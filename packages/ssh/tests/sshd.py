#!/usr/bin/env python3
"""The ssh transport's gate (docs/ssh-client.md SC11 step 4): ssh-tests
against a local sshd.

An sshd of its own is started on 127.0.0.1, as this user, with host keys of
each type made for the run (Ed25519, ECDSA P-256, RSA 3072) and a config
that says what the case needs; ssh-tests connects, makes the exchange, asks
for the ssh-userauth service, makes a second exchange and asks to
authenticate with `none`. Its lines are held to expected/CASE.txt.

The recorded sessions in replays/ are then run again with no server, and
must write the same bytes.

usage (after tests/build.sh):
    packages/ssh/tests/sshd.py            every case
    packages/ssh/tests/sshd.py --update   write the pins; read the diff first
    packages/ssh/tests/sshd.py --record   record replays/*.txt again
"""

import argparse
import re
import getpass
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / ".harness-work" / "ssh"
PINS = HERE / "expected"
REPLAYS = HERE / "replays"
CLIENT = HERE / "ssh-tests"
SSHD = "/usr/sbin/sshd"

CIPHERS = ["chacha20-poly1305@openssh.com", "aes256-gcm@openssh.com", "aes128-gcm@openssh.com"]
HOSTKEYS = ["ssh-ed25519", "ecdsa-sha2-nistp256", "rsa-sha2-512", "rsa-sha2-256"]

# name, client options, sshd config lines
CASES = [(f"{c.split('@')[0]}-{h}", ["--cipher", c, "--hostkey", h], []) for c in CIPHERS for h in HOSTKEYS] + [
    ("default", [], []),
    # the server rekeys on its own after 512 bytes, beside the client's
    ("server-rekeys", [], ["RekeyLimit 512"]),
    # OpenSSH takes no new exchange from a client before authentication
    ("client-rekeys-before-auth", ["--rekey"], []),
    # what the client offers and the server will not take
    ("no-shared-cipher", ["--cipher", "aes128-gcm@openssh.com"], ["Ciphers aes256-gcm@openssh.com"]),
    ("no-shared-hostkey", ["--hostkey", "ssh-ed25519"], ["HostKeyAlgorithms rsa-sha2-512"]),
    ("no-shared-kex", [], ["KexAlgorithms ecdh-sha2-nistp256"]),
    # a banner before the version is not something sshd sends; the server's
    # own lines are the client's to show
]

SEED = "00" * 31 + "01"

# user authentication (step 6): name, client options with {KEY} for a user
# key's file, sshd config lines. The authorized keys are ed, ecdsa521 and
# rsa; `other` is a key the server does not know.
LOGIN_CASES = [
    ("login-ed25519", ["--identity", "{ed}"], []),
    ("login-ecdsa521-passphrase", ["--identity", "{ecdsa521}", "--passphrase", "hunter2"], []),
    ("login-rsa", ["--identity", "{rsa}"], []),
    ("login-rsa-sha256-only", ["--identity", "{rsa}"], ["PubkeyAcceptedAlgorithms rsa-sha2-256"]),
    ("login-unknown-then-known", ["--identity", "{other}", "--identity", "{ed}"], []),
    ("login-wrong-passphrase", ["--identity", "{ecdsa521}", "--passphrase", "wrong"], []),
    ("login-max-tries", ["--identity", "{other}", "--identity", "{other2}", "--identity", "{other3}", "--identity", "{ed}"], ["MaxAuthTries 2"]),
    ("login-no-key", [], []),
    ("login-rekey", ["--identity", "{ed}", "--rekey"], []),
]


# the agent (step 6): name, the keys ssh-add gives an ssh-agent of the
# case's own (`-c` for one that must be confirmed, which with no askpass is
# refused), sshd config lines
AGENT_CASES = [
    ("login-agent-ed25519", [("ed", [])], []),
    ("login-agent-rsa", [("rsa", [])], []),
    ("login-agent-unknown-then-known", [("other", []), ("ed", [])], []),
    ("login-agent-confirm-refused", [("ed", ["-c"])], []),
]


# the session (step 7): name, client options after a login with the ed key,
# sshd config lines
SESSION_CASES = [
    ("session-euc-kr", ["--exec", r"printf '\307\321\261\333'", "--hex"], []),
    ("session-exit-3", ["--exec", "exit 3"], []),
    ("session-pty-size", ["--exec", "stty size", "--pty", "100,30"], []),
    ("session-resize", ["--exec", "read x; stty size; exit 5", "--pty", "100,30", "--resize", "120,40", "--stdin2", "\\n"], []),
    # the size in pixels pty-req and window-change carry (puritty
    # docs/images.md IM21): rows, columns, width, height as the pty says
    ("session-pty-pixels", ["--exec", "python3 -c 'import fcntl, termios, struct; print(*struct.unpack(\"4H\", fcntl.ioctl(0, termios.TIOCGWINSZ, bytes(8))))'", "--pty", "100,30,800,480"], []),
    ("session-resize-pixels", ["--exec", "read x; python3 -c 'import fcntl, termios, struct; print(*struct.unpack(\"4H\", fcntl.ioctl(0, termios.TIOCGWINSZ, bytes(8))))'; exit 5", "--pty", "100,30,800,480", "--resize", "120,40,960,640", "--stdin2", "\\n"], []),
    ("session-iutf8", ["--exec", "stty -a | tr ' ;' '\\n\\n' | grep iutf8", "--pty", "80,24"], []),
    ("session-not-iutf8", ["--exec", "stty -a | tr ' ;' '\\n\\n' | grep iutf8", "--pty", "80,24", "--not-utf8"], []),
    ("session-env", ["--exec", "echo $LANG", "--env", "LANG=ko_KR.EUC-KR"], ["AcceptEnv LANG"]),
    ("session-env-refused", ["--exec", "echo ${LANG:-unset}", "--env", "LANG=ko_KR.EUC-KR"], []),
    ("session-big-output", ["--exec", "head -c 5000000 /dev/zero"], []),
    ("session-big-input", ["--exec", "wc -c", "--stdin-bytes", "3000000", "--eof"], []),
    ("session-stderr", ["--exec", "echo oops >&2; exit 1"], []),
    ("session-signal", ["--exec", "kill -TERM $$"], []),
    ("session-keepalive", ["--exec", "sleep 1", "--keepalive"], []),
]


# Ssh.Session (step 8): name, how known_hosts starts (empty, holding the
# server's key, holding another key for it, or another key on a line that
# names another host too), client options. The
# port and the file's path are written as PORT and KNOWN_HOSTS in the pins.
SESSION_DRIVER_CASES = [
    ("driver-trust-remember", "empty", ["--identity", "{ed}", "--trust"]),
    ("driver-trust-once", "empty", ["--identity", "{ed}", "--trust-once"]),
    # the key file replaced by another key after the session read it and
    # before it signs: read again to sign, so the key it held is not used
    # (the code review's SC4, docs/ssh-client.md SC36)
    ("driver-key-file-replaced", "empty", ["--identity", "{edcopy}", "--trust-once", "--replace-before-trust", "{other}", "{edcopy}"]),
    ("driver-decline", "empty", ["--identity", "{ed}"]),
    ("driver-known", "known", ["--identity", "{ed}"]),
    ("driver-changed", "other", ["--identity", "{ed}", "--trust"]),
    # a changed key asked about (SC28): trusted once, put in place of the
    # old, refused with no question under StrictHostKeyChecking yes, and
    # put in place where the old line names another host too ("shared"),
    # which keeps that line
    ("driver-changed-once", "other", ["--identity", "{ed}", "--trust-changed-once"]),
    ("driver-changed-replace", "other", ["--identity", "{ed}", "--replace-changed"]),
    ("driver-changed-strict", "other", ["--identity", "{ed}", "--replace-changed", "--strict", "yes"]),
    ("driver-changed-shared", "shared", ["--identity", "{ed}", "--replace-changed"]),
    ("driver-strict-yes", "empty", ["--identity", "{ed}", "--strict", "yes"]),
    ("driver-accept-new", "empty", ["--identity", "{ed}", "--strict", "accept-new"]),
    # the host known by its ECDSA key, the server offering only Ed25519 (a
    # man in the middle's way, the code review's SC6): asked under
    # accept-new, as ask asks; taken under no, checking turned off
    ("driver-accept-new-other-type", "other-type", ["--identity", "{ed}", "--strict", "accept-new"]),
    ("driver-no-other-type", "other-type", ["--identity", "{ed}", "--strict", "no"]),
    # HostKeyAlias on the server's port, not 22: the key under the bare
    # alias, as OpenSSH writes and finds it (SC5, docs/ssh-client.md SC32)
    ("driver-alias-known", "alias", ["--identity", "{ed}", "--strict", "yes", "--host-key-alias", "box"]),
    # HashKnownHosts (SC31): the key written under a hashed name, which a
    # second connection under StrictHostKeyChecking yes then finds
    ("driver-accept-new-hashed", "empty", ["--identity", "{ed}", "--strict", "accept-new", "--hash-known-hosts"]),
    ("driver-passphrase", "known", ["--identity", "{ecdsa521}", "--passphrase", "hunter2"]),
    ("driver-wrong-passphrase", "known", ["--identity", "{ecdsa521}", "--passphrase", "wrong"]),
    ("driver-unknown-key-then-agentless", "known", ["--identity", "{other}", "--identity", "{rsa}"]),
    # first contact with a server that takes an RSA key as rsa-sha2-256
    # alone: its server-sig-algs comes while the host key is asked about,
    # and is kept for the login (the code review's SC14)
    ("driver-trust-rsa-sha256-only", "empty-rsa256", ["--identity", "{rsa}", "--trust-once"]),
]


# side channels beside the session (docs/sftp.md FT12): name, client
# options after the driver's own, sshd config lines. The session's command
# waits for a line, which the driver sends once every side channel is over,
# so a side channel's end never ends the session; each side channel's lines
# are said at the end by its number.
SFTP_SERVER = "/usr/lib/openssh/sftp-server"
SIDE_CASES = [
    ("side-exec", ["--side-exec", "echo side one; exit 2"], []),
    ("side-two", ["--side-exec", "echo a", "--side-exec", "echo b; exit 1"], []),
    # 3 MB pumped through the server's window, then the end
    ("side-stdin", ["--side-exec", "wc -c", "--side-stdin-bytes", "3000000", "--side-eof"], []),
    ("side-stderr", ["--side-exec", "echo oops >&2; exit 7"], []),
    ("side-sftp", ["--side-subsystem", "sftp", "--side-eof"], [f"Subsystem sftp {SFTP_SERVER}"]),
    # no Subsystem line: the request is refused, the channel closed, and
    # the session goes on
    ("side-sftp-off", ["--side-subsystem", "sftp"], []),
    # one session per connection: the side channel is not opened at all
    ("side-max-sessions", ["--side-exec", "echo never"], ["MaxSessions 1"]),
    # a side channel that refuses does not stop the next
    ("side-refused-then-exec", ["--side-subsystem", "nosuch", "--side-exec", "echo still"], []),
]


# the session's channel window (docs/ssh-client.md SC35): name, client
# options. 8 MB of newlines then "done": taken as it comes, the whole of it;
# taken by no one (`--hold-output`), no more than the 2 MiB window.
FLOW_COMMAND = "head -c 8000000 /dev/zero | tr '\\0' '\\n'; echo done"
FLOW_CASES = [
    ("flow-taken", []),
    ("flow-held", ["--hold-output"]),
]


# jump hosts (SC21): name, how many jump hosts before the host, which of
# the servers' keys known_hosts holds ("all", or "host" for the host's
# only), client options, sshd config lines for the jump hosts. The host is
# reached through each in turn, as `ssh -J` does; its port, and each jump
# host's, are written as PORT, JUMP1, JUMP2 in the pins. "down" sends the
# last jump host to a port nothing listens on.
JUMP_CASES = [
    ("jump-known", 1, "all", ["--identity", "{ed}"], []),
    ("jump-trust-bastion", 1, "host", ["--identity", "{ed}", "--trust-once"], []),
    ("jump-two-hops", 2, "all", ["--identity", "{ed}"], []),
    ("jump-forwarding-refused", 1, "all", ["--identity", "{ed}"], ["AllowTcpForwarding no"]),
    ("jump-host-down", 1, "all", ["--identity", "{ed}"], []),
]


class Agent:
    def __init__(self, keys, adds):
        self.path = WORK / f"agent.{os.getpid()}.{free_port()}"
        self.proc = subprocess.Popen(["ssh-agent", "-D", "-a", str(self.path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if self.path.exists():
                break
            time.sleep(0.05)
        env = dict(os.environ, SSH_AUTH_SOCK=str(self.path))
        env.pop("SSH_ASKPASS", None)
        env.pop("DISPLAY", None)
        for name, flags in adds:
            subprocess.run(["ssh-add", "-q", *flags, keys[name]], env=env, check=True, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        self.proc.terminate()
        self.proc.wait(5)
        self.path.unlink(missing_ok=True)


def user_keys():
    keys = WORK / "userkeys"
    names = {"ed": ("ed25519", None, ""), "ecdsa521": ("ecdsa", "521", "hunter2"), "rsa": ("rsa", "3072", ""),
             "other": ("ed25519", None, ""), "other2": ("ed25519", None, ""), "other3": ("ed25519", None, "")}
    if not (keys / "other3").exists():
        shutil.rmtree(keys, ignore_errors=True)
        keys.mkdir(parents=True)
        for name, (t, bits, passphrase) in names.items():
            subprocess.run(["ssh-keygen", "-q", "-t", t, *(["-b", bits] if bits else []), "-a", "4", "-N", passphrase, "-f", str(keys / name)], check=True)
        (keys / "authorized_keys").write_text("".join((keys / f"{n}.pub").read_text() for n in ["ed", "ecdsa521", "rsa"]))
    return {name: str(keys / name) for name in names}, keys / "authorized_keys"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def host_keys():
    keys = WORK / "keys"
    if not (keys / "ssh_host_rsa_key").exists():
        shutil.rmtree(keys, ignore_errors=True)
        keys.mkdir(parents=True)
        for t, bits in [("ed25519", None), ("ecdsa", "256"), ("rsa", "3072")]:
            subprocess.run(["ssh-keygen", "-q", "-t", t, *(["-b", bits] if bits else []), "-N", "", "-f", str(keys / f"ssh_host_{t}_key")], check=True)
    return keys


class Server:
    def __init__(self, extra):
        self.port = free_port()
        self.authorized = user_keys()[1]
        keys = host_keys()
        WORK.mkdir(parents=True, exist_ok=True)
        cfg = WORK / f"sshd_config.{self.port}"
        cfg.write_text("\n".join([
            f"Port {self.port}", "ListenAddress 127.0.0.1",
            *(f"HostKey {keys / f'ssh_host_{t}_key'}" for t in ["ed25519", "ecdsa", "rsa"]),
            f"PidFile {WORK / f'sshd.{self.port}.pid'}", "UsePAM no", "StrictModes no",
            "AuthenticationMethods publickey", f"AuthorizedKeysFile {self.authorized}", "LogLevel DEBUG1",
            *extra, ""]))
        self.log = open(WORK / f"sshd.{self.port}.log", "w")
        self.proc = subprocess.Popen([SSHD, "-D", "-e", "-f", str(cfg)], stdout=self.log, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.1).close()
                return
            except OSError:
                time.sleep(0.05)
        raise SystemExit(f"sshd did not start; see {self.log.name}")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.log.close()


def run_client(args, timeout=30):
    out = subprocess.run([str(CLIENT), *args], capture_output=True, text=True, timeout=timeout)
    return out.stdout + (f"[exit {out.returncode}]\n" if out.returncode else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()
    if not CLIENT.exists():
        sys.exit("sshd.py: build ssh-tests first (tests/build.sh)")
    fails = 0
    for name, options, extra in CASES:
        server = Server(extra)
        try:
            got = run_client(["connect", "127.0.0.1", str(server.port), *options])
        finally:
            server.stop()
        pin = PINS / f"{name}.txt"
        if a.update:
            PINS.mkdir(exist_ok=True)
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    keys = user_keys()[0]
    for name, options, extra in LOGIN_CASES:
        server = Server(extra)
        try:
            got = run_client(["login", "127.0.0.1", str(server.port), "--user", getpass.getuser(),
                              *(o.format(**keys) for o in options)])
        finally:
            server.stop()
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    for name, options, extra in SESSION_CASES:
        server = Server(extra)
        try:
            got = run_client(["login", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--identity", keys["ed"], *options])
        finally:
            server.stop()
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    other_key = WORK / "userkeys" / "other.pub"
    for name, start, options in SESSION_DRIVER_CASES:
        # a copy of the ed25519 key a case may replace, made again each case
        keys["edcopy"] = str(WORK / "userkeys" / "edcopy")
        shutil.copy(keys["ed"], keys["edcopy"])
        os.chmod(keys["edcopy"], 0o600)
        server = Server(["HostKeyAlgorithms ssh-ed25519"] if start == "other-type"
                        else ["PubkeyAcceptedAlgorithms rsa-sha2-256"] if start == "empty-rsa256" else [])
        kh = WORK / f"known_hosts.{name}"
        server_pub = (WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
        lookup = f"[127.0.0.1]:{server.port}"
        other_pub = " ".join(other_key.read_text().split()[:2])
        names = f"{lookup},elsewhere" if start == "shared" else lookup
        ecdsa_pub = " ".join((WORK / "keys" / "ssh_host_ecdsa_key.pub").read_text().split()[:2])
        if start == "other-type":
            kh.write_text(f"{names} {ecdsa_pub}\n")
        elif start == "alias":
            kh.write_text(f"box {' '.join(server_pub)}\n")
        else:
            kh.write_text("" if start in ("empty", "empty-rsa256") else f"{names} {' '.join(server_pub) if start == 'known' else other_pub}\n")
        try:
            got = run_client(["session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--known-hosts", str(kh),
                              "--exec", "echo hi; exit 4", *(o.format(**keys) for o in options)])
            got += "known_hosts holds the key: " + ("yes" if " ".join(server_pub) in kh.read_text() else "no") + "\n"
            if start in ("other", "shared"):
                got += "known_hosts holds the old key: " + ("yes" if other_pub in kh.read_text() else "no") + "\n"
            if "--hash-known-hosts" in options:
                got += "known_hosts names it hashed: " + ("yes" if kh.read_text().startswith("|1|") and lookup not in kh.read_text() else "no") + "\n"
                got += "again under yes:\n" + run_client(["session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--known-hosts", str(kh),
                                                          "--exec", "echo hi; exit 4", "--identity", keys["ed"], "--strict", "yes"])
        finally:
            server.stop()
        got = re.sub(r"SHA256:[A-Za-z0-9+/]+", "SHA256:FINGERPRINT", got.replace(str(kh), "KNOWN_HOSTS").replace(str(server.port), "PORT"))
        got = got.replace(f"as {getpass.getuser()}", "as USER").replace(str(WORK), "WORK")
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    server_pub = (WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    for name, options, extra in SIDE_CASES:
        server = Server(extra)
        kh = WORK / f"known_hosts.{name}"
        kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(server_pub)}\n")
        try:
            got = run_client(["session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--known-hosts", str(kh),
                              "--identity", keys["ed"], "--exec", "read x; echo main done", *options])
        finally:
            server.stop()
        got = re.sub(r"SHA256:[A-Za-z0-9+/]+", "SHA256:FINGERPRINT", got.replace(str(kh), "KNOWN_HOSTS").replace(str(server.port), "PORT"))
        got = got.replace(f"as {getpass.getuser()}", "as USER")
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    for name, options in FLOW_CASES:
        server = Server([])
        kh = WORK / f"known_hosts.{name}"
        kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(server_pub)}\n")
        try:
            got = run_client(["session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--known-hosts", str(kh),
                              "--identity", keys["ed"], "--exec", FLOW_COMMAND, *options])
        finally:
            server.stop()
        got = got.replace(str(server.port), "PORT").replace(f"as {getpass.getuser()}", "as USER")
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    for name, hops, known, options, extra in JUMP_CASES:
        host = Server([])
        jumps = [Server(extra) for _ in range(hops)]
        kh = WORK / f"known_hosts.{name}"
        ports = [host.port] + [j.port for j in jumps]
        if name == "jump-host-down":
            ports[0] = free_port()
        kh.write_text("".join(f"[127.0.0.1]:{p} {' '.join(server_pub)}\n" for p in (ports if known == "all" else ports[:1])))
        try:
            args = ["session", "127.0.0.1", str(ports[0]), "--user", getpass.getuser(), "--known-hosts", str(kh),
                    "--exec", "echo hi; echo $SSH_CONNECTION | cut -d' ' -f1; exit 4"]
            for j in jumps:
                args += ["--jump", f"127.0.0.1:{j.port}"]
            got = run_client(args + [o.format(**keys) for o in options])
        finally:
            host.stop()
            for j in jumps:
                j.stop()
        got = re.sub(r"SHA256:[A-Za-z0-9+/]+", "SHA256:FINGERPRINT", got.replace(str(kh), "KNOWN_HOSTS"))
        for i, j in enumerate(jumps):
            got = got.replace(str(j.port), f"JUMP{i + 1}")
        got = got.replace(str(ports[0]), "PORT").replace(f"as {getpass.getuser()}", "as USER")
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    for name, adds, extra in AGENT_CASES:
        server = Server(extra)
        agent = Agent(keys, adds)
        try:
            got = run_client(["login", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--agent", str(agent.path)])
        finally:
            agent.stop()
            server.stop()
        pin = PINS / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    if a.record:
        REPLAYS.mkdir(exist_ok=True)
        for cipher in CIPHERS:
            server = Server([f"Ciphers {cipher}"])
            try:
                run_client(["connect", "127.0.0.1", str(server.port), "--seed", SEED, "--record", str(REPLAYS / f"{cipher.split('@')[0]}.txt")])
            finally:
                server.stop()
            print("recorded", cipher)
    replays = sorted(REPLAYS.glob("*.txt")) if REPLAYS.exists() else []
    for replay in replays:
        got = run_client(["replay", str(replay)])
        if "replay: the same" in got:
            print(f"ok   replay {replay.stem}")
        else:
            fails += 1
            print(f"FAIL replay {replay.stem}\n  {got}")
    total = len(CASES) + len(LOGIN_CASES) + len(SESSION_CASES) + len(SESSION_DRIVER_CASES) + len(SIDE_CASES) + len(FLOW_CASES) + len(JUMP_CASES) + len(AGENT_CASES) + len(replays)
    if not a.update:
        print(f"{total - fails} of {total} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

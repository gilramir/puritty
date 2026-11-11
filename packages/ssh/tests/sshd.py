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
# server's key, or holding another key for it), client options. The
# port and the file's path are written as PORT and KNOWN_HOSTS in the pins.
SESSION_DRIVER_CASES = [
    ("driver-trust-remember", "empty", ["--identity", "{ed}", "--trust"]),
    ("driver-trust-once", "empty", ["--identity", "{ed}", "--trust-once"]),
    ("driver-decline", "empty", ["--identity", "{ed}"]),
    ("driver-known", "known", ["--identity", "{ed}"]),
    ("driver-changed", "other", ["--identity", "{ed}", "--trust"]),
    ("driver-strict-yes", "empty", ["--identity", "{ed}", "--strict", "yes"]),
    ("driver-accept-new", "empty", ["--identity", "{ed}", "--strict", "accept-new"]),
    ("driver-passphrase", "known", ["--identity", "{ecdsa521}", "--passphrase", "hunter2"]),
    ("driver-wrong-passphrase", "known", ["--identity", "{ecdsa521}", "--passphrase", "wrong"]),
    ("driver-unknown-key-then-agentless", "known", ["--identity", "{other}", "--identity", "{rsa}"]),
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
        server = Server([])
        kh = WORK / f"known_hosts.{name}"
        server_pub = (WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
        lookup = f"[127.0.0.1]:{server.port}"
        kh.write_text("" if start == "empty" else f"{lookup} {' '.join(server_pub if start == 'known' else other_key.read_text().split()[:2])}\n")
        try:
            got = run_client(["session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--known-hosts", str(kh),
                              "--exec", "echo hi; exit 4", *(o.format(**keys) for o in options)])
            got += "known_hosts holds the key: " + ("yes" if " ".join(server_pub) in kh.read_text() else "no") + "\n"
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
    server_pub = (WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
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
    total = len(CASES) + len(LOGIN_CASES) + len(SESSION_CASES) + len(SESSION_DRIVER_CASES) + len(JUMP_CASES) + len(AGENT_CASES) + len(replays)
    if not a.update:
        print(f"{total - fails} of {total} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

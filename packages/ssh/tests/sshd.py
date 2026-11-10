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
        keys = host_keys()
        WORK.mkdir(parents=True, exist_ok=True)
        cfg = WORK / f"sshd_config.{self.port}"
        cfg.write_text("\n".join([
            f"Port {self.port}", "ListenAddress 127.0.0.1",
            *(f"HostKey {keys / f'ssh_host_{t}_key'}" for t in ["ed25519", "ecdsa", "rsa"]),
            f"PidFile {WORK / f'sshd.{self.port}.pid'}", "UsePAM no", "StrictModes no",
            "AuthenticationMethods publickey", "AuthorizedKeysFile none", "LogLevel DEBUG1",
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
    total = len(CASES) + len(replays)
    if not a.update:
        print(f"{total - fails} of {total} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

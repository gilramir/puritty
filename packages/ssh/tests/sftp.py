#!/usr/bin/env python3
"""SFTP's gate (docs/sftp.md FT14): Ssh.Sftp's script of every request kind
(SftpDrive.script), against OpenSSH's sftp-server two ways, each held to
expected/NAME.txt:

- sftp-local: the server a child of ssh-tests, over pipes, no ssh;
- sftp-session: over a channel beside a session, `subsystem sftp`, to the
  local sshd of sshd.py with a `Subsystem` line.

What differs from machine to machine is written over: the directory used
as DIR, times other than the one the script sets as T, and a directory's
own size as DIRSIZE.

usage (after tests/build.sh):
    packages/ssh/tests/sftp.py            both
    packages/ssh/tests/sftp.py --update   write the pins; read the diff first
"""

import argparse, getpass, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sshd  # noqa: E402

SERVER = "/usr/lib/openssh/sftp-server"


def normalized(text, d):
    text = text.replace(str(d), "DIR")
    text = re.sub(r"mtime (?!1000000000\b)\d+", "mtime T", text)
    text = re.sub(r"^((?:stat sub|lstat /|mkdir[^:]*): )size \d+", r"\1size DIRSIZE", text, flags=re.M)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    work = sshd.WORK / "sftp"
    fails = 0
    results = {}
    d = work / "local"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    # sftp-server's files take its umask: 022, as sshd gives it, wherever this runs
    results["sftp-local"] = normalized(subprocess.run([str(HERE / "ssh-tests"), "sftp-local", SERVER, str(d)], capture_output=True, text=True, timeout=120,
                                                      preexec_fn=lambda: os.umask(0o022)).stdout, d)
    keys = sshd.user_keys()[0]
    server = sshd.Server([f"Subsystem sftp {SERVER}"])
    d = work / "session"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    kh = sshd.WORK / "known_hosts.sftp"
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    try:
        got = subprocess.run([str(HERE / "ssh-tests"), "session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--identity", keys["ed"],
                              "--known-hosts", str(kh), "--strict", "yes", "--exec", "read x", "--sftp", str(d)], capture_output=True, text=True, timeout=120).stdout
    finally:
        server.stop()
    results["sftp-session"] = normalized(got.replace(str(server.port), "PORT").replace(f"as {getpass.getuser()}", "as USER"), d)
    for name, got in results.items():
        pin = HERE / "expected" / f"{name}.txt"
        if a.update:
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    if not a.update:
        print(f"{len(results) - fails} of {len(results)} cases pass")
        sys.exit(1 if fails else 0)


main()

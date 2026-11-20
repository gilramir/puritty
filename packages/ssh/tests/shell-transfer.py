#!/usr/bin/env python3
"""Uploads through the host's shell (docs/sftp.md FT7, FT18):
`Ssh.ShellTransfer` driven by `ssh-tests session … --upload` over a session
to the local sshd of sshd.py, which has no `Subsystem` line, so it refuses
SFTP as a host with SFTP turned off does. Each case is transfer.py's
(its folders, its jobs), run through the shell instead, and pinned the
same way: what the engine said, and what the folders hold afterwards.
Beside them: the same refusal with the shell not allowed, a host that has
SFTP, and names a shell would misread.

    shell-transfer.py [--update] [CASE...]
"""
import argparse, getpass, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sshd  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("transfer", HERE / "transfer.py")
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)

CLIENT = HERE / "ssh-tests"
PINS = HERE / "expected" / "shell-transfer"
WORK = sshd.WORK / "shell-transfer"
SFTP_SERVER = "/usr/lib/openssh/sftp-server"


def c_odd_names(l, r):
    # quotes, a dollar, a glob, a space and a leading dash: each must reach
    # the host's shell as one word, as written
    names = ["it's \"one\".txt", "$HOME and *.txt", "-n"]
    for n in names:
        transfer.put(l / n, n.encode() + b"\n", transfer.OLD)
    args = []
    for n in names:
        args += ["up", l / n, r, n]
    return args


def c_large(l, r):
    # far more than the engine keeps read ahead (256 KiB), so the channel's
    # queue paces the reads
    transfer.put(l / "large.bin", transfer.pattern((5 << 20) + 3), transfer.NEWER)
    return ["up", l / "large.bin", r, "large.bin"]


def c_not_allowed(l, r):
    transfer.put(l / "a.txt", b"a\n")
    return ["up", l / "a.txt", r, "a.txt"]


# each: (name, setup, whether the shell is allowed, the server's extra lines)
CASES = [(name, setup, True, []) for name, setup in transfer.CASES if name != "rename-refused"] + [
    ("odd-names", c_odd_names, True, []),
    ("large", c_large, True, []),
    ("not-allowed", c_not_allowed, False, []),
    ("host-has-sftp", c_not_allowed, True, [f"Subsystem sftp {SFTP_SERVER}"]),
]


def run_case(name, setup, allow, extra, keys):
    d = WORK / name
    shutil.rmtree(d, ignore_errors=True)
    l, r = d / "local", d / "remote"
    l.mkdir(parents=True)
    r.mkdir(parents=True)
    args = [str(a) for a in setup(l, r)]
    before = WORK / f"{name}.before"
    shutil.rmtree(before, ignore_errors=True)
    shutil.copytree(d, before, symlinks=True)
    server = sshd.Server(extra)
    kh = WORK / f"known_hosts.{name}"
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    try:
        out = subprocess.run([str(CLIENT), "session", "127.0.0.1", str(server.port), "--user", getpass.getuser(), "--identity", keys["ed"],
                              "--known-hosts", str(kh), "--strict", "yes", "--exec", "read x",
                              "--upload", *(["--allow-shell"] if allow else []), *args],
                             capture_output=True, text=True, timeout=120, preexec_fn=lambda: os.umask(0o002))
    finally:
        server.stop()
    said = out.stdout.replace(str(d), "DIR")
    sources = {}
    for side, other in [("local", "remote"), ("remote", "local")]:
        for p in (before / other).rglob("*"):
            if p.is_file():
                sources.setdefault((side, p.name), p)
    report = [said.rstrip("\n")]
    for side in ["local", "remote"]:
        report.append(f"{side}:")
        report += transfer.listing(d / side, {n: p for (s, n), p in sources.items() if s == side})
    shutil.rmtree(before, ignore_errors=True)
    return "\n".join(report) + "\n" + (f"[exit {out.returncode}]\n" if out.returncode else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    if not CLIENT.exists():
        sys.exit("shell-transfer.py: build ssh-tests first (tests/build.sh)")
    keys = sshd.user_keys()[0]
    fails = 0
    ran = 0
    for name, setup, allow, extra in CASES:
        if a.only and name not in a.only:
            continue
        ran += 1
        got = run_case(name, setup, allow, extra, keys)
        pin = PINS / f"{name}.txt"
        if a.update:
            PINS.mkdir(parents=True, exist_ok=True)
            pin.write_text(got)
            print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {name}")
    print(f"{ran - fails} of {ran} cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

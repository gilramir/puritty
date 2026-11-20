#!/usr/bin/env python3
"""The transfer engine's gate (docs/sftp.md FT17): `Ssh.Transfer` driven by
`ssh-tests transfer-local` against OpenSSH's `sftp-server` over pipes, one
batch a case, each in folders of its own (`local/` and `remote/`, both on
this machine, the server's being "the host"). A case sets the folders up,
runs the batch, and its pin holds what the engine said and what is in the
folders afterwards: each file's size, mode, whether its bytes are what
was sent, and whether its time is the source's.

    transfer.py [--update] [CASE...]
"""
import argparse, os, shutil, stat, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIENT = HERE / "ssh-tests"
SERVER = "/usr/lib/openssh/sftp-server"
PINS = HERE / "expected" / "transfer"
WORK = HERE.parent.parent.parent / ".harness-work" / "transfer"
OLD = 1577934245  # 2020-01-02, a time no file made now has
NEWER = 1609470245  # 2021-01-01


def put(path, data, mtime=None, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mode is not None:
        path.chmod(mode)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def pattern(n):
    """n bytes that differ from piece to piece, so a piece out of place shows."""
    return bytes((i * 7 + i // 32768) % 251 for i in range(n))


# each case: (name, setup(local, remote), argv(local, remote), options)
def c_new(l, r):
    put(l / "a.txt", b"hello\n", OLD)
    put(l / "b.bin", pattern(1000001))
    put(l / "empty.txt", b"")
    put(l / "sub" / "c.txt", b"c\n", NEWER)
    return ["up", l / "a.txt", r, "a.txt", "up", l / "b.bin", r, "b.bin", "up", l / "empty.txt", r, "empty.txt",
            "mkdir", r / "sub", "up", l / "sub" / "c.txt", r / "sub", "c.txt"]


def c_skip(l, r):
    put(l / "a.txt", b"new\n", NEWER)
    put(r / "a.txt", b"old\n", OLD)
    put(l / "b.txt", b"b\n")
    return ["--choice", "skip", "up", l / "a.txt", r, "a.txt", "up", l / "b.txt", r, "b.txt"]


def c_replace(l, r):
    # replaced in place: the host's mode, 0600, kept
    put(l / "a.txt", b"new and longer\n", NEWER)
    put(r / "a.txt", b"old\n", OLD, 0o600)
    return ["--choice", "replace", "up", l / "a.txt", r, "a.txt"]


def c_keep(l, r):
    put(l / "a.txt", b"new\n")
    put(r / "a.txt", b"old\n")
    put(r / "a (2).txt", b"older\n")
    put(l / "noext", b"n\n")
    put(r / "noext", b"m\n")
    put(l / ".hidden", b"h\n")
    put(r / ".hidden", b"g\n")
    return ["--choice", "keep", "up", l / "a.txt", r, "a.txt", "up", l / "noext", r, "noext", "up", l / ".hidden", r, ".hidden"]


def c_newer(l, r):
    put(l / "x.txt", b"newer here\n", NEWER)
    put(r / "x.txt", b"older there\n", OLD)
    put(l / "y.txt", b"older here\n", OLD)
    put(r / "y.txt", b"newer there\n", NEWER)
    return ["--choice", "newer", "up", l / "x.txt", r, "x.txt", "up", l / "y.txt", r, "y.txt"]


def c_stale_part(l, r):
    # a part left by a transfer that broke is puritty's: removed, made again
    put(l / "d.txt", b"d\n")
    put(r / ".d.txt.puritty-part", b"half a fi")
    return ["up", l / "d.txt", r, "d.txt"]


def c_no_folder(l, r):
    put(l / "a.txt", b"a\n")
    return ["up", l / "a.txt", r / "missing", "a.txt"]


def c_folder_in_way(l, r):
    put(l / "e", b"e\n")
    (r / "e").mkdir(parents=True)
    return ["up", l / "e", r, "e"]


def c_mkdir(l, r):
    (r / "there").mkdir(parents=True)
    put(r / "afile", b"f\n")
    return ["mkdir", r / "there", "mkdir", r / "afile", "mkdir", r / "new"]


def c_download(l, r):
    put(r / "dl.bin", pattern(300001), OLD)
    l.mkdir(parents=True, exist_ok=True)
    return ["down", r / "dl.bin", l / "dl.bin", l / ".dl.bin.part", l / "dl (2).bin"]


def c_download_keep(l, r):
    put(r / "dl.bin", pattern(70000))
    put(l / "dl.bin", b"mine\n")
    return ["--choice", "keep", "down", r / "dl.bin", l / "dl.bin", l / ".dl.bin.part", l / "dl (2).bin"]


def c_cancel(l, r):
    put(l / "big.bin", pattern(8 << 20))
    put(l / "after.txt", b"never sent\n")
    return ["--cancel-after", "3", "up", l / "big.bin", r, "big.bin", "up", l / "after.txt", r, "after.txt"]


def c_no_rename(l, r):
    # a server that refuses renames (sftp-server -P): the part removed, and
    # the file written under its own name
    put(l / "f.txt", b"written in place\n", OLD)
    return ["up", l / "f.txt", r, "f.txt"]


# a case's server, when not SERVER as it is
SERVERS = {"rename-refused": ["-P", "rename,posix-rename"]}


CASES = [
    ("new-files", c_new), ("conflict-skip", c_skip), ("conflict-replace", c_replace), ("conflict-keep-both", c_keep),
    ("conflict-replace-if-newer", c_newer), ("stale-part", c_stale_part), ("no-such-folder", c_no_folder),
    ("folder-in-the-way", c_folder_in_way), ("make-folders", c_mkdir), ("download", c_download),
    ("download-keep-both", c_download_keep), ("cancel", c_cancel), ("rename-refused", c_no_rename),
]


def listing(top, sources):
    """Each file under `top`: size, mode, and whether its bytes and time are
    those of the file it came from (by name, from `sources`)."""
    lines = []
    for p in sorted(top.rglob("*")):
        rel = p.relative_to(top)
        st = p.lstat()
        if stat.S_ISDIR(st.st_mode):
            lines.append(f"  {rel}/")
            continue
        line = f"  {rel}: {st.st_size} bytes, mode {oct(st.st_mode & 0o777)}"
        src = sources.get(p.name)
        if src is not None and src != p and src.exists():
            line += f", bytes {'same' if src.read_bytes() == p.read_bytes() else 'DIFFERENT'} as {src.parent.name}/{src.name}"
            line += f", time {'same' if int(src.stat().st_mtime) == int(st.st_mtime) else 'not kept'}"
        lines.append(line)
    return lines


def run_case(name, setup):
    d = WORK / name
    shutil.rmtree(d, ignore_errors=True)
    l, r = d / "local", d / "remote"
    l.mkdir(parents=True)
    r.mkdir(parents=True)
    args = [str(a) for a in setup(l, r)]
    # what each file should equal: the other side's of the same name, as it
    # was before the batch
    before = WORK / f"{name}.before"
    shutil.rmtree(before, ignore_errors=True)
    shutil.copytree(d, before, symlinks=True)
    server = SERVER
    if name in SERVERS:
        # ssh-tests runs the server with no arguments: a script gives them
        server = str(d / "server.sh")
        Path(server).write_text(f"#!/bin/sh\nexec {SERVER} {' '.join(SERVERS[name])}\n")
        Path(server).chmod(0o755)
    out = subprocess.run([str(CLIENT), "transfer-local", server, *args], capture_output=True, text=True, timeout=120,
                         preexec_fn=lambda: os.umask(0o002))
    said = out.stdout.replace(str(d), "DIR")
    sources = {}
    for side, other in [("local", "remote"), ("remote", "local")]:
        for p in (before / other).rglob("*"):
            if p.is_file():
                sources.setdefault((side, p.name), p)
    report = [said.rstrip("\n")]
    (d / "server.sh").unlink(missing_ok=True)
    for side in ["local", "remote"]:
        report.append(f"{side}:")
        report += listing(d / side, {n: p for (s, n), p in sources.items() if s == side})
    shutil.rmtree(before, ignore_errors=True)
    return "\n".join(report) + "\n" + (f"[exit {out.returncode}]\n" if out.returncode else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    if not CLIENT.exists():
        sys.exit("transfer.py: build ssh-tests first (tests/build.sh)")
    fails = 0
    ran = 0
    for name, setup in CASES:
        if a.only and name not in a.only:
            continue
        ran += 1
        got = run_case(name, setup)
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

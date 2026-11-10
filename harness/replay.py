#!/usr/bin/env python3
"""The replay corpus and the differential oracle (docs/vt-core.md §VC4).

Each case is a directory of corpus/replay/ holding `case.txt`: a first line
`size COLSxROWS`, then the bytes the terminal is fed, written with escapes
(below). The case's `expected.txt` is the screen dump (§VC3) the core must
print, fed the whole file in one read and again a byte a read.
libghostty-vt, through harness/oracle/ghostty-dump, must print the
same, unless the case has a `divergence.txt` saying why it does not; then
ghostty's own dump is pinned in `ghostty.txt`, so a change on either side is
seen.

In case.txt after the size line, a newline in the file is not a byte (so
long inputs can be wrapped) and these escapes are:

    \\e  ESC      \\r  CR      \\n  LF      \\t  HT      \\b  BS
    \\a  BEL      \\\\  a backslash          \\xHH  the byte HH
    \\s  a space (for one at the end of a line, which editors trim)
    \\R{COLSxROWS}  no byte: the terminal is resized here, as its host
                    resizes it (docs/vt-core.md §VC14)

Every other byte is itself, UTF-8 as written.

usage:
    harness/replay.py                 every case, both sides
    harness/replay.py -f wrap         cases whose name contains "wrap"
    harness/replay.py --side ghostty  only the oracle
    harness/replay.py --update        write expected.txt from the core and
                                      ghostty.txt from ghostty (divergent
                                      cases only); read the diff before
                                      committing it
    harness/replay.py --update --side ghostty
                                      seed expected.txt from ghostty, for a
                                      new case the core does not pass yet
    harness/replay.py --windows beelink1
                                      the core's side on Windows

With `--windows HOST` the core's side runs on a Windows machine instead
(docs/windows.md WS12 step 6, WS22): harness/dump/core-dump.exe
(harness/dump/build-windows.sh), the cases' bytes and harness/dump/run.ps1
are copied to `geng-probe/replay` in the home directory there over ssh,
every run of every case is made in one ssh call, and the dumps come back to
be held to the same expected.txt. ghostty is not run (its pins are Linux's
and say nothing of Windows), and nothing is updated.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "replay"
GHOSTTY = ROOT / "harness" / "oracle" / "ghostty-dump"
CORE = ROOT / "harness" / "dump" / "core-dump"
CORE_EXE = ROOT / "harness" / "dump" / "core-dump.exe"
WORK = ROOT / ".harness-work" / "replay"
REMOTE = "geng-probe/replay"

ESCAPES = {
    "e": b"\x1b", "r": b"\r", "n": b"\n", "t": b"\t", "b": b"\b",
    "a": b"\x07", "\\": b"\\", "s": b" ",
}


def parse_case(text):
    """The size, and the bytes with no resizes."""
    cols, rows, data, _ = parse_resizing(text)
    return cols, rows, data


def parse_resizing(text):
    """The size, the bytes, and the resizes, each (offset, cols, rows)."""
    head, _, body = text.partition("\n")
    words = head.split()
    if len(words) != 2 or words[0] != "size":
        raise ValueError("first line must be `size COLSxROWS`")
    cols, rows = (int(n) for n in words[1].split("x"))
    out = bytearray()
    resizes = []
    raw = body.replace("\n", "").encode("utf-8")
    i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        k = raw[i + 1:i + 2].decode()
        if k == "x":
            out.append(int(raw[i + 2:i + 4], 16))
            i += 4
        elif k in ESCAPES:
            out += ESCAPES[k]
            i += 2
        elif k == "R":
            end = raw.index(b"}", i)
            c, r = (int(n) for n in raw[i + 3:end].decode().split("x"))
            if not (1 <= c <= 256 and r >= 1):
                raise ValueError(f"resize to {c}x{r} at byte {i}")
            resizes.append((len(out), c, r))
            i = end + 1
        else:
            raise ValueError(f"unknown escape \\{k} at byte {i}")
    return cols, rows, bytes(out), resizes


def side_args(exe, chunk, resizes):
    extra = [] if chunk is None else [str(chunk)]
    if resizes:
        if exe == CORE and chunk is None:
            extra = ["0"]
        extra.append(",".join(f"{a}:{c}x{r}" for a, c, r in resizes))
    return extra


def run_side(exe, cols, rows, path, chunk=None, resizes=()):
    extra = side_args(exe, chunk, resizes)
    p = subprocess.run(
        ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G",
         "-p", "MemorySwapMax=0", "--", "timeout", "60",
         str(exe), str(cols), str(rows), str(path)] + extra,
        capture_output=True)
    if p.returncode != 0:
        return None, p.stderr.decode(errors="replace").strip()
    return p.stdout.decode("utf-8", errors="replace"), None


def run_windows(host, runs):
    """Every core run on `host` in one call: `runs` maps a name to the
    case's size, bytes, chunk and resizes; the answer maps each name to
    (dump, None) or (None, why)."""
    stage = WORK / "windows"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    lines, bins = [], {}
    for name, (cols, rows, data, chunk, resizes) in runs.items():
        case = name.split(".")[0]
        if case not in bins:
            bins[case] = stage / f"{case}.bin"
            bins[case].write_bytes(data)
        lines.append("\t".join([f"{name}.txt", str(cols), str(rows), f"{case}.bin",
                                 *side_args(CORE, chunk, resizes)]))
    (stage / "runs.tsv").write_text("\n".join(lines) + "\n")
    ssh = ["ssh", "-o", "BatchMode=yes", host]
    subprocess.run(ssh + [f"powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path {REMOTE} | Out-Null;"
                          f" Remove-Item {REMOTE}\\* -ErrorAction SilentlyContinue\""], check=True)
    subprocess.run(["scp", "-q", str(CORE_EXE), str(ROOT / "harness" / "dump" / "run.ps1"),
                    *map(str, stage.glob("*")), f"{host}:{REMOTE}/"], check=True)
    p = subprocess.run(ssh + [f"powershell -NoProfile -ExecutionPolicy Bypass -File {REMOTE}\\run.ps1"],
                       capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        raise RuntimeError((p.stdout + p.stderr).strip())
    back = stage / "back"
    back.mkdir()
    subprocess.run(["scp", "-q", f"{host}:{REMOTE}/*.txt", str(back)], check=True)
    failures = {}
    for line in (back / "failures.txt").read_text(errors="replace").splitlines():
        out, _, why = line.partition("\t")
        failures[out] = why
    answers = {}
    for name in runs:
        f = back / f"{name}.txt"
        if f"{name}.txt" in failures:
            answers[name] = (None, failures[f"{name}.txt"])
        elif not f.exists():
            answers[name] = (None, "no dump came back")
        else:
            answers[name] = (f.read_bytes().decode("utf-8", errors="replace"), None)
    return answers


def first_difference(a, b):
    al, bl = a.splitlines(), b.splitlines()
    for n, (x, y) in enumerate(zip(al, bl)):
        if x != y:
            return f"line {n + 1}: want {x!r}, got {y!r}"
    return f"want {len(al)} lines, got {len(bl)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-f", "--filter", default="")
    ap.add_argument("--side", choices=["both", "core", "ghostty"], default="both")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--windows", metavar="HOST", default="")
    args = ap.parse_args()

    sides = ["core", "ghostty"] if args.side == "both" else [args.side]
    if args.windows:
        if args.update or args.side == "ghostty":
            sys.exit("replay.py: --windows runs the core's side only, and updates nothing")
        sides = ["core"]
        if not CORE_EXE.exists():
            sys.exit(f"{CORE_EXE} is not built: run {CORE_EXE.parent}/build-windows.sh")
    else:
        for side, exe in (("core", CORE), ("ghostty", GHOSTTY)):
            if side in sides and not exe.exists():
                sys.exit(f"{exe} is not built: run {exe.parent}/build.sh")

    cases = sorted(d for d in CORPUS.iterdir()
                   if d.is_dir() and args.filter in d.name)
    remote = None
    if args.windows:
        runs = {}
        for case in cases:
            try:
                cols, rows, data, resizes = parse_resizing((case / "case.txt").read_text())
            except ValueError:
                continue
            runs[case.name] = (cols, rows, data, None, resizes)
            if (case / "expected.txt").exists():
                runs[case.name + ".bytewise"] = (cols, rows, data, 1, resizes)
        remote = run_windows(args.windows, runs)

    def core(case, cols, rows, path, chunk=None, resizes=()):
        if remote is not None:
            return remote[case.name + (".bytewise" if chunk == 1 else "")]
        return run_side(CORE, cols, rows, path, chunk, resizes)
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for case in cases:
            try:
                cols, rows, data, resizes = parse_resizing(
                    (case / "case.txt").read_text())
            except ValueError as e:
                print(f"FAIL {case.name}: case.txt: {e}")
                failed += 1
                continue
            path = Path(tmp) / f"{case.name}.bin"
            path.write_bytes(data)
            divergent = (case / "divergence.txt").exists()
            expected = case / "expected.txt"
            want_core = expected.read_text() if expected.exists() else None
            notes = []
            if "core" in sides and not args.update and want_core is not None:
                # The same bytes a read of one byte each: every state the
                # parser can be cut in is left and picked up again.
                out, err = core(case, cols, rows, path, 1, resizes)
                if out is None:
                    notes.append(f"core, a byte a read, crashed: {err}")
                elif out != want_core:
                    notes.append("core, a byte a read: "
                                 + first_difference(want_core, out))
            for side in sides:
                if side == "core":
                    out, err = core(case, cols, rows, path, resizes=resizes)
                else:
                    out, err = run_side(GHOSTTY, cols, rows, path, resizes=resizes)
                if out is None:
                    notes.append(f"{side} crashed: {err}")
                    continue
                if side == "ghostty" and divergent:
                    pin = case / "ghostty.txt"
                else:
                    pin = expected
                if args.update and (side == "core" or divergent
                                    or args.side == "ghostty"):
                    pin.write_text(out)
                    continue
                want = pin.read_text() if pin.exists() else None
                if want is None:
                    notes.append(f"{side}: no {pin.name}")
                elif out != want:
                    notes.append(f"{side}: {first_difference(want, out)}")
                    if args.verbose:
                        notes.append(out)
            if divergent and want_core is not None and "ghostty" in sides:
                g = case / "ghostty.txt"
                if g.exists() and g.read_text() == want_core:
                    notes.append("divergence.txt, but ghostty agrees now")
            if notes:
                failed += 1
                print(f"FAIL {case.name}")
                for n in notes:
                    print(f"     {n}")
            else:
                tag = " (divergent)" if divergent else ""
                print(f"ok   {case.name}{tag}")
    print(f"{len(cases) - failed} of {len(cases)} cases pass")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

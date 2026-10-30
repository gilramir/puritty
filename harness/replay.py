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
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "replay"
GHOSTTY = ROOT / "harness" / "oracle" / "ghostty-dump"
CORE = ROOT / "harness" / "dump" / "core-dump"

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


def run_side(exe, cols, rows, path, chunk=None, resizes=()):
    extra = [] if chunk is None else [str(chunk)]
    if resizes:
        if exe == CORE and chunk is None:
            extra = ["0"]
        extra.append(",".join(f"{a}:{c}x{r}" for a, c, r in resizes))
    p = subprocess.run(
        ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G",
         "-p", "MemorySwapMax=0", "--", "timeout", "60",
         str(exe), str(cols), str(rows), str(path)] + extra,
        capture_output=True)
    if p.returncode != 0:
        return None, p.stderr.decode(errors="replace").strip()
    return p.stdout.decode("utf-8", errors="replace"), None


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
    args = ap.parse_args()

    sides = ["core", "ghostty"] if args.side == "both" else [args.side]
    for side, exe in (("core", CORE), ("ghostty", GHOSTTY)):
        if side in sides and not exe.exists():
            sys.exit(f"{exe} is not built: run {exe.parent}/build.sh")

    cases = sorted(d for d in CORPUS.iterdir()
                   if d.is_dir() and args.filter in d.name)
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
                out, err = run_side(CORE, cols, rows, path, 1, resizes)
                if out is None:
                    notes.append(f"core, a byte a read, crashed: {err}")
                elif out != want_core:
                    notes.append("core, a byte a read: "
                                 + first_difference(want_core, out))
            for side in sides:
                out, err = run_side(CORE if side == "core" else GHOSTTY,
                                    cols, rows, path, resizes=resizes)
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

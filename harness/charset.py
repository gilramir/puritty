#!/usr/bin/env python3
"""The EUC-KR filter gate (docs/phase3-input.md V49): harness/charset/core-charset
runs Vt.Charset on cjk-and-thai.md §10.5's cases and on every code point of
WHATWG's index, and its lines are held to corpus/charset/expected.txt.

    harness/charset.py            check
    harness/charset.py --update   write expected.txt; read the diff first

Build the program first (charset/build.sh).
"""
import argparse, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).parent
EXPECTED = HERE / "../corpus/charset/expected.txt"
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--update", action="store_true")
a = ap.parse_args()
got = subprocess.run([str(HERE / "charset/core-charset")], capture_output=True, text=True, check=True).stdout
if a.update:
    EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    EXPECTED.write_text(got)
    print(got, end="")
    sys.exit(0)
want = EXPECTED.read_text()
if got == want:
    print(f"ok: {len(got.splitlines())} lines")
    sys.exit(0)
for w, g in zip(want.splitlines(), got.splitlines()):
    if w != g:
        print(f"want {w}\ngot  {g}")
print("FAIL")
sys.exit(1)

#!/usr/bin/env python3
"""The selection gate (docs/phase3-select.md §14): Vt.selectionText,
Vt.wordAt and Vt.lineAt on each case of corpus/select/.

A case is a directory with case.txt (harness/replay.py's format: the size,
then the input, escaped) and queries.txt (harness/select/src/Main.geng says
what a query is); harness/select/core-select feeds the input to the core,
256-row pages so a short case reaches them, answers each query a line, and
the lines are held to the case's expected.txt.

usage:
    harness/select.py              every case
    harness/select.py -f word      cases whose name contains "word"
    harness/select.py --update     write expected.txt; read the diff first

Build the program first (select/build.sh).
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import parse_resizing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "corpus" / "select"
PROGRAM = ROOT / "harness" / "select" / "core-select"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-f", dest="filter", default="")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    fails = runs = 0
    for d in sorted(p for p in CASES.iterdir() if p.is_dir() and a.filter in p.name):
        cols, rows, data, _ = parse_resizing((d / "case.txt").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input"
            inp.write_bytes(data)
            got = subprocess.run([str(PROGRAM), str(cols), str(rows), str(inp), str(d / "queries.txt")],
                                 capture_output=True, text=True, check=True).stdout
        runs += 1
        pin = d / "expected.txt"
        if a.update:
            pin.write_text(got)
            print(f"== {d.name}\n{got}", end="")
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            want = pin.read_text().splitlines() if pin.exists() else []
            print(f"FAIL {d.name}")
            for i, g in enumerate(got.splitlines()):
                w = want[i] if i < len(want) else "(none)"
                if w != g:
                    print(f"  want {w}\n  got  {g}")
    if not a.update:
        print(f"{'FAIL' if fails else 'ok'}: {runs - fails} of {runs} cases")
    return 1 if fails else 0


sys.exit(main())

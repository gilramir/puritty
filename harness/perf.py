#!/usr/bin/env python3
"""Holds the core's speed to its recorded numbers (docs/vt-core.md §VC34).

Two kinds of case, each counted in user-space instructions (`perf stat -e
instructions:u`) with address-space randomization off (`setarch -R`), which
makes a count repeat to within a few dozen instructions of a billion:

- **throughput**: `core-bench FILE`, the thirteen inputs of §VC7 fed at 160
  by 50 with the default scrollback. Each also has the time budget of
  `geng-plan.md` §1.4, checked as §VC7 measures it: one untimed run, then the
  least of five times `core-bench` reports.
- **resize**: `core-bench FILE resizes 20 80 50 [BYTES]`, twenty resizes
  between 160 and 80 columns, less `resizes 0`, the feeding alone, so the
  count is the resizes' own. Five inputs (§VC31), with the default limit and
  with none (`unlimited`, as §VC32 compares with Ghostty).

The recorded numbers are corpus/perf/baseline.tsv, with each input's
SHA-256: a changed input is an error, not a comparison. A count more than
--tolerance percent above its record (1 for throughput, 3 for a resize
unless told) fails the run, as does a time over its budget. A count more
than that below its record is reported, so that the record can be brought
down with --update and a later loss is not hidden by an earlier gain.

The thirteen throughput inputs are not generated here (vtebench's are a
pty's capture, `probes/throughput/gen-vtebench.py`): they are read from
.harness-work/perf/inputs, which `--inputs DIR` fills from a copy once. The
resize inputs are written by this script, and gitlog.txt is the
throughput one.

  ./harness/bench/build.sh
  ./harness/perf.py                       # everything
  ./harness/perf.py --no-times            # counts only, on a busy machine
  ./harness/perf.py -f resize             # cases whose name contains it
  ./harness/perf.py --update              # write the counts as the record
  ./harness/perf.py --inputs DIR          # copy the thirteen inputs in first

Times need a quiet machine: do not run it beside the fuzzers or a gate.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "harness/bench/core-bench"
WORK = ROOT / ".harness-work/perf"
INPUTS = WORK / "inputs"
BASELINE = ROOT / "corpus/perf/baseline.tsv"

# geng-plan.md §1.4's budgets, in ms (vt-core.md §VC7)
BUDGETS = {
    "cup": 56,
    "gitlog": 132,
    "ls": 124,
    "vte-cursor_motion": 28,
    "vte-dense_cells": 28,
    "vte-light_cells": 24,
    "vte-scrolling": 42,
    "vte-scrolling_bottom_region": 37,
    "vte-scrolling_bottom_small_region": 132,
    "vte-scrolling_fullscreen": 45,
    "vte-scrolling_top_region": 223,
    "vte-scrolling_top_small_region": 125,
    "vte-unicode": 25,
}

UNLIMITED = 2000000000


def long_line(rows):
    return b"a" * (160 * rows)


def short_lines(n):
    return b"".join(b"line %06d the quick brown fox jumps over the lazy dog\r\n" % i for i in range(n))


RESIZE_INPUTS = {
    "long-10000": lambda: long_line(10000),
    "long-100000": lambda: long_line(100000),
    "short-10000": lambda: short_lines(10000),
    "short-100000": lambda: short_lines(100000),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def resize_input(name):
    if name == "gitlog":
        return INPUTS / "gitlog.txt"
    path = WORK / "resize" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(RESIZE_INPUTS[name]())
    return path


def cases():
    """(name, file, core-bench arguments after FILE, budget or None, kind)"""
    out = []
    for name in sorted(BUDGETS):
        out.append((f"throughput/{name}", INPUTS / f"{name}.txt", [], BUDGETS[name], "throughput"))
    for name in ["long-10000", "long-100000", "short-10000", "short-100000", "gitlog"]:
        for limit, extra in [("default", []), ("unlimited", [str(UNLIMITED)])]:
            out.append((f"resize/{limit}/{name}", None, extra, None, "resize"))
    return out


def run(args, memory="12G"):
    cmd = ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={memory}", "-p", "MemorySwapMax=0", "--"] + args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        sys.exit(f"perf.py: {' '.join(args)} failed ({p.returncode}):\n{p.stdout}{p.stderr}")
    return p


def instructions(file, extra):
    p = run(["setarch", "-R", "perf", "stat", "-x,", "-e", "instructions:u", str(BENCH), str(file)] + extra)
    for line in p.stderr.splitlines():
        fields = line.split(",")
        if len(fields) > 2 and fields[2].startswith("instructions"):
            return int(fields[0])
    sys.exit(f"perf.py: no count from perf stat:\n{p.stderr}")


def least_time(file, runs=5):
    run([str(BENCH), str(file)])  # untimed: the clock comes up from idle (§VC7)
    times = []
    for _ in range(runs):
        out = run([str(BENCH), str(file)]).stdout
        times.append(int(out.split(" in ")[1].split(" ms")[0]))
    return min(times), max(times)


def load_baseline():
    rows = {}
    if BASELINE.exists():
        for line in BASELINE.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            name, digest, count = line.split("\t")[:3]
            rows[name] = (digest, int(count))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-f", dest="filter", default="", help="only cases whose name contains this")
    ap.add_argument("--update", action="store_true", help="write the counts as the record")
    ap.add_argument("--no-times", action="store_true", help="skip the time budgets")
    ap.add_argument("--inputs", help="copy the thirteen throughput inputs from this directory first")
    ap.add_argument("--tolerance", type=float, help="percent over the record that fails (default 1, resizes 3)")
    a = ap.parse_args()

    if a.inputs:
        INPUTS.mkdir(parents=True, exist_ok=True)
        for name in BUDGETS:
            shutil.copyfile(Path(a.inputs) / f"{name}.txt", INPUTS / f"{name}.txt")
    if not BENCH.exists():
        sys.exit(f"{BENCH} is not built: run {BENCH.parent}/build.sh")
    missing = [n for n in BUDGETS if not (INPUTS / f"{n}.txt").exists()]
    if missing:
        sys.exit(f"perf.py: {INPUTS} lacks {', '.join(missing)}: give --inputs DIR once")

    base = load_baseline()
    new = dict(base)
    failed, lower = [], []
    for name, file, extra, budget, kind in cases():
        if a.filter not in name:
            continue
        if kind == "resize":
            file = resize_input(name.split("/")[2])
        digest = sha(file)
        if kind == "throughput":
            count = instructions(file, extra)
        else:
            count = instructions(file, ["resizes", "20", "80", "50"] + extra) - instructions(file, ["resizes", "0", "80", "50"] + extra)
        tol = a.tolerance if a.tolerance is not None else (1.0 if kind == "throughput" else 3.0)
        note = ""
        if name in base and not a.update:
            old_digest, old = base[name]
            if old_digest != digest:
                failed.append(name)
                note = f"  INPUT CHANGED ({old_digest} recorded, {digest} now)"
            else:
                d = 100.0 * (count - old) / old
                note = f"  {d:+.2f}% of {old / 1e6:,.1f} M"
                if d > tol:
                    failed.append(name)
                    note += f"  OVER (+{tol:g}% allowed)"
                elif d < -tol:
                    lower.append(name)
                    note += "  lower: --update to keep it"
        elif name not in base and not a.update:
            note = "  no record"
        line = f"{name:<46} {count / 1e6:>10,.1f} M{note}"
        if budget is not None and not a.no_times:
            lo, hi = least_time(file)
            line += f"   {lo}-{hi} ms (budget {budget})"
            if lo > budget:
                failed.append(name + " (time)")
                line += "  OVER BUDGET"
        print(line, flush=True)
        new[name] = (digest, count)

    if a.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        with open(BASELINE, "w") as f:
            f.write("# harness/perf.py's record: case, input SHA-256 (16), instructions:u\n")
            for name in sorted(new):
                f.write(f"{name}\t{new[name][0]}\t{new[name][1]}\n")
        print(f"recorded {BASELINE.relative_to(ROOT)}")
    if lower:
        print(f"{len(lower)} lower than recorded: {', '.join(lower)}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        sys.exit(1)
    print("all within the record" + ("" if a.no_times else " and the budgets"))


if __name__ == "__main__":
    main()

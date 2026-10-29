#!/usr/bin/env python3
"""Runs esctest2 against the core and against libghostty-vt (docs/vt-core.md §VC10).

esctest2 runs in the terminal it tests: it writes sequences and reads the
terminal's replies, mostly DECRQCRA checksums of the screen. Here it runs on a
pty's slave, and the terminal is a program given the master as its standard
input and output: `harness/esctest/core-pty` for the core, and
`harness/esctest/ghostty-pty` for the oracle. esctest is told to expect xterm,
as Ghostty's own runner tells it (vendor/ghostty/test/esctest).

Each side's tests that pass are recorded in `corpus/esctest/<side>.txt`. A run
fails when a test recorded there no longer passes; one that newly passes is
listed, and `--update` records it.

  ./harness/esctest/build.sh && ./harness/esctest/build-oracle.sh
  ./harness/esctest.py                     # both sides, every test
  ./harness/esctest.py --side core -- --include=DECSTBM
  ./harness/esctest.py --update            # record what passes now
  ./harness/esctest.py --diff              # tests Ghostty passes and the core does not

Each side's whole log is in .harness-work/esctest/<side>.log.
"""

import argparse
import fcntl
import os
import re
import struct
import subprocess
import sys
import termios
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESCTEST = os.path.join(ROOT, "vendor", "esctest2", "esctest")
CORPUS = os.path.join(ROOT, "corpus", "esctest")
WORK = os.path.join(ROOT, ".harness-work", "esctest")
PROGRAMS = {
    "core": os.path.join(ROOT, "harness", "esctest", "core-pty"),
    "ghostty": os.path.join(ROOT, "harness", "esctest", "ghostty-pty"),
}
# What Ghostty's runner passes, so that the two runs can be compared.
ESCTEST_ARGS = [
    "--expected-terminal=xterm",
    "--xterm-checksum=411",
    "--xterm-reverse-wrap=411",
    "--timeout=0.2",
    "--no-print-logs",
]
COLS, ROWS = 80, 25


def run_side(side, extra):
    """Runs esctest with `side`'s program as its terminal. Answers the log."""
    os.makedirs(WORK, exist_ok=True)
    log = os.path.join(WORK, side + ".log")
    if os.path.exists(log):
        os.unlink(log)
    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
    # The terminal is capped as every built program's run is in geng-lang.
    term = subprocess.Popen(
        ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G",
         PROGRAMS[side], str(COLS), str(ROWS)],
        stdin=master, stdout=master, stderr=subprocess.DEVNULL)
    test = subprocess.Popen(
        [sys.executable, "esctest.py"] + ESCTEST_ARGS + ["--logfile=" + log] + extra,
        cwd=ESCTEST, stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True)
    # Only the two children hold the ends now, so the master's read fails once
    # esctest has gone and the terminal ends.
    os.close(master)
    os.close(slave)
    started = time.monotonic()
    code = test.wait()
    try:
        term.wait(timeout=10)
    except subprocess.TimeoutExpired:
        term.kill()
        term.wait()
    seconds = time.monotonic() - started
    if not os.path.exists(log):
        sys.exit("%s: esctest wrote no log (exit %d)" % (side, code))
    with open(log, errors="replace") as f:
        text = f.read()
    if term.returncode not in (0, None):
        print("%s: the terminal ended with %d" % (side, term.returncode))
    return text, seconds


def outcomes(text):
    """Each test's name and how it ended: pass, fail, known (a bug esctest
    records for xterm) or skip."""
    found = {}
    name = None
    for line in text.splitlines():
        m = re.match(r"Run test: (\S+)", line)
        if m:
            name = m.group(1)
            continue
        if name is None:
            continue
        if line == "Passed.":
            found[name] = "pass"
        elif line.startswith("*** TEST ") and "FAILED" in line:
            found[name] = "fail"
        elif line.startswith("Fails as expected"):
            found[name] = "known"
        elif line.startswith("Skipped because"):
            found[name] = "skip"
        else:
            continue
        name = None
    return found


def recorded(side):
    path = os.path.join(CORPUS, side + ".txt")
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {l.strip() for l in f if l.strip() and not l.startswith("#")}


def record(side, passing):
    os.makedirs(CORPUS, exist_ok=True)
    with open(os.path.join(CORPUS, side + ".txt"), "w") as f:
        f.write("# esctest2 tests that pass on %s; harness/esctest.py --update writes it\n" % side)
        for n in sorted(passing):
            f.write(n + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--side", choices=["core", "ghostty", "both"], default="both")
    p.add_argument("--update", action="store_true", help="record what passes now")
    p.add_argument("--diff", action="store_true",
                   help="list the tests Ghostty passes and the core does not")
    p.add_argument("extra", nargs="*", help="esctest's own arguments, after --")
    a = p.parse_args()
    sides = ["core", "ghostty"] if a.side == "both" else [a.side]
    partial = any(x.startswith("--include") for x in a.extra)
    ok = True
    results = {}
    for side in sides:
        if not os.access(PROGRAMS[side], os.X_OK):
            sys.exit("%s is not built" % PROGRAMS[side])
        text, seconds = run_side(side, a.extra)
        found = outcomes(text)
        results[side] = found
        counts = {k: sum(1 for v in found.values() if v == k)
                  for k in ("pass", "fail", "known", "skip")}
        print("%-8s %4d passed, %4d failed, %3d known bugs, %3d skipped  (%d tests, %.0f s)" % (
            side, counts["pass"], counts["fail"], counts["known"], counts["skip"],
            len(found), seconds))
        passing = {n for n, v in found.items() if v == "pass"}
        before = recorded(side)
        ran = set(found)
        lost = sorted((before & ran) - passing)
        gained = sorted(passing - before)
        for n in lost:
            print("  no longer passes: " + n)
        for n in gained:
            print("  newly passes:     " + n)
        if a.update:
            if partial:
                passing = (before - ran) | passing
            record(side, passing)
        elif lost:
            ok = False
    if a.diff and "core" in results and "ghostty" in results:
        g = {n for n, v in results["ghostty"].items() if v == "pass"}
        c = {n for n, v in results["core"].items() if v == "pass"}
        print("Ghostty passes, the core does not (%d):" % len(g - c))
        for n in sorted(g - c):
            print("  " + n)
        print("The core passes, Ghostty does not (%d):" % len(c - g))
        for n in sorted(c - g):
            print("  " + n)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

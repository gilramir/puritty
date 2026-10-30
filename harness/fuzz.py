#!/usr/bin/env python3
"""Runs the core's fuzzer and records each run (docs/vt-core.md §VC11).

`harness/fuzz/vt-fuzz` is libFuzzer over the core: a crash, or a dump that
differs when the input is fed in pieces, is a finding (`fuzz/fuzz.c`). Its
corpus grows in .harness-work/fuzz/corpus across runs, seeded from every
replay case; a finding is written to .harness-work/fuzz/ and stops its job.
Each run is a row of corpus/fuzz/runs.tsv: when, the commit, how long, how
many jobs, how many inputs, the coverage, and what it found.

  ./harness/fuzz/build.sh
  ./harness/fuzz.py --minutes 10                # one job
  ./harness/fuzz.py --hours 4 --jobs 8          # the exit's run
  ./harness/fuzz.py --show FILE                 # both dumps of a finding
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import replay  # noqa: E402

FUZZ = ROOT / "harness" / "fuzz" / "vt-fuzz"
DICT = ROOT / "harness" / "fuzz" / "vt.dict"
WORK = ROOT / ".harness-work" / "fuzz"
RUNS = ROOT / "corpus" / "fuzz" / "runs.tsv"
# fuzz.c's tables: an input's first two bytes index them.
COLS = [1, 2, 3, 4, 5, 8, 10, 13, 20, 40, 80, 132]
ROWS = [1, 2, 3, 4, 5, 8, 10, 24, 25, 50]


def nearest(table, n):
    return min(range(len(table)), key=lambda i: abs(table[i] - n))


def seeds(into):
    """Every replay case as an input: its size where fuzz.c's tables have
    it, the nearest otherwise, its resizes as 0xFE and the two indexes
    (`Fuzz.dump`, §VC14), and reads of 1 and of 7."""
    into.mkdir(parents=True, exist_ok=True)
    n = 0
    for case in sorted(replay.CORPUS.iterdir()):
        f = case / "case.txt"
        if not f.exists():
            continue
        cols, rows, data, resizes = replay.parse_resizing(f.read_text())
        # A 0xFE of the case's own would read as a resize; none has one.
        out, at = bytearray(), 0
        for off, c, r in resizes:
            out += data[at:off] + bytes([0xFE, nearest(COLS, c), nearest(ROWS, r)])
            at = off
        out += data[at:]
        for chunk in (0, 6):
            (into / f"{case.name}-{chunk + 1}").write_bytes(
                bytes([nearest(COLS, cols), nearest(ROWS, rows), chunk]) + bytes(out))
            n += 1
    return n


def commit():
    out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "vt"],
                           capture_output=True, text=True).stdout.strip()
    return out.stdout.strip() + ("+" if dirty else "")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--minutes", type=float, default=0)
    p.add_argument("--hours", type=float, default=0)
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--show", metavar="FILE", help="print both dumps of one input")
    p.add_argument("--no-record", action="store_true", help="do not add a row to runs.tsv")
    a = p.parse_args()
    if not os.access(FUZZ, os.X_OK):
        sys.exit(f"{FUZZ} is not built: ./harness/fuzz/build.sh")
    if a.show:
        env = dict(os.environ, VTFUZZ_PRINT="1")
        sys.exit(subprocess.run([str(FUZZ), a.show], env=env).returncode)
    seconds = int(a.hours * 3600 + a.minutes * 60) or 60
    corpus = WORK / "corpus"
    seed_dir = WORK / "seeds"
    shutil.rmtree(seed_dir, ignore_errors=True)
    n = seeds(seed_dir)
    corpus.mkdir(parents=True, exist_ok=True)
    logs = WORK / "logs"
    shutil.rmtree(logs, ignore_errors=True)
    logs.mkdir(parents=True)
    started = datetime.datetime.now().astimezone()
    print(f"{a.jobs} job(s) for {seconds} s, {n} seeds, corpus {len(list(corpus.iterdir()))} inputs")
    # Each job is capped as every built program's run is in geng-lang.
    cmd = ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={3 * a.jobs + 2}G",
           str(FUZZ), f"-max_total_time={seconds}", "-rss_limit_mb=2048", "-timeout=10", "-max_len=4096",
           f"-dict={DICT}", f"-artifact_prefix={WORK}/", "-print_final_stats=1",
           f"-jobs={a.jobs}", f"-workers={a.jobs}", str(corpus), str(seed_dir)]
    t0 = time.monotonic()
    subprocess.run(cmd, cwd=logs, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    took = time.monotonic() - t0
    execs, cov, found = 0, 0, []
    for log in sorted(logs.glob("fuzz-*.log")):
        text = log.read_text(errors="replace")
        m = re.findall(r"stat::number_of_executed_units:\s*(\d+)", text)
        execs += int(m[-1]) if m else 0
        c = re.findall(r"cov: (\d+)", text)
        cov = max(cov, int(c[-1]) if c else 0)
        for f in re.findall(r"Test unit written to (\S+)", text):
            found.append(Path(f).name)
            why = re.findall(r"vt-fuzz: (.*)", text)
            print(f"{log.name}: {why[-1] if why else 'a crash'}: {f}")
    print(f"{execs} inputs in {took:.0f} s, coverage {cov}, {len(found)} finding(s)")
    if not a.no_record:
        RUNS.parent.mkdir(parents=True, exist_ok=True)
        if not RUNS.exists():
            RUNS.write_text("# when\tcommit\tseconds\tjobs\tinputs\tcoverage\tfindings\n")
        with RUNS.open("a") as f:
            f.write("\t".join([started.strftime("%Y-%m-%dT%H:%M%z"), commit(), str(round(took)),
                               str(a.jobs), str(execs), str(cov), ",".join(found) or "none"]) + "\n")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()

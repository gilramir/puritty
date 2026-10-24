#!/usr/bin/env python3
"""G7: runs the gcpause probe over a set of heaps and reports every pause.

    ./run.py                       # the default matrix
    ./run.py --panes 4 --rows packed --runs 3
    ./run.py --env GENG_NURSERY=16777216   # a variant of the runtime's settings

Each run sets GENG_GC_PAUSES (geng-lang m4-visiterm.md §VA7) and keeps the
pauses whose start falls inside the probe's `cat`. A minor collection's time
includes any full one Boehm ran inside it; a full one outside a minor is its
own pause. Each run is capped with systemd-run's MemoryMax.

patches/ holds two experiments on geng-lang's runtime, applied with `git apply`
in geng-lang, then `./harness/native.py --embed` and `devbox run build` in the
fork: census.patch (GENG_HEAP_CENSUS=n lists Boehm's reachable objects by size
at the nth full collection, and GENG_CENSUS_BEFORE=line the chain that holds
the oldest row reachable), and options.patch (GENG_MARKERS=n,
GENG_ATOMIC_BYTES=1), §VA7.2 and §VA7.4.
"""

import argparse
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def pct(sorted_values, p):
    if not sorted_values:
        return 0
    return sorted_values[min(len(sorted_values) - 1, (len(sorted_values) - 1) * p // 100)]


def run_once(panes, rows, back, scrollback, cat_mb, extra_env):
    with tempfile.TemporaryDirectory() as work:
        log = pathlib.Path(work) / "pauses"
        env = dict(os.environ, PANES=str(panes), ROWS=rows, BACK=back, SCROLLBACK=str(scrollback), CAT_MB=str(cat_mb), GENG_GC_PAUSES=str(log))
        env.update(extra_env)
        out = subprocess.run(
            ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=12G", "/usr/bin/time", "-f", "rss_kb %M", str(HERE / "probe")],
            env=env, capture_output=True, text=True, check=True,
        )
        facts = {}
        for line in (out.stdout + out.stderr).splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].lstrip("-").isdigit():
                facts[parts[0]] = int(parts[1])
            if line.startswith("reads"):
                facts["reads_line"] = line
            if line.startswith("panes"):
                facts["head"] = line
        start_us, end_us = facts["cat_start_ms"] * 1000, facts["cat_end_ms"] * 1000
        pauses = []
        for line in log.read_text().splitlines():
            if line.startswith("#"):
                continue
            kind, nested, start, ns, mark_ns, size = line.split()
            pauses.append((kind, int(nested), int(start), int(ns), int(mark_ns), int(size)))
    inside = [p for p in pauses if start_us <= p[2] <= end_us]
    return facts, pauses, inside


def report(facts, pauses, inside):
    minors = sorted(p[3] for p in inside if p[0] == "m")
    fulls = [p for p in inside if p[0] == "f"]
    # The program sees a minor (with any full inside it) or a full on its own.
    seen = sorted([p[3] for p in inside if p[0] == "m"] + [p[3] for p in fulls if not p[1]])
    ms = lambda ns: f"{ns / 1e6:.2f}"
    cat_s = (facts["cat_end_ms"] - facts["cat_start_ms"]) / 1000
    print(facts["head"])
    print(f"  cat {cat_s:.2f} s ({facts['cat_lines'] * 103 / 1e6 / cat_s:.0f} MB/s), fill {facts['fill_ms']} ms, peak RSS {facts['rss_kb'] // 1024} MB; {facts['reads_line']}")
    print(f"  pauses in the cat: {len(seen)}, p50 {ms(pct(seen, 50))} ms, p99 {ms(pct(seen, 99))}, max {ms(seen[-1] if seen else 0)}, total {ms(sum(seen))} ms ({sum(seen) / 1e9 / cat_s * 100:.0f}% of the cat)")
    print(f"  minors {len(minors)}: p50 {ms(pct(minors, 50))} p99 {ms(pct(minors, 99))} max {ms(minors[-1] if minors else 0)}")
    for p in fulls:
        print(f"  full{' (in a minor)' if p[1] else ''}: {ms(p[3])} ms, mark {ms(p[4])}, heap {p[5] / 2**20:.0f} MB")
    every_full = [p for p in pauses if p[0] == "f"]
    if every_full:
        worst = max(every_full, key=lambda p: p[3])
        print(f"  whole run: {len(every_full)} full, the longest {ms(worst[3])} ms (mark {ms(worst[4])}) at heap {worst[5] / 2**20:.0f} MB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panes", type=int, action="append")
    ap.add_argument("--rows", action="append", choices=["packed", "cells", "page"])
    ap.add_argument("--back", action="append", choices=["queue", "ring"])
    ap.add_argument("--scrollback", type=int, default=100000)
    ap.add_argument("--cat-mb", type=int, default=200)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--env", action="append", default=[], help="NAME=VALUE for the probe's environment")
    args = ap.parse_args()
    extra = dict(e.split("=", 1) for e in args.env)
    for rows in args.rows or ["packed", "cells"]:
        for back in args.back or ["queue", "ring"]:
            for panes in args.panes or [1, 4, 8]:
                for _ in range(args.runs):
                    report(*run_once(panes, rows, back, args.scrollback, args.cat_mb, extra))
                    sys.stdout.flush()


if __name__ == "__main__":
    main()

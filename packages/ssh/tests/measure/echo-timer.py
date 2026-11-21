#!/usr/bin/env python3
"""Run on the host as `ssh-tests session --echo`'s command (docs/sftp.md
FT12, FT17): after DELAY seconds, writes one byte N times, GAP seconds
apart, and times each until the client sends it back; the times go to OUT,
since standard output is what is echoed.

    echo-timer.py N OUT GAP DELAY
"""
import os, statistics, sys, time

n, out, gap, delay = int(sys.argv[1]), sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
time.sleep(delay)
v = []
for i in range(n):
    t = time.perf_counter()
    os.write(1, b"x")
    os.read(0, 1)
    v.append((time.perf_counter() - t) * 1000)
    time.sleep(gap)
v.sort()
open(out, "w").write(f"median {statistics.median(v):.1f} ms  p90 {v[int(len(v) * .9)]:.1f}  max {v[-1]:.1f}  (n={n}, {gap} s apart)\n")

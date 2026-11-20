#!/usr/bin/env python3
"""Run on the host as a side channel's command (docs/sftp.md FT12, FT17):
reads standard input to its end and says how many bytes came and how fast,
from the first byte on."""
import sys, time

r = sys.stdin.buffer
first = r.read(1)
t = time.perf_counter()
n = len(first)
while True:
    b = r.read(1 << 20)
    if not b:
        break
    n += len(b)
dt = time.perf_counter() - t
print(f"{n} bytes, {n / dt / 1e6:.1f} MB/s")

# 3,000 lines 0.7 ms apart: reads and a 1 ms timer finishing together, for
# `x11 stress` (docs/phase2-window.md §12).
import sys, time
for i in range(3000):
    sys.stdout.write(f"drip {i:05d} " + "x" * 40 + "\n"); sys.stdout.flush(); time.sleep(0.0007)

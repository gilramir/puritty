# Two lines 5 ms apart, then 300 ms of quiet, twenty times: the shape that
# leaves a frame undrawn under a loop that draws only on reads
# (docs/phase2-window.md §12).
import sys, time
for i in range(20):
    sys.stdout.write(f"burst {i} first\r\n"); sys.stdout.flush(); time.sleep(0.005)
    sys.stdout.write(f"burst {i} second\r\n"); sys.stdout.flush(); time.sleep(0.3)

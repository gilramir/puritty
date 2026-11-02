"""The GC survey's summary (docs/phase2-window.md §15): GENG_GC_PAUSES's
file, the collections that started after the probe's window opened (its
report's `start`, CLOCK_MONOTONIC ms, as the file's start is in us).

usage: pauses.py PAUSES START_MS"""
import sys

rows = []
for line in open(sys.argv[1]):
    if line.startswith("#"):
        continue
    kind, nested, start, ns, mark, nbytes = line.split()
    if int(start) >= int(sys.argv[2]) * 1000:
        rows.append((kind, int(nested), int(ns), int(mark), int(nbytes)))
minor = sorted(ns for k, n, ns, _, _ in rows if k == "m")
full = [r for r in rows if r[0] == "f"]
def pct(xs, p):
    return xs[min(len(xs) - 1, int(len(xs) * p))] / 1e6 if xs else 0
longest = max((ns for _, _, ns, _, _ in full), default=0)
mark = max((m for _, _, ns, m, _ in full if ns == longest), default=0)
heap = max((b for k, _, _, _, b in full), default=0)
print(f"minor {len(minor)}: median {pct(minor, .5):.3f} p99 {pct(minor, .99):.3f} max {pct(minor, 1):.3f} ms; "
      f"full {len(full)}: longest {longest / 1e6:.2f} ms (marking {mark / 1e6:.2f}), heap after up to {heap / 1e6:.0f} MB")

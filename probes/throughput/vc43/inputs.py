#!/usr/bin/env python3
"""vt-core.md §VC43: vte-scrolling taken apart into one kind of work each.
Writes DIR/{empty,cr,lf,crlf,ycr,full}.txt; full.txt is vte-scrolling."""
import sys
from pathlib import Path

n = 2666667
d = Path(sys.argv[1])
d.mkdir(parents=True, exist_ok=True)
for name, unit in [("empty", b""), ("cr", b"\r"), ("lf", b"\n"), ("crlf", b"\r\n"), ("ycr", b"y\r"), ("full", b"y\r\n")]:
    (d / f"{name}.txt").write_bytes(unit * n)

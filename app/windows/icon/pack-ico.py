#!/usr/bin/env python3
"""Packs png/<size>.png into puritty.ico, each size as a PNG entry (which
Windows reads from Vista on)."""
import struct
from pathlib import Path

here = Path(__file__).resolve().parent
sizes = [16, 20, 24, 32, 40, 48, 64, 256]
images = [(s, (here / "png" / f"{s}.png").read_bytes()) for s in sizes]
out = bytearray(struct.pack("<HHH", 0, 1, len(images)))
offset = 6 + 16 * len(images)
for s, data in images:
    out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
for _, data in images:
    out += data
(here / "puritty.ico").write_bytes(out)
print(f"puritty.ico: {len(images)} sizes, {len(out)} bytes")

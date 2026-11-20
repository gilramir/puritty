#!/usr/bin/env python3
"""The X screen as a PNG, by python-xlib: shot.py OUT.png"""
import struct, sys, zlib
from Xlib import X, display

d = display.Display()
r = d.screen().root
g = r.get_geometry()
data = r.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xFFFFFFFF).data
rows = bytearray()
for y in range(g.height):
    rows.append(0)
    line = data[y * g.width * 4:(y + 1) * g.width * 4]
    for i in range(0, len(line), 4):
        rows += bytes((line[i + 2], line[i + 1], line[i]))


def chunk(t, b):
    return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)


open(sys.argv[1], "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", g.width, g.height, 8, 2, 0, 0, 0))
                              + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))

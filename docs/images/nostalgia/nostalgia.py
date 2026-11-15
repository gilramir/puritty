#!/usr/bin/env python3
"""The home page's two phosphor pictures: `cat chrget.asm` in
green-screen's and amber-screen's colors (app/src/Palettes.geng), as cases
for docs/images/render.py.

chrget.asm is CHRGET, from Microsoft's BASIC for the 6502, version 1.1
(1978), m6502.asm lines 948 to 976 with its tabs expanded; Copyright (c)
Microsoft Corporation, MIT License (LICENSE-BASIC-M6502.txt,
github.com/microsoft/BASIC-M6502).

    nostalgia.py          writes green-screen.case.txt and amber-screen.case.txt
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMES = {
    # foreground on black, as each scheme has it
    "green-screen": "33/ff/33",
    "amber-screen": "ff/b0/00",
}

listing = (HERE / "chrget.asm").read_text().splitlines()
cols = max(len(line) for line in listing) + 3
rows = len(listing) + 2


def escaped(text):
    return text.replace("\\", "\\\\")


for name, fg in SCHEMES.items():
    body = (
        "\\e]10;rgb:" + fg + "\\e\\\\" + "\\e]11;rgb:00/00/00\\e\\\\"
        + "$ cat chrget.asm\\r\\n"
        + "".join(escaped(line) + "\\r\\n" for line in listing)
        + "$ "
    )
    (HERE / (name + ".case.txt")).write_text(f"size {cols}x{rows} points=13\n{body}\n")
    print(name, f"{cols}x{rows}")

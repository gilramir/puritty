#!/usr/bin/env python3
"""Writes vt/tests/src/JpegCases.geng: small JPEGs made by Pillow, each with
the pixels libjpeg (through Pillow) decodes it to, which Vt.Jpeg is held to
within a tolerance (docs/images-iterm.md IT4). Run again only to change the
cases; the file it writes is checked in.

    python3 vt/tests/gen-jpeg.py
"""

import base64
import io
import math
from pathlib import Path

from PIL import Image, ImageOps

OUT = Path(__file__).resolve().parent / "src" / "JpegCases.geng"


def picture(w, h, mode="RGB"):
    im = Image.new(mode, (w, h))
    for y in range(h):
        for x in range(w):
            if mode == "L":
                im.putpixel((x, y), int(255 * x / max(1, w - 1)))
            else:
                r = int(127 + 120 * math.sin(x / 3.0))
                g = int(255 * y / max(1, h - 1))
                b = int(255 * (x + y) / max(1, w + h - 2))
                im.putpixel((x, y), (r, g, b))
    return im


# name, picture, Pillow's save options
CASES = [
    ("rgb 4:4:4, quality 95", picture(16, 16), dict(quality=95, subsampling=0)),
    ("rgb 4:2:0, quality 90", picture(32, 16), dict(quality=90, subsampling=2)),
    ("rgb 4:2:2, 13 by 7, edges not whole blocks", picture(13, 7), dict(quality=90, subsampling=1)),
    ("grey", picture(16, 16, "L"), dict(quality=90)),
    ("restart markers every block", picture(32, 32), dict(quality=85, subsampling=2, restart_marker_blocks=1)),
    ("optimized Huffman tables", picture(24, 24), dict(quality=80, subsampling=0, optimize=True)),
]


def exif(orientation):
    e = Image.Exif()
    e[0x0112] = orientation
    return e.tobytes()


# a camera's orientation (IT5): the picture turned as the tag says, which
# Pillow's exif_transpose does as a browser does
CASES += [
    ("Exif orientation %d" % o, picture(16, 8), dict(quality=95, subsampling=0, exif=exif(o)))
    for o in (2, 3, 6, 8)
]

# progressive (IT6): the DC and AC bands in scans of their own, refined a
# bit at a time
CASES += [
    ("progressive 4:2:0", picture(32, 24), dict(quality=90, subsampling=2, progressive=True)),
    ("progressive 4:4:4", picture(24, 16), dict(quality=95, subsampling=0, progressive=True)),
    ("progressive grey", picture(16, 16, "L"), dict(quality=85, progressive=True)),
    ("progressive, a restart marker every block", picture(24, 24), dict(quality=85, subsampling=2, progressive=True, restart_marker_blocks=1)),
]


def main():
    lines = [
        "module JpegCases exposing (Case, cases)",
        "",
        "{-| Written by vt/tests/gen-jpeg.py: each JPEG Pillow made, as base64,",
        "and the RGB libjpeg decodes it to. -}",
        "",
        "",
        "type alias Case =",
        "    { name : String, jpeg : String, width : Int, height : Int, rgb : Array Int }",
        "",
        "",
        "cases : Array Case",
        "cases =",
    ]
    items = []
    for name, im, opts in CASES:
        b = io.BytesIO()
        im.save(b, "JPEG", **opts)
        data = b.getvalue()
        back = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        rgb = list(back.tobytes())
        items.append(
            "{ name = %s, jpeg = %s, width = %d, height = %d, rgb = [ %s ] }"
            % ('"' + name + '"', '"' + base64.b64encode(data).decode() + '"', back.width, back.height, ", ".join(map(str, rgb)))
        )
    lines.append("    [ " + "\n    , ".join(items))
    lines.append("    ]")
    lines.append("")
    OUT.write_text("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Writes vt/tests/src/GifCases.geng: small GIFs made by Pillow, each with
the RGBA of its first frame as Pillow decodes it, which Vt.Gif is held to
exactly (docs/images-iterm.md IT4). Run again only to change the cases;
the file it writes is checked in.

    python3 vt/tests/gen-gif.py
"""

import base64
import io
import math
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent / "src" / "GifCases.geng"


def picture(w, h):
    im = Image.new("RGB", (w, h))
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), (int(127 + 120 * math.sin(x / 2.0)), int(255 * y / max(1, h - 1)), (x * 37 + y * 11) % 256))
    return im


def four(w, h):
    im = Image.new("P", (w, h))
    im.putpalette([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0])
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), (x // 3 + y) % 4)
    return im


def gif(im, **opts):
    b = io.BytesIO()
    im.save(b, "GIF", **opts)
    return b.getvalue()


def animated():
    a = picture(12, 10).quantize(64)
    b = Image.new("RGB", (12, 10), (0, 0, 255)).quantize(64)
    out = io.BytesIO()
    a.save(out, "GIF", save_all=True, append_images=[b], duration=100, loop=0)
    return out.getvalue()


CASES = [
    ("256 colours", gif(picture(16, 12).quantize(256), interlace=False)),
    ("4 colours, LZW codes from 3 bits", gif(four(20, 9), interlace=False)),
    ("interlaced", gif(picture(13, 11).quantize(200), interlace=True)),
    ("a transparent index", gif(four(10, 10), transparency=2, interlace=False)),
    ("an animation: its first frame", animated()),
]


def main():
    lines = [
        "module GifCases exposing (Case, cases)",
        "",
        "{-| Written by vt/tests/gen-gif.py: each GIF Pillow made, as base64,",
        "and the RGBA of its first frame as Pillow decodes it. -}",
        "",
        "",
        "type alias Case =",
        "    { name : String, gif : String, width : Int, height : Int, rgba : Array Int }",
        "",
        "",
        "cases : Array Case",
        "cases =",
    ]
    items = []
    for name, data in CASES:
        im = Image.open(io.BytesIO(data))
        im.seek(0)
        rgba = im.convert("RGBA")
        px = []
        for r, g, b, a in rgba.getdata():
            # a clear pixel's colour is not drawn: held as 0, as Vt.Gif writes it
            px += [r, g, b, a] if a else [0, 0, 0, 0]
        items.append(
            "{ name = %s, gif = %s, width = %d, height = %d, rgba = [ %s ] }"
            % ('"' + name + '"', '"' + base64.b64encode(data).decode() + '"', im.width, im.height, ", ".join(map(str, px)))
        )
    lines.append("    [ " + "\n    , ".join(items))
    lines.append("    ]")
    lines.append("")
    OUT.write_text("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()

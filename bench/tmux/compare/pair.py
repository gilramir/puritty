#!/usr/bin/env python3
"""Render each NAME.tmux.ans (capture-pane -p -e of the outer tmux) to a
picture on puritty's 9x17 grid and put it above NAME.puritty.png:
NAME.pair.png. Usage: pair.py DIR [prefix...]"""

import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CW, CH, COLS, ROWS = 9, 17, 100, 30
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
FG, BG = (197, 200, 198), (29, 31, 33)
BASE16 = [(0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0), (0, 0, 238), (205, 0, 205), (0, 205, 205),
          (229, 229, 229), (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0), (92, 92, 255),
          (255, 0, 255), (0, 255, 255), (255, 255, 255)]


def c256(n):
    if n < 16:
        return BASE16[n]
    if n < 232:
        n -= 16
        v = [0, 95, 135, 175, 215, 255]
        return (v[n // 36], v[n // 6 % 6], v[n % 6])
    g = 8 + (n - 232) * 10
    return (g, g, g)


def render(text):
    im = Image.new("RGB", (COLS * CW, ROWS * CH), BG)
    d = ImageDraw.Draw(im)
    for r, line in enumerate(text.split("\n")[:ROWS]):
        st = dict(fg=None, bg=None, rev=False, ul=False, bold=False, dim=False)
        col = 0
        for part in re.split(r"(\x1b\[[0-9;:]*m)", line):
            if part.startswith("\x1b["):
                ps = [int(x) if x else 0 for x in re.split(r"[;:]", part[2:-1])] or [0]
                i = 0
                while i < len(ps):
                    p = ps[i]
                    if p == 0:
                        st = dict(fg=None, bg=None, rev=False, ul=False, bold=False, dim=False)
                    elif p == 1: st["bold"] = True
                    elif p == 2: st["dim"] = True
                    elif p == 22: st["bold"] = st["dim"] = False
                    elif p == 4: st["ul"] = True
                    elif p == 24: st["ul"] = False
                    elif p == 7: st["rev"] = True
                    elif p == 27: st["rev"] = False
                    elif 30 <= p <= 37: st["fg"] = BASE16[p - 30]
                    elif 90 <= p <= 97: st["fg"] = BASE16[p - 82]
                    elif 40 <= p <= 47: st["bg"] = BASE16[p - 40]
                    elif 100 <= p <= 107: st["bg"] = BASE16[p - 92]
                    elif p == 39: st["fg"] = None
                    elif p == 49: st["bg"] = None
                    elif p in (38, 48) and i + 1 < len(ps):
                        k = "fg" if p == 38 else "bg"
                        if ps[i + 1] == 5:
                            st[k] = c256(ps[i + 2]); i += 2
                        elif ps[i + 1] == 2:
                            st[k] = tuple(ps[i + 2:i + 5]); i += 4
                    i += 1
                continue
            for ch in part:
                fg, bg = st["fg"] or FG, st["bg"] or BG
                if st["rev"]:
                    fg, bg = bg, fg
                if st["dim"]:
                    fg = tuple(x // 2 for x in fg)
                w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
                x, y = col * CW, r * CH
                d.rectangle([x, y, x + w * CW - 1, y + CH - 1], fill=bg)
                if ch != " ":
                    d.text((x, y + 1), ch, font=FONT, fill=fg)
                if st["ul"]:
                    d.line([x, y + CH - 2, x + w * CW - 1, y + CH - 2], fill=fg)
                col += w
    return im


def main():
    out = Path(sys.argv[1])
    pre = sys.argv[2:]
    for ans in sorted(out.glob("*.tmux.ans")):
        stem = ans.name[:-len(".tmux.ans")]
        if pre and not any(stem.startswith(p) for p in pre):
            continue
        top = render(ans.read_text())
        png = out / f"{stem}.puritty.png"
        bot = Image.open(png).convert("RGB") if png.exists() else Image.new("RGB", top.size, (80, 0, 0))
        im = Image.new("RGB", (max(top.width, bot.width), top.height + bot.height + 6), (255, 0, 255))
        im.paste(top, (0, 0))
        im.paste(bot, (0, top.height + 6))
        im.save(out / f"{stem}.pair.png")


if __name__ == "__main__":
    main()

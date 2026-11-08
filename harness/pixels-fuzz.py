#!/usr/bin/env python3
"""The pixel gate's fuzzer (docs/renderer.md §R16, V40).

Makes random screens of italic, Thai, CJK, Devanagari, box drawing, Fira Code's
ligatures typed a character a frame, and Latin, moved about by cursor
moves, erases, insertions and deletions, scroll regions and reverse
index, with frames drawn at random points; draws each in its frames and in
one frame with harness/pixels/core-pixels; and demands the same pixels.
What a later frame draws over, it must draw again, and a word it draws must
be shaped as it is beside its neighbours.

A case that differs is minimized (a token at a time taken out while it
still differs) and left in .harness-work/pixels/fuzz/ as a case for
harness/pixels.py's format.

usage (from puritty's devbox, after harness/pixels/build.sh):
    harness/pixels-fuzz.py [N] [--seed S]
"""

import argparse
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("pixels", Path(__file__).resolve().parent / "pixels.py")
pixels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pixels)

OUT = pixels.WORK / "fuzz"
# The first fifteen are typed a character a frame as well as whole.
TYPED = ["-", ">", "=", "!", "<", "w", "-->", "=>", "!=", "===", "www", "<!--", "ष", "ि", "क्"]
WORDS = TYPED + [
    "\\e[3m-\\e[0m", "\\e[3mffff\\e[0m", "\\e[3mjjj\\e[0m", "\\e[1;3mWW\\e[0m", "กี้", "ญุ", "ฐุ", "ปั๊ม", "น้ำ",
    "漢字", "\\e[3m漢\\e[0m", "\\e[1m字\\e[0m", "ab", "xyz", " ", "  ", "\\e[7mrv\\e[0m", "क्षि",
    "┌─┐", "│", "╬═", "▀▄", "╭╯", "\\e[3m─┼\\e[0m",
]


def generate(r):
    cols, rows = r.randint(6, 16), r.randint(3, 6)
    parts = []
    for _ in range(r.randint(3, 30)):
        k = r.random()
        if k < 0.35:
            parts.append(r.choice(WORDS))
        elif k < 0.45:
            parts.append("\\F".join(r.choice(TYPED)))
        elif k < 0.6:
            parts.append(f"\\e[{r.randint(1, rows)};{r.randint(1, cols)}H")
        elif k < 0.67:
            parts.append("\\r\\n")
        elif k < 0.72:
            parts.append("\\eM")
        elif k < 0.77:
            top = r.randint(1, rows)
            parts.append(f"\\e[{top};{r.randint(top, rows)}r")
        elif k < 0.8:
            parts.append("\\e[r")
        elif k < 0.84:
            parts.append(r.choice(["\\e[K", "\\e[1K", "\\e[2K", "\\e[J"]))
        elif k < 0.88:
            parts.append(f"\\e[{r.randint(1, 3)}{r.choice('@PLMX')}")
        else:
            parts.append("\\F")
    font = ' font="Fira Code"' if r.random() < 0.5 else ""
    return f"size {cols}x{rows} lang=th{font}\n" + "".join(parts) + "\n"


class Runner:
    def __init__(self, display, conf):
        self.display, self.conf = display, conf

    def differs(self, text):
        case = OUT / "try.txt"
        case.write_text(text)
        if not pixels.parse_case(text)[2]:
            return False
        a, b = OUT / "frames.ppm", OUT / "once.ppm"
        pixels.draw(case, self.display, self.conf, a, False)
        pixels.draw(case, self.display, self.conf, b, False, whole=True)
        return pixels.read_ppm(a.read_bytes()) != pixels.read_ppm(b.read_bytes())

    def minimize(self, text):
        head, body = text.split("\n", 1)
        tokens = re.findall(r"\\e\[[0-9;]*[ -/]*[@-~]|\\e.|\\.|.", body.strip())
        shrunk = True
        while shrunk:
            shrunk = False
            for i in range(len(tokens)):
                fewer = tokens[:i] + tokens[i + 1:]
                if self.differs(head + "\n" + "".join(fewer) + "\n"):
                    tokens, shrunk = fewer, True
                    break
        return head + "\n" + "".join(tokens) + "\n"


def main():
    ap = argparse.ArgumentParser(description="The pixel gate's fuzzer.")
    ap.add_argument("n", nargs="?", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if not pixels.DRIVER.exists():
        sys.exit("pixels-fuzz.py: build harness/pixels/core-pixels first (harness/pixels/build.sh)")
    OUT.mkdir(parents=True, exist_ok=True)
    conf = pixels.write_fonts_conf()
    xvfb, display = pixels.start_xvfb()
    runner, found = Runner(display, conf), 0
    try:
        for n in range(a.n):
            seed = a.seed + n
            text = generate(random.Random(seed))
            if runner.differs(text):
                found += 1
                small = runner.minimize(text)
                (OUT / f"case-{seed}.txt").write_text(small)
                print(f"DIFF seed {seed}: {small.strip()}")
    finally:
        xvfb.kill()
        xvfb.wait()
    print(f"{a.n} cases, {found} drawn differently in frames")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()

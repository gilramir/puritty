#!/usr/bin/env python3
"""The fallback-cache gate (docs/renderer.md R22, the code review's X3): a
code point no loaded face has is asked of the platform once, however many
there are and however often they are drawn.

core-pixels draws 6,000 distinct code points from plane 15's Private Use
Area, which none of the pixel gate's fonts has, on a 160 by 50 screen,
four times with the screen cleared between: the text library's counts
must say at least 24,000 clusters (29,040 drawn when R22 was written) and
6,000 fontconfig queries. Before R22 the cache held 4,096 code points and
asked again for every one past that on every draw: 19,392 queries.

usage (from puritty's devbox, after harness/pixels/build.sh):
    harness/fallbacks.py
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402

DISTINCT, DRAWS = 6000, 4


def main():
    driver = Path(sys.argv[1]) if len(sys.argv) > 1 else pixels.DRIVER
    if not driver.exists():
        sys.exit("fallbacks.py: build harness/pixels/core-pixels first (harness/pixels/build.sh)")
    conf = pixels.write_fonts_conf()
    text = "".join(chr(0xF0000 + i) for i in range(DISTINCT)).encode()
    data, breaks = b"", []
    for _ in range(DRAWS):
        data += b"\x1b[H\x1b[2J" + text
        breaks.append(len(data))
    xvfb, display = pixels.start_xvfb()
    try:
        with tempfile.TemporaryDirectory() as d:
            case = Path(d) / "in.bin"
            case.write_bytes(data)
            env = dict(os.environ, DISPLAY=display, FONTCONFIG_FILE=str(conf), X11_STATS="1")
            p = subprocess.run(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=2G", str(driver), "160", "50",
                                str(case), str(Path(d) / "out.ppm"), "DejaVu Sans Mono", "11", "",
                                ",".join(map(str, breaks)), "focused"],
                               env=env, capture_output=True, text=True, timeout=120)
    finally:
        xvfb.kill()
    if p.returncode != 0:
        sys.exit(f"fallbacks.py: core-pixels exited {p.returncode}: {(p.stdout + p.stderr).strip()}")
    m = re.search(r"clusters (\d+) .*fontconfig queries (\d+)", p.stderr)
    if not m:
        sys.exit(f"fallbacks.py: no counts in {p.stderr!r}")
    clusters, queries = int(m.group(1)), int(m.group(2))
    if clusters < DISTINCT * DRAWS or queries != DISTINCT:
        sys.exit(f"fallbacks.py: {clusters} clusters and {queries} fontconfig queries, "
                 f"want at least {DISTINCT * DRAWS} and {DISTINCT}")
    print(f"{clusters} clusters drawn, {queries} fontconfig queries: each code point asked once")


if __name__ == "__main__":
    main()

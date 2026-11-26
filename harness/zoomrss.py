#!/usr/bin/env python3
"""The zoom memory gate (docs/renderer.md R31, the code review's X8): a
zoom step does not make each loaded face's glyph tables resident.

puritty runs on Xvfb with the system's fonts, its tab a program that
prints text in several scripts (Han, Hangul, Arabic, Thai, Devanagari,
symbols), so that fallback faces are loaded beside the primary ones.
Its resident memory (VmRSS) is read, Ctrl+= is pressed STEPS times, and
it is read again. Each face has 10 MB of tables a glyph index (2^20
advances and inks); before X8 every zoom step wrote zeros over all of
them, making them resident: the growth must stay under LIMIT_MB.

usage (from puritty's devbox, after app/build.sh):
    harness/zoomrss.py [PURITTY]
"""
import getpass
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its Xvfb)
import hosts  # noqa: E402  (its xdotool)

APP = ROOT / "app" / "puritty"
STEPS = 8
LIMIT_MB = 40
TEXT = "漢字 한글 العربية ภาษาไทย हिन्दी ∮∯⨌ ⌘⏚ ♞♛ ✓✗ ⅀ 𝔘𝔫𝔦\\n"


def rss_mb(pid):
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0


def faces_open(err):
    return sum(1 for l in err.read_text(errors="replace").splitlines() if l.startswith("face "))


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="zoomrss-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "show.sh").write_text(f"printf '{TEXT}'; sleep 60\n")
    (home / "config" / "puritty" / "config.toml").write_text(f'[program]\ncommand = ["sh", "{home / "show.sh"}"]\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser(), PURITTY_NO_XIM="1", X11_STATS="1")
    err = home / "stderr.txt"
    p = None
    try:
        p = subprocess.Popen([str(app)], env=env, stdout=subprocess.DEVNULL, stderr=open(err, "w"))
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(2)
        before = rss_mb(p.pid)
        for _ in range(STEPS):
            subprocess.run([xdo, "key", "ctrl+equal"], env=env, check=True)
            time.sleep(0.4)
        time.sleep(1)
        after = rss_mb(p.pid)
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    faces = faces_open(err)
    print(f"{faces} faces open; resident {before:.0f} MB, after {STEPS} zoom steps {after:.0f} MB "
          f"(+{after - before:.0f} MB, at most {LIMIT_MB})")
    if after - before > LIMIT_MB:
        sys.exit(f"zoomrss.py: zooming made {after - before:.0f} MB resident (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

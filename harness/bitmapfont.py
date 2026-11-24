#!/usr/bin/env python3
"""The bitmap-font gate (docs/renderer.md R23, the code review's X5): a
font FreeType cannot scale, only bitmap strikes (Terminus's .otb), opens a
window with cells, at a size no strike has, and the window survives a
resize.

puritty runs on Xvfb with a fontconfig file that sees the pixel gate's
fonts and Terminus, from the same pinned nixpkgs, with `[font] family =
"Terminus"` at 9 points (12 px at 96 dpi, the strike its 12 px file has),
11 (14.67 px, none) and 20; each window is resized by xdotool and must
still be running. Before R23, at 11 points the cells were 0 px high, the
window 662 by 10, and the resize divided by the cell's height: SIGFPE.

usage (from puritty's devbox, after app/build.sh):
    harness/bitmapfont.py [PURITTY]
"""
import getpass
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its Xvfb, fonts and pinned nixpkgs)
import hosts  # noqa: E402  (its xdotool)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "bitmapfont"
SIZES = [9, 11, 20]


def fonts_conf():
    terminus = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", f"{pixels.NIXPKGS}#terminus_font"],
                              capture_output=True, text=True, check=True).stdout.split()[0]
    base = pixels.write_fonts_conf().read_text()
    WORK.mkdir(parents=True, exist_ok=True)
    conf = WORK / "fonts.conf"
    conf.write_text(base.replace("<fontconfig>\n", f"<fontconfig>\n  <dir>{terminus}/share/fonts</dir>\n", 1)
                    .replace(str(pixels.WORK / "fc-cache"), str(WORK / "fc-cache")))
    return conf


def run_size(app, xdo, conf, size):
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="bitmapfont-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[font]\nfamily = "Terminus"\nsize = {size}\n\n[program]\ncommand = ["sleep", "30"]\n')
    env = dict(os.environ, DISPLAY=display, FONTCONFIG_FILE=str(conf), HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = subprocess.Popen([str(app)], env=env, stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
    try:
        time.sleep(3)
        tree = subprocess.run(["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True).stdout
        m = re.search(r'\("puritty" "Puritty"\)\s+(\d+)x(\d+)', tree)
        opened = (int(m.group(1)), int(m.group(2))) if m else None
        subprocess.run([xdo, "search", "--class", "puritty", "windowsize", "%@", "500", "300"], env=env)
        time.sleep(2)
        code = p.poll()
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
        xvfb.kill()
    print(f"     {size} points: opened {opened}, after a resize {'running' if code is None else f'exit {code}'}")
    if opened is None or code is not None or opened[1] < 20:
        return f"{size} points: opened {opened}, after a resize {'running' if code is None else f'exit {code}'} (the home is {home})"
    shutil.rmtree(home)
    return None


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    conf = fonts_conf()
    fails = [why for why in (run_size(app, xdo, conf, size) for size in SIZES) if why]
    for why in fails:
        print("FAIL " + why)
    print(f"{len(SIZES) - len(fails)} of {len(SIZES)} sizes pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

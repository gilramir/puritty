#!/usr/bin/env python3
"""The font name gate (the code review's X13): a family is looked up by
its name as it is, not parsed as fontconfig's name syntax.

puritty runs on Xvfb with the pixel gate's fonts and IBM's 3270 fonts
(from the same pinned nixpkgs), whose families are `IBM 3270`, `IBM 3270
Condensed` and `IBM 3270 Semi-Condensed`, with `X11_STATS=1`, which
prints each face it opens. Three families are asked for:

- `IBM 3270 Semi-Condensed` must open `3270SemiCondensed-Regular`. Parsed
  as a name, the `-` begins a size and the family is `IBM 3270 Semi`.
- `IBM 3270` must open `3270-Regular`.
- `Foo:weight=nonsense` is a family no font has: puritty must open a
  window with the closest font. Parsed as a name, fontconfig gives no
  pattern, and puritty handed fontconfig a NULL.

usage (from puritty's devbox, after app/build.sh):
    harness/fontnames.py [PURITTY]
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
import pixels  # noqa: E402  (its Xvfb and fonts)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "fontnames"
CASES = [("IBM 3270 Semi-Condensed", "3270SemiCondensed-Regular"), ("IBM 3270", "3270-Regular"),
         ("Foo:weight=nonsense", None)]


def fonts_conf():
    ibm = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", f"{pixels.NIXPKGS}#_3270font"],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    base = pixels.write_fonts_conf().read_text()
    WORK.mkdir(parents=True, exist_ok=True)
    conf = WORK / "fonts.conf"
    conf.write_text(base.replace("<fontconfig>\n", f"<fontconfig>\n  <dir>{ibm}/share/fonts/opentype</dir>\n", 1)
                    .replace(str(pixels.WORK / "fc-cache"), str(WORK / "fc-cache")))
    return conf


def first_face(app, conf, family):
    """The first face puritty opened for `family`, and whether its window came."""
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="fontnames-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[font]\nfamily = "{family}"\n\n[program]\ncommand = ["sleep", "30"]\n')
    env = dict(os.environ, DISPLAY=display, FONTCONFIG_FILE=str(conf), HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               USER=getpass.getuser(), PURITTY_NO_XIM="1", X11_STATS="1")
    err = home / "stderr.txt"
    p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                         stdout=subprocess.DEVNULL, stderr=open(err, "w"))
    try:
        time.sleep(3)
        tree = subprocess.run(["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True).stdout
        window = '("puritty" "Puritty")' in tree
    finally:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
        xvfb.kill()
    m = re.search(r"^face 0: (\S+)#", err.read_text(errors="replace"), re.M)
    shutil.rmtree(home)
    return (Path(m.group(1)).stem if m else None), window


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    conf = fonts_conf()
    wrong = []
    for family, want in CASES:
        face, window = first_face(app, conf, family)
        print(f"{family!r}: face 0 {face}, window {'open' if window else 'none'}")
        if not window:
            wrong.append(f"{family!r} opened no window")
        if want and face != want:
            wrong.append(f"{family!r} opened {face}, want {want}")
    if wrong:
        sys.exit("fontnames.py: " + "; ".join(wrong))


if __name__ == "__main__":
    main()

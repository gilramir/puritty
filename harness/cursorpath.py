#!/usr/bin/env python3
"""The cursor path gate (the code review's X19): the `XCURSOR_PATH` the
window sets for its own cursors is not left for the programs it starts.

Nix's xcb-util-cursor does not search /usr/share/icons, so the window sets
`XCURSOR_PATH` to libXcursor's own path while it loads its cursors when
the user has not set one. puritty runs on Xvfb with it unset, its program
a shell that writes `XCURSOR_PATH` as it sees it, or `unset`, to a file.
It must see `unset`: before X19 the variable stayed set in the process's
environment and every program puritty started, and every GUI program
those started, had libXcursor's default path replaced by the four
folders.

usage (from puritty's devbox, after app/build.sh):
    harness/cursorpath.py [PURITTY]
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

APP = ROOT / "app" / "puritty"


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="cursorpath-"))
    out = home / "seen"
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "-c", "printf %s \\"${{XCURSOR_PATH-unset}}\\" > {out}; sleep 30"]\n')
    env = {k: v for k, v in os.environ.items() if k != "XCURSOR_PATH"}
    env.update(DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        for _ in range(40):
            time.sleep(0.25)
            if out.exists() and out.stat().st_size > 0:
                break
        seen = out.read_text() if out.exists() else None
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    print(f"the program's XCURSOR_PATH: {seen!r}")
    if seen != "unset":
        sys.exit(f"cursorpath.py: the program saw {seen!r}, want 'unset' (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

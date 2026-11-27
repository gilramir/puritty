#!/usr/bin/env python3
"""The blink gate (the code review's MA16): a blinking cursor that is not
on the screen does not wake the window.

puritty runs on Xvfb through maximized.py's proxy, which counts the
requests it sends. Its program asks for a blinking cursor (mode 12),
prints a hundred lines and waits. The view is scrolled back a page
(Shift+PageUp), so no cursor is shown; requests are counted for WAIT
seconds. Before MA16 the blink went on with the cursor out of view, and
each blink drew every cell, the scrollbar being up: many requests a
second. There must now be at most a few (LIMIT).

usage (from puritty's devbox, after app/build.sh):
    harness/blinkback.py [PURITTY]
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
import maximized  # noqa: E402  (its counting proxy)

APP = ROOT / "app" / "puritty"
WAIT = 3
LIMIT = 20
SHOW = "printf '\\033[?12h'; i=0; while [ $i -lt 100 ]; do echo line $i; i=$((i+1)); done; sleep 60"


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    counter = maximized.Counter()
    via, lsock = maximized.proxy(display, counter)
    home = Path(tempfile.mkdtemp(prefix="blinkback-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "show.sh").write_text(SHOW + "\n")
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "{home / "show.sh"}"]\n\n[cursor]\nblink_ms = 500\n')
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh", USER=getpass.getuser(),
               PURITTY_NO_XIM="1")
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)],
                             env=dict(env, DISPLAY=via), stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(3)
        xenv = dict(env, DISPLAY=display)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=xenv, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=xenv, check=True)
        time.sleep(1)
        at = counter.mark()
        shown = len(counter.since(at))
        time.sleep(WAIT)
        focused = len(counter.since(at)) - shown
        subprocess.run([xdo, "key", "shift+Prior"], env=xenv, check=True)
        time.sleep(1)
        at = counter.mark()
        time.sleep(WAIT)
        back = len(counter.since(at))
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        lsock.close()
        xvfb.kill()
    print(f"in {WAIT} s: {focused} requests with the cursor blinking on screen, {back} scrolled back (at most {LIMIT})")
    if back > LIMIT:
        sys.exit(f"blinkback.py: {back} requests while scrolled back (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

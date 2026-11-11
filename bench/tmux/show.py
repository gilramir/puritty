#!/usr/bin/env python3
"""tmux control mode in puritty, shown (docs/tmux.md TM14): puritty on
Xvfb runs `tmux -CC new-session` on its own socket, a second tmux client
splits the window and opens floating panes, keys are typed into puritty's
window, and the window's own picture (PURITTY_SHOT) is saved as a PNG
after each step, in .harness-work/tmux-show/. Stops what it started.

    devbox run -- python3 bench/tmux/show.py --puritty app/puritty
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its fonts)
from reload import read_ppm, save_png  # noqa: E402

DISPLAY = ":87"
SOCK = "puritty-bench-tmux"
WORK = ROOT / ".harness-work" / "tmux-show"
CONF = ROOT / "packages" / "tmux" / "tests" / "data" / "tmux.conf"


def xdotool():
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), "xdotool"], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0] + "/bin/xdotool"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", default=str(ROOT / "app" / "puritty"))
    ap.add_argument("--tmux", default="tmux")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "config.toml").write_text("[window]\ncolumns = 100\nrows = 30\n")
    shot = WORK / "shot.ppm"
    xdo = xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", PS1="$ ", PURITTY_SHOT=str(shot))
    for k in ("LC_ALL", "TMUX", "ENV"):
        env.pop(k, None)
    tmux = [a.tmux, "-L", SOCK, "-f", str(CONF)]
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    app = None
    n = 0

    def snap(name):
        nonlocal n
        time.sleep(0.8)
        rows = read_ppm(shot)
        n += 1
        if rows:
            save_png(WORK / f"{n:02d}-{name}.png", rows)
            print(f"{n:02d}-{name}.png")
        else:
            print(f"{n:02d}-{name}: no picture")

    def cli(*args):
        r = subprocess.run([*tmux, *args], env=env, capture_output=True, text=True)
        if r.returncode:
            print("tmux", *args, "->", r.stderr.strip())

    try:
        app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                                *tmux, "-CC", "new-session"], env=env, stdout=subprocess.DEVNULL,
                               stderr=open(WORK / "stderr.txt", "w"))
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(1.5)
        snap("attached")
        subprocess.run([xdo, "type", "--delay", "20", "echo typed into puritty"], env=env, check=True)
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        snap("typed")
        cli("split-window", "-h")
        cli("send-keys", "-t", "%1", "printf '\\033[1;32mright pane\\033[0m 한글\\n'", "Enter")
        snap("split")
        cli("split-window", "-v", "-t", "%1")
        cli("send-keys", "-t", "%2", "ls /", "Enter")
        snap("three")
        cli("new-pane")
        snap("floating")
        subprocess.run([xdo, "type", "--delay", "20", "echo in the floating pane"], env=env, check=True)
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        snap("floating-typed")
        cli("new-pane", "-O", "-x", "36", "-y", "7")
        subprocess.run([xdo, "type", "--delay", "20", "echo modal"], env=env, check=True)
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        snap("modal")
        cli("kill-server")
        time.sleep(1)
        snap("after-exit")
    finally:
        subprocess.run([*tmux, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        if app:
            app.terminate()
            app.wait()
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

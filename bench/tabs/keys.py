#!/usr/bin/env python3
"""The `[keys]` table at work (docs/tabs.md TB6): puritty on Xvfb with
`new_tab` moved to Ctrl+Alt+N and `next_tab` emptied. Ctrl+Shift+T and
Ctrl+PageDown must reach the shell (which `cat -v` shows), Ctrl+Alt+N must
open a tab, and Ctrl+PageUp, still bound, must switch. What each step did
is read from files the shells write.

    devbox run -- python3 bench/tabs/keys.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "bench" / "tmux"))
import pixels  # noqa: E402
from show import xdotool  # noqa: E402

DISPLAY = ":87"
WORK = ROOT / ".harness-work" / "tabs-keys"


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    for f in WORK.glob("*"):
        f.unlink()
    (WORK / "config.toml").write_text('[program]\ncommand = ["/bin/sh"]\n\n[keys]\nnew_tab = "Ctrl+Alt+N"\nnext_tab = ""\n')
    xdo = xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", PS1="$ ", HOME=str(WORK))
    for k in ("LC_ALL", "TMUX", "ENV"):
        env.pop(k, None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([ROOT / "app" / "puritty", "--config", str(WORK / "config.toml"), "--title", "tabs-keys"],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    said = lambda name: (WORK / name).read_text().strip() if (WORK / name).exists() else "(none)"

    def typed(text):
        xd("type", "--delay", "10", text)
        xd("key", "Return")
        time.sleep(0.5)

    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tabs-keys"], env=env, capture_output=True,
                             text=True, timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(1.5)
        # the unbound keys go to the program: cat -v writes what it reads
        xd("type", "--delay", "10", f"cat -v > {WORK}/got.txt")
        xd("key", "Return")
        time.sleep(0.4)
        xd("key", "ctrl+shift+t")
        xd("key", "ctrl+Next")
        xd("key", "Return")
        xd("key", "ctrl+d")
        time.sleep(0.5)
        print("Ctrl+Shift+T then Ctrl+PageDown, unbound, reached the shell as:", said("got.txt"))
        typed(f"echo first > {WORK}/a.txt")
        xd("key", "ctrl+alt+n")
        time.sleep(1.0)
        typed(f"echo second > {WORK}/b.txt")
        print("after Ctrl+Alt+N the new tab's shell wrote:", said("b.txt"))
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        typed(f"echo back > {WORK}/c.txt")
        print("Ctrl+PageUp, still bound, went back to the first tab:", said("c.txt"))
    finally:
        if app.poll() is None:
            app.terminate()
            app.wait()
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

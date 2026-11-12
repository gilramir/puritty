#!/usr/bin/env python3
"""puritty's local tabs, shown (docs/tabs.md): puritty on Xvfb runs a
shell, keys open, switch, move and close tabs, each tab's shell is typed
into, and the window's picture (PURITTY_SHOT) is saved after each step,
in .harness-work/tabs-show/. Prints what each tab's shell wrote, read from
a file each writes, so a step is checked by more than a picture.

    devbox run -- python3 bench/tabs/show.py --puritty app/puritty
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "bench" / "tmux"))
import pixels  # noqa: E402
from reload import read_ppm, save_png  # noqa: E402
from show import xdotool  # noqa: E402

DISPLAY = ":88"
WORK = ROOT / ".harness-work" / "tabs-show"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", default=str(ROOT / "app" / "puritty"))
    ap.add_argument("--tabs", default="", help="a [tabs] table's lines, as bar = \"always\"")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    for f in WORK.glob("*"):
        f.unlink()
    (WORK / "config.toml").write_text('[program]\ncommand = ["/bin/sh"]\n\n[window]\ncolumns = 80\nrows = 24\n'
                                       + (f"\n[tabs]\n{a.tabs.replace(chr(92) + 'n', chr(10))}\n" if a.tabs else ""))
    shot = WORK / "shot.ppm"
    xdo = xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", PS1="$ ", PURITTY_SHOT=str(shot), HOME=str(WORK))
    for k in ("LC_ALL", "TMUX", "ENV"):
        env.pop(k, None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    n = 0

    def snap(name):
        nonlocal n
        time.sleep(0.8)
        rows = read_ppm(shot)
        n += 1
        if rows:
            save_png(WORK / f"{n:02d}-{name}.png", rows)
            print(f"{n:02d}-{name}.png")

    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    # the close button's request, as a window manager sends it
    wmclose = lambda w: subprocess.run([sys.executable, str(Path(__file__).parent / "wmclose.py"), w], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tabs-show"], env=env,
                           stdout=subprocess.DEVNULL, stderr=open(WORK / "stderr.txt", "w"))
    said = lambda name: (WORK / name).read_text().strip() if (WORK / name).exists() else "(none)"
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tabs-show"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(1.5)

        def typed(text):
            xd("type", "--delay", "10", text)
            xd("key", "Return")
            time.sleep(0.4)

        typed(f"echo one > {WORK}/a.txt; echo first tab")
        snap("one-tab")
        typed("cd /usr/share")
        xd("key", "ctrl+shift+t")
        time.sleep(1.0)
        typed(f"echo two > {WORK}/b.txt; echo second tab; pwd > {WORK}/h.txt")
        print("after cd /usr/share in the first tab, the new tab's shell is in:", said("h.txt"))
        snap("two-tabs")
        xd("key", "ctrl+shift+t")
        time.sleep(1.0)
        typed(f"echo three > {WORK}/c.txt; echo third tab")
        print("each tab's shell wrote:", said("a.txt"), said("b.txt"), said("c.txt"))
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        typed(f"echo back-in-two > {WORK}/b2.txt")
        snap("back-to-second")
        print("Ctrl+PgUp then typed, the second tab's shell wrote:", said("b2.txt"))
        # output in a tab not shown marks it, and a bell rings it
        typed(f"(sleep 1; echo late; printf '\\a') &")
        xd("key", "ctrl+Next")
        time.sleep(1.8)
        snap("marks")
        xd("key", "ctrl+shift+Prior")
        time.sleep(0.4)
        snap("moved-left")
        # a name of the user's, by key and by a double click on the bar
        xd("key", "ctrl+shift+r")
        time.sleep(0.4)
        snap("rename-box")
        xd("type", "--delay", "20", "dm")
        xd("key", "Return")
        time.sleep(0.4)
        xd("mousemove", "--window", win, "10", "399")
        xd("click", "--repeat", "2", "--delay", "120", "1")
        time.sleep(0.4)
        xd("type", "--delay", "20", "a")
        xd("key", "Return")
        snap("renamed")
        typed(f"echo in-a > {WORK}/f.txt")
        print("after the double click and naming, the first tab's shell wrote:", said("f.txt"))
        # closing a tab whose shell runs something asks first (TB4)
        xd("type", "--delay", "10", "sleep 30")
        xd("key", "Return")
        time.sleep(0.5)
        xd("key", "ctrl+shift+w")
        snap("close-asked")
        xd("key", "Escape")
        time.sleep(0.4)
        xd("key", "ctrl+c")
        time.sleep(0.4)
        typed(f"echo kept > {WORK}/g.txt")
        print("after Esc to the question, the tab's shell wrote:", said("g.txt"))
        # the window's close button asks when a tab, shown or not, is busy
        xd("key", "ctrl+Next")
        time.sleep(0.4)
        xd("type", "--delay", "10", "sleep 30")
        xd("key", "Return")
        time.sleep(0.4)
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        wmclose(win)
        snap("window-close-asked")
        xd("key", "Escape")
        time.sleep(0.5)
        print("after the window's close and Esc, puritty:", "ended" if app.poll() is not None else "still running")
        xd("key", "ctrl+Next")
        time.sleep(0.4)
        xd("key", "ctrl+c")
        time.sleep(0.4)
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        xd("key", "ctrl+shift+w")
        time.sleep(0.8)
        snap("closed")
        typed(f"echo after-close > {WORK}/d.txt")
        print("after Ctrl+Shift+W, the shown tab's shell wrote:", said("d.txt"))
        typed("exit")
        time.sleep(0.8)
        snap("exited")
        typed(f"echo last > {WORK}/e.txt")
        print("after exit, the last tab's shell wrote:", said("e.txt"))
        typed("exit")
        time.sleep(1.0)
        print("puritty after the last tab's exit:", "ended" if app.poll() is not None else "still running")
        # an idle window closes at once
        idle = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tabs-idle"], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        w2 = subprocess.run([xdo, "search", "--sync", "--name", "tabs-idle"], env=env, capture_output=True, text=True,
                            timeout=20).stdout.split()[0]
        time.sleep(1.5)
        wmclose(w2)
        time.sleep(1.0)
        print("an idle window's close:", "ended" if idle.poll() is not None else "still running")
        if idle.poll() is None:
            idle.terminate()
            idle.wait()
    finally:
        if app.poll() is None:
            app.terminate()
            app.wait()
        xvfb.terminate()
        xvfb.wait()
        err = (WORK / "stderr.txt").read_text().strip()
        if err:
            print("stderr:", err[:500])


if __name__ == "__main__":
    main()

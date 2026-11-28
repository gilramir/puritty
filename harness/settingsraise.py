#!/usr/bin/env python3
"""The settings raise gate (docs/settings.md ST42, the code review's W10):
a terminal whose program titles it as the settings window is not taken
for the settings window.

puritty runs on Xvfb, its tab a program that sets the window's title to
the settings window's ("puritty settings", OSC 2) and waits. Then
`puritty settings` is started: a settings window already open would be
raised and the new one end (ST8), but none is, so it must open its own,
and the display then has two puritty windows. Before W10 a window was
found by its title: the terminal was raised and `puritty settings`
ended, with no settings window.

usage (from puritty's devbox, after app/build.sh):
    harness/settingsraise.py [PURITTY]
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
TITLE = "puritty settings"


def windows(xdo, env):
    r = subprocess.run([xdo, "search", "--class", "puritty"], env=env, capture_output=True, text=True, timeout=10)
    return r.stdout.split()


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="settingsraise-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "title.sh").write_text(f"printf '\\033]2;{TITLE}\\007'; sleep 60\n")
    (home / "config" / "puritty" / "config.toml").write_text(f'[program]\ncommand = ["sh", "{home / "title.sh"}"]\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               XDG_STATE_HOME=str(home / "state"), SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_NO_XIM="1",
               LANG="C.UTF-8", LC_ALL="C.UTF-8")
    terminal = settings = None
    try:
        terminal = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                                    stdout=subprocess.DEVNULL, stderr=open(home / "terminal.txt", "w"))
        subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, timeout=10)
        time.sleep(2)
        named = subprocess.run([xdo, "search", "--name", TITLE], env=env, capture_output=True, text=True).stdout.split()
        settings = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app), "settings"],
                                    env=env, stdout=subprocess.DEVNULL, stderr=open(home / "settings.txt", "w"))
        time.sleep(4)
        ended = settings.poll() is not None
        seen = windows(xdo, env)
    finally:
        for p in (settings, terminal):
            if p and p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
        xvfb.kill()
    print(f"the terminal titled {TITLE!r}: {len(named)} window(s) by that name; "
          f"then `puritty settings` {'ended' if ended else 'stayed'}, {len(seen)} puritty window(s)")
    wrong = []
    if not named:
        wrong.append("the terminal's program did not title it")
    if ended or len(seen) < 2:
        wrong.append("`puritty settings` opened no window of its own")
    if wrong:
        sys.exit("settingsraise.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

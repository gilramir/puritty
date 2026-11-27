#!/usr/bin/env python3
"""The closed terminal gate (docs/tabs.md TB24, the code review's MA23):
a program that closes its terminal and carries on does not hold the
window.

puritty runs on Xvfb with its diagnostic log on. Its program is a script:
the first tab's a shell, every later one's `exec >/dev/null 2>&1
</dev/null; sleep 60`, which closes the terminal at once and lives a
minute. Two cases:

- two tabs: the second, opened with Ctrl+Shift+T, closes its terminal;
  the first must be shown within WITHIN seconds (the log's `shown: tab 0
  of 1`). Before MA23 the loop waited for the program's exit inside its
  turn, and the window, every tab and its events with it, stood still
  for the minute.
- one tab, the same program: puritty must have ended within WITHIN
  seconds. Before, it waited for the program's exit.

usage (from puritty's devbox, after app/build.sh):
    harness/closedterm.py [PURITTY]
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
WITHIN = 5
GONE = "exec >/dev/null 2>&1 </dev/null; sleep 60"


def shown_one(home):
    logs = sorted((home / "state" / "puritty" / "logs").glob("*.log"))
    return any("shown: tab 0 of 1" in l for f in logs for l in f.read_text(errors="replace").splitlines())


def run(app, xdo, first_plain):
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="closedterm-"))
    (home / "config" / "puritty").mkdir(parents=True)
    if first_plain:
        (home / "tab.sh").write_text(f'if [ -e "{home}/first" ]; then {GONE}; fi\ntouch "{home}/first"; exec sh\n')
    else:
        (home / "tab.sh").write_text(GONE + "\n")
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "{home / "tab.sh"}"]\n\n[debug]\nlog = true\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               XDG_STATE_HOME=str(home / "state"), SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = subprocess.Popen([str(app)], env=env, stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
    took = None
    try:
        if first_plain:
            win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True,
                                 text=True, timeout=10).stdout.split()[0]
            subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
            time.sleep(1.5)
            subprocess.run([xdo, "key", "ctrl+shift+t"], env=env, check=True)
            start = time.time()
            while time.time() - start < 20:
                if shown_one(home):
                    took = time.time() - start
                    break
                time.sleep(0.2)
        else:
            start = time.time()
            try:
                p.wait(20)
                took = time.time() - start
            except subprocess.TimeoutExpired:
                pass
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
        xvfb.kill()
        # the tabs' minute-long sleeps end by themselves
    shutil.rmtree(home)
    return took


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    two = run(app, xdo, True)
    one = run(app, xdo, False)
    say = lambda t: "not within 20 s" if t is None else f"{t:.1f} s"
    print(f"two tabs, the second's program closing its terminal: the first shown after {say(two)}")
    print(f"one tab: puritty ended after {say(one)}")
    wrong = [w for w, t in (("two tabs", two), ("one tab", one)) if t is None or t > WITHIN]
    if wrong:
        sys.exit(f"closedterm.py: {', '.join(wrong)} took more than {WITHIN} s")


if __name__ == "__main__":
    main()

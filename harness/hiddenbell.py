#!/usr/bin/env python3
"""The hidden tmux bell gate (docs/sounds.md SN10, the code review's MA14):
a bell in a `tmux -CC` tab that is not shown is heard when it rings, and
showing that tab again does not ring it.

puritty runs on Xvfb with `[sound] bell = "apple2"` and its diagnostic
log on. Its program is a script: the first tab's a shell, the second's
the system's tmux in control mode
(`tmux -L hiddenbell -CC new-session`), whose pane rings the bell after RING_AT seconds. The second
tab is opened (Ctrl+Shift+T), its control mode started at the question
puritty asks for a start it did not expect (Enter), and the first tab
shown again (Ctrl+Alt+PageUp, which switches tabs under tmux too), so
the bell rings while the tmux tab is hidden; after it the tmux tab is
shown again (Ctrl+Alt+PageDown). Each bell the window hears is a `rang:`
line in the log: there must be one before the switch back and none more
after it. Before MA14 a hidden tab's tmux panes were not counted:
nothing was heard when the bell rang, and the switch back rang it.

usage (from puritty's devbox, after app/build.sh):
    harness/hiddenbell.py [PURITTY]
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
TMUX = "/usr/bin/tmux"
SOCKET = "hiddenbell"
RING_AT = 8


def rang(home):
    logs = sorted((home / "state" / "puritty" / "logs").glob("*.log"))
    return sum(1 for f in logs for l in f.read_text(errors="replace").splitlines() if "rang: " in l)


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="hiddenbell-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "pane.sh").write_text(f"sleep {RING_AT}; printf '\\a'; sleep 60\n")
    (home / "tab.sh").write_text(
        f'if [ -e "{home}/first" ]; then exec {TMUX} -L {SOCKET} -f /dev/null -CC new-session "sh {home}/pane.sh"; fi\n'
        f'touch "{home}/first"; exec sh\n')
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "{home / "tab.sh"}"]\n\n[sound]\nbell = "apple2"\n\n[debug]\nlog = true\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               XDG_STATE_HOME=str(home / "state"), SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_NO_XIM="1")
    env.pop("TMUX", None)
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(2)
        subprocess.run([xdo, "key", "ctrl+shift+t"], env=env, check=True)
        time.sleep(1.5)
        # the tab did not start tmux itself: puritty asks (docs/tmux.md
        # TM108), and Enter starts control mode
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        time.sleep(1.5)
        subprocess.run([xdo, "key", "ctrl+alt+Prior"], env=env, check=True)
        time.sleep(RING_AT)
        before = rang(home)
        subprocess.run([xdo, "key", "ctrl+alt+Next"], env=env, check=True)
        time.sleep(2)
        after = rang(home) - before
    finally:
        subprocess.run([TMUX, "-L", SOCKET, "kill-server"], env=env, capture_output=True)
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    logs = sorted((home / "state" / "puritty" / "logs").glob("*.log"))
    switches = [l.split("shown: ", 1)[1] for f in logs for l in f.read_text(errors="replace").splitlines() if "shown: tab" in l]
    print(f"tabs shown: {switches}")
    print(f"bells heard while the tmux tab was hidden: {before}; on showing it again: {after}")
    if before != 1 or after != 0:
        sys.exit(f"hiddenbell.py: want 1 and 0 (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

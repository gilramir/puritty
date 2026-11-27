#!/usr/bin/env python3
"""The reopen gate (docs/tabs.md TB25, the code review's MB14): a closed
tab whose reopening does not start is still there to reopen.

puritty runs on Xvfb with its diagnostic log on and `sh` its program. A
second tab is opened and closed (Ctrl+Shift+T, Ctrl+Shift+W). puritty's
limit of processes (RLIMIT_NPROC, its soft limit, `prlimit` on its pid)
is then set to 1, so that it cannot start a program, and the tab reopened
(Ctrl+Alt+Shift+T): it does not start. The limit is put back and the tab
reopened again: it must open, the window showing two tabs again (the
log's `shown: tab N of 2` after the second try).
Before MB14 the first, failed try took the closed tab out of the ones
kept, and the second had nothing to reopen.

usage (from puritty's devbox, after app/build.sh):
    harness/reopenfail.py [PURITTY]
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
GOOD = '[program]\ncommand = ["sh"]\n\n[debug]\nlog = true\n'


def lines(home, text):
    logs = sorted((home / "state" / "puritty" / "logs").glob("*.log"))
    return [l for f in logs for l in f.read_text(errors="replace").splitlines() if text in l]


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="reopenfail-"))
    conf = home / "config" / "puritty" / "config.toml"
    conf.parent.mkdir(parents=True)
    conf.write_text(GOOD)
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               XDG_STATE_HOME=str(home / "state"), SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = None
    key = lambda k: subprocess.run([xdo, "key", k], env=env, check=True)
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(1.5)
        key("ctrl+shift+t")
        time.sleep(1.5)
        key("ctrl+shift+w")
        time.sleep(1.5)
        hard = subprocess.run(["prlimit", "--pid", str(p.pid), "--nproc", "--noheadings", "--output=HARD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["prlimit", "--pid", str(p.pid), "--nproc=1:"], check=True)
        key("ctrl+alt+shift+t")
        time.sleep(2)
        failed = "a new tab did not start" in (home / "stderr.txt").read_text(errors="replace")
        subprocess.run(["prlimit", "--pid", str(p.pid), f"--nproc={hard}:"], check=True)
        # the box that says the tab did not start, closed
        key("Escape")
        time.sleep(1)
        before = len([l for l in lines(home, "shown: tab ") if l.endswith(" of 2")])
        key("ctrl+alt+shift+t")
        time.sleep(2)
        reopened = len([l for l in lines(home, "shown: tab ") if l.endswith(" of 2")]) - before
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    print(f"the first reopening did not start: {failed}; the second opened the tab: {reopened > 0}")
    if not failed or reopened == 0:
        sys.exit(f"reopenfail.py: want the first refused and the second opened (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

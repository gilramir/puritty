#!/usr/bin/env python3
"""Reopening a closed tab (docs/tabs.md TB11), on Xvfb. Each step is checked
by what the reopened tab's shell writes, read from a file; pictures are
saved in .harness-work/tabs-reopen/.

  1. Two local tabs closed, the one in dirs/one first, then the one in
     dirs/two: Ctrl+Alt+Shift+T opens dirs/two's again, then dirs/one's.
  2. A tab with 300 lines behind it and vi on its screen, closed and
     reopened: its old lines above, vi's screen gone, the shell taking the
     next line (the picture shows it).
  3. Reopening from the menu (Ctrl and the right button, Reopen closed tab).
  4. A host's tab of the built-in client, against the local sshd
     (packages/ssh/tests/sshd.py), closed and reopened: it connects again.

Only the puritty processes this run started are ever killed: each carries
this run's work directory in its environment.

    devbox run -- python3 bench/tabs/reopen.py      (after app/build.sh and packages/ssh/tests/build.sh)
"""

import getpass
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "packages" / "ssh" / "tests"))
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402
import reload  # noqa: E402  (the window's picture)
import sshd  # noqa: E402

DISPLAY = ":84"
WORK = ROOT / ".harness-work" / "tabs-reopen"


def pids():
    """The puritty processes this run started: each has this run's HOME."""
    mark = f"HOME={WORK}".encode()
    found = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            if (d / "comm").read_text().strip() != "puritty":
                continue
            if mark in (d / "environ").read_bytes().split(b"\0"):
                found.append(int(d.name))
        except OSError:
            continue
    return found


def kill_ours():
    for p in pids():
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(1.0)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "config" / "puritty").mkdir(parents=True)
    (WORK / ".ssh").mkdir()
    for d in ("one", "two", "three"):
        (WORK / "dirs" / d).mkdir(parents=True)
    xdo = hosts.xdotool()
    keys = sshd.user_keys()[0]
    sshd.host_keys()
    server = sshd.Server([])
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    (WORK / ".ssh" / "known_hosts").write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    (WORK / "config" / "puritty" / "config.toml").write_text(
        '[program]\ncommand = ["/bin/sh"]\n\n[tabs]\nask_before_closing = false\n\n'
        f'[hosts.box]\nhost = "127.0.0.1"\nport = {server.port}\nuser = "{getpass.getuser()}"\n'
        f'identity = "{keys["ed"]}"\nclient = "built-in"\ncommand = "/bin/sh"\n')
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", HOME=str(WORK), XDG_CONFIG_HOME=str(WORK / "config"),
               SHELL="/bin/sh", USER=getpass.getuser(), PS1="$ ", PURITTY_SHOT=str(WORK / "shot.ppm"),
               TERM="xterm-256color")
    for k in ("SSH_AUTH_SOCK", "LC_ALL", "ENV", "TMUX"):
        env.pop(k, None)
    xd = lambda *a: subprocess.run([xdo, *a], env=env, check=True)
    said = lambda name: (WORK / name).read_text().strip().replace(str(WORK), "WORK") if (WORK / name).exists() else "(none)"
    stderr = open(WORK / "stderr.txt", "a")

    def start(*args, wait=2.5):
        subprocess.Popen([str(ROOT / "app" / "puritty"), *args], env=env, stdout=subprocess.DEVNULL, stderr=stderr)
        time.sleep(wait)
        win = subprocess.run([xdo, "search", "--onlyvisible", "--name", "."], env=env, capture_output=True,
                             text=True).stdout.split()[-1]
        xd("windowfocus", "--sync", win)
        time.sleep(0.3)
        return win

    def typed(text):
        xd("type", "--delay", "10", text)
        xd("key", "Return")
        time.sleep(0.6)

    def snap(name):
        time.sleep(0.6)
        rows = reload.read_ppm(WORK / "shot.ppm")
        if rows:
            reload.save_png(WORK / f"{name}.png", rows)

    def reopen():
        xd("key", "ctrl+alt+shift+t")
        time.sleep(1.2)

    try:
        # 1
        start()
        typed(f"cd {WORK}/dirs/three")
        for d in ("one", "two"):
            xd("key", "ctrl+shift+t")
            time.sleep(1.0)
            typed(f"cd {WORK}/dirs/{d}")
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        xd("key", "ctrl+shift+w")
        time.sleep(0.8)
        # the tab after it is shown: two's
        xd("key", "ctrl+shift+w")
        time.sleep(0.8)
        typed(f"pwd > {WORK}/left.txt")
        reopen()
        typed(f"pwd > {WORK}/first.txt")
        reopen()
        typed(f"pwd > {WORK}/second.txt")
        print(f"1. closed one, then two; left in {said('left.txt')}; reopened first in {said('first.txt')}, "
              f"then in {said('second.txt')}")
        # 2
        typed("seq 1 300")
        typed("vi")
        time.sleep(0.8)
        snap("2-before")
        xd("key", "ctrl+shift+w")
        time.sleep(0.8)
        reopen()
        snap("2-reopened")
        typed(f"pwd > {WORK}/after-vi.txt")
        snap("2-after")
        print("2. a tab closed under vi, reopened: its shell wrote", said("after-vi.txt"))
        # 3
        xd("key", "ctrl+shift+w")
        time.sleep(0.8)
        geometry = subprocess.run([xdo, "getwindowfocus", "getwindowgeometry"], env=env, capture_output=True,
                                  text=True).stdout
        xd("mousemove", "200", "200")
        xd("keydown", "ctrl")
        xd("click", "3")
        xd("keyup", "ctrl")
        time.sleep(0.6)
        snap("3-menu")
        for _ in range(5):
            xd("key", "Down")
        xd("key", "Return")
        time.sleep(1.2)
        typed(f"pwd > {WORK}/menu.txt")
        print("3. reopened from the menu: its shell wrote", said("menu.txt"))
        kill_ours()
        # 4
        start("--host", "box", wait=4.0)
        xd("key", "ctrl+shift+t")
        time.sleep(3.0)
        typed(f"echo one > {WORK}/ssh1.txt")
        xd("key", "ctrl+shift+w")
        time.sleep(1.0)
        reopen()
        time.sleep(3.0)
        snap("4-ssh-reopened")
        typed(f"echo again > {WORK}/ssh2.txt")
        print("4. an ssh tab: its shell wrote", said("ssh1.txt"), "then, closed and reopened,", said("ssh2.txt"))
    finally:
        kill_ours()
        server.stop()
        xvfb.terminate()
        xvfb.wait()
        err = (WORK / "stderr.txt").read_text().strip()
        if err:
            print("stderr:", err[:600])
        print("pictures:", WORK)


if __name__ == "__main__":
    main()

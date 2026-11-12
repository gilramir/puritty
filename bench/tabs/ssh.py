#!/usr/bin/env python3
"""ssh tabs ending (docs/tabs.md TB8): puritty with a host of the built-in
client against a local sshd (packages/ssh/tests/sshd.py's), on Xvfb. A
second tab is another session to the host (Ctrl+Shift+T); `exit` in the
shown tab closes that tab and not the window; `exit` in a tab not shown
does the same; `exit` in the last tab ends the window with the remote
shell's status. Each step is checked by a file the remaining shell writes.

    devbox run -- python3 bench/tabs/ssh.py      (after app/build.sh and packages/ssh/tests/build.sh)
"""

import getpass
import os
import shutil
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

DISPLAY = ":85"
WORK = ROOT / ".harness-work" / "tabs-ssh"


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "config" / "puritty").mkdir(parents=True)
    (WORK / ".ssh").mkdir()
    xdo = hosts.xdotool()
    keys = sshd.user_keys()[0]
    sshd.host_keys()
    server = sshd.Server([])
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    p = None
    try:
        pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
        (WORK / ".ssh" / "known_hosts").write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
        (WORK / "config" / "puritty" / "config.toml").write_text(
            f'[hosts.box]\nhost = "127.0.0.1"\nport = {server.port}\nuser = "{getpass.getuser()}"\n'
            f'identity = "{keys["ed"]}"\nclient = "built-in"\ncommand = "/bin/sh"\n')
        env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
                   PURITTY_DPI="96", LANG="C.UTF-8", HOME=str(WORK), XDG_CONFIG_HOME=str(WORK / "config"),
                   SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_SHOT=str(WORK / "shot.ppm"))
        env.pop("SSH_AUTH_SOCK", None)
        env.pop("LC_ALL", None)
        p = subprocess.Popen([str(ROOT / "app" / "puritty"), "--host", "box"], env=env, stdout=subprocess.DEVNULL,
                             stderr=open(WORK / "stderr.txt", "w"))
        time.sleep(3.0)
        win = subprocess.run([xdo, "search", "--sync", "--onlyvisible", "--name", "."], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()
        xd = lambda *a: subprocess.run([xdo, *a], env=env, check=True)
        xd("windowfocus", "--sync", win[-1])
        said = lambda name: (WORK / name).read_text().strip() if (WORK / name).exists() else "(none)"

        def typed(text):
            xd("type", "--delay", "15", text)
            xd("key", "Return")
            time.sleep(0.8)

        alive = lambda: "running" if p.poll() is None else f"ended, status {p.returncode}"

        def snap(name):
            time.sleep(0.8)
            rows = reload.read_ppm(WORK / "shot.ppm")
            if rows:
                reload.save_png(WORK / f"{name}.png", rows)
                print(f"  picture: {WORK / (name + '.png')}")
        typed(f"echo one > {WORK}/a.txt")
        print("the first ssh tab's shell wrote:", said("a.txt"))
        xd("key", "ctrl+shift+t")
        time.sleep(3.0)
        typed(f"echo two > {WORK}/b.txt")
        print("the second ssh tab's shell wrote:", said("b.txt"))
        typed("exit")
        time.sleep(1.0)
        print("after exit in the shown ssh tab, puritty is", alive())
        typed(f"echo after > {WORK}/c.txt")
        print("then the first tab's shell wrote:", said("c.txt"))
        # a tab not shown whose session ends
        xd("key", "ctrl+shift+t")
        time.sleep(3.0)
        typed("sleep 2; exit")
        xd("key", "ctrl+Prior")
        time.sleep(4.0)
        print("after exit in an ssh tab not shown, puritty is", alive())
        typed(f"echo still > {WORK}/d.txt")
        print("then the shown tab's shell wrote:", said("d.txt"))
        # a session that drops, its shell not exiting: the tab stays, marked,
        # and reconnects with r
        xd("key", "ctrl+shift+t")
        time.sleep(3.0)
        typed("kill -9 $PPID")
        time.sleep(1.5)
        print("after its connection dropped, puritty is", alive())
        snap("dropped")
        xd("key", "r")
        time.sleep(3.0)
        typed(f"echo again > {WORK}/e.txt")
        print("after r, the reconnected tab's shell wrote:", said("e.txt"))
        snap("reconnected")
        typed("exit")
        time.sleep(1.0)
        typed("exit 5")
        time.sleep(2.0)
        print("after exit 5 in the last tab, puritty is", alive())
    finally:
        if p is not None and p.poll() is None:
            p.terminate()
            p.wait()
        server.stop()
        xvfb.terminate()
        xvfb.wait()
        err = (WORK / "stderr.txt").read_text().strip() if (WORK / "stderr.txt").exists() else ""
        if err:
            print("stderr:", err[:400])


if __name__ == "__main__":
    main()

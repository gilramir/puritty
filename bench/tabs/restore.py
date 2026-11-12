#!/usr/bin/env python3
"""Restoring tabs when puritty starts (docs/tabs.md TB10), on Xvfb, with
`[tabs] restore = true` and the state directory under the work directory.
Each step is checked by what the restored tabs' shells write, read from
files, and by the state directory's files; pictures are saved in
.harness-work/tabs-restore/.

Only the puritty processes this run started are ever killed: each carries
this run's XDG_STATE_HOME in its environment, and so do the ones they
start, so a puritty the user has open is never touched.

  1. Three local tabs in three directories, the second named `dm` and
     green, the second shown; the window killed (SIGKILL, as a crash
     would end it); `puritty` again: the same tabs.
  2. That window closed by its button, the only one open: kept.
  3. Every tab's shell ended: forgotten, and `puritty` opens one shell.
  4. Two windows; one closed by its button while the other runs: that one
     forgotten, the other kept.
  5. Two windows killed: one `puritty` start opens both.
  6. A host of the built-in client with two named tabs, against the local
     sshd (packages/ssh/tests/sshd.py), killed and restored: both connect.

    devbox run -- python3 bench/tabs/restore.py      (after app/build.sh and packages/ssh/tests/build.sh)
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

DISPLAY = ":87"
WORK = ROOT / ".harness-work" / "tabs-restore"
STATE = WORK / "state" / "puritty" / "windows"


def pids():
    """The puritty processes this run started, and those they started:
    each has this run's state directory in its environment, so a puritty
    the user is running is never one of them."""
    mark = f"XDG_STATE_HOME={WORK / 'state'}".encode()
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
    return sorted(found)


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
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1600x1000x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    (WORK / ".ssh" / "known_hosts").write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    (WORK / "config" / "puritty" / "config.toml").write_text(
        '[program]\ncommand = ["/bin/sh"]\n\n[tabs]\nrestore = true\n\n[keys]\ncolor_tab = "Ctrl+Alt+K"\n\n'
        f'[hosts.box]\nhost = "127.0.0.1"\nport = {server.port}\nuser = "{getpass.getuser()}"\n'
        f'identity = "{keys["ed"]}"\nclient = "built-in"\ncommand = "/bin/sh"\n\n'
        '[hosts.box.colors]\nbackground = "#2a1010"\n')
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", HOME=str(WORK), XDG_CONFIG_HOME=str(WORK / "config"),
               XDG_STATE_HOME=str(WORK / "state"), SHELL="/bin/sh", USER=getpass.getuser(), PS1="$ ",
               PURITTY_SHOT=str(WORK / "shot.ppm"))
    for k in ("SSH_AUTH_SOCK", "LC_ALL", "ENV", "TMUX"):
        env.pop(k, None)
    xd = lambda *a: subprocess.run([xdo, *a], env=env, check=True)
    said = lambda name: (WORK / name).read_text().strip() if (WORK / name).exists() else "(none)"
    w = lambda name: said(name).replace(str(WORK), "WORK")
    stderr = open(WORK / "stderr.txt", "a")

    def windows():
        out = subprocess.run([xdo, "search", "--onlyvisible", "--name", "."], env=env, capture_output=True, text=True)
        return out.stdout.split()

    def start(*args, wait=2.5):
        subprocess.Popen([str(ROOT / "app" / "puritty"), *args], env=env, stdout=subprocess.DEVNULL, stderr=stderr)
        time.sleep(wait)

    def focus(win):
        xd("windowfocus", "--sync", win)
        time.sleep(0.3)

    def typed(text):
        xd("type", "--delay", "10", text)
        xd("key", "Return")
        time.sleep(0.6)

    def snap(name):
        time.sleep(0.6)
        rows = reload.read_ppm(WORK / "shot.ppm")
        if rows:
            reload.save_png(WORK / f"{name}.png", rows)

    def files(end=""):
        return sorted(f.name for f in STATE.glob("*") if f.name.endswith(end)) if STATE.exists() else []

    def wmclose(win):
        subprocess.run([sys.executable, str(Path(__file__).parent / "wmclose.py"), win], env=env, check=True)
        time.sleep(1.5)

    try:
        # 1
        start()
        focus(windows()[-1])
        typed(f"cd {WORK}/dirs/one")
        xd("key", "ctrl+shift+t")
        time.sleep(1.0)
        typed(f"cd {WORK}/dirs/two")
        xd("key", "ctrl+shift+r")
        time.sleep(0.3)
        xd("type", "dm")
        xd("key", "Return")
        xd("key", "ctrl+alt+k")
        time.sleep(0.3)
        xd("key", "4")
        xd("key", "ctrl+shift+t")
        time.sleep(1.0)
        typed(f"cd {WORK}/dirs/three")
        xd("key", "ctrl+Prior")
        time.sleep(6.0)
        print("1. the state saved:", files())
        print((STATE / files(".toml")[0]).read_text().replace(str(WORK), "WORK"))
        kill_ours()
        start()
        focus(windows()[-1])
        snap("1-restored")
        typed(f"pwd > {WORK}/t2.txt")
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        typed(f"pwd > {WORK}/t1.txt")
        xd("key", "ctrl+Prior")
        time.sleep(0.4)
        typed(f"pwd > {WORK}/t3.txt")
        print(f"   restored: the shown tab in {w('t2.txt')}, the one before it in {w('t1.txt')}, "
              f"the last in {w('t3.txt')}; windows {len(windows())}")
        # 2
        wmclose(windows()[-1])
        print("2. closed by its button, the only window; running:", len(pids()), "saved:", files(".toml"))
        start()
        focus(windows()[-1])
        typed(f"pwd > {WORK}/again.txt")
        print("   started again: the shown tab in", w("again.txt"), "windows", len(windows()))
        # 3
        for _ in range(3):
            typed("exit")
            time.sleep(0.4)
        time.sleep(1.0)
        print("3. every shell ended; running:", len(pids()), "files:", files())
        start()
        focus(windows()[-1])
        typed(f"pwd > {WORK}/fresh.txt")
        snap("3-fresh")
        print("   started again: one tab in", w("fresh.txt"))
        # 4
        start()
        time.sleep(5.5)
        print("4. two windows: locks", len(files(".lock")), "saved", len(files(".toml")))
        wmclose(windows()[-1])
        print("   one closed by its button while the other runs; running:", len(pids()), "saved:",
              len(files(".toml")))
        # 5
        start()
        time.sleep(5.5)
        print("5. two windows saved:", len(files(".toml")))
        kill_ours()
        start(wait=5.0)
        print("   both killed, one puritty started: windows", len(windows()), "running", len(pids()))
        kill_ours()
        for f in STATE.glob("*"):
            f.unlink()
        # 6
        start("--host", "box", wait=3.5)
        focus(windows()[-1])
        xd("key", "ctrl+shift+r")
        time.sleep(0.3)
        xd("type", "web")
        xd("key", "Return")
        xd("key", "ctrl+shift+t")
        time.sleep(3.0)
        xd("key", "ctrl+shift+r")
        time.sleep(0.3)
        xd("type", "db")
        xd("key", "Return")
        time.sleep(6.0)
        print("6. a host's window saved:")
        print((STATE / files(".toml")[0]).read_text())
        # a settings change reloads the window's settings from the file,
        # which names no host: the window is still saved as the host's
        def corner():
            time.sleep(0.6)
            rows = reload.read_ppm(WORK / "shot.ppm")
            return "#" + bytes(rows[len(rows) // 2][-30:-27]).hex() if rows else "no picture"
        before = corner()
        cfg = WORK / "config" / "puritty" / "config.toml"
        cfg.write_text(cfg.read_text() + "\n# changed\n")
        time.sleep(6.0)
        xd("key", "shift")
        print("   the terminal's background (the host's #2a1010) before a settings change", before, "and after", corner())
        print("   after a settings change, still saved as box's:",
              (STATE / files(".toml")[0]).read_text().startswith('host = "box"'))
        kill_ours()
        # both sessions connect at once; keys typed while puritty's own
        # screen says it connects are not the shell's, so wait for both
        start(wait=8.0)
        focus(windows()[-1])
        typed(f"echo db > {WORK}/s2.txt")
        xd("key", "ctrl+Prior")
        time.sleep(1.0)
        typed(f"echo web > {WORK}/s1.txt")
        snap("6-host-restored")
        print("   restored: the shown tab's shell wrote", said("s2.txt"), "and the other's", said("s1.txt"))
        # puritty restore with nothing waiting
        kill_ours()
        for f in STATE.glob("*"):
            f.unlink()
        p = subprocess.run([str(ROOT / "app" / "puritty"), "restore"], env=env, timeout=20)
        print("puritty restore with none waiting: exit", p.returncode, "windows", len(windows()))
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

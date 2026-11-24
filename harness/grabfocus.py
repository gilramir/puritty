#!/usr/bin/env python3
"""The focus-grab gate (docs/phase3-input.md §19, the code review's X10):
another client's keyboard grab, as a window manager's hotkey or an
Alt-Tab switcher makes, is not a focus change.

puritty runs on Xvfb, its tab a program that asks for focus reports
(mode 1004) and writes what it receives to a file. A second client grabs
the keyboard (XGrabKeyboard, which sends the focused window FocusOut with
mode NotifyGrab) and lets it go (FocusIn, NotifyUngrab), three times. The
program must receive nothing; before §19 it received `CSI O` and `CSI I`
for each. Then the focus really moves to another window and back, which
must still be reported: `CSI O` `CSI I`.

usage (from puritty's devbox, after app/build.sh):
    harness/grabfocus.py [PURITTY]
"""
import ctypes
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
RECORD = "printf '\\033[?1004h'; stty raw -echo; exec dd bs=1 of=\"$0\" 2>/dev/null"


def grabs(display, n):
    """The keyboard grabbed and let go `n` times by a client of its own."""
    x = ctypes.CDLL("libX11.so.6")
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XDefaultRootWindow.restype = ctypes.c_ulong
    x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x.XGrabKeyboard.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    x.XUngrabKeyboard.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    d = x.XOpenDisplay(display.encode())
    root = x.XDefaultRootWindow(d)
    for _ in range(n):
        x.XGrabKeyboard(d, root, 0, 1, 1, 0)
        x.XSync(d, 0)
        time.sleep(0.3)
        x.XUngrabKeyboard(d, 0)
        x.XSync(d, 0)
        time.sleep(0.3)
    x.XCloseDisplay(d)


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="grabfocus-"))
    out = home / "typed"
    (home / "config" / "puritty").mkdir(parents=True)
    script = home / "record.sh"
    script.write_text(RECORD.replace('"$0"', '"$1"') + "\n")
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "{script}", "{out}"]\n\n[debug]\nlog = true\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(3)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(1)
        start = out.stat().st_size if out.exists() else 0
        grabs(display, 3)
        time.sleep(1)
        grabbed = (out.read_bytes() if out.exists() else b"")[start:]
        # a real move of the focus, to the root window, and back
        subprocess.run([xdo, "windowfocus", "--sync", str(int(subprocess.run(
            [xdo, "search", "--maxdepth", "0", "--name", ""], env=env, capture_output=True, text=True).stdout.split()[0]))],
            env=env)
        time.sleep(0.5)
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(1)
        moved = (out.read_bytes() if out.exists() else b"")[start + len(grabbed):]
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    print(f"during the grabs: {grabbed!r}; the focus moved away and back: {moved!r}")
    wrong = []
    if grabbed:
        wrong.append(f"the grabs reported {grabbed!r}, want nothing")
    if moved != b"\x1b[O\x1b[I":
        wrong.append(f"the move reported {moved!r}, want CSI O CSI I")
    if wrong:
        sys.exit("grabfocus.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

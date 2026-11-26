#!/usr/bin/env python3
"""The X screen gate (the code review's X16 and X17): puritty opens its
window on the screen `DISPLAY` names, and its `WM_CLASS` is the two
strings and nothing more.

Xvfb runs with two screens, and puritty with `DISPLAY` naming the second
(`:N.1`). Every top-level window of both screens is looked at with Xlib
(through ctypes): puritty's, found by its `WM_CLASS`, must be on screen 1,
and its `WM_CLASS` must be the 16 bytes `puritty\\0Puritty\\0`. Before
X17 the window opened on screen 0 whatever `DISPLAY` said; before X16
the property was 18 bytes, the last two past the class's terminator.

usage (from puritty's devbox, after app/build.sh):
    harness/screens.py [PURITTY]
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
APP = ROOT / "app" / "puritty"


def start_xvfb():
    """Xvfb with two screens; its display number."""
    r, w = os.pipe()
    proc = subprocess.Popen(["Xvfb", "-displayfd", str(w), "-screen", "0", "1280x800x24", "-screen", "1",
                             "1280x800x24", "-nolisten", "tcp", "-dpi", "96"],
                            pass_fds=(w,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(w)
    with os.fdopen(r) as f:
        number = f.readline().strip()
    if not number:
        proc.kill()
        raise RuntimeError("Xvfb did not start")
    return proc, ":" + number


def xlib():
    x = ctypes.CDLL("libX11.so.6")
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XScreenCount.argtypes = [ctypes.c_void_p]
    x.XRootWindow.restype = ctypes.c_ulong
    x.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                             ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                             ctypes.POINTER(ctypes.c_uint)]
    x.XInternAtom.restype = ctypes.c_ulong
    x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x.XGetWindowProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
                                     ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                     ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
                                     ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)]
    x.XFree.argtypes = [ctypes.c_void_p]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    return x


def classes(display):
    """Each top-level window's screen and raw WM_CLASS bytes, where it has one."""
    x = xlib()
    d = x.XOpenDisplay(display.encode())
    if not d:
        raise RuntimeError(f"cannot open {display}")
    wm_class = x.XInternAtom(d, b"WM_CLASS", 0)
    found = []
    for screen in range(x.XScreenCount(d)):
        root, parent = ctypes.c_ulong(), ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)()
        n = ctypes.c_uint()
        x.XQueryTree(d, x.XRootWindow(d, screen), ctypes.byref(root), ctypes.byref(parent), ctypes.byref(children),
                     ctypes.byref(n))
        for i in range(n.value):
            kind, fmt = ctypes.c_ulong(), ctypes.c_int()
            items, after = ctypes.c_ulong(), ctypes.c_ulong()
            data = ctypes.c_void_p()
            x.XGetWindowProperty(d, children[i], wm_class, 0, 64, 0, 0, ctypes.byref(kind), ctypes.byref(fmt),
                                 ctypes.byref(items), ctypes.byref(after), ctypes.byref(data))
            if data.value:
                found.append((screen, ctypes.string_at(data.value, items.value)))
                x.XFree(data)
        if children:
            x.XFree(children)
    x.XCloseDisplay(d)
    return found


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xvfb, display = start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="screens-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text('[program]\ncommand = ["sh", "-c", "sleep 60"]\n')
    env = dict(os.environ, DISPLAY=display + ".1", HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        ours = []
        for _ in range(40):
            time.sleep(0.25)
            ours = [(s, c) for s, c in classes(display + ".0") if c.startswith(b"puritty\0")]
            if ours:
                break
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    print(f"puritty's windows (screen, WM_CLASS): {ours!r}")
    wrong = []
    if not ours:
        wrong.append("no window with puritty's WM_CLASS on either screen")
    for screen, cls in ours:
        if screen != 1:
            wrong.append(f"the window is on screen {screen}, DISPLAY named 1")
        if cls != b"puritty\0Puritty\0":
            wrong.append(f"WM_CLASS is {cls!r} ({len(cls)} bytes), want b'puritty\\x00Puritty\\x00' (16)")
    if wrong:
        sys.exit("screens.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

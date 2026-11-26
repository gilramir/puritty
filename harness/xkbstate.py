#!/usr/bin/env python3
"""The XKB state gate (the code review's X21): a modifier pressed and let
go wakes puritty with its key events only, not with an XKB StateNotify
for each change of the keyboard's state, which nothing reads.

puritty runs on Xvfb through a proxy that reads what the server sends it
(`maximized.py`'s proxy, the other way). With its window focused, Shift
is pressed and let go PRESSES times by xdotool. Counted from the first
press: XKB StateNotify events sent to puritty must be 0. Before X21 the
window selected them and kept an xkb_state up to date with them, read
nowhere: two a press and release.

usage (from puritty's devbox, after app/build.sh):
    harness/xkbstate.py [PURITTY]
"""
import ctypes
import getpass
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its Xvfb)
import hosts  # noqa: E402  (its xdotool)

APP = ROOT / "app" / "puritty"
PRESSES = 10
XKB_STATE_NOTIFY = 2


def xkb_base(display):
    """The XKEYBOARD extension's first event code on `display`."""
    x = ctypes.CDLL("libX11.so.6")
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XQueryExtension.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int),
                                  ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    d = x.XOpenDisplay(display.encode())
    op, event, error = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
    x.XQueryExtension(d, b"XKEYBOARD", ctypes.byref(op), ctypes.byref(event), ctypes.byref(error))
    x.XCloseDisplay(d)
    return event.value


class Events:
    """The (code, detail) of each event the server sent the first client."""

    def __init__(self):
        self.seen = []
        self.lock = threading.Lock()

    def mark(self):
        with self.lock:
            return len(self.seen)

    def since(self, at):
        with self.lock:
            return list(self.seen[at:])


def pump(src, dst, events=None):
    """Bytes from `src` to `dst`; from the server, its events noted."""
    buf, setup = b"", events is not None
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
            if events is None:
                continue
            buf += data
            while True:
                if setup:
                    # the setup's answer: 8 bytes and its length in words at 6
                    if len(buf) < 8:
                        break
                    size = 8 + struct.unpack_from("<H", buf, 6)[0] * 4
                    if len(buf) < size:
                        break
                    buf, setup = buf[size:], False
                    continue
                if len(buf) < 32:
                    break
                code = buf[0] & 0x7F
                size = 32
                if code == 1 or code == 35:
                    # a reply, or a generic event: more words, counted at 4
                    size += struct.unpack_from("<I", buf, 4)[0] * 4
                if len(buf) < size:
                    break
                if code > 1:
                    with events.lock:
                        events.seen.append((code, buf[1]))
                buf = buf[size:]
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def proxy(display, events):
    """A TCP display that passes through to `display`'s socket, noting the
    events sent to the first client; answers its display name."""
    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen()
    port = lsock.getsockname()[1]
    if port < 6000:
        lsock.close()
        return proxy(display, events)
    first = [True]

    def accept():
        while True:
            try:
                c, _ = lsock.accept()
            except OSError:
                return
            s = socket.socket(socket.AF_UNIX)
            s.connect(f"/tmp/.X11-unix/X{display.lstrip(':')}")
            noted = events if first[0] else None
            first[0] = False
            threading.Thread(target=pump, args=(c, s), daemon=True).start()
            threading.Thread(target=pump, args=(s, c, noted), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    return f"127.0.0.1:{port - 6000}", lsock


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    base = xkb_base(display)
    events = Events()
    via, lsock = proxy(display, events)
    home = Path(tempfile.mkdtemp(prefix="xkbstate-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text('[program]\ncommand = ["sleep", "60"]\n')
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh", USER=getpass.getuser(),
               PURITTY_NO_XIM="1")
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)],
                             env=dict(env, DISPLAY=via), stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(3)
        xenv = dict(env, DISPLAY=display)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=xenv, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=xenv, check=True)
        time.sleep(1)
        at = events.mark()
        for _ in range(PRESSES):
            subprocess.run([xdo, "keydown", "shift"], env=xenv, check=True)
            subprocess.run([xdo, "keyup", "shift"], env=xenv, check=True)
            time.sleep(0.1)
        time.sleep(1)
        after = events.since(at)
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        lsock.close()
        xvfb.kill()
    states = sum(1 for code, detail in after if code == base and detail == XKB_STATE_NOTIFY)
    keys = sum(1 for code, _ in after if code in (2, 3))
    print(f"Shift pressed and let go {PRESSES} times: {keys} key events, {states} XKB StateNotify")
    wrong = []
    if keys < 2 * PRESSES:
        wrong.append(f"{keys} key events, want {2 * PRESSES}")
    if states:
        wrong.append(f"{states} XKB StateNotify, want 0")
    if wrong:
        sys.exit("xkbstate.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

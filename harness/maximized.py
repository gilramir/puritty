#!/usr/bin/env python3
"""The resize round-trip gate (docs/window-state.md WP10, the code review's
X9): a resize asks the X server nothing it already knows.

puritty runs on Xvfb through a proxy that counts the requests it sends.
After it has opened, `xdotool windowsize` resizes it RESIZES times, each a
Resized for puritty, whose handler asks Window.isMaximized. Counted from
the first resize on: InternAtom requests for _NET_WM_STATE and its two
MAXIMIZED atoms, which the window interns once at open, must be 0; and
GetProperty requests at most one a resize, for _NET_WM_STATE itself.
Before WP10, each resize interned the three atoms again, each a blocking
round trip.

usage (from puritty's devbox, after app/build.sh):
    harness/maximized.py [PURITTY]
"""
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
RESIZES = 6
INTERN_ATOM, GET_PROPERTY = 16, 20


class Counter:
    """The client's requests, as (opcode, InternAtom's name or None), in order."""

    def __init__(self):
        self.requests = []
        self.lock = threading.Lock()

    def mark(self):
        with self.lock:
            return len(self.requests)

    def since(self, at):
        with self.lock:
            return list(self.requests[at:])


def pump(src, dst, counter=None):
    buf, setup = b"", counter is not None
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
            if counter is None:
                continue
            buf += data
            while True:
                if setup:
                    # byte order, then name and data lengths at 6 and 8
                    if len(buf) < 12:
                        break
                    assert buf[0:1] == b"l", "the proxy reads only little-endian clients"
                    n, d = struct.unpack_from("<HH", buf, 6)
                    size = 12 + (n + 3) // 4 * 4 + (d + 3) // 4 * 4
                    if len(buf) < size:
                        break
                    buf, setup = buf[size:], False
                    continue
                if len(buf) < 4:
                    break
                length = struct.unpack_from("<H", buf, 2)[0] * 4
                if length == 0:
                    if len(buf) < 8:
                        break
                    length = struct.unpack_from("<I", buf, 4)[0] * 4
                if len(buf) < length:
                    break
                op, name = buf[0], None
                if op == INTERN_ATOM:
                    k = struct.unpack_from("<H", buf, 4)[0]
                    name = buf[8:8 + k].decode("latin-1")
                with counter.lock:
                    counter.requests.append((op, name))
                buf = buf[length:]
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def proxy(display, counter):
    """A TCP display that passes through to `display`'s socket, counting
    the first client's requests; answers its display name."""
    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen()
    port = lsock.getsockname()[1]
    if port < 6000:
        lsock.close()
        return proxy(display, counter)
    first = [True]

    def accept():
        while True:
            try:
                c, _ = lsock.accept()
            except OSError:
                return
            s = socket.socket(socket.AF_UNIX)
            s.connect(f"/tmp/.X11-unix/X{display.lstrip(':')}")
            counted = counter if first[0] else None
            first[0] = False
            threading.Thread(target=pump, args=(c, s, counted), daemon=True).start()
            threading.Thread(target=pump, args=(s, c), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    return f"127.0.0.1:{port - 6000}", lsock


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    counter = Counter()
    via, lsock = proxy(display, counter)
    home = Path(tempfile.mkdtemp(prefix="maximized-"))
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text('[program]\ncommand = ["sleep", "60"]\n')
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh", USER=getpass.getuser())
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)],
                             env=dict(env, DISPLAY=via), stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(3)
        xenv = dict(env, DISPLAY=display)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=xenv, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        at = counter.mark()
        for i in range(RESIZES):
            subprocess.run([xdo, "windowsize", win, str(500 + 40 * i), str(300 + 30 * i)], env=xenv, check=True)
            time.sleep(0.5)
        time.sleep(1)
        after = counter.since(at)
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        lsock.close()
        xvfb.kill()
    interned = [n for op, n in after if op == INTERN_ATOM and n and n.startswith("_NET_WM_STATE")]
    props = sum(1 for op, _ in after if op == GET_PROPERTY)
    print(f"{RESIZES} resizes: {len(after)} requests, {len(interned)} _NET_WM_STATE atoms interned, {props} GetProperty")
    wrong = []
    if not after:
        wrong.append("no requests counted")
    if interned:
        wrong.append(f"interned {len(interned)} _NET_WM_STATE atoms, want 0")
    if props > RESIZES:
        wrong.append(f"{props} GetProperty, want at most {RESIZES}")
    if wrong:
        sys.exit("maximized.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

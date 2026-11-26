#!/usr/bin/env python3
"""The slow paste gate (docs/phase3-select.md §31, the code review's X12):
a paste that is still coming after 10 s is not given up, and a second
paste asked for meanwhile does not mix into it.

puritty runs on Xvfb, its tab a program that writes what it receives
(raw) to a file. A clipboard owner here (python-xlib) answers a request
for UTF8_STRING with INCR and then sends PIECES pieces of 1,000 bytes, a
second apart, each when the last is deleted: the transfer takes about
fifteen seconds and makes progress every second. Paste is pressed, then
pressed again at 11 s, while pieces still come. The program must receive
the pieces once, in order, nothing else. Before X12 the 10 s were
counted from the paste's start: the second press began a new paste on
the same property while the first's owner still wrote to it, and the
pieces came twice or out of order.

usage (from puritty's devbox, after app/build.sh):
    harness/slowpaste.py [PURITTY]
"""
import getpass
import os
import select
import shutil
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
PIECES = 15
RECORD = "stty raw -echo; exec cat > \"$1\""


def piece(i):
    line = f"piece {i:02d} ".encode()
    return (line * (1000 // len(line) + 1))[:999] + b"\n"


def owner(display, ready, stop):
    """Owns CLIPBOARD; each request for UTF8_STRING is answered with INCR
    and PIECES pieces a second apart. Each transfer is served on its own."""
    from Xlib import X, Xatom, display as xdisplay
    from Xlib.protocol import event
    d = xdisplay.Display(display)
    w = d.screen().root.create_window(0, 0, 1, 1, 0, X.CopyFromParent)
    clipboard, utf8, incr, targets = (d.intern_atom(n) for n in ("CLIPBOARD", "UTF8_STRING", "INCR", "TARGETS"))
    w.set_selection_owner(clipboard, X.CurrentTime)
    d.flush()
    ready.set()
    transfers = {}  # (requestor, property) -> [next piece, due time or None]
    while not stop.is_set():
        now = time.time()
        for (req, prop), t in list(transfers.items()):
            if t[1] is not None and now >= t[1]:
                data = piece(t[0]) if t[0] < PIECES else b""
                req.change_property(prop, utf8, 8, data)
                t[0] += 1
                t[1] = None
                if not data:
                    del transfers[(req, prop)]
        d.flush()
        if not d.pending_events():
            select.select([d.fileno()], [], [], 0.05)
            continue
        e = d.next_event()
        if e.type == X.SelectionRequest:
            req, prop = e.requestor, e.property
            if e.target == targets:
                req.change_property(prop, Xatom.ATOM, 32, [targets, utf8])
            elif e.target == utf8:
                req.change_attributes(event_mask=X.PropertyChangeMask)
                req.change_property(prop, incr, 32, [PIECES * 1000])
                transfers[(req, prop)] = [0, None]
            else:
                prop = X.NONE
            req.send_event(event.SelectionNotify(time=e.time, requestor=req, selection=e.selection, target=e.target,
                                                 property=prop))
            d.flush()
        elif e.type == X.PropertyNotify and e.state == X.PropertyDelete:
            for (req, prop), t in transfers.items():
                if req.id == e.window.id and prop == e.atom and t[1] is None:
                    t[1] = time.time() + 1.0
    try:
        d.close()
    except Exception:
        pass


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="slowpaste-"))
    out = home / "received"
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "record.sh").write_text(RECORD + "\n")
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "{home / "record.sh"}", "{out}"]\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser(), PURITTY_NO_XIM="1")
    ready, stop = threading.Event(), threading.Event()
    p = None
    serving = threading.Thread(target=owner, args=(display, ready, stop), daemon=True)
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(1)
        serving.start()
        ready.wait(5)
        subprocess.run([xdo, "key", "ctrl+shift+v"], env=env, check=True)
        time.sleep(11)
        subprocess.run([xdo, "key", "ctrl+shift+v"], env=env, check=True)
        time.sleep(PIECES - 11 + 5)
        got = out.read_bytes() if out.exists() else b""
    finally:
        stop.set()
        if serving.is_alive():
            serving.join(2)
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    want = b"".join(piece(i) for i in range(PIECES)).replace(b"\n", b"\r")
    order = [int(got[i + 6:i + 8]) for i in range(0, len(got) - 8, 1000) if got[i:i + 6] == b"piece "]
    print(f"received {len(got)} bytes, pieces in order {order}; want {len(want)} bytes, 0 to {PIECES - 1} once")
    if got != want:
        sys.exit(f"slowpaste.py: the paste came {len(got)} bytes, not the {len(want)} sent once in order (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

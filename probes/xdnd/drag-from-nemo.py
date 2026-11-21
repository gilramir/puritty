#!/usr/bin/env python3
"""Drag files from Nemo onto the XDND probe (target.py), under Xvfb, and
keep what the probe logged (puritty docs/sftp.md FT21). Run in devbox:

    probes/xdnd/drag-from-nemo.py OUT-DIR

It makes a folder of files with names that test the encoding (spaces, a
quote and a dollar, Korean in UTF-8, Korean in EUC-KR's bytes) and a
subfolder, opens Nemo on it in list view, and drags: one file, then all
of them (clicked with Ctrl held), each onto the probe. A screenshot of the screen before
each drag is kept, to place the pointer.
"""
import os, subprocess, sys, time, zlib, struct, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import hosts  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
XDO = hosts.xdotool()
DISPLAY = ":79"
env = dict(os.environ, DISPLAY=DISPLAY, GTK_THEME="Adwaita", NO_AT_BRIDGE="1")


def xdo(*args):
    return subprocess.run([XDO, *map(str, args)], env=env, capture_output=True, text=True).stdout


def shot(path):
    from Xlib import display, X
    d = display.Display(DISPLAY)
    r = d.screen().root
    g = r.get_geometry()
    img = r.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xFFFFFFFF)
    data = img.data
    rows = b"".join(b"\0" + bytes(c for i in range(g.width) for c in data[(y * g.width + i) * 4:(y * g.width + i) * 4 + 3][::-1])
                    for y in range(g.height))
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", g.width, g.height, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


files = out / "files"
subprocess.run(["rm", "-rf", str(files)])
files.mkdir()
for n in ["a plain.txt", "it's $HOME.txt", "한글 이름.txt"]:
    (files / n).write_text("x\n")
with open(os.path.join(os.fsencode(files), "euc-kr ".encode() + "한글".encode("euc-kr") + b".txt"), "w") as f:
    f.write("x\n")
(files / "a folder").mkdir()

xv = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
time.sleep(1)
procs = []
try:
    # another file manager by FM=…, Dolphin's from nix (FT21)
    fm = os.environ.get("FM")
    cmd = [fm, str(files)] if fm else ["nemo", "--no-desktop", "--geometry=640x700+0+0", str(files)]
    # in a process group of its own, so that its D-Bus session's gvfs
    # daemons are stopped with it (harness/drop.py's `ended`)
    nemo = subprocess.Popen(["dbus-run-session", "--", *cmd], env=dict(env, QT_QPA_PLATFORM="xcb"),
                            stdout=open(out / "nemo.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    procs.append(nemo)
    time.sleep(5)
    win = xdo("search", "--class", "dolphin" if fm else "nemo").split()
    for wid in win:
        xdo("windowmove", wid, 0, 0)
        xdo("windowsize", wid, 640, 700)
    time.sleep(1)
    # list view, so rows are where they can be found: Ctrl+2
    if win:
        xdo("windowfocus", win[-1])
        xdo("key", "ctrl+2")
    time.sleep(1.5)
    shot(out / "nemo.png")
    print("nemo windows:", win, "screenshot:", out / "nemo.png")
    # where to grab: given on the command line after a first look
    grabs = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
    for n, g in enumerate(grabs):
        log = open(out / f"drag-{n}.jsonl", "w")
        t = subprocess.Popen([sys.executable, str(HERE / "target.py"), "--x", "700", "--y", "100"], env=env, stdout=log,
                             stderr=subprocess.STDOUT)
        procs.append(t)
        time.sleep(1.5)
        if g.get("keys"):
            xdo("windowfocus", win[-1])
            for k in g["keys"]:
                xdo("key", k)
            time.sleep(0.5)
        x, y = g["at"]
        if g.get("select"):
            # the first clicked, the rest added with Ctrl held
            sx, sy = g["select"][0]
            xdo("mousemove", sx, sy)
            xdo("click", 1)
            for sx, sy in g["select"][1:]:
                xdo("mousemove", sx, sy)
                xdo("keydown", "ctrl")
                xdo("click", 1)
                xdo("keyup", "ctrl")
            time.sleep(0.5)
        if g.get("click"):
            xdo("mousemove", x, y)
            xdo("click", 1)
            time.sleep(0.5)
        xdo("mousemove", x, y)
        time.sleep(0.3)
        xdo("mousedown", 1)
        for i in range(1, 31):
            xdo("mousemove", x + (950 - x) * i // 30, y + (350 - y) * i // 30)
            time.sleep(0.03)
        time.sleep(0.5)
        xdo("mousemove", 951, 351)
        time.sleep(0.5)
        xdo("mouseup", 1)
        try:
            t.wait(15)
        except subprocess.TimeoutExpired:
            t.kill()
        log.close()
        print(f"drag {n}:", (out / f"drag-{n}.jsonl").read_text())
        shot(out / f"after-{n}.png")
finally:
    sys.path.insert(0, str(ROOT / "packages" / "ssh" / "tests"))
    from drop import ended  # noqa: E402
    ended(procs)
    xv.kill()

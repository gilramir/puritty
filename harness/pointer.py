#!/usr/bin/env python3
"""The pointer gate (docs/phase3-select.md §4, §11): visiterm's window on
Xvfb, the mouse driven with xdotool, and what a program that asked for
mouse reports receives.

The encoder is the mouse gate's (harness/mouse.py, against libghostty-vt);
this one holds the path from X to it: that presses, releases, wheel steps
and motion reach the encoder with the right buttons, modifiers and cells,
that X sends every motion only while mode 1003 asks for it, and that Shift
takes the mouse back. Each case starts visiterm (default settings, 96 dpi,
no IME, a fresh home) on a program that sets the case's modes and records
every byte it receives on a raw terminal, runs the case's actions, and pins
the bytes to corpus/pointer/CASE.txt.

Actions: move:X,Y moves the pointer to a pixel of the window; click:B,
down:B, up:B for button B (X's numbers: 1 left, 2 middle, 3 right, 4 and 5
the wheel); double:B and triple:B click it two and three times 100 ms
apart; key-down:K and key-up:K hold a key (shift, ctrl); key:K presses one
(xdotool's names); sleep:S; primary and clipboard read that selection with
xclip and add it to the case's pin, its length when it is long
(docs/phase3-select.md §14). A case may give a shell command run before
the program reads, to print what it selects.

usage:
    harness/pointer.py            every case
    harness/pointer.py -f drag    cases whose name contains "drag"
    harness/pointer.py --update   write the pins; read the diff first

Build visiterm first (app/build.sh). Run from visiterm's devbox (Xvfb);
xdotool is built as the IME gate builds it (harness/ime/imes.nix).
"""
import argparse, os, signal, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "corpus" / "pointer"
WORK = ROOT / ".harness-work" / "pointer"
VISITERM = ROOT / "app" / "visiterm"
DISPLAY = ":82"

SGR = "\\e[?1000h\\e[?1006h"
TEXT = "printf 'hello world, again\\r\\nsecond line\\r\\n'"
# 5,000 lines of 64 characters: 325,000 bytes, more than an INCR piece
LARGE = "seq -f '%063g' 1 5000"
# name, the modes the program sets, its actions. The default font at 96 dpi
# has a cell of 9 by 17 pixels, so pixel (50, 30) is in column 6, row 2.
CASES = [
    ("sgr-click", SGR, "move:50,30 click:1"),
    ("sgr-buttons", SGR, "move:50,30 click:2 click:3"),
    ("sgr-wheel", SGR, "move:50,30 click:4 click:5 click:4"),
    ("sgr-modifiers", SGR, "move:50,30 key-down:ctrl click:1 key-up:ctrl key-down:alt click:1 key-up:alt"),
    ("sgr-shift-is-visiterms", SGR, "move:50,30 key-down:shift click:1 down:1 move:100,30 up:1 click:4 key-up:shift click:1"),
    ("x10-click", "\\e[?1000h", "move:50,30 click:1"),
    ("x10-only-presses", "\\e[?9h", "move:50,30 click:1 click:4"),
    ("normal-no-motion", SGR, "move:50,30 down:1 move:100,30 up:1"),
    ("button-drag", "\\e[?1002h\\e[?1006h", "move:50,30 down:1 move:100,30 move:101,31 move:100,60 up:1 move:200,60"),
    ("button-drag-outside", "\\e[?1002h\\e[?1006h", "move:50,30 down:1 move:900,30 up:1"),
    ("any-motion", "\\e[?1003h\\e[?1006h", "move:50,30 move:200,100 move:201,101 click:1"),
    ("any-motion-off-again", "\\e[?1003h\\e[?1006h\\e[?1003l\\e[?1000h", "move:50,30 move:200,100 click:1"),
    ("pixels", "\\e[?1000h\\e[?1016h", "move:50,30 click:1"),
    ("urxvt", "\\e[?1000h\\e[?1015h", "move:50,30 click:3"),
    ("utf8-far", "\\e[?1000h\\e[?1005h", "move:700,400 click:1"),
    ("none-asked", "", "move:50,30 click:1 click:4"),
    # the wheel no program asked for (docs/phase3-select.md §11): on the
    # alternate screen with 1007, three arrows a step, in DECCKM's form
    ("alt-wheel-arrows", "\\e[?1049h", "move:50,30 click:4 click:5"),
    ("alt-wheel-decckm", "\\e[?1049h\\e[?1h", "move:50,30 click:4"),
    ("alt-wheel-1007-reset", "\\e[?1049h\\e[?1007l", "move:50,30 click:4"),
    ("alt-wheel-reported", "\\e[?1049h" + SGR, "move:50,30 click:4"),
    # selection (docs/phase3-select.md §14): rows 0 and 1 are
    # "hello world, again" and "second line"; a cell is 9 by 17
    ("select-drag", "", "move:4,8 down:1 move:40,8 up:1 primary", TEXT),
    ("select-drag-rows", "", "move:58,8 down:1 move:40,25 up:1 primary", TEXT),
    ("select-drag-back", "", "move:40,25 down:1 move:58,8 up:1 primary", TEXT),
    ("select-click-none", "", "move:4,8 down:1 move:40,8 up:1 sleep:0.6 click:1 sleep:0.6 primary", TEXT),
    ("select-double", "", "move:58,8 double:1 primary", TEXT),
    ("select-double-drag", "", "move:58,8 click:1 down:1 move:130,8 up:1 primary", TEXT),
    ("select-triple", "", "move:40,25 triple:1 primary", TEXT),
    ("select-copy", "", "move:4,8 down:1 move:40,8 up:1 key:ctrl+shift+c clipboard primary", TEXT),
    ("select-shift", SGR, "move:4,8 key-down:shift down:1 move:40,8 up:1 key-up:shift primary", TEXT),
    ("select-large", "", "key:shift+Home sleep:0.5 move:0,0 down:1 key:shift+End sleep:0.5 move:715,400 up:1 sleep:0.5 primary", LARGE),
]


def escaped(b):
    out = []
    for c in b.decode("utf-8", "backslashreplace"):
        if c == "\x1b": out.append("\\e")
        elif c == "\\": out.append("\\\\")
        elif ord(c) < 0x20 or c == "\x7f": out.append(f"\\x{ord(c):02x}")
        else: out.append(c)
    return "".join(out)


def xdotool():
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), "xdotool"], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0] + "/bin/xdotool"


def selection(env, which):
    try:
        b = subprocess.run(["xclip", "-o", "-selection", which], env=env, capture_output=True, timeout=10).stdout
    except subprocess.TimeoutExpired:
        return f"{which} (timed out)"
    if len(b) > 200:
        return f"{which} {len(b)} bytes, {b.count(b'\n') + 1} lines, ending {escaped(b[-20:])}"
    return f"{which} {escaped(b)}"


def run(xdo, env, modes, actions, before=""):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "received"
        read = []
        v = subprocess.Popen([str(VISITERM), "--", "sh", "-c", f"{before}{';' if before else ''} printf '{modes}'; stty raw -echo; exec cat > {out}"],
                             env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        win = subprocess.run([xdo, "search", "--sync", "--name", "visiterm"], env=env, capture_output=True,
                             text=True).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(0.5)
        for a in actions.split():
            kind, _, arg = a.partition(":")
            if kind == "move":
                x, y = arg.split(",")
                cmd = ["mousemove", "--window", win, "--sync", x, y]
            elif kind == "click":
                cmd = ["click", arg]
            elif kind == "down":
                cmd = ["mousedown", arg]
            elif kind == "up":
                cmd = ["mouseup", arg]
            elif kind == "key-down":
                cmd = ["keydown", arg]
            elif kind == "key-up":
                cmd = ["keyup", arg]
            elif kind == "key":
                cmd = ["key", arg]
            elif kind == "double":
                cmd = ["click", "--repeat", "2", "--delay", "100", arg]
            elif kind == "triple":
                cmd = ["click", "--repeat", "3", "--delay", "100", arg]
            elif kind in ("primary", "clipboard"):
                time.sleep(0.3)
                read.append(selection(env, kind))
                continue
            elif kind == "sleep":
                time.sleep(float(arg))
                continue
            # a pointer outside the window is still the window's during a drag
            subprocess.run([xdo, *cmd], env=env, check=kind != "move", stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            time.sleep(0.15)
        time.sleep(0.7)
        v.send_signal(signal.SIGTERM)
        try:
            v.wait(timeout=5)
        except subprocess.TimeoutExpired:
            v.kill()
            v.wait()
        received = out.read_bytes() if out.exists() else b""
    return "bytes " + escaped(received) + "\n" + "".join(r + "\n" for r in read)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-f", dest="filter", default="")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    xdo = xdotool()
    home = WORK / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DISPLAY=DISPLAY, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               VISITERM_NO_XIM="1", VISITERM_DPI="96", LANG="C.UTF-8")
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    fails = runs = 0
    try:
        for name, modes, actions, *before in CASES:
            if a.filter not in name:
                continue
            runs += 1
            got = run(xdo, env, modes, actions, *before)
            pin = PINS / f"{name}.txt"
            if a.update:
                PINS.mkdir(parents=True, exist_ok=True)
                pin.write_text(got)
                print(f"wrote {name}: {got.strip()}")
            elif not pin.exists() or pin.read_text() != got:
                fails += 1
                print(f"FAIL {name}\n  want {pin.read_text().strip() if pin.exists() else '(no pin)'}\n  got  {got.strip()}")
    finally:
        xvfb.terminate()
        xvfb.wait()
    if not a.update:
        print(f"{'FAIL' if fails else 'ok'}: {runs - fails} of {runs} cases")
    return 1 if fails else 0


sys.exit(main())

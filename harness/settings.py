#!/usr/bin/env python3
"""The settings window's gate (docs/settings.md ST19, ST20): `puritty
settings` on Xvfb, driven with xdotool's keys, its file held to a pin.

Each case starts the window on a settings file (or none), presses keys,
and holds what the file then says to harness/settings/expected/NAME.toml
("(none)" for no file). Two cases hold more:

- `hand-edit`: the file changed by hand while the window is open, then a
  key that changes the same setting; the window must have read the edit,
  or the key's change is not the one pinned;
- `terminal-follows`: a terminal puritty beside the window, whose picture
  (PURITTY_SHOT) must take the background typed in the window.

The window's own picture of each case is kept in .harness-work/settings,
to look at.

usage (from puritty's devbox, after app/build.sh):
    harness/settings.py              every case
    harness/settings.py -f undo      cases whose name contains "undo"
    harness/settings.py --update     write the pins; read the diff first
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its fonts)
import reload  # noqa: E402  (its pictures)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "settings"
PINS = ROOT / "harness" / "settings" / "expected"
DISPLAY = ":86"

DOWN, ENTER, BACKSPACE = "Down", "Return", "BackSpace"

# from the first setting to the Hosts page's first row
TO_HOSTS = ["Tab", "Tab"] + ["Down"] * 7 + ["Right"]

HOSTS = '# my hosts\n[hosts.box]   # the build box\nhost = "b.example.com"\nuser = "me"\n\n[hosts.box.colours]\nbackground = "#2a1010"\n'

# name, the file before (None: none), the keys, and what else is done
CASES = [
    ("size-typed", None, [DOWN, ENTER, BACKSPACE, BACKSPACE, ("type", "14"), ENTER]),
    ("bold-toggled", None, [DOWN, DOWN, DOWN, DOWN, DOWN, ENTER]),
    ("reset", '[font]\nsize = 13\n\n[colours]\nbackground = "#102030"\n', [DOWN, "Delete"]),
    ("comments-kept", "# mine\n[window]\ncolumns = 100 # wide\n", [DOWN, DOWN, DOWN, DOWN, DOWN, ENTER]),
    ("undo", None, [DOWN, DOWN, DOWN, DOWN, DOWN, ENTER, "ctrl+z"]),
    ("search-and-choice", None, ["ctrl+f", ("type", "paste"), DOWN, ENTER]),
    # a font chosen from the system's, offered as its name is typed
    ("font-chosen", None, [ENTER] + [BACKSPACE] * 16 + [("type", "fira"), DOWN, ENTER]),
    ("typed-not-taken", None, [DOWN, ENTER, BACKSPACE, BACKSPACE, ("type", "2"), ENTER, "Escape"]),
    # the window reads an edit by hand: bold, turned on by hand, is turned
    # off by Enter; had the window not read it, Enter would turn it on
    ("hand-edit", "[font]\nsize = 13\n", [("hand", "[font]\nsize = 13\n\n[colours]\nbold_is_bright = true\n"),
                                          DOWN, DOWN, DOWN, DOWN, DOWN, ENTER]),
    # hosts (ST25): the Hosts page is the last; a new host and its fields,
    # a host removed, one renamed with the table under it, one copied
    ("host-new", None, TO_HOSTS + [DOWN, ENTER, ("type", "lab"), ENTER, ENTER] + [BACKSPACE] * 3
                       + [("type", "lab.example.com"), ENTER, DOWN, ENTER, ("type", "me"), ENTER]),
    ("host-removed", HOSTS, TO_HOSTS + [DOWN, DOWN, "Delete"]),
    ("host-renamed", HOSTS, TO_HOSTS + [DOWN, DOWN, "Right", "Up", ENTER] + [BACKSPACE] * 3 + [("type", "lab"), ENTER]),
    ("host-copied", HOSTS, TO_HOSTS + [DOWN, DOWN, "ctrl+d"]),
    # the mouse (ST27): a click on a value changes it, one on the reset
    # mark resets it, a click on a page shows it. Clicks are at pixels of the
    # drawn window (docs/settings-gui.md SG3, SG8): at the gate's font a
    # line is 17 pixels, the list begins at 51 and a setting is 68 tall but
    # for the colour scheme's, whose description takes 119 (SG12), so
    # "bold is bright" is 442 to 510; a value's box begins at x 469 and the
    # reset mark at 706, and the side bar's pages are 32 tall from 51.
    ("click-value", None, [("click", 489, 476, 1)]),
    ("click-reset", "[colours]\nbold_is_bright = true\n", [("click", 716, 476, 1)]),
    ("click-page-and-value", None, [("click", 50, 99, 1), ("click", 489, 85, 1)] + [BACKSPACE] * 2 + [("type", "100"), ENTER]),
    ("terminal-follows", None, [DOWN, DOWN, DOWN, DOWN, ENTER] + [BACKSPACE] * 7 + [("type", "#203040"), ENTER]),
]


def xdotool():
    """The IME gate's xdotool (harness/ime/imes.nix), as harness/pointer.py
    builds it; that script runs its gate when imported, so it is not."""
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), "xdotool"], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0] + "/bin/xdotool"


def run_case(env0, xdo, name, before, keys):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    config = home / "config" / "puritty"
    config.mkdir(parents=True)
    path = config / "config.toml"
    if before is not None:
        path.write_text(before)
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"))
    terminal = None
    if name == "terminal-follows":
        terminal = subprocess.Popen([str(APP), "--", "sh", "-c", "exec sleep 600"],
                                    env=dict(env, PURITTY_SHOT=str(home / "terminal.ppm")),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
    log = open(home / "stderr.txt", "w")
    window = subprocess.Popen([str(APP), "settings"], env=dict(env, PURITTY_SHOT=str(home / "window.ppm")),
                              stdout=subprocess.DEVNULL, stderr=log)
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "puritty settings"], env=env, capture_output=True,
                             text=True, timeout=10).stdout.split()[0]
        # with no window manager both windows open at the corner, and the
        # picture of a covered window is not defined
        subprocess.run([xdo, "windowmove", "--sync", win, "760", "0"], env=env, check=True)
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(0.5)
        for key in keys:
            if isinstance(key, tuple) and key[0] == "type":
                subprocess.run([xdo, "type", "--delay", "40", key[1]], env=env, check=True)
            elif isinstance(key, tuple) and key[0] == "click":
                _, x, y, n = key
                subprocess.run([xdo, "mousemove", "--window", win, str(x), str(y)], env=env, check=True)
                subprocess.run([xdo, "click", "--repeat", str(n), "--delay", "80", "1"], env=env, check=True)
            elif isinstance(key, tuple) and key[0] == "hand":
                path.write_text(key[1])
                time.sleep(0.5)
            else:
                subprocess.run([xdo, "key", "--delay", "40", key], env=env, check=True)
            time.sleep(0.15)
        time.sleep(0.8)
    finally:
        window.terminate()
        window.wait(5)
    got = path.read_text() if path.exists() else "(none)\n"
    extra = None
    if terminal is not None:
        time.sleep(0.5)
        pic = reload.read_ppm(home / "terminal.ppm")
        terminal.terminate()
        terminal.wait(5)
        if pic is None:
            extra = "the terminal drew nothing"
        else:
            # an empty cell well inside the window: the background
            row = pic[len(pic) * 3 // 4]
            x = (len(row) // 3) * 3 // 4
            rgb = row[x * 3:x * 3 + 3]
            if rgb != bytes([0x20, 0x30, 0x40]):
                extra = f"the terminal's background is #{rgb.hex()}, not #203040"
    shot = home / "window.ppm"
    if shot.exists():
        rows = reload.read_ppm(shot)
        if rows:
            reload.save_png(home / "window.png", rows)
    return got, extra


def windows_named(env, xdo, name):
    out = subprocess.run([xdo, "search", "--name", f"^{name}$"], env=env, capture_output=True, text=True).stdout
    return out.split()


def run_opening(env0, xdo, name):
    """Opening the window (ST9): Ctrl+Comma in a terminal, twice, opens one;
    a second `puritty settings` raises the first and ends."""
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    (home / "config" / "puritty").mkdir(parents=True)
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"))
    started = []
    try:
        if name == "ctrl-comma":
            t = subprocess.Popen([str(APP), "--title", "reload-term", "--", "sh", "-c", "exec sleep 600"], env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started.append(t)
            win = subprocess.run([xdo, "search", "--sync", "--name", "reload-term"], env=env, capture_output=True,
                                 text=True, timeout=10).stdout.split()[0]
            subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
            subprocess.run([xdo, "key", "ctrl+comma"], env=env, check=True)
            time.sleep(1.5)
            first = len(windows_named(env, xdo, "puritty settings"))
            subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
            subprocess.run([xdo, "key", "ctrl+comma"], env=env, check=True)
            time.sleep(1.5)
            second = len(windows_named(env, xdo, "puritty settings"))
            got = f"after one: {first}; after two: {second}\n"
        else:
            a = subprocess.Popen([str(APP), "settings"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started.append(a)
            time.sleep(1.5)
            b = subprocess.run([str(APP), "settings"], env=env, capture_output=True, timeout=10)
            got = f"the second ended with {b.returncode}; windows: {len(windows_named(env, xdo, 'puritty settings'))}\n"
    finally:
        for w in windows_named(env, xdo, "puritty settings"):
            subprocess.run([xdo, "windowclose", w], env=env)
        for p in started:
            p.terminate()
            p.wait(5)
        time.sleep(0.3)
    return got, None


OPENING = ["ctrl-comma", "second-raises"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-f", dest="filter", default="")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if not APP.exists():
        sys.exit("settings.py: build app/puritty first (app/build.sh)")
    xdo = xdotool()
    conf = pixels.write_fonts_conf()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96",
               LANG="C.UTF-8")
    env.pop("LC_ALL", None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1700x900x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    fails = runs = 0
    try:
        for name, before, keys in CASES + [(o, None, None) for o in OPENING]:
            if a.filter not in name:
                continue
            runs += 1
            if keys is None:
                got, extra = run_opening(env, xdo, name)
            else:
                got, extra = run_case(env, xdo, name, before, keys)
            pin = PINS / (f"{name}.txt" if keys is None else f"{name}.toml")
            if a.update:
                PINS.mkdir(parents=True, exist_ok=True)
                pin.write_text(got)
                print(f"wrote {name}: {got!r}" + (f"  ({extra})" if extra else ""))
                continue
            want = pin.read_text() if pin.exists() else None
            if want != got or extra:
                fails += 1
                print(f"FAIL {name}")
                if want != got:
                    print(f"     want {want!r}\n     got  {got!r}")
                if extra:
                    print(f"     {extra}")
            else:
                print(f"ok   {name}")
    finally:
        xvfb.terminate()
        xvfb.wait()
    if not a.update:
        print(f"{runs - fails} of {runs} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

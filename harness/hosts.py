#!/usr/bin/env python3
"""The hosts gate (docs/settings.md ST10, ST11, ST23): what puritty asks
OpenSSH, and the window a session gets.

A stand-in `ssh` is put first on PATH: it writes the arguments it was
given to a file, one a line, and waits. Each case starts app/puritty on
Xvfb with a settings file and a command line, and holds the arguments the
stand-in was given, the window's title, and the color of an empty cell
of the window's picture (PURITTY_SHOT) to harness/hosts/expected/NAME.txt.

usage (from puritty's devbox, after app/build.sh):
    harness/hosts.py              every case
    harness/hosts.py --update     write the pins; read the diff first
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
import reload  # noqa: E402  (its pictures, its window's title)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "hosts"
PINS = ROOT / "harness" / "hosts" / "expected"
DISPLAY = ":87"

SETTINGS = """start = "shell"

[colors]
background = "#101010"

[hosts."build-box"]
host = "build.example.com"
user = "gilbert"
port = 2222
jump = "bastion"
command = "tmux new -A -s main"
title = "build"

[hosts."build-box".colors]
background = "#2a1010"

[hosts.bastion]
host = "b.example.com"
user = "me"
"""

# name, the settings (with `start` replaced when given), the command line,
# and keys pressed in the window titled so, when the case has some
CASES = [
    ("host", None, ["--host", "build-box"]),
    ("host-alias", None, ["--host", "work"]),
    ("host-titled", None, ["--title", "mine", "--host", "build-box"]),
    ("quick", None, ["ssh", "me@h.example.com:2200"]),
    ("start-host", 'start = "host:bastion"', []),
    ("start-shell", None, []),
    ("shell-over-start", 'start = "host:bastion"', ["shell"]),
    ("program-over-host", None, ["--host", "build-box", "--", "sh", "-c", "exec sleep 600"]),
    # the host list (V65): quick connect and New host come first; Enter on
    # the first host makes the same window
    # its session, so there is one window, with the host's title and colors
    ("host-list", None, ["hosts"], ("puritty hosts", ["Down", "Down", "Return"])),
    ("start-hosts", 'start = "hosts"', [], ("puritty hosts", [])),
    # from the settings window, a session opens a window of its own and the
    # settings window stays
    # the menu (ST26): Ctrl+right-click in a terminal, the seventh item (after
    # the tab's name and color, TB9, and reopening one, docs/tabs.md TB11),
    # the first host, started in a window of its own
    ("menu-connects", None, ["--title", "term", "--", "sh", "-c", "exec sleep 600"],
     ("term", ["ctrl+button3", "Down", "Down", "Down", "Down", "Down", "Down", "Return"])),
    # a double click on a host in the settings window (ST27): the Hosts page
    # clicked, then the first host's row twice, at pixels of the drawn
    # window (settings.py's click cases say where things are)
    # the Hosts page is the sidebar's ninth since the Keys page (puritty
    # docs/tabs.md TB6): eight Downs, and its row's middle at 321
    ("double-click-host", None, ["settings"], ("puritty settings", ["click 50 321 1", "click 300 221 2"])),
    ("settings-connects", None, ["settings"], ("puritty settings", ["Tab", "Tab"] + ["Down"] * 8 + ["Right", "Down", "Down", "Return"])),
]


def xdotool():
    """The IME gate's xdotool, as harness/pointer.py builds it."""
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), "xdotool"], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0] + "/bin/xdotool"


XDO = None


def windows(env):
    out = subprocess.run(["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True).stdout
    return sorted(l.split('"')[1] for l in out.splitlines() if '("puritty"' in l)


def run_case(env0, name, start, args, keys=None):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    (home / "config" / "puritty").mkdir(parents=True)
    text = SETTINGS if start is None else SETTINGS.replace('start = "shell"', start)
    (home / "config" / "puritty" / "config.toml").write_text(text)
    bin_dir = home / "bin"
    bin_dir.mkdir()
    said = home / "ssh-args.txt"
    (bin_dir / "ssh").write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > "{said}"\nexec sleep 600\n')
    (bin_dir / "ssh").chmod(0o755)
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               PATH=f"{bin_dir}:{env0['PATH']}", PURITTY_SHOT=str(home / "shot.ppm"))
    p = subprocess.Popen([str(APP), *args], env=env, stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
    time.sleep(1.8)
    seen = None
    if keys is not None:
        window, presses = keys
        win = subprocess.run([XDO, "search", "--sync", "--name", f"^{window}$"], env=env, capture_output=True,
                             text=True, timeout=10).stdout.split()[0]
        subprocess.run([XDO, "windowfocus", "--sync", win], env=env, check=True)
        for k in presses:
            if k.startswith("click "):
                _, x, y, count = k.split()
                subprocess.run([XDO, "mousemove", "--window", win, x, y], env=env, check=True)
                subprocess.run([XDO, "click", "--repeat", count, "--delay", "80", "1"], env=env, check=True)
            elif k == "ctrl+button3":
                subprocess.run([XDO, "mousemove", "--window", win, "100", "60"], env=env, check=True)
                subprocess.run([XDO, "keydown", "ctrl", "click", "3", "keyup", "ctrl"], env=env, check=True)
            else:
                subprocess.run([XDO, "key", k], env=env, check=True)
            time.sleep(0.15)
        time.sleep(1.8)
        seen = windows(env)
    title = reload.title_of(env)
    pic = reload.read_ppm(home / "shot.ppm")
    p.terminate()
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
    # a session the settings window started is its own process: closed so
    for w in subprocess.run([XDO, "search", "--class", "puritty"], env=env, capture_output=True, text=True).stdout.split():
        subprocess.run([XDO, "windowclose", w], env=env, capture_output=True)
    time.sleep(0.3)
    ssh = said.read_text().splitlines() if said.exists() else None
    color = "none"
    if args[:1] == ["settings"] or name == "menu-connects":
        # the settings window and the session it starts both write
        # PURITTY_SHOT's file, so which picture is there is a race
        color = "not pictured"
    elif pic:
        row = pic[len(pic) * 3 // 4]
        x = (len(row) // 3) * 3 // 4
        color = "#" + row[x * 3:x * 3 + 3].hex()
    # the window's size, from its picture: the host list's window turns
    # into a terminal's size when a host is chosen (docs/settings-gui.md SG11)
    size = f"{len(pic[0]) // 3}x{len(pic)}" if pic and name in ("host-list", "start-hosts") else None
    return (f"ssh: {ssh if ssh is not None else 'not run'}\n"
            f"title: {title}\n"
            f"background: {color}\n"
            + (f"windows: {seen}\n" if seen is not None else "")
            + (f"size: {size}\n" if size is not None else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if not APP.exists():
        sys.exit("hosts.py: build app/puritty first (app/build.sh)")
    global XDO
    XDO = xdotool()
    conf = pixels.write_fonts_conf()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96",
               LANG="C.UTF-8")
    env.pop("LC_ALL", None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    fails = 0
    try:
        for name, start, args, *keys in CASES:
            got = run_case(env, name, start, args, keys[0] if keys else None)
            pin = PINS / f"{name}.txt"
            if a.update:
                PINS.mkdir(parents=True, exist_ok=True)
                pin.write_text(got)
                print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
            elif not pin.exists() or pin.read_text() != got:
                fails += 1
                print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
            else:
                print(f"ok   {name}")
    finally:
        xvfb.terminate()
        xvfb.wait()
    if not a.update:
        print(f"{len(CASES) - fails} of {len(CASES)} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

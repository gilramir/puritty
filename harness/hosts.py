#!/usr/bin/env python3
"""The hosts gate (docs/settings.md ST10, ST11, ST23): what puritty asks
OpenSSH, and the window a session gets.

A stand-in `ssh` is put first on PATH: it writes the arguments it was
given to a file, one a line, and waits. Each case starts app/puritty on
Xvfb with a settings file and a command line, and holds the arguments the
stand-in was given, the window's title, and the colour of an empty cell
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

[colours]
background = "#101010"

[hosts."build-box"]
host = "build.example.com"
user = "gilbert"
port = 2222
jump = "bastion"
command = "tmux new -A -s main"
title = "build"

[hosts."build-box".colours]
background = "#2a1010"

[hosts.bastion]
host = "b.example.com"
user = "me"
"""

# name, the settings (with `start` replaced when given), the command line
CASES = [
    ("host", None, ["--host", "build-box"]),
    ("host-alias", None, ["--host", "work"]),
    ("host-titled", None, ["--title", "mine", "--host", "build-box"]),
    ("quick", None, ["ssh", "me@h.example.com:2200"]),
    ("start-host", 'start = "host:bastion"', []),
    ("start-shell", None, []),
    ("shell-over-start", 'start = "host:bastion"', ["shell"]),
    ("program-over-host", None, ["--host", "build-box", "--", "sh", "-c", "exec sleep 600"]),
]


def run_case(env0, name, start, args):
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
    title = reload.title_of(env)
    pic = reload.read_ppm(home / "shot.ppm")
    p.terminate()
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
    ssh = said.read_text().splitlines() if said.exists() else None
    colour = "none"
    if pic:
        row = pic[len(pic) * 3 // 4]
        x = (len(row) // 3) * 3 // 4
        colour = "#" + row[x * 3:x * 3 + 3].hex()
    return (f"ssh: {ssh if ssh is not None else 'not run'}\n"
            f"title: {title}\n"
            f"background: {colour}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if not APP.exists():
        sys.exit("hosts.py: build app/puritty first (app/build.sh)")
    conf = pixels.write_fonts_conf()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96",
               LANG="C.UTF-8")
    env.pop("LC_ALL", None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    fails = 0
    try:
        for name, start, args in CASES:
            got = run_case(env, name, start, args)
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

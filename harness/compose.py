#!/usr/bin/env python3
"""The compose gate (docs/phase3-input.md §18, the code review's X4): with
no input method, a dead key and the Compose key make the character they
make in xterm.

puritty runs on Xvfb with PURITTY_NO_XIM=1, its tab a program that writes
what is typed to a file. Each case sets a layout with `setxkbmap`, presses
keys with xdotool and holds the bytes typed:

    dead-acute   us(intl): dead_acute, e              -> é
    dead-space   us(intl): dead_acute, space          -> ' (the locale's
                 table's, how us(intl) types an apostrophe)
    compose      us, Compose on Right Alt: Compose, o, c -> ©
    nothing      us(intl): dead_acute, q (no such sequence) -> nothing,
                 then x -> x

usage (from puritty's devbox, after app/build.sh):
    harness/compose.py [PURITTY]
"""
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
RECORD = "stty raw -echo; exec dd bs=1 of=\"$0\" 2>/dev/null"

CASES = [
    ("dead-acute", ["us", "-variant", "intl"], ["dead_acute", "e"], "é".encode()),
    ("dead-space", ["us", "-variant", "intl"], ["dead_acute", "space"], b"'"),
    ("compose", ["us", "-option", "compose:ralt"], ["Multi_key", "o", "c"], "©".encode()),
    ("nothing", ["us", "-variant", "intl"], ["dead_acute", "q", "x"], b"x"),
]


def run_case(app, xdo, name, layout, keys, want):
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="compose-"))
    out = home / "typed"
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "-c", {RECORD!r}, "{out}"]\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser(), PURITTY_NO_XIM="1", LANG="en_US.UTF-8")
    env.pop("LC_ALL", None)
    env.pop("LC_CTYPE", None)
    p = None
    try:
        subprocess.run(["setxkbmap", "-display", display, *layout], check=True)
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(3)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        for k in keys:
            subprocess.run([xdo, "key", k], env=env, check=True)
            time.sleep(0.3)
        time.sleep(1)
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    got = out.read_bytes() if out.exists() else b""
    if got == want:
        shutil.rmtree(home)
        return None
    return f"typed {got!r}, want {want!r} (the home is {home})"


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    fails = 0
    for name, layout, keys, want in CASES:
        why = run_case(app, xdo, name, layout, keys, want)
        if why:
            fails += 1
            print(f"FAIL {name}: {why}")
        else:
            print(f"ok   {name}")
    print(f"{len(CASES) - fails} of {len(CASES)} cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

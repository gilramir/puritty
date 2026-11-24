#!/usr/bin/env python3
"""The keymap gate (docs/phase3-input.md §17, the code review's X7): a burst
of keyboard layout changes fetches the keymap once, not once an event, and
the keys typed after it are read with the new layout.

puritty runs on Xvfb with its diagnostic log on, its tab a program that
writes the first byte typed to a file. `setxkbmap` changes the layout
four times (us, de, us, de), each sending the window XKB NewKeyboardNotify
and MapNotify events; then `xdotool key z` presses German z, which is US y's
key. The window's "keymap fetched" lines in the log are counted: the one at
open, and one for the whole burst, when the key needs it (14 before §17).
The byte typed must be `z`.

usage (from puritty's devbox, after app/build.sh):
    harness/keymaps.py
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
LAYOUTS = ["us", "de", "us", "de"]
READ_ONE = "stty raw -echo; dd bs=1 count=1 of=\"$0\" 2>/dev/null; exec sleep 30"


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="keymaps-"))
    out = home / "typed"
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["sh", "-c", {READ_ONE!r}, "{out}"]\n\n[debug]\nlog = true\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser())
    env.pop("XDG_STATE_HOME", None)
    p = None
    try:
        subprocess.run(["setxkbmap", "-display", display, "us"], check=True)
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(3)
        for layout in LAYOUTS:
            subprocess.run(["setxkbmap", "-display", display, layout], check=True)
        time.sleep(2)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        subprocess.run([xdo, "key", "z"], env=env, check=True)
        for _ in range(20):
            if out.exists() and out.stat().st_size:
                break
            time.sleep(0.25)
        time.sleep(1)
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    typed = out.read_bytes() if out.exists() else b""
    logs = sorted((home / ".local" / "state" / "puritty" / "logs").glob("*.log"))
    fetched = sum(log.read_text(errors="replace").count("keymap fetched") for log in logs)
    print(f"keymap fetched {fetched} times for {len(LAYOUTS)} layout changes; typed {typed!r}")
    wrong = []
    if not logs:
        wrong.append("no diagnostic log")
    if fetched != 2:
        wrong.append(f"fetched {fetched} times, want 2")
    if typed != b"z":
        wrong.append(f"typed {typed!r}, want b'z'")
    if wrong:
        sys.exit("keymaps.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

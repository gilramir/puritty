#!/usr/bin/env python3
"""The late-copy gate (docs/phase3-select.md §27, the code review's X6): a
copy a program asks for (OSC 52) takes the clipboard even when another
program took it after puritty's last input event.

puritty runs on Xvfb, its tab a program that waits 5 s and then sets the
clipboard to `mine` with OSC 52. Meanwhile the window is clicked (the
time of its last event), and then xclip takes the clipboard with `other`.
After the program's copy the clipboard must read `mine`; before §27 the
server kept xclip as the owner, since puritty's claim was older, and it
read `other`.

usage (from puritty's devbox, after app/build.sh):
    harness/stalecopy.py [PURITTY]
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
PROGRAM = "sleep 5; printf '\\033]52;c;bWluZQ==\\007'; exec sleep 30\n"


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    xdo = hosts.xdotool()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="stalecopy-"))
    script = home / "copy.sh"
    script.write_text(PROGRAM)
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(f'[program]\ncommand = ["sh", "{script}"]\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh",
               USER=getpass.getuser(), PURITTY_NO_XIM="1")
    p = other = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        time.sleep(2)
        win = subprocess.run([xdo, "search", "--sync", "--class", "puritty"], env=env, capture_output=True, text=True,
                             timeout=10).stdout.split()[0]
        subprocess.run([xdo, "mousemove", "--window", win, "40", "40"], env=env, check=True)
        subprocess.run([xdo, "click", "1"], env=env, check=True)
        time.sleep(0.5)
        other = subprocess.Popen(["xclip", "-quiet", "-selection", "clipboard", "-i"], env=env, stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        other.stdin.write(b"other")
        other.stdin.close()
        time.sleep(5)
        got = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=env, capture_output=True,
                             timeout=10).stdout
    finally:
        if other:
            other.kill()
            other.wait()
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    print(f"the clipboard after the program's copy: {got!r}")
    if got != b"mine":
        sys.exit(f"stalecopy.py: the clipboard reads {got!r}, want b'mine' (the home is {home})")
    shutil.rmtree(home)


if __name__ == "__main__":
    main()

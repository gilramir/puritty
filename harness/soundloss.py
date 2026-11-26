#!/usr/bin/env python3
"""The sound loss gate (docs/sounds.md SN9, the code review's X11): after
the sound server goes away and comes back, the bell is heard again, and
while it is away the log says the bell was not played.

puritty runs on Xvfb with `[sound] bell = "apple2"` and its diagnostic
log on, with a stand-in for libpulse-simple (soundloss/fake_pulse.c, put
first on LD_LIBRARY_PATH) that writes each call to a file and plays the
gone server while a second file exists: no stream opens, and a stream's
write fails and that stream stays dead, as one whose server went away.
The tab's program rings the bell four times, three seconds apart; the
server goes away before the second bell and comes back after it.

The stand-in must then have opened a stream again and written to it
after the server came back. Before X11 the dead stream was kept and
written to: every later bell failed, and was logged as played.

usage (from puritty's devbox, after app/build.sh):
    harness/soundloss.py [PURITTY]
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

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "soundloss"
CLANG = "/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang"
RING = "sleep 2; for i in 1 2 3 4; do printf '\\007'; sleep 3; done; sleep 30"


def build_fake():
    """The stand-in, built with the toolchain puritty is built with."""
    WORK.mkdir(parents=True, exist_ok=True)
    lib = WORK / "libpulse-simple.so.0"
    subprocess.run([CLANG, "-shared", "-fPIC", "-O1", "-o", str(lib), str(ROOT / "harness/soundloss/fake_pulse.c")],
                   check=True)
    return WORK


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    libdir = build_fake()
    xvfb, display = pixels.start_xvfb()
    home = Path(tempfile.mkdtemp(prefix="soundloss-"))
    calls, gone = home / "calls.txt", home / "down"
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "ring.sh").write_text(RING + "\n")
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[sound]\nbell = "apple2"\n\n[debug]\nlog = true\n\n[program]\ncommand = ["sh", "{home / "ring.sh"}"]\n')
    env = dict(os.environ, DISPLAY=display, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               XDG_STATE_HOME=str(home / "state"), SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_NO_XIM="1",
               LD_LIBRARY_PATH=f"{libdir}:{os.environ.get('LD_LIBRARY_PATH', '')}", FAKE_PULSE_LOG=str(calls),
               FAKE_PULSE_DOWN=str(gone))
    p = None
    try:
        p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app)], env=env,
                             stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        # bells at about 2, 5, 8 and 11 s: the server gone from 3.5 to 6.5
        time.sleep(3.5)
        gone.touch()
        time.sleep(3)
        gone.unlink()
        time.sleep(7)
    finally:
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        xvfb.kill()
    said = calls.read_text().split("\n") if calls.exists() else []
    said = [l for l in said if l]
    logs = sorted((home / "state" / "puritty" / "logs").glob("*.log"))
    rang = [l.split("rang: ", 1)[1] for f in logs for l in f.read_text(errors="replace").splitlines() if "rang: " in l]
    print(f"the stand-in heard: {', '.join(_runs(said))}")
    print(f"the log: {rang}")
    opened = [i for i, l in enumerate(said) if l == "new"]
    wrong = []
    if len(opened) < 2:
        wrong.append(f"a stream was opened {len(opened)} times, want again after the server came back")
    elif "write" not in said[opened[-1]:]:
        wrong.append("nothing was written after the stream was opened again")
    if wrong:
        sys.exit("soundloss.py: " + "; ".join(wrong) + f" (the home is {home})")
    shutil.rmtree(home)


def _runs(lines):
    """Repeated lines as one, with their count."""
    out = []
    for l in lines:
        if out and out[-1][0] == l:
            out[-1][1] += 1
        else:
            out.append([l, 1])
    return [l if n == 1 else f"{l} x{n}" for l, n in out]


if __name__ == "__main__":
    main()

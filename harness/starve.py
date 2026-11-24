#!/usr/bin/env python3
"""The busy-tab gate (docs/tabs.md TB22, the code review's MA8): while the
shown tab's program prints without a pause, the window's other work still
gets its turns.

Each case starts puritty on Xvfb with a fresh home. Its first tab, A, runs
the case's program; a second, B, opened with Ctrl+Shift+T, runs the
window's command again, which a marker file in the home turns into `yes`,
shown from then on.

Cases:
    hidden    A waits 4 s, writes 200 KB to its terminal, then makes a file:
              it blocks on a full pty unless puritty reads the hidden tab.
              The file must be there within 10 s.
    settings  A sleeps; the settings file's title is changed while B
              prints, and the window's title must follow within 10 s.

usage (from puritty's devbox, after app/build.sh):
    harness/starve.py [PURITTY]
"""
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402  (its fonts)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "starve"
DISPLAY = ":85"
TITLE = "starve-gate"

CASES = [
    ("hidden", "sleep 4; head -c 200000 /dev/zero | tr '\\\\0' x; touch DONE; exec sleep 60"),
    ("settings", "exec sleep 60"),
]


def title_of(env):
    out = subprocess.run(["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True).stdout
    m = re.search(r'"([^"]*)": \("puritty"', out)
    return m.group(1) if m else None


def run_case(app, env0, xdo, name, program):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    (home / "config" / "puritty").mkdir(parents=True)
    conf = home / "config" / "puritty" / "config.toml"
    conf.write_text(f'[window]\ntitle = "{TITLE}"\n')
    done = home / "done"
    program = program.replace("DONE", f"'{done}'")
    marker = home / "a-started"
    both = f"if [ -e '{marker}' ]; then exec yes; fi; touch '{marker}'; {program}"
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"))
    p = subprocess.Popen(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", str(app), "--", "sh", "-c",
                          both], env=env, stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
    why = None
    try:
        time.sleep(1.5)
        win = subprocess.run([xdo, "search", "--sync", "--name", f"^{TITLE}"], env=env, capture_output=True,
                             text=True, timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        subprocess.run([xdo, "key", "ctrl+shift+t"], env=env, check=True)
        time.sleep(2.0)
        if name == "settings":
            conf.write_text(f'[window]\ntitle = "{TITLE}-again"\n')
        waited = 0.0
        while waited < 10:
            if name == "hidden" and done.exists():
                break
            if name == "settings" and title_of(env) == f"{TITLE}-again":
                break
            time.sleep(0.5)
            waited += 0.5
        else:
            why = ("the hidden tab's program never finished writing" if name == "hidden"
                   else f"the title is {title_of(env)!r} after 10 s")
        if why is None:
            print(f"     {name}: after {waited:.1f} s")
    finally:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    return why


def main():
    app = Path(sys.argv[1]) if len(sys.argv) > 1 else APP
    if not app.exists():
        sys.exit("starve.py: build app/puritty first (app/build.sh)")
    xdo = hosts.xdotool()
    conf = pixels.write_fonts_conf()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96", LANG="C.UTF-8")
    env.pop("LC_ALL", None)
    WORK.mkdir(parents=True, exist_ok=True)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    fails = 0
    try:
        for name, program in CASES:
            why = run_case(app, env, xdo, name, program)
            if why:
                fails += 1
                print(f"FAIL {name}: {why}")
            else:
                print(f"ok   {name}")
    finally:
        xvfb.terminate()
        xvfb.wait()
    print(f"{len(CASES) - fails} of {len(CASES)} cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

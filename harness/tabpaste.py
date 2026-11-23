#!/usr/bin/env python3
"""The tab paste gate (docs/phase3-select.md §25, the code review's MA9 and
MB3): a paste goes to the tab that asked for it, whichever is shown when
its pieces come.

Each case starts puritty on Xvfb with a fresh home. The window's first tab,
A, runs the case's program; a second, B, opened with Ctrl+Shift+T, runs
the window's command again, which a marker file in the home turns into
one that records every byte it receives on a raw terminal. A is shown again, xclip owns the clipboard with a large text,
which comes in INCR pieces, and Ctrl+Shift+V pastes it. What B received is
held to what the case wants.

Cases:
    closes   A reads one byte of the paste and exits, so its tab closes
             while the paste comes: B must receive nothing of it.
    switched A records too, and B is shown again right after the paste is
             asked for: A must receive all of it, B nothing.

usage (from puritty's devbox, after app/build.sh):
    harness/tabpaste.py
"""
import os
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
WORK = ROOT / ".harness-work" / "tabpaste"
DISPLAY = ":84"
TITLE = "tabpaste-gate"

# 4 MB in lines, many INCR pieces
LARGE = b"".join(b"%063d\n" % n for n in range(1, 65537))

# name, A's program (A_GOT its file), the key pressed right after the paste
CASES = [
    ("closes", "stty raw -echo; dd bs=1 count=1 of=/dev/null 2>/dev/null", None),
    ("switched", "stty raw -echo; exec cat > A_GOT", "ctrl+Next"),
]


CASES_BY_NAME = {c[0]: c[1] for c in CASES}


def run_case(env0, xdo, name, program, after):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(f'[window]\ntitle = "{TITLE}"\n')
    got = home / "b.bin"
    a_got = home / "a.bin"
    program = program.replace("A_GOT", f"'{a_got}'")
    marker = home / "a-started"
    both = (f"if [ -e '{marker}' ]; then stty raw -echo; exec cat > '{got}'; fi; touch '{marker}'; {program}")
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"))
    p = subprocess.Popen([str(APP), "--", "sh", "-c", both], env=env, stdout=subprocess.DEVNULL,
                         stderr=open(home / "stderr.txt", "w"))
    owner = None
    try:
        time.sleep(1.5)
        win = subprocess.run([xdo, "search", "--sync", "--name", f"^{TITLE}"], env=env, capture_output=True,
                             text=True, timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)

        def key(k):
            subprocess.run([xdo, "key", k], env=env, check=True)
            time.sleep(1.0)
        key("ctrl+shift+t")
        key("ctrl+Prior")
        owner = subprocess.Popen(["xclip", "-quiet", "-selection", "clipboard", "-t", "UTF8_STRING", "-i"], env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner.stdin.write(LARGE)
        owner.stdin.close()
        time.sleep(0.5)
        subprocess.run([xdo, "key", "ctrl+shift+v"], env=env, check=True)
        if after is not None:
            subprocess.run([xdo, "key", after], env=env, check=True)
        time.sleep(5.0)
    finally:
        if owner is not None:
            owner.kill()
            owner.wait()
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    n = got.stat().st_size if got.exists() else -1
    if n < 0:
        return "tab B never started"
    if n != 0:
        return f"tab B received {n} bytes of the paste meant for A"
    if "A_GOT" in CASES_BY_NAME[name] and (not a_got.exists() or a_got.stat().st_size != len(LARGE)):
        return f"tab A received {a_got.stat().st_size if a_got.exists() else 0} bytes of {len(LARGE)}"
    return None


def main():
    if not APP.exists():
        sys.exit("tabpaste.py: build app/puritty first (app/build.sh)")
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
        for name, program, after in CASES:
            why = run_case(env, xdo, name, program, after)
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

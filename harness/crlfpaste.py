#!/usr/bin/env python3
"""The CRLF paste gate (docs/phase3-select.md §15, docs/tmux.md TM95, the
code review's VS5): a paste's line ends reach a program that did not ask
for brackets as one CR each, CR LF and LF alike, whether the paste comes
whole or in INCR pieces that split a CR LF.

Each case starts puritty on Xvfb with a fresh home, its one tab running a
program that records every byte it receives on a raw terminal. xclip owns
the clipboard with the case's text and Ctrl+Shift+V pastes it. What the
program received is held to the text with each CR LF and each LF made CR.

Cases:
    small    a few lines ending CR LF, one LF, one CR: one piece.
    large    4 MB of lines ending CR LF, 39 bytes each, in many INCR pieces.
    split    one byte and 2,000,000 CR LFs, 4 MB in INCR pieces: every
             even offset is between a CR and its LF, so a piece of an even
             size ends between them.

usage (from puritty's devbox, after app/build.sh):
    harness/crlfpaste.py
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
WORK = ROOT / ".harness-work" / "crlfpaste"
DISPLAY = ":85"
TITLE = "crlfpaste-gate"

CASES = [
    ("small", b"one\r\ntwo\r\nthree\nfour\rfive\r\n"),
    ("large", b"".join(b"%036d\r\n" % n for n in range(1, 107000))),
    ("split", b"x" + b"\r\n" * 2000000),
]


def wanted(text):
    return text.replace(b"\r\n", b"\r").replace(b"\n", b"\r")


def run_case(env0, xdo, name, text):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(f'[window]\ntitle = "{TITLE}"\n')
    got = home / "got.bin"
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"))
    p = subprocess.Popen([str(APP), "--", "sh", "-c", f"stty raw -echo; exec cat > '{got}'"], env=env,
                         stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
    owner = None
    try:
        time.sleep(1.5)
        win = subprocess.run([xdo, "search", "--sync", "--name", f"^{TITLE}"], env=env, capture_output=True,
                             text=True, timeout=10).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        owner = subprocess.Popen(["xclip", "-quiet", "-selection", "clipboard", "-t", "UTF8_STRING", "-i"], env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner.stdin.write(text)
        owner.stdin.close()
        time.sleep(0.5)
        subprocess.run([xdo, "key", "ctrl+shift+v"], env=env, check=True)
        want = wanted(text)
        asked = time.time()
        deadline = asked + 20
        while time.time() < deadline and (not got.exists() or got.stat().st_size < len(want)):
            time.sleep(0.05)
        took = time.time() - asked
        time.sleep(1.0)
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
    data = got.read_bytes() if got.exists() else b""
    print(f"     {name}: {len(text)} bytes pasted, all received {took:.2f} s after Ctrl+Shift+V")
    if data == want:
        return None
    first = next((i for i in range(min(len(data), len(want))) if data[i] != want[i]), min(len(data), len(want)))
    return (f"received {len(data)} bytes, wanted {len(want)}; {data.count(b'\r\r')} CR CR; first difference at "
            f"{first}: {data[max(0, first - 8):first + 8]!r} for {want[max(0, first - 8):first + 8]!r}")


def main():
    if not APP.exists():
        sys.exit("crlfpaste.py: build app/puritty first (app/build.sh)")
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
        for name, text in CASES:
            why = run_case(env, xdo, name, text)
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

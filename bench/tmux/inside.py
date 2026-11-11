#!/usr/bin/env python3
"""tmux inside puritty (docs/tmux.md TM4): puritty runs `tmux attach` on
Xvfb, to a server whose one pane runs `cat -v`. After WAIT seconds a lone
Esc is typed into the window (xdotool), and the time until the pane shows
`^[` is measured by polling capture-pane; then tmux says what it learned
of puritty: the theme, the name XTVERSION gave and the features. Runs its
own Xvfb (:86), tmux socket and config file, and stops what it started.

    devbox run -- python3 bench/tmux/inside.py --puritty app/puritty \\
        --tmux /nix/store/...-tmux-3.8/bin/tmux [--wait 1] [--runs 3]
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its fonts)

DISPLAY = ":86"
SOCK = "puritty-bench-tmux"
WORK = ROOT / ".harness-work" / "tmux-inside"


def xdotool():
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), "xdotool"], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0] + "/bin/xdotool"


def one(a, env, xdo):
    tmux = [a.tmux, "-L", SOCK]
    subprocess.run([*tmux, "-f", "/dev/null", "new-session", "-d", "-x", "80", "-y", "24", "cat -v"], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-inside", "--",
                            a.tmux, "-L", SOCK, "attach"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux-inside|tmux|cat"], env=env,
                             capture_output=True, text=True, timeout=20).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(a.wait)
        t = time.monotonic()
        subprocess.run([xdo, "key", "Escape"], env=env, check=True)
        ms = None
        while time.monotonic() - t < 3:
            if "^[" in subprocess.run([*tmux, "capture-pane", "-p", "-t", "%0"], env=env,
                                      capture_output=True, text=True).stdout:
                ms = round((time.monotonic() - t) * 1000)
                break
        told = subprocess.run([*tmux, "display", "-p", "-c", subprocess.run(
            [*tmux, "list-clients", "-F", "#{client_name}"], env=env, capture_output=True, text=True).stdout.split()[0],
            "theme=#{client_theme} type=#{client_termtype} features=#{client_termfeatures}"],
            env=env, capture_output=True, text=True).stdout.strip()
        return ms, told
    finally:
        subprocess.run([*tmux, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", required=True)
    ap.add_argument("--tmux", required=True)
    ap.add_argument("--wait", type=float, default=1.0)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "config.toml").write_text("")
    xdo = xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8")
    for k in ("LC_ALL", "TMUX"):
        env.pop(k, None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    try:
        for _ in range(a.runs):
            ms, told = one(a, env, xdo)
            print(f"esc {ms} ms after {a.wait} s; {told}")
    finally:
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

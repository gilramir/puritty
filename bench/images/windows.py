#!/usr/bin/env python3
"""Pictures in puritty on Windows (docs/images.md IM29): puritty.exe on a
Windows machine connects to this machine with its built-in ssh client and
attaches to a tmux here, plain and with `-CC`; this side types gnuplot's,
chafa's and timg's commands into tmux, and each step's frame (PURITTY_SHOT)
comes back as a PNG, its pictures counted by color as bench/images/
programs.py does. The window's padding shows in each picture's edges.

    devbox run -- python3 bench/images/windows.py [--host beelink1] [--mode plain|cc|all]

The Windows side is bench/images/windows/run.ps1, run over ssh; the
pictures are in .harness-work/images-windows/MODE/. Stops what it started.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "bench" / "tmux"))
sys.path.insert(0, str(ROOT / "bench" / "images"))
from reload import read_ppm, save_png  # noqa: E402
from show import check, note, report, that  # noqa: E402
from programs import BLUE, GREEN, RED, count, pictures, plot, tool  # noqa: E402

SOCK = "puritty-images-windows"
WORK = ROOT / ".harness-work" / "images-windows"
REMOTE = "geng-probe/images"
CONF = ROOT / "packages" / "tmux" / "tests" / "data" / "tmux.conf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="beelink1")
    ap.add_argument("--mode", default="all", choices=["plain", "cc", "all"])
    ap.add_argument("--exe", default=str(ROOT / "app" / "puritty.exe"))
    a = ap.parse_args()
    tmux_bin = shutil.which("tmux")
    path = ":".join([tool("gnuplot"), os.environ["PATH"]])
    env = dict(os.environ, PATH=path, LANG="C.UTF-8", PS1="$ ")
    for k in ("TMUX", "LC_ALL"):
        env.pop(k, None)
    tmux = [tmux_bin, "-L", SOCK, "-f", str(CONF)]
    me, here = os.environ.get("USER", "gram"), socket.gethostname()
    ssh = ["ssh", "-o", "BatchMode=yes", a.host]
    stage = WORK / "stage"
    shutil.rmtree(WORK, ignore_errors=True)
    stage.mkdir(parents=True)
    pics = pictures(WORK / "pics")
    for mode in ("plain", "cc"):
        flag = "-CC " if mode == "cc" else ""
        (stage / f"config-{mode}.toml").write_text(
            "[window]\ncolumns = 110\nrows = 32\npadding = 8\n\n[font]\nsize = 11\n\n"
            f"[hosts.\"{here}\"]\nhost = \"{here}\"\nuser = \"{me}\"\nclient = \"built-in\"\n"
            f"command = \"{tmux_bin} -L {SOCK} {flag}attach -t img\"\n", newline="\n")
    subprocess.run(ssh + [f"powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path {REMOTE} | Out-Null;"
                          f" Remove-Item -Recurse -Force {REMOTE}\\* -ErrorAction SilentlyContinue\""], check=True)
    subprocess.run(["scp", "-q", a.exe, str(ROOT / "bench/images/windows/run.ps1"), *map(str, stage.glob("*")),
                    f"{a.host}:{REMOTE}/"], check=True)

    def cli(*args):
        r = subprocess.run([*tmux, *args], env=env, capture_output=True, text=True)
        if r.returncode:
            print("tmux", *args, "->", r.stderr.strip())
        return r.stdout

    for mode in (["plain", "cc"] if a.mode == "all" else [a.mode]):
        work = WORK / mode
        work.mkdir()
        cli("kill-server")
        cli("new-session", "-d", "-s", "img", "-x", "110", "-y", "31")
        cli("set", "-g", "allow-passthrough", "on")
        runner = subprocess.Popen(ssh + [f"powershell -NoProfile -ExecutionPolicy Bypass -File {REMOTE}\\run.ps1 -Host_ {here} -Mode {mode}"],
                                  stdout=open(work / "runner.txt", "w"), stderr=subprocess.STDOUT)
        n = 0

        def snap(name):
            nonlocal n
            n += 1
            name = f"{n:02d}-" + "".join(c if c.isalnum() else "-" for c in name)
            time.sleep(1.0)
            subprocess.run(ssh + [f"Set-Content -Path {REMOTE}\\want.txt -Value {name}"], check=True)
            for _ in range(40):
                left = subprocess.run(ssh + [f"Test-Path {REMOTE}\\want.txt"], capture_output=True, text=True).stdout.strip()
                if left == "False":
                    break
                time.sleep(0.5)
            subprocess.run(["scp", "-q", f"{a.host}:{REMOTE}/out/{name}.ppm", str(work)], stderr=subprocess.DEVNULL)
            rows = read_ppm(work / f"{name}.ppm")
            if rows:
                save_png(work / f"{name}.png", rows)
                print(f"     windows-{mode}/{name}.png", flush=True)
            return rows

        def run(command, wait=3.0):
            cli("send-keys", "-t", "img", command, "Enter")
            time.sleep(wait)

        try:
            for _ in range(60):
                if cli("list-clients"):
                    break
                time.sleep(0.5)
            check(f"windows {mode}: puritty.exe attached over its own ssh client", bool(cli("list-clients")), True)
            time.sleep(2)
            run("clear; echo puritty on Windows: padding and pictures", 1.0)
            snap("attached")
            steps = [
                ("gnuplot sixelgd", plot("sixelgd", RED), RED),
                ("chafa, left to choose", f"chafa --size 20x6 {pics / 'blue.png'}", BLUE),
                ("chafa -f iterm", f"chafa -f iterm --size 20x6 {pics / 'green.png'}", GREEN),
                ("timg -ps (Sixel), a JPEG", f"timg -ps -g 20x6 {pics / 'blue.jpg'}", BLUE),
                ("gnuplot kittycairo", plot("kittycairo", GREEN), GREEN),
            ]
            for name, command, color in steps:
                run("clear", 0.8)
                run(command)
                rows = snap(name.split(",")[0].replace(" ", "-"))
                if mode == "plain" and name in ("chafa -f iterm", "gnuplot kittycairo"):
                    check(f"windows {mode}: {name}: dropped by tmux, as tmux does", count(rows, color), 0)
                else:
                    check(f"windows {mode}: {name}: its color in the window", count(rows, color),
                          that("more than 2000 pixels", lambda v: v > 2000))
            if mode == "cc":
                run("clear", 0.8)
                run(plot("sixelgd", RED))
                shown = count(snap("before-split"), RED)
                cli("split-window", "-h", "-t", "img")
                time.sleep(2)
                rows = snap("split-beside")
                check(f"windows {mode}: the pane split beside the picture: still drawn", count(rows, RED),
                      that("over half of it", lambda v: v > shown // 2))
            steps_alive = subprocess.run(ssh + [f"Get-Content {REMOTE}\\out\\steps-{mode}.txt"], capture_output=True, text=True).stdout
            check(f"windows {mode}: puritty.exe alive at every step", "alive=False" in steps_alive, False)
        finally:
            subprocess.run(ssh + [f"Set-Content -Path {REMOTE}\\stop.txt -Value stop"])
            try:
                runner.wait(timeout=30)
            except subprocess.TimeoutExpired:
                runner.kill()
            cli("kill-server")
            subprocess.run(["scp", "-q", f"{a.host}:{REMOTE}/out/stderr-{mode}.txt", str(work)], stderr=subprocess.DEVNULL)
    report()


if __name__ == "__main__":
    main()

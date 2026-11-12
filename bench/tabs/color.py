#!/usr/bin/env python3
"""Per-host tab colors (docs/tabs.md TB9), on Xvfb: a host of the built-in
client with `[hosts.prod.colors] tab`, against a local sshd
(packages/ssh/tests/sshd.py's), and a host of OpenSSH's run by a stand-in
`ssh` that starts a shell. Each step prints the bar's fills, read from the
window's picture (PURITTY_SHOT) along a row just under the tabs' tops, so
it is checked by colors and not only by looking; the pictures are saved
too, in .harness-work/tabs-color/.

    devbox run -- python3 bench/tabs/color.py      (after app/build.sh and packages/ssh/tests/build.sh)
"""

import getpass
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "packages" / "ssh" / "tests"))
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402
import reload  # noqa: E402  (the window's picture)
import sshd  # noqa: E402

DISPLAY = ":86"
WORK = ROOT / ".harness-work" / "tabs-color"
BAR = (0x26, 0x26, 0x26)


def fills(rows):
    """The bar's fills from left to right, each a color and its width, read
    along the row four pixels under the bar's top, where the shown tab's
    line has ended and the names' letters have not begun."""
    if not rows:
        return "no picture"
    px = lambda row, x: tuple(row[x * 3:x * 3 + 3])
    top = len(rows)
    while top > 0 and px(rows[top - 1], 0) == BAR:
        top -= 1
    row = rows[top + 4]
    runs = []
    for x in range(len(row) // 3):
        c = px(row, x)
        if runs and runs[-1][0] == c:
            runs[-1][1] += 1
        else:
            runs.append([c, 1])
    return " ".join(f"#{bytes(c).hex()}x{n}" for c, n in runs if n >= 6 and c != BAR)


def config(port, keys, tab):
    return (f'[keys]\ncolor_tab = "Ctrl+Alt+K"\n\n'
            f'[hosts.prod]\nhost = "127.0.0.1"\nport = {port}\nuser = "{getpass.getuser()}"\n'
            f'identity = "{keys["ed"]}"\nclient = "built-in"\ncommand = "/bin/sh"\n\n'
            f'[hosts.prod.colors]\ntab = "{tab}"\n\n'
            f'[hosts.lab]\nhost = "lab.invalid"\nclient = "openssh"\n\n'
            f'[hosts.lab.colors]\ntab = "#1565c0"\n')


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "config" / "puritty").mkdir(parents=True)
    (WORK / ".ssh").mkdir()
    (WORK / "bin").mkdir()
    # OpenSSH's ssh stood in for by a shell, so that an OpenSSH host's
    # window needs no server
    (WORK / "bin" / "ssh").write_text("#!/bin/sh\nexec /bin/sh\n")
    (WORK / "bin" / "ssh").chmod(0o755)
    xdo = hosts.xdotool()
    keys = sshd.user_keys()[0]
    sshd.host_keys()
    server = sshd.Server([])
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    file = WORK / "config" / "puritty" / "config.toml"
    p = None
    try:
        pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
        (WORK / ".ssh" / "known_hosts").write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
        file.write_text(config(server.port, keys, "#c62828"))
        env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
                   PURITTY_DPI="96", LANG="C.UTF-8", HOME=str(WORK), XDG_CONFIG_HOME=str(WORK / "config"),
                   SHELL="/bin/sh", USER=getpass.getuser(), PURITTY_SHOT=str(WORK / "shot.ppm"),
                   PATH=f"{WORK / 'bin'}:{os.environ['PATH']}", PS1="$ ")
        env.pop("SSH_AUTH_SOCK", None)
        env.pop("LC_ALL", None)
        xd = lambda *a: subprocess.run([xdo, *a], env=env, check=True)
        said = lambda name: (WORK / name).read_text().strip() if (WORK / name).exists() else "(none)"

        found = []
        win = found

        def start(*args):
            q = subprocess.Popen([str(ROOT / "app" / "puritty"), *args], env=env, stdout=subprocess.DEVNULL,
                                 stderr=open(WORK / "stderr.txt", "a"))
            time.sleep(3.0)
            win = subprocess.run([xdo, "search", "--sync", "--onlyvisible", "--name", "."], env=env,
                                 capture_output=True, text=True, timeout=20).stdout.split()
            xd("windowfocus", "--sync", win[-1])
            found[:] = [win[-1]]
            return q

        def typed(text):
            xd("type", "--delay", "15", text)
            xd("key", "Return")
            time.sleep(0.8)

        def snap(name, what):
            time.sleep(0.8)
            rows = reload.read_ppm(WORK / "shot.ppm")
            if rows:
                reload.save_png(WORK / f"{name}.png", rows)
            print(f"{what}: {fills(rows)}")

        p = start("--host", "prod")
        xd("key", "ctrl+shift+t")
        time.sleep(3.0)
        snap("01-two-prod-tabs", "two tabs of prod, red, the second shown")
        # the menu by the right button on the first tab, its "Tab color…"
        # (the fifth item), and 4 in the box: green
        geometry = subprocess.run([xdo, "getwindowgeometry", win[0]], env=env, capture_output=True, text=True).stdout
        size = geometry.split("Geometry: ")[1].split()[0].split("x")
        pos = geometry.split("Position: ")[1].split()[0].split(",")
        xd("mousemove", str(int(pos[0]) + 12), str(int(pos[1]) + int(size[1]) - 6))
        xd("click", "3")
        time.sleep(0.6)
        snap("02-menu", "the menu over the first tab")
        for _ in range(4):
            xd("key", "Down")
        xd("key", "Return")
        time.sleep(0.6)
        snap("03-color-box", "the color box")
        xd("key", "4")
        snap("04-first-green", "the first tab green, shown; the second red")
        typed(f"echo first > {WORK}/a.txt")
        print("the first tab's shell then wrote:", said("a.txt"))
        # the key, 0: no color, over the host's
        xd("key", "ctrl+alt+k")
        time.sleep(0.4)
        xd("key", "0")
        snap("05-first-none", "the first tab without a color, amber as shown")
        # a bell in the red tab not shown: its dot
        xd("key", "ctrl+Next")
        time.sleep(0.4)
        typed("sleep 1; printf '\\a'")
        xd("key", "ctrl+Prior")
        time.sleep(2.0)
        snap("06-bell", "the red tab rang, not shown")
        # h: the host's again
        xd("key", "ctrl+alt+k")
        time.sleep(0.4)
        xd("key", "h")
        snap("07-first-host", "the first tab the host's red again")
        # the host's color changed in the file: both tabs, at once
        file.write_text(config(server.port, keys, "#6a1b9a"))
        time.sleep(2.5)
        snap("08-reloaded", "prod's tab color changed to purple in the file")
        p.terminate()
        p.wait()
        p = None
        # a host of OpenSSH's: its window's tabs take its color too
        p = start("--host", "lab")
        typed(f"echo lab > {WORK}/b.txt")
        print("lab's shell wrote:", said("b.txt"))
        xd("key", "ctrl+shift+t")
        time.sleep(1.5)
        snap("09-lab", "two tabs of lab (OpenSSH), blue")
    finally:
        if p is not None and p.poll() is None:
            p.terminate()
            p.wait()
        server.stop()
        xvfb.terminate()
        xvfb.wait()
        err = (WORK / "stderr.txt").read_text().strip() if (WORK / "stderr.txt").exists() else ""
        if err:
            print("stderr:", err[:400])
        print("pictures:", WORK)


if __name__ == "__main__":
    main()

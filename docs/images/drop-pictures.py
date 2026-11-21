#!/usr/bin/env python3
"""The site's picture of drag and drop (docs/sftp.md FT32, FT33): files
dragged from Nemo onto puritty, the screen as Xvfb has it so that the
file manager and the drag's icon are in it.

- `drop-picker.png`, the home page's: the folder picker on its pretend host
  (`--try-folder-picker`, nothing real in it), the files dragged over its
  `assets/` row.
- `tmux`, kept as the other candidate (`.harness-work/drop-pictures/tmux/
  shot.png`, not used): tmux -CC over ssh (the drop harness's local sshd), two
  panes, the files dragged over the right one, which says where they go.

    devbox run -- python3 docs/images/drop-pictures.py picker 1080,240
    devbox run -- python3 docs/images/drop-pictures.py tmux 1280,420

The point is where the drag is held; with none, the screen before it.
The picture is the shot copied to `docs/images/drop-picker.png`.
"""

import getpass
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "packages" / "ssh" / "tests"))
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402  (its fonts)
import sshd  # noqa: E402  (the local sshd and the user keys)
from drop import ended, file_manager  # noqa: E402

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "drop-pictures"
OUT = Path(__file__).resolve().parent
DISPLAY = ":84"
W, H = 1550, 860
SHOT = [sys.executable, str(ROOT / "probes" / "xdnd" / "shot.py")]
# Nemo's icon view at 470 wide, its sidebar hidden: the first row's three icons
ICONS = [(82, 120), (237, 120), (392, 120)]
STYLE = '[font]\nfamily = "Fira Code"\nsize = 12\n\n[colors]\nscheme = "ghostty"\n'


def xdo(env, *args):
    return subprocess.run([hosts.XDO, *map(str, args)], env=env, capture_output=True, text=True).stdout


def png(path, rgb, width, height):
    raw = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    chunk = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def home_for(name):
    """A home called `me`, holding the files Nemo shows."""
    home = WORK / name / "me"
    shutil.rmtree(home.parent, ignore_errors=True)
    files = home / "site"
    files.mkdir(parents=True)
    # a real PNG, so that Nemo draws it as a picture
    side = 48
    pic = bytearray()
    for y in range(side):
        for x in range(side):
            pic += bytes((255 - x * 3, 120 + y * 2, 90 + x * 3))
    png(files / "logo.png", bytes(pic), side, side)
    (files / "notes.txt").write_text("Things to change on the site.\n")
    (files / "report-2026-11.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    # no thumbnails: with no thumbnailer Nemo shows a clock for them
    keyfile = home / ".config" / "glib-2.0" / "settings" / "keyfile"
    keyfile.parent.mkdir(parents=True)
    keyfile.write_text("[org/nemo/preferences]\nshow-image-thumbnails='never'\n\n"
                       "[org/nemo/window-state]\nstart-with-sidebar=false\n")
    return home, files


def start(env, home, files, app_args, app_env=None):
    procs = [file_manager(["nemo", "--no-desktop", "--geometry=470x700+0+0", str(files)],
                          dict(env, GTK_THEME="Adwaita", GSETTINGS_BACKEND="keyfile")),
             subprocess.Popen([str(APP), *app_args], env=app_env or env, stdout=subprocess.DEVNULL,
                              stderr=open(home.parent / "stderr.txt", "w"))]
    time.sleep(7)
    for wid in xdo(env, "search", "--class", "nemo").split():
        xdo(env, "windowmove", wid, 0, 0)
        xdo(env, "windowsize", wid, 470, 700)
    for wid in xdo(env, "search", "--class", "puritty").split():
        xdo(env, "windowmove", wid, 490, 40)
    time.sleep(1.5)
    return procs


def drag_all_to(env, at):
    """The three files selected in Nemo and dragged to `at`, held there."""
    xdo(env, "mousemove", *ICONS[0])
    xdo(env, "click", 1)
    for icon in ICONS[1:]:
        xdo(env, "mousemove", *icon)
        xdo(env, "keydown", "ctrl")
        xdo(env, "click", 1)
        xdo(env, "keyup", "ctrl")
    time.sleep(0.5)
    x, y = ICONS[0]
    xdo(env, "mousemove", x, y)
    time.sleep(0.3)
    xdo(env, "mousedown", 1)
    for i in range(1, 41):
        xdo(env, "mousemove", x + (at[0] - x) * i // 40, y + (at[1] - y) * i // 40)
        time.sleep(0.03)
    xdo(env, "mousemove", at[0] + 1, at[1] + 1)
    time.sleep(1.5)


def stop(procs):
    ended(procs)


def picker(env, at):
    home, files = home_for("picker")
    (home / "config.toml").write_text("[window]\ncolumns = 104\nrows = 40\n\n" + STYLE)
    env = dict(env, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"))
    procs = start(env, home, files, ["--config", str(home / "config.toml"), "--try-folder-picker"])
    try:
        subprocess.run(SHOT + [str(home.parent / "before.png")], env=env)
        if at:
            drag_all_to(env, at)
        subprocess.run(SHOT + [str(home.parent / "shot.png")], env=env)
    finally:
        stop(procs)
    return home.parent / "shot.png"


E = "\x1b["
PROMPT = E + "1;32mme@web1" + E + "0m:" + E + "1;34m{}" + E + "0m$ "


def panes(work):
    """The two panes' text: a site built on the left; on the right a shell in
    /srv/www/site, which says so by OSC 7, as a shell set up for it does."""
    dim, ok, rst = E + "2m", E + "32m", E + "0m"
    left = "\r\n".join([
        PROMPT.format("~/projects/site") + "make build",
        "hugo --minify --destination public",
        "",
        "                  │ EN  │ KO",
        " ─────────────────┼─────┼─────",
        "  Pages           │  48 │  41",
        "  Paginator pages │   4 │   3",
        "  Static files    │ 112 │ 112",
        "  Processed images│  36 │  36",
        "",
        "Total in 312 ms",
        ok + "✓" + rst + " built public/ " + dim + "(2.4 MB)" + rst,
        PROMPT.format("~/projects/site") + "git log --oneline -4",
        E + "33ma1c9e2f" + rst + " Add the November report",
        E + "33m7d40b18" + rst + " New logo",
        E + "33m3e9f0c2" + rst + " Fix the Korean menu",
        E + "33mb52a6d1" + rst + " Notes on the deploy",
        PROMPT.format("~/projects/site"),
    ])
    blue = E + "1;34m"
    right = "\r\n".join([
        PROMPT.format("/srv/www/site") + "ls -l",
        "total 32",
        "drwxr-xr-x 4 me www 4096 Nov 14 02:13 " + blue + "assets" + rst,
        "drwxr-xr-x 2 me www 4096 Nov 15 02:13 " + blue + "css" + rst,
        "drwxr-xr-x 2 me www 4096 Nov 16 02:13 " + blue + "img" + rst,
        "-rw-r--r-- 1 me www 4198 Nov 14 08:11 index.html",
        "-rw-r--r-- 1 me www 12001 Nov 14 12:35 logo.png",
        "-rw-r--r-- 1 me www   64 Nov 14 10:23 robots.txt",
        PROMPT.format("/srv/www/site"),
    ])
    (work / "left.ans").write_text(left)
    (work / "right.ans").write_text(right)
    conf = work / "tmux.conf"
    conf.write_text('set -g default-shell /bin/sh\nset -g status-left "[web1] "\nset -g status-right ""\n')
    hold = "; exec sleep 100000"
    osc7 = "printf '\\033]7;file://%s/srv/www/site\\007' \"$(hostname)\""
    script = work / "panes.sh"
    script.write_text(
        "#!/bin/sh\n"
        f"exec tmux -L puritty-picture-drop -f {conf} -CC new-session -s web1 -n site "
        f"\"cat {work / 'left.ans'}{hold}\" \\; "
        f"split-window -h \"{osc7}; cat {work / 'right.ans'}{hold}\" \\; "
        f"new-window -d -n logs\n")
    return script


def tmux(env, at):
    home, files = home_for("tmux")
    script = panes(home.parent)
    keys = sshd.user_keys()[0]
    server = sshd.Server([])
    kh = home / ".ssh" / "known_hosts"
    kh.parent.mkdir(parents=True)
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    (home / ".config" / "puritty").mkdir(parents=True)
    (home / ".config" / "puritty" / "config.toml").write_text(
        f'[window]\ncolumns = 104\nrows = 40\n\n{STYLE}\n[hosts.web1]\nhost = "127.0.0.1"\nport = {server.port}\n'
        f'user = "{getpass.getuser()}"\nidentity = "{keys["ed"]}"\nclient = "built-in"\ncommand = "sh {script}"\n'
        '\n[files]\ndrop_uploads = "allow"\n')
    env = dict(env, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"))
    procs = start(env, home, files, ["--host", "web1"])
    try:
        time.sleep(2)
        subprocess.run(SHOT + [str(home.parent / "before.png")], env=env)
        if at:
            drag_all_to(env, at)
        subprocess.run(SHOT + [str(home.parent / "shot.png")], env=env)
    finally:
        stop(procs)
        subprocess.run(["tmux", "-L", "puritty-picture-drop", "kill-server"], capture_output=True)
        server.stop()
    return home.parent / "shot.png"


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "picker"
    at = tuple(map(int, sys.argv[2].split(","))) if len(sys.argv) > 2 else None
    hosts.XDO = hosts.xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", NO_AT_BRIDGE="1", USER=getpass.getuser(), SHELL="/bin/sh")
    env.pop("SSH_AUTH_SOCK", None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", f"{W}x{H}x24", "-nolisten", "tcp", "-noreset"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    # a desktop's color behind the two windows
    subprocess.run(["xsetroot", "-solid", "#4a5468"], env=env)
    try:
        print(picker(env, at) if which == "picker" else tmux(env, at))
    finally:
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

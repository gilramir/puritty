#!/usr/bin/env python3
"""tmux control mode in puritty, shown (docs/tmux.md TM14): puritty on
Xvfb runs `tmux -CC new-session` on its own socket, a second tmux client
splits the window and opens floating panes, keys are typed into puritty's
window, and the window's own picture (PURITTY_SHOT) is saved as a PNG
after each step, in .harness-work/tmux-show/. Stops what it started.

    devbox run -- python3 bench/tmux/show.py --puritty app/puritty
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
from reload import read_ppm, save_png  # noqa: E402

DISPLAY = ":87"
SOCK = "puritty-bench-tmux"
WORK = ROOT / ".harness-work" / "tmux-show"
CONF = ROOT / "packages" / "tmux" / "tests" / "data" / "tmux.conf"


def xdotool():
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), "xdotool"], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0] + "/bin/xdotool"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", default=str(ROOT / "app" / "puritty"))
    ap.add_argument("--tmux", default="tmux")
    ap.add_argument("--scenario", default="build", choices=["build", "attach", "mouse", "select", "tabs", "safety", "lines", "prefix", "prompts", "views", "menus", "panes", "status", "marks", "copy", "modes"],
                    help="build: panes made while puritty watches; attach: panes made and filled first, then attached")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "config.toml").write_text("[window]\ncolumns = 100\nrows = 30\n")
    shot = WORK / "shot.ppm"
    xdo = xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", PS1="$ ", PURITTY_SHOT=str(shot))
    for k in ("LC_ALL", "TMUX", "ENV"):
        env.pop(k, None)
    tmux = [a.tmux, "-L", SOCK, "-f", str(CONF)]
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    app = None
    n = 0

    def snap(name):
        nonlocal n
        time.sleep(0.8)
        rows = read_ppm(shot)
        n += 1
        if rows:
            save_png(WORK / f"{n:02d}-{name}.png", rows)
            print(f"{n:02d}-{name}.png")
        else:
            print(f"{n:02d}-{name}: no picture")

    def cli(*args):
        r = subprocess.run([*tmux, *args], env=env, capture_output=True, text=True)
        if r.returncode:
            print("tmux", *args, "->", r.stderr.strip())

    try:
        if a.scenario == "attach":
            attach(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "mouse":
            mouse(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "select":
            select(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "tabs":
            tabs(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "safety":
            safety(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "lines":
            lines(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "prefix":
            prefix(a, env, tmux, xdo, snap, cli)
            return
        if a.scenario == "modes":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                modes(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "copy":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                copy(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "marks":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                marks(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "status":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                status(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "panes":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                numbers(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "menus":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                menus(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "views":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                views(a, env, tmux, xdo, snap, cli, look)
            return
        if a.scenario == "prompts":
            for look in ("puritty", "tmux"):
                (WORK / "config.toml").write_text(f'[window]\ncolumns = 100\nrows = 30\n\n[tmux]\nlook = "{look}"\n')
                prompts(a, env, tmux, xdo, snap, cli, look)
            return
        app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                                *tmux, "-CC", "new-session"], env=env, stdout=subprocess.DEVNULL,
                               stderr=open(WORK / "stderr.txt", "w"))
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(1.5)
        snap("attached")
        subprocess.run([xdo, "type", "--delay", "20", "echo typed into puritty"], env=env, check=True)
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        snap("typed")
        cli("split-window", "-h")
        cli("send-keys", "-t", "%1", "printf '\\033[1;32mright pane\\033[0m 한글\\n'", "Enter")
        snap("split")
        cli("split-window", "-v", "-t", "%1")
        cli("send-keys", "-t", "%2", "ls /", "Enter")
        snap("three")
        cli("new-pane")
        snap("floating")
        subprocess.run([xdo, "type", "--delay", "20", "echo in the floating pane"], env=env, check=True)
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        snap("floating-typed")
        cli("new-pane", "-O", "-x", "36", "-y", "7")
        subprocess.run([xdo, "type", "--delay", "20", "echo modal"], env=env, check=True)
        subprocess.run([xdo, "key", "Return"], env=env, check=True)
        snap("modal")
        cli("kill-server")
        time.sleep(1)
        snap("after-exit")
    finally:
        subprocess.run([*tmux, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        if app:
            app.terminate()
            app.wait()
        xvfb.terminate()
        xvfb.wait()


def attach(a, env, tmux, xdo, snap, cli):
    """A session made and filled before puritty attaches (docs/tmux.md
    TM15): history and colors in one pane, less on the alternate screen in
    another, a floating pane; then `tmux -CC attach`, and keys typed."""
    cli("new-session", "-d", "-s", "work", "-x", "100", "-y", "29")
    cli("send-keys", "-t", "%0", "seq 1 60; printf '\\033[1;33mbefore attach\\033[0m 한글\\n'", "Enter")
    cli("split-window", "-h", "-t", "%0")
    cli("send-keys", "-t", "%1", "seq 1 200 | less", "Enter")
    cli("new-pane", "-t", "work")
    cli("send-keys", "-t", "%2", "echo floating, made before attach", "Enter")
    time.sleep(1.5)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *tmux, "-CC", "attach", "-t", "work"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(2)
        snap("attached")
        cli("select-pane", "-t", "%1")
        time.sleep(0.3)
        subprocess.run([xdo, "type", "--delay", "40", "jjjj"], env=env, check=True)
        snap("less-scrolled")
        cli("kill-server")
        time.sleep(1)
    finally:
        app.terminate()
        app.wait()


CW, CH = 9, 17   # the pixel gate's font at 96 dpi: a cell's size


BAR = 0          # rows above tmux's: the tab bar is at the bottom by default (TM22)
TABROW = 29      # the tab bar's row, the window's last of 30


def at(col, row):
    """A cell's center, in the window's pixels."""
    return str(col * CW + CW // 2), str(row * CH + CH // 2)


def at_t(col, row):
    """A cell of tmux's, by tmux's coordinates: below the tab bar."""
    return at(col, row + BAR)


def mouse(a, env, tmux, xdo, snap, cli):
    """The mouse on tmux's panes (docs/tmux.md TM16), read back from tmux:
    a click makes a pane active, a drag of a floating pane's top edge moves
    it and of its corner resizes it, a program that asked for the mouse
    gets its click at its own cell, and a key goes out by the active pane's
    DECCKM."""
    cli("new-session", "-d", "-s", "m", "-x", "100", "-y", "30")
    cli("send-keys", "-t", "%0", "printf '\\033[?1h\\033[?1000h\\033[?1006h'; stty raw -echo; cat -v", "Enter")
    cli("split-window", "-h", "-t", "%0")
    cli("new-pane", "-t", "m", "-x", "30", "-y", "6")
    time.sleep(1.0)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *tmux, "-CC", "attach", "-t", "m"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    q = lambda *args: subprocess.run([*tmux, *args], env=env, capture_output=True, text=True).stdout.strip()
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(2)
        geom = lambda: q("display-message", "-p", "-t", "%2", "#{pane_left},#{pane_top} #{pane_width}x#{pane_height}")
        print("floating before:", geom(), "| active:", q("display-message", "-p", "#{pane_id}"))
        snap("mouse-attached")
        x, y = at(80, 20)
        subprocess.run([xdo, "mousemove", x, y, "click", "1"], env=env, check=True)
        time.sleep(0.5)
        print("after a click in the right pane, active:", q("display-message", "-p", "#{pane_id}"))
        left, top = map(int, geom().split()[0].split(","))
        x0, y0 = at_t(left + 3, top - 1)
        x1, y1 = at_t(left + 13, top + 4)
        subprocess.run([xdo, "mousemove", x0, y0, "mousedown", "1", "mousemove", str(int(x0) + 30), y0,
                        "mousemove", x1, y1, "mouseup", "1"], env=env, check=True)
        time.sleep(0.6)
        print("floating after moving its top edge by 10,5:", geom())
        left, top = map(int, geom().split()[0].split(","))
        w, h = map(int, geom().split()[1].split("x"))
        x0, y0 = at_t(left + w, top + h)
        x1, y1 = at_t(left + w + 6, top + h + 2)
        subprocess.run([xdo, "mousemove", x0, y0, "mousedown", "1", "mousemove", x1, y1, "mouseup", "1"], env=env, check=True)
        time.sleep(0.6)
        print("floating after dragging its corner by 6,2:", geom())
        snap("mouse-moved")
        x, y = at_t(5, 24)
        subprocess.run([xdo, "mousemove", x, y, "click", "1"], env=env, check=True)
        time.sleep(0.4)
        subprocess.run([xdo, "key", "Up"], env=env, check=True)
        time.sleep(0.6)
        print("active:", q("display-message", "-p", "#{pane_id}"), "| the left pane's program got:",
              repr(q("capture-pane", "-p", "-t", "%0").split("cat -v")[-1].strip()[:80]))
        snap("mouse-left")
        cli("kill-server")
        time.sleep(1)
    finally:
        app.terminate()
        app.wait()


def select(a, env, tmux, xdo, snap, cli):
    """Scrollback and selection within a pane (docs/tmux.md TM17): the wheel
    scrolls the pane under the pointer, a drag and a double click select in
    that pane's own text, read back as PRIMARY, and Ctrl+Shift+C copies it to
    CLIPBOARD; a key brings the view back down."""
    cli("new-session", "-d", "-s", "s", "-x", "100", "-y", "30")
    cli("send-keys", "-t", "%0", "seq -f 'left %g' 1 200", "Enter")
    cli("split-window", "-h", "-t", "%0")
    cli("send-keys", "-t", "%1", "clear; echo 'hello world from the right pane'", "Enter")
    time.sleep(1.0)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *tmux, "-CC", "attach", "-t", "s"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    sel = lambda which: subprocess.run(["xclip", "-o", "-selection", which], env=env, capture_output=True,
                                       text=True, timeout=5).stdout
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        x, y = at(10, 10)
        xd("mousemove", x, y, "click", "4", "click", "4", "click", "4")
        time.sleep(0.5)
        snap("scrolled-left")
        x0, y0 = at_t(51, 0)
        x1, y1 = at_t(61, 0)
        xd("mousemove", x0, y0, "mousedown", "1", "mousemove", str(int(x0) + 20), y0, "mousemove", x1, y1, "mouseup", "1")
        time.sleep(0.5)
        print("a drag in the right pane, PRIMARY:", repr(sel("primary")))
        x, y = at(2, 5)
        xd("mousemove", x, y, "click", "--repeat", "2", "--delay", "80", "1")
        time.sleep(0.5)
        print("a double click on the scrolled left pane, PRIMARY:", repr(sel("primary")))
        snap("selected-left")
        xd("key", "ctrl+shift+c")
        time.sleep(0.5)
        print("Ctrl+Shift+C, CLIPBOARD:", repr(sel("clipboard")))
        xd("key", "Return")
        time.sleep(0.5)
        snap("back-down")
        cli("kill-server")
        time.sleep(1)
    finally:
        app.terminate()
        app.wait()


def tabs(a, env, tmux, xdo, snap, cli):
    """tmux's windows as tabs (docs/tmux.md TM18), read back from tmux: a
    click on a tab selects its window, `+` makes one, Ctrl+PgUp goes to the
    previous, Ctrl+Shift+T makes one, and a rename shows on its tab."""
    cli("new-session", "-d", "-s", "t", "-x", "100", "-y", "29", "-n", "editor")
    cli("send-keys", "-t", "t:0", "echo the first window", "Enter")
    cli("new-window", "-t", "t", "-n", "logs")
    cli("send-keys", "-t", "t:1", "echo the second window", "Enter")
    cli("select-window", "-t", "t:0")
    time.sleep(1.0)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *tmux, "-CC", "attach", "-t", "t"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    q = lambda *args: subprocess.run([*tmux, *args], env=env, capture_output=True, text=True).stdout.strip()
    state = lambda: f"active {q('display-message', '-p', '-t', 't', '#{window_index}:#{window_name}')}, " \
                    f"{len(q('list-windows', '-t', 't').splitlines())} windows"
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        print("attached:", state())
        snap("tabs-attached")
        # the tabs are " 0:editor │ 1:logs │ + │", on the bottom row
        x, y = at(13, TABROW)
        xd("mousemove", x, y, "click", "1")
        time.sleep(0.6)
        print("a click on the second tab:", state())
        snap("tabs-second")
        x, y = at(20, TABROW)
        xd("mousemove", x, y, "click", "1")
        time.sleep(0.8)
        print("a click on +:", state())
        xd("key", "ctrl+Prior")
        time.sleep(0.6)
        print("Ctrl+PgUp:", state())
        xd("key", "ctrl+shift+t")
        time.sleep(0.8)
        print("Ctrl+Shift+T:", state())
        cli("rename-window", "-t", "t:1", "renamed")
        time.sleep(0.6)
        snap("tabs-renamed")
        cli("kill-server")
        time.sleep(1)
    finally:
        app.terminate()
        app.wait()


PREFIX_CONF = """set -g default-shell /bin/sh
set -g default-command /bin/sh
unbind C-b
set-option -g prefix C-a
bind-key C-a send-prefix
bind | split-window -h
bind - split-window -v
unbind '"'
unbind %
setw -g mode-keys vi
bind -n C-k send-keys -R \\; send-keys C-l \\; clear-history
set -g set-clipboard on
"""


def prefix(a, env, tmux, xdo, snap, cli):
    """Keys go through tmux's key table (docs/tmux.md TM23), with a user's
    tmux.conf: prefix C-a, `|` and `-` split, vi copy mode, and a root
    binding on C-k that clears the screen and the history. Each step is
    read back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    panes = lambda: len(q("list-panes").splitlines())
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("type", "--delay", "20", "echo 한글 typed")
        xd("key", "Return")
        time.sleep(0.6)
        print("typed text:", "한글 typed" in q("capture-pane", "-p"))
        xd("key", "ctrl+a", "bar")
        time.sleep(0.8)
        print("C-a |:", panes(), "panes")
        xd("key", "ctrl+a", "minus")
        time.sleep(0.8)
        print("C-a -:", panes(), "panes")
        xd("key", "ctrl+a", "quotedbl")
        time.sleep(0.8)
        print("C-a \" (unbound):", panes(), "panes")
        snap("prefix-splits")
        # a prompt or a confirmation would leave the client answering nothing
        # (TM24): puritty asks it itself (TM25), and tmux still answers
        xd("key", "ctrl+a", "x")
        time.sleep(0.6)
        snap("prefix-confirm-asked")
        xd("key", "Escape")
        xd("key", "ctrl+a", "comma")
        time.sleep(0.4)
        xd("key", "Escape")
        xd("key", "ctrl+a", "bar")
        time.sleep(0.8)
        print("C-a x Escape, C-a , Escape, then C-a |:", panes(), "panes")
        xd("key", "ctrl+a", "i")
        time.sleep(0.6)
        snap("prefix-message")
        # suspend-client would leave tmux taking no keys from puritty (TM24)
        xd("key", "ctrl+a", "ctrl+z")
        time.sleep(0.4)
        xd("type", "--delay", "20", "echo after-suspend")
        xd("key", "Return")
        time.sleep(0.6)
        print("typing after C-a C-z:", "after-suspend" in q("capture-pane", "-p"))
        # a binding's error is said, as tmux's status line would say it
        xd("key", "ctrl+a", "5")
        time.sleep(0.6)
        snap("prefix-error")
        for _ in range(30):
            xd("type", "--delay", "5", "echo line")
            xd("key", "Return")
        time.sleep(0.5)
        print("history before C-k:", q("display-message", "-p", "#{history_size}"))
        xd("key", "ctrl+k")
        time.sleep(0.8)
        print("history after C-k:", q("display-message", "-p", "#{history_size}"))
        xd("key", "ctrl+a", "bracketleft")
        time.sleep(0.6)
        print("C-a [:", q("display-message", "-p", "#{pane_in_mode} #{pane_mode}"))
        snap("prefix-copy-mode")
        xd("key", "q")
        time.sleep(0.6)
        print("q:", q("display-message", "-p", "#{pane_in_mode}"))
        xd("key", "Up")
        time.sleep(0.4)
        xd("key", "ctrl+a", "ctrl+a")
        time.sleep(0.4)
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def prompts(a, env, tmux, xdo, snap, cli, look):
    """tmux's prompts asked by puritty (docs/tmux.md TM25), with Gilbert's
    tmux.conf, in puritty's look or tmux's: a confirmation answered and
    refused, a rename typed in English and Korean, the command prompt,
    copy mode's search and its count, and Escape; each read back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    panes = lambda: len(q("list-panes").splitlines())
    name = lambda: q("display-message", "-p", "#{window_name}")
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "bar")
        time.sleep(0.6)
        print(look, "| two panes:", panes())
        xd("key", "ctrl+a", "x")
        time.sleep(0.6)
        snap(f"{look}-confirm")
        xd("key", "n")
        time.sleep(0.5)
        print(look, "| C-a x, n:", panes(), "panes")
        xd("key", "ctrl+a", "x")
        time.sleep(0.4)
        xd("key", "y")
        time.sleep(0.6)
        print(look, "| C-a x, y:", panes(), "panes")
        xd("key", "ctrl+a", "comma")
        time.sleep(0.6)
        xd("key", "ctrl+u")
        xd("type", "--delay", "30", "editor 1")
        time.sleep(0.3)
        snap(f"{look}-rename")
        xd("key", "Return")
        time.sleep(0.6)
        print(look, "| C-a , editor 1:", repr(name()))
        xd("key", "ctrl+a", "comma")
        time.sleep(0.4)
        xd("key", "ctrl+u")
        xd("type", "--delay", "30", "한글 창")
        xd("key", "Return")
        time.sleep(0.6)
        print(look, "| C-a , in Korean:", repr(name()))
        xd("key", "ctrl+a", "comma")
        time.sleep(0.4)
        xd("type", "--delay", "30", "nope")
        xd("key", "Escape")
        time.sleep(0.5)
        print(look, "| C-a , Escape:", repr(name()), "and tmux answers:", q("display-message", "-p", "ok"))
        xd("key", "ctrl+a", "colon")
        time.sleep(0.4)
        xd("type", "--delay", "30", "split-window -h")
        xd("key", "Return")
        time.sleep(0.6)
        print(look, "| C-a : split-window -h:", panes(), "panes")
        for _ in range(20):
            xd("type", "--delay", "3", "echo line")
            xd("key", "Return")
        time.sleep(0.5)
        xd("key", "ctrl+a", "bracketleft")
        time.sleep(0.6)
        xd("key", "3", "k")
        time.sleep(0.5)
        print(look, "| copy mode, 3 k: cursor row", q("display-message", "-p", "#{copy_cursor_y}"), "of", q("display-message", "-p", "#{pane_height}"))
        xd("key", "slash")
        time.sleep(0.5)
        xd("type", "--delay", "30", "echo")
        snap(f"{look}-search")
        xd("key", "Return")
        time.sleep(0.6)
        print(look, "| / echo:", q("display-message", "-p", "#{pane_mode} #{search_present} #{search_match}"))
        xd("key", "q")
        time.sleep(0.5)
        print(look, "| q:", repr(q("display-message", "-p", "#{pane_mode}")))
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def modes(a, env, tmux, xdo, snap, cli, look):
    """tmux's other modes (docs/tmux.md TM32), with Gilbert's tmux.conf, in
    each look: `C-a w` and `C-a s` shown by puritty and a window and a
    session chosen from them; the clock (`C-a t`), and a key leaving it;
    `C-a =`, a mode puritty does not draw, said, and q leaving it. Read
    back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-s", "main", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    where = lambda: q("list-clients", "-F", "#{client_session}:#{window_index}")
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "c")
        time.sleep(0.5)
        cli("new-session", "-d", "-s", "other", "-n", "elsewhere")
        print(look, "| before:", where())
        xd("key", "ctrl+a", "w")
        time.sleep(0.8)
        snap(f"{look}-tree-windows")
        xd("key", "Up", "Return")
        time.sleep(0.8)
        print(look, "| C-a w Up Enter:", where())
        xd("key", "ctrl+a", "s")
        time.sleep(0.8)
        snap(f"{look}-tree-sessions")
        xd("key", "Up", "Return")
        time.sleep(0.8)
        print(look, "| C-a s Up Enter:", where())
        xd("key", "ctrl+a", "s")
        time.sleep(0.6)
        xd("key", "Escape")
        time.sleep(0.4)
        print(look, "| C-a s Escape:", where(), "| tmux answers:", q("display-message", "-p", "ok"))
        xd("key", "ctrl+a", "t")
        time.sleep(1.2)
        snap(f"{look}-clock")
        print(look, "| C-a t:", q("display-message", "-p", "-t", "other:", "#{pane_mode}"), "| tmux's time:", q("display-message", "-p", "%H:%M"))
        xd("key", "q")
        time.sleep(0.6)
        print(look, "| q:", repr(q("display-message", "-p", "-t", "other:", "#{pane_mode}")))
        cli("set-buffer", "-b", "one", "kept text")
        xd("key", "ctrl+a", "equal")
        time.sleep(1.0)
        print(look, "| C-a =:", q("display-message", "-p", "-t", "other:", "#{pane_mode}"))
        snap(f"{look}-buffer-mode")
        xd("key", "q")
        time.sleep(0.6)
        print(look, "| C-a = then q:", repr(q("display-message", "-p", "-t", "other:", "#{pane_mode}")))
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def copy(a, env, tmux, xdo, snap, cli, look):
    """Copy mode drawn by puritty (docs/tmux.md TM31), with Gilbert's
    tmux.conf (vi keys), in each look: entered, the cursor moved up, a
    selection begun with Space and grown, a page up, output arriving behind it,
    and Enter copying the selection (3.8's vi table has no y),
    held to tmux's buffer."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    pos = lambda: q("display-message", "-p", "#{scroll_position}/#{history_size} #{copy_cursor_x},#{copy_cursor_y}")
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("type", "--delay", "5", "for i in $(seq 1 60); do echo line $i; done")
        xd("key", "Return")
        time.sleep(1)
        xd("key", "ctrl+a", "bracketleft")
        time.sleep(0.8)
        snap(f"{look}-copy")
        xd("key", "k", "k", "k", "0")
        time.sleep(0.6)
        print(look, "| k k k 0:", pos())
        xd("key", "space", "k", "k", "dollar")
        time.sleep(0.6)
        print(look, "| Space k k $:", pos(), q("display-message", "-p", "#{selection_start_x},#{selection_start_y} #{selection_end_x},#{selection_end_y}"))
        snap(f"{look}-copy-selection")
        xd("key", "ctrl+b")
        time.sleep(0.8)
        print(look, "| C-b:", pos())
        snap(f"{look}-copy-page-up")
        xd("key", "ctrl+f")
        time.sleep(0.6)
        xd("key", "Return")
        time.sleep(0.8)
        print(look, "| Enter (copy-pipe-and-cancel), the buffer:", repr(q("show-buffer")), "| mode:", repr(q("display-message", "-p", "#{pane_mode}")))
        snap(f"{look}-copy-done")
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def marks(a, env, tmux, xdo, snap, cli, look):
    """Marks, titles and alerts (docs/tmux.md TM30), with Gilbert's
    tmux.conf, in each look: a pane marked by `C-a m`, pane titles by
    `pane-border-status top`, and a bell rung in a window behind. Read back
    from tmux, and the pictures looked at."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "bar")
        time.sleep(0.5)
        xd("key", "ctrl+a", "m")
        time.sleep(1.5)
        print(look, "| C-a m, marked:", q("display-message", "-p", "#{pane_marked}"))
        snap(f"{look}-marked")
        cli("set", "-g", "pane-border-status", "top")
        time.sleep(1.5)
        snap(f"{look}-titles")
        xd("key", "ctrl+a", "c")
        time.sleep(0.6)
        xd("type", "--delay", "20", "sleep 1; printf '\\a'")
        xd("key", "Return")
        xd("key", "ctrl+a", "0")
        time.sleep(2.5)
        print(look, "| a bell behind, flags of window 1:", repr(q("display-message", "-p", "-t", ":1", "#{window_flags}")))
        snap(f"{look}-bell")
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def status(a, env, tmux, xdo, snap, cli, look):
    """tmux's status line (docs/tmux.md TM29), with Gilbert's tmux.conf, in
    each look: status-right at the bar's right, then a styled one set while
    attached; in tmux's look the whole line as tmux draws it, a click on a
    window's text selecting it. Read back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "c")
        time.sleep(1.5)
        snap(f"{look}-status")
        cli("set", "-g", "status-right", "#[fg=white,bg=red,bold] right #[default] %H:%M ")
        cli("set", "-g", "status-left", "#[fg=yellow]<#S> ")
        time.sleep(1.5)
        snap(f"{look}-status-styled")
        if look == "tmux":
            # the first window's text, after `<0> ` (4 cells, 9 px each)
            xd("mousemove", "--window", win, "50", "500")
            xd("click", "1")
            time.sleep(0.6)
            print(look, "| a click on the first window's text, active:", q("display-message", "-p", "#{window_index}"))
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def numbers(a, env, tmux, xdo, snap, cli, look):
    """The panes' numbers (`display-panes`, docs/tmux.md TM28), with
    Gilbert's tmux.conf, in each look: `C-a q` shows them, a digit selects
    that pane, they close by themselves after `display-panes-time`, and a
    key after that reaches the pane. Each read back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    active = lambda: q("display-message", "-p", "#{pane_index}")
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "bar")
        time.sleep(0.5)
        xd("key", "ctrl+a", "minus")
        time.sleep(0.6)
        print(look, "| three panes, active:", active())
        # longer than the default second, for the picture to be taken
        # while they are up; puritty reads the option as it attaches
        cli("set", "-g", "display-panes-time", "3000")
        xd("key", "ctrl+a", "d")
        time.sleep(1.0)
        app.wait()
        app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                                *t, "-CC", "attach"], env=env, stdout=subprocess.DEVNULL,
                               stderr=open(WORK / "stderr.txt", "w"))
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "q")
        time.sleep(0.5)
        snap(f"{look}-numbers")
        xd("key", "0")
        time.sleep(0.6)
        print(look, "| C-a q 0, active:", active())
        xd("key", "ctrl+a", "q")
        time.sleep(3.5)
        snap(f"{look}-numbers-gone")
        xd("type", "--delay", "20", "echo after-numbers")
        xd("key", "Return")
        time.sleep(0.6)
        print(look, "| after display-panes-time, typing reaches the pane:", "after-numbers" in q("capture-pane", "-p"), "| active:", active())
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def menus(a, env, tmux, xdo, snap, cli, look):
    """tmux's menus shown by puritty (docs/tmux.md TM27), with Gilbert's
    tmux.conf, in each look: the window menu (`C-a <`) and the pane menu
    (`C-a >`) from the keyboard, an item chosen by its key, by the arrows
    and Enter, and one that opens a prompt; Escape; and, with tmux's mouse
    on, the right button's menu over a word, chosen by a click. Each read
    back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    panes = lambda: len(q("list-panes").splitlines())
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "less")
        time.sleep(0.8)
        snap(f"{look}-menu-window")
        xd("key", "Down", "Down")
        time.sleep(0.3)
        snap(f"{look}-menu-window-down")
        xd("key", "n")
        time.sleep(0.6)
        xd("key", "ctrl+u")
        xd("type", "--delay", "20", "renamed")
        xd("key", "Return")
        time.sleep(0.6)
        print(look, "| C-a < n renamed:", repr(q("display-message", "-p", "#{window_name}")))
        xd("key", "ctrl+a", "greater")
        time.sleep(0.8)
        snap(f"{look}-menu-pane")
        xd("key", "h")
        time.sleep(0.8)
        print(look, "| C-a > h:", panes(), "panes")
        xd("key", "ctrl+a", "less")
        time.sleep(0.6)
        xd("key", "Escape")
        time.sleep(0.4)
        print(look, "| C-a < Escape, tmux answers:", q("display-message", "-p", "ok"), "| windows:", len(q("list-windows").splitlines()))
        xd("key", "ctrl+a", "greater")
        time.sleep(0.6)
        xd("key", "Down", "Return")
        time.sleep(0.8)
        print(look, "| C-a > Down Enter (Horizontal Split):", panes(), "panes")
        # the right button, with tmux's mouse on: the pane's menu at the
        # pointer, over a word
        cli("set", "-g", "mouse", "on")
        xd("type", "--delay", "20", "echo wordy")
        xd("key", "Return")
        time.sleep(0.6)
        xd("mousemove", "--window", win, "700", "26")
        time.sleep(0.2)
        xd("click", "3")
        time.sleep(1.0)
        snap(f"{look}-menu-right")
        xd("key", "Escape")
        time.sleep(0.4)
        before = panes()
        xd("mousemove", "--window", win, "60", "26")
        xd("click", "3")
        time.sleep(1.0)
        xd("key", "v")
        time.sleep(0.8)
        print(look, "| right button, v:", before, "->", panes(), "panes")
        xd("mousemove", "--window", win, "700", "26")
        xd("click", "3")
        time.sleep(1.0)
        xd("key", "c")
        time.sleep(0.6)
        print(look, "| right button on a word, c (Copy):", repr(q("show-buffer")))
        xd("mousemove", "--window", win, "700", "26")
        xd("click", "3")
        time.sleep(1.0)
        xd("mousemove", "--window", win, "700", "348")
        time.sleep(0.2)
        snap(f"{look}-menu-hover")
        xd("click", "1")
        time.sleep(0.8)
        print(look, "| right button, a click on Zoom:", q("display-message", "-p", "#{window_zoomed_flag}"))
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def views(a, env, tmux, xdo, snap, cli, look):
    """What a binding prints, in a view (docs/tmux.md TM26), with
    Gilbert's tmux.conf, in each look: `C-a ?` opened, moved and closed,
    keys typed while it is open kept from the pane, `C-a #`, and a command
    from the colon prompt; each read back from tmux."""
    conf = WORK / "prefix.conf"
    conf.write_text(PREFIX_CONF)
    t = [a.tmux, "-L", SOCK, "-f", str(conf)]
    q = lambda *args: subprocess.run([*t, *args], env=env, capture_output=True, text=True).stdout.strip()
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *t, "-CC", "new-session", "-n", "first"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        xd("key", "ctrl+a", "bar")
        time.sleep(0.6)
        xd("key", "ctrl+a", "question")
        time.sleep(0.8)
        snap(f"{look}-view-keys")
        xd("type", "--delay", "20", "zzz")
        xd("key", "j", "j", "Next")
        time.sleep(0.4)
        snap(f"{look}-view-moved")
        xd("key", "G")
        time.sleep(0.4)
        snap(f"{look}-view-bottom")
        xd("key", "q")
        time.sleep(0.5)
        xd("type", "--delay", "20", "echo after-view")
        xd("key", "Return")
        time.sleep(0.6)
        shown = q("capture-pane", "-p")
        print(look, "| after q, typing reaches the pane:", "after-view" in shown, "| keys kept from it while open:", "zzz" not in shown)
        cli("set-buffer", "-b", "kept", "a buffer's text")
        xd("key", "ctrl+a", "numbersign")
        time.sleep(0.8)
        snap(f"{look}-view-buffers")
        xd("key", "Escape")
        xd("key", "ctrl+a", "colon")
        time.sleep(0.4)
        xd("type", "--delay", "20", "list-windows")
        xd("key", "Return")
        time.sleep(0.8)
        snap(f"{look}-view-command")
        xd("key", "q")
        time.sleep(0.4)
        print(look, "| tmux answers:", q("display-message", "-p", "ok"), "| panes:", len(q("list-panes").splitlines()))
        cli("kill-server")
        time.sleep(1)
    finally:
        subprocess.run([*t, "kill-server"], env=env, stderr=subprocess.DEVNULL)
        app.terminate()
        app.wait()


def safety(a, env, tmux, xdo, snap, cli):
    """Slow links and safety (docs/tmux.md TM19): a pane paused by tmux is
    continued and made again, so a line written while it was paused shows;
    `tmux -CC` inside a pane is detached with a note; a detach says why on
    the terminal left behind."""
    cli("new-session", "-d", "-s", "p", "-x", "100", "-y", "29")
    sh = subprocess.Popen(["sh"], stdin=subprocess.PIPE, env=env)   # unused; keeps the shape of the others
    sh.stdin.close()
    sh.wait()
    # puritty runs a shell, and tmux -CC from it, so that its terminal is
    # there to say why when control mode ends
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            "sh", "-c", " ".join(tmux) + " -CC attach -t p; echo; echo back in the shell; exec sh"],
                           env=env, stdout=subprocess.DEVNULL, stderr=open(WORK / "stderr.txt", "w"))
    q = lambda *args: subprocess.run([*tmux, *args], env=env, capture_output=True, text=True).stdout.strip()
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        subprocess.run([xdo, "windowfocus", "--sync", win], env=env, check=True)
        time.sleep(2)
        client = q("list-clients", "-F", "#{client_name} #{client_control_mode}").split()[0]
        cli("refresh-client", "-t", client, "-A", "%0:pause")
        time.sleep(0.3)
        cli("send-keys", "-t", "%0", "echo written while paused", "Enter")
        time.sleep(1.0)
        print("pane %0 after the pause, as tmux has it:", repr(q("capture-pane", "-p", "-t", "%0").strip().splitlines()[-2:]))
        snap("after-pause")
        cli("send-keys", "-t", "%0", " ".join(tmux).replace(SOCK, "puritty-bench-inner") + " -CC new-session", "Enter")
        time.sleep(2.0)
        print("inner clients after the nested -CC:", repr(subprocess.run([*tmux[:1], "-L", "puritty-bench-inner", "list-clients"],
                                                                         env=env, capture_output=True, text=True).stdout.strip()))
        snap("nested")
        subprocess.run([*tmux[:1], "-L", "puritty-bench-inner", "kill-server"], env=env, stderr=subprocess.DEVNULL)
        cli("detach-client", "-t", client)
        time.sleep(1.5)
        snap("detached")
        cli("kill-server")
        time.sleep(0.5)
    finally:
        app.terminate()
        app.wait()


def lines(a, env, tmux, xdo, snap, cli):
    """The lines between tiled panes dragged (docs/tmux.md TM20), read back
    from tmux: the line right of the left pane, and the line below the top
    right pane."""
    cli("new-session", "-d", "-s", "l", "-x", "100", "-y", "29")
    cli("split-window", "-h", "-t", "%0")
    cli("split-window", "-v", "-t", "%1")
    time.sleep(1.0)
    app = subprocess.Popen([a.puritty, "--config", str(WORK / "config.toml"), "--title", "tmux-show", "--",
                            *tmux, "-CC", "attach", "-t", "l"], env=env, stdout=subprocess.DEVNULL,
                           stderr=open(WORK / "stderr.txt", "w"))
    q = lambda *args: subprocess.run([*tmux, *args], env=env, capture_output=True, text=True).stdout.strip()
    sizes = lambda: q("list-panes", "-t", "l", "-F", "#{pane_id} #{pane_left},#{pane_top} #{pane_width}x#{pane_height}").replace("\n", " | ")
    xd = lambda *args: subprocess.run([xdo, *args], env=env, check=True)
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "tmux"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(2)
        print("before:", sizes())
        w0 = int(q("display-message", "-p", "-t", "%0", "#{pane_width}"))
        x0, y0 = at_t(w0, 5)
        x1, y1 = at_t(w0 - 10, 5)
        xd("mousemove", x0, y0, "mousedown", "1", "mousemove", str(int(x0) - 30), y0, "mousemove", x1, y1, "mouseup", "1")
        time.sleep(0.6)
        print("the vertical line dragged 10 left:", sizes())
        left = int(q("display-message", "-p", "-t", "%1", "#{pane_left}"))
        h1 = int(q("display-message", "-p", "-t", "%1", "#{pane_height}"))
        x0, y0 = at_t(left + 5, h1)
        x1, y1 = at_t(left + 5, h1 + 3)
        xd("mousemove", x0, y0, "mousedown", "1", "mousemove", x0, str(int(y0) + 20), "mousemove", x1, y1, "mouseup", "1")
        time.sleep(0.6)
        print("the horizontal line dragged 3 down:", sizes())
        snap("lines-dragged")
        cli("kill-server")
        time.sleep(1)
    finally:
        app.terminate()
        app.wait()


if __name__ == "__main__":
    main()

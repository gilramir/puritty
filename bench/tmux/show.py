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
    ap.add_argument("--scenario", default="build", choices=["build", "attach", "mouse", "select", "tabs", "safety", "lines"],
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
    TM15): history and colours in one pane, less on the alternate screen in
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
    """A cell's centre, in the window's pixels."""
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

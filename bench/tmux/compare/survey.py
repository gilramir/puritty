#!/usr/bin/env python3
"""Side-by-side survey: plain tmux (a normal client inside an outer tmux,
captured with capture-pane -p -e) against puritty -CC (PNG from
PURITTY_SHOT), same scenes, same size, same server state.

Run under a memory cap:
  systemd-run --user --scope -p MemoryMax=4G python3 survey.py [--only a,b] [--tmux PATH] [--out DIR]
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PURITTY = Path.home() / "prj" / "puritty"
sys.path.insert(0, str(PURITTY / "harness"))
import pixels  # noqa: E402
from reload import read_ppm, save_png  # noqa: E402

HERE = Path(__file__).resolve().parent
XDO = "/nix/store/lck8j0ci1qqbhqhqcmwh9w4nj4xans2n-xdotool-4.20260303.1/bin/xdotool"
XVFB = str(PURITTY / ".devbox/nix/profile/default/bin/Xvfb")
T38 = "/nix/store/k111lnbq1vw0k4v4cjhi1iwp5lky3ryn-tmux-3.8/bin/tmux"
DISPLAY = ":93"
CW, CH = 9, 17
COLS, ROWS = 100, 30

BASE_CONF = "set -g default-shell /bin/sh\nset -g default-command /bin/sh\n"
OUTER_CONF = ("set -g status off\nset -g prefix None\nunbind C-b\nset -g escape-time 0\n"
              "set -g default-terminal tmux-256color\n")

PUNCT = {"<": "less", ">": "greater", "[": "bracketleft", "]": "bracketright", ":": "colon", "=": "equal",
         "?": "question", "&": "ampersand", '"': "quotedbl", "%": "percent", "/": "slash", "-": "minus",
         ",": "comma", ".": "period", "'": "apostrophe", "~": "asciitilde", "$": "dollar", "!": "exclam",
         "#": "numbersign", "+": "plus", "{": "braceleft", "}": "braceright", ";": "semicolon",
         "(": "parenleft", ")": "parenright", "*": "asterisk"}
NAMED = {"Enter": "Return", "Escape": "Escape", "Tab": "Tab", "BTab": "shift+Tab", "Up": "Up", "Down": "Down",
         "Left": "Left", "Right": "Right", "PPage": "Prior", "NPage": "Next", "Space": "space",
         "BSpace": "BackSpace", "Home": "Home", "End": "End"}


def xkey(k):
    mods = []
    while len(k) > 2 and k[1] == "-" and k[0] in "CMS":
        mods.append({"C": "ctrl", "M": "alt", "S": "shift"}[k[0]])
        k = k[2:]
    if k in NAMED:
        base = NAMED[k]
    elif k in PUNCT:
        base = PUNCT[k]
    else:
        base = k
    return "+".join(mods + [base])


def sgr(button, col, row, release=False):
    """An SGR mouse report, 0-based cell → 1-based."""
    s = f"\033[<{button};{col + 1};{row + 1}{'m' if release else 'M'}"
    return s.encode().hex(" ").split()


class Run:
    def __init__(self, a):
        self.a = a
        self.out = Path(a.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.shot = self.out / "shot.ppm"
        self.env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()),
                        PURITTY_NO_XIM="1", PURITTY_DPI="96", LANG="C.UTF-8", PS1="$ ",
                        PURITTY_SHOT=str(self.shot))
        for k in ("LC_ALL", "TMUX", "ENV", "EDITOR", "VISUAL", "TMUX_PANE"):
            self.env.pop(k, None)
        if a.debug_log:
            self.env["XDG_STATE_HOME"] = str(self.out / "state")
        (self.out / "outer.conf").write_text(OUTER_CONF)
        self.log = open(self.out / "log.txt", "a")

    def t(self, sock, *args, conf=None):
        cmd = [self.a.tmux, "-L", sock]
        if conf:
            cmd += ["-f", str(conf)]
        r = subprocess.run([*cmd, *args], env=self.env, capture_output=True, text=True)
        if r.returncode:
            self.say(f"  tmux -L {sock} {' '.join(args)} -> {r.stderr.strip()}")
        return r.stdout

    def say(self, s):
        print(s, flush=True)
        self.log.write(s + "\n")
        self.log.flush()

    def scene(self, sc):
        name = sc["name"]
        conf = self.out / f"{name}.conf"
        conf.write_text(BASE_CONF + sc.get("conf", ""))
        A, B, O = "ccs-plain", "ccs-cc", "ccs-outer"
        for s in (A, B, O):
            subprocess.run([self.a.tmux, "-L", s, "kill-server"], env=self.env, capture_output=True)
        time.sleep(0.2)
        for s in (A, B):
            self.t(s, "new-session", "-d", "-s", "main", "-n", sc.get("first", "first"), "-x", str(COLS),
                   "-y", str(ROWS - 1), conf=conf)
            for c in sc.get("setup", []):
                if c[0] == "sleep":
                    time.sleep(c[1])
                else:
                    self.t(s, *c)
        time.sleep(sc.get("settle", 0.8))
        # the plain client, inside the outer tmux
        self.t(O, "new-session", "-d", "-s", "o", "-x", str(COLS), "-y", str(ROWS),
               f"env -u TMUX TERM=tmux-256color {self.a.tmux} -L {A} attach -t main", conf=self.out / "outer.conf")
        # puritty, control mode
        cfg = self.out / "config.toml"
        cfg.write_text(f'[window]\ncolumns = {COLS}\nrows = {ROWS}\n\n[tmux]\nlook = "{self.a.look}"\n'
                       + ('\n[debug]\nlog = true\n' if self.a.debug_log else ''))
        if self.shot.exists():
            self.shot.unlink()
        app = subprocess.Popen([self.a.puritty, "--config", str(cfg), "--title", "ccsurvey", "--",
                                self.a.tmux, "-L", B, "-CC", "attach", "-t", "main"], env=self.env,
                               stdout=subprocess.DEVNULL, stderr=open(self.out / f"{name}.stderr.txt", "w"))
        try:
            win = subprocess.run([XDO, "search", "--sync", "--name", "tmux"], env=self.env,
                                 capture_output=True, text=True, timeout=20).stdout.split()[0]
            subprocess.run([XDO, "windowfocus", "--sync", win], env=self.env, check=True)
            time.sleep(2.0)
            sizes = lambda s: self.t(s, "list-clients", "-F", "#{client_width}x#{client_height}").strip() + " win " + \
                self.t(s, "display-message", "-p", "-t", "main", "#{window_width}x#{window_height}").strip()
            self.say(f"[{name}] plain {sizes(A)} | cc {sizes(B)}")
            n = 0
            for st in sc["steps"]:
                kind = st[0]
                if kind == "keys":
                    self.t(O, "send-keys", "-t", "o", *st[1:])
                    subprocess.run([XDO, "key", "--delay", "60", *[xkey(k) for k in st[1:]]], env=self.env, check=True)
                    time.sleep(0.35)
                elif kind == "type":
                    self.t(O, "send-keys", "-t", "o", "-l", st[1])
                    subprocess.run([XDO, "type", "--delay", "30", st[1]], env=self.env, check=True)
                    time.sleep(0.35)
                elif kind == "cli":
                    for s in (A, B):
                        self.t(s, *st[1:])
                    time.sleep(0.3)
                elif kind == "out":
                    # a command's output on both, compared (TM61: a printed
                    # line is not a check)
                    pa = self.t(A, *st[1:]).strip()
                    pb = self.t(B, *st[1:]).strip()
                    self.say(f"  out {' '.join(st[1:])}: {'same' if pa == pb else 'DIFFERS'} plain [{pa}] cc [{pb}]")
                elif kind == "q":
                    self.say(f"  q {st[1]!r}: plain [{self.t(A, 'display-message', '-p', '-t', 'main', st[1]).strip()}]"
                             f" cc [{self.t(B, 'display-message', '-p', '-t', 'main', st[1]).strip()}]")
                elif kind == "dragstart":
                    _, c0, r0, c1, r1 = st
                    self.t(O, "send-keys", "-t", "o", "-H", *sgr(0, c0, r0), *sgr(32, (c0 + c1) // 2, (r0 + r1) // 2),
                           *sgr(32, c1, r1))
                    subprocess.run([XDO, "mousemove", str(c0 * CW + CW // 2), str(r0 * CH + CH // 2), "mousedown", "1",
                                    "mousemove", str(((c0 + c1) // 2) * CW + CW // 2), str(((r0 + r1) // 2) * CH + CH // 2),
                                    "mousemove", str(c1 * CW + CW // 2), str(r1 * CH + CH // 2)], env=self.env, check=True)
                    self.held = (c1, r1)
                    time.sleep(0.5)
                elif kind == "dragend":
                    c1, r1 = self.held
                    self.t(O, "send-keys", "-t", "o", "-H", *sgr(0, c1, r1, True))
                    subprocess.run([XDO, "mouseup", "1"], env=self.env, check=True)
                    time.sleep(0.5)
                elif kind == "sleep":
                    time.sleep(st[1])
                elif kind in ("click", "rclick"):
                    _, col, row = st
                    b = 0 if kind == "click" else 2
                    self.t(O, "send-keys", "-t", "o", "-H", *sgr(b, col, row), *sgr(b, col, row, True))
                    x, y = str(col * CW + CW // 2), str(row * CH + CH // 2)
                    subprocess.run([XDO, "mousemove", x, y, "click", "1" if b == 0 else "3"], env=self.env, check=True)
                    time.sleep(0.5)
                elif kind == "rpress":  # right press, held (menus open on press)
                    _, col, row = st
                    self.t(O, "send-keys", "-t", "o", "-H", *sgr(2, col, row))
                    x, y = str(col * CW + CW // 2), str(row * CH + CH // 2)
                    subprocess.run([XDO, "mousemove", x, y, "mousedown", "3"], env=self.env, check=True)
                    time.sleep(0.5)
                elif kind == "drag":
                    _, c0, r0, c1, r1 = st
                    hx = sgr(0, c0, r0)
                    steps = 4
                    for i in range(1, steps + 1):
                        hx += sgr(32, c0 + (c1 - c0) * i // steps, r0 + (r1 - r0) * i // steps)
                    hx += sgr(0, c1, r1, True)
                    self.t(O, "send-keys", "-t", "o", "-H", *hx)
                    pts = []
                    for i in range(1, steps + 1):
                        cc, rr = c0 + (c1 - c0) * i // steps, r0 + (r1 - r0) * i // steps
                        pts += ["mousemove", str(cc * CW + CW // 2), str(rr * CH + CH // 2), "sleep", "0.05"]
                    subprocess.run([XDO, "mousemove", str(c0 * CW + CW // 2), str(r0 * CH + CH // 2), "mousedown", "1",
                                    *pts, "mouseup", "1"], env=self.env, check=True)
                    time.sleep(0.5)
                elif kind == "shot":
                    n += 1
                    label = f"{name}-{n}-{st[1]}"
                    time.sleep(st[2] if len(st) > 2 else 1.0)
                    (self.out / f"{label}.tmux.ans").write_text(self.t(O, "capture-pane", "-p", "-e", "-t", "o"))
                    (self.out / f"{label}.tmux.txt").write_text(self.t(O, "capture-pane", "-p", "-t", "o"))
                    rows = read_ppm(self.shot)
                    if rows:
                        save_png(self.out / f"{label}.puritty.png", rows)
                    q = "#{pane_id} mode=#{pane_mode} zoom=#{window_zoomed_flag} win=#{window_index}"
                    self.say(f"  {label}: plain [{self.t(A, 'display-message', '-p', '-t', 'main', q).strip()}]"
                             f" cc [{self.t(B, 'display-message', '-p', '-t', 'main', q).strip()}]"
                             f"{'' if rows else ' NO PICTURE'}")
        except Exception as e:  # noqa: BLE001
            self.say(f"[{name}] FAILED: {e!r}")
        finally:
            app.terminate()
            try:
                app.wait(timeout=5)
            except subprocess.TimeoutExpired:
                app.kill()
                app.wait()
            for s in (A, B, O):
                subprocess.run([self.a.tmux, "-L", s, "kill-server"], env=self.env, capture_output=True)
            time.sleep(0.3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", default=str(PURITTY / "app" / "puritty"))
    ap.add_argument("--tmux", default=T38)
    ap.add_argument("--look", default="tmux")
    ap.add_argument("--out", default=str(PURITTY / ".harness-work" / "tmux-compare" / "out-3.8"))
    ap.add_argument("--only", default="")
    ap.add_argument("--scenes", default="scenes")
    ap.add_argument("--debug-log", action="store_true",
                    help="puritty's diagnostic log on, written under OUT/state/puritty/logs")
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    import importlib
    SCENES = importlib.import_module(a.scenes).SCENES
    only = [s for s in a.only.split(",") if s]
    run = Run(a)
    xvfb = subprocess.Popen([XVFB, DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    try:
        for sc in SCENES:
            if only and sc["name"] not in only:
                continue
            run.scene(sc)
    finally:
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

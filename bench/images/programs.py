#!/usr/bin/env python3
"""Real programs drawing pictures in puritty (docs/images.md IM29): gnuplot
(Sixel and Kitty), chafa, timg and yazi's preview, in a plain shell, in
plain tmux and in tmux's control mode (`-CC`); with tmux, the pane split,
resized and zoomed and puritty's window resized under the picture.

puritty runs on Xvfb and writes each frame's picture to a file
(PURITTY_SHOT), which is saved as a PNG after each step, in
.harness-work/images-programs/MODE/. Each picture is checked by its colors:
the test pictures and plots are drawn in a red, green or blue that no
prompt or text has, so the count of those pixels in the window says
whether the picture is there, and how much of it.

    devbox run -- python3 bench/images/programs.py [--mode shell|plain|cc|all]

`--showcase` instead draws the screenshots for the website (gnuplot's
plots in tmux -CC panes, at 144 dpi in Fira Code and Ghostty's colors),
into .harness-work/images-programs/showcase/, and checks nothing.
Stops what it started.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "bench" / "tmux"))
import pixels  # noqa: E402  (its fonts)
from reload import read_ppm, save_png  # noqa: E402
from show import check, note, report, that, xdotool  # noqa: E402

DISPLAY = ":88"
SOCK = "puritty-images-programs"
WORK = ROOT / ".harness-work" / "images-programs"
CONF = ROOT / "packages" / "tmux" / "tests" / "data" / "tmux.conf"
NIXPKGS = "github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600"

RED, GREEN, BLUE = (255, 0, 0), (0, 200, 0), (0, 0, 255)


def tool(name):
    """A program from the pinned nixpkgs, built or fetched once."""
    out = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", f"{NIXPKGS}#{name}"],
                         capture_output=True, text=True, check=True).stdout.split()
    return [p for p in out if not p.endswith(("-man", "-doc"))][0] + "/bin"


def count(rows, color):
    """Pixels near `color` in a window's picture; Sixel's colors are
    percentages and gnuplot's are anti-aliased at the edges, so near."""
    want = color
    n = 0
    for r in rows or []:
        for i in range(0, len(r) - 2, 3):
            if abs(r[i] - want[0]) < 40 and abs(r[i + 1] - want[1]) < 40 and abs(r[i + 2] - want[2]) < 40:
                n += 1
    return n


def pictures(folder):
    """The test pictures: one color each, so a count says which is shown;
    and a few to browse in yazi."""
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    for name, color in (("red", RED), ("green", GREEN), ("blue", BLUE)):
        Image.new("RGB", (160, 96), color).save(folder / f"{name}.png")
    Image.new("RGB", (160, 96), BLUE).save(folder / "blue.jpg", quality=95)
    return folder


# gnuplot drawing a block of one color, which the count finds: Sixel by
# libgd, Kitty's by cairo
def plot(term, color):
    hexc = "#%02x%02x%02x" % color
    return (f"gnuplot -e 'set term {term} size 320,200; unset key; unset border; unset tics; "
            f"set style fill solid; plot [0:1] [0:1] 1 with filledcurves y1=0 lc rgb \"{hexc}\"'")


def whole_ppm(data):
    """A P6 picture's rows from its bytes, or None while it is cut."""
    parts = data[:64].split(maxsplit=4)
    if len(parts) < 5 or parts[0] != b"P6":
        return None
    try:
        w, h = int(parts[1]), int(parts[2])
    except ValueError:
        return None
    # the header ends after the maximum value and one whitespace byte
    at = data.index(parts[3], len(parts[0]) + len(parts[1]) + len(parts[2])) + len(parts[3]) + 1
    if len(data) - at != w * h * 3:
        return None
    return [data[at + y * w * 3:at + (y + 1) * w * 3] for y in range(h)]


class Run:
    """puritty on Xvfb, in one mode, and how to type into what it runs."""

    def __init__(self, a, mode, path, dpi=96, config=None, columns=100, rows=30, size="1600x1000"):
        self.a, self.mode = a, mode
        self.bare = mode in ("shell", "showcase-shell", "seashell")   # a shell, no tmux
        self.work = WORK / mode
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        self.shot = self.work / "shot.ppm"
        self.n = 0
        (self.work / "config.toml").write_text(config or f"[window]\ncolumns = {columns}\nrows = {rows}\n")
        fonts = {} if config else {"FONTCONFIG_FILE": str(pixels.write_fonts_conf())}
        self.env = dict(os.environ, DISPLAY=DISPLAY, PURITTY_NO_XIM="1", PURITTY_DPI=str(dpi), LANG="C.UTF-8",
                        PS1="$ ", PURITTY_SHOT=str(self.shot), PATH=path + ":" + os.environ["PATH"], **fonts)
        for k in ("LC_ALL", "TMUX", "ENV", "TERM_PROGRAM", "KITTY_WINDOW_ID"):
            self.env.pop(k, None)
        self.tmux = [a.tmux, "-L", SOCK, "-f", str(CONF)]
        self.xdo = xdotool()
        self.xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", size + "x24", "-nolisten", "tcp"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        self.app = None
        self.win = None

    def start(self):
        """puritty, running a shell, plain tmux, or `tmux -CC`."""
        if not self.bare:
            self.cli("new-session", "-d", "-s", "img", "-x", "100", "-y", "29")
            self.cli("set", "-g", "allow-passthrough", "on")
            time.sleep(0.5)
        command = {"shell": ["bash", "--norc", "--noprofile"],
                   "showcase-shell": ["bash", "--norc", "--noprofile"],
                   "seashell": ["bash", "--norc", "--noprofile"],
                   "plain": [*self.tmux, "attach", "-t", "img"],
                   "cc": [*self.tmux, "-CC", "attach", "-t", "img"],
                   "showcase": [*self.tmux, "-CC", "attach", "-t", "img"]}[self.mode]
        self.app = subprocess.Popen([self.a.puritty, "--config", str(self.work / "config.toml"), "--title",
                                     "images-programs", "--", *command], env=self.env, stdout=subprocess.DEVNULL,
                                    stderr=open(self.work / "stderr.txt", "w"))
        self.win = subprocess.run([self.xdo, "search", "--sync", "--name", "tmux|images-programs"], env=self.env,
                                  capture_output=True, text=True, timeout=20).stdout.split()[0]
        subprocess.run([self.xdo, "windowfocus", "--sync", self.win], env=self.env, check=True)
        time.sleep(2)

    def cli(self, *args):
        r = subprocess.run([*self.tmux, *args], env=self.env, capture_output=True, text=True)
        if r.returncode:
            print("tmux", *args, "->", r.stderr.strip())
        return r.stdout

    def run(self, command, pane=None, wait=2.5):
        """A command typed at the shell: by tmux into a pane, or by xdotool."""
        if self.bare:
            subprocess.run([self.xdo, "type", "--delay", "5", command], env=self.env, check=True)
            subprocess.run([self.xdo, "key", "Return"], env=self.env, check=True)
        else:
            self.cli("send-keys", *(["-t", pane] if pane else []), command, "Enter")
        time.sleep(wait)

    def keys(self, *keys, pane=None, wait=1.0):
        if self.bare:
            subprocess.run([self.xdo, "key", *keys], env=self.env, check=True)
        else:
            self.cli("send-keys", *(["-t", pane] if pane else []), *keys)
        time.sleep(wait)

    def snap(self, name):
        time.sleep(0.8)
        rows = None
        for _ in range(10):
            # puritty may be writing the file as it is read: read again
            try:
                # one read, parsed here: the file is written again each
                # frame, and an empty or cut one sends read_ppm round its
                # header for ever
                rows = whole_ppm(self.shot.read_bytes())
            except OSError:
                rows = None
            if rows and len(rows[-1]) == len(rows[0]):
                break
            time.sleep(0.2)
        self.n += 1
        if rows:
            save_png(self.work / f"{self.n:02d}-{name}.png", rows)
            print(f"     {self.mode}/{self.n:02d}-{name}.png", flush=True)
        return rows

    def resize(self, width, height):
        subprocess.run([self.xdo, "windowsize", "--sync", self.win, str(width), str(height)], env=self.env)
        time.sleep(1.5)

    def stop(self):
        if not self.bare:
            subprocess.run([*self.tmux, "kill-server"], env=self.env, stderr=subprocess.DEVNULL)
        if self.app:
            self.app.terminate()
            try:
                self.app.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.app.kill()
        self.xvfb.terminate()
        self.xvfb.wait()

    def alive(self):
        return self.app.poll() is None


def programs(a, mode, path):
    """Each program's picture in one mode, then what a pane's changes do
    to a picture (with tmux), and a clear."""
    r = Run(a, mode, path)
    pics = pictures(r.work / "pics")
    try:
        r.start()
        clear = "clear"
        steps = [
            ("gnuplot sixelgd", plot("sixelgd", RED), RED),
            ("chafa, left to choose", f"chafa --size 20x6 {pics / 'blue.png'}", BLUE),
            ("chafa -f sixel", f"chafa -f sixel --size 20x6 {pics / 'red.png'}", RED),
            ("chafa -f iterm", f"chafa -f iterm --size 20x6 {pics / 'blue.png'}", BLUE),
            ("timg, left to choose", f"timg -g 20x6 {pics / 'red.png'}", RED),
            ("timg -ps (Sixel), a JPEG", f"timg -ps -g 20x6 {pics / 'blue.jpg'}", BLUE),
        ]
        # plain tmux keeps Sixel only (3.8 built with it): a Kitty or iTerm2
        # picture not wrapped for passthrough never reaches puritty
        dropped = ("chafa -f iterm",) if mode == "plain" else ()
        for name, command, color in steps:
            r.run(clear, wait=0.6)
            r.run(command)
            rows = r.snap(name.split(",")[0].replace(" ", "-"))
            if name in dropped:
                check(f"{mode}: {name}: dropped by tmux, as tmux does", count(rows, color), 0)
            else:
                check(f"{mode}: {name}: its color in the window", count(rows, color), that("more than 2000 pixels", lambda n: n > 2000))
        check(f"{mode}: puritty still running after the programs", r.alive(), True)

        # a picture on the screen through changes to the window and its pane
        r.run(clear, wait=0.6)
        r.run(plot("sixelgd", RED))
        shown = count(r.snap("before-changes"), RED)
        if mode != "shell":
            r.cli("split-window", "-h", "-t", "img")
            time.sleep(1.5)
            rows = r.snap("split-beside")
            if mode == "plain":
                # tmux frees a pane's images when it is resized (3.8
                # screen.c:381, screen_resize), and redraws the pane without
                check(f"{mode}: the pane split beside the picture: gone, as tmux frees it", count(rows, RED), 0)
            else:
                check(f"{mode}: the pane split beside the picture: still drawn", count(rows, RED), that("over half of it", lambda n: n > shown // 2))
            r.cli("resize-pane", "-t", "img:0.0", "-x", "30")
            time.sleep(1.5)
            r.snap("pane-narrowed")
            check(f"{mode}: the pane narrowed under the picture: puritty runs", r.alive(), True)
            r.cli("resize-pane", "-Z", "-t", "img:0.0")
            time.sleep(1.5)
            r.snap("zoomed")
            r.cli("resize-pane", "-Z", "-t", "img:0.0")
            r.cli("kill-pane", "-t", "img:0.1")
            time.sleep(1)
        r.resize(600, 400)
        r.snap("window-small")
        r.resize(1300, 800)
        rows = r.snap("window-large")
        check(f"{mode}: the window made small and large again: puritty runs", r.alive(), True)
        note(f"{mode}: red pixels before {shown}, after the resizes {count(rows, RED)}")
        r.run(clear, wait=1.0)
        check(f"{mode}: clear takes the picture away", count(r.snap("cleared"), RED), 0)

        # yazi's preview of a picture: it chooses its own way to draw
        r.run(f"cd {pics} && yazi", wait=3.0)
        for _ in range(3):
            r.keys("j", wait=0.3)
        r.keys("k", "k", "k", wait=2.0)  # back to blue.jpg, the first entry
        rows = r.snap("yazi")
        # under -CC yazi asks through tmux's passthrough, which puritty
        # answers into the pane (docs/images.md IM33)
        check(f"{mode}: yazi's preview of blue.jpg", count(rows, BLUE), that("more than 1000 pixels", lambda n: n > 1000))
        r.keys("j", wait=2.0)  # blue.png
        r.keys("j", wait=2.0)  # green.png
        rows = r.snap("yazi-green")
        check(f"{mode}: yazi moved on to green.png: green shown", count(rows, GREEN), that("more than 1000 pixels", lambda n: n > 1000))
        check(f"{mode}: and blue gone", count(rows, BLUE), that("fewer than 200 pixels", lambda n: n < 200))
        r.keys("q", wait=1.0)
        # until yazi has ended: under -CC it waits out its unanswered
        # questions first, and would take the keys typed after it
        for _ in range(40):
            if r.mode == "shell" or r.cli("display", "-p", "-t", "img", "#{pane_current_command}").strip() != "yazi":
                break
            time.sleep(0.5)
        time.sleep(1.0)

        # Kitty's pictures last, as they were run before IM30, when a -CC
        # pane's `clear` left them
        for name, command, color in (("gnuplot kittycairo", plot("kittycairo", GREEN), GREEN),
                                     ("chafa -f kitty", f"chafa -f kitty --size 20x6 {pics / 'green.png'}", GREEN)):
            r.run(clear, wait=0.6)
            r.run(command)
            rows = r.snap(name.replace(" ", "-"))
            if mode == "plain":
                check(f"{mode}: {name}: dropped by tmux, as tmux does", count(rows, color), 0)
            else:
                check(f"{mode}: {name}: its color in the window", count(rows, color), that("more than 2000 pixels", lambda n: n > 2000))
        r.run(clear, wait=1.0)
        left = count(r.snap("cleared-after-kitty"), GREEN)
        # under -CC too, since a pane's Kitty pictures are drawn into its
        # cells (docs/images.md IM30, Gilbert's call on review.md RV3)
        check(f"{mode}: clear after Kitty's pictures takes them away", left, 0)
        check(f"{mode}: puritty still running at the end", r.alive(), True)
    finally:
        r.stop()


SURFACE = """\
set term {term} size {w},{h} {font} background rgb '#282c34'
set border lc rgb '#abb2bf'; set tics textcolor rgb '#abb2bf'
set title 'sin(r)/r' textcolor rgb '#e5e5e5'
set key off; set hidden3d; set isosamples 60,60; set view 60,30
set pm3d at s; set palette defined (0 '#1a1b4b', 1 '#2f6db5', 2 '#4fc1a6', 3 '#f2e863', 4 '#f28f3b')
unset colorbox
r(x,y) = sqrt(x*x+y*y) + 1e-9
splot [-12:12] [-12:12] sin(r(x,y))/r(x,y) with pm3d
"""

WAVES = """\
set term {term} size {w},{h} {font} background rgb '#282c34'
set border lc rgb '#abb2bf'; set tics textcolor rgb '#abb2bf'
set key textcolor rgb '#e5e5e5' top right; set grid lc rgb '#3e4451'
set samples 400
plot [0:20] exp(-x/8)*sin(2*x) w l lw 2 lc rgb '#61afef' t 'damped', \\
     exp(-x/8) w l lw 1 dt 2 lc rgb '#e5c07b' t 'envelope', \\
     -exp(-x/8) w l lw 1 dt 2 lc rgb '#e5c07b' notitle, \\
     0.6*cos(x)*exp(-x/12) w filledcurves y1=0 fs transparent solid 0.35 lc rgb '#c678dd' t 'cos'
"""

# the home page's picture (docs/images.md IM36): the script the site
# offers (site/static/plots/seashell.gp), its size made the shot's
SEASHELL = ROOT / "site" / "static" / "plots" / "seashell.gp"


def seashell(a, path):
    """The home page's picture: the seashell drawn by gnuplot by Kitty's
    protocol in a shell, under the command that drew it, at 144 dpi in
    Fira Code and Ghostty's colors."""
    config = ("[window]\ncolumns = 120\nrows = 34\npadding = 8\n\n[font]\nfamily = \"Fira Code\"\nsize = 11\n\n"
              "[colors]\nscheme = \"ghostty\"\n")
    prompt = ("G=$(printf '\\033[32m') B=$(printf '\\033[34m') N=$(printf '\\033[0m'); "
              "PS1=\"${G}you@linux${N}:${B}~/plots${N}\\$ \"")
    r = Run(a, "seashell", path, dpi=144, config=config, size="2400x1500")
    plots = r.work / "plots"
    plots.mkdir()
    try:
        r.start()
        script = SEASHELL.read_text()
        # the term line and its continuations, made the shot's size
        script = re.sub(r"(?m)^set term kittycairo(?:.*\\\n)*.*$", "set term kittycairo scroll size 1380,660 background rgb '#282c34'", script)
        (plots / "seashell.gp").write_text(script)
        r.run(f"{prompt}; cd {plots}; clear", wait=0.8)
        r.run("gnuplot seashell.gp", wait=10)
        r.snap("seashell")
    finally:
        r.stop()


def showcase(a, path):
    """The website's shots, at 144 dpi in Fira Code and Ghostty's colors:
    gnuplot's plots in two tmux -CC panes, by Kitty's protocol (cairo) and
    by Sixel (libgd), and one large plot in a shell. Each plot drawn where
    the cursor is (`scroll`), under the command that drew it."""
    config = ("[window]\ncolumns = 120\nrows = 34\npadding = 8\n\n[font]\nfamily = \"Fira Code\"\nsize = 11\n\n"
              "[colors]\nscheme = \"ghostty\"\n")
    # the colors by printf, which bash and tmux's sh both run
    prompt = ("G=$(printf '\\033[32m') B=$(printf '\\033[34m') N=$(printf '\\033[0m'); "
              "PS1=\"${G}you@linux${N}:${B}~/plots${N}\\$ \"")
    terms = {"kitty": "kittycairo scroll font 'Fira Code,10'",
             "sixel": "sixelgd scroll truecolor font 'Fira Code,10'"}
    for mode in ("showcase", "showcase-shell"):
        r = Run(a, mode, path, dpi=144, config=config, size="2400x1500")
        plots = r.work / "plots"
        plots.mkdir()
        try:
            r.start()
            if mode == "showcase":
                for label, term in terms.items():
                    (plots / f"surface.gp").write_text(SURFACE.format(term=term, w=740, h=560, font=""))
                    (plots / f"waves.gp").write_text(WAVES.format(term=term, w=740, h=400, font=""))
                    r.cli("kill-pane", "-a", "-t", "img:0.0")
                    r.cli("split-window", "-h", "-t", "img:0.0")
                    time.sleep(1)
                    for pane in ("img:0.0", "img:0.1"):
                        r.run(f"{prompt}; cd {plots}; clear", pane=pane, wait=0.8)
                    r.run("gnuplot surface.gp", pane="img:0.0", wait=5)
                    r.run("gnuplot waves.gp", pane="img:0.1", wait=5)
                    r.run("ls", pane="img:0.1", wait=1.5)
                    r.snap(f"gnuplot-tmux-{label}")
            else:
                # the command above the plot and the prompt under it
                for label, term in terms.items():
                    (plots / "surface.gp").write_text(SURFACE.format(term=term, w=1380, h=690, font=""))
                    r.run(f"{prompt}; cd {plots}; clear", wait=0.8)
                    r.run("gnuplot surface.gp", wait=6)
                    r.snap(f"gnuplot-shell-{label}")
        finally:
            r.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", default=str(ROOT / "app" / "puritty"))
    ap.add_argument("--tmux", default="tmux")
    ap.add_argument("--mode", default="all", choices=["shell", "plain", "cc", "all"])
    ap.add_argument("--showcase", action="store_true")
    ap.add_argument("--seashell", action="store_true", help="the home page's picture alone")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    path = ":".join([tool("gnuplot"), tool("yazi"), tool("file")])
    if a.showcase:
        showcase(a, path)
        return
    if a.seashell:
        seashell(a, path)
        return
    for mode in (["shell", "plain", "cc"] if a.mode == "all" else [a.mode]):
        programs(a, mode, path)
    report()


if __name__ == "__main__":
    main()

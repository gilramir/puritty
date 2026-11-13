#!/usr/bin/env python3
"""The site's picture of tmux -CC in puritty (docs/images/tmux-panes.png,
the home page's tmux section and the tmux guide): tmux 3.8 with four
windows, the one shown split left and right, English in every text style
puritty draws on the left, Korean on the right, and a floating pane over
them; puritty attached with `tmux -CC`, in Ghostty's colors and Fira
Code. The picture is puritty's own (PURITTY_SHOT), on Xvfb.

    devbox run -- python3 docs/images/tmux-panes.py
"""

import os
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402
from reload import read_ppm, save_png  # noqa: E402

TMUX = "/nix/store/k111lnbq1vw0k4v4cjhi1iwp5lky3ryn-tmux-3.8/bin/tmux"
DISPLAY = ":88"
SOCK = "puritty-picture"
WORK = ROOT / ".harness-work" / "tmux-picture"
OUT = Path(__file__).resolve().parent / "tmux-panes.png"
COLS, ROWS = 124, 36

E = "\x1b["


def sgr(*codes):
    return E + ";".join(str(c) for c in codes) + "m"


R = sgr(0)


def width(s):
    n = 0
    for ch in s:
        if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
            continue
        n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n


def rgb(r, g, b, bg=False):
    return E + ("48" if bg else "38") + f";2;{r};{g};{b}m"


def gradient(n, a, b):
    """A bar of n cells from color a to color b, in 24-bit color."""
    out = ""
    for i in range(n):
        t = i / max(1, n - 1)
        c = [round(a[k] + (b[k] - a[k]) * t) for k in range(3)]
        out += rgb(*c, bg=True) + " "
    return out + R


def left():
    """English, in every style: puritty's own core draws each pane."""
    dim = sgr(2)
    head = lambda t: sgr(1, 38, 5, 117) + t + R
    lines = [
        "",
        " " + sgr(1) + rgb(255, 196, 120) + "puritty" + R + sgr(1) + " draws every tmux pane itself" + R,
        " " + dim + "each one a full terminal, fed by tmux -CC" + R,
        "",
        " " + head("Styles"),
        "   " + sgr(1) + "bold" + R + "  " + sgr(3) + "italic" + R + "  " + sgr(1, 3) + "bold italic" + R
        + "  " + sgr(2) + "dim" + R + "  " + sgr(9) + "struck" + R + "  " + sgr(53) + "overlined" + R,
        "   " + sgr(4) + "underline" + R + "  " + E + "4:2m" + "double" + R + "  " + E + "4:4m" + "dotted" + R
        + "  " + E + "4:5m" + "dashed" + R + "  " + sgr(7) + " reverse " + R,
        "   " + E + "4:3m" + E + "58:2::255:85:85m" + "a curly red underline" + R + ", as a spell checker marks it",
        "",
        " " + head("Color"),
        "   " + "".join(sgr(40 + i) + "  " + R for i in range(8)) + "  "
        + "".join(sgr(100 + i) + "  " + R for i in range(8)),
        "   " + gradient(16, (255, 94, 98), (255, 195, 113)) + gradient(16, (255, 195, 113), (99, 214, 255))
        + gradient(16, (99, 214, 255), (186, 140, 255)),
        "",
        " " + head("Code") + dim + "   lint marks and ligatures" + R,
    ]
    kw, fn, st, ty, cm, nb = sgr(38, 5, 176), sgr(38, 5, 117), sgr(38, 5, 150), sgr(38, 5, 222), sgr(3, 38, 5, 244), sgr(38, 5, 240)
    curly = E + "4:3m" + E + "58:2::255:85:85m"
    code = [
        f"{kw}fn{R} {fn}greet{R}(name: {ty}&str{R}) {kw}->{R} {ty}String{R} {{",
        f"    {cm}// say hello, warmly{R}",
        f"    {kw}if{R} name {kw}!={R} {st}\"\"{R} {kw}&&{R} name.len() {kw}>={R} 1 {{",
        f"        {kw}return{R} format!({st}\"{curly}Helo{R}{st}, {{name}}!\"{R});",
        f"    }}",
        f"    {st}\"Hello, world!\"{R}.to_string()",
        f"}}",
    ]
    for i, c in enumerate(code, 1):
        lines.append(f"  {nb}{i:>2}{R}  {c}")
    lines.append("  " + nb + "  " + R + "  " + sgr(38, 5, 203) + "      ╰─ " + sgr(3) + "did you mean \"Hello\"?" + R)
    lines.append("")
    lines.append(" " + head("Symbols") + "   ✓ ✗ → ⇄ ⚡ ★ ♥ ⌘ ⏎ 🚀 ✨ 🐧")
    lines.append("")
    lines.append(" " + sgr(1, 32) + "you@puritty" + R + ":" + sgr(1, 34) + "~/demo" + R + "$ ")
    return "\r\n".join(lines)


def right():
    """Korean: Yun Dong-ju's 서시 (1941), and a small table."""
    title = sgr(1) + rgb(255, 196, 120)
    dim = sgr(2, 3)
    poem = [
        "죽는 날까지 하늘을 우러러",
        "한 점 부끄럼이 없기를,",
        "잎새에 이는 바람에도",
        "나는 괴로워했다.",
        "별을 노래하는 마음으로",
        "모든 죽어 가는 것을 사랑해야지",
        "그리고 나한테 주어진 길을",
        "걸어가야겠다.",
        "",
        sgr(1, 38, 5, 117) + "오늘 밤에도 별이 바람에 스치운다." + R,
    ]
    lines = ["", " " + title + "서시" + R + "  " + dim + "윤동주, 1941년 11월 20일" + R, ""]
    lines += ["   " + p for p in poem]
    lines += ["", " " + sgr(1, 38, 5, 117) + "날씨" + R + "  " + dim + "wide characters, lined up" + R]
    rows = [("도시", "하늘", "기온"), ("서울", "맑음 ☀", "18°C"), ("부산", "구름 ⛅", "21°C"), ("제주", "비 🌧", "19°C")]
    widths = [max(width(r[i]) for r in rows) + 2 for i in range(3)]
    H = "─"
    lines.append("   ┌" + "┬".join(H * w for w in widths) + "┐")
    for k, r in enumerate(rows):
        cells = []
        for i, c in enumerate(r):
            pad = " " * (widths[i] - 1 - width(c))
            style = sgr(1, 33) if k == 0 else (sgr(36) if i == 0 else "")
            cells.append(" " + style + c + (R if style else "") + pad)
        lines.append("   │" + "│".join(cells) + "│")
        if k == 0:
            lines.append("   ├" + "┼".join(H * w for w in widths) + "┤")
    lines.append("   └" + "┴".join(H * w for w in widths) + "┘")
    lines += ["", " " + sgr(1, 32) + "사용자@puritty" + R + ":" + sgr(1, 34) + "~/문서" + R + "$ "]
    return "\r\n".join(lines)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "left.ans").write_text(left())
    (WORK / "right.ans").write_text(right())
    shot = WORK / "shot.ppm"
    shot.unlink(missing_ok=True)
    (WORK / "config.toml").write_text(
        f'[window]\ncolumns = {COLS}\nrows = {ROWS}\n\n[font]\nfamily = "Fira Code"\nsize = 12\nlanguage = "ko"\n\n'
        '[colors]\nscheme = "ghostty"\n')
    conf = WORK / "tmux.conf"
    conf.write_text('set -g default-shell /bin/sh\nset -g status-right " tmux 3.8 "\n'
                    'set -g pane-border-status off\n')
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="120", LANG="C.UTF-8", PURITTY_SHOT=str(shot))
    for k in ("LC_ALL", "TMUX", "TMUX_PANE", "ENV"):
        env.pop(k, None)
    t = [TMUX, "-L", SOCK, "-f", str(conf)]
    tm = lambda *a: subprocess.run([*t, *a], env=env, capture_output=True, text=True, check=True).stdout
    hold = "; exec sleep 100000"
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "2400x1500x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    app = None
    try:
        time.sleep(0.6)
        tm("new-session", "-d", "-s", "demo", "-n", "work", "-x", str(COLS), "-y", str(ROWS - 1),
           f"cat {WORK / 'left.ans'}{hold}")
        tm("split-window", "-h", "-t", "demo:work", f"cat {WORK / 'right.ans'}{hold}")
        for name in ("editor", "서버", "logs"):
            tm("new-window", "-d", "-t", "demo", "-n", name)
        tm("select-window", "-t", "demo:work")
        # the floating pane: puritty's own history, in color
        log = ("git --no-pager -C " + str(ROOT) + " log --graph --color=always --date=short -5 "
               "--format='%C(yellow)%h%C(reset) %C(green)%ad%C(reset) %<(44,trunc)%s'")
        tm("new-pane", "-t", "demo:work", "-x", "71", "-y", "8", "-X", "44", "-Y", "26", f"{log}{hold}")
        time.sleep(0.8)
        app = subprocess.Popen([str(ROOT / "app" / "puritty"), "--config", str(WORK / "config.toml"), "--title", "tmux",
                                "--", *t, "-CC", "attach", "-t", "demo"], env=env,
                               stdout=subprocess.DEVNULL, stderr=open(WORK / "stderr.txt", "w"))
        time.sleep(4)
        rows = read_ppm(shot)
        if not rows:
            raise SystemExit("puritty drew no picture")
        save_png(OUT, rows)
        print(OUT, len(rows[0]) // 3 if isinstance(rows[0], (bytes, bytearray)) else "", len(rows))
    finally:
        subprocess.run([*t, "kill-server"], env=env, capture_output=True)
        if app:
            app.terminate()
            app.wait()
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

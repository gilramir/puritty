#!/usr/bin/env python3
"""Scrollback search and the scrollbar, shown (docs/phase3-select.md §23):
puritty on Xvfb with 600 lines of scrollback, one with a word to find;
Ctrl+Shift+F, the word typed, Enter for an older match, Ctrl+Shift+C, the
clipboard read back; then a drag of the scrollbar. Pictures in
.harness-work/search-show/."""
import os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402
from reload import read_ppm, save_png  # noqa: E402
sys.path.insert(0, str(ROOT / "bench" / "tmux"))
from show import xdotool  # noqa: E402

WORK = ROOT / ".harness-work" / "search-show"
DISPLAY = ":88"


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "config.toml").write_text("[window]\ncolumns = 80\nrows = 24\n")
    shot = WORK / "shot.ppm"
    xdo = xdotool()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1",
               PURITTY_DPI="96", LANG="C.UTF-8", PURITTY_SHOT=str(shot))
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    script = ("seq -f 'line %g' 1 200; echo 'an old needle, 한글 before it'; seq -f 'line %g' 201 400; "
              "echo 'the newer needle'; seq -f 'line %g' 401 600; exec cat")
    app = subprocess.Popen([str(ROOT / "app" / "puritty"), "--config", str(WORK / "config.toml"), "--title", "search-show",
                            "--", "sh", "-c", script], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    xd = lambda *a: subprocess.run([xdo, *a], env=env, check=True)
    n = 0

    def snap(name):
        nonlocal n
        time.sleep(0.6)
        n += 1
        rows = read_ppm(shot)
        if rows:
            save_png(WORK / f"{n:02d}-{name}.png", rows)
            print(f"{n:02d}-{name}.png")
    try:
        win = subprocess.run([xdo, "search", "--sync", "--name", "search-show"], env=env, capture_output=True, text=True,
                             timeout=20).stdout.split()[0]
        xd("windowfocus", "--sync", win)
        time.sleep(1.5)
        xd("key", "ctrl+shift+f")
        xd("type", "--delay", "40", "NEEDLE")
        snap("typed")
        xd("key", "Return")
        snap("older")
        xd("key", "ctrl+shift+c")
        time.sleep(0.4)
        print("the clipboard:", repr(subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=env,
                                                    capture_output=True, text=True, timeout=5).stdout))
        xd("key", "shift+Return")
        snap("newer")
        xd("key", "Escape")
        xd("mousemove", "715", "60", "mousedown", "1", "mousemove", "715", "150", "mousemove", "715", "200", "mouseup", "1")
        snap("bar-dragged")
    finally:
        app.terminate()
        app.wait()
        xvfb.terminate()
        xvfb.wait()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""The reload gate (docs/settings.md ST3, ST4): settings changed under a
running puritty are what a fresh start with them gives.

Each case starts puritty with one config.toml and a program that writes a
fixed screen and waits, and rewrites the file under it: in place, as an
editor saves, or by a rename over it, as the settings window will. Once
the window has read it again, its picture (PURITTY_SHOT, the window's own,
`Window.shot`) is held to the picture of a fresh puritty started with the
new file. A change of font keeps the running window's size in pixels,
where a fresh one opens at its size in cells, so the two are held to each
other over the part both cover; the cases leave room enough that neither
scrolls nor wraps.

Some cases hold something else: the window's title, on Linux only; a file that does not
decode, which changes nothing and is said on standard error; a file
removed, which gives the defaults.

On Linux it runs app/puritty on Xvfb, with the pixel gate's fonts
(harness/pixels.py). With `--windows HOST` it runs app/puritty.exe
(app/build-windows.sh) there instead: the program, the cases and
harness/reload/run.ps1 are copied to `geng-probe/reload` in the home
directory over ssh, every case is run in one call, and the pictures come
back. The ssh session's own window station serves, as the pixel gate's
does. Windows' fonts are its own: the default is Cascadia Mono
(`Platform.font`, WS21), the other family Consolas.

usage (from puritty's devbox, after app/build.sh or app/build-windows.sh):
    harness/reload.py                     every case
    harness/reload.py -f font             cases whose name contains "font"
    harness/reload.py --windows beelink1  on Windows
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import pixels  # noqa: E402  (its fonts)

APP = ROOT / "app" / "puritty"
APP_EXE = ROOT / "app" / "puritty.exe"
WORK = ROOT / ".harness-work" / "reload"
RUNNER = ROOT / "harness" / "reload" / "run.ps1"
REMOTE = "geng-probe/reload"
DISPLAY = ":83"
TITLE = "reload-gate"

# A screen with what the settings change: the default colours, the named
# colours (SGR 31-36, 91-96), bold (bright under bold_is_bright), a box,
# and Han, whose forms the fallback language chooses.
SCREEN = ("plain text 0123456789\r\n"
          "\x1b[31mred\x1b[32m green\x1b[33m yellow\x1b[34m blue\x1b[35m magenta\x1b[36m cyan\x1b[0m\r\n"
          "\x1b[91mbright red\x1b[96m bright cyan\x1b[0m\r\n"
          "\x1b[1mbold\x1b[0m \x1b[1;34mbold blue\x1b[0m\r\n"
          "┌─┐ 直骨海\r\n")

# room enough that a larger font, in the window's pixels, neither scrolls
# the screen nor wraps its lines, as a zoom would
BASE = f"""[window]
columns = 60
rows = 20
title = "{TITLE}"

[cursor]
blink_ms = 0
"""


def cases(windows):
    other = "Consolas" if windows else "Fira Code"
    return [
        ("colours", BASE, BASE + '\n[colours]\nforeground = "#ffffff"\nbackground = "#003040"\n', "in place", "pixels"),
        ("colours-renamed", BASE, BASE + '\n[colours]\nforeground = "#202020"\nbackground = "#f0f0e0"\n', "rename", "pixels"),
        ("palette-set", BASE, BASE + '\n[colours]\npalette = ["#000000", "#ff0000", "#00ff00", "#ffff00", "#0000ff"]\n',
         "in place", "pixels"),
        ("palette-shortened",
         BASE + '\n[colours]\npalette = ["#000000", "#ff0000", "#00ff00", "#ffff00", "#0000ff", "#ff00ff"]\n',
         BASE + '\n[colours]\npalette = ["#000000", "#ff0000"]\n', "rename", "pixels"),
        ("bold-is-bright", BASE, BASE + "\n[colours]\nbold_is_bright = true\n", "in place", "pixels"),
        ("font-size", BASE, BASE + "\n[font]\nsize = 15\n", "rename", "pixels"),
        ("font-family", BASE, BASE + f'\n[font]\nfamily = "{other}"\n', "rename", "pixels"),
        ("font-language", BASE + '\n[font]\nlanguage = "ko"\n', BASE + '\n[font]\nlanguage = "ja"\n', "rename", "pixels"),
        # a family the system lacks is answered with the closest it has, or
        # on Windows the stand-in (Cascadia Mono, the default), at a start
        # as at a reload: what a fresh start gives, changed or not
        ("font-missing", BASE, BASE + '\n[font]\nfamily = "No Such Font Anywhere"\n', "rename", "pixels-or-same"),
        # a file that is not TOML changes nothing; a value a setting does not
        # take is its default, as a fresh start with the key left out gives
        # (a fresh start with the bad key shows the notice, docs/settings.md ST17)
        ("not-toml", BASE + '\n[colours]\nbackground = "#003040"\n', BASE + "\n[colours]\nbackground = = 1\n",
         "in place", "kept"),
        ("bad-value", BASE + '\n[colours]\nbackground = "#003040"\nforeground = "#ffffff"\n',
         BASE + '\n[colours]\nbackground = 12\nforeground = "#ffffff"\n', "in place", "pixels",
         BASE + '\n[colours]\nforeground = "#ffffff"\n'),
        # what is wrong is on the title until a read is clean
        ("title-trouble", BASE, BASE + "\n[font]\nsise = 12\n", "rename", "title-trouble"),
        ("title-clean", BASE + "\n[font]\nsise = 12\n", BASE, "rename", "title-clean"),
        ("removed", BASE.replace("blink_ms = 0", 'blink_ms = 0\n\n[colours]\nbackground = "#003040"'), None,
         "remove", "defaults"),
    ] + ([] if windows else [
        # the settings' title is the window's while the program has set
        # none, and on Windows the pseudo console sets one for every
        # program, its path, as it starts (docs/settings.md ST15)
        ("title", BASE, BASE.replace(TITLE, TITLE + "-again"), "rename", "title"),
    ])


def read_ppm(path):
    """A P6 picture as rows of RGB bytes, or None."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    parts, at = [], 0
    while len(parts) < 4:
        while data[at:at + 1].isspace():
            at += 1
        if data[at:at + 1] == b"#":
            at = data.index(b"\n", at)
            continue
        end = at
        while not data[end:end + 1].isspace():
            end += 1
        parts.append(data[at:end])
        at = end
    at += 1
    w, h = int(parts[1]), int(parts[2])
    if len(data) < at + w * h * 3:
        return None
    return [data[at + y * w * 3:at + (y + 1) * w * 3] for y in range(h)]


def save_png(path, rows):
    from PIL import Image
    Image.frombytes("RGB", (len(rows[0]) // 3, len(rows)), b"".join(rows)).save(path)


def common(a, b):
    """Two pictures cut to the part both cover, from their top left."""
    h = min(len(a), len(b))
    w = min(len(a[0]), len(b[0])) if h else 0
    return [r[:w] for r in a[:h]], [r[:w] for r in b[:h]]


def judge(held, first, got, fresh, title, said, home):
    """Why the case fails, or None."""
    if got is None:
        return "no picture after the change"
    if held == "title":
        want = TITLE + "-again"
        return None if title == want else f"title {title!r}, want {want!r}"
    if held == "title-trouble":
        return None if title and " [settings: " in title and "sise" in title else f"title {title!r}, with no [settings: ...]"
    if held == "title-clean":
        return None if title is not None and "[settings:" not in title else f"title {title!r}, still with [settings: ...]"
    if held == "kept":
        if got != first:
            return "the picture changed, where the settings in force should have been kept"
        return None if "puritty:" in said else "nothing was said on standard error"
    if fresh is None:
        return "no picture from the fresh start"
    a, b = common(got, fresh)
    save_png(home / "got.png", got)
    save_png(home / "fresh.png", fresh)
    if a != b:
        diff = sum(1 for ra, rb in zip(a, b) for i in range(0, len(ra), 3) if ra[i:i + 3] != rb[i:i + 3])
        return f"{diff} pixels differ from a fresh start ({len(b[0]) // 3}x{len(b)} compared)"
    if held == "pixels" and first is not None and common(first, got)[0] == a:
        return "the picture did not change"
    return None


# LINUX

def start(env, home, name):
    log = open(home / f"{name}-stderr.txt", "w")
    screen = home / "screen.txt"
    screen.write_bytes(SCREEN.encode())
    p = subprocess.Popen([str(APP), "--", "sh", "-c", f"cat '{screen}'; exec sleep 600"], env=env,
                         stdout=subprocess.DEVNULL, stderr=log)
    time.sleep(1.5)
    return p


def stop(p):
    p.terminate()
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()


def write(path, text, how):
    if how == "remove":
        path.unlink()
    elif how == "rename":
        new = path.with_name(path.name + ".new")
        new.write_text(text)
        os.replace(new, path)
    else:
        with open(path, "r+") as f:
            f.truncate(0)
            f.write(text)


def title_of(env):
    out = subprocess.run(["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True).stdout
    m = re.search(r'"([^"]*)": \("puritty"', out)
    return m.group(1) if m else None


def run_linux(env0, name, before, after, how, held, fresh_text=None):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    config = home / "config" / "puritty"
    config.mkdir(parents=True)
    path = config / "config.toml"
    path.write_text(before)
    shot = home / "shot.ppm"
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), PURITTY_SHOT=str(shot))
    p = start(env, home, "running")
    first = read_ppm(shot)
    write(path, after, how)
    time.sleep(1.0)
    got = read_ppm(shot)
    title = title_of(env)
    stop(p)
    said = (home / "running-stderr.txt").read_text()
    fresh = None
    if held in ("pixels", "pixels-or-same", "defaults"):
        if fresh_text is not None:
            path.write_text(fresh_text)
        elif after is not None:
            path.write_text(after)
        shot.unlink(missing_ok=True)
        p = start(env, home, "fresh")
        fresh = read_ppm(shot)
        stop(p)
    return judge(held, first, got, fresh, title, said, home)


# WINDOWS

def run_windows(host, chosen):
    """Every case on `host` in one call; each case's reason, or None."""
    stage = WORK / "windows"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    (stage / "screen.txt").write_bytes(SCREEN.encode())
    lines = []
    for name, before, after, how, held, *rest in chosen:
        (stage / f"{name}.before.toml").write_text(before, newline="\n")
        if after is not None:
            (stage / f"{name}.after.toml").write_text(after, newline="\n")
        if rest:
            (stage / f"{name}.fresh.toml").write_text(rest[0], newline="\n")
        fresh = "fresh" if held in ("pixels", "pixels-or-same", "defaults") else "none"
        lines.append("\t".join([name, how, fresh]))
    (stage / "cases.tsv").write_text("\n".join(lines) + "\n")
    ssh = ["ssh", "-o", "BatchMode=yes", host]
    subprocess.run(ssh + [f"powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path {REMOTE} | Out-Null;"
                          f" Remove-Item -Recurse -Force {REMOTE}\\* -ErrorAction SilentlyContinue\""], check=True)
    subprocess.run(["scp", "-q", str(APP_EXE), str(RUNNER), *map(str, stage.glob("*")), f"{host}:{REMOTE}/"], check=True)
    p = subprocess.run(ssh + [f"powershell -NoProfile -ExecutionPolicy Bypass -File {REMOTE}\\run.ps1"],
                       capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        raise RuntimeError((p.stdout + p.stderr).strip())
    back = stage / "back"
    back.mkdir()
    subprocess.run(["scp", "-q", f"{host}:{REMOTE}/out/*", str(back)], check=True)
    out = {}
    for name, before, after, how, held, *rest in chosen:
        home = WORK / name
        shutil.rmtree(home, ignore_errors=True)
        home.mkdir(parents=True)

        def text(suffix):
            f = back / f"{name}.{suffix}"
            return f.read_text(encoding="utf-8", errors="replace").strip() if f.exists() else ""
        out[name] = judge(held, read_ppm(back / f"{name}.first.ppm"), read_ppm(back / f"{name}.got.ppm"),
                          read_ppm(back / f"{name}.fresh.ppm"), text("title.txt"), text("stderr.txt"), home)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-f", dest="filter", default="")
    ap.add_argument("--windows", metavar="HOST", default="")
    a = ap.parse_args()
    chosen = [c for c in cases(bool(a.windows)) if a.filter in c[0]]
    WORK.mkdir(parents=True, exist_ok=True)
    if a.windows:
        if not APP_EXE.exists():
            sys.exit("reload.py: build app/puritty.exe first (app/build-windows.sh)")
        results = run_windows(a.windows, chosen)
    else:
        if not APP.exists():
            sys.exit("reload.py: build app/puritty first (app/build.sh)")
        conf = pixels.write_fonts_conf()
        env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96",
                   LANG="C.UTF-8")
        env.pop("LC_ALL", None)
        xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        results = {}
        try:
            for c in chosen:
                results[c[0]] = run_linux(env, *c)
        finally:
            xvfb.terminate()
            xvfb.wait()
    fails = 0
    for name, *_ in chosen:
        why = results.get(name, "not run")
        if why:
            fails += 1
            print(f"FAIL {name}: {why}")
        else:
            print(f"ok   {name}")
    print(f"{len(chosen) - fails} of {len(chosen)} cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

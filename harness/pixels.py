#!/usr/bin/env python3
"""The pixel gate (docs/renderer.md §R13, V38).

Every case of corpus/pixels/cases/ is fed to the core and drawn by
packages/x11 on an Xvfb of its own, by harness/pixels/core-pixels, and the
window's picture is held to its pin, corpus/pixels/NAME.png, pixel for
pixel.

What is drawn depends on the fonts, so the gate sees only its own: the
packages FONTS names, built from the nixpkgs commit visiterm's devbox pins
(Q13: the tests pin fonts; visiterm ships none), and a fontconfig file
that names their directories and nothing else, written to
.harness-work/pixels/fonts.conf. FreeType, HarfBuzz, fontconfig and Xvfb
are devbox's, from the same commit, so a picture changes only when the
renderer does.

A case is the replay corpus's `case.txt` format (harness/replay.py), with
two differences. Its first line may say more than the size:

    size 40x4 font="Fira Code" points=11 lang=ja unfocused

the primary font as fontconfig names it (DejaVu Sans Mono), its points
(11), the language fallback fonts are asked for (none), and whether the
window has the focus. And `\\F` in the body draws a frame there, so that
the next frame draws only what changed, as the app's frames do; a last
frame follows the last byte. A resize (`\\R`) is not taken.

usage (from visiterm's devbox, after harness/pixels/build.sh):
    harness/pixels.py              every case
    harness/pixels.py -f thai      cases whose name contains "thai"
    harness/pixels.py --update     write the pins; look at each before
                                   committing it
    harness/pixels.py --faces      say which font files each case drew with

A case that differs leaves NAME.got.png and NAME.diff.png (the differing
pixels red, the rest dimmed) in .harness-work/pixels/.
"""

import argparse
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import ESCAPES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "corpus" / "pixels" / "cases"
PINS = ROOT / "corpus" / "pixels"
WORK = ROOT / ".harness-work" / "pixels"
DRIVER = ROOT / "harness" / "pixels" / "core-pixels"

NIXPKGS = "github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600"
# The fonts the gate sees. noto-fonts is every Noto family, some 1.5 GB;
# the gate takes the two scripts C§9's corpus needs of it.
FONTS = [
    f"{NIXPKGS}#dejavu_fonts",
    f"{NIXPKGS}#fira-code",
    f"{NIXPKGS}#noto-fonts-cjk-sans",
    f"{NIXPKGS}#noto-fonts-color-emoji",
]
NOTO = (
    f'(builtins.getFlake "{NIXPKGS}").legacyPackages.x86_64-linux.noto-fonts.override'
    ' { variants = [ "NotoSansThai" "NotoSansDevanagari" ]; }'
)
# What a system's fontconfig makes of `monospace`, which the fallback
# query asks for: Mint's (Debian's) aliases, and its fonts-noto-cjk rules,
# which put a language's own region of Noto Sans Mono CJK first. Every
# region covers every CJK language, so fontconfig's own language matching
# cannot choose between them: without the rules, Japanese forms are drawn
# for every language (§R13).
MONOSPACE = ["DejaVu Sans Mono", "Noto Sans Mono CJK JP", "Noto Color Emoji"]
REGIONS = {"ja": "JP", "ko": "KR", "zh-cn": "SC", "zh-tw": "TC", "zh-hk": "HK"}


def font_dirs():
    out = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", *FONTS],
                         capture_output=True, text=True, check=True).stdout.split()
    out += subprocess.run(["nix", "build", "--no-link", "--print-out-paths", "--impure", "--expr", NOTO],
                          capture_output=True, text=True, check=True).stdout.split()
    return [str(Path(p) / "share" / "fonts") for p in out]


def write_fonts_conf():
    WORK.mkdir(parents=True, exist_ok=True)
    dirs = "".join(f"  <dir>{d}</dir>\n" for d in font_dirs())
    prefer = "".join(f"<family>{f}</family>" for f in MONOSPACE)
    regions = "".join(
        f'  <match target="pattern"><test name="lang"><string>{lang}</string></test>'
        f'<test name="family"><string>monospace</string></test><edit name="family" mode="prepend" binding="strong">'
        f"<string>Noto Sans Mono CJK {region}</string></edit></match>\n"
        for lang, region in REGIONS.items())
    conf = WORK / "fonts.conf"
    conf.write_text(
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n<fontconfig>\n'
        f"{dirs}  <cachedir>{WORK / 'fc-cache'}</cachedir>\n"
        f"  <alias><family>monospace</family><prefer>{prefer}</prefer></alias>\n{regions}</fontconfig>\n")
    return conf


# CASES

def parse_case(text):
    """The case's settings, its bytes, and where frames are drawn."""
    head, _, body = text.partition("\n")
    words = shlex.split(head)
    if len(words) < 2 or words[0] != "size":
        raise ValueError("first line must be `size COLSxROWS ...`")
    cols, rows = (int(n) for n in words[1].split("x"))
    s = {"cols": cols, "rows": rows, "font": "DejaVu Sans Mono", "points": 11, "lang": "", "focus": "focused"}
    for w in words[2:]:
        if w == "unfocused":
            s["focus"] = w
        elif "=" in w and w.split("=", 1)[0] in ("font", "points", "lang"):
            k, v = w.split("=", 1)
            s[k] = int(v) if k == "points" else v
        else:
            raise ValueError(f"unknown setting {w!r}")
    out, breaks = bytearray(), []
    raw = body.replace("\n", "").encode("utf-8")
    i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        k = raw[i + 1:i + 2].decode()
        if k == "x":
            out.append(int(raw[i + 2:i + 4], 16))
            i += 4
        elif k in ESCAPES:
            out += ESCAPES[k]
            i += 2
        elif k == "F":
            breaks.append(len(out))
            i += 2
        else:
            raise ValueError(f"unknown escape \\{k} at byte {i}")
    return s, bytes(out), breaks


# PICTURES

def read_ppm(data):
    parts = data.split(maxsplit=4)
    if parts[0] != b"P6" or parts[3] != b"255":
        raise ValueError("not an 8-bit PPM")
    w, h = int(parts[1]), int(parts[2])
    return w, h, parts[4][:w * h * 3]


def write_png(path, w, h, rgb):
    raw = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def read_png(path):
    """An 8-bit RGB PNG, any filters, not interlaced: width, height, pixels."""
    data = path.read_bytes()
    i, idat = 8, b""
    while i < len(data):
        n, = struct.unpack(">I", data[i:i + 4])
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        if kind == b"IHDR":
            w, h, depth, colour, _, _, lace = struct.unpack(">IIBBBBB", body)
            if (depth, colour, lace) != (8, 2, 0):
                raise ValueError(f"{path}: not 8-bit RGB")
        elif kind == b"IDAT":
            idat += body
        i += 12 + n
    raw, stride, out = zlib.decompress(idat), w * 3, bytearray()
    prev = bytearray(stride)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - 3] if x >= 3 else 0
            b = prev[x]
            c = prev[x - 3] if x >= 3 else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line
    return w, h, bytes(out)


def differences(w, h, got, want, cols, rows):
    """How many pixels differ, the cells they fall in, and a picture of them."""
    n, cells, pic = 0, set(), bytearray(len(got))
    cw, ch = w // cols, h // rows
    for i in range(0, len(got), 3):
        if got[i:i + 3] != want[i:i + 3]:
            n += 1
            x, y = (i // 3) % w, (i // 3) // w
            cells.add((min(x // cw, cols - 1), min(y // ch, rows - 1)))
            pic[i:i + 3] = b"\xff\x00\x00"
        else:
            v = sum(got[i:i + 3]) // 9
            pic[i:i + 3] = bytes((v, v, v))
    return n, sorted(cells, key=lambda c: (c[1], c[0])), bytes(pic)


# RUNNING

def start_xvfb():
    r, w = os.pipe()
    proc = subprocess.Popen(["Xvfb", "-displayfd", str(w), "-screen", "0", "1920x1080x24", "-nolisten", "tcp",
                             "-dpi", "96", "-extension", "MIT-SHM"],
                            pass_fds=(w,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(w)
    with os.fdopen(r) as f:
        number = f.readline().strip()
    if not number:
        proc.kill()
        raise RuntimeError("Xvfb did not start")
    return proc, ":" + number


def draw(case, display, conf, out, faces):
    s, data, breaks = parse_case(case.read_text())
    with tempfile.NamedTemporaryFile(suffix=".bin") as f:
        f.write(data)
        f.flush()
        env = dict(os.environ, DISPLAY=display, FONTCONFIG_FILE=str(conf))
        if faces:
            env["X11_STATS"] = "1"
        cmd = ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=2G",
               str(DRIVER), str(s["cols"]), str(s["rows"]), f.name, str(out), s["font"], str(s["points"]), s["lang"],
               ",".join(map(str, breaks)), s["focus"]]
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError((p.stdout + p.stderr).strip() or f"exit {p.returncode}")
    return s, [line.split(": ", 1)[1] for line in p.stderr.splitlines() if line.startswith("face ")]


def main():
    ap = argparse.ArgumentParser(description="The pixel gate.")
    ap.add_argument("-f", "--filter", default="")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--faces", action="store_true")
    a = ap.parse_args()
    if not DRIVER.exists():
        sys.exit("pixels.py: build harness/pixels/core-pixels first (harness/pixels/build.sh)")
    if shutil.which("Xvfb") is None:
        sys.exit("pixels.py: no Xvfb; run from visiterm's devbox")
    conf = write_fonts_conf()
    cases = sorted(c for c in CASES.glob("*.txt") if a.filter in c.stem)
    xvfb, display = start_xvfb()
    passed, failed = 0, []
    try:
        for case in cases:
            name = case.stem
            got_ppm = WORK / f"{name}.ppm"
            try:
                s, used = draw(case, display, conf, got_ppm, a.faces)
            except Exception as e:  # noqa: BLE001
                failed.append(name)
                print(f"FAIL {name}: {e}")
                continue
            if a.faces:
                print(f"{name}: {'; '.join(Path(u).name for u in used)}")
            w, h, got = read_ppm(got_ppm.read_bytes())
            got_ppm.unlink()
            pin = PINS / f"{name}.png"
            if a.update:
                write_png(pin, w, h, got)
                passed += 1
                continue
            if not pin.exists():
                failed.append(name)
                write_png(WORK / f"{name}.got.png", w, h, got)
                print(f"FAIL {name}: no pin (its picture is in {WORK / (name + '.got.png')})")
                continue
            pw, ph, want = read_png(pin)
            if (pw, ph) != (w, h):
                failed.append(name)
                write_png(WORK / f"{name}.got.png", w, h, got)
                print(f"FAIL {name}: {w}x{h} pixels, the pin {pw}x{ph}")
                continue
            if got == want:
                passed += 1
                continue
            n, cells, pic = differences(w, h, got, want, s["cols"], s["rows"])
            write_png(WORK / f"{name}.got.png", w, h, got)
            write_png(WORK / f"{name}.diff.png", w, h, pic)
            failed.append(name)
            shown = ", ".join(f"{x},{y}" for x, y in cells[:8]) + (" ..." if len(cells) > 8 else "")
            print(f"FAIL {name}: {n} pixels differ, in {len(cells)} cells (col,row: {shown})")
    finally:
        xvfb.kill()
        xvfb.wait()
    print(f"{'wrote' if a.update else 'passed'} {passed} of {len(cases)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

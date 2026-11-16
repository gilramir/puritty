"""Draws docs/user/symbol-fonts.md's pictures: claude-code.case.txt in
Fira Code with only the named fonts beside it, so each picture shows what
that fallback font draws. FONTS is a folder of the downloaded files (the
guide says where each comes from):

    python3 docs/images/symbol-fonts/render.py FONTS

Each picture's fonts, then which faces puritty drew with, are printed."""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pixels", HERE.parent.parent.parent / "harness" / "pixels.py")
px = importlib.util.module_from_spec(spec)
spec.loader.exec_module(px)

FONTS = Path(sys.argv[1])
FIRA = "/usr/share/fonts/truetype/firacode/FiraCode-Regular.ttf"
RHEL8 = ["rhel8/DejaVuSansMono.ttf", "rhel8/DejaVuSans.ttf", "rhel8/NotoSansSymbols-Regular.ttf"]
SETUPS = {
    "fira-alone": [],
    "rhel8": RHEL8,
    "rhel8-symbols2": RHEL8 + ["symbols2/NotoSansSymbols2-Regular.ttf"],
    "symbols2": ["symbols2/NotoSansSymbols2-Regular.ttf"],
    "juliamono": ["juliamono/JuliaMono-Regular.ttf"],
    "symbola": ["symbola/x/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf"],
    "unifont": ["unifont/x/usr/share/fonts/opentype/unifont/unifont.otf"],
}

xvfb, display = px.start_xvfb()
try:
    for name, files in SETUPS.items():
        work = px.WORK / "symbol-fonts" / name
        fonts = work / "fonts"
        fonts.mkdir(parents=True, exist_ok=True)
        for old in fonts.iterdir():
            old.unlink()
        for f in [FIRA] + [str(FONTS / f) for f in files]:
            (fonts / Path(f).name).symlink_to(f)
        conf = work / "fonts.conf"
        conf.write_text(
            '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n<fontconfig>\n'
            f"  <dir>{fonts}</dir>\n  <cachedir>{work / 'fc-cache'}</cachedir>\n"
            "  <alias><family>monospace</family><prefer><family>Fira Code</family></prefer></alias>\n"
            "</fontconfig>\n")
        ppm = work / "shot.ppm"
        s, used = px.draw(HERE / "claude-code.case.txt", display, conf, ppm, True)
        w, h, pic = px.read_ppm(ppm.read_bytes())
        px.write_png(HERE / f"{name}.png", w, h, pic)
        print(f"{name}: {w}x{h}; drew with", ", ".join(sorted(set(Path(u).name for u in used))))
finally:
    xvfb.kill()

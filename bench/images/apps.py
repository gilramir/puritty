#!/usr/bin/env python3
"""Pictures from programs that ask the terminal through tmux's passthrough
(docs/images.md IM33, IM34): snacks.nvim's images in neovim, and
ratatui-image's demo, in a shell, in plain tmux and in tmux -CC, as
bench/images/programs.py runs its programs.

snacks.nvim shows a picture file opened in neovim, and ratatui-image's
demo shows one in five panels; each is counted by the test picture's blue.
The demo says the way it chose (`Protocol: Sixel`, `Kitty`, `Iterm2`, or
`Halfblocks`, its text fallback), read from the pane with tmux's
capture-pane. Both draw Kitty's pictures with Unicode placeholders (IM34,
IM35): snacks.nvim knows terminals by name and puritty is not one, so it is
told it runs in WezTerm (direct placements) and then in Ghostty
(placeholders); the demo shows its own choice, Kitty with placeholders,
then Sixel and iTerm2 forced by `ratatui-demo.patch` (DEMO_PROTOCOL, and
DEMO_IMAGE for the picture shown).

Both are fetched and built in .harness-work/images-tools: snacks.nvim's
source (git), and ratatui-image's demo built by cargo, without chafa:

    git clone --depth 1 https://github.com/folke/snacks.nvim
    git clone --depth 1 https://github.com/benjajaja/ratatui-image
    git -C ratatui-image apply ../../../bench/images/ratatui-demo.patch
    cargo build --release --example demo --no-default-features --features crossterm,image-defaults

    devbox run -- python3 bench/images/apps.py [--mode shell|plain|cc|all]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from programs import BLUE, ROOT, Run, count, pictures, tool  # noqa: E402
from show import check, report, that  # noqa: E402

TOOLS = ROOT / ".harness-work" / "images-tools"
SNACKS = TOOLS / "snacks.nvim"
DEMO = TOOLS / "ratatui-image"


def snacks_init(folder):
    init = folder / "init.lua"
    init.write_text(f"""vim.opt.rtp:prepend("{SNACKS}")
vim.opt.swapfile = false
require("snacks").setup({{ image = {{ enabled = true }} }})
""")
    return init


def protocol_said(r):
    """The protocol the demo's help says it chose, read from the pane."""
    screen = r.cli("capture-pane", "-p", "-t", "img")
    said = [l for l in screen.splitlines() if "Protocol:" in l]
    return said[0].split("Protocol:")[1].split()[0].strip("│ ") if said else "none said"


def nvim_quit(r):
    """`:qa!`: snacks.nvim's picture buffer is marked as changed."""
    r.keys("Escape", wait=0.3)
    if r.bare:
        r.keys("colon", "q", "a", "exclam", "Return", wait=2)
    else:
        r.cli("send-keys", "-t", "img", ":qa!", "Enter")
        time.sleep(2)


def apps(a, mode, path):
    r = Run(a, mode, path)
    pics = pictures(r.work / "pics")
    init = snacks_init(r.work)
    blue = pics / "blue.png"
    try:
        r.start()
        r.run("clear", wait=0.6)
        # snacks.nvim knows terminals by name (XTVERSION's): puritty is not
        # one, so it is named WezTerm's, whose pictures are placed directly;
        # as kitty's or Ghostty's they would be Unicode placeholders (IM34)
        r.run(f"SNACKS_WEZTERM=1 nvim -u {init} {blue}", wait=6)
        check(f"{mode}: snacks.nvim shows blue.png, placed directly",
              count(r.snap("snacks-blue"), BLUE), that("more than 1000 pixels", lambda n: n > 1000))
        nvim_quit(r)
        r.run("clear", wait=1.0)
        check(f"{mode}: neovim's picture gone after it quits", count(r.snap("snacks-quit"), BLUE), 0)

        r.run(f"SNACKS_GHOSTTY=1 nvim -u {init} {blue}", wait=6)
        check(f"{mode}: snacks.nvim shows blue.png by Kitty's placeholders, as in Ghostty (IM35)",
              count(r.snap("snacks-placeholders"), BLUE), that("more than 1000 pixels", lambda n: n > 1000))
        nvim_quit(r)
        r.run("clear", wait=1.0)

        # ratatui-image's demo, its own choice, then Sixel and iTerm2 forced
        # (bench/images/ratatui-demo.patch)
        for forced in ("", "sixel", "iterm2"):
            name = forced or "chosen"
            r.run(f"cd {DEMO} && DEMO_IMAGE={blue} DEMO_PROTOCOL={forced} target/release/examples/demo", wait=6)
            n = count(r.snap(f"ratatui-{name}"), BLUE)
            if not r.bare:
                protocol = protocol_said(r)
                if not forced:
                    check(f"{mode}: ratatui-image's demo chose a picture protocol", protocol,
                          that("Sixel, Kitty or Iterm2, not Halfblocks", lambda p: p in ("Sixel", "Kitty", "Iterm2")))
            check(f"{mode}: ratatui-image's demo shows blue.png by {forced or 'its choice, Kitty with placeholders (IM35)'}", n,
                  that("more than 1000 pixels", lambda n: n > 1000))
            r.keys("q", wait=2)
            r.run("clear", wait=1.0)
            check(f"{mode}: the demo's pictures gone after it quits ({name})", count(r.snap(f"ratatui-{name}-quit"), BLUE), 0)
        check(f"{mode}: puritty still running at the end", r.alive(), True)
    finally:
        r.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puritty", default=str(ROOT / "app" / "puritty"))
    ap.add_argument("--tmux", default="tmux")
    ap.add_argument("--mode", default="all", choices=["shell", "plain", "cc", "all"])
    a = ap.parse_args()
    if not (SNACKS.exists() and (DEMO / "target/release/examples/demo").exists()):
        sys.exit("apps.py: fetch and build snacks.nvim and ratatui-image's demo first (see the top of this file)")
    path = ":".join([tool("neovim"), tool("imagemagick")])
    for mode in (["shell", "plain", "cc"] if a.mode == "all" else [a.mode]):
        apps(a, mode, path)
    report()


if __name__ == "__main__":
    main()

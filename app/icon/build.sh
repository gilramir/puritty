#!/bin/sh
# Renders the icon's SVGs to PNGs, packs puritty.ico (the exe's) and writes
# packages/x11's puritty_icon.h (the X window's). The PNGs, the .ico and
# the header are committed, so a build needs none of this; run it after
# changing an SVG. Chromium comes from geng-lang's browser harness.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
R=/home/gram/prj/geng-lang
mkdir -p "$here/png"
(cd "$R/harness/browser-runner" && PATH="$R/.devbox/nix/profile/default/bin:$PATH" node "$here/render.cjs" "$here")
python3 "$here/pack-ico.py"
python3 "$here/pack-x11.py"

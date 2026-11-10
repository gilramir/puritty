#!/bin/sh
# Renders the icon's SVGs to PNGs and packs puritty.ico. The PNGs and the
# .ico are committed, so a build of the exe needs none of this; run it after
# changing an SVG. Chromium comes from geng-lang's browser harness.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
R=/home/gram/prj/geng-lang
mkdir -p "$here/png"
(cd "$R/harness/browser-runner" && PATH="$R/.devbox/nix/profile/default/bin:$PATH" node "$here/render.cjs" "$here")
python3 "$here/pack-ico.py"

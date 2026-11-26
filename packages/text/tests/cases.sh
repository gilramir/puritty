#!/bin/sh
# The text package's C tested (cases.c: the code review's X14, X15, X22, X24, X26),
# built with AddressSanitizer against the pinned nixpkgs' FreeType and
# HarfBuzz, run on DejaVu Sans Mono and Terminus's 16 px .otb. From
# puritty's devbox.
set -e
cd "$(dirname "$0")"
ROOT=$(cd ../../.. && pwd)
NIXPKGS=$(python3 -c "import sys; sys.path.insert(0, '$ROOT/harness'); import pixels; print(pixels.NIXPKGS)")
TERMINUS=$(nix build --no-link --print-out-paths "$NIXPKGS#terminus_font")
TTF=$(fc-match -f '%{file}' "DejaVu Sans Mono")
OUT=${TMPDIR:-/tmp}/textcases.$$
/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -I../src/Ext/include \
  $(pkg-config --cflags freetype2 harfbuzz) cases.c -o "$OUT" $(pkg-config --libs freetype2 harfbuzz) -lm
trap 'rm -f "$OUT"' EXIT
SANS=$(fc-match -f '%{file}' "DejaVu Sans")
"$OUT" "$TTF" "$TERMINUS/share/fonts/terminus/ter-u16n.otb" "$SANS"

#!/bin/sh
# Builds the font survey's bench (docs/phase2-window.md §13) against
# devbox's HarfBuzz, FreeType and fontconfig. Run from anywhere.
set -e
here=$(cd "$(dirname "$0")" && pwd)
devbox run -- sh -c "cc -O2 -Wall -o '$here/bench' '$here/bench.c' \$(pkg-config --cflags --libs harfbuzz freetype2 fontconfig)"

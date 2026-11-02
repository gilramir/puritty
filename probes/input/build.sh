#!/bin/sh
# Builds the input survey's key-to-pixel tool (docs/phase2-window.md §14)
# against devbox's libxcb. Run from anywhere.
set -e
here=$(cd "$(dirname "$0")" && pwd)
devbox run -- sh -c "cc -O2 -Wall -o '$here/typo' '$here/typo.c' \$(pkg-config --cflags --libs xcb xcb-xtest xcb-keysyms)"

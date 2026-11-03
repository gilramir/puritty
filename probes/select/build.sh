#!/bin/sh
# Builds sel, the selection probe (docs/phase3-select.md). Run from visiterm's devbox.
set -e
cd "$(dirname "$0")"
/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang -O2 -Wall -Wextra -o sel sel.c $(pkg-config --cflags --libs xcb)

#!/bin/sh
# Builds xim, the XIM probe (docs/phase3-input.md). Run from visiterm's
# devbox, which has xcb-imdkit and xkbcommon; xcb-imdkit's .pc names
# xcb-util, which the devbox lacks, so it is built from the same pin.
set -e
cd "$(dirname "$0")"
U=$(nix build --no-link --print-out-paths github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600#libxcb-util.dev)
export PKG_CONFIG_PATH=$U/lib/pkgconfig:$PKG_CONFIG_PATH PKG_CONFIG_PATH_FOR_TARGET=$U/lib/pkgconfig:$PKG_CONFIG_PATH_FOR_TARGET
/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang -O2 -Wall -Wextra -o xim xim.c \
  $(pkg-config --cflags --libs xcb xcb-xkb xkbcommon xkbcommon-x11 xcb-imdkit)

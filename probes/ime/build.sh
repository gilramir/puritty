#!/bin/sh
# Builds xim, the XIM probe (docs/phase3-input.md), against xcb-imdkit:
# the pinned one, or with PATCHED=1 visiterm's patched build
# (packages/x11/build-imdkit.sh), as xim-patched. Run from visiterm's devbox.
set -e
cd "$(dirname "$0")"
CC=/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang
if [ -n "$PATCHED" ]; then
  P=$(realpath ../../vendor/xcb-imdkit/visiterm/lib/pkgconfig)
  PKG_CONFIG_PATH=$P:$PKG_CONFIG_PATH PKG_CONFIG_PATH_FOR_TARGET=$P:$PKG_CONFIG_PATH_FOR_TARGET \
    $CC -O2 -Wall -Wextra -o xim-patched xim.c $(PKG_CONFIG_PATH=$P:$PKG_CONFIG_PATH PKG_CONFIG_PATH_FOR_TARGET=$P:$PKG_CONFIG_PATH_FOR_TARGET pkg-config --cflags --libs xcb xcb-xkb xkbcommon xkbcommon-x11 visiterm-xcb-imdkit)
else
  $CC -O2 -Wall -Wextra -o xim xim.c $(pkg-config --cflags --libs xcb xcb-xkb xkbcommon xkbcommon-x11 xcb-imdkit)
fi

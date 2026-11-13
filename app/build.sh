#!/bin/sh
# Builds puritty for Linux (docs/renderer.md §R10; app/linux is its
# manifest over app/src, docs/windows.md V55) with geng-lang's compiler and
# devbox's clang, with the passes harness/bench/build.sh builds the core
# with. Run from puritty's devbox, which has the C libraries
# packages/x11 links.
set -e
cd "$(dirname "$0")/linux"
R=/home/gram/prj/geng-lang
# xcb-imdkit with puritty's patches (V44), linked by its own name
../../packages/x11/build-imdkit.sh
I=$(realpath ../../vendor/xcb-imdkit/puritty/lib/pkgconfig)
# nix's libpulse-simple for the sounds, which this build's loader can load
# where the system's it cannot (docs/sounds.md SN6)
P=$(pkg-config --variable=libdir libpulse-simple 2>/dev/null || true)
P=${P:+$P/libpulse-simple.so.0}
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_PKG_CONFIG=$(command -v pkg-config) \
GENG_CFLAGS="${P:+-DPURITTY_PULSE_SIMPLE=\"$P\"} $GENG_CFLAGS" \
PKG_CONFIG_PATH=$I:$PKG_CONFIG_PATH PKG_CONFIG_PATH_FOR_TARGET=$I:$PKG_CONFIG_PATH_FOR_TARGET \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --output=../puritty "$@"

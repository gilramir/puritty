#!/bin/sh
# Builds visiterm (docs/renderer.md §R10) with geng-lang's compiler and
# devbox's clang, with the passes harness/bench/build.sh builds the core
# with. Run from visiterm's devbox, which has the C libraries
# packages/x11 links.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_PKG_CONFIG=$(command -v pkg-config) \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop \
  exec node $C/app make Main --output=visiterm "$@"

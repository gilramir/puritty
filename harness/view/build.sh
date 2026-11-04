#!/bin/sh
# Builds core-view, the display-list gate's program (docs/renderer.md §R8):
# the core and Vt.View fed a case a read at a time, each frame's display
# list printed. geng-lang's compiler and devbox's clang, with the passes
# harness/dump/build.sh builds core-dump with.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --output=core-view "$@"

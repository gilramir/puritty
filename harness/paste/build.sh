#!/bin/sh
# Builds core-paste, the paste gate's program (docs/phase3-select.md §15):
# Vt.Paste.encode for each case of a file. geng-lang's compiler and devbox's
# clang, with the passes harness/dump/build.sh builds core-dump with.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --output=core-paste "$@"

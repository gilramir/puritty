#!/bin/sh
# Builds the view probe: the core fed in 64 KB reads with a renderer's frame
# after each (docs/phase2-window.md §3), with geng-lang's compiler, devbox's
# clang and the passes harness/bench/build.sh builds core-bench with.
set -e
cd "$(dirname "$0")"
../vtp/sync.sh
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace \
  exec node $C/app make Main --output=view "$@"

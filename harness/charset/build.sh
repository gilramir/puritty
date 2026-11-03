#!/bin/sh
# Builds core-charset, the EUC-KR filter gate's program (docs/phase3-input.md
# V49): Vt.Charset on cjk-and-thai.md §10.5's cases. geng-lang's compiler and
# devbox's clang, with the passes harness/dump/build.sh builds core-dump with.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop \
  exec node $C/app make Main --output=core-charset "$@"

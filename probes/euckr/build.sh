#!/bin/sh
# Builds the EUC-KR decoder probe (docs/phase3-input.md) with geng-lang's
# compiler, devbox's clang and core-bench's passes (harness/bench/build.sh),
# against the core. gen.py writes src/EucKrIndex.geng and the inputs.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop \
  exec node $C/app make Main --output=euckr "$@"

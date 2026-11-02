#!/bin/sh
# Builds the x11 probe: a program on a pty drawn in an X window
# (docs/phase2-window.md §5), with geng-lang's compiler, devbox's clang, the
# passes harness/bench/build.sh builds core-bench with, and the X and font
# libraries from visiterm's devbox. Run it inside visiterm's devbox:
# `devbox run probes/geng/x11/app/build.sh`.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_PKG_CONFIG=$(command -v pkg-config) \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace \
  exec node $C/app make Main --output=x11 "$@"

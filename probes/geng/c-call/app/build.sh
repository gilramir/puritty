#!/bin/sh
# Builds the c-call probe with devbox's clang (geng-lang's) and libxcb from
# visiterm's devbox, which pkg-config finds through the package's [native]
# table (geng-lang D890). Run it inside visiterm's devbox: `devbox run ./build.sh`.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_PKG_CONFIG=$(command -v pkg-config) \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall \
  exec node $C/app make Main --output=probe "$@"

#!/bin/sh
# Builds store, the settings file's writes on the system (docs/settings.md
# ST18; harness/store.py), from this manifest over app/src and app/linux/src,
# with geng-lang's compiler and devbox's clang.
# Run from puritty's devbox.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Store --output=store "$@"

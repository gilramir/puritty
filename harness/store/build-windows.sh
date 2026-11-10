#!/bin/sh
# Builds store, the settings file's writes on the system (docs/settings.md
# ST18; harness/store.py), from this manifest over app/src and app/linux/src,
# with geng-lang's compiler and its Windows toolchain (scripts/windows-toolchain.sh).
# Run from puritty's devbox.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
eval "$("$R/scripts/windows-toolchain.sh")"
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS" \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Store --platform=windows --output=store.exe "$@"

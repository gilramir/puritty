#!/bin/sh
# Builds core-dump.exe, the replay corpus's core side on Windows
# (docs/windows.md WS12 step 6, WS22; harness/replay.py --windows): the
# same manifest and sources as build.sh, cross-compiled by geng-lang's
# Windows toolchain (its scripts/windows-toolchain.sh), with build.sh's
# passes. Run from puritty's devbox.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
eval "$("$R/scripts/windows-toolchain.sh")"
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS" \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --platform=windows --output=core-dump.exe "$@"

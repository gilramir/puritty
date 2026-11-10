#!/bin/sh
# Builds the ssh-crypto tests (docs/ssh-client.md SC11 step 3) with
# geng-lang's compiler and build.sh's passes: ssh-crypto-tests for Linux,
# or with --windows ssh-crypto-tests.exe, cross-compiled by geng-lang's
# Windows toolchain. Run from puritty's devbox, or anywhere for Linux.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends
if [ "$1" = "--windows" ]; then
  shift
  eval "$("$R/scripts/windows-toolchain.sh")"
  PATH=$R/.devbox/nix/profile/default/bin:$PATH \
  GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
  GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS" GENG_CORE_PASSES=$PASSES \
    exec node $C/app make Main --platform=windows --output=ssh-crypto-tests.exe "$@"
fi
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=$PASSES \
  exec node $C/app make Main --output=ssh-crypto-tests "$@"

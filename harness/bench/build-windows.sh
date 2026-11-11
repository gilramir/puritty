#!/bin/sh
# Builds core-bench for Windows, core-bench.exe (docs/windows.md WS29), with
# geng-lang's Windows toolchain and build.sh's passes, so that the core's
# throughput, plain and profile-guided, is measured on Windows itself.
# Arguments go to `geng make`: `--profile-use=PATH` builds with a profile.
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
  exec node $C/app make Main --platform=windows --output="${OUT:-core-bench.exe}" "$@"

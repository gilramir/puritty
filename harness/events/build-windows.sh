#!/bin/sh
# Builds core-events.exe, the events gate's program (docs/windows.md WS19):
# harness/events/src with packages/win32 for its window, cross-compiled by geng-lang's Windows
# toolchain (its scripts/windows-toolchain.sh) with FreeType and HarfBuzz
# from vendor/win-text (packages/win32/build-text-libs.sh). The passes are
# build.sh's. Run from puritty's devbox.
set -e
cd "$(dirname "$0")/windows"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
T=$(realpath ../../../vendor/win-text/lib/pkgconfig)
[ -d "$T" ] || ../../../packages/win32/build-text-libs.sh
eval "$("$R/scripts/windows-toolchain.sh")"
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS" GENG_PKG_CONFIG=x86_64-w64-mingw32-pkg-config \
PKG_CONFIG_PATH=$T PKG_CONFIG_PATH_x86_64_w64_mingw32=$T \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --platform=windows --output=../core-events.exe "$@"

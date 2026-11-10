#!/bin/sh
# Builds puritty for Windows, app/puritty.exe (docs/windows.md V55; app/windows
# is its manifest over app/src), cross-compiled by geng-lang's Windows
# toolchain with FreeType and HarfBuzz from vendor/win-text
# (packages/win32/build-text-libs.sh), with build.sh's passes. Run from
# puritty's devbox.
set -e
cd "$(dirname "$0")/windows"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
T=$(realpath ../../vendor/win-text/lib/pkgconfig 2>/dev/null || true)
[ -d "$T" ] || { ../../packages/win32/build-text-libs.sh; T=$(realpath ../../vendor/win-text/lib/pkgconfig); }
eval "$("$R/scripts/windows-toolchain.sh")"
# the exe's icon (icon/puritty.ico), linked in as resource 1
mkdir -p ../../.harness-work/windows
ICON=$(realpath ../../.harness-work/windows)/icon.res.o
x86_64-w64-mingw32-windres icon/puritty.rc -O coff -o "$ICON"
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS $ICON" GENG_PKG_CONFIG=x86_64-w64-mingw32-pkg-config \
PKG_CONFIG_PATH=$T PKG_CONFIG_PATH_x86_64_w64_mingw32=$T \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --platform=windows --output=../puritty.exe "$@"

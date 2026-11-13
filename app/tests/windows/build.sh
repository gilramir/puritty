#!/bin/sh
# The application's unit tests as a Windows program, tests.exe (geng-lang
# m1b-test.md §TS11): native/'s NativeTests over app/windows's sources, so
# the suites compile against the win32 Window, cross-compiled as
# app/build-windows.sh builds puritty.exe but as a console program, whose
# report a terminal shows. Run from puritty's devbox; run tests.exe on
# Windows, where its arguments are the runner's.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
T=$(realpath ../../../vendor/win-text/lib/pkgconfig 2>/dev/null || true)
[ -d "$T" ] || { ../../../packages/win32/build-text-libs.sh; T=$(realpath ../../../vendor/win-text/lib/pkgconfig); }
eval "$("$R/scripts/windows-toolchain.sh")"
rm -f tests.exe
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS" GENG_PKG_CONFIG=x86_64-w64-mingw32-pkg-config \
PKG_CONFIG_PATH=$T PKG_CONFIG_PATH_x86_64_w64_mingw32=$T \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make NativeTests --platform=windows --output=tests.exe "$@"

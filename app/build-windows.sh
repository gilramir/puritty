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
# the exe's icon (app/icon/puritty.ico), linked in as resource 1
mkdir -p ../../.harness-work/windows
ICON=$(realpath ../../.harness-work/windows)/icon.res.o
# the icon and a version resource (the code review's W17: with none,
# Explorer's Details, SmartScreen and a crash report named no product or
# version), the version Main.geng's purittyVersion, as prerelease.sh reads it
VERSION=$(sed -n 's/^    "\([0-9][0-9.]*\)"$/\1/p' ../src/Main.geng | head -1)
[ -n "$VERSION" ] || { echo "build-windows: no purittyVersion in app/src/Main.geng" >&2; exit 1; }
COMMAS=$(echo "$VERSION.0.0.0" | cut -d. -f1-4 | tr . ,)
RC=../../.harness-work/windows/puritty.rc
{
    cat ../icon/puritty.rc
    cat <<EOF2

#include <winver.h>
1 VERSIONINFO
FILEVERSION $COMMAS
PRODUCTVERSION $COMMAS
FILEOS VOS_NT_WINDOWS32
FILETYPE VFT_APP
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904B0"
        BEGIN
            VALUE "CompanyName", "Gilbert Ramirez"
            VALUE "FileDescription", "puritty"
            VALUE "FileVersion", "$VERSION"
            VALUE "InternalName", "puritty"
            VALUE "LegalCopyright", "Copyright (c) 2026, Gilbert Ramirez"
            VALUE "OriginalFilename", "puritty.exe"
            VALUE "ProductName", "puritty"
            VALUE "ProductVersion", "$VERSION"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200
    END
END
EOF2
} >"$RC"
x86_64-w64-mingw32-windres -I ../icon "$RC" -O coff -o "$ICON"
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS $ICON" GENG_PKG_CONFIG=x86_64-w64-mingw32-pkg-config \
PKG_CONFIG_PATH=$T PKG_CONFIG_PATH_x86_64_w64_mingw32=$T \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --platform=windows --output=../puritty.exe "$@"

#!/usr/bin/env bash
# FreeType and HarfBuzz for Windows, static, for puritty's window on Windows
# (docs/windows.md WS3, WS12 step 1): built from the sources geng-lang's
# nixpkgs pin has, with geng-lang's Windows toolchain
# (scripts/windows-toolchain.sh), into vendor/win-text, with pkg-config files
# a Windows build reads (geng-lang D890):
#
#   packages/win32/build-text-libs.sh
#   PKG_CONFIG_PATH_x86_64_w64_mingw32=$PWD/vendor/win-text/lib/pkgconfig ...
#
# FreeType is its core and the modules OpenType and TrueType faces need,
# with its own copy of zlib and no libpng, bzip2 or Brotli: libpng serves
# bitmap emoji fonts (CBDT), and Windows' emoji font draws from its colour
# table (COLR), which FreeType draws itself. HarfBuzz is its one source file,
# threads off (puritty shapes on its window thread alone), compiled by the
# toolchain's g++, whose C++ headers find mcfgthread where clang's do not;
# the object needs only the C library.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
geng=${GENG_LANG:-/home/gram/prj/geng-lang}
out=${1:-$root/vendor/win-text}
eval "$("$geng/scripts/windows-toolchain.sh")"
rev=$(grep -o 'github:NixOS/nixpkgs/[0-9a-f]*#clang"' "$geng/devbox.json" | sed 's/.*nixpkgs\/\([0-9a-f]*\)#.*/\1/')
work=$out/build
rm -rf "$work"
mkdir -p "$work" "$out/lib/pkgconfig" "$out/include"
src() { nix build --no-link --print-out-paths "github:NixOS/nixpkgs/$rev#$1.src"; }
mkdir -p "$work/freetype" "$work/harfbuzz"
tar xf "$(src freetype)" -C "$work/freetype" --strip-components=1
tar xf "$(src harfbuzz)" -C "$work/harfbuzz" --strip-components=1
mcf=$(nix-store -qR "$(readlink -f "$(dirname "$(command -v x86_64-w64-mingw32-gcc)")/..")" | grep 'mcfgthread.*-dev$' | head -1)

# FreeType
ft=$work/freetype
cat > "$ft/ftmodule-puritty.h" <<'H'
FT_USE_MODULE( FT_Module_Class, autofit_module_class )
FT_USE_MODULE( FT_Driver_ClassRec, tt_driver_class )
FT_USE_MODULE( FT_Driver_ClassRec, cff_driver_class )
FT_USE_MODULE( FT_Module_Class, psaux_module_class )
FT_USE_MODULE( FT_Module_Class, psnames_module_class )
FT_USE_MODULE( FT_Module_Class, pshinter_module_class )
FT_USE_MODULE( FT_Module_Class, sfnt_module_class )
FT_USE_MODULE( FT_Renderer_Class, ft_smooth_renderer_class )
H
files=(base/ftsystem.c base/ftinit.c base/ftdebug.c base/ftbase.c base/ftbitmap.c base/ftglyph.c base/ftsynth.c base/ftbbox.c base/ftmm.c
       autofit/autofit.c truetype/truetype.c cff/cff.c psaux/psaux.c psnames/psnames.c pshinter/pshinter.c sfnt/sfnt.c smooth/smooth.c gzip/ftgzip.c)
objs=()
for f in "${files[@]}"; do
    o=$work/ft-$(basename "$f" .c).o
    x86_64-w64-mingw32-clang -O2 -DFT2_BUILD_LIBRARY '-DFT_CONFIG_MODULES_H=<ftmodule-puritty.h>' -I"$ft" -I"$ft/include" -c "$ft/src/$f" -o "$o"
    objs+=("$o")
done
rm -f "$out/lib/libfreetype.a"
x86_64-w64-mingw32-ar rcs "$out/lib/libfreetype.a" "${objs[@]}"
rm -rf "$out/include/freetype2"
mkdir -p "$out/include/freetype2"
cp -r "$ft/include/ft2build.h" "$ft/include/freetype" "$out/include/freetype2/"
ftv=$(sed -n 's/^#define FREETYPE_\(MAJOR\|MINOR\|PATCH\) *\([0-9]*\).*/\2/p' "$ft/include/freetype/freetype.h" | paste -sd.)

# HarfBuzz
hb=$work/harfbuzz
x86_64-w64-mingw32-g++ -O2 -std=c++17 -fno-exceptions -fno-rtti -fno-threadsafe-statics -DHB_NO_MT -DHAVE_FREETYPE=1 \
    -I"$out/include/freetype2" -I"$mcf/include" -c "$hb/src/harfbuzz.cc" -o "$work/harfbuzz.o"
rm -f "$out/lib/libharfbuzz.a"
x86_64-w64-mingw32-ar rcs "$out/lib/libharfbuzz.a" "$work/harfbuzz.o"
rm -rf "$out/include/harfbuzz"
mkdir -p "$out/include/harfbuzz"
cp "$hb"/src/hb*.h "$out/include/harfbuzz/"
hbv=$(sed -n "s/^ *version: *'\([0-9.]*\)'.*/\1/p" "$hb/meson.build" | head -1)

cat > "$out/lib/pkgconfig/freetype2.pc" <<PC
prefix=$out
Name: FreeType 2
Description: FreeType $ftv for Windows, static, OpenType and TrueType only (puritty)
Version: $ftv
Cflags: -I\${prefix}/include/freetype2
Libs: -L\${prefix}/lib -lfreetype
PC
cat > "$out/lib/pkgconfig/harfbuzz.pc" <<PC
prefix=$out
Name: harfbuzz
Description: HarfBuzz $hbv for Windows, static, one thread (puritty)
Version: $hbv
Requires: freetype2
Cflags: -I\${prefix}/include/harfbuzz
Libs: -L\${prefix}/lib -lharfbuzz
PC
rm -rf "$work"
echo "FreeType $ftv and HarfBuzz $hbv in $out"

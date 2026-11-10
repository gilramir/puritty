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
# with its own copy of zlib and with libpng, but no bzip2 or Brotli. Windows'
# emoji font draws from its colour table (COLR), which FreeType draws itself;
# libpng is for a bitmap emoji font (CBDT) such as Noto Color Emoji, which a
# user may install and the pixel gate draws with (docs/windows.md WS18), and
# it is built static with a zlib of its own, so puritty stays one .exe.
# HarfBuzz is its one source file,
# threads off (puritty shapes on its window thread alone), compiled by the
# toolchain's g++, whose C++ headers find mcfgthread where clang's do not;
# the object needs only the C library.
#
# FreeType's autohinter uses HarfBuzz (FT_CONFIG_OPTION_USE_HARFBUZZ), as
# nixpkgs' FreeType on Linux does by loading it at run time: it styles the
# glyphs a font reaches only through its substitutions (Fira Code's
# ligatures, Thai's and Devanagari's forms) by their script, and without it
# those glyphs are hinted otherwise and the pixel gate's pictures differ
# from Linux's (docs/windows.md WS18). The two libraries need each other,
# so freetype2.pc links HarfBuzz after FreeType.
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
mkdir -p "$work/freetype" "$work/harfbuzz" "$work/zlib" "$work/libpng"
tar xf "$(src freetype)" -C "$work/freetype" --strip-components=1
tar xf "$(src harfbuzz)" -C "$work/harfbuzz" --strip-components=1
tar xf "$(src zlib)" -C "$work/zlib" --strip-components=1
tar xf "$(src libpng)" -C "$work/libpng" --strip-components=1
mcf=$(nix-store -qR "$(readlink -f "$(dirname "$(command -v x86_64-w64-mingw32-gcc)")/..")" | grep 'mcfgthread.*-dev$' | head -1)

# zlib and libpng, for FreeType's PNG glyphs
z=$work/zlib
zobjs=()
for f in adler32 compress crc32 deflate gzclose gzlib gzread gzwrite infback inffast inflate inftrees trees uncompr zutil; do
    x86_64-w64-mingw32-clang -O2 -I"$z" -c "$z/$f.c" -o "$work/z-$f.o"
    zobjs+=("$work/z-$f.o")
done
rm -f "$out/lib/libz.a"
x86_64-w64-mingw32-ar rcs "$out/lib/libz.a" "${zobjs[@]}"
png=$work/libpng
cp "$png/scripts/pnglibconf.h.prebuilt" "$png/pnglibconf.h"
pobjs=()
for f in png pngerror pngget pngmem pngpread pngread pngrio pngrtran pngrutil pngset pngtrans pngwio pngwrite pngwtran pngwutil; do
    x86_64-w64-mingw32-clang -O2 -DPNG_ARM_NEON_OPT=0 -DPNG_INTEL_SSE_OPT=0 -DPNG_POWERPC_VSX_OPT=0 -DPNG_LOONGARCH_LSX_OPT=0 \
        -I"$png" -I"$z" -c "$png/$f.c" -o "$work/png-$f.o"
    pobjs+=("$work/png-$f.o")
done
rm -f "$out/lib/libpng.a"
x86_64-w64-mingw32-ar rcs "$out/lib/libpng.a" "${pobjs[@]}"

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
    x86_64-w64-mingw32-clang -O2 -DFT2_BUILD_LIBRARY '-DFT_CONFIG_MODULES_H=<ftmodule-puritty.h>' -DFT_CONFIG_OPTION_USE_HARFBUZZ -DFT_CONFIG_OPTION_USE_PNG \
        -I"$ft" -I"$ft/include" -I"$work/harfbuzz/src" -I"$png" -I"$z" -c "$ft/src/$f" -o "$o"
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
Description: FreeType $ftv for Windows, static, OpenType and TrueType only, with PNG glyphs (puritty)
Version: $ftv
Cflags: -I\${prefix}/include/freetype2
Libs: -L\${prefix}/lib -lfreetype -lharfbuzz -lpng -lz
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

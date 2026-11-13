#!/usr/bin/env bash
# build-libs.sh's part inside a puritty-build-NAME image: WORK holds the
# unpacked sources, OUT gets lib/*.a, include/ and lib/pkgconfig/*.pc,
# IMDKIT is the patched xcb-imdkit checkout.
set -euo pipefail
work=$1 out=$2 imdkit=$3
CC=clang CXX=clang++
flags=(-O2 -fPIC)

# FreeType: its core and the modules OpenType and TrueType faces need, with
# PNG glyphs and HarfBuzz for the autohinter, as the Windows build has it
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
objs=()
for f in base/ftsystem.c base/ftinit.c base/ftdebug.c base/ftbase.c base/ftbitmap.c base/ftglyph.c base/ftsynth.c base/ftbbox.c base/ftmm.c \
         autofit/autofit.c truetype/truetype.c cff/cff.c psaux/psaux.c psnames/psnames.c pshinter/pshinter.c sfnt/sfnt.c smooth/smooth.c gzip/ftgzip.c; do
    o=$work/ft-$(basename "$f" .c).o
    $CC "${flags[@]}" -DFT2_BUILD_LIBRARY '-DFT_CONFIG_MODULES_H=<ftmodule-puritty.h>' -DFT_CONFIG_OPTION_USE_HARFBUZZ \
        -DFT_CONFIG_OPTION_USE_PNG -DFT_CONFIG_OPTION_SYSTEM_ZLIB \
        -I"$ft" -I"$ft/include" -I"$work/harfbuzz/src" -c "$ft/src/$f" -o "$o"
    objs+=("$o")
done
rm -f "$out/lib/libfreetype.a"
ar rcs "$out/lib/libfreetype.a" "${objs[@]}"
rm -rf "$out/include/freetype2"
mkdir -p "$out/include/freetype2"
cp -r "$ft/include/ft2build.h" "$ft/include/freetype" "$out/include/freetype2/"
ftv=$(sed -n 's/^#define FREETYPE_\(MAJOR\|MINOR\|PATCH\) *\([0-9]*\).*/\2/p' "$ft/include/freetype/freetype.h" | paste -sd.)
# freetype2.pc's version is the libtool one (26.6.20 for 2.14.3), which
# fontconfig.pc asks for (>= 20.0.14 on RHEL8)
ftlt=$(sed -n "s/^version_info='\([0-9:]*\)'.*/\1/p" "$ft/builds/unix/configure.raw" | tr : .)

# HarfBuzz, its one source file, one thread, no C++ runtime beyond
# what the C library has
hb=$work/harfbuzz
$CXX "${flags[@]}" -std=c++17 -fno-exceptions -fno-rtti -fno-threadsafe-statics -DHB_NO_MT -DHAVE_FREETYPE=1 \
    -I"$out/include/freetype2" -c "$hb/src/harfbuzz.cc" -o "$work/harfbuzz.o"
rm -f "$out/lib/libharfbuzz.a"
ar rcs "$out/lib/libharfbuzz.a" "$work/harfbuzz.o"
rm -rf "$out/include/harfbuzz"
mkdir -p "$out/include/harfbuzz"
cp "$hb"/src/hb*.h "$out/include/harfbuzz/"
hbv=$(sed -n "s/^ *version: *'\([0-9.]*\)'.*/\1/p" "$hb/meson.build" | head -1)

# xcb-util-cursor
cu=$work/cursor
cobjs=()
for f in cursor load_cursor parse_cursor_file shape_to_id; do
    $CC "${flags[@]}" -D_GNU_SOURCE "-DXCURSORPATH=\"~/.local/share/icons:~/.icons:/usr/share/icons:/usr/share/pixmaps\"" -I"$cu/cursor" -I"$cu" $(pkg-config --cflags xcb xcb-render xcb-renderutil xcb-image) \
        -c "$cu/cursor/$f.c" -o "$work/cursor-$f.o"
    cobjs+=("$work/cursor-$f.o")
done
rm -f "$out/lib/libxcb-cursor.a"
ar rcs "$out/lib/libxcb-cursor.a" "${cobjs[@]}"
mkdir -p "$out/include/xcb"
cp "$cu/cursor/xcb_cursor.h" "$out/include/xcb/"
cuv=$(sed -n 's/^AC_INIT(\[[^]]*\], *\[\([0-9.]*\)\].*/\1/p' "$cu/configure.ac" | head -1)

# xcb-imdkit with puritty's patches
S=$imdkit/src
iobjs=()
for f in parser ximproto imdkit protocolhandler message common imclient clientprotocolhandler encoding \
         xlibi18n/lcCT xlibi18n/lcUTF8 xlibi18n/lcCharSet; do
    o=$work/imdkit-$(basename "$f").o
    $CC "${flags[@]}" -D_GNU_SOURCE -fvisibility=hidden -Dxcb_imdkit_EXPORTS -I"$S" -I"$imdkit/puritty/gen" -I"$imdkit/uthash" \
        $(pkg-config --cflags xcb xcb-util) -c "$S/$f.c" -o "$o"
    iobjs+=("$o")
done
rm -f "$out/lib/libpuritty-xcb-imdkit.a"
ar rcs "$out/lib/libpuritty-xcb-imdkit.a" "${iobjs[@]}"
rm -rf "$out/include/xcb-imdkit"
mkdir -p "$out/include/xcb-imdkit"
cp "$S"/imdkit.h "$S"/ximcommon.h "$S"/ximproto.h "$S"/ximproto-gen.h "$S"/imclient.h "$S"/encoding.h \
    "$imdkit/puritty/gen/xcbimdkit_export.h" "$out/include/xcb-imdkit/"

pc=$out/lib/pkgconfig
cat > "$pc/freetype2.pc" <<PC
prefix=$out
Name: FreeType 2
Description: FreeType $ftv, static, OpenType and TrueType only (puritty)
Version: $ftlt
Requires.private: libpng zlib
Cflags: -I\${prefix}/include/freetype2
Libs: -L\${prefix}/lib -lfreetype -lharfbuzz -lpng16 -lz
PC
cat > "$pc/harfbuzz.pc" <<PC
prefix=$out
Name: harfbuzz
Description: HarfBuzz $hbv, static, one thread (puritty)
Version: $hbv
Requires: freetype2
Cflags: -I\${prefix}/include/harfbuzz
Libs: -L\${prefix}/lib -lharfbuzz
PC
cat > "$pc/xcb-cursor.pc" <<PC
prefix=$out
Name: XCB cursor library
Description: xcb-util-cursor $cuv, static (puritty)
Version: $cuv
Requires: xcb xcb-render xcb-renderutil xcb-image
Cflags: -I\${prefix}/include
Libs: -L\${prefix}/lib -lxcb-cursor
PC
cat > "$pc/puritty-xcb-imdkit.pc" <<PC
prefix=$out
Name: puritty-xcb-imdkit
Description: xcb-imdkit 621048bd with puritty's patches, static
Version: 1.0.9
Requires: xcb xcb-util
Cflags: -I\${prefix}/include
Libs: -L\${prefix}/lib -lpuritty-xcb-imdkit
PC
echo "FreeType $ftv, HarfBuzz $hbv, xcb-util-cursor $cuv and xcb-imdkit in $out"

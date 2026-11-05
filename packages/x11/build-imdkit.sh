#!/bin/sh
# Builds xcb-imdkit with visiterm's patches (docs/phase3-input.md V44) into
# vendor/xcb-imdkit/visiterm: a shared library with an rpath, its headers,
# and visiterm-xcb-imdkit.pc, which packages/x11 links by. The checkout, made
# here when it is not there, is upstream's 621048bd50e8f3cbf52335f824f7b4d708a21b14.
# Each patch in patches/xcb-imdkit-*.patch is applied once; the library is
# built again when the set changes. Run from visiterm's devbox (libxcb,
# xcb-util).
set -e
cd "$(dirname "$0")"
V=$(realpath ../..)
X=$V/vendor/xcb-imdkit
O=$X/visiterm
CC=/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang
# The pinned commit fetched into the directory rather than cloned, so that a
# directory already there without a clone (an earlier build's output, say)
# does not stop it: `git clone` refuses a directory that is not empty.
if [ ! -d "$X/.git" ]; then
  mkdir -p "$X"
  git -C "$X" init -q
  git -C "$X" fetch -q https://github.com/fcitx/xcb-imdkit 621048bd50e8f3cbf52335f824f7b4d708a21b14
  git -C "$X" checkout -q -f FETCH_HEAD
fi
for p in patches/xcb-imdkit-*.patch; do
  git -C "$X" apply --reverse --check "$(realpath "$p")" 2>/dev/null || git -C "$X" apply "$(realpath "$p")"
done
want=$(cat patches/xcb-imdkit-*.patch | sha256sum | cut -d' ' -f1)
[ -f "$O/lib/libvisiterm-xcb-imdkit.so" ] && [ "$(cat "$O/.patches" 2>/dev/null)" = "$want" ] && exit 0
rm -rf "$O"; mkdir -p "$O/lib/pkgconfig" "$O/include/xcb-imdkit" "$O/gen"
cp "$(dirname "$(pkg-config --variable=includedir xcb-imdkit)")/include/xcb-imdkit/xcbimdkit_export.h" "$O/gen/" 2>/dev/null || \
  cp "$V/.devbox/nix/profile/default/include/xcb-imdkit/xcbimdkit_export.h" "$O/gen/"
S=$X/src
$CC -O2 -fPIC -shared -fvisibility=hidden -Dxcb_imdkit_EXPORTS -I"$S" -I"$O/gen" -I"$X/uthash" \
  $(pkg-config --cflags xcb xcb-util) \
  "$S"/parser.c "$S"/ximproto.c "$S"/imdkit.c "$S"/protocolhandler.c "$S"/message.c "$S"/common.c \
  "$S"/imclient.c "$S"/clientprotocolhandler.c "$S"/encoding.c \
  "$S"/xlibi18n/lcCT.c "$S"/xlibi18n/lcUTF8.c "$S"/xlibi18n/lcCharSet.c \
  -Wl,-soname,libvisiterm-xcb-imdkit.so -o "$O/lib/libvisiterm-xcb-imdkit.so" $(pkg-config --libs xcb xcb-util)
cp "$S"/imdkit.h "$S"/ximcommon.h "$S"/ximproto.h "$S"/ximproto-gen.h "$S"/imclient.h "$S"/encoding.h "$O/gen/xcbimdkit_export.h" \
  "$O/include/xcb-imdkit/"
cat >"$O/lib/pkgconfig/visiterm-xcb-imdkit.pc" <<PC
prefix=$O
Name: visiterm-xcb-imdkit
Description: xcb-imdkit 621048bd with visiterm's patches
Version: 1.0.9
Requires: xcb xcb-util
Cflags: -I\${prefix}/include
Libs: -L\${prefix}/lib -Wl,-rpath,\${prefix}/lib -lvisiterm-xcb-imdkit
PC
echo "$want" >"$O/.patches"

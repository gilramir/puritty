#!/bin/sh
# Builds xim-probe (xim_probe.c) on Ubuntu 24.04 in a container, three ways,
# into OUT-DIR: against Ubuntu's libxcb-imdkit (stock), against upstream's
# source at puritty's pinned commit (upstream), and against puritty's patched
# copy as the noble build bundles it (ours). Run each on a desktop with an
# XIM input method: XMODIFIERS=@im=ibus ./xim-probe-stock
#
#   harness/xim-probe/build.sh OUT-DIR
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
out=$(realpath "${1:?an output folder}")
mkdir -p "$out/upstream" "$out/ours/xcb-imdkit"
cp "$here/xim_probe.c" "$out/"
git -C "$root/vendor/xcb-imdkit" archive 621048bd50e8f3cbf52335f824f7b4d708a21b14 | tar -x -C "$out/upstream"
cp "$root/vendor/xcb-imdkit/src/"*.h "$out/ours/xcb-imdkit/"
cp "$root/vendor/distro/noble/lib/libpuritty-xcb-imdkit.a" "$out/"
podman run --rm -v "$out:/p" -w /p docker.io/library/ubuntu:24.04 sh -c '
set -e
apt-get -qq update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get -qq -y install gcc pkg-config libxcb1-dev libxcb-util-dev libxcb-imdkit-dev >/dev/null 2>&1
gcc -O1 -o xim-probe-stock xim_probe.c $(pkg-config --cflags --libs xcb-imdkit xcb)
U=upstream/src
cp /usr/include/xcb-imdkit/xcbimdkit_export.h $U/
cp /usr/include/xcb-imdkit/xcbimdkit_export.h ours/xcb-imdkit/
# upstream'"'"'s own headers, not the installed ones, for the probe too
mkdir -p uinc/xcb-imdkit && cp $U/*.h uinc/xcb-imdkit/
gcc -O1 -Dxcb_imdkit_EXPORTS -I$U -Iuinc -Iupstream/uthash -o xim-probe-upstream xim_probe.c \
  $U/parser.c $U/ximproto.c $U/imdkit.c $U/protocolhandler.c $U/message.c $U/common.c $U/imclient.c \
  $U/clientprotocolhandler.c $U/encoding.c $U/xlibi18n/lcCT.c $U/xlibi18n/lcUTF8.c $U/xlibi18n/lcCharSet.c \
  $(pkg-config --cflags --libs xcb xcb-util)
gcc -O1 -Iours -o xim-probe-ours xim_probe.c libpuritty-xcb-imdkit.a $(pkg-config --cflags --libs xcb xcb-util)
'
ls -l "$out"/xim-probe-*

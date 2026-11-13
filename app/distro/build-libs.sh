#!/usr/bin/env bash
# The libraries a distribution build links in rather than takes from the
# distribution (README.md; docs/rhel8-etx.md RE4), built static inside its
# puritty-build-NAME image into vendor/distro/NAME, with pkg-config files the
# build reads:
#
# - FreeType and HarfBuzz from the sources geng-lang's nixpkgs pin has, as
#   packages/win32/build-text-libs.sh builds them for Windows, so that
#   every build shapes and draws text alike (RHEL8's are 2.9.1 and 1.7.5,
#   from 2018). FreeType reads PNG glyphs through the distribution's own
#   libpng and zlib.
# - xcb-util-cursor, which RHEL8 does not have.
# - xcb-imdkit with puritty's patches (packages/x11/build-imdkit.sh makes
#   the patched checkout).
#
# The distribution's own libxcb, xkbcommon and fontconfig are linked as
# they are. Run on the host (it needs nix for the sources and podman):
#
#   app/distro/build-libs.sh rhel8
set -euo pipefail
name=${1:?the distribution, a folder of app/distro}
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
geng=${GENG_LANG:-/home/gram/prj/geng-lang}
out=$root/vendor/distro/$name
rev=$(grep -o 'github:NixOS/nixpkgs/[0-9a-f]*#clang"' "$geng/devbox.json" | sed 's/.*nixpkgs\/\([0-9a-f]*\)#.*/\1/')
src() { nix build --no-link --print-out-paths "github:NixOS/nixpkgs/$rev#$1.src"; }

# the patched xcb-imdkit checkout, and its generated export header
(cd "$root" && devbox run -- packages/x11/build-imdkit.sh >/dev/null)

work=$out/build
rm -rf "$work"
mkdir -p "$work"/{freetype,harfbuzz,cursor} "$out/lib/pkgconfig" "$out/include"
tar xf "$(src freetype)" -C "$work/freetype" --strip-components=1
tar xf "$(src harfbuzz)" -C "$work/harfbuzz" --strip-components=1
tar xf "$(src xcb-util-cursor)" -C "$work/cursor" --strip-components=1

podman image exists "puritty-build-$name" || podman build -q -t "puritty-build-$name" "$here/$name"
podman run --rm --userns=keep-id -v "$root:$root" -w "$root" "puritty-build-$name" \
    bash "$here/libs-inside.sh" "$work" "$out" "$root/vendor/xcb-imdkit"
rm -rf "$work"

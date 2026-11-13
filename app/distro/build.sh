#!/bin/sh
# Builds puritty for one Linux distribution release (README.md;
# docs/rhel8-etx.md RE4), app/puritty-NAME: the Linux manifest (app/linux)
# compiled by geng-lang's compiler to C, and the C compiled and linked in
# the puritty-build-NAME image against its glibc and X libraries, with
# FreeType, HarfBuzz, xcb-util-cursor and xcb-imdkit built in. Further
# arguments go to `geng make` (`--profile-use=…`). PURITTY_DISTRO_OUT
# names another output. Run from puritty's devbox, which has node.
#
#   app/distro/build.sh rhel8
set -e
name=${1:?the distribution, a folder of app/distro}
shift
here=$(cd "$(dirname "$0")" && pwd)
[ -f "$here/$name/Containerfile" ] || { echo "no app/distro/$name/Containerfile" >&2; exit 1; }
podman image exists "puritty-build-$name" || podman build -q -t "puritty-build-$name" "$here/$name"
[ -f "$here/../../vendor/distro/$name/lib/libharfbuzz.a" ] || "$here/build-libs.sh" "$name"
cd "$here/../linux"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
out=${PURITTY_DISTRO_OUT:-$here/../puritty-$name}
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
PURITTY_DISTRO=$name \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$here/cc NIX_HARDENING_ENABLE= \
GENG_PKG_CONFIG=$here/pkg-config \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --output="$out" "$@"

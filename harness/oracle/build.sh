#!/bin/sh
# Builds ghostty-dump against the vendored libghostty-vt, building that first
# if it is not built (Zig 0.16 from visiterm's devbox; its packages are in
# vendor/ghostty/zig-pkg). The library is linked statically.
set -e
cd "$(dirname "$0")"
V=$(realpath ../..)
G=$V/vendor/ghostty
PATH=$V/.devbox/nix/profile/default/bin:/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin:$PATH
if [ ! -f "$G/zig-out/lib/libghostty-vt.a" ]; then
  (cd "$G" && zig build -Demit-lib-vt=true -Doptimize=ReleaseFast)
fi
clang -O2 -Wall -Wextra -I"$G/zig-out/include" ghostty-dump.c gdump.c \
  "$G/zig-out/lib/libghostty-vt.a" -lm -lpthread -o ghostty-dump

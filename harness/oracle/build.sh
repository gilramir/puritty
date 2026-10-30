#!/bin/sh
# Builds ghostty-dump against the vendored libghostty-vt, building that first
# if it is not built (Zig 0.16 from visiterm's devbox; its packages are in
# vendor/ghostty/zig-pkg). The library is linked statically.
#
# The oracle is Ghostty v1.4.0 with patches/ applied: fixes of Ghostty bugs
# the core does not copy, so that the differential fuzzer does not stumble
# over them (docs/vt-core.md §VC17). Each patch is applied once to the
# vendored tree, and the library is built again when the set changes.
set -e
cd "$(dirname "$0")"
V=$(realpath ../..)
G=$V/vendor/ghostty
PATH=$V/.devbox/nix/profile/default/bin:/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin:$PATH
for p in "$V"/harness/oracle/patches/*.patch; do
  if ! git -C "$G" apply --reverse --check "$p" 2>/dev/null; then
    git -C "$G" apply "$p"
  fi
done
want=$(cat "$V"/harness/oracle/patches/*.patch | sha256sum | cut -d' ' -f1)
have=$(cat "$G/zig-out/.visiterm-patches" 2>/dev/null || true)
if [ ! -f "$G/zig-out/lib/libghostty-vt.a" ] || [ "$want" != "$have" ]; then
  (cd "$G" && zig build -Demit-lib-vt=true -Doptimize=ReleaseFast)
  echo "$want" > "$G/zig-out/.visiterm-patches"
fi
clang -O2 -Wall -Wextra -I"$G/zig-out/include" ghostty-dump.c gdump.c \
  "$G/zig-out/lib/libghostty-vt.a" -lm -lpthread -o ghostty-dump
clang -O2 -Wall -Wextra -I"$G/zig-out/include" widths.c \
  "$G/zig-out/lib/libghostty-vt.a" -lm -lpthread -o widths

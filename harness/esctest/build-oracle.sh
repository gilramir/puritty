#!/bin/sh
# Builds ghostty-pty, the oracle's side of the esctest2 run (docs/vt-core.md
# §VC10), against the libghostty-vt that harness/oracle/build.sh builds.
set -e
cd "$(dirname "$0")"
V=$(realpath ../..)
G=$V/vendor/ghostty
[ -f "$G/zig-out/lib/libghostty-vt.a" ] || ../oracle/build.sh
PATH=/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin:$PATH \
  clang -O2 -Wall -Wextra -I"$G/zig-out/include" ghostty-pty.c \
  "$G/zig-out/lib/libghostty-vt.a" -lm -lpthread -o ghostty-pty

#!/bin/sh
# Builds gdrag, libghostty-vt timed on core-bench's drag (vt-core.md §VC30),
# against the oracle's library (harness/oracle/build.sh builds it).
set -e
cd "$(dirname "$0")"
G=$(realpath ../../../../vendor/ghostty)
NIX_HARDENING_ENABLE= /home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang -O2 \
  -I "$G/zig-out/include" gdrag.c "$G/zig-out/lib/libghostty-vt.a" -lm -lpthread -o gdrag

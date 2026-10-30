#!/bin/sh
# Builds vt-fuzz and vt-min (docs/vt-core.md §VC11), and vt-diff and
# vt-diff-min, which hold the core to libghostty-vt (§VC16) and need
# harness/oracle/build.sh's library: the core as a runtime = "host"
# library (`Fuzz`), with the passes the core is measured with, its C then
# compiled again with libFuzzer's coverage into one program with fuzz.c.
# geng make builds no library C with extra flags, so this repeats its
# second step (geng-lang m3-embed.md D629) with them; Boehm's object is the
# build's own. Extra arguments are clang's, e.g. -fsanitize=address.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
CC=$R/.devbox/nix/profile/default/bin/clang
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$CC NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace \
  node $C/app make Fuzz --debug-info --output=libvtfuzz.so
D=libvtfuzz.so.native-build
NIX_HARDENING_ENABLE= "$CC" -std=c11 -O2 -g -ffp-contract=off -fno-fast-math \
  -fsanitize=fuzzer-no-link -DGENG_LIBRARY=vtfuzz \
  -I "$D/boehm/include/gc" -I "$D/boehm/include" -I "$D" -c \
  "$D/program.c" "$D/geng.c" "$D/geng_rt.c" "$D/geng_embed.c" "$@"
NIX_HARDENING_ENABLE= "$CC" -O2 -g -fsanitize=fuzzer -I . fuzz.c \
  program.o geng.o geng_rt.o geng_embed.o "$D/boehm/gc.o" -lm -o vt-fuzz "$@"
# vt-min: the same objects, its own main.
NIX_HARDENING_ENABLE= "$CC" -O2 -g -fsanitize=fuzzer-no-link -I . min.c \
  program.o geng.o geng_rt.o geng_embed.o "$D/boehm/gc.o" -lm -o vt-min "$@"
# vt-diff and vt-diff-min: the same, with libghostty-vt beside the core.
G=$(realpath ../../vendor/ghostty)
[ -f "$G/zig-out/lib/libghostty-vt.a" ] || ../oracle/build.sh
NIX_HARDENING_ENABLE= "$CC" -O2 -g -I "$G/zig-out/include" -c ../oracle/gdump.c "$@"
NIX_HARDENING_ENABLE= "$CC" -O2 -g -fsanitize=fuzzer -DVTFUZZ_DIFF -I . fuzz.c gdump.o \
  program.o geng.o geng_rt.o geng_embed.o "$D/boehm/gc.o" "$G/zig-out/lib/libghostty-vt.a" \
  -lm -lpthread -o vt-diff "$@"
NIX_HARDENING_ENABLE= "$CC" -O2 -g -fsanitize=fuzzer-no-link -DVTFUZZ_DIFF -I . min.c gdump.o \
  program.o geng.o geng_rt.o geng_embed.o "$D/boehm/gc.o" "$G/zig-out/lib/libghostty-vt.a" \
  -lm -lpthread -o vt-diff-min "$@"
rm -f program.o geng.o geng_rt.o geng_embed.o gdump.o

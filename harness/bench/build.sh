#!/bin/sh
# Builds core-bench, the core timed on the throughput inputs
# (docs/vt-core.md §VC7), with geng-lang's compiler and devbox's clang, and
# the passes bench/compare measures the probe with. CORE_BENCH_OUTPUT names
# another file to build, and GENG_CFLAGS reaches the C compiler after its -O,
# which is how perf.py --layouts builds the same core with other frames.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  exec node $C/app make Main --output="${CORE_BENCH_OUTPUT:-core-bench}" "$@"

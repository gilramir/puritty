#!/bin/sh
# Builds the c-call probe natively with the system gcc, as measured on
# 2026-10-23 (docs/geng-plan.md §1). Two workarounds are in it on purpose:
# devbox's clang cannot see /usr/include/xcb, and GENG_CFLAGS lands before the
# object files, so the linker drops -lxcb unless --no-as-needed is given.
set -e
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=/usr/bin/gcc NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall \
GENG_CFLAGS="-Wl,--no-as-needed $(pkg-config --cflags --libs xcb)" \
  exec node $C/app make Main --output=probe "$@"

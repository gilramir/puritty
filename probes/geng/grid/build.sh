#!/bin/sh
# Builds the probe natively the way harness/run.py's geng-c target does.
set -e
PATH=/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin:$PATH GENG_BIN=/home/gram/prj/geng-lang/vendor/gren-lang/compiler/geng GENG_CORE=/home/gram/prj/geng-lang/vendor/gren-lang/core GENG_CC=/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall \
  exec node /home/gram/prj/geng-lang/vendor/gren-lang/compiler/app make Main --output=probe "$@"

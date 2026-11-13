#!/bin/sh
# The core's unit tests as a native program (geng-lang m1b-test.md §TS11):
# the suites ../run.sh runs on node, built with the passes the core is
# built with and devbox's clang, and run by gren-unit-node's native runner.
# Its arguments are the runner's, e.g. a glob of the tests to run. With
# --windows it builds tests.exe instead, to run on Windows.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
if [ "$1" = "--windows" ]; then
  # tests.exe for Windows, cross-compiled by geng-lang's toolchain; run it there
  shift
  eval "$("$R/scripts/windows-toolchain.sh")"
  rm -f tests.exe
  PATH=$R/.devbox/nix/profile/default/bin:$PATH \
  GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=x86_64-w64-mingw32-clang NIX_HARDENING_ENABLE= \
  GENG_LDFLAGS="$GENG_WINDOWS_LDFLAGS" \
  GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
    exec node $C/app make Native --platform=windows --output=tests.exe "$@" >/dev/null
fi
rm -f tests
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  node $C/app make Native --output=tests >/dev/null
exec ./tests "$@"

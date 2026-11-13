#!/bin/sh
# The application's unit tests as a native program (geng-lang m1b-test.md
# §TS11): the suites ../run.sh runs on node, built as app/build.sh builds
# puritty (its passes, devbox's clang, the X11 package's libraries) and run
# by gren-unit-node's native runner. Run from puritty's devbox, which has
# those libraries. Its arguments are the runner's, e.g. a glob of the tests
# to run.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
../../../packages/x11/build-imdkit.sh >/dev/null
I=$(realpath ../../../vendor/xcb-imdkit/puritty/lib/pkgconfig)
C=$R/vendor/gren-lang/compiler
rm -f tests
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_CC=$R/.devbox/nix/profile/default/bin/clang NIX_HARDENING_ENABLE= \
GENG_PKG_CONFIG=$(command -v pkg-config) \
PKG_CONFIG_PATH=$I:$PKG_CONFIG_PATH PKG_CONFIG_PATH_FOR_TARGET=$I:$PKG_CONFIG_PATH_FOR_TARGET \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  node $C/app make NativeTests --output=tests >/dev/null
exec ./tests "$@"

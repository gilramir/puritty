#!/bin/sh
# The application's unit tests (docs/settings.md ST17), built with the passes the
# core is built with, on node, with gren-unit-node. Its
# arguments are the runner's, e.g. a glob of the tests to run.
set -e
cd "$(dirname "$0")"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
PATH=$R/.devbox/nix/profile/default/bin:$PATH
export PATH
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core \
GENG_CORE_PASSES=specialize,foldspec,transient,arraypop,mono,inline,float,floatin,mutual,case,tailcall,inplace,drop,appends \
  node $C/app make Tests --output=app >/dev/null
exec node app "$@"

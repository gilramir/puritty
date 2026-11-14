#!/bin/sh
# geng checks over the whole program (docs/vt-core.md §VC58, §VC64): the
# application as app/linux builds it, held to corpus/checks/baseline.tsv.
# A fallback that can run and is neither marked `meant` nor on the list,
# an open check, a stale mark or an unused reason fails it. The unit gate
# (harness/units.py) runs it so.
#
# usage (from puritty's devbox, which has the C libraries' pkg-config):
#     scripts/checks.sh                   held to the baseline
#     scripts/checks.sh --update          the baseline written again
#     scripts/checks.sh --json FILE       the report as JSON too
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/app/linux"
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
I=$(realpath ../../vendor/xcb-imdkit/puritty/lib/pkgconfig)
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core GENG_DEP_ERRORS=1 \
GENG_PKG_CONFIG=$(command -v pkg-config) PKG_CONFIG_PATH=$I:$PKG_CONFIG_PATH \
    exec node $C/app checks Main --baseline ../../corpus/checks/baseline.tsv "$@"

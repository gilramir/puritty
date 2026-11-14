#!/bin/sh
# geng fmt over puritty's Geng sources: every .geng file outside vendored
# trees and build output, or the files and directories given. With --check
# nothing is written, and it fails listing what is not formatted (the unit
# gate, harness/units.py, runs it so). The generators run it on what they
# write, so that a table made again comes out formatted.
#
# usage: scripts/fmt.sh [--check] [PATH...]
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
R=/home/gram/prj/geng-lang
C=$R/vendor/gren-lang/compiler
check=
if [ "$1" = "--check" ]; then
    check=--check
    shift
fi
if [ $# -eq 0 ]; then
    cd "$ROOT"
    set -- $(find . -name '*.geng' -not -path '*/.gren/*' -not -path './vendor/*' \
        -not -path '*/node_modules/*' -not -path './.harness-work/*' | sort)
fi
PATH=$R/.devbox/nix/profile/default/bin:$PATH \
GENG_BIN=$C/geng GENG_CORE=$R/vendor/gren-lang/core \
    exec node $C/app fmt $check "$@"

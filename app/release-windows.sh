#!/bin/sh
# Builds puritty.exe for a release: profile-guided, as app/release.sh is for
# Linux (docs/windows.md WS29). The core's profile is trained on Linux in the
# bench over the thirteen throughput inputs (harness/bench/pgo.sh): the core
# is the same Geng on both, and MinGW's clang is the same 21.1.8 as Linux's,
# so the Linux profile is the Windows build's too. Run from puritty's devbox.
set -e
cd "$(dirname "$0")/.."
harness/bench/pgo.sh
exec app/build-windows.sh --profile-use="$PWD/harness/bench/core-bench.profile" "$@"

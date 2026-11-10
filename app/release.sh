#!/bin/sh
# Builds puritty for a release: profile-guided (docs/vt-core.md §VC54,
# geng-lang m4-profile.md §PF12). The core's profile is trained afresh in
# the bench over the thirteen throughput inputs (harness/bench/pgo.sh),
# then app/build.sh compiles with it. A development build is app/build.sh
# alone: no profile, and minutes quicker. Run from puritty's devbox.
set -e
cd "$(dirname "$0")/.."
harness/bench/pgo.sh
exec app/build.sh --profile-use="$PWD/harness/bench/core-bench.profile" "$@"

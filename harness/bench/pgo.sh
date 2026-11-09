#!/bin/sh
# Trains the profile for a profile-guided build of puritty (docs/vt-core.md
# §VC54, geng-lang m4-profile.md §PF12): core-bench built with
# --profile-generate and run once over each throughput input, which writes
# core-bench.profile/; then core-bench built again plainly, since perf.py
# holds the plain build's instructions to the record. Then
#
#     app/build.sh --profile-use=$PWD/harness/bench/core-bench.profile
#
# builds puritty with it. The training runs vt alone: the renderer and the
# X11 code are compiled as they would be without a profile.
set -e
cd "$(dirname "$0")"
INPUTS=${1:-../../.harness-work/perf/inputs}
./build.sh --profile-generate
for f in "$INPUTS"/*.txt; do
    ./core-bench "$f" >/dev/null
done
./build.sh
echo "trained on $(ls "$INPUTS"/*.txt | wc -l) inputs: $(pwd)/core-bench.profile"

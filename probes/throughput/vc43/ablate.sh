#!/bin/bash
# vt-core.md §VC43: build core-bench over a copy of vt/ with one edit from
# edits/ applied (`base` for none), and count its instructions on the
# inputs inputs.py wrote, with the dump's hash to hold the screen the same.
#   ./ablate.sh WORK INPUTS NAME      (run under systemd-run, MemoryMax=12G)
set -e
H=$(cd "$(dirname "$0")" && pwd)
V=$(cd "$H/../../.." && pwd)
W=$1; IN=$2; N=$3
D=$W/$N
rm -rf "$D"; mkdir -p "$D"
cp -r "$V/vt" "$D/vt"
cp -r "$V/harness/bench" "$D/bench"
rm -rf "$D/bench/core-bench" "$D/bench/core-bench.native-build"
sed -i "s|path = \"../../vt\"|path = \"$D/vt\"|" "$D/bench/geng.toml"
[ "$N" = base ] || (cd "$D/vt/src" && python3 -I "$H/edits/$N.py")
(cd "$D/bench" && ./build.sh >/dev/null)
row="$N"
for f in full ycr; do
  c=$(cd "$IN" && setarch -R perf stat -x, -e instructions:u "$D/bench/core-bench" $f.txt 2>&1 >/dev/null | awk -F, '/instructions/{print $1}')
  row="$row $f=$c"
done
h=$(cd "$IN" && "$D/bench/core-bench" full.txt dump | sed 's/ in [0-9]* ms//' | md5sum | cut -c1-8)
echo "$row dump=$h"

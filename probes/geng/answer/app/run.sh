#!/bin/sh
# Builds the probe three ways and runs each five times: the wait kept in
# malloc'd memory (PROBE_NAIVE), also held from a static (PROBE_ROOTED), and
# answered through a post (geng-lang D897, the default). Then the post's
# costs, from Bench.geng.
cd "$(dirname "$0")"
for flags in -DPROBE_NAIVE -DPROBE_ROOTED ""; do
    GENG_CFLAGS="$flags" ./build.sh > /dev/null 2>&1 || { echo "build failed: $flags"; exit 1; }
    echo "== ${flags:-post}"
    for i in 1 2 3 4 5; do out=$(./probe 2>&1); echo "exit $?: $(echo "$out" | head -1)"; done | sort | uniq -c
done
./build-bench.sh > /dev/null 2>&1 && ./bench && rm -f bench

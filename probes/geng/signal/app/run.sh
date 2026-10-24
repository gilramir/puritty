#!/bin/sh
# Starts the probe 20 times, sends each SIGTERM once it has printed its pid,
# and counts the outcomes. Build first with ./build.sh, or with
# GENG_CFLAGS=-DPROBE_MAIN_BLOCKS ./build.sh to block SIGTERM on every thread.
cd "$(dirname "$0")"
for i in $(seq 1 20); do
    ./probe > out.txt 2>&1 & P=$!
    for t in $(seq 1 50); do grep -q pid out.txt && break; sleep 0.02; done
    kill -TERM $P; wait $P
    echo "exit $? : $(tail -1 out.txt | sed 's/^pid [0-9]*/pid N/')"
done | sort | uniq -c
rm -f out.txt

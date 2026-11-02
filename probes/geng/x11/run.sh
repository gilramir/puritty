#!/bin/sh
# Phase 2's survey (docs/phase2-window.md §5): the x11 probe on each
# workload, the bytes of its X connection counted by xcount.py. Start Xvfb
# as :77 and the proxy first, from visiterm's devbox:
#
#   Xvfb :77 -screen 0 1920x1080x24 -nolisten tcp &
#   python3 -I probes/geng/x11/xcount.py OUT &
#
# usage: run.sh OUT INPUTS [LOOP]   OUT the proxy's file, INPUTS the throughput
# inputs, LOOP the probe's loop, read (§5's, the default) or race (§12)
set -e
cd "$(dirname "$0")/app"
OUT=$1
IN=$2
LOOP=${3:-read}
VT=$(cd ../../../../vt/src && pwd)/Vt.geng
export TERM=xterm-256color
run() {
    name=$1
    shift
    : >"$OUT"
    out=$(DISPLAY=:78 systemd-run --user --scope -q -p MemoryMax=4G "$@" 2>&1 | tail -1)
    sleep 0.5
    echo "$name | $out | X to/from server: $(cat "$OUT")"
}
run idle ./x11 $LOOP sleep 3
run tail ./x11 $LOOP python3 -I -c 'import time,sys
for i in range(500):
    print(f"{time.time():.6f} INFO worker-{i%7}: request {i} served in {i*37%1000} us"); sys.stdout.flush(); time.sleep(0.01)'
run cat-gitlog ./x11 $LOOP cat "$IN/gitlog.txt"
run htop ./x11 $LOOP timeout 10 htop
run vim-down ./x11 $LOOP vim -R -N -u NONE -i NONE -c 'syntax on' -c 'set nu' -c 'for i in range(300) | exe "normal! \<C-e>" | redraw | sleep 20m | endfor | qa!' "$VT"
run vim-up ./x11 $LOOP vim -R -N -u NONE -i NONE -c 'syntax on' -c 'set nu' -c 'normal! 400G' -c 'redraw' -c 'for i in range(300) | exe "normal! \<C-y>" | redraw | sleep 20m | endfor | qa!' "$VT"

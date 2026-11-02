#!/bin/sh
# Phase 2's survey (docs/phase2-window.md §5, §16): the x11 probe, or a
# reference terminal, on each workload, the bytes of its X connection
# counted by xcount.py. Start Xvfb as :77 and the proxy first, from
# visiterm's devbox. §16 starts Xvfb without MIT-SHM, as a server across
# ssh is: a terminal that would put its frames in shared memory then sends
# them on the wire, as it would there.
#
#   Xvfb :77 -screen 0 1920x1080x24 -nolisten tcp -extension MIT-SHM &
#   python3 -I probes/geng/x11/xcount.py OUT &
#
# usage: run.sh OUT INPUTS [DRAWER]   OUT the proxy's file, INPUTS the
# throughput inputs, DRAWER what draws: the probe's loop, read (§5's, the
# default) or race (§12), or a reference terminal (§16): xterm (Xft,
# DejaVu Sans Mono 11 as the probe), xterm-core (its default core font),
# st or alacritty, each at 160x50 from the nixpkgs devbox pins.
set -e
cd "$(dirname "$0")/app"
OUT=$1
IN=$2
DRAWER=${3:-read}
VT=$(cd ../../../../vt/src && pwd)/Vt.geng
export TERM=xterm-256color
NIXPKGS=github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600
pkg() { nix build --no-link --print-out-paths "$NIXPKGS#$1" 2>/dev/null; }
# Each terminal runs the workload with the probe's TERM, so that every one
# is sent the same bytes.
case $DRAWER in
  read|race) set -- ./x11 "$DRAWER" ;;
  xterm) set -- "$(pkg xterm)/bin/xterm" -fa 'DejaVu Sans Mono' -fs 11 -geometry 160x50 -e env TERM=$TERM ;;
  xterm-core) set -- "$(pkg xterm)/bin/xterm" -geometry 160x50 -e env TERM=$TERM ;;
  st) set -- "$(pkg st)/bin/st" -f 'DejaVu Sans Mono:size=11' -g 160x50 -e env TERM=$TERM ;;
  alacritty)
    MESA=$(pkg mesa)
    export __EGL_VENDOR_LIBRARY_FILENAMES=$MESA/share/glvnd/egl_vendor.d/50_mesa.json LIBGL_DRIVERS_PATH=$MESA/lib/dri \
      __GLX_VENDOR_LIBRARY_NAME=mesa LD_LIBRARY_PATH=$MESA/lib LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
    set -- "$(pkg alacritty)/bin/alacritty" --config-file /dev/null -o window.dimensions.columns=160 -o window.dimensions.lines=50 \
      -o 'font.normal.family="DejaVu Sans Mono"' -o font.size=11 -e env TERM=$TERM ;;
  *) echo "run.sh: no drawer $DRAWER" >&2; exit 2 ;;
esac
run() {
    name=$1
    shift
    : >"$OUT"
    out=$(DISPLAY=:78 systemd-run --user --scope -q -p MemoryMax=4G "$@" 2>&1 | tail -1)
    # A terminal's connection may close a moment after its program ends;
    # xterm's after htop took longer than half a second.
    sleep 2
    # A terminal may open more than one connection (alacritty opens five):
    # the bytes are every connection's, summed.
    echo "$name | $out | X to/from server: $(awk '{t += $1; f += $2; n++} END {print t, f, n " connection(s)"}' "$OUT")"
}
run idle "$@" sleep 3
run tail "$@" python3 -I -c 'import time,sys
for i in range(500):
    print(f"{time.time():.6f} INFO worker-{i%7}: request {i} served in {i*37%1000} us"); sys.stdout.flush(); time.sleep(0.01)'
run cat-gitlog "$@" cat "$IN/gitlog.txt"
run htop "$@" timeout 10 htop
run vim-down "$@" vim -R -N -u NONE -i NONE -c 'syntax on' -c 'set nu' -c 'for i in range(300) | exe "normal! \<C-e>" | redraw | sleep 20m | endfor | qa!' "$VT"
run vim-up "$@" vim -R -N -u NONE -i NONE -c 'syntax on' -c 'set nu' -c 'normal! 400G' -c 'redraw' -c 'for i in range(300) | exe "normal! \<C-y>" | redraw | sleep 20m | endfor | qa!' "$VT"

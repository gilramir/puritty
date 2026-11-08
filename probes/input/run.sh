#!/bin/sh
# The input survey's key-to-pixel runs (docs/phase2-window.md §14): the x11
# probe and the reference terminals, each running a program that echoes
# each byte it reads, typed at by `typo`. Start Xvfb as :77 first (the
# probe's survey display) and build typo (build.sh) and the x11 probe.
#
# usage: run.sh KEYS INTERVAL_MS [TERMINAL...]   (default: probe xterm st alacritty)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
KEYS=$1 INTERVAL=$2
shift 2
[ $# -gt 0 ] || set -- probe xterm st alacritty
NIXPKGS=github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600
pkg() { nix build --no-link --print-out-paths "$NIXPKGS#$1" 2>/dev/null; }
export DISPLAY=:77 TERM=xterm-256color
ECHO="clear; stty raw -echo; exec dd bs=1 count=$((KEYS + 1)) status=none"
for t in "$@"; do
  case $t in
    probe) (cd "$HERE/../geng/x11/app" && X11_STATS=1 ./x11 race sh -c "$ECHO") > "/tmp/typo-$t.log" 2>&1 &
           NAME=puritty-probe ;;
    xterm) "$(pkg xterm)/bin/xterm" -T typo-xterm -fa 'DejaVu Sans Mono' -fs 11 -geometry 160x50 -e sh -c "$ECHO" &
           NAME=typo-xterm ;;
    st) "$(pkg st)/bin/st" -t typo-st -f 'DejaVu Sans Mono:size=11' -g 160x50 -e sh -c "$ECHO" &
        NAME=typo-st ;;
    alacritty)
        MESA=$(pkg mesa)
        __EGL_VENDOR_LIBRARY_FILENAMES=$MESA/share/glvnd/egl_vendor.d/50_mesa.json LIBGL_DRIVERS_PATH=$MESA/lib/dri \
        __GLX_VENDOR_LIBRARY_NAME=mesa LD_LIBRARY_PATH=$MESA/lib LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
        "$(pkg alacritty)/bin/alacritty" --config-file /dev/null -T typo-alacritty \
          -o window.dimensions.columns=160 -o window.dimensions.lines=50 \
          -o 'font.normal.family="DejaVu Sans Mono"' -o font.size=11 -e sh -c "$ECHO" &
        NAME=typo-alacritty ;;
  esac
  sleep 3
  W=$(xwininfo -root -tree | grep "\"$NAME\"" | head -1 | awk '{print $1}')
  printf '%-10s ' "$t"
  "$HERE/typo" "$W" "$KEYS" "$INTERVAL" 40
  wait
done

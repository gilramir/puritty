#!/bin/sh
# Runs inside.sh in each reference terminal, one after another, on a private
# Xvfb with Mesa's llvmpipe for the two GL terminals. Every program comes from
# the nixpkgs commit visiterm's devbox.json pins. Font: DejaVu Sans Mono 11 in
# all four; each terminal otherwise keeps its own defaults.
#
# usage: terminals.sh INPUTS OUT [TERMINAL...]   (default: all four)
set -e
IN=$(realpath "$1"); OUT=$(realpath -m "$2"); shift 2
HERE=$(dirname "$(realpath "$0")")
NIXPKGS=github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600
pkg() { nix build --no-link --print-out-paths "$NIXPKGS#$1" 2>/dev/null; }
MESA=$(pkg mesa); XVFB=$(pkg xvfb)/bin/Xvfb; XDO=$(pkg xdotool)/bin/xdotool
VTEBENCH=$(pkg vtebench)/bin/vtebench
mkdir -p "$OUT" "$OUT/xdg/ghostty"; echo "# defaults" > "$OUT/xdg/ghostty/config.ghostty"

export __EGL_VENDOR_LIBRARY_FILENAMES=$MESA/share/glvnd/egl_vendor.d/50_mesa.json
export LIBGL_DRIVERS_PATH=$MESA/lib/dri __GLX_VENDOR_LIBRARY_NAME=mesa
export LD_LIBRARY_PATH=$MESA/lib LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
export FONTCONFIG_FILE=/etc/fonts/fonts.conf
# Ghostty would otherwise write a template config into ~/.config.
export XDG_CONFIG_HOME=$OUT/xdg
# No session bus: with the desktop's, Ghostty's GTK waited on portals that never
# answered until inside.sh had stopped waiting for 160x50 (geng-plan.md §1.4).
export DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent

DPY=:77
$XVFB $DPY -screen 0 2560x1440x24 -nolisten tcp > "$OUT/xvfb.log" 2>&1 &
XP=$!; trap 'kill $XP' EXIT; sleep 1
export DISPLAY=$DPY

[ $# -gt 0 ] || set -- alacritty ghostty xterm st
for t in "$@"; do
  run="${INSIDE:-$HERE/inside.sh} $OUT $t $IN $VTEBENCH"
  case $t in
    alacritty) timeout 1800 "$(pkg alacritty)/bin/alacritty" --config-file /dev/null \
                 -o window.dimensions.columns=160 -o window.dimensions.lines=50 \
                 -o 'font.normal.family="DejaVu Sans Mono"' -o font.size=11 -e $run ;;
    ghostty)   "$(pkg ghostty)/bin/ghostty" --font-family='DejaVu Sans Mono' --font-size=11 -e $run &
               G=$!
               # With no window manager its GTK window ignores a size request in
               # cells, so it is sized in pixels: 9x17 cells, header bar and padding.
               W=; for _ in $(seq 100); do
                 W=$($XDO search --onlyvisible --class ghostty 2>/dev/null | tail -1); [ -n "$W" ] && break; sleep 0.1
               done
               sleep 0.5; $XDO windowsize "$W" ${GHOSTTY_W:-1461} ${GHOSTTY_H:-912}
               ( sleep 1800; kill $G 2>/dev/null ) & K=$!
               wait $G || true; kill $K 2>/dev/null || true ;;
    xterm)     timeout 1800 "$(pkg xterm)/bin/xterm" -fa 'DejaVu Sans Mono' -fs 11 -geometry 160x50 -e $run ;;
    st)        timeout 1800 "$(pkg st)/bin/st" -f 'DejaVu Sans Mono:size=11' -g 160x50 -e $run ;;
  esac > "$OUT/$t.log" 2>&1 || true
  cat "$OUT/$t.size" 2>/dev/null || echo "$t: no result"
done

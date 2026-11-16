#!/bin/sh
# What a program gets when text is pasted into it (docs/tmux.md TM94,
# TM95): puritty in an Xvfb, FILE put on the clipboard with xclip and
# pasted with Ctrl+Shift+V into rec.py, which records the bytes it reads;
# without tmux (plain), through a tmux client (tmux) or by tmux -CC (cc).
# BRACKETS 1 has rec.py turn bracketed paste on, as a newer nano does; 0
# not, as an older one. Prints the bytes read; they are left in
# WORK/got-MODE.bin.
#
#   bench/tmux/paste/run.sh PURITTY MODE FILE [BRACKETS]
#   bench/tmux/paste/run.sh app/puritty cc lines.txt 0
#
# Run from puritty's devbox (Xvfb); TMUX_BIN picks another tmux.
TM=${TMUX_BIN:-tmux}
P=$(realpath "$1"); M=$2; F=$(realpath "$3"); B=${4:-1}
D=$(cd "$(dirname "$0")" && pwd)
W=${WORK:-$D/../../../.harness-work/paste}
mkdir -p "$W/home"
XDO=${XDOTOOL:-$(command -v xdotool || ls /nix/store/*-xdotool-*/bin/xdotool 2>/dev/null | head -1)}
OUT=$W/got-$M.bin
rm -f "$OUT"; $TM -L paste kill-server 2>/dev/null
Xvfb :79 -screen 0 1200x800x24 >/dev/null 2>&1 & X=$!
sleep 1
DISPLAY=:79 xclip -selection clipboard -i < "$F"
REC="python3 $D/rec.py $OUT $B"
case $M in
plain) CMD="$REC" ;;
tmux) $TM -L paste -f /dev/null new-session -d -s main -x 100 -y 30 "$REC"; CMD="$TM -L paste attach -t main" ;;
cc) $TM -L paste -f /dev/null new-session -d -s main -x 100 -y 30 "$REC"; CMD="$TM -L paste -CC attach -t main" ;;
esac
DISPLAY=:79 PURITTY_NO_XIM=1 HOME=$W/home "$P" -- sh -c "$CMD" 2>/dev/null & PP=$!
sleep 3
DISPLAY=:79 "$XDO" key ctrl+shift+v
sleep 5
kill $PP 2>/dev/null; wait $PP 2>/dev/null; $TM -L paste kill-server 2>/dev/null; kill $X
printf '%s: ' "$M"; od -c "$OUT" | head -6

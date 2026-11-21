#!/bin/sh
# A pane that prints a burst, as an inline app (Claude Code's
# non-fullscreen mode) does when it comes back from Ctrl-Z and prints its
# whole transcript again, drawn by puritty under tmux -CC (docs/tmux.md
# TM90). puritty runs in an Xvfb attached to a tmux running standin.py N;
# with TRIGGER 1 a key makes the stand-in clear and reprint everything.
# Prints the frames puritty drew (X11_STATS); the diagnostic log, with each
# read of tmux's output timed, is left in WORK/home/.local/state/puritty/logs.
#
#   bench/tmux/burst/run.sh PURITTY N TRIGGER [WAIT]
#   bench/tmux/burst/run.sh app/puritty 5000 1 6
#
# Run from puritty's devbox (Xvfb); TMUX_BIN picks another tmux.
P=$(realpath "$1"); N=$2; T=$3; W=${4:-6}
D=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$D/../../../.harness-work/burst}
mkdir -p "$WORK"
H=$WORK/home; rm -rf "$H"; mkdir -p "$H/.config/puritty"
printf '[debug]\nlog = true\n' > "$H/.config/puritty/config.toml"
TM=${TMUX_BIN:-tmux}
$TM -L burst kill-server 2>/dev/null
$TM -L burst -f /dev/null new-session -d -s main -x 100 -y 30 "python3 $D/standin.py $N"
Xvfb :77 -screen 0 1200x800x24 >/dev/null 2>&1 & X=$!
sleep 1
DISPLAY=:77 X11_STATS=1 PURITTY_NO_XIM=1 HOME=$H "$P" -- $TM -L burst -CC attach -t main 2>"$WORK/stats.txt" & PP=$!
sleep 4
[ "$T" = 1 ] && $TM -L burst send-keys -t main x
sleep "$W"
$TM -L burst kill-server
wait $PP
kill $X
grep -o 'frames [0-9]*' "$WORK/stats.txt" | head -1

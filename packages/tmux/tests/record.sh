#!/bin/sh
# The recorded control-mode sessions the tests read (docs/tmux.md TM13),
# made with devbox's tmux 3.8 and bench/tmux/record.py; run from puritty's
# devbox. Each is the raw bytes a terminal got from `tmux -CC`.
set -e
cd "$(dirname "$0")"
R="$PWD/../../../bench/tmux/record.py"
export BARE=1 TMUX_BIN="$(command -v tmux)" TMUX_CONF="$PWD/data/tmux.conf"
cd data
python3 $R floating.raw \
  'split-window -h' \
  'refresh-client -f new-layouts' \
  'list-windows -F "W #{window_id} #{window_layout}"' \
  'new-pane' \
  'new-pane -O -x 30 -y 8' \
  'list-panes -F "P #{pane_id} #{pane_floating_flag} #{pane_modal_flag}"' \
  'refresh-client -f !new-layouts' \
  'list-windows -F "W #{window_id} #{window_layout}"'
python3 $R output.raw \
  "send-keys -t '%0' -l 'printf \"A\\\\033[1mB\\\\\\\\C\\\\303\\\\251\\\\301\\\\326\\\\n\"'" \
  "send-keys -t '%0' Enter" \
  'refresh-client -f pause-after=1' \
  "send-keys -t '%0' -l 'echo after'" \
  "send-keys -t '%0' Enter" \
  'display-message -p "a ; b"'

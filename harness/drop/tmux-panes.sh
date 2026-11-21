#!/bin/sh
# Run as the ssh tab's command by harness/drop.py's tmux cases (docs/sftp.md
# FT23): tmux -CC on a server of its own, with three panes, each a way a
# pane's folder is known: a shell in "left dir"; a shell started in
# "started here" that said by OSC 7 it is in "osc dir"; and a program whose
# name is ssh, started in "ssh dir", whose folder tmux can't see past.
D=$1
mkdir -p "$D/left dir" "$D/osc dir" "$D/started here" "$D/ssh dir"
osc=$(printf '%s' "$D/osc dir" | sed 's/ /%20/g')
exec tmux -L puritty-drop -f /dev/null -CC new-session -x 80 -y 24 -c "$D/left dir" "exec sh" \; \
    split-window -h -c "$D/started here" "printf '\\033]7;file://%s%s\\007' \"\$(hostname)\" '$osc'; exec sleep 600" \; \
    split-window -v -c "$D/ssh dir" "exec bash -c 'exec -a ssh sleep 600'"

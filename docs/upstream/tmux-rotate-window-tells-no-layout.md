# `rotate-window` moves the panes and tells control clients no layout change

**Repository:** `tmux/tmux`

**Found against:** every release from 2.7 to 3.8 (all built and recorded,
`corpus/tmux/*/notices.txt`); the code is `cmd-rotate-window.c` in 3.8.
Found by puritty's puppet harness (`docs/tmux-checks.md` TK12). Not yet
filed (Gilbert decides).

## Summary

`rotate-window` (`prefix C-o`, `prefix M-o`) moves every pane of the window
into the next one's cell, but a control client (`tmux -C`/`-CC`) is told
only `%window-pane-changed`, never `%layout-change`: it cannot learn where
the panes now are without asking. Every other command that moves panes
tells it (`swap-pane`, `select-layout`, `join-pane`, `break-pane`,
`resize-pane`, zoom).

| command, on a window of three panes | told to a control client |
|---|---|
| `swap-pane -D` | `%layout-change @0 …` (3.0 on; 2.x told nothing) |
| `select-layout tiled` | `%layout-change @0 …` |
| `rotate-window` | `%window-pane-changed @0 %9` only |

## Reproduction

```sh
tmux -f /dev/null new-session -d -s main -x 100 -y 30
tmux split-window -d -t main; tmux split-window -d -h -t main
tmux -C attach -t main &        # a control client, listening
tmux rotate-window -t main      # it reads only %window-pane-changed
```

`window_visible_layout` asked afterwards shows each pane id in another
cell than the last `%layout-change` said.

## Fix

`cmd_rotate_window_exec` rearranges `layout_cell`s itself and ends with
`redraw_invalidate_scene` and `server_redraw_window`, but, unlike
`cmd-select-layout.c:147` and `cmd-join-pane.c`, never fires the event.
Adding

```c
	events_fire_window("window-layout-changed", w);
```

before its `return (CMD_RETURN_NORMAL)` would tell control clients as
every other layout change does.

## In puritty

Since tmux cannot be relied on to tell every change to a window's panes,
puritty asks the window again after each of tmux's bindings runs (its
`send-keys -K` block, or the binding's command it sends before 3.4) and
after each command the user runs at its prompt or from a menu (TM75).

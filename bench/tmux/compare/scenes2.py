"""Second round: scenes whose first try was spoiled by timing (messages
gone before the shot), by Escape (tmux's emacs prompt does not cancel on
Escape; C-c is used instead), or by mouse targets on status-left."""

from scenes import FILL, THREE, P, sk

CUR = "#{pane_id} mode=#{pane_mode} cur=#{copy_cursor_x},#{copy_cursor_y} sel=#{selection_present} scroll=#{scroll_position}"
LAYOUT = "#{window_layout} active=#{pane_id}"

SCENES = [
    dict(name="messages2", conf="set -g display-time 6000\n", setup=FILL,
         steps=[("keys", P, ":"), ("type", "display-message 'hello from tmux'"), ("keys", "Enter"),
                ("shot", "message", 0.6), ("keys", "C-c"), ("sleep", 0.3),
                ("keys", P, ":"), ("type", "no-such-command"), ("keys", "Enter"), ("shot", "error", 0.6),
                ("keys", "C-c"), ("keys", P, "i"), ("shot", "prefix-i", 0.6)]),
    dict(name="messages-styled", conf="set -g display-time 6000\nset -g message-style bg=red,fg=white\n"
         "set -g message-command-style bg=blue,fg=yellow\n", setup=FILL,
         steps=[("keys", P, ":"), ("shot", "prompt", 0.6), ("keys", "C-c"), ("keys", P, "i"),
                ("shot", "message", 0.6)]),
    dict(name="prompt-vi", conf="set -g status-keys vi\n", setup=FILL,
         steps=[("keys", P, ":"), ("type", "display-message abc"), ("keys", "Escape"), ("shot", "vi-normal"),
                ("keys", "0"), ("keys", "C-c")]),
    dict(name="menus-keys2", setup=THREE, steps=[("keys", P, "<"), ("shot", "window-menu"), ("keys", "C-c"), ("sleep", 0.4),
                                                ("keys", P, ">"), ("shot", "pane-menu"), ("keys", "C-c")]),
    dict(name="menus-mouse2", conf="set -g mouse on\n", setup=[sk("main:0", "echo wordy")],
         steps=[("sleep", 0.5), ("rpress", 8, 29), ("shot", "window-status-menu"), ("keys", "C-c"), ("sleep", 0.4),
                ("rpress", 1, 29), ("shot", "status-left-menu"), ("keys", "C-c"), ("sleep", 0.4),
                ("rpress", 2, 1), ("shot", "pane-menu-word"), ("keys", "C-c")]),
    dict(name="mouse-status2", conf="set -g mouse on\n",
         setup=[("new-window", "-t", "main", "-n", "two"), ("new-window", "-t", "main", "-n", "three")],
         steps=[("q", "win=#{window_index}"), ("click", 8, 29), ("q", "win=#{window_index}"), ("shot", "clicked-0"),
                ("drag", 8, 29, 24, 29), ("q", "#{W:#{window_index}=#{window_name} }"), ("shot", "dragged"),
                ("q", "win=#{window_index}")]),
    dict(name="mouse-border2", conf="set -g mouse on\n", setup=THREE,
         steps=[("q", LAYOUT), ("dragstart", 50, 10, 30, 10), ("shot", "mid-drag"), ("dragend",), ("q", LAYOUT),
                ("shot", "dragged")]),
    dict(name="mouse-copy2", conf="set -g mouse on\n", setup=FILL,
         steps=[("dragstart", 2, 20, 10, 22), ("q", CUR), ("shot", "mid-drag"), ("dragend",), ("q", CUR),
                ("q", "buffer=#{buffer_sample}"), ("shot", "released")]),
    dict(name="copy-emacs2", setup=FILL,
         steps=[("keys", P, "["), ("keys", "Up", "Up", "Up"), ("q", CUR), ("keys", "C-r"), ("type", "3"),
                ("q", CUR), ("shot", "incremental"), ("keys", "Enter"), ("q", CUR), ("shot", "found"),
                ("keys", "C-Space"), ("keys", "Up", "Up", "C-e"), ("q", CUR), ("shot", "selection"),
                ("keys", "M-w"), ("q", "buffer=#{buffer_sample}")]),
    dict(name="copy-emacs3", setup=FILL,
         steps=[("keys", P, "["), ("keys", "C-r"), ("type", "3"), ("q", CUR), ("keys", "C-r"), ("q", CUR),
                ("keys", "C-r"), ("q", CUR), ("keys", "BSpace"), ("q", CUR), ("type", "5"), ("q", CUR),
                ("keys", "Enter"), ("q", CUR), ("keys", "C-r"), ("keys", "C-r"), ("q", CUR), ("shot", "recalled"),
                ("keys", "C-r"), ("q", CUR), ("keys", "C-s"), ("q", CUR), ("keys", "C-c"), ("q", CUR)]),
    dict(name="status-overflow-click", conf="set -g mouse on\n",
         setup=[("new-window", "-t", "main", "-n", f"a-rather-long-window-name-{i}") for i in range(1, 12)]
               + [("select-window", "-t", "main:6")],
         steps=[("q", "win=#{window_index}"), ("click", 62, 29), ("q", "win=#{window_index}"), ("shot", "clicked-7"),
                ("click", 7, 29), ("q", "win=#{window_index}"), ("shot", "clicked-left-marker")]),
    dict(name="pane-scrollbars2", conf="set -g pane-scrollbars on\n",
         setup=THREE + [sk("main:0.0", "seq 1 100"), ("select-pane", "-t", "main:0.0")],
         steps=[("keys", P, "["), ("keys", "PPage"), ("q", CUR), ("shot", "copy-scrolled")]),
    dict(name="tree-keys", setup=THREE + [("new-window", "-t", "main", "-n", "second"),
                                          ("new-session", "-d", "-s", "other", "-x", "100", "-y", "29")],
         steps=[("keys", P, "s"), ("keys", "Down"), ("keys", "t"), ("shot", "tagged"), ("keys", "x"),
                ("shot", "x-prompt"), ("keys", "n"), ("keys", "f"), ("shot", "f-prompt"), ("type", "#{==:#{session_name},other}"),
                ("keys", "Enter"), ("shot", "filtered"), ("keys", "C-c")]),
    dict(name="floating-pane", setup=FILL + [("new-pane", "-t", "main", "-x", "40", "-y", "8"),
                                              sk("main:0.1", "echo floating")],
         steps=[("shot", "floating")]),
    dict(name="window-size-latest", setup=FILL, steps=[("keys", P, "z"), ("shot", "zoom-single")]),
]

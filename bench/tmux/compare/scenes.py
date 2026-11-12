"""The scenes: tmux commands to set the server up (run identically on the
plain server and the -CC one), then steps applied to both sides.
Steps: ("keys", tmux-key...), ("type", text), ("cli", tmux-args...),
("click"|"rclick"|"rpress", col, row), ("drag", c0, r0, c1, r1),
("sleep", s), ("shot", label[, wait])."""

P = "C-b"


def sk(target, text):
    return ("send-keys", "-t", target, text, "Enter")


FILL = [sk("main:0", "seq 1 40; echo 'hello world alpha beta'")]

THREE = [("split-window", "-h", "-t", "main:0"), ("split-window", "-v", "-t", "main:0.1"),
         sk("main:0.0", "echo left"), sk("main:0.1", "echo top right"), sk("main:0.2", "echo bottom right")]

FOUR = [("split-window", "-h", "-t", "main:0"), ("split-window", "-v", "-t", "main:0.0"),
        ("split-window", "-v", "-t", "main:0.2"), ("select-pane", "-t", "main:0.0")]

SCENES = [
    # --- status line
    dict(name="status-flags", setup=[
        ("new-window", "-t", "main", "-n", "zoomed"), ("split-window", "-t", "main:zoomed"),
        ("resize-pane", "-Z", "-t", "main:zoomed"),
        ("new-window", "-t", "main", "-n", "belly"),
        ("new-window", "-t", "main", "-n", "busy"),
        ("new-window", "-t", "main", "-n", "marked"), ("select-pane", "-m", "-t", "main:marked"),
        ("new-window", "-t", "main", "-n", "cur"),
        ("select-window", "-t", "main:first"), ("select-window", "-t", "main:cur"),
        ("sleep", 1.0), ("set", "-g", "monitor-activity", "on"),
        sk("main:belly", "sleep 3; printf '\\a'"), sk("main:busy", "sleep 3; echo activity"),
    ], steps=[("sleep", 3.5), ("shot", "flags")]),
    dict(name="status-overflow", setup=[("new-window", "-t", "main", "-n", f"a-rather-long-window-name-{i}")
                                         for i in range(1, 12)] + [("select-window", "-t", "main:6")],
         steps=[("shot", "middle"), ("cli", "select-window", "-t", "main:11"), ("shot", "last")]),
    dict(name="status-custom", conf="set -g status-style bg=blue,fg=white\nset -g status-left '#[bg=red] [#S] #[default] '\n"
         "set -g window-status-current-style fg=black,bg=yellow,bold\nset -g status-justify centre\n"
         "set -g status-right '#[fg=green]R#[default] %%H:%%M'\n",
         setup=[("new-window", "-t", "main", "-n", "two")], steps=[("shot", "centre")]),
    dict(name="status-top-2lines", conf="set -g status-position top\nset -g status 2\n",
         setup=FILL, steps=[("shot", "top")]),
    dict(name="status-off", conf="set -g status off\n", setup=FILL, steps=[("shot", "off")]),
    # --- borders
    dict(name="borders-2", setup=[("split-window", "-h", "-t", "main:0"), sk("main:0.1", "echo right")],
         steps=[("shot", "two")]),
    dict(name="borders-3", setup=THREE, steps=[("shot", "three")]),
    dict(name="borders-4", setup=FOUR, steps=[("shot", "four")]),
    dict(name="border-status-top", conf="set -g pane-border-status top\nset -g pane-border-format ' #{pane_index}: #{pane_current_command} '\n",
         setup=THREE, steps=[("shot", "top")]),
    dict(name="border-status-bottom", conf="set -g pane-border-status bottom\n", setup=THREE, steps=[("shot", "bottom")]),
    dict(name="border-indicators-arrows", conf="set -g pane-border-indicators arrows\n", setup=THREE,
         steps=[("shot", "arrows")]),
    dict(name="border-indicators-both", conf="set -g pane-border-indicators both\n", setup=THREE,
         steps=[("shot", "both")]),
    dict(name="border-lines-double", conf="set -g pane-border-lines double\n", setup=THREE, steps=[("shot", "double")]),
    dict(name="border-lines-heavy", conf="set -g pane-border-lines heavy\n", setup=THREE, steps=[("shot", "heavy")]),
    dict(name="border-lines-simple", conf="set -g pane-border-lines simple\n", setup=THREE, steps=[("shot", "simple")]),
    dict(name="border-lines-number", conf="set -g pane-border-lines number\n", setup=THREE, steps=[("shot", "number")]),
    dict(name="border-lines-spaces", conf="set -g pane-border-lines spaces\n", setup=THREE, steps=[("shot", "spaces")]),
    dict(name="border-styles", conf="set -g pane-border-style fg=red\nset -g pane-active-border-style fg=cyan,bg=blue\n",
         setup=THREE, steps=[("shot", "styled")]),
    dict(name="window-styles", conf="set -g window-style bg=colour236\nset -g window-active-style bg=colour17\n",
         setup=THREE, steps=[("shot", "bg")]),
    dict(name="zoomed", setup=THREE + [("resize-pane", "-Z", "-t", "main:0.1")], steps=[("shot", "zoom")]),
    dict(name="marked", setup=THREE + [("select-pane", "-m", "-t", "main:0.0")], steps=[("shot", "marked")]),
    dict(name="pane-scrollbars", conf="set -g pane-scrollbars on\n", setup=THREE + [sk("main:0.0", "seq 1 100")],
         steps=[("shot", "on"), ("keys", P, "["), ("keys", "PPage"), ("shot", "copy-scrolled")]),
    dict(name="remain-on-exit", conf="set -g remain-on-exit on\n",
         setup=[("split-window", "-h", "-t", "main:0", "sh -c 'echo bye; exit 3'")], steps=[("shot", "dead", 1.5)]),
    dict(name="sync-panes", setup=THREE + [("set", "-w", "-t", "main:0", "synchronize-panes", "on")],
         steps=[("type", "echo synced"), ("keys", "Enter"), ("shot", "sync")]),
    # --- tree and choosers
    dict(name="choose-tree-s", setup=THREE + [("new-window", "-t", "main", "-n", "second"),
                                               ("new-session", "-d", "-s", "other", "-x", "100", "-y", "29"),
                                               sk("other:0", "echo in other")],
         steps=[("keys", P, "s"), ("shot", "s"), ("keys", "Right"), ("shot", "expanded"), ("keys", "Down"),
                ("shot", "window-row"), ("keys", "Right"), ("shot", "panes-level"), ("keys", "Escape"),
                ("keys", P, "w"), ("shot", "w"), ("keys", "v"), ("shot", "w-v-preview"),
                ("keys", "t"), ("shot", "tagged"), ("keys", "x"), ("shot", "kill-prompt"), ("keys", "n"),
                ("keys", "f"), ("shot", "filter-prompt"), ("type", "sec"), ("keys", "Enter"), ("shot", "filtered"),
                ("keys", "O"), ("shot", "sorted")]),
    dict(name="choose-buffer", setup=FILL + [("set-buffer", "first buffer text"), ("set-buffer", "second buffer text")],
         steps=[("keys", P, "="), ("shot", "buffers")]),
    dict(name="choose-client", setup=FILL, steps=[("keys", P, "D"), ("shot", "clients")]),
    dict(name="customize", setup=FILL, steps=[("keys", P, "C"), ("shot", "customize"), ("keys", "Down", "Down", "Right"),
                                              ("shot", "customize-open")]),
    dict(name="display-panes", setup=THREE, steps=[("keys", P, "q"), ("shot", "q", 0.4)]),
    dict(name="clock", setup=FILL, steps=[("keys", P, "t"), ("shot", "clock")]),
    # --- copy mode
    dict(name="copy-emacs", setup=FILL, steps=[("keys", P, "["), ("shot", "entered"), ("keys", "Up", "Up", "Up"),
                                              ("keys", "C-r"), ("shot", "search-prompt"), ("type", "1"),
                                              ("shot", "search-typed"), ("keys", "Enter"), ("shot", "search-found"),
                                              ("keys", "C-Space", "Up", "Up", "M-f"), ("shot", "selection"),
                                              ("keys", "q")]),
    dict(name="copy-vi", conf="setw -g mode-keys vi\n", setup=FILL,
         steps=[("keys", P, "["), ("keys", "?"), ("shot", "search-prompt"), ("type", "alpha"), ("keys", "Enter"),
                ("shot", "found"), ("keys", "v", "w", "w"), ("shot", "selection"), ("keys", "V"), ("shot", "line-sel"),
                ("keys", "C-v"), ("shot", "rect"), ("keys", "Escape"), ("keys", ":"), ("shot", "goto-line"),
                ("keys", "Escape"), ("keys", "q")]),
    dict(name="copy-wrapped-search", conf="setw -g mode-keys vi\n", setup=[sk("main:0", "for i in 1 2 3 4 5 6; do echo match$i; echo other; done")],
         steps=[("keys", P, "["), ("keys", "?"), ("type", "match"), ("keys", "Enter"), ("shot", "highlights"),
                ("keys", "n"), ("shot", "next")]),
    # --- prompts and messages
    dict(name="command-prompt", setup=FILL, steps=[("keys", P, ":"), ("shot", "empty"), ("type", "split-w"),
                                                  ("keys", "Tab"), ("shot", "completed"), ("keys", "C-u"),
                                                  ("type", "sel"), ("keys", "Tab"), ("shot", "ambiguous"),
                                                  ("keys", "Escape"),
                                                  ("keys", P, ":"), ("type", "display-message one"), ("keys", "Enter"),
                                                  ("keys", P, ":"), ("keys", "Up"), ("shot", "history")]),
    dict(name="confirm", setup=THREE, steps=[("keys", P, "x"), ("shot", "kill-pane"), ("keys", "n"),
                                            ("keys", P, "&"), ("shot", "kill-window"), ("keys", "n")]),
    dict(name="rename-prompts", setup=FILL, steps=[("keys", P, ","), ("shot", "rename-window"), ("keys", "Escape"),
                                                  ("keys", P, "$"), ("shot", "rename-session"), ("keys", "Escape"),
                                                  ("keys", P, "."), ("shot", "move-window"), ("keys", "Escape"),
                                                  ("keys", P, "'"), ("shot", "index"), ("keys", "Escape"),
                                                  ("keys", P, "f"), ("shot", "find-window"), ("keys", "Escape")]),
    dict(name="messages", setup=FILL, steps=[("keys", P, ":"), ("type", "display-message 'hello from tmux'"),
                                            ("keys", "Enter"), ("shot", "message", 0.5),
                                            ("keys", P, ":"), ("type", "no-such-command"), ("keys", "Enter"),
                                            ("shot", "error", 0.5),
                                            ("keys", P, "i"), ("shot", "prefix-i", 0.5),
                                            ("keys", P, "~"), ("shot", "show-messages")]),
    dict(name="custom-message-style", conf="set -g message-style bg=red,fg=white\nset -g message-command-style bg=blue\n",
         setup=FILL, steps=[("keys", P, ":"), ("shot", "prompt-styled"), ("keys", "Escape"),
                            ("keys", P, "i"), ("shot", "message-styled", 0.5)]),
    dict(name="list-keys", setup=FILL, steps=[("keys", P, "?"), ("shot", "list-keys"), ("keys", "NPage"),
                                             ("shot", "paged")]),
    # --- menus and popups
    dict(name="menus-keys", setup=THREE, steps=[("keys", P, "<"), ("shot", "window-menu"), ("keys", "Escape"),
                                               ("keys", P, ">"), ("shot", "pane-menu"), ("keys", "Escape")]),
    dict(name="menus-mouse", conf="set -g mouse on\n", setup=THREE + [sk("main:0.0", "echo wordy")],
         steps=[("rclick", 5, 3), ("shot", "pane-menu"), ("keys", "Escape"),
                ("rclick", 3, 29), ("shot", "window-status-menu"), ("keys", "Escape"),
                ("rclick", 0, 29), ("shot", "status-left-menu"), ("keys", "Escape"),
                ("rclick", 97, 29), ("shot", "status-right-menu"), ("keys", "Escape")]),
    dict(name="popup", setup=FILL, steps=[("keys", P, ":"), ("type", "display-popup -T title 'echo inside popup; sleep 20'"),
                                         ("keys", "Enter"), ("shot", "popup", 1.5), ("keys", "C-c")]),
    dict(name="popup-E", setup=FILL, steps=[("keys", P, ":"), ("type", "display-popup -E -w 40 -h 10 'echo hi; sleep 20'"),
                                           ("keys", "Enter"), ("shot", "popup-E", 1.5)]),
    # --- mouse
    dict(name="mouse-status", conf="set -g mouse on\n",
         setup=[("new-window", "-t", "main", "-n", "two"), ("new-window", "-t", "main", "-n", "three")],
         steps=[("click", 2, 29), ("shot", "clicked-first"), ("drag", 2, 29, 20, 29), ("shot", "dragged")]),
    dict(name="mouse-border", conf="set -g mouse on\n", setup=THREE,
         steps=[("drag", 49, 10, 30, 10), ("shot", "dragged")]),
    dict(name="mouse-copy", conf="set -g mouse on\n", setup=FILL,
         steps=[("drag", 2, 20, 10, 22), ("shot", "drag-select", 0.3)]),
]

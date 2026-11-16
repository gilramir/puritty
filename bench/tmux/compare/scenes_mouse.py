"""The mouse in tmux's modes (docs/tmux.md TM86): a press on a row of the
tree, choose-buffer's list and customize-mode, and on a window in the
tree's preview, each shot beside a plain client given the same press."""

from scenes import P

WINDOWS = [("new-window", "-t", "main", "-n", "two"), ("new-window", "-t", "main", "-n", "three"),
           ("select-window", "-t", "main:0")]

SCENES = [
    dict(name="mouse-tree", conf="set -g mouse on\n", setup=WINDOWS,
         steps=[("keys", P, "w"), ("shot", "open"), ("click", 12, 2), ("shot", "row-2"),
                ("click", 12, 0), ("shot", "session-row"), ("click", 66, 21), ("shot", "preview-pressed"),
                ("q", "win=#{window_index}")]),
    dict(name="mouse-buffers", conf="set -g mouse on\n",
         setup=[("set-buffer", "zero"), ("set-buffer", "one"), ("set-buffer", "two")],
         steps=[("keys", P, "="), ("shot", "open"), ("click", 12, 2), ("shot", "row-2"), ("click", 12, 1),
                ("shot", "row-1")]),
    dict(name="mouse-customize", conf="set -g mouse on\n",
         steps=[("keys", P, ":"), ("type", "customize-mode"), ("keys", "Enter"), ("shot", "open"),
                ("click", 12, 3), ("shot", "row-3"), ("click", 12, 6), ("shot", "row-6")]),
]

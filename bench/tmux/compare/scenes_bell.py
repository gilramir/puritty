"""A pane's bell under tmux's options (docs/tmux.md TM99): visual-bell on,
a bell in the current window and one in another, each shot beside a plain
client given the same."""

from scenes import P, sk

SCENES = [
    dict(name="bell-visual-current", conf="set -g visual-bell on\nset -g display-time 8000\n",
         setup=[sk("main:0", "sleep 2; printf '\\a'")],
         steps=[("sleep", 3), ("shot", "current", 0.3)]),
    dict(name="bell-visual-other", conf="set -g visual-bell on\nset -g display-time 8000\n",
         setup=[("new-window", "-d", "-t", "main", "-n", "two", "sh -c 'sleep 3; printf \"\\\\a\"; sleep 60'")],
         steps=[("sleep", 4), ("shot", "other", 0.3)]),
]

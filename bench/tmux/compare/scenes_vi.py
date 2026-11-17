"""status-keys vi at tmux's prompt (docs/tmux.md TM100): edits in command
mode, a vi word motion, and command mode's style, each shot beside a plain
client given the same keys."""

from scenes import P

VI = "set -g status-keys vi\n"

SCENES = [
    dict(name="vi-edit", conf=VI, steps=[("keys", P, ":"), ("type", "hello world"), ("keys", "Escape"), ("sleep", 1), ("keys", "0"),
                                       ("keys", "x"), ("keys", "A"), ("type", "!"), ("shot", "edited"), ("keys", "C-c")]),
    dict(name="vi-word", conf=VI, steps=[("keys", P, ":"), ("type", "abc def-ghi"), ("keys", "Escape"), ("sleep", 1), ("keys", "0"),
                                       ("keys", "w"), ("keys", "w"), ("keys", "x"), ("shot", "word"), ("keys", "C-c")]),
    dict(name="vi-command-mode", conf=VI, steps=[("keys", P, ":"), ("type", "abc"), ("keys", "Escape"), ("sleep", 1), ("shot", "command")]),
]

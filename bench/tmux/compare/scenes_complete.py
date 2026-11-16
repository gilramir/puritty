"""Tab at tmux's prompt (docs/tmux.md TM96): a command's name, 3.8's list of
what it cannot choose between, an option's name past the first word, each
shot beside a plain client given the same keys."""

from scenes import P

SCENES = [
    dict(name="complete-spl", steps=[("keys", P, ":"), ("type", "spl"), ("keys", "Tab"), ("shot", "spl"), ("keys", "C-c")]),
    dict(name="complete-select", steps=[("keys", P, ":"), ("type", "select-"), ("keys", "Tab"), ("shot", "select"), ("keys", "C-c")]),
    dict(name="complete-option", steps=[("keys", P, ":"), ("type", "set -g status-k"), ("keys", "Tab"), ("shot", "option"), ("keys", "C-c")]),
]

"""A pane killed while in copy mode (docs/tmux.md TM103): what puritty
asks of tmux afterwards, as other panes enter and leave copy mode. Read
from the diagnostic log; the shots are beside a plain client."""

from scenes import FILL, P

SCENES = [
    dict(name="dead-copy", conf="set -g mode-keys vi\n", setup=FILL + [("split-window", "-h", "-t", "main:0")],
         steps=[("cli", "copy-mode", "-t", "main:0.1"), ("sleep", 0.8), ("cli", "kill-pane", "-t", "main:0.1"), ("sleep", 0.8),
                ("keys", P, "["), ("sleep", 0.8), ("keys", "q"), ("sleep", 0.8),
                ("keys", P, "["), ("sleep", 0.8), ("keys", "q"), ("sleep", 0.8), ("shot", "after")]),
]

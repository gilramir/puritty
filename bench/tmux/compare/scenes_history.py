"""tmux's prompt history at puritty's prompt (docs/tmux.md TM89): a server
given a history file (one command, one search), then Up at `:` and at a
`-T search` prompt, shot beside a plain client given the same keys.
HISTORY is the file, written by the caller:
    printf 'command:set -g @seeded 1\\nsearch:needle\\n' > FILE"""

import os

from scenes import P

HISTORY = os.environ.get("PURITTY_HISTORY_FILE", "/tmp/puritty-history.txt")

SCENES = [
    dict(name="prompt-history", conf=f"set -g history-file {HISTORY}\n",
         steps=[("keys", P, ":"), ("keys", "Up"), ("shot", "command-up"), ("keys", "C-c"), ("sleep", 0.4),
                ("keys", P, ":"), ("type", "command-prompt -T search -p find 'display-message %%'"), ("keys", "Enter"),
                ("keys", "Up"), ("shot", "search-up"), ("keys", "C-c")]),
]

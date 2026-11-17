"""Another session shown whose pane is already in copy mode, scrolled
back (docs/tmux.md TM102): puritty asks the panes' modes when it
attaches, for its own session only."""

from scenes import FILL, P, sk

MODE = "#{pane_id} mode=#{pane_mode} scroll=#{scroll_position}"

OTHER = [("new-session", "-d", "-s", "other", "-x", "100", "-y", "29"),
         sk("other:0", "seq 101 160; echo 'other session'"), ("sleep", 0.5),
         ("copy-mode", "-t", "other:0"), ("send-keys", "-t", "other:0", "-X", "page-up")]

SCENES = [
    dict(name="session-copy", conf="set -g mode-keys vi\n", setup=FILL + OTHER,
         steps=[("keys", P, ":"), ("type", "switch-client -t other"), ("keys", "Enter"), ("sleep", 1.0),
                ("q", MODE), ("shot", "switched"), ("keys", "q"), ("sleep", 0.8), ("q", MODE), ("shot", "after-q")]),
]

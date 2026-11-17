"""A key that leaves copy mode (docs/tmux.md TM101): prefix [, a motion,
Enter; the pane's mode and what is drawn, beside a plain client. puritty
kept the scrolled view after tmux left copy mode, until output came."""

from scenes import FILL, P

MODE = "#{pane_id} mode=#{pane_mode}"

SCENES = [
    dict(name="copy-enter-vi", conf="set -g mode-keys vi\n", setup=FILL,
         steps=[("keys", P, "["), ("sleep", 0.5), ("keys", "b"), ("sleep", 0.5), ("keys", "Enter"), ("sleep", 0.8),
                ("q", MODE), ("shot", "after-enter")]),
    dict(name="copy-enter-emacs", conf="set -g mode-keys emacs\n", setup=FILL,
         steps=[("keys", P, "["), ("sleep", 0.5), ("keys", "M-b"), ("sleep", 0.5), ("keys", "Enter"), ("sleep", 0.8),
                ("q", MODE), ("shot", "after-enter")]),
    # prefix [, then the prefix itself (C-b), then Enter: tmux finds no
    # prefix binding for Enter and tries it again in copy mode's table
    dict(name="copy-prefix-enter", conf="set -g mode-keys vi\n", setup=FILL,
         steps=[("keys", P, "["), ("sleep", 0.5), ("keys", "C-b"), ("sleep", 0.5), ("keys", "Enter"), ("sleep", 0.8),
                ("q", MODE), ("shot", "after-enter")]),
    # the prefix C-a: in copy mode C-b is vi's page-up, then Enter
    dict(name="copy-pageup-enter", conf="set -g mode-keys vi\nset -g prefix C-a\n", setup=FILL,
         steps=[("keys", "C-a", "["), ("sleep", 0.5), ("keys", "C-b"), ("sleep", 0.5), ("keys", "Enter"), ("sleep", 0.8),
                ("q", MODE), ("shot", "after-enter")]),
]

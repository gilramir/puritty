"""The prompt's emacs word keys and word-separators (docs/review.md RV2,
docs/tmux.md TM104): M-f, M-b, C-w and C-Left, a mark typed where the
caret lands, beside a plain client."""

from scenes import P

SCENES = [
    dict(name="words-forward", steps=[("keys", P, ":"), ("type", "a--b c"), ("keys", "Home"), ("keys", "M-f"),
                                      ("type", "X"), ("shot", "forward"), ("keys", "C-c")]),
    dict(name="words-back", steps=[("keys", P, ":"), ("type", "a b--"), ("keys", "M-b"), ("type", "X"),
                                   ("shot", "back"), ("keys", "C-c")]),
    dict(name="words-cut", steps=[("keys", P, ":"), ("type", "new-window -n my_logs"), ("keys", "C-w"),
                                  ("shot", "cut"), ("keys", "C-c")]),
    dict(name="words-ctrl-left", steps=[("keys", P, ":"), ("type", "ab c"), ("keys", "C-Left"), ("type", "X"),
                                        ("shot", "ctrl-left"), ("keys", "C-c")]),
]

"""Kitty graphics images in tmux -CC panes (docs/images.md IM18): chafa
draws in a pane of a split window; puritty's shot shows it in its pane,
cut to it. tmux's own client draws no image, so only puritty's side is
looked at."""

from scenes import sk

PIC = "/tmp/claude-1000/-home-gram-prj-geng-lang/0cb03f08-cfdc-405b-b75d-c05bf5579c81/scratchpad/chafa/test.png"

SCENES = [
    # chafa run after puritty attached: an image drawn before is gone (IM1)
    dict(name="image-in-pane", setup=[("split-window", "-h", "-t", "main:0"), sk("main:0.0", "echo left pane"), ("send-keys", "-t", "main:0.1", "clear", "Enter")],
         steps=[("sleep", 1.0), ("type", "chafa -f kitty --size 30x8 " + PIC + "; echo below\n"), ("sleep", 2.0), ("shot", "split")]),
    # wider than its pane: cut at the pane's edge, not drawn over the other
    dict(name="image-cut-at-pane", setup=[("split-window", "-h", "-t", "main:0"), ("select-pane", "-t", "main:0.0"), ("send-keys", "-t", "main:0.0", "clear", "Enter")],
         steps=[("sleep", 1.0), ("type", "python3 " + PIC.replace("test.png", "wide.py") + "\n"), ("sleep", 2.0), ("shot", "cut")]),
]

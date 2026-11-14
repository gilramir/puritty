#!/usr/bin/env python3
"""src/TmuxVersions.geng from ../../../corpus/tmux/*/commands.txt: each
dumped tmux's `list-commands` usage lines (puritty docs/tmux-versions.md,
docs/tmux-checks.md TK2), so that the catalog's test holds every shape to
every tmux without reading files.

    gen-versions.py           write it
    gen-versions.py --check   fail if what is written is not what the dumps make
"""
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
corpus = here.parent.parent.parent / "corpus" / "tmux"


def geng(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


rows = []
for folder in sorted(p for p in corpus.iterdir() if (p / "commands.txt").exists()):
    lines = (folder / "commands.txt").read_text().splitlines()
    rows.append("{ name = " + geng(folder.name) + "\n      , usage =\n            [ "
                + "\n            , ".join(geng(l) for l in lines) + "\n            ]\n      }")
text = "\n".join([
    "module TmuxVersions exposing (versions)",
    "",
    "{-| Each dumped tmux's `list-commands` (corpus/tmux). Written by",
    "gen-versions.py; do not edit. -}",
    "",
    "",
    "versions : Array { name : String, usage : Array String }",
    "versions =",
    "    [ " + "\n    , ".join(rows),
    "    ]",
    "",
])
target = here / "src" / "TmuxVersions.geng"
if "--check" in sys.argv:
    if not target.exists() or target.read_text() != text:
        sys.exit("src/TmuxVersions.geng is not what corpus/tmux makes: run packages/tmux/tests/gen-versions.py")
    print(f"src/TmuxVersions.geng matches corpus/tmux ({len(rows)} tmuxes)")
else:
    target.write_text(text)
    print(f"{len(rows)} tmuxes written to src/TmuxVersions.geng")

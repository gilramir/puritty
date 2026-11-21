#!/usr/bin/env python3
"""src/LinesRecorded.geng from ../../corpus/tmux/*/lines.txt: how each
dumped tmux answered dump-lines.py's command lines (puritty
docs/tmux-checks.md TK10), so that the fake tmux's rules for a line of
several commands are held to every tmux without reading files.

    gen-lines.py           write it
    gen-lines.py --check   fail if what is written is not what the dumps make
"""
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
corpus = here.parent.parent / "corpus" / "tmux"


def geng(text):
    out = ""
    for c in text:
        if c in "\\\"":
            out += "\\" + c
        elif ord(c) < 0x20 or ord(c) == 0x7F:
            out += "\\u{%04X}" % ord(c)
        else:
            out += c
    return '"' + out + '"'


def sessions(folder, name="lines.txt"):
    """Each line sent (or step), and what tmux wrote, from lines.txt or
    notices.txt."""
    out = []
    path = folder / name
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if line.startswith("> "):
            out.append((line[2:], []))
        elif out:
            out[-1][1].append(line[2:])
    return out


rows = []
for folder in sorted(p for p in corpus.iterdir() if (p / "lines.txt").exists()):
    version = (folder / "about.txt").read_text().split("\n")[0].removeprefix("tmux ").strip()
    def entries(name):
        got = [
            "{ line = " + geng(sent) + ", wrote = " + ("[ " + ", ".join(geng(w) for w in wrote) + " ]" if wrote else "[]") + " }"
            for sent, wrote in sessions(folder, name)
        ]
        return ("[ " + "\n            , ".join(got) + "\n            ]") if got else "[]"

    rows.append("{ name = " + geng(folder.name) + "\n      , version = " + geng(version)
                + "\n      , lines =\n            " + entries("lines.txt")
                + "\n      , notices =\n            " + entries("notices.txt") + "\n      }")
text = "\n".join([
    "module LinesRecorded exposing (recorded)",
    "",
    "{-| How each dumped tmux answered dump-lines.py's command lines",
    "(corpus/tmux/*/lines.txt, docs/tmux-checks.md TK10), and what it told",
    "a control client as dump-notices.py changed the server (notices.txt,",
    "TK11). Written by",
    "gen-lines.py; do not edit. -}",
    "",
    "",
    "recorded : Array { name : String, version : String, lines : Array { line : String, wrote : Array String }, notices : Array { line : String, wrote : Array String } }",
    "recorded =",
    "    [ " + "\n    , ".join(rows),
    "    ]",
    "",
])
target = here / "src" / "LinesRecorded.geng"
if "--check" in sys.argv:
    if not target.exists() or target.read_text() != text:
        sys.exit("src/LinesRecorded.geng is not what corpus/tmux makes: run app/tests/gen-lines.py")
    print(f"src/LinesRecorded.geng matches corpus/tmux ({len(rows)} tmuxes)")
else:
    target.write_text(text)
    print(f"{len(rows)} tmuxes written to src/LinesRecorded.geng")

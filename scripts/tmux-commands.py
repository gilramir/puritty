#!/usr/bin/env python3
"""tmux command text outside Tmux.Command (puritty docs/tmux-checks.md TK2):
every command puritty sends is to be made from a shape in Tmux.Command's
catalog, so a string literal elsewhere that begins with a tmux command's
name is a command made by hand, unless it compares with what tmux sent
(`== "copy-mode"`, a `when` branch, `Caps.has "send-keys"`). Those found
are held to corpus/checks/tmux-commands.txt, which lists the ones not yet
moved; a new one fails, and one gone is said so the list can shrink.

    scripts/tmux-commands.py            held to the list
    scripts/tmux-commands.py --update   the list written again
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "corpus" / "checks" / "tmux-commands.txt"
# the modules that talk to tmux; elsewhere tmux's short aliases (`start`,
# `run`, `show`) are ordinary words
SOURCES = [ROOT / "app" / "src" / "TmuxMode.geng"] + sorted((ROOT / "packages" / "tmux" / "src" / "Tmux").glob("*.geng"))
SKIP = {"Command.geng", "CustomizeTables.geng"}

names, aliases = set(), set()
for line in (ROOT / "corpus" / "tmux" / "3.8" / "commands.txt").read_text().splitlines():
    w = line.split()
    names.add(w[0])
    if len(w) > 1 and w[1].startswith("("):
        aliases.add(w[1].strip("()"))
# full names, and an alias only when a flag follows it (`"set -pF …"`):
# alone an alias in puritty's own text is likelier a word (`start`, `run`)
words = names
# a mode's or key table's name, the same word as its command, said alone
MODES = {"copy-mode", "copy-mode-vi", "view-mode", "clock-mode", "customize-mode", "tree-mode",
         "buffer-mode", "client-mode"}
literal = re.compile(r'"((?:[^"\\]|\\.)*)"')
comparing = re.compile(r'(==|/=|== Just|startsWith|endsWith|contains|\bhas|Caps\.has|Caps\.known|Dict\.get|Dict\.member|Array\.member)\s*\(?\s*$')


def strays():
    out = []
    for f in SOURCES:
        if f.name in SKIP:
            continue
        for line in f.read_text().splitlines():
            code = line.strip()
            if code.startswith("--") or code.startswith("{-|") or code.endswith("->"):
                # a comment, or a pattern matched against what tmux sent
                continue
            for m in literal.finditer(line):
                parts = m.group(1).split(" ")
                first = parts[0]
                flagged = len(parts) > 1 and parts[1].startswith("-")
                if not (first in words or (first in aliases and flagged)):
                    continue
                if m.group(1) in MODES:
                    continue
                before = line[: m.start()]
                after = line[m.end():].strip()
                if comparing.search(before) or after.startswith("->") or after.startswith("||") and comparing.search(before):
                    continue
                out.append(f"{f.relative_to(ROOT)}\t{code}")
    return out


def main():
    found = strays()
    if "--update" in sys.argv:
        LIST.write_text("".join(s + "\n" for s in sorted(found)))
        print(f"{len(found)} tmux commands made outside Tmux.Command, written to {LIST.relative_to(ROOT)}")
        return 0
    kept = LIST.read_text().splitlines() if LIST.exists() else []
    new = sorted(set(found) - set(kept))
    gone = sorted(set(kept) - set(found))
    for s in new:
        print("NEW   " + s)
    for s in gone:
        print("GONE  " + s)
    print(f"{len(found)} tmux commands made outside Tmux.Command; {len(kept)} on the list: {len(new)} new, {len(gone)} gone")
    return 1 if new or gone else 0


sys.exit(main())

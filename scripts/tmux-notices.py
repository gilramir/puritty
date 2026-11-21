#!/usr/bin/env python3
"""Every notification a tmux sends a control client, held to what puritty
does with it (puritty docs/tmux-checks.md TK11).

The notifications are those the dumped tmuxes sent (corpus/tmux/*/
control.txt, lines.txt and notices.txt). Each is a row of
corpus/checks/tmux-notices.tsv:

    name    constructor    sent by    handling    why

`sent by` is which releases sent it, computed from the recordings: `all`,
`from X`, `until X`, `some`, or `unrecorded` for one no recording has (a
notification the recordings do not cause, kept with its decision).
`handling` is `acts` or `ignores`, and it is read from TmuxMode's `notice`:
a constructor with a branch of its own acts, one left to its `_` ignores.

The check fails on a notification sent that has no row (NEW), a row whose
`sent by` is not what the recordings say (SPAN), one recorded but written
`unrecorded` or the other way (SPAN), a name Tmux.Control does not read
(UNREAD), a constructor Control does not have (NOCTOR), and a `handling`
that is not what TmuxMode does (HANDLING).

    scripts/tmux-notices.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "corpus" / "checks" / "tmux-notices.tsv"
CORPUS = ROOT / "corpus" / "tmux"
CONTROL = ROOT / "packages" / "tmux" / "src" / "Tmux" / "Control.geng"
MODE = ROOT / "app" / "src" / "TmuxMode.geng"
# a block's own lines, not notifications
BLOCKS = {"%begin", "%end", "%error"}


def version_key(v):
    m = re.fullmatch(r"(\d+)\.(\d+)([a-z]?)", v)
    return (int(m.group(1)), int(m.group(2)), m.group(3))


def recorded():
    """Each notification, and the releases (not the distributions'
    packages) whose recordings have it; and every release recorded."""
    sent, releases = {}, []
    for folder in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        release = re.fullmatch(r"\d+\.\d+[a-z]?", folder.name) is not None
        if release:
            releases.append(folder.name)
        for f in ("control.txt", "lines.txt", "notices.txt"):
            path = folder / f
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                m = re.match(r"^  (%[a-z][a-z-]*)", line)
                if m and m.group(1) not in BLOCKS:
                    sent.setdefault(m.group(1), set())
                    if release:
                        sent[m.group(1)].add(folder.name)
    return sent, sorted(releases, key=version_key)


def span(have, releases):
    """`all`, `from X`, `until X` or `some`. 2.9's recordings end early
    (it ends the client after a split), so it neither makes nor breaks a
    span."""
    rs = [r for r in releases if r != "2.9"]
    on = [r in have for r in rs]
    if all(on):
        return "all"
    if not any(on):
        return "none"
    first = on.index(True)
    if all(on[first:]) and not any(on[:first]):
        return "from " + rs[first]
    last = len(on) - 1 - on[::-1].index(True)
    if all(on[:last + 1]) and not any(on[last + 1:]):
        return "until " + rs[last]
    return "some"


def handled():
    """The constructors TmuxMode's `notice` gives a branch of their own."""
    text = MODE.read_text()
    start = text.index("\nnotice : Notice")
    end = re.search(r"\n[a-z][A-Za-z0-9]* :", text[start + 1:]).start() + start + 1
    return set(re.findall(r"^        ([A-Z][A-Za-z]*)\b[^\n]*->", text[start:end], re.M)) - {"Just", "Nothing"}


def main():
    sent, releases = recorded()
    control = CONTROL.read_text()
    acts = handled()
    rows = {}
    for line in LIST.read_text().splitlines():
        if line and not line.startswith("#"):
            name, ctor, by, handling, why = line.split("\t")
            rows[name] = {"ctor": ctor, "by": by, "handling": handling}

    problems = []
    for name in sorted(sent):
        if name not in rows:
            problems.append(f"NEW      {name}: sent by {span(sent[name], releases)}, and no row")
    for name, r in sorted(rows.items()):
        want = span(sent[name], releases) if name in sent else "unrecorded"
        if r["by"] != want:
            problems.append(f"SPAN     {name}: the row says {r['by']}, the recordings {want}")
        if f'"{name}"' not in control and r["ctor"] != "Output":
            problems.append(f"UNREAD   {name}: Tmux.Control does not read it")
        if not re.search(r"\|\s*" + r["ctor"] + r"\b|=\s*" + r["ctor"] + r"\b", control):
            problems.append(f"NOCTOR   {name}: Tmux.Control has no {r['ctor']}")
        does = "acts" if r["ctor"] in acts else "ignores"
        if r["handling"] != does:
            problems.append(f"HANDLING {name}: the row says {r['handling']}, TmuxMode {does}")
    for p in problems:
        print(p)
    print(f"{len(sent)} notifications sent by {len(releases)} releases and the distributions, {len(rows)} rows: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

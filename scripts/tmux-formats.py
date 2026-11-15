#!/usr/bin/env python3
"""The format variables puritty asks, against every dumped tmux (puritty
docs/tmux-checks.md TK8).

A variable or option a tmux does not have expands to nothing, with no
error, so a format that asks one is answered with an empty field. Every
name puritty asks is held to corpus/checks/tmux-formats.tsv, one row each:

    name    since    empty

`since` is the first tmux puritty asks it of (`all`, or a version where the
asking is gated by version or by what the tmux takes); `empty` says how an
empty answer reads, for a tmux from `since` that lacks the name, or `-`
when every such tmux has it. What each tmux has is its variables.txt (from
its source) and its options-*.txt (corpus/tmux).

The check fails on a name asked that is not on the list (NEW), a row whose
name is no longer asked (GONE), a tmux from `since` lacking a name whose
`empty` is `-` (LACKS), an `empty` no tmux from `since` needs (NEEDLESS),
and a word in a format's place that no tmux knows, unless listed with
`since` `text` (UNKNOWN: a typo, or text that only looks like a name).
`since` `local` is a name in a format of tmux's own that puritty replaces
with a value before it is sent, so no tmux is asked it.

The names are read from the source, not run: every string literal with
`#{` in it, each lowercase word there that stands where a name does
(after `{`, `?`, `:` or `,` and before `}` or `,`); the option list sent
whole (`optionNames`); and the helpers that put a name into a format
(`flag "label" "name"`, `matching "name"`). That `since` is kept is read,
not proved; check 3's explorer (TK4) will see each format as it is sent.

    scripts/tmux-formats.py            the check
    scripts/tmux-formats.py --update   rows added for new names, gone ones removed
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "corpus" / "checks" / "tmux-formats.tsv"
CORPUS = ROOT / "corpus" / "tmux"
SOURCES = [ROOT / "app" / "src" / "TmuxMode.geng"] + sorted((ROOT / "packages" / "tmux" / "src" / "Tmux").glob("*.geng"))
# tmux's own option table, quoted, not asked
SKIP = {"CustomizeTables.geng"}

literal = re.compile(r'"((?:[^"\\]|\\.)*)"')
placed = re.compile(r"(?<=[{?:,])([a-z][a-z0-9_-]*(?:\[\d+\])?)(?=[},])")
helpers = re.compile(r'\b(?:flag\s+"[^"]*"|matching)\s+"([a-z][a-z0-9_-]*)"')


def asked():
    """Each name read from the source, with the first place it is."""
    out = {}
    for f in SOURCES:
        if f.name in SKIP:
            continue
        lines = f.read_text().splitlines()
        in_options = False
        for n, line in enumerate(lines, 1):
            code = line.strip()
            where = f"{f.relative_to(ROOT)}:{n}"
            if code.startswith("--") or code.startswith("{-"):
                continue
            if code == "optionNames =":
                in_options = True
                continue
            if in_options:
                if code == "]":
                    in_options = False
                for name in literal.findall(line):
                    out.setdefault(name, where)
                continue
            for name in helpers.findall(line):
                out.setdefault(name, where)
            for text in literal.findall(line):
                if "#{" in text:
                    for name in placed.findall(text):
                        out.setdefault(name, where)
    return out


def version_key(v):
    """2.7 < 2.9a < 3.3a < next-3.4 < 3.4."""
    snapshot = v.startswith("next-")
    m = re.fullmatch(r"(\d+)\.(\d+)([a-z]?)", v.removeprefix("next-"))
    major, minor, letter = int(m.group(1)), int(m.group(2)), m.group(3)
    if snapshot:
        return (major, minor - 1, "~")
    return (major, minor, letter)


def tmuxes():
    out = []
    for folder in sorted(p for p in CORPUS.iterdir() if (p / "variables.txt").exists()):
        version = (folder / "about.txt").read_text().split("\n")[0].removeprefix("tmux ").strip()
        known = set((folder / "variables.txt").read_text().split())
        for f in folder.glob("options-*.txt"):
            for line in f.read_text().splitlines():
                if line and not line.startswith("%"):
                    known.add(re.split(r"[ \[]", line)[0])
        out.append({"name": folder.name, "version": version, "known": known})
    return out


def has(t, name):
    return re.sub(r"\[\d+\]$", "", name) in t["known"]


def read_list():
    rows = {}
    if LIST.exists():
        for line in LIST.read_text().splitlines():
            if line and not line.startswith("#"):
                name, since, empty = (line.split("\t") + ["", ""])[:3]
                rows[name] = {"since": since, "empty": empty}
    return rows


def main():
    found = asked()
    ts = tmuxes()
    rows = read_list()
    known_anywhere = {n for n in found if any(has(t, n) for t in ts)}

    if "--update" in sys.argv:
        for name in found:
            if name not in rows:
                rows[name] = {"since": "all" if name in known_anywhere else "text", "empty": "?"}
        for name in [n for n in rows if n not in found]:
            del rows[name]
        head = "# name\tsince\tempty   (scripts/tmux-formats.py; docs/tmux-checks.md TK8)\n"
        LIST.write_text(head + "".join(f"{n}\t{r['since']}\t{r['empty']}\n" for n, r in sorted(rows.items())))
        print(f"{len(rows)} names written to {LIST.relative_to(ROOT)}")
        return 0

    problems = []
    for name, where in sorted(found.items()):
        if name not in rows:
            problems.append(f"NEW      {name}  ({where})")
    for name in sorted(rows):
        r = rows[name]
        if name not in found:
            problems.append(f"GONE     {name}")
            continue
        if r["since"] == "text":
            if name in known_anywhere:
                problems.append(f"NOT TEXT {name}: a tmux knows it")
            continue
        if r["since"] == "local":
            # a format of tmux's own that puritty fills in before it asks
            continue
        if name not in known_anywhere:
            problems.append(f"UNKNOWN  {name}: no tmux knows it ({found[name]})")
            continue
        if r["empty"] == "?":
            problems.append(f"UNSAID   {name}: since and empty not yet decided")
            continue
        start = None if r["since"] == "all" else version_key(r["since"])
        lacking = [t["name"] for t in ts if (start is None or version_key(t["version"]) >= start) and not has(t, name)]
        if lacking and r["empty"] == "-":
            problems.append(f"LACKS    {name}: asked of {', '.join(lacking)}, which lack it")
        if not lacking and r["empty"] != "-":
            problems.append(f"NEEDLESS {name}: every tmux it is asked of has it")
    for p in problems:
        print(p)
    print(f"{len(found)} names asked, {len(rows)} on the list, against {len(ts)} tmuxes: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

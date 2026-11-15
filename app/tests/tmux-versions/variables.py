#!/usr/bin/env python3
"""corpus/tmux/*/variables.txt: the format variables each dumped tmux knows,
read from its source (puritty docs/tmux-checks.md TK8).

`display-message -a` (formats-all.txt) lists only the variables of the
context it is run in, so a buffer's, copy mode's or a hook's are missing,
and 2.7 and 2.8 do not have `-a` at all. The source names every one: up
to 3.1 as `format_add(ft, "name", …)`, from 3.2 as `{ "name",
FORMAT_TABLE_…` in format.c's table, beside the few still added. Checked
against formats-all.txt: every variable a tmux lists is found in its
source, but for three internal ones from 2.9 to 3.1c (`*_mode_format`).

A release's folder is read from its own tarball, as releases.sh fetched it
into ~/.cache/puritty/tmux/src. A distribution's package from the release
its about.txt names (a distribution's patches are not read); AlmaLinux 10's
is a git snapshot between 3.3a and 3.4 (`next-3.4`), so it is 3.3a's
source and whatever its own formats-all.txt lists.

    variables.py            write them
    variables.py --check    fail if one written is not what the sources make
"""
import os
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus" / "tmux"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "puritty" / "tmux" / "src"
ADDED = re.compile(r'format_add(?:_tv|_cb)?\s*\(\s*\w+\s*,\s*"([a-z0-9_]+)"')
TABLE = re.compile(r'\{\s*"([a-z0-9_]+)"\s*,\s*FORMAT_TABLE_')
# a snapshot's release, where about.txt's version is not one
SNAPSHOTS = {"next-3.4": "3.3a"}


def from_source(version):
    tar = CACHE / f"tmux-{version}.tar.gz"
    if not tar.exists():
        sys.exit(f"variables.py: {tar} is missing; app/tests/tmux-versions/releases.sh fetches it")
    names = set()
    with tarfile.open(tar) as t:
        for m in t.getmembers():
            if m.isfile() and m.name.endswith(".c") and m.name.count("/") == 1:
                text = t.extractfile(m).read().decode("utf-8", "replace")
                names |= set(ADDED.findall(text)) | set(TABLE.findall(text))
    return names


def listed(folder):
    f = folder / "formats-all.txt"
    if not f.exists():
        return set()
    return {line.split("=")[0] for line in f.read_text().splitlines() if re.match(r"[a-z0-9_]+=", line)}


def made():
    out = {}
    for folder in sorted(p for p in CORPUS.iterdir() if (p / "about.txt").exists()):
        version = (folder / "about.txt").read_text().split("\n")[0].removeprefix("tmux ").strip()
        if version in SNAPSHOTS:
            names = from_source(SNAPSHOTS[version]) | {n for n in listed(folder) if not n.endswith("_mode_format")}
        else:
            names = from_source(version)
        out[folder] = "".join(n + "\n" for n in sorted(names))
    return out


def main():
    check = "--check" in sys.argv
    wrong = 0
    for folder, text in made().items():
        path = folder / "variables.txt"
        if check:
            if not path.exists() or path.read_text() != text:
                print(f"{path.relative_to(ROOT)} is not what the sources make")
                wrong += 1
        else:
            path.write_text(text)
    if not check:
        print(f"wrote variables.txt for {len(made())} tmuxes")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())

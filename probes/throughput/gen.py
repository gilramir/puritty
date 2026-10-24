#!/usr/bin/env python3
"""Writes the throughput inputs into DIR.

ls.txt and cup.txt are the two workloads of geng-plan.md §1, byte for byte what
probes/geng/grid builds: 200,000 ls-like lines with two SGR sequences each, and
2,000,000 single cells each after a CUP. gitlog.txt is real output with colour:
`git log -p --color=always` of the vendored Ghostty, the first COMMITS commits
back from a fixed revision.

usage: gen.py DIR
"""
import os
import subprocess
import sys

GHOSTTY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../vendor/ghostty")
REVISION = "d8619f1bc"
COMMITS = 2000


def ls_line(n):
    return (
        "drwxr-xr-x  2 gram gram  4096 Oct 23 10:%d \x1b[01;34mdirectory-%d\x1b[0m"
        " and some more ordinary text to fill the line out\r\n" % (n % 60, n)
    )


def cup_cell(n):
    return "\x1b[%d;%dHx" % ((n * 7) % 50 + 1, (n * 13) % 160 + 1)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "ls.txt"), "w", newline="") as f:
        f.write("".join(ls_line(n) for n in range(200_000)))
    with open(os.path.join(out, "cup.txt"), "w", newline="") as f:
        f.write("".join(cup_cell(n) for n in range(2_000_000)))
    log = subprocess.run(
        ["git", "-C", GHOSTTY, "-c", "color.ui=always", "log", "-p", "--color=always",
         "-n", str(COMMITS), REVISION],
        check=True, capture_output=True,
    ).stdout
    # A program writing to a tty has each LF turned into CR LF by the line
    # discipline. The headless cores read the file directly, so it has them.
    with open(os.path.join(out, "gitlog.txt"), "wb") as f:
        f.write(log.replace(b"\n", b"\r\n"))


main()

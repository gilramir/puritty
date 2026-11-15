#!/usr/bin/env python3
"""What one tmux tells a control client when the server changes under it,
for the version survey (docs/tmux-versions.md) and puritty's notification
check (docs/tmux-checks.md TK11).

    app/tests/dump-notices.py TMUX OUT-DIR

A control client (`tmux -C attach`) is attached to session `main` and only
listens; a second client, as a user at another terminal or a script would,
changes the server one step at a time: windows made, renamed, shown and
closed, panes split, killed and exiting on their own, the shown window's
last pane exiting, sessions made, renamed and killed, a window made in
another session, copy mode, a resize, buffers, another client attaching and
leaving, the server killed. After each step every line the control client
read until tmux was quiet is written to OUT-DIR/notices.txt, normalized as
dump-tmux.py's control.txt is. Each step is the command line given to
`tmux`, or a wait for a pane's program to end.

It runs inside a container with that tmux, as dump-tmux.py does.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
dump = __import__("dump-tmux")

# Each step: what it is, and the tmux arguments a second client runs, or a
# wait in seconds for a program to end. The session starts as dump-tmux.py's:
# window @0 (index 0, `sh`), pane %0.
STEPS = [
    ("a window made, not shown", ["new-window", "-d", "-n", "two"]),
    ("another window renamed", ["rename-window", "-t", ":1", "renamed"]),
    ("the shown window renamed", ["rename-window", "-t", ":0", "first"]),
    ("the shown window split", ["split-window", "-d", "-t", ":0"]),
    ("the other pane made active", ["select-pane", "-t", ":0.1"]),
    ("another window shown", ["select-window", "-t", ":1"]),
    ("the first window shown again", ["select-window", "-t", ":0"]),
    ("a pane of the shown window killed", ["kill-pane", "-t", ":0.1"]),
    ("a pane made whose program ends", ["split-window", "-d", "-t", ":0", "sleep 0.5"]),
    ("its program ends", 1.5),
    ("a window made whose program ends", ["new-window", "-d", "-n", "short", "sleep 0.5"]),
    ("that window's last pane's program ends", 1.5),
    ("another window killed", ["kill-window", "-t", ":1"]),
    ("a window made and shown, whose program ends", ["new-window", "-n", "brief", "sleep 0.8"]),
    ("the shown window's last pane's program ends", 2.0),
    ("a session made", ["new-session", "-d", "-s", "other", "-n", "elsewhere"]),
    ("a window made in the other session", ["new-window", "-d", "-t", "other:"]),
    ("a window of the other session renamed", ["rename-window", "-t", "other:1", "far"]),
    ("a window of the other session killed", ["kill-window", "-t", "other:1"]),
    ("the other session renamed", ["rename-session", "-t", "other", "renamed-session"]),
    ("the shown session renamed", ["rename-session", "-t", "main", "main2"]),
    ("the shown session renamed back", ["rename-session", "-t", "main2", "main"]),
    ("the other session killed", ["kill-session", "-t", "renamed-session"]),
    ("copy mode entered", ["copy-mode", "-t", ":0.0"]),
    ("copy mode left", ["send-keys", "-t", ":0.0", "-X", "cancel"]),
    ("the window resized", ["resize-window", "-t", ":0", "-x", "100", "-y", "30"]),
    ("a buffer set", ["set-buffer", "-b", "one", "hello"]),
    ("the buffer deleted", ["delete-buffer", "-b", "one"]),
    ("the window's layout changed", ["select-layout", "-t", ":0", "even-horizontal"]),
    ("a window swapped to another index", ["move-window", "-s", ":0", "-t", ":5"]),
    # what changes the shown window's panes or layout, each told or not
    ("the shown window split twice more", ["split-window", "-d", "-t", ":5"]),
    ("and again", ["split-window", "-d", "-h", "-t", ":5"]),
    ("its panes rotated", ["rotate-window", "-t", ":5"]),
    ("its panes rotated back", ["rotate-window", "-D", "-t", ":5"]),
    ("two panes swapped", ["swap-pane", "-D", "-t", ":5"]),
    ("a pane zoomed", ["resize-pane", "-Z", "-t", ":5"]),
    ("unzoomed", ["resize-pane", "-Z", "-t", ":5"]),
    ("a pane resized", ["resize-pane", "-t", ":5", "-R", "3"]),
    ("the panes laid out tiled", ["select-layout", "-t", ":5", "tiled"]),
    ("a pane respawned", ["respawn-pane", "-k", "-t", ":5.1"]),
    ("a pane broken out to a window", ["break-pane", "-d", "-n", "broke", "-s", ":5.1"]),
    ("a pane joined back", ["join-pane", "-d", "-s", ":broke", "-t", ":5"]),
    ("a window made, then two windows swapped", ["new-window", "-d", "-n", "swap"]),
    ("swapped", ["swap-window", "-s", ":5", "-t", ":swap"]),
    ("the server killed", ["kill-server"]),
]


def joined(lines, normal):
    """dump-tmux.py's control_session normalization: a pane's output in one
    step joined, block numbers and times written alike."""
    out = []
    for line in lines:
        m = re.match(r"^%(output|extended-output) (%\d+)( \d+ :)? (.*)$", line)
        if m and out and out[-1][0] == m.group(2):
            out[-1] = (m.group(2), out[-1][1] + m.group(4))
        elif m:
            out.append((m.group(2), m.group(4)))
        else:
            out.append((None, line))
    for pane, text in out:
        line = "%output " + pane + " " + text if pane else text
        line = re.sub(r"^%(begin|end|error) \d+ \d+ (\d)$", r"%\1 TIME N \2", line)
        yield normal(line)


def session(tmux, client, normal):
    out = []
    for what, step in STEPS:
        if isinstance(step, (int, float)):
            out.append("> (" + what + ": waited " + str(step) + " s)")
            time.sleep(step)
        else:
            out.append("> " + " ".join(step) + "    # " + what)
            p = dump.run(tmux, *step, check=False)
            if p.returncode != 0:
                out.append("  (tmux said: " + p.stderr.strip() + ")")
        for line in joined(client.lines(quiet=0.6), normal):
            out.append("  " + line)
        if client.ended:
            out.append("  (the client ended)")
            break
    return out


def main():
    tmux, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    dump.start(tmux)
    client = dump.Client(tmux)
    client.lines(quiet=1.0)
    normal = dump.Normal()
    lines = session(tmux, client, normal)
    client.close()
    dump.run(tmux, "kill-server", check=False)
    dump.write(out, "notices.txt", lines)


if __name__ == "__main__":
    main()

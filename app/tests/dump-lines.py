#!/usr/bin/env python3
"""How one tmux answers a command line of several commands, some failing,
for the version survey (docs/tmux-versions.md) and check 3's model of
tmux (puritty docs/tmux-checks.md TK4, TK10).

    app/tests/dump-lines.py TMUX OUT-DIR

Writes OUT-DIR/lines.txt: each line sent, then every line tmux wrote until
it was quiet, normalized as dump-tmux.py's control.txt is (a block's time
and number as `TIME N`). The lines ask how many blocks a line of n
commands gets when one fails as it runs, when one is not a command or
takes a flag this tmux lacks, when the line does not parse; where the
notifications its commands cause are written among the blocks; and what
`if-shell`, `run-shell` and a `display-message` without `-p` add.

It runs inside a container with that tmux, as dump-tmux.py does.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
dump = __import__("dump-tmux")

# The session starts as dump-tmux.py's does: one window, `@0`, one pane,
# `%0`, showing 200 lines and sleeping.
LINES = [
    # two commands that work: a block each
    "display-message -p A ; display-message -p B",
    # one failing as it runs, first, in the middle, last
    "select-pane -t %99 ; display-message -p B",
    "display-message -p A ; select-pane -t %99 ; display-message -p C",
    "display-message -p A ; select-pane -t %99",
    "display-message -p A ; capture-pane -p -t %99 ; display-message -p C",
    # a pane that is not there, which display-message may let pass
    "display-message -p -t %99 A ; display-message -p B",
    # not a command, first or after one that works
    "nosuchcommand ; display-message -p B",
    "display-message -p A ; nosuchcommand",
    # a flag no tmux has, on the second command
    "display-message -p A ; display-message -Z B",
    # a line that does not parse
    "display-message -p A ; display-message -p 'unclosed",
    # a command only newer tmuxes have (3.2)
    "display-message -p A ; display-popup -E true ; display-message -p B",
    # commands whose effects tmux tells the client, among others
    "display-message -p A ; split-window -d -t %0 ; display-message -p B",
    "display-message -p A ; select-pane -t %1 ; display-message -p B",
    "display-message -p A ; kill-pane -t %1 ; display-message -p B",
    "display-message -p A ; new-window -d -n two ; display-message -p B",
    "display-message -p A ; kill-window -t :1 ; display-message -p B",
    "display-message -p A ; copy-mode -t %0 ; display-message -p B",
    "send-keys -t %0 -X cancel ; display-message -p B",
    "send-keys -t %0 -X cancel ; display-message -p B",
    "display-message -p A ; refresh-client -C 100x30 ; display-message -p B",
    "refresh-client -C 80x24",
    # a message, not a reply
    "display-message M ; display-message -p B",
    # commands run by a command
    "if-shell -F 1 'display-message -p X' ; display-message -p B",
    "if-shell -F 1 'select-pane -t %99' ; display-message -p B",
    "if-shell -F 1 'display-message -p X ; display-message -p Y' 'display-message -p N' ; display-message -p B",
    "if-shell 'true' 'display-message -p X' ; display-message -p B",
    "if-shell -b 'true' 'display-message -p X' ; display-message -p B",
    "source-file /tmp/puritty-lines.conf ; display-message -p B",
    "run-shell 'echo ran' ; display-message -p B",
    "run-shell -b 'echo ran' ; display-message -p B",
    # the pane's lines in a reply, then a command
    "capture-pane -p -t %0 -S -2 ; display-message -p B",
    # a line that is empty but for spaces, and one that is only `;`
    "   ",
    ";",
    "display-message -p A ;",
    # a missing argument, last: 3.3 and 3.3a take `kill-pane -t` as
    # `kill-pane`, which ends the server
    "display-message -p A ; kill-pane -t",
]


def session(client, normal):
    out = []
    for line in LINES:
        out.append("> " + line)
        # a shell run by if-shell or run-shell -b may answer late
        for got in client.send(line) + client.lines(quiet=0.3):
            got = re.sub(r"^%(begin|end|error) \d+ \d+ (\d)$", r"%\1 TIME N \2", got)
            out.append("  " + normal(got))
        if client.ended:
            out.append("  (the client ended)")
            break
    return out


def main():
    tmux, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    # two commands for source-file to run
    Path("/tmp/puritty-lines.conf").write_text("display-message -p S1\ndisplay-message -p S2\n")
    dump.start(tmux)
    client = dump.Client(tmux)
    client.lines(quiet=1.0)
    normal = dump.Normal()
    lines = session(client, normal)
    client.close()
    dump.run(tmux, "kill-server", check=False)
    dump.write(out, "lines.txt", lines)


if __name__ == "__main__":
    main()

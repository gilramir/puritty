#!/usr/bin/env python3
"""src/RealTmux.geng: a real tmux's answers to puritty's questions, in the
states FakeTmux's tests use (docs/tmux.md TM68), so that a test can hold
the fake's answers to tmux's.

A server is started with one 80x24 pane that has printed `line 1` to
`line 200` and no last newline; then copy mode is entered and the cursor
moved up 30 times, then once more. At each state every question is asked
with tmux's own command line, and its lines recorded. Run it when tmux, a
question or the fake changes:

    app/tests/record-tmux.py [TMUX...]

Each tmux is recorded, its answers marked with its version; by default the
3.8 the comparison harness uses and the 3.6a beside it, the two versions
TmuxMode answers differently (docs/tmux.md TM68).
"""
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMUXES = sys.argv[1:] or [
    "/nix/store/k111lnbq1vw0k4v4cjhi1iwp5lky3ryn-tmux-3.8/bin/tmux",
    "/nix/store/6lixxqgzmdvx28k5bg2r55416cy4jv64-tmux-3.6a/bin/tmux",
]
SOCKET = "puritty-record"

# puritty's questions, as TmuxMode asks them (windowQuery, panesQuery,
# infoOf, modeFormat, copyFormat, tabsQuery)
QUESTIONS = [
    "display-message -p 'W #{window_id} #{pane_id} #{window_visible_layout} #{window_name}'",
    "list-windows -F 'T #{window_id} #{window_index} #{window_name}'",
    "list-panes -s -F 'P #{pane_id}'",
    "display-message -p -t %0 'P #{pane_id} #{pane_width} #{pane_height} #{cursor_x} #{cursor_y} #{alternate_on} #{scroll_region_upper} #{scroll_region_lower}'",
    "display-message -p -t %0 'M #{pane_id} #{pane_mode} #{mode-keys}'",
    "display-message -p -t %0 'C #{pane_id} #{scroll_position} #{history_size} #{copy_cursor_x} #{copy_cursor_y} #{selection_present}'",
]


def tmux(*args):
    return subprocess.run([TMUX[0], "-L", SOCKET, *args], capture_output=True, text=True, check=True).stdout


def ask(command):
    out = tmux(*shlex.split(command))
    return out.split("\n")[:-1] if out.endswith("\n") else out.split("\n")


TMUX = [None]


def recorded(binary):
    """One tmux's version and its (state, question, lines)."""
    TMUX[0] = binary
    subprocess.run([binary, "-L", SOCKET, "kill-server"], capture_output=True)
    tmux("-f", "/dev/null", "new-session", "-d", "-s", "main", "-n", "sh", "-x", "80", "-y", "24",
         "sh -c \"seq -f 'line %g' 200 | head -c -1; sleep 600\"")
    time.sleep(1)
    version = tmux("display-message", "-p", "#{version}").strip()
    steps = []

    def record(state):
        for q in QUESTIONS:
            steps.append((state, q, ask(q)))

    record("attached")
    tmux("copy-mode", "-t", "%0")
    record("copy mode")
    for _ in range(30):
        tmux("send-keys", "-t", "%0", "-X", "cursor-up")
    record("30 up")
    tmux("send-keys", "-t", "%0", "-X", "cursor-up")
    record("31 up")
    subprocess.run([binary, "-L", SOCKET, "kill-server"], capture_output=True)
    return version, steps


def main():
    recordings = [recorded(t) for t in TMUXES]

    def geng(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

    rows = []
    for version, steps in recordings:
        for state, q, lines in steps:
            rows.append("{ version = " + geng(version) + ", state = " + geng(state) + ", command = " + geng(q) + ", lines = [ "
                        + ", ".join(geng(l) for l in lines) + " ] }")
    out = [
        "module RealTmux exposing (versions, answers)",
        "",
        "{-| Real tmuxes' answers to puritty's questions in FakeTmux's tests'",
        "states (docs/tmux.md TM68). Written by app/tests/record-tmux.py; do not edit. -}",
        "",
        "",
        "versions : Array String",
        "versions =",
        "    [ " + ", ".join(geng(v) for v, _ in recordings) + " ]",
        "",
        "",
        "answers : Array { version : String, state : String, command : String, lines : Array String }",
        "answers =",
        "    [ " + "\n    , ".join(rows),
        "    ]",
        "",
    ]
    (HERE / "src" / "RealTmux.geng").write_text("\n".join(out))
    for version, steps in recordings:
        print(f"{len(steps)} answers from tmux {version}")


main()

#!/usr/bin/env python3
"""src/RealTmux.geng: real tmuxes' answers to puritty's questions, in the
states FakeTmux's tests use (docs/tmux.md TM68, TM69), so that a test can
hold the fake's answers to tmux's.

A server is started with one 80x24 pane that has printed `line 1` to
`line 200` and no last newline, and a control client attached to it
(`tmux -C attach`), through which every question is asked, as puritty
asks through its own; then copy mode is entered and the cursor moved up
30 times, then once more. At each state the questions are asked and
their lines recorded: puritty's own (QUESTIONS below), and those in
`tmux-questions.txt`, one `STATE<TAB>COMMAND` a line, which are what
puritty asks in the tests' scenarios (a test lists any it asks that are
not recorded, to be added there). `list-keys` is recorded whole.

What differs from run to run is written as the fake gives it: the host's
name as `host`, the control client's name as `client-0`, the session's and
window's times as 1700000000, and those times shown by `t/p:` as `12:00`.
`list-commands`' table is recorded whole too.

Run it when tmux, a question or the fake changes:

    app/tests/record-tmux.py [TMUX...]

Each tmux is recorded, its answers marked with its version; by default the
3.8 the comparison harness uses and the 3.6a beside it, the two versions
TmuxMode answers differently.
"""
import shlex
import socket
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

# puritty's questions, as TmuxMode asks them (windowQuery, tabsQuery,
# panesQuery, infoOf, modeFormat, copyFormat)
QUESTIONS = [
    "display-message -p 'W #{window_id} #{pane_id} #{window_visible_layout} #{window_name}'",
    "list-windows -F 'T #{window_id} #{window_index} #{window_name}'",
    "list-panes -s -F 'P #{pane_id}'",
    "display-message -p -t %0 'P #{pane_id} #{pane_width} #{pane_height} #{cursor_x} #{cursor_y} #{alternate_on} #{scroll_region_upper} #{scroll_region_lower}'",
    "display-message -p -t %0 'M #{pane_id} #{pane_mode} #{mode-keys}'",
    "display-message -p -t %0 'C #{pane_id} #{scroll_position} #{history_size} #{copy_cursor_x} #{copy_cursor_y} #{selection_present}'",
]


def extra_questions():
    """`tmux-questions.txt`: (state, command), in the file's order."""
    path = HERE / "tmux-questions.txt"
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                state, _, command = line.partition("\t")
                out.append((state, command))
    return out


def commands_in(line):
    """How many commands a line holds: one more than its `;` outside
    quotes and braces, as tmux splits it."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=";")
    lex.whitespace_split = True
    depth, count = 0, 1
    for token in lex:
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        elif token == ";" and depth == 0:
            count += 1
    return count


class Control:
    """A control-mode client: a command written, its block's lines read."""

    def __init__(self, tmux):
        self.p = subprocess.Popen([tmux, "-L", SOCKET, "-C", "attach", "-t", "main"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.ask("refresh-client -C 80x24")
        # as puritty's client asks when it attaches (Tmux.Command)
        self.ask("refresh-client -f new-layouts,pause-after=5")

    def ask(self, command):
        """The lines of every reply the command line gets, one block for
        each of its commands (`a ; b`), in order."""
        self.p.stdin.write(command + "\n")
        self.p.stdin.flush()
        out = []
        for _ in range(commands_in(command)):
            out += self.block(command)
        return out

    def block(self, command):
        lines, inside = [], False
        while True:
            line = self.p.stdout.readline()
            if line == "":
                raise RuntimeError(f"the control client ended asking {command!r}")
            line = line.rstrip("\n")
            # a block this client's command began has flags 1; the
            # attach's own has 0
            if line.startswith("%begin ") and line.split()[-1] == "1":
                inside, lines = True, []
            elif inside and (line.startswith("%end ") or line.startswith("%error ")):
                return lines
            elif inside:
                lines.append(line)

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


def recorded(binary):
    """One tmux's version, its (state, question, lines) and its list-keys."""
    def tmux(*args):
        return subprocess.run([binary, "-L", SOCKET, *args], capture_output=True, text=True, check=True).stdout

    subprocess.run([binary, "-L", SOCKET, "kill-server"], capture_output=True)
    tmux("-f", "/dev/null", "new-session", "-d", "-s", "main", "-n", "sh", "-x", "80", "-y", "24",
         "sh -c \"seq -f 'line %g' 200 | head -c -1; sleep 600\"")
    time.sleep(1)
    control = Control(binary)
    version = control.ask("display-message -p '#{version}'")[0]
    times = control.ask("display-message -p '#{session_activity} #{window_activity} #{session_created} #{pane_activity}'")[0].split()
    shown = [control.ask(f"display-message -p '#{{t/p:{v}}}'")[0] for v in
             ("session_activity", "window_activity", "session_created")]
    host = socket.gethostname().split(".")[0]
    client = control.ask("display-message -p '#{client_name}'")[0]

    def normal(line):
        for t in times:
            if t:
                line = line.replace(t, "1700000000")
        for s in shown:
            if s:
                line = line.replace(s, "12:00")
        return line.replace(client, "client-0").replace(host, "host")

    extra = extra_questions()
    steps = []

    def record(state):
        for q in QUESTIONS + [c for s, c in extra if s == state]:
            steps.append((state, q, [normal(l) for l in control.ask(q)]))

    record("attached")
    keys = control.ask("list-keys")
    commands = control.ask("list-commands -F '#{command_list_name}\t#{command_list_alias}'")
    control.ask("copy-mode -t %0")
    record("copy mode")
    for _ in range(30):
        control.ask("send-keys -t %0 -X cursor-up")
    record("30 up")
    control.ask("send-keys -t %0 -X cursor-up")
    record("31 up")
    control.close()
    subprocess.run([binary, "-L", SOCKET, "kill-server"], capture_output=True)
    return version, steps, keys, commands


def geng(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    recordings = [recorded(t) for t in TMUXES]
    rows = []
    for version, steps, _, _ in recordings:
        for state, q, lines in steps:
            rows.append("{ version = " + geng(version) + ", state = " + geng(state) + ", command = " + geng(q) + ", lines = [ "
                        + ", ".join(geng(l) for l in lines) + " ] }")
    def table(index):
        out = []
        for rec in recordings:
            out.append("{ version = " + geng(rec[0]) + "\n      , lines =\n            [ "
                       + "\n            , ".join(geng(l) for l in rec[index]) + "\n            ]\n      }")
        return out
    key_rows = table(2)
    command_rows = table(3)
    out = [
        "module RealTmux exposing (versions, answers, keys, commands)",
        "",
        "{-| Real tmuxes' answers to puritty's questions in FakeTmux's tests'",
        "states, asked through a control client (docs/tmux.md TM68, TM69), and",
        "their default key bindings. Written by app/tests/record-tmux.py; do",
        "not edit. -}",
        "",
        "",
        "versions : Array String",
        "versions =",
        "    [ " + ", ".join(geng(rec[0]) for rec in recordings) + " ]",
        "",
        "",
        "answers : Array { version : String, state : String, command : String, lines : Array String }",
        "answers =",
        "    [ " + "\n    , ".join(rows),
        "    ]",
        "",
        "",
        "{-| `list-keys`, as each version answers it with no configuration. -}",
        "keys : Array { version : String, lines : Array String }",
        "keys =",
        "    [ " + "\n    , ".join(key_rows),
        "    ]",
        "",
        "",
        "{-| `list-commands`' table, each command's name and alias, a tab between. -}",
        "commands : Array { version : String, lines : Array String }",
        "commands =",
        "    [ " + "\n    , ".join(command_rows),
        "    ]",
        "",
    ]
    (HERE / "src" / "RealTmux.geng").write_text("\n".join(out))
    for version, steps, keys, commands in recordings:
        print(f"{len(steps)} answers, {len(keys)} bindings and {len(commands)} commands from tmux {version}")


main()

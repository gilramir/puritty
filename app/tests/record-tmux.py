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
3.8 the comparison harness uses and 3.6a, 3.4, 3.2a, 3.0 and 2.7, one of
each step that changes what puritty asks (docs/tmux-versions.md TV8), the
older built by tmux-versions/releases.sh. The first is the newest: what
each lacks of its variables and options is written from the dumps.
"""
import re
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
] + [str(Path.home() / ".cache/puritty/tmux/build" / v / "bin/tmux") for v in ("3.4", "3.2a", "3.0", "2.7")]
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
        # the size in both forms: 3.0's, and 2.x's (TM72); the one a tmux
        # does not take is refused
        self.ask("refresh-client -C 80x24")
        self.ask("refresh-client -C 80,24")
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
        line = re.sub(r"\b\d\d:\d\d \d\d-[A-Z][a-z]{2}-\d\d\b", "12:00 01-Jan-70", line)
        return line.replace(client, "client-0").replace(host, "host")

    extra = extra_questions()
    steps = []

    def record(state):
        for q in QUESTIONS + [c for s, c in extra if s == state]:
            steps.append((state, q, [normal(l) for l in control.ask(q)]))

    record("attached")
    # each option's value as a format gives it (`#{status-style}`), which
    # the fake answers on this version; strftime's time written as the
    # fake writes it (`T:`)
    options = [(o, normal(control.ask(f"display-message -p '#{{{o}}}'")[0]))
               for o in option_names(version)]
    keys = control.ask("list-keys")
    # each command's usage line, as `list-commands` with no format gives it:
    # its name, alias and flags (TM72)
    commands = control.ask("list-commands")
    control.ask("copy-mode -t %0")
    record("copy mode")
    for _ in range(30):
        control.ask("send-keys -t %0 -X cursor-up")
    record("30 up")
    control.ask("send-keys -t %0 -X cursor-up")
    record("31 up")
    control.close()
    subprocess.run([binary, "-L", SOCKET, "kill-server"], capture_output=True)
    return version, steps, keys, commands, options


def option_names(version):
    """The options this version has, from its dump in corpus/tmux, an
    array option's items each by its index (`status-format[0]`)."""
    d = HERE.parent.parent / "corpus" / "tmux" / version
    out = []
    for f in sorted(d.glob("options-*.txt")):
        out += [l.split(" ", 1)[0] for l in f.read_text().splitlines() if l.strip()]
    return list(dict.fromkeys(out))


def names(version):
    """The variables and options this version has, from its dump in
    corpus/tmux (docs/tmux-checks.md TK8): none when it was not dumped."""
    d = HERE.parent.parent / "corpus" / "tmux" / version
    if not d.is_dir():
        return None
    out = set((d / "variables.txt").read_text().split())
    for f in d.glob("options-*.txt"):
        out |= {l.split(" ", 1)[0] for l in f.read_text().splitlines() if l.strip()}
    return out


# what is recorded drawn, by the key after the prefix: the window's and
# the pane's menus (TM27), and the tree of windows (TM77)
MENU_KEYS = ["<", ">", "w"]


def menus(binary, outer):
    """What each of MENU_KEYS opens, as this tmux draws it to a client of
    its own run in a pane of `outer` (the newest tmux), with no
    configuration: a menu's rows inside its box, trimmed, none where the
    key opens no menu (before 3.0); the tree's rows as they are."""
    out = {}
    for key in MENU_KEYS:
        inner, host = "puritty-record-menu", "puritty-record-outer"
        subprocess.run([binary, "-L", inner, "kill-server"], capture_output=True)
        subprocess.run([outer, "-L", host, "kill-server"], capture_output=True)
        subprocess.run([binary, "-L", inner, "-f", "/dev/null", "new-session", "-d", "-s", "main", "-n", "sh",
                        "-x", "80", "-y", "24", "sh"], check=True)
        subprocess.run([outer, "-L", host, "-f", "/dev/null", "new-session", "-d", "-x", "80", "-y", "25",
                        f"env -u TMUX TERM=xterm-256color {binary} -L {inner} attach"], check=True)
        time.sleep(1)
        subprocess.run([outer, "-L", host, "send-keys", "C-b", key], check=True)
        time.sleep(1)
        screen = subprocess.run([outer, "-L", host, "capture-pane", "-p"], capture_output=True, text=True, check=True).stdout
        if key == "w":
            # the tree's rows, down to the first empty one, the host's name
            # as the fake gives it
            rows = []
            for row in screen.splitlines():
                if not row.strip():
                    break
                rows.append(row.rstrip().replace(socket.gethostname().split(".")[0], "host"))
            out[key] = rows
        else:
            out[key] = [row.split("│")[1].strip() for row in screen.splitlines() if row.count("│") >= 2]
        subprocess.run([outer, "-L", host, "kill-server"], capture_output=True)
        subprocess.run([binary, "-L", inner, "kill-server"], capture_output=True)
    return out


def geng(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    recordings = [recorded(t) for t in TMUXES]
    drawn = [menus(t, TMUXES[0]) for t in TMUXES]
    rows = []
    for version, steps, _, _, _ in recordings:
        for state, q, lines in steps:
            rows.append("{ version = " + geng(version) + ", state = " + geng(state) + ", command = " + geng(q) + ", lines = [ "
                        + ", ".join(geng(l) for l in lines) + " ] }")
    def table(index):
        out = []
        for rec in recordings:
            out.append("{ version = " + geng(rec[0]) + "\n      , lines =\n            [ "
                       + "\n            , ".join(geng(l) for l in rec[index]) + "\n            ]\n      }")
        return out
    # what each version lacks of the newest's variables and options, which
    # the fake answers empty, as that tmux does
    newest = names(recordings[0][0]) or set()
    lacking_rows = []
    for rec in recordings:
        has = names(rec[0])
        lacks = sorted(newest - has) if has is not None else []
        lacking_rows.append("{ version = " + geng(rec[0]) + ", names = [ " + ", ".join(geng(n) for n in lacks) + " ] }")
    option_rows = []
    for rec in recordings:
        option_rows.append("{ version = " + geng(rec[0]) + "\n      , values =\n            [ "
                           + "\n            , ".join("{ name = " + geng(o) + ", value = " + geng(v) + " }" for o, v in rec[4])
                           + "\n            ]\n      }")
    menu_rows = []
    for rec, m in zip(recordings, drawn):
        for key in MENU_KEYS:
            menu_rows.append("{ version = " + geng(rec[0]) + ", key = " + geng(key) + ", items = [ "
                             + ", ".join(geng(i) for i in m[key]) + " ] }")
    key_rows = table(2)
    command_rows = table(3)
    out = [
        "module RealTmux exposing (answers, asked, commands, keys, lacking, menus, options, versions)",
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
        "{-| The questions recorded from `tmux-questions.txt`, what the tests'",
        "scenarios ask: each version's answers to them are held to the fake's",
        "only where that version's scenarios ask them. -}",
        "asked : Array String",
        "asked =",
        "    [ " + "\n    , ".join(geng(c) for c in dict.fromkeys(c for _, c in extra_questions())) + "\n    ]" if extra_questions() else "    []",
        "",
        "",
        "{-| The variables and options of the first version that each one lacks,",
        "from its dump in corpus/tmux (docs/tmux-checks.md TK8). -}",
        "lacking : Array { version : String, names : Array String }",
        "lacking =",
        "    [ " + "\n    , ".join(lacking_rows),
        "    ]",
        "",
        "",
        "{-| Each version's options with no configuration, as a format gives",
        "them (`#{status-style}`). -}",
        "options : Array { version : String, values : Array { name : String, value : String } }",
        "options =",
        "    [ " + "\n    , ".join(option_rows),
        "    ]",
        "",
        "",
        "{-| The menus each version draws for the prefix and a key, with no",
        "configuration, the items as their rows show them; none where the key",
        "opens no menu. -}",
        "menus : Array { version : String, key : String, items : Array String }",
        "menus =",
        "    [ " + "\n    , ".join(menu_rows),
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
        "{-| `list-commands`' usage lines: each command's name, alias and flags. -}",
        "commands : Array { version : String, lines : Array String }",
        "commands =",
        "    [ " + "\n    , ".join(command_rows),
        "    ]",
        "",
    ]
    (HERE / "src" / "RealTmux.geng").write_text("\n".join(out))
    # formatted as the rest of puritty (scripts/fmt.sh), so that the module
    # recorded again is the same text
    subprocess.run([str(HERE.parent.parent / "scripts" / "fmt.sh"), str(HERE / "src" / "RealTmux.geng")],
                   check=True, stdout=subprocess.DEVNULL)
    for version, steps, keys, commands, _ in recordings:
        print(f"{len(steps)} answers, {len(keys)} bindings and {len(commands)} commands from tmux {version}")


if __name__ == "__main__":
    main()

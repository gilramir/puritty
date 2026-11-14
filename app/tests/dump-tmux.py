#!/usr/bin/env python3
"""One tmux's answers, written out whole for the version survey
(docs/tmux-versions.md): what it is, its commands, its default keys and
options, every format variable's value, puritty's own questions in the
test states (record-tmux.py's), and a control-mode session.

    app/tests/dump-tmux.py TMUX OUT-DIR [NAME]

Each file is text, one line a thing, so that two versions' folders are
compared with `diff -r`. What differs from run to run, not from version to
version, is written as the fake tmux gives it (record-tmux.py): the host as
`host`, times as 1700000000, a client as `client-0`, and pids, ttys, the
socket and the user's directories by name.

It runs inside a container with that tmux (app/tests/tmux-versions/), and
needs Python 3.6 or later and nothing else.
"""

import os
import re
import select
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOCKET = "puritty-dump"

# every format variable tmux 3.8's manual lists (FORMATS), and those
# puritty asks that it does not; a tmux without one answers it empty
FORMATS = (HERE / "tmux-versions" / "formats.txt").read_text().split()


def run(tmux, *args, check=True):
    p = subprocess.run([tmux, "-L", SOCKET] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    if check and p.returncode != 0:
        raise RuntimeError("tmux " + " ".join(args) + ": " + p.stderr.strip())
    return p


class Client:
    """A control-mode client (`tmux -C attach`): a command line written,
    every line read until it has been answered and tmux is quiet."""

    def __init__(self, tmux):
        self.p = subprocess.Popen([tmux, "-L", SOCKET, "-C", "attach", "-t", "main"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.buffer = b""
        self.ended = False

    def lines(self, quiet=0.4, limit=10.0):
        """The lines tmux writes until it has said nothing for `quiet`
        seconds."""
        out = []
        start = time.time()
        while time.time() - start < limit:
            ready, _, _ = select.select([self.p.stdout], [], [], quiet)
            if not ready:
                break
            chunk = os.read(self.p.stdout.fileno(), 65536)
            if not chunk:
                self.ended = True
                break
            self.buffer += chunk
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                out.append(line.decode("utf-8", "backslashreplace"))
        return out

    def send(self, command):
        self.p.stdin.write((command + "\n").encode())
        return self.lines()

    def ask(self, command):
        """One command's answer: the lines of its block, or `%error` and
        its lines."""
        out, inside, answer = [], False, []
        self.p.stdin.write((command + "\n").encode())
        start = time.time()
        while time.time() - start < 10:
            for line in self.lines(quiet=0.05, limit=0.5):
                if line.startswith("%begin ") and line.split()[-1] == "1":
                    inside, answer = True, []
                elif inside and line.startswith("%end "):
                    return answer
                elif inside and line.startswith("%error "):
                    return ["%error"] + answer
                elif inside:
                    answer.append(line)
        raise RuntimeError("no answer to " + command)

    def close(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        self.p.wait(timeout=10)


class Normal:
    """What differs from run to run, written the same in every dump."""

    def __init__(self):
        self.pairs = []

    def add(self, value, name):
        # a number is replaced only as its own variable's value (KEYED),
        # since a short one is in other text too: a pid of 13 in `\134`
        if value and len(value) > 3 and not value.isdigit():
            self.pairs.append((value, name))
            self.pairs.sort(key=lambda p: -len(p[0]))

    def __call__(self, line):
        m = re.match(r"^([a-z_]+)([=\t])", line)
        if m and m.group(1) in KEYED:
            return m.group(1) + m.group(2) + KEYED[m.group(1)]
        for value, name in self.pairs:
            line = line.replace(value, name)
        # how many times a pane's output came, which depends on timing
        line = re.sub(r"(pane_output_generation[=\t])\d+", r"\1N", line)
        # any other time of this run, as seconds since 1970
        return re.sub(r"\b1[6-9]\d{8}\b", "1700000000", line)


# variables whose value is this run's, written by name in formats.txt
KEYED = {
    "pid": "PID", "pane_pid": "PANE-PID", "client_pid": "CLIENT-PID", "pane_tty": "PANE-TTY",
    "client_tty": "client-0", "client_name": "client-0", "uid": "UID", "user": "USER", "socket_path": "SOCKET",
    "start_time": "1700000000", "pane_current_path": "HOME", "session_path": "HOME", "host": "host",
    "host_short": "host",
}


def start(tmux):
    run(tmux, "kill-server", check=False)
    env_shell = "env PS1='$ ' ENV= sh"
    run(tmux, "-f", "/dev/null", "new-session", "-d", "-s", "main", "-n", "sh", "-x", "80", "-y", "24",
        "sh -c \"seq -f 'line %g' 200 | head -c -1; sleep 600\"")
    run(tmux, "set-option", "-g", "default-command", env_shell)
    time.sleep(0.5)


def write(out, name, lines):
    (out / name).write_text("".join(l + "\n" for l in lines))


def dump(tmux, out, name):
    out.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([tmux, "-V"], stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
    start(tmux)
    client = Client(tmux)
    client.lines(quiet=1.0)
    normal = Normal()
    learn(client, normal)
    normal.add(socket.gethostname(), "host")
    normal.add(socket.gethostname().split(".")[0], "host")
    normal.add(os.environ.get("HOME", ""), "HOME")

    write(out, "about.txt", [version, name])
    write(out, "commands.txt", [normal(l) for l in run(tmux, "list-commands").stdout.splitlines()])
    write(out, "keys.txt", [normal(l) for l in run(tmux, "list-keys").stdout.splitlines()])
    for scope, flags in [("server", ["-s"]), ("session", ["-g"]), ("window", ["-gw"]), ("pane", ["-gp"])]:
        p = run(tmux, "show-options", *flags, check=False)
        write(out, "options-" + scope + ".txt",
              [normal(l) for l in p.stdout.splitlines()] if p.returncode == 0 else ["%error " + p.stderr.strip()])

    # every format variable, as `display-message -p` gives it in the
    # attached control client; one that ends the server is said so, and
    # the server started again for the next
    values = []
    for f in FORMATS:
        try:
            values.append(normal(f + "\t" + " | ".join(client.ask("display-message -p -t %0 '#{" + f + "}'"))))
        except (RuntimeError, OSError):
            values.append(f + "\t%no answer: " + ("the server ended" if run(tmux, "has-session", check=False).returncode != 0 else "none came"))
            client.close()
            start(tmux)
            client = Client(tmux)
            client.lines(quiet=1.0)
            learn(client, normal)
    write(out, "formats.txt", values)
    # and all of them by `display -a`, where this tmux has it
    every = client.ask("display-message -a -t %0")
    write(out, "formats-all.txt", sorted(normal(l) for l in every) if every[:1] != ["%error"] else every)

    session = control_session(client, normal)
    client.close()
    run(tmux, "kill-server", check=False)
    write(out, "control.txt", session)

    # puritty's questions in the test states, as record-tmux.py asks them
    sys.path.insert(0, str(HERE))
    record = __import__("record-tmux")
    try:
        _, steps, _, _ = record.recorded(tmux)
        write(out, "answers.txt", [state + "\t" + q + "\n" + "".join("    " + l + "\n" for l in lines).rstrip("\n")
                                   for state, q, lines in steps])
    except Exception as e:  # an old tmux may not answer a question at all
        write(out, "answers.txt", ["%failed " + str(e)])


def learn(client, normal):
    """This run's pids, names and times, for `normal` to write as names."""
    for v, label in [
        ("#{pid}", "PID"), ("#{socket_path}", "SOCKET"), ("#{client_name}", "client-0"),
        ("#{client_tty}", "client-0"), ("#{client_pid}", "CLIENT-PID"), ("#{pane_pid}", "PANE-PID"),
        ("#{pane_tty}", "PANE-TTY"), ("#{host}", "host"), ("#{host_short}", "host"), ("#{user}", "USER"),
        ("#{uid}", "UID"), ("#{session_path}", "HOME"), ("#{pane_current_path}", "HOME"),
        ("#{start_time}", "1700000000"), ("#{session_created}", "1700000000"),
        ("#{t/p:session_created}", "12:00"), ("#{t/p:session_activity}", "12:00"),
        ("#{t/p:window_activity}", "12:00"), ("#{session_created_string}", "TIME"),
        ("#{session_activity_string}", "TIME"), ("#{window_activity_string}", "TIME"),
        ("#{client_created_string}", "TIME"), ("#{client_activity_string}", "TIME"),
    ]:
        answer = client.ask("display-message -p '" + v + "'")
        if answer and answer[0] != "%error":
            normal.add(answer[0], label)


# A control-mode session: each step's command line, then every line tmux
# wrote until it was quiet. `%output` is kept as tmux wrote it, its octal
# escapes and all, but the output of one pane in one step is joined, since
# how tmux splits it differs from run to run.
STEPS = [
    "refresh-client -C 80x24",
    "refresh-client -f new-layouts,pause-after=5",
    "refresh-client -B 'name:%0:#{pane_title}'",
    "send-keys -t %0 Escape",
    "split-window -h -t %0",
    "send-keys -t %1 'printf \"\\033[?25l\\033[?1049h\\033[?2004h\\033]0;titled\\007hi\"' Enter",
    "resize-pane -t %1 -x 30",
    "select-pane -t %0",
    "new-window -n second",
    "rename-window -t @1 renamed",
    "select-window -t @0",
    "copy-mode -t %0",
    "send-keys -t %0 -X cursor-up",
    "send-keys -t %0 -X cancel",
    "set-option -g status-left 'L'",
    "set-option -w -t @0 automatic-rename off",
    "set-buffer -b one hello",
    "list-buffers -F '#{buffer_name} #{buffer_size}'",
    "list-windows -F '#{window_id} #{window_index} #{window_name} #{window_layout} #{window_visible_layout}'",
    "list-panes -s -F '#{pane_id} #{pane_width} #{pane_height} #{cursor_x} #{cursor_y} #{cursor_flag} #{alternate_on} [#{pane_private_modes}] #{pane_title}'",
    "kill-pane -t %1",
    "kill-window -t @1",
    # named, since a name from its program comes when tmux next looks,
    # which differs from run to run
    "new-session -d -s other -n other",
    "switch-client -t other",
    "switch-client -t main",
    "kill-session -t other",
    "detach-client",
]


def control_session(client, normal):
    out = []
    for step in STEPS:
        out.append("> " + step)
        lines = client.send(step)
        joined = []
        for line in lines:
            m = re.match(r"^%(output|extended-output) (%\d+)( \d+ :)? (.*)$", line)
            if m and joined and joined[-1][0] == m.group(2):
                joined[-1] = (m.group(2), joined[-1][1] + m.group(4))
            elif m:
                joined.append((m.group(2), m.group(4)))
            else:
                joined.append((None, line))
        for pane, text in joined:
            line = "%output " + pane + " " + text if pane else text
            # a block's number and time differ from run to run
            line = re.sub(r"^%(begin|end|error) \d+ \d+ (\d)$", r"%\1 TIME N \2", line)
            out.append("  " + normal(line))
        if client.ended:
            out.append("  (the client ended)")
            break
    return out


if __name__ == "__main__":
    tmux, out = sys.argv[1], Path(sys.argv[2])
    dump(tmux, out, sys.argv[3] if len(sys.argv) > 3 else tmux)

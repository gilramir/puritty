#!/usr/bin/env python3
"""src/Keys27Recorded.geng: what the real tmux 2.7 (and 2.8, 2.9, 2.9a)
writes to a pane for each of a few hundred `send-keys` lines, so that the
model of it (`Tmux27`, puritty docs/tmux-checks.md TK3.3) is held to the
binary and not only to a reading of its source.

The lines are made here, not by puritty: lines of the form
`sendBytesPlain` makes for every byte below 0x80 and some UTF-8, and lines
for each branch of the model (quotes and their escapes, `;` and `\\;`, a
comment, getopt's `--` and `-`, the key names). Each is sent by a control
client (`tmux -C attach`) to a pane whose program is `cat` on a raw
terminal writing to a file; a `display-message` after each line answers
only when tmux has run it, and the file is read once it stops growing.
Every tmux built (releases.sh, ~/.cache/puritty/tmux/build) from 2.7 to
2.9a is recorded, in its container; the module holds 2.7's, and the
script fails if another wrote anything different.

    record-keys27.py           record and write src/Keys27Recorded.geng
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "puritty" / "tmux"
VERSIONS = ["2.7", "2.8", "2.9", "2.9a"]


def quote_runs(text):
    """sendBytesPlain's words for text: single-quoted runs, ' as "'", ; as \\;."""
    words, run = [], ""
    for c in text:
        if c in ";'":
            if run:
                words.append("'" + run + "'")
                run = ""
            words.append("\\;" if c == ";" else "\"'\"")
        else:
            run += c
    if run:
        words.append("'" + run + "'")
    return " ".join(words)


NAMES = {0: "C-@", 9: "Tab", 13: "Enter", 27: "Escape", 0x1C: "'C-\\'", 0x1D: "'C-]'", 0x1E: "'C-^'", 0x1F: "'C-_'", 0x7F: "BSpace"}


def cases():
    lines = []
    t = "send-keys -t '%0'"
    # the encoder's forms: each byte below 0x80
    for b in range(0x80):
        if b < 0x20 or b == 0x7F:
            name = NAMES.get(b) or "C-" + chr(b + 0x60)
            lines.append(f"{t} {name}")
        else:
            lines.append(f"{t} -l -- {quote_runs(chr(b))}")
    # text runs: UTF-8, quotes, ;, a leading -, spaces
    for text in ["ls -l", "é한", "😀", "\u0085", "a;b", "it's", ";", "'", ";;", "'a'", "-la", "--", "-", "- x",
                 "a\\", "\\;", "#x", "$HOME", "~", "a b  c", "\"q\"", "{}", "x;", "\u00a0", "\ufeff", "\U0010fffd"]:
        lines.append(f"{t} -l -- {quote_runs(text)}")
    # the model's branches, as lines puritty does not send
    lines += [
        f"{t} -l '-la'", f"{t} -l '--x'", f"{t} -l '-'", f"{t} -l -l-", f"{t} -l '--' '--'",
        f"{t} -l \"a\\eb\"", f"{t} -l \"\\r\\n\\t\\x\\\"\\\\\"", f"{t} -l \"\\003\"", f"{t} -l ''", f"{t} -l '' 'a'",
        f"{t} -l a\\;", f"{t} -l a;", f"{t} -l 'a;'", f"{t} -l \"a;\"", f"{t} -l a \\; b", f"{t} -l a ; send-keys -t '%0' -l b",
        f"{t} -l a # b", f"{t} -l a#b", f"{t} -l 'a#b'", f"{t} -l a\\b", f"{t} -l 'unclosed", f"{t} -l \"unclosed",
        f"{t} -x a", f"{t} -t", f"{t} -lt '%0' z", f"{t} -l 'é' 'x'", f"{t} -l\t'tab'",
    ]
    for k in ["C-a", "c-a", "C-z", "C-@", "C-[", "'C-\\'", "C-]", "C-^", "C-_", "C-?", "C-Space", "Tab", "tab", "Enter", "ENTER",
              "Escape", "BSpace", "bspace", "a", "~a", "'~'", "None", "é", "한"]:
        lines.append(f"{t} {k}")
    return lines


INSIDE = r'''
import json, os, select, subprocess, sys, time
tmux = sys.argv[1]
cases = json.load(open("/work/cases.json"))
os.environ["TMUX_TMPDIR"] = "/tmp/k"
os.makedirs("/tmp/k", exist_ok=True)
out = "/tmp/pane.bin"
subprocess.run([tmux, "-f", "/dev/null", "new-session", "-d", "-s", "k", "-x", "80", "-y", "24",
                "stty raw -echo -iexten; exec cat > " + out], check=True)
for _ in range(100):
    if os.path.exists(out):
        break
    time.sleep(0.05)
time.sleep(0.3)
c = subprocess.Popen([tmux, "-C", "attach", "-t", "k"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
fd = c.stdout.fileno()
os.set_blocking(fd, False)
buf = b""
def until(marker, limit=5.0):
    global buf
    end = time.time() + limit
    while marker not in buf and time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                buf += os.read(fd, 65536)
            except BlockingIOError:
                pass
    found = marker in buf
    buf = buf[buf.index(marker) + len(marker):] if found else b""
    return found
def size():
    return os.path.getsize(out)
results = []
for i, line in enumerate(cases):
    before = size()
    c.stdin.write(line.encode() + b"\n" + ("display-message -p 'SYNC%d'\n" % i).encode())
    c.stdin.flush()
    if not until(b"SYNC%d" % i):
        results.append(None)
        continue
    last, still = size(), 0
    while still < 4:
        time.sleep(0.02)
        now = size()
        still = still + 1 if now == last else 0
        last = now
    with open(out, "rb") as f:
        f.seek(before)
        results.append(f.read().hex())
json.dump(results, open("/work/results.json", "w"))
c.stdin.write(b"kill-server\n")
c.stdin.flush()
'''


def record(version, lines, work):
    (work / "cases.json").write_text(json.dumps(lines))
    (work / "inside.py").write_text(INSIDE)
    tmux = f"/cache/build/{version}/bin/tmux"
    subprocess.run(["podman", "run", "--rm", "-v", f"{CACHE}:/cache:ro", "-v", f"{work}:/work",
                    "puritty-tmux-versions", "sh", "-c", f"cd /tmp && HOME=/tmp LANG=C.UTF-8 python3 /work/inside.py {tmux}"],
                   check=True)
    return json.loads((work / "results.json").read_text())


def geng(text):
    out = ""
    for c in text:
        if c in "\\\"":
            out += "\\" + c
        elif ord(c) < 0x20 or ord(c) == 0x7F or ord(c) > 0x7E:
            out += "\\u{%04X}" % ord(c)
        else:
            out += c
    return '"' + out + '"'


def main():
    lines = cases()
    work = ROOT / ".harness-work" / "keys27"
    work.mkdir(parents=True, exist_ok=True)
    got = {}
    for v in VERSIONS:
        got[v] = record(v, lines, work)
        print(f"{v}: {sum(r is not None for r in got[v])} of {len(lines)} lines answered")
    differ = [(v, lines[i], got["2.7"][i], r) for v in VERSIONS[1:] for i, r in enumerate(got[v]) if r != got["2.7"][i]]
    for v, line, a, b in differ:
        print(f"{v} differs from 2.7 on {line!r}: {b} where 2.7 wrote {a}")
    rows = [f"{{ line = {geng(l)}, wrote = \"{r}\" }}" for l, r in zip(lines, got["2.7"]) if r is not None]
    text = "\n".join([
        "module Keys27Recorded exposing (recorded)",
        "",
        "{-| What tmux 2.7 wrote to a raw pane for each line (record-keys27.py;",
        "docs/tmux-checks.md TK3.3), its bytes in hex. Written by",
        "record-keys27.py; do not edit. -}",
        "",
        "",
        "recorded : Array { line : String, wrote : String }",
        "recorded =",
        "    [ " + "\n    , ".join(rows),
        "    ]",
        "",
    ])
    (HERE / "src" / "Keys27Recorded.geng").write_text(text)
    subprocess.run([str(ROOT / "scripts" / "fmt.sh"), str(HERE / "src" / "Keys27Recorded.geng")], check=True)
    print(f"wrote src/Keys27Recorded.geng: {len(rows)} lines")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())

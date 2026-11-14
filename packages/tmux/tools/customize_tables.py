#!/usr/bin/env python3
"""Generate Tmux/CustomizeTables.geng: what tmux's customize mode knows
that no tmux command reports (docs/tmux.md TM62).

customize-mode shows each option's description, type, choices, unit and
default, and each key's default binding. A control client can ask tmux for
the values in force (`show-options`, `list-keys`) but not for those, so
puritty carries them, per tmux version, made here from tmux's own source
and a fresh server of the same version:

- the option table: options-table.c run through the C preprocessor (for
  the hook macros), then each entry's fields read;
- the defaults: a server started with no configuration, every option unset
  globally (which sets tmux's table default, as customize-mode's
  `options_default_to_string` reads it, rather than what the server set at
  start, such as default-shell), then `show-options` answered in the same
  form puritty reads at run time;
- the default keys: that server's `list-keys` (and its notes), again in the
  form puritty asks for on that version.

  python3 packages/tmux/tools/customize_tables.py \\
      36=SRC-3.6a:BIN-3.6a 38=SRC-3.8:BIN-3.8 > packages/tmux/src/Tmux/CustomizeTables.geng
  scripts/fmt.sh packages/tmux/src/Tmux/CustomizeTables.geng
"""

import os
import re
import subprocess
import sys
import tempfile

TYPES = {
    "OPTIONS_TABLE_STRING": "string",
    "OPTIONS_TABLE_NUMBER": "number",
    "OPTIONS_TABLE_KEY": "key",
    "OPTIONS_TABLE_COLOUR": "colour",
    "OPTIONS_TABLE_FLAG": "flag",
    "OPTIONS_TABLE_CHOICE": "choice",
    "OPTIONS_TABLE_COMMAND": "command",
}

STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


def c_string(text):
    """Adjacent C string literals joined, escapes read."""
    out = []
    for m in STRING.finditer(text):
        s = m.group(1)
        s = re.sub(r'\\(.)', lambda e: {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(e.group(1), e.group(1)), s)
        out.append(s)
    return "".join(out)


def choice_lists(source):
    lists = {}
    for m in re.finditer(r'static const char \*(options_table_\w+_list)\[\] = \{(.*?)\};', source, re.S):
        lists[m.group(1)] = [c_string(x) for x in re.findall(r'"(?:[^"\\]|\\.)*"', m.group(2))]
    return lists


def entries(source):
    """The option table's entries, its hook macros expanded."""
    start = source.index("/* Helpers for hook options. */")
    end = source.index("{ .name = NULL }", start)
    chunk = source[start:end]
    # only the hook macros matter; everything else cpp leaves alone
    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
        f.write(chunk)
        path = f.name
    try:
        expanded = subprocess.run(["cpp", "-P", path], capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(path)
    body = expanded[expanded.index("options_table[] = {") + len("options_table[] = {"):]
    found = []
    depth = 0
    current = None
    i = 0
    while i < len(body):
        c = body[i]
        if c == '"':
            m = STRING.match(body, i)
            if current is not None:
                current.append(m.group(0))
            i = m.end()
            continue
        if c == "{":
            depth += 1
            if depth == 1:
                current = []
                i += 1
                continue
        elif c == "}":
            depth -= 1
            if depth == 0:
                found.append("".join(current))
                current = None
                i += 1
                continue
        if current is not None:
            current.append(c)
        i += 1
    return found


def fields(entry):
    """`.name = value` pairs of an entry, top level only."""
    out = {}
    parts = re.split(r',\s*(?=\.\w+\s*=)', entry.strip().rstrip(","))
    for p in parts:
        m = re.match(r'\s*\.(\w+)\s*=\s*(.*)', p, re.S)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def option_rows(source):
    lists = choice_lists(source)
    rows = []
    for e in entries(source):
        f = fields(e)
        if "name" not in f:
            continue
        name = c_string(f["name"])
        kind = TYPES[f["type"].strip()]
        scope = f.get("scope", "")
        scopes = "".join(
            letter for letter, flag in (("S", "SERVER"), ("s", "SESSION"), ("w", "WINDOW"), ("p", "PANE"))
            if "OPTIONS_TABLE_" + flag in scope
        )
        flags = f.get("flags", "")
        marks = "".join(
            letter for letter, flag in (("a", "IS_ARRAY"), ("h", "IS_HOOK"), ("s", "IS_STYLE"), ("c", "IS_COLOUR"))
            if "OPTIONS_TABLE_" + flag in flags
        )
        choices = lists.get(f.get("choices", "").strip(), [])
        unit = c_string(f["unit"]) if "unit" in f else ""
        text = c_string(f["text"]) if "text" in f else ""
        rows.append("\t".join(["O", name, kind, scopes, marks, unit, ",".join(choices), text]))
    return rows


def run(tmux, sock, *args):
    r = subprocess.run([tmux, "-L", sock, *args], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != "TMUX"})
    if r.returncode != 0:
        raise SystemExit(f"{tmux} {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def defaults(tmux, version, names):
    sock = f"puritty-tables-{version}-{os.getpid()}"
    run(tmux, sock, "-f", "/dev/null", "new-session", "-d", "-s", "main", "-x", "80", "-y", "24")
    try:
        for n, scope in names:
            flag = "-s" if "S" in scope else ("-gw" if ("w" in scope or "p" in scope) else "-g")
            subprocess.run([tmux, "-L", sock, "set-option", flag, "-u", n], capture_output=True)
        hooks = ["-H"] if version >= 38 else []
        shown = []
        for flag in ("-s", "-g", "-gw"):
            shown += ["D\t" + line for line in run(tmux, sock, "show-options", flag, *hooks).splitlines()]
        keys = []
        if version >= 37:
            keys += ["K\t" + line for line in run(tmux, sock, "list-keys", "-F", KEY_FORMAT).splitlines()]
        else:
            # 3.6 has no list-keys -F: its text read into the same form,
            # which tests/ checks against puritty's own reading of it
            listed = run(tmux, sock, "list-keys")
            tables = []
            for line in listed.splitlines():
                t = bind_line(line)["table"]
                if t not in tables:
                    tables.append(t)
            notes = {t: run(tmux, sock, "list-keys", "-N", "-a", "-P", "", "-T", t) for t in tables}
            if RAW is not None:
                # the raw answers, for the tests to read with puritty's own
                # parser and compare with the rows made here
                with open(os.path.join(RAW, f"CustomizeRaw{version}.geng"), "w") as f:
                    f.write(f"module CustomizeRaw{version} exposing (keys, notes)\n\n")
                    f.write(f"{{-| tmux {version // 10}.{version % 10}'s own list-keys answers on a fresh server, made with\n")
                    f.write("Tmux.CustomizeTables by `packages/tmux/tools/customize_tables.py`. -}\n\n\n")
                    f.write("keys : String\nkeys =\n" + geng_string(listed.splitlines()) + "\n\n")
                    f.write("notes : Array { table : String, text : String }\nnotes =\n    [ ")
                    f.write("\n    , ".join(f"{{ table = \"{t}\", text = notes{t.replace('-', '_')} }}" for t in tables))
                    f.write("\n    ]\n")
                    for t in tables:
                        f.write(f"\n\nnotes{t.replace('-', '_')} : String\nnotes{t.replace('-', '_')} =\n" + geng_string(notes[t].splitlines()))
            noted = {}
            for t in tables:
                for line in notes[t].splitlines():
                    k, _, note = line.strip().partition(" ")
                    noted[(t, k)] = note.strip()
            for line in listed.splitlines():
                b = bind_line(line)
                keys.append("K\t" + "\t".join([b["table"], b["key"], "1" if b["repeat"] else "0", noted.get((b["table"], b["key"]), ""), b["command"]]))
        return shown + keys
    finally:
        subprocess.run([tmux, "-L", sock, "kill-server"], capture_output=True)


# the form puritty asks for on 3.7 and later (Tmux.Customize.keyFormat)
KEY_FORMAT = "#{key_table}\t#{key_string}\t#{key_repeat}\t#{key_note}\t#{key_command}"


RAW = os.environ.get("CUSTOMIZE_RAW")


def bind_line(line):
    """`bind-key [-r] -T TABLE KEY COMMAND`: the key unquoted as tmux's
    parser would, the command as printed."""
    rest = line.split(None, 1)[1]
    repeat = False
    while True:
        rest = rest.lstrip()
        if rest.startswith("-r "):
            repeat = True
            rest = rest[3:]
        elif rest.startswith("-T "):
            table, rest = rest[3:].lstrip().split(None, 1)
        else:
            break
    i = 0
    key = []
    if rest[0] in "'\"":
        q = rest[0]
        i = 1
        while rest[i] != q:
            if q == '"' and rest[i] == "\\":
                i += 1
            key.append(rest[i])
            i += 1
        i += 1
    else:
        while i < len(rest) and not rest[i].isspace():
            if rest[i] == "\\":
                i += 1
            key.append(rest[i])
            i += 1
    return {"table": table, "key": "".join(key), "repeat": repeat, "command": rest[i:].strip()}


def identity(row):
    """What a row is about: an option's name, a default's name, a key's
    table and key; a newer version's row of the same identity is replaced."""
    f = row.split("\t")
    if f[0] == "O":
        return ("O", f[1])
    if f[0] == "D":
        return ("D", f[1].split(" ", 1)[0])
    return ("K", f[1], f[2])


def geng_string(lines):
    out = []
    for line in lines:
        out.append("    " + line.replace("\\", "\\\\").replace("\t", "\\t").replace('"""', '\\"""'))
    return "    \"\"\"\n" + "\n".join(out) + "\n    \"\"\"\n"


def main():
    pairs = []
    for arg in sys.argv[1:]:
        version, rest = arg.split("=", 1)
        src, binary = rest.split(":", 1)
        pairs.append((int(version), src, binary))
    ordered = sorted(pairs)
    newest = ordered[-1][0]
    print("module Tmux.CustomizeTables exposing (newest, older)\n")
    print("{-| What tmux's customize mode knows that no command reports (TM62):")
    print("each option's type, scope, flags, unit, choices and description, the")
    print("defaults as `show-options` prints them, and the default keys, per tmux")
    print("version: the newest whole, each older one as the rows that differ from")
    print("it (an `X` row: one it does not have). Generated by")
    print("`packages/tmux/tools/customize_tables.py` from tmux's own source")
    print("(`options-table.c`, ISC licence, Nicholas Marriott and others) and a")
    print("fresh server; do not edit. -}\n\n")
    print("{-| The newest version's table, and its version (tenths). -}")
    print("newest : { version : Int, rows : String }")
    print(f"newest =\n    {{ version = {newest}, rows = table{newest} }}\n\n")
    print("{-| The older versions' differences from the newest, newest first. -}")
    print("older : Array { version : Int, rows : String }")
    print("older =")
    olds = [v for v, _, _ in reversed(ordered[:-1])]
    print("    [ " + "\n    , ".join(f"{{ version = {v}, rows = table{v} }}" for v in olds) + "\n    ]\n\n")
    made = {}
    for v, src, binary in ordered:
        source = open(os.path.join(src, "options-table.c")).read()
        rows = option_rows(source)
        names = [(r.split("\t")[1], r.split("\t")[3]) for r in rows]
        made[v] = rows + defaults(binary, v, names)
    base ={identity(r): r for r in made[newest]}
    print(f"table{newest} : String\ntable{newest} =")
    print(geng_string(made[newest]))
    print()
    for v, _, _ in ordered[:-1]:
        own = {identity(r): r for r in made[v]}
        diff = [r for k, r in own.items() if base.get(k) != r]
        diff += ["X\t" + "\t".join(k) for k in base if k not in own]
        print(f"table{v} : String\ntable{v} =")
        print(geng_string(diff))
        print()

if __name__ == "__main__":
    main()

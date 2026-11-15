#!/usr/bin/env python3
"""puritty attached to a real tmux of each version, a second client
changing the server under it, and what puritty shows held to what tmux
has after each step (docs/tmux-checks.md TK12).

Each version's tmux runs in the survey's container (app/tests/tmux-versions,
the builds in ~/.cache/puritty/tmux/build), its socket in a folder shared
with this machine. puritty runs here on a virtual display, its program that
version's own client run in the container (`podman exec -it … -CC attach`),
so the client and the server are always the same tmux. The puppet is a
second `podman exec`: windows made, renamed, shown, split and killed;
panes killed and ended by their programs (`exit`, as Ctrl-D at a shell),
the window whose panes all end among them (window 6, TK11); a session made
and killed beside it; a window moved to another index. Then puritty's own
side: its window resized, and keys typed into it (`xdotool`), tmux's
default bindings through puritty's prompts, confirmations and menus:
copy mode, a window made, split, renamed at the prompt, a pane killed by
`prefix x` and from the pane menu, the window killed by `prefix &`, the
next and previous window.

After each step the harness waits for puritty's diagnostic log to say, in
a `tmux=` line, the same tabs, shown window, panes, sizes and panes' modes
as tmux lists (`list-windows`, `display-message`, `list-panes`), and fails
the step when it does not within a few seconds, with both.

    harness/puppet.py [VERSION ...]    each version, 2.7 3.0 3.2 3.4 3.6a 3.8 by default
    harness/puppet.py --all            every release built
"""
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "puritty" / "tmux"
WORK = ROOT / ".harness-work" / "puppet"
PURITTY = ROOT / "app" / "puritty-noble"
DEVBOX = ROOT / ".devbox" / "nix" / "profile" / "default" / "bin"
DEFAULT = ["2.7", "3.0", "3.2", "3.4", "3.6a", "3.8"]
ALL = ["2.7", "2.8", "2.9a", "3.0", "3.0a", "3.1", "3.1a", "3.1b", "3.1c", "3.2", "3.2a", "3.3", "3.3a", "3.4",
       "3.5", "3.5a", "3.6", "3.6a", "3.6b", "3.7", "3.7a", "3.7b", "3.7c", "3.8"]

# Each step: what it is, and the tmux commands the puppet runs, or a wait.
STEPS = [
    ("a window made, not shown", [["new-window", "-d", "-n", "two"]]),
    ("that window renamed", [["rename-window", "-t", "main:1", "renamed"]]),
    ("the shown window split", [["split-window", "-d", "-t", "main:0"]]),
    ("the other pane made active", [["select-pane", "-t", "main:0.1"]]),
    ("the other window shown", [["select-window", "-t", "main:1"]]),
    ("the first window shown again", [["select-window", "-t", "main:0"]]),
    ("a pane of the shown window killed", [["kill-pane", "-t", "main:0.1"]]),
    ("a window made whose program ends", [["new-window", "-d", "-n", "short", "sleep 1"]]),
    ("its program ends", 2.0),
    ("the other window killed", [["kill-window", "-t", "main:1"]]),
    ("a window made with two panes, as window 6", [["new-window", "-d", "-n", "six"], ["split-window", "-d", "-t", "main:six"]]),
    ("each of its panes' shells ended, as Ctrl-D does", [["send-keys", "-t", "main:six.1", "exit", "Enter"]]),
    ("its last pane's shell ended", [["send-keys", "-t", "main:six.0", "exit", "Enter"]]),
    ("a window made and shown, whose program ends", [["new-window", "-n", "brief", "sleep 1"]]),
    ("the shown window's program ends", 2.0),
    ("another session made, a window made in it", [["new-session", "-d", "-s", "other"], ["new-window", "-d", "-t", "other:"]]),
    ("the other session killed", [["kill-session", "-t", "other"]]),
    ("a window made, then the first moved to another index", [["new-window", "-d", "-n", "three"], ["move-window", "-s", "main:0", "-t", "main:7"]]),
    ("the shown window renamed", [["rename-window", "-t", "main:7", "seventh"]]),
    # puritty's own: its window resized, keys typed into it, its prompts,
    # confirmations and menus answered (TK12)
    ("puritty's window made smaller", ("resize", 900, 560)),
    ("puritty's window made larger", ("resize", 1150, 760)),
    ("copy mode entered by the puppet", [["copy-mode", "-t", "main:7.0"]]),
    ("copy mode moved by keys typed in puritty", ("keys", ["k", "k", "k"])),
    ("copy mode left by q typed in puritty", ("keys", ["q"])),
    ("copy mode entered by prefix [", ("keys", ["ctrl+b", "bracketleft"])),
    ("copy mode left by q", ("keys", ["q"])),
    ("a window made by prefix c", ("keys", ["ctrl+b", "c"])),
    ("the shown window split by prefix \"", ("keys", ["ctrl+b", "quotedbl"])),
    ("the other pane made active by prefix o", ("keys", ["ctrl+b", "o"])),
    ("the shown window renamed at puritty's prompt (prefix ,)", ("keys", ["ctrl+b", "comma"] + ["BackSpace"] * 12 + ["type:named", "Return"])),
    ("a pane killed by prefix x, confirmed with y", ("keys", ["ctrl+b", "x", "y"])),
    ("the shown window split again", ("keys", ["ctrl+b", "percent"])),
    ("a pane killed from the pane menu (prefix >, X)", ("keys", ["ctrl+b", "greater", "X"])),
    ("the shown window killed by prefix &, confirmed with y", ("keys", ["ctrl+b", "ampersand", "y"])),
    ("the next window shown by prefix n", ("keys", ["ctrl+b", "n"])),
    ("the previous window shown by prefix p", ("keys", ["ctrl+b", "p"])),
    ("the shown window split twice", ("keys", ["ctrl+b", "percent", "ctrl+b", "quotedbl"])),
    ("a pane zoomed by prefix z", ("keys", ["ctrl+b", "z"])),
    ("unzoomed by prefix z", ("keys", ["ctrl+b", "z"])),
    ("panes swapped by prefix {", ("keys", ["ctrl+b", "braceleft"])),
    ("panes rotated by prefix C-o", ("keys", ["ctrl+b", "ctrl+o"])),
    ("the next layout by prefix Space", ("keys", ["ctrl+b", "space"])),
    ("a pane resized by prefix C-Right", ("keys", ["ctrl+b", "ctrl+Right"])),
    ("a pane broken out to a window of its own by prefix !", ("keys", ["ctrl+b", "exclam"])),
    ("another window chosen in the tree (prefix w, Down, Enter)", ("keys", ["ctrl+b", "w", "Down", "Return"])),
    ("a window made by a command at puritty's prompt (prefix :)", ("keys", ["ctrl+b", "colon", "type:new-window -n typed", "Return"])),
    ("the shown window killed at puritty's prompt", ("keys", ["ctrl+b", "colon", "type:kill-window", "Return"])),
]

# tmux's own bugs that end its server at a step: the step left out there
# (docs/tmux-versions.md TV6)
SKIP = {
    "3.7": {"a pane broken out to a window of its own by prefix !": "3.7's break-pane with no name ends the server (fixed in 3.7a)"},
}

XDOTOOL = next((str(p / "bin" / "xdotool") for p in sorted(Path("/nix/store").glob("*-xdotool-*")) if (p / "bin" / "xdotool").exists()), "xdotool")


def tmux_in(name, tmux, *args):
    return subprocess.run(["podman", "exec", name, tmux, "-S", "/sock/s", *args], capture_output=True, text=True)


def truth(name, tmux):
    """What tmux has, as TmuxMode.viewLine writes what puritty shows."""
    wins = tmux_in(name, tmux, "list-windows", "-t", "main", "-F", "#{window_index} #{window_id}:#{window_name}").stdout.split("\n")
    wins = sorted((w.split(" ", 1) for w in wins if w), key=lambda w: int(w[0]))
    asked = tmux_in(name, tmux, "display-message", "-t", "main", "-p", "#{window_id} #{window_width}x#{window_height} #{window_zoomed_flag}")
    if len(asked.stdout.split()) != 3:
        # the server gone, or the session: said, as a step that fails
        return "tmux answered nothing: " + (asked.stderr.strip() or "no error")
    shown, size, zoomed = asked.stdout.split()
    panes = tmux_in(name, tmux, "list-panes", "-t", "main", "-F", "#{pane_id} #{pane_active} #{pane_width}x#{pane_height} #{pane_mode}").stdout.split("\n")
    panes = sorted(((p.split(" ") + [""])[:4] for p in panes if p), key=lambda p: int(p[0][1:]))
    if zoomed == "1":
        # a zoomed window shows its active pane alone, the window's size
        panes = [p for p in panes if p[1] == "1"]
    return ("tabs " + " ".join(w[1] for w in wins) + " | window " + shown + " | panes "
            + " ".join(p[0] + ("*" if p[1] == "1" else "") for p in panes)
            + " | size " + size
            + " | boxes " + " ".join(p[0] + ":" + p[2] for p in panes)
            + " | modes " + " ".join(p[0] + ":" + p[3] for p in panes if p[3]))


def shown(log):
    """puritty's last `tmux=` line."""
    last = None
    for f in sorted(log.glob("*.log")):
        for line in f.read_text(errors="replace").splitlines():
            m = re.match(r"^\d+ [\d:.]+ tmux=\s+(.*)$", line)
            if m:
                last = m.group(1)
    return last


def run_version(v, display):
    tmux = f"/cache/build/{v}/bin/tmux"
    name = f"puritty-puppet-{v}"
    work = WORK / v
    shutil.rmtree(work, ignore_errors=True)
    (work / "sock").mkdir(parents=True)
    (work / "cfg" / "puritty").mkdir(parents=True)
    (work / "state").mkdir()
    (work / "cfg" / "puritty" / "config.toml").write_text("[debug]\nlog = true\n")
    subprocess.run(["podman", "rm", "-f", name], capture_output=True)
    subprocess.run(["podman", "run", "-d", "--name", name, "-v", f"{CACHE}:/cache:ro", "-v", f"{work / 'sock'}:/sock",
                    "-e", "HOME=/tmp", "-e", "LANG=C.UTF-8", "puritty-tmux-versions", "sleep", "infinity"], check=True, capture_output=True)
    failures = []
    xvfb = puritty = None
    try:
        tmux_in(name, tmux, "-f", "/dev/null", "new-session", "-d", "-s", "main", "-n", "sh", "-x", "80", "-y", "24")
        tmux_in(name, tmux, "set-option", "-g", "default-command", "env PS1='$ ' ENV= sh")
        # names stay as given, so that the comparison is not a race with
        # tmux's renaming of windows by their programs
        tmux_in(name, tmux, "set-option", "-g", "-w", "automatic-rename", "off")
        env = dict(os.environ, DISPLAY=display, XDG_CONFIG_HOME=str(work / "cfg"), XDG_STATE_HOME=str(work / "state"),
                   PATH=str(DEVBOX) + ":" + os.environ["PATH"])
        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1200x800x24", "-nolisten", "tcp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        time.sleep(1.0)
        puritty = subprocess.Popen([str(PURITTY), "--", "podman", "exec", "-it", name, tmux, "-S", "/sock/s", "-CC", "attach", "-t", "main"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        log = work / "state" / "puritty" / "logs"

        def settled(step):
            want = truth(name, tmux)
            got = None
            end = time.time() + 8
            while time.time() < end:
                got = shown(log) if log.exists() else None
                if got == want:
                    return True
                time.sleep(0.25)
                want = truth(name, tmux)
            failures.append(f"{v}: {step}: puritty shows {got}, where tmux has {want}")
            return False

        settled("attached")
        window = None
        for what, step in STEPS:
            if what in SKIP.get(v, {}):
                print(f"         {v}: left out: {what}: {SKIP[v][what]}")
                continue
            if isinstance(step, float):
                time.sleep(step)
            elif isinstance(step, tuple):
                if window is None:
                    window = subprocess.run([XDOTOOL, "search", "--class", "Puritty"], capture_output=True, text=True, env=env).stdout.split()[0]
                if step[0] == "resize":
                    subprocess.run([XDOTOOL, "windowsize", window, str(step[1]), str(step[2])], env=env, capture_output=True)
                else:
                    for key in step[1]:
                        if key.startswith("type:"):
                            subprocess.run([XDOTOOL, "type", "--window", window, key[5:]], env=env, capture_output=True)
                        else:
                            subprocess.run([XDOTOOL, "key", "--window", window, key], env=env, capture_output=True)
                        # a key at a time, as typed: puritty answers the
                        # prefix and opens a prompt before the next comes
                        time.sleep(0.3)
            else:
                for args in step:
                    tmux_in(name, tmux, *args)
            settled(what)
    finally:
        if puritty:
            puritty.terminate()
            try:
                puritty.wait(timeout=5)
            except subprocess.TimeoutExpired:
                puritty.kill()
        if xvfb:
            xvfb.terminate()
        subprocess.run(["podman", "rm", "-f", name], capture_output=True)
    return failures


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    versions = ALL if "--all" in sys.argv else (args or DEFAULT)
    if not PURITTY.exists():
        sys.exit(f"{PURITTY} is missing: app/distro/build.sh noble builds it")
    failures = []
    for i, v in enumerate(versions):
        got = run_version(v, f":{120 + i}")
        steps = len(STEPS) + 1 - len(SKIP.get(v, {}))
        print(f"[{'  ok  ' if not got else ' FAIL '}] tmux {v}: {steps - len(got)} of {steps} steps as tmux has them")
        for f in got:
            print("         " + f)
        failures += got
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

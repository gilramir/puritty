#!/usr/bin/env python3
"""The puppet's odd cases (docs/tmux-checks.md TK13): puritty attached to a
real tmux by `tmux -CC`, as `harness/puppet.py` attaches it, and then
something going wrong: the server killed, the client detached from
elsewhere or killed with no `%exit`, the session killed under it, the
client stopped while the server changes, odd names, a bad command, a pane
printing what looks like control mode. Each trial starts its own tmux and
puritty, since many end the session.

puritty's program is a shell that attaches and, when control mode ends,
says the status and goes on as a shell: `sh -c 'tmux -CC attach -t main;
echo status $?; exec sh'`. So a trial can ask, after control mode ends,
whether what is typed reaches the shell again (a line typed into puritty
writes a file in the shared folder), and whether puritty is still there.
While a session goes on, puritty's `tmux=` log line is held to what tmux
has, as the puppet holds it, for the session the control client is in.

    harness/puppet-trials.py [-v VERSION ...] [TRIAL ...]   3.8 by default
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util

spec = importlib.util.spec_from_file_location("puppet", Path(__file__).resolve().parent / "puppet.py")
puppet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(puppet)

ROOT = puppet.ROOT
WORK = ROOT / ".harness-work" / "puppet-trials"
FIND = "for p in /proc/[0-9]*; do tr '\\0' ' ' < $p/cmdline 2>/dev/null | grep -q -- '{}' && echo ${{p#/proc/}}; done"
# the control client, and the server (which keeps the command line of the
# new-session that started it)
# (a bracket in each pattern, so that the finder's own command line, which
# holds the pattern, does not match it; the trial's shell attaches through
# a variable for the same reason)
CLIENT = FIND.format("-CC [a]ttach")
SERVER = FIND.format("new-session -d -s [m]ain")


def tmux_in(name, tmux, *args):
    return puppet.tmux_in(name, tmux, *args)


def client_session(name, tmux):
    """The session the control client is in, or None when there is none."""
    out = tmux_in(name, tmux, "list-clients", "-F", "#{client_control_mode} #{client_session}").stdout.split("\n")
    for line in out:
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0] == "1":
            return parts[1]
    # before 3.0 there is no client_control_mode: the only client
    rest = [l.split(" ", 1)[-1] for l in out if l.strip()]
    return rest[0] if len(rest) == 1 else None


def truth(name, tmux, session):
    """What tmux has for `session`, as `puppet.truth` writes it for main."""
    wins = tmux_in(name, tmux, "list-windows", "-t", session + ":", "-F", "#{window_index} #{window_id}:#{window_name}").stdout.split("\n")
    wins = sorted((w.split(" ", 1) for w in wins if w), key=lambda w: int(w[0]))
    # `session:`, not `session`: a bare name is looked for as a window
    # first, and a window may be named after the session
    asked = tmux_in(name, tmux, "display-message", "-t", session + ":", "-p", "#{window_id} #{window_width}x#{window_height} #{window_zoomed_flag}")
    if len(asked.stdout.split()) != 3:
        return "tmux answered nothing: " + (asked.stderr.strip() or "no error")
    shown, size, zoomed = asked.stdout.split()
    panes = tmux_in(name, tmux, "list-panes", "-t", session + ":", "-F", "#{pane_id} #{pane_active} #{pane_width}x#{pane_height} #{pane_mode}").stdout.split("\n")
    panes = sorted(((p.split(" ") + [""])[:4] for p in panes if p), key=lambda p: int(p[0][1:]))
    if zoomed == "1":
        panes = [p for p in panes if p[1] == "1"]
    return ("tabs " + " ".join(w[1] for w in wins) + " | window " + shown + " | panes "
            + " ".join(p[0] + ("*" if p[1] == "1" else "") for p in panes)
            + " | size " + size
            + " | boxes " + " ".join(p[0] + ":" + p[2] for p in panes)
            + " | modes " + " ".join(p[0] + ":" + p[3] for p in panes if p[3]))


def descendants(pid):
    """The processes under `pid`, from /proc."""
    found, todo = [], [pid]
    while todo:
        p = todo.pop()
        for task in Path(f"/proc/{p}/task").glob("*"):
            try:
                kids = [int(c) for c in (task / "children").read_text().split()]
            except OSError:
                kids = []
            found += kids
            todo += kids
    return found


LONG = "x" * 120

# Each trial: what it is, tmux commands before puritty attaches, and its
# steps. A step is ("tmux", [args], ...), ("keys", [...]), ("type", text),
# ("sleep", s), ("signal", SIG), ("resize", w, h), ("settled",) to hold
# puritty to tmux, ("shell",) to ask that typing reaches the shell after
# control mode ended, or ("alive",).
TRIALS = {
    "kill-server": ("the server killed while attached", [], [
        ("tmux", ["kill-server"]), ("shell",)]),
    "detached-elsewhere": ("the client detached by another client", [], [
        ("tmux", ["detach-client", "-s", "main"]), ("shell",)]),
    "only-session-killed": ("the only session killed", [], [
        ("tmux", ["kill-session", "-t", "main"]), ("shell",)]),
    "session-killed-detaches": ("the session killed while another is left: the client detaches, as tmux's default says", [["new-session", "-d", "-s", "other", "-n", "o1"]], [
        ("tmux", ["kill-session", "-t", "main"]), ("shell",)]),
    "session-killed-other-left": ("the session killed while another is left, detach-on-destroy off", [["new-session", "-d", "-s", "other", "-n", "o1"], ["set-option", "-g", "detach-on-destroy", "off"]], [
        ("tmux", ["kill-session", "-t", "main"]), ("settled",), ("keys", ["ctrl+b", "c"]), ("settled",)]),
    "switched-elsewhere": ("the client switched to another session by the puppet", [["new-session", "-d", "-s", "other", "-n", "o1"], ["new-window", "-d", "-t", "other:", "-n", "o2"]], [
        ("switch", "other"), ("settled",), ("tmux", ["new-window", "-d", "-t", "other:", "-n", "o3"]), ("settled",), ("switch", "main"), ("settled",)]),
    "last-pane-killed": ("the last pane of the last window killed", [], [
        ("tmux", ["kill-pane", "-t", "main:0.0"]), ("shell",)]),
    "client-killed": ("the client killed with no %exit, then attached again", [], [
        ("signal", "KILL"), ("shell",), ("type", "tmux -S /sock/s -CC attach -t main\n"), ("settled",), ("keys", ["ctrl+b", "c"]), ("settled",)]),
    "client-stopped": ("the client stopped while the server changes, then let go", [], [
        ("signal", "STOP"), ("tmux", ["new-window", "-d", "-n", "w1"]), ("tmux", ["split-window", "-d", "-t", "main:0"]),
        ("tmux", ["rename-window", "-t", "main:0", "renamed"]), ("tmux", ["kill-window", "-t", "main:1"]), ("sleep", 2.0),
        ("signal", "CONT"), ("settled",)]),
    "respawned": ("the shown pane and a window respawned", [["new-window", "-d", "-n", "two"]], [
        ("tmux", ["respawn-pane", "-k", "-t", "main:0.0"]), ("settled",), ("tmux", ["respawn-window", "-k", "-t", "main:1"]), ("settled",)]),
    "burst": ("thirty windows made, then all but one killed", [], [
        ("tmux", *[["new-window", "-d", "-n", f"b{i}"] for i in range(30)]), ("settled",),
        ("tmux", ["kill-window", "-a", "-t", "main:0"]), ("settled",)]),
    "odd-names": ("windows named oddly", [], [
        ("tmux", ["new-window", "-d", "-n", "한글 창"], ["new-window", "-d", "-n", "a%b%%c"], ["new-window", "-d", "-n", "x;y \"q\" 'z'"],
         ["new-window", "-d", "-n", "🙂 wide"], ["new-window", "-d", "-n", LONG], ["new-window", "-d", "-n", "#{session_name} #[fg=red]"]),
        ("settled",), ("tmux", ["rename-window", "-t", "main:0", ""]), ("settled",)]),
    "bad-command": ("a command tmux refuses, typed at puritty's prompt", [], [
        ("keys", ["ctrl+b", "colon"]), ("type", "no-such-command -x"), ("keys", ["Return"]), ("sleep", 1.0),
        ("keys", ["ctrl+b", "c"]), ("settled",), ("keys", ["ctrl+b", "colon"]), ("type", "kill-window -t nosuch:9"), ("keys", ["Return"]),
        ("sleep", 1.0), ("keys", ["ctrl+b", "c"]), ("settled",)]),
    "fake-control-lines": ("a pane printing lines like control mode's", [], [
        ("tmux", ["send-keys", "-t", "main:0.0", "printf '%%exit\\n%%begin 1 2 0\\n%%end 1 2 0\\n\\033P1000p%%exit\\033\\\\\\n'", "Enter"]),
        ("sleep", 1.0), ("tmux", ["new-window", "-d", "-n", "after"]), ("settled",)]),
    "tiny-window": ("puritty's window made tiny, then large", [["split-window", "-d", "-t", "main:0"]], [
        ("resize", 120, 80), ("settled",), ("resize", 1150, 760), ("settled",)]),
    "killed-at-prompt": ("the server killed while puritty's prompt is open", [], [
        ("keys", ["ctrl+b", "comma"]), ("sleep", 0.5), ("tmux", ["kill-server"]), ("shell",)]),
    "killed-in-tree": ("the server killed while the tree is open", [["new-window", "-d", "-n", "two"]], [
        ("keys", ["ctrl+b", "w"]), ("sleep", 0.5), ("tmux", ["kill-server"]), ("shell",)]),
    "killed-in-copy-mode": ("the server killed in copy mode", [], [
        ("keys", ["ctrl+b", "bracketleft"]), ("sleep", 0.5), ("tmux", ["kill-server"]), ("shell",)]),
    "server-crashed": ("the server killed by SIGKILL: no %exit", [], [
        ("server-signal", "KILL"), ("shell",)]),
    "garbage-output": ("a pane writing random bytes", [], [
        ("tmux", ["send-keys", "-t", "main:0.0", "head -c 300000 /dev/urandom; printf '\\377\\376\\300\\200 done\\n'", "Enter"]),
        ("sleep", 3.0), ("tmux", ["send-keys", "-t", "main:0.0", "reset", "Enter"]), ("sleep", 1.0), ("settled",),
        ("keys", ["ctrl+b", "c"]), ("settled",)]),
    "no-room-to-split": ("splits until tmux has no room, refused", [], [
        ("tmux", *[["split-window", "-d", "-t", "main:0"] for _ in range(20)]), ("settled",),
        ("keys", ["ctrl+b", "quotedbl"]), ("sleep", 1.0), ("settled",)]),
    "puritty-ended": ("puritty ended while attached: the session stays", [], [
        ("end-puritty",)]),
    "output-while-resized": ("a pane writing fast while the window is resized", [], [
        ("tmux", ["send-keys", "-t", "main:0.0", "seq 1 300000", "Enter"]), ("resize", 700, 450), ("resize", 1100, 700),
        ("resize", 900, 560), ("sleep", 3.0), ("settled",), ("keys", ["ctrl+b", "c"]), ("settled",)]),
}


# A step where a tmux disagrees with itself, so that puritty cannot match
# it: (version, trial, step number) and why. Reported, not failed.
KNOWN = {
    ("2.7", "tiny-window", 2): "2.7 says the window is 10x2 while its panes, 10x2 and 10x3 with the line between, take 6 rows; puritty draws the panes",
}


def run_trial(v, key, display):
    what, setup, steps = TRIALS[key]
    tmux = f"/cache/build/{v}/bin/tmux"
    name = f"puritty-trial-{v}-{key}"
    work = WORK / v / key
    shutil.rmtree(work, ignore_errors=True)
    (work / "sock").mkdir(parents=True)
    (work / "cfg" / "puritty").mkdir(parents=True)
    (work / "state").mkdir()
    (work / "cfg" / "puritty" / "config.toml").write_text("[debug]\nlog = true\n")
    subprocess.run(["podman", "rm", "-f", name], capture_output=True)
    subprocess.run(["podman", "run", "-d", "--name", name, "-v", f"{puppet.CACHE}:/cache:ro", "-v", f"{work / 'sock'}:/sock",
                    "-e", "HOME=/tmp", "-e", "LANG=C.UTF-8", "puritty-tmux-versions", "sleep", "infinity"], check=True, capture_output=True)
    failures = []
    xvfb = proc = None
    log = work / "state" / "puritty" / "logs"
    try:
        tmux_in(name, tmux, "-f", "/dev/null", "new-session", "-d", "-s", "main", "-n", "sh", "-x", "80", "-y", "24")
        tmux_in(name, tmux, "set-option", "-g", "default-command", "env PS1='$ ' ENV= sh")
        tmux_in(name, tmux, "set-option", "-g", "-w", "automatic-rename", "off")
        for args in setup:
            tmux_in(name, tmux, *args)
        env = dict(os.environ, DISPLAY=display, XDG_CONFIG_HOME=str(work / "cfg"), XDG_STATE_HOME=str(work / "state"),
                   PATH=str(puppet.DEVBOX) + ":" + os.environ["PATH"])
        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1200x800x24", "-nolisten", "tcp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        time.sleep(1.0)
        inner = f"export PATH=/cache/build/{v}/bin:$PATH; A=attach; tmux -S /sock/s -CC $A -t main; echo status $?; export OUTER=outer; PS1='$ ' exec sh"
        err = open(work / "stderr.txt", "w")
        proc = subprocess.Popen([str(puppet.PURITTY), "--", "podman", "exec", "-it", "-e", "ENV=", name, "sh", "-c", inner],
                                stdout=subprocess.DEVNULL, stderr=err, env=env)

        def settled(step):
            session = client_session(name, tmux) or "main"
            want = truth(name, tmux, session)
            got = None
            end = time.time() + 8
            while time.time() < end:
                got = puppet.shown(log) if log.exists() else None
                if got == want:
                    return True
                time.sleep(0.25)
                session = client_session(name, tmux) or "main"
                want = truth(name, tmux, session)
            failures.append(f"{step}: puritty shows {got}, where tmux has {want}")
            return False

        window = None

        def win():
            nonlocal window
            if window is None:
                found = subprocess.run([puppet.XDOTOOL, "search", "--class", "Puritty"], capture_output=True, text=True, env=env).stdout.split()
                window = found[0] if found else None
            return window

        def press(k):
            subprocess.run([puppet.XDOTOOL, "key", "--window", win(), k], env=env, capture_output=True)
            time.sleep(0.3)

        def typed(text):
            subprocess.run([puppet.XDOTOOL, "type", "--window", win(), text], env=env, capture_output=True)
            time.sleep(0.3)

        settled("attached")
        n = 0
        for step in steps:
            n += 1
            kind = step[0]
            label = f"step {n} ({kind})"
            if proc.poll() is not None:
                failures.append(f"{label}: puritty has exited, status {proc.returncode}")
                break
            if kind == "tmux":
                for args in step[1:]:
                    tmux_in(name, tmux, *args)
            elif kind == "switch":
                clients = tmux_in(name, tmux, "list-clients", "-F", "#{client_name}").stdout.split()
                for c in clients:
                    tmux_in(name, tmux, "switch-client", "-c", c, "-t", step[1])
            elif kind == "keys":
                for k in step[1]:
                    press(k)
            elif kind == "type":
                typed(step[1])
            elif kind == "sleep":
                time.sleep(step[1])
            elif kind in ("signal", "server-signal"):
                pids = subprocess.run(["podman", "exec", name, "sh", "-c", CLIENT if kind == "signal" else SERVER], capture_output=True, text=True).stdout.split()
                if not pids:
                    failures.append(f"{label}: no control client to signal")
                for p in pids:
                    # the shell's kill: the image may have no kill program
                    sent = subprocess.run(["podman", "exec", name, "sh", "-c", f"kill -{step[1]} {p}"], capture_output=True, text=True)
                    if sent.returncode != 0:
                        failures.append(f"{label}: kill -{step[1]} {p} failed: {sent.stderr.strip()}")
                time.sleep(0.5)
            elif kind == "resize":
                subprocess.run([puppet.XDOTOOL, "windowsize", win(), str(step[1]), str(step[2])], env=env, capture_output=True)
                time.sleep(0.5)
            elif kind == "settled":
                if (v, key, n) in KNOWN:
                    print(f"         {v} {key}: {label} left out: {KNOWN[(v, key, n)]}", flush=True)
                else:
                    settled(label)
            elif kind == "end-puritty":
                # puritty ended as a desktop ends it: the session stays,
                # and its program goes with the terminal (its hangup).
                # The client in the container is podman's to end: killing
                # `podman exec` leaves what it started running there, which
                # a real terminal's hangup would not, so puritty's own child
                # is what is held here
                children = descendants(proc.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    failures.append(f"{label}: puritty did not end when asked (SIGTERM)")
                time.sleep(1.0)
                left = tmux_in(name, tmux, "list-sessions", "-F", "#{session_name}").stdout.split()
                if "main" not in left:
                    failures.append(f"{label}: the session went with puritty: sessions now {left}")
                if not children:
                    failures.append(f"{label}: puritty had no program running")
                left_running = [c for c in children if Path(f"/proc/{c}").exists()]
                if left_running:
                    failures.append(f"{label}: puritty's program still running after it ended: {left_running}")
                break
            elif kind == "shell":
                # control mode is over: the shell has said the status and
                # waits; a line typed must reach it, not tmux. Only it has
                # OUTER (a pane of tmux in the same container would write
                # the file too, empty)
                time.sleep(1.5)
                if proc.poll() is not None:
                    failures.append(f"{label}: puritty exited, status {proc.returncode}, where the shell goes on")
                    break
                mark = work / "sock" / "typed"
                typed("echo $OUTER > /sock/typed\n")
                end = time.time() + 5
                while time.time() < end and not (mark.exists() and mark.read_text().strip()):
                    time.sleep(0.25)
                said = mark.read_text().strip() if mark.exists() else None
                if said != "outer":
                    failures.append(f"{label}: a line typed after control mode ended did not reach the shell"
                                    + (" (a tmux pane ran it)" if said == "" else ""))
                mark.unlink(missing_ok=True)
        time.sleep(0.5)
        if proc.poll() is not None and steps[-1][0] != "end-puritty":
            failures.append(f"at the end: puritty exited, status {proc.returncode}")
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                failures.append("puritty did not end when asked (SIGTERM), killed")
        if xvfb:
            xvfb.terminate()
        subprocess.run(["podman", "rm", "-f", name], capture_output=True)
    said = (work / "stderr.txt").read_text(errors="replace").strip() if (work / "stderr.txt").exists() else ""
    if said:
        failures.append("puritty's stderr: " + said[-400:])
    return what, failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--version", action="append", help="tmux versions (3.8 by default)")
    ap.add_argument("trials", nargs="*", help="trials to run (all by default)")
    a = ap.parse_args()
    versions = a.version or ["3.8"]
    chosen = a.trials or list(TRIALS)
    if not puppet.PURITTY.exists():
        sys.exit(f"{puppet.PURITTY} is missing: app/distro/build.sh noble builds it")
    bad = 0
    for v in versions:
        for i, key in enumerate(chosen):
            what, got = run_trial(v, key, f":{140 + i}")
            print(f"[{'  ok  ' if not got else ' FAIL '}] tmux {v} {key}: {what}", flush=True)
            for f in got:
                print("         " + f, flush=True)
            bad += bool(got)
    print(f"\n{sum(1 for _ in versions) * len(chosen) - bad} of {len(versions) * len(chosen)} trials pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The built-in ssh client in puritty's window (docs/ssh-client.md SC11
step 8, SC18): `puritty --host test`, its host entry's client "built-in",
against a local sshd (packages/ssh/tests/sshd.py's), on Xvfb, driven with
xdotool.

Each case holds to harness/sshwindow/expected/NAME.txt: the window's title
while puritty's own screen is up (puritty's, never the server's), the keys
pressed there, puritty's exit status (the remote command's; one other than 0 keeps the
window until a key, SC29), whether
known_hosts holds the server's key afterwards, and the terminal's size as
the remote side saw it (the command writes `stty size` to a file, the
server being this machine).

usage (from puritty's devbox, after app/build.sh and packages/ssh/tests/build.sh):
    harness/sshwindow.py              every case
    harness/sshwindow.py --update     write the pins; read the diff first
"""

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "packages" / "ssh" / "tests"))
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402  (its fonts)
import reload  # noqa: E402  (its window's title)
import sshd  # noqa: E402  (the local sshd and the user keys)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "sshwindow"
PINS = ROOT / "harness" / "sshwindow" / "expected"
DISPLAY = ":88"

# name, the key to log in with, its passphrase, how known_hosts starts
# (empty, holding the server's key, holding another), the keys pressed on
# puritty's screen (each after a pause), the command run there
CASES = [
    ("trust-remember", "ed", "", "empty", ["a"], "stty size > {size}; exit 0"),
    ("trust-once", "ed", "", "empty", ["o"], "exit 0"),
    ("known", "ed", "", "known", [], "stty size > {size}; exit 0"),
    ("passphrase", "ecdsa521", "hunter2", "known", ["type:hunter2", "Return"], "exit 0"),
    ("wrong-passphrase-then-right", "ecdsa521", "hunter2", "known", ["type:nope", "Return", "type:hunter2", "Return"], "exit 0"),
    ("decline", "ed", "", "empty", ["Escape", "Return"], "exit 0"),
    # a changed key (docs/ssh-client.md SC28): Enter does nothing, Esc
    # refuses and Enter closes; O trusts it once; A puts it in place
    ("changed", "ed", "", "other", ["Return", "Escape", "Return"], "exit 0"),
    ("changed-once", "ed", "", "other", ["o"], "exit 0"),
    ("changed-replace", "ed", "", "other", ["a"], "exit 0"),
    ("no-key-then-reconnect", "other", "", "known", ["r", "Return"], "exit 0"),
    # through a jump host (docs/ssh-client.md SC21): the host's `jump` is a
    # second sshd, its key from ~/.ssh/config's IdentityFile for it
    ("jump", "ed", "", "known", [], "stty size > {size}; exit 0"),
    # the window resized before the session runs, or while it is down, then
    # its terminal at the new size (docs/ssh-client.md SC26): first while
    # the passphrase is asked; then the connection dropped (the command
    # kills its sshd, no exit status) and a reconnect after the resize
    ("resize-while-asking", "ecdsa521", "hunter2", "known", ["resize:900:500", "type:hunter2", "Return"], "stty size > {size}; exit 0"),
    ("resize-then-reconnect", "ed", "", "known", ["resize:900:500", "r"],
     "if [ -e {size} ]; then stty size >> {size}; exit 0; else stty size > {size}; kill -9 $PPID; fi"),
    # tmux -CC attached when the connection drops (no %exit), then a
    # reconnect: what is typed reaches the new shell, not tmux (TM93); the
    # first press only waits for the drop
    ("tmux-then-reconnect", "ed", "", "known", ["shift", "r", "type:hello", "Return"],
     "if [ -e {size} ]; then read l; echo $l >> {size}; exit 0; else echo first > {size}; (sleep 2; kill -9 $PPID) & tmux -L sshwindow -f /dev/null -CC new-session; fi"),
    # a command that fails keeps the window, its own words behind puritty's
    # box (docs/ssh-client.md SC29): Enter closes it, its status the
    # window's; the second, a command the shell cannot find, as Gilbert's
    # `tmux -CC attach -t main` on a host whose tmux is not on a command's PATH
    ("command-fails", "ed", "", "known", ["sleep:1", "Return"], "echo it went wrong; exit 7"),
    ("command-not-found", "ed", "", "known", ["sleep:1", "Return"], "no-such-tmux -CC attach -t main"),
    # tmux -CC refusing the attach, its error said inside control mode
    ("tmux-attach-fails", "ed", "", "known", ["sleep:1", "Return"], "tmux -L sshwindow-none -f /dev/null -CC attach -t main"),
    # control mode ending oddly over the built-in client (docs/tmux-checks.md
    # TK13), then a line typed, which must reach the shell after it: the
    # client killed with no %exit; the server killed; the client detached
    # from elsewhere
    ("tmux-client-killed", "ed", "", "known", ["sleep:2", "type:hello", "Return"],
     # (the socket's name through a variable: the shell's own command line
     # holds the whole command, and pkill -f would match it too). Pinned as
     # it is, and wrong: the shell after it waits in `read` and says
     # nothing, so nothing tells puritty control mode is over, and the
     # first key goes as `send-keys` (TK13: a timeout on an unanswered
     # command is the only sign; left as it is, Gilbert 2026-11-18)
     "echo first > {size}; T=sw-k; (sleep 2; pkill -9 -f 'tmux -L sw-[k] -f') & tmux -L $T -f /dev/null -CC new-session; read l; echo $l >> {size}; tmux -L $T kill-server; exit 0"),
    # the same with an interactive shell after it, as a login shell that
    # ran tmux is: its prompt is the first thing after control mode
    ("tmux-client-killed-shell", "ed", "", "known", ["sleep:2", "type:echo hello >> size.txt", "Return", "type:exit", "Return"],
     "cd $(dirname {size}); echo first > {size}; T=sw-ks; (sleep 2; pkill -9 -f 'tmux -L sw-k[s] -f') & tmux -L $T -f /dev/null -CC new-session; tmux -L $T kill-server; PS1='$ ' exec sh -i"),
    ("tmux-server-killed", "ed", "", "known", ["sleep:2", "type:hello", "Return"],
     "echo first > {size}; (sleep 2; tmux -L sw-s kill-server) & tmux -L sw-s -f /dev/null -CC new-session; read l; echo $l >> {size}; exit 0"),
    ("tmux-detached-elsewhere", "ed", "", "known", ["sleep:2", "type:hello", "Return"],
     "echo first > {size}; (sleep 2; tmux -L sw-d detach-client -s 0) & tmux -L sw-d -f /dev/null -CC new-session; read l; echo $l >> {size}; tmux -L sw-d kill-server; exit 0"),
    # the connection dropped while tmux -CC is attached and puritty's prompt,
    # its tree, or a flood of output is up; then R, and a line typed into
    # the new shell
    ("tmux-drop-at-prompt", "ed", "", "known", ["ctrl+b", "comma", "sleep:4", "r", "type:hello", "Return"],
     "if [ -e {size} ]; then read l; echo $l >> {size}; exit 0; else echo first > {size}; (sleep 5; tmux -L sw-p kill-server; kill -9 $PPID) & tmux -L sw-p -f /dev/null -CC new-session; fi"),
    ("tmux-drop-in-tree", "ed", "", "known", ["ctrl+b", "w", "sleep:4", "r", "type:hello", "Return"],
     "if [ -e {size} ]; then read l; echo $l >> {size}; exit 0; else echo first > {size}; (sleep 5; tmux -L sw-t kill-server; kill -9 $PPID) & tmux -L sw-t -f /dev/null -CC new-session; fi"),
    ("tmux-drop-in-flood", "ed", "", "known", ["sleep:4", "r", "type:hello", "Return"],
     "if [ -e {size} ]; then read l; echo $l >> {size}; exit 0; else echo first > {size}; (sleep 3; tmux -L sw-f kill-server; kill -9 $PPID) & tmux -L sw-f -f /dev/null -CC new-session 'seq 1 100000000'; fi"),
]


SHOTS = False


def run_case(env0, name, key, passphrase, known, presses, command, keys):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    (home / "config" / "puritty").mkdir(parents=True)
    (home / ".ssh").mkdir()
    size = home / "size.txt"
    server = sshd.Server([])
    bastion = sshd.Server([]) if name == "jump" else None
    try:
        server_pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
        other_pub = (sshd.WORK / "userkeys" / "other.pub").read_text().split()[:2]
        kh = home / ".ssh" / "known_hosts"
        lookup = f"[127.0.0.1]:{server.port}"
        if known == "known":
            kh.write_text(f"{lookup} {' '.join(server_pub)}\n" + (f"[127.0.0.1]:{bastion.port} {' '.join(server_pub)}\n" if bastion else ""))
        elif known == "other":
            kh.write_text(f"{lookup} {' '.join(other_pub)}\n")
        jump = ""
        if bastion:
            (home / ".ssh" / "config").write_text(f"Host 127.0.0.1\n    IdentityFile {keys[key]}\n")
            jump = f'jump = "{getpass.getuser()}@127.0.0.1:{bastion.port}"\n'
        (home / "config" / "puritty" / "config.toml").write_text(
            f'[hosts.test]\nhost = "127.0.0.1"\nport = {server.port}\nuser = "{getpass.getuser()}"\n'
            f'identity = "{keys[key]}"\nclient = "built-in"\ncommand = "{command.format(size=size)}"\n' + jump
            # the diagnostic log, for a case that fails
            + "\n[debug]\nlog = true\n")
        env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh", USER=getpass.getuser(),
                   PURITTY_SHOT=str(home / "shot.ppm"))
        env.pop("SSH_AUTH_SOCK", None)
        p = subprocess.Popen([str(APP), "--host", "test"], env=env, stdout=subprocess.DEVNULL,
                             stderr=open(home / "stderr.txt", "w"))
        time.sleep(2.0)
        titles = []
        if presses:
            titles.append(reload.title_of(env))
            win = subprocess.run([hosts.XDO, "search", "--sync", "--name", "^(puritty: ssh to|tmux: )"], env=env, capture_output=True,
                                 text=True, timeout=10).stdout.split()
            for n, k in enumerate(presses):
                if SHOTS:
                    # the window as the question is asked (docs/ssh-client.md SC23)
                    pic = reload.read_ppm(home / "shot.ppm")
                    if pic:
                        reload.save_png(WORK / f"{name}-{n}.png", pic)
                if win:
                    subprocess.run([hosts.XDO, "windowfocus", "--sync", win[0]], env=env, capture_output=True)
                if k.startswith("resize:"):
                    w, h = k.split(":")[1:]
                    subprocess.run([hosts.XDO, "windowsize", "--sync", win[0], w, h], env=env, capture_output=True, timeout=10)
                elif k.startswith("sleep:"):
                    time.sleep(float(k[6:]))
                    titles.append(reload.title_of(env))
                elif k.startswith("type:"):
                    subprocess.run([hosts.XDO, "type", "--delay", "40", k[5:]], env=env, check=True)
                else:
                    subprocess.run([hosts.XDO, "key", k], env=env, check=True)
                time.sleep(1.5)
                if k in ("Return", "Escape") and p.poll() is None:
                    titles.append(reload.title_of(env))
        try:
            status = p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            status = "did not end"
    finally:
        server.stop()
        if bastion:
            bastion.stop()
    held = kh.exists() and " ".join(server_pub) in kh.read_text()
    seen = size.read_text().strip().replace("\n", ", ") if size.exists() else "none"
    return (f"titles: {titles}\n".replace(str(server.port), "PORT")
            + f"pressed: {presses}\nexit status: {status}\nknown_hosts holds the key: {'yes' if held else 'no'}\n"
            + f"the remote side's terminal: {seen}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    ap.add_argument("only", nargs="*", help="these cases alone")
    ap.add_argument("--shots", action="store_true", help="save the window's picture before each key, in .harness-work/sshwindow")
    a = ap.parse_args()
    global SHOTS
    SHOTS = a.shots
    if not APP.exists():
        sys.exit("sshwindow.py: build app/puritty first (app/build.sh)")
    hosts.XDO = hosts.xdotool()
    keys = sshd.user_keys()[0]
    sshd.host_keys()
    conf = pixels.write_fonts_conf()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96", LANG="C.UTF-8")
    env.pop("LC_ALL", None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    fails = 0
    try:
        chosen = [c for c in CASES if not a.only or c[0] in a.only]
        for name, key, passphrase, known, presses, command in chosen:
            got = run_case(env, name, key, passphrase, known, presses, command, keys)
            pin = PINS / f"{name}.txt"
            if a.update:
                PINS.mkdir(parents=True, exist_ok=True)
                pin.write_text(got)
                print(f"wrote {name}:\n  " + got.strip().replace("\n", "\n  "))
            elif not pin.exists() or pin.read_text() != got:
                fails += 1
                print(f"FAIL {name}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
            else:
                print(f"ok   {name}")
    finally:
        xvfb.terminate()
        xvfb.wait()
    if not a.update:
        print(f"{len(chosen) - fails} of {len(chosen)} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

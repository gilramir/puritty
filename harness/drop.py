#!/usr/bin/env python3
"""Files dropped on puritty's window from a file manager (docs/sftp.md
FT21, FT22), under Xvfb: Nemo (GTK) and Dolphin (Qt 6, from nixpkgs) drag
files onto a local tab whose program records what is pasted
(drop/record-paste.py), and each case is pinned with what came and what
the window said (its diagnostic log's `drop` and `paste` lines).

    devbox run -- harness/drop.py [--update] [CASE...]

The folder dragged from holds `a plain.txt`, `it's $HOME.txt`, `한글
이름.txt` (UTF-8), `euc-kr ` and 한글 in EUC-KR's bytes `.txt`, and `a
folder`. Where each sits in the file manager's window was read from a
screenshot (probes/xdnd/drag-from-nemo.py); the pin of a case that moved
would show it.
"""
import argparse, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "packages" / "ssh" / "tests"))
import getpass  # noqa: E402
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402  (its fonts)
import sshd  # noqa: E402  (the local sshd and the user keys)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "drop"
PINS = ROOT / "harness" / "drop" / "expected"
RECORD = ROOT / "harness" / "drop" / "record-paste.py"
PANES = ROOT / "harness" / "drop" / "tmux-panes.sh"
DISPLAY = ":86"
EUC = "euc-kr ".encode() + "한글".encode("euc-kr") + b".txt"

# Nemo's and Dolphin's icon views, 640x700 at the top left, with this
# harness's fonts (before.png in each case's folder shows them)
NEMO = {"folder": (253, 120), "plain": (408, 120), "euc": (562, 120), "quote": (253, 255), "korean": (408, 255)}
DOLPHIN = {"folder": (257, 85), "plain": (404, 85), "euc": (550, 85), "quote": (257, 182), "korean": (404, 182)}
ALL = ["folder", "korean", "plain", "euc", "quote"]

# name, file manager, what is dragged (the first is grabbed), the tab's charset
CASES = [
    ("nemo-one", "nemo", ["plain"], "utf-8"),
    ("nemo-several", "nemo", ["plain", "folder", "korean", "quote"], "utf-8"),
    # a name not UTF-8 is not pasted in a UTF-8 tab, and is in an EUC-KR one
    ("nemo-euc-kr-in-utf-8", "nemo", ["euc"], "utf-8"),
    ("nemo-euc-kr-in-euc-kr", "nemo", ["euc"], "euc-kr"),
    ("dolphin-several", "dolphin", ["plain", "folder", "korean", "quote"], "utf-8"),
    # Dolphin spoils the EUC-KR name before puritty sees it (FT21)
    ("dolphin-euc-kr-in-euc-kr", "dolphin", ["euc"], "euc-kr"),
]


# an ssh tab under tmux -CC (FT23): the pane a file is dropped on, by where
# it is in puritty's window, as tmux-panes.sh lays them out
TMUX_CASES = [
    ("tmux-plain-pane", (760, 250)),
    ("tmux-osc7-pane", (1100, 150)),
    ("tmux-ssh-pane", (1100, 400)),
]

# an ssh tab without tmux (FT24): the folder chooser, driven by keys: a path
# typed over the home it opens at, its folders listed, the second chosen,
# gone into, and chosen
CHOOSER_KEYS = ["ctrl+a", "type:HOST", "Return", "Down", "Down", "Down", "Return", "Return"]
# the chooser's folder, typed and chosen at once
TO_HOST = ["ctrl+a", "type:HOST", "Return", "Return"]


def taken(there):
    # a file of the dropped one's name there already, older
    (there / "a plain.txt").write_text("older\n")
    os.utime(there / "a plain.txt", (1577934245, 1577934245))


def toml_text(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def osc7_command(there, which):
    """A login shell that says its folder by OSC 7 (FT29), as a shell set up
    for it does at each prompt: `beta dir` in the case's folder, by this
    host's name; with `nested`, then another host's, as a shell in an ssh
    run in the tab would say."""
    path = str(there / "beta dir").replace(" ", "%20")
    first = f'printf "\\033]7;file://%s%s\\007" "$(hostname)" "{path}"'
    second = 'sleep 1; printf "\\033]7;file://elsewhere/srv\\007"' if which == "nested" else ":"
    return f"sh -c '{first}; {second}; exec sh'"


def host_listing(there, files):
    """What the host's folders hold after the drop: each file's size and
    whether its bytes are a dropped file's, by name."""
    lines = []
    for p in sorted(there.rglob("*")):
        rel = p.relative_to(there)
        if p.is_symlink():
            lines.append(f"  {rel} -> {os.readlink(p)}")
            continue
        if p.is_dir():
            lines.append(f"  {rel}/")
            continue
        src = next((f for f in files.rglob(p.name.replace(" (2)", "")) if f.is_file()), None)
        if src is None:
            same = ""
        elif src.stat().st_size > 1 << 20:
            # a large one, compared a piece at a time
            with open(src, "rb") as a, open(p, "rb") as b:
                alike = all(x == y for x, y in iter(lambda: (a.read(1 << 20), b.read(1 << 20)), (b"", b"")))
            same = ", the dropped file's bytes" if alike and src.stat().st_size == p.stat().st_size else ", OTHER bytes"
        else:
            same = ", the dropped file's bytes" if src.read_bytes() == p.read_bytes() else ", OTHER bytes"
        lines.append(f"  {rel}: {p.stat().st_size} bytes{same}")
    return lines


def run_tmux_case(env0, name, at, keys, after=(), tmux=True, items=("plain",), sftp=True, shell=False, before=None, big=False, size=4 << 30,
                  wait=3, drop=None, osc7=None, client="built-in"):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    files = home / "files"
    files.mkdir(parents=True)
    if big:
        # one file, 4 GiB of a hole, long enough to send that it is cancelled
        with open(files / "big.bin", "wb") as f:
            f.truncate(size)
    else:
        for n in ["a plain.txt", "it's $HOME.txt", "한글 이름.txt"]:
            (files / n).write_text("x\n")
        with open(os.path.join(os.fsencode(files), EUC), "w") as f:
            f.write("x\n")
        (files / "a folder").mkdir()
    there = home / "host"
    if not big:
        (files / "a folder" / "inside.txt").write_text("inside\n")
    server = sshd.Server(["Subsystem sftp /usr/lib/openssh/sftp-server"] if sftp else [])
    kh = home / ".ssh" / "known_hosts"
    kh.parent.mkdir(parents=True)
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[hosts.test]\nhost = "127.0.0.1"\nport = {server.port}\nuser = "{getpass.getuser()}"\nidentity = "{keys["ed"]}"\n'
        f'client = "{client}"\n' + (f'command = "sh {PANES} \'{there}\'"\n' if tmux else "")
        + (f'command = {toml_text(osc7_command(there, osc7))}\n' if osc7 else "") + '\n[debug]\nlog = true\n'
        + ('\n[files]\n' if shell or drop else "") + ('upload_through_shell = true\n' if shell else "")
        + (f'drop_uploads = "{drop}"\n' if drop else ""))
    if not tmux:
        # the folders the chooser is taken to
        for d in ["alpha", "beta dir", ".hidden"]:
            (there / d).mkdir(parents=True)
        # a link to a folder, which the chooser lists, and one to nothing,
        # which it does not (FT30)
        (there / "link to alpha").symlink_to("alpha")
        (there / "dangling").symlink_to("nowhere")
    if before:
        before(there)
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh", USER=getpass.getuser())
    if client == "openssh":
        # OpenSSH reads the user's own ~/.ssh, not $HOME's: a wrapper first
        # on PATH gives it a config of the case's, for the tab's ssh and the
        # helpers alike (FT31); the master's socket in a folder of its own
        bindir = home / "bin"
        bindir.mkdir()
        conf = home / "ssh_config"
        conf.write_text(f"Host *\n    UserKnownHostsFile {kh}\n    StrictHostKeyChecking yes\n    IdentitiesOnly yes\n")
        real = shutil.which("ssh")
        (bindir / "ssh").write_text(f'#!/bin/sh\nexec {real} -F {conf} "$@"\n')
        (bindir / "ssh").chmod(0o755)
        (home / "run").mkdir(exist_ok=True)
        env = dict(env, PATH=f"{bindir}:{env['PATH']}")
    # the master's socket's folder, puritty's alone: the file manager's
    # D-Bus session mounts its FUSE folders in XDG_RUNTIME_DIR
    app_env = dict(env, XDG_RUNTIME_DIR=tempfile.mkdtemp(prefix="pd-")) if client == "openssh" else env
    procs = []
    try:
        procs.append(subprocess.Popen(["dbus-run-session", "--", "nemo", "--no-desktop", "--geometry=640x700+0+0", str(files)],
                                      env=dict(env, GTK_THEME="Adwaita"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        procs.append(subprocess.Popen([str(APP), "--host", "test"], env=app_env, stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w")))
        time.sleep(7)
        for wid in xdo(env, "search", "--class", "nemo").split():
            xdo(env, "windowmove", wid, 0, 0)
            xdo(env, "windowsize", wid, 640, 700)
        for wid in xdo(env, "search", "--class", "puritty").split():
            xdo(env, "windowmove", wid, 660, 60)
        time.sleep(1.5)
        shot = [sys.executable, str(ROOT / "probes" / "xdnd" / "shot.py")]
        subprocess.run(shot + [str(home / "before.png")], env=env)
        x, y = (253, 120) if big else NEMO[items[0]]
        xdo(env, "mousemove", x, y)
        xdo(env, "click", 1)
        for it in items[1:]:
            xdo(env, "mousemove", *NEMO[it])
            xdo(env, "keydown", "ctrl")
            xdo(env, "click", 1)
            xdo(env, "keyup", "ctrl")
        time.sleep(0.5)
        xdo(env, "mousemove", x, y)
        time.sleep(0.3)
        xdo(env, "mousedown", 1)
        for i in range(1, 31):
            xdo(env, "mousemove", x + (at[0] - x) * i // 30, y + (at[1] - y) * i // 30)
            time.sleep(0.03)
        xdo(env, "mousemove", at[0] + 1, at[1] + 1)
        time.sleep(1.5)
        # the mark, as the drag is over the pane
        subprocess.run(shot + [str(home / "marked.png")], env=env)
        xdo(env, "mouseup", 1)
        time.sleep(2)
        # what the drop put up, before any key
        subprocess.run(shot + [str(home / "dropped.png")], env=env)
        if after:
            for wid in xdo(env, "search", "--class", "puritty").split():
                xdo(env, "windowfocus", "--sync", wid)
            for n, k in enumerate(after):
                if k.startswith("type:"):
                    xdo(env, "type", "--delay", "30", k[5:].replace("HOST", str(there)))
                elif k.startswith("sleep:"):
                    time.sleep(float(k[6:]))
                else:
                    xdo(env, "key", k)
                time.sleep(1.2)
                subprocess.run(shot + [str(home / f"after-{n}.png")], env=env)
        if big and name == "tmux-cancel":
            # the progress, a second and more on, and a click on it cancels
            time.sleep(2.5)
            subprocess.run(shot + [str(home / "progress.png")], env=env)
            # the note bar, at the window's bottom right over the tab bar,
            # where progress.png shows it (the window at 660,60)
            xdo(env, "mousemove", 1150, 434)
            xdo(env, "click", 1)
        # what is sent, given time to arrive
        time.sleep(wait)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
        subprocess.run(["tmux", "-L", "puritty-drop", "kill-server"], capture_output=True)
        server.stop()
    said = [line.split(None, 3)[-1].replace(str(there), "HOST").replace(str(files), "DIR")
            for log in sorted((home / ".local" / "state" / "puritty" / "logs").glob("*.log"))
            for line in log.read_text(errors="replace").splitlines()
            if (" paste " in line or " drop " in line) and "paste button" not in line and "paste asked" not in line]
    held = host_listing(there, files)
    # a large file sent is not kept in the work folder
    for p in list(there.rglob("big.bin")) + list(there.rglob(".big.bin.puritty-part")):
        p.unlink()
    return (f"dropped {items} {'on the pane ' if tmux else ''}at {at}{', then ' + str(after) if after else ''}\nsaid: {said}\n"
            + "the host holds:\n" + "\n".join(held) + "\n")


def dolphin():
    out = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", "nixpkgs#kdePackages.dolphin"], capture_output=True, text=True,
                         check=True)
    return out.stdout.split()[0] + "/bin/dolphin"


def xdo(env, *args):
    return subprocess.run([hosts.XDO, *map(str, args)], env=env, capture_output=True, text=True).stdout


def run_case(env0, name, fm, items, charset):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    files = home / "files"
    files.mkdir(parents=True)
    for n in ["a plain.txt", "it's $HOME.txt", "한글 이름.txt"]:
        (files / n).write_text("x\n")
    with open(os.path.join(os.fsencode(files), EUC), "w") as f:
        f.write("x\n")
    (files / "a folder").mkdir()
    out = home / "pasted.txt"
    (home / "config" / "puritty").mkdir(parents=True)
    (home / "config" / "puritty" / "config.toml").write_text(
        f'[program]\ncommand = ["python3", "{RECORD}", "{out}"]\n\n[terminal]\ncharset = "{charset}"\n\n[debug]\nlog = true\n')
    env = dict(env0, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"), SHELL="/bin/sh")
    procs = []
    try:
        cmd = [env0["DOLPHIN"], str(files)] if fm == "dolphin" else ["nemo", "--no-desktop", "--geometry=640x700+0+0", str(files)]
        procs.append(subprocess.Popen(["dbus-run-session", "--", *cmd], env=dict(env, QT_QPA_PLATFORM="xcb", GTK_THEME="Adwaita"),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        app = subprocess.Popen([str(APP)], env=env, stdout=subprocess.DEVNULL, stderr=open(home / "stderr.txt", "w"))
        procs.append(app)
        time.sleep(5)
        for wid in xdo(env, "search", "--class", fm).split():
            xdo(env, "windowmove", wid, 0, 0)
            xdo(env, "windowsize", wid, 640, 700)
        for wid in xdo(env, "search", "--class", "puritty").split():
            xdo(env, "windowmove", wid, 660, 60)
        time.sleep(1.5)
        subprocess.run([sys.executable, str(ROOT / "probes" / "xdnd" / "shot.py"), str(home / "before.png")], env=env)
        at = NEMO if fm == "nemo" else DOLPHIN
        # the first clicked, the rest added with Ctrl held, the first grabbed
        x, y = at[items[0]]
        xdo(env, "mousemove", x, y)
        xdo(env, "click", 1)
        for it in items[1:]:
            xdo(env, "mousemove", *at[it])
            xdo(env, "keydown", "ctrl")
            xdo(env, "click", 1)
            xdo(env, "keyup", "ctrl")
        time.sleep(0.5)
        xdo(env, "mousemove", x, y)
        time.sleep(0.3)
        xdo(env, "mousedown", 1)
        for i in range(1, 31):
            xdo(env, "mousemove", x + (950 - x) * i // 30, y + (300 - y) * i // 30)
            time.sleep(0.03)
        time.sleep(0.5)
        xdo(env, "mousemove", 951, 301)
        time.sleep(0.5)
        xdo(env, "mouseup", 1)
        for _ in range(40):
            if out.exists():
                break
            time.sleep(0.5)
        time.sleep(1)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
    got = out.read_text().strip() if out.exists() else "the program ended without saying"
    if got not in ("nothing pasted", "the program ended without saying"):
        raw = bytes.fromhex(got)
        raw = raw.replace(os.fsencode(files), b"DIR")
        try:
            got = "pasted: " + raw.decode("utf-8")
        except UnicodeDecodeError:
            # not UTF-8: each byte past ASCII as \xNN, as transfer.py shows names
            got = "pasted: " + "".join(chr(c) if c < 128 else f"\\x{c:02x}" for c in raw)
    said = [line.split(None, 3)[-1] for log in sorted((home / ".local" / "state" / "puritty" / "logs").glob("*.log"))
            for line in log.read_text(errors="replace").splitlines() if (" drop " in line or " paste " in line) and "paste button" not in line
            and "paste asked" not in line]
    said = [line.replace(str(files), "DIR") for line in said]
    return f"dragged: {items} from {fm}, the tab in {charset}\n{got}\nsaid: {said}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    hosts.XDO = hosts.xdotool()
    conf = pixels.write_fonts_conf()
    env = dict(os.environ, DISPLAY=DISPLAY, FONTCONFIG_FILE=str(conf), PURITTY_NO_XIM="1", PURITTY_DPI="96", LANG="C.UTF-8",
               NO_AT_BRIDGE="1", DOLPHIN=dolphin())
    env.pop("SSH_AUTH_SOCK", None)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    fails = ran = 0
    keys = sshd.user_keys()[0]
    runs = [(name, (lambda name=name, fm=fm, items=items, charset=charset: run_case(env, name, fm, items, charset)))
            for name, fm, items, charset in CASES] + \
        [(name, (lambda name=name, at=at: run_tmux_case(env, name, at, keys, after=["Escape"] if name == "tmux-ssh-pane" else (), drop="allow")))
         for name, at in TMUX_CASES] + \
        [("ssh-chooser", lambda: run_tmux_case(env, "ssh-chooser", (950, 300), keys, after=CHOOSER_KEYS, tmux=False)),
         # four items, a folder among them, to the folder typed
         ("ssh-several", lambda: run_tmux_case(env, "ssh-several", (950, 300), keys, after=TO_HOST, tmux=False,
                                               items=("plain", "folder", "korean", "quote"))),
         # a name there already: the question, answered K, keep both
         ("ssh-keep-both", lambda: run_tmux_case(env, "ssh-keep-both", (950, 300), keys, after=TO_HOST + ["k"], tmux=False,
                                                 before=taken)),
         # a host with SFTP off: through its shell when the setting allows,
         # else nothing, said; the chooser needs SFTP, so the pane of tmux
         # whose folder is known is dropped on
         ("tmux-no-sftp-shell", lambda: run_tmux_case(env, "tmux-no-sftp-shell", (760, 250), keys, sftp=False, shell=True, drop="allow")),
         ("tmux-no-sftp", lambda: run_tmux_case(env, "tmux-no-sftp", (760, 250), keys, sftp=False, drop="allow")),
         # a long one: its progress, and a click on it cancels, no part left
         ("tmux-cancel", lambda: run_tmux_case(env, "tmux-cancel", (760, 250), keys, items=("big",), big=True, drop="allow")),
         # [files] drop_uploads (FT28): on a pane, whose folder puritty
         # finds, asked by default, Enter sends and Esc does not; deny
         # sends nothing; the chooser cases above ask nothing more
         ("tmux-ask-yes", lambda: run_tmux_case(env, "tmux-ask-yes", (760, 250), keys, after=["Return"])),
         ("tmux-ask-no", lambda: run_tmux_case(env, "tmux-ask-no", (760, 250), keys, after=["Escape"])),
         ("tmux-deny", lambda: run_tmux_case(env, "tmux-deny", (760, 250), keys, drop="deny")),
         # OSC 7 (FT29): an ssh tab whose shell says its folder is asked
         # about that folder, Enter sends there; C takes the chooser to it,
         # where Enter sends; one whose last OSC 7 named another host (a
         # nested ssh's) gets the chooser at home, and Esc
         ("osc7-ask", lambda: run_tmux_case(env, "osc7-ask", (950, 300), keys, tmux=False, osc7="beta", after=["Return"])),
         ("osc7-another", lambda: run_tmux_case(env, "osc7-another", (950, 300), keys, tmux=False, osc7="beta", after=["c", "Return"])),
         ("osc7-nested", lambda: run_tmux_case(env, "osc7-nested", (950, 300), keys, tmux=False, osc7="nested", after=["Escape"])),
         # a tab of OpenSSH's ssh (FT31): the chooser and the sending through
         # its connection by ControlMaster, on a tab with no tmux and on a
         # tmux -CC pane
         ("openssh-chooser", lambda: run_tmux_case(env, "openssh-chooser", (950, 300), keys, after=TO_HOST, tmux=False, client="openssh")),
         ("openssh-tmux", lambda: run_tmux_case(env, "openssh-tmux", (760, 250), keys, drop="allow", client="openssh")),
         # another tab shown while one sends (FT26; 2 GiB, which a shown tab
         # does not finish in the two seconds before the switch, FT27): the sending goes on in
         # its own session, its tab marked, and its end said with its name
         ("switch-tab", lambda: run_tmux_case(env, "switch-tab", (950, 300), keys, tmux=False, items=("big",), big=True, size=2 << 30,
                                              after=TO_HOST + ["sleep:2", "ctrl+shift+t", "sleep:3"], wait=30))]
    try:
        for name, go in runs:
            if a.only and name not in a.only:
                continue
            ran += 1
            got = go()
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
        xvfb.kill()
    print(f"{ran - fails} of {ran} cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

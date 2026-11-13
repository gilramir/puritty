"""What a program in a pane gets, byte for byte, for each key or mouse
event: puritty running a normal tmux client against puritty in tmux -CC,
the same events by xdotool, the same tmux, the program asking for the same
modes (puritty docs/tmux.md TM61). A run that logs nothing stops the check
rather than passing it.

  systemd-run --user --scope -p MemoryMax=6G devbox run -- \
      python3 bench/tmux/compare/keydiff.py TMUX WORKDIR on|off [keys|mouse]
"""
import os, subprocess, sys, time
from pathlib import Path
P = Path.home()/"prj"/"puritty"
sys.path.insert(0, str(P/"harness")); import pixels
XDO = "/nix/store/lck8j0ci1qqbhqhqcmwh9w4nj4xans2n-xdotool-4.20260303.1/bin/xdotool"
XVFB = str(P/".devbox/nix/profile/default/bin/Xvfb")
T = sys.argv[1]; S = Path(sys.argv[2]); EXT = sys.argv[3]; WHAT = sys.argv[4] if len(sys.argv) > 4 else "keys"
KEYS = ["a", "Return", "BackSpace", "Tab", "shift+Tab", "Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next",
        "Insert", "Delete", "F1", "F5", "F12", "ctrl+c", "ctrl+Left", "shift+Up", "alt+x", "alt+Up", "ctrl+Return",
        "shift+Return", "KP_Enter", "KP_5", "space", "ctrl+space", "Escape", "hangul_text"]
MODES = {"plain": "", "app": "\\x1b[?1h\\x1b=", "ext2": "\\x1b[>4;2m", "ext1": "\\x1b[>4;1m"}
if WHAT == "mouse":
    KEYS = ["click1", "click3", "wheelup", "wheeldown", "drag", "click1shift"]
    MODES = {"sgr1000": "\\x1b[?1000h\\x1b[?1006h", "sgr1002": "\\x1b[?1002h\\x1b[?1006h", "x10": "\\x1b[?1000h", "any1003": "\\x1b[?1003h\\x1b[?1006h"}
env = dict(os.environ, DISPLAY=":96", FONTCONFIG_FILE=str(pixels.write_fonts_conf()), PURITTY_NO_XIM="1", PURITTY_DPI="96", LANG="C.UTF-8")
for k in ("TMUX","TMUX_PANE"): env.pop(k, None)
tm = lambda *a: subprocess.run([T, "-L", "kd", *a], env=env, capture_output=True, text=True).stdout
logger = S/"logger4.py"
logger.write_text('''import os, sys, tty, time
out = open(sys.argv[1], "ab", buffering=0)
tty.setraw(0)
os.write(1, sys.argv[2].encode().decode("unicode_escape").encode("latin1"))
while True:
    b = os.read(0, 256)
    if not b: break
    out.write(repr(b).encode() + b"\\n")
''')
def run(how, modes):
    log = S/f"kd-{how}.log"
    if log.exists(): log.unlink()
    tm("-f", "/dev/null", "new", "-d", "-s", "m", "-x", "100", "-y", "29", ";", "set", "-s", "extended-keys", EXT, ";",
       "set", "-g", "focus-events", "off", ";", "set", "-g", "mouse", "on" if WHAT == "mouse" else "off", ";", "respawn-pane", "-k", f"python3 {logger} {log} '{modes}'")
    time.sleep(0.5)
    cfg = S/"kd.toml"; cfg.write_text('[window]\ncolumns = 100\nrows = 30\n')
    args = [T, "-L", "kd", "-CC", "attach", "-t", "m"] if how == "cc" else [T, "-L", "kd", "attach", "-t", "m"]
    app = subprocess.Popen([str(P/"app"/"puritty"), "--config", str(cfg), "--title", "kd", "--", *args], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        win = subprocess.run([XDO, "search", "--sync", "--name", "kd|tmux"], env=env, capture_output=True, text=True, timeout=20).stdout.split()[0]
        subprocess.run([XDO, "windowfocus", "--sync", win], env=env); time.sleep(2.0)
        got = []
        for k in KEYS:
            before = log.read_bytes() if log.exists() else b""
            if k == "hangul_text":
                subprocess.run([XDO, "type", "한"], env=env)
            elif k == "click1":
                subprocess.run([XDO, "mousemove", "--window", win, str(9 * 5 + 4), str(17 * 6 + 8), "click", "1"], env=env)
            elif k == "click3":
                subprocess.run([XDO, "mousemove", "--window", win, str(9 * 7 + 4), str(17 * 3 + 8), "click", "3"], env=env)
            elif k == "wheelup":
                subprocess.run([XDO, "mousemove", "--window", win, str(9 * 10 + 4), str(17 * 10 + 8), "click", "4"], env=env)
            elif k == "wheeldown":
                subprocess.run([XDO, "click", "5"], env=env)
            elif k == "drag":
                subprocess.run([XDO, "mousemove", "--window", win, str(9 * 2 + 4), str(17 * 2 + 8), "mousedown", "1", "mousemove", "--window", win, str(9 * 6 + 4), str(17 * 4 + 8), "mouseup", "1"], env=env)
            elif k == "click1shift":
                subprocess.run([XDO, "mousemove", "--window", win, str(9 * 5 + 4), str(17 * 6 + 8), "keydown", "shift", "click", "1", "keyup", "shift"], env=env)
            else:
                subprocess.run([XDO, "key", k], env=env)
            time.sleep(0.35)
            after = log.read_bytes() if log.exists() else b""
            # the bytes read, joined: how they were split across reads is
            # the moment's, not the program's input
            import ast
            got.append(repr(b"".join(ast.literal_eval(line) for line in after[len(before):].decode().splitlines() if line.strip())))
        return got
    finally:
        app.terminate(); app.wait(); tm("kill-server")
x = subprocess.Popen([XVFB, ":96", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(0.8)
try:
    for name, modes in MODES.items():
        a = run("normal", modes); b = run("cc", modes)
        if not any(v != "b''" for v in a) or not any(v != "b''" for v in b):
            raise SystemExit(f"a run logged nothing (normal {sum(1 for v in a if v != chr(98)+chr(39)*2)}, cc {sum(1 for v in b if v != chr(98)+chr(39)*2)} events): the check sees nothing")
        diffs = [(k, x1, y1) for k, x1, y1 in zip(KEYS, a, b) if x1 != y1]
        print(f"== {T.split('/')[-3]} extended-keys {EXT}, app modes {name}: {len(diffs)} keys differ of {len(KEYS)}")
        for k, x1, y1 in diffs: print(f"   {k:14} normal {x1!s:30} cc {y1}")
finally:
    x.terminate(); x.wait()

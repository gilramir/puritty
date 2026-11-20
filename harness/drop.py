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
import argparse, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import hosts  # noqa: E402  (its xdotool)
import pixels  # noqa: E402  (its fonts)

APP = ROOT / "app" / "puritty"
WORK = ROOT / ".harness-work" / "drop"
PINS = ROOT / "harness" / "drop" / "expected"
RECORD = ROOT / "harness" / "drop" / "record-paste.py"
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
    try:
        for name, fm, items, charset in CASES:
            if a.only and name not in a.only:
                continue
            ran += 1
            got = run_case(env, name, fm, items, charset)
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

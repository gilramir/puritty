#!/usr/bin/env python3
"""The IME gate (docs/phase3-input.md V45): puritty with real IMEs.

For each IME and engine of the matrix (fcitx5 and ibus, each with Korean,
Japanese and pinyin), from the nixpkgs commit puritty's devbox pins
(harness/ime/imes.nix), on an Xvfb of its own with a session bus and a
fresh home: each case starts puritty on a program that records every byte
it receives on a raw terminal, types the case's keys with xdotool, and
pins two things to corpus/ime/CASE/IME-ENGINE.txt:

  - the bytes the program received, escaped;
  - puritty's IME log (PURITTY_IME_LOG): each commit and each preedit as
    puritty holds it after an IME event, in order.

How the preedit is drawn is the view gate's (corpus/view/cases/view-preedit-*).

usage:
    harness/ime.py               every case and pair
    harness/ime.py -f hangul     cases whose name contains "hangul"
    harness/ime.py --pair fcitx5-mozc
    harness/ime.py --update      write the pins; read the diff first

Build puritty first (app/build.sh). Run from puritty's devbox (Xvfb).
"""
import argparse, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "corpus" / "ime"
WORK = ROOT / ".harness-work" / "ime-gate"
PURITTY = ROOT / "app" / "puritty"
DISPLAY = ":81"

# IME, engine, the keys that switch the engine on for a new input context
PAIRS = [
    ("fcitx5", "hangul", ""), ("fcitx5", "mozc", ""), ("fcitx5", "pinyin", ""),
    ("ibus", "hangul", "key:Hangul"), ("ibus", "mozc-jp", "key:Zenkaku_Hankaku"), ("ibus", "libpinyin", ""),
]
KOREAN = {"hangul"}
JAPANESE = {"mozc", "mozc-jp"}
CHINESE = {"pinyin", "libpinyin"}

# name, the engines it is for, its keys (docs/phase3-input.md §3.2)
CASES = [
    ("hangul-return", KOREAN, "type:gks key:Return"),
    ("hangul-split", KOREAN, "type:gksks key:Return"),
    ("hangul-left", KOREAN, "type:gks key:Left"),
    ("hangul-ctrl-c", KOREAN, "type:gks key:ctrl+c"),
    ("hangul-backspace", KOREAN, "type:gks key:BackSpace key:BackSpace key:Return"),
    ("japanese-clauses", JAPANESE, "type:watashihanihongo key:space sleep:0.5 key:Right key:space sleep:0.5 key:Return"),
    ("chinese-pinyin", CHINESE, "type:nihao key:space"),
]


def build(attr):
    out = subprocess.run(["nix", "build", "--impure", "--no-link", "--print-out-paths", "-f",
                          str(ROOT / "harness/ime/imes.nix"), attr], capture_output=True, text=True, check=True)
    return [l for l in out.stdout.split() if not l.endswith("-man")][0]


def escaped(b):
    out = []
    for c in b.decode("utf-8", "backslashreplace"):
        if c == "\x1b": out.append("\\e")
        elif c == "\\": out.append("\\\\")
        elif ord(c) < 0x20 or c == "\x7f": out.append(f"\\x{ord(c):02x}")
        else: out.append(c)
    return "".join(out)


class Session:
    """One Xvfb, bus and IME for a pair."""

    def __init__(self, ime, engine, tools):
        self.ime, self.engine, self.tools = ime, engine, tools
        self.home = WORK / f"{ime}-{engine}"
        shutil.rmtree(self.home, ignore_errors=True)
        for d in ["config", "data", "cache", "runtime"]:
            (self.home / d).mkdir(parents=True)
        os.chmod(self.home / "runtime", 0o700)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / "config"),
                        XDG_DATA_HOME=str(self.home / "data"), XDG_CACHE_HOME=str(self.home / "cache"),
                        XDG_RUNTIME_DIR=str(self.home / "runtime"), DISPLAY=DISPLAY, LANG="C.UTF-8")
        self.procs = []
        self.procs.append(subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(0.7)
        bus = subprocess.run([tools["dbus"] + "/bin/dbus-launch", "--sh-syntax"], env=self.env,
                             capture_output=True, text=True, check=True).stdout
        for part in bus.split(";"):
            part = part.strip()
            if part.startswith("DBUS_SESSION_BUS_ADDRESS="):
                self.env["DBUS_SESSION_BUS_ADDRESS"] = part.split("=", 1)[1].strip("'")
            if part.startswith("DBUS_SESSION_BUS_PID="):
                self.bus_pid = int(part.split("=", 1)[1])
        log = open(self.home / "ime.log", "w")
        if ime == "fcitx5":
            c = self.home / "config" / "fcitx5"
            (c / "conf").mkdir(parents=True)
            (c / "profile").write_text(
                f"[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM={engine}\n\n[Groups/0/Items/0]\n"
                f"Name=keyboard-us\nLayout=\n\n[Groups/0/Items/1]\nName={engine}\nLayout=\n\n[GroupOrder]\n0=Default\n")
            (c / "config").write_text("[Behavior]\nActiveByDefault=True\nShareInputState=No\n")
            # puritty draws the preedit (on-the-spot, §3.1)
            (c / "conf" / "xim.conf").write_text("UseOnTheSpot=True\n")
            self.env["XMODIFIERS"] = "@im=fcitx"
            self.procs.append(subprocess.Popen(
                [tools["fcitx5"] + "/bin/fcitx5", "--disable=wayland,waylandim,notificationitem,kimpanel,clipboard"],
                env=self.env, stdout=log, stderr=log))
            time.sleep(2)
        else:
            self.env["XMODIFIERS"] = "@im=ibus"
            self.env["GSETTINGS_BACKEND"] = "memory"
            self.procs.append(subprocess.Popen([tools["ibus"] + "/bin/ibus-daemon", "--xim", "--panel=disable", "--replace"],
                                               env=self.env, stdout=log, stderr=log))
            time.sleep(2)
            subprocess.run([tools["ibus"] + "/bin/ibus", "engine", engine], env=self.env, stdout=log, stderr=log)
            time.sleep(0.5)

    def xdo(self, *args):
        subprocess.run([self.tools["xdotool"] + "/bin/xdotool", *args], env=self.env, check=True,
                       stdout=subprocess.DEVNULL)

    def reset(self):
        """ibus keeps an engine's mode (Hangul or Latin) across input
        contexts, so each case starts it afresh: another engine, then this
        one again."""
        if self.ime == "ibus":
            for e in ["xkb:us::eng", self.engine]:
                subprocess.run([self.tools["ibus"] + "/bin/ibus", "engine", e], env=self.env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.3)

    def run(self, keys):
        self.reset()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "received"
            v = subprocess.Popen([str(PURITTY), "--", "sh", "-c", f"stty raw -echo; exec cat > {out}"],
                                 env=dict(self.env, PURITTY_IME_LOG="1"), stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
            # keys go through the IME once puritty says its input context is
            # made; a key before that reaches the program as itself
            ready = False
            deadline = time.time() + 15
            while time.time() < deadline:
                line = v.stdout.readline()
                if not line:
                    break
                if line.strip() == b"ime ready":
                    ready = True
                    break
            win = subprocess.run([self.tools["xdotool"] + "/bin/xdotool", "search", "--sync", "--name", "puritty"],
                                 env=self.env, capture_output=True, text=True).stdout.split()
            if win:
                self.xdo("windowfocus", "--sync", win[0])
            time.sleep(0.3)
            for w in keys.split():
                kind, _, arg = w.partition(":")
                if kind == "type":
                    self.xdo("type", "--delay", "100", arg)
                elif kind == "key":
                    self.xdo("key", "--delay", "100", arg)
                elif kind == "sleep":
                    time.sleep(float(arg))
            time.sleep(1)
            v.send_signal(signal.SIGTERM)
            try:
                log, _ = v.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                v.kill()
                log, _ = v.communicate()
            received = out.read_bytes() if out.exists() else b""
        return ("" if ready else "NO IME\n") + "bytes " + escaped(received) + "\n" + log.decode("utf-8", "replace")

    def close(self):
        for p in reversed(self.procs):
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        if getattr(self, "bus_pid", None):
            try:
                os.kill(self.bus_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-f", dest="filter", default="")
    ap.add_argument("--pair", default="")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    tools = {k: build(k) for k in ["fcitx5", "ibus", "xdotool", "dbus"]}
    fails = runs = 0
    for ime, engine, prefix in PAIRS:
        pair = f"{ime}-{engine}"
        if a.pair and a.pair != pair:
            continue
        cases = [c for c in CASES if engine in c[1] and a.filter in c[0]]
        if not cases:
            continue
        s = Session(ime, engine, tools)
        try:
            for name, _, keys in cases:
                got = s.run((prefix + " " + keys).strip())
                pin = PINS / name / f"{pair}.txt"
                runs += 1
                if a.update:
                    pin.parent.mkdir(parents=True, exist_ok=True)
                    pin.write_text(got)
                    print(f"[ pin  ] {name} {pair}: {got.splitlines()[0]}")
                elif not pin.exists() or pin.read_text() != got:
                    fails += 1
                    print(f"[ FAIL ] {name} {pair}\n--- pinned\n{pin.read_text() if pin.exists() else '(none)'}--- got\n{got}")
                else:
                    print(f"[  ok  ] {name} {pair}")
        finally:
            s.close()
    print(f"{runs} runs: {runs - fails} pass" + (f", {fails} FAIL" if fails else ""))
    return 1 if fails else 0


sys.exit(main())

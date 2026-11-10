#!/usr/bin/env python3
"""The events gate on Windows (docs/windows.md WS19): packages/win32's
window driven by SendInput, and the event records Geng takes from it.

Each case, corpus/events/NAME.case, is actions for harness/events/drive.exe
(its comment names them): keys, characters, the pointer, the wheel and the
keyboard layout. On HOST, in the desktop session of the user logged on
there (harness/windows/inSession.ps1), harness/events/run.ps1 starts
harness/events/core-events.exe, which opens the window and writes every
event it takes as a line, and drive.exe makes the window the foreground
and does the case's actions, each only while the window has the
foreground; then asks it to close. The log is held to its pin,
corpus/events/NAME.txt.

What the window says as it opens (its size, the focus, the IME, a motion
if it opened under the pointer) depends on the order Windows does things
in and on where the pointer was, so the driver puts the pointer off the
window and types F24 before the case, the pin begins after F24's release,
and the gate asks only that the opening said `ime ready` and `focus in`. A
pin ends at `close`.

The records are packages/x11's, read as Linux reads them (WS5): a pin is
what Linux would give for the same keys, but for what WS19 lists.

usage (from puritty's devbox):
    harness/events.py                 every case, on beelink1
    harness/events.py -f hangul       cases whose name contains "hangul"
    harness/events.py --update        write the pins; read the diff first
    harness/events.py --host NAME     another Windows machine

The user must be logged on there with the screen unlocked, and away from
the keyboard: the driver stops at once if anything else takes the
foreground, and the case fails.
"""
import argparse, difflib, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "corpus" / "events"
WORK = ROOT / ".harness-work" / "events"
HERE = ROOT / "harness" / "events"
PROGRAM = HERE / "core-events.exe"
DRIVER = HERE / "drive.exe"
REMOTE = "geng-probe/events"


def build_driver():
    toolchain = subprocess.run([str(Path.home() / "prj/geng-lang/scripts/windows-toolchain.sh")], capture_output=True,
                               text=True, check=True).stdout
    env = dict(os.environ)
    for line in toolchain.splitlines():
        if line.startswith("export PATH="):
            env["PATH"] = line[len("export PATH="):].strip('"').replace("$PATH", env["PATH"])
    subprocess.run(["x86_64-w64-mingw32-clang", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-command-line-argument",
                    "-o", str(DRIVER), str(HERE / "drive.c"), "-luser32", "-lgdi32", "-static"], env=env, check=True)


def run(host, cases):
    ssh = ["ssh", "-o", "BatchMode=yes", host]
    ps = lambda cmd: subprocess.run(ssh + [f"powershell -NoProfile -Command \"{cmd}\""], capture_output=True, text=True)
    ps(f"Remove-Item -Recurse -Force {REMOTE}\\cases,{REMOTE}\\logs,{REMOTE}\\done.txt -ErrorAction SilentlyContinue;"
       f" New-Item -ItemType Directory -Force -Path {REMOTE}\\cases | Out-Null")
    subprocess.run(["scp", "-q", str(PROGRAM), str(DRIVER), str(HERE / "run.ps1"),
                    str(ROOT / "harness" / "windows" / "inSession.ps1"), f"{host}:{REMOTE}/"], check=True)
    subprocess.run(["scp", "-q", *map(str, cases), f"{host}:{REMOTE}/cases/"], check=True)
    home = subprocess.run(ssh + ["(Get-Location).Path"], capture_output=True, text=True).stdout.strip()
    remote = home + "\\" + REMOTE.replace("/", "\\")
    subprocess.run(ssh + [f"powershell -NoProfile -ExecutionPolicy Bypass -File {remote}\\inSession.ps1"
                          f" -Script {remote}\\run.ps1"], check=True)
    deadline = time.time() + 60 + 30 * len(cases)
    while time.time() < deadline:
        time.sleep(3)
        if ps(f"Test-Path {REMOTE}\\done.txt").stdout.strip() == "True":
            break
    else:
        raise RuntimeError("the run on Windows did not finish")
    stage = WORK / "logs"
    subprocess.run(["rm", "-rf", str(stage)], check=True)
    WORK.mkdir(parents=True, exist_ok=True)
    subprocess.run(["scp", "-q", "-r", f"{host}:{REMOTE}/logs", str(WORK)], check=True)
    # a case's pictures (its `shot`s), for a person to look at
    subprocess.run(["scp", "-q", f"{host}:{REMOTE}/*.bmp", str(stage)], capture_output=True)
    return stage


def trimmed(log):
    """The log after the driver's F24, which begins the case, and what the
    opening before it lacked."""
    lines = log.splitlines()
    begin = [i for i, l in enumerate(lines) if l.startswith("key release ") and " sym 0xffd5 " in l]
    if not begin:
        return [], ["F24"]
    i = begin[0] + 1
    lacks = [w for w in ("ime ready", "focus in") if w not in lines[:i]]
    return lines[i:], lacks


def main():
    ap = argparse.ArgumentParser(description="The events gate on Windows.")
    ap.add_argument("-f", "--filter", default="")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--host", default="beelink1")
    a = ap.parse_args()
    cases = sorted(c for c in CASES.glob("*.case") if a.filter in c.stem)
    if not cases:
        sys.exit("events.py: no case")
    if not PROGRAM.exists():
        sys.exit("events.py: build harness/events/core-events.exe first (harness/events/build-windows.sh)")
    build_driver()
    stage = run(a.host, cases)
    failed = []
    for case in cases:
        name = case.stem
        log = stage / f"{name}.txt"
        drive = (stage / f"{name}.drive").read_text(errors="replace").strip() if (stage / f"{name}.drive").exists() else ""
        if not drive.endswith("exit 0") or not log.exists():
            failed.append(name)
            print(f"FAIL {name}: the driver: {drive or 'nothing'}")
            continue
        got, lacks = trimmed(log.read_text(encoding="utf-8", errors="replace"))
        if lacks:
            failed.append(name)
            print(f"FAIL {name}: the opening lacked {', '.join(lacks)}")
            continue
        pin = CASES / f"{name}.txt"
        if a.update:
            pin.write_text("\n".join(got) + "\n", encoding="utf-8")
            continue
        want = pin.read_text(encoding="utf-8").splitlines() if pin.exists() else []
        if got != want:
            failed.append(name)
            print(f"FAIL {name}:")
            sys.stdout.writelines(l + "\n" for l in difflib.unified_diff(want, got, "pin", "got", lineterm=""))
    total = len(cases)
    if a.update:
        print(f"{total - len(failed)} pins written" + (f", {len(failed)} failed" if failed else ""))
    else:
        print(f"{total - len(failed)} of {total} cases pass")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

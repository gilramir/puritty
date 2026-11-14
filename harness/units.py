#!/usr/bin/env python3
"""The unit suites' gate (docs/vt-core.md VC61, VC62): every gren-unit-node
suite puritty has, built and run where puritty runs, each held to its count.

- on node: vt, tmux and the application's suites (each `run.sh`);
- natively on Linux: the same three (`native/run.sh`), ssh-crypto's
  vectors, and ssh-tests' known-hosts, config and connection cases;
- on Windows: the same, cross-compiled and run on beelink1 over ssh.

A run passes when the program ends with status 0 and its runner says
"OK — N passed" with N the count below. A count moves only with the commit
that moves it, as geng-lang's suites.py holds its suites (D356).

Before the suites, every Geng source is held to `geng fmt`
(`scripts/fmt.sh --check`), and the whole program to its checks list
(`scripts/checks.sh`, docs/vt-core.md §VC66): an unformatted file, a new
fallback that can run and is not meant, an open check, a stale `meant` or
an unused reason fails the gate. `--no-checks` leaves the checks out on
purpose, saying so.

Windows is part of the gate: when beelink1 cannot be reached the gate
fails, and `--no-windows` leaves Windows out on purpose, saying so.

usage (from puritty's devbox):
    harness/units.py                  every suite, every platform
    harness/units.py --no-windows     node and Linux only
    harness/units.py -s app -s vt     some suites
    harness/units.py -v               each run's report
"""

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / ".harness-work" / "units"
WINDOWS_HOST = "beelink1"
WINDOWS_DIR = "geng-probe/units"
MEMORY = "8G"


@dataclass
class Run:
    """One build and run of a suite: `build` makes the program (or, for
    `run.sh`-style scripts, builds and runs it); `run` runs what was built,
    with its arguments, in `cwd`."""

    platform: str
    build: list[str]
    run: list[str] | None = None
    cwd: str = "."
    # Windows: the program and the files it reads, copied to beelink1
    exe: str | None = None
    files: list[str] = field(default_factory=list)


@dataclass
class Suite:
    name: str
    expected: int
    runs: list[Run]


def runs_of(folder: str, node: bool = True) -> list[Run]:
    """A suite with a node `run.sh` and a `native/run.sh` that also builds
    `native/tests.exe` with `--windows`."""
    out = []
    if node:
        out.append(Run("node", [f"{folder}/run.sh"]))
    out += [
        Run("linux", [f"{folder}/native/run.sh"]),
        Run("windows", [f"{folder}/native/run.sh", "--windows"], exe=f"{folder}/native/tests.exe"),
    ]
    return out


SUITES = [
    Suite("vt", 94, runs_of("vt/tests")),
    # 100 since VC63: a choice moved on from the last
    Suite("tmux", 100, runs_of("packages/tmux/tests")),
    Suite(
        "app",
        # 162 since TM70: a tmux -CC that never attaches, two. 170 since
        # TB15: the tab order's moves and closings, eight. 173 since SN7: a
        # sound heard as it is chosen, three
        173,
        [
            Run("node", ["app/tests/run.sh"]),
            Run("linux", ["app/tests/native/run.sh"]),
            Run("windows", ["app/tests/windows/build.sh"], exe="app/tests/windows/tests.exe"),
        ],
    ),
    Suite(
        "ssh-crypto",
        10,
        [
            Run("linux", ["packages/ssh-crypto/tests/build.sh"], ["./ssh-crypto-tests"], cwd="packages/ssh-crypto/tests"),
            Run(
                "windows",
                ["packages/ssh-crypto/tests/build.sh", "--windows"],
                ["vectors.txt"],
                exe="packages/ssh-crypto/tests/ssh-crypto-tests.exe",
                files=["packages/ssh-crypto/tests/vectors.txt"],
            ),
        ],
    ),
    Suite(
        "ssh-known-hosts",
        34,
        [
            Run("linux", ["packages/ssh/tests/build.sh"], ["./ssh-tests", "known-hosts", "known-hosts.txt"], cwd="packages/ssh/tests"),
            Run(
                "windows",
                ["packages/ssh/tests/build.sh", "--windows"],
                ["known-hosts", "known-hosts.txt"],
                exe="packages/ssh/tests/ssh-tests.exe",
                files=["packages/ssh/tests/known-hosts.txt"],
            ),
        ],
    ),
    Suite(
        "ssh-config",
        # 45 since SC27: time forms, and lines OpenSSH refuses, fifteen
        45,
        [
            Run("linux", ["packages/ssh/tests/build.sh"], ["./ssh-tests", "config", "config-cases.txt"], cwd="packages/ssh/tests"),
            Run(
                "windows",
                ["packages/ssh/tests/build.sh", "--windows"],
                ["config", "config-cases.txt"],
                exe="packages/ssh/tests/ssh-tests.exe",
                files=["packages/ssh/tests/config-cases.txt"],
            ),
        ],
    ),
    Suite(
        # since SC27: a channel message that does not read ends the session
        "ssh-connection",
        5,
        [
            Run("linux", ["packages/ssh/tests/build.sh"], ["./ssh-tests", "connection"], cwd="packages/ssh/tests"),
            Run(
                "windows",
                ["packages/ssh/tests/build.sh", "--windows"],
                ["connection"],
                exe="packages/ssh/tests/ssh-tests.exe",
            ),
        ],
    ),
]


def capped(cmd: list[str]) -> list[str]:
    return ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={MEMORY}", "-p", "MemorySwapMax=0", *cmd]


def passed(output: str) -> int | None:
    """The count the runner reported passed, or None when it said nothing."""
    m = re.findall(r"^OK — (\d+) passed\s*$", output, re.M)
    if m:
        return int(m[-1])
    m = re.findall(r"^FAILED — (\d+) passed", output, re.M)
    return int(m[-1]) if m else None


def windows(run: Run, log: Path) -> subprocess.CompletedProcess:
    """The program and its files copied to beelink1 and run there."""
    exe = ROOT / run.exe
    name = exe.name
    copy = subprocess.run(
        ["timeout", "180", "scp", "-q", str(exe), *[str(ROOT / f) for f in run.files], f"{WINDOWS_HOST}:{WINDOWS_DIR}/"],
        capture_output=True, text=True,
    )
    if copy.returncode != 0:
        return copy
    args = " ".join(f"'{a}'" for a in (run.run or []))
    script = f"cd {WINDOWS_DIR}; .\\{name} {args}; exit $LASTEXITCODE"
    return subprocess.run(["timeout", "600", "ssh", WINDOWS_HOST, script], capture_output=True, text=True)


def windows_ready() -> str | None:
    """Why beelink1 cannot run the Windows programs, or None."""
    r = subprocess.run(
        ["timeout", "30", "ssh", "-o", "ConnectTimeout=10", WINDOWS_HOST, f"New-Item -ItemType Directory -Force {WINDOWS_DIR} | Out-Null"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return f"{WINDOWS_HOST} cannot be reached: {(r.stderr or r.stdout).strip()[:200]}"
    return None


def one(suite: Suite, run: Run, verbose: bool) -> tuple[bool, str, list[str]]:
    WORK.mkdir(parents=True, exist_ok=True)
    log = WORK / f"{suite.name}-{run.platform}.log"
    start = time.monotonic()
    build = subprocess.run(capped([str(ROOT / run.build[0]), *run.build[1:]]), cwd=ROOT, capture_output=True, text=True)
    text = build.stdout + build.stderr
    if run.platform == "windows" or run.run is not None:
        if build.returncode != 0:
            log.write_text(text)
            return False, f"does not build (exit {build.returncode}; {log.relative_to(ROOT)})", text.splitlines()[-30:]
        if run.platform == "windows":
            result = windows(run, log)
        else:
            result = subprocess.run(capped(run.run), cwd=ROOT / run.cwd, capture_output=True, text=True)
        text += result.stdout + result.stderr
        status = result.returncode
    else:
        status = build.returncode
    log.write_text(text)
    got = passed(text)
    took = time.monotonic() - start
    ok = status == 0 and got == suite.expected
    said = f"passed {got} of {suite.expected} expected, exit {status}, {took:.0f} s"
    tail = text.splitlines()[-40:] if (verbose or not ok) else []
    return ok, said, tail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-s", "--suite", action="append", choices=[s.name for s in SUITES], help="suite(s) to run")
    ap.add_argument("--no-windows", action="store_true", help="leave Windows out, on purpose")
    ap.add_argument("--no-checks", action="store_true", help="leave geng checks out, on purpose")
    ap.add_argument("-v", "--verbose", action="store_true", help="print each run's report")
    args = ap.parse_args()

    if not shutil.which("pkg-config"):
        print("units.py: run from puritty's devbox (the X11 build needs its libraries)", file=sys.stderr)
        return 2
    chosen = [s for s in SUITES if not args.suite or s.name in args.suite]
    formatted = subprocess.run([str(ROOT / "scripts" / "fmt.sh"), "--check"], cwd=ROOT, capture_output=True, text=True)
    fmt_ok = formatted.returncode == 0
    print(f"[{'  ok  ' if fmt_ok else ' FAIL '}] {'fmt':<24} {(formatted.stdout + formatted.stderr).strip().splitlines()[-1] if (formatted.stdout + formatted.stderr).strip() else ''}")
    if not fmt_ok:
        for line in (formatted.stdout + formatted.stderr).strip().splitlines()[:40]:
            print("         " + line)
    checks_ok = True
    if args.no_checks:
        print(f"[ skip ] {'checks':<24} left out by --no-checks")
    else:
        start_checks = time.monotonic()
        checked = subprocess.run(
            ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=16G", "-p", "MemorySwapMax=0",
             str(ROOT / "scripts" / "checks.sh")],
            cwd=ROOT, capture_output=True, text=True,
        )
        text = checked.stdout + checked.stderr
        (WORK).mkdir(parents=True, exist_ok=True)
        (WORK / "checks.log").write_text(text)
        totals = next((l.strip() for l in text.splitlines() if "checks hold" in l and "fallbacks never run" in l), "")
        against = next((l.strip() for l in text.splitlines() if "entries against" in l), "")
        checks_ok = checked.returncode == 0
        print(f"[{'  ok  ' if checks_ok else ' FAIL '}] {'checks':<24} {totals}; {against} ({time.monotonic() - start_checks:.0f} s)")
        if not checks_ok:
            for line in [l for l in text.splitlines() if l.startswith(("NEW", "  STALE", "  UNUSED", "  open"))][:40]:
                print("         " + line)
            print(f"         the whole report: {(WORK / 'checks.log').relative_to(ROOT)}")
    sys.stdout.flush()
    why_not = None if args.no_windows else windows_ready()
    start = time.monotonic()
    failed = []
    for suite in chosen:
        for run in suite.runs:
            label = f"{suite.name} {run.platform}"
            if run.platform == "windows" and args.no_windows:
                print(f"[ skip ] {label:<24} left out by --no-windows")
                continue
            if run.platform == "windows" and why_not:
                print(f"[ FAIL ] {label:<24} {why_not}")
                failed.append(label)
                continue
            ok, said, tail = one(suite, run, args.verbose)
            print(f"[{'  ok  ' if ok else ' FAIL '}] {label:<24} {said}")
            for line in tail:
                print("         " + line)
            sys.stdout.flush()
            if not ok:
                failed.append(label)
    total = sum(len([r for r in s.runs if not (args.no_windows and r.platform == "windows")]) for s in chosen)
    print(f"\n{total - len(failed)}/{total} runs pass in {time.monotonic() - start:.0f} s")
    if args.no_windows:
        print("Windows was left out (--no-windows): this is not the whole gate.")
    if args.no_checks:
        print("geng checks was left out (--no-checks): this is not the whole gate.")
    return 1 if failed or not fmt_ok or not checks_ok else 0


if __name__ == "__main__":
    sys.exit(main())

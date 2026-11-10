#!/usr/bin/env python3
"""The settings file's writes on the system (docs/settings.md ST6, ST18):
harness/store/store (harness/store/build.sh) changes a settings file
through `SettingsFile.change` in a new directory, step by step, and
writes each step's file, its backup and any `.new` left; this holds what
it writes to harness/store/expected.txt.

With `--windows HOST` it runs harness/store/store.exe
(harness/store/build-windows.sh) there instead, in `geng-probe/store`, and
holds it to the same pin: the steps are the same on both systems.

usage:
    harness/store.py
    harness/store.py --windows beelink1
    harness/store.py --update        write the pin; read the diff first
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "harness" / "store"
PIN = HERE / "expected.txt"
REMOTE = "geng-probe/store"


def run_linux():
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([str(HERE / "store"), d], capture_output=True, timeout=60)
    return p.stdout.decode("utf-8", errors="replace"), p.returncode


def run_windows(host):
    ssh = ["ssh", "-o", "BatchMode=yes", host]
    subprocess.run(ssh + [f"powershell -NoProfile -Command \"Remove-Item -Recurse -Force {REMOTE} -ErrorAction SilentlyContinue;"
                          f" New-Item -ItemType Directory -Force -Path {REMOTE}\\work | Out-Null\""], check=True)
    subprocess.run(["scp", "-q", str(HERE / "store.exe"), f"{host}:{REMOTE}/"], check=True)
    p = subprocess.run(ssh + [f"cmd /c \"cd {REMOTE} && store.exe work > out.txt\""], capture_output=True, timeout=120)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["scp", "-q", f"{host}:{REMOTE}/out.txt", d], check=True)
        return (Path(d) / "out.txt").read_bytes().decode("utf-8", errors="replace"), p.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--windows", metavar="HOST", default="")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    exe = HERE / ("store.exe" if a.windows else "store")
    if not exe.exists():
        sys.exit(f"store.py: build {exe} first ({'build-windows.sh' if a.windows else 'build.sh'})")
    got, code = run_windows(a.windows) if a.windows else run_linux()
    if a.update:
        PIN.write_text(got)
        print(f"wrote {PIN}")
        return
    want = PIN.read_text()
    if got == want and code == 0:
        print("ok: the file's writes are as pinned")
        return
    import difflib
    sys.stdout.writelines(difflib.unified_diff(want.splitlines(True), got.splitlines(True), "expected.txt", "got"))
    print(f"FAIL (exit {code})")
    sys.exit(1)


if __name__ == "__main__":
    main()

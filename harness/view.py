#!/usr/bin/env python3
"""The display-list gate (docs/renderer.md §R8).

A case whose name says `unfocused` is drawn as a window without the focus
has, and one whose directory has a `preedit.txt` (its text, each code
point's XIM feedback, the caret, a line each) has that preedit drawn over
every frame (docs/phase3-input.md V46), and one with a `back.txt` (offsets)
has a frame more for each after its input, the view scrolled back that many
rows (docs/phase3-select.md §11)
draws it. Every case of corpus/replay/ and of corpus/view/cases/ (the same
`case.txt` format, harness/replay.py's) is fed to the core and Vt.View by
harness/view/core-view, CHUNK bytes a read with a frame after each, and
each frame's display list is decoded here and held to its pin,
corpus/view/NAME.txt. The decoder is a second reader of the format
Vt.View's comment gives, and it checks what the format promises of every
frame, pinned or not:

  - the first frame says the screen's size, and a frame says it again
    exactly when it changes;
  - every style a run uses has its record earlier in the same frame, and
    no style has two (V35: what executes a list keeps no table);
  - a style has a cursor shape exactly when its id is a cursor's (0x8000
    and more);
  - a scroll's band and shift stay on the screen, and its shift is not 0;
  - a run is on the screen, does not start on a wide character's tail,
    and does not end on its head;
  - every record reads to its end, and nothing follows the last.

usage:
    harness/view.py              every case
    harness/view.py -f wrap      cases whose name contains "wrap"
    harness/view.py --update     write the pins; read the diff before
                                 committing it
    harness/view.py --show NAME  print one case's decoded frames
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import parse_resizing, first_difference  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "corpus" / "replay"
CASES = ROOT / "corpus" / "view" / "cases"
PINS = ROOT / "corpus" / "view"
VIEW = ROOT / "harness" / "view" / "core-view"
CHUNK = 16
SHAPES = {1: "block", 2: "underline", 3: "bar", 4: "hollow"}


def frames_of(size, resizes):
    """How many frames core-view draws: one a read, a read CHUNK bytes and
    never across a resize."""
    n, at, pending = 0, 0, [a for a, _, _ in resizes]
    while True:
        if pending and pending[0] <= at:
            pending.pop(0)
            continue
        if not pending and at >= size:
            return n
        at = min(at + CHUNK, pending[0]) if pending else at + CHUNK
        n += 1


def decode(data, size):
    """A frame's list as lines, the screen's size after it, and what it
    breaks of the format. `size` is the last frame's, None before the
    first."""
    lines, errors, styles, i = [], [], set(), 0
    if len(data) >= 5 and data[0] == 4:
        new = ((data[1] << 8) | data[2], (data[3] << 8) | data[4])
        if new == size:
            errors.append(f"a size record for the size it already had, {new[0]}x{new[1]}")
        size = new
        lines.append(f"  size {size[0]}x{size[1]}")
        i = 5
    elif size is None:
        errors.append("the first frame has no size record")
        size = (0, 0)
    cols, rows = size

    def u16(j):
        return (data[j] << 8) | data[j + 1]

    def u24(j):
        return (data[j] << 16) | (data[j + 1] << 8) | data[j + 2]

    while i < len(data):
        kind = data[i]
        if kind == 3:
            if i + 14 > len(data):
                errors.append("a style record cut short")
                break
            sid = u16(i + 1)
            if sid in styles:
                errors.append(f"style {sid} twice")
            styles.add(sid)
            ul, shape = data[i + 13] & 15, data[i + 13] >> 4
            if (sid >= 0x8000) != (shape != 0) or shape > 4:
                errors.append(f"style {sid} with cursor shape {shape}")
            name = f"cursor {SHAPES[shape]} on {sid - 0x8000}" if sid >= 0x8000 else f"style {sid}"
            lines.append(f"  {name} fg #{u24(i + 3):06x} bg #{u24(i + 6):06x} "
                         f"ul #{u24(i + 9):06x} flags {data[i + 12]:#04x} ul {ul}")
            i += 14
        elif kind == 1:
            if i + 7 > len(data):
                errors.append("a scroll record cut short")
                break
            top, bottom, k = u16(i + 1), u16(i + 3), u16(i + 5)
            k = k - 0x10000 if k >= 0x8000 else k
            if k == 0 or top > bottom or top < 0 or bottom >= rows or top + k < 0 or bottom + k >= rows:
                errors.append(f"scroll {top}-{bottom} by {k} off a screen of {rows} rows")
            lines.append(f"  scroll {top}-{bottom} by {k}")
            i += 7
        elif kind == 2:
            if i + 7 > len(data):
                errors.append("a run record cut short")
                break
            y, x, n = u16(i + 1), u16(i + 3), u16(i + 5)
            if y >= rows or x + n > cols or n <= 0:
                errors.append(f"run at row {y} col {x} of {n} off a screen of {cols}x{rows}")
            j, text, widths, runs = i + 7, [], [], []
            for c in range(n):
                if j + 3 > len(data):
                    errors.append("a run's cell cut short")
                    break
                wide, count, sid = data[j] >> 6, data[j] & 63, u16(j + 1)
                j += 3
                points = [u24(j + 3 * m) for m in range(count)]
                j += 3 * count
                if sid not in styles:
                    errors.append(f"style {sid} used before its record")
                if c == 0 and wide == 2:
                    errors.append(f"run at row {y} col {x} starts on a wide character's tail")
                if c == n - 1 and wide == 1:
                    errors.append(f"run at row {y} col {x} ends on a wide character's head")
                widths.append("nWts"[wide])
                text.append("" if wide >= 2 else ("".join(map(chr, points)) if points else " "))
                if runs and runs[-1][0] == sid:
                    runs[-1][1] += 1
                else:
                    runs.append([sid, 1])
            line = f"  run {y},{x}+{n} {json.dumps(''.join(text), ensure_ascii=False)}"
            if any(w != "n" for w in widths):
                line += " widths " + "".join(widths)
            line += " styles " + " ".join((f"c{s - 0x8000}" if s >= 0x8000 else str(s)) + (f"*{m}" if m > 1 else "") for s, m in runs)
            lines.append(line)
            i = j
        elif kind == 4:
            errors.append(f"a size record at byte {i}, not first")
            break
        else:
            errors.append(f"a record of kind {kind} at byte {i}")
            break
    return lines, size, errors


def view_of(name, text, tmp):
    cols, rows, data, resizes = parse_resizing(text)
    path = Path(tmp) / "input"
    path.write_bytes(data)
    extra = [",".join(f"{a}:{c}x{r}" for a, c, r in resizes)] if resizes else []
    if "unfocused" in name:
        extra = (extra or [""]) + ["unfocused"]
    pre = CASES / name / "preedit.txt"
    if pre.exists():
        # three lines: the text, each code point's feedback, the caret
        text, feedback, caret = (pre.read_text().split("\n") + ["", "", ""])[:3]
        extra = (extra or [""])
        extra = extra + ([] if len(extra) > 1 else ["focused"])
        extra = extra + [text.encode().hex() + "|" + ",".join(feedback.split()) + "|" + (caret.strip() or "0")]
    back = CASES / name / "back.txt"
    backs = []
    if back.exists():
        # the view scrolled back by each offset in turn, after the input
        backs = back.read_text().split()
        # RESIZES, FOCUS and PREEDIT come before BACKS: their defaults
        extra = extra + ["", "focused", ""][len(extra):] + [",".join(backs)]
    p = subprocess.run(
        ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=4G", "-p", "MemorySwapMax=0", "--",
         "timeout", "60", str(VIEW), str(cols), str(rows), str(path), str(CHUNK)] + extra,
        capture_output=True)
    if p.returncode != 0:
        return None, [p.stderr.decode(errors="replace").strip() or f"core-view exited {p.returncode}"]
    frames = [l for l in p.stdout.decode().splitlines() if l.startswith("frame")]
    want = frames_of(len(data), resizes) + len(backs)
    if len(frames) != want:
        return None, [f"{len(frames)} frames, where the reads make {want}"]
    out, errors, size = [], [], None
    for n, line in enumerate(frames, 1):
        hexes = line[len("frame"):].split()
        lines, size, errs = decode(bytes(int(h, 16) for h in hexes), size)
        out.append(f"frame {n}" + ("" if lines else ": nothing"))
        out += lines
        errors += [f"frame {n}: {e}" for e in errs]
    return "\n".join(out) + "\n", errors


def cases(filter_):
    found = {}
    for root in (REPLAY, CASES):
        if root.exists():
            for d in sorted(root.iterdir()):
                if d.is_dir() and (d / "case.txt").exists() and filter_ in d.name:
                    if d.name in found:
                        sys.exit(f"two cases named {d.name}")
                    found[d.name] = d / "case.txt"
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-f", "--filter", default="")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--show")
    args = ap.parse_args()
    if not VIEW.exists():
        sys.exit(f"{VIEW} is not built: run {VIEW.parent}/build.sh")
    found = cases(args.show or args.filter)
    if args.show:
        found = {k: v for k, v in found.items() if k == args.show}
    failed = updated = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, path in found.items():
            got, errors = view_of(name, path.read_text(), tmp)
            if args.show:
                sys.stdout.write(got or "")
                for e in errors:
                    print("BROKEN", e)
                continue
            pin = PINS / f"{name}.txt"
            if errors:
                failed += 1
                print(f"[ FAIL ] {name}: {errors[0]}" + (f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""))
                continue
            if args.update:
                if not pin.exists() or pin.read_text() != got:
                    pin.write_text(got)
                    updated += 1
                continue
            if not pin.exists():
                failed += 1
                print(f"[ FAIL ] {name}: no pin (--update writes it)")
            elif pin.read_text() != got:
                failed += 1
                print(f"[ FAIL ] {name}: {first_difference(pin.read_text(), got)}")
    if args.show:
        return
    if args.update:
        print(f"{len(found)} cases, {updated} pins written, {failed} broken")
    else:
        print(f"{len(found)} cases: {len(found) - failed} pass, {failed} fail")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

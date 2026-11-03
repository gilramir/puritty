#!/usr/bin/env python3
"""The mouse gate (docs/phase3-select.md §4, §11): Vt.Mouse.encode against
libghostty-vt's mouse encoder, the same bytes for every event.

    mouse.py [N] [--seed S]

N cases (default 200,000) are drawn from the seed. Each is a run of mode
changes fed to a terminal (modes 9, 1000, 1002, 1003, 1005, 1006, 1015 and
1016 set and reset, alone or several to a sequence, XTSAVE and XTRESTORE,
DECSTR and RIS), so that the core's bookkeeping of the tracking and format
is held to Ghostty's as well as the encoder; a window size, cell size and
padding; whether the last cell is tracked; and one to eight events: press,
release or motion, any of Ghostty's buttons or none, any modifiers, a
position inside the window or outside it, and whether a button is held.
Both programs read the same file; the gate fails on the first case they
differ on and prints up to twenty. Build mouse/core-mouse (mouse/build.sh)
and oracle/ghostty-mouse (oracle/build.sh) first.
"""
import argparse, pathlib, random, subprocess, sys

HERE = pathlib.Path(__file__).parent
WORK = HERE / "../.harness-work/mouse"
MODES = [9, 1000, 1002, 1003, 1005, 1006, 1015, 1016]


def modes(rng):
    out = []
    for _ in range(rng.randrange(0, 6)):
        r = rng.random()
        if r < 0.6:
            ps = ";".join(str(rng.choice(MODES)) for _ in range(rng.choice([1, 1, 1, 2, 3])))
            out.append(f"\x1b[?{ps}{rng.choice('hhl')}")
        elif r < 0.75:
            out.append(f"\x1b[?{rng.choice(MODES)}s")
        elif r < 0.9:
            out.append(f"\x1b[?{rng.choice(MODES)}r")
        elif r < 0.95:
            out.append("\x1b[!p")
        else:
            out.append("\x1bc")
    # most cases end with a program asking for reports, so that most events
    # are encoded rather than dropped
    if rng.random() < 0.8:
        out.append(f"\x1b[?{rng.choice([9, 1000, 1002, 1003, 1003])}h")
    if rng.random() < 0.7:
        out.append(f"\x1b[?{rng.choice([1005, 1006, 1006, 1015, 1016])}h")
    return "".join(out).encode().hex() or "-"


def case(rng):
    cw, ch = rng.randrange(1, 30), rng.randrange(1, 40)
    if rng.random() < 0.15:
        cw, ch = 1, 1
    w, h = rng.randrange(1, 2400), rng.randrange(1, 1600)
    pad = [rng.randrange(0, 25) if rng.random() < 0.5 else 0 for _ in range(4)]
    track = 1 if rng.random() < 0.8 else 0
    events = []
    for _ in range(rng.randrange(1, 9)):
        action = rng.choice([0, 1, 2, 2])
        button = 0 if action == 2 and rng.random() < 0.4 else rng.randrange(0, 12)
        mods = rng.randrange(16) if rng.random() < 0.5 else 0
        if rng.random() < 0.1:
            mods |= rng.choice([16, 32, 64, 128, 256])
        if rng.random() < 0.85:
            x, y = rng.randrange(0, w + 1), rng.randrange(0, h + 1)
        else:
            x, y = rng.randrange(-60, w + 60), rng.randrange(-60, h + 60)
        if events and rng.random() < 0.3:
            # the same cell again, or a pixel beside the last
            px, py = events[-1][3], events[-1][4]
            x, y = px + rng.randrange(-1, 2), py + rng.randrange(-1, 2)
        events.append((action, button, mods, x, y, rng.randrange(2)))
    head = " ".join(map(str, [modes(rng), w, h, cw, ch, *pad, track]))
    return head + "".join(" ; " + " ".join(map(str, e)) for e in events)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("n", nargs="?", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"cases-{a.seed}-{a.n}.txt"
    lines = [case(rng) for _ in range(a.n)]
    path.write_text("\n".join(lines) + "\n")
    want = subprocess.run([str(HERE / "oracle/ghostty-mouse")], stdin=open(path), capture_output=True, text=True, check=True).stdout.splitlines()
    got = subprocess.run([str(HERE / "mouse/core-mouse"), str(path)], capture_output=True, text=True, check=True).stdout.splitlines()
    if len(want) != len(lines) or len(got) != len(lines):
        print(f"FAIL: {len(lines)} cases, oracle answered {len(want)}, core {len(got)}")
        return 1
    bad = [(l, w, g) for l, w, g in zip(lines, want, got) if w != g]
    for l, w, g in bad[:20]:
        print(f"case  {l}\nghostty {w}\ncore    {g}\n")
    events = sum(len(w.split()) for w in want)
    print(f"{'FAIL' if bad else 'ok'}: {len(lines) - len(bad)} of {len(lines)} cases agree, {events} events (seed {a.seed})")
    return 1 if bad else 0


sys.exit(main())

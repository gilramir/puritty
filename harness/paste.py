#!/usr/bin/env python3
"""The paste gate (docs/phase3-select.md §15): Vt.Paste.encode against
libghostty-vt's ghostty_paste_encode, the same bytes for every case.

    paste.py [N] [--seed S]

N cases (default 100,000) are drawn from the seed: bracketed or not, and
up to 300 bytes of text made of printable ASCII, every control byte, DEL,
LF, CR and CR LF, the bracket's own end `ESC[201~` and start, and UTF-8 of
one to four bytes. The Geng side also encodes each case in pieces and
holds them to the whole. Both programs read the same file; the gate fails
on the first case they differ on and prints up to twenty. Build
paste/core-paste (paste/build.sh) and oracle/ghostty-paste (oracle/build.sh)
first.
"""
import argparse, pathlib, random, subprocess, sys

HERE = pathlib.Path(__file__).parent
WORK = HERE / "../.harness-work/paste"
PIECES = [b"\n", b"\r", b"\r\n", b"\x1b[201~", b"\x1b[200~", b"\x7f", b"\t", "é".encode(), "한".encode(),
          "😀".encode(), "€".encode(), b"echo hi; rm -rf ~"]


def case(rng):
    out = bytearray()
    for _ in range(rng.randrange(0, 40)):
        r = rng.random()
        if r < 0.4:
            out += bytes(rng.randrange(0x20, 0x7F) for _ in range(rng.randrange(1, 8)))
        elif r < 0.65:
            out.append(rng.randrange(0, 0x20))
        else:
            out += rng.choice(PIECES)
    return f"{rng.randrange(2)} {out.hex() or '-'}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("n", nargs="?", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"cases-{a.seed}-{a.n}.txt"
    lines = [case(rng) for _ in range(a.n)]
    path.write_text("\n".join(lines) + "\n")
    want = subprocess.run([str(HERE / "oracle/ghostty-paste")], stdin=open(path), capture_output=True, text=True, check=True).stdout.splitlines()
    got = subprocess.run([str(HERE / "paste/core-paste"), str(path)], capture_output=True, text=True, check=True).stdout.splitlines()
    if len(want) != len(lines) or len(got) != len(lines):
        print(f"FAIL: {len(lines)} cases, oracle answered {len(want)}, core {len(got)}")
        return 1
    bad = [(l, w, g) for l, w, g in zip(lines, want, got) if w != g]
    for l, w, g in bad[:20]:
        print(f"case  {l}\nghostty {w}\ncore    {g}\n")
    print(f"{'FAIL' if bad else 'ok'}: {len(lines) - len(bad)} of {len(lines)} cases agree (seed {a.seed})")
    return 1 if bad else 0


sys.exit(main())

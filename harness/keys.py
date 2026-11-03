#!/usr/bin/env python3
"""The key gate (docs/phase3-input.md V47): Vt.Keys.encode against
libghostty-vt's key encoder, the same bytes for every case.

    keys.py [N] [--seed S]

N cases (default 300,000) are drawn from the seed: any of Ghostty's 176
keys, press, repeat or release, any modifiers with locks and sides, consumed
shift, composing, text that is empty, the key's own character, its shifted
form, a control character, non-ASCII or two code points, and every option
(DECCKM, DECKPAM, DECBKM, 1035, 1036, modifyOtherKeys 2, kitty flags). Both
programs read the same file; the gate fails on the first case they differ on
and prints up to twenty. Build keys/core-keys (keys/build.sh) and
oracle/ghostty-keys (oracle/build.sh) first.
"""
import argparse, pathlib, random, re, subprocess, sys

HERE = pathlib.Path(__file__).parent
WORK = HERE / "../.harness-work/keys"
TABLES = HERE / "../vt/src/Vt/KeyTables.geng"

SHIFTED = dict(zip(r"`1234567890-=[]\;',./", "~!@#$%^&*()_+{}|:\"<>?"))


def codepoints():
    s = TABLES.read_text()
    body = s[s.index("codepointTable =") :]
    body = body[body.index("[") + 1 : body.index("]")]
    return [int(x) for x in re.findall(r"\d+", body)]


def case(rng, cps):
    key = rng.randrange(len(cps))
    cp = cps[key]
    mods = rng.randrange(16) if rng.random() < 0.7 else 0
    if rng.random() < 0.1:
        mods |= 16
    if rng.random() < 0.1:
        mods |= 32
    for bit, side in [(1, 64), (2, 128), (4, 256), (8, 512)]:
        if mods & bit and rng.random() < 0.2:
            mods |= side
    shift, ctrl = mods & 1, mods & 2
    r = rng.random()
    if r < 0.2 or cp == 0 and r < 0.5:
        text = ""
    elif r < 0.55 and cp:
        c = chr(cp)
        if shift:
            c = c.upper() if c.isalpha() else SHIFTED.get(c, c)
        if ctrl and c.isalpha():
            c = chr(ord(c.lower()) - 0x60)
        text = c
    elif r < 0.65:
        text = rng.choice(["\r", "\t", "\x7f", "\x1b", "\x08", "\x03", " "])
    elif r < 0.8:
        text = rng.choice(["é", "한", "ж", "€", "ß", "あ", "😀"])
    elif r < 0.9:
        text = rng.choice(["ab", "é", "AB", "한글"])
    else:
        text = chr(rng.randrange(0x21, 0x7F))
    consumed = 1 if shift and text and rng.random() < 0.5 else 0
    action = rng.choice([1, 1, 1, 2, 0])
    composing = 1 if rng.random() < 0.05 else 0
    unshifted = cp if rng.random() < 0.9 else 0
    opts = [rng.randrange(2) for _ in range(6)]
    kitty = 0 if rng.random() < 0.5 else rng.randrange(1, 32)
    th = text.encode().hex() or "-"
    return " ".join(map(str, [action, key, mods, consumed, composing, unshifted, *opts, kitty, th]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("n", nargs="?", type=int, default=300000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    cps = codepoints()
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"cases-{a.seed}-{a.n}.txt"
    lines = [case(rng, cps) for _ in range(a.n)]
    path.write_text("\n".join(lines) + "\n")
    want = subprocess.run([str(HERE / "oracle/ghostty-keys")], stdin=open(path), capture_output=True, text=True, check=True).stdout.splitlines()
    got = subprocess.run([str(HERE / "keys/core-keys"), str(path)], capture_output=True, text=True, check=True).stdout.splitlines()
    bad = [(l, w, g) for l, w, g in zip(lines, want, got) if w != g]
    if len(want) != len(lines) or len(got) != len(lines):
        print(f"FAIL: {len(lines)} cases, oracle answered {len(want)}, core {len(got)}")
        return 1
    for l, w, g in bad[:20]:
        print(f"case  {l}\nghostty {w}\ncore    {g}\n")
    print(f"{'FAIL' if bad else 'ok'}: {len(lines) - len(bad)} of {len(lines)} cases agree (seed {a.seed})")
    return 1 if bad else 0


sys.exit(main())

# DEL in the ground state is printed as a character

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`) and `d8619f1bc`; the code is the
same on `main` at `cf0ab14ae` (2026-10-30). Found by visiterm's
differential fuzzer (`vt-core.md` §VC16). Not to be filed (`README.md`).

## Summary

DEL (0x7F) in the ground state takes a cell: `a DEL b` on an empty screen
leaves `a`, a cell holding U+007F, and `b`, with the cursor at column 3.
xterm and the VT100 ignore DEL wherever it comes (ECMA-48 §8.3.38 gives it
no effect on the presentation), as Ghostty's own parse table does in every
other state (`parse_table.zig`, "anywhere": `0x7F => ignore`).

| input | Ghostty | xterm |
|---|---|---|
| `a \x7f b` | `a␡b`, cursor 3,0 | `ab`, cursor 2,0 |

## Reproduction

```
printf 'a\x7fb' > del.bin
ghostty-dump 10 2 del.bin     # visiterm harness/oracle
```

## Where

`src/terminal/stream.zig`, `handleCodepoint`: a code point is a control
when it has no bit set outside 0x9F, which covers 0x00–0x1F and 0x80–0x9F
and not 0x7F, so DEL falls through to `print`. Before `40a40f848` the test
was `cp <= 0x1F`, which missed it too, and the decoded run
in `nextSliceCapped` has the same mask.

## Fix

Treat 0x7F as ignored in `handleCodepoint` (`if (c == 0x7F) return;` before
the mask test) and end `nextSliceCapped`'s run at it.

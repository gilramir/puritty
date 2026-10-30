# A wide character that wraps over another clears its own spacer head

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC17). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0005-a-wide-cell-keeps-its-own-spacer-head.patch`.

## Summary

A wide character that does not fit at a row's end leaves a spacer head and
is written at the start of the next row. If that row already starts with a
wide character, writing the new one's tail over the old one's head runs
`writeCell`'s clean-up for an overwritten wide character, which turns a
spacer head at the end of the row above into an empty cell, meant for the
old character's. Here it is the new character's own, written a moment
before, so the row above ends in a blank that a reflow keeps.

## Reproduction

With libghostty-vt, 4 columns by 3 rows (visiterm `corpus/replay/wide-keeps-own-spacer-head`):

```
ESC [2;1H f中     row 1: "f", 中 at columns 1-2
ESC [H abc中      中 does not fit at column 3; it wraps onto row 1, over "f中"
resize 3x6
```

| | row 0 | row 1 |
|---|---|---|
| Ghostty | `abc`, wrapped | ` 中`, wrapped |
| expected | `abc`, wrapped | `中` |

## Where

`src/terminal/Terminal.zig`, `writeCell`, the `.wide` case of the old cell:
"If we're near the left edge, a wide char may have wrapped from the
previous row, leaving a spacer_head at the end of that row. Clear it".

## Fix

Skip that clean-up when the cell being written is a spacer tail (`wide !=
.spacer_tail`): the tail of a wide character written at column 0, which a
spacer head above may belong to.

# A reflow leaves the cursor on the spacer head before a wide character

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC17). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0004-reflow-moves-a-pin-with-a-wide-cell-not-its-spacer.patch`.

## Summary

When a reflow puts a wide character at the last column, where it does not
fit, it writes a spacer head there and writes the character again at the
start of the next row. A tracked pin on the character, the cursor or the
saved cursor, is moved before the spacer head is written and is not moved
again, so it ends on the spacer head instead of the character. The next
character printed there overwrites the spacer head and the wide character
stays.

## Reproduction

With libghostty-vt, 10 columns by 4 rows (visiterm `corpus/replay/resize-cursor-wide-respaced`):

```
027abcdef中 CR   中 does not fit at column 9 and wraps; the cursor goes onto it
ESC 7            and is saved there
resize 2x20
ESC 8 y          back to the saved cursor, and a "y"
```

| | the rows of the first line | cursor |
|---|---|---|
| Ghostty | `02` `7a` `bc` `de` `fy` `中` | 1, 4 |
| expected | `02` `7a` `bc` `de` `f` `y` | 1, 5 |

## Where

`src/terminal/PageList.zig`, `reflowRow`: the loop moves every pin at the
source column `x` to `self.x` before `writeCell`, which for a wide cell at
the last column writes a spacer head and returns `.repeat`; on the repeat
the pins no longer match the source row.

## Fix

Do not move the pins on the pass that writes a spacer head (`cells[x].wide
== .wide`, more than one column, `self.x` the last column); the repeat
moves them with the character.

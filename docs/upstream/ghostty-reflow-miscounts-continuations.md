# A reflow counts the rows it joins by a flag DL and DECALN leave behind

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC17). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0003-reflow-counts-rows-joined-to-a-wrapped-row.patch`.

## Summary

`resizeCols` keeps the rows below the cursor through a reflow: it counts the
rows between the cursor and the screen's top that continue a wrapped row,
before and after, and adds blank rows for the difference. It counts them by
each row's `wrap_continuation` flag, but the reflow joins a row to the one
above whenever the row above has `wrap` set. DL, IL and DECALN leave the two
flags disagreeing (the row above still wraps, the row that came in is not a
continuation), so the count is off by one per such row and the screen is
shifted against the cursor.

## Reproduction

With libghostty-vt, 4 columns by 2 rows (visiterm `corpus/replay/resize-dl-continuation`):

```
abcd H          "abcd" wraps; "H" is a continuation
ESC [M          DL: "H"'s row goes, a blank one comes in, not a continuation
efghi           written into it; it wraps, "i" below
resize 1x25
```

| | history | cursor |
|---|---|---|
| Ghostty | 0 | 0, 9 |
| `abcdefghi` fed the same way without the DL | 1 | 0, 8 |
| expected | 1 | 0, 8 |

DECALN does the same (`resize-decaln-continuation`): it rewrites every row
and leaves the wrapped row above the screen wrapping.

## Where

`src/terminal/PageList.zig`, `resizeCols`, the two loops that count
`wrapped` with `if (row.wrap_continuation) wrapped += 1;`.

## Fix

Count a row when the row above it wraps, the test the reflow itself joins
by: `const above = next.up(1) orelse continue; if (above.rowAndCell().row.wrap) wrapped += 1;`.

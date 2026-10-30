# Widening without a reflow keeps a row's wrapped flag or not by its page's capacity

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC17). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0002-widening-without-reflow-unwraps-every-row.patch`.

## Summary

The alternate screen, and the main screen with autowrap off, are resized
without a reflow. Made wider, a row that wrapped keeps its wrapped flag when
the new width fits in the capacity its page was allocated with, and loses it
when it does not: the same screen widened to the same width ends with
different flags depending on how wide it was when its page was made. A row
that no longer reaches the right edge does not wrap, so it should lose the
flag either way.

## Reproduction

With libghostty-vt, 8 columns by 3 rows (visiterm `corpus/replay/resize-alt-widen-in-capacity`):

```
ESC [?47h       the alternate screen, its page made at 8 columns
resize 1x4
7a              "7" wraps to "a"
resize 3x8
```

| | row 0 |
|---|---|
| Ghostty | `7`, wrapped |
| Ghostty, the screen made at 4 columns and widened to 8 (`resize-alt-widen`) | not wrapped |
| expected | `7`, not wrapped |

## Where

`src/terminal/PageList.zig`, `resizeWithoutReflowGrowCols`. Its fast path,
taken when `page.capacity.cols >= cols`, only sets `page.size.cols` and
leaves every row's `wrap`. Its slow path copies each row with
`cloneRowFrom`, which for a partial row keeps the new row's `wrap` and
`wrap_continuation` (both false).

## Fix

In the fast path, before `page.size.cols = cols`, clear `row.wrap` and
`row.wrap_continuation` on every row, as the slow path leaves them.

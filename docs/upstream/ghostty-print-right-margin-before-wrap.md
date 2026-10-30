# A wide character that wraps into the margins keeps the screen's edge as its limit

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC20). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0008-print-recomputes-the-right-margin-after-a-wrap.patch`.

## Summary

`Terminal.print` works out the column it stops at, `right_limit`, once, at
its start: the right margin when the cursor is at or left of it, the
screen's edge when it is past it. A wrap in the same call, the pending one
or the one a wide character makes when it does not fit, moves the cursor to
the left margin, inside the margins, but `right_limit` stays the screen's
edge. A wide character written there then goes past the right margin, and
the cursor is not left waiting to wrap at the margin.

`printSlice`, the run printer, works the limit out again after each wrap
("matching the logic in print()", its comment says), so the same bytes
behave differently by which path prints them: a cell in a style other than
the default makes `printSlice` hand over to `print`.

## Reproduction

With libghostty-vt, 10 columns by 1 row (visiterm `corpus/replay/print-margin-wide-wrap`):

```
ESC [?69h ESC [2;3s   left and right margins, columns 2 and 3
ESC [7m               inverse
ESC [;9H H            "H" in column 9, outside the margins
中                     does not fit at column 10; it wraps to the left margin
n
```

| | row | cursor |
|---|---|---|
| Ghostty | ` 中n    H` | 4, 0 |
| expected | ` n      H` | 2, 0 |
| Ghostty without `ESC [7m` | ` n      H` | 2, 0 |

## Where

`src/terminal/Terminal.zig`, `print`: `const right_limit = ...` before the
pending wrap's `printWrap` and the wide character's.

## Fix

Make `right_limit` a `var` and compute it again after each `printWrap` in
`print`.

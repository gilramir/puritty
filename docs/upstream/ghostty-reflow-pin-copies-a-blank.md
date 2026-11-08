# A reflow keeps a styled blank on the first row, under the viewport pin

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by puritty's differential
fuzzer (`vt-core.md` §VC21). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0010-reflow-a-pin-adds-no-cells.patch`.

## Summary

`ReflowCursor.reflowRow` trims a row that does not wrap to its last cell
that is not empty (`Cell.isEmpty`: no text, narrow), so a row of blanks
with a style but no text is a blank row and its style is dropped. It then
widens the row to cover every tracked pin on it, so that the pins can be
moved, and copies the cells it widened over. The page list's viewport pin
is a tracked pin at the first cell of the first row, so the first row of
the scrollback keeps a blank in a style that any other row loses. What a
reflow writes depends on where an internal pin sits.

Such a blank comes from a wide character printed in one column, which
`print` writes as an empty narrow cell in the cursor's style.

## Reproduction

With libghostty-vt, 1 column by 2 rows (puritty `corpus/replay/reflow-first-row-styled-blank`):

```
ESC [3m 中 ESC [m CR LF   an empty cell in italic: 中 does not fit
a CR LF b CR LF c CR LF
resize 80x2
```

| | the oldest row of the scrollback |
|---|---|
| Ghostty | empty, its first cell italic |
| expected | empty, no style |
| Ghostty with `a CR LF` first, the italic blank second | empty, no style |

## Where

`src/terminal/PageList.zig`, `reflowRow`: `cols_len = @max(cols_len, p.x +
1)` for every tracked pin but the cursor's.

## Fix

Keep the length the row's cells and the cursor give, and write no cell
past it: the pins still make the row be processed and are moved.

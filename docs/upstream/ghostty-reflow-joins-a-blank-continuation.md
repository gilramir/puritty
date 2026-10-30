# Reflow joins a line to the next when the line's last row is blank

**Repository:** `ghostty-org/ghostty`

**Found against:** `d8619f1bc` (libghostty-vt, `tip` of 2026-10-18), and
reproduced against v1.4.0 (`83fb95624`); the code is the same on `main` at
`cf0ab14ae` (2026-10-30). The oracle carries the fix below as
`harness/oracle/patches/0001-reflow-a-blank-continuation-ends-its-line.patch`
(`vt-core.md` §VC17), so `resize-blank-continuation` and
`resize-pages-one-column` no longer diverge.

## Summary

When a soft-wrapped line's last row is blank, a resize that reflows the
screen joins the next line onto it. The blank row is a wrap continuation,
and `ReflowCursor.reflowRow` returns early for a blank row without counting
a line's end when the row is a continuation, so the next row is written on
in the same destination row. Text that was on two lines is shown on one,
and the cursor moves into it.

## Reproduction

With libghostty-vt, a terminal of 4 columns by 5 rows, fed:

```
abcdefgh        the line wraps: "abcd" (wrapped) and "efgh"
ESC [2;1H       to row 2
ESC [2K         erase it: the line's last row is now blank
ESC [3;1H xy    "xy" on row 3, a line of its own
```

then `ghostty_terminal_resize` to 8 columns by 5 rows.

| | row 0 | row 1 | cursor |
|---|---|---|---|
| before | `abcd` (wrapped) | blank | 2, 2 |
| after, Ghostty | `abcdxy` | blank | 6, 0 |
| expected | `abcd` | `xy` | 2, 1 |

A resize to one column makes such rows by itself: a wide character becomes
an empty cell, so `b中` is `b` (wrapped) and a blank row, and widening
again joins every line that had a wide character to the line after it.

## Where

`src/terminal/PageList.zig`, `reflowRow`:

```zig
if (cols_len == 0) {
    // If this blank row was a wrap continuation somehow
    // then we won't need to write it since it should be
    // a part of the previously written row.
    if (!src_row.wrap_continuation) self.new_rows += 1;
    return;
}
```

A row is trimmed to `cols_len == 0` only when it does not wrap itself, so a
blank continuation row is always the end of its line. Counting it,
`self.new_rows += 1` whatever `wrap_continuation` says, starts the next
line on a row of its own; the blank row is still not written.

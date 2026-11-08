# A reflow wraps onto an empty row for a spacer head it does not write

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by puritty's differential
fuzzer (`vt-core.md` §VC18). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0006-reflow-a-spacer-head-does-not-wrap.patch`.

## Summary

A row that wraps because a wide character did not fit ends in a spacer
head. A reflow drops spacer heads (`writeCell` returns `.success` for one
without writing it), but its loop first handles a pending wrap. When the
cells before the spacer head exactly fill a row at the new width, the
spacer head makes the reflow mark that row wrapped and start a new one,
which nothing is written to. If the line ends there, because the next row
is blank, the row before keeps its wrapped flag and an empty row follows
it.

## Reproduction

With libghostty-vt, 10 columns by 5 rows (puritty `corpus/replay/reflow-dropped-head-full-row`):

```
002abcdef中           中 does not fit at column 9: a spacer head there, 中 on row 1
ESC [2;1H ESC [2K     row 1 erased: the line "002abcdef" ends at a blank row
ESC [3;1H x
resize 3x5
```

| | rows |
|---|---|
| Ghostty | `002`, wrapped; `abc`, wrapped; `def`, wrapped; empty; `x` |
| expected | `002`, wrapped; `abc`, wrapped; `def`; `x` |

The same line without the spacer head (`002abcdefgh`, then `h` erased)
reflows as expected.

## Where

`src/terminal/PageList.zig`, `ReflowCursor.reflowRow`: the loop over the
source cells begins with `if (self.pending_wrap) { ... cursorScrollOrNewPage
... }`, before `writeCell` ignores a `.spacer_head`.

## Fix

At the top of the loop, skip a spacer head before the pending wrap is
handled, moving its tracked pins to where the next cell would go:

```zig
if (cells[x].wide == .spacer_head) {
    if (row_has_pins) for (list.tracked_pins.keys()) |p| {
        if (p.node != row.node or p.y != src_y or p.x != x) continue;
        p.node = self.node;
        p.x = self.x;
        p.y = self.y;
    };
    x += 1;
    continue;
}
```

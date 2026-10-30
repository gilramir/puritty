# ED 22 gives the alternate screen a scrollback

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC19). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0007-scroll-clear-keeps-no-history-without-scrollback.patch`.

## Summary

`CSI 22 J` (`scroll_complete`) scrolls the screen up into the scrollback
until its last row that is not empty is gone. `PageList.scrollClear` does it
by growing the page list a row at a time, and nothing checks whether the
screen keeps a scrollback. The alternate screen does not (`no_scrollback`),
and every other way of scrolling it, `cursorDownScroll` among them, erases
the row at the top instead. So after ED 22 on the alternate screen the rows
it scrolled off are history: they are counted in the scrollback and a
viewport can be scrolled up to them.

## Reproduction

With libghostty-vt, 8 columns by 4 rows (visiterm `corpus/replay/ed-22-alt`):

```
ESC [?1049h        the alternate screen
a CR LF b CR LF c  three rows
ESC [2;1H          the cursor on "b"
ESC [22J           scroll them off
x
```

| | history | row 0 |
|---|---|---|
| Ghostty | 3: `a`, `b`, `c` | `x` |
| expected | 0 | `x` |

The same input with `ESC [S` three times in place of `ESC [22J` leaves no
history.

## Where

`src/terminal/Screen.zig`, `scrollClear`, which calls
`PageList.scrollClear` and nothing else of the screen's.

## Fix

After `self.pages.scrollClear()`, erase the history when the screen has
none, as `Screen.resize` already does for the same reason:

```zig
if (self.no_scrollback) self.pages.eraseHistory(null);
```

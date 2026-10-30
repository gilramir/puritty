# DCH after DL leaves a spacer head that DCH without it clears

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by visiterm's differential
fuzzer (`vt-core.md` §VC20). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0009-split-boundary-reads-the-row-above.patch`.

## Summary

`Screen.splitCellBoundary` clears the spacer head at the end of the row
above when a row that starts with a wide character is cut at column 0 or 1,
but only when the row's `wrap_continuation` flag is set. DL and IL clear
both flags of the rows they shift and not the `wrap` of the row above the
region, so a row DL brings up under a row that still wraps is not marked a
continuation, and the spacer head above it stays. The reflow joins a row to
the one above by that row's `wrap` (the subject of
[ghostty-reflow-miscounts-continuations.md](ghostty-reflow-miscounts-continuations.md)),
so the two disagree about whether the rows are one line.

## Reproduction

With libghostty-vt, 5 columns by 4 rows (visiterm `corpus/replay/dch-after-dl-spacer-head`):

```
; SP ESC [1m ��中��中   "; ��" and a spacer head, then 中 "��" and one, then 中
ESC [2;1H ESC [M       DL: the last row comes up under the first, which wraps
ESC [P                 DCH at its start, which cuts its 中
```

| | row 0's bold cells |
|---|---|
| Ghostty | 2–4, the spacer head kept |
| expected | 2–3 |
| Ghostty without the DL (DCH at the start of the row 中 wrapped to) | 2–3 |

## Where

`src/terminal/Screen.zig`, `splitCellBoundary`:
`if ((x == 0 or x == 1) and self.cursor.page_row.wrap_continuation)`.

## Fix

Test the row above's `wrap` instead, as the reflow's join does:
`(self.cursor.page_pin.up(1) orelse ...).rowAndCell().row.wrap`.

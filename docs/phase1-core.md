# Phase 1 · The headless core: a survey

Status: **survey, 2026-10-24, before any of the core is written; Gilbert took
every leaning of §8 the same day, and the stale read is fixed (§9).** Phase 1 of
[`geng-plan.md`](geng-plan.md) §6 starts here, as every phase does, by
measuring before building. What it measured is how the core's state can be
kept in Geng and what each way costs against D902's budget (`geng-plan.md`
§1.3), and whether the rest of phase 1's exit (the oracle, esctest2, the
fuzzer) can be run at all. It found a soundness bug in Geng on the way. As
with geng-lang's surveys, these sections stay as written when the work lands
below them. The Geng side is geng-lang's `m4-visiterm.md` §VA9.

Machine and builds as §1.2: AMD Ryzen 7 8845HS, Linux 6.8, idle. geng-lang
`572b6571`, the compiler fork `a6522467`, `core` `3d676f7`, devbox's clang
21.1.8 at `-O2`, with the passes `harness/run.py`'s `geng-c` target sets. The
inputs are §1.2's thirteen, byte for byte.

---

## 1. What was asked, and what was found

| asked | found | § |
|---|---|---|
| Can a core on immutable rows meet D902? | **No, on any input.** A probe core that does what the inputs ask (resumable parser, styles, wrap, regions, the alt screen, D901's scrollback pages) is 1.2–15× over the budget on twelve of the thirteen inputs and level on the thirteenth (`light_cells`, 40–41 ms against 39). A cell written through a row and the screen costs 34 ns before any parsing, where Alacritty's core takes 42 ns for the CUP and the cell together | 3 |
| Does an in-place screen help, and does Geng have one? | **`Array.Builder` is one, and it halves most inputs**: `cup` 264 → 144 ms, `vte-scrolling` 1,054 → 347. It meets the budget on two inputs. But **it is not sound**: natively and on node a read of a builder after another builder was made from it sees the newer write, and an `Array` that `toArray` handed out changes. It was found here, and it is Geng's own (D753), not stock Gren's | 4 |
| What stands between that and the budget? | A new header allocated for every cell written (half of `ls`'s time), row moves that each allocate (the small scroll regions, 1,250 ms against 179), and a parse that allocates its parameters. Three of `core`'s array builders go an element at a time | 4.3, 5 |
| Can the rest of the exit be run? | **Yes, all three.** libghostty-vt's C API writes bytes, reads every cell and calls back with the replies it writes to the pty; esctest2 is reachable and needs a pty harness; devbox's clang builds a libFuzzer target, and the embed ABI can make `Bytes` from a host buffer | 6 |
| Unicode | `core`'s streaming grapheme segmenter, `Unicode.Grapheme`, exists and is not exposed; `core` has no width tables, which the plan has visiterm generate anyway | 5.3 |

---

## 2. How it was measured

Two probe cores in [`../probes/geng/core/`](../probes/geng/core/), built by
`build.sh` and `build-hot.sh`, and timed by `run.sh` over the inputs, three
runs each, least and most. Each reads its file, then feeds it in 64 KB reads
as Alacritty's pty loop does, between two readings of `Time.monotonic`; the
times leave out start-up and the file read, which `cores.sh`'s include (a few
ms), so the comparison is slightly in the probes' favour.

What both do, from the same parser: a resumable state machine (a CSI, an
escape or a UTF-8 sequence cut by a read is picked up from the state the read
left); a printable run written to its row at once; UTF-8 decoded with each
codepoint's width looked up (a binary search over 480 ranges from Python's
Unicode 15.0 tables, `gen-width.py`, for the cost only); deferred wrap; SGR's
colours and flags interned into a style id through a `Dict`; CUP, the cursor
moves, ED, EL, DECSTBM, SU, SD, IL, DL and DSR 6; the alt screen of
`?1049h`, which keeps no scrollback; and the main screen's scrollback as
D901's pages: 256 rows trimmed of trailing blanks, a ring of 100,000 lines.
What they leave out: graphemes (a zero-width codepoint is dropped), a row's
wrapped flag, tab stops, OSC and DCS beyond skipping them, charsets.

A cell is an `Int`: codepoint in bits 0–20, bit 21 on a wide character's
second cell, style id in bits 22–31. **Ten bits hold 1,024 styles, and
`Int` is 32 bits in Geng on every target** (geng-lang D30), so Ghostty's
8-byte cell with a 16-bit style id is an `Int64`, two arrays, or a style
table per row or page. `dense_cells` makes 156 styles; nothing here
overflowed. The probe does not decide this.

The two probes give the same screen and the same number of scrollback pages
on all thirteen inputs (`checksum`), so they do the same work. Neither checks
the scrollback's content.

`../probes/geng/core-ops/` times each operation alone, 10,000,000 times in a
loop that threads its value.

---

## 3. Immutable rows

`Main.geng`: the screen an `Array` of rows, a row an `Array Int`, as §3.3
proposes. Three ways to write a row (`CELLS`): `copy`, §1's way (the run
built with `Array.initialize`, laid in with `setMany`); `set`, the same but
one cell is one `Array.set`; `chunk`, a row of five arrays of 32 cells.

| ms | budget | `copy` | `set` | `chunk` |
|---|---:|---:|---:|---:|
| `ls` | 195 | 346–367 | 333–348 | 486–497 |
| `cup` | 85 | 368–400 | 264–268 | 238–240 |
| `gitlog` | 239 | 508–553 | 484–519 | 725–758 |
| vte-cursor_motion | 41 | 182–199 | 133–139 | 122–126 |
| vte-dense_cells | 46 | 118–120 | 98–103 | 96–106 |
| vte-light_cells | 39 | 39–42 | 40–41 | 49–52 |
| vte-scrolling | 70 | 1,165–1,188 | 1,054–1,069 | 2,186–2,287 |
| vte-scrolling_bottom_region | 55 | 572–592 | 476–496 | 440–454 |
| vte-scrolling_bottom_small_region | 179 | 559–573 | 604–612 | 814–841 |
| vte-scrolling_fullscreen | 74 | 89–94 | 89–93 | 121–125 |
| vte-scrolling_top_region | 290 | 558–581 | 463–472 | 401–406 |
| vte-scrolling_top_small_region | 176 | 555–561 | 483–488 | 434–445 |
| vte-unicode | 39 | 105–113 | 104–110 | 107–118 |

(Scrollback as `PACK=cells`, below.) Chunked rows help a cell write and cost
every run and every scroll more; no way of writing an immutable row comes near
the budget.

**What the operations cost alone** (`core-ops`, three runs):

| operation | ns |
|---|---:|
| `Array.set` into a 160-cell row | 17.3–17.7 |
| `Array.set` into a 50-row screen | 13.8–14.0 |
| a cell through both, as a grid write is | 34.3–34.4 |
| `Array.Builder.set` into a 160-cell row | 3.7–4.0 |
| a cell through a builder of row builders | 12.1–12.3 |
| a record of 22 fields, one updated | 2.7–2.8 |

So a cell on immutable rows is 34 ns before the CSI that addressed it is
parsed, where Alacritty's core takes 42 ns for both, and a scroll copies the
50-row array and makes a blank row. That is the floor of the representation,
not of the probe.

**Three things first found as costs in the probe and fixed there**, each of
which a real core would meet:

- **`Maybe.withDefault`'s default is evaluated every time.** A blank row as
  the default of a row read made a 160-cell array per cell written: `cup`
  took 1,238 ms until the blank row was a constant.
- **`Array.repeat`, `Array.initialize` and `Array.flatten` build an element
  at a time** through the transient's push, 3–6 ns an element natively; a
  blank row made for each scroll was 58% of `vte-scrolling`'s time.
  `Array.prepend` is one `memcpy`. Joining the screen's slices with it
  instead of `flatten` took the region scrolls from 1,018 to 462 ms. This is
  `core`'s to fix (geng-lang §VA9).
- **Trimming a row scans it from the end**, 160 reads for a one-cell line;
  the builder probe keeps each row's extent instead.

**The scrollback's pages** (`PACK`), measured with `CELLS=set` and the blank
row already a constant, scrollback off and on:

| ms | `ls` off → on | `gitlog` off → on | vte-scrolling off → on |
|---|---:|---:|---:|
| `cells`: a page is its rows' cells in one `Array Int` | 207 → 340 | 271 → 480 | 452 → 1,052 |
| `string`: text through `String.fromArray`, then `Bytes.fromString` | 203 → 718 | 280 → 860 | 455 → 1,364 |
| `seq`: text and runs through `Bytes.Encode.sequence` | 197 → 1,228 | 279 → 1,347 | 492 → 1,417 |

D901's packed pages (text `Bytes`, attribute-run `Bytes`) cost 2.5 µs a line
through `String` and 5 µs through `Bytes.Encode`, since each cell becomes a
`Char` or an encoder. A page of cells costs 0.7 µs a line and is pointer-free
too (a flat array of `Int` is atomic, geng-lang D900), but holds 4 bytes a
cell where the packed text holds about 1. **What would let D901 stand at
`cells`' cost is an encoder from an `Array Int` of codepoints to UTF-8
`Bytes` in one call**, which `core` does not have. The plan's 100,000 lines
at 160 columns are 64 MB a pane as cells untrimmed, less trimmed; packed,
about a quarter.

---

## 4. A screen of builders

### 4.1 The probe

`Hot.geng`: the same parser, styles and scrollback over a screen kept as
`Array.Builder`s, `core`'s public transient: a ring of 50 row builders in a
builder, written in place. A run goes straight into its row, a cell at a time,
with no array made for it. A full-screen scroll hands the top row to the
scrollback with `Builder.toArray` (which gives up the buffer and copies
nothing) and turns the ring; a region touching the top or the bottom edge
turns the ring and moves back only the rows outside it, as Alacritty does;
any other region moves its own rows. Each row's extent is kept beside it.

`Array.Builder`'s documentation says this is sound: "a write to a builder
already passed on, or handed out by `toArray`, copies it first, O(n), so a
non-linear use stays correct". A renderer's snapshot would then be `toArray`
of each row, and a row's next write would copy it once: the copy-on-write a
frame needs, for free.

| ms | budget | immutable (`set`) | builders | builders, no scrollback |
|---|---:|---:|---:|---:|
| `ls` | 195 | 333–348 | 250–256 | 132–133 |
| `cup` | 85 | 264–268 | 144–145 | 144–146 |
| `gitlog` | 239 | 484–519 | 308–312 | 181–185 |
| vte-cursor_motion | 41 | 133–139 | 74–76 | 74–76 |
| vte-dense_cells | 46 | 98–103 | 73–75 | 75–92 |
| vte-light_cells | 39 | 40–41 | **33–35** | 36 |
| vte-scrolling | 70 | 1,054–1,069 | 347–350 | 232–237 |
| vte-scrolling_bottom_region | 55 | 476–496 | 281–283 | 279–284 |
| vte-scrolling_bottom_small_region | 179 | 604–612 | 1,248–1,255 | 1,254–1,258 |
| vte-scrolling_fullscreen | 74 | 89–93 | 83–87 | 38–39 |
| vte-scrolling_top_region | 290 | 463–472 | **284–286** | 286 |
| vte-scrolling_top_small_region | 176 | 483–488 | 1,026–1,035 | 1,019–1,028 |
| vte-unicode | 39 | 104–110 | 76–77 | 76–77 |

Builders meet the budget on two inputs, and without the scrollback on two
more (`ls`, `gitlog`). The scrollback's 100,000 lines are what the budget
asks for, so those two do not count.

### 4.2 It is not sound

A builder's read was not checked by the probe's own design, so it was tested
on its own ([`../probes/geng/builder-stale/case/`](../probes/geng/builder-stale/case/),
a geng-lang corpus case in waiting), on every target `harness/run.py` has:

| read after the newer value exists | expected | native and node | BEAM |
|---|---|---|---|
| `b`, after `set 0 9 b` | `[1,2,3]` | `[9,2,3]` | `[1,2,3]` |
| an array `toArray b` handed out, after `set 1 7 b` | `[1,2,3]` | changed | `[1,2,3]` |
| a top-level builder, after one row's `set` | unchanged | **every later row sees the `9`** | unchanged |

Natively each `tr_set` writes into the buffer in place when the handle it is
given has not escaped, marks that handle escaped and answers a new handle
over the same buffer (`geng_prim.h`, `geng_transient_writable`). A later
*write* through the old handle copies, as documented. A later *read* through
it reads the shared buffer and sees the newer write. Node does the same. The
BEAM's builder is a persistent tree and is right.

Stock Gren's `Array.Builder` has only `pushLast`, `append` and `toArray`, and a
push writes past the end of every older handle's view, so no older handle
can see it: stock is sound. The fork added `set` and `get` (geng-lang D753,
`m3-cost.md` §CO11, 2026-10-16), and a `set` writes inside an older
handle's view. Nothing at run time knows whether the older handle will be
read again, so this is not a missing check but a design hole, and **the
screen of §4.1 cannot be used until it is closed**. geng-lang §VA9 has the
options.

### 4.3 Where the builder probe's time goes

From `perf` on the probe, scrollback off:

- **`ls`: half is `Builder.set`**, a call per cell, each allocating a new
  32-byte handle in the nursery (above). A write of a run, a fill and a
  move of a block, each one handle, are what a builder lacks.
- **The small regions: row moves.** Each moves 25 rows a line, and each move
  allocates the screen's record and a handle: 18 ns a row, 1,250 ms where
  Alacritty takes 179. A block move would make it one call.
- **`cup`**: the CSI's parse, its parameters pushed into an `Array`, and the
  handle per cell.
- **`vte-unicode`: half is the probe's width search**, a binary search where
  a real core has a direct table (Ghostty's 16 bits a codepoint). That one is
  the probe's, not Geng's.

---

## 5. What the core needs from Geng

### 5.1 An in-place buffer that is sound

G4 asked for a mutable buffer "only if phase 1 needs one". It does: no
immutable representation measured reaches the budget, and the measured floor
of one (34 ns a cell, a 50-row copy a scroll) is above it. `Array.Builder`
is already the buffer, public and, used linearly, in place; what it lacks is
soundness on a stale read (§4.2) and the operations a grid needs in one call
(§4.3). So G4 becomes: make the builder sound, and give it those operations.

### 5.2 Cheaper array builders

`Array.repeat`, `initialize` and `flatten` at 3–6 ns an element, where a fill
or a `memcpy` costs a fraction of a nanosecond, and an encoder from code points
to UTF-8 `Bytes` (§3) are `core` work with no language question in them.

### 5.3 Unicode

The plan says `core` has `Unicode.Grapheme`, a streaming UAX #29 state
machine. It does, but `core` exposes only `Unicode` (its version) and the
`String` functions over whole strings (`graphemes`, `foldlGraphemes`), and a
terminal needs the state machine itself, one codepoint at a time across
reads (S§5.3, "streaming must re-open the previous cell"). Either `core`
exposes `Unicode.Grapheme`, or visiterm carries a second copy of its 256
lines and its 10,000 lines of tables, kept in step with `core`'s Unicode
version by hand. Width tables are not in `core`, and the plan already has
visiterm generate them (§5's `unicode-width`), since the width model is a
pane's policy.

---

## 6. The rest of phase 1's exit, checked

- **The differential oracle.** libghostty-vt at the vendored `d8619f1bc` has a
  C API (`include/ghostty/vt/terminal.h`, `screen.h`, `grid_ref.h`):
  `ghostty_terminal_vt_write` feeds bytes, `ghostty_terminal_grid_ref` and
  `ghostty_grid_ref_cell`/`_style`/`_graphemes` read every cell, and
  `GHOSTTY_TERMINAL_OPT_WRITE_PTY` is a callback with the replies it would
  write to the pty. So a C driver can feed both cores the same bytes and
  compare grids and replies. Not built.
- **esctest2** (`github.com/ThomasDickey/esctest2`) is reachable from here.
  It runs inside the terminal it tests, writing sequences and reading
  replies, so headless it needs a pty: esctest2 on the slave, a harness on
  the master feeding the core and writing its replies back. The core as a
  `runtime = "host"` library called from Python (geng-lang `m3-embed.md`
  §EM14) is the shortest such harness. Not built.
- **Fuzzing.** devbox's clang 21.1.8 links `-fsanitize=fuzzer`. The embed ABI
  has `bytes_from` among its layer-0 functions, so a host can hand an export
  `Bytes`; whether it copies more than it must is G9's question, not yet
  measured.
- **Refinement types for every index** (plan §7): not tried. The probes index
  with `Array.get` and a default, which is what refinements would replace.

---

## 7. What was not measured

- Graphemes, the wrapped flag, reflow, OSC, DCS and replies other than DSR 6.
  Each costs more, so the probes are a ceiling for their representations,
  as §1's grid probe was.
- A renderer's snapshot, and so the copy each row's first write after a frame
  costs. At 60 frames a second and 50 rows it is about 3,000 row copies a
  second, nothing beside the writes.
- `Int64` cells (§2), and per-page style tables.
- The probes' memory. G7's numbers stand for the scrollback; the builder
  screen holds the same rows.
- Whether the remaining gap is reachable at all in Geng: §4.3 names the
  costs, and only removing them will say.

---

## 8. For Gilbert

1. **The builder's stale read** (§4.2). This is a soundness bug in Geng and
   is fixed whatever visiterm does; the question is how. geng-lang §VA9.2
   lays out the options. *Leaning:* the old handle becomes a record of what
   the write replaced (a version tree, Baker's persistent arrays), so the
   newest handle stays in place at the cost of one more store a write and an
   older one reads back through the record.
2. **G4 is the builder** (§5.1): no new type, but `Array.Builder` made sound
   and given a write of a run, a fill and a block move, each one call.
   *Leaning:* yes, in geng-lang, before the core is written on it.
3. **D902 stays the bar** (§1.3). Builders are still 1.1–7× over on eleven
   inputs; §4.3 says where, and it is Geng work, which is the plan's second
   goal. *Leaning:* keep it, and measure again after 1 and 2 rather than
   relax it now; daily use (the first goal) is not what it protects, since a
   shell's pty is the floor for `cat` either way (§1.2).
4. **Expose `Unicode.Grapheme` from `core`** (§5.3). *Leaning:* yes: one copy
   of UAX #29, on the version `core` pins.
5. **The cell is wider than `Int`** (§2): Ghostty's cell needs 37 bits or
   more, and Geng's `Int` is 32. *Leaning:* decide in the core's design, by
   measurement, between `Int64` cells and a style table per page; nothing in
   Geng asks for a change.

**The order, if the leanings are taken:** the stale read fixed in geng-lang
(with the corpus case); the builder's three operations and `core`'s faster
`repeat`, `initialize`, `flatten` and code-point encoder; `Unicode.Grapheme`
exposed; this survey's builder probe measured again; then the core itself,
designed with the oracle and esctest2 harnesses from the start.

---

## 9. Gilbert's answers, and the stale read fixed (2026-10-24)

Gilbert took every leaning of §8: geng-lang D903 (the stale read, by the
record in the old handle), D904 (G4 is the builder, with a run write, a fill
and a block move), D905 (`core`'s faster `repeat`, `initialize`, `flatten`
and a code-point encoder), D906 (`Unicode.Grapheme` exposed), D907 (D902
stays the bar); and question 5, the cell's width, is decided in the core's
design by measurement.

D903 is built (geng-lang `m4-visiterm.md` §VA10). `builder-stale`'s case is
in geng-lang's corpus as `accept/builder-stale`, with seven rows more, and
passes on every fork target. It was not one more store a write: an older
handle's record keeps what follows it alive, which a generational,
conservative collector turns into promoting every handle a loop makes unless
the chains are bounded, and the bounds and the larger handle cost the builder
screen this, on the three inputs whose files were kept (5 runs, least and
most):

| ms | budget | builders before D903, measured again | builders, D903 |
|---|---:|---:|---:|
| `ls` | 195 | 260–275 | 323–340 |
| `cup` | 85 | 144–153 | 183–189 |
| `gitlog` | 239 | 317–337 | 376–394 |

The ten vtebench inputs were not kept and are not measured again here; D907's
measurement after D904 and D905 takes all thirteen.

---

## 10. On the second machine (2026-10-24)

Development moved to a Ryzen 9 9950X the same day, and `geng-plan.md` §1.4
measures the reference terminals and D902's budget again there. The two
probe cores, built on geng-lang `d027d333` and the fork at `d0f892f2` (D903
built), `run.sh` over all thirteen inputs, five runs, least and most; the
immutable one with `CELLS=set PACK=cells`, as §3's tables (its default,
`PACK=string`, is slower on the scrolling inputs: `ls` 552–556):

| ms | budget here | immutable (`set`) | builders, D903 | builders ÷ budget |
|---|---:|---:|---:|---:|
| `ls` | 124 | 264–272 | 203–205 | 1.7 |
| `cup` | 56 | 189–213 | 129–135 | 2.4 |
| `gitlog` | 132 | 371–380 | 248–252 | 1.9 |
| vte-cursor_motion | 28 | 92–94 | 62–64 | 2.3 |
| vte-dense_cells | 28 | 74–76 | 61–63 | 2.3 |
| vte-light_cells | 24 | 38–41 | 36–37 | 1.5 |
| vte-scrolling | 42 | 762–774 | 254–256 | 6.1 |
| vte-scrolling_bottom_region | 37 | 329–335 | 195–197 | 5.3 |
| vte-scrolling_bottom_small_region | 132 | 411–418 | 858–870 | 6.6 |
| vte-scrolling_fullscreen | 45 | 71–74 | 62–67 | 1.5 |
| vte-scrolling_top_region | 223 | 318–323 | **194–200** | 0.9 |
| vte-scrolling_top_small_region | 125 | 326–331 | 866–875 | 7.0 |
| vte-unicode | 25 | 75–77 | 59 | 2.4 |

- **Builders meet the budget on one input here**, `scrolling_top_region`.
  `light_cells`, which they met on the first machine before D903, is 1.5×
  over: Alacritty's core gained more from the machine (39 → 24 ms) than the
  probe did.
- **On the three inputs §9 measured, the builder screen's distance from the
  budget is about what it was**: `ls` 1.7× (1.7× on the first machine with
  D903), `cup` 2.4× (2.2×), `gitlog` 1.9× (1.6×). The machine does not change
  what D904 and D905 have to win.
- The immutable screen is 1.4–18× over, as §3 found.

`core-ops` (three runs, 10,000,000 each; D903 built, where §3's table was
before it):

| operation | ns |
|---|---:|
| `Array.set` into a 160-cell row | 10.0–12.4 |
| `Array.set` into a 50-row screen | 7.6–7.7 |
| a cell through both, as a grid write is | 20.5 |
| `Array.Builder.set` into a 160-cell row | 3.3–3.4 |
| a cell through a builder of row builders | 7.9–8.0 |
| a record of 22 fields, one updated | 2.0–2.1 |

A cell on immutable rows is 20 ns here before any parsing; Alacritty's core
takes 28 ns for the CUP and the cell together.

**G7's pauses** (`gcpause/run.py`, the ring, three runs each), the longest
pause in the `cat`, with the heap at the run's longest full collection:

| | longest pause | heap | peak RSS | the `cat` |
|---|---:|---:|---:|---:|
| packed rows, 1 pane | 4.8–5.1 ms | 84 MB | 99–100 MB | 4.88–4.92 s |
| packed rows, 4 panes | 12.1–12.3 | 188 | 212 | 4.98–5.03 |
| **joined pages, 4 panes** | **1.3–1.9** | **68** | **80** | 4.83–4.84 |
| **joined pages, 8 panes** | **1.7** | **124** | **137–138** | 4.81–4.84 |

D901's joined pages are under half the 4 ms goal at four and at eight panes,
where the first machine gave 3.0–3.7 and 3.0. Marking is still serial
(`GC_set_markers_count(1)`), so this is the machine's speed alone. The heaps
are larger than §VA7.7's (packed, 4 panes, 188 MB where 148; pages 68 where
60), which was not looked into.


---

## 11. D904 and D905 built (2026-10-24)

geng-lang `m4-visiterm.md` §VA11. `Array.Builder` has `setMany`, `fill` and
`copyWithin`, each one call and one builder, `append` is one call, and
`Array.repeat`, `initialize` and `flatten` each make their array in one call;
`Bytes.fromCodePoints` encodes an `Array Int` of code points as UTF-8, or
answers the index of the first that is not a scalar value (D909). A run
written in place keeps the run it replaced, so an older builder still reads
what it held.

What it means for the core, from geng-lang's `bench/builder-runs` (natively,
ns an element, the element-at-a-time way first): an erase in line is
2.0 → 0.18, a 25-row region scrolled 3.2 → 0.5 a row, a blank row made with
`repeat` 3.3 → 0.11, and a 160-cell line packed through `fromCodePoints`
10.4 → 0.86 a cell, where §3's `string` pages went through `String`.

What it does not change: **a printable run**. Made with `Array.initialize`
and written with one `setMany`, a run of 40 cells costs 2.3 ns a cell
against 2.1 for a `set` a cell, and a run of 8 is slower, since making each
cell through `initialize`'s function costs most of what the `set` did. The
probe's text should stay a `set` a cell; geng-lang registers a write from a
function as what would take the call out.

D907 is next: the builder probe rewritten on `fill`, `copyWithin` and
`repeat`, and the scrollback's pages on `fromCodePoints`, measured on all
thirteen inputs against this machine's budget.

---

## 12. D906 built and D907's measurement (2026-10-25)

geng-lang `m4-visiterm.md` §VA13 and §VA14.

**`Unicode.Grapheme` is exposed** (D906). Its `State` is one opaque `Int`
(geng-lang D912): `step : Char -> State -> State` and `isBoundary : State ->
Bool`, the rules UAX #29's at the version `core` pins. A step allocates
nothing, and a printable ASCII character is answered without a table:
natively 1.6 ns a character where it was 7.1, a Hangul syllable 4.3, a Thai
character 14 (a binary search of `core`'s table, registered in geng-lang).
The core carries the state across reads and asks `isBoundary` to attach a
character to the cell before it.

**The builder probe on D904's writes.** `probes/geng/core/src/Hot.geng`:
an erase in line is one `Builder.fill`; the rows a scroll moves are one
`copyWithin` of the screen and one of the extents for each stretch of the
ring the move covers, at most three, and one row is two `set`s; an erase in
display is a `fill` for each stretch; `PACK=points` joins a page's text with
`Bytes.fromCodePoints`. Printable runs stay a `set` a cell (§11). Every
input's checksum, pages and styles are what they were. Five runs, least and
most, against §10:

| ms | budget | §10 (D903) | rewritten (D903–D906) | ÷ budget | joined pages |
|---|---:|---:|---:|---:|---:|
| `ls` | 124 | 203–205 | 155–157 | 1.3 | 422–435 |
| `cup` | 56 | 129–135 | 133–158 | 2.4 | 131–136 |
| `gitlog` | 132 | 248–252 | 201–209 | 1.5 | 462–468 |
| vte-cursor_motion | 28 | 62–64 | 63–66 | 2.3 | 64–66 |
| vte-dense_cells | 28 | 61–63 | 59–61 | 2.1 | 59–63 |
| vte-light_cells | 24 | 36–37 | 38–39 | 1.6 | 37–39 |
| vte-scrolling | 42 | 254–256 | 264–266 | 6.3 | 417–428 |
| vte-scrolling_bottom_region | 37 | 195–197 | 206–211 | 5.6 | 207–208 |
| vte-scrolling_bottom_small_region | 132 | 858–870 | **247–254** | 1.9 | 247–249 |
| vte-scrolling_fullscreen | 45 | 62–67 | 45–48 | 1.0 | 136–143 |
| vte-scrolling_top_region | 223 | 194–200 | 197–204 | **0.9** | 197–203 |
| vte-scrolling_top_small_region | 125 | 866–875 | **333–343** | 2.7 | 331–338 |
| vte-unicode | 25 | 59 | 59–62 | 2.4 | 59–61 |

- The two small-region scrolls are 2–2.7× over where they were 7×; `ls` and
  `gitlog` lost a quarter, from `core`'s one-call `flatten` and `repeat`
  with the probe unchanged.
- It meets the budget on `top_region` and is level on `fullscreen`; eleven
  inputs are 1.3–6.3× over. **D902 stays the bar** (D907).
- **`ls`'s time is the text**: 39% is `Builder.set` a cell, each a 48-byte
  handle. Joined pages add 270 ms to `ls`, most of it `core`'s `keepIf` and
  `map` writing an element at a time and `attrRuns`' `Bytes.Encode`; a
  page's text through `fromCodePoints` is not where it goes.

geng-lang §VA14.1 puts the next step to Gilbert: survey the compiler
proving an older builder dead, so a write needs no handle or record (the
largest cost on every input over the budget), and start the core on the
builder screen meanwhile.

---

## 13. The builder probe on `update`, `swap` and `moveWithin` (2026-10-25)

geng-lang `m4-unique.md` §UQ14 (D913's first step).

geng-lang decided (D913) that the compiler will prove a builder's older
handle dead, so that a write is a store, and that `Array.Builder` first gets
an exchange, since a row taken out of the screen with `get` while the screen
still holds it has two owners and no proof can take its writes. `core` now
has `update i f b`, `swap i x b` and `moveWithin at from to vacated b`.

`probes/geng/core/src/Hot.geng` is rewritten on them: a row is written
through `update`; `decodeRun` takes its row out with `swap` and puts it back
with `set`; a run of rows moves with `moveWithin`, a one-row move with
`swap` and `set`, and the row a scroll turns to the bottom is taken with
`swap`. The placeholder, `holeRow`, is one empty row nothing writes. Every
input's checksum, pages and styles are what they were. Five runs, least and
most, ms, the same `core` and fork for both:

| ms | budget | before (§12's source) | on the exchange |
|---|---:|---:|---:|
| `ls` | 124 | 154–160 | 155–158 |
| `cup` | 56 | 131–152 | 129–132 |
| `gitlog` | 132 | 204–208 | 203–206 |
| vte-cursor_motion | 28 | 63–64 | 62–66 |
| vte-dense_cells | 28 | 60–62 | 61–63 |
| vte-light_cells | 24 | 37–39 | 37–40 |
| vte-scrolling | 42 | 263–267 | 264–270 |
| vte-scrolling_bottom_region | 37 | 204–217 | 221–226 |
| vte-scrolling_bottom_small_region | 132 | 245–251 | 264–269 |
| vte-scrolling_fullscreen | 45 | 47–49 | 45–48 |
| vte-scrolling_top_region | 223 | 198–209 | 231–236 |
| vte-scrolling_top_small_region | 125 | 333–337 | 389–391 |
| vte-unicode | 25 | 59–61 | 59–60 |

- Level on the text inputs: `update` is the `get` and `set` the old shape
  made.
- 7–16% slower on the four region scrolls: `swap` and `set`, and
  `moveWithin`'s copy and fill, are two writes where there was one, each a
  D903 handle. `top_region` is now just over the budget (231 against 223).
- The probe stays on the exchange: it is the shape the proof is built for,
  and the proof makes both writes stores. geng-lang's next piece is a survey
  of ownership in Geng's types (D918), then the proof.

## 14. The screen's ring holds recent scrollback (2026-10-26)

geng-lang's `m4-visiterm.md` §VA15 found where the builder probe's time
goes, and §VA16 builds Gilbert's answers (D978–D983). In the probe:

- **The ring holds recent scrollback as rows** (D978), as Alacritty's grid
  does: 563 row builders on the main screen, the screen's 50, up to 512 of
  scrollback and a free one. A scroll moves `base` and clears the free row
  in place; when the ring is full the oldest 256 rows of scrollback are
  copied out trimmed and joined into a page (D901), and their builders are
  written again. The alternate screen is a ring of 51 and keeps none.
- **A CSI's parameters are one `Builder`, and a width below U+20000 is two
  bits of a table** `gen-width.py` writes as a literal (D979).
- **The ASCII print calls `Builder.update` itself**, so that the compiler
  makes the row's write one call with no closure (D982).

Five runs, least and most, ms, every checksum, page count and style count
as it was; "before" is §13's probe on today's runtime, measured in the same
run (geng-lang §VA16.1 has every step between):

| ms | budget | before | now |
|---|---:|---:|---:|
| `ls` | 124 | 82–86 | 67–70 |
| `cup` | 56 | 91–93 | 72–74 |
| `gitlog` | 132 | 140–142 | 110–113 |
| vte-cursor_motion | 28 | 45–47 | 35–37 |
| vte-dense_cells | 28 | 54–57 | 34–36 |
| vte-light_cells | 24 | 12–14 | 12–13 |
| vte-scrolling | 42 | 237–239 | 143–145 |
| vte-scrolling_bottom_region | 37 | 191–195 | 160–163 |
| vte-scrolling_bottom_small_region | 132 | 189–192 | 158–160 |
| vte-scrolling_fullscreen | 45 | 22–24 | 20–22 |
| vte-scrolling_top_region | 223 | 200–202 | 167–170 |
| vte-scrolling_top_small_region | 125 | 277–278 | 237–239 |
| vte-unicode | 25 | 46–47 | 15–16 |

- Six inputs of thirteen meet the budget, `gitlog` and `vte-unicode` new
  among them. The scrolls are still 1.2–4.4× over.
- G7's pauses with joined pages are level or better: on one screen with
  100,000 lines, the longest full collection 0.75–0.85 ms.
- Writing the `Term` and `Screen` updates in place would be 10–24% more;
  one update of 55, `feed`'s `csi` call, reads its old record after it.
  geng-lang has asked Gilbert whether to build it (§VA16.6).

## 15. Records in place, tail calls as jumps, and regions turned (2026-10-27)

geng-lang's `m4-visiterm.md` §VA17 to §VA20 build what §14 asked and what
measuring after it found. The compiler writes 80 of the probe's 84 updates
of `Term` and `Screen` in place (D984–D988), with nothing in the probe
changed; the parser's functions call one another with `musttail` jumps
under clang (D989); and in the probe:

- **A row is cleared only up to its extent** (D990), the column past which
  it is already blank, as Alacritty clears a row to its occupied width.
- **A region scroll on the alternate screen reuses the row it drops** (D990)
  instead of a new blank one, which the next print copied.
- **A region whose rows are one stretch of the ring turns them with
  `Builder.rotate`** (D991, new in core), one call for the rows and one for
  their extents, the row that leaves coming in at the other end; a region
  that wraps the ring's end keeps the moves.

Five runs, least and most, ms, every checksum as it was; each column is
geng-lang's own measurement on its day:

| ms | budget | §14 | in place (§VA17) | `musttail` (§VA18) | now (§VA20) |
|---|---:|---:|---:|---:|---:|
| `ls` | 124 | 67–70 | 60–62 | 57–60 | 55–58 |
| `cup` | 56 | 72–74 | 60–63 | 45–48 | 45–57 |
| `gitlog` | 132 | 110–113 | 90–94 | 82–86 | 87–90 |
| vte-cursor_motion | 28 | 35–37 | 29–31 | 22–23 | 21–22 |
| vte-dense_cells | 28 | 34–36 | 25–26 | 17–18 | 17–18 |
| vte-light_cells | 24 | 12–13 | 9–11 | 9–10 | 9–10 |
| vte-scrolling | 42 | 143–145 | 109–110 | 100–102 | 90–91 |
| vte-scrolling_bottom_region | 37 | 160–163 | 114–117 | 105–106 | 90–92 |
| vte-scrolling_bottom_small_region | 132 | 158–160 | 115–120 | 111–112 | 86–88 |
| vte-scrolling_fullscreen | 45 | 20–22 | 19–20 | 18–20 | 18–20 |
| vte-scrolling_top_region | 223 | 167–170 | 112–115 | 103–107 | 89–91 |
| vte-scrolling_top_small_region | 125 | 237–239 | 190–191 | 180–185 | 85–88 |
| vte-unicode | 25 | 15–16 | 13–13 | 12–14 | 12–13 |

- Eleven inputs of thirteen meet the budget. `cup`'s 57 is one slow run of
  five; the other four are 45–48.
- `vte-scrolling` (2.1×) and `vte-scrolling_bottom_region` (2.4×) are left.
  Their scroll's own work is small: what is left is the print, and the
  checks the runtime makes around each `Builder` call, which geng-lang takes
  next, the print's closure per run first (D992).

## 16. A page written straight into its builders (2026-10-27)

geng-lang's `m4-visiterm.md` §VA21 priced a line of `vte-scrolling` by kind
of cost and measured four changes; Gilbert took all four (§VA22 there). Two
are the probe's:

- **`clearRowAt` binds the row's extent by a `let`** before handing `update`
  `Builder.fill 0 ext blank`. The compiler then made the `fill` a direct
  call, where it made a closure and applied it; since geng-lang D994 it does
  so without the `let` too, which the probe keeps as the clearer form.
- **A page of the `cells` packing is written straight into two builders**:
  `pageOut` appends each row's slice to one builder of cells and pushes its
  extent onto one of lengths, where it built a builder of rows and
  flattened it. The other packings are as they were.

The probe's checksum reads the screen, not the pages, so the second was
checked against a build whose checksum folds every page in too: the same on
every input. With geng-lang's D993 (a pointer written in place over the same
pointer is not written), five runs, ms:

| ms | budget | §15 | now |
|---|---:|---:|---:|
| vte-scrolling | 42 | 90–91 | 79–81 |
| vte-scrolling_bottom_region | 37 | 90–92 | 85–89 |
| vte-scrolling_bottom_small_region | 132 | 86–88 | 80–82 |
| vte-scrolling_top_region | 223 | 89–91 | 84–87 |
| vte-scrolling_top_small_region | 125 | 85–88 | 79–80 |

The other eight are as in §15, but for `light_cells` (10–13) and
`fullscreen` (20–23), which are code layout: aligned, the same cycles as
before (§VA22.1 there). `vte-scrolling` is still 1.9× and `bottom_region`
2.3×; the scrollback's paging is about 270 of `scrolling`'s 956
instructions a line, and geng-lang measures it next (§VA23).

## 17. A page read by slot and appended by run (2026-10-27)

geng-lang's `m4-visiterm.md` §VA23 measured the paging, and Gilbert took
§VA23.3's leanings (§VA24 there, D995 and D996):

- **A page of the `cells` packing is read by physical slot.** `pageOut`
  takes the page's rows as one or two runs of the ring's slots, from the
  oldest row's slot to the end of the ring and from its start, and their
  lengths as one slice of the extents for each run. It turned each logical
  row into its slot before. `flatRows` is gone.
- **Each row is appended with `Builder.appendSlice`**, new in core, which
  copies a run of one builder onto another with no `Array` between them,
  where `Builder.append (Builder.slice 0 ext row)` made one per row.

Every input's checksum is the same, and so is every page's, checked as §16's
were. `vte-scrolling` 2,550 → 2,227 M instructions, 78–79 → 68–70 ms;
`gitlog` 84–85 → 80–82, `ls` 55–60 → 53–56. Two inputs are over the budget,
`vte-scrolling` 1.6× and `bottom_region` 2.3×.

## 18. The probe's own logic (2026-10-28)

geng-lang's `m4-visiterm.md` §VA27 surveyed the probe's own logic with
`geng profile` and `bench/compare`, and Gilbert took §VA27.4's leanings:

- **A row's extent is the row's last cell**, past its `cols`, and the
  extents builder beside the rows is gone. A write of a run reads and
  writes one builder, not two, and a scroll that moves rows moves their
  extents with them.
- **The cells past a row's extent are never read.** A row is made blank by
  setting its extent to 0; a write that starts past the extent blanks the
  cells between first (`reach`), and `checksum` reads a row to its extent
  and blanks after it.
- **A line feed that does not page builds no record**, where `regionUp`
  built `{ screen, back }` for both branches.
- **The scrollback's pages are a `Builder`**, each page set in place,
  where an `Array` of 390 was copied at every page.
- **A page reads each row once**, for its cells and its extent
  (`physRows`).

Every input's checksum is the same, and so is every page's.
`vte-scrolling` 1,969 → 1,482 M instructions (738 → 556 a line), 63–67 →
51–53 ms; `bottom_region` 2,582 → 1,607 M, 80–81 → 47–49 ms; `gitlog`
83–87 → 72–74. The two over budget are now 1.2× and 1.3×.

## 19. A run's first byte read once (2026-10-28)

geng-lang's `m4-visiterm.md` §VA29, P8d, which Gilbert took: `ground`
hands `printAscii` the printable byte it read, `asciiEnd` starts after it,
and `asciiRow` writes it. `vte-scrolling` 556 → 535 instructions a line,
the region scrolls 3.5% fewer; the inputs of long runs 1.4–4.5% more,
level in time. Every checksum and page is the same.

## 20. A line feed's kind decided once (2026-10-29)

geng-lang's `m4-visiterm-scrolls.md` H2, which Gilbert took (its
`m4-visiterm.md` §VA41): `Term` keeps a `scroll` kind, set by `withScroll`
where the region, the screen or the scrollback change. A line feed at the
region's bottom goes straight to `feedFull` (the whole main screen,
scrollback kept) or `feedRegion` (a region, none kept), and only the other
kinds take `regionUp` and `screenUp`'s chain of tests. `vte-scrolling`
530 → 464 instructions a line, 46–48 → 42–44 ms against 42;
`bottom_region` 524 → 461, 41–43 → 36–38 against 37; every region scroll
10–12% fewer instructions. Every checksum and page is the same.

## 21. A region keeps its own turn (2026-10-29)

geng-lang's `m4-visiterm-scrolls.md` H1 (its `m4-visiterm.md` §VA42). A
`Screen` keeps its region (`top`, `height`) and a `turn`. `phys` maps a
row inside the region through the turn, and the rest of the ring through
`slot`, which is `phys` as it was. A line feed at the bottom of a region
(`feedRegion`) counts the turn on by one and blanks the row that left,
where it turned 49 row pointers. `settle` rotates the region's rows into
place, with the turn back to 0, before anything that works on runs of
slots (`screenUp`, `turnRegion`, `rotate`, `moveRows`, `blankRows`,
`regionDown`) and wherever the region or the screen changes
(`withScroll`). Every region scroll has 18–19% fewer instructions, and
`bottom_region` takes 30–32 ms against 37. `vte-scrolling` has 13 more
instructions a line, for the turn's test in `phys`, and is level in time.
Every checksum and page is the same, and so is the output on 800 random
mixes of every sequence the probe handles.

## 22. The screen's cells in one builder (2026-10-29)

geng-lang's `m4-visiterm-scrolls.md` H4, surveyed in its `m4-visiterm.md`
§VA43 and taken in §VA44. The ring is one `Builder Int` of `cols + 1` cells
a slot, a row's cells and then its extent. Every row function takes the
row's offset, so a print is a store into the one builder, and a moved row
is a `copyWithin` of its cells. The row builders' helpers are gone, and so
are D913's hole rows, which geng-lang D1016 now refuses, as it refuses the
old erase's `fill` of one row into many slots.

All thirteen of D902's inputs meet the budget: `vte-scrolling` 39–42 ms
against 42, the region scrolls 28–30. Inputs of long runs pay 6
instructions a byte, and an edit that moves rows costs 0.2 µs. Every
checksum and page matches H4 as surveyed. The survey also found two bugs
in the old screen, an erase that shared one row and a hole that became a
row, which this one cannot have.

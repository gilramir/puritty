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


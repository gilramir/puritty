# The headless core: `vt/`

Status: **begun 2026-10-29.** Phase 1 of [`geng-plan.md`](geng-plan.md) §6,
built on what [`phase1-core.md`](phase1-core.md) measured: the builder
probe's screen (`probes/geng/core/src/Hot.geng`, its §14–§23) made into a
package with a whole parser, modes and replies around it, and the gate it is
held to from its first day. This document says what the code does; its
decisions are numbered V1, V2, … and referenced by number afterwards, as
geng-lang's are. Geng-side work it finds is geng-lang's, under
`m4-visiterm.md` (§VA49 is the first).

Machine as `phase1-core.md` §10: Ryzen 9 9950X, Linux, devbox's clang
21.1.8. geng-lang `15637bf7`, the fork `ba3b9a30` (D1019, §VC8), `core` `0f90c92`.

---

## VC1. What is built

| piece | where | what it is |
|---|---|---|
| the core | `vt/` (`github.com/gilramir/visiterm-vt`, `runtime = "any"`) | `Vt`: `new`, `feed`, `takeReplies`, `dump`; `Vt.Width`, generated |
| the core's dump | `harness/dump/` (`core-dump COLS ROWS FILE [CHUNK]`) | feeds a file to a `Vt.Term`, a read of `CHUNK` bytes at a time, and prints §VC3 |
| the oracle | `harness/oracle/` (`ghostty-dump COLS ROWS FILE`) | the same for libghostty-vt at the vendored `d8619f1bc`, through its C API |
| the gate | `harness/replay.py`, `corpus/replay/` | §VC4 |
| the timing | `harness/bench/` (`core-bench FILE`) | §VC7 |
| esctest2 | `harness/esctest.py`, `harness/esctest/` (`core-pty`, `ghostty-pty`), `corpus/esctest/` | §VC10 |
| the fuzzer | `harness/fuzz.py`, `harness/fuzz/` (`vt-fuzz`, `vt-min`), `corpus/fuzz/runs.tsv` | §VC11 |

`Vt`'s interface, as it stands:

```gren
new : Config -> Term                       -- { cols, rows, scrollback, checksums }
feed : Bytes -> (moved t : Term) -> Term   -- one read's bytes
takeReplies : (moved t : Term) -> { term : Term, replies : Array Bytes }
dump : Term -> String                      -- §VC3
```

`feed` is the whole of what happens to a terminal: no clock, no file, no
callback. What the program asked to be answered (DSR, DA, DECRQM, DECRQSS,
XTVERSION) waits in the term until `takeReplies` takes it.

What it handles today: printing with deferred wrap, the wrapped flag, wide
characters (a spacer after one, a spacer head where one did not fit at the
row's end, half of one overwritten), marks joined to the cell before as a
grapheme cluster, insert mode, autowrap off, DEC special graphics through
G0/G1 and SO/SI; C0 controls; CUU to CBT, CUP/HVP with origin mode, HPA, HPR,
VPA, VPR, CNL, CPL; ED 0–3, EL, ECH, ICH, DCH, IL, DL, SU, SD, IND, NEL, RI,
DECSTBM, REP, DECALN, tab stops (HTS, TBC, CHT, CBT); SGR with every
attribute Ghostty keeps, 256 and RGB colours with either separator, the
underline's kind and colour; erases and scrolls in the background colour;
DECSC/DECRC and SCOSC/SCORC per screen; modes 4, 20, ?6, ?7, ?25, ?47,
?1047, ?1048, ?1049 (the alternate screen kept once made, as xterm and
Ghostty keep it), and every other private mode recorded for DECRQM, KAM and
SRM recorded and the ANSI modes xterm lacks answered as permanently reset;
XTSAVE and XTRESTORE; DECSCUSR; RIS and DECSTR; OSC 0 and 2 (the title);
DECRQSS for `m`, `r` and ` q`; DSR 5 and 6, DECXCPR, DA1 and DECID, DA2, DA3,
XTVERSION, XTWINOPS 18 (the size in cells), DECRQCRA when the embedder asks
for it (V5); the main screen's scrollback in D901's pages (§VC6).

What it does not handle yet is §VC9.

---

## VC2. The cell (V1)

`phase1-core.md` §8's fifth question, which Gilbert left to the core's design
by measurement: Ghostty's cell carries a 16-bit style id, and a 32-bit `Int`
with a 21-bit code point and width bits has room for ten.

**Measured.** `probes/geng/core/src/Hot64.geng` is `Hot.geng` with each cell
an `Int64`, its style id moved to bits 32–47, and nothing else changed;
`build-hot64.sh` builds it. Both give the same checksum, pages and styles on
all thirteen inputs. Five runs each, least and most, ms, and instructions
(millions, one run):

| input | budget | `Int` cells | `Int64` cells | instructions `Int` | `Int64` | |
|---|---:|---:|---:|---:|---:|---:|
| `cup` | 56 | 41–49 | 40–42 | 1,299 | 1,322 | +1.8% |
| `gitlog` | 132 | 75–80 | 79–82 | 2,641 | 2,644 | +0.1% |
| `ls` | 124 | 63–64 | 64–65 | 2,331 | 2,340 | +0.4% |
| vte-cursor_motion | 28 | 18–19 | 19–20 | 676 | 687 | +1.6% |
| vte-dense_cells | 28 | 14–15 | 15–16 | 547 | 552 | +0.9% |
| vte-light_cells | 24 | 9 | 10 | 366 | 367 | +0.3% |
| vte-scrolling | 42 | 36–39 | 37–39 | 1,332 | 1,382 | +3.8% |
| vte-scrolling_bottom_region | 37 | 22–23 | 23–24 | 878 | 916 | +4.3% |
| vte-scrolling_bottom_small_region | 132 | 22–24 | 24–25 | 877 | 914 | +4.2% |
| vte-scrolling_fullscreen | 45 | 19–20 | 20–22 | 752 | 753 | +0.1% |
| vte-scrolling_top_region | 223 | 22–23 | 23–24 | 878 | 916 | +4.3% |
| vte-scrolling_top_small_region | 125 | 22–24 | 23–24 | 877 | 914 | +4.2% |
| vte-unicode | 25 | 10–11 | 10–12 | 441 | 453 | +2.7% |

An `Int64` is an `int64_t` natively (geng-lang `m3-native.md`'s shape `I8`),
so a `Builder Int64` is 8 bytes an item in one buffer, as Ghostty's page is.
The wider cell costs 0–4.3% more instructions, most on the scrolls (the
rows moved are twice the bytes), and is level in time on every input; all
thirteen stay under the budget. The other way, a 32-bit cell and a second
builder of style ids beside it, writes two buffers at every cell and moves
two at every scroll, and was not built. Pages are D901's either way, since
a page holds text and style runs, not cells.

**V1 · A cell is an `Int64`**: bits 0–20 the code point, or with bit 23 set
the id of a grapheme cluster; bits 21–22 the width state (0 narrow, 1 wide,
2 the spacer after a wide character, 3 a spacer head); bits 32–47 the style
id; the rest unused. 0 is an empty cell in the default style. A row's meta
slot, past its `cols` cells, is its extent (bits 0–15) and its wrapped flag
(bit 16).

The probe's own build had been missing a pass. `build-hot.sh` set
`GENG_CORE_PASSES` without `inplace`, which geng-lang's measurements of the
probe have had since D984 (`bench/compare/visiterm.toml`); without it
`vte-scrolling` is 710 instructions a line instead of 499 and twice the time.
Both build scripts now name it, and the table above is with it.

---

## VC3. The screen dump (V2)

**V2 · The core and the oracle are compared as text**, each printing the
terminal in one form, so that a difference is a line of a diff and a case's
expectation is a file a person can read and write. `Vt.dump` and
`ghostty-dump` print it:

```
screen 10x4 main                  cols x rows, and `main` or `alt`
cursor 3,1 wrap                   column,row from 0; ` wrap` if a wrap is pending, ` hidden` if ?25 is reset
history 2                         rows of scrollback, then each, oldest first
h0 |abc|
h1+ |defg|                        `+`: the row wrapped into the next
0 |a中b|                          the screen's rows, every one
  0-1 fg=1 bold                   the row's cells by style: first-last and the style, default runs left out
1 ||
reply \x1b[2;7R                   each reply, oldest first; bytes 0x21–0x7E but `\` as themselves
```

A row's text is each cell to the last that has text: an empty cell before it
is a space, a wide character's spacer and a spacer head are nothing, and a
cluster is its code points. A written space is text and an empty cell is
not, so `a ` and `a` differ, as they do in both cores. A style is its
colours (`fg`, `bg`, `ulc`: a palette index, or `#rrggbb`) and then `bold`,
`faint`, `italic`, `ul=` and the underline's kind, `blink`, `inverse`,
`invisible`, `strike`, `overline`. Ghostty keeps a cell erased in a
background colour as a cell of that colour and no style; the oracle prints
it as the style `bg=`, which is what the core keeps.

---

## VC4. The gate

`./harness/replay.py` runs every case of `corpus/replay/` through the core
and the oracle. A case is a directory with `case.txt`: `size COLSxROWS`,
then the bytes, written with escapes (`\e`, `\r`, `\n`, `\xHH`, …; a newline
in the file is not a byte), and `expected.txt`, its dump. The core must
print `expected.txt` fed the whole file in one read **and fed it a byte a
read**, so that every state the parser can be cut in is left and resumed;
the oracle must print it too, or the case has a `divergence.txt` saying why
not and `ghostty.txt` pins what Ghostty prints instead.

```
./harness/oracle/build.sh && ./harness/dump/build.sh
./harness/replay.py                  # 108 of 108 cases pass
./harness/replay.py -f wide --side core
./harness/replay.py --update         # expected.txt from the core: read the diff
./harness/replay.py --update --side ghostty   # a new case's expected.txt from Ghostty
```

**108 cases, every one passing on both sides, none divergent** (2026-10-29;
98 when the core was begun, nine more with §VC10, one with §VC11).
Each case's `expected.txt` was written by Ghostty first and the core brought
to it. Corrupting an expectation fails all three runs, which was checked.

What Ghostty taught along the way, each now a case: a backspace with a wrap
pending moves left and clears it (`bs-at-wrap`); a tab keeps a pending wrap
(`ht-at-wrap`); SU on the main screen with the whole screen as the region
sends its rows to the scrollback (`scroll-su-sd`); DCH in a background
colour fills only the columns it vacates at the row's end, and the cells
past the old extent move in empty (`bce-ech-ich-dch`); a CSI of more than 24
parameters is ignored whole (`csi-many-params`); DECRQSS's SGR lists
overline before blink and writes the 16 colours as `3x`/`9x`
(`decrqss-sgr`); a mark with no cell before it is dropped
(`combining-at-start`), and one after a pending wrap joins the last column
(`combining-after-wrap`).

---

## VC5. The parser

Paul Williams' DEC state machine. The term carries its state between reads:
`ps` (ground, escape, escape intermediate, CSI, CSI ignore, a UTF-8
sequence, OSC, DCS, and SOS/PM/APC), a CSI's parameters, colons, private
marker, intermediate and phase, a string's bytes, and a UTF-8 sequence's
code point so far and the range its next byte must fall in.

- **The ground state's fast path** is the probe's: a run of printable ASCII
  is found and written to its row at once, when GL is ASCII, autowrap is on
  and insert is off. Anything else is a code point at a time through
  `printPoint`, which knows every mode.
- **UTF-8** is decoded with the well-formed ranges of Unicode §3.9 table
  3-7, and a sequence that breaks is U+FFFD and its next byte read again,
  the maximal subpart (`utf8-invalid`). A C1 control encoded as UTF-8 is
  not printed (`c1-ignored-utf8`).
- **C0 controls are executed inside an escape, a CSI or an escape's
  intermediates**; CAN and SUB end the sequence; ESC starts a new one.
- **Strings**: OSC ends at BEL or ST; DCS at ST, and its bytes above 0x7F
  are payload (S§5.1). ESC inside either ends it and starts an escape, so
  `ESC \` is ST.

**V3 · Bounds.** Every buffer the program controls is bounded (S§5.1): a
CSI's parameters at 24, each at 65,535, a longer CSI ignored whole as
Ghostty does; an OSC's or DCS's kept bytes at 4,096 (the rest dropped; tmux
control mode in phase 4 will want 1 MiB for its DCS, S§5.1); a grapheme
cluster at 32 code points, a mark past them dropped.

**V4 · The replies are Ghostty's for now**: DA1 `?62;22c`, DA2 `>1;0;0c`,
DA3 `!|00000000`, DECRQM's answers, DECRQSS's forms; XTVERSION answers
`visiterm`. What visiterm says it is is a product question for phase 3,
when programs start asking it; until then matching the oracle keeps the
gate whole.

---

## VC6. Scrollback pages

The main screen's ring holds the screen, up to `2 × 256` rows of
scrollback and a free row, as the probe's does. When it is full, the
oldest 256 rows of scrollback are packed into a page (geng-lang D901), and
the pages are a ring of `scrollback / 256` (rounded up). A page is three
`Bytes`, made with `Bytes.fromUInt8s` from three `Builder UInt8`:

- **text**: each row's cells as UTF-8, a cluster as its code points, an
  empty cell or a spacer head as a 0 byte, a wide character's spacer as
  nothing;
- **heads**: for each row a header, two bytes low first: its extent in bits
  0–13, bit 14 set when every cell is in the default style, bit 15 when the
  row wrapped;
- **runs**: unless a row's bit 14 is set, its style runs: each a style id
  in two bytes, with bit 15 set when a count of cells (two bytes) follows;
  the last run has no count and reaches the extent. So a style id has 15
  bits and the table holds 32,768 (`styleMax`).

Read back (`dump`'s `unpackPage`), a code point of width 0 joins the cell
before it, a wide one takes its spacer, and a 0 byte is an empty cell. So a
page gives back every cell but a spacer head's kind, which comes back as an
empty cell (§VC9). `scrollback-pages` and `scrollback-pages-styled` page
700 and 600 lines and hold every row of history to Ghostty's.

---

## VC7. Throughput

`core-bench` is the probe's timing for the core: 160 × 50, 100,000 lines of
scrollback, 64 KB reads, the time between two readings of the clock. Five
runs, least and most, ms, against the budget of `geng-plan.md` §1.4; the
probe (§VC2's `Int64` build) measured again in the same run; and the core
as first built, then after the changes below. Instructions are millions,
one run, without the dump (`core-bench FILE` makes none; `dump` adds one
after the clock is read, which a count of instructions would see).

| input | budget | probe | core, first | **core, now** | instr. probe | instr. core |
|---|---:|---:|---:|---:|---:|---:|
| `cup` | 56 | 40–41 | 71–72 | **49–56** | 1,322 | 1,602 |
| `gitlog` | 132 | 79–80 | 138–143 | **107–112** | 2,644 | 3,364 |
| `ls` | 124 | 63–66 | 95–98 | **85–89** | 2,340 | 3,017 |
| vte-cursor_motion | 28 | 18–20 | 35–37 | **23–24** | 687 | 834 |
| vte-dense_cells | 28 | 14–16 | 43 | **19–20** | 552 | 730 |
| vte-light_cells | 24 | 9–10 | 9–10 | **7–9** | 367 | 333 |
| vte-scrolling | 42 | 37–41 | 124–125 | **39–40** | 1,382 | 1,405 |
| vte-scrolling_bottom_region | 37 | 23–24 | 100–103 | **23–25** | 916 | 942 |
| vte-scrolling_bottom_small_region | 132 | 24 | 99–104 | **23–29** | 914 | 940 |
| vte-scrolling_fullscreen | 45 | 20–22 | 27–28 | **27–28** | 753 | 961 |
| vte-scrolling_top_region | 223 | 23–25 | 99–103 | **23–24** | 916 | 942 |
| vte-scrolling_top_small_region | 125 | 23–25 | 99–103 | **24–26** | 914 | 940 |
| vte-unicode | 25 | 10–12 | 85–86 | **13–15** | 453 | 505 |

**All thirteen inputs meet the budget**, `vte-scrolling` at 39–40 ms
against 42; `cup`'s slowest run of five is level with its budget, 56. **A first run after the machine sits idle is the clock's, not
the core's.** `cup`'s was 62–63 ms where the rest were 49–55 against 56. Two
minutes idle, then three runs of each (`perf stat`): the slow run takes the
same cycles as the warm ones (274.2 M against 273.0–275.3 M, the
instructions and page faults the same too) at about 4.0 GHz where they run
at 5.1, since this machine's power plan clocks the CPU down when it is idle
(`amd-pstate-epp`, `powersave`). The probe run first does it too (52, 47,
42 ms, against 40–41 warm, 219 M cycles each), and it had not shown it here
only because it ran after the core had woken the CPU; three seconds of a
busy loop first take it away (51, 52, 51). `probes/geng/core/run.sh` now
makes one untimed run before it times any, and every figure in this section
is a warm one. The
core is 0.9–1.3× the probe's instructions on every input; what it does that the probe does not
(the size and the width as fields, the wrapped flag, the wide-character
checks, the erase cell, a 40-field `Term` where the probe's had 21) is what
is left. The changes, in the order made, each with every case of the
corpus passing:

1. **A local function made every update of the term a copy.**
   `privateState` had a `let`'s helper `of`; geng-lang's `inplace` pass
   treats a local function as a value, and handing it a field of `t` made
   `t` possibly kept, which, as the pass's facts are a fixed point over the
   whole program, made the term shared along every path of the parser. Made
   a function of its own: 17 updates of an affine record in place → 173
   (`GENG_INPLACE_REPORT`).
2. **A run of UTF-8 is decoded into the row at once** (`printUnicode`,
   `decodeRun`), as the probe's was, one function looping on itself; a
   control, a cut or broken sequence, a C1 control, a mark, a wide
   character that does not fit and a pending wrap stop it and take the
   general path. `vte-unicode` 1,211 → 518 M instructions.
3. **A cluster of two code points is found by an `Int64`** of both, where
   every cluster was found by its code points written as text.
4. **SGR is a loop over five `Int`s and a `when` on the parameter**, where
   each parameter copied the `Attrs` record; an extended colour answers one
   `Int`, not a record.
5. **A style is found through a cache of 512 slots** (`styleCache`, a
   `Builder Int64` in the term) from its key to its pen's id and its erase
   cell's, where each SGR made two dictionary lookups. A style never leaves
   the table, so a slot never goes stale. `vte-dense_cells` 1,079 → 746.
6. **`eraseDisplay` blanks its rows before its line**: it read `t`'s
   fields after handing `t` to `eraseLine`, which made `blankRows`', and so
   `clearRow`'s, screen shared for every caller: a copy of the screen
   record at every line feed.
7. **A page's row header is two bytes and a row in the default style writes
   no runs** (§VC6), where every row wrote a flags byte, its extent and
   four bytes a run. `vte-scrolling` 1,992 → 1,787; `ls` and `gitlog` 4%
   more, for the two writes back into a styled row's header.
8. **A page's row headers are a builder of their own**, written after the
   row, so no header is written twice: a page is three `Bytes`, text,
   headers and runs (§VC6). `vte-scrolling` 1,787 → 1,655. Paging now costs
   fewer instructions a line than the probe's did.
9. **Whether the ASCII and UTF-8 runs may be taken is one field**,
   `plain`, set wherever GL, G0, autowrap or insert changes (`withPlain`),
   where each run tested all four. 1,655 → 1,515.
10. **CR and LF are taken in `ground` itself**, as the probe took them,
    not through `execute`'s call and its tests. 1,515 → 1,405, 38–40 ms.

## VC8. What it found in Geng

**`Core.Pass.InPlace` lifted a read out of a closure past the `let` that
bound what it read** (geng-lang D1019, `m4-visiterm.md` §VA49). `dump`'s
`historyRows` maps a closure over the scrollback's rows that calls `phys
t.screen y`; inlined, that is one `let` whose first binding is `t.screen`
and whose second reads `turn` from the first. The pass's hoist (D986), which
makes such a read when the closure is made, gathered the second binding's
read without dropping the `let`'s own names, and the C backend refused the
program: "the local `$n54` is not in scope". Fixed in the fork, with
`corpus/accept/inplace-hoist-let`.

**The parser's speed turned on clang inlining `dispatch`** into its only
caller (geng-lang `m4-visiterm.md` §VA50, registered there): §VC10's
additions took it past LLVM's bonus for a function called once, and every
CSI became an out-of-line call. Nothing in Geng was changed; §VC10 says
what the core does about it.

---

## VC9. What is not built yet

Phase 1's exit (`geng-plan.md` §6) and S§5's list, against today:

- **Throughput** (§VC7): every input meets the budget. Phase 1's exit
  measures it again once the rest is built.
- **esctest2** runs headless (§VC10): 297 of 567 tests pass, Ghostty 383.
  Every one of the 92 that Ghostty passes and the core does not needs a
  feature below. **The fuzzer** runs (§VC11); its differential against
  libghostty-vt is not built.
- **Left and right margins** (DECLRMM, ?69, and DECSLRM): not started, and
  52 of those 92 tests. Every scroll, insert, delete and wrap takes them;
  the scroll paths that §VC7 measured would carry the test.
- **Protected cells** (DECSCA, SPA/EPA, DECSED, DECSEL): 12 tests.
  **Reverse wraparound** (?45, ?1045): 10. **XTWINOPS's resize and
  maximize** wait on resize: 9. **OSC 4, 10, 11 and 104, the colours
  queried and reset**: 8.
- **DECRQM over-claims**: a private mode the core only records is reported
  set or reset, so ?45 and ?69 answer as if they worked, and a program that
  asks before it uses left and right margins would be misled. esctest's
  DECRQM tests for DECHEBM, DECNRCM, DECPEX and DECPFF and two DECSCL tests
  pass on the core and not on Ghostty for that reason, and are not passes
  of the features. To be narrowed to the modes the core has once the list
  above is decided.
- **Graphemes by UAX #29**: today a mark of width 0 joins the cell before
  it, which is the legacy model. `core`'s `Unicode.Grapheme` (D906) is what
  mode 2027 and the per-pane width model (S§5.3) will use, with the
  previous cell re-opened across reads. VS16, ZWJ sequences and emoji
  modifiers are not joined yet.
- **Widths** are Python's Unicode 15.0 tables (`vt/gen-width.py`), not the
  UCD 17.0 `core` pins; `core` carries no UCD files to generate from.
- **Resize and reflow** (S§5.4): not started; reflow is to have its tests
  first.
- **OSC 7, 8, 52, 133, 9 and 777, DCS for tmux and XTGETTCAP, mode 2026's
  synchronized output, the title stack, the kitty keyboard stack, the mouse
  modes' state, hyperlinks**: not started; every private mode is recorded
  and answered by DECRQM, which is all most of them need in the core.
- **The style and cluster tables never shrink.** A style id is handed out
  for each new SGR combination and kept; at 32,768 a new style is the
  default (`styleMax`), which bounds memory but draws wrong. Ghostty counts
  each page's styles and frees them. The same holds for clusters at 2²¹.
  To be decided with the renderer, which reads them.
- **A spacer head read back from a page** is an empty cell (§VC6).
- **The oracle is libghostty-vt at `d8619f1bc`** (a `tip` build of
  2026-10-18), 191 commits before v1.4.0 (2026-10-27). Most of v1.4.0's
  terminal changes are Kitty graphics, snapshots, tmux layouts and FreeBSD,
  which no case reaches; two parser fixes may move screens no case holds
  yet: a continuation restarts at a C1 sequence introducer, and a cancelled
  or aborted APC is discarded. `vt_write_until_ground` became
  `vt_write_until`, which `ghostty-dump` does not call. **v1.4.0 needs Zig
  0.17**, and visiterm's devbox has 0.16 from the nixpkgs commit
  geng-lang's clang comes from, so the upgrade is that pin moved, the
  library rebuilt, and `replay.py` run, each case it moves either the core
  fixed or a `divergence.txt`; a commit of its own, not mixed with the
  core's work. Best taken with the fuzzer, which makes such sequences.
  Registered 2026-10-29.
- **Refinement types for every index** (plan §7): not tried; the core reads
  with `Builder.get` and a default.

---

## VC10. esctest2 (V5, V6)

[esctest2](https://github.com/ThomasDickey/esctest2) runs in the terminal it
tests: it writes sequences and reads the replies, and it reads the screen
back through DECRQCRA, a checksum of a rectangle, one cell at a time.
Headless, it needs a pty. `harness/esctest.py` opens one, runs esctest on the
slave, and runs the terminal as a program with the master for its standard
input and output, so nothing relays between them:

| side | program | what it is |
|---|---|---|
| the core | `harness/esctest/core-pty` (`build.sh`) | `Os.File.read` of standard input a piece at a time as it comes, `Vt.feed`, `Vt.takeReplies` written to standard output |
| the oracle | `harness/esctest/ghostty-pty` (`build-oracle.sh`) | the same through libghostty-vt's C API: `vt_write`, the `WRITE_PTY`, `SIZE` and `RESIZE_WINDOW` callbacks |

esctest is the commit Ghostty's own runner pins
(`vendor/ghostty/test/esctest/build.zig.zon`), `2798f12` of 2026-09-13,
cloned into `vendor/esctest2`, and is passed what that runner passes it:
`--expected-terminal=xterm --xterm-checksum=411 --xterm-reverse-wrap=411
--timeout=0.2`. Each side's passing tests are recorded in
`corpus/esctest/core.txt` and `ghostty.txt`.

```
git clone https://github.com/ThomasDickey/esctest2 vendor/esctest2
git -C vendor/esctest2 checkout 2798f12149a19c3295e9b4853ab2da4b2eff1b2b
./harness/esctest/build.sh && ./harness/esctest/build-oracle.sh
./harness/esctest.py                    # both sides; fails if a recorded pass is lost
./harness/esctest.py --diff             # what one side passes and the other does not
./harness/esctest.py --side core -- --include=DECSTBM
./harness/esctest.py --update           # record what passes now
```

**V5 · DECRQCRA answers only when the embedder asks** (`Config.checksums`),
as libghostty-vt's does (`GHOSTTY_TERMINAL_OPT_XT_CHECKSUM_REPORT`): a
program can checksum the screen a cell at a time and so read everything on
it, other programs' output among it. `core-pty` and `core-dump` turn it on,
`core-bench` does not. The checksum is xterm's `checksumExtension: 23`, the
one esctest expects of xterm 334 and later and the one Ghostty's runner
sets: each cell's code point to 16 bits, an empty cell a space, a wide
character's spacer nothing, no attributes, summed to 16 bits and not
negated; in origin mode the rectangle is from the region's top. XTCHECKSUM,
which changes the calculation, is not taken.

**V6 · The two sides answer as the same terminal.** Ghostty's runner has
libghostty-vt answer DA as a VT520; `ghostty-pty` leaves the library's own
VT220, which is what the core answers (V4), so that what differs between
the two runs is the two cores. esctest's DECXCPR test expects the page only
of a VT400 or later, so Ghostty, which sends it as the core does, fails the
test here and passes it under its own runner; that one test is the
difference between 383 and the 384 the first run had.

**The record is the gate**: a test recorded in `core.txt` that fails fails
the run, and one newly passing is listed for `--update`. Adding a test the
core fails to `core.txt` was checked to fail the run. Three runs gave the
same 297; the 0.2 s read timeout is long beside the core's replies, which
take microseconds.

### What the first run found

| | core | Ghostty |
|---|---:|---:|
| the first run | 0 | 384 |
| CSI 18 t and DECRQCRA | 269 | 384 |
| the rest of this section | **297** | **383** |

Of 567 tests, Ghostty fails 142 and esctest records 42 of those as xterm's
known bugs; the core fails 249, 21 recorded so. Every test failed on the
core at first: esctest's reset before each test asks the screen's size
(CSI 18 t), which the core did not answer, and checks every screen through
DECRQCRA. With both, 269. Then each test Ghostty passes and the core did
not, by the features its source uses:

- **The alternate screen was made afresh each time it was entered**, where
  xterm and Ghostty keep it once made, its text and its saved cursor, and
  clear it only on leaving with ?1047 and entering with ?1049. Kept now
  (`alt-kept`, `alt-1047-clears`), and ?1048, which saves and restores the
  cursor, done (`save-cursor-1048`). 8 tests.
- **DECRQM answered 0 for every ANSI mode but IRM and LNM.** KAM and SRM are
  recorded now, SRM set by default, and the twelve ANSI modes xterm and
  Ghostty do not have answer 4, permanently reset (`decrqm-ansi`). 14.
- **DECID** (ESC Z) answers as DA1 (`decid`); **DECRQSS ` q`** answers
  DECSCUSR's style, kept as Ghostty keeps it, a shape and mode 12's blink,
  a steady block after DECSTR (`decrqss-decscusr`); **XTSAVE and
  XTRESTORE** keep and set back a private mode, one never kept set back to
  its state in a new terminal, as Ghostty's are (`xtsave`). 4.
- `decrqcra` and `size-report` hold the two reports to Ghostty.

The other 92 are §VC9's: left and right margins, protected cells, reverse
wraparound, resize, the colour queries.

### What it cost, and what that found

The additions are off the hot path, yet `cup` went from 49–54 ms to 56–58
against its budget of 56, and `vte-cursor_motion` from 23–24 to 26–28
against 28, on 3% more instructions: 15 more cycles for each of `cup`'s two
million CSIs, an IPC of 5.5 where it was 5.9. Each change alone was free
(the three new `Term` fields; DECRQCRA's branch; CSI 18 t; DECSCUSR;
XTSAVE), and all of them together were not: **`dispatch` had sat just
under clang's limit for inlining a function into its only caller**, and
past it every CSI is an out-of-line call from `csi`'s loop. clang gives a
static function called from one place a bonus of 15,000 against its cost
and inlines it whatever its size below that; the whole of `dispatch` cost
about 19,000 once over. A smaller part split off does not help, since clang
inlines that part back into its own one caller first: `dispatchPlain` with
a `dispatchRare`, and then `dispatch` with a `dispatchRest`, were each
inlined back together and left out of `csi` (the remarks of
`-Rpass-missed=inline`). Raising clang's threshold for a cold call site
changed nothing.

What holds: `dispatch` takes SGR and CUP itself, which are most of what a
program sends, and hands every other sequence to `dispatchRest`, **called
from two places** (the plain branch and the marked one), so that clang
never treats it as called once and keeps it out of line, while `dispatch`
is small and inlined. Instructions are level or 0.3–0.6% fewer on every
input, and the times are §VC7's (five runs each, least and most, ms):

| input | budget | before | first | **now** |
|---|---:|---:|---:|---:|
| `cup` | 56 | 49–50 | 56–58 | **49–51** |
| `gitlog` | 132 | 107–109 | 109–112 | **109–111** |
| vte-cursor_motion | 28 | 23–25 | 26–28 | **24–25** |
| vte-dense_cells | 28 | 19–20 | 21–23 | **19–20** |

and the other nine level with §VC7's. This is geng-lang's to know: a Geng
program's speed on its hottest path turned on a clang heuristic that the
program cannot see and Geng has no word for (`m4-visiterm.md` §VA50).

---

## VC11. The fuzzer (V7)

G9 of `geng-plan.md`: the core built as a `runtime = "host"` library and
driven by libFuzzer. `harness/fuzz/` is the library, one module, `Fuzz`,
exposing `dump : Int -> Int -> Int -> Bytes -> String`, which feeds a term
of so many columns and rows the bytes, a read of so many at a time or all in
one, and answers `Vt.dump`. `build.sh` builds it with the passes the core is
measured with and `--debug-info`, then compiles the C it kept again with
libFuzzer's coverage into `vt-fuzz` (with `fuzz.c`) and `vt-min` (with
`min.c`): `geng make` takes no C flags of a library's host, so the second
step of its build (geng-lang `m3-embed.md` D629) is repeated with them.

A host could not hand the library `Bytes`: the embed ABI's `bytes_from` was
specified and never built. geng-lang built it for this (D1020, `m3-embed.md`
§EM22, `m4-visiterm.md` §VA51).

**V7 · The fuzzer's findings are what the core itself can tell.** An
input's first three bytes choose the columns (1 to 132), the rows (1 to 50)
and a read's length (1 to 16); the rest is fed. It is a finding when a call
answers other than `GENG_OK`, a Geng crash among them (an index, a pattern
not matched, the stack, memory), or **when the dump fed the input in one
read differs from the dump fed it a read at a time**, which leaves the
parser and the fast paths in every state they can be cut in, as the replay
corpus's byte-a-read run does for its cases. libFuzzer adds a time limit
(10 s an input) and a memory limit (2 GB). A differential against
libghostty-vt is not one of them yet: on bytes chosen at random it would
diverge on every sequence §VC9 lists, and needs those built, or inputs
drawn from what the core has.

```
./harness/fuzz/build.sh
./harness/fuzz.py --minutes 10            # one job; a row of corpus/fuzz/runs.tsv
./harness/fuzz.py --hours 2 --jobs 8
./harness/fuzz.py --show FILE             # both dumps of an input
./harness/fuzz/vt-min FILE OUT            # the smallest input that is the same finding
```

The corpus grows in `.harness-work/fuzz/corpus` from run to run, seeded each
time from every replay case at its size (or the nearest the tables have),
read whole and seven bytes at a time. `vt.dict` gives libFuzzer the
sequences the core parses. Inputs are 4 KB at most: without a limit they
grew to 40 KB and each job ran 290 inputs a second where it had run 3,800.

### What it found

**A stale spacer past a row's extent.** In its first minute, at 20×2, a dump
fed a byte at a time had a bold blank cell where the whole read had an empty
one. `vt-min` cut the 4,540 bytes to 527: bold, `中`, 514 line feeds, `CR J
LF 中`. After 514 the ring of rows has wrapped, and the new bottom row is a
slot whose old cells are still there past its extent, which is all that
clearing a row resets: the bold `中` and its spacer. `printPoint`, which a
character decoded across reads goes through, made the cells from the extent
to the cursor empty and then asked `splitWide` whether the cell at the
cursor was a spacer, which past the extent it only seemed to be; it blanked
the cell before it in the old style. `printUnicode`, the whole read's path,
calls the two the other way round, which hid it. ED 2 clears rows the same
way, so 19 bytes show it at 6×1, and with autowrap off an ASCII character
takes `printPoint` too and both reads are wrong. Ghostty leaves the cell
empty. **Fixed:** `splitWide` takes a spacer only inside the extent
(`wide-stale-spacer`, which fails without the fix). §VC7's times are level.


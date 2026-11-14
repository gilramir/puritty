# The headless core: `vt/`

*The ownership mark is written `taken` here; it was `moved` until 2026-11-07
(geng-lang Dnene18), and commit messages before then use that word. §VC20's
and §VC22's `moved` is something else, `Page.moved`, a page a reflow kept.*

Status: **begun 2026-10-29.** Phase 1 of [`geng-plan.md`](geng-plan.md) §6,
built on what [`phase1-core.md`](phase1-core.md) measured: the builder
probe's screen (`probes/geng/core/src/Hot.geng`, its §14–§23) made into a
package with a whole parser, modes and replies around it, and the gate it is
held to from its first day. This document says what the code does; its
decisions are numbered V1, V2, … and referenced by number afterwards, as
geng-lang's are. Geng-side work it finds is geng-lang's, under
`m4-puritty.md` (§VA49 is the first).

Machine as `phase1-core.md` §10: Ryzen 9 9950X, Linux, devbox's clang
21.1.8. geng-lang `15637bf7`, the fork `ba3b9a30` (D1019, §VC8), `core` `0f90c92`.

---

## VC1. What is built

| piece | where | what it is |
|---|---|---|
| the core | `vt/` (`github.com/gilramir/puritty-vt`, `runtime = "any"`) | `Vt`: `new`, `feed`, `takeReplies`, `resize`, `dump`; under it, not exposed, `Vt.Cell`, `Vt.Style`, `Vt.Term`, `Vt.Screen`, `Vt.Pages`, `Vt.Recut` (§VC31), `Vt.Resize`, `Vt.Dump` (§VC23) and `Vt.Width`, generated |
| the core's dump | `harness/dump/` (`core-dump COLS ROWS FILE [CHUNK [RESIZES]]`) | feeds a file to a `Vt.Term`, a read of `CHUNK` bytes at a time, resized where `RESIZES` says (§VC14), and prints §VC3 |
| the oracle | `harness/oracle/` (`ghostty-dump COLS ROWS FILE [RESIZES]`) | the same for libghostty-vt at the vendored v1.4.0 (`83fb95624`; `d8619f1bc` before §VC15) with `patches/` applied (V12, §VC17), through its C API; `widths`, its width table (V13) |
| the gate | `harness/replay.py`, `corpus/replay/` | §VC4 |
| the timing | `harness/bench/` (`core-bench FILE [dump \| resize COLS ROWS \| drag N COLS ROWS]`) | §VC7, §VC14, §VC30 |
| esctest2 | `harness/esctest.py`, `harness/esctest/` (`core-pty`, `ghostty-pty`), `corpus/esctest/` | §VC10 |
| the fuzzer | `harness/fuzz.py`, `harness/fuzz/` (`vt-fuzz`, `vt-min`), `corpus/fuzz/runs.tsv` | §VC11 |
| the differential fuzzer | `harness/fuzz.py --diff`, `harness/fuzz/` (`vt-diff`, `vt-diff-min`), `corpus/fuzz/diff-runs.tsv` | §VC16 to §VC22 |

`Vt`'s interface, as it stands:

```gren
new : Config -> Term                       -- { cols, rows, scrollbackBytes, pageRows, checksums, cellWidth, cellHeight }
defaultPageRows : Int                      -- 1,024, Config.pageRows unless a test wants smaller (V33)
feed : Bytes -> (taken t : Term) -> Term   -- one read's bytes
takeReplies : (taken t : Term) -> { term : Term, replies : Array Bytes }
resize : Int -> Int -> (taken t : Term) -> Term   -- cols rows, §VC14
dump : Term -> String                      -- §VC3
historyBound : Term -> Int                 -- for the differential fuzzer, §VC17
historyReached : Int -> Term -> Bool       -- the same, sticky and inside a read, §VC25, §VC32
scrollbackBytesFor : { cols : Int, rows : Int } -> Int   -- the bytes for rows of a width, §VC32
recutHolds : Int -> Term -> Bool           -- for the fuzzer: the pages' recut is the reflow, §VC31
keyOptions : Term -> Keys.Options          -- what Vt.Keys.encode reads (phase3-input.md V47)
mouseModes : Term -> { tracking : Int, format : Int }   -- what Vt.Mouse.encode reads (phase3-select.md §12)
```

Beside it, exposed for the window: `Vt.View` (the renderer's Geng side),
`Vt.Keys` and `Vt.KeyTables` (Ghostty's key encoder, V47), `Vt.Mouse`
(Ghostty's mouse encoder, `phase3-select.md` §12) and `Vt.Charset` with
`Vt.EucKrIndex` (V49).

`feed` is the whole of what happens to a terminal: no clock, no file, no
callback. What the program asked to be answered (DSR, DA, DECRQM, DECRQSS,
XTVERSION) waits in the term until `takeReplies` takes it.

What it handles today: printing with deferred wrap, the wrapped flag, wide
characters (a spacer after one, a spacer head where one did not fit at the
row's end, half of one overwritten), marks joined to the cell before as a
grapheme cluster, insert mode, autowrap off, DEC special graphics and the
British set through G0 to G3, SO/SI, LS2/LS3 and SS2/SS3 (§VC17); C0 controls; CUU to CBT, CUP/HVP with origin mode, HPA, HPR,
VPA, VPR, CNL, CPL; ED 0–3, EL, ECH, ICH, DCH, IL, DL, SU, SD, IND, NEL, RI,
DECSTBM, REP, DECALN, tab stops (HTS, TBC, CHT, CBT); SGR with every
attribute Ghostty keeps, 256 and RGB colors with either separator, the
underline's kind and color; erases and scrolls in the background color;
DECSC/DECRC and SCOSC/SCORC per screen; modes 4, 20, ?6, ?7, ?25, ?47,
?1047, ?1048, ?1049 (the alternate screen kept once made, as xterm and
Ghostty keep it), and every other private mode recorded for DECRQM, KAM and
SRM recorded and the ANSI modes xterm lacks answered as permanently reset;
XTSAVE and XTRESTORE; DECSCUSR; DECSASD, where the status line takes
the printing and shows none of it, and DECECM (?117) answered as
permanently reset, as Ghostty (§VC27); reverse wraparound, ?45 and ?1045, for BS
and CUB; protected cells, DECSCA, SPA and EPA, against DECSED, DECSEL and in
ISO's mode ED, EL and ECH; the palette and the foreground, background and
cursor colors set, queried and reset (OSC 4, 10–19, 104, 110–112); left and
right margins, ?69 and DECSLRM, for printing, every scroll, IL, DL, ICH,
DCH, CR, the cursor's moves and reports, tabs and DECRQSS (§VC13); RIS and DECSTR; OSC 0 and 2 (the title);
DECRQSS for `m`, `r` and ` q`; DSR 5 and 6, DECXCPR, DA1 and DECID, DA2, DA3,
XTVERSION, XTWINOPS 14, 16, 18 and 19 and mode 2048 (the size in cells, and
in pixels when the embedder gives a cell's, V15), DECRQCRA and XTCHECKSUM
when the embedder asks for them (V5, V14); the main screen's scrollback in D901's pages (§VC6); resize,
the main screen's lines and scrollback reflowed (§VC14).

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
2 the spacer after a wide character, 3 a spacer head); bit 24 a protected
cell (§VC12); bits 32–47 the style id; the rest unused. 0 is an empty cell in the default style. A row's meta
slot, past its `cols` cells, is its extent (bits 0–15) and its wrapped flag
(bit 16).

The probe's own build had been missing a pass. `build-hot.sh` set
`GENG_CORE_PASSES` without `inplace`, which geng-lang's measurements of the
probe have had since D984 (`bench/compare/puritty.toml`); without it
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
colors (`fg`, `bg`, `ulc`: a palette index, or `#rrggbb`) and then `bold`,
`faint`, `italic`, `ul=` and the underline's kind, `blink`, `inverse`,
`invisible`, `strike`, `overline`. Ghostty keeps a cell erased in a
background color as a cell of that color and no style; the oracle prints
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
./harness/replay.py                  # 207 of 207 cases pass
./harness/replay.py -f wide --side core
./harness/replay.py --update         # expected.txt from the core: read the diff
./harness/replay.py --update --side ghostty   # a new case's expected.txt from Ghostty
```

**246 cases, every one passing on both sides, none divergent** (2026-10-30;
98 when the core was begun, nine more with §VC10, two with §VC11, eight with
§VC12, eight with §VC13, fifty-nine with §VC14, two divergent among them
until the oracle was patched (V12), four with §VC15, nineteen with §VC16
and thirty-nine with §VC17).
Each case's `expected.txt` was written by Ghostty first and the core brought
to it. Corrupting an expectation fails all three runs, which was checked.

What Ghostty taught along the way, each now a case: a backspace with a wrap
pending moves left and clears it (`bs-at-wrap`); a tab keeps a pending wrap
(`ht-at-wrap`); SU on the main screen with the whole screen as the region
sends its rows to the scrollback (`scroll-su-sd`); DCH in a background
color fills only the columns it vacates at the row's end, and the cells
past the old extent move in empty (`bce-ech-ich-dch`); a CSI of more than 24
parameters is ignored whole (`csi-many-params`); DECRQSS's SGR lists
overline before blink and writes the 16 colors as `3x`/`9x`
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
- **A CSI's parameters are counted as Ghostty counts them** (V11, §VC16):
  a separator ends one, and the last is kept only if a digit came after
  the last separator, so `CSI m` has none and `CSI 3 ; m` one; a colon
  outside SGR makes the sequence ignored, and each command takes only as
  many parameters as Ghostty's. A second intermediate makes a sequence no
  command takes (§VC17).
- **An 8-bit C1 control works outside the ground state** (`c1`, §VC15):
  inside an escape, a CSI, SOS/PM/APC or a DCS's header, 0x9B, 0x9D, 0x90
  and 0x98/0x9E/0x9F start CSI, OSC, DCS and SOS/PM/APC, 0x9C ends what
  was being parsed, and the rest are the ESC sequences they stand for. In
  the ground state such a byte is UTF-8's, as in Ghostty.
- **Strings**: OSC ends at BEL or ST; DCS at ST, and its bytes above 0x7F
  are payload (S§5.1), as are an OSC's. ESC inside either ends it and starts
  an escape, so `ESC \` is ST.

**V3 · Bounds.** Every buffer the program controls is bounded (S§5.1): a
CSI's parameters at 24, each at 65,535, a longer CSI ignored whole as
Ghostty does; an OSC's or DCS's kept bytes at 4,096 (the rest dropped; tmux
control mode in phase 4 will want 1 MiB for its DCS, S§5.1); a grapheme
cluster at 32 code points, a mark past them dropped (65 since §VC22, the
character and 64 marks, as Ghostty keeps them).

**V4 · The replies are Ghostty's for now**: DA1 `?62;22c`, DA2 `>1;0;0c`,
DA3 `!|00000000`, DECRQM's answers, DECRQSS's forms; XTVERSION answers
`puritty`. What puritty says it is is a product question for phase 3,
when programs start asking it; until then matching the oracle keeps the
gate whole. *2026-11-11:* the core's own answers stay these; its
embedder says more through `Vt.withEmbedder` (`tmux.md` TM12): puritty's
window answers DA1 `?62;21;22;52c`, XTVERSION `puritty 0.1.0`, OSC 10
and 11 from its look and DSR 996.

---

## VC6. Scrollback pages

*Since V33 (`phase2-window.md` §15.6) a page is `Config.pageRows` rows,
`Vt.defaultPageRows` (1,024) unless a caller says otherwise, and the ring
holds up to twice that; the harnesses (`core-dump`, the fuzzers,
`core-pty`) use 256, the size this section and the corpus were written
for. What follows is as it was built, at 256.*

The main screen's ring holds the screen, up to `2 × 256` rows of
scrollback and a free row, as the probe's does. When it is full, the
oldest 256 rows of scrollback are packed into a page (geng-lang D901), and
the pages are a ring of `scrollback / 256` (rounded up). A page is three
`Bytes`, made with `Bytes.fromUInt8s` from three `Builder UInt8`:

- **text**: each row's cells as UTF-8, a cluster as its code points, an
  empty cell as a 0 byte, a spacer head as 0xFF (V9, §VC14), a cell in a
  background color alone as 0xFE (§VC17), a wide character's spacer as
  nothing, and a protected cell's text followed by 0xFD (§VC19);
- **heads**: for each row a header, two bytes low first: its extent in bits
  0–13 (0–9 since §VC22, its prompt mark in 10–11), bit 14 set when every
  cell is in the default style, bit 15 when the
  row wrapped;
- **runs**: unless a row's bit 14 is set, its style runs: each a style id
  in two bytes, with bit 15 set when a count of cells (two bytes) follows;
  the last run has no count and reaches the extent. So a style id has 15
  bits and the table holds 32,768 (`styleMax`).

Read back (`dump`'s `unpackPage`), a code point of width 0 joins the cell
before it, a wide one takes its spacer, a 0 byte is an empty cell and 0xFF
a spacer head. So a page gives back every cell; until V9 a spacer head came
back as an empty cell. `scrollback-pages` and `scrollback-pages-styled` page
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
   each parameter copied the `Attrs` record; an extended color answers one
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

### At phase 1's exit

Measured again once the rest was built (2026-10-30, at 69dcf7e: §VC10's
sequences, §VC12–§VC14's wraparound, protection, colors, margins and
resize, and the lazy pages of V10), the way the table above was: the CPU
warmed by five seconds of a busy loop, then `run.sh`'s untimed run, five
timed runs of each input, the probe measured in the same session, and
instructions (millions, `/usr/bin/perf stat -e instructions:u`, one run).

| input | budget | probe | **core** | instr. probe | instr. core | core before |
|---|---:|---:|---:|---:|---:|---:|
| `cup` | 56 | 40–42 | **50–51** | 1,322 | 1,603 | 1,602 |
| `gitlog` | 132 | 76–79 | **107–110** | 2,644 | 3,385 | 3,364 |
| `ls` | 124 | 62–67 | **90–92** | 2,340 | 3,036 | 3,017 |
| vte-cursor_motion | 28 | 18–20 | **23–24** | 687 | 834 | 834 |
| vte-dense_cells | 28 | 15–16 | **19–20** | 552 | 727 | 730 |
| vte-light_cells | 24 | 9–11 | **8–9** | 367 | 341 | 333 |
| vte-scrolling | 42 | 37–40 | **37–38** | 1,382 | 1,390 | 1,405 |
| vte-scrolling_bottom_region | 37 | 23–24 | **23–24** | 916 | 934 | 942 |
| vte-scrolling_bottom_small_region | 132 | 23–24 | **23–24** | 914 | 932 | 940 |
| vte-scrolling_fullscreen | 45 | 19–22 | **28–29** | 753 | 968 | 961 |
| vte-scrolling_top_region | 223 | 23–24 | **23–24** | 916 | 934 | 942 |
| vte-scrolling_top_small_region | 125 | 23–24 | **23–25** | 914 | 932 | 940 |
| vte-unicode | 25 | 10–11 | **14–15** | 453 | 527 | 505 |

**All thirteen meet the budget**, the closest `cup`, 50–51 ms against
56, and `vte-scrolling`, 37–38 against 42, which had been the closest at
39–40. What was built since the table above moved no input's instructions
by more than 4.4% (`vte-unicode`, 505 → 527 M); `vte-scrolling` and the
four region scrolls are about 1% fewer.
This is the throughput item of phase 1's exit (`geng-plan.md` §6).

## VC8. What it found in Geng

**`Core.Pass.InPlace` lifted a read out of a closure past the `let` that
bound what it read** (geng-lang D1019, `m4-puritty.md` §VA49). `dump`'s
`historyRows` maps a closure over the scrollback's rows that calls `phys
t.screen y`; inlined, that is one `let` whose first binding is `t.screen`
and whose second reads `turn` from the first. The pass's hoist (D986), which
makes such a read when the closure is made, gathered the second binding's
read without dropping the `let`'s own names, and the C backend refused the
program: "the local `$n54` is not in scope". Fixed in the fork, with
`corpus/accept/inplace-hoist-let`.

**The parser's speed turned on clang inlining `dispatch`** into its only
caller (geng-lang `m4-puritty.md` §VA50, registered there): §VC10's
additions took it past LLVM's bonus for a function called once, and every
CSI became an out-of-line call. Nothing in Geng was changed; §VC10 says
what the core does about it.

---

## VC9. What is not built yet

Phase 1's exit (`geng-plan.md` §6) and S§5's list, against today. **The
four items of the exit are met** (2026-10-30): esctest2's rate is recorded,
the replay corpus passes against libghostty-vt with its two divergences
explained (§VC4), the fuzzer has run clean four hours, and throughput meets
the budget. What is below is what is left beside them.

- **Throughput** (§VC7): every input meets the budget, measured again at
  phase 1's exit with the rest built (2026-10-30).
- **esctest2** runs headless (§VC10): 386 of 567 tests pass, Ghostty
  v1.4.0 388 (297 at first; §VC12, §VC13, §VC15). The ten that Ghostty
  passes and the core does not need resize: XTWINOPS's resize and
  maximize, and DECCOLM, which resizes to 132 columns. **The fuzzer**
  has run clean for four hours on eight jobs, with resizes (§VC11); its
  differential against libghostty-vt is built and finds differences in
  its first second (§VC16), which are being fixed: 492 in three minutes
  after §VC17's, from 9,751 at first.
- **X11's color names** in OSC 4 and 10–19 (`red`, `DarkSlateGray`):
  Ghostty takes several hundred, from its `x11_color.zig`; the core takes
  none and leaves the color as it was. No esctest test names one. A table
  generated from Ghostty's, as `Vt.Width` is from its widths (V13), is the way.
- **The palette is only reported.** The core keeps what OSC 4 and 10–12
  set and answers for it, and draws nothing with it; the renderer reads it
  (phase 2).
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
- **Widths** are libghostty-vt's, UCD 18.0 (V13, `vt/gen-width.py`), not
  the UCD 17.0 `core` pins; `core` carries no UCD files to generate from,
  and the oracle's are what the core is held to.
- **A page cut at another width is reflowed at every read** (V10): gone
  with V20 (§VC31), which cuts every page again at the resize, so a page
  always has the screen's width and a read reflows nothing.
- **What a resize is not yet tested with**: the main screen's cursor
  behind 47 or 1047, which save none (the core carries the main screen's
  saved cursor, which 1049 made); what a resize leaves on the screen
  against Ghostty but in the corpus's cases, since the fuzzer's oracle is
  the core against itself (V7) and resizes only take part in it; XTWINOPS 8 and DECCOLM, which `core-pty` does not answer with a resize,
  so esctest's ten tests of them still fail.
- **OSC 7, 8, 52, 133, 9 and 777, DCS for tmux and XTGETTCAP, mode 2026's
  synchronized output, the title stack, the kitty keyboard stack, the mouse
  modes' state, hyperlinks**: not started; every private mode is recorded
  and answered by DECRQM, which is all most of them need in the core.
- **The style and cluster tables never shrink.** A style id is handed out
  for each new SGR combination and kept; at 32,768 a new style is the
  default (`styleMax`), which bounds memory but draws wrong. Ghostty counts
  each page's styles and frees them. The same holds for clusters at 2²¹.
  To be decided with the renderer, which reads them.
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
which changes the calculation, is not taken. (V14 takes it, §VC19; 23 is
where a new terminal starts.)

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
wraparound, resize, the color queries.

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
program cannot see and Geng has no word for (`m4-puritty.md` §VA50).

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
§EM22, `m4-puritty.md` §VA51).

**V7 · The fuzzer's findings are what the core itself can tell.** An
input's first three bytes choose the columns (1 to 132), the rows (1 to 50)
and a read's length (1 to 16); the rest is fed, but for **a 0xFE byte,
which with the two bytes after it resizes the terminal** (`Vt.resize`,
§VC14), to the sizes the two index in the same tables. UTF-8 has no 0xFE,
so no sequence is lost to it, and 0xFF still tries the decoder. A read
never crosses a resize, so both runs resize between the same two bytes. It
is a finding when a call
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
its resizes as 0xFE and the nearest sizes, read whole and seven bytes at a
time. The term keeps 600 lines of scrollback, three pages, so that a
resize meets pages cut at another width (V10); it kept 200 before. `vt.dict` gives libFuzzer the
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

**The first long run: two hours, eight jobs** (2026-10-29, at 339e266, the
row in `corpus/fuzz/runs.tsv`): 1,826,727 inputs, coverage 4,173 edges
from 3,932, and six findings, five splits and a time limit. `vt-min` cut
the splits to 41–76 bytes in under a minute each; one fix took all five, and
an older finding left over from the margins' work.

**A mark on a wide character's tail took the character's head.** At 2×25,
`中`, a cursor moved onto its spacer (`CSI 3 e`, `CHA`), then U+0301: Ghostty
joins the mark to `中`; the core dropped the mark and left the spacer
headless. `printUnicode`, the fast path for UTF-8, cut a wide character the
cursor stood in before it looked at what it was to write, and a mark makes
it stop at once and hand the byte to the general path, which found the head
already gone and nothing to join. Fed whole, the headless spacer was hidden
until a later run overwrote it in one piece; fed a read at a time, a
character written onto it alone took the cell before it, a `2` the fuzzer's
input had written there, and the two dumps differed. **Fixed:**
`printUnicode` reads the cell it starts on first, and cuts the head only
once its run has written something (`mark-on-wide-tail`, which fails
without the fix).

The fix first broke `run-over-wide-tail`, `é` over `中`'s spacer, which the
reading of the cell before the run was meant to keep: geng-lang's `floatin`
pass moved the read into the branch that used it, past the run, which writes
the row in place, and the read saw `é`. A local the inliner made of the
builder, `$n0 = s.cells`, hid that the read and the write named the same
buffer. geng-lang fixed the pass (D1021, `m4-puritty.md` §VA52); nothing
the core had before read a builder through such a local in a way the pass
could move.

**A scroll between narrow margins cost the screen's width.** The input that
took over 10 s was 1,341 bytes: margins of four columns at 132×24 and 18
REPs of 65,535, the core's cap for one. A margined scroll
copies each row's span between the margins, and `copySpan` and `clearSpan`
first made every cell of both rows explicit to the row's width and then
trimmed back from it, 132 cells twice a row where 4 moved, 24 rows every
four characters. One such REP took 0.87 s where Ghostty takes under 10 ms.
**Fixed:** both widen a row only to the column past the right margin, the
last one a span reads (`widenTo`); the extent a row is trimmed back to is
the same, since widening further adds only empty cells. The REP takes 0.12
s, and the input 2.0 s from 13.4, which is 4.7 million repeated cells at
about 0.4 µs. A REP is still a cell at a time where Ghostty's prints a
slice; that is left for when a profile asks for it.

The core after these: 125 replay cases on both sides, esctest 384 as
before, every finding replayed clean, and §VC7's thirteen times at or under
its table's but `vte-scrolling`'s, 40–43 ms against 39–40 and a budget of 42
on an idle machine, at the same instructions (1,401 M against 1,405 M):
the clock's, as §VC7 found of `cup`.

**With resizes: twenty minutes, then four hours, clean** (2026-10-30, at
cc44b75, eight jobs, the last two rows of `corpus/fuzz/runs.tsv`). Once the
fuzzer resized, twenty minutes ran 428,194 inputs to coverage 4,799 edges
from the two-hour run's 4,173, the new edges `Vt.resize`'s, and found
nothing. **Four hours** then ran 3,781,817 inputs, about 33 a second a job
where the first run's 1,826,727 in two hours were 32, to coverage 4,872, and
found nothing: no call other than `GENG_OK`, no split between the two
reads, no input over the time or memory limit. This is the recorded clean
run of phase 1's exit (`geng-plan.md` §6): four hours on eight jobs, with
resizes, against the core that passes 184 replay cases and esctest's 384.

---

## VC12. Reverse wraparound, protected cells and the colors

The three smaller of §VC10's remaining groups, in that order, each held to
Ghostty by new replay cases and to esctest: 297 → 307 → 323 → 334.

- **Reverse wraparound** (`reverse-wrap`, `reverse-wrap-extended`). BS and
  CUB are one `cursorLeft`, as Ghostty's is: with autowrap and ?45, a move
  past the first column goes on from the last column of the row above when
  that row wrapped into this one, and stops at the region's top; with ?1045
  it goes on whether the row wrapped or not, and from the region's top to
  its bottom; a pending wrap takes one of the count. The first run lost five
  tests it had passed: esctest resets with DECSTR before each test, and the
  core's DECSTR left ?45 set from the one before. **DECSTR resets what
  Ghostty's soft reset does** now: cursor keys, both reverse wraparounds,
  the numeric keypad and ESC =, left and right margins, KAM, protection and
  the palette (`decstr-modes`).
- **Protected cells** (`protect-dec`, `protect-iso`, `protect-save`).
  DECSCA 1 protects what the cursor writes from then on in DEC's mode, SPA
  (ESC V) in ISO's; DECSCA 0 or 2 and EPA (ESC W) stop it and leave the
  mode. A protected cell is bit 24 of the cell (V1), which the pen carries
  while protection is on (`guard`), and which a grapheme cluster keeps.
  DECSED and DECSEL (`CSI ?` J and K) erase only cells without it, and ED,
  EL and ECH do too in ISO's mode; DECSC saves the flag and DECSTR clears
  both. A row cleared around protected cells keeps its extent.
- **Colors** (`osc-colors`, `osc-colors-reset`). OSC 4 sets or queries
  palette entries in pairs, OSC 10 to 19 the dynamic colors from the one
  named on, OSC 104 resets entries or all, and OSC 110 to 112 the
  foreground, background and cursor. A query answers `rgb:` with 16 bits a
  channel, all of one request's answers in one reply, ended with BEL or ST
  as the request was. The core keeps only what was set (`colors`) and
  computes the rest: libghostty-vt's palette (its 16, the cube, the gray
  ramp), and no foreground or background until one is set, as
  libghostty-vt has none unless its embedder gives one; the cursor's is the
  foreground's when it has none. A color is parsed as Ghostty parses it,
  each channel's hex digits scaled to 8 bits (so `#fff` is `ffff`, where
  xterm's is `f0f0`, and esctest's `#rgb` test fails on both), with `rgb:`,
  `rgbi:` and bare hex; X11's names are §VC9's.

**A function value handed the term made it a copy everywhere.** The first
build of OSC 10's loop chose its next step as a local function, `next`,
applied to the term. That is §VC7's first finding again: the in-place pass
counts a term handed to a function value as kept, on every path of the
parser, and `vte-scrolling` took 123 ms where it took 39, `cup` 69 where it
took 49. A function of its own, `nextDynamic`, put it back; the times are
§VC7's, every input within budget (`cup` 49–54, `vte-scrolling` 39–40).

---

## VC13. Left and right margins

?69 (DECLRMM) allows them and DECSLRM (`CSI Pl ; Pr s`) sets them, as
Ghostty does: with ?69 set, `CSI s` is DECSLRM, and SCOSC only with ?69
reset; the cursor goes home after; resetting ?69, DECSTR, DECALN and RIS put
them back at the screen's edges. The term keeps `left` and `right` beside
`top` and `bottom`, and with them narrowed:

- **Printing** takes the general path (`plain` is false), wraps at the right
  margin when the cursor is left of it and at the screen's edge when it is
  right of it, and goes on at the left margin; the row is marked wrapped
  only when the cursor wraps from the screen's last column. Insert mode
  pushes cells out at the right margin.
- **IND, LF, RI, SU, SD, IL and DL** scroll the rectangle between the
  margins and the region's top and bottom (`marginUp`, `marginDown`), and
  only when the cursor is between the margins; no row goes to the
  scrollback. **ICH and DCH** work between the cursor and the right margin
  and do nothing with the cursor outside the margins. A row they touch is
  made whole, the work done with the builder's block move and fill, and its
  extent cut back to its last cell that is not empty; a wide character a
  margin cuts in two goes, both halves.
- **CR** goes to the left margin, or to the first column from left of it
  outside origin mode; NEL and LNM feed the line first and then CR, so a
  cursor right of the margins at the region's bottom does not scroll.
  **CUF** stops at the right margin, **CUP**, **HVP**, **CHA** and **HPA** in
  origin mode count from the left margin, **HT** stops at the right margin
  and **CBT** at the left in origin mode; reverse wraparound goes to the
  right margin. The cursor reports in origin mode count from the margins and
  are never negative; DECRQCRA in origin mode counts from the left margin;
  DECRQSS answers `s` while ?69 is set.

`lrm-print`, `lrm-scroll`, `lrm-edit`, `lrm-moves`, `lrm-wide`, `lrm-reset`,
`lrm-nel` and `lrm-decrqcra` hold it to Ghostty. esctest goes from 334 to 384,
one more than Ghostty's 383; one test it passed before, that DECSLRM does
nothing at VT level 3, it fails now, as Ghostty does. Ghostty fails
`test_CHA_RespectsOriginMode`, which the core passes: its CHA goes through
`setCursorPos` with the cursor's row, which origin mode then moves by the
region's top too.

**What it cost.** The margins are off the hot paths, and keeping them off
took four measurements:

1. `wrapped`, which every character calls, and `lineFeed` had grown past
   what clang inlines into `ground`; each keeps its old body, the margin
   case in a function of its own (`wrapNow`, `feedOther`).
2. **CR in the ground state cannot test anything.** Testing for narrowed
   margins at each CR, by `left`, by `plain`, by the arithmetic written in
   place or by a branch with `x = 0` kept on one side, cost
   `vte-scrolling` a cycle a line every way (205 M cycles without, 214–220 M
   with), 40–47 ms against its budget of 42. So `ground` is as it was, and
   a term with the margins narrowed has a ground state of its own,
   `groundMargined`, without the fast paths and with CR at the margin.
   Where a sequence, a string or a decoded character returns to the ground
   state, `resume` picks one, since the margins change only inside a
   sequence. That is a test and a hop a sequence: `ls` and `gitlog`, 1.3
   million sequences each, take 1.3% more instructions and 3–5 ms more,
   within their budgets of 124 and 132.

Five runs each, ms, against §VC7's:

| input | budget | §VC7 | **now** |
|---|---:|---:|---:|
| `cup` | 56 | 49–56 | **50–54** |
| `gitlog` | 132 | 107–112 | **107–111** |
| `ls` | 124 | 85–89 | **91–94** |
| vte-cursor_motion | 28 | 23–24 | **23–24** |
| vte-dense_cells | 28 | 19–20 | **19–21** |
| vte-light_cells | 24 | 7–9 | **8–10** |
| vte-scrolling | 42 | 39–40 | **39–40** |
| vte-scrolling_bottom_region | 37 | 23–25 | **23–25** |
| vte-scrolling_bottom_small_region | 132 | 23–29 | **24–25** |
| vte-scrolling_fullscreen | 45 | 27–28 | **28–30** |
| vte-scrolling_top_region | 223 | 23–24 | **24–25** |
| vte-scrolling_top_small_region | 125 | 24–26 | **24–24** |
| vte-unicode | 25 | 13–15 | **14–15** |

The fuzzer's coverage went from 3,190 edges to 3,932 with it, and five
minutes on eight jobs found nothing.


---

## VC14. Resize and reflow (V8, V9, V10)

`Vt.resize cols rows term` is what the host calls when the window changes
size: there is no sequence for it, since a program only asks (XTWINOPS 8,
DECCOLM) and the host decides. Ghostty is the oracle here as everywhere, so
the rules are Ghostty's (`Terminal.resize`, `Screen.resize`,
`PageList.resize` and `resizeCols` at `d8619f1bc`), read from its source and
then held to it case by case.

**V8 · A resize does what Ghostty's does.**

- The **main screen reflows** when the width changes and autowrap is on: its
  lines, the wrapped rows of each joined, the scrollback's among them, are
  cut again at the new width. A wide character that no longer fits at a
  row's end leaves a spacer head and goes on to the next row; a spacer head
  is dropped when its row is joined. A line's blanks at its end are dropped,
  but not before the cursor, which keeps its line as long as the cursor's
  column. Blank lines at the very end are dropped.
- When the width shrinks the rows change first, then the lines reflow; when
  it grows, the lines first. **Fewer rows** take the blank rows below the
  cursor first, then rows from the top, into the scrollback. **More rows**
  come back out of the scrollback, then blank rows are added below.
- After a reflow the screen is the last rows of the lines, with as many
  blank rows added below as keep the rows that were below the cursor
  (Ghostty's preserved cursor), so a cleared screen narrowed does not jump
  to the bottom.
- The **alternate screen never reflows**, and with autowrap off nor does
  the main screen, scrollback and all: a narrower row is cut, a wide
  character the new edge cuts goes, and the row keeps its wrapped flag; a
  wider row loses it. The alternate screen keeps no rows it loses.
- **The cursor and the saved cursors move with the cells they are on.** The
  main screen's cursor, while the alternate screen is shown, is the one
  1049 saved. A cursor waiting to wrap that ends up off the right edge goes
  on to the next cell instead; a saved cursor in a row's trailing blanks is
  kept within one row of the new width; a saved cursor the resize puts out
  of the screen goes to the top left.
- The **scroll region and the left and right margins are reset**, and the
  **tab stops** to every eighth column when the width changes.

**V9 · A page writes a spacer head as 0xFF**, a byte UTF-8 never has, where
it wrote a 0 as for an empty cell (§VC6). A reflow joins a wrapped row to
the next without its spacer head, and must tell one from an empty cell in
the scrollback too. It closes §VC9's item, a spacer head read back from a
page as an empty cell.

**V10 · The scrollback's pages are reflowed when they are read, not when
the terminal is resized.** (Replaced by V20, §VC31: a resize cuts every
page again on its bytes.) A page keeps the width its rows were cut at
(`Page.cols`). A resize works on the ring's rows, the screen and the
scrollback not yet paged, as one array of rows, each its cells as the ring
keeps them and its wrapped flag, the cursor and the saved cursor carried as
row and column (`changeRows`, `cutCols`, `reflowCols`), and `rebuild`
writes the result into a new ring, paging out as line feeds would. It
takes pages back into the array only as it needs them: the newest while a
line runs on from them into the ring (`lineStart`, by the page's last
row's wrapped flag), and more while it wants rows they hold (`short`: rows
to pull back onto the screen, or a reflow that leaves fewer than the screen
has, which only widening does). It takes all of them when it would lose
cells, which a reflow when read could not repeat: with autowrap off, where
rows are cut, and in one column, where a wide character is lost. Every
other page stays as it is, and `readPages` reflows a run of pages cut at
another width to the screen's when it is read (`dump`, a pull), or at its
own width once a resize has changed the width since it was packed
(`Page.moved`, §VC20; through every width it went through, `Page.via`,
V16, §VC22), the same
`joinLines` and `splitLine` a resize uses. A run of pages of one width ends
at a line's end, since a resize took back the page a line ran on from, so a
reflow when read cuts each line as the resize would have: reflowing twice
gives what reflowing once to the last width gives, but for the two lossy
cases, which are not left for later.

The first build reflowed every page at every resize, the pages read back
into records of arrays and paged out again (the commit before this one):
225–843 ms with a full scrollback where Ghostty takes 0–26, and as much for
a change of the rows only, which reads no page.

**The scrollback's limit now counts rows at the width they were cut at.**
The limit is in pages (§VC6), and a page narrowed later holds more rows
than it did: `ls` narrowed from 160 columns to 80 keeps 200,271 rows of
scrollback where the first build, paging every row out again, kept 100,431,
the newest of the same rows; Ghostty's limit, in lines, would prune the
narrowed rows. The bytes kept are what they were, and new output pushes the
oldest pages out as before. No case reaches the limit.

**The harness.** A case's `case.txt` takes `\R{COLSxROWS}`, which is no
byte: the terminal is resized there. `replay.py` hands both dumps the
offsets as `AT:COLSxROWS,...` (`core-dump COLS ROWS FILE CHUNK RESIZES`,
`ghostty-dump COLS ROWS FILE RESIZES`), and `core-dump`'s reads of a byte
each stop at a resize, so a resize between any two bytes is tested.

**The cases, fifty-nine**, every one written by Ghostty first, and every
one passing on both sides, whole and a byte a read, two of them divergent:

| | cases |
|---|---|
| rows only | `rows-grow`, `-grow-pulls-history`, `-grow-alt`, `-shrink-cursor-bottom`, `-shrink-cursor-top`, `-shrink-cursor-middle`, `-shrink-alt`, `-shrink-alt-back`, `-region-reset`, `pages-rows` |
| a line's cells | `cols-widen-unwraps`, `-narrow-wraps`, `-trailing-blanks`, `trailing-spaces`, `empty-rows-kept`, `cols-styles`, `-erase-color`, `-mark`, `-round-trip`, `both-shrink`, `both-grow` |
| wide characters | `cols-wide-split`, `-wide-rejoin`, `-wide-one-column`, `wide-at-edge-widen` |
| the scrollback | `cols-narrow-history`, `-widen-history`, `cursor-follows-history`, `pages-narrow`, `-widen`, `-round-trip`, `-wide-styled`, `-wide-widen` (700 and 600 lines, so pages) |
| pages left as they are (V10) | `pages-two-widths` (pages at 10 and at 7 columns, read at 13), `-long-line` and `-long-line-open` (a line of 3,000 cells over pages and the ring), `-rows-pull` (600 rows pulled back, more than the ring holds), `-widen-pull` (a widening that leaves the ring short of the screen), `-nowrap`, `-one-column-only`, `-one-column` (the lossy two) |
| the cursor | `cols-cursor-in-wrapped`, `-cursor-past-text`, `-cursor-blank-rows`, `-pending-wrap`, `-pending-wrap-narrow`, `saved-cursor`, `alt-saved-main` |
| no reflow | `cols-alt-truncates`, `-alt-active`, `alt-wrapped-narrow`, `-wide-cut`, `-widen`, `cols-nowrap-truncates`, `nowrap-history`, `-widen` |
| what is reset | `cols-tabs`, `-margins-reset` |
| divergent, until V12 patched the oracle (§VC17) | `blank-continuation`, `pages-one-column` |

(each named `resize-…`). Ghostty's own were the surprises: a cursor past a
row's text keeps the blanks before it, so `abc` with the cursor at column 7
narrowed to 4 is two rows (`cols-cursor-past-text`); a saved cursor in a
blank row's blanks lands in the first of the rows the blanks become, where
the cursor on the same cell lands in the second (`saved-cursor`); one wide
character in one column leaves a spacer head row and is gone
(`cols-wide-one-column`), an empty cell in its style; and widening without
a reflow drops the wrapped flags, where narrowing keeps them (`alt-widen`,
`alt-wrapped-narrow`).

**Where the core and Ghostty differed: a line whose last row is blank**
(until §VC17's V12, which patches the oracle; the two cases pass as any).
`abcd` wrapped, its second row erased, then `xy` on the next row, widened
from 4 columns to 8: Ghostty prints `abcdxy` on one row and puts the cursor
in it; the core prints `abcd` and `xy`. Ghostty's `reflowRow` skips a blank
row without counting a line's end when the row continues a wrapped one, so
the next line is written on in the same row; it is so on upstream main
(`108d503ac`) too. One column makes such rows of every line with a wide
character, and widening again joins every two lines
(`pages-one-column`). Both cases have a `divergence.txt` and pin Ghostty's
dump, and the report, kept and not to be filed (`upstream/README.md`), is
[`upstream/ghostty-reflow-joins-a-blank-continuation.md`](upstream/ghostty-reflow-joins-a-blank-continuation.md).

**What it costs.** `core-bench FILE resize COLS ROWS` feeds the file at 160
× 50 with 100,000 lines of scrollback, untimed, and times one resize, three
runs, ms; Ghostty the same through its C API with its line limit at
100,000, one run:

| input | history | 159 × 50 | Ghostty | 80 × 50 | Ghostty | 160 × 30 | Ghostty | 200 × 60 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ls` | 100,367 | 1 | 20.6 | 1 | 17.7 | 0–1 | 0.0 | 1 |
| `gitlog` | 100,495 | 1 | 23.3 | 0–1 | 26.4 | 0 | 0.0 | 0–1 |
| vte-scrolling_fullscreen | 49,351 | 3 | 14.5 | 2–3 | 4.5 | 0 | 0.0 | 2–3 |
| vte-scrolling | 100,474 | 0 | 24.4 | 0 | 26.1 | 0 | 0.0 | 0 |

(history is the core's; the other nine inputs leave none). The clock is
read in whole milliseconds. The first build, which reflowed every page, took
834, 338, 610 and 21 ms at 159 × 50, and 554, 225, 403 and 10 at 160 × 30.
What a resize no longer pays, reading a page pays: `dump` reads them all,
and phase 2's scrollback view will read a page at a time (§VC9).

The feed is as it was: `cup` 1,603 M instructions, `ls` 3,038 M,
vte-scrolling 1,390 M. The fuzzer, which pages but never resizes, ran two
minutes on eight jobs, unrecorded: the time went on its corpus, each job
through about 25,000 of its 34,000 inputs, and found nothing. esctest2 is at 384, the ten tests Ghostty passes and
the core does not still those that resize, since `core-pty` does not yet
answer XTWINOPS 8 or DECCOLM with one.

---

## VC15. The oracle at v1.4.0

The oracle was libghostty-vt at `d8619f1bc`, a `tip` build of 2026-10-18,
191 commits before v1.4.0 (2026-10-27). It is now v1.4.0 (`83fb95624`).
v1.4.0 needs Zig 0.17, and puritty's devbox had 0.16 from the nixpkgs
commit geng-lang's clang comes from; Zig alone is pinned to a later one,
`31ecbaca` (nixos-unstable as fetched on 2026-10-30), which has `zig_0_17` 0.17.0.
`ghostty-dump.c` and `ghostty-pty.c` built against the new library
unchanged.

**The replay corpus did not move**: 184 of 184 passed on the new oracle at
once, the two divergent cases with Ghostty's dump the same as pinned. **The
reflow report still applies**: the line it names in `reflowRow` is the same
at v1.4.0 and on Ghostty's main of 2026-10-30, the two cases show the same
screens, and GitHub's issue search finds no report of it.

**esctest moved: Ghostty 383 → 388.** Its newly passing tests are three of
CHA, HPR and VPR under origin mode, which the core passed already, and
two of BS and CUB at the left margin, which it did not: Ghostty's
`53fb05c6e` stops `cursorLeft` with reverse wrap off at the left margin
unless the cursor is already left of it, as its reverse-wrap path did. The
core's did the same only with reverse wrap on; now both paths do
(`lrm-left-stop`, which fails without it), and the core is at 386. The ten
tests Ghostty passes and the core does not are §VC9's, the ones that resize.

**v1.4.0's two parser changes** (§VC9 had registered them) are that a
stream's continuation restarts at a C1 introducer, which is a snapshot's
export and changes no screen, and that a canceled or aborted APC is thrown
away, which the core, running no APC, did already. A case probing them
(`apc-aborted`) found something else: **an 8-bit C1 control inside a
sequence**, `ESC _ hi 0x9B 32m`, which Ghostty ends the APC at and starts a
CSI with, and the core kept in the APC, losing the text after it. The old
oracle does the same; no case had sent one. Ghostty's parser takes the DEC
state machine's "anywhere" transitions from every state but three: the
ground state, where high bytes are UTF-8's; OSC, whose bytes from 0x20 are
text; and a DCS's payload, and an ignored DCS, where they are data. The
core now does as it does (`c1` and `dcsHeader`, §VC5): 0x9B, 0x9D, 0x90 and
0x98/0x9E/0x9F start CSI, OSC, DCS and SOS/PM/APC, 0x9C ends the sequence,
and the rest run as `ESC` and the byte less 0x40, so 0x85 inside a CSI is
NEL and 0x9A is DECID's reply. DEL and bytes from 0xA0 inside an escape
leave it waiting for its final byte, as Ghostty's empty table entries do.
`c1-anywhere` and `c1-edges` hold it, across every state, and a DECRQSS
with a high byte, which Ghostty answers as not recognized and the core had
dropped as text that is not UTF-8.

The core after it: 188 replay cases on both sides, esctest 386, and §VC7's
thirteen inputs level, warm, at instructions within 1.4% of §VC7's exit
table (`cup` 1,581 M from 1,603, `vte-scrolling` 1,393 from 1,390) and
every time under the budget. The fuzzer, twenty minutes on eight jobs at
65109b5 (1,490 s with loading its corpus, now 59,905 inputs), ran 482,256
inputs to coverage 4,887 edges from 4,872, and found nothing.

---

## VC16. The differential fuzzer

§VC11's fuzzer holds the core to itself: a dump fed whole against the same
dump fed a read at a time. It cannot see the core being wrong the same way
both times, which is how §VC15's C1 controls went unseen. `vt-diff` holds
it to libghostty-vt instead, in the same process, on the same inputs.

- **The input** is `vt-fuzz`'s: three bytes of size and read length, the
  rest fed, a 0xFE and two bytes a resize. The core is fed it in one read
  (`Fuzz.dump`); Ghostty is fed the bytes between the resizes and resized
  at each (`diff.h`).
- **Ghostty's dump** is `ghostty-dump`'s, which is now a function,
  `gdump` (`harness/oracle/gdump.c`), that `ghostty-dump` and the fuzzer
  both call. The replay corpus passes on it as before.
- **Scrollback.** Ghostty prunes its scrollback a page (about 400 KB) at a
  time, so its history's length cannot be the core's at any limit. Both
  keep 10,000 lines; Ghostty keeps at least that many, so while the core's
  history is under 10,000 the two must be the same, and once it reaches it
  only the screen, the cursor and the replies are compared. Ghostty gets no
  byte limit. `CSI 65535 S` makes a full history in a few bytes, so an
  unlimited one is not a choice.
- **A finding** is a crash, or a dump that differs from Ghostty's.
  `vt-diff-min` cuts one down while the dumps still differ in the same kind
  of line (the size, the cursor, the history's length, a row's text, its
  styles, a reply), so that it does not wander off to another difference.
- **Left out:** an input with a DEL. Ghostty prints DEL in the ground
  state, as a cell, where the core and xterm ignore it
  ([`upstream/ghostty-del-is-printed.md`](upstream/ghostty-del-is-printed.md)).
- **Seeds** are the replay cases but the two with a `divergence.txt`. Run
  as inputs, every other case agrees with Ghostty, and those two do not,
  which checks the comparison itself.

```
./harness/fuzz/build.sh                       # vt-diff, vt-diff-min too
./harness/fuzz.py --diff --minutes 10         # a row of corpus/fuzz/diff-runs.tsv
./harness/fuzz.py --diff --show FILE          # the core's dump and Ghostty's
./harness/fuzz/vt-diff-min FILE OUT
```

### What it found first

Eight jobs found a difference each in their first second. Three minutes
with libFuzzer's `-fork=8 -ignore_crashes=1`, which keeps going past a
finding, wrote 9,751; 120 of them, picked at random and cut down, fall into
these groups, most a few bytes long:

- **How a CSI's parameters are counted.** Ghostty's parser ends a
  parameter at each `;` or `:` and keeps the last only if a digit followed
  the last separator, so `CSI 3 ; m` has one parameter and `CSI m` none,
  where the core has `3, 0` and `0`; and every command but SGR is ignored
  if it has a colon. Each command then takes only so many parameters: CUP
  and DECSTBM two, the cursor moves, ED, EL, IL, DL, ICH, DCH, ECH, SU, SD,
  CHT, CBT and REP one, DSR and DECRQM exactly one, DECSTR none, and one
  with more is ignored (`CSI 9;;9 H` does not move the cursor). `CSI 0 S`
  scrolls nothing. This is also §VC9's `CSI 0 s`: `CSI s` has no parameter
  and `CSI 0 s` one.
- **SGR's colon groups**: a parameter Ghostty does not know followed by a
  colon is skipped with its subparameters (`CSI : 100 m`).
- **A string's end**, it seemed: the core answering an OSC or DCS cut at
  its ESC where Ghostty did not. Ghostty answers those too; what differed
  was the OSC's number and the DECRQSS's length (below).
- **A pending wrap kept** by RI, CHT and DECSTR, and set by a wide
  character at one column, where the core clears it or does not set it.
- **Scrolling and history**: DL and SU on a one-row screen, and SU by more
  than the region's rows, send more rows to the scrollback in the core.
- **DCH between margins** clears the row's wrapped flag in Ghostty.
- **Re-entering ?1049** on the alternate screen clears it in Ghostty.
- **RIS keeps OSC 12's cursor color** in Ghostty; the core resets it.
- **OSC 4 queries** with a high byte in them.

All of these are fixed, by Ghostty's code read for each (`stream.zig`'s
`csiDispatch`, `sgr.zig`, `dcs.zig`, `Terminal.zig`), each with replay
cases seeded from Ghostty, 188 → 207, but the string's end, which was the
OSC's number instead: `OSC 04` and `OSC +4` are no command to Ghostty,
whose number is digits with no leading zero, where the core read them as
4. And a DECRQSS request of more than two bytes is dropped unanswered, as
Ghostty keeps two.

**V11 · A CSI's parameters are Ghostty's.** The count, the colon rule,
and what each command takes, including that a count of 0 does nothing for
HPR, VPR, CHT, CBT, IL, DL, DCH, SU and SD, where for the rest 0 is 1
(HPR and VPR corrected in §VC17: by 0 they move as CUP does).
xterm's 0 may be 1 for those too; esctest has no test of it, and with the
rule the core passes the same 386, so the oracle's answer is taken and
the fuzzer is not left to stumble over the difference.

What the groups came to, besides the parameters (`csi-param-count`,
`csi-zero-counts`, `csi-s-params`):

- **SGR** (`sgr-colon-groups`): a colon group Ghostty does not know is
  skipped whole; `38`, `48` and `58` take `5` and an index (modulo 256) or
  `2` and three colors, with colons three or four joined parameters and
  any other count skipped; anything short of that passes over the `38`
  alone, so `38;5` is blink.
- **Strings** (`strings-dcs-osc`): an OSC's text that is not UTF-8 is still
  read, a high byte as one no command or color has; the core had dropped
  the whole string.
- **A pending wrap** (`pending-wrap-kept`): RI keeps it when it scrolls and
  clears it when it moves up; CHT, CBT, DECSTR and ED 3 keep it.
- **History** (`scroll-history-counts`): SU sends no more rows to the
  scrollback than the region has, and DL none.
- **Wrapped flags** (`wrapped-flags-kept`, `wrapped-flags-shifted`,
  `dch-margins-wrap`): DCH and ECH leave the row not wrapping, between
  margins too; ICH and insert mode keep the flag; IL, DL, SD, and an SU
  that is a DL in Ghostty (its region not the screen's top, or on the
  alternate screen not its bottom), clear it on every row of the region.
- **?1049 again** on the alternate screen saves the cursor and erases it
  (`alt-1049-again`); **RIS** keeps OSC 10–19's colors, as DECSTR does
  (`ris-keeps-dynamic`).
- **VPR and HPR** move as CUP does, to the screen's edge or in origin mode
  the margins', not as CUD and CUF; VPA kept the column wrongly in origin
  mode with a left margin (`vpr-hpr-origin`).
- **A wrap from right of the margins** takes the line feed before the
  carriage return, so it does not scroll the margins
  (`wrap-right-of-margins`).
- **A wide character with one column** to write in is an empty narrow
  cell, the cursor moving on (`wide-one-column`).
- **Resizes.** A cursor on any line but the last was put at (0,0): the
  split of each line after the cursor's wrote the cursor's place as not
  found, which only the last line's did not (`resize-cursor-above`). The
  core's own bug, and the replay corpus's fifty-nine resize cases had not
  put the cursor above text. The saved cursor lost its pen and charsets in
  a resize that rebuilt the screen (`resize-saved-state`); a cursor whose
  row goes into the scrollback goes home, as Ghostty's `cursorReload`
  puts it (`resize-cursor-history`); and with nothing saved a resize moves
  nothing, where the core had moved its (0,0) (`resize-nothing-saved`).

**What it cost.** The first build of these took `cup` from 1,581 M to
1,688 M instructions and 55–58 ms against a budget of 56: `csi` called
`dispatch` from two places, and clang inlines only a function called once
(§VC10). One call put it back to 1,628. The parameter's last digit is now
in `phase`, which every byte passes on anyway, not a `cur` of -1 that
every digit tested: 1,595. `vte-scrolling` went from 1,390 M to 1,420 and
40–42 ms against 42, which ablation put on the one-column case's call of
`printPoint` from itself; written in place, 1,390 again. Warm, five runs,
ms, and instructions, against §VC15's:

| input | budget | ms | instr. | §VC15 |
|---|---:|---:|---:|---:|
| `cup` | 56 | 48–50 | 1,595 | 1,581 |
| `gitlog` | 132 | 107–111 | 3,332 | 3,371 |
| `ls` | 124 | 89–92 | 3,027 | 3,032 |
| vte-cursor_motion | 28 | 23–24 | 830 | 823 |
| vte-dense_cells | 28 | 20–21 | 745 | 723 |
| vte-scrolling | 42 | 37–38 | 1,390 | 1,393 |
| vte-unicode | 25 | 14–15 | 527 | 527 |

`vte-dense_cells`' 3% is SGR's colon test on every parameter and Ghostty's
order of `38`'s forms; the rest are within 1%. esctest is at 386, and
every replay case and every seed passes `vt-fuzz` too.

### What is left

Three minutes again found 2,647 differences where the first three found
9,751, and 127 of the 128 first cut down agree now. A second sample of 120
falls into groups not yet looked at: VS16 after a narrow character, which
Ghostty makes wide; DEC special graphics (`ESC ( 0`) and the locking shifts
`ESC n` and `ESC o`, which the core does not take; `CSI 4 : m`; a DCS's
header with a high byte in it; DECRQM for ?66 and ?1048; a combining mark
with autowrap off; DECSCA's protection with EL; and resizes of the
alternate screen and with history. They are done, in §VC17.


## VC17. The differential fuzzer, the second round (V12, V13)

§VC16's second sample of 120 cut-down differences was fixed group by group
as its first was: Ghostty's code read for each, a case seeded from Ghostty,
the core brought to it. Then two more three-minute runs, a sample of 120
from each, the same way. Three minutes found 9,751 differences at §VC16's
start, 2,647 after its first fixes, 620 after the second sample's and 492
after the third's; the fourth sample is what is left (below). The replay
corpus went from 207 cases to 246, **none divergent**: the two that were
are not, under V12.

**V12 · The oracle is Ghostty with its bugs fixed.** Where Ghostty is wrong
and the core does not copy it, the vendored Ghostty is fixed, so that the
differential fuzzer is not left finding the same difference for ever and
a divergence is not kept as a case. `harness/oracle/patches/` holds the
fixes, applied by `harness/oracle/build.sh`, which builds the library again
when the set changes (and `harness/fuzz/build.sh` calls it). Each patch has
its report in [`upstream/`](upstream/README.md), kept and not filed. Five:

| patch | Ghostty's bug | cases |
|---|---|---|
| 0001 | a reflow joins a line to the next after a blank wrap continuation (§VC14's divergence) | `resize-blank-continuation`, `resize-pages-one-column`, no longer divergent |
| 0002 | widening without a reflow keeps a row's wrapped flag when its page was made at least as wide, and drops it otherwise | `resize-alt-widen-in-capacity` |
| 0003 | the rows a reflow joins are counted by `wrap_continuation`, which DL and DECALN leave disagreeing with the row above's `wrap` | `resize-dl-continuation`, `resize-decaln-continuation` |
| 0004 | a reflow moves the cursor onto the spacer head of a wide character that does not fit, not the character | `resize-cursor-wide-respaced` |
| 0005 | a wide character wrapping over another turns its own new spacer head into an empty cell | `wide-keeps-own-spacer-head` |

DEL, printed by Ghostty (§VC16), is not patched: its fix is in the SIMD
scan of a printable run as well, and the fuzzer leaves out an input with a
DEL as before.

**V13 · The widths are the oracle's.** `Vt.Width` is generated from
libghostty-vt's own table, `ghostty_unicode_codepoint_width`
(`harness/oracle/widths`; uucode's wcwidth from UCD 18.0), where it was
Python's `unicodedata` (15.0), so the two lay text out alike by
construction. 1,552 code points moved: 1,378 that are wide since
(U+2630's trigrams, U+4DC0's hexagrams, wide since Unicode 16), 124 new
marks, 41 prepends that take a cell (U+0600), and 9 that were wide and are
marks (U+302A–U+302D, U+115F). A code point up to 0xFF takes one cell,
as Ghostty prints it whatever its table says (U+00AD, the soft hyphen).
`vt/gen-width.py` also writes the Extended_Pictographic ranges, less
Emoji_Modifier_Base, from the same UCD's `emoji-data.txt` (below).

### What the groups were

- **Parsing.** A second intermediate makes a CSI or an escape one no
  command has (`CSI / * y`, `CSI % " q`, `CSI - ! p`), as none of Ghostty's
  takes two. A DCS's header skips a control, DEL or high byte, and a colon
  or a misplaced parameter byte makes it ignored (`dcs-header-bytes`); CAN
  and SUB end a DCS dispatched, as leaving Ghostty's DCS state unhooks it
  (`dcs-canceled`). A high byte in a string that is not UTF-8 stands as
  0x01, where it stood as `?`, which OSC 4 and 10 read as a query. OSC 4's
  indexes 256 to 260 are Ghostty's special colors, passed over
  (`osc-color-edges`).
- **Character sets** (`charsets-g0-g3`): G0 to G3, LS2 and LS3 (`ESC n`,
  `ESC o`), SS2 and SS3 (`ESC N`, `ESC O`, used up by the next character,
  a mark as well), the British set; a designation Ghostty does not know
  leaves the slot as it was, and DEC's graphics map `` ` `` to `~`, `_`
  left as it is. DECSC saves all of it.
- **SGR 4 with a colon** (`sgr-underline-colon`): `4:` alone does nothing,
  `4:3:1` skips the group, and a style Ghostty does not know is a single
  underline.
- **Modes and reports** (`decrqm-screen-modes`, `decrqm-known-modes`):
  DECRQM answers from Ghostty's table, `modes.zig`: ?47, ?1047, ?1048 and
  ?1049 as last set, not as the screen shown; `ESC =` and `ESC >` are ?66;
  ?8, ?40 and ?2033 known and ?1001 not; ?1007, ?1035 and ?1036 set until
  changed. The kitty keyboard protocol's flags, a stack of eight a screen,
  `CSI ? u` answering (`kitty-key-flags`; the core encodes no key with
  them, phase 2's). CTC (`CSI W`) and DECST8C (`CSI ? 5 W`) set and clear
  tab stops (`ctc-tabs`).
- **Editing.** EL 0 and 2 leave the row not wrapping, as Ghostty's
  `cursorResetWrap` (`el-unwraps`, `ed-unwraps`); RI's scroll unwraps the
  region as SD does (`ri-unwraps`). The half of a wide character a write
  or an edit cuts off becomes the erase cell, as Ghostty's `blankCell`,
  not an empty cell in the old style (`wide-split-blank`). A spacer head is
  written in the pen, and between margins it is an empty narrow cell
  (`spacer-head-pen`). Shifting rows between margins empties a wide
  character a margin cuts, in its style, and a spacer head at the row's end
  becomes a narrow cell, as `rowWillBeShifted` (`margins-cut-wide-styled`).
  Writing over a wide character's head in column 0 makes a spacer head at
  the end of the row above an empty cell, which a reflow keeps
  (`wide-stale-spacer-head`); `heads` says one has been written, so a
  screen without one does not pay for the test. DECALN keeps only the
  pen's colors, and fills in them (`decaln-pen`). HPR and VPR by 0 move as
  CUP does, to where the cursor is, which ends a pending wrap and in origin
  mode brings the cursor into the region (`hpr-vpr-zero`): V11 had them do
  nothing, which held for the rest of its list but not these two.
- **Marks** (`mark-autowrap-off`, `vs-needs-emoji`): with autowrap off a
  mark joins the cell before the cursor, the last column too; VS15 and
  VS16 follow only an Extended_Pictographic code point that is not an
  Emoji_Modifier_Base (uucode gives a modifier base a grapheme break of its
  own, so Ghostty's test is false for ✌ and 👍).
- **The two screens.** Each keeps its own cursor, as Ghostty keeps one a
  screen: the one not shown is resized with its own, not its saved one
  (`resize-main-cursor-47`). Each keeps its protection mode
  (`protect-mode-per-screen`) and its keyboard flags. Leaving ?1047 erases
  the alternate screen, which ends a pending wrap before the cursor is
  carried over (`alt-1047-ends-wrap`). Insert mode does not insert again
  on the row a wide character wraps to (`insert-wide-wraps`).
- **Resize.** More rows come out of the scrollback only when the cursor
  was on the last row, as `resizeWithoutReflow` pulls; otherwise blank
  rows are added below (`resize-rows-grow-no-pull`,
  `resize-both-grow-no-pull`). The blank rows a shrink takes stop at the
  saved cursor as at the cursor (`resize-saved-stops-trim`), and a row with
  no text is blank though its cells are colored (`resize-trim-bg-rows`).
  A saved cursor never set is carried as none (`resize-none-saved`). A
  cursor whose row a shrink of the alternate screen drops goes to the top
  left, column 0 too (`resize-alt-cursor-dropped`). A wide character in one
  column is an empty cell in no style, as Ghostty's reflow writes it before
  it copies a style (`resize-wide-one-column-style`).
- **An empty cell is Ghostty's `isEmpty`.** A reflow drops a line's
  trailing empty cells whatever their style, but keeps a cell an erase left
  in a background color, which Ghostty keeps as a `bg_color` cell. Every
  non-zero erase cell carries `bgBit` (0x2000000) to say so, and a page
  writes such a cell as a 0xFE byte, which UTF-8 never has
  (`pages-bg-cells`). Reading a page back, a mark after a wide character
  joined the tail written after the head, and was lost; it joins the head
  (`pages-wide-mark`), the core's own bug.
- **The fuzzer's comparison.** It compared the scrollback while the core's
  history was under 10,000 lines at the end, but a history that reached the
  limit before a resize, and was pruned at different points in each, can
  be widened back under it. `Fuzz.dump` now checks `Vt.historyBound` (the
  ring's rows, and each page's times as many rows as one can become at the
  width) before each resize and at the end, and says `pruned`; then
  `diff.h` compares only the size and the replies, since a line that runs on
  from the pruned rows is cut into rows differently too. (The core says
  it itself now, `Vt.historyReached`, §VC25.)

### What it cost

Instructions, millions, one run, against `8a0e706`, and times, warm, five
runs, ms (§VC7):

| input | budget | ms | ms at `8a0e706` | instr. | at `8a0e706` |
|---|---:|---:|---:|---:|---:|
| `cup` | 56 | 50–51 | 50–52 | 1,617 | 1,595 |
| `gitlog` | 132 | 103–106 | 102–106 | 3,384 | 3,342 |
| `ls` | 124 | 84–86 | 83–86 | 3,075 | 3,043 |
| vte-cursor_motion | 28 | 24–25 | 23–24 | 841 | 830 |
| vte-dense_cells | 28 | 19–21 | 20–21 | 750 | 745 |
| vte-light_cells | 24 | 9–10 | 8–9 | 335 | 342 |
| vte-scrolling | 42 | 38–40 | 39–40 | 1,451 | 1,393 |
| vte-scrolling_bottom_region | 37 | 23–24 | 24–25 | 997 | 934 |
| vte-scrolling_fullscreen | 45 | 26–31 | 26–27 | 977 | 968 |
| vte-scrolling_top_region | 223 | 23–24 | 23–24 | 997 | 934 |
| vte-unicode | 25 | 14–15 | 14–16 | 545 | 527 |

The times are the same. The first build was 7% over on `vte-scrolling`:
`printAscii` wrote `asciiRow`'s call twice, so clang stopped inlining it
(§VC10's lesson again), and the stale spacer head's test read the row at
every line's start, 24 instructions a line; one call, and the test only
once `heads` is set, took 96 M of the 154. Of what is left, the erase
cell's parameter to `asciiRow` is 8 M and the page's 0xFE byte 5 M; the
rest, 4% on the scrolling inputs, is not in any function on their path
(each change undone in turn, the `Term`'s new fields too, moved nothing)
and was not found.

esctest2 is at 386 as before, Ghostty at 388 with the patches.

### What is left

The fourth sample, from 492 differences in three minutes, 118 of 120 still
differing: DECRQM for ?2, ?24, ?46 and ?104; `CSI 19 t`, `CSI 22 J`,
`CSI > q` and `CSI = + c`; OSC 4 with an index written `+4`, and OSC 112
then a query; SGR `CSI : ; 1 m`; SPA with the alternate screen and an
erase in a background color; a wide character at the last column with
RI, IL, DL or SD and a resize; a wide character in one column, styled,
widened; and DECCOLM with ?40. They are done, in §VC18.


## VC18. The differential fuzzer, the fourth sample

§VC17's fourth sample, 118 cut-down differences, fixed group by group as
before. Three minutes, eight jobs, now find **73** differences where they
found 492 (564,124 inputs). The replay corpus went from 246 cases to 277,
none divergent. One more Ghostty bug is patched in the oracle (0006).

### What the groups were

- **Replies.** DECRQM answers 0 for a private mode Ghostty's table does
  not have, set or not, where the core answered for any mode it had
  recorded (`decrqm-unknown-set`); 5522, kitty's paste events, is in the
  table but answers 0 without a clipboard, and the core has none.
  `CSI 19 t` answers the text area's size as `CSI 9 ; rows ; cols t`, as
  `CSI 18 t` does with 8 (`size-report-19`). DA2, DA3 and XTVERSION take no
  second intermediate, since Ghostty counts the marker as one
  (`da-two-intermediates`). XTVERSION's name, `puritty` against
  `libghostty`, is an identity, not a difference: `diff.h` writes the core's
  name into Ghostty's reply before it compares.
- **OSC.** A color's index is decimal digits only, as Ghostty's
  `parseInt` takes an unsigned one: `+1` and `-1` end OSC 4's pairs and are
  passed over by OSC 104 (`osc4-index-digits`, `osc104-index-digits`).
  OSC 110 to 112 reset with empty parameters too, as Ghostty's words skip
  them (`osc112-empty`). A command the core takes is dropped whole when more
  than 2,048 bytes follow its number, the buffer Ghostty keeps for it
  (`osc-too-long`).
- **A colon straight after `CSI`** makes the sequence ignored, as in
  Ghostty's table, where a colon after a parameter is one more
  (`sgr-colon-first`).
- **ED 22**, Ghostty's (and kitty's) `scroll_complete`: the screen scrolled
  up into the scrollback until its last row that is not empty is gone, past
  the margins and protection, the rows coming in blank; the cursor goes up
  with its row, or home when its row goes (`ed-22`, `ed-22-cursor-below`,
  `ed-22-protected`).
- **DECCOLM.** `?3` with `?40` set resizes the terminal to 132 columns or
  80 as a host resizes it, then erases it as ED 2 and puts the cursor home;
  without `?40` it is recorded reset and nothing else (`deccolm`,
  `deccolm-needs-40`). Ghostty's dump printed the size it was last resized
  to, not the terminal's; `gdump` reads the terminal's own now, and the
  size reports' callback too.
- **Protection.** The alternate screen's clears (`?1049` on entry, `?1047`
  on exit) are ED 2's, which keep the protected cells of a screen in ISO's
  mode (`alt-clear-keeps-iso`). An erase with protection that grew a row's
  extent left the cells past the old extent as they were, and a protected
  one came back; they are cleared first (`erase-guarded-past-extent`), the
  core's own bug.
- **A wide character at an erase's edge.** ECH that ends on a wide
  character's head takes its tail too, and EL takes the whole character the
  cursor is on, as Ghostty widens both, which keeps a protected character
  whole (`ech-protected-wide-whole`, `el-protected-wide-whole`). Where ECH,
  DCH, ICH or insert mode cuts a wide character, both halves are cleared in
  the erase color, protected or not, as Ghostty's `splitCellBoundary`
  does, though its own TODO says protection should count; the core copies
  it (`ech-split-protected-wide`, `insert-margins-wide-tail`).
- **Spacer heads.** ECH, EL and DCH begin as Ghostty's `cursorResetWrap`:
  a row that wrapped is unwrapped, and a spacer head at its end becomes a
  cell in the erase color (`ech-reset-wrap-spacer-head`). At column 0 or
  1 of a row that continues a wrapped one and starts with a wide character,
  ECH and DCH make the spacer head ending the row above such a cell, also
  when that row is the scrollback's newest, while the ring holds it
  (`ech-clears-spacer-head-above`, `ech-spacer-head-in-history`). Writing a
  narrow character over a wide one in column 1, where one wraps to under a
  left margin, makes a spacer head above a plain cell, as over column 0
  (`margin-wide-unhead`). The test of column 0 read the row's cell past its
  extent, where a cleared row keeps old cells (`print-over-cleared-row`),
  the core's own bug.
- **Insert mode** makes its blanks for a wide character that does not fit
  where it is, before the wrap, and with autowrap off before writing
  nothing, as Ghostty inserts first (`insert-nowrap-wide-edge`).
- **Reflow.** A spacer head is dropped wherever it is, a row that ends a
  line too (`reflow-spacer-head-unwrapped`). The cursor's row keeps its own
  cells up to the cursor, a blank in a style too (`reflow-cursor-row-cells`).
  A cursor on a dropped spacer head goes where the next cell is written: on
  the character it was for (`reflow-cursor-dropped-head`), or on the new
  spacer head when that character does not fit at the new width
  (`reflow-cursor-head-before-wrap`), or on the row's last cell when the
  row is full (`reflow-dropped-head-full-row`). A saved cursor past a line's
  end is held to the row it starts on from the column the line so far ends
  at, counted with the wide characters a reflow moves down, not from the
  line's length (`reflow-saved-after-shift`).

**Patch 0006** ([report](upstream/ghostty-reflow-spacer-head-wraps.md)): a
spacer head that ended a row filling the new width made Ghostty's reflow
wrap onto an empty row before it dropped the head, which left the row
before wrapped and an empty row after it when the line ended there. The
patch skips a spacer head before the pending wrap, its pins moved to where
the next cell goes.

### What it cost

The first build was 5–6% slower on `gitlog` and `ls` (110–113 ms against
103–107, interleaved runs) on 0.5% more instructions, the time in the
scrollback's packing. Undoing one change at a time found it: clearing both
halves of a cut wide character in `splitWide`, which clang inlines into
`asciiRow`, where the half inside is written over anyway. The erase, insert
and delete paths take `splitWhole`, a function of its own, and the
writers keep `splitWide` as it was.

Instructions, millions, one run, and times, warm, five runs, ms, against
§VC17's (`bdb1388`):

| input | budget | ms | ms at `bdb1388` | instr. | at `bdb1388` |
|---|---:|---:|---:|---:|---:|
| `cup` | 56 | 49–51 | 50–51 | 1,615 | 1,617 |
| `gitlog` | 132 | 106–108 | 103–106 | 3,402 | 3,384 |
| `ls` | 124 | 84–86 | 84–86 | 3,096 | 3,075 |
| vte-cursor_motion | 28 | 23–25 | 24–25 | 840 | 841 |
| vte-dense_cells | 28 | 20–21 | 19–21 | 756 | 750 |
| vte-light_cells | 24 | 8–10 | 9–10 | 343 | 335 |
| vte-scrolling | 42 | 39–40 | 38–40 | 1,454 | 1,451 |
| vte-scrolling_bottom_region | 37 | 24–25 | 23–24 | 1,003 | 997 |
| vte-scrolling_fullscreen | 45 | 27–28 | 26–31 | 985 | 977 |
| vte-scrolling_top_region | 223 | 24 | 23–24 | 1,003 | 997 |
| vte-unicode | 25 | 14–16 | 14–15 | 547 | 545 |

`gitlog` and `bdb1388`'s build, run in turn, take the same 105–109 ms.

**esctest2: 392**, from 386 (Ghostty 388). DECCOLM passes
`test_DECSET_Allow80To132`, and `CSI 19 t` the nine `XtermWinops` tests
that read the display's size with it. Five are lost:
`test_DECRQM_DEC_DECHEBM`, `…DECNRCM`, `…DECPEX` and `…DECPFF`, and
`test_DECSCL_Level5_SupportsDECNCSM`, which the core passed by answering
for modes it only recorded and does not do; it answers 0 for them now, as
Ghostty does, and so passes `test_DECSCL_Level4_SupportsDECSLRMDoesntSupportDECNCSM`.

The self-fuzzer, two minutes from the seeds on eight jobs: 653,284 inputs,
no findings.

### What is left

The 73 differences of the last three minutes, not yet sampled. The fuzzer
is not recorded in `diff-runs.tsv` until a run is clean. They are done, in
§VC19.

---

## VC19. The differential fuzzer, the fifth sample (V14)

§VC18's 73 differences, cut down. Three minutes, eight jobs, now find
**27** where they found 73 (815,138 inputs, where the last run made
564,124). The replay corpus went from 277 cases to 284, none divergent.
One more Ghostty bug is patched in the oracle (0007).

### What the groups were

- **66 were the harness's.** §VC18's `own_name` wrote the core's name into
  Ghostty's XTVERSION reply wherever the text `P>|libghostty\x1b` was in its
  dump, and the fuzzer printed that text on the screen, where only Ghostty's
  side was rewritten. It rewrites a `reply` line only now.
- **ED 22 on the alternate screen** left the rows it scrolled off as
  Ghostty's history; the alternate screen has none (`ed-22-alt`,
  `ed-22-alt-cursor-leaves`). Patch 0007, below.
- **XTCHECKSUM** (`CSI Ps # y`), V14 below (`xtchecksum`, `xtchecksum-reset`).
- **REP after a wide character that did not fit.** With autowrap off, a
  wide character at the last column is not written, but Ghostty keeps every
  printable character for REP before it writes one, so `CSI b` repeats it
  (`rep-wide-nowrap`).
- **Protection in the scrollback's pages**, the core's own bug: `packCells`
  kept a cell's text and its style, not its protection, so a protected row
  that went into a page and came back on a resize was unprotected, and an
  erase in ISO's mode cleared it (`scrollback-pages-protected`, and
  `scrollback-pages-protected-wide` with DECSCA and DECSEL). A protected
  cell's text is followed by 0xFD now, a third byte UTF-8 never has (§VC6);
  a wide character's head carries it, and both halves get it back.

**V14 · XTCHECKSUM is taken.** V5 left it out because esctest expected
xterm's `checksumExtension: 23` and nothing else asked for another. Ghostty
takes it when DECRQCRA is on, and the fuzzer found it in its first minute,
so the core does what Ghostty's `xt_checksum.zig` does, which is xterm's
`xtermCheckRect`: the five bits (1 not negated, 2 no attributes, 4 no
blanks left out, 8 a cell never written to counted as a space, 16 the code
point rather than the DEC 8-bit value) are `Term.xtChecksum`, 23 in a new
terminal and again after RIS and DECSTR, as Ghostty's reset to its default
does; `CSI Ps # y` sets them when `Config.checksums` is on and there is at
most one parameter, bits past the fifth dropped. The DEC value is xterm's
`xtermCharSetDec` from the code point (0x7F and 0xFF are 0, 0x20–0x9F and
0xA1–0xFE their low seven bits, anything else, a wide character's spacer
among them, ESC); the attributes are protection 4, invisible 8, any
underline 16, inverse 32, blink 64 and bold 128; a blank is left out after
the rectangle's first counted cell unless faint, italic, struck through or
double underlined; and a cluster's marks are added only to the DEC sum with
nothing left out. Every value from 0 to 31 gives Ghostty's sum over a row
of every attribute, a wide character, a cluster, DEC line drawing and
Latin-1 (`xtchecksum` holds eight of them).

**Patch 0007** ([report](upstream/ghostty-scroll-clear-gives-the-alt-screen-history.md)):
`Screen.scrollClear` grows the page list a row at a time and does not ask
whether the screen keeps a scrollback, where `cursorDownScroll` does. The
patch erases the history after it when the screen has none, as
`Screen.resize` already does.

### What it cost

The protection test came first as one more test of each cell in
`packCells`, after the four it made already (a spacer, a cluster, a spacer
head, a background color alone): `vte-scrolling` 1.4% more instructions,
`gitlog` and `ls` 0.7%. One test now finds a plain cell, the commonest: a
mask of every bit that makes a cell more than its code point (`packSpecial`,
the width and cluster bits, `bgBit` and `protectBit`), and anything else
goes to `packOther`. That is fewer instructions than before on everything
that pages: `gitlog` 8.6%, `ls` 10.4%, `vte-scrolling_fullscreen` 11.9%.
The mask has to be written as a literal, `0x3E00000`: written as
`Bitwise.or 0xE00000 (Bitwise.or bgBit protectBit)` it is a top-level value
the program computes on first use, and each read of it in the loop cost
about 17 instructions, 331 M on `gitlog` (geng-lang `m4-puritty.md`
§VA54). geng-lang D1023 (§VA55) has the inliner fold it into the literal,
and the core writes the `Bitwise.or` again, at the literal's instructions.

Instructions, millions, one run, and times, warm, five runs, ms, against
`744bb0f`; every input's dump is the same:

| input | budget | ms | ms at `744bb0f` | instr. | at `744bb0f` |
|---|---:|---:|---:|---:|---:|
| `cup` | 56 | 49–51 | 50–51 | 1,615 | 1,615 |
| `gitlog` | 132 | 100–103 | 105–107 | 3,109 | 3,402 |
| `ls` | 124 | 80–83 | 84–88 | 2,774 | 3,097 |
| vte-cursor_motion | 28 | 23–24 | 23–25 | 840 | 840 |
| vte-dense_cells | 28 | 20–21 | 19–22 | 756 | 756 |
| vte-light_cells | 24 | 8–10 | 9–11 | 343 | 343 |
| vte-scrolling | 42 | 38–40 | 38–41 | 1,414 | 1,454 |
| vte-scrolling_bottom_region | 37 | 24–26 | 24–25 | 1,003 | 1,003 |
| vte-scrolling_bottom_small_region | 132 | 24–25 | 24–26 | 1,001 | 1,001 |
| vte-scrolling_fullscreen | 45 | 27–28 | 27–29 | 868 | 985 |
| vte-scrolling_top_region | 223 | 24–25 | 24–25 | 1,003 | 1,003 |
| vte-scrolling_top_small_region | 125 | 25–26 | 24–26 | 1,001 | 1,001 |
| vte-unicode | 25 | 15–16 | 14–16 | 547 | 547 |

`Term`'s new field costs nothing measured: the build with the old
`packCells` and everything else of this section's is at `744bb0f`'s
instructions on every input to within 1 M.

**esctest2: 392**, as before (Ghostty 388). The self-fuzzer, two minutes
from the seeds on eight jobs: 740,822 inputs, no findings.

### What is left

The 27 differences of the last three minutes, cut down (two too long for
the minimizer's two minutes) and grouped but not yet fixed (they are, in
§VC20):

- **The window's size in pixels.** `CSI 14 t` and `CSI 16 t`, and mode
  2048's report of the size, answer in pixels, which the oracle's callback
  gives as ten by twenty a cell and the core has no number for (3).
- **A wide character in a reflow, a resize to one column among them**:
  rows that start a column later or earlier in one than the other, and a
  history a row longer (14).
- **The alternate screen's clears.** `?1047l` clears the alternate screen
  in the erase color, which `?47h` then shows; the core's rows come back
  without it (3).
- **A wide character written past the right margin of a one-row screen**
  with left and right margins (2), **DL and DCH over a wide character** (1),
  **OSC 104 with an index past 255** (2), **the saved cursor after three
  resizes** (1), and **an underline one cell short** (1).

---

## VC20. The differential fuzzer, the sixth sample (V15)

§VC19's 27 differences, cut down. Three minutes, eight jobs, now find
**12** where they found 27 (623,933 inputs). The replay corpus went from
284 cases to 295, none divergent. Two more Ghostty bugs are patched in the
oracle (0008, 0009).

### What the groups were

- **The size in pixels**, V15 below (`size-report-pixels`).
- **The alternate screen's clears are in that screen's own pen.** `?1047l`
  is Ghostty's ED 2 of the alternate screen before it switches, in the
  current pen's background (`alt-1047-clear-erase-color`); `?1049h` is its
  ED 2 after the switch and before the cursor is copied, so in the pen the
  alternate screen was left with (`alt-1049-clear-own-pen`). `Term` keeps
  the hidden screen's erase cell beside its protection (`otherErase`).
- **OSC 104** names an entry with a palette index or one of the five
  special colors after it (256 to 260), which the core does not keep;
  anything else is passed over, and when every parameter is, the whole
  palette is reset, as with none (`osc104-index-out-of-range`).
- **Insert mode** inserts only when the character ends before the screen's
  edge, as Ghostty does; at the edge the core's insert had cut the wide
  character under the cursor (`insert-at-edge-wide-tail`).
- **Widening with autowrap off** (no reflow) makes a spacer head at the old
  last column a plain cell in its style, as Ghostty's `cloneRowFrom` does
  (`resize-nowrap-spacer-head`).
- **A wide character that does not fit, written over a wide character in
  column 0 or 1,** makes a spacer head above a plain cell, as a narrow one
  written there does (§VC17): the spacer head it writes is a cell like any
  other to Ghostty's `writeCell` (`wide-edge-unheads-above`).
- **The saved cursor on a dropped spacer head** goes where the cursor would
  (§VC18): on the character it was for, or on the new spacer head when that
  character does not fit (`reflow-saved-dropped-head`).
- **A page a resize has passed is reflowed at its own width.** V10 left a
  page cut at the screen's width as it was, on the premise that a reflow
  does not depend on the widths it went through. It does: Ghostty reflows
  every row at each resize, and a wrapped row followed by a blank one is a
  line its blank-continuation rule (patch 0001) ends, so four columns, then
  three, then four again is not the rows it began with. `Page.moved` is set
  on every page a width-changing reflow keeps, and `readPages` reflows such
  a page at its own width too (`scrollback-pages-moved`).

**Patch 0008** ([report](upstream/ghostty-print-right-margin-before-wrap.md)):
`print` worked out its right limit once, before the wraps in the same call,
so a wide character that wrapped from past the right margin to the left
margin kept the screen's edge as its limit. `printSlice`, which works it
out after each wrap, gives the core's answer; a cell in a style other than
the default sent the character to `print`.

**Patch 0009** ([report](upstream/ghostty-split-boundary-reads-continuation.md)):
`splitCellBoundary` cleared the spacer head above a cut wide character only
when the row was marked a continuation, which DL leaves unmarked under a
row that still wraps. The patch tests the row above's wrap, as patch 0003
made the reflow's count do and as the core does throughout.

**V15 · The embedder may give a cell's size in pixels** (`Config.cellWidth`,
`cellHeight`; 0 is unknown). With it the core answers `CSI 14 t` (`CSI 4 ;
height ; width t`, the text area), `CSI 16 t` (`CSI 6 ; height ; width t`,
a cell) and mode 2048's in-band report (`CSI 48 ; rows ; cols ; height ;
width t`), each with one parameter only, as Ghostty. Mode 2048 reports
each time it is set and after each resize while it is, the size the same
or not; DECCOLM's resize does not report. Without a size the three are not
answered, as Ghostty answers none without its size callback; `CSI 18 t`
and `19 t` need none. `core-dump`, `core-pty` and the fuzzer give ten by
twenty, which the oracle's callback and its resizes give; `core-bench`
gives none.

### What it cost

Instructions within 1 M of §VC19's core with D1023 on all thirteen inputs,
and every dump the same. `vte-scrolling`'s times, interleaved with that
build's twice, are 39–41 ms against 38–40 and 38–44: level in instructions,
a millisecond at the low end. Every other input's times are level.

**esctest2: 392**, as before (Ghostty 388). The self-fuzzer, two minutes
from the seeds on eight jobs: 741,974 inputs, no findings.

### What is left

The 12 differences of the last three minutes, cut down (eleven written by
the minimizer) and grouped:

- **REP after a character set changed** (5): Ghostty repeats the character
  as it was received, through the character set in use when REP comes; the
  core repeats what it wrote.
- **OSC 9;12**, ConEmu's mark of a prompt's start, which in Ghostty begins
  a fresh line (1).
- **SD, RI and margins before a resize** (3), and **long histories after a
  resize** (2).

They are done, in §VC21.

---

## VC21. The differential fuzzer, the seventh sample

§VC20's 12 differences, cut down. Three minutes, eight jobs, now find
**3** where they found 12 (751,310 inputs). The replay corpus went from 295
cases to 300, none divergent. One more Ghostty bug is patched in the oracle
(0010).

### What the groups were

- **REP repeats the character as it was received**, mapped through the
  character sets in use when REP comes, a single shift used up, as Ghostty
  prints its `previous_char` again; the core had repeated what it wrote
  (`rep-charset-as-received`, `rep-single-shift`). `printGraphic` is the
  ground state's path for a character set and REP's both.
- **A fresh line for a semantic prompt.** OSC 133 `A` (with options or
  none) and `L`, and ConEmu's OSC 9;12, which Ghostty takes as 133 `A`,
  begin a fresh line: CR and IND unless the cursor is at the left margin, or
  in the first column when it is left of it (`osc133-fresh-line`). The core
  keeps no prompt marks; see what is left.
- **IL, DL, SD and SU make a spacer head ending a row they move a plain
  cell**, as Ghostty's `rowWillBeShifted` does when the region is the
  screen's width; the core had kept it, and a reflow then dropped the blanks
  before it (`il-unheads-row-end`). Ghostty does the same between margins
  that reach the last column or start in the first two, and the core's
  scroll between margins already left no spacer head there: no case found a
  difference.
- **Patch 0010** ([report](upstream/ghostty-reflow-pin-copies-a-blank.md)):
  Ghostty's reflow widened a row to cover any tracked pin on it, and the
  page list's viewport pin is on the first cell of the first row, so the
  oldest row kept a blank in a style that every other row lost. The patch
  lets a pin other than the cursor's make the row be processed without
  adding cells (`reflow-first-row-styled-blank`).

### What it cost

REP's fix first went into the ground state's loop as a call of its own,
and `vte-scrolling`, which never takes that branch, went from 38–40 ms to
40–42 against its budget of 42 on the same instructions: 6% more cycles,
no more branch misses or instruction-cache misses, a function 6 bytes
longer (`resume`, the parser's step). Reverting the call alone took back
8 M of the 13 M cycles. `printGraphic`, shared by that path and REP and
too large to inline, keeps the path out of `resume`, which is 1,278 bytes
shorter than before; every input takes fewer instructions than §VC20's
build, `vte-scrolling` 1.3%:

| input | budget | ms | ms at §VC20 | instr. | at §VC20 |
|---|---:|---:|---:|---:|---:|
| `cup` | 56 | 49–52 | 50–51 | 1,603 | 1,615 |
| `gitlog` | 132 | 97–102 | 97–100 | 3,067 | 3,107 |
| `ls` | 124 | 82–86 | 81–84 | 2,730 | 2,775 |
| vte-cursor_motion | 28 | 23–24 | 23–25 | 834 | 840 |
| vte-dense_cells | 28 | 19–21 | 20 | 753 | 756 |
| vte-light_cells | 24 | 9–11 | 8–9 | 326 | 343 |
| vte-scrolling | 42 | 38–39 | 39–41 | 1,398 | 1,417 |
| vte-scrolling_bottom_region | 37 | 24–25 | 25–26 | 981 | 1,003 |
| vte-scrolling_bottom_small_region | 132 | 24–25 | 25–26 | 980 | 1,001 |
| vte-scrolling_fullscreen | 45 | 26–28 | 25–27 | 852 | 868 |
| vte-scrolling_top_region | 223 | 24–26 | 25–26 | 981 | 1,003 |
| vte-scrolling_top_small_region | 125 | 24–26 | 25–26 | 980 | 1,001 |
| vte-unicode | 25 | 14–15 | 15–16 | 532 | 547 |

Every input's dump is the same. **esctest2: 392**, as before (Ghostty
388). The self-fuzzer, two minutes from the seeds on eight jobs: 657,912
inputs, no findings.

### What is left

Two of the three differences, and one the fuzzer has not met yet (both
done, in §VC22, as Gilbert chose):

- **A page reflowed through the widths it passed** (2). V10 reflows a
  page once, from the width it was cut at to the one it is read at, and
  §VC20's `moved` does so at its own width too; Ghostty reflows every row
  at every resize, and with a line that ends in a blank row that wraps (an
  erase that kept protected cells leaves one) two widths in a row are not
  the one between them: two columns, then eight, then four is not two,
  then four. A page would have to be reflowed through each width it went
  through, or at each resize as Ghostty's are.
- **Prompt marks.** After OSC 133 `A` or `P`, Ghostty marks the rows of
  the prompt, and ED 2 with the last row that is not empty a prompt
  scrolls the screen into the scrollback as ED 22 does (Ghostty's #905: ^L
  at a prompt keeps what was above it). The core keeps no marks, and its ED
  2 clears in place.

---

## VC22. Pages through every width, and prompt marks (V16, V17)

§VC21 left two differences that were choices, and Gilbert made them: a page
reflowed through each width it went through, and Ghostty's prompt marks
with its ED 2 at a prompt. With both, and patch 0010's case, **three
minutes on eight jobs find no difference** (652,337 inputs), the first clean
run. The replay corpus went from 300 cases to 315, none divergent. One
more Ghostty bug is patched in the oracle (0011).

**V16 · A page is reflowed through every width it went through.**
(Replaced by V20, §VC31, which reflows a page at each resize, so a page
has the screen's width and `via` is gone.)
`Page.via` holds the widths the resizes since the page was packed reflowed
to, oldest first; a resize that changes the width pushes the new one onto
every page it keeps, and `readPages` reflows a run of pages from the width
they were cut at through each of `via` to the width they are read at. It
replaces §VC20's `moved`, which was the one case of it a resize back to the
page's width makes. A reflow depends on the widths it goes through, since
Ghostty's blank-continuation rule (patch 0001) ends a line at a blank row
that wraps, and a line that ends in blanks can make one at one width and not
at another: two columns, then eight, then four is not two, then four
(`scrollback-pages-via-widths`).

What it costs is reads, not resizes. 20,000 lines of scrollback, 80
columns, the widths changed and then everything read (`core-dump`, which
reads all of the history):

| resizes | before | V16 |
|---:|---:|---:|
| 1 | 0.23 s | 0.23 s |
| 2 | 0.23 s | 0.26 s |
| 8 | 0.25 s | 0.48 s |
| 50 | 0.26 s | 1.91 s |

A read of one page costs a reflow for each width it went through; a
resize's own cost does not change. Taking every page back once one had gone
through eight widths, and so reflowing them all at that resize, was tried
and measured worse: 0.49 s after 8 resizes and 2.33 s after 50, and a
resize of 0.2 s every eighth, which is a stall in a window being dragged.

**V17 · The core keeps Ghostty's prompt marks** (OSC 133, §VC21's
fresh line with them). A row's meta slot holds its mark in bits 17–18: a
prompt (`A`, `N` or `P`), or a prompt's continuation (`k=c` or `k=s`, or a
row a line feed or a wrap went to while the prompt or the input lasted). The
cursor's state is `Term.prompt` (output, prompt, input, or input to the
line's end, `I`), the hidden screen's `otherPrompt`: 47 and 1047 copy the
cursor's both ways and 1049 gives the main screen its own back, as
Ghostty's `cursorCopy` and its saved cursor do. A line feed while the input
to the line's end lasts ends it and marks nothing; a wrap marks a
continuation while the prompt or the input lasts, but not the input to the
line's end, which `printWrap` keeps. `C` at a row's start takes its mark
away. A write that moves a row's extent keeps the mark, and so do DCH and
the wrapped bit's own clear (`setWrapped`, which took it away until a case
found it, `prompt-il-moves-mark`); a row cleared whole loses it, as
Ghostty's `row.reset` does. The marks go into the pages (§VC6) and through
a reflow: a row cut from a line takes the mark of the last source row
Ghostty's reflow began while it was on the row, which copies the row's mark:
the source row of the row's last cell, or, when the row filled and so waits
to wrap, of the cell after it; and a blank row with a mark
is its first cell, as Ghostty keeps one (`prompt-reflow-blank-row`). What
the marks change: ED 2 on the main screen, when the last row that is not
blank is marked, scrolls the screen into the scrollback first, as ED 22
does, Ghostty's way of keeping what was above a prompt cleared with ^L
(#905): `prompt-ed2-scrolls`, `prompt-ed2-wrapped`, `prompt-il-moves-mark`,
`prompt-dch-keeps-mark`, `prompt-c-unmarks-row`, `prompt-alt-screens`, and
two where it must not, `prompt-ed2-after-output` and
`prompt-ed2-input-to-eol`.

A line feed in the ground state takes `execute`'s path while a prompt or the
input lasts, as it does with LNM: the loop tests one field (`lfSlow`) where
it tested `newline`, and the mark is set out of it.

**A resize clears the prompt being written**, for the shell to write again,
as Ghostty does on the main screen while its cursor is on a prompt or the
input: from the prompt's first row (up from the cursor's row past rows with
no mark to a prompt's row, or past continuations to the row above them) to
the screen's end, or only the cursor's row with kitty's `redraw=last`; the
rows keep their marks. While the alternate screen shows, the main screen's
own cursor and state decide (`prompt-redraw-main-under-alt`). Whether to
clear is `Term.redraw`, set by `A` and `N`'s first `redraw` option (`0`,
`1`, `last`), and **off in a new terminal and after RIS**, as libghostty-vt
starts one, since the core's embedder need not install a shell integration
that writes its prompt again (`prompt-redraw-clears`, `prompt-redraw-last`,
`prompt-redraw-off`). Ghostty itself starts with it on. The clear goes by the
row the cursor is on once the resize is made, the screen's top when its own
went into the scrollback, as Ghostty puts the cursor back before it clears
(`prompt-redraw-cursor-home`). It is made on the resize's rows before they
are written back, and when the search for the
prompt's first row reaches the first row taken back while pages are left,
the resize takes every page back, so that a prompt taller than the ring's
scrollback, which one column makes of a long one, is cleared from its first
row as Ghostty's is (`prompt-redraw-tall`); a resize at a prompt that
begins on the screen takes no more than it did.

**Patch 0011** ([report](upstream/ghostty-full-reset-forgets-prompt-redraw.md)):
libghostty-vt turns the prompt's clearing off when it makes a terminal, and
RIS turned it back on, Ghostty's default, so a reset terminal cleared
prompts on resize where a new one did not. The patch keeps the embedder's
choice beside the flag, as `default_xt_checksum` is kept, and RIS restores
it.

The ten-minute runs that followed the first clean three found three more:
`?1049l` on the main screen, with nothing to leave, gave the main screen the
hidden screen's prompt state (`prompt-1049l-on-main`); a full row took the
mark of its last cell's source row where Ghostty's waiting wrap gives it the
next one's; a prompt that began in a page was not cleared from there; and the
clear went by the cursor's row before the resize moved the cursor home. One
more was the harness's: once the scrollback was pruned before a resize, the
fuzzer compared the replies still, and a checksum of the screen, or the
cursor's report, reads what the two pruned differently; `diff.h` leaves
those two out of a pruned run's comparison. And one was the oracle's dump:
`gdump` read a cell's code points into 16, and a cell with more printed
empty; it reads 65 now, Ghostty's most, and the core keeps 65 where it kept
32 (V3).

### What it cost

Two things on the hot paths, both found by measuring and one put right. The
wrap's test of the prompt state first read `t.prompt` after `t` was handed
to `lineFeed`, so that the term could not be written in place: a copy of it
at every wrap, `vte-scrolling` 21% more instructions and 60% more cycles,
`clearRow` with the copy in it at 38% of them. Read first, the copy is gone.
What is left is the test itself, which makes `wrapNow` too large for clang
to inline, a call at every wrap: 15 M instructions of `vte-scrolling`'s
27 M (callgrind, and with the test taken out again); the rest is the pages'
`via` (7 M) and the header's mark. Merging the line feed's and the wrap's
marking into one function shared by five callers left it out of line all
the same.

Against §VC21's build (`4e2915f`), every dump the same:

| input | budget | ms | ms at `4e2915f` | instr. | at `4e2915f` |
|---|---:|---:|---:|---:|---:|
| `cup` | 56 | 50–52 | 49–52 | 1,619 | 1,603 |
| `gitlog` | 132 | 97–101 | 98–102 | 3,075 | 3,067 |
| `ls` | 124 | 80–84 | 81–85 | 2,736 | 2,730 |
| vte-cursor_motion | 28 | 24 | 23–24 | 842 | 834 |
| vte-dense_cells | 28 | 20–22 | 20–21 | 757 | 753 |
| vte-light_cells | 24 | 9–11 | 9–11 | 327 | 326 |
| vte-scrolling | 42 | 40–41 | 39–40 | 1,428 | 1,401 |
| vte-scrolling_bottom_region | 37 | 24–26 | 23–25 | 997 | 981 |
| vte-scrolling_bottom_small_region | 132 | 24–26 | 24–25 | 996 | 980 |
| vte-scrolling_fullscreen | 45 | 25–27 | 26–28 | 852 | 852 |
| vte-scrolling_top_region | 223 | 25–26 | 24–25 | 998 | 981 |
| vte-scrolling_top_small_region | 125 | 24–26 | 24–25 | 996 | 980 |
| vte-unicode | 25 | 15–18 | 14–15 | 574 | 532 |

`vte-unicode`'s 8% more instructions are the clusters it keeps since the
limit is Ghostty's 65 code points: it has runs of up to 76 Hangul medial
vowels, which are of width 0 and join the cell before, so a cell holds 65
of them where it held 32; its screen is Ghostty's. The rest are level with
the build before the prompt's clearing. `vte-scrolling` is a millisecond from its budget, as it was at §VC20; its
cycles are 4% more than §VC21's, all within the budget.

**esctest2: 392**, as before (Ghostty 388). The self-fuzzer, two minutes
from the seeds on eight jobs: 535,610 inputs, no findings.

### What is left

A longer run. The first recorded one, `diff-runs.tsv`'s first row: ten
minutes on eight jobs at `3a26665`, 203,456 inputs, no findings. Reading pages
after many resizes could be made cheaper by reflowing through `via` only a
page whose lines a reflow could change, one with a line that ends in
blanks; it is not measured to matter yet.

---

## VC23. Vt.geng split into modules

`Vt.geng` had grown to 8,059 lines. It is split in seven steps, a commit
each, every one a move of definitions as they were, with no other change,
and each held to the build before it, so that a change in the core's
speed would point at one step: the replay corpus, every bench input's dump
(the same hash), and its instructions and cycles (`perf stat`, cycles three
runs each), against the build of `96e1c68`. The instructions of a build
measured against itself vary by up to 0.03%, `vte-scrolling`'s by 2.5 M
(1,428.5 M to 1,431 M) now and then, and its cycles by up to 2.3%.

Geng allows no cycle of imports, so the modules go from the bottom up, each
importing those below it `exposing (..)`, and `Vt` all of them:

| step | module | what it holds | from `Vt` | instructions |
|---|---|---|---:|---|
| 1 | `Vt.Cell` | the limits, a cell's and a row's meta bits, `byteAt` | 23 + 2 | level |
| 2 | `Vt.Style` | the interned styles and the clusters' table | 13 | level |
| 3 | `Vt.Term` | `Term`, `Config`, `Screen`, `Page`, `Back`, the parser's states, the kitty keyboard stack, `reply` | 22 + 1 | level |
| 4 | `Vt.Screen` | the ring, `rowOffset`, `cellAt`, `settle`, `clearRow`, the row moves | 23 | level |
| 5 | `Vt.Pages` | packing the scrollback | 8 | level |
| 6a | `Vt.Pages` | reading pages back, `Row`, `DumpRow` | 13 | level |
| 6b | `Vt.Resize` | the reflow, `resizeScreen`, `rebuild`, `readPages` | 49 | level |
| 7 | `Vt.Dump` | the dump's rows, the styles' text, the checksum of cells | 15 | level |

Every step's dump was the same on all thirteen inputs and its instructions
within the spread above; no step moved cycles past it. Step 4 is the one
that could have: the screen's helpers are the core's hottest, and clang
inlines them across the move as it did, since a program is one C file
however many modules it is written in. A resize of `gitlog`'s 100,000
lines after step 6b gives the same dump.

`Vt` keeps what it exposes (`new`, `feed`, `takeReplies`, `resize`,
`dump`, `historyBound`), with `Term` and `Config` as aliases of `Vt.Term`'s,
which Geng accepts beside the import exposing all of it; and what the
modules below would otherwise need from it: `fresh`, which reads
constants of the sections still in `Vt`, `resizeTo` and `resized`, which
set the term's state with `withScroll`, and `rectChecksum`, which reads a
CSI's parameters. What is left in `Vt.geng`, 5,235 lines, is the parser
and everything the dispatch does: the colors, the margins, the modes, the
tabs, SGR, printing, editing a row and scrolling, which call each other and
would take a choice of seams of their own to split.

After the split: replay 318 passing, esctest2 392 (Ghostty 388), the
self-fuzzer two minutes on eight jobs with no findings in 524,574 inputs,
and the differential fuzzer ten minutes on eight jobs at `d66cc97`, no
findings in 200,197 inputs (`diff-runs.tsv`'s second row).

---

## VC24. The first long run: a quadratic reflow and a harness gap

Started with phase 2's survey (`phase2-window.md` §9): the differential
fuzzer for four hours on six jobs at `757c4ff` (the core's code is the same
at `d8b3afa`, which `diff-runs.tsv`'s third row names, the commit when the
run ended). It ended after 66 minutes, 446,707 inputs, when each job had
stopped on a finding: five on libFuzzer's 10-second timeout, one on a dump
that differs. The row stays as recorded.

**The timeouts were the core.** Each input, about 3 KB, took 10.2–11.4 s
alone on an idle machine in `vt-diff`, and 0.44 s in `vt-fuzz`, which does
not read the scrollback back. `perf`: 89% in `Vt.Resize.splitLine` and the
fold in `promptAt`, which `splitAt` called for each row it cut from a line,
and which folded over every source row of the line: a line's rows times the
rows it is cut into. The inputs resize about 90 times, down to one column,
so a line of a few thousand cells is that many rows both ways. A real
terminal meets it too: a megabyte of minified JSON is 12,500 rows at 80
columns, and V16 reflows pages when they are read. `promptAt` is now a
binary search over the starts, which `joinLines` adds in order, each
greater than the last, so the answer is the same (the last start at or
before the cell). Each input now takes 1.3–1.4 s under coverage
instrumentation, spread over the reflow's allocation, which is V16's
linear cost through 90 widths (§VC22, "What is left").

**The difference was the harness.** `vt-diff-min` cut it to 26 bytes: an
8×1 terminal, `h`, `REP` 65,535 (one line of 8,192 rows), a resize to 1×1,
and DECCOLM to 132 columns. The resize to one column makes the line 65,536
rows, past `diff.h`'s `LIMIT` of 10,000, and the core and Ghostty prune it
at different rows (the core counts rows at their cut width, §VC14);
DECCOLM's widening then brings both under the limit, 81 rows of history
against 141. That is §VC17's case, which `Fuzz.dump` marks `pruned` so that
only the size and the replies are compared, but it looked only *before*
each fuzzer resize: not after one, though a narrowing itself can cut past
the limit, and not inside the bytes fed, where DECCOLM resizes. It now
looks before and after each resize and after each read. (Not enough:
§VC25.)

After both: all six findings pass `vt-diff`, the replay corpus 318 of 318
with `core-dump` rebuilt. The feed paths are untouched and were not
re-benched.


## VC25. The second long run: a limit reached inside one read

The differential fuzzer for four hours on eight jobs at `4163c3e`, after
§VC24: it ran the four hours, 3,083,225 inputs, coverage 6,254, with no
timeout and three dumps that differ (`diff-runs.tsv`'s fourth row).

**All three were §VC24's gap again, one level down.** `vt-diff-min` cut
them to 23 and 26 bytes, each the same shape: a narrow terminal (1×4,
10×1, 1×25), one printed character, `REP` with a count of 22,202 to
65,535, mode 40 and DECCOLM to 132 columns. All of it is one read. The
`REP` takes the history past `LIMIT` and the core and Ghostty prune it at
different rows; DECCOLM's widening brings it back under (78 rows against
138, 313 against 130, 56 against 144). §VC24 has `Fuzz.dump` look after
each read, but by the end of this one the history is under the limit again,
and nothing outside `feed` can see inside it.

**The core says it now.** `Back` keeps `reach`, the scrollback asked for in
rows, and `reached`, which once set stays set. `pageOut` sets it when the
history it pages from, plus the `pageRows` rows the ring takes before the
next page goes, could reach `reach`: it can be up to a page early, never
late, and a page early only leaves out a scrollback compared that was
close to the limit. `resizeQuiet`, which `resize` and DECCOLM both go
through, sets it before and after a resize from `historyBound`, since a
narrowing can take the history past the limit with no page going. And
`Vt.historyReached` is the flag or `historyBound` at or past the limit
now. `Fuzz.dump` asks it at the end and no longer keeps its own; its `run`
only feeds and resizes.

**What it costs.** `pageOut`'s check is a sum over the pages (`pagedBound`,
which `historyBound` shares), once per 256 rows until the flag is set. As
a fold over `pagesOf` it cost 4–5% of `ls` and `gitlog` on `core-bench`,
whose 100,000 lines are 391 pages; as a loop over the builder's slots,
3.05 million instructions of `ls`'s 2,737 million (0.11%), and a build
with the check taken out counts the same as the core before it. The
wall-clock difference left (77–80 ms against 82–85) is within the
ablated build's own spread (78–85).

After it: the three findings and §VC24's six pass `vt-diff`, and the replay
corpus 318 of 318 with `core-dump` rebuilt.


## VC26. The fuzzer in fork mode, 24 jobs

Gilbert asked why the third four-hour run used three CPUs. `fuzz.py` ran
libFuzzer with `-jobs=8 -workers=8`: eight jobs, each stopped for good on
its first finding and none started in its place. The second run (§VC25)
and the third each lost five of their eight jobs to findings within two
and a half hours, the third from 04:11 to 04:58 of a run started at 02:33,
and the machine has 32 CPUs.

`fuzz.py` now runs libFuzzer's fork mode, `-fork=N` with
`-ignore_crashes=1`, `-ignore_timeouts=1` and `-ignore_ooms=1`: the parent
starts a child again when one ends, so all N CPUs work until the time is up
and every finding of the run is kept, not one a job. `--jobs` is 24 unless
told (Gilbert, 2026-10-31), which leaves eight CPUs; a job holds about
200 MB, so the scope's cap is 2 GB a job and 2 more, 50 GB, under the
machine's 60. The parent's log is `diff-logs/fork.log` (`logs/` for
`vt-fuzz`): its `#N: cov: C …` lines count every child's inputs, and each
child that ends on a finding has its log copied in, which is where the
finding's name and its `vt-fuzz:` line are read from; a finding found
twice is listed once. (It is not, with `-ignore_crashes`; the findings are
read from the files written, §VC28.)

Not run yet: the parsing was checked against a log made of the fork
mode's line format and a job log of the third run, and the first fork
run waits for Gilbert, who needs the machine.


## VC27. The third long run: RIS, DECSASD, DECECM and CHA

The differential fuzzer for four hours on eight jobs, started 02:33 on
2026-10-31 at `c40e256` (§VC25). `diff-runs.tsv`'s fifth row names
`c4a39f0`, the commit when it ended, which changed only `fuzz.py` (§VC26);
the row stays as recorded. 1,858,268 inputs, coverage 6,263, six dumps
that differ, the run's first at 04:11 and its jobs down to three by 04:58
(§VC26). `vt-diff-min` cut them to 6 to 36 bytes.

**Three were §VC25's flag, cleared by RIS.** A `REP` past the limit, a
resize or none, DECRQCRA (`CSI * y`), whose checksum reads the screen
(§VC22), then RIS. `reset` builds the term again with `fresh`, a new
`Back` with `reached` false, so the harness compared a checksum read from a
screen reflowed from rows pruned differently. Before §VC25 the flag was
the harness's own and RIS could not touch it. `reset` now keeps it, set as
well if the history is at the limit then.

**DECSASD.** `CSI 1 $ }` makes the status line the active display; Ghostty
shows none and its `print` returns before anything while it is active: no
cell written, no single shift used up, REP's character kept. Every other
sequence acts on the main display as before. `CSI 0 $ }`, RIS and DECSTR
bring the main display back; another value, no parameter or more than one
is ignored. The core has `statusLine`, which turns `plain` off so that
every character takes `printGraphic` or `printDecoded`, and both return
first while it is set. Found as a 0xFF byte (U+FFFD) printed after
`CSI 1 $ }`.

**DECECM.** DECRQM for private mode 117 is answered 4, permanently reset:
Ghostty's erases always take the current background, which is DECECM
reset, and the core's do too. It was answered 0, not recognized.

**CHA and HPA in origin mode.** Ghostty's `setCursorCol` sets the column
through `setCursorPos` with the row as CUP reads it back
(`cursorPosForSet`), so a cursor above or below the scroll region in origin
mode comes into it. ED 22 puts one there, at the top left, above a region
that starts lower. The core set the column alone; it now goes through
`cursorTo` with `originY`, as its VPR and HPR do.

Replay cases `decsasd`, `decrqm-dececm` and `cha-origin-outside`, their
`expected.txt` written by Ghostty. After it: the six findings and the
earlier runs' nine pass `vt-diff`, the replay corpus 321 of 321 with
`core-dump` rebuilt, esctest unchanged (core 392, Ghostty 388), and
`core-bench`'s instructions within 0.05% of `c40e256` on `ls`, `gitlog`,
`cup`, vte-cursor_motion and vte-unicode.



## VC28. The first fork run: a cursor's shape per screen, visibility reports

The first run in fork mode (§VC26), 24 jobs for four hours at `fac1752`,
row 6 of `diff-runs.tsv`: 3,897,159 inputs, twice the third run's
1,858,268 on eight jobs. Coverage 6,228 as the parent counts it, below the
third run's 6,263, which was read from the jobs' own logs; the two counts
are not known to be the same measure.

**The summary said none; there were five.** libFuzzer's parent counted
them (`oom/timeout/crash: 0/0/5`), but with `-ignore_crashes` it copies no
job's log into its own, so `fuzz.py`, which read each finding's name from a
copied log (§VC26), found none and recorded `none`. A finding is now a file
the run wrote under `-artifact_prefix` since it started, and the summary
says so when that number and the parent's count disagree; why one differs
is read by running it again (`--show`). Row 6 was corrected by hand to the
five files.

**Startup took 33 minutes.** Before any job starts, the parent runs every
input of the corpus and the seeds once, in one process, and keeps those
that add coverage: 59,813 inputs in, 10,285 kept, the first job at 1,973 s.
The jobs-mode runs did the same in each job, in parallel.

`vt-diff-min` cut the five to 16 and 31 bytes, two groups.

**A cursor's shape is the screen's.** Three were DECSCUSR on the alternate
screen of 1049, then DECRQSS for it (`DCS $ q SP q ST`) after 1049 was
reset: the core answered the shape set on the alternate screen, Ghostty the
main screen's. Ghostty keeps the shape on each screen's cursor
(`Screen.cursor.cursor_style`) and blinking as mode 12, one for the
terminal. 47 and 1047 copy the whole cursor, shape with it, each time the
screen changes, either way; 1049 copies it in and, going out, restores the
saved cursor, which has no shape, so the main screen's own shape shows
again. That is how the core already carries the prompt state (§VC22): the
core keeps `otherShape`, the hidden screen's, swapped as `otherPrompt` is,
and 1049's reset takes it back. DECSTR and RIS set the shown screen's only,
as Ghostty's `setCursorStyle(.default)` does, unchanged.

**Visibility reports.** Two were private mode 2033 set: Ghostty at once
sends `CSI ? 999 ; 1 n`, "potentially visible", and sends the same for
`CSI ? 998 n`; the core sent neither. It sends both now, always visible:
libghostty-vt answers from its `flags.visible`, true until its host says
otherwise, and the core has no host that says so yet. A window that knows
it is hidden is phase 2's (`phase2-window.md`); with it the core would
keep the flag and send the report when it changes while 2033 is set.

Replay cases `cursor-shape-per-screen` and `visibility-report`, their
`expected.txt` written by Ghostty. After it: the five findings pass
`vt-diff`, cut down and as found; the replay corpus 323 of 323 with
`core-dump` rebuilt; esctest unchanged (core 392, Ghostty 388); a
five-minute self-fuzz on eight jobs from the seeds, clean; and
`core-bench`'s instructions within 0.05% of `fac1752` on all thirteen
inputs.

**The corpus merged, startup still nine minutes.** `vt-diff -merge=1` into
an empty directory, one process, 33 minutes, kept 10,829 of the corpus's
60,508 inputs with every feature (43,138) and edge (6,182); it replaced
`diff-corpus` (the old one is `diff-corpus.old`, not in git). The
recorded ten-minute run after it, row 7 at `3f34881`, clean, still started
its first job at 537 s: a sixth of the inputs took a quarter of the time,
as the inputs kept are the larger. So a ten-minute fork run fuzzes for about
a minute and confirms little. A check after a change wants an hour, or a
run from the seeds alone into an empty corpus (as the self-fuzz check
does). Whether `fuzz.py` should merge after each long run, another half
hour on one CPU, is left open.


## VC29. Why a fork run starts slowly: the runtime's coverage, and resizes

§VC28's ten-minute run spent 537 s loading 10,829 inputs, about 45 ms an
input, in the one process libFuzzer's parent runs them all in before a job
starts. Measured on 300 inputs drawn from the corpus (1.2 MB, 900 bytes on
average), `vt-diff -runs=0` over them:

**The runtime had coverage, 1.75 times the run.** `build.sh` compiled
`geng.c` and `geng_rt.c`, the GC, arrays and allocation, with
`-fsanitize=fuzzer-no-link` as it did the core, so every comparison the
collector made called a libFuzzer hook: 64% of the profile was
`__sanitizer_cov_trace_cmp*`, most of it under `minor_scan` and
`geng_alloc`. It also counted the collector's own edges, 391 of 5,432 on
the sample, as coverage, rewarding an input for a new GC path. Only
`program.c`, the core, has it now: the sample 12.4 s to 7.15 s.

**The rest is the core's resize, 90%.** Ghostty's side of every input is
about 3%. Half the inputs have no resize and take 2 ms; the 17 with more
than 200 take 60% of the time, 262 ms each. The slowest is typical: `a`,
then REP of 99,920,220,279 (`CSI … b`), which fills the 10,000 lines of
`vt-diff`'s scrollback (`diff.h`, `LIMIT`) with one wrapped line, then
hundreds of resizes. A resize takes back every page a line runs on from
(`lineStart`), so each width change reflows the whole scrollback. 10,000
lines, 80 and 40 columns in turn, the whole run with its dumps:

| width changes | one long line | 12,000 short lines |
|---:|---:|---:|
| 0 | 44 ms | 284 ms |
| 1 | 49 ms | 278 ms |
| 10 | 159 ms | 586 ms |
| 50 | 638 ms | 1,983 ms |
| 200 | 2,435 ms | 7,215 ms |

About 12 ms a width change for the long line, in the resize (`pullUntil`
98.6%); about 35 ms for the short lines, but in the read after it
(`historyRows` 94%, the resizes 3.5%), as V16 measured (§VC22): each page
is reflowed through every width it went through when it is read. Ghostty
reflows every page at the resize (`PageList.resizeCols`); on the long line
its resizes were 0.27% of the profile, which puts one near 30 µs against
the core's 12 ms. That is a sample's share, not a timing of its own.

What it means past the fuzzer: a window dragged wider and narrower over a
full scrollback, at Ghostty's 25 ms coalescing, is 40 resizes a second; one
long line makes each 12 ms, and short lines make the next read of the
scrollback pay 35 ms for each. Where the core's 1.2 µs a row goes
(`readPages`' unpacking, `splitLine`, the minor collections that are a
quarter of it) is not yet looked at, and neither is whether V16's widths
could be cut short, say by reflowing a page back when a resize returns to
a width it had (§VC22's `moved`).


## VC30. A resize is the core's slowest operation: a survey (V20 proposed)

§VC29 found a fork run's slow start in the core's resize; Gilbert: the slow
resize is an issue to solve. This section measures it on the core alone and
against Ghostty, finds where the time goes, measures how fast a reflow on
the packed pages can be, and proposes V20. Nothing in the core is changed.

**Tools.** `core-bench FILE drag N COLS ROWS` (160 by 50, 100,000 lines of
scrollback, as every `core-bench` run) times N resizes, to COLS by ROWS and
back in turn, then one read of the whole scrollback (`Vt.dump`).
`probes/geng/recut/ghostty/gdrag` times libghostty-vt on the same; and
`probes/geng/recut/app` is the floor of a reflow on packed pages (below).
Inputs: one line of 160 × L `a`s, which fills L rows; L short lines
(`line 000001 the quick brown fox…`); and `gitlog.txt` of §VC7, styled,
25 MB. 160 and 80 columns in turn.

| input | core: a resize | core: added to the next read, a resize | Ghostty: a resize |
|---|---:|---:|---:|
| one line, 10,000 rows | 118 ms | — | 0.53 ms |
| one line, 100,000 rows | 740 ms | — | 4.5 ms |
| 100,000 short lines | 0.3 ms | 140 ms | 18 ms |
| `gitlog.txt` (93,500 rows) | 0.8 ms | 113 ms | 19 ms |

The read itself, with no resize, is 778 ms for the short lines and 582 ms
for `gitlog`, most of it the dump's own strings; the column that matters is
what each resize adds to it.

**Where it goes.** Two costs, one mechanism. A page is read back cell by
cell into records (`unpackText`: a record and an array of code points a
cell), each made an `Int64` cell again (`pagedCell`), the rows joined into
lines and split again as arrays (`joinLines`, `splitLine`), and, when a
resize takes the pages back, packed again (`rebuild`, `pushHistory`). On
the long line `readPages` is 55% of a resize, `reflowCols` 26%, and the
allocations and minor collections in both about 38%: some 7 µs a row of
160 cells. Short lines are cheap to resize, since V10 leaves their pages
as they are, but V16 makes every read reflow every page through every width
it went through, 1.4 µs a row a width. A long line is dear at the resize:
`lineStart` takes back every page the line runs on from, since the ring's
part of the line cannot be cut until the line's start is known, so a resize
reflows the whole line. A `cat` of one large minified file is that line.

**How fast a reflow on the packed bytes is.** A page is its rows' text,
UTF-8, one header of two bytes a row (the extent, the wrapped flag, the
prompt mark, whether it has style runs) and the style runs. For plain ASCII
in the default style a row's bytes are its cells, so a reflow is new
headers over the same text: `recut` walks each page's headers, carries a
line's length from one page to the next, and writes a header for each row
of the new width. Text with wider or longer characters needs the byte where
each cell starts: a walk of the text counting lead bytes. 20 passes, 160 and
80 columns in turn:

| input | headers alone, a pass | a walk of every byte, a pass |
|---|---:|---:|
| one line, 100,000 rows (16 MB of text) | 0.15 ms | 17 ms |
| 100,000 short lines (5.5 MB) | 0.35 ms | 6.5 ms |
| `gitlog.txt` (4 MB of text in pages) | 0.35 ms | 4.8 ms |

About 3.5 ns a row for the headers and 1.1 ns a byte for the walk: a
reflow on the packed form is as fast as Ghostty's for any text, and much
faster for plain text, against the core's 1.4 to 7 µs a row now. The
probe writes headers only; a real one also cuts style runs, and keeps
§VC14–§VC22's rules (below).

**V20 (proposed) · A resize reflows the pages at once, on their bytes.**
Each page is cut again to the new width when the width changes, as
Ghostty's are, by a reflow that reads and writes the packed form and
never makes a cell record. It replaces two decisions whose premise was
that a reflow of the scrollback is dear:

- V10, pages left at their width and reflowed when read, goes: a read
  reads a page at the screen's width and no more.
- V16, `Page.via`, goes: a page is reflowed through each width at the
  resize that goes to it, which is what Ghostty does, so the widths it went
  through need no list, and the blank-continuation rule (patch 0001) comes
  out the same as Ghostty's by construction.
- `lineStart` no longer takes back every page a line runs on from: the
  pages' part of a line is cut on the bytes, and only the line's last row
  in the pages, which the ring's rows continue, comes back into the ring to
  be cut with them.

A page then holds as many rows as the cut makes, not `pageRows`; the
history's bound already counts rows from the headers (`boundFrom`).

**What the bytes reflow must keep.** Everything `joinLines` and
`splitLine` do now, on the packed form: a wide character that does not fit
leaves a spacer head (0xFF) and wraps (§VC14, patches 0005, 0006); a spacer
head is dropped when its line is joined; a mark of width 0 stays with its
cell; a cell in a background color alone (0xFE) and protection (0xFD)
travel with their cells (§VC17, §VC19); a style run is cut where its row is;
a row cut from a line takes the prompt mark §VC22 says; a blank row that
ends a wrapped line ends it (patch 0001); and the cursor, the saved cursor
and the prompt's rows, which are in the ring, are not touched by it.

**How it would be held.** The current reflow is the reference: a fuzz
target that reflows a random page both ways (`reflowedVia` on the rows,
and the bytes reflow) and demands the same rows, besides `vt-diff`
against Ghostty, the replay corpus and `core-bench` (`drag`, and the
thirteen inputs' instructions, which no resize touches). Expected: a resize
of a full scrollback in Ghostty's range (tens of milliseconds at most for
100,000 rows of text, under a millisecond for plain text), and reads that
no longer depend on how many resizes came before them.

**Open.** The ring's own reflow (the screen and up to 513 rows not yet in
a page) stays on arrays: 0.3 to 0.8 ms a resize, measured above. Whether
plain pages should carry a flag that lets the reflow skip the walk of
their bytes is for the implementation to measure.

## VC31. V20 built: the pages cut again at a resize, on their bytes

§VC30 proposed V20; Gilbert: try it, and measure its side effects so that
the speed targets are not broken to get it. It is built as proposed, with
one change the differential fuzzer forced (the pages' size, below).

**V20 · A resize cuts every page again at the new width, on its bytes.**
`Vt.Recut.recut` walks the pages line by line. A line whose cells are all
one column wide (ASCII or a code point of width 1, protected or not, with
no spacer head, no cell in a background color alone and no mark of width
0) is cut without a cell record: its bytes are copied a run at a time into
the new pages, a header written each time a row fills, its style runs
merged and cut where its rows are, as `packCells` would have. A wrapped
source row brings its padding (the old width less its extent, as empty
cells), the line's last row loses its trailing empty cells, and a row cut
from it takes the prompt mark of the row its cells came from, which is
what `joinLines` and `splitLine` do on cells. Any other line is read back
into rows, reflowed by `reflowed` (the reflow a resize makes of the ring),
and packed again. The new rows fill pages of `pageRows` rows, as `pageOut`
cuts the ring's.

When a line runs on from the pages into the ring, only its last row in the
pages comes back (`popLast`): its cells begin the ring's first line
(`reflowCols`' `prefix`), so a resize no longer takes back every page a
long line runs on from. The way before stays, with the pages cut again
after it, when the screen wants rows the pages hold (the flow is `short`),
when the prompt to clear may begin in them, and when the resize would lose
cells (autowrap off, one column), where all pages are taken back as
§VC14 says.

What goes: `Page.via`, `passWidth` and `reflowedVia` (V16), and the reflow
when read (V10). A page has the screen's width, so `readPages` reflows
nothing, and `historyBound` counts rows exactly.

**How it is held.** `Vt.recutHolds cols t` cuts a term's pages to `cols`
both ways, `reflowed` on the rows read back and `recut` on the bytes, and
compares every cell's code points, width and style bits, and every row's
wrapped flag and prompt mark. `Fuzz.dump` checks it at 1, 3, 7, 13 and 80
columns whenever the scrollback is at most 600 lines, and `vt-fuzz` aborts
on "recut differs". It caught a bug planted for it, a prompt mark written at the wrong bit. Besides
it: the replay corpus, `vt-diff` against Ghostty, esctest2, and the dump
of the old build and the new one after 1, 2 and 5 drags of six inputs to
six widths.

### What the fuzzer found

The first one-hour run on 16 jobs (`diff-runs.tsv`'s row at `612c70f+`,
1,167,212 inputs) found seven differences from Ghostty and eleven slow
inputs; the build before V20 had none of the differences. Three causes:

- **The first row after a prefix** (two inputs). When a screen that grows
  pulls down every row of the ring's history, the screen's first row is the
  continuation of the prefix's line, and `reflowCols` counts the rows
  between the history and the cursor that continue a wrapped row to decide
  how many blank rows go below the cursor (`continuations`). The prefix is
  not one of the rows, so that row was not counted, and the core put one row
  fewer in the history than Ghostty. It is counted now. Also, the opened path
  now always says that there are rows outside the flow, since the prefix is
  one, so a flow that wants more rows than the ring has is `short` and goes
  the way before.
- **The pages' size** (five inputs). As §VC30 proposed, a new row went into
  the page its first cell came from, so the pages kept their number. A
  widening of a long line then left hundreds of pages of a few rows each.
  The scrollback's limit counts pages, so those used it up early, and the
  core kept 8,671 rows where Ghostty kept 9,951 of the fuzzer's 10,000.
  The new rows now fill pages of `pageRows` rows, as the way before did
  for the rows it took back. A narrowing can then cut more pages than the
  limit, and the resize drops the oldest and sets `reached`, as a push past
  the limit does.
- **Protected cells** (the eleven slow inputs). A protected cell's bytes
  are followed by 0xFD, and the first version sent every line with one to
  the slow path. On these inputs, all with long protected lines and
  200 resizes, V20 took 24.3 G instructions against the old build's 10.5 G
  (Ghostty: 0.03 s). The fast path now carries the byte with its cell, and
  counts a protected empty cell (`0 FD`) as an empty one when it trims a
  line's end, as `emptyCell` does. The check of the byte sits on the
  non-ASCII branch, since a check on every cell cost a short-line resize
  80% more. All eleven now take 5.4 to 8.7 G instructions, half the old
  build's, with the same dump.

After the fixes, the seven inputs agree with Ghostty and the eleven with the
old build. The self-fuzzer's run (one hour, eight jobs, with the recut
check, 2,860,914 inputs) found nothing that reproduces; it wrote one crash
file in its first second, which passes 200 runs. Its 8,670 inputs (seeds
and corpus) pass the fixed build.

### What it costs

`core-bench … drag 20 80 50` (160 by 50, 100,000 lines of scrollback, 20
resizes between 160 and 80 columns, then one read of the whole
scrollback), before V20 (`612c70f`) and after, three runs each, the median:

| input | resizes, before | resizes, V20 | read, before | read, V20 | peak memory, before → V20 |
|---|---:|---:|---:|---:|---:|
| one line, 10,000 rows | 2,205 ms | 102 ms | 151 ms | 192 ms | 355 → 169 MB |
| one line, 100,000 rows | 11,897 ms | 388 ms | 798 ms | 1,021 ms | 1,797 → 1,015 MB |
| 10,000 short lines | 20 ms | 45 ms | 292 ms | 66 ms | 72 → 65 MB |
| 100,000 short lines | 16 ms | 274 ms | 3,635 ms | 770 ms | 668 → 770 MB |
| `gitlog.txt` | 14 ms | 268 ms | 2,814 ms | 525 ms | 607 → 503 MB |

A resize is now 5 ms on the 10,000-row line (Ghostty: 0.53 ms), 19 ms on
the 100,000-row one (4.5 ms), and 13.5 ms on the short lines and on
`gitlog` (18 and 19 ms). A resize and a read together are
faster than before on every input: 2.8 times on 10,000 short lines, 9 on
the 100,000-row line. The long line's read is slower (192 against 151 ms,
1,021 against 798); that is not looked into.

**The speed targets.** The thirteen inputs' instructions (`perf stat`,
no resize) are −0.92% to +0.01% of the build before: `gitlog` −0.65%,
`ls` −0.87%, `vte-scrolling` −0.66%, `scrolling_fullscreen` −0.92%, the
other nine within ±0.01%. Their times, measured before the fixes (whose
instructions are the same), were level and inside budget: `vte-scrolling`
39–42 ms against 39–41 before (budget 42), its cycles 1% higher (212 M
against 210 M). Feeding `gitlog` alone peaks at 53 MB in both builds.

**The lossy resizes** (autowrap off, one column) take every page back as
before: one column, 10,000 short lines, two resizes, 97 → 110 ms; autowrap
off, 100,000 lines, 706 → 719 ms; the same dumps. Narrowing 100,000
unwrapped lines still costs about 350 ms a resize; a bytes version of that
cut would bring it down.

**One behavior changes: a narrowing past the limit prunes** (until V21,
§VC32, which counts the limit in bytes, so that a narrowing keeps its rows). V10 and V16
left a narrowed page at its width, so a narrowing could leave the
scrollback holding far more rows than it keeps: `m3` (§VC7's) narrowed to
7 columns held 362,679 rows for 100,000 lines of scrollback. V20 cuts
those rows into pages and drops the pages past the limit, as Ghostty
prunes: 100,535 rows, the newest of the 362,679, the screen the same. Of
the 108 dumps compared (6 inputs, 6 widths, 1, 2 and 5 drags), 96 are the
same as before and the 12 others are this: `m3` and `m4` at 7 columns, `m3`
and the 10,000-row line at 13. The `gitlog` drag above keeps 94,221 rows
where the old build kept 100,495, since every narrowing to 80 columns
went past the limit.

After all of it: replay 323 of 323, esctest2 392 (Ghostty 388).

### What is left

- The fuzz runs on the fixed build, the self-fuzzer's and a recorded
  `--diff` run, with their row.
- The 100,000-row line is 19 ms a resize against Ghostty's 4.5 ms; §VC30's
  floor for walking its bytes is 17 ms a pass. The headers-only cut for
  plain text that §VC30 measured (0.15 ms) is not built. (Built: V22,
  §VC33.)
- The lossy resizes still take every page back (above).

## VC32. A scrollback limit in bytes (V21)

§VC31's one change of behavior is that a narrowing past the limit prunes.
Gilbert: a window narrowed to 7 columns is likely to be widened again soon,
and the lines it dropped were wanted; a limit that waits (a time) was one
idea. This section measures what a narrowing costs in memory, which is what
a limit is for, and builds V21, which Gilbert chose from it.

**Tool.** `probes/geng/recut/size FILE WIDTH...` feeds FILE to a 160 by 50
term whose scrollback (100,000,000 lines) prunes nothing, resizes it to
each width in turn, and prints the pages' rows and bytes after each: text,
row headers (two bytes a row) and style runs. The ring (the screen and up
to 513 rows) is fixed in size and not counted.

| input | 160 columns | 80 | 40 | 13 | 7 | 160 again |
|---|---:|---:|---:|---:|---:|---:|
| `m3`, rows | 61,696 | 63,879 | 90,536 | 210,187 | 362,359 | 61,982 |
| `m3`, bytes | 2.56 MB | 2.57 | 2.66 | 3.06 | 3.57 (+39%) | 2.57 |
| `gitlog`, rows | 542,208 | 564,982 | 779,467 | 1,791,874 | 3,075,341 | 542,574 |
| `gitlog`, bytes | 21.6 MB | 21.7 | 22.4 | 25.8 | 30.0 (+39%) | 21.6 |
| 100,000 short lines, rows | 99,584 | 99,584 | 199,680 | 499,456 | 799,641 | 99,872 |
| 100,000 short lines, bytes | 5.68 MB | 5.68 | 5.89 | 6.49 | 7.10 (+25%) | 5.69 |
| one line of 100,000 rows, rows | 99,584 | 199,679 | 399,613 | 1,230,346 | 2,285,184 | 99,584 |
| one line of 100,000 rows, bytes | 16.1 MB | 16.4 | 16.8 | 18.5 | 20.6 (+27%) | 16.1 |

The rows grow with the narrowing, up to 23 times; the bytes by a quarter to
two fifths at 7 columns and a fifth at 13, since the text does not change
and each row adds only its header and, in styled text, its style runs again.
A narrowing and a widening back give the bytes of before, within 0.5%. A limit counted in rows prunes at a narrowing because
the count goes up, not because the memory does.

**Ghostty's limits.** Ghostty 1.4 has two (`Config.zig`):
`scrollback-limit-bytes`, 50 MB by default, and `scrollback-limit-lines`,
unlimited by default, in which soft-wrapped rows count; whichever is
reached first prunes. With its defaults, then, Ghostty does not prune for
a narrowing by a count of rows either, only when its bytes grow (its pages
are grids of cells, so its bytes follow the cells, not the text). The
oracle sets the line limit and no byte limit (`gdump.c`), which is why
§VC31's pruning agrees with it.

Two limits, bytes and rows, were proposed first, as Ghostty's. Gilbert:
two limits confuse; one limit, in bytes, with a helper that gives the bytes
for a number of rows of a width, knowing that what the lines hold changes
how many rows the bytes keep.

**What the bytes of a row depend on.** At 160 columns, from the table
above: 40 bytes a row of `gitlog`, 41 of `m3`, 57 of the short lines, and
162 of the one long line, whose rows are full. Lines shorter than the
screen take less, since a row's trailing blanks are not stored; a cell of
ASCII is a byte, of CJK 3 bytes for 2 columns, of an emoji 4 for 2, and a
mark of width 0 adds its bytes; a style changed inside a row adds 4 bytes a
change. The same bytes keep about four times as many rows of ordinary
output as of full rows of text.

**V21 · The scrollback's limit is in bytes, one limit.** `Config.scrollback`
(rows) becomes `scrollbackBytes`: the most the pages may hold, their text,
row headers and style runs together; 0 is none. A page pushed past it drops
the oldest pages until the pages fit, and so does a resize, so a narrowing
drops pages only when the bytes it adds pass the limit, and a widening back
finds every line. `Vt.scrollbackBytesFor { cols, rows }` is `rows × (cols +
2)`: the bytes of `rows` full rows of text in one style, a byte a cell and
a header, so that `rows` is what plain full-width text gets at the least.
Ordinary output gets several times as many; text whose style changes inside
its rows, or of characters of more bytes than columns, gets fewer. The
default the host is to use is `scrollbackBytesFor` 25,000 rows of the
width the terminal starts with (4.05 MB at 160 columns; it was 100,000
rows, 16.2 MB, until the costs below were measured, "The default"); the
core has no default of its own, as `Config` has none.

No clock is needed: what is dropped depends only on what was fed and how
the term was resized. A limit that waits was set aside: the core has no
clock (§VC1), a prune after an idle time would be a new call, a policy, and
a dump that depends on when it ran, and the memory a narrowing costs is a
quarter to two fifths more at 7 columns, which the byte limit bounds anyway.

**As built.** `Back` is a queue: the pages from slot `head` on, the oldest
first; a page dropped is emptied and `head` moves on, and the slots are
moved down once half of them are dropped ones. It keeps the pages' `bytes`
and `rows` as it pushes and drops, so `historyBound` is the ring's rows and
`rows`, with no walk of the pages (`pagedBound` goes). A resize hands its
pages to `backOf`, which totals them and applies the limit. For the
differential fuzzer, `Back` keeps `peak`, the most rows the scrollback may
have held (noted as a page goes and before and after a resize, as
`reached` was, §VC25), and `dropped`, whether a page has gone for the
limit; `historyReached rows t` is `dropped`, or `peak` at least `rows`, and
RIS keeps both. `reach` and `reached` go.

**The fuzzers.** Ghostty keeps 10,000 rows (`gdump.c` sets its line limit),
and `Fuzz.dump` gives the core the bytes of 10,000 rows of 132 columns,
the widest width it resizes to, so that the core rarely drops a page
before Ghostty prunes; the dump says `pruned` once either may have
(`historyReached 10000`), and only then do the two compare less. No mode
exists for the fuzzer alone. `vt-fuzz` asks for 600 rows the same way, and
holds the pages to the reflow (`recutHolds`) while the history is under
1,200 rows, which bounds the check's time as the 600 rows did.
`core-dump`, `core-bench`, esctest's `core-pty` and the probes give
`scrollbackBytesFor` the rows they kept before.

### What it costs

Everything in this part gives the core `scrollbackBytesFor` 100,000 rows of
160 columns (16.2 MB), where it kept 100,000 rows before; "The default"
below measures the 25,000 rows chosen after it.

**The speed targets.** The thirteen inputs' instructions are −2.30% to
+0.05% of the build before V20 (`vte-scrolling` −2.30%, `scrolling_fullscreen`
−0.98%, `ls` −1.05%, `gitlog` −0.65%, the other nine +0.01% to +0.05%): a
page pushed adds three lengths to two totals, and the walk of every page
that `pagedBound` made at each push is gone. Times, five runs warm, least
and most, are level and inside the core's budgets (§VC2) on all thirteen
but one, which is inside its budget and 3 ms slower: `gitlog`, 100–103 ms
against 97–100 (budget 132). It keeps more of its scrollback, 415,375 rows
where it kept 100,000, and its peak memory is 64 MB against 53.
`vte-scrolling`'s lines are so short that the same bytes keep 2,666,618 rows
of them, for 4 MB more (30 against 26 MB peak); `ls` and the others are level.

**What is kept.** Of §VC31's 108 dumps after a drag (6 inputs, 6 widths, 1,
2 and 5 drags), 84 are the same as the build before V20, and in the 24
others the old history is the newest part of the new and the screen is the
same: the old build pruned to 100,000 rows where the bytes keep more, at
one column (all six inputs) and the long line at 7 and 13 columns. The long
line narrowed to one column and widened back now has the dump of the long
line never resized: nothing was dropped on the way.

**Resizes cost what the rows they reflow cost.** `drag 20 80 50`, three
runs, the median, against V20 (§VC31), which kept 100,000 rows:

| input | resizes, V20 | resizes, V21 | read, V20 | read, V21 | peak, V20 → V21 |
|---|---:|---:|---:|---:|---:|
| one line, 10,000 rows | 102 ms | 107 ms | 192 ms | 186 ms | 169 → 173 MB |
| one line, 100,000 rows | 388 ms | 781 ms | 1,021 ms | 2,107 ms | 1,015 → 2,314 MB |
| 10,000 short lines | 45 ms | 48 ms | 66 ms | 65 ms | 65 → 65 MB |
| 100,000 short lines | 274 ms | 293 ms | 770 ms | 759 ms | 770 → 737 MB |
| `gitlog.txt` | 268 ms | 1,075 ms | 525 ms | 1,793 ms | 503 → 1,392 MB |

The peaks include the read, the dump's strings of every row. `gitlog`
keeps four times the rows, and a resize costs four times as much: 53 ms,
against Ghostty's 19 ms for the 93,500 rows it keeps at its 100,000-line
limit; a row costs what it did. The long line keeps its 100,000 rows of
160 columns and, at 80, the 200,000 they make, where V20 pruned them to
100,000 at every narrowing. So the byte limit's default decides a resize's
cost as much as the history's length: the same 16.2 MB is 4 times the rows
of ordinary output, and 4 times the resize. A smaller default, or the
headers-only cut for plain text (§VC30), are the two ways back to V20's
times on `gitlog`; neither is chosen here.

After it: replay 323 of 323, esctest2 392 (Ghostty 388); the fuzzers'
findings of §VC31 and their 10,126 inputs pass.

### The default: 25,000 rows

Gilbert chose a smaller default. `scrollbackBytesFor` 25,000 rows of 160
columns is 4.05 MB, about what the build before V20 kept of `gitlog` at its
100,000 rows (40 bytes a row, from the table above: 4.0 MB). `core-bench`,
`core-dump` and the probes give it; esctest's `core-pty` keeps its 1,000.

**What is kept**, at 160 columns: `gitlog` 93,327 rows (100,000 before
V20), `ls` 34,063 (100,000; its rows are long and colored, 119 bytes
each), `vte-scrolling` 1,350,266 (100,000; rows of a few bytes), `cup` none.
A host that wants more of `ls`-like output sets more; the bytes are the
limit, and the rows are what the output makes of them.

**The speed targets.** Instructions against the build before V20: `cup`
+0.01%, `gitlog` −0.68%, `ls` −0.64%, `scrolling_fullscreen` −0.63%,
`vte-scrolling` −0.48%, the other eight +0.01% to +0.06%. Times, five runs
after a warm-up, least and most, the build before V20 and V21 in the same
session: all thirteen inside their budgets (§VC2), and level but for two.
`gitlog` is 99–106 ms against 96–101 (budget 132), as it was at 16.2 MB.
`vte-scrolling` is 40–43 ms against 38–41, over 40 runs, and its budget is
42: one run in 40 was over it. Its instructions are fewer, its cycles 3.1%
more, its cache misses 9% and its page faults 21%: it keeps 1,350,266
short rows (29 MB peak, 26 before V20) where the build before kept 100,000.
Peak memory: `gitlog` 58 MB (53 before V20), `ls` 58 (66).

**Resizes.** `drag 20 80 50`, three runs, the median:

| input | resizes, V20 | 16.2 MB | 4.05 MB | read, 4.05 MB | peak, 4.05 MB |
|---|---:|---:|---:|---:|---:|
| one line, 10,000 rows | 102 ms | 107 ms | 105 ms | 187 ms | 173 MB |
| one line, 100,000 rows | 388 ms | 781 ms | 207 ms | 466 ms | 458 MB |
| 10,000 short lines | 45 ms | 48 ms | 49 ms | 66 ms | 65 MB |
| 100,000 short lines | 274 ms | 293 ms | 212 ms | 519 ms | 478 MB |
| `gitlog.txt` | 268 ms | 1,075 ms | 263 ms | 510 ms | 506 MB |

`gitlog`'s resizes are back to V20's, and the long lines' are faster, since
V20 pruned to 100,000 rows after the narrowing and the bytes now keep
fewer before it. Replay 323 of 323.

**The fuzzers on V21** (161d087; they set their own limits, below). The
differential run, one hour on 16 jobs, ran 678,085 inputs; the self-fuzzer,
one hour on 8 jobs at the same time, with the seeds and corpus of §VC31's.
Neither found a crash or a difference. They wrote 40 and 33 slow or
timed-out inputs (36 and 28 distinct), and each costs 3.5 to 15.8 times
V20's instructions on V20's own fuzzer build (`vt-diff`'s slowest: 5.7 s
against 0.38 s, 117 MB against 63). All are many rows of few bytes, then
hundreds of resizes (43 to 2,699): in the differential run mostly the long
line of §VC30, a REP of 65,535 to billions narrowed to a few columns, where
a row takes 3 to 5 bytes; in the self-fuzzer, thousands of one-character
lines. The fuzzers' limits are the bytes of 10,000 and 600 rows of 132
columns (1.34 MB and 80 KB, `Fuzz.dump`), so of such rows the core keeps
tens of times what V20 and Ghostty kept (10,000 and 600), 270,000 to
450,000 of the line at 1 to 3 columns, and reflows them at every resize.
This is what "Resizes cost what the rows they reflow cost" measured, met at
the fuzzers' widths and lines; the slow inputs are the price of a byte
limit on rows of few bytes, not a defect, and are not saved as findings.
The lower rate (1,167,212 inputs in §VC31's run) is partly the
self-fuzzer's 8 jobs beside it.

### A resize against Ghostty's, compared alike

The comparisons with Ghostty above, and §VC30's and §VC31's, gave the two
terminals different limits: the core its rows or bytes, Ghostty 100,000
lines, which counts wrapped rows and drops half of a long line at a
narrowing to 80 columns. Each then reflowed a different history, and the
times compared the limits as much as the resizes. Gilbert asked for a
comparison of like with like. This is it, and later ones are to be made
the same way:

- **The same history.** Neither terminal has a limit: `core-bench FILE drag
  20 80 50 2000000000` (BYTES, after the drag, is the limit) and `gdrag FILE
  20 80 50 0 0` (LINES and BYTES, 0 none), so neither drops a row.
  `core-dump` takes the limit after RESIZES, and `ghostty-dump` a line limit
  after its RESIZES, 0 none, so that the dumps can be compared too.
- **The same result.** After the 20 resizes (to 80 columns and back to 160,
  in turn, given to both dump tools at the input's end), the core's dump and
  Ghostty's are the same, byte for byte, on all five inputs: the history,
  its rows at each width, and the screen.
- **The same work timed.** Only the resizes. Both are eager: the core's
  since V20, and Ghostty's `resizeCols` (`PageList.zig`) walks every row
  into new pages at the resize. Neither leaves work for a later read.
- **A unit of work.** A resize's time over the rows it reflows, the mean of
  the history at 160 and at 80 columns.

Three runs each, the median:

| input | rows, 160 / 80 | core, a resize | Ghostty, a resize | core, ns a row | Ghostty, ns a row | core ÷ Ghostty |
|---|---:|---:|---:|---:|---:|---:|
| one line, 10,000 rows | 9,950 / 19,950 | 4.95 ms | 0.46 ms | 331 | 31 | 10.8 |
| one line, 100,000 rows | 99,950 / 199,950 | 34.8 ms | 8.65 ms | 232 | 58 | 4.0 |
| 10,000 short lines | 9,951 / 9,951 | 2.25 ms | 0.80 ms | 226 | 80 | 2.8 |
| 100,000 short lines | 99,951 / 99,951 | 13.6 ms | 19.0 ms | 136 | 190 | 0.72 |
| `gitlog.txt` | 542,607 / 565,403 | 70.4 ms | 114 ms | 127 | 207 | 0.61 |

On ordinary output at length the core's resize is faster than Ghostty's,
0.61 and 0.72 of its time, and its cost a row falls as the history grows
where Ghostty's rises (80 to 190 ns). It is slower in two places. A small
history costs the core about a millisecond a resize whatever its rows, so
10,000 short lines take 2.8 times Ghostty's time. A long line wrapped
across many rows costs it 4 to 11 times Ghostty's a row; this is §VC30's
gap, which the cut of plain text by its row headers alone would close and
which neither V20 nor V21 built. Neither is chosen here.

What each terminal keeps by default is a separate question, of policy and
not of speed: with its own default (50 MB, no line limit) Ghostty keeps all
542,607 rows of `gitlog` and takes 114 ms a resize, where the core's
default (4.05 MB) keeps 93,327 and takes 13 ms (263 ms for the 20, "The
default" above).

## VC33. A plain line cut on its headers alone (V22)

§VC32's comparison with Ghostty left the core 4 to 11 times slower a row on
a long wrapped line, the gap §VC30 measured and proposed to close by
cutting plain text on its row headers alone (0.15 ms a pass for the
100,000-row line, against 17 ms for a walk of its bytes). Gilbert: build
it.

**V22 · A resize cuts a plain line by arithmetic.** A page is *plain* when
it has no style runs and a byte a cell: its rows' text is as long as their
extents. A line all on plain pages, with no prompt mark and every row that
wraps full, so that no empty cells pad it, is cut at the new width without
a byte read: every row full and wrapped but the last, its text the pages'
text in order, less the empty cells that end the last row. `Recut` walks
the headers to find where the line ends (`plainSpans`), and moves its text
as one slice a page it runs over, merged with the slice before when it
follows it, and joins a new page's slices when the page is done
(`Bytes.flatten`), so no byte is copied one at a time either. A line on
other pages is cut as before (§VC31).

`Page.plain` is `Unsure | Plain | NotPlain`. A page paged out of the ring is
`Unsure`, so paging out costs nothing for it, and the first resize decides
it from the headers (`settlePlain`): no style runs, text as many bytes as
the extents sum to, and no row that wraps ending in a spacer head (0xFF),
read at the offset the sum gives. With no style runs and a byte a cell, a
cell is ASCII, an empty cell's 0, or a spacer head, which ends only a row
that wraps; a cell in a background color alone (0xFE) carries its color
(`eraseCell`), so it has a style run. A page `Recut` writes is `Plain`
when every row put in it was. A first version decided it in `pageOut`, a
row at a time: `vte-scrolling`, 2,666,667 one-character lines, cost 9.9%
more instructions, then 3.0% and 1.5% with cheaper tests, which is why it
waits for a resize.

**The ring's reflow.** Profiled after it, the 10,000-row line's resize was
three quarters the ring's own reflow (`reflowCols`), and half of that
`markAt`, which made the array of marks found again for every cell of the
line (the cursor and the saved cursor, two or three). It now does so only
for a cell a mark is on: the line's resize 2.05 to 1.3 ms, and 10,000
short lines' 1.45 to 1.25 ms, and to 1.2 and 1.1 with the marks tested in a
loop rather than by `Array.any`, whose closure was a call a cell.

**Against Ghostty**, compared as §VC32 says (neither with a limit, the
dumps the same byte for byte after the 20 resizes, a resize's time over
the rows it reflows), three runs, the median:

| input | core, a resize | Ghostty, a resize | core, ns a row | Ghostty, ns a row | core ÷ Ghostty | before V22 |
|---|---:|---:|---:|---:|---:|---:|
| one line, 10,000 rows | 1.20 ms | 0.47 ms | 80 | 31 | 2.6 | 10.8 |
| one line, 100,000 rows | 3.25 ms | 8.65 ms | 22 | 58 | 0.38 | 4.0 |
| 10,000 short lines | 1.10 ms | 0.81 ms | 111 | 81 | 1.37 | 2.8 |
| 100,000 short lines | 4.25 ms | 18.6 ms | 43 | 186 | 0.23 | 0.72 |
| `gitlog.txt` | 69.6 ms | 115 ms | 126 | 207 | 0.61 | 0.61 |

The long line is now faster than Ghostty's at 100,000 rows. What is left
at 10,000 rows, and of the short lines', is the ring's reflow, about a
millisecond a resize whatever the scrollback holds: its rows are cells in
arrays, cut a cell at a time (`splitLine`), and §VC30 left them so. The
short lines gain because their pages are plain too, a line a span.
`gitlog`'s pages are not plain, since its lines have color, and it is cut
as before.

**With the default limit** (4.05 MB, §VC32), `drag 20 80 50`, the dumps the
same as 6ea1ecd's: the long line of 10,000 rows 105 to 28 ms, of 100,000
rows 207 to 24, 10,000 short lines 49 to 22, 100,000 short lines 212 to
69, `gitlog` 263 to 244.

**The speed targets.** Instructions against 6ea1ecd: −0.40% to +0.02% on
the thirteen inputs (against the build before V20, −1.02% to +0.01%).
Times, five runs after a warm-up, against the build before V20 in the same
session: as at 6ea1ecd, all inside their budgets, `gitlog` 102–105 ms
against 97–99 (budget 132) and `vte-scrolling` 40–43 against 40–41 (budget
42), the rest level.

**The fuzzers found a bug.** The first runs on V22, the recorded
differential run (the row of 19:53) and the self-fuzzer beside it, one
hour each, ran 590,135 and 423,235 inputs. The differential run found
no difference. The self-fuzzer found six inputs where the pages cut on
their bytes differ from the reflow of their rows (§VC31's check). All six
were one bug. When the pages end inside a line, every row of it wraps and
none has its empty cells trimmed. `plainSpans` answered the start of the
last row as 0 there, the offset it begins a new page at, so `plainLine`
trimmed the empty cells off the whole of the last page's part. Minimized,
the input is one wide character repeated at one column, which writes rows
of empty cells. It shows in an ordinary resize too: `中\e[2000b` at 1 by 1,
widened to 3, lost 85 rows of history and the wrap of the last, where
Ghostty keeps them. The pages now end such a line at the last span's end,
and nothing is trimmed. The replay case `resize-cols-plain-blank-line`
holds it, and it fails without the fix.

On the fixed build, every saved input passes both fuzzers: the
differential run's 12,760 seeds, corpus and findings, and the
self-fuzzer's 6,288, the six inputs among them. The two fuzzers then ran an
hour again, side by side (the diff-runs.tsv row of 21:19). The
differential run, on 16 jobs, ran 568,853 inputs, and the self-fuzzer, on 8
jobs, ran 332,295. Neither found a crash or a difference. The 41 inputs
the differential run wrote as slow or timed out, 1.2 to 4.0 KB with 53 to
2,309 resizes each, are §VC32's kind, many rows of few bytes reflowed at
every resize. They are not saved as findings.

After it: replay 324 of 324, esctest2 392 (Ghostty 388), and the five
inputs of the comparison above still the same as Ghostty's byte for byte.

## VC34. A check on the core's speed

Replay, esctest2 and the fuzzers hold the core to what it does, and nothing
held it to how fast it does it: each speed figure in this document was
measured by hand for the change it describes. Gilbert asked for a check.

**What it counts.** `harness/perf.py` counts user-space instructions
(`perf stat -e instructions:u`) for two kinds of case:

- **Throughput:** the thirteen inputs of §VC7, `core-bench FILE`.
- **Resizes:** `core-bench FILE resizes 20 80 50 [BYTES]`, a new mode that
  is the drag without the read. It is counted less `resizes 0`, which is
  the feeding alone, so the count is the twenty resizes' own. The five
  inputs are §VC31's, each with the default limit and with none, as §VC32
  compares with Ghostty.

`drag` itself would not do: its read of the whole scrollback is most of
its count (for the 10,000-row line, 187 ms of reading against 25 ms of
resizing), and would hide a resize that doubled.

**Why instructions, and with randomization off.** Times vary by a few
percent from run to run (`vte-scrolling` 40 to 43 ms), and so did the
counts at first: twenty resizes of the 10,000-row line counted 675 M to
703 M. One GC marker thread (`GC_MARKERS=1`) did not settle them. With
address-space randomization off (`setarch -R`), they repeat to within 20
instructions of 686 M, and every case of a second run is 0.00% from the
first. The randomized layout of the heap, which Boehm's collector walks,
was the variation.

**The record.** `corpus/perf/baseline.tsv` holds each case's count and
its input's SHA-256, so a changed input is an error and not a comparison.
A count more than 1% over its record fails a throughput case, and more
than 3% fails a resize case (`--tolerance` changes both). A count that
far under its record is reported, to be recorded with `--update`, so that
a gain does not hide a later loss. Each throughput case is also timed as
§VC7 times it, one untimed run and then the least of five, against
`geng-plan.md` §1.4's budget. That half needs a quiet machine, and
`--no-times` leaves it out. The counts take about five seconds, and the
times about a minute.

**The inputs.** The thirteen throughput inputs are not generated: the ten
of vtebench are a pty's capture (`probes/throughput/gen-vtebench.py`).
`--inputs DIR` copies them into `.harness-work/perf/inputs` once, and the
recorded hashes are those of the copies every measurement in this document
used. The resize inputs are written by the script, and `gitlog` is the
throughput one.

**It fails when it should.** With V22's cut switched off (`plainSpans`
never tried), the eight resize cases of plain lines failed, 13% to 459%
over their record (the 100,000-row line without a limit, 896 M to 5,005 M).
The same build counted `gitlog`'s resizes 3.5% and 3.9% *under* the
record. V22 costs a resize of lines that are not plain that much, which
is left for the next change to look at.

**At 9731647**, all within their budgets:

| input | budget | ms, least–most of five |
|---|---:|---:|
| `cup` | 56 | 49–51 |
| `gitlog` | 132 | 95–97 |
| `ls` | 124 | 76–79 |
| vte-cursor_motion | 28 | 23–24 |
| vte-dense_cells | 28 | 20–22 |
| vte-light_cells | 24 | 8–9 |
| vte-scrolling | 42 | 40–43 |
| vte-scrolling_bottom_region | 37 | 24–26 |
| vte-scrolling_bottom_small_region | 132 | 25–26 |
| vte-scrolling_fullscreen | 45 | 23–25 |
| vte-scrolling_top_region | 223 | 25–26 |
| vte-scrolling_top_small_region | 125 | 26 |
| vte-unicode | 25 | 16–17 |

`vte-scrolling` is the closest, at 40 ms against 42 as its least run, and
its most is over. The least of five is what the budget is held to.

**When to run it.** Run it before committing a change to `vt/src`, on a
quiet machine. A count that moves is explained in the commit that moves
it, and recorded with `--update` in the same commit.

## VC35. The ring's rows cut as slices, and made with `Builder.repeat`

§VC33 left "about a millisecond a resize whatever the scrollback holds":
the ring's reflow (`reflowCols`), whose rows are cells in arrays, cut a
cell at a time. Two changes take it to about half.

**A row cut as a slice.** `splitAt`, which cuts a line of the ring into
rows of the new width, pushed each cell onto the row it was making. A row
with no wide character in it and no mark (the cursor, the saved cursor)
on it or on the cell after it is the same as `Array.slice` of the line, so
it is now cut so, and only the other rows are cut a cell at a time
(`splitCell`, the old body). 50 full rows at 80 by 50 went from 3.9 M
instructions a resize to 0.95 M, 500 short lines from 13.2 M to 3.3 M.

**The ring made with `Builder.repeat`.** `newScreen` made the ring, `rows
+ 513` rows of `cols + 1` cells, as `Builder.fromArray (Array.repeat n
0)`: the array, then the builder's copy of it at its first write. geng-lang
added `Builder.repeat` to `core` for it (its D1025, `m4-puritty.md`
§VA58), which makes the builder alone. In instructions it looks worse on
the larger inputs (4.2 M a resize on 1,000 short lines against 3.7 M),
because the copies it saves are `memcpy` and `memset`, which count as one
instruction whatever their length. Timed, it is better everywhere, and the
collector runs less (46 times in 400 resizes of the 1,000 lines, against
79).

`core-bench FILE resizes N 80 50`, the least of eight runs, the three
builds interleaved; "before" is c30d54d:

| input | resizes | before | slice | slice and `repeat` |
|---|---:|---:|---:|---:|
| empty | 2000 | 49 ms | 49 | 30 |
| 50 full rows | 2000 | 301 | 116 | 67 |
| 1,000 short lines | 400 | 195 | 57 | 42 |
| one line of 500 rows | 400 | 240 | 76 | 57 |
| 10,000 short lines | 100 | 91 | 57 | 52 |
| one line of 10,000 rows | 100 | 81 | 42 | 39 |
| `gitlog.txt` | 100 | 1,254 | 1,249 | 1,211 |

A full screen's resize is 34 µs, from 150.

**Against Ghostty**, compared as §VC32 says, five runs, the median, and
the dumps after the 20 resizes still the same as Ghostty's byte for byte
on all five:

| input | core, a resize | Ghostty, a resize | core, ns a row | Ghostty, ns a row | core ÷ Ghostty | §VC33 |
|---|---:|---:|---:|---:|---:|---:|
| one line, 10,000 rows | 0.65 ms | 0.48 ms | 43 | 32 | 1.35 | 2.6 |
| one line, 100,000 rows | 2.90 ms | 8.65 ms | 19 | 58 | 0.34 | 0.38 |
| 10,000 short lines | 0.60 ms | 0.84 ms | 60 | 84 | 0.72 | 1.37 |
| 100,000 short lines | 4.05 ms | 18.6 ms | 41 | 185 | 0.22 | 0.23 |
| `gitlog.txt` | 72.4 ms | 114 ms | 131 | 206 | 0.64 | 0.61 |

The core is now faster than Ghostty's on 10,000 short lines too, and
only the 10,000-row line is slower, by a third. `gitlog`, whose lines have color
and so are not plain, is where it was: §VC34's note on what V22 costs
such lines stands.

**`perf.py`.** The resize cases' counts fall 15% to 64% (the 10,000-row
line 516 M to 185 M, 10,000 short lines 486 M to 242 M), the 100,000
short lines without a limit 4.7%, and `gitlog` 0.6% and 2.5%. Recorded
with `--update`; the throughput counts move by under 0.5% and are
recorded with them. All thirteen inputs within their budgets, as before
(`vte-scrolling` 41–42 ms against 42).

**The fuzzers.** The slice path ran an hour under both, side by side (the
diff-runs.tsv row of 03:37, 559,286 inputs, and the self-fuzzer on 8
jobs): no crash and no difference; the 43 inputs the differential run
wrote as slow or timed out are §VC32's kind, as before. Rebuilt with
`Builder.repeat`, every saved input passes both: the differential run's
13,066 and the self-fuzzer's 14,634.

After it: replay 324 of 324, esctest2 392 (Ghostty 388).

## VC36. Why the 10,000-row line trailed Ghostty: the heap's growth

§VC35 left one input slower than Ghostty's, the line of 10,000 rows, at
1.35 times its time over 20 resizes. Gilbert asked why. It is the first
resizes of a process, not the resize. Each resize after the first 20 costs
0.31 ms of user time against Ghostty's 0.35, and at 100 resizes the totals
are level, 41 ms each. The first 20 pay for the collector's small heap:
about 10 full collections of 0.5 ms, where later resizes need one every
other resize, and 7,400 page faults as the heap grows from 8 MB to 33 MB.
A heap that starts at 32 MB has the same faults and 4 collections, and
takes 3 ms off the 20 (`m4-free.md` §FR10). Each resize builds a new ring and new pages and
leaves the old ones for the collector, 2.1 MB a resize on this input,
where Ghostty's reflow hands each old page straight to the next new one.

geng-lang's `m4-free.md` measures it. The resize's dead buffers, freed by
hand at the point an ownership proof would free them, take the 20 resizes
from 16 ms to 11 (Ghostty 10.4) and the 100 from 46 to 33 (Ghostty 42),
with the same dumps on all five inputs. `gitlog` does not move, since its
time is the cut of colored lines (§VC34). Nothing in the core changed.

**How resizes are compared with Ghostty from now on** (geng-lang D1029):
as §VC32 says, and reported as two numbers, the first 20 resizes of a
process and the cost of a resize after them, so that the collector's
start-up and the resize's own cost are not one figure.

### What is left

geng-lang decided (`m4-free.md` §FR9) that a builder's buffer is freed
where the ownership checker sees the builder dropped (D1026), and that the
core's pages hold their bytes affinely after it (D1027), which is the
change on puritty's side: a survey first of what reads a page and whether
each read can borrow. Two costs it found are registered here (D1030), for
after those, since what a resize allocates changes once the pages are
owned:

- **The rows between the old ring and the new.** `flowFrom` makes an array
  a row (`ringRowOf`), `splitLine` makes them again at the new width, and
  `rebuild` copies them into the new ring; the nursery promotes 22 MB of
  them in 20 resizes of the 10,000-row line. Rows written straight from the
  old ring into the new would not be allocated.
- **`gitlog`'s cut of colored lines**, 73 ms a resize of 542,000 rows
  without a limit, all of it work (§VC34's note on what V22 costs lines
  that are not plain).

## VC37. The old screen freed at a resize (geng-lang D1026)

geng-lang built D1026 (`m4-free.md` §FR11): native's last pass, `drop`,
gives a builder's buffer back to the allocator where a record holding it is
read for the last time and nothing else can reach it. The harness's builds
(`bench`, `dump`, `esctest`, `fuzz`) name `drop` in their passes.

**What it drops in the core.** `resizeTo`'s screens: `active` (and `main`
and `alt` with the alternate screen shown) is the old screen, taken out of
the term by `settle`, which `resizeScreen` only reads; it is freed once the
new screen is made, 20 buffers and 10.9 MB over 20 resizes on every input,
§VC36's ring. `reset` frees the old term's builders whole, RIS keeping none
of them. Nothing on the output path is dropped, and the thirteen
throughput counts do not move.

**The pages are not**: their text is `Bytes`, which no pass can show is the
pages' alone, and `Back.pages` is a buffer of pointers, which the runtime
does not give back. D1027 holds them affinely.

**Resizes**, `core-bench FILE resizes N 80 50 2000000000`, the median of
nine (five for the large inputs), before and after interleaved, reported as
D1029 asks:

| input | first 20 resizes, before | after | each of the next 80, before | after |
|---|---:|---:|---:|---:|
| one line of 10,000 rows | 15 ms | 12 | 0.33 ms | 0.35 |
| 10,000 short lines | 12 | 12 | 0.50 | 0.46 |

The 100,000-row line and 100,000 short lines are level over 20 resizes (57
and 81 ms against 57 and 82).

**`perf.py`.** The resize cases move both ways: 10,000 short lines +7.7%,
the 10,000-row line +3.2%, the 100,000-row line −5.1% and −7.6%, the rest
within 1.2%. Under callgrind the drop itself is 0.2 M instructions over 20
resizes of the short lines (`GC_freehblk`); the +18 M is the collector's
marking, as many collections at other moments (three each), and on the
10,000-row line two more of them. A freed block changes when Boehm next
collects, and an instruction count counts the marking (§VC35's lesson that
counts are not times holds the other way too). Recorded with `--update`;
all thirteen inputs inside their budgets.

**The fuzzers**, 20 minutes each, side by side. The differential run, on
12 jobs, ran 86,018 inputs with no finding. The self-fuzzer, on 4, spent the
run loading its corpus: libFuzzer's fork mode runs every saved input once
to merge them, 59,905 here into 7,845, with no crash, timeout or OOM, and
then ran 89. 600 of the saved inputs take 19.2 s with `drop` and without
it, so the time is the corpus's size and not the drops; a smaller corpus,
or `-runs=0` over it, is the way to a longer search next time.

After it: replay 324 of 324, esctest2 392 (Ghostty 388).

## VC38. ED 3 forgot what the pages held

geng-lang's rewrite of the pages for `Bytes.Owned` (`m4-owned-pages.md`
§OP15) found it, and it is older than that work. `clearScrollback` (ED 3)
emptied `Back.pages` but left `Back.bytes` and `rows` as they were. With a
full scrollback, every page pushed after ED 3 was then over the limit as
`dropOver` counts it, and dropped as soon as it was made: on `core-dump`,
20×5 with a 12,000-byte limit, 3,000 lines, ED 3 and 1,500 more kept 476
rows of scrollback, where the 1,500 alone keep 1,500. `rows` was wrong
too, so `historyBound` counted rows that were gone.

ED 3 now sets both to 0, as `backOf` does when a resize leaves no pages.
`peak` and `dropped` stay, as §VC25 has them.

The replay case `scrollback-erase-3-limit`, seeded from Ghostty, fills the
default limit in one column (26,000 cells, each wrapping onto its own row),
erases with ED 3 and writes 2,000 more. Ghostty and the core now keep all
of them. The core before the fix kept 464.

After it: replay 325 of 325, esctest2 392.

## VC39. The pages hold owned bytes (geng-lang D1027, D1031, D1035)

A page is now `{ text, heads, runs : Bytes.Owned, cols, plain }`.
`Bytes.Owned` is geng-lang's affine, read-only bytes (`m4-owned-pages.md`
§OP6, D1031), and the compiler frees one where the ownership checker sees
it dropped (D1032). Before, a page held `Bytes`, which only the collector
gives back. geng-lang's `m4-owned-pages.md` §OP15 and §OP18 have the
rewrite's design and the two compiler fixes it waited on (D1036, D1037).

**What changed.**

- `pageOut` makes each field with `Owned.fromBuilder`, one copy, as
  `Bytes.fromUInt8s` did. `pushPage`, `backOf` and `dropOver` read a page's
  sizes before they move it.
- A resize takes the pages out of the scrollback (`takePages`) and keeps
  the rest of `Back` apart (`withoutPages`). If the width changes,
  `recutPages` only reads them, and the `let` that binds the cut is the
  last use of the old pages, where they are dropped. If it does not,
  `keepPages` keeps all but the ones taken back into the ring. `compact`
  moves its slots through an array (`Builder.toArray`, `Array.dropFirst`,
  `Builder.fromArray`), and `pagesOf`'s copy of the builder is gone.
- `recut` reads the old pages where they are, lent. A range of a page is
  copied into the new page's builder with `Owned.appendTo`, plain row or
  not, so `Out.pieces`, `pend`, `Bytes.flatten` and `copyRange`'s loop of
  one byte at a time are gone. A span and the chunk source hold a page's
  index, not its bytes.
- A page's plainness is a question, `plainPage`, not a field `recut`
  writes back into the old page (`settlePlain`). `recut` asks it once a page
  into an `Array Bool`; the pages it writes carry their own.
- `popLast` shortens the last new page by copying its kept rows into a page
  of their own, since `Array.popLast` may keep an element twice and is
  refused for affine ones.
- `Dump`, `Vt.recutHolds` and the pull of rows back into the ring read the
  scrollback through `readBack`, a loop over its slots. `Vt.recutHolds`
  cuts copies (`copyPages`). Both are loops, not folds with a function,
  for §VC12's reason: a part of the term handed to a function value is
  kept for all the program's in-place updates.

**It answers what 60a4d07 answers.** Replay 325 of 325. esctest2 392, as
recorded. The dumps are the same hash as 60a4d07's on 153 of 153: the 17
perf inputs, each resized nine ways. The fuzzers: `fuzz.py --diff`, 24
jobs for 600 s (876 s with start-up), coverage 6,269; the core's own, 24
jobs for 600 s (1,759 s), coverage 6,145. Neither found anything.

**Instructions** (`perf.py`, recorded with `--update`). Every resize count
is lower than the record, which an older compiler made:

| resize, 20 less the feed | record | now |
|---|---:|---:|
| one line of 10,000 rows | 190.4 M | 149.4 M |
| 10,000 short lines | 261.0 M | 227.5 M |
| one line of 100,000 rows | 217.0 M | 195.0 M |
| …unlimited | 702.2 M | 656.1 M |
| 100,000 short lines | 1,356.8 M | 1,279.9 M |
| …unlimited | 1,960.4 M | 1,783.7 M |
| `gitlog` | 6,561.2 M | 5,219.2 M |
| …unlimited | 38,251.8 M | 30,684.7 M |

Against 60a4d07 built with today's compiler (`m4-owned-pages.md` §OP18),
10,000 short lines is the one that rises, 220 M to 227 M; why was not
measured. The
throughput inputs move by at most 0.7%: `vte-scrolling` +0.67%
(1,428.6 M to 1,438.2 M) and `gitlog` +0.14% go up, `ls` −0.43% and
`vte-scrolling_fullscreen` −0.50% go down, and the rest are level. The
record keeps the new counts, and every time is within its budget.

**Time** (D1029, §VC36's two numbers). 60a4d07 and the rewrite built with
the same compiler (the fork at 9cb38c60), `resizes N 80 50
2000000000`, no limit: the median of seven of `core-bench`'s own time;
Ghostty's is `gdrag FILE N 80 50 0 0`, the median of seven. The first 20,
then each resize after them as (time at 100 − time at 20) / 80:

| input | 60a4d07: 20 / each after | rewrite | Ghostty |
|---|---:|---:|---:|
| one line of 10,000 rows | 15 ms / 0.26 | 9 / 0.25 | 9.1 / 0.42 |
| 10,000 short lines | 11 / 0.44 | 10 / 0.44 | 14.8 / 0.74 |
| one line of 100,000 rows | 56 / 2.45 | 42 / 1.91 | 174 / 8.6 |
| 100,000 short lines | 72 / 3.4 | 68 / 3.3 | 369 / 18.6 |
| `gitlog` | 1,372 / 71 | 1,084 / 54 | 2,276 / 114 |

The 10,000-row line, which §VC36 found trailing Ghostty over the first 20
resizes, is now level with it (9 ms against 9.1). Where the time goes,
user and system time and page faults net of the feed, and full collections
(`perf stat -r 5`, `GC_PRINT_STATS`):

| input, resizes | user | system | faults | full collections |
|---|---:|---:|---:|---:|
| 10,000-row line, 20 | 7.9 → 6.3 ms | 5.1 → 2.6 | 7,075 → 3,517 | 10 → 7 |
| 10,000-row line, 100 | 31.1 → 26.0 | 5.0 → 4.8 | 7,560 → 5,207 | 30 → 19 |
| 10,000 short lines, 20 | 7.4 → 9.6 | 4.1 → 0.9 | 4,572 → 2,455 | 1 → 1 |
| 100,000-row line, 100 | 233.9 → 195.1 | 21.2 → 3.2 | 25,556 → 5,823 | 83 → 26 |
| 100,000 short lines, 100 | 340.5 → 331.9 | 7.8 → 2.6 | 8,321 → 2,979 | 53 → 15 |
| `gitlog`, 20 | 1,417 → 1,072 | 14.2 → 11.9 | 22,677 → 13,912 | 16 → 4 |

The old pages are dropped where the resize binds its cut, so the heap is
reused, not grown: faults and full collections fall on every input. The
10,000 short lines spend more user time, as their instructions say, and
win it back in system time. `gitlog`'s time is the cut of colored lines
(§VC34), whose ranges were copied a byte at a time and are now one
`appendTo` each; how much of its 21% that is was not measured apart from
the drops.

**The heap after a feed** at the default limit (4 MB), `GC_PRINT_STATS=1
core-bench gitlog.txt resizes 0 80 50`: 3 full collections and a last
growth to 49,968 KB, the same as 60a4d07 (§OP5's numbers), with 34 MB in
use at the last collection. The feed does not free pages yet: `dropOver`
writes over the oldest page with `Builder.set`, which drops nothing (§OP18).
Most of that heap is `core-bench`'s input, which it holds through the feed
(25 MB of `gitlog.txt`); the terminal's share is about 9 MB. geng-lang
leaves the page to the collector (`m4-owned-pages.md` §OP20, D1040):
taking it out with `Builder.swap` costs the in-place marks 312 → 29.

## VC40. D1030's two costs, measured after the owned pages (survey)

geng-lang's D1030 registered two costs of a resize here (§VC36), for after
the pages were owned (§VC39): `gitlog`'s cut of colored lines, and the
rows between the old ring and the new. This measures both on puritty
9496e75's core, against Ghostty, and says what each would buy.

**Where a resize goes.** A scratch build adds `Vt.probe`, which runs one
part of a narrowing to 80 columns on the term a feed left, with no limit.
Instructions are a part run 10 times, less the feed, divided by 10; the
time is the median of five runs of 100.

| input | one resize | the recut of the pages | the ring's rows (flow and rebuild) |
|---|---:|---:|---:|
| one line of 10,000 rows | 18 M | 5 M, 0.38 ms | 8 M, 0.38 ms |
| 10,000 short lines | | 10 M, 0.39 ms | 4 M, 0.15 ms |
| one line of 100,000 rows | | 48 M, 3.6 ms | 7 M, 0.31 ms |
| 100,000 short lines | | 101 M | 1 M |
| `gitlog` | 1,545 M | 1,558 M (the copy the probe makes, 32 M, in it) | 1 M |

So `gitlog`'s resize is its recut, and the ring's rows are about half of
the 10,000-row line's and little elsewhere.

**Against Ghostty** (§VC39, D1029's two numbers): `gitlog` is 1,084 ms for
the first 20 against Ghostty's 2,276, and 54 ms a resize after them
against 114. The 10,000-row line is 9 ms against 9.1, and 0.25 ms a resize
after them against 0.42. Neither cost leaves the core behind Ghostty.

### `gitlog`'s cut

Its lines are colored, so they are not on plain pages (V22, §VC33), and
each goes through `gather` and `fastLine`. Sampled by instructions
(`perf record -e instructions:u`, the recut 5 times), per resize: `chunks`
406 M (with `skipCells` and `styleCells` in it), `recut` 354 M (with
`lines`, `gather` and `fastLine` in it), `scan` 210 M, `decodeAt` 49 M.

Each byte of a colored row is walked twice: by `scan` in `gather`, to find
where the row's text ends and whether every cell is one column, and by
`skipCells` in `chunks`, to find where each new row's text ends. `chunks`
already finds the end by arithmetic for a row with a byte a cell, but only
when the row also has no style: one field, `Src.plain`, says both.

- **A. Split `Src.plain`.** A new field, `narrow`, true when a row's text
  is as many bytes as its extent, decides where a row's text ends;
  `plain` still decides the new page's plainness. A row reaches `fastLine`
  only when `scan` found every cell one column, so a byte a cell means
  every byte is a cell's: ASCII or an empty cell's 0, with no protection
  byte, which would be one more byte. Built in the scratch copy: `gitlog`'s
  recut is 1,328 M (−15%), `ls`'s 830 M, 100,000 short lines unchanged.
  `gitlog`'s 20 resizes take 982 ms (1,090), and each after them 49.0 ms
  (54.7). The dumps are the same as 9496e75's on 153 of 153. The change is
  about ten lines in `Recut`.
- **B. A row header bit for "a byte a cell"** (`0x1000` and `0x2000` are
  free), written by `packRows` and by `closeRow`, would let `gather` skip
  `scan` too: at most its 210 M and `decodeAt`'s 49 M, 17% more. It
  changes what a page holds, and a row-at-a-time decision in `pageOut` is
  what §VC33 measured at 1.5% to 9.9% more instructions on
  `vte-scrolling`. Output pays it on every page, so a resize can save it.

The rest, about 1,070 M after A and B, is a row's own work: a `Source`
record pushed to an array, `fastLine`'s fold, two `chunks` calls, the
style runs and the header written a `pushU16` at a time, about 2,000
instructions a row over 542,000 rows.

### The ring's rows

`flowFrom` makes a row of each of the ring's (`ringRowOf`, a slice of the
cells), `reflowCols` and `changeRows` make them again at the new width
(`splitLine`), and `rebuild` writes them into the new ring. On the
10,000-row line, 20 resizes now promote 19.4 MB from the nursery (22 MB
before the pages were owned) and allocate 72 MB of large arrays, and the
heap ends at 16.8 MB (33 MB before; `GENG_NURSERY_STATS`).

- **C. Write the rows straight from the old ring into the new.** It is the
  allocation D1030 named. It would replace `flowFrom`, `reflowCols`,
  `changeRows` and `rebuild`'s use of `Array Row`. That is the reflow V10,
  V16 and V17 are held to, with the cursor, the saved cursor, the prompt's
  rows and the marks carried through it. The most it saves is the ring's
  part, 0.38 ms of a narrowing on the 10,000-row line and 0.15 to 0.31 ms
  on the others, where the core is already level with Ghostty or ahead.

### For Gilbert

1. **A, now?** Leaning yes. It is small, local and measured: 10% off
   `gitlog`'s resizes, the dumps the same. It would land with replay,
   esctest2, the dumps, the fuzzers and `perf.py`.
2. **B?** Leaning no for now. It saves at most 17% of `gitlog`'s recut,
   and it costs output on every page, where §VC33 already measured such a
   cost and moved the decision out of `pageOut` for it. Registered with
   these numbers.
3. **C?** Leaning no. It would rewrite the reflow the core's resize
   correctness rests on, to save at most 0.4 ms a resize where the core
   is not behind. Registered with these numbers, and D1030 closed with
   them.

**Answered** (2026-11-01): all three leanings. A is built (§VC41). B and C
are registered here with the numbers above, and D1030 is closed.

**Reopened only on a measurement** (2026-11-02, with Gilbert). B when a
resize benchmark puts the core behind Ghostty, or when another use of a
header bit makes output pay the row-at-a-time decision anyway. C when a
resize's collections miss G7's pause budget, since the ring's rows are
the allocation D1030 named.

## VC41. A colored row with a byte a cell is cut by arithmetic (§VC40's A)

`Recut`'s `Src` has a fourth field, `narrow`: the row's text is as many
bytes as its extent. `chunks` finds where a new row's text ends by
arithmetic when it is set. Before, it did so only when the row was also
unstyled, since `plain` decided both; `plain` still decides whether the
page written is plain. A row reaches `fastLine` only when `scan` found
every cell one column wide, so a byte a cell means each byte is a cell's:
ASCII, or an empty cell's 0, with no protection byte.

**Held.** Replay 325 of 325, esctest2 392, the dumps the same as 60a4d07's
on 153 of 153. `fuzz.py --diff`, 24 jobs for 600 s, coverage 6,269, and
the core's own, coverage 6,147: nothing found.

**Instructions** (`perf.py`, recorded): `gitlog`'s 20 resizes 5,219 M →
4,376 M (−16%), and 30,685 M → 26,104 M without a limit (−15%). The
10,000-row line 149.4 M → 142.6 M (−4.5%). Throughput does not move. Four
resize counts rise by 0.2% to 1.3%: the line of 100,000 rows without a
limit 656.1 M → 664.8 M, and 10,000 and 100,000 short lines by 0.2% to
0.35%. Their lines are plain, so they gain nothing, and they build the
wider `Src` all the same.

**Time**, the median of seven of `core-bench FILE resizes N 80 50
2000000000`, against 7e99431 built with the same compiler: the first 20,
then each resize after them:

| input | before | after | Ghostty (§VC39) |
|---|---:|---:|---:|
| `gitlog` | 1,088 ms / 53.9 | 964 / 48.1 | 2,276 / 114 |
| `ls` | 705 / 34.8 | 529 / 26.1 | |
| one line of 10,000 rows | 9 / 0.26 | 9 / 0.26 | 9.1 / 0.42 |

`ls` gains the most because its colored names are ASCII. Every time is
within its budget.

## VC42. The page a push drops is freed (geng-lang D1041)

geng-lang's drop pass now follows a call of `Builder.set` over owned
elements with a drop of the element it writes over (`m4-owned-pages.md`
§OP22). So the oldest page `dropOver` writes over with an empty one is
given back where it is dropped, as §VC39 left for later. Nothing in the
core changed.

Replay 325 of 325, esctest2 392, the dumps the same on 153 of 153, both
fuzzers clean. The feed at the default limit, before → after:

| input | peak resident | page faults | full collections |
|---|---:|---:|---:|
| `gitlog` | 57,672 → 41,792 KB | 7,782 → 3,833 | 3 → 2 |
| `ls` | 50,644 → 38,372 KB | 6,438 → 3,331 | 4 → 2 |

Less the input `core-bench` holds, the terminal's own part of `gitlog`'s
peak is about half what it was, 32 MB to 16. Feeding times do not move.
`perf.py` records `ls`'s feed 1.0% and `gitlog`'s 0.65% lower, and every
time is within its budget.

## VC43. Where `vte-scrolling`'s last milliseconds go (survey)

geng-lang's register still had the core over D902 on eight inputs of
thirteen, a number from the probe. Measured again on b912f76
(`harness/perf.py`): all thirteen meet the budget on the least of five, and
`vte-scrolling` is the one with no room, 40–42 ms against 42, and over 40
runs 40 least, 42 median, 45 most. It has been there since §VC34. The next
nearest is `vte-cursor_motion`, 24 against 28. This finds where the core
spends more than the probe did.

**The probe, built today.** `probes/geng/core` with the same compiler
(geng-lang `bench/compare`, its §VA48 spec): 1,284 M instructions, 481 a
line, 36–38 ms. The core is 1,439.5 M, 540 a line: 155 M, 58 a line, more.

**Which work it is.** `vte-scrolling` is 2,666,667 lines of `y` CR LF.
`probes/throughput/vc43/inputs.py` writes inputs that do one kind of that
work each, the same number of times:

| input | probe | core | core − probe, a time |
|---|---:|---:|---:|
| none | 1.2 M | 1.0 M | |
| CR | 65.2 M | 75.7 M | 3.9 |
| LF (a scroll at the bottom) | 681.8 M | 682.8 M | 0.4 |
| CR LF | 747.1 M | 764.2 M | 6.4 |
| `y` CR (one cell written over) | 471.9 M | 724.7 M | 94.8 |
| `y` CR LF (`vte-scrolling`) | 1,284.1 M | 1,439.5 M | 58.3 |

The scroll, the ring and the pages cost what the probe's did. The gap is
the printing of one ASCII character: about 52 instructions more on a
cleared row, 91 on a row that already holds a cell there.

**What the print does that the probe's did not.** `ablate.sh` builds the
core with one edit from `vc43/edits/` and counts it; every edit leaves
`vte-scrolling`'s dump the same, but each takes a rule away, so none of them
is a candidate except `wrap`:

| edit | what it takes away | a line of `vte-scrolling` | `y` CR, a time |
|---|---|---:|---:|
| `noplain` | `ground`'s test of `plain` | −14.9 | −7.0 |
| `constcols` | the width read from the term and the screen, as the probe's constant 160 | −10.9 | −2.0 |
| `nostale` | the test for a wide character's head under column 0 or 1 (§VC17) | −9.9 | −6.0 |
| `nosplit` | the split of a wide character the run cuts (§VC17) | −8.0 | −75.0 |
| `nolast` | `lastPoint`, the character REP repeats | −4.0 | +1.0 |
| `noflags` | the row's flags kept beside its extent | −4.0 | −4.0 |
| `noautowrap` | `wrapped`'s test of `autowrap` | −2.0 | −2.0 |

They add to 54 of the 58. Most are larger than their work: one field test,
`plain`'s, is 15 instructions, and `heads`' test, false on this input,
10. What they cost is what they do to clang's code for `ground`'s loop, into
which `printAscii` and `asciiRow` are inlined, not the tests themselves.
The probe paid the same kind of cost for each layer it grew (geng-lang
`m4-puritty.md` §VA15).

**Two edits that keep every rule.**

- `fast`: `ground` sends a run to a copy of `printAscii` without the
  `stale` test until a spacer head has been written (`heads`). It is
  1,453.0 M, 13.5 M *more*, and `y` CR 20 a time more: the second copy in
  the loop costs more than the test it skips.
- `wrap`: `printAscii` tests `wrapNext` alone, since `plain` is only true
  with autowrap on (`withPlain`). 1,434.2 M, 2.0 a line less, the dump
  the same. About 0.15 ms.

**Layout and flags.** The same C compiled again (`compile.sh`, geng-lang
D1002), 31 runs each: as built 40–42 ms (median 41); `-falign-loops=64`
39–42 (40); `-falign-loops=32` 40–43 (41); `-O3` 1,467 M instructions,
44–45. A millisecond at most, and not one to rely on (geng-lang
`m4-puritty.md` §VA50).

**Where the rest of a line goes.** Of the 540: the scroll and its page,
about 256 (`lf` less the empty input, a line), of which writing the row into
a page (`packRows`, `pushUtf8`) is about 137; the print, about 253; CR,
about 28. The page's share is the probe's too (`packRows` and `pushRun`,
377 M against the core's 366).

### For Gilbert

1. **`wrap`?** Leaning yes: two instructions a line, no rule lost, the
   dumps the same. It would land with replay, esctest2, the dumps, the
   fuzzers and `perf.py --update`.
2. **The print's other costs** are the rules that make the core correct
   where the probe was not (wide characters, REP, row flags, any size).
   Leaning: keep them all, and no more rearranging for clang, which the
   `fast` edit shows can go either way.
3. **The margin.** Leaning: leave it. `perf.py` fails a change that takes
   `vte-scrolling` over 42 on the least of five, and that change is
   looked at then. If room is wanted before then, the page's 137
   instructions a line is the largest block the probe and the core share,
   and would be a survey of its own; registered here.

**Answered** (2026-11-02): all three leanings, and `wrap` built. It did
not hold: `perf.py` over every case found it 0.37% fewer on
`vte-scrolling` (1,434.2 M) and 0.5% fewer on the region scrolls, but
2.44% more on `vte-light_cells`, 2.63% more on `vte-unicode` and 5.44%
more on the 10,000-row line's resizes, the code-shape effect above
again. Replay, esctest2, the dumps and both fuzzers had passed with it.
It is not kept: the edit stays in `vc43/edits/` with these numbers, and
the survey's two inputs were too few to judge an edit to the print by.
Gilbert's remark: in the far future Geng might emit LLVM IR itself, which
could take such choices back from clang (geng-lang `open-items.md`, the
entry on clang's inlining).


## VC44. A fuzzer timeout: 470 resizes of a scrollback (2026-11-02)

The differential fuzzer for ten minutes on four jobs during phase 3
(`phase3-input.md`), `diff-runs.tsv`'s row for `bccdbcc+`, stopped one job
on libFuzzer's 10-second timeout. Its binaries were the ones built at 14:02
that day: `fuzz.py` does not build them, so that run fuzzed the core before
phase 3's changes to it (XTMODKEYS, `styleMax`). Rebuilt with them, the
input takes the same time.

**It is the reflow, linear and slow.** The input, 2,755 bytes, resizes the
terminal 470 times (the 0xFE triples), and `perf` puts 97% of its time in
`Vt.Resize.resizeScreen`: the pages pulled and recut at each width
(`pullPages`, `readPages`, `Recut.recut`, `Pages.unpackText`). It takes
7.7 s in `vt-diff`, which keeps the history it compares, and 1.6 s in
`vt-fuzz`, each under coverage instrumentation. §VC24's inputs, about 90
resizes, took 1.3–1.4 s in `vt-fuzz`; this one is 470 at about the same
cost each. Nothing in it differs between the core and Ghostty. The row
stays as recorded. Rebuilt, the fuzzer ran ten minutes more on four jobs
with phase 3's core and found nothing (the next row, coverage 6,305).

Not decided: whether the fuzzer should cap the resizes an input may make,
or the reflow should be cheaper per resize; a real window resizes once a
frame at most, and `phase2-window.md` §15.6's drag of `long-10000` costs
20–22 ms a resize.


## VC45. The rest of Vt.geng split into modules (2026-11-07)

§VC23 left 5,235 lines in `Vt.geng`, which had grown to 6,197 since: the
parser and everything its dispatch does, sections that "call each other
and would take a choice of seams of their own to split". Gilbert asked for
the file to be split.

**The seams.** A graph of which top-level definition names which (a
script over the source, not the compiler) found one cycle among the
250 definitions: the parser's states, sixteen functions, `feed`,
`ground`, `escape`, `csi`, `c1`, the string states and the two UTF-8
ones, which call each other because each returns to the ground state.
Every other definition is in no cycle, so a layering exists; the sections
did not give one as they stood, since a few helpers sat in the section
that used them first. Eleven modules, each importing those below it
`exposing (..)` as §VC23's do, and nine definitions moved to a section
lower than their own so that no module imports one above it (`of`,
`param`, `withPlain`, `slotSet` and `rowWrapped` to `Vt.Cursor`;
`historyBound`, `noteReach` and `freshLine` to `Vt.Scroll`; `fresh` to
`Vt.Modes`):

| step | module | what it holds | lines |
|---|---|---|---:|
| 1 | `Vt.Cursor` | the margins, the cursor's moves, the origin, the tab stops, and the small helpers above share | 553 |
| 2 | `Vt.Prompt` | the prompt marks of rows that OSC 133 sets (§VC22) | 135 |
| 3 | `Vt.Scroll` | line feeds, the scrolling regions, the term's resize | 505 |
| 4 | `Vt.Sgr` | SGR and the pen | 387 |
| 5 | `Vt.Edit` | inserting, deleting and erasing cells, and splitting the wide characters an edit cuts | 651 |
| 6 | `Vt.Modes` | the modes, DECSC and DECRC, the resets, and `fresh` | 691 |
| 7 | `Vt.Print` | printing through the character sets, the wrap, UTF-8's decoding | 628 |
| 8 | `Vt.Dcs` | DCS strings, DECRQSS | 276 |
| 9 | `Vt.Osc` | the OSC dispatch: colors, the clipboard, the semantic prompts | 511 |
| 10 | `Vt.Dispatch` | a CSI sequence's dispatch | 625 |
| 11 | `Vt.Parse` | the state machine, the cycle above | 883 |

`Vt.geng` is 893 lines: what it exposes, and `resize`, `keyOptions`,
`mouseModes` and `dump`, which nothing below needs. Two of its exposed
functions moved down, `feed` to `Vt.Parse` and `historyBound` to
`Vt.Scroll`, and `Vt` defines each as a call of the moved one, importing
the module qualified so the names do not clash; the other modules import
it `exposing` only the names `Vt` uses. The tab stops are in `Vt.Cursor`
rather than a module of 72 lines.

**Held as §VC23 held its steps.** Each step is a commit and a move of
definitions as they were, made by the same script from the same source,
and each was held to the build before it: the dump of every throughput
input the same, replay 325 of 325, and every count of `harness/perf.py
--no-times` within 0.1 M instructions of the build before the split
(`6c5f4f9`). Every count was the same to the 0.1 M `perf.py` prints, at
every step: clang sees one C file however the Geng is cut (§VC23).
After the last step, esctest2 392 passing, as at §VC23, and every other
program that builds the core builds (the app, `charset`, `esctest`,
`fuzz`, `keys`, `mouse`, `paste`, `pixels`, `select`, `view`).

**The self-fuzzer** (`fuzz.py`, eight jobs) on the split's tree, built with
the renamed compiler, found nothing in 237,030 inputs, coverage 6,490. Two
runs of the self-fuzzer and the differential fuzzer for two and ten minutes
first ran about 100 inputs each: libFuzzer merges the 59,905 saved inputs
before it fuzzes, one process, 25 to 35 minutes, and that counts against
the run's time. The run counted here was fifty minutes. The differential
fuzzer's ten-minute run ran 100 inputs, no finding, and is not counted.

**Found on the way.**

- `harness/fuzz/build.sh` did not build at `6c5f4f9`: it repeats
  `geng make`'s C step by hand, and geng-lang D1082 moved the runtime's
  system calls into `linux/geng_sys.c`, with `geng_platform.h` beside it.
  It now compiles and links that file with its directory on the include
  path, as `geng make` does (`4875096`).
- `harness/perf.py` fails at `6c5f4f9`, before the split, and the split
  does not move it: three resize cases are over their record,
  `short-10000` (default and unlimited) 349 M to 470 M, +35%, and
  `default/short-100000` 1,401 M to 1,476 M, +5%; `long-10000` is 13%
  under. Not looked into here; the record was last written at `18749a4`
  (2026-11-03), so the change came in since, in this repository, the
  compiler or `core`.


## VC46. Unit tests (2026-11-07)

The core was held to what it does only by gates against an oracle:
replay and esctest2 against Ghostty, the fuzzers, and the key, mouse,
paste and charset gates against libghostty-vt and WHATWG. Each is wide,
and none is a small case a person reads to learn what a function does,
nor runs in a second after an edit. Gilbert asked for checked-in unit
tests.

**Where they are.** `vt/tests/` is an application that depends on
`puritty-vt` by path and runs on node with `gren-unit-node`, as the
ported packages' suites do (geng-lang `harness/suites.py`). It reaches
only what `vt` exposes (`Vt`, `Vt.Keys`, `Vt.KeyTables`, `Vt.Mouse`, `Vt.Paste`,
`Vt.Base64`, `Vt.Charset`), which is what the app uses, so the tests
hold the interface and not the modules of §VC45. `vt/tests/run.sh`
builds it with the passes the core is built with everywhere else and
runs it; its arguments are the runner's.

| suite | what it holds | tests |
|---|---|---:|
| `Feed` | printing, the cursor, the pending wrap, wide characters, CR at a left margin, EL, ED, ICH and DCH, SGR, a scrolling region, the alternate screen, the scrollback, a resize's reflow, read through `Vt.dump` (§VC3) | 19 |
| `Resume` | ten inputs, each fed in two reads split at every byte, give the dump of one read: SGR, CUP and ED, OSC ended both ways, UTF-8 of every length, DEC graphics, DECRQSS, DSR, the alternate screen, a region, a wrap | 10 |
| `Select` | `selectionText` across a wrap, in either order, without a line's trailing blanks, a wide character once; `wordAt` at a boundary, on one, across a wrap; `lineAt`; `rowsPushed` and `scrollbackRows`; `promptJump` up and down | 12 |
| `Replies` | DSR 5 and 6, replies oldest first and a take emptying them, OSC 52 with BEL and ST and refused when not Base64, `keyOptions`, `mouseModes` | 8 |
| `Encoders` | keys (Enter, Tab, Escape, Backspace and DECBKM, an arrow in both cursor modes and with ctrl, F1, shift+Tab, ctrl+c, alt's ESC, a release, kitty's CSI u), the mouse in SGR and X10, paste with and without brackets and its controls, Base64's RFC 4648 vectors and refusals, EUC-KR both ways and across reads | 19 |

Each expectation was written from the specification, the module's own
documentation or a replay case Ghostty agrees with (CUP), before the
tests were first run, not copied from the core's output, and the 67 of
the first run all passed. They take 53 ms, and building
them after a change to the core 8 s.

**They fail when they should.** Two changes to the core, one at a time:
`(` dropped from `defaultWordBoundaries` failed `Select`'s word test,
and `crX` returning one column more failed the CR-at-a-margin test. That
second change first failed nothing: a CR in the ground state sets the
column to 0 itself (`Vt.Parse.ground`), and `crX` is reached only with
left and right margins, which no test had set. The margin test was added
for it, which is the 68th.

They run on node and not natively, where puritty runs: `gren-unit-node`
is node's. geng-lang's `run.py` holds the backends to the same output,
and the replay and bench programs run the core natively.


## VC47. Why `perf.py` failed: the appends pass on short lines (survey, 2026-11-08)

§VC45 found `harness/perf.py` failing at `6c5f4f9`, before the split: three
resize cases over their record, `short-10000` 349 M to 470 M (+35%) and
`default/short-100000` +5%, and `long-10000` 13% under. Gilbert asked for
it to be looked into before T1's piece 5. Nothing is changed here; the fix
is a choice in geng-lang's runtime, below.

**Where it came in.** puritty at `18749a4`, where the record was last
written, built with today's compiler, counts `short-10000` at 346.8 M, the
record. So the compiler did not move it: puritty did. Of the four commits
since that touch the core, each built and counted, it is `2727daf`, which
added geng-lang's `appends` pass (D1056, `m4-memory-proofs.md` §MP13) to
every build script's pass list. Today's core built with and without the pass:

| case | without `appends` | with |
|---|---:|---:|
| `short-10000` | 346.9 M | 470.5 M |
| `long-10000` | 302.4 M | 261.7 M |

The pass helps a long line and costs short ones. §MP13 timed `long-10000`
and `gitlog` with and without it, and no input of short lines.

**Which append.** The generated C of the two builds differs only at 175
append calls made `_u` or `_uu`. Each group on the resize path put back to
the plain append in the C, compiled and counted: `Pages.unpackRuns`,
`Pages`' and `Recut`'s folds and `Recut.plainsOf` move nothing. **One call
is all of it: `Resize.joinLines`' `line ++ own`**, an `arr_append_u`. Plain
there, `short-10000` is 346.5 M and `long-10000` 285.2 M.

**Why.** `joinLines` starts each line from `[]` and appends each of its
rows. The runtime's append (`geng_arr_append_mode`) answers the right
operand when the left is empty, except in `_u` mode: there it allocates a
buffer twice the length and copies, so that the accumulator owns its buffer
and an outgrown one may be given back (D1056). A short line is one append,
so every line pays an allocation and a copy at twice its size and gains
nothing; a long line pays it once and then appends in place, and gives back
what it outgrows. Giving back is not the cost: with `geng_u_outgrown` a
no-op, `short-10000` is still 470.5 M (and `long-10000` 274.4 M, 13 M worse).
The profile's growth is the allocation and the collection of the buffers
(`geng_array_alloc` +21 M, Boehm's `GC_header_cache_miss` +43 M and its lock
+28 M, `memmove` +13 M), and more in `splitLine` and `pushUtf8` (+24 M,
+21 M), which read the lines; the profile does not say why those two grew.

**What a change would buy**, each measured by editing the kept C
(`--debug-info`) and compiling it again; `short-100000` and `long-100000`
beside:

| variant | `short-10000` | `long-10000` | `short-100000` | `long-100000` |
|---|---:|---:|---:|---:|
| as built | 470.5 | 261.7 | 1,476.4 | 301.1 |
| no `appends` | 346.9 | 302.4 | 1,403.2 | 304.1 |
| an empty left answers the right in `_u` too, give-back of arrays off | 345.7 | 281.7 | 1,401.9 | 303.9 |
| an empty left makes an exact buffer, not a double one | 416.9 | 260.8 | 1,417.1 | 301.1 |

**The options.**

- **A. Leave it**, and record the counts: long lines 15% cheaper, short
  ones 35% dearer.
- **B. An empty left answers the right in `_u` mode, and only a buffer an
  accumulator made is given back.** That needs a mark on the buffer, since
  the right operand is someone else's and may be a buffer too. Expected:
  short lines at the record and long lines at today's count, the two rows
  above together; not built, so not measured. It touches D1056's safety
  rule (what may be freed), where a mistake is a use after free.
- **C. `joinLines` starts a line with its first row's cells**, not `[] ++`:
  the accumulator is then not its own, the pass makes no form, and it is the
  "plain" row: short lines at the record, long lines 23 M dearer. puritty's
  change alone.
- **D. An empty left makes an exact buffer**: one line in the runtime, no
  change to what is freed; recovers half (`short-10000` 417 M) and keeps
  long lines.

**Leaning: D now, B after.** D is safe by construction and costs nothing
measured; B is the whole answer but changes what the runtime frees, which
is worth its own survey under D1056's rules. The record stays as it is
until one is chosen: `perf.py` fails on these three cases until then.

**B surveyed** (geng-lang `m4-memory-proofs.md` §MP19, the same day): with a
mark on the buffers an accumulator's appends make, and only those given
back, `short-10000` counts 345.7 M, `short-100000` 1,383.5 M, `long-10000`
265.1 M (+1.3% on today) and `long-100000` 290.4 M, the throughput inputs
within 0.13%, the same 122 buffers given back on the long resizes, and the
native corpus passes under `GENG_GC_STRESS`. B frees a subset of what
today's rule frees. The leaning is now B.

**B built** (geng-lang Dnene19, `m4-memory-proofs.md` §MP20): every case of
`perf.py` within its record, `short-10000` 345.7 M, and the record written
again with today's counts.

## VC48. Reads the compiler proves, from the checks report (2026-11-08)

geng-lang's checks report (`m4-proof-report.md`) lists, for each `Nothing`
branch and `withDefault` default in the program, whether the compiler can
show it never runs. Of the core's 212, 192 could run as far as it could
tell; geng-lang PR11 read each and classed it. Eighteen are gone here, each
by a change that leaves no fallback to ask about:

- **Two arrays walked together** with `Array.map2`, not one read at the
  other's index: `reflowed` (lines and their marks, both reads),
  `headMarks` and `foundAt` (marks and where each was found).
- **A loop's bound written**: `trimmed`'s `n` and `lastUsed`'s `i` are below
  their array's length, so each read is `Array.getProven`. `countBlank`,
  `noWide`, `lineStart` and `Recut.plainsOf` test the index at the read
  instead, where proving it of their callers would ask the same of a
  `+` that nothing bounds; `lineStart` takes the pages' length itself rather
  than a `count` beside them.
- **Nothing to look up**: `continuations` counts the wrapped rows of a
  slice; `takeSpans` starts a span at `max at span.from`, with -1 for a new
  span, so neither it nor `plainLine` reads the next span to find its
  start; `lineCps` reads a wide tail's head only in the branch where the
  tail was there; `Charset.pointers` folds over the index with its
  positions.
- **A refinement**: `Charset.Decoder` holds a `Lead`, `0` or `0x81` to
  `0xFE`, the constructor contract geng-lang's own guide shows with this
  type, and `go` promises it of the decoder it answers, so the table read
  is `Array.getProven` and a wider lead is refused at build; `dcsHeader`'s
  `i` is `0 <= i`; `defaultColor` answers 0 for a negative index, where it
  read the palette from its end.

Held to: the unit tests 68 of 68, replay 325 of 325 with `core-dump` built
again (replay does not build it), the charset gate's 17 lines, the app
built. `perf.py`: the throughput counts the same to 0.1 M; six resize
cases fewer (`long-10000` 247.1 M from 265.1, `long-100000` 272.0 from
290.4 and 677.1 from 709.2 unlimited, `short-10000` 329.2 from 345.7),
the arrays walked together making no range of indexes to read by; the
record written again with them. The report after: 174 of the core's
fallbacks can run, 18 fewer, and 101 of its checks hold where 46 did
(geng-lang PR12).

What is left, by PR11's classes: 92 fallbacks are meant to run; 41 need an
invariant of a record held in another (`Screen` in `Term`, `Term` in the
app's model), which the language does not allow yet; the rest need
`core` contracts (`Maybe.map`, `Array.Builder.get`) or larger changes
(`alt` and `other` as one custom type, `Sgr`'s parameter index).

## VC49. `core`'s `Maybe.map` contract, and a correction to §VC48 (2026-11-08)

geng-lang gave `Maybe.map` the promise that it answers a `Just` exactly
when it is given one, and its solver now prunes before it splits
(`m4-proof-report.md` PR13). With them, three of the core's defaults are
shown never to be used (`View.cellAt`, `Resize.recutPages`,
`Keys.functionKey`), and ten fallbacks left undecided are decided. Three
changes here:

- `promptStartIn` matches the row it reads, a missing row taken as one with
  no mark as before, so `continuationsIn` is called with a `y` known to be
  a row and refined so (`y < Array.length rows`), and reads it with
  `Array.getProven`.
- `lineCps` reads the row after `r` only when `r` is one of the rows: none
  is there otherwise, and the new facts made `r + 1` one whose wrap must be
  ruled out.
- `lineStart` reads its page with `when Array.get … is` again, keeping
  §VC48's other change (the pages' length taken inside, not passed).

**The correction.** §VC48's `perf.py` record was written with `--update`
after its last changes without `harness/bench/build.sh` run again, so it
recorded the binary built before them. Built again, `short-10000` counts
341.4 M, not 329.2: 1.2% under its record before §VC48, not 4.8%. The 12 M
are `lineStart`'s `Array.getProven` over the pages: with `when Array.get …
is` it counts 329.2 M again, and with the match and §VC48's `k < 0` test
together, also 329.2 M. `lineStart`'s own C is the shorter with
`getProven`, so the cost is elsewhere and was not isolated (geng-lang's
register has it). `getProven` over rows in `continuationsIn`, in the same
resize, costs nothing measured.

Held to: the unit tests 68 of 68, replay 325 of 325 on `core-dump` built
again, the charset gate, the app built, and every `perf.py` count the same
to the 0.1 M it prints as the record §VC48 wrote, which is now true of the
code.

## VC50. `Keys` and the palette keep invariants (2026-11-08)

geng-lang made a refined record alias a type invariant (its
`m4-refine-t1.md` TO18, Dnene22): every record of the alias's shape is
asked its predicate where it is built or updated, and keeps it everywhere
else, through a `Task`, a `Maybe` or a fold. Two are written here:

- `Keys`: `at : Int where 0 <= at && at < Array.length stack`. Its two
  writes wrapped with `modBy 8`, whose result nothing promises (a class
  method's signature cannot be refined); they test instead, `at + 1` below
  the stack's length or 0, and `at - 1` from 0 to the last slot, the same
  values with a stack of eight. `keyFlags`'s `?u` reply and `keyOptions`'s
  kitty flags read the top with `Array.getProven`.
- `Term`'s `named : Array Int where Array.length named == 16`:
  `paletteColor` reads it with `getProven` for an index from 0 to 15.

Nothing else changed: `Term` is held in the app's `Model` through `Task`,
folded over in `Dispatch`, and passed as a value, as before. geng-lang's
TO16 had tried the same with a refinement that held only where a signature
named the type, and stopped at the app.

Held to: the unit tests 68 of 68, replay 325 of 325 on `core-dump` built
again, the charset gate, the app built, and every `perf.py` count the same
to the 0.1 M it prints.


## VC51. Every read of a screen row proved in range (2026-11-09)

geng-lang's refinement checker now holds every read and write of a screen
row in `vt` to the ring's range, with nothing left unproved (its
`m4-refine-t1.md` TO19.8, from 90 errors at TO19.4). What the core says now:

- **Invariants.** `Term`'s screen is its size (`screen.rows == rows`,
  `screen.cols == cols`). `Screen`'s scrollback fits in its ring
  (`0 <= hist`, `hist + rows <= size`), and every ring has a row past its
  screen (`rows < size`; a view's `viewAt` makes one row more for it).
  `Back` counts at most 2^29 rows held and 2^29 dropped (below).
- **Signatures.** The 36 functions that make a screen from a screen say
  they keep its `rows`, `cols`, `hist` and `size`; every row a function
  takes is refined, a logical row `0 - s.hist <= y && y < s.rows`, or the
  ring's bounds for `moveRows` and its kin; the parser's byte index is
  never negative, and below the read's length where a byte is read.
- **Loops for maps over ranges.** `Array.map` over `Array.range` cannot
  say its index is in range, so `Dump.screenRows`, `Dump.ringRows` and
  `Resize.ringRowsOf` are loops, as `Vt.ringRows` already was.
- **Tests where a fact cannot be written.** The hidden screen of
  `toAlt`/`toMain` is the term's size, which a `Maybe Screen` cannot
  carry: `altScreen` makes a new alternate screen for one that were not,
  and `toMain` leaves the alternate screen up. `screenUp` keeps a row only
  when the ring has room for it, which `pageOut` makes, and `pageOut`
  packs at most `hist` rows; `spreadWork` skips a queued cell outside the
  screen; `cursorOf` reads the cursor's row only once it is in view;
  `unheadAbove` does nothing with no row above; `hiddenHist` clamps the
  hidden ring's count to its invariant. No unit test or replay case takes
  any of these branches.
- **Functions of their own for the checker.** `insertFor` (`printPoint`'s
  insert) and `altScreen`: a three-way `if` choosing a screen is too large
  a question for the checker inline. Neither costs an instruction.

**The scrollback's counts are capped.** `back.gone`, the rows ever dropped
from the scrollback, only grew, and at 32 bits would have wrapped after
2^31 rows, about an hour of `yes`, taking a selection's absolute rows with
it. Gilbert chose a cap: `Back.rows` and `Back.gone` stop at 2^29
(536,870,912), added with saturation (`Pages.addRows`), and `dropOver`
drops a page at the cap as at the byte limit, so that the ring's rows, the
pages' and the dropped ones add up inside `Int`. A selection's absolute
row is read through `Vt.fromAbsolute`, which saturates 2^30 rows above the
screen. The bounds in the signatures are written as numbers, since a
refinement reads only literals: 536,880,105 is 2^29 + 9,193 (the pages'
cap and the largest ring), 1,073,751,017 is 2^30 + 9,193.

**What it cost, and what was found.** The first build was up to 118%
slower on scrolling: the resize, rewritten to keep the screen in the term,
handed it to a reader, so `resizeTo`'s result was not fresh, nor
`dispatch`'s, and the in-place pass copied the screen at every line feed
(`GENG_INPLACE_REPORT` named it: "a call of resizeTo, whose result is not
fresh"). The resize takes the screen and sets the new one with the size in
one update, as `Term`'s invariant needs. Of the run-time tests,
`printAscii`'s stop as `i + min (n - i) (cols - t.x)` cost 17% on
`vte-light_cells` and `unheadIf`'s `y > 0` 2.3% on `vte-unicode`; the stop
is now an `if` computed once and the test moved into `unheadAbove`, and
both cost nothing. What is left, accepted by Gilbert and recorded in
`corpus/perf/baseline.tsv`: `vte-scrolling` +1.35%, the four region cases
+1.87%, `vte-unicode` +1.35%, from the overflow-safe forms in `decodeRun`
and `printAscii` (three provable forms of `decodeRun` were counted, and
this one is the least), and two resizes of `short-10000` +3.7%, with
`long-10000`'s 3.5% lower.

Held to: the unit tests 68 of 68, replay 325 of 325 on `core-dump` built
again, and `perf.py`'s counts, recorded.


## VC52. The ASCII scan is a primitive, and what proofs bought (2026-11-09)

After §VC51, two ideas for turning the proofs into speed were counted, and a
third was built.

**Cell reads with `getProven`.** With `rowOffset` proved, `metaAt`,
`extentAt`, `cellAt` and `peekCell` can read with `Array.Builder.getProven`,
no `Maybe` and no test of the index (their offset refined as `rowOffset`'s
result, their column below `s.cols`, and the 36 functions that keep a
screen promising its `stride` and its cells' length too, since the checker
cannot equate two products `size * stride`). It proved, and the C lost
twelve comparisons; but `vte-light_cells` took 90 ms with it where it took
78 without, and the instructions of its ASCII scan, `asciiEnd`, went from 62 M to
108 M though the scan had not changed: everything is inlined into the
parser's one function, and the readers, smaller without their tests, were
inlined in more places, and clang compiled the scan in it differently. Not
kept.

**No wrapping in the C.** `geng_prim.h` adds through `uint32_t`, so that
`Int` wraps, and clang cannot assume a sum does not. Compiled again with
plain signed sums everywhere (unsound, to measure the most a proof of no
overflow could give): `gitlog` 948 to 907 ms, the rest within a few, and
`vte-light_cells` counting 7% more instructions while no slower. A sum the
checker proves is a sum the backend could emit so; that is worth at most a
few percent here, and is not built.

**The scan as a primitive.** The scan was the largest single cost of
`vte-light_cells`, and moved with whatever else changed. geng-lang made it
`Bytes.spanWithin`, a run of bytes in a range, 16 bytes a step natively
(its `m3-bytes-access.md` §BA19, §BA20, Dnene27), and `asciiEnd` is now one
call of it. The counts and times are in §BA20: `vte-light_cells` 78 to
59 ms, `ls` 726 to 659, `gitlog` 948 to 896, `vte-scrolling_fullscreen`
212 to 196; the region cases about 4% slower in time and 1.8% in
instructions, `vte-scrolling` 2%, which is the parser's layout moving, as
in §VC51. In cycles: `vte-light_cells` −24.9%,
`vte-scrolling_fullscreen` −12.3%, `ls` −8.4%, `gitlog` −5.6%, the region
cases +3.5% to +4.0%. The record holds the new instruction counts. The cell reads with `getProven` were counted again with the
primitive in: still a loss (59 to 72 ms), and still not kept.

**Counting cycles.** `perf.py` holds instructions to the record because they
repeat to the instruction, but they are not time: a SIMD step reads 16
bytes in an instruction or two, and the unwrapped build counted more and ran
faster. `--cycles` prints the median of five counts of `cycles:u` beside
each case, and `--against OTHER` counts another `core-bench` beside the one
built, instructions and cycles, with the change; cycles move by a few
percent run to run, more on a loaded machine.

## VC53. Where the time goes now, and what profile-guided optimization gives (2026-11-09)

**The profile.** `geng profile` (geng-lang `m4-profile.md` T2) over
`harness/bench` with this commit's `vt`, two inputs. `gitlog`, 2,910 M
instructions:

| function | M instructions | of which ownership checks |
|---|---|---|
| `Vt.Pages.pushUtf8` | 648 | 178 |
| `Vt.Parse.resume` (the parser, everything inlined) | 482 | 13 |
| `Vt.Pages.packCells` | 353 | 0 |
| `Vt.Pages.packRows` | 324 | 9 |
| `Array.Builder.set` | 236 | 130 |
| `Vt.Parse.csi` | 205 | 10 |

Packing rows into scrollback pages (§VC6), `pushUtf8`, `packCells` and
`packRows`, is 1,325 M, 46% of `gitlog`: every row that scrolls off is
packed once, a byte pushed at a time, and each push tests that the builder
is its own (geng-lang D1000) and has room. The ownership tests are 12% of
the whole. `vte-scrolling_top_region`, 1,040 M: the parser 493 M,
`Vt.Scroll.lineFeed` 136, `Vt.Screen.clearRow` 91, `inRegion` 71, `phys`
67; nothing allocates.

**Profile-guided optimization.** The kept C of a `--debug-info` build,
compiled again by its `compile.sh` with clang 21's
`-fprofile-instr-generate`, run over the thirteen inputs, and compiled a
third time with `-fprofile-instr-use`. Cycles, the least of seven runs of
each input ten times over, interleaved; the output is the same:

| input | before | trained on all 13 | trained on 6 |
|---|---|---|---|
| `cup` | 2,731 M | −22.7% | −12.3% |
| `gitlog` | 4,812 M | −20.1% | −16.4% |
| `ls` | 3,592 M | −31.9% | −22.7% (not trained on) |
| `vte-dense_cells` | 1,060 M | −22.7% | −10.9% |
| `vte-light_cells` | 317 M | −6.8% | +10.8% (not trained on) |
| `vte-scrolling_fullscreen` | 1,061 M | −30.0% | −26.9% (not trained on) |
| `vte-scrolling_top_region` | 1,433 M | −25.1% | +3.8% (not trained on) |
| `vte-scrolling` | 2,052 M | −23.4% | −17.5% |
| `vte-unicode` | 835 M | −8.4% | −10.4% |

The six were `gitlog`, `vte-scrolling`, `vte-dense_cells`, `cup`,
`vte-unicode` and `vte-cursor_motion`. Trained on everything, every input
is 7% to 32% faster, on all but `vte-light_cells` more than §VC52's
primitive gave; it also gives clang what the layout of the parser's one function has
lacked (§VC51). Trained on half, two of the inputs left out are slower: a
path the training never ran is laid out as cold. So the training set is
part of the build, and must run every path that matters. The toolchain
has no option for it yet (geng-lang `docs/open-items.md`).

**What is left, largest first.**

1. Profile-guided builds, as above: a toolchain question.
2. Packing pages: a run of plain cells (no `packSpecial` bit, one style)
   is its code points' low bytes, so it could be packed in one step, a
   primitive over the cells as `Bytes.spanWithin` is over bytes; or the
   newest pages could be kept as cells, copied whole, and packed later.
3. The ownership test on each push: `pushUtf8` tests up to four times for
   one code point. A push of several bytes that tests once would cut most
   of the 178 M.
4. Scrolling in a region: `lineFeed`, `clearRow`, `inRegion` and `phys`,
   300 M between them, each small.

## VC54. A profile-guided build of puritty (2026-11-09)

geng-lang built §VC53's measurement into `geng make` (its `m4-profile.md`
§PF12, Dnene31). `harness/bench/pgo.sh` builds `core-bench` with
`--profile-generate`, runs it once over each of the thirteen inputs, and
builds it again plainly, leaving the counts in
`harness/bench/core-bench.profile/`; `app/build.sh
--profile-use=$PWD/harness/bench/core-bench.profile` builds puritty with them.

`core-bench` built so, against a plain build of the same source, in
cycles: `cup` −24.4%, `gitlog` −19.9%, `ls` −31.7%, `vte-dense_cells`
−22.6%, `vte-light_cells` −7.5%, `vte-scrolling_fullscreen` −30.2%,
`vte-scrolling_top_region` −24.7%, `vte-scrolling` −23.6%, `vte-unicode`
−8.1%. puritty itself is a different program over the same `vt`: clang
found 38 of its 2,782 functions' counts out of date and used the rest. The
renderer and the X11 code are not trained, and compiled as before.

`perf.py` measures the plain build, whose instructions the record holds.
`app/build.sh` does not use a profile unless asked.

## VC55. Packing a page in runs (2026-11-09)

§VC53's second item. geng-lang added three general primitives to `core`'s
`Array.Builder` (its `m3-bytes-access.md` §BA21, Dnene32): `pushUtf8`, a
code point's UTF-8 in one write; `spanMasked`, how far a run of words agree
under a mask; and `appendNarrowed`, words' low bytes onto a builder of
bytes.

`packCells` now asks, once a style run is in hand, how far the cells go
that are plain ASCII in that style: every bit of the cell above the low
seven equal to `styleBits style` (`plainMask`), which leaves out a wide
cell, a cluster, a background-only or protected cell, a code point from
0x80 up and another style. That run is packed with `appendNarrowed` and
counted into the run in hand; a cell outside it is `packCell`, the old
step, whose code point is now `Builder.pushUtf8`'s. The bytes written are
the same: 325 replay cases, 345 view cases and the selection cases pass.

`perf.py`, instructions, against the build before: `vte-scrolling_fullscreen`
−54.7%, `ls` −43.5%, `gitlog` −33.6%; the rest within 0.3%. Cycles, the
least of seven runs over each input ten times over: `vte-scrolling_fullscreen`
−54.5%, `ls` −45.4%, `gitlog` −25.7%; the rest within noise. The record
holds the new counts.

**Two findings on the way.** `pushUtf8` compiled as one C function was not
inlined where `pushLast` had been, and `vte-scrolling`, whose rows are a
character or two, counted 4.7% more; with its ASCII byte always inlined and
the rest out of line it counts what it did. And the resizes of
`long-10000` were 6.7% over their record before this change: commit
23eddf6, which took `hiddenHist`'s clamp out, made them 4% dearer in
instructions with no cycle change measured, and its message did not
count them. `geng decisions` over the two builds found no inline or
in-place decision changed, so it is clang's compile of the code around
it; the clamp stays out, and the record moves.

## VC56. Scrolling in a region: what is left is layout (2026-11-09)

§VC53's fourth item. `vte-scrolling_top_region` is `y\r\n` in a region of
rows 2 to 50: a character, a carriage return, a line feed that turns the
region (`feedRegion`, O(1)) and clears its bottom row. By source line
(`perf record` on a `--debug-info` build, cycles) nothing is large: the
integer comparisons inlined all through it 12%, `clearRow`'s write of the
row's meta slot 5.6%, the parser's byte read 5.2%, the builder's ownership
test 5.1%, and `Bytes.spanWithin` 4% to 5%, called for the run of one
printable byte after each `y`.

**Tried and not kept.** `geng_prim_bytes_span_within` with its first byte
tested inline before the call (a run that ends at once paying a load and
two compares): `vte-scrolling_top_region` +0.9% in cycles,
`vte-light_cells` +23.0%, `vte-scrolling_fullscreen` +16.4%, `ls` +6.7%.
The primitive is a function of its own so that the parser's one large
function does not compile it by its neighbors (geng-lang
`m3-bytes-access.md` §BA19), and an inline prelude undid that.

**Profile-guided, on top of §VC55** (`harness/bench/pgo.sh`, then
`--profile-use`, cycles against the plain build): `vte-scrolling_top_region`
−24.9%, `cup` −24.7%, `vte-dense_cells` −22.9%, `vte-scrolling` −19.2%,
`gitlog` −12.3%, `ls` −10.3%, `vte-light_cells` −8.4%, `vte-unicode`
−7.0%, `vte-scrolling_fullscreen` −5.6%. What a hand edit of the region's
path could win, a trained build wins without one, and the edit risks the
swings above. Not pursued by hand.

**Release builds only** (Gilbert, 2026-11-09): `app/release.sh` trains the
profile and builds with it; `app/build.sh`, the development build, takes no
profile.

## VC57. Every cell read the compiler can see, proved (2026-11-09)

The sixth round of the checks report (geng-lang `m4-proof-report.md`
§PR16), the first made with `geng checks`. geng-lang gave
`Array.Builder.get` a contract (a `Just` exactly when an index of 0 or more
is inside the builder) and taught its checker two things it needed
(Dnene35). Here, row offsets are refined through 46 signatures: a row
offset is `0 <= o && o + s.stride <= Builder.length s.cells`, as
`rowOffset` promises, and a column below `s.cols`. With them each read of a
screen cell through `Builder.get` has a `Nothing` the compiler shows never
runs, and the reads are the same code as before.

Four changes to code, each measured:

- `extentAt` clamps a row's extent to its width, `clamp 0 s.cols`: the
  meta slot never holds a wider one, and now the compiler knows it.
  Instructions the same on every input.
- `splitWhole o x x`, an insert at column 0, read its last cell at
  `o - 1`; on the buffer's first row that is -1, which `Builder.get`
  counts from the end. It now reads nothing for an empty run.
- `eraseChars`' end and `wordRight`'s step compare before they add, so
  that a count past the row's width cannot wrap the sum.
- `Dump.ringRow` maps over its row with `Array.indexedMap`, whose callback
  is given an index in range, where `Array.range` gave none.

| `vt` | before | after |
|---|---:|---:|
| fallbacks never run | 14 | 41 |
| fallbacks can run | 178 | 151 |
| checks hold | 1,218 | 1,597 |
| open | 13 | 24 |

`perf.py` against the build before: instructions within 0.2% on every
input, cycles within run-to-run noise. 68 unit tests, 325 replay cases, 345
view cases and the selection cases pass.

The open checks that grew are sums the contract now asks about and nothing
bounds yet: the renderer's previous frame, read at `y * cols + x` (its
`Shadow` has no rule tying its cells to `rows * cols`), `withPen`'s style
cache and `scanY`. They are the next round's. The report's list of what
can run and what is open is kept in `corpus/checks/baseline.tsv` (228
entries): `geng checks Main --baseline ../corpus/checks/baseline.tsv`, run
in `app/`, fails on an entry not in it.

**A correction to §VC55.** Its perf record was written from a `core-bench`
built in a tree with §VC55's packing change set aside (for the clamp
question of that section), so it held the counts from before packing:
`gitlog` 2,862 M where the committed code counts 1,899 M. The record now
holds this build's counts, written after checking the binary measured is
the one built from this tree.

**After §VC57** (2026-11-09): two binary searches, `Width.find` and
`Resize.promptIn`, took their midpoint as `(lo + hi) // 2`, which wraps
past `Int`; both are `lo + (hi - lo) // 2`, their bounds stated (`0 <= lo`,
`hi` inside the array), so each read at `mid` is proved too. `wrapsAt`
reads with `Array.getProven`, its callers `lineTop` and `lineBottom`
testing the index they pass. `geng checks` against the list: 0 new, 4 gone
(224 entries); every test passes and `perf.py` is within the record.

## VC58. No open checks: every sum and product the report doubted, bounded (2026-11-11)

Gilbert, 2026-11-11, before local tabs: run `geng checks` and see where
puritty stands, adding refinements where they fix errors or prevent them.
The report over the whole program (`app/linux`, `Main`) said 1,662 checks
hold, 740 fallbacks can run and **51 checks are open**: sums and products
the compiler could not show stay inside `Int`. Of those, 24 were the core's;
the rest were the app's and the tmux and window packages' (`docs/tmux.md`
TM33). After this round: **1,883 hold, 0 open**, 735 can run.

The core's, each bounded where the value is made, not tested again where
it is used:

- **The renderer's previous frame, `y * cols`** (`diffRow`, `runEnd`,
  `differs`, `inWord`, PR16's open sums): the rows the frame walks start at
  0 (`diffRows` and `collect` now say `0 <= y`, which was `0 - s.hist <=
  y`, so a negative row could not reach the shadow, where `Builder.get`
  would count it from the end), and the helpers take `y < 1000` and `cols`
  1 to 1000. The checker shows such a product does not wrap but not how big
  it is, so `rowStart y cols` gives the row's first index with its range
  stated (`clamp 0 999000`, two compares a row); `cellAt`, `drawnAs`,
  `writeRun` take the row at most 999,000 and the column at most 1000, and
  `runEnd` promises its end at most `cols`. `cellAt` reads the preedit only
  for a `preAt` of 0 or more.
- **`scanY` and `searchK`**: the shift between this frame and the last is
  within 1000 either way, and the rows within the screen.
- **`inkRecords`**, the renderer's ink bytes, and **`Window.decode`**, the
  window's events: the bytes left from the offset are compared instead of
  `at + 5`; the step is `advance`, which never goes back or past the end.
- **`composePane`**: a pane placed outside ±16,384 draws nothing.
- **`runEdge`** (a word's or line's edge for a click): one back, or one on
  while inside the line.
- **`Dump.ringRow`** reads within the row's extent; **`Sgr.cacheSlot`**
  states its slot 0 to 1022, so `h + 1` cannot wrap; **`rgbAt`** reads its
  three parameters from `Array.dropFirst at`.
- **`Resize.writeRows`**: `from + y` only for a `from` of 0 to 10^9.

**A cost found on the way, and what it was.** Written as a `let` before the
function's `if`, `writeRows`'s index made `perf.py`'s long-line resizes 12%
dearer (245.7 M recorded, 268.4 M measured); written inside the branch they
are as before (238.8 M). It is not the `let` (geng-lang `m4-proof-report.md`
PR17.1): the two programs allocate the same, but in the first a stack slot
`writeRows` left a pointer in is read again, unwritten, inside
`Recut.recut`'s frame on the next resize, and the nursery's conservative
scan of the stack pins what it points at, 18 MB more promoted over the
run. Moving the `let` moved the word, not a defect; geng-lang's D915 has
the remedy, precise stack roots, registered.

Tested: every harness (view 345, replay 325, pixels 46, keys, mouse,
paste, events on beelink1 13, settings 20, app tests 104, …) and `perf.py`
within the record.

## VC59. Where puritty stands before local tabs (2026-11-11)

`geng checks Main` in `app/linux`, against `corpus/checks/baseline.tsv`:

| | 2026-11-11, before | after VC58 and TM34 |
|---|---:|---:|
| checks hold | 1,662 | 1,891 |
| fallbacks never run | 42 | 46 |
| fallbacks can run | 740 | 736 |
| open | 51 | 0 |
| type invariant checks | 298 | 420 |

**The list.** On 2026-11-09 it held the core, `x11` and `Main`'s 224
entries; since then the ssh and tmux packages, the settings window and
most of the app came into the report, 376 entries never looked at, so the
check failed on every build. They have been read by kind and module and
recorded (480 lines): the core's 161 (as VC57 left them, less the ones
VC58 settled); and the app's and packages': a default for a setting or a
reply that is missing, a `Maybe` field of the model that is `Nothing`
when no search, menu, dialog or prompt is open, an `Err` from the system
or the network, and a few index reads. **From now on a new fallback that
can run, or any open check, fails `geng checks`**, which is the guard for
the tab work: each one it reports is to be proved away or recorded with a
reason.

**What is left worth refining, in order of use to the tabs:**

1. **Index reads in the app** that an invariant on the model would prove:
   `Main`'s menu (`menuKey`, `menuChosen`: the selected item inside the
   items), the dialog's prompts (`dialogOf`, `ownTerm`), the preedit's
   feedback. The tabs' own model is the same shape (TM34): the shown tab
   inside the list, written with that invariant from the start.
2. **`core`'s `Array.findFirst`** promising its index is inside the array
   (TM34): every "find the pane, then read its terminal" in TmuxMode, and
   the tabs to come, would be proved by it.
3. **TmuxMode's 160**, mostly replies tmux may not send (`replied`,
   `copyLine`, `subscribed`) and formats asked for: intended; a few pane
   lookups follow from 2.
4. **The ssh client's 115** and the settings window's 90: parsing and
   protocol defaults, intended; a separate round, not on the tabs' path.


## VC60. `perf.py --layouts`: is a jump a stack word's? (2026-11-11)

Gilbert, 2026-11-11, after geng-lang's `m4-roots.md` (D915's survey): add
the layout check. PR17.1 spent a day finding that a 12% jump in a resize
count was a word left on the stack, which the nursery's conservative scan
read as a pointer and pinned. `m4-roots.md` RT3 found that changing only
the C's frames moves such words on and off.

`./harness/perf.py --layouts -f CASE` builds core-bench four more times,
at `-O1`, `-O3`, `-fno-inline-functions` and `-fno-omit-frame-pointer`
(`GENG_CFLAGS`, which comes after the build's `-O`; `build.sh` takes
`CORE_BENCH_OUTPUT` for where to put each), and runs each case on all five
with `GENG_NURSERY_STATS`. The flags change the code's own instructions
(no inlining is a third more on some programs), so instructions are not
compared. What the nursery promotes is. All five allocate the same bytes,
within 0.1% (`-O3` boxes 48 bytes more of 260 M), so promotions that
differ between them are the layout's: a stack word, and a count that moved
with it is not the code's.

**Measured.** PR17.1's version A (`writeRows`' index as a `let` before
its `if`), built for the test and put back after:

| layout | allocated | promoted |
|---|---:|---:|
| as built | 260.4 M | **45.3 M** |
| `-O1` | 260.4 M | 27.2 M |
| `-O3` | 260.4 M | 27.2 M |
| no inlining | 260.4 M | 27.2 M |
| frame pointers | 260.4 M | **45.3 M** |

"promoted moves 67% with the layout alone, on the same allocation: a word
left on the stack." That is PR17.1's 18 MB, named in one command. The code
as it is gives 27.2 M at every layout for `long-10000`. For
`long-100000`, `-O1` promotes 31.3 M against 23.9 M at the others: a word
there too, at a layout the build does not use. `perf.py` without
`--layouts` is unchanged, and all within the record.


## VC61. The unit suites run natively, on Linux and on Windows (2026-11-13)

The unit suites of §VC46 and their siblings ran on node only, compiled to
JavaScript: the core's, the tmux package's and the application's. puritty
ships compiled to C, and on two platforms, so a test on node held the Geng
code but not the code that runs. gren-unit-node 2.0.0 has a runner for
native programs (geng-lang `m1b-test.md` §TS11, Dnene54), and each suite
now runs on node, natively on Linux, and on Windows.

**How.** Each suite's list moved out of its `main` into a module both
entries share (`VtSuites`, `TmuxSuites`, `AppSuites`), so a suite added
to one runs in all. The node entries are as they were (`run.sh`); a
`native/` application beside each builds the same list on gren-unit-node's
os runner (`native/run.sh`, whose arguments are the runner's), and
`native/run.sh --windows` cross-compiles `tests.exe` for vt and tmux. The
application's tests build natively over `app/linux`'s sources and the
real X11 package, where node has `app/tests/stub/Window.geng`, and
`app/tests/windows/build.sh` builds them over `app/windows`'s sources and
the win32 package, as a console program so that its report shows.

| suite | node | Linux, native | Windows 11 (beelink1) |
|---|---|---|---|
| vt | 94 | 94, in 7 ms | 94 |
| tmux | 99 | 99, in 16 ms | 99 |
| app | 149, in 229 ms | 149, in 31 ms | 149, in 75 ms |

**What Windows found.** Its first run failed three of the application's
tests, each a default `Platform` sets per platform that the test had
written as Linux's: the `start` a bad value falls back to (`hosts` on
Windows, `shell` on Linux), the default font (Cascadia Mono, DejaVu Sans
Mono), and the client of a host that names none (the built-in client on
Windows, OpenSSH on Linux; ssh-client.md SC18). The code was right on both;
the tests now read the value from `Platform`, and pass on all three.

**ssh's checks too.** `ssh-tests known-hosts FILE` and `ssh-tests config
FILE` run their cases as suites on the same runner, a test for each case
(34 and 30, as before), the runner's arguments after the file;
`ssh-crypto-tests` became one the same day (ssh-client.md SC13). The
scripted server's 25 cases and the live `sshd.py`'s 62 pass with the
program's other modes unchanged.

**Not yet:** the `text` package's Geng surface needs an open window and
has no tests. The runs were by hand; §VC62 makes them a gate.


## VC62. The unit suites' gate: `harness/units.py` (2026-11-13)

Gilbert: the native tests need to be in a gate. `harness/units.py` builds
and runs every gren-unit-node suite puritty has on each platform it runs
on, and holds each run to its count: the program ends with status 0 and
its runner says `OK — N passed` with the N written in the gate, which
moves only with the commit that moves it (as geng-lang's `suites.py`
holds its suites, D356).

| suite | node | Linux, native | Windows (beelink1) |
|---|---|---|---|
| vt | 94 | 94 | 94 |
| tmux | 99 | 99 | 99 |
| app | 149 | 149 | 149 |
| ssh-crypto's vectors | — | 10 | 10 |
| ssh-tests' known-hosts | — | 34 | 34 |
| ssh-tests' config | — | 30 | 30 |

The Windows programs are cross-compiled here and copied to beelink1 with
the files they read, and run there over ssh. **Windows is part of the
gate**: when beelink1 cannot be reached, its runs fail, and `--no-windows`
leaves them out on purpose and says that the run was not the whole gate.
It is run from puritty's devbox, which has the X11 package's libraries;
each build and run is capped at 8 GB.

Measured: 15 of 15 runs pass in 495 s, most of it building (the app's
three builds about 80 s each). Set to expect 98 of tmux, it fails, saying
`passed 99 of 98 expected` with the report.



## VC63. The checks report after the tabs, the tmux work and the sounds (2026-11-13)

Gilbert: use `geng checks` to tighten the refinements and find new ones.
`geng checks Main` in `app/linux` against `corpus/checks/baseline.tsv`
had not been run since §VC59, and the program had grown by the tabs,
TM35 to TM69, the sounds and the settings' pages: it failed, **7 checks
open** and 396 fallbacks that can run not in the list.

| | 2026-11-11, §VC59 | 2026-11-13, before | after |
|---|---:|---:|---:|
| checks hold | 1,891 | 1,937 | 1,948 |
| fallbacks never run | 46 | 46 | 47 |
| fallbacks can run | 736 | 1,115 | 1,114 |
| open | 0 | 7 | 0 |

**The open checks, each bounded where the value is made:**

- **The choose-buffer and choose-client list's selection** (`drawListing`,
  `top + listHeight` and `selected - listHeight + 1`): `Listing.selected`
  is a row index now, a type invariant `0 <= selected && (selected == 0 ||
  selected < Array.length rows)`, asked at every write. Writing it found a
  bug: when tmux's answer emptied the list, the selection became
  `clamp 0 (Array.length rows - 1) l.selected`, which is -1; it is 0
  now. The writes clamp to the rows shown, a sorted copy of the rows the
  filter kept, which `core` could not show to be no more than the rows;
  `Array.keepIf` and the sorts now say so (geng-lang `m4-refine-t1.md`
  TO21), and `listRows` says its result is no longer than `l.rows`. The
  rows shown are `dropFirst top` then `takeFirst listHeight`, which needs
  no sum. A search's hit is clamped where it is written (`findFirst`
  promises its index nothing).
- **customize-mode's list height** (`drawCustomize`, `customizeHeight`):
  `customizeListHeight` takes a height of 0 or more and answers one
  between 0 and it; the height less its frame is taken only when the
  area is taller than 2.
- **A choice moved on** (`Tmux.Customize.setOption`, `at + 1` of an index
  `findFirst` gave): each choice is paired with the one after it, the last
  with the first, so the next is found with no arithmetic. A new test
  holds the round from the last choice to the first (tmux tests 100); it
  passes on the code before and after.

**A fallback proved away:** the dialog's buttons' places are made one for
each button (`Array.indexedMap` over their widths, where a fold made
them), and `Dialog.layout` says so (`Array.length r.buttonXs ==
Array.length d.buttons`), so the draw's read of a button's place never
falls back.

**What is left, and recorded** (1,114 entries, 693 lines): the 388 new are
input, read as it comes: tmux's replies and their words (`replied`, the
tree's, the listing's and customize mode's parsers), the restore file's
tabs, an IME's feedback array, a key chord typed, the event queue's
end; the tree's selection over rows it works out rather than keeps, empty
while it loads; and the tab order, whose closing writes (`keepIf`) leave
nothing a rule could bound. **From now on a new one fails `geng checks`
again**, as §VC59 set.

**Opportunities found, not taken here:** `Array.findFirst` cannot promise
its index, since a refined field inside `Maybe` is refused (every "find,
then read" clamps instead); the tree's rows are worked out, not kept, so
its selection has no field to be bounded by; and the tab order could keep
its shown tab as an invariant if closing a tab chose the next one in the
same update.

Tested: the unit gate (`harness/units.py`) 15 of 15 on node, Linux and
Windows, before the tmux count moved to 100.

## VC64. Every fallback that can run, meant or listed (2026-11-13)

Gilbert: apply `meant` (geng-lang `m4-refine-t1.md` TO23, TO24) to
puritty and check the reports. Each of §VC63's 1,114 fallbacks that can
run was read, in six groups, and given a reason and one of three
verdicts: meant (the fallback is how the program answers that case),
provable (it can never run, and a rule the checker cannot yet see says
why), or a bug (it hides something that should be reported).

| | §VC63 | after |
|---|---:|---:|
| checks hold | 1,948 | 1,985 |
| fallbacks never run | 47 | 47 |
| fallbacks can run, listed | 1,114 | 133 |
| meant | — | 981 |
| open | 0 | 0 |

(1,948 to 1,985 is the TB15 tab order, before this work.)

**The reasons.** One `Reason` type per package, each variant with its
words (`Reason`, `Vt.Reason`, `Tmux.Reason`, `Ssh.Reason`,
`X11.Reason`), each holding only the reasons its package uses, since an
unused one fails `geng checks`:

| reason | words | app | tmux | vt | ssh |
|---|---|---:|---:|---:|---:|
| `FromOutside` | what came from outside was short, missing or not what was asked | 92 | 50 | 16 | 29 |
| `NotSet` | a setting or option is not set, so its default applies | 125 | 31 | 26 | 27 |
| `NotOpen` | a part of the model is empty because its menu, search, dialog, prompt or mode is not open | 98 | 2 | 2 | 1 |
| `NotKnown` | a name, key or id is not in the program's own tables | 66 | 45 | 23 | 1 |
| `OutOfRange` | an index or position is past an edge, and this is the edge's answer | 68 | 2 | 38 | 5 |
| `NoMore` | a scan, list or queue ended, and this is its end | 43 | 11 | 27 | 18 |
| `NotYet` | it is not known yet; a later event fills it in | 40 | 4 | 7 | 10 |
| `Gone` | a pane, tab, window or session closed before an event about it was handled | 38 | 15 | — | — |
| `Refused` | a call to the OS, a file or the network failed | 13 | — | — | 1 |

(`app` counts `TmuxMode` and `Platform`; x11 has one, `FromOutside`.
Counts are as first applied, before seven hand-placed marks.)

The report reads, for each: `meant  differs:977  the default of
Maybe.withDefault is used when …, meant: Vt.Reason.NotYet (it is not
known yet; a later event fills it in)`.

**What stays in `corpus/checks/baseline.tsv`** (133 entries) is what
should not be called meant:

- **121 provable**, where the fallback cannot run but the checker cannot
  see why. The commonest: `String.split` never answers an empty array
  (`Array.first`/`last` of one, a dozen places); an index found in one
  array read from a parallel one (`TmuxMode`'s `ids` and `panes`); a
  `when` on a field just tested `/= Nothing` (`Main`'s menu, search,
  rename, close and color modes, each with a caller that only runs it
  when its mode is open); `slotOf` having found a filled slot (four in
  `Main`); `Vt.Recut`'s page index from an `Array.get` on the same
  pages that succeeded. By module: `Main` 27, `TmuxMode` 24, `Schema` 9,
  `Ssh.Session` 6, `Vt.Recut` 6, `Ssh.Transport` 5, `Tmux.Customize` 5,
  the rest three or fewer.
- **11 bugs**, found by reading and checked against the code, fixed
  since in `docs/ssh-client.md` SC27 (the baseline is 125 entries after):
  - `Main.sshBackend`: with neither `HOME` nor `USERPROFILE` set, home
    is `""` and `~/.ssh/config` is read as `/.ssh/config`; with neither
    `USER` nor `USERNAME`, `""` is the login name. Both should be said.
  - `Ssh.Session.resolveOne`: a `Port`, `ServerAliveInterval` or
    `ServerAliveCountMax` that is not a number becomes 22, 0 or 3
    without a word.
  - `Ssh.Config.matchLine`: a `Match` criterion with no argument is
    matched against `""` rather than reported.
  - `Ssh.Connection.onChannel`: a `WINDOW_ADJUST`, `CHANNEL_DATA` or
    `EXTENDED_DATA` that does not read is dropped (`Err _ -> st`), so
    output is lost or sending stalls; an unreadable confirmation ends
    the channel, and these should too.
  - `Ssh.Session.remember`: a known_hosts path with no parent makes a
    directory at the file's own path, and the append then fails.
  - `Ssh.Transport.sendPacket`: a failed seal sends nothing but still
    counts the sequence number, so the next packet's MAC is wrong.

**Seen while reading, kept meant:** `Vt.Resize.promptIn` reads
`Array.get (lo - 1)`, and core's `Array.get` counts a negative index
from the end, so at `lo = 0` it would read the last start; it is safe
only because the first start is always at 0. A `Maybe` used as yes/no
(`writeLog`'s `Nothing` is success, `moveFocus`'s is "not Tab") has no
reason that fits; those are `NotKnown` or `Refused`, and a `Result` or
`Bool` would say it better.

**From now on** a new fallback that can run fails `geng checks` unless it
is marked `meant` or recorded, as before, and a mark whose fallback stops
running fails it too.

## VC65. puritty is formatted, and kept so (2026-11-13)

Gilbert: run `geng fmt` on puritty; all its code needs to be formatted.
Of its 164 Geng files (the application, the packages, their tests, the
probes), 117 were not; `scripts/fmt.sh` formats them all, or the files
given, and `--check` changes nothing and fails listing what is not
formatted. The unit gate (`harness/units.py`) runs `--check` before the
suites, so an unformatted file fails it.

The generated tables are formatted by their generators, so a table made
again is the same text: `vt/gen-euckr.py`, `vt/gen-keys.py`,
`packages/tmux/tools/color_names.py` and `probes/euckr/gen.py` run
`scripts/fmt.sh` on what they write; `vt/gen-width.py` and
`customize_tables.py`, which print, say to in their usage. Made again,
`EucKrIndex` and `KeyTables` are byte for byte the formatted files.
`gen-keys.py` had not known of §VC64's marks, and writes them now
(`meant Reason.NotKnown 0` in its five lookups, and the import after
the module's doc comment, where §VC64's script had put it before).

The formatter writes an array of more than one line one element to a
line, so `EucKrIndex`'s 23,940 entries went from 1,260 lines to 23,949.

`geng checks`: 0 new, the same counts. The unit gate passes and the
Windows build compiles.

## VC66. The unit gate runs `geng checks` (2026-11-13)

§VC63 began because `geng checks --baseline` "had not been run since
§VC59": the guard was a command, and nothing ran it. `scripts/checks.sh`
runs it over the whole program against `corpus/checks/baseline.tsv`, as
§VC64's runs did, and `harness/units.py` runs it after the format check,
before the suites. A fallback that can run and is neither marked `meant`
nor on the list, an open check, a stale mark or an unused reason fails the
gate; `--no-checks` leaves it out on purpose, saying so. Its line gives
the totals and the list's count:

    [  ok  ] checks   1985 checks hold    47 fallbacks never run    125 can run    0 open    991 meant; 125 entries against ../../corpus/checks/baseline.tsv: 0 new, 0 gone. (49 s)

Held to fail: with one entry taken out of the list, `scripts/checks.sh`
exits 1 and names it (`NEW 1 Main atTab the Nothing branch reachable`).
It takes 49 s, under 16 GB of memory.

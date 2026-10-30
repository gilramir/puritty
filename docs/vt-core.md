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
| the core | `vt/` (`github.com/gilramir/visiterm-vt`, `runtime = "any"`) | `Vt`: `new`, `feed`, `takeReplies`, `resize`, `dump`; `Vt.Width`, generated |
| the core's dump | `harness/dump/` (`core-dump COLS ROWS FILE [CHUNK [RESIZES]]`) | feeds a file to a `Vt.Term`, a read of `CHUNK` bytes at a time, resized where `RESIZES` says (§VC14), and prints §VC3 |
| the oracle | `harness/oracle/` (`ghostty-dump COLS ROWS FILE [RESIZES]`) | the same for libghostty-vt at the vendored v1.4.0 (`83fb95624`; `d8619f1bc` before §VC15) with `patches/` applied (V12, §VC17), through its C API; `widths`, its width table (V13) |
| the gate | `harness/replay.py`, `corpus/replay/` | §VC4 |
| the timing | `harness/bench/` (`core-bench FILE [dump \| resize COLS ROWS]`) | §VC7, §VC14 |
| esctest2 | `harness/esctest.py`, `harness/esctest/` (`core-pty`, `ghostty-pty`), `corpus/esctest/` | §VC10 |
| the fuzzer | `harness/fuzz.py`, `harness/fuzz/` (`vt-fuzz`, `vt-min`), `corpus/fuzz/runs.tsv` | §VC11 |
| the differential fuzzer | `harness/fuzz.py --diff`, `harness/fuzz/` (`vt-diff`, `vt-diff-min`), `corpus/fuzz/diff-runs.tsv` | §VC16, §VC17, §VC18, §VC19 |

`Vt`'s interface, as it stands:

```gren
new : Config -> Term                       -- { cols, rows, scrollback, checksums }
feed : Bytes -> (moved t : Term) -> Term   -- one read's bytes
takeReplies : (moved t : Term) -> { term : Term, replies : Array Bytes }
resize : Int -> Int -> (moved t : Term) -> Term   -- cols rows, §VC14
dump : Term -> String                      -- §VC3
historyBound : Term -> Int                 -- for the differential fuzzer, §VC17
```

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
attribute Ghostty keeps, 256 and RGB colours with either separator, the
underline's kind and colour; erases and scrolls in the background colour;
DECSC/DECRC and SCOSC/SCORC per screen; modes 4, 20, ?6, ?7, ?25, ?47,
?1047, ?1048, ?1049 (the alternate screen kept once made, as xterm and
Ghostty keep it), and every other private mode recorded for DECRQM, KAM and
SRM recorded and the ANSI modes xterm lacks answered as permanently reset;
XTSAVE and XTRESTORE; DECSCUSR; reverse wraparound, ?45 and ?1045, for BS
and CUB; protected cells, DECSCA, SPA and EPA, against DECSED, DECSEL and in
ISO's mode ED, EL and ECH; the palette and the foreground, background and
cursor colours set, queried and reset (OSC 4, 10–19, 104, 110–112); left and
right margins, ?69 and DECSLRM, for printing, every scroll, IL, DL, ICH,
DCH, CR, the cursor's moves and reports, tabs and DECRQSS (§VC13); RIS and DECSTR; OSC 0 and 2 (the title);
DECRQSS for `m`, `r` and ` q`; DSR 5 and 6, DECXCPR, DA1 and DECID, DA2, DA3,
XTVERSION, XTWINOPS 18 (the size in cells), DECRQCRA when the embedder asks
for it (V5); the main screen's scrollback in D901's pages (§VC6); resize,
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
  empty cell as a 0 byte, a spacer head as 0xFF (V9, §VC14), a cell in a
  background colour alone as 0xFE (§VC17), a wide character's spacer as
  nothing, and a protected cell's text followed by 0xFD (§VC19);
- **heads**: for each row a header, two bytes low first: its extent in bits
  0–13, bit 14 set when every cell is in the default style, bit 15 when the
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

### At phase 1's exit

Measured again once the rest was built (2026-10-30, at 69dcf7e: §VC10's
sequences, §VC12–§VC14's wraparound, protection, colours, margins and
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
- **X11's colour names** in OSC 4 and 10–19 (`red`, `DarkSlateGray`):
  Ghostty takes several hundred, from its `x11_color.zig`; the core takes
  none and leaves the colour as it was. No esctest test names one. A table
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
- **A page cut at another width is reflowed at every read** (V10): one
  read in `dump`, but phase 2's scrollback view, reading a page at a time
  as the view moves, would reflow it each time, and the scrollbar wants the
  scrollback's length in rows at the screen's width, which is every page
  read. A page reflowed once could be kept, or its row count at the
  screen's width; to be measured with the view.
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
buffer. geng-lang fixed the pass (D1021, `m4-visiterm.md` §VA52); nothing
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

## VC12. Reverse wraparound, protected cells and the colours

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
- **Colours** (`osc-colours`, `osc-colours-reset`). OSC 4 sets or queries
  palette entries in pairs, OSC 10 to 19 the dynamic colours from the one
  named on, OSC 104 resets entries or all, and OSC 110 to 112 the
  foreground, background and cursor. A query answers `rgb:` with 16 bits a
  channel, all of one request's answers in one reply, ended with BEL or ST
  as the request was. The core keeps only what was set (`colours`) and
  computes the rest: libghostty-vt's palette (its 16, the cube, the grey
  ramp), and no foreground or background until one is set, as
  libghostty-vt has none unless its embedder gives one; the cursor's is the
  foreground's when it has none. A colour is parsed as Ghostty parses it,
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
the terminal is resized.** A page keeps the width its rows were cut at
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
another width to the screen's when it is read (`dump`, a pull), the same
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
| a line's cells | `cols-widen-unwraps`, `-narrow-wraps`, `-trailing-blanks`, `trailing-spaces`, `empty-rows-kept`, `cols-styles`, `-erase-colour`, `-mark`, `-round-trip`, `both-shrink`, `both-grow` |
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
v1.4.0 needs Zig 0.17, and visiterm's devbox had 0.16 from the nixpkgs
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
export and changes no screen, and that a cancelled or aborted APC is thrown
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
- **RIS keeps OSC 12's cursor colour** in Ghostty; the core resets it.
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
  `2` and three colours, with colons three or four joined parameters and
  any other count skipped; anything short of that passes over the `38`
  alone, so `38;5` is blink.
- **Strings** (`strings-dcs-osc`): an OSC's text that is not UTF-8 is still
  read, a high byte as one no command or colour has; the core had dropped
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
  (`alt-1049-again`); **RIS** keeps OSC 10–19's colours, as DECSTR does
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
  (`dcs-cancelled`). A high byte in a string that is not UTF-8 stands as
  0x01, where it stood as `?`, which OSC 4 and 10 read as a query. OSC 4's
  indexes 256 to 260 are Ghostty's special colours, passed over
  (`osc-colour-edges`).
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
  pen's colours, and fills in them (`decaln-pen`). HPR and VPR by 0 move as
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
  no text is blank though its cells are coloured (`resize-trim-bg-rows`).
  A saved cursor never set is carried as none (`resize-none-saved`). A
  cursor whose row a shrink of the alternate screen drops goes to the top
  left, column 0 too (`resize-alt-cursor-dropped`). A wide character in one
  column is an empty cell in no style, as Ghostty's reflow writes it before
  it copies a style (`resize-wide-one-column-style`).
- **An empty cell is Ghostty's `isEmpty`.** A reflow drops a line's
  trailing empty cells whatever their style, but keeps a cell an erase left
  in a background colour, which Ghostty keeps as a `bg_color` cell. Every
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
  from the pruned rows is cut into rows differently too.

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
erase in a background colour; a wide character at the last column with
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
  (`da-two-intermediates`). XTVERSION's name, `visiterm` against
  `libghostty`, is an identity, not a difference: `diff.h` writes the core's
  name into Ghostty's reply before it compares.
- **OSC.** A colour's index is decimal digits only, as Ghostty's
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
  the erase colour, protected or not, as Ghostty's `splitCellBoundary`
  does, though its own TODO says protection should count; the core copies
  it (`ech-split-protected-wide`, `insert-margins-wide-tail`).
- **Spacer heads.** ECH, EL and DCH begin as Ghostty's `cursorResetWrap`:
  a row that wrapped is unwrapped, and a spacer head at its end becomes a
  cell in the erase colour (`ech-reset-wrap-spacer-head`). At column 0 or
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
head, a background colour alone): `vte-scrolling` 1.4% more instructions,
`gitlog` and `ls` 0.7%. One test now finds a plain cell, the commonest: a
mask of every bit that makes a cell more than its code point (`packSpecial`,
the width and cluster bits, `bgBit` and `protectBit`), and anything else
goes to `packOther`. That is fewer instructions than before on everything
that pages: `gitlog` 8.6%, `ls` 10.4%, `vte-scrolling_fullscreen` 11.9%.
The mask has to be written as a literal, `0x3E00000`: written as
`Bitwise.or 0xE00000 (Bitwise.or bgBit protectBit)` it is a top-level value
the program computes on first use, and each read of it in the loop cost
about 17 instructions, 331 M on `gitlog` (geng-lang `m4-visiterm.md`
§VA54).

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
the minimizer's two minutes) and grouped but not yet fixed:

- **The window's size in pixels.** `CSI 14 t` and `CSI 16 t`, and mode
  2048's report of the size, answer in pixels, which the oracle's callback
  gives as ten by twenty a cell and the core has no number for (3).
- **A wide character in a reflow, a resize to one column among them**:
  rows that start a column later or earlier in one than the other, and a
  history a row longer (14).
- **The alternate screen's clears.** `?1047l` clears the alternate screen
  in the erase colour, which `?47h` then shows; the core's rows come back
  without it (3).
- **A wide character written past the right margin of a one-row screen**
  with left and right margins (2), **DL and DCH over a wide character** (1),
  **OSC 104 with an index past 255** (2), **the saved cursor after three
  resizes** (1), and **an underline one cell short** (1).

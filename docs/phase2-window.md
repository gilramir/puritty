# Phase 2 · A window on X11: a survey

Status: **survey begun 2026-10-30; nothing of the window is built. Gilbert
took §8's first three leanings the same day (§10: D1024, V18, V19).** Phase 2
of [`geng-plan.md`](geng-plan.md) §6 starts here, as every phase does, by
measuring before building. It asks three things first, the three that
decide the shape of the rest: how a renderer reads the core's screen now
that the screen is written in place (§3), whether a pty fits Geng's one
loop (§4), and what a frame costs on the wire when the display list is
drawn with XRender (§5). Fonts, shaping, input and the remote case come
after (§7). As with every survey here, these sections stay as written when
the work lands below them.

Gilbert's answer to Q13 came with the request to start (2026-10-30):
visiterm ships no fonts and uses the system's (`geng-plan.md` §9.3).

---

## 1. What was asked, and what was found

| asked | found | § |
|---|---|---|
| How does a renderer see what changed, now that the screen is one `Array.Builder` written in place? | **By keeping its own copy of what it drew and diffing the screen against it each frame**, as PuTTY does. It cannot keep last frame's handle: a builder is used once (geng-lang D963), and the compiler refuses a second use. The diff costs 26–33 µs a frame on `ls` and `gitlog` and 73–80 µs when every cell changed, against a 16 ms frame | 3 |
| Can the renderer find scrolls without the core recording them? | **Yes, by content**: a hash per row, matched against last frame's at every shift. The core's ring slots are not enough: the core settles a region's turn by moving rows, and vim's scrolls went unseen (12 KB a line) until the renderer hashed rows (377 B a line) | 3.2, 5.2 |
| Does a pty fit the one loop? | **Yes.** `posix_spawn` with `POSIX_SPAWN_SETSID` and the slave opened as fd 0 gives the child its controlling terminal with no code between `fork` and `exec`; the master is read through `geng_io_wait`. `cat` of `ls` through the pty and the core takes 150–161 ms, against Alacritty's 236–268 drawing in a window. A frame every 16 ms changes nothing measurable | 4 |
| What does a frame cost on the wire? | **374 B a line of a vim scroll, 331 B a line of `tail -f`, 10–14 KB a frame of `htop` or a `cat` that outruns the screen**, plus 35 KB to open the window. A full image of the same window is 4.9 MB. The draw path makes no round trip: 1,124 bytes come back from the server in every run, all of them at connection setup | 5 |
| What does Geng need? | Nothing new to start. Two ownership shapes were refused that only read the screen, a field bound to a local and a lambda handed to `Array.initialize`, both worked around with a loop (§3.3). Whether a pty belongs in `os` is a question for Gilbert (§8) | 3.3, 8 |

---

## 2. How it was measured

Machine as `geng-plan.md` §1.2: AMD Ryzen 7 8845HS, 16 threads, Linux 6.8.
visiterm `757c4ff`, geng-lang `685c6f43`, the compiler fork at `0a907d06`,
devbox's clang at `-O2` with the passes `harness/bench/build.sh` builds
`core-bench` with. The inputs are `geng-plan.md` §1.2's thirteen, byte for
byte.

**Not idle.** A four-hour differential fuzzer run was going on six of the
sixteen threads throughout (§9). The core alone took `ls` in 97–105 ms here
where `vt-core.md` §VC22 has 80–84, so every absolute time below is about
1.2–1.5× an idle one. The comparisons are within one session and one load:
a probe with and without a frame, the pty probe beside `pty.py` run the same
hour.

**No desktop.** Nobody was logged in to the desktop: `:0`'s socket accepts
a connection and never answers the setup. Every X measurement is on devbox's
Xvfb 21.1.24, `-screen 0 1920x1080x24`, which has RENDER, MIT-SHM, Present,
XKEYBOARD and DAMAGE among its 22 extensions. Bytes on the wire do not
depend on the server; time to draw does, and is not measured here.

The probes are in [`../probes/geng/`](../probes/geng/), each with its
`build.sh`:

- `view/`: `Vt.View`, the renderer's Geng side, built beside a copy of the
  core's modules (`vtp/sync.sh` copies them, since it needs `Vt.Screen`,
  which `Vt` does not expose), and `view`, the core fed in 64 KB reads with
  and without a frame after each;
- `pty/`: `Pty`, two rows that start a program on a pty and read its master,
  and `pty`, `cat FILE` through it into the core;
- `x11/`: `X`, the C that draws a display list with XRender, and `x11`, a
  program on a pty drawn in a window; `run.sh` runs the workloads with
  `xcount.py` counting the X connection's bytes between the probe (`:78`)
  and Xvfb (`:77`).

---

## 3. How the renderer reads the screen

The plan (§3.3) expected immutable rows, where "the render snapshot is
free": the renderer would keep last frame's rows and compare them by
identity. Phase 1 found immutable rows too slow (`phase1-core.md` §3), and
the core's screen is one `Array.Builder Int64` written in place, a ring of
rows (`vt-core.md` §VC2). Three ways for a renderer to see what changed:

1. **Keep last frame's handle.** D903 made a builder persistent, so an old
   handle could be read; D963 since made a builder affine, and the compiler
   refuses a second use. Not available; and while it was, a held older
   handle made each write record a diff (`m4-visiterm.md` §VA10).
2. **The core records damage**: a dirty flag per row, scroll deltas, cleared
   by the renderer. A write on every path that changes a row, measured
   against D902's budget, which the core meets on `cup` by less than a
   tenth (50–52 ms against 56, `vt-core.md` §VC22).
3. **The renderer keeps a shadow of what it drew** and diffs the visible
   screen against it each frame (PuTTY, S§6.2). The core does nothing more;
   the renderer pays a read of every visible cell per frame.

The probe measures 3, since it costs the core nothing and 2 only pays if 3
is too slow.

### 3.1 The diff

`Vt.View.frame : Term -> Shadow -> { shadow, list }` reads each visible row
through `rowOffset` and `extentAt`, compares each cell with the shadow's,
and writes a run for each stretch of changed cells, gaps of fewer than four
unchanged cells merged in so that an overhanging glyph is redrawn with its
neighbour. The list is `Bytes`: a run is its row, column and length and each
cell's code point and style id, five bytes a cell; a scroll is its band and
shift.

The core fed in 64 KB reads at 160×50, alone and with a frame after every
read, three runs each, ms. A frame per read is the worst case: at 60 frames
a second a `cat` of `gitlog` makes about 14 frames, not 394 (§4).

| input | core alone | with a frame a read | frames | cells drawn a frame | µs a frame |
|---|---:|---:|---:|---:|---:|
| `gitlog` | 133–135 | 146–148 | 394 | 2,494 | 33 |
| `ls` | 97–98 | 106–108 | 371 | 553 | 26 |
| vte-light_cells | 13–15 | 23–24 | 124 | 8,000 | 80 |
| vte-scrolling_fullscreen | 29–31 | 38–40 | 123 | 7,959 | 73 |
| vte-unicode | 20–21 | 30–31 | 123 | 7,902 | 80 |
| vte-scrolling_top_small_region | 127–129 | 131–133 | 123 | 65 | 33 |

A frame that redraws the whole screen costs about 80 µs, 10 ns a cell,
half of one percent of a 16 ms frame. The first version of the probe,
without row hashes, ran all thirteen inputs with the same shape (cup 2.5 ms
over 280 frames; no input over 75 µs a frame).

### 3.2 Scrolls

S§6.2: "Scroll detection must exist in the core. The renderer needs 'the
viewport moved up N rows', not 'every row is dirty'." A scroll found is one
`CopyArea` and the new rows; a scroll missed is every row redrawn.

The probe's first version found scrolls from the ring: a row that moved up
`k` rows sits in the same ring slot, `k` rows higher, so the renderer kept
each row's slot and looked for the shift. It found the scrolls of
`vte-scrolling_top_small_region` (122 in 123 frames) and of `tail` (226 in
251), and **none of vim's**. For each line vim sets a region of rows 1–48,
deletes its top line with `DL` (`ESC [M`) and resets the region (captured
with `script`), and when the region is reset the core settles its turn by
moving the rows (`Vt.Screen.settle`), so a slot is not a row's identity
across a frame. vim's scroll by a line cost 12 KB on the wire (§5.2).

The second version finds scrolls by content. Each frame it hashes every
visible row (its cells to its extent, and the extent) and, for every shift
`k` up and down, finds the longest band of rows whose hashes are last
frame's moved by `k`, at least two of them not blank. The band is one
`CopyArea`, in the shadow as in the window, and the diff draws what is left.
A false match costs a copy, then the diff draws over it: the shadow says
what the pixels show, so the result is never wrong. It found 298 of vim's
300 scrolls each way, and costs what §3.1's table shows, the hashing and the
search over 98 shifts included.

The rows a scroll vacates keep their pixels, so the shadow keeps their
cells. The first version marked them unknown, which redrew them whole:
`tail` went from 836 to 331 bytes a line when that was fixed.

**Leaning: the renderer finds scrolls, the core records nothing.** It costs
the core nothing, it sees a scroll however the program made it (a region,
`IL`/`DL`, a full redraw of moved text), and it is cheap enough. The core
recording deltas stays the fallback if a measurement asks for it.

### 3.3 What Geng said about it

Two ways of reading the screen that only read were refused by the
ownership checker, each worked around in a line:

- `let s = t.screen` and then `t.screen` again: binding the field to a
  local takes the builder in it, so the second read is a second use. Known:
  D1022 chose to substitute such a binding in the inliner, after the
  checker, so source still refuses it (geng-lang register, "D1021's alias").
  The probe passes `t.screen` to each call.
- `Array.initialize rows 0 (\y -> rowHash t.screen …)`: "A function that
  captures `t.screen.cells` is handed to `Array.initialize`, which may call
  it more than once", though `rowHash` only reads. D928's borrowing
  callbacks would cover it if `initialize`'s callback were one. The probe
  pushes the hashes in a loop.

Neither blocks anything. They are the shapes a renderer reading the core
will write first, so they go in geng-lang's register as one item
(`m4-visiterm.md` §VA56).

The renderer reads `Term`'s fields and `Vt.Screen`'s functions, which `Vt`
does not expose; the probe builds beside a copy of the modules. The real
API is a choice for the build: `Vt.View` in the core's package, or a
narrow read interface (`Vt.rowCells`, `Vt.rowExtent`) for a renderer
elsewhere.

---

## 4. The pty

`Pty.spawn cols rows argv` opens a master with `posix_openpt`, sets its size
with `TIOCSWINSZ` and starts the child with `posix_spawnp`:
`POSIX_SPAWN_SETSID`, the slave opened as fd 0 without `O_NOCTTY` (a
session leader opening a terminal acquires it as its controlling terminal),
`dup2` to 1 and 2, an empty signal mask and default dispositions, as `os`
starts a child. Nothing of visiterm's runs between `fork` and `exec`, which
was the plan's reason for putting the child side in C (`geng-plan.md` §3.2):
glibc's spawn
does it. `POSIX_SPAWN_SETSID` is glibc 2.26, so RHEL8's 2.28 has it.
`Pty.read` reads the non-blocking master, and when it has nothing waits in
the scheduler's `poll` through `geng_io_wait`; a read of `EIO` is the end
(every slave descriptor closed).

`cat FILE` on a 160×50 pty into the core, three runs each, ms; and in the
same hour `pty.py`, which reads and discards (`geng-plan.md` §1.2's
floor), and the core alone (§3.1's `view`):

| input | `pty.py` | core alone | pty and core | with a frame each 16 ms (frames) |
|---|---:|---:|---:|---:|
| `ls` | 74–102 | 97–105 | 153–160 | 150–161 (9–10) |
| `gitlog` | 176–217 | 133–137 | 212–225 | 217–222 (13) |
| `cup` | 22–41 | 77–78 | 89–94 | 91–95 (5) |
| vte-dense_cells | — | 25–26 | 34–37 | 33–35 (2) |

For `gitlog` the pty and the core together take about what the pty alone
does: the kernel's `ONLCR` work in `cat`'s writes (`geng-plan.md` §1.2)
runs while the core parses. For `ls` and `cup` the sum shows. Alacritty in a window, from
`geng-plan.md` §1.2: `ls` 236–268, `cup` 107–113, `gitlog` 309–314; those include its
drawing and a shell's `cat`, so they are the bar the whole of visiterm has
to meet, not this probe alone. What the probe says is that the loop, the
rows and the core leave the room.

`gitlog` came in 27,000–42,000 reads, about 700 bytes each: the core keeps
up with `cat`, so each `poll` finds what the kernel had. A read is a `Task`
and a copy into a new `Bytes`; at that count it is within the noise.

---

## 5. The X side

### 5.1 The probe

`X.open` connects with libxcb, opens a window of 160×50 cells of DejaVu Sans
Mono 11 (fontconfig finds it; FreeType at 96 dpi gives a 9×17 px cell), and
makes a pixmap of the same size, an A8 glyph set and a RENDER picture on the
pixmap. `X.draw` executes a display list into the pixmap: a scroll is one
`CopyArea` within it, a run one `RenderFillRectangles` for its background
and one `RenderCompositeGlyphs32` for each stretch of one foreground colour,
and a glyph not seen before is rasterised and sent with `RenderAddGlyphs`,
its id its code point. Then one `CopyArea` puts the rows the frame touched
on the window, so an expose needs no redraw (S§6.2's retained pixmap). It
flushes and drains events, and waits on no reply.

The x11 probe runs a program on the pty, feeds the core, writes the core's
replies back to the pty (vim and htop ask), and draws a frame when a read
comes 16 ms or more after the last frame, and once at the end.

Left out, and so not in the numbers: shaping, fallback fonts, wide glyphs at
two cells, the cursor, the style table's real colours (a style id picks a
colour from a palette, which costs the same requests), events and input.

### 5.2 Bytes per update

`xcount.py` between the probe and Xvfb; bytes to the server, and from it.
The window costs 35,460 bytes to open, nearly all of it the first frame
(§6), so each row below has it taken off before dividing.

| workload | what it does | frames | scrolls found | to the server | a unit |
|---|---|---:|---:|---:|---|
| idle (`sleep 3`) | opens the window | 1 | — | 35,460 | — |
| `tail` | 500 log lines, one each 10 ms | 251 | 226 | 200,908 | **331 B a line** |
| vim, `Ctrl-E` ×300 | `Vt.geng` with `syntax on`, `set nu` | 301 | 298 | 147,668 | **374 B a line** |
| vim, `Ctrl-Y` ×300 | the same, upward | 301 | 298 | 149,712 | **381 B a line** |
| `htop`, 10 s | its default screen | 9 | 5 | 128,228 | **10.3 KB a frame** |
| `cat` of `gitlog` | 26.3 MB in 208 ms | 14 | 0 | 225,416 | **13.6 KB a frame** |

From the server, 1,124 bytes in every run, the same however long the run:
the replies at opening (the setup and RENDER's queries), and nothing in the
draw path.

Before §3.2's hashes the same vim scroll cost 3,689,672 bytes, 12.2 KB a
line, every row redrawn; `tail` cost 453,356, 836 B a line.

**Against S§6.1.** The GL terminals over `ssh -X` send an image a frame;
this window's is 1440×850×4 = 4.9 MB. A vim scroll here is about
1/13,000th of that, and a `cat` that outruns the screen 1/360th, since at
most one frame in 16 ms is drawn and it is drawn as text.

### 5.3 Where the bytes go, and what is cheap to take off

Not measured request by request yet (`xtrace` is in devbox for that). From
the request sizes: a run of `n` cells is a 28-byte fill and 28 + 4n bytes of
glyphs, so text is about 4 bytes a cell. Three changes would each cut it,
none needed for the exit:

- **16-bit glyph ids** (`CompositeGlyphs16`, ids assigned per glyph set
  rather than code points): 2 bytes a cell.
- **No glyph for a blank cell**: the fill draws it. Splits the element.
- **A first frame from a blank shadow**: the pixmap starts filled, so the
  shadow can start blank instead of unknown, and the first frame draws only
  what is not blank: the 35 KB of opening falls to about 1 KB.

---

## 6. The environment

- **Fonts on this machine** (Q13: the system's are what visiterm uses).
  `fc-match monospace` is DejaVu Sans Mono. Present: Noto Sans Mono CJK in
  all five regions (JP, KR, SC, TC, HK) and Noto Sans CJK, Noto Sans Thai,
  Noto Serif Thai, Noto Looped Thai, Noto Color Emoji, Droid Sans Fallback,
  Ubuntu Mono, Liberation Mono. 542 fonts in all, and devbox's fontconfig
  2.18.3 sees the same 542 with no configuration. C§9's corpus can be drawn
  from what is installed; the rendering tests still pin their own copies
  (Q13).
- **X servers.** The desktop's `:0` did not answer (§2). devbox's Xvfb works
  and is what the gates can use; it has no GPU, as ETX has none. A run on
  the real desktop waits for Gilbert to be logged in, and is needed for the
  exit (§7).
- **Libraries.** `[native] pkg-config` (D890) built the probe's C against
  devbox's libxcb 1.17.0, xcb-render-util 0.3.10, FreeType 2.14.3 and
  fontconfig 2.18.3 with no flags by hand.

---

## 7. What is not measured yet

In the order the build will meet them:

1. **The loop**: a frame timer. The probe draws only when a read comes, so
   output that stops inside a frame waits for the next read (the first
   screenshot was black for that reason). The real loop needs "a frame is
   due" as a timer in the same `poll`, with the paint cooldown and the
   synchronized-output timeout (`geng-plan.md` §3.1), and X events read
   through `geng_io_wait` on the connection's fd.
2. **Shaping and fonts**: HarfBuzz per run, its cost a frame; fallback by
   fontconfig on a C thread (G5); the ideograph-width fit; Thai and SARA AM
   with ink extents (C§4.3); the Han language per profile; procedural box
   drawing. These change the display list from code points to glyph ids
   and positions, and the bytes per cell with it.
3. **Input**: keys through xkbcommon, and the latency from a key to its
   pixel.
4. **Time to draw** on a real server, the desktop's and ETX's, and the
   frame pacing S§6.2 asks for ("latest frame wins").
5. **`ssh -X` from another host**, which the exit asks for: needs a second
   host (§8).
6. **A reference**: xterm under the same proxy on the same workloads, so
   that the bytes per update have a bar beside them.
7. **GC**: pauses with the renderer's allocation (a display list a frame)
   on top of the core's, against G7's 16 ms and 4 ms.

---

## 8. For Gilbert

1. **Where the pty lives.** The plan (§5) has a `pty` package of C rows. The
   probe shows the child side is `os`'s spawn with one flag and one file
   action, and the parent side `os`'s pipe handle with `TIOCSWINSZ` beside
   it. **Leaning: put it in `os`**: a `Connection` that is a terminal of a
   given size, its master a handle that reads and writes as a pipe's does,
   and a resize. It keeps one copy of the pidfd, reaping and signal-mask
   logic (`m3-os.md` D527, D531, D774) instead of a second in visiterm, and
   it is something `os` lacks for anyone. It is a geng-lang decision.
2. **Scrolls found by the renderer** (§3.2). Leaning: the renderer, by row
   hashes; the core records no damage and no deltas. Revisit only if a
   measurement asks.
3. **The renderer's read of the core** (§3.3). Leaning: `Vt.View` in the
   core's package, so it reads the screen's own representation with no
   copy; its display list is the boundary to C.
4. **A second host for `ssh -X`.** Which machine should run visiterm
   remotely for the exit's measurement? Until then, an X connection over
   TCP on this machine stands in for the bytes, which are the same, and not
   for the latency.

---

## 9. The fuzzer run alongside

Started with the survey: the differential fuzzer, four hours on six jobs at
`757c4ff` (`fuzz.py --diff --hours 4 --jobs 6`). It stopped after 66
minutes on six findings: a reflow quadratic in a line's rows, and a gap in
the harness's rule for a pruned scrollback, both fixed (`vt-core.md`
§VC24); `corpus/fuzz/diff-runs.tsv`'s third row. A second run, the four
hours at `4163c3e`, found the harness's gap again inside one read; the core
now says when its scrollback reached the limit (§VC25, the fourth row).

---

## 10. Gilbert's answers (2026-10-30)

Gilbert took §8's first three leanings. The fourth, the host for `ssh -X`,
is open.

**D1024 (geng-lang) · A pty is `os`'s.** `Os.Process` starts a program on a
pty as a terminal `Connection` of a given size; the master is a handle that
reads and writes as a pipe's does, and resizes (geng-lang `m4-visiterm.md`
§VA57). visiterm has no `pty` package (`geng-plan.md` §5). It is built in
geng-lang, designed first in `m3-os.md`; until then §4's probe stands in.

**V18 · The renderer finds scrolls; the core records no damage.** The
renderer keeps a shadow of what it drew and a hash of each row, diffs the
screen against the shadow each frame, and finds a scroll as the longest
band of rows whose hashes moved by one shift (§3.2). The core keeps no
dirty flags and no scroll deltas, so its throughput is untouched. If a
measurement later asks for it, the core recording deltas is the fallback.

**V19 · `Vt.View` lives in the core's package.** It reads the screen's own
representation (`Vt.Screen`, `Term`'s fields) with no copy and no wider
API for it; its display list, `Bytes`, is the boundary to the C that draws
(§3.1, §5.1). `Vt` exposes `Vt.View` beside itself.

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
puritty ships no fonts and uses the system's (`geng-plan.md` §9.3).

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
puritty `757c4ff`, geng-lang `685c6f43`, the compiler fork at `0a907d06`,
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
   handle made each write record a diff (`m4-puritty.md` §VA10).
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
neighbor. The list is `Bytes`: a run is its row, column and length and each
cell's code point and style id, five bytes a cell; a scroll is its band and
shift. *Since §13 a cell carries its width state and its cluster's code
points.*

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
(`m4-puritty.md` §VA56).

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
starts a child. Nothing of puritty's runs between `fork` and `exec`, which
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
drawing and a shell's `cat`, so they are the bar the whole of puritty has
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
and one `RenderCompositeGlyphs32` for each stretch of one foreground color,
and a glyph not seen before is rasterized and sent with `RenderAddGlyphs`,
its id its code point. Then one `CopyArea` puts the rows the frame touched
on the window, so an expose needs no redraw (S§6.2's retained pixmap). It
flushes and drains events, and waits on no reply.

The x11 probe runs a program on the pty, feeds the core, writes the core's
replies back to the pty (vim and htop ask), and draws a frame when a read
comes 16 ms or more after the last frame, and once at the end.

Left out, and so not in the numbers: shaping, fallback fonts, wide glyphs at
two cells, the cursor, the style table's real colors (a style id picks a
color from a palette, which costs the same requests), events and input.

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

- **Fonts on this machine** (Q13: the system's are what puritty uses).
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
   and positions, and the bytes per cell with it. *Surveyed 2026-11-02:
   §13.*
3. **Input**: keys through xkbcommon, and the latency from a key to its
   pixel. *Surveyed 2026-11-02: §14.*
4. **Time to draw** on a real server, the desktop's and ETX's, and the
   frame pacing S§6.2 asks for ("latest frame wins").
5. **`ssh -X` from another host**, which the exit asks for: needs a second
   host (§8).
6. **A reference**: xterm under the same proxy on the same workloads, so
   that the bytes per update have a bar beside them. *Measured 2026-11-02:
   §16, with st and alacritty beside it.*
7. **GC**: pauses with the renderer's allocation (a display list a frame)
   on top of the core's, against G7's 16 ms and 4 ms. *Measured 2026-11-02: §15.*

---

## 8. For Gilbert

1. **Where the pty lives.** The plan (§5) has a `pty` package of C rows. The
   probe shows the child side is `os`'s spawn with one flag and one file
   action, and the parent side `os`'s pipe handle with `TIOCSWINSZ` beside
   it. **Leaning: put it in `os`**: a `Connection` that is a terminal of a
   given size, its master a handle that reads and writes as a pipe's does,
   and a resize. It keeps one copy of the pidfd, reaping and signal-mask
   logic (`m3-os.md` D527, D531, D774) instead of a second in puritty, and
   it is something `os` lacks for anyone. It is a geng-lang decision.
2. **Scrolls found by the renderer** (§3.2). Leaning: the renderer, by row
   hashes; the core records no damage and no deltas. Revisit only if a
   measurement asks.
3. **The renderer's read of the core** (§3.3). Leaning: `Vt.View` in the
   core's package, so it reads the screen's own representation with no
   copy; its display list is the boundary to C.
4. **A second host for `ssh -X`.** Which machine should run puritty
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
reads and writes as a pipe's does, and resizes (geng-lang `m4-puritty.md`
§VA57). puritty has no `pty` package (`geng-plan.md` §5). It is built in
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

---

## 11. The pty is `os`'s (2026-11-02)

D1024 is built in geng-lang (`m3-os.md` §OS25, §OS26, D1042–D1044):
`Os.Process.spawn` with `Terminal { columns, rows, utf8 }`, the master an
`Os.File` handle whose read answers the end on `EIO`, and
`Process.resize`. §4's probe now uses it, and `probes/geng/pty/pkg`, its
`Pty` package and C, is gone. Against the probe on that package, both on
the core at b912f76: the same bytes and screen, `ls` 115–153 ms against
111–150, `cup` 87–91 against 87, `gitlog` a median of 203.5 against 196.0
over ten runs each in turn, in the same instructions and CPU time; its
reads fall differently from run to run on either. The probe's
`Vt.new` call now gives `scrollbackBytes`, as the core's `Config` asks;
it had not been built since the core changed it.

---

## 12. The loop: a survey (2026-11-02)

§7's first item. §5's probe draws only when a read comes, so output that
stops inside a frame waits for the next read. The plan (`geng-plan.md`
§3.1) has one loop on Geng's one thread, waiting on the terminal, the X
connection and the frame's timer at once. The probe now has both loops:
`x11 read`, §5's, and `x11 race`, in which each turn is a `Task.race` of
`Os.File.read` on the terminal, `X.events`, and, while a read is not drawn
yet, `Process.sleep` until the frame is due (16 ms after the last). A read
that comes when a frame is due draws it at once, as before. `X.events` is a
`geng_io_wait` on xcb's descriptor, answered at once when xcb has already
queued events (it reads the socket in its own calls, a flush or a reply,
so the descriptor can be quiet with events waiting). An expose is redrawn
from the pixmap in C. All runs on Xvfb on this machine, `DISPLAY=:77`, no
proxy, the core at b9bebb2.

### 12.1 Frames that came late

A frame's lateness is the time from the first read it shows to the frame.
`burst.py` writes two lines 5 ms apart, then is quiet for 300 ms, twenty
times; `tail` is §5's line every 10 ms.

| | `read`: frames | late, max / mean | `race`: frames | late, max / mean |
|---|---|---|---|---|
| burst | 20 | 306 / 300 ms, all 20 over 16 | 40 | 12 / 5 ms, none over 16 |
| tail | 250 | 20 / 10 ms | 316 | 17 / 10 ms |
| `gitlog` | 15 | 16 / 15 ms | 15 | 16 / 15 ms |

Under `read`, each burst's second line is drawn with the next burst, 300
ms on. Under `race`, the timer draws it. On the throughput inputs the
frames under `race` are 16 to 21 ms late at most: a timer that is due
waits for the read being fed to the core.

### 12.2 What a turn costs

Five runs each, `perf stat` over the probe and `cat`, medians:

| input | loop | instructions | CPU | wall | reads |
|---|---|---|---|---|---|
| `gitlog` | read | 3,890 M | 389 ms | 200 ms | 46,071 |
| | race | 4,342 M | 416 | 216 | 23,719 |
| `ls` | read | 3,112 M | 221 | 121 | 2,022 |
| | race | 3,176 M | 227 | 126 | 1,979 |
| `vte-scrolling` | read | 5,258 M | 1,351 | 747 | 612,748 |
| | race | 10,507 M | 1,531 | 807 | 314,051 |
| `cup` | read | 2,224 M | 127 | 89 | 4,412 |
| | race | 2,342 M | 133 | 97 | 4,336 |

`vte-scrolling` comes 17 bytes a read, so it is the worst case: twice the
instructions and 8% of the wall time. Each branch priced on it, three runs
(`x11 race1`, the read raced alone; `race2`, the read and the X events):

| race of | instructions over `read`, a turn | wall |
|---|---|---|
| the read | 8,300 | 737–779 ms |
| the read, the X events | 12,600 | 793–805 |
| the read, the X events, the timer | 16,900 | 801–807 |
| (`read`, no race) | | 737–750 |

The race's own processes cost the most, a process a branch spawned and
canceled each turn; the X wait and the timer, a `poll` entry and a heap
entry made and canceled each turn, the rest. A slower loop reads less
often and more each time, so the reads fall to half. The byte counts are
the same in every run.

### 12.3 What a race loses

Racing a read is safe only if the race never drops what a branch took.
`x11 double` races two reads of the terminal, and loses a fifth of
`gitlog`: 21,051,866, 19,476,696 and 19,387,076 bytes of 26,344,379. A read
answers at once when bytes are there, and when two branches answer in one
drain of the run queue, the loser is killed with its answer in it
(geng-lang `m3-os.md` §OS27). The probe's own loop does not lose: a read
or an event that answers from `poll`, or a timer, settles the race before
anything else runs, and `x11 stress`, with a 1 ms timer in every turn,
read every byte of 3,000 lines 0.7 ms apart in five runs (`drip.py`) and
of `gitlog` in three. But that rests on the read being the branch that
steps first, which `Task.race` does not promise. So `X.events` now answers
only that events are there and takes none, and `X.take`, after the race,
takes them; and the terminal's read waits on §OS27's question.

### 12.4 Not measured

- An expose with a real window manager: Xvfb has none, and the one
  probe counted one or two events a run, from the map.
- The paint cooldown (PuTTY's 20 ms) and the synchronized output timeout:
  the loop has the timer they need, and neither is written.
- A loop that is not a race each turn: the plan's diagram has C rows
  emitting into one `Source` and the loop reading it, with no process per
  branch. `os` cannot read a handle into a `Source`; it would need a
  reader that emits a piece and waits to be asked for the next, or the
  kernel's flow control is lost and a fast program's output queues in
  memory.
- `ssh -X` (§8's fourth question): `192.168.1.100` answers a ping in 3.7 ms
  and its `sshd` answers, but refuses this machine's key, `Permission denied
  (publickey,password)`; its ED25519 key is
  `SHA256:dTtdQoxwA6OwuJfwdIaNc/tj4nhraUbdCQ6rMIypmQI`. *Set up the same
  day, as gmktec7: §12.6.*

### 12.5 For Gilbert

1. **A race that loses nothing** (geng-lang `m3-os.md` §OS27). Leaning:
   the give-back geng-lang made for `Source` (D377), for C rows, with
   `os`'s read giving its bytes back to the handle. The loop is built on
   it.
2. **The loop is a race each turn.** Leaning: yes, as §12.1 shows it draws
   what the old loop left undrawn, for 8% of the wall time on the worst
   input. The `Source` form is registered, to be surveyed if a loop budget
   is missed, and not built now.
3. **`ssh -X` from `192.168.1.100`.** Its key is not authorized here:
   `ssh-copy-id -i ~/.ssh/id_ed25519.pub gram@192.168.1.100` from this
   machine, after checking the fingerprint above. puritty and the X
   libraries also have to build or be copied there.

### 12.6 `ssh -X` from gmktec7, and the answers (2026-11-02)

Gilbert took §12.5's first two leanings, and set up the host for the
third.

**D1045 (geng-lang) · A race loses nothing a branch took.** `m3-os.md`
§OS27's leaning, to be built there: D377's give-back for C rows, and
`os`'s read giving its bytes back to the handle.

**V23 · The loop is a race each turn**, of the terminal's read, the X
connection's events and the frame's timer (§12). The `Source` form is
registered, to be surveyed if a loop budget is missed.

**`ssh -X` works from gmktec7** (`192.168.1.100`, an AMD Ryzen 7 8845HS;
this machine is a Ryzen 9 9950X), 3.5 to 7.3 ms a ping, 4.3 on average.
gmktec7's nix store already holds every library the probe links against,
so the binary built here runs there as it is. This shell has no display,
so its `DISPLAY` was this machine's Xvfb (`:77`): the X server is here and
the program there, which is the exit's shape; the server is not a desktop's.
Three runs each, every byte read in every run:

| input | `read`: wall | late max | `race`: wall | late max |
|---|---|---|---|---|
| burst | 6,115 ms | 305–306 ms | 6,115 ms | 11–12 ms |
| `gitlog` | 299–343 | 16 | 367–381 | 16–17 |
| `ls` | 185–199 | 16 | 199–247 | 16 |
| `cup` | 150–172 | 16 | 169–187 | 16–19 |
| `vte-scrolling` | 748–759 | 16 | 860–899 | 18–19 |

The burst's frames come as they do on one machine. Throughput is slower
than §12.2's, and `race` costs more against `read` here (15% to 22% on
`gitlog` and `vte-scrolling`, against 8%): the CPU is slower, and
whether the forwarding adds to it is not separated, since gmktec7 has no
Xvfb to run the probe against locally. Not measured either: a key's
latency to its pixel over `ssh -X`, which needs input.

gmktec7 has Xvfb after all, in its nix store (`xvfb-21.1.24`, not on its
`PATH`), and the same runs against it there, three each, say the
forwarding costs nothing measurable in throughput: `gitlog` 329–355 ms
under `read` and 342–375 under `race`, `vte-scrolling` 742–745 and
858–873, as over `ssh -X`. The larger cost of `race` there is the CPU's.

### 12.7 D1045 built (2026-11-02)

geng-lang `m3-os.md` §OS28: a read that loses a race gives its piece back
to the handle, and the next read answers it. Rebuilt on it, `x11 double`
reads all of `gitlog` (26,344,379 bytes) and `vte-scrolling` (10,666,668),
three runs each, where §12.3 lost a fifth; `read` on `gitlog` takes 204–208
ms and `race` 215–228, as in §12.2. V23's loop no longer rests on which
branch steps first.

---

## 13. Shaping and fonts: a survey (2026-11-02)

§7's second item. The plan (S§6.5, C§4–§5, C§9) asks for HarfBuzz on
every run, whole clusters moved to fallback fonts, fallback found off the
loop thread, CJK fallback faces scaled to the primary cell, a CJK language
per profile, and ink that may leave its cell. §5's probe drew one glyph
per code point from one face. Two probes now measure it:

- `probes/fonts/bench`, C alone: fontconfig's matching, HarfBuzz over the
  throughput inputs, each CJK face's ideograph width, the Han forms per
  language, ink extents, and FreeType's rasterizing;
- the x11 probe, drawing as the plan says. `Vt.View`'s run record now
  carries each cell's width state and all its code points (a cluster's,
  up to 63), and a run never starts on a wide character's tail or ends on
  its head. In C:
  - a cluster the primary face lacks goes whole to the first loaded face
    that has all of it, and only then to fontconfig, asked with the
    cluster's code points and `PROBE_LANG`, the answer cached by the
    cluster's first code point;
  - clusters in one face are one HarfBuzz run, each code point's cluster
    its cell, so glyphs go back to cells by the core's widths;
  - a face with 水 is sized so 水 fills two cells without its ink leaving
    the primary cell, and a wide glyph is centered.

  `PROBE_SHAPE=0` keeps §5's drawing in the same binary, and
  `PROBE_STATS`/`PROBE_SHOT` print counts and save the pixmap.

The new run record costs `View.frame` little. The view probe, built with
the old `View` and the new one and run three times each, takes:

| input | old `View` | new `View` |
|---|---|---|
| `gitlog` | 140–162 ms | 144–145 |
| `ls` | 97–100 | 98–99 |
| `vte-scrolling` | 152–154 | 154–155 |
| `vte-unicode` | 28–30 | 32–33 |

The `vte-unicode` difference is 25 µs a frame. The list itself:

- **Size.** It is 6 bytes for an ASCII cell, against 5, and 3 for a blank
  one: `ls`'s list grew 14%, and `vte-scrolling`'s shrank 38%.
- **Wide characters.** A run widened to a whole wide character draws 0.5%
  more cells of `vte-unicode`.

`probes/fonts/corpus.txt` is C§9's test text, in a row each. `gen.py`
writes `cjk.txt` (20,000 lines of 70 ideographs and kana from 6,000 code
points, so that most of a screen is glyphs not seen before) and
`thai.txt` (20,000 lines of Thai words with stacked marks).

### 13.1 What draws right

Rendered on Xvfb and read off the screenshots:

- **Thai.** It stacks (กี้ ปั๊ม), SARA AM is reordered (น้ำ), and
  ญุ and ฐุ are drawn.
- **Hangul.** It is drawn, and conjoining ᄒᆞᆫ composes to one glyph.
- **Han.** The forms change with the language.
- **Mixed text.** CJK beside Latin, fullwidth punctuation, Devanagari
  क्षि, box drawing, and combining marks (n̈, a̧, é from e + U+0301) are
  drawn.
- **Color emoji draw nothing** (§13.6).

Two of the probe's own bugs were found and fixed on the way:

- **Marks drawn a cell late.** Inside an XRender glyph element the
  server moves the pen by each glyph's advance as uploaded, not as the run
  computes it. An `n` uploaded with one cell's advance put its mark in the
  next cell, and the same bug dropped a Thai vowel: ภาษาไทย was drawn
  ภษไทย. A glyph placed anywhere but the pen now starts a new element.
- **An element per CJK glyph.** A centered wide glyph never sat where the
  last one's advance left the pen, so every one was its own element, 12
  bytes a glyph and not 4. A glyph alone in a cluster narrower than its
  cells is now uploaded with its centering in its bearing: 11,702 CJK
  glyphs went from 11,702 elements to 174.

### 13.2 The Han forms come from the shaper's language

Noto Sans CJK is one collection with a face per region (`#5` JP, `#6` KR,
`#7` SC, `#8` TC, `#9` HK) and `locl` lookups per language. fontconfig with
`lang` picks the region's face, but the glyph each region needs is in
every face. On one face, `#5`, HarfBuzz's buffer language alone gives the
same glyph ids as each region's own face, for all four of 直 骨 返 刃 in all
five languages: for example 刃 is glyph 11138 in `ja`, 62118 in `ko` and
`zh-Hans`, and 11139 in `zh-Hant` and `zh-HK`. With no language, every
region gets the Japanese form.

The language still matters to fontconfig. With it, `monospace` for 水
gives *Noto Sans Mono CJK*. Without it, fontconfig gives the proportional
*Noto Sans CJK*. Ideographs are the same width in both; Latin and
punctuation in the CJK face are not.

### 13.3 Fallback is cheap enough to do on the loop

- **Cost.** `FcFontMatch` takes 0.17–0.24 ms a call, first or later:
  fontconfig keeps no cache of its own. `FcInit` takes 4.2 ms.
- **In the probe.** The cache by first code point, and loaded faces asked
  first, leave one query for each script. C§9's text, in six faces, took 5
  queries and 1.4–2.1 ms. `cjk.txt`, 4,576 distinct glyphs, took 1 query
  (0.6 ms), and `thai.txt` took 1.
- **Two queries need more than the code points.**
  - Color emoji come only when asked: `monospace:charset=2764` gives
    DejaVu Sans Mono's monochrome heart, and `:color=true` (or
    `lang=und-zsye`) gives Noto Color Emoji. U+1F600 with no flag gives
    DejaVu Sans.
  - A cluster with U+FE0F went to Noto Color Emoji only because DejaVu
    lacks the selector.

  The query needs an emoji-presentation flag from the cluster.

S§6.5 and C§5.1 ask for fallback discovery off the loop thread
(WezTerm's), because a lookup can take milliseconds. Here it takes a fifth
of one, once a script.

### 13.4 Shaping costs nothing measurable on Latin text

- **The bench.** HarfBuzz over each line as one run takes 22–43 ns a cell
  (`ls` 21.8, `gitlog` 27.9, `vte-unicode` 43.2), against 7–10 for
  `FT_Get_Char_Index`. A whole 160×50 screen is 0.2–0.35 ms. A hash of
  the run, a shape cache's lower bound (G§5.5), is 0.5 ns a cell.
- **The loop.** Three runs each on `race`, the same binary with and
  without shaping:

| input | wall: §5's | shaped | instructions: §5's | shaped | shape | rasterize |
|---|---|---|---|---|---|---|
| `gitlog` | 221–244 ms | 212–220 | 4.47–4.80 G | 4.68–4.80 | 0.8–0.9 ms | 0.3 ms |
| `vte-scrolling` | 806–822 | 767–790 | 10.5–11.6 G | 11.0–11.1 | 0.06 | 0.03 |
| `thai.txt` | 134–139 | 150–155 | 2.99–3.05 G | 3.30–3.37 | 12.6–13.1 | 0.4 |
| `cjk.txt` | 21–26 | 59–75 | 0.63 G | 1.09–1.10 | 0.9 | 32–47 |

- **Latin.** `gitlog` and `vte-scrolling` are within run-to-run spread.
- **Thai.** It costs about 10%: each word is a segment of its own (a space
  is the primary face's), so it is shaped as 28,846 runs of a word each.
- **CJK.** §5's column drew `.notdef`, and its whole cost is
  rasterizing (§13.5).

### 13.5 A screen of new ideographs costs a frame and more

- **Per glyph.** FreeType takes about 6 µs to rasterize an ideograph of
  Noto Sans Mono CJK at the probe's size: 6.07 µs hinted, 6.09 light,
  5.59 unhinted, and 3.01 to load the outline alone. Hinting is not the
  cost. In the probe, with the copy and the request, it is 7–10 µs a
  glyph.
- **Per screen.** A screen of 80×50 new ideographs is 4,000 glyphs:
  25–40 ms of rasterizing, over G7's 16 ms.
- **Afterwards.** The glyph is the server's, and costs 4 bytes a use.
- **On the wire.** 299 bytes of A8 bitmap an ideograph: `cjk.txt` sent
  1,615,036 bytes for 4,576 glyphs over 4 frames. Each glyph is sent once
  a session, and C§6's LRU on the glyph set bounds the server's copy.

| input | X bytes: §5's | shaped | elements, shaped |
|---|---|---|---|
| `gitlog` | 173,020 | 161,960 | 715 for 25,569 glyphs |
| `vte-scrolling` | 6,900 | 6,872 | 50 for 50 |
| `thai.txt` | 285,240 | 484,956 | 14,844 for 80,591 |
| `cjk.txt` | 34,412 | 1,615,036 | 174 for 11,702 |
| C§9's text | 14,012 | 27,564 | 26 for 472 |

`thai.txt` costs 70% more bytes because a mark is placed by its base's
anchors, so each one is an element of its own.

### 13.6 Not measured

- **Color emoji.** fontconfig gives Noto Color Emoji when asked (§13.3),
  but its glyphs are CBDT bitmaps (`FT_LOAD_COLOR`, a 109 px strike)
  that need an ARGB32 glyph set and scaling to the cell; the probe draws
  nothing for them. *Built: §13.10.*
- **Bold and italic.** Synthesized bold and italic for fallback
  faces are not measured.
- **Box drawing.** It is the font's, not drawn procedurally. Across rows,
  its gaps are not looked at.
- **Narrow cells.** PuTTY's compression of a glyph the font draws wide
  in one cell is not done, and the screenshots show why it is needed: ①
  ② ★, one cell each in the core, come from a fallback face wider than a
  cell and cover the space after them. *Built: §13.10.*
- **Ink outside the run.** A row's ink extents beyond its run are not
  tracked. Noto Sans Thai's tallest stack rises 0.8 px above DejaVu's
  ascent at 11 points, and its lowest mark stays inside the descent, so a
  neighbor's repaint cuts less than a pixel.

### 13.7 Ligatures: Fira Code

Gilbert programs in Fira Code (installed the same day, Debian's
`fonts-firacode`). Its ligatures keep a glyph per cell:

- `!=` is a spacer glyph, empty, in the first cell and the ligature in the
  last, its ink reaching back over the spacer
  (`exclam.spacer|exclam_equal.liga`);
- `===` is two spacers and a ligature;
- `=>` is two glyphs that join (`equal_start.seq|greater_equal_end.seq`);
- `fi` is `f` and a different `i`.

Every glyph has one cell's advance. The grid holds, and the probe draws
them (→ ≠ ⇒ ≡) with nothing added. What follows from the shape:

- **Color.** A ligature takes its last cell's color, since its ink is
  that cell's glyph. A color change inside one draws it in one color.
- **Redraw.** A change to one cell of a ligature must reshape and redraw
  all of its cells, or the old form and its ink stay. A run's context is
  the row's, not only the changed cells'. The probe's gap-of-four merging
  covers it by chance, not by rule.
- **The cursor.** On the first cell of `!=` the cursor covers a spacer,
  and the ink is the next cell's.

On `gitlog`, with Fira Code as the primary font, shaping takes 3.3–3.7 ms
over the run, against 0.8–0.9 with DejaVu, for `calt`'s lookups. The wall
time, 222–231 ms against 215–231 unshaped, is within the spread.

### 13.8 For Gilbert

1. **Shape every run, every frame, with no shape cache.** The cost is
   shaping time per frame: 0.2–0.35 ms a full screen, nothing measurable
   on `gitlog`, and 10% on Thai. Leaning: yes, and a space between two
   clusters of one fallback face joins their run, so Thai is a run a line
   and not a word.
2. **Han forms from the shaper's language.** The cost is one profile
   setting, which feeds HarfBuzz's buffer language (the forms) and
   fontconfig's `lang` (the Mono face). Leaning: yes; the language
   defaults from the locale.
3. **Fallback found on the loop thread.** The cost is up to 0.24 ms the
   first time a script is drawn. S§6.5 and C§5.1 say off the loop;
   measured, it is not worth a thread. Leaning: on the loop, loaded faces
   asked first, cached by code point; move it to a C thread (G5) only if
   a font set is measured slow. A cluster with emoji presentation asks for
   color.
4. **Rasterizing a screen of new ideographs.** The cost is 25–40 ms, once
   per glyph. Leaning: register it and measure it in daily use (phase 3).
   The fix, if it is needed, is to rasterize on a C thread and draw the
   frame when the glyphs come, which latest-frame-wins pacing allows. It
   is the only frame-budget miss found.
5. **Ligatures on, by the font's `calt`, reshaped as a row.** The cost is
   3.3–3.7 ms of shaping over `gitlog` in Fira Code, and nothing in wall
   time. Fira Code keeps a glyph per cell (§13.7). Leaning: yes. A
   changed cell redraws the stretch of the row it is shaped with, out to
   the nearest space on each side, and the cursor and colors apply per
   glyph, not by splitting runs, as C§4.2 says. A setting turns `calt`
   off.
6. **Next, before the renderer is written:** color emoji (an ARGB glyph
   set), and the narrow compression the screenshots showed is needed.

### 13.9 Gilbert's answers (2026-11-02)

Gilbert took §13.8's six leanings.

**V24 · Shape every run, every frame, with no shape cache.** HarfBuzz
shapes a run of clusters in one face each frame. Spaces between two
clusters of one fallback face join their run, so a line of Thai is one
run (§13.10).

**V25 · The CJK forms come from a language per profile.** It defaults from
the locale and feeds HarfBuzz's buffer language, which picks the forms,
and fontconfig's `lang`, which picks the Mono face (§13.2).

**V26 · Fallback is found on the loop thread.** Loaded faces are asked
first, then fontconfig, the answer cached by code point. A cluster that
asks for emoji presentation asks for a color face (§13.3). A C thread
(G5) is for a font set measured slow.

**V27 · The cost of rasterizing new ideographs is registered** (§13.5).
It is measured in phase 3's daily use, and a C thread that rasterizes
while the frame waits is decided then (`geng-plan.md` §6, phase 3).

**V28 · Ligatures are on, from the font's `calt`.** A changed cell redraws
the stretch of its row it is shaped with, out to the nearest space on
each side. The cursor and colors apply per glyph, not by splitting runs
(§13.7). A setting turns `calt` off. *Amended 2026-11-11
(`renderer.md` §R19): the cursor's cell is shaped alone, splitting the run
there, and the setting is `[font] ligatures`.*

**V29 · Color emoji and narrow compression come before the renderer**
(§13.10).

### 13.10 Color emoji, narrow compression, joined runs (2026-11-02)

Built in the x11 probe:

- **Color emoji** (V29). A cluster with U+FE0F, or one whose first code
  point is in U+1F300–1FAFF or a regional indicator, asks for emoji
  presentation. This is an approximation of UTS #51's
  `Emoji_Presentation`; the renderer takes the table. Such a cluster
  skips every face that is not color, the primary included, and its
  fontconfig query adds `color=true`. A text presentation (U+FE0E) skips
  color faces.

  Noto Color Emoji is CBDT bitmaps in one 136×128 strike. A glyph is
  loaded with `FT_LOAD_COLOR`, averaged down into its cells (one or two
  wide, a cell high, keeping its proportions), and put into an ARGB32
  picture once. It is then composited over its cells at each use: one
  `Composite` request, 28 bytes. ❤️ 🇯🇵 👨‍👩‍👧 😀 draw, and ✔ with no
  selector stays text.

  The four in C§9's text cost 4,056 bytes more on the wire (31,620
  against 27,564), about 1 KB each, sent once. A family is drawn in the
  two cells of its head, which the core's legacy width places
  followed by its other members' cells.
- **Narrow compression** (C§4.4, PuTTY's). A glyph alone in a one-cell
  cluster, whose advance is wider than the cell, is rasterized squeezed
  to the cell by an `FT_Set_Transform` and uploaded as a third form of
  that glyph. ① ② ★ from the fallback face no longer cover the space
  after them: 3 glyphs squeezed in C§9's text in DejaVu Sans Mono, 4 in
  Fira Code.
- **Joined runs** (V24). `thai.txt` drops from 28,846–29,206 segments to
  1,128–1,231, and its shaping from 12.6–13.1 ms to 8.5–10.2. Its wall
  time (154–172 ms) and instructions (3.24–3.33 G, against 3.30–3.37) do
  not move beyond the spread.

What §13.6 left that is still open: synthesized bold and italic for
fallback faces, procedural box drawing, and ink extents tracked per row.

---

## 14. Keys, and the time from a key to its pixel: a survey (2026-11-02)

§7's third item. Phase 3 builds input: XKB modifiers, the legacy and kitty
encodings, mouse, selection, IME. What phase 2 asks first is narrower:
whether keys through xkbcommon fit the one loop, and what a key costs
from its press to its pixel, here and over `ssh -X`.

### 14.1 What was built

- **The x11 probe reads keys.**
  - **In C.** xkbcommon-x11 reads the keymap from the server's XKB at
    start and again on its `NewKeyboardNotify` and `MapNotify`. Its state
    follows `StateNotify`.
  - **To Geng.** Each key press becomes a record of keysym, modifiers
    and UTF-8 text. `X.keys` hands the records over after the race's
    events branch.
  - **The encoding is in Geng**, since it decides something (§3.2). It
    is legacy xterm's, the smallest set a shell needs: the key's text,
    which xkbcommon has already made a control character under ctrl; ESC
    before it under alt; and a sequence for Return, BackSpace, Tab,
    Escape, the arrows, Home, End, Delete, PgUp and PgDn.
  - **Phase 3's, not here:** DECCKM's application cursor keys, modifiers
    on named keys, the function keys and kitty's protocol.
- **`probes/input/typo`** measures from outside, as Typometer does.
  - **How.** It gives a window the focus and, for each key, reads the
    window's top 40 rows with `GetImage`, presses and releases `x`
    through XTest, and polls the same rows until they differ. A poll
    costs 0.08–0.12 ms.
  - **What the terminal runs.** Each one runs
    `stty raw -echo; exec dd bs=1 count=KEYS+1`, so a key's echo is one
    glyph. One extra key, not timed, ends the program: a terminal that
    closes as its program ends dropped the last key's echo.
  - **`run.sh`** runs it against the probe and against xterm 411,
    st 0.9.3 and Alacritty 0.17.0 (llvmpipe) from the pinned nixpkgs, all
    in DejaVu Sans Mono 11 at 160×50 on Xvfb.

### 14.2 Key to pixel, on one machine

100 keys each:

| terminal | a key every 100 ms: median | p95 | max | every 10 ms: median | p95 | max |
|---|---|---|---|---|---|---|
| the probe, as §12 drew | 0.30 ms | 0.37 | 0.72 | 6.21 | 6.25 | 6.29 |
| the probe, a frame after a key at once | 0.28 | 0.36 | 0.65 | 0.16 | 0.21 | 0.59 |
| xterm | 0.29 | 0.42 | 0.66 | 0.13 | 0.34 | 1.08 |
| st | 2.60 | 2.65 | 2.72 | 2.31 | 2.39 | 2.63 |
| Alacritty | 2.16 | 2.46 | 2.68 | 6.49 | 7.01 | 7.15 |

- **Slow typing.** The probe is level with xterm: about 0.3 ms, of which
  the probe's own part is 0.13–0.18 ms from the key's event to its frame,
  echo included. st holds about 2.5 ms, its own minimum latency. Alacritty
  takes about 2 ms, on Mesa's software GL.
- **Fast typing.** The probe held the echo back: with keys 10 ms apart,
  a read came less than 16 ms after the last frame, so §12's loop waited
  for the frame's timer. 6.2 ms a key is the same wait Alacritty shows.
- **The fix, measured.** A read that comes after a key, before a frame,
  is drawn at once. That gives 0.16 ms a key at 10 ms apart and 0.24 at
  30. Output with no key before it keeps the cap: `cat` of `gitlog` takes
  212–249 ms in 14–16 frames, as in §13.4.
- **Its cost.** At most one frame a key, so autorepeat at 30 keys a
  second is 30 frames.

### 14.3 Key to pixel over `ssh -X`

The probe on gmktec7, its display this machine's Xvfb, `typo` here:

| a key every | median | p95 | max | ping, at the time |
|---|---|---|---|---|
| 100 ms | 4.65–4.69 ms | 5.12–29.94 | 19.1–49.0 | 3.3–28.4 ms |
| 10 ms | 3.85 | 5.18 | 20.9 | 3.5–4.8 |

- **One round trip.** A key costs about one network round trip: the key
  event to gmktec7, and the frame's requests back. The probe's own part
  stays 0.24–0.33 ms. The 29 ms tails came in a run whose pings reached
  28 ms. In a later run whose pings stayed within 3.5–4.8 ms, the p95 was
  5.2.
- **Nothing to win in puritty.** Nothing in the path waits on a reply;
  the X requests are written and flushed.
- **The keymap.** It costs 36–39 ms to load over the link, against
  0.35–0.74 ms here: `xkb_x11_keymap_new_from_device` makes its requests
  one after another. It is paid at start and when the keymap changes.

### 14.4 What a key costs inside

- **xkbcommon.** It takes 0.8–6.4 µs a key, for its keysym, text and four
  modifier tests, the higher figure when keys come 100 ms apart and the
  caches are cold. It is far below a frame.
- **Geng.** The encoding and the write to the pty are inside the probe's
  0.08–0.18 ms from the key's event to its frame.

### 14.5 Not measured

- **A real server.** On a desktop with a compositor, a frame waits for
  the next vertical blank and adds up to a refresh. Xvfb has none, so the
  table is the terminal's part alone. This needs Gilbert's desktop
  (`:0`, §6).
- **ETX.** It needs the RHEL8 VM (phase 6).
- **Keys held down.** Autorepeat is the server's, and only the frames it
  causes are counted above.
- **Phase 3's input:** the IME, the kitty protocol, mouse reports and
  selection.

### 14.6 For Gilbert

1. **Keys through xkbcommon-x11 in C, the encoding in Geng.** The cost is
   up to 6.4 µs a key, and the keymap's 36–39 ms over `ssh -X` at start.
   Leaning: yes. C turns a key into a keysym, modifiers and text, and
   Geng decides what the program is sent, so the legacy and kitty
   encodings, DECCKM and the profile's settings are Geng's.
2. **A frame after a key is drawn at once** (§14.2). The cost is a frame
   a key at most, and none when no key is typed. Fast typing's echo went
   from 6.2 ms to 0.16. Leaning: yes, with the 16 ms cap kept for output
   no key caused. Later phases' paint cooldown and synchronized output
   (§12.4) apply to output and not to this.
3. **Over `ssh -X`, a key is a round trip.** The cost is the network's,
   3.9–4.7 ms median to gmktec7. Leaning: nothing to build; record it
   with ETX's number in phase 6.

### 14.7 Gilbert's answers (2026-11-02)

Gilbert took §14.6's three leanings.

**V30 · Keys go through xkbcommon-x11 in C, and the encoding is Geng's.**
C turns a key press into a keysym, modifiers and text. Geng decides what
the program is sent: the legacy and kitty encodings, DECCKM and the
profile's settings.

**V31 · A read after a key is drawn at once.** The 16 ms cap holds only
for output that no key caused (§14.2). The paint cooldown and the
synchronized-output timeout, when they are written, apply to output.

**V32 · Over `ssh -X`, a key is a network round trip.** There is nothing
to build for it. ETX's number is recorded beside gmktec7's in phase 6.

---

## 15. GC pauses with the renderer on the loop (2026-11-02)

§7's seventh item. G7's budget is 16 ms a pause and its goal 4 ms
(geng-lang `m4-puritty.md` §VA7). Phase 0 measured it on a probe's heap
of joined pages, 3.0–3.7 ms at four and eight panes (§VA7.7). This is the
real core, with the renderer's allocation on top: a display list a frame,
the shadow, and the loop's race each turn.

**How it was measured.** The x11 probe runs with `GENG_GC_PAUSES` (D899),
which logs every collection. `PROBE_PANES=n` adds `n` panes that sit
idle beside the one drawn. Each is fed `gitlog` (26 MB, 542,103 lines)
until its 100,000-row scrollback is full, and is then kept alive and not
touched, as §VA7's idle panes were. `pauses.py` keeps the collections that
start after the window opens. Xvfb, DejaVu Sans Mono, shaping on (§13).

### 15.1 The pauses

Short inputs, one run each:

| input | panes | the run | minor: median | p99 | full | longest | its marking | heap |
|---|---|---|---|---|---|---|---|---|
| `gitlog` | 1 | 240 ms | 0.077 ms | 0.248 | 5 | 1.47 ms | 1.24 | 68 MB |
| | 4 | 219 | 0.072 | 0.135 | 3 | 2.39 | 2.09 | 110 |
| | 8 | 210 | 0.072 | 0.165 | 1 | 3.68 | 2.96 | 219 |
| `cjk.txt` | 1, 4, 8 | 56–60 | 0.066–0.069 | ≤ 0.149 | 0–1 | ≤ 1.24 | | |
| `thai.txt` | 1, 4, 8 | 141–142 | 0.038–0.042 | ≤ 0.059 | 0–2 | ≤ 1.20 | | |
| vim, 300 scrolls | 1, 4, 8 | 6.06–6.07 s | 0.220–0.284 | ≤ 0.338 | 0–1 | 0.14 | | |

`gitlog` eight times over (211 MB), two runs each, the long load §VA7 used:

| panes | the `cat` | frames | latest frame | minor p99 | full | longest | its marking | heap |
|---|---|---|---|---|---|---|---|---|
| 1 | 1,710–1,747 ms | 107–109 | 17 ms | 0.224–1.285 ms | 44–50 | 2.15 ms | 1.92–1.95 | 51 MB |
| 4 | 1,672–1,706 | 105–107 | 17–19 | 0.109–0.139 | 19–20 | 3.02–3.51 | 2.42–2.89 | 143 |
| 8 | 1,694–1,695 | 106 | 19–20 | 0.116–0.119 | 11 | 4.34–4.99 | 3.17–3.89 | 252 |

- **The 16 ms budget holds**, with a margin of three or more, at every
  count of panes.
- **The 4 ms goal holds at four panes and is missed at eight**, by 0.3 to
  1.0 ms.
- **Minor collections are not the question.** Their median is 0.04–0.08
  ms whatever the renderer does; a p99 over 1 ms is a run with full
  collections nested inside minor ones (§VA7.1).
- **The renderer adds nothing visible.** Its display list and the race
  are inside the minor numbers, and the vim scroll, 303 frames in 6 s,
  saw at most one full collection.
- **Where it shows.** A frame's lateness: the latest frame of the long
  `cat` came 17–20 ms after the read it shows, against the 16 ms its cap
  allows. The difference is a pause and the frame's own drawing.

### 15.2 Why eight panes take more than §VA7.7 said

§VA7.7's probe held 84 MB at eight panes. The core holds 252 MB, about 31
MB a pane. The core bounds a pane's scrollback by its bytes
(`scrollbackBytesFor`, 162 bytes a row at 160 columns: 16.2 MB of text
for 100,000 rows), and `gitlog`'s rows are long and fill it. The probe's
rows were short `ls` lines, which did not. A full collection's length
follows the heap: 2.15 ms at 51 MB, 3.0–3.5 at 143, 4.3–5.0 at 252.
Marking is 75–80% of it. What in the heap Boehm marks word by word was
not counted: §VA7.2's census would say.

### 15.3 For Gilbert: the 4 ms goal at eight panes

The goal is missed by up to 1 ms at eight full panes. G7's rule is to
bring the options and decide together (§VA7.6). From what was measured
here and in §VA7.4:

- **A. Accept it, and record the bound.** The goal holds to four full
  panes; eight need tabs and splits, phase 4. The budget's margin is
  three times.
- **B. More markers.** Boehm marks on one thread today (D558).
  §VA7.4 measured 4 markers halving the pause. The cost is threads, and
  cores the RHEL8 VM may not have (phase 6).
- **C. Count the heap first** (§VA7.2's census). If part of the 252 MB is
  scanned word by word that need not be, making it atomic shortens every
  pause, as D900 halved them, at no cost to the program.
- **D. A smaller default scrollback.** The pause is roughly linear in the
  scrollback held: 50,000 rows a pane would put eight panes near four
  panes' 3.0–3.5 ms. The cost is history users may want.
- **E. Incremental marking** (Boehm's incremental mode). It splits a
  full collection into steps. The cost is a write barrier on every
  pointer store, through dirty bits or page protection, and its
  interaction with the nursery (D561), which is unmeasured. It is the
  largest change here.

**Leaning: C now, then A.** The census is cheap and may remove the miss
outright, as D900 did. If it does not, accept the bound with the goal held
to four panes, and keep B for phase 4, when eight panes are real, and
phase 6, when the VM's cores are known. D and E are not worth their cost
for a 1 ms miss.

### 15.4 The census (§15.3's C)

`gcpause/patches/census-kinds.patch`, applied to geng-lang's runtime as
`gcpause/run.py` says, lists at the Nth full collection Boehm's reachable
objects by kind, atomic or scanned, and by size, and counts the words of
the scanned ones that point into the heap. Eight panes, the 211 MB `cat`,
a full collection late in it:

| | objects | bytes |
|---|---:|---:|
| atomic | 64,992 | 155.2 MB |
| scanned | 118,559 | 4.9 MB, 606,854 words, 253,381 of them pointers into the heap |

**C's premise does not hold.** Almost nothing is scanned that need not be:
the scanned part is 3% of what is reachable, and the text is atomic, as
D900 made it. A pause is not the bytes of the heap but **the objects and
pointers marking reaches**. From four panes to eight each pane adds about
10,200 scanned objects and 24,700 pointers, and about 0.2 ms of marking,
some 8 ns a pointer.

**They are the pages.** A pane holds all of `gitlog` (2,287 pages, one
512-byte `heads` each, the census's commonest atomic size), since its
bound is bytes (§15.2). A page is three `Bytes.Owned`, and an `Owned` is
a 32-byte struct, scanned, whose `data` and `block` both point at its own
atomic block (D1031). A page costs marking six objects and nine pointers:
three from the builder of pages, which holds the records unboxed (no object
of a record's size comes one to a page), and two from each struct.

Two experiments, eight panes, the same `cat`, runs of each alternated:

- **1,024-row pages**: `pageRows` from 256 to 1,024 (`Vt.Cell`), a
  quarter of the pages.
- **Inline `Owned`**: `gcpause/patches/owned-inline.patch` has
  `geng_bo_new` make the struct and its bytes one object, laid out as a
  short `Bytes` is, so it is atomic (D900). The drop then frees nothing;
  it is an experiment only.

| pages | `Owned` | runs | longest full | objects reached | pointers | the `cat` |
|---|---|---:|---|---:|---:|---|
| 256 | struct and block | 5 | 4.36–5.89 ms | 183,551 | 253,381 | 1,673–1,741 ms |
| 256 | inline | 3 | 3.95–5.09 | 149,204 | 175,992 | 1,678–1,710 |
| 1,024 | struct and block | 6 | 2.50–3.92 | 43,576 | 59,213 | 1,696–1,731 |
| 1,024 | inline | 3 | 2.28–3.00 | 30,112 | 35,027 | 1,688–1,721 |

The counts are from one census each. The baseline's five runs here sit
higher than §15.1's two (4.34–4.99); the spread between runs is wider than
any difference under 0.5 ms.

- **The page's size is the lever.** A quarter of the pages meets the 4 ms
  goal at eight panes in all six runs, and the `cat` takes as long.
- **Inline `Owned` helps less**, and alone does not meet the goal. Kept
  with D1031's drop it would mean freeing the object the page still names,
  where today the drop empties a struct and frees only the block, so that a
  read finds no bytes rather than freed memory. That is the guarantee
  geng-lang keeps over speed.
- **What is not measured** for 1,024-row pages: the time of one page-out,
  which packs four times the rows in one step of a read; the limit's
  granularity, since a page dropped for the limit is 1,024 rows; and a
  resize's cut, the same rows in fewer pages.

### 15.5 For Gilbert: after the census

- **F. 1,024-row pages** (a constant in the core). Measured above: 2.5–3.9
  ms at eight panes. First measure one page-out's time at 1,024 rows (and
  at 512, if 1,024 costs a frame visibly); the rest of its cost is the
  coarser limit.
- **G. One `Owned` a page**: a page's text, heads and runs in one block,
  the record holding where each starts. Six objects and nine pointers a
  page become two and three. A change to `Vt.Pages`, `Vt.Resize` and the
  dump; not measured. It could go with F.
- **H. Inline `Owned`** in geng-lang's runtime: less than F, and it weakens
  D1031's empty-on-drop guarantee. Not recommended.
- **A. Accept** the bound, as §15.3 had it.

**Leaning: F**, after its page-out is measured. It is a constant, it meets
the goal with margin in every run, and the throughput does not move. G
only if F's page-out or limit turns out to cost something visible; H not.

### 15.6 F built: 1,024-row pages (V33)

**One page-out.** `probes/geng/pageout` feeds the core an input at 160 by
50, then packs the ring's oldest rows into a page N times over, the same
rows each time, each page pushed onto the scrollback as a read pushes
one, and divides the time by N:

| input | 256 rows | 512 | 1,024 |
|---|---:|---:|---:|
| `gitlog` | 18 µs | 36 | 75 |
| `ls` | 53 | 109 | 215 |
| `cjk.txt` | 84 | | 328 |
| every cell its own color, 160 columns | 226 | | 918 |

A page-out is linear in its rows, and the worst, a page of rows styled
cell by cell, is 0.92 ms, paid once in the read that fills a page: a
seventeenth of a frame. The vtebench inputs came out flat across the three
sizes (`dense_cells` 86–90 µs, `light_cells` 29–32, `unicode` 61–64),
which says the rows above their screens at the end are not like the rows
they scroll; they are left out.

**V33 · A page of scrollback is 1,024 rows by default** (§15.5's F). It is
`Config.pageRows`, `Vt.defaultPageRows` unless a caller says otherwise,
and `Back` carries it to every place a page is cut. The harnesses ask for
256, so that the replay corpus, esctest and the fuzzers still fill pages
with the short inputs they were written for; a dump does not depend on the
page's size, and the corpus passed unchanged at both.

**The pauses with it**, the 211 MB `cat`, the core's own default now:

| panes | runs | longest full | its marking | heap |
|---|---:|---|---|---|
| 1 | 2 | 1.74–2.66 ms | 1.50–1.58 | 51–60 MB |
| 4 | 2 | 2.12–2.46 | 1.76–2.00 | 118–143 |
| 8 | 3 | 2.63–3.16 | 2.07–2.53 | 219–244 |

The 4 ms goal holds at every count of panes, eight with 0.8 ms to spare.

**What it costs**:

- **A resize takes twice as long** with a short history. The ring holds
  the screen and up to two pages of rows, now 2,049 rows of history where
  it was 513, and a resize reflows the ring's rows a cell at a time where
  it cuts a page's on their bytes. `core-bench`'s twenty-resize drag,
  five runs each:

  | input | 256 rows | 1,024 |
  |---|---|---|
  | `long-10000` | 9–13 ms | 20–22 |
  | `short-10000` | 10–11 | 16–18 |
  | `long-100000` | 10 | 18–20 |
  | `short-100000` | 48–51 | 57–60 |

  About 1 ms a resize where it was 0.5, inside a frame, but no longer the
  9 ms of Ghostty's drag that §VC31 matched. `harness/perf.py`'s counts
  are recorded again: the resizes 3.6% to 104% higher, the throughput
  inputs within 0.3% but for `vte-scrolling` (3.8% lower) and
  `vte-scrolling_fullscreen` (1.1% lower).
- **The ring is 2.7 MB a pane** at 160 by 50 where it was 0.7, all atomic.
- **The limit is kept to a page**, as before, but a page is 1,024 rows: a
  scrollback at its limit holds up to 1,024 rows fewer than the bytes
  allow, where it was 256. The drag's dump after `long-100000` and
  `short-100000`, both over the default limit, differs between the two
  sizes for that reason.

If the resize's cost matters, G (one `Owned` a page) cuts the objects a
page without growing the ring; it is not built.

**A compiler bug it found.** The first 20 minutes of `fuzz.py` after the
change found an input that crashed the core natively in `resizeScreen`,
which now reads `back.pageRows` before taking the pages out. geng-lang's
drop pass took the later uses of that `Int` for reads of `back` and dropped
the pages a second time, through the builder `Builder.toArray` had already
taken. The core was right; the pass is fixed as geng-lang D1046
(`m4-owned-pages.md` §OP23; geng-lang 83e539f8, compiler 46b9278d), and
the input runs clean with it. With the fixed compiler a second 20 minutes
found nothing (coverage 6,144, `runs.tsv`), and the `--diff` fuzzer's run
was clean (coverage 6,307).

---

## 16. A reference: xterm, st and alacritty on §5's workloads (2026-11-02)

§7's sixth item: the bytes of §5.2's six workloads, drawn by xterm and two
more terminals under the same proxy, beside the probe as it is now.

**How.** `probes/geng/x11/run.sh` takes a drawer for its third argument:
the probe's loop (`race`, §12's, here), or `xterm`, `xterm-core`, `st` or
`alacritty`, each from the nixpkgs pin the devbox uses, at 160×50, each
running the workload with the probe's `TERM=xterm-256color` so that every
one is sent the same bytes. `xterm` and `st` draw DejaVu Sans Mono 11
through Xft as the probe does; `xterm-core` is xterm with its default
core font, the way it is usually run across ssh. It asks for an ISO 10646
`fixed` that Xvfb does not have and falls back to `fixed`, 6×13.
`xcount.py` now sums all of a run's connections, since alacritty opens
five, and `run.sh` waits 2 s after a workload instead of 0.5, since
xterm's connection after `htop` closed later than that and was counted
in the next run's.

Xvfb ran at `-dpi 96`, the probe's FreeType size, so the Xft terminals'
cells match the probe's (9 px wide; xterm's and st's 18 px high to the
probe's 17: windows 1444×904 and 1440×850). It ran without MIT-SHM, as a
server across ssh is: a terminal that would put a frame in shared memory
then sends it on the wire. No other drawer here uses it. puritty
babea81, the compiler 58d59f90; two runs of each, and a third of xterm
(below).

**To the server.** The opening is the idle run's bytes, which come off
the others before dividing, as in §5.2. Where the two runs differ, both
are given.

| | probe | xterm-core | xterm (Xft) | st | alacritty |
|---|---:|---:|---:|---:|---:|
| opening | **2,448** | 13,780 | 350,368 | 158,940 | 10,619,440 |
| `tail`, a line | **337** | 375 | 703 | 12,688 | 3.20 MB |
| vim `Ctrl-E`, a line | **346** | 500 | 935 | 18,577 | 5.32–5.33 MB |
| vim `Ctrl-Y`, a line | **338** | 499 | 931 | 18,525 | 5.33 MB |
| `htop`, a second | 7.5–7.8 KB | **4.5–5.0 KB** | 10.6–11.2 KB | 45.8–49.4 KB | 4.8–5.3 MB |
| `cat` of `gitlog`, all | 187–197 KB | 3.7–4.8 MB | 6.5–6.8 MB | **184–207 KB** | 69–74 MB |

**From the server**, per run: the probe 16,740 bytes every time (its
replies at opening, now with xkbcommon's keymap, §14), st 2.6 KB,
xterm and xterm-core 30–31 KB idle and up to 45 KB on `tail`, 14,432
bytes more, which is 451 events of 32 bytes: xtrace of a 20-line vim
scroll in xterm-core shows 19 `NoExposure` events, one for each scroll's
`CopyArea` with graphics exposures on. alacritty 31–40 KB.

What the numbers say:

- **The probe sends the fewest bytes on five of the six.** A scroll is
  one `CopyArea` and the new row's text for both it and xterm; per line
  the probe is 337–346 bytes to core-font xterm's 375–500 and Xft xterm's
  703–935.
- **Core-font xterm beats it on `htop`**, 4.5–5.0 KB a second to
  7.5–7.8. A core-font run is one `ImageText8`, a byte a character with
  its background in the same request; the probe's is a 28-byte fill and
  `28 + 4n` bytes of glyphs. `htop` redraws short runs in many colors,
  where that header and the 4 bytes a cell tell. §5.3's 16-bit glyph ids
  halve the cell's 4 bytes. Shaping (§13) makes the ids glyph indices,
  which fit 16 bits, so the real renderer can take them at no cost.
- **`cat` is where frame pacing shows.** The probe and st draw at most a
  frame in 16 ms, and send 184–207 KB for 26 MB. xterm draws as it
  reads, jump-scrolling, and sends 18 to 36 times as much.
- **Xft xterm's opening is its glyphs.** xtrace (`xtrace -n`) puts 332,060
  of its 350,340 bytes in 808 `AddGlyphs` at start, before any text is
  drawn. Each is 32 bits a pixel (an 11×2 glyph's data is 88 bytes),
  where the probe's glyph set is A8, a byte a pixel.
- **st redraws every row on a scroll**: 12.7–18.6 KB a line. xtrace of a
  20-line vim scroll shows 2,046 `CompositeGlyphs` over 24 frames, about
  85 runs a frame, every row's, and one `CopyArea` a frame, its back
  buffer to the window.
- **alacritty sends its window as an image a frame**, about 5.3 MB, as
  S§6.1 said of the GL terminals over ssh: Mesa's software GL puts each
  frame with `PutImage` when the server has no MIT-SHM. `tail` and the vim
  runs sent the same 1.61 GB, about 300 frames each: vim's 300 redraws,
  and `tail`'s 5 s at about 60 frames a second, whatever the lines.
  Against it a probe frame is 1/15,000th.

**Not measured.** Time to draw, on any of them; the desktop's server;
alacritty's window size, which the image's 5.3 MB stands in for. Two
runs of each, and three of xterm.


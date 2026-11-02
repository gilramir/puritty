# The renderer: what the probes leave, and how it is built (survey, 2026-11-02)

Status: **survey, answered 2026-11-02: Gilbert took §R5's five leanings
(§R7, V34–V38). Steps 1 and 2 of §R6 are built (§R8); step 3,
`packages/x11`, is next.** Phase 2 of [`geng-plan.md`](geng-plan.md) §6 builds the
window: the X11 renderer, its fonts, the loop that runs a shell in it. Its
survey is [`phase2-window.md`](phase2-window.md), whose leanings are all
taken (V18–V33, geng-lang D1024 and D1045). What it measured, it measured
in probes. This document starts the real renderer the way
[`vt-core.md`](vt-core.md) started the core: an inventory of what the
probes do and do not do, the places where the probes and the plan disagree,
one measurement the plan asks for that nothing has made, and a build order.

Measured against visiterm b4566ea, geng-lang c28c234b, the compiler
58d59f90, on devbox's Xvfb at 96 dpi.

---

## R1. What the probes do

Three probes hold the renderer between them:

- **`Vt.View`** (`probes/geng/view/vtp/src/Vt/View.geng`, 352 lines), the
  renderer's Geng side, built beside a copy of the core's modules
  (`vtp/sync.sh`), since it reads `Vt.Screen`, which `vt` does not expose.
  It keeps a shadow of the cells it drew and a hash a row, finds a scroll
  as the longest band of rows moved by one shift (V18), diffs the rest, and
  writes a display list: a scroll record and a run record a changed run,
  each cell its width state, style id and code points, up to 63 (§13).
- **`X`** (`probes/geng/x11/pkg`, 40 lines of Geng and 811 of C in one
  file), which executes a display list. In C: the connection, a window and
  a retained pixmap (S§6.2), one A8 glyph set, FreeType and HarfBuzz with
  fallback through fontconfig and a per-code-point cache (V24–V26), CJK
  faces fitted to two cells, colour emoji as ARGB pictures and narrow
  compression (V29), keys through xkbcommon-x11 (V30), and an expose redrawn
  from the pixmap. It waits on the connection with `geng_io_wait` (§12).
- **The x11 app** (`probes/geng/x11/app`, 504 lines), the loop: a program on
  `os`'s terminal (D1042), each turn a race of its read, the X events and
  the frame's timer (V23), frames at most every 16 ms except after a key
  (V31), the core's replies written back, keys sent in legacy xterm
  encoding.

## R2. What they do not

Against phase 2's exit (`geng-plan.md` §6: a shell on this desktop and over
`ssh -X`, bytes per update recorded, C§9's corpus drawn right under pinned
fonts) and S§6.2, the probes lack:

| | what | where it is said |
|---|---|---|
| colours | the core's styles: a style id picks one of 16 fixed colours in C; no 256-colour, truecolour, reverse, dim, hidden | `probe_x11.c` header |
| attributes | bold, italic, underline (its styles and colour), strikethrough, overline; synthesised bold and italic for fallback faces | §13.10 |
| the cursor | none drawn: block, underline, bar, hollow when unfocused, blink | §5.1 |
| a size | 160×50, fixed: no resize (ConfigureNotify → `Vt.resize` and the pty's), no DPI from RandR | §5.1 |
| events | an expose and keys only: no focus (and mode 1004), no close (`WM_DELETE_WINDOW`), no title (OSC 0/2 → `_NET_WM_NAME`), no bell | §5.1 |
| pacing | a frame at most every 16 ms; no paint cooldown, no synchronized-output timeout (mode 2026, which the core reports), no latest-frame-wins against a slow server | `geng-plan.md` §3.1, V31 |
| glyphs | box drawing procedural; ink extents tracked per row, so overhang is redrawn | §13.10, C§4.3 |
| the glyph set | grows without a bound | S§6.2, §R4 below |
| a program | runs its arguments; no `$SHELL`, no login shell, no exit status, no config | `geng-plan.md` §3.2 |
| tests | none: the probes print numbers | `geng-plan.md` §6, §7 |

## R3. Where the probes and the plan disagree

The plan was written before the probes; the probes followed V24–V30. Three
places differ, and the renderer has to follow one or the other:

1. **Who shapes, and who keeps the glyph cache.** Plan §3.4: HarfBuzz
   returns glyph ids, clusters and offsets to Geng as `Bytes`, and Geng
   keeps the cache keys, the LRU and the eviction decisions. The probe, as
   V24–V26 describe it: the display list carries clusters, and C shapes
   them, picks the face, rasterises and caches. Shaping every run every
   frame (V24) in C and sending the glyphs back to Geng would cross twice
   a frame to carry what Geng then hands straight back; nothing Geng
   decides needs the glyph ids.
2. **Who resolves a style to colours.** The plan does not say. The probe
   sends a style id in 2 bytes a cell and C maps it to one of 16 colours.
   The real table (`Vt.Style`) has 256 colours, truecolour, reverse and
   the rest, and a profile's palette.
3. **How events cross, and how many packages the C is.** Plan §3.2 and §5:
   an `xcb` package whose "protocol knowledge is in Geng and the C is
   thin", events crossing "as their raw 32-byte xcb form" decoded in Geng,
   and `xkb` and `fonts` as packages of their own. The probe has one C
   file that does all of it, and sends Geng records of its own (keys, as
   V30 says: keysym, modifiers, text). Drawing needs the faces (shaping
   happens as a run is drawn), so `fonts` and the drawing C share objects
   the plan put in different packages.

## R4. The glyph set, measured

S§6.2 asks for bounded server-side glyph sets; the probe never evicts. The
x11 probe, `PROBE_STATS=1`, fed `phase2-window.md` §13's inputs
(`probes/fonts/gen.py`) 50 lines at a time 25 ms apart, so that every
screen is drawn:

| input | distinct code points | frames | glyphs uploaded | to the server, all |
|---|---:|---:|---:|---:|
| `cjk.txt` (70 ideographs and kana a line) | 6,086 | 588 | 6,094 | 9.0 MB |
| `thai.txt` | — | 598 | 46 | 17.7 MB |
| `gitlog.txt`, at full speed | — | 16 | 100 | 178 KB |

`cjk.txt` at full speed, 6 frames drawn, uploaded 5,047 glyphs in 1.79 MB,
about 335 bytes a glyph, nearly all of it the glyphs (an A8 ideograph is 18
by 17 pixels, its rows padded to 4 bytes: 340 bytes). So a reader's whole
vocabulary of 6,000 characters holds about 2 MB on the server for each
window, and is sent once. A window is a process (Q6), so its glyph set is
freed when it closes; on ETX's shared server each window holds its own.
The bound matters against a file made to defeat it, not daily use: the
CJK ideographs Unicode has are some 98,000 glyphs, about 33 MB in one form,
and a glyph may be uploaded in up to three (§13.10).

## R5. For Gilbert

1. **Shaping, fallback and the glyph cache in C** (§R3.1). Leaning: as the
   probe and V24–V26 have it, and plan §3.4 changed to say so. The display
   list carries clusters and colours; Geng decides what to draw and the
   profile's fonts, C turns them into glyphs. The cost is that plan §3.4's
   "Geng keeps the LRU" does not hold, and a cache policy is C code.
2. **Styles resolved in Geng; a frame carries its colours** (§R3.2).
   Leaning: each display list starts with the styles it uses, each id with
   its foreground, background and underline colours as RGB and its flags,
   resolved in Geng from `Vt.Style` and the profile's palette (bold as
   bright or not, dim, reverse, hidden), and the cells keep their 2-byte
   ids. C keeps no table between frames. The cost is a few bytes a style a
   frame, against 6 bytes more a cell if colours went in the cells.
3. **One C package, `x11`, and events as C's own records** (§R3.3).
   Leaning: `packages/x11` holds the connection, window, events, keys
   (xkbcommon), fonts and drawing; its Geng modules are the API. Events
   cross as records C writes, as keys do now (a key, a resize, focus, a
   close, a selection later), decoded in Geng with `Bytes.Decode`; an
   expose stays in C, since the pixmap answers it. Plan §3.2 and §5 change
   to say so. The cost is that the X protocol is C's, and the plan's
   "protocol in Geng" goes; what decides (what a key sends, what a resize
   does) is still Geng.
4. **The glyph set bounded by a reset** (§R4). Leaning: C counts the bytes
   it has uploaded, and past a cap (8 MB, a setting) frees the glyph set and
   starts a new one; the next frame redraws the screen. 8 MB is four times
   a CJK reader's vocabulary, so daily use never meets it, and a hostile
   file costs the server 8 MB and a redraw a time. No LRU: its bookkeeping
   costs every glyph for a case that should not come.
5. **Tests: display lists pinned, and pixels on Xvfb.** Leaning: two gates.
   `harness/view`, a recorded input fed to the core and `Vt.View`, with
   every frame's display list pinned, as `core-golden` pins Core in
   geng-lang. And `harness/pixels`, C§9's corpus and a set of screens drawn
   on Xvfb and compared with pinned images, under fonts pinned from the
   nixpkgs commit the devbox uses and a fontconfig file that sees only them
   (Q13). The bytes per update (§16 of phase2) become a recorded table, as
   `corpus/perf` is for throughput.

## R6. The build order

What each step needs decided is in brackets.

1. **`Vt.View` into `vt`** (V19, decided). `vt` exposes `Vt.View`, the probe
   copy and `sync.sh` go, and the view probe and the x11 app import it.
2. **The display-list gate** [§R5.5], and `View` writing the styles a frame
   uses [§R5.2].
3. **`packages/x11`** [§R5.1, §R5.3, §R5.4], from the probe's C: the frame's
   styles, the attributes, the cursor, a resize, focus, close and title;
   the glyph set's bound.
4. **The app**, `visiterm`, from the probe's loop: `$SHELL`, the exit
   status, a resize carried to the core and the pty, the paint cooldown and
   the synchronized-output timeout, config through TOML and
   `gren-argparse`.
5. **The pixel gate** [§R5.5], and what it finds: box drawing, ink extents,
   synthesised bold and italic.
6. **The exit**: a shell on this desktop (Gilbert's session), and over
   `ssh -X` from gmktec7, with the bytes per update recorded by xtrace for
   `tail -f`, `htop` and a vim scroll.

Step 1 is decided, and done (2026-11-02): `vt/src/Vt/View.geng`, exposed
beside `Vt`; the view, pty and x11 probes build against `vt/` itself, and
`probes/geng/view/vtp` with its copying script is gone. (The recut probes
keep their own copy, `probes/geng/recut/vtp`, for `Vt.Recut`.)

## R7. Gilbert's answers (2026-11-02)

Gilbert took §R5's five leanings.

**V34 · Shaping, fallback and the glyph cache are C's.** The display list
carries clusters and colours; Geng decides what is drawn and the
profile's fonts, C turns them into glyphs and keeps the cache.
`geng-plan.md` §3.4 says so now.

**V35 · Styles are resolved in Geng, and a frame carries its colours.**
Each display list starts with a record for each style its runs use: the
id, foreground, background and underline colours as RGB, the flags and the
underline's kind, resolved by `Vt.View` from `Vt.Style`, the core's
palette and the profile's look. The cells keep their 2-byte ids, and C
keeps no table between frames.

**V36 · One C package, `packages/x11`, and events as C's records.** It
holds the connection, the window, events, keys (xkbcommon), fonts and
drawing; its Geng modules are its API. Events cross as records C writes,
decoded in Geng; an expose stays in C. `geng-plan.md` §3.2 and §5 say so
now.

**V37 · The glyph set is bounded by a reset.** Past a cap of uploaded
glyph bytes, 8 MB and a setting, C frees the glyph set and starts a new
one, and the next frame redraws the screen.

**V38 · Two gates: display lists pinned, and pixels on Xvfb.**
`harness/view.py` (§R8) and `harness/pixels`, C§9's corpus and a set of
screens against pinned images under pinned fonts (step 5). The bytes per
update become a recorded table.

## R8. Step 2 built: styles in the frame, and the display-list gate (2026-11-02)

**The format.** `Vt.View`'s comment is its definition. A frame's list now
starts with a size record (`0x04`, columns and rows) in the first frame
and in each whose size is not the last one's, since the core changes its
own size on DECCOLM; then a style record (`0x03`, 14 bytes) for each style
id its runs use, in the order they are first used; then the scroll and
run records as before.

**Resolving a style** (V35), in `Vt.View.styleRecord`:

- a colour is the look's foreground or background for the default (OSC 10
  and 11 override them), the core's palette for an index (OSC 4 overrides
  an entry), or its RGB;
- bold makes an index of the first eight its bright one when the look's
  `boldIsBright` says so (`defaultLook`: no, its colours the core
  palette's white on black);
- inverse, and the screen's reverse video (mode 5), swap the two; with
  both they cancel;
- faint takes the foreground half way to the background, after the swap;
- invisible makes the foreground the background; the flag goes to C too;
- the underline colour is the foreground unless SGR 58 gives one.

The palette lookups the replies used (`paletteColour`, `dynamicColour`)
moved from `Vt` into `Vt.Palette`, which both read.

A cell whose style's colours change is not a changed cell: the shadow
compares cells, and a style's id stays. So `View` keeps a key of what
colours are resolved from (the palette and dynamic colours the core holds,
mode 5, the look) and forgets the shadow when it changes: that frame draws
every cell.

**The probe follows.** The x11 probe's C reads the style records into a
table for the frame and draws with their colours. Two of its shortcuts,
harmless while colours were 16 made up ones, showed at once in a
screenshot of a colour test (palette, cube, truecolour, inverse, faint,
invisible): a run was filled with its first cell's background, so it is
now a fill for each stretch of one background; and its cache of solid
pictures returned whatever picture was in a colour's slot, so it now
replaces one that holds another colour.

**The gate.** `harness/view.py`, with its program `harness/view/core-view`.
Every case of `corpus/replay/` (325) and of `corpus/view/cases/` (9) is
fed 16 bytes a read, a frame after each, and the frames' lists are decoded
in Python, a second reader of the format, into `corpus/view/NAME.txt`,
which they are held to. The decoder also checks, of every frame, what the
format promises: a size record in the first frame and whenever the size
changes, and only then; every style a run uses declared earlier in the
frame, and none twice; scrolls and runs on the screen; no run starting on
a wide character's tail or ending on its head; every record read to its
end. On the first run it found DECCOLM (`deccolm`, `size-report-pixels`),
where the core resizes itself and the frame had no way to say so; the size
record is the answer.

`corpus/view/cases/`: scrolls up, down (reverse index) and within a
region; a palette change and its reset, reverse video, OSC 10 and 11, each
redrawing every cell; every attribute and colour form; wide characters at
a run's edges; resizes from the host. 334 cases pass, in under 2 s; a pin
changed by hand fails.

**What it costs.** On the wire, `run.sh race` (phase2 §16's workloads, two
runs): a vim scroll 106,308 and 103,848 bytes, against 106,164 and
103,948; `tail` and `cat` within their spread; `htop` 82.8–83.5 KB
against 77.7–80.6, the fills of more than one background in a run. The
style records stay in the program. In Geng, the view probe with a frame a
read takes `gitlog` in 148–168 ms, `ls` 101–102, `vte-scrolling` 146–150
and `vte-unicode` 33–34, three runs each, against phase2 §13's 144–145,
98–99, 154–155 and 32–33: within the spread of runs on different days,
not an A/B of one build against another.

# The renderer: what the probes leave, and how it is built (survey, 2026-11-02)

Status: **survey, answered 2026-11-02: Gilbert took §R5's five leanings
(§R7, V34–V38). Steps 1 to 4 of §R6 are built (§R8–§R10, §R12); step 5,
the pixel gate, is next.** Phase 2 of [`geng-plan.md`](geng-plan.md) §6 builds the
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

## R9. Step 3 built: `packages/x11`, and the cursor in the view (2026-11-02)

**The package** (V36), `packages/x11`: `X11.geng`, the API, and
`src/Ext/visiterm_x11.c`, the probe's C taken over and the probe's own
package (`probes/geng/x11/pkg`) removed. The x11 probe builds on it.

- `X11.open` takes a `Settings` record (cells, the font as fontconfig names
  it and its points, the fallback language, the glyph cap, the title) and
  answers the cell's size in pixels, or why not.
- `X11.draw` executes a display list; `X11.events` and `X11.take` are the
  probe's wait and take, `take` now answering decoded `X11.Event`s: a key
  (keysym, modifiers, text, as V30 has it), a new size in cells, the
  focus, a close. An expose is answered in C from the pixmap.
- `X11.setTitle` sets `_NET_WM_NAME` and `WM_NAME`; `X11.shot` writes the
  window as a PPM, for the pixel gate (step 5). `X11_STATS=1` and
  `X11_SHOT=FILE` do at exit what the probe's `PROBE_STATS` and
  `PROBE_SHOT` did; §14's key-to-frame counters, a survey's instrument,
  were left behind with the probe's C.

What the C draws that the probe's did not:

- **Bold and italic** from the primary font's own faces, `FONT:bold`,
  `:italic` and `:bold:italic` asked of fontconfig; a font with no such
  face gives its regular, and a fallback face draws them as its regular.
- **Lines**: the underline in each of its kinds (single, double, curly,
  dotted, dashed) in the style's underline colour, at the font's underline
  position and thickness; strikethrough and overline in the foreground;
  none for invisible text.
- **The window's size.** A size record makes a pixmap of that many cells;
  the window may be larger or smaller, and what lies past the cells is the
  window's background, set to style 0's background. WM_NORMAL_HINTS asks
  a window manager for steps of a cell. A resize of the window becomes an
  `X11.Resized` in cells, which the probe gives to the core
  (`Vt.resize`) and the terminal (`Process.resize`); the next frame's size
  record answers it.
- **The glyph set's bound** (V37): past the cap the glyph set is freed and
  a new one begun, every face's record of its uploads cleared and its
  colour pictures freed. V37 said the next frame redraws the screen; it
  need not, since the pixmap keeps what the old glyphs drew, so nothing is
  redrawn and glyphs are uploaded again as frames use them.
- `WM_DELETE_WINDOW`, `WM_CLASS` `visiterm`, and the focus, reported once
  each time it changes (pointer-only focus events left out).

**The cursor, in `Vt.View`.** C keeps nothing between frames (V35), so
the cursor is the view's: its cell is drawn in a cursor style, id
`0x8000` and the cell's style, whose record carries the cursor's colours
and its shape in the underline byte's top four bits (block, underline,
bar, hollow). The shadow marks the cursor's cells, so a cell the cursor
leaves is drawn again. `View.frame` now takes a `Focus` (has the window
the focus; is a blinking cursor in its shown half): unfocused, the cursor
is hollow; hidden by DECTCEM, or blinking and off, it is not drawn.
Blinking's timer is the app's (step 4). The view gate decodes the cursor
records, checks a shape comes with a cursor id and only then, and has four
cases more (shapes, OSC 12's colour, a wide character, unfocused): 338
pass.

**Checked on Xvfb**, with `probes/geng/x11/poke`, a window manager's part
played by hand (resize, focus, unfocus, close, the title), since Xvfb has
none:

- an attribute screen (bold, italic, bold italic, the five underlines, a
  red curly one, strikethrough, overline, ideographs and emoji from
  fallback faces, a block cursor) draws as each should;
- focus, a resize to 900×500, unfocus and close, with `stty size` printed
  twice a second inside: 4 events taken, `stty` reads 50 160 and then
  29 100, the cursor is hollow after the focus left, the 7 pixels under
  the last row are the background, and the probe ends on the close, at
  4 s of its program's 8. `poke` first left a request undone: a
  connection that closes having only flushed it may not be served, so it
  makes a round trip before it leaves;
- `cjk.txt` fed a screen at a time (§R4): at the 8 MB cap, 6,094 glyphs
  held in 2,076,676 bytes, 341 a glyph, and no reset; at a cap of 200 KB,
  596 resets in 601 frames and 7.3 s rasterising, since every screen
  passes the cap; the last screen's pixels the same in both. A cap under
  one screen's glyphs (a screen of new ideographs is some 2.7 MB) makes
  every frame upload its glyphs again; the app's config should not allow
  one (step 4).

**What it costs on the wire** (`run.sh race`, two runs each, against §R8):
a vim scroll 404–417 bytes a line, against 338–346, about 70 bytes a frame
for the cursor's two cells, the one left and the one reached, which vim
moves every frame; `tail` 339, as before; `htop` 8.2–8.5 KB a second,
against 8.0–8.1; `cat` 188–194 KB; the opening 2,816 bytes, against
2,448, the atoms, the hints and the title. The replies from the server are
16,900 bytes, against 16,740, the atoms'. Core-font xterm's vim scroll is
500 a line (phase2 §16).

**Found in geng-lang:** a package summary of 80 characters or more, which
the backend refuses, is passed to it by the front end, and `geng make`
dies with `DecodeProblem` and the outline as JSON (geng-lang
`open-items.md`).

## R10. Step 4 built: the app (2026-11-02)

`app/` is visiterm: `Main.geng`, the loop; `Config.geng`, the settings;
`Keys.geng`, what a key sends. It builds with `app/build.sh` from
visiterm's devbox, and is native (`runtime = "os"`).

**Settings** are a TOML file, `$XDG_CONFIG_HOME/visiterm/config.toml` or
`~/.config/visiterm/config.toml`, read with `gren-toml`; none at all is
the defaults. `Config.geng`'s comment lists every key: the window's
columns, rows and title; the font's family, size, fallback language and
glyph cache (V37, 4 MB at least, since a smaller cap than a screen's
glyphs uploads them every frame, §R9); the default colours and whether
bold brightens; the cursor's blink; the frame interval and the
synchronized-output timeout; the scrollback in lines; the program. A key
the file does not know is refused, naming it and the keys there are, as
the compiler's own manifest does, and visiterm exits 2; so does a value
out of its range. The fallback language defaults to the locale's
(`LC_ALL`, `LC_CTYPE`, `LANG`, as fontconfig names it: `ja`, `ko`,
`zh-tw`), as V25 says.

**The program** is the settings' `program.command`, or `$SHELL`, or
`/bin/sh`, on `os`'s terminal (D1024) with `TERM=xterm-256color` and
`COLORTERM=truecolor` added to the environment. visiterm ends with the
program's exit status (1 when a signal ended it); when the window is
closed, it asks the program to end (`Process.kill`, SIGTERM) and exits 0.

**The loop** is the x11 probe's race (V23) with what §R2 found missing:

- a frame is due `frames.every_ms` (16) after the last when output is
  waiting, and at once after a key, a resize, a focus change or a blink
  (V31);
- synchronized output (mode 2026): while the program holds it, its output
  is not drawn, for at most `frames.sync_timeout_ms` (150) from the first
  read the hold kept back; a hold that times out begins again at the next
  read. 150 ms is a choice, not a measurement;
- a blinking cursor (mode 12, DECSCUSR's odd shapes) blinks every
  `cursor.blink_ms` (500) while the window has the focus, the timer one
  more branch of the race, and is shown again at once by a key;
- the focus is drawn in the cursor (§R9) and, under mode 1004, reported as
  `CSI I` and `CSI O`;
- the program's title (OSC 0, 2) is the window's, the settings' title
  while it has none;
- a key is the probe's legacy encoding with application cursor keys
  (DECCKM, mode 1) added, Shift-Tab, Insert and the keypad's Enter;
  the rest of input is phase 3's.

**Checked on Xvfb**, with `probes/geng/x11/poke`, which now also takes a
picture of the window (`shot`), so a frame can be looked at while the
program runs:

| what | how | seen |
|---|---|---|
| exit status | `sh -c '…; exit 3'` | visiterm exits 3 |
| title | OSC 2 `a title` | `poke` finds the window by it |
| synchronized output, a 1 s timeout | `A`, then under `?2026h` `B`, 0.6 s, `C`, `?2026l` | 0.3 s into the hold only `A` shows; after it `ABC` |
| the same, 150 ms | | 0.3 s into the hold `AB` shows |
| blink | `?12h` | the cursor shown, hidden, shown at 0.6, 1.1, 1.6 s |
| close | `sleep 7.25`, then `WM_DELETE_WINDOW` | exits 0, and the `sleep` is gone |
| resize | 40×5, the window made 360×170 | `stty size` reads 5 40, then 10 40 |
| a misspelt key | `colums = 40` | `…: at window: "colums" is not a key here; the keys are columns, rows, title`, exit 2 |

Not checked: typing into a shell (the key path is the probe's, measured in
phase2 §14, with DECCKM added); a desktop's window manager; `ssh -X`. Those
are step 6's.

**Its command line is not built** (§R11): visiterm reads no arguments
yet.

## R11. For Gilbert: `gren-argparse` on `os`

The plan's command line is `gilramir/gren-argparse` (`geng-plan.md` §3.2),
which is a `node` package: `Argparse.Program`, the runner, uses `Node`,
`Terminal` and `Node.setExitCode`, and `Argparse.Parser`'s `pathParser`
answers node's `FileSystem.Path`. The rest of the parser and
`Argparse.PrettyPrinter` use nothing of a platform. An `os` program cannot
depend on a `node` package, so visiterm cannot use it as it is.

**Leaning: make it two packages.** `gren-argparse` 3.0.0 becomes
`runtime = "any"`: `Argparse.Parser` and `Argparse.PrettyPrinter`, with
`pathParser` taking the platform's `fromString`
(`pathParser : (String -> path) -> ValueParser path`), so a node program
passes `Path.fromPosixString` and an `os` one `Os.Path.fromString`. The
runners are each platform's: `Argparse.Program` for node in a package of
its own (`gren-argparse-node`), and one for `os` beside it
(`gren-argparse-os`), each a few hundred lines over the same parser. The
cost is a major version: node programs import their runner from a new
package and pass `pathParser` a function. visiterm then takes
`gren-argparse` and `gren-argparse-os`, and its command line is `-e
PROGRAM ARGS...`, `--config FILE`, `--title` and `--class` to begin with.

The alternative, one package for each runtime with the parser copied, keeps
two parsers to keep alike.

## R12. The command line (V39, 2026-11-02)

Gilbert took §R11's leaning, and noted that Geng has no users but him, so
any of it can change.

**V39 · `gren-argparse` is a parser for any platform and a runner for
each.** `gilramir/gren-argparse` 3.0.0 is `runtime = "any"`, its
`Argparse.Parser` and `Argparse.PrettyPrinter`, with `pathParser` taking
the platform's function from a string to a path. Its repository holds two
more packages beside it: `gren-argparse/node` (`node/`), node's
`Argparse.Program` as it was, and `gren-argparse/os` (`os/`), the same
runners and `Failure`s over `Os.Env`. The `os` runner colours and wraps
help as node's does, and for that geng-lang's `os` gained
`Os.Env.standardOutputTerminal` (geng-lang D1048, `m3-os.md` §OS29). Both
runners now wrap at their 80-column fallback for a terminal that says 0
columns, as a pty nobody has sized does, where they wrapped at their
20-column minimum. geng-lang's `suites` gate builds every example now,
seven of them and `os-no-subcommand` natively, and runs the suite, 136
pass.

**visiterm's command line**, `app/src/Main.geng`:

    visiterm [--config FILE] [--title TITLE] [PROGRAM ARGS...]

`--config` names the settings file, which must then be there; `--title`
and a program override the settings'. `--` before a program keeps its own
flags from being taken for visiterm's (`visiterm -- vim -O a b`), since
the parser cannot take one argument and then the rest. `--help` and
`--version` are the runner's; a bad flag is reported on standard error
with exit 1, and a bad settings file or a window that will not open with
exit 2.

Checked: `--version` prints 0.1.0 and `--help` the usage, both exit 0;
`--frob` is "I don't recognize this flag" with the two flags there are,
exit 1; `--config /nonexistent/x.toml` is the `readFile` error, exit 2;
`--title cli-title -- sh -c '…; exit 4' --flag-for-sh` runs the program
with its own flag and exits 4, and `poke` finds the window by the title.


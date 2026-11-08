# The renderer: what the probes leave, and how it is built (survey, 2026-11-02)

Status: **survey, answered 2026-11-02: Gilbert took §R5's five leanings
(§R7, V34–V38). Steps 1 to 5 of §R6 are built (§R8–§R10, §R12, §R13);
Gilbert took the leanings of what the pixel gate found (§R14, §R15:
V40–V42); V40 and V41 are built (§R16, §R17; with V43, a change to V24
he accepted). Step 6, the exit, is done: over `ssh -X` from gmktec7
to this machine's Xvfb, and by Gilbert at gmktec7's desktop with puritty
running here (§R18). Phase 2's renderer is finished.** Phase 2 of [`geng-plan.md`](geng-plan.md) §6 builds the
window: the X11 renderer, its fonts, the loop that runs a shell in it. Its
survey is [`phase2-window.md`](phase2-window.md), whose leanings are all
taken (V18–V33, geng-lang D1024 and D1045). What it measured, it measured
in probes. This document starts the real renderer the way
[`vt-core.md`](vt-core.md) started the core: an inventory of what the
probes do and do not do, the places where the probes and the plan disagree,
one measurement the plan asks for that nothing has made, and a build order.

Measured against puritty b4566ea, geng-lang c28c234b, the compiler
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
4. **The app**, `puritty`, from the probe's loop: `$SHELL`, the exit
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
`src/Ext/puritty_x11.c`, the probe's C taken over and the probe's own
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
- `WM_DELETE_WINDOW`, `WM_CLASS` `puritty`, and the focus, reported once
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

`app/` is puritty: `Main.geng`, the loop; `Config.geng`, the settings;
`Keys.geng`, what a key sends. It builds with `app/build.sh` from
puritty's devbox, and is native (`runtime = "os"`).

**Settings** are a TOML file, `$XDG_CONFIG_HOME/puritty/config.toml` or
`~/.config/puritty/config.toml`, read with `gren-toml`; none at all is
the defaults. `Config.geng`'s comment lists every key: the window's
columns, rows and title; the font's family, size, fallback language and
glyph cache (V37, 4 MB at least, since a smaller cap than a screen's
glyphs uploads them every frame, §R9); the default colours and whether
bold brightens; the cursor's blink; the frame interval and the
synchronized-output timeout; the scrollback in lines; the program. A key
the file does not know is refused, naming it and the keys there are, as
the compiler's own manifest does, and puritty exits 2; so does a value
out of its range. The fallback language defaults to the locale's
(`LC_ALL`, `LC_CTYPE`, `LANG`, as fontconfig names it: `ja`, `ko`,
`zh-tw`), as V25 says.

**The program** is the settings' `program.command`, or `$SHELL`, or
`/bin/sh`, on `os`'s terminal (D1024) with `TERM=xterm-256color` and
`COLORTERM=truecolor` added to the environment. puritty ends with the
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
| exit status | `sh -c '…; exit 3'` | puritty exits 3 |
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

**Its command line is not built** (§R11): puritty reads no arguments
yet.

## R11. For Gilbert: `gren-argparse` on `os`

The plan's command line is `gilramir/gren-argparse` (`geng-plan.md` §3.2),
which is a `node` package: `Argparse.Program`, the runner, uses `Node`,
`Terminal` and `Node.setExitCode`, and `Argparse.Parser`'s `pathParser`
answers node's `FileSystem.Path`. The rest of the parser and
`Argparse.PrettyPrinter` use nothing of a platform. An `os` program cannot
depend on a `node` package, so puritty cannot use it as it is.

**Leaning: make it two packages.** `gren-argparse` 3.0.0 becomes
`runtime = "any"`: `Argparse.Parser` and `Argparse.PrettyPrinter`, with
`pathParser` taking the platform's `fromString`
(`pathParser : (String -> path) -> ValueParser path`), so a node program
passes `Path.fromPosixString` and an `os` one `Os.Path.fromString`. The
runners are each platform's: `Argparse.Program` for node in a package of
its own (`gren-argparse-node`), and one for `os` beside it
(`gren-argparse-os`), each a few hundred lines over the same parser. The
cost is a major version: node programs import their runner from a new
package and pass `pathParser` a function. puritty then takes
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

**puritty's command line**, `app/src/Main.geng`:

    puritty [--config FILE] [--title TITLE] [PROGRAM ARGS...]

`--config` names the settings file, which must then be there; `--title`
and a program override the settings'. `--` before a program keeps its own
flags from being taken for puritty's (`puritty -- vim -O a b`), since
the parser cannot take one argument and then the rest. `--help` and
`--version` are the runner's; a bad flag is reported on standard error
with exit 1, and a bad settings file or a window that will not open with
exit 2.

Checked: `--version` prints 0.1.0 and `--help` the usage, both exit 0;
`--frob` is "I don't recognize this flag" with the two flags there are,
exit 1; `--config /nonexistent/x.toml` is the `readFile` error, exit 2;
`--title cli-title -- sh -c '…; exit 4' --flag-for-sh` runs the program
with its own flag and exits 4, and `poke` finds the window by the title.


## R13. Step 5 built: the pixel gate, and what it found (2026-11-02)

**The gate** (V38), `harness/pixels.py`, with its program
`harness/pixels/core-pixels`: a case is fed to the core and drawn by
`packages/x11` on an Xvfb of the gate's own, and the window's picture is
held to its pin, `corpus/pixels/NAME.png`, pixel for pixel. No pty and no
timing: the program feeds the bytes, draws a frame at each `\F` the case
has and one after the last byte, and writes the window. A case is the
replay corpus's format, its first line also naming the font, its points,
the fallback language and the focus (`size 30x2 lang=ko`). A failure
leaves the picture and one of its differing pixels in
`.harness-work/pixels/`, and names the cells they fall in.

**Its fonts** are its own (Q13): DejaVu 2.37, Fira Code 6.2, Noto Sans CJK
2.004, Noto Color Emoji 2.051, and Noto Sans Thai and Devanagari from
noto-fonts 2026.09.01, built from the nixpkgs commit the devbox pins
(noto-fonts with only those two of its families, since the whole is some
1.5 GB), and a fontconfig file that names only their directories. FreeType,
HarfBuzz, fontconfig and Xvfb come from the same commit, so a picture
moves only when the renderer does. Three runs drew the same pixels.

**The cases**, 26: C§9's corpus (Thai's stacking, SARA AM and
descenders; Hangul precomposed, conjoining and LV+T; 直 骨 返 刃 and four
more under each of `ja`, `ko`, `zh-cn`, `zh-tw` and `zh-hk`; mixed CJK and
Latin, fullwidth punctuation and ambiguous characters; ❤️ 🇯🇵 👨‍👩‍👧; क्षि),
and screens of attributes (in DejaVu and in Fira Code), Fira Code's
ligatures, box drawing (both fonts), the 256 colours, the four cursor
shapes and a wide cursor, reverse video, wide characters at edges, and
three of ink drawn over by a later frame. The gate takes half a second;
the pins are 232 KB. It fails when it should: each change below moved the
cases it should and no others (the merged clusters' fix Devanagari, emoji
and Thai; synthesis the cases with bold or italic), and a first try at the
merge fix that also widened a cluster over the blank cell after it was
caught by `wide-edges`.

What it found:

1. **Every Han case drew Japanese forms**, under any language, at first.
   The cause was the gate's fontconfig file, not the renderer: every
   region of Noto Sans Mono CJK covers every CJK language, so fontconfig's
   own language matching cannot choose among them, and on Mint it is
   fonts-noto-cjk's rules (`70-fonts-noto-cjk.conf`) that put a
   language's region first. The gate's file now has the same rules for
   `monospace`, and each language draws its own forms (直's and 骨's
   differ between `ja`, `ko` and `zh-cn`). V25's language reaches the
   right font only where the system has such rules (§R14.3).
2. **A shaper's merged cluster was drawn in its first cell's box.** The
   core gives a Devanagari vowel sign (ि, ी) and each half of a conjunct
   cells of their own, as Ghostty does, and a flag's two regional
   indicators and an emoji ZWJ sequence's people likewise; HarfBuzz merges
   them into one cluster, and the C took only the first's cells, so क्षि
   sat in one cell and left two empty after it, and 🇯🇵 in two of its four.
   Fixed: a merged cluster takes the cells of every cluster merged into it
   (C§9 rule 4). The same rule moves Thai's น้ำ, whose SARA AM has a cell
   of its own (rule 3), 2 pixels right, centred on its two cells. Gaps
   narrower than a cell stay where a glyph is narrower than its cells (the
   half form न् in its own cell): legacy widths on a grid.
3. **Bold and italic were not synthesised** for a face without them: CJK,
   Thai and Devanagari from fallback faces, and Fira Code's italic (it has
   none, so fontconfig gives its regular), drew upright and regular. Built
   (C§9 rule 6): a face's own bold and italic are known from which faces
   fontconfig gave the four variants, and what a style asks of a face that
   is not of itself is synthesised when its glyph is uploaded, an italic
   slanted by 0.2 as fontconfig's oblique matrix, a bold widened by a 24th
   of the em, as `FT_GlyphSlot_Embolden`, but not made taller, since a CJK
   glyph fills its cell's height and a taller one bled a pixel into the
   row above. Each form is its own glyph in the glyph set (two bits more
   in a glyph's key).
4. **Ink is lost to a later frame** (C§9 rule 5). An italic f's hook
   reaches a pixel into the next cell, กี้'s tone mark a pixel above its
   row, a fallback CJK glyph's top a pixel above its row; drawn once, all
   of it shows, since nothing is clipped and rows are drawn top to bottom.
   A later frame that redraws a neighbouring cell fills its background over
   that ink and does not draw the neighbour again. Measured, a case drawn
   in two frames against the same in one: `ink-italic` loses 5 pixels at
   11 points and 7 at 22, `ink-thai` 3 and 5, `ink-fallback` 5 and 4. The
   gate's three `ink-` cases pin the loss as it is now (§R14.1).
5. **Box drawing joins** in both fonts at 11 points: the cell is the
   font's height, and DejaVu's and Fira Code's box glyphs fill it, so
   lines meet across rows and cells with no gap. They are not crisp: a
   1-pixel line is drawn anti-aliased across two pixel columns, and Fira
   Code's horizontal lines are a full row and a faint one, with a pixel's
   wobble at one row (§R14.2).
6. Nothing else was wrong. The colour emoji family's silhouettes are Noto
   Color Emoji 2.051's own design (PIL with raqm draws the same); the
   gaps after emoji and flags are the core's legacy widths.

## R14. For Gilbert: ink, box drawing, the CJK region

1. **Ink extents** (§R13.4). Leaning: **the view redraws a neighbour whose
   ink reaches into a redrawn cell.** `X11.draw` answers, for the cells it
   drew, which edges each one's ink crossed (left, right, up, down, a
   nibble a cell, only for cells that did); `Vt.View` keeps them in its
   shadow, and when it redraws a cell, it adds to the frame the
   neighbours whose ink reaches into it, so they are drawn again over the
   new background. C still keeps no table between frames (V35): the table
   is the view's, beside what it already keeps of each cell. The cost is a
   few bytes back from a draw and a few cells more in a frame beside
   italics, Thai and CJK. The alternatives: clip each glyph to its cells,
   as xterm and st do, which loses the overhangs every time (rule 5 says
   no clipping); C remembering the overhangs itself, which it cannot act
   on without the neighbours' contents; or accept the loss, a few pixels
   a case until the row is drawn again.
2. **Procedural box drawing** (§R13.5; plan S§6.3, phase 2's list).
   Leaning: **build it before the exit**, for the box-drawing and block
   elements (U+2500–U+259F): lines drawn by the C on whole pixels at the
   cell's centre, in 1 and 2 pixels by weight, so they are crisp and join
   whatever the font, and blocks and shades filled. tmux's and vim's
   borders are what a daily terminal draws most of, and the exit is
   Gilbert looking at them. Braille and Powerline stay the font's until
   they are seen to need it. The cost is some 200 lines of C, and the
   gate's box pins change.
3. **The CJK region** (§R13.1). Leaning: **rely on the system's rules**,
   as now. Mint has them from Debian's fonts-noto-cjk (other
   distributions not checked); a system without them draws Japanese forms for every language, which a
   per-range font setting (C§9 rule 7, phase 3) can override. puritty
   naming Noto's regions itself would tie it to one font family.

## R15. Gilbert's answers (2026-11-02)

Gilbert took §R14's three leanings.

**V40 · Ink is drawn whole: the view redraws a neighbour whose ink
reaches into a redrawn cell.** "We need to render the glyphs properly.
Especially Thai." `X11.draw` answers which edges each drawn cell's ink
crossed; `Vt.View` keeps them in its shadow and adds those neighbours to
the frame when it redraws a cell they reach into.

**V41 · Box drawing and blocks are drawn by the C**, U+2500–U+259F, on
whole pixels, before the exit.

**V42 · The CJK region is the system's fontconfig rules'.** Gilbert
expects puritty to want its own override later, Chinese fonts above all;
it is registered with C§9 rule 7's per-range font settings in phase 3
(`geng-plan.md` §6).

## R16. V40 built: ink drawn whole, and words shaped whole (2026-11-02)

**What the C does.** A frame is drawn in three passes, every run's
backgrounds, then every run's glyphs, then every run's lines, so that a
glyph's ink reaching into a neighbouring row is not filled over by that
row's run; the window takes a row more above and below what was drawn.
Each glyph's bitmap box is kept beside its advance when it is uploaded,
and `X11.draw` answers, for each cell it drew whose cluster's ink crossed
its edges, the row, the column and the edges (1 left, 2 right, 4 up, 8
down; two together cover the corner between them). `X11.draw` now answers
`Maybe Bytes`, `Nothing` once the connection has failed.

**What the view does.** `View.inked` keeps the answer in the shadow, a
number a cell, and the next frame, before it diffs, works a queue: every
changed cell is queued, and a cell taken from it is forgotten in the
shadow, so the diff draws it, with

- its **word**, the cells around it with a glyph in what the core holds or
  in what was drawn, since a shaper chooses a glyph by its neighbours and
  shapes only the cells a run gives it (Fira Code's arrows, a Devanagari
  conjunct); typing `>` after `-` draws the arrow;
- every neighbour whose ink reaches into it, whose ink its background
  would fill over;
- every neighbour its old ink reached, which still shows that ink, and
  would otherwise take a new glyph's ink over it twice;

each queued in turn. A scroll's band copies its pixels and no more, so the
cells at its edges whose ink crossed them, and the cells beside it whose
ink crossed into it, are forgotten too. Runs no longer take in gaps of
fewer than four unchanged cells: that was for overhangs, which this does,
and a gap's cells, drawn unasked, filled over ink nothing knew to redraw.

**Overlapping ink is drawn in reading order.** Where two glyphs' ink
meets, the later one lies over the other, and a screen drawn at once
draws row by row, left to right. A glyph drawn new does not know its ink
until it is drawn, so when its ink reaches a later cell that holds a glyph
and was not drawn with it, the view forgets that cell and
`View.wantsFrame` asks for another frame at once, which draws both in
order; the app draws it as it draws one after a key. It costs a frame
only where new ink lands on a glyph after it.

**Ink reaches its word and a cell past it, and no further.** A cluster's
ink is clipped to its word, a cell either side, and a row above and below,
which the view's reach covers; nothing in the corpus or the fuzzer's
screens is clipped. A cluster no face covers draws one `.notdef` box for
its first code point, not one a code point (a Devanagari vowel sign with
two Thai marks drew three boxes across three cells).

**Shaping stops at an empty cell**, and **V43**: spaces no longer join
two runs of one fallback face (V24's join). Both made a word shape one
way drawn beside its neighbours and another drawn alone: two lone ि with
empty cells between shaped as one run and drew nothing, and a space
joining ि to the cluster before it dropped its dotted circle. The join
saved 3–4 ms of shaping over the whole of `thai.txt` and moved neither
its wall time nor its instructions (phase2 §13.10), so it is gone, and
recorded here as a change to V24, which Gilbert accepted (2026-11-02).

**How it is checked.** The pixel gate draws each case that has frames a
second time in one frame and demands the same pixels; its cases are 32,
six of them scrolls with italics, Thai and CJK at the band's edges, two in
a scroll region with unchanged rows above and below. `harness/pixels-fuzz.py`
makes random screens (italic, Thai, CJK, Devanagari, Fira Code's
ligatures typed a character a frame, cursor moves, erases, insertions,
scroll regions, reverse index; half in Fira Code) and holds each the same
way, minimizing what differs. It found, in turn: the gap merge; a
redrawn cell's old ink left in a neighbour; the corner; ink composited
twice and out of order (the reading-order frame); a row of `.notdef`
boxes; and the shaping across empty cells and spaces. On the final code,
13,000 screens draw the same in frames as at once; the measurement of
§R13.4 loses 0 pixels in each case at 11 and at 22 points (3–7 before).
Disabling the band's edges fails both scroll-region cases, 13 and 16
pixels.

**What it costs.** The view gate's lists, every case read 16 bytes a
frame, grow from 2,058,079 bytes to 2,731,704: a word is drawn whole each
time a frame catches it growing. On the wire (`run.sh race`, two runs
each, against §R13's renderer):

| workload | before | after |
|---|---|---|
| `tail`, bytes to the server | 172,408–172,592 | 212,108–212,120 |
| vim scroll down | 129,768 | 154,944–155,188 |
| vim scroll up | 125,760 | 150,728–152,428 |
| `htop`, 10 s | 80,996–95,612 | 95,308–104,096 |
| `cat` gitlog | 182,020–199,000 | 198,208–239,548 |

`tail` is 23% more, some 417 bytes a line against 339 (core-font xterm's
is 500, phase2 §16): its lines differ from the one before in a few
digits, which were drawn alone and are now drawn with their words. A vim
scroll is 19% more for the same reason. `cat` and `htop` move within their
spread.

**Left for later.** Most of a word's redraw buys nothing in a font that
shapes ASCII without context (DejaVu Sans Mono). HarfBuzz's
unsafe-to-break flags say where breaking a run changes its shaping; the C
could answer them beside the ink, as links the view follows instead of
whole words, which would give `tail` back its 339 bytes a line where no
ligature is near. Not built: a new link is not known until the glyph that
makes it is drawn, so it needs the reading-order frame's kind of answer,
and the cost it saves is bytes, not correctness.

## R17. V41 built: box drawing and blocks drawn by the C (2026-11-02)

U+2500 to U+259F are no font's: a cluster of one of them is drawn by the C,
which rasterises it once into a bitmap of its cells, the first time it is
drawn at that width, and uploads it to the glyph set as any glyph is
(under a face number of its own), so it is drawn in its style's colour by
the same requests, and is reset with the glyph set (V37).

- **Lines** (U+2500–U+254B, U+2550–U+256C, U+2574–U+257F) come from a
  table of each one's four arms, light, heavy or double, which the
  characters' Unicode names were checked against (all 128 agree). A light
  line is a ninth of the cell's width, rounded, at least a pixel (1 at 11
  points), a heavy one twice that, on whole pixels at the cell's centre and
  running to its edges, so a line joins its neighbours in any font; the
  widest arm across decides where the others stop, so a corner is filled.
  A double arm is two lines a line apart, each stopping at the corner it
  meets (╔, ╬, ╣), and a single arm meeting a double one runs to its far
  line (╒, ╞).
- **Dashed lines** (┄ ┆ ┈ ┊ ╌ ╎ and their heavy forms) are 2, 3 or 4
  dashes a cell, a third of each dash's share left as its gap.
- **Arcs** (╭ ╮ ╯ ╰) are a quarter circle of the line's width,
  anti-aliased, from the middle of one edge to the next, and meet the
  straight lines beside them. **Diagonals** (╱ ╲ ╳) run corner to
  corner, anti-aliased, so a run of them joins.
- **Blocks** (U+2580–U+259F): the halves, eighths, quadrants and edges
  filled on whole pixels; the shades ░ ▒ ▓ as flat alpha, a quarter, half
  and three quarters of the colour, which join with no seam.

Nothing a box glyph draws leaves its cells, so it answers no ink (V40).
Braille, Powerline and the geometric shapes stay the font's.

Checked by the pixel gate: `box` and `box-fira` change, every line crisp
and joined, where the fonts' own glyphs were a 1-pixel line spread over
two pixel columns (§R13.5); three cases are added, every character of the
range in DejaVu Sans Mono and in Fira Code, and a screen of tmux-style
panes with double, heavy and rounded boxes, read at the pixel to find a
gap of one pixel at the double corners, then closed. `pixels-fuzz.py`
takes box drawing among its words: 2,000 screens draw the same in frames
as at once.

## R18. Step 6, the exit: over `ssh -X` from gmktec7 (2026-11-02)

The exit (`geng-plan.md` §6, phase 2) is a shell on this desktop and over
`ssh -X` from another host, with the bytes per update recorded for
`tail -f`, `htop` and a vim scroll.

**The desktop** cannot be reached from here: nobody is logged in at it,
and `:0` accepts a connection and never answers its setup, as in phase2
§6. That half waits on Gilbert (below).

**Over `ssh -X`.** puritty, built here, runs on gmktec7 as it is: its 23
libraries are in gmktec7's nix store, and it finds gmktec7's own fonts
through fontconfig (DejaVu Sans Mono for `monospace`). This shell has no
desktop, so the display is this machine's Xvfb, through `ssh -X`: the X
server is here and the program there, as the exit's shape is; a byte
counter (`probes/geng/x11/xcount.py`) sits between the ssh client and the
server.

- **A shell.** puritty with no program runs gmktec7's `$SHELL` (bash),
  which titles the window `gram@gmktec7: ~/puritty-exit`; typed into
  with xdotool, `echo` and `printf` print `80x24`, `TERM=xterm-256color`,
  an italic, a wrapped line and the prompt's colours, and `exit 7` ends
  puritty, and ssh, with status 7.
- **A resize and a close**, made by `poke`: `stty size` in the program
  reads 24 80, then 29 100 after the window is made 900×500; a close ends
  puritty with status 0 and leaves no program behind on gmktec7.
- **gmktec7's fonts**: Thai, Hangul, emoji, a flag, Devanagari, box
  drawing and the attributes draw from its own faces. Han did not (below).

**Found, and fixed: 1-bit glyph bitmaps.** gmktec7's fontconfig gives Han
to AR PL UMing, the Han that Debian and Mint install, whose file carries
1-bit bitmaps at 11 to 16 pixels an em; FreeType hands one over as a
bitmap of a bit a pixel, and the C uploaded it as a byte a pixel, so Han
drew as hatching. A bitmap that is not a byte a pixel is now converted
(`FT_Bitmap_Convert`) and its levels spread to 0..255. A synthetic bold or
italic is made from the outline, never the bitmap, which can be neither
widened nor slanted. The pixel gate pins UMing from the nixpkgs commit
(adding it moved none of the other cases) and gains `han-bitmap`, UMing at
9 points (12 pixels an em): the renderer before the fix draws it as
hatching. 36 cases pass; 1,000 fuzzed screens draw the same in frames.

**Found, not fixed: a keymap changed under a key.** Characters xdotool
types that the keymap lacks (Thai, Han, box drawing) arrive as others.
xdotool maps a spare keycode, presses it and maps it back at once;
puritty reloads its keymap on XKB's map notify, by asking the server,
which by then has the old map again. A person's keyboard does not remap a
key per keystroke; an input method or a layout switch changes the map and
keeps it. Input is phase 3's, and it is registered there.

**Bytes per update, over `ssh -X`** (two runs each; bytes from the client
to the server, every run's replies the same 16,900):

| workload | bytes | per update |
|---|---|---|
| `tail`, 500 lines in 5 s | 213,688–213,852 | 422 a line |
| `htop`, 10 s | 86,968–107,732 | 8.4–10.5 KB a second |
| vim scroll down, 300 lines | 152,996 | 500 a line |
| vim scroll up, 300 lines | 149,120–149,420 | 488 a line |

(a line's figure is after the opening's 2,816 bytes). They are §R16's
local figures within a few percent: the forwarding adds nothing to the X
stream. Against phase2 §16's references: core-font xterm's vim scroll is
500 a line and its `htop` 7.5–7.8 KB a second; Xft xterm's vim scroll
935. puritty is level with core-font xterm on a vim scroll, where §R9's
renderer was some 20% below it (404–417 a line) before V40 drew words
whole, and above it on `htop`, as §R9's was (8.2–8.5 KB a second); §R16's
unsafe-to-break links are what would win the scroll back.
The counter is a byte counter, not a decoding tracer; xtrace's per-request
breakdown was not needed to answer the exit's question.

**What Gilbert's half is.** On his desktop, logged in, in a terminal:
`~/prj/puritty/app/puritty` runs his `$SHELL` in a window. The things
only a desktop shows: a window manager's resize, focus and close; a
compositor's frame timing; his keyboard, including any layout switch;
Fira Code (`[font] family = "Fira Code"` in
`~/.config/puritty/config.toml`); tmux and vim at full size.

**Gilbert's half (2026-11-02).** Gilbert ran `ssh -X nene
~/prj/puritty/app/puritty` at gmktec7's desktop, the other direction
from the runs above: puritty here, its window on a real desktop with a
window manager and compositor. "It works over ssh -X from gmktec7; it
scrolls very fast." His screen is large, and the font was very small: the
C sizes every face at 96 dpi, whatever the screen's, and the default is
11 points. Until that changes, `[font] size` in the settings enlarges it.
Registered for phase 3 (`geng-plan.md` §6): the size taken from the
screen's own resolution (`Xft.dpi`, else the screen's physical size), and
a zoom at run time. The session at nene's own desktop is left to phase
3's daily use.

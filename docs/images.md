# Inline images: the survey

*Begun 2026-11-17.* puritty is to show images sent by all three
protocols, Sixel, Kitty graphics and iTerm2's inline images
(`feature-plan.md` §5, Gilbert 2026-11-06). This document settles the
questions §5 left for a survey, from the sources, before any code. Each
finding cites where it was read. Numbers marked *estimate* are not
measured yet.

## IM1 · What tmux does with images

Read in every tmux release from 2.7 to 3.8 and in master (`c05e710546f8`,
2026-11-12).

- **A control client gets every image's bytes, raw.** The pane's bytes go
  to each control client *before* tmux parses them:
  `window_pane_read_callback` calls `control_write_output`, then
  `input_parse_pane` (3.8 `window.c:1654-1656`, master `:1720-1722`; in
  2.7 to 3.1 the same through `notify_input`). `%output` escapes bytes
  below 0x20 and `\` and changes nothing else. So a Sixel DCS, a Kitty APC
  and an iTerm2 OSC 1337 reach puritty's `-CC` client byte for byte,
  whatever tmux was built with and whatever `allow-passthrough` says.
  **Under `tmux -CC` puritty can show all three protocols itself**, each
  pane's core decoding its own `%output`, with nothing from tmux.
- **What is lost.** A control client is never redrawn
  (`server_client_check_redraw` returns for `CLIENT_CONTROL`, 3.4
  `server-client.c:2570`), and no command fetches a pane's images
  (`capture-pane`, `refresh-client`: no image anywhere in 3.4, 3.8 or
  master). An image drawn before puritty attached, or before a pane was
  captured again (TM15's recapture after `%pause`, TM93's reconnect), is
  gone; the text around it comes back. That is tmux's limit; puritty shows
  what it saw.
- **tmux answers the probes itself, at compile time.** DA1 gives
  attribute 4 (Sixel) only from 3.4 built with `--enable-sixel` (3.4
  `input.c:1449-1453`); XTSMGRAPHICS is answered from 3.4 (1024
  registers); Kitty's `a=q` probe gets no answer in 3.3 to 3.8 and
  tmux's own `OK` in master (`image-kitty.c:1281`). The outer terminal's
  abilities change none of these. So a program in a pane decides by
  tmux's build, not by puritty: under a Sixel tmux it sends Sixel (which
  puritty then shows from `%output`); under a plain one it sends none
  unless told to.
- **tmux's grid and puritty's can part.** A tmux built without Sixel
  ignores the DCS and leaves the cursor; puritty's core, drawing the
  image, moves it below. Text after the image then lands on different
  rows in puritty and in tmux, until the next recapture. To be measured
  (IM8 step 2) before deciding whether puritty should follow tmux's
  cursor there.
- **A Kitty image sets the pane's title in 3.3 to 3.8.** `input_exit_apc`
  takes any APC as a title when `allow-set-title` is on (3.8
  `input.c:2794`), so `ESC _ G…` makes the pane's title `G…`, which
  reaches puritty's pane borders through `pane-border-format`. master
  gives `G` APCs to the Kitty parser instead. puritty can't tell such a
  title from one a program chose, so it shows what tmux says; the user
  guide says why.
- **Plain tmux (not `-CC`)** is the outer-terminal case: tmux 3.4+ built
  with Sixel redraws stored Sixel images to a terminal that says it has
  Sixel (`tty_draw_images`), master also Kitty; older tmux passes images
  only through `allow-passthrough`. puritty's part is to answer DA1 and
  the Kitty probe truthfully.

Corrects TM5.9 (it held this as inferred, and for 3.4 to 3.8 only).

## IM2 · Where images go in puritty's drawing

From the renderer's code (`docs/renderer.md`).

- **The core hands the renderer a display list** (`Vt.View.frame`,
  records 0x01 to 0x09: scroll, styles, runs of cells, highlights, the
  interface boxes) and keeps a shadow with a hash a row to send only what
  changed. Both platforms execute it in `packages/text`
  (`puritty_text.c`, `pt_frame`) through a small platform interface.
- **An image primitive exists already:** `pt_picture_add`/`draw`/`free`,
  premultiplied ARGB uploaded once and composited many times, used for
  color emoji. On X11 it is an ARGB32 pixmap and a RENDER Composite; on
  Windows a C blend into the frame's bitmap. It needs a source offset
  (it draws from 0,0 today) to draw part of an image in a cell range.
- **Proposed hook.** The core keeps images (id, size, RGBA) and placements
  (image, anchor row and column, source rectangle, cells covered, layer);
  View emits two new records: an image's definition, once a window, and a
  placement for each changed run of cells it covers; the shadow marks
  covered cells so that a redrawn cell redraws its slice. `pt_frame` stops
  at a record it does not know (`:1517`), so an old executor fails
  closed. Images are composited between the cells' backgrounds and their
  glyphs (Kitty's layers choose before or after).
- **Cost on X11** *(estimate)*: an image is sent once, `w × h × 4` bytes
  (640 × 480: 1.2 MB), then about 28 bytes a redraw; a scroll is the
  pixmap's CopyArea, which moves images free. For comparison (measured,
  `phase2-window.md` §5): 10 to 14 KB a frame for htop, 35 KB to open the
  window. ETX itself is unmeasured (RE7); IM8 measures there.
- **Risks found:** `pt_picture_add` sends one `xcb_put_image`, which over
  the server's request size (16 MB with BIG-REQUESTS; unknown on ETX)
  breaks the connection: big images go in bands. A shared X server (ETX)
  holds every window's images: they need a cap and eviction, with View
  told to send again. On Windows each redraw over an image is a CPU blend.

## IM3 · A bug found on the way: the core's cell size after a zoom

The core answers `CSI 14 t` and `CSI 16 t` from the cell size it was given
when the window opened (`Vt.Term` `cellWidth`, `cellHeight`, set once at
`Main.geng:1171`). The two zoom keys (`Main.geng:4133`, `:4425`) and the
settings window's font and size (`:2863`, `:2877`) get the new cell size
from the window and drop it, and the core has no setter. After a zoom a
program asking the cell size is told the old one, and an image sized by
it comes out the wrong size. To fix first (IM8 step 0): a
`Vt.withCellSize`, applied to every tab's terminal.

**Fixed (2026-11-17).** `Vt.withCellSize`, and `Main.cellSized` gives the
window's new cell to the terminal and every tab's at the four places; a
tab made later copies it (`freshTerm`). Measured in the app under Xvfb,
a program asking `CSI 16 t`, then Ctrl+=, then asking again: 0.1.0
answers `6;17;9t` both times; now `6;17;9t`, then `6;19;10t`. A vt unit
test (103). tmux panes' terminals still have no cell size (0, which the
reports take as unknown): the image layer gives them one (IM8 step 1).

## IM4 · Decoders

- **Sixel** is text (a palette and six-pixel columns): decoded in Geng, in
  the core, bounded before it allocates.
- **PNG, JPEG, GIF** (iTerm2), **PNG and zlib** (Kitty) need decoders in C.
  No decoder is called anywhere in puritty today; libpng and zlib are in
  the binary only for FreeType's color emoji.
- **wuffs, bundled** (Apache-2.0, one generated C file): PNG, JPEG, GIF
  with every frame, and zlib, which Kitty's compressed data needs raw.
  Its bounds and overflow safety are proven by its compiler; it allocates
  nothing itself. It is what Ghostty uses (pinned in Ghostty's
  `pkg/wuffs`), so the oracle and puritty would decode with the same code.
  Bundled statically, as HarfBuzz and FreeType are for RHEL8 (RE4).
- Not chosen: **stb_image** (public domain; its author says it is not for
  untrusted input, and a long list of fuzz-found overflows since 2021;
  no raw inflate), and **the system libraries** (libpng, libjpeg-turbo,
  giflib, zlib: four dependencies pinned old on RHEL8, each with its own
  CVE history, and giflib leaves animation to the caller).

**Changed, 2026-11-17 (Gilbert): PNG and zlib in Geng, in the core.**
The core must know an image's size and whether it is valid when the
command arrives: to place it, move the cursor, count it against the limit,
and answer as Ghostty does ("OK" or "EINVAL: invalid data", KG5); `o=z`
needs the inflated length too. The core (`vt/`) is pure Geng, run on node
as well as natively, so a C decoder cannot sit in it. So inflate (RFC 1950
and 1951) and PNG (its filters, colour types, palette, Adam7) are written
in Geng in the core, where no buffer can be overrun, which matters for
data a remote program sends. Its speed is to be measured on real images;
wuffs stays the fast path to add in the renderer if that is too slow.
JPEG and GIF (iTerm2's) are decided when iTerm2's step comes. The oracle
gets a PNG decoder from its host (`GHOSTTY_SYS_OPT_DECODE_PNG`, wuffs,
which Ghostty bundles), so both sides accept PNG.

## IM5 · Safety and limits

- **Transmission.** Kitty can ask the terminal to read a file, a
  temporary file or shared memory by name. A remote program must never
  make puritty read local files: **direct transmission only** (the data in
  the escape sequence), as libghostty-vt's default and tmux master take
  it. A local shell could be allowed temporary files later, with Ghostty's
  checks (a real path under the temp directory, `tty-graphics-protocol`
  in its name); not in the first version.
- **Size.** Each side at most 10000 pixels and each image's RGBA at most
  a cap, both checked before allocating (Ghostty: 10000 px, 400 MB; WezTerm:
  100 MB). The Sixel decoder stops at the same bound.
- **Memory.** All images together under a limit, a setting (Ghostty 320
  MB in its app, 10 MB as a library; WezTerm 320 MiB). Over it, evict as
  Ghostty does: images no longer placed before placed ones, oldest first.
  The default is for Gilbert to choose (IM9); on ETX's shared server it
  is also the X server's memory.

## IM6 · Telling programs

Claimed only when that protocol works, each by its own question:
Sixel by DA1 attribute 4 and XTSMGRAPHICS (`CSI ? 1;1 S` colors,
`CSI ? 2;1 S` geometry); Kitty by answering `a=q` with `OK`; iTerm2 has
no probe (programs check `TERM_PROGRAM` or just send). chafa, timg and
yazi pick a protocol from these answers. Under `-CC` tmux answers for the
pane (IM1), so these are puritty's answers to programs outside tmux.

## IM7 · The oracle

- **Kitty: Ghostty is an oracle.** Its Kitty graphics live in the
  terminal library (about 14,600 lines: parse, storage, placements,
  deletion, Unicode placeholders), compiled into libghostty-vt as the
  oracle builds it (`build_options.zig:165`), with a C API to read images
  and placements back (`include/ghostty/vt/kitty_graphics.h`). The
  library's defaults: direct transmission only, 10 MB, and no PNG
  decoder unless the host installs one (`GHOSTTY_SYS_OPT_DECODE_PNG`).
  `ghostty-dump` can dump images and placements and install a wuffs PNG
  decoder, and the replay corpus and differential fuzzer then hold the
  core's Kitty to Ghostty's.
- **Sixel and iTerm2: no oracle.** Ghostty ignores a Sixel DCS
  (`dcs.zig:37`) and drops OSC 1337 `File` (`iterm2.zig:169-193`).
  WezTerm has both (its own Sixel parser, MIT; the `image` crate for
  iTerm2), but no library to drive. These get puritty's own tests:
  replay cases with the expected placements and decoded pixels, and
  pixel tests of the drawn frame (`corpus/pixels`).
- **Placements against the text.** Ghostty ties a placement to a tracked
  pin, so it moves with its row on scroll and reflow, and each screen
  (primary, alternate) has its own store. WezTerm instead gives each
  covered cell its slice of the image, so slices scroll and reflow as
  text and a rewrap can scatter them. puritty's plan (IM2) is Ghostty's.

## IM8 · Order of work

0. **The cell size after a zoom** (IM3), with a test. Small; a real bug
   today.
1. **The image layer**: images and placements in the core (scroll, clear,
   alternate screen, reflow), View's two records, `pt_picture` with a
   source offset and bands, the memory cap and eviction; shown by a test
   pattern before any protocol. Replay and pixel tests.
2. **Sixel**: the decoder in Geng; DA1 4 and XTSMGRAPHICS. Then under
   `tmux -CC`, the cursor question of IM1 measured on a Sixel and a plain
   tmux.
3. **iTerm2**: wuffs bundled (Linux, RHEL8 container, Windows), PNG, JPEG
   and GIF's first frame; the notices gate's entry for wuffs.
4. **Kitty graphics**: direct transmission, placements by id, deletion,
   z layers, compressed data; the oracle's dump of images and placements;
   then Unicode placeholders; animation last.
5. **ETX**: bytes per image measured on RHEL8 (RE7's harness).

Test programs: chafa 1.18 (all three protocols) is in nixpkgs; img2sixel
(libsixel) and timg too. They join the devbox when step 2 starts.

## IM9 · Decided (Gilbert, 2026-11-17)

- **Kitty first**, after the image layer: it has the oracle (IM7) and the
  most modern programs; then Sixel, then iTerm2's. IM8's steps 2 to 4
  are taken in that order: Kitty (with wuffs, which its PNG and zlib
  need), Sixel, iTerm2.
- **The memory limit's default is 320 MB** for all images together, as
  Ghostty's app and WezTerm have it; a setting on the Advanced page.
- **Direct transmission only** for now, a local shell too: no temporary
  files or shared memory (IM5).

## IM11 · How a placement keeps to its text: the design

A placement must move with its rows: on scroll, into the scrollback and
back on screen, through a scroll region's moves (IL, DL, DECSTBM), and on a
resize's reflow; and go when its rows are erased or leave the scrollback.
Two ways, read in the core (2026-11-17):

- **(a) A mark in the row.** Each row's meta slot (`Vt.Cell`: extent bits
  0–15, wrapped 16, prompt 17–18) has room above bit 19 on the screen, so
  a row could carry an anchor id the way it carries OSC 133's prompt mark,
  and every operation that moves rows would move it for free, as
  Ghostty's tracked pins do. But a row leaving the screen is packed into
  a page whose row header is 16 bits (`Vt.Pages`: extent 0–9, prompt
  10–11, unstyled 14, wrapped 15; 12–13 unused), so the anchor would need
  the page format to grow, and every reader of it (unpack, recut, dump,
  reflow) to carry it.
- **(b) Absolute rows.** The core numbers rows absolutely already
  (`Vt.rowsPushed`, `Point`), which selection and search use: a row keeps
  its number while the screen scrolls and while it sits in the scrollback.
  Placements in a table keyed by absolute row need nothing from the pages.
  What (a) gets free, (b) does by hand: a scroll inside a region (IL, DL,
  SU and SD under DECSTBM, DECSLRM's columns) moves or drops the placements
  in it; an erase (ED, EL over the anchor, DECSTBM's region cleared) drops
  them; a reflow maps each anchor through the reflow's row map, as it
  must for the cursor; a row dropped off the scrollback's end drops them.

**Chosen: (b).** It leaves the page format and the scrollback's code as
they are, and each by-hand case is one place in the core (the scroll and
erase primitives, the reflow's map), each with a replay case. Placements
are per screen (primary and alternate each their own, as Ghostty's), and
the images they show are shared by both and by every placement, counted
for the memory limit once. If (b)'s cases prove many, (a) stays open: the
page header's bits 12–13 could flag rows with anchors and a side table
keyed by page carry them.

## IM12 · Checkpoint A: Kitty's images and placements in the core (2026-11-17)

`Vt.Kitty` (the protocol, `images-kitty.md`), the `images` field of
`Vt.Term` (one field, as `osc52`: each screen's store, the APC being read
and the limit), the parser's APC state (`psApc`, `apcString`: slices of
each read as OSC 52's, at most 65 MiB, ESC or ST ends it, CAN, SUB or a C1
abort it), and the hooks: ED 2 and 22 take the placements on the screen
and the images left unshown, ED 3 those in the scrollback, the alternate
screen's switch swaps the stores (clearing the alternate's with its
text), RIS empties them. Placements are anchored to absolute rows (IM11).

**Held to the oracle.** `harness/oracle/gdump.c` gives Ghostty the core's
cell size (10 by 20, by a resize to the same size, which Ghostty needs to
know it; no existing case changed) and prints the placements as
`Vt.Kitty.dumpLines` does. Fifteen replay cases (`corpus/replay/kitty-*`):
transmit and place, a=T sized by cells and by pixels with offsets, the
cursor after (C=0 and C=1, a wrap at the last column, a scroll into the
scrollback), the error replies and quiet, chunks, each delete (a, i, I,
p, q, x, y, z, r, R, n, N, c), ED 2 and 3, the alternate screen, image
numbers, the parser's corners (a key's value skipped, underscores and
`+`, a trailing comma, an overlong value, a sign, an unknown action or
compression, a non-`G` APC, bad base64), and a=q. All agree with Ghostty
on the first run. The differential fuzzer's dictionary has Kitty commands.

**Not yet**, each a known difference from the oracle: relative
placements (`P`: answered "parent image not found"), animation (`a=f`,
`a`, `c`: ignored), `o=z` (answered "decompression failed" until wuffs),
the moves a scroll region and the alternate screen's scroll make (IM8
step C), base64 with whitespace (the core's decoder is strict). The
executors' records (IM2) are written but nothing sends them yet
(checkpoint B).

## IM13 · Checkpoint B: images drawn (2026-11-17)

**The records** (`puritty_text.c`, read by both platforms): 0x0A defines
an image (id, width, height, 3 or 4 bytes a pixel, the pixels as they
came; premultiplied there into ARGB and kept as a picture by id), 0x0B
frees one, 0x0C places one in 30 bytes (the image; the cells covered, the
first's row signed, since a placement may start above the screen; the
source rectangle; the offset in the first cell; the size drawn; under or
over the text). Placements are drawn after the runs' backgrounds and
before their glyphs (z below 0) or after them, clipped to their cells.
`pt_picture_draw_part` draws part of a picture scaled: on X11 a RENDER
transform with the bilinear filter and the composite's rectangle as the
clip, on Windows the nearest pixel in the C blend. X11 uploads a picture
in bands within the server's longest request (IM2's risk).

**View** (`Vt.View.frameOn`) keeps in the shadow the placements it drew
and the images the window holds by generation. Each frame the cells of
placements that came, went or moved are forgotten before the diff, and a
placement any of whose cells the frame drew is drawn again with all of
its cells (up to three passes, as one drawn whole may make another's
cells drawn), since a picture is composited over its cells and cells
left as they were would take a translucent one twice. Images are defined
the first time a drawn placement shows them at their generation, and
freed once the core no longer has them. The view scrolled back shows the
placements in it (`Kitty.shownPlacements back`).

**Measured.** Five pixel cases (`corpus/pixels/cases/image-kitty-*`): an
image between text, scaled to cells, cropped, offset in its cell; a
translucent one over text with a cell under it changed a frame later; one
deleted; one scrolled half off. The gate draws each in its frames and at
once and holds the two equal, which the first build failed (the
executor's record size was 34, View's 30: the text after a placement was
lost) and the second passes. In the app under Xvfb a 32-pixel gradient
placed scaled to 6 by 3 cells and at its own size shows as it should.
The app's limit is 320 MB (`Vt.withImageLimit`, IM9).

**Not yet:** tmux `-CC` panes (each pane's terminal keeps its images, but
the canvas puritty draws panes on does not carry them), the Windows
executor's drawing seen (it compiles; the pixel gate's pins are Linux's),
and a frame's cost measured with an image (ETX, IM8 step 5).

## IM14 · Checkpoint C: what scrolls and resizes do to placements (2026-11-17)

Read in libghostty-vt (`scrollMarginsBegin`, `clipTop`, `clipBottom`,
`index`, `scrollUp`, `scrollDown`), then held to it by eight replay cases
written first (`kitty-region-*`, `kitty-alt-scroll`, `kitty-resize-rows`).

- **A scroll within margins** (IND at the bottom margin, SU, SD, RI at the
  top margin; never IL or DL): a placement wholly inside the region (rows,
  and columns between DECSLRM's margins) moves with it, clipped at a
  margin, a scaled one losing that share of its source and a row, one at
  its own size a cell's height of pixels a row, and gone when nothing is
  left; any other on the screen keeps its screen row, which on the main
  screen with the region at the top means anchoring it again, since the
  rows that leave go to the scrollback; one in the scrollback is not
  touched. `Vt.Placed` (below `Vt.Scroll`, which calls it) plans this in
  screen rows before the scroll and applies it after (`scrollPlan`,
  `scrollApply`). The full screen's scroll on the main screen needs
  nothing: absolute rows (IM11) carry the placements into the scrollback.
- **The alternate screen's full scroll** (it keeps no scrollback): each
  placement goes up with its row, and one whose row leaves stays on the top
  row at the first column, as Ghostty's pins do (`altScrolled`).
- **A resize that changes the rows only** agrees already.
- **A resize that rewraps lines does not** (`kitty-resize-reflow`, with
  its divergence): Ghostty's pins reflow with their rows and by rules of
  their own; the core keeps absolute rows. Held for the reflow to carry
  the placements as it carries the cursor.

The 24 Kitty replay cases agree with Ghostty but that one.

## IM15 · PNG and zlib in the core (2026-11-17)

As IM4 was changed to: `Vt.Inflate` (RFC 1950 and 1951, after zlib's
`puff.c`: canonical codes decoded a bit at a time, stored, fixed and
dynamic blocks, the zlib header and Adler-32 checked, the output held to a
limit) and `Vt.Png` (the signature, the chunks with the critical ones'
CRCs, IHDR's legal depths and colour types, PLTE, tRNS, the IDATs joined,
the five filters, every colour type and depth to 8-bit RGBA, Adam7). A
width or height past 10,000 is "dimensions too large" from the header, as
Ghostty answers a valid one (a corrupt one so large it would call "invalid
data"). `Vt.Kitty.loaded` inflates `o=z` ("EINVAL: decompression failed")
then decodes `f=100` ("EINVAL: invalid data"), the size then the PNG's,
as libghostty-vt does.

**The oracle** decodes with the wuffs Ghostty vendors, given to it through
`GHOSTTY_SYS_OPT_DECODE_PNG` in `harness/oracle/gdump.c`, called as
Ghostty's app calls it (`pkg/wuffs/src/png.zig`), so both sides take PNG.
Both dumps now give each image's format and an Adler-32 of its pixels.

**Held to it.** `kitty-png-types`: 22 PNGs, grey at 1, 2, 4, 8 and 16 bits,
RGB and RGBA at 8 and 16, grey with alpha at 8 and 16, a palette at 1, 2, 4
and 8 bits with tRNS, colour keys for grey and RGB, all five filters, Adam7
at three sizes, three IDATs and an ancillary chunk, 1 by 1: every pixel's
checksum equal to wuffs'. `kitty-png-errors`: a bad CRC, a truncated file,
a bad Adler-32, an unknown critical chunk, a bad signature, no data,
`s`/`v` overridden by the PNG's. `kitty-zlib`: RGB and RGBA inflated, a bad
checksum, a truncated stream, a compressed PNG, a chunked compressed load.
All agree with Ghostty on the first run.

**Measured** (`harness/dump/core-dump`, the whole run, three times each):
an 800 by 600 RGBA photo-like PNG (531 KB) loads in 0.05 s at 27 MB at
most; 1920 by 1080 (2.3 MB) in 0.19 s at 79 MB; the same bytes as an APC
not Kitty's take 0.00 s. Enough to show an image; slow for flicking through
previews (yazi). The memory is the output builders' (a `Builder UInt8`
element costs more than a byte): the first thing to look at if it matters,
before wuffs in the renderer (IM4).

## IM16 · Off for 0.1.1 (2026-11-17)

*Gilbert, 2026-11-17:* 0.1.1 is released for its fixes with images off,
since they are not ready (tmux panes, reflow, real programs untried).
libghostty-vt's own switch is used: an image limit of 0 turns the
protocol off, every command ignored and none answered, a query too
(`Vt.Kitty.apcDispatch`), so a program asking finds no support and sends
none. `Main.imageLimit` is 0 for the release. **To turn images back on**
after it: `imageLimit = 320000000` in `app/src/Main.geng` (IM9). A vt
test holds the switch (104); in the app under Xvfb the script that drew
two placements draws none and is answered nothing.

**Back on (2026-11-17)**, 0.1.1 published: `imageLimit` is 320 MB again.

## IM17 · Real programs: chafa and timg (2026-11-17)

chafa 1.18.2 and timg 1.6.3 (both in the devbox now, from the nixpkgs
commit the X libraries come from), run in puritty under Xvfb on a
200 by 120 test picture:

- **Told to use Kitty's protocol** (`chafa -f kitty`, `timg -pk`), each
  draws the picture in puritty as it should. chafa sends exactly what the
  core does: `a=T,f=32,s=270,v=160,c=27,r=8,m=1,q=2` with no payload, then
  `m=1` chunks of base64 RGBA, then an empty `m=0`; no id, so no reply.
- **Left to choose, neither picks it**; each draws with text symbols
  (chafa) or half blocks (timg). Neither asks the terminal about Kitty's
  protocol: chafa knows terminals by their environment (`TERM=xterm-kitty`,
  `KITTY_PID`, `TERM_PROGRAM=ghostty`, …; `chafa/chafa-term-db.c`) and its
  probe asks DA1 only, for Sixel; timg matches the name XTVERSION answers
  (kitty, ghostty, WezTerm, foot, …; `src/term-query.cc`) and says it
  sends no Kitty query on purpose, as the query confuses some terminals,
  then asks DA1 for Sixel. puritty is in neither list.

**What it means.** For a terminal neither knows, what both find by
themselves is Sixel, through DA1's attribute 4. So Sixel (IM8, after
Kitty) is what makes images appear unasked in these two, and comes next
after tmux's panes. Until then a user tells them (`chafa -f kitty`, or
`format kitty` in chafa's config; `timg -pk`), which the guide (IM10)
will say. Asking chafa and timg to know puritty by name is a later
question, Gilbert's, once puritty's XTVERSION name is settled for good.

## IM18 · Images in tmux `-CC` panes: the design (2026-11-17)

Under `tmux -CC` each pane is a `Vt.Term` of its own, fed its `%output`,
so a pane's images are already kept (IM1), on its own rows. The window
draws one terminal, the canvas, which `Vt.composeStyled` makes of the
panes' cells (`TmuxMode.paint`). What is needed:

1. **The panes' terminals sized.** They are made with no cell size (so
   no placement covers a cell) and libghostty-vt's 10 MB: `TmuxMode` is
   given the window's cell size and the image limit, and makes and
   resizes its panes with them, as the window's own terminal has them.
2. **The canvas carries the panes' placements.** `composeStyled` takes
   each place's pane's placements in view (`Kitty.shownPlacements`, the
   pane's own scrolled-back rows for copy mode), moves them by the
   place's row and column, and keeps them, with their images, beside the
   canvas's own, each clipped to its pane's rectangle.
3. **View keys images by where they come from.** Two panes may both
   have an image 1; the executor's table is the window's. So View gives
   each image it sends an id of its own (a counter in the shadow), by a
   key of the pane, the image and its generation, frees one when no
   placement shows its key, and a placement's record names that id.
4. **A placement's record carries a clip** besides the cells it starts
   at: a pane cuts an image at its edges without moving it. The record
   grows by the clip's x, y, columns and rows.

Not in this step: an image of a tiled pane lies under a floating pane
over it only as far as the floating pane's cells are drawn after it;
placements a floating pane covers are left out where they meet it.
Images drawn before attach are gone (IM1), as is a pane's after a
recapture.

**Built (2026-11-17).** `TmuxMode.setCell` (the window's cell and the
image limit, given by `Main` where it makes a tmux state and after a
zoom) and `celled`, which gives them to every pane's terminal as `paint`
begins; `Vt.composeStyled` carries each place's placements onto the
canvas (`images.composed`), cut to the pane and to the canvas, dropping
those a later pane meets; `Vt.withoutComposed` clears them as `paint`
composes again. View sends each image under an id of its own by key, and
a placement's record (38 bytes now) carries its clip.

**Seen** (`bench/tmux/compare/scenes_images.py`, puritty under real tmux
3.8 `-CC`): `chafa -f kitty` run in the right pane of a split draws its
picture in that pane, the text above and below it where they belong; a
Kitty image 70 columns wide in a 50-column pane is cut at the pane's
edge and nothing reaches the other pane. An app test on each tmux (402)
holds a pane's image on the canvas, its size and its clip. Both scenes
show IM1's two findings live: tmux 3.8 takes the APC as the pane's title
(the status line shows `Gm=0`, or the command's text), and an image run
before puritty attached is not there (the first try ran chafa in the
setup).

**The cursor, measured** (`image-cursor-drift`, real 3.8): after
`chafa -f kitty --size 30x6 …; echo below`, tmux's pane has `below` on
its row 3 and the prompt on 4, as if no image were there; puritty's has
them under the image's six rows, where the program meant them. A switch
to another window and back changes nothing in puritty, which keeps each
pane's terminal; the two would show only where puritty draws a pane
again from tmux's capture (after `%pause`, TM15, and at attach), when
tmux's text would land under the image. Left as it is: what puritty
shows is the program's intent, and following tmux's cursor would draw
text over the image. Gone with tmux master's Kitty parsing (IM1).

## IM19 · Sixel (2026-11-17)

Built as `docs/images-sixel.md` says (SX1 the references, SX2 the
choices, SX3 what was measured): `Vt.Sixel` decodes in Geng to RGBA, and
the image goes into the Kitty store as an implicit image with a
placement under the text, so scrolling, erasing, the alternate screen,
the limit (0 turns Sixel off too) and the panes of `tmux -CC` take it as
they take Kitty's. DA1 now says `4`, and chafa and timg choose Sixel in
puritty with no flag (IM17 needed `-f kitty`). Sixel is the embedder's
(`sixel` in `Vt.Embedder`, on in the app and its tmux panes), off in
the oracle's terminal, so the differential fuzzer and the replay corpus
see the core ignore a Sixel DCS as Ghostty does.

## IM10 · The user guide, drafted

Kept here, not in `docs/user/` (which `site/sync.py` publishes whole),
until the first protocol works; then it moves to `docs/user/images.md`.

> **# Images in the terminal**
>
> Programs can show pictures in puritty: an image viewer such as `chafa`
> or `timg`, a file manager such as `yazi`, plots from `gnuplot`. They
> send the picture in one of three ways, and puritty understands all
> three: **Sixel**, **Kitty graphics** and **iTerm2's inline images**.
> There is nothing to install or turn on; most programs ask the terminal
> which it supports and choose.
>
> **Over ssh** it works the same: the picture travels in the program's
> output.
>
> **In tmux.** With puritty's tmux integration (`tmux -CC`), pictures
> work in any tmux, from any of the three ways. Two things are tmux's,
> not puritty's: a picture shown before you attached, or before you
> reconnected, does not come back (tmux keeps only the text), and a
> program asks *tmux* which way to send pictures, so under an older tmux
> it may send none unless told (`chafa -f sixel`). In plain tmux
> (without `-CC`), pictures need tmux 3.4 or later built with Sixel.
>
> **Limits.** A remote program can't make puritty open your files: it
> must send the picture itself. Very large pictures are refused, and
> when pictures together use more memory than the limit in the settings
> (Advanced), the oldest ones no longer on screen go first.

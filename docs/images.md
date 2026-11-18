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
JPEG and GIF (iTerm2's) are decided when iTerm2's step comes (done:
in Geng as well, `images-iterm.md` IT4). The oracle
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
- **A resize that rewraps lines did not** (`kitty-resize-reflow`, with
  its divergence): Ghostty's pins reflow with their rows and by rules of
  their own; the core kept absolute rows. Done in IM25, and the
  divergence gone.

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

## IM20 · iTerm2's images (2026-11-17)

Built as `docs/images-iterm.md` says (IT1 the protocol, IT2 the choices,
IT3 what was measured): `OSC 1337 File` and the multipart form, read as
long strings; PNG and uncompressed TIFF decoded in Geng (`Vt.Tiff` new);
sizes in cells drawn by the placement, other sizes resampled in the
core; kept in the Kitty store as Sixel's are. With Sixel, it is the
embedder's (`extraImages`, renamed from `sixel`). JPEG and GIF were left
(done in `images-iterm.md` IT4):
the guide's promise of "all three" holds for what chafa and timg send,
not yet for `imgcat` of a photo.

## IM21 · The terminal's size in pixels (2026-11-17)

Every pty puritty started, and every ssh `pty-req` and `window-change`,
said the terminal was 0 by 0 pixels: a program that sizes its images by
`TIOCGWINSZ` alone could not. chafa and timg ask `CSI 16 t` as well, so
they drew right (SX3), but timg takes the pty's pixels when they are set.

Now the size goes with its pixels, the cells times the cell size, at
most 65,535 each: at the start of a local program and of each new tab,
at each resize, at a reconnect, and in ssh's `pty-req` (the cell when the
window opened) and `window-change` (sent as the session starts, SC26).
For a local program this needed `Os.Process` to carry pixels (geng-lang
`m3-os.md` OS38, Dnene61); on Windows a pseudo console has none, so only
ssh sessions get them there. A zoom that keeps the columns and rows does
not send the new pixels: the resize is sent when the cells change.

**Measured:** puritty under the gate's font, a local `python3` reading
`TIOCGWINSZ`: 24 80 720 408, the 9 by 17 cell. The ssh package's
`session-pty-pixels` and `session-resize-pixels` against OpenSSH's sshd:
the remote pty says 800 by 480, then 960 by 640 after a resize (68 of 68
cases pass).

## IM22 · Images in tmux `-CC` panes, measured (2026-11-17)

`bench/tmux/show.py --scenario images`: puritty attached to tmux 3.8 with
`-CC`, a 64 by 32 PNG (red left, green right) shown in a pane by chafa
1.18.2 and timg 1.6.3, each left to choose and told each protocol; each
program's output kept by `pipe-pane` to say what it sent.

- **What they choose.** Left to choose, both send Sixel in the pane (tmux
  answers their queries, puritty does not). Told Kitty, chafa sends plain
  Kitty and timg wraps it in tmux's passthrough (`ESC P tmux;` with each
  ESC inside doubled). Every one drew.
- **Passthrough needs nothing.** The doubled ESC ends the envelope's DCS,
  as a terminal's parser ends any string at ESC, and the sequence after it
  is read as it would be bare; the envelope's last `ESC \` is a stray ST.
  A Kitty image wrapped by hand drew the same, whatever tmux's
  `allow-passthrough` says, since a control client gets the pane's bytes
  before tmux reads them.
- **Detach and attach: the images are gone.** tmux sends a new client the
  panes' text, never their output again, so only images drawn after the
  attach are there. The guide says so.
- **`clear` in a pane is `CSI H CSI J CSI 3J`** (tmux-256color's), ED 0
  from the top left, not ED 2: Ghostty's rule takes no Kitty placement
  for it, so every image stayed under the new prompt. tmux's own rule
  (3.8's `image_check_line` and `image_check_area`) frees an image when
  any cell it covers is written or erased, a line inserted or deleted
  through it, and all of them on RI, a scroll down or a clear. For Sixel
  and iTerm2's images IM23 answers it; Kitty's in a `-CC` pane are
  `review.md` RV3.
- **iTerm2's image alone in a pane** drew in the 20 by 5 cells chafa asked
  for. chafa sized its TIFF by tmux's cell (16 by 32 pixels: 320 by 160),
  which puritty scales into the cells.

## IM23 · Text over an image drawn into the cells (2026-11-17)

A Sixel or iTerm2 image is drawn into the cells, as xterm and Windows
Terminal have it: a cell written or erased loses the image's pixels in
it. Windows Terminal erases them on a write (`TextBuffer::Replace`), on
ECH, EL, ED and DECERA (`ImageSlice::EraseCells`), and moves them with
the cells on ICH, DCH, IL, DL and scrolls (`CopyCells`, `CopyBlock`).
puritty, since IM19, kept them whole under the text, so a `clear` left
them on the screen (IM22).

**What it does now.** `Vt.Kitty.overwritten` takes a rectangle of the
screen's cells, and every image marked `textErases` (Sixel's and
iTerm2's; never Kitty's, which keep Ghostty's rule) under it records the
cells as a hole, in its placement's cells from the top left. Called by
the two fast print paths and `printPoint` (the cells just written), by
`eraseSpan` (EL, ECH, and the cursor's row of ED), by ED 0 and 1 for the
other rows, by ICH and DCH (the row from the cursor to the right margin)
and IL and DL (from the cursor's row to the bottom margin, between the
margins), and by DECALN. ICH, DCH, IL and DL take the cells they move
where Windows Terminal moves the pixels with them: a difference left. An
image whose every row is erased, or with more than 1024 holes, is gone.

The holes stay with the image; it is masked where its pixels leave the
core (`imageByKey`), each cell's pixels found as its placement draws it,
at its own size or scaled to its cells, with alpha 0. The image's key
carries a count of its erasures, so the window receives the new picture
once a frame while text changes it.

**Cost.** The call sites test `Array.isEmpty` of the placements before
calling, so a screen with none pays a few loads a run of text: 0.0% to
0.7% more instructions on twelve of the thirteen throughput inputs at
first, 1.4% on vte-unicode. Four of its first shapes made the terminal
copy, which IM24 found and changed; its numbers there are the whole
day's.

**Checked.** Nine tests in `vt/tests/src/Sixel.geng` (a write, a
character at a time making one hole, EL and ECH past the row's text, ED
0 from the top left taking the image, ED 1, rows lost one at a time,
ICH, DCH, IL and DL, text beside the image, a Kitty image left whole),
the pixel case `image-sixel-erase` (XY over two cells, EL across the
second row), and IM22's scenario, where `clear` now leaves no Sixel
image behind. `image-sixel-basic` was pinned again: its `cd`, written on
the image's last row of cells, now clears the one row of the image's
pixels under those two cells.

## IM24 · Scrolling 3.6 times slower since IM14, and what fixed it (2026-11-17)

`harness/perf.py` had not been run since 11-14, and on 11-17 every
throughput input was over its record: vte-scrolling at 2,611 M
instructions against 1,417 M, the region inputs at 2.3 times theirs, and
in cycles scrolling took 3.6 times as long. The 11-14 core (`839d92f`),
built with today's compiler, gave the record's counts exactly, so the
cause was puritty's. Building each core commit since: 2bc73b0 (IM12, the
Kitty store) 1,035.8 M on top_region, as recorded; e30e689 (IM14,
placements moving with scroll regions) 2,351.9 M.

**What it was.** `perf record` on e30e689's build: 62% of instructions in
`memmove` and 18% in the collector's `minor_scan`, where 2bc73b0's had
none. geng-lang's `GENG_INPLACE_REPORT` (`m4-investigate.md`) gave 398
updates in place before and 66 after. IM14 planned the placements' move
from the terminal before the scroll (`imagesPlan`) and handed the same
terminal to `feedRegion`, `regionDown` and `scrollUpRegion`; a function's
parameter is its own only when every caller hands it over unshared, so
those took the terminal shared for every caller, and every scroll copied
the screen's cells, images or none. The same rule found four more today,
each a result not shown fresh, which spreads to every caller:

| where | what made it copy | now |
|---|---|---|
| `Scroll.lineFeed`, `reverseIndex`, `Dispatch` SU and SD (IM14) | the plan read the terminal before the scroll took it | numbers read before (`pushedRows`, the margins), and the placements moved after, from the scrolled terminal (`imagesMoved`, `Placed.scrollMoved`, which plans from the store and the margins and updates the terminal it read) |
| `Dispatch.xtsmgraphics` (IM19) | a local `answer` closing over the terminal | the text worked out, then one `reply` |
| `Kitty.overwritten` (IM23) | the fold's step closing over the store, and the terminal returned beside what was read of it | a top-level step (`holedIf`), and one update of the terminal |
| `Print.printPoint` (IM23) | the test after it, inside the recursion `printPoint`, `edgeWide` | the test in its callers, `printGraphic` and `printDecoded` |
| `Parse`'s two print paths (IM23) | the cursor read after the update it was passed beside | read into a `let` before |

With those, the report has 434 updates in place, and `memmove` is gone
from the profile. `feedRegion`, given a second caller for the images'
path, was no longer inlined into `lineFeed`, which cost the region inputs
9%; `feedImaged` has its own copy of it (`feedRegionImaged`).

**Where it stands**, against 2bc73b0's build (`--against`, instructions
and cycles):

| input | instructions | cycles |
|---|---|---|
| cup | +1.6% | +0.4% |
| gitlog | +2.2% | −0.6% |
| ls | +3.6% | +3.7% |
| vte-cursor_motion | +1.6% | +0.8% |
| vte-dense_cells | +0.7% | 0.0% |
| vte-light_cells | +6.4% | +1.5% |
| vte-scrolling | +2.3% | −0.2% |
| the four region inputs | +5.2% | +2.8% to +3.5% |
| vte-scrolling_fullscreen | +4.7% | +1.7% |
| vte-unicode | −0.1% | +1.7% |

The same rule caught `core-bench` itself when IT4 gave it an `images`
mode: the terminal chosen as `(if images then f else identity) <| Vt.new
…` passed through a function value, which is never shown fresh, and the
counts went back to 2,681 M; `withImages`, a plain function, put them
back to the table's.

So the gate still fails at its 1%, by what all of today's image work adds
to a screen with no image (IM12 to IM23): the parser's Sixel and iTerm2
states, the tests for placements, the larger store. The record is not
moved: what is left is to be found as this was, one decision at a time,
or the record moved with the reason written here. Until then `perf.py`
says so.

## IM25 · Placements through a resize that rewraps lines (2026-11-17)

IM14 left one difference from Ghostty: a resize that changes the width
reflows the main screen's lines, and Ghostty's placements, pinned to cells,
move with them, where the core kept each placement's absolute row and
column. An image drawn in the cells (Sixel's, iTerm2's) is a placement too,
so after a narrower or wider window it was off its text.

**Ghostty's rule** (`PageList.reflowRow`): a tracked pin, which a
placement's anchor is, moves with the cell it is on; one in the blanks past
a row's last text first has its column held to `new width - 1 - the column
the row begins writing at`, and the row is walked as far as it, the blanks
advancing without being written. The cursor is not such a pin: its blanks
are kept as cells. The test of it: a cursor after `0123456789abcdef` at 10
columns, through 6 and then 20, ends at column 16; a placement there at
column 11 (`0123456789` and `abcdef`'s row begins at column 4 of a 6
column row, so the pin is held to column 1, offset 11). The core's saved
cursor already had that rule (`Vt.Resize.joinLines`), Ghostty's saved
cursor being such a pin.

**How the core does it**, around the resize in `Vt.resize` rather than in
`Vt.Resize`'s reflow, which carries two points through sixteen places and
the scrollback's pages through their own recut:

- `pinsBefore`, for a change of width on the main screen with autowrap on
  and placements present: the rows from a few hundred above the highest
  placement to the screen's end (`rowsBetween`), each row's line by the
  wrap flags, and for each placement its line's distance in lines from the
  cursor's and its offset in its line, the blanks rule applied at the new
  width. Numbers alone, so that the resize takes the term unshared (IM24).
- `pinsAfter`, on the resized term: the rows read again from the cursor's
  line up, each line found that many lines above the cursor's, and the
  offset walked through its new rows (a wrapped row gives its width, less
  a spacer head it ends with). Read and updated in one function.

Lines keep their count through a reflow, which is why a line counted from
the cursor's is found again. A placement whose line has left the scrollback
or the rows read keeps its anchor.

**Checked**: `kitty-resize-reflow` now gives Ghostty's dump, its
divergence and `ghostty.txt` removed; two new cases agree with Ghostty:
`kitty-reflow-on-text` (placements on cells of a 26-character line through
8, 13 and 30 columns) and `kitty-reflow-scrollback` (a placement that the
narrowing pushes into the scrollback, then a widening). The replay binary
(`harness/dump/core-dump`) had not been built again since the morning, so
the replay runs of IM22 to IT4 tested the morning's core; built again, all
353 cases passed but this one, which then passed as above. The diff
fuzzer's (`harness/fuzz/vt-diff`) was older still, built at 06:22, so the
day's fuzz runs before this one tested the core from before IM19; built
again, 8 minutes, 142 inputs, 0 findings. The resize inputs of
`perf.py` are within their record.

**Not done** (then): the alternate screen shown during the resize; done
in IM27.

## IM26 · No image on the screen, no cost (2026-11-17)

Gilbert, 2026-11-17: slower with an image on the screen is understood, but
with none it is to be as fast as before images. After IM24 the throughput
inputs were still 0 to 6.4% over the build before images (2bc73b0) in
instructions.

**What it was**, found by taking the image code out of a copy one piece
at a time and counting (`perf stat -e instructions:u`, `setarch -R`):

- All of it was IM23's test in Parse's two fast paths for text
  (`printAscii`, `printUnicode`), and the extra test in `lineFeed` that
  IM14 added. The tests in `printGraphic`, in the erases and elsewhere cost
  nothing measurable.
- Not the work of the test, nor the copies IM24 removed: testing a Bool of
  the term in its place cost the same, and so did a branch to the image
  code that never ran. `ground` runs once a run of text, so anything at all
  it does more costs a few instructions a run, 3% of `vte-light_cells`,
  whose runs are short; and a call out of the fast path with the term,
  even one never taken, made `vte-scrolling_top_region` cost more again.

**What does it now**: the tests the hot loops already make.

- `plain`, which `ground` tests before it takes a run of text, now also
  says there are no placements (`Vt.Cursor.withPlain`). With an image on
  the screen, text goes a character at a time, by `printGraphic`, which
  tells the images of each cell it writes (IM23). The fast paths are as
  they were before images, with no image code in them.
- `scroll`, which `lineFeed` tests at the region's bottom, is no longer
  `scrollRegion` while there are placements (`withScroll`): a region's
  line feed with an image takes the other way, which moves the placements
  (`feedImaged`); without one, `lineFeed`'s three branches are as before.
- Both are found again where placements come and go: `Kitty.withStore`,
  which every placement added goes through, and the screens' swap; and
  once a read where `plain` is off (`Parse.feed`), for the last image gone
  by a scroll, a clip or an erase.

**Measured**, instructions in millions, the build before images, the
build before this change, and now:

| input | before images | before this | now |
|---|---|---|---|
| vte-light_cells | 261.4 | 278.1 | 261.4 |
| vte-scrolling_top_region | 1,035.8 | 1,089.2 | 1,035.8 |
| vte-scrolling | 1,417.7 | 1,449.9 | 1,418.0 |
| ls | 1,390.1 | 1,440.2 | 1,390.3 |
| vte-scrolling_fullscreen | 345.6 | 362.0 | 345.6 |
| cup | 1,645.1 | 1,671.9 | 1,645.7 |

The cost moved to text written while an image is on the screen, a
character at a time, which is what was asked.

## IM27 · Slower only for a picture text can erase, on the screen; and the alternate screen's resize (2026-11-17)

IM26 made any placement turn off the fast ways: text a character at a
time, a region's line feed by `feedImaged`. Gilbert, 2026-11-17: narrow it.

**What changed.** `Placed.onScreen` says whether a placement covers a row
at or below the screen's top: any, or one of an image drawn into the cells
(Sixel's, iTerm2's), which text erases (IM23).

- `plain` (`Cursor.withPlain`) asks the narrow question: a Kitty picture,
  which text never erases, or one in the scrollback, which text never
  reaches, leaves text its fast way.
- `withScroll` asks the wide one: a region's fast line feed is not taken
  while any picture is on the screen, since the region's scroll moves it
  (IM14); one in the scrollback leaves it.
- Both are found again once a read while there are placements
  (`Parse.feed`), for a picture scrolled off the screen.

`onScreen` is a loop with the store as an argument: its first form, an
`Array.any` with a closure over the store, made `withScroll`'s result not
fresh, and every update of the term copied (311 M instructions on
`vte-light_cells` against 261 M), as in IM24.

**Measured** (instructions in millions, `core-bench FILE images`, 200,000
lines of 62 characters, no clear), the commit before and now:

| text after | before | now |
|---|---|---|
| no picture | 605 | 605 |
| a Kitty picture, scrolled away | 7,268 | 606 |
| a Sixel picture, scrolled away | 11,586 | 662 |
| a Kitty picture kept by a scroll region | 7,853 | 1,208 |
| a Sixel picture kept by a scroll region | 12,169 | 12,172 |

So a Kitty picture, and any picture once scrolled away, costs text
nothing; a Kitty picture beside a region costs the region's line feeds
twice (`feedImaged`'s plan, 3,000 instructions a line). A Sixel or iTerm2
picture on the screen still makes text some 20 times slower: a character
at a time through `printGraphic`, each telling the images of its cell. That
is left (IM28, tried and not done): a second copy of the ground loop for that case,
taking runs with a hole each, would bring it near the fast way, with the
loop without images untouched.

**The alternate screen** (IM25's "not done"): `Vt.resize` now carries the
main screen's placements while the alternate screen is shown: its rows
read from the main screen (`mainRows`, a reader of a given screen's ring),
its cursor from `hidden`, its store from the `other` slot, and the moved
placements written back there. `kitty-reflow-alt-screen` (a placement on
the main screen's text, the alternate shown, 6 and then 20 columns, back)
agrees with Ghostty: column 12, its `c`. The diff fuzzer found the same at
5 rows putting the placement at column 4: the narrowing pushes the line
into the main screen's scrollback, and the readers took the scrollback's
size from `scrollbackRows`, which is 0 while the alternate screen is
shown; they take `Scroll.historyBound`, the main screen's, now, and
`kitty-reflow-alt-scrollback` keeps the case.

## IM28 · Runs of text beside a Sixel or iTerm2 picture: tried, not done (2026-11-18)

IM27 left text some 20 times slower while a picture text erases is on the
screen. Tried: a flag `textPlain` (`plain` without the picture test), and
for that case the run written at once and the picture's cells lost for the
run together (`Kitty.overwritten` over the run's span), not a character at
a time.

**What it gave**: a Sixel picture kept by a scroll region, 200,000 lines
of text, 12,172 M instructions to about 1,260 M, near the Kitty picture's
1,208 M.

**What it cost text without pictures** (instructions in millions, the
throughput inputs, against f20d778), through every shape tried:

| shape | light_cells | scrolling_top_region | scrolling | cup |
|---|---|---|---|---|
| f20d778 | 261.4 | 1,035.7 | 1,418.0 | 1,645.7 |
| a copy of `printAscii` in `ground`'s group | 295.5 | 1,113.1 | 1,498.0 | 1,717.7 |
| an empty wrapper, in the group, around the old branch | 286.1 | 1,041.1 | 1,423.3 | 1,669.9 |
| the hole first, then `printAscii` called a second time | 296.7 | 1,198.4 | 1,580.6 | 1,816.3 |
| the hole first, through `printAscii`'s one call | 301.5 | 1,025.1 | 1,409.9 | 1,644.5 |
| outside the group, with its own copies of `asciiRow` and `writeAscii` (the best) | 261.6 | 1,059.7 | 1,442.0 | 1,657.7 |
| the same, routed by `resume` to `groundMargined` | 261.7 | 1,051.7 | 1,434.0 | 1,677.7 |

The new code never runs on these inputs. The cost is clang's: each member
the group gains, and each hot function that gains a caller (`asciiRow`,
`writeAscii`, `printAscii`), changes how it compiles the loop's step
function. Taken apart, the best shape's hole alone costs nothing
(1,030.4, 1,412.6, 1,641.7), and its write alone all of it: a second
writer of runs is what the loop pays for.

**Decided** (Gilbert, 2026-11-18): not done. Text with no picture on the
screen, which is the measurement that matters, stays at the speed it had
before images; a Sixel or iTerm2 picture on the screen keeps text slow
until it scrolls away, as IM27 left it.

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
> it may send none unless told (`chafa -f sixel`). A program that wraps
> its picture for tmux (`timg` does) works too, whatever tmux's
> `allow-passthrough` says. In plain tmux (without `-CC`), pictures need
> tmux 3.4 or later built with Sixel.
>
> **Text over a picture.** Text written over a Sixel or iTerm2 picture
> takes the picture's place in those cells, and erasing cells (`clear`,
> deleting a line) erases the picture there too, as in xterm. A Kitty
> picture stays until the program removes it or the screen is cleared.
>
> **Limits.** A remote program can't make puritty open your files: it
> must send the picture itself. Very large pictures are refused, and
> when pictures together use more memory than the limit in the settings
> (Advanced), the oldest ones no longer on screen go first.

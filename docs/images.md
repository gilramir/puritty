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

# Sixel: what puritty does

The Sixel step of `images.md` (IM8; IM17 made it next). Read on
2026-11-17 in Windows Terminal's `SixelParser.cpp` (vendored at
`vendor/terminal`, a VT340 emulation tested against the hardware; **WT**),
WezTerm (**WZ**), tmux 3.4 and 3.8 (**TM**), chafa and timg; xterm's
behaviour from its documentation where no source was read (marked so).
Ghostty has no Sixel: there is no oracle, so puritty's own replay cases
and pixel tests hold it, and the differential fuzzer leaves out inputs
with a Sixel DCS (Ghostty ignores them, the core draws them).

## SX1 · What the references do

- **Framing.** `DCS P1;P2;P3 q … ST`, no intermediates (WT, WZ, TM agree).
  P1 an aspect macro (7, 8, 9 1:1; 0, 1, 5, 6 2:1; 3, 4 3:1; 2 5:1; WT
  honours it as each sixel bit that many pixels tall, WZ and TM ignore
  it); P2 1 leaves unset pixels transparent, 0 or 2 fills them; P3
  ignored. C0 bytes inside are ignored (WT); tmux drops a whole image on a
  byte it does not know, WT and WZ skip it.
- **Commands.** `"Pan;Pad;Ph;Pv` raster attributes (WT: aspect
  `ceil(Pan/Pad)`, Ph×Pv the background fill's size, data may go past
  it, and a graphics CR); `#Pc` selects, `#Pc;Pu;Px;Py;Pz` defines and
  selects (WT; WZ defines only, a bug) in HLS (Pu 1, DEC's hue: blue 0,
  red 120, green 240) or RGB percent (Pu 2, `(v·255+50)/100`, WT); `!Pn`
  repeats (0 or none is 1); `$` back to the first column; `-` down six
  rows (six times the aspect in WT); 0x3F–0x7E data, bit 0 the top
  pixel, x advancing one.
- **Registers.** 1024 (xterm, tmux; WT 256). VT340's sixteen first:
  `000000 3333CC CC2424 33CC33 CC33CC 33CCCC CCCC33 787878 454545 575799
  994545 579957 995799 579999 999957 CCCCCC` (WT; WZ has 6 grey, a bug),
  xterm's 256-colour palette after them (WT). xterm's private registers
  (mode 1070) are on by default (from documentation): a fresh palette an
  image. The colour before any `#`: register 15 (WT).
- **Size.** Without raster attributes, the furthest x reached by the
  six-row bands holding data (WZ). Limits: WZ 100 MB of RGBA, TM
  10000 by 10000, xterm 1000 by 1000 by default (documentation).
- **Placement and cursor.** The cursor's cell, `ceil(w/cw)` by
  `ceil(h/ch)` cells. DECSDM reset (the default): scrolling as each band
  needs room; the cursor ends in the start column on the row holding the
  top of the last band (VT340, WT; WZ alike); with `?8452h` right of the
  image on that row. DECSDM set (`?80h`): at the screen's top left,
  clipped at the bottom, the cursor not moved. tmux: the row after the
  image, column 0.
- **Text over an image.** WT erases only the overwritten cells' pixels;
  tmux removes the whole image; WZ keeps a per-cell image.
- **Reports.** DA1 with `4`. XTSMGRAPHICS `CSI ? Pi ; Pa ; Pv S`, Pi 1
  colours, 2 geometry; Pa 1 read, 2 reset, 3 set, 4 read the most;
  `CSI ? Pi ; Ps ; … S`, Ps 0 done, 1 bad item, 2 bad action, 3 failed.
  tmux answers `?1;0;1024S` and no geometry; WZ `?2;0;W;HS`.
- **chafa and timg.** Both pick Sixel by DA1's `4`; both size by `CSI
  16 t` (and `TIOCGWINSZ`'s pixels when set: timg only when they are at
  least 2 by 4 a cell). timg sends ANSI `CSI 80h` (no `?`).

## SX2 · puritty's choices

Where the references differ, xterm's semantics as WT emulates them:

1. `q` with no intermediates; C0 inside ignored; CAN or SUB abort (what
   was decoded is shown, as WZ shows it); ESC or ST ends it.
2. P1's aspect honoured as WT honours it, and raster `Pan/Pad`; P2 1
   transparent, else the image's extent filled with register 0; P3
   ignored.
3. Parameters clamped to 65535; a repeat of 0 or none is 1; an unknown
   command byte ignored, never the whole image dropped.
4. `#` defines and selects; HLS and RGB as WT; an unknown Pu selects
   without defining.
5. 1024 registers, a fresh palette each image (1070 set): VT340's
   sixteen, xterm's 256, black above; colour 15 before any `#`.
6. Raster Ph×Pv sets the fill's size and the least image size; data may
   go past it.
7. Clipped at 10000 by 10000 pixels (as Kitty's KG5), not dropped; a 0
   by 0 image drawn as nothing.
8. Kept as an image and a placement in the core's store (the Kitty
   store: an implicit id, the screen's own placements), so scrolling,
   erasing, the alternate screen and the panes of `tmux -CC` (IM14, IM18)
   take it as they take Kitty's. Under the text (z −1), so text later
   printed over it is seen: WT's rule of erasing the overwritten cells'
   pixels is not followed in this step.
9. The cursor as VT340 and WT: DECSDM reset scrolls as bands need room
   and ends in the start column on the row of the last band's top; with
   `?8452h` right of the image on that row; DECSDM set draws at the top
   left, clipped, the cursor kept.
10. DA1 says `4`; XTSMGRAPHICS answers colours `?1;0;1024S` (read, reset
    and read the most; set as failed) and geometry `?2;0;W;HS` (the
    window clamped to 10000, and 10000 by 10000 for the most).
11. ANSI `CSI 80h` is nothing, as it is today.

Follow-ups noted: `pty-req` and `window-change` send 0 pixels, and the
local pty's pixel size is not set; chafa and timg ask `CSI 16 t`, which
the core answers, but a program that reads only `TIOCGWINSZ` would not
know the cell's pixels.

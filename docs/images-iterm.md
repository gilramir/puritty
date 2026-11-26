# iTerm2's inline images: what puritty does

The third way of `images.md` (IM8), after Kitty's (`images-kitty.md`) and
Sixel (`images-sixel.md`). Read on 2026-11-17 in WezTerm
(`vendor/wezterm`: `wezterm-escape-parser/src/osc.rs`, `ITermFileData`;
`term/src/terminalstate/iterm.rs` and `image.rs`) and iTerm2's
documentation of the protocol; iTerm2's own source is not vendored.
Ghostty has none of it: as with Sixel, no oracle, and the oracle's
terminal ignores the sequence as Ghostty does.

## IT1 · The protocol, and what programs send

- `OSC 1337 ; File = ARGS : BASE64 ST` (or BEL). `ARGS` are `key=value`
  separated by `;`: `name` (base64), `size` (bytes), `width` and
  `height` (`N` cells, `Npx`, `N%` of the terminal, or `auto`, the
  default), `preserveAspectRatio` (1 by default), `inline` (0 by
  default: a download, not shown), and WezTerm's `doNotMoveCursor`.
- iTerm2 3.5's multipart form: `OSC 1337 ; MultipartFile = ARGS ST`,
  then `OSC 1337 ; FilePart = BASE64 ST` any number of times, then
  `OSC 1337 ; FileEnd ST`. WezTerm does not have it.
- **Sizes.** iTerm2's documentation: with the aspect preserved, the image
  "will fill the specified width and height as much as possible without
  stretching"; WezTerm instead takes the width and works out the
  height. `auto` both ways is the image's own size, scaled down to fit
  the terminal (WezTerm).
- **Cursor.** WezTerm, as iTerm2: the image's rows taken by newlines
  (which scroll), the cursor left right of the image on its last row;
  `doNotMoveCursor` leaves it.
- **What is sent.** Measured with the devbox's chafa 1.18.2 and timg
  1.6.3: chafa `-f iterm` sends an uncompressed little-endian TIFF, RGBA,
  8 bits a sample, one strip, `width=10;height=4;preserveAspectRatio=0`
  in cells; timg `-pi` a PNG, `width=64px;height=48px`, its own size;
  both a newline after. iTerm2's `imgcat` sends the file as it is, so a
  JPEG or a GIF arrives as one.

## IT2 · puritty's choices

1. `File` and the multipart form, read as long strings as OSC 52's and
   Kitty's are (up to Kitty's 65 MiB); `inline=0` is a download, which
   puritty does not do: nothing is kept.
2. Decoded in Geng: PNG (`Vt.Png`), uncompressed TIFF of 8-bit RGB or
   RGBA (`Vt.Tiff`), what chafa and timg send, and JPEG (`Vt.Jpeg`) and
   GIF's first frame (`Vt.Gif`), what `imgcat` of a photo sends (IT4).
3. The size as iTerm2's documentation says (fit within the box with the
   aspect kept), `%` of the terminal's cells, `auto` the image's own
   size fitted to the terminal. Drawn in whole cells, a size the
   placement draws itself (KG); any other size, `Npx` not the image's
   own or a fitted one, resampled in the core (bilinear) to the exact
   pixels and drawn at its own size.
4. Kept in the Kitty store as Sixel's are (SX2 8): an implicit image, a
   placement under the text, so scrolling, erasing, the alternate
   screen, the limit (0 off) and `tmux -CC` panes take it.
5. The cursor as WezTerm and iTerm2 leave it: down through the image's
   rows by IND, right of the image on its last row; `doNotMoveCursor`
   keeps it.
6. On with Sixel, by the embedder (`extraImages` in `Vt.Embedder`): the
   oracle's terminal has it off, so the diff fuzzer and the replay
   corpus see the core ignore the sequence as Ghostty does.

## IT3 · What was measured (2026-11-17)

- **chafa `-f iterm` and timg `-pi`, in puritty:** both drew their test
  picture, chafa's TIFF in the cells it asked for, timg's PNG at its own
  200 by 120 pixels, the next line under each. Left to choose, both
  choose Sixel in puritty (SX3), so this form is for programs told to
  use it, and for `imgcat`.
- **The first run of timg drew nothing:** `Vt.Png.decode`'s first
  argument is the most bytes of pixels, and 10,000 had been passed as if
  it were a side; it is the terminal's image limit now.
- **The tests:** twelve in `vt/tests/src/Iterm.geng` (TIFF, PNG, a
  download, cells, the aspect fitted, pixels resampled, `doNotMoveCursor`,
  the multipart form, a split read, off, a limit of 0, overlapping
  strips), and the pixel
  case `image-iterm-basic` (a PNG at its own size and the TIFF in 3 by 1
  cells, each with text after it).
- **Not yet** (then): JPEG and GIF, done in IT4; an animated GIF's frames
  after its first are still not shown.

## IT4 · JPEG and GIF, decoded in Geng (2026-11-17)

As PNG and zlib are (IM4, the user's choice for a remote program's
data: no C decoder, so no buffer overrun), both in the core:

- **`Vt.Jpeg`**: the baseline and extended sequential processes with
  Huffman coding (SOF0, SOF1), 8-bit samples; grey, YCbCr, or RGB where an
  Adobe marker says its transform is 0; any sampling factors; restart
  intervals (the entropy data is unstuffed and cut at each RST into a
  segment of its own); scans interleaved or one component each. Each
  block dequantized and transformed in floating point (a block with only
  its DC is one value). Chroma half as wide, or half as wide and tall, is
  smoothed as libjpeg does it ("fancy upsampling", h2v1 and h2v2, its
  weights and rounding); any other ratio takes the nearest sample.
  Progressive (done in IT6), arithmetic-coded, lossless, 12-bit and CMYK
  files are not decoded and say which. EXIF orientation is not applied: a phone's
  photo taken on its side shows on its side (done in IT5).
- **`Vt.Gif`**: the first frame, as a still picture on the logical
  screen (clear where the frame does not reach): the global or the
  frame's own colour table, the graphic control extension's transparent
  index, LZW codes from 3 to 12 bits with the table cleared and grown as
  the format says, and interlaced rows put in their places.

Both are chosen by their first bytes (`FF D8`, `GIF`) in
`Vt.Iterm.decoded`, beside PNG and TIFF, and held to the terminal's image
limit. `Vt.Jpeg` and `Vt.Gif` are exposed by the package, for their tests.

**Bounded before the work** (the code review's VI1 and VI3, 2026-11-21).
The TIFF decoder is held to the image limit too, before it reads a strip,
and reads the strips only up to the pixels' bytes: 99,999 strips each
naming the same 64 KB had been joined first, 6.5 GB from a 400 KB file. A
JPEG scan names one to four components, each once and each in the frame;
a sequential file scans each component once; a progressive one has at
most 100 scans. Each scan is a pass over the frame's blocks, so a few KB
of empty scans on a large frame had been hours of work.

**Measured** (2026-11-17):

- **Against libjpeg**: six JPEGs Pillow made (`vt/tests/gen-jpeg.py`:
  4:4:4, 4:2:0, 4:2:2 at 13 by 7, grey, a restart marker every block,
  optimized tables), each decoded and held to libjpeg's pixels through
  Pillow. Taking the nearest chroma sample, they differed by up to 21;
  with libjpeg's smoothing, by at most 2, and 3 where chroma is
  subsampled, which is the integer transform's against this one's; held
  to 3. A progressive JPEG says "progressive JPEG". Grey matched exactly.
- **Against Pillow's GIF reader**: five GIFs (`vt/tests/gen-gif.py`: 256
  colours, 4 colours and 3-bit codes, interlaced, a transparent index, an
  animation's first frame), each first frame byte for byte the same.
- **Speed**, natively, `core-bench FILE images` (the app's image limit
  and a 9 by 17 cell), an iTerm2 sequence of a photo-like JPEG at quality
  90, 4:2:0: 1920 by 1080 in 189 ms and 4000 by 3000 in 807 ms, each
  with its resize to fit 160 by 50 cells. The first version took 492 ms
  and 2,558 ms: `Array.range` in the inner loops and each sample finding
  its component again; the transform's sums are now written out, the
  loops counted, and each component's place found once.
- **Drawn**: the pixel case `image-iterm-jpeg-gif`, a JPEG and a GIF each
  with text after it.

**Not done** (then): progressive JPEG and EXIF orientation, done in IT6
and IT5; an animated GIF's later frames, still.

## IT5 · A camera's orientation (2026-11-17)

A phone stores a photo as its sensor saw it and writes how to turn it in
the Exif data (APP1, `Exif\0\0` and a TIFF directory, tag 0x0112, 1 to
8). Browsers and macOS's image views turn it; puritty showed it on its
side. `Vt.Jpeg` now reads the tag (either byte order; Pillow writes
big-endian, which the first version read wrongly, and the tests caught)
and turns the decoded picture as it says: 2 mirrored, 3 a half turn, 4
flipped, 5 transposed, 6 a quarter clockwise, 7 transverse, 8 a quarter
counterclockwise, 5 to 8 swapping width and height. The size asked for
(IT2 3) is the turned picture's.

**Checked**: four JPEGs of 16 by 8 with orientation 2, 3, 6 and 8,
each held within 3 to what Pillow's `ImageOps.exif_transpose` makes of
libjpeg's pixels; 6 and 8 come out 8 by 16.

## IT6 · Progressive JPEG (2026-11-17)

A progressive JPEG (SOF2), as many pictures on the web are, sends each
block in parts: the DC in one scan, then bands of the AC coefficients, and
then each again a bit at a time. So every block's coefficients are kept
across the scans (in the planes' own places: a plane holds 64 samples a
block), and each block is dequantized and transformed once they are all
read. The four procedures are stb_image's (`stbi__jpeg_decode_block_prog_dc`
and `_ac`): the DC's first bits and its refinement, an AC band's first
bits with its end-of-band runs over the blocks after, and an AC band's
refinement, which places new values of ±1 past runs of zeros and gives
each coefficient already not zero a correction bit. A progressive scan
uses one of its two Huffman tables, and the other may not be defined yet,
which a baseline scan's may not. Restart intervals reset the predictions
and the end-of-band run. Differential and arithmetic-coded processes still
say they are not decoded.

**Checked**: four progressive JPEGs Pillow made (4:2:0, 4:4:4, grey, a
restart marker every block), each within 3 of libjpeg, as the baseline
ones are. A lossless one (SOF3) says it is not decoded. **Speed**, a
photo-like progressive JPEG through `core-bench FILE images`: 1920 by
1080 in 231 ms, 4000 by 3000 in 988 ms (baseline: 189 and 807). The first
version took 1,825 ms: each coefficient found its zigzag place by a
search, now a table.

## IT7 · Green as libjpeg rounds it (2026-11-25)

The code review's VI12. YCbCr to RGB takes libjpeg's constants in 16.16,
but green was `y - ((22554·cb + 46802·cr - 32768) >> 16)`, the floor of
the negated sum negated, which is its ceiling: one more than libjpeg's
`y + ((32768 - 22554·cb - 46802·cr) >> 16)` whenever the quotient is not
whole, and with `cb` and `cr` at 128 (neutral) always. Every grey came
out with green one up: black (0, 1, 0). The tests hold a colour file to
within 3 of libjpeg (IT4), which the transforms' difference fills, so it
was not seen. Green is now libjpeg's form.

vt's Jpeg suite gains flat greys, 8 by 8 at 4:4:4, of 0, 128 and 200:
libjpeg (Pillow) decodes them to themselves, the old decoder to (0, 1, 0),
(128, 129, 128) and (200, 201, 200), the new to the greys (242). The
largest differences from libjpeg over the suite's fourteen files are as
before (2, and 3 for 4:2:0) but for the 4:2:2 file of 13 by 7, 2 now 1;
they are the transforms', so the bound of 3 stays.

The pixel gate's `image-iterm-jpeg-gif` pin was made with the old green,
and that gate was not run with this change: it failed from then, and was
found on 2026-11-26 with the code review's X fixes. Of its 216 by 102
pixels, 2,444 differed, each in green alone and each by one, the drawn
one lower: this section's rounding, no other change. The pin was made
again.

## IT8 · TIFF made RGBA by a counted loop (2026-11-25)

The code review's VI13. An uncompressed TIFF of three samples or grey
was made RGBA by folding over `Array.range 0 (n - 1)`, every pixel's
index, building a four-element array a pixel and folding over it into a
`Builder UInt8`, then copying that into `Bytes`. It is now a counted
loop writing each pixel's four bytes into a `Bytes.Builder` (as IM39's
decoders write).

Measured with `harness/dump/core-dump` built with the app's limits, five
1920-by-1080 TIFFs sent as iTerm2 images, at 200 by 60 cells (2,000 by
1,200 pixels, so not resampled), two runs each: RGB (6.2 MB a file) 0.45
to 0.48 s and 147 MB before, 0.45 to 0.46 s and 123 MB after; grey (2.1
MB) 0.35 to 0.36 s and 112 to 113 MB before, 0.35 s and 78 to 83 MB
after; the same pixels. The time was not the array's, which the
compiler's passes had made cheap; the memory was.

## IT9 · The limit on what is kept, and why an image is not shown (2026-11-25)

The code review's VI14 and VI15.

**VI14.** A `File` sized to whole cells is kept at its own size and drawn
scaled by its placement (IT2), but the image limit was tested against
the size drawn, `width × height × 4`, before that was known. In a tmux
pane (a 10 MB limit, IM30) `imgcat --width 100% --height 100%` of a small
picture on a pane past 1,700 by 1,500 pixels drew nothing, though what
would be kept was a few KB. Now the limit is held to what is kept: the
image as decoded (which its decoder held to the limit already) when it
is drawn at its own size or over whole cells, the resampled pixels
otherwise. vt's Iterm suite: the 2-by-2 TIFF over 10 by 5 cells of 10 by
20 pixels (100 by 100 drawn, 40,000 bytes) under a limit of 1,000 is
shown, scaled by its placement; at 95 by 95 pixels, resampled to 36,100
bytes, it is not. The old code showed neither.

**VI15.** Each decoder answers why it does not decode ("compressed", a
JPEG process not decoded, "too large"), and `Iterm.file` dropped it to
`Nothing`: an LZW TIFF or a CMYK JPEG drew nothing, and nothing said why
(IT3's first timg run cost a session so). `Iterm.file` now answers the
reason, with the format before it, or that the `File` is a download, or
that its data is not base64, or that it is too large; and the core says
it to the diagnostic log at level 2, as it says a sequence it ignores
(DG6): `iTerm2 image not shown: JPEG: a JPEG process not decoded
(lossless, hierarchical or arithmetic)`. vt's Heard suite holds three
(244).

## IT10 · One frame a JPEG (2026-11-25)

The code review's VI19. A SOF segment was read by `frameOf body |>
Result.andThen (\f -> markers ...)`, the next marker read from inside
the closure, so every SOF met nested one more call where every other
marker is a loop, and a second SOF replaced the frame that the scans
before it were read for. Now `markers` takes `frameOf`'s answer by
`when`, a tail call, and refuses a second frame ("a second frame"). vt's
Jpeg suite: an 8-by-8 JPEG decodes, the same with its SOF0 segment
written twice is refused (248); the old decoder decoded both.

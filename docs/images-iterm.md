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
2. Decoded in Geng: PNG (`Vt.Png`) and uncompressed TIFF of 8-bit RGB or
   RGBA (`Vt.Tiff`), what chafa and timg send. JPEG and GIF are not yet
   decoded: an image in them is not shown (IT3).
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
- **The tests:** eleven in `vt/tests/src/Iterm.geng` (TIFF, PNG, a
  download, cells, the aspect fitted, pixels resampled, `doNotMoveCursor`,
  the multipart form, a split read, off, a limit of 0), and the pixel
  case `image-iterm-basic` (a PNG at its own size and the TIFF in 3 by 1
  cells, each with text after it).
- **Not yet:** JPEG and GIF (`imgcat photo.jpg` shows nothing yet), and
  an animated GIF's frames.


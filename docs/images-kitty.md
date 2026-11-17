# Kitty graphics as libghostty-vt has it

What the core must match for the oracle to agree (`images.md` IM7, IM8
step 2), read in Ghostty v1.4.0 as the oracle builds it (2026-11-17):
direct transmission only, a 10,000,000-byte limit, no PNG decoder, zlib by
wuffs. `cmd`, `exec`, `img`, `sto` are `src/terminal/kitty/graphics_command.zig`,
`_exec.zig`, `_image.zig`, `_storage.zig`. Not run, only read, where it
says so.

## KG1 · Framing

- APC bytes 0x00–0x17, 0x19, 0x1C–0x7F are the string (BEL, CR and LF
  among them). ESC ends it (the `\` after is an ordinary escape), as does
  0x9C. CAN, SUB or another C1 byte abort it: nothing is done.
- Kitty's only when the first byte is `G`; any other APC is ignored.
- At most 65 MiB of payload (the base64 after `;`); more drops it whole.
- Keys are one letter. A longer key's value is skipped; a one-character
  non-letter key is read and dropped. A value over 11 characters is
  skipped, the key left unset. A one-character value that is not a digit
  is its ASCII code (`a=t` is 116, `i=a` is 97); any other value is a
  decimal u32 (`z`, `H`, `V` i32) that takes a leading `+`, `-0` and
  inner underscores (`1_0` is 10); an empty value, a sign on a u32 or junk
  drops the whole APC, no reply. The last of a duplicate key wins.
- Ending after a key (a trailing comma, a bare `G`) drops it. `G;data` is
  valid; no `;` is an empty payload. `a` must be one of `q t T p d f a c`,
  `t` one of `d f t s`, `o` only `z`, else dropped. An unknown `f` is not
  dropped (it is replied to, KG3). The payload is base64-decoded first
  (simdutf, loose: whitespace skipped, padding optional, not run); a bad
  one drops the APC silently.

## KG2 · Keys

`a` (default `t`), `q` (0, 1 only errors, ≥2 nothing), `f` (default 32;
24 RGB, 0 or 32 RGBA, 100 PNG, other "unsupported format"), `t` (default
`d`), `o`, `s` `v` (size), `S` `O`, `i` (id), `I` (number), `p`
(placement), `m` (more, read only when the command's own `t` is `d`), `N`
(bit 0 transient), `x y w h` (source), `X Y` (offset in the cell), `c r`
(cells), `C` (1: no cursor move), `U` (virtual), `z` (i32), `P Q` (parent),
`H V` (i32), `d` (default `a`).

## KG3 · Actions and replies

- Reply: `ESC _ G` `i=ID` [`,I=N`] [`,p=P`] [`,r=F`] `;` message `ESC \`,
  each field only when non-zero; **none at all when both i and I are 0**,
  errors too. q=1 sends errors only, q≥2 nothing.
- First, any command with both i>0 and I>0: `EINVAL: image ID and number
  are mutually exclusive` (with i, I, p), only q≥2 hiding it; a=d and a
  chunk's continuation too.
- Errors: `ENOMEM: out of memory`, `EINVAL: invalid data`, `EINVAL:
  decompression failed`, `EINVAL: unsupported format`, `EINVAL:
  unsupported medium`, `EINVAL: dimensions required`, `EINVAL: dimensions
  too large`, `ENOENT: image not found`, and the parent errors (KG6).
- **a=t, a=T**: with i>0 and no load in progress, image i and its
  placements go first, even if this transmission fails. No i: with I, the
  lowest unused id ≥ 1; with neither, an implicit id counting up from
  2147483647. An image over the whole limit is `ENOMEM`; else eviction
  (KG7); a same-id image is replaced and its placements go. a=T then
  places it (a=p with i the new id), and its reply is the display's. An
  implicit id is never replied to. Else `i=ID[,I][,p];OK` (p echoed for
  a=t too).
- **a=q**: i=0 never answered. Otherwise a full load and check, the result
  dropped, storage and any load untouched: `i=…;OK` or the error.
  `a=q,i=31,s=1,v=1,f=24;AAAA` is `ESC_Gi=31;OK ESC\`.
- **a=p**: needs i or I (else never answered). I picks the newest image of
  that number; none: `ENOENT: image not found`. The reply's i is the
  image's real id. U=1 is virtual (`EINVAL: virtual placement cannot refer
  to a parent` with P>0); P>0 relative; else anchored at the cursor. X, Y
  clamped to the cell's size − 1 where it is known. p=0 is a new
  placement each time (an internal id from a counter at 0); p>0 replaces
  the image's placement p.
- **a=d**: abandons a load in progress; never replies (but the i+I error).
  Lowercase removes placements; uppercase also frees an image the
  selector touched that has none left. `a/A` placements on or reaching
  into the screen (not virtual, not relative); `i/I` image i, or its
  placement p; `n/N` the newest image numbered I; `c/C` those covering the
  cursor; `p/P` the cell at 1-based x, y (0 is nothing); `q/Q` and z
  too; `x/X` the 1-based column; `y/Y` the 1-based screen row; `z/Z` z
  (not virtual); `r/R` ids x to y (`R` frees unused ones in it, placed
  or not; y=0 or x>y nothing); `f/F` frames (`F` on a still image deletes
  it). Any other `d`: nothing. The geometric ones match nothing while the
  cell size is unknown.
- **Animation** (a=f, a=a, a=c) is in the library; the core has none yet.

## KG4 · Chunks

- Only a direct transmit with m>0 starts a load; one per screen. A middle
  chunk is never replied to. The first fixes f, s, v, o, i, I, p, N, a=T's
  display keys and q, and deletes image i, and errors there (an unknown
  f) are replied to at once. Later chunks give only their payload and m
  (any transmit-like command; a chunk with t≠d drops the load and starts
  afresh). A chunk's q: 0 keeps the first's, ≥1 replaces it. m=0 ends it,
  replied with the first's i, I, p.
- a=p and a=q leave a load alone; a=d and RIS drop it; a transmit with
  neither i nor I continues it. At most 400 MB gathered ("invalid data").

## KG5 · Pixels

In order: o=z inflated (400 MB at most; "decompression failed"); f=100
"unsupported format"; s=0 or v=0 "dimensions required"; s or v over
10000 "dimensions too large"; then the length **exactly** s·v·3 (f=24) or
s·v·4 (f=32), else "invalid data". Stored as they came, w·h·bytes a
pixel counted.

## KG6 · Geometry (from the cell size at the time)

- Cell size from the terminal's pixel size (0 until told). sx = min(x, W),
  sy = min(y, H); sw = min(w or W, W − sx), sh = min(h or H, H − sy).
- offX = min(X, cw − 1) if cw > 0 else 0; offY likewise.
- Pixel size: c = r = 0: (sw, sh). Both: (cw·c −| offX, ch·r −| offY).
  c only: width cw·c −| offX, height round(width·sh / sw). r only: the
  same the other way. Rounding is (a·b + d/2) / d.
- Cells: c>0 and r>0: (c, r); else ceil((pw + offX) / cw) and ceil((ph +
  offY) / ch); 0 when the cell size is.
- Anchor: the cursor (x = cols − 1 while a wrap is pending), fixed there.
  Covered: rows down from it (clamped at the end), columns to min(x + cols
  − 1, cols − 1).
- Cursor after (a pin placement, C≠1): tx = x + cols; wraps = tx ≥ the
  terminal's columns; n = (rows −| 1) + (wraps ? 1 : 0) times IND (which
  scrolls at the bottom margin, the anchor going up into the scrollback),
  at most (bottom margin − cursor row) + rows (0 + rows outside the
  region); no CR; the wrap cleared; then x = wraps ? 0 : tx. Unknown
  cell size and not both c and r: no move down, x unchanged.

## KG7 · Storage

- Total = Σ w·h·bytes. A new image over the limit evicts others: transient
  unused, unused, transient used, used; oldest generation first, then
  lowest id; their placements with them. The active screen only.
- **Each screen its own storage** and load; the alternate one made when
  first used and kept across switches; commands act on the active one.
- RIS: the alternate's gone, the primary's emptied (the implicit counter
  and any load too).
- ED 2 (and `?1049h`'s): placements on screen removed as d=A, then every
  image with no placement freed, never-placed ones too. `CSI 22 J` is the
  scroll-clear then that. ED 0 and 1: nothing. ED 3: placements anchored
  in the scrollback removed, images kept.
- A placement whose row leaves the scrollback stays listed until the next
  placement is added (C API) but is not shown.
- A scroll within margins (IND, LF at the bottom margin, SU, SD; not IL or
  DL): a placement wholly inside the region moves, is clipped at the
  margins (its source and rows shrink) or goes when nothing is left;
  others stay. A full-screen scroll moves them with their rows. Resize:
  they reflow with their rows. (The alternate screen's top row on a full
  scroll keeps its pin at row 0: read, not run.)

## KG8 · The C API for a dump

`ghostty_terminal_get(t, GHOSTTY_TERMINAL_DATA_KITTY_GRAPHICS, &g)`; a
placement iterator (`ghostty_kitty_graphics_placement_iterator_new`,
`ghostty_kitty_graphics_get(g, …_PLACEMENT_ITERATOR, &it)`, `…_next`,
`…_placement_get(it, key, out)` for image id, placement id, virtual,
offsets, source, columns, rows, z; `…_source_rect`, `…_grid_size`,
`…_pixel_size`, `…_viewport_pos`, `…_placement_rect`); images by id
(`ghostty_kitty_graphics_image(g, id)`, `…_image_get`: id, number, width,
height, format, data). No image iterator: images are found through the
placements or by the ids sent. Hash order: sort. p=0 placements show
their internal id. Removed-but-listed placements have no rect.

# Slice 03: vt image protocols and decoders

Files read whole: `vt/src/Vt/{Kitty,Jpeg,Png,Inflate,Gif,Sixel,Iterm,Tiff,Placed,Placeholder}.geng`,
plus `app/src/ImageFile.geng` and the callers in `Vt.geng`, `Vt/View.geng`, `Vt/Print.geng`
(for how results are used). Documents checked: `docs/images.md`, `images-kitty.md`,
`images-sixel.md`, `images-iterm.md`, `docs/review.md`. Ghostty's vendored source
(`vendor/ghostty/src/terminal/kitty/graphics_exec.zig`) was read for the reply rule.

Facts the findings lean on, all read from the tree:
- `Vt.Cell.byteAt` answers -1 past the end; `UInt8.fromInt` saturates (-1 becomes 0), so no
  decoder can crash on a short read.
- `Int` is 32 bits (`Vt.Kitty.u32`'s comment).
- The app's image limit is 320,000,000 bytes (`app/src/Main.geng:9146`); a tmux pane's is
  10,000,000 (`app/src/TmuxMode.geng:823`). One APC/DCS/OSC payload is at most 65 MiB
  (`Kitty.apcMax`).
- A `Builder UInt8`/`Builder Int` element costs about 8 bytes, by `docs/images.md` IM15's own
  measurement (an 8.3 MB RGBA PNG peaks at 79 MB).
- All decoding runs synchronously inside the parser (`sixelDispatch`, `itermDispatch`,
  `apcDispatch`), so a slow decode freezes the terminal.

---

### VI1 · TIFF: overlapping strips make a decompression bomb, and the decoder ignores the image limit
- Where: vt/src/Vt/Tiff.geng:66-72, 132-136, 153; vt/src/Vt/Iterm.geng:92-93
- Kind: security
- Severity: high
- Confidence: confirmed
- What: `entries` allows an entry `count` up to 100,000 (`clamp 0 100000 (u32 (at + 4))`).
  `strips = Array.map2 (\o c -> Bytes.slice o (o + c) data) (field 273 []) (field 279 [])` and
  `raw = Bytes.flatten strips` are built in the `let`, before any check of width, height or
  size, and nothing stops strips overlapping or their total passing the file's length.
  `Tiff.decode` takes no `most` argument at all (`Iterm.decoded` passes `r.limit` to the other
  three decoders only).
- Scenario: an iTerm2 `File=inline=1:` whose TIFF has StripOffsets and StripByteCounts pointing
  at one 400 KB array of 100,000 LONGs (the same array can serve as both), each strip slicing to
  the file's end: `Bytes.flatten` is asked for up to 100,000 times the file's length (tens of GB
  from a file under 1 MB; the payload may be 48 MB). The terminal dies of memory on `cat file`.
  Also, with `samples == 3` and 10,000 by 10,000, `rgba` runs `Array.range 0 (n - 1)` over 10^8
  pixels whatever the limit is; the limit is only looked at afterwards in `Iterm.sized`.
- Fix: pass the limit in; check width, height, `width * height * 4 <= most` first; then require
  the strips' byte counts to sum to no more than `width * height * samples` (and each strip to
  lie inside the file) before slicing or flattening anything.
- Fixed: 2026-11-21. `Tiff.decode` takes the limit and refuses a size over it first, and `stripped` reads the strips only up to `width * height * samples` bytes, so overlapping strips cannot make more. Test: `Iterm`'s "a TIFF's strips are read only up to its pixels" (99,999 overlapping strips), which ran out of memory before.

### VI2 · Sixel: a 30-byte string allocates gigabytes; the size is never held to the image limit
- Where: vt/src/Vt/Sixel.geng:100-119; vt/src/Vt/Kitty.geng:1159
- Kind: security
- Severity: high
- Confidence: confirmed
- What: `decode` clamps each side to 10,000 and then builds the canvas with
  `Builder.fromArray (Array.repeat (width * height) fill |> Array.flatten |> Array.map UInt8.fromInt)`:
  an array of `width*height` 4-element arrays, a flattened array of `4*width*height` Ints, a
  mapped copy of it, then the builder. `Sixel.decode` is given no limit; `addImage` refuses the
  image only after it is fully painted. `docs/images.md` IM4 says Sixel is "bounded before it
  allocates" and IM5 "each image's RGBA at most a cap ... checked before allocating. The Sixel
  decoder stops at the same bound": the code has only the 10,000-pixel sides.
- Scenario: `printf '\033Pq"1;1;10000;10000\033\\'` (raster attributes only, no data) gives
  width = height = 10,000, so four structures of 10^8 to 4x10^8 elements (well over 10 GB at
  8 bytes an element) are allocated for an image that is then refused at 320 MB. In a tmux pane
  (limit 10 MB) the same holds. An ordinary 1920 by 1080 Sixel pays the same four copies
  (about 200 MB of garbage) per image, which matters for Sixel animation.
- Fix: give `decode` the terminal's limit and refuse (or clip) when `width * height * 4` passes
  it, before the second pass; build the canvas with `Builder.repeat` of bytes (or a `Bytes`
  fill) rather than three intermediate arrays.
- Fixed: 2026-11-21. `Sixel.decode` takes the limit and refuses after the first pass, before the canvas; the canvas is one builder filled by doubling a copy of its first pixel. Test: `Sixel`'s "a Sixel string's size is held to the image limit", which ran out of memory before.

### VI3 · JPEG: nothing bounds the number of scans or a scan's components, so a small file hangs the terminal
- Where: vt/src/Vt/Jpeg.geng:173-207 (`markers`, SOS), 345-376 (`scanOf`), 478-483, 860-894 (`scanned`), 496-530
- Kind: security
- Severity: high
- Confidence: confirmed (the loop structure; the time per scan is an estimate from IT4's 807 ms for 12 MP)
- What: every SOS marker appends a `Scan`; `pixelsOf` then runs `scanned` (or `progressiveScan`)
  once per scan over every MCU of the frame (`Array.range 0 (units...)`), whether or not the
  scan has any entropy data (`bitAt` answers 0 past the end, so an empty scan still decodes and
  inverse-transforms every block). `scanOf` reads `n = byteAt body 0` components (up to 255,
  the standard allows 4) and lets the same component id repeat. A baseline file should have at
  most one scan per component.
- Scenario: a JPEG with SOF0 10000 by 8000 (allowed under the 320 MB limit), one DHT/DQT, then
  a few thousand 10 to 14-byte SOS segments with no data: each costs a full pass over 1.25
  million MCUs (seconds each), so a file of tens of KB, sent as `OSC 1337 File=inline=1`, blocks
  the parser for hours. A scan naming one component 255 times multiplies it again.
- Fix: refuse `n > 4` or a repeated component in `scanOf`; for baseline, refuse a second scan
  of a component already scanned; cap progressive scans (libjpeg-turbo warns past 100 or so);
  stop a scan when its segment's bits are exhausted rather than decoding zeros to the end; and
  consider a budget of blocks decoded per image.
- Fixed: 2026-11-21. `scanOf` refuses a scan of no components or more than four or than the frame has, and one naming a component twice or, in a sequential file, one scanned already; a progressive file has at most 100 scans (`maxScans`). Stopping a scan at the end of its bits, and a budget of blocks, are not done: these bound the passes to 100. Test: `Jpeg`'s "a scan's components are bounded", whose three refusals were decoded before.

### VI4 · Decoders peak at roughly ten times the pixel bytes, so the 320 MB limit admits multi-GB spikes from small inputs
- Where: vt/src/Vt/Inflate.geng:48,77 (`Builder UInt8` output to `most`); vt/src/Vt/Kitty.geng:520,528,551-553 (`maxSize` 400 MiB); vt/src/Vt/Png.geng:281,304,329; vt/src/Vt/Jpeg.geng:466,478-485,841,1299; vt/src/Vt/Gif.geng:176,213,243,324
- Kind: security
- Severity: medium
- Confidence: confirmed (structure); plausible (exact bytes: scaled from IM15's 79 MB for 8.3 MB of pixels)
- What: every decoder's limit is on the final RGBA bytes, but the working storage is builders
  and arrays of one word per byte or sample: Inflate's output builder (to 400 MiB of elements
  for `o=z`), PNG's inflated builder plus a per-pass unfilter builder plus the `w*h*4` output
  builder, JPEG's `Builder Int` of every plane (to 400,000,000 samples, twice for progressive:
  coefficients and `transformed`'s output) plus `Builder.toArray`, GIF's `Builder.repeat count`
  of indices, `byRow`, and the output. IM15 notes the cost for PNG ("the first thing to look at
  if it matters") but not that the bound a remote program can reach is the limit times it.
- Scenario: `a=t,o=z,f=32,s=10000,v=10000` with 400 KB of deflated zeros inflates to 400 MB of
  builder elements (about 3 GB) before `addImage` answers ENOMEM. A 300-byte baseline JPEG
  declaring 10000 by 8000 allocates 240 million plane samples and 320 million output elements.
  A 50-byte GIF declaring 10000 by 8000 allocates two 80-million-Int arrays and the output. On
  the shared server IM5 mentions this is an OOM kill of the terminal.
- Fix: decode into bytes, not word builders (a `Bytes` builder, or rows flushed to `Bytes` and
  flattened); make the per-decoder cap account for working storage (e.g. refuse when planes
  plus output exceed the limit); for `o=z` raw formats, cap inflation at `s*v*bpp` when `s`
  and `v` are given rather than at 400 MiB.
- Fixed: In part, 2026-11-23, `docs/images.md` IM37. Measured: decoders cost 2.4 to 5 times the pixels, not 10. A raw Kitty load is inflated only to its declared size; wrong dimensions and a size past the store are answered before inflating: a 389 KB load declaring 10000 by 10000 peaked at 941 MB, now 11 MB. Left for Gilbert: JPEG/GIF up to 320 MB of pixels peak at 1.4-1.6 GB (rewrite to bytes, or a working budget that refuses some).
- Fixed: The rest, 2026-11-25, `docs/images.md` IM39, by the rewrite Gilbert chose: the decoders keep samples, indices and coefficients a byte or two each and write each image once into `Bytes`. 10000 by 8000: JPEG 1.36 GB to 448 MB, progressive 1.88 GB to 751 MB, GIF 1.61 GB to 402 MB; PNG 8900 by 8900 2.61 GB to 799 MB; the same pixels for 288 images.

### VI5 · A Sixel or iTerm2 image drawn over an older one never frees it: animations pile up to the limit
- Where: vt/src/Vt/Kitty.geng:1199-1268 (`placeShown`)
- Kind: bug
- Severity: medium
- Confidence: confirmed (by reading; not run)
- What: `placeShown` adds an implicit image and a placement at the cursor and never looks at
  what its cells already hold. Only text (`overwritten`) or ED 2 removes a `textErases` image.
  IM23 says these images are "drawn into the cells, as xterm and Windows Terminal have it",
  where a new image replaces the pixels of the cells it covers.
- Scenario: a Sixel animation (`chafa anim.gif`, `timg` video, `mpv --vo=sixel`): each frame is
  CUP then a new Sixel over the same cells. Every earlier frame stays in the store with its
  placement at z -1, so `shownPlacements` hands the window all of them every frame (hundreds of
  full-size blends), memory climbs to 320 MB, and from then on every frame runs `evict`
  (next finding). With P2=1 (transparent) frames, old frames also show through wrongly.
- Fix: in `placeShown`, treat the new image's cell rectangle as overwritten for `textErases`
  images already there (the existing `holed`, which deletes an image once every row is lost),
  at least when the new image is opaque; for transparent ones, compositing or the same rule as
  Windows Terminal.
- Fixed: 2026-11-22. `placeShown` treats the cells an opaque new image covers as overwritten (`overwritten`, `holed`) before placing it; a transparent one leaves what is under it. Test: `Sixel`'s "an opaque image drawn over an older one takes its cells": five opaque frames left five images before, one after; five transparent ones five. `docs/images.md` IM23.

### VI6 · An image refused for memory is answered even when the program gave no id
- Where: vt/src/Vt/Kitty.geng:817-819 (`finishLoad`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: on `addImage`'s error the reply is `respond quiet { r | id = id, message = why }`, where
  `id` is the id just chosen: `store.implicit` (2147483647 upward) for a transmission with
  neither `i` nor `I`, or `lowestFree` for one with `I`. `respond` sends whenever `id /= 0`.
  `docs/images-kitty.md` KG3 says "none at all when both i and I are 0, errors too" and "An
  implicit id is never replied to"; Ghostty's `transmit` (graphics_exec.zig:197-220) keeps the
  command's own `image_id` in the error reply, so it sends nothing for an implicit id, and only
  `I=n` for a numbered one.
- Scenario: a program sends an image without an id that is larger than the limit: common in a
  `tmux -CC` pane, whose limit is 10 MB (a 2000 by 1500 RGBA picture is 12 MB). puritty writes
  `ESC _Gi=2147483647;ENOMEM: out of memory ESC \` to a program that asked for no replies, which
  lands on the shell's input as typed text. With `I=5`, the reply carries an `i=` Ghostty's does
  not.
- Fix: reply with `r` as it is (the command's own i and I) on the error path; add a corpus case
  for ENOMEM with no id and with `I`.
- Fixed: 2026-11-22. The refusal is answered with the command's own `i` and `I`. Test: `KittyFiles`' "an image refused for memory is answered with the command's own ids": before, `i=2147483647;ENOMEM` for no id and `i=1,I=5` for `I=5`. `docs/images-kitty.md` KG7.

### VI7 · Eviction sorts every image once per victim, with a scan of all placements inside the comparison
- Where: vt/src/Vt/Kitty.geng:887-928 (`evict`)
- Kind: speed
- Severity: medium
- Confidence: confirmed (complexity); plausible (time)
- What: each step of `evict` does `Dict.values store.images |> Array.sortWith order |> Array.first`
  and recurses; `order` calls `rank` on both sides, and `rank` calls `used`, an
  `Array.any` over `store.placements`. One victim costs O(I log I x P); freeing k victims costs
  k times that.
- Scenario: once the store is full (which the previous finding makes the steady state for any
  Sixel animation, and which thumbnails from `lsix`/`yazi` reach too), every new image pays it
  inside the parser. With 8,000 small images (40 KB each fills 320 MB) and as many placements:
  about 8000 x 13 x 2 x 8000, over 10^9 closure calls per victim, seconds per frame.
- Fix: compute the set of used image ids once, find the minimum in one pass (no sort), and
  evict in a loop over one ordering computed once.
- Fixed: 2026-11-22. `evict` finds the placed images once and orders the images once (a victim takes its own placements only, so no rank moves), then evicts in that order (`evictIn`). Natively, 1,000 placed images and 100 evicted: 138 ms before, 32 ms after, loading included. Test: `KittyFiles`' "eviction takes the unplaced images first", which holds KG7's order on both.

### VI8 · Placements whose rows have left the scrollback are never removed
- Where: vt/src/Vt/Kitty.geng:1059, 1268 (added), 1649-1671 (`overwritten`), 1979-2025 (`shownPlacements`); vt/src/Vt/Placed.geng:171-194
- Kind: efficiency
- Severity: medium
- Confidence: confirmed (no pruning exists); plausible (how large it gets in practice)
- What: placements only leave `store.placements` by a delete command, ED 2/ED 3, a margin
  scroll, `holed`, or their image's eviction. KG7 records that Ghostty keeps such a placement
  "until the next placement is added"; puritty has no such step, so they stay. A Kitty program
  can also add placements without bound (`a=p` with p=0 is "a new placement each time"), each a
  few dozen bytes, far under any byte limit.
- Scenario: each stale placement keeps its image ranked "used" in `evict` (so live unplaced
  images go first), and makes every O(placements) walk longer: `overwritten` runs
  `Array.foldl (holedIf ...)` over all of them for every character printed while any erasable
  image is on screen (IM27's "20 times slower" grows with the count), `shownPlacements` sorts
  and takes `rect` of all of them every frame, `anyOnScreen`, `scrollPlan` and `altScrolled`
  walk them per scroll. A program looping `a=p` a million times makes every later operation
  linear in a million.
- Fix: drop placements with `row < geo.gone` (and nothing reaching below it) when a placement is
  added, as Ghostty does, and free transient implicit images left with none; cap the
  placements per screen.
- Fixed: 2026-11-22. `prunedGone`, where a placement is added: placements whose every row is below the rows gone are dropped, and an implicit, transient image left with none freed. Test: `KittyFiles`' "a placement whose rows have left the scrollback is dropped": two placements before, one after. The cap per screen is not done.

### VI9 · `imageByKey` is linear, builds a string per image, and re-masks the pixels on every call; View calls it per sent image per frame
- Where: vt/src/Vt/Kitty.geng:1960-1968 (`imageByKey`), 1763-1855 (`masked`); callers vt/src/Vt/View.geng:797, 828; vt/src/Vt.geng:488
- Kind: speed
- Severity: medium
- Confidence: confirmed (code path); plausible (that `imageRecords` runs every frame, View.geng:591)
- What: `imageByKey` does `Dict.values ... |> Array.findFirst (\im -> keyOf 0 im == wanted)`
  (three string concatenations per image examined) and then always
  `Maybe.map (\found -> masked ...)`. `masked`, for an image with holes, rebuilds the whole
  pixel buffer (`Array.range 0 (h - 1)`, several slices a row, `Bytes.flatten`).
  `View.imageRecords` computes `gone` with `Kitty.imageByKey key t == Nothing` for every key in
  `sent`, so the masked copy is built only to be compared with `Nothing`.
- Scenario: while a Sixel image that text has partly overwritten is on a window, every frame
  re-masks all of it (8 MB for 1920 by 1080) per such image, and with N images known the lookups
  are N x N string builds per frame.
- Fix: split it: an existence test by key that parses the key back to (id, generation,
  erasures) and uses `Dict.get`, and the masked pixels only where they are sent
  (View.geng:797); cache the masked bytes on the image per `erasures`.
- Fixed: In part, 2026-11-22. `View.imageRecords` asks `Kitty.hasKey`, which finds the image without masking its pixels, where it built the masked copy of every image held to compare it with `Nothing`. Natively, 100 frames of a 200 by 50 window with a 1000 by 900 Sixel image partly written over: 59 ms before, 22 ms after. The lookup is still linear with a key built per image, and the masked bytes are not cached; with a few images held that is small.

### VI10 · Sixel painting allocates about eight arrays per data byte, and a repeat is an unbudgeted fill
- Where: vt/src/Vt/Sixel.geng:390-420 (`paint`), 143-241 (`run`)
- Kind: speed
- Severity: medium
- Confidence: confirmed (allocations); plausible (time)
- What: for each data byte `paint` builds `rgbaOf ... |> Array.map UInt8.fromInt` (two arrays),
  `rows` through `Array.range`, `keepIf`, `mapAndFlatten` (with a nested `range`/`map` per bit)
  and `keepIf` again, and `columns = Array.range p.x ...`, then one `Builder.setMany` per pixel.
  `run` is walked twice over the data, calling `finish` and rebuilding the 12-field `Pass`
  record per byte. The colour's RGBA and the row list depend only on the colour and aspect.
- Scenario: Sixel is what chafa and timg choose in puritty by default (SX3); a full-screen
  picture is a million or more data bytes, so roughly ten million small allocations per image,
  per frame of an animation. Separately, `!10000~$` (9 bytes) paints up to 600,000 pixels (aspect
  10), so a 1 MB string of them is 6x10^10 `setMany` calls: the terminal is frozen for many
  minutes, with no budget on pixels painted.
- Fix: keep the current colour's four bytes in the pass (set when `#` selects), loop over bits
  and columns with counters instead of arrays, write a repeat as a row fill; hold the painted
  pixel count to a multiple of the canvas (stop painting when it is passed).
- Fixed: 2026-11-22. `paint` loops over the bits and rows with counters and writes a row's run as its first pixel copied by doubling (`paintRun`, `doubledAt`), and the canvas carries a budget of sixteen writes per pixel, after which nothing more is painted. Natively, 10,000 repeats of `!10000~$` (90 KB): 5,632 ms before, 6 ms after, the same image. Test: `Sixel`'s "a Sixel string's painting is held to sixteen times its canvas"; the other Sixel tests hold the pixels. `run`'s `Pass` record a byte is not changed. `docs/images-sixel.md` SX2 7.

### VI11 · With `read_files` on under Windows, a remote program can make puritty open a UNC path
- Where: app/src/ImageFile.geng:38-50, 122-126 (`sensitive`); vt/src/Vt/Kitty.geng:662-700
- Kind: security
- Severity: medium
- Confidence: plausible (Windows path handling of `Path.isAbsolute`/`File.realPath` not checked)
- What: the core accepts any UTF-8 path with no control character; the app requires only an
  absolute path and refuses `/proc/`, `/sys/`, `/dev/` (its comment: "Kitty's blocked folders
  (Linux's)"). There is no Windows rule. KG9 accepts that a program reached by `ssh` in a local
  tab can name local files once the setting is on.
- Scenario: on Windows with `[images] read_files = true`, a program on a remote host (plain
  `ssh.exe` in a local tab) sends `a=q,t=f,i=1;<base64 of \\attacker\share\x.png>`. Opening it
  makes Windows authenticate to the attacker's SMB server (NTLM hash disclosure), and
  `\\?\`/`\\.\` device paths are reachable the same way. The `a=q` reply (ENOENT, EPERM, EINVAL,
  OK) is also an oracle for whether any local path exists, on both platforms.
- Fix: on Windows refuse paths that are not `X:\...` on a local fixed drive (no `\\`), before
  `realPath`; say in KG9 and the setting's text that replies reveal which files exist.
- Fixed: In part, 2026-11-22. `ImageFile.read` refuses a path beginning with two separators (`Links.shared`: `\\host\share`, `//host`, `\\?\`, `\\.\`) before `realPath` opens it, on every platform. Not done: a Windows path that is not on a local fixed drive by other means (a mapped network drive letter), and the setting's text saying the replies reveal which files exist (KG9 says it now). Test: "a picture's file named by a share or a device path is refused".
- Fixed: 2026-11-24, the rest: `docs/images.md` IM38. On Windows a path must begin with a drive letter of a local drive (`GetDriveTypeW`, win32 `Drives.isLocal`, `Platform.localDrive`) before it is opened; a resolved path to a share is refused; the setting's text says the answers reveal which files exist. Test: the app's `drives` suite on Linux and Windows. A mapped network drive was not tried.

### VI12 · JPEG: green is one too high on every YCbCr pixel
- Where: vt/src/Vt/Jpeg.geng:1289
- Kind: bug
- Severity: low
- Confidence: confirmed (by arithmetic; not run)
- What: `g = c0 - Bitwise.shiftRightBy 16 (22554 * cb + 46802 * cr - 32768)`. libjpeg computes
  `y + ((-22554*cb - 46802*cr + 32768) >> 16)`, a floor; negating a floored value makes this a
  ceiling, which is one more whenever the quotient is not whole. With `cb = cr = 0` it is
  `c0 - (-32768 >> 16) = c0 + 1`. The comment says "libjpeg's constants".
- Scenario: any neutral pixel of a colour JPEG comes out (v, v+1, v): black is (0,1,0). The
  tests hold colour files to within 3 of libjpeg (IT4: "by at most 2 ... which is the integer
  transform's against this one's"), which hid it; part of that 2 is this.
- Fix: `c0 + Bitwise.shiftRightBy 16 (32768 - 22554 * cb - 46802 * cr)`; then tighten the
  tolerance for the 4:4:4 case.

### VI13 · TIFF to RGBA allocates an array per pixel and a range of every pixel index
- Where: vt/src/Vt/Tiff.geng:161-195 (`rgba`)
- Kind: speed
- Severity: low
- Confidence: confirmed
- What: for 3 samples or grey, `Array.foldl ... (Array.range 0 (n - 1))` materialises n Ints, and
  each pixel builds a 4-element array `px` and folds over it with a closure.
- Scenario: TIFF is chafa's form of iTerm2 images (IT3), sent per frame for animations: a
  1920 by 1080 frame is 2 million small arrays plus a 2-million-element range. The JPEG decoder
  had exactly this fixed (IT4: "`Array.range` in the inner loops", 2.6 times faster without).
- Fix: a counted loop pushing the four bytes directly, as `Jpeg.pixels` does.

### VI14 · iTerm2: the limit is tested against the drawn size even when no pixels of that size are made
- Where: vt/src/Vt/Iterm.geng:234-242
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `if tw == 0 || th == 0 || tw * th > r.limit // 4 then Nothing` comes before the
  whole-cells branch, which keeps the original `nw` by `nh` pixels and lets the placement scale
  them.
- Scenario: in a tmux pane (limit 10 MB, so 2.5 million pixels) `imgcat --width 100% --height
  100%` of a small picture on a pane of 1700 by 1500 pixels or more shows nothing, though the
  image stored would be a few KB.
- Fix: apply the `tw * th` test only on the `resample` branch.

### VI15 · iTerm2 decode failures are dropped to `Nothing`
- Where: vt/src/Vt/Iterm.geng:65-72; vt/src/Vt/Kitty.geng:1410-1424
- Kind: design
- Severity: low
- Confidence: confirmed
- What: each decoder returns a reason ("progressive ... not decoded", "too large", "compressed",
  "dimensions"), and `file` maps `Err _` to `Nothing`; `itermShow` then does nothing. Nothing
  reaches the diagnostic log or a notice, unlike KG9's file reads ("Each read or refusal is a
  line in the diagnostic log").
- Scenario: `imgcat photo.tif` (LZW-compressed, the usual TIFF) or a CMYK JPEG draws nothing and
  the user has no way to learn why; IT3 records one such silent failure costing a debugging
  session ("The first run of timg drew nothing").
- Fix: return `Result String Shown` (with "a download" as one reason) and have the caller raise
  it through the core's notice/diagnostic channel.

### VI16 · Inflate accepts incomplete code sets that puff.c and zlib refuse
- Where: vt/src/Vt/Inflate.geng:202-243 (`huffman`), 464, 479-484
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed (puff.c from memory: `construct` nonzero for the code-length code is an error; for literal/length and distance, incomplete is allowed only for a single code of length 1)
- What: `huffman` answers `Nothing` only when over-subscribed (`left < 0`); an incomplete set
  (`left > 0`) is used as it is. The module says "After zlib's own reference decoder, puff.c".
- Scenario: a stream with an incomplete dynamic code decodes here, so `a=q`/`a=t` with `o=z`
  answers OK where Ghostty (zlib) answers `EINVAL: decompression failed`: a divergence the
  oracle would report, and a lenient path for malformed data.
- Fix: carry `left` out of `huffman`; require 0 for the code-length code, and for the other two
  allow `left > 0` only when the set is one code of length 1.

### VI17 · PNG: a palette index past PLTE, a repeated IHDR, and PLTE/tRNS of bad length are accepted
- Where: vt/src/Vt/Png.geng:556-569 (palette lookup), 117-132 (chunks)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed (what the code does); plausible (that wuffs refuses each)
- What: `byteAt c.palette (3 * i)` past the palette is -1, which `UInt8.fromInt` makes 0: opaque
  black, no error. A second IHDR replaces the first (only "IHDR first" is tested). PLTE's
  length is not held to a multiple of 3 or to 256 entries, and PLTE is not required before
  IDAT.
- Scenario: such a file is answered `OK` and drawn where Ghostty answers `EINVAL: invalid
  data`; `kitty-png-errors` has none of these cases.
- Fix: check PLTE's length at the chunk, refuse a second IHDR, and make an index past the
  palette an error (or decide the leniency and write it in IM15).

### VI18 · PNG: CRC-32 is worked a bit at a time, for every chunk, including those whose CRC is not checked
- Where: vt/src/Vt/Png.geng:104-105, 579-605; 453-459 (`placeAt`)
- Kind: speed
- Severity: low
- Confidence: confirmed
- What: `crcOk` is computed in the `let` for every chunk, then used only `if critical`;
  `crcByte` is eight steps a byte with no table. `placeAt` builds an `Array Int` and an
  `Array UInt8` for every pixel. IM15 measured 0.19 s for 1920 by 1080 and calls it "slow for
  flicking through previews".
- Scenario: per PNG, eight shift/xor steps for every file byte plus two arrays a pixel: a share
  of the 0.19 s that is cheap to remove.
- Fix: a 256-entry table (a top-level array), computed only for critical chunks; push the four
  channel bytes without the intermediate arrays for the non-interlaced case.

### VI19 · JPEG `markers` recurses through `Result.andThen` for SOF, so it is not a loop there
- Where: vt/src/Vt/Jpeg.geng:142-147
- Kind: bug
- Severity: low
- Confidence: plausible (depends on the native frame size against the 1 GiB stack)
- What: `frameOf body |> Result.andThen (\f -> markers data after ...)` calls `markers` from
  inside a closure, so each SOF marker met adds stack frames, where every other branch is a
  tail call.
- Scenario: a 48 MB payload of 13-byte SOF0 segments is 3.7 million nested calls; if a nesting
  costs more than about 290 bytes of stack the terminal dies at the stack limit. A second SOF
  is also simply accepted, replacing the frame the earlier scans were read for.
- Fix: `when frameOf body is` with direct tail calls, and refuse a second SOF.

### VI20 · No malformed-input tests for the JPEG, GIF, TIFF and Sixel decoders
- Where: vt/tests/src/Jpeg.geng, Gif.geng, Iterm.geng, Sixel.geng
- Kind: test-gap
- Severity: medium
- Confidence: confirmed
- What: the JPEG and GIF tests are Pillow-made valid files (plus one SOF3); TIFF has valid cases
  in `Iterm.geng`; Sixel's are well-formed. PNG and zlib have `kitty-png-errors` and
  `kitty-zlib`. Nothing feeds truncated, oversized or adversarial files to the other four,
  though they exist to take "data a remote program sends" (IM4), and nothing holds a decode's
  time or memory.
- Scenario: the three high findings above (TIFF strips, Sixel raster size, JPEG scans) would
  each be caught by one small case with a time and memory cap.
- Fix: add cases for: a header-only file at the largest size the limit allows, per format;
  TIFF with overlapping strips; JPEG with repeated SOS/SOF and a 255-component scan; Sixel raster
  10000 by 10000 and long repeats; GIF with codes past the table; and the ENOMEM reply with no
  id. A small mutation fuzzer over the Pillow-made files with a per-case budget would cover the
  rest.

## Looked at and found sound

- **Inflate**: stored, fixed and dynamic blocks; LEN/NLEN; the code-length alphabet order;
  16/17/18 repeats (repeat with nothing before, and overrun past HLIT+HDIST, refused); HLIT > 286
  and HDIST > 30 refused; length codes 286/287 and distance codes 30/31 refused; distance past
  the output refused; missing end-of-block code refused; over-subscribed sets refused; output
  held to `most` at every push; zlib CMF/FLG check, FDICT refused, Adler-32 compared; short
  reads at every point end in `Err` (traced with `byteAt` = -1).
- **PNG**: signature; chunk length against the data; critical-chunk CRC; IHDR's legal
  depth/colour pairs, compression, filter and interlace bytes; 10,000 cap from the header; the
  five filters (bpp for sub-byte depths is 1, average uses floor, Paeth's tie order); first-row
  and first-pixel predictors; Adam7 pass geometry and empty passes; 1/2/4-bit sample
  extraction and grey scaling; 16-bit by high byte; tRNS for grey, RGB (compared at full 16
  bits) and palette; size checks before inflating; inflated length checked against the rows
  needed.
- **JPEG**: marker walk and segment bounds; DHT/DQT (8 and 16 bit) parsing; byte unstuffing,
  fill bytes and RST cutting in `entropy`; baseline DC prediction and AC run/size decoding
  incl. ZRL and runs past 63; EXTEND; MCU geometry for interleaved and single-component scans
  (incl. a one-component frame with factors above 1); restart intervals; the float IDCT's
  indexing and cosine table; DC-only shortcut; h2v1 and h2v2 fancy upsampling weights and
  rounding against libjpeg; R and B conversion constants; Adobe transform 0; Exif orientation
  parsing in both byte orders and all eight turns; progressive DC first/refine, AC first with
  EOB runs, AC refine with correction bits and ZRL, against stb_image's procedures. No division
  by zero and no out-of-range write found (all through `Maybe`/proven indexes).
- **GIF**: header, global/local table sizes, extension skipping, GCE transparent index; LZW
  code-width growth, clear code, end code, table full at 4096 (deferred clear), the KwKwK case,
  codes past the table (lenient, bounded), output bounded by `count`; interlace row order;
  frame offset on the logical screen. First frame only is by design (IT4).
- **Sixel**: parameters, repeat 0/none = 1, `$`, `-`, raster attributes, colour registers
  (define and select, modulo 1024), HLS with DEC's hue origin, RGB percent rounding, P2
  transparency, clipping at the canvas.
- **Kitty**: the control-data parser (key/value states, 11-byte cap, Zig integer rules, u32 ids
  kept as bits); validation of `a`, `t`, `o`, `d`; quiet levels; i/I mutual exclusion; chunking
  (first chunk fixes the keys, later chunks' q, 400 MB cap, non-direct medium drops the load);
  id choice; same-id replacement; `a=p` with p replacing, virtual and parent errors, cursor
  movement and `C=1`; every delete selector against KG3; ED 2/ED 3 handling; replies carry only
  numbers and fixed messages (no program-shaped text is echoed); a limit of 0 turns all three
  protocols off; shared memory always refused; file paths limited to 4,096 bytes of UTF-8
  without controls, and off unless the embedder allows it; `ImageFile`'s realpath, /proc /sys
  /dev refusal, regular-file and size checks, and the temp-file deletion rule (temp folder and
  `tty-graphics-protocol` in the name) on Linux.
- **Placed / Placeholder**: source rectangle, pixel and grid sizes, `rect`, margin-scroll
  clipping arithmetic (no overflow: all operands clamped), alternate-screen scroll;
  placeholder cell decoding, run cutting, the high byte, `fit`'s axes (no zero divisors once
  the cell and image sizes are positive).
- `Array.pushLast` accumulation of chunks/pieces (Kitty loads, JPEG `entropy`, GIF sub-blocks)
  is amortised O(1) natively per geng-lang `docs/core.md`, and IT4's timings bear it out: not
  reported.

## Not covered

- Nothing was built or run: every scenario is from reading. Times and byte counts are estimates
  from the documents' own measurements.
- `Vt.Base64`, the APC/DCS/OSC accumulation in `Vt.Parse` (incl. the unbounded `held` reads
  while a file is awaited), `Vt.View`'s wire records and `Vt.geng`'s canvas composition were
  read only where they call into this slice.
- `Placed.scrollPlan`/`clipTop`/`clipBottom` and `Placeholder.fit` were checked for arithmetic
  safety, not line by line against Ghostty's `scrollMarginsBegin` and `renderPlacement`.
- `Int` overflow at the far edges (e.g. `Inflate.zlib`'s `n * 8` for compressed input over
  256 MiB, reachable only by `t=f` or a 400 MB chunked load) fails as "decompression failed"
  rather than crashing; not listed as a finding.
- Windows behaviour of `ImageFile` (path forms, temp folders) was not traced into the Os
  package.
- Fixed: 2026-11-22. With VI1, VI2, VI3 and VI10's tests (TIFF's overlapping strips, a Sixel's size and repeats, JPEG's scans), `Iterm`'s "truncated and broken files of each format are taken without a crash" feeds JPEG, GIF and TIFF fixtures cut at a quarter, a half and three quarters, and each format's first bytes followed by 6 KB of zeros or ones, and holds that the terminal goes on. Not done: a cap on a decode's time or memory as such.

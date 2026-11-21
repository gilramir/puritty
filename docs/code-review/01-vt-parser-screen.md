# Slice 01: vt parser and screen operations

Files: `vt/src/Vt.geng`, `vt/src/Vt/{Parse,Dispatch,Osc,Dcs,Sgr,Modes,Term,Print,Edit,Scroll,Cursor,Screen,Cell,Style,Palette,Reason}.geng`.
Read-only review: nothing was built or run, so every cost figure below is an estimate from the code, and every scenario was traced by reading.

### VP1 · SD, IL and DL loop the raw count (up to 65,535) instead of the region's height
- Where: `vt/src/Vt/Dispatch.geng:540` (SD), `:560` (IL), `:579` (DL); the loops are `regionDown` (`vt/src/Vt/Scroll.geng:500-513`) and `scrollUpBy` (`vt/src/Vt/Scroll.geng:477-497`)
- Kind: security
- Severity: high
- Confidence: confirmed
- What: SU clamps (`regionUp (min (count0 params) (bottom - top + 1))`, `Dispatch.geng:865`), and the margined paths clamp (`marginUp`/`marginDown`: `min (max 1 count) (bottom - top + 1)`). The unmargined SD, IL and DL do not: `regionDown (param 0 1 params) t.top t.bottom t`, `regionDown (param 0 1 params) t.y t.bottom ...`, `scrollUpBy False (count0 params) t.y t.bottom ...`. In SD the clamped `count` is computed (`Dispatch.geng:530`) but only handed to `imagesMoved`. Each iteration of `regionDown` is a `settle`, a `turnRegion`/`shiftDown` (`Builder.copyWithin` over the whole region) and a `clearRow`; each of `scrollUpBy` is a `screenUp` (a region copy in most layouts).
- Scenario: `ESC [ 65535 T` (9 bytes) on an 80x24 screen does 65,535 copies of about 15 KB, roughly 1 GB of memmove; on 200x50 about 5 GB; on the 1000x1000 maximum about 500 GB. A program writing that sequence repeatedly (`yes $'\e[65535T'`) hangs the terminal for minutes per read. `ESC [ 65535 L` and `ESC [ 65535 M` are the same. The result after `height` iterations is already a blank region, so all further iterations are wasted.
- Fix: clamp the count to the region's height (`bottom - top + 1`, or `bottom - y + 1` for IL/DL) before the loop, as SU and the margined paths already do. A corpus case with a count of 65,535 for each of SD, IL, DL would hold it.

### VP2 · Searching or reading one scrollback row decodes its whole page (1,024 rows), and walks the pages from the oldest
- Where: `vt/src/Vt.geng:1325-1354` (`viewPages`), reached from `rowsBetween` (`Vt.geng:744-767`); `pageRowsOf` at `vt/src/Vt/Pages.geng:533`; callers that read one row at a time: `app/src/Search.geng:56` and `:145` (`Vt.selectionText` per row), `Vt.linkAt` (`Vt.geng:2135-2160`)
- Kind: speed
- Severity: high
- Confidence: confirmed (the code path); the timing is an estimate
- What: `viewPages` steps over pages from `b.head` until it reaches the one holding row `at`, then calls `pageRowsOf page clusters`, which unpacks every row of the page and rebuilds every cell with `Array.pushLast`, and only then `Array.slice`s the rows wanted. `Search.findFrom` walks the scrollback a row at a time, each row through `Vt.selectionText {row,0} {row,cols-1}`, so each row costs one full page decode plus a walk over all older pages.
- Scenario: a search with no match in a 100,000-row scrollback decodes 100,000 pages of 1,024 rows (about 10^8 row decodes) and does 100,000 walks over about 100 page slots. That is tens of seconds with the update loop blocked. `linkAt` on a pointer move over a scrolled-back view pays one page decode per call.
- Fix: read a page once per page, not once per row: give `Search` a page-at-a-time (or range) reader, or have `viewPages` decode only rows `at - start .. at - start + want` of the page (the row headers in `page.heads` already give each row's place), and let the caller pass the slot it found last time instead of starting from `head`.

### VP3 · ED 3 lowers `rowsPushed`, so absolute rows (image anchors, selection points) no longer name their rows
- Where: `vt/src/Vt/Edit.geng:709-724` (`clearScrollback`); `vt/src/Vt.geng:174-176` (`rowsPushed`), `vt/src/Vt/Scroll.geng:203-205` (`pushedRows`); consumer `vt/src/Vt/Kitty.geng:1894-1903` (`clearedHistory`); order of calls at `Edit.geng:538` (`imagesErased how (erasePlain selective how t)`)
- Kind: bug
- Severity: medium
- Confidence: confirmed by reading (not run)
- What: `rowsPushed` is "the rows that have entered the main screen's scrollback since the term was made: those it holds and those dropped", i.e. `hist + back.rows + back.gone`, and every absolute row (a `Point`, a placement's `row`) is `rowsPushed + screen row`. `clearScrollback` sets `hist = 0`, `rows = 0` and leaves `gone` as it was (`{ b | pages = Builder.empty 0, head = 0, bytes = 0, rows = 0 }`), so the count falls by the rows cleared. `dropOver` does add the rows it drops to `gone` (`Pages.geng:434`); ED 3 is the one drop that does not.
- Scenario: (1) A Kitty image has scrolled into the scrollback (anchor row R, `gone <= R < pushed`). `ESC [ 3 J`: `erasePlain` clears the scrollback first, then `clearedHistory` reads `top = pushed t`, which is now `gone`, and keeps every placement with `row >= top`, so the scrollback placement is kept, and is now taken to be `R - gone` rows below the screen's top: it shows on the screen, or scrolls into view later. (2) A placement on the screen at row y (anchor `pushed + y`) is, after ED 3, `y + cleared` rows down: it disappears and comes back when that many rows have been pushed. (3) Any `Point` the app holds across an ED 3 (selection, search marks) names a different row once output scrolls again. `Vt.setScrollbackBytes 0` goes through the same function.
- Fix: in `clearScrollback`, add the rows cleared (`hist + rows`) to `back.gone` (with `addRows`, as `dropOver` does), so `rowsPushed` never goes down; `clearedHistory`'s test is then right as written.

### VP4 · With Sixel/iTerm2 images on, every `:` or `=` in an OSC rebuilds the kept string; a DCS has the same shape per `q` and per C1 byte
- Where: `vt/src/Vt/Parse.geng:658` and `:682-702` (`keptText`, `itermLong`); `Parse.geng:840` with `vt/src/Vt/Dcs.geng:52-76` (`dcsHeader`); `Parse.geng:843` with `:860-874` (`sixelHeader`)
- Kind: security
- Severity: medium
- Confidence: confirmed (the code); cost estimated
- What: `oscString` tests `(b == 0x3A || b == 0x3D) && t.embedder.extraImages && itermLong b t` for each such byte, and `itermLong` calls `keptText t.str`: `Array.range 0 (len - 1) |> Array.mapAndKeepJust ... |> Bytes.fromUInt8s |> Bytes.toStringLossy`, three allocations the size of the string, then a `startsWith`. The string is capped at `stringMax` (4,096), but the test goes on for every later `:`/`=` although the byte is no longer kept. `dcsString` likewise rescans the kept string from 0 for every byte 0x80-0x9F (`dcsHeader t.str 0 0`, which skips high bytes and answers only at the end) and for every `q` (`sixelHeader t.str 0`).
- Scenario: `ESC ]` + 4,096 bytes of `a` + an unending run of `:`. Each colon costs a 4,096-element range, a filtered copy, a `Bytes` and a `String`: several tens of microseconds, so a 64 KB read is on the order of a second or more, and the OSC need never end. The DCS forms (4,096 bytes of 0xA0 then a run of 0x80; or 4,095 digits, `x`, then a run of `q`) cost 4,096 loop steps a byte. Ordinary cost too: every OSC 8 hyperlink (`8;;https://...?a=b`) pays one rebuild per `:` and `=` in its URI.
- Fix: decide on lengths and bytes without building a string: `1337;FilePart` is exactly 13 kept bytes and `1337;File=` a 10-byte prefix, so test `Builder.length t.str` and the bytes directly (as `isFiftyTwo` does), and only while the string is below `stringMax`. For DCS keep the header's phase in the parser state (it is already computed byte by byte in `dcsClean`) instead of rescanning.

### VP5 · The hyperlink table never forgets a link: after 4,096 distinct links OSC 8 stops working for the session
- Where: `vt/src/Vt/Osc.geng:639-685` (`hyperlink`); `vt/src/Vt/Style.geng:80-122` (`intern`); `vt/src/Vt/Sgr.geng:54-56`; decided in `docs/claude-code.md` CL9 ("past the 4,096th a new one ends the link instead ... RIS forgets them")
- Kind: design
- Severity: medium
- Confidence: confirmed
- What: `t.links` only grows; an entry stays after every cell that named it has scrolled out of the scrollback. At 4,096 entries a new URI gives `link = 0`. Lookup is `Array.findFirst (\l -> l.uri == uri && l.id == id) t.links`, linear with string compares, for each OSC 8 that opens a link. A linked pen also bypasses the style cache (`attrs.link /= 0` goes to `withPenInterned`), and `intern` then scans every style id that shares the key (`Array.findFirst` over `same`), which for links in the default style is one id per link seen.
- Scenario: `ls --hyperlink=auto` (a common alias) gives every file its own `file://` URI. One `ls -R` of a source tree, or a day's use, passes 4,096; from then on no new link is clickable until RIS, with nothing shown to say why. Before that point each link's open costs a scan of up to 4,096 URIs that share a long prefix, and each SGR inside a link a scan of up to 4,096 style ids. Each distinct (style, link) pair also takes one of the 32,760 style ids for good.
- Fix: the decision CL9 bounds memory but not usefulness. Either drop links no style still refers to when the table fills (the styles table is the reference count's natural home, see the next finding), or make the table a ring whose oldest entry is reused. Independently, find a link through a `Dict` keyed by URI and id instead of a linear scan.

### VP6 · Style and cluster ids are never given back; the tmux canvas is one long-lived terminal that takes the union of every pane's
- Where: `vt/src/Vt/Style.geng:113-114` (`id >= styleMax` gives style 0), `:187-188` (`clusterIdMax`); `vt/src/Vt/Print.geng:450` (`internCluster` per mark); `vt/src/Vt.geng:577-631` (`composeCell`), canvas kept across frames at `app/src/TmuxMode.geng:5049-5098`; registered as open in `docs/vt-core.md:490-494`
- Kind: design
- Severity: medium
- Confidence: confirmed (known open item; the canvas and the hostile case are the new part)
- What: the open item says "bounds memory but draws wrong ... to be decided with the renderer". Two things make it more pressing than that reads. (1) `composeStyled` interns every pane cell's style and cluster into `s.canvas`, which is the same `Term` for the whole tmux session (ED 2 does not clear the tables), and `Vt.invert` adds an inverse twin of each selected style. The canvas therefore reaches 32,760 styles before any pane does, and from then on new colors in every pane draw in the default style. (2) Clusters are bounded only at 2^21 ids, each an `Array Int` of up to 65 code points, plus a `Dict String Int` whose keys are the code points as decimal text. `joinMark` interns one new cluster per mark, so a base with 64 marks leaves 64 entries.
- Scenario: (1) a truecolor program (an image shown with half blocks is about 10,000 styles a screen) in a `tmux -CC` pane: after a few screens the canvas is full and colors are wrong in all panes until the tmux session is restarted. (2) `cat` of a file of random combining sequences grows the cluster table and its string-keyed dict toward 2 million entries: several hundred MB to over a GB that only RIS frees (`restarted` keeps them).
- Fix: for the canvas, start each compose from empty tables (they are rebuilt from the panes each frame anyway) or map ids through a per-compose cache and drop the rest. For the terminals proper the open item stands: count references per page as Ghostty does, or rebuild the tables from the live rows when they fill. A much lower cap on clusters (or on the dict's bytes) would bound the hostile case meanwhile.

### VP7 · RIS in the same read drops clipboard requests, notifications and diagnostic lines not yet taken
- Where: `vt/src/Vt/Modes.geng:678-696` (`reset`); takers at `vt/src/Vt.geng:1566`, `:1596`, `:2124`
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `reset` builds `fresh t.config` and carries over `replies`, the dynamic colors, `named`, `embedder`, the scrollback's `peak`/`dropped` and the image limit. `osc52.requests`, `notices`, `heard`, `kittyNotices` and `status` are the embedder's outputs in the same way `replies` is (they wait for `takeClipboard`, `takeNotices`, `takeHeard`), but are not carried, so they are lost if RIS is parsed before the embedder takes them, which is always the case when both are in one `feed`.
- Scenario: `printf '\e]52;c;%s\a' "$(base64 <<<text)"; reset`, or any script that copies or notifies (OSC 9/777/99) and then resets: the pty read holds both, `oscDispatch` queues the request, `ESC c` replaces the term, and the clipboard is never written / the notification never shown. With the diagnostic log listening, everything heard before the `ESC c` in that read is missing from the log.
- Fix: carry `osc52.requests`, `notices` and `heard` through `reset` as `replies` is carried (the comment at `Modes.geng:673` already gives the reason for replies). Whether `status` should survive is CL7's to say; it documents that RIS clears it.

### VP8 · `composeStyled` interns a style for every pane cell on every frame
- Where: `vt/src/Vt.geng:512-573` (`composePane`), `:577-631` (`composeCell`)
- Kind: speed
- Severity: medium
- Confidence: confirmed (the code); cost estimated
- What: the tmux view calls `composeStyled` each time it draws (`app/src/TmuxMode.geng:5055`, `:5067`). For each cell of each pane, `composeCell` calls `intern (styleOf style paneStyles) styles`: a `Dict.get` on the Int64 key, an `Array.findFirst` over the ids with that key, and a fresh `{ id, styles }` record; then `{ cells = Array.pushLast one.cell m.cells, styles, clusters }`, another record per cell. With a base color (`window-style`) even default-style cells go through `intern`. Before that, `rowsBetween` copies every row of the canvas and of each pane into `Array (Array Int64)`, and `writeRows` copies them back.
- Scenario: a 200x50 window is 10,000 cells a frame, each a dictionary lookup and two or three allocations, on the path that runs for every screen update of every tmux pane. A pane's distinct styles in view are typically a few dozen.
- Fix: per `composePane` call, keep a small map from the pane's style id to the canvas's (an array indexed by pane style id, filled on first use), so `intern` runs once per distinct style, and thread plain values instead of a record through the cell fold.

### VP9 · A C1 byte inside an APC, SOS or PM string ends it, so UTF-8 text in such a string is cut and its tail printed
- Where: `vt/src/Vt/Parse.geng:1051-1066` (`apcEnd`), `:1025-1026`, `:1086-1087`, `:945-966` (`c1`); by design per the comment at `Parse.geng:940-944` (Ghostty's "anywhere" transitions)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: OSC and a DCS's payload take bytes 0x80-0xFF as text, but APC, SOS and PM treat any byte 0x80-0x9F as a C1 control: the string is abandoned and the byte dispatched (`c1 ... (Kitty.apcDispatch False kept)`). In a UTF-8 terminal those bytes are continuation bytes of ordinary characters. xterm in UTF-8 mode decodes first and does not see them as C1.
- Scenario: `printf '\e_한글\e\\'` (screen's hardstatus form, with any Korean, Hebrew, or symbol text: `한` is ED 95 9C, `✓` is E2 9C 93). At 0x95 the APC is dropped and the parser is in the ground state; 0x9C prints U+FFFD and `글` prints as text, so the screen shows `�글`. The same in a PM or SOS string.
- Fix: this is Ghostty's behaviour and so "by design", but it is wrong for a terminal whose input is UTF-8: in APC/SOS/PM treat 0x80-0x9F as payload (as OSC does), ending only on ESC, CAN and SUB. If parity with the oracle matters more, record it as a known divergence from xterm.

### VP10 · XTRESTORE of a mode never saved builds a whole new terminal to read one default
- Where: `vt/src/Vt/Modes.geng:385-401` (`restoreMode`)
- Kind: efficiency
- Severity: low
- Confidence: confirmed (the code); the cost depends on whether the compiler removes the unused fields
- What: `privateState p (fresh t.config)`: `fresh` allocates a screen of `rows + 2 * pageRows + 1` rows (`newScreen`, about 2,100 rows by `cols + 1` Int64s with the default 1,024-row pages: 3.4 MB at 200 columns), a 1,024-slot style cache and the tab stops, to answer what is always 2 except for modes 1007, 1035, 1036 (1), 7 and 25 (1) and 6 (2).
- Scenario: `ESC [ ? 1 ; 2 ; ... ; 24 r` allocates and frees 24 such terminals per sequence; a stream of them is an allocation storm a remote program controls.
- Fix: a small function `defaultPrivate : Int -> Int` (the table `privateState` already encodes in its `Nothing` branch plus 6, 7 and 25), used by both.

### VP11 · `feedImaged` decides "in place" with `t.bottom == 0` where SU uses `t.bottom == t.rows - 1`
- Where: `vt/src/Vt/Scroll.geng:182`; the same expression at `vt/src/Vt/Dispatch.geng:511`
- Kind: bug
- Severity: low
- Confidence: plausible
- What: `Scroll.geng:182`: `inPlace = not (t.top == 0 && t.left == 0 && t.right == t.cols - 1 && (not (isAlt t) || t.bottom == 0))`. `Dispatch.geng:511` (SU, the same decision): `... (not (isAlt t) || t.bottom == t.rows - 1))`. The two were one rule written twice and now differ. The SU form says: rows leave the screen (rather than being lost in place) when the region starts at the top and, on the alternate screen, is the whole screen. The line-feed form's `t.bottom == 0` is only true for a one-row region.
- Scenario: on the alternate screen with a region `1;1` (top and bottom both row 0) and a Kitty placement in that row, a line feed takes `inPlace = False`, so `imagesMoved` treats the row as pushed to a scrollback the alternate screen does not have, and the placement is not scrolled off. Also the full-screen alt case is caught by `whole` before this in both places, so the only effect of the difference is that edge; it reads as a typo for `t.rows - 1`.
- Fix: make the rule one function (`leavesScreen : Term -> Bool`) used by SU and the line feed.

### VP12 · BS at the left margin above the scroll region, with reverse wraparound, moves the cursor down to the region's top
- Where: `vt/src/Vt/Dispatch.geng:748-749` (`cursorLeft`)
- Kind: bug
- Severity: low
- Confidence: plausible (not checked against Ghostty's `cursorLeft` for this case)
- What: `else if t.x == lm && mode == 1 && t.y <= t.top then { t | x = lm, y = t.top, wrapNext = False }`. For `t.y == t.top` this is a no-op, as meant ("stops at the region's top"). For `t.y < t.top` it sets `y = t.top`.
- Scenario: `ESC [ ? 45 h`, `ESC [ 5 ; 20 r`, `ESC [ 2 ; 1 H`, then BS: the cursor jumps from row 2 to row 5. The general path (`reverseLeft`) with the cursor one column further right would instead stay on its row or go up to a wrapped row.
- Fix: leave `y` as it is in that branch (`{ t | wrapNext = False }`), or restrict the branch to `t.y == t.top` and let `reverseLeft` take the rest.

### VP13 · DECRQSS's SGR report leaves out the underline color
- Where: `vt/src/Vt/Dcs.geng:233-291` (`sgrText`)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: `sgrText` writes flags, the underline's kind, `fg` and `bg`; `Attrs.ulc` (SGR 58) is never written, though SGR 58/59 are kept (`Sgr.geng:282-290`).
- Scenario: `ESC [ 4 : 3 ; 58 : 2 : : 255 : 0 : 0 m` then `DCS $ q m ST` answers `0;4:3` with no `58`; a program that saves and restores SGR through DECRQSS loses the underline color.
- Fix: add `color "58" ...` in the colon form for `a.ulc` (it has no 30-37 short form, so only the `58:5:n` and `58:2::r:g:b` branches).

### VP14 · A truecolor SGR copies the parameter array for each color, against the comment beside it
- Where: `vt/src/Vt/Sgr.geng:393-403` (`rgbAt`); comment at `:309-311` ("one `Int`, so that a color allocates nothing")
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: `rgbAt` does `from = Array.dropFirst at params` and then reads `from[0..2]`, a new array per color, on the SGR path that `dispatch` keeps inline for speed. `38;2;r;g;b;48;2;r;g;b` allocates twice.
- Scenario: truecolor output (one SGR a cell for image viewers and gradient prompts) pays two array allocations per SGR that the packing in `extendedColor` was written to avoid.
- Fix: read `at`, `at + 1`, `at + 2` directly; `extendedColor` already proved `len >= 5` (or the colon run's length), which is the refinement the reads need.

### VP15 · Unknown private modes are stored for a DECRQM that never reads them
- Where: `vt/src/Vt/Modes.geng:255-258` (`setPrivate`), `:426-428` (`privateState`); `docs/vt-core.md:488-489`
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: the last branch of `setPrivate` records any mode number ("recorded, so DECRQM answers what was set"), but `privateState` returns 0 for every mode not in `knownPrivate` before it looks in `modes`. The stored entry is dead, and `t.modes` can hold one entry for each of 65,536 numbers a program sends. `docs/vt-core.md:488` ("every private mode is recorded and answered by DECRQM") is stale in the same way.
- Scenario: `ESC [ ? 12345 h` then `ESC [ ? 12345 $ p` answers `0`, not `1`; a program that sets every number grows the dict to 65,536 entries for nothing.
- Fix: do not store modes outside `knownPrivate`, and correct the comment and the document.

### VP16 · Copying a long selection concatenates a string per cell and per row
- Where: `vt/src/Vt.geng:833-874` (`textOfRows`: `acc ++ text`), `:877-906` (`cellsText`: `acc ++ text` per cell)
- Kind: speed
- Severity: low
- Confidence: plausible (depends on whether Geng's `++` on a uniquely held string appends in place)
- What: both loops grow an accumulator with `++`. If each `++` copies, a selection of N rows costs about N^2 x (row length) / 2 bytes of copying.
- Scenario: a selection dragged over 50,000 rows of scrollback (about 4 MB of text) would copy on the order of 100 GB; 10,000 rows about 4 GB.
- Fix: collect the rows' pieces in an array and `String.join` once (and per row, build from an array of code points).

### VP17 · Jump-to-prompt with no prompt in the scrollback walks every row, and each row walks the pages from the oldest
- Where: `vt/src/Vt.geng:1252-1261` (`promptUp`), `:1293-1319` (`promptMark`, `pagedPrompt`)
- Kind: speed
- Severity: low
- Confidence: confirmed (the code); cost estimated
- What: `promptUp` steps one row at a time down to the scrollback's oldest row; for a paged row `promptMark` calls `pagedPrompt t.back t.back.head ...`, which steps over every page before the row's. Rows x pages / 2 steps.
- Scenario: a shell without OSC 133 and a million-row scrollback (about 1,000 pages): one press of the jump key is about 5 x 10^8 steps, a visible stall.
- Fix: walk page by page (newest first), scanning each page's row headers once, instead of row by row from the head.

## Looked at and found sound

- **Parser state machine** (`Parse.geng`): resumes at any byte through `t.ps`; CAN/SUB/ESC handled in every state; CSI parameters clamp at 65,535 and at 24 parameters (`paramMax`, so the `colons` bit mask cannot overflow); a second intermediate, a private marker after a parameter and a colon outside SGR go to `csiIgnore`; DEL and bytes >= 0xA0 inside a sequence are skipped.
- **UTF-8** (`startUtf8`, `continueUtf8`, `decodeRun`, `wellFormed`): overlongs, surrogates and > U+10FFFF rejected by the first-continuation ranges; maximal-subpart replacement; U+0080-U+009F decoded from UTF-8 are not executed as C1 (`printDecoded` drops them), so a C1 cannot be smuggled through valid UTF-8 in the ground state.
- **Limits on what a program fills**: OSC/DCS kept bytes (`stringMax` 4,096, `oscMax` 2,048 with over-long strings dropped whole), OSC 52 (8 MB, dropped whole when over), APC/Sixel/iTerm data (`Kitty.apcMax`), notices (16), kitty key stack (8), parameter count (24), tab stops (one per column), cluster length (65), title and working directory (within `oscMax`).
- **Replies** (DSR 5/6, DECXCPR, DA1/2/3, XTVERSION, DECRQM, DECRQSS, DECCKSR, XTWINOPS 14/16/18/19, mode 2048/2033/996 reports, OSC 4/10-12 queries, OSC 7501 query, kitty `CSI ? u`): every reply is built from fixed text, numbers and hex digits, or from embedder-set strings; none echoes program-supplied text. There is no title report (XTWINOPS 20/21) and no answerback, DECRQSS echoes nothing of the request, and DECRQCRA is off unless `Config.checksums`. I found no reply a program can shape into injected input in this slice. (OSC 52 reads are passed to the embedder to decide; Kitty graphics replies are another slice.)
- **Reply formats** checked against xterm ctlseqs: CPR, DECXCPR (`?r;c;1R`), DECRPM (`?p;s$y`), DECRPSS (`1$r...`), DECSCUSR report (shape plus blink from mode 12), XTWINOPS 4/6/8/9 reports, DECCKSR, OSC 4/10 `rgb:hhhh/hhhh/hhhh` with the request's terminator.
- **SGR** (`Sgr.geng`): 38/48/58 in semicolon and colon forms, colon runs skipped where Ghostty skips them, style key packing (flags<<53, ul<<50, fg<<25, bg) has no overlapping fields for 25-bit colors; the 512-slot style cache stores and restores pen and erase ids consistently and is bypassed for linked or underline-colored pens.
- **Color parsing** (`parseColor`, `highHex`, `scaledHex`, `intensity`, `digits`): digit and length bounds hold; no overflow.
- **Cell and row edits** (`Print`, `Edit`, `Cursor`, `Screen`): wide-character splitting at both ends of a write, ICH/DCH/ECH/EL/ED counts clamped to the row, margined copies clamped to the region, negative-index guards before `Builder.get`. These are refinement-typed and differential-fuzzed; I read them for bounds and counts, not for cell-exact parity with Ghostty.
- **Hot print path**: `printAscii` writes a run with one extent update and `Bytes.spanWithin`; `printUnicode`/`decodeRun` write a row's run without per-character term updates; `lineFeed` at the bottom is O(1) plus one row clear (`feedFull`, `feedRegion`). No per-byte or per-cell allocation found on the plain path. REP repeats up to 65,535 cells per sequence, which is what xterm and Ghostty also do.
- **Tabs, cursor moves, origin mode, DECSTBM/DECSLRM, DECSC/DECRC, alt-screen switches, DECSTR**: counts and clamps hold; CHT/CBT stop at the margin so a large count ends early.
- **`Reason.geng`, `Palette.geng`, `Cell.geng`**: nothing to report.

## Not covered

- `vt/tests/`, the corpus and the fuzzers were not read, so no test-gap findings are given beyond the corpus cases suggested above.
- Cell-exact parity of `Print`/`Edit`/`Cursor` with Ghostty (spacer heads, `stale` conditions, protected erases) was not re-derived; the differential fuzzer is the authority there.
- Modules these files call but that are outside the slice were read only where a finding needed them: `Vt.Kitty`, `Vt.Placed`, `Vt.Pages`, `Vt.Resize`, `Vt.Prompt`, `Vt.Notice`, `Vt.Status`, `Vt.Width`, `Vt.Probe`.
- `docs/ghostty.md` and `docs/phase1-core.md` were not read through; `docs/vt-core.md` and `docs/claude-code.md` were searched for the decisions each finding touches, not read whole.
- Whether `Array.pushLast`/`++` on uniquely held values update in place in compiled Geng was not established; findings that depend on it are marked plausible.

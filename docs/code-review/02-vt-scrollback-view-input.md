# Slice 02: vt scrollback, reflow, view, input encoders

Files read whole: `vt/src/Vt/{Pages,Resize,Recut,View,Placed,Dump,Probe,Status,Notice,Prompt,Charset,Keys,Mouse,Paste,Base64}.geng`,
`Placeholder.geng` to line 330 (the rest is the diacritics table), the lookups of
`Width.geng`, `vt/gen-*.py`. Callers read where a finding needed them:
`vt/src/Vt.geng` (`viewAt`, `rowsBetween`, `viewPages`, `selectionText`, `compose`),
`vt/src/Vt/{Style,Cell,Print,Modes,Dcs,Osc}.geng` in part, `app/src/Search.geng`,
and the paste, mouse, charset and frame call sites in `app/src/Main.geng`.
Nothing was built or run; "confirmed" below means confirmed by reading the code
and its callers.

---

### VS1 · Scrollback search decodes a whole 1,024-row page for every row it looks at
- Where: app/src/Search.geng:48-80 (`findFrom`), :125-150 (`matchesIn`/`rowMatches`); vt/src/Vt.geng:783-830 (`selectionText`), :744-767 (`rowsBetween`), :1325-1354 (`viewPages`); vt/src/Vt/Pages.geng:533-553 (`pageRowsOf`), :595-628 (`unpackPage`)
- Kind: speed
- Severity: high
- Confidence: confirmed (by reading; the per-page cost is the document's own measurement)
- What: `Search.findFrom` asks `Vt.selectionText { row, 0 } { row, cols-1 }` once per row and recurses to the next row until a match. For a row in the pages, `rowsBetween first 1 t` calls `viewPages`, which walks the page slots from `back.head` and then runs `pageRowsOf page clusters`: `unpackPage` decodes all of the page's rows (1,024 by default) into `DumpRow` records, a second fold turns every cell into an `Int64` through `pagedCell`, and then `Array.slice (at - start) (at - start + want)` keeps one row. `docs/phase3-select.md` §13 measures a view read (one or two page decodes) at 1.8 to 4.2 ms and accepts it per frame; search pays it per row.
- Scenario: a full default scrollback (§13's bench: 94,095 rows at 160 columns; 25,000 rows at full width) and Ctrl+Shift+F with a query that has no match, or whose nearest match is far up. Every key typed in the bar runs `Search.find query True viewBottom` synchronously in `update` (app/src/Main.geng:8113-8127): about 2 ms a row, so 50 s for 25,000 rows and minutes for 94,000, with the window frozen, and again for the next key. `matchesIn` (tmux copy mode's marks, app/src/TmuxMode.geng:16291) does the same per visible row per call.
- Fix: read rows a page at a time. Either give `Vt` a search entry that walks the pages once (decode each page once, or scan the page's UTF-8 `text` directly for the lowered query and only decode a row that matches), or let `rowsBetween`/`viewPages` decode only the wanted rows of a page (walk `heads` to the row's text offset, then `Recut.rowAt` for that row), which is also what `phase3-select.md` §18 registered and did not build. A bound on rows searched per update step, continuing on the next, would keep the window alive either way.
- Fixed: 2026-11-21: see MA3.

### VS2 · OSC 99 parts with `d=0` grow a pending notification without bound, each part copied onto the last
- Where: vt/src/Vt/Notice.geng:152-175 (`fromOsc99`); caller vt/src/Vt/Osc.geng:323-328
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: for `d=0` the payload is appended to the pending entry of its id, `{ before | body = before.body ++ text }` (or `title`), and kept: `{ pending = Array.pushLast added (Array.takeLast 15 others), done = Nothing }`. The number of ids is capped at 16 but an id's `title` and `body` are not capped; `clean 256` / `clean 1024` run only in `notice`, when a part with `d=1` completes it.
- Scenario: a program (or a file `cat`ed) repeats `OSC 99 ; i=1:d=0:p=body ; <2,000 bytes> ST`. The terminal keeps every byte for the life of the session (until RIS), and each part re-copies the whole string so far: 10 MB of such output is about 5,000 appends of a string averaging 5 MB, some 25 GB of copying inside `feed`; 100 MB does not finish. With `e=1` the same through `Base64.decode`.
- Fix: cap as it accumulates, the same limits `notice` applies at the end (keep at most 256 characters of title and 1,024 of body per id, drop the rest), so a part past the cap costs nothing.

### VS3 · A selection that starts on the right half of a wide character leaves that character out of the copy
- Where: vt/src/Vt.geng:877-906 (`cellsText`), :783-830 (`selectionText`); anchor taken raw at app/src/Main.geng:7691-7693 (`pointAt`), copied at :7761
- Kind: bug
- Severity: medium
- Confidence: confirmed (by reading; not run)
- What: `cellsText` starts at column `lo` and emits nothing for a cell whose width state is `wideTail` (`if w == wideTail || w == spacerHead then ""`). The head, at `lo - 1`, is outside the range, so the character is not in the text. `selecting` stores `pointAt p m` as the anchor with no move to the head, and `View`'s highlight starts at the same cell (`selFrom`), so half the glyph is highlighted. `wordAt` does treat a tail as its head (phase3-select.md §14); the plain drag does not.
- Scenario: Korean or Chinese text on a row, press the button on the right half of the first syllable wanted (half of all presses on a wide character) and drag right; or drag right to left and release on a right half. The copied text is missing its first character.
- Fix: in `selectionText`, when the ordered start's cell is a `wideTail`, start one column earlier (and the highlight with it); a test in `corpus/select/` for a start on a tail.

### VS4 · The frame's diff trusts style and cluster ids across RIS, which hands the same ids out again
- Where: vt/src/Vt/View.geng:1518-1558 (`diffRow`), :1785-1803 (`drawnAs`), :1680-1707 (`colorKey`); vt/src/Vt/Modes.geng:678-696 (`reset`), :85-88 (`fresh`: `styles = noStyles`, `clusters = noClusters`)
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading; not run)
- What: the shadow keeps each drawn cell as the core's `Int64`, whose high bits are a style id and whose low bits may be a cluster id, and a cell equal to the shadow's is not drawn. RIS builds the term with `fresh`, so ids start from 0 again and the same id can name another style or cluster. `colorKey` covers mode 5, the look and `t.colors` only, and no caller makes a new shadow at RIS (`View.shadowIn` is called at size, font and tab changes), so the shadow is not forgotten.
- Scenario: `printf '\033c\033[31mA'; sleep 1; printf '\033c\033[34mA'`. After the first, cell (0,0) is `A` in style 1 (red). The second resets and writes `A` in style 1 again, now blue, in one read. `drawnAs` equals the shadow's cell, no run and no style record is sent, and the `A` stays red until something else redraws it. The same with two different clusters that both get cluster id 0 in the same cell.
- Fix: carry a generation in the term that `reset` bumps (or fold `Array.length t.styles.table` going down into the test), and have `frameOn` make a fresh shadow when it changes, as it does for `colorKey`.

### VS5 · An unbracketed paste of CRLF text sends CR CR, and a CRLF split across two pieces does too
- Where: app/src/Main.geng:7354-7380 (`lineEnds`), :7416 (`lineEnds (Paste.piece bracketed text)`); vt/src/Vt/Paste.geng:69-74
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading; not run)
- What: `lineEnds`' comment and `docs/tmux.md` TM95 say "every LF goes as CR, bracketed or not ... and CRLF as one CR". `lineEnds` drops an LF only when the byte before it in the same call was CR. But `Paste.piece False` has already turned each LF into CR (`if bracketed then 0x0A else 0x0D`), so for an unbracketed paste `lineEnds` sees `CR CR` and passes both. And `lineEndsFrom` starts each piece with `last = -1`, so when a paste comes in pieces (`pasteInto more`, INCR) and one piece ends in CR and the next begins with LF, the LF becomes a second CR, bracketed or not. TM95's check of CRLF was made with brackets on.
- Scenario: on Linux, text with CRLF line ends on the clipboard (copied from a file with DOS line ends, or through a remote-desktop clipboard), pasted into a program that did not set mode 2004 (`cat > file`, a `read` loop, an older REPL): every line end arrives as two Enters. Windows' clipboard read already makes CRLF LF, so it is Linux only.
- Fix: collapse CRLF before `Paste.piece` (or have `lineEnds` treat `CR CR` that came from `CR LF` as one, which needs the original bytes), and keep `last` across pieces in the model next to `pasting`.

### VS6 · The diagnostic log gets a DECRQSS or XTGETTCAP body as the program wrote it, control bytes included
- Where: vt/src/Vt/Probe.geng:175-184 (`dcsText`), :189-225 (`unhex`); caller vt/src/Vt/Dcs.geng:134-138; vt/src/Vt/Dcs.geng:149-172 (`dcsClean`, phase 3 keeps every byte)
- Kind: security
- Severity: low
- Confidence: plausible (the log's writer, outside this slice, may escape lines; not checked)
- What: the module's comment says "Nothing a program shows is written ... a DCS's body [is] given by [its] size". For a body that starts `$q`, `dcsText` writes `String.dropFirst 2 text` whole, and for `+q` each `;` piece through `unhex`, which answers the piece itself when it is not hex. `dcsClean` keeps every byte after the final byte, C0 controls and newlines among them, and a DECRQSS longer than four characters is still logged ("not answered") at Dcs.geng:134. Up to 4,096 bytes.
- Scenario: with `[debug] log` on, a program sends `DCS $ q` followed by a newline and text shaped like another log line (or terminal escapes, for whoever `cat`s the log). The log shows a line the terminal never wrote.
- Fix: write the setting only when it is short and printable (as `Probe.written` does for answers, naming control bytes), else its size; the same for a `+q` piece that is not hex.

### VS7 · `Base64.decode` is documented as strict but takes non-canonical final characters
- Where: vt/src/Vt/Base64.geng:7-11 (comment), :116-129
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed for the code; plausible for the claim that Ghostty's decoder refuses it (Zig's `std.base64` answers `InvalidPadding` for leftover bits, from memory)
- What: for a final group of two characters only `(a << 2) | (c >> 4)` is written and `c`'s low four bits are never tested; for three, `d`'s low two bits. So `QR==` decodes as `QQ==` does. The comment says the decoder is "strict as Ghostty's `decodeStrict(.optional)` is meant to be".
- Scenario: OSC 52 or OSC 7501 (`Status.decoded`, which drops a report whose `msg` "is not base64") accepts text a strict decoder refuses. No harm found; the comment and any gate that holds it to Ghostty disagree with the code.
- Fix: refuse a final group whose unused bits are not zero, or say in the comment that they are ignored.

### VS8 · Every frame copies the `drawnIn` stamps and allocates a `worded` array, with no image and no ink on the screen
- Where: vt/src/Vt/View.geng:690-691 (`imagesDrawn`: `stamps = Builder.slice 0 (rows * cols) done.shadow.drawnIn`), :1259 (`spread`: `worded = Builder.fromArray (Array.repeat (cols * rows) False)`)
- Kind: efficiency
- Severity: low
- Confidence: confirmed (assuming a `let` is evaluated where it is written, as in Gren)
- What: `imagesDrawn` slices `rows * cols` ints out of `drawnIn` before it looks at `desired`; with no placement in view (`touched` is then empty) the copy is unused. `spread` builds a `rows * cols` array of `False` each frame even when `collect` queues no cell. Both are per frame, the first up to three times a frame through the recursion.
- Scenario: a 300 by 100 window: 240 KB copied and 30,000 elements allocated for every frame, a cursor blink included, on top of the three passes over the cells the diff needs (`hashRows`, `collect`, `diffRows`).
- Fix: return early from `imagesDrawn` when `desired` is empty, before the slice; make `worded` only when `collect` returns a non-empty queue (or keep it in the shadow and clear what was set).

### VS9 · `Recut.gather` decodes a row that is not single-column twice
- Where: vt/src/Vt/Recut.geng:246-258 (`gather`), :427-432 (`lastSource`), :981-1009 (`rowAt`)
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: when `scan` answers -1 (a wide character, a cluster, a spacer head or a background-only cell in the row), `gather` runs `(unpackText page.text ti ext []).next` to find where the row's text ends, building and dropping the row's cell records; `slowLine` then calls `rowAt`, which runs `unpackText` on the same row again. `lastSource` does the same for every such row of the last page at each resize.
- Scenario: a scrollback of CJK text (every row takes the slow path) during a window drag: each row of each page is decoded twice per resize step, where `docs/vt-core.md` §VC34 already names the cut of lines that are not plain as the resize's cost.
- Fix: a text-only walk that answers the end offset without building cells (as `skipCells` does for the narrow case, extended to wide and zero-width code points and the 0xFE/0xFF bytes), or keep the first decode's cells in the `Source`.

### VS10 · `Prompt.geng`, `Pages.geng`, `Resize.geng` and `Dump.geng` import what they do not use, some of it twice
- Where: vt/src/Vt/Prompt.geng:13-34; vt/src/Vt/Pages.geng:46-56; vt/src/Vt/Resize.geng:61-74; vt/src/Vt/Dump.geng:28-42
- Kind: dead-code
- Severity: low
- Confidence: confirmed
- What: left from the split of `Vt.geng` (§VC23, §VC45): `import Vt.Cell exposing (..)` and others appear twice in a row; `Prompt.geng` (136 lines, which set a row's mark) imports `Vt.Base64`, `Vt.Keys`, `Vt.Recut`, `Vt.Resize`, `Vt.Dump`, `Vt.Palette`, `Vt.Pages`, `Vt.Width`, `Math`, `Dict`, `Bytes`, `UInt8` and uses none of them.
- Scenario: `Prompt` depends on the whole resize and dump chain for nothing, so the module graph says the prompt marks sit above `Resize` and `Dump` when they do not, and any of those modules that later wants `Prompt.setPrompt` meets an import cycle.
- Fix: delete the unused and repeated imports.

---

## Looked at and found sound

- **Keys.geng** against the vendored `vendor/ghostty/src/input/key_encode.zig`: the kitty path (release filtering, composing, Enter/Tab/Backspace legacy bytes, plain-text shortcut, the no-entry fallback, modifier-only keys, alternates, associated text, `CSI 1;mods:event` forms), the legacy path (PC-style table matching and its three mode tests, the IME text exceptions for Backspace/Enter/Escape, `modifyOtherKeys` 2 with xterm's `should_modify`, `ctrlSeq`, fixterms CSI u with kitty's lowercasing, the alt ESC prefix), and `KittyMods.fromInput`, which in the vendored source ignores the action and key as the port does. No difference found. `gen-keys.py` takes the first entry per key and the tables are bounds-checked on lookup.
- **Mouse.geng** against Ghostty's encoder as documented: what each tracking mode reports, the outside-the-window rule, cell clamping, legacy release as button 3, modifier bits, X10's 222 limit, the five formats.
- **Paste.geng**: the replaced set is Ghostty's and xterm's list byte for byte (`vendor/ghostty/src/input/paste.zig`); ESC is always replaced, so a paste holding `ESC[201~` cannot close the bracket; the per-piece encoding is safe for UTF-8 since continuation bytes are 0x80 and up. In an EUC-KR pane the encoded paste goes through `Charset.encode`, whose trail bytes are 0x41 and up, so it adds no control byte.
- **Charset.geng**: WHATWG's `euc-kr` decoder: a lead kept across reads, an ASCII trail after a bad lead read again (so ESC is never swallowed), 0x80 and 0xFF as U+FFFD, no C1 made; the encoder's first-pointer rule (the `foldr` makes the lowest pointer win) and strict EUC-KR's `?` with a count. `gen-euckr.py`'s table is 126 by 190 as the decoder indexes it. Legacy mouse reports bypass the encoder (`sendRaw`).
- **Base64.geng**: padding rules, the lone-character refusal, builder capacities, the encoder.
- **Pages.geng**: the page format round trip (text, headers, runs) against what `Print` can put in a cell: a cell's width is always `Width.width` of its first code point and only width-0 code points join, so `unpackText`'s reading by width cannot drift from `packCells`; `plainPage`'s byte-count argument; `dropOver`/`compact`'s amortized cost; `addRows`' saturation.
- **Resize.geng / Recut.geng**: read for structure, bounds and cost rather than re-derived against Ghostty's reflow, which the differential fuzzer and `recutHolds` (§VC31) hold; `promptIn`'s binary search, `splitAt`'s slice path, the `lossy` and `short` fallbacks and the pages always having the screen's width were followed and are consistent. The appends in `joinLines`/`reflowCols` (`j.line ++ kept`, `acc.rows ++ cut.rows`) look quadratic for a long wrapped line, but §VC36 measures a 10,000-row line at 0.31 ms a resize, so they are not reported.
- **View.geng**: run cutting at wide heads and tails, the cursor and selection marks in the shadow, the scroll band search and `copyWithin`, ink spreading, the preedit overlay's wrapping, style and cursor records, the highlight record. The tmux canvas keeps its own style and cluster tables across frames (`Vt.composeStyled`), so its ids are stable for the shadow.
- **Status.geng, Notice.geng (OSC 9, 777), Prompt.geng, Placed.geng, Placeholder.geng (logic), Dump.geng, Width lookups, gen-width.py**: bounds on what a program sends are in place (ids, sizes, 256 records, control characters refused); nothing found.

## Not covered

- Known and left out as documented: the per-frame page decode of a view scrolled back (phase3-select.md §13, §18); the style and cluster tables that never shrink, 32,760 styles and 2^21 clusters (vt-core.md §VC9); a cluster drawn with at most 63 code points (View's header).
- `Vt.geng` itself beyond the functions named at the top (`resize`'s pins, `wordAt`, `lineAt`, `promptJump`, `compose`'s image handling) and `Vt.Kitty`: not in this slice.
- `app/src/Search.geng` was read only for the cost above. One thing seen there for its reviewer: `findFrom` takes the match's index in `String.toLower text` and applies it to `text`; where lowering changes a string's length (U+0130) the match's columns shift.
- The reflow's results cell by cell against Ghostty (spacer heads in rows that no longer wrap, saved-cursor placement): not re-derived by hand.
- `Placeholder.geng`'s diacritics table (lines 330 on), `KeyTables.geng`, `Width.geng`'s tables, `EucKrIndex.geng`: generated, not read.
- No harness or test was run; the keys, mouse, paste and charset gates were taken as described in the documents.

# Slice 13: the application's picker, dialogs and settings

Files read whole: `app/src/{Picker,PickerDemo,Dialog,Schema,SettingsWindow,SettingsGui,SettingsProgram,SettingsFile,SettingsSource}.geng`,
plus `app/src/TextEdit.geng` and `app/src/Config.geng` (which they lean on), the
interface-record parser in `packages/text/src/Ext/puritty_text.c:1430-1463`, and
`docs/user/settings.md`, `docs/settings.md` (ST2-ST6, ST15-ST20, ST25-ST32),
`docs/settings-gui.md` SG20, `docs/sftp.md` FT32-FT33. Nothing was built or run:
every finding is from reading the code, and "confirmed" means the path was traced
in the source, not observed.

Two facts used throughout, both checked:
- `Array.get` with a negative index reads from the end
  (`/home/gram/prj/geng-lang/vendor/gren-lang/core/src/Array.geng:384-406`, `get -1 [1,2,3] == Just 3`).
- `Int` is 32 bits (`SettingsProgram.geng:471-473` says so of the clock; `Picker.bounded`/`little` exist for it).

---

### PS1 · Enter on the font box with nothing picked sets the last font in the list
- Where: app/src/SettingsWindow.geng:1521-1533 (the `Array.get t.pick` at 1527); app/src/SettingsGui.geng:1201-1202 (the sample line); `pick = -1` set at SettingsWindow.geng:89, 1372, 1850
- Kind: bug
- Severity: high
- Confidence: confirmed
- What: `name = Maybe.withDefault (String.trim (String.fromArray t.chars)) (Array.get t.pick (suggestions m t))`. `t.pick` is -1 until Down is pressed, and `Array.get -1` answers the last element, not `Nothing`, so the typed name is never the fallback while the list is not empty. `hostAt` (506-514) and `Picker.rowAt` (Picker.geng:668-676) guard this same trap; this place was missed.
- Scenario: (a) Enter on the Font row, then Enter again without touching anything: `suggestions` is every system font (the name is unchanged, 2025-2030), and `font.family` is written as the alphabetically last one. (b) Click the font's value, then click anywhere else: `hit` finishes typing "as Enter does" (1901-1908), same result. (c) Type `fira`, Enter: with "Fira Code" and "Fira Mono" offered, "Fira Mono" is written, not what was typed. Every open terminal re-fonts at once. The tests only press Down before Enter (`app/tests/src/AppSuites.geng:1326-1329`), so none covers no pick. The sample line under the list is drawn in the last font for the same reason.
- Fix: look the pick up only when `t.pick >= 0` (a `pickAt` helper as `rowAt` is), in both places; add a test for Enter with no pick, and for a click away.
- Fixed: 2026-11-21. The pick is looked up only when it is 0 or more (`SettingsWindow.picked`, and the sample line in `SettingsGui`), so Enter or a click away with nothing picked takes the name typed. Test: "a font's name typed with fonts offered and none chosen is taken as typed" (`fira`, and Enter twice untouched).

### PS2 · A click away from quick connect connects to what is typed (and from "New host" makes the host)
- Where: app/src/SettingsWindow.geng:1897-1926 (`hit`), 1454-1458 (`typingKey` routes the list's rows to `quickKey`/`newHostKey`), 1655-1658 (Enter connects), 1602-1617 (Enter makes the host); app/src/SettingsProgram.geng:509-527 (the middle button goes the same way), 711-714 (the host list becomes the session)
- Kind: bug
- Severity: high
- Confidence: confirmed
- What: a click on anything but the box being typed in first runs `typingKey { sym = sym.enter } t m` so that a setting's typed value is kept (ST27). On the host list the box typed in is quick connect or New host, where Enter is not "keep" but "connect" (`effects = [ ConnectQuick text ]`) or "make the host" (`PutHost`).
- Scenario: `puritty hosts` opens with quick connect already being typed (`init`, 204-209). Type `bui`, then decide on a saved host and click its row (a single click only highlights), or click the search field, a page, or paste with the middle button on another row: `ConnectQuick "bui"` runs. In the host list `connect` sets `outcome = Session h, closed = True`, so the window becomes an ssh session to `bui`; in the settings window a new puritty is started to it. A half-typed name on the New host row is written to `config.toml` as a host the same way.
- Fix: in `hit`, when `inList m`, a click away drops the typing (as Esc) or just leaves it; only settings' values take the Enter path.
- Fixed: 2026-11-21. In `hit`, what is typed in quick connect or New host (`inList`) is let go as Esc lets it go, not finished as Enter, which connects or makes the host; the middle button goes through `hit` too. Test: "a click away from quick connect or New host lets what is typed go".

### PS3 · What is typed is tied to a row number, so it lands in another setting when the list changes under it
- Where: app/src/SettingsWindow.geng:1844-1869 (`typedSetting` uses `focused m`), 293-307 (`listedSettings` filters by `modified m.config`), 903-921 (Ctrl+M keeps `typing`), 1501-1516 (Esc), 1557-1580 (Enter), 238-240 (`fileRead`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `Typing` holds no setting; each keystroke asks `focused m = Array.get m.row (listed m)` again. Under "Modified only" `listed` depends on the config, which typing itself changes; and Ctrl+M re-filters and sets `row = 0` without ending the typing (`control` falls through `TextEdit.key`'s `NotMine` to `controlNotEditing`, which clears `typing` for Ctrl+Z and Ctrl+F but not for Ctrl+M).
- Scenario 1 (Modified only on, scrollback 50000 and blink 250 modified, on Advanced/Appearance as applicable): Enter on scrollback, retype towards `250000`. At `25000`, the default, the value is written, the setting stops being modified and leaves `listed`; row 0 is now the next modified setting, and the following `0` is parsed and written as *that* setting's value. A hand edit read by `fileRead` mid-typing shifts rows the same way.
- Scenario 2: typing `250` in Cursor blink, press Ctrl+M; row 0 is Font size. Backspace gives `25`, a valid size: `font.size = 25` is written and every terminal re-fonts. Esc then runs `s.set t.before` on Font size with blink's old value and writes it through `Schema.write` with no range check: `font.size = 500` in the file, which the decoder then reports.
- Also: Ctrl+F and Ctrl+Z while typing drop `typing` without the Enter path's undo entry, so what was written while typing cannot be undone (and Ctrl+Z undoes an older change instead).
- Fix: keep the `Setting` (or its key) in `Typing` and write/revert through it; end typing (commit or revert) on Ctrl+M, Ctrl+F, Ctrl+Z and on a `fileRead` that removes the row; have Esc go through `Schema.fromText`-level validation or simply restore without `set` when kinds differ.

### PS4 · With a color scheme set, a color equal to puritty's default cannot be chosen, and the reset mark does nothing
- Where: app/src/Schema.geng:2140-2168 (`write` removes a key when `v == s.get Config.defaults`), 1110-1118 (`decode` starts from `Palettes.apply name Config.defaults`); app/src/SettingsWindow.geng:252-254 (`modified`), 1389-1401 (`set`), 1179-1196 (reset); app/src/SettingsFile.geng:86-90
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: "default" means two things. The file's reader takes a missing `foreground`/`background`/`palette` from the scheme (ST29); the writer and the window take it to be `Config.defaults`'s.
- Scenario: `[colors] scheme = "solarized-dark"`. (a) In the window set Background to `#1d1f21`: `write` sees the default and removes a key that is not there, `SettingsFile.change` finds no byte changed and writes nothing, no file event comes, and the window goes on showing `#1d1f21` while every terminal keeps Solarized's; the next unrelated write snaps the row back. (b) Foreground, Background and Palette show the modified bar and `↺` (and count on the page, and list under Modified only) though the file sets none of them; `↺` sets the model to puritty's colors and writes nothing, same split. (c) Choosing a scheme in the list changes only `c.scheme` in the model (`set` at Schema.geng:384-392); the rows show the old colors until the file read comes back.
- Fix: one notion of a setting's default given the rest of the config (for the three colors, the scheme's): use it in `write`, `modified`/`changed` and reset; and make the `scheme` setter apply `Palettes.apply` to the model.
- Fixed: 2026-11-23, `docs/settings.md` ST38. `Schema.defaultsFor config` (the scheme's three colors when one other than puritty's is set) is the default for `Schema.write`, the window's modified mark and Modified only, and its reset; the scheme's setter moves each color still at the old scheme's. Test: the Writing suite: before, `#1d1f21` was not written, the row showed modified, and choosing the scheme left the model's colors.

### PS5 · Rows scrolled partly under the header still take its clicks
- Where: app/src/SettingsGui.geng:732-733 (`visible`), 772-788 (`rowBox`, `target rowBox (OnRow i)`), 878 and 887 (value and reset boxes), 422-425 (the header's boxes), 227 (`Array.reverse d.hits`); app/src/SettingsProgram.geng:494-496
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: drawing is clipped to `listBox`, but a row's hit boxes are pushed whole, and since rows are drawn after the header their boxes come first in the reversed list. A row that begins above `top` covers the search field and the Modified-only switch (same x range: `x0 - px 12`, width `cw + px 24`).
- Scenario: any page taller than the window (Advanced, Window, Keys). Press Down to the last row: `keepInView` aligns the bottom, leaving the first shown row cut by one to several lines (rows are 4 lines or more, SG12). With it cut by two lines or more, a click on the search field or on "Modified only" is `OnRow i` (or `OnValue i`, toggling a switch that is not visible): the list jumps to that row and the search is not focused.
- Fix: intersect each row's hit boxes with `listBox` before `target` (a `targetIn clip box` helper), as the drawing is clipped.
- Fixed: 2026-11-23, `docs/settings-gui.md` SG22. `Drawn.hitClip`, the list's box while the rows are drawn, cuts every hit box `target` pushes. Test: the SettingsWindow suite: before, the search field's and the switch's middles landed on rows scrolled 2, 3 and 6 lines.

### PS6 · Two listings of one folder in flight corrupt the listing (duplicates, or a part shown as the whole)
- Where: app/src/Picker.geng:483-515 (`listed`: `before` comes from the cache by path), 396-427 (`goTo`/`fetch` ask again while a listing of the same path is in flight), 1730-1746 (each press on a crumb or a place is a `goTo`), 1125-1135 (`refresh`), 1378-1384 (`peekTyped`); app/src/PickerSftp.geng:34, 390 (`readings : Dict Int Reading`, one per request id, so they do run side by side)
- Kind: bug
- Severity: medium
- Confidence: plausible (the picker's logic is confirmed; the interleaving of two READDIR streams in PickerSftp was read, not run)
- What: parts are appended to `cache[path].entries` whenever that entry is incomplete, whichever request they came for; when either request ends, the entry is marked complete, and the other's next part then starts from `[]`.
- Scenario: a folder that takes more than one READDIR (a few hundred names), not yet cached. Double-click its bookmark or its breadcrumb segment (two presses, two `fetch`es, ids 1 and 2), or press Ctrl+R twice, or type its path so that a `Peek` and a `Go` overlap. Parts interleave: the list shows names twice; when id 1 ends the entry is "complete" with duplicates; id 2's last part then replaces it with only that part, `complete = True`. The box says "N items", Send is enabled, and the wrong listing stays cached for the box's life (same-name clash marks are then missing too).
- Fix: accumulate parts per request id (in `waiting`), and write the cache entry only from the request that owns it (ignore or cancel a superseded one); `goTo` to the path already being gone to should not ask again.

### PS7 · The picker sorts and filters names as lossy UTF-8, not in the host's character set
- Where: app/src/Picker.geng:357-378 (`sortKey`: `Bytes.toStringLossy e.name`), 649-657 (`rows`: the filter); against 2675-2681 (drawn with `with.decode`) and 1263 (completions with `with.decode`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: the module says "Names are the host's bytes; the caller says how its character set reads and writes them (`With`)", but `sorted` and `rows` do not have `With` and read the bytes as UTF-8.
- Scenario: a host whose `charset` is `euc-kr` (a case the project names). Hangul names decode to runs of U+FFFD: typing Korean into the filter matches nothing ("No name here has … in it") though the names are drawn correctly, and Korean names sort in READDIR's order (equal keys) while ASCII ones sort. Path completion on the same names works, since it uses `with.decode`.
- Fix: pass `With` to `listed`/`sorted` and `rows` (or decode once when a part arrives and keep the lowercased name beside the entry, which also removes the per-frame lowercasing below).

### PS8 · `middle` cuts a long label one character at a time, measuring the whole string each time
- Where: app/src/Picker.geng:1849-1871 (`middle`, `middleFrom`); used per frame at 2175, 2252, 2578, 2620, 2712, 2788, 2794, 2891, 2912, 2974, 3042; contrast app/src/SettingsGui.geng:629-654 (`fit`, a binary search)
- Kind: speed (and security: a remote host can hang the window)
- Severity: medium
- Confidence: confirmed (the loop); plausible (how slow `Text.width` is per call)
- What: `middleFrom size width s keep` builds `takeFirst … ++ "…" ++ takeLast …`, measures it with `Text.width`, and recurses with `keep - 1` until it fits: O(L) measurements of O(L) characters. It runs for every visible row's name and link target, every bookmark and recent place, the status line and the title, on every frame, and again for every pointer event (next finding).
- Scenario: names come from the host. A folder of links whose targets are near PATH_MAX (4096), or an SFTP server that answers READDIR with very long names (the length is the server's to choose): each row costs millions of glyph measurements per frame, for ~20 rows, per mouse motion. The whole terminal window (all tabs) stalls while the picker is on that folder. A user's own deep bookmarks pay the same quadratic cost on every frame at a smaller scale.
- Fix: binary-search `keep` as `fit` does (or share one `fitMiddle` in SettingsGui); cap a name's length before measuring (nothing past a few hundred characters can show); bound entry-name length where listings are parsed.

### PS9 · Each part of a listing re-sorts everything received so far
- Where: app/src/Picker.geng:491-504 (`all = sorted (before ++ l.entries)`), 352-378 (`sortBy sortKey`, the key built by `toStringLossy`, `toLower` and two concatenations)
- Kind: speed
- Severity: medium
- Confidence: confirmed
- What: a folder of N names arriving k at a time is sorted N/k times, each over everything so far: O(N²/k · log N) key comparisons, the keys rebuilt as strings (per element at best, per comparison if `sortBy` does not cache them). `highlightName` then rebuilds `rows` and scans it for each part (542-544, 444-451).
- Scenario: the path is hot per READDIR answer. A mail spool or build-output folder of 50,000 entries at ~100 a part is 500 sorts averaging 25,000 entries each, on the update loop, while the terminal's own output waits. FT32's point 6 ("a remote listing never blocks") is what this breaks.
- Fix: keep the cached entries sorted and merge each (sorted) part in, O(N) a part; store the sort key with the entry when it arrives.

### PS10 · Undo of a host removed or renamed rewrites its table: bookmarks, comments and unknown keys are lost, and hosts added since are deleted
- Where: app/src/SettingsWindow.geng:1414-1446 (`HostsWere`), 238-240 (`fileRead` leaves `undo` as it is); app/src/Schema.geng:1812-1903 (`hostFields` has no `bookmarks`), 1909-1918 (`writeHost`), 1373-1385 (`bookmarks` is read)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: undo puts back each host of the snapshot that is not in the hosts now with `PutHost` (the fields `hostFields` knows), and deletes every host now that the snapshot does not name.
- Scenario 1: rename `web1` to `web2` (done with `renameTable`, which keeps everything), then Ctrl+Z: the effects are `PutHost web1` and `DeleteHost web2`, so `[hosts.web2]` goes with its `bookmarks = [...]` (the folder picker's, FT33), its comments and its sub-tables' comments, and a bare `[hosts.web1]` is written. Remove a host and undo: the same loss. The user guide says the window "keeps your comments".
- Scenario 2: remove host A in the window; add host B to the file by hand (or let another window save one of PuTTY's sessions); Ctrl+Z: B is not in the snapshot, so `DeleteHost B` runs.
- Fix: undo a rename with `RenameHost` back; keep, for a removal, the removed table's text (or its document nodes) and put that back; compute deletions against the hosts as they were *after* the undone action, not against whatever the file holds now; carry `bookmarks` in `writeHost`.

### PS11 · After the keyboard moves the highlight down, the wheel does nothing
- Where: app/src/Picker.geng:2130-2139 (the frame moves `top` to show the highlight but only in its own copy), 1688-1697 (the wheel adds to the model's `top`), 825-833 (`shownRow` only ever scrolls up)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `sceneWith` computes `p = { p0 | top = highlight - visibleRows + 1 }` when the highlight is below the view and throws it away; the model's `top` stays where it was. The wheel then changes the stale `top`, and the next frame overrides it again.
- Scenario: in `/usr/lib` (2,000 rows) press End or hold Down: the list shows row 1,999 but the model's `top` is 0. Wheel up: `top` stays 0, the frame snaps back to the highlight. Wheel down: `top` becomes 3, 6, … with nothing moving until it catches up some 660 notches later. Likewise, click the last visible row and the wheel can no longer scroll up at all (the highlight is pinned to the bottom edge).
- Fix: store the corrected `top` (do the correction in `key`/`listed` with the last known `shownRows`, kept in the model from the last frame or passed in), and let the wheel scroll freely without re-pinning to the highlight.
- Fixed: 2026-11-22. The picker keeps `follow`: the keys moving the highlight set it, the wheel lets go of it, and the frame keeps the highlight in view only while it is set; the wheel starts from where the view is, not from the model's stale `top`. Test: `picker`'s "after End, the wheel scrolls up from the rows shown": before, `top` stayed 0 and the wheel did nothing.

### PS12 · Writing `config.toml`: one fixed temporary name, no lock, a symlink replaced, the mode not kept
- Where: app/src/SettingsFile.geng:42-110 (`beside ".new"` at 60-61, 106-107; `.bak` at 99)
- Kind: bug
- Severity: medium
- Confidence: plausible (the code is as described; the races need two writers within a few milliseconds)
- What: `change` is read, edit, write `config.toml.new`, move over. Nothing serializes writers, the temporary's name is the same for all of them, the file is replaced by rename whatever it is, and nothing is flushed to disk before the move.
- Scenario: (a) Writers are several processes: the settings window, every host list window (PuTTY's sessions saved, `saveRecent`), and each terminal when its picker closes with changed bookmarks (FT33). Two within the read-to-move window: the second's read misses the first's change and its move undoes it (a lost setting or bookmark); if both are between `writeFile` and `move`, they write the same `.new`, and one `move` fails with NotFound ("Not written"). (b) `~/.config/puritty/config.toml` is a symlink into a dotfiles repository (stow, chezmoi): the first change replaces the link with a regular file, and the repository's copy silently stops following. (c) The new file has the umask's mode, not the old file's. (d) A crash or power loss right after the move can leave an empty `config.toml` on filesystems that do not order data before rename; the `.bak` is from the session's first write only.
- Fix: a lock file (or `O_EXCL` on the temporary, with a per-process name) around read-edit-move, with a re-read under the lock; resolve a symlink and write beside its target; copy the mode; fsync the temporary before the move if `os` offers it.

### PS13 · The one-line text field exists five times and they have drifted: an invisible selection, a cut that loses text, no paste
- Where: app/src/SettingsGui.geng:1515-1600 (`typingField`: selection, scroll, both `…`, preedit) and 378-421 (the search field); app/src/Dialog.geng:357-383, 492-516 (the box's field) and 592-633 (`searchBar`); app/src/Picker.geng:2437-2462 (the path bar), 2838-2855 (the new folder's name), 1175-1186 and 1344-1355 (their keys)
- Kind: design (with bugs it has caused)
- Severity: medium
- Confidence: confirmed
- What: SG20 fixed "every text box" in `typingField` only. The others each draw their own:
  - Picker's two boxes take `TextEdit.key`, so Shift+arrows, Shift+Home/End and Ctrl+A make a selection, but neither box draws one. Ctrl+A (nothing shows), then a letter, replaces the whole path. `TextEdit.Copied c -> … Just c.edit` drops `c.text`: Ctrl+C copies nothing, and Ctrl+X deletes the selection without it reaching the clipboard. `PasteAsked -> s`: a path cannot be pasted, the one thing a path box is most used for.
  - Picker's name box has no clip and no scroll: a long name runs out of the box and over the list. Neither Picker box draws an input method's preedit.
  - `Dialog.draw`'s field and `searchBar` do not scroll: the caret is clamped to the right edge (`min typedW (inner - px 20)`) and what is typed past it is not seen, the fault SG20 describes. With `hidden`, the caret is always drawn at the end whatever `caret` is.
  - The settings search field is drawn without a clip: a long query runs under "Modified only".
- Fix: one `field : { box, edit, preedit, hidden, focused } -> Bytes` (and one `fieldHit`) in SettingsGui that all five call; route `Copied`/`PasteAsked` out of `Picker.key` as outcomes the caller serves, as `SettingsWindow`'s effects do.

### PS14 · A text record longer than 65,535 bytes breaks the frame's record stream
- Where: app/src/SettingsGui.geng:110-120 (`u16 (Bytes.length b)`), 126-147; read by packages/text/src/Ext/puritty_text.c:1437-1441
- Kind: bug
- Severity: low
- Confidence: confirmed (the wrap); plausible (what the rest of the frame then does)
- What: the length is written modulo 65,536, so the renderer takes the first `n mod 65536` bytes as the text and parses the remaining text bytes as records: a byte 6/7/8/9 starts a box, text or clip record made of the string's bytes; anything else ends the list there (`return NULL`), dropping everything drawn after it. The parser is bounds-checked, so this is garbage on screen, not memory.
- Scenario: values drawn uncut: a setting's value (`fieldWith t`, 1013-1029: a 70 KB `title`, command or word-boundaries string in `config.toml`), the text before the caret in `typingField` (1577) after a large paste into quick connect, Picker's typed path (2459). `Typed` text is not filtered for control bytes (below), so a paste can carry 0x06-0x09.
- Fix: in `text`/`textIn`, cut the bytes at a character boundary below 65,536 (nothing that long can be seen); cut values with `fit` in `fieldWith`.

### PS15 · A command with a quote in a word does not survive the settings window
- Where: app/src/Schema.geng:1961-1972 (`toText` for `Words`), 2092-2127 (`words`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `toText` wraps a word holding a space in `"` and writes a `"` inside a word as it is; `words` has no escape, so every `"` toggles quoting and is dropped.
- Scenario: `[program] command = ["sh", "-c", "echo \"a b\""]`. The row shows `sh -c "echo "a b""`; add one argument and the whole value is parsed and written back as `["sh", "-c", "echo a", "b", …]`. A word with a `"` and no space (`a"b`) makes every edit fail with "quote not closed" until the user removes it.
- Fix: escape `"` and `\` in `toText` and read the escapes in `words` (and quote a word holding a tab); a test that `fromText (toText v) == v` over words with spaces, quotes and backslashes.

### PS16 · Every pointer event builds the picker's whole frame to find what is under it, and `rows` is rebuilt several times a frame
- Where: app/src/Picker.geng:1636-1640 (`hits = (scene size with p).hits`, for motion too), 1804-1806 (`dropTarget`), 2110-2112 (`scene` formats times with `utcText` only to discard them), 638-665 (`rows`), 670-676 (`rowAt` calls `rows`), used at 900-901, 3038, 1655
- Kind: speed
- Severity: low
- Confidence: confirmed
- What: `sceneWith` lays out and encodes every record (all the `Text.width` and `middle` calls above) and `pointer` keeps only `.hits`; then the frame is drawn again. `rows` copies the whole listing (`Array.map Item`), and with a filter lowercases and decodes every name, on each call: once in `pointer`, once in `sceneWith`, again per `rowAt`.
- Scenario: mouse motion over the box is hundreds of events a second; in a folder of tens of thousands of names with a filter typed, each is several passes over all names plus a full frame's layout, twice.
- Fix: split `hits : Size -> With -> Picker -> Array Hit` out of the drawing (it needs geometry, not text records); compute the filtered rows once per change of entries or filter and keep them in the model.

### PS17 · The settings window measures and draws more than it needs per event, and row positions are quadratic
- Where: app/src/SettingsProgram.geng:560-587 (`measured` before and after `update`) and 379-389 (again in `draw`), 356-370 (every directory event loops to `draw`); app/src/SettingsWindow.geng:2061-2063 (`rowTop` sums from 0 through an `Array.range`), 354-422 (`hostRows`); app/src/SettingsGui.geng:726-733 (`rowY`/`visible` per row), 801, 1120 (`hostRows m` per drawn row), 245-246
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: one key is three `SettingsGui.measure` passes (each wraps every listed row's description word by word with `Text.width`) and a paint; the paint calls `rowTop` three times for each of n rows, each O(i) with an allocation, and for the host list rebuilds `hostRows` (itself O(aliases × hosts)) for every visible row and for `rowCount`. One typed character in a text setting is also a read, parse, three serializations (`toString` twice, `toBytes`), a write and a rename, then a re-read and decode when the watch reports it, and a full redraw for each of the `.bak`/`.new`/move events though `ours` says they are not the file.
- Scenario: unnoticeable for 70 settings; a host list with several hundred `~/.ssh/config` aliases and PuTTY sessions pays O(n²) per key, per click and per wheel step.
- Fix: measure once per change of (listed settings, width, language); keep prefix sums of row lines; compute `hostRows` once per frame; skip `draw` when a directory event is not the file's.

### PS18 · Path completion asks the host again on every keystroke under a link or `~`, and Tab completes from the first eight only
- Where: app/src/Picker.geng:1360-1387 (`peekTyped` tests the cache under the *typed* path), 506-508 (the cache is keyed by the path the host *answered*; PickerSftp answers REALPATH's, PickerSftp.geng:390), 1240-1271 (`found = Array.takeFirst 8 names`), 1326-1335 (Tab's common prefix over `c.found`)
- Kind: bug
- Severity: low
- Confidence: plausible
- What: when the typed folder is reached through a link (`/var/www/` answering as `/srv/www`), or typed as `~/…` before `Home` has come, the listing is cached under another key than `completions` and `peekTyped` look up. No completions show, and since the `Peek` leaves `waiting` when answered, each further character sends another full listing of that folder. Separately, Tab extends to the common prefix of the eight names shown, not of all that match: with nine or more matches the text can be completed past where they agree, hiding the rest.
- Fix: record typed-path → answered-path when a `Peek`/`Go` is answered and look up through it; compute the common prefix over all matches, cut to eight only for display.

### PS19 · The places column does not scroll, and its hidden rows still take clicks
- Where: app/src/Picker.geng:2300-2332 (`placeY i = l.bodyY + i * placeRowH`, hits unclipped), 2535-2538 (drawn clipped)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: places past the column's height (three fixed, a heading and up to five recent, a heading and any number of bookmarks, 24 px each) are cut by the clip and cannot be reached by the mouse or seen when chosen with the keys; there is no scroll. Their hit boxes continue below `bodyBottom`: a click on the status line's left part under the column goes to a bookmark that is not drawn (the footer's buttons win only because they are later in the list).
- Fix: scroll the column with the wheel and with `placeAt`, and clip place hits to the column's box.

### PS20 · The settings window does not settle before reading, keeps a stale error, and never shows a later read's reports
- Where: app/src/SettingsProgram.geng:738-784 (`fileChanged` reads at once); app/src/SettingsWindow.geng:238-240 (`fileRead` sets `reports`, which nothing reads after `init`, and leaves `message`); against app/src/SettingsSource.geng:55-59 (`reloadDelayMs`, the terminal's 50 ms)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: an editor's save in several writes is read mid-way: "… is not TOML" is put at the foot by `told`, and the good read that follows does not clear it, so the error stays until the next key. A hand edit that decodes with problems (an unknown key, a value out of range) updates `m.reports` only: the window shows nothing, where the terminal puts it on its title. `Model.reports` is otherwise dead state.
- Fix: share the terminal's delay (it is in `SettingsSource` for that); in `fileRead` set the message from the reports as `init` does, and clear a file error once a read succeeds.

### PS21 · Pasted and committed text is not filtered for control characters
- Where: app/src/SettingsWindow.geng:662-679 (`Pasted` → `oneLine` → `Typed` → `insert`), app/src/TextEdit.geng:197-202 (`oneLine` handles tab, CR and line ends only), against 264-266 and SettingsWindow.geng:1209-1211 (`printable`, applied to keys)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: a key's text must be `printable`; a paste or an input method's commit is inserted as it is, so ESC, NUL, BEL, C1 and bidirectional controls go into the title, a host's name, a command or the quick connect line, are written to `config.toml`, shown in the list, and (for quick connect) passed as an argument to the spawned puritty.
- Fix: drop characters below 0x20 and 0x7F-0x9F in `oneLine` (or in `insert`).

### PS22 · A dialog cuts its lines instead of wrapping them, and a tall one puts its buttons off the window
- Where: app/src/Dialog.geng:486-490 (`fit body inner line` for the title and every line), 172-193 (`bh` grows with the lines; `by = max 0 …`), 233 (`buttonY = by + bh - pad - buttonH`)
- Kind: design
- Severity: low
- Confidence: plausible (depends on what callers pass; the callers are in `Main`, not in this slice)
- What: each line is cut at the box's inner width with `…` at its end, so the end of a long path, file name or fingerprint in a question is not shown, and the end is where paths differ. The box's height is not held to the window's: enough lines put the hint and the buttons below the bottom edge, answerable by key only. Text is drawn as given: nothing here strips control or bidirectional characters from names a host or a dropped file supplies.
- Fix: wrap lines (SettingsGui's `wrapAll` is there) and cut a path in its middle; cap the lines to the window with "and N more"; sanitize in one place before `text`.

### PS23 · The terminal scrollbar's arithmetic overflows `Int` with a very long scrollback
- Where: app/src/Dialog.geng:793-794 (`room * clamp 0 v.most v.back`), 757 (`v.most * (p.y - g.top - g.thumbH // 2)`)
- Kind: bug
- Severity: low
- Confidence: plausible (what an overflow does natively was not checked)
- What: both are products of a pixel count (up to ~2,000 on a tall window) and a row count. `scrollback.lines` goes to 10,000,000 (Schema.geng:503); past roughly 1,000,000 rows of history the product passes 2³¹.
- Scenario: a user with a multi-million-line scrollback, scrolled far back: the thumb is drawn at a wrong place, and a click on the bar jumps to a wrong row.
- Fix: divide first or compute in `Int64`/`Float` (the `little`/`bounded` treatment Picker has).

### PS24 · Strings outside the translation table: the whole picker, the search bar's placeholder, the settings' units
- Where: app/src/Picker.geng:889-907, 1156, 1168, 1315, 1597-1622, 2159-2175, 2349-2355, 2616-2617, 2649-2651, 2701-2704, 2823-2829, 2849-2852, 2943, 2964, 3002-3005, 3163-3169; app/src/Dialog.geng:628 (`"Search"`); app/src/SettingsGui.geng:997-1011 with app/src/Schema.geng:176-593 (`unit = "cells"`, `"lines"`, `"pt"`, `"ms"`, `"MB"`)
- Kind: design
- Severity: low
- Confidence: confirmed
- What: the settings window goes through `Words` (English and Korean); the picker's every string is a literal, with plurals built by hand (`"1 item"`/`" items"`, `" and 1 more"`), and `placeHeading` tells a heading from the "Ctrl+D adds this folder" hint by comparing the label to `"Recent"`/`"Bookmarks"`, which a translation would break. The units after a number in the settings window are the schema's English words in the Korean window ("25000 lines").
- Fix: `Picker.draw` takes the language (or a record of its words) as SettingsGui does; give `PlaceRow` a kind instead of comparing labels; add `unit.*` keys to `Words`.

### PS25 · Renaming a host leaves what names it pointing at the old name
- Where: app/src/SettingsWindow.geng:1460-1499 (`RenameHost` and the model's hosts only)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: other hosts' `jump = "old"`, `start = "host:old"`, and `Recent.Saved "old"` in `m.recents` and in the recents file are not touched. The recent row stays in the list as "as ~/.ssh/config has it" and Enter on it runs `--host old`.
- Fix: on rename, rewrite `jump` and `start` where they name the host, and map the recents.

### PS26 · `docs/user/settings.md` shows a file that leaves out settings no other user page names
- Where: docs/user/settings.md:27-93 ("The file"), 119-138 (hosts); against app/src/Schema.geng:340, 412, 448, 466, 484, 520, 916, 1294-1296, 1414-1417
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: every key the page documents exists in `Schema` with the documented name, values and default (checked: `[window]`, `[font]`, `[sound]`, `[colors]` and all sixteen scheme names against `Palettes`, `[terminal]`, `[scrollback]`, `[selection]`, `[mouse]`, `[clipboard] osc52_read`, `[files]`, `[images]`, `[debug] log`, `start`, `[connections]`, and the host keys). The reverse fails for keys documented nowhere under `docs/user/`: `font.glyph_cache_mb`, `colors.bold_is_bright`, `cursor.blink_ms`, `frames.every_ms`, `frames.sync_timeout_ms`, `program.command` (the page says "the program" is taken by new windows but never gives its key), `keys.mark_log`, and for a host `title`, `paste_folder`, `[hosts.NAME.font]` (`family`, `size`), `colors.foreground` and `colors.palette`. The page presents the block as "The file" with no word that it is a selection, and gives no ranges (`font.size` 4-200, `recent` 0-50, `padding` 0-72, `scrollback.lines` 0-10,000,000).
- Fix: generate the block from `Schema.example` (which a test already holds to the table), or say it is a selection and point at the settings window's search for the rest.

### PS27 · Test gaps that matter
- Where: app/tests/src/AppSuites.geng, app/tests/src/PickerTests.geng, harness/store.py
- Kind: test-gap
- Severity: low
- Confidence: confirmed (by searching the suites for the cases; the suites were not run)
- What: no test presses Enter in the font box without Down first (the first finding), clicks away from quick connect with text in it (the second), types through a default under Modified only, sets a color beside a scheme, or undoes a rename and looks at the file's comments and `bookmarks`. `PickerTests` has no case of two requests for one path, of a non-UTF-8 `With` (sorting, filtering), or of the wheel after End. Nothing runs two `SettingsFile.change` at once.
- Fix: add those cases with their fixes; `With` for EUC-KR can be a table of two names in the test.

---

## Looked at and found sound

- **Schema's decoder**: an unknown key, an unknown table, a wrong type, a value out of range and a bad enum are each reported with a line and the default kept; a host with no `host` is left out with a report; hosts' sub-tables take only their keys; the scheme is applied before the keys so file order does not matter (ST29). A file that is not TOML is refused whole, at a start and at a reload, as ST17 says. `suggest`/`distance` are correct (the refinements hold the row lengths).
- **Ranges and enums** agree between the file's reader (`read`) and the window's (`fromText`) for every kind; an `Address` cannot be written empty (ST25's fix holds).
- **Writing back**: `Toml.Edit.set`/`remove` in place, the emptied-table rule with a header comment (ST18), nothing written when no byte changes, a non-UTF-8 or non-TOML file refused rather than overwritten, the `.bak` once a store. Inside one process writes are strictly serialized (`handle` and `input` chain tasks), so the window's own writes cannot reorder.
- **File watching**: the directory is watched, events for other files are ignored, `Lost` re-reads, `Gone` stops the wait without spinning; the terminal-side reload ordering is in `Main` (another slice).
- **Modal states**: every one can be left with Esc: a choice list, typing, a host's form (also when its host vanished by a hand edit), the picker's path box, name box and breadcrumb menu, and the picker itself while a listing never answers (`Cancelled` is not gated on `going`; only Send is). Send is refused while a listing is in flight, so the folder named is the one shown.
- **Picker paths**: `parts`/`joined`/`under`/`parentOf`/`normal` handle trailing and doubled slashes, `.` and `..` (not above `/`); `~` is expanded from the host's `Home` or left to the host; a new folder's name may not be empty or hold `/`; a name the host's charset cannot write is refused with a message. `rowAt` guards the negative index. The destination is the folder you are in, never the highlight, as FT32 decided.
- **Dialog**: `layout`'s button places match `buttonAt`; `swatchAt`, `checkAt`, `noteBarAt` agree with what `draw`/`noteBar` draw; `contrast` is the usual luma test.
- **The renderer's record parser** (`ui_record`) bounds-checks every record, so the encoding faults above cannot read out of the frame.
- **Preedit splice** in `SettingsProgram.one` clamps the server's `first`/`length`.
- **i18n in the settings window**: labels, descriptions, choices, hints, problems and messages all go through `Words` with the English as fallback; the file's reports are English by decision (`inEnglish`).
- `PickerDemo` is a test double only reached by `--try-folder-picker`; nothing wrong found in it.

## Not covered

- How `Main` drives `Dialog` and `Picker` (which lines it passes, how it edits a dialog's field, whether an input method's commit reaches the picker, how bookmarks are written at close): `Main.geng` is another slice. The Dialog findings marked plausible depend on it.
- `PickerSftp.geng` beyond confirming that listings run concurrently by id and answer REALPATH's path.
- `Chord.parse`, `Hosts.quick`/`Hosts.spec`, `Words.geng`'s tables (only grepped), `Toml.Edit` (gren-toml), `Window.raise` (whether one settings window is found by title or by class).
- `docs/settings-ui.md` and the parts of `docs/settings-gui.md` before SG20 were skimmed by heading, not read line by line.
- Nothing was run: no build, no tests, no gates.

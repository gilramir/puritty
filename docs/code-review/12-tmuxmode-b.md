# Review 12: app/src/TmuxMode.geng, lines 8600 to 17377

Slice: the second half of `app/src/TmuxMode.geng` (pointer shapes and selection,
the tab bar and tmux's status line, pane borders, running bindings and menus,
display-panes, popups, choose-buffer/choose-client, customize-mode glue,
choose-tree and its preview, the clock, copy mode's state, views, file drops,
drags and mouse reports). Lines in the first half are cited where a call from
this half was traced into them. Nothing was built or run; tmux's own behaviour
is cited from its source as remembered and is marked `plausible` where the
finding rests on it.

---

### TB1 · A click or the wheel over a pane in copy mode sends mouse bytes and arrow keys into copy mode's key table
- Where: app/src/TmuxMode.geng:8056-8078 (`pointerHere`, `takesMouse`), 8755-8762 (`paneTakesMouse`), 17304-17363 (`report`), 8802-8844 (`selecting`, the alternate-screen wheel), 9280-9286 (`bytesTo`)
- Kind: bug
- Severity: high
- Confidence: plausible (the code path is confirmed; what tmux does with the bytes is from `cmd-send-keys.c` as remembered, not run)
- What: whether a pointer event is the program's is decided only by the pane's own terminal state: `paneTakesMouse` is `(Vt.mouseModes t).tracking /= Mouse.none`, and `report` encodes the event and sends it with `sent (bytesTo s.caps q.id r.bytes)`, i.e. `send-keys -H -t %N …`. Nothing on this path asks `inCopy q.id s`. The wheel branch of `selecting` likewise sends `ESC [ A` three times when `t.alt` is set, with no copy-mode test. `send-keys` to a pane that is in a mode does not reach the program: `cmd_send_keys_inject_key` looks each key up in the mode's key table and runs its binding.
- Scenario: vim (mouse on) or htop in a pane; `prefix [`; the user turns the wheel or clicks. puritty sends `1b 5b 3c 36 34 3b …4d` as keys. With `mode-keys emacs` (tmux's default) `Escape` is `send -X cancel`: copy mode ends and the rest, `[<64;10;5M`, is typed into vim. With `mode-keys vi`, `Escape` clears the selection, the digits become a repeat count, `;` is jump-again and `M` is middle-line, so the copy cursor jumps. On the alternate screen without mouse tracking (less, man) the wheel's `ESC [ A` does the same: `A` in copy-mode-vi is `append-selection-and-cancel`.
- Fix: in `pointerHere`, treat a pane with `inCopy q.id s` (or any `paneModes` entry) as not taking the mouse and not getting wheel arrows; give copy mode what tmux's own bindings give it (`send-keys -X -t %N scroll-up`/`scroll-down` for the wheel, or nothing), then `askCopy`.
- Fixed: 2026-11-21. Checked on tmux 3.8: an SGR wheel report sent with `send-keys -H` to a pane in copy mode ended copy mode with `mode-keys emacs` and ran copy-mode commands with `vi`. In `pointerHere` a pane in copy mode (`inCopy`), without Shift, is sent no report and no arrows: the wheel is `send-keys -X -N 5 scroll-up`/`scroll-down` (`Command.copyScroll`, as every tmux from 2.7 binds it), then `askCopy`; a press or drag is puritty's selection. Test: "the wheel over a pane in copy mode scrolls copy mode", on each tmux; `docs/tmux.md` TM107.

### TB2 · The wheel and Shift+PgUp scroll puritty's view of a pane in copy mode, which tmux's copy mode does not follow
- Where: app/src/TmuxMode.geng:8846-8859 (`selecting`, wheel), 17143-17177 (`scrollKey`), against 16332-16386 (`copyLine`) and 4916-4925 (copy cursor in `paint`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: both write `s.back` for the pane (`none { s | back = Dict.set q.id next s.back }`) whatever mode the pane is in. In copy mode `back` is owned by tmux's answer: `copyLine` sets `back = Dict.set pane (min most c.scroll) …`, and the cursor, the `[N/M]` mark and the selection spans are all drawn from `Copying` (`place.value.y + c.cy`), not from `back`.
- Scenario: `prefix [`, then three wheel steps. The pane's text moves 9 rows; the copy cursor, the `[0/200]` mark and any selection stay where tmux has them, so the highlight covers the wrong text. The next key or line of output asks tmux (`askCopy`) and the view snaps back.
- Fix: in copy mode turn the wheel and the scroll keys into copy-mode commands and re-ask, or ignore them; never write `back` for a pane that has a `copy` entry.
- Fixed: 2026-11-21, the wheel over a pane in copy mode is copy mode's own scroll (TB1); 2026-11-23, Shift+PgUp, PgDn, Home and End leave a pane in copy mode to tmux (`docs/tmux.md` TM117). Test: on each tmux, Shift+PgUp in copy mode is not puritty's scroll; before, it was.

### TB3 · A size sent after a status-line change is not put in the reply queue, so the replies after it go to the wrong questions
- Where: app/src/TmuxMode.geng:4240-4253 (`notice`, `SubscriptionChanged`; first half, found tracing `resized` at 17367 and `ours` at 2623-2661)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: every other command goes through `sent`/`ask`/`sendAsking`/`expectedLine`, which push an `Asked` on `s.expecting`; `ours` pops the head for each reply block. Here `resize = [ sizeCommand … ]` is appended with `commands = acc.commands ++ resize` and nothing is pushed. tmux answers `refresh-client -C` with a `%begin`/`%end` block like any other command.
- Scenario: `set -g status 2` (or `status off`) while anything is in flight (a copy-mode question, the 1 s polls before 3.2, a key's `send-keys`). The empty reply to the size pops the next expectation, and every reply after it is read as the answer to the question before its own until the queue happens to run empty: a `ForWindow` gets no lines, a capture's text is read as a layout, and so on.
- Fix: send it with `ask [ { command = …, expect = ForNothing } ]`. Worth an assertion in the tests' fake tmux that every line written has an `Asked`.
- Fixed: 2026-11-22: TA5's fix.

### TB4 · A popup's title is expanded twice, the second time as `pane-border-format`
- Where: app/src/TmuxMode.geng:11323-11339 (`openPopup`), packages/tmux/src/Tmux/Command.geng:776-778 (`setPaneFormat`, `set-option -p -F`)
- Kind: security
- Severity: medium
- Confidence: plausible (not run against tmux 3.8)
- What: `display-popup -T` takes a format that tmux expands once and then draws. puritty sends `set-option -p -F pane-border-format '<title>'`: `-F` expands the title once and stores the result as the pane's `pane-border-format`, which tmux expands again every time it draws the border and every second for puritty's own subscription `puritty-ptitle:%*:#{T:pane-border-format}`.
- Scenario: a binding `display-popup -T '#{pane_title}' …` (or `#{pane_current_path}`, `#{window_name}`). A program in the pane sets its title to `#(touch /tmp/x)` or to `#{…}` text; after the first expansion that text is the stored format, and tmux runs the `#()` job on the tmux host. Under a plain tmux client the same binding only shows the text. Without an attacker, a title that contains `#` is drawn wrongly.
- Fix: ask tmux for the expanded title (`display-message -p`, as menus do), double every `#` in the answer, and set it without `-F`.
- Fixed: 2026-11-24, `docs/tmux.md` TM121. The title is set without `-F` (`Command.setPaneFormatUnexpanded`), so tmux expands it once, at each draw. Test: TmuxTests "a popup's -T title is set as a format tmux expands once": before, on 3.8, `set-option -p -F pane-border-format '#{pane_title}'`. Measured on tmux 3.8: a directory named `a#{session_name}b` was drawn `a0b` with `-F`, as itself without (3.8 turns `#` in a pane title into `_`, so the title example does not apply there).

### TB5 · customize-mode's filter is sent through `display-message` without `%` doubled, and is longer than strftime's buffer
- Where: app/src/TmuxMode.geng:12436-12440 (`customizeFilterAsk`), packages/tmux/src/Tmux/Customize.geng:1827-1850 (`filterFormat`, `literal`)
- Kind: bug
- Severity: medium
- Confidence: plausible
- What: one `display-message -p` carries `#{?<filter with this row's values written in>,1,0}` for every row (several hundred options, keys and variables). Everywhere else a format given to `display-message` goes through `noTime` (`%` to `%%`), because `display-message` gives the whole string to strftime first (docs/tmux-versions.md TV10); here it does not, and `literal` escapes `#`, `,` and `}` but not `%`. tmux's `format_expand1` runs strftime into a `char expanded[8192]` whenever the format holds a `%` and answers the empty string when it does not fit.
- Scenario: `f` with a filter that names `#{option_value}` or `#{key_command}`: `status-right`'s `%H:%M %d-%b-%y` and the default bindings' `%%` are written into the format, so it holds `%`, it is far over 8192 bytes, tmux answers nothing, `customizeFiltered` reads no `1`s and shows "no matches" with every row. A short filter with a `%` of its own is changed by strftime before it is compared.
- Fix: `noTime` the whole format, and send it in pieces that stay under 8 KB (several `display-message`s on one line, answers joined), or use a command that does not call strftime.
- Fixed: 2026-11-24, `docs/tmux.md` TM122. The filter is asked with `list-panes -t PANE -F` (no strftime), this pane's line chosen by `#{?#{==:#{pane_id},PANE},=…,}` (`Customize.filterQuery`, `filterAnswers`). Measured on tmux 3.8, a 10,523-byte format with one `%`: `display-message` answered nothing (with `%` doubled too), `list-panes` all 301 answers. Test: Customize "the filter is asked with list-panes".

### TB6 · Text from tmux is written into the canvas terminal with its control characters
- Where: app/src/TmuxMode.geng:16772-16787 (`drawText`), 14255-14286 (`clipCells` keeps characters below 0x20 as zero-width), 9732-9737 (`laidRuns`), 15373-15376 and 15424 (tree rows), 11961 (list rows), 10677 (menu items); 4634 (`said`), 4623-4626 (prompt label)
- Kind: security
- Severity: medium
- Confidence: plausible
- What: the canvas is a `Vt.Term` and everything is drawn by `Vt.feed (… color ++ p.text ++ ESC[0m)`. Only `viewOf`, the buffer preview and customize-mode pass text through `shownLine` first. The status line's parts, window texts, tree rows, list rows, menu names, `%message` text and prompt labels go in as tmux sent them. tmux escapes control characters in some values (window and session names, buffer samples) and, in newer releases, in what a command prints, but `%subscription-changed` values and, on the older targets (3.2a, 3.3a), `list-*`/`display-message` output are raw.
- Scenario: `status-left '#{b:pane_current_path}'` (very common) and a directory whose name holds `ESC ( 0`, `ESC [ ? 1049 h` or `ESC [ 4 h`; or a process name with such bytes in a tree row on tmux 3.2a. The sequence runs in the canvas. `paint` starts each frame with only `ESC[?7l ESC[0m ESC[H ESC[2J`, so a charset, insert mode, margins or the alternate screen stay set and the whole window is drawn wrongly until control mode ends. An OSC 52 or OSC 8 in such text is queued in the canvas on every frame; only `takeReplies` is drained, so `takeClipboard`'s and `takeNotices`' lists grow without bound.
- Fix: make `drawText` (or one `piece` constructor) the single place that maps C0, DEL and C1 to spaces, as `shownLine` does; reset the canvas's modes at the start of a frame (`Vt.restarted` or RIS) rather than SGR and ED only.
- Fixed: 2026-11-23, `docs/tmux.md` TM118. `drawText` writes control characters as spaces (`inert`). Test: a status-left with ESC(0 on each tmux: before, the line-drawing charset ran (`L──`).

### TB7 · An unknown tmux version (0) is taken as the newest by some gates and as the oldest by others
- Where: app/src/TmuxMode.geng:5654-5684 (`versionOf`); newest: 10885, 11062, 11073, 11342, 12178, 12706, 12927, 13135, 13996, 14306, 14708, 14869, 15213, 15379, 16239 and about fifteen more `version == 0 ||`; oldest: 11491 (`listSortNames`), 13737 (`sortNames`), 15144 and 15264 (`drawTree`)
- Kind: bug
- Severity: medium
- Confidence: confirmed for the inconsistency; plausible for OpenBSD
- What: `versionOf` gives 0 "for what is not a version", and stays 0 until `#{version}` is answered. About thirty tests read `s.version == 0 || s.version >= 38`, a handful read `version >= 38` alone, so at 0 the tree is drawn with 3.8's coloured rows but 3.6's `>` arrow, three sort names and no `(view: preview)`.
- Scenario: OpenBSD's base tmux reports `openbsd-7.x`; `String.split "."` gives `["openbsd-7","x"]`, `digits "openbsd-7"` is empty, so 0 for the whole session. puritty then sends 3.8's `new-pane -O` for a popup, asks 3.8's theme formats, reads customize-mode's keys two ways (`customizeAsk` goes by `Caps.has "list-keys" "F"`, `customizeGot` by `s.version == 0 || >= 37`, so a tmux without `-F` has its text listing parsed as the format's), and so on.
- Fix: one `atLeast : Int -> State -> Bool`; for a version that does not parse, estimate it from `caps` (already read from `list-commands`) rather than assuming the newest; use `Caps` in both customize functions.
- Fixed: 2026-11-23, `docs/tmux.md` TM111. A `#{version}` that does not parse is estimated from the caps (`versionFrom`, `estimated`): the oldest recorded tmux with every mark it has, so it is never 0 once tmux has answered; `customizeGot` goes by `Caps` as `customizeAsk` does. Test: on each tmux, its `list-commands` with `openbsd-7.6` gives its own version; before, 0. The thirty `version == 0 ||` tests are left, now reached only before the answer.

### TB8 · choose-buffer's and choose-client's rows are asked with 3.2's format on every tmux
- Where: app/src/TmuxMode.geng:11407-11413 (`listQuery`)
- Kind: bug
- Severity: low
- Confidence: confirmed that the text is wrong before 3.2; plausible for what tmux shows there
- What: the row text is `#{t/p:buffer_created}: #{buffer_sample}` and `#{t/p:client_activity}: session #{session_name}` with no version test. docs/tmux-versions.md TV10: `t/p:` is from 3.2, "before, `#{op:…}` is empty".
- Scenario: RHEL 8's tmux 2.7 (a named target), `prefix =`: every row reads `buffer0: : text`. tmux 2.7 to 3.1 show the size and the full time (`N bytes (time): sample`; a client as `session NAME (WxH, time)`). The tree's rows have four forms by version (`treeQueries`), these have one.
- Fix: the pre-3.2 formats from those releases' `window-buffer.c` and `window-client.c`, chosen as `treeQueries` chooses.
- Fixed: 2026-11-26, `docs/tmux.md` TM140. `listQuery` takes the version: before 3.2 the rows are asked in 2.7's and 3.0's own formats (size and time). App suite test.

### TB9 · Before tmux 3.2 the status line is asked with 21 commands a second, whether or not the last second's were answered
- Where: app/src/TmuxMode.geng:10999-11004 (`tick`), 9327-9367 (`pollsFor`, `pollOf`), 9295-9318
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: each due tick sends one line per subscription (`commands = Array.map .command asked`, `expected asked …`): 13 `display-message`, 3 `list-windows`, 5 `list-panes -s`; on 2.7 and 2.8 the time formats cost a second round trip each (`ForRawOptions`). `pollAt` is moved on without looking at `s.expecting`.
- Scenario: RHEL 8 over a slow or stalled ssh link: 21 lines a second are queued for as long as the stall lasts, `s.expecting` grows by 21 a second (`s.expecting ++ asked`, then `Array.dropFirst 1` per reply), and tmux's own message log (`show-messages`) fills with them. On a healthy link it is 21 round trips and 21 reads a second for an idle window.
- Fix: one line (`askLine` joins with ` ; `, one line number), the session-scope formats merged into one `display-message` with tabs as `puritty-opts` already is, and no new poll while the last one's replies are outstanding.
- Fixed: In part, 2026-11-27, `docs/tmux.md` TM147. No new poll while the last is unanswered. Left: the poll as one line, and the session's formats merged.

### TB10 · Work done again on every frame while a mode is open or a search is marked
- Where: app/src/TmuxMode.geng:16274-16315 (`searchMarks`: `(colorsOf s.status)` per match), 4707 and 4778 (`colorsOf` per pane), 4545 with 4789 and 10524 (`tmuxBar` built two or three times a frame), 15087 with 15007 (`treeRows` twice, each sorting three lists and filtering all windows per session and all panes per window), 15381-15421 (`Style.themed`, 20 `String.replace`s, per piece per row), 13137 with 12325-12331 (`Customize.entries` and `lines` for every option, key and variable), 12019-12020 (`shownLine` over each preview line's whole length)
- Kind: speed
- Severity: medium
- Confidence: confirmed (by reading; not measured)
- What: `paint` runs for every frame under control mode (`Main.geng:8566`), so once per read of pane output. `colorsOf` parses twelve styles; `searchMarks` calls it for each match on screen, and `modesDrawn`/`numbersDrawn` once per pane. `drawCustomize` rebuilds all the rows (several hundred) to show forty. `drawListing` runs `shownLine` (a `String.toArray` and a `pushLast` per character) on the full text of each of the first lines of the chosen buffer before cutting it to the box.
- Scenario: copy mode with a search for `e` marked on a 200 by 60 pane while another pane scrolls `make` output: hundreds of `colorsOf` per frame. choose-buffer with a buffer whose first line is 1 MB (a copied minified file) while any pane prints: megabytes walked per frame.
- Fix: compute `colorsOf s.status` once in `paint` (or keep it in the state when the status changes, as `status` is kept beside `rawStatus`) and pass it down; build `tmuxBar` once and take `hits` from it; keep the tree's rows and customize-mode's shown lines in their records, rebuilt when their inputs change; cut a preview line to the box's width before sanitising it, or sanitise once in `ForListPreview`.
- Fixed in part: 2026-11-24, `docs/tmux.md` TM125. `paint` makes tmux's colors and its bar once a frame; a preview line (choose-buffer, the tree) is cut to what can fill the box before it is sanitised. Test: choose-buffer over a 1,000,000-character first line, thirty frames: 3,361 ms on node before, 109 ms now. Not done: the tree's and customize-mode's rows kept in the state (a change to the state's shape, left for the restructuring).

### TB11 · Clipping and padding by characters where the neighbours go by cells
- Where: app/src/TmuxMode.geng:15492 (tree rows before 3.8 and in puritty's look: `String.padRight width ' ' (String.takeFirst width …)`) against 15424 and 15439 (`clipCells`); 11961 (list rows); 10474-10490 and 10677 (menu width and rows); 9018, 9154-9157, 9724, 9735, 9790-9843 (tab bar and status line, `String.count`); 16624 and 16745 (views)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: docs/tmux.md TM29 lists "a wide character counts one cell in the line's layout" as not yet done for the status line. The same has spread: 3.8's tree rows, the preview and customize-mode cut by cells (`clipCells`, `cellCount`), while the older tree rows, choose-buffer's rows, menus and views cut by characters. Autowrap is off, so an over-long row is not wrapped but runs on to the right.
- Scenario: a Korean window name or buffer sample (the EUC-KR users the project names) in `choose-tree` on 3.4, or in a non-zoomed `choose-buffer` in the left pane: each row is up to twice the pane's width and is drawn over the pane to its right; a menu's right border sits inside its items; a click on the tab bar after a wide name selects the wrong window (`hits` are character offsets).
- Fix: one pair of helpers, cut-to-cells and pad-to-cells, used by every row; `laidRuns` and the bar's `hits` advanced by `textCells`.

### TB12 · The loop's time in the state is stale on every path but a key and a tick
- Where: app/src/TmuxMode.geng:10166 (`numbers.until = Clock.after s.clock …`), 3725 (`ForDayTime`: `{ clock = st.clock, ms = day * 1000 }`), 3123 (`pollAt = Clock.after st.clock pollMs`), 16071-16073 (`dayNow`); `s.clock` is written only at 5415-5444 and 10978-10984
- Kind: bug
- Severity: low
- Confidence: plausible (it shows only when no other timer of Main's has ticked lately, e.g. cursor blink off or the window unfocused)
- What: `pointer`, `read` and `dragOver` do not set `s.clock`; `tick` runs only on a `Due` event. Code on those paths uses `s.clock` as now.
- Scenario: (1) attach to a session one of whose panes shows `clock-mode`: the reply to `D %H %M %S` is stamped with the last tick's time, 0 in a fresh state, so `dayNow` adds the whole of `Clock.since 0 ms` and the clock shows an arbitrary time for the session (`tick` carries the error forward). (2) `display-panes` chosen from a menu with the mouse minutes after the last key: `until` is already past, and the numbers are closed at the first tick before they are answered. (3) On tmux before 3.2, `pollAt = after 0 1000` is "not reached" for up to 6.2 days when the loop's clock is in the far half of its period (`Clock.since`), so the status line is never polled.
- Fix: give `read` and `pointer` the time (Main has `ms` at both call sites) and set `clock` there; or stamp such values with a "from the next tick" marker, as `strayUntil = -2` already does.
- Fixed: 2026-11-26, `docs/tmux.md` TM145. Main gives TmuxMode the loop's time before a read, a pointer's event and a drag (`clockedAt`). No test fails on the old code (the tmux tests feed reads without the loop's time).

### TB13 · A pane that closes leaves its mode behind, and a clock left behind keeps the timer and the repaint going
- Where: app/src/TmuxMode.geng:10925-10939 (`dueAt`), 16319-16327 (`forgetPane`, called only from `ForCopy` at 3737), 3984-3986 (`modeLine` sets, nothing removes)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `paneModes`, `modes`, `back`, `copy` (and `info`, `scans`, `status.panes` in the first half) are keyed by pane id and pruned only when a copy-mode question comes back empty. `dueAt` asks `Array.any (\m -> m == "clock-mode") (Dict.values s.paneModes)`, over every pane ever seen, shown or not.
- Scenario: `clock-mode` in a pane, then `kill-pane -t` it from another pane, or its window is closed. tmux sends no `%pane-mode-changed` for a pane that is gone, so the entry stays `clock-mode`: `dueAt` wakes the loop every minute (every second with `clock-mode-style 24-with-seconds`) and `tmuxTick` sets `urgent`, a full `paint`, until control mode ends. `dayAt` is never cleared either.
- Fix: call `forgetPane` for every id that leaves `s.ids` in `applyLayout`/`ForPanes` (and drop the other per-pane maps there); have `dueAt` look only at panes in the layout shown.
- Fixed: 2026-11-26, `docs/tmux.md` TM142. `clockAt` looks only at the panes of the window shown; the maps by pane were already pruned by TM110's `forgetGone`. App suite test on six versions: a hidden clock was due in 60,000 ms before, none now.

### TB14 · A mode puritty draws outlives its pane and its window, unseen but still taking the keys
- Where: app/src/TmuxMode.geng:4709-4772 (`area` is `Nothing`, nothing drawn), 5689-5712 (`modePlace`), 5433-5441 (keys still go to the mode), 12658-12666 (`customizeArea`), 14094-14108; `notice` (4051-4275) closes none of `tree`, `listing`, `customizing`, `menu`, `numbers`
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: the tree, the lists, customize-mode and menus are puritty's own state; tmux does not know of them and puritty closes them only on a key. Without `-Z` they are drawn in `pane`; when that pane is no longer in the layout `modePlace` is `Nothing` and nothing is drawn, but `typedHere` still gives every key to `treeKey`/`listKey`/`customizeKey`.
- Scenario: `:choose-tree` (no `-Z`), `x` on the row of the pane the tree is in, `y`: the pane is killed, `reloadTree` keeps the tree with `pane` gone, and typing does nothing visible until `q` or Escape happens to be pressed. With `-Z`, a click on another tab or another client's `select-window` leaves the tree drawn over the other window. The lists are also not asked again on `%sessions-changed`, `%window-add` or `%paste-buffer-changed`, so Enter can name a target that is gone.
- Fix: in `applyLayout`, close a mode whose pane has left; on `SessionWindowChanged`/`SessionChanged` close or re-anchor it; on the notices that change a list, `reloadTree`/`listRun []`.
- Fixed: In part, 2026-11-26, `docs/tmux.md` TM146. `applyLayout` closes the tree, a list, customize, a menu or the numbers whose pane left the layout. Left: lists not asked again on the notices that change them. App suite test on six versions.

### TB15 · The mouse's word and line are left on the pane as user options
- Where: app/src/TmuxMode.geng:10050-10068 (`runHeld`), 10073-10079 (`mouseNames`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: every right click on a pane whose binding names `mouse_` sends `set-option -p -t %N @puritty_mouse_word '…'` and `@puritty_mouse_line '…'` and never unsets them.
- Scenario: after one right click the pane carries a line of its screen as an option for its lifetime: it shows in `show-options -p`, in puritty's own customize-mode under the pane's options, to every other client, and in what session-saving plugins write to disk. A line with a password typed at a prompt is kept there.
- Fix: `set-option -pu` both when the menu closes or its item has run (on the same line as the command), or expand `#{mouse_word}`/`#{mouse_line}` in puritty before sending rather than parking them in tmux.

### TB16 · FT11's first rule lets a nested host's OSC 7 name a folder on tmux's host
- Where: app/src/TmuxMode.geng:17054-17067 (`dropFolderOf`); docs/sftp.md FT11 rule 1 (lines 1588-1589)
- Kind: security
- Severity: low
- Confidence: confirmed (it is the decision as written; reported as a doubt about the decision)
- What: `shellSaid` is taken when the URI's host is empty, `localhost` or tmux's host, and it is taken before `blindCommands` is looked at.
- Scenario: the pane runs `ssh other`; the remote shell's prompt prints `ESC ] 7 ; file:///srv/www` (an empty host is what many hand-written prompts send) or `file://localhost/…`. tmux keeps it as `pane_path`; the drop's label says `Drop into /srv/www` and the files go to that path on tmux's host, where rule 2 would have said "the pane runs ssh, whose folder tmux can't see". A hostile remote can aim it at any folder it can guess.
- Fix: when `pane_current_command` is one of `blindCommands`, accept OSC 7 only with tmux's own host name spelled out, not empty or `localhost`.
- Fixed: 2026-11-26, `docs/sftp.md` FT48. In a pane running a command of `blindCommands`, OSC 7 is taken only when it names tmux's host. App suite test: before, an unnamed or localhost URI under ssh gave a folder.

### TB17 · The three modes are three `Maybe`s, and their kinds are bare `Int`s
- Where: app/src/TmuxMode.geng:226-247 (`tree`, `listing`, `customizing`), 168-188 (`asking`, `view`, `menu`, `numbers`); the same three-way `when` at 4556, 5433, 8107, 8238, 8398, 8560, 8577; `purpose : Int` (1-5, 11, 12, 21-24: 5382, 11851, 13016, 13625-13662), `Drag.kind` 0-7 (8615-8667, 17213-17249), `previewMode`, `sort`, `start`, `Sel.mode`, `ending`
- Kind: design
- Severity: medium
- Confidence: confirmed
- What: `runLine` opens a list or customize-mode without closing a tree (10129-10139), so two can be open; each of seven dispatch sites orders them tree, list, customize by a record pattern, and the second shows only when the first closes. A prompt's meaning is its `purpose` number, compared in four places with no exhaustiveness check; `promptKind` (5382) must list the search purposes by hand.
- Scenario (cost): adding a purpose or a mode means finding every `when`; `treeAnswered` falls through to "a filter" for any purpose it does not name (13665-13669), so a new number silently filters the tree.
- Fix: `type Mode = NoMode | InTree Tree | InList Listing | InCustomize Customizing` in one field; `type Purpose = TreeSearch | TreeFilter | TreeKill | …`; `type DragKind = MoveBox | ResizeRight | …`.

### TB18 · The mode tree's keys are written three times and have drifted from each other and from tmux
- Where: app/src/TmuxMode.geng:11553-11750 (`listKey`), 12671-12909 (`customizeKey`), 14441-14781 (`treeKey`); 13507-13527 (`cellCount`) and 15968-15988 (`textCells`) are the same function; `clipCells` (14255) and `takeCells` (15948) nearly so; the sort-order `flip` at 11440 and 13864; the box heading at 11974-12007, 13420-13450 and 15132-15175
- Kind: design
- Severity: low
- Confidence: confirmed for the duplication; plausible for tmux's page size
- What: Up/Down/PPage/NPage/Home/End, `t`/`T`/`C-t`, search, filter, `v`, `O`, `r` and the row keys are each handled in three functions. They already differ: the tree pages by a fixed `page = 10` (14459) and the lists by 10 (11604-11612), customize-mode by the list's height (12775-12778), which is what tmux's `mode_tree_key` does for all three; the kill questions take only `"y"` (13629, 13639) where tmux's take `Y` too.
- Fix: one `modeTreeKey : String -> { count, selected, height } -> ModeTreeAct` shared by the three, each mode handling only its own keys; one set of cell helpers.

### TB19 · What would make modules of this half, and what each needs
- Where: app/src/TmuxMode.geng, 8600-17377
- Kind: design
- Severity: medium
- Confidence: confirmed
- What: 17,377 lines in one module, every function taking and returning the 80-field `State`. Most of this half does not need it:
  - **Status line and tab bar** (`tabsOf`, `puritySTabs`, `tmuxBar`, `extraStatus`, `takeRuns`, `laidRuns`, `clipPiece`, `statusSubscriptions`, `pollsFor`, `pollOf`, `timeOptions`, `subscribed`, `themedStatus`, `themeOf`, `colorsOf`, `optionNames`; about 900 lines): needs `StatusLine`, `tabs`, `window`, the theme, `lookTmux`, `timeFormats`. Pure.
  - **Pane borders** (`paneBorders`, `frameOf`, with `titleControls`, `scrollbarPieces` from the first half): `Layout.Pane`s and `StatusLine`. Pure.
  - **Menus** (`Menuing`, `MenuRow`, `readied`, `menuRows`, `menuPlace`, `drawMenu`, `menuKey`, `menuPointer`, `unstyled`): needs the menu, the area and `Colors`; `menuKey`/`menuPointer` can return `Chosen Int | Closed | Stay Menuing` rather than calling `runLine`.
  - **display-panes and the clock** (`Numbering`, `numberKey`, `paneNumber`, `bigDigit`, `clockText`, `modeOverlay`, `dayNow`): the version, `Colors`, a pane, a time.
  - **Lists** (11362-12026) and **the tree with its preview** (13537-16066, 2,500 lines): each needs only its own record, the version, `Colors` and a place; `treeKey`/`listKey` reach `State` only to set `asking`/`view`/`said` and to call `sendAsking`. Return `{ mode, asks : Array { command, expect }, prompt : Maybe Asking, said : String }`.
  - **customize-mode's glue** (12037-13505): `Customizing`, already resting on `Tmux.Customize`.
  - **Views** (`View`, `viewOf`, `filtered`, `shownLine`, `viewKey`, `moveView`, `tmuxView`, `boxView`): pure on `View` already.
  - **Copy mode's state** (`Copying`, `copyFormat`, `copyLine`, `askCopy`, `searchMarks`, with `copySpans` from the first half): `copy`, `copyAsked`, `back`, `modes`.
  - **Drops** (`DropMark`, `dragOver`, `dropMarked`, `dropLabel`, `pathFitting`…, `dropFolderOf`): `dropMark` and the placed panes.
  - **Pointer** (`pointerShape`, `selecting`, `extended`, `dragged`, `report`, `boxEdge`, `dragShape`): `drag`, `grab`, `selection`, `clicks`, `mouseLast`, `back`, the panes.
  What must stay in the core is the reply queue (`Expect`, `expecting`, `sendAsking`, `replied`) and `runLine`, which opens every mode. The obstacle to splitting is that the modes call `sendAsking` and build `Expect` values themselves; with the return shape above the core registers the questions.
- Scenario (cost): the findings above that are drift between copies (cells against characters, version 0 two ways, the unregistered command, page sizes) are each one helper used in some places and not others, in a file too long to see them side by side.
- Fix: start with the pure ones (views, status line, borders, menus), which move without touching `State`; then the tree.

### TB20 · Comments that no longer say what the function does
- Where: app/src/TmuxMode.geng:10919-10921 (`dueAt`: "to close the panes' numbers"; it also carries the poll, the stray wait and the clock), 8967-8969 (`tabsOf`: describes puritty's bar only; in tmux's look it returns `tmuxBar`'s hits and no text), 17141-17142 (`scrollKey`: "`Nothing` for any other key"; it returns `used = False`), 10873-10877 against 11059-11060 (letters for panes "10 to 35" and "10 to 34"; both are true of different things, a key and a label, and neither says so), 9292-9294 (`statusSubscriptions`: "at most once a second, the time in it expanded (`T:`)", but most entries have no `T:`)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- Fix: reword each to what it returns now.
- Fixed: 2026-11-26. Comments reworded: `dueAt` names all it wakes for (the numbers, the poll, a stray wait, a clock); `tabsOf` says what it answers in tmux's look; `statusSubscriptions` says which formats hold `T:`; the panes' letters say the keys take 10 to 35 and the labels 10 to 34, as tmux's `cmd-display-panes.c` does. `scrollKey`'s already said what it returns.

### TB21 · No test drives the pointer over a pane in a mode, or holds lines written to replies expected
- Where: app/tests/src/TmuxTests.geng, app/tests/src/FakeTmux.geng (looked at by name and by grep only)
- Kind: test-gap
- Severity: low
- Confidence: plausible
- What: the first three findings are each one test: a wheel event over a pane with `modes` `copy-mode` must send no `send-keys -H`; `back` must not change while `copy` has the pane; and the fake tmux should fail a test when it is sent a line for which `expecting` has no entry (it would have caught 4242).

---

## Looked at and found sound

- **Quoting of what goes into command lines** in this half: every value passes `Command.quote` (single quotes, `'` closed and reopened) or `Syntax.fill` (re-quotes a filled word): buffer and client names (`showBuffer`, `deleteBuffer`, `clientCommand`, the list's template), the mouse's word and line (`setPaneOption`), popup size, place, directory and command, tree targets (always ids `%n`, `@n`, `$n` made from `Int`s), filters (inside a quoted format). No raw concatenation of pane or user text into a line was found apart from the popup title's double expansion above. Text that reaches `quote` here cannot hold a newline (reply lines, a terminal row, a prompt's characters: `promptPasted` stops at the first control character), which matters because `quote` does not guard against one.
- **Menus**: formats asked once and run once as tmux does (`openMenu`, `ForMenuCommand`, `chooseItem`); the serial that drops an older menu's answers (`menuPart`); `readied`'s `-C` start item; a menu with answers pending takes only its closing keys; `menuRows`' separators and `-` items.
- **`noTime`** on every other `display-message` of a user's or a binding's format (`runLine`'s `run -C`, `plainLines`' condition, `openMenu`, `themeAsked`, `customizeDetailAsk`).
- **tmux 3.2's `buffer_created` crash** (TV6): `buffer_*` is asked only inside `list-buffers -F` (`listQuery`, `listFilterQuery`).
- **`kill-pane -t` always has a target** (TV6): `killOf` builds from `rowTarget`.
- **The status bar's trimming and justify arithmetic** (`tmuxBar`: list, then right, then left; the `<` and `>` marks; the hits' clipping), `clipPiece`, `takeRuns`.
- **`sessionSpan`, `previewRects`, `modeListHeight`, `customizeListHeight`, `treeFrame`**: bounds and clamps hold for empty lists and tiny areas.
- **The preview's serial** (`askPreview`, `ForPreviewList`, `ForTreeInfo`) drops answers for a row since left.
- **`bellsRung`** against `alerts_check_bell` as described (monitor-bell, bell-action, visual-bell).
- **`dragged`**: one line per motion to a new cell, the reply queue kept in step (`expectedLine` with the joined line), the left-edge move-and-resize pair, the floating box's border allowance.
- **`report`**: pane-relative pixel coordinates, the lowest held button for motion, `mouseLast` to drop repeats (apart from the copy-mode case above).
- **`tick`'s stray-line wait** (`strayUntil` -2, then `Control.giveUp`), and `Clock`'s wrap-safe comparisons where used.
- **`copyLine`**: positional parsing survives empty fields; a pane not in copy mode clears `copy` and `back`; `located` for tmux before 3.1.
- **`shownLine`/`viewOf`**: tabs, C0, DEL and C1 made harmless for views, the buffer preview and customize-mode.
- **`dropFolderOf`** follows docs/sftp.md FT11 as written; `dragOver` re-asks once a second only when the last answer is in.
- **`versionOf`** for `3.6a`, `next-3.9`, `3.10` (capped at 39) as documented.
- Known and not repeated: docs/review.md RV1 (the tree preview shows the last rows, not around the cursor), RV2 (done); docs/tmux.md TM39.3's differences by design (drag selects in puritty, the wheel and middle button are puritty's, Escape closes a prompt); popups before 3.8 (TV10); `e` in choose-buffer and customize-mode (TM80).

## Not covered

- Lines 1 to 8600 beyond the type definitions and the functions traced from this half (`notice`, `ours`/`reply`, `sendAsking`/`expected`, `ForCopy`, `ForModes`, `ForDayTime`, `pointerHere`, `typedHere`, `paint`'s frame, `modePlace`, `versionOf`): the prefix and key tables, `-r` repeat timing, the prompt editor and completion, copy mode's selection spans and what goes to the clipboard, `modeClick`/`modeClicked`/`modeMenuOpen` are the other reviewer's.
- `Tmux.Customize.act`/`answered`/`confirmed` (the commands customize-mode builds from typed values), `Tmux.Syntax` (`fill`, `retarget`, `menuOf`, `popupOf`, `ifFormatOf`, `lines`) and `Tmux.Style` were read only where called; whether puritty's parser agrees with tmux's on quoting was not checked.
- Nothing was run against a real tmux or the fake one: every statement about what tmux 2.7 to 3.8 does with a command is from the design documents or from tmux's source as remembered. The findings marked `plausible` need one run each.
- Draw-for-draw agreement of the tree, the lists, customize-mode, menus and display-panes with each tmux version (column positions, colours) was not checked beyond the version gates; the documents say these were measured side by side.
- Per-frame cost was read, not measured.

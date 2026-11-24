# 09 · app/src/Main.geng lines 1–5350, and Backend, Config, Clock, Keys, Chord, Links, Reason, TabOrder, LastWindow, Words, Search, TextEdit

Nothing was built or run: every finding is from reading the code. "Confirmed"
means the code path was read end to end, callers included; "plausible" means a
step depends on something outside the slice (the core library, another
package, the window layer), which is named.

Line numbers are `app/src/Main.geng` unless a file is named.

---

### MA1 · A window that draws no frame for 6.2 days stops drawing at all, for up to 6.2 more
- Where: app/src/Main.geng:1692-1704 (`frameAt`), 2605 (`step`), 2477 (`race`'s timer), 8668 (`draw`, the only write of `last`); app/src/Clock.geng:30-52
- Kind: bug
- Severity: high
- Confidence: confirmed
- What: `Clock.since` is right only for gaps under half the period (2^29 ms, 6.2 days); `Clock.reached due now` is `since due now >= 0`. `frameAt` answers `m.last` for an urgent frame and `Clock.after m.last frameMs` otherwise, and `step` draws only `if at >= 0 && Clock.reached at ms`. `m.last` is written only in `draw` (`last = ms`). Nothing refreshes it while the window is idle.
- Scenario: a window sits idle (shell prompt, no output; cursor not blinking because the window has no focus or mode 12 is off) for between 6.2 and 12.4 days of machine uptime. Then output arrives or a key is pressed: `since m.last ms` is now negative, so `Clock.reached` is false for both the urgent and the paced case, no frame is drawn, and the timer branch sleeps `Clock.since ms0 at`, which is up to 6.2 days. Keys are still sent and output still fed, but the window shows the old picture until the clock comes round. Focus, resize and tab-switch frames fail the same way, since they also go through `urgent`. `docs/rhel8-etx.md` RE11 says puritty's gaps "are seconds" and lists only the log under "Left"; the last frame's time is a gap that is not seconds.
- Fix: do not let `last` go stale: either keep it in `Int64` (it is the one time compared after an unbounded wait), or in `step` treat a `last` whose `since` is negative or larger than some hours as "long ago" and set it to `ms - frameMs`. A unit test with `PURITTY_CLOCK_START` cannot catch this; a `frameAt`/`reached` test with a 7-day gap can.
- Fixed: 2026-11-21. `step` keeps `last` recent with `Clock.recent`: a last frame older than a frame's pacing is taken as just that old, so a frame is due however long the window drew nothing. Test: the clock's "a frame paced from a time seven days old". MA13's three times are not done.

### MA2 · Ctrl+click opens any `file://` link, including executables and UNC paths, with the target never shown
- Where: app/src/Links.geng:12-22; app/src/Main.geng:7231-7252 (`linkOpened`); packages/win32/src/Ext/puritty_win32.c:2939 (`ShellExecuteW(NULL, L"open", ...)`); docs/claude-code.md CL9
- Kind: security
- Severity: high
- Confidence: confirmed for what `Links.openable` lets through; plausible for what Windows then does with it (the C caller was read, not run)
- What: `openable` accepts anything that starts `file:///` or `file://localhost/`, whatever the path or file type, and the URI goes to `xdg-open` or `ShellExecuteW "open"` as it is. `file:////host/share/x.exe` starts with `file:///` and so passes as a "local" file. CL9 records that a link is not drawn differently and the pointer does not change over one, so the user cannot see where a link goes before Ctrl+clicking it. The check also does not ask whether the tab is remote (`isRemoteTab`), though the module's comment gives "a program on another host names its own files" as the reason for the host check, and `filesRead` (4035) refuses local paths for a remote tab for the same reason.
- Scenario: any text that reaches the terminal (a remote host's output, `cat` of a hostile file, a `curl`ed page) prints an OSC 8 link whose visible text is `https://example.com/docs` and whose URI is `file:///C:/Users/me/Downloads/setup.exe`, or `file:////attacker/share/tool.exe`. On Windows, Ctrl+click runs it (`ShellExecuteW "open"` on an executable, `.bat`, `.lnk`, `.hta`), and the UNC form also sends the user's NTLM credentials to the attacker's SMB server. On Linux `xdg-open` opens the path in whatever the desktop maps its type to. In an ssh tab the path is one of this computer's, not the host's the program meant.
- Fix: refuse `file:` links from a remote tab; for local ones resolve the path, refuse a UNC or `//` path and an empty-host form that normalizes to one, and open the containing folder or only non-executable types rather than handing the file to "open". Show the URI (in the note bar or a hover) before it is opened. Add the UNC and executable cases to the app test that covers `Links`.
- Fixed: 2026-11-21. `Links.openable` refuses every `file:` link from a host's tab (`isRemoteTab`), and a path beginning with a second `/` or a `\`, plainly or as `%2F`/`%5C`, or holding a `\` anywhere; and a file link is shown in the note bar at the first Ctrl+click and opened by a second on it within 6 s (`Links.click`, W1). Tests: "a file link to another machine's share ... is not opened", "a file link is shown first"; checked on Xvfb; `docs/claude-code.md` CL9.

### MA3 · Scrollback search unpacks a whole 1,024-row page for every row it looks at
- Where: app/src/Search.geng:48-81 (`findFrom`), 141-154 (`rowMatches`); vt/src/Vt.geng:783-830 (`selectionText`), 743-765 (`rowsBetween`), 1325-1354 (`viewPages`); vt/src/Vt/Pages.geng:533-553 (`pageRowsOf`); app/src/Main.geng:8081-8131 (`searchKey`)
- Kind: speed
- Severity: high
- Confidence: confirmed (by reading; not timed)
- What: `findFrom` reads one row at a time with `Vt.selectionText { row, col = 0 } { row, col = cols - 1 }`. For a row in the paged scrollback that is `rowsBetween first 1`, which walks the page list from its head (`viewPages`, linear in pages) and then calls `pageRowsOf page`, which unpacks every row and every cell of the page (`Vt.defaultPageRows` = 1,024) to slice one row out. `searchKey` runs `Search.find` from the view's bottom on every typed character and every Backspace, synchronously in the update loop.
- Scenario: the default scrollback (25,000 lines' worth of bytes, often several times that many rows; the setting goes to 10,000,000). The user opens search and types a word that does not occur, or occurs only far back: each keystroke unpacks about `rows × 1,024` rows (25,000 rows gives some 25 million row unpacks, around 2 billion cells), plus a string built per row by per-cell `++`. The window is frozen for that long per character typed: no output is read, no frame drawn, no key handled. A search that matches within the ring (the most recent rows) is fast, so the gate's `search-copy` case does not show it.
- Fix: read the scrollback a page at a time (a core function that answers a block of rows' text, or a fold over rows that unpacks each page once) and search within the block; bound the work per turn and carry the scan over turns so the loop keeps running; skip a rescan on a longer query when the shorter one already failed. `Search.find` has no unit test over paged scrollback.
- Fixed: 2026-11-21. `Search.find` and `Search.matchesIn` read rows through `Vt.rowTexts`, 1,024 at a time, each page of the scrollback read once for its rows. Measured on node, 20,000 rows, a query found nowhere: 140.2 s before, 0.59 s after (feeding included). Not done: the search still runs within one turn of the loop, and a shorter query that failed is not used to skip a longer one. Test: "a query is found in the paged scrollback". `docs/phase3-select.md` §23.

### MA4 · The dialog shown and the dialog the keys go to are decided by two different orders
- Where: app/src/Main.geng:8427-8476 (`draw`'s `dialog`), 8304-8388 (`dialogUp` and its chain, used by `handleOne` at 6585), and the same list again at 2389 (`pointerShape`), 2420 (`hoverShapes`), 3119-3176 (`windowState`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `draw` picks the box in the order `startFailed`, `closing`, `dropAsk`, the conflict question, (chooser), `pasteAsk`, `renaming`, `coloring`. `dialogUp`, which decides where a key or press goes, uses `startFailed`, `dropAsk`, conflict, `picking`, `choosing`, `pasteAsk`, `closing`, `renaming`, `coloring`. Each is a separate `Maybe` field of the model, so two can be up together.
- Scenario: the question "send these files to the folder found?" (`dropAsk`) or "write the pasted picture?" (`pasteAsk`, which arrives later, when the host answers) is up, and the user clicks the window's close button; a busy tab sets `closing`. The window now draws the close question, but Enter or `y` goes to `dropKey`/`pasteKey`: the files are sent, or the picture is written, by a user who thinks they answered "close the window?". The reverse also happens: `pasteAsk` set by `uploadDone` while the close question is up is not drawn but takes the keys.
- Fix: one field, `dialog : Dialog` (the `Dialog` type at 8296 already lists the cases) or a stack of them, read by `draw`, `handleOne`, `pointerShape`, `hoverShapes` and `windowState` alike; opening one while another is up either queues or replaces, decided in one place.
- Fixed: 2026-11-23, `docs/tabs.md` TB20. `draw` renders the box of `dialogUp m`, the dialog the keys and presses go to. Not measured end to end: the drop gate's nemo opens no window on gmktec7.

### MA5 · A settings reload reaches only the shown tab's terminal
- Where: app/src/Main.geng:3389-3486 (`applyLook`), 8933-8980 (`swapTab`), 8995 (`afterSwitch`), 1104-1116 and 9310/9354 (`starter.charset`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `applyLook` calls `Vt.setPalette`, `Vt.setScrollbackBytes`, `Vt.withEmbedder` and the four `TmuxMode.set…` on `m.term` and `m.tmux`, and sets `m.charset`; these are the shown tab's. `m.tabs` is touched only by `cellSized` (font) and `relayout` (bar). Nothing re-applies them when a tab is shown later (`afterSwitch` only resets the shadow). The next reload compares `new` with the already-updated `m.config`, so the difference is never seen again.
- Scenario: three tabs; the user changes the palette (or `[scrollback] lines`, `[tmux] look`/`tabs`, the foreground/background a program reads with OSC 10/11, `[terminal] charset`) in the settings window. The shown tab changes at once; the other two keep the old palette, the old scrollback bound, the old OSC 10/11 answers and the old charset for the rest of their lives, and a program in them that asked for theme reports (mode 2031) is never told. New local tabs get `starter.charset`, captured in `begin` at the window's start, so after a charset change the shown tab, the hidden tabs and new tabs can disagree. ST4 ("applied to the running window") does not say tabs are excepted.
- Fix: apply the per-terminal part of a reload through `atTab` for every hidden tab (as `relayout` does for sizes), or keep an "applied config" stamp per tab and bring a tab up to date in `swapTab`. Take the new tab's charset from the config in force rather than from `starter`.
- Fixed: 2026-11-23, `docs/settings.md` ST37. `lookTab` is a change's per-tab part (palette, scrollback bound, embedder, tmux look, charset when its setting changed), done to the shown tab and through `atTab` to each hidden one; new local tabs take the charset in force. Test: `harness/reload.py` `palette-hidden-tab`: before, 1,185 pixels differed from the change made with the tab shown.

### MA6 · `[images] read_files` turned off (or on) does not reach a running terminal
- Where: app/src/Main.geng:3420-3425 (`applyLook`'s `told`), 1784-1797 (`embedderOf`); vt/src/Vt/Kitty.geng:655; app/src/Schema.geng:917-924 (`applies = AtOnce`)
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: whether Kitty's file media are honoured is `t.embedder.kittyFiles`. On a reload the embedder is replaced only `if new.foreground /= old.foreground || new.background /= old.background`; otherwise `term1` keeps the embedder it was made with. (And only for the shown tab, as in the finding above.)
- Scenario: the user finds `read_files = true` in their settings, reads its description ("a program you ssh to from a tab can show this computer's files"), and turns it off in the settings window, which says it applies at once. Every open terminal goes on reading local files a program names until the window is closed, unless the same reload also changed a color. Turning it on has no effect either.
- Fix: replace the embedder whenever `embedderOf new /= embedderOf old` (it also carries `version` and `attributes`), on every tab.
- Fixed: 2026-11-23, `docs/settings.md` ST37. The embedder is replaced whenever `embedderOf` differs, on every tab. Test: `harness/reload.py` `read-files-on` and `read-files-off`: before, a picture from a file was not shown after turning it on and was shown after turning it off.

### MA7 · Output in a tab not shown forces a frame for every chunk read, past the 16 ms pacing
- Where: app/src/Main.geng:9649, 9656 (`behind`: `{ m | urgent = True }`), 1700-1701 (`frameAt`: urgent is due at `m.last`), 2605 (`step`)
- Kind: speed
- Severity: medium
- Confidence: confirmed
- What: `behind` sets `urgent = True` on the window's model for every read of a hidden tab, so that its activity mark shows. An urgent frame is due at once, so `step` calls `draw` after every chunk. `draw` rebuilds the tab bar, the title and the frame, and calls `Window.draw` and `Window.spot`, each time.
- Scenario: a build or `yes` runs in a background tab. Each chunk read from it (up to 64 KB, often far smaller) costs a frame of the shown tab, where the shown tab's own output would be held to one frame per `frames.every_ms`. A hidden tab's flood is thus more expensive than a shown one's, and takes time from the shown tab's key handling. The FT27 comment at 4822-4826 records the same effect for uploads ("a frame each reply held a shown tab's upload to a fifth of a hidden one's") and fixed it there only.
- Fix: set `urgent` in `behind` only when the tab's `activity` or `bell` mark actually changes (compare `info` before and after `marked`); otherwise leave the frame to `pending` and the pacing.
- Fixed: 2026-11-24, `docs/tabs.md` TB21. `behind` asks for a frame at once only when the tab's marks change (`marksOf`). Measured: a hidden tab with about a thousand small reads a second cost puritty 0.53-0.70 s of CPU per 5 s, now 0.19-0.38 s; with `yes` the parsing dominates (about 6 MB/s either way).

### MA8 · Work that only the timer branch does waits for as long as the shown tab keeps printing
- Where: app/src/Main.geng:2509 (`Task.race (remote.read …) ([ Window.events … ] ++ timer ++ writing ++ following ++ behindTabs)`), 2548-2552 (`Due`), 2557, 2560-2564; docs/sftp.md FT25 ("natively the session's did every time")
- Kind: bug
- Severity: medium
- Confidence: plausible (rests on which ready task `Task.race` answers natively; FT25 measured that the first listed did, every time)
- What: FT25 found the window's events starved by a session that always had something to read, and added `windowToo` after a read. The other branches got no such thing. `reloadIfDue`, `saveIfDue`, `expireNote`, `expireClosed`, `blink`, `tmuxDue` (tmux's tick, and the give-up when tmux does not answer), `pickerTick` run only when `Due` wins; `SettingsChanged`, `Behind` and `BehindWritable` only when theirs do.
- Scenario: the shown tab prints without pause (`yes`, a long `cat`, a build log). For as long as it does: a settings change is not applied, a note does not go away, the tabs are not saved, hidden tabs are neither read nor written (their programs block on a full pty, and a hidden tab whose program ended is not closed), and under `tmux -CC` the tick does not run. Frames are still drawn, since `step` does that after every read.
- Fix: after a read wins, do the due work by the clock (`if Clock.reached … ms`) in `step` rather than only in the `Due` branch, and give hidden tabs and the settings source a non-waiting look in the same place `windowToo` gives the window one; or rotate which task is listed first.

### MA9 · A paste in flight goes to whichever tab is shown when its pieces arrive
- Where: app/src/Main.geng:180-185 (`toPaste`, window's; `pasting`, `clipRead`, the tab's), 7076-7111 (`Window.Pasted`, `Window.PastedImage`), 8933-8980 (`swapTab`), 9066 (`dropShownFrom`)
- Kind: bug
- Severity: medium
- Confidence: plausible (the pieces' timing is the window layer's; the routing was read)
- What: a paste is asked for with `toPaste` and its text comes back in later events, in several pieces for a large one (`Pasted more`). Each piece is handled against the model as it is then: `m.clipRead` and `m.pasting` are the shown tab's, swapped by `swapTab`, and `pasteIn`/`imagePasted` write to `m.remote`. Nothing records which tab asked.
- Scenario: (1) the user pastes many lines into a shell and the first makes it exit; the tab closes (`dropShown`) and the rest of the paste is typed into the next tab, as a new paste whose bracketing is that tab's. In a tab without bracketed paste the lines run as commands. (2) The user switches tabs during a large paste: the old tab is left with `pasting = Just …` (its closing `ESC [ 201 ~` never sent, and its next paste sends no opening one), the new tab gets the remainder. (3) With `osc52_read` on, a program asks to read the clipboard and its tab is switched away or closed before the selection arrives: `m.clipRead` is now `Nothing`, so the clipboard's text is pasted into the other tab as typed input. The same holds for a picture (`imagePaste` is the window's).
- Fix: keep the asking tab's id with `toPaste` and with the gathering state, and hand each piece to that tab with `atTab` (as `pasteAsk` and `dropAsk` already carry `tab`); drop the pieces when the tab is gone, and close an open bracket when a tab is put away mid-paste.
- Fixed: 2026-11-23, `docs/phase3-select.md` §25. The window keeps `pasteTab`, the tab a paste, picture or OSC 52 read was asked for; `toAsker` hands each piece to it (through `atTab` when hidden), and drops the rest when it is gone. Test: `harness/tabpaste.py`: before, B received 1,048,579 bytes when A closed mid-paste and 2,097,154 when switched away from.

### MA10 · The built-in ssh session's output reaches the window through a queue with no bound
- Where: app/src/Backend.geng:102-139 (`ssh`: `Source.next sources.notices`, `writeSome` = `Source.emit … |> Task.map (\_ -> Bytes.length bytes)`, `writable = Task.succeed {}`); packages/ssh/src/Ssh/Session.geng:1312-1316 (`tell (Output bytes)`); geng-lang core `Source.geng` (a queue; `emit` does not wait)
- Kind: security
- Severity: medium
- Confidence: plausible (whether the session's channel window is tied to what the window has consumed is the ssh package's; nothing in `Backend` ties it)
- What: a pseudo terminal pushes back through the kernel when the loop is slow. The ssh backend does not: the session task reads the socket and emits each `Output` into a `Source`, and the loop takes one notice a turn (each turn does the per-turn housekeeping, a feed, and often a frame). In the other direction `writeSome` always takes everything, so the outbox's flow control (V48) is moot and a large paste is copied whole into the inputs queue.
- Scenario: a host (hostile, or just `cat` of a large file over a fast link) sends faster than the loop feeds and draws. The queue grows without limit, and memory with it; Ctrl+C is sent at once but the megabytes already queued are still fed and drawn before the prompt shows.
- Fix: bound what is outstanding: have the session grant channel window only as the loop takes output (an acknowledging input, or a counter the session reads), or coalesce queued `Output` notices into one feed per turn and stop reading the socket past a high-water mark.
- Fixed: 2026-11-23, with SC2 (`docs/ssh-client.md` SC35): what waits between the session and the loop is at most the 2 MiB window. The keys direction (`writeSome` takes a whole paste) is left; it is the user's own paste.

### MA11 · A failing call on any tab's backend ends the whole window, and skips `finish`
- Where: app/src/Main.geng:1430-1568 (`runWith`: `restoreInto … |> Task.mapError Os.Error.toString |> Task.andThen (\m -> finish m.remote m)`), 1830-1841 (`flush`), 2521-2523, 9119-9121 (`closeShown`: `m.remote.kill |> Task.mapError …`), 9597 (`resizeShown`), 9706-9713 (`endTab`), 1650 (`finishTabs`)
- Kind: design
- Severity: medium
- Confidence: plausible (which of these calls can fail in practice is the core library's and the OS's)
- What: the loop is one `Task Error Model`. `remote.read`, `writeSome`, `resize`, `kill` and `waitForExit` of the shown tab and of every hidden tab are chained into it with no `onError`, so one failure fails the loop. `finish` is chained with `Task.andThen` after it and so does not run: the window's state is not remembered (`rememberWindow`), `SessionFile.end` is not written (the count of open windows that SG16 and `savedAtEnd` read stays one too high), the log's last lines are not written, and the other tabs' programs are not killed by puritty.
- Scenario: the user presses Ctrl+Shift+W on a tab whose program exited a moment before (its end not yet read): if `Process.kill` answers an error for a process that is gone, every tab of the window closes with `puritty: …` on standard error. The same for a `resize` or a write that fails on one hidden tab while the user works in another.
- Fix: catch a backend's error at the tab (`Task.onError` in `flush`, `resizeShown`, `closeShown`, `endTab`, and around each raced read) and close that tab with the reason in a note or the log; run `finish` on both the loop's success and its failure.

### MA12 · Main.geng is 10,922 lines over one 130-field record, and the shown tab's fields are kept in step with `Tab` by hand
- Where: app/src/Main.geng:115-285 (`Model`), 300-327 (`Tab`), 8933-8980 (`swapTab`), 9303-9375 (`freshTab`, `reopened`)
- Kind: design
- Severity: medium
- Confidence: confirmed
- What: the shown tab's session is twenty loose fields of `Model`; `Tab` repeats them; `swapTab` copies each of the twenty by name in both directions, and `freshTab` and `reopened` list them twice more. A per-tab field added to `Model` and not to those four lists is silently shared by every tab; several findings above are state on the wrong side of that line (`toPaste`/`imagePaste`, the nine dialog fields, the bell total) or code that updates only the loose copy (`applyLook`). The file's size is its own cost: every function takes the whole `Model`, so nothing says what a function reads or writes, and the dialog order above drifted across five copies inside one file.
- Scenario: the cost is the findings above, and review: the two halves of this file were given to two reviewers who each had to read into the other's half to follow one key press.
- Fix, concretely. First make the shown session one field, `session : Tab` (or `Session`), so `swapTab` is one exchange and `atTab` needs no copying. Then these groups are coherent modules, with the state each needs:
  - **Start** (lines 508-1430: `cli`, `main`, `terminalMain`, `choose`, `hostList`, `becomeSession`, `start`…`begin`, `sshBackend`, `ptyBackend`, `controlled`, `userMaster`, `spawnFirst`, `run`): needs no `Model`; it ends by making one.
  - **Saving** (`lastWindow`, `rememberWindow`, `restoreInto`, `startSaving`, `saveIfDue`, `saveNow`, `stateOf`, `savedTabsOf`, `savedAtEnd`, `restoreTurned`): the `saving` record, `normalSize`, `maximized`, and a read-only list of `{ name, color, remote }` per tab.
  - **DiagLog** (2781-3340: `logTurned`, `beginLog`, `pruneLogs`, `logHeader`, `writeLog`, `markLog`, `windowState`, `eventLine`, `sshLine`, `sideLine`): `diag`, `logDir`, `turnMs`, `clockStart`, the file permission; `windowState` wants a small summary record rather than the model.
  - **Notices** (`bellRung`, `tabStates`, `statusNoticed`, `noticesShown`, `noticesFrom`, `statusMark`, `keySound`): `bellsHeard`, `statusSeen`, `attentionAsked`, `noticeAt`, and each tab's terminal.
  - **Menu** (3577-3865): `MenuItem`, `menuItems`, `popupItems`, `menuBox`, `menuPaints` are pure over `Config`, the recents and a `Menu`; only `menuDo` touches the model.
  - **PicturePaste** (4254-4660 with 5597-5830: `imagePasted`, `uploadImage`, `sendImage`, `uploaded`, `uploadDone`, `localImage`, `pasteBox`, `pasteAnswer`): `upload`, `imagePaste`, `pasteAsk`, `uploads`, the tab's charset and `side`. Its shell quoting (`folderWord`, `underSh`, `doubleQuoted`, `uploadCommand`, `folderCommand`, `quotedPath`) is pure and wants its own tested module: it builds commands a host runs.
  - **Drops** (4662-5465: `filesDropped`, `sshDropped`, `startPending`, `sendingStep`, `sendingOut`, `sendingShown`, the conflict keys, `chooser…`, `marksKept`, `folderSent`, `dropBox`…`dropAnswer`): `sending`, `choosing`, `pendingSend`, `dropAsk`, `dropGather`, `folders`, `pickerPlaces`.
  - **SshScreen** (4183-4252 with 5829-6580), **Tabs** (8680-10730) and **Frame** (`frameAt`, `nextAt`, `blink`, `step`'s test, with `last`, `pending`, `urgent`, `blinkAt`, `syncSince`), the last small and pure enough to unit-test the pacing and the clock finding above.
  Also: the state folder is found by cutting a word off another path in three places (`stateFolder` 996 drops "logs", `Platform.logDirectory` drops "windows", `RecentFile.folder` drops "windows"); one function that answers the folder would do.

### MA13 · Three more times are compared after gaps the clock cannot hold
- Where: app/src/Main.geng:9678 (`marked`: `Clock.reached m.quietUntil ms`), 1865 (set once, never cleared); 2265, 2287 (`noticeAt`); 1915 (`saving = { …, at = 0 }`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: the same half-period limit as the first finding. `quietUntil` is set to "3 s from the start" in a restored window and never set back to -1. `noticeAt` is "3 s after the last notification shown". `startSaving` writes the literal `0` as a time.
- Scenario: a restored window open for 6.2 to 12.4 days (and each alternate 6.2 days after): `Clock.reached m.quietUntil ms` is false again, so output in hidden tabs no longer sets their activity mark. A window whose last desktop notification was 6.2 to 12.4 days ago: the next ones are "dropped: one was shown less than 3 s ago", every one of them, since a drop does not move `noticeAt`. `[tabs] restore` turned on in a window open that long: the first save is "due" at clock 0, days away.
- Fix: clear `quietUntil` and `noticeAt` to -1 once reached (in the `Due` branch or where they are read), and use the turn's time, not `0`, in `startSaving`.
- Fixed: 2026-11-22. `Clock.passed span due now`: `reached`, or a due reading as more than `span` to come, which one set at most `span` ahead can only once it is half the period old. `marked` (`quietUntil`, 3 s), the notifications (`noticeAt`, 3 s) and `saveIfDue` (`saving.at`, 5 s) use it, and `startSaving` makes the first save due at `m.turnMs`, not 0. Test: the clock's "a time set 3 s ahead is passed seven days later". The other due times of the kind are listed as MAN2 in README; `docs/rhel8-etx.md` RE11.

### MA14 · Bells in a hidden `tmux -CC` tab are not heard, and switching to or reopening a tab can ring
- Where: app/src/Main.geng:2104-2152 (`bellRung`), 9339-9352 (`reopened` keeps `k.term`); app/src/TmuxMode.geng:9469-9471 (`bells` = `s.audible`, a running count)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: the total is `m.term.bells + (each hidden tab's term.bells) + TmuxMode.bells m.tmux`: the shown tab's tmux panes are counted, a hidden tab's are not. The sound plays when the total rises.
- Scenario: (1) a pane rings in a `tmux -CC` tab that is not shown: no sound, against SN6 ("puritty's own or another tab's or a tmux pane's"). (2) Switching from a plain tab to that tmux tab raises the total by its `audible`, so the bell sounds on the switch; switching back lowers it, silently. (3) A tab whose terminal ever rang is closed (the total falls, taken as it is) and reopened with Ctrl+Alt+Shift+T: `reopened` keeps the terminal and its count, the total rises, the bell sounds.
- Fix: count per tab: keep each tab's heard count beside `TabInfo.bells` (terminal and tmux together) and ring when any tab's own count rises, rather than comparing one sum.

### MA15 · Every turn of the loop does several passes over all tabs, and every key parses every binding
- Where: app/src/Main.geng:2074-2097 (`loop`), 2104 (`bellRung`), 2158-2223 (`tabStates`, `statusNoticed`), 2230-2328 (`noticesShown`, `noticesFrom`), 2378-2420 (`pointerShape`, `hoverShapes`), 2497-2507 (`hiddenOf` and a read task per tab); 3544-3551 (`bound`: `Chord.parse name` per call); 3944, 4140 (log text built whether or not the log is on)
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: a turn is one read chunk, one batch of events or one timer. Each turn: `bellRung` folds over the tabs; `tabStates` builds an array and `statusNoticed` a fresh `Dict` of every tab's status; `noticesFrom` rewrites every hidden tab's slot (`Builder.set i (Just { t | term = taken.term })`) whether or not it had a notice; `pointerShape` evaluates the dialog list and the scrollbar hit; `race` builds a read task per hidden tab and cancels the losers. Per key event, `bound` re-parses the binding's string (`String.split`, trims, `toLower`, a linear scan of `Chord.named`) for each of about seventeen `[keys]` entries (`tabAction`, `isPasteKey`, `isCopyKey`, `isSearchKey`, `isSettingsKey`). `feed` builds `String.fromInt (Bytes.length chunk) ++ " bytes"` and `handle` builds `eventLine ev` (per pointer motion too) before `Diag` decides the log is off.
- Scenario: a flood read in small chunks with fifteen tabs open pays the O(tabs) passes per chunk; none is large alone, but they are on the path every byte of output and every key goes through.
- Fix: parse the chords once when the settings are read (a `Maybe Chord` per binding in `Config`), take notices and statuses only from the tab that was just fed, and build log text behind `Diag.isOn`.

### MA16 · The cursor's blink keeps waking the loop, and repainting every cell, while no cursor is on the screen
- Where: app/src/Main.geng:1686-1688 (`blinking`), 3910-3916 (`blink`: `urgent = True`), 8531-8539 (`over || m.overlaid` gives a fresh shadow)
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: `blinking` asks only for focus, `showCursor` and mode 12. It does not ask whether the view is scrolled back (`m.back > 0`), puritty's own ssh screen or a dialog is up. Each blink sets `urgent`, and a frame drawn while the scrollbar, the search bar, a note or a box is up draws every cell (§23, by design for those frames).
- Scenario: the user scrolls back to read, in a program that asked for a blinking cursor: twice a second (`blink_ms` 500) the window is repainted whole, to blink a cursor that is not in the view.
- Fix: make `blinking` false while the cursor is not drawn (scrolled back, own screen, a box over it), so the timer is not armed.

### MA17 · A search match after an emoji sequence, or in a row where lowering a letter changes its length, is highlighted in the wrong columns
- Where: app/src/Search.geng:58-67, 85-103 (`cells`), 159-175; vt/src/Vt.geng:849-877 (`cellsText`: "a cluster read whole")
- Kind: bug
- Severity: low
- Confidence: plausible (depends on `Vt.Width.width` for joiners, modifiers and regional indicators, and on `String.toLower` keeping the count of characters)
- What: the match's columns are found by measuring the row's text before the match one code point at a time (`Width.width cp`). `selectionText` gives a cell's whole cluster, so a cell holding a ZWJ family, a flag or a skin-toned emoji contributes the sum of its code points' widths (6 or 4) where it takes 2 cells. The index `i` is found in `String.toLower text` and then applied to `text`.
- Scenario: a row `👨‍👩‍👧 error: …`; searching `error` highlights four cells to the right of the word, and Ctrl+Shift+C copies those cells, not the match.
- Fix: have the core answer each character's column with the row's text (or search over the cells), so the app does not measure again; compare case without changing the string that is indexed.

### MA18 · The `Backend` passed beside the model can be a tab's that is no longer shown (the menu's paths)
- Where: app/src/Main.geng:2571 (`step remote ms m0`: `remote` is never used), 4132 (`handle remote …`), 6691, 6705, 6843 (`menuKey …`/`menuChosen …` then `handle remote ms rest next`), 6110, 6237, 6252 (`sshKey remote`: `remote.reconnect`, `remote.answer`)
- Kind: design
- Severity: low
- Confidence: confirmed (the stale value is passed; no input was found that makes `sshKey` act on it today)
- What: `loop`, `race`, `step`, `handle`, `handleOne`, `key` and `sshKey` take the shown tab's backend as a parameter although it is `m.remote`. Most branches pass `next.remote` after a step that can change the shown tab; the menu's branches do not, though `menuDo` can open or reopen a tab. `step`'s parameter is dead.
- Scenario: a menu's "New tab" and a following key in the same batch of events: the rest of the batch is handled with the old tab's backend, and `sshKey` would answer or reconnect the wrong session if it were reached. It is one edit away from a real misdirected answer (a password typed for one host sent to another's session).
- Fix: drop the parameter; read `m.remote` where it is used.

### MA19 · A restored window shows the wrong tab when one of its tabs does not start
- Where: app/src/Main.geng:1867-1876 (`restoreInto`: "ids are given in order from 0, so the saved order's place is the id"), 9251-9252 (`openTabWith`'s `Err` branch takes no id)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: the saved `shown` is a place in the saved order, used as a tab id. A tab that fails to start (`startFailed`) gets no id, so every later tab's id is one lower than its place.
- Scenario: five saved tabs, the third's directory is on a disk not mounted and its start fails outright, the fourth was shown: the window shows what was the fifth, or with the last one failing, stays on the last opened. Only the last failure's reason is kept in `startFailed`.
- Fix: collect the id each restored tab got (or `Nothing`) and show by that list.

### MA20 · A font that cannot be opened on reload also drops a size change made with it
- Where: app/src/Main.geng:3507-3531 (`refontOr`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: on `Err`, `config` becomes `{ new | font = old.font, language = old.language, glyphCacheMb = old.glyphCacheMb }`: `config.points` is the new size, `m.points` and the window's font are the old, and `Window.zoom` is not called. The next reload sees `new.points == old.points` and does nothing.
- Scenario: the settings file is edited to a font name with a typo and a new size together: the size is never applied until it is changed again.
- Fix: on `Err`, fall through to the `points` branch (zoom when the size changed).

### MA21 · A synchronized update holds back puritty's own frames too
- Where: app/src/Main.geng:1697-1701 (`frameAt`: the mode 2026 test comes before `urgent`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: while the program holds mode 2026 and a read has come since the last frame (`syncSince >= 0`), the frame is due at `syncSince + sync_timeout_ms` whether or not it is urgent.
- Scenario: a program redraws under 2026 continuously (or sets it and never clears it while printing). Scrolling back, opening the menu or the search bar, a tab switch, a resize: each waits up to 150 ms for its frame, every time.
- Fix: let frames that puritty's own state asked for (`urgent` set by an event, not by a read) draw at once; hold only the program's output.

### MA22 · The helper processes of an OpenSSH tab: a pipe left open, entries never removed, and two ways to stall
- Where: app/src/Backend.geng:223-268 (`helpers`), 305-340 (`helperOutput`)
- Kind: bug
- Severity: low
- Confidence: plausible (whether `Process.kill` or the collector closes a child's pipes is the core library's)
- What: (1) `SideClose` kills the child and drops it from `children`, but closes nothing; `pipes.input` is closed only by `SideEof`. The folder chooser ends with `SideClose` and no `SideEof` (Main.geng:5211, 5337), so each chooser leaves a pipe open. (2) A helper that ends by itself stays in `children` until a `SideClose` that the picture upload never sends (`uploaded` at 4549 only forgets the upload). (3) `helperOutput` reads the error pipe only after the output pipe reaches its end: a helper that writes more than a pipe's buffer to standard error first blocks, and so does the read. (4) `SideWrite` is `File.write` of the whole piece inside the one loop that takes every helper's inputs: while `ssh` is slow to read a 10 MB picture, the chooser's requests and a `SideClose` for the stuck upload wait behind it.
- Fix: close all three pipes on `SideClose` and when the helper ends, and remove its entry then; read the two outputs side by side; write in pieces with the `writable` wait the pty backend uses.

### MA23 · A program that closes its terminal but keeps running freezes the window
- Where: app/src/Main.geng:2516-2524 (`remote.waitForExit` then `dropShown`), 9710 (`endTab`), 1668 (`finishShown`)
- Kind: bug
- Severity: low
- Confidence: plausible
- What: an empty read (the pty's other side closed) is taken as "the program ended", and the loop then waits for the child's exit inside the turn.
- Scenario: the tab's program closes or redirects all three of its terminal descriptors and carries on (`exec >/dev/null 2>&1 </dev/null; sleep 600`, a shell function that daemonizes itself). The read ends; `waitForExit` blocks the loop, and with it every other tab and the window's events, until that process exits.
- Fix: close the tab at the empty read and collect the exit status off the loop (a spawned task), or kill the child before waiting.

### MA24 · A binding that names a shifted character or a non-Latin layout's letter never matches
- Where: app/src/Chord.geng:240-249 (`matches`), 144-170 (`keySym`), 24-41 (`parse`)
- Kind: bug
- Severity: low
- Confidence: plausible (depends on what the window layer puts in `sym` and `unshifted`)
- What: a chord matches when the modifiers are exactly its own and `k.sym == c.sym` or `k.unshifted == c.sym`. `"Ctrl+Plus"` is sym `+`; on a US layout `+` is Shift+`=`, so the key arrives with Shift held (the modifiers differ) or as `=` (the sym differs), and it never matches, though the module's comment offers `"Ctrl++"` as an example. The same for a digit on a layout where digits are shifted (AZERTY). A letter chord compares against Latin keysyms only, so on a Russian or Greek layout `Ctrl+Shift+C` has neither `sym` nor `unshifted` equal to `C`. A bare `"+"` parses as two empty names and is refused. Keypad Enter, Home, End and Delete are not taken for their main-block keys, though keypad Insert, PageUp and PageDown are.
- Fix: match a letter or punctuation chord on the key's position as well (the keycode's US meaning, which `Vt.KeyTables.evdevKey` already knows), and treat Shift as consumed when the chord's character is the key's shifted one.

### MA25 · What a host's paste command prints is kept without bound
- Where: app/src/Main.geng:4534-4541 (`uploaded`: `Bytes.flatten [ u.out, b ]`, `[ u.err, b ]`)
- Kind: security
- Severity: low
- Confidence: confirmed
- What: the command puritty runs on the host prints one path; whatever arrives on its channel is appended to `u.out` or `u.err` until the channel ends, each append copying all that came before.
- Scenario: a host whose `sh` (or a hostile host) answers the paste command with an endless stream: memory grows without limit, quadratically in time, and the "still being sent" state never ends, so no other picture can be pasted in that tab.
- Fix: cap both at a few kilobytes (a path and an error line) and close the channel with a failure note past that.

---

## Looked at and found sound

- **Clock** (`Clock.geng`): `since`, `after`, `reached`, `earlier`, `latest`, `soonest` are right within the documented half period; the findings are about callers whose gaps are not short.
- **TabOrder**: `around`, `moved`, `closedShown`, `removed` keep `0 <= shown < length order`, as their refinements say; `Model.shown`'s refinement is kept by every update read (`showTab`, `dropShownFrom`, `endTab`, `openTabWith`, `moveShown`).
- **Stale messages for a closed tab**: there are none to arrive. Every turn builds its race anew from `hiddenOf m`, and `takeTab`/`atTab`/`endTab` answer the model unchanged for an id that is gone. A read that loses the race gives its bytes back (geng-lang D1045, phase2-window §12.7).
- **Frame pacing for the shown tab**: `pending`, `urgent`, `last` and `frameAt` give one frame per `frames.every_ms` for output and an immediate one after a key (V31); no frame is drawn and no timer armed when nothing is pending. The blink timer is armed only with focus, a shown cursor and mode 12 (but see the blink finding for when the cursor is out of view).
- **Reply cap** (`replyCap`, `fedTerm`): a program that asks and never reads holds at most 1 MB of replies; keys and pastes are not dropped.
- **Window events against a flooding shown tab** (`windowToo`, FT25): taken after every read and notice of the shown tab.
- **Settings reload for the shown tab**: debounced by `reloadDelayMs`; a file that does not decode keeps the settings in force and says why; a host's window keeps its host's look (`forHost`, ST32); `restoreTurned` and `logTurned` act on the change of their setting. The 5 s save (`saveIfDue`) is TB10's by design and writes only on change.
- **Shell quoting for the host's paste command** (`folderWord`, `doubleQuoted`, `underSh`, `uploadCommand`): the folder is escaped for double quotes and the whole script for single quotes; the file name is puritty's own hex; `set -C` and the `.part` rename do what the comment says.
- **`controlled`/`userMaster`** (FT31): the socket path's length is held under Linux's limit, its name is 40 random bits, helpers run with `BatchMode=yes` and `ControlMaster=no`.
- **Menu geometry** (`menuBox`, `menuPaints`, `menuPress`, `menuKey`): clamped to the screen; the index is proved before `getProven`; the item list is never empty.
- **LastWindow**: the line is validated on read (state word, 10–1000 columns, 3–1000 rows); a bad file gives the settings' size.
- **TextEdit**: caret and anchor stay within the text for every key; an empty copy is not put on the clipboard by its callers; AltGr is neither Ctrl nor Alt in both window layers, so AltGr characters are typed.
- **Keys**, **Reason**, **Config**: thin; nothing found. `Config.bellSound` and the defaults match `Schema`'s keys that were checked (`scrollback.lines`, `images.read_files`).
- **Words**: the i18n tables for the settings window (not word selection, which is `Vt.wordAt` in the core: boundary set from `[selection] word_boundaries`, applied on reload for the shown tab). `say` falls back to English; `lookup` answers the schema's English when Korean has no key. Not checked key by key against `Schema`.

## Not covered

- `Main.geng` 5350 to the end, except the functions read to follow a call from the first half: `draw` (8402-8677), the tab functions (8798-9400, 9570-9718), `dialogUp` (8296-8388), `searchKey`/`found` (8073-8150), `rowHashes`/`kept` (7847-7891), `linkOpened` (7231-7252), the `Pasted` events (7076-7111), `pickerDue`. `handleOne`, `key`, `pointer`, `selecting`, `pasteInto`, `clipboardRequests`, the ssh screen, the tab bar and the close/rename/color boxes were not reviewed here.
- `Outbox`, `Diag`, `Dialog`, `Sending`, `Picker`, `PickerSftp`, `Restore`, `RestoreFile`, `RecentFile`, `SettingsSource`, `Hosts`, `TmuxMode`: called from this half, read only where a finding needed a fact from them (`TmuxMode.bells`).
- Whether `Task.race` prefers its first ready task natively was taken from docs/sftp.md FT25, not from the runtime; whether `Process.kill`, `Process.resize` and `File.writeSome` can fail on a pty whose program has gone was not established (core library).
- The Windows side of anything here (`app/windows/src/Platform.geng`, `Open.geng`) beyond the one `ShellExecuteW` call.
- Nothing was built, run or timed; the search cost and the hidden-tab frame cost are from reading.

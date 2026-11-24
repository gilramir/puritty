# Review slice 10: app/src/Main.geng 5350 to end, and Diag, ImageFile, Restore, RestoreFile, SessionFile, Recent, RecentFile, Folders, FolderFile, Palettes

Paths are relative to `/home/gram/prj/puritty`. Nothing was built or run; every
finding is from reading the code and its callers.

### MB1 · Closing a tab never closes its pty: the shell gets SIGTERM only, and the descriptor is kept for the window's life
- Where: app/src/Main.geng:9103-9122 (`closeShown`), 9066-9098 (`dropShownFrom`), 9683-9715 (`endTab`), 2520-2524 (the shown tab's end); app/src/Backend.geng:72-93 (`pty`, which has no close); `/home/gram/prj/geng-lang/packages/os/src/Os/Process.geng:477-481, 541-547`
- Kind: bug
- Severity: high
- Confidence: confirmed (the code path); plausible (the effect, not run)
- What: `closeShown` does `m.remote.kill` and then `dropShownFrom`, which puts the whole `Tab`, its `remote` with it, in `closedTabs`. `kill` for a local tab is `Process.kill child`, which is one `SIGTERM` to the child's pid. Nothing in `app/src` closes the terminal's handle (`grep File.close app/src` finds only Restore's locks and the side pipes), and `Os.Process.terminalHandle` says "It is this program's to close, and stays open, holding a descriptor, until it is." `closeShown` also does not wait, so the child is not reaped.
- Scenario: (1) Ctrl+Shift+W on a tab with an interactive bash: an interactive bash ignores SIGTERM, the pty master stays open so no SIGHUP comes, and the shell stays alive, unseen, until the window exits. With a job in front (`make`, `vim`), "Closing the tab ends it." is answered yes, and the job is not signalled at all: SIGTERM goes to the shell's pid, not the foreground group. `docs/tabs.md` Dnene51 says "closing ends the program at once" and rejects exactly this (programs "keep running, and get their hangup later"). (2) Every tab that ends, by `exit` too, leaves its master descriptor open: a window that lives for days and opens tabs by the hundred walks toward `RLIMIT_NOFILE`, and then a new tab does not start. (3) A killed child is never waited for (`closeShown`), so its record and pidfd stay.
- Fix: give `Backend` a `close` that closes the terminal handle (the hangup) and waits for the child, call it wherever a tab goes (`closeShown`, `endTab`, the shown tab's end at 2521, `reopened` replacing `remote`), and keep in `Closed` only what reopening needs (the term, name, color), not the dead `Backend`.
- Fixed: 2026-11-21. `Backend` has `hangUp`: a pseudo terminal's handle is closed (the hangup), its program sent `SIGTERM` and waited for beside the window; an ssh session is hung up. Ctrl+Shift+W (`closeShown`), `endTab` and the shown tab's end use it. Checked on Xvfb with an interactive bash as the shell, a second tab opened then closed: before, two shells and two pseudo terminals were left; after, one and one, no zombie. A tab ended by `exit`: two pseudo terminals left before, one after. `docs/tabs.md` TB11.

### MB2 · The box drawn and the dialog that takes the keys are chosen in two different orders
- Where: app/src/Main.geng:8426-8476 (`draw`'s `dialog`), 8304-8387 (`dialogUp`), 10621-10662 (`askCloseWindow`), 6830-6840
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `draw` picks the box as `startFailed`, `closing`, `dropAsk`, conflict, chooser, `pasteAsk`, renaming, coloring. `dialogUp`, which routes keys and presses, picks `startFailed`, `dropAsk`, conflict, picking, choosing, `pasteAsk`, `closing`, renaming, coloring. `closing` is second in one and seventh in the other. `Window.Close` calls `askCloseWindow` whatever else is up, and the drop, conflict and paste questions are raised asynchronously.
- Scenario: files are being sent on an ssh tab; the user asks to close (the window's button, or Ctrl+Shift+W before the conflict comes); the SFTP conflict question (`sendingAsks`) arrives. The window shows "Close this tab?" and Enter goes to `conflictKey`. Likewise with "Paste the picture as a file?" up and the window's close button pressed: "Close the window?" is drawn, Enter runs `pasteAnswer True` (a file written, its path typed into the program). Buttons are hit-tested against the hidden box.
- Fix: one function that answers the dialog up, used by `draw`, the key path, the pointer path, `pointerShape` and `hoverShapes` alike (`draw` should render `dialogUp m`); and decide whether a second question may be raised while one is up.
- Fixed: 2026-11-23, as MA4: `docs/tabs.md` TB20.

### MB3 · A paste's later pieces, a pasted picture and an OSC 52 read go to whichever tab is shown when they arrive
- Where: app/src/Main.geng:7076-7111 (`Window.Pasted`, `Window.PastedImage`), 7393-7500 (`pasteInto`), 7296-7309 and 7317-7340 (OSC 52 read), 7140-7159 (`Dropped`), 8933-8980 (`swapTab`)
- Kind: bug
- Severity: medium
- Confidence: confirmed (logic); the window delivers a large paste as INCR pieces over several turns (packages/x11/src/Ext/puritty_x11.c:1673 "a paste of megabytes over ssh -X does not stop the window")
- What: the window has one paste under way, but `pasting` and `clipRead` are per tab (swapped by `swapTab`), and `imagePaste`/`dropGather` are the window's. Each `Pasted more` is applied to the model's shown tab: `first = m.pasting == Nothing`.
- Scenario: (a) a multi-megabyte paste into tab A over a slow X link; the user presses Ctrl+PgDn, or A's program ends, between pieces. The rest of the text is sent to tab B, with a fresh `ESC[200~` if B asked for brackets, or unbracketed into B's shell, where each line runs. A never gets `ESC[201~` and its `pasting` stays `Just`, so its program stays in a paste and A's next paste starts without a bracket. (b) with `osc52_read = "allow"`, tab A asks to read the clipboard, the user switches before the text comes: the clipboard is pasted into tab B as typed text, and A's `clipRead` stays `Just` for good, so every later paste in A is sent to its program as an `OSC 52` answer and no other read is made (7298). (c) a picture's pieces gathered while the tab changes are pasted as a file path into the other tab.
- Fix: remember the tab id a paste (or read, or image, or drop) was asked for, in the window's state, and deliver each piece with `atTab` to that tab; if the tab is gone, drop the rest. End a tab's open bracket when its paste is abandoned.
- Fixed: 2026-11-23, as MA9: `docs/phase3-select.md` §25, `harness/tabpaste.py`.

### MB4 · Text the input method commits skips the search bar, the folder picker and the questions, and is sent to the program
- Where: app/src/Main.geng:6855-6887 (`Window.Commit`), 8254-8275 (`spotOver`), 8643-8644
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `Window.Commit` looks at `renaming`, `coloring`, `ownScreenUp` and tmux's prompt, and otherwise does `send text`. It does not look at `m.search`, `m.choosing`, `m.picking`, `closing`, `pasteAsk`, `dropAsk`, `startFailed` or the conflict question, all of which take the keys in `Window.Key` (6585-6696). `draw` meanwhile puts the IME's window at the search field or the picker's caret (`spotOver { picker, box, search }`).
- Scenario: a Korean or Japanese user opens the search bar (Ctrl+Shift+F) or the folder chooser's path field and types with the IME: the candidate window sits at the field, and on commit the text goes to the shell under it, not into the query; with "Close this tab?" up, committed text reaches the program the question covers.
- Fix: route `Commit` by `dialogUp` and `m.search` as keys are: into the search query (`found`), into `Picker.key`'s text for the chooser and the working model, and dropped for the yes/no questions.
- Fixed: 2026-11-23, `docs/phase3-input.md` §16. `Window.Commit` is routed by `dialogUp` as keys are: into the picker's and chooser's fields, into the search bar's query, dropped for the questions and the color box. Test: the IME gate's `hangul-search` on fcitx5-hangul and ibus-hangul: before, the program received 한.

### MB5 · Every read of a tab not shown forces an unpaced frame of the shown tab
- Where: app/src/Main.geng:9649, 9656 (`behind` sets `urgent = True`), 1692-1703 (`frameAt`), 2605 (`step`), 8489-8490 and 9792-9828 (the bar rebuilt in each frame)
- Kind: speed
- Severity: medium
- Confidence: confirmed (logic; not measured)
- What: `behind` feeds a hidden tab with `atTab ... { m | urgent = True }`. `urgent` is the window's, not swapped, and `frameAt` answers `m.last` for it, so `step` draws at once, as for a key (V31), instead of at most every `frames.every_ms`. A shown tab's own output only sets `pending` and is paced.
- Scenario: a build or `yes` in a background tab: each read (a few KB) is followed by `draw`: `View.frameWith` over the shown terminal against the shadow, `tabBar` (every tab's label rebuilt, `Text.width` measured for each, `Array.findFirst` over the hidden ones per tab), `Bytes.flatten` and `Window.draw` with the bar's fill and every label drawn again, though at most one mark in the bar changed. With several busy background tabs the loop spends its time drawing a screen that did not change, hundreds or thousands of frames a second. The same holds with a note or the scrollbar up, when by `phase3-select.md` §23 each of those frames draws every cell.
- Fix: in `behind`, set `pending` (paced) and only when the tab's `activity` or `bell` mark, label or status actually changed; keep `urgent` for what a key causes. Cache the bar's records and send them only when they change.
- Fixed: 2026-11-24, with MA7 (`docs/tabs.md` TB21). The bar's records are not cached; the frames they were drawn in are no longer asked for.

### MB6 · OSC 52 writes of a tab not shown queue without bound, and are applied when it is next shown
- Where: app/src/Main.geng:4104 (`clips = m.clips ++ taken.clips`), 7264-7312 (`clipboardRequests`, run by `loop` on the shown tab only, 2094), 8946/8969
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: `fedTerm` appends each read's clipboard requests to the tab's `clips`. Only the loop's `clipboardRequests` empties it, and that reads `m.clips`, the shown tab's. A hidden tab's list only grows; `phase3-select.md` §16 allows a write of 8 MB of base64 (6 MB of text) each.
- Scenario: a program on a remote host in a background tab (or `cat` of a hostile file there) emits OSC 52 writes in a loop: 6 MB kept per write, with no cap, and `++` copying the list each read, until the window runs out of memory. When the user at last shows the tab, every queued write is made in turn (`Window.select` once each), and the clipboard ends as whatever the program wrote hours ago.
- Fix: keep at most the last write per selection (a later write replaces an earlier one) and at most one read; or run `clipboardRequests` for hidden tabs too, if a background tab is meant to be able to copy.
- Fixed: 2026-11-23, `docs/phase3-select.md` §24. `ClipQueue.queued` keeps one read, the writes before it, and after it the last write to each selection: at most five wait. Test: the app's `clipboard` suite; with the old append a thousand writes and two reads kept all 1,002.

### MB7 · An unbracketed paste of CRLF text sends two CRs a line, and a CRLF cut between two pieces does too
- Where: app/src/Main.geng:7358-7390 (`lineEnds`), 7416 (`lineEnds (Paste.piece bracketed text)`); vt/src/Vt/Paste.geng:64-80 (`byteOut`)
- Kind: bug
- Severity: low
- Confidence: confirmed (logic)
- What: `lineEnds` is documented "CRLF one CR" (`docs/tmux.md` TM95) and drops an LF that follows a CR. But it runs after `Paste.piece bracketed`, and with `bracketed = False` `byteOut` has already made each LF a CR, so `\r\n` reaches `lineEnds` as `\r\r` and passes unchanged. `lineEndsFrom` also starts each piece with `last = -1`, so a `\r` ending one piece and the `\n` starting the next give two CRs, bracketed or not.
- Scenario: on X11, text with CRLF ends (copied from a browser's textarea, a Wine or remote-desktop program, a DOS file in an editor) pasted into a program that has not asked for bracketed paste (an older shell, `cat > file`, a Python REPL before 3.13): every line is followed by an empty one, which in a REPL ends an indented block early. Windows is spared by `read_clipboard` making CRLF LF first.
- Fix: do the line-end rule on the pasted text before `Paste.piece` (or always call `Paste.piece True` for the body, since `lineEnds` makes every LF a CR anyway), and carry "the last byte was CR" across pieces beside `pasting`.

### MB8 · Tabs past the window's right edge cannot be seen or clicked
- Where: app/src/Main.geng:9816-9828 (`barTabs`), 9837-10027 (`tabBar`), 10045 (`barPress`)
- Kind: bug
- Severity: low
- Confidence: confirmed (logic)
- What: `barTabs` lays the tabs out from x = 2, each `min 400 (Text.width ...) + 2 * cw` wide, with no regard for `m.term.cols * cw`; `tabBar` draws them all and `barPress` hit-tests the same positions. Nothing shrinks, scrolls or elides. `docs/tabs.md` says nothing of a bar that does not fit.
- Scenario: an 80-column window with a dozen tabs titled by their shells (`user@host: ~/some/dir`, up to 24 characters each): the tabs from the fifth or sixth on, the shown one among them after Ctrl+Shift+T, are drawn outside the window. The user cannot see which tab is shown, nor its bell and activity marks, nor click it.
- Fix: when the sum of widths passes the window's, shrink the labels evenly to a floor, and past that scroll the bar so that the shown tab is in view.

### MB9 · `lineEnds` builds each pasted piece as an `Array UInt8`, a `pushLast` a byte
- Where: app/src/Main.geng:7364-7390
- Kind: efficiency
- Severity: low
- Confidence: plausible (whether `Array.pushLast` on a uniquely held array is in place is the compiler's)
- What: `lineEndsFrom` pushes every byte of the piece onto an `Array UInt8` and then `Bytes.fromUInt8s` copies it: a boxed-array element per byte, on top of `Paste.piece`'s `Bytes.Builder` pass, and `tmuxBytes` is computed too (a second `Paste.piece` and `lineEnds`) for a tab not under tmux.
- Scenario: a 50 MB paste: 50 M array pushes and at least four full copies of each piece; if `pushLast` copies, quadratic per piece.
- Fix: use `Bytes.Builder` as `Vt.Paste.pieceFrom` does, sized by the piece's length, or fold the rule into `Paste`'s pass; compute `tmuxBytes` only under tmux.

### MB10 · `Diag.lines` decodes and rewrites each pasted piece although the log is off
- Where: app/src/Main.geng:7440-7476; app/src/Diag.geng:531-547
- Kind: efficiency
- Severity: low
- Confidence: confirmed (Geng evaluates arguments before the call)
- What: `pasteInto` builds the log line's text, `Diag.lines text` in it, as an argument of `Diag.add`, which returns the log unchanged when it is off. `Diag.lines` does `Bytes.toStringLossy` of the whole piece, `String.replace "\n" ""` over it and two `String.count`s.
- Scenario: every paste piece is decoded to a string and copied again to count its lines, for a line that is thrown away in the usual case (`[debug] log` off).
- Fix: guard with `Diag.isOn m.diag` (or give `Diag.add` a thunk), and count `0x0A` bytes in the `Bytes` directly.

### MB11 · `Restore.fresh` ignores whether its lock was taken, and another window's `others` can remove a new window's lock file under it
- Where: app/src/Restore.geng:151-163 (`fresh`), 193-240 (`others`, `anyRunning`), 68-84 (`take`)
- Kind: bug
- Severity: low
- Confidence: plausible (a race of microseconds; not run)
- What: `fresh` opens `ID.lock` and then `File.tryLock handle |> Task.map (\_ -> { id, lock })`: the answer is dropped. `anyRunning`, run by a window closing by its button, takes every other `*.lock` it can, and where `ID.toml` does not exist calls `forget`, which removes the lock file.
- Scenario: window C starts and has opened `c.lock` but not yet locked it; window X, closing, takes `c.lock`, finds no `c.toml` (C has not saved yet) and removes `c.lock`. C goes on with a lock on an unlinked file (or none, its failed `tryLock` not looked at) and saves `c.toml` every five seconds. The next puritty to start finds `c.toml`, creates a new `c.lock`, locks it, and restores C's tabs while C still runs; both then write `c.toml`, and when one ends it forgets the other's state.
- Fix: in `fresh`, fail (or try another id) when `tryLock` answers False, and after locking check that the path still names the locked file (compare `handleMetadata` with the path's metadata), retrying if not; in `anyRunning`, do not remove a lock file younger than a few seconds.

### MB12 · The recent and folder files are read, changed and written with no lock, through one shared `.new` name
- Where: app/src/RecentFile.geng:73-96 (`remember`, `forget`, `write`); app/src/FolderFile.geng:51-73 (`change`, `write`); app/src/SessionFile.geng:114-123
- Kind: bug
- Severity: low
- Confidence: confirmed (logic)
- What: `remember` is `load` then `write (added ...)`; `write` puts the text in `recent.toml.new` and moves it. Two processes use the same temporary name. `FolderFile`'s header says "Each change reads the file first, so another window's changes since are kept", which holds only when the two do not overlap.
- Scenario: a restore opens several windows at once (`spawnSelf ["restore"]`, each a process), or two `puritty --host` are started together from the host list: both read the same list, and the later move loses the other's entry. Worse, both truncate and write `recent.toml.new` at once: a shorter text written over a longer one's start leaves a tail of the longer, and the move puts a file that is not TOML in place; `fromText` then answers `[]` and the next `remember` writes a list of one, the history gone. Errors are swallowed (`Task.onError (\_ -> Task.succeed {})`), so nothing says so.
- Fix: a temporary name of the process's own (`recent.toml.<pid>.new`), and a lock file held across the read-change-write (`File.tryLock`, as `Restore` uses), or a re-read and retry when the file changed between read and move.

### MB13 · The log writes tab titles and a program's name, which the log's contract says are never written; `Diag.command` shows some typed words
- Where: app/src/Main.geng:10634-10661 (`askCloseWindow`: `logLine "close" ("question shown: " ++ ...)` with `tabLabel t.info t.term.title`), 10686-10711; app/src/Diag.geng:357-412, 428-434 (`command`, `shownWord`, `isKeyName`)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: `docs/diagnostics.md` DG2 and `Diag`'s header: "What is typed, pasted or shown is never written", so that "the log can then be read at work and its lines passed on"; DG6 has "a title not written". The window's close question logs each busy tab's label, which is the program's title (OSC 0/2) when the tab has no name, and the foreground program's name. `Diag.command` shows a quoted tmux argument whole when it contains `#{`, or starts with `C-`, `M-` or `S-` and is longer than two characters, or equals a key's name.
- Scenario: a shell that sets its title to `user@host: ~/clients/acme` or `vim passwords.txt`, and the window's close button: that title is in the log file. A window renamed at tmux's prompt to `S-ecret plan` or a search for `M-x foo`: the typed text is in the log, where any other text would be `<12 chars>`.
- Fix: log the close question by counts and tab ids (`3 busy tabs: 0, 2, 5`), as links are logged by length (7245); in `shownWord`, take a key's name only for the arguments of commands whose argument is a key (`send-keys`, `bind-key`), and a format only for puritty's own formats.

### MB14 · A closed tab is lost, with its scrollback, when opening it again does not start
- Where: app/src/Main.geng:9537-9562 (`reopenTab`), 9246-9252 (`openTabWith`'s `Err`)
- Kind: bug
- Severity: low
- Confidence: confirmed (logic)
- What: `reopenTab` takes the closed tab out of its slot (`Builder.swap slot Nothing`) and passes it as `kept`; when `starting` fails, `openTabWith` answers `{ m | startFailed = Just why }`, where `m` already has the slot empty, and `with.kept` is dropped. (`bellsHeard`, raised for the lost tab's bells, is put right by `bellRung` on the next turn, which takes a lower total as it is.)
- Scenario: Ctrl+Alt+Shift+T while the shell's program cannot start (its directory's file system gone, `fork` refused, the program in the settings removed): the box says the tab did not start, and the scrollback the user wanted back, kept for ten minutes by TB11, is gone on the first try.
- Fix: on `Err`, put the `Closed` back in its slot (and take the bells back) before answering.

### MB15 · `handleOne` carries a `remote` beside `m.remote`, and four paths go on with the stale one
- Where: app/src/Main.geng:6691 (`menuKey`), 6843 (`menuChosen`), 7043 (`menuPress`), 7047 (`openMenu`), against 6594-6711 (`handle next.remote`)
- Kind: design
- Severity: low
- Confidence: confirmed (logic); the wrong outcome needs two events in one take
- What: the dialogs' and the tab keys' branches continue with `handle next.remote ms rest next`; the menu's four continue with `handle remote ms rest next`. A menu item can change the shown tab (`menuDo`: `Reopens` → `reopenTab`, `OpensTab` → `openTab`, 3690-3706). `sshKey remote k m` then uses that parameter for `remote.answer` and `remote.reconnect` (6137, 6237).
- Scenario: Enter on the menu's "New tab" in a host window, and a second key in the same take of events: the key is handled on the new tab's ssh screen with the old tab's backend, so an answer or `R` (reconnect) goes to the other tab's session. Rare, but the parameter is a second copy of a field of the model that every caller must remember to refresh.
- Fix: drop the `remote` parameter from `handle`, `handleOne`, `owned`, `key`, `sshKey` and read `m.remote` where it is used.

### MB16 · `ImageFile.read`: a temporary file is not removed when its read fails, and a load is read whole inside the loop with three copies
- Where: app/src/ImageFile.geng:36-37 (the doc), 71-112 (`checked`), 116-130 (`readUpTo`); called from app/src/Main.geng:4027-4055 (`filesRead`, inside `feedTerm`)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed (logic). Only with `[images] read_files = true`, which is off by default, and only for a local tab.
- What: (1) the doc says "A temporary file is removed once its checks pass, read or not"; the removal is in the `andThen` after `File.withHandle`, so a failed open, seek or read, "not a regular file" and "too large" all leave it. (2) the file's kind and size are taken by `File.metadata` on the path and the file is then opened by path: a program that swaps it for a FIFO in between has the window's loop wait in `open` for good, and one on a slow mount (NFS, sshfs) holds every tab for the length of the read. (3) `readUpTo` gathers pieces, `Bytes.flatten`s them and `Bytes.slice`s the result: a 400 MB load (the cap, above the 320 MB the terminal's images may hold) is about 1.2 GB for a moment.
- Scenario: a local program (or `cat` of a file of escape sequences) sends `ESC _G t=f,...` naming a 400 MB file on a slow mount: every tab of the window stops until it is read.
- Fix: open first, then `File.handleMetadata` on the handle for kind and size (no window between check and read); remove a temporary file in every branch after its checks pass, or correct the sentence; read into one builder of `count` bytes; cap a file load at the image limit.

### MB17 · `ownTerm`'s question text is never drawn: the same questions are written twice and have drifted
- Where: app/src/Main.geng:6442-6544 (`asked`, `typingAsked`, the DECSC/DECRC `mark`), against 6331-6414 (`questionDialog`), 8478-8486
- Kind: dead-code
- Severity: low
- Confidence: plausible (followed every case of `dialogOf`; not run)
- What: `draw` calls `ownTerm m boxed`, and `ownTerm` writes the question only when `boxed` is False. While the ssh screen asks or has failed, `dialogOf` answers a box for every question (`HostKeyChanged`, `TrustHostKey`, `Password`, `Passphrase`, `Responses` with a prompt left, and `failed`), so `boxed` is True and `question = []`. The two texts already differ ("Esc: skip this key" in the box, "Esc: do not use this key" on the screen; the box's failed hint against the screen's).
- Scenario: about ninety lines, with their own cursor handling, that a reader must take for live, and a second place to forget when a question's wording or keys change.
- Fix: delete `asked`, `typingAsked` and the cursor marks from `ownTerm` (keeping the heading and the lines), or have both made from one description of the question.

### MB18 · A paste while the ssh question is up does not reach the question's field
- Where: app/src/Main.geng:7076-7090 (`Window.Pasted` → `pasteIn`), 7694-7697 (the paste button), against 6866-6868 (`Commit` → `sshTyped`)
- Kind: bug
- Severity: low
- Confidence: confirmed (logic); that `Session` drops `Keys` before it is connected was read at packages/ssh/src/Ssh/Session.geng:725-738 but not followed into `withConnection`
- What: with puritty's own screen up, keys go to `sshKey` and IME text to `sshTyped`, but pasted text goes to `pasteIn` → `send` → the session's `Keys`. The paste keys are swallowed by `sshKey` (6677-6685), while the middle button still asks for a paste.
- Scenario: a user with a password manager middle-clicks to paste the password into "password for gilbert@build:": nothing shows in the field, and the text is handed to the session instead. If any path delivers `Keys` queued before the shell starts, the password is typed at the shell's prompt.
- Fix: in `Window.Pasted`, when `ownScreenUp m` and a field is asked, give the text to `sshTyped` (control characters dropped, as it does); let the paste keys through `sshKey` too.

### MB19 · The dialogs are listed in six places, and four groups of this half are modules in waiting
- Where: app/src/Main.geng:6585-6696 (keys), 6947-7074 (pointer), 6855-6887 (IME), 8426-8476 (`draw`), 2389 (`pointerShape`), 2420 (`hoverShapes`); and 5348-5810, 10264-10615
- Kind: design
- Severity: medium
- Confidence: confirmed
- What: which dialog is up is decided separately by the key path (`dialogUp`), the pointer path (`dialogUp` with three cases lifted out), the IME path (its own `if` chain), `draw` (its own order), and two boolean chains for the pointer. Two findings above (the box drawn against the keys' dialog; IME text) are these lists disagreeing. Each question is also three near-copies (`dropBox`/`dropKey`/`dropPress`, `pasteBox`/`pasteKey`/`pastePress`, `closeBox`/`closeKey`/`closePress`, `startFailed*`, `color*`, `rename*`): the same key tests (`0xFF0D || 0xFF8D || 0x79 || 0x59`), the same `Dialog.buttonAt` hit test. `Main.geng` is 10,922 lines in one module with a 170-field model; nobody can hold it.
- Scenario: a new question (broadcast input's, say) must be added in six places and will be missed in one, as `closing` and `Commit` were.
- Fix: one `Dialog`-valued function used by all six; a question as data (`{ box, onYes, onNo, extraKeys }`) with one key handler and one press handler. Then split, each pure and testable alone: (1) `SshScreen` (5823-6578: `sshAsked`, `sshNoticed`, `endsSession`, `commandFailed`, `cleanText`, `sshKey`, `questionDialog`, `ownTerm`), a function from screen and key to screen and an answer to send; (2) `TabBar` (9721-10040: `tabLabel`, `shortTitle`, `barTabs`, `tabBar`, `mix`, the hit test), over an array of labels; (3) `ClosedTabs` (9408-9532), over `Builder (Maybe Closed)`; (4) `Selecting` (7684-7940: `selecting`, `extended`, `pointAt`, `rowHashes`, `kept`, `highlightOf`), where `Selection.mode : Int` (0, 1, 2) would be a type; (5) `Tabs` (8833-9060, 9601-9636: `takeTab`, `swapTab`, `atTab`, `showTab`), the one place that knows which fields are a tab's and which the window's; today that is only the two field lists in `swapTab`, and `pasting`/`clipRead` being a tab's while the paste is the window's is the finding above.

## Looked at and found sound

- `draw` (8402-8677): which frame is built for tmux, the own screen, a menu, a view scrolled back; the shadow reset when an overlay comes or goes (`over || m.overlaid`), which `phase3-select.md` §23 decides (every cell while anything is over them); the title made of the program's with puritty's own while its screen is up; `lost` set when `Window.draw` answers nothing. The diff against the last frame and the scroll by copy are `Vt.View`'s (`frameWith`, `inked`), outside this slice.
- Text from the server shown on puritty's own screen and boxes: `cleanText` is applied to status lines, banners, failures, prompts, names, instructions and host names before they are written into `ownTerm`'s escape text or a box; a session's last lines (`lastWritten`) are cleaned too.
- Tab bookkeeping: `takeTab`/`swapTab`/`atTab` put back what they take; `showTab`, `dropShownFrom`, `endTab` and `openTabWith` set `order` and `shown` in the same update as the swap; `atTab`'s work (`feed`, `sshTold`, `flush`, `resizeShown`, naming, coloring) does not reach `closeShown`/`dropShown`, so `shown` not following the swap inside `atTab` is harmless today. A read or a writable for a tab already gone falls through `takeTab` with nothing done.
- `reopened` and `openTabWith` taking the shown tab's host: a window's tabs are all one host's or all local (`stateOf`'s comment), so it is by design.
- Closed tabs (TB11): five slots, the oldest replaced, ten minutes, `Clock` comparisons the right way round.
- The questions' answers carry the tab id and are refused when another tab is shown (`dropAnswer`, `pasteAnswer`, `closeAnswer`).
- Selection: `selecting`, `extended`, `highlightOf` clamp to the screen; `kept` drops a selection on a screen switch or a changed row; PRIMARY and CLIPBOARD (`owned`, `pasteFrom`, `copyToClipboard`) as `phase3-select.md` §14-§15 and `windows.md` WS27 say; OSC 52 reads only under `osc52_read`.
- `Vt.Paste.piece` replaces ESC and the other control bytes byte by byte, so a `ESC[201~` cut between pieces cannot end a bracket.
- `Restore`: the lock is `flock`/`LockFileEx` per open handle, so a window probing its own id fails as it should; `save` is write-then-move under the window's own id; the saved windows' folder (`.../windows`) is apart from `recent.toml` and `folders.toml`, so `claim`'s forgetting of an unreadable state cannot remove those. `restoredConfig` clamps columns to 10-1000 and rows to 3-1000; `shown` is clamped. The number of saved tabs is not capped (the user's own file).
- `RestoreFile`, `Recent`, `Folders` decoders: unknown rows are passed over, a file that is not TOML is none, hex paths are checked digit by digit; `Recent.quoted` follows `CommandLineToArgvW`'s rules.
- `SessionFile`: pid reuse is acknowledged in its header; a non-numeric name is passed over; `isRunning` refuses pids below 1.
- `ImageFile`: absolute path, `realPath` before the `/proc`, `/sys`, `/dev` test, temporary files only under real temporary folders (`Path.relativeTo` answers `Nothing` for a path outside), offset and size clamped to the file, errors in Kitty's words.
- `Diag`: keys with text logged as `text`, pastes by size, `send-keys -H` by count, `set-buffer` by length; lines flushed every 250 ms and cleared whether or not the write worked.
- `Palettes`: the sixteen colors of each scheme checked against Ghostty's and Windows Terminal's defaults from memory; no difference seen.
- Broadcast input (`docs/broadcast.md`) is a survey; nothing of it is in the code.

## Not covered

- The first half of `Main.geng` beyond what these functions call (`loop`, `race`, `step`, `feed`, `fedTerm`, `filesRead`, `sshTold`, `restoreInto`, `saveNow`, `savedAtEnd`, `finishTabs` were read; `imagePasted`, `sendImage`, `filesDropped`, `startPending`, the chooser, the menus' bodies, `windowState` were not).
- `Dialog`, `Picker`, `Sending`, `TmuxMode`, `TabOrder`, `Clock`, `Remembered`, `Outbox`: only their signatures as used here.
- The C side of the paste (INCR timeouts, whether every `paste` ends in a final `Pasted`), which decides whether `clipRead` can also stick with no tab switch.
- Whether `Array.pushLast` and `++` on a uniquely held array copy in compiled Geng (the two efficiency findings depend on it).
- Nothing was run: the process-survives-close finding in particular should be confirmed with `ps` after Ctrl+Shift+W on a bash tab.

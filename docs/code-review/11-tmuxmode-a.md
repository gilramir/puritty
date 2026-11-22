# Review: app/src/TmuxMode.geng, lines 1 to 8600

Read in full: lines 1 to 8950, plus the parts of the second half that calls from the first
reach (`runHeld`, `runLine`, `plainLines`, `sendAsking` callers, `tick`, `dueAt`, `askCopy`,
`copyLine`, `forgetPane`, `resized`, `drawText`, `pollsFor`, `themeAsked`). Also read for the
calls: `packages/tmux/src/Tmux/Control.geng` (whole), parts of `Command.geng`, `Syntax.geng`,
`Bindings.geng`, and `Main.sendCommands`/`Main.feed`. Nothing was built or run; "confirmed"
means confirmed by reading the code and its callers, and tmux's own behaviour is taken from
`docs/tmux.md`, `docs/tmux-checks.md` (TK10.1's measurements) or, where said, from memory of
tmux's source.

One thing about the reply queue that several findings below rest on: `ours` (2623) pops the
head of `expecting` for every block with flags 1, and a block arriving on an empty queue is
dropped. So a reply *too many* shifts every answer by one only until the queue next runs
empty, and then it is in step again; a reply *too few* never heals: every later answer is
read as the answer to the question before it, until the next attach.

---

### TA1 · A typed line that tmux parses to no command leaves the reply queue one behind for good
- Where: app/src/TmuxMode.geng:7173-7207 (`closePrompt`), 7235-7258 (`sendAsking`), 10222-10243 (`runOne`), 2623-2661 (`ours`)
- Kind: bug
- Severity: high
- Confidence: plausible (tmux's side is TK10.1's "a blank line: nothing, from 3.0" plus tmux's parser as I remember it; not run)
- What: a line typed at puritty's colon prompt is split by `Syntax.lines` and each piece is sent with `{ command = line, expect = ForRan }`, then `windowQuery`. Only an empty line is filtered (`String.trim line == ""`). `Syntax.tokens` does not know tmux's comments, assignments or `%` directives: `# note`, `FOO=bar`, `%hidden X=1`, `%if ...` each become one "command" and one expectation.
- Scenario: on tmux 3.0 or later the user types `:FOO=bar` (a documented way to set a variable) or pastes a commented line from a tmux.conf. tmux's parser makes no command of it, so, as for a blank line (TK10.1), no `%begin`/`%end` comes. `ForRan` then takes `windowQuery`'s reply (the `W @1 %3 ...` line opens in a view as the command's output), `ForWindow` takes the next reply, and so on for the rest of the session: captures are read as pane info, a pane is rebuilt from the wrong block, and an expectation that runs its reply as commands (`ForRunExpanded`, `ForCondition`, `ForMenuCommand`) is given the reply of whatever was asked after it.
- Fix: put the fence (`display-message -p puritty-fence`) after every line the user typed, not only after `runsCommands` ones, and let the fence's own reply end a `ForRan` that got no block (today `ours` only handles blocks before the fence, not a missing one). That makes a user line safe whether it yields zero, one or many blocks, and does not depend on puritty's tokenizer agreeing with tmux's parser.
- Fixed: 2026-11-21. Checked on tmux 3.8: `FOO=bar`, `# a comment` and `%hidden X=1` in control mode get no block. Every typed line is now followed by the TK10 fence, and the fence's reply where the line's was waited for answers the line with nothing. Test: "a typed line tmux makes no command of leaves the replies in step", on each tmux; `docs/tmux.md` TM106.

### TA2 · `endsClient` takes `detach-client -t another-client` for this client leaving: nothing is sent again
- Where: app/src/TmuxMode.geng:906-922 (`endsClient`), 5559-5566, 7192-7199, 10180-10185 (the three places that set `ending = 1`), 11578 and 11752-11764 (choose-client's choice), app/src/Main.geng:3342-3353 (`sendCommands`)
- Kind: bug
- Severity: high
- Confidence: confirmed
- What: `endsClient` is true for any `detach-client`/`detach` whose flags hold no `a`, and for `kill-server`. `ending` goes 1, then 2 in `afterSent`, and from then `Main.sendCommands` logs and drops every command; only `Exited` resets it.
- Scenario: (1) `prefix D` (choose-client), Enter on a row that is another client: the template `detach-client -t '%%'` filled with that client's name goes through `runLine` → `plainLines`, `endsClient` says yes, the other client is detached, this one stays attached and mute: every key, paste, resize and click is dropped until tmux is detached from somewhere else. (2) `:detach-client -s other-session` or `-t /dev/pts/N` at the prompt: the same. (3) A detach that tmux refuses (`detach-client -t nosuch` → `%error`): the same, since nothing looks at the reply. TM92 describes only "`detach-client` or `detach` without `-a`".
- Fix: decide from the arguments (`-t` naming a client other than `clientName`, `-s` naming another session: not this client); and clear `ending` when the command's reply is an `%error`, or when anything but `%exit` arrives after a short wait, so the state can always be left.
- Fixed: 2026-11-21. `endsClient` reads `detach-client`'s flags as getopt does, and a `-t` naming another client than `clientName` does not end this one; when the reply to the line that would detach is `%error`, `ending` goes back to 0. A `-s` is still taken as this client's session. Test: "a detach naming another client does not end this one", on each tmux; `docs/tmux.md` TM105.

### TA3 · Control mode is entered from in-band bytes with no check, and text read from that stream is later written back as command lines
- Where: packages/tmux/src/Tmux/Control.geng:195-196 (entry on `ESC P 1000 p`), app/src/TmuxMode.geng:2423-2432 (`Entered`), 2502-2517 (first reply starts `attachQueries`), 2804-2816 (`ForKeys`), 3039-3089 (`ForCaps` decides `byTable`), 5489-5493 (a binding's command sent as a line), app/src/Main.geng:3936 (every read goes through `TmuxMode.read`)
- Kind: security
- Severity: high
- Confidence: plausible (each step read in the code; not exercised)
- What: any bytes the terminal receives that hold the entry sequence switch the tab into control mode; nothing ties it to the user having started `tmux -CC`. From then on the stream is believed: its answer to `list-commands` chooses which code path keys take, and its answer to `list-keys` becomes `keys.bindings`. On the path for a tmux without `send-keys -K`, a key with a binding is answered by writing the binding's command text, unquoted, as a line to the pty (`[ Command.bindingLine way.ran ]`).
- Scenario: output that is not a tmux client (a file shown with `cat`, a remote service's output, anything that can print raw lines) can therefore put text of its choosing on the terminal's input the next time the user presses a bound key, where whatever program reads the tty next takes it as typed. This is the same class as the tmux-integration issue fixed in another terminal in 2019. TK13/TK14's stray-line check ends a false control mode once a non-`%` line appears, but a stream that keeps writing well-formed lines is not stopped by it. Separately, the false mode replaces the screen and swallows keys for as long as it lasts.
- Fix: do not enter control mode silently. Either ask the user on entry unless the tab's own command line (or the last typed line) started `tmux -CC`, or keep the mode but never write stream-derived text as a bare line: send bindings only by key (`send-keys -K`) or refuse to follow tables on a tmux that lacks it until the user has confirmed the session. A cap on the entry sequence appearing mid-output (only at the start of a line after a shell prompt) narrows it further but is not enough alone.
- Fixed: 2026-11-22, as Gilbert decided (README, For the owner to decide): `docs/tmux.md` TM108. Control mode is entered at once only when expected: the tab's command, or the line typed before Enter, started `tmux -CC`; otherwise the tab asks "Start tmux control mode?" and holds the bytes until answered, refused they are its text. Tests: the tmux package's reader (asked and held, yes, no, an expectation used up, the 1 MiB bound) and the app's TmuxMode suite (asked and refused, asked and started, typed lines, `startsTmux`).

### TA4 · After the active pane or window changes, named keys go to the old pane and text to the new one
- Where: app/src/TmuxMode.geng:5455-5481 (`nobodyBinds`, `Command.sendKeyTo s.active`), 7309-7321 (`byName`: text by `send-keys -K -H`), 4140-4145 and 4147-4149 (when `active` is learned)
- Kind: bug
- Severity: medium
- Confidence: confirmed (mechanism); the window is one to two round trips
- What: on tmux 3.4 and later a named key no binding takes (Enter, BSpace, Tab, the arrows, F-keys) is sent `send-keys -t %<s.active>`, where `s.active` is puritty's belief; typed characters go `send-keys -K -H`, which tmux gives to the pane that is active *in tmux*. `s.active` changes only when `%window-pane-changed` or the `ForWindow` reply is read.
- Scenario: `prefix %` (or `prefix o`, `prefix n`, `prefix c`) and then `ls` Enter typed ahead over a link with some latency. tmux has already made the new pane active: `l` and `s` reach the new pane, Enter reaches the old one, which runs whatever stood on its command line; the new pane is left with `ls` unentered. Before 3.4 all bytes go to the old pane (`bytesTo s.caps s.active`), which is at least one place, but the wrong one. TM50 chose the by-id route for tmux's `-K` fault and does not mention this.
- Fix: while a command that can move the active pane is unanswered (a binding sent, a flags-0 block seen and `windowQuery` out, `%session-window-changed` read), hold named keys in order behind it, or send them `-K` during that window; or target the key with `-t` only when no such question is in flight.

### TA5 · A change in the status line's row count sends a resize that nothing waits for
- Where: app/src/TmuxMode.geng:4240-4253 (`SubscriptionChanged`), reached also from 3150-3176 (`ForPoll`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `resize = [ sizeCommand next.caps ... ]` is appended with `commands = acc.commands ++ resize`; every other sender goes through `ask`/`sent`/`sendAsking`, which add an `Asked`. `refresh-client -C` answers with an empty block, flags 1 (TK10.10), so one more reply comes than is waited for.
- Scenario: tmux's look with `status off`, `status 2` or a binding that toggles `status`: about a second after attach, or after the toggle, the notification arrives and the resize goes out. Whatever puritty sends before that resize's reply is read is answered one early until the queue empties: a pane's `recapture` line then rebuilds the pane from the saved-screen capture (usually empty: a blank pane), a `ForWindow` is lost. On a local tmux the window is tiny; over ssh it is the round trip.
- Fix: `sent [ sizeCommand ... ] next` in both branches, as `resized` does.
- Fixed: 2026-11-22. The size sent when the status line's rows change goes through `ask`, its reply waited for; and the state counts replies that came when no question waited (`unasked`), which the diagnosis shows, so a desync is seen. Test: "the size sent when the status line's rows change waits for its reply", on each tmux: one reply with no question before, none after.

### TA6 · Before tmux 3.4 a binding of several commands is sent on one line and waited for once; `source-file` in it has no fence
- Where: app/src/TmuxMode.geng:5489-5493, 5544-5557 (`sent commands`), packages/tmux/src/Tmux/Command.geng:1403-1417 (`bindingLine`)
- Kind: bug
- Severity: medium
- Confidence: confirmed (the count); the effect heals when the queue empties
- What: `[ Command.bindingLine way.ran ]` is one string with ` ; ` between the binding's commands, and `sent` adds one `ForNothing` for it. tmux answers each command (TK10.1). `runsCommands` is not consulted on this path, so `source-file`'s commands, each a block of this client's from 3.2, are not fenced either.
- Scenario: `bind r source-file ~/.tmux.conf \; display "reloaded"` on 3.2a or 3.3a (Ubuntu 22.04, Debian 12, RHEL 9): one expectation, then the file's commands' blocks and two more. The `windowQuery` sent right after (5577) is answered by the second block and its own reply dropped, and anything asked while the burst is being read is answered by the wrong block. A two-command binding on 2.7 to 3.3a loses the `windowQuery` every time.
- Fix: send a binding's commands as `Syntax.lines` does for a typed line, one expectation each on one line number (`askLine`'s shape), and fence it when `runsCommands` says so.

### TA7 · A pane that closes while it holds the pointer leaves `grab` set: clicks, selection and tabs stop working
- Where: app/src/TmuxMode.geng:7932-7938 (`target`), 8043-8045, 7925 (`tabHit` needs `grab == Nothing`), 8067, 8892 (where it is set)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: with `grab = Just g`, `target` is looked up among the layout's panes only; when `g` is not there the event falls to `{ state = s, ... }` unchanged. `grab` is cleared only inside the branches that need a target.
- Scenario: a press in a pane whose program exits on that press (a "quit" button in a mouse program), or a selection held while the pane's program ends, or a window switch by a binding with a button down. The release finds no target, `grab` stays, and from then every press over a pane or a tab does nothing until the next attach. Menus and the drawn modes still take the mouse, which hides it for a while.
- Fix: clear `grab` (and `drag`) when its pane is not in the layout: in `applyLayout`, and in `pointerHere` when `target` is `Nothing` and no button is held.
- Fixed: 2026-11-22. `pointerHere` lets go of a grab or a drag whose pane is no longer in the layout before it reads the event. Test: "a pane that closes while a press in it holds the pointer lets go of it", on each tmux: before, the press in the other pane sent its program nothing, on all six.

### TA8 · Panes are never taken out of `ids`/`panes`/`info`: closed panes and a left session's panes keep their terminals
- Where: app/src/TmuxMode.geng:94-98, 3957-3962, 4368, 4511 (the only writers add), 4151-4161 (`SessionChanged`), 16319-16327 (`forgetPane` clears five maps, not these)
- Kind: bug (leak) / design
- Severity: medium
- Confidence: confirmed
- What: a terminal is made for every pane of the session and for any `%output` id; nothing removes one except `Entered`/`Exited`. `info`, `scans`, `nested`, `status.panes` are the same. TM103 records only that `modes` and `paneModes` keep "small entries".
- Scenario: a session attached for days in which windows and panes come and go (popups on 3.8 are panes; a script that opens a window per job): each closed pane leaves a `Vt.Term` with its scrollback. After `switch-client` the old session's terminals stay too. Besides memory, `celled` (1760) and `paneBells` (9475) walk every one of them on each paint and each read, and every lookup by id is a linear search of `ids`.
- Fix: on each `ForPanes` answer (it lists the session's panes) drop every id not listed, from all the per-pane maps in one function; ask `panesQuery` on `%window-close`/`%unlinked-window-close` and after a layout that no longer names a pane. One record per pane (`Dict Int Pane` holding terminal, info, back, mode, copy state, scan) would make "forget a pane" one `Dict.remove` and remove the hand-kept parallel structures, including the `ids`/`panes` refinement.

### TA9 · Every attach asks the window, tabs, panes and modes twice, so every pane is captured twice
- Where: app/src/TmuxMode.geng:2513-2514 (`attachQueries` on the first reply), 4151-4161 (`SessionChanged`)
- Kind: efficiency
- Severity: medium
- Confidence: confirmed (TM3 records `%session-changed` right after the first block of every start)
- What: `attachQueries` asks `windowQuery`, `tabsQuery`, `panesQuery`, the modes; the `%session-changed` that tmux sends next asks the same four again, and each `ForPanes` answer sends `recapture` for every pane.
- Scenario: attaching to a session of ten panes transfers and parses twenty whole-history captures and builds each terminal twice. `State` holds no session id, so it cannot tell the session it is attaching to from a `switch-client`.
- Fix: keep the session id; on `%session-changed` to the same session while the attach's own questions are still in `expecting`, ask nothing.

### TA10 · A pane's whole history is captured on attach and on every `%pause`, into a terminal that keeps about 1000 rows
- Where: app/src/TmuxMode.geng:867-877 (`blank`: `scrollbackBytesFor { cols, rows = 1000 }`), 2381-2383 and Command.geng:549-558 (`-S - -E -`), 4163-4167 (`Pause`), 3889-3962 (`rebuild`)
- Kind: efficiency
- Severity: medium
- Confidence: confirmed for what is asked and the fixed budget; I did not measure what the budget keeps of coloured lines
- What: the capture asks from the first line of history; the terminal it is fed to has a scrollback budget sized for 1000 plain rows, whatever the user's scrollback setting or tmux's `history-limit`.
- Scenario: `history-limit 50000`, eight panes: an attach moves several megabytes per pane (twice, by the finding above) to keep a fiftieth. Worse for flow control: `%pause` means puritty fell five seconds behind on a pane, and the answer is to ask for that pane's entire history again, on the same slow link, each time it is paused.
- Fix: ask `-S -N` with N from the terminal's budget (and make the budget the user's scrollback setting, which TM53 already says it is); after a `%pause` the screen and a few hundred lines are enough.

### TA11 · `applyLayout` sizes terminals without the scrollbar's columns; only `refit` uses `fittedIn`
- Where: app/src/TmuxMode.geng:4443 (`fitted`), 4469 (`fittedIn`), 1987-1989 (`fitted` is only `fittedTitles`), docs/tmux.md TM53
- Kind: bug / inaccuracy
- Severity: medium
- Confidence: confirmed by reading
- What: TM53 says `fittedIn` is "used for both their terminals' sizes and where they are drawn". Drawing does (`placedPanes`), and `refit` does, but every `%layout-change` and every `ForWindow` answer goes through `applyLayout`, which fits titles only.
- Scenario: tmux's look with `pane-scrollbars on`: after any split, resize or window switch each pane's terminal is the cell's width, one or more columns wider than tmux's pane, until an option change happens to call `refit`. A full-width line then wraps a column late and the pane's picture drifts from tmux's; each flap is also a `Vt.resize` with reflow.
- Fix: one function for a pane's box, used by `applyLayout`, `refit` and `placedPanes`; delete `fitted`.

### TA12 · Key bindings and prefixes are read once, on attach
- Where: app/src/TmuxMode.geng:2546-2547 (the only senders of `ForKeys`/`ForPrefixes`), 5455-5461, 5506-5513
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: puritty routes every key by its copy of the tables: which keys go straight to the pane (`nobodyBinds`), which bindings it runs itself (prompts, menus, the tree), what table the client is in.
- Scenario: `prefix r` reloading a changed tmux.conf, `:bind -n F5 ...`, `:set -g prefix C-a`, or customize-mode's own `bind-key`: the new root binding's key keeps going to the pane by id, a key newly bound to `command-prompt` is sent to tmux, which can show a control client no prompt, and a changed prefix is not followed (before 3.4 the old prefix keeps working in puritty and the new one is typed into the pane).
- Fix: ask `list-keys` and the prefixes again after a user-run command or a flags-0 block that names `bind-key`, `unbind-key`, `source-file` or `set` of `prefix`; cheaper, after any `ForRan` whose command is one of those.

### TA13 · Layout changes of windows not shown are dropped, so their panes' terminals keep the old size
- Where: app/src/TmuxMode.geng:4133-4138 (`LayoutChange`), 4147-4149 (a window shown: only `windowQuery`), 4493-4511 (`sizePane`)
- Kind: bug
- Severity: medium
- Confidence: plausible (read, not run)
- What: a resize makes tmux send `%layout-change` for every window of the session (TK10.10); those for other windows are ignored, while their panes' `%output` keeps being fed to terminals of the old size. When such a window is shown, `applyLayout` resizes the terminal but nothing captures it again.
- Scenario: two windows, an editor in the hidden one; puritty's window is resized. The editor redraws for the new size into a terminal of the old size. Switching to that window shows the garbled picture until the program redraws by itself.
- Fix: keep each window's last layout and size its panes when the notification comes, or `recapture` the panes of a window when it is shown at a size other than the one their terminals had.

### TA14 · Commands queued earlier in the read that ends control mode are still written
- Where: app/src/TmuxMode.geng:2434-2475 (`Exited` keeps `acc.commands`), 4169-4175 (`Exit` sets nothing), app/src/Main.geng:3978
- Kind: bug
- Severity: low
- Confidence: plausible (which tmux sequences put a question in the same read as `%exit` was not measured)
- What: TM92 stops sending after the user's own detach. When tmux ends the client otherwise ("too far behind", a detach or kill from elsewhere), anything an earlier event of the same read asked (a `windowQuery` after a flags-0 block, `askCopy` for output in copy mode, a status poll) is in `done.commands`, and `Exited` has reset `ending`, so `sendCommands` writes it to the shell control mode left.
- Fix: on `Exited` empty `acc.commands`; on the `%exit` notice set `ending = 2` so nothing goes between `%exit` and the `ESC \` when they come in different reads.

### TA15 · A pane's output holding the entry sequence types a newline into that pane and hides its output
- Where: app/src/TmuxMode.geng:4059-4100, packages/tmux/src/Tmux/Control.geng:654-674, docs/tmux.md TM19
- Kind: security (decision questioned)
- Severity: low
- Confidence: confirmed
- What: by TM19, when a pane's `%output` holds `ESC P 1000 p` puritty sends that pane a newline and reads its output with a nested reader until `ESC \` at a line's start. The trigger is any bytes shown in the pane, not only a real inner `tmux -CC`.
- Scenario: a file or remote output containing the sequence makes puritty press Enter in that pane (running whatever is on its command line) and then drop the pane's output; the nested reader's `held` also grows without bound for output that has no newline, copied again on each `%output`. The sequence split across two `%output` lines is not seen at all.
- Fix: do not send input on in-band bytes: show the note and drop the inner lines, and let the user detach the inner client; bound the nested reader's held bytes and time it out as TK14 does for the outer one.
- Fixed: 2026-11-22: TM108. No key is sent to the pane; the note says Enter detaches the inner client; the nested reader is strict, so the first line that is not tmux's ends it and is shown. Test: "tmux -CC in a pane sends that pane no key", on each tmux: before, `send-keys -H 0a` went to the pane and the line after was dropped.

### TA16 · Before 3.2 the status polls are sent every second whether or not the last were answered
- Where: app/src/TmuxMode.geng:10999-11007 (`tick`), 7294-7304 (`awaited`: `s.expecting ++ asked`), 2642-2659
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: each second about twenty questions are appended to `expecting` and written, with no check that the previous batch has been read. Appending copies the queue, and each reply's `Array.dropFirst 1` copies it again.
- Scenario: a stalled link, or tmux blocked behind `wait-for`: the queue and the unsent output grow by twenty a second, and when the link returns each reply costs a copy of the whole queue.
- Fix: skip a poll while a `ForPoll`/`ForRawOptions` is still in `expecting`.

### TA17 · `ForCopy` does not look at `ok`: before 3.2 a pane killed in copy mode is never forgotten
- Where: app/src/TmuxMode.geng:3727-3767, 16332-16385 (`copyLine`), 16254-16267 (`askCopy`)
- Kind: bug
- Severity: low
- Confidence: plausible
- What: TM103's fix reads an answer with every field empty. Before 3.2 `display-message -t` a pane that is gone is an `%error` (TK10.1): the line is not a `C` line, `gone` is false, `copyLine` does nothing, so `copyAsked` keeps the pane (every later `askCopy` for it only sets the flag) and `copy`, `modes`, `back` keep it too.
- Fix: `if not ok then forgetPane asked`.

### TA18 · Work done on every read that only some events need
- Where: app/src/TmuxMode.geng:961-981 (`readHere`: `paneBells` twice, `viewLine`), 1448-1512, 9475-9492
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: each read, even one of plain `%output`, builds a `Dict` of every pane's bell count before and after, and builds `viewLine`'s whole string (tabs sorted, panes sorted, sizes, modes) to compare with the last. The path is hot when a pane floods: one read per chunk.
- Fix: compute `viewLine` only when a read held an event other than `Output`; count bells only for the panes that had output in this read.

### TA19 · Text from tmux is drawn on the canvas terminal with its control characters
- Where: app/src/TmuxMode.geng:16772-16787 (`drawText`), 2612, 2619, 2934, 4212 (`said` from `%message` and error lines), 4634, 2496 (the one place that filters, and it keeps C1 and DEL)
- Kind: security
- Severity: low
- Confidence: plausible
- What: `drawText` concatenates the text between a CUP and an SGR reset and feeds it to `Vt.feed`. `said` is whatever a `%message` or a reply's first line held; other pieces (labels, names) come the same way. tmux itself sanitises window names and titles, so the reachable cases are messages built from formats and error lines that quote input.
- Scenario: an escape sequence in a message moves the cursor, changes modes or paints over other parts of puritty's picture of tmux (the tab bar, a prompt). Replies are dropped (`takeReplies`), so I found no way out of the canvas.
- Fix: strip C0, DEL and C1 in `drawText` itself, once, rather than at each source.

### TA20 · A config reload that changes the look does not tell tmux the new size
- Where: app/src/Main.geng:3440, app/src/TmuxMode.geng:1946-1948 (`setLook`), 1955-1972 (`statusRows`)
- Kind: bug
- Severity: low
- Confidence: plausible
- What: `statusRows` is 1 in puritty's look and tmux's `status` count in tmux's look. `setLook` changes which applies and calls `barPlaced` only.
- Scenario: attached to a tmux with `status off` or `status 2`, the config's look is switched and reloaded: tmux's window stays a row taller or shorter than the room puritty now draws it in, until the next window resize.
- Fix: have `setLook` return commands as `resized` does, and `refit`.

### TA21 · A 17,377-line module: where it would split
- Where: app/src/TmuxMode.geng (whole)
- Kind: design
- Severity: medium
- Confidence: confirmed
- What and cost: `State` has about 75 fields and almost every function takes all of it. The findings above are what that costs: one path of ~10 that send commands forgot the expectation; `fitted`/`fittedIn` drifted; per-pane state lives in nine separate maps and "forget a pane" clears five; `ending`, `grab` and `copyAsked` each have a path that never clears them. The file cannot be reviewed in one sitting, and the explorer (TK10) has to drive the whole of it to check the queue. Groups that are already coherent, with the state each needs:
  1. **Conversation** (the queue): `Asked`, `Expect`, `expecting`, `linesSent`, `ending`, `ask`, `askLine`, `sent`, `sendAsking`, `expected*`, `ours`, the fence. If this module owned the only function that can emit a command (returning the command *and* the expectation as one value), a command without an expectation would not type-check. Needs: `expecting`, `linesSent`, `ending`, `userRan`.
  2. **Panes**: `ids`, `panes`, `info`, `back`, `scans`, `nested`, `modes`, `paneModes`, `copy`, `copyAsked` as one `Dict Int Pane`; `feedPane`, `feedOutput`, `rebuild`, `sizeAll`, `celled`, `forget`. Needs nothing else but the cell size and embedder.
  3. **Window and layout**: `window`, `layout`, `active`, `modal`, `tabs`, `applyLayout`, `refit`, `fittedIn`, `placedPanes`, the size told to tmux. Needs the status options for titles and scrollbars only.
  4. **Diagnostics**: `traced`, `describe`, `noticeLine`, `expectName`, `viewLine`, `diagnose` (lines 996-1726): pure functions of events and state, ~700 lines.
  5. **Prompt**: `Asking`, `promptKey`, `viKey`, `emacsKey`, `editLine`, the word motions, completion, history (lines 5603-7166, ~1500 lines). Needs `version`, `word-separators`, the name lists; returns an edited `Asking` or an answer. It is nearly pure already.
  6. **Keys**: `keyName`, `namedKey`, `lookupName`, `byName`, `keyByTable`. Needs `keys`, `caps`, the active pane's mode.
  7. **Pointer**: `pointerHere`, `selecting`, `modeClick`, drags, `pointerShape`. Needs layout, panes, `drag`, `grab`, `selection`, `clicks`.
  8. **Status line and options**: `StatusLine`, `subscribed`, `withStatus`, `colorsOf`, `scrollbarOf`, polls, themes.
  9. **Drawn modes**, one module each: tree, lists, customize, menus, views, numbers; each already has its own record (`Tree`, `Listing`, `Customizing`, `Menuing`, `View`, `Numbering`).
  10. **Paint**: `paint` and the piece builders, reading the others.
- Also: the overlays are seven independent `Maybe`s (`asking`, `menu`, `numbers`, `view`, `tree`, `listing`, `customizing`) with their precedence re-derived by pattern matches in `typedHere` (5410), `paint` (4556, 4679), `modeClick` (8107, 8181), `modeMenuOpen`, `modeRowChosen`, `modeKeyed`, `isAsking`: tree, listing and customize are exclusive in every one of those matches and would be one `Mode` type. Ints that are types: `ending` (0/1/2), `Drag.kind` (0-7), `Asking.purpose` (0, 1-4, 11-12, 21-24, tested by ranges at 7103-7121 and by list at 5382), `Sel.mode`, `previewMode`, `sort`, `ForPoll.scope`, `strayUntil`'s -1/-2, `clicks.pane = -2` meaning "a mode's row" (8143, 8323).

### TA22 · What the explorer does not reach
- Where: docs/tmux-checks.md TK10.3-TK10.10, app/tests/src/Explorer.geng
- Kind: test-gap
- Severity: medium
- Confidence: confirmed from the documents (the test sources were not read line by line)
- What: the queue's invariants are checked for the scenarios listed in TK10. Not among them, and each is a finding above: a typed line that makes no command (TK10.1 measured the blank line and says "which no scenario sends"); a resize caused by a status-option notification rather than by the window; a multi-command binding on the pre-3.4 path; `%session-changed` arriving during attach (the double capture is not a queue fault, so only a count of commands would show it). `endsClient`'s false positives have a test only for `prefix d`, `detach` and `detach-client -a` (TM92).
- Fix: add a scenario for each; for the first, make the fake answer nothing for a comment, an assignment and a `%` directive, as it does for a blank line.

---

## Looked at and found sound

- **A failing command ends its line** (`ours`, 2645-2661): the expectations sharing the head's `line` number are answered as failed; `askLine` and `expected` number lines consistently (7280-7288).
- **Startup** (`Entered`, `starting`, TM70): nothing is asked until the first flags-0 block ends well; an error before attach is put back on the terminal. Keys, pastes, the pointer, resizes and the timer all send nothing while `starting` (each guarded by `active < 0`, `layout == Nothing`, `capsKnown`, `pollAt < 0`).
- **Resize while attaching** (TK10.10, TM78): `resized` holds the size until `ForCaps`, which sends `wantedSize` as it is then.
- **Capture and output order** (`rebuild`, TM15, TM5.8): state and both captures on one line; output before the capture's reply is replaced by it; `%pause` continues and recaptures on one line.
- **Answers for views that have closed**: tree, list, customize, menu and preview answers update only an open view and carry a serial; prompt answers check a prompt is open and unedited (2876-2911, 3592-3670, 10360-10371).
- **Quoting of what puritty itself puts in commands**: `Command.quote` (single quotes, `'` closed and reopened), bytes as hex (`sendBytes`, `typeText`), pastes through `quoteBytes`; prompt input is stripped of line ends and controls before it can reach a template (`typeIntoPrompt` 1912-1942, `plainText` 6191, `promptPasted` 6894); `Syntax.fill` requotes any word an answer changed. The mouse's word and line go as a quoted option value, and what the menu then runs is what tmux expanded, as tmux itself would run it. I found no place in lines 1-8600 where typed or pasted text, a file name or a title reaches a command line unquoted, and none that can carry a newline into one.
- **`Exited`** resets to `idle` keeping only settings (TM102); `Stray`/`Foreign`/`giveUp` follow TK14.
- **Copy mode's asked-again flag** (`askCopy`/`ForCopy`) converges: one question out per pane, asked again once if anything changed.
- **The prompt's editing keys** (emacs and vi, 5770-7077): bounds are clamped; no index can leave the line.
- `docs/review.md` RV1-RV3 are not repeated here.

## Not covered

- Lines 8950 to the end, except the functions named at the top; in particular the drawing of the tree, lists, customize-mode, menus and views, `dragged`, `report`, `tabKey`, and whether `shownLine` strips control characters.
- `packages/tmux` beyond what calls needed. One thing seen there for its reviewer: `Control.line` ends a reply at any line that reads as `%end`/`%error` with the block's number (Control.geng:322-327), and a capture's lines are pane content, so a reply's end is decided by text a pane's program can print; what that does to the queue in `TmuxMode` follows from the note at the top of this file.
- The app's tests and the fake tmux were not read; statements about coverage come from `docs/tmux-checks.md`.
- Nothing was run against a real tmux: the behaviours of tmux marked "plausible" above need one measurement each (`dump-lines.py` with a comment line, an assignment, and a `%if`).

# 06 · packages/tmux (control mode): review findings

Slice: `packages/tmux/src/Tmux/{Control,Command,Syntax,Layout,Bindings,Style,Borders,Passthrough,Caps,Customize,CustomizeTables,ColorNames,Reason}.geng`.
Callers in `app/src/TmuxMode.geng` were read only where a finding needed its scenario traced.

No copy of tmux's source is on this machine (nothing under `vendor/` or `bench/tmux`), so every
statement about tmux's own code (`cmd-parse.y`, `control.c`, `input.c`, `colour.c`) is from memory of
that source. Findings that rest on it are marked `plausible` and say which tmux function to check.

---

### TP1 · A paste whose text (or any 1024-byte piece of it) begins with `~` is tilde-expanded by tmux 3.x
- Where: packages/tmux/src/Tmux/Command.geng:1114-1193 (`quoteBytes`, `quoteFrom`), used by `pasteBytes` :1072
- Kind: bug
- Severity: medium
- Confidence: plausible (tmux side from memory: `yylex_token` in `cmd-parse.y`)
- What: `quoteBytes` writes the piece as one double-quoted word and escapes only `"`, `\`, `$`, ESC, CR, LF, Tab and non-UTF-8 bytes. `~` goes as it is. In tmux 3.0+'s lexer the test is `if (ch == '~' && last != state && state != SINGLE_QUOTES)`, and `last` is not updated when the opening `"` is consumed (`goto next` skips `last = state`), so a `~` that is the first character inside double quotes is expanded as at the start of a bare word.
- Scenario: the user pastes `~/.bashrc` (or any text whose first byte is `~`, or a long paste where a 1024-byte boundary lands just before a `~`). puritty sends `set-buffer -b puritty-paste "~/.bashrc"`; tmux stores `/home/user/.bashrc`, and the program gets that. `~name…` with no such user makes the `set-buffer` a parse error and that piece of the paste is lost, the later pieces appended to a buffer missing its start. `docs/tmux-checks.md` lists `~` among the bytes checked for `sendBytesPlain` (single quotes, safe) but nothing checks it for `quoteBytes`; the suite's paste cases (`TmuxSuites.geng:432-458`) have no `~`.
- Fix: write `~` as `\~` in `quoteFrom` (tmux's `yylex_token_escape` gives any unknown escaped character back as itself; 2.x's `cmd_string_string` does too), or at least when it is the first byte of the word. Add a case, and measure it against a real 3.x once.
- Fixed: 2026-11-22. Measured on tmux 3.8 (`source-file` of three `set-buffer` lines): `"~/.bashrc"` was stored as `/home/gram/.bashrc`, `"\~/.bashrc"` as `~/.bashrc`, `"x~/y"` as it is. `quoteFrom` writes every `~` as `\~`. Test: `Command`'s "a paste's ~ is escaped". 2.x's parser was read, not run.

### TP2 · `ESC \` at the start of a line ends control mode even inside a reply, and a reply's lines are split on newlines the pane's program can put there
- Where: packages/tmux/src/Tmux/Control.geng:229-240 (the `ESC \` test comes before any look at `r.block`), :322-333 (`%end`/`%error` matched by number only)
- Kind: security
- Severity: medium
- Confidence: plausible (the code path is confirmed; that tmux prints these format values with raw newlines is from memory of `cmdq_print`/`control_write`)
- What: `inside` tests `byteAt at data == 0x1B && byteAt (at + 1) data == 0x5C` for every line start, block open or not, and then emits `Exited` and drops the block. A reply's lines are otherwise "the command's output as it is". puritty asks formats whose values a pane's program chooses and tmux does not escape: `#{pane_current_path}` and `#{pane_current_command}` (app/src/TmuxMode.geng:14138-14139, :14349, :17031). A directory name or a process name may hold `\n` and ESC.
- Scenario: a program in a pane (or a remote host over ssh in a pane) does `mkdir $'x\n\e\\…'; cd` into it. The next tree-mode or drop query's reply holds a line that starts `ESC \`: puritty leaves control mode with tmux still attached, and everything tmux writes from then on (`%output …` lines for every pane, and the attacker's text after the `ESC \`) is fed raw to the outer terminal. With a newline only, the value's second line shifts or forges rows of the reply (`P\t@1\t%0…` rows in `ForTreePanes`), and a line `%end <n> 1` with a guessed number closes the block early so that the following attacker lines are read as notifications (`%output %<other pane> …`, `%layout-change`, `%exit`).
- Fix: inside an open block take `ESC \` as a reply line (tmux only writes ST after `%exit`, outside any block) or, if a killed block must still be left, require the `%exit` first. For the formats, ask pane-controlled values in a form tmux escapes (`#{q:…}` does not escape newlines; a subscription or one value per `display-message` whose reply is joined again are options) and have the app treat a reply with more lines than asked as bad.
- Fixed: In part, 2026-11-22. Inside an open reply, a line beginning `ESC \` is the reply's: tmux writes `ESC \` only after `%exit`, outside any reply. Test: `Control`'s "ESC \ at a reply's line start is the reply's": before, control mode was left mid-reply and the rest went to the terminal. Not done: a pane-chosen value (a folder's or a program's name) holding a newline can still add rows to a reply or close it early with a guessed `%end`.

### TP3 · A line that has not ended yet is copied and rescanned on every read, and nothing bounds it, a reply's lines or the lines in doubt
- Where: packages/tmux/src/Tmux/Control.geng:138-143 and :284-285 (held partial line), :330/:333 (`open.lines` grows), :270 (`stray` re-flattened per line)
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: when a line has no `\n` yet, `inside` keeps `Bytes.slice at n data` as `held`; the next `feed` does `Bytes.flatten [ r.held, bytes ]` and `indexOf 0x0A` starts again at 0. A line of L bytes arriving in reads of R bytes costs L²/2R bytes copied and as many scanned. There is no cap on `held`, on `Block.lines`, or on `stray` (which is also re-flattened once per line in doubt: `Bytes.flatten [ b, doubtful ]`, quadratic in the number of lines until tmux speaks or `giveUp`).
- Scenario: any program's output (a `cat` of a file, a remote host) holds `ESC P 1000 p`; from there bytes with no newline (a binary file, `/dev/zero`) are all held: memory grows without bound and each read recopies everything held. 100 MB in 64 KB reads is about 80 GB of copying, so the terminal hangs long before memory runs out. The same stream with `%begin 1 1 1` and then lines never closed stores every line for good. Real tmux lines are short (an `%output` line is bounded by tmux's own buffer), so nothing legitimate needs more than a few hundred KB.
- Fix: remember how far the held bytes were scanned (hold an array of pieces and scan only the new read for `\n`), and put a limit on a held line, on a block's size and on `stray`; past it, leave control mode and say so (the bytes go to the terminal as `giveUp` does), rather than growing.
- Fixed: In part, 2026-11-22. After each read, a held line or the lines in doubt past 1 MiB (`heldMost`) leave control mode as `ESC \` does, their bytes the terminal's (`bounded`); the copying per read is bounded with them. Not done: a reply's lines are not bounded, and the held line is still copied whole each read up to the limit. Test: `Control`'s "a line that does not end is held to 1 MiB": before, control mode held all 1.31 MB.

### TP4 · `%output` is unescaped with two allocations per escaped byte, and each short line is decoded to a String twice before that
- Where: packages/tmux/src/Tmux/Control.geng:598-651 (`unescape`, `unescapeFrom`), :351-375 (`guard`), :391-397 (`startsWith`), :381-388 (`notice`)
- Kind: speed
- Severity: medium
- Confidence: confirmed (the allocation pattern; not measured)
- What: this is the path every byte of every pane's output takes under `-CC`. tmux writes each byte below 0x20 and `\` as `\ooo`, so a full-screen program's output has an escape every few bytes (every ESC of every SGR and cursor move, every CR and LF). For each one `unescapeFrom` makes a `Bytes.slice` of the text before it, a one-byte `Bytes.fromUInt8s [ … ]` from a fresh one-element array, and two `Array.pushLast`es on `pieces`; then `Bytes.flatten` copies it all once more. Before that, for every notification line of 64 bytes or less (most `%output` lines of an interactive program), `guard` does `Bytes.toStringLossy` and `String.split " "` only to find it is not `%begin`; `notice` then calls `startsWith` twice, each making `Bytes.fromString prefix` and a slice to compare.
- Scenario: `cat` of a colored log, or a curses program repainting, through tmux: per escaped byte roughly four heap objects, where a decoder writing into one output buffer needs none.
- Fix: decode in one pass into a single builder sized to the input (the output is never longer than the input), or ask core for a primitive; in `guard`, test the bytes for `%b`/`%e` before making a String; make the two prefixes top-level constants and compare by index.
- Fixed: Measured and left, 2026-11-22. Natively, 30,000 `%output` lines of 211 bytes with an escape in every four bytes (6.3 MB) took 76 ms through `Control.feed`, about 80 MB/s, more than a terminal's output asks.

### TP5 · `Bindings.held` matches a word anywhere in the command: arguments named `menu` or `popup` hold a binding back, and a prompt inside a quoted argument is not held
- Where: packages/tmux/src/Tmux/Bindings.geng:201-246; callers app/src/TmuxMode.geng:10238 (typed commands) and `route` :153
- Kind: bug
- Severity: medium
- Confidence: confirmed for the false positives; plausible for what tmux then does in the false negatives
- What: `held` splits the command at spaces, drops a leading `{` from each word and asks `Array.member name words` for each of `command-prompt`, `confirm-before`, `choose-tree`, `popup`, `menu`, `displayp`, … Any word counts, whatever its place.
- Scenario (held wrongly): `bind m send-keys menu Enter`, `bind p new-window -n popup`, `bind x display-message menu`: the key is never sent, puritty says "puritty: m is display-menu; tmux -CC shows no menu", and `menuOf`/`popupOf` then find no such command. Scenario (not held): tmux prints a string argument in quotes, so `bind y if-shell -F '#{x}' 'command-prompt -p name "rename-window %%"'` lists as `… "command-prompt -p name \"rename-window %%\""`; the word is `"command-prompt`, nothing matches, the key is sent with `send-keys -K` and tmux opens its prompt on the control client, which is the wedge `held`'s own comment says it exists to prevent. docs/tmux.md:1089 records only the `{ … }` form as known. For a command typed at puritty's prompt (TmuxMode.geng:10238) tmux's alias `confirm` and any unambiguous prefix (`command-p`, `confirm-b`) are not matched either.
- Fix: decide from `Syntax.tokens`/`Syntax.commands`: the first word of each command, and recursively the commands inside a block or inside a string argument of `if-shell`/`run-shell -C`; match names the way tmux resolves them (alias table, unique prefix) for typed lines.
- Fixed: 2026-11-22. `held` decides from command names (`commandNames`): the first word of each command, and of the commands in a block, in `if-shell`'s commands and in `run-shell -C`'s, four deep. Test: `Bindings`' "what is held is decided by commands' names": before, `send-keys menu Enter`, `new-window -n popup` and `display-message menu` were held and the prompts inside `if-shell` and `run-shell -C` were not. Not done: tmux's command aliases and unique prefixes for a typed line (`confirm`, `command-p`).

### TP6 · `Bindings.bindingOf` rebuilds a binding's command from space-split words, so runs of spaces inside its quoted arguments collapse
- Where: packages/tmux/src/Tmux/Bindings.geng:263-291 (`String.split " " line |> Array.keepIf (\w -> w /= "")`, then `String.join " " (Array.dropFirst (t.index + 3) words)`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: the empty words are dropped to get past `list-keys`' column padding, but the same filter runs over the command.
- Scenario: `bind X send-keys "a  b"` (two spaces) is stored as `send-keys "a b"`. On a tmux before 3.4 puritty sends that text itself (`Command.bindingLine way.ran`, TmuxMode.geng:5493), so the pane gets one space; on any version a held `command-prompt -p "Name:   "` or a `display-menu` item with padding is shown with the spaces gone. `Customize.bindLine` (Customize.geng:383) reads the same lines by position and keeps the command as printed; the two readers have drifted.
- Fix: read the flags, the table and the key by position as `bindLine` does and take the rest of the line untouched (one reader for both modules).

### TP7 · `Command.pasteBytes` on tmux 2.x loses a `;` that ends a piece
- Where: packages/tmux/src/Tmux/Command.geng:1072-1104 (`setBufferFirst`/`setBufferAppend` are `allowed = anyTmux`), :1273-1280 (the measurement, in `sendBytesPlain`'s comment)
- Kind: bug
- Severity: low
- Confidence: plausible (rests on the module's own measurement: 2.x "drops a `;` that ends a word even in quotes")
- What: `sendBytesPlain` works around 2.x's `cmd_list_parse` taking a word's final `;` as a command separator by sending `\;` as its own word; `quoteBytes` does nothing about it, and `pasteBytes` is used for every version (app/src/TmuxMode.geng:5304).
- Scenario: on 2.7 to 2.9a, pasting `select 1;` or a C line sends `set-buffer -b puritty-paste "select 1;"` and the program gets `select 1`. The same at any 1024-byte boundary that falls after a `;`. docs/tmux.md TM94 measured line ends, a tab and Korean, not a final `;`.
- Fix: for a tmux without `cmd-parse.y` (Caps: no `send-keys -H`), end such a word so that 2.x's rule gives the `;` back (a word whose unquoted text ends `\;` becomes `;`), or move the cut so no piece ends in `;` and carry a last `;` as its own `set-buffer -a` word; add it to the 2.7 model's cases.

### TP8 · `unescape` drops the text before a backslash that is not an escape
- Where: packages/tmux/src/Tmux/Control.geng:649-651
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: in the not-octal branch the call is `unescapeFrom bytes slash (indexOf 0x5C (at + 1) bytes) pieces`: `from` becomes `slash` while `pieces` is passed without `before`, so the bytes in `[from, slash)` are in neither.
- Scenario: `unescape "ab\9c"` gives `\9c`, not `ab\9c`. The suite's case (`TmuxSuites.geng:348`, `a\015\134\9b`) passes only because its bad backslash comes straight after an escape, where `from == slash`. Real tmux always writes `\` as `\134`, so this needs a stream that is not tmux's (a hand-made one, a nested or truncated line); it is still silent loss of output.
- Fix: keep `from` as it is in that branch (only the next search position moves), and add a case with text before the bare backslash.

### TP9 · A notification that arrives inside a reply is kept as a reply line and never acted on
- Where: packages/tmux/src/Tmux/Control.geng:320-333
- Kind: bug
- Severity: low
- Confidence: plausible (tmux(1) says a notification never occurs inside an output block; from memory of `cmd-queue.c`, `%begin` is written when a command starts and `%end` when it finishes, and a command that waits, `run-shell` without `-b`, `wait-for`, `if-shell` with a shell test, lets the event loop write `%output` in between)
- What: with a block open every line that is not its `%end`/`%error` is pushed to `open.lines`, `%output` and `%exit` included.
- Scenario: the user's binding `run-shell 'sleep 5'` is sent by puritty (`runLine`); panes that write during those five seconds have their `%output` lines swallowed into the reply and never drawn, and a `%pause`/`%layout-change` is lost the same way.
- Fix: measure it first (a `run-shell 'sleep 2'` under `-CC` with a pane printing). If tmux does interleave, read a line of the exact shape `%output %<digits> …` (and the other known notification names with valid ids) as a notification even with a block open.

### TP10 · A layout's nesting depth is not bounded, and a split's box is not clamped as a pane's is
- Where: packages/tmux/src/Tmux/Layout.geng:173-241 (`oldCell` → `oldRest` → `children` → `oldCell`, not tail calls), :105-113 (`splitDecoder`, plain `Decode.int`), :212/:216 (split boxes unclamped)
- Kind: security
- Severity: low
- Confidence: plausible (stack use not measured)
- What: each `{` or `[` adds several native frames (`Result.andThen` closures included). The text comes from `%layout-change` or a `list-panes` reply, that is from whatever speaks control mode. `Pane` boxes go through `bounded`, but `Split`'s `w h x y` are whatever nine digits (old form) or any JSON int say, and the app reads them (`heightOf`, TmuxMode.geng:2316; the size shown at :1464).
- Scenario: a stream holding `ESC P 1000 p` and `%layout-change @0 0000,1x1,0,0{1x1,0,0{1x1,0,0{…` nested some tens of thousands deep (a few hundred KB) can overflow the stack: a crash from printed bytes. The JSON form has the same shape through `Decode.lazy`.
- Fix: carry a depth and fail past a small limit (tmux cannot make more levels than panes); clamp a split's box with `bounded` as well, so the type says the same for both.

### TP11 · Escapes inside double quotes are not decoded: `\n`, `\t`, `\e`, `\ooo`, `\u…` read as the letter or digits
- Where: packages/tmux/src/Tmux/Syntax.geng:174-175 and :189-190 (`word`); used for values by `Customize.unquoted` (Customize.geng:279-290)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed (tmux's printing with `VIS_OCTAL|VIS_CSTYLE|VIS_TAB|VIS_NL` from memory)
- What: after `\` the next character is taken as itself, which is right for `\\`, `\"`, `\$`, `\;`, and wrong for the C-style escapes `list-keys` and `show-options` print for control characters.
- Scenario: an option or a binding argument holding a tab, a newline or ESC (`set -g @sep "a\tb"`; a status format with a literal ESC) is listed as `"a\tb"`; `Token.value` is `atb`. Customize mode shows that value, offers it as the prompt's first text, and Enter writes `atb` back. In `fill`, a template word that held such an escape and a `%%` is re-quoted from the wrong value.
- Fix: decode `\a \b \e \f \n \r \s \t \v`, three octal digits and `\uXXXX`/`\UXXXXXXXX` in the double-quote branch as `yylex_token_escape` does, and make what is written back able to say them (a double-quoted word, as `quoteBytes` makes).

### TP12 · `Command.quote` cannot say a newline and does not refuse one; three builders take an unquoted name
- Where: packages/tmux/src/Tmux/Command.geng:1451-1453 (`quote`), :500-502 (`globalValue`), :769-778 (`setPaneOption`, `setPaneFormat` names)
- Kind: design
- Severity: low
- Confidence: confirmed (no reachable injection found: the prompt's paste is cut at its first control character, and today's unquoted names are constants)
- What: control mode is one command a line. `quote` single-quotes and escapes `'` only, so a `\n` in a value ends the line inside an open quote and the rest of the value is run by tmux as the next command. Every user- or pane-supplied word (prompt answers through `Syntax.fill`, `setOption` values, `@puritty_mouse_word`/`_line` from the pane's screen, buffer and client names, a popup's directory and command) depends on its caller never passing one.
- Scenario: a later caller hands `quote` text with a line end (a multi-line value from customize mode's editor key, a clipboard string) and its tail is executed as a tmux command.
- Fix: make the one quoting function safe by construction: write a value that holds LF (or CR, or any control byte) as a double-quoted word with `\n` (`quoteBytes` already does this), and quote the names in the three builders too.

### TP13 · Outside tmux, every ESC in the terminal's output costs a 7-byte slice and compare; under tmux every `%output` is scanned once more, and an entry split across two is missed
- Where: packages/tmux/src/Tmux/Control.geng:178-203 (`outside`), :656-674 (`startsControl`/`startsFrom`); callers app/src/Main.geng:3936, app/src/TmuxMode.geng:4077
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: `TmuxMode.read` runs `Control.feed` over every read whether or not tmux is in use. For each ESC, `outside` allocates `Bytes.slice esc (min n (esc + 7)) data` and compares it with `entry`, then on a miss allocates a second slice of `entry` for the prefix test. Colored output has an ESC every few bytes. Under tmux, `startsControl` does the same over each `%output`'s bytes. `startsControl` also has no carry between calls, so `ESC P 1000 p` cut between two `%output` lines (tmux cuts anywhere) is not seen and the nested client's control text is fed to the pane's terminal as a DCS.
- Fix: look at the byte after the ESC first (`P`), and only then compare the rest by index; give the nested check the same `Reader` hold `feed` has (start each pane with a `Reader` and let `feed` find the entry) instead of a separate stateless scan.

### TP14 · `Style.themed` rewrites `theme…` words in expanded text, not only inside `#[…]`
- Where: packages/tmux/src/Tmux/Style.geng:182-189; callers app/src/TmuxMode.geng:15421, :16051 (`Style.themed theme l.text`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `themed` is `String.replace "themegreen" …` over the whole string. The app applies it to a format's expanded text, which holds window names, pane titles and commands.
- Scenario: a window named `themeblack` or a pane titled `use themered here` is shown in the tree or status as `gray5` / `use indianred here` (dark theme).
- Fix: resolve theme names where a color is parsed (`color` already strips the `theme` prefix: give it the theme table), not by text replacement.

### TP15 · `Style.color` takes `colourN` for any N and does not know tmux's digit names
- Where: packages/tmux/src/Tmux/Style.geng:254-266, :218-245; `isColor` :194-200
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed for the range; plausible for the digit names (`colour_fromstring` from memory: `"0"`…`"7"` and `"90"`…`"97"` are the eight colors and their bright forms)
- What: `colour999` and `colour-5` become `38;5;999` / `38;5;-5`, and `isColor` says yes where tmux's `strtonum(…, 0, 255)` says no. `fg=1` or `bg=92`, which tmux takes, give `""` here and the color is dropped.
- Fix: hold N to 0..255, and add the digit names to `named`.

### TP16 · `quoteFrom` builds each paste piece by appending to a String per byte, and slices per byte
- Where: packages/tmux/src/Tmux/Command.geng:1119-1193
- Kind: efficiency
- Severity: low
- Confidence: confirmed (pattern; not measured)
- What: `acc ++ …` once per byte makes a piece of 1024 bytes cost about half a megabyte of copying if `++` copies; `sequence = Bytes.slice i (i + length) bytes` is made for every byte, ASCII too (length 0), since `let` is strict; `Array.range`/`Array.all` run for each multi-byte lead.
- Scenario: a 1 MB paste is about a thousand pieces, so some 500 MB of copying and a million empty slices before the first command is written.
- Fix: collect runs (index of the run's start, emit a slice when an escape is needed) into an array and join once; only slice when `length > 0`.

### TP17 · An ESC that is not doubled inside a passthrough envelope is kept; tmux drops it
- Where: packages/tmux/src/Tmux/Passthrough.geng:127-129 ("an ESC not doubled: kept as it is, as tmux passes it")
- Kind: inaccuracy
- Severity: low
- Confidence: plausible (`input.c` from memory: in `dcs_handler` an ESC has no action and moves to `dcs_escape`, where any byte but `\` is added and the state returns; so `ESC X` adds `X` alone)
- What: the comment claims tmux's behaviour; by the state tables tmux passes `X` without the ESC.
- Scenario: a program that forgets to double an ESC inside `ESC P tmux; … ESC \` works in puritty's `-CC` panes and breaks in real tmux, or the reverse for a payload that relied on the drop. Small, but the comment states a measurement that was not made.
- Fix: check against tmux and either drop the ESC or correct the comment.

### TP18 · `Customize.table` is rebuilt from its text on every call, and `Borders.cells` parses the two border styles once per border cell
- Where: packages/tmux/src/Tmux/Customize.geng:95-133 (called at app/src/TmuxMode.geng:6396 inside `completions`, itself called up to three times per Tab at :6271-6274, and at :12067); packages/tmux/src/Tmux/Borders.geng:317-335 (`styleAt`)
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: `table` splits about 1,300 rows at `\n` and `\t`, builds a Dict of rows, then three Dicts, each call; the completion only wants the option names. `styleAt` runs `Style.apply` (replace, split, color lookup through `ColorNames`) and `Style.sgr` for each candidate cell, though only four results exist (active or not, marked or not).
- Fix: keep the built table in the state by version (or make `table38`'s parse a top-level value and apply the diff once); compute the four SGR strings before the loop.

### TP19 · Dead or duplicated: `prefixesOf`'s `byTable` and `hasSendKeysK`; `indexOf`/`byteAt` twice
- Where: packages/tmux/src/Tmux/Bindings.geng:52-85 (`byTable`, `hasSendKeysK`, `leadingDigits`); packages/tmux/src/Tmux/Control.geng:678-719 and packages/tmux/src/Tmux/Passthrough.geng:142-183
- Kind: dead-code
- Severity: low
- Confidence: confirmed
- What: the app takes `prefixes` and `repeatMs` from `prefixesOf` (TmuxMode.geng:2830) and sets `byTable` only from `Caps.has "send-keys" "K"` (:3088); the version-number test for `-K` is computed and dropped, and it is a second, different answer to a question `Caps` exists to answer (a `next-3.4` or patched build would differ). `indexOf` and `byteAt` are the same twenty lines in two modules.
- Fix: remove `byTable` from `prefixesOf` with `hasSendKeysK` and `leadingDigits`; move the byte search to one internal module.

### TP20 · Test gaps
- Where: packages/tmux/tests/src/TmuxSuites.geng
- Kind: test-gap
- Severity: low
- Confidence: confirmed (by grep of the suite)
- What: no case for a paste piece that begins with `~` or (2.x) ends with `;`; `unescape` has no case with text before a bare backslash (the one case hides the bug above); `Bindings.held` has no case where the name is an argument or sits inside a quoted string; nothing feeds `Control.feed` a reply line that starts with `ESC \`, a very long line over many reads, or a deeply nested layout; `bindingOf` has no command with two spaces in a quoted argument.

---

## Looked at and found sound

- **Control.geng**: `ESC P 1000 p` found across reads (the prefix hold is right for every cut); `\r\n` and bare `\n` line ends; `%begin`/`%end`/`%error` matched by number, an `%end` with no `%begin` ignored, a guard-shaped line with another number kept as a reply line; lines of other programs outside a reply (`Stray`/`Foreign`/`giveUp`, TK13/TK14) behave as the documents say, including `ESC \` with lines in doubt; `%output` and `%extended-output` field positions (`: ` after the age); raw bytes above 0x7F and invalid UTF-8 pass through `Output` untouched (only names go through `toStringLossy`); each notification's word positions against tmux 3.8's forms, including `%subscription-changed` and names with spaces; `indexOf`'s two-span search is correct (the `past == from` case can only be the byte looked for).
- **Command.geng**: `render` and the shapes (every command comes from the catalog; optional parts keep the value index in step); ids always quoted; `send-keys -H` chunking and `pairs`; `-l --` before 2.x text; `controlName`'s table; `bindingLine`'s `\;` test is per word, and tmux prints a literal backslash-semicolon inside a string as `\\;`, so it does not match; `quote`'s `'\''` form is right for both parsers; `#{…}`/`#(…)` in a quoted word are expanded only by commands meant to expand them (`display-message`), with `%` doubled by the app's `noTime`.
- **Customize.geng**: every command it builds goes through `Command.quote`; `filterFormat`'s `literal` escapes `#`, `,` and `}` so a value cannot open a format or a `#(…)` job; `unescaped`'s ` \; ` replace cannot hit a quoted `\\;`; reset/unset chains and levels read as `window-customize.c` describes. The tree, preview and `write` (about 1,300 lines porting tmux's drawing) were read for crashes and unbounded loops only, not compared line by line with tmux.
- **Syntax.geng**: flag letters with values for `command-prompt`, `confirm-before`, `display-menu`, `display-popup`, `choose-tree`/`-buffer`/`-client`, `customize-mode`, `display-panes`, `find-window`, `if-shell` agree with tmux(1); `substitute` follows `cmd_template_replace` (one `%%` per answer, `%N` everywhere, inserted text not read again); brace counting agrees with tmux's for `#{…}` inside blocks; `fill` quoting a changed word whole is the documented design.
- **Layout.geng**: old form and JSON for well-formed input, trailing text refused, numbers capped at nine digits, pane boxes clamped. The 4-character checksum is skipped, not verified (tmux is trusted for it; a wrong one changes nothing).
- **Bindings.geng**: `route` against `server_client_key_callback` (prefix from any table but `prefix`, fall back to `root`, repeat window, a non-repeat key during a repeat going to `root`), `since`'s wrap at 2^30.
- **Style.geng**: `#[…]`/`##` runs, `default`/`none`/`noattr`, `#rrggbb`, `bright*`, X11 names and `greyN` rounding agree with `style.c`/`colour.c` as remembered.
- **Passthrough.geng**: the marker and a lone ESC held across reads, doubled ESCs, several envelopes in one read; no quadratic work.
- **Caps.geng**: `flagsOf` on tmux's usage forms (`[-abc]`, `[-x value]`, `[-l [target-pane]]`); unknown-until-answered is the documented design (TM72).
- **ColorNames.geng, CustomizeTables.geng, Reason.geng**: generated data and the reason type; the lookup code around them read, the rows not.

## Not covered

- tmux's source was not available, so nothing was compared against `cmd-parse.y`, `control.c`, `style.c`, `colour.c`, `screen-redraw.c` or `window-customize.c` on the page; `Borders.cells` (a port of `screen-redraw.c`'s cell typing) and `Customize`'s `entries`/`preview`/`write` were read for internal soundness only.
- `CustomizeTables.geng`'s and `ColorNames.geng`'s rows were not checked against tmux's tables.
- `docs/tmux.md` (4,152 lines) was searched for each finding's topic, not read through; a decision that covers one of the findings under a wording I did not search for is possible.
- Nothing was built or run: every finding is from reading, and the costs under "speed"/"efficiency" are not measured (whether `Array.pushLast` and `++` copy here depends on the compiler's uniqueness handling).

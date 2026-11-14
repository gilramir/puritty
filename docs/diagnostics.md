# The diagnostic log

Gilbert, 2026-11-12, while a tmux -CC paste bug could not be reproduced
away from his work machine: "I need you to add special logging to
puritty. This was on the roadmap anyway, so people could log their
sessions to help us debug problems. The only catch is that I can't send
the diagnostic log out from work. So I need a way to have you guide me
which parts of the log are interesting and I can tell you the values or
provide snippets."

So the log is built to be read where it is written, and quoted from in
small pieces: numbered lines with short tags, marks a user sets at the
moment of trouble, and nothing typed, pasted or shown in it. The user's
guide is [`user/diagnostics.md`](user/diagnostics.md).

## DG1 · The file and its lines

- **On by a setting**, `[debug] log` (Advanced page), off by default, at
  once in every window: turned on, a window begins a file; turned off, it
  writes a last line and stops. One file a window, since a window is a
  process: `puritty-YYYY-MM-DD_HHMMSS-mmm.log` in
  `%LOCALAPPDATA%\puritty\logs` or `$XDG_STATE_HOME/puritty/logs`
  (`Platform.logDirectory`), beside the restore folder (TB10). Opening a
  file removes the folder's oldest beyond the newest nineteen, so twenty
  are kept.
- **A line** is its number (six digits), the local time of day to the
  millisecond, a tag of six columns and the text. The number is what a
  user quotes ("lines 900 to 960") and what a reader asks for; the time
  matches what the user remembers; the tag is what a `Select-String` or
  `grep` filters by. The header says the date, the file, the version and
  platform, the window, the settings that decide pastes and tmux's look,
  and the window's state as a mark gives it.
- **Written in batches.** `Diag` is pure: lines wait in the model and the
  loop appends them (`File.appendFile`) at most every 250 ms, its timer
  waking it for them (`nextAt`); a mark, the log turned off and the
  window's end write at once. A write that fails loses its lines and says
  so on the next. A crash loses at most a quarter second.
- **Each turn's lines have its time** (`turnMs`, set by `handle` and
  `feed` from the turn's clock), so the lines a key causes, the tmux
  commands among them, carry the key's time.

## DG2 · What is written, and what never is

**Never**: the text of a key (`text`), of a paste, of a program's output,
of a capture; a password or an answer to ssh's questions; the bytes
`send-keys -H` carries; a quoted argument that is not a tmux id (`%3`,
`@2`, `$1`), a key's name (`Up`, `C-Space`) or a format (a `#{`) of
puritty's own (`Diag.command`, which the app tests hold to it: a typed
letter, a shifted one and a Hangul syllable are all `text`). Until
2026-11-12 only a quoted argument over 40 characters was hidden, so a
command filled from a prompt's answer (a search, a new name) showed the
answer when it was short; DG5 says how that was found. Names are written (hosts, tmux's sessions and windows by id),
since the user chooses what leaves.

**Written:**

| tag | from | |
|---|---|---|
| `key` | each press and repeat | by name, chords with their modifiers; a modifier alone is not said, its chord is |
| `mouse` | each press and release | button, cell, modifiers; motions are not written |
| `paste` | the request, and each piece sent | its source, bytes, lines, bracketed or not, pieces, bytes sent and where |
| `window`, `ime`, `menu`, `select` | the window's events | focus, size, a new cell (WS30), close, an IME's commit by length |
| `tab` | `step` | the tab shown, when it changes |
| `ssh` | the session's notices | its status lines, a question asked, started, failed and why, ended |
| `read` | `feed`, without tmux | the bytes a read gave |
| `tmux>` | every command written (`sendCommands`) | as `Diag.command` says it |
| `tmux<` | `TmuxMode.read`'s `trace` | each notification, each reply with what it was matched to (`expectName`), a run of one pane's `%output` as one line of bytes and lines |

A reply's lines are shown only for puritty's own queries (the window's
layout, the prefixes, the panes' modes, copy mode's state, the time), and
an error's first line, which is tmux's; a capture's never.

## DG3 · Marks

`[keys] mark_log`, Ctrl+Alt+Shift+M by default, and the menu's **Mark
the diagnostic log**, both only while the log is on (the key goes to the
program otherwise), write `MARK n`, the window's state and, under tmux
control mode, `TmuxMode.diagnose`:

- the shown tab and the tab count, the host; focus, the buttons held,
  Shift; a paste asked or under way; the bytes waiting to be sent; the
  terminal's paste brackets, focus reports, mouse reports, alternate
  screen, how far the view is scrolled back; puritty's boxes open; the
  ssh session's state;
- under tmux: the window and active pane, the key table and whether keys
  go by table (`send-keys -K`, TM23), the replies waited for and what for,
  puritty's tree, menus, prompts and views open, a selection and which
  pane holds the pointer, and every pane with its paste brackets, focus
  reports, mouse, alternate screen, cursor keys, size, tmux mode, key
  table, scrolled view, copy mode, and whether it is read as a nested
  control client (TM19, its output dropped).

The mark is the anchor: "the thirty lines before MARK 2, and the mark".

## DG4 · Checked

- App tests, 132 (the `diagnostics` suite, 16: keys by name and as
  `text`, the redaction of `send-keys -H` and of a long argument, a format
  kept, lines counted, the clock, a line dropped while off).
- Live, on Xvfb with a real tmux 3.8 under `-CC`, the paste scenario of
  Gilbert's report (select in session A, switch to B, type, paste with the
  right button, type, mark): 189 lines, the selection, the session change,
  each key as `text` with its `send-keys -K -H <1 bytes>`, the paste as
  `734 bytes, 12 lines, bracketed, in one piece, sent 746 bytes to tmux's
  active pane` and its three `send-keys -t '%1' -H` of 256, 256 and 234
  bytes, every reply, and the mark with pane `%1`'s paste brackets on.

## DG5 · Prompt answers and copy mode's search kept out (2026-11-12)

Found while building copy mode's incremental search and its marks
(`tmux.md` TM40, TM41), by running a search with the log on
(`bench/tmux/compare/survey.py --debug-log`): two places wrote what was
typed.

- **Commands filled from a prompt.** `Diag.command` hid only a quoted
  argument over 40 characters, so `send-keys -X
  search-backward-incremental -- '=3'` showed the search, as a short
  `rename-window` answer would have. Now a quoted argument is shown only
  when it is an id, a key's name or a format; any other is `<N chars>`.
- **Copy mode's state.** Its reply now ends with `pane_search_string`
  (TM41), and the log shows the first lines of that reply: the search is
  written by its length (`TmuxMode.withoutSearch`).

**Checked:** the same search, `C-r 3`, `C-r`, `C-r`, `BSpace`, `5`,
Enter, with the log on: every search command reads `'<1 chars>'` or
`'<2 chars>'`, and no line quotes the typed `3` or `5`. App tests 141
(four new for `Diag.command`).

## DG6 · What a program asks the terminal, for its developer (2026-11-14)

Gilbert, 2026-11-14: an application's developer may want only the probes
a program sends the terminal; and, with them, the sequences puritty
ignores. Both are options of the log.

**The setting.** `[debug] only`, beside `log`: `"probes"` keeps only the
`probe` lines; `"app"` the `probe` and `ignore` lines; unset, everything,
`probe` lines included. Start, marks, errors and end are always kept
(`Diag.keeping`). Its own setting rather than a value of `log`, so that the
settings window has a switch and a choice, and the file one type a key.

**`probe` lines** (`Vt.Probe`, at the terminal's three dispatchers): a
question as written, the name of what it asks, and the answers as written,
their control bytes named:

```
000016 10:03:01.129 probe  CSI c (primary device attributes, DA1) -> ESC[?62;21;22;52c
000018 10:03:01.129 probe  CSI 18 t (window report 18, XTWINOPS) -> ESC[8;24;80t
000019 10:03:01.129 probe  OSC 11 ; ? (background color) -> ESC]11;rgb:1d1d/1f1f/2121\x07
000020 10:03:01.129 probe  CSI > q (name and version, XTVERSION) -> ESCP>|puritty 0.1.0ESC\x5c
000021 10:03:01.129 probe  DCS + q TN (capabilities, XTGETTCAP) -> not answered
```

A CSI is caught where `dispatch` hands what is not SGR or CUP to
`dispatchRest`, which now tests the embedder's `listening` first: the two
sequences a program sends most go by unchanged. A question the terminal
does not answer is said so: one `Probe.csiName` names, a DCS `$q` or `+q`,
an OSC with `?`. An OSC 52 read is asked of the window, and said so.

**`ignore` lines**: a CSI that reaches a dispatcher's last branch, a DEC or
ANSI mode the terminal does nothing with (`ignored DEC mode 7727 set`), an
OSC no command takes, a DCS other than `$q`. A mode the terminal only
records, as DECRQM reports it (`knownPrivate`), is not ignored.

**Nothing shown is written** (DG2): an OSC's text is written only when it
is a question of numbers and `?` (`OSC 4 ; 1 ; ?`), otherwise by its size;
a title asked for (`CSI 20 t`, `21 t`) is answered by its size; a DCS's
body by its size.

**How it reaches the log**: the terminal keeps its lines (`heard`) while
`Embedder.listening` is 1 or 2, set from `[debug] log` and `only` on every
read (`Vt.listen`), so a hidden tab listens as the shown one; the loop
takes them with the replies (`Vt.takeHeard`) and writes them under `probe`
and `ignore`. A tmux pane's terminal under `-CC` never listens: tmux
answers its panes, and the log's start says so when `only` is set.

**Checked:** vt tests 100 (six in `Heard`): nothing while not listening; a
question and its answer; a question not answered; an OSC question
answered, a title not written; ignored sequences only at 2; a clipboard
read. App tests 175: the log keeping only probes, its start and marks; and
keeping everything. And run: puritty with `log = true`, `only = "app"`,
its shell printing DA1, mode 2026 and 7727 set, XTWINOPS 18, OSC 11 ?,
XTVERSION and XTGETTCAP: the lines above and `ignore DEC mode 7727 set`
(2026 is the terminal's, so not ignored), and no other line but the start
and end.

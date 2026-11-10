# The settings window and hosts: the plan to build

`settings-ui.md` settled what the settings window is (Gilbert's answers of
2026-11-06): its own window, drawn by puritty as text cells, so the
terminal beside it is the live preview; search over every page, a marker
and a reset on each changed setting; changes applied at once, with Undo;
`config.toml` edited in place by `gren-toml`; unknown keys reported, not
fatal. This document is how to build it, now that puritty also runs on
Windows (`windows.md` WS12-WS22), and how the same window will start ssh
sessions, the step before the built-in ssh client (`synthesis.md` §10.2,
`feature-plan.md` "The Windows product").

Gilbert reviewed it on 2026-11-10 and took it, with one change: what
puritty starts with is a setting (ST11, ST14). Sections are ST1, ST2,
and so on; as each step is built, its section says what was.

## ST1 · What exists today, measured 2026-11-10

**The settings are read once.** `app/src/Config.geng` decodes
`config.toml` at start, strictly: an unknown key or a bad value ends
puritty with a message. Nothing re-reads it. The config reload that
`geng-plan.md` "Between phases 3 and 4" puts first is not built.

**What a running window can change.** `Window` (the X11 and Win32 twins,
V55) can set the title (`setTitle`), the font's size (`zoom`, V50) and the
pointer. It cannot change the font family, the fallback language, its size
in cells, or the glyph cache, which `open` takes once. Everything else a
setting governs lives in `Main`'s model (colours, blink, paste button,
word boundaries, OSC 52, frame pacing) or in the core (`Vt.withPalette`).

**`os` cannot watch a file.** `Os.File` has `metadata` (with the
modification time) and `move` (a rename, atomic on both systems), but no
change notification.

**`gren-toml`'s `Toml.Edit`** sets, removes and renames keys and whole
tables in place, keeping comments and layout (`set`, `remove`, `rename`,
`removeTable`, `renameTable`, `setComments`). It has no array of tables
(`[[host]]`), so a list of hosts is a table of tables keyed by name
(ST10).

**A new puritty window is cheap to open.** Launch to the start of the
program it runs, which comes after the window and its font are open:

| | measured | |
|---|---|---|
| Linux, Xvfb on nene | 12-18 ms, 8 runs | `sh -c 'date > t'` as the program |
| Windows, beelink1 | 93-95 ms in 4 runs, 271-323 ms in 4 | `cmd /c type nul > t` |
| Windows, `cmd.exe` alone | 67-113 ms, 8 runs | the same, started without puritty |

So puritty's own share on Windows is about 15 ms in the fast runs and
about 225 ms in the slow ones; what makes the slow cluster (the font scan,
the pseudo console, the disk) is not split yet.

## ST2 · The settings window is a process of its own

`puritty settings` (the same program, a second command) opens the
settings window. A terminal that is asked for the settings starts that
command, or raises the settings window if one is open (ST9).

Why:

- **One process a top-level window** (`geng-plan.md` Q6, 2026-10-23) is
  already the rule, for isolation, and `Window` is built for one window a
  process on both platforms. A second window in the terminal's process
  would break both.
- **It opens fast enough** (ST1): about 15 ms on Linux, 0.1 to 0.3 s on
  Windows.
- **Every terminal is the preview, not only one.** Changes reach the
  running terminals through the file, which every terminal watches (ST3),
  so all of Gilbert's open windows take a new colour at once. A hand edit
  of `config.toml` is the same event, so there is one path, not two.

The alternative, a channel from the settings process to each terminal (a
socket, a named pipe), would be faster than a file by a few milliseconds
and adds a discovery mechanism, a protocol and a second way for a change
to arrive; the file watch is needed anyway for hand edits.

## ST3 · Watching `config.toml`

Each terminal races a wait for "the settings directory changed" with its
other waits, as it races the pty and the window. On a change it reads the
file again, decodes it, and applies what differs (ST4). A file that no
longer decodes changes nothing; the error goes to the terminal as a
notice (`settings-ui.md` §5), and the settings in force stay.

The directory is watched, not the file, because the writer replaces the
file by a rename (ST6), which a watch on the old file does not see.

This needs **a change wait in `os`**, which it does not have: inotify on
Linux, `ReadDirectoryChangesW` on Windows, as a task like the pty's read.
That is geng-lang work, registered there when it is built. Polling the
file's `metadata` every 250 ms would work without it, at up to a
quarter-second lag and a wake-up four times a second in every terminal,
even one whose cursor does not blink. Leaning: the change wait.

## ST4 · What each setting needs to apply to a running window

| setting | applied by | new |
|---|---|---|
| colours, palette, bold is bright | the model's `Look`, `Vt.withPalette`, a full redraw | |
| cursor blink | the model | |
| frame interval, sync timeout | the model | |
| word boundaries, paste button, OSC 52 read | the model | |
| font size | `Window.zoom` | |
| font family, fallback language | the faces opened again | `Window.setFont`, `zoom` generalised |
| glyph cache | the cache begun again at its new size | part of `setFont` |
| charset | a new decoder and encoder at the next read | |
| scrollback | kept to the new bound as it next grows; a smaller one drops the oldest rows | a `Vt` call |
| title | `Window.setTitle`, while the program has set none | |
| columns, rows | **the size new windows open at**; a running window keeps the size it has | |
| program | **new windows only** | |

The two "new windows only" rows say so on their rows in the window
(`settings-ui.md` §3). The test is a gate like the pointer gate: a
terminal on Xvfb, `config.toml` rewritten under it, and the pixels and
the model held to what a fresh start with the new file gives.

## ST5 · One schema for every setting

`settings-ui.md` §2's table, in Geng: a module `Settings` with one entry a
setting, each with its key (`["font", "size"]`), its kind, its default,
its label, its description, its search words, its page and whether it
applies at once. The kinds are few:

- an integer in a range (`font.size`, 4 to 200);
- a colour (`#rrggbb`);
- a list of colours (the palette);
- one of a set (`charset`: `utf-8`, `euc-kr`, `cp949`);
- a font family (chosen from the families the system has, ST8);
- text (the title, the word boundaries);
- a command (an array of strings).

From the table come: the decoder (lenient: an unknown key or a bad value
is a report with its line, and the rest decode; a near miss is offered,
`font.sise` → `font.size`), `Config.defaults`, the window's rows, the
search, and the example at the top of `Config.geng`. A test holds the
documented example to the table.

## ST6 · Writing the file

- `Toml.Edit.set` for a changed key, `remove` for one reset to its
  default (its table too, when nothing is left in it and no comment is
  over its header, ST18). Only the keys
  touched change; the file is never generated again.
- Written to `config.toml.new` beside it, then moved over it: a terminal
  reading at that moment sees the old file or the new one, never half.
- `config.toml.bak` is the file as it was before the settings window's
  first write in a session.
- A text field is written when it holds a valid value: `#c5c8` is not
  written, `#c5c8c6` is. A change reaches the terminals in the time of one
  write and one wait, with no half-second debounce.
- Tests: a commented sample written unchanged is byte for byte the same;
  a key set then reset gives the file back; every kind round-trips.

## ST7 · Drawing the settings window: a screen of its own, fed by the program

The settings window is drawn the way the terminal is: a `Vt.Term`, its
frame made by `Vt.View.frame` and drawn by `Window.draw`. The difference
is who writes into the `Term`. In a terminal it is the program on the
pty. In the settings window it is the settings program itself: its view
of the model is written as the bytes a full-screen text program writes
(cursor moves, colours, text), and fed to its own `Term`.

What that gives for nothing: the renderer, the fonts and their fallbacks,
CJK and Thai, the IME and its preedit (a host name typed in Hangul works),
selection and copy, the clipboard, zoom, and both platforms. Keys and the
pointer come from `Window`'s events directly, as decoded keys and cells,
so no key encoding is involved.

It is testable without a window. The model is pure: a test feeds it keys
and clicks and holds `Vt.dump` of its screen and the bytes of
`config.toml` to pins, as the replay corpus holds the core
(`harness/settings.py`, run on Linux and, with `--windows`, on Windows).

**Its own look.** The settings window does not take the user's font or
colours: the platform's default font (`Platform.font`) at the default
size, and a fixed palette, so that a bad setting (a 4-point font, white
on white) cannot make the window that fixes it unreadable.

## ST8 · What the window needs from the platform

- **The font families.** A font row is a list to filter, not a name to
  type. Linux asks fontconfig for the monospace families;
  `packages/win32` already scans Windows' fonts for its fallbacks
  (`scan_everything`) and lists their families. A `Window.fonts` call on
  each.
- **Raising another window**, so that Ctrl+Comma with a settings window
  already open brings it forward instead of opening a second: on X11 a
  `_NET_ACTIVE_WINDOW` request for the window of class
  `puritty-settings`; on Windows `FindWindowW` and `SetForegroundWindow`,
  which Windows allows because the terminal asking has the foreground.

## ST9 · Opening it

As `settings-ui.md` §1 decided, plus what Windows offers:

- **Ctrl+Comma** in any terminal, on both systems.
- **Ctrl+right-click**: a small menu with "Settings…" and, once hosts
  exist, "New session" and the hosts. On Windows the menu is Windows' own
  (`TrackPopupMenu`): cheap, and what PuTTY users know. On Linux puritty
  draws it in the terminal window, over the cells, as it draws the IME's
  preedit.
- **Windows' system menu** (Alt+Space or the title bar's icon) gets
  "Settings…" and the hosts, as PuTTY's has "Change Settings…" and "Saved
  Sessions".
- **`puritty settings`** from a shell or a shortcut (ST11).

## ST10 · Hosts

A host is a named way to start an ssh session, kept in `config.toml`:

```toml
[hosts."build-box"]
host = "build.example.com"
user = "gilbert"
port = 22                      # left out: 22
identity = "~/.ssh/id_ed25519" # left out: ssh's own choice
jump = "bastion"               # another host's name, or user@host:port
command = "tmux new -A -s main" # run there; left out: the login shell
charset = "euc-kr"             # this host's, over the global one

[hosts."build-box".colours]    # this host's look, over the global one
background = "#2a1010"
```

- **A host's own settings** are the global ones with its overrides on
  top: the look (colours, font), the charset, the title. A red background
  for production is the common use. Groups, whose settings pass down to
  their hosts (`settings-ui.md` §6, Termius's model), come after.
- **Passwords and passphrases are never in the file.** With OpenSSH, ssh
  asks in the terminal, as it does today; the Windows credential store
  comes with the built-in client.
- **`~/.ssh/config`'s hosts are listed too** (`%USERPROFILE%\.ssh\config`
  on Windows), read-only and marked as from there, and connected as `ssh
  alias`, so OpenSSH applies its own file. Only `Host` lines with no
  wildcard are listed; nothing is copied into `config.toml`. A full parser
  (`Match`, `Include`, tokens) comes with the built-in client
  (`synthesis.md` §10.2), which needs one anyway.

**Starting a session.** `puritty --host build-box` (ST11) opens a terminal whose
program is OpenSSH: `ssh -p 22 -l gilbert -i … -J … -t build.example.com
'tmux new -A -s main'`, built from the entry, on the pty as any program
runs today (WS9, WS20: Windows' `ssh.exe` already works on the pseudo
console, host-key question included). Its title is the host's name. From
the settings window, Connect starts that command as a new process, so
each session is its own window (Q6).

**When the built-in client comes** (Windows), the same entry starts it
instead, and nothing a user saved changes. Until then one thing does not
work on Windows: a host whose charset is not UTF-8. ConPTY carries a
program's output as UTF-16, so EUC-KR bytes from the remote end become
U+FFFD before puritty sees them (`synthesis.md` §10.1). On Linux,
`ssh` on a pty passes them through and the charset works. That is one
of the built-in client's reasons.

**Quick connect**: a field at the top of the Hosts page takes
`user@host:port`, connects with it, and offers to save it.

## ST11 · The Hosts page, and starting puritty on Windows

The settings window gets a **Hosts** page (`settings-ui.md` §3 "later"):
the hosts, filtered by the window's search, each row its name, `user@host`
and where it is from; Enter connects; New, Duplicate, Rename, Delete; a
host's form is its fields and its overrides, each with the marker and
reset every row has.

**What starting puritty does** is a setting (*Gilbert, 2026-11-10*,
V64), since one machine is mostly an ssh client and another mostly a
local shell, and `config.toml` is each machine's own:

```toml
start = "shell"           # the default: a local shell on a pseudo terminal
start = "hosts"           # the host list; no pseudo terminal until asked
start = "host:build-box"  # straight into one saved host
```

The command line always wins over it:

| command | opens |
|---|---|
| `puritty` | what `start` says |
| `puritty -- htop`, `puritty shell` | a local program on a pseudo terminal |
| `puritty --host build-box` | a saved host |
| `puritty ssh user@host:port` | a quick connect |
| `puritty hosts` | the host list |
| `puritty settings` | the settings window |

A shortcut is `puritty.exe` with arguments, so no second Start-menu entry
is needed; one is made only for what is not the machine's default. A
`start` that differs by machine within one shared file
(`[machines."beelink1"]`) waits until a file is shared.

**The host list becomes the session** when it is how puritty started
(*Gilbert, 2026-11-10*, V65), as PuTTY's dialog does: Connect turns the
same window from the list into a terminal running ssh, with the host's
font and size. It is still one window a process. Opened from a running
terminal (the Ctrl+right-click menu, the system menu), the list starts
each session in a new window and stays, since a session is already open.

Windows' taskbar jump list (right-click on the taskbar icon) listing the
hosts is a later nicety.

## ST12 · The order to build

Each step ends with its gate passing and this document saying what was
built, as the Windows steps did.

1. **The change wait in `os`** (geng-lang): inotify and
   `ReadDirectoryChangesW`, with its own test there. *Built (ST15).*
2. **Config reload**: ST3 and ST4, with `Window.setFont`; the reload gate
   on Xvfb, and on beelink1 by `--windows`. *Built (ST15).*
3. **The schema and the lenient decoder** (ST5), the notice in the
   terminal for a bad key, the documented example from the table.
   *Built (ST17).*
4. **Writing** (ST6), with its round-trip tests. *Built (ST18).*
5. **The settings window** (ST7, ST8): every page of today's settings,
   search, modified only, reset, Undo; `harness/settings.py`.
6. **Opening it** (ST9): Ctrl+Comma, the Ctrl+right-click menu, the
   Windows system menu, raising one already open.
7. **Hosts** (ST10, ST11): the entries, `~/.ssh/config`'s, `--host`,
   quick connect, the Hosts page, `start` (V64) and the list that
   becomes the session (V65).
8. **Key sounds** (`feature-plan.md` §3), the first setting added through
   the schema.

Then the built-in ssh client's survey, which starts from ST10's entries.

## ST13 · Geng-side work

To be registered in geng-lang's `docs/open-items.md` as each is built:

- `os`: a wait for a directory's change (ST3), on Linux and Windows.
- Nothing else is known to be missing: the settings window is a Geng
  program on the packages puritty already has.

## ST14 · Gilbert's answers (2026-11-10)

Gilbert took the plan, and question 8 became a setting:

- **V57 · The settings window is its own process** (ST2), which every
  terminal follows through the file.
- **V58 · A change wait in `os`**, not polling (ST3), built in geng-lang
  first.
- **V59 · Columns, rows and the program apply to new windows only** (ST4).
- **V60 · The settings window keeps its own look** (ST7).
- **V61 · Hosts are `[hosts."name"]` tables in `config.toml`** (ST10).
- **V62 · A host's overrides are its look, charset and title** at first;
  groups later.
- **V63 · `~/.ssh/config`'s hosts are listed read-only**, connected as
  `ssh alias` (ST10).
- **V64 · `start` says what plain `puritty` opens** (`shell`, `hosts`,
  `host:NAME`), and the command line overrides it (ST11).
- **V65 · The host list becomes the session** when puritty started on it;
  from a running terminal it starts new windows (ST11).
- The Ctrl+right-click menu is Windows' own on Windows and drawn by
  puritty on Linux (ST9), as leaned.

## ST15 · Steps 1 and 2 built: the change wait, and config reload (2026-11-10)

**Step 1, in geng-lang** (Dnene39, `m4-puritty.md` §VA64, geng-lang
b2c8bf31): `Os.Directory.watch` delivers a directory's changes into a
`Source`, `Added`, `Removed`, `Changed`, `Lost` and `Gone`, as
`Os.Signal.listen` delivers signals; inotify on Linux,
`ReadDirectoryChangesW` on the loop's completion port on Windows. Measured
on all three: Windows also says a file replaced by a move was `Removed`,
which Linux does not, and Wine never says the watched directory is `Gone`.

**Step 2, config reload.** Each terminal watches its settings file's
directory (made first when it is the user's and not there yet, so that a
file written into it later is seen) and races the watch with its other
waits. A change to the file, or `Lost`, has it read again 50 ms later, so
that an editor's save, often several writes, is read once and whole. What
decodes is applied by difference (ST4):

- the colours and the palette, with every cell drawn again;
  `Vt.setPalette` sets the named colours over the defaults, so a palette
  made shorter gives the rest back, where `withPalette` keeps them;
- a new family, fallback language or glyph cache opens the faces again
  (`Window.setFont`, `pt_refont` in `packages/text`, the window kept at its
  size in pixels as a zoom keeps it); a new size alone is a zoom;
- the scrollback's bound, `Vt.setScrollbackBytes`: the oldest pages over it
  dropped at once, and a bound of none clearing the scrollback as ED 3
  does, so that the terminal holds what one made with the bound would;
- the charset, the word boundaries, and what is read where it is used
  (the blink, the frames, the paste button, OSC 52, the title).

A file that does not decode, or a family Windows does not have, changes
nothing and is said on standard error; the notice in the terminal is step
3's. On Linux fontconfig answers a family it lacks with the closest it
has, at a start as at a reload, so there it is a change. A removed file is
the defaults.

**The reload gate**, `harness/reload.py`: each case starts puritty on one
file, rewrites it under it (in place, as an editor saves, or by a rename,
as the settings window will), and holds the window's own picture to a
fresh puritty's with the new file, over the part both cover. The picture
is `PURITTY_SHOT`, a file the app writes each frame to when it is set, as
`PURITTY_IME_LOG` serves the IME gate. **12 of 12 on Linux** (Xvfb, the
pixel gate's fonts) and **11 of 11 on Windows** (`--windows beelink1`, in
the ssh session's window station): colours in place and by rename, the
palette set and shortened, bold as bright, the size, the family, the
language (Korean to Japanese Han), a missing family, a file that does not
decode, a file removed, and on Linux the title. The core's tests gain a
`Settings` suite (75 of 75): the palette set and shortened, the scrollback
cut and emptied, each held to a terminal made with the new setting.

**Held as before:** pixels 36 of 36 on Linux and on Windows, pointer 51 of
51, IME 14 of 14, replay 325 of 325, events 13 of 13 on Windows, and the
core's counts and times within their record (`perf.py`).

**Left open:**

- *The window's title on Windows.* The settings' title is the window's
  while the program has set none, and under a pseudo console the program
  always has: conhost titles each program with its path as it starts
  (`C:\WINDOWS\system32\cmd.exe`, measured), as Windows Terminal shows it.
  So `[window] title` is never seen on Windows, and the title case is
  Linux's. A question for Gilbert (ST16).
- *A charset changed between UTF-8 and another* changes puritty's decoder
  at once, but not the pseudo terminal's `IUTF8` flag, which `Os.Process`
  sets when the program starts; only a program reading in the kernel's
  line mode (a plain `cat`, not a shell's line editor) sees the
  difference, in how a backspace erases. New windows have it right.
- What is read where it is used (blink, frames, paste button, OSC 52, word
  boundaries) is not pictured by the gate; it is `m.config` replaced.

## ST16 · A question for Gilbert (2026-11-10)

1. **The title on Windows** (ST15): the pseudo console names every program
   by its path, so the settings' title never shows. Windows Terminal has a
   per-profile `suppressApplicationTitle` for this: the profile's title
   wins over the program's. *Leaning:* the same as a setting on both
   systems, `[window] keep_title = false` by default, which a host's
   overrides (ST10) can set, since a host's name is the title one wants
   for an ssh session.

## ST17 · Step 3 built: one table of the settings, read leniently (2026-11-10)

**`app/src/Schema.geng`** holds every setting once (ST5): its key, its
kind (a whole number in a range with its unit, text, on or off, a colour,
a list of colours, one of a set, a font family, a command), whether it may
be left unset (`font.language`, `terminal.charset`), its label,
description and search words, its page, whether it applies at once or to
new windows, and how it reads and writes its part of a `Config` through
one `Value` type, so that the decoder, and the settings window after it,
walk one list. `Config` keeps the record and its defaults.

**The decoder is lenient** (`settings-ui.md` §5): a key that is not a
setting, a table that is not one of settings, or a value a setting does
not take is a report with its line, and the setting is left at its
default while the rest are read. A near miss within two edits is named:
`font.sise is not a setting; did you mean font.size?`, `[fonts] is not a
table of settings; did you mean [font]?`, `font.size: 2 is not from 4 to
200; 11 is used`. gren-toml keeps no positions, by design, so a key's line
is counted from the document's expressions, each a line but for a value
that runs on; its integers are read through its own decoder (`at`,
`int`), the only way it gives an `Int`. gren-toml needed no change.

A file that is not TOML at all is not read: at a start the defaults are
used, at a reload the settings in force are kept, and either way the
report says so. A file the command line names that cannot be read still
ends puritty, as a command line that names nothing usable should.

**Where a report shows.** On standard error, always. At a start, as
`settings-ui.md` §5 has it, as lines in yellow at the top of the window,
before the program's first output. At a reload a line written into the
terminal would land in the middle of a full-screen program, so it is
shown in the title instead, `[settings: config.toml line 6: font.sise is
not a setting; did you mean font.size? (and 1 more)]`, as puritty already
shows `[N characters sent as ?]`; the title keeps it until a read is
clean, a start's reports too.

**The example is the table's.** `Schema.example` is the documented file,
every key with what it means; a test holds it to the table (it decodes
with nothing reported, it names every setting in its table, its values
are read).

**Held by:** `app/tests` (gren-unit-node on node, `app/linux`'s
`Platform`), 19 of 19: the defaults, the example, a misspelt key and
table with their nearest, a key with nothing near, values out of bounds,
of the wrong kind, a bad colour, a choice not offered, a palette too
long, a line after a value that runs on, reports in the file's order, a
file that is not TOML, an optional setting left out, and each setting
reading back what it set. The reload gate's cases for this: a file not
TOML keeps the settings in force; a bad value is what a fresh start with
the key left out gives; the title carries a report and loses it once the
file is fixed. **15 of 15 on Linux, 14 of 14 on Windows**; pointer 51 of
51 and IME 14 of 14 hold. The start notice was looked at once: two lines
in yellow above the program's first line.

## ST18 · Step 4 built: writing the file (2026-11-10)

**`Schema.write`** changes one setting in a parsed document: `Toml.Edit.set`
when it differs from its default, which keeps the file's comments and
layout and leaves a value the file already means as the file writes it
(`rows = 0x1E` stays when 30 is written); `Toml.Edit.remove` when it is
its default or unset, so the file holds only what differs.

A table left empty by a reset goes too, unless a comment is over its
header. In gren-toml a comment directly above a `[header]` is the header's,
and `removeTable` takes it with the table: the first form lost a file's
opening `# kept by hand` when the last key of the `[font]` under it was
reset. An empty `[font]` left in the file costs nothing; a user's comment
lost is what `settings-ui.md` §5 says never happens.

**`SettingsFile.change`** is the write on the system: the file read as it
is now, so that a hand edit since is kept; parsed from its bytes, so that
one that is not UTF-8 or not TOML is refused and nothing in it is lost;
nothing written when the edit changes no byte; else written whole to
`config.toml.new` and moved over the file (`MoveFileExW` replaces on
Windows), so that a terminal reading it (ST3) sees the old file or the new
one. The first write of a session copies the file as it was to
`config.toml.bak`, and a missing file's directory is made.

**Held by:** `app/tests`, 30 of 30, with the writing suite: a setting
written as it is changes no byte; a value the file spells otherwise is
kept as spelled; a setting set and reset gives the file back, in a table
the file had and in one it lacked; a set setting reads back; a reset takes
its key and the key's comment and keeps the table's others; an emptied
table goes, and stays under a comment; an optional setting unset goes;
every setting written to an empty file reads back as written and is
reported for nothing. `harness/store.py` runs `SettingsFile.change` on the
system, step by step, and holds the file, its backup and any `.new` to one
pin, **the same on Linux and on Windows** (`--windows beelink1`): a file
and a directory not there, the same value writing nothing, a hand edit
kept, one backup a session, a new session's backup, both settings reset,
and a file that is not TOML refused with its line.

One edge of gren-toml was seen and needs no change: a file whose last
line has no newline gains one when a table is added after it, and keeps it
when the table is removed. A file written by an editor ends its last line.

## ST19 · Step 5a built: the settings window's model and screen (2026-11-10)

Step 5 is built in three parts: **5a**, what the window shows and what
each key does, pure and tested without a window; **5b**, `puritty
settings`, the program around it (its window, the font list of ST8, the
file written and followed); **5c**, the mouse beyond a click.

**`app/src/SettingsWindow.geng`** is the model, its update and its view.
The view writes the screen as a full-screen program writes one (every row
by its position, SGR for the styles, the cursor shown only where something
is typed), which the program will feed to a `Vt.Term` of its own and draw
(ST7). The layout is `settings-ui.md` §3's: the search on the top row and
Modified only at its right, the pages on the left with a count beside each
(changed settings, or a search's matches), each setting in three rows (a
marker when it differs from its default, its label, its value, a reset
mark; its description, with "New windows take it." for V59's; a space),
and the focused setting's key and the keys' hints at the foot.

Keys: Tab and Shift+Tab between the search, the pages and the settings;
Up, Down, Page Up, Page Down, Home, End; Enter turns an on-off setting,
goes round a choice (the system's among an optional one's), or begins
typing the rest; Delete or Backspace resets; Ctrl+Z undoes; Ctrl+M is
Modified only; Ctrl+F, or typing in the list, searches; Esc stops typing
(putting back what was there), clears the search, or closes. What is
typed is written each time it is a value the setting takes, so the
terminals follow it as it is typed (ST6); one that is not is shown as the
problem at the foot and not written. An input method's commit is typed as
keys are; text is fitted to the window by cell width, as the core counts
it (`Vt.Width`, now exposed by `vt`).

`Schema` gains `toText` and `fromText`, a setting's value as the window
edits it (a palette as colours joined by commas, a command as words
quoted where they hold a space) and back, with the file's checks.

**Held by** `app/tests`, 45 of 45: the settings window's 15 feed keys,
text and clicks to the model and hold the screen, as `Vt.dump` reads it,
and the effects asked for: the first screen, moving, a number typed and
written while valid, one refused, undo, Esc putting back, on and off with
its marker, a reset, a search across pages with its counts, a choice
going round, Modified only empty, Esc closing, Hangul committed and drawn
two cells a character, a page clicked, a narrow window.

## ST20 · Step 5b built: `puritty settings` (2026-11-10)

`puritty settings [--config FILE]` opens the settings window: a process of
its own (V57), the same program with a first word that the terminal's
command line does not take, so `puritty -- settings` still runs a program
of that name. **`app/src/SettingsProgram.geng`** is the window around
`SettingsWindow` (ST19): it opens a `Window` with its own look (V60: the
platform's font at the default size, the default colours), feeds the
model's screen to a `Vt.Term` of its own and draws it with `Vt.View` as
the terminal draws, and turns the window's events into the model's
inputs: keys (a press or a repeat), an input method's commit and its
preedit, drawn as the terminal draws one, a resize, a left click by cell,
and closing. Each `Write` is `SettingsFile.change` with `Schema.write`
(ST18), and a write that fails is shown at the foot. The settings file's
directory is watched here too (`watchSettings`), so that an edit by hand
shows in the window; the window's own writes come back that way as what it
already shows. **`app/src/SettingsSource.geng`** holds what the terminal
and the window share: where the file is, reading it leniently, and
watching it, moved out of `Main`.

**The settings gate**, `harness/settings.py`: `puritty settings` on Xvfb,
driven with xdotool's keys, its file held to a pin. **9 of 9**: a size
typed, bold turned on, a reset that takes its emptied table, a file's
comments kept, an undo, a search and a choice, a value typed that the
setting does not take (nothing written), an edit by hand read before the
next key (bold turned on by hand, then off by Enter), and a terminal beside
the window taking a background typed in it, as its own picture shows. On
Windows the window was opened on beelink1 and pictured: Cascadia Mono,
`%APPDATA%`'s file read, a Hangul title counted on its page.

**Held as before:** `app/tests` 45 of 45, pointer 51 of 51, IME 14 of 14,
reload 15 of 15 on Linux and 14 of 14 on Windows.

**Left for 5c and after:**

- *The font list* (ST8): a font is typed by its family's name for now;
  `Window.fonts`, the families each platform has, and a list to filter
  come next.
- *The mouse* beyond a left click on a page or a setting: the wheel, a
  click on a value to change it, on the reset mark, on Modified only.
- *The settings gate on Windows*: the window is pictured there, not yet
  driven with keys; `harness/events`' driver can do it, in Gilbert's
  session.
- *Opening it from a terminal* is step 6.

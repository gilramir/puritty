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
   Windows system menu, raising one already open. *Ctrl+Comma and raising
   built (ST22).*
7. **Hosts** (ST10, ST11): the entries, `~/.ssh/config`'s, `--host`,
   *(entries, `--host`, `ssh`, `shell` and `start` built, ST23)*
   quick connect, the Hosts page, `start` (V64) and the list that
   becomes the session (V65).
8. **Key sounds** (`feature-plan.md` §3). *Gilbert, 2026-11-10: low
   priority, moved to the very end, after the built-in ssh client.*

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

## ST21 · Step 5c, first part: the system's fonts offered (2026-11-10)

**`Window.fonts`** (ST8) answers the families of the monospace fonts the
system has, sorted, each once. On X11 it is fontconfig's list of the
fonts whose spacing is mono, dual (most CJK monospace fonts) or charcell;
on Windows every face `packages/win32` reads, those FreeType says are
fixed-width and are not colour.

**While a font is typed** in the settings window, the system's families
that hold what is typed are offered beneath it, eight at a time; Up and
Down choose one, Enter takes it, or takes the name typed when none is
chosen. A font is written when it is taken, not as its name is typed,
which would have every terminal open a new font at each letter.

**A defect found on the way, in `packages/win32`:** `scan_everything`,
which reads every font Windows has, asked `scan_family("")`, whose test
for a name wanted the character after the empty prefix to be a space or
`&`, so it read none. The fallback's last resort (any face that has a
character no listed face has) therefore never searched beyond the faces
already opened. An empty family now reads every font. Measured on
beelink1: the settings window's first frame 0.82 s after it starts the
first time, the fonts' files not yet in the system's cache, and 0.22 s
after (Window.fonts reads every face once).

**Measured on beelink1** in Gilbert's session with the events gate's
driver: "cas" offers Cascadia Mono; nothing typed offers BatangChe,
Cascadia Code, Cascadia Mono, Consolas, Courier New, DejaVu Sans Mono,
DotumChe and Fira Code first.

**Held by:** `app/tests` 48 of 48 (a font offered as typed, written when
chosen, a name typed taken as typed); the settings gate 10 of 10, with
`font-chosen` (Fira Code from "fira" on the gate's fonts); pixels 36 of 36
on Linux and on Windows, events 13 of 13, reload 14 of 14 on Windows.

## ST22 · Step 6, first part: Ctrl+Comma, and one settings window (2026-11-10)

**Ctrl+Comma** in a terminal starts the settings window: this program's
own file again (`Os.Env.executable`, geng-lang Dnene40, which `os` did not
have), with `settings`, and `--config FILE` when the terminal was given
one, on `Os.Process`'s `Ignored` connection, so that it is tied to the
terminal by nothing and outlives it. A failure is said on standard error.
In the usual key encoding a program cannot tell Ctrl+Comma from a comma,
so nothing a program could ask for is taken from it (`settings-ui.md`
§1).

**One settings window.** `puritty settings` first looks for a window
titled "puritty settings" and, if there is one, brings it forward and
ends (`Window.raise`, ST8): a second Ctrl+Comma, or a second `puritty
settings` from a shell, raises the first. On X11 the candidates are the
window manager's `_NET_CLIENT_LIST`, or with none the root's children and
theirs, matched by `_NET_WM_NAME` or `WM_NAME`; one found is asked active
with `_NET_ACTIVE_WINDOW` and raised and focused itself, for a display
with no window manager; it is asked on a connection of its own, before
this process has a window. On Windows it is `FindWindowW` of puritty's
class and the title, and `SetForegroundWindow`, which Windows allows a
process the foreground one started.

**Held by** the settings gate, now 12 of 12 with two cases: `ctrl-comma`
(one window after one Ctrl+Comma, and after two) and `second-raises` (the
second ends with 0, one window). **On Windows**, in Gilbert's session
with the events gate's driver: Ctrl+Comma in a terminal started one child
`puritty.exe` titled "puritty settings", and it took the foreground (the
driver's own check that the terminal had it stopped the case, which is
the sign); a second `puritty settings` over ssh ended with 0, the first
still running. Held as before: `app/tests` 48 of 48, pointer 51 of 51, IME
14 of 14, reload 15 of 15 and 14 of 14, pixels 36 of 36 on both, events 13
of 13.

**Left of step 6:** the Ctrl+right-click menu (Windows' own on Windows,
drawn by puritty on Linux) and the Windows system menu's items, which come
with the hosts (step 7) since they list them.

## ST23 · Step 7a built: hosts, and connecting to one (2026-11-10)

**In the file.** `[hosts."name"]` tables (V61): `host` (where to connect;
a host without one is reported and left out), `user`, `port` (1 to
65535), `identity`, `jump`, `command`, `charset`, `title`, and two tables
of its look, `[hosts."name".colours]` (`foreground`, `background`,
`palette`) and `[hosts."name".font]` (`family`, `size`) (V62). Each key is
read as a setting is, a bad one reported at its line with the nearest
name. `start` (V64) is the one setting outside any table, so it comes
first in a file: `"shell"`, `"hosts"` or `"host:NAME"`. `Schema.example`
shows a host and `start`, and its test holds them.

**Connecting** (`app/src/Hosts.geng`): a session is OpenSSH's `ssh` on the
terminal as any program (WS9): `-p`, `-l`, `-i` and `-J` from the host, a
jump that names another host written as its `user@host:port`, and `-t`
with the command when there is one. Its window takes the host's colours,
font, size, charset and title over the settings', and the host's name as
its title when it gives none. A name the settings do not have is `ssh
NAME`, for ssh to resolve, so an alias of `~/.ssh/config` connects with no
entry (V63).

**The command line** (V64): `puritty --host NAME`; `puritty ssh
user@host:port`, quick connect, the user and the port left out as one
likes and an IPv6 address written `[::1]:22`; `puritty shell`, a local
shell whatever `start` says; and plain `puritty`, what `start` says. A
program after `--` wins over all of them, and `--title` over a host's
title. `start = "hosts"` opens a shell, with a notice that the host list
is step 7b's, until it is built.

**Held by** `app/tests`, 59 of 59 (hosts read whole, one without a host,
a misspelt host key, a port out of range, a name with a space, `start`'s
values, the ssh command, a jump through another host, an alias, quick
connect's forms, a session's settings), and **the hosts gate**,
`harness/hosts.py`, 8 of 8: a stand-in `ssh` first on PATH writes what it
was given, and each case holds that, the window's title and its
background: `--host` with its jump and command, an alias, `--title` over
the host's, quick connect, `start = "host:…"`, `start = "shell"`, `shell`
over `start`, and a program over `--host`. **On Windows**, `puritty.exe
--host self` (localhost) ran `C:\WINDOWS\System32\OpenSSH\ssh.exe`,
which asked its host-key question in the window, on the host's background.

**On Windows the session's title is lost** as the settings' is (ST15,
ST16): conhost titles `ssh.exe` with its path. ST16's question decides
it.

Held as before: settings 12 of 12, reload 15 of 15, pointer 51 of 51, IME
14 of 14.

## ST24 · Step 7b, first part: the Hosts page, and the host list (2026-11-10)

**The Hosts page**, after the settings' pages: quick connect first
(`user@host:port`, typed, connected to on Enter, refused with why when it
is not one), then the file's hosts, each with `user@host:port` and its
jump, then the hosts `~/.ssh/config` names that the file does not, marked
as its (`SshConfig.aliases`: the names of `Host` lines that are not
patterns; `Include` and `Match` are not read, and `ssh NAME` reads the
file itself, V63). `Platform.sshConfig` is where that file is:
`~/.ssh/config`, or `%USERPROFILE%\.ssh\config`. Enter connects. The
file's hosts are listed in their names' order, not the file's: gren-toml's
table is a `Dict`.

**What Connect does** (V65): in the settings window, opened from a
terminal (Ctrl+Comma) or by `puritty settings`, it starts the session in a
window of its own, this program again with `--host NAME` or `ssh TARGET`,
and the settings window stays. As **the host list**, `puritty hosts` or
`start = "hosts"`, it opens on the Hosts page, titled "puritty hosts", and
Connect makes the same window the session: `SettingsProgram.run` answers
`Session host`, and `Main` sets the window's font to the host's
(`Window.setFont`) and runs the terminal in it (`begin`, the half of
`startIn` after the window is open). There may be several host lists at
once, each a session to be; there is one settings window.

**Held by** `app/tests`, 64 of 64 (the page's rows and where each host is
from, Enter on a host, quick connect taken and refused, the host list
opening on it), and the hosts gate, **11 of 11**, with `host-list` (Down
and Enter in `puritty hosts`: the stand-in ssh is given the first host's
arguments and there is one window, titled as the host), `start-hosts`, and
`settings-connects` (a second window, the session, and the settings window
still there). **On Windows**, in Gilbert's session: `puritty.exe hosts`,
Down and Enter, and the same window showed `ssh.exe`'s host-key question
for beelink1 itself on the host's background. The driver's F24, which it
types to mark where a case begins, reached that question too, and ssh
ended a few seconds later; without the driver a session to the same host
was still waiting at its question after 15 s.

Held as before: settings 12 of 12, reload 15 of 15, pointer 51 of 51, IME
14 of 14.

**Left of step 7:** changing hosts in the window (a new host, its fields,
a rename, a removal), and the menus that list them (ST9: the
Ctrl+right-click menu, Windows' system menu).

## ST25 · Step 7b, second part: hosts changed in the window (2026-11-10)

*Gilbert, 2026-11-10:* the rest of the plan in this order: changing hosts
in the window, the menus, the mouse; then the built-in ssh client's
survey (begun alongside, `ssh-client.md`); key sounds last of all.

**A host's fields are settings.** `Schema.hostFields name` makes each
field of a host a `Setting` whose key is its path in the file
(`["hosts", "box", "user"]`, `["hosts", "box", "colours", "background"]`)
and which reads and writes that host among the settings' hosts, so the
window's rows, typing, live writes, reset and undo serve a host's form as
they serve the settings: where it connects (which may not be empty), the
user, the port, the key, the jump, the command, the charset, the title,
its colours, palette, font and size. Unset takes a key out, and a table of
the host's left empty with it (ST18's rule).

**The host list** has a New host row after quick connect. On a host:
Enter connects, Right opens its form, Delete removes it (its table and
those under it, and the comment over its header, which gren-toml counts
as the header's), Ctrl+D copies it as `name-2`; Right on one of
`~/.ssh/config`'s saves it as a host of the settings first. In a form, the
first row is the host's name, and a new one typed renames it on Enter, the
tables under it with it (`Toml.Edit.renameTable`); Left or Esc goes back to
the list. Ctrl+Z undoes a field as a setting, and a host made, removed,
renamed or copied by putting back the hosts as they were. The window
writes them as `PutHost` (each field set or taken out, so what the file
already says is not touched), `DeleteHost` and `RenameHost`.

**Held by** `app/tests`, 77 of 77 (a host made and its form opened, a
field changed, a field unset and where it connects kept, a host removed
and put back, renamed, copied, an alias saved, an address not written
empty; and in the file: a field set and unset giving the file back with
its comments, a colour making its table and unsetting taking it out, a
rename taking the tables under it, a removal leaving the others, every
host of the example written whole and read back as it was), and the
settings gate, **16 of 16**, with a new host given its address and user,
one removed, one renamed with its colours' table and comment, one copied.
The hosts gate's keys step past the new row (11 of 11), and its
`settings-connects` case no longer pictures the session: the settings
window and the session it starts both write `PURITTY_SHOT`'s file, so
which picture is there was a race, which a run lost.

**Found on the way:** typing where a host connects down to nothing wrote
`host = ""`; the window read its own file back, a host with no address is
left out, and the form lost its host under the typing. Where to connect
is now its own kind (`Address`), which does not take empty text.

## ST26 · Step 6 completed: the menus (2026-11-10)

**Ctrl+right-click** in a terminal opens a menu at the pointer: Settings…,
Hosts…, New window, then Connect to each host of the settings. Each item
starts this program again (`settings`, `hosts`, `shell`, `--host NAME`,
and `--config` when the window was given one), not tied to the window, as
Ctrl+Comma does (`spawnSelf`). Ctrl with the right button is puritty's
whatever mouse mode the program asked for.

**On Windows the menu is Windows' own** (`Window.menu`, `TrackPopupMenu`):
the program's thread hands the items to the window's thread, which owns
the window and shows the menu, and the item chosen comes back as an event,
`MenuChosen { menu = 0, index }`. **The system menu** (the title bar's
icon, Alt+Space) has the same items after Windows' own and a separator
(`Window.systemMenu`, as PuTTY puts its sessions there), given when the
window starts and again when a settings reload changes the hosts; one
chosen is `MenuChosen { menu = 1, index }`. Its commands go in steps of 16
from 0x1000, since Windows keeps a `WM_SYSCOMMAND`'s low four bits.

**On Linux puritty draws it**, as ST9 leaned and Gilbert took (ST14): `Vt.viewPainted`
paints the menu's box (box-drawing borders, a `▸` at the marked item; plain
text, since a cell's style is the term's) over a copy of the screen, which
`View.frameBack` draws; the term is only read, and when the menu closes the
next frame's diff draws the cells it covered again. Up and Down move the
mark, Enter starts it, Esc or any other key closes it; a left click on an
item starts it, a press anywhere else closes it. X11 gives a program no
system menu, so `Window.systemMenu` does nothing there and `Window.menu`
answers that it shows none.

**Held by:** the core's tests, 79 of 79, with `viewPainted` and `paint`
(text over a row's cells, the term left as it was, past a row's text, wide
characters two cells, a wide character cut at either edge mended); the
hosts gate, **12 of 12**, with `menu-connects` (Ctrl+right-click, the
fourth item, and the stand-in ssh started for the first host in a window of
its own); on Xvfb the menu was pictured at the pointer, the mark moved by
Down, and Esc gave the screen back cell for cell. **On Windows**, in
Gilbert's session with the events gate's driver: Ctrl+right-click showed
Windows' pop-up with the four items, and Down three times and Enter started
`puritty.exe shell`; Alt+Space showed the system menu with the items after
Close, and Up twice and Enter started `puritty.exe shell` again.

**Held as before:** `app/tests` 77 of 77, settings 16 of 16, reload 15 of
15, pointer 51 of 51, IME 14 of 14, pixels 36 of 36 on Linux and on
Windows, replay 325 of 325, events 13 of 13.

## ST27 · Step 5c completed: the mouse in the settings window (2026-11-10)

What the keys do, the mouse does where it points, through the keys' own
paths, so the two cannot drift: a click on a setting's value is Enter on
it (on and off and a choice change, the rest begin typing); a click on
the reset mark is Delete; a click on a label moves to the setting, and a
double click there is Enter; on the host list a click moves to a host and
a double click connects, and one click on quick connect or New host
begins typing; a click on a page shows it, on the search row begins a
search, on Modified only turns it over. A click while something is typed
keeps it first as Enter does, or puts back what was there as Esc does
when it is not a value. The wheel scrolls the list three rows a step. The
program counts a double click: a second press within 400 ms on the same
cell.

The marker and the reset mark now show where a reset does something: in
a host's form on a field that is set and may be unset, not on its name or
where it connects.

**Held by** `app/tests`, 85 of 85 (a click on a value, on the reset mark,
on a label, a click away keeping what is typed and Ctrl+Z undoing it, a
click away putting back what is not a value, a double and a single click
on a host, the wheel); the settings gate, **19 of 19**, with a click on a
value, on the reset mark, and on a page and a value typed after; the hosts
gate, **13 of 13**, with a double click on a host in the settings window
opening its session. **On Windows**, in Gilbert's session: a click on Bold
is bright's value wrote `bold_is_bright = true`. Held as before: reload 15
of 15, pointer 51 of 51, IME 14 of 14.

**What is left of the plan:** key sounds (step 8), last of all (ST25), and
Gilbert's answer to ST16, the title on Windows. The built-in ssh client's
survey is `ssh-client.md`, its questions in SC12.

## ST28 · A host's client (2026-11-10)

`client = "built-in"` in a host's table (`[hosts."name"]`) connects with
puritty's own ssh client (`ssh-client.md` SC18) instead of OpenSSH's `ssh`
on the terminal; `client = "openssh"` keeps `ssh`, and none takes the
platform's default: the built-in client on Windows (Gilbert,
2026-11-10), OpenSSH's on Linux. It is a
setting like the others: read with its line reported when it is neither,
on the Hosts page as **Client**, written back by the host's form, and in
`Schema.example`.

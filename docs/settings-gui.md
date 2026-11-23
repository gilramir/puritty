# A graphical settings window (2026-11-10)

Gilbert, using puritty on Windows for the first time (2026-11-10): the
settings window being text-based "like this" is not what he wants; it
should look modern, not be in a monospaced font, show an arrow pointer,
and have better widgets, the font picker first. Of the three options put
to him (puritty's own drawn widgets, a web page in a WebView, native
controls), he chose **puritty's own drawn widgets**, "to see what it ends
up looking like", and asked for the window's text in **American English
and Korean**, chosen as the system's language is: Korean on beelink1,
English on his work computer. Sections are SG1, SG2, and so on.

## SG1 · What is kept

The settings window's logic is kept whole: `SettingsWindow`'s model, its
pages, its rows, typing and its checks, undo, the hosts page and its form,
and every effect it asks `SettingsProgram` for (a write, a connect, a
host put, deleted or renamed), with `SettingsFile`'s edits that keep a
file's comments. What changes is how the model is drawn and how a click
finds what it is on: today a `Vt.Term` of the window's cells fed VT bytes,
then a drawn window of boxes and proportional text.

## SG2 · Drawing: the renderer takes two more records

puritty's renderer (`packages/text`, `puritty_text.c`) is shared by the
X11 and Windows windows and draws through two calls a platform gives it:
a fill, and glyph masks drawn in a color (`pt_glyphs_draw`). Both are
enough for a modern flat look, so the platforms need no new drawing:

- **Text at a pixel**, in the *interface font* at a size and a color:
  shaped by HarfBuzz and rasterized by FreeType as the terminal's text is,
  each code point the interface font lacks found by the same fallback
  (`pt_fallback_file`), so Hangul comes from the system's Korean font.
  The interface font is Segoe UI on Windows and the system's `sans-serif`
  on Linux (fontconfig's choice), loaded beside the terminal's.
- **A rounded rectangle** in a color, filled: its middle by fills and its
  four corners by a glyph mask the renderer makes for each radius, so its
  edges are smooth with nothing new from the platform.
- **A clip** for what follows, so a scrolled list draws only in its box.

And one question the Geng side asks before it lays a page out: **a text's
width** in the interface font at a size (`Window.measure`), answered by the
same shaping. A frame of the settings window is drawn whole each time, as
it is small: no shadow, no ink.

## SG3 · Widgets

In Geng (`app/src/Ui.geng`), each widget a function from its state to
draw records and the boxes a click lands in: a side bar of pages, a
search field, rows of a setting's name, its description beneath in a
lighter color, and its value on the right: a **switch** for on and off,
a **number field** with steps, a **text field** with a caret, a **choice**
that drops a list, a **color swatch** with its hex, and a reset button
when the value is not the default. The **font picker** is a field that
opens a list of the system's fonts, each name drawn in its own font where
the system has it, the monospaced ones first and marked, filtered as one
types, with a line of sample text. Keys work as they do today (Tab,
arrows, Enter, Escape, Ctrl+Z); the mouse finds what it is on by the
boxes.

## SG4 · Two languages

The window's own words and every setting's label and description come
from one table (`app/src/Words.geng`): English, with American spelling
(*color*, not *color*, in what the window shows; the file's keys, such as
`[colors]`, are the file format's and do not change), and Korean. The
language is the one puritty already reads from the system for its font
fallback (`Platform.locale`): on Windows the head of the user's language
list (WS21), on Linux `LANG` and `LC_*`. A language that starts `ko` is
Korean; any other is English. A setting the table has no Korean for falls
back to its English, so a new setting never shows nothing.

## SG5 · Steps

1. The renderer's records and `measure`, on both platforms, held by the
   pixels gate's new cases (text in the interface font, Hangul in it,
   rounded boxes, a clip).
2. `Ui`: the widgets, laid out and drawn; a picture of each.
3. The settings window drawn with them, and the mouse by their boxes; the
   settings gate's cases kept passing, since they drive keys and hold the
   file, not the picture.
4. `Words`, English and Korean; a picture of a page in each.
5. The font picker.

## SG6 · Where it stands (2026-11-10)

Steps 3 and 4 are done, with the widgets in `app/src/SettingsGui.geng`
rather than a separate `Ui` module; steps 1, 2 and 5 are not.

- **Drawn.** Pictures were taken on Xvfb, English and Korean, and on
  beelink1, which shows Korean in Segoe UI with Hangul from the system's
  fallback. The header is three lines tall, the search field centered in
  it, so the list starts on the window's fourth line. `SettingsWindow`'s
  `bodyRows` is the window's rows less five, which keeps scrolling in step
  with what is drawn. A label or description too long for its column
  ends in "…", cut at the longest prefix that fits by `Text.width`.
- **The name `sans-serif`.** fontconfig's name syntax reads `-` as the
  start of a size, so `sans-serif` parses as the family `sans`. It works
  on a desktop only because the system's own configs alias `sans`. The
  Linux name is therefore `sans\-serif`. The gates' `fonts.conf`
  (`harness/pixels.py`) aliases `sans-serif` to DejaVu Sans, so a drawn
  window under the gates is in a proportional face.
- **The mouse.** A click finds what it is on by the boxes `paint` returns
  (`SettingsWindow.Hit`). The settings and hosts gates click at pixels of
  the drawn window, no longer at cells. `start-hosts`'s sampled background
  is the window's own `#1f1f1f`, no longer the terminal's `#1d1f21`.
- **Still the text screen.** `SettingsWindow.view` and the cell-based
  `Click` are left from the window that was a terminal. The program no
  longer uses them; the app tests read the model through them. Their
  header has the drawn window's three lines. They are to give way to tests
  that read the model and click through `Hit`.
- **Then:** a check's message came from `SettingsWindow` in English
  only, and the font list showed its names in the interface font. SG7
  covers both.

## SG7 · The words as gren-i18next's tables, and the font list (2026-11-10)

**The words.** At Gilbert's suggestion, his gren-i18next is ported to
Geng (geng-lang `vendor/gilramir/gren-i18next`, `docs/releasing.md`
Dnene43), and `Words` uses it:

- **The tables.** There are two `Translations`, `english` and `korean`,
  built in Geng with `I18Next.fromTree` rather than read from JSON. They
  are compiled in with no file to find at run time, and a quote needs no
  escape. A window word is `window.<name>`, a page `page.<name>`, a
  message `message.<name>` or `problem.<name>`, and a setting's Korean
  `setting.<its key>.label` and `.description`. English for a setting is
  the schema's own, so `english` does not repeat it, and
  `Schema.tableKey` gives a setting's key in the tables. A text is said
  with `I18Next.trf [korean, english]`, so a key without Korean is said
  in English.
- **Messages.** What the window says is a `Words.Message`, a key plus
  the values its `{{name}}` placeholders take. Schema's checks of typed
  text (`fromText`) and every message of `SettingsWindow` and
  `SettingsProgram` are messages, said in the window's language only
  where they are drawn. A reason the system gives (a write that failed)
  is `Words.plain`, said as it is in every language.
- **What stays English.** The file's reports go to the terminal with
  the file's line numbers, so they stay English: `Schema.read` says the
  shared checks' messages in English (`inEnglish`). Its spelling is now
  American throughout ("colors", "a color as #rrggbb"), with the file's
  keys (`[colors]`) unchanged. Two of the app tests' expected reports
  changed only in that spelling.
- **The tests.** The app tests' `Words` suite holds that:
  - Korean has every English key, and English has every key of Korean's
    own words;
  - every setting has a Korean label and description;
  - every setting Korean names exists;
  - a message's values are put into its text in both languages;
  - English is American.

  A key missing from a table would show the key itself, which these
  checks catch. The app tests are 97.

**The font list.** SG3 planned "the monospaced ones first and marked".
Both platforms' lists hold only monospace fonts (`puritty_x11_fonts`,
`puritty_win32_fonts`; a proportional font is no terminal's font), so
there is nothing to mark. What changed:

- **Each name in its own font.** A new renderer record, 9, is text in a
  named font: as record 7, with the font's name (its length a byte)
  before the text. The renderer finds the face once per name through
  the platform's `pt_font_file`. The face is used only for the characters
  it has; the rest come from the interface font's faces and fallback. A
  face loaded for a name is marked `named`, so it is never a fallback for
  the interface's own text. Up to 128 faces.
- **A sample line** under the list ("Ab 0O 1lI {}[] 한글") is drawn in the
  font Up and Down picked, or in the typed name before a pick.
- **Every font is offered** while the field's name is as it was when
  typing began. The list used to be filtered by the current font's own
  name, so it showed one font until that name was erased. The list also
  used to stop at eight fonts, so a ninth could not be picked. It is now
  ten at a time and scrolls with the pick. The text view the tests read
  keeps its eight.
- **No color fonts on Linux.** fontconfig calls Noto Color Emoji
  monospace, and it was listed, its names drawn with emoji-width spaces.
  Color fonts are now left out, as Windows' list already left them out.
- **The keypad's keys.** The keypad's arrows, Home, End, Page Up and
  Down, and Delete (as NumLock off gives them) work as the main keys do.
  This was found when keys sent to beelink1 by `WScript.Shell.SendKeys`
  arrived without the extended flag, as the keypad's Down (0xFF99), and
  did nothing.

Pictures were taken on Xvfb in English and Korean (the list in DejaVu
Sans Mono and Fira Code), and on beelink1 in Korean (BatangChe, Cascadia,
Consolas, Courier New and the rest, each in its face; the sample in
Cascadia Code).

Still open: the pixels gate has no cases for records 6 to 9 (SG5 step 1),
and the app tests read the model through the old text screen (SG6).

## SG8 · A window's shape, and the host list first on Windows (2026-11-10)

Gilbert: at 100 by 30 cells the settings window "looks like yet another
terminal"; it should be a bit narrower and taller. And on Windows,
`puritty` with nothing after it should first ask where to connect,
with the built-in client (the Windows default since SC12).

**The shape.** The window opens at 84 by 38 cells. At the gates' DejaVu
Sans Mono 11 pt that is 756 by 646 pixels, a ratio of 1.17 where it was
1.76. To fit the narrower width:

- The side bar is 190 pixels, and the value column the smaller of 260
  pixels and 45% of the list.
- A setting is four lines tall (`SettingsWindow.linesPerRow`), so its
  description wraps to two lines (`wrapTwo`, broken at spaces, the second
  line ending in "…" when the rest does not fit). The label and the
  description are centered in the row (`labeled`).
- The wheel moves one setting a step.
- The text view the app tests read has four lines a row too, and its
  tests' line numbers moved with it.
- The settings and hosts gates click at the new positions.

**The host list first.** `start`'s default is now `Platform.start`:
"hosts" on Windows and "shell" on Linux, said in the setting's
description in both languages. The host list opens typing in Quick
connect, so `user@host:port` and Enter connect at once. Down (or Up)
leaves the field for the hosts under it. A key typed on Quick connect
or New host begins typing it. While typing, the footer says what to do
(`window.hintQuick`). A host's line under its name ("from the
settings", "through X", "from ~/.ssh/config") is now a message, said in
the window's language too.

The app tests are 100. The settings and hosts gates pass, 19 and 13.

## SG9 · The pixels gate holds the drawn window; kerning on X (2026-11-10)

SG5's first step. A pixels case whose first line says `ui` is a list of
the settings window's records, a line each, in pixels:

- `box X Y W H RADIUS #rrggbb` (record 6);
- `text X BASELINE PX #rrggbb TEXT` (7);
- `clip X Y W H` and `noclip` (8);
- `textin "FONT" X BASELINE PX #rrggbb TEXT` (9).

`harness/pixels.py` encodes them, and `core-pixels` draws them as one
frame, with `ui_font=` (DejaVu Sans by default, the gate's own) as the
interface font. Five cases:

- `ui-boxes`: corners at radii 0 to 20, a field, a switch;
- `ui-text`: sizes, colors, kerning pairs, an ellipsis;
- `ui-hangul`: Hangul from the Korean fallback beside Latin;
- `ui-clip`: text and a box cut, then not;
- `ui-textin`: names in their own fonts, Hangul from the fallback in a
  sample.

A name that no font has is left out of `ui-textin`. fontconfig answers
its nearest font for one, while the Windows driver, which reads its
fonts from a directory, finds none and uses the interface font.

**Kerning was lost on X.** Drawn on beelink1 (`--windows`), three cases
differed from Linux by a pixel or a few, in the lines with kerning pairs
("AVATAR", "Wo", "Va"). Both platforms shaped the same: the same
DejaVuSans.ttf, the same sizes, and the same kerned advances, printed
from each. The difference was in the drawing. X's server moves its pen
by the advance a glyph was uploaded with, which is unkerned, and the X
side starts a new element only where a glyph's place differs from the
place it predicts. The interface text gave it the kerned advance as the
prediction, so kerned pairs came out apart on X. It now gives the
uploaded advance (kept beside the glyph's id), and X starts a new
element wherever kerning moves a glyph. Windows places every glyph
where it is told and was right already. The settings window on Linux
is now kerned as it is on Windows.

Pixels gate: 41 of 41 on Linux, and the five `ui` cases on beelink1.

## SG10 · The text screen retired (2026-11-10)

SG6 left `SettingsWindow.view` and the cell-based `Click` in place, used
only by the app tests, which read the model through the terminal text
they drew. Now the tests read the model itself:

- what the window says at its foot (`m.message` in English);
- the setting with the focus;
- the rows listed, as `key = value`;
- whether a row differs from its default;
- the pages' counts;
- the fonts offered;
- the hosts listed, with their lines in English.

They click through the targets the drawn window's boxes give
(`Hit { target, count }`). `view` and its screen, rows, header, footer,
cursor and cell widths are gone, with `Click`, `clickOn` and the
column constants, and SettingsWindow is 1,252 lines where it was about
1,870. One test went with it: "a narrow window still draws every row"
counted the text screen's lines. The wheel's test reads the scroll
(one setting, `linesPerRow`). The app tests are 99. The settings, hosts
and sshwindow gates pass, 19, 13 and 8.

## SG11 · The host list's window becomes a terminal's size (2026-11-11)

*Gilbert, 2026-11-11, trying the Windows build:* after typing `nene` in
the host list, the session ran in a window of the settings window's shape
(84 by 38 cells, narrower than tall, SG8). With no size remembered, a
session's window should be a terminal's, wider than tall.

The window packages had no way to size their window from the program:
`Window.resize { cols, rows }` is new in both. On Windows it adds the frame
for the window's style and resolution (`AdjustWindowRectExForDpi`) and calls
`SetWindowPos` where the window is, leaving a maximized window alone; on X11
it configures the window's width and height, which the window manager may
adjust. Either way the platform reports the new size, as a user's resize.
When a host is chosen in the host list, `Main.hostList` sizes the window to
the session's `[window] columns` and `rows`, 80 by 24 unless set, before the
session begins. puritty remembers no window size of its own yet; the
settings' size is the one it has.

**Checked** in the hosts gate, whose cases that drive a window now pin its
size from its picture: `host-list`, Enter on a host, ends at 720 by 408
pixels, 80 by 24 cells of the gate's font, where it was 756 by 646, the
host list's 84 by 38; `start-hosts`, the list opened and nothing chosen,
stays 756 by 646.

## SG12 · A setting's description is never cut (2026-11-11)

*Gilbert, 2026-11-11:* on the Mouse & selection page, "Copy the selection
to the clipboard"'s description was cut off. Descriptions are not to be
hidden.

A row was `linesPerRow` (4) lines tall and its description at most two
lines, the second ending in "…" (`wrapTwo`). Now a description wraps into
as many lines as it takes (`SettingsGui.wrapAll`; only a single word too
wide for a line is still cut), and a row is as tall as its label and
description need with 8 pixels above and below at the gate's font, never
fewer than 4 lines. The drawing measures the rows (`SettingsGui.measure`,
which needs text widths) and the program hands the counts to the window
(`SettingsWindow.withRowLines`) before each input and each frame, so the
wheel's limit and keeping the focused row in view count the rows as drawn
(`rowLines`, `rowTop`); a window never measured, as in the app tests,
counts 4 lines a row as before.

**Measured** at the settings gate's font (17-pixel lines): every
description that fit in two lines keeps its 68-pixel row; the color
scheme's, five lines at that width, takes 119. The gate's two click cases
aim at "bold is bright", which is below it and moved from 425 to 476.
Settings 19 of 19, app tests 102.

## SG13 · A choice drops its list (2026-11-11)

*Gilbert, 2026-11-11, on the color schemes:* "I wish the widget acted
more like a pop-up menu. I can't see all the choices at once; I can only
click one by one."

The design above had a choice "that drops a list"; what was built made
Enter and a click step to the next choice, which is no way to choose among
sixteen schemes. Now Enter or a click on a choice's field opens its list
(`SettingsWindow.choosing`), the pick on the value it has:

- **Keys:** Up and Down move the pick, Home and End go to the ends, Page Up
  and Down by ten, the wheel by one. Enter or Space take the pick, Escape
  leaves the value as it was, and either closes the list. Any other key,
  Ctrl+Z among them, does nothing while it is open.
- **Mouse:** a click on a choice takes it; a click anywhere else only
  closes the list.
- **Drawing** (`SettingsGui.choiceList`): the font picker's list box, under
  the field or over it where there is more room, as many 26-pixel items as
  the room holds, the pick in the accent color and the value it has
  ticked. A list longer than the room scrolls with the pick and shows ▴ and
  ▾ where there is more. An optional choice lists "the default" first.

**Checked:** app tests 104. The test "Enter goes round a choice" is
replaced by three: Down and Enter take the next choice, Escape changes
nothing, and a click on a choice takes it where a click off the list only
closes it. In the settings gate `search-and-choice` presses Down and Enter
in the list. The new `choice-list-open` case leaves the color scheme's
list open for its picture: 10 of the 18 schemes at the gate's 38 rows,
"puritty" ticked. Settings 20 of 20.

## SG14 · Recent connections, and quick connect with a command (Dnene59, decided 2026-11-14; not built)

Gilbert, using the host list on Windows: it should remember the last hosts
connected to, so one is a click away; and a connection is more than a
host, a user over the host's or a command instead of the shell. The host
list already has the whole of a connection in a saved host (`[hosts."name"]`:
host, user, port, identity, jump, command, charset, colors, font), but
quick connect forgets what was typed, and "New host…" did not say that it
makes one of those.

**Dnene59, Gilbert's answers:**

1. **A Recent section at the top of the list**, the last **8**
   connections made, newest first. One is the whole connection: user,
   host, port and command; the same connection again moves to the top.
   Kept in a state file beside the restore directory, not in the settings
   file; a setting for how many, 0 for none. No password or passphrase is
   ever kept.
2. **Quick connect takes a command after a space**, as `ssh` does:
   `gilbert@build tmux -CC attach` connects as gilbert and runs `tmux -CC
   attach`. **The screen says so** (Gilbert: the user has to know it is
   possible): the empty field shows a grayed example,
   `user@host:port command`, and the footer while typing says that what
   follows a space is the command to run, in both languages.
3. **A recent made from a saved host names the saved host**, so later
   changes to it apply; a recent made by quick connect keeps what was
   typed.
4. **Save… on a recent** opens the saved host's form filled in from it;
   Delete removes a recent.
5. **A saved host's second line says what it does**, `user@host ·
   command`, besides where it came from.
6. **"New host…" is "New connection…"** on the screen; the file keeps
   `[hosts."name"]`.

Same window on Linux and Windows, so both get it.

**Built (2026-11-14).** `Recent` (pure: the two kinds, the file's lines,
`added`, `forgotten`) and `RecentFile` (the file, `recent.txt` in
puritty's state folder beside `logs`, written whole and moved into
place; `recent.toml`, an array `[[connections]]`, since `docs/sftp.md`
FT33). The host list's rows are Quick connect, New connection, the recent
connections, then the saved hosts; a recent row's second line says it is
one ("a recent connection · Right saves it"), a quick one's value "by
quick connect". Enter connects as it was made; Delete forgets it (the
saved host stays); Right on a quick one saves it as a host named for its
address, its user, port and command kept, and opens the form, and on a
saved one opens that host's form. Remembered by the window a connection
becomes: `puritty ssh`, `--host`, `start = "host:NAME"` (`Main.recentOf`),
and the host list when it becomes the session; `[connections] recent`
(default 8, 0 for none). `Hosts.quick` takes a command after the first
space; the field shows its grayed example, `user@host:port command`,
until a key is typed, and the footer says it. A saved host's line says its
command after `user@host:port`.

**Checked:** app tests 180 (five new: the rows, Enter on each kind, Delete,
Right saving, the command parsed); settings gate 20 of 20; and run:
`puritty ssh` twice wrote `recent.txt` newest first, and `puritty hosts`
listed both above the saved hosts, its field grayed with the example.

A host's name, where it is from and where it goes are cut with "…" to
their columns: a saved host's command ran off the window's edge.
`docs/images/host-list.png`, the home page's picture of the built-in ssh
client, is the host list with made-up hosts.

**Found, not this work's:** `harness/hosts.py` fails three cases
(`menu-connects`, `double-click-host`, `settings-connects`) at the commit
before this work too: in each, one puritty starts another, which runs no
ssh. The gate is not in the unit gate; left to look into. *Fixed
2026-11-15:* the cases' positions were stale, not puritty: the menu had
gained New tab, Rename tab…, Tab color… and Reopen closed tab, so six Downs
chose "Reopen closed tab" where "Connect to bastion" is now the eighth
item; and the host list's local shell (SG15) is its third row, so the two
settings cases opened a shell where they meant the first host. With the
cases moved, 13 of 13 pass.


## SG15 · The local shell in the host list (2026-11-14)

Gilbert, on Windows, where puritty opens on the host list: nothing in it
said how to open a session on this computer instead, which puritty calls
the **local shell** (`puritty shell`, `start = "shell"`). The list's third
fixed row is now "Local shell", "A shell on this computer, not over ssh",
"this computer"; Enter or a click opens it, in the host list's own window
(`SettingsProgram.LocalShell`, which `Main.becomeSession` begins as it
begins a host's) or, from the settings window of a terminal, in a window of
its own (`puritty shell`). The hosts are a row lower. The terminal's menu
says "New local window" where it said "New window".

The quick connect and new connection fields now take Home, End and Delete,
which they had not (Gilbert).

**Checked:** app tests 183 (the local shell's Enter, and Right and Delete
doing nothing on it; the host tests a row lower); the settings gate 20 of
20 and the hosts gate's `host-list`, a row lower; and run: `puritty hosts`,
Down, Down, Enter became a shell, which ran what was typed.

## SG16 · The settings window's page, kept while puritty runs (2026-11-14)

Gilbert: having set the bell on the Sound page and closed the settings
window, Ctrl+, opened it again on the first page; it should open where it
was, during the same session, not at a new start. Asked whether "the
session" is one puritty window's or all of them, he chose all of them: the
page is kept until the last puritty window closes.

**Why it needs a file.** The settings window is a process of its own each
time it opens (`puritty settings`), so nothing of it outlives its close,
and puritty's windows are separate processes too.

**What is built:**

- **`SessionFile`**, in puritty's state folder: `open/ID`, an empty file
  for each puritty window running, named by its process's id, and
  `settings-page.txt`, the page's name (`Sound`, `Hosts`).
- **A window starting** (`Main.run`) lists `open/`, takes away the marks
  whose processes no longer run (a window that crashed), and, when no
  other window runs, forgets the page: a new session. Then it marks
  itself. **A window ending** (`Main.finish`) takes its mark away.
- **The settings window** opens on the kept page (`withPageNamed`), unless
  it is the start screen, which opens on the hosts as before, and keeps
  the page each time it moves to another (`SettingsProgram.input`).
- **Geng's `os` gains** `Process.currentId` and `Process.isRunning`
  (Linux: `getpid`, `kill(id, 0)` with EPERM counting as running;
  Windows: `GetCurrentProcessId`, `OpenProcess` and no exit code yet).

**Left:** an id is reused once its process has ended, so a mark left by a
crashed window whose id another program now has keeps the session: the
page is remembered one start too long. Nothing worse follows.

**Checked** under Xvfb with a state folder of its own: a window's mark
made (`open/4078341`); the settings window moved to Sound kept `Sound`;
another opened on the Sound page; a window killed by a signal (no
`finish`) left its mark, and the next window, finding no process with that
id, took it away and forgot the page.

## SG17 · "Connecting to" said once the window is opened (2026-11-14)

Gilbert, on Linux: a host connected from the settings window's Hosts page
worked, but the bottom of the settings window kept saying "Connecting to
nene" in blue, even after the session's window was closed.

**Why.** From the settings window a session runs in a puritty window of its
own, another process (`connect`), so the settings window never hears how
the connection goes: it said "Connecting to" before starting that window,
and nothing replaced it.

**What changed.** Once the window's process has started, the settings
window says what it knows: "Opened nene in a new window" (`message.opened`),
or for the local shell "Opened a local shell in a new window"
(`message.openedLocal`), each in Korean too; a window that cannot start
says why, as before (`message.notStarted`). The start screen, which
becomes the session itself, is not changed.

## SG18 · Plainer descriptions, examples in empty boxes (2026-11-14)

Gilbert's review of the settings window's wording, page by page:

- **Appearance.** The font's "More in the Fonts guide" now gives its
  address, gilramir.github.io/puritty/guide/fonts. The palette says
  what its 16 colors are (0 to 15, black to white, then the bright forms)
  and how to type them: hex colors separated by commas, from color 0;
  "as many as given" is gone. Cursor blink, in ms, says what the number
  is: how long a blinking cursor stays shown and then hidden, so 500 is one
  blink a second.
- **Text & language.** Fallback language says what it does (the language
  preferred when another font lends a glyph the font lacks) and that it
  matters most for Han characters. It is now a list to pick from, `ko`,
  `ja`, `zh-cn` and `zh-tw`, each named in the description, where it took
  any text before.
- **Keys.** Each description is a sentence of what the key does, and the
  common ending is "Leave it empty for no key." ("Empty: the program gets
  the key" before); the box's grayed example shows how a key is written.
  Where a key is not taken (one tab, the log off), it "goes to the program
  like any other key". Mark the diagnostic log is last, as the least used.
- **Clipboard.** Its one setting, whether programs may read the clipboard
  (OSC 52), is on the Advanced page, and the page is gone. A
  `settings-page.txt` naming it (SG16) is a name no page has, so the
  window opens as it does with none kept (`withPageNamed`).

**Examples in empty boxes.** A box whose form is not plain words shows an
example, grayed, from the moment it is opened until a key is typed, as
quick connect does (SG14): `#000000, #cd0000, #00cd00, …` for a palette,
`#1e1e1e` for a color, `Ctrl+Shift+T` for a key.

Each changed text is changed in Korean too (`Words.geng`).


## SG19 · Recent connections in the menu and the jump list (2026-11-15)

SG14's recent connections were offered only by the host list. Now:

- **The menu** (Ctrl and the right button; on Windows also the title bar's
  system menu) lists "Connect to …" for each recent connection, newest
  first, then the saved hosts not among them, so a saved host is there
  once. Chosen, one starts puritty as the host list does: `--host NAME`
  for a saved host, `ssh TEXT` for what quick connect was given
  (`Recent.arguments`). A window reads `recent.txt` as it starts and again
  when it gains the focus, so that another window's connection is offered
  too; the system menu is made again when they changed.
- **The taskbar's jump list** on Windows: a category, "Recent
  connections", of links to puritty itself with those arguments, each named
  as the menu names it (`Window.jumpList`, `ICustomDestinationList`; on X11
  it does nothing). It is made as every window starts, which is when a
  connection is made and remembered, and again when the host list
  remembers or forgets one. A link the user took off the list is not put
  back (Windows refuses a category that has one). Windows takes no list
  when it is set not to show recently opened items; the window's
  diagnostic log then says so with Windows' reason (`HRESULT 0x80070005`).
  A link's arguments are one command line, quoted as the C runtime splits
  it (`Recent.commandLine`, as `Os.Process` quotes a child's).

**Checked:** app tests 246 (two new: a recent's arguments and name, and
the command line's quoting, empty arguments, quotes and trailing
backslashes among them). On Linux under Xvfb, with `build-box` and a quick
connection recent and `build-box` and `other` saved, Ctrl and the right
button showed "Connect to build-box", "Connect to me@example.com tmux -CC
attach", then "Connect to other". On beelink1, puritty run from a folder of
its own with its state folder there too (Gilbert's own untouched), started
as a local shell: Windows wrote the jump list's file, which holds "Recent
connections", the titles, and the links' arguments `--host build-box` and
`ssh "me@example.com tmux -CC attach"` to that `puritty.exe`. Opened by a
right-click on its taskbar button, the list showed "Recent connections",
then build-box and the quick connection (its name cut by Windows), each with
puritty's icon, above Windows' own items. The probe, its folder and its
jump list's file were removed after.


## SG20 · Text boxes that behave, and a connection edited before it is made (2026-11-18)

Gilbert, connecting from the host list on Windows with a long quick
connect line, `HOST tmux -CC attach -t main`, which needed `tmux`'s full
path (the remote zsh puts it on `PATH` in a file a command's shell does
not read):

- **The box did not scroll.** It is drawn from its first character and
  cut at its right edge, so the caret ran off it and what was typed could
  not be seen.
- **Ctrl+V did nothing.** `quickKey` drops every key with Ctrl held, and
  no box reads the clipboard.
- **A recent connection could not be edited**, only connected to, so
  changing `tmux` to its full path meant typing the whole line again.

**Decided** (Gilbert, 2026-11-18, "I agree; go ahead"):

1. **Every text box** of the host list and the settings window (they
   share the drawing): the text scrolls to keep the caret in view, a faint
   `…` at an end that is cut; Ctrl+V, Shift+Insert and the paste mouse
   button paste, the lines of a paste joined by spaces; Ctrl+Left and
   Right move by a word, Ctrl+Backspace deletes one; Shift with the arrows,
   Home and End selects, Ctrl+A selects all, Ctrl+C and Ctrl+X copy and
   cut, and what is typed replaces a selection.
2. **F2 on a row** (a recent connection or a saved host) puts its
   connection line into quick connect, the caret at its end, and connects
   to nothing; Enter on a row still connects. A small pencil on the row
   chosen does the same with the mouse. → is not used for it: on a recent
   connection it already saves it as a host (SG14).
3. **Up in quick connect while it is empty** brings back the recent
   connections one at a time, newest first, as a shell's history does;
   Down goes back towards the newest, and from it into the list as now.
4. **Delete on a recent** forgets it, as SG14 built, so the wrong line can
   go once the right one has been used.

With it, a session whose program fails says so (`docs/ssh-client.md`
SC29): the line that was wrong is then seen, not only logged.

**Built.** `TextEdit` (new, pure) takes a box's keys and says what they
did: the text or the caret changed, a copy, a paste asked, or a key not
its own (Enter, Esc, Tab, Up, Down), which the box's own handling keeps.
A word's separators are blanks and `/ \ @ : . , ; =`, so Ctrl+Left stops
inside `user@host:/path`; Ctrl+Right goes to the next word's start, as
Windows' boxes do. `Typing` gains the selection's other end (`anchor`)
and `recall`, Up's place among the recents. The window asks the program
for a paste (`PasteAsked`: the clipboard, through `Window.paste`; the
middle button clicks the box under it, then pastes the primary
selection) and gets its text as `Pasted`, made one line (`oneLine`);
Ctrl+V or Shift+Insert where nothing is typed yet pastes into the search,
or into quick connect or a new host's name. A copy is `Copy` (`Window.select`).
`typingField` draws the selection and scrolls: the text from its start
until the caret would pass the right edge, then moved left to keep the
caret there, a dim `…` at an end that is cut. It holds for every typed
box (quick connect, a new host, a setting's value, a font), the search
field aside, which takes a paste but is not typed with a caret.

F2 on a host row, or the chosen row's pencil (`✎`, `OnEdit`), puts its
line in quick connect: a recent quick connection's own; a saved host's
`user@host:port` and command (`Hosts.spec`, now exposed); an alias of
~/.ssh/config's, its name. A saved host's other settings (key, jump host,
colors) are not in a quick line, and a connection made from it is a quick
one. The hints at the foot say F2 and Up (English and Korean), and the
user guide's host list says the keys.

**Measured**: six tests in the app suite (408, from 402): a word left and
a selection typed over; Ctrl+Backspace and Ctrl+Delete by words; Ctrl+V
and Shift+Insert asking a paste and its two lines joined; Ctrl+A with
Ctrl+C, and Ctrl+X; F2 on a recent and on a saved host, connecting to
nothing until Enter, and an edited line connected to; Up and Down through
two recents and back to empty. On Xvfb, `puritty hosts`: a 96-character
line scrolled to its end with the dots at the left, a selection drawn,
a real Ctrl+V of two lines set by xclip pasted as one, the pencil on the
chosen row, and F2 filling quick connect. Not yet seen on Windows.

## SG21 · PuTTY's saved sessions in the host list (2026-11-18, Dnene62)

The Windows product's third item (`feature-plan.md`, "The Windows
product"): bring in the hosts a PuTTY or MobaXterm user already has.
`~/.ssh/config`'s are listed already (V63). This section is PuTTY's;
MobaXterm's waits on a real MobaXterm (below).

**Where PuTTY keeps them**, read from its source (`vendor/putty`):

- **Windows**: a registry key a session under
  `HKCU\Software\SimonTatham\PuTTY\Sessions`
  (`windows/storage.c`). The key's name is the session's name
  %-escaped (`windows/utils/escape_registry_key.c`: space, `\ * ? %`,
  control characters, bytes past `~`, and a leading `.`) in the **ANSI
  code page**, so a Korean name is CP949 bytes, not UTF-8. A string is
  `REG_SZ`, a number `REG_DWORD`.
- **Linux**: a file a session in PuTTY's folder (`unix/storage.c`'s
  `make_filename`): `$PUTTYSESSIONS`, else `$PUTTYDIR/sessions`, else
  `$XDG_CONFIG_HOME/putty/sessions` when that folder exists, else
  `~/.putty/sessions`. The file's name is the session's escaped with an
  opt-in list (letters, digits, `+ - . @ _`), its lines `Key=Value`.
- **Every setting is written**, so a session is whole without "Default
  Settings" (`settings.c`'s save loop), which is itself a session of that
  reserved name.

**What a host takes** (`app/src/Putty.geng`):

| PuTTY | host |
|---|---|
| `HostName` (may be `user@host`) | `host`, and `user` when it has one |
| `UserName` | `user`, when `HostName` has none |
| `PortNumber` | `port`, unless 22 |
| `Protocol` | only `ssh` is listed (telnet, serial, raw, rlogin, supdup are not); a session with none is ssh, Default Settings' default |
| `RemoteCommand` | `command` |
| `ProxyMethod` 6 ("SSH to proxy and use port forwarding", 0.77 on), `ProxyHost`, `ProxyPort`, `ProxyUsername` | `jump`: the session's name when `ProxyHost` names one, as `proxy/sshproxy.c` tries first, else `user@host:port`. PuTTY's other proxies (SOCKS, HTTP, telnet, a local command, `ProxyMethod` 1 to 5, 7, 8) are not jump hosts and are not taken |
| `LineCodePage` | `charset`: "Use font encoding" with a Hangul font (`FontCharSet` 129) is `cp949`, since PuTTY on Windows refuses a multi-byte code page by name (`decode_codepage` answers −3); UTF-8 and the rest are left unset |
| `Colour0`, `Colour2`, `Colour6`–`Colour21` (`r,g,b`) | `foreground`, `background`, and the sixteen (each normal, then bold) as `palette`; each only where it differs from PuTTY's defaults, so a session that kept PuTTY's look takes puritty's |
| `Font`, `FontHeight` | `font` unless Courier New (Windows' default) or a `server:` font (Linux's); `points` unless 10 |
| `WinTitle` | `title` |
| `PublicKeyFile` | **not taken**: a `.ppk`, which neither OpenSSH nor the built-in client reads (`ssh-crypto` loads `openssh-key-v1` only). A PuTTY user's keys are usually in Pageant, which the built-in client uses (SC19) |

Port forwardings, X11 and agent forwarding, keepalives, terminal modes,
logging and the rest of PuTTY's 200-odd settings have no host field and
are not taken.

**Decided** (Dnene62, mine; for Gilbert's review): PuTTY's sessions are
**listed, not imported**. They join the host list after the settings'
own and `~/.ssh/config`'s, marked "from PuTTY", skipping a name either
already has; the list reads them each time it opens. Enter on one makes
it a host of the settings (`PutHost`) and connects; → makes it one and
opens its form; Delete says it is PuTTY's and changes nothing; F2 puts
its line in quick connect. A session it jumps through is made a host
with it, so the `jump` names a host. The other way, an "Import" that
copies every session once, would put sessions nobody uses into
`config.toml` and need a step and a dialog; listed, PuTTY's sessions
work at once, and only those used become puritty's. A user done with
PuTTY who wants them gone removes them in PuTTY (or deletes the
registry key); a setting to hide them can come if anyone asks.

**Built.** `Putty` (pure): `unescape`, `parseFile` (Linux's files),
`parseSessions` (Windows' text), `hosts`. Windows reads the registry in
C (`puritty_win32_puttySessions`, `packages/win32`'s new `Registry`
module): each key unescaped and read in the ANSI code page
(`MultiByteToWideChar` in the machine's code page, below), its values as `[name]` and `Key=Value`
lines in UTF-8, a control character in a name or value made a space.
`app/linux/src/PuttyStore.geng` and `app/windows/src/PuttyStore.geng`
read each platform's place; `SettingsProgram` reads them as the window
opens, beside `~/.ssh/config`; `SettingsWindow`'s rows gain `putty`, the
host a session becomes; `fromPutty` makes it and its jump chain hosts.
English and Korean words for "from PuTTY" and the two messages; the user
guide's Hosts section says what is taken.

**Measured**: twelve tests in the app suite (420, from 408): names
unescaped (a space, a dot, UTF-8, a `%` that is not an escape); the
registry's text; a host's address, user, port, command and title;
`UserName` and port 22; telnet, serial, an empty host and Default
Settings left out; a jump by a session's name, by `user@host:port`, and
a SOCKS proxy not taken; CP949 from "Use font encoding" and a Hangul
font; default and changed colors and font; the rows listed after the
hosts, without a name the settings have; Enter saving the session and its
jump host, then connecting; Delete; Right.

**On beelink1** (Windows 11, its ANSI code page 1252), six sessions
written to the registry as PuTTY writes them (`Default%20Settings`,
`prod%20web`, `Caf%E9`, `bastion`, `inner` through `bastion`, and
`router`, telnet) and `puritty.exe hosts` opened: five hosts listed after
`~/.ssh/config`'s two, "PuTTY의 세션", Default Settings and the telnet one
left out. The first build showed `Caf�`: Geng's manifest makes the
process's ANSI code page UTF-8 (`activeCodePage`, geng-lang
`runtime/windows/geng_sys.c`), so `CP_ACP` in puritty is not the code
page PuTTY wrote the name in. The name is now read in the machine's
(`Nls\CodePage\ACP` in the registry, else the system locale's), and
showed `Café`. The registry key and the probe's files were removed after.

**MobaXterm, not built.** Its sessions are lines of `[Bookmarks]` and
`[Bookmarks_N]` sections (`SubRep` the folder): `name=#109#0%host%port%user%…`,
`%`-separated groups after `#`. MobaXterm does not document the format;
third parties' readings agree on the first fields (type, host, port,
user) and give a key file and jump host further on, but disagree on
where, and on where the installed edition keeps the file (`MobaXterm.ini`
beside the program, under `%APPDATA%\MobaXterm`, or the registry). Not
built until it is read against what a real MobaXterm writes.


## SG22 · A row under the header takes none of its clicks (2026-11-23)

The code review's PS5. The list is drawn clipped to its box, under the
header with the search field and the "Modified only" switch, but each
row's hit boxes were pushed whole, and, drawn after the header, they came
first. On a page taller than the window, with the first row shown cut by
two lines or more (as Down to the last row leaves it), a click on the
search field or the switch was the row's, or its value's: the list jumped
and a switch nobody could see was flipped.

Now `Drawn` has `hitClip`, set to the list's box while the rows, the
suggestions and the choice list are drawn: `target` cuts each box to it,
and leaves out one that is all outside.

Test (the app's SettingsWindow suite): the middle of the search field and
of the switch, the list scrolled 0 to 6 lines. Before, scrolled 2, 3 and
6 lines, they landed on `OnRow 0`, `OnValue 0` and `OnRow 1`; now on the
field and the switch every time.


## SG23 · What is typed stays the setting's it was typed into (2026-11-23)

The code review's PS3. What was being typed held no setting: each key
asked `focused m`, the row with the focus, again. Under Modified only the
rows listed depend on the settings, which typing itself changes, and
Ctrl+M changed the list (row 0) without ending the typing, so the next
keys went into another setting's value: a font size of 25 written while
the cursor blink was being typed, and Esc then setting that other
setting to blink's old value. Ctrl+F and Ctrl+Z also dropped the typing
without the undo entry Enter makes, so what it wrote could not be
undone.

Now `Typing` keeps the key of the setting typed into, and `typedOn`
writes, reverts (Esc) and ends (Enter) through that setting whatever row
has the focus. Ctrl+Z, Ctrl+M and Ctrl+F end the typing as Enter does
(`endTyping`), its change undoable, before they act.

Test (the app's SettingsWindow suite): with Fira Code set, Font size
typed to 114, then Ctrl+M and Ctrl+Z. Before, the typing went on into
the row now first and Ctrl+Z undid nothing (`font.size = 114` alone);
now Ctrl+Z writes `font.size = 11` back.

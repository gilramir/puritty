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
place). The host list's rows are Quick connect, New connection, the recent
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
ssh. The gate is not in the unit gate; left to look into.


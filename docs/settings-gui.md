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
a fill, and glyph masks drawn in a colour (`pt_glyphs_draw`). Both are
enough for a modern flat look, so the platforms need no new drawing:

- **Text at a pixel**, in the *interface font* at a size and a colour:
  shaped by HarfBuzz and rasterised by FreeType as the terminal's text is,
  each code point the interface font lacks found by the same fallback
  (`pt_fallback_file`), so Hangul comes from the system's Korean font.
  The interface font is Segoe UI on Windows and the system's `sans-serif`
  on Linux (fontconfig's choice), loaded beside the terminal's.
- **A rounded rectangle** in a colour, filled: its middle by fills and its
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
lighter colour, and its value on the right: a **switch** for on and off,
a **number field** with steps, a **text field** with a caret, a **choice**
that drops a list, a **colour swatch** with its hex, and a reset button
when the value is not the default. The **font picker** is a field that
opens a list of the system's fonts, each name drawn in its own font where
the system has it, the monospaced ones first and marked, filtered as one
types, with a line of sample text. Keys work as they do today (Tab,
arrows, Enter, Escape, Ctrl+Z); the mouse finds what it is on by the
boxes.

## SG4 · Two languages

The window's own words and every setting's label and description come
from one table (`app/src/Words.geng`): English, with American spelling
(*color*, not *colour*, in what the window shows; the file's keys, such as
`[colours]`, are the file format's and do not change), and Korean. The
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
  fallback. The header is three lines tall, the search field centred in
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
- **Not yet in Korean.** A check's message (such as "not a whole number")
  comes from `SettingsWindow`, in English. The
  font list shows names in the interface font, with no mark for the
  monospaced fonts and no sample.

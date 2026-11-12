# The settings UI

A proposal for how puritty's settings are changed without editing
`config.toml`, drawn from `research/config-ui-survey.md` and from what
`geng-plan.md` §6 already decided (*Gilbert, 2026-11-04*):

- A user should not have to edit `config.toml`, and should never restart
  puritty for a change.
- Changes are seen at once in the running terminal.
- The file stays what is stored. `gren-toml` edits the document in place, so
  the UI and hand edits share one file.
- The form was left open: a view inside puritty's window, or a dialog
  outside it.

How it is built, and the hosts it will start ssh sessions from, is
[`settings.md`](settings.md) (2026-11-10).

The survey's models are VS Code's settings editor (search, a "modified"
marker, reset per setting, one schema for the UI and the file) and Windows
Terminal (a UI over a hand-editable file, inheritance from Defaults).

## 1. Its form: a separate window, drawn by puritty

*Gilbert, 2026-11-06: a separate window.* Settings open in their own
top-level window, beside the terminal, drawn with puritty's own renderer as
a grid of text cells, like a well-made full-screen text program, with the
mouse working too.

Why:

- **The terminal is the live preview.** A view inside the window would cover
  the terminal whose colors and font you're changing. Beside it, every
  change shows in the real terminal, with no separate preview to build.
- **No toolkit.** GTK or Qt would add a large dependency on RHEL8 and under
  ETX, where every library is pinned. Cells drawn by puritty cost nothing
  new and send few bytes over ETX.
- **Keyboard first, for free.** A cell grid is naturally keyboard-driven,
  which the survey (Zed, the Windows Terminal spec) counts as essential.
- **The same code on Windows** once the renderer runs there.

What it gives up: no native widgets. A color is a hex field with a swatch
and the 16-color palette beside it; a font is a filtered list from
fontconfig; a choice is a row of options. Those are enough for every setting
puritty has.

The alternative, a view inside the terminal window, was turned down because
it hides the preview.

### How it's opened

PuTTY's "Change Settings…" is in the window's system menu (the title-bar
icon, or Alt+Space). Windows lets a program add items to that menu, so the
Windows puritty can do the same. X11 does not: the window manager draws the
title bar and its menu, and a program can't add to them unless it draws its
own title bar (client-side decorations, as Ghostty does with GTK4), which
Linux users dislike and which suits ETX badly.

*Gilbert, 2026-11-06: Ctrl+Comma and Ctrl+right-click.* On Linux:

1. **Ctrl+Comma**, as in Windows Terminal, VS Code and Ghostty (which uses
   Ctrl+Shift+Comma to reload its config). Safe to take: in the usual key
   encoding a program can't tell Ctrl+Comma from a comma.
2. **Ctrl+right-click** opens a small menu with "Settings…", as xterm's
   Ctrl+click menus do. Plain right-click is not free: `paste_button =
   "right"` gives it to paste.
3. **A gear button in puritty's tab bar**, once phase 4 brings tabs, as in
   Windows Terminal (proposed).
4. **`puritty --settings`** from a shell (proposed).

On Windows, the system menu as well, as PuTTY does.

## 2. One schema drives everything

Today `app/src/Config.geng` describes each setting by hand: its key, its
bounds, its default, and a comment. The UI needs the same facts plus a label,
a description and search words. Writing them twice would drift, so the first
step is one table, with an entry per setting:

| Field | Example |
|---|---|
| key | `font.size` |
| type | integer, 4 to 200 |
| default | 11 |
| label | Font size |
| description | In points. |
| search words | text size, zoom, points |
| page | Appearance |
| applies | at once / to new windows only |

The decoder, the UI's rows, the search and the documented example at the top
of `Config.geng` all come from that table.

## 3. The window

```
┌ puritty settings ──────────────────────────────────────────────────────┐
│ Search: font_                                       [Modified only] [ ] │
├──────────────────┬──────────────────────────────────────────────────────┤
│ Appearance    (2)│ Appearance                                           │
│ Window           │                                                      │
│ Text & lang.  (1)│  Font                                                │
│ Mouse & selection│ ● Family        Noto Sans Mono         [list]    ⟲   │
│ Clipboard        │     The font, as fontconfig names it.                │
│ Program          │ ● Size          13                       pt      ⟲   │
│ Sound            │     In points.                           default: 11 │
│ Advanced     (1) │                                                      │
│                  │                                                      │
│                  │  Colors                                             │
│                  │   Foreground    #c5c8c6  ███                         │
│                  │   ...                                                │
├──────────────────┴──────────────────────────────────────────────────────┤
│ Undo  ·  Open config.toml  ·  ~/.config/puritty/config.toml            │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Search** at the top filters every page at once. It matches labels,
  descriptions, search words and TOML keys (`font.size`), so both newcomers
  and hand-editors find things. The category list shows how many matches each
  page has, and hides pages with none.
- **Categories on the left, one scrolling page each on the right**, with
  section headings. No tabs inside tabs (PuTTY, SecureCRT, MobaXterm are the
  survey's warnings).
- **Every row is the same:** label, control, a one-line description, a
  marker (●) when it differs from the default, and a reset button (⟲) that
  appears only then. The TOML key shows when a row has focus.
- **Modified only** lists just the settings you've changed, the quickest
  answer to "what did I change?".
- **Settings that only apply to new windows** (the program to run, the
  starting size) say so on their row.

The pages, for today's settings:

| Page | Settings |
|---|---|
| Appearance | font family, size; colors, bold-is-bright, palette; cursor blink |
| Window | columns, rows, title |
| Text & language | font language (for fallback fonts), remote charset |
| Mouse & selection | paste button, word boundaries |
| Clipboard | whether programs may read the clipboard (OSC 52) |
| Program | the command to run |
| Sound | key sounds (new, `feature-plan.md` §3) |
| Advanced | frame interval, sync timeout, glyph cache, scrollback |

Later: **Keyboard** (key bindings) and, with the Windows product, **Hosts**.

## 4. Changes apply at once, with Undo

*Gilbert, 2026-11-06: apply at once.* The survey says to pick one model,
apply at once or Save/Discard; apply at once fits "seen at once" and the
live preview. Each change:

1. applies to every running terminal window right away (config reload);
2. is written to `config.toml` once you leave the field, or half a second
   after you stop typing in it;
3. can be undone with **Undo** (Ctrl+Z), one change at a time.

## 5. Saving to `config.toml`

`gren-toml`'s `Toml.Edit` already does the hard part: its round trip is exact
for every valid file in the TOML test suite, and edits keep comments and
blank lines. The rules on top:

- **Change only the keys the user touched.** Never regenerate the file.
- **Write only what differs from the default.** Resetting a setting removes
  its key (the section too, if it's left empty), keeping the file short.
- **Back up before writing:** `config.toml.bak`, the version before this
  session's first write. A reset never touches the backup.
- **Pick up hand edits.** puritty watches the file. An outside edit reloads
  the window; if the window also has an unwritten change, it shows both and
  asks which to keep.
- **A file that doesn't parse** shows the line and the error, and the window
  opens read-only until the file is fixed. puritty never resets it to
  defaults.
- **A test** loads a commented sample config, saves it unchanged, and checks
  the bytes are identical; and another sets then resets a key and checks the
  file returns to what it was.

### Unknown keys: reported, not fatal

Today a key puritty doesn't know makes the whole file an error, so that a
misspelling is never silently ignored, and puritty exits with a message. The
survey says a settings UI must keep keys it doesn't recognize. *Gilbert,
2026-11-06: report them, and start anyway.* The strictness stays, the exit
goes:

- Unknown keys are reported, by name and line, with a suggestion when one is
  close (`font.sise` → did you mean `font.size`?).
- puritty starts with the settings it does know.
- The settings window shows the unknown keys in an **"Not recognized in your
  file"** section, each with a remove button, and never drops them on save.
- A known key with a bad value (`font.size = 2`, below its bound) is reported
  the same way and its default is used, so a typo in one setting never costs
  the rest.

*Gilbert, 2026-11-06:* the report goes to stderr, as now, and also as a
one-line notice in the terminal window the first time it opens, since a
puritty started from a desktop launcher has no stderr anyone sees.

## 6. Inheritance, later

With one flat config there is nothing to inherit yet. Hosts and profiles come
with the Windows product, in three layers: **Defaults → group → host**. A
field you haven't overridden shows the value it inherits in gray with where
it comes from ("from Defaults", "from group *prod*"); typing in it makes an
override, and reset removes it. The row design above already has room for
that line, so nothing needs to change when it arrives.

## 7. Questions for Gilbert

Answered 2026-11-06: a separate window (§1), opened with Ctrl+Comma or a
Ctrl+right-click menu (§1), apply at once (§4), unknown keys reported and not
fatal, on stderr and as a notice in the terminal (§5).

None open.

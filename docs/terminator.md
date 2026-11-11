# Terminator: what it does, for tabs and splits (2026-11-11)

*Gilbert, 2026-11-11:* a colleague likes Terminator for its tab management,
which puritty does not have; find out what it can do.

Read from its source, `gnome-terminator/terminator` at 9f2d0b6 (2026-09-07,
after v2.1.6), cloned into `vendor/terminator`: the manual
(`doc/terminator.adoc`), the config reference (`doc/terminator_config.adoc`),
the defaults (`terminatorlib/config.py`) and the tab code
(`terminatorlib/notebook.py`). Not run here.

Terminator is a Python GTK 3 program around VTE, GNOME Terminal's widget:
"multiple GNOME terminals in one window", for people who keep many
terminals side by side without a tiling window manager. It draws nothing
itself; its value is arranging terminals.

## TA1 · What it does

**Tabs** (a GTK notebook; `notebook.py`, config "Tab Behavior"):

| | Terminator |
|---|---|
| New tab | Ctrl+Shift+T; at the end, or after the current one (`new_tab_after_current_tab`, off) |
| Switch | Ctrl+PgUp, Ctrl+PgDn; the mouse wheel over the tab bar; `switch_to_tab_1`…`10` have no default keys |
| Move a tab | Ctrl+Shift+PgUp, Ctrl+Shift+PgDn; or drag it along the bar (every tab is reorderable) |
| Out into its own window | drag it off the bar (`detachable_tabs`, on), or Ctrl+Shift+D |
| Rename | double-click the label, or Ctrl+Alt+A; empty goes back to the terminal's own title |
| Close | the × on each tab (`close_button_on_tab`, on), a middle click on the tab, Ctrl+Shift+W in its last terminal |
| Where the bar is | `tab_position`: top, bottom, left, right, or hidden |
| Many tabs | `scroll_tabbar`: tabs as wide as their text, with scroll arrows when they overflow; otherwise they share the width |

**Splits within a tab** (`paned.py`): Ctrl+Shift+O and Ctrl+Shift+E split
the terminal across or down (`split_auto` by the terminal's shape); the
dividers drag, and Ctrl+Shift+arrows move them; Super+R rotates the
arrangement; Alt+arrows go to the terminal in that direction,
Ctrl+Tab / Ctrl+Shift+Tab to the next and previous; Ctrl+Shift+X shows one
terminal alone and back (Ctrl+Shift+Z scaled up); a terminal can be dragged
by its title bar into another place, another tab or another window. Each
terminal has its own title bar (renameable, Ctrl+Alt+X), and inactive
terminals can be dimmed (`inactive_color_offset`).

**Typing into many at once** ("broadcasting"): terminals are put in named
groups (Super+T groups a tab's, Super+G all); Alt+A sends keys to all,
Alt+G to the group, Alt+O stops. The title bar turns red on the terminal
typed into and blue on those receiving.

**Layouts:** an arrangement of windows, tabs and splits, each terminal with
its profile, command and directory, saved by name in the config's
`[layouts]` (`Window`, `Notebook`, `HPaned`, `VPaned`, `Terminal` objects);
Alt+L opens a launcher, `terminator -l NAME` starts one, and a plugin saves
the last session's arrangement.

**Also:** profiles per terminal (Ctrl+Shift+arrow keys cycle them),
scrollback search, `--new-tab` into a running Terminator over DBus, and
plugins: activity and silence watches with desktop notifications, a
custom-commands menu, logging a terminal to a file, URL handlers.

## TA2 · Against puritty

puritty, without tmux, is **one terminal a window**: no tabs, no splits.
Under `tmux -CC` it has tmux's windows as tabs and tmux's panes as splits
(TM18 to TM32), so the arrangement lives on the server and survives a
dropped connection, which Terminator's does not.

| Terminator | puritty without tmux | puritty under tmux -CC |
|---|---|---|
| Tabs: new, switch, keys | none | Ctrl+Shift+T, Ctrl+PgUp/PgDn, a click, `+`; tmux's own keys (TM18, TM23) |
| Move a tab | none | none from the bar (tmux's `swap-window`, or its menu, TM27) |
| Detach a tab to a window | none | none |
| Rename a tab | none | tmux's `prefix ,`, asked by puritty (TM25) |
| Close button, middle-click close | none | none, on purpose: closing a tmux window ends what runs in it (TM22) |
| Bar position | n/a | top or bottom (`[tmux] tabs`) |
| Wheel over the bar | none | none |
| Splits, dividers dragged, keys | none | tmux's, dividers dragged (TM20), floating panes |
| Directional moves, zoom | none | tmux's (`prefix` arrows, `z`) |
| Broadcast typing | none | tmux's `synchronize-panes` |
| Saved layouts | none | tmux sessions persist; no saved layouts |
| Per-terminal title bar | none | `pane-border-status` titles (TM30) |
| Activity, silence | none | tmux's flags on the tabs (TM30) |

## TA3 · Proposal, for Gilbert

The gap is local tabs and splits, without tmux. In order of what a
colleague coming from Terminator meets first:

1. **Local tabs** (medium). Several terminals in one window, each its own
   `Vt.Term` and program or ssh session; the tab bar puritty already draws
   for tmux (TM18, TM22) reused, in both looks; Ctrl+Shift+T,
   Ctrl+PgUp/PgDn, Ctrl+Shift+PgUp/PgDn, Ctrl+Shift+W; rename by
   double-click; drag to reorder; a close button and a middle click; the
   wheel over the bar; `[tabs] position` top or bottom. On Windows this is
   also what the host list wants: one window holding several ssh sessions,
   as MobaXterm does.
2. **Local splits** (larger). Panes within a tab, split across and down,
   dividers dragged, Alt+arrows, zoom; the pane drawing and selection
   code written for tmux (`TmuxMode`) is most of the drawing.
3. **Broadcast typing** to a tab's panes (small, once 2 exists).
4. **Saved layouts** (medium), restoring tabs, splits, commands and
   directories, which `feature-plan.md` §2 already lists for the Windows
   product ("Reconnect, restoring tabs, layouts and titles").
5. **A tab to its own window** (larger: two windows in one process, which
   puritty's one-window design (`geng-plan.md` Q6) does not have).

*Leaning:* 1 now-ish, as the next feature after tmux, since it is most of
what "tab management" means and serves the Windows product; 2 and 3
together after it; 4 with reconnect; 5 not unless asked. Not started.

## TA4 · How the colleague uses it (2026-11-11)

*Gilbert, 2026-11-11, from the colleague's screen:* 10 to 20 tabs in one
window, each renamed to a name of one or two letters (`a`, `b`, `c`, `d`,
`dm`, `e`); some tabs run tmux (inside the tab, not as control mode) and
many do not; the tabs are cycled from the keyboard.

What it says for puritty's local tabs, beside the survey's ranking
(`docs/research/reports/Terminal tabs survey.md`):

- **Rename is used all the time**, not occasionally: one keystroke away
  from a short name (the survey's must-do 5), and a user's name kept over
  whatever the program sets as its title, since a tab named `dm` running
  tmux would otherwise show tmux's title.
- **Tabs as wide as their names**, not dividing the window's width: twenty
  one-letter tabs then fit on one bar with no overflow, and each is found
  by its letter at a glance. This argues for natural-width tabs by default
  (the survey's should-do 7), and against full-width tabs.
- **Keyboard cycling is the main way between tabs**: next and previous
  (Ctrl+PgUp/PgDn, Terminator's defaults) must work without the mouse and
  without the bar's help. With names like these, jumping to a tab by its
  name (type `d`, go to `d`) may be worth more than jumping by number;
  that is a question for him, not settled here.
- **tmux runs inside some tabs**, so the tab keys must not take tmux's
  (his prefix, and Ctrl+PgUp/PgDn if he binds them in tmux); every tab key
  rebindable and removable (must-do 1) covers it.
- Splits and broadcast were not seen in use; worth asking him whether he
  uses them, before they are ranked above restore or colours.

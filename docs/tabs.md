# Local tabs

Several sessions in one puritty window, each a local shell or an ssh
session, with a tab bar and keys to move between them. Gilbert, 2026-11-11:
"Let's do tabs first", after the survey (`docs/research/reports/Terminal
tabs survey.md`), Terminator's notes (`docs/terminator.md` TA1 to TA4) and
the checks round that prepared for it (`vt-core.md` §VC58, §VC59,
`tmux.md` TM33, TM34).

## TB1 · What the first version does, and the order

The survey's must-do list, ranked, and what Gilbert saw on his colleague's
screen (TA4: ten to twenty tabs, each renamed to a letter or two, cycled
from the keyboard, some running tmux), give the first version:

1. **Several sessions in one window** (step 1). `Ctrl+Shift+T` opens a tab:
   the shell, or in an ssh tab another session to the same host;
   `Ctrl+Shift+W` closes the active tab; `Ctrl+PgUp` and `Ctrl+PgDn` go to
   the tab before and after, `Ctrl+Shift+PgUp` and `Ctrl+Shift+PgDn` move
   it. A tab whose program ends closes; the window closes with its last
   tab. Each tab keeps its own terminal, scrollback, selection, search,
   character set and colours (an ssh host's own, `[hosts.NAME]`), and its
   ssh session or tmux control mode; background tabs keep reading, so
   nothing waits behind the one shown.
2. **The bar** (step 1). A row of the window below the terminal, shown
   while there are two tabs or more (`[tabs] bar = "auto"`, or
   `"always"`). Each tab as wide as its title, which is the host's name for
   an ssh tab, else the program's title, and the user's name once renamed.
   The active tab unmistakable in both looks: puritty's (the tmux tab bar's
   colours, TM22) and a plain one, square tabs as most terminals draw
   them (`[tabs] look = "plain"`, as `[tmux] look`).
   A click selects a tab; a middle click closes it (`[tabs]
   middle_click_closes`, on).
3. **Marks** (step 1). A background tab that rang its bell shows `!` and
   red, one that printed shows its activity, as tmux's tabs do (TM30).
4. **Rename** (step 2). One key away (`Ctrl+Shift+R`) and a double click on
   the tab: a name of one letter is the colleague's normal; it stays over
   whatever the program sets as its title, and an empty name gives the
   program's title back.
5. **Closing safely** (step 2). Asked only when it matters: an ssh tab whose
   connection is open, a local tab whose shell is running something in the
   foreground. Needs the foreground process of a pseudo terminal from
   `os` (Linux: `tcgetpgrp` on the pty against the shell's process group).
6. **New tab where I am** (step 2). A local tab opens in the active one's
   directory: OSC 7 when the shell says it, else the shell's own directory
   (Linux: `/proc/PID/cwd`), from `os`.
7. **Every tab key rebindable and removable** (step 3), the survey's first
   must-do: a `[keys]` table naming each action's chord, an empty one for
   none, so that Ctrl+PgUp and the others can go back to vim or tmux.

After the first version, in the survey's order: per-host tab colours,
restore on restart, reopening a closed tab, broadcast to several tabs,
dragging to reorder, the bar at the top, "move this tab to a new window"
as a reconnect. Tear-off and tab groups are not planned (the survey's
"must avoid").

## TB2 · How it is built

**One window, several sessions, the shown one in the model.** `Main.Model`
holds the window's state and the active session's (its terminal,
scrollback, selection, ssh screen, tmux state, character set, outbox). A
new field holds the other tabs, each its `Backend` and its session's
fields. Switching tabs swaps them: the active session's fields go into its
tab, the chosen tab's come out, and the window draws every cell. Feeding a
background tab swaps it in for the feed and out again, so every path that
reads a session (`feed`, the ssh notices, tmux control mode) is the one
code, not a second copy for background tabs. The loop races every tab's
`read` and, where its outbox is not empty, its `writable`, beside the
window's events and the timer, as it races the one backend now.

**The bar is a row the terminal gives up.** With the bar shown, each tab's
terminal is one row shorter than the window, and the bar is drawn in the
last row as overlay records after the cells, as the scrollbar and the
dialogs are (`Dialog`). Every tab's terminal and backend are told the
size, shown or not, so that a switch needs no resize.

**Keys under tmux control mode.** A tab running `tmux -CC` has tmux's
windows as its own tabs (TM18), and today `Ctrl+Shift+T` and
`Ctrl+PgUp/PgDn` act on them. *Leaning:* in such a tab they keep acting on
tmux's windows, and the local tabs are reached with the bar, or with the
same keys plus Alt; once `[keys]` exists, each is the user's to set.
To be settled with Gilbert.

**The bar's place.** At the bottom in the first version, as tmux's is by
default; at the top later (the frame's cells would move down a row, which
`Vt.View` does not do yet).

**Invariants from the first line** (`tmux.md` TM34): the tabs' list and the
index of the shown one are a record whose type says the index is inside
the list, and each tab's fields are one record, never parallel arrays.

## TB3 · Step 1, built (2026-11-11)

TB1's items 1 to 3 are built, in `app/src/Main.geng` (its TABS section)
and `vt`; the user's side is `docs/user/tabs.md`.

**How the model holds them.** `Model` keeps the shown session as before,
with `tab : TabInfo` (id, name, host, the marks) and `remote`, the
shown tab's `Backend`. The others are a `Tab` record each (the session's
fields and its `TabInfo`), in `tabs : Builder (Maybe Tab)`, a slot per tab
that is `Nothing` once the tab is shown or closed, and `order : Array Int`,
the tabs' ids in the bar's order, the shown one's among them. Not TB2's
"one record whose type says the index is inside": a `Tab` holds values
written in place (the terminal, the outbox), and an `Array` of them can be
neither sliced nor popped under ownership, so the slots are reached with
`Builder.swap` and `Builder.get` by an index found from the id, and every
lookup that misses (`slotOf`, `shownAt`) answers `Nothing` and the action
is dropped, never a crash. Each tab's fields are one record (`Tab`), as
TB2 asked.

**One code for every tab.** `atTab id work` swaps a hidden tab into the
model, runs `work` (the same `feed`, ssh notices and tmux code the shown
tab runs), and swaps it back; the loop races each hidden tab's `read`, and
its `writable` while its outbox holds bytes (`Behind`, `BehindWritable`).
A hidden tab's output sets its activity mark, and a bell its bell mark,
from a count of BELs the terminal now keeps (`Vt.Term.bells`, wrapping at
a million), compared before and after the feed.

**Size.** The window's rows (`windowRows`) are the terminal's plus the
bar's (`barRows`: one with two tabs or more, or with `[tabs] bar =
"always"`). `relayout` gives every tab, shown or not, the same columns and
rows, terminal and backend, so a switch draws without a resize. The bar is
drawn as overlay records after the cells, in the row below the terminal,
which `Vt.View` gives room for with `shadowIn cols rows windowRows` (the
size record names the window's rows, not the terminal's).

**Keys.** As TB1 lists them, with TB2's leaning taken: in a tab under
`tmux -CC`, Ctrl+Shift+T and Ctrl+PgUp/PgDn stay tmux's, and Ctrl+Alt+
PgUp/PgDn go to puritty's tab before and after, from any tab. With one
tab, Ctrl+PgUp/PgDn go to the program, as before tabs. Still open for
Gilbert until `[keys]` (step 3) makes them the user's.

**Settings.** `[tabs] bar` (`"auto"`, `"always"`), `[tabs] look`
(`"puritty"`, `"plain"`) and `[tabs] middle_click_closes` (on), on the
settings window's Window page, in English and Korean, each applying at
once (a change of `bar` lays every tab out again).

**Measured.** `bench/tabs/show.py` on Xvfb, with `/bin/sh` in each tab:
three tabs each wrote its own file; Ctrl+PgUp then typing wrote in the
second tab's shell; a background job's output and bell marked its tab red
with `!`; Ctrl+Shift+PgUp moved the shown tab; Ctrl+Shift+W closed one
and the next shown took the keys; `exit` closed its tab, and the last
`exit` ended puritty. The same with `--tabs 'bar = "always"\nlook =
"plain"'`: the bar shown over one tab from the start, square tabs. On
Windows (beelink1, `cmd.exe`, keys sent with `keybd_event`): Ctrl+Shift+T
opened a second `cmd.exe` on the bar, Ctrl+PgUp went back to the first
(each wrote its file), and two Ctrl+Shift+W ended puritty. Every gate the
change could move passes unchanged: view, pixels, replay, keys, mouse,
events, ime, settings, hosts, sshwindow, ssh, reload, the app's 104 unit
tests, perf within its record, and every tmux scenario.

**Not yet.** Steps 2 and 3 (rename, asking before closing, a new tab in
the same directory, `[keys]`), and everything after the first version.

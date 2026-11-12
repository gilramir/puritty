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
   character set and colors (an ssh host's own, `[hosts.NAME]`), and its
   ssh session or tmux control mode; background tabs keep reading, so
   nothing waits behind the one shown.
2. **The bar** (step 1). A row of the window below the terminal, shown
   while there are two tabs or more (`[tabs] bar = "auto"`, or
   `"always"`). Each tab as wide as its title, which is the host's name for
   an ssh tab, else the program's title, and the user's name once renamed.
   The active tab unmistakable in both looks: puritty's (the tmux tab bar's
   colors, TM22) and a plain one, square tabs as most terminals draw
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

After the first version, in the survey's order: per-host tab colors,
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
tab, Ctrl+PgUp/PgDn go to the program, as before tabs. Gilbert,
2026-11-11: "The keys are fine for now"; `[keys]` (step 3) makes them the
user's.

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

## TB4 · Step 2, built (2026-11-11)

TB1's items 4 to 6.

**Rename.** Ctrl+Shift+R, or a second click on the same tab within half a
second, opens a box over the screen (`Dialog`, as the ssh questions are)
holding the tab's name; Enter names it, Esc leaves it, and an empty name
gives the program's title back. The box takes the keys and what the IME
commits while it is up; a name is kept to 40 characters with control
characters dropped. The name is the tab's `TabInfo.name`, which the label
already put before the host's and the title (TB3), so a tab named `dm`
running tmux stays `dm`. Measured: Ctrl+Shift+R then `dm` and a double
click on another tab then `a` gave the bar `a`, `dm`, and the named tab's
shell took the next line.

**Closing safely.** Ctrl+Shift+W and a middle click (which shows the tab
first) ask only when it matters: an ssh tab whose session is up (started,
not ended, not failed), or a local tab with a program in front of its
shell, named in the question ("sleep is running in it."). An idle shell
closes at once, as the survey asks. When puritty cannot tell, it asks and
says why. Enter or Y closes; Esc or N keeps it. `[tabs]
ask_before_closing` (on) turns the asking off. What runs in front comes
from geng-lang's new `Os.Process.foreground` (`m3-os.md` §OS32,
Dnene45): the terminal's foreground process group against its session on
Linux, the newest running child of the shell on Windows; `Backend.busy`
asks it, and an ssh backend answers `Nothing`. Closing the window itself
does not ask yet.

**New tab where I am.** A new local tab starts in the shown tab's
directory: `Backend.directory`, from `Os.Process.directory` (§OS33,
Dnene46): `/proc/SID/cwd` on Linux, the process's current directory read
from it on Windows, so `cmd`'s `cd` counts and PowerShell's `Set-Location`
does not (a PowerShell tab's new tab opens where it started). When it
cannot be read, the program's own directory, as before. An ssh tab's new
tab is another session to the host, in the host's home. OSC 7 is not read:
the shell's own directory needs no shell setup, and OSC 7 would only add a
remote shell's directory, which a local new tab cannot use.

**Measured.** `bench/tabs/show.py`, extended: `cd /usr/share` then
Ctrl+Shift+T, and the new tab's `pwd` said `/usr/share`; `sleep 30` then
Ctrl+Shift+W asked "sleep is running in it.", Esc kept the tab and its
shell took the next line after Ctrl+C, and the idle shell then closed at
once. On Windows (beelink1, `cmd.exe`): `cd /d C:\Windows` then
Ctrl+Shift+T, and the new tab's `cd` said `C:\Windows`; `ping -n 30` then
Ctrl+Shift+W asked "PING.EXE is running in it.", Esc kept it, and after
Ctrl+C the idle tab closed at once, then the last.

**Seen, not done.** On Windows a `cmd.exe` tab's label is its title,
`C:\WINDOWS\system32\cmd.exe` cut to 24 characters; a name, or the
program's file name for a title that is a path, would read better.

## TB5 · puritty's own text in the interface font (2026-11-11)

*Gilbert, 2026-11-11:* the "Close this tab?" box was in the terminal's
monospace font; puritty's own messages should be in a proportional one, as
the settings window's are, to set them apart from the terminal's text, and
the tab names too.

Every one of them was already drawn with the settings window's text
records (`SettingsGui.text`, `Dialog`), which ask for the *interface
font*, but only the settings window told the renderer which font that is
(`Text.interfaceFont`, `settings-gui.md`); in the terminal's window the
renderer fell back to the terminal's font. The window now names it at its
start, before anything is drawn: Segoe UI on Windows, `sans-serif` on
Linux (`Platform.interfaceFont`). That moves all of puritty's own text over
the terminal at once: the ssh questions and the ssh screen's box (SC23),
the search bar, the rename box, the question before closing, tmux's
prompts in puritty's look (TM25), and the tab bar, whose tabs were already
measured in it (`Text.width`) and now fit their names exactly.

**Measured.** `bench/tabs/show.py`'s pictures on Xvfb, and a screenshot on
beelink1: the question and the tab names proportional, the terminal's text
monospace. No gate moved: pixels 46, view 345, sshwindow 9, reload 15,
hosts 13, ime 14, events 13 — none of them pictures puritty's own text in
the terminal's window, which is why the fallback went unseen.

## TB6 · Step 3, built: the `[keys]` table (2026-11-11)

TB1's item 7, the survey's first must-do: every key puritty takes for
itself is named in `[keys]`, and an empty entry gives the key back to the
program, so that a user whose tmux or vim wants Ctrl+PgUp, or the
colleague's tmux prefix, loses nothing to puritty.

| entry | default | |
|---|---|---|
| `new_tab` | Ctrl+Shift+T | tmux's new window in a tab under `tmux -CC` |
| `close_tab` | Ctrl+Shift+W | |
| `rename_tab` | Ctrl+Shift+R | |
| `color_tab` | none | TB9: the tab's menu has it |
| `next_tab`, `previous_tab` | Ctrl+PageDown, Ctrl+PageUp | tmux's windows under `tmux -CC`; the program's with one tab |
| `next_tab_always`, `previous_tab_always` | Ctrl+Alt+PageDown, Ctrl+Alt+PageUp | puritty's tabs from any tab |
| `move_tab_right`, `move_tab_left` | Ctrl+Shift+PageDown, Ctrl+Shift+PageUp | |
| `copy`, `paste` | Ctrl+Shift+C, Ctrl+Shift+V | |
| `paste_selection` | Shift+Insert | |
| `search` | Ctrl+Shift+F | |
| `settings` | Ctrl+Comma | |

Copy, paste, search and the settings are in it as well as the tabs' keys:
they take keys from programs the same way, and the table cost nothing more
for them.

**Names.** `Chord` (`app/src/Chord.geng`) reads `Ctrl`, `Shift`, `Alt`,
`Super` (or `Control`, `Win`) in any order and case, then a letter, a
digit, a named key (`PageUp`/`PgUp`, `Home`, `Insert`, `Tab`, `Comma`,
`F1` to `F24`, and the others in its table) or one punctuation character;
`Ctrl++` is Ctrl and the plus key. It writes them back one way
(`Ctrl+Alt+Shift+Super+Key`), which is what the settings window shows and
writes. A key matches with exactly its modifiers; a letter in either case;
punctuation by the key its unshifted character is, so `Ctrl+Shift+Comma`
holds where Shift makes the comma `<`; the keypad's Insert, PageUp and
PageDown are those keys. A name that is no key is reported with its line,
in English and Korean, and the default kept, as every setting's is. When
two entries name one key, the first in `tabAction`'s order has it.

**The settings window** has a Keys page, between Clipboard and Program,
each entry a text field (`Schema.KeyChord`) checked as it is typed. The
settings gate's way to the Hosts page passes one page more, and the unit
tests count the pages from `Schema.pages` rather than a number. A field
that takes the key pressed, as Windows Terminal's does, would be kinder
than typing a name; not built.

**Measured.** `bench/tabs/keys.py` on Xvfb with `new_tab = "Ctrl+Alt+N"`
and `next_tab = ""`: Ctrl+Shift+T and Ctrl+PageDown reached the shell
(`cat -v` read `^[[116;6u^[[6;5~`, the keys as the program's), Ctrl+Alt+N
opened a tab whose shell took the next line, and Ctrl+PageUp, still
bound, went back. With the defaults, `bench/tabs/show.py` and
`bench/search/show.py` (Ctrl+Shift+F, Ctrl+Shift+C) are unchanged; the
app's tests are 110 with `Chord`'s six; settings 20, keys, paste, select
and pointer pass.

## TB7 · Step 2's loose ends (2026-11-11)

**Closing the window asks too.** The close button, or the system closing
the window (`Window.Close`: X11's `WM_DELETE_WINDOW`, Windows' `WM_CLOSE`),
now asks as Ctrl+Shift+W does (TB4), over every tab, shown or not: each
busy tab is a line of the question, its label and what runs in it
("dm: sleep is running", "box: the ssh session to box is open"), six at
most and "and N more". With no tab busy, or `[tabs] ask_before_closing`
off, the window closes at once. `busyWhy` is the one test for a tab, shown
or hidden.

**A failed ssh tab's Esc closes the tab, not the window.** On the ssh
screen, Esc, or Enter after a failure, set the window's `closed`, which
with tabs ended every other tab too. It is `closeShown` now: that tab
goes, and the window only with its last. The loop goes on with the
backend of the tab then shown, not the one that went.

**A Windows program's path in a title is cut to its name.** `cmd.exe`
titles itself with its path (`C:\WINDOWS\system32\cmd.exe`, and
`... - ping -n 30 127.0.0.1` while a command runs), which the bar cut to
24 characters of the path. `shortTitle` puts the program's name for a
first part that is a path ending in `.exe`: `cmd`, `cmd - ping -n 30
127.0.`. Other titles are as they were.

**A regression from step 3, found here.** The hosts gate's two cases that
reach the Hosts page by its place in the settings window's sidebar
(`double-click-host`, `settings-connects`) failed since the Keys page
(TB6) moved it a row down; the gate was not run then. They now take eight
Downs and click at 321, and pass (13).

**Measured.** `bench/tabs/show.py`: with `sleep 30` in a tab not shown,
the window's close request (`bench/tabs/wmclose.py`, the client message a
window manager sends, since Xvfb has none and xdotool's `windowquit` asks
one) brought "Close the window? dm: sleep is running", Esc kept it; a
second puritty with an idle shell closed at once. On Windows (beelink1,
PowerShell's `CloseMainWindow`): "cmd - ping -n 30 127.0.: PING.EXE is
running", the bar reading `cmd - ping -n 30 127.0.` and `cmd`, and Esc
kept the window. sshwindow 9, hosts 13, events 13, the app's 110 tests.

## TB8 · An ssh tab's session ending, and dropping (2026-11-11)

**`exit` in an ssh tab ended the whole window.** `sshNoticed` set the
window's `closed` when a session ended as it should, which was right with
one session a window and wrong with tabs: `exit` typed into an ssh tab,
shown or not, ended puritty and every other tab, with status 0. Measured
on the code before this (`bench/tabs/ssh.py`): after `exit` in the second
of two ssh tabs, "puritty is ended, status 0", the first tab's shell gone.
Now the callers decide (`endsSession`): the shown tab goes by
`closeShown`, which ends the window only with its last tab, its ssh exit
status the window's as before; a tab not shown goes by `endTab`.

**A dropped session keeps its tab** (the survey's must-do 4, and its
must-avoid "closing an ssh tab the moment the connection drops"). A
session ends as it should only with its shell's exit status
(`Session.Exited`) before `Session.Ended`. One that ends without it
dropped: the network went, the server or its session process was killed.
It keeps its tab and its scrollback, with puritty's screen up ("The
session could not go on", Enter to close, R to connect again), as a
failure to connect did already. This holds with one tab too: a dropped
connection used to close the window; it now waits for Enter or R.

**The bar marks it.** A tab whose session failed or dropped shows `×`
before its name, in red (`0xFF6B6B` on a background tab, dark red on the
shown tab's amber), until it reconnects (`sessionLost`).

**Measured,** `bench/tabs/ssh.py` against a local sshd: two ssh tabs, `exit`
in the shown one closes it and the window stays; `exit` after `sleep 2` in
a tab not shown closes that one, and the shown tab's shell takes the next
line; a third tab's `kill -9 $PPID` drops its connection: the window stays,
the bar reads `box` and `× box`, and R reconnects it, its shell writing
the next file, the mark gone; `exit 5` in the last tab ends puritty with
status 5. sshwindow 9 and hosts 13 pass, unchanged.

## TB9 · Per-host tab colors (2026-11-12)

The survey's first item after the first version (its "should" list, item
1): "Per-host tab color from the host list, settable per tab at runtime",
as MobaXterm, Royal TS and Windows Terminal's `tabColor` do it, and as
GNOME Terminal, Konsole (since 2011) and Terminator users have asked, a
red tab for production their usual case. Gilbert, 2026-11-12: "Next on the
tabs survey's list is per-host tab colours"; and in American spelling
(`settings.md` ST31).

**A host's color.** `[hosts.NAME.colors] tab = "#rrggbb"`, beside the
host's `foreground` and `background`, and **Tab** on its page of the
settings window. Every tab of the host takes it: the window's first, and
each Ctrl+Shift+T opens there. A tab keeps its host's name
(`TabInfo.hostName`), from `Config.hostName`, which `Hosts.session` sets
for any host's window whichever client connects: the built-in client's
`config.remote` was not enough, since an OpenSSH host's window starts its
new tabs by running its `ssh` command again and knows no host otherwise.
The color is looked up in the settings in force each time the bar is
drawn, so a change in the settings window recolors the tabs at once.

**A tab's own.** `TabColor` is the host's, one picked, or none over the
host's. A box asks (`Dialog`, now with a row of swatches and `swatchAt`
for a click): eight colors on keys 1 to 8, 0 for none, H for the host's in
a host's tab, the one in use framed; a click on a swatch picks it, Esc or
a press elsewhere leaves. It is reached three ways:

- the menu has **Rename tab…** and **Tab color…** after New window, so
  Ctrl and the right button reach them anywhere, and the Windows system
  menu has them too (built for Windows, not yet tried there);
- the **right button on a tab** shows that tab and opens the menu over it;
- `[keys] color_tab`, **empty by default**: the survey's first must-do is
  keys not taken from programs, and Windows Terminal binds no key to its
  color picker either.

Restoring tabs (the next item) will carry the picked color with the name.

**How a colored tab is drawn.** Filled with its color; the tab shown at
full strength with a line of its text's color along its top, the others
three fifths the color over the bar's gray. Its text is dark on a light
color and white on a dark one (`Dialog.contrast`). Its marks move to a dot
at its end, since a red fill would hide the bell's red tab: red ringed in
white for the bell, the text's color for output; the `!` and `×` before
its name stay. A tab without a color is drawn as before, in both looks.

**The menu's order moved the hosts gate.** Its `menu-connects` case went
four items down to reach the first host; with the two tab items it goes
six (`harness/hosts.py`).

**Measured,** `bench/tabs/color.py` on Xvfb, reading the bar's fills from
the window's picture: a built-in-client host `prod` with `tab =
"#c62828"` against the local sshd, two tabs, both red (`#c62828` shown,
`#862727` not); the right button on the first tab, Tab color…, 4: green
`#2e7d32`, and its shell took the next line; the key (`Ctrl+Alt+K` set
for the run), 0: amber, as an uncolored tab shown; a bell in the red tab
not shown: its dot; H: red again; the file's color changed to `#6a1b9a`:
both tabs purple, without a restart; an OpenSSH host `lab` (a stand-in
`ssh` running a shell) with `#1565c0`: its two tabs blue. App tests 112,
with two for the host's `tab` (read; a value that is no color reported and
left out).

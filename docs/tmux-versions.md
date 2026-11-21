# tmux versions: what each answers, a survey before the design

Gilbert, 2026-11-14, after TM71 (the cursor hidden under `tmux -CC` on his
gmktec7's tmux 3.4, where the tests had only 3.8 and 3.6a): survey the
tmux versions puritty meets, dump everything found about each into text
files kept in git, as well as folding what is learned into the code, and
build tmux's releases from source to fill in the versions no distribution
ships. Section numbers are TV*n*. Nothing in puritty is changed by it yet.

---

## TV1 · Which tmux each distribution ships

Measured 2026-11-14 by installing `tmux` in each distribution's container
image:

| distribution | package | tmux -V |
|---|---|---|
| RHEL8 (AlmaLinux 8) | tmux-2.7-3.el8 | 2.7 |
| RHEL9 (AlmaLinux 9) | tmux-3.2a-5.el9 | 3.2a |
| Ubuntu 22.04 | 3.2a-4ubuntu0.3 | 3.2a |
| Debian 12 | 3.3a-3 | 3.3a |
| RHEL10 (AlmaLinux 10) | tmux-3.3a-13.20230918gitb202a2f.el10 | `next-3.4`: a git snapshot between 3.3a and 3.4 |
| Ubuntu 24.04, Linux Mint 22 | 3.4-1ubuntu0.2 (gmktec7: 0.1) | 3.4 |
| Debian 13 | 3.5a-3 | 3.5a |
| Fedora 43 | tmux-3.8-3.fc43 | 3.8 |

So puritty's own targets (`docs/releasing.md` RL3) meet everything from 2.7
to 3.5a. The tests until now had 3.8 and 3.6a.

## TV2 · The dumps

`corpus/tmux/` holds one folder per tmux: every release from 2.7 to 3.8
built from its tarball (25: `2.7` … `3.8`, the lettered ones too), and
each distribution's own package (`almalinux-8` … `fedora-43`). Each folder:

| file | what |
|---|---|
| `about.txt` | `tmux -V` and where it came from |
| `commands.txt` | `list-commands`: every command's usage, its flags |
| `keys.txt` | `list-keys` with no configuration |
| `options-server.txt`, `-session`, `-window`, `-pane` | `show-options -s`, `-g`, `-gw`, `-gp`: the defaults |
| `formats.txt` | each of 291 format variables (tmux 3.8's manual's, and those puritty asks) as `display-message -p` gives it in one fixed state; empty where a tmux has no such variable |
| `formats-all.txt` | `display-message -a`: the variables of the context it is run in (from 2.9); a buffer's, copy mode's or a hook's are not among them |
| `variables.txt` | every format variable the tmux knows, read from its release's source by `variables.py` (`docs/tmux-checks.md` TK8) |
| `control.txt` | a control-mode session: 27 commands (resize, flags, a subscription, splits, a program setting modes and a title, windows, copy mode, options, buffers, sessions, detach) and every line tmux wrote after each |
| `answers.txt` | puritty's own questions in the test states, as `app/tests/record-tmux.py` asks them |
| `lines.txt` | 33 lines of several commands (some failing, some refused, some running others) and every line tmux wrote after each, by `app/tests/dump-lines.py` (`docs/tmux-checks.md` TK10) |

**Made by** `app/tests/dump-tmux.py` (one tmux; `lines.txt` by
`dump-lines.py`), run in a container by
`app/tests/tmux-versions/releases.sh` (the releases, built on Debian 12;
tarballs and builds in `~/.cache/puritty/tmux`, each tarball's sha256 in
`sources.tsv`) and `distros.sh` (each distribution's package). What
differs from run to run is written by name: the host, times, pids, ttys,
the socket, the user's directories, a pane's `pane_output_generation`;
a window that would be renamed by its program is named, since when tmux
looks differs. Two runs of one tmux give the same files; `diff -r` between
two folders is what changed. 33 folders, 3.7 MB on disk.

## TV3 · What changes from release to release

Lines that differ between consecutive releases' files (the 2 to 6 that
change at every step are the version itself):

| step | commands | keys | options | formats | control | answers |
|---|---|---|---|---|---|---|
| 2.7→2.8 | 2 | 0 | 13 | 2 | 0 | 28 |
| 2.8→2.9 | 17 | 7 | 10 | 10 | 89 | 6 |
| 2.9→2.9a | 0 | 0 | 0 | 2 | 85 | 4 |
| 2.9a→3.0 | 31 | 473 | 39 | 16 | 13 | 18 |
| 3.0a→3.1 | 34 | 484 | 7 | 28 | 0 | 12 |
| 3.1c→3.2 | 70 | 52 | 34 | 44 | 9 | 18 |
| 3.2→3.2a | 0 | 0 | 0 | 22 | 0 | 4 |
| 3.2a→3.3 | 21 | 118 | 20 | 30 | 0 | 810 |
| 3.3a→3.4 | 18 | 515 | 6 | 8 | 1 | 4 |
| 3.4→3.5 | 6 | 60 | 7 | 6 | 0 | 6 |
| 3.5a→3.6 | 44 | 529 | 38 | 22 | 0 | 6 |
| 3.6b→3.7 | 27 | 56 | 33 | 22 | 0 | 12 |
| 3.7c→3.8 | 53 | 131 | 94 | 30 | 19 | 22 |

The other steps (the lettered releases, 3.0→3.0a, 3.1→3.1a …) change only
the version, apart from 3.6→3.6a's two key bindings. In the control
protocol, what puritty meets:

- **Before 3.0** `refresh-client -C 80x24` is refused (`bad size
  argument`): 2.x takes `80,24`.
- **Before 3.2** `refresh-client -f` (client flags: `pause-after`, and
  3.8's `new-layouts`) does not exist (3.0 and 3.1 have `-F`), nor
  subscriptions (`-B`, `%subscription-changed`), nor `%exit` at detach.
- **3.3** stops padding `capture-pane`'s lines with spaces (the 810).
- **3.4** adds `%paste-buffer-changed`.
- **3.8** with `new-layouts` gives layouts as JSON; before, tmux's own
  layout string. `pane_private_modes` answers from 3.8 only (TM71).

## TV4 · What puritty asks, and since when

From each release's `commands.txt`, the first that has each command and
flag puritty sends that 2.7 lacks:

| first in | commands and flags |
|---|---|
| 2.9 | `display-message -a` |
| 3.0 | `send-keys -H` (every key typed), `display-menu`, `show-options -H`, `-p`, `set-option -p` |
| 3.1 | `list-keys -N -a -P` |
| 3.2 | `refresh-client -A -B -f`, `customize-mode`, `display-popup`, `list-buffers -f`, `list-panes -f`, `run-shell -C` |
| 3.4 | `send-keys -K`, `list-clients -f` |
| 3.7 | `list-keys -F` |

`TmuxMode` already answers some by version (`versionOf`: TM61's flags,
the menus 3.6a lacks); the rest it sends as they are.

## TV5 · puritty under `tmux -CC`, by version

puritty (the build with TM71) under Xvfb, `tmux -CC new` of each release
built here, a `sh` with `$ ` for its prompt; `echo OK` typed and Enter:

| tmux | prompt and cursor | typing |
|---|---|---|
| 2.7, 2.9a | shown | **nothing reaches the shell** |
| 3.0, 3.1c, 3.2a, 3.3a, 3.4, 3.5a, 3.6a, 3.7c, 3.8 | shown | `echo OK`, `OK` |

Below 3.0 every key is sent with `send-keys -H`, which 2.x does not have,
so tmux refuses each and the shell gets nothing; RHEL8's tmux is 2.7.
Menus, customize mode, popups and copy mode by version are not yet
measured.

## TV6 · tmux's own bugs met

- **3.2 and 3.2a end the server** on `display-message -p
  '#{buffer_created}'` when no buffer is in the context (`server exited
  unexpectedly`; 3.3 answers it empty). puritty asks `buffer_created`
  only inside `list-buffers -F`, which is safe with and without buffers
  (checked on the 3.2a build); it must never ask a `buffer_*` variable
  outside a buffer's context on 3.2. RHEL9 and Ubuntu 22.04 ship 3.2a.
- **2.9** ends the control client at `select-pane -t %0` after a split
  and a resize; 2.9a does not. No target ships 2.9.
- **3.7 ends the server** on `break-pane` with no name, as `prefix !`
  gives it (3.7a's CHANGES: "Fix crash in break-pane when no name is
  provided"); found by the puppet (`docs/tmux-checks.md` TK12.1), which
  leaves that step out on 3.7. No target ships 3.7.
- **3.3 and 3.3a end the server** on `kill-pane -t` with its argument
  missing: they take it as `kill-pane`, which kills the session's only
  pane (every other tmux refuses the line, `-t expects an argument`;
  `docs/tmux-checks.md` TK10). puritty always gives `-t` a pane. Debian
  12 ships 3.3a.

- **3.2 to 3.7c hang in customize mode** at a filter that leaves out any
  row (`f`, then `0`, `#{m:*-time*,#{option_name}}` or
  `#{==:#{option_name},history-limit}`): the server spins at 100% CPU and
  answers no client; 3.8 does not. Found by the survey's customize-filter
  scene on 3.2a and 3.4; measured on 3.2, 3.2a, 3.3, 3.3a, 3.4, 3.5a,
  3.6a and 3.7c. No issue on tmux's tracker names it, and 3.8's CHANGES
  does not either. puritty under `-CC` is not touched: it draws customize
  mode itself and filters by asking formats (TM62), and the `-CC` server
  stayed idle while the plain one spun. RHEL9 and Ubuntu 22.04 ship 3.2a,
  where anyone using tmux's own customize filter meets it.

- **3.2a sizes a detached session by the client that made it**:
  `new-session -d -x 100 -y 30` gives an 80x23 window (the command
  client's 80x24 less the status line), though `default-size` says
  100x30; 3.2 and 3.3 give 100x30. 3.2a passes the command's client to the
  first window's spawn (`cmd-new-session.c`, `sc.tc = c`), and
  `default_window_size` takes that client's size before `-x`/`-y`. Ubuntu
  22.04 patches it (`lp1976110-respect-sizing.diff`, "only use client for
  sizing when not detached", Launchpad 1976110), which is TV7's 80x24
  where the release makes 80x23; RHEL9's 3.2a does not. puritty starts
  `tmux -CC new` attached, so is not touched; the comparison harness's
  outer tmux, a detached session, is now resized to its size after it is
  made.

- **3.8 gives a closed pane's space to the next pane, not the previous**
  (2026-11-21, Gilbert's report: puritty on Windows over ssh, plain tmux
  and `-CC` alike). Split a window left and right, split the left again,
  close the new middle pane: in a 200-column window 2.7, 3.3a, 3.4, 3.6a
  and 3.7c leave 100 | 99, the split pane back to half; 3.8 leaves 50 |
  149, the right pane grown and the left at a quarter. Measured on each
  build, detached, with no configuration and no terminal, so it is tmux's
  own and puritty only draws what tmux lays out. 3.8 rewrote
  `layout_destroy_cell` for floating panes: its `layout_cell_get_neighbour`
  ("Prefers cells 'after'") takes the next sibling, where through 3.7c
  the space went to the previous one, or the next for the first. Known:
  tmux issue #5859, "Closing or floating a pane gives its space to the
  wrong neighbour" (2026-11-06); fixed by Michael Grant's PR #5860, applied
  2026-11-11 as commit `0a3b2a1a20`, "Prefer previous cell not next when
  tiling/floating", on master and in no release yet (3.8, 2026-09-09, is
  the latest). 3.8 built with that commit gives 100 | 99. Until a release
  has it, `select-layout even-horizontal` or `resize-pane -x 50%` puts
  the panes back. Fedora 43 ships 3.8.

The first six are fixed in later releases; the seventh is fixed on tmux's
master, not yet released. Nothing to report.

## TV7 · The distributions' packages against the releases

| package | against | lines that differ | why |
|---|---|---|---|
| almalinux-8 | 2.7 | 5 | the distribution's `sh` (bash) redrawing |
| almalinux-9 | 3.2a | 17 | bash's bracketed paste; `pane_current_command` `coreutils` |
| ubuntu-22.04 | 3.2a | 32 | the window 80×24 where the release makes 80×23: Ubuntu's patch for 3.2a's detached sizing (TV6) |
| debian-12 | 3.3a | 0 | |
| almalinux-10 | 3.3a | 577 | a git snapshot past 3.3a: commands, keys, options |
| ubuntu-24.04 | 3.4 | 0 | |
| debian-13 | 3.5a | 0 | |
| fedora-43 | 3.8 | 23 | bash; the window's command `sleep` |

So, but for RHEL10's snapshot and Ubuntu 22.04's size, a distribution's
tmux answers as its release does, and the releases stand for them.

## TV8 · Leanings, for Gilbert

1. **Know the version at attach and say what will not work.** puritty asks
   `#{version}` already. Below 3.0 under `tmux -CC` typing does nothing
   today, with no word why. Either keys are sent as 2.x takes them
   (`send-keys -l` for text, key names for the rest; `refresh-client -C
   W,H`), or puritty says in the tab that this tmux is too old for `-CC`
   and plain `tmux` works. RHEL8 is the target that has it.
2. **The tests answered as more tmuxes answer.** `RealTmux` from the dumps
   for one version of each step that changes what puritty asks: 3.0, 3.2a
   (RHEL9, Ubuntu 22.04), 3.4 (Mint), 3.6a, 3.8, and 2.7 if 1 keeps it.
3. **A minimum stated** in the tmux guide: the version below which `-CC`
   is not offered, from 1.
4. **The dumps kept current**: a new tmux release added by
   `releases.sh NEW`, and a diff against the last read for the control
   protocol and the formats puritty asks.

Questions: is `tmux -CC` on RHEL8's 2.7 wanted, or is plain tmux there
enough? And which versions should the tests hold to?

## TV9 · Built: puritty adapts to each tmux (2026-11-14)

Gilbert: `tmux -CC` on 2.7 is wanted, puritty adapting to each tmux's
protocol. Built as `docs/tmux.md` TM72: what a tmux takes is read from its
`list-commands` when it attaches, and every difference in TV4 that puritty
meets has its other form. TV5's table again, after it: on 2.7, 2.9a, 3.0,
3.1c, 3.2a, 3.3a, 3.4 and 3.8, typing, the prefix's split and new window,
and (2.7 to 2.9a) the status line, each working.

## TV10 · What each tmux answers differently, measured (2026-11-15)

TV8's second leaning: the tests' fake tmux (`app/tests/src/FakeTmux.geng`)
answered as 3.8, and as 3.6a where those two differ. `record-tmux.py` now
records 3.8, 3.6a, 3.4, 3.2a, 3.0 and 2.7 (the older from
`tmux-versions/releases.sh`'s builds), one of each step that changes what
puritty asks, and with each: what that tmux lacks of 3.8's variables and
options (from its dump, TK8), its options' values with no configuration as a
format gives them, and the window and pane menus it draws (`prefix <`,
`prefix >`, captured from a client of its own inside an outer tmux). The
fake answers as each, and every recorded answer to a question that
version's scenarios ask is held to the fake's (TM68); the app's tests that
drive puritty run on all six.

What the recordings and probes of every release from 2.7 to 3.8 showed,
each now in the fake (`FakeTmux.rulesOf`, `modifierSince`):

| what | how |
|---|---|
| `#{?name,a,b}` with a name tmux does not have, or an unset `@option` | **true on 2.7**; from 2.8 empty, so false. `#{?#{name},a,b}` is false on all |
| `capture-pane -J` | before 3.3 a line keeps the cells tmux gave it, cleared ones as spaces: a quarter of the width, then half, then all (`line 1` and 14 spaces at 80 columns) |
| `capture-pane -a` with no alternate screen | nothing before 3.2; one empty line from it |
| copy mode's cursor moving up | held to the line's last character from 3.7; before, it keeps its column |
| `#{copy_cursor_x}`, `#{selection_start_x}` … | from 3.1 (TK8) |
| the layout | JSON from 3.8; tmux's layout string before |
| modifiers | `T:`, `E:`, `q:` from 2.9; `m/r:`, `<:`, `>:`, `=/N/end:`, `P:` from 3.0; `t/p:` and `e\|op:` from 3.2; `!:` from 3.6 (on 3.3 to 3.5 `#{!:#{x}}` gives the text `!:`); before, `#{op:…}` is empty |
| `display-message` | fills strftime's fields in the message as written, before its variables: an option's `%H` comes through raw |
| `#{status}` | `1` on 2.7, `on` from 2.8 |

The menus each draws are puritty's on every version that has them:
3.0's own keys (`Swap Left  (l)`, `Swap Up          (u)`, `Zoom
(z)`); from 3.2 the swaps and Zoom without keys; 3.8's Float. 2.7 has no
menus, and `prefix <` there types nothing. TV5's "not yet measured" is so
answered for the menus; copy mode by version is held by the fake's
answers above and by the puppet's copy-mode steps on every release
(`tmux-checks.md` TK12.1). Customize mode on 3.4, side by side
(`bench/tmux/compare/survey.py --scenes scenes2`, 2026-11-15): opening it,
a session's and an option's rows, a value cycled and reset, an array item
added, the key tables, each row for row as tmux 3.4 draws them, the only
differences the harness's (its palette, and `capture-pane` leaving out a
row's cleared end); on 3.2a too, once the harness's outer tmux was sized
(TV6), with 3.2a's own option list (`status-justify` its `(M-y)` where 3.4
has `(M-z)`).
Popups before 3.8 are not shown under `-CC`, by design: puritty shows a
popup as a 3.8 floating pane, and says so on the status line ("display-popup
under tmux -CC needs tmux 3.8's floating panes"). *Gilbert, 2026-11-15:*
no popup of puritty's own (a hidden window drawn as a box) for tmux before
3.8; the message stays.

**Found and fixed** (`docs/tmux.md` TM76): puritty's tree rows tested
`#{?pane_marked,…}`, `#{?window_marked_flag,…}` and
`#{?pane_floating_flag,…}`, which 2.7 has none of, so on RHEL8's tmux every
pane would show `M`; and the status line's timer could ask 2.7 for
`#{T:…}` before it knew 2.7 has none (`tmux-checks.md` TK10.9).

**The tree by version** (`docs/tmux.md` TM77): before 3.2 its rows are
written `name flags (N panes)` and `command "title"`, keys `(0)  `; from
3.2 a marked row is reversed; a window's only pane is a row of its own
from 3.6; 3.7 writes a pane's flags as `pane_flags` and a floating pane in
italics. puritty asks each tmux for its own, and in tmux's look draws the
rows each real tmux draws (recorded with the menus).


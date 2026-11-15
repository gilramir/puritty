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

**Made by** `app/tests/dump-tmux.py` (one tmux), run in a container by
`app/tests/tmux-versions/releases.sh` (the releases, built on Debian 12;
tarballs and builds in `~/.cache/puritty/tmux`, each tarball's sha256 in
`sources.tsv`) and `distros.sh` (each distribution's package). What
differs from run to run is written by name: the host, times, pids, ttys,
the socket, the user's directories, a pane's `pane_output_generation`;
a window that would be renamed by its program is named, since when tmux
looks differs. Two runs of one tmux give the same files; `diff -r` between
two folders is what changed. 33 folders, 3.3 MB.

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

Both are fixed in later releases; nothing to report.

## TV7 · The distributions' packages against the releases

| package | against | lines that differ | why |
|---|---|---|---|
| almalinux-8 | 2.7 | 5 | the distribution's `sh` (bash) redrawing |
| almalinux-9 | 3.2a | 17 | bash's bracketed paste; `pane_current_command` `coreutils` |
| ubuntu-22.04 | 3.2a | 32 | **the window 80×24 where the release makes 80×23**: not yet explained |
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


# Tabs in the Linux desktop terminals (Terminator, GNOME Terminal, GNOME Console, Ptyxis, Konsole, Tilix, xfce4-terminal, Guake, Yakuake, Tilda)

Researched 2026-11-11. Method: feature facts read from each project's **current source** (shallow clones taken 2026-11-11, commit and date given per entry: settings schemas and default key bindings), plus project docs; complaints from the issue trackers' own APIs (GitHub search sorted by reactions; GNOME GitLab and xfce GitLab sorted by popularity/upvotes; KDE Bugzilla REST), so the counts below are as of today. Reddit/HN were searched but the search tools surfaced little first-hand Reddit material; sentiment leans on trackers, forums and reviews and says so.

Source clones (not committed anywhere; paths are the agent's scratchpad): gnome-terminal `e633d6e` (2026-11-09), GNOME Console `5bd9698` (2026-11-01), Ptyxis `fb9b536` (2026-11-11), xfce4-terminal `75cb485` (2026-11-11), Guake `0911ddf` (2026-08-19), Tilda `b6a2ca2` (2026-01-10), Yakuake `21c6210` (2026-11-09). Terminator: `/home/gram/prj/puritty/vendor/terminator` at 9f2d0b6 and `/home/gram/prj/puritty/docs/terminator.md`.

## Tab features, per terminal

### Takeaway
A de-facto common core has emerged across almost all of them: **Ctrl+Shift+T new, Ctrl+Shift+W close, Ctrl+PgUp/PgDn switch, Ctrl+Shift+PgUp/PgDn move, Alt+1…9/0 jump, drag to reorder, drag out to detach, new tab inherits the current directory, confirm close when a process runs.** The differences are in title rules (user title vs program title), splits/broadcast (Terminator, Tilix, Konsole, Yakuake, Guake), session restore (Ptyxis, Guake, Konsole layouts; GNOME Terminal still not), and overflow (GNOME's libadwaita "tab overview" grid vs scroll arrows). Konsole and Yakuake are the outliers on keys (Shift+Left/Right switch).

### Cited Findings

**Terminator** (GTK3/VTE, v2.1.6 2026-09-05)
- New Ctrl+Shift+T, at end or after current (`new_tab_after_current_tab`, off); switch Ctrl+PgUp/PgDn and mouse wheel over the bar; `switch_to_tab_1…10` have **no default keys**; move Ctrl+Shift+PgUp/PgDn or drag; detach by dragging off the bar (`detachable_tabs`, on) or Ctrl+Shift+D; rename by double-click or Ctrl+Alt+A, empty reverts to the program's title; close via × (`close_button_on_tab`, on), middle click, Ctrl+Shift+W; bar top/bottom/left/right/hidden; overflow: `scroll_tabbar` gives natural-width tabs with scroll arrows, otherwise tabs share the width — `/home/gram/prj/puritty/docs/terminator.md` (TA1), from `vendor/terminator/terminatorlib/notebook.py`, `config.py`
- Splits inside tabs (Ctrl+Shift+O/E), Alt+arrows navigation, zoom Ctrl+Shift+X, drag a terminal into another tab/window, per-terminal title bars; broadcast to all/group (Alt+A / Alt+G / Alt+O) with red/blue title bars; named layouts saved in config incl. profile, command, cwd per terminal; a plugin saves the last session; activity/silence watch plugins — `/home/gram/prj/puritty/docs/terminator.md` (TA1)
- Release dates: v2.1.6 2026-09-05, v2.1.5 2025-05-22, v2.1.4 2024-05-30 — GitHub releases API, `gh api repos/gnome-terminator/terminator/releases`

**GNOME Terminal** (current main is a GTK4/libadwaita port, version string `3.97.1`, `vte-2.91-gtk4`, libadwaita ≥1.4 — `meson.build` in the clone; the port's release status in distros not verified)
- Defaults from `src/org.gnome.Terminal.gschema.xml`: `new-tab` Ctrl+Shift+T; `new-tab-position 'last'`; `new-terminal-mode 'window'` (new terminals open as windows unless changed to tab); `preserve-working-directory 'safe'`; `prev-tab`/`next-tab` Ctrl+PgUp/PgDn; `move-tab-left/right` Ctrl+Shift+PgUp/PgDn; `move-tab-start/end` disabled; `switch-to-tab-1…9` Alt+1…9, `-10` Alt+0, 11–35 and "last" bindable but disabled; `detach-tab` disabled by default; `show-tabs-overview` disabled (exists); `confirm-close true`; `tab-position 'top'`; `tab-policy 'automatic'` (bar hidden with one tab) — gnome-terminal clone e633d6e
- Tabs are now an `AdwTabView`; "Set _Title…" is back in the header menu and tab context menu (`win.set-title`, `notebook.notebook-set-title`) — `src/terminal-headermenu.ui:61`, `src/terminal-notebook.ui:67`
- **Middle-click close is deliberately blocked**: "Adwaita's tab bar closes tabs from middle-click, which is undesirable… we need to install a capturing event handler to claim the middle button click" — `src/terminal-window.cc:1938`, `:2246`. Matches the 2019 request "Ability to close tabs by clicking on scroll wheel", closed 2019-02-04 with 11 comments — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/75
- No splits, no broadcast (none in schema; not a feature of the app).
- Session restore: **not implemented**; "Auto-restore last opened tabs during opening gnome-terminal" open since 2010-07-09 (12 notes, 3 upvotes) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/7019

**GNOME Console (kgx)** (GTK4/libadwaita)
- App-level accelerators: new window Ctrl+Shift+N, new tab Ctrl+Shift+T, close tab Ctrl+Shift+W, find Ctrl+Shift+F, tab overview ("show-tabs") Ctrl+Shift+O — `src/kgx-application.c:166-204`, Console clone 5bd9698
- Uses `AdwTabOverview` (thumbnail grid of tabs) — `src/kgx-window.ui:67`; tab overview landed in GNOME 44 ("top-level look at all your open tabs") — https://itsfoss.com/gnome-terminal-console/ (via search summary; also https://news.itsfoss.com/gnome-terminal-console)
- Only "restore-window-size" in settings; no session/tab restore found in source (`grep restore src/kgx-settings.c`) — Console clone
- Tab-move keys Ctrl+Shift+PgUp/PgDn were missing until fixed (issue opened 2022-11-28, 7 upvotes, 15 notes, closed 2023-08-04): "Other GTK apps with tabs (GNOME Terminal, Epiphany… BlackBox) allow moving the tab… Currently this is not supported in GNOME Console" — https://gitlab.gnome.org/GNOME/console/-/issues/237
- Ctrl+PgUp/PgDn switching was also an early gap (closed 2022-02-17, 4 upvotes) — https://gitlab.gnome.org/GNOME/console/-/issues/118
- "Tabs don't have titles" (closed 2021-11-26, 6 upvotes, 14 notes) — https://gitlab.gnome.org/GNOME/console/-/issues/89
- "Sudo mode colour should only affect the current tab" (closed 2022-05-01, 6 upvotes) — https://gitlab.gnome.org/GNOME/console/-/issues/139

**Ptyxis** (GTK4/libadwaita; default terminal in Fedora Workstation, RHEL and Ubuntu per its README)
- README: "Advanced Tab Management: Searchable tab overview with live previews and pinned tabs that persist their session context (profile, container, working directory) across application restarts"; "Visual indicators for `sudo` sessions, active SSH connections, and other foreground processes" — https://gitlab.gnome.org/chergert/ptyxis/-/raw/main/README.md
- Defaults from `src/org.gnome.Ptyxis.gschema.xml.in` (clone fb9b536): `new-tab-position 'last'` (or `next`); `tab-middle-click 'close'` (or `paste`, `nothing`); `restore-session true`; `restore-window-size true`; `prompt-on-close true`; `ignore-osc-title false`; `disable-dynamic-title false`; `exit-action 'close'` (or `restart`, `none`); `preserve-directory 'safe'` (or `never`, `always`); keys: new tab Ctrl+Shift+T, tab overview Ctrl+Shift+O, tab menu Alt+comma, previous/next Ctrl+PgUp/PgDn, move left/right Ctrl+Shift+PgUp/PgDn, close Ctrl+Shift+W, focus-tab-1…9 Alt+1…9, -10 Alt+0, **undo-close-tab Ctrl+Shift+Alt+T**; detach-tab, close-other-tabs, set-title, focus-tab-last exist but unbound
- Overview supports drag to reorder, pin to top, "Set title" via right-click (prepend a name to the process title or write a custom one), and a search button to find tabs — https://itsfoss.com/ptyxis-terminal-features/
- No splits, no broadcast (none in schema or README).

**Konsole** (KDE)
- Menu/defaults: New Tab Ctrl+Shift+T; Clone Tab (no key); Close Session Ctrl+Shift+W; Copy Input To → All Tabs in Current Window / Select Tabs… (Ctrl+Shift+.) / None (Ctrl+Shift+/); Configure Tab Settings… (Ctrl+Alt+S) sets "the name format, remote tab title format, and current tab color"; Split View Left/Right Ctrl+(, Top/Bottom Ctrl+); Expand/Shrink View Ctrl+Shift+] / [; toggle maximize view Ctrl+Shift+E; equalize Ctrl+Shift+\; Detach Current Tab Ctrl+Shift+L; Detach Current View Ctrl+Shift+H; Save/Load tab layout; Monitor for Activity Ctrl+Shift+A, Silence Ctrl+Shift+I, Prompt Ctrl+Shift+R, Process Finishing; Next/Previous Tab Shift+Right/Left; Move Tab Ctrl+Alt+Left/Right; Tab Bar/Splitters settings page for visibility, placement and behaviour — https://docs.kde.org/stable_kf6/en/konsole/konsole/commandreference.html
- 22.12: split views got headers with drag-and-drop and a maximize toggle, and the tab bar is shown only when needed by default — https://konsole.kde.org/changelog.html (via search summary)
- Saved tab layouts to .json and reopening them from the command line; layout-automation work blogged 2024–2025 — https://blogs.kde.org/2024/06/11/konsole-layout-automation-part-1/ ; https://blogs.kde.org/2025/04/02/konsole-layout-automation-part-2 ; https://planet.kde.org/akseli-lahtinen-aks-2025-05-18-my-changes-to-saving-konsole-tab-layouts
- Tab color derived from remote host name requested since 2011 (ASSIGNED) — https://bugs.kde.org/show_bug.cgi?id=278699

**Tilix** (GTK3/D)
- "Tabs or sidebar list current sessions"; "grouping of terminals can be saved and loaded from disk"; splits "horizontally or vertically"; "Input can be synchronized between terminals" — https://github.com/gnunn1/tilix (README)
- Its tabs are "sessions"; new sessions historically went to a sidebar rather than a tab bar — https://www.linuxuprising.com/2018/03/tilix-almost-perfect-tiling-gtk-3.html (via search summary); visible tabs were themselves a long request: "Can we please have tabs?" (2016, 36 comments, 8 👍, closed), "Add optional support for tabs" (2017, closed), "[Proposal] Drop Sidebar functionality in favor of tabs" (2019, 12 comments, closed) — https://github.com/gnunn1/tilix/issues/114 , /1047 , /1627
- Maintenance: README: "This project is looking for maintainers!… only very minimal maintenance is done, no new features will be implemented… pull-requests may be reviewed very slowly" — https://github.com/gnunn1/tilix ; last release 1.9.6 on 2023-11-08 (prior 1.9.5 2022-02-22), last push 2026-07-01, 458 open issues — `gh api repos/gnunn1/tilix` and `/releases`; original author sought a new maintainer in 2019 — https://www.omgubuntu.co.uk/2019/05/tilix-terminal-emulator-new-maintainer

**xfce4-terminal** (GTK3)
- Actions and defaults in `terminal/terminal-window.c` (clone 75cb485): Open Tab Ctrl+Shift+T; **Undo Close Tab Ctrl+Shift+D**; Detach Tab (menu, no key); Close Tab Ctrl+Shift+W; Close Other Tabs; Copy Input To All Tabs…; Set Title…; Set Title Color…; Previous/Next Tab Ctrl+PgUp/PgDn; Last Active Tab; Move Tab Left/Right Ctrl+Shift+PgUp/PgDn; Go to Tab 1…N (Alt+N per docs)
- Preferences (`terminal/terminal-preferences.c`): `tab-activity-color`, `tab-activity-timeout` (activity indicator), `misc-always-show-tabs`, `misc-confirm-close`, `misc-cycle-tabs`, `misc-tab-close-buttons`, `misc-tab-close-middle-click`, `misc-tab-position`, `misc-slim-tabs`, `misc-new-tab-adjacent`, `misc-bell-urgent`; title rules `title-mode` = replace / prepend / **append (default)** / hide, with `title-initial` — `terminal/terminal-preferences.c:1235`, `terminal-preferences.h:39-43`
- Alt+N switches tabs; to disable, blank the entries in `accels.scm`; has a built-in drop-down mode — https://docs.xfce.org/apps/xfce4-terminal/start
- New tabs inheriting cwd was fixed in 2021 (#121 closed 2021-05-20) — https://gitlab.xfce.org/apps/xfce4-terminal/-/issues/121

**Guake** (drop-down, GTK3/Python; 3.10.1 2025-10-20, previous 3.10 2023-05-12 — GitHub releases API)
- Defaults from `guake/data/org.guake.gschema.xml` (clone 0911ddf): `restore-tabs-startup true`, `restore-tabs-notify true`, `save-tabs-when-changed true`, `workspace-specific-tab-sets false`, `prompt-on-quit true`, `prompt-on-close-tab 0`, `tab-ontop false` (bar at bottom), `new-tab-after false`, `hide-tabs-if-one-tab false`, `fullscreen-hide-tabbar true`, `display-tab-activity false`, `use-vte-titles true`, `open-tab-cwd true`, `max-tab-name-length 100`, `tab-close-buttons false`; keys: new tab Ctrl+Shift+T, new tab in home Ctrl+Shift+H, new tab in cwd Super+T, close Ctrl+Shift+W, move Ctrl+Shift+PgUp/PgDn, prev/next Ctrl+PgUp/PgDn **and Ctrl+Shift+Tab/Ctrl+Tab**, switch to tab N **Ctrl+F1…F10**, last Ctrl+F12, rename Ctrl+Shift+R, split vertical Super+Shift+comma, horizontal Super+minus, close terminal Super+X
- Rename tabs manually or automatically, by UUID from the command line, or from a per-directory `.guake.yml` — https://guake.readthedocs.io/en/latest/user/features.html

**Yakuake** (drop-down, KDE, uses Konsole's KPart)
- Default keys from `app/mainwindow.cpp` (clone 21c6210): new session (tab) Ctrl+Shift+T, plus "new session two-horizontal / two-vertical / quad" (pre-split tabs, no key); close Ctrl+Shift+W; previous/next Shift+Left/Right; move Ctrl+Shift+Left/Right; rename Ctrl+Alt+S; previous/next terminal within tab Ctrl+Shift+Tab / Ctrl+Tab; split Ctrl+( / Ctrl+) / auto Ctrl+*; grow terminal Ctrl+Alt+arrows; close active terminal Ctrl+Shift+R; toggle prevent-closing and keyboard-input lock per session; monitor activity Ctrl+Shift+A, silence Ctrl+Shift+I; Alt+1…9 / Alt+0 jump
- Tab bar (`app/tabbar.cpp`): double-click renames inline, middle button handled on press, wheel cycles tabs, drag-move reordering; config has `ShowTabBar`, `DynamicTabTitles` — Yakuake clone

**Tilda** (drop-down, GTK3; 2.0.0 released 2024-02-16 after 1.5.0 in 2020 — GitHub releases API)
- `src/configsys.c` (clone b6a2ca2): add tab Ctrl+Shift+T, close Ctrl+Shift+W, prev/next Ctrl+PgUp/PgDn, move Ctrl+Shift+PgUp/PgDn; `tab_pos`, `expand_tabs` false, `show_single_tab` false, `insert_tab_after_current` false, `title_max_length 25`, `title_behaviour`, `inherit_working_dir true`, `confirm_close_tab true`, `show_title_tooltip`
- No rename-tab action found in source (only title length/behaviour settings) — `grep -i rename tilda/src` finds no tab-rename action; the request "Rename Tab Functionality?" is open since 2015-03-31 (20 comments, 6 👍) — https://github.com/lanoxx/tilda/issues/134

### Inferences
- The libadwaita terminals (GNOME Terminal's port, Console, Ptyxis) converge on: tab overview grid (Ctrl+Shift+O), Alt+N, Ctrl+(Shift+)PgUp/PgDn, and in Ptyxis undo-close-tab and session restore. xfce4-terminal and Ptyxis both have undo-close-tab — a cheap feature worth copying.
- The "user title vs program title" rule is handled best by modes rather than a single override: xfce4-terminal's replace/prepend/append/hide; Ptyxis's "prepend a name to the default process" title; Terminator's "empty reverts to program title".
- Middle-click on a tab is contested: closes in Terminator, Ptyxis (default, configurable to paste/nothing), xfce4-terminal (option); explicitly suppressed in GNOME Terminal.

### Gaps
- Exact overflow behaviour (shrink vs scroll vs menu) for Konsole, xfce4-terminal, Guake and Tilda with many tabs was not verified from source or docs.
- Whether GNOME Terminal's GTK4 port (3.97.x) has shipped in a stable distro release, and when "Set Title" returned to it, not verified.
- Konsole's tab-title format placeholders and middle-click/close-button options were not read from source.
- Konsole session restore relies on KDE session management; not verified beyond the bug below.

## What users praise about tab handling

### Takeaway
Praise clusters on (1) splits + broadcast inside tabs (Terminator, Tilix), (2) restoring tabs across restarts (Guake, Ptyxis pinned tabs), (3) Ptyxis's searchable overview with pin/rename, and (4) Konsole's breadth (layouts, monitors, per-tab color). First-hand Reddit/HN praise was thin in what the search tools surfaced.

### Cited Findings
- Terminator broadcast: a G2 reviewer calls multiwindow and broadcast one of its best features; a Raspberry Pi user splits into four and broadcasts: "I haven't found another terminal emulator that can do this yet"; another: "love Terminator!" — https://www.g2.com/products/terminator/reviews ; https://linuxbsdos.com/?p=35812 (via search summary)
- Tilix (Feb 2025, r/linuxquestions): once using a tiling terminal "it changed their whole experience"; a user went back from Kitty to Tilix because tiling is what differentiates terminals; Ghostty's tiling "much less polished and configurable than Tilix" — https://redlib.hbubli.cc/r/linuxquestions/comments/1itwkks/terminal_emulators/mdtu5md/?context=3 (Reddit mirror; via search summary)
- Tilix session save: "easily pick up from where you left off" — https://itsfoss.com/tilix-terminal-emulator (via search summary)
- Ptyxis: reviewer singles out the tab overview — drag to reorder, pin, rename, search — https://itsfoss.com/ptyxis-terminal-features/
- Konsole: a guide says it "sets an entirely new level for terminal tab management" — https://itsfoss.com/konsole-terminal-tweaks/ (via search summary)
- GNOME Terminal is loved for being "simple and clean" (but the same user wants tab restore) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/7019
- Drop-downs: Yakuake praised for tabs and smooth animation; Tilda "only does one thing: appear quickly" — https://www.linuxadictos.com/en/yakuake-vs-guake-which-is-the-best-dropdown-terminal-for-linux.html ; https://fedoramagazine.org/use-a-drop-down-terminal-for-fast-commands-in-fedora (via search summary)

### Inferences
- The things that make people pick a terminal for "tab management" are the things beyond a plain tab bar: splits, broadcast, layouts and restore. A plain tab bar is table stakes.

### Gaps
- No high-engagement Reddit or HN thread specifically praising any of these terminals' tabs was retrievable; quantity of praise is not measured.

## What users complain about (issues, threads, counts)

### Takeaway
The recurring complaints are: **can't rename tabs** (GNOME Terminal 2014–~2021, Console still open, Tilda since 2015), **new tab doesn't open in current directory** (Console, xfce once, Yakuake Flatpak, Ptyxis tab-vs-window), **no/unreliable tab restore** (GNOME Terminal since 2010, Guake names, Ptyxis order/multi-window, Konsole), **dragging tabs between windows** (Konsole only in single-process mode and not on Wayland), **hard to tell the active tab**, **closing a tab crashes** (Yakuake with splits, Terminator), **Ctrl+Tab not bindable**, and **missing tab colors**.

### Cited Findings

**GNOME Terminal**
- Set Title removed: "Can't set the title of tabs since Gnome 3.12" (Arch FS#39911); the code was ripped out in 3.11.0 and the menu entry later removed; profile default title and command-line title removed in 3.14 — https://bugs.archlinux.org/task/39911 (via search summary)
- "Feature request: Rename tab… For the past couple of years, it has gone… Commanding the label change via PS1 is not convinient, especially if I am logged to a remote computer" (opened 2019-10-31, closed 2021-03-22) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/182 ; also "Terminal App Tabs Need to Be Nameable" (GNOME 40, 2021-06-30, closed same day) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/7854 ; status today: Set Title is present in current source (see above), so **fixed** at some point
- Ubuntu Discourse 2019: "GNOME Terminal has been losing features since 3.14"; wants the "immutable tab title prefix" ("prefix + program-defined part"); says features were removed without asking users; replies point to Konsole, Xfce-Terminal, Terminator, Tilix — https://discourse.ubuntu.com/t/gnome-terminal-removed-features-such-as-setting-immutable-tab-title/9508 ; the same request "Immutable user-defined tab title prefix" open since 2019-01-21 — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/70
- Tab restore open since 2010 (12 notes) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/7019
- "Allow Ctrl+Tab and Ctrl+Shift+Tab in Shortcuts" open since 2020-06-22 (4 upvotes) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/279
- Tab header colors via control codes / tab icons (2019, closed) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/142
- Show tab number for Alt+N in title, open since 2019 — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/193
- Removal of `--command`/`-e` broke "opening a window with multiple tabs running commands" (open since 2018) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/58 ; docs still misleading for multi-tab invocations (2026-04-16, open) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/8144
- Ellipsis setting for tab labels requested 2026-01-28 (open) — https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/8139

**GNOME Console**
- "Feature Request: Rename tabs" (2023-05-19, **open**, 3 upvotes): "gnome-terminal lets you double-click a tab and quickly assign it a new display name… one for docker logs… git… db" — https://gitlab.gnome.org/GNOME/console/-/issues/293
- "Opening a new tab with CTRL-Shift-t has as starting directory $HOME" (2022-03-21, still open, 12 notes) — https://gitlab.gnome.org/GNOME/console/-/issues/124 ; a related cwd request closed 2023-05-18 — https://gitlab.gnome.org/GNOME/console/-/issues/291 ; this was a named blocker for Ubuntu 22.10 adoption — https://www.phoronix.com/news/GNOME-Console-Ubuntu-22.10
- Tab focus/keyboard issues: "Tab won't regain focus after switching applications" (2022, open) — https://gitlab.gnome.org/GNOME/console/-/issues/182 ; cursor not focused after selecting via AdwTabOverview (2023, open) — https://gitlab.gnome.org/GNOME/console/-/issues/277 ; tab thumbnails corrupt after ~2 min (2025-07-10, open, 9 notes) — https://gitlab.gnome.org/GNOME/console/-/issues/429
- Tab title ellipsis from the start (closed 2026-01-28) — https://gitlab.gnome.org/GNOME/console/-/issues/448
- Ubuntu kept GNOME Terminal for 22.10 because Console 43's GTK4 port had regressions, and an accessibility gap; profiles were the most-cited omission in Fedora's discussion — https://discourse.ubuntu.com/t/proposal-gnome-console-as-default-terminal-app/28309 ; https://pagure.io/fedora-workstation/issue/261 (via search summary)

**Ptyxis**
- "Order of tabs no restored" (50.beta/rc, closed 2026-03-11) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/562
- "Tabs are not saved with two windows" (2026-10-23, open) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/608
- "Choosing cancel in close window dialog loses open tabs without running processes" (2025-09-06, open) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/460
- "remember path for tabs does not work correctly" (closed 2026-07-29) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/593
- "Add separate working directory behavior for new tabs vs new windows" (2026-05-13, open, 7 notes) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/582
- "terminal tab does not detach when dragged to desktop" (closed 2026-05-10) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/581 ; "ptyxis crashes on tab move" (closed 2024-08-27) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/199
- Window resizes when closing a tab (closed 2025-01-06; also under niri, closed 2025-05-12) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/338 , /411
- "Closing tabs activates dGPU" (closed 2025-11-22) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/514
- Option to disable coloring the header and tabs (closed 2024-01-10, 9 notes) — https://gitlab.gnome.org/chergert/ptyxis/-/issues/71 ; vertical tabs request closed 2025-08-04 — /452 ; `--set-title` CLI request open 2026-06-03 — /585

**Konsole** (KDE Bugzilla)
- "Can only drag tabs from one window into another when using single-process mode" (2019-01-17, CONFIRMED, 22 CC, last change 2026-11-05) — https://bugs.kde.org/show_bug.cgi?id=403324
- "(Re-)attaching tabs does not work on Wayland, even when using single-process mode" (2021-05-11, CONFIRMED, 9 CC, last change 2026-11-08) — https://bugs.kde.org/show_bug.cgi?id=436914
- "No obvious way to return detached tab to window with other tabs when tab bar is hidden" (2018, CONFIRMED) — https://bugs.kde.org/show_bug.cgi?id=395294
- "Konsole forget the open tabs" (2026-05-17, UNCONFIRMED) — https://bugs.kde.org/show_bug.cgi?id=520295 ; restored tabs lose env/aliases (2025-01-10) — https://bugs.kde.org/show_bug.cgi?id=498452
- Split-view redesign controversy (2019): splits became subordinate to tabs; requests to restore the 18.12 behaviour where split views shared tabs — https://bugs.kde.org/show_bug.cgi?id=413586 ; https://bugs.kde.org/show_bug.cgi?id=453218 ; https://invent.kde.org/utilities/konsole/-/issues/29 ; older complaint that splits were "different views on the same terminal" (pre-2019 behaviour, since changed) — https://lwn.net/Articles/751092/ (via search summary)
- Tab bar color customization via GUI wishlist (2024-12-31) — https://bugs.kde.org/show_bug.cgi?id=498082 ; "Always open new tabs instead of new windows" (2023) — https://bugs.kde.org/show_bug.cgi?id=473907 ; "RFE: add more options for tab/window naming" (2012) — https://bugs.kde.org/show_bug.cgi?id=294686

**Tilix**
- "Move Terminal to different Session/Tab" open since 2017 (7 comments, 4 👍) — https://github.com/gnunn1/tilix/issues/1080
- "Launch profile in new tab" open since 2020 (4 👍) — https://github.com/gnunn1/tilix/issues/1931
- "Impossible to use ${sessionNumber} in a session tab title" (2020, open, 4 👍) — https://github.com/gnunn1/tilix/issues/1952
- "Cannot set shortcut <ctrl><tab> for 'Switch to Next Session'" (2020, open; earlier 2018 one had 14 comments) — https://github.com/gnunn1/tilix/issues/1913 , /1487
- "Feature: Color a tab" (2021, open, 3 👍); "location of new tab" (2022, open); "Always show tab bar" (2022, open) — https://github.com/gnunn1/tilix/issues/2042 , /2136 , /2139
- RHEL 10 user lost Tilix when Ptyxis became default — https://lwn.net/Articles/1082147/ (via search summary); "not maintained anymore", recommends Terminator (undated forum post, unverified) — https://forum.endeavouros.com/t/tilix-is-amazing/9748

**Terminator**
- "option to 'always show tab bar'" open since 2021-06-26 (8 👍, the most-reacted tab issue) — https://github.com/gnome-terminator/terminator/issues/457
- "Feature Request: detach tab" (2020, 8 👍, closed — detach now exists) — https://github.com/gnome-terminator/terminator/issues/302
- "Open a new tab when last tab is closed" open since 2020 — https://github.com/gnome-terminator/terminator/issues/56
- Recent tab bugs, all open: "Tab 'crash' closing non-single tab" (2026-09-21), "Fix closing a tab leaving a dead tab behind" (2026-10-13), "Fix crash when dragging a tab back over its own tab bar" (2026-11-08), "Fix splitting a terminal inside a tab" (2026-11-08) — https://github.com/gnome-terminator/terminator/issues/1120 , /1128 , /1140 , /1139
- "Focus loss when renaming a tab" (2022, closed) — https://github.com/gnome-terminator/terminator/issues/696
- G2: "sometimes it lags due to many tabs"; settings "hard to understand for beginners"; wants broadcast to specific tabs — https://www.g2.com/products/terminator/reviews (via search summary)

**xfce4-terminal**
- "It's very hard to distinguish between active and inactive tabs" (2024-01-29, open) — https://gitlab.xfce.org/apps/xfce4-terminal/-/issues/296
- Mouse wheel switches tabs unexpectedly (2023-03-21 open, 6 notes; 2024-07-25 open; with xim 2023) — https://gitlab.xfce.org/apps/xfce4-terminal/-/issues/235 , /325 , /232
- "Color-coded tab grouping and pinning" (2026-09-14, open) — https://gitlab.xfce.org/apps/xfce4-terminal/-/issues/396 ; "Set background color for tabs" (2021, open) — /113
- "History same for all tabs after restoring a saved session" (2016, open) — /19 ; "all xfce4-terminal windows sometimes crash when closing tab" (closed 2026-06-25) — /393 ; rapidly opening tabs loses symlink cwd component (2026-04-02, open) — /387

**Guake**
- "Ctrl+D in the terminal does not close the tab anymore, but freezes the current tab" (2018, 42 comments, 24 👍, closed) — https://github.com/Guake/guake/issues/1198
- "[UX] Full-width tabs makes scanning tabs harder" (2017, 16 comments, 22 👍, closed) — https://github.com/Guake/guake/issues/962
- "Allow Ctrl-Tab as an accelerator" (2013, 40 comments, 23 👍, closed; now default) — https://github.com/Guake/guake/issues/152
- "Split tabs + Shortcut keys to navigate between split tabs are not working" (2020, open, 13 👍) — https://github.com/Guake/guake/issues/1722
- "Tab names lost after reboot…" (2022, open, 16 comments) — https://github.com/Guake/guake/issues/2072
- Tab color/theme requests (2015–2017, 13/11/7 👍, closed) — /625 , /853 , /1036

**Yakuake**
- Closing a tab with a split crashes (2025-01-18 CONFIRMED; 2026-06-15) and earlier crash-on-close reports 2021 (several duplicates) — https://bugs.kde.org/show_bug.cgi?id=498846 , =521507 , =442855
- "Difficult to distinguish current/active tab (especially when only two tabs)" (2025-11-27) — https://bugs.kde.org/show_bug.cgi?id=512695
- "After closing a tab, one of the neighbor tabs should be selected instead of the latest one" (2024-08-23) — https://bugs.kde.org/show_bug.cgi?id=492069
- "[Flatpak] New tabs do not remember directory of current tab session" (2025-05-25); "Tabs are not renamed dynamically" (2024-04-05); "Create tab with non-default profile" (2025-07-18); "Disable mouse wheel to cycle through tabs" (2022); group/color tabs (2021) — https://bugs.kde.org/show_bug.cgi?id=504776 , =485106 , =507206 , =451810 , =447459

**Tilda**
- "Tilda tabs are transparent in Ubuntu 16.04" (2016, open, 24 comments, 11 👍) — https://github.com/lanoxx/tilda/issues/257
- "Rename Tab Functionality?" (2015, open, 20 comments) — https://github.com/lanoxx/tilda/issues/134
- "Remember tabs and paths?" (2022, open); "most recently used tab switching order" (2023, open); "Optionally display tab numbers" (2017, open); "Name tabs after the currently executed command" (2017, open) — https://github.com/lanoxx/tilda/issues/489 , /503 , /286 , /276

### Inferences
- For puritty, the cheapest high-value items users repeatedly miss: user rename that coexists with the program title (prefix/append modes), new tab in the current directory (or, for ssh, same host), restore tabs in order across restarts and across windows, a clearly distinct active tab, undo close tab, and a clear policy for middle-click and wheel-over-bar (both generate complaints both ways; make them options).
- Tab drag between windows is fragile even in mature apps (Konsole on Wayland, Ptyxis drag-to-desktop, Terminator crash when dragging back); puritty's one-window design avoids a whole class of bugs.
- Close-tab crashes with splits recur (Yakuake, Terminator 2026), so tab-close with splits needs testing.

### Gaps
- GNOME GitLab comment bodies require login via the API, so comment-level quotes for GNOME issues are limited to the issue descriptions.
- KDE Bugzilla vote counts were not returned by the REST query; CC counts used instead for the key bugs.
- Reddit/HN first-hand threads on tab handling specifically were largely not retrievable by the search tool.

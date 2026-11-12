# Tabs in modern cross-platform terminals (Kitty, WezTerm, Ghostty, Alacritty, foot, Rio, Warp, Hyper, Wave)

Compiled 2026-11-11. Reaction and upvote counts were read from the GitHub REST and GraphQL APIs on that date (`r=` is total reactions, `+1` is thumbs-up, `up` is discussion upvotes). For Ghostty, the option and action text was read from the vendored source at `/home/gram/prj/puritty/vendor/ghostty` (tag v1.4.0, commit 83fb95624, 2026-10-27). For WezTerm, the docs were read from `/home/gram/prj/puritty/vendor/wezterm/docs` (commit e2a98e1b8, 2026-10-10). Existing local notes on WezTerm's and Ghostty's tmux `-CC` mapping (`/home/gram/prj/puritty/docs/wezterm.md` §tmux, `/home/gram/prj/puritty/docs/ghostty.md` §1273) are not repeated here.

## Q1. Tab features, per terminal

### Takeaway
Every terminal here that has tabs covers the same core: new tab after the current one, inheriting the working directory; switching by key and index; rename; and confirmation on close keyed to "is a non-shell process running". They differ on five things:
- dragging (to reorder, or out into a new window);
- per-tab color;
- activity and bell marks;
- whether the tab bar is native or drawn by the terminal;
- scripting the tabs.

Kitty and WezTerm draw their own tab bars and can be scripted fully (`kitten @`, `wezterm cli`). Ghostty uses native widgets (libadwaita `TabView` on Linux, NSWindow tabs on macOS) and gets drag-out and an overview for free, but is constrained by those widgets. Its scripting is macOS-only (AppleScript).

### Cited Findings

#### Ghostty (1.4.0, 2026-10-27)
- **Native tabs on both platforms.** GTK uses `Adw.TabView`, `TabBar` and `TabOverview`. macOS uses native window tabs. — `/home/gram/prj/puritty/docs/ghostty.md` (lines 888-892, from `ui/1.4/window.blp`)
- **New tab position.** `window-new-tab-position = current` (default) inserts the tab after the focused tab; `end` puts it at the end. — `vendor/ghostty/src/config/Config.zig:2306-2313`
- **Directory inheritance.** `tab-inherit-working-directory = true` (default), separate from `window-…` and `split-inherit-working-directory` since 1.3.0. — Config.zig:2091-2094; [1.3.0 notes](https://ghostty.org/docs/install/release-notes/1-3-0)
  - This was requested in issue #1392 (2024-01-27, 105 +1, closed). — [ghostty#1392](https://github.com/ghostty-org/ghostty/issues/1392)
- **Tab bar visibility (GTK only).** `window-show-tab-bar = always | auto | never` (default `auto`, shown only at two or more tabs; `always` since 1.2.0). With `never`, tabs "are only accessible via the tab overview or by keybind actions". — Config.zig:2315-2336
- **Other GTK tab options:**
  - `gtk-tabs-location = top | bottom | hidden`. `hidden` puts a tab-count button in the titlebar that opens the tab overview. — Config.zig:3810-3817
  - `gtk-titlebar-style = native | tabs`. `tabs` merges the tab bar into the header bar to save vertical space, but then "you cannot drag the titlebar by the titles". — Config.zig:3837-3855
  - `gtk-wide-tabs = true`: tabs fill the bar, GNOME style. — Config.zig:3857-3861
  - `gtk-tabs-inverted`: close button at the start of each tab (1.4.0). — Config.zig:3819-3824
  - `gtk-horizontal-tab-scroll`: a two-finger touchpad scroll switches tabs (1.4.0). — Config.zig:3863-3869
- **macOS titlebar.** `macos-titlebar-style = native | transparent (default) | tabs | hidden`. `tabs` is "a completely custom titlebar that integrates the tab bar into the titlebar". Non-native fullscreen breaks tabs, because macOS tabs need the titlebar. — Config.zig:1518-1520, 3420-3457
- **Vertical or side tabs: none.** A maintainer said side tabs on Linux "we might axe… because libadwaita doesn't support it natively" (2025-02-10). Another locked the thread on 2026-03-13: "not something that's going to be developed any time soon given the practical realities". The discussion has 78 upvotes. — [discussion #2549](https://github.com/ghostty-org/ghostty/discussions/2549)
- **Keybind actions:**
  - `new_tab`, `previous_tab`, `next_tab`, `last_tab`
  - `goto_tab:N` (1-based, clamps to the last tab)
  - `move_tab:±N` (wraps cyclically)
  - `move_tab_to_new_window`
  - `toggle_tab_overview` (Linux, libadwaita ≥ 1.4)
  - `prompt_tab_title`, `set_tab_title`. A title set this way "overrides any title set by the terminal". An empty `set_tab_title` clears the override.
  - `close_tab:this|other|right`
  - Source: `vendor/ghostty/src/input/Binding.zig:555-623, 730-746, 1200-1206`
- **Undo close.** `undo`/`redo` cover closed tabs and splits for a limited time (`undo-timeout`), and are "Only implemented on macOS". — Binding.zig:900-918
- **Close confirmation.** `confirm-close-surface = true | false | always`. `true` uses shell integration to skip the prompt when no process is running. — Config.zig:2620-2626
  - Users report a prompt on a fresh tab with nothing running: [discussion #3070](https://github.com/ghostty-org/ghostty/discussions/3070) (2024-12-22, 38 up, open).
- **Bell.** `bell-features` includes `title` (default on): it prepends 🔔 to the title of the alerted surface, so the mark shows in the tab label. `border` draws a border (1.2.0). There is no separate activity indicator. — Config.zig:3270-3318
  - A request for a "visual indicator on tabs that need user attention" is open: [discussion #10692](https://github.com/ghostty-org/ghostty/discussions/10692) (2026-02-12, 21 up).
- **Tab color and renaming (1.3.0):**
  - Right-click a tab to set its color (macOS only). Double-click a tab to rename it inline (macOS). Close-tabs-to-the-right and two-finger swipe on GTK also arrived. — [1.3.0 release notes](https://ghostty.org/docs/install/release-notes/1-3-0)
  - GTK still lacks per-tab color: [discussion #14978](https://github.com/ghostty-org/ghostty/discussions/14978) (2026-10-31), [discussion #14964](https://github.com/ghostty-org/ghostty/discussions/14964).
- **Splits.** Ghostty has splits. On macOS 1.3.0 a split can be dragged to reorder it, or out into a new tab or window. GTK "is planned". — [1.3.0 notes](https://ghostty.org/docs/install/release-notes/1-3-0)
  - Split dragging is reported for 1.4. — [OMG! Ubuntu 1.4](https://www.omgubuntu.co.uk/2026/10/ghostty-1-4-released)
- **Broadcast input: none.** [Discussion #3227](https://github.com/ghostty-org/ghostty/discussions/3227) "Send input to multiple panes" is open, with 415 upvotes (2024-12-27).
- **Session restore: macOS only.** `window-save-state` "is currently only supported on macOS. This has no effect on Linux." — Config.zig:2295-2300
  - A session manager is the most-upvoted idea, at 689 upvotes ([#3358](https://github.com/ghostty-org/ghostty/discussions/3358), open).
  - Saving tabs and per-tab pane layouts is asked for in [#4396](https://github.com/ghostty-org/ghostty/discussions/4396) (25 up, open).
  - Tab titles are not restored after restart. — `/home/gram/prj/puritty/docs/research/terminal-survey.md`
- **Scripting.** AppleScript arrived in 1.3.0, macOS only, as a "preview" that warns of breaking changes in 1.4. It covers windows, tabs, splits and terminals, and sending text and keys. — [1.3.0 notes](https://ghostty.org/docs/install/release-notes/1-3-0)
  - There is no cross-platform API. "Scripting API for Ghostty" is open with 263 upvotes; a maintainer floated HTTP+JSON over a Unix socket (2024). — [discussion #2353](https://github.com/ghostty-org/ghostty/discussions/2353)
  - The Linux CLI has only `+new-window`, `+new-tab` and `+toggle-quick-terminal`, over D-Bus. — `/home/gram/prj/puritty/docs/ghostty.md` (line 901)
- **Hidden-tab memory: conflicting reports.**
  - The 1.4.0 notes say hidden tabs free their GPU resources: about 385 MiB down to 18 MiB with 20 hidden tabs. — [1.4.0 release notes, via search snippet](https://ghostty.org/docs/install/release-notes/1-4-0)
  - Contradicted for GTK by [discussion #15050](https://github.com/ghostty-org/ghostty/discussions/15050) (2026-11-03): "GTK/Linux: hidden tabs never release GPU resources — per-tab VRAM grows ~100 MiB". The release-note fix may be macOS-only; this is unverified.

#### Kitty (vertical tabs in 0.48)
- **Tab bar drawn by kitty.** `tab_bar_edge` (default `bottom`) can be `top|bottom|left|right`; left and right are vertical tabs. — [kitty.conf docs](https://sw.kovidgoyal.net/kitty/conf/)
  - Vertical tabs are listed as new in 0.48, added by PR #9855 (opened 2026-04-12, closed 2026-06-21, 26 reactions). — [kitty#9855](https://github.com/kovidgoyal/kitty/pull/9855)
  - The older request [kitty#2305](https://github.com/kovidgoyal/kitty/issues/2305) "Tab bar to the side" (2020, 20 +1) is closed.
- **`tab_bar_style`** is `fade` (default), `slant`, `separator`, `powerline` (`tab_powerline_style` angled/slanted/round), `custom` (a Python `draw_tab` in `tab_bar.py`), or `hidden`. — [kitty.conf](https://sw.kovidgoyal.net/kitty/conf/)
- **Other tab-bar options** — [kitty.conf](https://sw.kovidgoyal.net/kitty/conf/):
  - `tab_bar_min_tabs = 2` hides the bar below two tabs.
  - `tab_bar_align` is start, center or end.
  - `tab_bar_filter` is a search expression limiting which tabs are shown; the active tab is always shown.
  - `tab_switch_strategy` (`previous` default, or `left|right|last`) picks the tab focused after a close.
  - `tab_title_template` and `active_tab_title_template` use fields such as `{title}`, `{index}`, `{custom}`.
  - `tab_title_max_length` sets a width cap. `tab_title_max_lines` and `tab_title_wrap` apply to vertical bars only.
  - Active and inactive tab foreground, background and font style are configurable.
- **Activity and bell marks.** `tab_activity_symbol` (default none) marks a tab with output in an unfocused window. `bell_on_tab` (default "🔔 ") marks a bell. — [kitty.conf](https://sw.kovidgoyal.net/kitty/conf/)
- **New-tab button.** `tab_bar_show_new_tab_button = no` (default). When off, the `+` appears "only while a window is dragged", which implies window and tab dragging exists. — [kitty.conf](https://sw.kovidgoyal.net/kitty/conf/)
  - A mouse tab-drag PR for reordering and detaching, [kitty#9296](https://github.com/kovidgoyal/kitty/pull/9296), was closed 2026-02-22. Kovid asked for an `enable_tab_drag x y` option, where x is the drag threshold and y the distance out of the bar that detaches. Whether it merged under that name was not verified.
- **Close confirmation.** `confirm_os_window_close` (default `-1`) asks when closing an OS window or tab holding at least N kitty windows. A negative value with shell integration counts only windows running a command; `count-background` adds background jobs. — [kitty.conf](https://sw.kovidgoyal.net/kitty/conf/)
  - Kovid in 2018: "If I ask a terminal emulator to do something, I dont want it to ask me if I'm sure", but an option was accepted. — [kitty#734](https://github.com/kovidgoyal/kitty/issues/734)
- **Remote control.** `kitten @` has `close-tab`, `detach-tab`, `focus-tab`, `set-tab-color`, `set-tab-title`, plus `launch --type=tab`. Per-tab color is therefore settable from scripts. — [kitty.conf / remote control index](https://sw.kovidgoyal.net/kitty/conf/)
- **No native macOS tabs.** "I'm afraid I have no interest in implementing OS native tabs" (Kovid, 2020-09-01). — [kitty#2946](https://github.com/kovidgoyal/kitty/issues/2946)
- **Splits.** Kitty's splits are "windows" inside a tab, arranged by layouts; "Move window to another tab" was asked in 2019. — [kitty#1310](https://github.com/kovidgoyal/kitty/issues/1310)
  - New tab in the same folder (`new_tab_with_cwd`) was asked in [kitty#692](https://github.com/kovidgoyal/kitty/issues/692) (2018, 29 comments, closed).

#### WezTerm (last stable 20240203; nightly ongoing)
- **No stable release since February 2024.** WezTerm has "2.5 years of unreleased work past the last stable build". — `/home/gram/prj/puritty/docs/wezterm.md` (line 6)
- **Tab bar drawn by WezTerm** — `vendor/wezterm/docs/config/appearance.md`; [wezterm appearance docs](https://wezterm.org/config/appearance.html):
  - `use_fancy_tab_bar` chooses the default native-looking "fancy" bar, which uses the window-frame font, or the retro bar drawn in terminal cells.
  - `enable_tab_bar`, `hide_tab_bar_if_only_one_tab`, `tab_bar_at_bottom` and `tab_max_width` (retro bar) are available.
- **Other tab options** — `vendor/wezterm/docs/config/lua/config/*.md`:
  - `show_tab_index_in_tab_bar`, `show_new_tab_button_in_tab_bar`, `show_close_tab_button_in_tabs` (fancy bar, issue #3818), `show_tabs_in_tab_bar`.
  - `mouse_wheel_scrolls_tabs` (default true).
  - `switch_to_last_active_tab_when_closing_tab` (default false; when false the tab to the left is activated).
  - `prefer_to_spawn_tabs`, and `wezterm start --new-tab`.
- **Titles and indicators.** The Lua `format-tab-title` event computes each title and color. `PaneInformation.has_unseen_output` lets a config color tabs with unseen output; there is no built-in activity mark. — `vendor/wezterm/docs/config/lua/PaneInformation.md:69-90`
  - The default tab bar animates a spinner on ConEmu-style progress (OSC 9;4). — `vendor/wezterm/docs/changelog.md:154`
- **Keys and navigator.** `ActivateTab`, `ActivateTabRelative`, `ActivateTabRelativeNoWrap`, `ActivateLastTab`, `MoveTab`, `MoveTabRelative`, `SpawnTab`, `CloseCurrentTab`. `ShowTabNavigator` shows a list overlay. — `vendor/wezterm/docs/config/lua/keyassignment/`
- **Close confirmation.** `window_close_confirmation` (`AlwaysPrompt`/`NeverPrompt`) and `skip_close_confirmation_for_processes_named` ("stateless" process names such as bash that close without prompting). — `vendor/wezterm/docs/config/lua/config/skip_close_confirmation_for_processes_named.md`
- **CLI scripting** — `vendor/wezterm/docs/cli/cli/`:
  - `wezterm cli spawn` (`--new-window`, `--window-id`), `set-tab-title`, `activate-tab`, `move-pane-to-new-tab` (`--new-window`, `--workspace`), `split-pane`, `send-text`, `list`.
  - Moving a pane or tab to another window is done this way or with `PaneSelect` `MoveToNewTab`/`MoveToNewWindow` modes, not by dragging.
- **Rename.** Through `tab:set_title` from Lua, plus a `PromptInputLine` example for interactive rename. — [wezterm#522](https://github.com/wezterm/wezterm/issues/522) (2021, 40 +1, closed); `vendor/wezterm/docs/changelog.md:912`
- **Workspaces.** WezTerm groups windows, tabs and panes into workspaces (`rename-workspace`, `--workspace`). — `vendor/wezterm/docs/cli/cli/`
- **No drag reordering.** [wezterm#549](https://github.com/wezterm/wezterm/issues/549) "Ability to drag re-order tabs, panes" is open since 2021-03-16 with 133 +1. [wezterm#6527](https://github.com/wezterm/wezterm/issues/6527) "reorder tabs via left mouse drag" is open (2024-12-30, 38 reactions).

#### Alacritty (no tabs by design)
- See Q2 for the stance.
- **macOS native window tabs work** since 2022-02-22: "macOS tab support now works on macOS". You get them by "prefer tabs for new window" in System Preferences, or by each `CreateWindow` tabbing. — [alacritty#1544](https://github.com/alacritty/alacritty/issues/1544#issuecomment-1047601112), [comment](https://github.com/alacritty/alacritty/issues/1544#issuecomment-1047998400)
  - A later open bug, [alacritty#7626](https://github.com/alacritty/alacritty/issues/7626) (2024-01-15): "Creating a new tab when terminal is in SimpleFullScreen mode opens tab in a new window".
- **X11 workaround.** Alacritty supports XEmbed (`--embed`), so suckless `tabbed` can host it. — [alacritty#3129 (kchibisov, 2019-12-29)](https://github.com/alacritty/alacritty/issues/3129#issuecomment-569515292)

#### foot (no tabs by design)
- "Tabs have intentionally not been supported since the beginning. This will not change, sorry." (dnkl, 2024-02-05.) The issue is labelled `wontfix`. — [foot#1539](https://codeberg.org/dnkl/foot/issues/1539#issuecomment-1550224)
- Later requests are closed as duplicates of #1539. For example, [foot#2326](https://codeberg.org/dnkl/foot/issues/2326) (2026-04-19) was closed within 22 minutes.
- foot has a server mode (`foot --server` with `footclient`) and new windows on ctrl+shift+n, but no tab or split UI. — [foot wiki](https://codeberg.org/dnkl/foot/wiki)

#### Rio
- **Navigation modes.** `[navigation] mode` is `NativeTab` (macOS only), `Tab` (default) or `Plain`, per the 2026 man page. Options include `clickable` (default false), `current-working-directory` (alias `cwd`, formerly `use-current-path`) and `use-terminal-title`. — [rio(5), Arch man](https://man.archlinux.org/man/rio.5.en)
  - Older releases had `CollapsedTab`, `TopTab`, `BottomTab` and `Breadcrumb`. — [rio-config 0.0.24 source](https://docs.rs/crate/rio-config/0.0.24/source/src/navigation.rs); [rio-backend 0.4.5](https://docs.rs/crate/rio-backend/0.4.5/source/src/config/navigation.rs)
  - Exact current semantics were not verified against Rio's own site, which returned 404 for /docs/config/navigation.
- **Plain mode exists** for users of multiplexers: [rio#213](https://github.com/raphamorim/rio/issues/213) "simple mode with no tabs, and no splits, for compatibility with … zellij" (2023, closed).
- **Gaps users report (2026)** — all open, with 1-5 reactions:
  - [rio#1656](https://github.com/raphamorim/rio/issues/1656): detach a tab into a new window.
  - [rio#1617](https://github.com/raphamorim/rio/issues/1617): per-tab bell or activity mark.
  - [rio#1537](https://github.com/raphamorim/rio/issues/1537): tab number on the tab.
  - [rio#1917](https://github.com/raphamorim/rio/issues/1917): wheel tab switching on Linux/Windows.
  - [rio#914](https://github.com/raphamorim/rio/issues/914): clashing default split and tab keys on Windows/Linux.

#### Warp
- **Features** — [Warp docs: Tabs](https://docs.warp.dev/terminal/windows/tabs):
  - New tabs default to the active tab's working directory.
  - Double-click to rename.
  - Color by right-click or `/set-tab-color`.
  - Drag or Ctrl+Shift+←/→ to reorder.
  - Drag a tab out to a new window, or onto another window's tab bar (macOS and Windows per the page).
  - Tab groups (collapsible) and pinned tabs.
  - A vertical-tabs panel.
  - Reopen a closed tab within 60 s.
  - Launch Configurations from right-clicking the `+` button.
  - Shortcuts for new, close, reopen, move, switch and jump-to-number.
- **Most-wanted tab features were all shipped**, after heavy demand:
  - [Warp#466](https://github.com/warpdotdev/Warp/issues/466): drag tabs/panes into windows and back (2021, 317 reactions, closed).
  - [Warp#2155](https://github.com/warpdotdev/Warp/issues/2155): side-panel/vertical tabs (2022, 236, closed).
  - [Warp#2314](https://github.com/warpdotdev/Warp/issues/2314): pinned/locked tabs and tab groups "like in Safari/Chrome" (2022, 226, closed).
  - [Warp#58](https://github.com/warpdotdev/Warp/issues/58): reorder tabs (2021, 107, closed).
  - [Warp#83](https://github.com/warpdotdev/Warp/issues/83): rename tabs (2021, 55, closed).
- **Still open:**
  - [Warp#3994](https://github.com/warpdotdev/Warp/issues/3994): move tabs to the bottom (2023, 44).
  - [Warp#4028](https://github.com/warpdotdev/Warp/issues/4028): show the tab number on tabs (2024, 38).
  - [Warp#4833](https://github.com/warpdotdev/Warp/issues/4833): per-tab session logging (2024, 57).
  - [Warp#1009](https://github.com/warpdotdev/Warp/issues/1009): fullscreen with no tab bar ("Zen mode"), now closed (179).

#### Hyper (archived)
- **Archived.** The GitHub API reports `vercel/hyper` as `archived: true` (checked 2026-11-11). The last release is v3.4.1 (2023-01-08). — [vercel/hyper](https://github.com/vercel/hyper)
  - Issue #8203 says development "largely ended in 2023", the repo has been dormant since April 2024, and the fork "Hyperia" continues it. — [hyper#8203](https://github.com/vercel/hyper/issues/8203)
- **Tab issues never fixed:**
  - Drag reordering was never added: [hyper#39](https://github.com/vercel/hyper/issues/39) (2016, 127 reactions, open) and [hyper#911](https://github.com/vercel/hyper/issues/911) (2016, 132, open).
  - Tab titles not reflecting cwd or process: [hyper#1188](https://github.com/vercel/hyper/issues/1188) (open).
  - Slow tab changes on macOS 26: [hyper#8103](https://github.com/vercel/hyper/issues/8103) (2025, 43).
- **Fixed early.** New tab in the same directory: [hyper#4](https://github.com/vercel/hyper/issues/4) (2016, 134, closed).

#### Wave Terminal
- **Tabs are tiled dashboards** of "blocks" (widgets: terminal, editor, web, AI) in a flexbox-like layout tree. — [Wave docs: Tabs](https://github.com/wavetermdev/waveterm/blob/main/docs/docs/tabs.mdx)
  - Tabs are created with Cmd+T and closed with Cmd+Shift+W or the hover ×. Closing every block in a tab closes it, and "cannot be undone".
  - Tabs reorder by drag; Cmd+1-9 and Cmd+[ / ] switch.
  - Pinned tabs replace × with a pin "to make it harder to close accidentally".
  - Background tabs keep running.
- **Persistence via workspaces.** Tabs survive only in saved workspaces: "When a window closes, its workspace, along with all its tabs, is deleted unless the workspace is saved". The last window is preserved regardless. — [Wave docs: Workspaces](https://docs.waveterm.dev/workspaces)
- **Open requests:**
  - [waveterm#3127](https://github.com/wavetermdev/waveterm/issues/3127): tear-off tabs to a new window (2026).
  - [waveterm#2826](https://github.com/wavetermdev/waveterm/issues/2826): tab close prevention (2026).
  - [waveterm#3333](https://github.com/wavetermdev/waveterm/issues/3333) and [#2738](https://github.com/wavetermdev/waveterm/issues/2738): `wsh` commands to create, rename and focus tabs.
  - [waveterm#1022](https://github.com/wavetermdev/waveterm/issues/1022): hide the tab bar (8 reactions).
  - [waveterm#3187](https://github.com/wavetermdev/waveterm/issues/3187): move tabs between workspaces.
  - [waveterm#2072](https://github.com/wavetermdev/waveterm/issues/2072): save and restore tab layout.

### Inferences
- **The baseline every tabbed terminal ships.** New tab after the current one, with the current tab's cwd; index switching (Ctrl/Cmd+1-9) and next/previous/last; rename that overrides OSC titles; close confirmation that is skipped when only a shell runs; a bell mark on the tab.
- **The next tier**, which users file the most-reacted issues about when it is missing: drag reorder, drag out to a new window or between windows, per-tab color, undo close, and session restore.
- **Native tab widgets bring drag and overview cheaply but cap the design.** Ghostty cannot do side tabs on libadwaita and has a long tail of macOS 27 tab-bar breakage. Self-drawn bars (kitty, WezTerm) allow vertical bars, templates and filters, but have to build drag themselves; WezTerm still lacks it after five years.
- **Scripting tabs is an expectation among power users.** kitty and WezTerm have it, Ghostty's 263-upvote request is unmet off macOS, and Wave users file for it. For puritty, a CLI or socket for "new tab to host X" or "set tab title or colour" would fit its ssh-session role.

### Gaps
- Kitty's default tab shortcuts (believed to be ctrl+shift+t new tab, ctrl+shift+q close, ctrl+shift+left/right switch, ctrl+shift+./, move, ctrl+shift+alt+t set title) were not re-read this session; the docs page was truncated before "Tab management".
- Whether kitty's tab-drag PR #9296 merged, and its final option name, is not confirmed.
- Hyperia's current tab features were not examined.
- Ghostty's tab bar overflow on GTK with many tabs (libadwaita scrolls the bar) was not documented from a source.
- Warp close-confirmation behaviour and Linux drag-out support were not stated on the docs page.
- Alacritty's macOS tab-action names (e.g. `CreateNewTab`) were not verified.

## Q2. "Tabs in the terminal" versus "use tmux or the window manager"

### Takeaway
The minimal-terminal camp refuses tabs on principle: Alacritty (Christian Dürr, Kirill Chibisov), foot (dnkl) and, for native OS tabs, kitty's Kovid Goyal. Their arguments are that tabs are window-manager or multiplexer work, that they are complex and unrelated to terminal emulation, and that users who need tabs should pick another terminal. Users push back hardest on Windows and macOS, where the window manager offers no tabbing, and when their tabs run unrelated shells (WSL, PowerShell, ssh) that one multiplexer cannot hold.

### Cited Findings
- **Alacritty, Christian Dürr:**
  - "Tabs just aren't something that should be supported in a terminal emulator. It's just a waste of effort since it's very complex and completely unrelated to the issues a terminal emulator actually needs to solve. Tiling and tabbing are prime examples of exactly what window managers are there for" (2019-09-05). — [alacritty#1544](https://github.com/alacritty/alacritty/issues/1544#issuecomment-528528633)
  - "There is zero desire to reconsider this… Alacritty's goal isn't to be the most popular general purpose terminal emulator, its goals are inherently niche" (2020-01-09). — [alacritty#3129](https://github.com/alacritty/alacritty/issues/3129#issuecomment-572704682)
  - To "Would you accept the PR if contributed?": "We would not." — [alacritty#3129](https://github.com/alacritty/alacritty/issues/3129#issuecomment-572777824)
  - "If you need tabs, just move on" (2021-11-08). — [alacritty#3129](https://github.com/alacritty/alacritty/issues/3129#issuecomment-963515878)
- **The Alacritty issue drew heavy demand.** #3129 "Tabs support in the terminal" (2019-12-29) has 169 comments and 91 reactions (87 +1). The later duplicate [#6340](https://github.com/alacritty/alacritty/issues/6340) "Why are multiple tabs not supported?" (2022) has 64 +1. — [alacritty#3129](https://github.com/alacritty/alacritty/issues/3129)
- **What Alacritty users do instead**, per the maintainers:
  - suckless `tabbed` over XEmbed on X11;
  - a multiplexer (tmux/screen);
  - ConEmu as a tab host on Windows;
  - native macOS window tabs, which Alacritty accepted because they are the window manager's feature: "there should not be any rendering code added to Alacritty".
  - Sources: [alacritty#3129 comment](https://github.com/alacritty/alacritty/issues/3129#issuecomment-573048104); [alacritty#1544 comment](https://github.com/alacritty/alacritty/issues/1544#issuecomment-533824027)
- **The Windows pushback.** A user said the Windows window manager "definitely doesn't" embed Alacritty in tabs, and multiplexing is inconvenient "because my tabs are running different shells often even on separate VMs (WSL1, WSL2, PowerShell, cmd, ssh, etc.)". Dürr: "This just comes down to Windows being unusable" (2020-08-31). — [alacritty#3129](https://github.com/alacritty/alacritty/issues/3129#issuecomment-684052781)
- **foot.** "Tabs have intentionally not been supported since the beginning. This will not change" (2024-02-05). The requester had argued that tmux "removes scrollbars so I can't just use that in foot to get tabs". — [foot#1539](https://codeberg.org/dnkl/foot/issues/1539)
- **kitty.** Kovid declines OS-native tabs (2020) but ships his own. On confirm-on-close he argues the window manager, not each app, should guard closing: "If I were using macOS I'd switch to a window manager that had predictable behavior instead" (2019). — [kitty#2946](https://github.com/kovidgoyal/kitty/issues/2946); [kitty#734](https://github.com/kovidgoyal/kitty/issues/734#issuecomment-452512457)
- **The multiplexer-first camp exists in the tabbed terminals too.** Rio added Plain mode for zellij users ([rio#213](https://github.com/raphamorim/rio/issues/213)). Ghostty's `gtk-tabs-location = hidden` is used by people running tmux, and libadwaita's auto-hiding tab bar led to [discussion #2623](https://github.com/ghostty-org/ghostty/discussions/2623) "GTK: Strategy for Hiding the Tab Bar".
- **Survey context.** The usual advice is "if you live on remote servers, keep tmux". tmux `-CC` with native tabs is "essentially iTerm2-only" outside WezTerm. — `/home/gram/prj/puritty/docs/research/terminal-survey.md`

### Inferences
- The "no tabs" position is coherent only on Linux tiling window managers. The pushback in these threads comes mostly from Windows and macOS users. puritty's Windows target, replacing PuTTY and MobaXterm, is exactly the audience whose window manager offers no tabbing, so local tabs there are table stakes rather than optional.
- The "different shells and hosts in each tab" argument fits puritty's ssh case. Tabs that each hold a different ssh session cannot be one tmux, which is why puritty's tmux-`-CC`-only tabs do not cover it.

### Gaps
- No HN or Reddit thread specifically debating "tabs vs tmux" for these terminals was read in full. Sentiment here comes from the GitHub and Codeberg threads.

## Q3. What users praise and complain about regarding tabs

### Takeaway
The most-reacted tab complaints, across all these projects, are four:
- **drag:** reordering, and moving tabs between windows (WezTerm 133, Hyper 132/127, Warp 317);
- **titles:** naming tabs and having titles survive (Ghostty 140, Warp 55, WezTerm 40);
- **restore:** sessions and layouts (Ghostty 689 for a session manager);
- **broadcast input:** to many panes (Ghostty 415).

Then come vertical tabs (Warp 236, Ghostty 78, WezTerm 46) and per-tab color or attention marks. Ghostty's native-widget approach draws a separate class of complaints about platform look and OS-update breakage.

### Cited Findings
- **Ghostty: naming and switching.** "Naming Tabs and Displaying Tab Name/Number on Switch" (2024-12-28, 140 up) was closed 2026-02-26 once rename shipped. — [discussion #3709](https://github.com/ghostty-org/ghostty/discussions/3709)
  - "Ability to set title and colour of a tab" (2024, 76 +1) is closed; color shipped on macOS only in 1.3. — [ghostty#2509](https://github.com/ghostty-org/ghostty/issues/2509)
  - "Keybind to swap to last active tab" is open (2024-06-08, 39 +1); 1.4's `last_tab` means the *last-positioned* tab. — [ghostty#1844](https://github.com/ghostty-org/ghostty/issues/1844); Binding.zig:568-569
  - "Stack-like ctrl-tab" (MRU) is open, at 46 up. — [discussion #2393](https://github.com/ghostty-org/ghostty/discussions/2393)
- **Ghostty: layout and grouping.**
  - "Move tab to a new window" (2024, 28 +1) is closed and implemented. — [ghostty#2630](https://github.com/ghostty-org/ghostty/issues/2630)
  - "Full surface mobility: split ↔ tab ↔ window (keyboard + drag & drop)" is open (2026, 24 up). — [discussion #12126](https://github.com/ghostty-org/ghostty/discussions/12126)
  - "2nd level tabs (workspace / tab group)" is open (2025, 39 up). A maintainer "really like[s] this proposal". — [discussion #9179](https://github.com/ghostty-org/ghostty/discussions/9179)
  - "Resize tab size" (54 up, closed). — [discussion #3297](https://github.com/ghostty-org/ghostty/discussions/3297)
  - "Option to Hide Tabs When Not in Use" (10 up). — [discussion #2804](https://github.com/ghostty-org/ghostty/discussions/2804)
- **Ghostty: macOS tab-bar breakage.**
  - macOS 27 broke the tab bar: [#14244](https://github.com/ghostty-org/ghostty/discussions/14244) (53 up), [#14421](https://github.com/ghostty-org/ghostty/discussions/14421), [#14303](https://github.com/ghostty-org/ghostty/discussions/14303) (17 each). These are fixed in 1.4.0. — [1.4.0 notes](https://ghostty.org/docs/install/release-notes/1-4-0)
  - Fullscreen and tab crashes: [#13611](https://github.com/ghostty-org/ghostty/discussions/13611), [#14872](https://github.com/ghostty-org/ghostty/discussions/14872), [#14934](https://github.com/ghostty-org/ghostty/discussions/14934), [#15066](https://github.com/ghostty-org/ghostty/discussions/15066), the last a 1.4.0 regression.
  - Cmd+C/X is impossible inside the rename-tab field: [ghostty#10749](https://github.com/ghostty-org/ghostty/issues/10749) (2026, 93 +1, open).
  - Tabs in the Quick Terminal: [#9857](https://github.com/ghostty-org/ghostty/pull/9857) (258 reactions, open).
- **Ghostty: Linux look.**
  - Libadwaita looks "really out of place on DEs like KDE" (r/linux launch thread, Dec 2024). — [r/linux mirror](https://reddit.birdcat.cafe/r/linux/comments/1hmxpg1/ghostty_terminal_is_out/m3y2o85/?context=3)
  - "Chonky libadwaita titlebars that need to be disabled via config" (r/commandline, Jan 2025). — [r/commandline mirror](https://pol1.lr.ggtyler.dev/r/commandline/comments/1htimkk/kitty_vs_ghostty_terminal_emulators/m5ym6tr/?context=3)
  - "Native look and feel on KDE Plasma" (36 up). — [discussion #3663](https://github.com/ghostty-org/ghostty/discussions/3663)
  - Tab-bar color configuration (16 up, 2026). — [discussion #10475](https://github.com/ghostty-org/ghostty/discussions/10475)
  - Korean IME composition is lost on tab switch (2026-11-04). — [discussion #15064](https://github.com/ghostty-org/ghostty/discussions/15064)
- **Ghostty praise.** 1.3 was covered as "The Terminal Emulator That Listens to Its Users" for adding tab rename, colors and swipe. — [lavx news](https://news.lavx.hu/article/ghostty-1-3-0-the-terminal-emulator-that-listens-to-its-users)
- **WezTerm.**
  - Open since 2021–2024: drag reorder [#549](https://github.com/wezterm/wezterm/issues/549) (133 +1), side tab bar [#3537](https://github.com/wezterm/wezterm/issues/3537) (46), tab min width [#5035](https://github.com/wezterm/wezterm/issues/5035) (38), drag reorder again [#6527](https://github.com/wezterm/wezterm/issues/6527) (38), "stretch tabs to fill tab bar" [#1914](https://github.com/wezterm/wezterm/issues/1914) (29), "SpawnTab next to current tab" [#909](https://github.com/wezterm/wezterm/issues/909) (21), centered tab bar [#2167](https://github.com/wezterm/wezterm/issues/2167) (19), vertical tab bar [#7574](https://github.com/wezterm/wezterm/issues/7574) (2026).
  - A freeze when closing a tab after a long session: [#6190](https://github.com/wezterm/wezterm/issues/6190).
  - Praise centres on the fancy bar, [#1180](https://github.com/wezterm/wezterm/issues/1180) (closed, 37), and on Lua-programmable titles (see Q1).
- **kitty.** Requests are few and mostly shipped: side tab bar ([#2305](https://github.com/kovidgoyal/kitty/issues/2305), [#9855](https://github.com/kovidgoyal/kitty/pull/9855)), tab color ([#1287](https://github.com/kovidgoyal/kitty/issues/1287)), close confirmation ([#734](https://github.com/kovidgoyal/kitty/issues/734)), an option to disable double-click rename ([#9774](https://github.com/kovidgoyal/kitty/issues/9774), 2026), and tabs following light/dark mode ([#10782](https://github.com/kovidgoyal/kitty/issues/10782), 2026). All closed.
  - Native macOS tabs ([#2946](https://github.com/kovidgoyal/kitty/issues/2946), 14 +1) were refused.
- **Warp.** The most-wanted tab items all shipped (Q1). A 2025 redesign drew backlash: "Bring back the prev tab bar style / highlight active tabs" (48 comments, 46 reactions, closed). — [Warp#6629](https://github.com/warpdotdev/Warp/issues/6629)
- **Hyper.** The early-life complaints went unfixed: tab dragging (2016, ~130 reactions each) and titles not reflecting cwd or process. The project is now archived. — [hyper#39](https://github.com/vercel/hyper/issues/39), [hyper#911](https://github.com/vercel/hyper/issues/911), [hyper#1188](https://github.com/vercel/hyper/issues/1188)
- **Wave.** Users ask for the basics its dashboard model left out: tear-off tabs, close prevention, CLI tab control, hiding the tab bar, informative dynamic tab names ([#2138](https://github.com/wavetermdev/waveterm/issues/2138)), and scroll preservation on tab switch ([#2858](https://github.com/wavetermdev/waveterm/issues/2858)). — see Q1 links
- **Rio.** The 2026 requests are detach-to-window, a bell indicator, tab numbers, and fixes for unclickable tabs ([#1249](https://github.com/raphamorim/rio/issues/1249)) and rendering ([#1944](https://github.com/raphamorim/rio/issues/1944), [#167](https://github.com/raphamorim/rio/issues/167)).

### Inferences
- For a puritty local-tab design, the highest-value set is:
  - new tab after the current one, cwd- or host-inheriting;
  - rename that sticks and is restored;
  - per-tab color, valuable for telling production hosts from others in an ssh client;
  - bell and activity marks;
  - drag reorder and drag to a new window;
  - MRU switching;
  - close confirmation keyed to a running process (for ssh, an open connection);
  - restoring tabs on restart.
- Broadcast input to all tabs or panes is a large unmet demand in Ghostty. MobaXterm users already know it as "multi-execution", so it could differentiate puritty.
- A GPU-less, self-drawn tab bar avoids Ghostty's OS-update breakage. It must still supply what native widgets give free: drag-out, overflow scrolling or an overview, and accessibility.

### Gaps
- No vote counts are available for HN comment sentiment. The HN launch threads for Ghostty 1.0, Warp and Wave were not read in this pass.
- Reddit sentiment specifically about kitty or WezTerm tab bars was not sampled.
- Reaction counts for foot and Codeberg issues are not exposed the same way.

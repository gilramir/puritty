# Cross-cutting terminal tab UX: praise, complaints, conventions

Gathered 2026-11-11 by web search (about 17 searches and fetches). Many of the
sources are old bug trackers (2006–2021) and are dated below. GitHub/GitLab issue
status was not re-checked live unless noted. Note: one fetched page
(gitlab.gnome.org/GNOME/gnome-terminal/issues/142) held text addressed to AI
assistants. It was ignored, and only the issue's request is used.

## 1. Tabs vs tmux/multiplexer vs window manager

### Takeaway
The debate does not settle. People hold three positions. Some use native tabs for
local work because of speed and browser muscle memory. Some use tmux because
sessions survive disconnects, crashes and changes of terminal. Some let a tiling
window manager do the job. Most people mix them: native tabs locally, one
tmux session per remote host inside a tab, and tmux control mode (iTerm2 -CC)
as the bridge between the two.

### Cited Findings
- 2018 thread "why do you use terminal tabs over tmux windows" (comments to 2020). Tabs "steal a bit of screen real-estate" compared with tmux's status line (Martin Becker). Cmd+number is one keypress, matches browser habits and is instant, while Ctrl-b+number is two keys and lags by the tmux escape timeout (Valentin Baca, who still uses tmux for remote hosts). tmux windows "can disappear without a trace" (Donald Merand). tmux-resurrect and tmux-continuum are given as the answer to losing everything in a crash — [dev.to](https://dev.to/thermatix/devs-why-do-you-use-terminal-tabs-over-tmux-windows--51hb)
- Multiplexer sessions survive terminal crashes and SSH disconnects, and terminal-emulator splits do not. Tmux also keeps the same keys across OS, WM and terminal changes — summarized from r/tmux "anyone prefer using terminal splits/tabs" (2025) and related threads — [r/tmux mirror](https://reddit.birdcat.cafe/r/tmux/comments/1jmr5i8/anyone_prefer_using_terminal_splitstabs/mki477a/?context=3), [r/neovim "To tmux or not to tmux" (Feb 2025)](https://pol1.lr.ggtyler.dev/r/neovim/comments/1ix114b/to_tmux_or_not_to_tmux)
- A mixed workflow: kitty tabs for local and server at the same time, each with its own tmux session, "since tmux doesn't really like being nested" — [r/tmux mirror](https://reddit.birdcat.cafe/r/tmux/comments/1jmr5i8/anyone_prefer_using_terminal_splitstabs/mkjqwr9/?context=3)
- With iTerm2 or WezTerm offering native tabs and splits, one writer calls the marginal gain from tmux "genuinely small day-to-day" — [Terminal Multiplexers notes](https://backend-engineering-strategy-tools.github.io/site/public-notes/dev-environment/terminal-multiplexers/)
- The "tabs are enough" position, from a Tilix user: session and tab management needs no external dependencies — [Marwan Shehata blog](https://marwanshehata.is-a.dev/blog/why-I-dont-use-tmux)
- iTerm2 with tmux -CC "works great and gives native tabs and panes"; one user dropped tmux for kitty's built-in windows and tabs; another says a tiling WM and workspaces cover most multiplexer needs — [HN mirror](https://alt-hn.vercel.app/item/47752819), [Lemmy "From tmux to kitty"](https://forum.agnos.is/post/https%3A%2F%2Fslrpnk.net%2Fpost%2F18481126)
- The purist position: Alacritty's long-running tabs/splits issue #178, where commenters argue tiling "is not a feature that belongs in terminal emulator" (leave it to the WM or tmux). A 2026 HN commenter argues the reverse: window management belongs to the terminal emulator, not a multiplexer inside it — [alacritty#178](https://github.com/alacritty/alacritty/issues/178), [HN mirror 2026](https://alt-hn.vercel.app/item/47752819)
- An essay on tiling vs tabbing as rival models for window management (undated, older) — [jnrowe](https://jnrowe.github.io/articles/tiling_vs_tabbing.html)
- On Windows, PuTTY has no tabs (one process and one window per connection), so a set of wrappers grew up around it. SuperPuTTY is a GUI that opens PuTTY in tabs, MTPuTTY wraps "unlimited number of PuTTY applications in one tabbed GUI", and WinSSHTerm combines PuTTY/KiTTY, WinSCP and VcXsrv in tabs. Many of them look unmaintained — [SuperPuTTY](https://jimradford.github.io/superputty), [AlternativeTo SuperPuTTY](https://alternativeto.net/software/superputty/), [WinSSHTerm](https://en.xiaoz.org/post/11916)

### Inferences
- A tabbed ssh client with no multiplexer is a third option, and Windows users clearly want it, as the wrapper ecosystem around PuTTY shows. Tmux users will only use it if tabs coexist with tmux sessions inside them, and if a disconnect does not throw away the tab. One way to meet that is a "dead" tab with a reconnect action rather than an automatic close.
- The browser habit (one keypress, numbered tabs, instant response) is the main argument for native tabs. Latency and one-chord access matter more than features.

### Gaps
- I could not reach a canonical news.ycombinator.com thread directly (search returned only mirrors), and found no quantitative survey of tabs vs tmux usage.

## 2. Conventions carried over from browsers

### Takeaway
Users expect browser semantics: new tab, close tab, next and previous tab, select
by number, middle-click close, drag to reorder, reopen closed tab. Terminals have
to move the chords to Ctrl+Shift+… because the plain chords belong to the
programs running inside. The two contested choices are Ctrl+Tab order (MRU or
positional) and where a new tab goes. Each needs a setting, because users split
on both.

### Cited Findings
- **Ctrl+Tab MRU vs in-order**, from Windows Terminal issue #973 (opened May 2019).
  - For MRU: symmetry with Alt+Tab, long history in tabbed multi-document apps, and short-term memory. Ctrl+Shift+Tab "is still tab order, not MRU order".
  - Maintainer zadjii-msft: some users prefer positional order, so MRU needs a setting. That comment got 8 thumbs-down and 7 thumbs-up, a near-even split.
  - Resolution: PR #7952 (Oct 2020) made the tab switcher MRU, and v1.5 added `tabSwitcherMode` = `mru` | `inOrder` | `disabled`.
  - Follow-up (Jan 2021): people wanted Ctrl+Tab freed entirely for programs inside the terminal, and the switcher still hard-coded it in 1.5.
  - [microsoft/terminal#973](https://github.com/microsoft/terminal/issues/973), [v1.5 release notes mirror](https://newreleases.io/project/github/microsoft/terminal/release/v1.5.3142.0)
- MRU without a visible switcher dialog "doesn't really work" (Windows Terminal pane-navigation spec), which is why WT's MRU comes with an overlay — [WT spec #2871](https://cdn05042023.gitlink.org.cn/folkslinux/windows-terminal/src/branch/main/doc/specs/%232871%20-%20Pane%20Navigation/%232871%20-%20Pane%20Navigation.md), [Advanced Tab Switcher spec #1502](https://cdn05042023.gitlink.org.cn/folkslinux/windows-terminal/src/branch/main/doc/specs/%231502%20-%20Advanced%20Tab%20Switcher/spec.md)
- Other tabbed apps get the same MRU Ctrl+Tab request repeatedly (Royal TS, Devolutions RDM, Total Commander, Bluebeam), so it is a common expectation for remote-session managers in particular — [Royal Apps](https://community.royalapps.com/t/most-recent-tab-switching/589), [Devolutions](https://forum.devolutions.net/topics/55803/ctrl--tab-move-to-last-active-session), [Total Commander](https://www.ghisler.ch/board/viewtopic.php?p=329760)
- **New tab position.**
  - GNOME Terminal added a `new-tab-position` preference (`next` / `last`, default `last`) in Nov 2019, after a request for opening at the current position.
  - Konsole has a "New tab behavior" option (end or after current), and a regression in it was treated as a bug worth fixing.
  - Firefox's default is "relatedAfterCurrent".
  - [gnome-terminal commit](https://mail.gnome.org/archives/commits-list/2019-November/msg06319.html), [gnome-terminal#181](https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/181), [Konsole D20836](https://phabricator.kde.org/D20836?id=57025), [MDN newTabPosition](https://developer.mozilla.org/docs/Mozilla/Add-ons/WebExtensions/API/browserSettings/newTabPosition)
- **Working directory of a new tab (OSC 7).**
  - The convention comes from macOS Terminal. Once the shell reports OSC 7, new tabs start in that directory (WezTerm).
  - Stock bash does not emit it, so the terminal needs shell integration (VTE ships a PROMPT_COMMAND script) or a /proc fallback. xfce4-terminal reads /proc and its bug notes limitations; Roost reads /proc with no shell config.
  - Caveat: if the active tab is ssh'd into a remote host, a new local tab opens in the local directory, not the remote one.
  - [WezTerm shell integration](https://wezterm.org/shell-integration.html), [Roost cwd tracking](https://charliek.github.io/roost/guides/cwd-tracking/), [xfce bug 13902](https://bugzilla.xfce.org/show_bug.cgi?id=13902), [GNOME bug 697475](https://bugzilla.gnome.org/show_bug.cgi?id=697475)
- **Reopen closed tab (Ctrl/Cmd+Shift+T).** Requested repeatedly, mostly to get back lost scrollback rather than the directory.
  - iTerm2: #9890 asks for it "to get back the log history you just lost"; #2877 is an older request.
  - Konsole: bug 419501, "UNDO feature for closed tabs" (2020).
  - kitty: #1197 asks for Cmd+Shift+T after an accidental Cmd+W.
  - Warp ships it: recently closed tabs can be reopened for up to 60 seconds.
  - [iTerm2#9890](https://gitlab.com/gnachman/iterm2/-/issues/9890), [iTerm2#2877](https://gitlab.com/gnachman/iterm2/-/issues/2877), [KDE 419501](https://bugs.kde.org/show_bug.cgi?id=419501), [kitty#1197](https://www.Github.com/kovidgoyal/kitty/issues/1197), [Warp tabs docs](https://docs.warp.dev/terminal/windows/tabs/)
- Ctrl+Shift+T as the default new-tab key in gnome-terminal is confirmed by Launchpad reports — [LP 182418](https://launchpad.net/bugs/182418)

### Inferences
- Default Ctrl+Tab to positional order with an MRU option, or the reverse with an overlay. Either way, the binding must be removable so the key reaches the program inside.
- Reopening a closed *ssh* tab is cheap to offer (reconnect to the same host/profile) and maps onto the scrollback-loss complaint if the closed tab's scrollback is kept briefly, as Warp does for 60 s.
- New tabs ought to inherit the remote cwd when the active tab is an ssh session (a new channel on the same connection, cd to the OSC 7 path). The local-terminal ecosystem cannot do that. This is my inference; I found no source discussing it.

### Gaps
- I found no sources specifically on middle-click close, double-click rename or tear-off as complaints. They are present in WT, GNOME Terminal and others, but I found no citations for users demanding them. Alt+1..9 colliding with readline (Alt+digit is readline's numeric argument) was not found in a citable tracker in this pass.

## 3. Recurring complaints

### Takeaway
The biggest recurring complaints are:
- shortcuts that steal keys from vim, emacs and readline (Ctrl+PgUp/PgDn, Ctrl+Tab), hard-coded and impossible to unbind
- no indication of which background tab had output, a bell, or a finished job
- titles that do not tell you which host or directory a tab is
- getting the close confirmation wrong, in either direction
- losing tabs on close or reboot
- no way to color-code production hosts

### Cited Findings
- **Key collisions.**
  - gnome-terminal hard-coded Ctrl+PgUp/PgDn for tab switching, and the bindings did not even appear in the Shortcuts settings, so vim users could not get them back (Debian #747242, 2014).
  - Red Hat 1268255: they are captured "even with a single tab open".
  - Gentoo 142117 (2006): Vim's Ctrl+PgUp/PgDn breaks.
  - xfce4-terminal suppressed the keys even when the shortcut was disabled.
  - Ctrl+Tab was not bindable in gnome-terminal (issue 6356).
  - [Debian 747242](https://lists.alioth.debian.org/pipermail/pkg-gnome-maintainers/2014-May/110707.html), [RH 1268255](https://bugzilla.redhat.com/show_bug.cgi?id=1268255), [Gentoo 142117](https://bugs.gentoo.org/142117), [xfce 10469](https://bugzilla.xfce.org/show_bug.cgi?id=10469), [gnome-terminal#6356](https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/6356), [vim Debian 746491](https://lists.alioth.debian.org/pipermail/pkg-vim-maintainers/2015-August/009673.html)
- **Activity, bell and "which tab needs me".**
  - Konsole has "Monitor for activity/inactivity".
  - gnome-terminal users have requested it for years (Launchpad 392175, GNOME issue 6422, Bugzilla 132173).
  - xfce4-terminal changes the tab label color when a background job produces output.
  - Ghostty has `activity-monitor` and `activity-monitor-threshold`.
  - A Windows Terminal issue asks for a bell-style tab indicator that "stays until the user activates" the tab.
  - tmux's monitor-bell / window-bell flags are the model people cite.
  - [LP 392175](https://bugs.launchpad.net/gnome-terminal/+bug/392175), [gnome-terminal#6422](https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/6422), [xfce 15939](https://bugzilla.xfce.org/show_bug.cgi?id=15939), [microsoft/terminal#20014](https://github.blesdmm.dns-dynamic.net/microsoft/terminal/issues/20014), [TermFlow notifications](https://llm4s.github.io/termflow/cookbook/notifications.html)
- **New 2025–26 driver: AI agents in tabs.**
  - A Cursor forum request: with several CLI sessions open in Warp, iTerm or Ghostty, "there's no way to see which one needs attention without focusing each tab". It asks for idle / working / needs-approval in the tab title, as Codex does.
  - Similar requests are filed against Claude Code, and a Konsole "attention router" tool exists for agents.
  - [Cursor forum](https://forum.cursor.com/t/cli-show-idle-working-needs-approval-in-the-terminal-tab-title-like-codex/169352), [claude-code#36850](https://github.com/anthropics/claude-code/issues/36850), [konsole-pal](https://pypi.org/project/konsole-pal/)
- **Useless titles.**
  - The title is "bash" or the program name unless the shell sets OSC 0/2, so users add PROMPT_COMMAND hacks or wrap `cd` to put the directory in the tab title.
  - Over ssh, the remote shell's title (often user@host:path) replaces the local one.
  - [makandra card](https://makandracards.com/makandra/21405-krisleech-wisper/previous?read=true), [WezTerm shell integration](https://wezterm.org/shell-integration.html)
- **Close confirmation, too many vs too few.**
  - Ghostty's `confirm-close-surface` asks only when a process is running. Without shell integration it cannot tell, so it always asks; it can also be set to always or never.
  - Konsole asks only when a non-shell process is in the foreground. Background jobs at a prompt do not trigger it.
  - Konsole users asked for GNU screen to be excluded from the prompt (bug 337166) and for the redundant "close current tab" button to go when there is only one tab (D23146).
  - A "do not ask again" option needs a way back (KDE 322230).
  - Windows Terminal's separate "close all tabs?" prompt is toggleable.
  - Unix.SE discusses how a terminal can tell whether closing is safe (foreground process group vs shell).
  - [Ghostty config](https://mintlify.wiki/ghostty-org/ghostty/config/terminal), [KDE 337166](https://bugs.kde.org/show_bug.cgi?id=337166), [KDE D23146](https://phabricator.kde.org/D23146), [KDE 322230](https://bugs.kde.org/show_bug.cgi?id=322230), [NinjaOne WT](https://www.ninjaone.com/videos/windows/how-to-enable-or-disable-do-you-want-to-close-all-tabs-in-windows-terminal/), [Unix.SE 703943 mirror](https://wiki.neonvagabond.xyz/content/unix.stackexchange.com_en_all_2024-05/questions/703943/how-can-the-terminal-emulator-tell-whether-it-s-safe-to-close-the-window-or-it)
- **Session restore.**
  - Windows Terminal's `firstWindowPreference: persistedWindowLayout` (Preview 1.12, Oct 2021) restores windows, tabs, panes and profiles but not pane contents.
  - A 2026 PR notes WT cannot restore window geometry without also restoring all tabs.
  - Ghostty has a session-manager discussion (#3358), kitty #1197 asks for session save and restore, and WindTerm users ask for it too.
  - [MS Learn startup settings](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/startup), [WT 1.12 blog](https://devblogs.microsoft.com/commandline/windows-terminal-preview-1-12-release/), [WT PR #20283 mirror](https://gh.r-mj.com/microsoft/terminal/pull/20283), [ghostty#3358](https://github.com/ghostty-org/ghostty/discussions/3358), [WindTerm#1126](https://www.github.com/kingToolbox/WindTerm/discussions/1126)
- **Per-host tab colors.**
  - gnome-terminal issue 142 asks for tab header color settable by control code, as iTerm2 allows, with a red tab for production as the use case.
  - GNOME Console #162 asks for a different header-bar color per ssh host.
  - Terminator and Launchpad carry old per-tab color-profile requests.
  - Windows Terminal users set `tabColor` per ssh profile, e.g. red for prod.
  - Workarounds wrap ssh to change background color by host regex.
  - Royal TS colors tabs per connection or folder.
  - [gnome-terminal#142](https://gitlab.gnome.org/GNOME/gnome-terminal/issues/142), [GNOME Console#162](https://gitlab.gnome.org/GNOME/console/-/issues/162), [bitExpert WT config](https://blog.bitexpert.de/blog/windows_terminal_config), [sshw](https://github.com/akx/sshw), [LP 1338976](https://bugs.launchpad.net/bugs/1338976), [Royal TS](https://support.royalapplications.com/support/discussions/topics/17000015003), [Colored SSH terminals blog](https://michaelmior.is-a.dev/blog/coloured-ssh-terminals/), [zpl.fi](https://zpl.fi/distinguish-local-and-remote-terminals/)
- **Vertical space.** Tabs "steal a bit of screen real-estate", which is a reason people give for tmux's one-line status bar — [dev.to](https://dev.to/thermatix/devs-why-do-you-use-terminal-tabs-over-tmux-windows--51hb)
- **Accessibility.**
  - GNOME Terminal tab labels could not be focused by keyboard, and Orca read tab labels only while cycling, not on window focus (fixed).
  - GNOME Console with Orca reads "GtkStackPagePanel GtkStackPagePanel KGX Terminal" junk on focus.
  - Windows Terminal published an a11y plan in 2023.
  - [GNOME bug 746665](https://bugzilla.gnome.org/show_bug.cgi?id=746665), [GNOME Console#244](https://gitlab.gnome.org/GNOME/console/-/issues/244), [WT a11y 2023](https://cdn05042023.gitlink.org.cn/folkslinux/windows-terminal/src/branch/main/doc/terminal-a11y-2023.md)

### Inferences
- Every tab shortcut must be rebindable and removable, and none should be active with only one tab. This is the single most repeated complaint over 20 years.
- For an ssh client, the tab label should default to something the client knows: profile name or host, plus the OSC title. It should not rely on the remote shell setting one.
- Close confirmation should follow the foreground process group (for local tabs) or "connection is open" (for ssh tabs), with always/never overrides.

### Gaps
- HiDPI and Wayland/GTK CSD tab-bar complaints were not reached within the tool budget. The existing terminal-survey.md may cover them per product.
- There is no data on how many tabs typical users keep open.

## 4. Recurring feature requests across trackers

### Takeaway
The requests that recur on many trackers:
- session restore after reboot
- reopen closed tab
- activity and bell indicators
- per-tab color
- an MRU switcher or tab search
- vertical tabs (Windows Terminal #16387, which maintainers called sensible)

### Cited Findings
- Vertical tabs, Windows Terminal #16387: a follow-on to #835, with a proposal to group tabs by profile. Maintainers called it sensible and proposed a setting — [microsoft/terminal#16387](https://www.github.com/microsoft/terminal/issues/16387)
- Advanced tab switcher / tab search (WT spec #1502) shipped as the MRU overlay with a search field — [spec](https://cdn05042023.gitlink.org.cn/folkslinux/windows-terminal/src/branch/main/doc/specs/%231502%20-%20Advanced%20Tab%20Switcher/spec.md)
- Session restore, reopen closed tab, activity monitor and tab color are cited in §2–3 above.

### Inferences
- For puritty the Windows audience (PuTTY/MobaXterm users) will expect a saved-session list and per-session tab color more than vertical tabs.

### Gaps
- No ranked list of upvotes across trackers. Pinned tabs and tab groups were not found as terminal requests in this pass.

## 5. User studies, surveys, popular posts

### Takeaway
I found no formal user study of terminal tab workflows. The evidence is discussion
threads (dev.to 2018–2020, r/tmux and r/neovim 2025, HN mirrors 2026) and issue
reaction counts. The nearest thing to data is WT #973's even 8/7 split on MRU.

### Cited Findings
- [dev.to 2018 thread](https://dev.to/thermatix/devs-why-do-you-use-terminal-tabs-over-tmux-windows--51hb); [r/neovim "To tmux or not to tmux" 2025](https://pol1.lr.ggtyler.dev/r/neovim/comments/1ix114b/to_tmux_or_not_to_tmux); [r/neovim "You might not need tmux" Aug 2025](https://redlib.hackliberty.org/r/neovim/comments/1mexqxf/you_might_not_need_tmux/n6cvd9q/?context=3); [microsoft/terminal#973 reactions](https://github.com/microsoft/terminal/issues/973)

### Gaps
- There is no published survey. The State of Developer Ecosystem surveys were not checked for terminal or tmux questions.

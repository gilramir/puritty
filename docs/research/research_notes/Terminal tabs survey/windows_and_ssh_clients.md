# Tabs in Windows terminals and tabbed ssh clients (survey, 2026-11-11)

Scope: Windows Terminal, MobaXterm, SuperPuTTY, MTPuTTY, KiTTY, Tabby, Termius, ConEmu/Cmder, Xshell, SecureCRT, Royal TS. Each entry covers what the client does with tabs and what users say about them, so puritty can decide what its own local tabs must do. Reaction counts are GitHub 👍 counts, read through `gh api` on 2026-11-11.

**Method caveat:** Reddit could not be reached from this session. reddit.com's JSON returned no data, mirror fetches were refused by the sandbox, and `site:reddit.com` web searches returned only aggregator sites. The sentiment below therefore comes from GitHub issue reactions, vendor changelogs, review sites (G2, Capterra, Zoftwarehub) and secondary mirrors. See Gaps.

## Tab features per client

### Takeaway
Two groups of clients emerge. The ssh-first clients are MobaXterm, SecureCRT, Xshell, Royal TS and Termius. They all treat a tab as an instance of a *saved session*, and they all have:
- a session tree with folders that can open many sessions at once;
- duplicate/clone;
- reconnect from the tab, with the disconnected state shown on it;
- broadcast typing to many sessions.

Windows Terminal and Tabby are terminal-first. They have strong tab mechanics (tear-out, reorder, colour, rename, restore), but Windows Terminal has a weak host list, and its broadcast stays inside one tab's panes. The PuTTY wrappers (SuperPuTTY, MTPuTTY) give tabs and send-to-many, and are stagnant. KiTTY has no tabs at all.

### Cited Findings

**Windows Terminal (stable v1.25.3131.0 and preview v1.26.3133.0, both released 2026-11-11 — `gh api repos/microsoft/terminal/releases`)**

Tab actions:
- Tab actions are `closeTab`, `closeOtherTabs`, `closeTabsAfter`, `duplicateTab` (default Ctrl+Shift+D), `newTab`, `nextTab`/`prevTab`, tab search, `switchToTab`, `renameTab`, `openTabRenamer`, `setTabColor`, `openTabColorPicker` and `moveTab`. — [WT Actions docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions)
- `nextTab`/`prevTab` take `tabSwitcherMode`: `"mru"`, `"inOrder"` or `"disabled"`. — [WT Actions docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions)
- `moveTab` takes a `window` parameter that accepts `"new"` or a window ID/name, so a tab can be moved to another window by keyboard. — [WT Actions docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions)

Broadcast and restart:
- `toggleBroadcastInput`: "all input sent to the pane will be sent to all panes in the same tab". It does not reach other tabs. — [WT Actions docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions)
- `restartConnection` restarts the pane's commandline, "especially useful for scenarios like `ssh`, where you might want to restart a connection without closing the pane." — [WT Actions docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions)

Tab-row settings:
- `tabWidthMode` accepts `equal`, `titleLength` or `compact` (inactive tabs shrink to their icon).
- `newTabPosition` accepts `afterLastTab` or `afterCurrentTab` (Preview).
- `confirmCloseAllTabs` defaults to true.
- `alwaysShowTabs` and `showTabsFullscreen` control when the tab row shows.
- All of these are from [WT Appearance docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/appearance).

New-tab menu and ssh profiles:
- The `newTabMenu` dropdown can hold folders (the docs' example is an "ssh" folder of host profiles), separators, `matchProfiles` and `remainingProfiles`. This is the nearest WT has to a host list. — [WT Appearance docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/appearance)
- A dynamic profile generator, `Windows.Terminal.SSH`, generates profiles from ssh config. — [WT startup docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/startup)
- That generator is thin: #9031 "Auto generate profile from .ssh/config" (7 👍, closed 2021), #15007 "Finish the SSH profile generator" (closed 2023-03), and #19555 "Add support for includes in SSH profile generator" (open, 2025-11). — `gh api` on microsoft/terminal

Session restore:
- `firstWindowPreference: "persistedWindowLayout"` saves the window layout on close and restores it. 1.21 added restoring the screen contents. — [WT startup docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/startup); [1.21 release notes](https://github.com/microsoft/terminal/releases/tag/v1.21.1272.0)

**MobaXterm (latest 26.6, 2026-10-25)**

Tabs and keys (all from the [MobaXterm documentation](https://mobaxterm-en.mobatek.net/documentation.html)):
- Keys: Ctrl+Alt+T opens a new local terminal, Ctrl+Shift+Q quick-connects, Ctrl+Shift+U duplicates the tab, Ctrl+Alt+Q closes it.
- Detach and reattach go through the tab's right-click menu or Ctrl+Shift+D.
- A tab's icon shows "a blue dot if some activity is detected".
- Switching: Ctrl+Tab and Ctrl+Shift+Tab, Ctrl+Alt+←/→, and Ctrl+Alt+F<n> for tab n.
- `MobaXterm.exe -newtab` opens a tab in the running instance.

Split, MultiExec and session folders (same docs):
- The "Split" button cycles between "multitab", "2-terminals" and "4-terminals" modes, also bound to Ctrl+Alt+1/2/3/4.
- "MultiExec" displays all terminals and writes typed commands to all of them.
- "Right-clicking on a session folder allows you to launch many sessions at once."
- "Display reconnection message at session end" asks whether to restart the session.
- "Lock terminal title" sets the title to the session name.

Changelog items about tabs (all from the [MobaXterm changelog](https://mobaxterm-en.mobatek.net/download-home-edition.html)):
- Each tab has a colour. 23.1 fixed "the tab color selection button was hardly visible when the tab color was white". 26.0 matched the "Reattach tab" button colour to the current tab colour.
- Tab text turns red for a disconnected or inactive state. 26.1 fixed "tab text remained red after selecting and unselecting an inactive tab", and 26.6 fixed a reconnected RDP tab's title no longer turning red.
- 23.4 made the tab bar scroll with the mouse wheel and let tabs be pinned to the left. That is how it handles overflow.
- 24.2 added right-click actions in MultiExec to activate or deactivate all terminals and to synchronize scrolling.
- 24.3 added "close all inactive tabs".
- 24.4 added "Close all tabs to the left/right" and a shortcut for "Rename tab".
- 26.1 added dots in the session tree that mark which sessions are open; clicking one jumps to its tab.
- 26.1 also made tab switching faster.

A user notes that MultiExec includes all open tabs by default, with a checkbox to exclude one. — [SO mirror via search](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/tagged/mobaxterm_page=11) (old mirror; the 2024 changelog above adds activate/deactivate-all).

**SecureCRT (VanDyke)**
- Tabs arrived in 5.0. Dragging tabs between windows, "Send to New Window" and "Clone to New Window" arrived in 6.0. Since 6.7 a tab double-click can be mapped to send or clone. — [VanDyke tip](https://vandyke.com/support/tips/dragouttabs.html)
- Global tab options set status-indicator colours for connected, disconnected, new input, inactivity and locked sessions, shown as tab background or a colour rectangle. There is also a "Reconnect Tab" action. — [SecureCRT help, Global Options/Terminal/Tabs](https://documentation.help/SecureCRT/GO_Terminal_Tabs.htm) (via search snippet; the page itself returned 403)
- The colours above are status colours, not per-session tab colours. I found no per-session tab colour. The workaround is a per-session colour scheme. — [VanDyke colour tip](https://vandyke.com/support/tips/colorconfig.html)
- Tab groups can be tiled left-to-right or top-to-bottom, and tabs move between groups. — [VanDyke video page](https://www.vandyke.com/products/securecrt/securecrt-video.html)
- The Command window (called "Chat window" before 7.2) sends to all connected sessions, all visible sessions or selected tab groups (9.6.2). Locked sessions are skipped. — [filehorse SecureCRT changelog](https://mac.filehorse.com/download-securecrt); [VanDyke chat tip](https://www.vandyke.com/support/tips/chatsendcom.html)
- The Session Manager has folders, and "all sessions in a particular group may be opened and manipulated at once." — [VanDyke session management](https://vandyke.com/products/securecrt/session_management.html)
- 9.0 (2021) gave each tab its own font, character encoding and zoom, and added a "Reuse disconnected tabs" option. — [SecureCRT 9.0 history](https://www.vandyke.com/download/securecrt/9.0/history.txt)

**Xshell (NetSarang)**
- Each tab belongs to a tab group, and a window holds several groups. The docs have pages for Split and Merge Tabs, Arrange Tabs and a Tab Manager tree. — [Xshell Tab Management](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/2237304945/Tab+Management)
- Within a group only one tab shows at a time, and with many sessions in one group some tabs are hidden from view. — [Xshell Tab Group](https://netsarang.atlassian.net/wiki/spaces/EN8/pages/2237304981/Tab+Group) (via search snippet)
- The Compose bar and Compose pane send typed input to chosen sessions. "Send Key Input to All Sessions" has a per-session Off button. 7.0 b0098 added sending from the Compose Pane to *same-coloured tabs*, and a later 7.0 build added sending only to connected sessions. — [NetSarang KB](https://netsarang.atlassian.net/wiki/x/HoKsQg); [Softpedia Xshell changelog](https://www.softpedia.com/progChangelog/Xshell-Changelog-23416.html)

**Termius**
- Ctrl/Cmd+T opens a New Tab. Dragging one connection onto another's tab creates a "workspace" in Split view (up to 16 terminals), and Ctrl/Cmd+Shift+M toggles it with Focus mode. — [Termius workspaces docs](https://docs.termius.com/terminal/workspaces)
- Broadcast sends to "all active terminals in the workspace" (Ctrl+Alt+B).
- Workspace templates save connections, tab names, layout, working directories and running commands, and a grey dot marks unsaved changes.
- "Rename" on a tab "does not change the original hostname".
- Tab status colours: green means unread output, yellow means input is needed, red means an error or failed connection.
- (The last four items are from the same [Termius workspaces docs](https://docs.termius.com/terminal/workspaces).)
- Workspaces arrived in 9.21.2, and 9.22.0 (June 2025) lets snippets run on several targets in a separate tab. — [Termius changelog](https://docs.termius.com/changelog)

**Tabby (formerly Terminus; v1.0.238, 2026-10-07; 75k stars)**
- The README lists "Tabs on any side of the window", "Multiple nested split panes", "Remembers your tabs", an "SSH2 client with a connection manager", and "Neither is it lightweight". — [Tabby README](https://github.com/Eugeny/tabby)
- 1.0.206 made the behaviour on disconnect configurable (close, keep or reconnect, #8206) and added a hotkey to reconnect the current tab (#8201). — [Softpedia Tabby changelog](https://www.softpedia.com/progChangelog/Terminus-Pankov-Changelog-257708.html)
- A third-party plugin, tabby-tmux-restore, re-attaches tmux sessions after an ssh reconnect. — [plugin README](https://cdn.jsdelivr.net/npm/tabby-tmux-restore@1.3.1/README.md)

**ConEmu / Cmder**
- Tab captions come from templates or a manual rename (Apps+R). Since build 170805 a double-click on a tab renames it by default. — [ConEmu TabBar](https://conemu.github.io/en/TabBar.html); [ConEmu blog build 170805](https://conemu.github.io/blog/page9)
- Splits and grids can be made with `-new_console:s` switches. — [NewConsole](https://conemu.github.io/en/NewConsole.html)
- "Tasks" are named commands, and they are "the only easy way to run several tabs or preconfigured splits at once". — [Tasks](https://backiee.wasmer.app/https_conemu_github_io/en/Tasks_html) (mirror)
- The tab menu has "Unfasten", which moves the tab to a new ConEmu window, and "Detach", which separates the console from ConEmu. — [ConEmu notes wiki](https://raju.shoutwiki.com/wiki/Conemu_notes)
- The last GitHub release is v23.07.24 (2023-07-24). — `gh api repos/ConEmu/ConEmu/releases`
- Cmder is a ConEmu bundle, and I found no tab features of its own. See Gaps.

**SuperPuTTY**
- A docking UI hosts PuTTY or KiTTY windows as tabs, with "layouts". — [SuperPuTTY site](https://jimradford.github.io/superputty)
- The last release is 1.5.0.0 (2023-01-29). The repo has 362 open issues, and its last push was 2026-04-14. — `gh api repos/jimradford/superputty`
- Issue #656 "Restart all sessions with one click" is closed. Issue #408 "Shortcut to restart a session in an active tab" is open (2015), as is #602 "Force session to open in new tab via CLI". — `gh api`
- Its top issues are dark mode (#759, 14 👍) and focus and Alt+Tab problems (#747 "freezes … keyboard stops working until I press ALT", 7 👍; #809 Alt+Tab, 4 👍; #941 "Clicking on window does not bring superputty to the front", 2024). These are all artefacts of re-parenting PuTTY's own windows. — `gh api` on jimradford/superputty

**MTPuTTY (ttyplus)**
- Each PuTTY session is a tab, and any tab can be detached back into a standalone PuTTY window. It can "type" a script into several tabs at once. Servers are grouped in a sidebar. The latest version is 1.8.5 beta, with no date. — [ttyplus MTPuTTY](https://ttyplus.com/?p=12); [admin-ahead forum](https://admin-ahead.com/forum/general-discussion/multi-tabbed-putty-mtputty/)

**KiTTY (PuTTY fork)**
- KiTTY has no tabs. Its README lists a sessions filter, a session launcher, a per-session icon, send-to-tray and "quick start of a duplicate session". — `gh api repos/cyd01/KiTTY/readme`
- The last release is v0.76.1.13 (2023-09-17). — `gh api repos/cyd01/KiTTY/releases`
- Users get tabs by wrapping KiTTY: issue #420 "Integrating in ConEmu, to get Titty (Tabbed Kitty)", issue #514 "Issue with Multi Tab Putty", and SuperPuTTY lists KiTTY support. — `gh api` search on cyd01/KiTTY; [Softpedia SuperPuTTY](https://www.softpedia.com/get/Network-Tools/Telnet-SSH-Clients/SuperPutty.shtml)

**Royal TS**
- Each connection gets a tab, and tabs can be grouped. Dragging the tab of an external-app connection (PuTTY, VNC) needs Shift held down. — [Royal TS panels and tabs](https://docs.royalapps.com/r2023/royalts/getting-started/panels-and-tabs.html) (via search snippet)
- Each object has a colour, shown "in the navigation tree, the connection tab or as connection border". — [Royal TS features](https://royalapps.com/ts/win/features-all)
- The terminal plugin is PuTTY-based, updated to PuTTY 0.84 (2026-05-22), and stores its settings in the document. — [Royal TS PuTTY plugin](https://docs.royalapps.com/r2023/royalts/reference/connections/terminal-putty.html); [release notes](https://www.royalapps.com/go/kb-ts-win-v7-releasenotes)
- A vendor reply says its UI framework "doesn't allow us to create tab groups like in mRemote." — [Royal community thread](https://community.royalapps.com/t/folder-name-in-tab-title/530) (via search snippet)

### Inferences
- **Common floor among ssh-first clients:**
  - a tab is opened from a host tree or quick-connect;
  - duplicate/clone tab;
  - reconnect in place, keeping the tab;
  - a visible disconnected state (red text in MobaXterm, a status colour in SecureCRT, a red dot in Termius);
  - rename that does not rename the host;
  - opening every session in a folder;
  - broadcast input to a chosen subset.
- Puritty lacks most of these today, outside tmux -CC.
- **Broadcast scope differs and matters.** Windows Terminal broadcasts to the panes of one tab only. SecureCRT targets tab groups or all connected sessions. Xshell targets tabs of the same colour or connected sessions only. MobaXterm targets all tabs, with per-tab exclusion. Termius targets the workspace. Selecting targets by colour or group (Xshell, SecureCRT) fits a user with "prod in red" hosts.
- **Two kinds of tab colour:** a per-host colour (MobaXterm, Royal TS, WT `tabColor`) and a status colour (SecureCRT, Termius). SecureCRT's users have to fake per-host colour with colour schemes.
- Wrapper tools that re-parent another process's window (SuperPuTTY, MTPuTTY, Royal TS with PuTTY) keep producing focus, Alt+Tab and drag bugs. A built-in ssh client avoids that whole class.

### Gaps
- Exact current SecureCRT 9.x tab options. The documentation.help page returned 403, so the findings rely on search snippets and older help.
- MobaXterm's tab-colour setting is confirmed by the changelog, but no official doc says where it is set. A 2023 Reddit mirror says Bookmark settings.
- Royal TS has no confirmed "open all in folder" action.
- I found no Cmder-specific tab features.
- Xshell 8's tab colour and detach behaviour was not confirmed beyond the 7.0 changelog.

## What users praise and complain about

### Takeaway
On Windows Terminal's tracker, tab mechanics drew the largest demand early: open a tab in the same directory, tear-out, start with multiple tabs, rename, reorder, persist/restore. Almost all of it shipped by 2023–24. What is still open is tab-to-pane drag, tab-row position, background-activity indicators, focus bugs, and tmux control mode, which is puritty's existing angle. Tabby's top tab complaints are tear-out (open since 2018) and a 2026 regression that left tabs blank. Users of the ssh-client group complain mostly about cost or limits and about weight, not about tab design.

### Cited Findings

Windows Terminal: the tab issues with the most 👍 (`gh api` search on microsoft/terminal, 2026-11-11):

| issue | 👍 | state | what it asks |
|---|---|---|---|
| #3158 | 535 | closed | "Open new terminal tab in same directory as existing tab (OSC 7?)" |
| #1256 | 326 | closed 2023-03-30 | "Add support for tab tearoff and tab merge"; shipped in Preview 1.18 ([devblog](https://devblogs.microsoft.com/commandline/windows-terminal-preview-1-18-release/)) |
| #766 | 254 | closed 2021-09 | "Enable Terminal to persist / restore instance settings" |
| #3656 | 223 | open since 2019 | "Add support for `tmux` Control Mode" |
| #756 | 187 | closed | "Start with multiple tabs open" |
| #961 | 178 | closed 2024-03 | "Restore previously closed session's state (Buffer contents)" |
| #2634 | 141 | closed 2023-07 | "Support broadcast input?" |
| #1000 | 140 | open | "Scenario: Add support for panes" (umbrella issue) |
| #1079 | 92 | closed | "Ability to rename Tab title at runtime" |
| #4587 | 91 | open | "Drag & Drop Tabs to create a Pane" |
| #564 | 88 | closed | "Use tab-bar/title bar for dragging window around" |
| #835 | 85 | open since 2019 | "Enable customization for tabs on bottom/right/left" |
| #13388 | 62 | open | "Cannot type in new pane or tab until focus is manually activated with mouse click" |
| #7955 | 62 | open | "terminal activity indicator/alert when in background" |
| #2976 | 49 | open | "Customize confirmation prompt before exit" |
| #6549 | 48 | open | "Prompt before closing pane with multiple client apps" |
| #3726 | 47 | closed 2023-04 | "keybinding to restart/reload a tab" |
| #443 | 47 | closed | "Add support for tab reordering" |
| #3335 | 45 | closed | "Setting to hide/remove close ('x') button from tabs" |
| #6878 | 27 | closed 2020 | "Allow per-profile default tab colors" |
| #9470 | 26 | closed 2021 | "Option to confirm before closing a tab" |
| #771 | 25 | closed | "The default 'active' tab contrast is very low" |

- The non-draggable tab/title bar was "the #1 complaint from early testers" (2019). — [WT #1375](https://www.github.com/microsoft/terminal/issues/1375)
- Tear-out bugs continued after it shipped: in #18561 (2025) dragging a tab out of the window closed Terminal (closed 2025-03-31), and #12616 asks for padding in the tab well so the window can still be dragged. — [#18561](https://github.looper.workers.dev/microsoft/terminal/issues/18561); [#12616](https://www.github.com/microsoft/terminal/issues/12616)
- #17211, a later fix: "Terminal will no longer try to remember tabs even after you tell it not to". — [WT releases](https://github.com/microsoft/terminal/releases)
- A reported ssh defect: "Windows terminal tab freezes when ssh is disconnected within WSL" (#10183, 2021, closed). — `gh api`

Tabby: the tab issues with the most 👍 (`gh api` on Eugeny/tabby):
- #581 "Drag Tabs to New Window": 54 👍, **open since 2018**. #4264 "Detachable tabs": 6 👍, open.
- 2026 regression: #11225 "Tabs become black after revisiting them…" (24 👍), #11213 "Terminal pane goes blank after switching between SSH tabs on Windows 11 (v1.0.232)" (23 👍) and #11231. All were closed by May 2026.
- Open requests:
  - #514 new tab in the same folder (9 👍, 2018);
  - #8157 "open several profiles simultaneously" (14 👍);
  - #9909 "Open pre-defined group of tabs on startup" (4 👍);
  - #10978 "Tab closure on disconnect" (2026);
  - #11000 "Cannot disable close confirmation for local tabs with running processes" (2026);
  - #9961 MRU tab cycling.
- Weight: one user reports ~1 GB for 3–4 tabs. Another says scrolling settings "feels like 30fps at best". An r/unix user dropped it on noticing it was slow. — [lemm.ee comment](https://lemm.ee/post/42238371/14791668); [itsfoss](https://itsfoss.com/news/tabby.md); [r/unix mirror](https://pol1.lr.ggtyler.dev/r/unix/comments/1k5t4d4/does_anyone_use_electron_based_terminal_emulators)
- Praise: users like its ssh, its SFTP browsing and remembered tabs, and call it "easier and more smoother … than PuTTY". — [AlternativeTo Tabby](https://alternativeto.net/software/terminus/)

ConEmu:
- #346 "Drag Tabs to New Window": 24 👍, open since 2015.
- #1661 "Tab bar dark theme": 22 👍, open.
- #552 "Active tab is hard to see": 21 👍, closed.
- #578 "tmux integration": 29 👍, open.
- (All from `gh api` on ConEmu/ConEmu.)

MobaXterm:
- Praise: "a GUI for multiple sessions"; the ability to "manage more (servers, tabs)". — [G2 MobaXterm](https://www.g2.com/products/mobaxterm); [Gartner Peer Insights](https://external.pi.gpi.aws.gartner.com/reviews/market/it-infrastructure-and-iot/vendor/mobatek)
- Complaints:
  - The Home edition caps saved sessions at 12 (plus 2 tunnels and 4 macros), and one reviewer called the cap "frustrating".
  - It may crash with many active sessions, and the interface is "dated".
  - The SFTP side panel does not always follow the terminal's folder.
  - It runs only on Windows.
  - Sources: [ctrlops](https://ctrlops.io/blog/best-ssh-clients-windows); [fitgap](https://us.fitgap.com/products/016680/mobaxterm); [tech.scargill.net](https://tech.scargill.net/?p=9979); [Zoftwarehub](https://zoftwarehub.com/products/mobaxterm/reviews); [Capterra](https://capterra.com/p/209929/MobaXTerm/); [G2](https://www.g2.com/products/MobaXTerm/reviews)
- The changelog shows recent tab fixes for performance and red-text state, which suggests users with many tabs pushed on those. — [MobaXterm changelog](https://mobaxterm-en.mobatek.net/download-home-edition.html)

SecureCRT, Termius and Royal TS:
- SecureCRT is "the gold standard for serious network engineers", but costs about $119. G2 says SecureCRT is easier to administer and MobaXterm easier to do business with. — [jpptechnology](https://jpptechnology.com/blog/best-ssh-clients-network-engineers/); [fitgap PuTTY alternatives](https://us.fitgap.com/products/017896/putty/alternative); [G2 compare](https://www.g2.com/compare/mobaxterm-vs-securecrt)
- Termius is "the most polished cross-device option", but on paid tiers credentials sync to Termius servers. — [thebackroomtech](https://thebackroomtech.com/best-ssh-clients-terminal-managers-sysadmins/)
- Royal TS: one user asked for the folder name in tab titles, so that same-named hosts in different folders can be told apart. — [Royal community #530](https://community.royalapps.com/t/folder-name-in-tab-title/530)

### Inferences
- Windows Terminal's demand ranks the features as: (1) open a new tab where the current one is (OSC 7), (2) tear-out and merge, (3) restoring tabs and their buffers, (4) broadcast, (5) rename, (6) per-profile colour. All are shipped there, so a PuTTY or MobaXterm refugee will take them as the baseline.
- Tear-out is the persistent open request in Tabby (2018) and ConEmu (2015). It is hard to do, and its absence is noticed.
- WT #3656 (tmux control mode, 223 👍, open since 2019) shows demand for the feature puritty already has.
- Focus-after-new-tab bugs (WT #13388) and window-reparenting focus bugs (SuperPuTTY) are a repeated irritation. Keyboard focus must land in the new tab's terminal.

### Gaps
- No direct Reddit (r/sysadmin, r/networking, r/commandline, r/windows) threads or vote counts; reddit.com was not reachable from this session. Opinions above are from review sites and mirrors.
- No vendor-forum sentiment for SecureCRT, Xshell or Royal TS was gathered beyond what is cited.

## Why PuTTY users move, and what they miss

### Takeaway
Tabs and a host list are the main reasons people leave. PuTTY's "lack of tabs … too cumbersome … with multiple sessions" is the stock complaint, and MobaXterm is the most-suggested replacement. On Windows they get MobaXterm's tree, tabs and X server, or SecureCRT's scripting. What they lose is PuTTY's lightness and freedom from a licence: MobaXterm caps the free edition, SecureCRT and Xshell cost money, Tabby is Electron, and Termius syncs credentials to the cloud.

### Cited Findings
- "PuTTY is the smoothest for SSH but the lack of tabs means it's too cumbersome for me when working with multiple sessions." — [The Register forum](https://forums.theregister.com/forum/all/2020/08/27/windows_terminal_update/) (2020)
- MobaXterm is AlternativeTo's top alternative to PuTTY Tab Manager, and is credited with a built-in X server and tabs. — [AlternativeTo](https://alternativeto.net/software/puttytabmanager)
- Comparison sites say: MobaXterm if the team is Windows-only; SecureCRT for scripting and enterprise; Termius for cross-platform and mobile; Tabby for free and open source. — [comparitech](https://www.comparitech.com/net-admin/best-putty-alternatives-ssh-clients/); [dev.to 2026 guide](https://dev.to/daxesh/putty-alternatives-for-windows-the-2026-guide-for-developers-whove-outgrown-classic-ssh-b7g)
- Costs and limits of the alternatives:
  - MobaXterm Home is capped at 12 sessions, and Professional is $69 per user. — [fitgap](https://us.fitgap.com/products/016680/mobaxterm)
  - SecureCRT starts at $119. — [fitgap](https://us.fitgap.com/products/017896/putty/alternative)
  - Tabby's README says it is not lightweight and points to ConEmu or Alacritty "if RAM usage is of importance". — [Tabby README](https://github.com/Eugeny/tabby)
- The tab wrappers have stalled: SuperPuTTY's last release was in 2023 and its window-focus bugs are still open; KiTTY's last release was in 2023 and it still has no tabs; AlternativeTo marks PuTTY Tab Manager as discontinued. — `gh api`; [AlternativeTo](https://alternativeto.net/software/puttytabmanager/about/)

### Inferences
- The gap puritty would fill is a native, light, free client whose built-in ssh tabs open from a host list, with these MobaXterm-class features:
  - duplicate;
  - reconnect-in-tab;
  - per-host colour;
  - a disconnected state on the tab;
  - open-folder;
  - broadcast to a subset.
- It should keep PuTTY's per-session settings, which matters for EUC-KR hosts. SecureCRT 9.0 made encoding per tab for the same reason ([SecureCRT 9.0 history](https://www.vandyke.com/download/securecrt/9.0/history.txt)).

### Gaps
- No sourced data on how often PuTTY users move to Windows Terminal + OpenSSH versus MobaXterm or others, and no survey numbers.
- I found no source on handling Korean/EUC-KR encoding per tab in any of these clients, other than SecureCRT's per-tab character encoding (9.0).

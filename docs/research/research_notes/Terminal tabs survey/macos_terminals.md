# macOS terminals: iTerm2 (incl. tmux -CC) and Terminal.app — tab features and user sentiment

Researched 2026-11-11. iTerm2's current stable line is **3.7.x** (3.7 announced ~Sep 2026; 3.7.7 built 2026-11-03), not 3.5/3.6 as the brief assumed; tab groups, pinned tabs and floating panes are 3.7 features. Note: several WebFetch extractions were summarized by a helper model; quotes below are as returned.

## 1. iTerm2 local tab features

### Takeaway
iTerm2 treats tabs like browser tabs (drag to reorder, drag between windows, tear off into a new window, middle-click close, Cmd-number), and layers on per-profile/per-session identity (title components, badge, icon, tab color, automatic profile switching by host) plus status indicators (activity, new-output dot, session-ended icon, progress ring, and in 3.7 a custom status subtitle/color/dot). 3.7 added Chrome-style named/colored collapsible tab groups and pinned tabs.

### Cited Findings
**Creating tabs**
- Shell > New Window/Tab uses the *default* profile; "New Window/Tab with Current Profile" uses the current session's profile; inside a tmux integration session you are asked whether the new tab is local or tmux — [iTerm2 menu items](https://iterm2.com/documentation-menu-items.html)
- Duplicate Tab "Creates another tab with the same arrangement of split panes, profile, etc." — [menu items](https://iterm2.com/documentation-menu-items.html); since 3.7.5 the duplicate opens immediately right of the original instead of at the end of the bar — [iTerm2 downloads/changelog](https://iterm2.com/downloads)
- Working directory: per profile, new sessions start in home by default, or can reuse the current session's directory, or a specified directory — [Profiles > General](https://iterm2.com/documentation-preferences-profiles-general.html) (the page as fetched did not detail the "Advanced" per-window/tab/pane split; see Gaps)
- Open Quickly (Cmd-Shift-O) can search sessions and also open new tabs — [menu items](https://iterm2.com/documentation-menu-items.html)

**Closing / confirm / undo**
- "Confirm closing multiple sessions": closing one session is unconfirmed; closing several at once (e.g. a multi-tab window) alerts. Separate "Confirm Quit" setting; an option to disable all confirmations on shutdown/logout ("could cause you to lose work") — [Settings > General](https://iterm2.com/documentation-preferences-general.html)
- Edit > Undo Close Session/Tab/Window: "you have five seconds to undo it" (timeout configurable in Profiles > Session) — [menu items](https://iterm2.com/documentation-menu-items.html). 3.7.5: with archiving profiles, undo works past the time limit and "Archived sessions come back ... in their original split panes, tabs, and windows" — [downloads](https://iterm2.com/downloads)
- Middle-click on a tab closes it — [General usage](https://iterm2.com/documentation-general-usage.html)

**Reorder, move, tear-off**
- "you can drag and drop tabs to reorder them within a window"; "You can drag tabs from one window to another"; dropping outside any tab bar makes a new window — [General usage](https://iterm2.com/documentation-general-usage.html)
- Move Tab Left/Right exist as commands; 3.7.5 changed them to move just the current tab, not its whole group; 3.7.6 fixed them unpinning a pinned tab into a group — [downloads](https://iterm2.com/downloads)
- 3.7.7 fixed tab/pane drag stutter "with many windows open when the tab bar is always shown" — [downloads](https://iterm2.com/downloads)
- Older request thread for more browser-like tab-drag conventions — [iterm2-discuss "Request: More UX conventions for tab dragging"](https://groups.google.com/g/iterm2-discuss/c/6zfcnBba0iU) (contents not fetched)

**Switching keys**
- Cmd-Left/Right and Cmd-{ / Cmd-} move among tabs; Cmd-number jumps to a tab; Cmd-Opt-number to a window; three-finger swipe selects adjacent tab; Cmd-[ / Cmd-] move among split panes "in order of use"; Cmd-Opt-Arrow moves among panes spatially — [General usage](https://iterm2.com/documentation-general-usage.html)
- "Show tab numbers": tabs show their keyboard shortcut — [Appearance](https://iterm2.com/documentation-preferences-appearance.html)
- Complaint: Ctrl-Tab cycles in an order not matching the visual tab order (issue #8219, v3.3.2, ~2019) — [GitLab #8219](https://gitlab.com/gnachman/iterm2/-/issues/8219); status not verified.

**Titles, rename, badges, icons, color**
- Title is built from selectable components: Session Name, Profile Name, Profile & Session Name, Job, User, Host, PWD, TTY; User/Host/PWD on remote hosts need Shell Integration — [Profiles > General](https://iterm2.com/documentation-preferences-profiles-general.html)
- Default tab label is the running job's name — [General usage](https://iterm2.com/documentation-general-usage.html)
- Window > Tab > Edit Tab Title takes an *interpolated string* — [menu items](https://iterm2.com/documentation-menu-items.html). Right-click "Rename Tab" only arrived in 3.7.5 — [downloads](https://iterm2.com/downloads); it had been requested years earlier ([GitLab #6022](https://gitlab.com/gnachman/iterm2/-/issues/6022)). 3.7.5 also fixed a user-set tab title being "replaced by the session's name" — [downloads](https://iterm2.com/downloads)
- "Each tab may have its own window title": whether OSC 0/2 applies to the whole window or only the sending session — [Settings > General](https://iterm2.com/documentation-preferences-general.html)
- Optional basic HTML (`<b>`,`<i>`,`<u>`) in tab titles — [Appearance](https://iterm2.com/documentation-preferences-appearance.html)
- Badge: large interpolated-string label drawn behind the text, top right, with configurable position/size/font — [Profiles > General](https://iterm2.com/documentation-preferences-profiles-general.html)
- Icon: custom, built-in per foreground app, or none; shown in tab bar and title bar — [Profiles > General](https://iterm2.com/documentation-preferences-profiles-general.html)
- View > Tab Color: "select a tint color for the tab, to make it easier to distinguish" — [menu items](https://iterm2.com/documentation-menu-items.html); 3.7.5 fixed the control sequence that resets tab color to the profile's — [downloads](https://iterm2.com/downloads)

**Indicators**
- "A blue dot means new input was received"; an activity indicator spins while output arrives; an end-of-session icon appears when the session ends — [General usage](https://iterm2.com/documentation-general-usage.html). Each indicator toggle ("Show activity indicator", "Show new-output indicator" for unseen output in non-selected tabs) is in Appearance — [Appearance](https://iterm2.com/documentation-preferences-appearance.html)
- Older (2.x) docs describe activity coloring of tab labels (new output / stale / ended-gray) — [2.1 general usage](https://iterm2.com/documentation/2.1/documentation-general-usage.html)
- A progress ring around a tab exists (3.7.5 fixed it missing on first/last tab on Tahoe) — [downloads](https://iterm2.com/downloads)
- 3.7: Claude Code session status shown "on tabs as a custom subtitle, color, and dot icon", so you see "which Claude Code instance is waiting for attention" — [AlternativeTo, 2026-09-10](https://alternativeto.net/news/2026/9/iterm2-3-7-released-with-ios-companion-app-claude-code-integration-tab-groups-and-more/); 3.7.7 fixed that status not reappearing after window restoration — [downloads](https://iterm2.com/downloads)

**Tab bar layout and overflow**
- Tab Bar Location: top, bottom, left or right; in Minimal/Compact themes top tabs go in the title bar — [Appearance](https://iterm2.com/documentation-preferences-appearance.html). With side tab bars, context menus say "New Tab Below"/"Close Tabs Below" (3.7.5) — [downloads](https://iterm2.com/downloads)
- Options: show tab bar with only one tab; stretch tabs to fill bar (default on); "Tab bar scrolls when tabs don't fit" (default on; else overflow menu), works on every edge; show tab bar in fullscreen; flash tab bar when switching in fullscreen; "Preserve window size when tab bar shows or hides"; close buttons always or on hover only — [Appearance](https://iterm2.com/documentation-preferences-appearance.html)

**Tab groups and pinned tabs (3.7)**
- Right-click > Add Tab to Group > New Group (prompts for name, suggests title, assigns color); group members "always stay contiguous"; chip menu: Rename, color swatches/picker, Duplicate Group, Move Group to New Window, Remove All Tabs from Group, Close Group; click chip to collapse (shows count), selecting a member auto-expands; works on horizontal and vertical bars; drag chip moves whole group (also between windows); name/color/collapsed state persist through arrangements and restarts — [Tab Groups doc](https://iterm2.com/documentation-tab-groups.html)
- Pinned tabs exist (3.7.7 fixed unpinning a non-rightmost pinned tab breaking the tab bar) — [downloads](https://iterm2.com/downloads)

**Split panes, broadcast, workgroups, floating panes**
- Split vertically/horizontally, each pane a session; per-pane title bars optional; dim inactive panes — [menu items](https://iterm2.com/documentation-menu-items.html), [Appearance](https://iterm2.com/documentation-preferences-appearance.html)
- Shell > Broadcast Input, incl. "Broadcast to all panes in current tab" — [menu items](https://iterm2.com/documentation-menu-items.html)
- Workgroups (3.7): a set of sessions (new tabs, splits, "peers" that switch in-place in one pane) built from one session; ordinary Cmd-T tabs are not members — [Workgroups doc](https://iterm2.com/documentation-workgroups.html)
- Floating panes (3.7.5) float over a tab's splits, saved with arrangements — [downloads](https://iterm2.com/downloads)

**Arrangements and restore**
- Window > Arrangements > Save Window Arrangement saves "all of the window's positions, tabs, and split panes"; restore (also "as Tabs"); load from file — [menu items](https://iterm2.com/documentation-menu-items.html)
- Startup policy: system restoration, only hotkey window, or open default arrangement; "Restore windows to same Spaces" — [Settings > General](https://iterm2.com/documentation-preferences-general.html)
- Restoration is still being fixed in 3.7.x (erased lines reappearing, SSH-integration hang, restoration lost on logout while Claude Code ran) — [downloads](https://iterm2.com/downloads)

**Automatic profile switching (host-dependent look)**
- Rules in Profiles > Advanced match user@, hostname, :/path, &job, with `*` wildcards; scoring (exact host 16, wildcard host 8, job 4, user 2, exact path 1); `!` makes a rule sticky, otherwise the session reverts when no rule matches "such as when an SSH session ends"; requires Shell Integration on each host (or a trigger workaround) — [Automatic Profile Switching](https://iterm2.com/documentation-automatic-profile-switching.html). The doc's example is background color/encoding changing per host; it does not explicitly mention tab color.

### Inferences
- Since tab color is a profile property and APS swaps the profile, a per-host tab tint follows from APS; puritty, owning the ssh client, knows the host without shell integration and can do this more reliably.
- The 3.7 changelog shows that tab-groups/pinning interacting with move/drag commands is a bug farm; a puritty v1 can skip groups.
- iTerm2 needed years to add right-click rename; it is cheap and expected.

### Gaps
- Could not confirm the exact current wording of the per-new-window/tab/pane working-directory "Advanced" options.
- No source fetched explicitly documenting bell/idle ("silence") alerts on tabs in current versions.
- Changelog for 3.5/3.6 tab changes not read (page too long; only 3.7.5–3.7.7 read).

## 2. iTerm2 tmux integration (tmux -CC)

### Takeaway
Each tmux window is a native tab (or window), each tmux pane a native split; native keys, scrollback, find and copy work. Pain points are concentrated in: sizes (tmux forces common size; gray gutters), close semantics (closing kills the tmux window unless you choose Hide; detach not on the close dialog), reattach state (groups lost), and many attach/hang/crash edge cases still being fixed in 2026.

### Cited Findings
- Running `tmux -CC` opens an iTerm2 window acting like a normal window; new window/tab from the tmux menu creates a tmux window; splits run `split-window` — [tmux integration doc](https://iterm2.com/documentation-tmux-integration.html)
- "Windows are never larger than the smallest attached client"; gray area right/bottom when the native window is bigger; all tmux windows/tabs have the same rows/columns — [tmux doc](https://iterm2.com/documentation-tmux-integration.html)
- "A tab with a tmux window may not contain non-tmux split panes"; "A tab with split panes may have 'empty' areas" — [tmux doc](https://iterm2.com/documentation-tmux-integration.html)
- Close: "Close a session, tab, or window: Kills the tmux session or window." Detach closes all tmux windows; `tmux -CC attach` reopens them "in the same state" — [tmux doc](https://iterm2.com/documentation-tmux-integration.html)
- Cmd-W on a tmux tab prompts kill/cancel/hide (no detach); suppressible via Advanced "Suppress kill/hide dialog when closing a tmux tab"; hidden windows are reopened from the tmux Dashboard; a user (2018) found hide+reattach from a second window gave "already attached" — [iterm2-discuss, May–Jun 2018](https://groups.google.com/g/iterm2-discuss/c/rrcj-wtsAEc). George Nachman agreed adding detach was a good idea; whether added is unverified.
- Users who expect closing a tab to keep the session are surprised (issue #9731, 3.4 nightly 2021: "Is it possible to prevent tmux session to close when I close a tab") — [GitLab #9731](https://gitlab.com/gnachman/iterm2/-/issues/9731)
- Settings > General > tmux: "When attaching, restore windows as…" (new windows vs tabs, for windows iTerm2 hasn't seen); auto-bury the client session that ran `tmux -CC`; use a "tmux" profile vs the connecting session's profile (off since 3.3); show tmux status bar content; pause panes that would take > N s to catch up (tmux ≥3.2), warn before pausing, unpause automatically — [Settings > General](https://iterm2.com/documentation-preferences-general.html)
- Dashboard opens for sessions with many windows (option); 3.7 adds "Open tmux windows and tabs in the background?" and a setting for where a window created outside iTerm2 opens (new window, focused window, or topmost window already showing that session) — [tmux doc](https://iterm2.com/documentation-tmux-integration.html)
- iTerm2 remembers which tmux windows were tabs together; titles and tab colors persist across detach via tmux session options `@per_tab_settings` and `@tab_colors`, but tab groups do not (issue #13167, 3.7.3, 2026, no maintainer reply seen) — [GitLab #13167](https://gitlab.com/gnachman/iterm2/-/issues/13167)
- Size complaints: "Creating new tmux tabs shortens window height each time" — [GitLab #7821](https://gitlab.com/gnachman/iterm2/-/issues/7821); "variable window sizes ... both windows change size" over ssh (3.3.0beta16, 2019) — [GitLab #7970](https://gitlab.com/gnachman/iterm2/-/issues/7970); [iterm2-discuss "tmux windows changing sizes all together"](https://groups.google.com/g/iterm2-discuss/c/Cg0unhMJKf4). Status unverified.
- Attach hangs: remote FreeBSD ([#12145](https://gitlab.com/gnachman/iterm2/-/issues/12145)), mosh ([#5924](https://gitlab.com/gnachman/iterm2/issues/5924)), remote failure ([#11131](https://gitlab.com/gnachman/iterm2/-/issues/11131))
- 2026 fixes in 3.7.5–3.7.7 touching tabs: missed window switches by another client/script so the old tab stayed shown; `new-window -d` now opens a background tab; tmux sessions not resizing when tab bar hides/shows in fullscreen; tab shows finished title immediately on load; "Close tmux windows after detaching?" Always answer closing wrong sessions; crashes with windows left open after detach; resume tmux integration after a crash; hotkey windows moving when tmux windows open as tabs in the attaching window; tmux floating panes (tmux ≥3.7) — [downloads](https://iterm2.com/downloads). 3.6.7 fixed "tabs switching unexpectedly in tmux integration" (per search summary of the same page).
- Praise (Dec 2025): "Each tmux window becomes a native iTerm2 tab"; Cmd-T/W/1-9 and drag-reorder work as locally; trackpad scroll and Cmd-F; "Cmd+C just works"; reconnect "restores exactly". Trade-offs: macOS-only; attaching from two Macs "gets weird"; prefix conflicts with local tmux — [DEV Community](https://dev.to/evoleinik/iterm2-tmux-cc-the-remote-development-setup-nobody-talks-about-4p89)
- Recommended invocation `ssh -t host 'tmux -CC new -A -s main'`; "Don't use mosh for tmux integration" — [search summary of HN/gist results](https://news.ycombinator.com/item?id=8036749) (attribution approximate)
- tmux -CC is cited as a main reason users stay on iTerm2 rather than Ghostty — [tslateman comparison](https://tslateman.github.io/tutor/how/terminal-emulators)
- Third-party: tab titles in -CC show the same title for many Claude Code sessions and tmux renames don't carry over — [claudeissues #55397](https://claudeissues.com/issue/55397-feature-include-session-name-in-terminal-title-critical-for-tmux-cc-iterm2)

### Inferences
- Lessons for puritty's tmux tabs: (1) make Close offer Kill / Hide / Detach explicitly (iTerm2 users asked for detach on the dialog); (2) persist tab-local state (titles, colors, grouping) in tmux user options so reattach restores it; (3) track window switches/new windows made by other clients; (4) honor `new-window -d` as background tab; (5) handle tab-bar show/hide resizing; (6) be explicit about the common-size constraint (gutters) — it is the most persistent complaint.
- Mixing local and tmux panes in one tab is forbidden in iTerm2; puritty can adopt the same rule simply.

### Gaps
- Could not fetch the GitLab "tmux Integration Best Practices" wiki (empty page body).
- Did not confirm whether the kill/hide dialog now includes Detach.
- Status of #7821/#7970 unknown; tmux ≥2.9 `window-size` behavior vs iTerm2 "variable window sizes" not verified.

## 3. Terminal.app

### Takeaway
Terminal.app has basic tabs (Cmd-T with default or current profile, profile submenu, Finder "New Terminal Tab at Folder") and "window groups" — saved sets of windows/tabs with their settings, optionally reopened at launch and exportable. It lacks split panes (beyond a same-session split view — uncited), tab groups, per-tab color, and tmux integration.

### Cited Findings
- Cmd-T opens a new tab with the default profile or the active tab's profile per "New tabs open with" in General settings; Shell > New Tab > profile list chooses a profile; Finder Services > "New Terminal Tab at Folder" — [Apple: Open new Terminal windows and tabs](https://support.apple.com/guide/terminal/open-new-terminal-windows-and-tabs-trmlb20c7888/mac)
- Window groups: windows and their tabs, settings, sizes, positions, titles; "Restore all commands" re-runs remote connections and safe commands; managed under Settings > Window Groups; "Use window group when Terminal starts" — [Apple: window groups](https://support.apple.com/guide/terminal/trml15652/mac), [Apple: Window Groups settings](https://support.apple.com/guide/terminal/trmlwrkspc/mac), exported as `.terminal` files — [Terminal 2 release notes](https://developer.apple.com/library/archive/releasenotes/DeveloperTools/RN-Terminal/index.html)
- Anecdote: an 11-window group fails to expand on a recent macOS while 3–9-window groups work — [Apple Discussions](https://discussions.apple.com/thread/250257252)
- macOS Tahoe 26 betas 1–2: the new tab UI in Safari and Terminal was "One of the most common complaints", later revised by Apple — [9to5Mac](https://9to5mac.com/?p=1008984)
- A 2012 HN commenter: both iTerm2 and Terminal do tabs, but tmux "decouples my workflow from the operating system" — [HN 3729527](https://news.ycombinator.com/item?id=3729527)

### Inferences
- Terminal.app is the floor users compare against; the iTerm2-specific features (drag between windows, colors, indicators, arrangements) are what make iTerm2 "the reference".

### Gaps
- Could not fetch Apple pages on Move Tab to New Window, Merge All Windows, Show All Tabs, tab switching shortcuts, or close confirmation, though these menu items exist in Terminal (from prior knowledge, uncited).

## 4. User sentiment (praise / complaints)

### Takeaway
Praise centers on tmux -CC (native tabs for remote tmux), broadcast input, scripting, and restore-on-relaunch; complaints are about tmux sizing and close semantics, attach hangs, titles not being what users set, and (in competitors) the absence of iTerm2-style restore. Direct Reddit threads were not found by search.

### Cited Findings
- Users leaving iTerm2 for Ghostty: exceptions are those depending on "-CC integration, broadcast input, or the scripting API" — [tslateman comparison](https://tslateman.github.io/tutor/how/terminal-emulators)
- HN: WezTerm "closest to iTerm2, minus being able to quit it and have it restore all windows and tabs on restart"; another wants per-pane detach into its own window — [hn.nuxt.dev 47206009](https://hn.nuxt.dev/item/47206009)
- A migrator to Ghostty "wasn't 100% happy with how the terminal tabs appeared" — [James Brooks blog](https://blog-jamesbrooks-net.pages.dev/posts/migrating-from-iterm2-to-ghostty)
- Tab-title frustration: manual titles overwritten by session name (fixed 3.7.5) — [downloads](https://iterm2.com/downloads); rename-by-right-click requested since #6022 — [GitLab #6022](https://gitlab.com/gnachman/iterm2/-/issues/6022)
- Tab order: Ctrl-Tab not following visual order (#8219, 2019) — [GitLab #8219](https://gitlab.com/gnachman/iterm2/-/issues/8219)
- Historical tab-bar visual regressions: invisible tab bar after Cmd-T in 3.2.6beta1 on High Sierra — [GitLab #7301](https://gitlab.com/gnachman/iterm2/-/issues/7301); Big Sur master issue noting tab bar changes — [GitLab #8964](https://gitlab.com/gnachman/iterm2/-/issues/8964)

### Inferences
- For puritty local tabs, the "must" list implied by iTerm2 usage: new tab with same/default profile and directory reuse, Cmd/Ctrl-number + next/prev in visual order, drag reorder, drag between windows and tear-off, confirm only when closing multiple/running sessions, undo close, rename via context menu that sticks, per-profile/per-host tab color, new-output dot + activity + ended indicators, scrolling overflow, and restore-on-relaunch.

### Gaps
- No Reddit (r/macapps, r/iterm, r/commandline) threads surfaced in search with tab-specific complaints; sentiment here comes from GitLab, Google Groups, HN mirrors and blogs.
- No GitLab issue vote counts collected.

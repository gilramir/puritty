# Broadcast input in SSH clients and connection managers

A survey of how SSH clients and session managers let one person type the same
input into several sessions. Gathered 2026-11-12 from manuals, changelogs,
knowledge-base pages, forum threads and, for ClusterSSH and electerm, the
source. Each claim names its source. "Not verified" means that no source was
found, not that the feature is missing.

The central question for puritty is **where the user types**. The programs
fall into three groups:

- **Mirror the keys typed in a session** (MobaXterm MultiExec, Xshell "Send
  Key Input to All Sessions", Termius, Royal TS, RDM, Tabby, electerm's
  broadcast toggle, Ásbrú clusters).
- **A separate input box inside the window** (SecureCRT Command window, Xshell
  Compose bar/pane, mRemoteNG Multi SSH, SuperPuTTY command bar, MTPuTTY
  Send Script, electerm batch input, WindTerm Sender pane, Royal TS key
  sequence panel, Ásbrú PCC).
- **A separate console window** (ClusterSSH, csshX).

Several programs offer two of these at once, usually a line box for commands
and a keystroke mirror for everything else.

---

## MobaXterm — MultiExec

**Where you type.** In any terminal. The manual describes "another really
useful mode called "Multi-execution" mode. This mode allows you to display all
your terminals at the same time and to write your commands to all of them at
once … when you press a keyboard key, it will write the same letters on all
your terminals at once." It is entered with the "MultiExec" button.
([MobaXterm documentation §1.3](https://mobaxterm.mobatek.net/documentation.html))

**The screen.** All terminals are shown at once (manual, above). The manual
does not describe the grid's shape or limits. The changelog shows a toolbar
across the top in this mode: 8.0 "Added a Paste button on the MultiExec top
toolbar". ([changelog](https://mobaxterm.mobatek.net/download-home-edition.html))
The tile layout for many terminals, and how small tiles get with 10-20
sessions, is not verified.

**Key by key.** Yes ("when you press a keyboard key"). Function keys were
broken until 9.1: "function keys now work properly in "MultiExec" mode".
Macros: 6.1 "Corrected macros hotkeys which did not work in MultiExec mode".
([changelog](https://mobaxterm.mobatek.net/download-home-edition.html))

**Paste.** Pasting goes to all terminals and has had a history of bugs: 5.1
"pasting to multiple terminal at once using Ctrl+Shift+Insert"; 8.2 "corrected
some issues when pasting to all terminals (in MultiExec mode)"; 26.3 (2026-04)
"the paste confirmation dialog was frozen in "MultiExec" mode".
([changelog](https://mobaxterm.mobatek.net/download-home-edition.html))
Passwords: no MultiExec-specific handling found. One bug was an authentication
case: 9.0 "corrected a freeze issue in MultiExec mode, when connecting several
SSH sessions to the same host and using Keyboard-interactive authentication".

**Choosing targets.** Every open terminal is in by default; each tile has an
"Exclude" checkbox. 8.2: "you can now select terminals for writing in
"MultiExec" mode"; 21.5: "in "MultiExec" mode, the terminal title is written in
the "Exclude" checkbox under each terminal"; 24.2 (2024-07-02): "added a new set
of right-click options in "MultiExec" mode that allow to activate or deactivate
all terminals".
([changelog](https://mobaxterm.mobatek.net/download-home-edition.html))
Whether the exclusions are remembered between MultiExec sessions is not
verified.

**Showing it.** The mode itself is the indicator: the tab view is replaced by
the tiled view with the toolbar. Per-terminal state is the checkbox under each
tile.

**Start/stop.** The MultiExec button toggles it.

**Other.** 24.2 also "added a new right-click option in "MultiExec" mode that
allows to synchronize mouse scrolling".
([changelog](https://mobaxterm.mobatek.net/download-home-edition.html))

**Complaints and praise.** A Stack Overflow question: "By default all open tabs
are included in the MultiExec. While inside MultiExec environment I can check a
box to exclude a tab", asking how to choose tabs *before* entering; no answer
in the snapshot.
([SO 63649230, archive](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/63649230/how-do-i-choose-tabs-to-include-in-multiexec-of-mobaxterm)
— archive returned 401 on direct fetch; quoted from search result.) A
Remote Desktop Manager user asks for one button that broadcasts to all SSH
tabs and splits the screen, because "This feature works perfect in MobaXterm".
([Devolutions forum 41824](https://forum.devolutions.net/topics/41824/multiexec-button-ssh-sessions-with-automatic-split-screen))
That is the strongest praise found: one click gives both the broadcast and the
view of every target.

---

## SecureCRT — Command window (formerly Chat window)

**Where you type.** A separate input box docked below the session area. "Choose
Command window from the View menu"; "the window appears below the session
window." ([VanDyke tip](https://vandyke.com/support/tips/chatsendcom.html)) It
was the "chat window" until 7.2: "The "chat window" has been renamed to
"command window"." ([7.2 history](https://www.vandyke.com/download/securecrt/7.2/history.txt))
In 6.x the broadcast item was "Send chat to all tabs"
([6.6 history](https://www.vandyke.com/download/securecrt/6.6/history.txt)).
ALT+G opens it (8.0 history).

**Line or key.** By default a line: "Provides a mechanism for composing a line
(or more) of text before sending to the remote system", with history.
([features](https://www.vandyke.com/products/securecrt/features.html)) Commands
go "only when you press ENTER"; CTRL+ENTER makes multi-line drafts
([tip](https://vandyke.com/support/tips/chatsendcom.html)). 8.0 added a
per-keystroke mode: "Added a "Send Characters Immediately" mode to the Command
window, which makes it possible to do the following in one or multiple
sessions: stop commands using CTRL+C, edit files using an editor such as vi,
send escape sequences, and do tab completion."
([8.0 history](https://vandyke.com/download/securecrt/8.0/history.txt))
So SecureCRT added keystroke mode *to the box* rather than mirroring a session.
Key collisions followed: 8.5 "if the option "Send Characters Immediately" was
set, pressing CTRL+A selected all the text in the Command Window instead of
sending the CTRL+A"; 9.0 Mac/Linux "When the close tab keyboard shortcut
(Command+W or Ctrl+F4) was sent to all tabs via the Command Window, SecureCRT
could crash". 9.2: "When connected to a remote system with shell support for
bracketed paste mode, commands sent from the Command Window were not
immediately executed". 9.5: a paste shortcut used from the Command window "when
the command was being sent to multiple sessions, the pasted text may have been
duplicated in each session".
([8.5](https://www.vandyke.com/download/securecrt/8.5/history.txt),
[9.0](https://www.vandyke.com/download/securecrt/9.0/history.txt),
[9.2](https://www.vandyke.com/download/securecrt/9.2/history.txt),
[9.5](https://www.vandyke.com/download/securecrt/9.5/history.txt))
Passwords: nothing specific found.

**Choosing targets.** Right-click in the Command window → "Send Commands to" →
All Sessions (the tip's wording: "choose Send Commands to All Sessions";
"each command you enter is sent to all tabs in that SecureCRT window").
([tip](https://vandyke.com/support/tips/chatsendcom.html)) The full set:
"Commands can be sent to the active session, all sessions, selected tab
groups, or visible sessions."
([features](https://www.vandyke.com/products/securecrt/features.html)) Tab
groups and visible sessions came in 8.1: "Added new Command window options to
send to selected tab groups or visible tabbed sessions."
([8.1 history](https://www.vandyke.com/download/securecrt/8.1/history.txt))
Exclusion is by **locking** a tab: "Commands are not sent to locked sessions",
locked from the File or tab menu ([tip](https://vandyke.com/support/tips/chatsendcom.html));
8.0 added locking a whole tab group. A safety bug: 9.5 "If a locked session tab
was reconnected automatically, the tab became unlocked"
([9.5](https://www.vandyke.com/download/securecrt/9.5/history.txt)) — an
excluded session silently rejoined.

**Remembered.** The target is a setting with a default: 8.5 "Added a global
option that allows the Command window to be configured to send commands to all
sessions, visible sessions, or the active session by default"; 8.7 renamed it
"Initially send commands to"; 8.7 also lets "Send Characters Immediately" be on
by default. ([8.5](https://www.vandyke.com/download/securecrt/8.5/history.txt),
[8.7](https://www.vandyke.com/download/securecrt/8.7/history.txt)) Bugs where
the mode silently reverted: 9.4 "If the Command Window's send mode was set to
"Visible Sessions" and SecureCRT is started in tiled mode, the send mode was
changed to "Send commands to active session""; 9.6 "The Command Window reverted
to sending commands to the active session when all session tabs were closed,
regardless of the "Send Commands to" setting"; 8.7/9.0 "minimizing and
restoring SecureCRT caused the option [Send Characters Immediately] to be
disabled". ([9.4](https://www.vandyke.com/download/securecrt/9.4/history.txt),
[9.6](https://vandyke.com/download/securecrt/9.6/history.txt))

**Showing it.** Not documented beyond the context-menu check state. Tiling is
the recommended way to watch: "Tiled sessions make it easier to compare
multiple sessions or view output when sending commands to all sessions"; since
7.0 broadcast works with tiled sessions.
([features](https://www.vandyke.com/products/securecrt/features.html),
[tip](https://vandyke.com/support/tips/chatsendcom.html)) 9.1 lets the Command
window's colours be set. Whether the window shows the current target in its
title bar is not verified.

**Start/stop.** Choose another "Send Commands to" value, or a key/button
mapped to `MENU_TOGGLE_SEND_COMMANDS_TO_ALL_SESSIONS` or (8.1.2)
`MENU_SEND_COMMAND_TO_ALL_SESSIONS`; 8.0 added
`MENU_TOGGLE_SEND_CHARACTERS_IMMEDIATELY`.
([8.1 history](https://www.vandyke.com/download/securecrt/8.1/history.txt),
[8.0](https://vandyke.com/download/securecrt/8.0/history.txt)) 9.6 added
mapping "a button, key, or command to send a string to the Command window",
which puts button-bar strings through the window's target.
([9.6](https://vandyke.com/download/securecrt/9.6/history.txt))

**Scripting.** The Command window is scriptable (`SendToAllSessions`).
([command window automation](https://vandyke.com/support/scripting/scripting-examples/command-window-automation.html))

---

## Xshell — Compose bar/pane and "Send Key Input to All Sessions"

Xshell has both models side by side.

**Compose bar / pane (a box).** View → Compose → Compose Bar or Compose Pane;
"choose the target sessions with the range selection icon on the left";
the bar sends "a single line of command or string", the pane lets you "draft
and edit multiple lines and send them at once".
([NetSarang KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/1118601758/How+to+send+keystrokes+to+different+multiple+sessions))
Targets: "the current sessions, the current session group, all sessions within
the current window, … all Xshell sessions universally"; Shift+Enter for a new
line in the pane; the pane can be detached; "the Compose Bar or Pane only
supports visible characters".
([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/31392021/Sending+Strings+to+Multiple+Open+Sessions))
An older blog post words the targets "Current Sessions, the Current Tab Group,
to All Sessions, or to All Xshell Windows" and says the delivery options are
under a triple-bar icon. ([search snippet of NetSarang blog](https://blog.netsarang.com/?p=1027), not fetched)
Changelog (via Softpedia, the NetSarang page did not load): Xshell 7 Build
0093 (2021-12-28) customise which sessions/tabs receive keystrokes; Build 0098
(2022-02-17) send Compose Pane commands to **same-coloured tabs**; Build 0157
"ADD: Ability for Compose Pane/Bar to send to currently connected sessions
only". ([Softpedia changelog](https://www.softpedia.com/progChangelog/Xshell-Changelog-23416.html)
— returned 403 on direct fetch; entries quoted from search results, not
verified line by line.)
Quick Commands buttons can only go to the current session, but sending a Quick
Command through the Compose bar sends it to the bar's target; special keys in
Quick Commands are written as octal (`\033` for ESC).
([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/31392021/Sending+Strings+to+Multiple+Open+Sessions))

**"Send Key Input to All Sessions" (mirror).** Tools → Send Key Input to All
Sessions. "A status indicator appears at the top of each session that will
receive the input. To exclude a session, press its 'Off' button." It sends
what the Compose bar cannot: "Esc, Backspace, and Ctrl or Alt combinations".
([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/1118601758/How+to+send+keystrokes+to+different+multiple+sessions))
"Once toggled ON, each individual session within the window can be toggled
ON/OFF as desired … type long strings into several sessions simultaneously and
see the results in real time."
([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/31392021/Sending+Strings+to+Multiple+Open+Sessions))
Scope is "all sessions within a window". So targets are shown **in each
session**, as a bar with its own On/Off — the clearest per-session indicator
found in this survey.

**Remembered.** Not verified for either feature.

**Complaints.** Forum archive threads exist titled "Broadcast commands",
"Paste in all opened sessions", "Send ^] to all sessions", "Script send to all
tabs", "Compose Bar, send to multiple windows"; only the titles could be read.
([NetSarang forum archive](https://netsarang.atlassian.net/wiki/spaces/ENFA/pages/1311743180/Broadcast+commands+3))

---

## Termius — Broadcast in workspaces

**Where you type.** In one terminal; Termius copies it. "Termius sends your
input to all active terminals in the workspace." In Focus mode "The selected
terminal stays active for input"; in Split view "A solid frame highlights the
main input terminal."
([Termius docs, Workspaces](https://docs.termius.com/terminal/workspaces))

**Targets.** Every active terminal in the workspace (a workspace is a set of
hosts and local terminals). "Broadcast input works only with terminals opened
in Split View mode and will not affect other connections"; up to 16 panes per
Split View tab; "toggle input broadcast input independently" per Split View
tab. ([Termius blog](https://termius.com/blog/broadcast-input)) No per-pane
exclusion is documented.

**Start/stop.** Broadcast icon in the side panel (Focus mode) or in a terminal
pane (Split view); shortcut "Ctrl + Alt + B (Windows/Linux) or Cmd + B (macOS)",
rebindable in Settings → Shortcuts.
([docs](https://docs.termius.com/terminal/workspaces))

**Other.** Typing a snippet's title "will send the script to all active Split
View panes". Paid plans only. ([blog](https://termius.com/blog/broadcast-input))
Key-by-key vs line, paste and passwords: not documented; it mirrors raw
terminal input, so presumably key by key (not verified).

---

## Royal TS (Windows) / Royal TSX (macOS)

**Royal TSX.** A single toggle: in the Tab menu of a terminal, "Broadcast
Input to all Terminal Sessions … When this is enabled, all input will be
broadcast to all other open terminal sessions." (quoted from search results
of Royal's support site, which now redirects). Users ask for subsets: a 2022
post says it cannot broadcast to selected sessions; a 2024 reply asks for
"Broadcast input into all terminal sessions at once", "Broadcast input to all
displayed terminal tabs (active split tabs)", "Broadcast input to marked
terminal sessions (like royal ts)" — no staff reply.
([community thread](https://community.royalapps.com/t/royal-tsx-unable-to-broadcast-input-to-selected-terminal-sessions/1562))

**Royal TS V6+.** Actions tab → "Broadcast Input"; "Via the "Broadcast
Receiver" you are able to select which Terminal (Rebex) connections receive
the input"; "by default, all rebex based connection receive the input
broadcast"; a receiving tab shows an icon in its top-right corner, which a beta
user found hard to see. After a bug in which closing a tab turned broadcast on
by mistake (fixed 7.02.50304), staff added a confirmation prompt and kept
direct typing into a session that is not a receiver.
(Support threads 17000020301, 17000024321 on support.royalapps.com; the site
now redirects to a login page, so these are from search-result excerpts, not
verified.)

**Key sequence panel (line-based).** Royal TS 3.2's "Key Sequence Broadcaster"
panel: "Choose which targets (active connections) should receive the key
sequence"; "(on by default) send {ENTER} at the end of each line"; `{` brings
up special keys; CTRL+ENTER runs it. Direct mode or simulated keyboard input.
([Royal blog](https://blog.royalapps.com/blog/royal-ts-3-2-key-sequence-broadcaster-panel))

---

## Remote Desktop Manager (Devolutions)

**Where you type.** In an SSH tab (mirror). Right-click an SSH tab →
"Broadcast input" → "Add to broadcast" / "Remove from broadcast"; "Manage
broadcast" opens a window listing sessions with checkboxes; ribbon Actions has
"Broadcast all" (adds every entry not yet broadcasting; can switch to a
pre-configured view) and "Remove all broadcasts".
([Devolutions KB](https://docs.devolutions.net/rdm/kb/how-to-articles/broadcast-actions-in-ssh-sessions/))
How participating tabs are marked: not documented. On macOS (iTerm sessions,
RDM 4.2) a user asked for header text or colour on participating windows; not
confirmed. ([forum 27222](https://forum.devolutions.net/topics/27222/broadcast-input-to-several-terminals))

**Complaints.** Too many steps: select all SSH entries, OK, then tile;
request for one MobaXterm-style button. Staff: a shortcut opens "manage
broadcast" (File → Settings → User Interface → Keyboard).
([forum 41824](https://forum.devolutions.net/topics/41824/multiexec-button-ssh-sessions-with-automatic-split-screen))

---

## mRemoteNG — Multi SSH

**Where you type.** A text box: View → Multi SSH "will open a text box where we
can type in commands and they will be sent to all open sessions."
**Targets.** All open SSH sessions; "There is no option to selecively send
commands to some sessions."
([yurisk.info guide, 2025](https://yurisk.info/2025/02/16/mremoteng-initial-set-up-and-usage/))
Added in 1.76.0: "#611: Added multi-ssh toolbar for sending commands to many
SSH clients at once" (search-result quote of the changelog, not fetched).
Key-by-key or line: not verified.

---

## SuperPuTTY — Send Commands toolbar

**Where you type.** A toolbar text field, View → Toolbars "Show or Hide the
Send Commands Toolbar"; a hotkey task "GotoCommandBar" focuses it. Tools →
Toggle Command Mask "Enables masking characters with a `*` when input is
entered into the Send Commands Toolbar" (CTRL+SHIFT+8) — a password mode for
the box. ([wiki](https://github.com/jimradford/superputty/wiki/Documentation))
**Targets.** Release notes 1.4.0.8: commands "now sent to all sessions that are
selected"; 1.4.0.9: Enter sends a carriage return (issue #490). (Search-result
quotes of the release notes, not fetched.) How sessions are selected is not
verified.

---

## MTPuTTY — Send Script

A "Send script" window: "enter the script, select the active connection from
servers list, and click Send script". (AddictiveTips, via search result.)
Later 1.8 beta: "Special keys in script added (including the Escape key)".
(Softpedia, via search result.) A line/script sender with a checklist of
targets, not a keystroke mirror. Not verified first-hand.

## PuTTY Connection Manager

Listed with a "Multi Command Sender"; no documentation found and the project
site is gone. (Search results only.) Stock PuTTY has no broadcast; it is on
the wishlist as "terminal fanout".
([PuTTY wishlist](https://putty.cs.utah.edu/wishlist/terminal-fanout.html))

---

## WindTerm

**Sync Input (mirror, channels).** "To start sync input, you only need to add
related sessions to the same sync channel … to stop sync input, you only need
to let the sessions leave the corresponding channel"; up to four channels.
([WindTerm blog](https://kingtoolbox.github.io/2021/05/27/sync-input))
Release notes add pause/resume during synchronisation and a Sync Input dialog
listing members; Tmux integration "lacks support for Sender Pane and Sync
Input" (2.7.0). (Search-result quotes of GitHub releases.) How channel
membership is shown is not verified (the blog uses GIFs).

**Sender pane (box).** "Sender pane supports sending text line by line at
specified intervals"; escapes such as `\x03` for Ctrl+C.
([sender blog](https://kingtoolbox.github.io/2020/06/20/sender-send-text))
Sending to a tab group is mentioned in search results, not verified.

Several channels is unusual: an admin can drive "web servers" and "db
servers" as separate groups without re-picking.

---

## electerm

Two features, read from the source.

**Broadcast toggle (mirror).** An icon in each session's control bar toggles
`broadcastInput` for that session; when the *active* terminal has it on, its
raw input is sent to every other open terminal pane:
`if (!this.isActiveTerminal() || !this.props.broadcastInput) return` … then
for every other `term-` ref that `canReceiveBroadcast`.
([term-socket.js](https://github.com/electerm/electerm/blob/master/src/client/components/terminal/mixins/term-socket.js))
So the toggle marks the *sender*, not the receivers; there is no per-receiver
exclusion. A 2026 issue: "Broadcast input can only be toggled by clicking the
icon in the session control bar", proposing `ctrl+alt+b`.
([issue #4568](https://github.com/electerm/electerm/issues/4568))

**Batch input (box).** A footer field that expands into "the textarea +
tab-select panel"; "press Enter in the textarea -> send `cmd` to all selected
tabs"; the current tab is listed first and is selected by default; history is
kept. ([batch-input.jsx](https://github.com/electerm/electerm/blob/master/src/client/components/footer/batch-input.jsx))
Complaint: the "Q" and "B" footer buttons are too small to click and have no
shortcut. ([issue #3046](https://github.com/electerm/electerm/issues/3046))

---

## Tabby (SSH and local alike)

Broadcast works on split panes: "You can type into all panes by pressing
`Ctrl-Shift-I` (`⌘-Shift-i`). Click any pane to cancel focus." To reach tabs,
first combine them into panes (`Ctrl-Shift-,`), "to quickly send commands to
all tabs! `1.0.173+`".
([Tabby discussion #5259](https://github.com/Eugeny/tabby/discussions/5259))
Mirror model, all panes of the tab, stopped by a click. No per-pane exclusion
found.

---

## Ásbrú Connection Manager (formerly PAC Manager)

**Clusters (mirror).** Opening a cluster opens its terminals and "link[s] the
keyboard to all terminals in the cluster"; clustered terminals cannot be given
different commands since "they are tied together"; a terminal that reconnects
"is no longer with the cluster". Clusters are saved, made by "Add to cluster".
([Ásbrú docs, Clusters](https://docs.asbru-cm.net/Managing/Clusters/))
Known bugs (6.3.3 notes, via search): closing one tab in a cluster
disconnected the whole cluster.

**Power Cluster Controller (separate).** For terminals not in a cluster:
"send keys to all open terminals"; typing in one terminal stays there unless
sent through the PCC. ([docs](https://docs.asbru-cm.net/Managing/Clusters/))
The PCC's layout (text box, per-key or line, terminal selection) is not
documented on that page.

---

## ClusterSSH (cssh)

**Where you type.** A separate small console window, plus one xterm per host.
"Any text typed into the administration console is replicated to all
windows. All windows may also be typed into directly."
([cssh man page](https://www.mankier.com/1/cssh))

**Key by key.** Yes: the console binds `<KeyPress>` and `<KeyRelease>` and
forwards each as an X `SendEvent` to every active host's window.
Pasting into the console (Control-v or middle button) sends the pasted text to
each host character by character (`send_text`).
([Tk.pm](https://github.com/duncs/clusterssh/blob/master/lib/App/ClusterSSH/Window/Tk.pm))

**Targets.** The Hosts menu holds "Retile Windows", "Set all active", "Set half
inactive", "Toggle active state", "Close inactive sessions", "Add Host(s) or
Cluster(s)", "Re-add closed session(s)", then one checkbox per host
([Tk.pm](https://github.com/duncs/clusterssh/blob/master/lib/App/ClusterSSH/Window/Tk.pm)).
"Unchecking a hostname on the Hosts sub-menu will unplug the host from the
cluster control window … Re-selecting it will plug it back in."
([man](https://www.mankier.com/1/cssh)) "Setting a host to inactive keeps the
session open". ([putorius](https://putorius.net/?p=3385)) Clusters (named host
lists) come from config files, so they are remembered; the active/inactive
state is not.

**Showing it.** The console's title is the configured title plus the host
count, `title [N]` (Tk.pm). The per-host state lives in the Hosts menu, which
can be torn off into its own window. No visual change to inactive xterms was
found.

**Special input.** Alt-n pastes each host's own hostname, Alt-u the username;
a Send menu of per-host macros. ([man](https://www.mankier.com/1/cssh))

---

## csshX (macOS)

**Where you type.** "A master window will also be created. All keyboard input
in the master will be sent to all the slave windows."
**Toggling.** A control mode on Ctrl-a; Ctrl-a e enters window selection
(arrows/hjkl), then "e: Enable input for selected window", "d: Disable",
"t: Toggle", "o: Disable all windows except for selected", "O: Zoom selected
window and disable all other windows"; Ctrl-a t toggles all; Ctrl-a n
"Re-enable all windows for input"; Ctrl-a Space "Disable current terminal and
enable next terminal"; Ctrl-a Ctrl-a sends a literal Ctrl-A.
**Showing it.** A disabled window's text turns grey: `color_disabled_foreground`
default "{37779,37779,37779} (mid-gray)".
([csshX POD](https://raw.githubusercontent.com/brockgr/csshx/master/csshX))
The "Space" key (disable this, enable next) is a step-through mode: do
something to each host in turn without leaving broadcast.

---

## Patterns

### 1. Where the user types

| model | programs |
|---|---|
| in a session, keys mirrored | MobaXterm, Xshell (Send Key Input), Termius, Royal TS/TSX, RDM, Tabby, electerm (toggle), Ásbrú clusters, WindTerm Sync Input |
| a box in the window | SecureCRT, Xshell Compose, mRemoteNG, SuperPuTTY, MTPuTTY, electerm batch, WindTerm Sender, Royal key-sequence panel |
| a separate console window | ClusterSSH, csshX, Ásbrú PCC (probably) |

The vendors who have lived with this longest offer **both**. SecureCRT began
with a line box and in 8.0 bolted a keystroke mode onto it because users need
Ctrl+C, vi, Tab completion. Xshell keeps the box for lines and a separate
mirror mode for "Esc, Backspace, and Ctrl or Alt combinations". The box is
safe and editable but blind to anything but text; the mirror handles
everything but makes it easy to forget broadcast is on.

### 2. Line or key, special keys, paste, passwords

- Boxes send a line on Enter (SecureCRT, Xshell, mRemoteNG, SuperPuTTY,
  electerm) with Ctrl/Shift+Enter for multi-line; special keys need escapes
  (Xshell octal, WindTerm `\x03`, Royal `{…}`) or a keystroke mode.
- Mirrors send each key. Every mirror implementation found has a bug history
  on special keys and paste: MobaXterm function keys, macros, paste x3;
  SecureCRT Ctrl+A captured, close-tab shortcut broadcast and crashing,
  bracketed paste, paste duplicated.
- Passwords: only SuperPuTTY has a mask for the box. No product documents how
  a password prompt in one host interacts with broadcast.

### 3. Choosing targets

- **All, then exclude**: MobaXterm (Exclude checkbox per tile; all on/off since
  24.2), Xshell mirror (Off per session), SecureCRT (lock a tab), Royal TS
  (receiver list), cssh/csshX (per-host toggle).
- **Opt in**: RDM (Add to broadcast / Manage broadcast), electerm batch
  (checklist, current tab preselected), MTPuTTY (server list), WindTerm (join a
  channel), Ásbrú (saved cluster).
- **By scope**: SecureCRT active / all / visible / tab group; Xshell current /
  group / window / all windows / connected only / same colour; Termius and
  Tabby the panes on screen.
- **All only**: mRemoteNG, Royal TSX; both draw complaints.
- **Remembered**: SecureCRT (global "Initially send commands to"), Ásbrú and
  cssh (saved clusters), WindTerm (channels). SecureCRT's changelog shows
  the danger of state: the mode reverting silently (9.4, 9.6) and a locked tab
  unlocking on auto-reconnect (9.5).

### 4. Showing targets and the active broadcast

- Strongest: Xshell's bar at the top of each receiving session with an Off
  button; MobaXterm's switch to a tiled view with a checkbox under each
  terminal; csshX greying disabled windows; Termius's frame on the input
  terminal.
- Weak or missing: Royal TS's small corner icon (reported hard to see); RDM
  (none documented; users asked for colour); electerm (an icon on the sender
  only); SecureCRT (a context-menu setting; tiling recommended).
- Seeing the *output* of every target is treated as part of the feature:
  MobaXterm tiles automatically; SecureCRT recommends tiling; Termius and Tabby
  work only on visible panes; RDM users ask for broadcast and tiling together.

### 5. Start / stop

Toggle button or menu (MobaXterm, Xshell Tools menu, Termius icon and
Ctrl+Alt+B, Royal, Tabby Ctrl+Shift+I and click-to-cancel), choose a different
target (SecureCRT), close the console (cssh), leave the channel (WindTerm).
Royal TS added a confirmation prompt after broadcast turned on by accident.

### 6. Complaints and praise

- Choose targets before entering the mode (MobaXterm SO question).
- Broadcast to a subset or to visible tabs only (Royal TSX, Royal TS beta).
- One click for broadcast + tile ("works perfect in MobaXterm"; RDM request).
- Too many steps, too-small buttons, no shortcut (RDM, electerm).
- Silent state changes are the bug class that matters most (SecureCRT 9.4,
  9.5, 9.6; Royal's accidental activation; Ásbrú's reconnect leaving the
  cluster).

## Not verified

MobaXterm's tile layout and limits, and whether exclusions persist; Xshell's
exact menu wording for "connected only" and "same colour", and whether its
choices persist; Termius per-pane exclusion; the Royal TS forum details
(site now redirects); mRemoteNG and SuperPuTTY key handling; MTPuTTY and PuTTY
CM first-hand; WindTerm membership display; Ásbrú PCC layout.

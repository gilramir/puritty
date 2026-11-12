# Broadcast input in terminal emulators and multiplexers

Research notes for puritty's broadcast-input design, written 2026-11-12. The
question is where the user types, either into one of the sessions with the keys
mirrored to the others or into a separate input box, and how the targets are
chosen, shown and stopped.

How these notes were checked. Where a program's source is public, it was
shallow-cloned on 2026-11-12 and read. The commits read were Konsole `439ce807c1`,
Tilix `46b6a7c6b3`, Terminator `9f2d0b6ccc`, kitty `fdea442b70`, iTerm2
`2a8d67e061`, Tabby `467ce8ebfa`, Zellij `9e7be20f5c`, tmux `c05e710546` and
Windows Terminal `f6de9e0618`. Source links point at the default branch, so line
content can drift from what is quoted here. Claims marked *(from source)* come
from reading code, not from documentation. Warp and SecureCRT are closed source,
so their sections rest only on their documentation and issue trackers.

---

## Terminator

**Where the user types:** in an ordinary terminal. The focused terminal is the
broadcaster: "The current terminal (the one with the red titlebar by default)
is always the **broadcaster**."
([grouping docs](https://gnome-terminator.readthedocs.io/en/latest/grouping.html))

**What is sent:** key events. When the terminal that has focus gets a key press,
Terminator re-emits the same GDK `key-press-event` into every receiving VTE
(`group_emit` / `all_emit`), so each receiver encodes the key in its own mode
*(from source:
[terminator.py](https://github.com/gnome-terminator/terminator/blob/master/terminatorlib/terminator.py),
[terminal.py `on_keypress`](https://github.com/gnome-terminator/terminator/blob/master/terminatorlib/terminal.py))*.
- Paste is not mirrored as bytes. Each target terminal runs its own
  `paste_clipboard()`/`paste_primary()`, so each applies its own bracketed-paste
  state *(from source, `paste_clipboard` in terminal.py)*.
- The docs warn about IME and dead keys: "IME, IBus, and dead-key input can
  misbehave. Only the composed character reaches the current terminal, and
  receivers get unpredictable output." The workaround they give is to paste the
  composed character instead. A related bug,
  [#853 "Compose key input is not broadcasted"](https://github.com/gnome-terminator/terminator/issues/853),
  was closed without a fix.
- The docs also say that hidden terminals still receive: "Just because you
  cannot see a terminal does not mean the terminal is not receiving."
- Terminator can insert each terminal's number or name into all targets, which
  is how it handles per-host differences
  ([#540](https://github.com/gnome-terminator/terminator/issues/540);
  `do_enumerate` in terminator.py).

**How targets are chosen:** by named groups, plus a broadcast mode of Off, Group
or All.
- The mode is set from the 3-box group menu in each terminal's titlebar.
  "Broadcast group" is the default and can be changed in Preferences.
- Groups are created from the same menu ("New group…", which gets a random Greek
  letter name). Terminals are moved between groups with click modifiers, for
  example Ctrl+click puts this terminal in the current terminal's group.
- There are also Group all, Group tab and Ungroup actions bound to Super+G /
  Super+T. Groups span tabs and windows.
- Broadcast to tabs was reported not to cross windows
  ([LP #1514879](https://bugs.launchpad.net/bugs/1514879), marked wishlist).

**How it is shown:** by titlebar colour. Red is the broadcaster, blue is a
receiver, grey is a terminal that is not receiving. The 3-box button uses the
same colours.

**How it is started and stopped:** from the group menu, or with keybindings. The
docs still list Alt+O (off), Alt+A (all) and Alt+G (group) as the keys, but
those **defaults were removed in 2020** because they were dangerous.
[#40 "Remove default keybindings for enabling terminal broadcast"](https://github.com/gnome-terminator/terminator/issues/40)
cites [LP #1872460](https://bugs.launchpad.net/terminator/+bug/1872460). In the
current `config.py`, `broadcast_off`, `broadcast_group` and `broadcast_all` are
all `''` *(from source,
[config.py](https://github.com/gnome-terminator/terminator/blob/master/terminatorlib/config.py))*.
- A maintainer said, as one reason, that "there's no visual indicator that the
  commands you're sending are being sent to every single open terminal" (#40).
- A request to restore the keys with a first-use warning,
  [#183](https://github.com/gnome-terminator/terminator/issues/183), was
  declined.

**Known problems:**
- Passwords typed while broadcasting appear in clear in the other terminals. The
  maintainer's answer: "The shell, or receiving program is responsible for hiding
  input." ([#744](https://github.com/gnome-terminator/terminator/issues/744))
- A recurring "doubled keys" bug
  ([#96](https://github.com/gnome-terminator/terminator/issues/96),
  [#596](https://github.com/gnome-terminator/terminator/issues/596),
  [#704](https://github.com/gnome-terminator/terminator/issues/704)), and "broadcast
  all is turned on every time i start terminator"
  ([#620](https://github.com/gnome-terminator/terminator/issues/620)).
- A second Terminator launch joins the first process's groups over DBus unless
  `-u` is given (grouping docs).

## Tilix

**Where the user types:** in any terminal of the session. In Tilix a "session"
is one tab holding tiled terminals.

**What is sent:** key events, replayed into every participating VTE as copies
of the GDK event, so each receiver encodes the key itself. Pasted text,
including middle-click paste, is sent as text with `feedChild`. Reset and
reset-and-clear are mirrored too *(from source,
[terminal.d](https://github.com/gnunn1/tilix/blob/master/source/gx/tilix/terminal/terminal.d)
`SyncInputEventType` and `handleSyncInput`)*.
- The other approach, syncing VTE's commit (text) event, is disabled. The comment
  in [constants.d](https://github.com/gnunn1/tilix/blob/master/source/gx/tilix/constants.d)
  says: "The commit event allows for IME to work but causes some issues with
  certain programs like VIM. See #888". So IME is broken
  ([#351 "Synchronize Input conflicts with input method"](https://github.com/gnunn1/tilix/issues/351)).

**How targets are chosen:** every terminal in the session, minus any terminal
that has switched its own override off.

**How it is shown:** while sync is on, each terminal's title bar shows a toggle
button with a keyboard icon (`input-keyboard-symbolic`). Its tooltip reads
"Disable input synchronization for this terminal", or "Enable…" when the
terminal is opted out. When sync is off the button is hidden *(from source)*.
- This design was the author's answer to
  [#134 "Include a visual aid to synchronized input"](https://github.com/gnunn1/tilix/issues/134)
  ("it may be dangerous to forget about it"). He wrote: "adding a toggle button
  to each terminals titlebar that appears when sync input is active … It would
  also fill the role you are looking for, a visual indicator."
- A follow-up,
  [#1271](https://github.com/gnunn1/tilix/issues/1271), asked for synchronized
  input to work when the toolbar/CSD is hidden.

**How it is started and stopped:** the "Synchronize Input" item in the session
menu. The `session-synchronize-input` and `terminal-sync-input-override`
shortcuts default to `'disabled'` *(from source,
[gschema](https://github.com/gnunn1/tilix/blob/master/data/gsettings/com.gexperts.Tilix.gschema.xml))*.

**Known problems:**
- vim on CentOS starts in REPLACE mode while sync is on
  ([#888](https://github.com/gnunn1/tilix/issues/888)).
- Characters are duplicated
  ([#1729](https://github.com/gnunn1/tilix/issues/1729)).
- Paste needed special handling
  ([#150](https://github.com/gnunn1/tilix/issues/150),
  [#410](https://github.com/gnunn1/tilix/issues/410)).

## Konsole

**Where the user types:** in one source session. Copy Input is **one-way**:
it is a property of the session it was turned on from, and typing in a target
does not go back to the source. Each `SessionController` owns its own
`_copyToGroup` with itself as master *(from source,
[SessionController.cpp](https://invent.kde.org/utilities/konsole/-/blob/master/src/session/SessionController.cpp))*.

**What is sent:** bytes after encoding. The master's `Emulation::sendData`
signal is connected to `SessionGroup::forwardData`, which calls `sendString` on
each target
([SessionGroup.cpp](https://invent.kde.org/utilities/konsole/-/blob/master/src/session/SessionGroup.cpp)).
In `Vt102Emulation`, everything the emulation writes to the pty goes through
`sendData`: keys, pasted text (sent as one "big fat keypress event"), mouse
reports, and the emulator's own replies such as the DA response in
`reportTerminalType()`. So those replies are copied to the targets too *(from
source,
[Vt102Emulation.cpp](https://invent.kde.org/utilities/konsole/-/blob/master/src/Vt102Emulation.cpp);
this is a reading of the code and was not tested)*.

**How targets are chosen:** from the Edit ▸ Copy Input To submenu:
- "All Tabs in Current Window": "Allows input from the current session to be sent
  simultaneously to all sessions in current window". Sessions created later are
  added when the source next gains focus *(from source)*.
- "Select Tabs…" (Ctrl+Shift+.): "Allows input from the current session to be
  sent simultaneously to sessions picked by user". This opens a modal dialog
  with a **Filter:** field, a checkbox list of sessions, and Select All /
  Deselect All buttons. "The current tab will be greyed out." The list is built
  from all of Konsole's sessions (`SessionManager::sessions()`) *(from source,
  [CopyInputDialog.cpp](https://invent.kde.org/utilities/konsole/-/blob/master/src/CopyInputDialog.cpp))*.
  Older complaints:
  [bug 182216](https://bugs.kde.org/show_bug.cgi?id=182216) asked that the box
  list only the current window's tabs, and
  [bug 191648](https://mail.kde.org/pipermail/konsole-devel/2009-May/012096.html)
  asked for an apply button.
- "None" (Ctrl+Shift+/): "Stop sending input from current session into other
  sessions".
- Menu text quoted from the handbook source,
  [index.docbook](https://invent.kde.org/utilities/konsole/-/blob/master/doc/manual/index.docbook).

**How it is shown:** an `irc-voice` icon in the split-view header bar of the
**source** session, and the same icon as the tab icon when every view in the
tab has copy-input active. Targets get no mark *(from source,
[TerminalHeaderBar.cpp](https://invent.kde.org/utilities/konsole/-/blob/master/src/widgets/TerminalHeaderBar.cpp),
[ViewContainer.cpp](https://invent.kde.org/utilities/konsole/-/blob/master/src/widgets/ViewContainer.cpp))*.

## Yakuake and Guake

- **Yakuake** has no broadcast. The request
  [bug 291863 "Support for 'Copy Input To...' as in konsole"](https://bugs.kde.org/show_bug.cgi?id=291863)
  has been open since 2012, with a "What are the plans?" comment in 2023.
  Yakuake does have the opposite control, a per-terminal "Disable Keyboard Input"
  *(from source, `app/tabbar.cpp`)*.
- **Guake:** no broadcast feature and no request for one was found. The search
  was not exhaustive.

## iTerm2

**Where the user types:** in any session in the broadcast domain. By default
every member is both a source and a target. The Python API can make broadcast
asymmetric, as in the
[Asymmetric Broadcast Input example](https://iterm2.com/python-api/examples/broadcast.html):
"broadcasts input from the bottom left one to the other three. If a pane other
than the bottom-left one has focus, input to it does not get broadcast". The
source code tracks `sources` and multiple `broadcastDomains` *(from source,
[iTermBroadcastInputHelper.h](https://github.com/gnachman/iTerm2/blob/master/sources/InputBroadcasting/iTermBroadcastInputHelper.h))*.

**What is sent:** the source session's encoded bytes. `writeTaskImpl`
hands the string to the window, and `sendInputToAllSessions` writes the same
string to each broadcast session with `writeTaskNoBroadcast`. Arrow keys are
encoded by the *source's* `terminalOutput` (`keyArrowUp:` etc.), so a target in
a different cursor-key mode gets the source's encoding *(from source,
[PTYSession.m](https://github.com/gnachman/iTerm2/blob/master/sources/PTYSession/PTYSession.m),
[PseudoTerminal.m](https://github.com/gnachman/iTerm2/blob/master/sources/TerminalView/PseudoTerminal.m))*.
- A comment in PTYSession.m lists what counts as broadcastable: "keystrokes,
  pastes, snippets, Composer commands, and the like". What is not broadcast:
  "mouse reports, password entry, the companion keyboard", and focus reports
  and anti-idle are written with `broadcastAllowed:NO`.
- Passwords from the password manager are not blindly broadcast.
  `iTermBroadcastPasswordHelper` probes each target's echo, and warns "The
  following sessions to which input is broadcast do not appear to be at a
  password prompt: …" *(from source)*. This followed
  [#6294 "Broadcast sends passwords in clear to other tabs"](https://gitlab.com/gnachman/iterm2/-/issues/6294)
  and [#9094](https://gitlab.com/gnachman/iterm2/-/issues/9094).
- Clear and Reset ask "Clear in All Broadcasted-to Sessions?" /
  "Reset in All Broadcasted-to Sessions?" *(from source)*.

**How targets are chosen:** from the Shell ▸ Broadcast Input submenu
([menu docs](https://iterm2.com/documentation-menu-items.html)):
- "Send input to current session only": "The default setting."
- "Broadcast to all panes in all tabs": "Anything you type on the keyboard goes
  to all sessions in this window."
- "Broadcast to all panes in current tab": "Anything you type on the keyboard
  goes to all sessions in this tab."
- "Toggle broadcast input to current session": "Toggles whether this session
  receives broadcasted keystrokes within this window." This is also in the
  session's context menu *(from source, `contextMenuToggleBroadcastingInput`)*.
- The submenu opens with the warning "These options allow you to send keyboard
  input to more than one session. Be careful."
- Broadcast never crosses windows. The request for that,
  [#6709](https://gitlab.com/gnachman/iterm2/-/issues/6709), is open.
- Choosing "current tab" again toggles just that tab, so several tabs can each
  be broadcasting *(from source, `setBroadcastMode:`)*.
- The default shortcuts are Cmd+Shift+I (all tabs) and Cmd+Opt+I (current tab),
  as cited in [Ghostty discussion #3227](https://github.com/ghostty-org/ghostty/discussions/3227)
  and [#11440](https://gitlab.com/gnachman/iterm2/-/issues/11440). These were not
  checked against the source.

**How it is shown:**
- A **confirmation** when going from off to on, which can be silenced
  permanently. It names the scope and counts the targets: "Keyboard input will
  be sent to %ld panes across all tabs in this window." *(from source,
  [iTermBroadcastInputHelper.m](https://github.com/gnachman/iTerm2/blob/master/sources/InputBroadcasting/iTermBroadcastInputHelper.m))*.
- A per-session corner indicator: SF Symbol `dot.radiowaves.left.and.right` for
  sessions that send and receive, with the tooltip "Keyboard input gets
  broadcast to other sessions.", and `dot.radiowaves.right` for receive-only,
  "…but this session is not an input source for broadcasting (anything you type
  here stays here)." *(from source,
  [iTermIndicatorsHelper.m](https://github.com/gnachman/iTerm2/blob/master/sources/Drawing/iTermIndicatorsHelper.m))*.
- Optional "Show Background Pattern Indicator": "sessions receiving broadcast
  input get an obnoxious red-stripe background" (menu docs).

**Known problems and requests** (from the [GitLab tracker](https://gitlab.com/gnachman/iterm2/-/issues/?search=broadcast)):
- Users cannot tell which mode they are in.
  [#6007](https://gitlab.com/gnachman/iterm2/-/issues/6007): "I often switch
  between 'send input to all tabs' and 'send input to all panes in this tab' and
  struggle with being able to tell which mode I'm in."
- Groups.
  [#5639 "Broadcast groups"](https://gitlab.com/gnachman/iterm2/-/issues/5639),
  [#3372 "multiple but not all tabs"](https://gitlab.com/gnachman/iterm2/-/issues/3372),
  and [#10174](https://gitlab.com/gnachman/iterm2/-/issues/10174), which asks for
  coloured tabs: "if I forget 3, I am getting diverging input".
- **A separate input window.**
  [#12396 "Add a control window for the 'Broadcast input' feature"](https://gitlab.com/gnachman/iterm2/-/issues/12396)
  (2025) describes toggling broadcast off and on just to type a per-VM number,
  and proposes an input window that "becomes the main input window. Everything
  typed in to this input window is transmitted to the other sessions … but each
  individual session can be clicked in to to allow for individual changes".
- Remote vim opens in Replace mode under broadcast
  ([#3329](https://gitlab.com/gnachman/iterm2/-/issues/3329)). Tilix has the same
  report.
- Broadcast tmux messages break remote tmux
  ([#7786](https://gitlab.com/gnachman/iterm2/-/issues/7786)).
- Escape sequences leak to other windows with broadcast off
  ([#12752](https://gitlab.com/gnachman/iterm2/-/issues/12752), 2026).

## Windows Terminal

**Where the user types:** in any pane of a broadcasting tab.

**What is sent:** keys and characters re-encoded per target. Each control raises
`KeySent`/`CharSent`/`StringSent`. The tab calls `Pane::BroadcastKey` →
`RawWriteKeyEvent(vkey, scanCode, modifiers, keyDown)` on every other non-read-only
control, so **each target encodes the key in its own mode**. Strings go out with
`RawWriteString` *(from source,
[Pane.cpp](https://github.com/microsoft/terminal/blob/main/src/cascadia/TerminalApp/Pane.cpp),
[Tab.cpp](https://github.com/microsoft/terminal/blob/main/src/cascadia/TerminalApp/Tab.cpp))*.
- Paste was added late, and only the source applies bracketed paste: "The
  sending control does get to do the bracketed paste thing. The others however
  just get the `RawWriteString`"
  ([#15812](https://github.com/microsoft/terminal/issues/15812)).
- Mouse input is not broadcast. A reviewer asked about it and got no answer
  ([PR #14393](https://github.com/microsoft/terminal/pull/14393)).

**How targets are chosen:** all panes in the current tab, nothing else.
"When broadcast mode is enabled, all input sent to the pane will be sent to all
panes in the same tab"
([actions docs](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions)).
Read-only panes are skipped.
- The [draft spec](https://github.com/microsoft/terminal/blob/main/doc/specs/drafts/%232634%20-%20Broadcast%20Input/%232634%20-%20Broadcast%20Input.md)
  weighed three models, left the choice open ("**TODO!**: Make a decision."), and
  shipped only `scope: tab`:
  - iTerm2-like per-tab modes;
  - a single window-wide "broadcast set" of panes;
  - a hybrid.
- The spec's discussion of groups: "how do we differentiate these different
  groups to the user? … The UI for this would certainly get complex fast."
- The spec rejected SecureCRT's chat window: "This seemed like a less ergonomic
  solution, so it was not seriously considered."

**How it is shown:**
- "An icon in the tab is used to indicate when this mode is active". It is a
  NetworkTower-style Segoe glyph, per the spec.
- Receiving panes get a border in a variant of the system accent colour
  (`SystemAccentColorDark2/Light2`), distinct from the active pane's border
  (PR #14393; `_ComputeBorderColor` in Pane.cpp).
- Unfocused broadcast panes keep their cursors blinking (#15812).

**How it is started and stopped:** the `toggleBroadcastInput` action
("Toggle broadcast input to all panes" in the command palette). It has an ID but
no default key in the docs.

**Known problems:**
- [#16287 "Paste doesn't always work as expected in broadcasted panes"](https://github.com/microsoft/terminal/issues/16287)
  (open): Ctrl+V "pastes into _some_ of the broadcast group panes", right-click
  pastes into one pane, and holding Ctrl+V crashed it.
- [#20164](https://github.com/microsoft/terminal/issues/20164) (open, 2026):
  "Paste displays a warning dialog if the *active control* isn't using
  bracketed paste; this means that a broadcast group containing one BP and one
  non-BP control will display NO warning". Drag/drop path translation is also
  not per-target.
- Open requests:
  [#16593 tabs, not just panes](https://github.com/microsoft/terminal/issues/16593)
  and [#17011 manually select panes](https://github.com/microsoft/terminal/issues/17011).
  The megathread is [#16600](https://github.com/microsoft/terminal/issues/16600).

## Warp

**Where the user types:** in one session's input editor. Warp's blog says it
syncs **buffer contents, not keys**: "We're only syncing the input buffer text
across all synced terminals", and "we force the input buffers of all synced
inputs to become the same as soon as you begin syncing those inputs"
([blog](https://www.warp.dev/blog/warped-expectations-the-iceberg-of-ux-ambiguity-behind-synced-inputs)).
- Only the focused session shows a cursor and runs completions and
  autosuggestions.
- "When a session is running a long-running or interactive command, Warp falls
  back to broadcast-input behavior", meaning key bytes (blog).
- The team considered a separate "super" input floating outside the sessions and
  rejected it as costly for too little value (blog).
- The [docs](https://docs.warp.dev/terminal/entry/synchronized-inputs) say the
  whole-buffer approach suits whole commands better than editing parts of a
  command. In vim mode, sync "applies only to tabs running that same editor
  type".

**How targets are chosen:** two scopes. "Synchronize All Panes in All Tabs",
and "Synchronize All Panes in Current Tab" (⌘⌥I, or Ctrl+Alt+I). These are in
Edit ▸ Synchronize Input and the command palette (docs).

**How it is shown:** a chain icon on each synced tab, according to a Warp staff
reply in [#3713](https://github.com/warpdotdev/Warp/issues/3713). The docs do not
describe an indicator.
- Users asked for all cursors to blink, iTerm2-style (#3713).
- They also asked for dimmed inactive panes to undim while syncing
  ([#3666](https://github.com/warpdotdev/Warp/issues/3666)).

**How it is started and stopped:** the same shortcut, or "Stop Synchronizing Any
Panes".
- [#10662 "Reduce accidental synchronized input activation"](https://github.com/warpdotdev/Warp/issues/10662)
  (open) proposes removing the default shortcut. It also proposes clearing sync
  state when a tab drops to one pane, "so newly re-split panes do not inherit
  stale sync state".
- [#3437](https://github.com/warpdotdev/Warp/issues/3437): the current-tab scope
  leaks to other tabs that also have it on.

## kitty

**Where the user types:** in a **separate window** opened by the `broadcast`
kitten. "whatever you type in the newly created window will be sent to all kitty
windows"
([docs](https://sw.kovidgoyal.net/kitty/kittens/broadcast/)).
- It is set up as a mapping, for example
  `map f1 launch --allow-remote-control kitten broadcast`.
- The window prints "Type the text to broadcast below, press Ctrl+Esc to quit:"
  and keeps a local echo of the current line with a minimal line editor. Enter
  starts a new line *(from source,
  [main.go](https://github.com/kovidgoyal/kitty/blob/master/kittens/broadcast/main.go))*.

**What is sent:** a mix of text and keys *(from source)*:
- Text, including IME text and pasted text, is sent as text. Pasted text is not
  wrapped in bracketed paste, because the payload does not set
  `bracketed_paste`.
- Enter is sent as `\r`, Ctrl+C as `\x03` and Ctrl+D as `\x04`.
- Every **non-text key** (arrows, function keys, Tab with modifiers…) is
  forwarded as a key event. Each target re-encodes it for its own mode with
  `w.encoded_key(data)` in
  [send_text.py](https://github.com/kovidgoyal/kitty/blob/master/kitty/rc/send_text.py).
- Ctrl+C broadcast was added by request
  ([#3956](https://github.com/kovidgoyal/kitty/pull/3956)).

**How targets are chosen:** by the kitten's command-line options, fixed for the
session. The default is all windows except the broadcast window itself
(`exclude_active`).
- `--match`/`-m` uses kitty's window-match syntax (`title:`, `cwd:`, `cmdline:`,
  `env:`, `var:`, `state:` …).
- `--match-tab`/`-t` matches tabs. The docs give
  `--match-tab state:focused` for "current tab only".

**How it is shown:** while the session is active, every target window draws its
cursor as if focused (`render_unfocused_cursor = True`), and this is cleared at
session end *(from source, send_text.py `session:start`/`session:end`)*. There
is no border or badge.

**How it is started and stopped:** the mapped key starts it.
`--end-session` (default Ctrl+Esc) ends it. `--hide-input-toggle` (default
Ctrl+Alt+Esc) stops the broadcast window echoing what is typed, "Useful while
typing a password".
- Ctrl+Esc was swallowed by the Xfce desktop; the answer was to pass
  `--end-session alt+esc` in the mapping
  ([#6974](https://github.com/kovidgoyal/kitty/issues/6974)).
- The cursor drawing confused at least one user
  ([#4030](https://github.com/kovidgoyal/kitty/issues/4030): "the cursor
  highlight was messed up here so it looked like it wasn't moving").

## Tabby

**Where the user types:** in the focused pane or tab. Tabby calls the mode
"Focus all panes/tabs (broadcast)".

**What is sent:** the source frontend's `input$` stream (bytes after the source
xterm.js has encoded them), forwarded with `sendInput` to each other tab *(from
source,
[multifocus.service.ts](https://github.com/Eugeny/tabby/blob/master/tabby-terminal/src/services/multifocus.service.ts))*.
- Ctrl-keys were reported not to broadcast
  ([#7957](https://github.com/Eugeny/tabby/issues/7957), open).
- An open PR fixes hotkey and paste handling
  ([#11882](https://github.com/Eugeny/tabby/pull/11882)).

**How targets are chosen:** all panes in the split tab, or all terminal tabs.
- Hotkeys: Ctrl+Shift+I and Ctrl+Alt+Shift+I (⌘⇧I and ⌘⌥⇧I on macOS) *(from
  source,
  [config.ts](https://github.com/Eugeny/tabby/blob/master/tabby-terminal/src/config.ts))*.
- The tab context menu has "Focus all tabs" and "Focus all panes".

**How it is shown:**
- All-tabs mode puts a 5 px red border around the whole app and a red banner at
  the top: "Broadcast mode. Click anywhere to cancel."
- Panes mode draws every pane as focused (`_allFocusMode`) and shows no banner
  *(from source)*.

**How it is stopped:** any left click in a terminal, or the terminal losing
focus (`blurred$` → `cancel()`). So it ends by accident.
[#9101 "Broadcast mode 'disappears' when switching between apps using CMD+TAB"](https://github.com/Eugeny/tabby/issues/9101)
is open, and a third-party `tabby-multiexec` plugin was written to make it
"sticky".

## Hyper

Hyper has no built-in broadcast. The
[hyper-broadcast](https://github.com/chabou/hyper-broadcast) plugin
"broadcast[s] user inputs to multiple terms".
- Its hotkeys are `selectCurrentPane`, `selectCurrentTabPanes`, `selectAllPanes`
  and `toggleCurrentPane`.
- The indicator is a 10 px red dot at the top right of each pane (configurable
  `indicatorStyle`).
- How keys and paste are forwarded was not checked.

## WezTerm

WezTerm has no built-in broadcast.
[#2658 "duplicate input to multiple panes"](https://github.com/wezterm/wezterm/issues/2658)
is open. Wez: "No, wezterm doesn't have this feature", then "I personally have no
plans to implement this any time soon." Users get it by running tmux or byobu
inside WezTerm, or from third-party Lua plugins, which were not checked.

## tmux

**Where the user types:** in the active pane.

**What is sent:** keys, each re-encoded per pane. `window_pane_key` calls
`window_pane_copy_key`, which calls `input_key_pane(loop, key)` for each other
pane, so every pane encodes the key in its own modes.
- Pastes go through `window_pane_copy_paste`, which writes the same bytes.
- Mouse events are not copied.
- Panes are skipped if they are in a mode (copy mode etc.), have `PANE_INPUTOFF`
  set, or **are not visible because another pane is zoomed** *(from source,
  [window.c](https://github.com/tmux/tmux/blob/master/window.c))*.

**How targets are chosen:** the `synchronize-panes` option: "Duplicate input to
all other panes in the same window where this option is also on (only for panes
that are not in any mode)" ([tmux.1](https://github.com/tmux/tmux/blob/master/tmux.1)).
Since tmux 3.2 it is a pane option, so it can be set per pane, and `set -U`
unsets it on all panes ([CHANGES](https://github.com/tmux/tmux/blob/master/CHANGES)).

**How it is shown:** since 3.2, the default `pane-active-border-style` turns the
active pane's border red when `synchronize-panes` is on (CHANGES; current
default `#{?synchronize-panes,themered,…}` in
[options-table.c](https://github.com/tmux/tmux/blob/master/options-table.c)).
Anything more is user configuration with the `#{pane_synchronized}` format, as
in the tmux.conf snippet that colours the window status red, quoted in WezTerm
#2658.

**How it is started and stopped:** `setw synchronize-panes [on|off]`. There is
no default key binding.

## Zellij

**Where the user types:** in the focused pane.

**What is sent:** the client's key, as both raw bytes and a parsed key, written
to every pane of the tab with `write_to_terminals_on_current_tab`. This includes
floating panes and hidden stacked panes *(from source,
[tab/mod.rs](https://github.com/zellij-org/zellij/blob/main/zellij-server/src/tab/mod.rs))*.

**How targets are chosen:** all panes of the tab, except panes declared
`exclude_from_sync` in a layout
([#2285](https://github.com/zellij-org/zellij/issues/2285)).
[#404 "select individual panes"](https://github.com/zellij-org/zellij/issues/404)
is open.

**How it is shown:** the tab's name gets " (SYNC)" in the tab bar *(from source,
`default-plugins/bars/src/tab_bar/tab.rs`)*.
[#2838 "highlight all panes 'participating' in sync"](https://github.com/zellij-org/zellij/issues/2838)
is open: "the only indicator is on the tab bar".

**How it is started and stopped:** `ToggleActiveSyncTab`, bound to `s` in Tab
mode (Ctrl+t then s by default) *(from source,
`zellij-utils/assets/keybinds/default.kdl`)*. The status bar has a tip: "Sync a
tab and write keyboard input to all its panes with …".

**Known problems:**
[#3458 "Fullscreen should temporarily disable 'sync'"](https://github.com/zellij-org/zellij/issues/3458)
(open). The scenario: two redundant servers synced, one pane fullscreened to
reboot it, and the hidden one reboots too. "Sending commands to panes you can't
see is not a safe default." Others replied that changing presentation should not
change sync state.

## Ghostty

Ghostty has no broadcast in a release.
- [Discussion #3227](https://github.com/ghostty-org/ghostty/discussions/3227)
  (opened 2024-12-27) asks for "the ability to send the same input to multiple
  panes in the current active tab".
  - Commenters cite iTerm2's two scopes and keys, tmux, Tilix, kitty and Konsole.
  - One user ("Spiral90210") does not care where the cursor is.
  - Two (memco, Spiral90210) want focus to return to the last active pane when
    broadcast is turned off.
  - YLivay notes that multi-cursor display is "a big ask".
  - Visual indication and groups are hardly discussed.
  - The thread was locked in March 2025 and reopened on 2026-09-30, when jcollie
    pointed to PR #13745 as showing "some good potential".
- [PR #10531](https://github.com/ghostty-org/ghostty/pull/10531), a global
  `toggle_broadcast`, was closed unmerged as a drive-by PR.
- [PR #13745](https://github.com/ghostty-org/ghostty/pull/13745) (open as of
  2026-11-12) uses **numbered groups** instead of one switch:
  - up to 16 groups, which may span splits, tabs and windows;
  - each group has its own border colour (`broadcast-group-colors`, with defaults
    ordered so adjacent numbers differ);
  - modifier+click (default super+shift on macOS, ctrl+shift on GTK) adds or
    removes a pane, joining the focused pane's group or starting a new group;
  - `toggle_broadcast_group:N` (cmd+ctrl+digit or ctrl+shift+digit) toggles the
    focused pane in group N, and `clear_broadcast_groups` clears all groups;
  - the PR description does not say which inputs (paste, IME, mouse) are
    broadcast.

## SecureCRT (for contrast: a separate input box)

Out of the main scope, but it is the established "separate box" design, and the
Windows Terminal spec cites it. The Command Window (formerly the "Chat window")
"provides a mechanism for composing a line (or more) of text before sending to
the remote system".
- Text is "only sent to the remote when you press the **ENTER** key".
- Ctrl+Enter adds lines.
- It has command history.
- Right-click ▸ "Send Commands to All Sessions" sends each command "to every tab
  in the SecureCRT window".
- Locked sessions are excluded, "which makes it possible to send commands to a
  subset".
- "Commands can be sent to the active session, all sessions, selected tab groups,
  or visible sessions".
- A "Send characters immediately" mode handles Ctrl+C, vi and tab completion.

Sources: [VanDyke tip](https://vandyke.com/support/tips/chatsendcom.html) and
[Command window automation](https://vandyke.com/support/scripting/scripting-examples/command-window-automation.html).

---

## Patterns

**1. Where the user types.** Nearly everyone has the user type into a real
session and mirrors that input:
- Terminator, Tilix, Konsole, iTerm2, Windows Terminal, Warp, Tabby, tmux,
  Zellij, Hyper's plugin, and Ghostty's PR.

Separate input surfaces are the minority:
- kitty, a separate terminal window with a one-line local echo;
- SecureCRT, a line-composing Command Window.

Others considered and rejected one:
- Warp, a floating "super" input, as too costly;
- Windows Terminal, the chat window, as "less ergonomic".

Users still ask for one, because mirroring makes per-host differences awkward
(iTerm2 #12396). Konsole and iTerm2's asymmetric API mode sit in between: one
designated source session that is not echoed back.

**2. What is sent.** There are three models:
- **Key events re-encoded per target:** Terminator, Tilix, Windows Terminal,
  tmux, and kitty for non-text keys. Each target applies its own cursor-key and
  keypad modes.
- **The source's encoded bytes:** iTerm2, Konsole, Tabby. These can send the
  wrong encoding to a target in a different mode. Konsole's code also forwards
  the source emulator's own replies.
- **Lines or buffers:** SecureCRT sends lines; Warp syncs the shell-input buffer
  and falls back to keys inside running programs.

Where these differ:
- **Paste** is where the implementations differ and break. Terminator lets each
  target paste itself; Windows Terminal brackets only on the source and has
  open paste bugs; kitty sends paste unbracketed.
- **IME/compose** is broken in the key-event designs (Terminator docs, #853;
  Tilix #351).
- **Mouse** is never broadcast.
- **Passwords:** only iTerm2 guards password-manager passwords, with an echo
  probe; Terminator's answer is that the receiver must hide its input.

**3. How targets are chosen.**
- The common pair is "all panes in this tab" and "all panes in all tabs of this
  window": iTerm2, Warp, Tabby. Windows Terminal, tmux and Zellij offer only
  the tab.
- Per-pane opt-out: iTerm2's toggle, Tilix's override button, tmux's pane
  option, Zellij's layout flag.
- Explicit selection: Konsole's filterable checklist dialog, kitty's `--match`
  expressions.
- Named or numbered groups that may span tabs and windows: Terminator, Ghostty
  PR #13745. Users ask for groups wherever they are missing (iTerm2 #5639,
  #3372, #10174; Windows Terminal spec).
- Scope boundaries differ:
  - Hidden panes receive in Terminator and Zellij, which is the subject of a
    safety complaint (#3458).
  - tmux skips panes hidden by zoom.
  - iTerm2 never crosses windows.

**4. How it is shown.** There are three layers, used in different combinations:
- On the targets: a border colour (Windows Terminal accent, Ghostty group
  colours, tmux's red active border), a background pattern (iTerm2 stripes,
  optional), a corner icon (iTerm2), titlebar colour (Terminator red/blue/grey),
  a per-terminal toggle icon (Tilix), or all cursors drawn focused (kitty,
  Windows Terminal, Tabby panes).
- On the tab: an icon (Windows Terminal, Konsole on the source, Warp's chain) or
  text (Zellij " (SYNC)").
- Whole-window alarm: Tabby's red border and banner, iTerm2's confirmation
  dialog that counts targets.

The repeated complaint is that the indicator is too weak or does not say the
scope:
- "struggle with being able to tell which mode I'm in" (iTerm2 #6007);
- "the only indicator is on the tab bar" (Zellij #2838);
- Terminator removing its keys because there was no indicator;
- Tilix #134.

**5. How it is started and stopped.**
- Usually by a toggle key plus a menu item, and turned off by the same toggle.
- Several projects **removed or withheld default keys because broadcast started
  by accident**: Terminator (2020), Warp #10662, Tilix (none by default), tmux
  (none). iTerm2 confirms on enable instead.
- Stopping by accident is the opposite failure: Tabby cancels on any click or
  focus loss, and #9101 complains about it.
- kitty's session lasts exactly as long as its window is open.

**6. Recurring problems.**
- Forgetting broadcast is on, or not knowing its scope.
- Accidental activation.
- Sending to unseen sessions.
- Passwords echoed in clear where the target is not at a prompt.
- Paste inconsistency.
- IME loss.
- Mode-dependent oddities (remote vim starting in Replace mode in iTerm2 #3329
  and Tilix #888).
- Per-host variations, which users solve by toggling off and on, or with
  "insert terminal number" helpers (Terminator, Tilix).

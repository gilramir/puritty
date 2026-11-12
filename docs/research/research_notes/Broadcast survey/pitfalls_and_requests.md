# Broadcast input: pitfalls, user stories and requests

Research notes, gathered 2026-11-12. This file covers what goes wrong with
broadcast input (typing once into several sessions), what users ask for, and
the design reasoning vendors have published. Other notes catalogue how each
program presents the feature. Sources are linked inline. Where something could
not be verified, the text says so.

## 1. Feature requests and what users say they want

### Ghostty discussion #3227, "Send input to multiple panes"

<https://github.com/ghostty-org/ghostty/discussions/3227>. Opened 2024-12-27,
415 upvotes and 15 top-level comments when read (2026-11-12).

- The request: "It would be great to have the ability to send the same input to
  multiple panes in the current active tab", modelled on iTerm2.
- Use cases given:
  - "input the same command across multiple ssh sessions", including network
    switches in HA or stacked setups that do not sync their config
    (MassimilianoPasquini97).
  - A network engineer who "often ssh to multiple switches and routers. Each
    connection in its own pane" and wants to "get rid of additional tmux layer"
    (darvad).
  - "sweeping dependency updates or go versions in 15+ repos. Just need to have
    whatever I've typed be sent into all panes in the visible tab. Don't care
    where the cursor is" (Spiral90210).
  - "huge time saver for me as a dev ops" (YLivay).
  - Skeeve built a tmux wrapper, `tmh`, for "fixed combinations of hosts".
- Several commenters call it the last iTerm2, Konsole or Tilix feature keeping
  them from switching. Collaborators locked the thread over "+1" spam
  (00-kat, jcollie). On 2026-09-30 jcollie unlocked it and pointed to PR #13745.
- Ghostty's existing `all:` keybind prefix was suggested as a substitute. It
  was rejected because it applies one *action* to every surface rather than
  routing typed input.
- **PR #13745** (open, 2026-08-11), "add broadcast support to sync across panes",
  <https://github.com/ghostty-org/ghostty/pull/13745>:
  - Up to 16 numbered groups, each shown by "a colored border". A group "can
    contain panes from different splits, tabs, and windows."
  - You add a pane with a modifier-click or with `toggle_broadcast_group:N`, and
    remove all groups with `clear_broadcast_groups`.
  - The digit bindings deliberately accept both physical and Unicode digit keys
    "Thus keyboard layouts with shifted digits (for example, AZERTY) operate
    correctly."
  - It replaced an earlier closed PR,
    [#10531](https://github.com/ghostty-org/ghostty/pull/10531). That PR had a
    single global `toggle_broadcast` that skipped read-only surfaces and exited
    children.
  - The PR author reports daily use and says he "haven't used more than 3"
    groups.
  - The PR text does not say whether paste or mouse input is broadcast.

### Windows Terminal #2634 and follow-ups

The original request,
[#2634](https://github.com/microsoft/terminal/issues/2634) (2019-09-01), was to
"broadcast input to all the panes in current tab, or all tabs", because "It is
useful to maintain a series of servers with the same role". It cited iTerm2,
ConEmu and SecureCRT.

- **What shipped.** [PR #14393](https://github.com/microsoft/terminal/pull/14393)
  was merged 2023-07-19 and released in 1.19. It covers the tab scope only. The
  PR says: "Consensus from community feedback is that the whole of that spec is
  _nice to have_, but what REALLY matters is just broadcasting to all the panes
  in a tab." It is shown by an icon in the tab, and the borders of the
  broadcast-to panes use `SystemAccentColorDark2`/`Light2`.
- **Ship-list bugs from the bug bash**
  ([#15812](https://github.com/microsoft/terminal/issues/15812)):
  - "Broadcast border doesn't appear when you make new panes, but they ARE
    broadcasted-to!"
  - Cursors in broadcast-to panes did not blink, or did not stop blinking.
  - Context-menu paste was not broadcast.
- **Across tabs.** [#16593](https://github.com/microsoft/terminal/issues/16593)
  asks to "broadcast keyboard input to multiple tabs at once … Ideally there
  would be some options for choosing which tabs." The reporter notes that many
  such requests had been closed as duplicates of the panes-only issue. Megathread:
  [#16600](https://github.com/microsoft/terminal/issues/16600).
- **Several groups in one tab.**
  [#17011](https://github.com/microsoft/terminal/issues/17011) asks for "half of
  my windows be one broadcast group and half of other in second or third
  broadcast windows but in same tab."
- **Paste** ([#16287](https://github.com/microsoft/terminal/issues/16287), open):
  - Ctrl+V reached a random subset of panes ("pastes in 1&2 … pastes in 2&3 …
    pastes in 3"), right-click pasted only into one pane, and repeated pastes
    crashed the app (stevelipinski, MateuszBeru).
  - In 2026 paste was made to broadcast (#19879). A user who administers Linux
    servers then asked for a setting to keep paste local. Their reason:
    "multiline pastes are not always handled correctly in the non-focused panes.
    Commands can end up being processed differently across sessions,
    potentially causing unintended execution."
  - DHowett declined: "I'm not introducing a 'broadcast most events but not all
    of them' mode to work around what is essentially _a bug_ in the handling of
    bracketed paste across multiple panes."
  - [#20164](https://github.com/microsoft/terminal/issues/20164) records the
    bracketed-paste divergence: "Paste displays a warning dialog if the *active
    control* isn't using bracketed paste; this means that a broadcast group
    containing one BP and one non-BP control will display NO warning". It also
    notes that drag/drop path translation "broadcasts the same input for all
    panes even if their path translation styles differ".
- **Exit crashes.**
  [#18071](https://github.com/microsoft/terminal/issues/18071): broadcasting
  `exit` / Ctrl+D to several panes crashed the whole app.
  [#18532](https://github.com/microsoft/terminal/issues/18532): "It closes all of
  my Windows Terminal windows" after exiting broadcast SSH sessions to EC2 hosts.
- **Accessibility.** Microsoft's
  [terminal-a11y-2023.md](https://github.com/microsoft/terminal/blob/main/doc/terminal-a11y-2023.md)
  lists broadcast input as useful "for users with mobility issues, as it is time
  consuming to write commands to multiple sessions quickly".

### kitty (broadcast kitten)

- [#902](https://github.com/kovidgoyal/kitty/issues/902) (2018): "think 60 remote
  machines where I need to run identical commands … when I don't want to use
  fabric or similar." kovidgoyal pointed at `send-text`, which later became the
  broadcast kitten. A user called the kitten "pretty awkward" because input is
  typed into a separate window and by default goes to all windows in all tabs.
  kovidgoyal replied that you can choose targets. Backspace was not sent at
  first and was fixed after the report.
- [#2962](https://github.com/kovidgoyal/kitty/issues/2962): asks for all panes of
  the active tab to join a group, the mode to persist when switching away, and
  "A visual indicator … on the panes joined-in a broadcast group." Another user:
  "It's quite dangerous to broadcast it to all windows on all tabs." The fix
  was `--match-tab`.
- [#6974](https://github.com/kovidgoyal/kitty/issues/6974): the end-broadcast key
  (Ctrl+Esc) was captured by the desktop (Xfce), so the user could not leave the
  mode until they found `--end-session`.
- The kitten's docs
  (<https://sw.kovidgoyal.net/kitty/kittens/broadcast/>) offer a
  `--hide-input-toggle`, "Useful while typing a password". Text goes "to all
  windows, unless one of the matching options is specified."

### WezTerm, Zellij, Tabby, Alacritty

- **WezTerm** [#2658](https://github.com/wezterm/wezterm/issues/2658), open since
  2022. wez: "I personally have no plans to implement this any time soon."
  Users name tmux, Terminator, kitty and screen, and one posts a screenshot of
  "a zoo of panes". Workarounds: Byobu inside WezTerm, or the third-party
  `sync-panes.wez` plugin.
- **Zellij**:
  - [#2838](https://github.com/zellij-org/zellij/issues/2838): with sync on, "the
    only indicator is on the tab bar", so the user asks for "a harder to miss
    highlight of all the panes".
  - [#404](https://github.com/zellij-org/zellij/issues/404): select individual
    panes for sync, shown by border colour.
  - [#3454](https://github.com/zellij-org/zellij/issues/3454): start a layout with
    sync already on, to SSH to two servers from a `.desktop` file.
  - #3458 is under §2.
- **Tabby**:
  - [#7957](https://github.com/Eugeny/tabby/issues/7957): broadcast sent only
    plain characters. Ctrl+key, paste, Home/End did not go out. One user saw
    "great confusion and errors while editing files".
  - [#9101](https://github.com/Eugeny/tabby/issues/9101) and
    [#8800](https://github.com/Eugeny/tabby/issues/8800): the mode silently ends
    when the app loses focus. A MobaXterm convert wants "sticky" broadcast and
    per-pane exclusion, and a third-party `tabby-multiexec` plugin was written
    for exactly that.
  - [#9668](https://github.com/Eugeny/tabby/issues/9668): "Most of the time we
    need to send a lot of lines or a very long commands", so paste matters.
- **Alacritty**: no broadcast request turned up in a GitHub issue search. It
  has no tabs or splits, so this is expected. Not investigated further.

### Konsole "Copy Input To"

- [KDE 330559](https://bugs.kde.org/show_bug.cgi?id=330559) (confirmed): with
  "5 connection to the same remote host", the tab picker lists tabs only by
  title and creation order. After rearranging, you cannot tell which is which.
  Maintainer: "making it worthless when the names are the same."
- [KDE 509299](https://bugs.kde.org/show_bug.cgi?id=509299) (2025): after
  closing and re-splitting panes, the tab still shows the copy-input asterisk,
  but commands reach only some panes. The dialog also shows varying state.
- [KDE 191648](https://bugs.kde.org/show_bug.cgi?id=191648): users "switch back
  and forth between input to all tabs and input to only one tab". The modal
  dialog makes that slow.

### Terminator (groups)

- [#540](https://github.com/gnome-terminator/terminator/issues/540): "ssh to 30
  servers with different names at the same time". The user wants to insert a
  per-terminal *name* (e.g. `user1@server1.com`) into broadcast input, because
  "Insert Terminal Number" changes when the layout changes. This is per-session
  substitution inside a broadcast.
- [#532](https://github.com/gnome-terminator/terminator/issues/532): turning on
  group broadcast in one group seemed to turn it on for all groups, and the
  maintainer could not reproduce it.
  [#685](https://github.com/gnome-terminator/terminator/issues/685): asks for a
  quicker way to form groups, and an undo.
- [#947](https://github.com/gnome-terminator/terminator/issues/947): broadcast
  limited to a saved layout.
- **Duplicated keystrokes.** Others see `llss` for `ls`:
  [#78](https://github.com/gnome-terminator/terminator/issues/78),
  [#504](https://github.com/gnome-terminator/terminator/issues/504), #596, #623,
  #704, #719, #771, #788. It depends on the desktop and input method (KDE Xorg).
  The maintainer suggests `IBUS_NO_SNOOPER_APPS` and calls it "the bane of my
  existence."
- Other bugs:
  - Compose-key input is not broadcast
    ([#853](https://github.com/gnome-terminator/terminator/issues/853)).
  - Pasting into a maximized terminal while broadcasting segfaults
    ([#1069](https://github.com/gnome-terminator/terminator/issues/1069)).
- **Indicator.** [Launchpad 1375054](https://bugs.launchpad.net/bugs/1375054)
  asks for a "background image or pattern when broadcast_all is active". It was
  never built natively; a "hacky plugin" recolours the background, but "will not
  update the bgcolor of new terminals."

### iTerm2 (GitLab)

- [#3372](https://gitlab.com/gnachman/iterm2/-/issues/3372): broadcast to "1, 2,
  5, 6 but not necessarily all tabs" for a Kafka/ZooKeeper cluster.
- [#5639](https://gitlab.com/gnachman/iterm2/-/issues/5639): broadcast groups:
  "6 panes with 3 on the left and 3 on the right that need their own broadcast
  group".
- [#6007](https://gitlab.com/gnachman/iterm2/-/issues/6007): "I often switch
  between 'send input to all tabs' and 'send input to all panes in this tab' and
  struggle with being able to tell which mode I'm in." It asks for a stripe
  colour per mode.
- [#6709](https://gitlab.com/gnachman/iterm2/-/issues/6709): broadcast across
  windows, for "giving demos in the terminal … one copy of the terminal on my
  laptop screen and one copy … on the projector".
- [#6451](https://gitlab.com/gnachman/iterm2/-/issues/6451) (filed by the
  maintainer): broadcast *commands* such as Clear Buffer, password manager, font
  size, Reset, with a mode "for just the next command".
- [#9094](https://gitlab.com/gnachman/iterm2/-/issues/9094) (closed): send a
  password from the password manager to every broadcast pane at a sudo prompt.
  [#11623](https://gitlab.com/gnachman/iterm2/-/issues/11623): the app crashes
  when doing that in 3.5.1.

## 2. Accidents and dangers

### Reported incidents and near-misses

- **Commands reaching panes that are not visible.** Zellij
  [#3458](https://github.com/zellij-org/zellij/issues/3458):
  - The scenario: two redundant servers with synced input; you full-screen one
    pane to reboot it, and "you have also rebooted a server through a terminal
    that you can't see. Now both halves of the redundant cluster are down".
  - The reporter: "you can't notice you've typed a command into two servers
    instead of one until you've exited fullscreen and by then it may be too
    late". They asked for "safe by default".
  - A Zellij contributor disagreed: with 10–20 IoT targets you cannot see them
    all on a laptop, and changing presentation should not change sync state.
  - tmux behaves as the reporter wants. In tmux's `window.c`,
    `window_pane_copy_key` and `window_pane_copy_paste` skip a pane unless
    `window_pane_is_visible()`, which is false for hidden panes of a zoomed
    window. They also skip panes in a mode (copy mode) and panes with input
    disabled (`select-pane -d`). Read from
    [tmux master](https://github.com/tmux/tmux/blob/master/window.c), 2026-11-12.
- **A password echoed into a forgotten session.** Terminator
  [#744](https://github.com/gnome-terminator/terminator/issues/744):
  - With `broadcast_all` on, a sudo password typed in one terminal reached a
    background terminal with a half-typed line. It was not hidden there and was
    "log[ged] … as raw into sys logs".
  - The maintainer: "this is exactly as expected. The shell, or receiving
    program is responsible for hiding input."
  - [#620](https://github.com/gnome-terminator/terminator/issues/620): broadcast
    was "turned on every time i start terminator", because `broadcast_all` was
    saved in the config.
- **Divergent prompts.** On HN, VintageCool
  [recounts](https://news.ycombinator.com/item?id=15455258) a clusterssh session
  to 40 machines. They typed `yes` to accept host keys, but "I had already
  accepted two of them so now they are spitting out the letter 'y' as fast as
  they possibly can", and output flooded back despite Ctrl+C.
- **Mode stuck on, or invisible.**
  - iTerm2 [#9932](https://gitlab.com/gnachman/iterm2/-/issues/9932): after an
    update the toggle would not turn broadcast off ("stuck in broadcast mode").
  - Windows Terminal (#15812): new panes received broadcast without showing the
    border.
  - Konsole 509299: the indicator showed copy-input on while panes did not get
    input.
  - Not opened (the vendor URL redirects to a login): a Royal TS forum thread,
    which a search summary describes as broadcast still active with its red
    marker gone.
- **Paste reaching an unpredictable subset**: Windows Terminal #16287 (above),
  and Tabby #7957 (paste not sent at all).
- **Exit and crashes**: WT #18071 and #18532, Terminator #1069, iTerm2 #11623.
- **General warnings.**
  - Putorius on ClusterSSH: "I learned this lesson the hard way so you don't
    have to … it usually goes horribly wrong" and "any mistake, mistype or fat
    finger is being propagated also"
    (<https://www.putorius.net/cluster-ssh.html>).
  - iTerm2's manual: "These options allow you to send keyboard input to more
    than one session. Be careful."
    (<https://iterm2.com/documentation-menu-items.html>).
- I found no public postmortem of a production outage caused by broadcast
  input. Searches of Reddit (blocked to fetch), HN and incident write-ups turned
  up only the anecdotes above and general "wrong window" stories.

### Safeguards vendors and users have added

- **Confirmation on enabling** (iTerm2):
  - Moving from off to any broadcast mode shows a warning with OK/Cancel that
    names the scope and the count, e.g. "Keyboard input will be sent to %ld
    panes across all tabs in this window." Source:
    [`iTermBroadcastInputHelper.m`](https://github.com/gnachman/iTerm2/blob/master/sources/InputBroadcasting/iTermBroadcastInputHelper.m).
  - The warning can be silenced permanently (`NoSyncSuppressBroadcastInputWarning`).
  - Users asked for that as early as 2011
    ([#1658](https://gitlab.com/gnachman/iterm2/-/issues/1658)): "fine as
    default, but slightly annoying if you use this on a regular basis".
- **Background pattern** (iTerm2): "sessions receiving broadcast input get an
  obnoxious red-stripe background". It is optional. A top-right broadcast icon
  can be disabled with an advanced setting.
- **Borders and tab icons**:
  - Windows Terminal: an accent-coloured border plus a tab icon.
  - Ghostty PR: a border colour per group.
  - Xshell: "A status indicator appears at the top of each affected session"
    with an "Off" button to exclude it
    ([NetSarang](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/1118601758)).
  - tmux users add their own red status bar with `#{?pane_synchronized,#[bg=red],}`
    (e.g. WezTerm #2658's quoted `tmux.conf`).
- **Exclusion of one session without leaving the mode**:
  - iTerm2 "Toggle broadcast input to current session".
  - ClusterSSH "Unchecking a hostname on the Hosts sub-menu will unplug the host"
    ([README](https://github.com/duncs/clusterssh/blob/master/README)).
  - SecureCRT: locked sessions do not receive the command window's text
    ([VanDyke tip](https://vandyke.com/support/tips/chatsendcom.html)).
  - Xshell "Off" button, MobaXterm per-tab exclusion checkbox (from a Stack
    Overflow question; I did not find it in MobaXterm's own docs), the Tabby
    plugin, and tmux `select-pane -d`.
- **Password safety** (iTerm2):
  - Sending a password-manager entry to broadcast sessions first runs an "echo
    probe" on each session. The setting says it is "used by the password manager
    to ensure you're at a password prompt."
    ([`iTermBroadcastPasswordHelper.m`](https://github.com/gnachman/iTerm2/blob/master/sources/InputBroadcasting/iTermBroadcastPasswordHelper.m),
    advanced setting `echoProbeDuration`).
  - I did not trace what the UI does with sessions that fail the probe.
- **Scope limits as safety**:
  - Termius: "works only with terminals opened in Split View mode and will not
    affect other connections"
    (<https://www.termius.com/blog/broadcast-input>).
  - kitty `--match-tab state:focused`.
  - tmux skips hidden or zoomed panes.
- **Auto-off timeout, sound, confirm-per-command**: none found as a shipped
  feature in any program surveyed, and no explicit request found. Tabby's
  focus-loss auto-off exists, but users experience it as a bug (#8800, #9101).

## 3. Divergence between sessions

How sessions come to differ, by cause:

- **Shell state and line contents**:
  - Terminator #744: a half-typed line in one terminal turned a password into
    a command line.
  - The ClusterSSH README warns that when editing files "lines may not
    necessarily be in the same order".
  - Putorius: "a single comment or blank line can threw the line numbers off."
- **Prompts that differ per host**:
  - The VintageCool host-key story above.
  - sudo prompting on some hosts only: iTerm2's echo probe exists because of it.
  - A tmux guide says broadcasting sudo "will only work if the password prompt
    is consistently handled or if you've configured passwordless sudo"
    ([adhdecode](https://adhdecode.com/articles/tmux/tmux-broadcast-to-all-panes/);
    quoted from a search summary, page not opened).
- **Terminal modes per pane**:
  - Bracketed paste on in one pane but not another (WT #20164).
  - Path translation per profile (WT #20164).
  - tmux re-encodes each copied key against each pane's own modes:
    `input_key_pane()` calls `input_key(wp->screen, …)`, so application cursor
    keys are honoured per pane (tmux `input-keys.c`). A design that copies the
    *bytes* the focused pane produced would send the wrong arrow-key sequences
    to a pane in a different mode.
- **Keyboard layouts and input methods**:
  - ClusterSSH sends X key events. Its changelog has "Totally rework character
    mapping and events to cope with non-QWERTY keyboards" and "Pastes uses a
    strange keyboard layout (Debian bug ID #364565)"
    ([Changes](https://fastapi.metacpan.org/v1/source/DUNCS/App-ClusterSSH-4.16/Changes)).
  - Terminator's duplicated keys come from input-method interaction (#78/#504),
    and its Compose-key sequences are not broadcast (#853).
- **Encodings** (e.g. EUC-KR vs UTF-8 hosts):
  - No primary source found that discusses this for broadcast. Xshell sets
    encoding per session and blames broken Korean on "encoding discordance"
    ([NetSarang](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/31654386)).
  - So the question is whether a broadcast sends characters (encoded per target
    session) or the source session's bytes. None of the docs I read say which.
    This is unverified, and an open question for puritty.
- **Window sizes**:
  - ClusterSSH once set terminal size "only … on last windows" (changelog).
  - A Zellij user with 10–20 targets notes that you cannot see them all on a
    1080p screen.
  - iTerm2 has an advanced setting for whether font-size changes in a
    broadcasting session apply to all of them (`fontChangeAffectsBroadcastingSessions`).
- **Completion**:
  - Warp runs autosuggestions and completions only in the focused session.
    Other sessions only receive buffer updates (see §5).
  - The `hss` tool completes "based on the first server in the list" (per its
    README via search; not opened).
  - Tab completion through a keystroke broadcast runs independently on every
    host, so results can differ. No user report quantifying this was found.

How people cope:

- **Compose a line, then send it**:
  - SecureCRT's command window.
  - Xshell's Compose Bar ("a single line of command") and Compose Pane
    ("multiple lines … send them at once").
  - kitty's separate broadcast window.
  - Microsoft's spec judged SecureCRT's chat window "less ergonomic" (§5).
  - Xshell keeps a separate "Send Key Input to All Sessions" mode because ESC,
    Backspace and Ctrl/Alt keys are "difficult to do through the 'Compose Bar'".
- **A window per host, typed into directly**: ClusterSSH ("All windows may also
  be typed into directly"), Putorius's "click a host's window to type into it
  alone, then click back into the admin console".
- **Per-session substitution**: ClusterSSH's Send menu (hostname, username),
  Terminator #540, and HN joeyoung's per-host paste buffers in tmux
  (<https://news.ycombinator.com/item?id=7276297>).
- **Paste vs keystrokes**: users disagree.
  - One WT user wants paste kept local, as a way to diverge on purpose.
  - Tabby users want paste broadcast, because commands are long.

## 4. What people use it for, how many sessions, and alternatives

- **Cluster and fleet admin, mostly over ssh**:
  - "series of servers with the same role" (WT #2634).
  - Kafka/ZooKeeper (iTerm2 #3372).
  - EC2 instances (WT #18532).
  - HPC nodes (Putorius).
  - "configuring multiple servers identically at the same time, which is a task
    I perform on a weekly basis" (HN justwalt,
    <https://news.ycombinator.com/item?id=25792217>).
  - Recovering 200 Hadoop machines (HN nisa,
    <https://news.ycombinator.com/item?id=39956834>).
  - Running the same Ubuntu update everywhere (Termius; Tabby #9321: "very
    useful to send upgrade commands to multiple servers without getting into
    more complex Ansible actions").
- **Network gear**: switches and routers that have no config sync (Ghostty
  #3227).
- **Comparing output and checks**:
  - "an easy way to run interactive commands on multiple machines", comparing
    speed or output (Tom Ryder, [Arabesque, 2012](https://blog.sanctum.geek.nz/?p=1012)).
  - "execute commands over multiple hosts to make checks" (kitty #2962).
  - "getting a quick visual on a few servers" (HN invertedohm,
    <https://news.ycombinator.com/item?id=8216136>).
- **Local repos and directories**: "15+ repos" (Ghostty), "switch to the same
  directory in all panes" of a 4-pane layout (iTerm2 #1658).
- **Demos** (iTerm2 #6709), **accessibility** (WT a11y doc).
- **How many sessions** (reported, not surveyed):
  - 3–6 panes: iTerm2 #1658, #5639; WT #16287 (3).
  - 4 in a WT tab (#17011).
  - 15+ (Ghostty), 16 is Termius's cap, 30 (Terminator #540; HN antoniomika
    `runner{0..30}`), 40 (HN VintageCool), 60 (kitty #902).
  - csshX: "less that 20 servers at a time (about the limit of what you can
    read on screen at once)" (HN jhickner,
    <https://news.ycombinator.com/item?id=4232916>).
  - Ghostty PR author: no more than 3 groups at once.
- **Alternatives named, and why the terminal is still wanted**:
  - Ansible: HN linsomniac
    (<https://news.ycombinator.com/item?id=21389556>) moved fleet OS updates to
    Ansible for batching, load-balancer drain and health checks.
  - Fabric (kitty #902), Capistrano/Puppet (Tom Ryder: "generally better
    practice").
  - pssh and similar tools (HN res0nat0r's list,
    <https://news.ycombinator.com/item?id=8650240>).
  - tmux `synchronize-panes` and Byobu, used inside terminals that lack the
    feature.
  - Reasons given for staying in the terminal:
    - "pets rather than cattle … For the rare occasions a task needs to be done
      on a variety of machines, clusterssh does perfectly well" (HN iso1631,
      <https://news.ycombinator.com/item?id=25123713>).
    - Interactive or exploratory work, where you watch every host's output.
    - Network devices without an automation agent.
    - Avoiding an extra tmux layer (Ghostty #3227).

## 5. Vendor design rationales

### Microsoft: draft spec "#2634 - Broadcast Input"

Mike Griese, created 2021-03-03, last updated 2022-11-04. Still a draft, at
[`doc/specs/drafts/#2634 - Broadcast Input/#2634 - Broadcast Input.md`](https://github.com/microsoft/terminal/blob/main/doc/specs/drafts/%232634%20-%20Broadcast%20Input/%232634%20-%20Broadcast%20Input.md)
(spec PR #9365). It calls itself "lighter-than-usual … to build consensus on
the design of how the actions should be expressed".

- **Rejected models.**
  - SecureCRT's chat window was judged "less ergonomic", "so it was not seriously
    considered".
  - Terminator groups were judged "a less powerful version".
- **Stories**, taken from iTerm2: current session only; all panes in all tabs;
  all panes in current tab; toggle the current session.
- **Three proposals, all with the same actions**
  (`toggleBroadcastInput` with `scope: window|tab|pane`, and
  `disableBroadcastInput`):
  1. *iTerm2-like modal.* A window flag, plus a per-tab "all panes" flag and a
     per-tab pane set.
     - Con: you "can't broadcast to a subset of panes in inactive tabs".
     - Con: the tab/pane interaction is confusing.
  2. *One broadcast set* across the window.
     - Pro: it can span tabs and extends to groups.
     - Con: you cannot keep separate sets in two tabs, and focus changes alter
       who receives.
  3. *iTerm2 with only per-tab sets.*
- **No decision.** "**TODO!**: Make a decision." What shipped was the tab scope
  only.
- **Open questions it raises**:
  - "Does creating a new split in a pane that's being broadcast to add that pane
    to the broadcast set?"
  - Can a pane be in multiple groups?
  - How to label groups ("[📡: 1]").
  - Window-wide broadcast is a perf worry: "tossing every keystroke across the
    process boundary".
- **What is broadcast.** Keystrokes only: "the `KeySent` and `CharSent` events".
  - Paste is deferred to "Broadcast commands": "Copy doesn't really make sense.
    Paste _does_ though." The spec says this "probably would require its own
    spec."
  - Mouse input is not discussed.
  - Read-only panes do not take broadcast input.
- **Indicators.**
  - A tab icon (Segoe "NetworkTower"), shown even on inactive tabs that contain
    a broadcast-to pane.
  - A variant of the accent colour on the borders of broadcast-to panes, to
    show they are "_not_ the active pane, but they are going to receive input".
  - iTerm2-style stripes were deferred, and a custom pixel shader was suggested.
  - A per-scope colour (iTerm2 #6007) is listed for later.
  - The spec says: "this is supposed to be a quick & dirty spec, so I'm LARGELY
    skipping this."
- **Later practice** (issues above):
  - Paste broadcasting was added in 2026 and still diverges under bracketed
    paste.
  - The team refuses a partial "broadcast most events but not all" mode
    (DHowett, #16287).
  - Implementation notes in #15812 discuss tagging strings with a source
    (`Source::Broadcast`) so a broadcast string is "not accidentally
    rebroadcast". In the current layering the receiving panes get a raw,
    non-bracketed write.

### Warp: "Warped Expectations: The Iceberg of UX Ambiguity Behind Synced Inputs"

David Melvin, 2023-08-10,
<https://warp.dev/blog/warped-expectations-the-iceberg-of-ux-ambiguity-behind-synced-inputs>.

- **The core problem**: "how do we broadcast inputs and still be useful when the
  terminal inputs don't have the same starting state?"
- **Decision: sync the input buffer, not keystrokes.** "We're only syncing the
  input buffer text across all synced terminals."
  - When sync starts, "We force the input buffers of all synced inputs to become
    the same", which removes divergence at the start.
  - During long-running or interactive commands it falls back to raw broadcast.
- **Selection.** Tried several mappings, and chose same indices, with the cursor
  moved to the nearest valid index. The reason: "non-intuitive behavior in the
  terminal can make it easier for users to accidentally run dangerous commands."
- **Completion.** Only the focused session runs autosuggestions and completions.
  The others apply buffer updates.
- **What it gave up.** It accepts being "less 'powerful' than broadcast input"
  in order to optimize for the main use case.
- **Process.** It reframed the request as "how can I run the same command in
  multiple sessions?" A separate "super input" was considered and rejected.
- **Open questions.** Ctrl-R, up-arrow history, and which sessions to sync.
- **Related doc.** Warp's docs say that in vim mode, synced input "will only
  apply to all tabs with that same editor type running"
  (<https://docs.warp.dev/terminal/entry/synchronized-inputs>).

### iTerm2 (George Nachman)

I found no essay by Nachman on broadcast design. What follows is from the
source, the manual and the issues:

- A warning on enabling, which names the scope and the count.
- Stripes that are "obnoxious" by design.
- Per-session toggles, and broadcast "domains" kept disjoint ("Invert it to
  ensure broadcast domains will be disjoint" in `iTermBroadcastInputHelper.m`).
- An echo probe before broadcasting a password.
- Advanced settings for whether Clear Session and font-size changes also apply
  to broadcast-to sessions (`noSyncClearAllBroadcast`,
  `fontChangeAffectsBroadcastingSessions`). These are the "broadcast commands"
  of #6451.
- A Python API example of asymmetric broadcast, from one pane to three, where
  typing in the others stays local
  (<https://iterm2.com/python-api/examples/broadcast.html>).

### Not found / not verified

- No user study or usability test of broadcast input by any vendor.
- No iTerm2 design write-up.
- No source on encodings under broadcast.
- No Reddit threads could be fetched (403).
- Royal TS and MobaXterm exclusion details come only from search summaries.

## Implications for a design

- **Be explicit about scope, and show it on every pane that will receive input,
  not only on the tab.** Every program that showed it only on the tab got a
  request for more (Zellij #2838, kitty #2962, Terminator LP 1375054, iTerm2
  #6007). Some indicator has to show on the receiving panes themselves.
- **The indicator must never be out of step with routing.**
  - WT #15812 (new pane received input without a border) and Konsole 509299
    (asterisk on, input not delivered) are the worst kind of bug here.
  - New tabs or panes need a defined rule: join or not. The WT spec left this
    open.
  - Mode changes should be logged in the session.
- **Do not send to sessions the user cannot see, by default** (Zellij #3458,
  tmux's zoom rule). Or show a count of hidden recipients ("sending to 5; 2 not
  visible"). iTerm2's warning already states a count.
- **Start-up should never restore broadcast silently** (Terminator #620). Leaving
  the mode must always work and be easy to find (kitty #6974, iTerm2 #9932).
- **Decide what crosses**, each separately, and document it:
  - keystrokes
  - paste (WT users split both ways; Tabby users need it)
  - drag/drop
  - mouse (no one asks for it)
  - terminal actions such as clear, reset and font size (iTerm2 #6451)

  WT's history shows that adding paste later, as an afterthought, broke
  workflows and still misbehaves.
- **Encode each key against each target's own state**, as tmux does: application
  cursor mode, bracketed paste, keyboard protocol. Do not copy the focused
  session's output bytes.
  - For puritty's EUC-KR users, the same question decides encodings. Broadcast
    text should be encoded per target session (that session's charset). Raw
    bytes from the source session would be wrong for a different-encoding host.
  - No vendor documents this, so puritty would be first. Its behaviour should
    be tested.
- **Plan for diverging prompts**:
  - A per-session "exclude for now" that does not end the mode (iTerm2, Xshell
    Off button, ClusterSSH unplug).
  - Easy direct typing into one member.
  - Optionally, a guard for secrets: iTerm2's echo probe idea, or refusing to
    broadcast password-manager input to sessions that echo.
- **Line-at-a-time (compose then send) and per-keystroke are both wanted.**
  - Line-at-a-time is safer against divergence and lets the user review the
    line.
  - Per-keystroke is needed for ESC, Ctrl keys, editors and pagers (Xshell keeps
    both).
  - Warp's "sync the buffer" is a third option, but it depends on owning the
    line editor, which puritty does not.
- **Groups across tabs are the long-tail request.** They appear in iTerm2 #3372
  and #5639, WT #16593 and #17011, and Terminator. Ghostty's PR implements
  numbered, coloured groups spanning tabs and windows.
  - If the first version is "this tab only", choose a model that extends to
    groups. The WT spec found Proposal 2 (a set) extends and the modal one does
    not.
  - Group membership needs stable, distinguishable labels: host or session
    name, not position (Konsole 330559, Terminator #540).
- **Per-session substitution** is a recurring ask that can be cheap: insert this
  session's host or name (ClusterSSH Send menu, Terminator #540).
- **Exit and close under broadcast** must be safe. A broadcast `exit` closing
  N sessions at once crashed WT twice (#18071, #18532), and killed every window
  in one case.
- **Warnings that fire every time get silenced** (iTerm2 #1658 in 2011).
  Prefer something that is always visible and states a count, over a modal that
  is dismissed by habit. A confirm-on-enable can be offered as an option.
- **There is no prior art for an auto-off timeout or a sound.** If puritty adds
  one, it is untested territory. Tabby's focus-loss auto-off was experienced as
  a bug, not a feature.

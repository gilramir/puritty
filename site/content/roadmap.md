+++
title = "Roadmap"
+++

puritty is at 0.2.1: its author's daily terminal, with builds for
Windows, RHEL 8 and 9, and Ubuntu 24.04 (and Linux Mint). This is where it
stands, and what comes next.

## Done

- **The terminal core**, tested against libghostty-vt, fuzzed, and run
  against `esctest2`; a renderer of its own for X11 that is fast over the
  network.
- **Input methods** through XIM, with Korean, Japanese and Chinese tested.
- **EUC-KR and CP949** built in.
- **tmux control mode**: run `tmux -CC` and tmux's panes, floating and
  modal panes included, are drawn as puritty's own, with tmux's windows as
  tabs, the mouse on panes, scrollback and selection in each pane, and
  tmux's own screens (its prompt, menus, session tree, copy mode and
  options editor) drawn by puritty, in its look or tmux's, with vi keys
  and tmux's own history at its prompt, completion of commands, options
  and targets, the mouse in its session tree and options editor, and
  tmux's `bell-action` and `visual-bell`. It adapts to each tmux from 2.7
  to 3.8, is checked against every release between, and is tested with
  the server killed, the client cut off and other ways a session goes
  wrong.
- **Inline images**: Sixel, Kitty graphics (Unicode placeholders too) and
  iTerm2 images, in a shell, through tmux and in the panes of `tmux -CC`.
- **Tabs**: colors of your own or per host, renaming, reopening a closed
  tab, and your tabs opened again when puritty starts.
- **Search** in the scrollback.
- **Copy and paste** with both of X's clipboards, and OSC 52 for programs
  that copy for you.
- **The settings window**, in English and Korean, with every change taken
  by every open window at once: fonts, color schemes, your own keys,
  bells and key sounds.
- **Hosts**: a host list with quick connect, hosts kept in the settings and
  read from `~/.ssh/config` and PuTTY's saved sessions, and your recent
  connections in the menus and Windows' taskbar.
- **Windows**: the same terminal, with the ssh client built in, jump hosts,
  keys and agents, a changed host key asked about, and passwords and
  passphrases remembered in Windows' Credential Manager when you ask.
- **The diagnostic log**, to see what a program sent when something looks
  wrong.
- **Builds** for Windows (signed with the author's code-signing
  certificate), RHEL 8 (which also runs on any later x86-64
  Linux), RHEL 9, and a `.deb` for Ubuntu 24.04 and Linux Mint 22.

## Next

Not in a fixed order:

- **A scrollbar.**
- **A native Wayland window**, in place of running through Xwayland on a
  Wayland desktop.
- **GPU drawing** for local use, with OpenGL ES; the X11 renderer stays
  for remote X11 and machines with no GPU.
- **Tabs**: dragging to reorder them, and typing into several at once.
- **1.0.0**, with the first alpha of [Geng](https://geng-lang.org), the
  language puritty is written in.

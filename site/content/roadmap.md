+++
title = "Roadmap"
+++

puritty is pre-release: its author's daily terminal, with preview builds
for Windows, RHEL 8 and 9, and Ubuntu 24.04 (and Linux Mint). This is
where it stands, and what comes next.

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
  options editor) drawn by puritty, in its look or tmux's. It adapts to
  each tmux from 2.7 to 3.8, and is checked against every release between.
- **Tabs**: colors of your own or per host, renaming, reopening a closed
  tab, and your tabs opened again when puritty starts.
- **Search** in the scrollback.
- **Copy and paste** with both of X's clipboards, and OSC 52 for programs
  that copy for you.
- **The settings window**, in English and Korean, with every change taken
  by every open window at once: fonts, color schemes, your own keys,
  bells and key sounds.
- **Hosts**: a host list with quick connect, hosts kept in the settings and
  read from `~/.ssh/config`, and your recent connections in the menus and
  Windows' taskbar.
- **Windows**: the same terminal, with the ssh client built in, jump hosts,
  keys and agents, and a changed host key asked about.
- **The diagnostic log**, to see what a program sent when something looks
  wrong.
- **Builds** for Windows, RHEL 8 (which also runs on any later x86-64
  Linux), RHEL 9, and a `.deb` for Ubuntu 24.04 and Linux Mint 22.

## Next

Not in a fixed order:

- **tmux control mode, the last of it**: vi keys at tmux's prompt, tmux's
  own prompt history, completing options and targets, the mouse in tmux's
  session tree and options editor, and tmux's `bell-action` and
  `visual-bell`.
- **Inline images**: Sixel, Kitty graphics and iTerm2 images.
- **A scrollbar.**
- **Tabs**: dragging to reorder them, and typing into several at once.
- **A signed Windows release**, and passwords kept in the Windows
  credential store.
- **The first public release**, with the first alpha of
  [Geng](https://geng-lang.org), the language puritty is written in.

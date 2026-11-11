+++
title = "Roadmap"
+++

puritty is pre-release. This is where it stands, and what comes next, in
roughly this order.

## Done

- **The terminal core**, tested against libghostty-vt, fuzzed, and run
  against `esctest2`; a renderer of its own for X11 that is fast over the
  network.
- **Input methods** through XIM, with Korean, Japanese and Chinese tested.
- **EUC-KR and CP949** built in.
- **The settings window**, in English and Korean, with every change taken by
  every open window at once.
- **Hosts**: a host list with quick connect, hosts kept in the settings and
  read from `~/.ssh/config`.
- **Windows**: the same terminal, with the ssh client built in, jump hosts,
  keys and agents.
- **tmux control mode, first part**: tmux's tiled, floating and modal panes
  drawn as puritty's own.

## Next

1. **tmux control mode, the rest**: what the panes held when you attach,
   tmux's windows as tabs, the mouse on panes (focus, moving and resizing
   floating panes), scrollback and selection within a pane.
2. **Inline images**: Sixel, Kitty graphics and iTerm2 images.
3. **Scrollback search**, a scrollbar, and **key bindings** in the settings.
4. **Key sounds**, an optional typewriter click as you type.
5. **RHEL 8**, built against its older libraries.
6. **A signed Windows release**, and passwords kept in the Windows
   credential store.

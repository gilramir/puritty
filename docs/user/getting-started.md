# Getting started

puritty is a terminal for Linux and Windows. On Linux it runs your shell, or
any program, in an X11 window, locally or over `ssh -X`. On Windows it is
first of all an ssh terminal, with the ssh client built in.

> **puritty is pre-release.** It is its author's daily terminal, and it will
> be published with the first alpha of [Geng](https://geng-lang.org), the
> language it is written in. Until then you build it from source.

## Building

puritty is a Geng program with a little C for X11 (or Win32), fonts and the
input method. Until Geng's first release, a build needs a
geng-lang checkout ([geng-lang.org](https://geng-lang.org)) with its
compiler built, and the libraries in puritty's `devbox.json` (libxcb,
xkbcommon, FreeType, HarfBuzz, fontconfig). From the repository:

```sh
devbox shell
app/build.sh            # writes app/puritty, for Linux
app/build-windows.sh    # writes app/puritty.exe, for Windows
```

`app/release.sh` builds a release: it trains a profile of the terminal core
first, which makes the core 5% to 25% faster, and takes a few minutes more.

## Running it

```sh
puritty                         # your $SHELL in a new window
puritty -- htop                 # any program
puritty --title notes -- vim -O a.txt b.txt
puritty --config ~/work.toml    # another settings file
puritty --host build-box        # a host from your settings, over ssh
puritty ssh user@host:port      # a host you haven't saved
puritty hosts                   # the list of your hosts, to choose one
puritty settings                # the settings window
```

On Windows, plain `puritty` opens the list of hosts, with a quick-connect
field at the top: type `user@host` and press Enter. The hosts in your
settings and in `~/.ssh/config` are listed under it. On Linux it opens your
shell; `start = "hosts"` in the settings makes it open the list there too.

## The keys to know

| keys | what they do |
|---|---|
| Ctrl+Shift+C, Ctrl+Shift+V | copy to and paste from the clipboard |
| middle button, Shift+Insert | paste the selection |
| Shift+PgUp, Shift+PgDn, the wheel | scroll back |
| Ctrl+Shift+Up, Ctrl+Shift+Down | jump between shell prompts |
| Ctrl+=, Ctrl+−, Ctrl+0, Ctrl+wheel | zoom |
| Ctrl+Comma | the settings window |
| Ctrl+right-click | the menu: settings, hosts, a new tab, a new window |

## Where next

- [Settings](settings.md): the settings file, and the window that edits it.
- [Copy and paste](copy-and-paste.md): the selection, the clipboard, and
  programs that take the mouse.
- [tmux](tmux.md): tmux's panes drawn as puritty's own, floating panes
  included.

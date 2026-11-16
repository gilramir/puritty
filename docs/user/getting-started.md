# Getting started

puritty is a terminal for Linux and Windows. On Linux it runs your shell, or
any program, in an X11 window, locally or over `ssh -X`. On Windows it is
first of all an ssh terminal, with the ssh client built in.

## Installing

Download it from the [latest release](https://github.com/gilramir/puritty/releases/latest)
on GitHub. Take the file for your system:

| system | file | then |
|---|---|---|
| Windows 10 or 11 | `puritty-VERSION-windows-x64.zip` | Unzip it and run `puritty.exe`. It is not signed yet: if Windows says "Windows protected your PC", choose **More info**, then **Run anyway**. |
| Ubuntu 24.04, Linux Mint 22 | `puritty_VERSION_ubuntu24.04_amd64.deb` | `sudo apt install ./puritty_*_ubuntu24.04_amd64.deb`, which adds it to the desktop's menu. Or the `.tar.gz` beside it, to unpack anywhere. |
| RHEL 9 | `puritty-VERSION-rhel9-x64.tar.gz` | Unpack it anywhere and run `./puritty`. |
| RHEL 8, or any other x86-64 Linux | `puritty-VERSION-linux-rhel8-x64.tar.gz` | Unpack it anywhere and run `./puritty`. Built on RHEL 8, it runs on any later Linux too. |

No administrator rights are needed except for the `.deb`. On Linux puritty
needs the X libraries every desktop has (xcb, xcb-util, xcb-util-image,
xcb-util-renderutil, libxkbcommon-x11 and fontconfig);
`ldd puritty | grep "not found"` lists any that are missing. On RHEL, see
[Fonts for symbols](symbol-fonts.md) too.

## Building

> **It cannot be built outside its author's machines yet.** The Geng
> toolchain it needs has not been published; it will be with Geng's first
> alpha. The steps below are how it is built then.

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

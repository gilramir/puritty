# Settings

puritty reads `~/.config/puritty/config.toml` (on Windows
`%APPDATA%\puritty\config.toml`). Every key is optional. A change to the
file is taken by every open window at once, except the window's size and
the program, which new windows take.

A key puritty doesn't know, or a value a setting doesn't take, is reported
with its line and the nearest setting's name (`font.sise`: did you mean
`font.size`?) rather than silently ignored, and puritty goes on with the
rest. The report is on standard error, at the top of a new window, and on
the title until the file is fixed.

## The settings window

`puritty settings`, or Ctrl+Comma in any window, opens a window that changes
the settings without editing the file: search, a page of settings at a time,
each change written to the file and taken by every open window as you make
it, Ctrl+Z to undo, with the keys or the mouse. It edits the file in place
and keeps your comments. Its Hosts page adds, changes, copies, renames and
removes hosts. It speaks English, or Korean when your language is Korean.

## The file

```toml
[window]
columns = 120
rows = 36

[font]
family = "Fira Code"        # DejaVu Sans Mono when left out,
                            # Cascadia Mono on Windows
size = 11                   # points
language = "ko"             # which regional forms fallback fonts use

[colours]
foreground = "#c5c8c6"
background = "#1d1f21"
palette = ["#1d1f21", "#cc6666", "#b5bd68", "#f0c674"]   # the 16 named colours, from 0

[terminal]
charset = "utf-8"           # or "euc-kr", "cp949"

[scrollback]
lines = 25000

[selection]
word_boundaries = " \t'\"│`|:;,()[]{}<>$"
copy_to_clipboard = true    # a selection goes to the clipboard too;
                            # true on Windows, false on Linux

[mouse]
paste_button = "middle"     # or "right"

[clipboard]
osc52_read = "deny"         # or "allow"
```

## Colour schemes

`scheme` under `[colours]` copies another terminal's colours:

| `scheme` | from |
|---|---|
| `puritty` | puritty's own, the default |
| `ghostty`, `alacritty`, `putty`, `xterm` | those terminals' defaults |
| `campbell`, `vintage` | Windows Terminal's default, and the old Windows console's |
| `one-half-dark`, `one-half-light` | One Half |
| `solarized-dark`, `solarized-light` | Solarized |
| `tango-dark`, `tango-light` | Tango |
| `dark-plus` | VS Code's Dark+ |

```toml
[colours]
scheme = "solarized-dark"
background = "#001820"     # wins over the scheme's
```

A `foreground`, `background` or `palette` you write beside it wins over
the scheme's, wherever it is in the file.

## Hosts

Hosts are kept in the same file. `puritty --host NAME` connects to one, in
the host's own colours and font:

```toml
[hosts."build-box"]
host = "build.example.com"
user = "gilbert"
port = 22                        # left out: 22
identity = "~/.ssh/id_ed25519"   # left out: ssh's own choice
jump = "bastion"                 # another host, or user@host:port
command = "tmux -CC new -A -s main"
charset = "euc-kr"               # this host's, over the one above

[hosts."build-box".colours]
background = "#2a1010"
```

A name the file doesn't have is looked up in `~/.ssh/config`, so your
aliases work as they are. `start = "hosts"` at the top of the file makes
plain `puritty` open the host list, and `start = "host:build-box"` connect
straight there; `puritty shell` still opens a local shell.

**On Windows** puritty connects with its own ssh client: no OpenSSH and no
pseudo console between the host and the terminal. It checks host keys
against `~/.ssh/known_hosts` and asks before trusting a new one, uses your
keys and the Windows ssh agent or Pageant, asks for a passphrase or a
password in the window, and goes through jump hosts as `ProxyJump` does.
On Linux puritty runs OpenSSH, unless a host says `client = "built-in"`.

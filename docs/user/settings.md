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
A new window opens as the last one closed: maximized if it was, and
otherwise at its size; `[window] columns` and `rows` are the size of the
first. On its Sound page, the bell plays as you move through its list, and a key
clicks as you turn key sounds on, so you hear what you are choosing.

## The file

```toml
[window]
columns = 120
rows = 36
padding = 8                 # points between the text and the window's
                            # left and right edges; 0 for none
padding_vertical = 4        # the same above and below

[font]
family = "Fira Code"        # DejaVu Sans Mono when left out,
                            # Cascadia Mono on Windows; a font of your
                            # own: see fonts.md
size = 11                   # points
language = "ko"             # the forms Han characters are drawn in:
                            # "ko", "ja", "zh-cn", "zh-tw" or "zh-hk"
ligatures = true            # the font's, as Fira Code's != and ->; the
                            # cell under the cursor is always drawn alone

[sound]
bell = "none"               # what Ctrl-G (BEL) sounds like: "none",
                            # "system" (the desktop's own beep), or a
                            # classic computer's: "apple2", "ibm-pc",
                            # "atari-st", "bbc-micro", "x11"
keys = false                # a click for each key typed, another for Enter

[colors]
foreground = "#c5c8c6"
background = "#1d1f21"
palette = ["#1d1f21", "#cc6666", "#b5bd68", "#f0c674"]   # the 16 named colors, from 0

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

[files]
drop_uploads = "ask"        # files dropped on an ssh tab sent to its
                            # host: "ask" first, "allow", or "deny"
upload_through_shell = false  # true: where a host has SFTP turned
                            # off, an upload may run sh, cat and mv
                            # there instead; off, since it runs
                            # commands on your behalf (see
                            # Sending files to a host)

[images]
read_files = false          # true: a program on this computer may
                            # show a picture by naming its file
                            # (Kitty's graphics, Claude Code's mods)

[debug]
log = false                 # true: a diagnostic log for each window,
                            # see the diagnostic log guide
```

## Color schemes

`scheme` under `[colors]` copies another terminal's colors:

| `scheme` | from |
|---|---|
| `puritty` | puritty's own, the default |
| `ghostty`, `alacritty`, `putty`, `xterm` | those terminals' defaults |
| `campbell`, `vintage` | Windows Terminal's default, and the old Windows console's |
| `one-half-dark`, `one-half-light` | One Half |
| `solarized-dark`, `solarized-light` | Solarized |
| `tango-dark`, `tango-light` | Tango |
| `dark-plus` | VS Code's Dark+ |
| `green-screen`, `amber-screen` | the green and amber phosphor screens of early terminals |

```toml
[colors]
scheme = "solarized-dark"
background = "#001820"     # wins over the scheme's
```

A `foreground`, `background` or `palette` you write beside it wins over
the scheme's, wherever it is in the file.

## Hosts

Hosts are kept in the same file. `puritty --host NAME` connects to one, in
the host's own colors and font:

```toml
[hosts."build-box"]
host = "build.example.com"
user = "gilbert"
port = 22                        # left out: 22
identity = "~/.ssh/id_ed25519"   # left out: ssh's own choice
jump = "bastion"                 # another host, or user@host:port
command = "tmux -CC new -A -s main"
charset = "euc-kr"               # this host's, over the one above

[hosts."build-box".colors]
background = "#2a1010"
tab = "#c62828"                  # its tabs' color in the bar
```

A name the file doesn't have is looked up in `~/.ssh/config`, so your
aliases work as they are.

**PuTTY's saved sessions** are in the host list too, marked "from PuTTY",
after your own hosts and `~/.ssh/config`'s, so there is nothing to
import. Connecting to one (Enter), or opening it with Right, makes it a
host of your file first, with the session's host, user, port, command,
jump host ("SSH to proxy and use port forwarding"), title, and its colors
and font where you changed them from PuTTY's. From then on it is yours to
change; PuTTY's copy is left as it was. Sessions that are not ssh
(telnet, serial) are not listed. PuTTY's key files (`.ppk`) are not read
yet: if you log in with one, keep it in Pageant, which puritty uses.

The host list's **Local shell** opens a shell on this computer instead of
a host (on Windows, PowerShell). It offers the connections you made last first (eight, or as
many as `[connections] recent` says; 0 for none): Enter makes one again,
Delete forgets it, and Right saves a quick one as a host. In quick connect,
anything after a space is a command to run there, as with `ssh`:
`gilbert@build tmux -CC attach`. To change a connection before making
it, choose its row and press F2 (or click its pencil): its line goes into
quick connect, where you can edit it and press Enter. Up in an empty quick
connect brings back your recent connections one at a time, as a shell's
history does. The boxes take Ctrl+V and Shift+Insert to paste (a paste of
several lines comes as one, joined by spaces), Ctrl+C and Ctrl+X to copy
and cut, Ctrl+A to select everything, Shift with the arrows to select,
and Ctrl with the arrows and Backspace to move and delete by a word. The same recent connections are in the
menu (Ctrl and the right button, and on Windows the title bar's menu), as
"Connect to …" before your saved hosts, and on Windows in the taskbar's
jump list: right-click puritty's button, under **Recent connections**. If
the jump list stays empty, Windows is set not to show recently opened
items (Settings, Personalization, Start). `start = "hosts"` at the top of the file makes
plain `puritty` open the host list, and `start = "host:build-box"` connect
straight there; `puritty shell` still opens a local shell.

**On Windows** puritty connects with its own ssh client: no OpenSSH and no
pseudo console between the host and the terminal. It checks host keys
against `~/.ssh/known_hosts` and asks before trusting a new one, uses your
keys and the Windows ssh agent or Pageant, asks for a passphrase or a
password in the window, and goes through jump hosts as `ProxyJump` does.
On Linux puritty runs OpenSSH, unless a host says `client = "built-in"`.

When the window asks for a password or a key's passphrase on Windows,
Tab checks "Remember it in Windows' Credential Manager", and the next
connection logs in without asking. Remembered ones are listed in Control
Panel's Credential Manager under "Generic credentials", named
`puritty:ssh:…` and `puritty:key:…`, where you can remove them; one the
server refuses is asked for again. `remember_secrets = "never"` under
`[connections]` turns the offer off. Nothing is remembered on Linux.

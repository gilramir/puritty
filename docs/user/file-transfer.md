# Sending files to a host

*Status: this guide describes what is built as of 2026-11-20
([`../sftp.md`](../sftp.md) FT22 to FT33): dropping files on a tab.
Downloading, a file tab, and `get` and `put` typed in the shell are still
to come.*

Drag files or folders from your file manager (Explorer, Nautilus, Nemo,
Dolphin) onto puritty's window. What happens depends on the tab you drop
them on.

---

## 1. A tab on this computer

The files' paths are pasted, each followed by a space, as other terminals
do. They are quoted for the shell where they need it: in single quotes on
Linux (`'my file.txt'`), in double quotes on Windows
(`"C:\Users\me\my file.txt"`). Nothing is copied; your program gets the
names.

## 2. An ssh tab

The files are sent to the host over the tab's own connection, with no
second login. With puritty's own ssh (`client = "built-in"`, the default
on Windows) that is another channel on its connection. With OpenSSH's
`ssh` (the default on Linux), puritty starts the tab's `ssh` as a
`ControlMaster`, on a socket of its own, and sends through it; a host for
which your `~/.ssh/config` already sets up a master keeps yours, and
puritty sends through that. On Windows, whose OpenSSH has no masters, a
tab using OpenSSH's `ssh` can't send files, and says so.

### Where they go

- **Under `tmux -CC`**, as you drag, the pane under the pointer is marked
  with the folder the files would go to: a yellow label, " Drop into
  /home/me/project ", over the pane. Drop on the pane you want. The folder
  is the shell's: the one it reports itself (OSC 7) when it does, else the
  one tmux sees. When the pane runs `ssh`, `su`, `sudo` or the like, tmux
  can't see its folder, and the label says a folder will be asked for.
- **In a tab without tmux whose shell says where it is** (by OSC 7, see
  below), they go to the shell's folder.
- **Otherwise** the folder picker opens, at your home on the host (see
  below).

Folders are sent with everything in them.

### The folder picker

```
 Send report.pdf and 2 more to web1
 ~ › projects › site                                          ☆
 Shell's folder │ Name                       Size  Modified
 Home           │ ▸ ..
 /              │ ▸ assets/                        2026-11-14 02:13
 RECENT         │ ▸ css/                           2026-11-15 02:13
 /srv/www/site  │   index.html            4.1 KB   2026-11-14 08:11
 BOOKMARKS      │   logo.png  ◆ same name  12 KB   2026-11-14 12:35
 /var/log       │
 New folder                      Cancel   Send to ~/projects/site/  Ctrl+Enter
```

The files go to **the folder you are in**, the one at the end of the path
at the top, and the button says which. Moving the highlight up and down
doesn't change it; going into a folder does.

| to | with the mouse | with the keys |
|---|---|---|
| go into a folder | double-click it | Enter, or Right |
| go up | click a name in the path, or `..` | Backspace, or Left |
| go to a place | click it at the left | Tab to the places, then Enter; or Alt+1 to Alt+9 |
| type a path | click the path's empty end | `/`, `~` or Ctrl+L; Tab completes; Enter goes there |
| find a name | | type it: the list keeps only names with it in them; Esc clears it |
| make a folder | New folder | Ctrl+N, a name, Enter (and you are in it) |
| bookmark this folder | the ☆ at the path's end | Ctrl+D (again to remove it) |
| read the folder again | | Ctrl+R |
| send | Send to … | Ctrl+Enter |
| cancel | Cancel | Esc |

- **Dragging files onto a folder in the list** sends them there, while the
  picker is open; the row says "Drop into …" as you drag over it.
- **Dragging a folder from the list onto the places** bookmarks it. A
  bookmark's ✕, as the pointer is over it, removes it; so does Delete in
  the places.
- Files are listed dimmed, so you can see what is there; one with the name
  of a file you are sending is marked **◆ same name**.
- A long path keeps its start and its end, `~ › … › long › paths`; click the
  `…` for the folders left out.
- **Recent** lists the folders files were last sent to on this host.
  **Bookmarks** are a host's own. For a host in your settings they are kept
  in its table:

  ```toml
  [hosts.web1]
  host = "web1.example.com"
  bookmarks = ["/srv/www/site", "/var/log"]
  ```

  For a host you reached with `puritty ssh user@host`, they are kept with
  the recent folders in `folders.toml` in puritty's state folder.
- **Modified** times are in your computer's time zone, but with the offset
  it has today: a file changed on the other side of a change to or from
  summer time shows an hour off. puritty doesn't read the time zone's
  rules yet.

### Asked first

Sending writes your files on the host, so puritty asks first. When it
found the folder itself (the `tmux -CC` pane you dropped on, or the
shell's), a box names the files and the folder, and nothing is sent until
you say yes (Enter, or Send; Esc, or Don't send, sends nothing). "Another
folder…" (C) opens the folder picker there, to choose another. When the picker
asked you for the folder, choosing one is your yes, and there is no second
question.

```toml
[files]
drop_uploads = "ask"     # the default; "allow" sends without asking,
                         # "deny" never sends dropped files
```

A drop on a tab on this computer pastes the paths whatever this says.

### A name that is there already

One question for the whole drop, listing the names:

- **Replace** (R, or Enter): the file on the host is written over, keeping
  its owner and permissions;
- **Keep both** (K): yours arrives as `name (2).ext`;
- **Skip** (S): yours is not sent;
- **Replace if newer** (N): only where yours was changed later;
- **Esc** cancels the whole drop.

### While it is sent

After a second, the bar at the bottom right shows the file, which of how
many, how much is done, the speed and the time left. **Click it to
cancel**: the file being sent is removed from the host rather than left
half written, and the rest is not sent. You can go on typing meanwhile,
and switch tabs: the sending goes on, and the tab shows `↑` before its
name until it is done. At the end a note says what was sent, and what was
skipped or failed and why.

A new file is written under a temporary name (`.name.puritty-part`) and
renamed when it is complete, so a broken connection never leaves a
half-written file under the real name. The file keeps its modification
time.

---

### Letting the shell say where it is (OSC 7)

A shell can tell the terminal its folder with OSC 7, and some do at every
prompt: fish does by default; bash and zsh do in a desktop's terminal on
Fedora and Linux Mint, but not over ssh. To have bash say it on a host,
add this to its `~/.bashrc`:

```bash
PROMPT_COMMAND='printf "\033]7;file://%s%s\007" "$HOSTNAME" "${PWD// /%20}"'"${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
```

and for zsh, to `~/.zshrc`:

```zsh
precmd_osc7() { printf '\033]7;file://%s%s\007' "$HOST" "${PWD// /%20}" }
precmd_functions+=(precmd_osc7)
```

puritty takes the host the tab's shell names first as the tab's host. A
folder named by another host later, from an `ssh` run in the tab, is not
used: the files would go to the tab's host, not that one.

## 3. A host with SFTP turned off

Some hosts turn SFTP off. puritty can still send files through the host's
shell (`sh`, `cat` and `mv`, run as you), but since that runs commands on
your behalf it is off until you turn it on:

```toml
[files]
upload_through_shell = true
```

With it off, a drop on such a host sends nothing, and the note says which
setting would allow it. The folder picker needs SFTP, so on such a host
drop on a `tmux -CC` pane whose folder is known.

## 4. Korean file names on an EUC-KR host

A host whose `charset` is `euc-kr` or `cp949` gets the files' names in
that character set, as it gets what you type. A name with a character
that set has no form for is not sent, and the note says so.

A file on this computer whose name is EUC-KR bytes (not UTF-8) goes to
such a host as it is. Dolphin, and other programs built on Qt 6, can't
hand such a name over: they change its bytes before puritty sees them,
and puritty says the file isn't there.

## 5. What can't be sent yet

- A file dragged out of a zip in Explorer, or an attachment from a mail
  program: it isn't a file on disk yet. Save it first, then drag it.
- Downloading from the host.

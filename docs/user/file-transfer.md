# Sending files to a host

*Status: this guide describes what is built as of 2026-11-20
([`../sftp.md`](../sftp.md) FT22 to FT26): dropping files on a tab.
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
second login. This needs puritty's own ssh (`client = "built-in"` for the
host; it is the default on Windows). A tab using OpenSSH's `ssh` can't send
files yet, and says so.

### Where they go

- **Under `tmux -CC`**, as you drag, the pane under the pointer is marked
  with the folder the files would go to: a yellow label, " Drop into
  /home/me/project ", over the pane. Drop on the pane you want. The folder
  is the shell's: the one it reports itself (OSC 7) when it does, else the
  one tmux sees. When the pane runs `ssh`, `su`, `sudo` or the like, tmux
  can't see its folder, and the label says a folder will be asked for.
- **In a tab without tmux whose shell says where it is** (by OSC 7, see
  below), they go to the shell's folder.
- **Otherwise** a box asks which folder, starting at your home on the
  host:

  | key | what it does |
  |---|---|
  | Up, Down | choose a folder; `..` is the one above |
  | Enter | go into the folder in the box's field |
  | Enter again | send the files there |
  | typing | a path of your own, `/srv/www` or `projects/site`, then Enter |
  | Esc | cancel |

  "Send here" sends them to the folder shown; "Cancel" cancels.

Folders are sent with everything in them.

### Asked first

Sending writes your files on the host, so puritty asks first. When it
found the folder itself (the `tmux -CC` pane you dropped on, or the
shell's), a box names the files and the folder, and nothing is sent until
you say yes (Enter, or Send; Esc, or Don't send, sends nothing). "Another
folder…" (C) opens the folder box there, to choose another. When it asked
you for the folder, choosing one is your yes, and there is no second
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
setting would allow it. The folder box needs SFTP, so on such a host drop
on a `tmux -CC` pane whose folder is known.

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
- Folders that are links don't show in the folder box (type their path).
- Downloading from the host.

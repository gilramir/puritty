# File transfer over the tab's connection: a survey before the design

Gilbert, 2026-11-19: "do a survey of different sftp apps and ssh terminals
that provide sftp (so, putty, mobaxterm, even ChromeOS's "Terminal", and
maybe file transfer software like filezilla etc); I do want to provide sftp
functionality with our ssh client; it's very useful when running puritty on
windows and connecting to a remote host. In addition to the drag-and-drop
into the terminal (perhaps opening a file UI), general SFTP functionality
should be provided. I'm undecided on the UX/UI. What positive & negative
feedback do people write about online about this topic?"

This is the survey; nothing is built. `feature-plan.md` §9 (a file dropped
on the window, uploaded to a folder the user chooses) is the piece already
asked for, and §8 (a screenshot pasted as a remote path) shares its second
channel. The sources are four sets of notes in
`research/research_notes/SFTP survey/`, each claim there with its link:

- `ssh_clients.md`: MobaXterm, Termius, SecureCRT/SecureFX, Xshell/Xftp,
  Bitvise, Tabby, WindTerm, electerm, Royal TS, Remote Desktop Manager,
  XPipe, Solar-PuTTY, PuTTY, Warp, iTerm2 and Windows Terminal.
- `file_transfer_apps.md`: WinSCP, FileZilla, Cyberduck, Mountain Duck,
  Transmit, ForkLift, Commander One, Total Commander, Far's NetBox,
  VS Code Remote-SSH, JetBrains' Remote Host, SSHFS-Win, rclone and
  SFTP Drive.
- `os_and_inband.md`: ChromeOS Terminal and Secure Shell, GNOME Files,
  Dolphin, Finder, Explorer, ZMODEM, trzsz/tssh, iTerm2's `it2ul`/`it2dl`,
  kitty's `transfer` and `dnd`, and what terminals do with a dropped file.
- `pain_points_and_requests.md`: the same material by theme rather than by
  program.

**What the sources are.** Reddit was out of reach: the search and fetch
tools both refuse reddit.com. G2 and Capterra pages mostly answered 403, and
Stack Exchange pages would not fetch, so those claims come through search
summaries or mirrors and the notes mark them. The user voice is therefore
Hacker News, GitHub issues, the vendors' forums and trackers (WinSCP's
forum and FileZilla's and Cyberduck's trackers most of all), university
help pages, and some review sites. This is signal, not a count. Where FT1
says "many", several independent sources say it; "one" means one.

## FT1 · What users say, ranked

**1. Logging in twice is the most widespread complaint.** A file panel that
opens its own SSH connection asks for the password and second factor
again. MobaXterm's sidebar does it on login. Alliance Canada's MFA page says
"each time you navigate to a different folder on the left pane, another
transaction requiring MFA is started", sometimes in "hidden MFA-Duo
windows". FileZilla asks per transfer and Cyberduck per file. University
help pages at Alliance Canada, Hawaii, NeSI, Kennesaw and Oakland exist to
tell users to turn the panel off. Clients that read only part of
`~/.ssh/config` also lose jump hosts and agents: WinSCP, Cyberduck,
iTerm2's scp, and Royal TS. The fix people name is one login with SFTP as
another channel on it. SecureCRT advertises its SFTP tab as working
"without having to re-authenticate", and Remote Desktop Manager moved SFTP
onto the terminal's connection in 2023 because Azure Bastion allows one.
On Linux and macOS, OpenSSH's ControlMaster does the same; Windows'
OpenSSH has nothing like it. Many sources.

**2. MobaXterm's sidebar is the model everyone asks for.** The browser opens
by itself on login and "follows" the shell's directory. "Integration with
sftp browser and follow terminal path saved me many hours" (HN). A DEV
guide calls it MobaXterm's "killer feature", and it appears in nearly every
"why I use MobaXterm" thread. Royal TS users ask for it by name; Tabby,
electerm, Xshell and WindTerm users asked, and electerm and WindTerm built
it. Users also ask that the panel live in the terminal's tab, not a window
of its own: Royal TS, Xftp, SecureFX and Bitvise open one, and users put up
with it. Many sources.

**3. Following the directory is fragile, everywhere.** MobaXterm labels it
"experimental". It breaks after `su` and `sudo su`, under byobu or tmux,
after several ssh hops, when a startup file prints something, on old
Unixes, and when the sidebar was on another tab during the `cd`. Xshell
reads the directory from the window title and fails when the title says
`~`. Tabby opens at `/` until you press a button. PuTTY's author calls
uploading into the shell's directory "mayhem" and "not feasible": the
terminal cannot know it without the shell's help. OSC 7 is the modern
help, but it needs `allow-passthrough` in tmux and carries no user name, so
after `sudo su` it gives the right path for the wrong user. Several threads
each, always the same three cases: a user switch, a multiplexer, a nested
ssh.

**4. Files only root can write are the most-asked "how do I".** SFTP runs
as the login user, and users expect the panel to follow their `sudo -i`.
The one recipe is to point the client at `sudo /usr/lib/openssh/sftp-server`
with a sudoers rule that needs no password. Only WinSCP and Xftp offer it,
users are uneasy about the rule, the path differs per distribution, and a
mistake shows only "Cannot initialize SFTP protocol". WinSCP's request
"Allow providing a password to sudo" has been open since 2014; its 2024
note calls the askpass workaround "a huge hack". FileZilla rejected sudo,
Cyberduck has open tickets, Tabby's author answered "You cannot elevate the
SSH connection itself", and VS Code needs an extension. MobaXterm later
added a "sudo su" button to its panel. What people do instead: upload to
home, then `sudo mv`. Many sources.

**5. A built-in panel is judged against WinSCP and FileZilla, and loses.**
On speed: Tabby gave one user 5.5 MB/s against FileZilla's 120 MB/s, and
Termius and Remote Desktop Manager draw the same complaint. On basics:
Tabby's most-voted SFTP issue was folders and several files at once
("If there is no folder to upload, I feel that sftp does not make much
sense"), then rename, chmod, a typed path, search and two panes. A Termius
user keeps FileZilla for SFTP. Many sources.

**6. Editing a remote file in a local editor is expected, and it fails
silently.** MobaXterm, Termius, WinSCP, electerm, Cyberduck and FileZilla
download to a temporary file and upload on save. The reported failures:
a tabbed editor hands the file to its first process and later saves go to
an older temporary copy; a disconnect "de-links" the file; the temporary
copy is deleted while open; a save is not noticed; Vim's write-by-rename
defeats a watcher; text mode rewrites line endings although SFTP itself is
always binary. Almost nobody checks that the server's copy is unchanged
before writing over it: JetBrains shows a diff, Transmit has a setting,
Mountain Duck keeps both copies with the time in the name, and the rest
overwrite. Many WinSCP threads over fifteen years; fewer elsewhere because
fewer tools do it.

**7. Overwrite prompts get no praise, only complaints.** WinSCP's dialog is
the fullest: size and time of both files, Yes, No, Cancel, Yes to all,
Newer only, New name, Append/Resume. Transmit adds "Keep both" and
separate rules for folders, with a warning on Replace and Merge. The
complaint is the reach of "apply to all": in WinSCP it covers one batch, so
with files sent one by one it asks for each; in FileZilla it lasts the
session, misses files queued later, and is reported to come back after
"always". "Only if newer" is fooled by clocks and by servers that round
times. People want one default they set once, and a "newer only" that
works. A steady trickle of tickets.

**8. Transfers belong in a queue that doesn't steal focus.** WinSCP and
FileZilla run every transfer in a background queue (Queued, Failed, Done in
FileZilla); WinSCP marks a row that needs an answer and waits rather than
pop a dialog. Cyberduck removed queuing in version 6 and users filed "When
will CyberDuck restore the ability to queue transfers?". Resume after a
dropped connection is expected (WinSCP's `.filepart`, OpenSSH's `reput`).

**9. Speed is latency and small files.** SFTP waits for answers per request;
with 32 KiB requests and one outstanding, 100 ms of latency caps a transfer
near 0.3 MB/s, and clients that keep many requests in flight go far faster
(libssh2 reported 8x from pipelining; PuTTY keeps up to 1 MiB outstanding,
`putty.md`). Many small files are slow by any SFTP client: one user's 16 GB
of small files took over 14 hours by SFTP and under 7 minutes by tar over
ssh.

**10. Dropping a file on the terminal is requested in many projects.**
Windows Terminal (discussion #17029), xterm.js, Konsole (since 2005),
PuTTY's wishlist, Tabby, Royal TS. What ships: Xshell and SecureCRT send a
dropped file by ZMODEM (Xshell: run `rz`, then drop); iTerm2 uploads it by
scp into "the directory you were in on the line where you dropped it",
with shell integration on the host; tssh runs `trz` in the shell, with a
file dialog; kitty 0.47's `kitten dnd` receives drops into its own
directory on the remote host. Each one gets the directory from the remote
side, which is FT1.3 again.

**11. Transfer inside the terminal stream is loved for one reason.** ZMODEM
(`rz`/`sz`), trzsz, iTerm2's `it2ul`/`it2dl` and kitty's `transfer` ride the
shell itself, so they work through jump hosts, nested ssh, `sudo su` and
serial lines with no second login. "It's so much easier then switching to a
local terminal to use scp" (HN); Lennart Poettering wishes terminals did
ZMODEM "so that you can ssh into some host of your choice and just type
sz". ZMODEM is the most-voted file request on Windows Terminal (#1999,
185 thumbs-up, locked as "not a high priority"); Alacritty, WezTerm and
GNOME Terminal declined it. Its failures: it breaks in tmux (tmux declined;
trzsz exists because of that), escaping errors corrupt or stall it, it is
slow, and it needs a program on the host. Its danger: the remote side can
ask the terminal for local files, so kitty asks before every transfer and
tssh warns that its auto-upload folders let "the server ... stealthily
steal all files". "A serious violation of the cleanliness and available
attack surface involved in a terminal interface" (HN).

**12. Mounting the host as a drive feels native and freezes.** ChromeOS's
Terminal mounts a host into the Files app (`chrome://flags#terminal-sftp`
since ChromeOS 109; "Mount to Files" beside a saved connection). In the
nassh source the mount is its own ssh with the `sftp` subsystem, so it logs
in again, and it belongs to a tab: "Keep this tab open. Closing this tab
will remove the mount connection from Files." It measured 0.46 MB/s on a
90 ms link, and the maintainer answered "help wanted ;)". GNOME Files and
Dolphin are two to four times slower than scp and freeze when the link
drops; SSHFS-Win and rclone slow Explorer down (thumbnails for every file,
minute-long listings), and sshfs leaves 0-byte files when it flakes out.
Transmit dropped its Finder mount in 5.6. Neither Finder nor Explorer
speaks SFTP: "It baffles me that Windows Explorer still doesn't know how
to connect to an SFTP site out of the box" (HN). Many sources.

**13. Dragging a file out to Explorer is hard.** Windows wants the data
before the drop finishes and doesn't tell the source where it landed.
WinSCP's answer is a shell extension that drags an empty dummy folder and
learns the target from a CopyHook. It works only with Explorer, stays
loaded at boot, is missing from portable and Store installs, and still
leaves empty `scpNNNNN` folders. Without it, WinSCP downloads to a temporary
folder first, can't transfer in the background, and can strand the file
if the Explorer window closes mid-copy. The non-invasive way is virtual
files (`CFSTR_FILEDESCRIPTOR` with an `IStream` per file), as in Raymond
Chen's "What a drag" series. Remote Desktop Manager had no drag to or from
Explorer until 2026.3; Termius users say it "isn't possible".

**14. Servers that refuse.** Some admins and appliances turn the SFTP
subsystem off or give a restricted shell (pfSense, F5, Data Domain);
Dropbear and OpenWrt often have no `sftp-server`, which OpenSSH 9.0's
switch of `scp` to SFTP made visible (`scp -O`). A login script that prints
breaks SFTP, the same cause as byobu breaking MobaXterm's following. People
want a fallback through the shell and an error that says why.

**15. Keyboard users want to skip the mouse.** scp is loved for its short
syntax, lftp for completing remote paths, WinSCP's Commander for its
Norton keys, and Termius is faulted for missing shortcuts. "Or better yet,
a full keyboard workflow" (HN, on drag and drop).

**16. Trust decides switches.** FileZilla's Windows installer has carried
"bundled offers" since 2013, and HN users say that is why they moved to
WinSCP ("switched to WinSCP on Windows and never looked back") or banned it
at work. Plain-text saved passwords until 2017 were the second blow. puritty
has nothing to bundle; its secrets already go through `saved-secrets.md`.

**Smaller points, each worth carrying:**

- **A transfer error must not end the session.** In Tabby, a failed SFTP
  upload "interrupts the SSH connection". On one connection, a channel's
  failure has to stay that channel's.
- **Dotfiles.** WinSCP and FileZilla hide them by default, and web-hosting
  users can't find `.htaccess`. Termius hides them too.
- **Overwrite in place.** Writing over a file keeps its owner and mode; a
  delete-and-create gives the uploader's and the umask's. An upload through
  `sudo` makes the file root's.
- **Times.** FileZilla doesn't keep modification times by default; XPipe
  users asked for it. Sync features depend on them.
- **Symlinks.** ChromeOS's mount filters them out; a WinSCP setting turned
  a symlink into a plain file. Rare and severe.
- **Logins that print.** sshd starts a subsystem through the user's shell,
  so an `echo` in `.bashrc` corrupts SFTP for every client (MobaXterm and
  pfSense reports). A client can't prevent it; it can say what it read
  instead of an SFTP version, which is what the user needs to fix it.

## FT2 · Where the files are shown: five models

**A. A dialog when needed.** A drop on the window opens a folder chooser on
the remote host; nothing else is on screen until then. `feature-plan.md`
§9 is this. iTerm2 and tssh are close (tssh opens a dialog when no folder
is configured). Nobody complains about it, because few ship it; it doesn't
answer "general SFTP".

**B. A panel in the tab.** MobaXterm, WindTerm's filer, electerm, Tabby,
Remote Desktop Manager. The most asked for (FT1.2), and the one users
leave other programs for. It costs width beside the terminal, which changes
the terminal's columns when it opens, and it is a whole file manager to
build.

**C. A file tab.** SecureCRT's "Connect SFTP Tab" (on the same connection)
and Termius (one click between a host's terminal and its SFTP). In
puritty, a tab in the tab bar whose page is a file list of the same host,
over the same connection, opened from the terminal tab. Full width, so two
panes (local and remote) fit, as WinSCP's Commander does, which WinSCP's
author says 97% of its users choose. The terminal keeps its size. Less
discoverable than a panel and needs a key or a click to go between them.

**D. A separate window or program.** Xftp, SecureFX, Bitvise, Royal TS,
Cyberduck. Tolerated; users ask for it to be inside the tab instead
(Xshell's "Combine xshell + xftp tabs", Royal TS's "within the terminal
connection").

**E. A mount in the system's file manager.** ChromeOS, GNOME Files,
Dolphin, SSHFS-Win, Mountain Duck. Native, and the slowest and the most
prone to freezing (FT1.12). On Windows it needs a file-system driver
(WinFsp) or a cloud-files provider, which is a large dependency for one
feature.

Not a model of its own but beside any of them: **commands typed in the
session** (FT1.15). `put` and `get` in the shell, the files moved over
puritty's channel; see FT4.

## FT3 · What puritty has that the others don't

- **One connection, already authenticated.** On the built-in client, SFTP
  is another channel on the tab's connection: no second password, no second
  factor, through the same jump hosts (`ssh-client.md` SC21), with the same
  agent. That removes FT1.1, the most widespread complaint, and it is the
  feature HPC users can't get from MobaXterm. On Linux with OpenSSH as the
  client, `ControlMaster` on a socket of puritty's does the same
  (`feature-plan.md` §9). The cost is one connection's limits: OpenSSH's
  `MaxSessions` (10 by default) caps the channels, and a slow upload shares
  the pipe with the typing (window sizes and how the loop schedules the two
  are to be measured).
- **Its own prompt box** (SC23) can ask a sudo password over the screen, so
  "as root" can be offered without a sudoers rule (FT4, question 4).
- **tmux control mode knows each pane's directory.** In a `tmux -CC` tab,
  `#{pane_current_path}` is read by tmux on the host from the pane's
  foreground process (`/proc` on Linux), so it needs no shell hook and is
  not broken by byobu or a noisy `.bashrc`. puritty already uses the format
  (the pane lines in `TmuxMode.geng`'s `infoLines`). After `sudo su`, tmux,
  running as the user, may not be allowed to read a root process's
  directory, and after a nested ssh the path is the ssh program's own
  directory on the outer host. Neither is measured yet.
- **The shell's own directory, without tmux, needs the shell's help.**
  puritty doesn't read OSC 7 yet (`tmux.md`'s table: "build first";
  `tabs.md` reads `/proc` for local tabs only). OSC 7's hostname field
  tells a nested ssh apart (the directory belongs to another host); it does
  not tell a `sudo su` apart.

## FT4 · Options for puritty

**The drop (§9), with what the survey adds.** The dialog opens at the
directory the tab knows (tmux's pane path, else OSC 7 when its host is the
tab's host, else home) and *shows where that came from* ("the shell's
folder" or "home"), since FT1.3 says it will sometimes be wrong. The
dialog is the guard: puritty never uploads into a guessed folder without
the user seeing it. This answers PuTTY's "mayhem" objection by not
trusting the guess.

**Uploading and downloading.** Requests pipelined from the start (FT1.9);
several files and folders as the normal case, not a later one (FT1.5);
bytes as they are, never a text mode (FT1.6); write to a temporary name in
the same folder and rename at the end, so a broken transfer leaves no half
file, falling back to writing in place where rename is refused; an existing
file overwritten in place so it keeps its owner and mode (FT1 smaller
points); the modification time kept.

**Conflicts.** One question per batch with the scope said in words ("3 of
the 12 files are already there"), size and time of both sides, and
Replace, Keep both (`name (2).ext`), Skip, and "Replace if newer"; a
default per direction in the settings. Never a silent overwrite (§9
already says so).

**Progress.** In the tab (a line or a bar over the terminal's bottom edge,
or the tab title's progress, as OSC 9;4 does for programs), with cancel;
a question that needs an answer waits in the transfer list rather than
taking the keyboard from the shell (FT1.8).

**General SFTP.** Two shapes, from FT2:

- **B, the panel.** What users ask for by name. Follows the directory
  where puritty knows it, with a "go to the shell's folder" key where it
  doesn't. Remote only, as MobaXterm's is.
- **C, the file tab.** Full width, local and remote side by side, keyboard
  first (arrows, Enter, F5 copy and the Commander keys, a typed path with
  completion). Same connection. The terminal's size never changes.

**Commands in the shell, for keyboard users.** A small program on the host
(or a shell function) prints a request in an escape sequence: "get this
path", "put into this folder". Only the *request* travels in the stream; the
data goes over puritty's SFTP channel, at SFTP's speed, and the request
carries the directory it was typed in, so FT1.3 is answered exactly. The
remote side can only *ask*: a get always ends in puritty's save dialog,
a put always in puritty's file picker, so a host can neither read a local
file nor write one without the user choosing it (FT1.11's danger). Its
hostname is checked against the tab's host; a request from a nested ssh is
refused with a message, since the file is on another machine. This is
iTerm2's `it2ul`/`it2dl` shape with the bytes moved off the terminal
stream. It needs something installed on the host, as every in-band scheme
does.

**Remote edit.** Download to a folder of puritty's, open in the user's
editor, upload on each change seen, *after checking the server's copy has
not changed since* (size and time; ask if it has), and show each upload's
result in the tab ("saved to host at 14:02", or the error). Watch the
folder, not the file, so Vim's rename-on-write and tabbed editors are
seen (FT1.6). This is the feature most likely to lose someone's work, so
it should come after the rest.

**As root** (ruled out, FT6). An `exec` channel running `sudo -S -p '' <sftp-server>`, with
the password from puritty's box written first to its standard input, then
SFTP over the rest. The server's path is read from `/etc/ssh/sshd_config`'s
`Subsystem` line where it is readable, else the distributions' known
paths. Untested: whether sudo reads the password without a terminal on the
hosts Gilbert uses (`requiretty`), and what a sudo that wants a second
factor does. The panel or tab shows that it is root's view, in color.

**When SFTP is refused.** For an upload, an `exec` channel writing standard
input to the file (`cat > path`), as §8 already plans for screenshots; for
a listing, `ls`. The message says SFTP was refused and that the fallback is
in use.

**Drag out.** Windows: virtual files (`CFSTR_FILEDESCRIPTOR` and
`CFSTR_FILECONTENTS` with an `IStream`), never a shell extension. X11:
XDND with the direct-save protocol (XDS), which lets the drop target name
the folder. Both are new code in `win32` and `x11`.

**Not for puritty, with reasons.** A mount in the system's file manager
(E): the slowest and least reliable model in the survey, and a driver
dependency on Windows. A window of its own (D): what users ask to be rid
of. ZMODEM: breaks in tmux, which puritty's users run, slow, and the
remote side drives it; trzsz fixes tmux but keeps the rest. Each could be
revisited if asked for.

## FT5 · Questions for Gilbert, with leanings

1. **The panel (B) or the file tab (C) for general SFTP?** Leaning: **C
   first**, the file tab on the same connection, local and remote side by
   side, keyboard first. It never changes the terminal's size, it has room
   for two panes, and it is one view to build rather than a panel that
   must also be narrow. A panel can come later as a second way to show the
   same view. Against the leaning: B is what MobaXterm users name, and
   following the directory is most useful when the files are beside the
   prompt.
2. **The order.** Leaning: the second channel and an SFTP client with
   pipelining; the §9 drop and its dialog; uploads and downloads with
   conflicts and progress; the file tab; the shell commands; as root;
   drag-out; remote edit last.
3. **Following the directory.** Leaning: from `tmux -CC`'s pane path first
   (no shell setup; its `sudo su` and nested-ssh cases measured first), then
   OSC 7 (which means building
   it in the core), with a key for "go to the shell's folder" and the
   source shown. Never following silently into a directory on another host.
4. **As root.** Leaning: offer it, through `sudo -S` on its own channel
   with the password asked in puritty's box, after measuring it on the
   hosts you use. Not a sudoers rule, which is what users are uneasy
   about.
5. **The shell commands** (`get`/`put` printed as a request, data over
   SFTP). Leaning: yes, after the file tab, because it is the only way the
   directory is known exactly and the keyboard way to move files. It needs
   a name and a program or function on the host.
6. **§9's open questions, with the survey's answers:** the dialog is
   puritty's own, drawn as SC23's box is (a platform dialog can't show a
   remote host's folders); a drop in a local tab pastes the path, as every
   terminal does; after an upload the path is not pasted unless asked (a
   key, or a setting), since the shell may be in the middle of a command;
   §8's screenshot keeps its fixed folder (it is pasted, so where it goes
   matters less); a server with SFTP off falls back to `exec` with a
   message (FT1.14).
7. **The local side on Linux.** The file tab's local pane, and the drop's
   source, read through `os`. Leaning: the same view on both systems; no
   GTK or Explorer dialogs.

## FT6 · Gilbert's answers (2026-11-19)

The survey above is left as written; this section and those after it say
what was decided.

**No root.** "I don't care to support editing as root. Let's rule that
out too." FT4's "As root", FT3's note on the prompt box and FT5 question 4
are dropped. The SFTP session is the login user's, always. A file the user
can't write is an error with the server's text, and the answer is theirs
(upload to home, then `sudo mv` in the shell), as FT1.4 found most people do
anyway.

**Each tmux pane is its own drop target.** In a `tmux -CC` tab, a file
dropped on a pane goes to that pane's directory, read from tmux
(`#{pane_current_path}`, FT3) at the moment of the drop, not cached. So
dropping on the left pane and on the right pane can send files to two
different folders on the host, as the user sees them in the two shells.

- The pane under the pointer is the target, not the active pane. The pane
  is marked while the drag is over it (a frame or a tint), with the
  directory it will go to written in the mark, so the user knows where the
  file is going before letting go. This is the answer to FT1.3's
  fragility: the guess is shown, not trusted.
- When the directory can't be written (permission denied, a full disk, a
  read-only file system, the directory gone), the error says which and
  why, from the server's status, and offers the folder chooser (§9's
  dialog) opened at that directory, so the user picks another and the
  upload goes on. Cancel leaves nothing on the host.
- When tmux can't say (an empty path, a pane whose process isn't readable,
  the cases FT3 leaves to measure), the drop opens the chooser, as a tab
  without tmux does.
- A name already there is FT4's conflict question, before anything is
  written.

**A progress bar for large copies.** Shown when a transfer is not done
within a short time (a second, to be tuned), so a small file doesn't
flash one. It sits over the target pane or tab: the file name, bytes done
and the total, the rate, the time left, and a cancel. Several files show
one bar for the batch with "3 of 12". A transfer keeps going if the user
switches tabs, and the tab's title marks it.

## FT7 · "Writing through the shell": what the fallback is

A server can refuse the `sftp` subsystem (FT1.14): an admin turned it off,
an appliance's restricted shell, a Dropbear without `sftp-server`. The
connection still runs commands. The fallback opens an `exec` channel, the
same kind `ssh host command` uses, running

    cat > '/the/chosen/dir/name.part' && mv '/the/chosen/dir/name.part' '/the/chosen/dir/name'

and sends the file's bytes as that command's standard input, then closes
it; the exit status says whether it worked. Nothing is installed on the
host. It needs a POSIX shell, `cat` and `mv`, which a restricted shell may
not give either; then the upload fails with the server's words.

What it can't do as well as SFTP: the folder chooser has to list
directories by running `ls` and reading its output (fragile with odd
names; `find -print0` or `ls -b` help), the conflict question needs a
`test -e` first, a broken upload can't be resumed, and the names must be
quoted for the remote shell (single quotes, with `'` written `'\''`). The
§8 screenshot paste already plans this channel.

The leaning: keep it for uploads only (the drop, and §8), with the message
"SFTP is turned off on this host; uploading through the shell". The file
tab needs SFTP and says so.

## FT8 · Editing a remote file in a local program: expanded

**What it is.** In a file list (the file tab, or a "get" from the shell),
the user opens a remote file. puritty downloads it to a folder of its own
on the local machine, opens it in a local program, and watches the copy.
Each time the program saves, puritty uploads the copy back to where it came
from. To the user it is "edit that file on the server in Notepad++, or
VS Code, or GIMP", with no download and upload steps by hand. MobaXterm,
WinSCP, Termius, Cyberduck, FileZilla and electerm all do it (FT1.6).

**All file types?** The mechanism doesn't care about the type: it moves
bytes and watches for a save. What decides is the program that opens it.

- **Which program.** The default is the system's choice for the extension
  (Windows' file association, `ShellExecute`'s "open"; on Linux
  `xdg-open`), so an image opens in the image editor and a `.conf` in the
  text editor. The others let the user change it per pattern: WinSCP's
  editor list by file mask, Termius remembering the app per type,
  Cyberduck's "Edit With". A file with no extension, common on Unix hosts
  (`Makefile`, `hosts`, `crontab` files), has no association on Windows,
  so a default editor for those is needed; a setting naming a program,
  and patterns mapped to programs, would be the `config.toml` shape.
- **Text files** are the main case and the risky one: the program must
  write the bytes back as they were. puritty never converts anything (no
  text mode, FT1.6), but the editor can: some editors change LF to CRLF
  or add a byte-order mark on save (general knowledge, not measured).
  That is the editor's setting, and the upload carries whatever it wrote;
  puritty could warn when a file that had only LF comes back with CRLF.
- **Binary files** (images, office documents, PDFs, archives) work when the
  program saves to the same path. Office programs write a lock file
  (`~$name.docx`) beside the file and save through a temporary file and a
  rename; image editors often save under a new name or a new format
  ("Export"), which leaves the watched file unchanged. So for these, the
  upload follows the file that was opened, and a save under another name
  isn't uploaded (said in the tab, not silent).
- **Programs that open nothing but view** (a PDF reader, an image viewer)
  are fine: nothing is saved, nothing is uploaded.
- **Large files** download whole before the program opens; a progress bar
  as in FT6. Editing a 2 GB log this way is the wrong tool, and puritty
  can ask before downloading above a size.

**The failures the survey found, and what each needs** (FT1.6):

1. *The program saves by writing a new file and renaming it* (Vim, many
   editors, Office). A watch on the file sees the old one vanish. puritty
   watches the folder, one folder per opened file, and takes any write or
   rename to the file's name as a save.
2. *A tabbed editor* (Notepad++, VS Code) hands the file to the process
   already running and the process puritty started exits at once. So
   puritty can't use "the program closed" to mean "editing is done". The
   watch lasts until the user closes it in puritty (a list of open edits in
   the tab, each with a close), or until the tab closes.
3. *A save not noticed, or uploaded and failed* (permission denied, the
   connection gone). Each upload's result shows in the tab: "saved to
   host at 14:02", or the error, in the open-edits list and as a short note
   over the terminal. Never silent.
4. *The file changed on the server since it was opened* (someone else, a
   program, the user in the shell). Before each upload puritty compares the
   server's size and modification time with what it downloaded; if they
   differ, it asks: replace the server's copy, keep both (upload beside it
   with a name), or don't upload. Only JetBrains and Transmit check this
   among the programs surveyed.
5. *The connection drops while editing.* The local copy stays, marked
   "not uploaded"; when the tab reconnects, puritty offers to upload it
   (after check 4). The copy is never deleted while it has unsent changes.
6. *Two edits of the same file.* Opening a file that is already open
   switches to the existing edit rather than downloading a second copy.

**Where the copies live.** A folder of puritty's per host and path
(`%LOCALAPPDATA%\puritty\edit\…`, `~/.cache/puritty/edit/…`), the file
keeping its own name so the program's title and its type are right.
Removed when the edit is closed and uploaded, kept otherwise.

**Questions for Gilbert, with leanings:**

1. Whether to have this at all, now that it has been described. Leaning:
   yes, after the file tab, and last of the file features, since it is the
   one that can lose someone's work.
2. The program: the system's association by default, a `config.toml`
   table of patterns to programs, and a default editor for files with no
   extension. Leaning: yes, all three.
3. Office documents and image editors: allowed, with "a save under another
   name is not uploaded" said when it happens. Leaning: allowed; refusing
   by type would be a list to keep up.
4. The line-ending warning when LF comes back as CRLF. Leaning: yes, as a
   note, never a conversion.

## FT9 · Gilbert's answers on remote edit (2026-11-19)

"I agree to all 4 leanings" (FT8's questions):

1. **Remote edit is in**, after the file tab and last of the file
   features.
2. **The program**: the system's association by default, a `config.toml`
   table of patterns to programs, and a default editor for files with no
   extension.
3. **Office documents and image editors allowed**; a save under another
   name is not uploaded, and puritty says so when it happens.
4. **The line-ending note**: when a file that had only LF comes back with
   CRLF or a byte-order mark, a note says so; puritty never converts.

## FT10 · The plan (2026-11-19)

The steps, in order. Gilbert: the screenshot paste (`feature-plan.md` §8,
`image-paste.md`) comes before SFTP. Each step gets its own section here
with what was measured, gate cases (the hosts gate against the local sshd,
the paste gate, beelink1 for Windows), and a commit of its own. The user
guide, `docs/user/file-transfer.md`, begins with step 2.

0. **Measure what the surveys left open.** `#{pane_current_path}` after
   `sudo su` and after a nested ssh (nene, the RHEL8 hosts); the clipboard
   formats the Snipping Tool and Print Screen leave (beelink1); one
   channel's throughput against `sftp-server`, locally and to gmktec7; the
   typing latency while a large upload shares the connection.
1. **Several channels on one connection** (`packages/ssh`):
   `Ssh.Connection`'s `ourChannel` is a constant today. A table of
   channels, each with its window, events tagged by channel, `session`,
   `exec` and `subsystem` opens; one channel's failure closes that channel
   only (Tabby's lesson, FT1). Tested against the local sshd, the scripted
   server and the fuzzer.
2. **The screenshot paste.** The clipboard's image (Windows' `PNG` as it
   is, a `CF_DIB` encoded with zlib in C; X11's `image/png`); the upload on
   an `exec` channel (`cat > name.part && mv`); the absolute path pasted,
   bracketed; the setting, on by default; local tabs as IP6 says.
   Checked with Claude Code over ssh, in tmux and in `tmux -CC`, on
   beelink1.
3. **An SFTP client** (`Ssh.Sftp`, pure): version 3 and `posix-rename`,
   pipelined. Replayed, fuzzed, measured against OpenSSH's `sftp`.
4. **The transfer engine**: the queue, `.part` and rename, overwrite in
   place, times kept, the conflict question, the progress bar, the `exec`
   fallback (FT7).
5. **The drop** (§9, FT6): XDND and `IDropTarget`; the pane under the
   pointer marked with its directory in `tmux -CC`; the chooser
   (`Dialog.geng`) otherwise and on a write error; a path pasted in a local
   tab. **OSC 7 in the core** (Gilbert: in step 5; "it may not help me,
   but it could help other users"): the shell's directory and host for a
   tab without `tmux -CC`, where the shell prints it; its host checked
   against the tab's, a nested ssh's ignored; `tmux.md`'s `osc7` row then
   answered.
6. **The file tab** (FT5 question 1).
7. **`get` and `put` typed in the shell** (FT4).
8. **Drag out**: virtual files on Windows, XDS on X11.
9. **Remote edit** (FT8, FT9).

The OpenSSH-client tabs on Linux get the same through `ControlMaster`
after step 4.

## FT11 · Step 0, measured (2026-11-19)

**tmux's directory for a pane** (tmux 3.4 on nene, a tmux of its own
socket, `bash --norc`). `#{pane_current_path}` after `cd /usr/share` was
`/usr/share`, without any shell setup. The rest:

- *A root process in front.* tmux 3.4's `osdep_get_cwd` (osdep-linux.c)
  reads `/proc/<foreground process group>/cwd`, and when that fails,
  `/proc/<session leader>/cwd`, the user's own shell. A user can't read a
  root process's `cwd` (`readlink /proc/<root sshd>/cwd` failed on nene).
  So after `sudo su` and `cd /etc`, tmux says the directory where `sudo
  su` was typed, and nothing tells it apart from a true answer. Measured
  with a stand-in, since there's no sudo here or on gmktec7: `cd /tmp;
  su` waiting at its password prompt (root, `S+`) gave `/tmp` and
  `pane_current_command` `su`.
- *A nested ssh.* `cd /var; ssh gmktec7`, then `cd /etc` there: `/var`,
  the local `ssh` process's directory, with `pane_current_command` `ssh`.
- *OSC 7 is kept by tmux.* A shell on gmktec7 printing `ESC ] 7 ;
  file://gmktec7/usr/lib` set the pane's `#{pane_path}` to that URL, host
  included, with no `allow-passthrough`. So a `tmux -CC` tab can ask for
  both: `pane_current_path` (no setup, but blind to a user switch and a
  nested ssh) and `pane_path` (the shell's own word and its host, where
  the shell prints OSC 7).

What it means for step 5: the destination marked on a pane is
`pane_current_path` when `pane_current_command` is not `ssh`, `su`,
`sudo` or another program known to change host or user; `pane_path`
when its host is the tab's; else the folder chooser. A root shell's
directory is never offered without OSC 7, since tmux can't read it.

**Windows' clipboard after each kind of screenshot** (beelink1, Windows
11, a 4K screen; formats listed with `EnumClipboardFormats` from a script
in the desktop session, `clipfmt.ps1`):

| Taken with | Formats | Sizes |
|---|---|---|
| Alt+Print Screen (the active window) | `CF_BITMAP`, `CF_DIB`, `CF_DIBV5` | DIB 1.1 MB |
| Win+Print Screen (the whole screen, also saved to `Pictures\Screenshots`) | `CF_BITMAP`, `CF_DIB`, `CF_DIBV5` | DIB 33.2 MB (3840×2160×4); the saved PNG 22.9 MB |
| Snipping Tool, Win+Shift+S (Gilbert) | `PNG`, `CF_DIB`, `CF_DIBV5`, `CF_BITMAP`, `DataObject`, `Ole Private Data`, `CanUploadToCloudClipboard`, `CanIncludeInClipboardHistory` | PNG 49.9 KB, DIB 279 KB |

So the Snipping Tool's `PNG` goes up as it is, and the two Print Screen
keys leave only bitmaps, which step 2 encodes. A whole 4K screen is a
33 MB bitmap: the encoder's speed matters, and the upload is tens of MB,
so step 2 shows a progress bar for it as FT6 says.

**OpenSSH's `sftp` to gmktec7** (3.8 ms round trip, a 256 MiB file of
random bytes; `-R` is the requests in flight):

| | `-R 64` | `-R 16` | `-R 4` | `-R 1` |
|---|---|---|---|---|
| upload | 41.5 MB/s | 41.4 | 41.0 | 37.4 |
| download | 92.2 MB/s | | | 39.2 |

Uploads stop at about 41 MB/s whatever `-R` is, so something on the
path limits them, not round trips; downloads gain 2.4 times from
requests in flight. These are the numbers step 3 is held to. puritty's
own channel has no tool to measure it yet; step 1 adds one.

**Typing while a file goes up** (echo round trips of 2 bytes through
`cat` on a session channel, every 50 ms, while `sftp` uploads the same
file):

| | idle | during the upload |
|---|---|---|
| the upload on the same connection (`ControlMaster`) | 3.7 ms median | 42.9 ms median, p90 56.6, max 69.3 |
| the upload on a connection of its own | 3.7 ms | 17.2 ms median, p90 26.6, max 39.1 |

The busy link alone adds about 13 ms; sharing the connection adds about
26 ms more, the keystrokes waiting behind the file's bytes in OpenSSH's
buffers. puritty schedules its own channels, so step 1 sends a session
channel's bytes ahead of queued file data and keeps little file data
queued unsent; the same table, for puritty, is step 1's check.

**A `ControlPath` must be short.** A socket path under the scratchpad
failed: "too long for Unix domain socket" (Linux allows 108 bytes, and
OpenSSH adds a random suffix while it makes the socket). puritty's own
socket for its OpenSSH tabs goes under `$XDG_RUNTIME_DIR` with a short
name.

The plain Print Screen key on beelink1 (Gilbert): it opens Windows 11's
full-screen overlay for choosing an area, the one Win+Shift+S opens (the
Snipping Tool's screen capture, by the setting "Use the Print screen key
to open screen capture"), so a snip taken that way should leave the same
formats as the Snipping Tool row; he closed it without taking one, so
that is inferred, not listed. Alt+Print Screen and Win+Print Screen still
copy without the overlay, as measured above. Not measured: the RHEL8
hosts, which aren't reachable from here.

## FT12 · Step 1 built: channels beside the session (2026-11-19)

**`Ssh.Connection`** holds a table of channels instead of one. Channel 0
is the session (or a jump host's `direct-tcpip`), with its API as before.
Beside it:

- `openExec COMMAND` and `openSubsystem NAME` open more `session`
  channels on the same connection, numbered from 1, and answer the
  number; `writeSide`, `sendEofSide` and `closeSide` act on one.
- A side channel's events come in the step's `side` field, each with its
  number. Its refusal, a message about it that does not read, and its end
  close that channel only; the session goes on (Tabby's failure, FT1).
- Messages are dispatched by the recipient channel in them, which the
  one-channel code read and ignored.
- The session's bytes are sent as soon as the server's window allows. A
  side channel's wait until the caller calls `pump BUDGET`, which sends
  at most that many bytes from the side channels, then their EOFs;
  `sideWaiting` says whether anything could go.

**`Ssh.Session`** takes `OpenExec`, `OpenSubsystem`, `SideWrite`,
`SideEof` and `SideClose` as inputs, each naming the channel by a number
of the window's choosing (`ref`), and tells `Side { ref, event }`. Its
loop races `writable` on the socket beside the server's bytes and the
window's inputs whenever a side channel has something to send, and pumps
32 KiB each time the socket has room. The socket is set with geng-lang's
new `Os.Net.limitUnsent` (Dnene62, its `m4-puritty.md` §VA68) to keep at
most 64 KiB unsent. The app logs side notices and otherwise ignores them
until step 2 uses them.

**Measured** (`ssh-tests session --echo` to gmktec7: the session's
command writes a byte every 50 ms and times its echo, 80 of them, while a
side channel uploads 256 MiB to a reader that times itself):

| | echo during the upload | upload |
|---|---|---|
| idle (no upload) | 3.9 ms | |
| pumped 32 KiB, no unsent limit | 32.5 ms median, p90 41.9 | 49.0 MB/s |
| pumped 32 KiB, 64 KiB unsent (chosen; three runs) | **5.2, 5.7, 5.4 ms** median, p90 7.2–7.8 | 34.8, 34.5, 34.4 MB/s |
| pumped 32 KiB, 128 KiB unsent (three runs) | 16.0, 15.7, 15.6 ms | 34.9, 30.9, 33.0 MB/s |
| pumped 128 KiB, 64 KiB unsent (one run) | 14.0 ms | 48.5 MB/s |
| OpenSSH, upload on the same connection (FT11) | 42.9 ms | 41.5 MB/s (`sftp`) |
| OpenSSH, upload on its own connection (FT11) | 17.2 ms | |

The same build uploads at 383 and 387 MB/s to a local sshd, so
puritty's loop is not what costs the 30% to gmktec7; the small unsent
buffer is, on that link, whose runs vary by several MB/s. The setting
puts keys first, as puritty's priorities do; the throughput is to be
looked at again with SFTP's own numbers (step 3) and on Windows.

**Tested.** `packages/ssh/tests/sshd.py` has eight side cases against
the local sshd: an exec beside the session, two, 3 MB written and
counted, standard error, `sftp` started and ended, `sftp` refused where
the server has no `Subsystem` line, a side channel refused under
`MaxSessions 1`, and a refused subsystem followed by an exec that works;
in each the session's own command ends after them, untouched. The unit
suite adds two: a side channel's unreadable data closes only it, and its
data waits for a pump. The gate's other cases are unchanged (76 sshd, 25
scripted, the replays, fuzz, known_hosts, config). The unit suite passes
on beelink1 too.

**Left for later steps:**

- On Windows `limitUnsent` does nothing (geng-lang's register, M7):
  measure the echo during an upload on beelink1 in step 2.
- No back-pressure to the window yet: `SideWrite` is kept in memory until
  pumped, and each one copies what waits (`Bytes.flatten`). Step 2's
  files are at most tens of MB; step 4's transfer engine needs a notice
  of how much waits.
- A side channel closed before the server confirms it is not closed.

## FT13 · Step 2 built: a screenshot pasted as a file's name (2026-11-19)

`feature-plan.md` §8, with `image-paste.md` IP4's details and IP6's
answers.

**The platform asks for text or a picture in one step.** `Window.pasteOrImage`
(both platforms) pastes the clipboard's text when it has any, told by
`Pasted` events as before, and otherwise its picture as PNG, told by a new
record (14) and `PastedImage` events; `pasted` takes either.

- *X11* asks the clipboard's owner for its `TARGETS` first: any text
  target (`UTF8_STRING`, `STRING`, `TEXT`, `text/plain;charset=utf-8`)
  means text; else `image/png` is asked for and read as a paste's text
  is, INCR pieces too; an owner that won't say its targets is asked for
  text. Asking for text first and for the picture only when none came was
  the first design, and it failed the first test: `xclip` holding only
  `image/png` answers a request for `UTF8_STRING` with the PNG's bytes,
  which were pasted as text.
- *Windows*: `CF_UNICODETEXT` means text, as before. Else the
  registered `PNG` format (the Snipping Tool's, FT11) is taken as it is,
  and a bitmap alone (the Print Screen keys') is encoded by the Windows
  Imaging Component through COM, while the clipboard is open, since the
  bitmap is the clipboard's. No new library: WIC is reached with
  `CoCreateInstance`, and `ole32` was linked already.

**The app.** On the paste key, with `[clipboard] paste_images` on (the
default; a new setting, with its Korean text), `Main` asks with
`pasteOrImage`; a picture, gathered as its pieces come, is then put where
the tab's program runs (`imagePasted`):

- *A tab on the built-in client*: a side channel (FT12) runs, under `sh -c`
  so that any login shell will do,
  `umask 077; mkdir -p ~/.cache/puritty/paste; find … -mmin +1440 -exec rm
  -f {} +; f=$(mktemp …/paste.XXXXXXXX) && cat > "$f" && mv "$f" "$f.png"
  && printf "%s.png" "$f"` (`$XDG_CACHE_HOME` when set), with the picture
  as its standard input. The path it writes back is pasted, bracketed, as
  any paste, in double quotes if it has a space. Its failure, the
  session's end before it finishes, a second picture while one is on its
  way and a tab not connected are each said.
- *A local tab on Linux*: written to `Platform.pasteDirectory`,
  `$XDG_RUNTIME_DIR/puritty/paste` or `~/.cache/puritty/paste`, and its
  path pasted.
- *A local tab on Windows*: an empty bracketed paste, where the program
  asked for bracketed pastes.
- *A tab on OpenSSH's `ssh`*: refused, with why.

What happened shows in a **note** at the window's bottom right
(`Dialog.noteBar`): "Sending the picture (49 KB) to the host" while it
goes, then "Pasted the picture as …", for six seconds, or the failure in
red. The `Backend` record gained `side`, an ssh session's way to its side
channels; a pseudo terminal has none.

**Tested** (`harness/sshwindow.py`, puritty on Xvfb against the local
sshd, the clipboard owned by `xclip`, the host's command
`harness/sshwindow/paste-check.py`, which turns bracketed paste on and
reads one paste):

| case | the host received |
|---|---|
| `paste-picture` (a 971-byte PNG) | a path in `~/.cache/puritty/paste`, named `paste.*.png`, mode 0600, the picture's bytes exactly |
| `paste-text` | `hello there`, as before |
| `paste-picture-off` (`paste_images = false`) | 970 bytes that are not text: the paste asked for text, as before FT13, and `xclip` answered with the PNG, its CR LF made CR as a paste's are |

The gate's 24 other cases are unchanged (27 of 27). It finds a window
whose program set no title by its class now, as these cases' does.

**Tested on Windows by Gilbert** (2026-11-19, puritty on beelink1, pasted
into Claude Code over an ssh tab on the built-in client): Alt+Print Screen,
which leaves a bitmap that WIC turns into a PNG, and Win+Shift+S, the
Snipping Tool's PNG taken as it is. Both pasted, and Claude Code took each
as a picture. Not yet tested: the local-tab paths (Linux's file, Windows'
empty paste).

**The compiler's memory.** A build of the app after these changes was
killed under a 12 GB cap. Measured with every process the build starts
sampled every 0.2 s: it is `geng`, the fork's Haskell backend, alone, at
10.3 GB when any module changes (an 85-line one) and 16.6 GB when `Main`
does, against 1.7 GB with all cached. Most of it is a pass over the whole
program, which splitting `Main` cannot lower. Recorded in geng-lang's
register, not fixed (D761); puritty builds under 24 GB.

## FT14 · Step 3 built: an SFTP client (2026-11-19)

**`Ssh.Sftp`**, pure as the rest of `packages/ssh`: SFTP version 3 as
OpenSSH's `sftp-server` speaks it. `start` gives the `INIT`; `request`
turns a request into bytes and a number; `received` turns the channel's
bytes into events (`Ready` with the version and extensions, `Answer` by
number, `Broken` for a stream it will not read on), joining packets split
across reads and splitting those joined in one. Any number of requests may
wait at once; the caller chooses how many.

- Requests: open (for reading; for writing, made and emptied; for writing
  only if new), close, read, write, stat, lstat, fstat, setstat, fsetstat,
  opendir, readdir, remove, mkdir, rmdir, realpath and rename, which is
  `posix-rename@openssh.com` when the server offers it (it replaces a
  file already there, as `rename(2)` does) and version 3's own else.
- **Paths and names are `Bytes`**: a host's names need not be UTF-8
  (EUC-KR, the "bytes first" rule); the caller makes text of them for a
  person.
- **Sizes and offsets are `Int64`** (`Wire.uint64`, `Wire.writeUint64`,
  new), since an `Int` is 32 bits; a mode, an owner's id and the flags
  are read with `Wire.uint32Bits`, which keeps 2^31 and more as their
  bits.
- Refused: an answer before the version, a version other than 3, a
  packet longer than 16 MiB or shorter than its type.

**Tested.**

- `ssh-tests sftp`, seven unit cases: posix-rename chosen, a packet split
  in two reads, two in one, a 2^32 + 5 size and the EXTENDED bit, and the
  three refusals. In the unit gate (`ssh-sftp`), on Linux and Windows.
- `packages/ssh/tests/sftp.py`, in the ssh gate: `SftpDrive.script`, every
  request kind once, against `sftp-server` two ways, over pipes with no ssh
  (`ssh-tests sftp-local`) and over a channel beside a session to the
  local sshd (`ssh-tests session … --sftp DIR`); the same lines both ways.
  A 1,000,000-byte file is written 16 requests in flight and read back
  the same; a byte written at offset 3,000,000,000 makes a file of
  3,000,000,001 bytes; an EUC-KR name (`c7 d1`) is made, listed as its
  bytes and removed; mkdir of a directory that is there, a second
  exclusive open and a second remove give the server's failure and "no
  such file", as they should.

**Measured** (`SftpDrive.transfer`, 256 MiB up and then down, 32 KiB a
request, 64 in flight, OpenSSH `sftp`'s defaults):

| | upload | download |
|---|---|---|
| over pipes to `sftp-server` on nene, no ssh (two runs) | 1,917 and 2,081 MB/s | 2,314 and 2,684 MB/s |
| over a side channel to gmktec7 (two runs) | 27.8 and 31.0 MB/s | **92.2 and 91.6 MB/s** |
| OpenSSH `sftp -R 64` to gmktec7 (FT11) | 41.5 MB/s | 92.2 MB/s |

The client is not what limits anything: through pipes it moves 2 GB/s.
Downloads to gmktec7 equal OpenSSH's. Uploads are held where FT12 chose,
a 32 KiB pump each time the socket has under 64 KiB unsent, which keeps a
key's echo at 5 ms during an upload and costs about 30% of the upload's
rate on that link. Whether to pump more when no key has been typed for a
while is a question for the transfer engine (step 4), measured there.
A request of 256 KiB fails: OpenSSH's `sftp-server` takes no packet of
256 KiB or more, its header counted, so the engine keeps to 32 or 64 KiB.

The SFTP script and transfer have an over-the-session mode (`--sftp`,
`--transfer SIZE,PIECE,MOST` on `ssh-tests session`), which is how the
gmktec7 numbers were taken; the app does not use `Ssh.Sftp` yet (step 4).

## FT15 · The paste folder chosen (2026-11-19)

Gilbert, after FT13's Windows test: the host's folder for a pasted
picture should be a setting, a fixed folder for now. It stays a temporary
place; putting the picture in the shell's current folder is for
drag-and-drop later (§FT10's step 5, once OSC 7 tells puritty that
folder).

**The settings.** `[clipboard] paste_folder`, and `paste_folder` in a
`[hosts.NAME]` entry, which comes first (`Main.pasteFolderOf`). Empty, the
default, is `~/.cache/puritty/paste` as before (`$XDG_CACHE_HOME`'s when
set); `~` or `~/…` is the home on the host. Both are in the settings
window, the host's in its host page, with their Korean text.

**The cleanup made safe for any folder.** FT13's command removed every file
in the folder older than a day, in its subfolders too: harmless in
puritty's own cache folder, not in one the user names. Now pictures are
named `puritty-paste.XXXXXXXX.png`, and each paste removes only files of
that name, in the folder itself (`find "$d" -maxdepth 1 -type f -name
"puritty-paste.*" -mmin +1440`), and nothing else. The folder is made if
it is not there.

**Quoting.** The folder reaches `sh -c '…'` inside double quotes, with `\`,
`"`, `$` and backquote escaped (`Main.doubleQuoted`), and the whole script
inside single quotes with each `'` closed and reopened; `~/` becomes
`"$HOME/"` followed by the rest, quoted.

**Tested** (`harness/sshwindow.py`, as FT13's cases):

| case | the host received |
|---|---|
| `paste-picture` | as FT13, the file now named `puritty-paste.*.png` |
| `paste-picture-folder` | settings' folder `/nowhere/not-this-one`, the host's `p "x" $HOME 'q'` under the home, holding beforehand puritty's picture of two days ago, the user's `keep.txt` of two days ago and puritty's picture of now: the picture went to the host's folder, mode 0600, its bytes exact; afterwards the folder holds `keep.txt`, the recent picture and the new one, the old picture gone |

28 of 28 cases pass. The settings' folder used alone, with no host
folder, is not a case of its own: it is the same command with another
string.

## FT16 · Asked first: paste_images is ask, allow or deny (2026-11-19)

Gilbert: writing a pasted picture writes to the user's files, so the user
should give puritty permission. `[clipboard] paste_images` was on or off;
it is now `"ask"` (the default), `"allow"` or `"deny"`.

- **ask**: a box (`Main.pasteBox`, drawn as the close question is) names
  the file by its whole path and where it goes ("on build.example.com",
  "on this computer"), and nothing is written until the user says yes:
  Enter, `y` or Paste; Escape, `n` or Don't paste writes nothing and says
  so. The box takes the keys and the pointer while it is up.
- **allow**: as FT13 and FT15, no question.
- **deny**: a picture is not pasted anywhere, and a note says why.
  (`false` used to ask the clipboard for text alone, and `xclip` holding
  only a PNG answered with the PNG's bytes, pasted as text; `deny` pastes
  nothing.)

A local tab on Windows writes nothing (the empty bracketed paste), so it is
not asked about; a local tab on Linux is, its file in
`Platform.pasteDirectory` named before the question.

**Naming the file before it is written.** FT13's command let `mktemp` choose
the name on the host, so the name was known only after the file was. Now
puritty chooses it, `puritty-paste.` and ten hex digits from
`Os.Random.bytes 5`. For an ssh tab under "ask", the host is first asked
only for its folder's path (`folderCommand`: `printf` of the folder, with
`$XDG_CACHE_HOME` and `~/` as the host reads them; nothing made or
changed), so that the question shows the path as it will be. On yes,
`uploadCommand` writes the bytes to `NAME.part`, made only if it is not
there (`set -C`), and renames it to the name if nothing has that name.
The old-pictures cleanup runs only then, so a "no" leaves the host as it
was. If the tab is no longer the one shown, or no longer connected, when
the answer comes, nothing is sent and that is said.

A long path is broken after its `/`s into lines of at most 56 characters
(`wrapPath`), since the box, 560 pixels at most, cuts a line off at its
edge, and the end of the path, the file's name, is what must show.

**Tested** (`harness/sshwindow.py`; the paste cases from FT13 and FT15 now
set `paste_images = "allow"`; `paste-check.py` waits 12 s for a paste, was
8, and writes the path it received beside its report):

| case | the host received |
|---|---|
| `paste-picture-off` (`"deny"`) | nothing pasted |
| `paste-picture-ask` (the default), Return | the picture, mode 0600, its bytes exact, at the path the question named (the diagnostic log's `asked: write PATH` against the path received) |
| `paste-picture-ask-no`, in FT15's folder `p "x" $HOME 'q'`, Escape | nothing pasted; the folder holds what it held before, puritty's two-day-old picture too, since nothing but the folder's path was asked of the host |

30 of 30 cases pass. The question as drawn was looked at in the cases'
window pictures (`--shots`): the FT15 folder's path in three lines, the
file's name whole on the last.

## FT17 · Step 4 begun: faster uploads while no key is typed (2026-11-19)

FT14 left a question for the transfer engine: whether to send more when no
key has been typed for a while. Gilbert: yes.

**What changed** (`Ssh.Session`). A session's options carry a `Pacing`:
while keys come, the socket keeps at most 64 KiB unsent and each turn
sends 32 KiB of the side channels, as FT12 chose. Once no key has come for
a second (`quietMs`), the socket is set to keep 256 KiB unsent and each
turn sends 128 KiB. The next key sets it back before it is sent, so that
key waits behind at most what the quiet setting let in, and the keys after
it behind FT12's 64 KiB. `Os.Net.limitUnsent` is set again on the open
socket (`TCP_NOTSENT_LOWAT` can be changed at any time); a link through a
jump host has no socket of its own and is not paced, as before.
`ssh-tests session --pacing UNSENT,PUMP,QUIET_MS,QUIET_UNSENT,QUIET_PUMP`
runs with another. The measuring scripts are kept now, in
`packages/ssh/tests/measure/` (`echo-timer.py`, which takes the gap
between keys, and `sink.py`); FT12's were in `/tmp` and were lost.

**Measured** (to gmktec7, which ran a load average of 35 throughout, so
each comparison was made in the same minutes, interleaved):

Uploads, 256 MiB on a side channel, no keys at all, MB/s (two rounds; a
third, when the load rose, was 20 to 35 for every setting, OpenSSH's too):

| quiet setting (unsent, pump) | round 1 | round 2 |
|---|---|---|
| 64 KiB, 32 KiB (FT12's, unchanged) | 31.4 | 34.8 |
| **256 KiB, 128 KiB** | **47.7** | **49.0** |
| 1 MiB, 256 KiB | 48.4 | 49.5 |
| 64 MiB, 512 KiB (no limit in effect) | 48.5 | 49.2 |
| OpenSSH `sftp -R 64`, its own connection, login counted | 46.5 | 41.9 |

The first key after a quiet spell (12 keys 1.2 s apart during a 1 GiB
upload; median, p90, two runs each):

| quiet setting | run 1 | run 2 |
|---|---|---|
| 64 KiB, 32 KiB (FT12's) | 5.7, 7.6 ms | 8.7, 13.5 ms |
| 128 KiB, 64 KiB | 17.0, 28.3 ms | 14.6, 19.8 ms |
| **256 KiB, 128 KiB** | **16.6, 22.0 ms** | **17.3, 23.1 ms** |
| no upload | 4.3, 4.8 ms | |

Steady typing (80 keys 50 ms apart, which never go quiet): 5.2 ms median
with FT12's setting and 5.3 to 5.4 ms with the quiet one, both runs; the
quiet one's worst is the run's first key, which comes after a second's
quiet.

**Chosen: 256 KiB and 128 KiB after one second.** An upload with no typing
runs 40% faster, as fast as with no limit and as OpenSSH's; the first key
after a pause of a second or more costs about 17 ms instead of 6 to 9, and
every key after it is as before. OpenSSH sharing its connection with an
upload gave 42.9 ms for every key (FT11). 128 KiB's first key cost the
same and its rate was not measured, so the larger, measured as fast as no
limit, is taken. On a slower link
the first key waits longer, by 256 KiB's time to drain (a quarter second
at 1 MB/s); a pacing from the link's measured rate would bound it, and is
left until a slow link shows it matters. On Windows `limitUnsent` does
nothing yet (FT12), so only the pump changes there.

**The rest of step 4**, in order, each held by cases against the local
sshd and `sftp-server` in `ssh-tests`, as FT14's were:

1. **Back-pressure** (FT12's leftover): how much waits for a side channel,
   so the engine keeps a few pumps' worth queued instead of a whole file
   in memory, and `SideWrite` stops copying what waits.
2. **`Ssh.Transfer`**, pure, over `Ssh.Sftp`: a queue of uploads and
   downloads, files and folders, pipelined; a new file written to
   `NAME.part` and renamed at the end (`posix-rename`), falling back to
   writing in place where the rename is refused; a file replaced written
   in place, so it keeps its owner and mode; the modification time kept;
   names already there found before anything is written, for the conflict
   question (FT4: Replace, Keep both, Skip, Replace if newer), answered by
   the caller; progress as bytes done of the total; cancel, which removes
   the `.part`.
3. **The `exec` fallback** for uploads where the server refuses SFTP
   (FT7): `cat > NAME.part && mv`, with the message saying so. Built,
   FT18, behind a setting that is off by default.

The progress bar and the conflict question are drawn by the app, and
their first caller is step 5's drop; they are built with it, on the
engine's events, rather than here with nothing to start a transfer.

**1, back-pressure, built.** A side channel's data waiting to be sent was
one `Bytes`, and each `writeSide` made a new one of what waited and the
new bytes (`Bytes.flatten`, which copies everything): an SFTP upload,
which writes one request at a time with up to 64 waiting, copied what
waited at every request. It is kept in pieces now, with their length
beside them; a packet copies only its own bytes, cutting a piece where it
ends (`Bytes.slice`, which costs nothing). Each pump that sends a side
channel's data tells how much still waits, a new `Connection.Sent`
event, which `Session` passes on as a `Side` notice, so that a writer
with no answers to pace it (the `exec` fallback, FT7) can keep a little
queued instead of a whole file. A unit case (`ssh-connection`, 8 now)
writes three pieces, pumps 32 KiB across the first two, and checks the
bytes, their order, and `Sent` saying 87,232 and then 0.

Measured, SFTP to a local sshd (`packages/ssh/tests/measure/local-sftp.py`,
256 MiB in 32 KiB requests, 64 in flight, no network, so the client's own
cost):

| | upload | download |
|---|---|---|
| before (72505cf, built in a worktree; two runs) | 136.6, 135.6 MB/s | 360.8, 366.2 MB/s |
| pieces (two runs) | **318.4, 325.3 MB/s** | 370.2, 355.5 MB/s |

To gmktec7 the link set the rate in the same minutes (ours 29.4 and 22.7
MB/s up, OpenSSH's `sftp` 18.5 and 29.4), so the gain shows only where
the client's work is what limits.

**2, `Ssh.Transfer`, built.** A pure state machine over `Ssh.Sftp`, since
the app runs on events and cannot wait in a chain of tasks as
`SftpDrive` does. It is told the channel's bytes, what the caller did on
this computer, and the answer to a conflict; it answers bytes to send,
`Local` actions for the caller (`ReadPiece`, `CreateFile`, `WritePiece`,
`Move`, `RemoveFile`), and events (`Conflicts`, `Progress`, `Done`,
`Skipped`, `Failed`, `Finished`, `Broken`). A batch's jobs are
`Upload`, `Download` and `MakeDir` (a folder made for an upload of a
folder, which the caller lists, having the file system). Files go one
after another, each pipelined: 32 KiB a request, 64 in flight.

- **Every target is looked at first** (`stat`), and if any name is there
  already, one question for the batch: replace, keep both, skip, replace
  if newer. A folder in the way is not asked about; that upload fails,
  saying so. A download's target the caller looks at, here.
- **A new file goes to `.NAME.puritty-part`**, made only if it is not
  there, and is renamed at the end (`posix-rename` when offered). A part
  in the way, left by a transfer that broke, is removed and made again,
  once. Where the server refuses the rename, the part is removed and the
  file written under its own name.
- **A file replaced is written in place** (`TRUNC`), so it keeps its
  owner and mode; a failure then says the file is partly written.
- **Keep both** finds the first free `name (N).ext` from 2; the number
  goes before the last dot, or at the end of a name with none or with only
  a leading one (`.hidden (2)`).
- **The modification time** is set on the open file before it is closed
  (`fsetstat`). A download's is handed to the caller with `Move`, which
  sets it on the part with geng's `Os.File.setTimes` (geng-lang Dnene63,
  `m3-os.md` §OS39) before the rename, so a failure to set it leaves no
  file in place.
- **`Finished` waits for every answer still owed.** OpenSSH's
  `sftp-server` exits when its input ends and drops the requests it has
  not done, so an engine that said "finished" with a close and a removal
  in flight left the part behind once the caller closed the channel (the
  first `cancel` pin had `.big.bin.puritty-part` in it). Cancel, a
  failure and the end of the batch now drain first.

**Tested** (`packages/ssh/tests/transfer.py`, in the ssh gate):
`ssh-tests transfer-local` (`TransferDrive`) runs one batch against
`sftp-server` over pipes and does the local actions with `Os.File`; the
script sets up each case's folders and pins what the engine said and what
the folders hold afterwards, each file's size, mode, bytes and time
against its source. Thirteen cases: new files (a 1,000,001-byte one, an
empty one, a folder and a file in it), skip, replace in place (the host's
mode 0600 kept), keep both (`a (3).txt` past an `a (2).txt`, `noext (2)`,
`.hidden (2)`), replace if newer (one replaced, one skipped), a stale
part, a folder that is not there (the server's "No such file"), a folder
in the way, folders made (one there already, one a file), a download, a
download's keep both, a cancel after three progress steps (no part left,
both files counted skipped), and a server that refuses renames
(`sftp-server -P rename,posix-rename`; its log shows the rename refused,
the part removed and the target opened with `TRUNCATE`). Five runs gave
the same pins.

Not yet: a folder downloaded whole (the host's folders listed); the
app's use, with step 5. Item 3 is FT18.

## FT18 · Step 4's fallback: uploads through the host's shell (2026-11-20)

**Off unless the user turns it on.** Gilbert, 2026-11-20: the fallback
runs commands on the user's behalf, so it is guarded by a setting,
disabled by default: `[files] upload_through_shell = false` (Advanced
page, with its Korean words). Where a host refuses the `sftp`
subsystem, an upload with the setting off fails, saying SFTP is off
there and naming the setting; with it on, it goes through the shell,
saying so. A host that has SFTP is never sent through the shell. The
screenshot paste keeps its own shell commands (FT13, FT16): Gilbert,
the same day, `paste_images` is its permission, and the new setting
does not cover it.

**`Ssh.ShellTransfer`**, pure, beside `Ssh.Transfer` and with its jobs,
choices, conflicts and events, so that the app drives both the same way.
Where `Transfer` is told one channel's bytes, this one asks the caller
to open, write, end and close `exec` channels (`Channel`: `Open`,
`Write`, `Eof`, `Close`, each with a reference from a base the caller
gives) and is told their events. Every command is `sh -c '…'`, so the
login shell does not matter (zsh's ran them in the gate), each name in
single quotes with `'` written `'\''`. (As first built, a name that was
not UTF-8 failed its job, since a command was text; FT19 made it bytes.)

- **One command looks at every target first**: `test -d`, `test -e`, the
  size from `ls -lnd` (fields, not the name, under `set -f`), and the
  time from `date -r FILE +%s` where the host's `date` has it (GNU, BSD,
  busybox; elsewhere the time is not known, and "replace if newer" then
  skips). The same one question for the batch follows.
- **A new file** is written by `cat` to `.NAME.puritty-part`, after
  removing a part a broken transfer left, under `set -C`; its size is
  checked against what was sent (`wc -c`); its time set with
  `TZ=UTC0 touch -m -t CCYYMMDDhhmm.SS`, POSIX's form; then renamed with
  `mv` to the first of its names not there at that moment, the name or,
  for keep both, `name (2).ext` to `name (50).ext`, which the command
  prints by number. Where the folder is not there, it says so.
- **A file replaced** is written in place by `cat`, keeping its owner
  and mode, its size checked and its time set.
- **A folder** is `mkdir`, if not there. **A download** fails: it needs
  SFTP.
- **Cut short or cancelled**, the command's input closes early; `cat`
  ends, the size is short, and the part is removed before anything is
  said (the channel may be gone). OpenSSH's sshd closes a session
  channel only once its command has exited, so the `Ended` the engine
  waits for comes after the removal.
- **Paced by the channel's queue**: the file is read here 32 KiB a piece,
  with at most 256 KiB read and not yet sent; `Connection.Sent` (FT17's
  item 1) says how much still waits, and more is read as it drains.

**Tested.**

- `packages/ssh/tests/shell-transfer.py`, in the ssh gate: `ssh-tests
  session … --upload` (`ShellDrive`) over a session to sshd.py's local
  sshd with no `Subsystem` line, so the subsystem is refused as on such
  a host. Sixteen cases: `transfer.py`'s twelve that apply, run through
  the shell (the same results: names, conflicts, keep both's `a (3).txt`,
  the replaced file's mode 0600 kept, times kept, the stale part, the
  cancel leaving no part; a folder's `mkdir` failure in coreutils' words;
  downloads failing), and four of its own: names with quotes, `$HOME`,
  `*` and a leading `-` arriving as written; 5 MiB, past what is read
  ahead; the setting off, nothing written; a host with SFTP, not sent
  through the shell. Five runs gave the same pins.
- Two unit cases in the `sftp` suite (9 now, `harness/units.py`): an
  upload reads 4 pieces of 32 KiB on starting with 128 KiB allowed, none
  more once they are written, and 4 more when the queue says it is
  empty (a changed expectation fails it); and a cancel while the command
  is opening closes it once it has started, the batch then cancelled.

Measured, 256 MiB to the local sshd, connecting included, three runs:
241 to 243 MB/s, the bytes the same (SFTP's own was 320 MB/s with the
connection made, FT17).

## FT19 · Names in the host's own character set: EUC-KR (2026-11-20)

*Why.* Gilbert: a user may be working in an EUC-KR environment. FT18's
engine failed any name that was not UTF-8, because `Session.OpenExec`
and `Connection.openExec` took the command as a `String`, written as
UTF-8. SSH sends an `exec` command as bytes, and `sh` takes every byte
inside single quotes as it is, but the quote: EUC-KR's bytes past ASCII
are 0xA1 to 0xFE, and CP949's second bytes add 0x41 to 0x5A, 0x61 to
0x7A and 0x81 to 0xFE, so neither ever makes 0x27. Nothing needed the
limit. Local paths had the same flaw on this computer's side:
`Ssh.Transfer`'s `Upload.local`, a download's `to`, `part` and
`keepBoth`, and every `Local` action's path were `String`s.

**Changed.**

- `Connection.openExec` and `Session.OpenExec` take the command as
  `Bytes`, sent with `Wire.writeString`. The paste's commands (FT13) are
  made from text, as before, with `Bytes.fromString`. The session's own
  `command` (a host's setting) is still text: it comes from the settings
  file, which is UTF-8. (FT20 sends both in the host's character set.)
- `Ssh.ShellTransfer` builds every script as bytes, each name spliced in
  as it came, `'` written `'\''` byte by byte. Its `notUtf8` failure is
  gone.
- `Ssh.Transfer` and `Ssh.ShellTransfer` take local paths as `Os.Path`,
  which holds a path's exact bytes (`Path.fromBytes`); the drivers read
  their arguments as bytes (`Os.Env`'s `argsAsBytes`).

Which character set a dropped file's name should be turned into, for a
host whose `charset` is `euc-kr` while this computer names files in
UTF-8, is step 5's: the drop knows both ends. The engines move names as
the caller gives them.

**Tested without an EUC-KR machine.** Linux names files by bytes, so a
name's EUC-KR bytes are a name like any other; what has to be real is
the host running in EUC-KR. glibc has no Korean locale installed here,
and `localedef -i ko_KR -f EUC-KR` (and `-f CP949`) builds one from
glibc's own sources without root, into the gate's work folder.
`shell-transfer.py` runs the Korean cases with `SetEnv LOCPATH=… LANG=…
LC_ALL=…` in the test sshd's config, so the login shell (zsh), `sh`,
`wc`, `ls` and `mv` all run in that locale; two pinned checks show it
holds (`locale charmap` says `EUC-KR` and `CP949`, and `wc -m` counts the
4 bytes of 한글, and of CP949's 똠방, as 2 characters).

- `transfer.py` (SFTP) and `shell-transfer.py` (the shell) each gain
  three cases: EUC-KR names both ways (`한글 파일.txt`, `it's 한.txt`
  with a quote inside, a folder `폴더` made and a file put in it, and over
  SFTP a download `받은.bin`, part and all); keep both on an EUC-KR name
  (`한글 파일 (2).txt`); and CP949's `똠방각하.txt`, whose 똠 is `8C 63`,
  a second byte that is an ASCII `c`. Every file arrives under its own
  bytes with its own bytes in it and its time kept. A name that is not
  UTF-8 is pinned as its bytes, `\xc7\xd1…`.
- A unit case (`sftp` suite, 10 now): `한'글.txt` in EUC-KR given to the
  engine, whose command is not UTF-8 and holds `C7 D1`, the quote
  escaped twice over (the script's quotes and `sh -c`'s), then `B1 DB`.
  With the expected escape changed, it fails.

All pass three runs in a row.

## FT20 · The paste folder and a host's command in the host's character set (2026-11-20)

*Why.* FT19 left two commands made from the settings file's text and
sent as UTF-8: the screenshot paste's (FT13, FT15), which hold
`paste_folder`, and the session's own, a host's `command`. On a host
whose `charset` is `euc-kr`, a Korean folder in `paste_folder` was made
under its UTF-8 bytes, a name its shell shows as mojibake; a Korean word
in `command` went the same way. Gilbert: fix both.

**Changed.**

- `Connection.Session`'s `command` is `Bytes`, and `Session.optionsFor`
  takes it so. `RemoteCommand` from `~/.ssh/config` goes as the file has
  it, as OpenSSH sends it.
- The app encodes text for a command with `Vt.Charset.encode`, the
  encoder typed keys go through: the paste's two commands in the tab's
  character set, a host's `command` in that host's (`charset`, else the
  window's). Where a character has no form in it (strict EUC-KR is KS X
  1001 only), nothing is sent: the paste stops with "the paste folder's
  name has characters EUC-KR cannot write", and the session with the
  same about its command, rather than a `?` in a name.
- What the paste's commands print back, the folder's path and the
  host's error, is decoded the same way (`Vt.Charset.decode`), so the
  path asked about and the path pasted are the folder as the host has
  it, which the paste then sends in the tab's character set.

**Tested.** A window case, `paste-picture-euc-kr` (31 in all now), runs
the app against sshd.py's sshd with its commands in `ko_KR.EUC-KR`
(FT19's locale, `SetEnv`), a host entry with `charset = "euc-kr"`, a
`paste_folder` named 붙여넣기 폴더 and a `command` that writes its result to
결과.txt. The result is found under 결과.txt's EUC-KR bytes; the picture
went to the folder under its EUC-KR bytes, none under UTF-8's; the path
pasted back, read in the host's locale, names the picture, whose bytes
are the clipboard's. Built with the commands sent as UTF-8 instead, the
case fails: the result is not found, and the folder is made under
UTF-8's bytes.

(The case's first run used `~/` for the folder; sshd's `$HOME` is the
real one, so the folder was made in the user's home. It was empty, and
removed; the case uses a folder under its own work directory.)

## FT21 · Step 5's survey: what a drop carries (2026-11-20)

Measured before building the drop (FT10 step 5), on both systems. The
probes are in `probes/xdnd/` and `probes/drop-windows/`.

### Linux: XDND from Nemo and Dolphin

A probe drop target (`probes/xdnd/target.py`, python-xlib, XDND version 5)
logs the types a source offers, each position, and on the drop the data in
every type. `drag-from-nemo.py` opens a file manager under Xvfb on a folder
of test names (`a plain.txt`, `it's $HOME.txt`, `한글 이름.txt` in UTF-8, a
name in EUC-KR's bytes, `a folder`) and drags with xdotool: each alone,
then five selected together. Nemo is the one installed here (GTK, as
Nautilus is); Dolphin 26.08.3 (Qt 6, KDE) came from nixpkgs for the run.

| | Nemo | Dolphin |
|---|---|---|
| version | 5 | 5 |
| types | `x-special/gnome-icon-list`, `text/uri-list`, `UTF8_STRING`, `COMPOUND_TEXT`, `TEXT`, `STRING`, `text/plain;charset=utf-8`, `text/plain` | `text/uri-list`, `text/x-moz-url` (UTF-16), `text/plain`, `application/x-kde4-urilist` |
| positions a drag | 12 to 21, each with `XdndActionCopy` | 11; in one run those after the first had no action |
| five items | five `file://` lines, CRLF | the same |
| `'` and `$` | not escaped in the URI | the same |
| a UTF-8 Korean name | percent-encoded UTF-8 | the same |
| an EUC-KR name | `%C7%D1%B1%DB`: the bytes as they are | `%EF%BF%BD%D1%B1%EF%BF%BD`: each byte that is not UTF-8 made U+FFFD |

- **`text/uri-list` is the one to read**: both offer it, it is exact for
  any name GTK can see, and the text types are no better (Nemo's
  `UTF8_STRING` holds the EUC-KR bytes raw, not UTF-8). Percent-decoded,
  each line is a path's bytes, for `Os.Path.fromBytes`.
- **Dolphin loses a name that is not UTF-8**, and not only under a UTF-8
  locale: run in `ko_KR.EUC-KR` (FT19's locale) it sent the same
  `%EF%BF%BD`, since Qt 6 takes every file name as UTF-8. No drop target
  can get that file back; puritty can only say the file it was given is
  not there.
- **A missing action is a copy.** XDND 5 lets a source leave it out after
  the first position.
- puritty's X11 layer (`packages/x11/src/Ext/puritty_x11.c`, Xlib) already
  reads selections, INCR included, for the clipboard and its pictures;
  XDND's data comes the same way, a `ConvertSelection` of
  `XdndSelection` with the drop's time.

Not measured: a drop from a Wayland program into puritty under XWayland
(GNOME and KDE on Wayland bridge it to XDND; there is no Wayland session
here), and a Flatpak'd source, which may offer only the portal's types.

### Windows: OLE drops on beelink1

A WinForms window (`probes/drop-windows/drop-probe.ps1`; WinForms' drop
target is OLE's `IDropTarget`, the one puritty's window would register),
run in Gilbert's session, logged four drops he made (the log is kept
beside it, `beelink1-2026-11-20.log`):

| Dragged | Allowed | Formats | What it gives |
|---|---|---|---|
| `한.txt` from Explorer (OneDrive Documents) | copy, move, link | `Shell IDList Array`, `FileDrop`, `FileNameW`, `FileGroupDescriptorW`, `FileContents`, drag image and context | `FileDrop`: the path, 한 intact |
| three files and a folder from Explorer | copy, move, link | the same without the virtual-file pair | `FileDrop`: four paths, the folder among them |
| a file inside a `.zip` in Explorer | copy, move | `Shell IDList Array`, `FileGroupDescriptorW`, `FileContents` only | no path at all: the name `built-from.txt` and 19 bytes, as a stream |
| a download from the browser's list | copy, link | `FileDrop`, drag image and context | `FileDrop`: the path |

- **`CF_HDROP` (`FileDrop`)** is what Explorer and the browser give:
  UTF-16 paths, read with `DragQueryFileW`, Korean as it is.
- **A file inside a zip is virtual**: `FileGroupDescriptorW` gives names
  and sizes, and `FileContents` the bytes, a stream for each file asked
  for by its index. Nothing on disk to read with `ReadPiece`.
- `DragOver` came 24 to 33 times a drag, each with the pointer's screen
  position; the drop has no modifier keys held.
- puritty's window runs on a thread of its own with its own message loop
  (WS4, WS15): that thread calls `OleInitialize` and `RegisterDragDrop`,
  and its `IDropTarget` answers each `DragOver` at once, a copy, posting
  the position on to the program, as the window's other events go.

### tmux and OSC 7

- **tmux's folder for a pane** was measured in FT11: `pane_current_path`
  needs no shell setup but is blind after `sudo su` (a root process's cwd
  can't be read) and inside a nested ssh (the local `ssh`'s folder);
  `pane_path` holds OSC 7, with its host, as the shell sent it.
- **OSC 7 is mostly not sent over ssh unless set up.** Mint's (and
  Fedora's) `/etc/profile.d/vte-2.91.sh` sends it only when `VTE_VERSION`
  is 3405 or more, which a VTE terminal sets in its own environment and
  ssh does not carry (sshd takes only `LANG` and `LC_*` by default). fish
  sends it by default. So the folder chooser stays the common path for an
  ssh tab without `tmux -CC`; OSC 7 serves those who set it up.
- puritty's core does not take OSC 7 yet (`tmux.md`'s `osc7` row: no).

### The plan for step 5

1. **The drop, on both systems.** X11: `XdndAware` (5) on the window;
   Enter, Position, Leave and Drop answered (`XdndStatus` accepting a copy
   where `text/uri-list` or `application/x-kde4-urilist` is offered,
   `XdndFinished`); the list read through the selection code and
   percent-decoded to bytes. Windows: `IDropTarget` on the window's
   thread, `CF_HDROP` read as UTF-16 and given on as UTF-8. Both give the
   program the same events: a drag over a cell, a leave, a drop of paths.
2. **A local tab** pastes the paths, each quoted for the shell, as other
   terminals do (FT5 question 6).
3. **An ssh tab**: the pane under the pointer marked with its folder in
   `tmux -CC` (FT6, FT11's rule); otherwise, or on a write error, the
   folder chooser, a dialog listing the host's folders over SFTP.
4. **The transfer in the app**: SFTP's engine, or the shell's where SFTP
   is refused and `upload_through_shell` allows it (FT18); the conflict
   question; the progress bar after a second, with cancel and "3 of 12";
   a folder dropped is made and its files listed here, each a job.
5. **Names in the host's character set**: a local name turned into the
   host's `charset` with `Vt.Charset.encode` (FT20), a name that set
   can't write failing its job, saying so.
6. **OSC 7 in the core**: the shell's folder and host for a tab, its host
   held against the tab's, so a nested ssh's is not offered.

### For Gilbert

1. **A file dragged out of a zip (or an Outlook attachment) on Windows**
   is not on disk: its bytes come as a stream. Taking it means writing it
   to a folder of puritty's first and uploading that. Leaning: not in the
   first drop; such a drop says the program gave no file to send, and it
   comes later if wanted.
2. **A name Dolphin has already spoiled** (a file named in EUC-KR on a
   UTF-8 or Qt 6 desktop) can't be sent from a Dolphin drag at all.
   Leaning: say so, naming the file as Dolphin gave it, and nothing more.
3. **A local file whose name is not UTF-8** (EUC-KR bytes on this
   computer), dropped on a host whose `charset` is `euc-kr`: leaning,
   sent as its bytes, since they are already that host's; to a UTF-8 host,
   refused, since there is no right UTF-8 for them.

**Answered (2026-11-20).** Gilbert: the three leanings, as written. A
virtual file is not taken in the first drop, which says the program gave
no file to send; a name Dolphin spoiled is reported as given; a local
name that is not UTF-8 goes as its bytes to an `euc-kr` or `cp949` host
and is refused for a UTF-8 one.

## FT22 · Step 5, item 1 built: the drop on both systems (2026-11-20)

**X11** (`packages/x11/src/Ext/puritty_x11.c`, its DROPS section). The
window sets `XdndAware` to 5. A drag's Enter names its types (in the
message, or past three in the source's `XdndTypeList`); the window takes
`text/uri-list`, else KDE's `application/x-kde4-urilist`. Where the
window is on the screen is asked once a drag, on Enter, a round trip,
since positions come in the root's pixels. Each Position is recorded and
answered at once with a Status (accepted, a copy, every position wanted);
a missing action counts as a copy (FT21). Leave is recorded. On Drop the
list is read by the paste's code, `XdndSelection` as a third selection
asked for with the drop's own time, so a long list comes in INCR pieces
without the window waiting; Finished goes back when it has come. A drop
with no files offered gives an empty list and a refused Finished; one
while a paste is still being read counts as a leave, since the two would
share the paste's buffer.

**Windows** (`packages/win32/src/Ext/puritty_win32.c`, its DROPS
section). The window's thread calls `OleInitialize` and registers an
`IDropTarget` written in C (its vtable, `IID`s declared in the file as
the jump list's are, no import library). A drag holding `CF_HDROP` is
taken as a copy; one holding only `FileGroupDescriptorW` (virtual files)
is taken too, so its drop can say why nothing came; any other is refused.
`DragOver` answers at once and records the position, made the window's
from the screen's. A drop reads `CF_HDROP` with `DragQueryFileW`, UTF-16
to UTF-8, a path a line, into a buffer of its own under the queue's lock,
since it fills on the window's thread and is taken on the program's.

**The same events from both** (records 15, 16, 17 in the X11 file's
list): `Window.DragOver` (the pointer's place in the cells' area, with
the area and the cell, as a pointer event's), `DragLeft`, and `Dropped
more`, whose list `Window.dropped` takes: `file://` URIs on X11, paths on
Windows.

**The app** (`app/src/Drop.geng`, `Main.filesDropped`). `Drop.paths`
reads either shape into path bytes: a `file://` URI percent-decoded to
bytes after its host, a `#` line skipped, another scheme counted as not
a file, a Windows path taken as it is. Then:

- every path is checked to be there (`File.exists`): a name a file
  manager spoiled names no file (FT21: Dolphin's U+FFFD), and the note
  says so, with the name as given, as Gilbert chose;
- in a tab on this computer the paths are pasted, each followed by a
  space as GNOME Terminal and Windows Terminal paste a drop: for a POSIX
  shell a path with anything but letters, digits and `_./+-:@%,=` in
  single quotes, `'` written `'\''`; on Windows in double quotes, a
  backslash plain;
- a name that is not UTF-8 is read in the tab's character set, so the
  paste hands the shell its own bytes; one the set can't carry, or any
  in a UTF-8 tab, is not pasted, and the note says so;
- a drop with no file on disk says the program it came from gave none,
  and a file inside a zip or an attachment must be saved first;
- in an ssh tab, for now, a note that sending dropped files is not built
  yet (items 3 and 4).

The drag's position is not yet used: item 3 marks the pane under it.

**Tested.**

- Nine unit cases (`drops`, the app suite 437 now): Nemo's list with a
  space and an EUC-KR name, Dolphin's spoiled name read as given,
  Windows' paths, a comment and a web address, a URI naming its host and
  a last line with no end, a `%` with no hex after it, and the quoting
  for both shells (a quote and a dollar; a Korean name; a Windows path
  with a space).
- `harness/drop.py` (new): under Xvfb, Nemo and Dolphin (from nixpkgs)
  drag onto puritty's window, whose local tab runs a program that records
  the paste (`harness/drop/record-paste.py`), and each case pins what was
  pasted and what the window said. Six cases: one file; four items, a
  folder, a quote and a dollar, and Korean among them, from each file
  manager; an EUC-KR name in a UTF-8 tab (not pasted, said) and in an
  EUC-KR tab (its four bytes pasted as they are); and Dolphin's spoiled
  EUC-KR name, said and not pasted. Its first run pasted `???` for the
  last, the spoiled name's U+FFFD sent as EUC-KR's stand-in: that is why
  every path is checked and a name the set can't carry refused. Three
  runs gave the same pins.
- beelink1 (Windows 11), with Gilbert's drags onto the window: Explorer's
  `한.txt` pasted as `"C:\Users\yosup\OneDrive\Documents\한.txt" `;
  three files at once pasted plain, one after another; a file from inside
  a zip pasted nothing, and the note said why. The diagnostic log has
  each (`drop   1 paths pasted`, `drop   3 paths pasted`, the note).


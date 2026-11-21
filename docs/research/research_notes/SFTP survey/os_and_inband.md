# File transfer built into an OS or a terminal (not a file-manager client)

Survey notes, 2026-11-19. Each claim has its source. "Not verified" means no
source was found. Reddit could not be read from this sandbox (the search tool
refuses reddit.com), so user voices come from Hacker News, GitHub, Google
Groups, bug trackers and forums.

## Summary of the patterns

1. Two families. **Side-channel**: a second SSH connection or channel runs
   SFTP and shows it as a mount (ChromeOS, GVfs, KIO, SSHFS-Win). **In-band**:
   bytes travel inside the terminal stream (ZMODEM, trzsz, iTerm2 OSC 1337,
   kitty `transfer` and `dnd`).
2. Side-channel mounts are praised for convenience and blamed for slowness
   and hangs: a dead link freezes the file manager. Users who move bulk data
   switch to sshfs, scp or a dedicated client.
3. In-band transfer is loved for one reason: it works wherever the shell is,
   through jump hosts, `sudo su`, `docker exec`, serial lines, nested ssh.
   "It's so much easier than switching to a local terminal to use scp."
4. In-band transfer fails in tmux (ZMODEM), is slow (base64 or escaped
   bytes), and needs a helper on the remote host (`rz`, `trz`, kitty kitten).
5. trzsz exists only because rz/sz breaks in tmux, and tmux declined to fix it.
6. Drop-to-upload is a recurring request (Windows Terminal, PuTTY, Konsole,
   xterm.js, Royal TS). The hard part named every time: the terminal does not
   know the remote shell's current directory (PuTTY calls it "not feasible").
7. Products that ship drop-to-upload either ask the remote side to be ready
   first (Xshell: run `rz`, then drop) or open a dialog to pick the folder
   (tssh), or need a helper program running remotely (kitty `dnd`).
8. Security: an in-band protocol lets the remote host ask for local files.
   kitty prompts before every transfer; tssh warns that auto-upload dirs let
   "the server ... stealthily steal all files"; kitty's dnd protocol only
   releases data after a real drop.
9. Terminal maintainers mostly say no to ZMODEM (Alacritty, WezTerm,
   Windows Terminal "not a high priority"), while the Windows Terminal issue
   is one of the most up-voted (185 thumbs-up). Users point each other to
   trzsz/tssh as the workaround.
10. ChromeOS ties its mount to a terminal tab that must stay open; the mount
    is a separate SSH connection using the `sftp` subsystem.

## ChromeOS Terminal and Secure Shell (nassh)

### What it is

- Secure Shell's description: "A SFTP command line client is included. On
  ChromeOS, you can create SFTP mounts and access them from the Files app!"
  ([nassh messages.json, CWS_DESCRIPTION](https://chromium.googlesource.com/apps/libapps/+/HEAD/nassh/_locales/en/messages.json)).
- The connection dialog has three buttons: Connect, "SFTP Mount" and "SFTP"
  (same file, `MOUNT_BUTTON_LABEL`, `SFTP_CLIENT_BUTTON_LABEL`). "SFTP Mount"
  is ChromeOS only; "SFTP" opens a command-line client on every platform
  ([Mike Frysinger, chromium-hterm](https://groups.google.com/a/chromium.org/g/chromium-hterm/c/qr-vgpD5ZEA)).
- The mount uses Chrome's File System Provider (FSP) API, SFTP version 3,
  plus OpenSSH extensions (`posix-rename`, `fsync`, `hardlink`, `statvfs`,
  `copy-data`) ([nassh hack.md](https://chromium.googlesource.com/apps/libapps/+/HEAD/nassh/docs/hack.md)).
- The command-line client (`nasftp`) has `put`, `get`, `reput` (resume
  upload), `mget`, `mput`, and a progress bar
  ([nassh ChangeLog](https://chromium.googlesource.com/apps/libapps/+/HEAD/nassh/docs/ChangeLog.md),
  versions 0.26, 0.59, 0.60).

### How it is turned on

- In the built-in Terminal app, ChromeOS 109 added it behind
  `chrome://flags#terminal-sftp` ("still experimental") ([About Chromebooks, ChromeOS 109](https://www.aboutchromebooks.com/news/chromeos-109-release-adds-6-new-features-to-chromebooks)).
  You add an SSH connection with "+Add SSH", then pick "Mount to Files" from
  the three-dot menu beside it
  ([chromium-hterm thread](https://groups.google.com/a/chromium.org/g/chromium-hterm/c/iVkC68RDXSI)).
  Whether the flag is still required today: not verified.

### Does it share the SSH connection?

- No. A mount creates its own `CommandInstance` with `isSftp = true`, and
  that instance starts ssh with `argv.subsystem = 'sftp'`, so it is a new
  connection with no shell
  ([nassh_command_instance.js](https://chromium.googlesource.com/apps/libapps/+/HEAD/nassh/js/nassh_command_instance.js),
  `mountForegroundProfile`, line ~1215). It authenticates again.
- In the Terminal app the mount lives in a tab: "Keep this tab open. Closing
  this tab will remove the mount connection from Files."
  (`TERMINAL_HOME_MOUNTED_TAB_CLOSE_MESSAGE` in
  [messages.json](https://chromium.googlesource.com/apps/libapps/+/HEAD/nassh/_locales/en/messages.json)).
  Closing the tab unmounts (`beforeunload` handler in the same source file).
- Mounts are "non-persistent across logouts" (ChangeLog 0.8.41). Custom ssh
  commands are ignored for a mount (0.8.36.3), so ProxyCommand-style hops are
  limited; how far is not verified.

### Limitations and complaints

- Slow. A 37.6 MB file took 1:22 (0.46 MB/s) through the mount on a 90 ms
  link, slower than an HTTP download over an SSH tunnel. The maintainer: the
  team had not done performance testing; the Files app's FSP "doesn't always
  issue efficient requests"; reads are chunked at 32 KiB; "help wanted ;)"
  ([SFTP mount is slow](https://groups.google.com/a/chromium.org/g/chromium-hterm/c/jsf5lnBV5cA)).
- Fixed mount root. Users asked to mount a folder other than home; the answer
  was a bind mount on the server. Symlinks are filtered out
  ([SFTP Mount Point](https://groups.google.com/a/chromium.org/g/chromium-hterm/c/JKZaJT3Dskg)).
  A "Mount Path" field was added later (ChangeLog 0.8.36.4).
- Breakage. The extension's mount stopped working in v0.54 with no message
  ("SFTP Mount never works", "I don't even see a connection attempt"); the
  workaround was the built-in Terminal app: "Work around but would prefer the
  extension" ([v0.54 thread](https://groups.google.com/a/chromium.org/g/chromium-hterm/c/iVkC68RDXSI);
  tracked as [issuetracker 304150729](https://issuetracker.google.com/issues/304150729)).
- A 2026 guide says "SFTP mounting into the Files app is broken" in the
  Secure Shell extension since Manifest V3, while "Command-line SFTP still
  works fine" ([termai.sh](https://termai.sh/blog/ssh-client-chromebook)).
  One blog, not confirmed by Google.
- The old Secure Shell Chrome App is gone with Chrome Apps (ChromeOS 138,
  July 2025) (same source). The old app's mount used the same FSP code.

## GNOME Files (Nautilus) with GVfs `sftp://`

- Speed: sshfs, scp and sftp gave ~30 MB/s; Nautilus over gvfs ~10-14 MB/s.
  A maintainer: "gvfs-fuse is more or less considered as a fallback with no
  performance goals." Closed WONTFIX at end of life
  ([Red Hat bug 759659](https://bugzilla.redhat.com/show_bug.cgi?id=759659)).
  Similar older reports: [Launchpad 285462](https://bugs.launchpad.net/bugs/285462),
  [Launchpad 1497068](https://bugs.launchpad.net/ubuntu/+source/gvfs/+bug/1497068).
- Hangs: "sftp freezes nautilus after standby / resume cycle"
  ([Launchpad 1366840](https://bugs.launchpad.net/ubuntu/+source/gvfs/+bug/1366840)).
  In 2025: "While that mount is active Nautilus keeps a single worker thread
  busy talking to the remote machine"; "sshfs runs in its own process, so
  Nautilus never blocks" ([Ubuntu Discourse](https://discourse.ubuntu.com/t/nautilus-gets-confused-after-an-sftp-transfer-from-a-remote-hotspot/63197)).
  The same user dropped FileZilla because it "was less convenient than
  Nautilus" — convenience wins until it hangs.
- Thumbnails: requests not to thumbnail on slow file systems
  ([GNOME bug 619962](https://bugzilla.gnome.org/show_bug.cgi?id=619962),
  [Launchpad 350150](https://bugs.launchpad.net/bugs/350150)); and the
  opposite complaint, "Nautilus shows no thumbnails for remote locations"
  ([nautilus#2746](https://gitlab.gnome.org/GNOME/nautilus/-/issues/2746)).

## KDE Dolphin (KIO `sftp:/` and `fish:/`)

- `fish:/` runs over a shell, `sftp:/` over the SFTP subsystem. fish is
  called "a slow hack"; one user measured 500 KB/s with fish against 5 MB/s
  with scp ([Fedora KDE list](https://lists.fedoraproject.org/pipermail/kde/2012-March/011283.html),
  [KDE bug 339830](https://bugs.kde.org/show_bug.cgi?id=339830),
  [KDE bug 103661](https://bugs.kde.org/show_bug.cgi?id=103661)).
- sftp too: "sftp transfer speeds are atrociously slow, but on Filezilla
  super quick" ([KDE bug 491547](https://bugs.kde.org/show_bug.cgi?id=491547));
  a later comment ties it to the libssh version.
- Dolphin opened ~38 kio_sftp processes for one folder
  ([KDE bug 460141](https://bugs.kde.org/show_bug.cgi?id=460141)).
- Konsole wish from 2005: drag a file into a remote session and upload it
  with ZMODEM; "confirmed by popular vote"; maintainer in 2012: "If someone
  wants to provide the code, then we'll look at it", resolved LATER
  ([KDE bug 110524](https://bugs.kde.org/show_bug.cgi?id=110524)).

## macOS Finder

- No SFTP. "Connect to Server" lists FTP but not SFTP
  ([Apple Community](https://discussions.apple.com/thread/1780418)); Finder's
  FTP is read-only ([CloudMounter](https://cloudmounter.net/mount-sftp-mac/),
  vendor page).
- What people use: sshfs on macFUSE (closed source now, kernel extension,
  Homebrew dropped it) or FUSE-T; Mountain Duck (paid, now a subscription:
  [HN 46062313](https://news.ycombinator.com/item?id=46062313)); ExpanDrive;
  File Provider-based apps
  ([dev.to](https://dev.to/tommasomeli/free-sshfs-gui-for-macos-mount-remote-folders-in-finder-237a),
  [AppleInsider](https://appleinsider.com/inside/macos/tips/how-to-use-sftp-and-rsync-for-file-transfers-in-macos)).
  Mostly vendor sources; user sentiment not verified.

## Windows Explorer

- No SFTP. "It baffles me that Windows Explorer still doesn't know how to
  connect to an SFTP site out of the box" (kijin,
  [HN 41606916](https://news.ycombinator.com/item?id=41606916)).
- SSHFS-Win (WinFsp + Cygwin sshfs): "The fastest SSH mount on Windows I ever
  seen", but the same user stopped because of a bug (atmanactive, same
  thread). Issue: "Adding sshfs location makes Windows Explorer very very very
  slow (windows 11)" ([sshfs-win issues](https://www.github.com/winfsp/sshfs-win/issues)).
  Others suggest WSL sshfs or VS Code Remote; "Not everyone wants to install a
  huge resource just to use one feature" (same HN thread).
- WinSCP drag to Explorer: Windows does not tell the drag source where the
  drop landed, so WinSCP drags an empty dummy folder and uses a CopyHook shell
  extension to learn the target; it "misuses Windows File Explorer CopyHook's"
  ([WinSCP docs](https://winscp.net/eng/docs/dragext)). Failure: leftover
  empty `scpXXXXX` folders ([forum](https://winscp.net/forum/viewtopic.php?p=41595)),
  lost files in temp-folder mode ([forum](https://winscp.net/forum/viewtopic.php?p=42752)).
  Relevant to puritty only for drag *out* of the window.
- SFTP Drive, RaiDrive, ExpanDrive: exist; user feedback not verified.

## ZMODEM (lrzsz `rz` / `sz`)

### Where it is built in

- Xshell: run `rz`, then drop a file on the window, and "File transfer is
  carried out automatically"; an "Activate ZMODEM automatically" option skips
  prompts ([NetSarang docs](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/419957195)).
- SecureCRT: built in; uploads to BSD can "abort or hang" with CRC errors
  until `rz -e` ([somacon](https://www.somacon.com/p388.php)).
- WindTerm: drop chooses X/Y/ZMODEM (2.1 prerelease); bug "sz, rz always get
  stuck at 99%" (2.7 prerelease)
  ([WindTerm releases](https://www.github.com/kingToolbox/WindTerm/releases?page=2)).
- iTerm2: not built in; two triggers run helper scripts as a "silent
  coprocess"; README says use `-e` under tmux/screen
  ([iterm2-zmodem](https://github.com/Manho/iterm2-zmodem),
  [grack.com 2011](https://grack.com/blog/2011/10/26/automatic-file-transfer-in-iterm2-via-zmodem/)).
- GNU screen: `zmodem catch` in `.screenrc` (korben5,
  [HN 35703057](https://news.ycombinator.com/item?id=35703057)); "one of
  screen's advantages over tmux" (pmoriarty,
  [HN 12768719](https://news.ycombinator.com/item?id=12768719)).
- Tabby: has ZMODEM; an issue says it is not compatible with tmux and asks
  for trzsz ([tabby-trzsz](https://www.npmjs.org/package/tabby-trzsz)); the
  issue itself not read.

### Why people like it

- "It's still hard to match the convenience ... Since it runs over your
  current ssh connection it's perfectly secure. It's so much easier then
  switching to a local terminal to use scp" (stevefeinstein,
  [HN 12768719](https://news.ycombinator.com/item?id=12768719)).
- "Still would love if desktop terminal emulators would implement the zmodem
  receiver side, so that you can ssh into some host of your choice and just
  type "sz"" (poettering, [HN 35703057](https://news.ycombinator.com/item?id=35703057)).
- "Should work through multiple SSH hops, and not giving the hassle of using
  scp through those same sets of hops" (thomashabets2, same thread).
- Serial-only devices: "the only convenient way" (Grishnakh); "handy ... when
  nothing else works" (tonyarkles) ([HN 12768719](https://news.ycombinator.com/item?id=12768719)).
- Works where scp/sftp are disabled by the admin
  ([shuford archive](https://mi.rro.rs/lynx/pub/shuford/terminal/x-y-z-modem.news)).
- `sudo su` and `docker exec`: no source states it outright for ZMODEM;
  trzsz documents `docker exec` (below). Treat as inferred from "runs in the
  shell", not verified.

### Failures

- tmux: "Tmux does not support rz and sz", tmux declined (tmux issues 906,
  1439) ([trzsz README](https://github.com/trzsz/trzsz)).
- Corruption and stalls with escaping: SecureCRT on BSD, `rz -e` fix
  ([somacon](https://www.somacon.com/p388.php)); Xshell `sz` hang
  ([NetSarang](https://netsarang.atlassian.net/wiki/spaces/ENFA/pages/1314560386/Hang+up+when+use+sz+1));
  Devolutions RDM 2025.2 broke it
  ([forum](https://forum.devolutions.net/topics/50853/favicon.png)).
- Speed: "Slow as hell" over serial (revelation, HN 12768719); one personal
  account of ~600 Mbit/s over SSH
  ([cambus.net](https://www.cambus.net/fun-with-kermit-and-zmodem-over-ssh/)).
- Needs `rz`/`sz` on the remote host ("If the sz command does not exist in a
  remote host, users must install it", NetSarang docs above).

### Terminal maintainers on ZMODEM requests

- Windows Terminal [#1999](https://github.com/microsoft/terminal/issues/1999)
  "Plugin: add support for [XYZ]MODEM file transfers": 185 thumbs-up, 56
  comments (2026-11-19). DHowett locked it: not a high priority, "already
  handled better by other software". Users: the terminal is only the UI, and
  others (Xshell, iTerm2) do it. Duplicates: [#1602](https://github.com/microsoft/terminal/issues/1602)
  (35 up), [#2229](https://github.com/microsoft/terminal/issues/2229),
  [#9158](https://github.com/microsoft/terminal/issues/9158),
  [#19543](https://github.com/microsoft/terminal/issues/19543),
  [#19812](https://github.com/microsoft/terminal/issues/19812).
- Alacritty [#2586](https://github.com/alacritty/alacritty/issues/2586):
  "That's up to the rz/sz application, not Alacritty." A 2026 comment points
  to tssh.
- WezTerm [#5799](https://github.com/wezterm/wezterm/issues/5799): built-in
  X/Y/ZMODEM; closed "not planned".
- GNOME Terminal/VTE: ZMODEM upload request marked obsolete
  ([GNOME bug 79276](https://bugzilla.gnome.org/show_bug.cgi?id=79276)).
- Ghostty: no ZMODEM or transfer issue found (not verified either way).

## trzsz (`trz` / `tsz`) and tssh

- Why: "lrzsz ( rz / sz ) is convenient to use, but unfortunately it's not
  compatible with tmux" ([trzsz README](https://github.com/trzsz/trzsz)).
  The author's path was laptop, hosts, Docker, tmux.
- Features: directories (`-d`), resume, progress bar with "file name,
  progress, size, speed, remaining time", binary mode `-b` "faster for binary
  files"; `trz -b` may fail over telnet or `docker exec`, use `trz -eb`
  (same README). Supports tmux normal mode and iTerm2 `tmux -CC`.
- Clients: tssh, iTerm2 (trigger), Tabby plugin, Electerm, ttyd, trzsz-go
  wrapper, trzsz.js (same README).
- Drag and drop in tssh: `EnableDragFile yes` (or `--dragfile`);
  `DragFileUploadCommand trz -y` to overwrite; `DefaultUploadPath` for the
  file dialog; `AllowedAutoUploadDirs` skips the dialog, with the warning
  that "the server could stealthily steal all files under the configured
  directories without your confirmation" ([tssh docs](https://trzsz.github.io/tssh)).
  When files are dropped, the upload command is run in the remote shell,
  so the files land in the shell's current directory (inferred from the
  config; the docs do not say it in words — not verified).
- Windows: cmd and PowerShell accept only one dragged file; a window titled
  "Administrator" blocks drag and drop; on Windows Terminal drop on the
  "Paste path to file" area ([trzsz-go docs](https://trzsz.github.io/go)).
- Users recommend it as the answer in Windows Terminal #1999, Alacritty
  #2586 and Tabby issues (links above). No independent user reviews found;
  HN posts about tssh have 0-1 comments
  ([HN 46674252](https://news.ycombinator.com/item?id=46674252)).

## iTerm2 OSC 1337 `File=` (`it2dl`, `it2ul`)

- `it2dl file` downloads over SSH. Since 3.7 iTerm2 asks whether to save to
  Downloads or show a save panel ([iTerm2 utilities](https://iterm2.com/documentation-utilities.html)).
- `it2ul [dest]`: you are "prompted to select one or more files"; iTerm2
  tars, gzips and base64-encodes them, and the remote script extracts them
  (same page).
- tmux behavior: not documented on that page (not verified).
- User feedback: none found.

## kitty `transfer` kitten and `dnd`

- `transfer` moves files "over the TTY device itself", so it works "over
  nested SSH sessions, serial links, etc."; directories, links, permissions
  and timestamps kept; optional rsync deltas ("will actually degrade
  performance on fast links or with small files") and auto compression
  ([kitty transfer docs](https://sw.kovidgoyal.net/kitty/kittens/transfer/)).
- Security: kitty asks for confirmation before each transfer so the protocol
  cannot be "abused to read/write files on your computer". A bypass password
  in `kitty.conf` skips it, with the warning that any remote software that
  learns it gets full access (same page).
- Drag and drop: in 2023 Kovid declined a drag-and-drop kitten: "drag/drop
  is not a superior interface for this" ([kitty #6906](https://github.com/kovidgoyal/kitty/issues/6906)).
  In 2026 he shipped `kitten dnd` and an OSC 72 drag-and-drop protocol
  (0.47.0, marked stable June 2026). Run `kitten dnd` on the remote host and
  drops land in its current directory (`--drop-dest` changes it)
  ([kitty #9984](https://github.com/kovidgoyal/kitty/issues/9984),
  [dnd kitten](https://sw.kovidgoyal.net/kitty/kittens/dnd/)).
- dnd protocol: the program must register for drops; data can be requested
  "only after a drop has actually occurred"; file data goes base64 in escape
  codes; a hashed machine id tells the terminal the program is remote; drags
  from the same window are refused with EPERM; request limits against denial
  of service. No confirmation prompt: the drop gesture is the consent
  ([dnd protocol](https://sw.kovidgoyal.net/kitty/dnd-protocol/)).
- Testing found macOS gaps over SSH (Finder as target needs all data before
  the drag starts) ([kitty #9984](https://github.com/kovidgoyal/kitty/issues/9984)).

## WezTerm, Ghostty, Windows Terminal, Alacritty: drop behavior today

- Common default: a dropped file pastes its path. Windows Terminal shows
  "Paste path to file" ([trzsz-go docs](https://trzsz.github.io/go)). WezTerm
  added X11 file drops ([changelog](https://wezterm.org/changelog.html)).
  Behavior per terminal beyond these: not verified individually.
- WezTerm: request to adopt kitty's dnd protocol, 13 thumbs-up
  ([#7908](https://github.com/wezterm/wezterm/issues/7908)).
- Ghostty: a PR for "image upload on drag and drop" was closed
  ([#9699](https://github.com/ghostty-org/ghostty/pull/9699)); a merged PR
  added SSH image paste on macOS
  ([#10515](https://github.com/ghostty-org/ghostty/pull/10515)). Both are
  about images for CLI tools, not general file upload (titles only read).
- Windows Terminal: "SSH Drag-and-Drop File Transfer" idea, zero replies:
  "PuTTY and similar clients have this feature, and I really liked it";
  proposes a wrapper that reads `SSH_*` variables and runs scp
  ([discussion #17029](https://www.github.com/microsoft/terminal/discussions/17029)).
  (PuTTY does not have it; the poster likely means MobaXterm or Xshell.)
- PuTTY wishlist "drag-drop-to-cwd": low priority, difficulty "mayhem";
  there is no reliable way to know the remote shell's current directory;
  prompt parsing is unreliable and a custom escape sequence is risky; "just
  not feasible" ([PuTTY wish](https://putty.cs.utah.edu/wishlist/drag-drop-to-cwd.html)).
  A separate wish asks for upload over a spare SFTP channel on drop
  ([PuTTY wish drag-drop](https://ftp.cvut.cz/putty/wishlist/drag-drop.html)).
- xterm.js: "I would be very interested in drag and dropping files into the
  terminal. I suppose it could be done via SFTP." Maintainer: "pretty
  involved" ([discussion #4958](https://github.com/xtermjs/xterm.js/discussions/4958)).
- Tabby: drag a folder onto the SFTP panel did not upload it; asks for
  folder upload/download; closed as done in 2025
  ([tabby #4946](https://www.github.com/Eugeny/tabby/issues/4946)).

## Folder that follows the shell (related request)

- MobaXterm's "Follow terminal folder" makes the SFTP side panel track `cd`;
  labeled experimental; breaks with Byobu output and after multiple SSH hops
  ([portablefreeware forum](https://portablefreeware.com/forums/viewtopic.php?p=64049),
  [Stack Overflow 41830936](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/41830936/mobaxterm-follow-terminal-folder-stfp-and-byobu),
  [Super User 1804247](https://apis.emri.workers.dev/https-superuser.com/questions/1804247/mobaxterm-file-browser-not-following-terminal-after-multiple-ssh-hops)).
- Royal TS users ask for the same: "+1 for this idea!", and for SFTP "inside
  the terminal connection, instead of having to create a separate SFTP
  window" ([Royal Apps community](https://community.royalapps.com/t/sftp-to-follow-ssh-current-directory/453)).
- Xshell users ask Xftp to open at the shell's present working directory
  ([NetSarang](https://netsarang.atlassian.net/wiki/spaces/ENFA/pages/1315280012/XFTP+from+XSHELL+present+working+Directory+4)).

## Common opinions vs one-off anecdotes

Common (several independent sources):
- Built-in SFTP mounts are convenient but slower than scp/sftp/sshfs, often
  2-4x (GVfs, KIO, ChromeOS).
- A dropped or slow link freezes the file manager (GVfs, SSHFS-Win/Explorer).
- rz/sz does not work in tmux; trzsz is the usual fix.
- In-band transfer is valued because it needs no second login and follows
  the shell through hops and serial lines.
- Users want an upload by drop, and want the remote side to follow the
  shell's current folder.

One-off or thin:
- ChromeOS Files mount broken since MV3 (one blog).
- 600 Mbit/s ZMODEM (one blog).
- SSHFS-Win "fastest" (one HN user).
- Kitty dnd over SSH macOS gaps (one tester).

Recurring requests:
- ZMODEM / in-band transfer in modern terminals (Windows Terminal 185 up).
- Drop a file to upload to the remote current directory.
- SFTP view that follows `cd`.
- Folder upload, not only files (Tabby).
- Choose the mount's root folder (ChromeOS).

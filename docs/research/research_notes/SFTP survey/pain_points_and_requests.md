# SFTP beside an SSH session: pain points, praise and requests

Cross-cutting survey, by theme, of what users write about file transfer
alongside an SSH terminal. Gathered 2026-11-19.

## Summary

1. The most praised thing is the MobaXterm pattern: a file pane next to the shell that follows `cd`, with drag and drop both ways. HN users call it a time saver ("saved me many hours").
2. The most common pain is logging in twice. GUI clients open a second SSH connection for SFTP, so 2FA (Duo, push) fires again. University HPC sites document this widely. Reusing the shell's own connection removes it.
3. The second most common pain is root-owned files. SFTP runs as the login user. The only real fix is `sudo /usr/lib/openssh/sftp-server` with NOPASSWD. WinSCP's request for a sudo password prompt has been open since 2014.
4. "Follow terminal folder" is loved but fragile. It breaks after `su`/`sudo su`, under tmux/byobu, through nested ssh hops, and with noisy shell startup files. MobaXterm marks it "experimental".
5. Edit-in-local-editor with upload on save is valued. Its failures are silent: saves not detected, the editor saving to an older temp copy, and line endings changed by text mode.
6. Overwrite prompts: users want a sticky default and "newer only". FileZilla's "apply to all" choices do not persist and "only if newer" is reported unreliable.
7. Speed: SFTP is RTT-bound and slow on many small files. tar over ssh and rsync beat it. HN discussion is detailed on why.
8. Drag out to Windows Explorer is hard. WinSCP needs a shell extension (CopyHook hack); without it, files go through a temp folder, can be lost, and block background transfer.
9. Drag a file into the terminal to upload it is a recurring request (Windows Terminal, xterm.js, PuTTY wishlist, Tabby). PuTTY says the remote cwd problem makes it "Mayhem". OSC 7 is the modern answer.
10. Reddit was not reachable from this sandbox (search and fetch both blocked), and Stack Exchange pages could not be fetched. Those are cited through search snippets or mirrors and marked as such.

## Source limits

- reddit.com is blocked for both WebSearch and WebFetch here. No Reddit quotes are included.
- superuser.com, unix.stackexchange.com and stackoverflow.com could not be fetched. Where cited, the claim comes from a search summary or a kiwix mirror URL, and is marked "(via search summary)".
- news.ycombinator.com rate-limited after a few fetches.

## 1. Writing root-owned files (sudo)

**What users hit.** The SFTP session runs as the login user, so uploads to `/etc` fail. A Unix & Linux SE question asks how to use MobaXterm's SFTP with root files; the answer says there is no simple way (via search summary) — https://unix.stackexchange.com/questions/472802/how-to-use-mobaxterm-ssh-sftp-client-with-root-files

**The standard trick.** Point the client's "SFTP server" setting at `sudo /usr/lib/openssh/sftp-server` and add a NOPASSWD sudoers rule for that binary.
- WinSCP FAQ: set the SFTP server option to `sudo /bin/sftp-server`; it only works "if you are allowed to do sudo su without being prompted with password", and requires `requiretty` off. It says WinSCP "cannot implement terminal emulation." — https://winscp.net/eng/docs/faq_su
- Same recipe in a gist and on KernelTalks, using `sudo su -c /usr/lib/openssh/sftp-server` — https://gist.github.com/rwese/8e59d17e5e26f9b3738f9955af9b6349 , https://kerneltalks.com/tools/how-to-use-sudo-access-in-winscp/
- Users report "Cannot initialize SFTP protocol" after setting it up — https://winscp.net/forum/viewtopic.php?p=41166
- Password via stdin fails with "no tty present and no askpass program specified"; a WinSCP reply says TTY is incompatible with SFTP — https://winscp.net/forum/viewtopic.php?p=29901

**How people feel.** Uneasy.
- A WinSCP user: they "would then be able to use WinSCP to accidentally do all sorts of things such as deleting critical files" — https://winscp.net/forum/viewtopic.php?p=19940
- A Server Fault question calls a broad sudoers rule "too benevolent" (via search summary) — https://kiwix.lema.org/serverfault.com_en_all_2023-11/questions/399536/how-to-use-sudo-with-winscp-and-proftpd
- A RetroPie user found the file is recreated root-owned, which changes ownership — https://retropie.org.uk/forum/post/11980

**Requests.**
- WinSCP issue 1247 "Allow providing a password to sudo", open since 2014-11-21. The 2024 note sketches `SUDO_ASKPASS=./mypass sudo /bin/sftp-server` and calls it "a huge hack and bypass of alls the sudo security features." — https://winscp.net/tracker/1247
- A MobaXterm Pro reviewer: "The SFTP pane should elevate to root when I "sudo su"". Mobatek told him to use SCP mode, and later "there's a quick button in the SFTP pane to sudo su." — https://b3n.org/mobaxterm-professional-review/
- Devolutions RDM users asked for a "sudo on login" option for SFTP — https://forum.devolutions.net/topics/32992/sftp-sudo-on-login-for-winscp-add-server-command--protocol-option-like
- VS Code Remote SSH has the same gap; users rely on the "Save as Root in Remote - SSH" extension — https://ademking.github.io/posts/ssh-vscode-save-as-root

**Workarounds people actually use.** Upload to home, then `sudo mv` — https://www.linuxquestions.org/questions/linux-newbie-8/gaining-root-access-on-bitvise-client-4175557484/ . Or a shell-based mode (WinSCP SCP with shell `sudo -s`, MobaXterm "SCP" browser) — https://winscp.net/eng/docs/faq_su , https://forum.hestiacp.com/t/winscp-permission-denied/13124

**How widespread.** Very. Many forum threads across WinSCP, MobaXterm, Bitvise, Cyberduck, FileZilla and VS Code. It is the most-asked "how do I" in this area.

**Best-liked solution.** `sudo sftp-server` with a NOPASSWD rule narrowed to that one binary. Second: a sudo button that asks for the password interactively (MobaXterm). An SSH client that owns the session can run `sudo -S sftp-server` on its own exec channel and feed the password itself, which is what issue 1247 asks for.

## 2. Logging in twice (second connection, 2FA, jump hosts)

**What users hit.** The file pane opens a second SSH connection and the second factor fires again.
- Alliance Canada docs: "MobaXterm establishes two connections by default: the first for the terminal ...", "which causes a mandatory second prompt for your second factor". Also: "each time you navigate to a different folder on the left pane, another transaction requiring MFA is started", and "1 or 2 hidden MFA-Duo windows (behind other windows)". — https://ualberta-rcg.github.io/ragflow-wiki-data/en/getting-started/multifactor_authentication/ (mirror of https://docs.alliancecan.ca/wiki/MFA)
- Same page: "FileZilla will ask the password and second factor each time a transfer is initiated"; "By default, Cyberduck opens a new connection for every file transfer, prompting you for your second factor each time." — same URL
- Hawaii, NeSI and Kennesaw HPC docs tell users to turn off MobaXterm's SFTP sidebar or switch its type — https://uhawaii.atlassian.net/wiki/x/MwArKw , https://docs.nesi.org.nz/General/FAQs/Why_cant_I_log_in_using_MobaXTerm , https://hpcdocs.kennesaw.edu/getting_started/connecting_with_duo
- The SCP workaround has its own bug: switching to "SCP (enhanced speed)" "causes transfers to hang indefinitely" (via search summary of the Alliance page).
- Cyberduck 8.4.4 regression: after Duo approval "it calls Duo again"; "We don't have this issue with command line sftp" — https://groups.google.com/g/cyberduck/c/vUVevnLwRk8

**ControlMaster.** OpenSSH users fix it with multiplexing: "subsequent SSH connections on the same device will reuse the connection of the first session", but it "doesn't work with native Windows" — Alliance page above; also https://nsc.liu.se/support/2fa/power-user/ . Zed forces `-o ControlMaster=yes` for its file browser, so it may not reuse the user's master — https://github.com/zed-industries/zed/issues/45271

**Agents and jump hosts.**
- A Royal TS user: "anything else like SFTP wouldn't even try to use the ssh agent so I couldn't authenticate." — https://b3n.org/mobaxterm-professional-review/ (comment)
- Cyberduck: ProxyJump "always fails to connect ... the conf in itself is correct since it works from the terminal" — https://lists.cyberduck.io/pipermail/cyberduck-trac/2021-January/045273.html
- WinSCP does not read ProxyJump; its author says multi-hop needs a local proxy and plink — https://winscp.net/forum/viewtopic.php?p=112856
- iTerm2's drag-drop scp uses libssh2 and reads only Host, HostName, User, Port, IdentityFile from ssh_config, so jump hosts and agents like 1Password fail — https://groups.google.com/g/iterm2-discuss/c/bE5b3Q8Rt2A , https://iterm2.com/documentation-utilities.html
- SecureCRT's answer is an "SFTP tab" opened from the live SSH2 session — https://vandyke.com/support/tips/sftptab.html

**How widespread.** Very, in academic/HPC and corporate (Duo, Okta ASA, Safeguard) settings. Dozens of institutional help pages exist only to work around it.

**Best-liked solution.** One authenticated connection, with SFTP as another channel on it. OpenSSH ControlMaster on Linux/macOS; nothing comparable is built into Windows OpenSSH. A terminal with its own SSH client can do this by design, and that is likely the strongest selling point here.

## 3. File browser following the shell's directory

**Praise.**
- HN, kyriakos: "Integration with sftp browser and follow terminal path saved me many hours." and "Drag and drop a file from/to local to/from current terminal directory is an amazing shortcut." — https://news.ycombinator.com/item?id=29007855 (thread https://news.ycombinator.com/item?id=29001665)
- MobaXterm Pro reviewer: "I always want the SFTP directory to follow the directory in the terminal" — https://b3n.org/mobaxterm-professional-review/
- Requests in other products: Royal TS, 2017: "Would be great to have a checkbox in the SFTP window to "follow" the position of the SSH connection", with "+1" and a request for two-way sync (filer sends `cd` to the terminal) — https://community.royalapps.com/t/sftp-to-follow-ssh-current-directory/453 . WindTerm users asked for it (#331, #2091) and it shipped as "Sync Terminal Folder", with the caveat that not all systems support it — https://github.com/kingToolbox/WindTerm/discussions/2091

**Failures.**
- After `su`/`sudo su`: an answer says switching user is the most probable trigger and suggests typing `cd .`; the feature is "experimental" (via search summary) — https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/72193255/mobaxterm-follow-terminal-folder-doesn-t-work
- Under byobu/tmux: following stopped once byobu was installed; redirecting its output fixed it (via search summary) — https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/41830936/mobaxterm-follow-terminal-folder-stfp-and-byobu
- After multiple ssh hops (Super User 1804247, title only; page not fetchable) — https://superuser.com/questions/1804247/mobaxterm-file-browser-not-following-terminal-after-multiple-ssh-hops
- An `echo` in `.bashrc` broke it (via search summary, same SO thread as above).
- PuTTY's view: a terminal cannot reliably know the remote cwd; prompt parsing fails, and an escape sequence has "many failure modes, including subshells ... and security risks" — https://putty.cs.utah.edu/wishlist/drag-drop-to-cwd.html
- SecureCRT: "SecureCRT doesn't know what directory you are currently in on the remote side", so its tip has the shell emit an escape sequence — https://vandyke.com/support/tips/sftptab.html

**OSC 7.** The modern mechanism. Over SSH it is "the only way" to learn a remote shell's cwd; inside tmux it needs `allow-passthrough on`; it carries no username, so after `sudo su` the path is right but the user is not — https://wezterm.org/shell-integration.html , https://docs.rs/crate/ezpn/0.12.0/source/docs/shell-integration.md , https://ghostty.org/docs/vt/osc/7

**How widespread.** Praise is common (it is MobaXterm's signature feature). Failure reports are a handful of threads each, but cover the same three cases: user switch, multiplexer, nested ssh.

**Best-liked solution.** Automatic following, with a manual "go to terminal folder" fallback. MobaXterm does it by hooking the shell; WindTerm offers manual, auto and reverse sync. For puritty, OSC 7 plus a "sync now" command fits, and the host field of OSC 7 tells you when the shell is no longer on the tab's host (nested ssh).

## 4. Edit remotely in a local editor, upload on save

**Praise.** "SFTP can also be used to round trip edit files with the integrated and external editors like Notepad++." — https://blog.nashcom.de/nashcomblog.nsf/dx/my-favorite-ssh-client-on-windows-mobaxterm.htm . WinSCP documents it as a core task: the file is downloaded to temp and uploaded when changed — https://winscp.net/eng/docs/task_edit

**Failures (all silent).**
- Saves not detected: "wait a minute, resave the file, and it will get uploaded" — https://winscp.net/forum/viewtopic.php?p=106723
- Tabbed editors keep an older temp copy: "the updates stayed in the original local temp folder, while WinSCP picked up the file from a new one" — https://winscp.net/forum/viewtopic.php?p=57877 , https://winscp.net/forum/viewtopic.php?p=113959
- Two sessions sharing one deterministic temp path — https://winscp.net/forum/viewtopic.php?p=129287
- Temp copy deleted too early, "you can not update it anymore" — https://winscp.net/forum/viewtopic.php?p=21015
- Same problem in Devolutions RDM: "Edit files over SCP not uploading after edit" — https://forum.devolutions.net/topics/40461/edit-files-over-scp-not-uploading-after-edit
- Line endings: WinSCP's internal editor and text mode convert CRLF/LF; users switch to binary — https://winscp.net/eng/docs/faq_line_breaks , https://winscp.net/forum/viewtopic.php?p=129983 , https://winscp.net/forum/viewtopic.php?p=32593
- WindTerm: "The files downloaded from linux to windows are inconsisten" — https://github.com/kingToolbox/WindTerm/discussions/2091

**How widespread.** Many WinSCP threads over 15 years; fewer elsewhere because fewer tools do it. VS Code Remote SSH is the competitor most developers now use for this (and it has the sudo gap from theme 1).

**Best-liked solution.** Byte-exact (binary) transfer, a visible "uploaded at hh:mm" or error per save, and refusing to overwrite if the remote changed since download.

## 5. Overwrite and conflict prompts

- FileZilla: dialog choices "apply to current queue only" and do not persist across sessions — https://trac.filezilla-project.org/ticket/5560
- FileZilla: "overwrite if source is newer" not remembered, and the newer check unreliable — https://trac.filezilla-project.org/ticket/11263 ; uploads everything despite "newer" with equal size and time — https://forums.opensuse.org/t/filezilla-uploads-all-files-despite-being-told-otherwise/122248
- FileZilla: user accidentally chose "overwrite all" and it kept applying to a restarting queue — https://trac.filezilla-project.org/ticket/13197
- Devolutions: "SFTP Do Same for All Existing Overwrite/Skip Fails to Do Same" — https://forum.devolutions.net/topics/51301/sftp-do-same-for-all-existing-overwriteskip-fails-to-do-same
- WinSCP's dialog offers "Newer only" (SFTP only) and resume — https://winscp.net/eng/docs/ui_overwrite

**How widespread.** Moderate. Steady trickle of tracker tickets; nobody praises any prompt.

**Best-liked solution.** A default action set once (FileZilla "File exists action", WinSCP prefs), plus "newer only" that is actually correct, plus a summary of what was skipped.

## 6. Queues, progress, resume, speed

- SFTP is RTT-bound. HN nickcw: it "packetizes the data and waits for responses, effectively re-implementing the TCP window inside a TCP stream", and "If you have 100 ms of latency then you can send at most 20 MB/s". HPN-SSH author rapier1: "The bottleneck in SSH is entirely on the receiving side." — https://news.ycombinator.com/item?id=46227641
- Many small files: Warwick benchmark found sshfs, sftp and scp "terrible at transferring a large number of small files"; tar over ssh fastest, rsync second — https://ejbrambley.warwick.ac.uk/sshspeedtest.html . HN jcranmer: "tar c | ssh tar x can actually be far faster than scp -r, especially when you have a lot of small files." — https://news.ycombinator.com/item?id=25005567
- One user: 16 GB of small files took "over 14 hours" by SFTP vs 6m51s by tar over ssh (via search summary) — https://jmmv.dev/2021/02/seeding-a-file-server.html
- WinSCP's "Optimize connection buffer size" is a common cause of slowness; one user went from 4 hours to 5 minutes by turning it off — https://winscp.net/forum/viewtopic.php?p=81801 ; FileZilla faster than WinSCP for long files — https://winscp.net/forum/viewtopic.php?p=116249
- Termius: "slow and inefficient" SFTP while SSH is fine — https://ca.trustpilot.com/review/termius.com ; MobaXterm SFTP panel "sometimes struggles to upload large files" — https://capterra.com/p/209929/MobaXTerm/reviews/
- Resume: WinSCP leaves `.filepart` and auto-reconnects and resumes (Endurance settings) — https://winscp.net/eng/docs/resume . OpenSSH `reput`/`reget` exist. SSH.NET users ask for them — https://www.github.com/sshnet/SSH.NET/issues/1391
- Folders: Tabby's "Drag-dropping a folder to SFTP does not create the folder" got 27 thumbs-up, lived 2021-2025 — https://www.github.com/Eugeny/tabby/issues/4946 . Users there also asked for multi-select transfers and whole-folder download.

**How widespread.** Speed complaints are very common; folder-upload gaps are common in newer terminal-with-SFTP products.

**Best-liked solution.** Many outstanding requests in flight (pipelining), several files in parallel, upload to a temp name then rename, auto-reconnect with resume, and folder upload as a first-class case.

## 7. Permissions, ownership, timestamps, symlinks, dotfiles

- Uploads get 0644 minus the remote umask unless the client sets mode; OpenSSH `-p` sends a setstat after writing — https://access.redhat.com/node/3291161 , https://www.supportsages.com/blog/linux-setting-umask-for-sftp
- WinSCP: with "Set permissions" off, new files get defaults and overwritten files usually keep theirs; preserving timestamps or mode can fail after a good upload, so it offers "Ignore permission errors" — https://winscp.net/eng/docs/ui_transfer , https://winscp.net/eng/docs/message_preserve_time_perm
- Uploading as sudo recreates the file root-owned (theme 1) — https://retropie.org.uk/forum/post/11980
- Symlinks: a WinSCP user found a symlinked local file >=100 KB "will get converted to a hard file" and on Linux the target deleted; uploads to a symlink disable the feature that causes it — https://winscp.net/forum/viewtopic.php?p=116628 . Sync does not follow folder symlinks — https://winscp.net/forum/viewtopic.php?p=68544
- Hidden dotfiles: users cannot find `.htaccess`; WinSCP hides dotfiles client-side by default — https://winscp.net/forum/viewtopic.php?p=90932 , https://winscp.net/forum/viewtopic.php?p=40266 ; FileZilla needs "Force showing hidden files" — https://kinsta.com/blog/filezilla-show-hidden-files/
- Termius users miss permission editing and mass changes — https://ca.trustpilot.com/review/termius.com

**How widespread.** Dotfile confusion is very common among web-hosting users. Ownership/umask issues are steady. Symlink damage is rare but severe.

**Best-liked solution.** Overwrite in place (keeps owner and mode) rather than delete-and-create; keep the remote mode on overwrite; show dotfiles by default for a sysadmin audience, or one keystroke to toggle.

## 8. Drag and drop

**Into the terminal (upload by dropping on the window).**
- Windows Terminal discussion #17029: "PuTTY and similar clients have this feature, and I really liked it." No replies — https://www.github.com/microsoft/terminal/discussions/17029 . A maintainer pointed SSH features at the extension model — https://www.github.com/microsoft/terminal/issues/11034
- xterm.js: "I would be very interested in drag and dropping files into the terminal. I suppose it could be done via SFTP." Maintainer: "currently pretty involved" — https://github.com/xtermjs/xterm.js/discussions/4958
- PuTTY wishlist: "Drag and drop support (the hard version)", difficulty "mayhem", because "there's no reliable way for PuTTY to determine what the currect directory of the remote shell is" — https://putty.cs.utah.edu/wishlist/drag-drop-to-cwd.html
- iTerm2 does it: "dropping a file on an iTerm2 window during an ssh session and it can scp it over for you" — https://news.ycombinator.com/item?id=33836308 . HN on MobaXterm: "having the ability to just drop files over to be scp'ed" — https://news.ycombinator.com/item?id=29001665
- In-band alternatives: trzsz `--dragfile` and kitty's transfer kitten work over the TTY, so they survive nested ssh and serial links, but need a helper on the remote — https://trzsz.github.io/go , https://sw.kovidgoyal.net/kitty/kittens/transfer/
- Zmodem drop-to-upload exists in ZOC, SecureCRT, Konsole, Tabby — https://news.ycombinator.com/item?id=33836308

**Out of the browser to Explorer.** Windows wants the file before the drop finishes.
- WinSCP without its extension "uses a trick ... It tells Windows File Explorer that the files are in temporary folder", then copies; files "need to be downloaded to temporary directory first", and background transfer is not possible — https://winscp.net/eng/docs/ui_pref_dragdrop
- With the extension: WinSCP creates a dummy folder and the extension's CopyHook reports the real target. Costs: only Explorer works as a target; the extension stays loaded at boot; not available for portable or Store installs; broken on Windows 10 1803 — https://winscp.net/eng/docs/dragext
- Lost files when the user changes folder mid-copy: "There's nothing we can do about it. You should be using WinSCP drag&drop shell extension." — https://winscp.net/forum/viewtopic.php?p=42752 ; stray empty `scpNNNNN` folders — https://winscp.net/forum/viewtopic.php?p=69275 , https://winscp.net/forum/viewtopic.php?p=41400
- XYplorer users find the extension does not work with their file manager — https://www.xyplorer.com/xyfc/viewtopic.php?p=75955
- The documented alternative is virtual files (CFSTR_FILEDESCRIPTOR + CFSTR_FILECONTENTS, IStream), from Raymond Chen's "What a drag" series — https://devblogs.microsoft.com/oldnewthing/20080318-00/?p=23083
- Other products: Termius users say drag and drop with the OS "isn't possible" — https://ca.trustpilot.com/review/termius.com ; Devolutions "Why no drag and drop copying from remote to local?" — https://forum.devolutions.net/topics/39025/why-no-drag-and-drop-copying-from-remote-to-local ; MobaXterm drag-and-drop failing to OpenWrt — https://forum.openwrt.org/t/mobaxterm-file-drag-n-drop-fails/141178

**How widespread.** Drop-to-upload is requested in many projects. Drag-out complaints are concentrated in WinSCP's forum (because WinSCP is the one that tries hard).

**Best-liked solution.** Drop on the window uploads to the shell's folder (needs theme 3). Drag-out: WinSCP's extension is the most reliable but is disliked as a system hook; virtual-file IStream drag-out is the non-invasive path.

## 9. Security policy, chroot, and the scp change

- OpenSSH 9.0 made `scp` use SFTP; `-O` restores the old protocol; no bug-compatibility for remote-shell globbing; `~user` needs the server's `expand-path@openssh.com` (8.7+) — https://www.openssh.com/txt/release-9.0
- Users on Dropbear/OpenWrt hit `sftp-server: not found` and must use `scp -O` — https://forum.openwrt.org/t/ash-usr-libexec-sftp-server-not-found-when-using-scp/125772/3.md
- HN: the SFTP subsystem "may be disabled on the server side (not that uncommon)" (3np); "disabling the sftp subsystem yet granting people shell access is backwards" (tinus_hn); "Many SSH servers do not run OpenSSH" (sanxiyn) — https://news.ycombinator.com/item?id=25005567
- Appliances with restricted shells (pfSense admin menu, F5, Data Domain `ddsh`) break SFTP or WinSCP's shell modes — https://forum.netgate.com/post/684108 , https://www.dell.com/support/kbdoc/en-au/000202391/data-domain-winscp-not-work-with-data-domain-or-ddmc?lang=en
- A big MOTD or login output breaks SFTP — https://forum.netgate.com/post/679765 (same root cause as byobu breaking MobaXterm following).

**How widespread.** The scp change caused a burst of breakage reports in 2022 and then quieted. Disabled SFTP is uncommon but real on appliances and locked-down hosts.

**Best-liked solution.** Fall back to a shell-based transfer (scp legacy, or `cat`/`base64` over an exec channel) when the SFTP subsystem is refused, and say why in the error.

## 10. Keyboard-driven users

- scp is loved for its short syntax: "the syntax is quick and easy" (alias_neo); "close enough to what I need 95% of the time" (stjohnswarts) — https://news.ycombinator.com/item?id=25005567
- rsync is preferred for resume and deltas but its trailing slash bites people ("treats trailing slashes as significant") — same thread
- lftp is the keyboard user's SFTP: tab completion of remote paths, job control, `mirror` — https://lists.freebsd.org/pipermail/freebsd-questions/2007-June/152107.html . OpenSSH's own sftp completion was still being fixed in 2022 — https://lists.mindrot.org/pipermail/openssh-unix-dev/2022-September/040393.html
- WinSCP's Commander interface "is primarily designed to be controlled using keyboard", Norton-style F5 — https://winscp.net/eng/docs/ui_commander_key ; some users find F5 = download jarring — https://winscp.net/forum/viewtopic.php?p=53502
- Termius users miss keyboard shortcuts for delete and permissions — https://ca.trustpilot.com/review/termius.com
- HN, on drag from terminal: "Or better yet, a full keyboard workflow." — https://news.ycombinator.com/item?id=33836308
- PuTTY's wishlist notes sftp's lack of `~` expansion — https://putty.cs.utah.edu/wishlist/sftp-tilde.html

**How widespread.** Common among the HN/sysadmin audience; they mostly use CLI tools and ask GUIs only to not get in the way.

**Best-liked solution.** A command typed in the session (or a palette) that does `put`/`get` relative to the shell's cwd with remote tab completion, so the file pane is optional.

## 11. Why people stay with or leave a tool

**Stay with MobaXterm.**
- "Without a doubt, Moba is what SSH on windows has been missing." (krossitalk); "saved me tons of time every day when I worked as sysadmin" (NikolaNovak) — https://news.ycombinator.com/item?id=29001665
- A DEV guide calls the integrated SFTP browser MobaXterm's "killer feature" — https://dev.to/daxesh/putty-alternatives-for-windows-the-2026-guide-for-developers-whove-outgrown-classic-ssh-b7g
- A blogger says MobaXterm "replaced WinSCP which I used in earlier days along with Putty" — https://blog.nashcom.de/nashcomblog.nsf/dx/my-favorite-ssh-client-on-windows-mobaxterm.htm

**Leave MobaXterm.** "MobaXterm feels slower" (jcrawfordor); moved to Linux (franga2000), who also lists "fixing all the drag&drop bugs" as a wish; WSL plus Windows Terminal "choking off demand" (tyingq) — https://news.ycombinator.com/item?id=29001665

**Keep a separate SFTP tool.** A Termius user still uses FileZilla for SFTP; a LowEndTalk user "hates the SFTP features of Termius but has no better option" on macOS/Linux (via search summary) — https://ca.trustpilot.com/review/termius.com , https://lowendtalk.com/discussion/comment/3453844/

**How widespread.** The "integrated SFTP is why I use MobaXterm" sentiment appears in nearly every MobaXterm review or thread found. Termius and Tabby get "SFTP is the weak part" reviews.

## Implications worth carrying to the design (not research findings)

- Open SFTP as a channel on the tab's existing connection. That removes theme 2 entirely for puritty's built-in client, including through jump hosts the tab already traversed.
- Offer "as root" by starting `sudo -S <sftp-server path>` on an exec channel and supplying the password from a puritty prompt. That is the feature WinSCP has had open since 2014.
- Use OSC 7 for the current folder, show which host and path it came from, and fall back to the dialog when OSC 7 is missing, stale, or names another host.
- Transfer bytes exactly; never convert line endings.
- On Windows, drag-out via virtual files (IStream) rather than a shell extension.

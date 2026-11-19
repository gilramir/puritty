# SFTP in SSH terminal clients: UX and user feedback

Surveyed 2026-11-19. Each claim has its source. "Not verified" means no source
was found. Reddit could not be searched or fetched from this sandbox (the search
tool refuses reddit.com), so the user voice comes from Hacker News (via the
Algolia API), GitHub issues, vendor forums, and review sites.

## Summary of the patterns

1. The file pane beside the terminal that follows the shell's directory (MobaXterm) is the model everyone else is asked to copy. Royal TS, Tabby, electerm and Xshell users all ask for it by name.
2. Following the directory is fragile everywhere: it needs shell cooperation (a hook, the title, OSC 7), and it breaks after `sudo`, nested `ssh`, tmux/byobu, `~` paths and old Unix hosts.
3. A second SSH login for the file pane is the main structural complaint. MobaXterm's second connection asks for the second factor again. SecureCRT, Bitvise and (since 2023) RDM run SFTP on the terminal's own connection and say so as a feature.
4. Root-owned files are the most common "it doesn't work" report. SFTP runs as the login user. Users expect the pane to follow `sudo -i`. Clients that solve it run a custom SFTP server command (`sudo /usr/lib/openssh/sftp-server`), like WinSCP.
5. Drop on the terminal itself splits two ways: Xshell/SecureCRT send ZMODEM (`rz` must be on the host), iTerm2 sends scp into the directory of the line you drop on. PuTTY's author says the drop target directory "can't be sensibly" found without shell help.
6. The ZMODEM (`rz`/`sz`) request is very common among Chinese-speaking users: it is the most-voted file request on Windows Terminal (270 reactions) and on Warp. trzsz is its modern successor.
7. Built-in SFTP panes are judged against WinSCP and FileZilla, and lose on speed (Tabby, Termius, RDM) and on basics: folders, multi-select, rename, chmod, typed paths, bookmarks.
8. Remote edit with a local editor and upload on save is expected (MobaXterm, Termius, WinSCP, electerm). Its failure modes are editors that hold one process, and saves that fail silently on permission errors.
9. A separate window or program (Royal TS, Xftp, SecureFX, Bitvise) is tolerated but disliked; users ask for it "within the terminal connection" and docked with the tab.
10. Terminal-first projects decline the feature: Windows Terminal closed an SFTP-browser PR ("not in line with our product vision"), and PuTTY's GUI SFTP wish is "low" priority.

## MobaXterm (Windows)

- **Where:** a left sidebar, the "SSH-browser", shown automatically on SSH login. ([docs §1.6, §6.1.2](https://mobaxterm-en.mobatek.net/documentation.html))
- **Protocol:** SFTP by default; SCP "normal" and "enhanced speed" options; "None" turns it off. It falls back to SCP if SFTP fails. ([docs §4.1](https://mobaxterm-en.mobatek.net/documentation.html), [release 10.4 notes via search](https://blog.mobatek.net/post/mobaxterm-new-release-10.4/))
- **Connection:** a second SSH connection. HPC sites document that this asks for the second factor again: "MobaXterm establishes by default two connections ... the second one for the remote file browser ... which causes a mandatory second prompt for your second factor." Switching to SCP avoids it but "transfers hang indefinitely". ([Alliance Canada MFA wiki, diff page](https://docs.alliancecan.ca/wiki/Special:MobileDiff/144828)) Oakland University and Hawaii tell users to turn the browser off to stop the second Duo prompt. ([Oakland](https://support.oakland.edu/TDClient/33/Support-Center/KB/Article/837/Logging-into-Matilda-with-MobaXterm), [Hawaii](https://uhawaii.atlassian.net/wiki/x/MwArKw)) A FreeIPA thread reports PAM failures when the browser's SFTP login runs on a 2FA host. ([freeipa-users](https://lists.fedorahosted.org/archives/list/freeipa-users@lists.fedorahosted.org/thread/P6M7KG4G2CHEIZ2P746IEE7VNRTLKC5F/))
- **Keyboard-interactive:** the docs say the browser "keeps asking for a password" on keyboard-interactive servers, and that login scripts that print output break SFTP. ([docs §6.8.2](https://mobaxterm-en.mobatek.net/documentation.html))
- **Follow terminal folder:** "Follow SSH path (experimental)"; "will not work on old Unix systems". ([docs §4.1](https://mobaxterm-en.mobatek.net/documentation.html)) It installs a shell hook at session start; if the sidebar is on another tab when you `cd`, it misses the change and `cd .` fixes it. It fails with byobu output and after several SSH hops. ([SO 72193255 mirror](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/72193255/mobaxterm-follow-terminal-folder-doesn-t-work), [SO 41830936 mirror](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/41830936/mobaxterm-follow-terminal-folder-stfp-and-byobu), [Super User 1804247](https://superuser.com/questions/1804247/mobaxterm-file-browser-not-following-terminal-after-multiple-ssh-hops)) A Capterra reviewer: "sometimes the session window does not follow your terminal folder." ([Capterra](https://capterra.com/p/209929/MobaXTerm/reviews/))
- **Drag and drop:** "drag and drop files directly from or to the remote server". ([docs §1.6](https://mobaxterm-en.mobatek.net/documentation.html)) Drop onto the terminal itself: not verified.
- **Remote edit:** double-click opens in your editor (default MobaTextEditor); "Your changes will be saved to the remote server automatically!" ([docs §1.6, §3.1](https://mobaxterm-en.mobatek.net/documentation.html))
- **Root files:** a reviewer wanted the pane to "elevate to root when I 'sudo su'"; Mobatek's answer was SCP mode plus a sudo button in the pane, and "This works." ([b3n.org review](https://b3n.org/mobaxterm-professional-review/)) A Bosch ctrlX forum user reports the SUDO prefix stopped working. ([Bosch forum](https://developer.community.boschrexroth.com/t5/ctrlX-CORE/SUDO-prefix-from-MOBA-XTerm-suddenly-doesn-t-work-anymore/m-p/85416))
- **Permissions, hidden files, symlinks, large directories, queue/resume:** not verified.
- **Praise (many):** HN: "the included SFTP client in MobaXterm that follows the current folder you're currently located in the terminal" ([HN 11446451](https://news.ycombinator.com/item?id=11446451)); "Upon ssh'ing to a system, a sftp session is automatically opened as well" ([HN 13701504](https://news.ycombinator.com/item?id=13701504)); "the GUI sftp (?) client is also pretty nice" ([HN 23092353](https://news.ycombinator.com/item?id=23092353)). The b3n.org reviewer: the sidebar "automatically follows where I am in the terminal", and he wanted that as a global default, not per host. ([b3n.org](https://b3n.org/mobaxterm-professional-review/))
- **Complaints (few each):** no bookmarks in the SFTP browser ([HN 15256444](https://news.ycombinator.com/item?id=15256444)); fails with a password auth style ([HN 9599993](https://news.ycombinator.com/item?id=9599993)); "struggles to upload large files" and "SFTP browser (quick connect) is not working sometime" ([Capterra](https://capterra.com/p/209929/MobaXTerm/reviews/)); "too complex and ugly" ([microsoft/terminal#11855](https://github.com/microsoft/terminal/issues/11855)).

## Termius (desktop and mobile)

- **Where:** SFTP is its own tab, dual-pane (local or remote on each side); "one click" switches between a host's terminal and SFTP. Mobile: "Connect via SFTP" opens a new tab. ([Termius docs](https://docs.termius.com/organize-and-connect-to-hosts/managing-files-with-sftp))
- **Connection:** whether SFTP reuses the terminal's connection is not verified from official docs. A clone's docs (docs.xermius.com) say it does; not Termius.
- **Follow directory:** not verified. There is a per-host default SFTP path setting. ([FAQ](https://docs.termius.com/help-center/faq/how-to-set-a-default-sftp-path))
- **Drag and drop:** between panes, from the OS into a pane, between Termius windows, and from the iPad Files app. ([docs](https://docs.termius.com/organize-and-connect-to-hosts/managing-files-with-sftp))
- **Conflicts and progress:** a Transfers view shows progress and asks about conflicts ("replace" or "keep both"). Mobile redesign added a Transfers tab with pause, resume and retry. ([docs](https://docs.termius.com/organize-and-connect-to-hosts/managing-files-with-sftp), [blog](https://termius.com/blog/rethinking-sftp-for-mobile))
- **Remote edit:** opens in a local app from a temp folder, detects the change and asks whether to upload; remembers the app per file type. ([docs](https://docs.termius.com/organize-and-connect-to-hosts/managing-files-with-sftp))
- **Hidden files:** hidden by default; "Show Hidden Files" in the Actions menu. ([docs](https://docs.termius.com/organize-and-connect-to-hosts/managing-files-with-sftp))
- **Mobile design rationale:** old SFTP was "designed for occasional use"; the two-pane model limited users to two devices; each connection is now a tab. ([blog](https://termius.com/blog/rethinking-sftp-for-mobile))
- **Complaints (several):** slow — "moving folders over SFTP can be quite slow" (Capterra), "sFTP connection is a bit slow ... still use FileZilla" (Findstack); "lacks critical shortcuts & performance improvements" (Trustpilot); paywall — SFTP was a paid feature ([HN 20123496](https://news.ycombinator.com/item?id=20123496)). One LowEndTalk user "truly hate[s] the SFTP features" but keeps it for cross-platform. ([Capterra](https://www.capterra.com/p/234457/Termius/reviews), [Findstack](https://findstack.com/products/termius/reviews?page=4), [LowEndTalk](https://lowendtalk.com/discussion/comment/3453844/), via search summaries)
- **Praise:** "SFTP and SSH can be managed in same space" ([G2](https://www.g2.com/products/termius/reviews)); "share integration is nice" ([HN 24429834](https://news.ycombinator.com/item?id=24429834)).

## SecureCRT and SecureFX (VanDyke)

- **Connect SFTP Tab:** from the File menu or a tab's context menu; it uses "the same transport as the current SSH2 session". ([SecureCRT help](https://documentation.help/SecureCRT/Session_Tabs.htm)) VanDyke markets it: "Open an SFTP tab to the same SSH2 session without having to re-authenticate." ([features](https://www.vandyke.com/products/securecrt/features.html)) Drag-and-drop SFTP happens through that tab. ([tip](https://vandyke.com/support/tips/dragdropft.html)) That the tab is a command-line `sftp>` prompt, not a file browser, is from memory, not verified here.
- **Drop onto the terminal:** dropping files on a session asks for a protocol: ASCII, Xmodem, Ymodem or Zmodem; Y/Zmodem take several files but not folders. ([tip](https://vandyke.com/support/tips/dragdropft.html))
- **SecureFX:** the separate GUI program; shares session settings with SecureCRT. ([Stanford](https://uit.stanford.edu/service/ess/scrt_sfx/securecrt)) Smart-card PINs are not cached, so 2FA by smart card prompts per program. ([VanDyke tip](https://vandyke.com/support/tips/configure-securecrt-securefx-for-2fa-rfc-6187-smartcard-authentication.html))
- **User feedback:** not found beyond mentions.

## Xshell and Xftp (NetSarang)

- **Where:** Xftp is a separate program launched from an Xshell toolbar button; it "opens a new session by using the same account information" — that is, a new login. ([NetSarang KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/31523239)) The two share session files, not connections. ([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/3027927079))
- **Current directory:** Xshell reads the directory from the terminal title. If the title says `~`, Xftp fails with "Cannot display the remote folder". Users must set the prompt to put the path in the title. ([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/1076133906/How+does+Xshell+determine+the+current+working+directory+when+calling+Xftp), [KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/31588536))
- **Requests:** "Combine xshell + xftp tabs" and "Open tabs not windows". ([forum](https://netsarang.atlassian.net/wiki/spaces/ENFA/pages/1315281978/Suggestion+Combine+xshell+xftp+tabs+3), [forum](https://netsarang.atlassian.net/wiki/spaces/ENFA/pages/1314558776/Open+tabs+not+windows+from+xshell+1))
- **Drop onto terminal:** ZMODEM by default, changeable to other protocols in session properties; `rz` opens a file picker. ([KB](https://netsarang.atlassian.net/wiki/spaces/ENSUP/pages/2237305518/File+Transfer+Using+X_Y_ZMODEM)) Tabby users ask for exactly this: "In Xshell, I can select multiple files on my desktop and drag-and-drop them directly into the SSH terminal". ([Tabby#10517](https://github.com/Eugeny/tabby/issues/10517))
- **Root files:** Xftp supports a sudo login, cited by a Tabby request. ([Tabby#7153](https://github.com/Eugeny/tabby/issues/7153))

## Bitvise SSH Client (Windows)

- **Where:** separate SFTP and terminal windows; both open on login by default, or via "New SFTP window". ([Bitvise](https://bitvise.com/getting-started-connect-first-time))
- **Connection:** "only ever establishes one SSH session per process instance", so SFTP windows are channels on that login. ([version history](https://bitvise.com/ssh-client-version-history)) Not stated as a UX claim; inferred.
- **User feedback:** not found.

## Tabby

- **Where:** an SFTP panel opened from the tab's toolbar or context menu; added as an "experimental implementation" in 2021, single files only at first. ([Tabby#296](https://github.com/Eugeny/tabby/issues/296)) A File Transfers panel covers SFTP and ZMODEM. ([1.0.140 notes](https://newreleases.io/project/github/Eugeny/tabby/release/v1.0.140))
- **Connection:** same SSH connection (inferred from bug reports that an SFTP upload "interrupts the SSH connection"). ([Tabby#10616](https://github.com/Eugeny/tabby/issues/10616), [Tabby#10685](https://github.com/Eugeny/tabby/issues/10685)) A design lesson: a transfer failure that drops the shell is worse than a separate connection.
- **Follow directory:** opens at `/` by default; a "blue lightbulb" button jumps to the shell's directory. Several duplicate requests. ([#9396](https://github.com/Eugeny/tabby/issues/9396), [#5291](https://github.com/Eugeny/tabby/issues/5291), [#10863](https://github.com/Eugeny/tabby/issues/10863))
- **Root files:** owner: "You cannot elevate the SSH connection itself." Users answer that a custom subsystem or server path would do it. ([#9816](https://github.com/Eugeny/tabby/issues/9816)) Request for a custom SFTP server command, citing WinSCP and Xftp (8 reactions). ([#7153](https://github.com/Eugeny/tabby/issues/7153))
- **Recurring complaints (many):** no folder upload/download, no multi-select (29 reactions): "If there is no folder to upload, I feel that sftp does not make much sense"; "I have to use XFTP for folder upload now". ([#4946](https://github.com/Eugeny/tabby/issues/4946)) Missing rename, chmod, typed path, search, two-pane layout (16 reactions). ([#7154](https://github.com/Eugeny/tabby/issues/7154)) Slow: "maxxing out at 5.5MB/s on my gigabit network (I'm getting 120MB/s ... on FileZilla)". ([#8972](https://github.com/Eugeny/tabby/issues/8972))
- **Why people wanted it:** "I have hundreds of servers, I don't want to manage more than one configuration"; some servers are only reachable through the session. ([#296](https://github.com/Eugeny/tabby/issues/296))

## WindTerm

- **Where:** a "filer" pane beside the terminal with "Sync Terminal Folder": "When you change directories in the terminal, filer should follow automatically and optionally, vice versa". "Not all local or remote systems support" it. ([blog](https://kingtoolbox.github.io/2022/08/21/sync_terminal_folder))
- **Issues:** sync failing on macOS ([#2563](https://github.com/kingToolbox/WindTerm/issues/2563)); upload hangs in 2.6.1 ([#2360](https://github.com/kingToolbox/WindTerm/issues/2360)); downloaded file all zero bytes ([#2240](https://github.com/kingToolbox/WindTerm/issues/2240)); sudo requests ([#842](https://github.com/kingToolbox/WindTerm/issues/842), [#1656](https://github.com/kingToolbox/WindTerm/issues/1656)). The top issue is "This project has been abandoned" (151 reactions). ([#1596](https://github.com/kingToolbox/WindTerm/issues/1596))

## electerm

- **Features:** SFTP beside the terminal, "Double click to directly edit (small) remote files", ZMODEM and trzsz. ([README](https://github.com/electerm/electerm))
- **Sync path:** a toggle (paperclip button) syncs the SFTP path with the terminal; a user asked for it to be remembered across restarts, and it was added as a setting. ([#3524](https://github.com/electerm/electerm/issues/3524)) Users asked for SSH and SFTP side by side in one view. ([#2525](https://github.com/electerm/electerm/issues/2525)) External editor choice was requested and added. ([#1314](https://github.com/electerm/electerm/issues/1314))

## Royal TS / Royal TSX

- **Where:** "Connect using SFTP" opens a separate window; can be docked beside SSH. ([request](https://community.royalapps.com/t/open-sftp-connection-within-ssh-terminal-window/1921))
- **Requests (recurring, MobaXterm refugees):** a checkbox so SFTP follows the SSH directory, "(this feature is present in mobaxterm)"; later "+1", plus two-way sync and an internal editor. ([#453](https://community.royalapps.com/t/sftp-to-follow-ssh-current-directory/453)) An embedded SFTP panel in the SSH view that stays with the terminal; vendor: "I will put this on our list". ([#1921](https://community.royalapps.com/t/open-sftp-connection-within-ssh-terminal-window/1921)) A macOS user: the side-by-side SFTP "really speeds up work". ([#1697](https://community.royalapps.com/t/sftp-windows/1697))
- One user ruled out Royal TS because its SFTP could not use an external SSH agent. ([b3n.org comments](https://b3n.org/mobaxterm-professional-review/))

## Remote Desktop Manager (Devolutions)

- **Where:** an SSH Shell entry with "Use SFTP connection for remote file transfer" shows an embedded SFTP panel. ([forum](https://forum.devolutions.net/topics/41378/sftp-locks-up-the-program-andor-is-wicked-slow-transferring-files))
- **Connection:** a user asked to reuse the SSH channel for SFTP because Azure Bastion allowed only one; shipped in 2023.2.9: "SFTP over a single SSH connection now works as expected using Azure Bastion." ([forum 39385](https://forum.devolutions.net/topics/39385/use-the-same-ssh-sessionchannel-for-sftp))
- **Complaints:** lockups and "wicked slow" transfers vs FileZilla ([41378](https://forum.devolutions.net/topics/41378/sftp-locks-up-the-program-andor-is-wicked-slow-transferring-files)); no drag and drop to or from Windows Explorer until 2026.3.4 ([51517](https://forum.devolutions.net/topics/51517/sftp-panel-drag-drop-dont-work--either-way)); no delete, no deselect, no leaving home, and edits outside home "silently failing" — fixed in 2026.2 ([52065](https://forum.devolutions.net/topics/52065/sftp-mode-need-a-lot-improvements)); jump-host password asked twice ([31309](https://forum.devolutions.net/topics/31309/ssh-shell-and-ssh-gateway-jump-host--you-have-to-enter-password-twice-)).

## XPipe

- **Model:** no terminal of its own; it launches your terminal and offers a file browser with terminal docking. ([search summary of docs](https://docs.xpipe.io)) Connections through its local SSH bridge cannot use the file browser. ([XPipe 21 notes](https://xpipe.io/blog/xpipe-21-released))
- **Requests:** keep modification times on transfer ([#848](https://github.com/xpipe-io/xpipe/issues/848)); directory auto-refresh and transfer settings ([#882](https://github.com/xpipe-io/xpipe/issues/882)).

## Solar-PuTTY

- SFTP/SCP is grayed out until the app downloads WinSCP libraries. ([quick reference](https://thwack.solarwinds.com/free-tools-trials/f/solar-putty/1323/solarwinds-solar-putty-quick-reference-guide)) AlternativeTo lists it as discontinued since 2019. ([AlternativeTo](https://alternativeto.net/software/solar-putty/about)) UX and feedback: not verified.

## PuTTY (psftp, pscp)

- Only command-line `psftp` and `pscp`. The GUI SFTP wish is "tricky", "low" priority: "Writing big complex GUIs is hard work and I simply don't have the effort to spare." ([wish gui-sftp](https://www.chiark.greenend.org.uk/~sgtatham/putty/wishlist/gui-sftp.html))
- Drop a file on the window: a wish to open an auxiliary SFTP channel and upload to a *configured* directory. ([wish drag-drop](https://www.chiark.greenend.org.uk/~sgtatham/putty/wishlist/drag-drop.html)) Upload to the shell's current directory is "Probably impossible": "there's no reliable way for PuTTY to determine what the currect directory of the remote shell is"; a custom escape sequence raises compatibility and security problems. ([wish drag-drop-to-cwd](https://ftp.fau.de/putty/wishlist/drag-drop-to-cwd.html))
- HN: "putty doesn't support it (wish it did.)" about ZMODEM. ([HN 5232301](https://news.ycombinator.com/item?id=5232301))

## WinSCP (reference point, not a terminal)

- External editor with upload on save; saves don't upload until the editor closes unless "External editor opens each file in separate window (process)" is set — a recurring forum question. ([forum](https://winscp.net/forum/viewtopic.php?p=57877), [docs](https://winscp.net/eng/docs/task_edit)) Uploads go through a background connection, which users say makes saves slower. ([forum](https://winscp.net/forum/viewtopic.php?p=42134)) An option checks the remote file has not changed before saving. ([docs](https://winscp.net/eng/docs/ui_pref_editor))
- Root files: a documented "sudo su" SFTP server setting. ([FAQ](https://winscp.net/eng/docs/faq_su))

## Warp

- No SFTP. "SFTP file transfer out of the box" is open, 24 reactions. ([warp#3131](https://github.com/warpdotdev/warp/issues/3131)) `lrzsz` support, 22 reactions; the top answer points to trzsz. ([warp#988](https://github.com/warpdotdev/warp/issues/988))
- With its SSH extension on the host, the file tree and editor work remotely; you can drag paths into commands, not upload files. ([docs](https://docs.warp.dev/code/ssh-feature-support/), [changelog](https://docs.warp.dev/changelog/2025/))

## iTerm2

- **Upload:** hold Option and drop a file from Finder; it "offers to upload the file via scp into the directory you were in on the line where you dropped it". **Download:** right-click a filename in `ls` output, "Download with scp from hostname". Menu-bar items track progress. ([docs](https://iterm2.com/documentation-shell-integration.html))
- **How it knows the host and directory:** shell integration escape codes on each host, or regex triggers on the prompt. Doesn't work under plain tmux or screen by default. ([docs](https://iterm2.com/documentation-shell-integration.html))
- **Connection:** its own libssh2 login (password, keyboard-interactive, key) — a second login. ([docs](https://iterm2.com/documentation-shell-integration.html)) Without remote shell integration, an Option-drop just hands the file to Finder. ([iterm2-discuss](https://groups.google.com/g/iterm2-discuss/c/yD7rn7AugIo))
- **Feedback:** praised in passing: "Drag-drop files to upload with scp." ([HN 12858197](https://news.ycombinator.com/item?id=12858197)) Much feedback not found.

## Windows Terminal

- No file transfer. The most-voted file request is ZMODEM, 270 reactions, open on the "infinite backlog" for a plugin model: "We're not going to do this ourselves, but it is a valuable feature". ([terminal#1999](https://github.com/microsoft/terminal/issues/1999)) A team member at first did not see why a terminal is involved; users: "Other Terminal do this ... iTerm2 on macOS, SecureCRT / XShell on Windows".
- "Why not add session management and file transfer" (users cite MobaXterm): "File transfer is probably best left for something like `scp`". ([#11855](https://github.com/microsoft/terminal/issues/11855))
- An outside PR adding an SFTP browser pane was closed: "We're a terminal emulator and we do not intend to expand into file browsing. Cool feature though!" ([#20736](https://github.com/microsoft/terminal/pull/20736))
- "SSH Drag-and-Drop File Transfer" idea: "PuTTY and similar clients have this feature" (actually not PuTTY), suggesting a wrapper using the session's variables and `scp`. ([discussion 17029](https://github.com/microsoft/terminal/discussions/17029))

## ZMODEM and trzsz (cross-cutting)

- HN opinions split. For: "It's still hard to match the convenience of moving files to and from a server with RZ/SZ" ([HN 12769518](https://news.ycombinator.com/item?id=12769518)); "I still think rz and sz should be supported everywhere" ([HN 35705490](https://news.ycombinator.com/item?id=35705490)). Against: "a serious violation of the cleanliness and available attack surface involved in a terminal interface" ([HN 35706069](https://news.ycombinator.com/item?id=35706069)).
- Its appeal: it works through jump hosts and `sudo`, since it rides the shell, not a new SSH channel. ([Tabby#296](https://github.com/Eugeny/tabby/issues/296), comment by XianwuLin, for the jump-host case)
- trzsz: rz/sz-like, with drag-and-drop of files and directories, progress bars and tmux support; warns that auto-upload directories are "a security risk if you connect to a malicious server". ([trzsz-go](https://github.com/trzsz/trzsz-go))

## Recurring feature requests (across products)

1. File pane in the terminal tab, not a separate window (Royal TS, Xshell, electerm, RDM).
2. Follow the shell's directory, on by default, remembered (MobaXterm, Royal TS, Tabby, electerm); optionally two-way.
3. Folders and multi-select for upload and download (Tabby, the top request).
4. Root access: sudo/custom SFTP server command (Tabby, WindTerm, MobaXterm).
5. Drop onto the terminal to upload (Windows Terminal, Tabby, PuTTY wish).
6. ZMODEM / trzsz (Windows Terminal, Warp).
7. Speed comparable to scp/FileZilla (Tabby, Termius, RDM).
8. Basic file-manager operations: rename, delete, chmod, typed path, bookmarks, search.
9. One login: no second password or second factor (HPC sites, RDM/Bastion).

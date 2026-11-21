# Standalone file-transfer programs: UX survey and user feedback

Researched 2026-11-19 for puritty's SFTP work (drop a file on the window to
upload to the tab's host, plus general SFTP).

**Method note.** Reddit could not be reached from this sandbox (the search
tool and the fetch tool both refuse `reddit.com`, and the redlib mirror did
not resolve). G2 and Capterra review pages returned 403. User opinion here
comes from Hacker News, DEV Community, AlternativeTo, the WinSCP forum, the
FileZilla and Cyberduck trackers, and vendor docs. Where a claim says "not
verified", no source was found for it. Several summaries below came from a
search tool that paraphrases pages; quotes marked as quotes were in the
fetched text.

## Summary of patterns

1. Every mature client puts transfers in a **background queue** with Queued /
   Failed / Done views, and lets prompts wait in the queue (WinSCP, FileZilla).
2. The **overwrite prompt** is the most-discussed dialog. People want sizes and
   dates for both sides, "Newer only", "Rename", "Skip", and an "apply to all"
   whose scope is clear. The scope is a recurring bug and complaint source.
3. **Remote edit with auto-upload** is loved and fragile: tabbed editors,
   atomic-save editors and disconnects break the link and lose edits silently.
4. Nobody detects **"changed on the server since you opened it"** well. Transmit
   has a "Check for editing conflicts" setting; Mountain Duck makes a timestamped
   duplicate; most others overwrite.
5. **sudo/root files** are the top gap. Only WinSCP (custom sftp-server command)
   offers a path; FileZilla rejected it; VS Code needs an extension.
6. **Trust drives switching.** FileZilla's bundled-adware installer pushed many
   to WinSCP and Cyberduck. Plaintext saved passwords were the second blow.
7. **Speed** complaints are about many small files and high latency. FileZilla
   is credited with better parallel transfers. Pipelining is the fix.
8. **Two-pane vs explorer:** WinSCP says 3% use its Explorer mode; Mac users
   praise one-window clients but miss "commander" panes when they leave WinSCP.
9. **Drive mapping** (SSHFS-Win, rclone, Mountain Duck) feels native but users
   report Explorer/Finder freezes, slow listings, and 0-byte files on drops.
10. **Line endings** matter only for FTP; SFTP is binary, yet WinSCP's text mode
    and internal editor still rewrite line endings and surprise people.

---

## WinSCP (Windows)

**Layout.** Two interfaces. Commander shows local and remote panels side by
side; Explorer shows only the remote panel
([interfaces](https://winscp.net/eng/docs/interfaces)). The author says only
"about 3% of users" use Explorer, "with decreasing trend"
([forum](https://winscp.net/forum/viewtopic.php?p=121606)). The docs still
recommend Explorer to newcomers because it looks like Windows Explorer (same
page). Forum users asked for a Commander view without the local panel, to free
space ([forum](https://winscp.net/forum/viewtopic.php?p=93344)).

**Transfers and queue.** The queue sits at the bottom of the main window and
by default is "Hide when Empty". Each line is "one background operation (not
one file)". When an operation needs input, its row shows "Query", "Error" or
"Prompt" and the icon flashes; the prompt pops up only while the main
connection is idle, and the pop-up can be turned off. Suspend/Resume per item
and for all. `Del` cancels an item
([queue docs](https://winscp.net/eng/docs/ui_queue)).

**Overwrite dialog.** Shows size and modification time of "New" and
"Existing". Buttons: Yes, No, Cancel (Cancel stops the whole batch; No skips one
file). The Yes drop-down has "Yes to All" (Shift+click) and "Newer only"
(Ctrl+click); the No drop-down has "No to All", "Append"/"Resume" (Alt+click)
and "New name" (Ctrl+click). "Never ask me again" leaves only Yes
([overwrite docs](https://winscp.net/eng/docs/ui_overwrite)).
Problem: "Yes to All" is scoped to one batch. With "Transfer each file
individually", each file is its own batch, so users saw the prompt repeat per
file ([forum](https://winscp.net/forum/viewtopic.php?p=47230);
[forum](https://winscp.net/forum/viewtopic.php?p=74061)). A user called the
competing dialog entries "confusing"
([forum](https://winscp.net/forum/viewtopic.php?p=80588)).

**Errors.** Permission errors show the server text plus code, e.g. "Error
code: 3 / Error message from server: Permission denied". The moderator's stock
answer is "It's the server that denies you the access, not WinSCP. We cannot
know why" ([forum](https://winscp.net/forum/viewtopic.php?p=52267)). The exact
Skip/Retry/Abort dialog layout is not verified.

**Edit remote file.** Downloads to a temp directory, opens the internal or an
external editor, and "once you change the file, WinSCP uploads it back" through
the background queue. The internal editor forces text mode. With a tabbed
editor, the second instance hands the file to the first and exits, so WinSCP
cannot tell when the file is closed and keeps watching until WinSCP exits; there
is an "External editor opens each file in separate window (process)" setting
([edit docs](https://winscp.net/eng/docs/task_edit)).
Pitfalls reported: a new editor process got a new temp folder, so saves went to
the wrong copy ([forum](https://winscp.net/forum/viewtopic.php?p=57877)); temp
copies deleted so the file "cannot be updated anymore"
([forum](https://winscp.net/forum/viewtopic.php?p=106723)); after a disconnect
the open file was "de-linked" and saves no longer uploaded
([forum](https://winscp.net/forum/viewtopic.php?p=128906)). A user asked for
detection of changes in the remote file while editing
([forum](https://winscp.net/forum/viewtopic.php?p=68946)); no such check is
documented.

**Keep remote directory up to date.** Watches a local folder and syncs it to
the remote one on every change. It only learns "something has changed", so it
runs a full sync; a rename becomes delete plus add; it warns above 500
subfolders; it needs accurate remote timestamps "or data can be lost"
([docs](https://winscp.net/eng/docs/task_keep_up_to_date)). One user: "Winscp
with the live sync feature has been a saver for me"
([DEV](https://dev.to/nataliedeweerd/what-ftp-software-do-you-use-p6m/comments)).
A report that it sometimes skips a file
([forum](https://winscp.net/forum/viewtopic.php?p=106170)).

**Synchronize.** A dialog with modes (Synchronize files, Mirror files,
Synchronize timestamps), criteria (time, size, checksum) and a "Preview
changes" checklist with one row per action
([sync dialog](https://winscp.net/eng/docs/ui_synchronize);
[checklist](https://winscp.net/eng/docs/ui_synchronize_checklist)). Size
criteria and text mode cannot work together
([FAQ](https://winscp.net/eng/docs/faq_synchronize)).

**Open in PuTTY.** Commands > Open in PuTTY writes a temporary PuTTY site
("WinSCP temporary session") with connection options only; terminal settings
are PuTTY's defaults. It can pass the password, but the docs prefer Pageant.
Opening the shell in the same directory needs a hand-written startup command
with `!/` and `-t`
([docs](https://winscp.net/eng/docs/integration_putty)). The reverse (open the
file browser at the shell's cwd) does not exist; a Server Fault question asks
for it ([SF](https://kiwix.lema.org/serverfault.com_en_all_2023-11/questions/834343/opening-winscp-in-the-same-folder-as-opened-putty-session)).

**sudo workaround.** No protocol lets the user change mid-session, so WinSCP
lets you set the SFTP server command to `sudo /path/to/sftp-server`; it works
only with passwordless sudo ([FAQ](https://winscp.net/eng/docs/faq_su)).
Pitfalls: the path differs by distro; a sudoers rule naming only the binary
failed for some users; errors appear as "Cannot initialize SFTP protocol"
([kerneltalks](https://kerneltalks.com/tools/how-to-use-sudo-access-in-winscp/);
[forum](https://winscp.net/forum/viewtopic.php?p=104003)).

**Drag out to Explorer.** Needs a shell extension that fakes a dummy folder
and uses CopyHook to learn the drop target. The fallback downloads to temp
then copies, with no background transfer; closing the Explorer window mid-copy
can strand the file in temp
([dragext](https://winscp.net/eng/docs/dragext);
[forum](https://winscp.net/forum/viewtopic.php?p=42752)). Empty `scpNNNNN`
folders at the destination are a known symptom
([forum](https://winscp.net/forum/viewtopic.php?p=69275)).

**Line endings.** Default Automatic mode picks text or binary by extension;
text mode converts CRLF to LF on upload; the docs admit "known issues" with
Automatic mode for source files
([transfer modes](https://winscp.net/eng/docs/transfer_mode);
[FAQ](https://winscp.net/eng/docs/faq_line_breaks)). Users report CRLF
not preserved after upgrades
([forum](https://winscp.net/forum/viewtopic.php?p=129488)).

**Speed.** On high latency SFTP is slow because of request/response round
trips; WinSCP's FAQ covers buffer settings
([FAQ](https://winscp.net/eng/docs/faq_slow)). One user fixed slowness by
turning off "Optimize connection buffer size"
([forum](https://winscp.net/forum/viewtopic.php?p=90034)).

**Keyboard.** Commander is a Norton Commander style UI (F-keys, Tab between
panels) ([interfaces](https://winscp.net/eng/docs/interfaces)). Exact key map
not verified here.

**Feedback.**
- Common: people moved to it from FileZilla. "When FileZilla started doing the
  adware thing years ago, I switched to WinSCP on Windows and never looked
  back" ([HN](https://news.ycombinator.com/item?id=26601941)). "WinSCP is
  better than FileZilla ever was" (same thread). "wish it had just a couple more
  features but it sure beats using filezilla"
  ([AlternativeTo](https://alternativeto.net/software/winscp/about/)).
- Common: automation praise. "epic automation interface which include
  PowerShell cmdlets" ([HN](https://news.ycombinator.com/item?id=26601941)).
- Common: Windows only. "it doesn't work on Linux"
  ([HN](https://news.ycombinator.com/item?id=26601941)).
- Mixed: speed. "FileZilla has a speed advantage over winscp but nothing like
  the flexibility"; others say WinSCP "has long since improved dramatically"
  ([HN](https://news.ycombinator.com/item?id=26601941)).
- Missed when people leave it: "I do miss the WinScp file commander like
  interface" (Cyberduck user, same thread).

## FileZilla (Windows, macOS, Linux)

**Layout.** Top to bottom: quickconnect bar, message log, local and remote
panes (each with tree and list), transfer queue. The queue has three tabs:
"Queued files", "Failed transfers", "Successful transfers"; errors are red in
the log ([FileZilla Pro docs](https://filezillapro.com/docs/v3/features-v3/transfer-queue/);
[ticket 5145](https://trac.filezilla-project.org/ticket/5145?version=0)).
During sync, skipped files appear under "Successful", so you can't tell what
moved ([trac](https://trac.filezilla-project.org/ticket/12251)) (not verified
that this ticket is the skipped-file one; the search tool attributed it).
Tom's Hardware: "cluttered with no less than six panes and really small,
nondescript icons" ([Tom's](https://www.tomshardware.com/reviews/linux-internet-application,2407-9.html)).
TechRadar: "it's still very ugly though"
([TechRadar](https://www.techradar.com/news/software/applications/8-of-the-best-linux-ftp-clients-902168/2)).

**Overwrite dialog ("Target file already exists").** Options include
overwrite, overwrite if source newer, overwrite if size differs, overwrite if
size differs or source newer, resume, rename, skip; plus "Always use this
action" and "Apply to current queue only"
([FileZilla Pro docs](https://filezillapro.com/docs/v3/advanced/change-default-file-exists-behaviour/)).
Choices made in the dialog last only for the session; the permanent default is
under Transfer > Default file exists action, separately for uploads and
downloads ([ticket 5560](https://trac.filezilla-project.org/ticket/5560)).
Complaints: the prompt keeps returning despite "always use this action"
([ticket 5560](https://trac.filezilla-project.org/ticket/5560);
[ticket 8114](https://trac.filezilla-project.org/ticket/8114)); "apply to
current queue only" does not cover files queued later in the same operation
([ticket 9570](https://trac.filezilla-project.org/ticket/9570)); "overwrite if
newer" re-uploads files whose time and size look identical
([openSUSE](https://forums.opensuse.org/t/filezilla-uploads-all-files-despite-being-told-otherwise/122248)).

**"File has changed, upload back?"** View/Edit downloads to temp; on save
FileZilla asks whether to upload the file back. Users asked to skip the
question and upload on save (duplicate of #2914)
([ticket 11795](https://trac.filezilla-project.org/ticket/11795)). Misfires:
after switching servers, the prompt offered to upload to the wrong server
([ticket 11769](https://trac.filezilla-project.org/ticket/11769)).

**Site Manager.** Saved sites with protocol, host, logon type, and per-site
settings. Passwords were stored in plain text, then base64 in
`sitemanager.xml`; a master password arrived in 2017 (exact version not verified) after ten years of
requests ([FileZilla Pro docs](https://filezillapro.com/docs/v3/advanced/master-password/);
[Slashdot](https://it.slashdot.org/story/17/05/26/2236205/10-years-later-filezilla-adds-support-for-master-password-that-encrypts-your-logins)).

**Bundled adware.** Since 2013 the default Windows installer may carry
"bundled offers"; the clean installer hides behind "Show additional download
options" ([Malwarebytes](https://www.malwarebytes.com/blog/news/2013/11/sourceforge-drives-off-downloads-ask-why);
[HN 2024](https://news.ycombinator.com/item?id=39613789)). Quotes: "The entire
point here is to trick or confuse people who aren't paying attention"; "We've
had to ban the application entirely from our work machines"
([HN](https://news.ycombinator.com/item?id=39613789);
[HN](https://news.ycombinator.com/item?id=26601533)). "Setup files include
BUNDLEWARE, windows defender detecting unwanted program"; "Official download:
Virus detected. Come on." ([AlternativeTo](https://alternativeto.net/software/filezilla/about/)).

**sudo.** Requests for "sudo on login" and an "su" dialog were rejected; one
reporter "had to switch to WinSCP"
([ticket 12073](https://trac.filezilla-project.org/ticket/12073);
[ticket 2215](https://trac.filezilla-project.org/ticket/2215)).

**Errors.** "Open for write: permission denied" then "File transfer failed",
in red in the log, item moved to Failed transfers
([OCLC help](https://help.oclc.org/Librarian_Toolbox/Troubleshooting/I_am_getting_an_error_that_says_Open_for_write%3A_permission_denied_and_file_transfer_failed)).

**Timestamps, permissions, ASCII.** Timestamp preservation is off by default
and lives in the Transfer menu
([tigertech](https://support.tigertech.net/filezilla-preserve-timestamps)).
A user found Cyberduck uploads got 664 while FileZilla's got 644
([ticket 11104](https://trac.filezilla-project.org/ticket/11104)) (attribution
from the search tool, not fetched). Auto mode uses ASCII for text extensions
and for dotfiles and extensionless files; this only applies to FTP, as "SFTP can
only transfer files in binary mode"
([wiki](https://wiki.filezilla-project.org/Data_Type)).

**Speed.** Credited with good parallel SFTP: "Neither Cyberduck nor WinSCP
seem to be able to do parallel transfers as well as FileZilla can, especially
over SFTP"; "Filezilla was a lot faster on fast connections"
([HN](https://news.ycombinator.com/item?id=26601941)).

**Feedback.**
- Common: cross-platform. "The nice thing about FileZilla is that you don't
  have to qualify which OS you're using"
  ([HN](https://news.ycombinator.com/item?id=26601533)). "on Linux I'm stuck
  with FileZilla" ([AlternativeTo](https://alternativeto.net/software/filezilla/about/)).
- Common: distrust after bundling (above).
- One-off: "FileZilla couldn't even connect reliably to multiple SFTP accounts
  on AWS" ([HN](https://news.ycombinator.com/item?id=26601533)).

## Cyberduck (macOS, Windows)

**Layout.** One browser window per connection (remote only, no local pane),
bookmarks, and a separate Transfers window. In version 6 the ability to queue
transfers was removed; users filed "When will CyberDuck restore the ability to
queue transfers?" and one "can't believe it was a feature!"
([#10139](https://lists.cyberduck.io/pipermail/cyberduck-trac/2017-November/037576.html);
[#9984](https://lists.cyberduck.io/pipermail/cyberduck-trac/2018-April/038403.html)).
The Transfers window shows few rows ("about 7 transfers on screen")
([#9740](https://lists.cyberduck.io/pipermail/cyberduck-trac/2016-October/035501.html)),
hangs with hundreds of items
([#5676](https://trac.cyberduck.io/ticket/5676)), and progress shows in three
inconsistent places ([#11572](https://lists.cyberduck.io/pipermail/cyberduck-trac/2021-January/045349.html)).

**Editing.** Downloads to a temp dir, opens the editor; "The file will be
uploaded to the server every time you choose File → Save". Version 9 can keep
the last 5 versions in a hidden `.duckversions` folder on servers without
native versioning ([docs](https://docs.duck.sh/cyberduck/edit/)). No conflict
check is documented. Failures: uploads after save silently stop after some
cycles ([#7310](https://lists.cyberduck.io/pipermail/cyberduck-trac/2020-June/043597.html));
temp-name-then-rename fails in non-writable dirs
([#5373](https://lists.cyberduck.io/pipermail/cyberduck-trac/2010-October/015201.html)).

**sudo.** Open requests: "Add support to run subsystem with sudo" (#8230),
"Execute SFTP with sudo on connect" (#11636)
([#8230](https://lists.cyberduck.io/pipermail/cyberduck-trac/2021-March/045632.html);
[#11636](https://lists.cyberduck.io/pipermail/cyberduck-trac/2021-March/045628.html)).

**Feedback.** "Switched from Filezilla to this. Better UI."; "it does struggle
with some servers when uploading very large files"
([AlternativeTo](https://alternativeto.net/software/cyberduck/about)).
"So buggy though" ([HN](https://news.ycombinator.com/item?id=26601533)).
A recommended FileZilla replacement on HN in 2024
([HN](https://news.ycombinator.com/item?id=39613789)).

## Mountain Duck (macOS, Windows)

Mounts a server as a drive in Finder/Explorer. Modes: Online (stream) and
Smart Synchronization (local cache, offline use, background upload). It polls
open folders about once a minute. On a conflict, "the file with conflicting
edits will be renamed with the current time added to the filename. You will
have to compare the changes manually"
([docs](https://docs.duck.sh/mountainduck/connect/sync)). Users report
duplicate files ([#10779](https://lists.cyberduck.io/pipermail/cyberduck-trac/2019-August/041584.html)).
An App Store reviewer: "slow and irritating", and expensive
([App Store](https://apps.apple.com/hu/app/mountain-duck/id1024974133?mt=12)).
Version 5 moved to a subscription, per a competitor's listing (not verified on
the vendor site).

## Transmit 5 (macOS, Panic)

**Layout.** Dual pane; each pane can be local or a server. Default: left is
Home, right is empty ([prefs](http://help.panic.com/transmit/transmit5/preferences)).

**Conflicts.** "When an Item Already Exists" is a preference, separate for
files ("Ask me what to do", "Replace", "Try to resume", "Keep both files"
(appends 2), "Skip") and folders ("Replace", "Merge", "Keep both", "Skip"),
with a warning about Replace/Merge on folders. There is a "Check for editing
conflicts" setting, and "Preserve Modification Dates"; permissions default to
the server's, with per-extension rules ([prefs](http://help.panic.com/transmit/transmit5/preferences)).
Double-click can be set to Transfer, Edit, or Edit in External Editor (same page).

**Mount.** Transmit Disk (kernel-extension Finder mount) was dropped in 5.6.0
([Panic](https://help.panic.com/transmit/td-troubleshoot/)). HN users had liked
it: "My most favorite features is the ability to mount a server as a disk"
([HN](https://news.ycombinator.com/item?id=10671645)).

**Feedback.** "I used to switch FTP clients all the time until I stumbled upon
Transmit"; "so easy to use" ([HN](https://news.ycombinator.com/item?id=10671645)).
Price doubts: "what Transmit does that makes it worth $45"
([HN](https://news.ycombinator.com/item?id=16083618)). One user left Cyberduck
for it over unreproducible bugs (same thread family; attribution by the search
tool).

## ForkLift 4 (macOS)

Two-pane Finder replacement with SFTP, sync and remote edit. Release notes show
SFTP churn: 4.2.5 switched from libssh2 to OpenSSH and was pulled; users hit an
"AskPassTool" error; IPv6 SFTP crashes; a one-connection-per-user server that
worked in ForkLift 3 broke in 4
([blog 4.2.5](https://blog.binarynights.com/2025/02/25/forklift-4-2-5-is-available/);
[intro comments](https://blog.binarynights.com/2023/09/05/introducing-forklift-4/comment-page-1/)).
Earlier fixes include zero-byte downloads from some SFTP servers
([changelog](https://mac.softpedia.com/progChangelog/ForkLift-Changelog-24241.html)).
WinSCP users compare their sync to it: "It even syncs subfolders like ForkLift"
([AlternativeTo](https://alternativeto.net/software/winscp/about/)).

## Commander One (macOS)

Two-pane manager; SFTP in Pro. Reviews: "old-school geeky", confusing for
Finder users; sometimes slow deleting
([G2](https://g2.com/products/commander-one/reviews/commander-one-review-4409006)).
Changelog fixes for SFTP disconnects and crashes
([version history](https://wiki.eltima.com/user-guides/commander/commander-one-from-the-mac-app-store.html)).
Most review sources are vendor-adjacent.

## Total Commander SFTP plugin (Windows)

A file-system plugin by Christian Ghisler; remote server appears as a panel in
TC's two-pane UI ([wiki](https://ghisler.ch/wiki/index.php/Secure_FTP_plugin)).
Early versions uploaded up to 3x slower; later users found login and listing
"almost instantaneous"
([forum](https://ghisler.ch/board/viewtopic.php?p=155896)). No ssh-agent
support at one point because Ghisler found no documentation for the Windows
agent (same thread family; not verified in the current version).

## Far Manager NetBox (Windows)

WinSCP's own Far plugin was discontinued and replaced by NetBox, built on the
WinSCP code base (SFTP/FTP/SCP/WebDAV/S3)
([WinSCP](https://winscp.net/eng/docs/far);
[GitHub](https://github.com/michaellukashov/Far-NetBox)). Keyboard-only, inside
Far's panels. A user reports a connection that "doesn't exposure any errors"
([SO](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/69786178/far-manager-netbox-sftp-can-t-connect-to-the-linux-server)).

## VS Code Remote-SSH explorer

Drag files and folders from the OS into the remote Explorer to upload; a
"Download..." context action with multi-select; dragging out of the remote
Explorer worked for a single file and not on Linux, per the 1.36 notes
([release notes mirror](https://source-hub.etos-pro.ru/microsoft/vscode-docs/src/commit/cfc56fe64a5a91504dfe99f824a42debaa721c1b/remote-release-notes/v1_36.md)).
Files are edited in place on the server, so there is no temp copy to lose, but
root-owned files fail with EACCES; the fix is the "Save as Root in Remote -
SSH" extension or logging in as root
([DigitalOcean](https://www.digitalocean.com/community/questions/how-to-edit-files-with-vs-code-remote-ssh-with-non-root-user)).
Cursor (a VS Code fork) shows "Insufficient permissions. Select 'Retry as
Sudo'" locally ([Cursor forum](https://forum.cursor.com/t/linux-ubuntu-failed-to-save-hosts-insufficient-permissions-select-retry-as-sudo-to-retry-as-superuser/93576)).

**SFTP extensions** (liximomo, now Natizyskunk fork): local workspace mirrored
to a server; `uploadOnSave` off by default; uploads only overwrite and create,
never delete
([wiki](https://github.com/Natizyskunk/vscode-sftp/wiki/configuration)).
"There's no check in vscode on open, so it's easy to lose those changes when
files are edited on the server"
([SO](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/48756394/vscode-remote-editing-download-on-open-option)).
Bugs: download leaves the local document blank
([lightrun](https://lightrun.com/answers/liximomo-vscode-sftp-the-download-leaves-my-local-document-blank)).

## JetBrains deployment / Remote Host

Tools > Deployment > Browse Remote Host opens a Remote Host tool window; drag
between Project and Remote Host to upload or download, Ctrl to copy rather than
move ([PhpStorm blog](https://blog.jetbrains.com/phpstorm/2013/03/drag-drop-project-files-to-remote-hosts-in-phpstorm/);
[docs](https://www.jetbrains.com/help/idea/remote-host-tool-window.html)).
Automatic upload: Always / On explicit save / Never. The setting for remote
changes can be "No" (silently overwrite remote changes since the last sync),
"Compare timestamp & size", or "Compare content", which open a diff
([WebStorm docs](https://www.jetbrains.com/help/webstorm/2022.2/settings-deployment-options.html)).
A local rename leaves the old name on the server
([IDEA docs](https://www.jetbrains.com/help/idea/2023.1/settings-deployment-options.html)).
This is the only surveyed tool with a built-in diff on conflict.

## Drive mapping on Windows

**SSHFS-Win** (WinFsp + sshfs): map `\\sshfs\user@host` in Explorer
([GitHub](https://github.com/winfsp/sshfs-win)). Issue #395: adding an sshfs
location "makes Windows Explorer very very very slow"
([issues](https://www.github.com/winfsp/sshfs-win/issues)).
**rclone mount**: Explorer is slow because it wants thumbnails for every file;
`--network-mode` stops that; `--buffer-size=0` made right-click usable over
SFTP ([rclone forum](https://forum.rclone.org/t/for-mount-sftp-why-right-click-on-exe-file-is-so-slow-until-it-freezes/33830));
Windows hangs when the remote is unreachable
([rclone forum](https://forum.rclone.org/t/windows-unresponsiveness-with-rclone-mount-on-failing-to-connect-to-remote-expected-behavior-or-fixable/54067)).
**SFTP Drive / SFTP Net Drive (nsoftware)**: small G2 sample, 4.5/5; vendor
lists server-specific failures, e.g. servers without file resize interrupt
Windows copies ([known issues](https://cdn.nsoftware.com/help/NDC/app/pg_knownsftpserverissues.htm)).
**General sshfs** (HN): "it takes upwards of a minute to list a directory with
like 100 items"; "when sshfs flakes out then it has a habit of leaving you with
0-byte files"; "hung mounts all the time"
([HN](https://news.ycombinator.com/item?id=30987770);
[HN](https://news.ycombinator.com/item?id=31812506)) (quotes as given by the
search tool, threads not fetched). Mounts can "cause complete freeze-ups of
Explorer/Finder" ([SF](https://kiwix.lema.org/serverfault.com_en_all_2023-11/questions/186767/why-are-sftp-bridges-so-painfully-slow)).

## Terminal-attached file browser (adjacent, not standalone)

MobaXterm's SFTP sidebar can follow the shell's cwd ("Follow SSH path
(experimental)"); it fails on old Unixes, breaks when the shell prints extra
output (byobu), and goes stale if the tab is not visible
([SO](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/72193255/mobaxterm-follow-terminal-folder-doesn-t-work);
[SO](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/41830936/mobaxterm-follow-terminal-folder-stfp-and-byobu)).
Royal TS users asked for the same "follow" checkbox
([Royal forum](https://community.royalapps.com/t/sftp-to-follow-ssh-current-directory/453)).

---

## Cross-cutting themes

### Overwrite / conflict prompts
- Liked: showing size and date of both files (WinSCP), "Newer only" / "if
  source newer", "Keep both" (Transmit), per-direction defaults (FileZilla).
- Disliked: "apply to all" whose scope is a batch, queue or session and not
  what the user thought (WinSCP batch scope, FileZilla session/queue scope).
  Prompts that return after "always". "Newer" that is fooled by clock or
  timestamp-precision differences
  ([openSUSE](https://forums.opensuse.org/t/filezilla-uploads-all-files-despite-being-told-otherwise/122248)).
- Background transfers need prompts that wait in the queue (WinSCP Query/Prompt
  state) rather than steal focus.

### Remote editing pitfalls
- Lost link between temp file and remote: tabbed editors, new editor
  processes, disconnects (WinSCP, Cyberduck).
- Atomic-save editors (Vim's rename-then-write) can defeat file watchers; Vim
  docs suggest `backupcopy=yes` for watched files
  ([vim_dev](https://groups.google.com/g/vim_dev/c/DCs_TFkxXe4/m/Cq0CE_6-AwAJ)).
- No client but JetBrains (diff) and Transmit (a setting) checks whether the
  server copy changed since download. Mountain Duck keeps both.
- Upload-to-temp-name-then-rename protects against partial files but fails in
  non-writable dirs and on servers that refuse renames
  ([WinSCP](https://winscp.net/eng/docs/message_transfer_finished_could_not_rename)).

### Timestamps and permissions
- Preserving mtime is off by default in FileZilla; WinSCP's sync and "keep up
  to date" depend on accurate timestamps.
- New-file permissions mostly follow the server umask; SFTP does not force 644
  the way some FTP servers do ([supportsages](https://www.supportsages.com/linux-setting-umask-for-sftp)).

### Line endings
- SFTP is binary; only FTP has ASCII mode. Surprises come from clients that
  still convert (WinSCP text mode, internal editor) and from FTP auto mode
  treating dotfiles as text ([FileZilla wiki](https://wiki.filezilla-project.org/Data_Type)).

### Speed
- Per-request round trips dominate on latency; pipelining gave an 8x upload
  speedup in libssh2 ([Daniel Stenberg](https://daniel.haxx.se/blog/2010/12/08)).
  OpenSSH exposes `-B` and `-R` for request size and count.
- Many small files: parallel connections help; FileZilla is credited for this.
- Bigger buffers can backfire on some servers (16k to 16M took a test from 18 s
  to 45 min) — single report via the search tool, not fetched.

### sudo / root-owned files
- Only WinSCP supports it, through `sudo /path/to/sftp-server` and
  NOPASSWD sudoers. FileZilla rejected it; Cyberduck has open tickets; VS Code
  needs an extension. Demand recurs across products, including Devolutions and
  Royal TS ([Devolutions](https://forum.devolutions.net/topics/32992/sftp-sudo-on-login-for-winscp-add-server-command--protocol-option-like);
  [Royal](https://support.royalapps.com/support/discussions/topics/17000010022)).

### Why people switch
- Trust (FileZilla bundling, plaintext passwords) is the most-cited reason.
- Platform: WinSCP is Windows only; Linux users stay with FileZilla or use
  Nautilus/Dolphin's `sftp://` ([HN](https://news.ycombinator.com/item?id=39613789)).
- Features that bind users: WinSCP's automation and live sync, Transmit's
  mount, WinSCP's commander panes.
- Reliability one-offs: Cyberduck "so buggy", FileZilla failing on some
  servers ("Filezilla for some reason doesn't like to connect to it"
  ([DEV](https://dev.to/nataliedeweerd/what-ftp-software-do-you-use-p6m/comments))).

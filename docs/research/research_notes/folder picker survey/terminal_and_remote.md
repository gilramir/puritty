# Terminal file managers, fuzzy pickers and remote clients

Survey notes, 2026-11-20, for the remote folder picker (`../../../sftp.md`
FT32). Quotes from the GitHub API, the HN Algolia API or fetched pages are
verbatim. Reddit answered 403 and Stack Overflow wouldn't fetch, so HN,
GitHub issues, vendor forums and trackers stand in. "(unverified)" marks
what was seen only in a search summary.

## 1. Terminal file managers

### ranger (Python, Miller columns and a preview)

Three columns (parent, current, preview), hjkl. `m<key>` sets a bookmark,
`` `<key> `` or `'<key>` jumps; `:cd` completes bookmarks; "cd on quit" by
a shell wrapper (<https://raw.githubusercontent.com/ranger/ranger/master/doc/ranger.pod>).
- "Launch ranger using a keybinding from my shell … allows me to very
  quickly switch folders" (<https://news.ycombinator.com/item?id=24324577>)
- "it being slow pythonware is sometimes a problem with extra large dirs"
  (<https://news.ycombinator.com/item?id=40325112>)
- nnn's author: "I found ranger's changing/shifting panes very confusing"
  (<https://news.ycombinator.com/item?id=18521462>)

### lf (Go, a ranger clone)

Marks with `m` and `'`, kept in `~/.local/share/lf/marks`; `cd "$(lf
-print-last-dir)"`. **Mouse off by default** (<https://raw.githubusercontent.com/gokcehan/lf/master/doc.md>).
- "A lot faster in all aspects" (<https://news.ycombinator.com/item?id=40298792>);
  "lf is too barebones for me" (<https://news.ycombinator.com/item?id=40325112>)

### nnn (C, minimal)

One list; "type-to-nav" filters as you type; bookmarks, contexts,
cd-on-quit; remote mounts through sshfs and rclone (<https://github.com/jarun/nnn>).
- "an endless ls-cd loop … please try the type-to-nav mode"
  (<https://news.ycombinator.com/item?id=25126134>)
- An open request that nnn emit OSC 7: <https://github.com/jarun/nnn/issues/1147>

### yazi (Rust, async)

Miller columns, "All I/O operations are asynchronous"; `g ⇒ Space` cds by
an interactive prompt with completion, `z` through fzf, `Z` through zoxide
(<https://yazi-rs.github.io/docs/quick-start>); mouse and drag and drop;
native SFTP since December 2025 (<https://github.com/sxyazi/yazi/pull/3396>).
- "Maintaining user responsiveness feels so nice"
  (<https://news.ycombinator.com/item?id=46030241>)
- "a file overwrite strategy prompt is absent from many modern file
  managers of the day like yazi" (<https://news.ycombinator.com/item?id=45363065>)

### Midnight Commander's hotlist and quick cd

`C-\` shows the directory hotlist, `C-x h` adds to it, `Alt-c` is quick cd;
sftp:// and sh:// panels (<https://source.midnight-commander.org/man/mc.html>).
- "Midnight Commander has directory hotlist (Ctrl-\)."
  (<https://news.ycombinator.com/item?id=10537100>)
- **Latency**: "Entering a directory with 1023 entries … via `sftp://` takes
  about 9 seconds. Listing the same directory with the command line client
  takes 0.7 s … 1023 entries × ~9 ms RTT ≈ 9 s." mc throws away READDIR's
  attributes and stats each entry again
  (<https://github.com/MidnightCommander/mc/issues/5179>).

### termscp

A two-pane local/remote TUI SFTP client with bookmarks
(<https://github.com/veeso/termscp>). No opinions gathered.

## 2. Fuzzy and frecency pickers

### fzf: Ctrl-T and Alt-C

Alt-C walks the tree, filters fuzzily and cds.
- "you type a part of your directory name, hit enter, and it cd's to that
  directory" (<https://news.ycombinator.com/item?id=27995536>)
- It walks the whole tree: "fzf etc. are useful as long as you are not on a
  slow disk" (<https://news.ycombinator.com/item?id=25126134>); "Why is fzf
  control t significantly slower when using fd?"
  (<https://github.com/junegunn/fzf/issues/4089>)

### zoxide, z, autojump (frecency)

`z foo` jumps to the best-ranked match; `zi` picks in fzf.
- "I rarely type 'cd' anymore" (<https://news.ycombinator.com/item?id=49731158>)
- Surprising jumps: "it's very unexpected when I type `z Cat` and zoxide
  takes me to 'duplicates'" (<https://github.com/ajeetdsouza/zoxide/issues/260>);
  "If I do `z blah` and follow it by another quick `z blah` … I value the
  second match higher" (<https://github.com/ajeetdsouza/zoxide/issues/1020>);
  "a heuristic model can 'overlearn' that path"
  (<https://news.ycombinator.com/item?id=47260835>)

### VS Code: Quick Open, and the remote "simple file dialog"

Over Remote-SSH, Open Folder is a quick-pick with an editable path box (Tab
completes), `..`, the folder's entries and an OK button.
- "CTRL+P – shows list of recently opened files and it's a fuzzy search
  dialog – no mouse involved" (<https://news.ycombinator.com/item?id=10974085>)
- No fuzzy filtering, the most-reacted request (#202367, 34): "you get only
  the first item selected that matches … if the list is long then it will
  be at the very bottom" (<https://github.com/microsoft/vscode/issues/202367>)
- Wrong starting folder (#210991, 20): "I hate it! It's one of the stupid,
  annoying things with vsCode." (<https://github.com/microsoft/vscode/issues/210991>)
- No new folder (#71425): <https://github.com/microsoft/vscode/issues/71425>
- "make it more like a standard dialog box"
  (<https://github.com/microsoft/vscode-remote-release/issues/1411>)
- "takes 35 – 40 seconds to open the folder"
  (<https://github.com/microsoft/vscode-remote-release/issues/970>)
- `files.dialog.defaultPath` set locally does nothing remotely
  (<https://github.com/microsoft/vscode/issues/213426>)

### JetBrains: Go to File, Search Everywhere

Fuzzy search over a project index built in advance.
- "These three bindings alone can make any developer 2-3x productive"
  (<https://news.ycombinator.com/item?id=1712719>)
- It needs the index; an un-indexed remote tree has no equivalent
  (inference).

## 3. Remote and SFTP clients

### WinSCP: Commander and Explorer

Commander: local and remote panels; the upload dialog's destination
defaults to the remote panel's folder (<https://winscp.net/eng/docs/ui_copy>).
Explorer: remote only; downloads default to "the last local directory
used". Location profiles pair a local and a remote folder; synchronized
browsing; per-site "Remember last used directory".
- "The Explorer interface is currently used by only about 3% of users"
  (<https://winscp.net/forum/viewtopic.php?p=121606>)
- Remembering cuts both ways: "WinSCP takes me to the last subdirectory … I
  want it to always keep me at root level"
  (<https://winscp.net/forum/viewtopic.php?p=52481>); "I just want to
  ignore my last location if it is outside of what makes sense"
  (<https://winscp.net/forum/viewtopic.php?p=128784>)
- Dragging out of WinSCP needs a shell extension to learn where the drop
  landed (<https://winscp.net/eng/docs/dragext>).

### FileZilla

Local and remote panels each with a tree and a list; Site Manager default
folders; bookmarks; synchronized browsing; drag between panels
(<https://wiki.filezilla-project.org/Using>).
- Ticket #2191 (22 years, critical, 112 comments, unresolved): "We find it
  very dangerous the ability to move folders in the remote pane without
  asking for a confirmation"; "I accidentally dragged a folder into another
  folder while trying to search through folders … I brought down a
  client's site overnight." The maintainer: "Do you have any example of a
  file manager … that asks for a confirmation?"
  (<https://trac.filezilla-project.org/ticket/2191>)
- "someone at my company just messed up our website because of an
  accidentally moved folder … didn't even notice"
  (<https://forum.filezilla-project.org/viewtopic.php?p=144280>)

### Cyberduck and Transmit

Cyberduck: one remote browser per window, bookmarks, upload by drop.
Transmit 5: two panels, a Places bar of favorite folders (dragged onto it
to add), "droplets" that upload into a fixed folder (unverified wording).
- "Transmit is way superior in terms of protocols and speed"
  (<https://news.ycombinator.com/item?id=14799555>)
- "it is not obvious when an drag and drop action has been trigged, we
  won't even notice until server restarts."
  (<https://github.com/iterate-ch/cyberduck/issues/6880>)
- "Critical Linux config files moved to wrong places."
  (<https://github.com/iterate-ch/cyberduck/issues/7364>)
- The opposite: a per-drop prompt "ALL THE TIME … I have to click cancel or
  something on EACH ONE." (<https://github.com/iterate-ch/cyberduck/issues/10580>)

### MobaXterm's SFTP panel ("Follow terminal folder")

Docked left of the SSH tab, with a path box and a "Follow terminal folder"
box: "Follow SSH path (experimental) … will not work on old Unix systems"
(<https://mobaxterm.mobatek.net/documentation.html>).
- The feature users migrate for: "I am migrating from MobaXterm to tabby
  and found that sftp in tabby can't follow terminal folder"
  (<https://github.com/Eugeny/tabby/issues/10481>); Royal TS users asked
  for the same (<https://community.royalapps.com/t/sftp-to-follow-ssh-current-directory/453>).
- Fragile (unverified: Stack Overflow and Superuser wouldn't fetch): stops
  following after a tab switch; breaks when login scripts print; doesn't
  follow across hops.

### Termius

A separate SFTP tab with two panels. On mobile a dropped file goes to
`/tmp` with a unique name and the path is typed into the terminal; "you can
use the SFTP browser to choose a destination directory"
(<https://docs.termius.com/terminal/mobile-terminal>). No default SFTP path
(<https://docs.termius.com/help-center/faq/how-to-set-a-default-sftp-path>).
- "sftp built right into it. honestly, it feels like cheating"
  (<https://news.ycombinator.com/item?id=34073633>)

### Tabby

A popup SFTP panel over the tab, opened in the shell's folder only if the
shell reports it with `OSC 1337;CurrentDir=`.
- Intrusive: "must do some intrusive modification to the ~/.bash_profile"
  (#10481); broken under tmux without passthrough (#5255).
- No path entry: "you can only jump from the root directory level by
  level" (<https://github.com/Eugeny/tabby/issues/5646>).
- Can't be docked: "could the pop-up SFTP window be user customizable as a
  resident window or a separate window?" (<https://github.com/Eugeny/tabby/issues/9630>)
- "this sftp function is almost unusable" (#7154); uploads drop the
  connection (#10616, #10685).

### Terminals that take a drop

- **iTerm2**: Option-drop "will offer to upload the file via scp to the
  remote host into the directory you were in on the line you dropped the
  file on"; "Recent Directories … stored separately for each
  username+hostname combination. It is sorted by 'frecency'"
  (<https://iterm2.com/documentation-shell-integration.html>).
- **kitty `kitten dnd`**: run on the remote end; files land "into the
  current working directory" or `--drop-dest`; Copy and Move drop regions;
  overwrite confirmation "asked only for actual file conflicts"
  (<https://sw.kovidgoyal.net/kitty/kittens/dnd/>).
- **Warp**: an `SshDragAndDrop` flag (unverified).

## Lessons drawn

1. Start at the shell's folder and say where the start came from; fall back
   to the last folder used on that user@host, else home. Every
   follow-the-shell implementation is fragile; puritty owns the terminal and
   reads OSC 7 itself.
2. Recent folders and bookmarks per user@host, as a visible list, not an
   automatic jump (zoxide's surprises, WinSCP's remember-last complaints).
3. A path field with completion that filters the open listing; fuzzy over
   recents, bookmarks and what is listed, never by crawling the host.
4. Listing latency is the thing to engineer: READDIR's attributes, no stat
   per entry, progressive, never blocking keys, cached with a refresh.
5. A drop never moves files and the destination is explicit; ask about
   overwrites only on real conflicts.
6. Mouse and keyboard to the same actions; "go into" separate from
   "choose"; a New folder in the picker.
7. For the later two-panel browser, choose its default destinations
   deliberately (WinSCP's opposite panel; synchronized browsing).

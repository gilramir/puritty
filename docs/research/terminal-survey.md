# Terminal Survey

What developers complain about in today's terminal apps, and what they wish for. Compiled from Reddit/Lemmy threads, GitHub issues, blog posts and review sites (November 2026).

> Most sources are forum opinion, often from Reddit/Lemmy mirrors, and some are a few years old. Treat this as signal, not data.

## What people complain about, by product

### Ghostty
- Search and scrollbars were missing for a long time. Version 1.3 (March 2026) added both, so it's catching up.
- Key bindings are weaker than WezTerm's, with no multi-key sequences.
- Tab titles aren't restored after a restart.
- Startup takes about 250ms, and it pulls in GTK4 and client-side window decorations, which Linux purists dislike.
- **SSH breakage:** remote servers don't know its terminal type (`xterm-ghostty`), so `clear`, vim and others break until you copy the terminfo entry over. This is a very common complaint, and there are many blog posts about fixing it.
- No built-in remote sessions. The usual advice is "if you live on remote servers, keep tmux."

### Alacritty
- No tabs or splits, by design: they leave that to tmux or the window manager.
- No image protocol, so file-manager previews (e.g. Yazi) look pixelated.

### Kitty / WezTerm
- Praised for SSH features: Kitty's `kitten ssh` brings your terminal settings to the remote host, and WezTerm has remote multiplexing.
- Kitty gets called slow in some benchmarks, and Ghostty is said to be behind on images.

### PuTTY
- Clunky session management.
- No built-in file transfer: you close PuTTY, open WinSCP, then reopen PuTTY.
- Looks dated.
- People do praise it for being reliable.

### MobaXterm
- The free tier caps saved sessions (10–12), tunnels and macros.
- The paid license is per person and disliked.
- The X11 server freezes for 5–10 seconds and opens tiny windows.
- SFTP struggles with large files.
- The UI is "garish."

### Windows Terminal (also a competitor)
- GitHub issues ask for:
  - A UI to connect over SSH without first creating a profile.
  - Saved SSH bookmarks.
  - Importing PuTTY sessions.
  - Password storage.
- Microsoft has mostly declined the last two, which leaves room for a competitor.

### Warp (a warning)
- Developers pushed back hard on its mandatory login, telemetry being on by default, and the app being closed source. They dropped the login, but the reputation stuck.

## General wishlist items
- Jump back to the output of an earlier command, and fold long command output.
- Safe paste: pasting several lines shouldn't run them all at once.
- Inline images (Kitty/Sixel protocols).
- Smooth scrolling and animated cursors like Neovide's.
- Horizontal scrolling.
- Closer cooperation between shell and terminal.
- Automatically recover when a program leaves the display garbled with stray escape codes.
- Ctrl+Left and scroll wheel working sensibly (e.g. in `less`).
- Pipe a pane's contents to an external command to pull out URLs or data.
- A loud minority wants it fast and lean: plain-text config you can keep in git, no Electron, quick startup, everything optional, no network features.

## tmux: the biggest opening
- **tmux control mode (`tmux -CC`)**, where tmux windows show up as native tabs and panes, is essentially iTerm2-only on macOS. People keep saying there's nothing comparable on Linux. WezTerm's support was experimental, so check where it stands now. This could be the headline feature.
- **Clipboard over SSH plus nested tmux is a known mess.** Each tmux layer has to pass the clipboard sequence (OSC 52) through, and different settings are involved (`set-clipboard`, `allow-passthrough`). There's an open tmux issue about it. A terminal that makes copy work across local tmux → ssh → remote tmux would stand out.

## Suggested roadmap

### Basics (expected from day one)
- Fast startup and low input lag.
- Correct UTF-8 and true color.
- Search, scrollbar, multi-key bindings.
- Plain-text config you can keep in git.
- Everything can be turned off.
- No login and no telemetry unless the user opts in.

### What sets it apart: SSH and tmux
1. Native tmux control mode on Linux and Windows.
2. No terminfo problems: copy your terminfo to the host automatically, or fall back cleanly to `xterm-256color`.
3. Clipboard that works across nested tmux over SSH.
4. A session manager: bookmarks, quick-connect, import from PuTTY/MobaXterm and `~/.ssh/config`, jump hosts, port-forwarding UI, and keys or passwords kept in the OS credential store.
5. File transfer inside the SSH session: drag-and-drop or an SFTP side panel, no separate tool.
6. Reconnect automatically and restore layouts and tab titles.

### Windows: replacing MobaXterm
- None of MobaXterm's free-tier caps.
- Optional X11 forwarding that doesn't freeze.
- A modern look.
- Proper PowerShell and WSL support.

### Later
- Jump between and fold command outputs (via shell integration).
- Safe paste.
- Inline images.
- Smooth scrolling.
- Pipe a pane to a command.

## Sources
- [Ghostty launch thread, r/linux](https://reddit.birdcat.cafe/r/linux/comments/1hmxpg1/ghostty_terminal_is_out)
- [Ghostty 1.3 UI update (Gigazine)](https://gigazine.net/gsc_news/en/20260404-ghostty-ui)
- [Ghostty review, mvolkmann](https://mvolkmann.github.io/blog/ghostty/)
- [Lemmy Ghostty discussion](https://lemmy.klein.ruhr/post/107550/527144)
- [2025 terminal feature wishlist thread](https://piefed.jeena.net/post/91939)
- [Lemmy wishlist comments](https://lemmy.linuxuserspace.show/post/363787)
- [Fix "unknown terminal xterm-ghostty"](https://travis.media/blog/ghostty-ssh-unknown-terminal-error/)
- [Fixing xterm-ghostty](https://firstfinger.pages.dev/posts/fixing-xterm-ghostty-unknown-terminal-type/)
- [Alacritty (Wikipedia)](https://en.wikipedia.org/wiki/Alacritty)
- [Alacritty lands scrollback](https://jwilm.io/blog/alacritty-lands-scrollback/)
- [iTerm2 tmux integration](https://iterm2.com/documentation-tmux-integration.html)
- [iTerm2 + tmux -CC remote setup](https://dev.to/evoleinik/iterm2-tmux-cc-the-remote-development-setup-nobody-talks-about-4p89)
- [Which terminals support tmux control mode (Unix SE)](https://backiee.wasmer.app/https_unix_stackexchange_com/questions/189805/what-terminal-emulators-support-tmux-control-mode)
- [tmux issue #4275 (OSC 52)](https://github.com/tmux/tmux/issues/4275)
- [Linuxfabrik tmux docs](https://docs.linuxfabrik.ch/lfops/tmux.html)
- [Byobu/tmux clipboard over SSH](https://www.zonca.dev/posts/2026-04-13-opencode-byobu-clipboard)
- [Linux terminal shootout 2026](https://linuxjunkies.org/guides/terminal-emulator-shootout)
- [Best terminal for Mac 2026](https://dev.to/vibehackers/best-terminal-for-mac-in-2026-ghostty-kitty-wezterm-alacritty-warp-more-4pe6)
- [WezTerm overview](https://www.linuxlinks.com/wezterm-gpu-accelerated-cross-platform-terminal-emulator-multiplexer)
- [PuTTY alternatives 2026 guide](https://dev.to/daxesh/putty-alternatives-for-windows-the-2026-guide-for-developers-whove-outgrown-classic-ssh-b7g)
- [HN PuTTY thread](https://igor.root.sx/item?id=2758491)
- [MobaXterm reviews (G2)](https://www.g2.com/products/mobaxterm/reviews)
- [MobaXterm tiny X11 window](https://tekstream.com/blog/mobaxterm-resolving-tiny-x11-window)
- [MobaXterm freezes, r/mobaxterm](https://reddit.birdcat.cafe/r/mobaxterm/comments/tc6fkk/how_to_troubleshoot_random_freezes_in_ssh_and)
- [MobaXterm free-version limits (iThome)](https://ithelp.ithome.com.tw/articles/10400283)
- [MobaXterm alternatives](https://alternativeto.net/software/mobaxterm)
- [Windows Terminal #13327 SSH UI](https://www.github.com/microsoft/terminal/issues/13327)
- [Windows Terminal #2085 bookmarks](https://github.com/microsoft/terminal/issues/2085)
- [Windows Terminal #10943 PuTTY import](https://github.com/microsoft/terminal/issues/10943)
- [Windows Terminal #11034 passwords](https://www.github.com/microsoft/terminal/issues/11034)
- [Warp drops login requirement](https://warp.dev/blog/lifting-login-requirement)
- [It's FOSS on Warp](https://itsfoss.com/news/warp-terminal-no-login/)
- [HN Warp thread](https://hn.jakechampion.name/item/42247583)

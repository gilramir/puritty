+++
title = "puritty"

[extra]
headline = "A terminal that's fast, and just does things right"
lede = "puritty runs on Linux and Windows. It draws tmux's panes as its own, carries its own ssh client, and is just as quick when it runs on another machine and draws on your desktop."
status = "**Pre-release.** puritty is its author's daily terminal. It will be published with the first alpha of [Geng](https://geng-lang.org), the language it is written in; until then you build it from source."
hero_image = "tmux-on-windows.png"
hero_alt = "puritty on Windows 11, connected to a Linux host with its built-in ssh client, showing tmux 3.8 in control mode: three tiled panes and a floating pane over them"
hero_caption = "On Windows 11, connected to Linux with puritty's own ssh client, running `tmux -CC attach`: tmux's tiled panes and a floating pane, drawn by puritty."

[[extra.features]]
kicker = "tmux, natively"
title = "tmux's panes become puritty's own"
body = """
Run `tmux -CC` and puritty draws tmux's panes itself, each a terminal of
its own, with tmux 3.8's **floating and modal panes** in boxes over the
tiled ones. What you type goes to the active pane; resize the window and
tmux lays its panes out again.

The session lives on the server. Close the window or lose the connection,
run `tmux -CC attach` again, and the same panes come back. Until now only
iTerm2 on macOS did this well.
"""
link = "@/guide/tmux.md"
link_text = "tmux in puritty"

[[extra.features]]
kicker = "Remote X11"
title = "Fast when it runs on another machine"
body = """
GPU terminals draw every frame with OpenGL. Run one on a remote host and
the whole window crosses the network as pixels, about **4.9 MB a frame**.

puritty has a renderer of its own for X11. It sends the X server text and
small instructions, only what changed, and moves scrolled text with one
copy on the server. Measured over `ssh -X`:

| what you're doing | what crosses the network |
|---|---|
| scrolling in vim | about 500 bytes a line |
| `tail -f` on a log | about 420 bytes a line |
| `htop` updating | about 8–10 KB a second |
"""

[[extra.features]]
kicker = "Every script"
title = "Korean, Chinese, Japanese and Thai, done properly"
body = """
- **Input methods work**, drawn at the cursor as you compose, tested over
  six IME setups: fcitx5-hangul, ibus-hangul, Mozc and pinyin among them.
- **Wide characters and grapheme clusters** take the cells they should,
  and copy back out as the characters you see.
- **Thai is shaped**, and **Han characters** take your language's
  regional forms.
- **EUC-KR and CP949 are built in**, both ways, for the hosts that still
  run `ko_KR.euckr`. No `luit`, no wrapper.
"""
image = "multilingual.png"
alt = "puritty showing file names, a table and git commit messages in Korean, Japanese, Chinese and Thai, with every column lined up"

[[extra.features]]
kicker = "Windows"
title = "An ssh terminal with the client built in"
body = """
On Windows puritty opens a list of your hosts, from its settings and your
`~/.ssh/config`, with a quick-connect field. Its own ssh client talks to
the host directly: no OpenSSH and no console layer between them.

It checks host keys against `known_hosts`, uses your keys, the Windows ssh
agent or Pageant, asks for a passphrase or a password in the window, and
goes through jump hosts. A selection is copied to the clipboard as you
make it, as in PuTTY.
"""
link = "@/guide/settings.md"
link_text = "Hosts in the settings"

[[extra.features]]
kicker = "Correct, and checked"
title = "Written in a memory-safe language with compile-time constraint checking"
body = """
The terminal core is tested against libghostty-vt on recorded sessions,
fuzzed, and run against the `esctest2` conformance suite, where it passes
392 of 567 tests; Ghostty 1.4 passes 388. Every buffer a remote program can
fill has a limit.

puritty is written in [Geng](https://geng-lang.org), whose compiler proves
array and byte reads in range before it builds the program.
"""
image = "geng-code.png"
alt = "puritty's EUC-KR decoder, written in Geng, shown in an editor"

[[extra.small]]
title = "Copy and paste that make sense"
body = "Double-click a word, triple-click a line. A wrapped line copies back as one. Hold Shift to select in programs that take the mouse."

[[extra.small]]
title = "No terminfo to copy"
body = "`TERM=xterm-256color`, which every host knows, so ssh to a fresh server just works."

[[extra.small]]
title = "Settings, live"
body = "Edit `config.toml` or use the settings window: every open window takes a change at once, and your comments stay."

[[extra.small]]
title = "Jump between prompts"
body = "Ctrl+Shift+Up and Down move between shell prompts, for shells that mark them."

[[extra.small]]
title = "Paste safely"
body = "Bracketed paste, so a block of commands pasted into a shell waits for you."

[[extra.small]]
title = "Your clipboard is yours"
body = "Remote programs can copy to it with OSC 52. Reading it is denied unless you allow it."
+++

## Try it

puritty is pre-release and built from source for now.
[Getting started](@/guide/getting-started.md) says how, and the
[roadmap](@/roadmap.md) what comes next.

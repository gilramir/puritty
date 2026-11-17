+++
title = "puritty"

[extra]
headline = "A terminal that's fast, and just does things right"
lede = "puritty runs on Linux and Windows. It has deep integration with tmux, carries its own ssh client on Windows, and is quick on the desktop and over remote X11."
status = "**0.1.0.** puritty is its author's daily terminal. It is published now in source and binary form, but nobody but the author can build it until [Geng](https://geng-lang.org), the language it is written in, is published."
hero_image = "tmux-on-windows.png"
hero_alt = "puritty on Windows 11 with three colored tabs, the first connected to Linux with puritty's own ssh client and attached to tmux 3.8 by tmux -CC: git history in the left pane, two Chinese poems and a table in the right one, and Thai in a floating pane over them"
hero_caption = "On Windows 11, connected to Linux with puritty's own ssh client, running `tmux -CC attach`: tmux's panes and a floating pane, with Chinese and Thai, drawn by puritty, and three tabs of puritty's own."

[[extra.features]]
kicker = "tmux, natively"
title = "tmux's panes are managed by puritty"
body = """
Run `tmux -CC` and puritty draws tmux's panes itself, each a full terminal
of its own, with tmux 3.8's **floating and modal panes** in boxes over the
tiled ones and tmux's windows as tabs. You can move and resize panes with your mouse.
Your prefix and key bindings work
as in tmux, and tmux's own screens (its prompts, menus, session tree,
copy mode, even its options editor) are drawn by puritty too.

The session lives on the server. Close the window or lose the connection,
run `tmux -CC attach` again, and the same panes come back. Until now only
iTerm2 on macOS did this well.
"""
link = "@/guide/tmux.md"
link_text = "tmux in puritty"
image = "tmux-panes.png"
alt = "puritty attached to tmux 3.8 with tmux -CC, in Ghostty's colors: two panes side by side, English in bold, italic, curly, dotted and dashed underlines and 24-bit color on the left, a Korean poem and table on the right, a floating pane of git history over both, and tmux's windows as tabs"

[[extra.features]]
kicker = "Remote X11"
title = "Fast when it runs over remote X11"
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
title = "Thai, Korean, Chinese, and Japanese, done properly"
body = """
- **Input methods work**, drawn at the cursor as you compose, tested over
  six IME setups: fcitx5-hangul, ibus-hangul, Mozc and pinyin among them.
- **Wide characters and grapheme clusters** take the cells they should,
  and copy back out as the characters you see.
- **Thai's vowel and tone marks stay with their letters.** What a Thai
  reader sees as one character is often several pieces stacked together:
  a consonant, a vowel mark above or below it, and a tone mark on top.
  puritty draws it as it's meant to look.
- **Han characters** take your language's regional forms. Some Han
  characters are drawn differently in Simplified Chinese, Traditional
  Chinese, Japanese and Korean, and puritty draws the forms your language
  expects.
- **EUC-KR and CP949 are built in**, both ways, for the hosts that still
  run `ko_KR.euckr`. No `luit`, no wrapper.
"""
image = "multilingual.png"
alt = "puritty showing file names, a table and git commit messages in Korean, Japanese, Chinese and Thai, with every column lined up"

[[extra.features]]
kicker = "Windows"
title = "A terminal with the ssh client built in"
body = """
On Windows puritty opens a list of your hosts, from its settings and your
`~/.ssh/config`, with a quick-connect field. The connections you made last
come first, and quick connect takes a command to run, as `ssh` does. Its
own ssh client talks to the host directly: no OpenSSH and no console layer
between them. But you can still open a local shell if you want.

It checks host keys against `known_hosts`, uses your keys, the Windows ssh
agent or Pageant, asks for a passphrase or a password in the window, and
goes through jump hosts. A selection is copied to the clipboard as you
make it, as in PuTTY.
"""
link = "@/guide/settings.md"
link_text = "Hosts in the settings"
image = "host-list.png"
alt = "puritty's host list: a quick-connect field with the example user@host:port command, New connection, two recent connections, two saved hosts (one through a jump host, one running tmux -CC attach) and two hosts from ~/.ssh/config"

[[extra.features]]
kicker = "Correct, and checked"
title = "Written in a memory-safe language with compile-time constraint checking"
body = """
The terminal core is tested against libghostty-vt on recorded sessions,
fuzzed, and run against the `esctest2` conformance suite, where it passes
410 of 567 tests; Ghostty 1.4 passes 388. Every buffer a remote program can
fill has a limit.

puritty is written in [Geng](https://geng-lang.org), whose compiler proves
array and byte reads in range before it builds the program. 88% of
puritty's own code is Geng; the C is a thin layer (6,400 lines) for the
window, text drawing and ssh crypto.
"""
image = "geng-code.png"
alt = "puritty's EUC-KR decoder, written in Geng, shown in an editor"

[extra.nostalgia]
title = "A nod to nostalgia"
body = """
The phosphor screens of early terminals are two color schemes away:
`green-screen` and `amber-screen`. And the bell can sound like the
computers many of us learned on, each worked out from its ROM:
"""
caption = "`CHRGET`, the routine that hands Microsoft BASIC for the 6502 each character of your program, from version 1.1 (1978). © Microsoft Corporation, [MIT License](https://github.com/microsoft/BASIC-M6502)."
after = "Pick one in Settings → Sound, or use a WAV file of your own."

[[extra.nostalgia.shots]]
image = "green-screen.png"
alt = "puritty in the green-screen color scheme, bright green text on black: cat chrget.asm, a 6502 assembly routine from Microsoft BASIC with its comments"

[[extra.nostalgia.shots]]
image = "amber-screen.png"
alt = "The same listing in the amber-screen color scheme, amber text on black"

[[extra.nostalgia.bells]]
name = "Apple II"
detail = "934.5 Hz for 0.103 s, from the Monitor ROM's `BELL1`"
file = "apple2.wav"

[[extra.nostalgia.bells]]
name = "IBM PC AT"
detail = "896 Hz for 0.218 s, from the 1984 BIOS"
file = "ibm-pc.wav"

[[extra.nostalgia.bells]]
name = "Atari ST"
detail = "the \"ping\", 2,404 Hz fading over 0.52 s, from TOS"
file = "atari-st.wav"

[[extra.nostalgia.bells]]
name = "BBC Micro"
detail = "516 Hz for 0.3 s, from the MOS's bell settings"
file = "bbc-micro.wav"

[[extra.nostalgia.bells]]
name = "X11"
detail = "400 Hz for 0.1 s, X's default bell"
file = "x11.wav"

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

puritty 0.1.0 is out for Windows and Linux:
[download it](https://github.com/gilramir/puritty/releases/latest) from
GitHub. [Getting started](@/guide/getting-started.md) says which file to
take, and the [roadmap](@/roadmap.md) what comes next.

Why is it called puritty? Because it's written in
[Geng](https://geng-lang.org), which is a pure functional programming
language.

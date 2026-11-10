# puritty

**A terminal for Linux that stays fast when it runs on another machine, gets
Korean, Chinese, Japanese and Thai right, and gets out of your way.**

![puritty showing file names, a table and git commit messages in Korean, Japanese, Chinese and Thai, with every column lined up](docs/images/multilingual.png)

Most new terminals are built for one case: a local GPU, a local shell, UTF-8
everywhere. puritty is built for that case too, and for the ones they leave
behind: the terminal running on a remote host and drawn on your desktop over
`ssh -X` or a remote X session, the server whose locale is still EUC-KR, and
the IME that has to work the first time.

> **Status:** puritty is pre-release. It is its author's daily terminal on
> Linux Mint, and it will be published alongside the first alpha of
> [Geng](https://geng-lang.org), the language it is written in.
> Until then, building it needs the Geng toolchain (see
> [Building](#building)).

---

## Why puritty

### It is fast over remote X11

GPU terminals such as Alacritty, Ghostty and WezTerm draw every frame with
OpenGL. When they run on a remote host, that drawing happens on the remote
CPU and the whole window goes over the network as pixels: about **4.9 MB a
frame** for an ordinary window.

puritty has a renderer of its own for X11. It sends the X server text and
small instructions, not pictures. It keeps its own copy of the screen, sends
only what changed, and moves scrolled text with one copy on the server
instead of redrawing it. It never waits on a reply from the server while
drawing. Measured over `ssh -X`:

| what you're doing | what crosses the network |
|---|---|
| scrolling in vim | about 500 bytes a line |
| `tail -f` on a log | about 420 bytes a line |
| `htop` updating | about 8–10 KB a second |

That is level with classic core-font xterm, but with modern font
rendering, wide characters, true colour and a modern feature set.
Remote X11 is a main path in puritty, not an afterthought.

### Korean, Chinese, Japanese and Thai, done properly

- **Input methods work.** puritty talks XIM directly, draws the text you are
  still composing at the cursor, and has a scripted test suite over six IME
  setups, among them fcitx5-hangul, ibus-hangul, Mozc and a pinyin IME.
- **Wide characters and grapheme clusters** take the cells they should,
  using the same Unicode width tables as Ghostty, and copy back out as
  the characters you see, not doubled.
- **Thai** is shaped, and **Han characters** are drawn in the regional forms
  for your language: set `language = "ja"` (or `ko`, `zh-CN`, ...) and the
  fallback fonts follow it. Left out, it is your locale's on Linux, and on
  Windows the first language in Settings' Language & region.
- **EUC-KR and CP949 are built in.** If you log in to hosts that still run
  `ko_KR.euckr`, set `charset = "euc-kr"` and puritty converts in both
  directions. You don't need `luit` or a wrapper script.

### Correct, and checked

The terminal core is tested against libghostty-vt on recorded sessions,
fuzzed, and run against the `esctest2` conformance suite, where it passes
386 of 567 tests (Ghostty 1.4 passes 388). Every buffer a remote program can
fill has a limit. puritty is written in Geng, a memory-safe language whose
compiler proves array and byte reads in range before it builds the program.

![puritty's EUC-KR decoder, written in Geng, shown in an editor](docs/images/geng-code.png)

### Copy and paste that make sense

- Select with the mouse, double-click for a word, triple-click for a line,
  and choose for yourself which characters end a word.
- Middle-click (or right-click, PuTTY style) pastes the selection.
  Ctrl+Shift+C and Ctrl+Shift+V use the clipboard.
- A wrapped line copies back as one line, without trailing spaces.
- Programs that take the mouse (nvim, tmux, htop) keep it. Hold **Shift** to
  select anyway.
- Remote programs can copy to your clipboard with OSC 52, so a copy in tmux
  on a server reaches your desktop. Reading your clipboard is **denied** by
  default.

A full guide is in [`docs/user/copy-and-paste.md`](docs/user/copy-and-paste.md).

### Small things that add up

- **No terminfo to copy around.** puritty sets `TERM=xterm-256color`, which
  every host already knows, so ssh to a fresh server just works.
- **Scrollback** with the wheel or Shift+PgUp/PgDn, and **jump between shell
  prompts** with Ctrl+Shift+Up/Down (for shells that mark them with OSC 133).
- **Zoom** with Ctrl and the wheel, or Ctrl+=, Ctrl+− and Ctrl+0. The
  starting size comes from your screen's DPI, so text isn't tiny on a large
  monitor.
- **Bracketed paste**, so pasting a block of commands into a shell doesn't
  run them before you look.
- **Synchronized output** (mode 2026), so full-screen programs redraw without
  tearing.
- **No account, no login, no telemetry.** It is a terminal.

---

## Using it

```sh
puritty                         # your $SHELL in a new window (on Windows,
                                #   PowerShell 7, else Windows PowerShell, else cmd)
puritty -- htop                 # any program
puritty --title notes -- vim -O a.txt b.txt
puritty --config ~/work.toml    # another settings file
```

### Settings

puritty reads `~/.config/puritty/config.toml` (on Windows
`%APPDATA%\puritty\config.toml`). Every key is optional. A key
puritty doesn't know is reported rather than silently ignored, so a typo
doesn't leave you wondering why nothing changed.

```toml
[window]
columns = 120
rows = 36

[font]
family = "Fira Code"        # as fontconfig names it; DejaVu Sans Mono
                            # when left out, Cascadia Mono on Windows
size = 11                   # points
language = "ko"             # which regional forms fallback fonts use

[colours]
foreground = "#c5c8c6"
background = "#1d1f21"
palette = ["#1d1f21", "#cc6666", "#b5bd68", "#f0c674"]   # the 16 named colours, from 0

[terminal]
charset = "utf-8"           # or "euc-kr", "cp949"

[scrollback]
lines = 25000

[selection]
word_boundaries = " \t'\"│`|:;,()[]{}<>$"

[mouse]
paste_button = "middle"     # or "right"

[clipboard]
osc52_read = "deny"         # or "allow"
```

---

## What's coming

In roughly this order:

1. **A settings window**, opened with Ctrl+Comma. Every change applies to the
   running terminal at once, and your hand-edited `config.toml` keeps its
   comments and layout.
2. **Key sounds**, an optional typewriter click as you type.
3. **tmux control mode** (`tmux -CC`): tmux windows and panes become native
   tabs and splits, including tmux 3.8's floating panes. Only iTerm2 on macOS
   does this well today. puritty brings it to Linux.
4. **Inline images**: Sixel, Kitty graphics and iTerm2 images.
5. **Scrollback search** and a scrollbar, and **key bindings** in the config.
6. **A GPU renderer** for local desktops, beside the X11 one.
7. **RHEL 8**, built against its older libraries.
8. **Windows**, as an SSH terminal with the SSH client built in: a host list
   with groups, import from `~/.ssh/config`, PuTTY and MobaXterm, and
   passwords kept in the Windows credential store.

---

## Building

puritty is a Geng program with a small amount of C for X11, fonts and the
input method. Until Geng's first release, a build needs a
[geng-lang](https://github.com/geng-language/geng) checkout with its
compiler built, and the libraries in this repository's `devbox.json`
(libxcb, xkbcommon, FreeType, HarfBuzz, fontconfig). From the repository:

```sh
devbox shell
app/build.sh        # writes app/puritty
```

`app/release.sh` builds the same program for a release: it trains a
profile of the terminal core on the benchmark inputs first and compiles
with it, which makes the core 5% to 25% faster
([`docs/vt-core.md`](docs/vt-core.md) §VC54, §VC56). It needs the
benchmark inputs in `.harness-work/perf/inputs` (`harness/perf.py
--inputs DIR`) and takes a few minutes more; day-to-day builds use
`app/build.sh`.

It runs on Linux under X11, locally or over `ssh -X`.

---

## Acknowledgements

puritty learned from the terminals that came before it. Its design started
from close readings of Alacritty, Ghostty, WezTerm, Windows Terminal and
PuTTY (see [`docs/`](docs/)). Its key encoder, mouse encoder and Unicode
widths follow Ghostty's, and libghostty-vt is the reference its core is
tested against.

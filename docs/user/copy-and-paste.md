# Copy and paste in visiterm

*Status: this guide describes phase 3's design as decided on 2026-11-03
([`../phase3-select.md`](../phase3-select.md) §10–§11), and all of it is
built (§12–§16 there).*

Copy and paste in a terminal on Linux is confusing because there are **two
clipboards**, not one, and because the programs running inside the terminal
can want the mouse and the clipboard for themselves. This guide explains
each piece and then gives a quick reference at the end.

---

## 1. The two clipboards

X, the window system visiterm runs on, has two places text can be copied
to. Every X program shares them.

| | **the selection** (X calls it PRIMARY) | **the clipboard** (X calls it CLIPBOARD) |
|---|---|---|
| how text gets there | **just by selecting it**. No key needed | an explicit copy: Ctrl+Shift+C in visiterm, Ctrl+C in most other programs |
| how you paste it | the **middle mouse button** (or the right one, if you choose, §3), or Shift+Insert | Ctrl+Shift+V in visiterm, Ctrl+V in most other programs |
| what replaces it | selecting anything else, in any program | the next copy, in any program |
| what it is for | quick copying of something you can see | the copy-and-paste you know from other systems |

They are independent. Selecting text does not change the clipboard, and a
Ctrl+Shift+C does not change the selection. So you can keep something on
the clipboard for later while you select and middle-click other things.

**Why Ctrl+Shift, not Ctrl?** In a terminal, Ctrl+C interrupts the running
program and Ctrl+V tells the shell to take the next key literally. visiterm
must pass those to the program, so its own copy and paste keys add Shift,
as most Linux terminals do.

**When visiterm exits.** X keeps no copy of either one: the text stays in
the program it was copied from, which hands it over when someone pastes.
When visiterm closes, what it put in the selection is gone. Most desktops,
Mint's among them, run a clipboard manager that keeps the *clipboard* after
its program exits; nothing keeps the *selection*.

---

## 2. Selecting text

- **Drag** with the left button to select from one point to another.
- **Double-click** to select a word, **triple-click** to select a line.
  Keep the button down after a double or triple click and drag to select
  more words or lines. (Thai text has no spaces between words; until
  visiterm learns Thai word breaks, a run of Thai is selected as one word.)
- To select into the history that has scrolled away, scroll back first
  (the wheel, Shift+PgUp, Shift+Home). A selection can also span more than
  a screen: press the button, move the view with Shift+PgUp, Shift+PgDn,
  Shift+Home or Shift+End while holding it, and let go where it ends.
  Dragging past the window's edge does not scroll the view yet.

### What counts as a word

A word is a run of characters that are all *word boundaries* or all not.
The boundaries are tab, space and ``'"│`|:;,()[]{}<>$`` (Ghostty's list),
so a double click on `path/to/file.txt` takes all of it, on `a=b` all three
characters, and on `===` the three `=`. Everyone draws this line
differently, so it is yours to set in `~/.config/visiterm/config.toml`:

```toml
[selection]
# the default, with "=" added: a double click on a=b now takes "a" or "b"
word_boundaries = " \t'\"│`|:;,()[]{}<>$="
```

Write the whole list: the setting replaces the default rather than adding
to it.

What you selected goes into the selection (PRIMARY) **when you let go of the
button**. visiterm reads the text out then:

- a long line the terminal wrapped onto several rows is copied as one line;
- spaces at the end of each line are left out;
- a wide character (Chinese, Japanese, Korean) is copied once, not twice.

**What happens to the highlight.** It stays while you scroll. It goes away
when the program writes over the selected rows, when the window is
resized, or when you select something in another program. The text you
copied stays copied: a middle-click still pastes what you selected, even
after the screen has changed.

### When a program has the mouse

Some programs ask the terminal for the mouse: **nvim** does by default,
**tmux** does with `set -g mouse on`, and so do htop, mc and many others.
Then a click or drag goes to the program, not to visiterm. tmux selects into
its own copy buffer, nvim moves its cursor or starts a visual selection.

**Hold Shift** to make visiterm select instead, whatever the program wants.
Shift+drag, Shift+double-click and Shift+triple-click work as above.

---

## 3. Pasting

| keys | pastes |
|---|---|
| middle button | the selection (PRIMARY) |
| Shift+Insert | the selection (PRIMARY) |
| Ctrl+Shift+V | the clipboard (CLIPBOARD) |

**Middle or right button.** xterm and most Linux programs paste with the
middle button; PuTTY pastes with the right one. Choose in
`~/.config/visiterm/config.toml`:

```toml
[mouse]
paste_button = "right"    # the default is "middle"
```

The other button does nothing. When a program has the mouse (nvim, tmux
with `mouse on`), the paste button goes to the program; hold Shift to
paste with it anyway.

visiterm sends the pasted text to the program as if typed, with three
changes, the same ones xterm makes:

1. **Control characters that could act are turned into spaces**: NUL,
   backspace, ESC, delete, and the keys that interrupt, suspend or edit a
   line (Ctrl+C, Ctrl+Z, Ctrl+\\, Ctrl+U, Ctrl+W and a few more). A paste
   cannot send a signal or an escape sequence.
2. **If the program asked for bracketed paste**, the text is wrapped in
   markers that tell it "this was pasted, not typed". Shells (bash 5.1 and
   later, zsh, fish), vim, nvim and most editors ask for it. A shell then
   puts a multi-line paste on its command line **without running it** until
   you press Enter.
3. **If it did not ask**, each newline is sent as Enter.

> **Careful:** visiterm does not ask before a paste. Pasting several lines
> into a program that has not asked for bracketed paste (an old shell, a
> shell with it turned off, `cat`, some remote shells) runs each line as you
> paste it, exactly as if you had typed it with Enter after each.

Large pastes work: the text goes to the program as fast as it reads it,
and the window keeps drawing meanwhile. 10 MB takes a fraction of a second
into an editor or shell, about a second into a plain `cat`, and about a
second more to arrive over `ssh -X`.

**A pane set to EUC-KR or CP949** sends a paste in that character set, as it
does typed text. A character the set does not have is sent as `?`.

---

## 4. Programs that copy for you: OSC 52

A program inside the terminal can put text on your clipboard by sending the
terminal an escape sequence, OSC 52. This is how copying works **from a
remote machine over ssh**, where the program cannot reach your X display:

- **tmux**: with `set -g set-clipboard on`, anything copied in tmux's copy
  mode lands on your clipboard.
- **nvim 0.10 and later**: `"+y` copies to your clipboard through OSC 52
  when nvim has no other clipboard (over ssh, for instance).
- other programs and scripts that say they support OSC 52.

visiterm puts it on **the clipboard** (CLIPBOARD), unless the program asks
for the selection (PRIMARY) instead. Paste it with Ctrl+Shift+V as usual.
Up to about 6 MB of text is taken; a larger copy is ignored.

### Reading the clipboard is off

OSC 52 can also *ask* the terminal for your clipboard, and the terminal
answers by typing it to the program. visiterm **does not answer**, because
the question can come from anything that prints to your screen: a remote
server you are logged in to, or a file you `cat`. If you had just copied a
password, the asker would get it. Alacritty, WezTerm and Windows Terminal
do the same.

What this costs: nvim's `"+p` and tmux's `get-clipboard` cannot read your
clipboard through the terminal. Paste with Ctrl+Shift+V instead; nvim and
tmux receive it as a bracketed paste. If you want programs to read it
anyway, set:

```toml
[clipboard]
osc52_read = "allow"
```

visiterm never asks you about it either way.

---

## 5. With tmux and nvim

| you want to | in tmux with `mouse on` | in nvim |
|---|---|---|
| select on screen for a middle-click paste elsewhere | Shift+drag | Shift+drag |
| copy to the clipboard | Shift+drag, then Ctrl+Shift+C; or tmux's copy mode with `set-clipboard on` | Shift+drag, then Ctrl+Shift+C; or `"+y` (nvim 0.10+ over ssh through OSC 52, or locally through xclip or xsel) |
| paste the clipboard | Ctrl+Shift+V | Ctrl+Shift+V (in insert mode it arrives as a bracketed paste) |
| paste the selection | Shift+middle button (tmux takes the middle button itself), or Shift+Insert | Shift+middle button (nvim takes the middle button itself), or Shift+Insert |

A Shift+drag in tmux selects what is on visiterm's screen. That includes
tmux's status line and the borders of other panes, because visiterm does
not know about tmux's panes. To select within one pane, use tmux's own copy
mode.

---

## 6. Quick reference

| action | how |
|---|---|
| select | drag; double-click a word; triple-click a line |
| select when a program has the mouse | hold Shift |
| copy the selection to the clipboard | Ctrl+Shift+C |
| paste the clipboard | Ctrl+Shift+V |
| paste the selection | middle button (or right, `[mouse] paste_button`), or Shift+Insert |
| let programs read the clipboard | `[clipboard] osc52_read = "allow"` (off by default) |

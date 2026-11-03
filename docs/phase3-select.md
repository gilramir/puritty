# Phase 3 · Mouse, selection, clipboard, OSC 52, paste: a survey

Status: **survey begun 2026-11-03**, for Gilbert's answers (§10); every
leaning taken the same day (§11); a user's guide in
[`user/copy-and-paste.md`](user/copy-and-paste.md). Built: mouse reports
(§12), scrolling back (§13). It is the
rest of phase 3 of [`geng-plan.md`](geng-plan.md) §6 after
[`phase3-input.md`](phase3-input.md)'s keys, IME, writes, font size and
EUC-KR (V44–V50), and it measures before building, as every phase does. It
asks: what scrolling back through history costs, which the plan never named
and daily use needs (§3); what a mouse report needs (§4); what the X
selections cost here and over `ssh -X` (§5); what a paste costs through a
pty (§6); what an OSC 52 costs the core (§7); and whether Ctrl with the
mouse wheel should zoom, as Gilbert asked on 2026-11-03 (§8). As with every
survey here, these sections stay as written when the work lands below them.

---

## 1. What was asked, and what was found

| asked | found | § |
|---|---|---|
| Can the window show the scrollback? | **No: nothing in visiterm scrolls back**, and the plan's phase 3 list does not name it. The wheel is how it is done, so it belongs with the mouse. The rows are there: the core's ring holds recent ones, and D901's pages the rest. Reading the whole scrollback (94,095 rows) as text takes 544 ms, 5.8 µs a row, so a screen in the oldest pages costs at most two 1,024-row pages, about 12 ms, once | 3 |
| What does a mouse report need? | Ghostty's encoder is 290 lines before its tests, and libghostty-vt has it behind a C API, so a gate like the key gate's can hold a Geng port to it. The core already keeps modes 1000–1016 and 1007 | 4 |
| What do the X selections cost? | **Locally nothing: 10 MB pasted in 2.6 ms, served in 19 ms. Over `ssh -X` from gmktec7, a 10 MB paste takes 1.1 s and a copy 0.24–1.0 s by piece size.** One blocking `GetProperty` of a 1 MB piece holds the caller for about 100 ms there, so the transfer has to run in the loop, not in a call | 5 |
| What does a paste cost through a pty? | **10 MB into a raw program (a shell's line editor, vim) in 12–21 ms; into cooked `cat`, 1.0–1.3 s**, the line discipline's own speed, which V48's queue already rides out. Ghostty's paste rules (unsafe controls to spaces, brackets, CR for LF) are in libghostty-vt too, for the same gate | 6 |
| What does an OSC 52 cost? | **tmux 3.4 sends a copy as one OSC 52, unlimited: 4 MB of text is 5.3 MB of base64.** The core keeps 4,096 bytes of a string and drops the rest, at 9 ms for those 5.3 MB. Ghostty keeps OSC 52 up to 8 MB. Base64 in Geng on `Bytes.Builder` decodes 5.3 MB in 10.4 ms, so nothing is needed from geng-lang | 7 |
| Should Ctrl and the wheel zoom? | **Of the five terminals vendored here, only Windows Terminal does, and only when no program has taken the mouse.** nvim 0.9.5 takes the mouse by default (`mouse=nvi`), so under that rule the zoom is dead in nvim. Neither nvim nor tmux 3.4 binds anything to Ctrl and the wheel, so visiterm taking it always costs programs nothing they do by default | 8 |

---

## 2. How it was measured

This machine (`nene`), AMD Ryzen 7 8845HS, Linux 6.8, visiterm `d63beab`,
geng-lang `7fd24703`, devbox's clang at `-O2`. gmktec7 for `ssh -X`, 4.7 ms
ping. No other load.

- [`../probes/select/`](../probes/select/): `sel`, an X selection client
  in xcb as visiterm's would be: `sel get SELECTION TARGET` asks for a
  selection and reads it, `INCR` included; `sel own SELECTION FILE` owns
  one and answers `TARGETS`, `UTF8_STRING`, `STRING`, `TEXT` and
  `text/plain;charset=utf-8`, in `INCR` pieces of `CHUNK` bytes when the
  text is larger. `run.sh` starts its own Xvfb (`:81`) and times both
  directions against the system's xclip at 1 KB, 1 MB and 10 MB of
  `gitlog.txt`; `REMOTE=HOST` runs `sel` there over `ssh -X`.
- [`../probes/paste/paste.py`](../probes/paste/paste.py): SIZE bytes of
  text written to a pty's master in non-blocking writes, the master read
  all the while, as visiterm's loop does since V48.
- [`../probes/paste/osc52.py`](../probes/paste/osc52.py): tmux on a pty
  with `set-clipboard on`; `load-buffer -w` of SIZE bytes; the OSC 52 read
  back from the master.
- [`../probes/base64/`](../probes/base64/): a base64 decoder in Geng into a
  `Bytes.Builder` (geng-lang D1050), timed ten times over a 5.3 MB input.
- `harness/bench/core-bench` (`vt-core.md` §VC7) for the scrollback's read
  and the core's time on an OSC 52.

---

## 3. Scrolling back

`app/src/Main.geng` draws the core's live screen and nothing else: there is
no offset into the history, and no key or wheel moves one. `geng-plan.md`'s
phase 3 list (keys, mouse 1006/1016, selection, OSC 52, paste, XIM,
EUC-KR) does not name it either. Every terminal Gilbert has used scrolls
back with the wheel, and selection (§5) has to reach rows above the screen,
so it is surveyed here.

The rows are in two places (`Vt.geng`'s header, §VC6): the ring, which
holds the screen and the recent scrollback in cells, and D901's pages, the
older rows packed 1,024 to a page. A row in the ring is read as the screen
is. A row in a page is read by decoding its page (`Vt.Pages.pageRowsOf`,
the read `Vt.dump` and the reflow use).

What a decode costs, from `core-bench gitlog.txt drag 0 160 50`, which fills
the default scrollback (25,000 rows' worth at 160 columns) and then reads
all of it with `Vt.dump`:

| rows in the scrollback | the whole read | per row | a 1,024-row page |
|---|---|---|---|
| 94,095 | 544 ms | 5.8 µs | ~6 ms |

The dump formats every row as text, so this is an upper bound on the
decode. A screen of 50 rows straddles at most two pages, so the first
frame shown from deep in the history costs at most about 12 ms, and a
frame after it nothing more if the view keeps the decoded pages it
showed last. The pages change only at a page-out or a resize, which say
so.

The rest is behaviour to decide (§10): how far a notch scrolls (Ghostty:
3 rows for a wheel, 1 for a precise device), what the alternate screen does
with the wheel (Ghostty's default sets 1007, which sends arrow keys; the
core sets it by default as Ghostty does), and what new output does to a
view scrolled back (stay, as Ghostty, xterm and Windows Terminal do, until
a key is typed).

---

## 4. Mouse reports

The core keeps every mode a report needs: 1000, 1002, 1003 (which events),
1005, 1006, 1015, 1016 (which format) and 1007, in the table that follows
Ghostty's (`Vt.geng`, the mode list). Nothing reads them: the window
selects no button or motion events.

Ghostty's encoder, `src/input/mouse_encode.zig`, is 290 lines before its
tests: `shouldReport` by mode, a motion outside the window reported only
while a button is held, motion de-duplicated by cell unless the format is
pixels (1016), the button code with its modifiers, and five formats. It
takes a position in pixels, the cell size and padding, whether any button
is down, and the last cell reported. libghostty-vt has it as
`ghostty_mouse_encoder_*` (`include/ghostty/vt/mouse/encoder.h`), so a
Geng port can be held to it as the key encoder is (V47's gate, 900,000
events), and V47's survey already said the mouse would share that gate.

What the C has to send: a button press or release with its button (1–3,
4–7 for the wheels, 8–11), the pointer's position in pixels, and the
modifiers as the key record carries them (the event's own state, V47); a
motion with its position and the buttons held. X sends a motion only to a
window that asked, and over `ssh -X` each is 32 bytes on the wire, so the
window asks for `PointerMotion` only while a program wants motion (1003),
or `ButtonMotion` while a button is down (1002, or a selection being
dragged).

Two things are left to decide (§10). The first is what takes the mouse
back from a program for a selection. xterm, Ghostty
(`mouse-shift-capture`) and Windows Terminal all use Shift. The second is
whether the wheel goes to a program that has taken the mouse.
Ghostty sends it, and with 1007 set and the alternate screen up, a program
that has not taken the mouse gets arrow keys.

---

## 5. Selection and the X selections

A copy is visiterm owning PRIMARY (on a selection) or CLIPBOARD (on a copy
key) and answering each `SelectionRequest` with the text; a paste is
asking the owner with `ConvertSelection` and reading a property. Text
larger than the server's largest request goes as `INCR`: a piece at a time,
each written when the reader deletes the last, so one round trip a piece.

Locally on Xvfb, xclip on the other side:

| | 1 KB | 1 MB | 10 MB |
|---|---|---|---|
| paste: xclip owns, `sel get` | 0.09 ms | 1.26 ms (`INCR`, 2 pieces) | 2.55 ms (`INCR`, 11 pieces) |
| copy: `sel own`, xclip reads | 2 ms | 4 ms | 19 ms |

xclip offers `TARGETS` and `UTF8_STRING` only. It sends `INCR` pieces of
about 1 MB.

Over `ssh -X`, `sel` on gmktec7, the display and xclip here:

| | 1 KB | 1 MB | 10 MB |
|---|---|---|---|
| paste: `ConvertSelection` answered | 4.7 ms | 4.5 ms | 3.6 ms |
| paste: all of it read | 11.9 ms | 115 ms | **1,124 ms** (11 pieces, 14 round trips) |
| copy: xclip has all of it | 11 ms | 71 ms | 240 ms (one write of 10 MB, which held `sel` 120 ms) |

The 10 MB copy served in pieces, the same way:

| piece | pieces | xclip has all of it |
|---|---|---|
| 64 KB | 160 | 998 ms |
| 256 KB | 40 | 328 ms |
| 1 MB | 10 | 243 ms |
| 4 MB | 3 | 235 ms |

What this says for visiterm's loop:

- **A paste has to be read in the loop, a piece at a time.** `sel` reads
  each piece with a blocking `GetProperty`: over `ssh -X` a 1 MB piece holds
  it about 100 ms, during which a window would draw nothing. The C can send
  the request and take its reply when the X socket next has it, as it
  takes events (`xcb_poll_for_reply`), and the loop goes on. A paste then
  reaches the pty in pieces, which V48's queue was built for.
- **A copy is answered in the C, from the C's copy of the text**, as an
  expose is answered from the pixmap (V36): the text is handed to the C
  once, when the selection ends, and a `SelectionRequest` never waits on
  Geng. Pieces of 256 KB to 1 MB keep each write short. Each piece is a
  round trip, so a smaller piece costs throughput: a 10 MB copy over
  `ssh -X` takes 1.0 s in 64 KB pieces and 0.24 s in 1 MB pieces.

What the selection is in the core: the cells between two points, as
absolute rows (counted from the first row the terminal ever had, so they
survive scrolling and page-outs), read out as text when the button is
released: wrapped rows joined, trailing blanks dropped, a wide character's
spacer skipped, a grapheme cluster read whole. That text is what PRIMARY
serves until the next selection, as xterm does, so a selection whose rows
are later written or reflowed still pastes what was selected. A double
click selects a word, a triple click a line. Thai words are C§8's libthai
row and come later; until then a Thai run is one word.

---

## 6. Paste

A paste goes through a pty's line discipline. 10 MB of `gitlog.txt` (ESCs
removed, LF sent as CR, as a terminal sends a newline), in non-blocking
writes with the master read throughout (`paste.py`):

| program | writes of 4 KB | writes of 64 KB | read back |
|---|---|---|---|
| `cat` (cooked, echo) | 1,259 ms | 1,255 ms | 20.7 MB |
| `cat >/dev/null` (cooked, echo) | 1,192 ms | 1,041 ms | 10.4 MB |
| `stty raw -echo; cat >/dev/null` | | 12 ms | 0 |
| `stty raw -echo; cat` | | 21 ms | 10.0 MB |

A program with its own line editor (a shell's readline or zle, vim, any
program that sets bracketed paste) runs the terminal raw, and a paste is
the kernel's copy. Only a cooked program costs a second a 10 MB paste, and
its echo comes back doubled for the core to read. V48's queue is what makes
either work: the loop writes what the pty takes and reads in between.

What a paste writes is Ghostty's (`src/input/paste.zig`, and
`ghostty_paste_encode` in libghostty-vt): control bytes that could act
replaced by spaces; with mode 2004 the text wrapped in `ESC[200~` and
`ESC[201~`; without 2004, each LF sent as CR. An `ESC[201~` inside the
text cannot end the bracket early: its ESC is among the bytes replaced, so
the program reads ` [201~`. Ghostty also refuses a paste until the user confirms it
(`clipboard-paste-protection`, `isSafeWith`): an unbracketed one with a
`\n` or `\r`, which would arrive as Enter, or one of either kind containing
`ESC[201~`, which Ghostty takes as a sign that whoever made the text is
acting strangely. With 2004 set, newlines are not asked about
(`clipboard-paste-bracketed-safe`). The bytes replaced are xterm's list:
NUL, BS, ENQ, EOT, ESC, DEL, and the tty's own control characters, so that
a paste cannot send a signal or edit the line (Ctrl+C, Ctrl+\\, Ctrl+U,
Ctrl+Z, Ctrl+Q, Ctrl+S, Ctrl+W, Ctrl+V, Ctrl+R, Ctrl+O). visiterm has
nowhere to ask yet (§10).

Where a paste comes from: X's PRIMARY with the middle button or
Shift+Insert, CLIPBOARD with a key. Ctrl+Shift+V is the convention in VTE
terminals, Ghostty and kitty on Linux. Under the kitty protocol a program
could ask for Ctrl+Shift+V itself, so the terminal takes it before the
encoder, as V50 takes Ctrl+=.

---

## 7. OSC 52

What tmux 3.4 sends its terminal for a copy, `set-clipboard on`, TERM
`xterm-256color` (`osc52.py`):

| copied | OSC 52 sent | selection | base64 |
|---|---|---|---|
| 1,000 B | 1 | empty | 1,336 B |
| 100,000 B | 1 | empty | 133,336 B |
| 1,000,000 B | 1 | empty | 1,333,336 B |
| 4,000,000 B | 1 | empty | 5,333,336 B |

tmux sends a copy whole, of any size. An empty selection is CLIPBOARD to
Ghostty (`stream_handler.zig`, `clipboardContents`), as `c` is; `p` is
PRIMARY.

What the core does with it now: any OSC, DCS or APC string is kept to
4,096 bytes and the rest is dropped (`Cell.stringMax`), and a command the
core takes is dropped whole past 2,048 bytes (`oscMax`, Ghostty's
`MAX_BUF`). Ghostty keeps OSC 52 to 8 MB of base64 (`MAX_ALLOCATING_BUF`),
which is 6 MB of text, and allows writes and asks before reads
(`clipboard-write = allow`, `clipboard-read = ask`).

A read is `ESC]52;c;?`, and the terminal's answer, the clipboard in
base64, goes to whatever reads the pty, as if typed. A remote host in an
ssh session can ask for it and read the answer; a file printed with `cat`
can ask for it too, and the shell is then typed the clipboard. The other
terminals vendored here allow writes and never answer a read: Alacritty's
default is `OnlyCopy`, WezTerm parses `QuerySelection` and does nothing,
and Windows Terminal parses the `?` and sets no clipboard. nvim 0.10 and
later read through OSC 52 for `"+p`, and tmux through `get-clipboard`;
without an answer they give up after a timeout.

The core's time on the 5.3 MB OSC, against the same bytes as text
(`core-bench`, three runs):

| input | time |
|---|---|
| `ESC]52;c;` + 5.3 MB of base64 + BEL | 8–9 ms |
| the 5.3 MB of base64 as text | 17–19 ms |

The OSC is cheaper than text because the core stops keeping it after
4 KB. Keeping it to 8 MB is a byte at a time into an `Array.Builder
UInt8` as the string is kept now, or a slice of each read appended to a
`Bytes.Builder` (D1050), which copies a run in one call; the slices are
the shape the EUC-KR decoder took.

Decoding it: geng-lang's `core` has no base64, nor does any package here.
One written in Geng into a `Bytes.Builder` (`probes/base64`), four
characters to three bytes, decodes the 5.3 MB in **10.4 ms** (104 ms for
ten), about 510 MB/s; coreutils' `base64 -d` does it in 3.5 ms with its
process start. A 4 MB copy from tmux costs visiterm about 20 ms in Geng,
kept and decoded, and then the C owns CLIPBOARD as for any copy (§5).
Nothing is needed from geng-lang.

---

## 8. Ctrl and the wheel: a zoom?

Gilbert asked on 2026-11-03 for Ctrl with the wheel to change the font's
size, as browsers do, beside or instead of V50's Ctrl+=, Ctrl+− and Ctrl+0,
and said it need not be built if it turns out badly.

What the terminals vendored here do (their sources, defaults only):

| terminal | Ctrl+wheel | when a program has taken the mouse |
|---|---|---|
| Windows Terminal | a point a notch (`ScrollToZoom`, on) | goes to the program; Shift takes it back (`_canSendVTMouseInput`) |
| Ghostty 1.4 | scrolls | goes to the program |
| Alacritty | scrolls | goes to the program |
| WezTerm | scrolls | goes to the program |
| PuTTY | scrolls | goes to the program |

What programs do with it by default: tmux 3.4 binds only `WheelUpPane`,
`WheelUpStatus` and `WheelDownStatus` in its root table, nothing with
Ctrl; nvim 0.9.5 binds the wheel with Shift (a page) and nothing with
Ctrl. **But nvim takes the mouse by default** (`mouse=nvi`), and so does a
tmux with `mouse on`. Under Windows Terminal's rule the zoom does nothing
in nvim, or anywhere in such a tmux, which is much of where a terminal is
used.

So there are two rules that work:

- **Ctrl and the wheel are always visiterm's**, as Ctrl+= already is
  (V50): a program never sees them. It loses nothing a default nvim or
  tmux does; a user's own mapping of `<C-ScrollWheelUp>` would stop
  working.
- **Windows Terminal's rule**: the zoom only when no program has the
  mouse. Programs keep Ctrl and the wheel, and the zoom works at a shell
  prompt but not in nvim.

What it costs either way: a zoom sizes every face again and redraws every
cell (V50, §14). Its time was not measured. A touchpad under X sends wheel
buttons as it crosses each step, several in a fast stroke, so the wheel
events one read of the X socket brings are summed into one zoom, and the
window resizes once. A notch is a point, as Ctrl+= is, and Windows
Terminal's is.

Whether it should replace the keys: the keys cost nothing to keep, work
without a mouse, and Ctrl+0 has no wheel form. The leaning is to keep both.

---

## 9. Not measured yet

- **A real mouse's motion rate**, and a touchpad's wheel steps, on Gilbert's
  desktop: Xvfb has neither. `xdotool` can drive both for gates.
- **XInput 2's smooth scrolling.** X's core protocol gives a wheel as
  buttons 4–7, one press a step; precise scrolling and fractional steps
  need XInput 2 (`xcb-xinput`). The core protocol works the same over
  `ssh -X` and on ETX; XInput 2 comes after daily use says the steps are
  too coarse.
- **The time of a zoom** (§8).
- **Clipboard managers** that take CLIPBOARD when its owner exits
  (`SAVE_TARGETS`): what Mint's desktop runs.
- Thai word selection (C§8), as before.

---

## 10. For Gilbert

1. **Scrolling back, with the wheel and Shift+PgUp/PgDn**, built with the
   mouse. A notch scrolls 3 rows; the view reads rows from the ring, and
   from pages decoded when shown, keeping the last two; new output leaves a
   scrolled view where it is, and a key typed brings it to the bottom. In
   the alternate screen with 1007 set, the wheel sends arrow keys. Leaning:
   yes; registered in `geng-plan.md` phase 3, where it was missing.
2. **Mouse reports: Ghostty's encoder ported to Geng, held to
   libghostty-vt in the key gate.** The C sends button and motion records
   with pixel positions and asks X for motion only while a program or a
   drag wants it. Shift takes the mouse back for a selection; the wheel
   goes to a program that has taken the mouse. Leaning: yes.
3. **Selection in the core as absolute rows, its text read at release and
   handed to the C, which owns PRIMARY and answers every request itself**,
   `INCR` in pieces of 256 KB. Word on a double click, line on a triple.
   The selection is cleared when the rows it covers are written or the
   window is resized, and what it copied stays copied. Leaning: yes.
4. **Paste: CLIPBOARD with Ctrl+Shift+V, PRIMARY with the middle button
   and Shift+Insert; copy to CLIPBOARD with Ctrl+Shift+C.** The C reads the
   selection in the loop, a piece at a time; Ghostty's paste encoder,
   ported and gated, writes it into V48's queue. Ghostty asks before an
   unsafe paste and visiterm has nowhere to ask: the leaning is to paste
   as xterm does, with the unsafe bytes Ghostty replaces still replaced,
   and register the confirmation for phase 7. The other choice is a
   confirmation line drawn in the window, which is the larger piece of
   work.
5. **OSC 52: writes allowed to 8 MB of base64, as Ghostty; reads denied
   unless the config allows them**, since there is nowhere to ask. The
   core keeps an OSC 52 as `Bytes` slices, decodes it in Geng, and hands
   the text to the C as a copy. Empty and `c` are CLIPBOARD, `p` PRIMARY.
   Leaning: yes.
6. **Ctrl and the wheel zoom, always**, a point a notch, the wheel events
   of one read summed into one zoom; Ctrl+=, Ctrl+− and Ctrl+0 kept beside
   it. Leaning: yes, by §8's first rule, since the second leaves nvim
   without it. If you would rather programs kept Ctrl and the wheel, it is
   Windows Terminal's rule, or none.

The order to build: the encoder and the gate (2), since every other piece
reads the mouse; scrolling back (1); selection and copy (3); paste (4);
OSC 52 (5); the zoom (6) with the wheel.

---

## 11. Gilbert's answers (2026-11-03)

**4, paste: as xterm does.** Gilbert does not want visiterm to ask before a
paste, as Ghostty does. A paste is written with xterm's bytes replaced by
spaces (§6), bracketed when the program set 2004 and with LF as CR when it
did not, and never refused. No confirmation is registered for later.

**5, OSC 52: taken.** Writes allowed, to 8 MB of base64; reads refused by
default and never answered, as Alacritty, WezTerm and Windows Terminal do;
`[clipboard] osc52_read = "allow"` in the config for anyone who wants nvim's or tmux's
paste over ssh, with no question asked either way.

**1, scrolling back: taken, as most terminals do it.** What the vendored
terminals do by default (their sources):

| | Ghostty | Alacritty | WezTerm | Windows Terminal | PuTTY |
|---|---|---|---|---|---|
| a wheel notch | 3 rows (1 precise) | 3 rows | 5 rows on X11 | the system's (3) | 5 rows |
| page keys | Shift+PgUp/PgDn | Shift+PgUp/PgDn | Shift+PgUp/PgDn | Ctrl+Shift+PgUp/PgDn | Shift+PgUp/PgDn, half a page |
| top, bottom | Shift+Home/End | Shift+Home/End | none bound | Ctrl+Shift+Home/End | none |
| a key typed | to the bottom | to the bottom | to the bottom | to the bottom | stays (`ScrollOnKey` off) |
| new output | stays | stays | stays | stays | to the bottom (`ScrollOnDisp` on) |

visiterm takes the majority: a notch is 3 rows; Shift+PgUp/PgDn a page and
Shift+Home/End the top and bottom, all given to the program on the
alternate screen, as Alacritty and WezTerm do; a key typed brings the view
to the bottom and new output leaves it where it is; in the alternate screen
with 1007 set the wheel sends arrow keys. And Ghostty's Ctrl+Shift+Up/Down,
which jumps between the prompts the shell marks with OSC 133, since the
core already keeps them.

**2, mouse reports: taken** as §10 has it: Ghostty's encoder in Geng, held
to libghostty-vt in the key gate; motion asked of X only while it is
wanted; Shift takes the mouse back for a selection; the wheel goes to a
program that has taken the mouse.

**3, selection: taken** as §10 has it, with one consequence written out:
when another program takes PRIMARY (X's `SelectionClear`), visiterm stops
highlighting its selection, as xterm does.

**6, Ctrl and the wheel: taken.** Always visiterm's, a point a notch, the
wheel events of one read summed into one zoom, Ctrl+=, Ctrl+− and Ctrl+0
kept.

Every leaning of §10 is taken. Gilbert asked as well for a user's guide to
the kinds of copy and paste, since the selection, the clipboard and OSC 52
confuse: [`user/copy-and-paste.md`](user/copy-and-paste.md), written from
these answers before the build and kept to it as the build lands. It names
the OSC 52 setting as the config file names its keys:
`[clipboard] osc52_read = "allow"`.

The order to build stands: the mouse encoder and its gate, scrolling back,
selection and copy, paste, OSC 52, the zoom.

---

## 12. Mouse reports built (2026-11-03)

**The encoder** is `Vt.Mouse`, Ghostty's `mouse_encode.zig` in Geng: which
events a tracking reports, a press or motion outside the window reported
only while motion is tracked and a button held, a motion within the last
cell reported not again unless the format is pixels, the button code with
Shift, Alt and Ctrl, and the five formats. A position is whole pixels, as
X gives them, where Ghostty's is a float. The legacy forms are raw bytes,
so a report goes out by `sendRaw`, which no pane's character set touches.

**The core** keeps the tracking and format as Ghostty's flags do, not by
reading its mode table: the last of 9, 1000, 1002 and 1003 set is the
tracking, the last of 1005, 1006, 1015 and 1016 the format, and a reset of
any one of a group is none, whichever was set (`Vt.mouseModes`). XTRESTORE
goes through the same setter, as Ghostty's does; RIS makes them none.

**The mouse gate** (`harness/mouse.py`) holds both to libghostty-vt. Each
case is a run of mode changes fed to a terminal on each side (the modes set
and reset alone or several to a sequence, XTSAVE, XTRESTORE, DECSTR, RIS),
whose tracking and format then go to each side's encoder
(`ghostty_mouse_encoder_setopt_from_terminal` for the oracle,
`harness/oracle/ghostty-mouse.c`); a window, cell and padding; and one to
eight events, with the last cell carried between them. **300,000 cases
agree: 1,350,913 events, 603,676 of them encoded.** With the Ctrl bit made
17 instead of 16 for the test, 1,048 of 3,000 cases fail.

**The window**: the C records a press, release or motion (kind 9) with its
button in Ghostty's numbering (X's but for middle and right, which swap),
its modifiers read from its own event as a key's are, its position, and
the window's and cell's sizes, so a zoom or resize needs no state in
`Main`. A wheel step is its press: X's release of buttons 4-7 is dropped,
as Ghostty reports a step as a press. Motions in a row are recorded as the
last of them. X sends motion only while a button is held, and every motion
while the program asks for mode 1003 (`X11.motion`, set from the loop when
the tracking changes). `Main` keeps the buttons held, and reports a motion
with the lowest of them, as Ghostty does.

**Shift**: a press or release of a button with Shift, or a motion with
Shift while a button is held, is visiterm's own and is not reported (it
will select, §5). The wheel is not taken by Shift: Ghostty's
`scrollCallback` reports it whatever the modifiers, and nvim pages with
Shift and the wheel, so the program gets Shift+wheel (code 68 for a step
up).

**The pointer gate** (`harness/pointer.py`, `corpus/pointer/`) drives
visiterm on Xvfb with xdotool, on a program that sets the case's modes and
records every byte it reads: 16 cases, every one as the encoder says, among
them presses and releases of each button, the wheel without releases, Ctrl
and Alt, Shift, X10's raw bytes, mode 9's presses alone, no motion under
1000, a drag under 1002 with a repeated cell left out, a drag off the
window's edge clamped to the last column, motion without a button under
1003 and none after it is reset, pixels, urxvt and UTF-8. Its first run
found the C's window size unset until the first resize: every press was
outside a 0 by 0 window and dropped, and every release, which is always
reported, came at cell (1, 1).

---

## 13. Scrolling back built (2026-11-03)

**The core** answers three questions about the scrollback and draws none of
it itself:

- `Vt.scrollbackRows`: how far a view can go back, the main screen's rows
  in the ring and the pages; 0 while the alternate screen is up.
- `Vt.rowsPushed`: the rows that have ever entered the scrollback, the ones
  it holds and the ones dropped from its oldest end. The pages count the
  rows they drop (`Back.gone`) when they drop a page, so the line feed's
  path is untouched. A view stays on its rows by moving up as many rows as
  this grew by over a read.
- `Vt.viewAt`: the rows a view `back` rows up shows, as a screen of their
  own. A row in the ring is copied; a row in the pages is read from its
  page, whose clusters are interned in a copy of the term's table that the
  view carries, so drawing a view never changes the term.

**`Vt.View.frameBack`** draws that screen through the same body as every
frame (`frameOn`), with the cursor `back` rows lower, hidden when it falls
off the bottom, and no preedit. A scroll of the view is found by the rows'
hashes and sent as one `CopyArea`, as output's is.

**`Main`**: a wheel step no program asked for scrolls the view 3 rows on
the main screen; on the alternate screen with 1007 set it sends three arrow
keys in DECCKM's form, as Ghostty does, and nothing with 1007 reset. A step
reported to a program that asked for the mouse is one report, as xterm
sends it; Ghostty sends three (its scroll multiplier, `Surface.scrollCallback`),
and nvim already scrolls 3 lines a report. Shift+PgUp and Shift+PgDn move a
page, Shift+Home and Shift+End to the top and the bottom, and Ctrl+Shift+Up
and Ctrl+Shift+Down to the shell's previous and next prompt
(`Vt.promptJump`, after Ghostty's `PageList.scrollPrompt`: a row marked as
a prompt's start by OSC 133 put at the view's top; in the pages, the mark
is read from the row's header, so no text is decoded). All of them are the
program's on the alternate screen. A key that sends the program anything,
or an IME's commit, brings the view to the bottom; a resize does too.

**Tested**: the view gate draws a case's frames scrolled back after its
input (`back.txt`): `view-back-pages`, 600 rows on a 4 by 3 screen with
256-row pages, at offsets in the ring, in a page, across the two, past the
top (clamped) and back to 0, the move from 10,000 (the top) to 6 found as a
scroll; `view-back-clusters`, rows with a combining mark and a wide
character read back from a page. 344 cases pass. The pointer gate adds four
cases of the wheel on the alternate screen (arrows, DECCKM's arrows, 1007
reset, a report). On Xvfb, by screenshots: five steps of the wheel move the
view 15 rows and Shift+PgUp a page more; Return brings it to the bottom;
Shift+Home goes to the top; 500 lines and then 20,000 more arriving leave
the view on its rows; when 10,000 full-width lines push the view's own rows
past the 3,000-line limit, it shows the oldest row kept; two
Ctrl+Shift+Up go to the prompt two above, and 99 more reach a prompt 2,100
rows back, in the pages.

**Measured, and no cache**: §3 leaned on keeping the last two decoded
pages between frames. `core-bench FILE view BACK N` times N views of
`gitlog.txt`'s full scrollback (94,095 rows at 160 by 50, 1,024-row
pages):

| rows up | 100 views | a view |
|---|---|---|
| 30 (the ring) | 0 ms | under 0.01 ms |
| 2,000 | 182 ms | 1.8 ms |
| 20,000 | 211 ms | 2.1 ms |
| 90,000 | 423 ms | 4.2 ms |

A frame deep in the history reads its page or two again each time, at 2
to 4 ms, against a frame every 16 ms at most, and a view moves only when
the wheel or a key moves it, or output comes. No cache is kept; daily use
can say otherwise.

**Gates for §12 and §13**: replay 325 of 325, view 344 of 344, keys
300,000, mouse 200,000 (901,013 events), charset 17 lines, pixels 36 of
36, pointer 20 of 20, IME 14 of 14, perf within its record and budgets
(the resize cases −0.9% to +2.7%), and the differential fuzzer clean on
each tree (coverage 6,174 and 6,175, no findings). The fuzzer is asked for
600 s and takes about 1,720 s, most of it replaying its saved corpus of
59,905 inputs before it begins; the corpus wants trimming.

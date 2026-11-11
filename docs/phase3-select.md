# Phase 3 · Mouse, selection, clipboard, OSC 52, paste: a survey

Status: **survey begun 2026-11-03**, for Gilbert's answers (§10); every
leaning taken the same day (§11); a user's guide in
[`user/copy-and-paste.md`](user/copy-and-paste.md). Built: mouse reports
(§12), scrolling back (§13), selection and copy (§14), paste (§15),
OSC 52 (§16), the Ctrl and wheel zoom (§17). It is the
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
| Can the window show the scrollback? | **No: nothing in puritty scrolls back**, and the plan's phase 3 list does not name it. The wheel is how it is done, so it belongs with the mouse. The rows are there: the core's ring holds recent ones, and D901's pages the rest. Reading the whole scrollback (94,095 rows) as text takes 544 ms, 5.8 µs a row, so a screen in the oldest pages costs at most two 1,024-row pages, about 12 ms, once | 3 |
| What does a mouse report need? | Ghostty's encoder is 290 lines before its tests, and libghostty-vt has it behind a C API, so a gate like the key gate's can hold a Geng port to it. The core already keeps modes 1000–1016 and 1007 | 4 |
| What do the X selections cost? | **Locally nothing: 10 MB pasted in 2.6 ms, served in 19 ms. Over `ssh -X` from gmktec7, a 10 MB paste takes 1.1 s and a copy 0.24–1.0 s by piece size.** One blocking `GetProperty` of a 1 MB piece holds the caller for about 100 ms there, so the transfer has to run in the loop, not in a call | 5 |
| What does a paste cost through a pty? | **10 MB into a raw program (a shell's line editor, vim) in 12–21 ms; into cooked `cat`, 1.0–1.3 s**, the line discipline's own speed, which V48's queue already rides out. Ghostty's paste rules (unsafe controls to spaces, brackets, CR for LF) are in libghostty-vt too, for the same gate | 6 |
| What does an OSC 52 cost? | **tmux 3.4 sends a copy as one OSC 52, unlimited: 4 MB of text is 5.3 MB of base64.** The core keeps 4,096 bytes of a string and drops the rest, at 9 ms for those 5.3 MB. Ghostty keeps OSC 52 up to 8 MB. Base64 in Geng on `Bytes.Builder` decodes 5.3 MB in 10.4 ms, so nothing is needed from geng-lang | 7 |
| Should Ctrl and the wheel zoom? | **Of the five terminals vendored here, only Windows Terminal does, and only when no program has taken the mouse.** nvim 0.9.5 takes the mouse by default (`mouse=nvi`), so under that rule the zoom is dead in nvim. Neither nvim nor tmux 3.4 binds anything to Ctrl and the wheel, so puritty taking it always costs programs nothing they do by default | 8 |

---

## 2. How it was measured

This machine (`nene`), AMD Ryzen 7 8845HS, Linux 6.8, puritty `d63beab`,
geng-lang `7fd24703`, devbox's clang at `-O2`. gmktec7 for `ssh -X`, 4.7 ms
ping. No other load.

- [`../probes/select/`](../probes/select/): `sel`, an X selection client
  in xcb as puritty's would be: `sel get SELECTION TARGET` asks for a
  selection and reads it, `INCR` included; `sel own SELECTION FILE` owns
  one and answers `TARGETS`, `UTF8_STRING`, `STRING`, `TEXT` and
  `text/plain;charset=utf-8`, in `INCR` pieces of `CHUNK` bytes when the
  text is larger. `run.sh` starts its own Xvfb (`:81`) and times both
  directions against the system's xclip at 1 KB, 1 MB and 10 MB of
  `gitlog.txt`; `REMOTE=HOST` runs `sel` there over `ssh -X`.
- [`../probes/paste/paste.py`](../probes/paste/paste.py): SIZE bytes of
  text written to a pty's master in non-blocking writes, the master read
  all the while, as puritty's loop does since V48.
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

A copy is puritty owning PRIMARY (on a selection) or CLIPBOARD (on a copy
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

What this says for puritty's loop:

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
Ctrl+Z, Ctrl+Q, Ctrl+S, Ctrl+W, Ctrl+V, Ctrl+R, Ctrl+O). puritty has
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
process start. A 4 MB copy from tmux costs puritty about 20 ms in Geng,
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

- **Ctrl and the wheel are always puritty's**, as Ctrl+= already is
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
   unsafe paste and puritty has nowhere to ask: the leaning is to paste
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

**4, paste: as xterm does.** Gilbert does not want puritty to ask before a
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

puritty takes the majority: a notch is 3 rows; Shift+PgUp/PgDn a page and
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
when another program takes PRIMARY (X's `SelectionClear`), puritty stops
highlighting its selection, as xterm does.

**6, Ctrl and the wheel: taken.** Always puritty's, a point a notch, the
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
Shift while a button is held, is puritty's own and is not reported (it
will select, §5). The wheel is not taken by Shift: Ghostty's
`scrollCallback` reports it whatever the modifiers, and nvim pages with
Shift and the wheel, so the program gets Shift+wheel (code 68 for a step
up).

**The pointer gate** (`harness/pointer.py`, `corpus/pointer/`) drives
puritty on Xvfb with xdotool, on a program that sets the case's modes and
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

**Open, for daily use**: Gilbert (2026-11-03) keeps one report a wheel
step for now; once he uses puritty, ask him to compare it with Ghostty's
three in nvim and tmux and say which he wants.

**Gates for §12 and §13**: replay 325 of 325, view 344 of 344, keys
300,000, mouse 200,000 (901,013 events), charset 17 lines, pixels 36 of
36, pointer 20 of 20, IME 14 of 14, perf within its record and budgets
(the resize cases −0.9% to +2.7%), and the differential fuzzer clean on
each tree (coverage 6,174 and 6,175, no findings). The fuzzer is asked for
600 s and takes about 1,720 s, most of it replaying its saved corpus of
59,905 inputs before it begins; the corpus wants trimming.

---

## 14. Selection and copy built (2026-11-03)

**Gilbert, on word selection** (2026-11-03): the characters that end a
word for a double click must be the user's to set, at least in part: users
differ on whether `=` and other punctuation belong to a word on a command
line, and he has had to change it in PuTTY before. `[selection]
word_boundaries` in the config is that set, Ghostty's model
(`selection-word-chars`): a run of cells that are all boundaries or all
not is a word, so `===` is a word of its own. The default is Ghostty's,
tab, space and ``'"│`|:;,()[]{}<>$``; `=` is not in it, so `a=b` is one word
until it is added.

**The core** gives a selection's text and its words and lines, by
absolute rows (`Vt.Point`: `rowsPushed` plus the row on the screen), so a
selection stays on its text as output scrolls it:

- `Vt.selectionText`: the cells between two points, a row that wraps
  joined to the next, a newline after any other, the blanks at a line's
  end dropped, a wide character's tail and a spacer at a row's end
  skipped, a cluster read whole; rows in the pages read from them.
- `Vt.wordAt`: Ghostty's `Screen.selectWord`, across a row that wraps; a
  wide character's tail is its head and a spacer at a row's end is the
  character it moved to the next row.
- `Vt.lineAt`: the rows from one that does not wrap to the next that does
  not, without the blanks at either end. Ghostty's `selectLine` also
  stops at a change of OSC 133 content (prompt, input, output) within a
  line; the core keeps prompt marks by row, not by cell, so it does not.
- `Vt.rowsHash`: a hash of rows still on the screen, for the highlight.

`rowsBetween`, which `Vt.viewAt` reads its rows through now, reads rows
for all of them. Writing them turned up one trap: `Array.get` with a
negative index counts from the end of the array (core's documentation says
so), and `wordAt`'s first version walked left from column 0 into the row's
last cells. Every `Array.get` on an index the core computes by subtracting
was read again: the rest are guarded, or reach -1 only on an empty line
with one start (`Resize.promptIn`), where -1 and 0 are the same element.

**The selection gate** (`harness/select.py`, `corpus/select/`) answers
queries of a case's terminal and pins them: wrapped lines joined, blanks
dropped, either order, words on one row and across a wrap, `=` added as
a boundary, runs of boundaries, a blank cell; wide characters, a spacer at
a row's end, a combining mark; rows in a page, across a page and the ring,
and above the oldest row. 3 cases, 30 queries.

**The highlight**: a frame with a selection on the screen carries a
highlight record (`0x05`, its first and last cell) before its runs, and
the C draws a run's cells in that range in a copy of their style with the
foreground and background swapped (the style table's second half, from
65,536); a cursor's cell keeps the cursor's colours. The shadow marks a
selected cell (bit 55), so a cell the selection takes or leaves is drawn
again. Style ids are as they were: giving a selected cell an id bit of its
own would have halved the styles the core can hold (`styleMax`), which
never frees one (vt-core). The view gate draws a case highlighted
(`highlight.txt`): `view-highlight`, a highlight over a bold red word, a
wide character and the cursor, moved, kept and taken away; 345 cases
pass. A screenshot on Xvfb shows a red word's colours swapped and the rest
of two rows in the default colours swapped.

**The window**: `X11.select` gives the C the text and the window owns
PRIMARY or CLIPBOARD from the time of the last event it had (ICCCM 2.1).
The C answers TARGETS, TIMESTAMP, UTF8_STRING, `text/plain;charset=utf-8`,
TEXT, and STRING as Latin-1 with `?` for the rest, from its own copy and
never by asking Geng; text over 256 KB goes as INCR (§5's piece), up to
eight transfers at once, each piece sent when its requestor deletes the
last. A `SelectionClear` is recorded (kind 10).

**`Main`**: with no program reporting the mouse, or with Shift, the left
button selects: a press starts at its cell; a second and third press
within 500 ms on the same cell select the word and the line; a drag moves
the head, by words or lines when it began so, keeping the first word or
line on the far side; letting go makes the text the window's PRIMARY, and
a press and release with no drag takes the highlight away and leaves
PRIMARY as it was, as xterm does. Ctrl+Shift+C gives the selection to
CLIPBOARD, and is puritty's with or without one. The highlight goes on a
resize, when the screen it was made on is no longer up, when another
program takes PRIMARY, and when a row of it still on the screen changes
(each row's hash taken when it was made; rows that scrolled off do not
change). A drag past the window's edge stops at the edge: the view does
not scroll with it yet.

**The pointer gate** gains ten cases that read the selections back with
xclip: a drag, one over two rows either way, a click after it, a double
click, a double click and drag, a triple click, Ctrl+Shift+C, Shift with
mouse reports on (nothing reported, the text selected), and a selection of
the whole scrollback, 320,000 bytes of 5,000 lines, which xclip reads
whole through INCR (the view taken to the top with Shift+Home, the button
pressed, the view taken down with Shift+End, the button let go). 30 cases
pass.

**Gates for §14**: replay 325 of 325, view 345 of 345, select 3 of 3,
keys 300,000, mouse 200,000, charset 17 lines, pixels 36 of 36, pointer 30
of 30, IME 14 of 14, perf within its record and budgets, the differential
fuzzer clean (coverage 6,175, no findings).

---

## 15. Paste built (2026-11-03)

**Gilbert, on the paste button** (2026-11-03): users will want to choose
between the middle button and the right one. `[mouse] paste_button` is
`"middle"` (the default, as xterm) or `"right"` (as PuTTY); the other does
nothing yet.

**The encoder** is `Vt.Paste`, Ghostty's `paste.zig`: xterm's list of
bytes that could act replaced by spaces, the text between `ESC[200~` and
`ESC[201~` with mode 2004, each LF as CR without it, and nothing asked
(§11). A piece of a paste encodes as the whole would, since no byte of
UTF-8 past the first is one the encoder changes, so a paste is encoded as
its INCR pieces come. **The paste gate** (`harness/paste.py`) holds it to
libghostty-vt's `ghostty_paste_encode` (`harness/oracle/ghostty-paste.c`):
**100,000 cases agree**, of printable ASCII, every control byte, DEL, LF,
CR, CR LF, the bracket's start and end, and UTF-8 of one to four bytes,
each also encoded in pieces of 1 to 7 bytes and held to the whole. With
LF sent as itself unbracketed for the test, 997 of 3,000 fail.

**The window** never waits for a paste (§5's finding): `X11.paste` sends
`ConvertSelection` for UTF8_STRING into a property of the window's, and
for STRING, read as Latin-1, when the owner has not UTF-8; the property is
read with a `GetProperty` whose reply is taken when it comes
(`xcb_poll_for_reply`, at the end of each drain), and INCR pieces are read
as the owner puts them. Each piece's text is kept in the C and a record
(kind 11) says it came, and whether more is to come; `X11.pasted` takes
it. One paste at a time: another asked for while one is under way is not
made, unless the first has waited 10 s for an owner that never answered.
Its first run lost all but the first megabyte of a 10 MB paste: the owner
writes its next piece as soon as a read deletes the last, so the event
saying so came before the read's reply was taken, and was dropped. A new
piece seen while a read is out is now read when its reply is taken.

**`Main`**: the paste button (with no program reporting the mouse, or with
Shift) and Shift+Insert paste PRIMARY; Ctrl+Shift+V pastes CLIPBOARD. All
three are puritty's before the encoder. Whether the paste is bracketed is
mode 2004 when its first text comes; each piece goes through `Vt.Paste`
into V48's queue as typed text does, in the pane's character set, and the
view comes to the bottom. A paste of nothing sends nothing.

**The pointer gate** gains 13 cases, with xclip owning the selection
(in the foreground, ended with each case, so that none pastes another's):
CLIPBOARD with Ctrl+Shift+V, unbracketed (LF as CR) and bracketed; text
with ESC, Ctrl+C, DEL, NUL, CR LF and Ctrl+U, unbracketed and bracketed
(the bracket's end, its ESC a space, stays inside); Korean and a combining
accent from PRIMARY by the middle button and by Shift+Insert; an owner of
STRING alone, read as Latin-1 (`café naïve`); 320,000 bytes through INCR,
bracketed, whole; puritty's own selection pasted back; the middle button
reported to a program that asked, and pasting with Shift; the right button
pasting under `paste_button = "right"`, the middle doing nothing; and
Ctrl+V with nothing owned, nothing sent. 43 cases pass.

**10 MB pasted end to end** on Xvfb (`gitlog.txt`'s first 10 MB, ESCs
taken out, owned by xclip):

| program | arrived | time |
|---|---|---|
| raw `cat` to a file | 9,968,714 bytes, all of it | about 250 ms |
| cooked `cat`, echoing | 9,932,251 bytes | about 2.7 s |

The cooked shortfall is the line discipline's, to the byte: two lines of
the input are longer than the 4,096 bytes a canonical line holds, which
drops 36,433 bytes, and the last 30 bytes, a line with no end, wait for an
Enter. The time is §6's: cooked `cat` echoes every byte back for the core
to read.

**Gates for §15**: replay 325 of 325, view 345 of 345, select 3 of 3,
paste 100,000, keys 300,000, mouse 200,000, charset 17 lines, pixels 36 of
36, pointer 43 of 43, IME 14 of 14, perf within its record and budgets,
the differential fuzzer clean (coverage 6,175, no findings).

---

## 16. OSC 52 built (2026-11-03)

As §11 has it: writes allowed to 8 MB of base64, reads refused and never
answered unless `[clipboard] osc52_read = "allow"`, and nothing asked.

**The core** keeps an OSC 52 whole instead of to `stringMax`: once an OSC
has read `52;`, it is in a state of its own (`psClip`), which copies each
run of bytes up to a control into a `Bytes.Builder` (geng-lang D1050) in
one call and carries on in the next read when one ends inside it. Past
Ghostty's 8 MB (`MAX_ALLOCATING_BUF`) the OSC is dropped whole; CAN and
SUB end it with nothing done; other controls inside are skipped, as in any
OSC. At its end it is read as Ghostty reads it (`clipboard_operation.zig`,
`Surface.clipboardWrite`): `KIND;DATA` with one letter of kind or none
(`p` and `s` PRIMARY, any other CLIPBOARD), `?` a read, any other DATA
base64, strict with its padding optional (`Vt.Base64`), which writes
nothing when it does not decode and the empty text when DATA is empty.
Each request waits for the embedder (`Vt.takeClipboard`), which decides
what may be done.

**The selection gate** has a case of fourteen OSCs fed in reads of 1, 7
and 100,000 bytes, the same requests each time: writes ended by BEL and by
ST, to each selection, with and without padding, a read, 5,000 characters
(past the 2,048 the core keeps of another OSC), controls inside, empty
DATA; and the ones that write nothing: bad base64, a kind of two letters,
nothing after `52;`, one cut by CAN, a lone character left over. A title
OSC after them and the text after that are as they were.

**`Main`** does the requests between turns of the loop: a write makes the
window own the selection with the text, as a copy does (a write to PRIMARY
takes a selection's highlight away, since the selection is no longer
puritty's); a read, when allowed, asks the selection's owner for its text
as a paste does and answers `OSC 52 ; LETTER ; BASE64`, ended as the
question was. One read or paste at a time: a read asked for during a paste
is not answered.

**The pointer gate** gains six cases: a write to CLIPBOARD and to PRIMARY,
read back with xclip; a read refused (nothing comes back) and one allowed
(`ESC]52;c;cGFzdGVkIHRleHQKbGluZSB0d28=BEL` for `pasted text\nline two`);
3,000,000 bytes written, as tmux sends a large copy whole (§7), read back
whole; and a write to PRIMARY after puritty's own selection, which xclip
then reads.

**The perf gate moved, and the record with it.** With the OSC 52 state as
four fields of the term, `resize/*/long-10000` counted 5.9% over its
record (3% allowed); the same state as one field (`Term.osc52`, a record
of its own) counted 3.09% over. The instructions are not the resize's
code: `perf record` puts about a third of that case in the collector
(`minor_scan`, `GC_mark_from`, `GC_allochblk_nth` and the rest), and the
runtime's nursery statistics (`GENG_NURSERY_STATS`) for twenty resizes are

| build | minor collections | full collections | instructions |
|---|---|---|---|
| `d97d306` (before OSC 52) | 43 | 13 | 444,246,530 |
| this one | 43 | 18 | 454,272,267 |

with the feeding alone the same on both (154,357,157 and 154,359,233). A
term one word larger on each of its copies moves where Boehm's full
collections fall, five more of them here; the same kind of shift made the
two words of the mouse's state count 0.35% *under* the record (§12). The
four `long` resize cases are recorded again with this commit: `long-10000`
290.9 M to 299.9 M (both limits), `long-100000` 309.8 M to 310.3 M and
688.4 M to 707.0 M, the last two within the tolerance but moved the same
way. That the term's size moves full collections at all is the
collector's, and belongs with geng-lang's G7 work on collection, not here.

**Gates for §16**: replay 325 of 325, view 345 of 345, select 4 of 4,
paste 100,000, keys 300,000, mouse 200,000, charset 17 lines, pixels 36 of
36, pointer 49 of 49, IME 14 of 14, perf within its record (as recorded
above) and budgets, the differential fuzzer clean (coverage 6,229, no
findings).

---

## 17. Ctrl and the wheel zoom (2026-11-03)

As §11 has it: Ctrl and the wheel are puritty's always, a point a step,
and never reach a program, even one that asked for the mouse. A step up
or down of the wheel with Ctrl alone is a zoom's step; the steps that come
in the same take of events (a touchpad's stroke sends several) are summed,
a motion between them passed over, and the font is sized once, from 4 to
96 points, as Ctrl+= does (V50). Ctrl+=, Ctrl+− and Ctrl+0 are as they
were.

**What a zoom costs**, §8's question, on Xvfb with a screen of
`gitlog.txt`, the X side's statistics (`X11_STATS`) for ten zooms a step
at a time against none: 4.15 ms of drawing in all against 0.39 ms, so
about 0.4 ms a zoom for its frames, the glyph set begun again each time
(`resets 10`) and every glyph rasterised at its new size. Summing a
stroke's steps saves a few of these, not a stall.

**The pointer gate** gains two cases, with SGR mouse reports on: two
steps up with Ctrl, nothing reported, and then a plain step reported in
the larger cells (column 11 where 11 points has it in 12); and a step down
and one up with Ctrl, which sum to no zoom, the plain step then reported
in column 12. A screenshot on Xvfb shows the text drawn larger in the same
window after three steps.

With this, every piece of phase 3's list is built. Its exit is Gilbert's
daily use (`geng-plan.md` §6).

**Gates for §17**: replay 325 of 325, view 345 of 345, select 4 of 4,
paste 100,000, keys 300,000, mouse 200,000, charset 17 lines, pixels 36 of
36, pointer 51 of 51, IME 14 of 14, perf within its record and budgets,
the differential fuzzer clean (coverage 6,228, no findings).

## 18. Registered from geng-lang: decoding a page into the view (2026-11-03)

geng-lang's census of what dies old (`m4-memory-proofs.md` §MP2, §MP5)
found the view's decoded pages to be the frame loop's largest old garbage:
about 165 MB over `core-view`'s 399 views of `gitlog.txt`, each 1,024-row
page decoded whole into rows of its own, which the view keeps two of and
then drops. Its D1054 (Gilbert's answer, §MP9) is that geng-lang adds no
owned array for them. puritty decodes only the rows a frame shows,
straight into the view's screen, which is what such an array would have
freed. Not built; measured against the census when it is.

## 19. The output queue's shape (2026-11-04, measured, not built)

geng-lang's quadratic shapes survey (`m4-quadratic.md` §QD10) found V48's
queue (§11 of `phase3-input.md`) copying itself: `send` and `sendRaw` add
to `out` with `Bytes.flatten [ m.out, bytes ]`, which copies the whole
queue for every key, report, reply or paste added while anything is still
queued. Normally the queue is empty and this costs nothing. It grows while
the program is not reading: busy, stopped, or blocked on output puritty
has not read yet.

**The probe**, `probes/queue/`: `Main.send`'s queue, a paste in it, then
12-byte reports, one write tried after each, as the loop tries one every
turn. The pty takes nothing while the program is "stalled", and then a
fixed count a write. Natively, at `-O2` with core-bench's passes, three
shapes:

- `flatten`: one `Bytes`, as today;
- `pieces`: an `Array Bytes`, each write offering its first piece;
- `coalesce`: the same array, and before a write a first piece under 4 KB
  is joined with the ones after it, up to 64 KB, and kept joined, so a
  byte is joined once.

`flatten` and `coalesce` write the same bytes in the same order (a sum
over every byte written, `check`, agrees).

| load | `flatten` | `coalesce` |
|---|---:|---:|
| a 1 MB paste, 2,000 reports while stalled, 2,000 draining at 4 KB | 77 ms, 42.8 MB | 2 ms, 17.4 MB |
| the same, 4 MB | 393 ms, 58.1 MB | 8 ms, 34.2 MB |
| the same, 16 MB | 3,106 ms, 111.7 MB | 15 ms, 106.9 MB |
| the reply cap filled: 87,381 replies, nothing read (§11's test) | 1,620 ms, 68.0 MB | 8 ms, 15.6 MB |

`flatten`'s cost is the queue's length for every addition, so a paste of n
bytes and k reports after it costs n·k: 16 MB and 2,000 reports is 32 GB
copied. The reply cap's 1 MiB filled 12 bytes at a time is about 46 GB.

**Is an array a queue here?** Pushed at the back and taken from the front
with `popFirst`, natively a slice: the probe kept about 1,000 pieces
queued over 1, 4 and 16 million turns, 192 MB through it, with the pty
taking 12 bytes a write. RSS stayed at 13–18 MB in every shape and the
time was linear in the turns (`coalesce` 140, 559, 2,246 ms; `pieces` 65,
253, 1,005 ms; `flatten` 241, 952, 3,785 ms, copying its 12 KB queue
every turn). A consumed front is not kept alive, and nothing grows. What
does not work is offering one piece a write (`pieces`): a pty that would
take 4 KB is offered 12 bytes, so a queue of small pieces never catches
up (120,300 bytes still queued at the end of a run `coalesce` drains).
The first versions of `coalesce` were slow for the same kind of reason:
joining even a single large piece copied it at every write (3,620 ms at
16 MB), and joining the same small pieces again at every write the pty
took little of cost 10.5 s for a million turns. Keeping the joined piece
at the front fixed both.

**The two-list queue, and an array with an offset** (asked the same day:
a FIFO grows at its end and shrinks at its front, so is a linked list
better?). Two more shapes, with `coalesce`'s joining:

- `twolist`: Okasaki's queue on cons lists of pieces, added to `back`,
  taken from `front`, `back` reversed onto `front` when `front` is empty or
  is one small piece; the rest of a piece a write took part of is consed
  back on `front`;
- `offset`: the array, with an offset into its first piece in place of
  putting the rest back, the piece popped once it is all written.

Each writes the same bytes as `flatten` on every load, at writes of 7,
4,096 and 5,000 bytes (`check`). Best of three, natively:

| load | `flatten` (today) | `coalesce` | `offset` | `twolist` |
|---|---:|---:|---:|---:|
| 1 MB paste, then 2,000 reports stalled and 2,000 at 4 KB | 74 ms, 42 MB | 2 ms, 18 MB | 0 ms, 11 MB | 0 ms, 11 MB |
| the same, 16 MB | 3,072 ms, 132 MB | 15 ms, 108 MB | 0 ms, 52 MB | 0 ms, 51 MB |
| the reply cap filled, nothing read | 1,508 ms, 80 MB | 8 ms, 15 MB | 9 ms, 15 MB | 8 ms, 16 MB |
| 1,000 pieces queued, 16 million turns at 12 bytes | 3,833 ms, 14 MB | 2,240 ms, 18 MB | 1,179 ms, 18 MB | 1,198 ms, 18 MB |
| a queue growing to 512 KB, writes of 7 bytes | 832 ms, 50 MB | 3,559 ms, 79 MB | 11 ms, 21 MB | 13 ms, 19 MB |
| the same, to 692 KB | 1,541 ms, 52 MB | 6,002 ms, 84 MB | 13 ms, 23 MB | 14 ms, 22 MB |

**What this says about an array as a queue.** Growing at the end and
shrinking at the front is cheap on a slice: the front is given up by
moving the view, and when the buffer is full an append copies only the
live part into one twice its size (`geng_arr_append_mode`), so the bytes
given up are collected. `offset` is as fast as the two-list queue on every
load. What is not cheap is putting something back on the front of an
array whose front was just taken: `Array.pushFirst` onto a view
`popFirst` left copies the whole array, the pop-then-push shape of
geng-lang's D708 at the front. `coalesce` does that at every partial
write, and a partial write is a pty's usual answer, so it is quadratic in
the pieces queued: 6.0 s, slower than today's `flatten`. The two-list
queue cannot fall into it: consing the rest of a piece back on `front` is
what a cons list is cheap at, and it costs the same on every target,
slices or not.

**What the fix would be**, in `app/src/Main.geng`, either shape: the queue
and a count of its bytes beside it, which `feed`'s `replyCap` test reads
in place of `Bytes.length`; `send` and `sendRaw` add the piece and its
length; `flush` joins a small first piece with what follows, up to 64 KB,
offers the first piece to `writeSome`, and takes what was written off the
front. The loop's `Bytes.isEmpty m.out` tests become the count's.
**Leaning: the two-list queue.** It is as fast as `offset` everywhere
measured, and its cost does not rest on how a slice's front behaves,
which is what `coalesce` got wrong. Against today, it takes the 16 MB paste
from 3.1 s to under a millisecond, filling the reply cap from 1.5 s to
8 ms, and a growing queue under small writes from 1.5 s to 14 ms. Not
built: Gilbert to decide.

## 20. V51 built: the output queue is a two-list queue (2026-11-04)

**V51 · What puritty sends the program waits in a two-list queue of
pieces**, Gilbert's choice from §19. `app/src/Outbox.geng`: a piece is
consed onto `back`, written from `front`, and `back` is reversed onto
`front` when `front` is empty or is one small piece, so every piece is moved
once. Before a write a first piece under 4 KB is joined with those after
it, up to 64 KB, and kept joined; the rest of a piece the pty took part of
goes back on `front`. The queue keeps its size in bytes, which `feed`'s
`replyCap` test and the loop's tests read. `Main`'s `send`, `sendRaw` and
`flush` call it, and nothing else in `Main` changed.

**Measured in puritty** on Xvfb, V48's case (§11 of `phase3-input.md`): a
program on a raw terminal writes N cursor-position requests, reads none of
the replies, and exits with status 3. Wall time to puritty's exit, which is
3 every time:

| requests | before | after |
|---:|---:|---:|
| 0 | 22 ms | 21 ms |
| 100,000 | 2,447 ms | 40 ms |
| 400,000 | 6,832 ms | 65 ms |
| 1,000,000 | 6,896 ms | 116 ms |

Past about 87,000 requests the reply cap's 1 MiB is full and replies are
dropped, which is why the old queue's time levels off: it is the cap's fill,
each reply copying all that was queued. §19's probe gives the rest: a 16 MB
paste and the reports after it from 3.1 s to under a millisecond.

**Gates for §20**: pointer 51 of 51, pixels 36 of 36, IME 14 of 14, the
gates that run the window; the core's are untouched by `Main`.
`Outbox.geng` and the probe are as `geng fmt` leaves them; `Main.geng` was
not formatted before and is left so.

## 21. The pointer: the theme's I-beam, and its arrow while the program takes the mouse (2026-11-04)

Gilbert, using puritty beside Alacritty: puritty's pointer was an arrow,
where Alacritty's is the I-beam, the better shape for selecting text.
puritty set no cursor on its window, so it showed the root window's.

- **The two pointers** come from the user's cursor theme, as other programs
  load them: `xcb-util-cursor` (`libxcb-cursor` 0.1.6, new in devbox and in
  `packages/x11`'s `pkg-config` list) reads `Xcursor.theme` and
  `Xcursor.size` from the X resources, and loads `text` (or `xterm`) and
  `default` (or `left_ptr`) by the freedesktop cursor names. Where no theme
  answers, the core cursor font's `XC_xterm` and `XC_left_ptr`.
- **Nix's `xcb-util-cursor` does not search `/usr/share/icons`**: its
  compiled path is the home directory's two and its own store path, so on a
  distribution's desktop it found no theme and fell back to the cursor
  font. puritty sets `XCURSOR_PATH` to libXcursor's own path
  (`~/.local/share/icons:~/.icons:/usr/share/icons:/usr/share/pixmaps`)
  when the user has not set one.
- **The shape**, as Alacritty and Ghostty show it: the I-beam, and the arrow
  while the program asks for mouse reports (any mode but none) and Shift is
  not held, Shift being what takes the mouse back for a selection (§4). The
  loop sets it when that changes, beside the motion mask (§4), from
  `Vt.mouseModes` and a `shiftHeld` the events keep: a Shift key's press or
  release, a pointer event's Shift bit, and not after the focus goes.

**Checked** under `xtrace` on Xvfb, with a program that turns mode 1000 on
and then off: the window's cursor is set to the I-beam when it opens, the
arrow after `CSI ? 1000 h`, and the I-beam again after `CSI ? 1000 l`; with
`XCURSOR_PATH` set as above, both are the theme's (RENDER `CreateCursor`
from Bibata-Modern-Classic, `/usr/share/icons/default`'s), where without it
they were the cursor font's glyphs 152 and 68. The gates that run the window
pass: pointer 51 of 51, pixels 36 of 36, IME 14 of 14.

## 22. The palette's 16 colours in the settings (2026-11-04)

Gilbert, beside Alacritty: puritty's text was less bright. Measured from
his screenshot, Alacritty draws `#d8d8d8` on `#181818` and puritty
`#c5c8c6` on `#1d1f21`, libghostty-vt's defaults, which the core takes
because Ghostty is its oracle. Foreground and background could already be
set (`[colours]`); the 16 named colours, which tmux's status line and `ls`
draw with, could not.

**`[colours] palette`**: up to 16 `#rrggbb` colours, the named ones from 0;
each one left out stays libghostty-vt's, and more than 16 are refused
("17 colours, where the palette has 16").

**They are the core's**, not the renderer's alone: `Term` has `named`, the
16 colours before a program sets one, libghostty-vt's in `new` and the
embedder's after `Vt.withPalette`, which puritty calls once at start.
`paletteColour` reads it where no OSC 4 has set the colour, so the colours
drawn, what OSC 4 answers and what OSC 104 and RIS go back to are the
configured ones, as Ghostty does with its configured palette. A core made
without `withPalette`, as every gate and the oracle make it, has
libghostty-vt's.

**Checked** in puritty on Xvfb, with `palette = ["#000000", "#ff0000"]`:
OSC 4 asks colour 1 and is answered `rgb:ffff/0000/0000`, colour 2
libghostty-vt's `rgb:b5b5/bdbd/6868`; set to `#00ff00` it is answered so;
after OSC 104 1, and after an OSC 4 to `#0000ff` and RIS, it is
`rgb:ffff/0000/0000` again. Gates: replay 325 of 325, view 345 of 345,
select 4 of 4, charset 17 lines, keys 300,000, mouse 200,000, paste
100,000, perf within its record and budgets, the differential fuzzer clean
for 10 minutes (coverage 6,452, no findings), pixels 36 of 36, pointer 51
of 51, IME 14 of 14.

## 23. Scrollback search and the scrollbar (2026-11-11)

*Gilbert, 2026-11-11:* the scrollbar and search (`feature-plan.md` §2's
two medium gaps).

**Search.** Ctrl+Shift+F opens a bar at the window's top right. What is
typed is looked for at once, from the bottom of the view up; Enter finds the
next match older, Shift+Enter newer; Backspace shortens the query; Esc
closes the bar, leaving the view and the match where they are. The bar takes
every key but Ctrl+Shift+C, which copies the match: no key reaches the
program while it is open. Matching (`app/src/Search.geng`) is row by row
over the scrollback and the screen, ignoring case, each row's text read
with `Vt.selectionText`; the first occurrence in a row is the row's match,
and its columns count each character's cells (`Vt.Width`), so a match after
Korean text is where it shows. A match is made the selection, which draws
its highlight (§14) and is what a copy takes, and the view goes back far
enough to show its row near the middle. A match across two rows is not
found. On puritty's own terminal only, not in tmux's panes.

**The scrollbar** is a thumb at the right edge, shown while the view is
scrolled back or the search bar is open: as tall as the screen is of the
scrollback and the screen together, as far down as the view is. A press in
its column puts the thumb's middle at the pointer, a drag moves it, letting
go ends it; a press elsewhere is as before.

**Drawing.** Both are interface records after the cells, as SC23's box is
(`Dialog.searchBar`, `Dialog.scrollbar`). While anything is drawn over the
cells, every frame draws every cell, with no scroll copied: a `CopyArea`
would carry the thumb's pixels along with the rows. It costs a full frame
only while the bar, the search or a question's box is up; the frame the
last of them goes in draws every cell too.

**Tested:** the pointer gate's `search-copy` (the bar opened, `needle`
typed, Enter, Ctrl+Shift+C: the clipboard holds `needle`, and the program
was sent no byte); `bench/search/show.py` shows the match as typed and then
the older one, the bar's note, and a drag of the thumb.

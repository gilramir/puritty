# Phase 3 · Input, clipboard, IME, EUC-KR: a survey

Status: **survey begun 2026-11-02; nothing of phase 3 is built. Its seven
leanings wait on Gilbert (§9).** Phase 3 of [`geng-plan.md`](geng-plan.md)
§6 starts here, as every phase does, by measuring before building. It asks
first the things that decide the shape of the rest: whether the IME matrix
can be tested at all, what XIM costs a key here and over `ssh -X` (§3); what
a kitty encoder needs from the C (§4); whether a paste fits the loop as it
is (§5); what an EUC-KR decoder written in Geng costs beside the core (§6);
and where the font's size comes from (§7). Mouse reports, selection,
the clipboard and OSC 52 come after (§8). As with every survey here, these
sections stay as written when the work lands below them.

Phase 2's §14 already settled the keyboard's path for a shell: xkbcommon-x11
in C, the encoding in Geng (V30), a frame at once after a key (V31).

---

## 1. What was asked, and what was found

| asked | found | § |
|---|---|---|
| Can the IME matrix (fcitx5-hangul, ibus-hangul, Mozc, pinyin) be tested by a script? | **Yes, all six pairs**, fcitx5 and ibus each with Korean, Japanese and pinyin, built from the devbox's nixpkgs pin, on Xvfb, typed into with xdotool. Each run logs every callback in order | 3.1 |
| Do the IMEs order a commit and the key that ended it as S§9 needs? | **Yes, every IME, in every case tried**: Return, Left and Ctrl+C after a syllable, a syllable split by its next vowel. The commit comes before the key given back. The two frameworks disagree on whether the preedit ends before or after the commit | 3.2 |
| What does XIM cost a key? | **Locally 0.15–1.6 ms. Over `ssh -X` from gmktec7, 16–24 ms a key event**, against a 5 ms ping: xcb-imdkit's client makes five or six blocking round trips for each, four of them avoidable. A key without the IME was one round trip (phase 2 §14.3) | 3.3 |
| What does the kitty encoder need from the C? | Ghostty's encoder takes **a physical key, press, repeat or release, sided modifiers with the locks, the modifiers the layout consumed, the text, and the unshifted code point**. The C sends a keysym, four modifiers and text. libghostty-vt's key, mouse and paste encoders are an oracle for a gate | 4 |
| Does a paste fit the loop? | **No, as the loop is written.** A pty takes 15–37 KB and then stops until the program reads; a program that echoes stops reading until visiterm reads. Main waits for each write, so a paste of more than that into `cat` hangs the window. A write raced and cancelled cannot say how much it wrote: a gap in `os` | 5 |
| What does an EUC-KR decoder in Geng cost? | **+12–15% on `gitlog`, +72% on Korean text**, beside the core. Geng is near C's floor on ASCII and 4× it on Korean, because user code has no byte writer | 6 |
| Where should the font's size come from? | **`Xft.dpi`, then the monitor's size from RandR, then 96.** Gilbert's desktop says 192, its monitors are 163 dpi, and the X screen says 96 | 7 |

---

## 2. How it was measured

Machine as `geng-plan.md` §1.2: this machine (`nene`), AMD Ryzen 7 8845HS,
Linux 6.8. visiterm `2e3d994`, geng-lang `e13c28c3`, devbox's clang at
`-O2`. gmktec7 for `ssh -X`, as in phase 2. No other load.

The probes:

- [`../probes/ime/`](../probes/ime/): `xim`, an XIM client through
  xcb-imdkit 1.0.9 in C, as visiterm's would be: one window, an input
  context whose preedit the client draws (on-the-spot,
  `XIMPreeditCallbacks`), every key press and release sent to the IME, and
  each callback logged with its time from the key the server sent.
  `run.sh IME ENGINE SCRIPT` starts its own Xvfb (`:79`), a session bus, the
  IME with a fresh home under `.harness-work/ime`, the probe, and types the
  script with xdotool. `imes.nix` builds the IMEs from the devbox's pin:
  fcitx5 5.1.22 with fcitx5-hangul 5.1.11, fcitx5-mozc 2.30.5544 and
  fcitx5-chinese-addons 5.1.14; ibus 1.5.34 with ibus-hangul 1.5.5,
  ibus-mozc and ibus-libpinyin 1.16.5. `REMOTE=gmktec7` runs the probe there
  over `ssh -X`; `TRACE=1` puts xtrace between the probe and the server.
- [`../probes/euckr/`](../probes/euckr/): `EucKr`, WHATWG's `euc-kr`
  decoder in Geng, and `euckr`, a file decoded in 64 KB reads, alone or
  feeding the core; `floor.c` the same decoder in C. `gen.py` writes the
  index module from WHATWG's `index-euc-kr.txt` (2024-09-18) and the inputs.
- [`../probes/paste/`](../probes/paste/): `fill`, the bytes a pty's master
  takes before a write would wait.

This Mint desktop has ibus 1.5.29 installed with no engine and no Korean
locale, so the matrix runs from the pin, not from the system.

---

## 3. The IME through XIM

### 3.1 The matrix runs headless

Each IME needed one setting to behave as a desktop user's does:

- **fcitx5** starts with its engine active by `ActiveByDefault=True`, and
  sends preedit callbacks only with `UseOnTheSpot=True` in `xim.conf`.
  Without it, fcitx5 draws the preedit in a window of its own and the client
  sees only commits.
- **ibus** starts each engine in Latin or direct input: ibus-hangul needs
  the Hangul key (or Shift+Space), ibus-mozc Zenkaku_Hankaku. The script
  presses it first. ibus-libpinyin starts in Chinese.

Both frameworks negotiated **COMPOUND_TEXT, not UTF-8**, with the probe
asking for UTF-8 first. Every commit and preedit went through xcb-imdkit's
converter, and came out right for Hangul, kana, kanji and hanzi.

### 3.2 What the IMEs send, in order

`gks` is 한 on the Korean two-set layout. Every case, both frameworks:

| typed | fcitx5-hangul | ibus-hangul |
|---|---|---|
| `gks` Return | commit 한, preedit cleared, preedit done, **Return given back** | preedit cleared, preedit done, commit 한, **Return given back** |
| `gksks` (하난) | at the second `k`: commit 하, preedit 나 | at the second `k`: preedit done, commit 하, preedit start, preedit 나 |
| `gks` Left | commit 한, …, Left given back | …, commit 한, Left given back |
| `gks` Ctrl+C | commit 한 on **Control_L's press**, then Control_L and `c` given back | the same |
| `gks` BackSpace BackSpace Return (fcitx5) | 하, then ㅎ, then commit ㅎ, Return given back | |

- **The commit always comes before the key that ended it.** Neither IME
  forwards a key during composition. Neither drops one.
- **The two orders differ inside one key**: fcitx5 commits and then clears
  the preedit; ibus clears and ends the preedit and then commits. visiterm
  takes both: it holds the preedit as its own string, a commit never
  touches it, and each draw replaces `[first, first + length)`. A preedit
  done with a commit still to come draws nothing in between, since nothing
  is drawn until the frame after the key.
- **A key the IME consumed is not given back**; its release is.
- **Japanese and pinyin carry clauses.** Mozc's feedback marks the target
  clause reverse (1) and the others underlined (2) on both frameworks
  (`私は日本語`: 2 2 1 1 1 after Right). fcitx5's pinyin marks all reverse
  and underlined (3); ibus-libpinyin underlined (2).
- **The caret does not say where the target clause is.** fcitx5's Mozc puts
  it at the target clause's start (2); ibus's at the preedit's end (5). The
  candidate window's place has to come from the reverse run.
- **fcitx5 sends one feedback value more than the preedit has
  characters**, a trailing 0; ibus sends exactly one each.
- **The first key of a session is slow**: fcitx5's pinyin took 39 ms and
  Mozc 7 ms to answer it, loading their engines.

### 3.3 What a key costs: round trips

Locally, the IME answers a key event in 0.15–0.5 ms on fcitx5 and 0.6–1.6
on ibus.

Over `ssh -X`, the probe on gmktec7 and fcitx5-hangul here, two runs of
`gksgks` Return `abc`:

| | |
|---|---|
| ping, the same minute | 4.8–6.0 ms |
| a key event to the IME's first answer | 15.6–24.3 ms, median about 21 |
| Return to Return given back | 34.3, 34.7 ms |

xtrace between the probe and the server, locally, shows why: **five
replies waited for on a press, six on a release** (nine on Return, which
also commits). In xcb-imdkit's `src/message.c`, every message longer than
20 bytes goes as a property, and sending one makes, each waiting for its
reply:

1. `InternAtom` of `_clientN`, a name that rotates through a fixed set and
   could be interned once;
2. `GetProperty` of that property, whose answer is thrown away;
3. `ChangeProperty`, checked (`xcb_request_check`, a round trip);
4. `SendEvent`, checked.

Reading the IME's answer is a fifth (`GetProperty` of the property it
names). A key event is 44 bytes, so every key pays all of them, twice with
its release. The first four are xcb-imdkit's choices; the fifth is the
protocol's for a reply that does not fit a ClientMessage.

Two more things follow from the same code:

- **The waits are inside the calls.** `xcb_xim_forward_event` and
  `xcb_xim_filter_event` block until their replies come. On visiterm's one
  loop, 20 ms a key over `ssh -X` is 20 ms in which no output is read and
  no frame drawn.
- **ETX is not `ssh -X`.** There the IME runs in the desktop session on the
  same host as visiterm and the X server, so each round trip is local. It
  is measured in phase 6.

xcb-imdkit's tracker has no report of this. A patched client keeps one
round trip a key event: the IME's answer read back. Its interned atoms are
kept from the connection, the `GetProperty` before an append goes, and the
two requests are sent unchecked.

### 3.4 A freeze in the IME's server

xcb-imdkit's server side, which fcitx5 links, has a bug closed on
2026-10-09 (fcitx/xcb-imdkit#17, commit 621048bd) and in no release: when a
client destroys an input context while a key is in flight in sync mode,
the server never leaves sync mode for that client, and every later key is
swallowed until the client restarts. The pinned 1.0.9 has it, as will the
fcitx5 on any desktop for some time. visiterm cannot fix the server, but it
can avoid the trigger: an input context is never destroyed while a key
sent to it has no answer, and focus changes unset the context's focus and
keep it.

---

## 4. Keys for the kitty protocol

libghostty-vt v1.4.0, the core's oracle, has encoders in its C API:
`ghostty_key_encoder_encode`, `ghostty_mouse_encoder_encode`,
`ghostty_paste_encode` and `ghostty_focus_encode`. Their options are the
modes visiterm's core already keeps: DECCKM (1), the keypad (66), 1035,
1036, `modifyOtherKeys` 2, the kitty flags of the stack top
(`Vt.Term.Keys`), and DECBKM. A gate like the replay gate's, the Geng
encoder against Ghostty's for every key and mode, needs no new oracle.

Ghostty's key event has more than the C sends now:

| Ghostty's event | the C's record now | from xkbcommon |
|---|---|---|
| physical key, W3C code (`GhosttyKey`, 180 of them) | — | the keycode: evdev's code is X's less 8, mapped by a table of evdev codes to W3C codes |
| press, repeat, release | press only | X sends releases; repeats need XKB's detectable autorepeat (`PerClientFlags`), else a repeat is a release and a press |
| shift, ctrl, alt, super, caps and num lock, and the side of each | shift, ctrl, alt, super | `xkb_state_mod_name_is_active`, the side from the key that set it |
| modifiers the layout consumed | — | `xkb_state_key_get_consumed_mods2` |
| text | text | `xkb_state_key_get_utf8` |
| unshifted code point | — | the keysym at level 0, `xkb_keymap_key_get_syms_by_level` |

**A key the IME gives back is read with its own event's modifiers.** It
comes back up to 34 ms after it was pressed over `ssh -X` (§3.3), after
later keys may have changed the modifiers that the XKB state the C keeps
tracks. The record is built from the given-back event's `state` field, the
modifiers the server saw at the press.

---

## 5. Paste, and a write that waits

A pty's master takes this much before a write would wait, nobody reading
the master (`fill`, 4 KB writes of 64-byte lines):

| program on the pty | cooked (echo on) | raw |
|---|---|---|
| `cat` | 21,504–25,088 B | 36,864 B |
| `sleep 100`, which never reads | 15,360 B | 15,360 B |
| `cat >/dev/null` | 1 MB and more | |

Main's loop (`app/src/Main.geng`, `handle` and `feed`) writes a key, a
focus report or the core's replies with `File.write` and waits for it to
finish before it reads again. `os` makes the master non-blocking, and a
write that would block waits in the scheduler's `poll`, so the loop is not
stuck in a syscall. But it is stuck in the task: a paste larger than the
table's first column into `cat` fills the pty; `cat` then blocks writing
its echo, which visiterm is not reading; and visiterm waits for a write
`cat` will never make room for.

The way out is a write the loop can race with its read, as the read is
raced now. That is where `os` falls short:

- `Os.File.write` answers `{}` when every byte is written. A write that
  loses a race is cancelled (`pending_stop` in `geng_os_file.c`) and says
  nothing of the bytes it had written. Written again, the paste doubles
  them; not written again, it loses the rest.
- This is D1045's question for reads (`m3-os.md` §OS27), the other way
  round: a branch that loses a race must say what it did.

Two shapes would do. **A write that answers how much it wrote** and never
waits, with a separate wait for the handle to take bytes again that the
loop races; or **D1045's give-back for writes**, a cancelled write
answering the count it reached. The first is simpler to reason about and
is what bracketed paste's slicing wants anyway: the loop hands the pty one
slice at a time and keeps the rest in its model.

The core's replies have the same shape, with less at stake: a program that
asks for replies and never reads them can hold the loop the same way, after
15 KB of them.

---

## 6. EUC-KR: a decoder in Geng

WHATWG's `euc-kr` decoder, which takes the CP949 superset (C§10.3): a lead
0x81–0xFE and a trail 0x41–0xFE look up the index; a trail below 0x80 that
makes no code point is read again on its own, so a stray lead never
swallows an ESC; a lead that ends a read is kept for the next. The index is
one literal of 23,940 code points (126 leads × 190 trails) in a generated
module, `EucKrIndex`, which compiles with the rest in 8 s.

Inputs, made by `gen.py`: `gitlog`, harness/perf.py's 25.8 MB in CP949;
and 24 MB of Korean lines, words of KS X 1001 syllables with some Hanja,
symbols, file names and SGR colours. Both decode to exactly what Python's
CP949 makes of them. Three runs each, in ms:

| | gitlog | Korean |
|---|---|---|
| C, the floor | 12.2–12.4 | 28.5–35.3 |
| Geng, every byte built | 64–71 | 98–101 |
| Geng, every ASCII run passed on as a slice | 22–23 | 214–217 |
| **Geng, ASCII runs of 16 bytes or more as slices** | **15–17** | **120–121** |
| the core alone, fed the UTF-8 | 100–104 | 165–167 |
| the 16-byte form, then the core | 112–117 (+12–15%) | 283–284 (+72%) |

- **ASCII costs little.** Most of an EUC-KR pane's output is ASCII, and
  there the decoder is within 1.3× of C and adds 12–15% to the core.
- **Korean text costs 4× C.** User code has no byte writer: `core` keeps
  `Bytes.Transient` to itself (D233), so the decoder pushes each byte into
  an `Array.Builder UInt8`, which `toArray` and `Bytes.fromUInt8s` then
  copy twice. Slicing every ASCII run is worse on Korean, where a space
  between short words makes a piece of three bytes for `Bytes.flatten`.
- **Is +72% on Korean text a problem?** 24 MB of Korean through `cat` takes
  0.28 s instead of 0.17. EUC-KR panes are the RHEL8 users' legacy
  programs, whose output is mostly ASCII. It is a cost to record, not one
  that blocks.

Not measured yet: the encoder (keys, IME commits and paste go out through
it, a few bytes at a time) and the corpus of C§10.5.

---

## 7. The font's size

Gilbert found 11 points very small on gmktec7's desktop (`renderer.md`
§R18): the C sizes the font at a fixed 96 dpi. What that desktop says:

| source | says |
|---|---|
| `Xft.dpi` in `RESOURCE_MANAGER` (`xrdb -query`) | **192** |
| RandR: two 3840×2160 monitors of 597 × 336 mm | 163 dpi |
| the X screen's size (`xdpyinfo`): 7680×2160 over 2032 × 571 mm | 96 |

The screen's size is the X server's arithmetic for 96 dpi, and says
nothing. `Xft.dpi` is what the desktop's scale setting writes, and what
GTK, Qt and Xft programs size their fonts by, so visiterm at 11 points
would match them. The order: `Xft.dpi` if set, else the RandR size of the
monitor that holds the window, else 96. Over `ssh -X` both are read from
the display's server, so they are the desktop's, as they should be.

---

## 8. Not measured yet

- **Mouse reports** (1000–1006, 1015, 1016): the core keeps the modes;
  the encoder is Ghostty's oracle's too (§4).
- **Selection and the clipboard.** X selections in C: `SelectionRequest`
  answered from the selection's text, `INCR` for large ones, `UTF8_STRING`
  first (C§10.3 rule 7). Thai word selection (C§8).
- **OSC 52.** The core drops an OSC longer than 2,048 bytes (Ghostty's
  limit for the commands it takes), so a clipboard write needs a cap of its
  own, and a read needs a setting (S§9).
- **The preedit drawn**: shaped, wrapped, clause styles, as an overlay in
  the display list (C§7.4).
- **The keymap race** from `renderer.md` §R18, the time to rasterise a
  screen of new ideographs in daily use (V27), and per-range font settings
  (V42): all phase 3's exit, measured as they are built.
- **The IMEs on a real desktop and on ETX** (phase 6, with ibus 1.5.19).

---

## 9. For Gilbert

1. **XIM through xcb-imdkit, with its client's round trips patched
   away.** The cost now is 16–24 ms a key event over `ssh -X` (§3.3),
   paid inside the call on the one loop. Leaning: vendor xcb-imdkit at a
   pinned commit with a patch, as the oracle carries Ghostty's: interned
   atoms kept, no `GetProperty` before an append, unchecked requests. That
   leaves one round trip a key event. A report goes in `docs/upstream/`
   for xcb-imdkit's maintainers, kept for you to decide on. Writing our own
   XIM client instead is a larger piece of C for the same result.
2. **An IME gate.** `harness/ime.py` runs the six pairs of §3.1 on Xvfb
   with scripts of §3.2's cases, against visiterm itself, and pins what the
   program on the pty receives and what the preedit overlay shows. Leaning:
   yes, with the probe's settings made the gate's (§3.1).
3. **Ordering as §3.2 found it.** visiterm holds the preedit as its own
   string, changed only by draws; a commit goes out through the key path
   whenever it comes; a key given back is encoded from its own event's
   modifiers (§4); the candidate window goes to the reverse run, else the
   caret; an input context is never destroyed with a key in flight (§3.4).
   Leaning: yes.
4. **Keys: the C sends Ghostty's event, the encoder stays Geng's.** The
   record grows to §4's fields, with XKB's detectable autorepeat on, and a
   key gate holds the Geng encoder to libghostty-vt's for legacy, kitty and
   `modifyOtherKeys`, with mouse and paste in the same gate. Leaning: yes
   (V30 stands).
5. **A write the loop can race** (§5): a geng-lang decision in `os`.
   Leaning: `Os.File` gains a write that takes what the handle takes now
   and answers the count, and a wait for the handle to take more; the loop
   keeps what is left to write in its model and races the wait with its
   read. Paste, replies and keys all go that way.
6. **EUC-KR's decoder in Geng**, the 16-byte form (§6), at +12–15% on ASCII
   and +72% on Korean text. Leaning: yes, and register in geng-lang that
   user code has no byte writer, which is what Korean text pays for.
7. **The font's size from `Xft.dpi`, then RandR, then 96**, and a zoom at
   run time (Ctrl+= and Ctrl+−, Ctrl+0 to reset) that resizes the font and
   keeps the window's pixel size. Leaning: yes.

After the answers, the order to build: the write (5), since paste and the
IME both need it; keys and the key gate (4); XIM with the patch and the IME
gate (1–3); the font's size (7); EUC-KR (6); then §8's mouse, selection,
clipboard and OSC 52, each surveyed as it comes.

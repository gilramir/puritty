# Phase 3 · Input, clipboard, IME, EUC-KR: a survey

Status: **survey begun 2026-11-02; Gilbert took its seven leanings the same
day (§10), and all seven are built (§11–§15). Mouse reports, selection, the
clipboard, OSC 52 and paste come next, each surveyed as it comes.** Phase 3 of [`geng-plan.md`](geng-plan.md)
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

---

## 10. Gilbert's answers (2026-11-02)

Gilbert took all seven leanings, and for EUC-KR asked for more: **the
decoder is to be fast, and if that takes a byte builder in Geng, Geng gets
one.**

**V44 · XIM through xcb-imdkit, its client's round trips patched away.**
xcb-imdkit is vendored at a pinned commit with a patch: interned atoms kept,
no `GetProperty` before an append, requests sent unchecked. A report for its
maintainers is kept in `docs/upstream/`, not filed.

**V45 · An IME gate.** `harness/ime.py` runs §3.1's six pairs against
visiterm and pins what the program on the pty receives and the preedit shown.

**V46 · §3.2's ordering.** The preedit is visiterm's string, changed only by
draws; a commit goes out by the key path when it comes; a key given back is
read with its own event's modifiers; the candidate window goes to the reverse
run, else the caret; an input context is never destroyed with a key in flight.

**V47 · The C sends Ghostty's key event and the encoders are Geng's**, held
by a key gate against libghostty-vt's key, mouse and paste encoders. V30
stands.

**V48 · A write the loop races** (§5): geng-lang D1049. Every write the app
makes (keys, replies, focus reports, paste) is queued in its model, written
as far as the pty takes it, and the rest waits on a race branch.

**V49 · EUC-KR's decoder in Geng, made fast**: on a byte builder in `core`,
geng-lang D1050, rather than in C.

**V50 · The font's size from `Xft.dpi`, then RandR, then 96, and a zoom at
run time**: Ctrl+= and Ctrl+− by a point, Ctrl+0 back to the configured size.

---

## 11. V48 built: every write queued (2026-11-02)

geng-lang D1049 (`m3-os.md` §OS30, §OS31) gives `os` `File.writeSome`,
which never waits and answers the count, and `File.writable`, a wait that
takes nothing. visiterm's `Main` now:

- queues everything it sends in the model's `out`: keys, the core's
  replies, focus reports;
- writes `out` with `writeSome` at the top of every turn, and keeps what
  the pty did not take;
- races `File.writable` beside the read, the X events and the timer while
  anything is left, and a turn it wins only writes again;
- drops the core's replies while 1 MiB waits (`replyCap`), so a program
  that asks and never reads holds no more (S§5.1). Keys and pastes are
  never dropped.

A program that writes 400,000 cursor-position requests on a raw terminal
and never reads the replies: visiterm at `2e3d994` hangs (killed by
`timeout` after 60 s, status 124); now the program runs to its end and
visiterm exits with its status, 3.

---

## 12. V47 built: Ghostty's key event, and its encoder in Geng (2026-11-02)

**`Vt.Keys`** (`vt/src/Vt/Keys.geng`) is libghostty-vt's key encoder
(`key_encode.zig`, `function_keys.zig`) in Geng, path for path: legacy
encoding with fixterms' CSI u and `modifyOtherKeys` 2, and the kitty
protocol under any of its five flags. **`Vt.KeyTables`** is generated by
`vt/gen-keys.py` from Ghostty's `key.zig` (the 176 keys, numbered as
`GhosttyKey`), `kitty.zig` (81 entries) and `keycodes.zig` (152 evdev
codes). The function-key table is written out in Geng with Zig's own
helpers (`pcStyle`, `cursorKey`, `kpKeys`). Only what Ghostty does on macOS
is left out.

**The core keeps `modifyOtherKeys` 2**: `CSI > 4 ; 2 m` sets it, any other
`CSI > … m` and `CSI > n` clear it, as Ghostty takes them. It lives in
`modes` under a key no mode has, so that DECSTR and RIS clear it, and `Term`
has no new field. `Vt.keyOptions` gives the encoder DECCKM, DECKPAM, DECBKM,
1035, 1036, `modifyOtherKeys` and the active screen's kitty flags.

**The C sends Ghostty's event** (`packages/x11`): press, repeat or release,
with XKB's detectable autorepeat on so a held key's repeats are presses
without releases; the keycode, which the app maps through the evdev table;
the modifiers with caps and num lock, and the right-hand side of a held
shift, ctrl, alt or super; the modifiers its text consumed; its unshifted
code point (level 0); its keysym; and its text. Every key is read from a
state built from its own event's modifiers and group (V46). The text is
the keysym's own, not `xkb_state_key_get_utf8`'s, which makes Ctrl+C 0x03
before the encoder sees it; Ghostty's GTK front end hands its encoder "c",
and the encoder makes the control character.

**The key gate**, `harness/keys.py`: N random events (300,000 by default)
from a seed, over every key, action, modifier set with locks and sides,
consumed shift, composing, text of every kind (none, the key's own, shifted,
control, non-ASCII, two code points) and every option, fed to
`harness/keys/core-keys` and to `harness/oracle/ghostty-keys`, which calls
`ghostty_key_encoder_encode`. Seeds 1, 2 and 3 agree on all 300,000 cases.
One fault it found while it was built: the Zig enum's `@"fn"`, which the
generator skipped, shifting the keys after it by one (kitty's numbers for
Scroll Lock and Pause crossed). The encoder's logic agreed once the tables
did.

**In the window**, on Xvfb with xdotool and a program that records what it
receives: legacy `a`, Shift+A, Ctrl+C, Up, F5, Ctrl+Left, Alt+X, Return,
KP_1 and Escape send `a A 03 ESC[A ESC[15~ ESC[1;5D ESC x \r 1 ESC`; after
the program pushes kitty flag 1, `a`, Ctrl+C, Escape, Shift+Tab and
Ctrl+Shift+A send `a ESC[99;5u ESC[27u ESC[9;2u ESC[97;6u`.

Mouse and paste encoding, the other half of V47's gate, come with mouse
reports and paste.

**`perf.py` with the core change.** Every throughput input runs the same
instructions as recorded (+0.00%). `resize/*/long-10000` runs 312.7 M
against the record's 290.9 M (+7.48%, over its 3%), and so does the core
at `3716cb3`, where the record was written, built with today's compiler:
the move came with the compiler, and the only fork commit since the record
is D1047's (`58d59f90`, an hour later), whose root numbers gave drops to
walks that had lost them. That is by order, not measured by building the
fork before it. It is registered in geng-lang, not re-recorded here.

---

## 13. V44–V46 built: XIM in the window, the preedit drawn, the IME gate (2026-11-02)

**xcb-imdkit, patched** (V44). `vendor/xcb-imdkit` is a clone at `621048bd`
(upstream's `main`, which carries the fix for §3.4's freeze);
`packages/x11/patches/xcb-imdkit-0001-no-round-trips.patch` interns the
client's rotating property atoms once, pipelined, and sends each message
with neither request checked and no `GetProperty` before its append.
`packages/x11/build-imdkit.sh` builds it as `libvisiterm-xcb-imdkit.so`, with
an rpath and `visiterm-xcb-imdkit.pc`, a name no system library has, so
that the app can never load another. It is shared, not static: LGPL-2.1
is simplest that way, and how the RHEL8 release carries it is phase 6's
(Q12). The devbox gains xcb-util, which it needs.

What the patch buys, the probe on gmktec7 over `ssh -X` (ping 3.3–4.7 ms):
a key event's first answer from fcitx5-hangul in 3.4–14.5 ms, most
7–12, where §3.3 had 15.6–24.3. Locally, xtrace counts one reply waited
for on a key event, the read of the IME's answer, where there were five or
six; a key whose IME answers with three messages (Return: commit, preedit,
done) waits for three. The first message pays one round trip for all 1,024
atoms. The report is `docs/upstream/xcb-imdkit-client-round-trips.md`.

**The window** (`packages/x11`, V46). When an input method is there,
`open` creates an input context whose preedit visiterm draws, every key
press and release goes to it, and a key it gives back is recorded then,
read with its own event's modifiers (§12). Its commits, preedit draws and
the preedit's end are records 5, 6 and 7, in the order the IME sent them;
record 8 says the context is made. Focus changes set and unset the
context's focus, and nothing destroys it while the window lives. `drain`
flushes the connection, since a forwarded key causes no frame and so no
flush of its own: without that, the IME saw the first key only.
`X11.spot` sends the candidate window's place when it moves, the cell's
baseline. `VISITERM_NO_XIM` turns it off.

**The preedit** (V46). `Main` keeps it as code points with a feedback each,
changed only by draws (`[first, first + length)` replaced); a commit goes
to the program as text, through the same queue as keys. `Vt.View.frameWith`
draws it over the screen from the cursor: each grapheme in the core's
width, code points with no width joined to the one before, wrapping at
the row's end with a spacer before a wide grapheme that does not fit, cut
off past the last row. Its cells are core-like cells in eight style ids
`Vt.Cell.styleMax` now leaves over (32,760 instead of 32,768): reverse
video for XIM's reverse, bold for highlight, an underline otherwise. The
caret is the cursor. `View.preeditSpot` is the reverse run's start, else
the caret. The view gate draws a preedit where a case has `preedit.txt`:
`view-preedit-hangul`, `-wrap`, `-marks` (Thai marks and a combining
acute) and `-spacer`; 342 cases pass. Lowering `styleMax` shortened the
table the frame marks style ids in to below the highest cursor id, which
recorded a style twice; it is now the whole 16-bit space.

**The IME gate** (V45), `harness/ime.py`: the six pairs of §3.1, each on an
Xvfb with a session bus and a fresh home; per case a fresh visiterm on a
program that records what it receives, keys typed once visiterm says its
input context is made, and the received bytes and visiterm's IME log
(`VISITERM_IME_LOG`, each commit and each preedit as visiterm holds it)
pinned in `corpus/ime/CASE/PAIR.txt`. ibus keeps an engine's mode across
input contexts, so each ibus case switches the engine away and back
first; without that, alternate cases started in Latin. Fourteen runs:

| case | fcitx5 | ibus |
|---|---|---|
| `gks` Return | `한\r` | `한\r` |
| `gksks` Return | `하난\r` | `하난\r` |
| `gks` Left | `한 ESC[D` | `한 ESC[D` |
| `gks` Ctrl+C | `한 \x03` | `한 \x03` |
| `gks` BackSpace BackSpace Return | `ㅎ\r` | `ㅎ\r` |
| Mozc: `watashihanihongo`, convert, next clause, convert, Return | `私は日本後` | `私は日本後` |
| pinyin: `nihao` Space | `你好` | `你好` |

The logs keep §3.2's differences: fcitx5 commits and then clears, ibus
clears, ends and then commits; fcitx5's Mozc puts the caret at the target
clause, ibus's at the end. Three runs of the gate in a row: 14 of 14 each.
The pixel gate passes 36 of 36 with the new `packages/x11`.

---

## 14. V50 built: the font's size from the screen, and a zoom (2026-11-02)

`open` connects to the display before it loads a face, and sizes every face
at the screen's resolution: `Xft.dpi` from the root's `RESOURCE_MANAGER`,
else the primary monitor's width over its millimetres from RandR (1.5's
`GetMonitors`), else 96; `VISITERM_DPI` sets it outright. `X11_STATS`
prints it. A fallback face is sized as before, from the primary cell.

**`X11.zoom`** sizes every face again at a new point size, begins the glyph
set again, sets the window manager's size hints to the new cell, and keeps
the window at its size in pixels, so a `Resized` with the cells that now
fit follows. `Main` takes Ctrl with `=` or `+` (a point larger), `-` (a
point smaller) and `0` (the configured size) before the encoder sees them,
on a press or repeat without alt or super, from 4 to 96 points, and starts
the view's shadow afresh so every cell is drawn at the new size. The core's
cell size in pixels, which `CSI 14 t` and `CSI 16 t` report, stays the one
it was made with: registered.

On Xvfb, 80×24 at 11 points (`probes/dpi/setres` sets the root's resources
as `xrdb` does; the server must run with `-noreset`, or it clears them
when that client leaves):

| resources | dpi | window | terminal |
|---|---|---|---|
| none | 96 | 720×408 | 24×80 |
| `Xft.dpi: 192` | 192 | 1440×816 | 24×80 |
| `Xft.dpi: 144` | 144 | 1040×624 | 24×80 |
| `Xcursor.size` only | 96 | 720×408 | 24×80 |
| `VISITERM_DPI=120` | 120 | 880×504 | 24×80 |
| 96, then Ctrl+= twice | 96 | 720×408 | 20×72 |
| then Ctrl+0 | 96 | 720×408 | 24×80 |

RandR's branch is not exercised: Xvfb's monitor says 96, as the
fallback does. On gmktec7's desktop `Xft.dpi` is 192 (§7), so 11 points
there is drawn as GTK would draw it. The pixel gate passes 36 of 36.

---

## 15. V49 built: the EUC-KR filters, on `Bytes.Builder` (2026-11-02)

**`Vt.Charset`** (`vt/src/Vt/Charset.geng`) is the pair of filters C§10.3
designs, with WHATWG's index as `Vt.EucKrIndex`, generated by
`vt/gen-euckr.py` from `vt/data/index-euc-kr.txt` (2024-09-18):

- **the decoder** is §6's, written into geng-lang's new `Bytes.Builder`
  (D1050, `m4-visiterm.md` §VA63): a run of 16 or more ASCII bytes copied
  whole with `append`, a shorter one pushed byte by byte, a lead and its
  trail read in one step when both are in the read, each code point
  written with `pushCodePoint`; a lead that ends a read is kept;
- **the encoder** writes a code point by its first pointer in the index,
  from a reverse table built the first time it is used. Strict EUC-KR
  sends only KS X 1001 (both bytes 0xA1 and up); anything else, in either
  mode, goes as `?` and is counted.

| | `gitlog` in CP949 | 24 MB of Korean |
|---|---|---|
| C, the floor | 9.5–10.2 ms | 27.0–27.5 |
| §6, `Array.Builder UInt8` | 15–17 | 120–121 |
| `Vt.Charset` on `Bytes.Builder` | 12–13 | 64–66 |
| the core alone, fed the UTF-8 | 94–96 | 163–164 |
| `Vt.Charset`, then the core (the form before the checker's, below) | 107–110 (+14%) | 225–227 (+38%) |
| the same, final form, interleaved with the core alone on a loaded machine | +6–15% | +36–41% |

On Korean text the decoder is 2.4× C and runs at about twice the core's
speed; on ASCII, 1.3× C. `Bytes.Builder`'s first form gained 15%, since
clang inlined neither its growth test nor its UTF-8 writer; with the room
tested inline and `pushCodePoint`, 40% more (61–62 ms). The form `core`'s
refinement gate accepts, every goal proved, took the growth test out of
line again (88–90 ms) until the room was tested on locals first (64–66;
geng-lang `m4-visiterm.md` §VA63). What is left is the loop's own reads
through `Maybe`; reading with `Bytes.getAt` under the checker's proof
changed nothing measurable, and was taken out.

**The app.** `[terminal] charset` in the config (`utf-8`, `euc-kr`,
`cp949`), else the locale's codeset (`ko_KR.euckr`, `.EUC-KR`, `.CP949`,
`.UHC`); a non-UTF-8 pane's pty has IUTF8 off. Every read is decoded before
the core; everything sent goes through the encoder, which is right for all
of it while visiterm sends no raw bytes (legacy mouse reports will be the
first, C§10.3 rule 3). The count of characters sent as `?` is shown in the
window's title.

**The gate**, `harness/charset.py`, holds `harness/charset/core-charset`'s
lines to `corpus/charset/expected.txt`: C§10.5's cases (a character split
across reads, a lead before ESC, a lead before a letter CP949 takes as a
trail, a lead with no pair, 0x80 and 0xFF, two leads, box drawing and ①, a
long ASCII run between syllables; 가, 똠 and an emoji sent each way), every
line checked against Python's CP949, and all 17,048 code points of the
index sent as CP949 and read back the same.

**In the window**, a pane set to `euc-kr` on Xvfb: a program prints 가 as
`b0 a1` and asks for the cursor's position; the reply is `ESC[1;3R`, one
wide character. 가 typed goes out as `b0 a1`, and an emoji as `?`.

Not yet: ambiguous width 2 for these panes (registered, `geng-plan.md` §6
phase 3), OSC 52's payload in the pane's charset (with OSC 52), and the
C§10.5 cases that need tmux, IME commits in an EUC-KR pane on RHEL8, or a
Korean legacy program's screens (phase 6).

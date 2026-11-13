# Sounds: the bell and key sounds, a survey

Gilbert, 2026-11-13: an option to play the key sounds (`feature-plan.md`
§3), and a sound for the bell (Ctrl-G, BEL), chosen from classic
computers' bells made with ffmpeg: the Apple II's, the IBM PC XT/AT's, and
any others whose definitions can be found; "no bell" too. And how to play
sounds on Linux and Windows. Surveyed in SN1–SN5; built in SN6. Section
numbers are SN*n*.

---

## SN1 · What was found

1. **Five bells have definitions** good enough to rebuild the sound from:
   the Apple II, the IBM PC (XT and AT), the Atari ST, the BBC Micro, and
   the X server's default. Each is in `assets/sounds/bells/`, made by
   `assets/sounds/make-bells.sh` with ffmpeg from geng-lang's nixpkgs pin,
   and measured (SN2.3). The same script makes the same bytes twice.
2. **The Commodore 64 and VIC-20 have no bell** (their screen editors
   ignore CHR$(7)); the C128's and the PET's, and the Atari 400/800's
   buzzer, are not found in a source I could read (SN2.2).
3. **Playing:** on Linux, PulseAudio's simple API through `dlopen`, on a
   thread of its own, which also reaches PipeWire, and ETX's audio
   forwarding (ETX 12.0.4 and later forward a session's audio to the
   client; whether Gilbert's site has it on is a question); on Windows,
   `PlaySound` from memory, asynchronously (SN4).

---

## SN2 · The bells

### SN2.1 · Found, and made

| name | machine | the sound | from |
|---|---|---|---|
| `apple2` | Apple II | square wave, **934.5 Hz for 0.103 s**, after 10.9 ms of silence | the Monitor ROM's `BELL1` ($FBDD) |
| `ibm-pc` | IBM PC XT, AT | square wave, **896 Hz for 0.48 s** | the BIOS's `BEEP` and `WRITE_TTY` |
| `atari-st` | Atari ST | square wave, **2,404 Hz**, falling to silence over **0.52 s** (the "ping") | TOS's bell table, as EmuTOS has it |
| `bbc-micro` | BBC Micro | square wave, **516 Hz for 0.3 s** | the MOS's bell settings, OSBYTE &D3–&D6 |
| `x11` | an X server | square wave, **400 Hz for 0.1 s** | X's default bell (`xset q`: pitch 400, duration 100) |

How each was worked out:

- **Apple II.** `BELL1` waits with A=$40, then 192 times (`LDY #$C0`)
  waits with A=$0C and toggles the speaker (`LDA $C030`). `WAIT` takes
  ½(26 + 27A + 5A²) cycles, counted from its six instructions; with the
  loop's own 11 cycles, a half period is 546 cycles. The 6502 averages
  1.020484 MHz (the long cycle every line): 934.5 Hz, 96 periods, 0.1027
  s, after 11,117 cycles (10.9 ms) of silence. The ROM's comment says
  "1 KHz for .1 sec". Source: the original F8 ROM's disassembly
  (6502disassembly.com).
- **IBM PC.** `BEEP` sets the timer's channel 2 to a square wave with
  divisor 0x533 (1,331) of 1,193,182 Hz: 896.5 Hz (the XT listing's
  comment says 1000 Hz; the AT's says 896). For BEL, `WRITE_TTY` gives a
  count: the XT (1982-11-08) `BL=2`, each 65,536 turns of `LOOP`, about
  0.23 s at 4.77 MHz, so about 0.47 s; the AT of 1985-11-15 "31/64
  SECOND", 0.484 s, timed rather than counted (its 1984 BIOS, the XT's
  loop on a 6 MHz 286, gave about 0.17 s). Made at 0.484 s. Source: IBM's
  BIOS listings, as PCjs keeps them.
- **Atari ST.** The bell is a `Dosound` table: channel A's period 0x034
  (52) of the YM2149's 2 MHz clock is 2,403.8 Hz; its volume is the
  envelope (register 8 = 0x10), shape 9 (one fall, then silence), period
  0x1000: 256 × 4096 / 2 MHz = 0.524 s, in 32 steps of about 1.5 dB.
  Source: EmuTOS's `bios/sound.c` (`bellsnd`), which matches TOS's table.
- **BBC Micro.** VDU 7 plays the MOS's bell settings: channel 3, &90
  (loud), pitch 100, duration 6. Pitch 53 is middle C and 4 steps a
  semitone, so 100 is 515.7 Hz; durations are in twentieths of a second.
  The SN76489 makes square waves. Sources: the RISC OS and BBC wikis for
  OSBYTE &D3–&D6; one says the duration unit is 5 cs, which gives the
  same 0.3 s.
- **X11.** The X server's bell, played on a PC speaker: what xterm's
  bell sounds like on a desktop with no sound theme.

### SN2.2 · Looked for, not found or not made

- **Commodore 64, VIC-20:** no bell; CHR$(7) does nothing.
- **Commodore 128** (CHR$(7) rings the SID) and **PET 4000/8000** (a beep
  through CB2): the routines' values are in their ROMs; no readable
  disassembly was found.
- **Atari 400/800** (ATASCII 253, the "buzzer"): the OS clicks the console
  speaker (CONSOL) once a scan line, which I recall as about 980 Hz for
  about a quarter of a second, but the OS listing was not reachable, so it
  is not made.
- **Amiga:** `DisplayBeep` flashes the screen and makes no sound.
- **Macintosh:** its beeps are recordings Apple owns.

Any of SN2.2's can be added when its ROM is read; `make-bells.sh` takes a
line each.

### SN2.3 · Measured

Each file read back and its tone measured (rising zero crossings), so the
script's expressions are known to say what SN2.1 says:

| file | length | sound | frequency | peak by quarter |
|---|---|---|---|---|
| `apple2.wav` | 0.1136 s | 10.9 ms to 113.6 ms | 934.5 Hz | 9830, 9830, 9830, 9830 |
| `ibm-pc.wav` | 0.4844 s | 0 to 484.4 ms | 896.5 Hz | 9830 ×4 |
| `atari-st.wav` | 0.5243 s | 0 to 524.3 ms | 2403.9 Hz | 9830, 2935, 737, 185 |
| `bbc-micro.wav` | 0.3000 s | 0 to 300.0 ms | 515.7 Hz | 9830 ×4 |
| `x11.wav` | 0.1000 s | 0 to 100.0 ms | 400.0 Hz | 9830 ×4 |

All 16-bit PCM, 44.1 kHz, mono, peaking at 0.3 of full scale (9830), so no
bell is louder than another for being a square wave. A second run of the
script gave the same five files byte for byte. They are the waves as the
chips made them: no speaker's or cabinet's sound is added.

---

## SN3 · The key sounds

`feature-plan.md` §3's `keyany.wav` (G.711 mu-law, 44.1 kHz) and
`keyenter.wav` (16-bit PCM, 22.05 kHz). If every sound puritty plays is
16-bit PCM at 44.1 kHz mono, the player needs no decoder and no
resampler: the two can be converted once by the same script, kept beside
the originals.

---

## SN4 · Playing sounds

### SN4.1 · Linux

| way | for | against |
|---|---|---|
| **PulseAudio's simple API, loaded with `dlopen`** | one stream kept open, written from a thread of its own; reaches PipeWire through its Pulse layer, which Mint and RHEL 9 run, and RHEL8's PulseAudio; ETX forwards it; no new link: a machine without `libpulse-simple.so.0` plays nothing | a thread; latency is the stream's buffer, so it needs a small one (about 20 ms) for key sounds |
| ALSA (`libasound`) | lowest level | on a desktop it goes through Pulse or PipeWire anyway; no forwarding of its own |
| `paplay` or `pw-play` per sound | no code | a process for every key |
| the X bell (`xcb_bell`) | the X server's own beep, wherever the X server is | one sound, at the server's pitch; no files |

**Leaning:** PulseAudio's simple API through `dlopen`, as the key-sound
plan already says, with one change: loaded at run time, so that the RHEL8
and other distribution builds need no new library and a VM without audio
just stays quiet. The `system` bell choice (SN5) is `xcb_bell`.

### SN4.2 · Windows

| way | for | against |
|---|---|---|
| **`PlaySound` (winmm) from memory, `SND_ASYNC`** | one call, returns at once, plays in the background | one sound at a time: a new one stops the last |
| WASAPI or XAudio2 | sounds overlap, low latency | much more code |
| `MessageBeep` | Windows' own bell | Windows' sound only |

**Leaning:** `PlaySound`. A key sound cutting off the one before it is
what fast typing on a real keyboard sounds like anyway. `system` is
`MessageBeep(MB_OK)`.

### SN4.3 · Under ETX

ETX 12.0.4 and later forward a session's audio to the ETX client
("remote audio streaming"; 12.5 added it for the web client and over
UDP), so a PulseAudio stream on the VM can reach Gilbert's speakers,
where the site turns it on. In the ETX desktop, `pactl info` says whether
a Pulse server is there. If none is, the `system` bell (`xcb_bell`) goes
to ETX's X server, which may play it on the Windows side; that is also
to be tried there.

### SN4.4 · What the player must do

- Never block the window's loop: sounds go to the audio thread through a
  queue, and one that cannot play is dropped.
- **Bells come in floods** (`cat` of a binary): one bell at a time, a new
  one dropped while one plays.
- Key sounds as `feature-plan.md` §3 decided: a key that sends something,
  auto-repeat included, not modifiers alone, not a paste, one for an IME
  commit.

---

## SN5 · For Gilbert

1. **The bell setting**:
   ```toml
   [sound]
   bell = "none"     # or "system", "apple2", "ibm-pc", "atari-st",
                     #    "bbc-micro", "x11"
   keys = false
   ```
   `system` is the desktop's own (the X server's bell, Windows'
   `MessageBeep`). puritty rings nothing today. **Leaning:** `none` as
   the default, as now, so nobody hears a bell they didn't choose.
2. **Which bells.** The five of SN2.1 now; SN2.2's when their ROMs are
   read, if wanted.
3. **A volume setting** for both, now or when one turns out too loud.
4. **Linux playback** as SN4.1's leaning (`dlopen` of PulseAudio's simple
   API), Windows as SN4.2's (`PlaySound`).
5. **In the ETX desktop**: `pactl info`, and whether a sound plays there
   (`paplay /usr/share/sounds/freedesktop/stereo/bell.oga` if that file is
   on the VM).

Sources: [Apple II F8 ROM disassembly](https://6502disassembly.com/a2-rom/OrigF8ROM.html);
IBM BIOS listings in PCjs ([XT 1982-11-08](https://github.com/jeffpar/pcjs/tree/master/machines/pcx86/ibm/5160/rom/bios/1982-11-08/src),
[AT 1984-01-10, 1985-11-15](https://github.com/jeffpar/pcjs/tree/master/machines/pcx86/ibm/5170/rom/bios));
[EmuTOS `bios/sound.c`](https://github.com/emutos/emutos/blob/master/bios/sound.c);
[RISC OS OS_Byte 213](https://riscosopen.org/wiki/documentation/source/OS_Byte%20213),
[OS_Byte 214](https://riscosopen.org/wiki/documentation/source/OS_Byte%20214),
[MOS sound interface](https://kieranhj.github.io/llm-beeb-wiki/os/sound);
[ETX 12.0.4](https://blogs.opentext.com/whats-new-in-opentext-exceed-turbox-12-0-4/),
[ETX 12.5](https://wenweii.com.tw/new-features-of-exceed-turbox-12-5/).

---

## SN6 · Built (2026-11-13, Dnene54)

**Dnene54, Gilbert's answers to SN5:** the bell is `none` by default;
`system` is listed, since both platforms have a bell of their own; no
volume setting until he has heard how it works; playback as SN4's
leanings. The ETX test is his, soon.

**Settings** (a Sound page in the settings window, `docs/user/settings.md`):

```toml
[sound]
bell = "none"    # "system", "apple2", "ibm-pc", "atari-st", "bbc-micro", "x11"
keys = false
```

**The sounds in the program.** `make-bells.sh` also converts the two key
sounds to 16-bit PCM at 44.1 kHz and writes all seven WAV files into
`assets/sounds/puritty_sounds.h` (the key sounds 0 and 1, the bells 2 to
6), which both platform packages include, so a build carries them and
needs no files beside it. `Window.sound n` plays one without waiting; -1
is the system's bell.

**Linux** (`packages/x11/src/Ext/puritty_sound.c`): PulseAudio's simple
API loaded with `dlopen` at the first sound, on a thread of its own
(`geng_thread_start`, which blocks signals there), one stream kept open
with a 20 ms buffer, written 10 ms at a time so that a new request cuts
in (`pa_simple_flush`). A key sound replaces what plays; a bell while a
bell plays or waits is dropped. No audio library, or no server: nothing
plays, nothing fails. The system bell is `xcb_bell` on puritty's own X
connection. The devbox build's C library is nix's, whose loader neither
searches the system's folders nor would find a system library's own
libraries (measured with `strace`: `libpulse-simple.so.0` looked for in
the nix store only), so `app/build.sh` names nix's libpulse-simple by its
path (`PURITTY_PULSE_SIMPLE`, from the devbox's `libpulseaudio`), which
talks to the desktop's server over its socket. A distribution build
(`app/distro`) loads the system's by name.

**Windows** (`puritty_win32.c`): `PlaySoundA` from memory, `SND_ASYNC`;
a bell with `SND_NOSTOP`, so that a bell asked for while a sound plays is
dropped; `MessageBeep(MB_OK)` for `system`. `winmm` is linked.

**When.** The bell: after each turn of the loop puritty adds up every
terminal's bells (the shown tab's, the other tabs', every tmux pane's
under `-CC`) and rings once when the total rose, however many came. The
key sounds: in `key`, for a press or repeat that sends bytes (Enter its
own sound, by keysym), and one for an IME commit.

**Checked.** Sounds sent to a null sink (`PULSE_SINK`,
`module-null-sink`, unloaded after) and recorded from its monitor, so
nothing was heard here: with `bell = "apple2"`, `ibm-pc` and
`atari-st`, a program printing one BEL and, a second later, three: two
sounds each, the three BELs one, at 942, 898 and 2,404 Hz (the files'
934.5, 896.5 and 2,403.9 through the sink's resampling; the second Apple
II sound measured 1,044 Hz, a measuring artifact not looked into
further); with `keys = true`, xdotool typing `a`, `b`, Enter 0.6 s apart:
three sounds, 148, 148 and 365 ms long (the key sound, the key sound,
Enter's). The Windows build and the RHEL8 build compile and link;
`app/distro/smoke.sh rhel8` passes (its image has no PulseAudio, so it
also shows a machine without audio is fine). App tests 142 (a page more
counted), the settings gate 20 of 20 (Hosts one page further down).

**Not yet:** a volume setting (Gilbert, after trying it); Windows not
heard yet (beelink1); ETX (Gilbert's test, SN4.3); SN2.2's bells.

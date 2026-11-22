# RHEL8 and ETX: a survey, and the RHEL8 preview build

puritty on RHEL8, inside an OpenText (now Rocket Software) Exceed TurboX
(ETX) desktop on a VM with no GPU: `geng-plan.md`'s platform 2 (Q4, Q10,
phase 6). Gilbert, 2026-11-13: build a RHEL8 preview, and find out
whether puritty should draw differently under ETX, as `feature-plan.md` §6
asks for Omnissa's VDI. Section numbers are RE*n*.

---

## RE1 · What was asked, and what was found

1. **A RHEL8 preview build.** Built: `app/distro/build.sh rhel8` makes
   `app/puritty-rhel8` in an AlmaLinux 8 container (RE4). It needed one
   change to Geng's `os` (children named by pid on a kernel without
   pidfds, geng-lang Dnene53) and one to the compiler (`-ldl`). It runs in
   a clean AlmaLinux 8 under Xvfb (RE5). Not yet run on RHEL8 itself.
2. **Does ETX need puritty to draw differently?** Not known yet, and the
   answer depends on which of two ways ETX carries the screen, which only a
   measurement inside Gilbert's ETX desktop shows (RE6, RE7).

---

## RE2 · What a real RHEL8 ETX desktop has

`probes/rhel8/inspect.sh`, run by Gilbert inside his ETX desktop at work
(2026-11-13). Host names are left out.

| | measured | what it means for puritty |
|---|---|---|
| release | RHEL 8.10, kernel 4.18.0-553, glibc 2.28 | as `geng-plan.md` §1.1 expected |
| `pidfd_open` | **`ENOSYS`** | Red Hat did not take it back: `os` needs the pid fallback (RE3) |
| HarfBuzz, FreeType | 1.7.5, 2.9.1 | too old: puritty builds its own in (RE4) |
| libxcb, xkbcommon, fontconfig | 1.13.1, 0.9.1, 2.13.1 | linked from RHEL8 as they are; puritty builds against these versions |
| tmux | the RPM is 2.7, but `tmux -V` on `PATH` is **3.8** | a newer tmux is installed by hand; puritty's -CC work on 3.8 applies |
| `DISPLAY` | display 32 on a host other than the VM | **the X connection crosses the network** from the VM to the ETX server (RE6) |
| X vendor | `Rocket Software` | how puritty could tell it is under ETX (RE6) |
| extensions | GLX RANDR RENDER SYNC XFIXES XInputExtension XKEYBOARD | **RENDER is there**, which the X11 renderer needs; no MIT-SHM, Present or DRI3, none of which puritty uses |
| OpenGL | llvmpipe (software) | `geng-plan.md` Q10 confirmed: no GPU, the X11 renderer is the path |
| screen | 1902×879 at 100 dpi | the client's window, which ETX resizes |
| input method | `XMODIFIERS` empty; IBus 1.5.19 and ibus-hangul installed | IBus is not running for the session: Korean typed through an IME needs it started (RE8) |
| locales | `ko_KR.utf8`, `ko_KR.euckr` | EUC-KR is there for the charset work (D546) |
| fonts | DejaVu Sans Mono for `monospace`; Noto Sans CJK KR, JP, SC, TC; Waree for Thai | Hangul and Thai fall back to fonts that are there; Fira Code is not installed system-wide |

---

## RE3 · Children without pidfds (geng-lang Dnene53)

geng-lang `m3-os.md` §OS36 has it in full. Where `pidfd_open` answers
`ENOSYS`, `os` names each child by its pid, which is as safe against pid
reuse while only puritty reaps its own children, and learns of an exit
from `SIGCHLD`, whose handler writes to a pipe the loop waits on. glibc
2.28 also lacks `posix_spawn_file_actions_addfchdir_np`, so the parent
changes directory for the moment of a spawn. Both are held by the corpus
with the fallbacks forced on (`GENG_RUN_CFLAGS`).

---

## RE4 · The build

- **`app/distro/rhel8/Containerfile`**: AlmaLinux 8.10 (glibc 2.28, RHEL
  8.10's X libraries) with clang 21.1.8 from its AppStream, the devbox's
  version, so the release profile serves it too (`releasing.md` RL1).
  Every other distribution is a folder beside it (`app/distro/README.md`).
- **`app/distro/build-libs.sh rhel8`**, once: FreeType 2.14.3 and HarfBuzz
  13.2.1 (the sources geng-lang's nixpkgs pin has, built as
  `packages/win32/build-text-libs.sh` builds them for Windows),
  xcb-util-cursor 0.1.6 (RHEL8 has none) and xcb-imdkit with puritty's
  patches, all static, into `vendor/distro/rhel8`, with `.pc` files. FreeType's
  `.pc` gives its libtool version (26.6.20), which RHEL8's `fontconfig.pc`
  asks for.
- **`app/distro/build.sh rhel8`**: geng-lang's compiler as for Linux, its
  C compiler and `pkg-config` the container's (`app/distro/cc`,
  `app/distro/pkg-config`, run by `podman` with the home and `/tmp` at the
  same paths). 7.0 MB. `scripts/prerelease.sh` builds it profile-guided
  with the rest (`releasing.md` RL1).

What the binary asks of the machine: the newest glibc symbol it uses is
`GLIBC_2.25`; it loads libxcb and its render, render-util, randr, xkb,
shm, image and util libraries, libxkbcommon and -x11, fontconfig, libpng16
and zlib. **`inspect.sh` did not ask for xcb-util and xcb-util-image**,
which RHEL8 has as packages (`xcb-util`, `xcb-util-image`) but which a
desktop may not have installed; `ldd puritty-rhel8 | grep "not found"`
answers it.

---

## RE5 · Checked

`app/distro/smoke.sh rhel8` runs a build in `puritty-run-rhel8`
(`app/distro/rhel8/run/Containerfile`: AlmaLinux 8 with the runtime libraries
only, a font and Xvfb): `puritty -- sh -c "echo hello from puritty;
sleep 2"`. It passes when no library is missing, the line is drawn, and puritty
ends by itself once its program has, which is the child's exit seen.

- `app/puritty-rhel8`: ended after 2 s, the line drawn.
- The same built with `GENG_OS_NO_PIDFD_OPEN` (every child by pid, as on
  RHEL8's kernel): the same.

Not checked: the real 4.18 kernel (the container shares this machine's),
IBus, ETX itself, and anything beyond the smoke test. Gilbert's run on
his VM is the check.

---

## RE6 · ETX: what is known

OpenText's and Rocket's papers say little about the protocol. What they
do say:

- ETX runs a **per-user X server, `etxproxy`**, on the ETX node. puritty
  talks X to it; ETX sends the display on to the client in Windows (or
  a browser) in its own protocol, "**ThinX**", which Rocket says uses up
  to 90% less bandwidth than plain X. RE2 shows that on Gilbert's site
  that X server is on a host other than the VM, so puritty's X requests
  cross a network too, before ETX's protocol carries the result on.
- Newer ETX can encode the screen as **H.264**, on a GPU in the server
  (NVIDIA vGPU).

So there are two ways ETX may carry puritty's window, and they want
different things of puritty:

1. **As drawing (ThinX forwards something like X's requests).** puritty
   is already near the best case: it draws only the cells that changed,
   as RENDER glyph runs and fills of a few bytes a cell, and a scroll as
   one copy. Phase 2 measured about 330–380 bytes a scrolled line and
   10–14 KB a busy frame, against 4.9 MB a frame for a terminal that
   sends a picture (`phase2-window.md` §5.2). The cheap cuts listed there
   (§5.3: 16-bit glyph ids, no glyph for a blank cell, a first frame from a
   blank shadow) would help the VM-to-ETX hop as well, at no cost.
2. **As pictures (ETX renders on the server and sends images or
   video).** Then `feature-plan.md` §6's VDI list applies as it stands: no
   cursor blink (a blinking region is never still), fewer frames in a
   flood (a longer frame interval), grayscale or no text smoothing rather
   than subpixel, flat colors, and scrolling as a copy.

**Detecting ETX** is easy either way: the X server's vendor string, which
puritty reads when it connects, is `Rocket Software` on Gilbert's site (ETX
moved from OpenText to Rocket; an older ETX may say `OpenText`, not
checked). A setting would force the ETX profile on or off, as for
Horizon.

---

## RE7 · ETX: what to measure, for Gilbert

Which of RE6's two it is, and whether any setting changes the bytes, is
measured inside the ETX desktop with ETX's own numbers or the Windows
client's. The steps were mailed (2026-11-13); in short:

1. **The bandwidth meter.** ETX's client shows session statistics where
   the administrator allows it; otherwise Windows' Task Manager
   (Performance → Ethernet or Wi-Fi, "Send" and "Receive") or Resource
   Monitor's Network tab on the ETX client process.
2. **Four workloads**, each started from an idle screen, in a terminal of
   the same size (any terminal for now, then puritty once it runs there):
   an idle prompt with the cursor blinking, 30 s; the same with blink off;
   `cat` of a large text file; scrolling in `less` with Space held, 20 s.
3. **Two settings** where the terminal has them: text smoothing
   (subpixel, grayscale, none), and cursor blink.

If blink and smoothing change ETX's bandwidth a lot, ETX sends pictures
and RE6's second list is worth building, behind the vendor string. If they
barely change it, ETX forwards drawing, and puritty is already as cheap
as it gets there.

---

## RE8 · Not done

- A run on RHEL8 itself, and of `inspect.sh`'s two missing libraries.
- IBus under ETX: `XMODIFIERS` is empty, so no input method serves the
  session. Whether `ibus-daemon` can be started in it (`ibus-daemon -drx`
  and `XMODIFIERS=@im=ibus`) is Gilbert's to try; puritty's XIM client
  (`phase3-input.md`) is what would talk to it.
- The ETX profile (RE6's second list), until RE7 says it is needed.
- Packaging (an RPM, or a tarball with a `.desktop` file): phase 7.

---

## RE9 · A blank window under ETX and xfwm4 until another click (2026-11-13)

Gilbert's first run of the preview's RHEL8 build in his ETX desktop
(xfce4's xfwm4): the window opened blank, and the shell's prompt appeared
only when he clicked the xterm he had started it from. Clicking puritty's
own title bar, or another xterm, did nothing; `&` and standard input and
output sent to `/dev/null` changed nothing.

What he measured, step by step:

- `strace -f`: puritty's loop asleep in `ppoll` on four descriptors with
  no timeout: the X connection (3), the settings watcher (8, inotify),
  the terminal (9, `/dev/ptmx`) and the child-exit pipe (10, the pid
  fallback of geng-lang Dnene53). So it waited on the right things, and
  had no frame due: it believed it had drawn.
- The shell (zsh, and `zsh -f` and bash the same) on its own terminal
  (`pts/304`, `Ss+`), and its backtrace in zsh's line editor waiting for
  a key (`zleread` → `getkeycmd` → `getbyte`): it had printed its prompt.
- `xwininfo`: the window `IsViewable`. `xev` on it: the click brought it
  a `FocusOut`, and no `Expose`.

So puritty read the prompt, drew it, and the picture never reached the
screen; a `FocusOut` makes puritty draw again (the cursor's shape), and
that drawing did. The likely cause is the order: xfwm4 shows a window
started from another one late (its focus-stealing prevention), puritty
draws first into a window not yet shown, which an X server that keeps no
picture of it throws away, and ETX's server then sends no `Expose` when
it is shown (puritty repaints on `Expose`). The xterm click mattered
only as the one that took the focus from puritty.

**What changed** (`puritty_x11.c`): the whole window is drawn again from
puritty's pixmap, which holds every frame, when the window is mapped
(`MapNotify`), when it becomes visible (`VisibilityNotify`, now asked
for), and on every change of focus, whatever the server sends. And the
diagnostic log has a `window` line for each: `reparented`, `mapped`,
`unmapped`, `visibility N` (0 unobscured, 1 partly, 2 fully), `expose
X,Y WxH`, so a run at work says what the server did.

**Checked** here under Xvfb with twm: the notes in the log in the order
the server sent them (reparented, mapped, visibility 0, expose), the
prompt on the screen, app tests 142, the settings gate 20 of 20, `show.py`
mouse, menus and panes as before; the Windows build compiles. ETX itself
is Gilbert's to try: whether the window now shows at once, and what the
log's `window` lines say if it does not.

## RE10 · The blank window was the clock: a machine up 24.8 days (2026-11-14)

The same blank window on gmktec7 (Linux Mint 22.3, Cinnamon), started from
the file manager or a shell: the cursor, no prompt, until a click anywhere.
Every start did it there, and none did on nene or under Xvfb.

**What it was.** `Main`'s clock (`now`) was `Time.monotonic` in
milliseconds as an `Int`. Natively that clock counts from when the machine
started (`CLOCK_MONOTONIC`; on node, from the program's start, so the
tests never saw it). gmktec7 had been up 30.3 days, past 2^31 ms (24.8
days), so `Int64.toInt` held every reading at 2147483647. The first frame
drew (it is urgent); after that a frame is due at `last + frameMs`, which
overflowed to a negative number, which `frameAt` reads as none due, so no
timer was set and no frame drawn until an X event made one urgent. A run
with lines on standard error showed it: `ms=2147483647`, and each read of
the prompt followed by a wait with no timer. RE9's window under ETX was
most likely the same: work machines stay up for weeks. RE9's repaints on
`MapNotify`, `VisibilityNotify` and focus stay; they do no harm.

What looked like evidence and was not: with `PURITTY_NO_XIM` the prompt
showed, but only because the input method's start-up changed when the
first, urgent frame was drawn; under `strace` it hung without XIM too.

**What changed.** The window's clock counts from the window's start:
`Main.clock` subtracts `clockStart`, the system's reading when the window
began, in `Int64`, so times start at 0 on any machine. The settings
window's double click keeps its press times in `Int64`
(`SettingsProgram`).

**Left:** a window open longer than 24.8 days reaches the same limit,
since its times are still `Int` compared as they are (`ms >= at`). puritty
only ever asks how long since a moment, never how long the window has been
open, so Gilbert's choice (2026-11-14) is a clock that wraps, with every
test made on the difference (`ms - at >= 0`), as the Linux kernel compares
jiffies: next, as RE11.

**Checked:** on gmktec7, up 30.3 days, three starts (two as the file manager
starts it, `gio launch` of the desktop entry, one from a shell): the
prompt on the screen at once each time, where before every start was blank.

## RE11 · A clock that starts over, compared by differences (2026-11-14)

RE10 left a window open 24.8 days at the same limit. puritty never needs to
know how long a window has been open, only how long since a moment (a
frame, a blink, a click, a save), and those are seconds; Gilbert chose a
clock that starts over and is compared by differences, as the Linux kernel
compares its jiffies, over carrying every time in `Int64`.

**`Clock`** (app): milliseconds modulo 2^30, so a reading is never
negative and -1 still means no time where a field keeps one. `since a b` is
the difference taken modulo the period into (-2^29, 2^29], right while it
is under 6.2 days; `after t ms` a time later, modulo the period; `reached`,
`earlier`, `latest` and `soonest` (-1 for none) are made of them. Nothing
compares two times by `<` or adds them as plain `Int`s any more:

- `Main`: the frame and the synchronized update (`frameAt`; an urgent
  frame is due at the last frame's time, where it was 0), the blink, the
  timer's delay, the saves (a restored window's first save is due at its
  start, where it was 0), the settings reload, the log's writes, the
  closed tabs' order and expiry, the quiet start of a restored window, and
  the terminal's and the tab bar's double clicks (a first click is not
  half of one: `count > 0`).
- `Diag`: each line carries the time of day forward from the last line's
  by the difference, so a log runs past the clock's start.
- `TmuxMode`: the panes' numbers' end, the double click, and the clock
  mode's time of day, now a pair (a reading of the loop's clock, tmux's
  time of day then) carried forward at each tick and dropped when no pane
  shows a clock, so that tmux is asked again next time. `Tmux.Bindings`'
  `repeat-time` the same, with its own copy of the difference, since the
  tmux package does not see the app's module.

`SettingsProgram`'s double click keeps `Int64` press times (RE10) and needs
nothing. `PURITTY_CLOCK_START` sets the first reading, for a test to start
the clock just before it starts over.

**Left:** a gap is right while it is under 6.2 days. A log with no line for
6.2 days would carry its time of day forward wrongly; a tmux clock is
carried at least every minute while it shows.

*Found 2026-11-21* (the code review's MA1): the last frame's time is a gap
that is not seconds. It is written only when a frame is drawn, so a window
that drew nothing for 6.2 to 12.4 days read it as to come, and drew
nothing until the clock came round. `Clock.recent` keeps it: each turn of
the loop takes a last frame older than a frame's pacing as just that old
(an app test with a gap of seven days). The quiet time of a restored
window, the notifications' 3 s and the first save's time (MA13) are the
same kind of gap. *Fixed 2026-11-22:* `Clock.passed span due now` is
`reached`, or a due that reads as more than `span` to come, which one set
at most `span` ahead can only once it is half the period old; the three
use it (3 s, 3 s and the saves' 5 s), and the first save is due at the
turn it is asked for, not at the clock's 0, which can be 12.4 days ahead.
The other times compared with `reached` after a wait with no bound are
listed in the code review's MAN2.

**Checked:** app tests 193 (ten for the clock: a reading from a machine up
30 days, `after`, `since` both ways, `reached` before and after, `soonest`,
`latest`, and a log line's time across the start); under Xvfb with the
clock started 2 s before it starts over, a line printed before and one
after it drawn as they came, a word typed after it echoed as it was typed,
and Enter.

## RE12 · A desktop like ETX's, to test in (2026-11-17)

Gilbert, 2026-11-17: an environment like ETX's, for tests later.
`app/distro/rhel8/etx/` builds one container, `puritty-etx`, kept running
between commands:

    app/distro/rhel8/etx/etx.sh start [BINARY]   # default app/puritty-rhel8
    app/distro/rhel8/etx/etx.sh puritty [ARGS]   # standard error in share/puritty.log
    app/distro/rhel8/etx/etx.sh shot FILE.png
    app/distro/rhel8/etx/etx.sh vnc              # 127.0.0.1:5932, to look and type
    app/distro/rhel8/etx/etx.sh bytes [SECONDS]  # the X connection, each way
    app/distro/rhel8/etx/etx.sh shell | run CMD… | inspect | stop

The state (the binary, `share/` with pictures and logs, the seccomp
profile) is in `~/.cache/puritty/etx`. `ETX_DELAY_MS` (default 1),
`ETX_COMPOSITING` (`true` or `false`; unset leaves xfwm4's default) and
`ETX_TRACE` are read at `start`.

**What it copies from RE2**, each made the way the container allows:

| RE2's desktop | the stand-in |
|---|---|
| RHEL 8.10, glibc 2.28, the X libraries, HarfBuzz 1.7.5, FreeType 2.9.1 | AlmaLinux 8.10, the same package versions (`inspect` lists them) |
| `pidfd_open` answers `ENOSYS` (kernel 4.18) | the container's seccomp profile makes the three pidfd calls answer `ENOSYS` (38); the kernel is still the host's |
| the X server on another host, display 32 | Xvfb reached only over TCP as `etx-server:32`, through `xproxy.py`, which holds each direction back `ETX_DELAY_MS` |
| vendor `Rocket Software` | `xproxy.py` rewrites the vendor in the connection setup reply |
| RENDER, RANDR, SYNC, XFIXES, XInput, XKB, GLX (llvmpipe); no MIT-SHM, Present, DRI3 | Xvfb with MIT-SHM off; Xvfb cannot turn Present off, so `xproxy.py` answers a QueryExtension of Present, MIT-SHM or DRI3 "not present" (ListExtensions still names Present); Mesa's llvmpipe for GLX |
| 1902×879 at 100 dpi | the same |
| xfwm4 (Xfce) | xfwm4 with a session bus (`dbus-launch`), which its settings need |
| IBus 1.5.19 and ibus-hangul installed, not running; `XMODIFIERS` empty | the same |
| `ko_KR.utf8`, `ko_KR.euckr`; DejaVu Sans Mono, Noto Sans CJK, Waree | the same |
| tmux 2.7 from the RPM, 3.8 first on `PATH` | the same: 3.8 built from the tarball `app/tests/tmux-versions` checks |
| zsh | zsh, an empty `.zshrc` |

**What it does not copy:** ETX's own protocol to the Windows client
(ThinX, or H.264), so nothing here says what RE7 asks; the real network
between the VM and ETX's server (its latency is not measured: `ping` from
the VM to `DISPLAY`'s host would give it, and `ETX_DELAY_MS` should then be
half of it); the real kernel; how long the machine has been up (RE10:
`PURITTY_CLOCK_START` stands in); XTEST, which xdotool needs and ETX's
server may not have; and X authorization (`-ac`, none).

**`bytes`** counts what crosses the stand-in's X connection, the hop from
the VM to ETX's server, which phase 2 measured for plain X
(`phase2-window.md` §5.2). `shot` and `vnc` read Xvfb directly, so they
are not counted.

**`ETX_TRACE`** notes every request, reply, event and error with its time
and connection in `share/xtrace.txt`: what an X client waits on, as for
RE9's blank window.

### What it showed when it was first run

- **`inspect`** (`probes/rhel8/inspect.sh`) gave RE2's answers: AlmaLinux
  8.10, glibc 2.28, `pidfd_open` `ENOSYS`, tmux 3.8, the package
  versions, `ko_KR.euckr` and `.utf8`, IBus 1.5.19, the fonts, vendor
  `Rocket Software`, 1902×879 at 100 dpi, and GLX RANDR RENDER SYNC XFIXES
  XInputExtension XKEYBOARD (Present printed too, from ListExtensions,
  though a client that asks is told it is not there). The kernel line says
  the host's.
- **puritty** (the RHEL8 build of 2026-11-17): a window framed by xfwm4,
  zsh's prompt, a line typed with xdotool echoed, `tmux -V` saying 3.8,
  and 0 bytes either way over 5 idle seconds. A Hangul word sent with
  `xdotool type` did not arrive; not looked into (xdotool has to remap a
  key for a character the keyboard map lacks), and no input method runs.
- **`vnc`**: x11vnc needs `-noshm` here, since MIT-SHM is off; the port
  answered `RFB 003.008`.
- **xfwm4 starts in 0.5 s at no delay and 14 s at 1 ms.** The trace: it
  sends 6,240 GrabKey requests at start, each followed by a GetInputFocus
  it waits for (an error check), so each costs a round trip. Any X client
  that waits on the server that often is slow where the server is on
  another host; xfwm4 under real ETX would pay its own round trip the same
  number of times. A desktop started in the container is not ready to take
  a window until then, which `start` waits for.

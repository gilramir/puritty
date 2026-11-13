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

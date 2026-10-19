# Alacritty: architecture and lessons for a new terminal

Source analysed: `vendor/alacritty` at commit `54214706` (2026-10-16), version
`0.18.0-dev` (`alacritty_terminal 0.26.1-dev`). Dependency sources were read
from `~/.cargo/registry` (fetched with `cargo fetch --locked`): `vte 0.15.0`,
`crossfont 0.8.1`, `glutin 0.32.3`, `winit 0.30.x`.

Paths below are relative to `vendor/alacritty/` unless they name a crate from
the registry (`vte/src/...`, `crossfont/src/...`). Line numbers refer to that
commit. Anything not read directly in code is marked as **inference** or
**unverified**.

---

## 0. TL;DR

- Alacritty is two main crates. `alacritty_terminal` is a reusable library
  holding the PTY, VT parser glue, grid, selection, search and vi mode.
  `alacritty` is the GUI: winit window, glutin GL context, OpenGL renderer,
  input, config and IPC.
- It uses **one I/O thread per terminal window** (PTY read, parse, write) and
  **one main/UI thread** (winit event loop, input, rendering for *all*
  windows). They share the `Term` through an `Arc<FairMutex<Term>>`, and the I/O
  thread wakes the UI with a winit user event (`Event::Wakeup`).
- The parser is the external `vte` crate. Its `ansi::Processor` turns bytes
  into calls on a high-level `Handler` trait, which `Term` implements. vte also
  handles **synchronized updates (mode 2026)** inside the parser by buffering
  raw bytes. **DCS is completely unhandled**, so there is no sixel, no
  XTGETTCAP, no DECRQSS and no tmux control mode.
- The grid is a **ring buffer of `Row<Cell>`**. Scrolling the full screen is an
  O(1) rotation of a `zero` index. A cell is 24 bytes, and rare attributes
  (combining chars, hyperlink, underline colour) live behind
  `Option<Arc<CellExtra>>`. Reflow on column change rebuilds the whole buffer,
  scrollback included.
- The renderer **clears and redraws every non-empty cell every frame**: glyphs
  go into an atlas, and each cell becomes an instanced quad. "Damage tracking"
  is only used to send `eglSwapBuffersWithDamage` hints to Wayland
  compositors, not to skip drawing. There is no text shaping and there are no
  ligatures.
- Frame pacing: vsync is *disabled*. Alacritty runs its own refresh-rate timer
  (X11/Windows) or relies on Wayland frame callbacks via winit. On X11 it calls
  `glFinish()` after swap.
- GL bootstrap tries GLX then EGL on X11 (EGL then GLX with `debug.prefer_egl`),
  then OpenGL 3.3 core, then GLES 2.0, then GL 2.1. There is **no CPU/software
  renderer fallback** inside Alacritty; it needs some GL (llvmpipe works).
- Deliberately absent: tabs and splits (except native macOS tabs), ligatures,
  images, tmux control mode, and a scrollbar. The README's philosophy is
  "integrating with other applications, rather than reimplementing their
  functionality".

---

## 1. Crates, modules and threading model

### 1.1 Workspace layout

| Crate | Role | Key modules |
|---|---|---|
| `alacritty_terminal` | Headless terminal library (published on crates.io) | `event_loop.rs` (PTY I/O thread), `tty/{unix,windows}` (PTY), `term/mod.rs` (`Term` + `Handler` impl), `term/cell.rs`, `grid/{mod,storage,row,resize}.rs`, `selection.rs`, `term/search.rs`, `vi_mode.rs`, `sync.rs` (`FairMutex`) |
| `alacritty` | The application | `main.rs`, `event.rs` (winit `ApplicationHandler`, `ActionContext`), `window_context.rs` (one per window), `display/` (frame building, damage, window, hints, cursor), `renderer/` (GL), `input/` (keyboard, mouse), `config/`, `polling/` (IPC socket + signals), `scheduler.rs` (timers), `clipboard.rs` |
| `alacritty_config` | Small trait (`SerdeReplace`) for replacing config values from IPC/CLI | `lib.rs` |
| `alacritty_config_derive` | Proc macros `ConfigDeserialize` and `SerdeReplace` | lenient deserialization (see §8) |

The library/GUI split is real. `alacritty_terminal` has no dependency on winit
or GL; it talks to its host only through two traits in
`alacritty_terminal/src/event.rs`:

- `EventListener::send_event(Event)` carries events from the terminal to the UI.
  `Event` includes `Wakeup`, `Title`, `Bell`, `ClipboardStore/Load`,
  `ColorRequest`, `PtyWrite`, `TextAreaSizeRequest`, `CursorBlinkingChange`,
  `MouseCursorDirty`, `Exit` and `ChildExit`.
- `Notify`/`OnResize` carry data the other way, from the UI to the PTY. They are
  implemented by `event_loop::Notifier`.

Several projects embed `alacritty_terminal` directly (Zed, for example). That
is a good argument for keeping a clean core/GUI split.

### 1.2 Threads

| Thread | Created at | Does |
|---|---|---|
| **Main / UI** | `main.rs` → `Processor::run` → winit `run_app` | Window events, input handling, config reload, drawing for **all** windows, clipboard, scheduler timers |
| **"PTY reader"** (one per window) | `EventLoop::spawn` (`alacritty_terminal/src/event_loop.rs:205`) | `poll()` on the PTY fd, SIGCHLD pipe and a wake channel. Reads, parses into `Term`, writes queued input, handles resize ioctl |
| **"io event listener"** (Unix, one per process) | `IoListener::spawn` (`alacritty/src/polling/mod.rs`) | Listens on the IPC unix socket (`alacritty msg ...`) and the SIGINT/SIGTERM self-pipe |
| Config watcher | `ConfigMonitor::new` (`alacritty/src/config/monitor.rs`) | `notify` crate file watcher with 10 ms debounce (`DEBOUNCE_DELAY`), falling back to 1 s polling |
| Windows only: `alacritty-tty-reader-thread` / `-writer-thread` | `tty/windows/blocking.rs:63,161` | Blocking reads/writes on ConPTY anonymous pipes, bridged to `polling` (see §2.3) |
| Windows only: wait-thread callback | `RegisterWaitForSingleObject` in `tty/windows/child.rs` | Child-exit notification |

There is no render thread. Rendering happens on the main thread inside
`WindowEvent::RedrawRequested` (`alacritty/src/event.rs:249-282` →
`WindowContext::draw`).

### 1.3 Shared state and locking: `FairMutex`

`alacritty_terminal/src/sync.rs` defines:

```rust
pub struct FairMutex<T> { data: Mutex<T>, next: Mutex<()> }
lease()           -> locks `next` only (reserve the next turn)
lock()            -> lock `next`, then `data` (fair)
lock_unfair()     -> lock `data` directly
try_lock_unfair() -> try `data`
```

The `Term` lives in `Arc<FairMutex<Term<EventProxy>>>`
(`alacritty/src/window_context.rs:194`).

How the PTY thread uses it (`event_loop.rs:104-171`, `pty_read`):

1. It takes a **lease** (`self.terminal.lease()`) for the whole read burst.
   While the lease is held, any `lock()` (fair) caller blocks. The UI thread
   uses `lock()`.
2. It reads from the PTY into a **1 MiB** stack buffer (`READ_BUFFER_SIZE =
   0x10_0000`, line 24).
3. It tries `try_lock_unfair()` on the data. If the UI thread currently holds
   the data lock (mid-frame), the PTY thread **keeps reading into the buffer
   instead of waiting**. It only blocks once the buffer is full (line 142).
4. It parses the buffered bytes into `Term` while holding the lock. It stops
   after `MAX_LOCKED_READ = u16::MAX` bytes (line 27) so the UI isn't starved,
   then returns to `poll()`. Polling is level-triggered, so it comes straight
   back if more data is pending.
5. It sends `Event::Wakeup` to the UI unless every processed byte was held in
   the sync-update buffer (line 166).

The UI thread takes `terminal.lock()` (fair) in `WindowContext::handle_event`
(line 425) to process input batches, and in `WindowContext::draw` (line 390).
In `Display::draw` it **copies all renderable cells into a `Vec` and drops the
lock before issuing any GL calls** (`display/mod.rs:785-815`). The comment there
says: "Drop terminal as early as possible to free lock."

> Lesson: the critical section on the render side is "snapshot the
> viewport", not "render". The PTY side never waits for the renderer unless 1
> MiB has piled up.

### 1.4 Waking the UI and coalescing redraws

- `Event::Wakeup` goes through `EventLoopProxy::send_event` (winit user event)
  and lands in `Processor::user_event` (`event.rs:409-416`). There it sets
  `window_context.dirty = true` and calls `request_redraw()`, **only if
  `has_frame`**.
- `Window::request_redraw` itself dedupes with `requested_redraw`
  (`display/window.rs:260`).
- Window events (keys, mouse, and so on) are **queued** in
  `WindowContext::event_queue` and processed in one batch, with one terminal
  lock, on `AboutToWait` or `RedrawRequested` (`window_context.rs:401-495`).
  Input bursts therefore become a single lock acquisition plus a single redraw.
- After a frame on X11/Windows, `Display::request_frame`
  (`display/mod.rs:1435`) sets `has_frame = false` and schedules an
  `EventType::Frame` timer for the next vblank, computed by `FrameTimer`
  (§5.6). `EventType::Frame` "bypasses batching to minimize input latency"
  (`event.rs:442-450`).
- The scheduler (`scheduler.rs`) holds a sorted list of timers: cursor blink,
  frame, search-typing delay. `about_to_wait` sets winit's `ControlFlow::
  WaitUntil(next_deadline)` (`event.rs:466-490`).

### 1.5 UI → PTY channel

`EventLoopSender::send` (`event_loop.rs:389-393`) pushes a `Msg` (`Input(Cow<[u8]>)`,
`Resize(WindowSize)` or `Shutdown`) onto a `std::sync::mpsc` channel and then
calls `poller.notify()` to wake the PTY thread's `poll()`. The PTY thread
drains the channel into a `VecDeque` write list (`drain_recv_channel`, line 91).
It registers write interest only while there is pending output (lines 309-316)
and writes non-blockingly, keeping partial-write state (`Writing`).

**Terminal-generated replies take a detour.** DA, DSR, OSC colour queries and
OSC 52 reads are produced inside `Term` (on the PTY thread). They are sent as
`Event::PtyWrite` to the **UI thread**, which writes them back through the
`Notifier` channel to the PTY thread (`event.rs:1902-1926`). Query responses
therefore depend on the UI thread being responsive. **Inference:** a blocked UI
thread, for example on a synchronous X11 clipboard request, delays responses
to apps that probe the terminal.

---

## 2. PTY handling

### 2.1 Unix (`alacritty_terminal/src/tty/unix.rs`)

- **Creation** (`new`, line 195): `rustix_openpty::openpty(None,
  Some(&winsize))` creates the pty with the initial size already set. `from_fd`
  then:
  - sets `IUTF8` on the master termios (line 209) so the line discipline
    handles UTF-8 backspace correctly;
  - resolves the shell from `$SHELL` or `getpwuid_r`. On macOS it wraps the
    shell in `/usr/bin/login -flp` so the session is a login shell (lines
    166-192 / `default_shell_command`);
  - spawns with `std::process::Command`, using the slave fd as
    stdin/stdout/stderr;
  - in `pre_exec` (line 249) calls `setsid()`, `chdir`,
    `ioctl(TIOCSCTTY)`, closes the master/slave fds, and **resets
    SIGCHLD/HUP/INT/QUIT/TERM/ALRM to SIG_DFL**, because signal dispositions
    are inherited;
  - sets env vars: `ALACRITTY_WINDOW_ID`, `WINDOWID` (for X11 tools),
    `USER`, `HOME`; removes `XDG_ACTIVATION_TOKEN` / `DESKTOP_STARTUP_ID`.
    `TERM` and `COLORTERM=truecolor` are set process-wide by
    `tty::setup_env` (`tty/mod.rs:100`). `TERM=alacritty` is used only if
    that terminfo entry exists on disk (`terminfo_exists`), otherwise
    `xterm-256color`. **This matters for SSH:** remote hosts often lack the
    `alacritty` terminfo.
  - sets the master fd to `O_NONBLOCK` after spawn.
- **Child exit:** a `signal_hook::low_level::pipe` is registered for SIGCHLD
  (line 283) and connected to a `UnixStream` pair. That stream is added to the
  same `Poller` with token `PTY_CHILD_EVENT_TOKEN`. On readiness,
  `next_child_event` (line 384) calls `child.try_wait()`. The event loop
  optionally drains remaining output (`drain_on_exit`), then calls
  `terminal.exit()`, which sends `Event::Exit` (`event_loop.rs:258-271`).
- **EIO on Linux:** reading the master after the slave hangs up returns `EIO`.
  The loop ignores it and waits for the SIGCHLD event
  (`event_loop.rs:283-291`). The comment says: "This sucks, but checking the
  process is either racy or blocking."
- **Resize:** `OnResize for Pty` calls `ioctl(TIOCSWINSZ)` with rows/cols
  plus pixel sizes computed as `cols * cell_width` (line 414, `to_winsize`
  line 429). Failure is fatal (`die!`).
- **Drop:** `kill(child, SIGHUP)`, unregister the signal hook, then `wait()`
  (line 310).
- **Foreground process CWD** for "new window here": `daemon.rs:117`
  `foreground_process_path` uses `tcgetpgrp(master_fd)` and then
  `/proc/<pid>/cwd` (Linux), `/compat/linux/proc` (FreeBSD), or `proc_pidinfo`
  (macOS).

### 2.2 The `EventedPty` abstraction

`tty/mod.rs:65-97` defines `EventedReadWrite` (register/reregister/deregister
with a `polling::Poller`, `reader()`, `writer()`) and `EventedPty` (adds
`next_child_event`). The event loop is generic over it, so it works the same on
Unix and Windows.

### 2.3 Windows / ConPTY (`tty/windows/`)

- `conpty.rs:110` creates two anonymous pipes with `miow::pipe::anonymous` and
  calls `CreatePseudoConsole(size, conin, conout)`. It then spawns the child
  with `CreateProcessW` + `EXTENDED_STARTUPINFO_PRESENT` +
  `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE`. The default shell is `powershell`
  (`windows/mod.rs:159`). Argument escaping follows CRT rules when
  `escape_args` is set (`push_escaped_arg`).
- **Optional `conpty.dll`** (`conpty.rs:31-89`): if a `conpty.dll` (from the
  Windows Terminal project, paired with `OpenConsole.exe`) is found next to
  the exe or in PATH, its `CreatePseudoConsole/Resize/Close` are used instead
  of the OS ones. The comment cites "many improvements and bugfixes compared to
  the standard conpty that ships with Windows". This is a practical way to
  avoid being stuck on an old inbox ConPTY.
- **Anonymous pipes can't be polled**, so `blocking.rs` wraps each in an
  `UnblockedReader`/`UnblockedWriter`. These use a dedicated thread that does
  blocking `read`/`write` into an in-memory `piper` pipe (capacity =
  `READ_BUFFER_SIZE`, `conpty.rs:29`) and posts readiness into the `polling`
  IOCP poller through a custom `Waker`.
- **Child exit:** `RegisterWaitForSingleObject` callback →
  `GetExitCodeProcess` → mpsc + `poller.post(CompletionPacket)`
  (`child.rs:33-52`).
- **Resize:** `ResizePseudoConsole(COORD{cols, rows})` (`conpty.rs:303`).
  There are no pixel sizes. Zero-size resizes (window minimised) are filtered
  out in the UI (`event.rs:1958-1965`) "to avoid issues with Winit and the
  ConPTY".
- **Drop-order deadlock:** `ClosePseudoConsole` blocks until conout is
  drained. Dropping conout first deadlocks, so `Pty` orders its fields with
  `backend` first (`windows/mod.rs:28-30`), and `main.rs` drops the
  `Processor` before `FreeConsole` for the same reason (the long comment in
  `main.rs` near the end of `alacritty()`).
- **Inference / general knowledge, not in this code:** ConPTY is a VT
  *re-renderer*. It parses the child's output and re-emits its own VT stream,
  so some sequences may be altered or dropped before Alacritty sees them.
  `conpty.dll` + OpenConsole improves passthrough.

---

## 3. Parser path: bytes → `Handler` → grid

### 3.1 The vte crate

`vte` (maintained by the Alacritty org) has two layers:

1. `vte::Parser` (`vte/src/lib.rs`) is a Paul Williams-style DEC state
   machine. It calls a low-level `Perform` trait: `print`, `execute`,
   `csi_dispatch`, `esc_dispatch`, `osc_dispatch`, `hook/put/unhook`.
   Limits: `MAX_PARAMS = 32` (`params.rs:5`), `MAX_INTERMEDIATES = 2`,
   `MAX_OSC_PARAMS = 16`. The OSC buffer is a growable `Vec` with `std`.
   **Performance:** in the ground state it uses
   `memchr(0x1B, bytes)` to find the next ESC, validates the whole printable
   run with `str::from_utf8` and dispatches chars in bulk (`advance_ground`,
   `lib.rs:596`). Partial UTF-8 at buffer boundaries is kept in a 4-byte
   `partial_utf8` buffer.
2. `vte::ansi::Processor` (`vte/src/ansi.rs`) contains a `Performer` that
   implements `Perform` and translates it into a **semantic `Handler`
   trait**: `input(char)`, `goto`, `linefeed`, `set_private_mode`,
   `terminal_attribute(Attr)`, `clipboard_store`, `push_keyboard_mode`, and
   about 80 more. Every method has a default no-op. `Term` implements
   `Handler` (`alacritty_terminal/src/term/mod.rs:1059` onward).

The PTY thread owns `State { parser: ansi::Processor, .. }`
(`event_loop.rs:401-405`) and calls `state.parser.advance(&mut *terminal,
&buf)` (line 154).

### 3.2 Supported sequences (from `ansi.rs` dispatch tables)

- **C0** (`ansi.rs:1296`): HT, BS, CR, LF/VT/FF, BEL, SUB, SI/SO. Others are
  logged and ignored.
- **ESC** (`ansi.rs:1773+`): charset designation `ESC ( ) * + {B,0}` (only
  ASCII and DEC special graphics), IND, NEL, HTS, RI, DECID, RIS, DECSC/DECRC,
  DECALN, DECKPAM/DECKPNM, ST.
- **CSI** (`ansi.rs:1529+`): ICH `@`, CUU/CUD/CUF/CUB, CNL/CPL, CHA/HPA,
  VPA, CUP/HVP, `REP b`, DA1/DA2 `c`, TBC `g`, `CSI ? 5 W`, SM/RM and DECSET/DECRST
  `h/l`, CHT/CBT `I/Z`, ED/EL `J/K` (including `J 3` = clear scrollback), IL/DL
  `L/M`, SGR `m`, XTMODKEYS `CSI > m`, `CSI ? m`, DSR `n`, DCH `P`,
  DECRQM `$p` and `?$p`, DECSCUSR ` q`, DECSTBM `r`, SU/SD `S/T`, SCOSC/SCORC
  `s/u`, XTWINOPS `t` (only 14, 18, 22, 23), ECH `X`, and the kitty keyboard
  `CSI ? u`, `= u`, `> u`, `< u`.
- **SGR** (`attrs_from_sgr_parameters`): bold, dim, italic, underline styles
  (`4:x` single/double/curl/dotted/dashed), blink (stored, not rendered),
  inverse, hidden, strike, 16/256/truecolor via `;` and `:`, underline colour
  `58/59`.
- **OSC** (`ansi.rs:1329+`): 0/2 title, 4 palette set/query, 8 hyperlinks,
  10/11/12 dynamic colours set/query, 22 mouse pointer shape, 50 cursor
  style, 52 clipboard, 104/110/111/112 resets. **No OSC 7** (cwd), **no
  OSC 133** (prompt marks) and no OSC 9/777 notifications.
- **DECSET modes handled by `Term`** (`term/mod.rs:1934-1995`): 1 (DECCKM), 6
  (origin), 7 (wrap), 12 (blink), 25 (cursor), 1000/1002/1003 (mouse),
  1004 (focus), 1005/1006 (UTF-8/SGR mouse), 1007 (alternate scroll), 1042
  (urgency), 1049 (alt screen + save cursor; 47/1047 are *not* handled
  separately), 2004 (bracketed paste), 2026 (sync, handled in vte), and 3
  (DECCOLM, which only clears the screen; the window is not resized). Mode 4
  (IRM insert) and 20 (LNM) come via `set_mode`.
- **DCS: none.** `Performer::hook/put/unhook` only `debug!`-log
  (`ansi.rs:1311-1327`). So there is no sixel, no DECRQSS, no XTGETTCAP and
  no tmux control mode.
  - **Inference about `tmux -CC` in Alacritty:** tmux emits `ESC P 1000 p`
    and then a line protocol. vte enters `DcsPassthrough`, where every byte is
    passed to `put()` and **swallowed** until an ESC/CAN/SUB/ST
    (`vte/src/lib.rs:317-334`). Control-mode output would mostly disappear
    rather than display as garbage.
- Device attributes: DA1 replies `ESC[?6c` (VT102). DA2 replies
  `ESC[>0;<version>;1c` (`term/mod.rs:1257-1272`).

### 3.3 Synchronized updates (DEC mode 2026)

These are implemented **inside the vte `Processor`**, not in `Term`
(`vte/src/ansi.rs:35-48, 296-418`):

- When `CSI ? 2026 h` is dispatched, the processor arms a timeout
  (`SYNC_UPDATE_TIMEOUT = 150 ms`) and sets `terminated = true`, which makes
  `advance_until_terminated` return early (`ansi.rs:1603-1612`).
- While a sync timeout is pending, `advance()` does **not parse**. It appends
  raw bytes to a buffer (`SYNC_BUFFER_SIZE = 2 MiB`) and scans only the
  newly added bytes (`memchr` for ESC, backwards) for the exact 8-byte strings
  `\e[?2026h` (extends the update and resets the timer) or `\e[?2026l` (ends
  it). "We only allow EXACTLY `\e[?2026h`/`\e[?2026l` to keep the parser more
  simple."
- When the update ends, the buffer overflows, or the timeout fires, the
  buffered bytes are parsed in one go (`stop_sync_internal`).
- The PTY loop cooperates. `poll()` uses the sync deadline as its timeout
  (`event_loop.rs:228-249`); on timeout it calls `parser.stop_sync()` and
  wakes the UI. `Wakeup` is suppressed while all processed bytes are still
  buffered (line 166).
- `Term` itself ignores `SyncUpdate` in set/unset (`term/mod.rs:1993, 2043`).

> Design note: buffering *bytes* rather than freezing a *grid snapshot* makes
> sync trivial for the renderer, which simply never sees intermediate state.
> The cost is that the parse work for a big sync frame happens all at once,
> under the lock.

### 3.4 From `input(char)` to grid cells (`Term::input`, `term/mod.rs:1062`)

1. Width comes from `unicode_width::UnicodeWidthChar::width`. `None` (control
   chars) is dropped.
2. **Zero-width** chars (combining marks, ZWJ, VS16, ...) are attached to the
   *previous* cell's `extra.zerowidth`, or to the wide char if the previous
   cell is a spacer, via `Cell::push_zerowidth`. There is a cap of
   `MAX_ZEROWIDTH_CHARS = 9` per cell (`term/cell.rs:17`), added recently as a
   DoS fix (CHANGELOG: "Unbounded per-cell memory usage for zero-width cells").
3. Deferred wrap: `cursor.input_needs_wrap` is set after writing the last
   column. The next printable char triggers `wrapline()` (sets
   `Flags::WRAPLINE` on the last cell, then linefeeds). The cursor is never
   stored beyond the last column (comment at `grid/mod.rs`, `Cursor`).
4. Insert mode shifts the row right by `width`.
5. **Wide chars:** if a wide char doesn't fit in the last column, the code
   writes a `LEADING_WIDE_CHAR_SPACER` placeholder and wraps. It then writes
   the char with `WIDE_CHAR` and a following cell with `WIDE_CHAR_SPACER`.
   `write_at_cursor` (line 984) cleans up half-overwritten wide pairs.
6. Every write copies the cursor's `template` cell (fg, bg, flags, extra Arc)
   and applies the active charset mapping (DEC line drawing).

**Inference on grapheme clusters:** there is no grapheme segmentation. An emoji
ZWJ sequence becomes base emoji + ZWJ (zero-width, attached) + next emoji (new
wide cell). It renders as separate emoji, and its width can disagree with
other terminals and with applications.

### 3.5 Damage at the `Term` level

`TermDamageState` (`term/mod.rs:217`) keeps one `LineDamageBounds {line, left,
right}` per screen line, a `full` flag and `last_cursor`. Writes call
`damage_cursor()` and `damage_point()`. Scrolls, alt-screen swaps, clears and
display-offset changes call `mark_fully_damaged()`. `Term::damage()` (line
458) returns `TermDamage::Full` or a partial iterator, and the consumer calls
`reset_damage()`. Selection and vi cursor are explicitly *not* part of this;
the UI tracks them.

---

## 4. Grid, rows, cells, scrollback

### 4.1 `Cell` (`alacritty_terminal/src/term/cell.rs`)

```rust
pub struct Cell {
    pub c: char,                       // 4 B
    pub fg: Color,                     // vte::ansi::Color: Named | Spec(Rgb) | Indexed
    pub bg: Color,
    pub flags: Flags,                  // u16 bitflags
    pub extra: Option<Arc<CellExtra>>, // 8 B, null-pointer optimised
}
struct CellExtra {
    zerowidth: ArrayVec<char, 9>,
    underline_color: Option<Color>,
    hyperlink: Option<Hyperlink>,      // Arc<{id: String, uri: String}>
}
```

- A test asserts `size_of::<Cell>() <= 24` on 64-bit (`cell.rs:310-314`).
- `Flags` (u16): INVERSE, BOLD, ITALIC, UNDERLINE, WRAPLINE, WIDE_CHAR,
  WIDE_CHAR_SPACER, DIM, HIDDEN, STRIKEOUT, LEADING_WIDE_CHAR_SPACER,
  DOUBLE_UNDERLINE, UNDERCURL, DOTTED_UNDERLINE, DASHED_UNDERLINE. There is
  **no blink flag**: SGR 5 is parsed but not stored or rendered. WRAPLINE is a
  *cell* flag on the last column, not a row flag.
- `extra` is copy-on-write (`Arc::make_mut`). Since the cursor template holds
  the same `Arc`, a run of hyperlinked or underline-coloured text shares one
  allocation. Setting these back to `None` drops `extra` when it becomes empty
  (`set_underline_color`, `set_hyperlink`).
- Colours are stored *unresolved* (Named/Indexed/Spec). Resolution to RGB,
  bold-as-bright, dim, palette overrides and minimum-contrast handling all
  happen at render time (`display/content.rs:310-400`). Palette changes
  therefore need no grid rewrite.

### 4.2 `Row` (`grid/row.rs`)

```rust
pub struct Row<T> { inner: Vec<T>, pub(crate) occ: usize }
```

`occ` is an upper bound on how many leading cells were modified since the last
reset. `Row::reset` only touches `inner[..occ]`, unless the template's
discriminant (the bg colour) changed (`row.rs:73-95`). Clearing mostly-empty
rows is therefore cheap. There was a CHANGELOG fix for a "Performance
bottleneck when clearing colored rows". `Storage::swap` asserts
`size_of::<Row>() == 4 * usize`.

### 4.3 `Storage` ring buffer (`grid/storage.rs`)

```rust
pub struct Storage<T> {
    inner: Vec<Row<T>>,   // allocation
    zero: usize,          // index of the bottommost line (ring start)
    visible_lines: usize,
    len: usize,           // active lines (history + visible); may be < inner.len()
}
```

- Lines are indexed by `Line(i32)`: `0..screen_lines` is the visible area and
  negative lines are scrollback. `compute_index` maps `Line` → physical index
  with an if/else instead of `%` "to improve performance".
- `rotate(count)` and `rotate_down` are O(1) modular updates of `zero`.
- `swap(a, b)` is hand-written as four qword copies, with the comment "The
  default implementation from swap generates 8 movups and 4 movaps
  instructions. This implementation achieves the swap in only 8 movups".
- Scrollback is **allocated lazily**. `with_capacity` creates only visible
  rows, and `initialize()` grows `inner` by `max(n, MAX_CACHE_SIZE = 1000)`
  rows at a time. `shrink_lines` keeps up to 1000 spare rows before
  truncating. Shrinking `len` reduces history without freeing.
- History limit: config `scrolling.history`, default 10,000
  (`term::Config::default`), max 100,000
  (`alacritty/src/config/scrolling.rs:7`). The alt screen grid is created
  with 0 history (`term/mod.rs:415`).

### 4.4 `Grid` (`grid/mod.rs`)

Fields: `cursor`, `saved_cursor` (each a `Cursor { point, template: Cell,
charsets, input_needs_wrap }`), `raw: Storage`, `columns`, `lines`,
`display_offset` (scrollback viewing position), `max_scroll_limit`. The doc
comment at `grid/mod.rs:84-108` has a diagram of regions: visible, scroll-up,
resize buffer, uninitialised.

**Scrolling** (`scroll_up`, line 252):

- If the scroll region starts at the top, it grows history if allowed, then
  `raw.rotate(-n)` (O(1)). Lines fixed below a bottom margin are swapped back
  into place, and the new bottom lines are reset. The full-screen LF case
  costs one rotation plus resetting one row.
- Otherwise it does a swap-based O(region) shift.
- If the user is scrolled back (`display_offset != 0`), `display_offset` is
  increased so the viewport stays anchored on the same content while output
  continues.
- `scroll_down` (reverse index) uses rotation only when there's no history
  (alt screen). Otherwise it swaps.

**Alt screen:** `Term` holds `grid` and `inactive_grid` and `mem::swap`s
them (`swap_alt`, `term/mod.rs:714`). On entering, it copies the cursor and
resets the alt grid. It also swaps the **kitty keyboard mode stack** (there
is a separate stack per screen), clears the selection and marks full damage.

**Clear screen in primary (`ED 2`)** calls `grid.clear_viewport()`, which
**scrolls the visible content into history** rather than erasing it.
`ED 3` clears history.

### 4.5 Resize and reflow (`grid/resize.rs`)

`Grid::resize(reflow, lines, columns)`. `Term::resize` passes
`reflow = !is_alt` for the active grid, so **the alt screen is never
reflowed**, only truncated or extended.

- **Lines** (`grow_lines`/`shrink_lines`): the cursor is kept at the bottom.
  Growing pulls lines back from history. Shrinking pushes lines into history
  ("Terminal.app and iTerm.app ... Alacritty takes the same approach").
- **Columns, growing** (`grow_columns`): the code takes *all* rows out of
  storage (`take_all`, so the cost is O(history)) and walks them bottom-up.
  Whenever the previous (reversed) row ended with `WRAPLINE`, it pulls cells
  from the following row to fill it, then deletes rows that become empty and
  fixes `display_offset` and the cursor line. It handles wide chars
  (inserting a `LEADING_WIDE_CHAR_SPACER` when a wide char would straddle the
  edge) and the `input_needs_wrap` special case (temporarily moves the cursor
  one past the edge).
- **Columns, shrinking** (`shrink_columns`): `Row::shrink` splits off
  overflow cells (trailing empties are trimmed). Non-empty overflow is
  prepended to the next row if that row was itself wrapped, or becomes a new
  row. The result is truncated to `max_scroll_limit + lines`.
- Selection is dropped on column change and rotated on line change. Tabs are
  rebuilt. The scroll region is reset (`Term::resize`, line 655).
- The PTY is resized (`TIOCSWINSZ`) **before** `Term::resize` in
  `Display::handle_update` (`display/mod.rs:718-724`), all on the UI thread
  under the terminal lock.

Reflow edge cases visible in the CHANGELOG include "Reflow of cursor during
resize", "Crash/Freezes with partially visible fullwidth characters due to
alt screen resize" and "Selection on last line not updating correctly on
resize".

### 4.6 Memory estimate

24 B/cell × columns × (history + screen). With 200 columns and the default
10k history, that is about 48 MB at worst, plus 32 B per row. The CHANGELOG
records "Reduce memory usage by up to at least 30% with a full scrollback
buffer", which came from introducing `CellExtra`.

### 4.7 Selection, vi mode, search, hints

- `Selection { ty: Simple|Block|Semantic|Lines, region: Range<Anchor{point,
  side}> }` (`selection.rs:93-122`) is stored in grid coordinates. It is
  `rotate()`d whenever the terminal scrolls (`scroll_up_relative`,
  `term/mod.rs:778`) and dropped when cleared regions intersect it. "Side"
  (left/right half of a cell) gives correct inclusive/exclusive semantics.
- Vi mode (`vi_mode.rs`) is a separate `ViModeCursor` with motions (word,
  semantic word, bracket, paragraph, and so on). Keyboard input goes to
  motions instead of the PTY while `TermMode::VI` is set.
- **Regex search** (`term/search.rs`) uses `regex_automata::hybrid` *lazy
  DFAs*: four DFAs for forward/backward × start/end. It **feeds grid cells
  directly into the DFA byte by byte** (reversed for leftward search) without
  building a string. Line breaks only continue a match across `WRAPLINE`. The
  DFA cache size is bounded (CHANGELOG: "Excessive memory usage when using
  regexes with a large number of possible states"). Smart case: the search is
  case-insensitive unless the pattern has an uppercase letter.
- **Hints** (`display/hint.rs`) run configurable regexes (by default a URL
  regex) over the viewport ± `MAX_SEARCH_LINES = 100` and combine them with
  OSC 8 hyperlinks. Users can activate them by keyboard label (vimium style)
  or by mouse hover and click.

---

## 5. Rendering

### 5.1 Frame construction (`Display::draw`, `alacritty/src/display/mod.rs:775`)

1. Under the terminal lock, `RenderableContent::new` (`display/content.rs`)
   wraps `Term::renderable_content()` (a `display_iter` over the viewport rows,
   the cursor, the selection, colours and mode). Iterating it **skips empty
   cells and wide-char spacers** (`content.rs:161-185`). An empty cell has
   default bg, a space, no extra and no underline. For each cell it resolves
   RGB, applies inverse/dim/bold colour rules, selection, search and hint
   highlighting, and handles the cursor cell. A block cursor is drawn by
   recolouring the cell.
2. It collects all cells into `grid_cells: Vec<RenderableCell>`, pulls
   `Term::damage()` into the `DamageTracker`, calls `reset_damage()`, and then
   **drops the lock** (line 815).
3. `make_current()`, then `renderer.clear(bg, opacity)`, which clears the
   **whole** framebuffer.
4. `renderer.draw_cells(...)` sends every collected cell through the text
   renderer (§5.2). `RenderLines` collects underline and strikeout runs at the
   same time.
5. Rect pass (`renderer/rects.rs`): underlines (normal, double, undercurl,
   dotted, dashed are generated in the fragment shader, `RectKind`),
   strikeout, cursor shapes, visual bell, message bar, search bar, IME
   preedit and the vi line indicator.
6. `window.pre_present_notify()`, then `swap_buffers()`. On Wayland + EGL
   this becomes `swap_buffers_with_damage(rects)` (`display/mod.rs:607-626`).
7. **X11 only:** `renderer.finish()` (`glFinish`) right after swap
   (`display/mod.rs:1031-1038`). The comment says: "On X11 `swap_buffers`
   does not block for vsync. However the next OpenGl command will block to
   synchronize (this is `glClear` in Alacritty), which causes a permanent one
   frame delay."
8. On non-Wayland platforms, `request_frame()` schedules the next allowed
   frame time.

### 5.2 Text renderers: GLSL3 vs GLES2 (`renderer/mod.rs`, `renderer/text/`)

`Renderer::new` (`renderer/mod.rs`) picks:

- `Glsl3Renderer` if `GL_SHADING_LANGUAGE_VERSION >= 3.3` and the context is
  not GLES. Otherwise `Gles2Renderer`. The `debug.renderer` config can force
  `glsl3`, `gles2` or `gles2_pure`; the last disables dual-source blending.
- **GLSL3** (`text/glsl3.rs`) uses **instanced rendering**. There is one
  static index buffer for a quad and a per-instance VBO of `InstanceData`
  (`#[repr(C)]`, about 40 bytes): `col,row: u16`, glyph offset/size `i16`,
  atlas UVs `f32`×4, fg `u8`×3, flags `u8`, bg `u8`×4. Batches hold up to
  `BATCH_MAX = 65536` instances. A batch is flushed when the atlas texture
  changes or the batch fills. Each batch makes **two draw calls**
  (`DrawElementsInstanced`): a background pass (`renderingPass == 0`,
  discards fully transparent bg) and a text pass.
- **GLES2** (`text/gles2.rs`) has no instancing. It builds 4 vertices per
  glyph on the CPU, with `BATCH_MAX = 65532` (largest multiple of 4 ≤
  `u16::MAX`, since GLES2 indices are 16-bit). With
  `GL_EXT/ARB_blend_func_extended` it renders in 2 passes. Without dual-source
  blending it uses **3 text passes** to emulate per-channel (subpixel) alpha,
  following WebRender's text-rendering doc (`gles2.rs:462-475`).
- **Subpixel AA blending:** the fragment shader outputs colour and a
  per-channel **alpha mask** (`layout(location=0, index=1) out vec4
  alphaMask`), blended with `glBlendFunc(SRC1_COLOR, ONE_MINUS_SRC1_COLOR)`
  (`res/glsl3/text.f.glsl`, `renderer/mod.rs` `draw_rects`). Colour glyphs
  (emoji) are flagged `COLORED` and sampled as RGBA, with premultiplication
  undone.
- Context loss: if `GL_KHR_robustness` reports a reset,
  `Display::make_current` recreates the context, renderer and glyph cache
  (`display/mod.rs:556-605`).

### 5.3 Glyph cache and atlas

- `GlyphCache` (`text/glyph_cache.rs`) is a `HashMap<GlyphKey{font_key,
  char, size}, Glyph>`. The doc comment calls it a "Naïve glyph cache.
  Currently only keyed by `char`". There are four font keys: regular, bold,
  italic, bold-italic. ASCII for all four is preloaded at startup and after a
  font change (`load_common_glyphs`).
- Missing glyphs are cached once as `'\0'`.
- `builtin_font.rs` hand-draws box drawing (U+2500–259F), "legacy computing"
  sextants (U+1FB00–1FB3B, 1FB82–1FB8B) and powerline triangles
  (U+E0B0–E0B3) at the exact cell size, so lines join seamlessly. This is
  enabled by `font.builtin_box_drawing`.
- `Atlas` (`text/atlas.rs`) is a 1024×1024 texture with **shelf/row packing**
  (see its ASCII diagram). When it is full, a new atlas is pushed
  (`load_glyph`, line 251). There is **no eviction**: the cache only grows
  until a font/size change triggers `clear_atlas` plus a full reset.
  **Inference:** heavy CJK or emoji use grows GPU memory monotonically.
- Zero-width chars are rendered as additional glyphs at the same cell, with
  the anchor shifted by one cell (`glyph_cache.rs`, `load_glyph` comment).

### 5.4 Fonts: crossfont

`crossfont` has three backends: FreeType + fontconfig on Linux/BSD
(`crossfont/src/ft`), CoreText on macOS, and DirectWrite on Windows. On Linux
it builds a **per-font fallback list** from fontconfig (`ft/mod.rs:364-408`)
with charset coverage. `face_for_glyph` picks the first face that has the
char. Hinting, antialias, rgba and lcd filter come from fontconfig patterns.

**No shaping.** Every cell is rasterised independently from a single `char`.
There is no HarfBuzz, so there are no ligatures, no complex-script shaping, no
kerning across cells, and grapheme clusters are not composed.

### 5.5 "Damage-based partial redraw" (what it really is)

- `DamageTracker` (`display/damage.rs`) keeps damage for **two frames**
  (`frames: [FrameDamage; 2]`, swapped every frame). It adds terminal damage,
  old and new vi cursor, old and new selection, and UI overlays. Some states
  (visual bell, hints active, search active) force full damage.
- **It does not limit drawing.** The full framebuffer is cleared and every
  non-empty cell is redrawn every frame. Damage is only used to:
  1. pass `swap_buffers_with_damage` rects to Wayland compositors
     (`display/mod.rs:612-617`; CHANGELOG 0.12: "Track and report surface
     damage information to Wayland compositors");
  2. draw debug overlays (`debug.highlight_damage`).
- Two frames of damage are tracked because of buffer age with double
  buffering, so the compositor's view stays correct. **Inference:** the
  two-frame window is there for that reason.

> Lesson: Alacritty's bet is that the GPU is fast enough to redraw an entire
> terminal each frame, and the work saved by partial redraw isn't worth the
> complexity. That holds with a local GPU. It is a poor fit for **remote X11
> with GLX/software rendering**, where every frame's full pixels cross the
> network (see §6.3).

### 5.6 Frame scheduling / vsync

- **Vsync is turned off** at startup:
  `surface.set_swap_interval(SwapInterval::DontWait)`
  (`display/mod.rs:513`).
- Instead, `FrameTimer::compute_timeout` (`display/mod.rs:1557-1605`) uses the
  monitor refresh rate (`refresh_rate_millihertz`, default 60 Hz) to schedule
  the next frame on a fixed phase grid. If the last frame was more than an
  interval ago, it allows an immediate redraw (zero delay). Otherwise it waits
  until the next tick. Until that `Frame` event arrives, `has_frame == false`
  and Wakeups only set `dirty`.
- On Wayland, `request_frame` isn't called. Winit throttles `request_redraw`
  via compositor frame callbacks, and `pre_present_notify()` arms them.
- Occluded windows skip drawing entirely (`WindowContext::draw`,
  `window_context.rs:369`). CHANGELOG 0.12: "No longer renders to macos and
  x11 windows that are fully occluded".
- History in the CHANGELOG: "Increased input latency due to vsync behavior on
  X11" and "Low frame rate when multiple windows render at the same time".
  With vsync on, N windows each blocking in swap would divide the frame rate,
  since all windows render on one thread. This is the main reason for
  disabling vsync and using a timer.

---

## 6. Windowing and platform

### 6.1 winit + glutin

- One `winit::EventLoop<Event>` with user events. `Processor` implements
  `ApplicationHandler` (`event.rs:230`).
- GL setup (`renderer/platform.rs`):
  - `create_gl_display`: on X11 it uses `GlxThenEgl` by default and
    `EglThenGlx` if `debug.prefer_egl` (lines 36-41). Wayland is EGL only,
    Windows is WGL then EGL (or EGL then WGL), and macOS is CGL. An Xlib
    error hook is registered for GLX.
  - `pick_gl_config` tries, in order: 8-bit with transparency, 10-bit with
    transparency, 8-bit opaque, 10-bit opaque. Depth and stencil are 0.
  - `create_gl_context` tries **OpenGL 3.3 Core → GLES 2.0 → OpenGL 2.1
    Compat**, each with and without `RobustLoseContextOnReset` (lines
    114-147). The comment says: "Try gles before OpenGL 2.1 as it tends to be
    more stable."
  - On X11 the GLX/EGL config's **X visual** is passed into window creation
    (`gl_config.x11_visual()`, `window_context.rs:103-110`), so the window
    gets an ARGB visual for transparency.
  - The surface is created with `with_srgb(Some(false))`.
- On Windows the window must exist before the GL display (WGL needs an HWND),
  so the creation order differs (`WindowContext::initial`,
  `window_context.rs:74-120`).
- Wayland: the first frame isn't swapped at creation, because "the window
  isn't visible until you actually draw something" (`display/mod.rs:477-483`).
  Renderer resize is deferred to just before drawing (`process_renderer_update`),
  because "platforms like Wayland require resize and other OpenGL operations to
  be performed right before rendering ... This also solves flickering during
  resizes" (`display/mod.rs:739-743`).

### 6.2 Multiple windows

- One process can host many windows (`CreateNewWindow` action, `alacritty
  msg create-window`, or `--daemon` mode with no initial window). Each
  `WindowContext` has its own `Term`, PTY thread, `Display`, GL context and
  glyph cache. They share the GL **display/config** (`Processor::gl_config`).
- The main thread switches contexts (`make_current`) per window draw. Before
  creating a new window, all contexts are made not-current (`event.rs:375-381`,
  an EGL-on-Wayland quirk).
- On macOS, native window tabs come through winit (`CreateNewTab`,
  `SelectNextTab`, `config/bindings.rs:585-586`). This is the only "tabs"
  support.

### 6.3 Remote X11 / no GPU (what the code does and does not do)

Facts from the code:

- With the `x11` feature, GLX is tried first. Over `ssh -X`/`DISPLAY=remote`,
  EGL normally can't work because it needs local DRM. The usable path is GLX.
  Indirect GLX (rendering by the X server) generally exposes only old GL,
  typically ≤ 1.4 with Mesa (**general knowledge, unverified here**), which
  would fail all three context attempts above. In that case Alacritty exits
  with "failed to find suitable GL configuration" or a context error. There is
  **no CPU renderer fallback**.
- The practical remote path is Mesa **llvmpipe** on the client side
  (`LIBGL_ALWAYS_SOFTWARE=1`), which provides GL 3.3+/4.x in software. Then
  each frame is rendered on the CPU and pushed to the remote X server as an
  image. Because Alacritty **redraws and swaps the full window every frame**
  (§5.5), each update sends a full window of pixels. `glFinish` after swap
  (§5.1 step 7) then serialises on that. **Inference:** this is usable but
  bandwidth-heavy and latency-sensitive, and Alacritty has no mitigations
  (no partial swap on X11, no XRender/core-X text path).
- Monitor refresh rate can be missing or odd on remote displays; the code
  falls back to 60 Hz (`display/mod.rs:1442-1448`).
- Synchronous X11 round trips on the UI thread: clipboard (`copypasta`
  `X11ClipboardContext`) loads on paste, `set_ime_cursor_area` and window
  property calls. **Inference:** each costs one network RTT on a remote
  display and blocks input processing and rendering for every window, since
  everything is on one thread.

> For your design: if remote X11 matters, plan a renderer that can **draw only
> damaged rows** and present them with an X11-native path (XRender glyph sets
> or `XPutImage`/`XShmPutImage` of dirty rects, Present extension), separate
> from the GPU path. Keep all X round trips off the input-to-PTY path.

### 6.4 DPI scaling

- `scale_factor` comes from winit. Font size is scaled
  (`config.font.size().scale(scale_factor)`) and padding is scaled.
  `ScaleFactorChanged` rescales the font and schedules a font reload
  (`event.rs:1945-1956`).
- On X11, winit derives scale from `Xft.dpi`/XRandR (`WINIT_X11_SCALE_FACTOR`
  overrides). CHANGELOG notes: "`Xft.dpi` is now reloaded when xsettingd
  change its value" and "Alacritty failing to start on X11 with invalid DPI
  reported by XRandr".
- Cell size is derived from font metrics plus `font.offset`
  (`compute_cell_size`). With `window.resize_increments`, the WM is asked to
  resize in whole cells. `dynamic_padding` centres the grid.

### 6.5 IME

- `set_ime_allowed(true)`, `ImePurpose::Terminal` (`display/window.rs:191-193`).
- `Ime::Preedit` is stored in `Display::ime` and drawn inline at the cursor,
  with an underline and hollow cursor (`draw_ime_preview`,
  `display/mod.rs:1129`). Key events are ignored while preedit is active
  (`keyboard.rs:24`). `Ime::Commit` is written like a paste: bracketed if it
  is more than one char (`event.rs:2019-2024`).
- The IME candidate position is updated through `set_ime_cursor_area` (with
  an X11 off-by-one, `window.rs:453`). IME is inhibited while unfocused and in
  vi mode on X11 (`ImeInhibitor` bitflags).

---

## 7. Input

### 7.1 Keyboard (`alacritty/src/input/keyboard.rs`)

Pipeline in `key_input` (line 22):

1. Ignore keys during IME preedit. Releases only matter for kitty
   `REPORT_EVENT_TYPES`.
2. Hint mode, then inline search (`f`/`t` in vi), then **bindings**
   (`process_key_bindings`). Bindings match on `(key, mods, BindingMode)`,
   where `BindingMode` includes terminal modes such as `APP_CURSOR`,
   `ALT_SCREEN`, `VI`, `SEARCH` and the kitty flags.
3. Search input or vi mode capture the key.
4. Otherwise encode it:
   - Legacy encodings for keys that can't be derived automatically
     (`ESC O A` arrows in DECCKM, `ESC O P` F1–F4, `ESC [ Z` Shift-Tab, DEL
     for Backspace, and so on) are **default bindings**
     (`config/bindings.rs:443-460`), not encoder logic. Users can rebind them.
   - `should_build_sequence` (line 144) decides between sending the text as is
     (with an ESC prefix for Alt) and building an escape sequence.
   - `build_sequence` (line 295) implements xterm-style `CSI 1;mods X` /
     `CSI n;mods ~` and the **kitty keyboard protocol**: disambiguate, event
     types (press/repeat/release), alternate keys (shifted key), all keys as
     escapes, and associated text. Kitty flags live in `TermMode` bits
     18–22, with a push/pop stack per screen. The stack depth is capped at
     4096 (`KEYBOARD_MODE_STACK_MAX_DEPTH`, the HEAD commit's fix). Kitty
     support is always enabled from the UI (`ui_config.rs:126`).
   - Comments document winit limitations. For example: "Kitty's protocol
     mandates that the modifier state is applied before key press, however
     winit sends them after" (line 630). Base-layout keys are not reported
     because winit doesn't expose them (line 406).
5. Bytes go to `write_to_pty`, and `on_terminal_input_start()` clears the
   selection and scrolls to the bottom.

`modifyOtherKeys` (`CSI > 4;n m`) is parsed by vte, but `Term` doesn't
implement it (default no-op). Kitty protocol is the supported modern encoding.

### 7.2 Mouse (`alacritty/src/input/mod.rs`)

- Modes: 1000/1002/1003, which are mutually exclusive (`set_private_mode`).
  Encodings: X10 (`ESC [ M`, capped at 223), UTF-8 (1005, capped at 2015) and
  SGR (1006, `ESC [ < b;x;y M/m`) (`mouse_report`, line 541).
- Shift bypasses mouse mode for local selection. Only 3 buttons are reported;
  back and forward are not ("Can't properly report more than three
  buttons..").
- Alternate scroll (1007): on the alt screen without mouse mode, wheel events
  become arrow keys.
- Motion reports are only sent when the *cell* changes (CHANGELOG "Mouse mode
  generating events when the cell has not changed").
- Selection: click, double (semantic), triple (line), Ctrl for block,
  expansion with right click. Middle click pastes the primary selection.
  Hyperlinks and hints are activated on click.

### 7.3 Paste (`event.rs:1369`)

With bracketed paste, the text is wrapped in `ESC[200~ … ESC[201~` after
**stripping ESC and ETX (`\x03`)**. Stripping ESC prevents paste injection
that closes the bracket early; `\x03` is stripped because some shells end
bracketed paste on it. Without bracketed mode, `\r\n` and `\n` become `\r`.

### 7.4 Clipboard (`alacritty/src/clipboard.rs`)

- `copypasta` handles it: X11 `ClipboardContext` plus a separate
  `X11SelectionClipboard` for PRIMARY, Wayland data-device clipboards created
  from winit's `wl_display`, and native implementations on macOS/Windows.
- Selecting text stores to PRIMARY (`copy_selection(Selection)`), and also to
  CLIPBOARD if `selection.save_to_clipboard` is set.
- **OSC 52** (`term/mod.rs:1705-1748`): policy is `terminal.osc52` =
  `Disabled | OnlyCopy (default) | OnlyPaste | CopyPaste`. `c` → clipboard,
  `p`/`s` → selection. Writes and reads are **ignored when the window is
  unfocused** (`event.rs:1902-1913`). The CHANGELOG notes that paste was
  disabled by default for security. OSC 52 copy over SSH works out of the box
  and is the main way tmux/vim copy reaches the local clipboard.

### 7.5 Focus, bell, misc

Focus reporting (1004) sends `ESC[I`/`ESC[O`. The bell triggers a visual bell
animation, an urgency hint (mode 1042) and an optional command with a 100 ms
cooldown (`BELL_CMD_COOLDOWN`).

---

## 8. Configuration and live reload

- Format: **TOML** (`alacritty.toml`). YAML is legacy; `alacritty migrate`
  converts it (`alacritty/src/migrate/`). Files support `import = [...]`
  (`general.import`) with a recursion limit of 5 (`config/mod.rs:40`).
  Imports are merged with `serde_utils::merge`.
- Typed config structs (`config/ui_config.rs` and friends) derive
  `ConfigDeserialize` (`alacritty_config_derive`). That derive is
  **lenient per field**: an invalid value logs `Config error: <field>: ...` and
  keeps the default, unknown keys log `Unused config key`, and deprecated
  fields can emit warnings (`config_deserialize/de_struct.rs:45-160`). A typo
  never prevents startup. Errors are shown in the in-window **message bar**
  (`message_bar.rs`) through a logging target.
- **Live reload:** `ConfigMonitor` watches every loaded config file and import
  with `notify`, debounced 10 ms. On change it sends
  `EventType::ConfigReload(path)` → `config::reload` →
  `WindowContext::update_config` for every window (`window_context.rs:261-335`).
  That function diffs old and new configs to decide what to redo: font change
  → glyph cache reset (unless the user zoomed at runtime), padding →
  `pending_update.dirty`, opacity/blur/theme, title rules (there is a table in
  a comment), and `Term::set_options` (history size, cursor style, OSC 52,
  kitty). The monitor restarts if the set of import paths changed.
- **Runtime IPC** (Unix): `alacritty msg config 'key=value'` (`-w <window>`,
  `--reset`) and `alacritty msg get-config` over a unix socket
  (`polling/ipc.rs`). The overrides are stacked per window
  (`window_config: ParsedOptions`, `SerdeReplace`) on top of file config.
- CLI `-o key=value` overrides use the same mechanism.

---

## 9. Notable challenges and how they're handled

| Problem | Handling (source) |
|---|---|
| Parser throughput on dense output | vte ground-state `memchr` + bulk UTF-8 validation (`vte/src/lib.rs:596`). `Term::input` is `#[inline(never)]` to keep the hot loop small. 1 MiB read buffer. Up to 64 KiB parsed per lock hold. |
| Renderer blocking the parser | `FairMutex` lease + `try_lock_unfair`, buffering up to 1 MiB while the UI holds the lock (`event_loop.rs:116-146`). The UI snapshots cells and drops the lock before GL. |
| Parser starving the renderer | `MAX_LOCKED_READ` cap, and the fair `lock()` on the UI side waits for the lease. |
| Tearing / partial frames from apps | Mode 2026 byte buffering in vte (150 ms timeout, 2 MiB cap). An older DCS-based sync variant was removed (CHANGELOG 0.13: "Synchronized updates now use `CSI 2026` instead of legacy `DCS` variant"). |
| Input latency | Vsync off plus a custom frame timer, `glFinish` on X11, `Frame` events bypass batching, all window events per wake processed under one lock. CHANGELOG: "Increased input latency due to vsync behavior on X11", "IME input lagging behind on X11". |
| Many windows on one thread | No blocking swap (vsync off). Each window has its own frame timer. Occluded windows are skipped. |
| Scrolling cost | O(1) ring rotation for full-screen scroll, `Row::occ` to minimise resets, lazy scrollback allocation in 1000-row chunks. |
| Cell memory | 24-byte `Cell`, rare data in `Option<Arc<CellExtra>>` shared via the template's Arc. |
| DoS by escape sequences | Caps: 9 zero-width chars/cell, kitty stack 4096, title stack 4096, 32 CSI params, sync buffer 2 MiB, search DFA cache bounds. |
| Wide chars at line end | `LEADING_WIDE_CHAR_SPACER` cells, carried through reflow both directions (`grid/resize.rs`). |
| Deferred-wrap correctness | `input_needs_wrap` flag instead of an out-of-bounds cursor. Reflow temporarily moves the cursor one column past the edge to remove the special case. |
| Paste injection | Strip ESC and `\x03` inside bracketed paste. |
| OSC 52 abuse | Default copy-only, ignored when unfocused. |
| GPU reset / context loss | Robust context and recreate renderer + glyph cache (`display/mod.rs:556-605`). |
| Box drawing alignment | Built-in rasteriser for box, block and powerline glyphs. |
| Minimum cursor contrast | Invert cursor colours if contrast < 1.5 (`MIN_CURSOR_CONTRAST`, `content.rs:24`). |
| ConPTY deadlocks / old ConPTY | Field drop order, explicit `Processor` drop, optional `conpty.dll`. CHANGELOG: "Deadlock on Windows during high frequency output". |
| Linux EIO on child exit | Ignore EIO and wait for SIGCHLD (`event_loop.rs:283-291`). |
| X11 keyboard and modifier desync | Many CHANGELOG entries (sticky modifiers, xdotool, xmodmap). Most fixes are in winit. |
| Testing | "Ref tests": `--ref-test` records raw PTY bytes to `alacritty.recording` and dumps `grid.json`. `alacritty_terminal/tests/ref.rs` replays the recordings and compares grids. This is a cheap, robust regression harness for the VT core. |

---

## 10. Things Alacritty deliberately does not do

The README philosophy (README.md "About"): *"By integrating with other
applications, rather than reimplementing their functionality, it manages to
provide a flexible set of features with high performance."* In practice that
means "use your WM or tmux".

| Missing | Evidence in code | Stated reason |
|---|---|---|
| Tabs / splits | No such code; only macOS native tabs via winit | Philosophy above. Maintainers point users to tmux or the window manager (**public issue discussions, not in tree**) |
| Ligatures / shaping | No HarfBuzz; per-`char` `GlyphKey` ("Naïve glyph cache ... keyed by `char`") | Not stated in tree. A long-standing upstream issue (**unverified here**) |
| Images (sixel, kitty graphics, iTerm2) | DCS ignored; no APC handling (`SosPmApcString` → `anywhere`, swallowed) | Not stated in tree |
| tmux control mode (`-CC`) | DCS ignored (§3.2) | Not stated; consistent with "integrate rather than reimplement" |
| Scrollbar | None | — |
| OSC 7 / OSC 133 shell integration, notifications (OSC 9/777) | Not in vte OSC table | — |
| XTGETTCAP / DECRQSS / XTVERSION | DCS ignored; no `CSI > q` | — |
| Blink text | SGR 5 parsed but not stored or rendered | — |
| DECCOLM window resize | Mode 3 only clears the screen: "Setting 132 column font makes no sense" (`term/mod.rs:796`) | stated |
| Grapheme clustering | `unicode-width` per codepoint | — |
| Software (non-GL) rendering | Requires ≥ GLES 2.0 / GL 2.1 ("Requirements: At least OpenGL ES 2.0", README) | — |

---

## 11. Data flow diagram

```
                         ┌──────────────────────────── PTY thread (per window) ──────────────────────────────┐
                         │                                                                                    │
  child process          │  polling::Poller.wait(timeout = sync deadline)                                     │
  (shell / ssh)          │     ├─ PTY_READ_WRITE_TOKEN readable                                               │
       │  write()        │     │    pty_read():                                                               │
       ▼                 │     │      lease = term.lease()                  (block UI's fair lock)             │
  ┌─────────┐  bytes     │     │      read() → buf[1 MiB]                                                     │
  │ PTY     │───────────►│     │      try_lock_unfair()  ── busy? keep reading until 1 MiB, then block        │
  │ master  │            │     │      vte::ansi::Processor.advance(&mut Term, bytes)                           │
  │ (fd /   │            │     │         │  if mode 2026 active: append raw bytes to sync buffer, scan BSU/ESU │
  │ ConPTY  │            │     │         ▼                                                                    │
  │ pipes)  │            │     │      Parser (memchr ESC, utf8 run) ─► Perform ─► Handler (Term)               │
  └─────────┘            │     │                                              │                               │
       ▲                 │     │      Term::input / goto / linefeed / sgr ... ▼                               │
       │                 │     │      Grid<Cell> (Storage ring, Row.occ, Cell 24B + Arc<CellExtra>)           │
       │                 │     │      TermDamageState (per-line bounds / full)                                │
       │                 │     │      ≤64 KiB per lock hold → unlock                                          │
       │                 │     │      send_event(Wakeup) ───────────────────────────────┐                     │
       │                 │     ├─ PTY_CHILD_EVENT_TOKEN (SIGCHLD pipe / Win wait cb) → Exit                   │
       │ write()         │     └─ channel woken: drain Msg{Input,Resize,Shutdown}                              │
       └─────────────────┤          write_list ─► nonblocking write; Resize ─► TIOCSWINSZ / ResizePseudoConsole│
                         └──────────────────────────────────────────────────────────────▲──────┼────────────┘
                                                                       mpsc + poller.notify   │ winit user event
                                                                                              │ (EventLoopProxy)
┌────────────────────────────────────────── Main / UI thread (all windows) ──────────────────┼──────▼──────────┐
│ winit event loop                                                                           │                 │
│  WindowEvent (key/mouse/IME/resize) ─► WindowContext.event_queue                           │                 │
│  AboutToWait / RedrawRequested: term.lock() (fair) ─► input::Processor                     │                 │
│     keys: bindings ─► kitty / xterm encoder ─► write_to_pty ───────────────────────────────┘                 │
│     mouse: selection / X10/SGR report ─► write_to_pty                                                        │
│     Term events: PtyWrite (DA/DSR replies), ClipboardLoad/Store, Title, Bell ...                             │
│     resize: Display::handle_update → Notifier.on_resize + Term::resize (reflow)                              │
│  Wakeup ─► dirty=true; if has_frame → request_redraw                                                         │
│  RedrawRequested ─► Display::draw:                                                                           │
│     term.lock(); RenderableContent iter (skip empty cells, resolve colours, cursor, selection, hints)        │
│     Vec<RenderableCell>; Term::damage() → DamageTracker; reset; DROP LOCK                                    │
│     make_current; glClear(full)                                                                              │
│     GlyphCache.get(char,font) ─miss─► crossfont rasterise ─► Atlas (1024² shelves, grows)                    │
│     Text batches: GLSL3 instanced quads (bg pass + text pass, dual-source blend) | GLES2 4 verts/glyph       │
│     Rect pass: underlines/undercurl/strike/cursor/bell/bars                                                  │
│     swap_buffers (+damage rects on Wayland EGL); glFinish on X11                                             │
│     request_frame: FrameTimer → scheduler Frame event at next vblank (X11/Win); Wayland: frame callback      │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
                                        GPU (GLX / EGL / WGL / CGL) → compositor / X server
```

---

## 12. Lessons for a new terminal (Linux first, then Windows; SSH-heavy; remote X11 + local GPU; tmux)

**Architecture**

- Keep a **headless core crate or library**: parser glue, grid, modes,
  selection, search. Have it talk to the UI only through an event trait and
  a write/resize sink. Alacritty's `alacritty_terminal` is reused by other
  projects, and its ref-test replay harness (record PTY bytes, compare the
  serialised grid) is cheap and catches regressions. Copy that idea.
- **One I/O thread per PTY, one UI thread** works well. Snapshot the viewport
  under the lock and render without it. Use a lease/fair-lock scheme like
  `FairMutex` so neither side starves, and let the reader keep buffering
  rather than block on the renderer.
- Don't route terminal *query replies* (DA, DSR, colour queries) through the UI
  thread the way Alacritty does. Write them directly from the parser thread so
  a slow UI or a blocking X call can't stall apps probing the terminal over
  SSH.

**Parser**

- A DEC-state-machine parser with a semantic `Handler` trait (vte style) is a
  good split. Add memchr fast paths for printable runs.
- **You need DCS** for `tmux -CC`, XTGETTCAP, DECRQSS and sixel. Alacritty
  can't grow these easily because vte's `ansi` layer drops
  `hook/put/unhook`. Design DCS handlers as pluggable sub-parsers. For tmux
  control mode, the DCS `1000p` hook should switch the byte stream into a
  line-oriented control-protocol parser that owns many virtual panes/grids.
- Implement mode 2026 by **byte buffering with a timeout** (150 ms in vte) or
  by snapshot freezing. Byte buffering is simple and keeps the renderer
  oblivious.
- Bound every attacker-controlled structure (zero-width per cell, mode
  stacks, title stack, OSC length, sync buffer). Alacritty added several of
  these caps only recently.

**Grid**

- A ring buffer of rows with an O(1) rotate, lazily allocated scrollback, a
  per-row "occupied" watermark and a compact cell (≈16–24 B) with
  out-of-line rare attributes is a proven design. Store colours unresolved
  so palette changes are free.
- Plan **grapheme clusters** from day one. Alacritty's per-codepoint width
  plus "zero-width chars attached to previous cell" breaks ZWJ emoji and
  shaping. Store a cluster or an interned string id per cell instead of a
  single `char`.
- Reflow is the hardest piece of grid code. Wrap flags, wide chars at the
  edge, the deferred-wrap cursor and the display offset all interact. Alacritty
  reflows by rebuilding the whole buffer (O(history)) and never reflows the alt
  screen. Write exhaustive tests here (`grid/tests.rs`, `term` resize tests).
- Keep selections in buffer coordinates and rotate them on scroll.

**Rendering**

- Alacritty redraws everything each frame. That is fine on a local GPU and
  costly on **remote X11**. Your remote-X requirement argues for:
  1. real per-row damage that limits what is *drawn and presented*;
  2. a second backend for remote/no-GPU, either XRender glyph caches or
     `XShmPutImage`/Present of dirty rects;
  3. runtime selection: detect indirect/software GL or a remote `DISPLAY` and
     switch backend, rather than failing as Alacritty does when no ≥ GL 2.1 /
     GLES 2 context exists.
- If you use GL, copy the fallback ladder: GL 3.3 core → GLES 2 → GL 2.1, GLX
  vs EGL preference, transparency and 10-bit configs, robust contexts with
  reset recovery. Also copy the instanced-quad text pipeline with a background
  pass and dual-source subpixel blending.
- Frame pacing: Alacritty disabled vsync and uses its own refresh-phase timer
  so that many windows on one thread don't serialise on swap, and calls
  `glFinish` on X11 to avoid a one-frame lag. Use Wayland frame callbacks
  there. Skip occluded windows.
- A glyph atlas with no eviction is simple but grows forever. Add an LRU or
  multi-atlas eviction if CJK/emoji-heavy use matters. Draw box and powerline
  glyphs procedurally.
- Decide on shaping (HarfBuzz) early if you want ligatures or complex
  scripts. Retrofitting it onto a per-cell `char` cache is the reason
  Alacritty never did it.

**Platform / PTY**

- Unix PTY checklist from Alacritty: `openpty` with the initial winsize,
  `IUTF8`, `setsid` + `TIOCSCTTY`, reset signal dispositions in the child,
  non-blocking master, SIGCHLD self-pipe in the same poller, tolerate `EIO`
  on hangup, SIGHUP + wait on close, `TIOCSWINSZ` with pixel sizes, and
  foreground-process cwd via `tcgetpgrp` + `/proc`.
- Windows: ConPTY needs threads for the anonymous pipes, careful drop order
  (`ClosePseudoConsole` blocks until output drains), ignoring 0×0 resizes,
  and ideally the option to load a newer `conpty.dll`/OpenConsole. Remember
  that ConPTY rewrites the VT stream.
- Set `TERM` carefully for SSH. Alacritty falls back to `xterm-256color` when
  its terminfo is missing *locally*, but SSH sessions inherit the local
  `TERM` value and the remote side may lack that entry.

**Input / clipboard**

- Use the kitty keyboard protocol plus legacy xterm encodings. Making legacy
  sequences *default bindings* (user-overridable) rather than hard-coded
  encoder logic is neat.
- Bracketed paste must strip ESC. OSC 52 should be copy-only by default and
  ignored when unfocused. Over SSH, OSC 52 is the clipboard bridge for tmux
  and vim, so make it work well, including large payloads.
- Keep clipboard and other X11 round trips **asynchronous**. On a remote
  display every synchronous call is a network RTT that freezes the UI thread,
  and with it all windows.

**Config**

- Lenient per-field config parsing with an in-window error bar, imports,
  file-watch reload with per-field diffing, and runtime overrides over IPC
  (`alacritty msg config`) are all worth copying.

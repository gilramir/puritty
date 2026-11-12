# Ghostty: architecture analysis for a new terminal emulator

Source analyzed: `vendor/ghostty` at commit `d8619f1bc` (2026-10-18, "gtk: keep IME
cursor location updated during preedit on Wayland"), version 1.3.x-dev. Unless noted,
paths are relative to `vendor/ghostty/`. Line numbers come from that snapshot and will drift.

> **Important version caveat.** This snapshot is much newer than Ghostty 1.0–1.2,
> which most blog posts describe. Three changes matter most:
> 1. On Linux the renderer **no longer uses GtkGLArea**. It renders offscreen with
>    its own EGL context on the render thread and hands frames to GTK as DMA-BUFs.
>    If that fails, it uses a CPU `glReadPixels` copy.
> 2. The renderer reads terminal state through an incremental `RenderState`
>    instead of cloning the screen each frame.
> 3. The PTY reader is a two-thread gather/parse pipeline.
>
> A tmux control-mode *protocol layer* exists, but there is no GUI integration yet.

Contents:

1. Overall architecture and threading
2. PTY and termio
3. Parser and handled sequences
4. Terminal state data structures
5. Rendering and fonts
6. GTK runtime on Linux (OpenGL, X11, remote X)
7. Input
8. tmux control mode
9. Config, themes, reload, CLI
10. Testing, fuzzing and benchmarks
11. Notable challenges and workarounds
12. Lessons for a new terminal

---

## 0. Data-flow diagram

```
                       ┌─────────────────────── per Surface (one terminal) ────────────────────────┐
                       │                                                                            │
  child process        │  io-gather thread          io-reader thread (parse)                        │
  (shell/ssh/tmux)     │  (Exec.gatherMainPosix)    (Exec.ReadThread.threadMainPosix)               │
   ▲        │          │  read()/poll() pty fd ──►  ring of 4 × 64 KiB buffers ──► Termio.processOutput
   │        │ pty      │  nonblocking, spin+1ms     (mutex+condvars on ring metadata only)          │
   │        ▼ master   │  bridge polls, 3ms budget         │                                        │
   │   ┌─────────┐ ────┼──►                                ▼                                        │
   │   │  PTY    │     │                    ┌─── renderer_state.mutex (std.Io.Mutex) ───┐           │
   │   └─────────┘     │                    │ terminal.Stream.nextSlice(batch)          │           │
   │        ▲          │                    │   Parser (vt100.net DFA) + SIMD UTF-8     │           │
   │        │          │                    │   → StreamHandler (termio/stream_handler) │           │
   │        │          │                    │   → Terminal / Screen / PageList / Page   │           │
   │        │          │                    │   (sets row/page dirty bits)              │           │
   │        │          │                    └──────────┬───────────────┬────────────────┘           │
   │        │          │       yieldToDemand() at each │ batch boundary│ responses (DA, DSR, OSC 52, │
   │        │          │       hands lock to renderer  │               │ tmux cmds) → io mailbox     │
   │        │          │                               │ renderer_wakeup (xev.Async)                │
   │        │          │                               ▼                                            │
   │        │          │  renderer thread (renderer/Thread.zig, own xev loop, EGL ctx current here) │
   │        │          │   updateFrame: lockDemand() → RenderState.beginUpdate (copy dirty rows)    │
   │        │          │               unlock → endUpdate, rebuildCells (shaping, atlas)            │
   │        │          │   drawFrame:  upload bg SSBO + glyph instances → GL passes → glFinish      │
   │        │          │               → export DMA-BUF (or glReadPixels) → LatestFrame slot        │
   │        │          │               → surface mailbox `.redraw`                                  │
   │        │          │                               │                                            │
   │        │          │  io writer thread (termio/Thread.zig, xev loop)                            │
   │        └──────────┼── xev.Stream write ◄── termio mailbox (SPSC BlockingQueue, cap 64)         │
   │                   │   also: resize coalescing (25 ms), sync-output 1 s reset timer, termios poll│
   └───────────────────┘                    ▲                                ▼
                                            │ write_small/stable/alloc       │
  main / GUI thread (GTK GApplication loop, or the Swift app via the C API)  │
   key event → GtkIMMulticontext → Surface.keyCallback → bindings → key_encode → queueIo
   mouse → mouseButtonCallback → mouse_encode / selection
   GhosttyRenderSurface.snapshot ← takeFrame() → GdkDmabufTexture | GdkMemoryTexture → GSK → screen
   App mailbox (BlockingQueue 64): surface→app messages (title, clipboard, close, notifications)
```

Each surface therefore has **four threads**: renderer, io-writer, io-reader (parse) and
io-gather. The GUI main thread is shared by all surfaces, and the app may also start
short-lived warmup threads (`App.zig:80-110`).

---

## 1. Overall architecture

### 1.1 Layers

- **Core (`src/`)** is platform-agnostic Zig.
  - `App.zig` holds global state: the surface list, the font grid set, and the app mailbox.
  - `Surface.zig` (6.7 kLOC) is one terminal widget. It owns its PTY, its renderer, the
    renderer thread, termio, the IO threads, and the input state (`Surface.zig:1-140`).
  - A "surface" is deliberately independent of window, tab or split. The apprt decides
    what it is (`Surface.zig:1-11`).
- **libghostty-vt** (`src/terminal/`, `include/ghostty/vt.h`, `include/ghostty/vt/*.h`)
  is the parser, terminal state, formatter, search, snapshot, and key/mouse/paste
  encoders, exposed as a C API. The headers warn the API is still unstable.
  - It builds for macOS, Linux, Windows and wasm (`README.md`, "Cross-platform libghostty").
  - It is fuzzed and conformance-tested independently (§10).
  - **Note for the user:** this could serve as the VT core of a new terminal.
- **apprt (application runtime)** is chosen at **compile time** (`src/apprt.zig:38-47`):
  - `.exe` builds use `none` or `gtk`.
  - `.lib` builds use `embedded`, which is the macOS/iOS Swift app via `include/ghostty.h`.
  - `.wasm_module` builds use `browser`.
  - The default runtime is GTK on Linux and FreeBSD and `none` everywhere else
    (`src/apprt/runtime.zig:14-24`). **There is no Windows GUI runtime.**
- **Core → apprt calls** go through
  `rt_app.performAction(target, comptime action, value) !bool`.
  - `src/apprt/action.zig:16-365` defines about 75 actions: new_split, set_title,
    render, open_url, desktop notification, config_change and others.
  - The apprt returns `false` for actions it doesn't implement.
  - GTK's dispatch is `Application.performAction` (`apprt/gtk/class/application.zig:689`).
    Its explicit unimplemented list is around line 806.
- **apprt → core calls** are plain method calls on `CoreSurface`: `keyCallback`,
  `textCallback`, `preeditCallback`, `sizeCallback`, `focusCallback`,
  `mouseButtonCallback`, `scrollCallback` (`Surface.zig:2580-3900`).

### 1.2 Threads, mailboxes and wakeups

All event loops are **libxev** (`global.xev`). Cross-thread signaling always pairs a
bounded queue with an `xev.Async` wakeup.

| Channel | Type | Producer → consumer | Notes |
|---|---|---|---|
| termio mailbox | `BlockingQueue(termio.Message, 64)` + `xev.Async` (`termio/mailbox.zig:15-50`) | main/parse thread → io-writer | `send` tries a non-blocking push first. If the queue is full, it wakes the writer, **temporarily unlocks the renderer mutex** so the writer can make progress, and then does a blocking push (`mailbox.zig:63-95`). This avoids a deadlock in pathological cases. |
| renderer mailbox | `BlockingQueue(renderer.Message, 64)` | main, io → renderer | Carries resize, focus, visible, change_config, font grid swap, reset_cursor_blink. |
| renderer wakeup | `xev.Async` | parse thread (`StreamHandler.queueRender`, `stream_handler.zig:115-118`) → renderer | Many notifies collapse into one callback. **This is the only render coalescing on Linux** (§5.2). |
| surface/app mailbox | `BlockingQueue(Message, 64)` (`App.zig:587-589`; message union `apprt/surface.zig:14+`) | io, renderer → main | Carries set_title (fixed `[256]u8`), clipboard read/write, desktop notification (fixed-size), redraw, child exited. |

- `termio.Message` is about 40 bytes. Small writes are carried inline with
  `MessageData(u8, 38)`; larger ones are allocated or point to static ("stable")
  data (`termio/message.zig:8-20`).
- Messages are typed tagged unions with no closures. Each payload has a deliberate size cap.

### 1.3 The one big lock

- `renderer.State` (`src/renderer/State.zig`) holds `mutex: *std.Io.Mutex`,
  `terminal: *Terminal`, preedit, mouse state and the inspector.
- **Every** terminal mutation happens under this mutex: the parse thread, resize on the
  io-writer, and selection and scroll from the main thread. The renderer takes it only
  for the short snapshot phase.
- **Fairness fix** (`State.zig:35-102`):
  - `std.Thread.Mutex` and `os_unfair_lock` are unfair. Under sustained output, the
    parse thread's unlock→relock loop starved the renderer.
  - The renderer therefore uses `lockDemand()`, which bumps an atomic `demand` counter.
  - The parse thread calls `yieldToDemand()` between batches. If demand is non-zero, it
    futex-waits up to 1 ms for `handoff_gen` to change (`termio/Exec.zig:1513`).
  - This is a small, reusable trick worth copying.

---

## 2. PTY and termio

### 2.1 Structure

- **`termio/Termio.zig`** is the IO object. It owns the `Terminal`, the `terminal_stream`
  (a `Stream(StreamHandler)`), the backend (`Exec`), and the mailboxes.
- **`termio/backend.zig`** contains only `Exec` (a subprocess with a PTY). The design
  allows other backends, and the comments mention "manual".
- **`termio/Thread.zig`** is the io-writer thread. Its xev loop handles:
  - mailbox draining;
  - **resize coalescing**: `Coalesce.min_ms = 25`, so only the last resize in each
    window is applied (`Thread.zig:27-34, 390-450`);
  - the **synchronized-output safety reset**: `sync_reset_ms = 1000`. If a program sets
    mode 2026 and never clears it, rendering resumes after 1 s (`Thread.zig:36-38, 378-386`);
  - selection auto-scroll every 15 ms.
- **`termio/Exec.zig`** (2.3 kLOC):
  - starts the process, shell integration and env, and a process watcher via `xev.Process`;
  - writes via `queueWrite`, which splits data into pooled buffers and does `\r`→`\r\n`
    when linefeed mode is on (`Exec.zig:403-470`);
  - runs a **termios poll timer** every 200 ms (`TERMIOS_POLL_MS`, `Exec.zig:35`). It
    detects password prompts with ECHO off and shows a lock-icon cursor. The timer is
    disabled on Windows.

### 2.2 Read pipeline (Exec.zig:1264-1830)

The doc comment at `Exec.zig:1264-1300` explains the design:

- A serial `read(); process();` loop stalled producers on macOS. There the kernel tty
  queue caps each master read at about 1 KiB, and `cat` blocked while Ghostty was parsing.
- The fix is two stages:
  - **io-gather** drains a non-blocking fd into a ring of `buffer_count = 4` buffers,
    each `buffer_capacity = 64 KiB`.
  - **io-reader** parses one batch per lock acquisition. Only the ring metadata is
    behind a mutex; each buffer is owned by exactly one stage at a time.
- **Latency vs throughput:**
  - A batch is delivered on the first `EAGAIN` unless ≥1 KiB was gathered
    (`bridge_threshold`), which means the stream is "saturated".
  - When saturated, gather spins up to 16 non-blocking reads (`bridge_spin_max`), then
    polls for 1 ms (`bridge_poll_timeout_ms`), with a 3 ms cap per batch (`gather_budget_ns`).
  - When the parse stage goes idle, it interrupts the bridge poll through an "idle"
    self-pipe.
- **Backpressure:** once all 4 buffers are in flight, gather blocks. The kernel PTY queue
  then fills and the child blocks, which preserves flow control.
- **Windows** still uses the old serial loop (`threadMainWindows`, `Exec.zig:1773`) with
  `ReadFile` and `PeekNamedPipe` on a quit pipe.
- **`Termio.processOutput`** (`Termio.zig:697-754`):
  - locks the mutex;
  - calls `queueRender()` first;
  - resets cursor blink at most every 500 ms;
  - calls `terminal_stream.nextSlice(buf)`. If the inspector is open, it switches to a
    slow byte-at-a-time mode;
  - notifies the writer thread only if the handler queued messages, so there is one
    wakeup per batch rather than per response.

### 2.3 Resize

- `Termio.resize` (`Termio.zig:516-556`) takes the mutex.
- It calls `backend.resize`, which does `TIOCSWINSZ` or `ResizePseudoConsole`, **before**
  `terminal.resize` (reflow), under the same lock.
- The comment explains the order: SIGWINCH can wake the shell immediately, and its redraw
  must not be parsed against old dimensions.
- It then sends an in-band size report if mode 2048 is set, and mails `.resize` to the
  renderer.

### 2.4 PTY layer (`src/pty.zig`, `src/pty.c`)

- **PosixPty:**
  - `openpty`;
  - sets `IUTF8` on the termios (`pty.zig:177`);
  - resizes with `TIOCSWINSZ`;
  - `getProcessInfo` uses `tcgetpgrp` to find the foreground process (for cwd and the
    "process running?" check on close).
- `NullPty` is used on iOS.
- **WindowsPty** (`pty.zig:326-500`):
  - named pipes;
  - `CreatePseudoConsole` and `ResizePseudoConsole`;
  - the Exec subprocess passes `pseudo_console` into `Command`;
  - the default shell is `cmd.exe` (`Exec.zig:762, 841`).
- Reflow has a `pull_scrollback=false` mode for ConPTY. ConPTY keeps its own buffer and
  redraws, so Ghostty pads blank rows at the bottom instead of pulling scrollback down
  (PageList resize; see §4.4).

### 2.5 Windows status

| Exists | Missing |
|---|---|
| ConPTY pty | No Windows GUI apprt |
| Windows read thread | No renderer for Windows: backends are only OpenGL and Metal, and the OpenGL backend needs EGL surfaceless (§5) |
| `freetype_windows` font backend (`font/backend.zig`) | No termios polling |
| `VirtualAlloc` pages | Most process-management tests are skipped on Windows |
| libghostty-vt builds and runs on Windows (`test/windows/` contains a DLL-init test) | |

In practice, Windows support is libghostty-vt only.

#### Windows compilers and ABIs for libghostty-vt

libghostty-vt itself is always compiled by Zig. The C compiler only matters for the
program that links against it. What CI tests on Windows (`.github/workflows/test.yml`):

| Combination | Where | Tested how |
|---|---|---|
| **MSVC** (Visual Studio, `cl.exe` + `link.exe`) building the consumer | Native Windows runner | CMake examples via the Visual Studio generator, which always uses MSVC (`test.yml:313-338`). `c-vt-cmake-cross` is excluded |
| **`zig cc`, MSVC ABI** | Native Windows runner | `zig build test-lib-vt`, a static-link example and a DLL example (`test.yml:936-970`) |
| **`zig cc`, MinGW ABI** (`x86_64-windows-gnu`) | Cross-compiled from Linux | Build only, nothing runs (`test.yml:617`) |

- **MSVC is the default ABI on Windows.** The build forces it when no ABI is given,
  because Zig's default GNU ABI emits COMDAT sections that the MSVC linker rejects with
  LNK1143 (`src/build/Config.zig:100-111`).
- **MSVC-specific workarounds:**
  - DllMain initializes the MSVC C runtime (`src/main_c.zig:179-212`, regression test
    in `test/windows/test_dll_init.c`);
  - `_fltused` is exported for static builds (`src/lib_vt.zig:170-186`);
  - the stack protector is disabled in the static lib, and ubsan runtime bundling is
    off (`src/build/GhosttyLibVt.zig:253-268`);
  - the DLL links `libvcruntime` and finds the UCRT dir (`src/build/GhosttyLib.zig:112-125`);
  - the `memset` override is skipped for weak COFF builds (`src/quirks_memset.zig:61-73`).
- **Cross-compiling to MSVC from Linux doesn't work yet.** The CI entry is commented
  out: "we need a way to find msvc libc/c++ headers" (`test.yml:618-619`).
- **The MinGW output is built in CI but never run or linked.**
  `example/c-vt-cmake-cross` cross-compiles Linux → Windows (MinGW) with `zig cc`.
- **Untested:** native MinGW GCC (MSYS2), clang-cl and Cygwin are not mentioned
  anywhere.
- **Static linking on Windows needs extra steps** (`CMakeLists.txt:180-201`):
  - link `ntdll` and `kernel32`;
  - the SIMD dependencies (highway, simdutf) are not bundled into the Windows `.lib`.
    Link them separately or build with `-Dsimd=false`.
- **Output names:** `ghostty-vt.dll`, the import lib `ghostty-vt.lib`, and the static
  lib `ghostty-vt-static.lib`. The static lib is renamed to avoid colliding with the
  import lib.

**Conclusion:** MSVC, or `zig cc` targeting the MSVC ABI, is the only path tested end
to end. Use MinGW only if the whole application is MinGW-built. Don't mix the two ABIs.

### 2.6 Shell integration (`src/shell-integration/`, `termio/shell_integration.zig`)

- **Injection is automatic** (`shell-integration = detect`):
  - **bash:** started as `bash --posix` with `ENV` pointing at `bash/ghostty.bash`.
    `GHOSTTY_BASH_INJECT` records the original `--norc`/`--noprofile` so the script can
    emulate normal startup and then leave POSIX mode (`shell_integration.zig:299-400`;
    `shell-integration/README.md`).
  - **zsh:** `ZDOTDIR` trick (`zsh/.zshenv`).
  - **fish, elvish, nushell:** prepend to `XDG_DATA_DIRS`.
- **Features** are passed in `GHOSTTY_SHELL_FEATURES` (`Config.zig:8899-8906`):
  - `cursor`: bar cursor at the prompt;
  - `sudo`: preserve terminfo through sudo;
  - `title`;
  - `path`: add Ghostty's bin dir;
  - `ssh-env`, `ssh-terminfo`.
- **Semantic prompts** use OSC 133 with extended parameters: `133;A;redraw=last;cl=line;aid=…`,
  `133;P;k=i|s`, `133;B`, `133;D;exit;aid` (`bash/ghostty.bash:140-190`). These drive:
  - prompt-aware reflow (blank prompt rows are kept);
  - `jump_to_prompt`;
  - ctrl+triple-click "select command output";
  - redraw-on-resize hints.
- **SSH helpers matter for an SSH-centric terminal.** The shell function `ssh()` wraps
  `ghostty +ssh` (`bash/ghostty.bash:119-128`; `src/cli/ssh.zig`):
  - `--terminfo` runs `tic -x -` on the remote over a ControlMaster connection, then
    uses `TERM=xterm-ghostty`. Successful installs are cached (`+ssh-cache`).
  - `--forward-env` falls back to `TERM=xterm-256color` and forwards
    `COLORTERM`/`TERM_PROGRAM` with SendEnv.
  - **Lesson:** terminfo on remote hosts is a real UX problem for a new `TERM` value.

---

## 3. Parser (`src/terminal/Parser.zig`, `parse_table.zig`, `stream.zig`, `src/simd/`)

### 3.1 State machine

- `Parser.zig` is a direct implementation of Paul Williams' vt100.net DEC parser
  (`Parser.zig:1-30`). It has 14 states, including `sos_pm_apc_string`.
- The transition table is generated at comptime in `parse_table.zig`.
- Limits: `MAX_PARAMS = 24` and `MAX_INTERMEDIATE = 4` (`Parser.zig:196-219`). Params are
  `u16`, and a separate bitset records `:` vs `;` separators (for SGR sub-params such as
  `4:3` curly underline and `38:2::r:g:b`).
- Output is an `Action` union: `print`, `execute`, `csi_dispatch`, `esc_dispatch`,
  `osc_dispatch`, `dcs_hook/put/unhook`, `apc_start/put/end`.
- **A Ghostty-specific deviation** (`parse_table.zig:245-265`):
  - Bytes 0x80–0xFF inside DCS are treated as payload, including 0x9C (8-bit ST).
  - Reason: "Ghostty is UTF-8 only, and DCS payloads carry UTF-8 text (e.g. tmux
    control mode pane content)". A C1 byte is indistinguishable from a UTF-8
    continuation byte.
  - 8-bit C1 controls are not honored in ground state either; they go through UTF-8
    decoding.

### 3.2 `Stream` and its fast paths (`stream.zig`, 5.7 kLOC)

`Stream(Handler)` wraps the parser and dispatches to a handler at comptime. There are two
handlers:

- `stream_terminal.zig`: the libghostty-vt "readonly" handler. It applies only state
  changes; side effects go through optional callbacks.
- `termio/stream_handler.zig`: the GUI handler. It handles responses, clipboard,
  titles, tmux and so on.

`nextSlice` (`stream.zig:647-900`) works as follows:

1. Input is split into ≤4096-codepoint chunks.
2. Any in-progress UTF-8 or escape sequence is finished with the scalar path
   (`consumeUntilGround`).
3. In ground state, the SIMD routine `simd.vt.utf8DecodeUntilControlSeq` decodes UTF-8
   in bulk up to the next ESC (`src/simd/vt.cpp`). It is C++ using **Google Highway**
   (runtime target dispatch) and **simdutf**, and replaces invalid sequences with
   U+FFFD using the "maximal subpart" rule.
4. The decoded codepoints are split into **printable runs** with a vectorized
   `(cp & ~0x9F) == 0` test that detects C0 and C1 together. Each run goes to the
   handler as a single `print_slice` action. C0 controls are executed inline; C1
   controls decoded from UTF-8 are ignored.
5. Escape-sequence fast paths:
   - `ESC [` goes straight to `csi_entry`;
   - CSI parameter bytes are bulk-consumed (`consumeCsiParams`);
   - **APC payloads are bulk-consumed as slices**, because kitty graphics base64 can be
     megabytes;
   - OSC is accumulated in the OSC parser.
6. Debug builds always go byte-at-a-time, as a correctness oracle.

On the terminal side, `print_slice` → `Terminal.printSlice` (`Terminal.zig:581-652`)
writes runs of narrow or wide cells directly when conditions allow: no insert mode,
wraparound on, no single shift, no active hyperlink.

**DCS bytes are dispatched one at a time** (`dcsPut`), including tmux `%output`, so
tmux throughput is not on the fast path (§8).

Other SIMD routines in `src/simd`: `index_of` (memchr-like), `base64` (kitty graphics),
and `codepoint_width`.

### 3.3 Handled sequences (overview)

The stream `Action` enum (`stream.zig:36+`) covers:

- **Cursor:** cursor movement, CUP/HVP, tabs (HT/CBT/TBC/HTS).
- **Editing:** ED/EL (including scrollback erase `ED 3` and "erase right unless pending
  wrap"), ICH/DCH/ECH/IL/DL, SU/SD, IND/NEL/RI, RIS/DECSTR, DECALN, REP (`print_repeat`).
- **Margins:** DECSTBM, and DECSLRM including the `CSI s` ambiguity with SCOSC.
- **Modes:** SM/RM/DECSET/DECRST, save/restore (XTSAVE/XTRESTORE), DECRQM.
- **Charsets:** SCS, LS/SS.
- **SGR**, including colon sub-params and underline styles/colors.
- **Protection:** DECSCA/SPA/EPA.
- **Reports:** DA1/2/3, DSR (including color-scheme DSR 996 and CSI ? 996 n), XTVERSION,
  XTWINOPS size reports and title push/pop, `CSI 8 t` resize_window.
- **Kitty keyboard:** push/pop/set/query (`CSI > u`, `< u`, `= u`, `? u`).
- **Other:** `mouse_shift_capture` (XTSHIFTESCAPE), `modify_key_format` (XTMODKEYS),
  DECRQCRA checksum (`xt_checksum.zig`, used by esctest), DECSASD
  (`active_status_display`).

**Modes** (`modes.zig`, a comptime table generated into a packed struct of bools):
standard DEC/ANSI modes plus mouse modes 9/1000/1002/1003/1005/1006/1015/1016, focus
1004, bracketed paste 2004, **synchronized output 2026** (`modes.zig:405`, not
configurable), **grapheme clustering 2027** (`modes.zig:406`), in-band size reports 2048,
color-scheme reports 2031, and 2033 visibility reports.

**OSC** (`terminal/osc.zig:30-180`, parsers in `terminal/osc/parsers/`):

| OSC | Purpose |
|---|---|
| 0/1/2 | title/icon |
| 4/5/10–19/104/110–119 | color set, query, reset (`color_operation`) |
| 7 | report pwd |
| 8 | hyperlinks (`hyperlink_start/end`) |
| 9 | ConEmu family: sleep, message box, tab title, progress, wait, guimacro, … |
| 9;4 | progress reports |
| 21 | kitty color protocol |
| 22 | mouse shape |
| 52 | clipboard |
| 66 | kitty text sizing |
| 99 | kitty desktop notifications |
| 133 | semantic prompts |
| 777 | rxvt notify |
| 1337 | iTerm2 |
| 3008 | hierarchical context |
| 5522 | kitty clipboard protocol |
| — | kitty DnD protocol |
| — | `program_status` |

Unknown OSCs are captured with a size cap (`unknown_max_bytes`).

**DCS** (`terminal/dcs.zig`): XTGETTCAP (answered from the built-in terminfo,
`stream_handler.zig:495-501`), DECRQSS, and **tmux control mode `ESC P 1000 p`** (§8).

**APC** (`terminal/apc.zig`, `terminal/kitty/`):

- **kitty graphics**: transmit/put/delete/animate; unicode placeholders
  (`graphics_unicode.zig`); media direct, file, temporary file, and shared memory
  (`graphics_command.zig:506-585`); storage limit `image-storage-limit = 320 MB`
  (`Config.zig:2522`).
- a `glyph` APC (`terminal/apc/glyph.zig`), which looks Ghostty-specific (custom
  glyph protocol). I did not analyze it.

**Kitty extras**: keyboard protocol (`terminal/kitty/key.zig`), clipboard (OSC 5522,
with password "grants"), DnD, color (OSC 21), and text sizing (OSC 66).

**OSC 52** (`stream_handler.zig:1045-1075`):

- `c`→standard, `s`→selection, `p`→primary; anything else is standard.
- `?` is a read and goes to the main thread as `clipboard_read`.
- Policy is in config: `clipboard-read = ask`, `clipboard-write = allow`,
  `clipboard-write-limit-bytes = 64 MiB` (§7.5).

**Synchronized output (2026):**

- Setting the mode tells the writer thread to arm the 1 s reset timer.
- The renderer **skips updateFrame entirely** while the mode is set
  (`renderer/generic.zig:1413-1417`).
- `in_band_size_reports` (2048) is sent on resize.

---

## 4. Terminal state data structures (`src/terminal/`)

This is the most carefully engineered part of Ghostty and the most useful part to study.
Sizes: `Terminal.zig` 17 kLOC, `Screen.zig` 12.8 kLOC, `PageList.zig` 20.8 kLOC,
`page.zig` 4.5 kLOC. Much of that is tests: 450, 225, 294 and 52 tests respectively.

### 4.1 Hierarchy

```
Terminal ── modes, tabstops, scrolling_region, colors/palette, flags.dirty, ScreenSet
  └─ ScreenSet { primary, alternate (lazily allocated, no scrollback) }
       └─ Screen ── cursor (cached page pin/row/cell ptrs), saved_cursor, charset,
            │       selection (tracked pins), kitty_images, kitty_keyboard stack
            └─ PageList ── doubly linked list of Nodes (pool-allocated), tracked pins,
                 │         viewport pin, byte/line scrollback limits, compression
                 └─ Page ── ONE contiguous mmap'd buffer: rows | cells | styles |
                            grapheme alloc+map | string alloc | hyperlink set+map
```

### 4.2 Page: one offset-addressed memory block

- **Allocation** (`page.zig:29-81, 168-171, 237-246`):
  - `mmap(PRIVATE|ANONYMOUS)` on POSIX and `VirtualAlloc` on Windows; page-aligned;
    a multiple of the OS page size.
  - Allocation skips the general-purpose allocator because it is hot, and the OS
    returns **zeroed** memory.
- **All-zero is a valid empty page.**
  - `initBuf` writes only row headers (the per-row cell offsets). Every other structure
    (style set, bitmap allocators, hash maps) is designed so that zero means empty
    (`page.zig:256-318`).
  - Untouched OS pages are never faulted in, so they cost no RSS.
- **Offsets, not pointers.**
  - `Offset(T)` is a `packed struct(u32)` byte offset from the page base.
  - Nested structures such as the hash maps store offsets relative to the page base
    through `OffsetBuf`.
  - Result: cloning a page is a single `memcpy` (`cloneBuf`, `page.zig:665-681`).
    Compression, snapshotting and moving pages need no pointer fix-ups.
- **Layout** (`Page.layout`, `page.zig:1756-1885`):
  - `[Row headers][Cells (64-byte aligned)][StyleSet][GraphemeAlloc][GraphemeMap][StringAlloc][HyperlinkSet][HyperlinkMap]`.
- **Rows reference cells through an offset**, so row order changes by swapping or
  rotating 8-byte `Row` headers. IL/DL and scroll regions move no cells
  (`Terminal.zig:2998-3170`; `PageList.eraseRow` 5194-5300).
- **Capacity** (`page.zig:1890-2006`):
  - `std_capacity = {cols 215, rows 215, styles 128, grapheme_bytes 8192}`.
  - `std_size = layout(std_capacity).total_size`. `compress/AGENTS.md` puts it at
    ~400 KiB; the cells alone are 215×215×8 = 369,800 B.
  - `Capacity.adjust(cols)` keeps the byte size constant and trades rows for columns,
    so most terminals use the pool-sized page.
  - When styles, graphemes or hyperlinks run out, ops return typed errors
    (`StyleSetOutOfMemory`, `…NeedsRehash`, etc.).
  - The caller then runs `PageList.increaseCapacity`, which doubles the dimension. For
    styles and graphemes it can instead project the current density plus 25%, capped at
    32×, to avoid repeated whole-page clones (`PageList.zig:4219-4387`).
  - If the page is already at maximum capacity, `Screen.splitForCapacity` splits it.

### 4.3 Cell and Row: 8 bytes each

`Cell = packed struct(u64)` (`page.zig:2137-2250`):

```
content_tag:u2 (codepoint | codepoint_grapheme | bg_color_palette | bg_color_rgb)
content:u24    (u21 codepoint | palette idx | r,g,b)
style_id:u16   (0 = default style)
wide:u2        (narrow | wide | spacer_tail | spacer_head)
protected:u1, hyperlink:u1, semantic_content:u2 (output|input|prompt), _pad:u16
```

`Row = packed struct(u64)` (`page.zig:2008-2135`):

```
cells:Offset(u32), wrap, wrap_continuation, grapheme, styled, hyperlink,
semantic_prompt:u2, kitty_virtual_placeholder, dirty, _pad:u23
```

**Memory per cell** is 8 B plus 8 B per row, plus page metadata.

- Styles are **not** stored per cell. Each page has one ref-counted entry per unique
  style, and a cell holds a 16-bit page-local id.
- Background-color-only cells (erase with a colored BG) store the color inline and
  need no style entry.
- Graphemes (additional codepoints after the first) live in a side map keyed by cell
  offset, using a bitmap allocator with 16-byte chunks. Each cluster is capped at
  `grapheme_max_len = 64` codepoints as DoS protection (`page.zig:92, 1595`).
- Hyperlinks also live in a side map (cell offset → id). The rationale is that most
  cells are never links (`hyperlink.zig`).
- Row flags `styled`, `grapheme` and `hyperlink` may have false positives but never
  false negatives. Erase and clear on plain rows skip the per-cell release loop and
  just memset, which is about 4× faster (`page.zig:2030-2040`).
- Masked u64 compares are vectorized with `@Vector`
  (`Mask(T, fields, group_len)`, `page.zig:2410-2467`). They are used for "is this
  cell plain?" scans in the print path and the render state.

### 4.4 Ref-counted sets and hash maps

- **`RefCountedSet`** (`ref_counted_set.zig`) is an offset-based Robin Hood hash table.
  - Id 0 is reserved and the load factor is 0.8125.
  - Entries whose refcount reaches 0 stay in place and can be resurrected.
  - It tracks probe-sequence-length statistics, and **returns `NeedsRehash` to defend
    against crafted-hash DoS** instead of probing forever.
- **Styles** (`style.zig`):
  - `Style{fg, bg, underline_color, flags}`, packed into a u128 for hashing.
  - SGR updates the cursor's style. `Screen.manualStyleUpdate` adds it to the cursor's
    current page; when the cursor moves to another page, the ref is released and
    re-added there (`Screen.zig:2529-2610, 1543-1622`).
- **`hash_map.zig`** is a fork of the std hash map with offsets and backward-shift
  deletion (no tombstones, because capacity is fixed). A removal can move entries.
- **`bitmap_allocator.zig`**: one u64 bitmap word per 64 chunks. It describes itself as
  "relatively naive" and prone to fragmentation.

### 4.5 PageList: scrollback, pins, reflow

- **Nodes** (`PageList.zig:54-110`): an intrusive doubly linked list of
  `Node{prev, next, data: resident Page | compressed Page, serial: u64, owned: pool|heap}`.
  - Nodes and pages are pooled and their addresses reused, so each node carries a
    generation `serial`.
  - External holders (render state, search) keep `(ptr, serial)` pairs and check
    validity without dereferencing.
- **Pools** (`PageList.zig:323-399`):
  - `PagePool` is an "untouched" pool of std-size page buffers. Idle items are never
    written, so they cost only virtual memory. Whoever returns an item must zero it.
  - At startup it preheats 4 pages, 1 node and 2 pins.
- **Scrollback limit is in bytes.**
  - The GUI config is `scrollback-limit-bytes`, default 50 MB (`Config.zig:1394`), plus
    the newer `scrollback-limit-lines`.
  - The library default `Terminal.Options.max_scrollback_bytes = 10_000` effectively
    rounds up to about 2 pages (`PageList.zig:7111-7149`).
- **grow()** (`PageList.zig:4003-4154`):
  - Fast path: the last page has spare rows, so the row count is bumped. Unused rows
    are always zero.
  - Slow path when over the limit: **pop the oldest page and reuse it as the new tail**
    (memset and re-init). Tracked pins on the pruned page move to (0,0) of the new first
    page and are marked `garbage`.
  - Steady-state scrolling therefore allocates nothing.
- **Pins:**
  - `Pin{node, y:u16, x:u16, garbage}` is valid only until the next mutation.
  - A **tracked pin** is registered in a set and fixed up linearly by every mutating
    operation (eraseRow, increaseCapacity, compact, grow-prune, reflow).
  - Tracked-pin users: cursor, viewport, selection endpoints, search results, kitty
    placements.
  - The docs warn this is not cheap, so pins should be few (`PageList.zig:7197-7212, 5715-5736`).
- **Reflow on resize** (`resize`/`resizeCols`/`ReflowCursor`, `PageList.zig:1261-1700`):
  - Column growth reflows first and then changes rows; column shrink does the reverse.
  - It **rewrites the entire list, including all scrollback**: O(scrollback). The TODO
    for deferred reflow of off-screen pages is at `PageList.zig:1266`.
  - Trailing blanks of unwrapped rows are trimmed.
  - A style cache maps old→new style ids; source pages are recycled as soon as they
    are consumed.
  - The cursor is kept stable by counting `wrap_continuation` rows above it before and
    after.
  - The ConPTY mode (`pull_scrollback=false`) pads instead of pulling scrollback into
    view.
- **Compression** (`compress/`, new):
  - Cold scrollback pages (not in the viewport or active area) are LZ4-compressed and
    the raw range is released with `MADV_DONTNEED`.
  - **The virtual range is kept**, so decompressing can't fail and offsets stay valid.
  - The renderer thread runs compression in 250 ms idle slices
    (`renderer/Thread.zig:731-856`). Resize forces decompression of everything.

### 4.6 Screen, cursor, alt screen

- **Cursor** (`Screen.zig:131-185`):
  - active x/y, style value and page-local `style_id`, hyperlink, pending_wrap, protected.
  - **Cached pointers** `page_pin` (tracked), `page_row` and `page_cell`, so print writes
    without a lookup. They are rebuilt by `cursorReload` and `cursorPageReplaced`.
- **Charsets**: G0–G3 are stored as four separate fields rather than an EnumArray,
  because "benchmarks faster" (`Screen.zig:200-255`).
- **Alternate screen**:
  - **Allocated lazily** on first use, with `max_scrollback_bytes = 0`
    (`Terminal.zig:4826-4883`), and never freed afterwards.
  - Modes 47/1047/1049 follow xterm's `charproc.c` exactly (`Terminal.zig:4897-4970`).
  - Scrolling in a no-scrollback screen rotates rows in place.

### 4.7 print and Unicode width

`Terminal.print` (`Terminal.zig:1254-1615`) does the following:

1. Charset mapping.
2. If mode **2027** is on and the codepoint is above 255: grapheme-break check against
   the previous cell, using UAX #29 (`unicode.graphemeBreak`) by replaying the stored
   codepoints.
   - With no break, the codepoint is appended to the cell.
   - VS16 widens the previous cell, possibly wrapping it; VS15 narrows it.
   - The code says this path is "MUCH slower".
3. Without 2027:
   - zero-width codepoints attach to the previous cell;
   - VS15/VS16 attach only after an Extended_Pictographic cell.
4. Width:
   - `c <= 0xFF ? 1 : table.get(c).width` (0, 1 or 2);
   - the table is a 3-stage LUT generated at build time from the **uucode** library
     (`src/unicode/lut.zig`, `props.zig`).
5. Wide characters:
   - written as `wide` plus `spacer_tail`;
   - at the right edge, `spacer_head` plus a wrap.
6. `writeCell` repairs broken wide pairs and maintains style, grapheme and hyperlink
   refcounts.

### 4.8 Dirty tracking and RenderState (`terminal/render.zig`)

**Four dirty levels:**

1. Terminal `flags.dirty`: palette, reverse_colors, clear, preedit. Any of these forces
   a full redraw (`Terminal.zig:233-252`).
2. Screen `dirty`: selection, hyperlink_hover. Also forces a full redraw.
3. `Page.dirty`: all rows in the page.
4. `Row.dirty`. May have false positives.

A cursor move dirties both the old and the new row, because the cursor splits shaping runs.

**`RenderState`** (`render.zig:20-115`):

- It replaced per-frame screen cloning: "clone time was repeatedly a bottleneck blocking IO".
- It is a persistent, renderer-owned copy of viewport rows:
  - per-row arena, raw cells, graphemes, resolved styles, selection range, highlights;
  - pin and serial;
  - global `dirty: false|partial|full`.
- `beginUpdate` runs **under the lock** (`render.zig:511-965`):
  - forces full if the screen, dimensions or viewport changed;
  - otherwise reads and **clears** page and row dirty bits in terminal memory, scanning
    row dirty bits with vector masks;
  - memcpys only dirty rows;
  - plain rows return early ("~300% faster");
  - records style runs.
- `endUpdate` runs **without the lock**: it denormalizes style runs into per-cell styles
  and skips rows whose styles didn't change.
- `Row.Id = {serial, y}` gives renderers a stable per-row cache key across scrolling.

### 4.9 Selection and search

- **Selection** is a pair of tracked pins plus a rectangle flag.
  - Ordering uses `pointFromPin`, which walks the list. The code calls this slow; it
    came over from the older implementation (`Selection.zig:14-21`).
  - Word, line and "command output" selection use semantic prompts (`Screen.zig:3124-3560`).
  - `SelectionGesture.zig` handles click counting.
- **Search** (`terminal/search/`):
  - Runs on a dedicated thread with a 24 ms tick. It takes the terminal lock briefly
    and feeds one page at a time.
  - Pages are formatted to text in a sliding circular buffer with a byte→cell map.
    Overlap handles matches across page boundaries.
  - **ASCII case-insensitive substring only**: no regex, no Unicode case folding.
  - Results hold node+serial so they survive scrollback pruning.

---

## 5. Rendering and fonts

### 5.1 Structure

- `renderer/generic.zig`: `Renderer(comptime GraphicsAPI)`. The backend is chosen at
  compile time: Metal on Darwin, OpenGL elsewhere (`renderer/backend.zig`).
- Abstraction layers are documented at `generic.zig:51-89`: GraphicsAPI → Target → Frame
  → RenderPass → Step → Pipeline, plus Buffer and Texture.
- **There is no CPU or software renderer.**
- Triple buffering: `swap_chain_count = 3` with a semaphore (`OpenGL.zig:33`,
  `generic.zig:311-357`).
- Each `FrameState` holds a uniform buffer, a fg-instances buffer, a bg-cells buffer,
  grayscale and color atlas textures with modification counters, a target, and
  custom-shader ping-pong textures.

### 5.2 Renderer thread and frame pacing (`renderer/Thread.zig`)

- **Handles in the xev loop:**
  - `wakeup` (Async);
  - `draw_now` (macOS display link);
  - `render_h`, an animation timer used **only** for custom shaders and kitty
    animations at `draw_interval_ms = 8` (≈120 fps, `generic.zig:1104`);
  - cursor blink every 600 ms;
  - the idle compression timer.
- **What a wakeup does:**
  - It drains the mailbox and **immediately** runs `updateFrame` then `drawFrame`
    (`Thread.zig:458-561`).
  - An older 10 ms coalescing timer is commented out (`Thread.zig:480-496`).
  - **On Linux there is no frame cap and no vsync**: `DisplayLink` is `void` off macOS
    (`generic.zig:43-46`). Throughput is limited by Async coalescing plus frame cost,
    which includes a blocking `glFinish`.
- **On macOS** a CVDisplayLink paces drawing, but `updateFrame` still runs on every wakeup.
- **Invisible or occluded:** `setVisible(false)` releases the whole swap chain and draws
  stop. Unfocused surfaces stop the blink timer and, by default, custom-shader animation.
- **Synchronized output:** `updateFrame` returns early while mode 2026 is set (`generic.zig:1413`).
- **`updateFrame`** (`generic.zig:1363-1700`):
  - Under `lockDemand`: `RenderState.beginUpdate`, preedit clone, kitty image updates
    (marked "SLOW SLOW SLOW", `:1478`), OSC 8 hover hit-test.
  - Unlocked: `endUpdate`, regex link matching, search highlights, overlay (z2d), and
    `rebuildCells` under the renderer's own `draw_mutex`.
  - The RenderState is fully reset every 100k frames to drop retained memory.
- **`drawFrame`** (`generic.zig:1707-2032`) never takes the terminal lock.
  - Redraw happens if size, swap chain, cells or animation changed.
  - The subagent's reading, not runtime-verified: `rebuildCells` sets `cells_rebuilt`
    unconditionally (`:2908`), so every non-sync update redraws, including cursor-blink
    ticks.

### 5.3 Cells, passes, shaders

- **CPU-side buffers** (`renderer/cell.zig:41-200`):
  - `bg_cells`: a flat `rows*cols` array of RGBA8.
  - `fg_rows`: `rows+2` lists of `CellText`. Each entry is about 32 B: glyph rect,
    bearings, grid pos, color, atlas id, flags. Lists 0 and `rows+1` are the cursor
    layers (block cursor below text, other cursor shapes above).
  - Only dirty rows are rebuilt (`rebuildCells`, `generic.zig:2619-2913`).
- **Uploads:**
  - Every drawn frame re-uploads **all** bg cells and fg rows (one `glBufferSubData` per
    row list; `generic.zig:1867-1869`, `opengl/buffer.zig:93-123`).
  - When an atlas's modified counter changes, the **whole atlas** is re-uploaded, once
    per swap-chain slot (`generic.zig:1880-1896`).
- **Passes** (`generic.zig:1903-2030`):
  1. bg color or bg image (full-screen triangle);
  2. kitty images below bg;
  3. `cell_bg`: a full-screen triangle whose **fragment shader indexes an SSBO of bg
     colors by `gl_FragCoord / cell_size`**;
  4. kitty images below text;
  5. `cell_text`: **instanced quads**, one per glyph or decoration, sampling grayscale
     or color `sampler2DRect` atlases;
  6. kitty images above text (one draw per placement);
  7. inspector overlay;
  8. custom post-shaders, ping-ponging between textures.
- **Decorations are sprite glyphs**: underline (single, double, dotted, dashed, curly),
  strikethrough, overline, and all cursor shapes.
- Block-cursor text recoloring and `minimum-contrast` are done in the vertex shader.
- **Shaders** (`renderer/shaders/glsl/*`):
  - `#version 430 core`: `common.glsl`, `bg_color`, `cell_bg`, `cell_text`, `image`,
    `bg_image`.
  - `full_screen.v.glsl` is `#version 330`.
  - Metal uses hand-written `shaders/shaders.metal`.
- **Color handling:** sRGB framebuffer (`GL_SRGB8_ALPHA8` plus `GL_FRAMEBUFFER_SRGB`),
  premultiplied alpha. `alpha-blending` defaults to `linear-corrected` on Linux.
- **Custom shaders:** Shadertoy-style GLSL → **glslang** → SPIR-V → **SPIRV-Cross** →
  GLSL 430 or MSL (`renderer/shadertoy.zig:157-276`). On failure, post-shaders are
  dropped and the terminal keeps working.

### 5.4 OpenGL requirements (critical for remote X11)

- **OpenGL 4.3 core is required** (`renderer/OpenGL.zig:38-40`).
  - The context is created with EGL: `eglBindAPI(EGL_OPENGL_API)` and the core profile
    bit.
  - The version is re-checked after glad loads. A failure logs "OpenGL version is too
    old. Ghostty requires OpenGL 4.3" and returns `error.OpenGLOutdated`
    (`OpenGL.zig:165-186`).
- **4.3 features used:**
  - SSBOs (std430, bg cells);
  - `ARB_vertex_attrib_binding`-style setup;
  - explicit `layout(binding=)`;
  - instanced draws;
  - rectangle textures;
  - KHR_debug.
- **EGL device** (`renderer/opengl/Device.zig:37-105`):
  - It uses GDK's EGL display (Wayland or X11) when available; otherwise
    `eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA)`.
  - The config uses `EGL_SURFACE_TYPE = 0`: there is **no window surface at all**, and
    contexts are made current surfaceless.
  - It has detailed diagnostics for a missing EGL driver, a libc mismatch, or a missing
    `EGL_MESA_platform_surfaceless`.
- **Context ownership:**
  - One context per surface, created on the main thread and then made current on the
    render thread in `threadEnter`.
  - All GL calls happen on the render thread.
  - `opengl/Device.zig:7-8` has a TODO about GPU selection.
- **Presentation** (`OpenGL.zig:276-300`, `opengl/Target.zig:148-242`):
  1. `glFinish` every frame.
  2. If healthy: blit sRGB → RGBA8 ("Mesa cannot export `GL_SRGB8_ALPHA8` textures to
     dma-buf"), then `eglExportDMABUFImageMESA`, then a `GdkDmabufTexture` on the GTK side.
  3. If DMA-BUF export or GTK import fails (multi-GPU modifiers, etc.), presentation is
     marked **unhealthy** and every later frame does a **full `glReadPixels`** into a
     `GdkMemoryTexture` (`render_surface.zig:157-172, 367-430`).
  - The hand-off is a single **latest-wins slot** (`generic.zig:1054-1066`
    `pushFrame/takeFrame`). Frames that are never displayed are simply dropped.

### 5.5 Fonts (`src/font/`)

- **Backends** (`font/backend.zig`):
  - Linux: `fontconfig_freetype` + HarfBuzz.
  - macOS: CoreText for discovery, faces and shaping.
  - Windows: `freetype_windows`.
  - wasm: `web_canvas`.
- **Discovery** (`discovery.zig:248-333`): a fontconfig pattern with a monospace
  preference, then `fontSort`. Fallback discovery is the same query with a codepoint
  charset.
- **Collection** (`Collection.zig`):
  - Per-style (regular, bold, italic, bold-italic) priority lists of faces.
  - The index is a `packed u16` (2 style bits, 14 index bits); the max value means the
    sprite font.
  - Build order (`SharedGridSet.zig:155-391`): configured fonts, synthetic styles,
    embedded **JetBrains Mono** (variable), embedded **Symbols Nerd Font**, then embedded
    **Noto Color Emoji** and **Noto Emoji** (Apple Color Emoji on macOS).
  - Fallback faces are size-normalized like CSS `font-size-adjust`, by ic-width by default.
  - **Synthetic bold** uses `FT_Outline_Embolden`; **synthetic italic** uses a 12° skew.
- **CodepointResolver** (`CodepointResolver.zig:120-228`) looks up in this order:
  `font-codepoint-map`, sprite face, collection (respecting emoji vs text presentation),
  then system fallback discovery.
  - Fallback discovery runs **synchronously on the render thread under the grid write
    lock**.
  - Negative results are cached.
- **SharedGrid** (`SharedGrid.zig`):
  - Holds the codepoint→font cache, the glyph cache, and two **atlases**: grayscale R8
    and color BGRA, each starting at 512×512.
  - Protected by an RwLock with double-checked misses.
  - **Never evicts.** A full atlas **doubles**.
  - Size or font changes build a new grid.
  - **SharedGridSet** ref-counts grids by (font config, size) across all surfaces
    (`SharedGridSet.zig`).
- **Atlas** (`Atlas.zig`): skyline bottom-left bin packing (freetype-gl style). Grayscale
  AA only, no LCD/subpixel AA.
- **Shaping** (`font/shaper/run.zig:41-305`, `harfbuzz.zig`):
  - A run never crosses a row.
  - Runs break on style change (ignoring bg), font change, selection edges, the "bad
    ligatures" fi/fl/st, explicit VS15/VS16, and **the cursor position** (configurable
    with `font-shaping-break`).
  - HarfBuzz is forced LTR: "We don't support RTL text because RTL in terminals is messy".
  - The run hash is position-independent. The shaper cache is 256×8 LRU, and a comment
    notes shaping was once 96% of frame time.
  - HarfBuzz shaping takes the grid's exclusive lock, because FreeType faces aren't
    thread-safe, so surfaces sharing a grid serialize their shaping.
- **Sprite font** (`font/sprite/draw/*`): procedurally drawn (z2d) glyphs for:
  - box drawing U+2500–257F, blocks U+2580–259F, braille;
  - some geometric shapes;
  - Powerline E0B0–E0BF;
  - kitty branch-drawing glyphs;
  - Symbols for Legacy Computing and its supplement.
  - Drawing them by hand gives pixel-exact joins and consistent stroke thickness
    whatever the font provides.
- **Metrics** (`Metrics.zig:227-334`):
  - `cell_width = round(max advance over ASCII)`, `cell_height = round(ascent - descent + gap)`.
  - Many `adjust-*` overrides.
  - Nerd Font glyphs are constrained with tables generated from the font-patcher
    (`nerd_font_attributes.zig`).
  - Symbols may extend into a following blank cell.

---

## 6. GTK runtime on Linux

### 6.1 Structure

- Requirements: GTK ≥ **4.18** and libadwaita ≥ **1.7**, enforced at compile time and
  at runtime (`apprt/gtk/gtk_version.zig:18-28`, `adw_version.zig:19-22`).
- GObject classes are written in Zig under `apprt/gtk/class/`: application, window, tab,
  split_tree, surface, render_surface, overlays, dialogs.
- UI is Blueprint files in `apprt/gtk/ui/<adw-version>/*.blp`, compiled to a gresource.
- **Windows and tabs:** `Adw.ApplicationWindow` with `Adw.TabView`, `TabBar` and
  `TabOverview` (`ui/1.4/window.blp`).
- **Splits** (`src/datastruct/split_tree.zig`):
  - An **immutable** `SplitTree(View)`: a flat node array with u16 handles;
    `Split{layout, ratio: f16, left, right}`; zoom support; spatial navigation.
  - Every operation returns a new tree, which makes undo possible. Undo is implemented
    on macOS but is in GTK's unimplemented list.
  - The GTK side maps the tree onto nested `GtkPaned` widgets (`class/split_tree.zig`).
- **Single instance:** GApplication D-Bus uniqueness. `gtk-single-instance=detect` turns
  it off when launched from a terminal or with CLI args.
- **IPC:** `+new-window`, `+new-tab` and `+toggle-quick-terminal` call
  `org.gtk.Actions.Activate` over D-Bus (`apprt/gtk/ipc/`).
- **Quick terminal:** Wayland only (gtk4-layer-shell); on X11 it is "not yet supported"
  (`winproto/x11.zig:168-171`).
- **Reload triggers:** SIGUSR2 (`application.zig:1559`). systemd integration notifies
  `reloading` and `ready`.

### 6.2 How pixels reach the screen: no GtkGLArea

`apprt/gtk/class/render_surface.zig:20-44` explains why GtkGLArea was dropped:

- GLArea's lifecycle "lives **exclusively on the main UI thread**".
- That forced careful locking against the render thread.
- It also created a chicken-and-egg startup: wait for the GL context, then create the
  renderer, then the core surface.

`GhosttyRenderSurface` is a plain `gtk.Widget`:

- Its `snapshot` takes the latest exported frame and appends a `GdkDmabufTexture`, or a
  `GdkMemoryTexture` in readback mode, with a Y-flip.
- The renderer pushes `.redraw` → `performAction(.render)` → `queueDraw`.
- **The core surface is created on the first `resize` signal, not on realize**
  (`class/surface.zig:3426-3488`).
- `setGtkEnv` (`application.zig:3241-3295`) always sets `GDK_DISABLE=vulkan`, citing
  Vulkan/GL conflicts and hundreds of ms of startup. It strips `GDK_DEBUG`, `GDK_DISABLE`
  and `GSK_RENDERER` from children.
- GTK's own GSK renderer (GL, Vulkan or Cairo) is otherwise left to GTK.

### 6.3 X11 vs Wayland

- `winproto.zig` is a union of none, x11 and wayland. If init fails it falls back to
  `none` and the app still runs.
- **X11** (`winproto/x11.zig`, 505 lines):
  - WM_CLASS;
  - **XKB** state-notify to get correct modifiers when a modifier key is pressed,
    peeking the queue with `XPeekEvent` (a Firefox trick, lines 121-156);
  - KDE blur via `_KDE_NET_WM_BLUR_BEHIND_REGION`;
  - `_MOTIF_WM_HINTS` decorations;
  - `WINDOWID` env;
  - urgency hint.
  - If XKB init fails, winproto becomes `none`.
- **Wayland:** layer-shell, KDE decoration, blur and background-effect protocols,
  xdg-activation, and a global-hotkey protocol.
- **Global shortcuts** use the XDG GlobalShortcuts portal (`class/global_shortcuts.zig`).

### 6.4 Remote X11, no GPU, software rendering

**What the code says:**

- A grep of `src/apprt` and `src/renderer` for llvmpipe, softpipe, swrast,
  `LIBGL_ALWAYS`, indirect, GLX, `DISPLAY`, "x11 forward" or "ssh -X" finds **nothing**.
- GLX is never used. There is no remote-X awareness, no software-renderer detection,
  and **no non-GL renderer**.
- The minimum is GL 4.3 core through EGL with surfaceless contexts.
- The DMA-BUF → `glReadPixels` fallback exists for import failures (the stated reason
  is multi-GPU modifiers), not for remote displays.

**Failure UI:**

- `ui/1.0/surface.blp` defines an "Unable to acquire an OpenGL context for rendering"
  status page that links to ghostty.org/docs/help/gtk-opengl-context.
- In this snapshot, `Surface.setError` (`class/surface.zig:2314`) has **no callers**, so
  a failed init seems only to log "surface failed to initialize". This is a regression
  or work in progress.
- `renderer_health` is in GTK's unimplemented action list.

**Likely behavior over `ssh -X`.** This is inference, not tested:

1. `renderDeviceOptions` (`class/surface.zig:1771-1793`) passes
   `gdk_x11_display_get_egl_display()`. For a remote display this may be NULL (GDK fell
   back to GLX or no GL); then the code falls back to Mesa surfaceless EGL.
2. All GL rendering then happens **on the client host**, typically on Mesa **llvmpipe**,
   which supports GL 4.5 core, so the 4.3 floor is met. Indirect GLX is irrelevant.
3. GTK cannot import a DMA-BUF onto a remote X server, so the surface is marked
   unhealthy. From then on, each frame is a full re-render, `glFinish`, a full
   `glReadPixels` of w×h×4 bytes, a new `GdkMemoryTexture`, then GSK (probably Cairo on
   remote X) pushes the whole window image across the network.
4. There is no damage-region propagation from Ghostty to GTK and no frame cap on Linux.
   Every pty batch can cause a full-window upload. The latest-wins slot drops stale
   frames, which helps somewhat.
5. On a host with no usable EGL driver, surface init fails. Per the previous point, the
   user may just get an empty widget.

**Conclusion for the user's design:** Ghostty's architecture is GPU-first and
compositor-oriented. Supporting remote X11 well needs either a CPU renderer that sends
only damaged cell rectangles (core X11 or XRender, or `XPutImage` of dirty regions)
or at least damage-aware presentation. Ghostty provides neither.

---

## 7. Input

### 7.1 Key flow

1. GTK `EventControllerKey` → `class/surface.zig:1264 keyEvent`.
2. Every press and release goes through **`GtkIMMulticontext.filterKeypress`**. Releases
   are included because fcitx needs them. A composing/not-composing state machine
   attaches IM commits that happen *inside* a key event to that event (`im_buf`).
3. Key data is built from:
   - the physical key: X/Wayland keycode → W3C code table (`input/keycodes.zig`);
   - mods from `winproto.eventMods` (the X11 XKB trick);
   - consumed mods;
   - the unshifted codepoint.
4. → `CoreSurface.keyCallback` (`Surface.zig:2772-2963`):
   1. key remaps;
   2. `maybeHandleBinding` (sequences and tables);
   3. keyboard-action-mode lock;
   4. `encodeKey` (`Surface.zig:3306`);
   5. `queueIo(write_small…)` to the io-writer thread;
   6. scroll to bottom and clear selection.
5. A pressed key is remembered (`pressed_key`) so a release can be synthesized on focus
   loss (`Surface.zig` fields).

### 7.2 Encoding (`src/input/key_encode.zig`, 2.9 kLOC)

- **Kitty protocol** is used when the screen's kitty flag stack is non-zero.
  - Flags: disambiguate, report_events, report_alternates, report_all, report_associated
    (`terminal/kitty/key.zig:79-85`).
  - An 8-deep stack **per screen** (main and alt each have one).
  - The key table is "ported from Foot".
- **Legacy encoding:**
  - PC-style function keys from a table ported from foot's `keymap.h`
    (`input/function_keys.zig`), filtered by DECCKM, keypad mode and modifyOtherKeys.
  - Then xterm **modifyOtherKeys** state 2 (`CSI 27;mod;cp ~`).
  - Then C0 control sequences, then UTF-8 with an ESC prefix for Alt
    (`macos-option-as-alt` on macOS).
  - Nothing is sent while the IME is composing.

### 7.3 Mouse (`input/mouse_encode.zig`)

- **Reporting modes:** X10, normal, button, any.
- **Formats:** X10 (coordinates capped at 222), UTF-8 (1005), SGR (1006), urxvt (1015),
  SGR-pixels (1016).
- Motion events are deduplicated per cell.
- **Shift** bypasses reporting, subject to `mouse-shift-capture` and XTSHIFTESCAPE.
- **Selection gestures:**
  - double-click selects a word, triple-click a line;
  - ctrl+triple-click selects command output;
  - rectangle select is ctrl/super+alt on Linux.
- Linux defaults: `copy-on-select = primary`, middle-click pastes primary.

### 7.4 Keybindings (`input/Binding.zig`, 4.9 kLOC)

- **Trigger syntax:** `[prefixes:][table/]trigger[>trigger…]=action[:param]`.
- **Prefixes:** `unconsumed:`, `all:`, `global:`, `performable:`.
- **Triggers** are physical W3C keys, unicode codepoints or `catch_all`. Physical keys
  take priority.
- **Leader sequences** (`ctrl+a>n`) are stored in a trie (`Set.Value = leader | leaf |
  leaf_chained`).
  - There is **no timeout**.
  - An unmatched key flushes the buffered keys to the pty.
- **Chains:** `chain=` runs several actions from one binding.
- **Key tables:** a stack of named tables via `activate_key_table[_once]`, giving
  vim-like modes.
- About 90 actions, including `csi:`, `esc:` and `text:` for sending raw sequences.

### 7.5 IME and clipboard

- **IME:** GTK preedit start, changed, end and commit (`class/surface.zig:3197-3330`).
  - The comments note that ibus and the simple IM fire commit and preedit-end in
    opposite orders.
  - `Surface.preeditCallback` (`Surface.zig:2649`) stores preedit codepoints in
    `renderer_state.preedit`, and the renderer draws them at the cursor.
  - The IME cursor rectangle is updated before every key.
- **OSC 52:** `clipboard-read = ask` by default and `clipboard-write = allow`.
  `ClipboardConfirmationDialog` handles both OSC 52 "ask" and unsafe paste.
- **Paste safety** (`input/paste.zig`):
  - Bracketed paste strips or replaces dangerous control bytes, as xterm does
    (NUL, ESC, ^C and so on).
  - A paste is "unsafe" if it contains a newline (unbracketed) or `ESC[201~` (bracketed).
    Unsafe pastes need confirmation.

---

## 8. tmux control mode (very important for this project)

### 8.1 Status in one paragraph

Ghostty includes a well-tested **protocol layer** and a **headless "viewer" state
machine** for tmux control mode, about 4.7 kLOC under `src/terminal/tmux/`. It detects
`ESC P 1000 p`, parses control-mode lines into typed notifications, runs a command
queue against tmux, and **keeps one complete Ghostty `Terminal` per tmux pane**, filled
with `capture-pane` history plus live `%output`. **None of this reaches the GUI.** The
viewer's `windows` action is literally `// TODO` in `termio/stream_handler.zig:485-487`.
Keystrokes are not routed to panes, resize is not sent to tmux, and the per-pane
terminals are never rendered. While in control mode, the user sees only the main
terminal, with the DCS payload swallowed.

There is no tmux reference in `macos/Sources` or in `src/apprt`. The C API header exposes
only a build-info flag, `GHOSTTY_BUILD_INFO_TMUX_CONTROL_MODE`
(`include/ghostty/vt/build_info.h:70-74`).

### 8.2 Build gating

- `terminal_options.tmux_control_mode` is **synthesized from the `oniguruma` option**
  (`src/terminal/build_options.zig:296`), because the control parser uses Oniguruma
  regexes.
- The GUI build has oniguruma on (`src/build/Config.zig:714`).
- `terminal/main.zig:31` exports `tmux` as an empty struct when the option is off.

### 8.3 Detection and lifecycle (DCS)

- **`terminal/dcs.zig:53-74`:**
  - The DCS final byte `p` with exactly one param equal to `1000` starts tmux mode.
  - The handler state becomes `.tmux` (a `ControlParser`) and it emits `Command{.tmux = .enter}`.
  - Every following DCS byte goes to `ControlParser.put`.
  - DCS unhook (ST) emits `.exit` (`dcs.zig:168-170`).
- **`parse_table.zig:245-265`:** UTF-8 bytes inside DCS are kept as payload (§3.1).
  This change was made specifically for tmux pane content.
- **`termio/stream_handler.zig:418-489`:**
  - `.enter` allocates a `terminal.tmux.Viewer`; `.exit` frees it.
  - Every other notification goes to `viewer.next(.{ .tmux = n })`, which returns a
    slice of actions:
    - `.command`: the text, newline included, is written to the **pty**
      (`termio.Message.writeReq`). In control mode the pty's stdin is tmux's command
      channel.
    - `.exit`: ignored ("We may want to handle this in the future to notify our GUI").
    - `.windows`: TODO.
- All of this runs **on the io-reader (parse) thread, under the renderer mutex**.

### 8.4 Control-mode line parser (`tmux/control.zig`, 884 lines)

- `Parser{state: idle|broken|notification|block, buffer, max_bytes = 1 MiB}`.
- It consumes **one byte at a time** (`put`).
- In idle state, any byte other than `%` drops it into `broken` and emits `.exit`.
- **Block handling** (`%begin … %end/%error`):
  - Payload is buffered until a line exactly matches `%end|%error <time> <cmd#> <flags>`
    with numeric fields (`parseBlockTerminator`).
  - This is robust against payload lines that start with `%end`, and there are tests
    for that.
  - There is a TODO to match the `%begin` fields against `%end` (`control.zig:178-208`,
    `TODO(tmuxcc)`).
- **Notifications parsed** (`Notification` union, `control.zig:497-575`):
  - `enter`/`exit` (synthetic)
  - `block_end`/`block_err` (raw payload)
  - `%output %<pane> <data>`
  - `%session-changed $id name`
  - `%sessions-changed`
  - `%layout-change @win layout visible_layout flags`
  - `%window-add`
  - `%window-renamed`
  - `%window-pane-changed`
  - `%client-detached`
  - `%client-session-changed`
  - Unknown notifications are logged and ignored.
- **Implementation detail:** each notification type compiles an **Oniguruma regex per
  line** (`oni.Regex.init` inside `parseNotification`, e.g. `control.zig:216-245`). That
  is fine for correctness and wasteful for heavy `%output` streams.
- **Gap I found:** tmux escapes bytes < 0x20 and `\` in `%output` as `\ooo` octal.
  - The `output.data` field is commented `// unescaped`, but I could not find any
    octal-decoding code in `src/terminal/tmux/` (no `unescape` or octal handling).
  - The only output test uses plain text (`control.zig:759-770`).
  - So ESC sequences inside `%output` would currently reach the pane terminal as
    literal `\033…` text. Treat this as a likely bug or unfinished piece. Verify before
    relying on it.
- **Not handled:**
  - `%extended-output` (pause mode);
  - `%pause` and `%continue`;
  - `%window-close`, `%unlinked-window-*`;
  - `%pane-mode-changed`;
  - `%subscription-changed`;
  - `%paste-buffer-*`;
  - `%config-error`;
  - `%message`.
  These fall into "unknown notification".

### 8.5 Layout parser (`tmux/layout.zig`, 638 lines)

- `Layout{width, height, x, y, content: pane(id) | horizontal([]Layout) | vertical([]Layout)}`.
- It parses tmux layout strings such as `bb62,159x48,0,0{79x48,0,0,79x48,80,0}`.
- It verifies tmux's 16-bit rotating checksum (`parseWithChecksum`, `Checksum.calculate`)
  and is tested against tmux's documented example (`layout.zig:633`).
- Arena-allocated tree.

### 8.6 Format helpers (`tmux/output.zig`, 573 lines)

- `Variable` is an enum of the tmux format variables Ghostty uses.
- Pane state: `cursor_x/y`, `cursor_flag`, `cursor_shape`, `cursor_color`,
  `cursor_blinking`.
- Alternate screen: `alternate_on`, `alternate_saved_x/y`.
- Modes: `insert_flag`, `wrap_flag`, `keypad_flag`, `keypad_cursor_flag`, `origin_flag`.
- Mouse: `mouse_all/button/standard/utf8/sgr_flag`.
- Other pane fields: `focus_flag`, `bracketed_paste`, `scroll_region_upper/lower`,
  `pane_tabs`, `pane_id`.
- Window and session fields: `session_id`, `window_id`, `window_width/height`,
  `window_layout`, `version`.
- `comptimeFormat(vars, delim)` builds the `-F` format string at compile time.
- `FormatStruct(vars)` generates a struct type at compile time.
- `parseFormatStruct` parses one delimited output line into that struct.
- The result is type-safe round-tripping of tmux formats, which is a nice pattern.

### 8.7 Viewer state machine (`tmux/viewer.zig`, 2,594 lines including ~1,100 of tests)

The header (`viewer.zig:44-160`) has a full ASCII diagram.

**States:**

1. `startup_block`: wait for the reply block to the initial command (e.g. `attach`).
2. `startup_session`: wait for `%session-changed`, then enter `command_queue` with
   `[tmux_version, list_windows]`.
3. `command_queue`: the steady state.
   - **Only one command is in flight at a time**, to avoid ordering confusion
     (`command_queue: CircBuf(Command)`).
   - Each `%end`/`%error` block is matched to the head of the queue.
4. `defunct`: after `%exit` or an error.

**Commands** (`viewer.zig:1290-1385`):

| Command | Exact tmux command |
|---|---|
| `tmux_version` | `display-message -p '#{version}'` |
| `list_windows` | `list-windows -F '#{session_id} #{window_id} #{window_width} #{window_height} #{window_layout}'` |
| `pane_history` | `capture-pane -p -e -q [-a] -S - -E -1 -t %N` (history only, with SGR escapes) |
| `pane_visible` | `capture-pane -p -e -q [-a] -t %N` |
| `pane_state` | `list-panes -F '<25 vars joined by ;>'` |
| `user` | raw user text |

**Data:**

- `windows: ArrayList(Window{id, width, height, layout_arena, layout})`.
- `panes: AutoArrayHashMap(pane_id, Pane{terminal: Terminal, output_stream})`.
  - **Each tmux pane is a full Ghostty `Terminal`** with its own pages and scrollback.
  - `output_stream` is a `stream_terminal.Stream` bound to that terminal and recreated
    lazily. The comment notes pane values can move when the map is rebuilt, so the
    stream's terminal pointer is re-bound before each use.

**Flow:**

- After `list-windows`, `syncLayouts` parses each layout and walks its leaves
  (`initLayout`). Existing panes are kept; new panes get a `Terminal` sized
  `layout.width×height` and queue `pane_history` + `pane_visible` for **both primary and
  alternate screens**, then `pane_state`.
- `receivedPaneHistory` (`viewer.zig:1076-1114`):
  - feeds the capture through a VT stream;
  - then does `index()` rows times to push it all into scrollback;
  - then homes the cursor, leaving the active area blank.
- `receivedPaneVisible` erases the display and writes the visible capture.
- `receivedPaneState` (`viewer.zig:937-1074`) restores:
  - active screen;
  - cursor position and shape on the right screen;
  - alt-screen saved cursor (ignoring tmux's MAX_INT sentinel);
  - cursor visible and blink;
  - insert, wrap, keypad, cursor-keys and origin modes;
  - all mouse modes;
  - focus reporting and bracketed paste;
  - scroll region (validated);
  - tab stops.
  This is a careful, complete reconstruction of pane terminal state.
- `%output` → `receivedOutput` → `pane.outputStream().nextSlice(data)`, subject to the
  octal caveat above.
- `%layout-change` → re-sync of that window's layout.
- `%window-add` → re-queue `list-windows`.
- `%session-changed` while running → full reset: an empty `windows` action, then
  `list-windows` again. The version string is preserved.
- **Memory safety for actions:**
  - Actions are allocated in an arena that is reset on each `next()`.
  - A pre-allocated single-action slot guarantees `.exit` can be returned without
    allocating (`viewer.zig:186-196, 1249-1260`).

**Known TODOs and fragility** (`viewer.zig:19-36`):

- Startup should tolerate a session notification and block arriving out of order.
- `%output` should be ignored for panes whose capture isn't complete. This is a real
  race: output that arrives between `capture-pane` and the queue reaching the pane is
  applied and then partially overwritten.
- The active pane should be tracked for initial focus.
- Ordering assumptions come from reading the tmux source as of December 2025 and are
  not documented as stable.
- Overflow of pane width or height is cast unsafely, with a TODO (`viewer.zig:1189`).

### 8.8 What remains, for a full iTerm2-style `tmux -CC`

1. The apprt must turn `.windows` actions into native tabs and splits. Tmux windows
   become tabs and the layout tree becomes the split tree; Ghostty's immutable
   `SplitTree` is a natural target. Window IDs are stable and never reused, per the
   viewer comment.
2. A **surface kind with no PTY**: a surface rendering a `Viewer.Pane.terminal`,
   whose input is encoded and sent as `send-keys -H -t %N …` (or `send -l`), and whose
   resize becomes `refresh-client -C WxH` or per-window sizing. The termio backend
   abstraction (`termio/backend.zig`) is where this would plug in, but nothing exists.
3. **Thread model:** pane terminals currently live inside the main surface's stream
   handler, on the parse thread, under that surface's mutex. Rendering them needs
   cross-surface locking or a dedicated tmux IO owner.
4. Protocol completeness:
   - octal unescaping;
   - `%extended-output`, pause and continue flow control (needed over slow SSH links);
   - `%window-close` and `%unlinked-window-*`;
   - `%exit` reason;
   - matching `%begin`/`%end` command numbers;
   - per-pane output buffering until capture completes.
5. Performance: per-byte DCS dispatch and per-line regex compilation; a hand-written
   line splitter would be cheaper.
6. UX: detach and reattach, the "tmux in tmux" guard, and what to show in the
   originating surface (iTerm2 shows a small control window).

**Takeaway:** Ghostty's design gives a solid template for the protocol side:

- DCS-driven entry;
- a byte-wise line parser with a size cap;
- typed notifications;
- a single-in-flight command queue;
- comptime-typed `-F` formats;
- layout parsing with checksum;
- pane state reconstruction via `capture-pane -e` plus `list-panes -F`.

The hard GUI and plumbing half is not built yet.

---

## 9. Config, themes, live reload, CLI

- **Format** (`src/cli/args.zig:1391-1500`):
  - `key = value`, with whole-line `#` comments.
  - An empty value resets the key to its default. Repeatable keys accumulate.
  - Files and the CLI share one parser: each file line is rewritten to `--key=value`.
- **Load order** (`Config.zig:4054-4069, 4245`):
  1. defaults;
  2. `$XDG_CONFIG_HOME/ghostty/config` and `config.ghostty`;
  3. CLI args;
  4. recursive `config-file` includes (`?` prefix means optional; cycles detected);
  5. `finalize`.
- **Themes:**
  - Looked up in `~/.config/ghostty/themes`, then in bundled themes.
  - A theme is just a restricted config file.
  - `theme = light:X,dark:Y` switches with the system color scheme.
- **Conditional config** (`config/conditional.zig`, `Config.zig:4553-4596`):
  - The config records `_replay_steps`.
  - When the conditional state (light/dark, OS) changes, it replays all steps into a
    fresh config. Files are not re-read.
- **Live reload:**
  - Triggers: keybind (ctrl+shift+comma), SIGUSR2, or a color-scheme change.
  - **There is no file watching.**
  - `App.updateConfig` → each `Surface.updateConfig` (`Surface.zig:1784-1880`):
    - rebuilds a surface `DerivedConfig`;
    - possibly rebuilds the font grid, keeping a manually adjusted size;
    - sends a **renderer DerivedConfig** to the renderer thread;
    - sends a **termio DerivedConfig** to the io thread (`change_config` message).
  - **Each thread owns its own immutable derived copy**, so no config is shared across
    threads. This pattern is worth copying.
  - Some options apply only to new surfaces.
- **CLI actions** (`src/cli/ghostty.zig:31-88`, `ghostty +action`):
  - version, help;
  - list-fonts, list-keybinds, list-themes (TUI preview), list-colors, list-actions;
  - show-config, explain-config, validate-config, edit-config, show-face;
  - crash-report;
  - **ssh**, ssh-cache;
  - new-window, new-tab, toggle-quick-terminal;
  - boo.

---

## 10. Testing, fuzzing, benchmarks

- **Unit tests** are inline Zig `test` blocks: thousands in total, e.g. 450 in
  `Terminal.zig` and 294 in `PageList.zig`.
  - Run with `zig build test -Dtest-filter=…` and `zig build test-lib-vt` (`AGENTS.md`).
  - `zig build test-valgrind` and `valgrind.supp` exist.
- **Slow runtime safety:** `slow_runtime_safety` enables page and PageList integrity
  checks (`assertIntegrity`).
- **Tripwire** (`src/tripwire.zig`) injects faults to test OOM paths in init, resize
  and compression.
- **Fuzzing** (`test/fuzz-libghostty/`): AFL++ harnesses.
  - `fuzz-parser`: byte-at-a-time Parser.
  - `fuzz-osc`: OSC parser with an allocator.
  - `fuzz-stream`: full Terminal plus readonly stream; the first byte chooses the SIMD
    or scalar path.
  - A seed corpus and crash-replay script are included.
- **Conformance** (`test/esctest/`): ThomasDickey's **esctest2** runs against
  libghostty-vt without a GUI.
  - Replies (DECRQCRA checksums, DA, CPR) are fed back to it, so DECRQCRA support
    exists mainly for testing.
  - It runs in CI but does not fail the build.
  - The README mentions a broader xterm audit (issue #632).
- **Unicode width:** `test/ucs-detect.sh`.
- **Benchmarks** (`src/benchmark/`, `ghostty-bench`):
  - TerminalStream, TerminalParser, OscParser, ApcParser, CodepointWidth,
    GraphemeBreak, IsSymbol, HyperlinkMap, ScreenClone, TerminalResize,
    TerminalSnapshot, TerminalFormatter, Page/ScrollbackCompression, CApi.
  - **`ghostty-gen`** (`src/synthetic/`) generates deterministic synthetic data:
    random UTF-8, OSC, kitty, bytes.
  - `src/benchmark/AGENTS.md` sets methodology: generate once, then `hyperfine` with
    warmups. Never pipe the generator into the benchmark, and never run benchmarks in
    parallel.
- **Inspector:** a built-in ImGui terminal inspector (`src/inspector/`) records PTY
  reads and VT events per surface. This is a strong debugging aid.

---

## 11. Notable challenges and workarounds (with sources)

- **Unfair mutex starvation** of the renderer under heavy output: fixed with the
  demand/handoff protocol (`renderer/State.zig:35-102`).
- **macOS tty 1 KiB read cap** throttling producers: fixed with the gather/parse
  pipeline (`termio/Exec.zig:1264-1300`).
- **Per-frame screen clone** blocked IO: replaced by the incremental `RenderState`
  (`terminal/render.zig:20-62`).
- **`std.debug.assert` not optimized away** in ReleaseFast (Zig 0.15.2), costing 15–20%
  in hot loops. Ghostty uses its own inline assert (`src/quirks.zig:32-44`).
  `quirks.zig` also centralizes font-specific hacks, e.g. disabling default features
  for certain faces.
- **GtkGLArea** main-thread-only lifecycle: replaced by an EGL offscreen and DMA-BUF
  widget (`render_surface.zig:20-44`).
- **Mesa can't export sRGB textures** as DMA-BUF, so frames are blitted to RGBA8 first
  (`opengl/Target.zig:16-19`).
- **Multi-GPU DMA-BUF modifier failures**: fall back to `glReadPixels`
  (`render_surface.zig:157-169`).
- **Vulkan plus GL conflict and startup cost**: `GDK_DISABLE=vulkan`
  (`application.zig:3250`).
- **X11 modifier state lag**: peek XKB state-notify events (`winproto/x11.zig:121-156`).
- **IME ordering** differs between ibus and the simple IM (`class/surface.zig:1291-1295`);
  IME commits are attached to key events.
- **Mode 2027 / grapheme width:** the slow path replays the cell's codepoints. VS15/VS16
  can change width retroactively and force a wrap. Without 2027, zero-width characters
  attach blindly.
- **Grapheme DoS:** clusters are capped at 64 codepoints. Robin Hood PSL statistics
  guard against hash flooding. Saved modes hold a single value.
- **Synchronized-output deadlock** from a buggy app: 1 s reset timer.
- **"Bad ligatures"** fi/fl/st split shaping runs. The cursor splits runs so ligatures
  don't hide the cursor position.
- **Shaping was 96% of frame time** before the position-independent run cache.
- **Reflow is O(scrollback)**; the deferred-reflow TODO is at `PageList.zig:1266`.
- **Cross-page IL/DL panics on OOM** rather than leaving a corrupt list
  (`Terminal.zig:3018-3027`).
- **"Zombie styles"** integrity check disabled because of fast paths (`page.zig:640-649`).
- **CoreVideo deadlock**: the display link must start and stop on the main thread
  (`renderer/DisplayLink.zig:1-29`).
- **Cursor blink** costs a full update and redraw every 600 ms. Valgrind runs need a
  slower blink (`renderer/Thread.zig:836-850`).

---

## 12. Lessons for a new terminal (Linux first, SSH-heavy, remote X11 + local GPU, tmux)

**Core and state**

- **Consider adopting libghostty-vt as the VT core.** It is a C API, cross-platform
  (including Windows), fuzzed, esctest-checked, and includes key, mouse and paste
  encoders and a render-state API. The cost is an unstable API and a Zig toolchain.
  Either way, its design is the benchmark to compare against.
- **Use fixed-size, offset-addressed, zero-initialized pages** (~400 KiB each). Clone,
  compress, snapshot and serialize all become `memcpy`. Steady-state scrolling recycles
  the oldest page and allocates nothing.
- **Use 8-byte cells.** Keep styles in a per-page ref-counted set, and graphemes and
  hyperlinks in side maps keyed by cell offset. Keep "row might have X" flags so plain
  rows can be memset.
- **Make rows indirect** (row header → cell offset), so scrolling regions and IL/DL
  swap headers instead of copying cells.
- **Use tracked pins** for every position that must survive mutation (cursor, viewport,
  selection, search hits, images), plus generation serials on reused nodes. Keep the
  number of pins small.
- **Set the scrollback limit in bytes**, and consider LZ4-compressing cold pages while
  keeping their virtual address range reserved.
- **Reflow is O(history)** in Ghostty. If you expect huge scrollback, plan lazy reflow
  from the start.

**Threading and IO**

- **Use one mutex for terminal state**, but make it fair for the renderer: a demand
  counter plus a yield at batch boundaries. Snapshot only dirty rows under the lock and
  do the rest unlocked.
- **Split PTY reading** into a gather thread and a parse thread with a small ring of
  large buffers. Use spin plus short-poll bridging for saturated streams, and deliver
  immediately for interactive trickles. Backpressure comes from the bounded ring.
- **Use bounded typed mailboxes** with async wakeups. Coalesce resize (25 ms). Put a
  timeout on synchronized output (1 s). Keep a per-thread immutable "derived config"
  for live reload.

**Parsing**

- **SIMD the ground state:** bulk UTF-8 decode up to ESC, then hand printable runs to a
  `printSlice` fast path. Bulk-consume CSI params and APC payloads.
- **Keep a byte-at-a-time debug path** as an oracle and fuzz both paths.

**Rendering, especially for remote X11**

- Ghostty's GPU path is worth copying for local use:
  - bg colors as one SSBO read by a full-screen fragment shader;
  - glyphs as instanced quads from a grow-only atlas;
  - procedural box-drawing and Powerline sprites;
  - a position-independent shaping cache;
  - cursor-aware run splitting.
- It also has gaps you should avoid:
  - Linux has no frame cap or vsync;
  - every frame re-uploads all cell buffers and calls `glFinish`;
  - GPU frames are presented to GTK as full textures with no damage regions.
- **Over remote X11 Ghostty has no good answer.** It needs local GL 4.3 through EGL
  (llvmpipe works) and then pushes full-frame `glReadPixels` images through GTK on every
  update. For your remote-X11 requirement, plan:
  - a **CPU renderer** that tracks damage at cell or row granularity and sends only
    changed rectangles (XRender glyph sets or `XPutImage`/MIT-SHM-less fallback for
    remote);
  - a **frame-rate cap** (or latency-adaptive pacing), plus coalescing, so bursts don't
    flood the X connection;
  - runtime detection of remote or indirect displays (e.g. `DISPLAY` host part, no
    DRI3/GLX direct, llvmpipe `GL_RENDERER`) to pick the backend;
  - GL ≤ 3.3 (or GLES 3) as the minimum for the GPU path if you want broad driver
    compatibility. Ghostty's 4.3 requirement (SSBOs) excludes some older and virtual GPUs.
- **Failure must be visible.** Ghostty's "can't get GL context" page is currently
  unreachable (`setError` has no callers). Always fall back to a working renderer.

**tmux**

- Ghostty's `src/terminal/tmux/` is a good blueprint for the protocol half:
  - DCS 1000p detection, with the parser keeping UTF-8 bytes inside DCS;
  - a capped line parser;
  - typed notifications;
  - one command in flight;
  - comptime `-F` format structs;
  - checksummed layout parsing;
  - per-pane `Terminal` objects populated with `capture-pane -p -e -q [-a] -S - -E -1`
    plus `capture-pane` for the visible area, plus `list-panes -F` state restore.
- Avoid its gaps:
  - Decode `%output` octal escapes.
  - Buffer output for panes until their capture completes.
  - Implement `%extended-output` and pause/continue for slow SSH links.
  - Avoid per-byte DCS dispatch and per-line regex compilation.
- **Design pane surfaces as PTY-less terminal views from day one.** Input goes to
  `send-keys`, resize to `refresh-client -C`, and layout maps to your split tree.
  Ghostty's termio and backend split shows where this abstraction belongs, but it never
  built it.

**Input and UX**

- **Key handling:**
  - Use physical keys (W3C codes) plus the unshifted codepoint, and implement the kitty
    keyboard protocol with a per-screen flag stack.
  - Port the legacy and function-key tables from foot, as Ghostty did.
  - Run every key press *and release* through the IME and attach commits to key events.
  - On X11, fix modifier state via XKB state notify.
- **Bindings:** a trie of key sequences, key tables as a mode stack, and
  `performable:`/`unconsumed:` semantics. These solve real conflicts with TUI apps.
- **Clipboard and paste safety:**
  - OSC 52 read asks by default and write is allowed;
  - bracketed-paste sanitizing;
  - an unsafe-paste prompt.
- **SSH UX:** ship a terminfo-install helper (`+ssh` with a cache), or fall back to
  `xterm-256color` and forward `COLORTERM`/`TERM_PROGRAM`. Remote hosts lacking your
  terminfo is a top user complaint.

**Testing**

- Inline unit tests, AFL++ fuzzing of parser and stream, esctest2 conformance on a
  headless core, deterministic synthetic benchmark data with hyperfine, fault injection
  for OOM, and a live inspector.

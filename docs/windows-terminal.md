# Windows Terminal / OpenConsole: architecture and lessons for a new terminal

Source analyzed: `vendor/terminal` (microsoft/terminal) at commit `9e6cf223d`
(2026-10-19). This one repository contains conhost/OpenConsole, the ConPTY
API (`conpty.dll`), and the Windows Terminal app.

Paths below are relative to `vendor/terminal/`. Line numbers refer to that
commit. Anything not read directly in code is marked **inference** or
**unverified**. Earlier analyses are cited as A§n (`alacritty.md`), G§n
(`ghostty.md`) and S§n (`synthesis.md`).

This is the main reference for puritty's Windows side. Section 2 (ConPTY) is
the most important part. It corrects some things that S§10 and A§2.3 took
from older ConPTY behavior.

---

## 0. TL;DR

- **ConPTY no longer re-renders.** The old design had `VtEngine`, a
  "renderer" that diffed conhost's buffer and emitted its own VT. It was
  deleted in Aug 2024 (`450eec48d`, #17510). Modern conhost in PTY mode
  works like this:
  - It still parses everything into its own buffer.
  - It forwards the **client's VT output to the terminal unmodified**
    (`src/host/_stream.cpp:380-435`), apart from a few small rewrites (§2.4).
  - It **translates classic Console API calls synchronously to VT**:
    `SetConsoleCursorPosition` becomes CUP, `ScrollConsoleScreenBuffer`
    becomes IL/DL or DECCRA/DECFRA, and so on (`src/host/VtIo.cpp`).
  - It **no longer answers VT queries itself**. The terminal answers them
    (`src/host/outputStream.cpp:54-58`).

  Most of the "ConPTY mangles my escape sequences" folklore, A§2.3 included,
  describes Windows builds before 24H2 or a `conpty.dll` older than about
  WT 1.22.
- **ConPTY is still not transparent.** What remains:
  - Bytes are round-tripped UTF-8 → UTF-16 → UTF-8, so invalid UTF-8 becomes
    U+FFFD.
  - LF→CRLF translation applies when the client hasn't set
    `DISABLE_NEWLINE_AUTO_RETURN`.
  - Conhost injects `?1004h`/`?9001h` after RIS and mode resets.
  - Console-API output is lossy: 16 colors, UCS-2, `SGR 0` before every
    attribute change.
  - Conhost and the terminal **reflow separately on resize**, and conhost
    keeps **no scrollback**, so buffer and cursor state can drift. Conhost
    patches cursor drift by sending DSR-CPR and blocking
    `GetConsoleScreenBufferInfo` for up to about 500 ms.
  - **Input** goes through conhost's INPUT_RECORD layer. The terminal is
    asked for *win32-input-mode* (`CSI ?9001h`) and should speak it.

  The in-process ConPTY spec (`doc/specs/#13000`) calls the drift
  "an unsolvable issue" of the out-of-process design.
- **`ClosePseudoConsole` no longer waits** in the OSS `conpty.dll` (and,
  per the commit title, in Windows 11 24H2). It only closes handles
  (`src/winconpty/winconpty.cpp:395-431`, `7fd9c5c78`). Older inbox
  kernel32 builds wait `INFINITE` for conhost to exit, which deadlocks if
  nobody is draining the output pipe. That is the A§2.3/S§10 drop-order
  issue. Code for both behaviors.
- **The connection abstraction is small:** `Initialize(bag)`, `Start`,
  `WriteInput(UTF-16)`, `Resize(rows, cols)`, `Close`, a `TerminalOutput(UTF-16)`
  event, a `StateChanged` event and `State`
  (`src/cascadia/TerminalConnection/ITerminalConnection.idl`).
  - Each backend owns its reader thread and UTF-8 decoding.
  - Implementations: `ConptyConnection`, `AzureConnection` (websocket plus
    OAuth device flow, with resize as a REST call) and test/debug ones.
  - **There is no SSH backend.** SSH profiles are auto-generated from
    `~/.ssh/config` and simply run `ssh.exe` inside ConPTY
    (`SshHostGenerator.cpp`). There is no tmux integration.
- **Parsing happens on the connection's reader thread**, under one fair ticket
  lock shared with the render thread. Up to 128 KiB is parsed per lock
  acquisition. Rendering is a separate thread paced by the DXGI frame-latency
  waitable object. This is the same shape as Alacritty and Ghostty.
- **AtlasEngine** is the renderer: D3D11 with its own glyph atlas, or a
  Direct2D fallback for WARP and old GPUs.
  - Glyphs are shaped with DirectWrite **on the CPU while the lock is held**,
    then cached per row.
  - Each glyph is rasterized by D2D into a single BGRA atlas texture. When the
    atlas fills, it is **cleared entirely** (no LRU).
  - It draws instanced quads with a dual-source-blend pixel shader that also
    does ClearType.
  - **Every frame redraws the whole back buffer.** Row-level invalidation only
    decides which rows are re-shaped and which dirty and scroll rects go into
    `Present1` as a compositor hint.
- **Process and UI model:** one process, one UI thread, many windows. The old
  Monarch/Peasant COM remoting was removed in Dec 2024 (`8bbf00e05`, #18215).
  - XAML Islands host everything, and many workarounds exist for keys and
    mouse input that XAML swallows.
  - IME is a hand-written TSF client. Composition text is drawn inline by the
    renderer.
  - Keyboard: legacy encoding, win32-input-mode, and the **kitty keyboard
    protocol (all 5 flags)**. No modifyOtherKeys.
- Parser and buffer details worth knowing:
  - The parser works on UTF-16 with a SIMD fast path.
  - **DCS payloads drop non-ASCII**, and APC/PM/SOS are ignored, so there
    is no kitty graphics.
  - Sixel is supported, and so are DRCS soft fonts, 6 pages, macros and
    rectangular ops.
  - Grapheme clustering uses a 4-stage trie from Unicode 16 with three
    "text measurement" modes. ConPTY gets the same mode through a
    `CreatePseudoConsole` flag.
  - Scrollback is a ring of rows in one `VirtualAlloc` reservation with
    commit-on-demand, **capped at 32 767 rows**.

---

## 1. Repository map

| Area | Path | What it is |
|---|---|---|
| conhost / OpenConsole | `src/host`, `src/server`, `src/interactivity` | Console server: the ConDrv IOCTL dispatcher (`src/server`), Console API implementations (`src/host/getset.cpp`, `directio.cpp`, `_stream.cpp`), cooked read, the classic window (`src/interactivity/win32`). OpenConsole.exe is conhost built from this repo. |
| ConPTY host side | `src/host/VtIo.*`, `VtInputThread.*`, `PtySignalInputThread.*` | PTY mode: VT out, VT in, the signal pipe |
| ConPTY API | `src/winconpty` | `conpty.dll` / static lib: `ConptyCreatePseudoConsole` etc. Spawns OpenConsole/conhost with `--headless`. NuGet `Microsoft.Windows.Console.ConPTY` (`package/winconpty.nuspec`) |
| VT parser | `src/terminal/parser` | `StateMachine` plus `OutputStateMachineEngine` (app output) and `InputStateMachineEngine` (terminal → conhost input) |
| VT semantics | `src/terminal/adapter` | `AdaptDispatch` (all output sequences), `InteractDispatch` (input side), `SixelParser`, `FontBuffer` (DRCS), `MacroBuffer`, `PageManager` |
| Key/mouse encoding | `src/terminal/input` | `TerminalInput` (legacy, win32-input-mode, kitty) |
| Buffer | `src/buffer/out` | `TextBuffer`, `ROW`, `TextAttribute`, `ImageSlice`, reflow, search |
| Unicode | `src/types/CodepointWidthDetector.cpp`, `src/tools/GraphemeTableGen` | Width and grapheme tables |
| Renderer | `src/renderer/base` (Renderer and render thread), `atlas` (AtlasEngine), `gdi`, `uia`, `wddmcon` | Shared by conhost and WT |
| Terminal model | `src/cascadia/TerminalCore` | `Terminal` = buffer + parser + `ITerminalApi` + `IRenderData` |
| Connections | `src/cascadia/TerminalConnection` | `ITerminalConnection`, Conpty/Azure/Echo, `CTerminalHandoff` |
| Control | `src/cascadia/TerminalControl` | `ControlCore` (UI-free), `ControlInteractivity`, `TermControl` (XAML) |
| App | `src/cascadia/TerminalApp` | `TerminalPage`, `Tab`, `Pane` tree, actions, `DebugTapConnection` |
| Host process | `src/cascadia/WindowsTerminal` | `WindowEmperor` (process, message loop), `AppHost`, `IslandWindow`, `NonClientIslandWindow` |
| Settings | `src/cascadia/TerminalSettingsModel` | JSON model, profile generators (WSL, PowerShell, SSH, Azure, VS) |
| Small libs | `src/til` (headers in `src/inc/til`) | ticket lock, small_vector, RLE, throttled_func, u8u16, … |
| Tools | `src/tools` | ConsoleBench, benchcat, vtpipeterm, RenderingTests, GraphemeTableGen |

Because conhost and WT share the parser, adapter, buffer and renderer, a VT
feature generally lands in both at once. In ConPTY mode conhost creates **no
renderer at all**; `srvinit.cpp:836` creates one only `if
(!gci.IsInVtIoMode())`.

---

## 2. ConPTY internals

### 2.1 Process topology and the API

`_CreatePseudoConsole` (`src/winconpty/winconpty.cpp:119-278`):

1. **ConDrv handles.** It creates a ConDrv **server handle**, loading the
   driver first if needed (`0a3fbdefb`, 141-147). Then it creates a
   `\Reference` **client handle** from it (151-155).
   - The reference handle is what `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE`
     gives to children. Conhost lives as long as any reference is open.
   - The header comment (`winconpty.h:13-38`) explains the reference-count
     semantics.
2. **Signal pipe.** It creates an anonymous **signal pipe** (166-167).
3. **Choosing the host.** It picks the console host: `OpenConsole.exe` next
   to the module, else `<arch>\OpenConsole.exe`, else inbox
   `System32\conhost.exe` (`_ConsoleHostPath`, 49-99).
4. **Launch.** It launches the host:
   ```
   "<host>" --headless [--inheritcursor] [--ambiguousIsWide]
            [--textMeasurement graphemes|wcswidth|console]
            --width W --height H --signal 0x.. --server 0x..
   ```
   (194-204). The caller's in/out handles become conhost's
   stdin/stdout/stderr (207-211). `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` limits
   inheritance to exactly four handles (213-244).
5. **Result.** The `HPCON` is a heap struct `{hSignal, hPtyReference,
   hConPtyProcess}` (`winconpty.h:11-41`). The comment says this is an ABI
   shared with the OS.

**Exports** (`src/winconpty/dll/winconpty.def`, `src/inc/conpty-static.h:40-51`):

| Function | Effect |
|---|---|
| `ConptyCreatePseudoConsole[AsUser]` | Above. Duplicates the caller's handles as inheritable (496-499). Rejects 0×0 size (130). |
| `ConptyResizePseudoConsole` | Writes `{8, X, Y}` (u16s) to the signal pipe (288-302) |
| `ConptyClearPseudoConsole(keepCursorRow)` | Signal `{2, keep}`. Lets the terminal's "clear buffer" also clear conhost (GH#1193/#1882) |
| `ConptyShowHidePseudoConsole` | Signal `{1, show}`. Keeps conhost's pseudo-HWND iconic state in sync (GH#12515) |
| `ConptyReparentPseudoConsole` | Packed `{u16 3, u64 hwnd}`. Makes `GetConsoleWindow()` return a window owned by the terminal HWND (GH#2988) |
| `ConptyReleasePseudoConsole` | Closes `\Reference` early, so conhost exits when the last client leaves. The terminal then sees `ERROR_BROKEN_PIPE` on its output read (558-577) |
| `ConptyClosePseudoConsole` | Closes signal, reference and process handles. **Does not wait** (586-589, 426-433). The comment at 585 still says "Waits for conhost/OpenConsole to exit first"; that is stale. |
| `ConptyPackPseudoConsole` | Wraps handles from a default-terminal handoff into an HPCON (600-620) |

`kernel32`-compatible aliases (`CreatePseudoConsole = ConptyCreatePseudoConsole`
…) exist so P/Invoke users can switch DLLs without code changes (`.def`).

**Close semantics.** Before `7fd9c5c78` ("Align the OSS ConPTY API with
Windows 11 24H2", #17704), `ClosePseudoConsole` did `WaitForSingleObject(conhost,
INFINITE)` (and there was a `ConptyClosePseudoConsoleTimeout`). Conhost only
exits after it has flushed its output, so a caller that stopped reading output
before closing would deadlock. That is the A§2.3 hazard. With the current DLL,
closing just breaks the signal pipe. Conhost's `PtySignalInputThread::_Shutdown`
→ `VtIo::SendCloseEvent` → `CloseConsoleProcessState()` sends
`CTRL_CLOSE_EVENT` to the clients (`PtySignalInputThread.cpp:322-326`,
`VtIo.cpp:300-322`). Exit is detected when the output pipe reads EOF or
`ERROR_BROKEN_PIPE`. **Rule for puritty:** keep the output reader running
until EOF regardless; then either OS behavior is safe.

**Flags** (`conpty-static.h:26-38`). Only these four exist at this commit:

| Flag | Value | Meaning |
|---|---|---|
| `PSEUDOCONSOLE_INHERIT_CURSOR` | 0x1 | Conhost sends `CSI 6n` at start and adopts the reply as its cursor (§2.6) |
| `PSEUDOCONSOLE_GLYPH_WIDTH_GRAPHEMES` / `_WCSWIDTH` / `_CONSOLE` | 0x08 / 0x10 / 0x18 (mask 0x18) | Conhost's width algorithm (§4.3). **Set this to match your own measurement**, or conhost's cursor model diverges on emoji and combining marks |
| `PSEUDOCONSOLE_AMBIGUOUS_IS_WIDE` | 0x20 | East-Asian ambiguous = 2 columns (`3b8c5606e`) |

Older flags (`PSEUDOCONSOLE_RESIZE_QUIRK`, `PSEUDOCONSOLE_WIN32_INPUT_MODE`,
the `--vtmode` switch, and WT's experimental "passthrough mode") are **gone**.
The #13000 spec lists removing `--vtmode` and `--resizeQuirk` as goals of the
VtEngine removal (`doc/specs/#13000 - In-process ConPTY.md:226-232`), and a grep
of `src/` finds none of them. Passthrough is now the only mode.

**Pipes as WT uses them.** `ConptyConnection::Start` creates **one
duplex, overlapped, unnamed named pipe** with 128 KiB quotas via
`NtCreateNamedPipeFile` relative to `\Device\NamedPipe\`
(`src/types/utils.cpp:785-882`). It passes the same client end as both
`hInput` and `hOutput` (`ConptyConnection.cpp:411-413`). Conhost probes each
handle with `NtQueryInformationFile(FileModeInformation)` and uses overlapped
I/O if the handle allows it (`utils.cpp:750-756`, `VtIo.cpp:97-105`,
`VtInputThread.cpp:68-76`). Classic `CreatePipe` anonymous pipes also work, but
they are synchronous on both ends. That is why Alacritty needs helper threads
(A§2.3).

### 2.2 Bundling a newer ConPTY with your app

- The NuGet package ships `conpty.dll` and `OpenConsole.exe` for x86, x64 and
  arm64, plus `conpty.h`. It claims support for Windows 10 1809 (17763) and up
  (`winconpty.nuspec`).
- `conpty.dll` looks for `OpenConsole.exe` **next to itself** first, then in
  an arch subfolder, and falls back to inbox conhost (`winconpty.cpp:49-99`).
  If you ship `conpty.dll` but forget OpenConsole.exe, you silently get the
  inbox conhost and its old behavior.
- WT links the static lib and does not dllimport anything
  (`TerminalConnection.vcxproj:84-96`).
- **Why bundle at all.** Inbox conhost before 24H2 still has VtEngine and its
  re-rendering. Every fix in §2.8 reaches users only through the bundled
  DLL or a new Windows release. Alacritty's approach of an optional
  `conpty.dll` found on PATH (A§2.3) is the same idea. For puritty, **ship
  it** rather than make it optional.
- **ConDrv architecture.** `EnsureNativeArchitecture()` in WT's
  `main.cpp` exists because conhost must match the ConDrv architecture. Ship
  native builds per architecture.

### 2.3 Inside conhost in PTY mode: threads and data flow

```
 terminal ──(VT in, UTF-8)──► VtInputThread ──InputStateMachineEngine──► INPUT_RECORDs / raw VT
                                                              │                       ▼
                                                              │              InputBuffer ──► client ReadConsoleInput / ReadFile
 terminal ◄──(VT out, UTF-8)── VtIo::_flushNow ◄── VtIo::Writer ◄── WriteCharsVT / Console API impls ◄── client WriteConsole / API calls
                                                                 └► StateMachine/AdaptDispatch → conhost TextBuffer (no renderer)
 terminal ──(signal pipe)──► PtySignalInputThread ──► resize / clear / show-hide / reparent
```

- **One console lock** for everything: `til::recursive_ticket_lock`
  (`src/host/server.h:153`, `src/inc/til/ticket_lock.h`). It is a fair FIFO
  lock using WaitOnAddress.
- **VtInputThread** reads 4 KiB at a time, converts UTF-8 to UTF-16 with
  carried state, and parses under the global lock. It uses global
  `LockConsole()` so Ctrl+C dispatch happens on unlock. With overlapped I/O it
  **queues the next ReadFile before parsing**, so input isn't delayed while it
  waits for the lock (`VtInputThread.cpp:51-161`).
- **VtIo output buffering** (`VtIo.cpp:433-558`):
  - `Writer` is an RAII "cork": nested writers increment `_corked`, and the
    last `Submit()` flushes.
  - It double-buffers `_front`/`_back`. With an overlapped handle there is at
    most one `WriteFile` in flight. Before swapping buffers, it waits for the
    previous write.
  - Large buffers are released: over 128 KiB and more than twice what's used
    (500-505).
  - Exceptions "taint" a writer so half-built output is dropped (507-512).
  - `ERROR_BROKEN_PIPE` ends the session (546-549).
- **Overlapped output matters.** The #17510 commit message explains why:
  > "now that output cannot be 'skipped' anymore (VtEngine worked like a
  > renderer after all) it's become crucial to block conhost as little as
  > possible."

  **Consequence:** the old VtEngine could drop intermediate frames. The new
  design forwards every byte, so a terminal that reads slowly now
  back-pressures the client application. That is the Unix behavior.

### 2.4 The output path: what passes through, what is rewritten

The entry point for VT-mode writes is `WriteCharsVT`
(`src/host/_stream.cpp:380-435`):

1. `stateMachine.ProcessString(str)`: conhost parses the text into its own
   buffer and modes.
2. If writing to the active buffer, the **original string** is appended to the
   VT output, with two rewrites:
   - **LF → CRLF** if the client did not set `DISABLE_NEWLINE_AUTO_RETURN`
     (`WriteUTF16TranslateCRLF`, `VtIo.cpp:611-648`). It is applied blindly.
     The #17510 message admits it "may hypothetically break DCS sequences".
   - **Injections:** after a RIS, `CSI ?1004l` or `CSI ?9001l` in the stream,
     conhost appends `CSI ?1004h` and/or `CSI ?9001h` to re-enable the modes
     ConPTY depends on (`_stream.cpp:414-430`; offsets recorded by
     `StateMachine::InjectSequence`; `adaptDispatch.cpp:1866-1904, 3132-3134`).
     So **an app can never turn off focus reporting or win32-input-mode in
     the terminal**. The terminal must keep those modes on. Nested ConPTY
     relies on this.
3. **Encoding:** the client's text was already converted to UTF-16 by the
   console server, using the output codepage for `WriteConsoleA`/`WriteFile`.
   `WriteUTF16` converts it back to UTF-8 with `WideCharToMultiByte`
   (`VtIo.cpp:574-609`). Invalid input bytes have become U+FFFD by then, and
   lone surrogates are replaced (`SanitizeUCS2`, 399-431).

**VT queries are not answered by conhost.** `ReturnResponse` returns early in
PTY mode: "ConPTY should not respond to requests. That's the job of the
terminal." (`outputStream.cpp:47-65`). DA1, DSR, DECRQSS, OSC 4/10/11 queries
and so on travel to the terminal, and replies come back on the input pipe
(§2.5). Unknown sequences are still forwarded, but they mark conhost's cursor
as "may be wrong" (`outputStream.cpp:27-41`, §2.6).

**Kitty keyboard and conhost.** Conhost ignores `CSI = u` and related
sequences itself (`adaptDispatch.cpp:2079-2122`, `IsConPTY()` early returns).
It forwards them to the terminal like any other VT. The terminal then prefers
KKP over win32-input-mode (`terminalInput.cpp:226-234`). Its kitty-encoded keys
reach a *VT-input* client raw (§2.5). Conhost deliberately does **not**
translate win32-input-mode into KKP itself
(`ForceDisableKittyKeyboardProtocol(true)`, `VtIo.cpp:125-131`, TODO GH#19847).

**Classic Console API calls → VT.** These are translated synchronously while the
API call runs:

| API | VT emitted | Notes / losses |
|---|---|---|
| `WriteConsole` without VT processing (`WriteCharsLegacy`) | Text, CR/LF, OEM glyphs for control chars | Control chars become CP437 glyphs (☺ ♥ …) or are expanded. Tabs become spaces (`_stream.cpp:188-376`). **A delayed EOL wrap is forced with `\r\n`, which breaks reflow** (`_stream.cpp:207-225`; acknowledged in #17510) |
| `SetConsoleCursorPosition` | CUP | |
| `SetConsoleTextAttribute` | `SGR 0;…` | **Always starts with SGR 0** and has only 16 colors (`formatAttributes`, `VtIo.cpp:336-376`) |
| `SetConsoleCursorInfo` | DECTCEM | |
| `SetConsoleMode` output | DECAWM for `ENABLE_WRAP_AT_EOL_OUTPUT` | (`getset.cpp:455-463`) |
| `SetConsoleMode` input | `CSI ?1003;1006h/l` when `ENABLE_MOUSE_INPUT` changes | Quick-edit interplay, GH#9970 (`getset.cpp:367-387`) |
| `SetConsoleTitle` | `OSC 0;…ST` | Control chars sanitized |
| `WriteConsoleOutput` / `FillConsoleOutput*` | CUP + text + SGR per run (`WriteInfos`) | **UCS-2 only, 16 colors, DBCS halves fixed up** (`VtIo.cpp:771-834`). Full-screen space fill becomes `CSI H CSI 2J CSI 3J` (`_output.cpp:455-475`) |
| `ScrollConsoleScreenBuffer` | Full-width vertical scroll: `DECSC; SGR; CSI H; CSI n L/M; DECRC`. Otherwise **DECCRA/DECFRA if the terminal's DA1 lists rectangular ops (28)**. Otherwise read back the cells and rewrite them | `getset.cpp:1034-1110`. cmd `cls` shim → clear screen (GH#3126) |
| `SetConsoleActiveScreenBuffer` / closing a secondary buffer | Full repaint of the new buffer, main then alt (`WriteScreenInfo`, `VtIo.cpp:836-882`) | "destroys surrogate pairs and extended (VT) attributes" (#17510) |
| `ShowWindow(GetConsoleWindow())` | `CSI 1t` / `CSI 2t` (`InteractivityFactory.cpp:505-516`) | Focus-loop avoidance, #17829 |

Because the DA1 reply decides between DECCRA and readback, conhost's
**lazily-learned terminal capabilities** matter. They are parsed from the first
DA1 reply on the input pipe (`InputStateMachineEngine.cpp:482-509`). A
terminal that wants good `ScrollConsoleScreenBuffer` behavior (PowerShell's
PSReadLine, `cls`, TUI apps using the Console API) should **answer DA1 with
`;28`**.

### 2.5 The input path

- **Startup handshake.** At startup conhost writes
  `ESC[c ESC[?1004h ESC[?9001h` (`VtIo.cpp:196-206`). That is a DA1 request,
  focus reporting, and win32-input-mode. On shutdown it writes
  `ESC[?1004l ESC[?9001l` (245-265).
  - Since `bfc054685` (#20536, Aug 2026) conhost no longer *waits* for DA1,
    unless cursor inheritance is on, which waits up to 1 s.
- **win32-input-mode format.** Each key event is sent as
  `CSI Vk;Sc;Uc;Kd;Cs;Rc _`: virtual key, scan code, UTF-16 unit, key-down,
  control-key state, repeat count. Each field has a default
  (`InputStateMachineEngine.cpp:1134-1154`;
  spec `doc/specs/#4999 - Improved keyboard handling in Conpty.md:144-260`).
  - It is the only lossless way to deliver Win32 `KEY_EVENT_RECORD`s to
    classic console apps (cmd, PowerShell 5, far, anything using
    `ReadConsoleInput`).
  - The parser's parameter max was raised to 65535 for it (GH#12977,
    `stateMachine.hpp:25`).
- **Decoding without win32-input-mode.** Conhost synthesizes key events from
  legacy VT: arrows, F-keys, SGR mouse, `ESC x` meaning Alt+x, and so on
  (`InputStateMachineEngine.cpp:261-530`). Information is lost: there is no
  key-up, and Ctrl/Alt combos are guessed.
- **VT-input clients** (`ENABLE_VIRTUAL_TERMINAL_INPUT`, e.g. WSL, `ssh.exe`,
  modern TUI apps):
  - CSI sequences the engine doesn't consume are **flushed through raw** to
    the client. It returns `false`, which makes the state machine pass the
    original text on (`6dd9c468e`, #17741; `InputStateMachineEngine.cpp:296-303,
    378-532`).
  - win32-input-mode sequences are *always* consumed and turned into an
    INPUT_RECORD. For a VT-input client that record is then **re-encoded
    by conhost's own `TerminalInput`** (`inputBuffer.cpp:676-730`). The
    terminal's precise key event is therefore re-encoded under conhost's
    rules.
  - OSC on the input stream is always passed through, since it can only be a
    reply (`InputStateMachineEngine.cpp:579-590`).
- **Ambiguities to know about:**
  - **CPR vs F3.** `CSI r;c R` is both a DSR reply and modified F3. Conhost
    treats it as CPR when it asked for one, *or* when it has ever seen a
    win32-input-mode sequence, which implies the terminal sends keys that way
    (`InputStateMachineEngine.cpp:415-431`).
  - **Lone ESC at a read boundary.** It is dispatched as the Esc key
    immediately, *unless* win32-input-mode has been seen
    (`stateMachine.cpp:2033-2066`). The comment notes WSL delivers input in
    16-byte chunks, which split sequences.
  - **Focus events** (`CSI I`/`CSI O`) are consumed by conhost
    (`FocusChanged`) and not forwarded (GH#12799/#12900).
- **Lesson for the terminal side:** speak win32-input-mode whenever conhost
  asks, as WT does. It removes all of these heuristics.

### 2.6 Resize, reflow and the cursor-sync problem

- Resize arrives on the signal pipe → `ConhostInternalGetSet::ResizeWindow`
  (`outputStream.cpp:372-424`) → `SetConsoleScreenBufferInfoEx` → `ResizeScreenBuffer`
  (`screenInfo.cpp:1340-1400`).
- **Conhost reflows its own main buffer** when "wrap text" is on
  (`ResizeWithReflow`). The alt buffer is not reflowed (GH#3493).
- **Conhost emits nothing to the terminal on resize.** The old
  `--resizeQuirk` repaint is gone. The terminal reflows its own buffer and is
  the source of truth for what is shown.
- **In PTY mode the conhost buffer is only as tall as the window.** That is,
  **no scrollback** (`settings.cpp:142-146`; `getset.cpp:881-885` resizes the
  buffer with the window). Text that scrolls off in conhost goes to the
  terminal's scrollback and is unknown to conhost from then on.
  `ReadConsoleOutput` of history can't work.
- **The two reflows drift apart.** Different wrap rules, a wider terminal
  uncovering scrollback, and output racing a resize all cause it. Conhost's
  mitigation (#19535, GH#18725, `screenInfo.cpp:1409-1500`):
  - Every resize, and every **unknown** VT sequence, sets a
    "cursor may be wrong" flag. It is a generation counter in an atomic.
  - The next `GetConsoleScreenBufferInfo[Ex]` (`ApiDispatchers.cpp:597-604`)
    emits `CSI 6n` and **blocks, without the lock, for up to about 500 ms**
    for the CPR reply. The reply moves conhost's cursor
    (`InteractDispatch.cpp:173`).
  - PowerShell calls this API on every line of output, which is why the flag
    approach was chosen over always asking (`outputStream.cpp:31-36`).
  - Since #20510 the flag is cleared even without a reply, so a non-VT host
    doesn't get a 500 ms stall per call.
  - An earlier attempt to emit CPR on every resize was reverted because it
    could inject `CSI 6n` inside a DCS (`0c064905b`).
- **Terminal side (WT).** `Terminal::UserResize` reflows, then positions the
  viewport with heuristics written to match ConPTY's reflow (GH#3490). Main
  buffer reflow is deferred while the alt screen is active (GH#3494;
  `Terminal.cpp:294-479`). Resize is forwarded to the connection **only after
  the local reflow succeeds** (`ControlCore.cpp:1237-1285`).
- **Cooked read (cmd's line editor) during resize** was fixed by delaying its
  `CSI J` until after reflow (`9d0180a55`, #17668).
- **0×0.** `CreatePseudoConsole` rejects 0×0 (`winconpty.cpp:130`), and
  `ResizeWindow` ignores sizes ≤ 0 (`outputStream.cpp:375-378`). Still filter
  minimize-sized resizes yourself (A§2.3).

**Cursor inheritance** (`PSEUDOCONSOLE_INHERIT_CURSOR`):
- Conhost sends `CSI 6n` *before* DA1. It then waits up to 1 s for DA1,
  temporarily releasing the console lock (`VtIo.cpp:191-217`).
- The CPR reply sets conhost's cursor (`InputStateMachineEngine.cpp:417-420`).
- WT uses this for "restart connection" and session restore, so a new shell
  continues below old content instead of conhost starting at row 0
  (`ConptyConnection.cpp:264-273`).

### 2.7 Fidelity problems an app on top of ConPTY still faces

Current OSS ConPTY. Inbox ConPTY before 24H2 is much worse.

| # | Problem | Cause / code | Severity for an SSH-style workload |
|---|---|---|---|
| 1 | Invalid UTF-8 from the child becomes U+FFFD | UTF-16 round trip (§2.4) | Low (but binary-ish output differs) |
| 2 | LF→CRLF unless the child set `DISABLE_NEWLINE_AUTO_RETURN` | `WriteUTF16TranslateCRLF`; may corrupt DCS payloads containing LF | Medium for sixel/DCS-heavy apps |
| 3 | Child cannot turn off focus events or win32-input-mode in the terminal | Injections (§2.4) | Low (terminal hides it) |
| 4 | Console-API apps lose truecolor, 256-color and surrogates, and every attribute change resets SGR | `formatAttributes`, `WriteInfos` | Only for legacy apps |
| 5 | Delayed-wrap CRLF breaks reflow of mixed API/VT output | `_stream.cpp:207-225` | Medium |
| 6 | Conhost buffer ≠ terminal buffer after resize. Apps that read the console (PSReadLine, `GetConsoleScreenBufferInfo`) see stale positions; a CPR round trip papers over it | §2.6 | Medium–high for PowerShell |
| 7 | Focus and visibility VT injected "without checking whether the VT output is currently in a ground state" | #17510 unresolved list | Low, but can corrupt a long DCS |
| 8 | Keys decoded and re-encoded by conhost for VT-input apps; legacy-encoding ambiguities (ESC, F3/CPR) if the terminal doesn't speak win32-input-mode | §2.5 | Medium (terminal choice) |
| 9 | Every byte is parsed twice: once in conhost, once in the terminal, plus extra pipe hops and UTF conversions | design | Throughput / latency |
| 10 | DCS with non-ASCII payload is dropped by conhost's parser, which only affects conhost's buffer. The raw text is still forwarded, but conhost's model diverges | `stateMachine.cpp:333-337` | Low |
| 11 | Conhost needs its own width algorithm to agree with the terminal. Pass the matching `PSEUDOCONSOLE_GLYPH_WIDTH_*` | §4.3 | Medium for emoji/CJK |
| 12 | Classic console apps use `ReadConsoleInput`; no protocol exists for mouse wheel horizontal, pixel mouse, etc. | API | Low |

The #13000 spec's long-term fix is an **in-process ConPTY**: ship the console
server as a library and let the terminal implement `IApiRoutines` directly on
its own buffer. Only "Goal 1" (remove VtEngine) is done at this commit. The
`Server` library and productization are not (**unverified beyond spec status
and the absence of an in-proc path in `TerminalConnection`**).

**For puritty** this all supports S§3.2: route SSH sessions around ConPTY with
an embedded client. ConPTY is now good enough for local shells (PowerShell,
cmd, WSL) provided the terminal:

1. bundles a current `conpty.dll` and `OpenConsole.exe`;
2. speaks win32-input-mode;
3. answers DA1 (with `;28` for DECCRA);
4. answers DSR-CPR promptly;
5. passes the matching glyph-width flag;
6. keeps the output pipe drained, including during close.

### 2.8 ConPTY changes since mid-2024 (what has been fixed)

| Commit | Date | Change |
|---|---|---|
| `450eec48d` #17510 | 2024-08 | VtEngine removed; passthrough plus API→VT translation. "~20x" faster for mixed output in WT; overlapped I/O |
| `7fd9c5c78` #17704 | 2024-08 | OSS API aligned with Win11 24H2; Close no longer waits |
| `a40a4ea09` #17757 | 2024-08 | Inject W32IM/focus re-enable after RIS etc. |
| `6dd9c468e` #17741 | 2024-08 | Unhandled input sequences (e.g. DA1 replies) flushed to the client instead of swallowed |
| `040f26175` #17747 | 2024-08 | DECCRA/DECFRA for ScrollConsoleScreenBuffer, based on DA1 |
| `9d0180a55` #17668 | 2024-08 | Cooked-read reflow under ConPTY |
| `17a55da0f`, `4386bf07f` | 2024-08/10 | Pseudo-HWND focus fixes; avoid focus/iconify loops |
| `32ae00f71` #18681 | 2025-03 | Startup hang with 0-param DA1 replies |
| `733a5e7be` #18588 | 2025-02 | Shutdown when killed during startup |
| `898b9e3ca` #19535 | 2025-11 | Fetch the terminal cursor position after resize (§2.6) |
| `c81c66b40` #19817 | 2026 | Kitty keyboard protocol (WT side; ConPTY explicitly opts out of translating) |
| `0a3fbdefb` #19901 | 2026-02 | Load ConDrv if needed |
| `a47fb5d07` #20510 | 2026-08 | No repeated DSR-CPR stall if the host never answers |
| `bfc054685` #20536 | 2026-08 | Don't wait for DA1 on startup ("you can spawn ConPTY again without handling any queries") |
| `5951f6965` #20774 | 2026-10 | Several ScrollConsoleScreenBuffer fixes; lazy DA1 capabilities |

### 2.9 Default-terminal handoff (briefly)

When Windows Terminal is the default terminal and a user double-clicks
`cmd.exe`, the inbox conhost starts first. The handoff goes like this:

1. Inbox conhost reads `HKCU\Console\%%Startup\DelegationConsole/Terminal`.
2. It activates OpenConsole's `CConsoleHandoff` through COM.
3. OpenConsole creates a signal pipe and reference handle, then
   `CoCreateInstance`s the terminal's `ITerminalHandoff3` and calls
   `EstablishPtyHandoff`. The terminal creates the I/O pipes and returns them;
   v3 made in/out `[out]`.
4. OpenConsole then continues as a headless PTY host
   (`src/host/srvinit.cpp:401-575`, `src/host/proxy/ITerminalHandoff.idl`).
5. WT wraps the handles with `ConptyPackPseudoConsole`
   (`ConptyConnection.cpp:335-383`).

This is a ConPTY feature puritty only needs if it wants to be selectable as
the Windows default terminal. The spec is `doc/specs/#492 - Default Terminal/`.

---

## 3. TerminalConnection: the backend abstraction

### 3.1 Interface

`ITerminalConnection.idl:6-32`:

```
enum ConnectionState { NotConnected, Connecting, Connected, Closing, Closed, Failed }
delegate TerminalOutputHandler(Char[] output);         // UTF-16 text
interface ITerminalConnection {
    Initialize(ValueSet settings);  Start();  WriteInput(Char[] data);
    Resize(UInt32 rows, UInt32 columns);  Close();
    event TerminalOutputHandler TerminalOutput;
    event TypedEventHandler<ITerminalConnection, Object> StateChanged;   // no payload
    Guid SessionId { get; };  ConnectionState State { get; };
}
```

- **States only move forward.** `BaseTerminalConnection::_transitionToState`
  refuses backwards transitions (`BaseTerminalConnection.h:38-55`). Spec #2563:
  "States MUST NOT be transitioned in reverse".
- **Status messages travel in the stream.** Each backend writes its own text
  into the output, e.g. `[process exited with code N]` and
  `[error … when launching …]` (`ConptyConnection.cpp:479-533`).
- **Extras need a downcast.** Clear-buffer, show/hide, reparent, commandline
  and exit code are only on `ConptyConnection`. `ControlCore` reaches them with
  `try_as<ConptyConnection>()` (`ControlCore.cpp:428-432, 2398-2404, 2522-2530`).
  There are no capability interfaces.
- **Backends are chosen by profile GUID** in
  `TerminalPage::_CreateConnectionFromSettings` (`TerminalPage.cpp:1554-1662`).
  There is no plugin mechanism.

### 3.2 Implementations

| Class | Transport | Notes |
|---|---|---|
| `ConptyConnection` | ConPTY | §2. Output thread: 128 KiB overlapped reads, pipelined (queue next read, then raise the previous chunk), `til::u8u16` with carried state (`:737-842`). Input: UTF-16→UTF-8, one overlapped write in flight, FIFO via ticket lock (`:553-600`). Exit detected only by pipe EOF; exit code 0 → `Closed`, else `Failed` (`:537-551`). `Close()` loops `CancelIoEx` + wait until the reader thread is gone, so **no output callback fires after Close returns** (GH#13880, `:667-703`). Env: `WT_SESSION`, `WT_PROFILE_ID`, appended to `WSLENV` |
| `AzureConnection` | HTTPS + WinHTTP websocket | Cloud Shell. OAuth2 device-code flow, rendered as a text UI *inside the terminal*, with local echo and line editing while not connected (`AzureConnection.cpp:160-245`). Tokens in PasswordVault. Resize is an out-of-band REST POST (`:250-273`). Only built with a client ID |
| `EchoConnection` | none | Echoes input with `^X` for controls; test stub |
| `DebugTapConnection` (TerminalApp) | decorator | Tees a real connection into a second pane that shows control codes visibly. Enabled with both Alt keys + new tab when `debugFeatures` is on (`DebugTapConnection.cpp`) |

### 3.3 Binding to the control

- `ControlCore::Connection(conn)` (`ControlCore.cpp:320-362`) does the
  following:
  1. Closes the old connection.
  2. Subscribes `StateChanged`.
  3. Sends the current size.
  4. Subscribes `TerminalOutput` → `_connectionOutputHandler`.

  It does **not** call `Start`; `TermControl` does that after optional buffer
  restore (`TermControl.cpp:1404, 1435-1468`).
- **`_connectionOutputHandler` runs on the connection's thread**
  (`ControlCore.cpp:2303-2329`):
  1. Takes `LockForWriting()` and calls `Terminal::Write`, i.e.
     `StateMachine::ProcessString`.
  2. Releases the lock.
  3. Writes any queued VT replies (DA/DSR/…) back to the connection.

  Replies are buffered during parsing via `SetWriteInputCallback` so the
  write never happens while the lock is held. `SendInput` asserts that no
  terminal lock is held, because `WriteFile` may block (`:512-531`). This is
  the S§3.3 rule ("query replies must not depend on the UI thread"), done
  right.
- **Restart.** A new connection object replaces the old one under the same
  control and buffer:
  - `HardResetWithoutErase` clears modes but keeps the text.
  - The new connection uses `inheritCursor=true`
    (`TerminalPage.cpp:4005-4024, 1664-1704`).
- **Session restore.** On exit, each pane's main buffer is serialized to
  `buffer_{sessionGuid}.txt` (UTF-16 + SGR) by `TextBuffer::SerializeTo`. On
  start it is replayed through the VT parser, a `[Restored …]` banner is
  added, and then `Start()` is called with cursor inheritance
  (`WindowEmperor.cpp:1361-1470`, `ControlCore.cpp:1900-2006`). Only the
  screen comes back, not the process.
- **`closeOnExit`** (`Never/Graceful/Always/Automatic`) is decided in the app
  (`TerminalPaneContent.cpp:195-247`). It ignores failures that happen before
  `Connected`, so a bad `startingDirectory` doesn't flash and close.

### 3.4 SSH

- **No SSH connection type exists.** `SshHostGenerator`
  (`src/cascadia/TerminalSettingsModel/SshHostGenerator.cpp`) generates the
  SSH profiles:
  - It finds `ssh.exe` in `System32\OpenSSH`, then `Program Files[ (x86)]\OpenSSH`
    (17-24, 47-63).
  - It regex-parses `%ProgramData%\ssh\ssh_config` and `~/.ssh/config`, emitting
    a profile `SSH - <host>` with commandline `"ssh.exe" <host>` for each `Host`
    that is followed by a `HostName` (86-167).
  - `Include` is not followed and wildcard hosts are skipped.
- **So every WT SSH session runs ssh.exe inside ConPTY.** ssh.exe itself
  uses VT input mode and Console APIs, so it gets all of §2.7.
- **tmux appears only in docs** (pane specs). There is no control-mode support.

### 3.5 Mapping to puritty's backend interface

WT's interface is very close to the one S§3.2 needs. Differences to adopt or
avoid:

- **Bytes vs UTF-16.** WT decodes in the backend and hands UTF-16 to the
  parser. puritty should hand **bytes** to a UTF-8-native parser (G§3).
  The backend must not decode, especially for tmux `%output`, where
  unescaping comes first.
- **Capabilities.** Replace downcasts with optional capability methods: clear,
  set-window-owner, show/hide (ConPTY), reconnect (SSH), pane-ID (tmux).
- **Resize.** Units differ per backend: ConPTY takes cells, SSH
  `window-change` takes cells *and* pixels, tmux works at window level. Azure
  shows resize can be an asynchronous RPC with no acknowledgment. Design it
  as fire-and-forget with "latest size wins".
- **Swappability.** Keep WT's "swap connection under a persistent screen"
  property. It gives restart, SSH reconnect and tmux reattach for free.
- **Status text.** In-band status text, like WT's exit banner and Azure's
  login UI, is pragmatic. For SSH, host-key prompts and passwords are better
  done as UI overlays than as fake terminal lines. Use in-band text only for
  simple banners.
- **Close.** `Close()` must guarantee no callbacks after return
  (GH#13880). Do the same for SSH channels and tmux panes.

---

## 4. TerminalCore: parser, adapter, Unicode, buffer

### 4.1 Parser (`src/terminal/parser`)

- **States.** A vt100.net-style state machine (`stateMachine.hpp:10,
  170-192`) that adds colon sub-parameters, an `OscTermination` state for
  `ESC \`, VT52 parameters and SS3 (input engine only).
- **Input is UTF-16** (`ProcessString(wstring_view)`). UTF-8 is decoded by the
  connection (§3.2).
- **Limits** (`stateMachine.hpp:22-38`):
  - 32 parameters, each clamped to 65535.
  - 6 sub-parameters per parameter.
  - Sub-parameters are accepted only for SGR and DECCARA/DECRARA
    (`OutputStateMachineEngine.cpp:1133-1146`).
- **Fast path.** In Ground, `FindActionableControlCharacter` (SSE2/NEON,
  `src/types/utils.cpp:1141+`) finds the next C0/DEL/C1, and the whole
  printable run goes to `PrintString` in one call
  (`stateMachine.cpp:1977-2026`).
- **C1** is honored only when `AcceptC1` is set: DECAC1/S8C1T for output,
  always for input. The reason given is that codepage-mapped stray bytes
  would otherwise trigger controls (`stateMachine.cpp:1856-1870`).
  Unhandled C0 codes are dropped, not stored (GH#1825).
- **DCS** uses a returned `StringHandler = function<bool(wchar_t)>`
  (`IStateMachineEngine.hpp:23`):
  - It is fed one character at a time.
  - Returning `false` switches to DcsIgnore.
  - ESC/CAN/SUB deliver `ESC` as end-of-data (`stateMachine.cpp:648-661, 727-749`).
  - This streaming design is good (G§3 does the same).
  - **Pitfall:** only 0x20–0x7E and C0 reach the handler
    (`_isDcsPassThroughValid`, `stateMachine.cpp:333-337`). **Non-ASCII DCS
    payloads are dropped.** tmux control mode wraps UTF-8 output inside a DCS,
    so don't copy this.
- **APC/PM/SOS** are parsed and discarded (`:1823-1827`). There is no kitty
  graphics protocol.
- **OSC** is buffered with **no length limit** apart from a 2 MiB cap on OSC 8
  URIs, and dispatched at the terminator (`OutputStateMachineEngine.cpp:763-925`,
  `.hpp:23`). This is a memory-exhaustion risk; cap it in puritty.
- **REP** repeats a single UTF-16 unit (`OutputStateMachineEngine.cpp:152-170`),
  which is wrong for astral characters and clusters.

### 4.2 Adapter: supported sequences (`src/terminal/adapter`)

Broad DEC coverage, largely the work of j4james's VT conformance effort:

- **Editing / cursor:** full CUx/CNL/CPL/CHA/HPA/VPA/HPR/VPR, ICH/DCH/IL/DL,
  DECIC/DECDC, ECH, SU/SD, DECBI/DECFI, tab controls, DECSTBM **and DECSLRM**
  (mode 69), DECOM, IRM, LNM.
- **Rectangular:** DECCARA, DECRARA, DECCRA, DECFRA, DECERA, DECSERA,
  DECSACE. DECRQCRA sits behind a feature flag.
- **SGR:** colon sub-params; underline styles 1–5; underline color;
  XTPUSHSGR/XTPOPSGR; DECSCA; DECDWL/DECDHL.
- **Reports:**
  - DA1 `?61;4;6;7;14;21;22;23;24;28;32;42[;52]c` (`adaptDispatch.cpp:1435-1462`),
    DA2 `>0;10;1c`, DA3.
  - DECRQSS (SGR, DECSTBM, DECSLRM, DECSCUSR, DECSCA, DECSACE, DECAC),
    DECRQM, DECRQTSR/DECRSTS, DECRQPSR/DECRSPS, DECRQUPSS.
  - **No XTGETTCAP, no XTVERSION** (searched).
- **Modes** (`DispatchTypes.hpp:518-550`): 1,2,3,5,6,7,8,12,25,40,64,66,67,69,80
  (sixel display), 117, 1000/1002/1003/1004/1005/1006/1007, **1049 only** (no
  47/1047/1048), 2004, **2026** synchronized output, 2027 (reports
  permanently set or reset per the measurement mode), 9001. **No 1015/1016.**
- **Sixel:** `SixelParser`, up to 256 colors, virtual cell 10×20 (VT340-like),
  so images are scaled to font cells.
  - Stored as per-row `ImageSlice` RGBA buffers that move with text through
    scroll and reflow (`src/buffer/out/ImageSlice.hpp`, `textBuffer.cpp:2848`).
  - Flushes at least every 500 ms while streaming.
- **Other DEC features:** **DRCS soft fonts** (DECDLD, mapped to PUA
  U+EF20–EF7F), **6 pages** (NP/PP/PPA…, `PageManager`, pages copied in and out
  of the visible viewport), **macros** (DECDMAC/DECINVM, 256 KiB), **DECPS**
  (MIDI notes), VT52 mode, charsets (SCS/LS/SS/DOCS).
- **OSC:**
  - Titles 0/1/2/21; palette 4/104; dynamic colors 10/11/12/17 and
    resets.
  - **7** and **9;9** (cwd); **8** hyperlinks; **9;4** progress;
    **52 set only** (queries ignored; needs focus and permission); **133**
    A/B/C/D;exit; 633 completions; 1337 SetMark; 777 notify.
- **Kitty keyboard protocol:** `CSI =/?/>/< u` with separate 8-deep stacks
  for the main and alt screens (`terminalInput.hpp:52-85, 186-193`).

### 4.3 Unicode width and graphemes

- **One process-wide `CodepointWidthDetector`** (`CodepointWidthDetector.cpp:770-775`).
  - WT sets it once from settings in a function-local `static` in the first
    `ControlCore` (`ControlCore.cpp:75-95`), so a mode change needs a restart
    (**inference**).
  - ConPTY gets the same mode by flag (§2.1, `VtIo.cpp:31-56`).
- **Modes** (`TextMeasurementMode`): `Graphemes` (default, close to UAX #29),
  `Wcswidth` (zero-width attaches to previous), `Console` (one code point per
  cell, legacy).
- **Tables:**
  - A 4-stage trie from **Unicode 16.0, 9224 bytes**, generated by
    `src/tools/GraphemeTableGen`. Each entry packs the break class and width;
    width 3 means "ambiguous" (`:45-47, 666-687`).
  - Overrides force box drawing/blocks U+2500–259F narrow
    (`unicode_width_overrides.xml`).
  - Joining uses a **pairwise rule table**. The authors say it "trades off
    correctness for simplicity" and only differs from UAX #29 on degenerate
    input (`:33-43`).
- **Width rules:**
  - VS16 makes a cluster wide; widths are summed and clamped to 2
    (`:850-888`).
  - Zero-width clusters still take ≥ 1 column (`Row.cpp:696`).
  - Ambiguous is narrow by default (GH#2066). Optional wide.
- **Streaming.** `GraphemeState` lets a cluster continue across separate
  writes. A later VS16 or combining mark re-measures the previous cell and
  rewrites it in place (`Row.cpp:676-718`). Puritty needs the same for
  chunked PTY reads.

### 4.4 Buffer: TextBuffer, ROW, attributes

- **Arena and ring:**
  - **One `VirtualAlloc(MEM_RESERVE)`** per buffer of
    `(height+1) * rowStride`. Rows are **committed on demand** plus 128 rows of
    read-ahead (`textBuffer.cpp:92-140`).
  - Physical row 0 is a scratchpad.
  - Logical rows form a ring: `_firstRow` plus modulo. Full-screen scroll is
    O(1) (`IncrementCircularBuffer`, `:728-746`). Region scrolls copy rows
    (`:806-881`).
- **ROW** (`Row.hpp:268-317`):
  - `_chars` (wchar_t; capacity = columns, spilling to a heap block when
    clusters need more).
  - `_charOffsets` (u16 per column + 1). Bit 15 marks a trailing (wide)
    half, so leading/trailing is **derived**, not stored.
  - `_attr` as `til::small_rle<TextAttribute, u16, 2>` (attribute runs, 2
    inline).
  - Wrap-forced flag, line rendition, optional `ScrollbarData` (prompt marks)
    and an `ImageSlice` pointer.
  - Arrays are 16-byte aligned for SIMD reset: "wastes up to 5.8% memory but
    increases overall scrolling performance by around 40%".
- **TextAttribute** is 18 bytes, compared with `memcmp`:
  - u16 flags (incl. 3-bit underline style)
  - u16 hyperlink ID
  - 3 × 4-byte `TextColor` (fg/bg/underline; Default/16/256/RGB)
  - u16 `MarkKind` (prompt/command/output). Shell-integration regions are a
    cell attribute.
- **Hyperlinks:** u16 IDs into a map. When a row containing links scrolls
  out, **the whole buffer is scanned** for remaining references
  (`_PruneHyperlinks`, `:1427-1470`). This is a performance hazard.
- **Limits:** `_height` is u16 and WT clamps viewport+history to **32 767
  rows** (`Terminal.cpp:49-50, 80-84`). Default history is 9001. Infinite
  scrollback is a TODO.
- **Reflow** (`TextBuffer::Reflow`, `textBuffer.cpp:2718-2957`):
  - It builds a new buffer, walking old rows, trimming trailing blanks,
    joining wrap-forced rows and re-wrapping grapheme-aware.
  - It carries attributes, images and marks, and tracks the cursor and
    viewport.
  - Double-width lines are truncated. A "BODGY" clamp guards against
    infinite loops.
  - WT's alt screen is a separate, viewport-sized TextBuffer with no
    scrollback, created on each 1049h (`TerminalApi.cpp:242-340`), and is
    resized without reflow.
- **Search:** ICU regex over a `UText` adapter onto the buffer
  (`textBuffer.cpp:3067-3120`).

### 4.5 Terminal class

- **Roles.** `Terminal : ITerminalApi, ITerminalInput, IRenderData`
  (`Terminal.hpp:55-57`). It is the adapter's host *and* the renderer's
  data source.
- **Locking.**
  - **`LockForReading` and `LockForWriting` take the same exclusive ticket
    lock** (`Terminal.cpp:990-1006`). It is fair FIFO and documented as fine
    only for about 2 threads.
  - The UI thread takes it for every key event, selection and resize.
  - `SuspendLock()` releases a recursive hold, e.g. while DECPS plays a note.
- **Line feed at the bottom.** First the viewport moves down the buffer. Once
  the buffer is full, it rotates the ring and calls
  `NotifyBufferRotation`, which shifts the selection
  (`adaptDispatch.cpp:2419-2500`, `TerminalApi.cpp:391-413`).

---

## 5. Rendering

### 5.1 Shared Renderer (`src/renderer/base`)

- **Engines.** One `Renderer` with one **render thread** ("Rendering Output
  Thread", `renderer.cpp:56-96`) drives a list of `IRenderEngine`s: AtlasEngine
  plus UiaEngine in WT; GDI or Atlas plus UIA in conhost.
- **Loop** (`:139-162`): `WaitUntilCanRender` (engine pacing) →
  wait on an atomic `_redraw` flag via WaitOnAddress, with a timeout for cursor
  and SGR blink timers → `PaintFrame`.
- **Frame:**
  1. Take the console lock.
  2. Clear `_redraw` *after* acquiring it.
  3. Scroll the viewport delta into `InvalidateScroll`.
  4. Handle the cursor.
  5. For each engine: `StartPaint` → `PaintBackground` → buffer lines as
     clusters → selection → cursor → `EndPaint`.
  6. **Unlock, then `Present()`** (`:402-467`).
- **Invalidation.** Producers call `TriggerRedraw/Scroll/Selection/…` while
  holding the lock. Each call forwards to every engine's `Invalidate*` and then
  `NotifyPaintFrame()`. There is no frame timer; vsync pacing coalesces
  output.
- **Failure handling.** 5 retries with 100→1600 ms backoff, then
  `_pfnRendererEnteredErrorState`. WT then **falls back once to D2D + WARP**
  (`ControlCore.cpp:168-181`).
- **Synchronized output (2026).**
  - The render thread waits up to **100 ms**, releasing the lock while it
    waits (`renderer.cpp:542-610`).
  - When the mode is reset, the writer does `Unlock(); Lock();` so the renderer
    gets a turn. The comment calls this "an awful, ugly hack" against
    starvation.
- **README self-critique.** The atlas README says that translating the buffer
  into GDI-style primitives (brush changes, `PaintBufferLine` per run) is
  "pretty wasteful… incredibly bug prone" and that AtlasEngine should read
  the TextBuffer directly. Puritty's headless-core/renderer split (S§3.1)
  should pass the renderer a row snapshot, not a stream of draw calls.

### 5.2 AtlasEngine (`src/renderer/atlas`)

**Two phases.**
- Under the lock, `StartPaint`/`PaintBufferLine` run DirectWrite **font
  fallback and shaping** into persistent per-row `ShapedRow`s.
- Outside the lock, `Present` does the GPU work (`AtlasEngine.cpp:16-20`,
  `AtlasEngine.r.cpp:10-31`).
- Consequence: shaping cost extends the lock hold. Ghostty and Alacritty
  shape on the render side from a snapshot (G§5). Puritty should snapshot
  under the lock and shape outside it.

**Backend choice** (`AtlasEngine.r.cpp:102-302`):
- **Settings:** `graphicsAPI` = automatic | direct2d | direct3d11, plus
  `rendering.software` (WARP) and `disablePartialInvalidation`.
- **Adapter:** the default one; no monitor matching.
- **Device flags:** `D3D11_CREATE_DEVICE_SINGLETHREADED |
  PREVENT_INTERNAL_THREADING_OPTIMIZATIONS` (the Nvidia driver otherwise
  spawns a thread per CPU) `| BGRA_SUPPORT`. Feature levels 11_1…9_1.
- **Automatic rule:** WARP → D2D ("definitely better tested"); FL < 10_0 →
  D2D; FL < 11_0 without compute-shader support → D2D; else D3D11.
- The README describes D2D as "for low latency remote desktop and
  older/no GPUs". **No RDP detection exists** (no `SM_REMOTESESSION` in `src/`;
  **unverified** beyond grep). Behavior over RDP depends only on the adapter
  reported.

**D3D11 backend** (`BackendD3D.*`):
- **Instancing:**
  - One unit quad, instanced. `QuadInstance` is about 20 bytes: shading type,
    rendition scale, i16 position, u16 size, u16 texcoord, u32 color
    (`BackendD3D.h:87-100`).
  - One `DrawIndexedInstanced` per batch into a dynamic `WRITE_DISCARD`
    buffer.
  - A comment benchmarks compute shaders, geometry shaders and vertex pulling;
    instancing won by about 50% on Nvidia (`.cpp:1016-1033`).
- **Shading types:** background (sampled from a cells-sized RGBA texture),
  grayscale text, ClearType text, builtin glyph, passthrough (color
  emoji/sixel), dotted/dashed/curly/solid lines, cursor, filled rect
  (`shader_ps.hlsl:36-218`).
- **ClearType in the shader.** **Dual-source blending**
  (`ONE, INV_SRC1_COLOR`) lets per-channel ClearType weights and premultiplied
  source-over share one blend state (`.cpp:139-177`). DirectWrite's gamma and
  contrast correction is reimplemented in HLSL. D2D is given linear
  params so it isn't applied twice (`dwrite_helpers.cpp:15-80`).
- **When ClearType is disabled.** It is forced to grayscale when the
  background is transparent or a custom shader is active
  (`AtlasEngine.api.cpp:510-527`).
- **Background upload.** The background color plane is uploaded only when its
  generation changes; this "halves (!) the GPU load" (`.cpp:1072-1106`).

**Glyph atlas:**
- **Texture.** One `B8G8R8A8` texture that is both SRV and RTV, with a D2D
  render target on it. D2D's own glyph caches are turned off
  (`SetMaximumTextureMemory(0)`).
- **Packing:** `stb_rect_pack`.
- **Cache key:**
  - The outer key is the **`IDWriteFontFace` pointer value**. This relies on
    `MapCharacters` returning the same instance while it is referenced
    ("BODGY", `BackendD3D.h:144-181`).
  - The inner key is the glyph index, with one table per line rendition.
  - Builtin glyphs are keyed by code point. Sixel slices are keyed by image
    revision.
- **When full:** flush the queued quads, **clear everything** and maybe grow
  the texture, then retry. A second failure throws. **No LRU**
  (`_drawGlyphAtlasAllocate`, `.cpp:1706-1721`).
- **Size:** about `min(2×target area, max(95 cells, 2×current))`,
  power-of-two dimensions, max D3D10 dimension (`:752-825`).
- **Rasterization:** D2D `DrawGlyphRun` per glyph. A manual
  `IDWriteGlyphRunAnalysis` path is kept under `#if 0`; D2D was "roughly 2x
  faster" (`:1343-1409`).
- **Color glyphs:** `TranslateColorGlyphRun` (COLR/SVG/PNG/…), drawn layer by
  layer (`Backend.cpp:31-51`). **Inference:** foreground-colored layers are
  baked white in the atlas.
- **Ligatures across color changes:** `overlapSplit` cuts wide glyph quads
  at cell boundaries where the foreground color changes (`:1236-1325`).

**DirectWrite** (`AtlasEngine.cpp:820-1185`, `AtlasEngine.api.cpp:616-876`):
- **Font list and fallback:**
  - The font list is CSS-like. Extra fonts and the system fallback are
    combined with `IDWriteFontFallbackBuilder`.
  - A "nearby fonts" retry works around packaged-font cache failures
    (GH#9375).
- **Simple-text fast path:** `GetTextComplexity`, then advances forced to
  cell widths.
- **Complex path:** `AnalyzeScript` → `GetGlyphs` →
  `GetGlyphPlacements`. Cluster advances are **snapped to the cell grid**,
  with the error added to the last glyph of the cluster.
- **No bidi:** `isRightToLeft = 0` is hard-coded, and directional isolates are
  replaced by ZWSP.
- `MapCharacters` is "awfully slow", so runs that use the same face are
  merged.
- **Cell metrics:**
  - Width is the advance of `'0'`; height is ascent+descent+lineGap.
    Both can be overridden with CSS-like lengths.
  - Baseline centers extra leading.
  - `thinLineWidth = max(1, round(max(w/16, h/32)))`
    (`AtlasEngine.api.cpp:734-874`).

**Builtin glyphs** (`BuiltinGlyphs.cpp`):
- **Coverage:** U+2500–259F, Powerline E0B0–E0BF, legacy computing
  1FB00–1FB94.
- **Encoding:** each glyph is up to four packed 32-bit instructions (shape +
  5-bit fractional coordinates).
- **Drawing:** drawn with D2D geometry clipped to the cell. Light line =
  `max(1, round(cellW/6))`.
- **Shades:** in D3D, shade characters are generated **per device pixel in the
  shader**, so the checkerboard is exact. D2D approximates them with alpha.
- Soft-font (DRCS) bitmaps are upscaled into the atlas.

**Damage and present:**
- **Under the lock:**
  - `Invalidate` only widens a **row range**; x is ignored.
  - `InvalidateScroll` accumulates a scroll offset; `StartPaint` then
    **rotates the `ShapedRow*` array** instead of re-shaping
    (`AtlasEngine.cpp:162-228`).
  - Only invalidated rows are cleared and re-shaped.
- **GPU side:** **draws every row every frame** plus a full-screen background
  quad (`BackendD3D.cpp:1080-1083, 1119`). The dirty rect is the union of old
  and new pixel extents of re-shaped rows plus the cursor.
- **Swap chain:**
  - `FLIP_SEQUENTIAL` (DWM asked for it so Panel Self Refresh can use dirty
    rects), 3 buffers, `FRAME_LATENCY_WAITABLE_OBJECT`, `SetMaximumFrameLatency(1)`.
  - Alpha `IGNORE` when opaque, which allows independent flip.
  - `FLIP_DISCARD` when partial invalidation is disabled
    (`AtlasEngine.r.cpp:327-386`).
- **Present** (`:478-539`):
  - **Empty dirty rect → no Present, only `Flush()`.**
  - Otherwise `Present1(1, 0, {1 dirty rect, scroll rect + offset})`.
  - Full present on settings change, full-viewport scroll, custom shader, or
    when disabled.
  - If Present1 with rects fails, it retries with plain `Present`
    (`Feature_AtlasEnginePresentFallback`, "we don't feel super confident in
    our usage of the Present1 API").
- **Pacing:** wait on the latency object **only after a Present happened**,
  because it is auto-reset. Otherwise sleep 8 ms (`:448-473`).
- **Targets:** WT renders into a DirectComposition surface handle
  (`CreateSwapChainForCompositionSurfaceHandle`) handed to XAML's
  `SwapChainPanel` (`ISwapChainPanelNative2::SetSwapChainHandle`); XAML's DPI
  scale is undone with `SetMatrixTransform`. Conhost and the WPF control use
  `CreateSwapChainForHwnd`.
- **Device lost:** `DXGI_ERROR_DEVICE_REMOVED/RESET` and `D2DERR_RECREATE_TARGET`
  → drop the device, `E_PENDING`, redraw all and recreate on the next frame
  (`AtlasEngine.r.cpp:57-65`).

**Custom shaders:**
- **Compilation:** `experimental.pixelShaderPath` and the built-in retro
  effect are compiled at runtime with `D3DCompileFromFile` and run as a
  fullscreen pass over an offscreen texture.
- **Continuous redraw:** if the shader uses the `time` cbuffer field (found by
  `D3DReflect`), the engine sets `RequiresContinuousRedraw` and redraws at
  display rate. Any custom shader forces full-frame present and grayscale AA
  (`BackendD3D.cpp:366-557, 2407-2409`).

**D2D backend** (`BackendD2D.*`):
- Redraws everything each frame: a stretched nearest-neighbor background
  bitmap, then one `DrawGlyphRun` per color run, with D2D's glyph cache.
- Builtin glyphs are drawn through a cached sprite batch.
- It still uses the same swap chain and Present1 path.

### 5.3 GDI and other engines

- **GdiEngine** (`src/renderer/gdi`) is still **conhost's default** window
  renderer. AtlasEngine is used only if the registry `UseDx` is set
  (`src/interactivity/win32/window.cpp:197-214`).
  - It works with a memory DC and BitBlt, `ScrollWindowEx`/`ScrollDC` for
    scrolling, and `PolyTextOut`.
  - It forces logical order for RTL (GH#12294).
  - WT never uses it.
- **UiaEngine** is an "engine" attached to the same Renderer. It turns
  invalidations into UI Automation events and sends new text in 1000-char
  chunks. Its `WaitUntilCanRender` returns immediately so it doesn't add
  throttle.
- **WddmConEngine** is for the OneCore full-screen console. It is irrelevant
  here.

### 5.4 Relevance to puritty's Windows renderer

- **Mostly yes:** D3D11 + DirectWrite, instanced quads, a single atlas, dual-source
  ClearType and shader-side gamma. This is the strongest available reference
  for a native Windows backend, and it validates S§10's "D3D11 is the native,
  most reliable path".
- **Worth copying:** the WARP/D2D fallback after repeated failures; deferring
  the frame-latency wait until after a present; skipping Present on an empty
  dirty rect; per-pixel shade generation for block elements.
- **Improve on:**
  - Shape outside the lock.
  - Use an LRU or generation-based atlas eviction instead of clear-all, which
    causes frame spikes with CJK or emoji-heavy output.
  - Fill dirty rects with real partial redraws, which matters over RDP: when
    the D3D11 path runs on a remote session the whole frame is still rendered
    and only the present is partial (**inference**; RDP's own encoder likely
    diffs the frame).
  - Detect `SM_REMOTESESSION` and prefer a GDI-like or D2D path in RDP
    sessions, the Windows analog of S§6's remote-X11 backend.

---

## 6. Threading and locking (summary)

| Thread | Work | Locks |
|---|---|---|
| UI thread (one per process, all windows) | XAML, input, settings, pane layout | Takes the terminal lock for key events, selection, resize |
| Connection reader (one per pane) | ReadFile → UTF-8→16 → parse → reply writes | Terminal lock per chunk (≤128 KiB) |
| Render thread (one per pane) | Snapshot + shape under lock; GPU + Present outside | Terminal lock per frame |
| Threadpool timers | `til::throttled_func`: scrollbar (8 ms), output-idle (100 ms debounce, regex/URL detection off the UI thread, GH#12607), focus debounce (25 ms) | Some take the lock |
| conhost (ConPTY) | VtInputThread, signal thread, API dispatcher threads | One console ticket lock |

- **Starvation avoidance** comes from the **fair ticket lock** (FIFO tickets,
  WaitOnAddress; `src/inc/til/ticket_lock.h`). This is the same idea as
  Alacritty's `FairMutex` (A§1.3). The 2026 lock-yield hack covers the
  synchronized-output case.
- **Lock hold time.** There is no output throttling on the parse side. A
  128 KiB chunk is parsed under one lock hold, and the renderer waits for its
  ticket. Ghostty bounds this differently (G§2).
- **Pane count.** One reader thread plus one render thread per pane means many
  threads with many panes. Puritty's tmux mode (many panes over one
  connection) argues for a different split: one reader per *connection* and a
  shared render thread per window (S§4).

---

## 7. Window, input, process model

- **Process model:**
  - `WindowEmperor` owns a hidden top-level window, not `HWND_MESSAGE`,
    because that kind doesn't get `WM_QUERYENDSESSION`. It also owns a
    **single `GetMessageW` loop for all windows** and global hotkeys (quake
    mode).
  - Single instance: a named mutex. A second instance forwards
    argv/env/cwd by `WM_COPYDATA` and exits. Mutex and window-class names are
    salted with elevation, exe-path hash and SID hash, so elevated and normal
    instances are separate processes (`WindowEmperor.cpp:149-197, 482-535`).
  - The Monarch/Peasant spec `doc/specs/#5000` is historical (`8bbf00e05`).
  - Tab tear-out serializes content to actions. `ContentManager` keeps
    `ControlCore`s by GUID so a core can move between windows without
    restarting its connection.
- **Panes:**
  - A **binary split tree**: `Pane{_firstChild, _secondChild, _splitState,
    _desiredSplitPosition, _content}`, with a XAML Grid per node (`Pane.h:242-252`).
  - Pane content is pluggable (`IPaneContent`: terminal, settings, markdown,
    …).
  - Resizing is keyboard-only in 5% steps; no draggable splitter was found.
  - `WM_SIZING` snaps the window so **every** pane fits whole cells
    (`Pane::CalcSnappedDimension`, `IslandWindow.cpp:246-300`).
  - Puritty's tmux layouts are n-ary trees (`%layout-change`). WT's binary
    tree would need an n-ary generalization.
- **XAML Islands cost.** Many workarounds are needed:
  - Keys XAML swallows (F7, Alt-up, Alt+Space) are intercepted in the
    message loop (GH#638/#6421/#7125).
  - A child "drag bar" window takes NC hit-testing back from the island,
    with fake `HTMAXBUTTON` for Snap Layouts (GH#9443).
  - The top pixel row is unclickable when maximized (GH#7422).
  - Alt+Numpad is re-implemented by hand.
  - `TerminateProcess` on exit avoids XAML teardown crashes (GH#15410).

  Puritty has no XAML, and this list is a good argument for staying with
  plain Win32 plus your own title bar or the native one.
- **DPI:** a PerMonitorV2 manifest. `WM_DPICHANGED` just applies the suggested
  rect. The control re-rasterizes on CompositionScale changes, whose event
  ordering is documented at `TermControl.cpp:2375-2411`.
- **Keyboard** (`src/terminal/input/terminalInput.cpp`, `TermControl.cpp:1531-1873`):
  - **Key and char events are split.** XAML KeyDown is refused by
    `Terminal::SendKeyEvent` if `ToUnicodeEx` (flags `0b101`: no state change)
    says it produces a character. That key then arrives as `CharacterReceived`,
    with the stashed vkey/scancode re-attached (`Terminal.cpp:626-735, 900-958`).
  - **Dead keys** are flushed by looping `ToUnicodeEx` when a keybinding eats
    the key.
  - **AltGr heuristics:** Ctrl+Alt + graphical code point means AltGr. A fake
    LCtrl is distinguished by a >50 ms gap. The `altGrAliasing` setting.
  - **Encoders:** win32-input-mode (unless kitty flags are set), kitty (all 5
    flags, AltGr treated as a layer), legacy. No modifyOtherKeys.
  - The HKL is taken from the foreground window thread. A test hook overrides
    it.
- **Mouse:** X10/normal, 1005, 1006; tracking 1000/1002/1003; Shift bypasses
  app mouse mode. No SGR-pixels.
- **IME:** a custom TSF client (`src/tsf/Implementation.cpp`):
  - It creates its own thread manager and context, and steals focus from
    WinUI's input site.
  - It activates with `TF_TMAE_CONSOLE` so Korean IMEs don't emit interim
    characters a terminal can't take back.
  - `GetStatus` returns `TS_SS_TRANSITORY`, which enables CUAS and gives up
    reconversion. The comment says this is "the primary reason why we cannot
    use the WinRT CoreTextServices APIs".
  - Finalized text is sent to the PTY.
  - The composition preview and its attributes are written into the render
    data and **drawn inline by the Renderer** into a scratch row at the
    cursor (`renderer.cpp:1160-1230, 1683-1760`).
  - Async edit sessions are flushed synchronously on key-down so Enter can't
    overtake the committed text (GH#20244).
  - The candidate window position is computed from cell metrics.
  - This is the best Win32 IME reference in the three codebases studied.
- **Accessibility:** a UIA text provider shared with conhost
  (`src/types/UiaTextRangeBase`). New output is announced through the UiaEngine,
  with typed-character echo suppressed.

---

## 8. Testing

- **Framework:** TAEF (`doc/TAEF.md`), with test lists in `src/testlist`.
- **Unit tests:**
  - Parser: `ut_parser`, about 135 methods, including OutputEngineTest and
    InputEngineTest.
  - Adapter: `ut_adapter`, about 80 methods against a `TestGetSet :
    ITerminalApi` mock, plus input, mouse and table-driven kitty tests.
  - Buffer, til, types and host have their own.
- **Headless control tests:** `UnitTests_TerminalCore` (Terminal without UI)
  and `UnitTests_Control` (`ControlCore` + `ControlInteractivity` with
  `MockConnection`). These work because Core and Interactivity are
  UI-framework-free, which is the S§3.1 headless-core argument, demonstrated.
- **Feature tests against real conhost:** `src/host/ft_host` (Console API),
  `ft_uia`, `src/winconpty/ft_pty`.
- **UI smoke tests:** `WindowsTerminal_UIATests` (WinAppDriver). They also
  drive **PGO training** (`build/pipelines/pgo.yml`).
- **Fuzzing:** libFuzzer configuration (`doc/fuzzing.md`); OneFuzz in CI.
- **No automated vttest or esctest.** Conformance is checked through targeted
  adapter tests. vttest appears only as manual guidance in the VT52 spec.
- **Tools:**
  - `ConsoleBench`: compare conhost builds on WriteConsole throughput.
  - `benchcat`: a cat with chunking and VT options.
  - `vtpipeterm`: a minimal ConPTY host, the best small example of using the
    API.
  - `RenderingTests`, `vttests/*.py`.
  - Tracing: conhost logs every ConPTY `ReadFile`/`WriteFile` payload through
    TraceLogging (`VtIo.cpp:530-535`, `VtInputThread.cpp:151-156`). Record
    a session with WPR to see exactly what ConPTY sent.

---

## 9. Notable challenges, bugs and workarounds

| Area | Item | Where |
|---|---|---|
| ConPTY | Out-of-sync buffers are "unsolvable" out-of-process; in-proc ConPTY planned | `doc/specs/#13000`, §2.6 |
| ConPTY | `GetConsoleScreenBufferInfo` blocks on CPR after resize; PowerShell calls it per line | `ApiDispatchers.cpp:597-604`, #20510 |
| ConPTY | Close used to wait forever; now doesn't | `7fd9c5c78` |
| ConPTY | Emitting CPR on resize reverted because it could land inside a DCS | `0c064905b` |
| ConPTY | Pseudo-HWND needs a message pump on the input thread, or a DPI change in the terminal can hang ConPTY | `PtySignalInputThread.cpp:55-90`, GH#13066 |
| ConPTY | Must start "hidden"; terminal must send ShowHide(true) | GH#12515 |
| ConPTY | Empty bracketed paste is "load-bearing" for some CLI tools | `2870a702f` |
| Parser | DCS non-ASCII dropped; OSC unbounded; APC ignored | §4.1 |
| Unicode | Pairwise grapheme table knowingly not full UAX #29; process-global mode | §4.3 |
| Buffer | 32 767-row cap; hyperlink pruning scans whole buffer | §4.4 |
| Renderer | Shaping under lock; atlas clear-all; MacType hook crash workaround | §5.2, `BackendD3D.cpp:902-956` |
| Renderer | Present1 fallback flag because of low confidence in dirty-rect presents | `features.xml:61-69` |
| Renderer | `GetClientRect` returns 0×0 after Win+D | `AtlasEngine.api.cpp:458-463` |
| Renderer | Packaged fonts break after app update (DirectWrite cache) | GH#9375 |
| UI | XAML Islands key/mouse/NC workarounds | §7 |
| Input | AltGr heuristics, touch keyboard scancode 0 (GH#7495), AutoHotKey vkeys (GH#7064) | §7 |
| IME | Korean interim chars, edit-session ordering (GH#20244), buggy IME color attributes | `src/tsf/Implementation.cpp` |
| Startup | Single-process model to fix startup speed and threading bugs; NVIDIA loader-lock stall workaround (GH#20348) | `8bbf00e05`, `WindowEmperor.cpp:547-550` |

---

## 10. Lessons for puritty

**ConPTY and the Windows backend**

1. **Correct S§10:** ConPTY is no longer a re-renderer. Current ConPTY
   forwards VT as-is (§2.4). The remaining problems are input translation,
   LF→CRLF for some clients, double parsing and reflow drift (§2.7). The
   embedded-SSH decision (S§3.2) still stands: for SSH it removes conhost from
   the path entirely, with no INPUT_RECORD round-trip, no second reflow, no
   CPR stalls and no UTF-16 round trip. But it is no longer the case that
   ConPTY "rewrites your VT stream".
2. **Ship `conpty.dll` + `OpenConsole.exe`** for each architecture. Don't depend
   on inbox ConPTY: Windows 10 and pre-24H2 Windows 11 still have VtEngine.
   Check at startup that OpenConsole.exe sits next to the DLL, because a
   missing one silently falls back to inbox conhost (§2.2).
3. **ConPTY host checklist:**
   - Use an overlapped duplex pipe (or two), as WT does.
   - Keep a reader running until EOF, including during close.
   - **Answer DA1** with a DA1 that includes `28` if you implement DECCRA.
   - **Answer DSR-CPR fast**, from the parse thread (S§3.3).
   - **Implement win32-input-mode (9001)** and focus events (1004). Treat
     them as always on for ConPTY panes.
   - Pass `PSEUDOCONSOLE_GLYPH_WIDTH_*` matching puritty's width mode.
   - Send ShowHide/Reparent so `GetConsoleWindow()` behaves.
   - Map "clear scrollback" to `ConptyClearPseudoConsole`.
   - Never send 0×0.
4. **Write close and exit code for both OS behaviors.** Treat
   `ClosePseudoConsole` as possibly blocking, as on old inbox kernel32. Call
   it from a thread that isn't the output reader, or after the reader is
   done. Detect exit by output EOF, then `GetExitCodeProcess` (§2.1, §3.2).
5. **Win32-input-mode is the Windows-side key encoding puritty needs**, on
   top of kitty/legacy for SSH and tmux. Ghostty and Alacritty don't have it.
   Its format is trivial (§2.5).
6. **Consider the default-terminal handoff later** (§2.9). It needs a COM
   local server implementing `ITerminalHandoff3`. It is optional and v2
   material.

**Backend interface**

7. WT's `ITerminalConnection` validates the S§3.2 interface. Adopt its
   good properties:
   - monotonic state machine;
   - backends own their reader thread;
   - **no callbacks after Close**;
   - resize forwarded only after local reflow;
   - connection swappable under a live screen (restart, reconnect, reattach);
   - replies queued during parse and written after unlock.

   Change three things: pass bytes rather than UTF-16, use capability
   interfaces rather than downcasts, and give resize both cells and pixels
   (SSH `window-change`).
8. WT's `SshHostGenerator` is a minimum bar for the Windows UX:
   auto-populate hosts from `~/.ssh/config`. Do it properly: follow `Include`,
   honor `Match`/wildcards for defaults, and use the same parser as the
   embedded client's config handling (S§10).

**Core**

9. **Copy:**
   - the streaming DCS handler interface, but **pass non-ASCII**;
   - SIMD scanning for the next control character;
   - streaming grapheme state that can re-measure the previous cell;
   - sixel stored as per-row slices that move with reflow;
   - the commit-on-demand ring arena, which is the Windows twin of Ghostty's
     mmap pages (G§4);
   - the alt screen as a separate, no-scrollback buffer with deferred
     main-buffer reflow.
10. **Avoid:**
    - unbounded OSC buffering;
    - u16 row counts (32 767 cap);
    - whole-buffer hyperlink pruning;
    - a process-global width mode;
    - REP of one UTF-16 unit;
    - an exclusive lock taken by the UI thread for every key event. Use
      lock-free input enqueueing instead.
11. **Text measurement as a negotiated mode.** WT's Graphemes, Wcswidth and
    Console modes, plus mode 2027 reporting, are a reasonable model. Make it
    per-terminal (per pane), since a tmux pane's width model is tmux's, not
    yours.

**Rendering on Windows**

12. **Use AtlasEngine as the blueprint for the D3D11 backend:**
    - instanced quads (about 20 B per instance);
    - one BGRA atlas rasterized by D2D `DrawGlyphRun`;
    - DirectWrite fallback via `IDWriteFontFallbackBuilder` plus system
      fallback;
    - cluster advances snapped to cells;
    - dual-source ClearType blending with gamma/contrast in the shader;
    - procedural box/block/Powerline glyphs;
    - a flip-model swap chain with `FRAME_LATENCY_WAITABLE_OBJECT` and
      `SetMaximumFrameLatency(1)`;
    - `Present1` with one dirty rect + scroll rect, plus a plain `Present`
      fallback;
    - skip Present when nothing is dirty;
    - device-lost → recreate;
    - repeated failure → D2D/WARP.
13. **Do better than AtlasEngine:**
    - Shape outside the lock, from a snapshot.
    - Use LRU or epoch atlas eviction.
    - Actually redraw only dirty rows. This matters for RDP and battery, and
      it pairs with Present1 dirty rects. With flip-sequential, the back
      buffer holds the frame from two presents ago, so partial redraw needs
      either a copy of the previous frame or accumulated damage across buffer
      ages. That is why WT gave up and redraws everything; plan for it.
    - Add an RDP-aware path. Detect `GetSystemMetrics(SM_REMOTESESSION)` and
      prefer D2D/WARP or GDI with minimal invalidation. This is the Windows
      counterpart of the remote-X11 backend (S§6).
14. **Windowing:** plain Win32 rather than XAML Islands avoids most of §7's
    workaround list. Take from WT:
    - PerMonitorV2;
    - snap-to-cell in `WM_SIZING`;
    - the hidden top-level message window for `WM_QUERYENDSESSION`;
    - single-instance hand-off via `WM_COPYDATA`;
    - **a custom TSF client** with `TF_TMAE_CONSOLE` semantics and inline
      composition drawn by the renderer;
    - flushing composition synchronously on key-down.

    For keyboard, copy WT's KeyDown/`ToUnicodeEx`/WM_CHAR split and its AltGr
    heuristics. They encode years of bug reports.
15. **Testing:**
    - A headless `ControlCore` with a `MockConnection` is the pattern for
      puritty's backend tests.
    - Add a fake ConPTY peer that emits the startup handshake
      (`ESC[c ESC[?1004h ESC[?9001h`) and checks puritty's replies.
    - Record real ConPTY sessions with the conhost TraceLogging provider for
      replay tests (S§11).
    - WT has no esctest runs. Puritty should (S§11).

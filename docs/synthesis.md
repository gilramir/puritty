# Synthesis: what a new terminal has to get right

Inputs, and the prefixes used to cite them (for example "G§8.4" is §8.4 of the Ghostty
doc):

| Prefix | Doc | Source analysed |
|---|---|---|
| A | [`alacritty.md`](alacritty.md) | Alacritty @ `54214706`, 2026-10-16 |
| G | [`ghostty.md`](ghostty.md) | Ghostty @ `d8619f1bc`, 2026-10-18 |
| W | [`wezterm.md`](wezterm.md) | WezTerm @ `e2a98e1b8`, 2026-10-10 (nightly; last tagged release Feb 2024) |
| T | [`windows-terminal.md`](windows-terminal.md) | Windows Terminal / OpenConsole @ `9e6cf223d`, 2026-10-19 |
| P | [`putty.md`](putty.md) | PuTTY @ `7507c54b`, 2026-10-14 |

Target product, as stated:

- Linux first, Windows later.
- **Linux: a regular, general-purpose terminal** for development, system work, and so
  on. It runs a local shell in a PTY. SSH happens the usual way, by running the `ssh`
  binary inside it. No SSH client is built in.
- Linux display paths: **X11 over the network** (app on one host, X server on another)
  and **local GPU** rendering. **Efficient remote X11 is mandatory**, not a fallback.
- **Windows: mostly used as an SSH terminal**, with an **SSH client built into the
  app** (leaning that way). Local shells through ConPTY are still needed, but are the
  secondary path there.
- **tmux integration** (control mode, `tmux -CC`) on both platforms.
- The implementation language is deliberately undecided. This document stays
  language-neutral; §12 lists what the design asks of a language.

What this means for the design: one core, one backend interface, two products that
weigh the backends differently. On Linux the PTY backend is the main path and the
SSH-channel backend doesn't exist. On Windows the SSH-channel backend is the main
path and ConPTY is the fallback. Platform-specific code is built only on its own
platform (conditional compilation), so the Linux binary carries no SSH client.

### Why build rather than adopt WezTerm

WezTerm is the closest existing terminal: it has the right backend layering, an
embedded SSH client with connection sharing, working tmux `-CC` tab/split mapping,
and predictive echo (W§0). Its Windows SSH gaps (no ProxyJump, no Windows agent or
Pageant, no reconnect, keepalives that can't detect a dead link) and tmux gaps could be
fixed by contributing. The deciding factor is remote X11: WezTerm renders only through
OpenGL/wgpu, uses XRender only for cursors, rebuilds the whole frame every time, and
has no scroll or damage information reaching the renderer (W§7). Adding a server-side
X11 renderer would mean reworking its renderer, its damage tracking and its threading,
the parts where it is weakest. Its release cadence (last tagged release Feb 2024)
and size add to the case for a smaller, purpose-built design that borrows its ideas.

---

## 1. The short version

Six things none of the five reference terminals fully does for you, and that your
requirements make central:

1. **Remote X11 needs its own renderer.** Alacritty, Ghostty and WezTerm are all
   GPU-only. Over `ssh -X` they render on the remote CPU (llvmpipe) and send a full
   window of pixels per frame (A§6.3, G§6.4, W§7.5). You need a second backend that
   draws with **X server-side primitives**: XRender glyph sets, `CopyArea` for
   scrolling, filled rects for backgrounds. It should send only damaged cells and
   never block on a round trip. PuTTY's GTK front end is prior art for most of this
   (shadow-screen diffing, a server-side pixmap, server-side glyph masks), but it has
   no scroll-by-blit (P§8.5, P§9.4).
2. **The backend abstraction decides how much code tmux and SSH cost.** A tmux pane
   has no PTY: its bytes arrive inside another terminal's DCS stream, input goes out
   as `send-keys`, size is set with `refresh-client`. WezTerm proves the payoff of
   getting this right: PTY, ConPTY, SSH channel and tmux pane all sit under one
   terminal implementation, so `tmux -CC` inside an embedded SSH pane needed no extra
   code (W§2). It also shows the cost of getting the shape wrong (blocking readers,
   process-shaped API). Design the interface first (§3.2).
3. **Damage tracking must reach the screen.** Alacritty uses damage only for Wayland
   hints. Ghostty, WezTerm and Windows Terminal's AtlasEngine all rebuild or redraw
   the full frame and at best pass dirty rects to the compositor (G§5.3, W§7.2,
   T§5.2). Only PuTTY draws just what changed. For remote X11 (and RDP on Windows)
   the damage set *is* the network payload. Add explicit scroll deltas, which none of
   them report to the renderer.
4. **Grapheme clusters and shaping are hard to retrofit.** Alacritty and PuTTY store
   one codepoint per cell. Ghostty, WezTerm and Windows Terminal designed for
   clusters and shaping. Decide on the cell content model now.
5. **Distance changes latency assumptions.** On Linux the distance is the X link. On
   Windows it's the SSH connection. Query replies, clipboard, terminfo, and echo
   latency all behave differently when the app and the shell are far apart (§8).
6. **An embedded SSH client is a security product, not a transport.** Once the app
   speaks SSH itself, it is the trusted party: host-key decisions, credential prompts
   that a malicious server must not be able to fake, agent access, keepalives that
   actually detect a dead link. PuTTY has decades of lessons here; WezTerm's client
   shows the gaps you get when it's treated as plumbing (P§4–§7, W§3, §10.2).

Everything else, including the parser, grid, PTY handling, and input encoding, is
mostly solved. Copy the best of the designs, listed below.

**A correction to earlier versions of this doc:** ConPTY no longer re-renders the VT
stream. Since Aug 2024 (`450eec48d`, "Goodbye VtEngine") the open-source ConPTY
forwards the client's VT unchanged and translates only classic Console API calls into
VT (T§2.4). Embedded SSH on Windows is still the right call, but for different
reasons: no double parsing, no INPUT_RECORD translation, no second reflow, no cursor
resync stalls (§10.1).

---

## 2. Side-by-side

### 2.1 Core, rendering, platform

| Area | Alacritty | Ghostty | WezTerm | Windows Terminal | Take from |
|---|---|---|---|---|---|
| Core/GUI split | `alacritty_terminal` crate | `libghostty-vt`, C API | `termwiz` + `wezterm-term` + `mux` | TerminalCore / ControlCore | All: a headless core is essential |
| Threads per terminal | 1 PTY thread; UI thread renders all windows | gather, parse, writer, renderer | reader + parser (joined by a socketpair) + writer per pane; GUI thread renders all windows (W§1.2) | reader+parser per pane, render thread per pane, one UI thread (T§6) | IO thread + render thread (§4) |
| Lock fairness | `FairMutex` lease | demand counter + `yieldToDemand` | — | fair ticket lock, 128 KiB parse per hold (T§6) | Any of the three fair schemes |
| Render snapshot | copy visible cells | incremental dirty-row `RenderState` | per-line seqno + `StableRowIndex` (W§4.3) | row-range invalidation, cached shaped rows | Ghostty's snapshot + WezTerm's seqnos |
| Parser | vte; **DCS dropped** | DEC machine + SIMD, DCS/APC/OSC | vtparse; owned `Action` per sequence | DEC machine + SIMD; **DCS drops non-ASCII**, APC ignored (T§4.1) | Ghostty |
| Sync output (2026) | buffer bytes, 150 ms timeout | skip renders, 1 s timeout | **no timeout** (W§12.5) | yes, unlocks during hold | Any, but with a timeout |
| Cell | 24 B | 8 B + per-page side tables | 24 B, inline 7-byte cluster (W§6.2) | attribute runs per ROW (T§4.4) | Ghostty |
| Scrollback | ring of rows, lines | mmap pages, bytes | lines, compress line on scroll-off | commit-on-demand ring arena; **u16 row cap (32 767)** | Ghostty pages + WezTerm's cold-line compression |
| Graphemes | none | UAX #29, mode 2027 | yes | negotiated text-measurement modes (T§4.3) | Ghostty, per-pane mode like WT |
| Shaping | none | HarfBuzz + run cache | HarfBuzz; async font fallback (W§7.4) | DirectWrite, under the terminal lock | Ghostty + WezTerm's async fallback |
| GPU | GL 3.3→GLES2→GL 2.1 | GL 4.3 | glium GL (default) / wgpu | D3D11, D2D/WARP fallback | Alacritty's ladder; AtlasEngine on Windows |
| Damage to screen | Wayland hint only | full frame | full rebuild every frame | full redraw; dirty rect only as `Present1` hint | None — build it |
| Remote X11 | llvmpipe, full frames | llvmpipe + `glReadPixels` | EGL only; nothing remote-friendly | n/a (no RDP detection) | PuTTY GTK as prior art (§6.2) |
| Tabs/splits | no | immutable `SplitTree` | binary split tree | pane tree | Ghostty's tree |
| tmux `-CC` | nothing | protocol layer, **no GUI**, octal-unescape bug | **GUI mapping works**, correct unescape, several gaps (W§5) | none | WezTerm's mapping + Ghostty's protocol rigour |
| Windows | ConPTY + WGL | ConPTY in core only | sideloaded ConPTY; WGL default; SSH bypasses ConPTY | the reference | T for ConPTY, input, IME, D3D11 |
| Testing | ref tests | fuzz, esctest2, inspector | unit tests | headless ControlCore + mock connection (T§8) | All |

PuTTY is left out of this table: its terminal core is dated (no reflow, no DCS, no
2026, no graphemes, P§8) and its value is in its SSH, backend and repaint designs.

### 2.2 SSH and the backend interface

| Area | WezTerm | Windows Terminal | PuTTY | Take from |
|---|---|---|---|---|
| Backend interface | two layers: `MasterPty`+`Child` (bytes) under `Pane`; `Domain` owns spawn/split (W§2) | `ITerminalConnection`: bytes as UTF-16, monotonic state, no callbacks after Close (T§3.1) | `Backend` down + `Seat` up, backpressure by return value, `sendok`, "specials" (P§1.3–1.4) | WezTerm's layering, PuTTY's Seat, WT's lifecycle rules |
| SSH implementation | libssh **and** libssh2 behind an enum; features drift (W§3.1) | none: `ssh.exe` inside ConPTY (T§3.4) | own, layered, single-threaded coroutines (P§2) | One implementation, layered like PuTTY |
| ssh_config | own parser; Host, Include, tokens, some Match; bugs (W§3.2) | reads hosts to make profiles only | not read | Parse it; test against `ssh -G` |
| known_hosts | yes; libssh2 path skips check if file missing | n/a | own registry store | OpenSSH `known_hosts`, PuTTY's UX |
| Agents on Windows | AF_UNIX `$SSH_AUTH_SOCK` only | n/a | Pageant (own); not the OpenSSH pipe | Both OpenSSH pipe and Pageant |
| Prompts | in the pane, as text, before swapping in the channel (W§2.4) | n/a | async; trusted-text marker server bytes can't forge (P§5.5) | Pane-is-dialog + trust marker |
| Keepalive | IGNORE packets, no death detection | n/a | IGNORE packets, no death detection | Reply-requiring keepalives with a miss limit |
| Reconnect | no | restart swaps connection under the same screen | manual "Restart Session" keeps screen | WT's swap + auto-offer reconnect |
| Jump hosts | ProxyCommand only | n/a | composition: an SSH client whose channel is the next hop's socket (P§6.4) | PuTTY's composition |
| Connection sharing | one session, one channel per pane | n/a | upstream/downstream over named pipe (P§6.1) | In-process: one connection per host, channel per tab |
| Slow-link UX | predictive local echo above 100 ms RTT (W§4.4) | — | — | WezTerm's, made smarter |

---

## 3. Architecture to aim for

```
                ┌───────────────────────────── core library (no GUI deps) ─────────────────────────────┐
                │                                                                                      │
 Backend ──────►│  Parser (state machine + fast paths) ──► Handler ──► Terminal state                  │
  (bytes in,    │      DCS sub-parsers: tmux, XTGETTCAP, DECRQSS, [sixel]       (screens, pages, pins) │
   bytes out,   │      APC sub-parsers: [kitty graphics]                               │               │
   resize,      │                                                                      ▼               │
   events up)   │  Replies (DA/DSR/CPR/OSC queries) ──► written to Backend directly    RenderState     │
  • PTY/ConPTY  │                                                         (dirty rows + scroll deltas) │
  • tmux pane   │                                                                                      │
  • SSH channel └──────────────────────────────────────────────────────────────────────┬───────────────┘
    (Windows)                                                                          │ frame = changed rows
                ┌──────────────────────────── frontend ────────────────────────────────▼───────────────┐
                │  Renderer interface:  begin(damage) / draw_row_bg / draw_glyph_run / scroll(n) / end │
                │     ├─ GPU backend (GL 3.3 core / GLES 3 on Linux; D3D11 on Windows)                 │
                │     ├─ X11 backend (XRender glyphsets + CopyArea + rects; async X protocol)          │
                │     └─ [Windows remote-session path: minimal invalidation for RDP]                   │
                │  Window/platform: X11, [Wayland], Win32                                              │
                │  Input: key encoder (kitty + legacy + win32-input-mode), mouse, IME, clipboard       │
                │  Layout: windows / tabs / split tree  ◄── also driven by tmux layout notifications   │
                │  Connection owners ("domains"): local, SSH host (Windows), tmux session              │
                └──────────────────────────────────────────────────────────────────────────────────────┘
```

Design points behind this picture:

### 3.1 Keep a headless core

All four modern references have one and benefit: other projects embed it, it can be
fuzzed, and it can run esctest2 without a window (A§1.1, G§1.1, G§10, W§1.1, T§8).
Rules worth copying:

- The core talks to the frontend only through an event/callback interface plus a
  write/resize sink.
- Colours stay **unresolved** (palette index / named / RGB) in the grid. Resolution
  happens at render time, so palette changes need no grid rewrite (A§4.1).
- Each thread gets its **own immutable copy of derived config** on reload, never a
  shared mutable config (G§9).
- **Key encoding lives in the core**, not the front end, so every platform sends
  identical bytes (P§13).

**Option worth evaluating:** adopt `libghostty-vt` as the core. It has a C API,
builds on Windows, is fuzzed and conformance-tested, and includes key/mouse/paste
encoders and the render-state API. It already contains the tmux protocol layer.
The costs are an unstable API, a Zig toolchain dependency, and that you'd inherit
its tmux gaps (§7.4). Even if you don't adopt it, use it as the benchmark.

### 3.2 The backend interface

You need three backends:

| Backend | Platforms | Bytes in | Bytes out | Resize |
|---|---|---|---|---|
| PTY (local shell; on Linux also the `ssh` binary) | Linux (main), Windows (secondary, via ConPTY) | PTY master / ConPTY pipe | same | `TIOCSWINSZ` / `ResizePseudoConsole` |
| tmux pane | both | `%output %N …` from the control connection, octal-unescaped | `send-keys -H -t %N …`, batched per burst | `refresh-client -C …` (window-level; see §7) |
| SSH channel | Windows only (main) | channel data | channel data | `window-change` (cells **and** pixels) |

**Linux** needs only the first two. SSH is just a program running in the PTY, as in
any other terminal. OpenSSH already handles config, agents, keys, `ProxyJump`, and
`ControlMaster`, and Linux users expect exactly that behaviour.

**Windows** is where the embedded SSH client pays for itself (§10.1).

The tmux control connection sits on top of whichever byte stream carries tmux: a
Linux PTY running `ssh host tmux -CC attach`, or on Windows an SSH channel running
`tmux -CC attach` directly. Keep the tmux layer unaware of which. WezTerm gets this
for free from its layering (W§2).

What the references teach about the interface's shape:

- **Two layers** (W§2.1–2.2). A byte-level backend under one "terminal surface" type
  that owns the parser, state and renderer feed. Every backend shares that one
  terminal implementation.
- **Message-based, not blocking-read-based.** WezTerm wraps SSH channels and tmux
  output as blocking readers using socketpairs and extra threads: three threads and
  two socketpairs between the SSH socket and the parser (W§3.6). Instead, the backend
  calls `deliver(bytes)` into the terminal; the terminal calls `write(bytes)` and
  `resize(cols, rows, px_w, px_h)` on the backend.
- **An upward channel, not just a downward one.** PuTTY's `Seat` (P§1.4) is the model
  for what a backend needs to tell the UI:
  - output, with the return value as a backlog figure, so the terminal's parse rate
    drives SSH channel window size (backpressure end to end);
  - EOF, remote exit (with status) vs. connection lost;
  - fatal and non-fatal errors;
  - async prompts (host key, passphrase, keyboard-interactive) with results
    `{pending, ok, user-abort, software-abort(msg)}`;
  - trust state (§10.2) and "available actions changed".
- **No process concepts in the base interface.** PID, foreground process, tty name
  and cwd are optional capabilities. WezTerm's `todo!()` in `TmuxChild::try_wait`
  and `None`s on SSH show the cost of a process-shaped API (W§2.1). Likewise,
  ConPTY-only extras (clear, show/hide, reparent) should be capability interfaces,
  not downcasts as in WT (T§3.5).
- **Backend-published actions** ("specials", P§1.3): break, signals, rekey, "accept
  new host key", reconnect. The pane's menu shows them without knowing about SSH.
- **Input gating.** Don't deliver keystrokes until the backend says it's ready
  (`sendok`, P§1.3). Buffer them meanwhile, so typing during connect doesn't reach a
  jump host's prompt.
- **Lifecycle rules from WT** (T§3.1): a monotonic state machine
  (connecting → connected → closed/failed); **no callbacks after Close returns**;
  resize forwarded only after the local reflow succeeds; replies queued during parse
  and written after unlock.
- **Swappable under a live screen.** WT's restart replaces the connection under the
  same buffer (T§3.1). That's also reconnect for SSH and reattach for tmux.
- **The pane is the dialog** (W§2.4). An SSH pane appears immediately and runs the
  host-key and auth prompts inside itself, then swaps in the real channel. Errors stay
  visible in the pane. Only the "host key changed" case deserves a separate modal.
- **A connection owner per remote** ("domain", W§2.3): local, an SSH host, a tmux
  session. It spawns panes, handles split requests (for tmux: send the command, create
  the native split when tmux's notification arrives), and tracks attach/detach.

### 3.3 Query replies must not depend on the UI thread

Alacritty generates DA, DSR, and OSC colour-query replies on the PTY thread but sends
them to the UI thread, which writes them back to the PTY (A§1.5). A UI thread blocked
on an X11 round trip then delays every remote app that probes the terminal. Ghostty
writes replies straight from the parse thread (G§2.2), and WT queues them during the
parse and writes them after unlock (T§3.1). Do that. ConPTY makes this more urgent:
conhost blocks some Console API calls on a DSR-CPR reply for up to ~500 ms (T§2.6).

---

## 4. Threads, locking, data flow

Recommended model:

- **Per terminal: one IO thread** that reads, parses under the lock, and writes.
  Ghostty's separate gather thread exists to work around macOS's ~1 KiB tty read cap
  (G§2.2). On Linux a 64 KiB–1 MiB read buffer on one thread is enough (A§1.3). WT
  parses up to 128 KiB per lock hold (T§6).
- **Per SSH connection (Windows): one IO loop** serving all its channels. It must
  never block: not on a UI prompt, not on opening a new channel. Prompts are async
  yields (P§2.3, P§13), and WezTerm's habit of running blocking requests on the
  session thread stalls other channels (W§3.5). Channel data goes straight into
  each pane's parser, not through socketpairs.
- **One render thread per window**, or one for all windows. Alacritty renders all
  windows on the UI thread and had to disable vsync (A§5.6). WT runs one per pane.
- **UI/main thread** handles window-system events, input, and layout only. WT takes
  an exclusive terminal lock for every key event; queue input lock-free instead
  (T§10).

Locking rules the references converged on:

1. One mutex guards terminal state.
2. The renderer holds it **only to copy dirty rows**, then renders unlocked
   (A§1.3, G§4.8). WT shapes text with DirectWrite *while holding the lock*; don't
   (T§5.2).
3. Make it fair: Alacritty's lease, Ghostty's demand counter, or WT's ticket lock.
   Plain mutexes starve the renderer under `cat bigfile`.
4. Cap work per lock hold. Alacritty uses 64 KiB of parse; WT 128 KiB; Ghostty one
   batch.

Messaging rules:

- Use bounded, typed mailboxes with an async wakeup. Avoid closures. Keep small
  payloads inline (G§1.2). **Never use unbounded queues** for data heading to a slow
  consumer; WezTerm's per-client mux queue is unbounded (W§4.3).
- Coalesce resize (Ghostty: 25 ms) and wakeups. Many "data arrived" notifications
  should become one render. PuTTY caps paints with a 20 ms cooldown (P§8.5).
- **Event-loop fairness:** when the network floods, still service input and paint.
  PuTTY drains network messages only until it sees a non-network one (P§2.3).
- Time out synchronized output. Ghostty uses 1 s and Alacritty 150 ms; WezTerm has no
  timeout. A buggy app must not freeze the display.
- **Resize order:** call `TIOCSWINSZ` *before* reflowing, under the same lock, so the
  shell's SIGWINCH redraw is never parsed against old dimensions (G§2.3, A§4.5).
- **Pause parsing across geometry round trips** (P§8.6, P§13): while a tmux
  `refresh-client` awaits `%layout-change`, or a remote resize awaits confirmation,
  later bytes belong to the new size.
- **Paste in slices**, one chunk per loop turn, subject to backend backpressure
  (P§13).

---

## 5. Parser and terminal state

### 5.1 Parser

- Use Paul Williams' DEC state machine (vt100.net). Everyone does.
- Add a **ground-state fast path**: find the next ESC/control byte with memchr or
  SIMD, decode UTF-8 in bulk, and hand whole printable runs to a `print_slice`
  routine (A§3.1, G§3.2, T§4.1). Keep a byte-at-a-time path as a test oracle and fuzz
  both against each other.
- **Dispatch directly.** WezTerm builds an owned `Action` value per sequence on the
  hot path (W§6.1). Keep such a type for tests and recording only.
- **DCS and APC are not optional.** Make them pluggable sub-parsers chosen at `hook`
  time (WT's streaming DCS handler interface is a good shape, T§4.1).
  - DCS `1000p` → tmux control-mode parser (§7).
  - `+q` XTGETTCAP and `$q` DECRQSS. WT lacks XTGETTCAP.
  - Optional: sixel (DCS) and kitty graphics (APC; WT ignores APC entirely).
  - Feed payloads **as slices, not bytes** (G§3.2, G§8.4).
- **UTF-8 inside DCS:** treat 0x80–0xFF inside DCS as payload, including 0x9C. tmux
  pane content is UTF-8. Ghostty changed its parse table for this (G§3.1); WT still
  drops non-ASCII DCS bytes, which would break tmux `-CC` (T§4.1).
- **Bound every attacker-controlled buffer:** OSC length (WT's is unbounded), DCS
  length (tmux line cap 1 MiB in Ghostty), params (24–32), title stack, kitty keyboard
  stack, grapheme length per cell, sync buffer (A§9).

Minimum sequence coverage for a modern terminal (local and over SSH): everything in
A§3.2, plus OSC 7 (cwd), OSC 133 (prompt marks), OSC 8, OSC 52, OSC 9/777
notifications, XTVERSION, DECRQM, mode 2026 (sync), 2004, 1004, and 1006/1016 mouse.
Add 2027 (grapheme) and 2048 (in-band resize) when the grid supports them.

### 5.2 Cells and pages

Ghostty's design is the best one to start from:

- **8-byte cell:** content (codepoint, or a flag meaning "grapheme in side table" or
  "bg colour only"), a 16-bit **style id**, wide-char state, and a few flag bits
  (G§4.3). WezTerm's 24-byte cell with an inline 7-byte cluster is a simpler middle
  ground (W§6.2).
- **Interned styles per storage block**, ref-counted.
- **Side tables** for rare data: grapheme tails and hyperlinks.
- **Row header flags** that may have false positives but never false negatives
  ("has styles", "has graphemes", "has links", "wrapped", "dirty").
- **Rows point to cells by offset**, so IL/DL and scroll regions swap row headers
  (G§4.2).

Storage:

- Fixed-size blocks of rows, **recycled** when the scrollback limit is hit (G§4.5).
  WT's commit-on-demand ring arena is the Windows equivalent (`VirtualAlloc` with
  reserve/commit, T§4.4).
- **Compress cold lines.** WezTerm stores lines that scroll off as one string plus
  attribute runs (W§6.2). Cheap and effective even with page-based storage.
- **Offsets instead of pointers** inside a block, for cheap clone, snapshot,
  compression, and serialisation (G§4.2).
- Set the scrollback limit in **bytes**. Don't use 16-bit row counts (WT caps at
  32 767 rows, T§4.4).
- **Tracked positions** ("pins") with generation counters (G§4.5).
- **One dirty-tracking mechanism for everything.** WezTerm gives each line a sequence
  number and each row a stable index that survives scrollback trimming (W§4.3). The
  same data feeds the local renderer, remote X11 damage, and any future network
  protocol.

### 5.3 Unicode

- Use a generated width table so you control the Unicode version.
- **Store grapheme clusters per cell from the start**, with UAX #29 break checks
  gated by mode 2027 (G§4.7). Streaming grapheme state that can re-measure the
  previous cell handles VS16 widening (T§4.3).
- **Make the width model per pane, not global.** WT's measurement modes (graphemes,
  wcswidth, console) are a good model, but WT makes the choice process-global
  (T§4.3). A tmux pane must use tmux's width model, a local pane can use yours.
- Width disagreements between your terminal, the remote `wcwidth`, and tmux **will**
  happen over SSH. Match xterm/tmux in legacy (non-2027) mode and test with
  `ucs-detect` (G§10).
- On Windows, pass ConPTY the `PSEUDOCONSOLE_GLYPH_WIDTH_*` flag that matches your
  width mode (T§2.1).

### 5.4 Reflow and alt screen

- Reflow is the bug farm everywhere (A§4.5, G§4.5, W§6.4, T§4.4). Most rebuild all of
  history on a column change.
- Plan for **lazy reflow** of off-screen history if you allow large scrollback.
- Keep the alt screen as a separate buffer with no scrollback, and don't reflow it.
  WT defers main-buffer reflow while the alt screen is active (T§4.4).
- Write exhaustive tests before writing the reflow code.
- **tmux panes don't reflow locally.** tmux owns the content and resends it.
- **ConPTY panes reflow twice** (conhost and you), and the two drift (§10.1). WezTerm
  special-cases ConPTY resize and soft-wrap quirks in its model (W§9.1).

---

## 6. Rendering: two backends behind one interface

### 6.1 Why "GPU + llvmpipe" isn't good enough remotely

What happens today with `ssh -X host terminal`:

- **Alacritty:** GLX first; usually falls back to llvmpipe, renders on the remote CPU,
  redraws every cell, swaps the full window, then `glFinish` (A§5.1, A§6.3).
- **Ghostty:** can't export a DMA-BUF to a remote X server, so it does a full
  `glReadPixels` on every frame and GTK sends the whole image. No frame cap on Linux
  (G§5.2, G§6.4).
- **WezTerm:** EGL only; "software" mode is Mesa llvmpipe; full rebuild every frame;
  RENDER is used only for cursors (W§7.5).

A 1600×1000 window at 4 B/pixel is ~6.4 MB per frame. A cursor blink costs the same
as a full repaint.

### 6.2 The X11 backend (classic, server-side)

This is how xterm, urxvt, st and PuTTY's GTK front end stay fast over the network.
The bytes sent per update scale with *changed text*, not window size:

| Operation | X request | Network cost |
|---|---|---|
| New glyph first seen | `RenderAddGlyphs` to a server-side GlyphSet (once per glyph/size/style) | glyph bitmap, once |
| Draw a run of text | `RenderCompositeGlyphs8/16/32` | a few bytes per glyph |
| Cell backgrounds | `RenderFillRectangles` / `PolyFillRectangle` (coalesce runs of same bg) | a few bytes per run |
| Scroll N lines | **`CopyArea`** of the scroll region, then draw only the new rows | ~28 bytes + new rows |
| Cursor, underline, selection | small fills / glyphs | tiny |
| Fallback (no XRender) | core text or `PutImage` of dirty rects | larger, still damage-limited |

Rules for this backend:

- **Use asynchronous X protocol access** (XCB-style request/reply cookies), and
  never wait on a reply in the draw path. Intern atoms at startup in one batch. Make
  clipboard, IME position, and property reads asynchronous. Each synchronous call is
  a full network RTT on the UI thread (A§6.3).
- **Copy PuTTY's repaint discipline** (P§8.5):
  - keep a shadow of what is on screen and diff per row;
  - when anything in a run changes, redraw the whole previously drawn run, to cope
    with glyphs that overhang their cells;
  - coalesce with a cooldown timer (PuTTY: 20 ms).
- **Keep a retained server-side pixmap** for the window contents, so exposes don't
  require a redraw from the terminal state (P§9.4).
- **Scroll detection must exist in the core.** The renderer needs "the viewport moved
  up N rows", not "every row is dirty". None of the five terminals reports this to
  its renderer; PuTTY's lack of scroll-by-blit means `tail -f` resends every row.
- **Adaptive frame pacing.** Cap the rate according to how fast the X server consumes
  requests. "Latest frame wins": drop intermediate states, never queue them (G§5.4).
  WezTerm's mux protocol shows the failure mode of not doing this (§8.1).
- Glyph rasterisation stays local. Only glyph bitmaps cross the wire, once. Colour
  emoji need ARGB glyphsets, which XRender supports.
- MIT-SHM, DRI3, and Present are local-only. Use them when local; never depend on
  them.

### 6.3 The GPU backend (local)

Copy the proven pieces:

- **Glyphs** as instanced quads from an atlas (A§5.2, G§5.3, T§5.2; WT's instances
  are ~20 B).
- **Procedurally drawn** box-drawing, block, Powerline, braille, and legacy-computing
  glyphs, so lines join exactly at any cell size. Every modern reference does this.
  The X11 backend can reuse the same rasteriser.
- **GL minimum around 3.3 core or GLES 3.0** on Linux, with Alacritty's fallback ladder
  and robust-context reset recovery (A§5.2, A§6.1). Ghostty's GL 4.3 floor rules out
  some hardware (G§5.4).
- **Frame pacing:** vsync or presentation feedback on Wayland; on X11, Alacritty's
  refresh-phase timer plus `glFinish` (A§5.6).
- **Redraw only changed rows**, not just upload them. Ghostty, WezTerm and WT all
  redraw the whole frame. WT explains why: with a flip-model swap chain the back
  buffer holds a frame from two presents ago, so partial redraw needs a copy of the
  previous frame or damage accumulated across buffer ages (T§10). Plan for this from
  the start; it pays off on battery, RDP and VMs.
- Skip drawing when nothing is dirty (WT skips `Present`) or the window is occluded.
- **Atlas eviction.** Alacritty and Ghostty atlases only grow; WT clears the whole
  atlas when full. Use LRU or epoch eviction.

### 6.4 Choosing a backend at runtime

1. User override in config or on the CLI.
2. If `DISPLAY` has a host part (`host:0`, including `ssh -X`'s `localhost:10`), or
   the X server lacks DRI3/MIT-SHM, use the X11 backend.
3. Otherwise try the GPU path. If context creation fails, or `GL_RENDERER` reports
   llvmpipe/softpipe, fall back to the X11 backend.
4. On Windows, check `GetSystemMetrics(SM_REMOTESESSION)`. Under RDP prefer a
   minimal-invalidation path (D2D/WARP or GDI). No reference terminal does this
   (T§10, W§9.3).
5. **Failure must be visible and never fatal.** Ghostty's "no GL context" page is
   unreachable (G§6.4). Alacritty exits.

### 6.5 Fonts and shaping

- **Discovery:** fontconfig on Linux, DirectWrite on Windows, with per-style fallback
  chains and negative-result caching (A§5.4, G§5.5, T§5.2).
- **Async fallback:** render immediately with what you have, redraw when the fallback
  font is found (W§7.4). Ghostty and WT do fallback discovery synchronously, on the
  render thread or under the terminal lock.
- **Shaping** (HarfBuzz or DirectWrite): if yes, follow Ghostty: runs never cross
  rows; break on style, font, selection edges, and the cursor; force LTR; cache by a
  position-independent run hash (G§5.5). Shape from a snapshot, outside the lock.
- **Synthetic bold and italic** for fonts lacking those styles.
- **Bundle a fallback font set** so remote or minimal hosts still render.
- With the X11 backend, glyph upload is an X request, so cache both rasterised
  bitmaps and server-side glyph ids.

---

## 7. tmux control mode

### 7.1 Protocol facts to design around

- **Entry:** tmux writes `ESC P 1000 p`, then a line protocol, then ST at exit.
- **Lines:**
  - Command replies are `%begin <time> <num> <flags>` … `%end|%error <time> <num>
    <flags>`.
  - Async notifications start with `%`: `%output`, `%layout-change`, `%window-add`,
    `%window-close`, `%session-changed`, `%exit`, `%pause`, `%continue`,
    `%extended-output`, and others.
- **`%output %<pane> <data>`:** bytes below 0x20 and `\` are **octal-escaped**. WezTerm
  decodes them correctly (W§5.1); Ghostty doesn't (G§8.4).
- **Commands** are written to the byte stream tmux is running on: the local PTY on
  Linux, or the SSH channel on Windows.
- **Pane content is UTF-8 inside a DCS**, so the DCS path must pass non-ASCII bytes
  (§5.1).

### 7.2 Two partial implementations to learn from

| | Ghostty (G§8) | WezTerm (W§5) |
|---|---|---|
| Parser | capped line parser; regex per line | full grammar for tmux 3.x notifications |
| `%output` unescape | **missing** | correct |
| Reply matching | one command in flight, FIFO | FIFO **without checking `%begin` numbers**; resize sends two commands sharing one reply slot |
| Unknown lines | — | **fatal**: pane drops out of control mode |
| State on attach | `capture-pane` history + visible, both screens, `list-panes -F` for modes | creates tabs and splits from the layout |
| GUI | **none** | windows→tabs, layout→splits; new tab/split/focus/resize/keys round-trip to tmux |
| Layout after attach | parser with checksum | **ignored** after initial attach |
| Pre-capture output | TODO | backlog keeps only the last chunk |
| Flow control | none | none |
| Threading | all panes under parent terminal's lock | a blocking write into one pane can stall all panes |

Take Ghostty's rigour (strict `%end` matching, typed `-F` format fields, layout
checksum, full pane state reconstruction) and WezTerm's grammar coverage and GUI
round trips. Port both projects' test cases.

### 7.3 What you need to build

1. **PTY-less terminal surfaces** whose backend is "tmux pane %N" (§3.2). Each gets
   its own terminal state and renderer. Input is encoded exactly as for a local
   terminal and sent as `send-keys -H -t %N <hex>`, batched per burst rather than
   one command per write.
2. **Layout mapping:**
   - A tmux window becomes a tab.
   - The tmux layout tree becomes your split tree (n-ary, or nested binary as in
     WezTerm). Window ids (`@N`) and pane ids (`%N`) are stable.
   - **Apply every `%layout-change`**, not just the first one.
3. **Sizing:**
   - `refresh-client -C WxH`, or per-window `refresh-client -C @win:WxH` on tmux 3.2+.
   - Native resizes become tmux size requests; apply pane sizes **from tmux**. Expect
     rounding differences (1-cell dividers).
   - Pause pane parsing between the request and the `%layout-change` (§4).
4. **Robust command handling:** match replies by `%begin` number; one reply slot per
   command; unknown notifications are logged and skipped, never fatal; parse names
   with `-F` and a delimiter that can't appear (or tmux's `#{q:…}` quoting), not by
   splitting on spaces.
5. **Flow control for slow links:** `refresh-client -f pause-after=N` (tmux 3.2+),
   `%extended-output`, `%pause`, `%continue`. Without this, one noisy pane over SSH
   starves the others. Neither reference does it.
6. **Attach race:** buffer *all* output for a pane until its capture is processed,
   then replay or drop what the capture covers.
7. **Threading:** a control-connection owner that demultiplexes `%output` to
   per-pane terminals, each with its own lock and render wakeup. No pane write may
   block the control reader.
8. **Performance:** hand-written line splitter; slice-based DCS delivery; unescape
   `%output` straight into the pane's parser.
9. **UX decisions:**
   - What the originating terminal shows during control mode.
   - Clean detach (`detach-client`), kill, and reattach from the GUI (WezTerm has no
     kill or detach).
   - Guarding against `tmux -CC` inside a tmux pane.
   - What "scrollback" means (yours from `capture-pane`, vs tmux copy mode).
   - Version detection and graceful degradation on older tmux.
   - On Windows, reconnecting a dropped SSH connection should reattach (§10.2).
10. **Testing:** record real control-mode sessions, including over high-latency SSH,
    and replay them.

### 7.4 Should you build it on libghostty-vt?

- **For:** protocol layer, viewer state machine, format helpers and layout parser
  exist and are tested.
- **Against:** the octal unescape bug, no flow control, it runs inside the parent
  terminal's lock, the API is unstable, and its tmux assumptions aren't documented as
  stable (G§8.7).

Port its *design* and test cases, plus WezTerm's grammar coverage, rather than
depending on it, unless you adopt libghostty-vt as your whole core anyway.

---

## 8. Remote-shell concerns

These apply on both platforms: on Linux whenever the user runs `ssh` inside the
terminal, and on Windows for nearly every session. Concerns specific to the embedded
client are in §10.2.

| Concern | What the references do | Recommendation |
|---|---|---|
| Remote lacks your terminfo | Alacritty uses `TERM=alacritty` only if the entry exists locally. Ghostty's `+ssh` installs terminfo remotely or falls back to `xterm-256color` (A§2.1, G§2.6) | Default to `xterm-256color`-compatible behaviour. Ship an install helper. Answer XTGETTCAP. On Windows, set `TERM` per host in `pty-req` |
| Clipboard from remote vim/tmux | OSC 52. Alacritty: copy-only by default. Ghostty: write allowed, read asks (A§7.4, G§7.5) | Write allowed with a size cap, read asks |
| Query latency | Alacritty routes replies via the UI thread | Reply from the IO thread directly (§3.3) |
| Paste over SSH | Both strip ESC in bracketed paste. Ghostty warns on newline or `ESC[201~` (A§7.3, G§7.5) | Do both. Paste in slices with backpressure (§4) |
| Shell integration | Ghostty auto-injects OSC 133/7 locally only | Support OSC 7/133 from remote shells. Offer remote snippets |
| Output bursts | — | Handle sync output (2026) with a timeout. Coalesce redraws |
| Hyperlinks to remote files | OSC 8 widely supported; OSC 7 gives cwd + hostname | Use the hostname to decide whether a path is openable locally |
| Typing latency on slow links | WezTerm: predictive local echo above 100 ms RTT, predicted cells underlined, replaced by the next real update (W§4.4) | Worth doing on Windows (where you own the connection and can measure RTT). Predict only when echo is likely: no alt screen, not after a password-like prompt or with echo off. WezTerm's password check is a substring test for "sword" |

### 8.1 If you ever ship screen state over a network

WezTerm's mux protocol (W§4) is the only reference that does. Lessons, which also
apply to the remote X11 renderer, where the X connection is the slow link:

- It pushes whole dirty lines on every output event, to every client, through an
  **unbounded** queue, with no scroll operations. Scrolling resends the screen.
- Fix: at most one outstanding update per pane per client, computed when the
  transport can accept it ("latest state wins"); explicit scroll deltas; cell-run
  diffs.
- Negotiate protocol versions instead of demanding an exact match, if visiterm ever
  has a remote helper.

---

## 9. Input

- **Keyboard:** physical key (W3C code) + unshifted codepoint + mods (G§7.1).
  - **kitty keyboard protocol** with a flag stack per screen.
  - Legacy xterm encodings and `modifyOtherKeys` (WT lacks the latter).
  - Alacritty makes legacy sequences **default bindings** users can override (A§7.1).
  - **win32-input-mode** (`CSI Vk;Sc;Uc;Kd;Cs;Rc _`, mode 9001) for ConPTY panes on
    Windows. Trivial format; needed to avoid conhost's input ambiguities (T§2.5).
  - Keys go to the remote by default (PuTTY's principle, P§13).
- **X11 modifier correctness:** use XKB state-notify events (G§6.3).
- **Windows keyboard:** copy WT's KeyDown / `ToUnicodeEx` / `WM_CHAR` split and its
  AltGr heuristics (T§7).
- **IME:** send every key press and release through the IME, attach commits inside a
  key event to that event, draw preedit inline at the cursor (G§7.5, A§6.5). On
  Windows, WT's custom TSF client with `TF_TMAE_CONSOLE` semantics, inline
  composition drawn by the renderer, and composition flushed on key-down is the best
  reference (T§7).
- **Mouse:** SGR (1006) and SGR-pixels (1016). Motion only on cell change. Shift
  bypasses mouse reporting.
- **Bindings:** a trie of key sequences, plus key tables (modes) and
  "performable/unconsumed" flags (G§7.4). For a tmux-centric terminal, consider a
  native prefix-key mode.

---

## 10. Windows

### 10.1 ConPTY: what it does now, and why SSH should still bypass it

Current state (T§2):

- Since Aug 2024 the open-source ConPTY **forwards the client's VT unchanged**.
  Conhost still parses everything into its own buffer, and translates classic Console
  API calls into VT (cursor moves → CUP, scrolls → IL/DL or DECCRA/DECFRA). Conhost
  no longer answers queries; your terminal does.
- Inbox ConPTY on Windows 10 and Windows 11 before 24H2 is the **old re-rendering
  kind**. WezTerm's analysis still treats ConPTY as a re-renderer; that's out of date
  for current builds.
- Only four flags remain (INHERIT_CURSOR, three GLYPH_WIDTH modes,
  AMBIGUOUS_IS_WIDE). Passthrough mode is gone, so ignore advice to enable it.
- `ClosePseudoConsole` no longer waits in the open-source DLL; old inbox builds wait
  indefinitely for conhost to exit.

What still goes wrong (T§2.7):

- Bytes go UTF-8 → UTF-16 → UTF-8; invalid UTF-8 becomes U+FFFD.
- LF becomes CRLF unless the client set `DISABLE_NEWLINE_AUTO_RETURN`.
- Conhost re-injects `?1004h`/`?9001h` after RIS and after apps reset those modes.
- Console API output is lossy: 16 colours, UCS-2, extra SGR 0s.
- Conhost reflows separately from the terminal on resize, then patches the cursor via
  a DSR-CPR that can block for ~500 ms. WT's own spec calls this drift unsolvable.
- Input goes through conhost's INPUT_RECORD layer unless you use win32-input-mode.

So **embedded SSH remains the most important Windows decision**: for SSH sessions it
removes conhost from the path entirely — no double parse, no input translation, no
second reflow, no CPR stalls, no UTF-16 round trip. WezTerm's SSH panes already work
this way (W§9.2).

ConPTY host checklist, for local shells (T§10):

- **Bundle `conpty.dll` + `OpenConsole.exe`** per architecture. Check at startup that
  OpenConsole.exe sits next to the DLL; if it's missing the DLL silently falls back to
  inbox conhost.
- Use an overlapped duplex pipe. Keep a reader running until EOF, including during
  close. Call `ClosePseudoConsole` from a thread that isn't the reader.
- Answer DA1 (include `28` if you implement DECCRA) and DSR-CPR, fast, from the parse
  thread.
- Implement win32-input-mode (9001) and focus events (1004); treat both as always on.
- Pass the GLYPH_WIDTH flag matching your width mode.
- Send ShowHide/Reparent so `GetConsoleWindow()` behaves; map "clear scrollback" to
  `ConptyClearPseudoConsole`. Never resize to 0×0.
- Detect exit by output EOF, then `GetExitCodeProcess`.

### 10.2 The embedded SSH client

It exists only in the Windows build. Users will compare it with OpenSSH and PuTTY.

**Structure**

- **Pick one SSH implementation.** WezTerm compiled in libssh and libssh2 and their
  features drifted apart: keepalive, agent forwarding and signals exist on only one
  (W§3.1).
- **Layer it like PuTTY** (P§2), whether you write it or adopt a library: transport
  (with rekey holding back higher-layer output, so channels never see a rekey),
  userauth, connection (channel multiplexing), and a channel interface per consumer.
  Check that a library offers transparent rekey, per-channel window/backpressure,
  pipelined `pty-req` + `env` + `shell` in one round trip, and **async host-key and
  auth callbacks** that can wait for the UI without blocking the IO loop.
- **Every user interaction is an async yield** (P§13). Host-key dialogs, passphrases
  and keyboard-interactive prompts must not stall the IO loop or other tabs'
  channels.
- **Jump hosts as composition** (P§6.4): a jump connection is a complete SSH client
  whose channel becomes the socket for the next hop. Implement ProxyJump natively;
  WezTerm has only ProxyCommand (W§3.9).
- **Connection sharing is in-process.** One connection per (user, host, port, proxy
  chain), one channel per tab, no re-auth. The connection outlives its first tab;
  warn before closing the last tab of a connection that still has forwardings.
  With several sessions on one connection, X11 forwarding needs per-session fake
  cookies and agent forwarding is necessarily shared (P§6.1). Cross-process sharing
  (PuTTY's named-pipe upstream) is only needed if external tools should reuse GUI
  connections.
- **A server-bug table** keyed on the server version string, with per-host overrides,
  from day one (P§13).

**Configuration and keys**

- **Parse `%USERPROFILE%\.ssh\config`** (Host, Match, Include, tokens, HostName, User,
  Port, IdentityFile, ProxyJump, ServerAlive*, StrictHostKeyChecking,
  UserKnownHostsFile). Treat it as a feature with a test suite: table-driven tests
  against `ssh -G host` output from real OpenSSH. WezTerm's parser has subtle bugs
  (`Match User` against the local user, a typo that disables token expansion for
  `UserKnownHostsFile`) (W§3.2).
- Use the same parser to populate a host list in the UI, as WT's `SshHostGenerator`
  does, but following Include and Match properly (T§3.4).
- **Use OpenSSH `known_hosts`** so the CLI and the app agree. PuTTY's registry store
  is a standing interop complaint (P§4.2).
- **Load OpenSSH private keys natively**; PuTTY requires conversion to PPK (P§5.2).
- **Agents:** the Windows OpenSSH agent (named pipe `\\.\pipe\openssh-ssh-agent`) and
  Pageant. WezTerm supports neither; PuTTY only Pageant (W§3.4, P§5.3).
- **Environment:** most servers reject SSH `env` requests. WezTerm's fallback of
  prefixing `env K=V` to the remote command is pragmatic; make it a per-host choice
  (W§3.4). Send terminal modes in `pty-req` (WezTerm sends none).

**Security UX**

- **Host keys** (P§4):
  - Accept / Connect once / Cancel on first contact.
  - A distinct, alarming mismatch dialog where Cancel is the default and the only
    choice described as safe. This is the one case for a modal dialog.
  - Manually pinned keys hard-fail without a prompt.
  - Prefer host key types already cached; support safe key rotation
    (`UpdateHostKeys` or cross-certification).
  - Honour `StrictHostKeyChecking`. Never skip verification when no known_hosts file
    exists, as WezTerm's libssh2 path does (W§3.3).
  - Structure dialog text so the GUI and any CLI tool render it their own way.
- **Anti-spoofing** (P§5.5). When the app draws prompts inside the terminal, a
  malicious server can print a fake "Enter passphrase:" too. PuTTY marks lines it
  writes itself with a trust bit and draws an icon in the margin that server bytes
  can't produce; server banners and keyboard-interactive prompts are framed and
  stripped of control characters. visiterm should either draw prompts out of band
  (overlay or dialog) or copy the trust bit. Announce each hop ("Connecting via
  jumphost…") before any prompt so the user knows who is asking. This matters more
  for an embedded client than for `ssh` in a PTY, because the app *is* the trusted
  party.
- **Auth:** offer a public key before asking for its passphrase; don't try every agent
  key when a specific identity is configured; optionally refuse servers that grant
  access without real credentials (P§5).
- **Weak-crypto and protocol warnings** with a "WARN below here" line in algorithm
  preferences. PuTTY's Terrapin handling re-runs negotiation to tell the user whether
  reordering preferences would avoid the issue (P§3.2, P§3.4).

**Connection health**

- **Keepalives that detect death.** Both WezTerm and PuTTY send `SSH_MSG_IGNORE`,
  which gets no reply and so can't detect a dead server. Use reply-requiring requests
  (`keepalive@openssh.com`) with a miss limit (`ServerAliveCountMax`), plus a connect
  timeout (WezTerm has none) (W§3.7, P§7).
- **Disconnect UX:** keep the pane and scrollback, show the state in the pane (no
  modal box), offer reconnect. PuTTY's "Restart Session", which keeps the screen and
  resets modes, is the floor. Swap the new connection under the same screen
  (§3.2). With tmux `-CC`, reconnect means reattach.

**Later, not v1:** port forwarding, X11 forwarding, SFTP drag-and-drop.

### 10.3 Rendering, windowing, fonts

- **D3D11 renderer, using AtlasEngine as the blueprint** (T§5.2):
  - instanced quads; one BGRA atlas rasterised by D2D `DrawGlyphRun`; DirectWrite
    fallback via `IDWriteFontFallbackBuilder`;
  - cluster advances snapped to cells; dual-source ClearType blending with
    gamma/contrast in the shader; procedural box/block/Powerline glyphs;
  - flip-model swap chain with a frame-latency waitable object and maximum frame
    latency 1; `Present1` with dirty and scroll rects, falling back to `Present`;
  - device lost → recreate; repeated failure → D2D/WARP.
- **Do better than AtlasEngine:** shape outside the lock, evict the atlas
  incrementally, actually redraw only dirty rows (§6.3), and add the RDP path (§6.4).
- WezTerm's experience argues against GL on Windows: EGL/ANGLE resizes badly, WGL
  breaks on driver updates, DX12 via wgpu crashed on some systems, RDP forces
  software GL (W§9.3).
- **Plain Win32, not XAML Islands.** WT's XAML workaround list (swallowed keys,
  title-bar hit testing, crashes on exit) is long (T§7). Take from WT: PerMonitorV2
  DPI, snap-to-cell in `WM_SIZING`, a hidden message window for
  `WM_QUERYENDSESSION`, single-instance hand-off via `WM_COPYDATA`. WT removed its
  multi-process window model in Dec 2024; one process with one UI thread is enough.
- **Fonts:** DirectWrite for discovery and fallback. WezTerm uses DirectWrite to find
  fonts and FreeType to draw them; WT uses DirectWrite throughout.
- **Memory:** `VirtualAlloc` reserve/commit replaces `mmap` for page storage (G§4.2,
  T§4.4).
- **Default-terminal handoff** (making visiterm the console host for console apps) is
  possible via a COM server implementing `ITerminalHandoff3`. Optional; v2 material
  (T§2.9).

---

## 11. Testing and tooling to build early

1. **Replay tests:** record raw bytes and compare serialised grid state (A§9). Extend
   to tmux control-mode recordings and ConPTY sessions (conhost's TraceLogging
   provider can capture them, T§10).
2. **Conformance:** run esctest2 against the headless core (G§10). WT doesn't; you
   should.
3. **Fuzzing:** parser, OSC/DCS sub-parsers, tmux line parser, full stream; SIMD vs.
   scalar paths against each other. For SSH, a fuzzing build mode with a null cipher
   and a constant RNG, as PuTTY has (P§11).
4. **Backend tests:** a headless terminal surface driven by a mock backend (WT's
   `ControlCore` + `MockConnection`, T§8). A fake ConPTY peer that emits conhost's
   startup handshake (`ESC[c ESC[?1004h ESC[?9001h`) and checks your replies.
5. **SSH tests:** a test SSH server built from the same layers (PuTTY's Uppity, P§2.5)
   or an embedded OpenSSH `sshd` in CI. `ssh -G` as the oracle for config parsing.
   Scripted slow/lossy links for keepalive and reconnect.
6. **Repaint tests:** a headless front end that logs draw calls gives deterministic
   damage tests (PuTTY's `fuzzterm`, P§11). For the X11 backend, measure bytes per
   update with `xtrace`/`x11trace`.
7. **Benchmarks:** deterministic synthetic input plus `hyperfine`. Measure throughput,
   keypress-to-pixel latency, and remote X bytes per update.
8. **Integrity checks:** debug-mode assertions over page and row invariants (Ghostty
   `assertIntegrity`). Fault injection for OOM paths.
9. **Inspector:** an in-app view of recent bytes and parsed events per terminal. You'll
   want it for tmux control mode and SSH.

---

## 12. Decisions to make up front

| Decision | Why it can't wait | Suggested default |
|---|---|---|
| Cell content model | Retrofitting broke Alacritty's ligature and emoji plans | Codepoint + grapheme side table, 8-byte cell |
| Shaping yes/no | Changes glyph cache keys and renderer run structure | Yes, cursor-aware run splitting, from a snapshot outside the lock |
| Backend interface | tmux on both platforms and SSH on Windows depend on it | Two layers; message-based; upward Seat-style events; process details as capabilities (§3.2) |
| Renderer interface with damage + scroll deltas | Required by the X11 backend and RDP; no reference has scroll deltas | Row-granular damage plus explicit scroll ops; one seqno-based dirty mechanism |
| GPU API | Ghostty's GL 4.3 excludes some hardware; GL on Windows is fragile | GL 3.3 core / GLES 3 on Linux; D3D11 on Windows |
| Threading model | Hard to change after state ownership is set | IO thread per terminal, IO loop per SSH connection, render thread, UI thread, one fair lock; bounded queues |
| Core as a separate library | Testing, fuzzing, reuse | Yes; consider libghostty-vt vs your own |
| Scrollback units and reflow | Affects page design and resize cost | Bytes; cold-line compression; plan lazy reflow |
| Width model scope | tmux panes and local panes disagree | Per pane, negotiated (mode 2027) |
| Native tabs/splits | tmux `-CC` needs them anyway | Yes, as an immutable split tree |
| Windows SSH strategy | Determines whether ConPTY is on the main path | Embedded SSH on Windows, one implementation; Linux uses system `ssh` in a PTY |
| Prompt trust model | Decides how prompts are drawn and whether the renderer needs a trust bit per line | Prompts out of band, or a per-line trust bit with an unforgeable margin marker |
| ConPTY distribution | Inbox ConPTY on older Windows is the re-rendering kind | Bundle `conpty.dll` + `OpenConsole.exe` |

### Properties the implementation language must support

The language is deliberately undecided. These are the requirements the design above
puts on it, to check any candidate against:

- **Compact, pointer-free hot data.** The parser and grid want 8-byte cells and
  offset-addressed pages in large flat buffers. A garbage-collected language must let
  you keep these out of the GC's scan set, and you should benchmark pause times during
  `cat`-heavy output.
- **Cheap calls into C libraries**, or native equivalents. FreeType, HarfBuzz,
  fontconfig, GL/D3D11, DirectWrite, and possibly libghostty-vt or an SSH library are
  C/C++/COM. If foreign calls are expensive, batch them per row or run.
- **Asynchronous X11 protocol access**, including the RENDER extension. Some languages
  have pure implementations of the X protocol.
- **Real threads with shared memory** for the IO/render/UI split and a fair lock (§4).
- **Win32 and COM interop** for ConPTY, D3D11, DirectWrite, TSF, and named pipes.
- **A mature SSH implementation** for the Windows build, with async callbacks for host
  keys and auth (§10.2), or the willingness to own one. This may be the deciding
  factor for the Windows product.
- **Fuzzing and benchmarking tools** (§11).

### A sensible build order

1. Headless core: parser, terminal state, replay tests, fuzzing from day one.
2. Linux PTY backend plus the **X11 server-side renderer** (async X protocol,
   XRender, `CopyArea`). It works locally and remotely, and makes damage and
   scroll-delta tracking honest from the start.
3. Input (kitty and legacy), clipboard and OSC 52, IME.
4. tmux control mode: protocol layer, then PTY-less pane surfaces, then the split
   tree and tabs.
5. GPU renderer for local high-DPI and high-throughput use, selected at runtime.
6. Windows:
   1. Win32 window, D3D11 renderer, DirectWrite, TSF IME.
   2. Embedded SSH backend: transport, host keys, auth, agents, config, prompts with a
      trust model, keepalive and reconnect. It's the main use case and skips ConPTY.
   3. tmux `-CC` over SSH channels (should mostly fall out of steps 4 and 6.2).
   4. Bundled ConPTY backend for local shells, with win32-input-mode.

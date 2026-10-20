# Synthesis: what a new terminal has to get right

Inputs: [`alacritty.md`](alacritty.md) (Alacritty @ `54214706`, 2026-10-16) and
[`ghostty.md`](ghostty.md) (Ghostty @ `d8619f1bc`, 2026-10-18). Section references like
"A§5.5" point into the Alacritty doc, and "G§8.4" into the Ghostty doc.

Target product, as stated:

- Linux first, Windows later.
- **Linux: a regular, general-purpose terminal** for development, system work, and so
  on. It runs a local shell in a PTY. SSH happens the usual way, by running the `ssh`
  binary inside it. No SSH client is built in.
- Linux display paths: **X11 over the network** (app on one host, X server on another)
  and **local GPU** rendering.
- **Windows: mostly used as an SSH terminal**, with an **SSH client built into the
  app** (leaning that way). Local shells through ConPTY are still needed, but are the
  secondary path there.
- **tmux integration** (control mode, `tmux -CC`) on both platforms.

What this means for the design: one core, one backend interface, two products that
weigh the backends differently. On Linux the PTY backend is the main path and the
SSH-channel backend doesn't exist. On Windows the SSH-channel backend is the main
path and ConPTY is the fallback. Platform-specific code is built only on its own
platform (conditional compilation), so the Linux binary carries no SSH client.

---

## 1. The short version

Five things neither reference terminal does for you, and that your requirements
make central:

1. **Remote X11 needs its own renderer.** Both terminals are GPU-only. Alacritty
   needs GL 2.1 / GLES 2. Ghostty needs GL 4.3 through EGL. Both redraw the full
   window on each update. Over `ssh -X` they end up rendering on the client CPU
   (llvmpipe) and sending a full window of pixels per frame (A§6.3, G§6.4). You need
   a second backend that draws with **X server-side primitives**: XRender glyph sets,
   `XCopyArea` for scrolling, filled rects for backgrounds. It should send only
   damaged cells and never block on a round trip.
2. **tmux control mode is a different kind of terminal.** A tmux pane has no PTY.
   Its bytes arrive inside another terminal's DCS stream, its input goes out as
   `send-keys`, and its size is set with `refresh-client`. Ghostty built the protocol
   half (G§8) and stopped at the GUI half. Design a **"terminal backend" abstraction**
   (PTY / tmux pane / on Windows, an embedded SSH channel) from day one.
3. **Damage tracking must reach the screen.** Alacritty tracks damage but only uses it
   for Wayland hints. Ghostty tracks dirty rows to rebuild GPU buffers, then re-uploads
   everything and presents a full frame. For remote X11 the damage set *is* the network
   payload.
4. **Grapheme clusters and shaping are hard to retrofit.** Alacritty stores one `char`
   per cell and never added ligatures or ZWJ emoji. Ghostty designed for clusters
   (mode 2027) and HarfBuzz runs from the start. Decide on the cell content model now.
5. **Distance changes latency assumptions.** On Linux the distance is the X link
   (remote display). On Windows it's the SSH connection (the shell is on another
   machine). Either way, terminal query replies, clipboard, and terminfo availability
   behave differently when the app and the shell are far apart. Alacritty routes
   query replies through its UI thread (A§1.5). Both terminals assume `TERM` works on
   the remote host, and Ghostty ships a `+ssh` helper to install terminfo there (G§2.6).

Everything else, including the parser, grid, PTY handling, and input encoding, is
mostly solved. Copy the better of the two designs, listed below.

---

## 2. Side-by-side

| Area | Alacritty | Ghostty | Take from |
|---|---|---|---|
| Core/GUI split | `alacritty_terminal` crate, reused by Zed and others | `libghostty-vt` with a C API that builds on Windows | Both: a headless core is essential |
| Threads per terminal | 1 PTY thread (read + parse + write). One UI thread renders **all** windows | 4: gather, parse, writer, renderer. Main thread is GUI only | Ghostty's split, scaled down (§4) |
| Lock fairness | `FairMutex` lease. Reader keeps buffering while UI holds the lock | Demand counter and `yieldToDemand` at batch boundaries | Either; both solve renderer starvation |
| Render snapshot | Copy visible cells into a `Vec` under lock, then GL unlocked | Incremental `RenderState` copies **dirty rows only** | Ghostty |
| Parser | vte: DEC state machine + memchr ground fast path. **DCS dropped** | Same state machine + SIMD UTF-8 + `printSlice`. DCS/APC/OSC all handled | Ghostty's coverage, vte's simplicity |
| Sync output (2026) | Buffer raw bytes in parser, 150 ms timeout | Renderer skips updates while set, 1 s reset timer | Either; byte buffering is simpler |
| Cell | 24 B: `char` + 2 colours + flags + `Option<Arc<Extra>>` | 8 B packed: codepoint/bg + style id + flags; styles, graphemes, links in per-page side tables | Ghostty |
| Storage | Ring buffer of `Row<Cell>`, O(1) scroll | Linked list of ~400 KiB mmap'd offset-addressed pages, pooled, LZ4 for cold pages | Ghostty for big scrollback; ring buffer is fine to start |
| Scrollback limit | Lines (default 10k) | **Bytes** (default 50 MB) plus optional lines | Bytes |
| Graphemes | None (zero-width chars attach, max 9) | UAX #29 clustering with mode 2027, max 64 codepoints | Ghostty |
| Reflow | Rebuild everything; alt screen never reflowed | Rebuild everything (TODO for lazy reflow), prompt-aware | Both are O(history); plan lazy reflow if scrollback is huge |
| Shaping | None | HarfBuzz, runs split at style/cursor/selection, position-independent run cache | Ghostty |
| GPU minimum | GL 3.3 → GLES 2 → GL 2.1 ladder, GLX then EGL | **GL 4.3 core**, EGL surfaceless, DMA-BUF to GTK | Alacritty's ladder |
| Frame pacing | vsync off, own refresh-rate timer, `glFinish` on X11 | Linux: none (draws on every wakeup) | Alacritty, plus adaptive pacing for remote |
| Remote X11 | Works via GLX/llvmpipe, full frames | Works via llvmpipe + `glReadPixels`, full frames | Neither |
| Tabs/splits | No (philosophy: use tmux/WM) | Yes: Adw tabs, immutable `SplitTree` | Ghostty's split tree, if you want native splits |
| tmux `-CC` | DCS swallowed, nothing visible | Protocol layer + per-pane `Terminal`; **no GUI** | Ghostty's protocol design, fix its gaps |
| Windows | ConPTY + GUI (winit/WGL) | ConPTY in core; no GUI | Alacritty's ConPTY lessons |
| Testing | Ref tests: record PTY bytes, compare grid JSON | Inline tests, AFL++ fuzz, esctest2, benchmarks, inspector | Both |

---

## 3. Architecture to aim for

```
                ┌───────────────────────────── core library (no GUI deps) ─────────────────────────────┐
                │                                                                                      │
 Backend ──────►│  Parser (state machine + fast paths) ──► Handler ──► Terminal state                  │
  (byte source  │      DCS sub-parsers: tmux, XTGETTCAP, DECRQSS, [sixel]       (screens, pages, pins) │
   + sink)      │      APC sub-parsers: [kitty graphics]                               │               │
  • PTY/ConPTY  │                                                                      ▼               │
  • tmux pane   │  Replies (DA/DSR/CPR/OSC queries) ──► written to Backend directly    RenderState     │
  • SSH channel │                                                               (dirty-row snapshot)   │
    (Windows)   │                                                                                      │
                └──────────────────────────────────────────────────────────────────────┬───────────────┘
                                                                                       │ frame = changed rows
                ┌──────────────────────────── frontend ────────────────────────────────▼───────────────┐
                │  Renderer interface:  begin(damage) / draw_row_bg / draw_glyph_run / scroll(n) / end │
                │     ├─ GPU backend (GL 3.3 core / GLES 3; later D3D11 or Vulkan)                     │
                │     └─ X11 backend (XRender glyphsets + XCopyArea + rects; XCB, async)               │
                │  Window/platform: X11 (XCB), [Wayland], Win32                                        │
                │  Input: key encoder (kitty + legacy), mouse, IME, clipboard, bindings                │
                │  Layout: windows / tabs / split tree  ◄── also driven by tmux layout notifications   │
                └──────────────────────────────────────────────────────────────────────────────────────┘
```

Design points behind this picture:

### 3.1 Keep a headless core

Both projects have one and both benefit: other projects embed it, it can be fuzzed,
and it can run esctest2 without a window (A§1.1, G§1.1, G§10). Rules worth copying:

- The core talks to the frontend only through an event/callback interface plus a
  write/resize sink.
- Colours stay **unresolved** (palette index / named / RGB) in the grid. Resolution
  happens at render time, so palette changes need no grid rewrite (A§4.1).
- Each thread gets its **own immutable copy of derived config** on reload, never a
  shared mutable config (G§9).

**Option worth evaluating:** adopt `libghostty-vt` as the core. It has a C API,
builds on Windows, is fuzzed and conformance-tested, and includes key/mouse/paste
encoders and the render-state API. It already contains the tmux protocol layer.
The costs are an unstable API, a Zig toolchain dependency, and that you'd inherit
its tmux gaps (§7.4). Even if you don't adopt it, use it as the benchmark.

### 3.2 Make "where bytes come from" an interface

Ghostty's `termio/backend.zig` was designed for more than one backend but only has
`Exec` (subprocess + PTY). Alacritty's `EventedPty` abstracts Unix vs Windows PTYs
only. You need three:

| Backend | Platforms | Read side | Write side | Resize |
|---|---|---|---|---|
| PTY (local shell; on Linux also the `ssh` binary) | Linux (main), Windows (secondary) | PTY master / ConPTY pipe | same | `TIOCSWINSZ` / `ResizePseudoConsole` |
| tmux pane | both | `%output %N …` lines from the control connection (unescaped) | `send-keys -H -t %N …` via the control connection | `refresh-client -C WxH` (window-level; see §7) |
| SSH channel | Windows only (main) | channel data | channel data | `window-change` request |

**Linux** needs only the first two. SSH is just a program running in the PTY, as in
any other terminal. That's the right call: OpenSSH already handles config, agents,
keys, `ProxyJump`, and `ControlMaster`, and Linux users expect exactly that behaviour.

**Windows** is where the embedded SSH client pays for itself. SSH sessions **bypass
ConPTY entirely**. ConPTY re-parses and re-emits the VT stream, and that is the root
of most Windows terminal fidelity bugs (A§2.3). Windows Terminal, PuTTY, and others
all fight this. Neither reference terminal embeds SSH; WezTerm and PuTTY do (see the
note at the end of §10).

The control connection for tmux `-CC` sits on top of whichever byte stream carries
tmux: a Linux PTY running `ssh host tmux -CC attach`, or on Windows an SSH channel
running `tmux -CC attach` directly. Keep the tmux layer unaware of which.

### 3.3 Query replies must not depend on the UI thread

Alacritty generates DA, DSR, and OSC colour-query replies on the PTY thread but sends
them to the UI thread, which writes them back to the PTY (A§1.5). A UI thread blocked
on an X11 round trip (clipboard, IME, window property) then delays every remote app
that probes the terminal. Over a slow X link that adds up fast. Ghostty sends replies
straight to its writer thread from the parse thread (G§2.2). Do that.

---

## 4. Threads, locking, data flow

Recommended model, a middle ground between the two:

- **Per terminal: one IO thread** that reads, parses under the lock, and writes.
  Ghostty's separate gather thread exists to work around macOS's ~1 KiB tty read cap
  (G§2.2). On Linux a 64 KiB–1 MiB read buffer on one thread is enough (A§1.3).
  Revisit if profiling shows producer stalls.
- **One render thread per window**, or one for all windows. Alacritty renders all
  windows on the UI thread, and had to disable vsync so N windows don't each block in
  swap (A§5.6). A separate render thread keeps input handling responsive while
  drawing, which matters more on a slow X connection.
- **UI/main thread** handles window-system events, input, and layout only.

Locking rules both projects converged on:

1. One mutex guards terminal state.
2. The renderer holds it **only to copy dirty rows**, then renders unlocked
   (A§1.3, G§4.8).
3. Make it fair. Either the IO side keeps reading into its buffer while the renderer
   holds the lock (Alacritty lease), or it yields between batches when the renderer
   signals demand (Ghostty). Plain mutexes starve the renderer under `cat bigfile`.
4. Cap work per lock hold. Alacritty uses 64 KiB of parse; Ghostty uses one batch.

Messaging rules:

- Use bounded, typed mailboxes with an async wakeup. Avoid closures. Keep small
  payloads inline (Ghostty's termio messages are ~40 B with 38 B inline data) (G§1.2).
- Coalesce resize (Ghostty: 25 ms) and wakeups. Many "data arrived" notifications
  should become one render.
- Time out synchronized output. Ghostty uses 1 s and Alacritty 150 ms. A buggy app
  must not freeze the display.
- **Resize order:** call `TIOCSWINSZ` *before* reflowing, under the same lock, so the
  shell's SIGWINCH redraw is never parsed against old dimensions (G§2.3; Alacritty
  does the same, A§4.5).

---

## 5. Parser and terminal state

### 5.1 Parser

- Use Paul Williams' DEC state machine (vt100.net). Both use it.
- Add a **ground-state fast path**: find the next ESC/control byte with memchr or
  SIMD, validate or decode UTF-8 in bulk, and hand whole printable runs to a
  `print_slice` routine (A§3.1, G§3.2). Keep a byte-at-a-time path as a test oracle
  and fuzz both paths against each other (G§3.2, G§10).
- **DCS and APC are not optional.** Make them pluggable sub-parsers chosen at `hook`
  time.
  - DCS `1000p` → tmux control-mode parser (§7).
  - `+q` XTGETTCAP and `$q` DECRQSS. Remote apps use these to discover capabilities
    when terminfo is missing.
  - Optional: sixel (DCS) and kitty graphics (APC).
  - Feed DCS/APC payloads **as slices, not bytes**. Ghostty dispatches tmux DCS bytes
    one at a time, which makes heavy tmux output slow (G§3.2, G§8.4).
- **UTF-8 inside DCS:** treat 0x80–0xFF inside DCS as payload, including 0x9C. tmux
  pane content is UTF-8, and a C1 ST byte is indistinguishable from a continuation
  byte. Ghostty changed its parse table for exactly this (G§3.1).
- **Bound every attacker-controlled buffer:** OSC length, DCS length (tmux line cap
  1 MiB in Ghostty), params (24–32), title stack, kitty keyboard stack, zero-width or
  grapheme length per cell, sync buffer. Alacritty added several caps only recently
  as DoS fixes (A§9).

Minimum sequence coverage for a modern terminal (local and over SSH): everything in A§3.2, plus OSC 7 (cwd),
OSC 133 (prompt marks), OSC 8, OSC 52, OSC 9/777 notifications, XTVERSION, DECRQM,
mode 2026 (sync), 2004, 1004, and 1006/1016 mouse. Add 2027 (grapheme) and 2048
(in-band resize) when the grid supports them.

### 5.2 Cells and pages

Ghostty's design is the better one to start from:

- **8-byte cell:** content (codepoint, or a flag meaning "grapheme in side table" or
  "bg colour only"), a 16-bit **style id**, wide-char state, and a few flag bits
  (G§4.3).
- **Interned styles per storage block**, ref-counted. A cell stores an id. Most
  terminal text uses a handful of styles.
- **Side tables** for rare data: grapheme tails and hyperlinks, keyed by cell
  position. Alacritty's `Option<Arc<CellExtra>>` is the same idea at pointer cost
  (A§4.1).
- **Row header flags** that may have false positives but never false negatives, such
  as "has styles", "has graphemes", "has links", "wrapped", "dirty". They let erase
  and clear on plain rows be a `memset` (G§4.3), and give you cheap per-row damage.
- **Rows point to cells by offset**, so IL/DL and scroll regions swap row headers
  instead of moving cells (G§4.2). Alacritty's ring of rows gets the same O(1)
  full-screen scroll (A§4.3).

Storage:

- Start with fixed-size blocks of rows that are **recycled** when the scrollback limit
  is hit (Ghostty pops the oldest page and reuses it as the new tail, G§4.5), so
  steady-state scrolling allocates nothing.
- Use **offsets instead of pointers** inside a block if you want cheap clone, snapshot,
  compression, or (for tmux reattach or session restore) serialisation (G§4.2).
- Set the scrollback limit in **bytes**.
- Use **tracked positions** ("pins") for anything that must survive mutation: cursor,
  viewport top, selection ends, search hits, image placements. Add generation
  counters on recycled blocks so stale references can be detected without
  dereferencing (G§4.5). Keep the number of pins small, because every mutation fixes
  them up.

### 5.3 Unicode

- Use a generated width table (Ghostty: 3-stage LUT built from Unicode data) rather
  than a generic library, so you control the Unicode version.
- **Store grapheme clusters per cell from the start**, with UAX #29 break checks
  gated by mode 2027 (G§4.7). VS16 can widen a cell after the fact and force a wrap.
- Width disagreements between your terminal, the remote `wcwidth`, and tmux's own
  width table **will** happen over SSH. tmux re-renders panes using its idea of
  width. Make the "legacy" (non-2027) behaviour match what xterm and tmux do, and
  test with `ucs-detect` (G§10).

### 5.4 Reflow and alt screen

- Reflow is the bug farm in both codebases: wrapped-row flags, wide chars at the
  edge, the deferred-wrap cursor, the viewport offset, and selection (A§4.5, G§4.5).
  Both rebuild all of history on a column change, which is O(scrollback).
- Plan for **lazy reflow** of off-screen history if you allow large scrollback.
  Ghostty has a TODO for exactly this.
- Don't reflow the alt screen. Alacritty truncates; full-screen apps redraw on
  SIGWINCH anyway.
- Write exhaustive tests before writing the reflow code.
- **tmux panes don't reflow locally.** tmux owns the pane content and resends it. A
  tmux pane terminal should resize without reflowing and let tmux repaint.

---

## 6. Rendering: two backends behind one interface

This is the requirement that diverges most from both reference terminals.

### 6.1 Why "GPU + llvmpipe" isn't good enough remotely

What happens today with `ssh -X host terminal`:

- **Alacritty:** GLX is tried first. Indirect GLX usually offers only old GL, so the
  context ladder fails unless `LIBGL_ALWAYS_SOFTWARE`/llvmpipe is used. With llvmpipe
  it renders on the remote CPU, clears and redraws every cell, and swaps the full
  window, followed by a `glFinish` (A§5.1, A§6.3).
- **Ghostty:** it can't export a DMA-BUF to a remote X server, so it falls back to a
  full `glReadPixels` on every frame, wraps it in a `GdkMemoryTexture`, and GTK sends
  the whole image. There is no frame cap on Linux (G§5.2, G§6.4).

A 1600×1000 window at 4 B/pixel is ~6.4 MB per frame. A cursor blink or one typed
character costs the same as a full repaint.

### 6.2 The X11 backend (classic, server-side)

This is how xterm, urxvt, and st stay fast over the network. The bytes sent per
update scale with *changed text*, not window size:

| Operation | X request | Network cost |
|---|---|---|
| New glyph first seen | `RenderAddGlyphs` to a server-side GlyphSet (once per glyph/size/style) | glyph bitmap, once |
| Draw a run of text | `RenderCompositeGlyphs8/16/32` | a few bytes per glyph |
| Cell backgrounds | `RenderFillRectangles` / `PolyFillRectangle` (coalesce runs of same bg) | a few bytes per run |
| Scroll N lines | **`CopyArea`** of the scroll region, then draw only the new rows | ~28 bytes + new rows |
| Cursor, underline, selection | small fills / glyphs | tiny |
| Fallback (no XRender) | core text or `PutImage` of dirty rects | larger, still damage-limited |

Rules for this backend:

- **Use XCB, not Xlib**, and never wait on a reply in the draw path. Intern atoms at
  startup in one batch. Make clipboard, IME position, and property reads
  asynchronous. Each synchronous call is a full network RTT on the UI thread
  (A§6.3).
- **Scroll detection must exist in the core.** The renderer needs to know "the
  viewport moved up N rows" rather than "every row is dirty". Neither reference
  terminal reports this to its renderer, because GPU rendering doesn't care. Add a
  scroll-delta field to your damage/RenderState.
- **Adaptive frame pacing.** Coalesce updates and cap the rate according to how fast
  the X server consumes requests. Ghostty's "latest frame wins" slot is the right
  shape: drop intermediate states and never queue them (G§5.4).
- Glyph rasterisation stays local (FreeType). Only glyph bitmaps cross the wire, once.
  Colour emoji need ARGB glyphsets, which XRender supports.
- MIT-SHM, DRI3, and Present are local-only. Detect them and use them when local, but
  never depend on them.

### 6.3 The GPU backend (local)

Copy the proven pieces:

- **Glyphs** as instanced quads from an atlas. Backgrounds either as their own
  instanced pass (Alacritty) or as one buffer indexed by a full-screen fragment
  shader (Ghostty) (A§5.2, G§5.3).
- **Procedurally drawn** box-drawing, block, Powerline, braille, and legacy-computing
  glyphs, so lines join exactly at any cell size (A§5.3, G§5.5). The X11 backend can
  reuse the same rasteriser and upload results as glyphs.
- **GL minimum around 3.3 core or GLES 3.0**, with Alacritty's fallback ladder and
  robust-context reset recovery (A§5.2, A§6.1). Ghostty's GL 4.3 + SSBO floor rules
  out some VMs, older iGPUs, and Mesa virtual GPUs (G§5.4).
- **Frame pacing:** use vsync or presentation feedback on Wayland. On X11 use
  Alacritty's refresh-phase timer plus `glFinish` to avoid a one-frame lag (A§5.6).
  Ghostty draws on every wakeup on Linux.
- **Upload only changed rows.** Ghostty rebuilds dirty rows on the CPU but re-uploads
  all buffers each frame (G§5.3). Where supported, use buffer-age or
  swap-with-damage so the compositor also gets partial damage.
- Skip drawing when the window is occluded or invisible (both do this).
- **Atlas eviction.** Both atlases only grow. With heavy CJK or emoji use, add LRU or
  generational eviction, or at least a reset when the atlas exceeds a budget.

### 6.4 Choosing a backend at runtime

Selection logic Ghostty and Alacritty both lack:

1. User override in config or on the CLI.
2. If `DISPLAY` has a host part (`host:0`, which includes `ssh -X`'s `localhost:10`),
   or the X server lacks DRI3/MIT-SHM, use the X11 backend.
3. Otherwise try the GPU path. If context creation fails, or `GL_RENDERER` reports
   llvmpipe/softpipe, fall back to the X11 backend.
4. **Failure must be visible and never fatal.** Ghostty's "no GL context" page is
   currently unreachable (G§6.4). Alacritty exits.

### 6.5 Fonts and shaping

- **Discovery:** fontconfig on Linux, DirectWrite on Windows. Use per-style fallback
  chains with negative-result caching (A§5.4, G§5.5).
- **Shaping** (HarfBuzz): decide now. If yes, follow Ghostty:
  - runs never cross rows;
  - break on style, font, selection edges, and the cursor;
  - force LTR;
  - cache shaping by a position-independent run hash. Shaping was once 96% of
    Ghostty's frame time (G§5.5).
- **Synthetic bold and italic** for fonts lacking those styles (Ghostty).
- **Bundle a fallback font set** (Ghostty embeds JetBrains Mono, Nerd Font symbols,
  and Noto Emoji), so remote or minimal hosts still render.
- **Font loading is slow.** Ghostty does fallback discovery synchronously on the render
  thread. With an X11 backend, glyph upload is an X request too, so cache both
  rasterised bitmaps and server-side glyph ids.

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
- **`%output %<pane> <data>`:** bytes below 0x20 and `\` are **octal-escaped**
  (`\033`). You must decode them. Ghostty currently does not (G§8.4); its field is
  commented `// unescaped`, but no decoder exists.
- **Commands** are written to the byte stream tmux is running on. On Linux that's the
  local PTY (for remote tmux, the PTY whose child is `ssh host tmux -CC attach`). On
  Windows with embedded SSH, it's the SSH channel.

### 7.2 What to reuse from Ghostty's design (G§8.3–8.7)

- DCS-driven entry with a capped line parser (1 MiB).
- Typed notification records.
- Block terminators matched strictly (`%end` with numeric fields), so pane content
  that happens to start with `%end` doesn't end a block.
- **One command in flight**, with replies matched to a FIFO queue.
- `-F` format strings generated from a typed field list and parsed back into a
  struct. This removes a class of parsing bugs.
- Layout string parser with checksum verification.
- **Pane state reconstruction** on attach:
  - `capture-pane -p -e -q -S - -E -1` for history, plus `capture-pane -p -e -q` for
    the visible area;
  - do both for normal and alternate screens (`-a`);
  - then `list-panes -F` for cursor, modes, mouse modes, scroll region, and tab stops.

### 7.3 What Ghostty didn't build, which you need

1. **PTY-less terminal surfaces** whose backend is "tmux pane %N" (§3.2). Each gets
   its own terminal state and renderer. Input encodes keys exactly as for a local
   terminal and sends them as `send-keys -H -t %N <hex bytes>`, which is safe for any
   byte. Mouse reports go the same way.
2. **Layout mapping:**
   - A tmux window becomes a tab.
   - The tmux layout tree becomes your split tree. Ghostty's immutable `SplitTree`
     (flat node array, u16 handles, zoom) is a good model (G§6.1).
   - Window ids (`@N`) and pane ids (`%N`) are stable and never reused.
3. **Sizing:**
   - The client size is set with `refresh-client -C WxH`. On tmux 3.2+, per-window
     sizes use `refresh-client -C @win:WxH`.
   - Native window resizes must become tmux size requests. tmux then sends
     `%layout-change`, and you apply pane sizes **from tmux**, not from your own
     split math. Expect rounding differences (tmux uses 1-cell dividers) and decide
     how to draw them.
4. **Flow control for slow links:**
   - Enable `refresh-client -f pause-after=N` (tmux 3.2+).
   - Handle `%extended-output` (it includes a latency field), `%pause`, and
     `%continue`.
   - Without this, a pane spewing output over SSH can flood the control channel and
     starve the other panes.
5. **Attach race:** output that arrives for a pane before its capture has been
   processed must be buffered and replayed afterwards, or dropped if the capture
   already covers it. Ghostty lists this as a TODO (G§8.7).
6. **Threading:** in Ghostty all pane terminals live inside the parent terminal's
   stream handler, under that terminal's lock (G§8.8). Give the control connection
   its own owner object, which demultiplexes `%output` to per-pane terminals, each
   with its own lock and render wakeup.
7. **Performance:**
   - Ghostty compiles a regex per notification line and dispatches DCS bytes one at a
     time.
   - Use a hand-written line splitter and slice-based DCS delivery instead.
   - `%output` is the hot path; unescape straight into the pane's parser.
8. **UX decisions:**
   - What the originating terminal shows while in control mode (iTerm2 shows a small
     status window with detach/kill buttons).
   - Clean detach (`detach-client`) and reattach.
   - Guarding against `tmux -CC` inside a tmux pane.
   - What "scrollback" means (yours, filled from `capture-pane`, vs tmux copy mode).
   - Version detection (`display-message -p '#{version}'`) and graceful degradation
     on older tmux.
9. **Testing:** record real control-mode sessions, including over high-latency SSH,
   and replay them in tests. This is Alacritty's ref-test idea applied to tmux
   (A§9).

### 7.4 Should you build it on libghostty-vt?

- **For:** the protocol layer, viewer state machine, format helpers, and layout parser
  exist and are tested, with about 1,100 lines of tests in `viewer.zig`.
- **Against:**
  - the octal unescape bug;
  - missing flow control;
  - it runs inside the parent terminal's lock;
  - the API is unstable;
  - its assumptions come from reading tmux source as of December 2025 and aren't
    documented as stable (G§8.7).

A reasonable plan is to port its *design* and test cases rather than depend on it,
unless you adopt libghostty-vt as your whole core anyway.

---

## 8. Remote-shell concerns

These apply on both platforms: on Linux whenever the user runs `ssh` inside the
terminal, and on Windows for nearly every session. The embedded-client-only concerns
for Windows are in §10.

| Concern | What the reference terminals do | Recommendation |
|---|---|---|
| Remote lacks your terminfo | Alacritty uses `TERM=alacritty` only if the entry exists *locally*. Ghostty's `+ssh` installs terminfo remotely via `tic`, or falls back to `xterm-256color` + `COLORTERM` (A§2.1, G§2.6) | Default `TERM=xterm-256color`-compatible behaviour. Ship an install helper. Answer XTGETTCAP so modern apps don't need terminfo. On Windows the embedded client sets `TERM` in its `pty-req`, so it can pick per host |
| Clipboard from remote vim/tmux | OSC 52. Alacritty: copy-only by default, ignored when unfocused. Ghostty: write allowed, read asks (A§7.4, G§7.5) | Write allowed with a size cap, read asks. Handle large base64 payloads efficiently |
| Query latency | Alacritty routes replies via the UI thread | Reply from the IO thread directly (§3.3) |
| Paste over SSH | Both strip ESC in bracketed paste. Ghostty warns on newline or `ESC[201~` (A§7.3, G§7.5) | Do both |
| Shell integration | Ghostty auto-injects OSC 133/7 locally only. Alacritty ignores those OSCs | Support OSC 7/133 when the remote shell emits them. Offer remote snippets |
| Output bursts | Ghostty's gather/parse pipeline exists for throughput. Fine on Linux with one thread | Handle sync output (2026). Coalesce redraws so bursts don't flood a remote X display |
| Hyperlinks to remote files | OSC 8 supported by both. OSC 7 gives cwd + hostname | Use the hostname in OSC 7/8 to decide whether a path is openable locally |

---

## 9. Input

- **Keyboard:** use physical key (W3C code) + unshifted codepoint + mods (G§7.1).
  - Implement the **kitty keyboard protocol** with a flag stack per screen. Both do;
    the stack swaps with the alt screen.
  - Implement legacy xterm encodings and `modifyOtherKeys`. Ghostty ported its tables
    from foot.
  - Alacritty makes legacy sequences **default bindings** that users can override,
    which is a neat trick (A§7.1).
- **X11 modifier correctness:** use XKB state-notify events (Ghostty peeks the queue,
  G§6.3). Alacritty's CHANGELOG is full of X11 modifier desync fixes.
- **IME:** send every key press and release through the IME, attach commits that occur
  inside a key event to that event, and draw preedit inline at the cursor. Beware
  different commit/preedit-end ordering between ibus and others (G§7.5, A§6.5).
- **Mouse:** support SGR (1006) and SGR-pixels (1016). Send motion only on cell
  change. Shift bypasses mouse reporting.
- **Bindings:** a trie of key sequences, plus key tables (modes) and
  "performable/unconsumed" flags. Ghostty's model resolves real conflicts with TUI
  apps (G§7.4). For a tmux-centric terminal, consider a native prefix-key mode.

---

## 10. Windows later: decisions to make now

- **ConPTY** (A§2.3, G§2.4):
  - It needs threads for its anonymous pipes.
  - `ClosePseudoConsole` blocks until output is drained, so get the drop order right.
  - Ignore 0×0 resizes from minimising.
  - Optionally load a newer `conpty.dll`/OpenConsole from Windows Terminal.
  - ConPTY rewrites the VT stream.
- **Embedded SSH** avoids ConPTY for the main use case (§3.2). That may be the most
  important Windows decision, and it affects the backend interface now. It exists
  only in the Windows build.
- **What the embedded client has to cover** (users will compare it to OpenSSH and
  PuTTY):
  - **Protocol library:** most SSH libraries (libssh, libssh2, and native ones in
    most languages) handle transport, auth, channels, PTY requests, `window-change`,
    and agent forwarding. Few parse `~/.ssh/config` or manage `known_hosts` with
    OpenSSH's semantics. Expect to write or adopt those separately.
  - **Agents:** the Windows OpenSSH agent (named pipe `\\.\pipe\openssh-ssh-agent`)
    and Pageant. Both speak the standard agent protocol.
  - **Host keys:** a first-connect prompt, then a mismatch warning that is hard to
    click through. Reuse `%USERPROFILE%\.ssh\known_hosts` so the CLI and the app agree.
  - **Config:** read `%USERPROFILE%\.ssh\config` for `Host`, `HostName`, `User`,
    `Port`, `IdentityFile`, and `ProxyJump`. Users already have it.
  - **Keepalives and reconnect:** laptops sleep. Detect a dead connection, show it in
    the pane, and offer reconnect. With tmux `-CC` that becomes a clean reattach.
  - **Connection sharing:** several tabs to the same host should share one SSH
    connection (one channel each), like OpenSSH's `ControlMaster`. This also makes
    new tabs instant.
  - Later: port forwarding and SFTP drag-and-drop. Keep them out of v1.
- **Local shells** (PowerShell, cmd, WSL) still go through ConPTY. WSL distros can
  also be reached over SSH to avoid ConPTY, but that's a user choice.
- **Rendering:**
  - GL on Windows means WGL. Alacritty creates the window before the GL display
    because WGL needs an HWND (A§6.1).
  - D3D11 is the native, most reliable path.
  - Keep the renderer interface backend-neutral so D3D11 can be added; the X11
    backend already forces that.
- **Fonts:** DirectWrite. Ghostty uses FreeType on Windows; crossfont uses DirectWrite.
- **Memory:** `VirtualAlloc` replaces `mmap` for Ghostty-style pages (G§4.2).

**More reference material for Windows.** Neither Alacritty nor Ghostty has a full
Windows story with embedded SSH. Codebases worth studying before the Windows phase:

- **Windows Terminal** (`microsoft/terminal`): ConPTY and OpenConsole source (the
  thing that rewrites your VT stream), the AtlasEngine D3D11/DirectWrite renderer,
  and Win32 IME/input/DPI handling.
- **WezTerm** (`wezterm/wezterm`): cross-platform, with a built-in SSH client
  (`wezterm ssh`, SSH domains), `ssh_config` parsing, and its own multiplexer. It is
  the closest existing match to the Windows product.
- **PuTTY**: the reference for what Windows SSH users expect (host-key UX, Pageant,
  saved sessions). Its code is old C, so read it for behaviour, not structure.

---

## 11. Testing and tooling to build early

1. **Replay tests:** record raw PTY bytes and compare serialised grid state (Alacritty
   `--ref-test`, A§9). Extend this to tmux control-mode recordings.
2. **Conformance:** run esctest2 against the headless core (G§10).
3. **Fuzzing:** fuzz the parser, OSC/DCS sub-parsers, the tmux line parser, and the
   full stream. Fuzz the SIMD and scalar paths against each other.
4. **Benchmarks:** use deterministic synthetic input (Ghostty's `ghostty-gen`) plus
   `hyperfine`. Measure throughput (`cat` large files), latency (keypress to pixel),
   and remote X bytes per update (`xtrace` or `x11trace` will show request volume).
5. **Integrity checks:** debug-mode assertions over page and row invariants (Ghostty
   `assertIntegrity`). Fault injection for OOM paths.
6. **Inspector:** an in-app view of recent PTY bytes and parsed events per terminal.
   Ghostty's is a strong debugging aid, and you'll want one for tmux control mode.

---

## 12. Decisions to make up front

| Decision | Why it can't wait | Suggested default |
|---|---|---|
| Cell content model (cluster vs `char`) | Retrofitting broke Alacritty's ligature and emoji plans | Codepoint + grapheme side table, 8-byte cell |
| Shaping (HarfBuzz) yes/no | Changes glyph cache keys and renderer run structure | Yes, with cursor-aware run splitting; allow disabling ligatures |
| Backend abstraction (PTY / tmux pane / SSH) | tmux panes need it on both platforms, embedded SSH on Windows; Ghostty never built it | Define it before writing the IO loop; SSH backend built only for Windows |
| Renderer interface with damage + scroll deltas | Required by the X11 backend; neither reference has scroll deltas | Row-granular damage plus explicit scroll ops |
| GPU API floor | Ghostty's GL 4.3 excludes some hardware | GL 3.3 core / GLES 3; D3D11 on Windows |
| Threading model | Hard to change after state ownership is set | IO thread per terminal, render thread, UI thread, one fair lock |
| Core as a separate library | Enables testing, fuzzing, reuse | Yes; consider libghostty-vt vs your own |
| Scrollback limit units and reflow strategy | Affects page design and resize cost | Bytes; plan lazy reflow |
| Native tabs/splits | tmux `-CC` needs them anyway | Yes, as an immutable split tree |
| Windows SSH strategy | Determines whether ConPTY is on the main path | Embedded SSH backend on Windows; Linux uses the system `ssh` in a PTY |

### Properties the implementation language must support

The language is deliberately undecided. These are the requirements the design above
puts on it, to check any candidate against:

- **Compact, pointer-free hot data.** The parser and grid want 8-byte cells and
  offset-addressed pages in large flat buffers. A garbage-collected language must let
  you keep these out of the GC's scan set (flat byte or integer arrays), and you
  should benchmark pause times during `cat`-heavy output.
- **Cheap calls into C libraries**, or native equivalents. FreeType, HarfBuzz,
  fontconfig, GL/D3D11, DirectWrite, and possibly libghostty-vt or an SSH library are
  C/C++/COM. If foreign calls are expensive, batch them per row or run, not per cell.
- **Asynchronous X11 protocol access.** XCB-style request/reply cookies, including
  the RENDER extension. Some languages have pure implementations of the X protocol,
  which avoids a C dependency for the remote X11 backend.
- **Real threads with shared memory** for the IO/render/UI split and a fair lock (§4).
- **Win32 and COM interop** for ConPTY, D3D11, DirectWrite, TSF (IME), and named
  pipes (agents).
- **A mature SSH library** for the Windows build, or the willingness to own one.
- **Fuzzing and benchmarking tools** (§11).

### A sensible build order

1. Headless core: parser, terminal state, and replay tests. Fuzz from day one.
2. Linux PTY backend plus the **X11 server-side renderer** (XCB, XRender,
   `CopyArea`). It works both locally and remotely, and makes damage and
   scroll-delta tracking honest from the start.
3. Input (kitty and legacy), clipboard and OSC 52, IME.
4. tmux control mode: protocol layer, then PTY-less pane surfaces, then the split
   tree and tabs.
5. GPU renderer for local high-DPI and high-throughput use, selected at runtime.
6. Windows: embedded SSH backend first (it's the main use case and skips ConPTY),
   then D3D11 or GL renderer and DirectWrite, then the ConPTY backend for local
   shells.

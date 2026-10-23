# Plan: visiterm for Linux, written in Geng

Status: **plan, 2026-10-23; Gilbert's first answers the same day (§9). Nothing is
built.** It turns [`synthesis.md`](synthesis.md)
into work, for the Linux product only, in Geng (`~/prj/geng-lang`, the Gren fork with
a native C backend). The Windows product, the embedded SSH client and ConPTY are out
of scope.

The plan has two goals, and they pull in different directions:

1. **A terminal Gilbert uses every day.** It has to be reliable. A crash closes every
   shell in the window, so a crash is the worst outcome.
2. **Find out what Geng lacks.** This is the "difficult native application" that
   geng-lang's D797 puts after refinement types and before the self-hosted front end.
   Each gap it finds is recorded in geng-lang with a decision number, like any other
   Geng work.

Where the two goals conflict, the first wins. A missing Geng feature is either built
in Geng or worked around in C, whichever is the right design. A gap is never hidden
to make the result look good.

Citations: "S§4" is §4 of `synthesis.md`, "C§10" is §10 of `cjk-and-thai.md`. Geng
references name the geng-lang document and decision (`ffi.md` F4, D757).

---

## 0. The short version

- **Geng can already do more than expected.** A package can carry C code and
  `@extern(c, …)` declarations (geng-lang `ffi.md` F7). The native runtime has a
  `poll(2)` event loop that a C row can register any fd with (`geng_io_wait`). C can
  push events into a Geng mailbox (`Source`, `geng_source_emit`). A pure C call costs
  about 1 ns. A Geng package opened a real connection to the X server through libxcb
  today (§1).
- **Gren's "ports can't be in packages" problem is gone.** Geng has no ports. The
  tvision experiment's port record, its JSON protocol and its JS layer are all
  unnecessary. A binding is one Geng package with its C beside it (§8).
- **The gaps are concrete.** None of them blocks starting. The biggest are:
  - **No way for a package to declare the C libraries it links**, and the flags that
    exist land in the wrong place on the link line (§1, G1).
  - **One thread.** Geng's native runtime runs every task on one OS thread, and
    multi-threading is not scheduled. The plan designs for that and does not wait for
    it (§3.1, G5).
  - **No signal handling, no monotonic clock in `core`, no PTY.** These are small
    (G2, G6, the PTY package in §5).
  - **No compiler check of a C row against its declaration.** A wrong type in a C row
    corrupts memory silently. That is not acceptable for this app (G8).
  - **The release binary must run on RHEL8** (decided, Q4). That means glibc 2.28,
    kernel 4.18 and 2018's HarfBuzz, and Geng's `os` package currently needs pidfds
    (§1.1, G10).
- **The terminal core is written in Geng, not adopted.** The core is the hardest pure
  code in the app and the part most worth testing Geng on. libghostty-vt is the
  oracle for a differential gate, in the style geng-lang already uses for its
  compiler (§6, Q2).
- **An immutable grid is fast enough to start.** The probe grid of immutable rows
  takes about 160 MB/s of `ls`-like output. Its worst case, one cell per cursor move,
  costs about 120 ns per cell (§1). Immutable rows also give the renderer its
  snapshot and damage tracking for free (§3.3).
- **Six phases** (§6), each starting as a measured survey, as geng-lang's work does.
  The terminal becomes usable for daily work at the end of phase 3.
- **Gilbert answered three of the eight questions** on 2026-10-23: RHEL8 is required,
  one process per window, and Geng-side tracking lives in geng-lang's register
  (D888, D889). The rest and six new ones are in §9.

---

## 1. What was measured, 2026-10-23

Machine: Linux Mint 22.3, kernel 6.8, 16 threads, 59 GB. geng-lang at `218cdf09`
and the compiler fork at `6d12eb99`, with the native passes `harness/run.py`'s
`geng-c` target sets, at `-O2`. The probes are in [`../probes/geng/`](../probes/geng/)
with their build scripts. Every run is shown.

| Probe | Result |
|---|---|
| A pure C row (`@externPure`), 100 M calls in a Geng loop | 100, 101, 102, 106 ms: **about 1 ns a call** |
| A `Task` C row that answers at once, 10 M calls chained with `andThen` | 332, 332, 336, 341 ms: **about 33 ns a call** |
| A C row calling libxcb: `xcb_connect`, count the screens, disconnect | **Works**: "xcb: 1 screen(s)", against `DISPLAY=:0`. It needed two workarounds, below |
| Grid, workload 1: 200,000 `ls`-like lines with two SGR sequences each, 24.3 MB, into a 160×50 grid of immutable rows (`Array (Array Int)`) | 148, 149, 149, 150, 151, 151, 151, 152, 154 ms: **about 160 MB/s** |
| Grid, workload 2: 2,000,000 single cells, each after a CUP, 18.3 MB | 234, 236, 236, 236, 237, 238 ms: **about 118 ns a cell**, a full row copy each |
| The same grid probe on node | Not measured: the build succeeded but the program printed nothing on the node runtime, and it was not pursued. Native is the target |

**The two workarounds for libxcb**, which are G1's evidence:

- devbox's clang is a Nix toolchain and does not search `/usr/include`, so
  `#include <xcb/xcb.h>` fails. The probe was built with the system gcc instead
  (`GENG_CC=/usr/bin/gcc`).
- `GENG_CFLAGS` is placed **before** the generated C and the package's `src/Ext/*.c` on
  the compiler's command line. A `-lxcb` there is dropped by the linker as unneeded,
  and every xcb symbol is undefined. `-Wl,--no-as-needed` ahead of it works.

**What the grid numbers do and don't say.** The probe has no style table, no wide
characters, no graphemes, no scrollback, no wrapping and no damage tracking. A real
core does more work per byte, so these numbers are a ceiling for this
representation. They show that the representation is not obviously too slow. They
do not show that it is fast enough. Phase 1 measures the real core against the
reference terminals on the same inputs (§6, phase 0 item 7).

**Also read, not measured** (geng-lang `docs/user/native.md`):

- Every task runs on one thread, and `Task.parallel` is `Task.concurrent` natively.
- The collector is a copying nursery in front of conservative, non-moving Boehm.
  Marking stops the program. **Pause times for a large interactive heap were never
  measured** (phase 0 item 6).
- `SIGINT` and `SIGTERM` end the program at once, and release handlers don't run.
- Regular-file reads run in place and stall every task (1 ms for 1.3 MB cold).
  Pipes, sockets and FIFOs wait in the scheduler.
- An executable built by devbox's toolchain is tied to the Nix glibc. One built by the
  system compiler links the system glibc.
- `os` starts children with pidfds, which needs Linux 5.4.

### 1.1 RHEL8, measured in a container

Gilbert's answer to Q4: visiterm must run on RHEL8 too, while development stays on
Mint with devbox (geng-lang D889). An AlmaLinux 8 container (`podman`,
`almalinux:8`, 2026-10-23) shows RHEL8's userland. It can't show RHEL8's kernel,
which is 4.18. §9 asks Gilbert for what only a real host shows.

| Component | RHEL8 (AlmaLinux 8, with EPEL) | On this Mint machine | What it means |
|---|---|---|---|
| glibc | 2.28 | 2.39; devbox's 2.42 | A release must be built against 2.28 |
| HarfBuzz | 1.7.5 (2018) | 8.3 | Too old to match Mint's shaping. Bundle a pinned HarfBuzz (Q12) |
| FreeType | 2.9.1 | 2.13 (pkg-config 26.1.20) | Bundle a pinned FreeType with it |
| fontconfig | 2.13.1 | 2.15.0 | System's is fine |
| libxcb | 1.13.1 | 1.15 | System's is fine. Don't use anything newer than 1.13's protocol set |
| libxkbcommon, -x11 | 0.9.1 | 1.6.0 | System's is probably fine; check the APIs used against 0.9 |
| xcb-util-renderutil, -keysyms | 0.3.9, 0.4.0 | present | Fine |
| xcb-imdkit | **not packaged**, not in EPEL | runtime only | Bundle it |
| fcitx5 | **not packaged** | — | The RHEL8 IME is **ibus 1.5.19** |
| libthai | 0.1.27 | runtime only | Fine |
| Mesa EGL | 23.1.4 | — | GLES 3 possible locally; irrelevant over `ssh -X` |
| Noto Sans CJK, Noto Sans Thai | packaged (2023, 2016) | — | Fallback fonts can come from the system, or be bundled (Q13) |
| **tmux** | **2.7** | 3.4 | Before 3.2's per-window `refresh-client -C @win` and `pause-after` flow control (S§7.3 items 3 and 5). Phase 4 has to degrade for it (Q11) |

---

## 2. What the design asks of a language, and what Geng gives

S§12 lists what the design asks of the implementation language. Here is each item
against Geng today. "Built" means it exists in geng-lang and a gate runs it.

| S§12 asks for | Geng today | What this plan does |
|---|---|---|
| Compact, pointer-free hot data, kept out of the GC's scan | `Bytes` and `String` data are pointer-free and Boehm does not scan them (built). No user-visible mutable buffer: `Bytes` is immutable and its transient is private to `core` | Start with immutable rows (§3.3). Measure in phase 1. A mutable buffer API is a Geng decision for later, taken only if the measurements need it (G4) |
| Cheap calls into C | ~1 ns pure, ~33 ns as a `Task` (§1) | Batch per frame and per run anyway: one display list per frame, one shaping call per run (§3.4) |
| Asynchronous X11 protocol access, RENDER included | libxcb from a C row works. The X connection's fd can wait in the scheduler's `poll` | XCB in C rows; event decoding and all decisions in Geng (§3.4) |
| Real threads with shared memory | **One thread.** A C thread can wake the loop only by writing to an fd the loop polls | One event loop, as PuTTY, xterm and st do. Blocking C work runs on C threads that answer through an fd (§3.1, G5) |
| Win32 and COM interop | — | Out of scope |
| A mature SSH implementation | — | Out of scope (Linux runs `ssh` in a PTY, S§3.2) |
| Fuzzing and benchmarking tools | No fuzzer for Geng code. geng-lang has a strong differential-harness culture | Fuzz the core as a `runtime = "host"` library under libFuzzer. Differential gate against libghostty-vt (§7) |

---

## 3. The architecture in Geng

### 3.1 One event loop

Geng's native runtime runs every task on one thread, and a multi-threaded runtime is
not scheduled (geng-lang `concurrency-native.md` §N1: "not scheduled, and not a
decision record"). The synthesis recommends an IO thread per terminal plus a render
thread (S§4). This plan does not wait for threads. It uses PuTTY's model instead
(P§0: "Everything is single-threaded"), which PuTTY's GTK front end, xterm and st
also use:

```
                         one OS thread: Geng's scheduler
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  ppoll() over: each PTY master fd, the X connection fd, timers, eventfds     │
 │      │ C rows emit into one Source Event                                     │
 │      ▼                                                                       │
 │  loop: Source.nextPrim (drain a batch) ─► update : Event -> Model -> Model   │
 │      │   PTY bytes ─► [EUC-KR filter] ─► Vt.feed ─► replies written at once  │
 │      │   X events  ─► input encoder / IME / selection / layout               │
 │      ▼                                                                       │
 │  when a frame is due: view : Model -> DisplayList (Bytes) ─► one C call      │
 └──────────────────────────────────────────────────────────────────────────────┘
        C threads (font fallback discovery, …) answer through an eventfd
```

Why this is acceptable, and what has to be measured to keep it acceptable:

- **No locks at all.** S§4's lock rules (fair locks, copying dirty rows under the lock,
  capping work per hold) exist because the parser and the renderer share mutable
  state. Here state is immutable and only one thread touches it. The renderer reads
  a snapshot that cannot change underneath it.
- **Query replies never wait on the UI** (S§3.3). A reply is written in the same turn
  that parsed the query, so nothing can stand between them.
- **The fairness rules still apply, as a per-turn budget.** Parse at most 128 KiB per
  pane per turn (WT's figure, S§4), then let input and paint run. Coalesce wakeups
  into one frame. Use a paint cooldown (PuTTY's 20 ms, S§6.2). Time out synchronized
  output.
- **The risks are GC pauses and render cost**, since either one stalls input. Phase 0
  measures pause times. Phase 2 measures frame cost. If either is too high, the fix
  is a design decision recorded in geng-lang, not a quiet workaround. The options
  are incremental marking, a smaller heap, or rendering on a C thread fed by the
  display list.
- **Blocking C work goes on C threads.** fontconfig fallback queries can take
  milliseconds, and S§6.5 wants them asynchronous anyway. A C row starts a thread, the
  thread writes its answer and an eventfd, and the loop picks it up. That works
  today. G5 proposes making it a runtime facility so that every package doesn't
  write it again.

### 3.2 What is Geng and what is C

The rule: **C does what only C can do** (call a library, own a pointer, hold a
pixel buffer). **Geng does everything that decides something.**

| Part | Language | Notes |
|---|---|---|
| VT parser, screen, modes, styles, scrollback, reflow, replies | Geng, pure | The core, `Vt.feed : Bytes -> Terminal -> { terminal, replies, events }`. No effects, so it runs headless, replays and fuzzes |
| Width and grapheme rules, SARA AM's cell (S§5.3) | Geng, pure | `core` has `Unicode.Grapheme`, a streaming UAX #29 state machine on UCD 17.0.0. Width tables are generated the way `core`'s are (`scripts/unicode-tables.py`) |
| EUC-KR / CP949 codec and the filter pair (S§3.4, C§10) | Geng, pure | A separate package, as geng-lang `m3-os.md` §OS22 says a codec must be |
| Key, mouse and paste encoding (S§9) | Geng, pure | In the core, so every front end sends the same bytes (S§3.1) |
| tmux control mode (S§7) | Geng, pure | Line parser, `%begin` matching, layout parser, octal unescape |
| Layout, tabs, split tree | Geng, pure | |
| Renderer: diffing, run building, damage, scroll detection | Geng, pure | Output is a display list (§3.4) |
| Config | Geng | TOML through `gilramir/gren-toml`, already vendored in geng-lang. CLI through `gilramir/gren-argparse` |
| PTY: `openpty`, fork and exec, `TIOCSWINSZ`, exit status | C rows | The child side has to be C, because only async-signal-safe calls are allowed between `fork` and `exec` |
| X11: connection, window, events, XRender, `CopyArea`, selections, XKB | C rows (libxcb) | Thin. Events cross as their raw 32-byte xcb form and Geng decodes them with `Bytes.Decode` |
| Keyboard state and keysyms | C rows (libxkbcommon, xkbcommon-x11) | |
| IME | C rows (xcb-imdkit, XIM) | The ordering rules of S§9 and C§7.4 are Geng |
| Fonts | C rows (fontconfig, FreeType, HarfBuzz) | Glyph bitmaps never cross into Geng (§3.4) |
| GPU renderer (phase 5) | C rows (EGL, GLES 3) | Executes the same display list |
| Thai word selection (C§8) | C row (libthai) | Optional; falls back to "one script run is one word" |

### 3.3 The grid: immutable rows

Each row is an immutable value. Writing a run of text makes a new row and shares
every other row. The probe in §1 measured this at about 160 MB/s on simple output.

What it buys:

- **The render snapshot is free.** S§4 copies dirty rows under a lock. Here the
  renderer holds the previous frame's rows, and a row that hasn't changed is the
  same object (S§5.2's "one dirty-tracking mechanism"). A sequence number per row is
  still useful, because comparing objects by identity isn't a Geng operation.
- **Scroll deltas are a value.** The core records "the region scrolled up N rows"
  when it does it, so the X11 renderer can issue one `CopyArea` (S§6.2: "Scroll
  detection must exist in the core").
- **Replay and testing are exact.** A terminal state is a value that can be compared
  and printed.

What has to be designed in phase 1 rather than copied: Ghostty's 8-byte cell with a
style id and side tables (S§5.2) maps to an `Int` or `Int64` per cell plus per-row or
per-page tables. Scrollback in **bytes**, with cold rows compressed to a string plus
attribute runs (WezTerm's scheme, S§5.2), suits immutable rows well. Whether a row is
an `Array Int` or a `Bytes` is measured, not guessed.

If the real core is too slow on immutable rows, the question for Geng is a mutable
buffer that the refinement checker or a linearity rule keeps safe (G4). That is a
language decision, and it waits for the numbers.

### 3.4 The display list and the C side of rendering

The tvision experiment's best idea was sending a *description* and diffing it in one
place (tvision `docs/native.md`). The same idea works one level down. Each frame, Geng
computes a display list from the previous frame and the current snapshot:

```
begin(damage rows, scroll ops) · fill(rect, colour) · glyphs(run of (glyph id, x, y), colour)
· copy(rect, dy) · cursor(…) · end
```

It encodes the list as `Bytes` and hands it to **one** C call per frame. The X11 C
side turns it into XRender and core-protocol requests, and the GPU C side (phase 5)
into instanced quads. That gives:

- one foreign call per frame, so foreign-call cost doesn't matter;
- a recorded display list is a deterministic repaint test (PuTTY's `fuzzterm`, S§11
  item 6), and its size per frame approximates the X11 bytes per update;
- both renderers share the decisions: runs, overhang and ink extents (C§4.3), what to
  redraw.

Glyphs: HarfBuzz shapes a run in a C row and returns glyph ids, clusters and offsets
as `Bytes`. FreeType rasterises inside C and uploads straight into the X server's
GlyphSet or the GPU atlas, so bitmaps never cross into Geng. Geng keeps the cache
keys, the LRU and the eviction decisions (S§6.2: "Bound server-side glyph sets",
C§6).

### 3.5 Processes and windows

A crash ends the process. If one process held every window, one crash would close
every shell Gilbert has open. **Decided (Q6, 2026-10-23): one process per top-level
window**, for isolation, at the cost of a fresh start (fonts, config) per window.
Tabs and splits inside a window share a process, since tmux `-CC` needs that.

---

## 4. Changes to Geng this needs

Each item is a proposal. When Gilbert decides one, it gets a geng-lang decision number,
a survey section where it needs one, and the usual gates. They are listed in the
order the work meets them.

**G1 · A package declares the C libraries it links.** Today a package's
`src/Ext/*.c` is compiled with no include paths and no libraries of its own, and the
only lever is the application builder's `GENG_CFLAGS`, which lands before the objects
(§1). Proposal: a `[native]` table in a package's `geng.toml` naming `pkg-config`
modules (`pkg-config = ["xcb", "xcb-render"]`). The compiler runs `pkg-config` once
per build, adds `--cflags` to that package's C compile and appends `--libs` **after**
every object. A missing module is a build error that names the package and the
module. This also needs a decision on **where libraries come from**:

- devbox's Nix toolchain, with the libraries in visiterm's own `devbox.json`, so a
  build is reproducible; or
- the system compiler and system libraries, which is what a release build for
  RHEL8 needs anyway (G10).

The recommendation is both: Nix for development and the gates, and a documented
system-toolchain build for releases.

**G2 · Signals as events.** `SIGTERM` and `SIGHUP` must close the terminal's shells
in order, and today they end the program with no release handlers run. Proposal: an
`Os.Signal` module (or package) whose rows block a signal, read it from a
`signalfd` in the scheduler's `poll`, and emit it into a `Source`. `SIGCHLD` isn't
needed, because `os` already waits on pidfds.

**G3 · No finalizers; resources are owned by name.** X resources, fonts and PTYs are
C objects. Geng has no finalizers, and this plan doesn't ask for any. Long-lived C
objects live in C tables, keyed by ids that Geng chooses, and are freed by explicit
rows. This is tvision's rule ("Name long-lived things"). The app's whole lifetime
sits inside `Task.bracket`. A debug build counts live C objects so that a soak test
can show the counts stay flat.

**G4 · A mutable byte buffer, only if phase 1 needs one.** See §3.3. The decision is
deferred to the measurements.

**G5 · Answering from another thread.** The pattern in §3.1 (a C thread does
blocking work and wakes the loop through an fd) works today, but each package would
write its own eventfd and queue. Proposal: a runtime call such as
`geng_answer_from_thread(wait, …)` backed by one eventfd and a locked queue, so a row
can complete its `Task` from any thread. That is a small, self-contained step toward
what `concurrency-native.md` explores, without a threaded scheduler.

**G6 · A monotonic clock in `core`.** It is registered already. Frame pacing, the
paint cooldown, the sync-output timeout and keepalives all need it.

**G7 · A GC pause budget.** Phase 0 measures pauses with a heap like visiterm's:
100k lines of scrollback in several panes, during `cat` of a large file. The plan's
target is that no pause exceeds one frame (16 ms), with 4 ms as the goal. Whatever is
measured is written down, and the fix, if one is needed, is a geng-lang decision.

**G8 · The compiler checks each C row against its declaration.** `ffi.md` F1 says the
compiler emits a prototype header for each row. That isn't built, and today "nothing
but a run holds a row's C to its declared type" (`m3-native.md` §NA31). A wrong
pointer type corrupts memory. This app will have hundreds of rows, so this is
recommended before phase 2: emit a header per package with each row's C prototype
and compile the package's C against it, so a mismatch is a C compiler error.

**G9 · Fuzzing Geng code.** Build the core as a `runtime = "host"` shared library
(geng-lang `m3-embed.md`, built) and drive it from a libFuzzer or AFL++ harness in C.
The same harness feeds identical input to libghostty-vt for the differential gate
(§7). No language change is needed, only an embed ABI that carries `Bytes` in and
out of an exported function efficiently. That is to be checked in phase 1.

**G10 · Running on old Linux.** visiterm must run on RHEL8 (Q4, geng-lang D889):
glibc 2.28 and kernel 4.18 (§1.1). `os` starts children with `pidfd_spawn` or `posix_spawn`
plus `pidfd_open`, and `pidfd_open` arrived in Linux 5.3, so `os` needs a fallback
that is still safe against pid reuse. Whether RHEL8's kernel backports it has not
been checked (§9 asks for a look). A release build also needs a toolchain that
targets glibc 2.28. The plan is to build releases in an AlmaLinux 8 container,
running the C compiler there through `GENG_CC`, and to link HarfBuzz, FreeType and
xcb-imdkit from pinned sources (§1.1).

**G11 · Things found along the way.** The geng-hello example under `~/prj` imports
a module named `Os` that no longer exists (Os.Env and friends replaced it), so it
does not build. That is trivial, and it is noted so that it isn't forgotten.

---

## 5. New packages

They start inside this repository, under `packages/`, as `[sources]` paths, the way
geng-lang develops its own. A package that is useful outside visiterm moves out to
its own repository once its API settles (Q5).

| Package | Kind | Contents |
|---|---|---|
| `vt` | pure Geng | Parser, terminal state, modes, replies, key/mouse/paste encoders, OSC/DCS sub-parsers |
| `unicode-width` | pure Geng, generated | Width tables from UCD 17.0.0 (the version `core` pins), the per-pane width model of S§5.3 |
| `euckr` | pure Geng | Streaming CP949 decoder and EUC-KR/CP949 encoder with the rules of S§3.4 |
| `tmux-control` | pure Geng | Control-mode protocol, layout parser, pane demultiplexing |
| `pty` | C rows | `openpty`, spawn with a controlling terminal, resize, exit status through a pidfd, signals to the child's process group |
| `xcb` | C rows + Geng | Connection, atoms, windows, events, XRender, XKB, selections, RandR for DPI. The protocol knowledge is in Geng and the C is thin |
| `xkb` | C rows | libxkbcommon and xkbcommon-x11 |
| `xim` | C rows | xcb-imdkit (the XIM client fcitx5 maintains) |
| `fonts` | C rows | fontconfig queries, FreeType faces and rasterising, HarfBuzz shaping. One package, because they share face objects |
| `gles` | C rows | EGL and GLES 3 for phase 5 |
| `signal` | C rows | G2, if it doesn't go into `os` |

The app itself, `visiterm`, holds the model, the update loop, the renderers' Geng
side, configuration and the C that executes display lists.

System libraries all have runtime packages on this machine. HarfBuzz, xcb-xkb,
xcb-imdkit, xkbcommon-x11, xcb-shm and libthai lack development headers here, so
visiterm's devbox supplies them (G1).

---

## 6. Phases

Each phase starts as a **survey document** that measures before building (the
geng-lang habit). It ends with its gate passing and the documents saying what the
code does. Geng-side work in a phase lands in geng-lang with its own decisions and
gates, committed at the same checkpoint as the visiterm side.

**Phase 0 · Groundwork (mostly geng-lang).**

1. G1: package link declarations and the library source decision.
2. G8: prototype headers for C rows.
3. G6: monotonic clock in `core`.
4. G2: signals as events.
5. G5: answering from another thread.
6. G7: measure GC pauses on a visiterm-shaped heap.
7. Measure the reference terminals' throughput on the same inputs (vtebench-style
   files plus §1's workloads) with Alacritty, Ghostty, xterm and st, and set the
   core's throughput budget from that.
8. G10: Gilbert runs `probes/rhel8/inspect.sh` on a RHEL8 host (§9). A hello
   program built in the AlmaLinux 8 container that starts a child runs there.
9. visiterm's `devbox.json` with the C libraries and Zig 0.16 (libghostty-vt's
   minimum, for the oracle).

Exit: a package in this repository links libxcb with no environment variables, a
wrong C row type fails to compile, and the throughput budget and pause figures are
written down.

**Phase 1 · The headless core.** S§5 in Geng: parser with a ground-state fast path,
cells and styles, scrollback in bytes, graphemes and widths per pane, the modes and
sequences of S§5.1's minimum list, replies, the bounds on every attacker-controlled
buffer. Reflow is designed with its tests first (S§5.4) and may land last.

Exit:
- esctest2 runs headless against the core, and its pass rate is recorded;
- the differential gate against libghostty-vt passes on the replay corpus, with every
  divergence explained in a `divergence.txt`, as geng-lang's corpus does;
- the fuzzer has run clean for a recorded number of hours;
- throughput meets the phase 0 budget.

**Phase 2 · A window on X11.** PTY backend, XCB window, the server-side X11 renderer
(S§6.2): glyph sets, `CopyArea` scrolling, damage-limited repaint with overhang,
retained pixmap, latest-frame-wins pacing. Fonts with fallback, CJK fitting, Han
language per profile, Thai shaping, procedural box drawing (S§6.3, S§6.5, C§4–§6).

Exit: runs a shell locally and over `ssh -X` from another host. Bytes per update are
measured with an X protocol tracer and recorded for `tail -f`, `htop` and a vim
scroll. The C§9 script corpus renders correctly under bundled fonts.

**Phase 3 · Input, clipboard, IME, EUC-KR.** XKB modifiers, legacy and kitty
keyboard encodings, mouse 1006/1016, selection and clipboard, OSC 52 with its caps,
bracketed paste with slicing, XIM through xcb-imdkit with S§9's ordering rules, the
EUC-KR filter pair.

Exit: **Gilbert uses it as his daily terminal.** The IME matrix (fcitx5-hangul,
ibus-hangul, Mozc, a pinyin IME, and RHEL8's ibus 1.5.19 with ibus-hangul) passes its
scripted tests, and the EUC-KR corpus
(C§10.5) passes.

**Phase 4 · tmux control mode, tabs and splits.** S§7.3's list: PTY-less pane
surfaces, layout mapping, sizing with paused parsing, `%begin` matching, flow control,
the attach race, recorded-session tests. tmux 2.7, RHEL8's, lacks per-window sizing
and `pause-after`, so the version detection of S§7.3 item 9 decides what each
session gets (Q11).

**Phase 5 · The GPU renderer.** EGL and GLES 3, the same display list, partial
redraw with buffer age, runtime selection by S§6.4's rules, failure visible and never
fatal.

**Phase 6 · Hardening and release.** Soak tests (§7), config reload, a crash report
that doesn't need a debugger, and packaging for Mint and RHEL8.

---

## 7. Reliability and testing

The main risk is a crash, and the plan attacks it on several fronts:

- **Pure code can't crash on bad input** if it never calls `Debug.todo` and never
  indexes without proof. The core uses refinement types for every index (the first
  real user of geng-lang's M4 work; D801 and D816 wait on what it finds).
- **Bound everything an attacker controls** (S§5.1): OSC, DCS, params, title stack,
  grapheme length, sync buffer, scrollback bytes. Out of memory in pure code is an
  accepted crash in Geng (geng-lang's Int-size decision), so bounds are what keep
  memory bounded.
- **Record and replay the whole app.** Every event enters through one `Source`, and
  `update` is pure, so a tape of events replays the session exactly. That covers
  crash reports, regressions and the tmux and IME recordings S§11 asks for. tvision
  got the same thing from "the port boundary is total".
- **Gates**, in this repository's `harness/`, in geng-lang's style:
  - replay corpus: bytes in, serialised grid out;
  - esctest2, headless;
  - differential against libghostty-vt;
  - fuzzing: parser, OSC/DCS, tmux lines, EUC-KR decoder, full stream;
  - repaint: display lists for recorded sessions;
  - X11 bytes per update;
  - throughput and latency against phase 0's budget;
  - a soak test that runs output and input for hours, under geng-lang's
    `GENG_GC_STRESS` build too, and checks the C object counts (G3) and resident
    memory stay flat.
- **Every C row is reviewed as C.** UBSan and ASan builds of the app, as geng-lang's
  native gate does for its runtime.

---

## 8. What carries over from the tvision experiment

| tvision lesson (`gren-tvision/docs/native.md`, `FINDINGS.md`) | Here |
|---|---|
| Ports can't be in packages, so the app hands the package a ports record | **Gone.** Geng has no ports. A package declares `@extern(c, …)` and ships its C. Gilbert's offer to change this isn't needed. What is left is linking (G1) |
| "Nothing can be asked, only told" | **Gone.** A C row returns a value, pure or as a `Task` |
| The JS layer is a real layer with the most bugs | Replaced by C rows, kept thin on purpose (§3.2). The decisions are in Geng where they can be tested |
| A notification a call can cause must be queued, not dispatched | Enforced by the design: C emits into a `Source`, and Geng pulls (geng-lang `ffi.md` F4, D71) |
| Compare descriptions with descriptions, never with the library | The display list is diffed against the previous frame's, never read back from X (§3.4) |
| An echo is not an event | Applies to window size, selection and IME state: record who moved a value |
| Version the wire format | Unneeded inside one binary. The replay tape gets a version |
| Record every session and replay it | Kept, for the whole app (§7) |
| Consistency checks for the four places a widget is declared | G8 does it for C rows in the compiler |

---

## 9. Questions for Gilbert

### 9.1 Answered, 2026-10-23

- **Q4, RHEL8:** yes, visiterm must run on RHEL8, though development is on Mint
  with devbox (geng-lang D889). §1.1 has what a container showed; Gilbert offered
  to inspect a real host, and §9.2's Q9 takes the offer.
- **Q6, one process per top-level window:** yes (§3.5).
- **Q8, the register:** yes. visiterm's own documents stay here; the work it asks of
  Geng and the issues it finds are tracked in geng-lang's register, under "The native
  application: visiterm" (D888).
- **Threads:** Gilbert is open to exploring real threads in Geng if visiterm needs
  them, and thinks it may be too early. The plan agrees it is too early: nothing
  measured yet asks for them. Two measurements would: GC pauses (G7, phase 0) and
  frame cost on the one loop (phase 2). If either breaks its budget, threads are one
  of the options considered then, beside incremental marking and rendering on a C
  thread fed by the display list. G5, a C thread completing a `Task`, is needed
  either way and is the small first step.

### 9.2 Open

Still open from the first list, each with its recommendation:

1. **One event loop for v1?** Recommended: yes (§3.1), revisited on the two
   measurements above.
2. **Write the core in Geng, with libghostty-vt as a differential oracle?**
   Recommended: yes. The core is where Geng is tested hardest, and libghostty-vt's API
   is unstable and needs Zig (S§3.1). As an oracle it only has to build in the dev
   environment.
3. **G1's shape:** a `[native] pkg-config` list in a package's `geng.toml`, libraries
   after the objects, Nix libraries for development and the gates, and the AlmaLinux 8
   container for releases (G10)? Recommended: yes.
5. **Packages live in this repository under `packages/` until their APIs settle?**
   Recommended: yes, then move the general ones (`pty`, `xcb`, `fonts`, `euckr`,
   `signal`) to their own repositories.
7. **GPU renderer after daily use, not before?** Recommended: yes. The X11 renderer
   is mandatory, works locally too, and keeps damage tracking honest.

New:

9. **Run `probes/rhel8/inspect.sh` on a RHEL8 host and send me its output?** It needs
   no compiler and changes nothing. It reports the kernel and whether `pidfd_open`
   works there (G10), glibc, the X server's extensions as seen from that host, fonts,
   ibus, tmux, and the locale settings the EUC-KR users have.
10. **How is visiterm used on RHEL8?** On the RHEL8 host with its window sent to
    another X server (`ssh -X`, the case S§1 calls mandatory), on a RHEL8 desktop,
    or both? This decides whether the GPU renderer matters on RHEL8 at all.
11. **Is `tmux -CC` used on RHEL8 hosts, with their tmux 2.7?** If so, phase 4 needs a
    degraded mode without per-window sizing and flow control. If tmux there is
    usually a newer build, the plan can require 3.2.
12. **Bundle HarfBuzz and FreeType, pinned, in every build?** Recommended: yes.
    RHEL8's HarfBuzz is from 2018, and shaping that differs between Mint and RHEL8
    would make Thai and Hangul rendering depend on the host. The rest (libxcb,
    fontconfig, xkbcommon) come from the system.
13. **Ship fallback fonts (Noto Sans Mono CJK, Noto Sans Thai), or rely on the
    system's?** Both are packaged on RHEL8 and Mint. Bundling makes rendering the
    same everywhere and makes the image tests (S§11 item 9) meaningful, at about
    100 MB. Recommended: rely on the system's, and pin bundled copies only for the
    tests.
14. **Which terminal do you use every day now, and which of its features would you
    miss on day one?** That sets phase 3's "daily terminal" bar more exactly than
    the synthesis can.

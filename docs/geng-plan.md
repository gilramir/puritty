# Plan: visiterm for Linux, written in Geng

Status: **plan, 2026-10-23; Gilbert answered §9 the same day. Phase 0 is done, 2026-10-24: G1, G8, G6, G2 and G5 are built in geng-lang, G7's pauses are measured and answered, and the throughput budget is set (§1.3). Nothing of visiterm itself is built yet. Phase 1 is surveyed, 2026-10-24 ([`phase1-core.md`](phase1-core.md)): no grid of immutable rows meets the budget, and `Array.Builder`, which halves it, has a soundness bug in Geng to fix first; its questions wait on Gilbert. The core is begun, 2026-10-29 ([`vt-core.md`](vt-core.md)): `vt/` agrees with libghostty-vt on the 98 cases of the replay corpus and meets the throughput budget on all thirteen inputs.** It turns [`synthesis.md`](synthesis.md)
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
  - **Two platforms, in order** (Gilbert, 2026-10-23). Platform 1 is this Linux
    Mint machine, a local X11 desktop: visiterm is built and used there first.
    Platform 2 is RHEL8 under ETX, which needs glibc 2.28, kernel 4.18 and 2018's
    HarfBuzz, while Geng's `os` package currently needs pidfds (§1.1, G10). It is
    its own phase, after daily use on Mint (phase 6).
- **The terminal core is written in Geng, not adopted.** The core is the hardest pure
  code in the app and the part most worth testing Geng on. libghostty-vt is the
  oracle for a differential gate, in the style geng-lang already uses for its
  compiler (§6, Q2).
- **An immutable grid is fast enough to start.** The probe grid of immutable rows
  takes about 160 MB/s of `ls`-like output. Its worst case, one cell per cursor move,
  costs about 120 ns per cell (§1). Immutable rows also give the renderer its
  snapshot and damage tracking for free (§3.3).
- **Eight phases, 0 to 7** (§6), each starting as a measured survey, as geng-lang's work does.
  The terminal becomes usable for daily work at the end of phase 3.
- **Gilbert answered the questions** on 2026-10-23 (§9.1). Mint is platform 1;
  RHEL8 is required as platform 2, where visiterm runs in an ETX remote X11 desktop
  on a VM with no GPU, so the server-side X11 renderer is the product's main path
  on both. One process per window. Every
  recommendation was taken. Geng-side tracking is in geng-lang's register (D888–D890).
  Q13 was answered 2026-10-30: system fonts, none shipped (§9.3).

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

**The two workarounds for libxcb**, which were G1's evidence. G1 is built since
(geng-lang D890–D892, `m4-visiterm.md` §VA2): the probe's package now names `xcb`
in a `[native]` table, and `probes/geng/c-call/app/build.sh` builds it with devbox's
clang and Nix's libxcb from this repository's `devbox.json`, with no workaround
(`devbox run probes/geng/c-call/app/build.sh`). What was measured first:

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
  Marking stops the program. Pause times on a heap like this one's are measured
  since (phase 0 item 6, geng-lang `m4-visiterm.md` §VA7): over the budget with a
  row per object, under it with a page per `Bytes`, which is how scrollback is kept
  (§3.3).
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
| Noto Sans CJK, Noto Sans Thai | packaged (2023, 2016) | — | Fallback fonts come from the system; visiterm ships none (Q13, §9.3) |
| **tmux** | 2.7 packaged; **3.6 installed** where visiterm will run | 3.4 | The packaged 2.7 predates 3.2's per-window `refresh-client -C @win` and `pause-after` flow control (S§7.3 items 3 and 5). Gilbert's hosts have 3.6, so visiterm requires 3.2 (Q11) |

### 1.2 The reference terminals' throughput, measured 2026-10-24

Phase 0 item 7. The same machine as §1 (AMD Ryzen 7 8845HS, 16 threads, Linux
6.8), idle. Every program comes from the nixpkgs commit `devbox.json` pins:
Alacritty 0.17.0, Ghostty 1.3.1, xterm 411, st 0.9.3, vtebench 0.3.1,
hyperfine 1.20.0, Xvfb 21.1.24, Mesa 26.2.3, rustc 1.98.1. The probe is
[`../probes/throughput/`](../probes/throughput/); each script's header says how
it is run.

**Inputs** (`gen.py`, `gen-vtebench.py`):

- `ls`: §1's workload 1, byte for byte: 200,000 `ls`-like lines with two SGR
  sequences each, 24.3 MB.
- `cup`: §1's workload 2: 2,000,000 single cells, each after a CUP, 18.3 MB.
- `gitlog`: real text with colour, `git log -p --color=always` of the vendored
  Ghostty, 2,000 commits back from `d8619f1bc`, 25.8 MB.
- `vte-*`: vtebench's ten benchmarks, run in a 160×50 pty and captured as the
  terminal would read them, each repeated to 8–11 MB.

**In a terminal** (`terminals.sh`, `inside.sh`). Each terminal runs at 160×50
in DejaVu Sans Mono 11 and otherwise keeps its defaults (scrollback: Alacritty
10,000 lines, xterm 1,024, st none). They run on a private Xvfb, the two GL
terminals drawing through Mesa's llvmpipe, so that nothing opens on Gilbert's
desktop and all four draw on the CPU, as on RHEL8's ETX desktop (Q10). On the
Radeon the GL terminals may do better; that was not measured. Inside each, the
shell times `cat` of a file, three runs:

| ms, three runs | `ls` | `cup` | `gitlog` |
|---|---:|---:|---:|
| **Alacritty** | **236–268** | **107–113** | **309–314** |
| st | 398–405 | 228–229 | 510–516 |
| Ghostty | 456–491 | 250–254 | 551–566 |
| xterm | 523–533 | 1,917–1,926 | 835–843 |
| no terminal: a reader that discards (`pty.py`) | 166–178 | 44–49 | 275–301 |
| the same, the pty in raw mode | 49–56 | 40–42 | 54–57 |

**The pty is a floor under every terminal.** A shell's pty has the line
discipline's output processing on (`OPOST`, `ONLCR`), and the kernel does that
work in `cat`'s `write`, a byte at a time around each newline: 120 ms of `ls`'s
170 and 230 of `gitlog`'s 285. So `cat` in a shell cannot go faster than about
140 MB/s of `ls` or 90 MB/s of `gitlog` here, whatever the terminal. Alacritty
is near that floor: 97 MB/s of `ls`, 83 of `gitlog`. A program that puts its
pty in raw mode, as tmux's client does, does not pay it.

vtebench in each terminal, its defaults (10 s a benchmark, samples of at least
1 MiB); the median ms a sample, and the number of samples:

| benchmark | Alacritty | Ghostty | xterm | st |
|---|---:|---:|---:|---:|
| cursor_motion | **7** (1,279) | 16 (587) | 152 (66) | 16 (608) |
| dense_cells | **7** (1,389) | 23 (418) | 71 (140) | 64 (156)¹ |
| light_cells | **6** (1,526) | 15 (670) | 129 (78) | 15 (650) |
| scrolling | **130** (76) | 166 (60) | 326 (31) | 183 (57) |
| scrolling_bottom_region | **128** (78) | 163 (62) | 143 (70) | 180 (57) |
| scrolling_bottom_small_region | **128** (78) | 163 (62) | 143 (70) | 171 (58) |
| scrolling_fullscreen | **15** (581) | 28 (363) | 25 (380) | 18 (533) |
| scrolling_top_region | **129** (77) | 160 (63) | 144 (70) | 169 (60) |
| scrolling_top_small_region | **129** (77) | 160 (63) | 143 (70) | 168 (60) |
| unicode | **7** (1,309) | 17 (600) | 495 (18) | 11 (170) |

¹ vtebench's `dense_cells` asks for 256-colour indices up to 355. st rejects each
one and writes a line to stderr, 162 MB of them in the run, so its number
measures that.

**Headless** (`build-cores.sh`, `cores.sh`). Two cores, fed each file directly:
Ghostty's own `ghostty-bench +terminal-stream` from the vendored checkout at
`d8619f1bc`, with `ghostty-scrollback.patch` to set its scrollback (the bench
keeps 10 KB, the app 50 MB); and `alacritty-core`, which feeds the vendored
`alacritty_terminal` 64 KB at a time, as Alacritty's pty loop does. Each is a
whole process under hyperfine, the mean of 10 runs, so each includes start-up
and reading the file, a few ms:

| ms | Ghostty, 10 KB | Ghostty, 50 MB | Alacritty, 10,000 lines | Alacritty, 100,000 |
|---|---:|---:|---:|---:|
| `ls` | 47 | 84 | 195 | 343 |
| `cup` | 71 | 68 | 85 | 82 |
| `gitlog` | 83 | 131 | 239 | 412 |
| vte-cursor_motion | 33 | 33 | 41 | 41 |
| vte-dense_cells | 57 | 58 | 46 | 46 |
| vte-light_cells | 6 | 6 | 39 | 40 |
| vte-scrolling | 106 | 206 | 70 | 240 |
| vte-scrolling_bottom_region | 105 | 104 | 55 | 57 |
| vte-scrolling_bottom_small_region | 107 | 103 | 179 | 179 |
| vte-scrolling_fullscreen | 8 | 36 | 74 | 132 |
| vte-scrolling_top_region | 105 | 105 | 290 | 290 |
| vte-scrolling_top_small_region | 106 | 109 | 176 | 175 |
| vte-unicode | 9 | 8 | 39 | 38 |

What they show:

- **Ghostty's core is the fastest on most inputs**, 2.3× Alacritty's on `ls` and
  1.8× on `gitlog` at each one's default scrollback, and 6× on `light_cells`.
  It is slower on `dense_cells`, `scrolling` and a bottom scroll region.
- **Its window does not show it.** In a terminal, Ghostty is half Alacritty's
  speed on every input, 3–6× its own core. Under llvmpipe its renderer and GTK
  are the likely cost; it was not profiled.
- **Scrollback is not free in either.** Alacritty at 100,000 lines takes `ls` in
  343 ms where 10,000 take 195, most of the difference system time, the pages
  of a larger grid faulted in; Ghostty at 50 MB is 1.8× its 10 KB on `ls`.
- **A scroll region costs differently at the top and the bottom.** Alacritty
  scrolls a region that ends at the bottom in 55 ms and one that starts at the
  top in 290; Ghostty takes 105 for both. Phase 1's region scroll is worth
  measuring on both.

**The Geng grid probe**, §1's, built again on geng-lang `ac0225e5` and run
beside them: `ls` in 149–156 ms, `cup` in 222–230 ms (113 ns a cell).

### 1.3 The core's throughput budget

**Headless, on this machine, visiterm's core takes each input of §1.2 at least
as fast as Alacritty's core does with its default 10,000 lines of scrollback,
while keeping visiterm's own scrollback** (100,000 lines a pane, as G7
measured). It is geng-lang D902, and phase 1's exit holds the core to it:

| input | budget | | input | budget |
|---|---:|---|---|---:|
| `ls` | 195 ms (124 MB/s) | | vte-scrolling | 70 ms |
| `cup` | 85 ms (42 ns a cell) | | vte-scrolling_bottom_region | 55 ms |
| `gitlog` | 239 ms (108 MB/s) | | vte-scrolling_bottom_small_region | 179 ms |
| vte-cursor_motion | 41 ms | | vte-scrolling_fullscreen | 74 ms |
| vte-dense_cells | 46 ms | | vte-scrolling_top_region | 290 ms |
| vte-light_cells | 39 ms | | vte-scrolling_top_small_region | 176 ms |
| vte-unicode | 39 ms | | | |

Why this bar:

1. **Alacritty is the fastest of the four in a window**, on all three files and
   on every vtebench benchmark, and its core is what sets that.
2. **A slower core would show in `cat`.** Alacritty's core takes `ls` in 195 ms
   over a pty floor of 170; much slower and the core, not the kernel, is what
   the user waits for.
3. **Ghostty's core is not the bar**, though it is faster on most inputs: it is
   slower on three, and the window it feeds is slower than Alacritty's here.
   Its numbers stay as the reference for what a core can do.
4. **It is necessary, not sufficient.** visiterm parses and renders on one
   thread (§3.1); Alacritty parses on a thread of its own. Phase 2 measures
   the frame cost on the loop and the same `cat`s in a visiterm window,
   against Alacritty's times above.

**Against it, the grid probe**: `ls` is under (152 ms against 195), though the
probe does a fraction of a core's work (no style table, scrollback, wrapping or
damage). **`cup` is 2.6× over** (225 ms against 85): each cell allocates its
run, copies its 160-cell row and copies the 50-row array, about 210 words a
cell. vte-cursor_motion is the same shape. This is the number §3.3 said G4
waits for, but it is the probe's, not the core's: phase 1 measures the real
core's cell write before G4 or an in-place update of a row in its grid is
decided (geng-lang `m4-visiterm.md` §VA8).

**Development moved to a second machine the same day (§1.4), and the budget
is measured again there**: its rule is the same, its numbers are §1.4's, and
from here on a probe is held to the budget measured on the machine the probe
ran on.

### 1.4 The same measurements on the second machine, 2026-10-24

Development moved to an AMD Ryzen 9 9950X, 16 cores, 32 threads, 60 GB, Linux
Mint 22.3 with kernel 7.0.0, the `powersave` governor with
`balance_performance` (Gilbert's choice, kept for now), idle. The programs
come from the same nixpkgs commit; geng-lang at `d027d333`, the fork at
`d0f892f2`, which is D903 built. Every script ran as in §1.2 except that
`terminals.sh` now gives the terminals no session bus: Ghostty's GTK waited
on desktop portals that never answered here until its window came up after
`inside.sh` had stopped waiting for 160×50.

**Headless** (`cores.sh`, the mean of 10 runs):

| ms | Ghostty, 10 KB | Ghostty, 50 MB | Alacritty, 10,000 lines | Alacritty, 100,000 |
|---|---:|---:|---:|---:|
| `ls` | 32 | 47 | 124 | 202 |
| `cup` | 51 | 51 | 56 | 56 |
| `gitlog` | 60 | 84 | 132 | 261 |
| vte-cursor_motion | 22 | 22 | 28 | 28 |
| vte-dense_cells | 40 | 39 | 28 | 28 |
| vte-light_cells | 3 | 3 | 24 | 25 |
| vte-scrolling | 69 | 143 | 42 | 119 |
| vte-scrolling_bottom_region | 66 | 66 | 37 | 38 |
| vte-scrolling_bottom_small_region | 65 | 66 | 132 | 132 |
| vte-scrolling_fullscreen | 4 | 13 | 45 | 67 |
| vte-scrolling_top_region | 66 | 67 | 223 | 225 |
| vte-scrolling_top_small_region | 65 | 65 | 125 | 126 |
| vte-unicode | 5 | 5 | 25 | 25 |

Alacritty's core is 1.3–1.8× faster than on the first machine (`ls` 195 →
124, `gitlog` 239 → 132, `cup` 85 → 56); what §1.2 says of the two cores still
holds.

**So D902's budget on this machine** is the Alacritty, 10,000 lines column:

| input | budget | | input | budget |
|---|---:|---|---|---:|
| `ls` | 124 ms (196 MB/s) | | vte-scrolling | 42 ms |
| `cup` | 56 ms (28 ns a cell) | | vte-scrolling_bottom_region | 37 ms |
| `gitlog` | 132 ms (195 MB/s) | | vte-scrolling_bottom_small_region | 132 ms |
| vte-cursor_motion | 28 ms | | vte-scrolling_fullscreen | 45 ms |
| vte-dense_cells | 28 ms | | vte-scrolling_top_region | 223 ms |
| vte-light_cells | 24 ms | | vte-scrolling_top_small_region | 125 ms |
| vte-unicode | 25 ms | | | |

**In a terminal** (`terminals.sh`, three `cat`s each; Ghostty run on its own
after the other three, the first time it ran never reaching 160×50):

| ms, three runs | `ls` | `cup` | `gitlog` |
|---|---:|---:|---:|
| **Alacritty** | **152–181** | **69–76** | **188–204** |
| Ghostty | 210–243 | 129–138 | 299–318 |
| st | 259–269 | 158–162 | 366–367 |
| xterm | 330–337 | 1,537–1,543 | 529–546 |
| no terminal: a reader that discards (`pty.py`, five runs) | 88–118 | 20–33 | 183–187 |
| the same, the pty in raw mode | 24–33 | 19–25 | 25–32 |

Alacritty is still the fastest. Ghostty is now faster than st on all three,
where on the first machine it was slower than st on all three; whether that
is the machine or the session bus Ghostty no longer waits on was not
separated. The cooked pty is still most of a `cat`: 88–118 ms of `ls` and
183–187 of `gitlog`, against Alacritty's 152–181 and 188–204.

vtebench, the median ms a sample and the number of samples:

| benchmark | Alacritty | Ghostty | xterm | st |
|---|---:|---:|---:|---:|
| cursor_motion | **4** (2,164) | 8 (1,190) | 118 (85) | 10 (954) |
| dense_cells | **4** (2,260) | 12 (812) | 54 (183) | 22 (459)¹ |
| light_cells | **3** (2,665) | 6 (1,495) | 82 (122) | 9 (1,078) |
| scrolling | **115** (87) | 146 (69) | 210 (48) | 155 (65) |
| scrolling_bottom_region | **118** (85) | 144 (71) | 148 (68) | 155 (65) |
| scrolling_bottom_small_region | **120** (84) | 147 (69) | 148 (68) | 153 (66) |
| scrolling_fullscreen | **9** (1,013) | 11 (925) | 16 (604) | 12 (823) |
| scrolling_top_region | **115** (87) | 146 (70) | 146 (69) | 151 (66) |
| scrolling_top_small_region | **112** (90) | 146 (70) | 147 (69) | 152 (66) |
| unicode | **4** (2,383) | 7 (1,190) | 170 (59) | 6 (318) |

¹ As in §1.2: st wrote 497 MB of rejected colour indices to its log in the run.

**The Geng probes on this machine**, against this budget:

- §1's grid probe (five runs): `ls` 132–148 ms against 124, over where it was
  under on the first machine (152 against 195); `cup` 149–151 against 56,
  2.7× over, as it was 2.6×. Alacritty's core gained more from the machine
  than the probe did on `ls` (0.64× its time against 0.87×).
- Phase 1's two cores, `core`'s cell operations and G7's pauses are in
  `phase1-core.md` §10.

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
  milliseconds, and S§6.5 wants them asynchronous anyway. A C row starts a thread
  with `geng_thread_start`, the thread sends its answer to a post, and the loop
  hands it to the row on the program's thread (G5, geng-lang D897). By hand, with
  the thread writing an eventfd and the loop answering a wait the row kept, it
  does **not** work: `probes/geng/answer` showed the nursery moves the wait, 5
  crashes in 5 runs.

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

**Cold scrollback is kept in pages, decided 2026-10-24** (geng-lang D901, from G7).
When a page of 256 rows fills, its rows' text is joined into one `Bytes` and their
attribute runs into another, and the page, not the row, is the unit of cold storage.
A cold row is read by slicing its page; reflow and search decode a page at a time.
The screen and the page being filled stay rows. Pages sit in a ring (`Array.set`),
not a queue. The reason is the collector: Boehm marks each live object with the
program stopped, and a row per object is 31–38 ms at four panes of 100,000 lines,
where pages are 3–4 ms (`probes/geng/gcpause`).

If the real core is too slow on immutable rows, the question for Geng is a mutable
buffer that the refinement checker or a linearity rule keeps safe (G4). That is a
language decision, and it waits for the numbers.

**The numbers, 2026-10-24** ([`phase1-core.md`](phase1-core.md) §3, §4): a
probe core on immutable rows is over the budget on every input, a cell
through a row and the screen costing 34 ns before it is parsed. The same core
on a screen of `Array.Builder`s, `core`'s public transient, halves most
inputs. The builder is G4's buffer already, but natively and on node it is
not sound on a read of an older handle (§4.2), and Geng fixes that first.

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
deferred to the measurements. *Measured 2026-10-24: phase 1 needs one, and
the survey proposes `Array.Builder`, made sound and given a write of a run, a
fill and a block move ([`phase1-core.md`](phase1-core.md) §5.1, §8).*

**G5 · Answering from another thread.** The pattern in §3.1 (a C thread does
blocking work and wakes the loop through an fd) was thought to work today, but each package would
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

1. G1: package link declarations and the library source decision. **Built
   2026-10-23** (geng-lang D890–D892).
2. G8: prototype headers for C rows. **Built 2026-10-23** (geng-lang D893).
3. G6: monotonic clock in `core`. **Built 2026-10-23** (geng-lang D894:
   `Time.monotonic`, a `Duration` of whole milliseconds).
4. G2: signals as events. **Built 2026-10-23** (geng-lang D895, D896:
   `Os.Signal`). `probes/geng/signal` showed that a row alone could not do
   it: the runtime's second thread took the signal and the program died, 20
   runs of 20, so the runtime now blocks every signal on that thread. The
   PTY spawn must give its child an empty signal mask, as `Os.Process` does.
5. G5: answering from another thread. **Built 2026-10-23** (geng-lang D897:
   `geng_post_*` and `geng_thread_start`). `probes/geng/answer` showed that the
   hand-written pattern was not safe: a wait kept in `malloc`'d memory is moved
   by the nursery, and the row crashed 5 runs of 5. A post costs about 170 ns a
   message from one thread (`answer/app/src/Bench.geng`); a row whose thread
   starts and answers once, about 82 µs, most of it the thread.
6. G7: measure GC pauses on a visiterm-shaped heap. **Measured 2026-10-24**
   (geng-lang `m4-visiterm.md` §VA7; `probes/geng/gcpause`). Minor collections
   are 0.3 ms at worst. Boehm's full collections stop the program about 7.5 ms
   for each 100,000 rows of scrollback kept as a `Bytes` per row: 16 ms at one
   pane of 100,000 lines, 31–38 ms at four, 57–62 ms at eight, so the budget
   holds only at one pane. With each full page of 256 cold rows joined into
   one text `Bytes` and one of attribute runs, the longest pause is 4.5 ms at
   four panes and 4.1 ms at eight, with a fifth of the memory. Keep the pages
   in a ring (`Array.set`), not a queue (`pushLast` and `dropFirst`), which
   keeps up to twice its rows (geng-lang D705). The probe first found a leak
   in Geng's runtime, fixed there (D898): every row a `cat` scrolled away was
   kept. **Decided 2026-10-24**: Gilbert chose joined pages here (geng-lang
   D901, §3.3) and atomic strings in the runtime (D900, built). With both,
   the longest pause is 3.0–3.7 ms at four panes and 3.0 ms at eight
   (geng-lang §VA7.7).
7. Measure the reference terminals' throughput on the same inputs (vtebench-style
   files plus §1's workloads) with Alacritty, Ghostty, xterm and st, and set the
   core's throughput budget from that. **Measured 2026-10-24** (§1.2,
   `probes/throughput`): Alacritty is the fastest in a window on every input,
   and a shell's pty alone is a floor of about 140 MB/s of `ls`. **The budget**
   (§1.3, geng-lang D902): headless, visiterm's core is at least as fast as
   Alacritty's core on each input. §1's grid probe meets it on `ls` and is 2.6×
   over on `cup`, a row copied for each cell.
8. Moved to phase 6: RHEL8 is platform 2. Gilbert's run of
   `probes/rhel8/inspect.sh` is still welcome whenever it suits, since it costs
   nothing to look early.
9. visiterm's `devbox.json` with the C libraries and Zig 0.16 (libghostty-vt's
   minimum, for the oracle). **Done 2026-10-23**, from the nixpkgs commit geng-lang's
   clang and gcc come from: libxcb 1.17.0 (with render, xkb, renderutil 0.3.10,
   keysyms 0.4.1), xkbcommon 1.13.2, HarfBuzz 13.2.1, FreeType 2.14.3, fontconfig
   2.18.3, xcb-imdkit 1.0.9, libthai 0.1.30, Zig 0.16.0, tmux 3.7c, Xvfb 21.1.24,
   xtrace 1.4.0 and xdpyinfo. Zig moved to 0.17.0 on 2026-10-30, pinned alone to
   a later nixpkgs commit, for libghostty-vt v1.4.0 (`vt-core.md` §VC15). These are much newer than RHEL8's (§1.1), so the
   AlmaLinux 8 release build is what catches an API RHEL8 lacks.

Exit: a package in this repository links libxcb with no environment variables, a
wrong C row type fails to compile, and the throughput budget and pause figures are
written down.

**Phase 1 · The headless core.** *Surveyed 2026-10-24:
[`phase1-core.md`](phase1-core.md); Gilbert answered its five questions
(§9). Begun 2026-10-29: [`vt-core.md`](vt-core.md); esctest2 headless the same
day, 297 of 567 (§VC10). Exit met 2026-10-30 (`vt-core.md` §VC9).* S§5 in Geng: parser with a ground-state fast path,
cells and styles, scrollback in bytes, graphemes and widths per pane, the modes and
sequences of S§5.1's minimum list, replies, the bounds on every attacker-controlled
buffer. Reflow is designed with its tests first (S§5.4) and may land last.

Exit:
- esctest2 runs headless against the core, and its pass rate is recorded;
- the differential gate against libghostty-vt passes on the replay corpus, with every
  divergence explained in a `divergence.txt`, as geng-lang's corpus does;
- the fuzzer has run clean for a recorded number of hours;
- throughput meets the phase 0 budget (§1.3, with 100,000 lines of scrollback).

**Phase 2 · A window on X11.** *Survey begun 2026-10-30:
[`phase2-window.md`](phase2-window.md): the renderer diffs its own copy of
the screen and finds scrolls by row hashes, a pty fits the one loop, and a
vim scroll costs 374 bytes a line on the wire.* PTY backend, XCB window, the server-side X11 renderer
(S§6.2): glyph sets, `CopyArea` scrolling, damage-limited repaint with overhang,
retained pixmap, latest-frame-wins pacing. Fonts with fallback, CJK fitting, Han
language per profile, Thai shaping, procedural box drawing (S§6.3, S§6.5, C§4–§6).

Exit: runs a shell on **this Mint desktop**, and over `ssh -X` from another
host, which stands in for ETX until phase 6. Bytes per update are
measured with an X protocol tracer and recorded for `tail -f`, `htop` and a vim
scroll. The C§9 script corpus renders correctly under the fonts the tests pin (Q13:
visiterm ships none).

**Phase 3 · Input, clipboard, IME, EUC-KR.** XKB modifiers, legacy and kitty
keyboard encodings, mouse 1006/1016, selection and clipboard, OSC 52 with its caps,
bracketed paste with slicing, XIM through xcb-imdkit with S§9's ordering rules, the
EUC-KR filter pair.

Exit: **Gilbert uses it as his daily terminal on Mint.** The IME matrix (fcitx5-hangul,
ibus-hangul, Mozc, a pinyin IME) passes its scripted tests, and the EUC-KR corpus
(C§10.5) passes.

**Phase 4 · tmux control mode, tabs and splits.** S§7.3's list: PTY-less pane
surfaces, layout mapping, sizing with paused parsing, `%begin` matching, flow control,
the attach race, recorded-session tests. tmux 3.2 or later is required (Q11): an
older tmux is refused with a message saying so, not served in a degraded mode.

**Phase 5 · The GPU renderer.** Local use on Mint only: on RHEL8 visiterm runs in
ETX on a VM with no GPU (Q10), where the X11 renderer is the path. It is an
option, not a requirement: the X11 renderer serves Mint's local desktop too. EGL and GLES 3, the same display list, partial
redraw with buffer age, runtime selection by S§6.4's rules, failure visible and never
fatal.

**Phase 6 · Platform 2: RHEL8 under ETX.** G10: the pidfd question settled on a
real RHEL8 kernel (`probes/rhel8/inspect.sh`), and a fallback in `os` if it needs
one; the release build in an AlmaLinux 8 container against glibc 2.28, with pinned
HarfBuzz, FreeType and xcb-imdkit linked in (Q12); every API visiterm uses checked
against RHEL8's libxcb 1.13.1 and xkbcommon 0.9.1; ibus 1.5.19 with ibus-hangul in
the IME matrix; the ETX X server's extensions checked, RENDER above all.

Exit: Gilbert uses it in the ETX desktop on his RHEL8 VM, and bytes per update are
recorded there as in phase 2.

**Phase 7 · Hardening and release.** Soak tests (§7), config reload, a crash report
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

- **Q1, one event loop for v1:** yes (§3.1).
- **Q2, the core in Geng, libghostty-vt as a differential oracle:** yes.
- **Q3, G1's shape:** yes: a `[native] pkg-config` list in a package's `geng.toml`,
  libraries after the objects, Nix libraries for development and the gates, the
  AlmaLinux 8 container for releases (geng-lang D890).
- **Q4, RHEL8:** visiterm must run on RHEL8, though development is on Mint with
  devbox (geng-lang D889). **Mint comes first:** Gilbert uses visiterm on this
  Mint machine first, and RHEL8 is platform 2 (phase 6). §1.1 has what a container showed.
- **Q5, packages in this repository until their APIs settle:** yes.
- **Q6, one process per top-level window:** yes (§3.5).
- **Q7, the GPU renderer after daily use:** yes, and Q10 makes it a Mint-only
  feature.
- **Q8, the register:** visiterm's own documents stay here. The work it asks of Geng
  and the issues it finds are tracked in geng-lang's register, under "The native
  application: visiterm" (D888).
- **Q9, a real RHEL8 host:** `probes/rhel8/inspect.sh` was mailed to Gilbert, to run
  inside the ETX desktop. Its output settles G10 (pidfds on RHEL8's kernel) and says
  which extensions ETX's X server has, RENDER above all.
- **Q10, how visiterm runs on RHEL8:** in an ETX (Exceed TurboX) remote X11 desktop
  on a VM, with no GPU. The server-side X11 renderer (S§6.2) is therefore the main
  path, not a fallback. Where ETX's X server runs relative to the VM, and so how far
  the X connection is, is for the inspection to show. Drawing only what changed pays
  either way, since ETX has to carry every changed pixel to Gilbert's screen.
- **Q11, tmux:** Gilbert runs tmux 3.6 on RHEL8 and RHEL9, so visiterm requires
  tmux 3.2 and has no degraded mode (phase 4).
- **Q12, bundle pinned HarfBuzz and FreeType:** yes.
- **Q14:** dropped. The plan builds what the synthesis describes. New features, from
  Gilbert or as questions about a specific feature, are considered as they come up.
- **Threads:** Gilbert is open to exploring real threads in Geng if visiterm needs
  them, and thinks it may be too early. Nothing measured yet asks for them. Two
  measurements would: GC pauses (G7, phase 0) and frame cost on the one loop
  (phase 2). If either breaks its budget, threads are one option considered then,
  beside incremental marking and rendering on a C thread fed by the display list.
  G5, a C thread completing a `Task`, is needed either way and is the small first
  step.

### 9.2 Open

None.

### 9.3 Answered later

- **Q13, fallback fonts, 2026-10-30:** visiterm does **not** ship fonts. It
  uses the system's, found through fontconfig, Noto Sans Mono CJK and Noto Sans
  Thai included when the system has them. The rendering tests (S§11 item 9) pin
  their own copies as test fixtures, which are not shipped.

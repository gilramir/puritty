# puritty on Windows: a survey (2026-11-09)

Gilbert, 2026-11-09: puritty on Windows, cross-built from Linux, before the
compiler runs there (geng-lang `docs/open-items.md` D1062–D1065, "Windows:
puritty, the compiler, the work"). His Windows 11 machine, `beelink1`, takes
ssh from nene, so this survey was measured there by Claude without him: files
copied with `scp`, programs run over ssh, window programs started in his
desktop session through a scheduled task and seen in a screenshot
(`harness/windows/`).

Geng's Windows target is done through geng-lang `m4-windows.md` §WN11 step
5: a Geng program built with `--platform=windows` runs there, with all of
`os`, a pseudo console (ConPTY) for a child on a terminal, and a console read
and written in UTF-16. What puritty adds is its window: everything
`packages/x11` does. This survey says what that is, what Windows offers for
each part, what was measured, and proposes the order.

## WS1 · What puritty asks of its platform

`packages/x11` is a Geng module of 450 lines over 2,306 lines of C. The
Geng side is small and portable; the C does five things:

| part | on X11 | what of it is X11's |
|---|---|---|
| the window | an X window, a retained pixmap the size of the cells, rows copied to the window, a scroll as one copy | the window and the copies |
| text | runs shaped by HarfBuzz, glyphs rasterised by FreeType, colour glyphs as ARGB, a fallback face found by fontconfig, uploaded to the server with XRender | XRender's glyph set and composites; fontconfig |
| box drawing | lines and blocks drawn by the C into a canvas | nothing |
| ink | which cell edges a glyph's pixels crossed (V40) | nothing |
| events | keys through XKB (V47), an IME through XIM (V46), the pointer, the size, the focus, the close, selections and paste | all of it |

The app (`app/src`, 2,326 lines) adds three Linux assumptions of its own:
the settings file under `XDG_CONFIG_HOME` or `~/.config`, the program run as
`$SHELL` or `/bin/sh`, and `X11.` in about thirty places in `Main`. The
terminal core (`vt`, 27,148 lines) assumes nothing of the platform: it reads
bytes, keys as records, and answers a display list.

## WS2 · Measured on beelink1

Windows 11 25H2 (build 26200), PowerShell 5.1 over ssh.

| what | measured |
|---|---|
| display | one monitor, 3840×2160, scaled 150% (144 DPI); a window that declares per-monitor DPI awareness (v2) gets the real pixels |
| input languages | Korean (Microsoft IME), English (US, and US-International), Thai |
| IMM32 | a window gets an input context, and the active layout is an IME (`ImmIsIME`) |
| a key's text | `ToUnicodeEx`, asked not to change the keyboard's state (flag 4), gives each layout's character for a key, unshifted and shifted: the Korean layout's are Latin (its Hangul comes through the IME), Thai's are Thai, and US-International's ` key is a dead key (−1) |
| fonts | Fira Code, installed for the user only (`%LOCALAPPDATA%\Microsoft\Windows\Fonts`), Cascadia Code and Mono, Consolas, DejaVu and Liberation Mono; Malgun Gothic, Gulim, Batang for Hangul; Leelawadee UI for Thai; Segoe UI Emoji |
| clipboard | readable; `CF_UNICODETEXT` there |
| a frame's copy | a 32-bit bitmap the window's size (1178×544) copied to the window with `BitBlt`: 0.39 ms, the median of 60 |
| a window's first paint | 35 ms after it is made |
| ssh | Windows' OpenSSH client is installed (`C:\Windows\System32\OpenSSH\ssh.exe`) |

**FreeType and HarfBuzz on Windows' own fonts** (`bench/windows/probe-text.c`):
FreeType 2.14.3 and HarfBuzz 13.2.1, the versions nixpkgs pins, shape and
rasterise one line in four faces as puritty's renderer does, picture below
the table. Fira Code's ligatures (`->`, `=>`, `!=`, `0x`), Hangul in Malgun
Gothic, Thai in Leelawadee UI, and Segoe UI Emoji's colour glyphs, which
FreeType draws from the font's colour table as BGRA: 😀 and the
skin-toned 👍🏽 as one glyph. 🇰🇷 is the letters "KR", since Segoe UI Emoji has
no flags; that is Windows' font, the same in every program. Shaping took
0.05 to 0.3 ms a run; Malgun Gothic's first glyphs 13 ms, its 13 MB loaded.

![FreeType and HarfBuzz on beelink1](images/windows-probe-text.png)

**GDI, for comparison** (`bench/windows/probe-window.c`): Windows' own text
drawing found Fira Code, applied its ligatures, and fell back to Hangul, Thai
and emoji by itself; its emoji is monochrome, since GDI draws no colour
glyphs, and Fira Code's box-drawing glyphs do not join (puritty draws those
itself anyway). The window as Gilbert's screen showed it (below):

![The window probe on beelink1](images/windows-probe-window.png)

**A console program opens a console.** The window probe, linked as a console
program, made Windows Terminal open a tab for it behind its window. puritty
has to be linked for the GUI subsystem (`-mwindows`). Geng's runtime, with no
console, answers a write to standard output with an error
(`ERROR_INVALID_HANDLE`), not a crash.

## WS3 · Drawing: puritty's own text path, into memory

**Proposed: keep FreeType and HarfBuzz, and draw into a bitmap.** The X11 C
uploads glyphs to the server and composites them with XRender. On Windows
the same code draws into a 32-bit DIB section the size of the cells, the
retained pixmap's twin, and the rows a frame touched are copied to the window
with `BitBlt`, which measured 0.4 ms for a whole window. Shaping, the face
lookup, rasterising, colour glyphs, box drawing and ink are the X11 C's as
they are; only the glyph set and the composite become a blend into memory.

Against **Direct2D and DirectWrite**: they are COM interfaces, written for
C++, with ClearType and Windows' own font fallback. They would be a second
text path, rendering differently from Linux, so the pixel gate (V38) could not
hold the two to one picture, and the ink measurement would be done again.
Against **GDI**: no colour emoji, and its own fallback.

What changes:

- **Finding a face.** fontconfig is Linux's. On Windows the faces are files
  in `C:\Windows\Fonts` and the user's font folder, named in the registry
  (`HKLM` and `HKCU` `...\CurrentVersion\Fonts`). The primary font is found
  by its family name there; a fallback is chosen by script from a short list
  (Malgun Gothic for Hangul, Yu Gothic or MS Gothic for Japanese, Microsoft
  YaHei for Chinese, Leelawadee UI for Thai, Segoe UI Emoji, Segoe UI
  Symbol), each checked for the cluster with the coverage test the X11 C has
  (`covers`). Only the Korean, Thai and emoji faces were looked for on
  beelink1; the Japanese and Chinese ones are Windows' defaults where their
  language packs are installed. DirectWrite's `IDWriteFontFallback` is the alternative if the
  list proves short.
- **Building the two libraries.** HarfBuzz builds for Windows as its one
  source file (`src/harfbuzz.cc`) with the toolchain's `g++`, with threads
  off (`HB_NO_MT`; puritty shapes on one thread), in 22 s; nixpkgs' own
  build needs a Windows Python that nixpkgs marks broken. nixpkgs' FreeType
  builds, but needs libpng, bzip2 and Brotli as DLLs; libpng serves only
  bitmap emoji fonts, which Windows' is not, so a FreeType built from source
  with zlib alone keeps puritty one static `.exe`, as Geng's Windows
  programs are (D1073). A script beside `packages/x11/build-imdkit.sh`
  would build both and give `pkg-config` their flags (D890).

## WS4 · The window and Geng's loop

A Win32 window belongs to the thread that made it, which has to keep taking
its messages. Geng's loop on Windows waits on an I/O completion port (D1075),
not on window messages. The runtime already has the way across: a *post*
(`geng_post`, D897), by which a thread that holds no Geng value hands
messages to the program's thread.

**Proposed:** a window thread, started by `open`, makes the window and runs
its message loop. It turns messages into the same event records X11's C
makes (V36) and queues them; the first queued after a `take` sends a post,
which answers `events`. `draw` copies the display list and hands it to the
window thread (`PostThreadMessage`), which draws it into the bitmap,
invalidates the rows, and posts the ink back. The Geng side, `events`,
`take` and `draw`, is unchanged, and so is everything in `vt` and most of
`Main`. FreeType and HarfBuzz run on the window thread alone, so HarfBuzz's
threads stay off.

## WS5 · Keys

The record a key makes stays X11's (V47): an action, a key code, the
modifiers as Ghostty's bits, the modifiers its text consumed, its unshifted
code point, its keysym and its text. On Windows:

- the key code is the scan code (`lParam` bits 16–23 and the extended bit);
- the keysym is X11's for the same key: the C maps each virtual key that
  makes no text (arrows, F1–F24, the keypad, Home, Insert, …) to the keysym
  X11 gives it, so `vt`'s encoder (Ghostty's, `docs/phase3-input.md` §4)
  reads Windows' keys as Linux's;
- the text is `WM_CHAR`'s, after `TranslateMessage`, so a dead key
  (US-International's `` ` ``) composes as Windows composes it;
- the unshifted code point is `ToUnicodeEx` of the key with no modifiers,
  asked not to change the keyboard's state (flag 4, measured: the Korean
  layout gives Latin, Thai gives Thai);
- left and right modifiers from `GetKeyState` of `VK_LSHIFT` and the rest;
  Alt arrives as `WM_SYSKEYDOWN`, which must not reach `DefWindowProc` for
  keys puritty uses (Alt+letter to the program, not to a menu).

## WS6 · The IME

**IMM32**, the older of Windows' two input-method interfaces and the one
the Korean IME serves to every program that asks: `WM_IME_COMPOSITION` with
`GCS_COMPSTR` (the preedit, its caret `GCS_CURSORPOS` and its attributes
`GCS_COMPATTR`) and `GCS_RESULTSTR` (the commit), `WM_IME_ENDCOMPOSITION`
(done). These are X11's records 5, 6 and 7 as they are; puritty draws the
preedit itself, as it does on X11 (V46), and `spot` becomes
`ImmSetCompositionWindow` and `ImmSetCandidateWindow` at the cursor's cell.
**TSF**, the newer, is COM, and is what Windows Terminal uses; it can wait
until IMM32 is found short.

## WS7 · The rest of the window

| X11 | Windows |
|---|---|
| size in cells | `WM_SIZE`, divided by the cell |
| focus | `WM_SETFOCUS`, `WM_KILLFOCUS` |
| close | `WM_CLOSE` |
| the pointer, the wheel | `WM_MOUSEMOVE`, the button messages, `WM_MOUSEWHEEL` (120 a notch, finer on a touchpad: steps accumulated) |
| every motion, or only with a button | the same messages, filtered |
| I-beam and arrow | `SetCursor` in `WM_SETCURSOR`, `IDC_IBEAM` and `IDC_ARROW` |
| title | `SetWindowTextW` |
| DPI | new on Windows: the window declares per-monitor awareness (v2) and takes `WM_DPICHANGED` when moved to another monitor or rescaled, as a zoom (V50) |
| the pixel gate's picture | the bitmap written as the same PPM |

## WS8 · Selections

X11 has two selections, PRIMARY (copy on select, paste with the middle
button) and CLIPBOARD. Windows has the clipboard alone (`CF_UNICODETEXT`,
UTF-16). `X11.Selection`'s `Primary` has no Windows twin: puritty can keep
its own selection as PRIMARY within its windows, so a middle click pastes
what was last selected in puritty, or leave PRIMARY out on Windows. OSC 52
writes the clipboard either way (§16).

## WS9 · The shell, ssh and settings

- **The program run.** `$SHELL` or `/bin/sh` on Linux; on Windows
  `%COMSPEC%` (cmd.exe) unless PowerShell is wanted (`pwsh.exe`, then
  `powershell.exe`). It runs on a pseudo console, which `Os.Process`
  already gives a child (D1088).
- **ssh.** Windows' own `ssh.exe` runs on the pseudo console like any
  program, so `puritty ssh host` works before an ssh client is built in
  (D1062's plan). A built-in client, with its cryptography, is its own
  survey.
- **Settings.** `%APPDATA%\puritty\config.toml` for
  `$XDG_CONFIG_HOME/puritty/config.toml`.

## WS10 · One application, two platforms

A Windows build refuses a package declared for Linux (D1083), and Geng has no
dependencies by platform, so puritty's one `app/geng.toml`, which lists
`x11`, cannot build for Windows. **Proposed:** the platform package's module
is named for what it is, `Window`, in both packages (`x11` renamed from
`X11`, and a new `packages/win32`, `platform = "windows"`), with the same
functions and types; and the application has two manifests,
`app/linux/geng.toml` and `app/windows/geng.toml`, over the one `app/src`,
each listing its platform's package. `app/src` imports `Window` and does not
know which. The settings path and the default program, the only other
differences, come from `Os.Env` and are tested at run time. A Geng feature
for dependencies by platform (`[dependencies.windows]`) would make the two
manifests one, and can wait until a second program needs it.

## WS11 · What can be tested from here

Without Gilbert: building, copying and running anything; a window in his
session and its screenshot; the clipboard, set and read by PowerShell; and
keys and the IME through `SendInput` from a program in his session.

**Measured** (`bench/windows/probe-ime.c`): keys sent with `SendInput` reach
the Korean IME as typed keys do. The 한/영 key (`VK_HANGUL`) turns Hangul on;
then `g`, `k`, `s` arrive as `VK_PROCESSKEY` (0xE5) with the preedit ㅎ
(U+314E), 하 (U+D558), 한 (U+D55C) in `WM_IME_COMPOSITION`'s `GCS_COMPSTR`,
and a space commits 한 (`GCS_RESULTSTR`, then `WM_CHAR` U+D55C) and is
typed. Setting Hangul mode with `ImmSetConversionStatus` alone did not
compose: the keys arrived as Latin letters. A program started by the task
scheduler cannot take the foreground by asking; joining the foreground
thread's input for the moment it raises its window (`AttachThreadInput`)
lets it, and sends that thread nothing. The probe sends a key only while
its own window is the foreground, and stops otherwise, so that nothing it
types reaches another program.

With Gilbert: typing Hangul into puritty by hand once, as a check of what
`SendInput` showed; how it feels; the scaled display at 150% and a move to
another monitor, if he has one.

## WS12 · The steps, in order

1. **The toolchain.** FreeType (zlib only) and HarfBuzz built for Windows as
   static libraries, with their `pkg-config` files, by a script.
2. **`Window`.** `X11` renamed `Window`; `app/linux/` and `app/windows/`
   manifests; the Linux build unchanged, every gate passing.
3. **`packages/win32`, drawing.** The window thread, the bitmap, the X11
   C's text, box and ink code moved where both packages share it, and
   `draw` and `shot`. A frame of `vt`'s output on beelink1, compared with
   Linux's picture of the same frame.
4. **Events.** Size, focus, close, the pointer, keys (WS5), then the IME
   (WS6), each with a `SendInput` probe.
5. **The app on Windows.** The program run on a pseudo console, the
   settings path, the clipboard; `puritty` running cmd, PowerShell and
   `ssh` on beelink1.
6. **The pixel gate and the replay corpus on Windows**, run over ssh.

## WS13 · Questions for Gilbert, with leanings

1. **Drawing** (WS3): FreeType and HarfBuzz into a bitmap, the same pixels as
   Linux, or Direct2D and DirectWrite, Windows' own look. *Leaning: FreeType
   and HarfBuzz.*
2. **PRIMARY on Windows** (WS8): kept within puritty (a middle click pastes
   puritty's last selection), or left out. *Leaning: kept within puritty.*
3. **The default program** (WS9): cmd, Windows PowerShell, or PowerShell 7
   when installed. *Leaning: PowerShell 7 if installed, else Windows
   PowerShell; cmd when neither.*
4. **One app, two manifests** (WS10), or a Geng feature for dependencies by
   platform first. *Leaning: two manifests now.*
5. **The IME** (WS6): IMM32 first, TSF when needed. *Leaning: IMM32.*

## WS14 · Step 1 built: the text libraries for Windows (2026-11-09)

`packages/win32/build-text-libs.sh` builds FreeType 2.14.3 and HarfBuzz
13.2.1 for Windows, static, from the sources geng-lang's nixpkgs pin has,
into `vendor/win-text` with `pkg-config` files, in 27 s:

- FreeType's core, its bitmap, glyph, emboldening, box and variation
  calls, and the modules OpenType and TrueType faces need (TrueType, CFF,
  SFNT with its colour tables, the auto-hinter, the smooth renderer), with
  FreeType's own copy of zlib: no libpng, bzip2 or Brotli.
- HarfBuzz's one source file, compiled by the toolchain's `g++` with
  threads off; its object needs nothing but the C library and libgcc, so a
  Geng program's C link takes it.

`bench/windows/probe-text.c` linked against them by `clang` alone, as a Geng
build links (`-static`), is one 2.2 MB `.exe` that needs no DLL but
Windows' own, and on beelink1 drew the picture above byte for byte as the
build against nixpkgs' FreeType DLLs did.

Note for a Windows build: the toolchain's `pkg-config` wrapper reads
`PKG_CONFIG_PATH`, not its target-suffixed variable, when run outside a
Nix build, so a build sets both, as geng-lang's `run.py` does.

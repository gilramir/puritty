# Feature plan, from the November 2026 surveys

Gilbert researched what people complain about in other terminals, and what
the best settings screens do. The surveys are in `docs/research/`:

- `terminal-survey.md`: complaints and wishlists for Ghostty, Alacritty,
  Kitty, WezTerm, PuTTY, MobaXterm, Windows Terminal and Warp.
- `config-ui-survey.md`: the best and worst settings UIs, and how to save to
  a hand-edited TOML file. Its design for puritty is in `settings-ui.md`.

This document checks the terminal survey against what puritty already has
or has planned (`geng-plan.md` §6), and proposes where each remaining item
goes. Nothing here changes the phase plan until Gilbert agrees.

## 1. What the survey confirms

The survey's "biggest opening" is the work puritty already has planned.

| Survey item | puritty |
|---|---|
| Native tmux control mode on Linux; nothing but iTerm2 does it well | Phase 4, with tmux 3.8's floating panes. The survey makes this the headline feature. |
| Clipboard across local tmux → ssh → remote tmux | OSC 52 writes are in (§16). Add a phase 4 test that copies through that whole chain. |
| `xterm-ghostty` breaks remote hosts until terminfo is copied | Not a problem: puritty sets `TERM=xterm-256color`. Keep it that way, or fall back to it if puritty ever gets its own entry. |
| Fast startup, low input lag, correct UTF-8, true colour | Phases 1–3, with measurements in `geng-plan.md` §1. |
| Plain-text config you can keep in git | `config.toml` already, and the settings UI keeps it (see `settings-ui.md`). |
| No login, no telemetry | Already true. Say so in the README. |
| Pasting many lines shouldn't run them all | Bracketed paste is in. A warning before a multi-line paste into a shell without it is a small addition (§2). |

## 2. Gaps, and where they could go

| Gap | Size | Proposed home |
|---|---|---|
| **Scrollback search** | Medium: a search bar, matching over rows, highlights | After phase 4. Ghostty's users complained about its absence for years. |
| **Scrollbar** | Small | With search. |
| **Key bindings in the config**, including multi-key sequences | Medium | A `[keys]` section and a "Keyboard" page in the settings UI. Before the Windows product, since that needs bindings for ssh actions. |
| **Multi-line paste warning** | Small | Any time; one setting, on by default. |
| **Selection copied to the clipboard** (Gilbert's request, 2026-11-11), as PuTTY and MobaXterm do | Small | With the Windows product; `windows.md` WS27. An option, on by default on Windows. |
| **Key sounds** (Gilbert's request, §3) | Small to medium: audio is new | Soon, and the first new setting added through the settings UI. |
| **Jump between and fold command outputs** | Medium; needs shell integration (OSC 133) | Later. |
| **Pipe a pane's text to a command** (pull out URLs) | Small | Later. |
| **Inline images**: Sixel, Kitty graphics, iTerm2 | Large | Right after phase 4 (§4 below). |
| **Smooth scrolling, animated cursor** | Medium; better with the GPU renderer | After phase 5, if at all. |

### The Windows product: replacing PuTTY and MobaXterm

These are the survey's SSH items. They all belong to the Windows ssh client,
which `geng-plan.md` already says decides the settings window's design for
hosts:

1. A host list with groups whose settings (user, key, jump host) pass down to
   each host. Termius is the model.
2. Quick-connect without first saving a host.
3. Import from `~/.ssh/config`, PuTTY's registry sessions and MobaXterm's
   session file.
4. Passwords and key passphrases in the Windows credential store, never in
   `config.toml`.
5. File transfer inside the session: an SFTP panel or drag-and-drop.
6. Reconnect, restoring tabs, layouts and titles. tmux control mode does much
   of this for free when the remote end runs tmux.
7. None of MobaXterm's free-tier caps, which is easy since puritty has none.

X11 forwarding (MobaXterm's built-in X server) is out of scope.

## 3. Key sounds

Gilbert wants an option to play a sound while typing, off by default:

- `keyany.wav` for any key other than Enter;
- `keyenter.wav` for Enter.

Both are in `assets/sounds/`. They came from Q10 Editor (`q10.exe`):

| File | Length | Format |
|---|---|---|
| `keyany.wav` | 0.15 s | G.711 mu-law, 8-bit, 44.1 kHz mono |
| `keyenter.wav` | 0.37 s | PCM 16-bit, 22.05 kHz mono |

**The setting:**

```toml
[sound]
keys = false          # play a click for each key, and another for Enter
```

A volume setting can come later if the clicks are too loud.

**Decisions to make before building it:**

- **Which keys click.** Suggested: any key press that sends something to the
  program, including auto-repeat. Modifiers alone (Shift, Ctrl) don't click,
  and neither do paste or keys the IME holds while composing. When the IME
  commits text, one click for the commit.
- **Audio output.** puritty has none yet. On Mint, PulseAudio's simple API
  (`libpulse-simple`) also works on PipeWire through its Pulse layer, and it
  accepts mu-law directly. Playing must never block the event loop, so sounds
  go to a small audio thread or a non-blocking stream. A click that can't
  play (no audio server) is dropped silently. Typing must not wait on it.
- **ETX on RHEL8.** puritty runs on the VM there, so sound would play on the
  VM and probably not reach Gilbert's speakers. Check whether ETX forwards
  audio; if it doesn't, the feature is for Mint (and later Windows) only.
- **Licence.** The two files are Q10 Editor's. Using them in Gilbert's own
  builds is one thing; shipping them in a released puritty needs Q10's
  author's permission, or replacement sounds that puritty owns.
  `assets/sounds/` is the place for either.

## 4. Proposed order

Gilbert wants the settings UI soon, which moves it ahead of the Windows work
where `geng-plan.md` had it:

1. **Config reload**, moved up from phase 7: every setting applied to a
   running window. The settings UI rests on it.
2. **A settings schema** (`settings-ui.md` §2): one table describing every
   setting, which the decoder, the UI and the documentation all use.
3. **The settings window** on Linux, for today's settings.
4. **Key sounds**, the first new setting added through the window.
5. Phase 4 (tmux control mode), as planned.
6. **Images**, all three protocols (§5).
7. Search and scrollbar, key bindings, then the Windows product with hosts in
   the settings window.
8. **VDI mode** (§6), well after puritty works on Windows, and only what
   measurements justify.

## 5. Images

*Gilbert, 2026-11-06:* after phase 4, puritty shows images, and supports all
three ways programs send them, not just the one that suits tmux. Gilbert
uses tmux all the time; other users may not.

| Protocol | What a program sends | Who uses it |
|---|---|---|
| **Sixel** (DEC, 1980s) | A palette image (usually 256 colours), six pixel rows at a time, as text | gnuplot, img2sixel, chafa, lsix. tmux 3.4+ stores and redraws Sixel itself, so it's the protocol that survives tmux. |
| **Kitty graphics** | PNG or raw pixels in chunks, or a file or shared memory; placed, layered above or below text, deleted, animated | yazi, `kitty +kitten icat`, image.nvim, timg, chafa. Ghostty and WezTerm support it. |
| **iTerm2 inline images** (OSC 1337) | A whole PNG, JPEG or GIF file in base64 | imgcat, many scripts. WezTerm, mintty and Konsole support it. |

**One image layer, three front ends.** The core gets an image store and
*placements*: an image tied to a cell position, which scrolls, clears and
reflows with the text and survives a switch to the alternate screen and back.
The renderer draws placements: XRender uploads each image once and redraws
from the server's copy (important over ETX), and the GPU renderer gets the
same. Each protocol is then a decoder that adds images and placements.
Suggested order: the image layer with Sixel first (smallest, and what tmux
carries), then iTerm2's (a file decoder on the same layer), then Kitty
graphics (the largest: placements by id, z-order, deletion, chunked and
compressed transfer, Unicode placeholders, animation last).

**Things to settle in the survey that starts the work:**

- **tmux control mode.** How a control-mode client receives a pane's Sixel
  images, or whether it does: check tmux's source before designing, as
  phase 4 did for floating panes. Kitty and iTerm2 images reach puritty
  through tmux only with `allow-passthrough`, and break when panes move;
  that is tmux's limit, and puritty should handle it cleanly, not mend it.
- **Image decoders.** iTerm2's and Kitty's PNG, plus JPEG and GIF for iTerm2,
  and zlib for Kitty's compressed data. On RHEL8 every library is pinned
  (Q12), so a small bundled decoder (stb_image) may be simpler than libpng,
  libjpeg and giflib. Decide in the survey.
- **Safety.** Kitty's protocol can ask the terminal to read a file or shared
  memory by name. A remote program must not make puritty read local files:
  file and shared-memory transfer are limited to temporary files, or off,
  as Kitty itself does. Every image has a size limit, and all images
  together a memory limit (a setting, as Kitty's is), with the oldest
  dropped first.
- **Telling programs it's supported.** Sixel through the device attributes
  reply (attribute 4) and XTSMGRAPHICS; Kitty through its query action;
  iTerm2's through its own report. Programs like chafa pick a protocol from
  these answers.
- **The oracle.** Ghostty supports Kitty graphics but not Sixel. Where
  libghostty-vt has no answer, puritty's image handling needs its own tests
  (recorded sequences with expected placements, and rendered pixels).
- **ETX.** Measure bytes per image update there, as phase 2 measured text.

**Settings:** `[images] enabled = true`, and the memory limit. They appear on
the settings window's Advanced page.

## 6. VDI mode: puritty inside a remote Windows desktop

*Gilbert, 2026-11-06:* one of Gilbert's workflows is a Windows desktop reached
through Omnissa Horizon Client (VDI), with PuTTY or MobaXterm on it connecting
to a Linux host by ssh. Could puritty, running on that remote desktop, do
anything to make it better? This comes well after puritty works on Windows,
and only what measurements justify gets built.

**The limit.** Horizon's Blast protocol (and PCoIP) sends pixels: it captures
the remote desktop's screen, finds what changed and compresses it as images
or video. It never sees text, so puritty can't send text instead. It can
only make its pixels cheaper to send.

**What might help:**

1. **Change fewer pixels.** Redraw only changed cells (as on X11), no smooth
   scrolling or animation, and no cursor blink: a blinking cursor keeps that
   region from ever being still, and Horizon re-sends still regions sharper.
2. **Fewer frames in bursts.** Merge a flood of output into fewer updates
   (xterm's "jump scroll"): `frames.every_ms` around 33–50 instead of 16.
3. **No ClearType.** Its coloured edges compress badly and are smeared by
   video encoding, which keeps colour at lower resolution than brightness.
   Grayscale smoothing survives better; unsmoothed text compresses best and
   stays sharp under Horizon's lossless text mode.
4. **Flat colours.** No transparency, background images or gradients.
5. **Scrolling as a move.** Windows lets a program say "this region moved"
   when it presents a frame (DXGI's scroll rectangle, GDI's ScrollWindowEx),
   and passes that to screen-capture tools as a move. RDP turns moves into a
   copy instead of new pixels. Whether Blast does is unknown; if it does,
   scrolling costs almost nothing. The one possibly large win.

**Detecting Horizon.** A Blast session is usually not a Windows "remote
session" (`GetSystemMetrics(SM_REMOTESESSION)` is false). The Horizon agent
is believed to write `ViewClient_*` values, the protocol among them, under
`HKCU\Volatile Environment`; check that on Gilbert's VDI. With detection,
puritty switches to a VDI profile (items 1–3); a setting forces it on or
off, in case detection misses.

**What can't change.** Typing goes to the VDI, then to the Linux host, and
the echo comes back as pixels; puritty can't hide that delay, since
mosh-style local echo needs the terminal on Gilbert's own machine.

**Measurements first.** Horizon Performance Tracker, run inside the
session, shows Blast's bandwidth and frame rate. With the same workloads
(a `cat` of a large file; an idle prompt with a blinking cursor; scrolling
in `less`), compare:

1. PuTTY with Font quality "ClearType", "Antialiased" and "Non-Antialiased"
   (Window → Appearance). It doesn't need puritty, so it can be done
   whenever this work comes up, and shows whether item 3 matters.
2. Cursor blink on and off.
3. Once puritty runs on Windows: frame interval 16 vs 50 ms, and scrolling
   presented as a move vs as a full redraw (item 5).

Whatever doesn't show up in the numbers isn't built.


## 7. Seeing who has the mouse, and tmux's settings (Gilbert's ideas, 2026-11-08)

Two ideas from Gilbert's own use. Both are at their best with tmux control
mode (phase 4), where puritty knows each pane on its own.

### Who has the mouse, the selection and the clipboard

With tmux, ssh and an editor in between, it is hard to tell what a drag or
a paste will do: whether the program in the pane gets the mouse or puritty
selects text, whether tmux has `mouse on`, and whether a program's copy will
reach the local clipboard through OSC 52. Gilbert would use a helper he
checks now and then: an **overlay**, on a key, that labels each pane with
what it is doing, or a small **indicator** that shows it all the time.

What puritty already knows, from the core (`Term`):

- whether the program has asked for the mouse, and how (`mouseTracking`
  and its format: click, drag, all motion, SGR coordinates), so whether a
  drag selects in puritty or goes to the program, and that Shift+drag
  selects anyway;
- whether the alternate screen is shown (full-screen programs like vim
  and less);
- bracketed paste, so whether a paste arrives as one piece;
- OSC 52 clipboard requests (`Osc52.requests`): the last write and read,
  from which program, and whether puritty's settings let it through.

What each place shows:

- **Without tmux control mode**: one indicator for the whole window, since
  puritty sees a single screen. It cannot tell tmux's panes apart.
- **With control mode**, puritty keeps a core per pane, so the overlay can
  label each pane: "vim has the mouse", "tmux selects", "a copy here reaches
  your clipboard", or "a copy here stays in tmux", from the pane's own
  modes and tmux's `mouse` and `set-clipboard` options (read with
  `show-options`).

Size: small for the window-wide indicator, which needs only state the core
already has; medium for the per-pane overlay, after phase 4.

**A "Copied" flash** (Gilbert, 2026-11-09, from ChromeOS's Terminal app):
when a program's OSC 52 write reaches the clipboard, the Terminal app
shows a "Copied" badge over the screen for about half a second and fades
it out. Selecting text in tmux over ssh then says at once that the copy
got through, which is the question above answered at the moment it
matters. puritty knows the moment: the core counts OSC 52 requests
(`Osc52.requests`), and the app writes the clipboard when it takes them.
The same badge could say when one was refused ("Copy blocked" by
puritty's settings) or when a read was asked. Size: small, an overlay
drawn by the app with a timer, no new state in the core; it needs a
setting to turn it off.

### A tmux configuration helper

In control mode puritty talks to the tmux server, so it can ask it its
actual settings (`show-options -g`, `-s`, `-w`; `list-keys`), not what a
`.tmux.conf` says they might be. That makes possible a **settings window
for tmux**, built like puritty's own (`settings-ui.md`): each option with
its current value, what it does, and a control to change it.

- A change applies to the running server at once (`set-option`), so it can
  be tried before it is kept.
- Keeping it is the user's: puritty shows the lines to add to
  `.tmux.conf`, or writes them to a local file, but never edits a remote
  host's files on its own.
- It can start with the options that cause the confusion above (`mouse`,
  `set-clipboard`, `allow-passthrough`, `terminal-features`), where it also
  says what puritty will do with each value.

Open questions: tmux's options differ between versions, so the window has
to read what the server reports rather than a fixed list; and how much of
tmux's key table is worth editing in a GUI. Size: medium, after phase 4
and the settings window.

**Where they go in §4's order**: the window-wide indicator any time after
the settings window; the per-pane overlay and the tmux settings helper
right after phase 4, before images.

# Feature plan, from the November 2026 surveys

Gilbert researched what people complain about in other terminals, and what
the best settings screens do. The surveys are in `docs/research/`:

- `terminal-survey.md`: complaints and wishlists for Ghostty, Alacritty,
  Kitty, WezTerm, PuTTY, MobaXterm, Windows Terminal and Warp.
- `config-ui-survey.md`: the best and worst settings UIs, and how to save to
  a hand-edited TOML file. Its design for visiterm is in `settings-ui.md`.

This document checks the terminal survey against what visiterm already has
or has planned (`geng-plan.md` §6), and proposes where each remaining item
goes. Nothing here changes the phase plan until Gilbert agrees.

## 1. What the survey confirms

The survey's "biggest opening" is the work visiterm already has planned.

| Survey item | visiterm |
|---|---|
| Native tmux control mode on Linux; nothing but iTerm2 does it well | Phase 4, with tmux 3.8's floating panes. The survey makes this the headline feature. |
| Clipboard across local tmux → ssh → remote tmux | OSC 52 writes are in (§16). Add a phase 4 test that copies through that whole chain. |
| `xterm-ghostty` breaks remote hosts until terminfo is copied | Not a problem: visiterm sets `TERM=xterm-256color`. Keep it that way, or fall back to it if visiterm ever gets its own entry. |
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
| **Key sounds** (Gilbert's request, §3) | Small to medium: audio is new | Soon, and the first new setting added through the settings UI. |
| **Jump between and fold command outputs** | Medium; needs shell integration (OSC 133) | Later. |
| **Pipe a pane's text to a command** (pull out URLs) | Small | Later. |
| **Inline images** (Kitty, Sixel) | Large | Not planned. Only add if someone asks. |
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
7. None of MobaXterm's free-tier caps, which is easy since visiterm has none.

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
- **Audio output.** visiterm has none yet. On Mint, PulseAudio's simple API
  (`libpulse-simple`) also works on PipeWire through its Pulse layer, and it
  accepts mu-law directly. Playing must never block the event loop, so sounds
  go to a small audio thread or a non-blocking stream. A click that can't
  play (no audio server) is dropped silently. Typing must not wait on it.
- **ETX on RHEL8.** visiterm runs on the VM there, so sound would play on the
  VM and probably not reach Gilbert's speakers. Check whether ETX forwards
  audio; if it doesn't, the feature is for Mint (and later Windows) only.
- **Licence.** The two files are Q10 Editor's. Using them in Gilbert's own
  builds is one thing; shipping them in a released visiterm needs Q10's
  author's permission, or replacement sounds that visiterm owns.
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
6. Search and scrollbar, key bindings, then the Windows product with hosts in
   the settings window.

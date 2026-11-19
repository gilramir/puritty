# Claude Code in puritty: a survey

Gilbert, 2026-11-18: he uses Claude Code a lot and wants it to work
superbly under puritty, on Linux and on Windows, and puritty to stand out
for it where it can. Sections are CL1, CL2, and so on. Nothing here is
built; the proposals in CL6 are for Gilbert.

Sources: Claude Code's own documentation (terminal configuration,
fullscreen rendering, environment variables, mods' elements), its public
issue tracker (`anthropics/claude-code`), the Program Status Protocol's
specification, and Claude Code 2.1.326 (Linux) and 2.1.319 (Windows)
measured inside puritty.

## CL1 · How Claude Code decides what a terminal can do

At startup Claude Code asks the terminal: XTVERSION (`CSI > 0 q`), DA1
(`CSI c`, also the sentinel that ends the waiting), the kitty keyboard
protocol's flags (`CSI ? u`), DECRQM 2026 (synchronized output), DECRQM
1016 (mouse in pixels), Kitty's graphics query (`a=q`) and the Program
Status Protocol's (`OSC 7501 ; ?`). `claude --debug-file F` writes what
it found as one `Terminal capabilities:` line.

Some features it enables by what the terminal answers; others it
enables only for terminals it knows by name, `TERM_PROGRAM` or the name
XTVERSION gives, and the issue tracker carries a stream of requests to
add one terminal at a time:

| feature | how it is decided |
|---|---|
| kitty keyboard protocol, Shift+Enter | the `CSI ? u` probe (plain `claude`, since 2.1.272); `claude attach` by a `TERM_PROGRAM` allow-list only (#97501) |
| modifyOtherKeys | only with the kitty protocol, or a `TERM_PROGRAM` on the list (#96526) |
| synchronized output (DEC 2026) | the DECRQM probe; `CLAUDE_CODE_FORCE_SYNC_OUTPUT=1` otherwise |
| a mod's `Image` (Kitty graphics) | the graphics probe **and** an XTVERSION name of kitty 0.28+ or ghostty (#101306, #99566); `CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1` otherwise, for terminals with Kitty's Unicode placeholders |
| iTerm2 images | XTVERSION naming iTerm2 3.5+ |
| desktop notifications | only Ghostty, kitty and iTerm2 when detected; `preferredNotifChannel` (`iterm2`, `kitty`, `ghostty`, `terminal_bell`) otherwise |
| OSC 8 hyperlinks | a `TERM_PROGRAM` list (#109032, #108854, #96923); `FORCE_HYPERLINK=1` otherwise |
| strikethrough | by name; `CLAUDE_CODE_FORCE_STRIKETHROUGH=1` otherwise |
| OSC 9;4 progress | `TERM_PROGRAM` of iTerm2, Ghostty or ConEmu (#103022) |
| program status (OSC 7501) | the `OSC 7501 ; ?` probe, answered before DA1's reply (#105534) |

An unrecognized `TERM_PROGRAM` costs about 3 s at startup (#98832,
Herdr). puritty sets none (only `TERM=xterm-256color` and
`COLORTERM=truecolor`), and starts Claude Code without that wait
(measured: XTVERSION answered 110 ms after start).

## CL2 · Measured in puritty (2026-11-18)

Claude Code started inside puritty, with a configuration directory of
its own (`CLAUDE_CONFIG_DIR`, so unauthenticated, nothing sent), and
`--debug-file`:

| | Linux, puritty on X11 | Windows, puritty.exe, Claude Code through ConPTY |
|---|---|---|
| XTVERSION | `puritty 0.1.1` | `puritty 0.1.1` |
| kitty keyboard | yes (`CSI ? u` flags=0) | yes (flags=0) |
| extended keys | yes | yes |
| synchronized output | **yes** (DECRPM 2026 status 2) | **no** (status 0: ConPTY answers for itself) |
| mouse in pixels | yes (DECRPM 1016 status 2) | no (ConPTY) |
| Kitty graphics | **no**: the graphics reply was OK, but the name is not kitty or ghostty | **no**: no reply at all (ConPTY swallows APC) |
| iTerm2 images | no (the name) | no |
| program status | **no**: puritty does not answer `OSC 7501 ; ?` | no |

A first run inherited this shell's `TMUX` and `TERM_PROGRAM=tmux`, and
Claude Code took puritty for a tmux pane ("the terminal did not answer
as tmux"); a puritty window does not set them, so the measured runs
cleared them.

**What puritty lacks of what Claude Code can use** (`vt-core.md` VC9):
OSC 8 hyperlinks, desktop notifications (OSC 9, OSC 777, kitty's OSC 99),
OSC 9;4 progress, and OSC 7501. OSC 52 (the clipboard) it has.

## CL3 · The Program Status Protocol (OSC 7501)

Mitchell Hashimoto's protocol (revision 0.4, October 2026; spec at
superlogical.com/rex/docs/build/program-status): a program reports
`OSC 7501 ; state=… : kind=… : app=… : msg=<base64> ST`, `state` one of
`idle`, `working`, `blocked` (with `kind` `permission`, `question` or
`auth`), `done`, `error`, `clear`, with optional `id` (a path, for
sub-tasks), `progress` (0–100), `title`. A terminal answers the query
`OSC 7501 ; ? ST` with `OSC 7501 ; ? ST` (optionally listing its states
and kinds), keeps one record per id, drops `working` and `blocked` at
the program's exit or the next prompt (OSC 133 A), and decides itself
what to show. Reports are untrusted text: no control characters, never
markup, never echoed back; external effects (notifications, sounds) are
to be rate-limited.

Claude Code reports through it since 2.1.295: working, waiting on you
(`blocked`, by kind), done, per subagent too, and in a terminal that
answers the query it leaves the status glyph out of the tab title,
since the terminal shows the state itself. Of terminals (areweosc7501yet.com,
2026-11-18): iTerm2 has shipped it and kitty merged it; Ghostty,
WezTerm, Alacritty, foot and Windows Terminal have not. tmux refused it,
and inside tmux Claude Code asks tmux, so a pane reports nothing.

## CL4 · Windows: ConPTY in the way

A local Claude Code on Windows reaches puritty through ConPTY, which
answers some questions itself and drops others: synchronized output, the
graphics query and mouse in pixels all fail (CL2). The issue tracker
adds Shift+Enter arriving as Enter when libuv turns console input back
into VT (#92771), and stale fragments in the fullscreen renderer on
ConPTY hosts (the docs' `CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT=1`).

`CreatePseudoConsole` takes a flag, `PSEUDOCONSOLE_PASSTHROUGH_MODE`
(0x8, from microsoft/terminal PR #11264), with which the console passes
the program's sequences through; libraries retry without it when it is
refused. Which Windows builds take it is not documented and not measured
here.

Claude Code run on Linux and reached with puritty's own ssh client does
not go through ConPTY, and gets what the Linux column shows.

## CL5 · Other things the tracker shows

- **Emoji with VS16** (`➡️`): Claude Code counts one column, terminals
  two, and its redraw drifts a row (#84986). puritty draws two, as
  Ghostty does; nothing for puritty to change.
- **U+23F5** (⏵, the permission-mode marker) is in no common monospace
  font (#85021); puritty's guide already says which font has it
  (`docs/user/symbol-fonts.md`).
- **On X11 one copy writes the clipboard twice**, by OSC 52 and by
  `xclip`, and the two race for the selection (#96123). puritty answers
  OSC 52 by taking the CLIPBOARD; worth checking that the race does not
  leave puritty's copy over the newer one.
- **Korean, Japanese and Chinese input** issues are mostly Claude Code's
  own cursor placement (#75507, #101804, #103346); puritty draws the
  preedit at the cursor the program leaves, so it inherits them.
- **Fullscreen rendering and `tmux -CC`**: Claude Code chooses the classic
  renderer under iTerm2's `-CC` (where mouse and the alternate screen do
  not work), detected by iTerm2's name; under puritty's `-CC` it would
  run fullscreen in a pane, whose mouse and alternate screen puritty
  carries. Not yet measured.

## CL6 · Where puritty could stand out (for Gilbert)

1. **OSC 7501, the program status.** Answer the query; keep the records
   per tab; show the state on the tab (a spinner while working, a mark
   when Claude waits on you, done and error colored), in the window's
   title, and in Windows' taskbar (overlay icon, flash when blocked) and
   X11's urgency hint; ring the bell sound puritty already has when a tab
   not shown becomes blocked or done. Claude Code turns it on by itself,
   no setting; Ghostty, Windows Terminal and WezTerm do not have it yet.
   *Cost: a parser and a record table in the core, the tab drawing, the
   platform hooks. Under tmux it does nothing until Claude Code can be
   told to report there (#103022).*
2. **Desktop notifications**: OSC 9 (iTerm2's), OSC 777 (rxvt's, which
   Ghostty sends) and OSC 99 (kitty's), shown with the desktop's
   notifications (`org.freedesktop.Notifications` on X11, a toast on
   Windows), rate-limited. Then `preferredNotifChannel` set to one of
   them gives Claude Code's notifications, and 7501's `blocked` can
   notify by itself.
3. **OSC 8 hyperlinks**, Ctrl+click to open, as most terminals have; then
   `FORCE_HYPERLINK=1` turns Claude Code's links on.
4. **Pictures in Claude Code**: puritty draws Kitty's Unicode
   placeholders (IM35), so `CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1` should
   draw a mod's `Image` today; to be checked. The name gate itself is
   Claude Code's (#99566 asks to trust the probe instead).
5. **A guide page**, "Claude Code in puritty": what works by itself, the
   variables to set (`CLAUDE_CODE_FORCE_TERMINAL_IMAGES`,
   `preferredNotifChannel` once 2 exists, `FORCE_HYPERLINK` once 3
   exists), and why to leave `TERM_PROGRAM` unset.
6. **Windows**: try `PSEUDOCONSOLE_PASSTHROUGH_MODE` on beelink1; if the
   console takes it, a local Claude Code gets synchronized output,
   pictures and the mouse in pixels as on Linux.
7. **Claude Code in `tmux -CC`**: measure its fullscreen renderer in
   puritty's panes, where iTerm2's integration cannot run it.

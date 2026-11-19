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

## CL7 · OSC 7501 built (2026-11-18)

**What puritty does with it**:

- **The core** (`Vt.Status`, new, pure; `Vt.Osc`): `OSC 7501 ; ?` is
  answered `OSC 7501 ; ?` with the query's own terminator. A report
  replaces its id's record whole, `clear` takes an id and those under it
  (all, with no id), at most 256 records, the least recently updated
  going first. Everything the spec drops is dropped: an unknown state, an
  id that is not a path of `[A-Za-z0-9_.+-]{1,32}` segments, an `app`
  over 32 bytes, a `msg` or `title` over its size, not base64, or with a
  control character in it; a malformed pair is skipped, an unknown key
  ignored, a repeated key's last value taken. The bidirectional and
  invisible formatting characters are taken out of what is shown. The
  records are the terminal's (the alternate screen keeps them), RIS
  removes them, and a new prompt (OSC 133 `A` or `N`, ConEmu's `9;12`)
  drops `working` and `blocked`. 7501 takes the spec's 4,096 bytes, past
  the 2,048 Ghostty's limit gives other OSCs; one that filled the core's
  string may have been cut and is dropped whole. `Vt.programStatus`
  gives the most pressing record (blocked, error, working, done, idle),
  its app its own or its nearest ancestor's.
- **The window and its tabs** (`Main`): the title and each tab's label
  begin with the state's mark, ◔ working, ◉ waiting on you (`blocked`),
  ✓ done, ✗ error. When a tab comes to be blocked, done or failed while
  the user is not looking at it (the window not focused, or the tab not
  shown), the window asks for attention (`Window.attention`: X11's
  urgency hint in `WM_HINTS`, `FlashWindowEx` on Windows' taskbar) and
  the bell's sound (`[sound] bell`) rings, once for that change; the
  window stops asking once it has the focus. Under tmux's control mode
  and on puritty's own screen the title is theirs, unmarked.

**Measured**: eleven tests in the vt suite (185): the query and both
terminators; a report kept, its message decoded, replaced whole; the most
pressing shown, a child's app inherited; clear by id and clear all; six
reports dropped whole; a bad pair skipped, an unknown key ignored, a
repeated key's last; invisible characters taken out; a prompt dropping
working but keeping done; RIS and the alternate screen; a report past
2,048 bytes kept; the change count. Claude Code 2.1.326 in puritty now
says `programStatus=yes (probe: OSC 7501 reply)`. In puritty on Xvfb, a
program reporting `working` then `blocked`: the title went "◔ t", then
"◉ t"; with the focus moved away, `WM_HINTS` gained the urgency bit and
the log said "tab 0 is blocked: attention asked"; given the focus back,
the bit was cleared.

**Not covered**: Claude Code inside tmux asks tmux, which does not
answer, so a tmux pane reports nothing (#103022); Windows, where ConPTY
stands between (CL4), not yet tried.

**CL6's ConPTY passthrough, tried (CL4)**: `CreatePseudoConsole` with
`PSEUDOCONSOLE_PASSTHROUGH_MODE` (0x8), behind a variable, on beelink1
(Windows 11 25H2, build 26200): Claude Code's capability line was the
same as without it (synchronized output, the graphics reply and mouse
pixels still lost). The console in Windows itself does not pass through;
Windows Terminal ships its own (`conpty.dll` and `OpenConsole.exe`, MIT),
which is where the mode lives. Taking it would mean shipping those two
files with puritty: Gilbert's call. The experiment was taken back out.

## CL8 · Desktop notifications built (2026-11-18)

- **The core** (`Vt.Notice`, new, pure): OSC 9 is iTerm2's notification,
  its text the body, unless it is one of ConEmu's commands (a number from
  1 to 12, then `;` or the end: `9;4` progress, `9;12` a prompt), as
  Ghostty reads it; OSC 777 `notify;title;body` (rxvt's, Ghostty's), the
  body keeping its `;`; OSC 99 (kitty's), metadata `i` (id), `p`
  (`title`, the default, or `body`), `e=1` (base64) and `d=0` (more to
  come), parts joined by id until one completes it. Control characters
  are taken out, the title cut at 256 characters and the body at 1,024;
  an empty one is none. At most 16 wait on a terminal for the embedder,
  `Vt.takeNotices`. OSC 777 is no longer an ignored sequence in the
  diagnostic log's test (its example became OSC 5113).
- **The app** (`Main.noticesShown`, `Notify` per platform): each turn the
  notices are taken from every tab, one with no title given its tab's
  label; the newest is shown, at most one every 3 s, the others dropped
  and said in the log. On Linux by `notify-send`, which hands it to the
  desktop's notification service; where it is not installed the log says
  so. On Windows by the notification area's balloon from puritty's icon
  (`Window.notify`, `Shell_NotifyIconW`, shell32 now linked), which
  Windows 10 and 11 show as a toast; the icon goes when puritty ends.

**Turned off** (Gilbert, 2026-11-18): `[notifications] desktop = false`
(on by default; "Desktop notifications" on the settings window's Program
page, English and Korean) takes the notices and shows none, the log saying
how many; an app test holds the default and the setting.

So Claude Code's notifications reach the desktop in puritty with
`preferredNotifChannel` set to `"iterm2"` (OSC 9), `"ghostty"` (OSC 777)
or `"kitty"` (OSC 99) in `~/.claude/settings.json`; left at `auto` it
sends none to a terminal it does not know.

**Measured**: seven tests in the vt suite (192): OSC 9's text; ConEmu's
`9;4`, `9;12` and `9;1` not notifications; a text that only starts with a
number one; OSC 777 with `;` in its body; OSC 99 alone, and in two parts
by id with a base64 body; control characters out and an empty one none;
taking empties. In puritty on Xvfb, with a `notify-send` that records its
arguments: OSC 777 "Claude Code" / "Claude is waiting for your input"
sent as given; OSC 9's `9;4;1;50` not sent; two OSC 9s a second later
dropped (one shown less than 3 s before); one after the pause sent,
titled "shell", its tab's label. On beelink1, PowerShell in puritty.exe
writing OSC 9 through ConPTY (which passes it): the toast "puritty.exe",
"shell", "Claude is waiting for your input".

## CL9 · OSC 8 hyperlinks built (2026-11-18)

- **The core**: a link is part of a cell's style (`Attrs.link`, its place
  in the terminal's `links` and one more), kept out of the style's key as
  the underline color is and compared when a style is interned, so the
  style cache (keyed without either) is not used for a linked pen. OSC 8
  `params ; URI` gives the pen a link, found again by its URI and `id`
  param (two of the same are one link), until an OSC 8 with no URI ends
  it; no SGR, `0` included, ends it, and an erase writes plain cells, so
  no erased cell is linked. A URI with a space or anything but printable
  ASCII is no link; past the 4,096th a new one ends the link instead. The
  links reflow and scroll back with their cells, as their styles do; RIS
  forgets them. `Vt.linkAt back point` reads the link of a cell in the
  view, `TmuxMode.linkAt` the topmost pane's under the pointer.
- **Ctrl and the left button** on a link open it, where the program does
  not take the mouse; with Shift too where it does (its own a plain
  Ctrl+click then is: Claude Code's fullscreen renderer opens its links
  so itself). In tmux's control mode, the pane's link. Only a web
  (`http`, `https`), mail (`mailto`) or this machine's file link
  (`file:///`, `file://localhost/`) is opened (`Links.openable`), by
  `xdg-open` on Linux and the shell's "open" on Windows
  (`Window.openLink`, `ShellExecuteW`); anything else is refused and said
  in the log.
- **`FORCE_HYPERLINK=1`** is in a local program's environment, beside
  `TERM` and `COLORTERM`: what Node's `supports-hyperlinks` reads, so
  Claude Code (run in puritty, not over ssh) prints its links as OSC 8.

**Measured**: seven tests in the vt suite (199): the cells between OSC 8
and its end linked, the others not; SGR (0 too) inside a link keeping it;
an erase writing no link; same URI and id one link, another id another; a
URI with a space no link; a link reflowed at 10 columns and found in the
scrollback; RIS. One app test (427): web, mail and local files opened;
another host's file, `javascript:` and `vscode:` not. In puritty on Xvfb
with an `xdg-open` that records what it is given: Ctrl+click on an OSC 8
link opened `https://example.com/claude`; a plain click opened nothing;
Ctrl+click on a `javascript:` link was refused ("not a web, mail or local
file link"); the same link in a `tmux -CC` pane opened from the pane.
Not tried on Windows, where it would open a browser on Gilbert's desktop;
the Windows build compiles.

**Not done**: a link is not drawn differently (most programs underline
their links themselves; Ghostty underlines one under the pointer), and
the pointer does not change over one.

## CL10 · Measured with Gilbert's own Claude Code (2026-11-18)

Gilbert let these run with his login (his `~/.claude`), in puritty on
Xvfb, from a scratch folder (trusted once, which Claude Code records in
`~/.claude.json`); nothing was sent to the API.

- **A mod's picture draws in puritty.** A local mod whose `/imgtest`
  opened a pane with a 160×160 red PNG (`Image`, `source.png`), Claude
  Code 2.1.326 started with `CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1`: the
  debug log said `kittyGraphics=yes (env: CLAUDE_CODE_FORCE_TERMINAL_IMAGES)`,
  and the pane showed the square, 18,496 red pixels in puritty's frame.
  So Kitty's Unicode placeholders (IM35) are what Claude Code needs; only
  its list of terminal names keeps it from drawing unasked (CL1).
- **The fullscreen renderer works in puritty's `tmux -CC` panes**, where
  Claude Code's docs say it does not in iTerm2's (the mouse wheel does
  nothing, a double click corrupts the terminal). Claude Code 2.1.328 in a
  tmux 3.x `-CC` pane with `CLAUDE_CODE_NO_FLICKER=1` (Gilbert's own
  setting is the classic renderer, `"tui": "default"`): the prompt held at
  the pane's foot on the alternate screen, `/` opened the command list, and
  a click on its `/dataviz` row put `/dataviz` in the prompt, so the click
  reached Claude Code through tmux. The wheel was not tried (nothing to
  scroll in an empty conversation). In the pane Claude Code saw
  synchronized output (tmux's answer) and no kitty keyboard (tmux does not
  pass `CSI ? u`), and asked for tmux's `focus-events`.
- **Its opening screen** shows the account's plan ("Claude Ultra") and the
  working folder under the logo, and here the debug log's path and a note
  that this session's environment (`CLAUDE_CODE_CHILD_SESSION`, inherited)
  turned transcripts off. A shot for the website leaves those out
  (`CLAUDE_CODE_HIDE_CWD=1`, no `--debug-file`, a clean environment).

## CL11 · The website's shot, and what making it found (2026-11-18)

**The shot** (`docs/images/claude-code.png`, on the home page and the new
guide page `docs/user/claude-code.md`, CL6 #5): one puritty window on
Xvfb (144 dpi, Fira Code 11, Ghostty's colors), three tabs each running
Claude Code 2.1.328 with Gilbert's login: a question about a notes folder
answered (✓), an LRU cache being written and tested (◔), and the shown
tab asking leave to run a git command (◉), with the seashell plot
(`site/static/plots/seashell.gp`, rendered to a PNG) drawn in the
conversation by a local mod. So that no path or name of Gilbert's shows,
puritty ran under `bwrap` with the demo folder bound at `/home/you` and an
`/etc/passwd` whose account is `you`; the logo and plan line scrolled off
before the capture. Nothing was approved that would change anything; no
session committed.

**Found**:

- **A mod's `Image` with a `file` source is refused**: Claude Code sends
  it as Kitty's file medium (`t=f`, the terminal reads the path), and
  puritty takes only pictures sent inline, so Claude Code logged "the
  terminal refused its source: EINVAL: unsupported medium" and left the
  row blank. The mod in the shot sends the PNG's bytes (`source.png`).
  *Since done*: Gilbert asked for files to be read for local programs,
  with a setting, on by default (`images-kitty.md` KG9); such a mod's
  picture now draws.
- **A mod's hooks module imports only its own files and `claude-code`**:
  no `node:fs`, so a mod that shows a file builds the bytes into a module
  beside it.
- **The placed row** (`$.ui.place`, drawn at the `Placed` site) is where
  a picture sits in the conversation and scrolls with it, in the classic
  renderer; a pane cannot be opened without focus at `session.start`
  (`focus: false` throws).
- **`CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1`** is still needed (CL10): without
  it the row kept its room and drew only its alt text.

# tmux and puritty: a survey of tmux 3.8 (2026-11-11)

Gilbert, 2026-11-11: analyze the latest tmux and survey what puritty's
integration with it could be. tmux control mode is already phase 4 and the
headline feature (`feature-plan.md` §1, `geng-plan.md` phase 4), and
`synthesis.md` §7 planned it from WezTerm's and Ghostty's code. That plan
left several questions "to be read from tmux's source when this is built".
This survey reads tmux 3.8 for them, records a real 3.8 session, and adds
the other half: tmux running *inside* puritty, which Gilbert does every day.
Sections are TM1, TM2, and so on; the questions for Gilbert are last
(TM10), each with a leaning.

What was measured is marked so. What was read in tmux's source has a
`file:line` into the 3.8 tag; what was reasoned and not run is marked
"inferred". Nothing here connected to another host or touched a tmux
server but the test's own sockets.

## TM1 · Which tmux

| | where | date | notes |
|---|---|---|---|
| **3.8** | tag `3.8` (7f2a35ad), cut from a release branch, so not in master's history | 2026-10-08 | what users get; what this survey reads |
| 3.8a | branch `release_3.8a`, `configure.ac` says 3.8a, no tag yet | last commit 2026-11-09 | 9 fixes past 3.8 (TM7) |
| master | f8426e7d, `configure.ac` says `next-3.9` | 2026-11-10 | 518 commits past 3.8, many of them master's copies of 3.8's fixes. Images are the big change (TM7) |
| nixpkgs-unstable | `tmux-3.8` | — | the binary measured here (`/nix/store/k111lnbq…-tmux-3.8`) |
| puritty's devbox | 3.7c | pinned 2026-10-23 | to move to 3.8 when phase 4 starts (`geng-plan.md` phase 4) |
| Gilbert's hosts | 3.6 | — | RHEL8 and RHEL9 (Q11); the floor stays 3.2 |

3.8's own changes that matter here: floating and modal panes grown up,
layouts as a JSON subset (`new-layouts`), hooks rebuilt on events with
monitors, built-in light and dark themes with the outer terminal's theme
reported to panes, OSC 133 turned into events, `pane_private_modes`,
`capture-pane -I`, `display-panes` as a mode, `mouse` on by default, and
the `active-pane` client flag removed.

## TM2 · Where puritty and tmux meet

1. **tmux inside puritty** (today). puritty is tmux's *outer terminal*:
   tmux asks it questions on attach and picks features from the answers.
   Small work, and it helps every tmux user now (TM4).
2. **tmux control mode** (phase 4). `tmux -CC` turns the pty into a line
   protocol; puritty draws each tmux window as a tab and each pane as a
   split, with its own scrollback, selection and search (TM5, TM6).
3. **Control mode through the built-in ssh client.** On Windows there is no
   local tmux, and reconnecting a dropped session is a product feature
   (`feature-plan.md` §2 item 6). `tmux -CC attach` over puritty's own ssh
   channel gives a session that outlives the connection, and on
   reconnect the window comes back as it was (TM8).

## TM3 · Measured on nene

The tools are in `bench/tmux/`: `record.py` records a `-CC` session from a
list of commands, and `attach.py` attaches an ordinary client on a pty,
answers its queries in one of three ways and times a lone Esc. Both use
their own socket (`-L puritty-bench-tmux`) and kill only that server.

**A control-mode recording**, 80×24, `-f /dev/null` (measured):

- Entry is `ESC P 1000 p` straight followed by the reply to the session's
  own command (`%begin … 0`), then `%sessions-changed`,
  `%session-changed $0 0`, `%window-renamed`, `%output`.
- After `refresh-client -f new-layouts`, `list-windows -F
  '#{window_layout}'` gives
  `{"V":2,"L":{"t":"h","w":80,"h":24,"x":0,"y":0,"c":[{"t":"p","w":40,"h":24,"x":0,"y":0,"l":0,"i":0,"I":"%0"},{"t":"p","w":39,"h":24,"x":41,"y":0,"a":true,"i":1,"I":"%1"}]}}`;
  before it, `8205,80x24,0,0{40x24,0,0,0,39x24,41,0,1}`.
- `new-pane` (floating) and `new-pane -O` (modal) add leaves with `"z"` to
  the same `"c"` array, and `%layout-change`'s last field becomes `*O`
  while a modal pane is open. With `!new-layouts` the same window is the
  old string with **the floating panes left out**; their `%output` still
  arrives.
- Bytes below 0x20 and `\` are octal-escaped. **Everything else, EUC-KR
  included, arrives raw**: `printf '\301\326\274\272'` came through
  `%output` byte for byte. `capture-pane` of the same line gives U+FFFD in
  their place: tmux's grid holds UTF-8 cells, so EUC-KR text in its history
  is lost (TM8).
- `pause-after=1` with a reader that stops for 3 s on `seq 1 3000000`:
  tmux sent `%pause %0` in 2 runs of 3, and after `refresh-client -A
  '%0:continue'` and `%continue %0`, no more output arrived. The bytes in
  between are gone and the pane has to be captured again (TM5.7).
- `refresh-client -A %0:continue` without quotes is `parse error: syntax
  error` in 3.8; quoted it works.
- `refresh-client -B 'dead:%0:#{pane_dead}'` gave
  `%subscription-changed dead $0 @0 0 %0 : 0`.

**A plain attach** with `TERM=xterm-256color` (measured). On attach,
tmux 3.8 sent: DA1 `CSI c`, DA2 `CSI > c`, XTVERSION `CSI > q`, DECRQM
`CSI ? 2026 $ p`, `CSI ? 996 n`, `OSC 10;?`, `OSC 11;?`, `CSI 18 t`,
`CSI 14 t` (and `CSI 22;0;0 t`, a title push). Each case was run three
times; a lone Esc reaches the pane after:

| the terminal answers | Esc 1 s after attach | Esc 6 s after | `client_theme` |
|---|---|---|---|
| nothing | 507 ms | 507 ms | (empty) |
| what puritty answers today: DA1, DA2, XTVERSION, DECRQM, 18t, 14t | 507 ms | 11–16 ms | (empty) |
| that, plus `OSC 10/11` colors and `CSI ? 997 ; 1 n` to 996 | 16 ms | 16 ms | dark |

The cause is in `tty_keys_next` (`tty-keys.c:1002-1009`): while any query
is unanswered, tmux waits 500 ms before taking an Esc as Esc, and a 5 s
timer gives up on them (`tty.c:312-323`). tmux asks for the colors again
after a theme report and after a resize 30 s or more since the last ask
(`tty.c:428-450`), so it is not only at attach.

## TM4 · tmux inside puritty

### TM4.1 · What tmux asks, and what puritty answers

| tmux sends | tmux uses it for | puritty today | gap |
|---|---|---|---|
| DA1 `CSI c` | parameters 4 sixel, 21 margins, 28 rectfill, 52 clipboard (`tty-keys.c:1515-1531`) | `CSI ?62;22c` (`vt/src/Vt/Dispatch.geng`, `primaryAttributes`) | claim **21**: puritty has DECSLRM (`vt-core.md` §VC13), and tmux then turns margins on. 52 is already given by the `xterm*` row |
| DA2 `CSI > c` | only 77 mintty, 84 tmux, 85 rxvt (`:1652-1663`) | `CSI >1;0;0c` | none needed |
| XTVERSION `CSI > q` | a fixed list of name prefixes: `iTerm2 `, `tmux `, `XTerm(`, `mintty `, `foot(`, `WezTerm `, `ghostty `, `Rio ` (`:1724-1739`); master adds `kitty(` | `DCS >|puritty ST` | no match, so no default feature list. Add a version (`puritty 0.1`): every prefix ends in a space or `(` |
| DECRQM `?2026` | sync | `CSI ?2026;2$y` | none: sync is detected |
| `OSC 10;?`, `OSC 11;?` | the background, to guess light or dark; and the Esc wait (TM3) | answered only after a program set the color (`vt/src/Vt/Osc.geng`, `dynamicColors`) | **answer from the configured look** |
| `CSI ? 996 n`, `CSI ? 2031 h` | the theme now, and on each change | 2031 recorded; 996 not answered, 997 never sent | **answer 996, and send `CSI ? 997 ; 1/2 n` under 2031 when the look changes** |
| `CSI 18 t`, `CSI 14 t` | cell size in pixels, for sixel | answered | none |
| `OSC 4;N;?` | a pane's palette question | answered | none |
| `OSC 52;;?` | `get-clipboard request` only | asked of the user, default deny | by design |

### TM4.2 · Features

tmux turns a feature on from its table of known terminals, the
`terminal-features` option (default `xterm*:clipboard:ccolor:cstyle:focus:title`),
terminfo, `COLORTERM`, and the replies above (`tty-features.c:509-529`,
`tty-term.c:618-683`). With `xterm-256color` and puritty's replies,
`client_termfeatures` was measured as
`bpaste,ccolor,clipboard,cstyle,focus,sync,title` (with 256 and RGB from
terminfo and `COLORTERM`).

| feature | escape | puritty supports | detected | to do |
|---|---|---|---|---|
| extkeys | `CSI >4;2m`, keys as `CSI 27;m;c~` | yes (modifyOtherKeys 2) | no | users set it (TM4.3) until a row exists |
| usstyle | `CSI 4:x m`, SGR 58/59 | yes, drawn | no | same |
| overline | SGR 53 | yes, drawn | no | same |
| margins | `?69`, DECSLRM | yes | no | DA1 21 |
| hyperlinks | OSC 8 | **no** (ignored; `vt-core.md` §VC9) | no | build OSC 8 first |
| osc7 | OSC 7 | **no** | no | build first |
| progressbar | OSC 9;4 | **no** (only `9;12`) | no | build first |
| rectfill | DECFRA | no | no | leave DA1 28 unclaimed |
| sixel | DCS sixel | no (after phase 4) | no | then DA1 4 |

`vt-core.md` §VC9's "not started" list is partly stale: OSC 52, OSC 133,
the kitty key flags and mode 2026 are built.

### TM4.3 · What to do

In order, all small:

1. Answer `OSC 10/11 ?` from the look's foreground and background when no
   program has set them. Measured effect: Esc waits 16 ms, not 507, for the
   first 5 s after attach, and tmux knows the background (TM3).
2. Answer `CSI ? 996 n` with `CSI ? 997 ; 1 n` (dark) or `; 2 n` (light),
   from the look's background, and send it unasked under mode 2031 when the
   look changes (config reload). tmux 3.8's themes and the panes' own 996
   then follow puritty.
3. Add 21 to DA1.
4. Give XTVERSION a version.
5. Until tmux knows puritty, say in the user guide:
   `set -as terminal-features 'xterm*:extkeys:usstyle:overline:margins'`
   and `set -g extended-keys on`.

A "puritty" row in tmux's `tty_default_features` and its XTVERSION list is
how Ghostty and Rio got theirs (TM10 question 3).

## TM5 · Control mode in 3.8: the protocol

This corrects and completes `synthesis.md` §7.1. Read from the 3.8 tag
unless marked.

### TM5.1 · Entry and exit

- `-CC` makes the client put the tty in raw mode with `ONLCR` and `ICRNL`
  (`client.c:343-358`), so lines reach puritty ending `\r\n` (inferred).
- The server writes `ESC P 1000 p` with no newline (`control.c:1025-1028`),
  then lines.
- Exit is `%exit` or `%exit <reason>` (`detached`, `server exited`,
  `too far behind`, …; `client.c:184-220`), then ST, `ESC \`
  (`client.c:425-429`). An empty line from puritty means detach
  (`control.c:712-715`).
- **tmux does not refuse `-CC` inside a tmux pane** (`cmd-new-session.c:190-198`):
  puritty guards against it itself.

### TM5.2 · Replies

- `%begin|%end|%error <time> <number> <flags>`. The number comes from one
  counter for the whole server (`cmd-queue.c:713`), so match by equality,
  not by counting. Flags is 1 for this client's own commands, 0 for the
  command on its argv and for hooks.
- `a ; b` on one line gives two blocks.
- **Notifications are held until the outermost `%end` (new in 3.8, issue
  5458; `control.c:530-580`), except `%message`, which is written at once.**
- `run-shell` (without `-b`) and `wait-for -E -v` write their output as
  bare lines *after* `%end` (inferred, `cmd-queue.c:652-656`), and hold
  the client's later commands meanwhile.
- More than 64 MiB of unread replies, or (without `pause-after`) pane
  output 300 s old, ends the client with `%exit too far behind`
  (`control.c:134-137`, `607-612`).
- **A pane's text can forge a reply line.** `capture-pane -p` output is
  written raw (`cmd-capture-pane.c:446`), so a captured line reading
  `%end <t> <n> 1` ends the block early (inferred). Capture with a line
  prefix (`-L` or `-F`), and start every `-F` format with a fixed literal.

### TM5.3 · Notifications

All of 3.8's, with what they carry (`control-notify.c`, `control.c`):
`%output`, `%extended-output %p <age-ms> : …`, `%pause`, `%continue`,
`%layout-change @w <layout> <visible layout> <flags>`,
`%window-pane-changed @w %p`, `%window-add`, `%window-close`,
`%window-renamed` and their `%unlinked-…` forms, `%session-changed`,
`%client-session-changed`, `%client-detached`, `%session-renamed $s name`
(the man page says `name` alone; the code sends the id too),
`%sessions-changed`, `%session-window-changed`, `%pane-mode-changed`,
`%paste-buffer-changed`, `%paste-buffer-deleted`,
`%subscription-changed`, `%config-error`, `%message`, `%exit`.

- None is new in 3.8. 3.8's new events (`pane-command-finished`,
  `window-zoomed`, `pane-moved`, …) reach a control client only through a
  hook or a subscription.
- Several are server-wide, not filtered to the client's session:
  `%window-pane-changed`, `%session-window-changed`, `%pane-mode-changed`,
  `%paste-buffer-*`, `%client-detached`. Filter by id.
- Unknown lines are logged and skipped, never fatal (WezTerm's mistake,
  `synthesis.md` §7.2).

### TM5.4 · `%output`

- The pty's bytes as the program wrote them, taken before tmux parses
  them (`window.c:1651-1655`), with bytes below 0x20 and `\` as `\ooo`
  (`control.c:829-840`). Measured: high bytes pass raw (TM3).
- One write can be split over several lines at any byte
  (`control.c:943-945`): a UTF-8 or escape sequence can straddle them.
  Unescape into a per-pane byte stream.
- **tmux has already answered the program's queries** (DA, DECRQM, OSC
  10/11, …; `input.c`). The pane's terminal in puritty must not answer
  what it sees in `%output`. Colors for a pane come from
  `refresh-client -r %p:<report>` (`cmd-refresh-client.c:140-173`).
- A mode's screen (copy mode, choose-tree, display-panes) is never in
  `%output`: `%pane-mode-changed` says a mode began, `#{pane_mode}` which,
  and `capture-pane -M` gives its text (inferred). A native client draws
  its own copy mode and search, which is what puritty wants anyway.

### TM5.5 · Client flags

`refresh-client -f` (or `attach -f`), comma-separated, `!` to clear
(`server-client.c:3100-3158`): `pause-after[=N]` (N in seconds),
`no-output`, `wait-exit`, `new-layouts` (3.8), `read-only`,
`ignore-size`, `no-detach-on-destroy`. **Unknown names are ignored without
an error**, so puritty can always send `new-layouts` and parse whichever
format comes back: JSON starts with `{` (`layout-custom.c:1106`). No
version check is needed for it.

### TM5.6 · Layouts

- **v1**: `CCCC,` and a cell: `WxH,X,Y` plus `,N` for a pane, `{…}` for
  left-right, `[…]` for top-bottom. The checksum is a 16-bit rotate-and-add
  over the text after the comma (`layout-custom.c:270-279`).
- **v2** (`new-layouts`): `{"V":2,"L":cell}`. A cell has `"t"` (`h`, `v`
  or `p` for a pane), `"w"`, `"h"`, `"x"`, `"y"`; a node has `"c"` with
  two or more children; a pane has `"a":true` (active) or `"l":n` (its
  place in the last-used list), `"i"` (index), `"z"` when floating, and
  `"I":"%id"` (`layout-custom.c:30-56`, `343-400`). Integers only, no
  null, depth at most 200 (`json.c`).
- **A floating pane is a sibling leaf inside the tiled tree**, with `"z"`:
  `z:0` is the topmost (`layout.c:1503-1527`, `layout-custom.c:312-338`).
  It is drawn over the tiled panes at its own `x,y`, not laid out by its
  parent. Focusing a floating pane raises it with only a
  `%window-pane-changed`, no `%layout-change` (inferred, `window.c:834-839`):
  puritty raises it on that.
- **Modal**: not in the layout. `%layout-change`'s flags field carries `O`
  (and `Z` for zoom); `#{window_modal_pane}` says which. While it is open,
  puritty sends keys only to it (keys sent with `send-keys -t` go wherever
  they are aimed; inferred).
- **Zoom**: the layout field is the saved, unzoomed tree; the visible
  field is what to draw.
- An old-layout client gets the tree with floating leaves removed, or
  `0000,` if nothing tiled is left (`layout-custom.c:445-553`); measured
  in TM3.

### TM5.7 · Sizing and flow control

- `refresh-client -C WxH` sizes the client; `-C @w:WxH` one window, `-C
  @w:` clears it; 1 to 10000 (`cmd-refresh-client.c:62-105`). A control
  client counts for sizing only after its first `-C` (`resize.c:109-112`).
  `window-size` defaults to `latest`. Floating panes are clamped back into
  a smaller window (`layout.c:772-800`).
- `pause-after=N`: a pane whose oldest unsent output is older than N s is
  paused, its queue thrown away, `%pause` sent (`control.c:601-606`).
  `refresh-client -A '%p:continue'` (or `on`) restarts from *now*; the
  bytes in between are lost (measured, TM3), so puritty captures the pane
  again on `%continue`.
- If every client is a control client that is behind on a pane, tmux stops
  reading that pane's pty and the program blocks (`server-client.c:2061-2129`).
  That is the right back-pressure for one slow link.

### TM5.8 · Rebuilding a pane

- `capture-pane -p -e -N -S - -E - -P -t %p` gives history, screen and any
  half-received escape; `-a` the saved alternate grid, `-I` (3.8) the time
  each line entered history, `-F` line flags, `-H` hyperlinks.
- 3.8's `#{pane_private_modes}` lists the DECSET modes that are on (1, 6,
  7, 12, 25, 1000-1006, 2004, 2026, 2031; `format.c:2156-2205`). With
  `cursor_x/y`, `cursor_shape`, `alternate_on`, `scroll_region_upper/lower`,
  `pane_tabs`, `keypad_flag` and the mouse flags, that is most of a
  pane's state in one `list-panes -F`. Not available: the current SGR pen,
  G0/G1, a DECSC on the main screen (inferred).
- **The attach race** (`synthesis.md` §7.3 item 6): reply lines queue
  behind earlier output, and output is queued and parsed in the same step
  (`control.c:466-483`, `window.c:1651-1655`). So everything before the
  capture's `%begin` is in the capture: drop it, apply the capture, feed
  the `-P` bytes, then carry on (inferred).

### TM5.9 · Input, subscriptions, OSC 133, images

- `send-keys -H` sends bytes as they are; invalid hex is skipped with no
  error (`cmd-send-keys.c:123-129`). A pane in a mode takes keys in the
  mode's table. Mouse reports are puritty's to encode for the pane's mode
  and send with `-H`; paste likewise, with the 200~/201~ brackets when
  2004 is on.
- `refresh-client -B name:what:format` polls a format each second and
  sends `%subscription-changed` when it changes (`monitor.c`). The value is
  raw, so a format that can hold a newline breaks the line (inferred).
- OSC 133 is in `%output` raw, so puritty sees prompt marks per pane
  itself, as it does for a local shell. That is better than 3.8's
  `pane-command-*` events, which a control client gets only as hooks.
- Sixel, Kitty and iTerm2 images arrive raw in `%output`. Images drawn
  before attach cannot be had again: `capture-pane` reads text only
  (inferred, TM7 for master).

## TM6 · What changes in phase 4's plan

`synthesis.md` §7.3 holds, with these changes from TM5:

1. **Send `new-layouts` always** and parse both formats by their first
   byte. Floating panes become surfaces over the tiled tree, ordered by
   `z`, raised on `%window-pane-changed`. The modal pane, from flag `O`,
   takes all keys while it is open.
2. **Match replies by number**, and treat bare lines after `%end` as
   belonging to that command. Prefix every capture and `-F` format.
3. **The pane terminals answer nothing.** Queries in `%output` were
   already answered by tmux. Puritty's look reaches the panes by
   `refresh-client -r` (colors) and its theme by the client's 997 (TM4).
4. **Flow control is `pause-after`** with a capture on `%continue`, which
   neither WezTerm nor Ghostty does.
5. **Guard `-CC` inside tmux** (`$TMUX` set in the shell that ran it, or
   tmux's own DCS arriving inside a pane's `%output`).
6. **Quote pane ids** in commands (`'%0:continue'`).
7. **Filter server-wide notifications** by session and window id.
8. **Copy mode and search are puritty's own** in control mode, on the
   pane's history from the capture plus what arrived since. tmux's modes
   do not reach the client.
9. The floor stays 3.2 (Q11). On 3.6, where Gilbert's hosts are, nothing
   above needs 3.8 except floating panes, which 3.6 does not have.

## TM7 · 3.8a and master

**3.8a** (not tagged yet): tmux respects terminfo `ncv` (measured:
`xterm-256color` has none, so nothing changes under puritty);
padding cells of compact wide characters are width 0; black and white
swapped in the light theme; crash fixes. No control-mode fix from master
is backported.

**master**, for a 3.9 with no date (inferred: early 2027 at 3.6 → 3.7 → 3.8's
pace):

- **Images, both ways.** tmux decodes Sixel and Kitty graphics into RGBA,
  keeps placements in the pane's grid (so they scroll, survive copy mode
  and reflow), and redraws them to each client in the best form it has:
  Kitty, then Sixel, then half-block text (`image-grid.c:178-203`). It
  takes Kitty's direct transmission only (no files or shared memory, which
  is also puritty's rule in `feature-plan.md` §5), no Unicode placeholders,
  no relative placements. To send puritty Kitty images, tmux must see the
  reply `ESC _ G i=31;OK ESC \` to its probe, or be told
  `terminal-features …:kittygraphics`. Built only with `--enable-images`.
  This changes `feature-plan.md` §5's order: with 3.9, the Kitty protocol
  is what survives tmux too, not only Sixel.
- **Control mode**: no new notifications or flags. `%layout-change` now
  also fires when border status or scrollbars change pane sizes
  (ecc43170); a control client's colors start unknown rather than black,
  which made tmux think a control client's terminal dark (e6211b41).
- **Outer terminal**: `kitty(` joins the XTVERSION list; Kitty's keyboard
  protocol is on an unmerged branch (`kitty-keys-autodetect`), so tmux
  still asks for modifyOtherKeys.
- **Branches to watch**, unmerged: `hidden-panes` (hide and show panes),
  `zoomed-floating-panes` (zoom recorded in layouts, which a v2 parser
  will meet), `new-pane-hooks`.

## TM8 · What the integration could be

Beyond phase 4's tabs and splits, each built on TM5:

- **Floating and modal panes as puritty's own overlays**, with a shadow
  and a title; dragging one sends `move-pane`/`resize-pane`. No other
  terminal draws tmux's floating panes natively.
- **Sessions in the host launcher.** Before attaching, puritty runs
  `tmux list-sessions -F …` on the host (over the built-in ssh, or `ssh`
  on Linux) and offers "attach main (3 windows)" or "new session" in the
  quick-connect list. A host entry's `command = "tmux new -A -s main"`
  (`settings.md` ST23) becomes a control-mode attach.
- **Reconnect is reattach.** When the ssh connection drops, the window
  keeps its tabs grayed, reconnects, and `attach -t` brings the panes back
  through TM5.8's capture. On Windows that is the PuTTY replacement's
  reconnect (`feature-plan.md` §2 item 6).
- **Per-pane prompt marks and progress** from OSC 133 and OSC 9;4 in
  `%output`: jump between commands in any pane, a tab's progress bar from
  its active pane.
- **The mouse indicator** of `feature-plan.md` §7, per pane, from
  `#{pane_private_modes}` and tmux's `mouse` and `set-clipboard` options
  read with `show-options`.
- **Clipboard**: `%paste-buffer-changed` tells puritty a tmux copy
  happened anywhere in the session, so it can offer it to the system
  clipboard without OSC 52 passing through.
- **The tmux settings window** of `feature-plan.md` §7, from
  `show-options -F` (3.8 made it take formats).
- **Theme follows the look**, both outside control mode (TM4.3) and in it.
- **EUC-KR.** tmux's grid is UTF-8, so an EUC-KR program inside tmux loses
  its text in tmux's own history and in an ordinary attach (measured, TM3,
  for capture). In control mode the live bytes pass raw, so puritty's
  charset filter would show them, but anything rebuilt from a capture
  (attach, `%continue`) would show U+FFFD. tmux cannot carry EUC-KR well
  either way; `cjk-and-thai.md` §10's colleagues need tmux's
  `LANG` to be UTF-8 with a converter in the pane, or no tmux.

## TM9 · Steps, in order

1. **TM4.3's five fixes** (small; any time; measured gain on every attach).
2. **Move devbox's tmux to 3.8** and record a corpus of control-mode
   sessions with `bench/tmux/record.py`: splits, floating, modal, zoom,
   pause, attach to a busy pane, EUC-KR, over a slow link.
3. **The protocol layer in pure Geng** (`geng-plan.md`'s `tmux-control`):
   line splitter, unescape into per-pane streams, reply matching, both
   layout parsers, notifications as a type, fuzzed with the recordings.
4. **PTY-less pane surfaces** and the tab and split tree, then floating
   and modal overlays.
5. **Attach and recovery**: capture, private modes, the race, `pause-after`.
6. **Over the built-in ssh**, then reconnect as reattach.
7. TM8's extras, each on its own.

## TM10 · Questions for Gilbert, with leanings

1. **TM4.3's fixes now, before phase 4?** Leaning yes: an afternoon's
   work, and the Esc wait is felt in vim inside tmux right after attach.
2. **The floor.** Keep 3.2, with `new-layouts` always sent (TM5.5)?
   Leaning yes: nothing else needs a version check.
3. **A "puritty" row upstream in tmux.** tmux takes GitHub issues and
   pull requests. Leaning: later, once puritty is released, as a request
   with the feature list puritty has then; until then the user-guide line
   in TM4.3.
4. **Images**: does 3.9's Kitty-to-Sixel translation move Kitty graphics
   ahead of Sixel in `feature-plan.md` §5? Leaning: keep Sixel first (tmux
   3.4 to 3.8 carry only it, and Gilbert's hosts run 3.6) and revisit when
   3.9 is released.
5. **EUC-KR and tmux**: do the colleagues on EUC-KR hosts run tmux there?
   If they do, TM8's last item needs a decision; if not, nothing to do.

**Gilbert's answers, 2026-11-11:** the leanings of questions 1 to 4 are
accepted. The colleagues do use tmux with EUC-KR (TM11).

## TM11 · EUC-KR through tmux, measured (2026-11-11)

`ko_KR.euckr` and `ko_KR.utf8` were built with `localedef` into a scratch
`LOCPATH` (for 2.7, with its own glibc 2.27's `localedef`). A program in a
pane printed `한글` as EUC-KR (`c7 d1 b1 db`) and as UTF-8, and an ordinary
client attached on a pty, with the server and the client each in either
locale. tmux 2.7 is nixpkgs 18.09's (RHEL8 packages 2.7), 3.6a nixos-25.11's
(Gilbert's hosts run 3.6), 3.4 Mint's, 3.8 nixpkgs-unstable's.

| tmux | EUC-KR from the pane reaches a UTF-8 client as | and `capture-pane` as | a client in `ko_KR.euckr` |
|---|---|---|---|
| 2.7 | nothing: the bytes are dropped | dropped | **refuses to start**: "need UTF-8 locale (LC_CTYPE) but have EUC-KR", `-u` or not |
| 3.4 | dropped | dropped | starts; every non-ASCII character, UTF-8 too, is `_` |
| 3.6a | `�` per invalid byte (three for the four bytes) | the same `�` | `_` |
| 3.8 | `�`, as 3.6a | `�` | `_` |

The server's own locale changed nothing. So **no tmux carries EUC-KR bytes
a program writes**: tmux decodes the pane as UTF-8 and keeps UTF-8 cells,
and it sends a client UTF-8 or nothing. Whatever the colleagues do, the
EUC-KR is turned into UTF-8 *before* tmux sees it, inside the pane (a
converter such as `luit` or `cocot` around the program or the ssh, or an
editor that converts files on reading, as vim's `fileencodings` does), and
the tmux client runs in a UTF-8 locale. Then the bytes puritty gets from
tmux are UTF-8, and puritty's EUC-KR setting (`cjk-and-thai.md` §10) must
be off for that session, in ordinary and in control mode alike. This is
inferred from the table; how the colleagues work is Gilbert's to confirm.

`cjk-and-thai.md` §10.4's open questions are answered here.

**Confirmed, 2026-11-11:** Gilbert asked the colleagues. They work in
EUC-KR by default and switch to UTF-8 to use tmux. So a session on such a
host is EUC-KR outside tmux and UTF-8 inside it, and puritty's character
set has to follow:

- **In control mode** puritty knows it is talking to tmux, so the session's
  panes are UTF-8 whatever the host's setting says. Nothing for the user to
  do (phase 4).
- **In an ordinary attach** puritty sees only bytes. Today the user changes
  the host's character set in the settings and back. Ideas, none built: a
  quick switch in the window's menu; or a host entry's `command` that runs
  tmux (`settings.md` ST23) marking that session UTF-8.

## TM12 · TM4.3 built (2026-11-11)

Gilbert accepted TM10's leanings, so the five fixes are in:

- **`Vt.Embedder`** (`vt/src/Vt/Term.geng`): what the embedder says of
  itself, its foreground and background, DA1's answer and XTVERSION's
  name. Without one (`ghosttyEmbedder`) every answer is libghostty-vt's as
  before, so the replay corpus and the oracle are untouched (`vt-core.md`
  V4). `Vt.withEmbedder` sets it.
- **OSC 10, 11 and 12 `?`** answer the program's color, else the
  embedder's (`Palette.dynamicColor`). The renderer keeps to the colors a
  program set (`Palette.programColor`), so a block cursor still takes the
  color of the text under it.
- **DSR 996** answers `CSI ? 997 ; 1 n` or `; 2 n` from the background OSC
  11 answers, light when its relative luminance is over half, and nothing
  when there is none. `withEmbedder` sends the same, unasked, under mode
  2031 when the side changes: puritty's settings reloaded with another
  background is sent at once (`applySettings`).
- **puritty's window** (`app/src/Main.geng`, `embedderOf`) gives the
  look's colors, DA1 `?62;21;22;52c` (21 margins, 52 OSC 52) and
  XTVERSION `puritty 0.1.0`.
- **The user guide** has `docs/user/tmux.md`, with TM4.3's line for
  `.tmux.conf` and the EUC-KR finding of TM11.

**Measured** with `bench/tmux/inside.py`: tmux 3.8 attached inside puritty
on Xvfb, a lone Esc typed with xdotool, timed until the pane shows it;
three runs each.

| puritty | Esc 1 s after attach | Esc 6 s after | `client_theme` | features tmux turned on |
|---|---|---|---|---|
| 9dc01c1, before | 503 ms | 17 ms | (empty) | bpaste, ccolor, clipboard, cstyle, focus, RGB, sync, title |
| with TM12 | 17 ms | — | dark | the same and **margins** |

The core's unit tests have a suite for it (`vt/tests/src/Embedder.geng`,
9 tests).

## TM13 · Phase 4 begun: the protocol package (2026-11-11)

*Gilbert, 2026-11-11:* he wants to see floating panes in puritty, natively,
so phase 4 starts. The steps, each tested and committed:

1. **devbox's tmux is 3.8** (`devbox.json`, a pinned nixpkgs-unstable
   commit). Done.
2. **`packages/tmux`**, pure Geng and runtime-free (`runtime = "any"`):
   - `Tmux.Control`: `feed` reads a terminal's bytes a read at a time.
     Outside control mode they come back as `Outside`; `ESC P 1000 p`
     gives `Entered`, then each line a `Notice` (every 3.8 notification of
     TM5.3, anything else `Unknown`) or, from `%begin` to the `%end` or
     `%error` of the same number, a `Reply` with its lines; `ESC \` at a
     line's start gives `Exited`. `%output` and `%extended-output` are
     `Output` with the pane's bytes unescaped (`\ooo`), raw high bytes
     kept. A partial line or a partial `ESC P 1000 p` waits for the next
     read. Scanning uses `Bytes.spanWithin`, 16 bytes at a time natively.
   - `Tmux.Layout`: both forms to one tree, the old by a small parser and
     3.8's JSON by `Json.Decode`; `panes`, `tiled`, and `floating` bottom
     first.
   - `Tmux.Command`: `send-keys -H` in commands of 256 bytes, the pane id
     quoted; `refresh-client -C` and `-f new-layouts`; `list-panes` with
     each line prefixed.
   - Tests (`packages/tmux/tests`, 22): two sessions recorded with tmux
     3.8 (`record.sh`, plain `sh` with a `$ ` prompt, `BARE` recordings
     with no markers), read whole and split at every byte; the layouts in
     both forms, nested and floating; the commands. Done.
3. **The app**: when `tmux -CC` starts on the pty, the window shows the
   tmux window's panes, tiled panes where tmux puts them with a divider
   between, floating panes over them with a border, the active pane's
   cursor; keys go to the active pane by `send-keys -H`; the window's size
   to tmux by `refresh-client -C`; `%exit` gives the terminal back.
4. Then: capture on attach and on `%continue`, `pause-after`, tmux windows
   as tabs, the mouse (focus, moving and resizing floating panes), and
   detach and reattach.

## TM14 · Step 3: tmux's panes in puritty's window (2026-11-11)

Built: `tmux -CC` run on puritty's terminal shows the tmux window's panes
in puritty's window, floating and modal panes included.

- **`app/src/TmuxMode.geng`** keeps the control mode's state: the reader
  (`Tmux.Control`), the window shown, a `Vt.Term` for each pane with its
  id beside it, the layout, the active pane, and the canvas. `Main.feed`
  gives every read to `TmuxMode.read` first: the terminal's own bytes go
  on to its core as before, each `%output` is fed to its pane's
  terminal (whose replies are dropped: tmux answered them, TM5.4), a
  `%layout-change` of the window shown sizes the panes' terminals to
  their boxes, `%window-pane-changed` moves the active pane. On entry
  puritty sends `refresh-client -f new-layouts`, `refresh-client -C` with
  the window's size, and asks for the window's id and layout.
- **Keys and pastes** (`Main.send`) go to the active pane as `send-keys
  -H` while control mode is on; a resize of the window becomes
  `refresh-client -C`.
- **The picture** is a canvas `Vt.Term` the size of the window, made
  again each frame by `TmuxMode.paint`: cleared, the tiled panes laid on
  with `Vt.compose`, the lines between them painted (`Vt.paint`), then
  each floating pane in a box, bottom first, so a box lies over what is
  under it; then the cursor at the active pane's. `draw` frames the
  canvas as it frames the terminal, so the renderer, its shadow and its
  scroll copies are unchanged. The title is `tmux: ` and the window's
  name.
- **`Vt.compose`** (new in the core): panes' screens laid on a terminal's
  screen at their places, by index into a `Builder` of terminals, which
  are only read; each cell's style and grapheme cluster interned into the
  canvas's own tables, so a style id means one style in the frame.
  `Vt.cursorOf` reads a pane's cursor. The canvas is kept between frames,
  so a style keeps its id and the renderer's diff draws only what
  changed.
- **The pane terminals live in an `Array.Builder`**, updated in place
  with `Builder.update`: Geng's ownership checker refuses a terminal
  rewritten inside `Array.map`, as an array only lends its elements.

**Shown** with `bench/tmux/show.py`, puritty on Xvfb running `tmux -CC
new-session` while a second client splits the window and opens a floating
and a modal pane: text typed with xdotool reached the active pane each
time, the right pane's green text and Hangul came through, the vertical
divider stops at the floating box, and the modal box lies over the
floating one.

**Not yet** (TM13 step 4): what the panes held before attaching (a
capture), `pause-after`, the session's other windows as tabs, the mouse
(focus by click, moving and resizing floating panes), scrollback and
selection within a pane, colors for the dividers and the active pane's
box, and puritty's own screen while tmux exits.

**Decided, Gilbert, 2026-11-11: floating panes stay inside the window.**
tmux keeps a floating pane within its window's area (it clamps each back
inside on a resize, `layout_clamp_floating_panes`), and puritty draws them
there, in boxes over the tiled panes. A floating pane is not pulled out into
a window of its own: tmux's coordinates would no longer say where it is, and
puritty has one window a process (`ssh-client.md` SC22). Step 4's mouse
moves and resizes them within the window, by `move-pane` and `resize-pane`.

## TM15 · Step 4.1: what the panes hold on attach (2026-11-11)

*Gilbert, 2026-11-11:* do all of step 4, in this order: what the panes hold
on attach, the mouse on panes, scrollback and selection within a pane,
tmux's windows as tabs, and slow links and safety.

Attaching to a session that was already running showed empty panes until
their programs wrote again. Now, on entry, puritty asks for the session's
panes (`list-panes -s`) and, for each, sends one line of three commands:
`display-message` with the pane's size, cursor, alternate screen, scroll
region and private modes (3.8's `#{pane_private_modes}`), `capture-pane
-a -q` for the main screen kept behind an alternate one, and `capture-pane
-p -e -J -S - -E -` for its history and screen with their colors. The
pane's terminal is made again from them: the main screen's lines, then the
alternate screen's after `?1049h`, then the modes, the region and the
cursor.

- **One line, one moment.** tmux runs a line's commands in turn before it
  reads a pane again, so the state and the captures are of one moment.
  Measured: with the cursor read by an earlier `list-panes`, a `less`
  resized by the attach had redrawn in between, its relative scrolling
  then lost a line, and puritty's copy of the pane drifted from tmux's.
  The reproduction (tmux 3.8 driven from Python, what puritty builds fed
  to `core-dump`) now ends as tmux's own capture of the pane does.
- **The attach race needs nothing more** (TM5.8): output a pane wrote
  before the capture's reply is in the capture, and the rebuilt terminal
  replaces whatever the pane's terminal held.
- **Replies are matched to commands** by a queue of what each command sent
  waits for (`Expect`), popped by each reply with flags 1; a reply with
  flags 0 is a command not puritty's (its first, a hook's). Keys and
  resizes put their own entries on it.
- **A reply's line may start with an escape**, as a capture with `-e`
  does: `Tmux.Control` took any `ESC` at a line's start for the end of
  control mode and skipped it, and drew `[1m` as text. Only `ESC \` ends
  it now (a test of its own).

Shown with `bench/tmux/show.py --scenario attach`: a session made before
attaching, with history and colors in one pane, `less` on the alternate
screen in another and a floating pane, came back as it was, and `less`
scrolled correctly after.

## TM16 · Step 4.2: the mouse on panes, and keys by the active pane (2026-11-11)

- **A click** makes the pane under the pointer active (`select-pane`),
  the topmost first: floating panes top down, then the tiled ones.
- **A floating pane's box**: a press on its top edge and a drag moves it,
  with `move-pane -t %N -X x -Y y`, the box's top left, border included,
  as tmux takes it (`cmd-join-pane.c`, `cmd_join_pane_move`); a press on
  its other edges resizes it, with `resize-pane -x -y`, whose sizes for a
  floating pane count the border's two lines (measured: `new-pane -x 30
  -y 6` makes a 28 by 4 pane, and a resize without the 2 grew a drag of
  6 by 2 by 4 by 0). Each is sent when the pointer reaches a new cell;
  tmux's `%layout-change` then moves the box.
- **A program that asked for the mouse** gets the event in its pane's own
  cells, encoded by its own modes (`Vt.Mouse.encode` over the pane's
  terminal), sent as `send-keys -H`; the pane a press began in keeps the
  mouse until every button is let go. Shift takes the mouse back for
  puritty, as without tmux.
- **Keys** are encoded by the active pane's modes (DECCKM, the keypad, the
  kitty flags, modifyOtherKeys), and bracketed paste and focus reports
  follow the active pane's 2004 and 1004: they had followed puritty's own
  terminal, which tmux's panes never set.
- **Every command puritty sends is queued** for its reply, `select-pane`
  and the drags included, so that the captures' replies keep their places.

**Checked against tmux** (`bench/tmux/show.py --scenario mouse`, reading
tmux's own state after each action): a click in the right pane made `%1`
active; a drag of the floating pane's top edge by 10 by 5 moved it from
4,2 to 14,7; a drag of its corner by 6 by 2 made it 34 by 6 from 28 by 4;
a click in the left pane, whose `cat -v` had set 1000, 1006 and DECCKM,
gave it `ESC [<0;6;26M` and `ESC [<0;6;26m` for the cell clicked, and Up
then gave `ESC O A`.

Not done here: dragging the line between tiled panes to resize them.

## TM17 · Step 4.3: scrollback and selection within a pane (2026-11-11)

- **Each pane has its own view.** The wheel over a pane whose program does
  not take the mouse scrolls that pane's view three rows, or on its
  alternate screen sends three arrow keys (by the pane's DECCKM), as
  puritty does without tmux; Shift+PgUp, PgDn, Home and End scroll the
  active pane's view; a key its program gets brings the view to the
  bottom; output keeps a view scrolled back on its rows. `Vt.compose` takes
  how far back each place is drawn, read by `rowsBetween` from the pane's
  scrollback as `viewAt` reads it; the cursor is drawn where its row has
  moved to, or not at all once it is scrolled out of the pane.
- **A selection lives in one pane**, in that pane's terminal: a drag, a
  double click for a word, a triple for a line (`Vt.wordAt`, `Vt.lineAt`,
  the word boundaries of the settings), its rows absolute as the core's
  `Point`s are, so it covers the pane's scrollback and joins its wrapped
  lines (`Vt.selectionText`). A drag that leaves the pane stays at its
  edge. Shift selects over a program that takes the mouse. Let go, its
  text is PRIMARY, and with `copy_to_clipboard` the clipboard (WS27);
  Ctrl+Shift+C copies it; the paste button pastes.
- **The highlight** is drawn in the canvas, not by the renderer: the new
  `Vt.invert` turns the inverse flag of a span's cells, right after the
  selection's pane is laid on, so a floating pane laid on later covers it
  as it covers the pane.
- **Ownership:** what `paint` reads of the state (each pane's place and
  view, the selection's spans) is read before the canvas is written, by
  helpers that only look; closures that held the whole state while its
  canvas was being written were refused.

**Checked** (`bench/tmux/show.py --scenario select`): three wheel steps over
the left pane, which had `seq` 200 lines, showed lines 163 to 192; a drag
over the right pane's first eleven cells made PRIMARY `hello world`; a
double click on the scrolled left pane made it `left`, highlighted, and
Ctrl+Shift+C put `left` on the clipboard; Return brought the view back to
line 200 and the prompt. The core's tests have a scrolled compose and
`invert` (94).

## TM18 · Step 4.4: tmux's windows as tabs (2026-11-11)

While control mode is on, puritty's first row is a tab bar: ` 0:editor │
1:logs │ + │`, the window shown inverse. tmux is told the window is a row
shorter (`refresh-client -C` with `rows - 1`), and the panes are drawn a
row down: the layout's panes are moved down where they are read for
drawing and for the pointer, and only what tells tmux a place (`move-pane
-Y`) takes the row off again.

- **The windows** come from `list-windows`, asked on attach and again on
  `%window-add`, `%window-close` and `%session-changed`; `%window-renamed`
  renames a tab in place. Windows of other sessions (`%unlinked-…`) are
  not shown.
- **A click** on a tab is `select-window`; on `+`, `new-window`. Ctrl+Shift+T
  is `new-window`, Ctrl+PgUp and Ctrl+PgDn `previous-window` and
  `next-window`; those keys no longer reach the pane.
- **No close button.** Closing a tmux window kills the programs in it, so
  the bar offers no click that does: a window closes when its programs end,
  or with tmux's `kill-window`.

**Checked against tmux** (`bench/tmux/show.py --scenario tabs`): attached
to a session of two windows, 0:editor active; a click on the second tab
made 1:logs active and showed its pane; `+` made a third and showed it;
Ctrl+PgUp went back to 1; Ctrl+Shift+T made a fourth; a rename from
another client showed on its tab. The mouse and select scenarios, moved
down a row, pass as before.

## TM19 · Step 4.5: slow links and safety (2026-11-11)

- **`pause-after=5`** is set with `new-layouts` on attach: a pane whose
  output puritty has not read for five seconds is paused by tmux and its
  backlog dropped, where without it tmux ends a client five minutes behind
  as "too far behind" (TM5.7). On `%pause`, puritty sends one line,
  `refresh-client -A '%N:continue'`, the pane's state and both its
  captures (TM15's line), so the pane is made again from one moment and
  goes on from there: what the paused pane printed shows, and nothing is
  drawn twice.
- **`tmux -CC` inside a pane** (tmux does not refuse it for a control
  client, TM5.1): when a pane's output starts control mode, puritty sends
  the pane an empty line, which detaches that inner client, reads the rest
  of its output with a `Tmux.Control` reader of its own, so that the inner
  client's lines are dropped until its `ESC \`, and writes a line in the
  pane saying why.
- **When control mode ends with a reason**, `%exit REASON` (as "too far
  behind"), puritty writes it on the terminal it goes back to. Measured: a
  detach gives a bare `%exit`, then ST, so nothing is said for one.

**Checked** (`bench/tmux/show.py --scenario safety`): a pane paused by
another client's `refresh-client -t CLIENT -A '%0:pause'`, then given a
command, showed `written while paused`, as tmux's own capture of it ends;
`tmux -CC new-session` on another socket, run in the pane, left the inner
server with no client, and the pane only the note and its prompt; a
detach gave the shell its terminal back.

With this, TM13's step 4 is done. Left for later: dragging the line
between tiled panes, colors for the tab bar and the dividers, and `%exit`
reasons for a detach, which tmux does not send.

## TM20 · The lines between tiled panes dragged (2026-11-11)

A press on the line right of a tiled pane, outside every pane and box, and
a drag resize that pane's width, `resize-pane -t %N -x`; on the line below
it, its height, `-y`; tmux takes the room from the neighbor. A tiled
pane's size, unlike a floating one's, counts no border. `Drag` has a kind
now: the box moved, the box resized, the line right, the line below. (Since TM38 each edge of
a box resizes only its own way, and the pointer shows it.)

**Checked against tmux** (`bench/tmux/show.py --scenario lines`): with the
window split left and right and the right split again, the line right of
the left pane dragged 10 left made it 40 wide from 50 and the right column
59 from 49; the line below the top right pane dragged 3 down made it 17
high from 14 and the one below 11.

## TM21 · Colors for the tab bar, the lines and the boxes (2026-11-11)

What puritty draws around tmux's panes is written into the canvas in
color from the 256 (`drawText`, with autowrap off so nothing moves): the
tab bar a dark band (250 on 236), its active tab puritty's amber with dark
bold text (234 on 214); the lines between tiled panes a quiet gray (240);
a floating pane's box gray (245), and the active pane's box amber (214), so
the pane the keys go to is seen at once. They are fixed colors for now;
a light look, or a palette of the user's, may want them from the look.

## TM22 · The tab bar at the bottom, by default (2026-11-11)

*Gilbert, 2026-11-11, using tmux 3.8 with `-CC`:* the bar used to be at the
bottom, where tmux's status line is. `[tmux] tabs = "bottom"` (the default)
or `"top"` places it; the settings window has it on the Window page. At the
bottom, tmux's rows are the window's from the top, and the bar is the last
row; at the top, the panes are drawn a row down as in TM18. Only where the
panes are drawn, where the bar is drawn and clicked, and `move-pane -Y`
follow it; tmux is told a row less either way. The show.py scenarios now
click their tabs on the bottom row, and pass.

## TM23 · Typed keys go through tmux's key table (2026-11-11)

*Gilbert, 2026-11-11, using tmux -CC:* with plain `tmux` his prefix,
`C-a` from his tmux.conf, works; under `-CC` it did nothing, and there was
no way to control tmux from the keyboard.

**Why.** TM5.9 had keys sent as `send-keys -t pane -H`, which is what
iTerm2 does: the bytes go into the pane and no key table is looked at, so
neither the prefix nor a root binding (`bind -n`) ever fires. iTerm2's
users drive tmux from iTerm2's menus; a tmux user expects their bindings.
Every gate typed text and Enter, and made panes from a second tmux
client, so none pressed a binding.

**Now.** tmux 3.8's `send-keys -K` sends keys to the client, which looks
them up as keys typed at a terminal are (tmux(1), `send-keys`). Measured
by hand on a control client: `send-keys -K C-a '"'` split the pane;
`send-keys -K -H 01 22` did not, because `-H 01` is the character 0x01, not
the key C-a, so a key with Ctrl or Alt has to go by its name. Ten keys
sent as ten lines in one write, as one line of `;`, and as one command all
arrived in order.

A typed key (`TmuxMode.typed`) is sent as:

- a named key (arrows, Home, End, PPage, NPage, IC, DC, F1–F12, Tab,
  BTab, Enter, KPEnter, Escape, BSpace) by its name, with `C-`, `M-` and
  `S-` for its modifiers (`send-keys -K 'C-Up'`);
- a character with Ctrl by `C-` and its unshifted character, `S-` for
  Shift on a letter (`C-a`, `C-S-a`), Ctrl+Space as `C-Space`;
- a character with Alt by `M-` and the character typed (`M-x`, `M-!`);
- other text as its UTF-8 bytes through the client (`send-keys -K -H`),
  which reaches the pane whole (Korean measured) and is a binding's key
  after the prefix (`|` measured);
- a chord with Super, which tmux has no name for, as before, the pane's
  bytes with `-t pane -H`.

A key no binding takes goes to the active pane, encoded by tmux for that
pane's modes as for any client. Pastes and the mouse still go to the pane
with `-t pane -H`: a paste is not keys to look up, and puritty draws and
routes the mouse itself (TM16).

**Checked** in `bench/tmux/show.py --scenario prefix`, with his
tmux.conf (prefix C-a, `|` and `-` split, `"` unbound, vi copy mode, `bind
-n C-k` clearing the screen and history), each step read back from tmux:
typed `echo 한글 typed` arrives; `C-a |` makes 2 panes and `C-a -` 3; `C-a
"` leaves 3; `C-k` takes the history from 47 lines to 0; `C-a [` enters
copy mode and `q` leaves it. The build, tabs, select and mouse scenarios
give what they gave; packages/tmux 26 tests, app 102.

## TM24 · What tmux does for a keyboard user under -CC: survey and guard (2026-11-11)

*Gilbert, 2026-11-11, after TM23:* "Why did we miss this in our tmux
support? It makes me wonder if we are missing other tmux things." Then:
-CC must support tmux's right-click menu too; puritty is free to draw these
things its own way, as it draws the tabs, "but we should always have an
option for the user to choose our look vs a more traditional tmux look".
He drives tmux entirely from the keyboard.

### TM24.1 · How it was measured

`bench/tmux/bindings.py` starts tmux 3.8 with its default bindings (two
panes, two windows, a paste buffer), attaches a control client, and for
each of the 93 bindings of the `prefix` table sends `send-keys -K C-b
<key>`, as puritty sends keys since TM23. It records what the control
client is sent, and what changed (panes, windows, sessions, clients,
buffers) as a second client reads it. A prompt's binding is followed by
`probe` and Enter, a confirmation's by `y`. The root table is the mouse's
(30 bindings) and Gilbert's own `bind -n C-k`, done in TM23.

### TM24.2 · Found: four ways a binding can wedge or lose the client

- **`confirm-before` and `command-prompt` leave the control client
  answering nothing, for good.** Both return "wait", which holds the
  client's command queue until the prompt closes; a control client's keys
  arrive as commands on that same queue, so the `y` never reaches the
  prompt. Measured: after `send-keys -K C-b x`, `display -p still-here`
  had no reply, nor did anything after it. TM23 made this reachable: from
  2ddf18a to this section, `C-a x` (or `,`, `$`, `.`, `'`, `/`, `:`, `f`,
  `T`, `&`) under puritty froze the session's window.
- **`suspend-client` (`C-z`) makes tmux drop every key from that client**
  (`server-client.c` ignores a suspended client's keys), and nothing
  resumes a control client: measured, keys after it reached no pane, nor
  after `refresh-client`. `lock-client` is harmless (keys still arrive).
- **`display-message` writes `%message` inside the binding's own
  `%begin`/`%end` block** (flags 0), not as a notification, so puritty,
  which drops blocks that are not its own, never saw it. A binding's error
  (`can't find window: 5`) comes back the same way, as the block's
  `%error`.
- **Output that a terminal client shows in a view comes back as text** in
  the binding's block: `list-buffers` (`#`), `list-keys -N` (`?`),
  `show-messages` (`~`).

### TM24.3 · Every default binding, under -CC

| what happens | keys (prefix table) |
|---|---|
| works through the panes and layouts | Space ! " % * ; @ E ] c l n o p z { } arrows, M-1…M-7, M-o, M-arrows, C-o, C-arrows, C-b (send-prefix), `(` `)` (other session), d (detach: `%exit`), g (switch-client -T move) |
| tmux enters a mode puritty does not show (TM25.4) | [ PPage (copy mode), = (choose-buffer), C (customize), D (choose-client), s w (choose-tree), t (clock), Tab BTab (switch-mode in a floating pane) |
| said in the tab bar now (TM24.4) | i (display-message), errors: 0–9 for a missing window, L with no last session, M-n/M-p with no alert |
| output dropped; a terminal client shows a view | # (list-buffers), ? (list-keys -N), ~ (show-messages) |
| held back now (TM24.4); would wedge the client | $ ' , . / : f T (command-prompt), & x (confirm-before), C-z (suspend-client) |
| nothing for a control client | < > (display-menu: nothing sent, nothing changed; `display-popup` returns at once for a control client, `cmd-display-menu.c:594`), q (display-panes: a mode on the active pane that ends by itself, no numbers puritty could show), m (marks the pane: tmux has it, puritty draws no mark), M (clears it), S-arrows and DC (refresh-client -U/-D/-L/-R/-c: pan a client smaller than its window; a control client has the window's size) |
| nothing to see | r (refresh-client) |

Not measured by this probe, and on the list for TM25: tmux's status line
(`status-left`, `status-right`; a control client has none,
`status.c:104`), pane titles and `pane-border-status`, the bell and
activity flags a window's tab could show, copy mode's copy reaching the
system clipboard (`set-clipboard on`, `%paste-buffer-changed`), and the
root table's mouse bindings, which puritty does not send since it handles
the mouse itself (TM16).

### TM24.4 · The guard, now

- **Following tmux's key tables** (`packages/tmux` `Tmux.Bindings`): on
  attach puritty reads `list-keys` and `#{prefix} #{prefix2}
  #{repeat-time} #{version}`, and follows the table each key leaves the
  client in, as tmux does: the prefix to `prefix`, a binding back to
  `root`, a `bind -r` key keeping its table for `repeat-time`, and
  `switch-client -T` to the table it names.
- **Held back:** a key whose binding has `command-prompt`,
  `confirm-before` or `suspend-client` is not sent; puritty sends
  `switch-client -T root` when the prefix had moved tmux out of `root`,
  and says `puritty: x is confirm-before; tmux -CC shows no prompt yet`
  at the tab bar's right.
- **Said:** a `%message` or an `%error` in a block that is not puritty's
  is shown at the tab bar's right until the next key.
- **tmux before 3.4** has no `send-keys -K` (tmux CHANGES, 3.4; 3.8 fixed
  where those keys land in the input queue). puritty asks the version and
  sends keys to the pane as before TM23 on an older tmux; the prefix there
  says `tmux's key bindings under -CC need tmux 3.4 (send-keys -K)`.
  Measured on 3.3a (nixpkgs 23.05): typing had also been lost on it, since
  its layouts do not mark the active pane and puritty never learned it; the
  window query now asks `#{pane_id}` with the window.

**Checked:** packages/tmux 37 tests (Bindings 11: the escaped key, `-r`,
prefix and back, the confirmation and both prompts held, repeat and its
expiry, a repeating key not reaching a non-repeating binding,
`switch-client -T`, a plain root binding sent, suspend held, the version
rule). `bench/tmux/show.py --scenario prefix`, with Gilbert's tmux.conf,
on 3.8: `C-a x`, then `C-a ,`, then `C-a |` makes the fourth pane (tmux
still answers), the bar says why (TM25 asks them instead; the step now answers Escape to each); `C-a i` shows tmux's message; `C-a C-z`
then typing reaches the pane; `C-a 5` shows `can't find window: 5`. On
3.3a: typing reaches the pane and the bar says why the prefix does
nothing. The build, tabs, select, mouse, safety, lines and attach
scenarios give what they gave.

### TM24.5 · Plan, keyboard first, each with tmux's look as an option

One setting chooses the look of everything below: `[tmux] look =
"puritty"` (boxes over the panes, as the settings window's dialogs) or
`"tmux"` (on the bar's row and over the panes as a terminal client draws
them). Leaning: one setting, not one per feature; `[tmux] tabs` stays for
where the bar is.

1. **Prompts and confirmations, drawn by puritty** (the held keys today).
   puritty runs the binding itself instead of sending the key:
   `confirm-before -p text cmd` asks the text (its formats expanded by
   `display -p`) and on `y` runs `cmd`; `command-prompt` takes `-I`, `-p`,
   `-k` and the template, puritty edits the line (history, Tab for nothing
   at first) and runs the template with `%%`/`%1` replaced. A binding with
   more than these (`if-shell … { command-prompt … }`) is run as tmux
   would, puritty taking the prompt's part. tmux look: the prompt on the
   bar's row in `message-style`.
2. **Views:** what `#`, `?`, `~` and any binding's command print, in a box
   puritty scrolls (q or Escape closes); tmux look: over the active pane.
3. **Menus:** `display-menu` read from the binding (`<`, `>`, and the
   right-click's `MouseDown3Pane`, sent to puritty's mouse code), drawn at
   the place tmux would put it, run as chosen.
4. **`display-panes`** numbers over the panes, a digit choosing one.
5. **Status line:** `status-left` and `status-right` asked with
   `refresh-client -B` subscriptions, shown in the bar; tmux look draws
   `status-style` and the window list as tmux would.
6. **Marks and flags:** the marked pane, pane titles (`pane-border-status`),
   bell and activity on the tabs.

The order is by what a keyboard user meets first; 1 removes every held key.

## TM25 · tmux's prompts asked by puritty, and copy mode's table (2026-11-11)

Item 1 of TM24.5: the keys TM24 held back now open puritty's own prompt,
which runs what tmux would have run. Gilbert, 2026-11-11: "Ok, proceed".

### TM25.1 · Copy mode's keys were a second way to wedge the client

tmux looks a key up in the active pane's mode table while the client is in
`root` (`server-client.c:1531`): `copy-mode-vi` or `copy-mode` by
`mode-keys` (`window_copy_key_table`), the only modes with a table. There,
`/ ? :` and `f F t T` are `command-prompt -P` (3.8's prompt in the pane)
and the digits `command-prompt -NP`, which wait as `command-prompt` does.
Measured: after `send-keys -K C-b [` and `send-keys -K /`, the control
client answered nothing again. Gilbert sets `mode-keys vi`, so TM24's guard
missed his copy mode's search.

puritty now follows each pane's mode: `list-panes -s -F 'M #{pane_id}
#{pane_mode} #{mode-keys}'` on attach and, for one pane, on each
`%pane-mode-changed`. `Bindings.route` takes the active pane's table and
does what tmux does with it: the mode table first while in `root`; the
prefix from any table but `prefix`; a key bound nowhere in its table
looked for in `root` (TM24 did that only while repeating). A binding sent
that enters copy mode (`copy-mode`, `copy-mode -u`) sets the pane's table at
once, before tmux's notice, so that `C-a [ /` typed within a round trip is
looked up in copy mode.

### TM25.2 · The prompt

- **Read from the binding** (`packages/tmux` `Tmux.Syntax`): tmux's words,
  quotes, `{ … }` blocks and `;`, as `list-keys` writes them.
  `confirm-before`: `-p`, `-c`, `-y`, and the command; with no `-p`, tmux's
  own `Confirm 'cmd'? (y/n)`. `command-prompt`: `-p` and `-I` split at
  commas (`-l` not), `-1`, `-N`, `-k`, flags run together (`-1P`, `-NP`),
  the template a block or a string, and with none, the colon prompt whose
  answer is the command. The commands after the prompt in the binding run
  when it closes, answered or not, as tmux continues the queue.
- **Formats:** a question or first text holding `#` is expanded by
  `display-message -p` (`kill-pane #P?` shows `kill-pane 1?`); a first text
  that comes back after a key has changed the line does not replace it.
- **Keys** (`TmuxMode.promptKey`): a confirmation runs on its key, or Enter
  with `-y`; any other key says no. A line edits as tmux's emacs
  `status-keys` do: Left, Right, Home, End, C-a, C-e, C-b, C-f, BSpace, C-h,
  DC, C-d, C-u, C-k, C-w; Up and Down go through earlier answers; Enter
  answers; Escape, C-c, C-g cancel. `-1` takes a key's text, `-k` a key's
  name, `-N` digits, and any other key answers the count and then goes on
  as typed, so copy mode's `3k` sets the count and moves. Text from an input
  method or a paste goes into the line, a line end as a space.
- **Run:** each answer fills the template: `%%` (or `%%%`) the first
  answer once, `%1`…`%9` each theirs, in the word they are written in and
  inside blocks; a filled word is written again in single quotes, so what
  is typed is one argument and never tmux syntax (a name `a"; kill-server;
  'x` stays a name). The line is sent as puritty's own command; an error,
  or the first line of what it prints, shows at the bar.
- **Drawn** by `[tmux] look`: `"puritty"` (the default) in the window's
  question box (`Dialog`, SC23, which now has a caret inside the line), the
  pane's cursor hidden; `"tmux"` on the bar's row in tmux's default
  `message-style`, black on yellow, the caret after the text before it,
  wide characters placed by the core. In tmux's look, a message also takes
  the whole row, as on tmux's status line.

**Checked:** packages/tmux 51 tests (Syntax 12: both commands' flags,
defaults, run-together flags, several prompts and the commands after, a
binding that is no prompt, an answer that tries tmux syntax, `%1 %2`, a
word around `%%`, a string template, `;` inside a block; Bindings 13, two
new: copy mode's table, and root after the prefix). `bench/tmux/show.py
--scenario prompts`, Gilbert's tmux.conf, in each look, read back from
tmux: `C-a x` then `n` leaves 2 panes, then `y` 1; `C-a ,` with `editor 1`
renames the window, then `한글 창`; `C-a ,` Escape leaves it, tmux still
answering; `C-a :` `split-window -h` makes 2 panes; in copy mode `3 k`
moves the cursor from row 28 to 25; `/` `echo` finds `echo`; `q` leaves the
mode. App tests 104; every harness and tmux scenario as before.

### TM25.3 · Not yet

- `status-keys vi`: the line edits with emacs keys only.
- ~~`-i` (incremental search, copy mode's emacs table) answers once, on
  Enter, rather than on each key.~~ Done (TM40).
- Tab completion on the colon prompt.
- A binding whose prompt is inside another command (`if-shell … {
  command-prompt … }`) is still held back with a message (none of tmux's
  defaults is).
- tree mode's own questions (`x` in choose-tree) are tmux's `status_prompt`
  without a waiting command: they do not wedge the client but are not
  shown.

### TM25.4 · Found: tmux's modes are not drawn under -CC

The prompts scenario's pictures show copy mode as a plain pane: tmux sends
a control client a pane's output (`%output`), never a mode's screen. Copy
mode, view mode (`prefix ?`), choose-tree, the clock and the other modes
change what tmux does with keys, and TM24's table had them as working
because the probe read tmux's state, not the picture. TM24.3 is corrected.
What there is to draw them with, measured on 3.8: `capture-pane -M` gives
copy mode's backing screen, the pane's own lines, not the view with its
cursor, selection or position; the formats give the rest (`copy_cursor_x`,
`copy_cursor_y`, `scroll_position`, `selection_present` and the selection's
ends). For a keyboard user in vi copy mode this comes before TM24.5's menus.

## TM26 · What tmux prints, in a view (2026-11-11)

Item 2 of TM24.5. A terminal client shows what a command prints for it
(`list-keys -N` from `prefix ?`, `list-buffers` from `#`, `show-messages`
from `~`, anything run from the colon prompt) in view mode over the active
pane. A control client gets it as the lines of the command's block
instead: a key binding's block is flags 0 (TM24.2), a command puritty ran
from a prompt is its own (TM25, `ForRan`).

**Shown:** lines in either block open a view (`TmuxMode.View`), unless the
block holds `display-message`'s `%message`, which goes to the bar as
before; a command's error goes to the bar too. Tabs become spaces to the
next column of eight and other control characters spaces, so nothing
printed reaches the canvas as a sequence. While it is open the view takes
every key and drops what an input method commits or a paste brings; the
pane's cursor is hidden.

**Keys:** q, Escape and C-c close it; Up, Down, k, j, C-p, C-n, C-y, C-e
and Enter move a line; PPage, NPage, C-b, C-f, b, f and Space a page (the
view's rows less two, as tmux pages: measured 21 in a pane of 23 rows);
C-u and C-d half a page; g, Home and M-< the top; G, End and M-> the bottom.

**Drawn** by `[tmux] look` (TM25.2): `"puritty"` in a box over the panes as
wide as the longest line (40 columns at least, the window at most) and as
tall as its lines, amber edges on the tab bar's dark band, with "q: close"
and where it is (`28-54 of 89`) on the bottom edge. `"tmux"` over the
active pane, as tmux draws view mode, measured on 3.8 by a tmux client
inside another tmux: the lines from the pane's top, and `[N/M]` in
`mode-style` at its top right, M the lines that do not fit and N those
below the view, so it opens at `[M/M]` (`prefix ?` in 23 rows: `[70/70]`)
and G gives `[0/M]`. tmux 3.8 writes the top line's time before it
(`copy-mode-position-format`); puritty has no time for a line and leaves
it out.

**Checked:** `bench/tmux/show.py --scenario views`, Gilbert's tmux.conf,
in each look: `C-a ?` opens the view; `zzz`, `j j Next`, `G` move it and
`zzz` never reaches the pane; `q` closes it and typing reaches the pane
again; `C-a #` with a buffer set shows it; `C-a :` `list-windows` shows the
window; tmux answers after. Every picture looked at.

**Not yet:** the wheel does not scroll the view; a line wider than the view
is cut, where tmux's copy mode scrolls sideways; copy mode's search is not
offered inside the view.

## TM27 · tmux's menus, shown by puritty (2026-11-11)

Item 3 of TM24.5. `display-menu` does nothing for a control client
(`cmd-display-menu.c` returns at once), so `prefix <` (the window's menu),
`prefix >` (the pane's), the right button's menu and the `move` table's
(`prefix g` then `,` or `.`, an `if-shell -F` around one) showed nothing.

**Read** (`Tmux.Syntax.menuOf`, `ifFormatOf`): `display-menu`'s flags
(`-T -t -x -y` and the others that take a value) and its items, a name, a
key and a command each, or `''` alone for a line; `if-shell -F [-t] format
{ yes } [{ no }]`. `Tmux.Bindings.held` now holds a binding with
`display-menu`, as it holds a prompt.

**Run** (`TmuxMode.runLine`): a command line puritty runs for tmux as tmux
would. A prompt opens puritty's (TM25); a menu opens puritty's; an
`if-shell -F` asks tmux its format (`display-message -p -t pane`) and runs
the branch it gives (true unless empty or `0`); anything else is sent, each
command on its own line (tmux answers each command of a line with a block
of its own and stops at the first that fails, so one per line keeps the
answers counted; TM25's `closePrompt` now does the same). `-t =`, the
mouse's pane, which a control client has no event for, is made the pane's
id (`Syntax.retarget`); `send-keys -M` is left out, since puritty hands a
pane the mouse itself; `suspend-client` is still said, not run.

**Formats:** tmux expands a menu's title, names and commands when it shows
it (`menu_add_item`); puritty asks `display-message -p -t pane` for each
that holds a `#` and shows the menu when all have come back. `display-
message` also hands `%` to strftime, which made the Rename item's `%%` one
`%` (measured: the window was renamed `%`), so each `%` is sent as `%%`
(`noTime`, also for TM25's prompt texts). `mouse_word` and `mouse_line`
have no event to come from: puritty sets the pane's options
`@puritty_mouse_word` and `@puritty_mouse_line` from the cell clicked
(`Vt.wordAt`, `Vt.lineAt`) and reads the binding with those names instead,
so the right button over a word gives tmux's Search For, Type, Copy and
Paste items for it. From a key they are set empty, as tmux has no word
then.

**Shown** as tmux shows a menu (`menu.c`), measured on 3.8 with a tmux
client inside another tmux: a name expanded to nothing is a line, never
two together, none first or last; a name starting with `-` is dim, cannot
be chosen and has no key; the key in brackets at the right; from a key the
first item that can be chosen is chosen, from a click none. Placed by `-x`
and `-y`: `P` the pane's left with the menu's last row on the pane's last,
`W` at the window's tab, beside the bar, `M` at the clicked cell, `C` the
middle, `R` the right, a number as given; kept inside the panes' rows.
`[tmux] look = "tmux"`: single lines, the title in the middle of the top
edge, gray on dark, the chosen item black on yellow (`menu-selected-style`);
`"puritty"`: the view's amber box, the chosen item amber.

**Keys:** an item's own key runs it; Up, k, BTab and Down, j, Tab move;
Home, g and End, G; Enter or Space runs the chosen item; Escape, q, C-c
close. **Pointer:** a press inside chooses the item under it, letting go
over an item runs it once the pointer has been pressed or moved since the
menu opened (so letting go of the right click that opened it does not), a
press outside closes it, the wheel does nothing.

**The right button** (button 2 as puritty numbers them), over a pane whose
program does not take the mouse, without Shift, and when it is not the
paste button: tmux's own `MouseDown3Pane` binding, run as `if-shell -F -t
pane '#{mouse}' { binding }`, so it does nothing while tmux's `mouse` is
off, as in tmux.

**Checked:** packages/tmux 54 tests (Syntax 15: a menu's title, place and
items with a line and a disabled name; `-t =`, an empty command and
commands after; `if-shell -F`'s branches, a shell `if-shell` not read).
`bench/tmux/show.py --scenario menus`, Gilbert's tmux.conf, each look:
`C-a <` drawn at the tab with Swap Left and Right dim in one window, Down
Down to Mark; `n` opens the rename prompt and `renamed` names the window;
`C-a >` then `h` splits; Escape closes, tmux answering; `C-a >` Down Enter
splits; with `mouse on`, the right button over `wordy` shows Search For
wordy, Type wordy, Copy wordy, then `v` splits, `c` puts `wordy` in a
buffer, and a click on Zoom zooms. Every other scenario gives what it
gave. Every picture looked at.

**Not yet:** the pointer over an item does not mark it until a button is
pressed (puritty is told of motion only while a button is held); a style
in a name (`#[underscore]`) is left out, not drawn; `-O` (a menu that stays
open after its button is let go) and `-C` (the first item) are not read;
`MouseDown3Status` and the other status-line bindings are not offered,
since puritty's tab bar takes those clicks.

## TM28 · The panes' numbers, shown by puritty (2026-11-11)

Item 4 of TM24.5. `display-panes` (`prefix q`) draws on a terminal
client's own screen, which a control client has none of, so nothing was
shown and a digit typed after it went to the pane.

**Read** (`Tmux.Syntax.panesOf`): `-d` (how long, in ms), `-N` (no digit
chooses), the template (`select-pane -t '%%'` by default) and the commands
after it. `Tmux.Bindings.held` holds it, and `TmuxMode.runLine` runs it:
puritty asks `list-panes -F 'N #{pane_id} #{pane_index}'` for each pane's
index and shows them. `display-panes-time` is read as puritty attaches.

**Keys:** a digit that is a pane's index runs the template with it (filled
as a prompt's answer is, TM25) and closes the numbers; any other key closes
them and goes no further, as tmux's overlay takes it. **Time:** the
numbers close by themselves after `-d` or `display-panes-time`:
`TmuxMode.dueAt` is a time the loop wakes for (`Main.nextAt`), and
`TmuxMode.tick` closes them then, the window drawn again.

**Drawn** as tmux draws them, measured on 3.8 with a tmux client inside
another tmux: each index in `window_clock_table`'s digits, five cells
square and a cell apart, the first at the pane's middle less three cells a
digit and two rows up, in `display-panes-color` (blue) or
`display-panes-active-color` (red) for the active pane, with the pane's
size (`50x29`) at its top right in the same color; a pane too small for
the digits gets the index as text in its middle. `[tmux] look =
"puritty"`: the same digits, gray and the active pane's amber, without the
size.

**Checked:** packages/tmux 55 tests (Syntax 16: the default template; `-N
-d 3000`, a block and a command after). `bench/tmux/show.py --scenario
panes`, Gilbert's tmux.conf, each look, `display-panes-time` 3000 for the
pictures: `C-a q` shows 0, 1 and 2 over three panes, the active one's in
red or amber; `0` makes pane 0 active; after the time the numbers are gone
and typing reaches the pane. The prefix and menus scenarios give what they
gave.

**Not yet:** an index of two digits (ten panes or more) cannot be chosen,
as the first digit closes the numbers; tmux waits for the second.

## TM29 · tmux's status line (2026-11-11)

Item 5 of TM24.5. A control client has no status line (`status.c`), so
`status-left`, `status-right` and the window list as tmux formats them
were nowhere; puritty's tab bar showed the windows its own way.

**Asked** with subscriptions (`refresh-client -B`, tmux 3.2 on), sent as
puritty attaches: `#{T:status-left}` and `#{T:status-right}` (`T:` gives
strftime the result, so `%H:%M` is the time), `status-style`,
`window-status-separator`, the two lengths, and for every window (`@*`)
its `window-status-current-format` or `window-status-format`, expanded,
its matching style, and its flags. tmux sends each when it changes, at most
once a second; `Tmux.Control`'s `SubscriptionChanged` now carries the
window it is for (`-1` for none). Measured on 3.8: `status-style` is
`bg=themegreen,fg=themeblack`, the current window's style `underscore`,
the formats `#I:#W#{?window_flags,#{window_flags}, }`.

**Styles** (`Tmux.Style`): an option's style and a format's `#[…]` made
into SGR: named colors, `bright…`, `color…`, `#rrggbb`, 3.8's theme
names as the color they name, the attributes and their `no…`, `none`;
`default`, alone or as a color, is the base style's, as tmux takes a
window's `default` style to be the status line's and `#[default]` to go
back to it. What places text (`align`, `list`, `range`, `fill`) is left out.

**Drawn** by `[tmux] look`: `"tmux"` as tmux draws its status line,
compared with tmux 3.8 drawing in a tmux client inside another tmux: the
row in `status-style`, `status-left` cut to `status-left-length`, each
window's own text in its own style with the separator between,
`status-right` cut to its length at the right edge; a click on a window's
text selects it, as a tab did, and a menu placed at `W` goes to it.
`"puritty"`: the tabs as before, and `status-right` without its styles at
the bar's right, where what tmux or puritty says (TM24) goes in its place
until the next key.

**Checked:** packages/tmux 61 tests (Control 16: a subscription's name,
window and value; Style 5: theme, named, bright, 256 and RGB colors,
attributes on and off, a format's runs, `default` as the base's, strip).
`bench/tmux/show.py --scenario status`, Gilbert's tmux.conf, each look:
`[0] 0:first- 1:sh*` and `"nene" 13:46 11-Nov-26` as tmux shows them; then
`status-right` set to `#[fg=white,bg=red,bold] right #[default] %H:%M ` and
`status-left` to `#[fg=yellow]<#S> ` while attached, both drawn within a
second; in tmux's look a click on `0:first-` selects it. The tabs, prompts
and menus scenarios give what they gave.

**Not yet:** `status-justify` (centered or right window lists),
`status-position`, more than one status line (`status 2`) and `status off`
are not read: the bar stays where `[tmux] tabs` puts it; a wide character
counts one cell in the line's layout.

## TM30 · Marks, pane titles, bells and activity (2026-11-11)

Item 6 of TM24.5, the last. A terminal client shows these on its borders
and status line, which a control client has none of.

**Asked** with more subscriptions (TM29): `pane-border-status` and
`pane-border-style` for the session, and for every pane (`%*`) its
`pane-border-format` expanded (`T:`), its border's style (`E:` of
`pane-active-border-style` for the active pane, which in 3.8 is itself a
format: magenta when marked, green otherwise, `pane-border-style` for the
rest) and `pane_marked`. `SubscriptionChanged` now carries the pane too.
The windows' style subscription adds `window-status-bell-style` and
`window-status-activity-style` when the window's flag is set.

**Titles take a row tmux does not announce.** Measured on 3.8: with
`pane-border-status top`, panes on the window's top edge move down a row
and lose one, with `bottom` panes on its bottom edge lose their last row,
and the others' titles are on the line between panes; tmux sends no
`%layout-change` for any of it, the layout still giving the whole cell.
puritty places tiled panes so (`fitted`), sizes their terminals to it, and
sizes them again when the setting changes (`refit`).

**Drawn:** the title row as tmux draws it: the border's line along it, the
title from two cells in, the part after `#[align=right]` (3.8's `[f][z][x]`
buttons) at the right. In tmux's look the lines are in `pane-border-style`
and the active pane is framed in its own style; the marked pane is framed
in magenta in both looks. The tabs in puritty's look show a window's
alerts and marks after its name (`!` a bell, `#` activity, `~` silence,
`M` the marked pane, `Z` zoomed), a bell's tab white on red, activity's
amber; in tmux's look the window's own text carries its flags, in its bell
or activity style (`reverse` by default).

**Checked:** packages/tmux 61 tests (Control: a pane's subscription, `%2`
read as 2). `bench/tmux/show.py --scenario marks`, Gilbert's tmux.conf,
each look: `C-a m` marks the pane (tmux says `pane_marked` 1) and it is
framed in magenta; `pane-border-status top` set while attached moves both
panes down a row and shows `0 "nene"` and `1 "nene"` with `[f][z][x]` on
the line, as in a tmux client; `printf '\a'` in window 1 behind window 0
gives it `!` (tmux's flags `!-`), its tab red in puritty's look and
`1:sh!-` reversed in tmux's. Every other scenario gives what it gave.

**Not yet:** a click on the title's `[f]`, `[z]` and `[x]` does nothing
(tmux 3.8's `range=control` buttons); a floating pane's title is drawn
over its box but its own place is not changed; puritty does not ring or
flash for a bell in a pane it shows.

## TM31 · Copy mode drawn by puritty (2026-11-11)

TM25.4 found that tmux sends a control client a pane's output, never a
mode's screen, so copy mode looked like a plain pane: no cursor, no
selection, no scrolling. Gilbert uses vi copy mode from the keyboard.

**What tmux gives.** Measured on 3.8: `capture-pane -M` gives the pane's own
lines for copy mode, tree mode and clock mode alike, never what the mode
draws. The formats give copy mode's state: `scroll_position` (lines back
from the bottom), `history_size`, `copy_cursor_x` and `copy_cursor_y` (in
the pane), `selection_present`, the selection's ends
(`selection_start_x/y`, `selection_end_x/y`) in tmux's lines, 0 the
history's first, so the view's top line is `history_size` less
`scroll_position` (measured: after two lines up, a selection begun, a line
up and a page up, the end's line was 79 − 10 + 8 = 77), and
`rectangle_toggle`.

**Drawn from puritty's own copy of the pane.** puritty keeps every pane's
history (TM15, TM17), so copy mode is that history, scrolled: a pane in
copy mode (`copy-mode` or `copy-mode-vi` in its mode, TM25) is asked
`display-message -p -t pane 'C #{pane_id} #{scroll_position} …'` after
each key typed while it is the active pane, and when output reaches it.
A question already out is not asked twice: the pane is marked and asked
again when the answer comes, so the last answer is from after the last key
(found by the scenario: `Space k k $` typed at once left the picture one
key behind). The answer sets the pane's view back by `scroll_position`
(the bottoms of the two histories are the same screen, so the lines agree
however long either history is), puts the cursor at `copy_cursor_x/y`,
and inverts the selection, its ends included, by cells, or by columns for
a rectangle. `[scroll_position/history_size]` is at the pane's top right,
in `mode-style` in tmux's look and amber in puritty's. Leaving copy mode
(`%pane-mode-changed`) gives the pane back its own view.

**Checked:** `bench/tmux/show.py --scenario copy`, Gilbert's tmux.conf
(vi keys), each look, after 60 lines: `C-a [`; `k k k 0` puts the cursor
at 0,25 (tmux: `0/33 0,25`); `Space k k $` selects from `line 58` back to
the end of `line 56` (tmux: start 0,58, end 6,56) and the picture shows
exactly that; `C-b` scrolls to `[27/33]` with the selection grown up to
the cursor; `Enter` (3.8's vi table has no `y`) copies `6\nline 57\nl`
into tmux's buffer and leaves copy mode. Every other scenario gives what
it gave.

**Not yet:** ~~search matches are not marked (tmux highlights them)~~
(marked, TM41); a line
longer than the pane that tmux wrapped is where puritty wrapped it, which
is the same only when the pane's width has not changed since; lines beyond
puritty's own history (`[scrollback] lines`) cannot be shown. Tree mode,
the clock and tmux's other modes are not drawn (TM32).

## TM32 · The tree, the clock and tmux's other modes (2026-11-11)

The rest of TM25.4. tmux's other modes draw only on a terminal client's
screen, and `capture-pane -M` gives the pane's own lines for them too
(TM31), so there is nothing to mirror. Measured on 3.8, the default
bindings that enter one: `s` and `w` (`choose-tree -Zs`, `-Zw`), `t`
(`clock-mode`), `=` (`choose-buffer -Z`), `D` (`choose-client -Z`), `C`
(`customize-mode -Z`).

**The tree is puritty's.** `choose-tree` (and its old names
`choose-session`, `choose-window`) is held (`Tmux.Bindings.held`) and read
(`Tmux.Syntax.treeOf`: `-s`, `-w`, `-Z`, the template, by default
`switch-client -t '%%'`) and run by puritty, as menus are (TM27): it asks
`list-sessions` and `list-windows -a`, lists the sessions with an open
one's windows under it, folded (`-s`) or open (`-w`), the current session
or window chosen. Keys as tmux's tree mode takes them: Up, Down, k, j,
C-p, C-n, PPage, NPage, Home, End, g, G; Right and l open a session, Left
and h fold it; `+` and `-` open and fold all; Enter, or a row's digit,
runs the template with the row's id (`$1` a session, `@2` a window; tmux
takes either as `switch-client`'s target, measured); q, Escape and C-c
close it. Drawn in tmux's look as tmux lists it, `(0)` keys (since TM37 every
row's key, in both looks), `+`/`-`, the
windows joined by `├─>` and `└─>`, the chosen row in `mode-style`, over
every pane for `-Z`; in puritty's, the view's box. tmux's preview of the
chosen item, under the list, is not drawn.

**The clock is drawn.** Each pane's mode is kept by name with its table
(`modeLine`); a pane in `clock-mode` shows `HH:MM` in tmux's five-cell
digits and colon in `clock-mode-color` (blue; amber in puritty's look),
in the pane's middle, the cursor hidden. The time of day is tmux's: on
the first clock puritty asks `display-message -p 'D %H %M %S'` and keeps
its distance from the loop's clock, and `dueAt` wakes the loop as each
minute turns. tmux's own keys leave it, as before.

**The others are said.** A pane in `buffer-mode`, `client-mode`,
`options-mode`, or `tree-mode` entered some other way (another client, a
command) shows, in its middle, `tmux's buffer-mode is not drawn under -CC;
q leaves it`, the cursor hidden, since tmux has the pane's keys and the
pane would otherwise seem to take none.

**Checked:** packages/tmux 62 tests (Syntax 17: `-Zs`, `-Zw`, a template
with `choose-window`). `bench/tmux/show.py --scenario modes`, Gilbert's
tmux.conf, each look, two sessions: `C-a w Up Enter` goes from `main:1`
to `main:0`; `C-a s Up Enter` to `other:0`; `C-a s Escape` stays, tmux
answering; `C-a t` shows the time tmux gives (`14:26`) in its digits, and
q leaves `clock-mode`; `C-a =` with a buffer is `buffer-mode`, said, and
q leaves it. Every other scenario gives what it gave.

**Not yet:** the tree's preview (since TM35), tags (`t`), kill (`x`), sorting (`O`),
filters (`f`) and the panes level; choose-buffer, choose-client and
customize-mode are only said, not drawn.

## TM33 · The app's open checks, and a pane's box bounded (2026-11-11)

Part of `vt-core.md` §VC58's round (`geng checks` before local tabs). The
app's and packages' open checks, 27 of the 51, were sums and differences
over values nothing bounded:

- **`Tmux.Layout.Pane`** now carries a type invariant: its place and size
  0 to 16,384 on each axis, clamped as tmux's layout is read (`bounded`,
  both layout forms), and `down` keeps it below the bar. Every sum puritty
  makes from a pane's box is then inside `Int`, and the tabs to come, which
  will place panes too, inherit it.
- **Menus and views** (TM26, TM27): `menuPlace`, `menuBox` and `boxView`
  take the window's size, 1 to 1000, and promise their box inside it; the
  lines of a view are taken with `Array.dropFirst` instead of `top + r`;
  the pointer's cell and the bar's row are clamped where they are made.
- **The prompt's history** steps one back or one on without a sum that can
  wrap; `Tmux.Syntax.substitute` walks `%1` to `%9` by index.
- **`Window.decode`** (X11 and Windows alike) holds every read and step to
  the bytes left (`advance`), so a short or broken buffer ends the events
  instead of reading past it.
- **`Outbox.leading`** compares a piece against what is left of 64 KB;
  the settings window's host rows and suggestions clamp their indexes.

Checked with `geng checks`: 0 open (51 before); the tmux package's tests
(62); every tmux scenario of `bench/tmux/show.py` gives what it gave.

## TM34 · The panes' ids and terminals, held to the same count (2026-11-11)

`TmuxMode.State` keeps each pane's terminal in `panes` and its id at the
same index in `ids`. Nothing said they were as long as each other, so
`withPane` had to allow for an id with no terminal, and any update that
pushed to one and not the other would have shifted every pane after it
onto the wrong terminal. The record now carries the invariant
`Array.length ids == Builder.length panes`, which the compiler checks at
every place a `State` is built or updated (420 type invariant checks with
the others, 304 before). `sizePane` states that it keeps it, and the
layout's panes are sized by a loop, `sizeAll`, instead of a fold, since the
checker does not follow refinements through a function passed as a value
(geng-lang D829).

`withPane` still allows for the id not being found in `ids` at an index
the terminal list has: `core`'s `Array.findFirst` does not promise that
the index it answers is inside the array. That contract is `core`'s to add
(geng-lang `m4-proof-report.md` PR17).

Local tabs (`docs/terminator.md` TA3, `docs/research/reports/Terminal tabs
survey.md`) will hold the same shape, a list of sessions and the one
shown; their model should carry such invariants from its first line (the
shown tab inside the list, each tab's terminal beside its id) rather than
have them added afterwards.


## TM35 · The tree's preview (2026-11-12)

Gilbert, using `-CC` at work: "when I did prefix s to see my sessions
there was no preview of the panes like there normally is in a non -CC
tmux". TM32 had left it out.

**What tmux draws**, below the list: for a window, its panes laid out as
they are, each showing the part of its screen around the cursor; for a
session, its windows side by side, each its active pane, the current one
marked. puritty does the same with what it asks tmux.

**Asked.** When the tree has loaded, and after every key in it, puritty
looks at the chosen row; if it is not the row already previewed, it asks
`list-panes -t @W` (each pane's id, place, size, whether active, index)
or `list-windows -t $S` (each window's id, size, whether active, index and
name), and on the answer `capture-pane -p -t` each of them, at most
twelve. A window target captures its active pane, as tmux's own preview
of a session does. Each question carries the preview's serial
(`ForPreviewList`, `ForPreviewCapture`), so the replies for a row the user
has moved past are dropped, however fast the keys come.

**Drawn** (`drawPreview`). The list takes a third of the tree's height, or
fewer rows when there are fewer, then a line, then the preview: a
window's panes scaled from the window's cells to the area; a session's
windows side by side, as many as fit at ten cells or more. Each has a top
line with its label (the pane's index, or the window's `index:name`), the
active one's in the active color (tmux's green in tmux's look, amber in
puritty's), and below it the last lines of its capture with the blank
ones at the end dropped, so the text near the prompt shows, cut to the
width in cells (`clipCells`, with `Vt.Width`: Hangul and Han take two). A
tree too small for it (under 8 rows or 12 columns inside) has no
preview.

**Not yet:** the panes' colors (the capture is taken without `-e`, so the
text is drawn plain), and tmux's `v` (preview size) and its arrows across
a session's windows when there are more than fit.

**Checked:** `bench/tmux/show.py --scenario modes`, which now splits the
first window and writes a line in each pane and in the other session:
`C-a w` with `1: sh` chosen previews its one pane; Up to `0: first`
previews its two panes side by side, `left pane` and `right pane`, the
active pane's label amber; `C-a s` previews `main`'s two windows side by
side, `0:first` (its active pane) and `1:sh`; the same in tmux's look,
the active label green. Choosing still goes where it did (`main:0`,
`other:0`).

## TM36 · A filter for the views (2026-11-12)

Gilbert: "A search or filter would be nice in that tmux help panel. As a
user searches for terms, only those lines or items that have substring
that match show up." tmux's view mode has none; puritty draws the view
(TM26), so it can.

**Keys.** `/` in a view starts the filter. What is typed keeps the lines
that have it in them, ignoring case (`String.toLower` on both), from the
first; Backspace takes a character back and C-u all of them; Enter keeps
the filter and gives the keys back to moving (so `j`, Space and the rest
scroll what is left); Escape clears it, and Escape with a filter kept
clears it before a second closes the view. Text an input method commits,
or a paste, goes into the filter while it is typed (`typeInto`), so Hangul
filters too. Ctrl and Alt chords type nothing into it.

**Kept.** `View` holds every line (`all`) beside the lines shown
(`lines`), the filter and whether it is being typed; filtering is
`filtered`, from `all` each time, so a character taken back widens it
again.

**Drawn.** In puritty's look the box keeps the size every line gives it,
so it does not move as lines go, and its bottom edge says `/window  30 of
89`, with `Enter: keep  Esc: clear` while typing (`q: close  /: filter`
before). In tmux's look the same line is on the pane's last row in
`mode-style`, where tmux puts its own search prompt, and `[N/M]` counts
the lines kept.

**Checked:** `bench/tmux/show.py --scenario views`, Gilbert's tmux.conf,
each look: `C-a ?`, `/`, `windowx`, BackSpace shows `/window  30 of 89`
(his configuration binds the splits without notes, so `split` keeps
none, which a first try mistook for a fault); Enter and `j` scroll the 30;
Escape gives the 89 back; `q` closes; nothing typed reached the pane. The
other steps as before.

## TM37 · The tree's row keys (2026-11-12)

*Gilbert, 2026-11-12:* in `prefix s` tmux shows a number at each session,
and pressing it chooses the session; under -CC puritty did not draw them.

**What was wrong.** The keys were drawn only in tmux's look; puritty's
look, the default, had none, though the digits worked. tmux's keys go past
nine, and puritty's did not: measured on 3.4 and 3.8, with fourteen
sessions, through an attached client in a second tmux, tmux numbers the
rows `0` to `9` and then `M-a` to `M-z` (36 in all, the rows after that
have none), pads every key to the longest shown and puts one space after:
`(0) + s00` with ten rows or fewer, `(0)   + s00` and `(M-a) + s10` with
more. puritty's tmux look put two spaces after `(0)`.

**Now.** `treeRowKey` names a row's key as tmux does, `treeKey` takes the
digits and `M-a` to `M-z` by it, and both looks draw it: tmux's as tmux
does, in brackets and padded; puritty's in a column at the row's left
(`0`, `M-a`), the foot saying `Enter or a row's key: go`.

**Checked:** app tests 132. `bench/tmux/show.py --scenario modes` gains
fourteen sessions: in each look `C-a s 1` goes to `k01:0` and
`C-a s M-c` to `main:0`, tmux says; the pictures show the keys, tmux's
look as tmux draws it.

## TM38 · The pointer's shape over what can be dragged (2026-11-12)

*Gilbert, 2026-11-12, on Windows:* dragging the lines between panes works,
but the pointer stayed an I-beam over them, so nothing said a line could
be taken. The pointer should give that feedback.

**The shapes.** `Window.Pointer` had two, the I-beam and the arrow
(phase3-select.md §21). It has five more: a width resized, a height, both
(down and right, down and left) and a move. On Windows they are
`IDC_SIZEWE`, `IDC_SIZENS`, `IDC_SIZENWSE`, `IDC_SIZENESW` and
`IDC_SIZEALL`; on X the theme's `ew-resize`, `ns-resize`, `nwse-resize`,
`nesw-resize` and `move`, or their older names (`sb_h_double_arrow` and
so on), or the cursor font's glyphs when no theme answers, as the I-beam
and the arrow already were.

**Where.** `TmuxMode.pointerShape` answers by the same tests a press
makes: over the line right of a tiled pane, a width; below one, a height;
over a floating pane's box, the top edge (its corners too) a move, the
right and left edges a width, the bottom a height, the bottom corners
both; during a drag, the drag's, wherever the pointer is. The arrow over
tmux's tab bar, a menu, the tree, and a pane whose program takes the
mouse (Shift held gives the I-beam back); the I-beam over the rest of a
pane. Outside tmux, `Main.pointerShape` gives the arrow over puritty's
tab bar, the scroll bar, a menu and a question (the close question's
buttons, TB12).

**Motion for it.** The window sent motion with no button held only while
a program asked for every motion (mode 1003). It now sends it too while a
shape can change under a still button (`Main.hoverShapes`: tmux control
mode, the tab bar, the scroll bar, a menu or a question); such a motion
only moves `hover`, the pointer's place, and goes nowhere else, so what a
program or tmux is told is as before.

**The box's edges.** A box's right, bottom and left edges all resized
both its width and height, from its bottom right, and its left edge the
wrong way. A two-headed pointer there would have said otherwise, so each
edge now does what its shape says: the right edge the width, the bottom
the height, the left edge the width with the box's left following the
pointer (`move-pane -X` and `resize-pane -x` in one line), the bottom
corners both. The kinds are in `Drag`'s comment (4 to 7).

**Checked:** `bench/tmux/show.py --scenario pointers` on Xvfb with no
cursor theme reads the window's cursor through XFixes and names it by the
cursor-font glyph it matches: the left pane `text`, the line right of it
`width`, the line below the top right pane `height`, the box's top edge
`move`, right `width`, bottom `height`, bottom right corner `down-right`,
bottom left `down-left`, left `width`, inside it `text`, the tab bar
`arrow`, and a line's drag with the pointer off the line `width`. The
box's right edge dragged 5 right: `28x6` to `33x6`; its bottom 2 down:
`33x8`; its left 2 left: `4,2 33x8` to `2,2 35x8`. The `mouse` and `lines`
scenarios give what they gave; harness/pointer.py 54, mouse.py, select.py,
events.py 13 and the app tests 132 pass. On beelink1, GetCursorInfo over
the window: the I-beam over text, the arrow over the tab bar. The resize
shapes under tmux were not seen on Windows (no tmux there); they are the
same table's other entries.

## TM39 · Where puritty's -CC drawing falls short of tmux's: survey (2026-11-12)

Gilbert, 2026-11-12: "We had many issues today where our tmux -CC
rendering was missing things that regular tmux draws. … Do a survey
looking at tmux screens, or code, and see where our -CC rendering is
lacking." This is the survey; nothing is built.

**Two halves.** *Read*: everything tmux 3.8 draws on a client that is not
a pane's own output, from its source (`screen-redraw.c`, `status.c`,
`menu.c`, `popup.c`, `mode-tree.c` and the four modes, `window-copy.c`,
`window-clock.c`, `options-table.c`), each row against `TmuxMode.geng`
and TM24–TM38. *Measured*: about 55 scenes put side by side, a plain
client inside an outer tmux read with `capture-pane -p -e` over puritty
-CC's frame in tmux's look, same size and server state, on 3.8 and (15
scenes) 3.6a, which differ the same way. The notes are in
`research/research_notes/tmux -CC survey/` (`source.md`, file:line per
row; `measured.md`, per scene); the harness is `bench/tmux/compare/`
(`survey.py`, its scenes in `scenes.py`/`scenes2.py`, `pair.py` stacking
the two as one picture), writing to `.harness-work/tmux-compare/`.

**Why the gaps.** Not iTerm2's model: puritty sends keys through tmux's
tables (TM23), where iTerm2 does not. The gaps come from drawing tmux's
UI a piece at a time, each piece to tmux's *defaults*: puritty reads 12
formats by subscription (`statusSubscriptions`) and none of tmux's other
drawing options, so a user's `pane-border-lines`, `message-style`,
`status-justify` or `window-style` are not seen, and in tmux's look the
default colors are written in.

### TM39.1 · Matched

Status flags and styles (`* - Z ! # M`), zoom, the clock, menus opened by
keys, confirm and rename prompts, `display-message`, `prefix i`, prompt
history, remain-on-exit's `Pane is dead`, synchronize-panes, copy mode's
`[0/14]` and its selections (char, line, rectangle), border dragging,
floating panes.

### TM39.2 · The gaps, ranked for a keyboard user

Gilbert drives tmux by keyboard (`prefix s`/`w`, copy mode, the status
line), on 3.6 at work. *M* = seen side by side, *R* = read in source.

1. **Copy-mode search shows no matches** (M, R). tmux paints every match
   (`copy-mode-match-style`), the current one apart
   (`copy-mode-current-match-style`), and adds `(N results)`
   (`window-copy.c:5129`). puritty moves the cursor only. The count is a
   format (`search_count`); the highlighting means puritty searching its
   own copy of the history with the string it sent. Also: the `(search
   up)` and `(goto line)` prompts belong on the pane's last row, not the
   bar. Count and marks done (TM41), the prompts' place (TM42).
2. **emacs `C-r` in copy mode does not search** (M): tmux's cursor moved
   with each character typed and stayed after Enter; under puritty it
   did not move. A bug, not a missing drawing; first to look at. Fixed
   (TM40).
3. **The status window list overflows silently** (M, R). With many
   windows puritty draws from window 0, so the current one can be off
   the edge, with no `<`/`>` marks, and the list runs over
   status-right. tmux scrolls to keep the current window in view. Done
   (TM43).
4. **`prefix f` (find-window) is a dead end** (R): it enters tree mode
   with a filter (`cmd-find-window.c:107`), which puritty only says is
   not drawn. Done (TM45).
5. **The tree has no pane level** (M, R): no `+` on window rows, panes
   cannot be listed or chosen (`window-tree.c:360`). Done (TM44).
6. **The tree's other keys do nothing** (M, R): search `/ n N`, filter
   `f` (and the text typed after it is dropped, so its Enter switched
   session), kill `x` with its prompt, tags `t T C-t`, `:`, sort `O r`,
   preview `v`, swap `S-Up S-Down` (3.6), help `C-h` (3.7). `+`/`-` fold
   every row where tmux folds the current one. Search, filter and the
   folds done (TM44, TM45); tags, kill, `:`, marks, sort and `v` done
   (TM46); swap, help and 3.8's info view not yet.
7. **Tree rows and preview** (M, R): no window flags or titles in rows;
   the preview has no colors, its split is the reverse of tmux's (tmux
   gives the list ⅔), its title lacks `(sort: …)`; 3.8 draws `→` where
   puritty draws `─>` (3.6's `->` is closer).
8. **`prefix =`, `prefix C`, `prefix D`** (choose-buffer, customize-mode,
   choose-client): said, not drawn (known, TM32). Done: TM55 (`=`, `D`),
   TM62 (`C`).
9. **The command prompt** (R): no Tab completion, `C-p`/`C-n`, `C-y` or
   word motions; its history is puritty's, not tmux's (known, TM25).
   `status-keys vi`'s normal mode: Escape closes puritty's prompt (TM25.3).
10. **Borders** (M, R; done in tmux's look, TM48): junction cells (`┼ ├ ┬ ┴`) are gaps;
    `pane-border-lines` (double, heavy, simple, number, spaces) and
    `pane-border-indicators` (arrows) are not read; with two panes tmux
    colors half the divider, puritty all of it; the marked pane is a thin
    magenta line where tmux reverses the cells; in puritty's own look
    nothing marks a synchronized pane or one in a mode.
11. **`display-popup` draws nothing and says nothing** (M, R). A floating
    pane could stand in.
12. **Pane scrollbars** (3.6+, `pane-scrollbars`): not drawn (M); the
    pane keeps its full width where tmux gives a column.
13. **Styles not read** (M, R): `message-style`,
    `message-command-style`, `window-style`/`window-active-style`
    (dimmed inactive panes), the clock's and display-panes' colors,
    `clock-mode-style` (12-hour, seconds).
14. **The status line's own options** (M, R): `status-justify`,
    `status-position top`, `status 2`/off, a custom `status-format`
    (known, TM29). Justify and position done (TM49).
15. **`show-messages` (`prefix ~`)** (M): the log is mostly puritty's own
    control commands (`send-keys -K`, `refresh-client -B`, captures),
    lines cut at the edge, tmux's `message:` lines absent. tmux's log, so
    the fix is fewer and quieter commands, or puritty's own view of it.
    puritty's own commands left out of it (TM65).
16. **Smaller** (M): an error reads `parse error: unknown command: X`
    where tmux says `Unknown command: X`; a right press on the status
    line gives no window or session menu; display-panes' numbers in
    right-hand panes sit one cell left (fixed, TM65); the floating box's `[f][z][x]`
    sit two cells short of its right edge; messages' `display-time`
    expiry and a bell's sound in a shown pane were read (R), not seen.

### TM39.3 · Differences by design

- **A mouse drag in a pane** selects in puritty (TM17) and copies to the
  system clipboard; tmux's `mouse on` enters copy mode and makes a tmux
  buffer.
- **Escape closes a tmux prompt** in puritty; in tmux (3.6a and 3.8,
  measured) Escape does not cancel the emacs prompt, C-c does.
- **The wheel and the middle button over a pane** are puritty's (TM17),
  measured against a normal client by `keydiff.py input` (TM64): the
  wheel scrolls the pane's view, or sends arrows when its program is on
  the alternate screen. A normal client with tmux's `mouse off` sends
  arrows on either screen, because tmux puts its own terminal on the
  alternate screen. With `mouse on` it gives the wheel to tmux's binding,
  which sends a program on the alternate screen nothing. The middle
  button pastes the selection, where with `mouse on` a normal client
  runs tmux's `MouseDown2Pane` (`paste-buffer`, tmux's own buffer).

### TM39.4 · What the gaps share, for Gilbert

Three kinds of work, undecided:

- **Read the user's options** (items 10, 12–14 and part of 3): subscribe to the
  drawing options as the 12 status formats are (`refresh-client -B`; an
  option's name is a format, `#{pane-border-lines}`), so a change is
  seen when made, and draw from them instead of tmux's defaults.
  One change reaches many rows.
- **Finish the tree** (4–7, then 8): it is the mode Gilbert uses most;
  the view's filter (TM36) and the tree's keys (TM37) are the start.
- **Copy-mode search** (1, 2): the bug first, then the count, then the
  highlighting.

## TM40 · Incremental search: copy mode's emacs C-r and C-s (2026-11-12)

TM39's item 2, the first of its work. tmux's copy-mode `C-r` and `C-s`
are `command-prompt -i … { send -X search-backward-incremental -- '%%' }`
(3.6a and 3.8 alike). puritty read the prompt without its `-i` and ran
the command once, on Enter, with the bare line. tmux's
`window_copy_cmd_search_backward_incremental` (`window-copy.c:2936`)
takes the argument's first character as *which search*: `=` the line as
it is, `-` the next match up, `+` down. `3` was read as that character,
leaving an empty string, so nothing was searched and the cursor stayed.

**Now as tmux's prompt does** (`prompt.c`, `prompt_incremental_start`
and `prompt_key`): `Syntax.Prompt` keeps `incremental`. The command runs
as the prompt opens, with `=` and the empty line; after every change to
the line with `=`; on C-r with `-` and C-s with `+`, or, on an empty
line, with `=` and the first text (`-I '#{pane_search_string}'`, the last
search), which an incremental prompt does not put on the line. Enter
closes it with nothing more run, the line kept for Up; Escape, C-c and
C-g close it. Keys that move the caret run nothing (`TmuxMode.
incrementalKey`), since the same line again would go on to the next
match.

**Checked against tmux** (`bench/tmux/compare/survey.py --scenes scenes2
--only copy-emacs2,copy-emacs3`): the cursor after each key of `C-r 3`,
`C-r`, `C-r`, `BSpace`, `5`, Enter, `C-r C-r` (recall), `C-r`, `C-s`,
`C-c`, then a selection and `M-w`'s buffer, all equal to a plain
client's on 3.8. On 3.6a the search positions are equal too; the plain
3.6a client in that harness lost an `Up` and a `C-e` sent to it, so two
positions after the search differ there, puritty's being the right ones.
App tests 132, tmux package 62, `show.py` prompts, copy, prefix and modes
unchanged.

**Not matched yet:** in 3.8 the arrow keys and Page Up/Down in an
incremental prompt go on to copy mode with the prompt left open
(`prompt_check_move`); puritty keeps them for the line and its history.
A paste into the prompt changes the line without running the search.

## TM41 · A copy-mode search's matches marked, and counted (2026-11-12)

TM39's item 1. tmux marks every match of a copy-mode search in
`copy-mode-match-style` (black on cyan by default), the one at the cursor
in `copy-mode-current-match-style` (black on magenta), and its default
`copy-mode-position-format` (3.6a and 3.8 alike) says `(N results)` after
the position, `N+` when the count stopped early, `(timed out)` when the
search did.

**tmux does not hand the marks over**: `capture-pane -M` gives copy
mode's text without its styles (measured, 3.6a and 3.8). So puritty
finds them itself, in its own copy of the pane's rows
(`Search.matchesIn`), as tmux's `window_copy_search_marks` does: within a
row, left to right, not overlapping, ignoring case when the search has
no capitals (`window_copy_is_lowercase`). The search string, whether
marks are up, the count and its two flags come with copy mode's state
after each key (`copyFormat`: `search_present`, `search_count`,
`search_count_partial`, `search_timed_out`, `pane_search_string`), and
the position reads `[0/14] (14 results)`. The marks are drawn on tiled
panes before the floating boxes and on floating ones after.

**Checked side by side** (`bench/tmux/compare`, `copy-emacs2`,
`copy-wrapped-search`): the same cells marked as a plain client's, the
same current match, the same `(14 results)` and `(7 results)`. puritty
draws its cursor on the current match's first cell where the plain
capture shows none. Tests: `Search` (5), app 137; `show.py` copy and
prompts unchanged.

**Not matched:**
- vi's `/` and `?` (`search-forward`, `search-backward`) are regular
  expressions in tmux, and puritty has none: a search holding any of
  `. [ ] ( ) * + ? { } | ^ $ \` is not marked. Its count is still said.
- A match across a wrapped row's end is found by tmux and not by puritty.
- The styles are tmux's defaults, not the user's (TM39.4, reading the
  options).

## TM42 · A prompt asked in the pane (`command-prompt -P`) (2026-11-12)

The last of TM39's item 1. 3.8's copy-mode bindings ask their searches
and `(goto line)` with `command-prompt -P` (`key-bindings.c:579`), which
puts the prompt on the pane's last row rather than the status line; 3.6a's
have no `-P` and ask on the status line, as puritty did. `Syntax.Prompt`
keeps `inPane`, and in tmux's look such a prompt is drawn on the active
pane's last row (`TmuxMode.promptAt`), its text and one cell after it in
the message color and the rest of the row blank, as tmux draws it.
puritty's own look asks in its box either way.

**Checked side by side** (`bench/tmux/compare`, `copy-emacs`,
`copy-vi`): `(search up) 1` and `(goto line)` on the same row, colored
over the same cells. Tests: app 137, tmux package 62; `show.py`
prompts, copy and modes unchanged.

## TM43 · A status line too long for the window (2026-11-12)

TM39's item 3. puritty laid the windows out from window 0 and dropped
what passed the edge, and dropped status-right whenever the list
reached it, so with many windows the current one could be off the bar.
tmux's default `status-format` makes the windows a list
(`#[list=on]`, the current window `list=focus`, `<` and `>` as its
markers), and `format_draw_left` and `format_draw_put_list`
(`format-draw.c:125`, `:228`) fit it: the list gives way first, then
status-right from its start, then status-left; a list cut short is shown
from its focus's middle less half the width, kept within the list, with
`<` where windows are hidden on the left and `>` on the right, each
taking a cell of the list. `TmuxMode.tmuxBar` now does the same, and
the windows' click ranges move and are cut with the text they belong to.

**Checked side by side** (`bench/tmux/compare`, `status-overflow` and
`status-overflow-click`): with twelve long-named windows, window 6
current, `[main] <ong-window-name-5  6:a-rather-long-window-name-6*
7:a-rather-long-win>"nene" …` on both, and with window 11,
`[main] <e-9  10:…  11:a-rather-long-window-name-11*"nene" …`; a click on
window 7's text selects it on both, a click on `<` does nothing on both.
App tests 137; `show.py` status, tabs and mouse unchanged.

**Not yet** (TM29): `status-justify` other than left, the status line on
top, more than one line, a custom `status-format`.

## TM44 · The tree's rows as tmux's, and its pane level (2026-11-12)

TM39's item 5 and the rows of item 7. puritty listed sessions and
windows in a text of its own (`0: first* (3 panes)`), with no panes.
tmux's tree (`window-tree.c`, `mode-tree.c`) lists each session, an open
one's windows, and an open window's panes, and every window has its
panes to open, so every window row has a `+`.

**The rows' text is tmux's.** puritty asks the three lists with tmux's
own `WINDOW_TREE_DEFAULT_FORMAT` pieces (`TmuxMode.treeQueries`):
`#{session_windows} windows` with the group and `(attached)`; a window's
name and `window_flags` with its pane's title when it has one pane; a
pane's command and flags with its title. Those are the same in 3.6a and
3.8 but for a pane's flags: 3.8's `pane_flags` (`1: sh-` for the last
pane), 3.6a's `*` and `M`. tmux's version is kept at attach in tenths
(`State.version`, 36 or 38) for that and for the branch's arrow, `→` in
3.8 and `>` in 3.6a (measured). Fields are split at tabs, so names keep
their spaces.

**Drawn as tmux draws them:** a window's and a pane's number right-
aligned to the widest at its depth (`mode_tree_align`), the branch
`├─`/`└─`, a pane row's `│   ` or four spaces as its window is last or
not, `+`/`-` for a row with something to open. Keys as `mode_tree_key`:
Right, l and `+` open a row or go down from an open one; Left, h and `-`
close an open row, or close its parent and go there, or at the top go up
a row; M-+ and M-- open and close every session (before, `+` and `-` did
that). A pane's row chooses `%id`; its preview is that pane alone.

**Checked side by side** on 3.8 and 3.6a (`bench/tmux/compare`,
`choose-tree-s`, `tree-pane-choose`): the same rows, character for
character, in the session tree, its windows open, a window's panes open,
and `prefix w`; Enter on a pane row makes the same pane active; Left
from a pane row and again close the same rows. App tests 141;
`show.py` modes unchanged.

**Not matched:** tmux's `choose-tree -Z` zooms the pane while the tree is
up, so its window rows read `*Z`; puritty draws its tree over the window
without zooming. 3.8's colors in the rows (flags in grey, a marked
window magenta) are not drawn. Search, filter, tags, kill, sort and the
preview's proportions are TM39's items 4, 6 and 7, still to do.

## TM45 · The tree's search and filter, and find-window (2026-11-12)

TM39's items 4 and 6 (in part).

**Search** (`/`, `?`, C-s ask `(search) `; n and N again): as
`mode_tree_search_forward` and `_backward`, every session, window and
pane in the tree's order, folded or not, from the row after the chosen
one round to it, matched by name (a pane by its command, as
`window_tree_search` reads `osdep_get_name`), case ignored when the
search has no capitals; the rows above the match are opened.

**Filter** (f asks `(filter) ` with the filter as it is; `choose-tree
-f`): a tmux format tested on every pane. tmux tests it for puritty:
`list-panes -a -f FILTER` names the panes that pass, and a window is
kept with such a pane, a session with such a window. When none passes,
or tmux cannot read the filter, every row stays. After a change the
chosen row stays, or the first row is chosen when it was filtered out,
and a session or window that comes back is open (measured on 3.8).

**Start state by flags** (`window_tree_init`): `-s` every session
folded on the current one, `-w` the sessions open on the current window,
neither (`choose-tree`, `find-window`) everything open on the active
pane, or its window when it is the window's only pane. puritty treated
neither as `-w` before.

**find-window** (`prefix f`: `command-prompt { find-window -Z -- '%%' }`)
opens the tree with the filter `cmd-find-window.c` builds from the text
and its `-C`, `-N`, `-T`, `-i`, `-r` (`Syntax.findFilter`). The command
filled from a prompt's answer used to go straight to tmux; now one that
puritty runs itself (`runsHere`) runs in puritty (`closePrompt`), so the
tree opens.

**C-c no longer closes the tree**: tmux's tree closes on q, Escape and
C-g only (`mode_tree_key`), and C-g now does in puritty.

**Checked side by side** on 3.8 and 3.6a (`bench/tmux/compare`,
`tree-search-filter`): `/logs`, `/sec`, `n` going round, the filter
`#{==:#{session_name},other}`, clearing it, and `prefix f second`, the
same rows and the same chosen row at each; Enter after find-window lands
in the same session and window. Tests: tmux package 62 (find-window's
and `-f`'s filters), app 141; `show.py` modes and prompts unchanged.

**Not yet:** the tree's `(search)`/`(filter)` prompts take no history
of tmux's; `no matches` is not said in the preview's top line; tags,
kill, sort, `v`, swap and help.

## TM46 · The tree's kill, tags, commands, sort and preview (2026-11-12)

The rest of TM39's item 6, and item 7's list and preview proportions.
From `window_tree_key` and `mode_tree_key`:

- **x** asks `Kill session NAME? `, `Kill window N? ` or `Kill pane N? `
  (one key; `y` kills, as `window_tree_kill_each`); **X** asks `Kill N
  tagged? `; **:** asks `(current) ` or `(N tagged) ` for a command run
  with `%%` each target. **m** marks the row's pane (`select-pane -m`),
  **M** clears the mark; **H** goes back to the active pane's row.
  After each, the three lists are asked again with the rows kept open
  and the chosen row kept where it still is (`reloadTree`), as tmux
  rebuilds.
- **t** tags the row (its parents and children untagged) and goes down a
  row, or untags it; **T** untags all; **C-t** tags every session. A
  tagged row's name has a `*` after it.
- **O** turns the order: 3.6's `index`, `name`, `time`, 3.8's `index`,
  `name`, `activity`, `z` (`sortNames`); **r** reverses it. Sessions by
  id, windows by number, either by name, or by activity (most recent
  first, then by name, from `session_activity` and `window_activity`);
  panes by number always, as tmux's but for time (a pane's last use,
  which tmux does not say), `z` as index. Sessions sorted by id is new:
  puritty listed them in `list-sessions`'s order, by name; measured,
  tmux lists `zed`, `alpha`, `mid` as made, so `show.py modes`' `C-a s 1`
  now chooses `other`, its second session, not `k01`.
- **v** turns the preview: as tmux draws it, off, big, as
  `mode_tree_key`. The list's height is `mode_tree_set_height`'s: two
  thirds of the pane with the preview, half when the rows are fewer, all
  when that leaves under ten; a quarter with the big preview. The
  preview is a box whose top line says ` NAME (sort: ORDER)`, 3.8 adding
  ` (view: preview)`, and ` (filter: active)` or `no matches`.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `choose-tree-s`,
`tree-kill`, `tree-session-order`): `v`, `t` and its move, the kill
questions and their effect (`other` killed, the chosen row then on
`spare`; two tagged rows killed with X, the chosen row on `1`), the
filter, `O`, the box's top line at the same row; and on 3.6a the same
but one step where the plain 3.6a client in the harness lost a Down
(tmux asked `Kill window 2?` from row 3 where its start row, the current
window, measured in `choose-tree-s`, puts four Downs at row 4). App
tests 141.

**Not yet:** S-Up/S-Down swap (3.6), C-h help (3.7), 3.8's `i` info
view, `<`/`>` scrolling the preview, the mouse in the tree; 3.8's colors
in the rows; the preview's inside is puritty's own drawing (each pane or
window with a label line), not tmux's (borders and a centered label box).

## TM47 · tmux's drawing options read: the styles (2026-11-12)

TM39.4's first kind of work, begun. One more subscription
(`puritty-opts`, `refresh-client -B`) carries tmux's drawing options,
tab between (`optionNames`): an option's name is a format, so tmux sends
the user's value whenever it changes, and an option a version lacks
comes as nothing and its default is used. The styles are drawn from it
(`colorsOf`): `message-style` for messages and prompts, `mode-style` for
the tree's chosen row, copy mode's position and the views' lines and the
modes' labels, `menu-selected-style` (or `mode-style`) for a menu's
chosen item, and `copy-mode-match-style` and
`copy-mode-current-match-style` for a search's marks. 3.8's theme names
(`themeyellow`) read as their colors.

**Checked** (`bench/tmux/compare`, `custom-message-style`): with
`message-style bg=red,fg=white` the prompt and `prefix i`'s message are
red on white. App tests 141; `show.py` prompts, menus, modes, copy
unchanged.

The other options in the list (border lines and indicators, the status
line's justify, position and lines, `window-style`, scrollbars, the
clock's and display-panes' colors) are read and waiting for their
drawing, which comes next.

## TM48 · The panes' borders drawn as tmux draws them (2026-11-12)

TM39's item 10, in tmux's look. puritty drew a line right of and below
each tiled pane, the active pane's frame over it in its color, and the
marked pane's frame magenta: the cells where lines meet were gaps, the
whole divider took the active color, and `pane-border-lines` and
`pane-border-indicators` were not read.

**Now cell by cell, as `screen-redraw.c`** (`Tmux.Borders.cells`, in the
tmux package with its own tests): a cell is a pane's border by
`screen_redraw_pane_border`, looking from the active pane round the
list; its glyph by which of its four neighbors are borders
(`screen_redraw_type_of_cell`: the corners, the joins and the cross) in
the set `pane-border-lines` names (single, double, heavy, simple,
number, spaces); its color `pane-active-border-style` when the cell is
the active pane's border and `pane-border-style` otherwise; with two
panes and `pane-border-indicators` `colour` (the default) or `both`,
each pane's side of the divider is its half, so the active color takes
half (`screen_redraw_two_panes`); the marked pane's border reversed; and
with `arrows` or `both`, an arrow on the active pane's border pointing
at it, one cell in. The window is the layout's size, not puritty's
canvas. Pane titles (`pane-border-status`) are drawn over the cells as
before. puritty's own look keeps its lines.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `borders-2`,
`-3`, `-4`, `border-lines-double`, `-heavy`, `-simple`, `-number`,
`border-indicators-arrows`, `-both`, `marked`, `border-status-top`,
`-bottom`, `border-styles`): the joins, the half-colored divider of two
panes (rows 0 to 14 grey, 15 on green, as tmux's), double and heavy
lines and their joins, the digits of `number`, the arrows at the same
cells, the marked pane's reversed border. Tests: the tmux package's
`Borders` (7: glyphs, both halves, indicators off, a cross, double, an
arrow), 69 in all; app 141; `show.py` lines, marks and mouse unchanged
(the lines still drag).

**Not matched:** a pane's index for `number` is its place in the
window's list, which is its index unless panes were moved; scrollbars
(3.6) are not drawn, so their columns are not left; floating panes keep
puritty's boxes.

## TM49 · status-justify and status-position (2026-11-12)

Part of TM39's item 14, from the options TM47 reads. **status-justify**
places the window list as tmux 3.8 draws it (measured side by side): `left`
after status-left; `centre` centered between status-left's end and
status-right's start (`format_draw_centre`'s middle); `absolute-centre`
centered on the whole row; `right` against status-right, which stays at
the edge (not after it, as `format_draw_right` reads at first sight: the
list region is between the two sides). Trimming, the `<`/`>` marks and the
click ranges move with it (TM43).

**status-position** decides, in tmux's look, whether the bar is at the
top or the bottom, once tmux has said (`barPlaced`); until then, and in
puritty's own look, `[tmux] tabs` does as before (kept apart as
`barTopConfig`).

**Checked side by side** on 3.8 (`bench/tmux/compare`,
`status-justify-centre`, `-right`, `-absolute-centre`, `status-top`): the
list at the same column in each (35, 59 before `"nene"`, 42), and with
the status on top a click at row 10 picks the same pane on both. App
tests 141; `show.py` status, tabs, mouse and `status-overflow-click`
unchanged.

**Not yet:** `status off` and `status 2` to `5` change how many rows
tmux's panes have, which puritty tells tmux (`refresh-client -C`) and
does not yet vary; a custom `status-format` is not drawn (TM29).

## TM50 · Keys no binding takes go straight to the pane (2026-11-12)

Gilbert's open bug (Enter did nothing in Claude Code under `-CC`, other
keys fine; diagnostic log, DG1–DG5) found with the log and reproduced
here. puritty sends every named key with `send-keys -K` (TM23), so that
tmux's bindings fire. tmux keeps `-K`'s internal "sent" flag on a key no
binding takes, and its encoder then drops every key that is an escape
sequence (Down, F5: 3.7c and 3.8 drop it, 3.6a writes a wrong byte) and,
when the pane has extended keys (`extended-keys on`, which Claude Code's
setup advises, and the program asking for modifyOtherKeys, as Claude Code
does), Enter too. Text (`-K -H`), Backspace and C-c still arrived, which
is what Gilbert saw. Measured on 3.6a, 3.7c and 3.8 with a logging
program behind a control client; the report is
`upstream/tmux-send-keys-K-drops-keys.md`.

**Now:** in the root table, with the pane in no mode, a named key that is
not a prefix and has no root binding is sent to the pane by name
(`send-keys -t %N Name`, `Command.sendKeyTo`), which tmux encodes for the
pane's modes; a key a binding may take still goes `-K`, so the prefix,
`bind -n` and the modes' tables work as before.

**Checked** end to end (puritty on Xvfb, tmux 3.8, `extended-keys on`,
the pane in Ext 2): `a`, Enter, Down, Backspace, F5, C-c, `b`, Enter
arrive as `a`, `\r`, `\e[B`, `\x7f`, `\e[15~`, `\e[27;5;99~`, `b`, `\r`,
and `C-b c` still opens a window. Claude Code itself in tmux 3.8 behind a
control client ignored `-K Down` at its trust question where a normal
client's Down moved it. App tests 141, tmux package 69; `show.py` prefix,
prompts, copy, modes, menus unchanged.

**Confirmed by Gilbert** (2026-11-12): the pane reads `VT10x` before the
bad state and `Ext 2` in it, as the cause says. Still open: a
`send-keys Enter` from the prompt did not help there, though without
`-K` tmux delivers Enter in Ext 2 here; a Claude Code that had already
lost Enters may not have been taking keys. **The fix confirmed by
Gilbert at work** (2026-11-12, Windows preview 2026-11-12c from
`ace0f29`): Enter reaches Claude Code under `-CC`, and `prefix s` lists
the sessions in the order made (TM46).

## TM51 · The clock's style and color, display-panes' colors (2026-11-12)

The rest of TM39's item 13's colors. From the options TM47 reads:
`clock-mode-colour` colors the clock's blocks, `display-panes-colour`
and `display-panes-active-colour` the panes' numbers. `clock-mode-style`
is drawn as `window-clock.c` writes it: `24` `HH:MM`, `12` with `%l` (a
space before a one-digit hour) and `AM`/`PM`, either `-with-seconds`;
the big glyphs gain tmux's `:`, `A`, `P` and `M`, and with seconds the
clock is drawn again each second rather than each minute.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `clock-12`,
`clock-24s`, `panes-colours`): ` 9:26 PM` in green, `21:26:32` a second
apart from tmux's capture, the numbers yellow and the active one magenta.
App tests 141; `show.py` panes unchanged.

## TM52 · window-style and window-active-style (2026-11-12)

TM39's item 13: configs that dim the inactive panes. tmux gives each pane
default colors, `window-style` and, for the active pane,
`window-active-style` laid over it (`tty_default_colours`); a cell with
no color of its own takes them. The terminal core's `compose` copied a
pane's cells with the canvas's defaults, so it gains `composeStyled`
(`compose` with no colors calls it): each place carries a foreground and
a background that cells take where they have none, colors as the core
holds them (`TmuxMode.vtColor` turns the SGR tmux's style parser writes
into them). In tmux's look only.

**Checked** (`bench/tmux/compare`, `window-style`, with
`fg=colour245,bg=colour236` and an active `bg=black`): the inactive panes
dimmed through, the active one black; tmux's capture cannot show it for
blank cells (`capture-pane` writes no colors for them), so its picture is
only a check on the cells with text. Core tests 94, app 141; `show.py`
attach and mouse.

**`show.py mouse` moved, and it should have earlier:** its last line,
what the left pane's `cat -v` got after Up, now ends `^[OA`. Before TM50
tmux dropped that Up (sent with `-K`), and the line, printed and not
checked, showed it missing on every run.

## TM53 · Pane scrollbars (2026-11-12)

TM39's item 12. `pane-scrollbars` (3.6) `on` takes the scrollbar's
columns out of each pane's layout cell (measured on 3.8: a 40-wide cell
is a 39-wide pane; with `pane-scrollbars-position left` the pane moves
right, and `pane-scrollbars-style`'s `width=` and `pad=` are the columns);
`modal` leaves the pane its width and shows the bar only in a mode.
puritty sized its panes from the cells, a column too wide, and drew no
bar.

**Now** (tmux's look): the panes are fitted as tmux fits them
(`fittedIn`, used for both their terminals' sizes and where they are
drawn), and refitted when the option changes; each bar is drawn as
`screen_redraw_draw_pane_scrollbar`: the track in the style, the slider
reversed, out of a mode at the bottom as tall as the screen's share of
screen and history, in copy mode where the view is (from copy mode's
`history_size` and `scroll_position`); none on the alternate screen. The
borders are worked out around the cells, scrollbar included, as tmux's
are (`withScrollbar`).

**Checked side by side** on 3.8 (`bench/tmux/compare`,
`pane-scrollbars`, `pane-scrollbars2`): the left pane's slider in the same
rows at the bottom and, in copy mode scrolled up, in the middle; the
right panes' full sliders (tmux draws them; `capture-pane` trims the
blank cells, so its picture leaves them out). App tests 141; `show.py`
lines and attach unchanged.

**Not matched:** out of a mode the history is puritty's own (its
scrollback setting), which can be shorter than tmux's; 3.8's `autohide`
is drawn as off.

## TM54 · status off, and two to five status lines (2026-11-12)

The rest of TM39's item 14. Under `-CC` puritty tells tmux its size
(`refresh-client -C`) less the status line's row, always one. Now the rows
are tmux's `status` (`statusRows`, in tmux's look): `off` none, so the
panes have every row and tmux's prompts and messages go over the last;
`2` to `5` that many, the lines after the first each `status-format[n]`
as tmux expands it (subscribed, `#{T:status-format[n]}`), drawn from the
left in its own styles on the terminal's colors (as 3.8 draws them,
measured), the list's `<` `>` markers left out. A change to `status`
sends tmux the new size. The panes' offset below a top status, a menu's
area, the zoomed tree and a floating box's drag all take the rows from
`statusRows`; clicks on the window list need a status line to be on.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `status-off`,
`status-top-2lines`): tmux's window 100x30 with the status off and
100x28 with two lines on top, as a plain client's; the same rows of the
panes; the second line ` P: 0:[nene]*` on the terminal's background.
App tests 141; `show.py` status, tabs, mouse, menus unchanged.

**Not matched:** a list in a second line is not trimmed or kept around
its focus (TM43 does the first line's); `#[align=right]` and `centre`
in those lines are drawn from the left; a custom `status-format[0]` is
still not read (TM29).

## TM55 · choose-buffer and choose-client drawn by puritty (2026-11-12)

TM39's item 8 (in part). `prefix =` (`choose-buffer -Z`) and `prefix D`
(`choose-client -Z`) entered tmux's modes, which a control client does not
see; puritty only said so. Now held like `choose-tree` (`Bindings.held`)
and read (`Syntax.listOf`: `-f`, `-Z`, the template, tmux's defaults
`paste-buffer -p -b '%%'` and `detach-client -t '%%'`), the list is
puritty's (`Listing`), as tmux's mode tree draws a flat list:

- rows `name: text` with tmux's own default formats
  (`WINDOW_BUFFER_DEFAULT_FORMAT` `#{t/p:buffer_created}: #{buffer_sample}`,
  the client's `... : session #{session_name}`), each row's key;
- buffers newest first in tmux's own order (the order of `list-buffers`'
  answer: their created seconds can tie), by name, by size; clients by
  name, width, creation, activity; 3.8 calls the buffers' first order
  `creation`, 3.6 `time`;
- keys: the moves, row keys, `t T C-t`, `O r`, `v`, `/ n N`, `f` (tmux
  tests the filter, `list-buffers -f`), q, Escape, C-g; buffers: Enter
  and `p` paste and close, `P` paste the tagged, `d`/`D` delete; clients:
  Enter the command, `d`/`x`/`z` detach, detach and kill, suspend, with
  `D X Z` for the tagged; a control-mode client, puritty's own among them,
  is not suspended (tmux takes no key from it again, TM24). After each the
  list is asked again, the chosen name kept; with nothing left it closes;
- a buffer's preview is its first lines (`show-buffer`), under ` NAME
  (sort: ORDER)`.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `buffers`,
`choose-client`): three buffers made in one second listed gamma, beta,
alpha as tmux lists them; `d` on beta, the chosen row then alpha; Enter
pasted `first text` and closed; the preview's top line and text; the
client row's form. Tests: tmux package 70 (`listOf`), app 141.
`show.py modes`' `C-a =` line now reads nothing for the pane's mode
(it read `buffer-mode`): tmux no longer enters it, puritty shows the list.

**Not yet:** `e` (edit a buffer), a client's preview (tmux draws its
screen), searching a buffer's contents rather than its sample,
customize-mode (`prefix C`, done in TM62).

## TM56 · display-popup as a modal floating pane (2026-11-12)

TM39's item 11. A popup is drawn on a client's screen as an overlay,
which a control client never gets: under `-CC` `display-popup` answers
`ok` and nothing shows (measured on 3.8). Now its bindings are held
(`Bindings.held`) and read (`Syntax.popupOf`: `-w`, `-h`, `-x`, `-y`,
`-d`, `-E`, the command), and on 3.8 puritty asks tmux for a modal
floating pane in its place (`new-pane -O`, which puritty draws, TM8):
the popup's size (half the window by default, `N%` as tmux takes it), its
place (`C`, the default, centered: half the space left, in `%` or cells),
its directory and command; without `-E` the pane waits for a key once
its command ends (`-k`), as a popup stays. The title is left out: `-T`
would be the pane's title, which the default status line shows. Before
3.8 there are no floating panes, and puritty says so at the bar.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `popup`: `bind p
display-popup -E -T hello 'echo popped; sleep 4'`): the floating pane
where tmux's popup is, about its size, showing `popped`; the window two
panes, the second modal (`O` in its flags). Tests: tmux package 71
(`popupOf`), app 141.

**Not matched:** the popup's border styles and title, `-B` (no
border), `-x`/`-y` given as `P`, `M`, `W`, `S` or `R` (drawn centered),
`-e` environment, `-EE`.

## TM57 · The command prompt's Tab, C-p, C-n, words, C-t and C-u (2026-11-12)

TM39's item 9. From tmux's `prompt_key` (3.8) and `status_prompt_key`
(3.6a):

- **Tab** in the colon prompt completes the first word from tmux's
  commands (`list-commands`, asked once at attach): one match whole with
  a space after it, more as far as they agree; aliases are not completed
  (measured: `sel` gives `select-`, where the aliases would stop it at
  `select`). tmux shows a menu of the matches; puritty does not.
- **C-p** and **C-n** go back and on through the answers, as Up and Down.
- **M-b**/**C-Left** and **M-f**/**C-Right** move by words; **C-t** swaps
  the two characters before the caret.
- **C-u** clears the whole line, as both versions do; puritty deleted
  only what was before the caret.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `command-prompt`):
`split-w` Tab gives `split-window `, C-u then `sel` Tab gives `select-`,
the history's Up. App tests 141; `show.py` prompts unchanged.

**Not yet:** C-y (tmux pastes its newest buffer, or 3.8 what C-k and
C-w removed), completion of options and targets, the matches' menu, vi
keys in the prompt (`status-keys vi`), tmux's own prompt history.

## TM58 · The status line's right button, and run -C (2026-11-12)

One of TM39's smaller items. tmux binds the right button on the status
line: `MouseDown3Status` (a window: its menu, `-t=` that window) and
`MouseDown3StatusLeft` (status-left: the session's menu, inside `run -C
"display-menu ..."`). puritty ran neither. Now a right press on tmux's
status line in tmux's look runs the binding for where it is (a window's
target `=` made that window's id; status-left; status-right), as a held
binding (TM27). `run -C` (and `run-shell -C`) runs its string as tmux
commands after tmux expands it as a format, which the session menu's
labels need (`#{?...}`); puritty has tmux expand it (`display-message
-p`) and then runs it here, so the menu inside shows.

**Checked side by side** on 3.8 (`bench/tmux/compare`, `status-menus`):
the session menu's items as tmux's (Renumber, Rename, Detach, New
Session, New Window), the window menu's for the window pressed. App tests
141; `show.py` menus unchanged.

## TM59 · Two of TM39's smaller items (2026-11-12)

- **Errors as tmux words them.** A control client is sent a parse error
  as `parse error: unknown command: x` (`control.c:679`); a client's
  status line shows `Unknown command: x`, the message's first letter a
  capital (`cmd-queue.c:881`). puritty showed the control text; now it
  shows the client's (`asTmuxSays`). Checked side by side on 3.8
  (`messages2`).
- **A pane title's right part at the pane's edge.** `pane-border-format`'s
  `#[align=right]` part (by default 3.8's `[f][z][x]` buttons with the
  mouse on) ended two cells short: puritty gave the title the pane's
  width less 4, where `screen_redraw_make_pane_status` gives `sx - 2`
  (with a scrollbar's width) from two cells in. Checked side by side
  (`title-buttons`): `[x]` ends at columns 49 and 99 on both.

**Not done:** display-panes' digits one cell off in right-hand panes:
3.8 draws them in a mode of its own (`window-panes.c`) with scaled
geometry, not yet read. Done (TM65).

## TM60 · The tree's swap and help (2026-11-12)

The last of TM39's item 6. **S-Up** and **S-Down** swap the chosen
window with its neighbor in the same session (`swap-window -d`), only
when sorted by index, as `window_tree_swap` refuses otherwise (swapping
indexes would not move the rows); the lists are asked again and the
chosen row follows the window. **C-h** (3.7 on) shows the keys as
`mode_tree_help_start`, `window_tree_help_lines` and
`mode_tree_help_end` list them, in puritty's view of printed lines
(tmux draws them in a box over the tree).

**Checked side by side** on 3.8 (`bench/tmux/compare`, `tree-swap`):
after S-Down on `0: first`, `0: two-`, `1: first*`, `2: three` on both,
the current window at index 1 on both. App tests 141.

**Not done from TM39's item 6:** 3.8's `i` (information in place of the
preview) and `<`/`>` (scrolling the previews). Done (TM65).

## TM61 · How the Enter bug got through, and the same kind found (2026-11-12)

Gilbert, 2026-11-12: "do an analysis of why we had that tmux -CC ENTER
bug; i.e., how did we miss it? how did we get it wrong? was our
code-reading not careful enough? … if we determine why we got this one
wrong, we can check to see if we made similar mistakes in other parts of
the code."

### What went wrong

**The change (TM23, 2026-11-11).** To make tmux's bindings fire, puritty
began sending every named key with `send-keys -K`, "as if typed by the
client". What was checked: the prefix and bindings fire, typed text
arrives. What was assumed: that a key no binding takes then goes to the
program exactly as a typed one. That was argued from the manual and from
the code we were changing (`cmd-send-keys.c`, the key-table lookup in
`server_client_key_callback`), and the reading stopped there. The bytes
are made further on, in `input_key` (`input-keys.c`), where the key still
carries `KEYC_SENT`: it is never the plain-byte case, its table lookup
fails, and an escape-sequence key counts as internal and is dropped;
Enter falls to the extended-keys encoder and, in Ext 2, nothing is
written (TM50). The code-reading was careful about the part we touched
and not about the path to where it mattered: **the bytes the program
receives**.

**The evidence that was there.** `show.py mouse` ends by printing what
the left pane's `cat -v` got after pressing Up. Since TM23 the line has
ended without `^[OA` on every run: Up never arrived. The line is printed,
not compared with anything, and read as "the mouse report arrived".

**The chase.** Gilbert's report began with a paste, so the work went to
pastes: the diagnostic log (DG1–DG4), and a Linux reproduction with a
logging stand-in that did not reproduce. The stand-in turned on no
extended keys and tmux had `extended-keys` off; and it was never compared
with a normal client, the one thing that would have shown every arrow
missing.

**The kind of mistake.** puritty stands in for a tmux client by sending
commands it believes equivalent to what a client does. Drawing got a
side-by-side oracle against a plain client today (TM39); input had none,
so each equivalence rested on reading, and reading stopped short.

### The same kind, looked for and found

A byte-level oracle for input, `bench/tmux/compare/keydiff.py`: the same
keys and mouse events by xdotool to puritty running a **normal** tmux
client and to puritty in **-CC**, a logging program in the pane asking
for the same modes, on 3.6a and 3.8, `extended-keys` on and off. Its first
version passed with nothing logged on either side (the log was unlinked
under the logger); it now stops when a run logs nothing, and it was run
against a build with TM50's fix turned off to see it fail (18 of 31 keys
lost on 3.8 with no modes at all: arrows, Home, End, PgUp, PgDn, Insert,
Delete, F-keys, Shift+Tab, keypad Enter; Enter too in Ext 2). Found and
fixed with it:

1. **Keypad Enter** (all versions, modes): `\n`, or `\eOM` in keypad mode,
   where a normal client gives `\r`; puritty now sends it as Enter.
2. **Mouse drags** (1002, 1003): no motion with a button held reached the
   program (1002), or it came as button 35, none held (1003): the tmux
   path gave a motion no button, where puritty's own path gives the
   lowest held (`lowestHeld`).
3. **Hover motions** (1003): never reached a pane. Main dropped a motion
   with no button held unless *its own* terminal asked for every motion;
   under `-CC` that terminal is the control channel, which never asks.
   Now it asks tmux mode whether a pane does (`TmuxMode.anyMotion`).
4. **3.6: a pane's modes at attach.** puritty learned them from
   `pane_private_modes`, which is 3.8's; on 3.6 it is empty, so a program
   that had turned on the mouse, cursor keys or the keypad before the
   attach got no mouse reports and the wrong keys until it turned them on
   again. Now 3.6's older flags fill in (`mouse_standard_flag`,
   `_button_`, `_all_`, `_sgr_`, `_utf8_`, `keypad_cursor_flag`,
   `keypad_flag`); `mouse_any_flag`, which reads as 1003, is any mouse
   mode at all (measured).

After them: 31 keys in 4 modes and 6 mouse events in 4 modes, the same
bytes as a normal client's on 3.6a and 3.8. Gates: app 141, tmux package
71, `pointer` 54, `mouse` 200,000, `select` 4, `events` 13; `show.py`
mouse, select, lines, pointers, attach.

**Still unchecked in the same way:** bracketed paste on 3.6 (no flag says
a program asked for it, so it is known only once the program asks after
the attach); pastes themselves (puritty adds the brackets and sends
bytes; a client sends its terminal's paste through tmux); focus events
(puritty sends `\e[I`/`\e[O`; tmux sends them with `focus-events` on
and the program asking); the wheel on the alternate screen; IME commits.
Each wants a case in `keydiff.py`. (Done for all but IME commits in TM64.)

### What changes in how we work

1. **Every place puritty stands in for a tmux client gets a byte-level
   comparison with a normal client in puritty**, on the oldest and newest
   tmux we support, before it is called done. `keydiff.py` is the start.
2. **A printed result is not a check.** A line that prints state is
   either compared with an expected value or it is not evidence;
   `show.py`'s lines are to become assertions, beginning with the mouse
   scenario's.
3. **A check is run against the bug once**, so that a check that sees
   nothing cannot pass, as this one's first version did.
4. **Read to the boundary.** A claim of equivalence from a manual or from
   the code being changed is a hypothesis until the code to the output
   (here, `input_key`) is read or the bytes are measured.

## TM62 · customize-mode drawn by puritty (2026-11-13)

TM39's item 8, the last of it. `prefix C` (`customize-mode -Z`) is tmux's
editor for its options, hooks, environment and key bindings: a tree of
them, the chosen one's description below, and keys that set, reset and
unset. tmux draws it only on a terminal client, so under `-CC` puritty
only said so. Gilbert asked for it (2026-11-13), and for a way into it
from puritty's menu, since few know it is there.

**What no command reports.** A control client can ask for the values in
force (`show-options`, `list-keys`, `show-environment`), but not for each
option's description, type, choices, unit and default, nor for each key's
default binding, which the mode shows and uses (`The default is:`, Enter
cycling a choice, `d`, 3.8's `C`). puritty carries them:
`Tmux.CustomizeTables`, generated by
`packages/tmux/tools/customize_tables.py` from tmux's own
`options-table.c` (through the C preprocessor, for the hook macros) and a
fresh server of the same version (`-f /dev/null`, every option unset
globally so that the default is the table's, as
`options_default_to_string` gives it, not what the server set at start,
such as `default-shell`). Gilbert asked for it to be stored compactly
(2026-11-13): the newest version whole, each older one as the rows that
differ from it, matched by option name or by table and key. Measured:
3.8 whole is 79 KB of source, 3.6 as differences 25 KB (84 options whose
type, scope or wording changed, the defaults and keys that differ, and
238 rows 3.6 lacks); the two whole were 152 KB. A version with no table
takes the newest at or below it (3.7 takes 3.6's); a new tmux needs the
script run with its source and binary.

The tables read keys in one form. 3.7 and later answer `list-keys -F`;
3.6 has no `-F`, so its text (`bind-key [-r] -T TABLE KEY COMMAND`) and
its notes (`list-keys -N -a -P ''`, per table) are read, both by the
generator in Python and by puritty in Geng. A test holds the two to each
other: puritty's reading of a recorded 3.6a server's own answers
(`tests/src/CustomizeRaw36.geng`, made by the same script) is every row
of the table with nothing changed. It was run once with the parser's
backslash handling broken, and failed (16 keys: `\;`, `\"`, `\$` …).

**What tmux is asked** (`TmuxMode.customizeAsk`), on opening and after
every change: where the pane is; `show-options -H` at each of the six
levels (`-s`, `-g`, the session's, `-gw`, the window's, the pane's);
`show-environment` global and the session's, each with `-h` for hidden
variables; the keys. The commands a key sends go first and the answers
come back in order, so the tree is always tmux's state after the change.
A value shown is unquoted as tmux's parser reads it; a key's command is
shown with ` ; ` between commands, as the mode prints it
(`cmd_list_print` unescaped), where `list-keys` writes ` \; `, and that
form is what `bind-key` reads back as two commands.

**The tree** (`Tmux.Customize.entries`), as `window_customize_build`: Server
Options, Session Options, Window & Pane Options; on 3.8 Session Hooks,
Window & Pane Hooks, Global Environment, Session Environment; a Key Table
section per table not empty, by name. In each options section the user
options of every level first, then the global level's, each with its
value from the lowest level that sets it and that level's name in reverse
(`(session main)`); an array's items under it; a key's Command, Note and
Repeat under it. All folded at first. The rows drawn as `mode_tree_draw`
draws them (branches, `→` on 3.8 and `>` on 3.6, `+`/`-`, a level's two
spaces when a sibling has children), 3.8's colors measured from the
harness's RGB: the prefix and values light grey (gray70), `+` green, `-`
red, the box's edges in `tree-mode-border-style`; the chosen row all in
`tree-mode-selection-style` (3.6 `mode-style`) save the level's reverse.
The list is the pane less the description's twelve rows
(`window_customize_height`), and it scrolls as tmux's does, the top row
moved only as far as the chosen row needs (`mode_tree_check_selected`).

**The description** (`Customize.preview`), written as
`screen_write_text` writes (each line to the last space that fits, a
blank line between parts, stopping at the box's foot as tmux's does):
an option's description, its kind and scope, the value, what it expands
to (asked of tmux for a string holding `#`, with `%` doubled since
`display-message` would read the time), its choices, an EXAMPLE in its
color or style, its default when different, and the values above its
level; a hook's fire count (`show-hooks -F`, 3.8); a key's note, table,
repeat (3.8 `Repeat: on`, 3.6 `This key does repeat.`), command and
default; a variable's value and the global one.

**The keys** (`customizeKey`, `Customize.act`): the moves, PPage and
NPage by the list's height, the row keys, Left/Right/`+`/`-`, M-+ and
M--, `t T C-t`, `/ ? C-s` and `n N` (by name, through folded rows too,
opening their parents), `f` (the filter: each row's variables written
into the format and every row answered `1` or `0` by one
`display-message`; none kept shows every row and says
`(filter: no matches)`), `c`, `v`, `H`, `C` (3.8), C-h (the keys, in
puritty's view, as TM60's tree), q, Escape, C-g. Then the mode's:

- Enter and `s` set at the row's level, `w` at the window's, `S` and
  `W` globally (`window_customize_set_option`'s rules: a window-only
  option set at a pane goes to the window); a flag flips and a choice
  moves on at once, anything else is asked with tmux's label
  (`(pane-base-index, for window 2) `);
- `d`/`D` reset to tmux's default at the row's level and every level
  above that sets it; a key to its default binding, or unbound when tmux
  has none; `u`/`U` unset; each asks `y` first, at once with `-y`;
- a key's Command and Note set by `bind-key -T TABLE [-r] [-N NOTE] KEY
  COMMAND`, its repeat and note kept; Repeat flipped the same way;
- Enter on a section's title (3.8) adds a user option or hook
  (`@name value`), a variable (`NAME=value`, `-NAME` removed) or a key
  (`KEY COMMAND`), with tmux's words for a wrong answer; `a` (3.8)
  changes an array item's key.

On 3.8 the questions are asked in the pane's last row, over the box's
foot, the rest of the row left as it is (`mode_tree_draw_prompt`); on
3.6 at the status line. The binding is held like the tree's
(`Bindings.held`, `Syntax.customizeOf`: `-f`, `-Z`, `-N`, `-y`), and
`:customize-mode` at the prompt opens it too.

**From the menu.** puritty's pop-up menu has **Customize tmux…** after
New window while `-CC` is on (`Main.popupItems`); it opens the mode on
the active pane over every pane, as `prefix C`. Windows' system menu
keeps its own items, whose places are fixed when it is made.

**Checked side by side** (`bench/tmux/compare/scenes2.py`:
`customize-open`, `-set`, `-add`, `-filter`, `-key`), on 3.8 and (the
first, second and last) 3.6a, every shot's text the same as tmux's
client's: the folded sections, an opened section, a found option with
its description, a choice cycled at the session's level and reset, the
reset question, a new user option, `C` with only what changed, a filter,
a variable, a hook with its fires, a key's three rows and its repeat
flipped. The changes are compared, not printed: a new `out` step runs a
command on both servers and says `same` or `DIFFERS` (TM61's second
rule): `status-justify` after Enter (`centre`) and after `d y` (unset),
`@mine hello`, and the whole prefix table and its notes after the
rebinding, all `same`. Tests: tmux package 93 (22 for customize), app
141; `show.py prompts` as before.

**Not yet:**
- `e` (an option, a key's command or a variable in an editor): tmux opens
  the editor in a popup on the client, which a control client has not;
  puritty says so. On 3.8 a floating pane could host it.
- The mouse in the mode (a click chooses a row, a double click sets it,
  the right button its menu).
- 3.8's monitor hooks and user hooks (`@name` hooks): no command says
  which options they are; they show as options.
- A filter's variables only where it names them as `#{name}`
  (`#{=5:option_name}` and the like are left for tmux to expand, which it
  cannot for these).
- A general one this showed: tmux 3.8's theme colors (`themeyellow` and
  the rest) are drawn here as tmux sends them (RGB, the dark theme's), but
  the rest of puritty's 3.8 drawing, prompts included, still takes them
  as the plain colors (`themeyellow` as yellow, TM47). Done (TM65).

## TM63 · show.py's lines are checks (2026-11-13)

TM61's second rule, done for `bench/tmux/show.py`: every result a
scenario reads back from tmux, which it printed for a reader to judge, is
now a check against what it should be (`check(label, got, want)`, `want` a
value or `that(description, test)`); each says `ok` or `FAIL`, the run
ends with `N checks, M failed` and status 1 on any failure. What is shown
only for the reader and claims nothing is a `note`. `build` and `attach`,
which only took pictures, check what they do (typed text in the pane, `jjjj`
in `less` after an attach).

Each want was taken from what the documents say should happen, not from
what the scenario printed, and the first run against them failed six:

- `modes`' `C-a s 1` and `C-a s M-c` chose `other` and `k10`, where the
  scenario's comment said `k01` and `main`. The comment predates TM46,
  which lists sessions in the order made (main, other, k00 …), as tmux
  does; the printed line had changed meaning since and nobody saw it.
  puritty is right; the want and the comment are fixed.
- `copy`'s buffer is from the end of one line to the first character of
  the line two below (`6\nline 57\nl`), which is what Space at column 0
  then `k k $` selects; the want expected three whole lines.
- `mouse`'s floating pane made by `new-pane -x 30 -y 6` is 28x4: the size
  is the box's. The program's line begins with the shell's `$ `.

After them: 138 checks in 17 scenarios, none failed. A failing check was
seen to end the run with status 1.

## TM64 · Pastes, focus and the wheel, byte for byte (2026-11-13)

TM61's unchecked list, taken up. `keydiff.py input` sends, to puritty
running a normal tmux client and to puritty in `-CC`: the clipboard by
Ctrl+Shift+V (one line, two lines, and a line of `" $ \ #{} ~`, Korean
and a tab), the selection by Shift+Insert and by the middle button,
focus leaving puritty's window and coming back, and the wheel; the
program asking for nothing, bracketed paste (2004), focus events (1004)
or the alternate screen, each set before puritty attaches; tmux's
`focus-events` on, its `mouse` off and on; 3.8 and 3.6a. `KD_ALL=1`
prints every event, not only those that differ, which is how the focus
events were seen to reach the program at all.

**Found: a pasted line end.** A paste of two lines gave the program
`line1\nline2` under a normal client and `line1\rline2` under `-CC`, on
both versions. A tmux client turns bracketed paste on in its terminal at
start (`tty_start_tty`, whatever the pane asks), so puritty encodes the
paste as a bracketed one (line ends kept), and tmux writes what came to
the pane as it is (`window_pane_paste`), leaving out the brackets the
program did not ask for. Under `-CC` puritty encoded it by the pane's own
mode, plain, which turns `\n` into `\r`, as xterm does.

**Found: 3.6, bracketed paste asked before the attach.** TM61's known gap,
measured: no brackets under `-CC` where a normal client had them.

**The fix, one for both:** under `-CC` a paste is given to tmux to make
(`TmuxMode.paste`, `Command.pasteBytes`): encoded as a bracketed paste,
put in a buffer of puritty's (`set-buffer`, a double-quoted word in which
every byte outside printable ASCII is an octal escape, so that it stays
on the command's one line; 1024 bytes a command, `-a` after the first),
then `paste-buffer -p -r -d` into the active pane: tmux brackets it where
the program asked, which tmux knows on every version, keeps the line ends
(`-r`) and drops the buffer. `PasteStart` and `PasteEnd` are no help:
`send-keys` types them as words on both versions (measured). The
diagnostic log shows a `set-buffer`'s text only as its length (DG5's
rule; a test holds it).

After it: every paste the same as a normal client's on 3.6a and 3.8, in
every mode, `mouse` on and off, the odd line included; focus events the
same on 3.8. `keydiff.py keys` and `mouse` on 3.8 still differ in
nothing. Tests: tmux package 96, app 142.

**Differences left, measured and kept:**
- the wheel and the middle button over a pane are puritty's
  (TM39.3, TM17);
- **3.6: focus events for a program that asked before the attach.** A
  control client is always focused to tmux (`CLIENT_FOCUSED`), so puritty
  sends `\e[I` and `\e[O` itself, only where it knows the program asked.
  3.6 has no flag that says so, and no command passes focus to tmux. Such
  a program gets its focus events once it asks again.

**Still unchecked:** IME commits (`keydiff` types Korean by keysym, not
through an input method); `harness/ime` could drive one.

## TM65 · tmux 3.8's theme colors everywhere, and three of TM39's leftovers (2026-11-13)

Gilbert's list after TM64: tmux 3.8's theme colors in all of puritty's
3.8 drawing, not customize mode's alone (TM62's last "not yet"); then
display-panes' digits a cell off in right-hand panes on 3.8 (TM59), tmux's
message log full of puritty's own commands (TM39 item 15), and the tree's
`i` and `<`/`>` (TM60).

**Dnene52: puritty's own commands are left out of tmux's message log as
puritty shows it.** tmux cannot be told not to log a client's commands,
and sending fewer would not remove the keys passed on, which are most of
them; so puritty filters the output it draws, and only lines its own
client wrote as `command:`, keeping the user's commands. The log in tmux
is unchanged: `show-messages` from another client still shows all of
them.

**Theme colors.** tmux 3.8 writes its default styles with theme names
(`message-style bg=themeyellow,fg=themeblack`, `status-style
bg=themegreen`, `menu-style bg=themedarkgrey,fg=themewhite`). Each name is
looked up per client (`server_client_update_theme_colours`): the `theme`
option picks the theme (`detect` from the terminal's reported theme or its
background, `light`, `dark`, or `terminal`, the plain ANSI colors), and
the name's option for that theme (`dark-theme-yellow`) is expanded for
the client, a format that gives `darkgoldenrod` to a client of 256 colors
or more and `yellow` to one of fewer. A control client has no terminal, so
`#{client_colours}` is empty for it: expanding `#{E:message-style}` there
gives the plain colors, which is what puritty drew (`themeyellow` as
yellow, TM47), where a terminal client in puritty is drawn dark gold.

What puritty does (`TmuxMode.themeOf`, `withStatus`, `themeAsked`):

- one more subscription, `puritty-theme`: `#{theme}` and the twenty
  `dark-theme-*` and `light-theme-*` options as they are set, so a
  change is seen when made; 3.6 sends nothing and nothing is asked;
- on each change, one `display-message -p` of the twenty with
  `#{client_colours}` written as `16777216`, as for a client of 24-bit
  color, which puritty is; a value tmux would not take as a color, or
  another theme name, is `default`, as tmux makes it;
- `theme detect` follows puritty's own background (`setBackground`, from
  the config, again on a settings reload): light when its red, green and
  blue add to more than 382, as `colour_totheme` reads a terminal's;
- the status line is kept as tmux sent it (`rawStatus`), and drawn
  (`status`) with every theme name in it written as its color
  (`Style.themed`): its formats, the windows' and panes' styles and
  titles, and the drawing options (TM47). Customize mode's colors (TM62)
  come from the same table, no longer from fixed dark-theme values.

`Tmux.Style` also reads the X11 color names tmux knows (`colour_byname`:
578 names, `gray0` to `gray100` rounded as tmux rounds them), generated
into `Tmux.ColorNames` by `packages/tmux/tools/color_names.py` from
tmux's `colour.c` (the same table in 3.6a and 3.8). Before it,
`fg=darkgoldenrod` in a user's style drew in the terminal's own color.

Three more options are read (`optionNames`): `menu-style` and
`menu-border-style` for menus (puritty had fixed colors close to 3.8's
defaults, so 3.6's menus were grey where 3.6 draws them in the terminal's
colors), and `tree-mode-border-style` for the tree's box. The tree's
preview labels take `tree-mode-preview-style`, expanded by tmux for each
window or pane in the preview's list (`#{E:…}`), so the active one is red
and the others blue on 3.8; before 3.8, display-panes' colors, as 3.6's
`window_tree_draw_session` draws them.

**Checked side by side** (`bench/tmux/compare`, the survey's 46 scenes on
3.8, the cells' backgrounds compared where tmux's are RGB or 256
colors): the prompt and messages darkgoldenrod (184,134,11), the status
line yellowgreen, the clock skyblue3, display-panes skyblue3 and
indianred, the menus and the tree box's edges gray15 (38,38,38), as
tmux's client. On 3.6a the prompt is still palette yellow (3.6a sends
`43`), display-panes as before, and the menus in the terminal's own
colors, as 3.6a's.

**display-panes on 3.8.** 3.8 draws the numbers in a mode of its own
(`window-panes.c`), which centers them as `(width − (6·digits − 1)) / 2`
and `(height − 5) / 2`, where 3.6's `cmd-display-panes.c` takes
`width/2 − 3·digits` and `height/2 − 2`: a cell apart on odd widths (a
right-hand pane of 49) and on even heights. puritty now places them by the
version, takes 3.8's larger threshold for the big digits (seven rows, as
`display-panes-format` takes one), and draws the letter that chooses panes
10 to 34 under the digits, as both versions do. Checked on 3.8 and 3.6a
(`display-panes`): the digits in the same cells as tmux's in all three
panes.

**tmux's message log.** tmux logs every command a client sends
(`cmdq_add_message`, once its config is read), with no flag to leave a
client out, and puritty sends many of its own: the keys it passes on
(`send-keys -K`), its questions, captures and subscriptions. A terminal
client sends none of them. puritty now leaves them out of `show-messages`'
output (`ownCommandsOut`, Dnene52): it learns its client name on attach
(`#{client_name}`), remembers the last 50 commands it ran for the user
(those sent as `ForRan`: a prompt's command, a menu item's, a binding's
line), and drops a line `TIME: NAME command: COMMAND` of its own unless
the command is one of those (compared without quotes and spacing, as tmux
prints a command its own way). Its key lines (`NAME key ~:
show-messages`) stay, as a terminal client's do. Checked (`messages`):
the log is the harness's commands, puritty's keys and the user's
`display-message "hello from tmux"`, where it was two screens of
puritty's.

**The tree's `<`, `>` and `i`.** `<` and `>` move the preview along a
session's windows when they do not all fit, as `window_tree_draw_session`
picks them (`sessionSpan`): all when each has 24 cells, else as many as
have, the current window among them, moved by the offset no further than
the first and last window; `<` and `>` drawn at the sides with a line
inside them. The offset goes back to 0 on another row, as tmux's. A
window's preview stays puritty's (its panes where they are, TM35), so
there they do nothing. `i` (3.8) shows the row's information in the
preview's place, `window_tree_draw_info`'s lines (a pane's, its window's,
its session's, as many as the row has), asked of tmux in one
`display-message -t ROW` and drawn with their styles, a line across
between the groups with `┼` where the labels' line meets it, and `(view:
info)` in the box's title. `C-h` lists `<`, `>` and (3.8) `i`. Checked side
by side (`scenes2.py`: `tree-info`, `tree-scroll`, 3.8): the session's,
window's and pane's information line for line as tmux's; with seven
windows, `>` shows windows 1 to 4 on both, four more `>` stop at 3 to 6,
`<` gives 2 to 5, the arrows in the same cells.

Tests: tmux package 99 (Style: X11 names and grey levels, theme names,
what is a color), app 142. `show.py`'s 17 scenarios: 138 checks, none
failed.

**Not yet:** (popup colors, display-panes' borders and the tree's
questions done in TM66)
- The message log has no `message:` lines for what tmux showed puritty
  (a control client is sent `%message`, which tmux does not log as a
  terminal client's status message), and a prompt's command reads
  `command:` where a terminal client's reads `key ::`. Kept: TM66.
- `<` and `>` on a window's preview: puritty draws a window's panes by
  its layout, all of them, where tmux puts them side by side and scrolls
  them as a session's windows.

## TM66 · The rest of TM65's list: questions in the mode, the tree's colors, popups, display-panes (2026-11-13)

**A mode's questions on 3.8.** Every question a mode tree asks on 3.8
(`mode_tree_set_prompt`: the tree's search, filter, kill, kill-tagged and
`:`, choose-buffer's and choose-client's search and filter, customize's)
is asked on the mode's own last row, or its first with `status-position
top`, the rest of the row left as it is (3.8's `message-style` fills only
where the prompt is not `IS_MODE`). Before 3.8 they stay at the status
line. The row is the mode's place (`modePlace`: the window less the
status line when zoomed, as `choose-tree -Zs` and `customize-mode -Z`
open, else its pane), so customize-mode, which asked on the active pane's
last row, now asks at the zoomed mode's foot. Checked side by side
(`choose-tree-s`: the kill and filter questions on the tree's last row,
no cell differing; on 3.6a still at the status line; `customize-set`,
`-add`, `-filter`: one cell each, the cursor).

**The tree's rows in 3.8's colors** (`MODE_TREE_PREFIX_FORMAT` and
`WINDOW_TREE_DEFAULT_FORMAT`): the key and branches light grey, `-` red
and `+` green, a window's flags and a session's `N windows` light grey, a
marked window or pane magenta, a floating pane underlined, a tagged row
cyan. puritty asks tmux for 3.8's formats with their style marks
(`treeQueries`) and draws the runs; puritty's look strips them. The
chosen row is all mode-style across the pane. Checked: every glyph with
an RGB color in the tree's first six rows the same color as tmux's, in
three scenes.

**What `capture-pane` cannot show.** The side-by-side harness reads the
inner client through the outer tmux's `capture-pane -p -e`, which leaves
out a line's cleared end, background and all (measured: `\e[43mab\e[K`
captures as `ab`, with or without `-N`). A highlight to the pane's edge
looks like one that stops at the text. puritty's own screenshot of a
plain tmux 3.8 client inside it shows the chosen row highlighted across
the pane, which is what puritty draws. The harness is right about every
cell with text in it.

**Popups in tmux's colors.** puritty's popup is a modal floating pane
(TM56). On the same command line as its `new-pane`, the new pane is given
`popup-style` as its `window-style` and `window-active-style`, and
`popup-border-style` as its border styles (`set -pF … '#{popup-style}'`),
so tmux holds the colors as pane options. puritty reads each pane's own
`window-style` (`puritty-pwstyle`, as tmux looks a pane option up from the
pane first) and, in tmux's look, draws a floating pane's frame in the
pane's own border style, as 3.8 does (puritty's look keeps amber and
grey). Checked (`popup`): the inside gray15 and the frame light grey on
gray15, as tmux's; 65 cells differ, the box's place a row and a column
apart (TM56) and the title not shown.

**display-panes' borders on 3.8.** While the numbers show, 3.8's mode
draws every border, and the floating frames, in
`display-panes-border-style` (gray15 under light grey), with no pane
titles; puritty does the same. Checked (`display-panes`, `borders-3`): no
cell differs.

**Kept: the message log's `message:` lines.** tmux does not log what it
tells a control client, and the log's times are minutes, so puritty
cannot put its own messages among tmux's lines in the order they came;
it adds none rather than guess.

Tests: app 142, tmux package 99; `show.py` modes, prompts, views, mouse,
menus, panes, marks, status, copy, pointers as before.

**Not yet:** a popup's `-T` title and `-B`; its box drawn where tmux's is
(TM56).

## TM67 · Copy mode's view kept while a key waits for tmux's answer (2026-11-13)

Gilbert, in `-CC` with a long `find` in a pane: `prefix [`, then `k`
held, and once the view scrolled past the screen it alternated between
the scrolled lines and the pane's live screen, "the ghost of the old info
flashing behind the scrolling contents".

**Why.** Every key puritty sends to the active pane brought that pane's
view back to the bottom, as a key typed into a program should
(`keys` and the binding path in `TmuxMode`). A key in copy mode is the
mode's, not the program's; the view is moved by tmux's answer to the copy
question (TM31), which comes a round trip after the key. So each `k`
drew the live screen for that round trip, and a held key alternated the
two.

**Now** a pane in copy mode keeps its view when a key is sent; tmux's
answer moves it, and leaving copy mode gives the pane its own view back
as before (`%pane-mode-changed`, TM31).

**Checked:** `show.py` copy (12 checks), modes and prompts (22 each), app
tests 142. The flash lasts one round trip, too short for a picture taken
by the harness to catch reliably, so it is not checked by a test yet: a
test of `TmuxMode`'s state for it is TM68's.

## TM68 · TmuxMode tested against a fake tmux (2026-11-13)

TM67's flash lasted one round trip, which no picture the harness takes
catches reliably, and `show.py` and `bench/tmux/compare` see only what
reaches a screen. Gilbert asked for tests of `TmuxMode`'s own state.

**Why it can be tested without tmux.** `TmuxMode` is pure: tmux's bytes go
in through `read`, keys through `typed`, `keys` and `paste`, and out come
its state and the command lines it would send. Its only tie to a platform
is two types of `Window`'s (the pointer's shapes and a pointer event), so
`app/tests/stub/Window.geng` declares just those, and the app's tests on
node compile `TmuxMode` as it is, with the tmux package as a dependency.

**`app/tests/src/FakeTmux.geng`**, a tmux server as control mode sees it:
one session (`$0`), one window (`@0`), its panes (`%0`), each with its lines
and, in copy mode, its scroll, cursor and the column the cursor keeps to.
It answers each command of a line puritty sends with a `%begin`/`%end`
block (parsing the line with the tmux package's own `Syntax.tokens`),
expands the `#{…}` formats from the model (`#{?…}` and `#{T:…}`-style
modifiers too), and acts on what changes it: `send-keys` in copy mode (by
`-X` command, by key name, and `-K -H 6b`, the hex form puritty sends a
letter in), `copy-mode`, `refresh-client -B` subscriptions (told at once).
A command it does not know is answered with nothing and listed in
`unknown`.

**`app/tests/src/TmuxTests.geng`**, the driver and the tests. A run holds
puritty's state, the fake, the command lines puritty sent that tmux has
not answered yet, and a clock; `deliver` feeds tmux's bytes to `read`,
`settle` answers what is held until puritty asks nothing more,
`typeKey` types a key, and `look` paints and reads puritty's screen as rows
of text. Holding the replies back is what lets a test see the moment
between a key and tmux's answer.

**Keeping the fake honest.** `app/tests/record-tmux.py` starts a real tmux
(3.8 by default) with the tests' pane (200 lines, no last newline), asks
puritty's questions (`windowQuery`, `tabsQuery`, `panesQuery`, the pane's
info, `modeFormat`, `copyFormat`) attached, in copy mode, and after 30 and
31 `cursor-up`s, and writes the answers into `app/tests/src/RealTmux.geng`.
A test asks the fake the same questions in the same states and requires
the same lines. Its first run found the fake wrong three times, and the
fake was fixed to match: tmux numbers a new server's ids from 0 (`$0`,
`@0`, `%0`); 3.8 gives the layout in its JSON form; copy mode's variables
are empty outside it (`C %0  176   `, not zeros); and the copy cursor keeps
its column until it moves, then is held to the line's last character in vi
mode (entering at column 8, past the end of `line 200`, it shows 8; one
line up, 7). Writing the fake also found it, not puritty, wrong once:
`#{pane_mode}` is `copy-mode` with vi keys too; `copy-mode-vi` is only the
key table.

**3.6a too.** The fake is made as one version (`FakeTmux.world`'s
`version`, `"3.8"` or `"3.6a"`, which `#{version}` gives), and
`record-tmux.py` records both tmuxes into `RealTmux.geng`, each answer
marked with its version (48 answers). Recorded, 3.6a differs from 3.8 in
two of puritty's questions and nowhere else: the layout is the old form,
`b25d,80x24,0,0,0`, its checksum tmux's `layout_checksum` (a 16-bit sum
rotated right by one before each character), which the fake computes; and
copy mode's cursor keeps its column when it moves (8 after 30 and 31
`cursor-up`s, where 3.8 holds it to 7). Forcing 3.8's hold onto 3.6a makes
the comparison fail on those two answers.

**The tests** (suite `TmuxMode`, 7):
- the fake answers as the recorded tmux 3.8 and 3.6a do, in all four
  states (48 answers);
- then on each version's fake:
  - attaching asks for nothing the fake does not know, and draws lines
    177 to 200;
  - 30 `k`s in copy mode scroll tmux to 7 and puritty shows `line 170` at
    the top with `[7/176]` at its right;
  - one more `k`, tmux's answer held: puritty still shows `line 170`; let
    through: `line 169`, `[8/176]`. **With TM67's fix taken out this test
    fails on both versions**: held, it shows `line 177`, the live screen
    behind `[7/176]`, the ghost Gilbert saw.

App tests 149, in under a second with the rest.

**Natively too** (`vt-core.md` §VC61): the same tests run as a native
program compiled against the real X11 `Window`, and as a Windows program
against win32's, all seven passing on each.

**Not yet:** one pane only; the
tree, prompts and menus came in TM69; customize-mode, the message log and
the status line are TmuxMode's that the fake does not yet answer for. Each new test widens
the fake and adds its questions to `record-tmux.py`.


## TM69 · The fake tmux widened: the tree, the prompt and the menus (2026-11-13)

TM68's fake answered what attaching and copy mode ask, and its key table
was six lines written by hand. This week's fixes were mostly in the tree,
the prompts and the menus, which no test reached.

**The recording is made as puritty asks.** `record-tmux.py` asks every
question through a control client (`tmux -C attach`), as puritty's own
client asks, with the flags puritty's sends when it attaches (`refresh-client
-f new-layouts,pause-after=5`). Asked through a separate `tmux` command
instead, as TM68's recording was, 3.8 gave `window_visible_layout` in its
JSON form; through a control client without those flags it gives the old
form, and with them the JSON form again, so the flags are part of what is
recorded. It records `list-keys` and `list-commands`' table whole (308 and
92 lines on 3.8, 267 and 90 on 3.6a), and writes what changes from run to
run as the fake gives it: the host's name `host`, the client's
`client-0`, the activity and creation times 1700000000, and those times
shown by `t/p:` `12:00`.

**The fake's bindings are tmux's.** `list-keys` is answered with the
version's recorded defaults, so `C-b s`, `C-b :` and `C-b <` reach puritty
as tmux binds them, and a binding tmux changes between versions changes in
the tests too (3.8's pane menu has Float, 3.6a's has Swap Up and Down).

**Every question a scenario asks is recorded.** The fake keeps every command
line as it was sent (`heard`). `TmuxTests.scenarios` names ten: attached,
copy mode, the tree of sessions and of windows, the tree closed, the
command prompt and one run, the window menu and its Rename, the pane menu.
A test runs each on each version and lists every line that only asks
(`display-message`, `list-*`, `capture-pane`) and is not in `RealTmux`,
ready to be added to `app/tests/tmux-questions.txt`, which `record-tmux.py`
puts to the real tmuxes. 61 lines there today, 85 answers a version in
all, and TM68's test holds the fake to every one.

**What holding it found in the fake**, each fixed:
- the variables the tree reads (`session_attached`, `session_windows`, the
  activity times, `pane_left`, `pane_flags`, which 3.6a does not have) and
  `pane_private_modes` (`7,25` on 3.8, unknown on 3.6a);
- the format language tmux's bindings use: `#{?#{…},a,b}` whose condition
  is a format, `!:`, `&&:`, `||:`, `==:`, `!=:`, `<:`, `>:`, `m/r:` (for
  the one-group patterns the bindings have), `=N:` and `=/N/end:`, `q:`,
  `t/p:`, `#{#{x}}`, the one-letter aliases (`#W`), user options (`@name`,
  which `set-option` keeps);
- `display-message` writes `%%` as `%` (`100%%` is `100%`);
- `capture-pane` without `-S` gives the screen, not the history too, and
  `-a` on a pane with no alternate screen gives one empty line;
- the selection's variables are empty while nothing is selected, not `0`;
- and the test read a reply without its empty lines, which tmux sends.

**The tests** (suite `TmuxMode`, 18: 2 over both versions, 8 on each):
the tree of sessions shows `main: 1 windows (attached)` and `q` closes it;
the tree of windows opens the session and shows `0: sh*`; the command
prompt opens (puritty's dialog, `promptBox`), shows what is typed and
sends it to tmux on Enter; the window menu shows tmux's nine items, and
its Rename opens a prompt holding the window's name (`#W` expanded by
tmux); the pane menu shows each version's items. App tests 160 on node,
natively and on Windows (`vt-core.md` §VC62's gate holds 160).

**Not yet:** more than one pane or window, customize mode, choose-buffer
and choose-client, the clock, display-panes, and the message log.


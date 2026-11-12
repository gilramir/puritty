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
now: the box moved, the box resized, the line right, the line below.

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
- `-i` (incremental search, copy mode's emacs table) answers once, on
  Enter, rather than on each key.
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

**Not yet:** search matches are not marked (tmux highlights them); a line
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
close it. Drawn in tmux's look as tmux lists it, `(0)` keys, `+`/`-`, the
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

**Not yet:** the tree's preview, tags (`t`), kill (`x`), sorting (`O`),
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


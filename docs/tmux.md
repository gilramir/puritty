# tmux and puritty: a survey of tmux 3.8 (2026-11-11)

Gilbert, 2026-11-11: analyse the latest tmux and survey what puritty's
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
| that, plus `OSC 10/11` colours and `CSI ? 997 ; 1 n` to 996 | 16 ms | 16 ms | dark |

The cause is in `tty_keys_next` (`tty-keys.c:1002-1009`): while any query
is unanswered, tmux waits 500 ms before taking an Esc as Esc, and a 5 s
timer gives up on them (`tty.c:312-323`). tmux asks for the colours again
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
| `OSC 10;?`, `OSC 11;?` | the background, to guess light or dark; and the Esc wait (TM3) | answered only after a program set the colour (`vt/src/Vt/Osc.geng`, `dynamicColours`) | **answer from the configured look** |
| `CSI ? 996 n`, `CSI ? 2031 h` | the theme now, and on each change | 2031 recorded; 996 not answered, 997 never sent | **answer 996, and send `CSI ? 997 ; 1/2 n` under 2031 when the look changes** |
| `CSI 18 t`, `CSI 14 t` | cell size in pixels, for sixel | answered | none |
| `OSC 4;N;?` | a pane's palette question | answered | none |
| `OSC 52;;?` | `get-clipboard request` only | asked of the user, default deny | by design |

### TM4.2 · Features

tmux turns a feature on from its table of known terminals, the
`terminal-features` option (default `xterm*:clipboard:ccolour:cstyle:focus:title`),
terminfo, `COLORTERM`, and the replies above (`tty-features.c:509-529`,
`tty-term.c:618-683`). With `xterm-256color` and puritty's replies,
`client_termfeatures` was measured as
`bpaste,ccolour,clipboard,cstyle,focus,sync,title` (with 256 and RGB from
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
  what it sees in `%output`. Colours for a pane come from
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
   `refresh-client -r` (colours) and its theme by the client's 997 (TM4).
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
  (ecc43170); a control client's colours start unknown rather than black,
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
  keeps its tabs greyed, reconnects, and `attach -t` brings the panes back
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

`cjk-and-thai.md` §10.4's open questions are answered here, but one: what
the colleagues run inside the pane.

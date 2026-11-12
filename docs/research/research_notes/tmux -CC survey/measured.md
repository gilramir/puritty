# puritty -CC against plain tmux, measured (2026-11-12)

## How it was measured

- **Plain tmux:** server `-L ccs-plain`, a normal client attached inside
  an outer tmux (`-L ccs-outer`, status off, no prefix) at 100x30;
  `capture-pane -p -e` of the outer pane gives the cells the client shows
  (`*.tmux.txt`, `*.tmux.ans`).
- **puritty:** `app/puritty` (built 15:15, before 1fa50f1, which only adds
  pointer shapes) on Xvfb :93, `[window] 100x30`, `[tmux] look = "tmux"`,
  running `tmux -L ccs-cc -CC attach -t main`; its PURITTY_SHOT frame saved
  as `*.puritty.png`.
- Both servers are built by the same commands from `-f` a conf that is
  tmux's defaults plus `default-shell /bin/sh` and the scene's lines;
  session made `-x 100 -y 29`. Both ended up with window 100x29 (checked
  every scene) except where noted. Keys go to the outer pane by
  `send-keys` and to puritty by xdotool; mouse to the plain client as raw
  SGR reports (`send-keys -H`). After each shot both servers are asked
  `#{pane_mode}` etc.; they agreed on mode, zoom and window unless noted.
- `*.pair.png`: the tmux capture rendered on puritty's 9x17 grid (top)
  over puritty's frame (bottom). The renderer (`pair.py`) ignores bold.
- tmux 3.8 for everything (`out-3.8/`); 15 scenes again on 3.6a
  (`out-3.6a/`), see the last section.
- Wrapped in `systemd-run --user --scope -p MemoryMax=4G`; private `-L`
  sockets, only those killed.

**Noise that is not a puritty difference:** pane text order differs
between the two servers (`echo left` typed before or after the prompt
drew) because the panes are filled before their shells start; colors of
named colors differ because puritty draws its palette (the same thing it
would do for a plain tmux inside it), theme colors (3.8) are RGB in the
capture. In tmux 3.6a and 3.8 **Escape does not cancel the emacs
command prompt** (measured: `C-b :` then Escape, or raw `1b`, leaves `:`
up; C-c cancels), so first-round steps that used Escape to close a prompt
drifted on the tmux side; the second round uses C-c.

## Status line

### status-flags (`*`, `-`, `Z`, `!`, `#`, `M`)
- tmux: `[main] 0:first#- 1:zoomed#Z 2:belly#! 3:busy# 4:marked#M 5:cur*`,
  flagged windows reversed, current underscored, `"nene" 17:40 12-Nov-26`.
- puritty: identical text, styles and placement. **No difference.**
  (Activity flagged every window on both sides: shells' first prompts.)

### status-overflow (12 windows with long names)
- tmux: scrolls the list to keep the current window visible and marks the
  cut: `[main] <ong-window-name-5  6:a-rather-long-window-name-6* 7:a-rather-long-win>"nene" 17:41 12-Nov-26`;
  with window 11 current: `[main] <e-9  10:… 11:a-rather-long-window-name-11*"nene" …`.
- puritty: always from window 0, `[main] 0:first  1:a-rather-long-window-name-1  2:… 3:a-rather-long-windo`.
  **The current window is not shown at all, no `<`/`>` markers, and
  status-right is lost** (the list runs to the edge over it).

### status-custom (status-style, styled status-left/right, current style, `status-justify centre`)
- Styles: match (red `[main]`, blue bar, yellow current, green `R`).
- **`status-justify centre` ignored**: tmux centres `0:first- 1:two*`,
  puritty puts it after status-left. (Known: TM29 Not yet.)

### status-top-2lines (`status-position top`, `status 2`)
- tmux: status on row 0 plus a second line (`P: 0:[nene]*`), window 100x28.
- puritty: bar stays at the bottom, one line, window 100x29. (Known: TM29.)

### status-off
- tmux: no status, window 100x30. puritty: bar still drawn, window 100x29.
  (Known: TM29.)

## Pane borders

### borders-2
- tmux 3.8 with two panes colors **half** of the dividing line in the
  active color (rows 15–28 green, 0–14 gray: the half nearest the active
  pane, tmux's two-pane split indicator).
- puritty: whole line green.

### borders-3 (left | top-right / bottom-right, bottom-right active)
- tmux: only the segments bordering the active pane are green (the
  vertical from row 14 down and the horizontal above it); the vertical next
  to top-right is gray; junction `├` at col 50.
- puritty: **the whole vertical line green**, also beside the inactive
  top-right pane; horizontal starts a cell right, no junction glyph.

### borders-4 (2x2)
- Active-edge coloring right (only top-left's edges green).
- **The centre crossing `┼` is missing**: a dark gap at col 50 row 14.
  Same gap at every junction in the other scenes (`├`, `┬`, `┴`).

### border-status-top (`pane-border-format ' #{pane_index}: #{pane_current_command} '`)
- Titles, placement, active title color: match. Junction gaps as above,
  vertical beside top-right green as in borders-3.

### border-status-bottom (default format, 3.8's `[f][z][x]`)
- tmux: right part flush at the right edge (`…────[f][z][x]`).
- puritty: **the `[f][z][x]` part ends two cells early** (`[f][z][x]──`),
  on every title. Pane 1's title is on the line between panes in both.

### border-indicators arrows / both
- tmux: `↓` on the horizontal border and `→` on the vertical at the active
  pane (both: arrows plus the colors).
- puritty: **no arrows**; colors as in borders-3.

### border-lines double / heavy / simple / number / spaces
- tmux: `║ ╠═`, `┃ ┣━`, `| +-`, the pane's index repeated (`0000`,
  `2222`), blanks.
- puritty: **always the thin single line**; `pane-border-lines` is not
  read (cropped strip: `out-3.8/lines-crops.png`).

### border-styles (`pane-border-style fg=red`, `pane-active-border-style fg=cyan,bg=blue`)
- Inactive red: match. Active: tmux cyan line on blue cells; puritty blue
  cells with **no visible line in them** (fg lost when bg set).

### window-styles (`window-style bg=colour236`, `window-active-style bg=colour17`)
- tmux: inactive panes gray background, active pane navy.
- puritty: **ignored**, every pane default background.

### marked pane (`select-pane -m` on the left pane)
- tmux: the marked pane's border cells drawn **reversed** (a solid block,
  gray/green halves).
- puritty: a thin magenta line. Status `0:first*M`: match.

### zoomed
- Match (`0:first*Z`, one pane full size).

### pane-scrollbars on (3.6+)
- tmux: a scrollbar column on every pane (track `bg=#262626`, thumb
  `#b3b3b3`; the left pane's thumb at its bottom after `seq 1 100`).
- puritty: **no scrollbars**; the pane content is the same width.
- In copy mode both turn the active pane's border amber: match.

### remain-on-exit (dead pane)
- Both show `Pane is dead (status 3, <date>)` on the pane's last row.
  Match (puritty also keeps the pane's `bye`, which the plain client did
  not show).

### synchronize-panes
- Both draw every border red and both panes got the typed line. Match.

### floating pane (3.8 `new-pane -x 40 -y 8`)
- Placement and content match; frame green in tmux, amber in puritty.

## Tree and choosers

### choose-tree `prefix s` / `prefix w`
- List text: match for sessions (`(0) + main: 2 windows (attached)`).
- Window rows: tmux `├─→ + 0: first-` (3.8 uses `→`; 3.6a `->`) with a
  `+` because the window can open to its panes; puritty
  `├─> 0: first (3 panes)` — **arrow glyph differs on 3.8, no `+`, extra
  `(3 panes)`, and no panes level**: Right on a window row opens
  `├─→ 0: sh / 1: sh- / 2: sh*` in tmux and does nothing in puritty.
- Selected row: tmux highlights the text only; puritty the whole row.
  The `+`/`-` are green in tmux, plain in puritty.
- **Preview layout:** tmux gives the list about half the height (14 rows)
  and frames the preview in a box titled `┌ main (sort: index) (view: preview) ─┐`;
  windows (or a window's panes) side by side, each with its top lines and
  cursor, and a small boxed label `0:first` / `1:second` (3.6a: just the
  index) in the middle, current one red, others blue. puritty: list a
  third of the height, a plain rule, labels on a top line, the **last**
  lines of each capture, a window's panes in their layout, **no sort/view
  title**.
- **Keys not handled by puritty:** `v` (tmux hides the preview), `t` (tag:
  `1*: second*`), `x` (tmux asks `Kill session other?` on the tree's last
  row), `f` (tmux asks `(filter)`; after a filter the title says
  `(filter: active)` and the list shrinks), `O` (sort). In puritty `t`,
  `x`, `f`, `v` do nothing, and the filter text typed after `f` is
  ignored, so the **Enter meant for the filter chose the row and switched
  session** (`[other] 0:sh*`), and a later `O` was typed into the shell.

### choose-buffer `prefix =`, choose-client `prefix D`, customize-mode `prefix C`
- tmux: lists (`(0) buffer1: 17:43: second buffer text`), preview box;
  client list with the client's screen; the options tree (3.8: 12 rows
  `(0) + Server Options` … `(M-b) + Key Table - root`, expandable).
- puritty: `tmux's buffer-mode is not drawn under -CC; q leaves it` (and
  the same for client-mode / options-mode). (Known: TM32.)

### display-panes `prefix q`
- Digits, colors, `50x29`/`49x14` labels: match. The right-hand panes'
  digits are **one cell left** of tmux's (col 76 vs 77, 72 vs 73). tmux
  draws every border gray while the numbers are up.

### clock-mode `prefix t`
- Match (digits, color, place).

## Copy mode

### entering (`prefix [`)
- `[0/14]` at the top right in mode-style: match.

### search (3.8, vi `?` and emacs `C-r`)
- tmux: **every match highlighted** (teal), the current one purple, and
  the position reads `[0/0] (7 results)`.
- puritty: no highlighting, no `(N results)`; the cursor lands on the
  match (vi). (Known: TM31 Not yet.) Same on 3.6a.
- **Prompt placement:** tmux puts `(search up)` and `(goto line)` on the
  pane's last row in mode-style; puritty on the bar row.
- **emacs `C-r` does not search in puritty:** after `Up Up Up`, `C-r 3`,
  tmux's cursor moved to 0,25 as `3` was typed (incremental) and stayed
  there after Enter; puritty's tmux reported 2,25 both times (no move). A
  later `C-Space Up Up C-e M-w` then copied `\n38\n39` against tmux's
  `\n38\n`.
- Selection, line selection and rectangle (vi): drawn; no difference seen
  beyond the cursor positions the search left.

### mouse drag in a pane (`mouse on`)
- tmux: the drag enters copy mode with a selection (`copy-mode`,
  cursor 2,22) and the release copies it to a tmux buffer (`\n35\n36`).
- puritty: pane stays out of copy mode and no tmux buffer is made
  (puritty's own selection, TM17). Behavior difference by design.

## Prompts and messages

### command prompt `prefix :`
- `:` row in mode-style on the status line: match (puritty's amber is
  lighter than 3.8's `#b8860b`).
- **Tab completion missing:** `split-w` Tab → tmux `:split-window`,
  puritty `:split-w`; `sel` Tab → tmux `:select-` (common prefix), puritty
  `:sel`. (Known: TM25.3.)
- History (Up): match.
- `status-keys vi`: Escape puts tmux's prompt in normal mode (drawn with
  message-command-style); puritty closes the prompt. (Known: TM25.3.)

### confirm-before (`prefix x`, `prefix &`)
- `kill-pane 2? (y/n)`, `kill-window first? (y/n)`: match (puritty puts a
  space before its cursor).

### other prompts (`,` `$` `.` `'` `f`)
- `(rename-window) first`, `(rename-session) main`, `(move-window)`,
  `index`, `(find-window)`: match.

### messages (`display-time 6000`)
- `hello from tmux`, `prefix i`'s `[main] 0:first, current pane 0 - (… )`:
  match.
- **Error wording:** tmux `Unknown command: no-such-command`, puritty
  `parse error: unknown command: no-such-command`.
- **`message-style` / `message-command-style` not read:** with
  `message-style bg=red,fg=white` tmux draws the message and the prompt
  white on red, across the text only, the status line continuing after
  it; puritty keeps its amber full-width row.

### show-messages `prefix ~`
- tmux: the log of key bindings and messages, newest first, long lines
  wrapped, `[0/0]`.
- puritty: the log is **dominated by puritty's own control traffic**
  (`send-keys -K C-b`, `send-keys -HK 7e`, `switch-client -T root`,
  `capture-pane …`, `refresh-client -B …` subscriptions), lines cut at the
  edge, `[20/20]`; `message:` entries for what was displayed are absent.

### list-keys `prefix ?`
- Lines and `[64/64]`: match; tmux 3.8 writes the time (`17:45`) before
  the position, puritty does not (known, TM26).

## Menus and popups

### display-menu from keys (`prefix <`, `prefix >`)
- Box, title, dim items, keys, chosen item: match (chosen-item yellow is
  lighter in puritty).

### right button (`mouse on`)
- On a pane word: tmux and puritty both show the pane menu with `Search
  For wordy`, `Type wordy`, `Copy wordy` (first round, press+release).
- **On the status line nothing in puritty:** right press on `0:first`
  gives tmux's window menu (`0:first` / Swap Left …), on `[main]` the
  session menu (`main` / Renumber, Rename, Detach, New Session, New
  Window); puritty shows neither and the following C-c reached the pane.
  (Known: TM27 says MouseDown3Status is not offered.)

### display-popup
- tmux: a framed popup `┌─title─┐ inside popup` over the panes (`-E -w 40
  -h 10` likewise).
- puritty: **nothing shown and no message**; the popup's command runs
  unseen in tmux.

## Mouse

### status line clicks
- Left click on `0:first` (col 8) selects window 0 in both.
- Dragging `0:first` onto `2:three`: neither reordered (tmux's default
  binding did nothing for this drag either).

### border drag
- Dragging the vertical border from col 50 to 30 resized both identically
  (`w 30` / `w 69`). tmux also made the left pane active (`%0`); puritty
  left `%2` active.

## 3.6a (the work hosts' version)

Re-run: status-flags, status-overflow, borders-3/4, border-status-top,
indicators, double lines, scrollbars, choose-tree, display-panes, copy-vi,
search, command prompt, list-keys, menus (`out-3.6a/`). The differences are
the same as on 3.8. 3.6a-specific: status bar `green` (no underscore on
the current window; puritty also none: styles are read); tree arrows `->`
(puritty's `─>` matches 3.6 better than 3.8's `→`); preview labels just
the index; search highlights `bg=cyan`, the position `bg=yellow` with
`(7 results)`; pane-scrollbars exist and puritty draws none.

## Files

- `survey.py` — the harness (one Xvfb, per scene two servers + outer +
  puritty; steps keys/type/cli/click/rclick/rpress/drag/dragstart/dragend/q/shot).
- `scenes.py`, `scenes2.py` — the scenes (round 2: C-c instead of Escape,
  display-time, mouse targets, state queries).
- `pair.py` — renders `*.tmux.ans` and stacks it over the puritty frame.
- `out-3.8/`, `out-3.6a/` — `*.tmux.txt`, `*.tmux.ans`, `*.puritty.png`,
  `*.pair.png`; `run-all.log`, `run-2.log`, `run-36.log` — sizes and
  per-shot states.
- Harness flaw: `rpress` never releases button 3, so in `menus-mouse2`
  only the first right press (window status) is valid for puritty.

# What tmux draws on a client, against what puritty draws under -CC

Survey, 2026-11-12. tmux side read from the 3.8 tag
(`scratchpad/tmux-3.8`, paths below relative to it). puritty side read from
`~/prj/puritty/docs/tmux.md` TM24–TM38 and `app/src/TmuxMode.geng`
(function names given), `packages/tmux/src/Tmux/`.

Columns: **default** is tmux 3.8's; **puritty** is yes / partly / no with
evidence; **conf** is R (read in both sources), Rt (read in tmux, puritty's
side inferred from a grep that found nothing or from a doc's "not yet"), I
(inferred). **ver** is the tmux version that added it where it is newer than
the 3.2 floor (CHANGES line ranges: 3.8 1–245, 3.7 271–600, 3.6 632–834, 3.5
845–934).

Gilbert's own `~/.tmux.conf` changes only the prefix, `|`/`-` splits,
`mode-keys vi`, `C-k`, `set-clipboard on`: so tmux's **defaults** are what
he sees, and the rows below weight them.

What puritty subscribes to (`statusSubscriptions`, TmuxMode.geng:3708):
status-left/right (T:), status-style, window-status-separator, the two
lengths, each window's status format/style/flags, pane-border-status,
pane-border-style, each pane's pane-border-format, its (E:)
pane-active-border-style, pane_marked. Nothing else is read from tmux's
drawing options: a grep of app/ and packages/tmux/ finds no
`pane-border-lines`, `pane-border-indicators`, `pane-scrollbars`,
`window-style`, `window-active-style`, `status-justify`, `status-position`,
`status-format` (only in comments), `message-*`, `display-time`,
`menu-style`, `display-popup`, `copy-mode-*`, `tree-mode-*`,
`clock-mode-*`, `display-panes-colour`/`-format`, `remain-on-exit`,
`visual-*`, `status-keys`, `switch-mode`.

---

## 1. Pane borders

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| Border line glyphs incl. junctions ┬┴├┤┼ by cell type (`screen-redraw.c:384` `redraw_get_cell_type`, `window_get_border_cell` at :1243) | single | partly: `divider` (TmuxMode.geng:2232) draws only `│` and `─`; no junction glyphs | Where dividers meet, one line overwrites the other instead of `┼`/`├`/`┤`; tmux's look is not tmux's | R |
| `pane-border-lines` single/double/heavy/simple/number/spaces (`options-table.c:1603`, `tmux.h:1149`) | single | no (not read) | `double`/`heavy`/`number` (pane index painted along the line)/`spaces` ignored | Rt |
| `pane-border-indicators` arrows / both: `,` `+` `-` `.` ACS arrows next to the active pane (`screen-redraw.c:631` mark, `:1186` draw) | colour | no | Arrow indicators ignored | Rt |
| Two-pane colouring: with exactly two tiled panes, each half of the divider takes the nearer pane's style (`screen-redraw.c:419`, `:806`) | on (indicators=colour) | no: tmux look frames the active pane all round (`paneBorders`, :3592) | With two panes the whole divider is active-coloured, where tmux colours half | R |
| Active border style is a format: blue modal, magenta marked, **red synchronize-panes, yellow pane in a mode**, green otherwise (`options-table.c:1555`) | as stated | partly: subscribed with `E:` (`puritty-pborder`), drawn only in tmux look; puritty's look draws only the marked frame (`frameColor` in `paneBorders`) | In the default look nothing says a pane is synchronized, in copy/tree mode or modal | R |
| `pane-border-status` top/bottom + `pane-border-format` (`options-table.c:1576`, `:1612`; `redraw_pane_status_line` :1550) | off | yes (TM30, `paneBorders` titleOf, `fitted`) | — | R |
| `top-floating` / `bottom-floating` values (`tmux.h:1539`) | — | partly: `titleOf` only acts on "top"/"bottom" | 3.8 floating-only titles not drawn | R (3.8) |
| Clickable `[t]/[f] [u]/[z] [x]` buttons in the default pane-border-format when `mouse` on (`options-table.c:1576` range=control) | shown when status on | partly: drawn, clicks do nothing (TM30 not yet) | Mouse only; low for a keyboard user | R |
| Pane scrollbars `pane-scrollbars` off/modal/on/auto-hide, `-position`, `-style`, `-timeout`; mouse on them (`screen-redraw.c:458`, `:1289`; `options-table.c:1637–1664`; key-bindings.c:562–564) | off | no | A user who turns them on gets nothing; puritty has its own scroll bar outside tmux (TM38) | Rt (3.6; auto-hide 3.8) |
| `fill-character`: area outside a smaller window / unused inside (`window-border.c`; `options-table.c:1474`) | grey `~` | no | Only matters when the window is not the client's size; rarely under -CC | I (3.8) |
| `window-style` / `window-active-style` (pane default fg/bg, e.g. dim inactive panes) applied by the client tty (`tty.c:3153`) | default | no | %output carries none of it; a config that dims inactive panes shows no difference | Rt |
| `pane-colours` palette option (`options-table.c:1629`) | empty | no | Ignored | Rt |
| Pointer feedback over borders (tmux has none; the terminal draws the pointer) | — | yes (TM38 `pointerShape`) | — | R |
| Pane-local prompt line for `command-prompt -P` (`screen-redraw.c:1626`) | — | yes in effect: puritty's own prompt (TM25) | Placement differs (box or bar row, not the pane's last row) | R (3.8) |

## 2. Status line

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| `status-format[0]` as the real layout engine (`options-table.c:119`), user-set `status-format` | built-in | no: puritty rebuilds left + windows + right itself (`tmuxBar`, :3832) | A custom `status-format` is ignored | R |
| `status-left`/`-right`, lengths, `status-style`, window formats/styles/flags/separator | `[#S] `, `"#{=21:pane_title}" %H:%M %d-%b-%y`, `bg=themegreen,fg=themeblack` | yes (TM29) | — | R |
| Window list overflow: `<` `>` markers and `list=focus` keeping the current window visible (`options-table.c:125`, `:151`) | on | no: `tmuxBar` lays windows left to right and drops pieces past `cols`, drops status-right if it would collide | With many windows the current one can fall off the right edge, no `<`/`>` | R |
| `status-justify` left/centre/right/absolute-centre (`options-table.c:1052`) | left | no (TM29 not yet) | Centred lists drawn left | R |
| `status-position` top/bottom (`options-table.c:1093`; `status.c:92`) | bottom | no; `[tmux] tabs` decides (TM22) | User's top status ignored | R |
| `status on/off/2..5` lines; default lines 2 (`P:` pane list) and 3 (`S:` session list) (`options-table.c:184`, `:212`, `:1006`) | 1 line | no | `status off` still shows a bar; `status 2/3` extra lines missing | R |
| `status-left-style`, `status-right-style`, `window-status-last-style`, style options as formats (3.8: "colours in styles are expanded as formats") | default | partly: window styles subscribed without `E:` (`puritty-wstyle`), left/right/last styles not subscribed | Formats inside style options come through unexpanded; left/right styles lost | R |
| Wide characters in status line | — | partly: counted as one cell (TM29 not yet) | CJK window names misplace the rest of the line | R |
| Mouse on status: `MouseDown1Status`, wheel prev/next window, `MouseDown3Status` window menu, `MouseDown3StatusLeft` session menu (`key-bindings.c:533–552`) | bound | partly: click selects; menus/wheel not offered (TM27 not yet) | Mouse only | R |
| Bell: BEL passed to the outer terminal; `visual-bell/activity/silence` show "Bell in window N" (`alerts.c:214`, `:250`, `:286`, `:308`) | bell on, visual off | partly: tab flag and style yes (TM30); no ring/flash, no visual message | A bell in a visible pane is silent | R |
| `set-titles` / `set-titles-string` (outer window title) (`options-table.c:984`) | off | no | Off by default | Rt |

## 3. Messages and prompts

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| `display-message` / errors shown on the status line, cleared by `display-time` or a key (`status.c:340–390`; `cmd-queue.c:882`) | 750 ms | partly: shown at bar right "until the next key" (TM24.4) | No timeout: a message stays until a key | R |
| `message-format` / `message-style` / `message-command-style` / `message-line` (`options-table.c:897–928`) | yellow on black; command prompt black/yellow | partly: tmux look draws hard-coded tmux colours (TM25.2); options not read | User's message styles ignored | R (format 3.7) |
| `confirm-before`, `command-prompt` with `-p -I -1 -N -k`, templates | — | yes (TM25) | — | R |
| Prompt editing keys (`prompt.c:1214`): Left/Right/Home/End/C-a/C-e/C-b/C-f/BSpace/DC/C-d/C-u/C-k/C-w, history Up/Down | — | yes (`editLine`, :2565) | — | R |
| Prompt keys missing: Tab completion of commands/targets with a completion list drawn (`prompt.c:1311`, `:1669`, `prompt_draw_complete` :368); C-y paste top buffer (`:1430`); C-t transpose (`:1434`); M-f/M-b, C-Left/C-Right words (`:1389`); C-p/C-n history (`:1411`); C-r/C-s reverse/forward incremental search direction (`:1459`); C-v literal (`:1481`) | — | no (TM25.3: Tab not yet) | `prefix :` has no completion; `C-p`/`C-n` don't recall history | R |
| `status-keys vi` prompt editing, Escape to command mode (`options-table.c:1060`) | emacs | no (TM25.3) | Only for vi status-keys users | R |
| Prompt history per type (command / search / target / window-target), shared across clients, persisted in `history-file` (`prompt-history.c:31`, `:41`) | 100 entries | partly: puritty's own single `history` array (State) | History not tmux's: not shared with a non-CC client, lost on restart, search and command mixed | R |
| Incremental search prompt `-i` (emacs copy mode C-r/C-s) | — | partly: answers once on Enter (TM25.3) | No live search while typing | R |
| `prompt-cursor-style/-colour` (`options-table.c:1157–1182`) | — | no | Cosmetic | Rt |
| A prompt nested in another command (`if-shell … { command-prompt }`) | — | no: held with a message (TM25.3) | No default binding does it | R |

## 4. Menus and popups

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| `display-menu` items, keys, disabled `-` items, separators, `-x/-y` placement, title | — | yes (TM27) | — | R |
| Menu keys (`menu.c:398–503`): also PPage/C-b, NPage/C-f page, C-[ / C-g close; with `MENU_TAB` BSpace closes | — | partly: TM27 list lacks PPage/NPage/C-b/C-f/C-g | Small | R |
| Menu `-O` stay open, `-C` starting choice, `-M` (`menu.c:574`) | — | no (TM27 not yet) | Small | R |
| `menu-style`, `menu-selected-style`, `menu-border-style`, `menu-border-lines` (`options-table.c:469–496`) | grey, yellow selected, single | partly: hard-coded tmux defaults in tmux look | User styles ignored | R |
| `#[…]` styles inside item names (default menus use `#[underscore]`, `key-bindings.c:60`) | — | no: left out (TM27) | Cosmetic | R |
| Hover highlight without a button (`menu.c:342–382`) | — | no: needs a press (TM27) | Mouse only | R |
| **`display-popup`** (`popup.c`; does nothing for a control client, `cmd-display-menu.c:594`) incl. `-E` command, `-T` title, `popup-style/border-style/border-lines` (`options-table.c:1672–1690`), drag/resize (`popup.c:325`) | — | **no**: not held, not read (no `popup` in app/ or packages/tmux) | A user binding like `bind g display-popup -E lazygit` silently does nothing under -CC. 3.7+ floating panes (`new-pane`) do work and could stand in | Rt |
| 3.8 menus belong to the window (shown on all clients) (CHANGES 3.8) | — | n/a | — | I |

## 5. Modes: tree / buffer / client / customize / switch

### 5a. choose-tree (`prefix s`, `prefix w`, and `prefix f` = find-window)

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| Sessions and windows, `-s` folded / `-w` open, current row chosen | — | yes (TM32 `treeRows`, `treeLoaded`) | — | R |
| **Panes level**: each window has its panes as children (`window-tree.c:360–372`); Right on a window opens its panes | — | **no**: rows are sessions and windows only (`TreeRow`, `treeRows` :4869) | Cannot pick a pane from the tree | R |
| Row keys 0–9, M-a..M-z, padded (`mode-tree.c:1620–1636`) | — | yes (TM37 `treeRowKey`) | — | R |
| Default row text: pane `cmd flags: "title"`; window `name<window_flags>: "title"`; session `N windows (group …) (attached)` (`window-tree.c:40–56`) | — | partly: window rows are `index: name* (N panes)` — `*` only, no `-` `Z` `M` `!` `#` flags, no pane title; session rows match minus group | Zoomed/marked/bell flags not visible in the tree | R |
| `-F` format, `-K` key format, `-f` filter, `-O` sort, `-r`, `-N` no preview (`mode-tree.c:584–592`) | — | no: `Syntax.treeOf` reads `-s -w -Z` and the template only | Custom choose-tree bindings lose their options | R |
| **`find-window` (`prefix f`) enters tree mode with a filter** (`cmd-find-window.c:107–112`; `key-bindings.c:429`) | bound to f | **no**: the prompt is asked (TM25) but tmux then enters tree-mode itself, which puritty only *says* ("tree-mode is not drawn", `modeOverlay`, :5262) | `prefix f` ends in a dead-looking pane | R |
| Up/k/C-p, Down/j/C-n (wrap), Home/g, End/G, Left/h, Right/l, Enter, q/Escape | — | yes (`treeKey` :4897) | — | R |
| PPage/NPage move by the list's height (`mode-tree.c:1669–1684`) | — | partly: fixed 10 (`page = 10`) | Small | R |
| `+`/`-` expand/collapse **current**; `M-+`/`M--` all (`mode-tree.c:1741–1773`) | — | partly: `+`/`-` do all; M-± absent | Keys differ from tmux | R |
| Search `/` `?` `C-s` with `(search) ` prompt; `n` `N` repeat (`mode-tree.c:1774–1789`) | — | no | No way to search sessions/windows by name | R (N: 3.5) |
| Filter `f` `(filter) ` prompt, `c` clear; box title shows `(filter: active|no matches)` (`mode-tree.c:1790–1798`, `:1010–1020`) | — | no (TM32 not yet) | — | R |
| Tagging `t`, `T`, `C-t`; `*` on tagged rows (`mode-tree.c:1698–1732`, `:922`); `:` run for each tagged (`window-tree.c:1540`); `X` kill tagged | — | no | — | R |
| `x` kill selected with `Kill session N? ` prompt (`window-tree.c:1496–1526`) | — | no (TM25.3 notes these prompts) | A common tree action missing | R |
| Sort `O` / reverse `r`; box title ` name (sort: index)` (`mode-tree.c:1733–1740`, `:998`) | index | no | — | R |
| `S-Up`/`S-Down` (`K`/`J`) swap windows (`mode-tree.c:1661–1668`) | — | no | — | R (3.6) |
| `m`/`M` mark/clear marked pane, `H` jump to starting pane, `i` info view (`window-tree.c:1474–1495`, `:808`) | — | no | — | R |
| `C-h`/F1 help overlay listing keys (`mode-tree.c:178–225`, `:1645`) | — | no | — | R (3.7) |
| Preview: windows/panes with **their colours** (`screen_write_preview`) | — | partly: plain text (TM35 not yet; `capture-pane` without `-e`) | Colourless preview | R |
| Preview layout: window = panes **side by side**, ≥24 cols each, `<` `>` arrows and scroll when they don't fit (`window-tree.c:659–720`); label centred in `tree-mode-preview-style` (red active/blue) with `tree-mode-preview-format` (`:621–636`, `:770–785`) | — | partly: puritty scales the real layout; label on a top line, green/amber; no `<`/`>` scroll | Different look; more than ~12 items can't be reached | R (format 3.7) |
| Preview size: list ⅔ (½ if short) / preview ⅓; `v` cycles normal/big/off (`mode-tree.c:632–660`, `:1799`) | normal | partly: list ⅓, preview ⅔ (TM35); no `v` | Proportions inverted vs tmux | R |
| `tree-mode-selection-style` whole line, `tree-mode-border-style` box (`mode-tree.c:849–851`, `:995`) | mode-style | partly: mode-style in tmux look (TM32) | — | R (3.8) |
| Mouse: click selects, double-click chooses, wheel moves, right click item menu (`mode-tree.c:1581–1613`) | — | no evidence in `treeKey`; pointer is an arrow (TM38) | Mouse only | I |

### 5b. Other modes

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| choose-buffer (`prefix =`): list + preview, Enter/p paste, P paste tagged, d/D delete, e edit, f filter (`window-buffer.c:341–353`, command `paste-buffer -p -b '%%'` :41) | bound | no: "buffer-mode is not drawn under -CC; q leaves it" (`modeOverlay`) | Cannot pick a buffer to paste | R |
| choose-client (`prefix D`): d/D/x/X detach, z/Z suspend, i info view (`window-client.c:402–416`) | bound | no: said | — | R |
| customize-mode (`prefix C`): options/keys/hooks tree, Enter/s/S/w set, d/D/u/U, e editor, C changed only, v info (`window-customize.c:1559–1581`) | bound | no: said | — | R (hooks/e/C 3.8) |
| switch-mode (`prefix Tab` / `BTab` in 3.8): fuzzy window/session switcher in a floating pane with `(search) ` prompt (`window-switch.c:41`, `:224`, `:367`; `key-bindings.c:441–442`) | bound | no: the floating pane appears, its mode is said not drawn | 3.8 only (not on Gilbert's 3.6 hosts) | R (3.8) |
| view-mode (output of `?` `#` `~` `:`) | — | yes (TM26) + puritty's own filter (TM36) | — | R |

## 6. Copy mode

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| Scrolled view, cursor, selection (char/word/line, rectangle) | — | yes (TM31 `copyLine`, `copySpans`) | — | R |
| Selection style `copy-mode-selection-style` = mode-style, yellow bg (`options-table.c:1430`, `window-copy.c:5936`) | yellow/black | partly: selection inverted (TM31) | Not tmux's colour in tmux look | R |
| Position indicator `copy-mode-position-format`: `[copy_position/limit]` **+ `(N results)` / `(timed out)`** + line time (`options-table.c:1409`; drawn `window-copy.c:5474`) | shown | partly: `[scroll_position/history_size]` only (TM31) | Search result count missing | R |
| **Search match highlighting**: all matches `copy-mode-match-style` (cyan), current `copy-mode-current-match-style` (magenta) (`window-copy.c:5129–5200`, `:4876`) | on after a search | **no** (TM31 not yet) | After `/foo` nothing shows where the matches are; only the cursor moves | R |
| Mark line `copy-mode-mark-style` after `set-mark` (vi `X`) (`window-copy.c:2627–2633`, `:5149`) | yellow | no | Rarely used | Rt |
| Line numbers `copy-mode-line-numbers` off/default/relative/hybrid, `line-numbers-toggle`, styles (`window-copy.c:5248–5300`, `options-table.c:1439–1466`; menu item `key-bindings.c:55`) | off | no | Only if turned on | Rt (3.7) |
| `copy-mode-current-line-style` (`window-copy.c:5140`) | default | no | Invisible by default | Rt (3.8) |
| Auto refresh `refresh-on/off/toggle`, `r` refresh-now (`window-copy.c:3713`) | off | partly: puritty draws from its own live history (TM31), so content is always current | Behaviour differs (tmux freezes the view) | I (3.8) |
| Formats available but unused: `search_present`, `search_count`, `search_count_partial`, `search_match`, `selection_mode`, `top_line_time`, `copy_line_numbers` (`window-copy.c:1100–1173`) | — | not asked (`copyFormat` :5326) | Cheap source for the count; matches need puritty to search its own history with the string it sent | R |
| History beyond puritty's own `[scrollback] lines`; lines rewrapped after a width change | — | partly (TM31 not yet) | — | R |

## 7. Clock

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| Big digits, centred, `HH:MM` | 24 | yes (TM32 `modeOverlay`) | — | R |
| `clock-mode-style` 12 / 24 / 12-with-seconds / 24-with-seconds, AM/PM (`window-clock.c:243–262`, `options-table.c:38`) | 24 | no: `clockText` gives `HH:MM` only | 12-hour and seconds styles ignored | R |
| `clock-mode-colour` (`window-clock.c:240`) | themeblue | no: hard-coded `\e[44m` | User colour ignored | R |

## 8. display-panes

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| Big digits per pane, active red, others blue, size top right, digit selects, timeout | 1000 ms | yes (TM28) | — | R |
| Two-digit indexes (≥10 panes) | — | no (TM28 not yet) | — | R |
| `display-panes-colour`, `-active-colour`, `-format`, `-border-style` (`options-table.c:1338–1372`; `window-panes.c:236`, `:692`) | blue/red/`WxH` | partly: colours/format hard-coded | User values ignored | R (format/border 3.8) |
| 3.8: display-panes is a mode inside a pane (`window-panes.c`), `-b` removed | — | yes for the binding (held, TM28); `panes-mode` entered any other way is only said | — | R (3.8) |

## 9. Cursor and miscellany

| tmux feature (source) | default | puritty | gap | conf |
|---|---|---|---|---|
| "Pane is dead (status N, time)" line written into the pane by `remain-on-exit-format` (`server-fn.c:403–414`; `options-table.c:1710`) — written to the pane's screen, not %output | remain-on-exit off | no (no `dead` in TmuxMode) | With remain-on-exit on, a dead pane looks alive and blank | Rt |
| `remain-on-exit failed-key` (3.8) waits for a key | — | no | — | Rt (3.8) |
| `lock-session`/`lock-client` run `lock-command` on the client tty | — | no (TM24: harmless) | — | R |
| `suspend-client` | — | held with a message (TM24) | — | R |
| Cursor hidden during messages/prompts (`status.c:388`), cursor style/colour options (`options-table.c:354–362`) | — | partly: hidden in prompts/views (TM25/26); options not read | — | I |
| Modal panes (blue border, take all keys) | — | partly: `modal` flag kept (TmuxMode.geng:1743); blue border only in tmux look via E: | — | R (3.8) |
| `refresh-client -U/-D/-L/-R` panning a larger window, `window_bigger` offset in status-right | — | no (TM24.3: control client has the window's size) | — | R |

---

## Ranked: what a keyboard-driven tmux user would notice most

Gilbert uses `prefix s`/`w`, vi copy mode and the status line, on tmux
3.6 at work (3.8 at home).

1. **Copy-mode search shows no matches** (§6). After `/foo` tmux paints
   every match cyan and the current one magenta and says `(N results)`;
   puritty moves the cursor only. Formats give the count
   (`search_count`); highlighting means puritty searching its own history
   with the string it sent.
2. **`prefix f` (find-window) ends in an undrawn tree-mode pane** (§5a).
   It's a default binding that becomes a dead end. Fix by reading
   `find-window` like `choose-tree` (its `-f` filter, `cmd-find-window.c:70–104`).
3. **The tree has no pane level** (§5a). In `prefix w` tmux opens a window
   into its panes, and puritty can't pick a pane.
4. **No search or filter in the tree** (`/`, `n`, `N`, `f`, `c`). With many
   sessions this is the main way to get around. The view already has a
   filter (TM36) to reuse.
5. **No `x` kill (with its `Kill window N?` prompt), tags, `:` in the
   tree**, nor `S-Up`/`S-Down` swap (3.6) or `C-h` help (3.7).
6. **Tree rows lack window flags and titles**: `Z`, `M`, `!`, `#` and `-`
   don't show, and `+`/`-` fold all rows, where tmux folds only the current
   one (M-± folds all). The preview is colorless, and its proportions are
   the reverse of tmux's (⅓ list vs ⅔).
7. **The status window list overflows silently.** There are no `<`/`>`
   markers and nothing keeps the current window visible. With many windows
   the active one can drop off the right edge.
8. **`choose-buffer` (`prefix =`), `customize-mode` (`prefix C`) and
   `choose-client` (`prefix D`) are only "said"**: the pane is blocked
   until q.
9. **Command prompt: no Tab completion, no `C-p`/`C-n`, no `C-y`, no word
   motions.** History is puritty's own, not tmux's per-type shared
   history.
10. **Border drawing isn't tmux's.** There are no junction glyphs, and
    `pane-border-lines` and `pane-border-indicators` are ignored. In
    puritty's default look nothing marks a synchronized pane (red) or a
    pane in a mode (yellow), and with two panes the whole divider is
    colored instead of half.
11. **`display-popup` bindings do nothing.** This is not held or emulated;
    a floating pane could stand in.
12. **Messages don't time out** (`display-time`). A bell in a visible pane
    makes no sound and no visual-bell message shows.
13. **The status line's own options are ignored**: `status-justify`,
    `status-position`, `status off`/`2`/`3`, a custom `status-format`,
    left/right styles, and wide characters counted as one cell.
14. **`window-style`/`window-active-style` are not applied**, so configs
    that dim inactive panes do nothing.
15. **The clock and display-panes ignore their styles**:
    `clock-mode-style` (12-hour, seconds), the colors, and two-digit pane
    numbers.

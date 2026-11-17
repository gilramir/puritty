# For Gilbert to review

Things found along the way that were left as they are, for Gilbert to
decide on later. Numbered RV*n*; each says where it was found, what
differs, and what fixing it would take. An item decided moves to the
section that does it, and its line here says where.

## RV1 · What the tree's preview shows of each pane (2026-11-16)

Found with TM88, side by side with real tmux 3.8 and 3.6a
(`bench/tmux/compare/scenes_mouse.py`, `tree-preview-labels`).

**tmux** (`screen_write_preview`, every release): with the pane's cursor
on, the part of its visible screen around the cursor: from a third of the
preview's height above the cursor's row and a third of its width left of
the cursor's column, held inside the screen; with the cursor off, the top
left. It draws the cursor there too.

**puritty** (`drawPreview`): the pane's last rows with text in them
(`capture-pane`, trailing blank rows dropped), from the left edge, no
cursor. So a pane whose prompt sits near the top shows the same rows in
both; one with its cursor high up and text below it, or one in a program
that hides the cursor (vim, less), shows different rows, and a wide line
is cut at a different place.

**To match it**, the preview's question would also ask each pane's
`cursor_x`, `cursor_y` and `cursor_flag` (`pane_height`, `pane_width` it
has), pick the rows and columns as tmux does, and draw the cursor; in
tmux's look only, or in both.

## RV2 · The prompt's emacs word keys and `word-separators` (2026-11-16)

**Decided 2026-11-16: as tmux; done in `docs/tmux.md` TM104.** The
defaults below were wrong: ` -_@` is 2.7–2.9's; 3.0–3.2's is a space and
3.3's on the punctuation but `_`, so on 3.3 on Ctrl-W after `my_logs`
deletes it whole, as puritty did.

Found with TM100. puritty's Alt-B and Ctrl+Left, Alt-F and Ctrl+Right, and
Ctrl-W at tmux's prompt stop at spaces only (`editLine`'s `wordStart`,
`wordEnd`). tmux's stop at the session's `word-separators` too (space,
`-`, `_` and `@` by default): 2.7 to 3.2 skip the separators and take a
word as the run between them (`status_prompt_key`'s `M-f`, `M-b`, C-w);
from 3.3 a run of separators is a word of its own (`prompt_forward_word`,
`prompt_backward_word`, C-w by the same classes). With
`new-window -n my_logs` and the caret at the end:

| keys | tmux 3.8 | puritty |
|---|---|---|
| Ctrl-W | deletes `logs`, leaving `my_` | deletes `my_logs` |
| Alt-B | to the start of `logs` | to the start of `my_logs` |
| Alt-F from the start of `new-window` | after `new` | after `new-window` |

The vi keys (TM100) follow tmux.

**To match it**, the three keys would take the separators puritty asks
(`word-separators`, TM100) and each version's rule, as the vi keys do.

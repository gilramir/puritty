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

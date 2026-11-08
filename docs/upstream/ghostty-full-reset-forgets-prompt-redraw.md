# A full reset undoes libghostty-vt's choice not to clear prompts on resize

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by puritty's differential
fuzzer (`vt-core.md` §VC22). Not to be filed (`README.md`). The oracle
carries the fix as `harness/oracle/patches/0011-a-full-reset-keeps-the-embedders-prompt-redraw.patch`.

## Summary

After a resize, while the cursor is on a prompt or its input, Ghostty clears
the prompt's rows for the shell to write again, unless
`flags.shell_redraws_prompt` says the shell will not (kitty's `redraw`
option of OSC 133 A). The flag's default is to clear. libghostty-vt's
`ghostty_terminal_new` sets it not to, since its embedders need not install
Ghostty's shell integration ("don't assume OSC 133 prompts can be redrawn on
resize"). `fullReset` rebuilds `flags` from its defaults, so after RIS a
libghostty-vt terminal clears prompts on resize as Ghostty's own does. The
other flag the embedder chooses, the checksum's, is kept apart as
`default_xt_checksum` and restored by RIS.

## Reproduction

With libghostty-vt, 8 columns by 4 rows (puritty `corpus/replay/prompt-redraw-off`):

```
out CR LF ESC ]133;A ST $ SP ab   a prompt being written
resize 6x4                        the prompt kept: redraw is off
ESC c                             RIS
ESC ]133;A ST $ SP ef
resize 8x4
```

| | after the second resize |
|---|---|
| Ghostty | the prompt's row cleared |
| expected | `$ ef` kept, as before the reset |

## Where

`src/terminal/Terminal.zig`, `fullReset`: `self.flags = .{ ... }` with no
`shell_redraws_prompt`; `src/terminal/c/terminal.zig`, `new`, which sets the
flag alone.

## Fix

Keep the embedder's choice beside the flag, as `default_xt_checksum` is
kept, set it where `ghostty_terminal_new` sets the flag, and restore the
flag from it in `fullReset`.

# `send-keys -K` drops escape-sequence keys, and Enter under extended keys

**Repository:** `tmux/tmux`

**Found against:** 3.8 (`7f2a35ad`), 3.7c and 3.6a (nixpkgs builds),
2026-11-12, chasing a user's report that Enter did nothing in Claude Code
under puritty's `tmux -CC` (`tmux.md` TM50). Not filed: Gilbert decides.

## Summary

A key injected with `send-keys -K` through a client keeps `KEYC_SENT`
(`cmd-send-keys.c`, `event->key = key|KEYC_SENT`). When no binding takes
it, it reaches `input_key` (`input-keys.c`) with that flag still set, so:

- it is never the "trivial case" (`!(key & ~KEYC_MASK_KEY)`), and
  `input_key_get(key)` finds no entry for an arrow or a function key;
  the key then counts as internal (`KEYC_IS_SPECIAL`) and is dropped;
- Enter, not trivial either, falls to the extended-keys encoder, and with
  the pane in extended keys (`extended-keys on` and the program asking
  for modifyOtherKeys) nothing is written.

The same names sent without `-K` (`send-keys -t %0 Down`) are written as
they should be.

| sent by a control client | 3.6a | 3.7c, 3.8 | 3.8, pane in Ext 2 | without `-K` |
|---|---|---|---|---|
| `send-keys -K Down` | `o` | nothing | nothing | `\e[B` |
| `send-keys -K F5` | `_` | nothing | nothing | `\e[15~` |
| `send-keys -K Enter` | `\r` | `\r` | nothing | `\r` |
| `send-keys -K BSpace`, `-K -H 61` | `\x7f`, `a` | the same | the same | the same |

## Reproduction

```sh
tmux -L k -f /dev/null new -d -s m 'python3 -c "import os,tty;tty.setraw(0);os.write(1,b\"\x1b[>4;2m\")
while 1: print(repr(os.read(0,64)),file=open(\"/tmp/k.log\",\"a\"))"'
tmux -L k set -s extended-keys on
printf "send-keys -K Down\nsend-keys -K Enter\nsend-keys -t m Down\n" | script -qc 'tmux -L k -CC attach -t m' /dev/null
cat /tmp/k.log    # only the third arrives: b'\x1b[B'
```

## Fix

Clear `KEYC_SENT` before the key is encoded for the pane (in the `-K`
path's forward to `window_pane_key`, or at the top of `input_key`).

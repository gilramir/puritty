# An XIM client makes four blocking round trips for each message it sends

**Repository:** `fcitx/xcb-imdkit`

**Found against:** 1.0.9 and `main` at `621048bd` (2026-10-09). Found by
visiterm's phase 3 survey (`docs/phase3-input.md` §3.3). Kept for Gilbert
to decide on; not filed.

## Summary

Every message the client side sends that is longer than 20 bytes, which
includes every `XIM_FORWARD_EVENT` (a key event is 44 bytes), costs four
round trips to the X server before it is sent, each waited for inside the
call:

| request | why it waits | needed? |
|---|---|---|
| `InternAtom` of `_clientN` | the reply's atom | no: the names rotate through a fixed set and can be interned once |
| `GetProperty` of that atom | its reply, which is freed unread | no |
| `ChangeProperty`, checked | `xcb_request_check` | no: the server processes a client's requests in order |
| `SendEvent`, checked | `xcb_request_check` | no |

A short message pays the last one. Over `ssh -X` to a display 3.3–6 ms
away, a key event took 15.6–24.3 ms to reach the IME and come back
(fcitx5-hangul, 20 key events); with the four removed, 3.4–14.5 ms. xtrace
of one keystroke locally: 11 replies waited for (5 on the press, 6 on the
release) before, 2 after.

The waits are inside `xcb_xim_forward_event` and `xcb_xim_filter_event`, so
a client with one thread, as most terminals are, stops drawing for them.

## Reproduction

An XIM client on a remote display, typing through fcitx5 or ibus with
xtrace between the client and the server:

```
xtrace -n -D :80 -d :79 -o trace.log -k &
DISPLAY=:80 ./client          # any xcb-imdkit client, e.g. test/client_demo
xdotool type gks              # on :79
grep -c 'Reply to' trace.log
```

## Where

`src/message.c`, `_xcb_send_xim_message`: `xcb_intern_atom_reply`,
`xcb_get_property_reply` (its result freed unread),
`xcb_change_property_checked` + `xcb_request_check`,
`xcb_send_event_checked` + `xcb_request_check`. `src/imclient.c`,
`_xcb_xim_send_message`, builds a new `_client%u` name for each message.

## Fix

visiterm carries it as `packages/x11/patches/xcb-imdkit-0001-no-round-trips.patch`:
the client interns the whole rotation once, pipelined (one round trip at
its first message), and sends through a variant of `_xcb_send_xim_message`
that takes the atom and sends both requests unchecked. The server side is
left as it is.

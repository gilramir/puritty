# Each key forwarded by the XIM client waits for several X round trips

- **Repository:** `fcitx/xcb-imdkit`
- **Version:** the latest commit, `621048bd` (2026-10-09)
- **Input method used:** ibus 1.5.29, through XIM
- **Attached:** `xim_roundtrips.c`, a program that measures it

This is about speed, not a bug: everything works, but slowly over a
remote display.

## What happens

Each message the client sends that is longer than 20 bytes goes through a
window property. Every forwarded key is one of those, since a key event is
44 bytes. To send such a message, `_xcb_send_xim_message` in
`src/message.c` makes four requests, and waits for an answer to each one:

1. `InternAtom` for a new `_clientN` name, waiting for its reply;
2. `GetProperty` on that name, waiting for its reply, which is then freed
   without being used;
3. `ChangeProperty`, checked with `xcb_request_check`;
4. `SendEvent`, checked with `xcb_request_check`.

On the same machine these waits are too short to notice. Over a remote
display, such as `ssh -X`, each one costs a network round trip. Most
terminals have a single thread, so they can't draw while they wait.

## Measurements

The attached program forwards 20 keys to the running input method, and
counts the X requests and the time spent for each. It also times one plain
round trip on the same connection, so the time can be read as a number of
round trips. Run over `ssh -X` to a desktop with ibus, about 3 ms away:

| | upstream `621048bd` | with the change below |
|---|---|---|
| X requests to send one key | 6 | 2 |
| time sending one key | 10.4 to 12.6 ms (3 to 3.5 round trips) | 0.005 ms (none) |
| time receiving it back | 5.3 to 6.3 ms (1.6 to 1.8 round trips) | 3.0 ms (about 1) |

To run it:

```
cc -o xim-roundtrips xim_roundtrips.c $(pkg-config --cflags --libs xcb-imdkit xcb)
XMODIFIERS=@im=ibus ./xim-roundtrips
```

## A possible change

We changed our copy of xcb-imdkit like this, and it has worked well:

- The `_clientN` names are interned once, all at once, at the first
  message: one round trip in total instead of one per message.
- The `GetProperty` is dropped, since its result is not used.
- The property and the event are sent unchecked. The X server handles one
  client's requests in order, so the event still arrives after the
  property has been written.

One question for you: the two checks may be there on purpose, so that the
client notices when the input method's window has gone away, for example
after the input method restarts. If so, could they be kept for that case
only, or done without waiting, so that a working connection doesn't pay
for them on every key?

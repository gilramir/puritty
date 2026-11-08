# PuTTY: architecture analysis for a new terminal emulator

Source analysed: `vendor/putty` at commit `7507c54b` (2026-10-14, "Stop treating
U+2028 and U+2029 as newlines"). `LATEST.VER` is `0.85`, so this is the post-0.85
development tree. Unless noted, paths are relative to `vendor/putty/`. Line numbers
come from that snapshot and will drift. Anything not read directly in code is marked
**inference** or **unverified**.

PuTTY matters for puritty for one reason above all: it is the long-standing
Windows-native terminal with a **built-in SSH client**, and it sets what Windows SSH
users expect. That covers the host-key dialog, Pageant, saved sessions, "Restart
Session", and plink/pscp/psftp. Its code is old-style C, but the architecture
underneath is carefully layered and transfers well to any language. This document
reads it for both behaviour and structure.

Contents:

1. Source layout and the core abstractions (Backend, Seat, Interactor, LogPolicy,
   TermWin, Ldisc, Plug/Socket, Conf)
2. SSH implementation architecture (BPP and PPL layers, coroutines, event model)
3. Crypto and protocol features
4. Host key verification: UX and storage
5. Authentication, agents, and anti-spoofing
6. Connection sharing, forwarding, proxies and jump hosts
7. Keepalives, network errors, "Restart Session"
8. Terminal emulation (`terminal/terminal.c`)
9. Front ends: Windows GDI, GTK/pterm, ConPTY
10. Saved sessions, configuration, command-line tools
11. Testing and fuzzing
12. Notable challenges and security history
13. Lessons for puritty

---

## 0. TL;DR

- **PuTTY is a "generic multi-backend remote terminal", not an SSH client with a
  terminal attached.** This is an explicit design rule (`doc/udp.but:114`). Every
  protocol (SSH, bare ssh-connection, Telnet, Rlogin, SUPDUP, Raw, serial, and the
  `pty`/`conpty` local backends in pterm) implements one `BackendVtable`
  (`putty.h:703`). The terminal, line discipline and window know nothing about
  which backend they're talking to. This is the closest existing analogue to
  puritty's "PTY / tmux pane / SSH channel" backend interface.
- **The backend talks *up* through a `Seat`** (`putty.h:1088`), a vtable of about 30
  methods. It carries session output (with a returned backlog for flow control), EOF,
  async prompts (passwords, host keys, weak-crypto warnings), trust-status changes,
  and "remote exited" / "connection fatal" notifications. Seats exist for the GUI
  window, for plink's console, for pscp/psftp, for the SSH server, and for **an SSH
  jump-host proxy** (the proxy is a Seat to the inner SSH session and a Socket to the
  outer one). That composition is the cleverest thing in the codebase.
- **Everything is single-threaded** (`doc/udp.but:262`). One event loop runs a
  timer list (`timing.c`), a queue of **top-level callbacks** (`callback.c`), and
  socket/handle readiness. Code never blocks. A long job is split into callbacks,
  and "idempotent callbacks" (`callback.c:36`) coalesce repeated wake-ups.
  `run_toplevel_callbacks()` runs **one** callback per call (`callback.c:115`), so
  the GUI message pump interleaves with protocol work.
- **SSH is a stack of layers joined by packet queues.**
  1. A *Binary Packet Protocol* (BPP) object handles framing, crypto and
     compression.
  2. Above it sit *Packet Protocol Layers* (PPLs): transport → userauth →
     connection.
  3. The connection layer hosts channels.
  Each layer is a coroutine (Simon Tatham's `crReturn` macros, `sshcr.h`), triggered
  by an idempotent callback whenever its input queue gains a packet. The transport
  layer *wraps* the layer above it and holds its outgoing packets back during
  rekeys. The same layers, reversed, build Uppity, PuTTY's SSH *server*, used for
  testing.
- **Connection sharing** works like OpenSSH `ControlMaster`, but with a different
  wire protocol. The first PuTTY for `user@host:port` becomes the *upstream* and
  listens on a named pipe or Unix socket. Later instances become *downstreams*. They
  speak an unencrypted "bare ssh-connection" protocol and the upstream NATs channel
  numbers. X11 forwarding is demultiplexed by unique fake X auth cookies. Only one
  agent can be forwarded.
- **The trust sigil and Interactor announcement** are PuTTY's anti-spoofing UX:
  - Lines written by PuTTY itself (prompts, host-key text) are tagged "trusted" in
    the terminal and drawn with a PuTTY icon in the left margin, which the server
    cannot forge.
  - When a jump host or proxy asks a question, PuTTY first prints "Making proxy SSH
    connection to …", so the user knows *which* hop is asking.
- **The terminal repaints with damage tracking, built for slow GDI/X11:**
  - `disptext` is a shadow copy of what is on screen. Each paint diffs the wanted
    frame against it and redraws only the changed runs of same-attribute cells.
  - Painting is capped by a **20 ms cooldown** (`terminal.c:40`).
  - There is no reflow on resize, no OSC 8/52/133, no ?2026, no colon-SGR, no
    italics, and DCS is ignored.
- **SSH features:**
  - Current: post-quantum hybrid KEX, OpenSSH certificates, GSSAPI, strict-KEX
    (Terrapin) mitigation, PPK v3 (Argon2), deterministic DSA/ECDSA nonces.
  - Gap: keepalives are `SSH_MSG_IGNORE`, which **keeps NAT state alive but cannot
    detect a dead peer**.

---

## 1. Source layout and core abstractions

### 1.1 Layout

| Path | What lives there |
|---|---|
| `putty.h` | The big header: Backend, Seat, Interactor, TermWin, LogPolicy, Conf API, callbacks, timers |
| `network.h` | `Socket` / `Plug` traits (the networking abstraction) |
| `ssh.h`, `ssh/` | SSH: BPPs (`bpp1.c`, `bpp2.c`, `bpp-bare.c`), layers (`transport2.c`, `kex2-client.c`, `userauth2-client.c`, `connection2*.c`, `login1.c`, `connection1*.c`), channels (`mainchan.c`, `portfwd.c`, `x11fwd.c`, `agentf.c`), sharing (`sharing.c`), SFTP (`sftp*.c`), and the server side (`*-server.c`, `server.c`, `sesschan.c`) |
| `crypto/` | All primitives: AES, ChaCha20-Poly1305, ECC, ML-KEM, NTRU Prime, RSA, mpint, hashes, Argon2, RFC 6979 |
| `terminal/` | `terminal.c` (8193 lines: parser, screen, paint), `bidi.c`, `lineedit.c` |
| `ldisc.c` | Line discipline: local echo and line editing between keyboard and backend |
| `proxy/` | HTTP CONNECT, SOCKS 4/5, Telnet proxy, local proxy command, SSH jump-host proxy, and the `Interactor`/TempSeat glue |
| `otherbackends/` | Telnet, Rlogin, SUPDUP, Raw, and the null/loopback test backends |
| `windows/` | Win32 GUI (`window.c`, 5950 lines), ConPTY backend (`conpty.c`), Pageant, named pipes, registry storage, plink, GSSAPI via SSPI |
| `unix/` | GTK front end (`window.c`, `unifont.c`), PTY backend (`pty.c`), file storage, Unix sockets, `uppity.c` (test SSH server), `psusan.c` |
| `utils/` | Small single-function files: marshalling, `tempseat.c`, `stripctrl.c`, `antispoof.c`, `wcwidth.c`, Conf |
| `settings.c`, `config.c`, `conf.h` | Saved-session load/save, the platform-neutral config dialog description, and the Conf key table |
| `test/` | `testcrypt` + `cryptsuite.py`, `testsc` (side channels), `test_terminal.c`, `test_bpp.c`, `fuzzterm.c` |
| `doc/udp.but` | Developer design principles (worth reading in full) |

Two serialization helpers run through everything:

- **`BinarySink`** (`marshal.h:14`): anything you can `put_uint32`/`put_string` into.
  That includes strbufs, outgoing packets, hash contexts, and MAC contexts.
- **`BinarySource`** (`marshal.h:224`): a cursor over a byte block with a sticky
  error flag. Decoders call `get_uint32`, `get_string` and the rest without checking
  each call. Out-of-data returns a harmless default and sets `err`, and the caller
  checks `get_err()` once at the end.

This pattern removes most hand-written bounds checks in protocol parsing and is
language-neutral. Use it.

### 1.2 Traits as explicit vtables

PuTTY implements interfaces as a struct holding a `vt` pointer, embedded in the
implementation struct and recovered with `container_of` (`doc/udp.but:373`). One
object can implement several traits. `Ssh` is a Backend, a Plug and an Interactor.
`SshProxy` is a Socket, a Seat and a LogPolicy (`proxy/sshproxy.c:16–43`). Any
language with interfaces or traits maps onto this directly.

| Trait | Defined | Direction | Implementations |
|---|---|---|---|
| `Backend` | `putty.h:696`, vtable `:703` | front end → protocol | ssh, sshconn (bare), telnet, rlogin, supdup, raw, serial (Win+Unix), pty (Unix pterm), conpty (Windows pterm), null/loop (tests) |
| `Seat` | `putty.h:1085`, vtable `:1088` | protocol → front end | GUI window (Win `window.c:250`, GTK `window.c:412`), plink (Win/Unix), pscp, psftp, SshProxy (`proxy/sshproxy.c:566`), TempSeat (`utils/tempseat.c:331`), server-side seats |
| `Interactor` | `putty.h:619`, vtable `:636` | anything that may prompt the user during connection setup | Ssh, proxies |
| `LogPolicy` | `putty.h:2073` | logging → front end (Event Log, "log file exists, overwrite?") | GUI, console, SshProxy |
| `TermWin` | `putty.h:1606` | terminal → window (draw text/cursor/sigil, title, palette, clipboard, resize request) | Win, GTK, test mocks, fuzzterm |
| `Plug` / `Socket` | `network.h:22–156` | network ↔ consumer | TCP, named pipes, handles, proxies (a proxy is a Socket built from another Socket) |
| `BinaryPacketProtocol` | `ssh/bpp.h` | SSH framing | SSH-1, SSH-2, bare (sharing) |
| `PacketProtocolLayer` | `ssh/ppl.h` | SSH layers | transport2, userauth2, connection2, login1, connection1 (+ server variants) |
| `Channel` / `SshChannel` | `ssh/channel.h:11`, `:176` | consumer of / provider of one SSH channel | mainchan, port forward, X11, agent forward, sharing |

### 1.3 The Backend interface in detail

`BackendVtable` (`putty.h:703–760`):

| Method | Meaning | puritty analogue |
|---|---|---|
| `init(vt, seat, &backend, logctx, conf, host, port, &realhost, nodelay, keepalive)` | Start connecting, **asynchronously**. Returns an error string or NULL; the connection completes later | `open()` |
| `free` | Tear down | `close()` |
| `reconfig(conf)` | Apply a changed Conf mid-session (e.g. keepalive interval, rekey limits) | live config |
| `send(buf, len)` | Keyboard data to the remote | write |
| `sendbuffer()` | How much is queued outbound | write backpressure |
| `size(w, h)` | Terminal resized → `window-change` / `TIOCSWINSZ` / `ResizePseudoConsole` / NAWS | resize |
| `special(code, arg)`, `get_specials()` | Protocol-specific actions (break, signals, IGNORE, rekey, "Send Ctrl-Alt-Del" for Telnet…). The backend publishes a **menu tree** of specials, and the Seat is told when it changes (`seat_update_specials_menu`) | per-backend context-menu actions |
| `connected()`, `exitcode()` | Liveness; exit status (`INT_MAX` = not yet / abnormal) | status |
| `sendok()` | "I want input now." **No backend returns true while still connecting**, so a proxy that prompts in the terminal doesn't race with the backend for keystrokes (`putty.h:720–730`) | input gating |
| `ldisc_option_state(opt)`, `provide_ldisc` | Whether the remote wants local echo/edit (Telnet ECHO, SSH no-pty) | rarely needed |
| `unthrottle(bufsize)` | The front end has drained its output backlog; resume reading | **read backpressure** |
| `cfg_info()` | Hint for the reconfig dialog (e.g. SSH protocol version) | — |
| `test_for_upstream()` | SSH only: "is there a sharing upstream for this config?" | connection reuse |
| `close_warn_text()` | SSH only: extra text for "really close?" (e.g. "this will kill 3 shared sessions") | close confirmation |
| `id`, `displayname_tc/lc`, `protocol`, `default_port`, `flags` | Metadata. Flags: `BACKEND_RESIZE_FORBIDDEN`, `NEEDS_TERMINAL`, `SUPPORTS_NC_HOST`, `NOTIFIES_SESSION_START` (`putty.h:582–588`) | capabilities |

Flow control runs **both ways through return values**:

- `seat_output()` returns the Seat's backlog. For a terminal, `term_data` returns
  `bufchain_size(&term->inbuf)` (`terminal.c:7884`). The backend then decides
  whether to shrink the SSH window.
- When the front end drains, it calls `backend_unthrottle()`.

For SSH this ties the terminal's parse rate to the SSH channel window
(`ssh/connection2.c:575–612`). A fast `cat` therefore cannot balloon memory: the
server just stops sending.

The backend list is chosen per binary at build time (`be_list.c`): PuTTY has
SSH+serial+others, PuTTYtel drops SSH, and pterm has only pty/conpty.

### 1.4 Seat in detail

The Seat (`putty.h:1088–1420`) is "where the session's user is". Its methods fall
into groups:

- **Data:** `output(type=stdout|stderr, data)` → backlog; `eof()`; `sent(bufsize)`;
  `banner(data)`. Banner is separate from output so intermediate seats (jump-host
  proxy) can route it differently.
- **Async prompts**, all returning `SeatPromptResult`:
  - `get_userpass_input(prompts_t*)`, `confirm_ssh_host_key(...)`,
    `confirm_weak_crypto_primitive(...)`, `confirm_weak_cached_hostkey(...)`.
  - `SeatPromptResult` (`putty.h:822–891`) has four kinds: `SPRK_INCOMPLETE` (answer
    comes later via callback), `SPRK_OK`, `SPRK_USER_ABORT` (no error message needed;
    the user knows), and `SPRK_SW_ABORT` (carries an error message, e.g. "batch mode,
    can't prompt").
  - A protocol coroutine calls the prompt. If the result is INCOMPLETE it parks on
    `crMaybeWaitUntilV(s->spr.kind != SPRK_INCOMPLETE)` (e.g.
    `ssh/transport2.c:1601`). The callback re-queues the layer (`ssh/common.c:754`).
  - The GUI therefore stays live while a host-key dialog is open, and rekeys and
    other channels keep running.
- **Lifecycle notifications:** `notify_session_started`, `notify_remote_exit`
  (the shell exited), `notify_remote_disconnect` (the *connection* ended; may differ
  when forwardings outlive the shell), `connection_fatal(msg)`, `nonfatal(msg)`.
- **Terminal facts for the backend:** `get_ttymode(mode)` (so SSH `pty-req` modes
  such as ERASE come from the terminal's backspace setting), `is_utf8`,
  `get_window_pixel_size`, `get_display`/`get_windowid` (for X11 forwarding),
  `get_cursor_position`.
- **Security UX:** `set_trust_status(bool)`, `can_set_trust_status()`,
  `stripctrl_new()` (a sanitiser for untrusted text such as banners and server
  prompt strings), and `has_mixed_input_stream()` (plink: are prompts and session
  input on the same stream?).
- **Misc:** `set_busy_status` (hourglass cursor during KEX), `update_specials_menu`,
  `echoedit_update`, `verbose`, `interactive`.

**`InteractionReadySeat`** (`putty.h:607`) is a wrapper type. Every prompting Seat
method takes it instead of a plain `Seat*`, and the only way to get one is
`interactor_announce()`. The type system thus guarantees that every prompt is
preceded by "which connection is asking" when proxies are involved (§5.6).

**TempSeat** (`utils/tempseat.c`): while a proxy (e.g. a jump host) is using the
real Seat for its own prompts, the main backend gets a TempSeat. It buffers output
and trust changes, then flushes them when the seat is returned
(`proxy/interactor.c:7–75`).

### 1.5 Ldisc and TermWin

- **Ldisc** (`ldisc.c`) sits between keyboard and backend:
  - It implements local echo and local line editing when the backend asks for them
    (Telnet, raw, SSH with no pty), using `terminal/lineedit.c`.
  - It **buffers input while `backend_sendok()` is false** (`ldisc.c:28–40`), so
    keystrokes typed during connection setup aren't lost or sent to a proxy prompt.
  - Input chunks are typed NORMAL / DEDICATED / NONINTERACTIVE. DEDICATED marks the
    real Return/Backspace keys, as opposed to Ctrl-M/Ctrl-H.
  - For SSH with a pty, ldisc is effectively a pass-through.
- **TermWin** (`putty.h:1606`) is everything the Terminal needs from a window:
  `setup_draw_ctx`/`draw_text`/`draw_cursor`/`draw_trust_sigil`/`free_draw_ctx`,
  `char_width`, `set_scrollbar`, `bell`, `clip_write`/`clip_request_paste`,
  `request_resize`, title, minimise/maximise/move/z-order, palette, `unthrottle`.
  Draw calls are bracketed by a draw context, so a GDI DC or a Cairo context is
  acquired once per paint.

### 1.6 End-to-end data flow

```
 NETWORK                                                     WINDOW
 ───────                                                     ──────
 socket ──(WSAAsyncSelect → WM_NETEVENT / select())──► Plug.receive (ssh.c:637)
     │                                                         │
     │   in_raw bufchain ── ic_in_raw (idempotent callback) ──►│
     ▼                                                         ▼
 BPP (bpp2.c: decrypt, MAC, decompress)  ──► in_pq ──► transport2 (KEX, rekey, filters <50)
                                                        │ pq_in_higher
                                                        ▼
                                                   userauth2 (until success, then
                                                        │       passes everything through)
                                                        ▼
                                                   connection2: channel demux,
                                                   window accounting
                                                        │ CHANNEL_DATA
                                                        ▼
                                                   mainchan (Channel) ── seat_output()
                                                                            │
 Seat (window.c win_seat_output) ── term_data() ── inbuf ── term_out(): parse,
   returns backlog ◄──────────────────────────────────────── update lines
                                                                            │
                                    term_schedule_update ── callback/20ms timer
                                                                            ▼
                                     do_paint: diff vs disptext ─► TermWin.draw_text
                                                                   (ExtTextOutW / Cairo / Xlib)

 KEYBOARD
 ────────
 WM_KEYDOWN/WM_CHAR ─► TranslateKey (window.c) ─► term_keyinput / ldisc_send()
   ─► [Ldisc: buffer if !sendok; local edit/echo if enabled]
   ─► backend_send() ─► connection2 → mainchan SshChannel write → out_pq
   ─► transport2 (held back during KEX) ─► BPP encrypt ─► out_raw ─► sk_write
```

On Windows the GUI event loop (`windows/window.c:805–875`) is a
`MsgWaitForMultipleObjects` over the handle list plus the message queue. Two
subtleties:

- The timeout drops to zero if a callback is pending.
- After each wait it drains Windows messages until it has seen at least one
  *non*-`WM_NETEVENT`, because Windows prioritises those and a flood would otherwise
  starve input (`windows/window.c:853–872`). Only then does it run one top-level
  callback.

This is how a single thread stays responsive under a flood: network reads only
queue work, the work runs in small callback slices, and paints are rate-limited.

---

## 2. SSH implementation architecture

### 2.1 Layers and how they are wired

`ssh_init` → `connect_to_host` (`ssh/ssh.c:778`):

1. **Try connection sharing first** (`ssh.c:789–804`). If an upstream exists, the
   "socket" is a pipe to it and the session runs in *bare* mode (§6.1).
2. Otherwise resolve the name and open a socket. This may go through a proxy
   (§6.4), which is invisible here because proxies are just Sockets.
3. Create the **version-string BPP** (`ssh/verstring.c`). It exchanges `SSH-2.0-…`
   lines, detects server bugs from the version string, and calls
   `ssh_got_ssh_version` (`ssh.c:177`).

`ssh_got_ssh_version` then **builds the stack top-down and links it bottom-up**
(`ssh.c:196–341`):

```
 ssh2_connection_new(...)          ← created first (needs nothing below it)
 ssh2_userauth_new(successor = connection)    (skipped if CONF_ssh_no_userauth)
 ssh2_transport_new(higher_layer = userauth)
 ssh2_bpp_new()                    ← replaces the verstring BPP
 base_layer = transport; its queues = bpp->in_pq / out_pq
```

Each PPL (`ssh/ppl.h`) has:

- `in_pq` and `out_pq` (packet queues);
- `ic_process_queue`, an idempotent callback wired so that **pushing a packet onto
  `in_pq` schedules `process_queue`** (`ssh/common.c:32–43`);
- `selfptr`, so a layer can **replace itself** (`ssh_ppl_replace`). Userauth uses
  this to hand over to the connection layer when done. **Inference** from the API
  comment at `ppl.h:85`;
- vtable methods `process_queue`, `get_specials`, `special_cmd`, `reconfigure`,
  `queued_data_size`, `final_output`.

The **transport layer owns the layer above it** (`transport2.c:121–129`). It gives
the higher layer a private pair of queues (`pq_in_higher`, `pq_out_higher`):

- **Incoming:** `ssh2_transport_filter_queue` (`transport2.c:430–495`) moves packets
  with type ≥ 50 to `pq_in_higher`. Before the first NEWKEYS it rejects them as a
  protocol error.
- **Outgoing:** higher-layer packets wait in `pq_out_higher` and are spliced onto
  the real `out_pq` only when no key exchange is running
  (`transport2.c:1855`, `:1995`). **A rekey therefore needs no cooperation from
  channels.** They keep queueing, and their data flows when the new keys are
  active.

The **BPP** (`ssh/bpp.h`) owns `in_raw`/`out_raw` byte buffers and the packet
queues. Its `handle_input` is itself a coroutine (`bpp2.c:287`). It reads with
`BPP_READ` = `crMaybeWaitUntilV(bufchain_try_fetch_consume(...))` (`bpp2.c:274`),
so partial packets simply suspend it.

- On NEWKEYS it **suspends input processing** until the transport layer has
  installed the new incoming cipher (`bpp2.c:626–637`). That is a deliberate,
  commented layer violation.
- It also enforces the strict-KEX ("Terrapin") rules about which packets may
  appear when.

### 2.2 Coroutines

`sshcr.h` implements stackless coroutines with Duff's-device `switch`/`case
__LINE__` macros. `crBegin(s->crState)` … `crReturnV` … `crFinishV`. The useful
variant is `crMaybeWaitUntilV(cond)`, which tests the condition first and only
yields if it's false (`sshcr.h:56–80`).

- Locals do not survive a yield, so all state lives in the layer struct
  (`doc/udp.but:335`).
- A coroutine may be abandoned at any yield point, so cleanup functions must free
  whatever is non-NULL (`udp.but:357–372`).

The heaviest users are `userauth2-client.c` (29 yields), `login1.c` (20),
`transport2.c` (13) and `kex2-client.c` (8). Connection-layer code is ordinary
event-driven code, since channel multiplexing doesn't suit a linear script.

**Why this matters for puritty.** Login and key exchange are naturally sequential
scripts ("send KEXINIT, wait for KEXINIT, wait for user to approve host key, send
…"). Written as coroutines or async functions, they stay readable while running on
a single non-blocking event loop. In a language with async/await or green threads,
use those. The structural point is that **every wait, including waiting for a user
dialog, is a yield.** Nothing blocks the loop.

### 2.3 The event model and staying responsive

- **One thread, three event sources:** OS readiness (sockets/handles), timers
  (`timing.c`, one sorted list, `schedule_timer` returns an absolute tick), and the
  top-level callback queue.
- **Idempotent callbacks** (`callback.c:36`) are the key primitive. "Something was
  added to queue X" schedules X's consumer once, however many items were added.
  Every packet queue and the BPP raw-input buffer use one.
- **Re-entrancy avoidance:** deep code never calls back up synchronously. It queues
  a callback instead (`putty.h:2680–2700`). For example, `win_seat_connection_fatal`
  queues `close_session` rather than freeing the backend mid-stack
  (`windows/window.c:1176–1190`).
- **Backpressure everywhere:**
  - SSH socket input freezes when `in_raw` exceeds `SSH_MAX_BACKLOG` (32 KiB) or a
    layer asks for it (`ssh.c:344–360`).
  - Socket output throttles every channel when `sk_write` reports a large backlog
    (`ssh.c:386`).
  - Per-channel windows: the default is 16 KiB, **grown dynamically** by 16 KiB
    whenever the server exhausts it while unthrottled, up to 1 GiB
    (`connection2.c:588–596`).
  - In "simple" mode (one channel, no sharing) the window is advertised as
    `0x7fffffff` (`ssh.h:31,48`).
  - `WINDOW_ADJUST` is sent only when at least half the window is free
    (`connection2.c:945–950`), and is paired with a `winadj@putty.projects.tartarus.org`
    request to measure the real window.
- **Pipelined channel setup:** `mainchan` sends X11-forwarding, agent-forwarding,
  `pty-req`, every `env`, and `shell`/`exec` back to back, each with want-reply. It
  then processes the replies in order (`ssh/mainchan.c:146–199`). There is one round
  trip, not five. A fallback command (`CONF_remote_cmd2`) is tried if the primary
  fails (`mainchan.c:208`).

### 2.4 SSH-1 vs SSH-2

SSH-1 is still present: `bpp1.c`, `login1.c`, `connection1*.c`, the CRC-attack
detector, and SSH-1 RSA keys. The default is SSH-2 only (`conf.h:248–270`, default
`3`). The old "SSH-2 with fallback to SSH-1" modes were removed, so a downgrade
attack isn't possible. The PPL abstraction was designed to cover "the three SSH-2
layers and both SSH-1 phases" (`ppl.h:1–4`). puritty should not implement SSH-1.

### 2.5 The same code as a server

`ssh/server.c`, `kex2-server.c`, `userauth2-server.c`, `connection2-server.c`,
`sesschan.c` and `sftpserver.c` reuse the BPPs and layer framework. Two programs use
them:

- **Uppity** (`unix/uppity.c`), a test SSH server.
- **psusan** (`unix/psusan.c`), a bare ssh-connection server meant to run over any
  byte pipe, e.g. a serial line or `docker exec`, giving SSH channel multiplexing
  with no crypto.

Running client and server from one codebase makes end-to-end protocol tests
practical. A puritty SSH client needs some equivalent fake server for tests.

---

## 3. Crypto and protocol features

PuTTY implements **all of its own crypto** in `crypto/`: AES with AES-NI/NEON
back-ends, ChaCha20-Poly1305, curve25519/448, NIST curves, ML-KEM, NTRU Prime, RSA,
mp_int, Argon2. puritty should not copy that; use a vetted library. The
*negotiation policy and UX* around the crypto are still worth studying.

### 3.1 Algorithms

| Category | Supported (default order first) | Where |
|---|---|---|
| KEX, post-quantum hybrids | `sntrup761x25519-sha512` (+`@openssh.com` alias), `mlkem768x25519-sha256`, `mlkem768nistp256-sha256`, `mlkem1024nistp384-sha384` | `crypto/kex-hybrid.c:300–400` |
| KEX, classical | `curve25519-sha256`, `curve448-sha512`, `ecdh-sha2-nistp256/384/521`, DH group-exchange sha256/sha1, DH groups 14–18, `rsa2048-sha256`, `rsa1024-sha1`, ⚠ `diffie-hellman-group1-sha1` | `crypto/ecc-ssh.c:1625–1702`, `crypto/diffie-hellman.c:79–212`, `crypto/rsa.c:1169` |
| KEX, GSSAPI | `gss-group14..18-*`, gex and ECDH variants keyed by Kerberos OID hash | `crypto/diffie-hellman.c:227–295`, `ssh/kex2-client.c:250–342` |
| Host keys | `ssh-ed25519`, `ssh-ed448`, `ecdsa-sha2-nistp*`, `rsa-sha2-512/256`, `ssh-rsa`, `ssh-dss`, and all `*-cert-v01@openssh.com` | `crypto/openssh-certs.c:250–279`, default order `settings.c:935` |
| Ciphers | AES-CTR/CBC 128/192/256, `aes128/256-gcm@openssh.com`, `chacha20-poly1305@openssh.com`; ⚠ 3DES, DES, Blowfish, Arcfour | `crypto/aes-select.c:62–71`, defaults `settings.c:17–26` |
| MACs | `hmac-sha2-512/256`, `hmac-sha1`, `-96`, `md5`, each with `-etm@openssh.com` | `crypto/hmac.c:178–281` |
| Compression | `zlib`, delayed `zlib@openssh.com` (own deflate) | `ssh/zlib.c` |
| Extensions | `ext-info-c` + `server-sig-algs` (picks RSA SHA-2), strict KEX `kex-strict-c-v00@openssh.com` | `ssh/transport2.c:30–35, 371–400` |

The hybrid KEX is generic: `{combining hash, PQ KEM, classical KEX}`. The wire format
reuses the ECDH message shape with concatenated values (`crypto/kex-hybrid.c:1–30`),
so any KEM pairs with any classical exchange.

### 3.2 Preference lists with a "WARN below here" line

Every algorithm preference list (KEX, host key, cipher, GSS-KEX) is user-orderable
and contains a **`WARN` sentinel**. If negotiation ends up choosing something below
it, the user is asked first, separately for KEX, host-key type, and each cipher
direction (`ssh/transport2.c:1596–1680`). Consent is remembered for the session, so
each algorithm is asked about once (`transport2.c:156, 2527–2536`).

**Settings migration** is a detail worth copying. Each algorithm table entry says
*where to insert it relative to another entry* if a saved list predates it
(`putty.h:517–556`). New algorithms (ML-KEM, ed448) therefore slot sensibly into
users' customised lists, and untouched old defaults get silently upgraded
(`settings.c:888–931`). An app that persists user crypto preferences must solve this
somehow; this is a clean way.

### 3.3 Rekeying

- Rekeys happen after **60 minutes** or **1 GB** in either direction
  (`conf.h:204–213`). The timer fires 30 s early so the two limits don't race
  (`transport2.c:2085–2103`).
- Rekeys also happen on user request (Specials menu), on server KEXINIT, after
  GSSAPI credential renewal (to re-delegate), and once right after auth to populate
  the transient host-key cache when GSS-KEX was used (`transport2.c:2017–2035`).
- Servers with the `BUG_SSH2_REKEY` flag are never rekeyed (`transport2.c:2050–2068`).
- **A rekey never prompts.** The host key must byte-match the first exchange, or the
  connection aborts with "Host key was different in repeat key exchange"
  (`ssh/kex2-client.c:1031–1052`).
- As described in §2.1, channels need not know a rekey is happening.

### 3.4 Terrapin (CVE-2023-48795)

Strict KEX is implemented in both the BPP and the transport layer. If the negotiated
combination is vulnerable (ChaCha20-Poly1305, or CBC+EtM, without strict KEX),
PuTTY:

1. Logs it.
2. **Re-runs negotiation against a modified Conf to see whether reordering
   preferences would have avoided it** (`try_to_avoid_terrapin`,
   `transport2.c:2607+`).
3. Warns with one of two wordings: "vulnerable" or "vulnerable, but you could avoid
   it by moving X down" (`ssh/common.c:1108–1130`, `ssh.h:2101`).

This is a good model for actionable security warnings.

### 3.5 GSSAPI / Kerberos

- **Libraries:** on Windows, SSPI (`secur32.dll`), MIT KfW, or a user-specified DLL
  (`windows/gss.c:38–48, 208–228`). On Unix, dlopen of Heimdal or MIT
  (`unix/gss.c:13–76`).
- **Mechanisms:** `gssapi-keyex` (GSS KEX), `gssapi-with-mic` auth, and credential
  delegation. Credentials are polled every 2 minutes, and a rekey re-delegates them
  when they change (`ssh/gss.h:40`, `transport2.c:2106–2121`).
- **Host keys under GSS-KEX:** they are never written to the persistent cache. A
  per-session **transient host key cache** (`ssh/transient-hostkey-cache.c`) lets
  later non-GSS rekeys accept only keys already vouched for in that session.

Windows corporate users do use this. It is not a v1 feature for puritty, but keep
the auth-method list extensible.

---

## 4. Host key verification

### 4.1 Flow (`verify_ssh_host_key`, `ssh/common.c:859–1078`)

1. **Manually configured host keys** (`CONF_ssh_manual_hostkeys`, fingerprints or
   base64 blobs; `-hostkey` on the command line) *replace* the cache entirely. A
   match connects. Anything else is a **hard abort with no prompt**
   (`common.c:865–917`).
2. **Certificates:** if the key is an OpenSSH host certificate and a configured CA
   matches this host (§4.3), it is validated. Success connects. If validation fails,
   PuTTY falls back to the cache ("Accepting certified host key anyway based on
   cache").
3. **Cache lookup** returns match / absent / mismatch (`common.c:922–924`).
4. Otherwise PuTTY builds a **structured, front-end-neutral dialog**
   (`SeatDialogText`). Its items are typed: `SDT_TITLE`, `SDT_SCARY_HEADING`,
   `SDT_PARA`, `SDT_DISPLAY` (fingerprint), `SDT_BATCH_ABORT` (where batch mode
   stops), `SDT_PROMPT`, `SDT_MORE_INFO_*`. It then calls
   `seat_confirm_ssh_host_key`. Each Seat renders the dialog in its own way:
   - The Windows GUI shows a modal dialog with **Accept / Connect Once / Cancel**
     (`windows/dialog.c:1181–1213`).
   - GTK shows a **non-modal** dialog and returns `SPRK_INCOMPLETE`
     (`unix/dialog.c:3700–3720`).
   - The console prints the text and asks y/n, with Return meaning cancel
     (`console.c:17–20`).
   - plink `-batch` prints the text up to `SDT_BATCH_ABORT`, then "Connection
     abandoned".

| Case | Heading | Choices | Default/safe |
|---|---|---|---|
| Unknown host | "PuTTY Security Alert"-style text, fingerprint, "store key in cache?" | Accept (store + connect), Connect Once, Cancel | — |
| **Mismatch** | "WARNING - POTENTIAL SECURITY BREACH!" (`common.c:1003`) | same three; text says "Cancel is the ONLY guaranteed safe choice" (`common.c:1061`) | Cancel |
| Cert signed by unknown CA / cert + mismatch | separate, scarier wording (`common.c:945–993`) | same | Cancel |
| Weak host key type chosen because it's the cached one | `confirm_weak_cached_hostkey`, listing better types the server offers (`transport2.c:1607–1655`) | continue / abort | — |

- **"More info"** shows the SHA256 and MD5 fingerprints and the full OpenSSH-format
  public key (`common.c:1065–1078`). SHA256 is the displayed default (`ssh.h:1741`).
- The Event Log records fingerprints, certificate IDs and CA names
  (`kex2-client.c:897–935`).
- **PreferKnownHostKeys** (default on): in the first KEX, PuTTY reorders host-key
  algorithms to prefer types it has cached for this host. Adding an ed25519 key on
  the server therefore doesn't make every client see an "unknown key" prompt.
- **Cross-certification:** when the server offers key types PuTTY hasn't cached,
  the Specials menu offers "Cache new host key type: …". This triggers a rekey with
  that algorithm *inside the already-authenticated session*, then stores the result
  (`transport2.c:2385–2408`, `kex2-client.c:1012–1030`). This is a safe key-rotation
  path. OpenSSH does the same automatically with `hostkeys-00@openssh.com`
  (UpdateHostKeys); **PuTTY does not implement that extension** (**inference**: no
  grep hits).

### 4.2 Storage

| Platform | Location | Format |
|---|---|---|
| Windows | `HKCU\Software\SimonTatham\PuTTY\SshHostKeys` (`windows/storage.c:284`) | value name `keytype@port:host`, value = PuTTY-specific key string (hex bignums / curve points) |
| Unix | `~/.putty/sshhostkeys` (or XDG) | one line `type@port:host keydata`, rewritten via temp file + rename (`unix/storage.c:765–870`) |

**PuTTY does not read or write OpenSSH `known_hosts`.** Users convert with
`contrib/kh2reg.py` (FAQ, `doc/faq.but:172–176`). This is the biggest interop wart
for people who use both PuTTY and the Windows OpenSSH client. synthesis §10 already
recommends using `%USERPROFILE%\.ssh\known_hosts`, and PuTTY confirms why.

### 4.3 Certificate authorities

- Host CAs are named records `{name, public key, validity expression, options}`
  (`storage.h:105–118`), stored in `…\SshHostCAs` or `~/.putty/sshhostcas`, and
  edited in a dedicated dialog.
- The validity expression is a tiny boolean language
  (`utils/cert-expr.c:1–60`):
  - Hostname wildcards and `port:N[-M]`, combined with `&&`, `||`, `!` and
    parentheses.
  - **Mixing `&&` and `||` without parentheses is a syntax error**, to avoid
    precedence mistakes.
- Cert host-key algorithms are offered in KEXINIT **only if some CA's expression
  matches this host**, which avoids a pointless cert negotiation
  (`transport2.c:719–760`).
- The dialog warns that caching a certified key does **not** make its CA trusted
  (`common.c:1029–1034`).
- User certificates are supported as a "detached certificate" file next to the key.

---

## 5. Authentication

### 5.1 Method order (`ssh/userauth2-client.c`)

1. Optional **auth plugin** start-up (may supply the username; `:669–719`).
2. Query the agent for its key list (`:577–660`).
3. `none` (learn the allowed methods; `:801`).
4. `gssapi-keyex` → agent keys → key file → `gssapi-with-mic` →
   `keyboard-interactive` → `password`, including the server-requested password
   change loop (`:990–2000`).
5. "Further authentication required" (partial success) is handled.

Details that matter for UX:

- **Agent vs key file** (`:625–655`): if a key file is configured and its key is in
  the agent, *only that* agent key is tried. If not, no agent keys are tried. This
  avoids "Too many authentication failures" on servers with `MaxAuthTries`.
- **The public key is offered before the passphrase is asked for** (`:1158–1175`).
  PPK stores the public half in cleartext for exactly this reason. The user is only
  prompted for a passphrase if the server would accept that key.
- A wrong passphrase re-prompts. Passphrase buffers are wiped (`smemclr`).
- Username: if not configured, the user is prompted "login as:" in the terminal.
  `change_username` allows trying a different user after failure.

### 5.2 Key files: PPK and import

- The client loads **only PPK** (or a public-key file for agent use). **OpenSSH
  private keys are rejected** with "Unable to use key file" (`userauth2-client.c:474–505`).
  Users must convert them in PuTTYgen (`import.c` reads OpenSSH PEM, OpenSSH new
  format and ssh.com). This is notorious friction; puritty should read
  `~/.ssh/id_*` directly.
- **PPK v3** (`sshpubk.c:729–845`, `doc/pubkeyfmt.but`):
  - The passphrase key comes from Argon2id, with memory/passes/parallelism stored in
    the header and passes auto-tuned to a target time.
  - The cipher is AES-256-CBC.
  - The HMAC covers public key, comment and encrypted private part, which defeats
    key-substitution attacks.

### 5.3 Agents

- **Windows client** (`windows/agent-client.c`):
  1. First a **named pipe** `\\.\pipe\pageant.<user>.<sha256(CryptProtectMemory("Pageant"))>`.
     The name is per user and unguessable by others
     (`windows/utils/agent_named_pipe_name.c:9–17`).
  2. Then the legacy **WM_COPYDATA** to window class "Pageant", with the request in
     a shared file mapping `PageantRequest%08x`. Pageant checks that the mapping's
     owner SID is the user's (`windows/pageant.c:1080–1120`).
- **The client does not talk to the Windows OpenSSH agent** (`\\.\pipe\openssh-ssh-agent`;
  no grep hits). The reverse works: `pageant --openssh-config FILE` writes an
  `IdentityAgent` line so Windows OpenSSH can use Pageant (`windows/pageant.c:1513,
  1714–1724`).
- **Unix client:** `SSH_AUTH_SOCK`.
- **Pageant** (`pageant.c`) can hold encrypted keys and decrypt them on first use. It
  adds PuTTY extensions (`list-extended`, `add-ppk`, `reencrypt`). There is no
  per-use confirmation (**unverified**; not found).
- **Agent forwarding:** `auth-agent-req@openssh.com`, requested only if enabled and
  an agent exists (`connection2.c:1610`). `ssh/agentf.c` relays each forwarded
  request asynchronously to the local agent, and synthesises `SSH_AGENT_FAILURE` if
  the agent gives no reply.

puritty on Windows should try, in order, the OpenSSH agent pipe and the Pageant pipe
(plus WM_COPYDATA for old Pageants). Both speak the standard agent protocol.

### 5.4 Auth plugins

`doc/authplugin.but` defines a local IPC protocol (SSH-style marshalling,
half-duplex) for an external helper that answers keyboard-interactive prompts (OTP,
web SSO) and can pick the username. This is a neat extension point for enterprise
2FA without baking each vendor into the client.

### 5.5 Anti-spoofing: the most important security UX lesson

The threat: a malicious or compromised server prints text that *looks like* the
client's own UI ("Host key changed, enter passphrase:", "Access granted"). The user
then hands over a secret, or believes they're on a safe host. Because PuTTY renders
both its own prompts *and* server output in the same terminal, it built layered
defences:

1. **Trust sigil** (§8.8):
   - Text generated by PuTTY is written while `seat_set_trust_status(true)`.
   - Those lines carry a `trusted` bit and reserve `TRUST_SIGIL_WIDTH` = 3 columns
     (`terminal/terminal.h:16`), where the front end draws the PuTTY icon
     (Windows `DrawIconEx`, `windows/window.c:4043–4054`).
   - Switching trust clears the current line.
   - The server has no byte sequence that can produce the sigil.
2. **Framing server text:**
   - The pre-auth banner is wrapped in trusted lines "Pre-authentication banner
     message from server:" / "End of banner message from server", with trust off in
     between (`userauth2-client.c:2071–2100`).
   - Keyboard-interactive prompts get "Keyboard-interactive authentication prompts
     from server:" … "End of keyboard-interactive prompts from server"
     (`:2154–2177`).
   - Every prompt records `from_server` (`putty.h:925–935`).
3. **Sanitising:**
   - Banners and server prompt strings pass through `StripCtrlChars` (via
     `seat_stripctrl_new`), which removes escape sequences and bounds line length.
   - Banners are capped at 128 KiB (`userauth2-client.c:19`).
   - Banners can be turned off.
4. **Where the front end can't draw a sigil** (plink on a console):
   - `seat_antispoof_msg` pads PuTTY's own header lines to a 78-column
     `-- msg -----` format the server can't reproduce in-line (`utils/antispoof.c`).
   - After auth, plink requires "**Access granted. Press Return to begin
     session.**" (`connection2.c:1007–1030`). Server-printed fake prompts therefore
     can't appear before the user knows the real session has begun.
   - The prompt is skipped when stdin isn't the console (`has_mixed_input_stream`).
   - It lives in the connection layer, so sharing downstreams get it too.
5. **`SshNoTrivialAuth`:** abort if the server "authenticates" you without any
   password, signature or KI response (`userauth2-client.c:1795, 2042–2045`). That
   blocks the "let them straight in, then show a fake passphrase prompt in the
   session" attack (`doc/config.but:2950–2990`).
6. **Interactor announcements for proxies** (§6.4): "Making proxy SSH connection to
   jumphost…" printed as trusted text, so the user knows which hop wants which
   password.

**For puritty:** embedded-SSH prompts on Windows should be **out-of-band UI** (a
pane overlay or dialog drawn by the app, never by VT text). That gives the trust
distinction structurally. If prompts are rendered in-terminal for keyboard flow,
adopt PuTTY's per-line trust bit plus an unforgeable margin glyph. Either way, frame
and sanitise server-supplied banner and KI text.

---

## 6. Connection sharing, forwarding, proxies

### 6.1 Connection sharing (upstream/downstream)

The design is documented at length in `ssh/sharing.c:1–126`.

- **Roles:** the first PuTTY with sharing enabled for a given `user@host[:port]`
  becomes the **upstream**. It owns the real TCP connection, all crypto, and the
  real auth. Later PuTTYs become **downstreams** and never touch the network.
- **Rendezvous:**
  - The name is `user@host` or `user@host:port` (`sharing.c:1987–2010`).
  - On Windows it is obfuscated to a SHA-256 of `CryptProtectMemory(…,
    CROSS_PROCESS)` output, so other users can't learn where you connect or the
    hostname length (`windows/utils/cryptoapi.c:29–80`).
  - A named mutex is taken while choosing a role: first try to connect as
    downstream, else create the listening pipe as upstream (`windows/sharing.c:31–109`).
  - The pipe gets a private DACL and `PIPE_REJECT_REMOTE_CLIENTS`
    (`windows/named-pipe-server.c:82–87, 211`).
  - On Unix the socket lives in `/tmp/putty-connshare.<user>/`, in a directory whose
    ownership and mode are checked (`unix/sharing.c:22–67, 267`).
- **Wire protocol:**
  - A version line `SSHCONNECTION@putty.projects.tartarus.org-2.0-…`, then
    `uint32 len, byte[len]` packets.
  - The packets are plain SSH *connection-protocol* messages, as if userauth had
    already finished, with no rekeying and a 16400-byte cap.
  - A downstream is literally the ordinary SSH backend in **bare-connection mode**
    (`ssh.c:805–821`, `bpp-bare.c`). The same code also implements the `PROT_SSHCONN`
    protocol used with psusan.
- **Channel-number NAT:** the upstream rewrites downstream channel IDs into its own
  ID space and routes server replies back. Global requests are accepted from
  downstreams only for remote port forwarding.
- **X11:** a server-initiated `x11` channel open doesn't say which session asked for
  it. The upstream therefore gives each downstream's X11 request **distinct fake
  auth data** and waits to read the X11 setup packet before deciding where to route
  the channel. Downstreams must confirm `x11` opens with a window of at least 256.
- **Agent forwarding** can't be demultiplexed, so all downstreams get the upstream's
  agent.
- **Lifetime:** the upstream stays alive while any downstream exists, even after its
  own shell exits (`connection2.c:1286–1298`). `close_warn_text` warns when closing
  an upstream window would kill downstreams (`ssh.c:721`). There is **no detached
  master process on Windows**: the upstream is a visible PuTTY window.
- Sharing turns off "simple" mode, because the big single-channel window would be
  wrong (`ssh.c:201–209`).

For puritty on Windows, all tabs live in one process. Sharing becomes **in-process
channel multiplexing**: one SSH connection object, many session channels, which is
simpler. PuTTY's cross-process design is worth copying only if puritty also wants
CLI tools (an scp-like helper, a `puritty ssh` subcommand) to piggyback on an open
GUI connection.

### 6.2 Port forwarding

`ssh/portfwd.c` covers local (`-L`), remote (`-R`) and **dynamic SOCKS 4/4A/5**
(`-D`, with an in-file SOCKS state machine at `portfwd.c:15–24`). Forwardings can
be added or removed mid-session through reconfiguration. Remote forwarding requests
from sharing downstreams are tracked per downstream.

### 6.3 X11 forwarding

PuTTY does **X auth spoofing** (`ssh/x11fwd.c`):

- The remote side gets *fake* `MIT-MAGIC-COOKIE-1` or `XDM-AUTHORIZATION-1`
  credentials (`x11_invent_fake_auth`, `:47`).
- Incoming X connections are checked against them (`x11_verify`, `:171`). The XDM
  variant also checks the timestamp and keeps a replay cache.
- The real local credentials, read from `.Xauthority` (`utils/x11authfile.c`), are
  substituted before forwarding to the local X server.

So the server never learns your real X cookie. On Windows the "local X server" is
VcXsrv/Xming, reached over TCP.

### 6.4 Proxies (`proxy/`)

Proxy types (`putty.h:415–418`): SOCKS4, SOCKS5, HTTP CONNECT, Telnet (a scripted
"proxy command" string sent over a TCP connection), local command (`PROXY_CMD`,
like OpenSSH `ProxyCommand`), and three SSH flavours: `PROXY_SSH_TCPIP`
(`direct-tcpip`, like `ProxyJump`), `PROXY_SSH_EXEC` and `PROXY_SSH_SUBSYSTEM`.

- Proxies are **Sockets wrapping Sockets**, so every backend gets them for free.
  The design rule forbids putting proxy logic in `ssh.c` (`doc/udp.but:121–126`).
- **The SSH jump host** (`proxy/sshproxy.c`) is the elegant part:
  - `SshProxy` *is a Socket* to the outer connection and *is a Seat* to an inner,
    complete `ssh_backend` instance.
  - Inner channel output (`seat_output`) becomes socket data for the outer SSH
    stack.
  - Inner prompts are forwarded to the real user Seat via
    `interactor_borrow_seat`.
- The jump host can be **a saved session name** (`sshproxy.c:617–637`). It then
  brings its own keys, user and even its own proxy, so chains nest to any depth.
- The inner connection never becomes a sharing upstream, and X11/agent/port
  forwardings are stripped from it. It *may* be a downstream, so a jump host already
  open in another window gets reused (`sshproxy.c:672–685`).
- **Interactor announcement** (`proxy/interactor.c:72–115`):
  - When control of the Seat passes between hops, PuTTY prints "Making primary SSH
    connection to …" or "Making proxy SSH connection to …" (`proxy^2` for nested).
  - The announcement goes through `seat_antispoof_msg`, so it is trusted text. The
    user always knows which host is asking for a password.

---

## 7. Keepalives, network errors, "Restart Session"

- **Application keepalives** (`pinger.c`) call `backend_special(SS_PING)` every
  `CONF_ping_interval` seconds.
  - For SSH-2 this sends `SSH_MSG_IGNORE` (`connection2.c:1648–1653`), unless the
    server is flagged `BUG_CHOKES_ON_SSH2_IGNORE`.
  - IGNORE gets no reply, so **PuTTY never detects a silently dead peer** at the
    application level. It keeps NAT/firewall state warm, and TCP eventually fails a
    write.
  - OpenSSH's `ServerAliveInterval` sends `keepalive@openssh.com` global requests
    and disconnects after N unanswered ones. That is what a laptop-sleep-friendly
    client needs.
  - `doc/config.but:1727–1748` frankly admits keepalives can make transient outages
    *worse*, because a send during a break makes TCP give up.
  - TCP `SO_KEEPALIVE` is a separate opt-in (`windows/network.c:953`).
- **Errors:**
  - Socket closure arrives as `Plug.closing(type, msg)` with `PLUGCLOSE_NORMAL /
    ERROR / BROKEN_PIPE / USER_ABORT` (`network.h:55–127`).
  - The SSH code separates `ssh_remote_error`, `ssh_remote_eof`, `ssh_proto_error`,
    `ssh_sw_abort` and `ssh_user_close` (`ssh.c:472–583`). These map to different
    user messages, and only some are worth a dialog.
  - The Windows seat shows a modal "PuTTY Fatal Error" box (`window.c:1179–1190`).
- **Session end UX:**
  - "Close window on exit" is Always / Never / Only on clean exit
    (`window.c:2104–2116`).
  - When the window stays open, `close_session` (`window.c:342`) frees the backend
    and ldisc, retitles the window "PuTTY (inactive)", and **inserts "Restart
    Session" into the context menu** (`window.c:367–373`).
  - Restart (`window.c:2347–2353`) logs "----- Session restarted -----" to the
    Event Log, calls `term_pwron(term, false)`, which resets terminal modes but keeps
    the screen and scrollback, and calls `start_backend` again with the same Conf.
  - There is **no automatic reconnect** and no session resumption. The remote shell
    is gone.
  - The modal fatal-error MessageBox also blocks interaction with the window until
    dismissed. Users dislike this.

For puritty: detect dead connections with replying keepalives, show the
disconnected state *in the pane* (not modally), keep scrollback, offer
one-key reconnect, and with tmux `-CC` make reconnect re-attach.

---

## 8. Terminal emulation (`terminal/terminal.c`)

### 8.1 Shape

- `Terminal` (`terminal/terminal.h:86–451`) is a single struct driven by
  `term_data()` (`terminal.c:7884`). That function appends to `inbuf`, runs
  `term_out()` (guarded against re-entry, `:7875`), and returns the backlog.
- Front-end drawing goes entirely through TermWin, which makes the terminal
  testable headless (§11).
- Two things deliberately stop parsing:
  - While the user is drag-selecting, `term_out` pauses (`:3726`) so the screen
    holds still. Backpressure then reaches the backend.
  - While a **remote-initiated resize** (`CSI 8;h;w t`) is pending
    (`win_resize_pending`, `terminal.h:408–438`), parsing pauses (`:3772`) until the
    window confirms (`term_resize_request_completed`, `:2377`). Following output is
    then interpreted at the new size. The same pattern applies to tmux
    `refresh-client` round trips.
- Compatibility levels: a `CL_*` bitmask drops sequences outside the emulated VT
  level (`terminal.c:10–48`). The parser includes a full VT52 mode and SCO
  sequences.

### 8.2 Parser and supported sequences

The parser is a hand-written switch on `termstate` (`terminal.h:201–217`). It is not
a table-driven DEC/vte parser.

- CSI accepts up to 32 parameters, saturating rather than overflowing. **Colon
  sub-parameters are not parsed** (**inference**), so `38:2::r:g:b` and `4:3`
  undercurl don't work.
- OSC strings are capped at 2048 bytes (`terminal.h:192`). **CR, LF or a stray ESC
  aborts an OSC**, so a broken sequence can't swallow the session (`:5335–5368`).
- **DCS, SOS, PM and APC are swallowed and ignored** (`:4140–4151`). There is no
  tmux control mode, no sixel, no XTGETTCAP, no DECRQSS.
- DEC modes (`toggle_mode`, `:3068`): the usual cursor/screen modes, alt screen
  47/1047/1048/1049, mouse 1000/1002/1003/1006/1015, **2004 bracketed paste**.
  Missing: 1004 focus, 1016 SGR-pixel, **2026 synchronized output**, DECRQM.
- SGR: bold, dim, underline, blink, reverse, strike, 256-colour and truecolour
  (semicolon form). **No italics**, no coloured or curly underline, no overline.
- OSC (`do_osc`, `:3204`): titles 0/1/2/21, OSC 4 query only, and PuTTY-specific
  `ESC ] P` (Linux palette) and `ESC ] W` (word-char table). **No OSC 7, 8, 52, 10/11/12
  or 133.**
- `CSI t` window ops are supported. Each is individually disableable, and title
  *reporting* returns an empty string by default (`settings.c:945–958`). The attack
  is to set the title to a command, query it, and have it typed back as keystrokes
  (`doc/config.but:883`).
- DA replies `ESC[?6c`. DA2 replies `ESC[>0;136;0c`, "so VIM can use drag messages"
  (`:4395`).

### 8.3 Cells, lines, scrollback

- `termchar` (`terminal.h:26–48`) holds a 32-bit codepoint, an attribute word (9-bit
  fg/bg palette indices plus style bits, `putty.h:211–275`), a truecolour fg/bg pair,
  and `cc_next`.
  - `cc_next` is a *relative index* to a combining-character chain stored past the
    visible columns of the same line, with a free list (`add_cc`, `:215`).
  - Combining characters per cell are capped at 32 (`CC_LIMIT`, `terminal.h:494`) to
    stop memory DoS.
- The right half of a wide char is the sentinel `UCSWIDE` (0xDFFF).
- `termline` carries line attributes (double width/height, `LATTR_WRAPPED`,
  `WRAPPED2` for a wide char pushed to the next line) and a **`trusted` flag**.
- Screen, alt screen and scrollback are counted 2-3-4 trees (`tree234`), giving
  O(log n) line indexing.
- **Scrollback is compressed per line** (`:700–1010`):
  - Four RLE streams (chars, attrs, truecolour, combining chars) with varint
    headers.
  - Lines are decompressed on demand by `lineptr()` (`:1185`).
  - The rationale is that scrollback is huge and rarely touched, so new cell
    features should cost memory only when used.
  - The limit is a line count (`savelines`).

### 8.4 Unicode, width, bidi

- Width comes from Markus Kuhn's `mk_wcwidth`/`mk_wcwidth_cjk` (ambiguous-wide is a
  setting), with tables regenerated from UCD 16.0 (`unicode/read_ucd.py`).
- **There is no grapheme clustering.** Width-0 codepoints attach as combiners to
  the previous cell, and ZWJ/VS16 get no special handling (**inference**). The one
  special case: regional-indicator pairs are drawn as one wide flag at paint time
  (`:6336–6356`).
- A wide char at the last column wraps, padding and setting `WRAPPED2`, or becomes
  U+FFFD if there's no room.
- **Bidi** (`bidi.c`, UAX#9 rev 46, passes the Unicode 15 conformance tests) plus
  Arabic shaping is a **display-time per-line transform**. It is cached per row with
  forward and backward permutations so the cursor and selection can be mapped
  (`:5785–6010`). Logical storage stays untouched.

### 8.5 Repaint: damage-limited by design

This was built for slow GDI and X11 links, and it is the part most relevant to
puritty's remote-X11 renderer.

1. **Coalescing** (`terminal.c:1291–1349`):
   - A state change calls `term_schedule_update`, which queues one top-level
     callback.
   - After each paint a **20 ms cooldown timer** (`UPDATE_DELAY`, `:40`) starts.
     Changes during the cooldown set `window_update_pending`, and the timer paints
     them.
   - The result is at most about 50 paints/s, and each one reflects *all* output
     parsed since the previous paint.
   - The same timer drives text blink, cursor blink and the visual bell.
2. **Shadow screen:** `term->disptext` (`terminal.h:97`) is what the window
   currently shows. `do_paint` (`:6039`) builds each row as it *should* look, with
   bidi, selection highlight, reverse video, blink phase, cursor and IME preedit
   applied (`:6120–6240`). It compares that against `disptext`.
3. **Run-granular invalidation:** any mismatched cell invalidates the **whole run
   previously drawn by one `draw_text` call**, marked by `DATTR_STARTRUN`. Fonts
   that overhang their cells (italic-like glyphs, wide chars) are clipped per run by
   the front end, so a partial redraw would leave fragments (comment at
   `:6244–6256`).
4. Changed cells are grouped into runs of identical attributes, and `draw_text` is
   called only for dirty runs. Expose/WM_PAINT goes through `term_paint` (`:6529`):
   it invalidates the rectangle and paints.
5. **There is no scroll-blit optimisation.** No ScrollWindow/XCopyArea in
   `terminal.c` or `windows/window.c` (**inference** from grep), so a full-screen
   scroll repaints every changed row.

### 8.6 Resize

`term_size` (`:2195`):

- **No reflow.** Lines are widened lazily and are **never truncated until they are
  modified** (`:1209–1227`), so dragging the window narrower and back loses
  nothing. Rewrapped prompts, though, never re-flow.
- On shrink, blank bottom rows go first, then top rows move to scrollback. On grow,
  those rows (`tempsblines`) come back.
- **The alt screen is discarded and recreated blank on every resize** (`:2315`); the
  app is expected to redraw.
- Selection is cleared, `disptext` is invalidated, and `backend_size` is called
  (`:2369`).

### 8.7 Selection and paste

- Selection is character, word or line, linear or rectangular (Alt toggles
  rectangular; `:7400`). Word classes come from a configurable 256-entry table plus
  a Unicode class table (`wordtype`, `:6874`).
- Shift overrides mouse reporting. Copy can carry RTF (colours and attributes) on
  Windows.
- **Paste** (`term_do_paste`, `:7124`):
  - Newlines are normalised to CR.
  - All C0/C1 controls except CR/LF/TAB/BS are **stripped by default**
    (`paste_controls` off).
  - In bracketed mode the ESC that would form `ESC[201~` is dropped.
  - Pastes over 256 chars are fed **one line per top-level callback** (`:7081`), so
    a huge paste never freezes the loop and the backend's `sendok`/backpressure
    applies.

### 8.8 Trust status in the terminal

- `term_set_trust_status` (`:2181`) sets the mode. Every line written while trusted
  carries `line->trusted`.
- When trust changes, the current line is cleared first (`check_trust_status`,
  `:2585`), so a server can't leave half a line that PuTTY then "continues".
- Trusted lines reserve leading columns where the renderer draws the PuTTY icon
  (`draw_trust_sigil`). Server output can never produce it.
- The bit survives scrollback compression.

---

## 9. Front ends

### 9.1 Process model

- **One process per window**, on both platforms.
  - Windows "Duplicate Session" serialises the Conf into a file mapping and launches
    a new process with `&R<handle>` (`windows/window.c:~2276–2297`).
  - GTK passes it over a pipe (`unix/main-gtk-simple.c:150–188`).
- **No tabs.** An unfinished GtkApplication variant exists for macOS
  (`unix/main-gtk-application.c`).
- The platform-neutral code avoids per-session globals so a multi-session process
  is possible (`doc/udp.but:136`). The Windows front end itself uses globals.

### 9.2 Windows GDI rendering (`windows/window.c`)

- **No back buffer.** Text is drawn straight to the window DC (`GetDC`, `:2144`).
  - `WM_PAINT` calls `term_paint` for the exposed rectangle (`:2784–2836`).
  - If a terminal update is pending, the paint only marks cells invalid.
  - A comment admits the "right" fix is a bitmap "as the GTK one already does"
    (`:2794–2824`).
- **Fonts** (`init_fonts` `:1432–1620`, `another_font` `:1626`):
  - Variants for bold/underline/wide/double-height/narrow/OEM are created lazily.
  - If the bold font's metrics differ, PuTTY falls back to **shadow bold** (draw
    twice, offset 1 px). If the underline variant's metrics differ, underlines are
    drawn manually.
  - Quality is default/antialiased/non-AA/ClearType. Size is DPI-scaled.
- **Text output** (`do_text_internal`, `:3537`):
  - `ExtTextOutW` with an explicit per-character advance array (`lpDx`) forces
    glyphs onto the cell grid; wide chars get double advance (`:3760–3827`).
  - Surrogate pairs and variation selectors are kept together.
  - Variable-pitch fonts are drawn glyph-by-glyph, centred.
  - Combining chars are overprinted.
  - RTL runs use glyph-index output so Windows doesn't apply a second bidi pass on
    top of PuTTY's own (`:1262–1299`). Other runs use plain `ExtTextOutW`, so GDI
    **font linking** supplies missing glyphs.
- **DPI:** the manifest declares PerMonitorV2 (`windows/putty.mft:24–32`).
  `WM_DPICHANGED` resets fonts and applies the suggested rect (`:3119–3124`).
- **Resize policy** (`CONF_resize_action`):
  - Change rows/cols, change font size, "either" (font when maximised or with Alt
    held), or disabled.
  - `WM_SIZING` snaps to whole cells and shows a size tooltip (`sizetip.c`).
  - The **backend is told only when the drag ends** (`need_backend_resize`,
    `:2903–2918`), so the server isn't flooded with `window-change`.
- **Event sources:** sockets use `WSAAsyncSelect` → `WM_NETEVENT` in the GUI
  (`windows/select-gui.c:44`), and `WSAEventSelect` in CLI tools. Non-socket handles
  (ConPTY pipes, serial, local proxy commands) get **one helper thread per direction
  per handle**, which signals the main thread with events (`windows/handle-io.c`).
  Overlapped I/O isn't used because some handle types can't do it. These threads are
  only a substitute for `select()`. All logic stays on the main thread
  (`doc/udp.but:276–290`).
- A modal MessageBox inside network code can be **re-entered** by network events
  pumped through its own message loop (`doc/udp.but:270–275`). Single-threaded GUI
  code needs care around nested message loops.

### 9.3 Keyboard

- **Key-to-bytes encoding lives in the shared terminal core** (`format_arrow_key`,
  `format_function_key`, `format_small_keypad_key`, `format_numeric_keypad_key`,
  `terminal.c:7561–7731`). Windows and GTK therefore send identical bytes.
- **Function-key modes:** ESC[n~ (tilde), Linux console, xterm R6, VT400, VT100+,
  SCO, and "xterm 216+" with modifier parameters (`putty.h:474–481`).
- **Arrows:** Ctrl toggles normal/application mode, or a modifier bitmap
  `ESC[1;mA` is sent.
- **Other options:** Backspace ^? vs ^H, rxvt Home/End, NetHack keypad, "Ctrl+Alt is
  AltGr", disable application keypad/cursor switching, Alt+F4/Alt+Space behaviour,
  compose key.
- **Not supported:** kitty keyboard protocol, `modifyOtherKeys`.
- `doc/udp.but:301` sets a principle worth adopting: **keystrokes go to the server
  wherever possible**. A key with a meaningful escape sequence should never be
  unconditionally hijacked as a hotkey.
- **IME:** Windows uses the system composition window and feeds committed text one
  char at a time, a workaround for a Korean IME bug (`:3291–3337`). GTK draws
  preedit inline and positions the IME at the cursor (`unix/window.c:2085–2126`).

### 9.4 GTK / pterm and remote X11

- **Retained server-side surface:** each window keeps a pixmap/Cairo surface
  (`unix/window.c:98–119`). Text is drawn into it, and an expose just copies a
  rectangle. The comment's stated aim is the "absolute minimum of network traffic"
  over remote X. Invalidation is `gtk_widget_queue_draw_area` per changed region.
- **`unifont.c`** puts two font back ends behind one interface:
  - **Server-side core X fonts:** with Cairo, glyphs are drawn by `XDrawString16`
    into a **1-bit server pixmap used as a Cairo mask** (`unifont.c:699–725`). No
    glyph pixels cross the wire, which is ideal over `ssh -X`. There is no fallback
    for missing glyphs.
  - **Client-side Pango fonts:** they get fallback, but are drawn in width-checked
    chunks (`:1505–1640`).
  - A "multifont" wrapper fills missing glyphs from a fallback font (`:2077`).
- **Event loop priorities:** fd watches run at `GDK_PRIORITY_REDRAW+1`, *below*
  redraw (`unix/gtk-common.c:111–121`). Top-level callbacks run from `g_idle_add`.
- **pty backend** (`unix/pty.c`):
  - It uses `posix_openpt` and keeps a privileged helper that stays alive to clean
    up utmp/wtmp (`:128–240`).
  - Resize sends `TIOCSWINSZ` including pixel size.
  - Child exit arrives via SIGCHLD → self-pipe.
  - It **stops reading once 32 KiB of output is backlogged** (`:711–716`).
  - EOF on the master while the child is alive counts as a clean finish.

This is the closest prior art for synthesis §6.2's "classic server-side X11
backend". PuTTY proves retained-pixmap plus server-side-glyph-mask rendering works
well over remote X.

### 9.5 ConPTY (`windows/conpty.c`)

ConPTY is used only by **Windows pterm** (`windows/pterm.c:62`), as a `Backend` like
any other.

- **Setup:** load the API at runtime (fail gracefully if absent), create two
  anonymous pipes, call `CreatePseudoConsole`, and `CreateProcessW` with the
  pseudo-console attribute (`:163–306`). I/O uses the threaded handle machinery plus
  a wait on the process handle.
- **Teardown:** when the process exits, record the exit code and call
  `ClosePseudoConsole`, but **keep reading the output pipe until EOF**, because
  closing can trigger a final burst of output (`:78–140`). Synthesis §10 already
  notes the related drop-order hazard.
- **Resize:** `ResizePseudoConsole` (`:340–347`).
- NTSTATUS-style negative exit codes are clipped (`:387–410`).

Windows PuTTY (the SSH client) **never goes through ConPTY**. This is exactly the
split puritty plans: embedded SSH for remote sessions, ConPTY only for local
shells.

---

## 10. Saved sessions, configuration, command-line tools

### 10.1 Conf and storage

- **The Conf schema is declarative:** `conf.h` is a macro table of options. Each
  entry has a value type, an optional subkey type (for maps such as port forwards
  and env vars), a default, a storage keyword, an enum mapping (`conf-enums.h`), and
  load/save flags. Generic load/save loops over it (`settings.c:537ff, 708ff`).
- **The storage interface is tiny** (`storage.h`). Windows uses the registry under
  `HKCU\Software\SimonTatham\PuTTY\Sessions`. Unix uses one file per session in
  `~/.putty/sessions`, with X resources as an extra defaults source.
- **"Default Settings"** is a saved session with a reserved name.
- **Saved sessions are full snapshots.** Every key is written, so later changes to
  Default Settings don't propagate. This is a long-standing user complaint
  (**inference** from the save loop). puritty should store overrides on top of
  inherited defaults.
- **Jump list:** recently launched sessions appear in the Windows taskbar jump list
  (`windows/jump-list.c`).

### 10.2 Config dialog

- `dialog.h`/`config.c` describe a **platform-neutral control tree** (panels such
  as "Connection/SSH/Auth", built by `setup_config_box`, `config.c:1783`). Each
  platform renders it (`windows/controls.c`, `unix/config-gtk.c`).
- The same tree is reused for mid-session **"Change Settings"**, with
  non-changeable options hidden, followed by `backend_reconfig`.
- Panels are deliberately kept small enough for 640×480 (`doc/udp.but:320`). That is
  why the UI has dozens of small panels, and new users find it confusing.
- PuTTY's config UX is widely considered dated: a modal tree of tiny panels, and
  "Load/Save" semantics that confuse users (you must click Save after editing).
  Users still value the **saved-session list** itself: named hosts, each with its
  own key, user, port forwards and colours. puritty's equivalent is probably
  `~/.ssh/config` hosts plus a light per-host profile overlay.

### 10.3 Command-line tools

- **`cmdline.c`** gives all tools a shared option set: `-load`, `-l`, `-P`, `-pw`,
  `-pwfile`, `-i`, `-cert`, `-A`, `-X`, `-t/-T`, `-N`, `-nc`, `-L/-R/-D`,
  `-proxycmd`, `-hostkey`, `-share`, `-batch`, logging options, and more. Each option
  is gated per tool.
- **plink** is the `ssh` equivalent.
  - The host can be a saved session name.
  - `-batch` makes every prompt, including host-key prompts, fail rather than wait.
  - Output to a console is control-character-stripped unless a pty was requested
    (`windows/plink.c:500–524`).
  - plink is commonly used as `GIT_SSH` and as a `ProxyCommand`.
- **pscp** prefers SFTP and falls back to legacy SCP (`pscp.c:432–466`). **psftp**
  is an interactive SFTP client. SFTP transfers pipeline up to 1 MiB of outstanding
  requests (`ssh/sftp.c:904`). Both tools use synchronous loops (`psftp.c:2500–2514`)
  that would be wrong in a GUI.
- **psusan** is a bare ssh-connection server over stdio. **psocks** is a standalone
  SOCKS server. **Uppity** is a test SSH server.
- **Pre-connect command:** new in this tree (`config.c:2516–2520`,
  `cmdline.c:474`). Exact semantics are **unverified**.

SFTP shares the connection layer. For puritty, file transfer would be one more
channel type ("drag a file onto an SSH pane") on the same connection object. Keep
it out of v1, but don't design the connection API so that only session channels are
possible.

---

## 11. Testing and fuzzing

| Tool | What it does |
|---|---|
| `test/testcrypt.c` + `testcrypt.py` | A half-duplex line protocol on stdin/stdout exposing every crypto primitive, mp_int op, key format and KEX to Python (`testcrypt.c:1–25`). It is a subprocess, not an extension module, so it can run under a debugger, sanitisers or valgrind, and other languages can drive it |
| `test/cryptsuite.py` | Thousands of assertions in classes `mpint`, `ecc`, `keygen`, `ntru`, `crypt`, `standard_test_vectors` (`cryptsuite.py:166–3599`) |
| `test/testsc.c` + `test/sclog/` | Runs each primitive with different secrets under a DynamoRIO instrumentation library. It logs control flow and memory addresses and asserts the traces are identical, giving **side-channel freedom by test** (`testsc.c:1–60`) |
| `test/dsa_nonce_recover.py` | Recovers DSA/ECDSA nonces from signatures, given the key, to eyeball their distribution. This came after the P-521 biased-nonce disaster (§12) |
| `test/agenttest.py`, `agentmulti.py` | Pageant protocol tests |
| `test/test_terminal.c` | A mock TermWin with only 4 tests (hello world, wrap, nonwrap, window title; `:184–508`). Coverage is thin |
| `test/test_bpp.c` | BPP large-packet tests |
| `test/test_lineedit.c`, `test_conf.c`, `windows/test/test_screenshot.c` | Small unit tests |
| `test/fuzzterm.c` | An AFL harness: feeds stdin to a 24×80 Terminal whose TermWin **prints every draw call** (`TEXT[attr]@(x,y)…`, `CURS`, `TRUST`). That output is also a deterministic trace of the damage-limited repaint |
| `test/*.txt` | vt100/display/utf8/colours files for manual visual checks |
| `PUTTY_FUZZING` CMake option (`cmake/setup.cmake:16`) | Builds SSH with `none` cipher/MAC added to the KEXINIT lists (`transport2.c:857–891`) and a constant RNG (`sshrand.c:15–25`), so a fuzzer can drive the protocol stack from plaintext input |
| Uppity / psusan | An in-tree SSH server built from the same layers, for end-to-end tests |

Lessons for puritty:

- A **headless terminal core plus a draw-call trace** makes renderer damage
  testable.
- A **fuzzing build flag** that neuters crypto lets the protocol parser be fuzzed.
- **Crypto known-answer tests and constant-time checks** matter only if you write
  crypto yourself. Don't; use a vetted library.

---

## 12. Notable challenges and security history

### 12.1 Security issues visible in the code and docs

CVE numbers below come from code comments where cited. The others are from general
knowledge of PuTTY's advisories and are marked **unverified** here.

| Issue | What PuTTY does | Lesson |
|---|---|---|
| **Terrapin**, CVE-2023-48795 (`ssh.h:2101`) | Strict KEX in BPP and transport. Warns, and computes whether a preference reorder would avoid the issue (`transport2.c:1683–1720, 2561–2710`) | Make security warnings actionable |
| **Biased ECDSA nonces** (the NIST P-521 key-recovery bug, CVE-2024-31497, fixed 0.81; **unverified** number) | The old deterministic-nonce scheme produced too little hash output. Replaced by RFC 6979 with test vectors and split into constant-time phases (`crypto/rfc6979.c:70–87`). `test/dsa_nonce_recover.py` checks the distribution | Don't roll crypto. If you must, test statistical properties |
| **Server spoofing PuTTY prompts** | Trust sigil, framed banners/KI prompts, "Access granted" in plink, antispoof formatting (§5.5) | Client UI must be unforgeable by server bytes |
| **Trivial-auth spoofing** (CVE-2021-36367, **unverified** number) | `SshNoTrivialAuth` option (`conf.h:321–324`) | Let users require real auth |
| **Window-title query → fake keystrokes** | Title reporting returns an empty string by default (`doc/config.but:883–900`, `settings.c:945–958`) | Never echo attacker-settable strings back as input |
| **Paste with embedded escapes** | Strip C0/C1 except CR/LF/TAB/BS by default; drop the ESC of `ESC[201~` (`terminal.c:7124`) | Same as synthesis §8 |
| **Combining-char memory DoS** | `CC_LIMIT` = 32 per cell (`terminal.h:494`) | Cap every per-cell unbounded structure |
| **OSC run-on** | 2048-byte cap; CR/LF aborts OSC (`terminal.c:5335–5368`) | Bound and resynchronise string states |
| **Side channels** | `testsc` DynamoRIO trace comparison for all crypto | Covered by a vetted library |
| **SSH-1 CRC32 compensation attack** | `ssh/crc-attack-detector.c` | Historical; don't ship SSH-1 |
| **Latest commits** | "Fix null dereference on a spurious remote port open", "Complain if CHANNEL_DATA received after CHANNEL_EOF" (git log, 2026-10-12) | Protocol state machines stay a source of bugs decades in. Fuzz them |

### 12.2 Engineering challenges and how PuTTY handles them

- **One thread doing everything:** solved with non-blocking coroutines, callback
  queues, idempotent wake-ups, and explicit fairness in the message loop. The cost
  is that one slow synchronous operation freezes the UI, and only discipline
  prevents that. Examples: Windows' modal host-key dialog, and the synchronous
  psftp loops. Argon2 key decryption with high memory settings is a likely freeze
  point too (**inference**).
- **Server bugs:** 15 `BUG_*` flags (`ssh.h:2062–2076`) can be auto-detected
  from the version string or forced on/off in config. Every mature SSH client needs
  this table.
- **Flow control end to end:** the terminal backlog drives the SSH window, socket
  backlog throttles all channels, and the pty read stops at 32 KiB. This is what
  keeps memory bounded under `cat /dev/urandom`.
- **Resize races:** the parser pauses on remote-initiated resizes. Backend resizes
  are sent only at drag end.
- **Legacy compatibility:** VT52, SCO and Linux console modes, many keyboard modes,
  and codepages. Most are irrelevant to puritty.

### 12.3 What a modern terminal should do differently

| PuTTY | Modern expectation |
|---|---|
| One process and window per session, no tabs/splits | Tabs, splits, one process, shared connections in-process |
| Own `SshHostKeys` registry store, no `known_hosts` | Read/write `~/.ssh/known_hosts` (OpenSSH semantics, hashed hosts, `@cert-authority`, `@revoked`) |
| PPK only; OpenSSH keys need conversion | Load OpenSSH keys directly; PPK import as a bonus |
| No Windows OpenSSH agent | Try `openssh-ssh-agent` pipe and Pageant |
| No `~/.ssh/config` | Parse `Host`, `HostName`, `User`, `Port`, `IdentityFile`, `ProxyJump` at least |
| Keepalive = IGNORE, no dead-peer detection; modal fatal-error box; manual "Restart Session" | Replying keepalives with N-miss timeout, in-pane disconnected banner, one-key reconnect, tmux re-attach |
| Saved sessions are full snapshots | Profiles that override inherited defaults |
| GDI, no back buffer, no shaping, shadow bold | GPU renderer locally; a retained-surface X11 renderer remotely; DirectWrite on Windows |
| No reflow, alt screen cleared on resize | Reflow the primary screen; keep the alt screen |
| No OSC 8/52/133/7, no 2026, no kitty keys, no colon SGR, no italics/undercurl, DCS ignored | All of these, plus DCS for tmux `-CC` |
| No grapheme clustering | Grapheme-cluster-aware width (synthesis §5.3) |
| UpdateHostKeys not implemented | Implement `hostkeys-00@openssh.com` or cross-certification |

---

## 13. Lessons for puritty

**Backend and Seat**

1. **Adopt a Backend/Seat pair, not just a Backend.** PuTTY's `Backend` (down) plus
   `Seat` (up) split maps onto puritty's PTY / tmux pane / SSH channel backends.
   - Down: `send`, `size`, `special`, `sendbuffer`, `unthrottle`, `sendok`.
   - Up: `output → backlog`, `eof`, `remote_exit`, `connection_fatal`, `nonfatal`,
     async `prompt`, `confirm_host_key`, `set_trust_status`, `specials_changed`.
   - Return-value backpressure in both directions is simple and works.
2. **"Specials" as a backend-published action menu.** Break, signals, rekey, cache
   new host key, "send Ctrl-Alt-Del". The pane's context menu can then show
   per-backend actions without the UI knowing about SSH.
3. **`sendok` gating plus buffered input.** Don't let keystrokes reach a backend
   before it's ready. Buffer them, and make sure a proxy's or jump host's prompt
   doesn't fight the main session for input.

**SSH structure (Windows embedded client)**

4. **Layer the SSH stack PuTTY's way, even if you use a library.** Transport (with
   rekey holding back higher-layer output), userauth as a replaceable layer, a
   connection layer multiplexing channels, and a `Channel` interface per consumer.
   Most libraries (x/crypto/ssh, russh, libssh2) already look like this. Check that
   yours:
   - rekeys transparently;
   - exposes per-channel window/backpressure;
   - lets you pipeline `pty-req`/`env`/`shell`;
   - supports async host-key and auth callbacks that can wait for UI without
     blocking the reactor.
5. **Every user interaction is an async yield.** Host-key dialogs, passphrases and
   KI prompts must not block the event loop or other tabs' connections. Rekeys and
   other channels keep running while a dialog is up. Model prompt results as
   `{pending, ok, user-abort, software-abort(msg)}`. The abort distinction decides
   whether to show an error.
6. **Connection sharing is in-process for puritty.** Keep one connection object per
   `(user, host, port, proxy chain)` and open one session channel per tab. Copy
   three PuTTY details:
   - The connection outlives its first tab while other channels exist.
   - Warn before closing the last tab of a connection that still has forwardings.
   - With several sessions on one connection, X11 forwarding needs per-session fake
     cookies, and agent forwarding is necessarily shared.
   Cross-process sharing (named pipe + bare ssh-connection protocol) is only needed
   if external tools should reuse GUI connections.
7. **Jump hosts as composition.** A jump-host connection is a full SSH client whose
   "seat" turns its channel into a socket for the next hop. Copy two things:
   - Hop announcements ("Connecting via jumphost…") before any prompt, so the user
     knows which hop is asking.
   - Letting a hop be a named profile.
8. **Host-key UX:**
   - Accept / Connect once / Cancel.
   - A scary, distinct mismatch dialog where Cancel is the default.
   - Pinned keys (manual list → hard fail, no prompt).
   - Prefer-known-key-types.
   - Safe key rotation (cross-certify or UpdateHostKeys).
   - Structured dialog text that each front end renders, including batch/CLI.
   - Unlike PuTTY, **use OpenSSH `known_hosts`**.
9. **Auth UX:**
   - Offer a public key before asking for its passphrase.
   - Don't spray every agent key when a specific identity is configured.
   - Optionally refuse trivial auth.
   - Try the Windows OpenSSH agent pipe and Pageant.
   - Load OpenSSH keys natively.
10. **Anti-spoofing.** Render client prompts out-of-band (overlay or dialog), or, if
    in-band, with a per-line trust bit and an unforgeable margin glyph. Frame and
    sanitise server banners and keyboard-interactive text. Show hop announcements.
    This matters more for a terminal that embeds SSH than for one that runs `ssh` in
    a PTY, because the app *is* the trusted party.
11. **Keepalives that detect death.** Use `keepalive@openssh.com`-style requests with
    a miss limit, not `SSH_MSG_IGNORE`. On disconnect, keep the pane and scrollback,
    show state in-pane (no modal box), and offer reconnect. PuTTY's "Restart
    Session", which keeps the screen and resets modes, is the floor. With tmux
    `-CC`, make reconnect a re-attach.
12. **Server-bug table and per-host overrides.** Plan for one from day one, keyed on
    the version string.

**Terminal and rendering**

13. **Damage-limited repaint is the right model for the X11 backend.**
    - Keep a shadow of what is on screen.
    - Diff per row.
    - Redraw whole previously-drawn runs to cope with glyph overhang.
    - Coalesce with a cooldown timer.
    PuTTY's GTK front end adds a retained server-side pixmap and server-side glyph
    masks, which keeps remote-X traffic minimal. That matches synthesis §6.2. Add
    what PuTTY lacks: **scroll by blit** (XCopyArea), so a scrolling `tail -f`
    doesn't resend every row.
14. **Pause parsing during round trips that change geometry.** Examples: a remote
    resize request awaiting the window, and a tmux `refresh-client` awaiting
    `%layout-change`. Bytes that follow are interpreted at the new size.
15. **Paste in slices.** Feed big pastes one chunk per event-loop turn, subject to
    backend backpressure.
16. **Event-loop fairness.** When the network floods, still service input and paint.
    PuTTY does this by draining until a non-network message is seen, and on GTK by
    putting fd watches below redraw priority.
17. **Keep key encoding in the core**, not the front end. Both platforms then send
    identical bytes. Follow PuTTY's principle: keys go to the server by default.

**Testing**

18. **Build a fake SSH server and a fuzzing build mode early.** PuTTY's Uppity
    (same layers, server side) and its `PUTTY_FUZZING` mode (null cipher, constant
    RNG) make protocol testing practical. A headless terminal whose TermWin logs
    draw calls (`fuzzterm`) gives deterministic repaint tests for free.

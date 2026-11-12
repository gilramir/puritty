# WezTerm: architecture analysis for a new terminal emulator

Source analyzed: `vendor/wezterm` at commit `e2a98e1b8` (2026-10-10). The last tagged
release in `docs/changelog.md` is `20240203-110809-5046fc22`; everything after that
is "Continuous/Nightly" (`docs/changelog.md:15-22`). So the code read here is about
2.5 years of unreleased work past the last stable build.

Paths are relative to `vendor/wezterm/`. Line numbers refer to that commit. Things
not confirmed in code are marked **inference** or **unverified**. Compared with the
Alacritty and Ghostty docs, this one spends more space on the parts WezTerm has and
they don't: the domain/pane abstraction, the embedded SSH client, the multiplexer
protocol and the tmux control-mode integration. Those are the parts closest to
puritty's Windows product. Section references like "A§5" and "G§8" point into
[`alacritty.md`](alacritty.md) and [`ghostty.md`](ghostty.md), and "S§7" into
[`synthesis.md`](synthesis.md).

---

## 0. TL;DR

- **Two abstraction levels for "where bytes come from".** `Pane`
  (`mux/src/pane.rs:172`) is the high-level unit the GUI renders and sends input
  to. Most panes are a `LocalPane`, which owns a local `wezterm_term::Terminal` plus
  a byte-level `MasterPty` + `Child` pair (`pty/src/lib.rs:90,132`). The byte source
  behind a `LocalPane` can be a Unix PTY, ConPTY, a serial port, **an SSH channel**
  (`wezterm-ssh/src/pty.rs:44`) or **a tmux pane** (`mux/src/tmux_pty.rs:125`). So
  SSH and tmux panes reuse the whole local terminal stack. The one `Pane` that does
  *not* have a local terminal is `ClientPane` (remote mux), which holds a line cache
  fed by the server. This split maps directly onto puritty's backend interface.
- **`Domain`** (`mux/src/domain.rs:50`) is a factory and lifecycle owner for panes:
  local, WSL, exec, serial, SSH, mux client, and tmux. It has `spawn_pane`,
  `split_pane`, `attach`, `detach` and `state`.
- **Embedded SSH client** (`wezterm-ssh`, about 8 kLOC): libssh (default) or
  libssh2 behind an enum wrapper. Its own `ssh_config` parser handles `Host`,
  `Match` (partly), `Include` and tokens. One OS thread per SSH session runs a
  poll loop that shuttles bytes between SSH channels and local socketpairs. New tabs
  in an SSH domain open a **new channel on the same session** (connection
  sharing). Host-key and auth prompts are drawn **inside the pane itself** with a
  line editor, before the real channel is swapped in. Gaps: **no ProxyJump, no
  Pageant or Windows OpenSSH named-pipe agent, no connect timeout, no reconnect, no
  port forwarding**. Keepalive works on the libssh backend only.
- **Multiplexer protocol** (`codec/`): leb128-framed, serde/varbincode PDUs, zstd
  for anything over 32 bytes, exact version match required. Remote panes are
  rendered from **whole serialized lines**: the server pushes "dirty line ranges +
  the dirty visible lines + cursor" on every output event. The client keeps an LRU
  line cache and fetches scrollback lazily. There is real **predictive local echo**
  above an RTT threshold (100 ms by default for SSH/TLS). There is **no
  backpressure** (unbounded server send queue).
- **tmux `-CC`**: a full pest-grammar protocol parser with correct `vis`
  unescaping. The mux layer maps tmux windows to tabs and panes to native splits
  **on attach**, and forwards GUI new-tab, split, focus, resize and keys. After
  attach it mostly ignores remote layout changes. It has no flow control, no
  detach or kill from the GUI, and drops out of control mode on any line the
  grammar doesn't know. The changelog calls it "very usable" since a 2025
  contribution.
- **Terminal model**: a byte-at-a-time DEC state machine (`vtparse`) feeds a
  second layer that builds an owned `Action` enum. Actions are batched into a
  `Vec<Action>` and applied to the `Terminal` under a mutex. Lines are
  `VecDeque<Line>`; each `Line` is either a `Vec<Cell>` (24-byte cells holding a
  grapheme cluster inline) or, once scrolled off, a compressed "clustered" form
  (one string plus attribute runs). Per-line `seqno` drives all dirty tracking,
  both for the GUI and for the mux protocol.
- **Threads per local pane: 4** (PTY reader, parser/applier, writer, child
  waiter). The GUI/mux "main thread" owns topology and rendering. Output reaches
  the GUI as a `PaneOutput` notification that invalidates the window.
- **Rendering**: OpenGL (glium) by default, optional wgpu (Vulkan/DX12/Metal), and a
  "Software" mode that is just Mesa llvmpipe (bundled `opengl32.dll` on Windows).
  Each frame rebuilds every quad, with per-line vertex caches. There is no
  damage-limited present. On X11 it uses **EGL only** and RENDER only for cursors,
  so nothing helps the remote-X case. Fonts use HarfBuzz with ligatures on,
  FreeType rasterizing everywhere, DirectWrite/fontconfig/CoreText for discovery,
  and asynchronous fallback lookup.
- **Windows**: ConPTY with a **sideloaded `conpty.dll` + `OpenConsole.exe`** and
  win32-input-mode; ConPTY quirks are special-cased in the terminal model. SSH panes
  bypass ConPTY completely. WGL is the default GL path (EGL/ANGLE resizes worse);
  RDP forces software GL.

---

## 1. Crates and threading model

### 1.1 Workspace layout

The workspace has roughly 60 crates. The ones that matter architecturally:

| Layer | Crate | kLOC | Role |
|---|---|---|---|
| Parser | `vtparse` | 1.6 | DEC ANSI state machine (vt100.net), UTF-8 aware, `no_std`-capable. Emits `VTActor` callbacks |
| Parser | `wezterm-escape-parser` | 10.9 | Turns `VTActor` callbacks into a typed `Action` enum (CSI/OSC/ESC/DCS/Sixel/Kitty). Contains the tmux control-mode parser (`tmux_cc/`) |
| Model | `wezterm-cell`, `wezterm-surface` | 1.9 + 5.2 | `Cell`, `CellAttributes`, `Line`, line storage variants, hyperlinks, image cells |
| Model | `term` (`wezterm-term`) | 10.2 | `Terminal`/`TerminalState`: screens, scrollback, modes, key/mouse encoding, sixel/kitty/iTerm2 images. No GUI deps |
| Library | `termwiz` | 10.4 | Terminal toolkit: "Surface" change lists, line editor, widgets, terminfo renderer. Re-exports the escape parser. Used for wezterm's own in-pane UIs (§3.6) |
| PTY | `pty` (`portable-pty`) | 2.8 | `PtySystem`/`MasterPty`/`SlavePty`/`Child` traits; Unix, ConPTY and serial impls |
| Mux | `mux` | 11.8 | `Mux` registry, `Domain`, `Pane`, `Tab` (split tree), `Window`, `LocalPane`, SSH domain glue, tmux domain |
| Mux | `codec`, `wezterm-client`, `wezterm-mux-server-impl`, `wezterm-mux-server` | 1.3 + 4.4 + 1.7 | Mux wire protocol, client domain and `ClientPane`, server session handler, server binary |
| SSH | `wezterm-ssh` | 7.9 | SSH client over libssh/libssh2, `ssh_config` parser, SFTP |
| GUI | `window` | 22.9 | Own windowing layer: X11 (XCB), Wayland, Win32, macOS; GL context creation |
| GUI | `wezterm-font` | 10.3 | Font location, HarfBuzz shaping, FreeType rasterizing, fallback |
| GUI | `wezterm-gui` | ~37 (+140 generated Unicode names) | `TermWindow`, render passes, glyph cache, overlays (copy mode, quick select, launcher), Lua GUI API |
| Infra | `promise`, `filedescriptor`, `config`, `luahelper` | | Main-thread executor, portable fds/poll/socketpair, Lua config |

The core/GUI split is real, as in Alacritty and Ghostty: `term` depends on neither
`mux` nor `window`. It talks to its host through a writer (`Box<dyn Write>`) for
replies and an `AlertHandler`/`DeviceControlHandler` for out-of-band events.

There is a second, less common split: **`mux` sits between the terminal and the
GUI**. The GUI never touches a `Terminal` directly. It renders `dyn Pane` objects
from the `Mux` registry (`mux/src/lib.rs:101-116`). That lets the same GUI code
render a local terminal, a pane on a remote mux server, or an overlay (copy mode
wraps another pane and itself implements `Pane`, `wezterm-gui/src/overlay/copy.rs:1105`).
The cost is a wide `Pane` trait (§2.2).

### 1.2 Threads

| Thread | Where | Does |
|---|---|---|
| Main / GUI | `wezterm-gui/src/main.rs`; executor in `promise/src/spawn.rs:39-50` | Window event loop, rendering for all windows, the `Mux` topology (tabs/windows/domains), Lua. Other threads hand work to it with `promise::spawn::spawn_into_main_thread` |
| PTY reader (per pane) | `read_from_pane_pty`, `mux/src/lib.rs:283-370` | Blocking `read()` on the pane's byte source into a 1 MiB buffer, forwards bytes to a socketpair |
| Parser (per pane) | `parse_buffered_data`, `mux/src/lib.rs:142-247` | Reads from the socketpair, parses to `Vec<Action>`, coalesces, then **applies actions to the `Terminal` itself** under the pane's mutex (`send_actions_to_mux`, :122-138), then posts `PaneOutput` to the main thread |
| Writer (per terminal) | `ThreadedWriter`, `term/src/terminalstate/mod.rs:455-500` | Drains a channel of byte buffers into the PTY. Exists so a full PTY input buffer never blocks the parser or GUI |
| Child waiter (per local pane) | `mux/src/localpane.rs:992-999` | `wait()` on the child, then asks the main thread to prune dead windows |
| SSH session (per SSH connection) | `wezterm-ssh/src/session.rs:89-129` | Poll loop over the SSH socket and all channels (§3.5) |
| Mux client (per connection) | `wezterm-client/src/client.rs:340-346` | Async I/O loop for the mux protocol (§4.6) |

Why two threads (reader + parser) per pane joined by a socketpair? The comment at
`mux/src/lib.rs:279-282` says blocking reads are used because "non-blocking reads
are not portable to all platforms and pty/tty types". The socketpair (with 1 MiB
`SO_SNDBUF`/`SO_RCVBUF`, :268-277) gives the parser something it *can* `poll()`
with a timeout, which it needs for output coalescing (§1.3). It is also what makes
backends pluggable: anything that can produce a `Read` works.

Terminal query replies (DA, DSR, OSC queries) are written by the `Terminal` to its
`ThreadedWriter` while the parser thread applies actions. They never go through
the GUI thread. That is what S§3.3 asks for.

### 1.3 Output coalescing and synchronized output

`parse_buffered_data` (`mux/src/lib.rs:142-247`) does three things that matter for
remote use:

- After each read, if fewer than `mux_output_parser_buffer_size` bytes (default
  128 KiB, `config/src/config.rs:1679`) have accumulated, it `poll()`s the socketpair
  for up to `mux_output_parser_coalesce_delay_ms` (default **3 ms**, :1675) to gather
  more before applying. This was added to stop tearing from TUIs that don't use
  synchronized output (#2443, `docs/changelog.md:1475`).
- **DECSET 2026** (synchronized output) is handled *before* the terminal: on set it
  flushes earlier actions and then holds everything until reset (:164-186). A soft
  reset (DECSTR) also releases the hold. There is **no timeout** on the hold, unlike
  Alacritty's 150 ms or Ghostty's 1 s (S§2). A program that sets 2026 and dies
  leaves the pane frozen until more output arrives with a reset. **Inference** from
  the code; I didn't find an issue for it.
- One `PaneOutput` notification per applied batch, sent via
  `Mux::notify_from_any_thread` (:715-727), which schedules a task on the main
  thread. The GUI handler only checks whether the pane is visible and calls
  `window.invalidate()` (`wezterm-gui/src/termwindow/mod.rs:1439-1446`), so many
  notifications collapse into one repaint.

---

## 2. Domains and panes: the backend abstraction

This is the most reusable idea in WezTerm for puritty. S§3.2 calls for a backend
interface (PTY / tmux pane / SSH channel). WezTerm has one, split into **two
layers**, and the split is worth copying.

### 2.1 Byte level: `MasterPty` + `Child`

`pty/src/lib.rs`:

```
trait PtySystem   { openpty(size) -> (MasterPty, SlavePty) }                 // :265
trait MasterPty   { resize(size); get_size(); try_clone_reader() -> Read;      // :90-130
                    take_writer() -> Write; [unix] process_group_leader(), as_raw_fd(), tty_name() }
trait SlavePty    { spawn_command(CommandBuilder) -> Child }                   // :165
trait Child       { try_wait(); wait(); process_id(); [win] as_raw_handle() }  // :132
trait ChildKiller { kill(); clone_killer() }                                    // :152
```

Implementations:

| Impl | File | Read side | Write side | Resize | "Child" |
|---|---|---|---|---|---|
| Unix PTY | `pty/src/unix.rs:343` | master fd | master fd | `TIOCSWINSZ` | real process |
| ConPTY | `pty/src/win/conpty.rs:84` | output pipe | input pipe | `ResizePseudoConsole` | real process |
| Serial | `pty/src/serial.rs:211` | tty | tty | no-op | fake |
| SSH channel | `wezterm-ssh/src/pty.rs:44` (`SshPty`) | socketpair fed by SSH thread | socketpair | `window-change` request (async, no reply) | `SshChildProcess`: exit status from channel EOF; `kill` = send SIGHUP signal request |
| SSH, still connecting | `mux/src/ssh.rs:979-1148` (`WrappedSshPty`) | auth UI output, then real channel | auth UI input, then real channel | remembers size, applies on connect | `WrappedSshChild` |
| tmux pane | `mux/src/tmux_pty.rs:125` (`TmuxPty`) | socketpair fed with `%output` | each write becomes `send-keys -H` | queues `refresh-client`/`resize-pane` | `TmuxChild`: exits on `%exit` |
| Spawn failed | `mux/src/domain.rs:525` (`FailedSpawnPty`) | | | | exits immediately, so the error stays visible |

The interface is just "a `Read`, a `Write`, a resize call and an exit status". Every
backend runs through the same reader thread, parser thread, `Terminal`, renderer,
key encoder, selection and search. The tmux and SSH support is small because of
this. `RemoteSshDomain::spawn_pane` says so in a comment: "Wrap up the pty etc. in
a LocalPane. That allows for eg: tmux integration to be tunnelled via the remote
session without duplicating a lot of logic over here" (`mux/src/ssh.rs:756-758`).
It also means `tmux -CC` works inside an embedded SSH pane with no extra code,
which is exactly puritty's Windows use case.

Weak points of this layer:

- **Blocking-read model.** Each backend must offer a blocking `Read`. Backends that
  are naturally message-based (SSH channels, tmux `%output`) are adapted to it by
  writing into a socketpair from another thread. That costs two extra copies and a
  thread per pane (the tmux and SSH panes each still get their own reader and
  parser thread).
- **Process-centric API.** `Child::process_id`, `process_group_leader`, `tty_name`
  and `as_raw_fd` have no meaning for SSH or tmux. They return `None`, and
  `TmuxChild::try_wait` is literally `todo!()` (`mux/src/tmux_pty.rs:73-75`). Features
  built on them (foreground process name, "is it safe to close this pane?", cwd
  from `/proc`) silently degrade on non-local backends.
- **Writes are opaque bytes.** The tmux backend gets the already-encoded key bytes
  and has to hex-encode each `write()` into its own `send-keys` command with no
  batching (`mux/src/tmux_commands.rs:1022-1028`).

### 2.2 Pane level: `Pane`

`Pane` (`mux/src/pane.rs:172-350`) is what the GUI and the mux server see. Main
groups of methods:

- **Render data:** `get_current_seqno`, `get_changed_since(range, seqno) ->
  RangeSet`, `get_lines(range) -> (first, Vec<Line>)`, `with_lines_mut`,
  `get_logical_lines`, `get_cursor_position`, `get_dimensions`, `get_title`,
  `palette`, `is_alt_screen_active`, `is_mouse_grabbed`.
- **Input:** `key_down/key_up(KeyCode, mods)`, `mouse_event`, `send_paste`,
  `writer()`, `resize(TerminalSize)`, `focus_changed`, `perform_actions`.
- **Lifecycle:** `is_dead`, `kill`, `can_close_without_prompting`, `exit_behavior`,
  `domain_id`.
- **Metadata:** `get_current_working_dir`, `get_foreground_process_name`,
  `tty_name`, `copy_user_vars`, `get_semantic_zones`, `search`.

Lines are addressed by **`StableRowIndex`**: a row number that doesn't change as
lines scroll into scrollback (the screen keeps `stable_row_index_offset`,
`term/src/screen.rs:27-30`). Dirty tracking is by **sequence number**: every
mutation stamps the touched `Line` with the terminal's current seqno, and
`get_changed_since` returns the rows whose seqno is newer
(`wezterm-surface/src/line/line.rs:283-300`, `mux/src/localpane.rs:186-192`). The
same two primitives drive the local renderer and the network protocol (§4.3), which
is elegant: a remote pane is just a `Pane` whose `get_lines` is backed by a cache.

Keys enter as **logical key events, not bytes**. `Pane::key_down(KeyCode, mods)`
asks the pane's `Terminal` to encode them (`term/src/terminalstate/keyboard.rs:64`),
because the encoding depends on terminal modes (kitty flags, DECCKM, win32-input).
For a `ClientPane` the key event itself goes over the wire (`SendKeyDown`) and the
*server's* terminal encodes it. That is correct, but it means the client can't
know what bytes a key produces, which limits local echo (§4.4).

Implementations: `LocalPane` (`mux/src/localpane.rs:124-136`), `ClientPane`
(`wezterm-client/src/pane/clientpane.rs:34`), `TermWizTerminalPane` (internal UIs
such as the launcher, `mux/src/termwiztermtab.rs:128`), `CopyOverlay` and
`QuickSelectOverlay` (GUI-side wrappers around another pane).

### 2.3 `Domain`

`Domain` (`mux/src/domain.rs:50-200`) creates panes and owns their lifecycle:

```
spawn(size, cmd, cwd, window) -> Tab        // default: spawn_pane + new Tab
split_pane(source, tab, pane, request)      // default: spawn_pane + tab.split_and_insert
spawn_pane(size, cmd, cwd) -> Pane          // required
move_pane_to_new_tab(...)                   // optional override (remote mux)
attach(window) / detach() / detachable() / state() -> Attached|Detached
spawnable(), domain_id(), domain_name(), domain_label()
```

| Domain | File | Panes | Notes |
|---|---|---|---|
| `LocalDomain` | `mux/src/domain.rs:202, 589` | `LocalPane` over `native_pty_system()` | Also used for **WSL** (rewrites argv to `wsl.exe --distribution … --cd … --exec`, :271-312), **exec domains** (a Lua callback rewrites the command, :313-373), **serial** (:246-254), and flatpak (`flatpak-spawn --host`, :374-428) |
| `RemoteSshDomain` | `mux/src/ssh.rs:180,701` | `LocalPane` over `SshPty` | `multiplexing = "None"`. One shared SSH session (§3.8) |
| `ClientDomain` | `wezterm-client/src/domain.rs:741` | `ClientPane` | Remote mux over unix socket, TLS, or SSH-exec. `spawn`/`split_pane` forwarded to server. `detachable()` is true |
| `TmuxDomain` | `mux/src/tmux.rs:364` | `LocalPane` over `TmuxPty` | Created on the fly when a pane sees DCS `1000p` (§5) |
| `TermWizTerminalDomain` | `mux/src/termwiztermtab.rs:50` | internal UI panes | not spawnable |

`DomainState::Detached` means "panes exist elsewhere but are not shown here".
`Mux::domain_was_detached` removes all local panes of the domain
(`mux/src/lib.rs:1095-1118`). For a `ClientDomain` the server keeps them, and
`attach()` brings them back (§4.7).

### 2.4 Pane lifecycle for a non-local backend

The SSH first-connect path shows a useful pattern for any backend whose setup is
slow or interactive (`mux/src/ssh.rs:327-411`):

1. `spawn_pane` returns **immediately** with a `LocalPane` whose `MasterPty` is a
   `WrappedSshPty` in state `Connecting`. Its reader is one end of a socketpair.
2. A separate thread runs the connection. Banner, host-key prompt, password and
   keyboard-interactive prompts are rendered **as terminal output in that pane**
   using termwiz's `LineEditor` over the socketpair (`mux/src/ssh.rs:421-698`). The
   user types into the pane as usual. Resizes during this phase are remembered.
3. On `Authenticated`, it requests the real PTY channel and sends the real
   reader/writer/pty/child through channels. The wrapper switches to `Connected`
   on next use and applies the remembered size (:1012-1034). The `PtyWriter` checks
   for a new writer before each write to fix a Windows issue where a socket accepted
   writes after disconnect (#771, :1108-1119).
4. While connecting, `exit_behavior` is forced to `CloseOnCleanExit` so failures
   stay on screen (`mux/src/localpane.rs:226-242`).

So the GUI never needs a modal dialog for SSH auth: the pane *is* the dialog. Mux
client connections and TLS bootstrap use a separate small terminal window instead
(`ConnectionUI`, `mux/src/connui.rs`), with the same prompt logic
(`mux/src/ssh.rs:60-131`).

### 2.5 Tabs and the split tree

A `Tab` holds a `bintree::Tree<Arc<dyn Pane>, SplitDirectionAndSize>`
(`mux/src/tab.rs:17,40-55`). Each internal node stores its direction and the cell
sizes of *both* children (`:103-107`). It is a binary tree, so an n-way tmux split
has to be expressed as nested binary splits (§5.3). Zoom is a field on the tab
(`zoomed`). The tree is serializable (`PaneNode`, :2103) and is sent over the mux
protocol in `ListPanesResponse`.

---

## 3. The built-in SSH client (`wezterm-ssh`)

### 3.1 Libraries and backend selection

- Both **libssh** (via `libssh-rs` 0.3.8, built `vendored`; bundled libssh 0.11.1
  per `docs/changelog.md:319`) and **libssh2** (via `ssh2` 0.9.3, built against
  OpenSSL on Windows) are compiled in by default (`wezterm-ssh/Cargo.toml`
  features `default = ["libssh-rs", "ssh2"]`). Building with neither is a
  `compile_error!` (`wezterm-ssh/src/lib.rs:1-2`).
- `config.ssh_backend` (`Ssh2` | `LibSsh`, default **LibSsh**,
  `config/src/ssh.rs:8-18`) and a per-domain override select one. The docs say
  libssh is the default "as it has broader support for newer keys"
  (`docs/config/lua/config/ssh_backend.md`). The choice travels as a pseudo
  ssh-option `wezterm_ssh_backend` (`mux/src/ssh.rs:202-212`).
- The abstraction is **enums with `match`**, not a trait: `SessionWrap`,
  `ChannelWrap`, `SftpWrap`, `FileWrap`, `DirWrap`
  (`wezterm-ssh/src/sessionwrap.rs:5-23`, `channelwrap.rs:4-10`). Connect,
  host verification and auth are written twice, once per library
  (`sessioninner.rs:110-321`, `host.rs`, `auth.rs`). Feature parity drifts as a
  result: keepalive, signals and agent forwarding exist only on libssh (§3.7, §3.10).

Lesson: two C SSH libraries behind one interface roughly doubled the surface for
bugs without delivering parity. The changelog shows wezterm switched the default
to libssh (`docs/changelog.md:1863`) and moved TLS bootstrap to libssh "for
Windows reliability" (:1826). Pick one SSH implementation.

### 3.2 `ssh_config` parsing (`wezterm-ssh/src/config.rs`)

WezTerm parses OpenSSH config itself, so `wezterm ssh host` and SSH domains honor
the user's existing files.

- **Files:** `~/.ssh/config`, `/etc/ssh/ssh_config`, and on Windows
  `%SystemDrive%/ProgramData/ssh/ssh_config` (`config.rs:467-475`).
- **Storage:** an untyped `BTreeMap<String,String>` keyed by lowercased directive
  (`config.rs:6`). First value wins, except `IdentityFile`, which accumulates
  (`config.rs:346-359`).
- **`Host`:** whitespace-separated patterns with `*`, `?`, `!` negation, compiled to
  regexes (`config.rs:18-72`).
- **`Match`:** `all`, `host`, `originalhost`, `user`, `localuser` work.
  `exec` logs "not implemented" and is treated as matching (`config.rs:112-114`).
  `canonical`/`final` never match because only one pass is run (`config.rs:101-104`).
  `Match User` is compared against the **local** user (`config.rs:516-517`), which is
  wrong relative to OpenSSH.
- **`Include`:** supported, with globbing; relative paths resolve against the
  including file's directory (`config.rs:171-226`).
- **Tokens:** `%h %n %r %p %d %u %l %L %i %C %%` (`config.rs:621-732`). `%i` is empty
  on Windows, `%j` is always empty. `ProxyCommand` expands only `%h %n %p %r`. A typo
  (`"userknownkostsfile"`, `config.rs:624`) means `UserKnownHostsFile` gets no token
  expansion. `${VAR}` expansion is applied to a fixed list of path-like keys
  (`config.rs:612-618`).
- **Defaults injected:** port 22, local user, `UserKnownHostsFile ~/.ssh/known_hosts
  ~/.ssh/known_hosts2`, `IdentityFile` = the four classic key names,
  `IdentityAgent = $SSH_AUTH_SOCK` (`config.rs:572-605`).
- **Override order:** file values, then `SshDomain.ssh_option` entries verbatim (keys
  must be lowercase), then `username`, port from `remote_address`, and `no_agent_auth`
  mapped to `identitiesonly=yes` (`mux/src/ssh.rs:187-230`). `wezterm ssh -oK=V`
  feeds the same map (`wezterm-gui/src/main.rs:136-152`).
- **Directives that actually do something:** hostname, user, port, proxycommand,
  proxyusefdpass, addressfamily, bindaddress, identityfile, identityagent,
  identitiesonly (libssh2 agent path only), userknownhostsfile,
  pubkeyacceptedtypes, hostkeyalgorithms, forwardagent, serveraliveinterval. The
  documented list is in `docs/ssh.md:31-68`. Everything else is parsed and ignored.
- **Double parsing on libssh:** the libssh backend also calls
  `options_parse_config(None)` so libssh reads the files itself, then wezterm
  re-applies its own values for a handful of keys (`sessioninner.rs:180-208`, with a
  `FIXME: overridden config path?`). Two parsers can disagree.
- `enumerate_hosts()` (`config.rs:778-798`) lists concrete `Host` names; WezTerm
  auto-creates `SSH:<host>` and `SSHMUX:<host>` domains from them
  (`config/src/ssh.rs:111-137`), which makes ssh_config hosts appear in the launcher.

### 3.3 known_hosts and host-key verification

- Events: `SessionEvent::HostVerify { message, reply }` and
  `HostVerificationFailed { remote_address, key, file }` (`wezterm-ssh/src/host.rs:5-26`).
- **libssh:** SHA256 fingerprint; on unknown it prompts (blocking the SSH thread
  until the UI answers) and appends via `update_known_hosts_file()`. Changed key:
  `HostVerificationFailed`, connection aborted. Only the **first**
  `UserKnownHostsFile` is passed to libssh (`sessioninner.rs:192-197`).
- **libssh2:** loops over the known_hosts files that *exist*; on not-found prompts,
  then writes `[host]:port`. **Bug:** if no known_hosts file exists at all, it
  returns OK with no prompt and no verification (`host.rs:119-121`).
- `StrictHostKeyChecking` and `GlobalKnownHostsFile` are never read by wezterm code.
  It always prompts on unknown hosts.
- **UX:** a text prompt `Enter [y/n]>` in the pane (`mux/src/ssh.rs:600-615`). A
  mismatch renders a bold, double-height "REMOTE HOST IDENTIFICATION CHANGED" banner
  with the fingerprint and the file to edit (`mux/src/ssh.rs:133-170`). No GUI
  dialog, no "replace key" action.

### 3.4 Authentication and agents

- `SessionEvent::Authenticate { username, instructions, prompts: [{prompt, echo}],
  reply }` (`wezterm-ssh/src/auth.rs:6-27`). The SSH thread blocks until answered.
  This one shape covers password, keyboard-interactive (OTP etc.) and key
  passphrases.
- **libssh order:** `none`, then loop over the server's method list: publickey via
  `userauth_public_key_auto` (agent + identity files, passphrase via callback),
  keyboard-interactive, password. Partial success loops again, so MFA chains work
  (`auth.rs:132-253`). There are `.unwrap()`s and `answers.remove(0)` on the reply
  path (`auth.rs:151-156, 233-238`): a canceled prompt can **panic** the SSH thread.
- **libssh2 order:** agent (skipped if `identitiesonly`), identity files (try without
  passphrase, then prompt), password, keyboard-interactive (`auth.rs:256-364`).
- **Agent:** `IdentityAgent` defaults to `$SSH_AUTH_SOCK`, and the agent socket is
  opened as an AF_UNIX stream, including on Windows via `uds_windows`
  (`sessioninner.rs:869-882`, `wezterm-uds/src/lib.rs:11-17`). **There is no
  Pageant support and no Windows OpenSSH named-pipe (`\\.\pipe\openssh-ssh-agent`)
  support** anywhere in the tree (grep for `pageant`, `openssh-ssh-agent`: nothing).
  On a stock Windows machine `SSH_AUTH_SOCK` is normally unset and the agent lives
  on the named pipe, so agent auth through the libssh backend most likely does not
  work out of the box. **Inference**; I didn't test it. Whether libssh2's own
  Windows agent code reaches Pageant is a libssh2 detail I didn't verify.
- **Agent forwarding:** libssh only (`ForwardAgent yes`); incoming agent channels are
  bridged to the local agent socket (`sessioninner.rs:864-917`). libssh2 returns an
  error (`channelwrap.rs:149-162`).

### 3.5 Threading model of a session

- **One OS thread per SSH session.** `Session::connect` creates bounded(8) event and
  request channels, plus a non-blocking socketpair used as a wake-up pipe, then
  spawns `SessionInner::run` (`wezterm-ssh/src/session.rs:89-129`). `Session` is a
  cheap clonable handle; each request writes one byte to the wake pipe.
- Connect, host verification and auth run **blocking** on that thread before the
  loop starts.
- Requests: `NewPty`, `ResizePty`, `Exec`, `Sftp`, `SignalChannel`, `SessionDropped`
  (`session.rs:55-62`), each with a bounded(1) reply channel; the public API is async
  (`request_pty`, `exec`, `sftp`).
- **Loop** (`sessioninner.rs:447-550`): keepalive → `tick_io` (move bytes between
  every SSH channel and its local fds, `:554-632`) → drain wake pipe → handle requests
  (switching the session to blocking mode during a request, `:644-650`) → accept
  agent-forward channels → `poll()` on wake pipe + SSH socket (direction from
  libssh2 `block_directions` / libssh `get_poll_state`) + every channel's local fd.
  Poll timeout starts at 100 ms, doubles while idle, resets on activity.
- Each channel has three 8 KiB-buffered slots (stdin, stdout, stderr), each a
  socketpair whose other end is handed to the pane (`sessioninner.rs:25-55`).

So bytes from the SSH server go: socket → SSH library → `tick_io` → socketpair →
pane's reader thread → socketpair → pane's parser thread → `Terminal`. That is three
threads and two socketpairs per hop. It works, but a design that delivers channel
data straight into the pane's parser would cut latency and copies.

A blocking request on the session thread (e.g. opening a new channel while the
server is slow) stalls I/O for **all** channels of that session. **Inference** from
the blocking-mode switch at `:644-650`.

### 3.6 How channel data reaches the terminal

`new_pty` (`wezterm-ssh/src/pty.rs:212-318`): `open_session` → optional
`request_auth_agent` → `request_pty(term, size)` → `request_env` per variable →
`request_exec(cmd)` or `request_shell`.

- **stderr is merged into stdout** by giving both the same fd (`pty.rs:272`).
- **pty-req:** libssh sends cols/rows only; libssh2 also sends pixels. **No terminal
  modes** are sent (libssh2 passes `None`, `channelwrap.rs:96-117`), so the remote
  tty gets server defaults for erase char, etc.
- **window-change:** libssh2 `request_pty_size` with pixels; libssh `change_pty_size`
  with cols/rows (`channelwrap.rs:164-179`). Sent fire-and-forget from
  `SshPty::resize`.
- **TERM:** the pty-req term is `config.term`, default `xterm-256color`
  (`config/src/config.rs:1751-1753`, `mux/src/ssh.rs:653,721`). TERM, COLORTERM,
  TERM_PROGRAM, TERM_PROGRAM_VERSION and user `set_environment_variables` also go
  as SSH `env` requests (`config/src/config.rs:1598-1622`), which most servers
  reject unless `AcceptEnv` allows them; wezterm warns once. With
  `assume_shell = "Posix"` it additionally wraps the command as
  `cd DIR; env K=V … $SHELL -c '<login-shell trick>'` (`mux/src/ssh.rs:272-322`),
  which is how it gets env vars and cwd through without AcceptEnv.
- `kill` sends a SIGHUP signal request (libssh only; no-op on libssh2,
  `channelwrap.rs:181-192`).

### 3.7 Keepalive, timeouts, reconnect

- **Keepalive:** `ServerAliveInterval` makes the libssh backend send an `IGNORE`
  packet every interval. There is no `ServerAliveCountMax` and no disconnect on
  failure; the comment says it's unclear how to implement that
  (`sessioninner.rs:416-445`). libssh2: no keepalive at all.
- **Connect timeout:** none. `sock.connect` blocks (`sessioninner.rs:401`), and
  `SshDomain.timeout` (`config/src/ssh.rs:71-72`) is never read on the SSH path.
- **Disconnect:** channel errors close the channel's fds, the pane sees EOF and exit
  code 1. `docs/ssh.md:19-20` says ad-hoc SSH tabs die on a network drop.
- **Reconnect:** none for panes. If the session is dead, the *next* spawn in the
  domain starts a fresh session (`mux/src/ssh.rs:737-745`). The SSH flavor of the
  mux client domain is explicitly not reconnectable because "we need to grow some
  smarts about whether the disconnect was because we sent CTRL-D … or whether it was
  a network level disconnect, because we will otherwise throw up authentication
  dialogs" (`wezterm-client/src/client.rs:639-643`). TLS mux domains do reconnect.

### 3.8 Connection sharing and the two SSH domain flavors

| | `multiplexing = "None"` (`wezterm ssh`, `SSH:host`) | `multiplexing = "WezTerm"` (default for configured domains, `SSHMUX:host`) |
|---|---|---|
| Domain | `RemoteSshDomain` | `ClientDomain` with `ClientDomainConfig::Ssh` |
| Remote requirement | any sshd | `wezterm` installed remotely |
| Panes | `LocalPane` + `SshPty`; terminal emulated locally | `ClientPane`; terminal emulated on the remote mux server |
| Sharing | one session; each new tab/split = new channel, no re-auth (`mux/src/ssh.rs:702-754`) | one exec channel running `wezterm cli proxy` carries the whole mux protocol (`wezterm-client/src/client.rs:677-729`) |
| Survives disconnect | no | panes survive on server; client must reattach manually (SSH flavor not auto-reconnect) |
| Auth UI | in the pane | separate ConnectionUI window |

The `None` flavor is the right model for puritty's Windows SSH backend: one
transport per host, one channel per pane. The `WezTerm` flavor is the "mosh-like"
option that needs a server-side component; tmux `-CC` gives similar persistence
without installing anything new.

### 3.9 ProxyCommand and ProxyJump

- **ProxyCommand** is implemented by wezterm (libssh2 lacks it, libssh lacks it on
  Windows): it runs `%COMSPEC% /c …` or `sh -c "exec …"` with a socketpair as stdio
  and hands that socket to the SSH library (`sessioninner.rs:323-404`). The child is
  killed and reaped on drop (`:1131-1142`, #5494). `ProxyUseFdPass` is Unix-only.
- **ProxyJump is not supported** (`config.rs:706-713`: "We don't directly support
  ProxyJump"). Users must write the equivalent `ProxyCommand ssh -W %h:%p jump`,
  which on Windows needs an external `ssh.exe`. For a bastion-heavy user base this is
  a real gap; a native implementation (direct-tcpip channel over a first session,
  then a second SSH handshake over that channel) is the fix.

### 3.10 Not present

- Port forwarding (`LocalForward`, `RemoteForward`, `DynamicForward`): parsed, never
  used.
- X11 forwarding: absent.
- SFTP: a complete async API exists (`wezterm-ssh/src/sftp/`), but only tests call it.
- ControlMaster/ControlPath with OpenSSH: not supported (wezterm's own sharing only).

### 3.11 Notable SSH changelog themes

From `docs/changelog.md`: Windows socket quirks (first character after
keyboard-interactive swallowed #771, resize during auth #696), token-expansion gaps
(#2448, #3437 after wezterm took over ProxyCommand), resource leaks ("too many open
files" #2466, ProxyCommand children #5494), hangs (password auth hang #2194, endless
loop after a drop #857, deadlock when a domain detaches on SSH timeout #6749), and
connection errors hidden by `exit_behavior` (#3941). The pattern: the SSH protocol
itself was rarely the problem; config semantics, Windows I/O and lifecycle edges
were.

---

## 4. The multiplexer and its protocol

### 4.1 Wire format (`codec/src/lib.rs`)

- Frame: `leb128 tagged_len` (bit 63 = compressed) · `leb128 serial` · `leb128 ident`
  · payload (`:59-97`). Payload is serde via `varbincode`. The explicit `ident` (not
  serde's variant tag) lets old PDUs be retired (`:1-10, :447-450`).
- **Compression:** any payload over `COMPRESS_THRESH = 32` bytes is also zstd-encoded
  and the smaller form is sent (`:289-317`).
- Serial: client requests number 1, 2, 3…; responses echo the serial; server pushes
  use serial 0. The client rejects implausibly large serials, which catches garbage
  such as remote shell startup output on the SSH channel
  (`wezterm-client/src/client.rs:1187-1192`).
- **`CODEC_VERSION = 46`** (`:445`). The handshake (`GetCodecVersion`) requires an
  **exact** match; otherwise "Please install the same version…" (`client.rs:64-78`).
  No feature negotiation. Client and server must be upgraded together, which is a
  constant user complaint pattern for SSH-mux setups where the remote is a different
  distro.
- PDUs cover topology (ListPanes, SpawnV2, SplitPane, KillPane, MovePaneToNewTab…),
  input (WriteToPane, SendKeyDown, SendMouseEvent, SendPaste, Resize, SetClipboard),
  rendering (GetPaneRenderChanges(+Response), GetLines(+Response), GetImageCell,
  LivenessResponse), search, palette, alerts, workspaces (`:451-517`).

### 4.2 Transports

| Transport | Code | Notes |
|---|---|---|
| Unix socket | `client.rs:731-808` | Auto-starts the server on first attach; optional `proxy_command`. AF_UNIX on Windows too (`wezterm-uds`) |
| TLS/TCP | `client.rs:810-1038` | OpenSSL, `TCP_NODELAY`, mutual certs. **Bootstrap via SSH**: runs `wezterm cli tlscreds` over SSH and saves the certs. Auto-reconnects |
| SSH exec | `client.rs:545-599, 677-729` | `wezterm cli --prefer-mux proxy` on the remote; the remote proxy is netcat to the local unix socket (`wezterm/src/cli/proxy.rs`) |

### 4.3 How remote panes render

Hybrid push and poll, carrying **whole lines**:

- **Push:** on every `PaneOutput` the server computes a delta per client and sends a
  `GetPaneRenderChangesResponse` with serial 0
  (`wezterm-mux-server-impl/src/sessionhandler.rs:53-151, 241-253`). The delta
  holds: cursor, dimensions, title, cwd, mouse-grabbed, alt-screen, seqno,
  `dirty_lines: Vec<Range<StableRowIndex>>`, and `bonus_lines`: the **full
  serialized contents of the dirty lines inside the viewport** plus the cursor line
  (`:104-128`). Dirty scrollback rows are sent as ranges only. Lines are compressed
  with `compress_for_scrollback` before serializing (§6.3), and the whole PDU is
  zstd'd.
- **Poll:** the GUI's `get_changed_since` triggers `GetPaneRenderChanges` at most
  one-in-flight, with an interval starting at 20 ms and doubling to 30 s when idle
  (`wezterm-client/src/pane/renderable.rs:27-28, 586-598`). It mostly acts as a
  liveness check.
- **Client cache:** an LRU of `StableRowIndex → Line | Fetching | Stale`, sized
  `max(scrollback_lines, 128)` (`renderable.rs:30-43, 68`). Dirty rows in the
  viewport not covered by bonus lines are fetched with `GetLines`, rate-limited to
  `ratelimit_mux_line_prefetches_per_second` (default 50); scrollback rows are
  marked stale and fetched on demand when scrolled into view. Images are fetched
  separately by hash (`GetImageCell`) into a 128-entry LRU.
- **Input:** keys, paste, resize are fire-and-forget. Mouse moves are collapsed and
  wheel deltas summed, one request in flight (`mousestate.rs:27-104`).

There are **no cell-level diffs and no scroll operations** in the protocol: if
`cat` scrolls the screen by one line, every visible line's seqno changes (they all
moved), so every visible line is resent. zstd claws much of that back, but it is
fundamentally "resend the screen" on scroll. The changelog has "Improved latency for
large window sizes" (#1872, `docs/changelog.md:986`) and "render update laggy, esp.
multiple windows" (#1814/#1841, :1702).

### 4.4 Latency handling: predictive local echo

This is real and worth studying (`renderable.rs:136-298`):

- **RTT measurement:** each `SendKeyDown` carries an `InputSerial`, which is the
  client's wall-clock milliseconds. The server always pushes a delta tagged with the
  latest input serial after handling a key, even if nothing changed
  (`sessionhandler.rs:667-699`). The client computes RTT from it.
- **Gate:** prediction only when `last_input_rtt >= local_echo_threshold_ms`
  (default **100 ms** for SSH and TLS domains, disabled for unix,
  `config/src/config.rs:1795-1797`).
- **Prediction:** printable keys (no modifiers, or Shift only) are written into the
  client's cached cursor line with a **double-underline** attribute and the cursor
  advances. Backspace/Delete erase, Enter and arrows move the cursor. Paste is
  predicted too, wrapped at the column count.
- **Correction:** the next real delta for that line simply overwrites the cached
  line. Cursor updates are accepted only from the newest input serial, so the cursor
  doesn't wiggle back.
- **Safety:** skipped if the line contains the substring `"sword"` (a password-prompt
  heuristic, `:157-163`). The comment admits vim normal mode and password prompts
  are unsolved (`:148-155`). It has no notion of the remote echo mode; mosh's
  approach (confirm predictions against the server's echo before showing them
  confidently, and back off when they're wrong) is more careful.
- **Lag indicator:** `is_tardy()` (more than max(poll interval, 3 s) since the last
  receive, with a send outstanding) can overwrite the top row with
  "wezterm: Ns⏳since last response" when `overlay_lag_indicator` is set (default
  off).

### 4.5 Server side

- One `SessionHandler` per connection, which subscribes to **all** mux notifications
  and keeps a `PerPane` record (last sent cursor, title, dims, seqno…) for every pane
  that produces output, whether or not this client shows it (`sessionhandler.rs:38-50,
  233-239`).
- The outgoing queue is **unbounded** (`dispatch.rs:48-57`). Every output event
  produces a push to every client. On a slow link this is the failure mode: deltas
  queue faster than the link drains, memory grows, and latency grows with the queue.
  Because each delta is "everything dirty since my last send", a coalescing design
  (at most one outstanding push per pane per client; compute the delta when the
  socket is writable) would bound both. WezTerm doesn't do that. A seqno race that
  lost updates was fixed late (#5981, `docs/changelog.md:232`).

### 4.6 Threading

Server: everything (mux, all sessions) on the main thread via the `promise`
executor; blocking accept threads per listener; 2 threads per pane. Client: one OS
thread per connection running a smol `block_on` select loop over requests and
socket readability (`client.rs:340-346, 381-386`); unilateral PDUs are forwarded to
the GUI thread. There is no per-request timeout (`client.rs:1304-1312`).

### 4.7 Detach and reconnect

- Unix domain: no reconnect. TLS: backoff 1 s → 10 s with a "Reconnecting..." window,
  then `ListPanes` and a mark-and-sweep of id mappings (`client.rs:1048-1109`,
  `wezterm-client/src/domain.rs:462-472`). SSH: no reconnect (§3.7).
- Detach removes local panes; `ClientPane::kill` doesn't send `KillPane` when the
  domain is detached, so panes stay alive on the server (`clientpane.rs:487-525`).
- Local and remote pane/tab/window ids differ and are translated in both directions
  (`domain.rs`), which is a recurring bug source in the changelog (#781, #2614,
  #2616, #2759, #1993).
- `docs/multiplexing.md:1-2` still calls multiplexing "a young feature".

---

## 5. tmux control mode

### 5.1 Detection and parsing

- DCS hook with params `[1000]` and final `p` puts the escape parser into tmux mode
  (`wezterm-escape-parser/src/parser/mod.rs:258-263`, cargo feature `tmux_cc`, on by
  default; no runtime switch). Subsequent `parse()` calls **bypass vtparse
  entirely** and hand whole buffers to the tmux parser (`:86-120`), which is the
  right shape for a hot path.
- Lines are split by hand, then each line is parsed with a **pest grammar**
  (`tmux_cc/tmux.pest`, `tmux_cc/mod.rs:219-515`). `%begin/%end/%error` blocks are
  collected into `Event::Guarded` and the three numbers must match
  (`mod.rs:883-939`).
- The grammar covers essentially every notification in tmux 3.x: `%output`,
  `%extended-output`, `%layout-change`, `%window-add/close/renamed`,
  `%window-pane-changed`, `%session-changed/renamed`, `%sessions-changed`,
  `%session-window-changed`, `%client-session-changed`, `%client-detached`,
  `%pause`, `%continue`, `%exit`, `%message`, `%config-error`, `%pane-mode-changed`,
  `%paste-buffer-*`, `%subscription-changed`, `%unlinked-window-*`
  (`tmux.pest:21-45`).
- **Unescaping is correct:** `unvis_bytes` is a full OpenBSD `vis` decoder (`\ooo`,
  `\\`, `\n`, `\M-x`, `\^x`, …) applied to `%output` and `%extended-output`
  (`mod.rs:519-681`). This is the bug Ghostty has (S§7.1). But the
  `%extended-output` age field isn't split off, so it leaks into the pane text
  (`tmux.pest:26`).
- **Fragility:** any line the grammar fails on drops the pane out of tmux mode and
  feeds the rest back to vtparse (`parser/mod.rs:107-118`). A new tmux notification
  or a `%client-detached` with extra arguments would end the session's integration.
  Unknown `%` lines should be ignored, not fatal.
- Layout strings are parsed (`tmux.pest:83-99`, `mod.rs:692-837`) into a flattened
  list of `SplitHorizontal/SplitVertical/SinglePane` entries.

### 5.2 TmuxDomain and the command queue

- When `LocalPaneDCSHandler` sees the hook, it creates a `TmuxDomain` tied to the
  originating pane and prints "[This pane is running tmux control mode. Press q to
  detach]" in it (`mux/src/localpane.rs:867-902`). That pane then swallows all keys
  except `q`, which sends `detach` (`:401-410`).
- Commands implement `TmuxCommand { get_command() -> String; process_result(&Guarded) }`
  (`mux/src/tmux_commands.rs:20-23`). **One in flight**, FIFO-matched, no check of the
  `%begin` number (`mux/src/tmux.rs:239-259, 92-109`). `Resize` emits two commands in
  one string and so two replies, which can desynchronize the FIFO
  (`tmux_commands.rs:933-948`).
- **Attach sequence:** `%session-changed` → `list-commands` (feature detection) →
  `list-windows -F …` → `sync_window_state` creates one tab per tmux window and
  builds splits by walking the flattened layout with `split_and_insert` and
  `SplitSize::Cells` (`tmux_commands.rs:358-548`) → per pane `capture-pane -p -e -C
  -S -<history>` → `list-panes` for cursor and active pane. `list-windows` output is
  split on spaces, so a window name containing a space breaks parsing
  (`tmux_commands.rs:797`).
- **GUI → tmux:** new tab sends `new-window` and lets `%window-add` create the tab
  (`tmux.rs:365-377`); split sends `split-window -h/-v` and waits for
  `%window-pane-changed` (`tmux.rs:379-401`); tab/pane focus sends
  `select-window`/`select-pane`; resize sends `refresh-client -C` or
  `resize-window` + `resize-pane` depending on what `list-commands` reported.
- **tmux → GUI after attach:** `%window-add`, `%window-close`, `%window-renamed`, and
  pane removal (via `%layout-change` → `list-panes` → prune). **Remote layout changes,
  splits made by another client, pane resizes, zoom and session switches are not
  reflected.**

### 5.3 Data path and threading

- `%output` is written into the target pane's socketpair; that pane's own reader and
  parser threads apply it (`mux/src/tmux.rs:160-173`). So each tmux pane gets the
  full local-pane machinery, including its own lock.
- tmux parsing and `TmuxDomainState::advance` run on the **originating pane's parser
  thread, holding that pane's terminal lock** (`term/src/terminalstate/performer.rs:354`).
  Command results and topology changes are moved to the main thread.
- The write into a pane's socketpair is a blocking `write_all` while holding the
  `remote_panes` lock. If one pane's parser falls behind and its socket buffer fills,
  the control connection's parser stalls and **all panes stop updating**.
  **Inference** from the code; this is the head-of-line problem that tmux's own
  `pause-after` flow control exists to solve.
- Output for a pane not yet created is backlogged with `HashMap::insert`, which keeps
  only the **last** chunk (`tmux.rs:170`).

### 5.4 Gaps

No `refresh-client -f pause-after`, `%pause`/`%continue` ignored; no kill-pane or
kill-window from the GUI; no detach from the GUI (`detachable()` false); `TmuxChild`
`try_wait` is `todo!()` and `kill` errors; `spawn_pane` unimplemented; one session and
one GUI window only; split sizes from the GUI ignored; tmux pane PTY sizes have no
pixel dimensions (`docs/changelog.md:304`). The user docs still say "Currently
incomplete, see issue #336" and give the wrong final byte (`docs/escape-sequences.md:373`),
while the changelog says "`tmux -CC` support is now very usable" (#6602,
`docs/changelog.md:118`). `SshMultiplexing` has a `// TODO: Tmux-cc in the future?`
(`config/src/ssh.rs:24`), so tmux as a persistence layer for SSH domains was planned
but never built.

What puritty can take: the grammar coverage and the `vis` decoder are good test
oracles; the idea of making a tmux pane "just another `MasterPty`" is right; the GUI
round-trip for new-tab/split (send the command, create the native object only when
tmux's notification arrives) is right. What to do differently: tolerate unknown
lines, match replies by number, apply `%layout-change` to the native split tree,
implement flow control, and demultiplex `%output` without blocking the control
reader.

---

## 6. Terminal model

### 6.1 Parser

Two stages:

1. **`vtparse`** (`vtparse/src/lib.rs`): table-driven DEC ANSI state machine with a
   UTF-8 sub-state. It processes **one byte at a time** (`parse` is a plain loop over
   `parse_byte`, :752-756); there is no SIMD or ASCII fast path. Limits: 256 CSI
   params, 2 intermediates, 64 OSC params; OSC data is a growable `Vec` when `std` is
   on (:316-345). APC is collected (used for kitty graphics). DCS is delivered as
   hook/put/unhook.
2. **`wezterm-escape-parser`** (`parser/mod.rs`, `csi.rs` 3.4 kLOC, `osc.rs` 2 kLOC):
   implements `VTActor` and builds an owned `Action` enum: `Print`, `PrintString`,
   `Control`, `DeviceControl`, `OperatingSystemCommand(Box<…>)`, `CSI`, `Esc`,
   `Sixel(Box<…>)`, `XtGetTcap`, `KittyImage(Box<…>)` (`lib.rs:47-67`). Sixel and
   short DCS have their own builders.

The parser thread collects `Vec<Action>` and hands it to
`Terminal::perform_actions`. Compared with Ghostty's direct dispatch from the state
machine into handler calls, this allocates per sequence (boxed OSC, strings for
prints). The changelog records several rounds of "reduced overhead of parsing
output" (`docs/changelog.md:1279`). The benefit is that `Action` is a serializable
value type, useful for tests and for replaying (termwiz also uses it to *generate*
output).

### 6.2 Cells, lines, scrollback

- **`Cell`** = `TeenyString` (8 bytes: up to 7 bytes of UTF-8 inline with width bits,
  otherwise a heap pointer) + `CellAttributes` (16 bytes) = **24 bytes**
  (`wezterm-cell/src/lib.rs:561-729, 1032-1036`). So a whole grapheme cluster lives in
  the cell, inline for almost all text. `CellAttributes` holds a 32-bit flag word,
  two `SmallColor`s, and `Option<Box<FatAttributes>>` for hyperlink, image
  placements, underline color and true-color fg/bg (`:58-104`).
- **`Line`** = `CellStorage` (`V(Vec<Cell>)` or `C(ClusteredLine)`), semantic zones,
  `seqno`, bits (wrapped, double-width/height, bidi)
  (`wezterm-surface/src/line/line.rs:46-54`, `storage.rs:7-12`).
- **Scrollback compression:** when a line scrolls off the top it is converted to
  `ClusteredLine`: one `String` for the text plus runs of (width, attributes)
  (`clusterline.rs:18-35`; triggered in `term/src/screen.rs:690-693`). Any later
  mutation re-materializes the `Vec<Cell>`. That's a cheap version of Ghostty's
  "cold pages" idea, applied per line.
- **`Screen`** = `VecDeque<Line>` with capacity for scrollback + viewport, and
  `stable_row_index_offset` for `StableRowIndex` (`term/src/screen.rs:16-46`).
  Scrollback is limited in **lines**, default **3500** (`config/src/config.rs:1705`),
  max 999,999,999.

### 6.3 Graphemes and width

Printable characters are buffered and segmented with `finl_unicode` grapheme
clusters, optionally NFC-normalized, then each cluster's width is computed with
`grapheme_column_width` against a configurable Unicode version
(`term/src/terminalstate/performer.rs:117-224`). Zero-width clusters are dropped
unless they are White_Space (with links to #1422 and #6637 explaining why). The
Unicode version defaults to **9** for width (`config/src/config.rs:1808`), and apps
can push/pop it with iTerm2's `OSC 1337 ; UnicodeVersion` (`performer.rs:838-858`).
This is WezTerm's answer to the width-mismatch problem; Ghostty uses mode 2027
instead.

### 6.4 Reflow

`Screen::resize` (`term/src/screen.rs:193-322`) rewraps the **whole** primary screen
plus scrollback when the column count changes (`rewrap_lines`, :101-190); the alt
screen is truncated or invalidated, never rewrapped. Trailing blank lines below the
cursor are pruned first so repeated maximize/restore doesn't grow scrollback
(:215-223). With ConPTY, resize keeps scrollback "immutable", because ConPTY's own
redraws otherwise move the cursor too high and erase output (comment at :265-287).
The same ConPTY quirk mode refuses to mark a line as wrapped when its last cell is
not alphanumeric/punctuation (`performer.rs:163-190`), because ConPTY re-emits lines
in ways that would otherwise be joined wrongly.

### 6.5 Images

All three protocols: sixel (`term/src/terminalstate/sixel.rs`), kitty graphics
(`kitty.rs`, 979 lines, including shared-memory transfer per
`docs/changelog.md:1676`), and iTerm2 `OSC 1337 File` (`iterm.rs`). Images are
attached to **cells** as `ImageCell`s with texture coordinates and a z-index
(`wezterm-cell/src/image.rs:92-104`), referencing an `Arc<ImageData>` deduplicated by
hash. Encoded image data can be stored as a content-addressed **blob lease** on disk
in the cache directory (`wezterm-blob-leases`, registered at
`wezterm-gui/src/main.rs:416-417`), so large images don't sit in RAM. A single image
is capped at 100 MB decoded (`term/src/terminalstate/image.rs:303-312`), added after
an OOM from huge iTerm2 PNGs (#1031). Over the mux, images were "unusable for all but
tiny images" until #1237 moved them to hash references fetched separately.

### 6.6 Other features worth noting

Bidi (`bidi` crate, 5 kLOC, opt-in per line), semantic zones from OSC 133, OSC 8
hyperlinks plus regex-based implicit hyperlinks, user vars (`OSC 1337 SetUserVar`),
`XTGETTCAP`, win32-input-mode (DECSET 9001, for ConPTY), kitty keyboard protocol,
DECRQCRA (now off by default to stop silent screen scraping, `docs/changelog.md:27`).

---

## 7. Rendering

### 7.1 Front ends

`FrontEndSelection { OpenGL (default), WebGpu, Software }` (`config/src/frontend.rs:5-10`).
OpenGL is the default on every platform; WebGpu was briefly the default and was
reverted (`docs/config/lua/config/front_end.md`).

| Front end | Implementation | Notes |
|---|---|---|
| OpenGL | glium 0.35; shaders tried as GLSL `330 core`, `330`, `320 es`, `300 es` (`wezterm-gui/src/renderstate.rs:679`) | X11 and Wayland via **EGL only** (no GLX); Windows via WGL by default, ANGLE EGL optional; macOS EGL (ANGLE) then CGL 3.2 |
| WebGpu | wgpu 25 with `Backends::all()` (`wezterm-gui/src/termwindow/webgpu.rs:226-230`); Vulkan/Metal/DX12/GL | `PresentMode::Fifo` hard-coded (:367). No automatic fallback to OpenGL if it fails (`termwindow/mod.rs:859-864`). Changelog has a DX12 crash on Windows 11 (#4279) and a panic on minimize |
| Software | **not** a CPU renderer of wezterm's own. Sets `prefer_swrast()` (`window/src/configuration.rs:1-12`) | Linux: sets `LIBGL_ALWAYS_SOFTWARE=true` for Mesa llvmpipe (`window/src/egl.rs:434-441`). Windows: loads a **bundled Mesa `opengl32.dll`** from `<exe>\mesa` (`window/src/os/windows/wgl.rs:94-110`, `assets/windows/mesa/`) |

History worth knowing: WezTerm *had* its own basic CPU renderer and removed it in
2020 in favor of Mesa llvmpipe "which has improved visuals"
(`docs/changelog.md:2242-2250`). Fallbacks: on Linux, if every EGL config fails it
retries with swrast forced (`egl.rs:435-479`). On Windows an **RDP session forces
software rendering** because "Using OpenGL in RDP has problematic behavior upon
disconnect" (`window/src/configuration.rs:3-9`; detection via `SM_REMOTESESSION`
and the GlassSessionId registry value, `window/src/os/windows/mod.rs:23-54`).

### 7.2 Per-frame pipeline: full rebuild, cached per line

- Every paint resets all layers' quad allocations and re-emits background, every
  pane, splits, tab bar, borders and modals (`termwindow/render/paint.rs:164-280`);
  the GL path clears the frame and draws every layer (`render/draw.rs:159, 237-270`).
  There is **no damage tracking to the screen and no partial present**: grep for
  `swap_buffers_with_damage` or similar finds nothing in the renderer.
- To make the full rebuild cheap there are three CPU-side caches, each 1024
  entries by default (`termwindow/mod.rs:430-436`; `config/src/config.rs:2106-2120`):
  1. `line_state_cache`: line seqno → 16-byte shape hash, stored in the line's
     appdata (`render/mod.rs:892-923`);
  2. `line_to_ele_shape_cache`: shaped elements per line (`screen_line.rs:119-135`);
  3. `line_quad_cache`: **ready-made vertices for a whole line**, keyed by config,
     shape and quad generations, selection, cursor, `top_pixel_y`, pane id…
     (`render/mod.rs:57-82`). On a hit the vertices are memcpy'd into the frame's
     vertex buffer (`render/pane.rs:426-466`).
  So unchanged lines skip shaping and quad building, but every vertex is still
  uploaded and drawn every frame. Note `top_pixel_y` in the key: when the screen
  scrolls, every line moves and every cache entry misses.
- Each z-layer has three sub-layers (background, text with optional dual-source
  subpixel blending, foreground), each a triple-buffered vertex buffer that grows
  in steps of 128 quads; on overflow the paint pass is retried after reallocating
  (`renderstate.rs:328-332, 454-470, 622-669`; `paint.rs:37-51`).
- **Frame pacing:** `max_fps` default 60, implemented as a timer after each paint
  on X11 and Windows (`window/src/os/x11/window.rs:396-411`,
  `window/src/os/windows/window.rs:1640-1655`); Wayland uses frame callbacks. EGL
  sets `SwapInterval(0)` ("we'll manage throttling frames at the application level",
  `egl.rs:643-647`). `animation_fps` default 10 drives blinking/easing; the docs
  suggest 1 for the Software front end.

### 7.3 Glyph atlas

guillotiere `SimpleAtlasAllocator` on a square texture starting at **128×128**
(`window/src/bitmaps/atlas.rs:24-44`, `termwindow/mod.rs:90`). On
`OutOfTextureSpace` the paint loop first recreates the atlas *at the same size*
(evicting everything, which reclaims space from glyphs no longer on screen), then
doubles; if that fails it downscales images by 2/4/8 and finally drops them
(`paint.rs:53-92`, `renderstate.rs:719-777`). There is no LRU eviction; "rebuild
everything" is the eviction policy. Glyph keys include font index, glyph id, cell
count, style, `followed_by_space`, cell metrics (`glyphcache.rs:75-83`). Box drawing,
block elements, sextants, octants, Braille and Powerline glyphs are **drawn
procedurally** with tiny-skia to fit the cell exactly (`customglyph.rs`, 6 kLOC;
`custom_block_glyphs` option).

### 7.4 Fonts and shaping

- **HarfBuzz** is the only shaper (Allsorts was removed, `config/src/font.rs:709-713`),
  cluster level MONOTONE_GRAPHEMES, default features `kern, liga, clig`
  (`wezterm-font/src/shaper/harfbuzz.rs:233`; `config/src/config.rs:1744-1749`).
  Ligatures are on by default. A shape cache keyed by (style, text) gave a 2-3×
  speedup (`shapecache.rs:9-12`; `docs/changelog.md:2465`).
- **Fallback is asynchronous:** when shaping finds codepoints with no glyph in any
  loaded font, it schedules a lookup on a background thread
  (`wezterm-font/src/lib.rs:181-243, 520-557`) and renders without them meanwhile.
  When results land, the next shape call returns `ClearShapeCache`, and the paint
  loop bumps the shape generation and redraws (`paint.rs:93-98`). This keeps
  fontconfig latency off the frame path. Default fallback fonts are bundled:
  JetBrains Mono, Noto Color Emoji, Symbols Nerd Font Mono.
- **Locators:** fontconfig on Linux, CoreText on macOS, and on Windows a locator
  called "Gdi" that is mostly **DirectWrite** (`dwrote` system collection plus
  `FontFallback::get_system_fallback()`), with GDI for some loading
  (`wezterm-font/src/locator/gdi.rs:213-312`).
- **Rasterizer:** FreeType everywhere (LCD subpixel, COLR v1), including Windows.
  So on Windows it is DirectWrite for finding fonts and FreeType for drawing them.

### 7.5 Remote X11

WezTerm has nothing for the remote-X case:

- GL on X11 is **EGL only** (`window/src/os/x11/window.rs:161-191`; `prefer_egl.md`:
  "X11: EGL is the only way to use the GPU"). Over `ssh -X` there is no usable EGL
  display on the remote X server, so it ends up on Mesa's software EGL on the
  client side, which presents finished frames as images. That is the full-frame
  llvmpipe path S§6.1 warns about. **Inference** about the Mesa behavior; wezterm's
  code just requests EGL.
- The RENDER extension is used **only for cursors** (`window/src/os/x11/cursor.rs:193-331`).
  No XRender glyph sets, no `XCopyArea` scrolling, no MIT-SHM path.
- No docs, comments or changelog entries discuss remote displays.

This confirms S§6: none of the three reference terminals has a server-side X11
renderer. puritty's X11 backend is new ground.

---

## 8. Windowing per platform (`window` crate)

WezTerm wrote its own windowing crate instead of using winit (23 kLOC). It gives
them direct control over IME, decorations and event handling; the cost is visible in
the changelog as a long tail of per-WM fixes.

| Platform | Stack | IME | DPI | Notes |
|---|---|---|---|---|
| X11 | xcb 1.3 (render, randr, dri2, xkb, present) + xlib display for EGL; xkbcommon with compose | **xcb-imdkit** (wezterm fork), preedit callbacks (`x11/connection.rs:106, 795-801`) | RandR / Xft.dpi | Prefers 32-bit visuals for transparency; refresh rate from RandR modes (`connection.rs:303-348`); `GetGeometry` round trips when geometry is uncertain (`x11/window.rs:353-360`) |
| Wayland | smithay-client-toolkit 0.19, wayland-egl | `zwp_text_input_v3` | fractional scale | Requests server-side decorations, falls back to its own tiny-skia frame. Changelog: "Wayland: currently being reimplemented, it maybe more unstable than usual" (`docs/changelog.md:30`) |
| Win32 | raw Win32 | IMM32 (`WM_IME_*`, `windows/window.rs:2002-2083`) | PerMonitorV2 via manifest; **no `WM_DPICHANGED` handler**, DPI re-read on `WM_WINDOWPOSCHANGED` (`window.rs:264-266, 1554-1563`) | Keys translated by hand with `ToUnicode` (`window.rs:2234-2854`); custom frame via `DwmExtendFrameIntoClientArea` |
| macOS | Cocoa/objc | `NSTextInputClient` | backing scale | EGL (ANGLE) first, then CGL |

Key encoding lives in the terminal, not the window layer:
`term/src/terminalstate/keyboard.rs:64`, `wezterm-input-types/src/lib.rs:1642`
(win32-input-mode) and `:1711` (kitty).

---

## 9. Windows specifics

### 9.1 ConPTY

- `pty/src/win/pseudocon.rs` loads `CreatePseudoConsole`/`ResizePseudoConsole`/
  `ClosePseudoConsole` dynamically. It **prefers a sideloaded `conpty.dll`** next to
  the executable over `kernel32.dll` (`:44-58`), and ships `conpty.dll` +
  `OpenConsole.exe` built from the Windows Terminal repo in
  `assets/windows/conhost/`. The README there says the inbox ConPTY lacked mouse
  reporting at the time (#1927). Requires Windows 10 1809+.
- Flags: `INHERIT_CURSOR | RESIZE_QUIRK | WIN32_INPUT_MODE` (`pseudocon.rs:84-87`).
  `PASSTHROUGH_MODE` (0x8) is defined but `#[allow(dead_code)]` (`:28-29`), so
  WezTerm does not use ConPTY's newer VT passthrough.
- `WIN32_INPUT_MODE` means ConPTY asks the terminal (DECSET 9001) to send keys as
  `CSI … _` win32 key records; WezTerm implements that encoding
  (`wezterm-input-types/src/lib.rs:1642`, `allow_win32_input_mode` config) so that
  console apps get full key events.
- **ConPTY quirks in the core:** `Terminal::enable_conpty_quirks()`
  (`term/src/terminalstate/mod.rs:601-604`) is set when the pane's PTY system is
  ConPTY (`mux/src/domain.rs:257-268, 628-630`). It (a) suppresses ConPTY's initial
  title OSC, (b) keeps scrollback immutable on resize (§6.4), and (c) avoids marking
  lines as soft-wrapped when the last cell is a space or symbol (§6.4). These are
  exactly the "ConPTY rewrites your stream" problems S§10 lists; WezTerm's answer is
  to special-case them in the model.
- `ClosePseudoConsole` is called from `Drop` (`pseudocon.rs:70-75`).

### 9.2 SSH avoids all of that

An SSH pane on Windows is a `LocalPane` over `SshPty`, so there is **no ConPTY in the
path** and no conpty quirks are enabled for it. This is the same reasoning as S§3.2,
and WezTerm's code confirms it works in practice. AF_UNIX sockets on Windows
(`uds_windows`) are used for the mux socket and for agent forwarding.

### 9.3 Rendering on Windows

- Default **WGL** with the vendor's `opengl32.dll`. `default_prefer_egl() =
  !cfg!(windows)` (`config/src/config.rs:1894-1896`); the comment says "EGL on Windows
  has jankier resize behavior than WGL … but EGL survives graphics driver updates"
  (`:537-542`). The docs (`prefer_egl.md`: "The default is `true`") and an old
  changelog entry preferring ANGLE disagree with the code.
- Bundled alternatives: ANGLE `libEGL.dll`/`libGLESv2.dll` (EGL over D3D11) and Mesa
  `opengl32.dll` (software). WebGpu gives DX12/Vulkan.
- Fonts: DirectWrite for discovery and fallback, FreeType for rasterization (§7.4).
  No DirectWrite rendering.

---

## 10. Configuration (Lua) and reload

- Config is a Lua script (`wezterm.lua`) that returns a table; `config/src/lua.rs` and
  `lua-api-crates/` expose a large API (wezterm.*, events, key tables, plugins).
- A global `configuration()` returns an `Arc` snapshot; generations are counted so
  caches can be invalidated (`config/src/lib.rs:474-690`).
- **Live reload:** the `notify` crate watches the config file plus any paths the
  script registers (`wezterm.add_to_config_reload_watch_list`), reloads on change and
  notifies subscribers (`config/src/lib.rs:505-623`).
- Lua callbacks (tab titles, status bar, exec domain fixups, `format-window-title`…)
  run **on the GUI thread** (`config::with_lua_config_on_main_thread`, e.g.
  `mux/src/domain.rs:339-358`). A slow user callback therefore slows rendering.
  **Inference** from the threading; I didn't search the issue tracker for complaints.
- Config affects the terminal model via `TerminalConfiguration` (`term/src/config.rs`),
  so the core stays independent of Lua.

---

## 11. Challenges, workarounds and things that went wrong

| Area | What happened | Source |
|---|---|---|
| Release cadence | Last tagged release Feb 2024; everything since is nightly | `docs/changelog.md:15-22, 364` |
| Two SSH libraries | Duplicated connect/auth/host-key code; features only on one backend (keepalive, agent forwarding, signals); default switched to libssh | §3.1 |
| SSH config fidelity | Token expansion bugs repeatedly (#2448, #3437), `Match` partly implemented, typo disables `UserKnownHostsFile` expansion, ProxyJump unsupported | §3.2 |
| SSH lifecycle | fd leaks (#2466), hangs on auth (#2194), endless loop after drop (#857), deadlock on detach after timeout (#6749), panics on canceled prompts | §3.4, §3.11 |
| Windows sockets | First char after keyboard-interactive swallowed (#771); writer swap workaround | `mux/src/ssh.rs:1108-1119` |
| Mux protocol | Exact version match; whole-line deltas; unbounded send queue; id translation bugs on reconnect (#781, #2614, #2616, #2759); images unusable over mux until #1237; lost updates race #5981 | §4 |
| Local echo | Password heuristic is a substring test for "sword"; vim normal mode unsolved | `wezterm-client/src/pane/renderable.rs:148-163` |
| tmux | Long incomplete (#336), then a 2025 contributor push; still drops out on unknown lines, no flow control | §5 |
| Synchronized output | Hold has no timeout | §1.3 |
| ConPTY | Needed sideloaded OpenConsole for mouse; resize and wrap quirks special-cased in the model | §9.1 |
| GPU | WebGpu as default was reverted; DX12 crash on Win11 (#4279); RDP forces software GL; EGL vs WGL trade-off on Windows | §7.1, §9.3 |
| CPU renderer | Own CPU renderer removed in favor of llvmpipe | `docs/changelog.md:2242-2250` |
| Fonts | Memory blow-up loading system fallback fonts (#559); slow fontconfig fallback, fixed by async fallback and coverage caching | `docs/changelog.md:1905, 2058` |
| Flicker | Unsynchronized TUIs tear; 3 ms coalesce delay added (#2443) | §1.3 |
| Wayland | Being reimplemented as of this commit | `docs/changelog.md:30` |
| Docs drift | `prefer_egl` default, tmux DCS final byte, "multiplexing is young" | §5.4, §9.3 |

---

## 12. Lessons for puritty

### 12.1 The backend interface

1. **Use two layers, like WezTerm.** A byte-level backend (read, write, resize,
   exit status, close) under one terminal-surface type that owns the parser, state
   and renderer feed. PTY, ConPTY, SSH channel and tmux pane are all byte-level
   backends. WezTerm's `MasterPty` + `LocalPane` split is the proof that one terminal
   implementation can serve all of them, and that `tmux -CC` over an embedded SSH
   channel then works with no special code.
2. **Make the byte-level interface message-based, not blocking-`Read`-based.** WezTerm
   adapts SSH channels and tmux `%output` into blocking readers through socketpairs
   and extra threads (3 threads and 2 socketpairs between the SSH socket and the
   parser). A `deliver(bytes)` callback or channel into the terminal's parser, plus a
   `write(bytes)` sink and a `resize(cols, rows, px)` call, fits all four backends and
   removes the copies.
3. **Don't put process concepts in the backend interface.** Make PID, foreground
   process, tty name and cwd optional capabilities. WezTerm's `todo!()` in
   `TmuxChild::try_wait` and the `None`s on SSH show the cost of a process-shaped API.
4. **Give the backend structured input when it wants it.** The tmux backend should
   receive key bytes in batches (one `send-keys -H` per burst, not per write), and
   possibly logical events if you later want tmux key-table semantics.
5. **Copy the "pane is the dialog" pattern** for SSH: return the pane immediately,
   run host-key and auth prompts as text in it, then swap in the real channel. It
   avoids modal dialogs, works the same over RDP, and keeps errors visible in the
   pane. Pair it with a proper GUI dialog only for the scary case (host key changed).
6. **Keep a `Domain`-like owner per connection** (local, SSH host, tmux session) that
   creates panes, tracks attach/detach state and knows how to split. WezTerm's
   `Domain::split_pane` / `spawn` round-trip for tmux (send the command, create the
   native split when tmux's notification arrives) is the right flow.

### 12.2 Embedded SSH (Windows)

7. **Pick one SSH implementation.** WezTerm's dual libssh/libssh2 setup created drift
   and duplicate bugs. Use one implementation, ideally one native to the chosen
   language so that channel I/O can be integrated with the backend interface
   directly (S§10).
8. **Treat `ssh_config` as a feature with tests.** WezTerm's parser is decent
   (Host, Include, tokens, most Match criteria) but has semantic gaps (Match User
   uses the local user, no `canonical/final`, typo-level bugs, `%i` empty on
   Windows). Write a table-driven test suite against `ssh -G host` output from real
   OpenSSH; that is the oracle.
9. **Implement what WezTerm didn't, because Windows users will need it:** ProxyJump
   natively, the Windows OpenSSH named-pipe agent and Pageant, a connect timeout,
   `ServerAliveCountMax` with real dead-connection detection, terminal modes in
   `pty-req`, and reconnect UX (show "disconnected" in the pane, offer reconnect;
   with tmux `-CC` this becomes reattach).
10. **Connection sharing works as WezTerm does it**: one session per host and one
    channel per pane, with no re-auth for new tabs. But don't run blocking requests
    on the I/O loop: opening a channel must not stall other channels' traffic.
11. **Env and TERM:** most servers reject SSH `env` requests. WezTerm's
    `assume_shell = "Posix"` trick (prefix `env K=V` to the command) is a pragmatic
    fallback; decide per host. Send `TERM` in `pty-req` and choose it per host
    (S§8).
12. **Verify host keys strictly from day one.** WezTerm's libssh2 path skips
    verification when no known_hosts file exists. Honor `StrictHostKeyChecking`,
    `UserKnownHostsFile` (all entries), and `GlobalKnownHostsFile`.

### 12.3 Multiplexing over slow links

13. **The seqno + StableRowIndex model is worth copying** even without a mux server.
    It gives one dirty-tracking mechanism for the local renderer, for remote X11
    damage, and for any future network protocol.
14. **If you ever ship screen state over a network, add scroll operations and
    bounded queues.** WezTerm resends whole lines (scrolling dirties every row),
    pushes on every output event, and has an unbounded per-client queue. The fixes:
    at most one outstanding update per pane per client, computed when the
    transport is writable ("latest state wins"); explicit scroll deltas; cell-run
    diffs. The same rules apply to the remote-X11 renderer, where the X connection is
    the slow link.
15. **Predictive local echo is feasible and valued, but needs care.** WezTerm's design
    (RTT gate at 100 ms, underline predicted cells, overwrite on the next real update,
    input serials to drop stale cursor positions) is a good start. Improve on it by
    only predicting when the terminal is in a state where echo is likely (cooked
    line, no alt screen, not after a password-looking prompt or with echo off), and
    by confirming predictions mosh-style. With tmux `-CC` over SSH this is the place
    it would help most.
16. **Version handshakes should negotiate, not demand equality.** If puritty ever has
    a helper on the remote side (terminfo installer, persistent session helper),
    design capability negotiation up front.

### 12.4 tmux control mode

17. **WezTerm complements Ghostty as a reference**: correct `vis` unescaping and a
    full notification grammar (Ghostty lacks the former), working GUI round-trips
    for new-window/split/select. Port its grammar coverage into tests.
18. **Avoid its mistakes:** fatal on unknown lines, FIFO matching without checking
    `%begin` numbers, two commands sharing one reply slot, single-chunk backlog,
    a blocking write into a pane while holding the control lock, layout applied only
    at attach, no `pause-after` flow control, no kill/detach from the GUI, window
    names parsed by splitting on spaces (use `-F` with a delimiter that can't appear,
    or tmux's `#{q:…}` quoting).
19. **Map tmux layouts to an n-ary split tree** or accept nested binary splits as
    WezTerm does; either way, apply sizes *from* tmux on every `%layout-change` (S§7.3).

### 12.5 Terminal core and rendering

20. **Cell model:** WezTerm's 24-byte cell with an inline 7-byte grapheme string is a
    middle ground between Alacritty (no clusters) and Ghostty (8-byte cells + side
    tables). Its per-line "compress on scroll-off" (one string + attribute runs) is a
    simple scrollback-memory win worth copying even with a Ghostty-style page design.
21. **Parser:** don't build an owned `Action` per sequence on the hot path; dispatch
    directly as Ghostty does. Keep an `Action`-like value type for tests and
    recording.
22. **Synchronized output needs a timeout**; WezTerm's hold has none.
23. **Async font fallback** (render now, redraw when the fallback font is found) keeps
    fontconfig/DirectWrite latency off the frame path. Copy it.
24. **Procedural box-drawing and block glyphs** fit cells exactly and avoid font gaps;
    WezTerm, Ghostty and Windows Terminal all do it.
25. **Remote X11 gets nothing from WezTerm.** Its renderer is EGL/WGL/wgpu with a
    full rebuild every frame (cached per line on the CPU side), RENDER only for
    cursors, and Mesa llvmpipe as the "software" mode. That reinforces S§6: the
    server-side X11 backend is puritty's own work.
26. **Windows rendering:** WezTerm's experience (WGL default because EGL/ANGLE
    resizes badly; WGL dies on driver updates; DX12 via wgpu crashed on some Win11
    systems; RDP needs software GL) argues for a native D3D11 renderer on Windows
    rather than GL, as S§10 suggests. Detect RDP and adapt.
27. **ConPTY:** if you support local shells, sideload a recent `conpty.dll`/OpenConsole,
    consider `PSEUDOCONSOLE_PASSTHROUGH_MODE` on new enough builds (WezTerm never
    enabled it), implement win32-input-mode, and expect to special-case resize and
    soft-wrap behavior in the model as WezTerm does.

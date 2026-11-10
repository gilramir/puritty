# The built-in ssh client: a survey (2026-11-10)

Gilbert, 2026-11-10: the Windows build gets an ssh client of its own,
started from the same `[hosts."name"]` entries that start OpenSSH today
(`settings.md` ST10, ST23, ST24), in place of `ssh.exe` on the pseudo
console. This survey says what an ssh client is, what Geng has toward one,
what was measured on nene, the main decision with its options, and the order
to build it in. Sections are SC1, SC2, and so on; the questions for Gilbert
are last (SC12), each with a leaning.

What was measured is marked so. Facts about protocols and libraries that
were not checked here are marked "general knowledge"; what was reasoned and
not run is marked "inferred". Nothing here connected to another host, and
nothing ran on beelink1.

## SC1 · Why a client of its own

Three reasons, each already written down elsewhere:

- **ConPTY sits between ssh and puritty.** Today a session is `ssh.exe` on
  a pseudo console (WS9, WS20, ST23). Conhost parses everything into its own
  buffer, translates input through `INPUT_RECORD`s, reflows separately on a
  resize, and can stall a DSR-CPR for about 500 ms (`synthesis.md` §10.1).
  An ssh channel needs none of it: the bytes from the server are already
  the terminal's bytes.
- **EUC-KR cannot pass through ConPTY.** ConPTY carries a program's output
  as UTF-16, so invalid UTF-8 becomes U+FFFD before puritty sees it
  (`synthesis.md` §10.1). An EUC-KR host (`cjk-and-thai.md` §10) therefore
  does not work on Windows today, while on Linux `ssh` on a pty passes the
  bytes and puritty's charset filter works (ST10). A built-in client hands
  the channel's bytes straight to the same filter.
- **The product.** The Windows product replaces PuTTY and MobaXterm
  (`feature-plan.md` §2): a host list, quick connect, passwords in the
  credential store, reconnect, later file transfer. Each needs the
  session's state in puritty, not in a child process.

It is a Windows feature. It is built and tested on Linux too, since the
gates run here (SC10), and whether Linux users get it is question 5.

## SC2 · What an ssh client is, layer by layer

SSH-2 is three layers over TCP (RFC 4251 §1). PuTTY builds them as a stack
of coroutines joined by packet queues (`putty.md` §2.1); the layering is
what matters, not the coroutines.

**Transport** (RFC 4253):

- *Version exchange* (§4.2): `SSH-2.0-…` lines, with lines before the
  server's version allowed. The server's version string keys the server-bug
  table (`synthesis.md` §10.2).
- *Binary packets* (§6): length, padding, payload, MAC; sequence numbers
  that wrap at 2^32. With an AEAD cipher the length is the associated data
  (RFC 5647 for AES-GCM; OpenSSH's `PROTOCOL.chacha20poly1305`, where the
  length is encrypted with a second key).
- *Algorithm negotiation* (§7.1): two `KEXINIT`s, first match from the
  client's lists. The guessed-packet rule (`first_kex_packet_follows`).
- *Key exchange*: curve25519-sha256 (RFC 8731, over X25519 of RFC 7748).
  The exchange hash, the server's host-key signature over it, and the six
  derived keys (§7.2).
- *`NEWKEYS`*, then everything under the new keys.
- *Strict KEX* (`kex-strict-c-v00@openssh.com`, OpenSSH's `PROTOCOL`), the
  Terrapin fix (CVE-2023-48795): sequence numbers reset at `NEWKEYS`, and no
  stray packets allowed during the first exchange (`putty.md` §3.4).
- *Extension negotiation* (RFC 8308): `ext-info-c` in the client's list,
  and the server's `server-sig-algs`, without which an RSA key cannot be
  used with SHA-2 (RFC 8332).
- *Rekey* (§9; RFC 4344 §3): after 1 GB or an hour, or when the server asks.
  Channel output waits while a rekey runs, so channels never see one
  (`putty.md` §2.1, §3.3). The host key must not change in a rekey.
- `IGNORE`, `DEBUG`, `UNIMPLEMENTED`, `DISCONNECT` with its reason codes.

**User authentication** (RFC 4252):

- `none` first, to learn the methods the server allows.
- *publickey* (§7): a query without a signature first, and the passphrase
  asked only if the server answers `PK_OK` (`putty.md` §5.1). The signature
  algorithm for RSA is `rsa-sha2-256` or `-512` (RFC 8332), never SHA-1.
- *password* (§8), with the password-change request.
- *keyboard-interactive* (RFC 4256): any number of rounds of prompts.
- Partial success, the pre-auth banner, and `MaxAuthTries`: try only the
  configured identity when there is one (`putty.md` §5.1).

**Connection** (RFC 4254):

- A *session channel* (§6.1) with its window and maximum packet size, and
  `WINDOW_ADJUST` (§5.2) tied to how fast the terminal parses (`putty.md`
  §1.3, §2.3).
- *`pty-req`* (§6.2): `TERM`, the size in cells and pixels, and the
  terminal modes (§8). Mode 42, `IUTF8` (RFC 8160), is the one that matters
  here: on for a UTF-8 host, off for an EUC-KR one, so the remote line
  editor erases a character by its own encoding.
- *`env`* (§6.4), which most servers refuse (`synthesis.md` §10.2).
- *`shell` or `exec`* (§6.5), pipelined with `pty-req` and `env` in one
  round trip (`putty.md` §2.3).
- *`window-change`* (§6.7) on every resize; *`signal`* (§6.9); *`break`*
  (RFC 4335).
- *`exit-status` and `exit-signal`* (§6.10), then `EOF` and `CLOSE`.
- *Global requests*: `keepalive@openssh.com` with want-reply, so a dead
  server is noticed (`putty.md` §7); later `hostkeys-00@openssh.com`
  (OpenSSH's UpdateHostKeys).
- *`direct-tcpip`* (§7.2): the channel ProxyJump runs the next hop over
  (`putty.md` §6.4).

**Around the protocol:**

- *known_hosts* (sshd(8), "SSH_KNOWN_HOSTS FILE FORMAT"): patterns with `*`,
  `?` and `!`, `[host]:port`, `@cert-authority` and `@revoked` markers, and
  hashed names `|1|salt|hash`, whose hash is HMAC-SHA1. Ubuntu and Debian
  hash by default (general knowledge), so a file copied from Linux needs
  SHA-1's HMAC to be read.
- *Key files*: OpenSSH's own format (`PROTOCOL.key`), whose passphrase is
  turned into a key by `bcrypt_pbkdf` (Blowfish and SHA-512) and whose
  cipher is `aes256-ctr` (measured: a key made by `ssh-keygen -t ed25519 -N
  …` on nene says `aes256-ctr` and `bcrypt` in its header). Old RSA keys in
  PEM (PKCS#1 with `DEK-Info`, PKCS#8) still exist. Public keys in RFC 4716
  and OpenSSH's one-line form.
- *Agents* (`draft-ietf-sshm-ssh-agent`, formerly draft-miller): on
  Windows, OpenSSH's agent at `\\.\pipe\openssh-ssh-agent` and Pageant at a
  per-user pipe name derived with `CryptProtectMemory` and SHA-256, with
  `WM_COPYDATA` for old Pageants (`putty.md` §5.3).
- *`~/.ssh/config`* (SC7).

### SC2.1 · The algorithms

OpenSSH on nene (9.6p1) offers these by default (measured, `ssh -G`):

| | offered, in order |
|---|---|
| kex | `sntrup761x25519-sha512@openssh.com`, `curve25519-sha256`, `curve25519-sha256@libssh.org`, `ecdh-sha2-nistp256/384/521`, `diffie-hellman-group-exchange-sha256`, `-group16-sha512`, `-group18-sha512`, `-group14-sha256` |
| host keys | the `-cert-v01` forms, then `ssh-ed25519`, `ecdsa-sha2-nistp256/384/521`, the two `sk-` forms, `rsa-sha2-512`, `rsa-sha2-256` |
| ciphers | `chacha20-poly1305@openssh.com`, `aes128/192/256-ctr`, `aes128/256-gcm@openssh.com` |
| MACs | `umac-64/128-etm`, `hmac-sha2-256/512-etm`, `hmac-sha1-etm`, then the same without `-etm` |

What a modern OpenSSH server accepts is the same set (general knowledge;
RFC 9142 is the IETF's view of which kex methods are current). OpenSSH 9.9
added `mlkem768x25519-sha256`, and 10.0 made it the default (general
knowledge). A server still accepts curve25519, so post-quantum kex is not
needed to connect; newer OpenSSH clients warn when it is not used (general
knowledge), which users will compare puritty with.

**Proposed for the first version**, the smallest set that every OpenSSH
server since about 6.5 (2014) takes:

| | algorithms | primitives |
|---|---|---|
| kex | `curve25519-sha256` (and its `@libssh.org` alias) | X25519, SHA-256 |
| host keys (verify) | `ssh-ed25519`, `rsa-sha2-512`, `rsa-sha2-256`, `ecdsa-sha2-nistp256` | Ed25519, RSA PKCS#1 v1.5 with SHA-2, P-256 ECDSA |
| ciphers | `chacha20-poly1305@openssh.com`, `aes256-gcm@openssh.com`, `aes128-gcm@openssh.com` | ChaCha20 (64-bit nonce), Poly1305, AES, GHASH |
| MACs | none needed with an AEAD cipher | |
| user keys (sign) | Ed25519, RSA with SHA-2; ECDSA P-256 | the same, private side |
| key files | OpenSSH format, unencrypted or `aes256-ctr` + `bcrypt_pbkdf` | AES-CTR, Blowfish, SHA-512 |
| known_hosts | plain and hashed names | HMAC-SHA1 |
| extensions | `ext-info-c`, `server-sig-algs`, strict KEX, `keepalive@openssh.com` | |

Two cases want more, and SC12 asks about both:

- **RHEL8 in FIPS mode** has no curve25519, Ed25519 or ChaCha20 (general
  knowledge about RHEL's crypto policies; not measured). It needs
  `ecdh-sha2-nistp256` (RFC 5656) or `diffie-hellman-group14-sha256` (RFC
  8268), AES-GCM or AES-CTR with `hmac-sha2-256-etm`, and RSA or ECDSA host
  keys. Gilbert's EUC-KR colleagues' hosts are RHEL8 (`cjk-and-thai.md`
  §10); whether they run FIPS mode is not known here.
- **Post-quantum kex**, `mlkem768x25519-sha256`: ML-KEM-768 and SHA3.

## SC3 · What Geng has today

**Sockets: none.** `os` exposes `Os.Directory`, `Os.Env`, `Os.Error`,
`Os.File`, `Os.Path`, `Os.Process` and `Os.Signal`
(`packages/os/geng.toml`); its C, on both platforms, has no `socket`,
`connect`, `getaddrinfo` or Winsock call (searched). geng-lang
`m3-native.md` lists `Os.Net` as "post-M3", and `open-items.md` has
"puritty's ssh client" as puritty's own item, "to be registered in puritty
when it starts". **DNS: none** either.

What the runtime gives a socket row is enough (`packages/c-backend/runtime/geng.h`):

- On Linux, `geng_io_wait(fd, POLLIN | POLLOUT, …)` beside the timers, in
  the loop's `ppoll`. A non-blocking `connect` waits for `POLLOUT`; reads
  and writes wait on `EAGAIN`, as a pty's do.
- On Windows, a handle bound to the loop's completion port
  (`geng_overlapped_bind`) and an operation per read or write
  (`geng_overlapped_new`). A socket made with `WSA_FLAG_OVERLAPPED` binds as
  a pipe does; `ConnectEx`, `WSARecv` and `WSASend` complete through it.
- Blocking work, `getaddrinfo` on Linux, goes on a C thread
  (`geng_thread_start`) that answers through a post (D897). Windows'
  `GetAddrInfoExW` can complete by itself, through
  `geng_overlapped_post`.
- `Os.File`'s rule that a read which loses a `Task.race` keeps what it took
  (D1045) is what a socket needs too, since `Main` races its read every
  turn (SC8).

**The `crypto` package is WebCrypto, and JavaScript only.**
`packages/crypto` is 2,904 lines of Geng over one `Ext/Crypto.js`, with no C
row; geng-lang `m3-native.md` and `m3-closeout.md` both list it as having
"`js` rows only". Its API, behind a `SecureContext` and every call a `Task`:

| primitive | in `crypto` | SSH needs it |
|---|---|---|
| SHA-256, -384, -512 (`digest`) | yes; SHA-1 is left out on purpose | SHA-256, SHA-512; SHA-1 for hashed known_hosts |
| HMAC (`generateHmacKey`, sign, verify) | yes, SHA-2 | HMAC-SHA1, HMAC-SHA2 (the `-etm` MACs, later) |
| AES-CTR, AES-CBC, AES-GCM | yes | AES-GCM; AES-CTR for key files |
| RSA-OAEP, RSA-PSS, RSASSA-PKCS1-v1_5 | yes | PKCS1-v1_5 with SHA-256/512, exactly `rsa-sha2-*` |
| ECDSA (P-256/384/521) | yes | P-256 |
| Ed25519 | generate, import, export, sign, verify | yes |
| PBKDF2 | yes | no |
| X25519 | **no** | the kex |
| ChaCha20, Poly1305 | **no**, and WebCrypto has neither | the default cipher |
| Blowfish, `bcrypt_pbkdf` | **no** | encrypted key files |
| random bytes | `getRandom…Values`, through the host | yes |

So the package covers more than half of SSH's primitives by name, but none
of them natively, and its shape does not fit a packet loop: each call is a
`Task` and each key a host object, where a cipher wants a pure function from
bytes to bytes, run tens of thousands of times a second.

**Secure random: eight bytes, for seeding.** `core`'s
`Random.seedFromEntropy` reads `getrandom(2)` on Linux and `rand_s` on
Windows, as two `UInt32`s (`core/src/Ext/*/geng_core_random.c`). There is
no "n bytes from the system's generator" on native. The rows exist; a
`Bytes` form of them is small.

**Arithmetic is enough for ChaCha20, SHA-2 and Poly1305.** `Int` is 32 bits
and wraps (`arithmetic.md` A6); `UInt32`, `UInt64` and `Int64` exist, and
`Bitwise` works on all four (A5). Poly1305 and X25519 in 26-bit or 51-bit
limbs need 32×32→64 multiplies, which `UInt64` gives. **There are no big
integers**, which RSA needs (2048 to 4096 bits) and DH groups would.

**Bytes:** `Bytes.get` is checked or proved in range (the refinement
checker, D863), and `Bytes.Transient` is written in place (affine, D921).
A parser of packets from a hostile server cannot read out of bounds.

**Constant time: nothing promises it.** Geng compiles to C through passes
that inline and specialise; nothing says a branch-free Geng function stays
branch-free, and `Bytes` equality is a `memcmp` that stops early (assumed;
`primEq`). Secret-dependent table lookups, AES's classic tables, are out in
any language.

**Secrets cannot be wiped.** `Bytes` are immutable and the collector frees
them when it likes. A password or a private key that becomes a Geng value
stays in the heap until reused, and may reach swap or a crash dump. C holds
memory it can clear.

**Named pipes: workable.** `Os.File.open` on a path that is a pipe reads it
on a thread of its own (`os/src/Ext/windows/geng_os_file.c`'s header), so
`\\.\pipe\openssh-ssh-agent` can be opened and spoken to today, slowly but
correctly. Pageant's pipe name needs `CryptProtectMemory`, a C row.

**The Windows credential store** (`CredReadW`, `CredWriteW`) is not
wrapped. It belongs in `packages/win32`.

## SC4 · Measured on nene

All on nene (Ryzen 9 9950X). beelink1, where the client will run, was not
touched, and its speed at these is not known; step 3 (SC11) measures there.

**ChaCha20 in Geng.** A probe written for this survey (in the session's
scratch directory, not committed): RFC 8439's block function over `Int`,
the state a record of sixteen words, 20 rounds, the keystream XORed into a
`Bytes.Builder` byte by byte, over a 16 MiB file, ten times. Built as
`probes/base64` builds (the core-bench passes). Its first output byte for
RFC 8439 §2.3.2's key, nonce and counter is `0x10`, as the RFC's is, and a
C version of the same loop gives the same checksum over the 16 MiB.

| ChaCha20 over 160 MiB | ms | MB/s |
|---|---:|---:|
| Geng, as above, three runs | 635, 616, 613 | ≈ 270 |
| C, the same loop, `clang -O2`, scalar | 167, 160, 167 | ≈ 1,000 |
| OpenSSL 3.0.13's `chacha20-poly1305`, 16 KiB blocks | | 7,000 (and Poly1305) |
| OpenSSL's `aes-128-gcm`, 16 KiB blocks | | 32,000 |

Geng is 3.8 times scalar C here. For scale, puritty's core parses `ls` and
`gitlog` at 108 to 124 MB/s (`geng-plan.md` §1.3): a Geng ChaCha20 alone
would add about 40% to the CPU of a `cat` over ssh, before Poly1305 (not
measured; its 130-bit multiplies in `UInt64` limbs are likely slower per
byte than ChaCha20). Scalar C adds about 10%. Either is far above what a
network gives; the cost is CPU and battery, not speed.

**Public-key operations, OpenSSL on nene** (`openssl speed`): RSA-2048
sign 0.16 ms, verify 10 µs; Ed25519 sign 17 µs, verify 45 µs; X25519 18 µs.
A connection does a few of these, so in C they never matter. In Geng
without a bignum, RSA would have to be written first, and a constant-time
modular exponentiation in Geng is the hardest part of option B (SC5).

**Decrypting a key file.** `ssh-keygen -y` on an Ed25519 key with a
passphrase: 0.10 s at the default 16 rounds of `bcrypt_pbkdf`, three runs;
0.41 s at `-a 100`; 0.00 s without a passphrase. Whatever does this must
not run on the loop, or a frame and the window's events wait for it: a C
thread and a post (D897), as font fallback does (`geng-plan.md` §3.1).

**Libraries** (nixpkgs at puritty's pin, built for Linux):

| | version | licence | `.so` | C lines in `src/` | crypto from |
|---|---|---|---:|---:|---|
| libssh2 | 1.11.1 | BSD-3-Clause | 336 KB | 45,271 | OpenSSL, mbedTLS, libgcrypt, WinCNG, OS/400 |
| libssh | 0.12.2 | LGPL-2.1 | 702 KB | 81,435 | OpenSSL, mbedTLS or libgcrypt, plus its own 25519, ChaCha, Poly1305, ML-KEM, sntrup |
| OpenSSL libcrypto | 3.6.4 | Apache-2.0 | 7.6 MB | | |
| libsodium | 1.0.22 | ISC | 683 KB | | |
| Monocypher | 4.0.3 | BSD-2 or CC0 | 74 KB | 3,491 | |
| PuTTY's `crypto/`, the subset SSH needs (33 files) | vendored, 2026-10-14 | MIT | 180 KB of text as objects | 13,997 | |

PuTTY's subset (AES with AES-NI, AES-GCM with CLMUL, ChaCha20-Poly1305,
the curve arithmetic for X25519, Ed25519 and P-256, `mpint`, RSA, RFC 6979,
SHA-1/256/512 with SHA-NI, HMAC, Blowfish, `bcrypt`, its PRNG, ML-KEM)
compiled here with `clang -O2` straight from `vendor/putty`, once the
x86 files were given `-maes -mpclmul -mssse3 -msse4.1 -msha`. Linked
together, it leaves 47 symbols undefined that are not libc's, all from
PuTTY's `utils/` (`BinarySink_*`, `strbuf_*`, `smemclr`, `safemalloc`,
`ptrlen_*`) or from files left out (SHA-3, MD5, NTRU). Measured as built;
not linked into a program or tested.

From the libraries' sources (read here):

- **libssh2's kbd-interactive callback is synchronous** (`userauth.c`:2241):
  the library calls it in the middle of `libssh2_userauth_keyboard_interactive`,
  and it must fill in the answers before it returns. An async prompt means
  a thread that blocks, or a second connection.
- **libssh2 on WinCNG has no Ed25519 and no AES-GCM** (`wincng.h`:64, :74),
  and its curve25519 kex is compiled only with Ed25519 (`kex.c`:2490). On
  Windows without OpenSSL it cannot speak puritty's proposed set. It does
  speak to OpenSSH's agent pipe (`agent_win.c`:124) and to Pageant by
  `WM_COPYDATA` (`agent.c`:340), but not Pageant's pipe.
- **libssh's agent is a Unix socket only** (`agent.c`, `SSH_AUTH_SOCK`,
  `AF_UNIX`): neither Windows agent. Its non-blocking API answers
  `SSH_AUTH_AGAIN` and its keyboard-interactive is a state
  (`SSH_AUTH_INFO`, prompts read and answers set between calls), which an
  async UI can drive; it has `ssh_userauth_try_publickey` for the query
  before the passphrase. Its kex list has the ML-KEM hybrids and sntrup761.

## SC5 · The main decision: who speaks SSH

Five routes. Gilbert's priorities, from the project notes: correctness over
everything; a crash is the worst failure, a leak second; native should be
fast; and code in Geng is part of the point.

**A. The protocol in Geng; the primitives in C.** Transport, kex, userauth,
connection, known_hosts, key files and `~/.ssh/config` are Geng: a pure
session, `step : Input -> Session -> { session, output, events }`, the way
`Vt.feed` is the terminal (SC8). The primitives (SC2.1's right-hand column)
are `@externPure(c, …)` functions over `Bytes` in a package of their own.

- *Correctness and crashes:* every byte from the server is parsed by Geng,
  where an index out of range is refused by the checker and nothing can
  overrun a buffer. That is where SSH clients' worst bugs have been: libssh2's
  CVE-2019-3855 family were integer overflows in packet parsing that led to
  writes out of bounds (general knowledge). The C left is the primitives,
  whose inputs are fixed-size keys and buffers, and which are tested by
  known answers.
- *Speed:* ciphers at C's speed, with AES-NI where the library has it.
- *Geng:* everything that decides something is Geng, which is puritty's
  rule (`geng-plan.md` §3.2).
- *Async UX:* the session is a value. A host-key question or a password
  prompt is an event out and an answer is an input; nothing in it can
  block, and other work in the loop goes on (`synthesis.md` §10.2,
  `putty.md` §2.2).
- *Tests:* a pure session replays. With its random bytes drawn from a
  generator seeded once, a recorded conversation with a real sshd replays
  byte for byte with no network (SC10), as the replay corpus replays the core.
- *Cost:* the most work of the five. A Geng SSH client of SC2's scope is
  perhaps 4,000 to 6,000 lines (inferred from PuTTY's and libssh2's
  protocol files, less their crypto, SSH-1 and SFTP).

**B. Everything in Geng, crypto too.** As A, with the primitives written in
Geng.

- ChaCha20 runs at 270 MB/s (SC4), so throughput is acceptable.
- Constant time is not something Geng can promise (SC3). ChaCha20 and
  Poly1305 have no secret-dependent branches by construction, so they could
  be Geng; AES (without AES-NI, which Geng cannot reach), RSA signing and
  P-256 signing cannot be written safely without that promise and a bignum.
- Writing one's own crypto is what `putty.md` §3 advised against.

The honest version of B is A with ChaCha20-Poly1305 and SHA-2 later moved
into Geng, if measured fine and wanted. Not v1.

**C. A C library: libssh or libssh2.** One call does each layer, written and
tested by others.

- *libssh2* (BSD): synchronous auth callbacks (SC4), and on Windows it needs
  OpenSSL for curve25519 and Ed25519. Its own blocking or EAGAIN-style API
  fits a loop that owns the socket (it can be given send and receive
  callbacks).
- *libssh* (LGPL-2.1): the better API for an async loop, and the broader
  algorithms, but no Windows agent, and LGPL in a statically linked
  program means the user must be able to relink it.
- *Both:* the hostile input is parsed in C, in-process, where a bug is a
  crash or worse; WezTerm's two libraries show how features drift across a
  wrapper (`wezterm.md` §3.1); the session's state is the library's, so
  reconnect, the trust UX and replay tests sit around a black box; and on
  Windows each needs OpenSSL or mbedTLS built for it.

**D. OpenSSH, but over pipes: `ssh.exe -tt` with no pseudo console.**
puritty would start `ssh.exe` with its standard streams as pipes, so conhost
is not in the path. Reasoned, not run:

- *The bytes:* Win32-OpenSSH writes to a console as UTF-16 and to a pipe as
  bytes (inferred from how it treats a console), so EUC-KR would pass. Not
  tested.
- *The size:* `-tt` forces `pty-req`, but ssh learns the size from its
  console, and with pipes there is none. It would send a default or zero
  size and **never send `window-change`**, since it watches the console for
  a resize (inferred). A terminal that cannot resize its session is broken.
- *The prompts:* host-key questions and passphrases are read from the
  console too; `SSH_ASKPASS` with `SSH_ASKPASS_REQUIRE=force` could send them
  to a puritty helper (general knowledge), which is a second program to
  write and check.
- *Nothing else improves:* no reconnect, no credential store, no trust
  marker, no shared state.

D fails on the resize alone. A cheap test on beelink1 would confirm it
(SC12, question 1 does not depend on it).

**E. Port PuTTY's SSH whole, in C.** MIT, decades of Windows use, the
layering this survey admires. But it is 30,000 lines of C for the hostile
input, on PuTTY's own framework, against puritty's rule that C does only
what only C can (`geng-plan.md` §3.2). It is the C-library option with more
work and no upstream.

**Leaning: A.** It puts the hostile input in the memory-safe language,
keeps every decision in Geng, keeps the session testable and replayable,
and buys C's speed and C's constant-time care for exactly the primitives.
It is the most work, and the work is the kind this project does well: a
pure state machine with a corpus.

### SC5.1 · Which C for the primitives

No small library has all of SC2.1's primitives. The candidates:

| | covers | lacks | notes |
|---|---|---|---|
| **PuTTY's `crypto/`** (vendored) | all of SC2.1, plus ML-KEM, SHA-3, `bcrypt_pbkdf` | | MIT. Written to be free of secret-dependent timing (`mpint.c` says so of its exponentiation and division). AES-NI, CLMUL, SHA-NI chosen at run time. Compiles here standalone with 47 outside symbols (SC4). PuTTY's CVE-2024-31497, biased P-521 ECDSA nonces that leaked keys, is a reminder that it has had a serious flaw (general knowledge). |
| **OpenSSL libcrypto** | all of SC2.1 but `bcrypt_pbkdf` | Blowfish-based KDF (a 200-line file from OpenBSD) | The most examined and the fastest (SC4). 7.6 MB shared here; built for Windows by its own Perl-driven build, which puritty's zig cross-build would have to take on (not measured). |
| **Monocypher** + **BearSSL** | Monocypher: ChaCha20, Poly1305, X25519, Ed25519, SHA-512. BearSSL: AES (constant time, and AES-NI), GCM, RSA, P-256, SHA-1/256, HMAC | `bcrypt_pbkdf` | Both small, permissive and careful about timing. Two upstreams; BearSSL's last release was 2018 (general knowledge). |
| **libsodium** | ChaCha20, Poly1305, X25519, Ed25519, SHA-2, HMAC-SHA2; AES-256-GCM only with AES-NI | RSA, P-256, AES-CTR, SHA-1 | ISC. Needs a second library for RSA. |
| Windows CNG (`bcrypt.dll`) | RSA, ECDSA, ECDH incl. Curve25519, AES-GCM, SHA, HMAC, random | Ed25519, ChaCha20, Poly1305 | Windows only, so the Linux gates would test other code (general knowledge for the list). |

**Leaning: PuTTY's `crypto/` subset**, wrapped in a thin C file that gives
Geng pure functions over bytes. It is the only one that is exactly SSH's
set, it is already in the tree and studied (`putty.md` §3), it is MIT, it
is careful about timing on the machines Windows runs on, and one upstream
can be watched the way geng-lang watches its forks. `putty.md` §3 said "use
a vetted library" against writing one's own; PuTTY's is vetted by use, if
not by audit. OpenSSL is the alternative if Gilbert would rather have the
most examined code and pay its size and build. Question 2.

## SC6 · The package boundary

Proposed:

- **`packages/ssh-crypto`** in puritty (or in geng-lang, question 3): the C
  wrapper over the primitives and its Geng module of `@externPure`
  functions, each total, with every length checked in Geng before the call:
  `chacha20 : key -> nonce -> counter -> Bytes -> Bytes`,
  `poly1305 : key -> Bytes -> Bytes`, `aesGcmSeal`/`Open`, `x25519`,
  `ed25519Verify`, `rsaVerify`, `ecdsaP256Verify`, the signers, `sha256`,
  `sha512`, `hmacSha1`, `bcryptPbkdf`, and a constant-time `equal`. An
  `Open` that fails answers `Nothing`; tag checks happen in C.
- **Secrets that live long stay in C.** A decrypted private key and a
  password kept for reconnect are C-held handles that are cleared when
  dropped; signing takes the handle. Session keys are Geng `Bytes`, which is
  accepted (question 7). `bcrypt_pbkdf` and RSA signing run on a C thread
  and answer through a post (SC4).
- **`Os.Net`** in geng-lang's `os` (question 4): `connect : Permission ->
  { host, port, timeoutMs } -> Task Error Socket` (DNS on a thread or by
  `GetAddrInfoExW`, the addresses tried in turn with Happy Eyeballs, RFC
  8305), `read`, `writeSome`, `writable`, `close`, `TCP_NODELAY` set, and the
  same race rule as `Os.File` (D1045). Linux and Windows together, as every
  `os` row is.
- **Secure random bytes**, `n` of them, in `core` or `os`: `getrandom` and
  `BCryptGenRandom` (or `ProcessPrng`).
- **`packages/ssh`** in puritty: the protocol, pure Geng, with no platform
  code, so it builds and is tested on Linux and runs on Windows unchanged.
- **`packages/win32`** gains the credential store and Pageant's pipe name.

## SC7 · `~/.ssh/config`

`SshConfig.aliases` lists `Host` names that are not patterns, and nothing
more (ST24). The built-in client needs the whole file, since a user's
`ProxyJump`, `User` and `IdentityFile` there must work as they do with
OpenSSH (`synthesis.md` §10.2). What the parser must do (ssh_config(5),
general knowledge, with what nene's `ssh -G` showed):

- **First value wins**, for most keywords, across the whole file in order;
  `IdentityFile`, `CertificateFile`, `LocalForward`, `RemoteForward` and
  `SendEnv` add up instead.
- **`Host` patterns** match the name as typed, with `*`, `?`, `!` and lists.
  *Measured:* `Host *.example.com` did not apply to `ssh build` whose
  `HostName` is `build.example.com`: its `ServerAliveInterval 30` stayed 0.
- **`Match`** criteria: `all`, `canonical`, `final`, `exec`, `host` (the
  name after `HostName`), `originalhost`, `user`, `localuser`,
  `localnetwork`, `tagged`. *Measured:* `Match host build.example.com user
  gilbert` did apply to `ssh build` (`forwardagent yes`), since `Match host`
  sees the `HostName`. `Match exec` runs a command (`cmd.exe` on Windows);
  WezTerm's `Match User` tested the local user by mistake (`wezterm.md`
  §3.2).
- **`Include`**, with globs; a relative path is under `~/.ssh` for the
  user's file, not beside the file that names it. *Measured:* an
  `Include extra.conf` in a `-F` file in another directory did not read the
  `extra.conf` beside it.
- **Tokens** (`%h`, `%p`, `%r`, `%u`, `%d`, `%C`, `%L`, `%l`, `%n`, `%i`,
  `%k`, `%j`, `%%`) in the keywords that take them, and `${VAR}` in some.
  *Measured:* `HostName %h.internal.example` gave `web1.internal.example`;
  `UserKnownHostsFile ~/.ssh/kh_%h_%p` printed as
  `/home/gram/.ssh/kh_web1.internal.example_22`, with `%h` the final host
  name; but `IdentityFile ~/.ssh/id_%r@%h` printed unexpanded, so `ssh -G`
  is an oracle for some expansions and not others.
- **Syntax:** keywords in any case, `=` or space, quoted arguments,
  comments, `CanonicalizeHostname` (which re-reads the file), and the system
  file (`%ProgramData%\ssh\ssh_config` on Windows) after the user's.
- **Keywords the client acts on in v1:** `HostName`, `User`, `Port`,
  `IdentityFile`, `IdentitiesOnly`, `IdentityAgent`, `ProxyJump`,
  `ProxyCommand` (later), `ServerAliveInterval`, `ServerAliveCountMax`,
  `ConnectTimeout`, `StrictHostKeyChecking`, `UserKnownHostsFile`,
  `HostKeyAlias`, `RequestTTY`, `RemoteCommand`, `SetEnv`, `SendEnv`,
  `ForwardAgent`, the algorithm lists. A keyword it does not act on is
  reported once, by name, not silently ignored.

**The oracle.** `ssh -F FILE -G HOST` prints the resolved settings, one per
line (82 lines for the first example), without connecting. A case is a
config, a host name and the lines expected; the expected lines are what
OpenSSH printed, recorded once and kept, and re-recorded with a note when
OpenSSH changes. The gate runs puritty's parser over every case and
compares the keywords it implements. `ssh -G` also prints to standard error
when standard input is not a terminal, which a recorder drops. The same
cases are worth recording on beelink1 with Windows' OpenSSH, since its
paths and `Match exec` differ.

A host entry in `config.toml` (ST10) is applied as if it were a `Host`
block before the file's, so a saved host and an alias resolve the same way
(question 9).

## SC8 · A session in puritty's loop

Today `Main.race` (app/src/Main.geng) races, every turn: the terminal's
`File.read`, `Window.events`, a timer, `File.writable` while the outbox has
bytes, and the settings watch. A `Read chunk` goes through the charset
filter into `Vt.feed`; keys and replies go out through `Outbox` and
`File.writeSome`; a resize is `Process.resize`; the end is the child's exit.

With a built-in session, the same shape, with the source changed:

| today (a pty) | a built-in session |
|---|---|
| `File.read fd` | `Net.read socket`, fed to `Ssh.step`, whose events are the channel's data, prompts, the host key, the end |
| `Outbox` written by `File.writeSome` | the session's encrypted output, written by `Net.writeSome`; keys and replies go to the session as channel data first |
| `Process.resize terminal` | `Ssh.resize`, a `window-change` |
| the charset filter, `Vt.feed` | unchanged, fed the channel's data |
| the child's exit status | `exit-status` or `exit-signal`; a lost connection keeps the screen (SC9) |
| `Process.kill` on close | `CLOSE` and `DISCONNECT` |
| the timer | also keepalive, the connect timeout, the rekey hour |
| — | an agent's pipe, raced while a request is out |

What stays: the window, the frame rules, the core, the outbox discipline
(V48), the settings watch, the charset (V49). The 128 KiB-per-turn budget
(`geng-plan.md` §3.1) becomes the channel's window: the session adjusts
the window only for data the core has taken, so a fast `cat` cannot fill
memory (`putty.md` §1.3).

`Main` should not hold two loops. Proposed: a `Backend` type, `Pty` or
`Ssh`, behind four functions (read, write, resize, end), as WezTerm and
PuTTY both found (`wezterm.md` §2, `putty.md` §1.3), so `race` names one
source. That change is made first, with only `Pty`, and the gates show
nothing moved.

**ProxyJump** composes: the outer session's `direct-tcpip` channel is the
inner session's transport. Both are values in one model, and still one
socket in the race.

**One process per window** (`geng-plan.md` §3.5) means a new window is a new
connection and a new authentication. `synthesis.md` §10.2's in-process
sharing applies to tabs in a window, when there are tabs. Sharing across
windows would need a cross-process multiplexer like OpenSSH's
`ControlMaster`, and is not v1 (question 10).

## SC9 · Security UX

`synthesis.md` §10.2 and `putty.md` §4, §5.5 set the rules; what is new is
how puritty's window can carry them.

**Who is speaking.** Before the session has a channel, the window shows
puritty's own screen: a `Vt.Term` written by puritty, as the settings window
is (ST7), so the font, the IME and Hangul input work in a password field
for nothing. Server bytes never reach that `Term`. But a user cannot see
which `Term` is shown, so the screen also needs a marker the server cannot
draw: **a strip outside the cell grid**, drawn only while puritty's screen
is up, with the host's name and puritty's icon. PuTTY's sigil does the same
in reserved columns (`putty.md` §8.8); a strip outside the grid needs no
per-line trust bit. Each hop is announced in it ("bastion, then
build-box") before any prompt (`putty.md` §5.5).

**First contact.** puritty's screen: the host, the key type, its SHA-256
fingerprint, the other key types the server has; Accept (store in
`known_hosts`), Connect once, Cancel.

**A changed key.** The one modal dialog (`synthesis.md` §10.2): on Windows,
a native dialog, so it cannot be mistaken for anything a server prints;
Cancel the default and the only choice called safe. A key pinned in the
host's entry fails with no prompt. A rekey with a different key ends the
connection.

**Server text.** The banner and keyboard-interactive prompts are shown in
puritty's screen, framed as from the server, with control characters
stripped and a length cap (`putty.md` §5.5).

**After authentication.** Refuse a server that lets the user in with no
credential, when the host asks for it (`SshNoTrivialAuth`, `putty.md`
§5.5). From then on the window is the session.

**Weak choices.** A negotiation that lands below a "warn" line, or is open
to Terrapin, says so in the strip once, with what would avoid it
(`putty.md` §3.2, §3.4).

**Disconnect.** The screen and scrollback stay; the strip says why and
offers Reconnect, which starts a new session under the same screen
(`synthesis.md` §10.2).

## SC10 · Testing

- **Primitives:** known answers from the RFCs (8439, 7748, 8032), NIST's
  vectors for AES-GCM and SHA-2, and Wycheproof's for the signature and
  AEAD edge cases (general knowledge), on Linux and on Windows.
- **A real server on nene.** OpenSSH's `sshd` runs unprivileged on a high
  port with its own host keys, `authorized_keys` and an `-o` per case
  (`Ciphers`, `KexAlgorithms`, `AuthenticationMethods`), all on localhost:
  each algorithm, each auth method, a changed host key, `MaxAuthTries`, a
  rekey forced by `RekeyLimit`, `window-change` seen by the remote `stty
  size`, and **EUC-KR bytes printed by the remote end arriving in `Vt.feed`
  unchanged**.
- **Replay.** With its random bytes from a seeded generator, the client is
  deterministic, so a conversation recorded against that sshd replays
  offline, byte for byte, in the corpus. A recording breaks only when the
  client's own output changes, which is then a change to explain.
- **A scripted server**, a few hundred lines of Geng on the same `ssh`
  package (the server side of transport only), for what a real server will
  not do: a bad MAC, a short packet, a packet during strict KEX, a channel
  window of zero, a banner full of escapes (`putty.md` §2.5's Uppity is the
  model).
- **Fuzzing** the packet parser and the session with random server bytes:
  no crash, no hang, memory bounded.
- **`~/.ssh/config`:** SC7's oracle table.
- **The app:** the hosts gate (`harness/hosts.py`) gains cases that start
  the built-in client against the local sshd and hold the window's title,
  background and screen.
- **Windows:** the same gates run there over ssh, as the pixel and replay
  gates do (WS22), against an sshd on nene or beelink1's own.

## SC11 · The steps, in order

Each ends with its gate passing, and the gates before it still passing.

1. **`Backend` in `Main`**, with only the pty behind it. *Gate:* every
   existing gate, unchanged.
2. **`Os.Net` and secure random bytes** in geng-lang (Linux and Windows).
   *Gate:* corpus cases against a local listener: connect, refused, timeout,
   a name that does not resolve, a read that loses a race keeping its bytes,
   a large write; run on beelink1 too.
3. **`ssh-crypto`.** *Gate:* the known-answer and Wycheproof tests, on both
   platforms; ChaCha20-Poly1305 and AES-GCM throughput measured beside SC4's.
4. **Transport**: version, packets, curve25519-sha256, Ed25519/RSA/ECDSA
   host-key verification, strict KEX, ext-info, rekey. *Gate:* the local
   sshd for each algorithm; the first replays; the scripted server's bad
   packets; the parser fuzzed for a set time.
5. **known_hosts and `~/.ssh/config`.** *Gate:* the `ssh -G` table; known_hosts
   cases (hashed, `[host]:port`, revoked, changed).
6. **User authentication**: key files (OpenSSH format, `bcrypt_pbkdf` on a
   thread), the agent (Linux's socket for the gate, then Windows' pipe and
   Pageant), password, keyboard-interactive. *Gate:* sshd with each method
   and with `MaxAuthTries 2`; a wrong passphrase.
7. **Connection**: session channel, `pty-req` with modes and `IUTF8`, `env`
   and `SetEnv`, shell or command, `window-change`, exit status,
   keepalives. *Gate:* the EUC-KR case; a resize seen by `stty size`; `exit
   3` ending puritty with 3; `tmux -CC` attaching.
8. **The window**: puritty's screen, the strip, the host-key screens, the
   mismatch dialog, disconnect and reconnect. *Gate:* the hosts gate's new
   cases; the settings gate's way of holding a screen (ST7) for each prompt.
9. **On Windows**: hosts start the built-in client (question 6), the
   credential store, Gilbert's own hosts. *Gate:* the Windows runs of all
   the above; Gilbert's session to an EUC-KR host.
10. **Later:** ProxyJump (needed early by Gilbert's hosts? question 8),
    agent forwarding, the FIPS set, ML-KEM, certificates, UpdateHostKeys,
    port forwarding, SFTP.

## SC12 · Questions for Gilbert, with leanings

1. **Who speaks SSH** (SC5): the protocol in Geng over C primitives (A),
   everything in Geng (B), libssh or libssh2 (C), OpenSSH over pipes (D),
   or PuTTY's client whole (E). *Leaning: A.* The hostile input is parsed in
   Geng; C does only the primitives, at C's speed and with C's care for
   timing.
2. **Which primitives** (SC5.1): PuTTY's `crypto/` subset, OpenSSL's
   libcrypto, or Monocypher with BearSSL. *Leaning: PuTTY's,* since it is
   exactly SSH's set, MIT, already vendored, and careful about timing;
   OpenSSL if the most examined code is worth its size and Windows build.
3. **Where the primitives live** (SC6): a puritty package, or C rows for
   geng-lang's `crypto`. *Leaning: puritty's `packages/ssh-crypto` now,*
   with pure functions shaped for packets; `crypto` keeps WebCrypto's shape,
   and geng-lang can take the package later if its standard library wants
   one.
4. **`Os.Net` in geng-lang's `os`** (SC3, SC6), as a Dnene decision built
   before puritty's step 2, or a puritty package of its own. *Leaning: in
   `os`,* since sockets are platform and every Geng program will want them.
5. **On Linux too?** *Leaning: built and gated on Linux; offered on
   Windows only, until Gilbert wants it on Linux* (where OpenSSH on a pty
   already passes EUC-KR).
6. **Which client a host uses on Windows.** *Leaning: the built-in one by
   default once step 9 passes, with a per-host `client = "openssh"`* for
   what it lacks (GSSAPI, FIDO keys, certificates at first).
7. **Secrets in Geng's heap** (SC3, SC6). *Leaning: private keys and saved
   passwords as C handles that are cleared; session keys as Geng `Bytes`,
   accepted.*
8. **ProxyJump in v1.** Do the hosts Gilbert and his colleagues use need a
   jump host from the start? *Leaning: right after step 7,* since `jump`
   is already a host field (ST10).
9. **A host entry over `~/.ssh/config`** (SC7): applied as a `Host` block
   before the file's, so the entry wins and the file fills in the rest.
   *Leaning: yes,* which is what `ssh -p … -l …` does today (ST23).
10. **Sharing a connection between windows** (SC8). *Leaning: not v1;*
    within a window when tabs come.
11. **The RHEL8 hosts** (SC2.1): are they in FIPS mode? If so the FIPS set
    (ECDH P-256, AES-GCM or CTR with `hmac-sha2-256-etm`, RSA and ECDSA host
    keys) moves into v1. *Leaning: ask the colleagues before step 4.*
12. **Post-quantum kex** (`mlkem768x25519-sha256`): v1 or later. *Leaning:
    after v1 and before release,* since OpenSSH warns without it and PuTTY's
    subset already has ML-KEM.
13. **The mismatch dialog** (SC9): a native Windows dialog, or puritty's
    own screen like every other prompt. *Leaning: native,* the one modal
    dialog, as `synthesis.md` §10.2 says.

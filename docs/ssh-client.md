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

**Decided (2026-11-10):** v1 must support at least `curve25519-sha256` kex;
`ssh-ed25519` and `ecdsa-sha2-nistp256` host keys, both verified from the
start; `chacha20-poly1305@openssh.com` and `aes256-gcm@openssh.com`; and
public-key and password login. The FIPS set (`ecdh-sha2-nistp256` or
`diffie-hellman-group14-sha256`, AES-CTR with `hmac-sha2-256-etm`) is not
in v1.

One case wants more later, and SC12 asks about it:

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
   existing gate, unchanged. **Done 2026-11-10:** `app/src/Backend.geng`
   holds what the loop asks of the remote end (read, write some, wait to
   write, resize, kill, wait for its exit), and `Backend.pty` makes one of
   a program on its pseudo terminal; `Main` knows nothing else. Every
   gate passed unchanged, on Linux and on beelink1.
2. **`Os.Net` and secure random bytes** in geng-lang (Linux and Windows).
   *Gate:* corpus cases against a local listener: connect, refused, timeout,
   a name that does not resolve, a read that loses a race keeping its bytes,
   a large write; run on beelink1 too.
   **Done 2026-11-10** (geng-lang Dnene41, `m4-puritty.md` §VA66):
   `Os.Net.connect` with Happy Eyeballs, `listen` and `accept`,
   `Os.Random.bytes`, and four connection kinds of `Os.Error`;
   `accept/os-net` passes on Linux, Wine and beelink1. Timeout is a race
   against `Process.sleep`, not a parameter; an unreachable address and a
   name that does not resolve have no case (the harness has no network).
3. **`ssh-crypto`.** *Gate:* the known-answer and Wycheproof tests, on both
   platforms; ChaCha20-Poly1305 and AES-GCM throughput measured beside SC4's.
   **Done 2026-11-10:** SC13.
4. **Transport**: version, packets, curve25519-sha256, Ed25519/RSA/ECDSA
   host-key verification, strict KEX, ext-info, rekey. *Gate:* the local
   sshd for each algorithm; the first replays; the scripted server's bad
   packets; the parser fuzzed for a set time.
   **Done 2026-11-10:** SC14.
5. **known_hosts and `~/.ssh/config`.** *Gate:* the `ssh -G` table; known_hosts
   cases (hashed, `[host]:port`, revoked, changed).
   **Done 2026-11-10:** SC15.
6. **User authentication**: key files (OpenSSH format, `bcrypt_pbkdf` on a
   thread), the agent (Linux's socket for the gate, then Windows' pipe and
   Pageant), password, keyboard-interactive. *Gate:* sshd with each method
   and with `MaxAuthTries 2`; a wrong passphrase.
   **Done 2026-11-10:** SC16, Linux's agent with it (geng-lang Dnene42).
   Windows' agent pipe and Pageant move to step 9: beelink1's OpenSSH
   agent service is disabled and Pageant is not running, and turning either
   on is a change to Gilbert's machine.
7. **Connection**: session channel, `pty-req` with modes and `IUTF8`, `env`
   and `SetEnv`, shell or command, `window-change`, exit status,
   keepalives. *Gate:* the EUC-KR case; a resize seen by `stty size`; `exit
   3` ending puritty with 3; `tmux -CC` attaching.
   **Done 2026-11-10:** SC17. `exit 3` ending puritty with 3 is the
   window's, step 8; `tmux -CC` waits for it too.
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

**Decided 2026-11-10: every leaning below is taken.** Question 11 was
answered on its own (SC2.1). The work follows SC11 in order.

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
8. **ProxyJump in v1.** Do the hosts Gilbert uses need a jump host from
   the start? *Leaning: right after step 7,* since `jump`
   is already a host field (ST10).
9. **A host entry over `~/.ssh/config`** (SC7): applied as a `Host` block
   before the file's, so the entry wins and the file fills in the rest.
   *Leaning: yes,* which is what `ssh -p … -l …` does today (ST23).
10. **Sharing a connection between windows** (SC8). *Leaning: not v1;*
    within a window when tabs come.
11. **The FIPS set** (SC2.1). **Decided 2026-11-10:** not in v1; v1
    must support the set SC2.1 names, ECDSA P-256 host keys included.
12. **Post-quantum kex** (`mlkem768x25519-sha256`): v1 or later. *Leaning:
    after v1 and before release,* since OpenSSH warns without it and PuTTY's
    subset already has ML-KEM.
13. **The mismatch dialog** (SC9): a native Windows dialog, or puritty's
    own screen like every other prompt. *Leaning: native,* the one modal
    dialog, as `synthesis.md` §10.2 says.

## SC13 · ssh-crypto as built (2026-11-10)

`packages/ssh-crypto` is SC11's step 3, as SC6 and questions 2 and 3 said:
PuTTY's primitives in C, under one Geng module, `SshCrypto`, of pure
functions over `Bytes`.

**What it carries of PuTTY.** `vendor.sh` copies 48 of PuTTY's C files
(the crypto subset SC4 compiled, SHA-3 and MD5 which `ecc-ssh.c` and
`rsa.c` name, eleven of `utils/` and three of `stubs/`) and the headers
they include, unchanged, from `vendor/putty` at the commit in
`src/Ext/putty/COMMIT` (`7507c54b`). A package compiles only
`src/Ext/*.c`, so each PuTTY file is compiled through a one-line file of
its own there (`pc_*.c`). Two files are ssh-crypto's own: `putty/putty.h`,
in place of PuTTY's, which the `*-select.c` files include and which would
bring PuTTY's whole program; and `ssh_crypto_config.h`, what PuTTY's CMake
would find. The AES-NI, SHA-NI and CLMUL files are compiled with those
instructions enabled for their functions alone (`#pragma clang attribute`),
and PuTTY picks them at run time when the CPU has them, as it does in
PuTTY. Compiled with `-Wall`, none warns.

**The functions.** Hashes (SHA-1, -256, -384, -512); HMAC (SHA-1, -256,
-512); a constant-time `equal`; X25519's public value and shared `K` (as
the SSH `mpint` the exchange hash takes); `verify` for `ssh-ed25519`,
`ecdsa-sha2-nistp256`, `rsa-sha2-256` and `rsa-sha2-512`, over SSH's
blobs; `seal`, `openLength` and `open` for whole packets under
`chacha20-poly1305@openssh.com` and `aes128`/`aes256-gcm@openssh.com`;
AES-CTR and `bcrypt_pbkdf` for OpenSSH key files. Nothing draws random
bytes: PuTTY's `random_read` answers only what a row supplies (the X25519
private value) and is a crash otherwise. Nothing keeps state: a packet
cipher is keyed again per packet from the sequence number and the count of
packets under those keys, AES-GCM's nonce counter set to the starting IV's
plus the count, as that many of PuTTY's `next_message` would leave it.
Signing (step 6) is not here yet.

**Two places PuTTY accepts what the standards refuse**, found by
Wycheproof: an RSA signature not below the modulus (RFC 8017 §5.2.2), and
an Ed25519 point encoding `x = 0` with the sign bit set (RFC 8032 §5.1.3).
`ssh_crypto.c` refuses both before PuTTY sees them;
`docs/upstream/putty-verify-accepts-malleable-signatures.md` has the
report, not filed.

**The gate.** `packages/ssh-crypto/tests/make-vectors.py` writes
`vectors.txt`, 2,421 vectors, none from PuTTY: FIPS 180's and RFC 4231's
and 2202's examples and random inputs against Python's `hashlib` and
`hmac`; RFC 7748's X25519 parties and Wycheproof's `x25519` (266);
Wycheproof's `ed25519`, `ecdsa_secp256r1_sha256` and the six
`rsa_signature_{2048,3072,4096}_sha{256,512}` files, as SSH blobs (2,000
with OpenSSH's own); `ssh-keygen -Y sign`'s signatures with each key type;
36 packets sealed by `cryptography`'s ChaCha20, Poly1305 and AES-GCM to
OpenSSH's two specifications, with counters that wrap; SP 800-38A's
AES-CTR; and three `ssh-keygen` key files with a passphrase, which must
decrypt to equal check words and the public key, and must not under the
wrong passphrase. A packet is also opened with each of seven bytes
changed and under the next nonce, and refused. Left out, and counted in
the file's head: Wycheproof's "acceptable" cases (x25519 254, ed25519 29,
rsa 6), which a verifier may take either way, and 221 ECDSA signatures
whose DER does not parse and so have no SSH form. `tests/build.sh` builds
the runner (`--windows` for the `.exe`); `ssh-crypto-tests` reads
`vectors.txt` and ends with status 1 on any failure.

| | nene (Ryzen 9 9950X), Linux | beelink1 (Ryzen 7 5700U), Windows 11 |
|---|---|---|
| vectors | 2,421 pass | 2,421 pass |
| chacha20-poly1305, MB/s | 486, 489, 493 | 188, 189, 191 |
| aes128-gcm, MB/s | 1,560 (three runs) | 860, 871, 871 |
| aes256-gcm, MB/s | 1,560 (three runs) | 945, 958, 972 |

Measured by `ssh-crypto-tests --bench`: 2,048 packets of 32,756 bytes
sealed with each, from Geng, each call keying again. On Windows the
clock's 15.6 ms steps make a run of about 70 ms good to some 20%, which is
why AES-128 reads slower than AES-256 there. Against SC4's: PuTTY's
ChaCha20-Poly1305 seals at about half of SC4's scalar C ChaCha20 alone on
nene and 1.8 times the Geng probe's 270 MB/s; AES-GCM with AES-NI and
CLMUL at three times that. Either is far above what a connection carries.
On nene, decrypting ChaCha20-Poly1305 would add about a fifth to the CPU
the core spends parsing a `cat` of a large file (108 to 124 MB/s,
`geng-plan.md` §1.3); AES-GCM about a fourteenth.

## SC14 · The transport as built (2026-11-10)

`packages/ssh` is SC11's step 4: `Ssh.Transport`, the client's side of
RFC 4253, in Geng with no I/O and no clock, over `Ssh.Wire` (SSH's data
types, every length checked before anything is taken) and `Ssh.Random`
(HMAC_DRBG with SHA-256, NIST SP 800-90A §10.1.2, seeded once with 32
bytes of `Os.Random`).

**Its shape.** `start`, `receive`, `send`, `rekey` and `disconnect` each
answer a step: the transport after, the bytes to write, and events
(`Banner`, `ServerVersion`, `HostKey`, `KeysChanged`, `ExtInfo`,
`Received`, `Closed`, `Failed`). Everything random comes from the seeded
generator, so a seed and the server's bytes decide every byte written:
`ssh-tests --record` writes a session and `replay` runs it again with no
server. The host key is reported with its signature checked; whether it is
the host's (`known_hosts`) is step 5's, and the layers above must not send
a secret before it is settled.

**What it does.** The version line (up to 1,024 lines before it, as RFC
4253 §4.2 allows, each shown); packets to OpenSSH's 256 KiB; KEXINIT with
`ext-info-c` and `kex-strict-c-v00@openssh.com` on the first exchange;
curve25519-sha256 and its libssh name; the exchange hash and keys of RFC
4253 §7.2; the host key's signature by `SshCrypto.verify`; NEWKEYS each
way; strict KEX, its first-packet rule, nothing but the exchange's messages
until it is done, and the sequence numbers reset at every NEWKEYS, as
draft-miller-sshm-strict-kex says ("for each subsequent KEX"); a server's
wrong `first_kex_packet_follows` guess dropped; a new exchange either side
begins, the layers' packets held until it is done; a host key that
changes between exchanges refused; a new exchange each GiB, or at 2^30
packets under one key; `EXT_INFO` reported; DISCONNECT both ways.

**Measured against OpenSSH 9.6p1** (`tests/sshd.py`, an sshd of the test's
own on 127.0.0.1 with host keys of each type): each of the three ciphers
with each of the four host key algorithms, twelve exchanges, each followed
by `ssh-userauth` accepted and a `none` authentication refused, which
needs both directions' keys; the defaults; refusals that name what the
server offers when no cipher, host key or kex is shared. **OpenSSH does not
take a client's new exchange before authentication**: it answers the
KEXINIT with UNIMPLEMENTED (`dispatch_protocol_error: type 20`). The
transport turns that into a failure instead of waiting forever; a
client-begun exchange against sshd waits for step 6. Against **Windows 11's
own sshd** (OpenSSH_for_Windows 9.5p2, LibreSSL, beelink1), the Windows
build made all twelve exchanges.

**The scripted server** (`tests/scripted.py`, Python's `cryptography`)
does what sshd does not, one thing a case: banner lines; an SSH-1 version;
no line in 8 KiB; a length of 2^31; padding of 3; a KEXINIT cut short; an
IGNORE before the KEXINIT with strict KEX (refused) and without it (taken);
a wrong guess; a signature over the wrong hash; an all-zero X25519 value;
NEWKEYS early; two KEXINITs; a MAC that does not hold; a new exchange it
begins (taken), and one that changes its host key (refused); DISCONNECT. 18
cases. The first version of that server reset sequence numbers only at the
first NEWKEYS, and the client's failure there led to the draft's text.

**Replays and fuzzing.** Three recorded sessions, one a cipher, replay to
the same bytes on Linux and Windows. `ssh-tests fuzz` replays them with the
server's bytes changed (bytes replaced, a run cut out, reads split
elsewhere), 5,000 runs each in the gate: about a third end as recorded,
two thirds with a failure the transport names, a few wait for bytes that
never come, and none crashes or speaks after failing. Its first run found
a crash in PuTTY: an `ssh-ed25519` key shorter than 32 bytes fails an
assertion in `eddsa_decode`. `ssh-crypto-tests --fuzz`, written then, found
a second, an even RSA modulus in `mp_modpow`. `ssh_crypto.c` now checks
every key and signature blob's shape before PuTTY sees it (`well_formed`),
and 200,000 rounds of that fuzzer since crash nothing and verify no random
signature or packet. Both are reproduced against PuTTY's code alone, and
`docs/upstream/putty-asserts-on-malformed-host-keys.md` keeps the report,
not filed.

**The gate:** `packages/ssh/tests/gate.sh`, 79 s on nene: ssh-crypto's
2,421 vectors and 20,000 fuzz rounds, `sshd.py`'s 21 cases (three of them
replays), `scripted.py`'s 18, and 15,000 fuzzed replays.

**Not yet:** keepalives (`keepalive@openssh.com`, step 7's); a time limit
on an exchange or on the version line (the caller's clock); and a
client-begun exchange against a real server after authentication (step 6).

## SC15 · known_hosts and ssh_config as built (2026-11-10)

SC11's step 5, in `packages/ssh`, both pure: the caller reads the files.

**`Ssh.KnownHosts`** parses a `known_hosts` file (each line that is not
an entry is reported with why), finds the lines for a host (by its name on
port 22, `[name]:port` otherwise; patterns with `*`, `?` and `!`, without
regard to case; hashed `|1|salt|hash` names by HMAC-SHA1), judges a key
(`Known`; `Unknown` with the types the host is known by; `Changed` with the
lines; `KeyRevoked` for a key on a `@revoked` line, whatever its names),
writes the line for a new key, plain or hashed, and orders the host key
algorithms so that those whose type the host is known by come first, as
OpenSSH's `order_hostkeyalgs` does. That last is what SC2.1's RHEL8 finding
needs: a host known by its ECDSA key is asked for ECDSA first.
`@cert-authority` lines are left out until certificates are taken.
`tests/make-known-hosts.py` makes a file of every kind of line with keys
from `ssh-keygen` and hashed lines from `ssh-keygen -H`, and holds the lines
found for 16 names to what `ssh-keygen -F` finds: 34 cases with the
verdicts and orders, all passing. One expectation of mine was wrong, not
the code: a host known by an Ed25519 key through `*.example.com` shows a
*changed* key when another Ed25519 key comes, not an unknown one.

**`Ssh.Config`** parses `ssh_config` lines (any case, `=` or space, double
quotes, a `#` after a space ending the line) and resolves a host as `ssh
-G` does, for the keywords SC7 lists. `ssh -G` is the oracle
(`tests/make-config.py`, 30 cases, all passing), and it corrected five
things I had from the documentation and SC7:

- **`Host` patterns are case-sensitive and comma is not a separator**:
  `Host build` does not take a host typed `BUILD`, and `Host alpha,beta`
  is one pattern that takes neither. `Match host` and `Match originalhost`
  are the other way: lists split at commas, case not regarded.
- **`SetEnv`'s first line wins whole**; it does not add up as `SendEnv`
  and `IdentityFile` do.
- **`RemoteCommand`'s tokens are expanded** (`echo %h` printed as the host
  name), as `UserKnownHostsFile`'s are; `IdentityFile`'s are printed as
  written.
- **`IdentityAgent none` is printed**.

Measured as SC7 said: `Match host` sees a `HostName` set by an earlier
line; a later `User` is not seen by an earlier `Match user`; `Match final`
blocks apply on a second pass, adding only what the first left unset; an
`Include` inside a `Host` block that does not match is not read, and what
an included file's own `Host` lines do ends with the file. A relative
`Include` is under `~/.ssh`, which no case tests, so as not to write there.
`Match exec` and `Match localnetwork` are not judged: the block is left out
and a problem says so.

**Not yet:** the `config.toml` host entry applied as a `Host` block before
the file's (question 9) and the system file after it, which come with the
window (steps 8 and 9); `CanonicalizeHostname`; the algorithm lists'
`+`, `-` and `^`; recording the cases on beelink1 with Windows' OpenSSH,
whose paths differ.

## SC16 · User authentication as built (2026-11-10)

SC11's step 6, without the agent.

**Keys stay in C** (SC12 question 7). `SshCrypto.keyFileInfo` reads an
OpenSSH key file's public half without its passphrase; `loadKey` reads the
file in C, runs `bcrypt_pbkdf` and AES-256-CTR on a thread of its own,
checks the two check words, and has PuTTY make its key of the private part
(`ssh_key_new_priv_openssh`), clearing every copy of the decrypted bytes
and of the passphrase it was handed; Geng holds a handle. `sign` signs on
a thread, as the server's algorithm asks (`rsa-sha2-512` or `-256` for an
RSA key); `forget` frees the key and PuTTY clears its numbers, after any
signature in flight. A cancelled signature still hands its work back, so
the key is freed and cleared on the program's thread. Ed25519, ECDSA
P-256, P-384 and P-521 and RSA; FIDO keys and PEM files not yet.
`ssh-crypto-tests`' 14 `keyload` vectors (`ssh-keygen` files of each type,
with a passphrase and without) hold the public key to the `.pub` file,
sign and verify, refuse a wrong passphrase and a forgotten key: on Linux and
Windows 11.

**`Ssh.Auth`** is RFC 4252 and 4256's client, as pure as the transport:
the `ssh-userauth` service, `none`, then the methods the server allows in
the client's order. It asks the caller for a signature, a password or
answers to prompts, and the caller may refuse each. A key is offered first
without a signature, and signed only after the server's PK_OK, so a key
with a passphrase is unlocked only when it would be taken; an RSA key signs
with `rsa-sha2-512` unless `server-sig-algs` offers only `-256`. It reports
the banner, each refusal with the methods left, partial success, a
password-change request (which it does not answer: the method is given
up), success, and running out.

**Against OpenSSH 9.6** (`tests/sshd.py`, `ssh-tests login`), OpenSSH
checked the client's Ed25519, ECDSA P-521 (behind a passphrase), RSA
`rsa-sha2-512` and, with `PubkeyAcceptedAlgorithms rsa-sha2-256`,
`rsa-sha2-256` signatures; an unknown key before a known one; a wrong
passphrase (the key is given up, and nothing is left); `MaxAuthTries 2`
(the server closes with "Too many authentication failures"); no key; and
a new exchange begun by the client **after** authentication, which
OpenSSH takes (SC14: before, it does not). Against **Windows 11's sshd**
from nene, the test client logged in with an Ed25519 key and made a new
exchange. **The scripted server** plays what a server without root cannot
check: a password, a wrong one twice, a banner, two prompts, two rounds
of keyboard-interactive, partial success, and a password-change request.
Gate: 9 login cases in `sshd.py`, 7 in `scripted.py`.

**The agent.** `Ssh.Agent` writes and reads the agent protocol's messages
(draft-ietf-sshm-ssh-agent): the keys it holds, and a signature by one,
with the RSA flags; the agent's private keys never leave it. On Linux the
connection is geng-lang's `Os.Net.connectLocal` (Dnene42) to
`SSH_AUTH_SOCK`. `ssh-tests login --agent` offers the agent's keys after
the key files', and asks the agent to sign. Against an `ssh-agent` of the
case's own and OpenSSH 9.6: an Ed25519 key, an RSA key (`rsa-sha2-512`),
an unknown key before a known one, and a key added with `ssh-add -c`, which
with no way to confirm the agent refuses to sign, so the login runs out of
keys. 4 cases in `sshd.py`.

**Not yet:** Windows' agent pipe and Pageant (step 9); `publickey-hostbound-v00@openssh.com`;
which keys to offer from `~/.ssh/config` (`IdentityFile`, `IdentitiesOnly`),
which is the window's (step 8).

## SC17 · The session as built (2026-11-10)

SC11's step 7: `Ssh.Connection`, RFC 4254's client for one session
channel, pure as the layers under it.

**What it does.** It opens a `session` channel with a 2 MiB window and
32 KiB packets, as OpenSSH's; asks for the terminal (`pty-req`, its type
and size, and its modes: `IUTF8` set for a UTF-8 terminal and cleared for
any other, as V49 does for a local pty), each variable (`env`, no reply
asked, since OpenSSH says nothing to one its `AcceptEnv` does not take),
then the shell or the command; and matches the replies to the requests
that asked, in order, so a refused terminal or command ends the session
with why. It sends the program's input in the server's window and
largest packet, keeping the rest until a `WINDOW_ADJUST`, then the EOF
after it; gives its own window back once half is used; sends
`window-change`; reports output and error output as bytes in no character
set, `exit-status`, `exit-signal`, and the channel's close, closing its
side. A server's global request or channel request that wants an answer
and is not one of these is refused (OpenSSH's `hostkeys-00@openssh.com`
asks none). A keepalive is `keepalive@openssh.com`, a global request the
server must answer, and those unanswered are counted for the caller's
`ServerAliveCountMax`. A window or packet size of 2^31 or more is read as
2^31 - 1 (`Wire.uint32Clamped`), since some servers send 2^32 - 1.

**Against OpenSSH 9.6** (`sshd.py`'s 13 session cases, after an Ed25519
login): **EUC-KR bytes** (`printf` of 한글's `c7 d1 b1 db`) arrive as
they were sent; `exit 3` is exit status 3; `stty size` on a 100 by 30
terminal says `30 100`; a resize to 120 by 40 before a line is read says
`40 120`; `stty -a` shows `iutf8` for a UTF-8 terminal and `-iutf8` for
one that is not; `LANG=ko_KR.EUC-KR` reaches the command under `AcceptEnv
LANG` and is dropped without it; 5,000,000 bytes out and 3,000,000 bytes in
(`wc -c` after the EOF), so both windows turn over many times; error
output; `kill -TERM $$` as the TERM signal; a keepalive. **Against
Windows 11's sshd** from nene: output, exit status 3, and a terminal 100
columns wide, through ConPTY.

**Not yet:** `SetEnv` from `~/.ssh/config`, which the window passes as
`env` (step 8); a server's global requests before the channel opens go to
the layer that has the session, which the window's loop is (step 8);
`tmux -CC`; X11 and agent forwarding, port forwarding.

## SC18 · The window's session (step 8, begun 2026-11-10)

**`Ssh.Session`** is the client as one task, for puritty's window to run
beside its loop: it connects, makes the exchange, holds the host's key to
`known_hosts`, logs in with the key files and an agent, and runs the
session channel, telling the window what happens through a `Source` of
notices (`Status`, `Asking`, `Banner`, `Started`, `Output`, `Exited`,
`Failed`, `Ended`) and taking keys, sizes, answers and a hang-up through a
`Source` of inputs. Its loop races the socket's read, the inputs and the
keepalive's timer; a read and a `Source.next` that lose keep what they
took (D1045, D377).

What it decides, as OpenSSH does and SC9 asks:

- **Nothing goes to a server before its key is settled.** Authentication
  begins only when the keys are in use *and* the host's key is trusted.
- **A known key** goes on; **a revoked one** is refused; **a changed one**
  is refused with no question, the message saying which line of the known
  hosts holds the old key and what to do if the host was rebuilt; **an
  unknown one** is refused under `StrictHostKeyChecking yes`, written
  without a question under `accept-new` and `no`, and asked about under
  `ask` (the default): trust and remember, trust this once, or decline.
  The known key types order the host key algorithms (SC15).
- **A key file with a passphrase** is asked about only when the server
  would take its key (SC16), and asked again after a wrong passphrase,
  three tries in all; the key is loaded, signs, and is forgotten.
- **Keepalives**, when `ServerAliveInterval` is set, end the session after
  `ServerAliveCountMax` go unanswered.
- **The exit status** is the program's, 255 for a signal, as `ssh` gives.

`ssh-tests session` drives it as the window does, answering from its
options; `sshd.py`'s ten `driver-*` cases hold the decisions above
against OpenSSH 9.6, with the port, the file's path, the fingerprint and
the user masked in the pins.

**The window** (puritty `app/src/Main.geng`, `Backend.geng`). A host
whose `client` is `"built-in"` (`settings.md` ST28) starts `Backend.ssh`
instead of a program on a pty: its options are `Ssh.Session.optionsFor`'s,
`~/.ssh/config` and what it includes resolved by `Ssh.Config` with the host
entry's user, port and key first, as `ssh -l -p -i` put theirs (question
9), the home, the local user and `SSH_AUTH_SOCK` from the environment, and
the terminal's size and character set (`IUTF8` as V49 says). A small
supervisor runs the session, and runs it again on a reconnect, until the
window hangs up. `Backend.read` answers the terminal's bytes or a notice,
which a pty never sends.

**puritty's own screen** (SC9) is up before the session runs, while it
asks, and after it failed: a `Vt.Term` puritty writes, of the window's
size, drawn instead of the session's, its text from the server (a banner,
a prompt's words) with every control character shown as `?`; the window's
title is `puritty: ssh to NAME` while it is up, which no server can set,
since the session's own title is not shown until it runs. Keys go to it:
`A` trusts and remembers an unknown key, `O` trusts it once, `Esc`
declines; a password, a passphrase and a server's prompts are typed
there, shown as `*` unless the server asks for an echo, with what an IME
commits taken as typed; after a failure, `Enter` closes the window and `R`
connects again. A session that ends ends the window with its exit status
(`Exited`), which is puritty's exit status, 255 for a signal.

**The gate** (`harness/sshwindow.py`): `puritty --host test` on Xvfb
against the local sshd, keys pressed with xdotool. Eight cases hold the
title while puritty's screen is up, puritty's exit status (the command's,
7), whether `known_hosts` took the key, and the size `stty size` saw
there (24 80): trust and remember, trust once, a known host, a passphrase,
a wrong passphrase then the right one, a key declined (the failure screen,
then Enter: status 0), a changed key, and no key that logs in followed by
R and Enter.

**Not yet:** the strip outside the cell grid that SC9 asks for (the title
is the marker for now); the changed-key dialog (a changed key is refused
outright, which is stricter); a jump host (the built-in client does not
take `jump` yet; such a host stays OpenSSH's); the session's exit status
when it is killed by a signal, which is 255 as `ssh`'s.

## SC19 · The agents on Windows (2026-11-10)

SC11's step 9, its agent part. Gilbert allowed turning on beelink1's
OpenSSH agent service and running Pageant (2026-11-10).

**An agent is a socket or a pipe.** `Ssh.Session.AgentPath` is
`LocalSocket` (Linux's `SSH_AUTH_SOCK`, through `Os.Net.connectLocal`) or
`Pipe` (a Windows named pipe, opened with `Os.File.open` for reading and
writing, which Windows' `os` reads on a thread of its own and writes in
place). The options carry a list, tried in turn until one lists its keys;
`IdentityAgent none` empties it, `IdentityAgent SSH_AUTH_SOCK` keeps the
platform's, and a path names one. Each platform's list is `SshAgents`'s
(kept apart from `Platform` so the application's tests, on node, need no
native package): on Linux `SSH_AUTH_SOCK`; on Windows the one
`SSH_AUTH_SOCK` names if it is set, else **Windows' OpenSSH agent**,
`\\.\pipe\openssh-ssh-agent`, then **Pageant**.

**Pageant's pipe** is named as PuTTY names it (`agent_named_pipe_name`,
`capi_obfuscate_string`): `\\.\pipe\pageant.USER.HASH`, USER the
user principal's name before its `@` (else the logon name), HASH the
SHA-256 in hex of "Pageant", NUL-padded to `CryptProtectMemory`'s block
and protected by it with `CRYPTPROTECTMEMORY_CROSS_PROCESS`, as an SSH
`string`. The C (`Locale.pageantParts` in `packages/win32`, linking
`crypt32` and `secur32`) answers the name and the protected bytes;
`SshCrypto` hashes them.

**Measured on beelink1** (`harness/windows/agents/`), against the test
sshd on nene listening on the LAN, with keys of the test's own:

- **OpenSSH's agent**: the service started, a test key added with
  `ssh-add`, and `ssh-tests.exe session ... --agent-pipe
  \\.\pipe\openssh-ssh-agent` logged in with the agent's key alone and
  ran `exit 7`. Then `ssh-add -D` (Windows' agent keeps keys in the
  registry until then), the service stopped and set back to Disabled.
- **Pageant** (0.85's `pageant.exe` from PuTTY's site, its signature
  valid, Simon Tatham's), run with the test key as a PPK: `puritty.exe
  --host test` (client built-in, its `%APPDATA%` and `HOME` the test's
  own) found the pipe by the name above, `pageant.yosup.9cf31a…`, logged
  in with Pageant's key while OpenSSH's agent was stopped, and exited 7,
  the command's status.

Each run leaves beelink1 as it was: no process left, the files removed,
the service Disabled, no key in the agent's store.

**Not yet, of step 9:** the built-in client as Windows' default (SC12
question 6 makes it so once step 9 passes, and its gate includes
Gilbert's own session to an EUC-KR host, which only he can run);
passwords kept in Windows' Credential Manager; the jump host, the strip
and the changed-key dialog of SC18.

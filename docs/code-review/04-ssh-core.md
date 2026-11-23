# 04 · SSH protocol core and crypto glue

Slice: `packages/ssh/src/Ssh/{Transport,Auth,Connection,Wire,KnownHosts,Agent,Random,Base64,Reason,Config}.geng`,
`packages/ssh-crypto/src/SshCrypto.geng`, `packages/ssh-crypto/src/Ext/ssh_crypto.c`, `ssh_crypto_keys.c`
(and `ssh_crypto_lock.*`). `Ssh/Session.geng` is not in the slice; it was read only where it is the
caller that decides whether something in the slice is a problem, and findings that land there say so.

Nothing was built or run. "Confirmed" means read in the code and traced through its callers.
Geng's `Int` is 32 bits and wraps (`geng-lang/docs/user/refinements.md` line 38); two findings rest on that.

---

### SC1 · A side channel closed while it is still opening is not closed, and then runs
- Where: packages/ssh/src/Ssh/Connection.geng:1016-1027 (`closeOn`), 553-568 (`OPEN_CONFIRMATION`), 416-433 (`afterOpen`); callers app/src/Sending.geng:332, 441 and app/src/Main.geng:5211, 5337 through packages/ssh/src/Ssh/Session.geng:776
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `closeOn` does nothing for a channel in `Opening`: `if ch.phase == Closed || ch.phase == Closing || ch.phase == Opening then finish st`. The channel stays in `st.channels` as `Opening`, with whatever `writeSide` queued in `pending`. When the server's `OPEN_CONFIRMATION` comes, `afterOpen` sends the `exec` or `subsystem` request as if nothing had been asked, and on success `pump` sends the queued bytes.
- Scenario: the user cancels a transfer or closes the remote picker before the server has confirmed the channel (one round trip; easy on a slow link). The app sends `SideClose`, believes the channel gone, and the command (`ShellTransfer`'s exec, or `sftp`) then starts on the host and takes the bytes queued for it, so a cancelled upload can still write a partial file. Nothing closes the channel afterwards: it lives until the session ends, and `Session.sides`/`refs` keep the ref (no `Ended` came). `close` on the session's own channel has the same hole.
- Fix: remember the close on an opening channel (a `closeWanted` flag or a `Cancelled` phase): on `OPEN_CONFIRMATION` send `CHANNEL_CLOSE` at once instead of the requests, drop `pending`, and say `Ended`; on `OPEN_FAILURE` just say `Ended`.
- Fixed: 2026-11-22. A channel closed while opening takes the phase `Cancelled`, its queued bytes dropped and later writes refused; on `OPEN_CONFIRMATION` it is closed at once (`CHANNEL_CLOSE`, no request), on `OPEN_FAILURE` it ends with no refusal said. Test: `Connection`'s "a side channel closed while it opens is closed when confirmed": before, the confirmation was answered with the exec request.

### SC2 · The channel window is given back on receipt, so the server is never slowed and output queues without bound
- Where: packages/ssh/src/Ssh/Connection.geng:690-700 (`consume`), 628-642; packages/ssh/src/Ssh/Session.geng:289-303 (`tell` is `Source.emit`), 1300-1317; docs/ssh-client.md:553-557
- Kind: security
- Severity: medium
- Confidence: plausible
- What: `consume` sends `WINDOW_ADJUST` as soon as half the 2 MiB window has arrived, whatever has happened to the bytes. The session hands each `Output` to the window with `Source.emit`, which "does not wait for the reader" (core `Source.geng`), and reads the socket again. There is no path by which the terminal says how much it has taken. docs/ssh-client.md:555 says the opposite is the design: "the session adjusts the window only for data the core has taken, so a fast `cat` cannot fill memory". Neither the window (data past it is taken) nor our 32 KiB maximum packet is enforced on what comes in.
- Scenario: a host (hostile, or just `cat` of a huge file on a fast LAN) sends faster than the terminal parses and draws. Every packet is acknowledged at network speed, so the notices source grows by the difference for as long as the output lasts. Not confirmed end to end: I did not measure whether the app's loop drains the source as fast as the session fills it, or what the native ring buffer does when full.
- Fix: count bytes as consumed only when the window reports them taken (an `Input` such as `Taken n`, sent from where `Vt.feed` has run), and give the window back from that count; refuse or drop data past the window. The same for a hop's `toInner`.

### SC3 · No warning or fallback when the server has no strict KEX and ChaCha20-Poly1305 is chosen (Terrapin), though the design promises one
- Where: packages/ssh/src/Ssh/Transport.geng:64 (cipher order), 94-102 (`Event` has no strict flag), 776-793; docs/ssh-client.md:609-611
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: the client prefers `chacha20-poly1305@openssh.com`, and with a server that does not offer `kex-strict-s-v00@openssh.com` it goes on without strict KEX, which is the combination CVE-2023-48795 needs. docs/ssh-client.md:609 says "A negotiation that ... is open to Terrapin, says so in the strip once, with what would avoid it". `KeysChanged Algorithms` does not carry whether strict KEX is on, `Transport` exposes no accessor for it, and "Terrapin" appears nowhere in `packages/` or `app/`.
- Scenario: a man in the middle between puritty and an unpatched server (OpenSSH before 9.6, most appliances) injects an `IGNORE` before `NEWKEYS` (taken: `dispatch` line 582) and deletes the server's first encrypted packet, `EXT_INFO`. Here that loses only `server-sig-algs`, so the damage today is small, but the user is told nothing and the document says they are.
- Fix: put `strict : Bool` in `Algorithms` (or an event), and say it in the session's status. Better, when the server is not strict and also offers an AES-GCM cipher, choose GCM for that connection (its nonce does not come from the sequence number).

### SC4 · An unencrypted key file's text, the private key itself, is held in Geng memory for the whole session
- Where: packages/ssh/src/Ssh/Session.geng:204, 508-513 (`file = Just { path = path, text = text }`), 1150-1155; packages/ssh-crypto/src/SshCrypto.geng:276-279; packages/ssh-crypto/src/Ext/ssh_crypto_keys.c:1-10; docs/ssh-client.md:970-975
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: `identitiesOf` reads every `IdentityFile` into `Bytes` and keeps the whole text in `State.identities` until the session ends, to hand to `loadKey` later. For a key with no passphrase that text is the private key. `SshCrypto.Key`'s comment says the key is "held in C, never in Geng's memory", `signWith`'s says "the key is in memory only while it signs", and SC16 says "`loadKey` reads the file in C"; none is true: Geng reads it, and C is handed a copy.
- Scenario: any passphrase-less key in `~/.ssh` (all seven default names are read, used or not) sits in the collector's heap for hours, where SC12 question 7 decided private keys must not be ("may reach swap or a crash dump", docs/ssh-client.md:240). The passphrase a user types reaches `loadKey` as Geng `Bytes` too; C clears only its own copy.
- Fix: keep only the path and the public blob in `Identity`; have `ssh_crypto_loadKey` take the path and read the file in C into memory it clears (or re-read in Geng only at signing time, which at least bounds the lifetime). Correct the three comments either way.

### SC5 · A host looked up through `HostKeyAlias` on a port other than 22 is looked up as `[alias]:port`; OpenSSH uses the bare alias
- Where: packages/ssh/src/Ssh/KnownHosts.geng:139-145 (`lookupName`); packages/ssh/src/Ssh/Session.geng:432, 908
- Kind: inaccuracy
- Severity: medium
- Confidence: plausible
- What: both call sites pass `host = hostKeyAlias or host` and the port to `lookupName`, which brackets any name when the port is not 22. OpenSSH's `get_hostfile_hostname_ipaddr` (sshconnect.c) uses `options.host_key_alias` as it is, with no port, and only otherwise `put_host_port(hostname, port)`. From memory of the source; `ssh-keygen -F` on a file OpenSSH wrote would settle it.
- Scenario: `Host box` / `HostKeyAlias box` / `Port 2222`, key stored by OpenSSH as `box ...`. puritty looks for `[box]:2222`, finds nothing, and reports the key as unknown. If the host's key has in fact changed, the user gets the first-contact question instead of the changed-key dialog, and with `StrictHostKeyChecking accept-new` or `no` the new key is taken and written with no question at all.
- Fix: when the name comes from `HostKeyAlias`, look it up and write it unbracketed whatever the port. Add a case to `make-known-hosts.py`.

### SC6 · With `accept-new` or `no`, a key of a type the host is not known by is taken silently even when the host is known by another type
- Where: packages/ssh/src/Ssh/KnownHosts.geng:251-255 (`check`); packages/ssh/src/Ssh/Session.geng:947-957
- Kind: security
- Severity: medium
- Confidence: confirmed
- What: `check` answers `Unknown { otherTypes }` when the file has keys for the host but none of the offered key's type, and the session's `accept-new` and `no` branches call `remember` and trust it without looking at `otherTypes`. The client knows better at that point: `orderHostKeys` put the known type first in its KEXINIT, so an honest server that still has that key would have used it.
- Scenario: the host is known by its Ed25519 key. A man in the middle offers only `ecdsa-sha2-nistp256` in its KEXINIT and signs with its own ECDSA key. Under `accept-new` the key is written to `known_hosts` and authentication starts (a password goes to the attacker). OpenSSH has the same weakness, so this is a decision to make rather than a divergence: `accept-new` is meant to accept new hosts, not new keys for known hosts.
- Fix: in the `accept-new`/`no` branches, treat `Unknown` with a non-empty `otherTypes` as the `ask` case does (the question already shows `knownTypes`), or refuse outright under `accept-new`.
- Fixed: 2026-11-22, as Gilbert decided: `docs/ssh-client.md` SC30. Under `accept-new`, a key of a type the host is not known by, when it is known by another, gets `ask`'s question; under `no` it is taken as before. Test: `sshd.py`'s driver-accept-new-other-type and driver-no-other-type (the host known by ECDSA, the server offering only Ed25519): before, the key was written and the session logged in under accept-new.

### SC7 · `ssh_config` keywords the client does not act on are dropped without a word, including ones that restrict what it may do
- Where: packages/ssh/src/Ssh/Config.geng:399-420 (`apply`'s last branch), 316-317 (`Settings.problems`); packages/ssh/src/Ssh/Session.geng:1543-1571; docs/ssh-client.md:510-516
- Kind: inaccuracy
- Severity: medium
- Confidence: confirmed
- What: `apply` stores any keyword's value and `resolveOne` reads the dozen it knows. Nothing compares the rest against a list, so `problems` never names one. SC7 says "A keyword it does not act on is reported once, by name, not silently ignored." The system file is not read either (`Config.resolve ... (entry ++ parsed.directives) []`), nor `GlobalKnownHostsFile`.
- Scenario: a user's config has `ProxyCommand` (puritty connects straight to the name instead), `HostKeyAlgorithms`/`KexAlgorithms`/`Ciphers` (the restriction is ignored), `PasswordAuthentication no` or `PreferredAuthentications publickey` (a password prompt is still shown and its answer sent), `RevokedHostKeys` (a revoked key is accepted), `CertificateFile`, `BatchMode`. Each silently behaves differently from `ssh` for the same host.
- Fix: keep the set of keywords acted on in `Config`, and have `resolve` add one problem per other keyword that was active for the host. Consider refusing to connect, not just reporting, for the handful whose loss weakens security (`ProxyCommand`, `RevokedHostKeys`, the `*Authentication no` family).
- Fixed: 2026-11-22, as Gilbert decided: `docs/ssh-client.md` SC31. `Config.client` names each keyword the host's lines set that the client does not act on, once per connection; honours the authentication switches, `PreferredAuthentications` and the algorithm lists in OpenSSH's forms; refuses `ProxyCommand`, `RevokedHostKeys`, `CertificateFile` and a restriction that leaves nothing, naming `client = "openssh"`; and the system file is read. Test: `ssh-tests client-config client-config.txt`, 21 cases.

### SC8 · keyboard-interactive is tried once per connection, so one mistyped answer ends the login
- Where: packages/ssh/src/Ssh/Auth.geng:340-346, 302-303 (`keyboardTried`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `next` sets `keyboardTried = True` when it sends the request and never offers the method again; `password` has `passwordTries` (3) but keyboard-interactive has no count. A PAM server answers a wrong password inside keyboard-interactive with `USERAUTH_FAILURE`, and a client is expected to start the method again (OpenSSH does, `NumberOfPasswordPrompts` times).
- Scenario: a server with `KbdInteractiveAuthentication yes` and `PasswordAuthentication no` (common with PAM or a one-time code). The user mistypes once: `Refused`, then `Exhausted`, "permission denied: nothing left to try", and the connection is closed. The same flag also stops the method after partial success if it had failed earlier in the connection.
- Fix: count keyboard-interactive attempts against the same limit as passwords (a counter in place of the Bool), and reset neither on partial success.
- Fixed: 2026-11-22. `keyboardTries` counts keyboard-interactive's starts and holds them to `passwordTries`, where a flag stopped the method after one failure; partial success does not reset it. Test: `Connection`'s "keyboard-interactive is begun again after a failure": before, asked once and then exhausted.

### SC9 · The hourly rekey in the design is not built: `Transport.rekey` has no caller
- Where: packages/ssh/src/Ssh/Transport.geng:294-300, 1114-1120; packages/ssh/src/Ssh/Session.geng (no call; `keysAt` at 282 is the time of the last typed key, despite its name); docs/ssh-client.md:67, 550
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: SC2 says "Rekey: after 1 GB or an hour" and SC8's table gives the timer "the rekey hour". Only the byte and packet counts in `rekeyIfDue` begin an exchange; `Transport.rekey` is called from the tests alone. SC14's "Not yet" list names a time limit on an exchange, not this.
- Scenario: an idle or low-traffic session keeps one set of keys for days. Not a break for AEAD ciphers at these volumes, but the document says otherwise.
- Fix: have the session's timer call `Transport.rekey` an hour after `KeysChanged`, or strike the hour from SC2 and SC8. `Session.keysAt` wants another name (`typedAt`).

### SC10 · `WINDOW_ADJUST` can wrap the server's window negative, after which the channel never sends again
- Where: packages/ssh/src/Ssh/Connection.geng:620-623
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `remoteWindow = min 2147483647 (ch.remoteWindow + more.value)`. Both terms can be up to 2^31 - 1 (`uint32Clamped`), `Int` wraps, and `min` then keeps the negative sum. `flushUpTo` and `canSend` need `remoteWindow > 0`.
- Scenario: a server opens with a window of 2^31 or more (read as 2^31 - 1; the module's own comment says "some servers send 2^32 - 1") and later sends any adjustment larger than what the client has sent since, which RFC 4254 allows up to 2^32 - 1 in total. The window goes negative, typed keys queue in `pending` for ever, and nothing is reported. A hostile server can do it at will.
- Fix: saturate without overflowing: `if more.value > 2147483647 - ch.remoteWindow then 2147483647 else ch.remoteWindow + more.value`.

### SC11 · A server that names a tiny maximum packet makes the client cut a write into one packet a byte, recursively
- Where: packages/ssh/src/Ssh/Connection.geng:560 (`max 1 (min opened.most maxPacket)`), 783-801 (`flushUpTo`)
- Kind: security
- Severity: low
- Confidence: plausible
- What: the server's maximum packet is floored at 1. `flushUpTo` sends `min pending window maxPacket` bytes and calls itself for the rest, and the call is not a tail call (`{ rest | sent = rest.sent + n }` after it), so its depth is the number of packets. Each packet is then framed, padded and sealed with a freshly keyed cipher.
- Scenario: a hostile server confirms the session channel with maximum packet 1 and a large window; the user pastes 1 MB. That is a million nested calls (whether the native backend survives that depth I did not test) and a million sealed packets of about 36 bytes each in one update, with the window frozen meanwhile. With an honest server the depth is at most 2 MiB / 32 KiB = 64.
- Fix: refuse a channel whose maximum packet is below some floor (OpenSSH servers send 32768; a few hundred bytes is a safe floor), and make the loop accumulate instead of recursing after the call.

### SC12 · `Agent.unframe` cannot tell "not all here yet" from "will never be valid", and the reader has no size limit
- Where: packages/ssh/src/Ssh/Agent.geng:32-39; packages/ssh/src/Ssh/Session.geng:582-598 (`agentRead`)
- Kind: security
- Severity: low
- Confidence: confirmed
- What: `unframe` maps every `Err` of `Wire.string` to `Nothing`, which `agentRead` takes as "read more" and answers by `Bytes.flatten [ got, more ]`. A length of 2^31 or more (which `Wire.uint32` refuses) is therefore waited for until the agent closes, and any length below it is believed: up to 2 GiB is buffered, each read copying all that came before. OpenSSH refuses an agent reply over 256 KiB (`MAX_AGENT_REPLY_LEN`). There is also no time limit: `agentOf` runs before the transport starts, so an agent that accepts the connection and says nothing stops the session from ever connecting.
- Scenario: `IdentityAgent` or `SSH_AUTH_SOCK` points at something that is not a healthy agent (a forwarded socket whose far end is stuck, a wrong pipe). The session hangs at "reading keys" or grows without bound.
- Fix: `unframe : Bytes -> Result String (Maybe {...})`: `Err` for a length over 256 KiB, `Ok Nothing` for a short buffer. Keep the pieces in an array and flatten once. Race the call against a timer in the session.

### SC13 · The transport hands packets to the layers above before any keys exist when the server is not strict
- Where: packages/ssh/src/Ssh/Transport.geng:563-565, 597-598, 603-604
- Kind: security
- Severity: low
- Confidence: confirmed
- What: outside strict KEX, `dispatch` emits `Received payload` for any message outside 20..49 and `ExtInfo` for message 7, even while `st.ready` is `False`, that is, in the clear and before the host key's signature has been checked. OpenSSH's client has no handlers for such messages during the first exchange. The module's contract ("`Received`: a packet for the layers above") gives the caller no hint that it may be unauthenticated.
- Scenario: none today: `Session.onEvent` drops them because `auth` and `connection` are still `Nothing`. But the safety is in the caller's ordering, not the transport, and a caller that created `Auth` early (the test driver's shape) would take a forged `USERAUTH_SUCCESS` or `server-sig-algs` from anyone on the path.
- Fix: in `dispatch`, when `not st.ready`, fail on (or answer `UNIMPLEMENTED` to) anything that is not a transport or key exchange message, strict or not; take `EXT_INFO` only as the first packet after a `NEWKEYS` (RFC 8308 §2.4).

### SC14 · `server-sig-algs` is thrown away when it arrives before the host key question is answered
- Where: packages/ssh/src/Ssh/Session.geng:863-870, 1060-1076 (outside the slice; it is how `Auth.withServerSigAlgs` is fed)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `ExtInfo` is applied with `Maybe.map (Auth.withServerSigAlgs algorithms) st.auth`. `st.auth` is `Nothing` until `beginAuth`, which waits for the host key to be trusted; `beginAuth` then starts with `serverSigAlgs = []`. The server sends `EXT_INFO` once, right after `NEWKEYS`.
- Scenario: first contact with a host (the user is looking at the trust question when `EXT_INFO` arrives) that takes only `rsa-sha2-256` for an RSA key: `algorithmFor` defaults to `rsa-sha2-512`, the key is refused, and the same login works on the second connection, when the key is known.
- Fix: keep the list in `State` when it arrives and pass it in `Auth.begin`'s config.

### SC15 · `exit-status` of 2^31 or more is dropped, and a server's channel number of 2^31 or more ends the channel
- Where: packages/ssh/src/Ssh/Connection.geng:734 (`Wire.uint32 request.rest`), 546-550 (`theirs`), 511 and 637
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `Wire.uint32` is for lengths and refuses values with the top bit set. It is used for the exit status, for the server's own channel number in `OPEN_CONFIRMATION`, and for the extended data type. These are numbers, not lengths; `Wire.uint32Bits` exists for them.
- Scenario: Windows' sshd reports NTSTATUS exit codes such as 0xC000013A (ended by Ctrl-C) or 0xC0000005: no `Exited` is emitted and the session ends with no status. A server that numbers its channels from the top (legal) gets "a channel confirmation that does not read".
- Fix: `uint32Bits` for all three; decide what `Exited` shows for a negative `Int` (print it unsigned).

### SC16 · A channel the server opens is never answered
- Where: packages/ssh/src/Ssh/Connection.geng:508-534, 663-664
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: `CHANNEL_OPEN` (90) from the server falls into the per-channel path, where its first field, the length of the channel type's name, is read as a channel number (`"x11"` is 3, `"session"` 7, `"forwarded-tcpip"` 15). If that happens to be a live side channel's number, `onChannel` ignores it; otherwise it is "a channel that is not ours". Either way no `CHANNEL_OPEN_FAILURE` is sent, which RFC 4254 §5.1 requires. Likewise `Session.onEvent` (872-889) answers nothing to a message number it does not know, where RFC 4253 §11.4 requires `UNIMPLEMENTED`.
- Scenario: a server that opens `auth-agent@openssh.com` or `x11` unasked waits for ever on that channel; a server probing with an extension message gets silence. No harm to the client, but both are protocol errors a strict peer may disconnect on.
- Fix: handle 90 before the channel lookup: read the type and the sender's channel and answer `OPEN_FAILURE` (1, administratively prohibited). Have the session send `UNIMPLEMENTED` with the packet's sequence number, which means `Received` must carry it.

### SC17 · The keepalive count reported is one behind, so a dead server is noticed one interval late
- Where: packages/ssh/src/Ssh/Connection.geng:990-1000; packages/ssh/src/Ssh/Session.geng:669-675
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `keepalive` emits `KeepaliveUnanswered st.keepalives`, the count before the one it has just sent, and the session ends the connection when that number reaches `keepaliveCountMax` at the next tick. With a silent server and the default 3: ticks 1 to 4 report 0, 1, 2, 3 and the session ends on tick 5. OpenSSH ends on tick 4 (`++keep_alive_timeouts > ServerAliveCountMax`).
- Scenario: `ServerAliveInterval 15`: a dead link is declared after 75 s, not 60.
- Fix: emit the count including the one just sent only if it was already unanswered at this tick, i.e. compare `st.keepalives >= max` in `keepalive` itself, or have the session test `>` against the fresh count. Add the dead-server timing to `scripted.py`.

### SC18 · A `FAILURE` while a signature is being made offers the same key again, as often as the server likes
- Where: packages/ssh/src/Ssh/Auth.geng:264-308 (`failed`), 319-320 (`untriedKey`), 402-409
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `failed` marks a key as tried only in `Querying` and `SentSignature`. In `Signing` (after `PK_OK`, while the caller loads the key or asks for its passphrase) a `FAILURE` goes to `next`, which finds the same identity untried and queries it again; the next `PK_OK` asks for a signature again. The caller's first request is still outstanding, and its answer is then ignored or applied to the second round.
- Scenario: a hostile or broken server alternates `PK_OK` and `FAILURE`: the user gets passphrase question after passphrase question for the same key, with no end. More generally any unsolicited `FAILURE` advances the state machine (`AwaitingPassword` asks for the password again).
- Fix: in `failed`, treat `Signing s` as the key refused (add `s.identity.id` to `triedKeys`), and ignore a `FAILURE` in states where no request of ours is outstanding (`AwaitingService`, `AwaitingPassword`, `AwaitingResponses`).

### SC19 · `KnownHosts.replaced` numbers lines differently from `parse`, so it can take out the wrong line
- Where: packages/ssh/src/Ssh/KnownHosts.geng:59 (`String.lines`), 342-349 (`String.split "\n"`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `parse` numbers lines with `String.lines`, which breaks at `\r\n`, at `\n` and at a lone `\r` (core `String.geng`:446-451). `replaced` takes the stale entries' numbers from `parse` and removes them from `String.split "\n" text`, which does not break at a lone `\r`.
- Scenario: a `known_hosts` with one stray carriage return above the host's line (a file edited on an old Mac, or a pasted line). Accepting a changed key removes the line one above the stale one, another host's key, and leaves the stale key in place.
- Fix: one splitter for both: split on `\n` only in `parse` too (trim takes the `\r` off), or have `parse` carry each entry's byte range and cut by range.

### SC20 · A relative `Include` in the system's file is read from the user's `~/.ssh`
- Where: packages/ssh/src/Ssh/Config.geng:430-439 (`includePath`); packages/ssh/src/Ssh/Session.geng:1601-1608
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: `includePath` puts every relative path under `context.home ++ "/.ssh/"`, without looking at `d.file`. ssh_config(5): relative to `~/.ssh` in a user file, to `/etc/ssh` in the system file. `~user/` is not expanded either. Latent today since the system file is not read at all (finding above), and SC15 says no case tests relative includes.
- Scenario: once the system file is passed to `resolve`, `Include ssh_config.d/*.conf` in `/etc/ssh/ssh_config` reads `~/.ssh/ssh_config.d/`.
- Fix: carry the including file's directory (or a `system : Bool`) to `includePath`.

### SC21 · `HostName %%h` expands to the host; `%%` is replaced before `%h`
- Where: packages/ssh/src/Ssh/Config.geng:545-547 (`expandHost`)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `String.replace "%h" host (String.replace "%%" "%" value)`: the inner replace turns `%%h` into `%h`, which the outer one then expands. `tokensIn` (646-662) does it properly in one pass and is not used here.
- Scenario: `HostName a%%h` gives `a` followed by the host, not the literal `a%h`. Rare, but it is a second token expander that has already drifted from the first.
- Fix: call `tokensIn` with a table of `h` and `%`.

### SC22 · RSA certificates and other key types an agent holds are offered under a name the server cannot take
- Where: packages/ssh/src/Ssh/Auth.geng:363-373 (`algorithmFor`); packages/ssh/src/Ssh/Agent.geng:80-94 (`signRequest` flags); packages/ssh/src/Ssh/Session.geng:560
- Kind: bug
- Severity: low
- Confidence: plausible
- What: an agent's identities are taken with whatever type their blob names. `algorithmFor` maps only `ssh-rsa` to `rsa-sha2-*`; `ssh-rsa-cert-v01@openssh.com` is offered as it is (SHA-1, refused by OpenSSH since 8.8; the SHA-2 name is `rsa-sha2-512-cert-v01@openssh.com`), and the sign flags are 0 for it. `sk-` keys and `ssh-dss` are offered too.
- Scenario: an agent with a few certificates and a FIDO key: each is a wasted `publickey` query, and they count against the server's `MaxAuthTries` (6) before the key that works is reached: "Too many authentication failures".
- Fix: map RSA certificate types to their `rsa-sha2-*-cert` names and flags, and leave out of `identities` any type the client has no signature algorithm for.

### SC23 · A key handle that is dropped without `forget` leaks the private key uncleared
- Where: packages/ssh-crypto/src/Ext/ssh_crypto_keys.c:177-195, 276-285; packages/ssh/src/Ssh/Session.geng:1182-1188
- Kind: design
- Severity: low
- Confidence: plausible
- What: `key_handle` is a collected object holding a `malloc`ed `key_box`; nothing runs when the handle is collected. The only release is `ssh_crypto_forgetKey`. `signWith` forgets on success and on failure, but not if its task is cancelled between `loadKey` succeeding and `forget` (the window closing while an RSA signature is on its thread).
- Scenario: the box and PuTTY's key, private numbers and all, stay allocated and uncleared for the life of the process. A small window, and a leak rather than a crash, but it is exactly the memory SC12 question 7 wanted cleared.
- Fix: one extern that loads, signs and frees in C (the session never needs the handle between the two), or a finalizer on the handle if the runtime has one.

### SC24 · `aesCtr` and `bcryptPbkdf` are exported and used by nothing but the tests
- Where: packages/ssh-crypto/src/SshCrypto.geng:241-261; packages/ssh-crypto/src/Ext/ssh_crypto.c:411-430
- Kind: dead-code
- Severity: low
- Confidence: confirmed
- What: key files are decrypted in C by `load_now`, which calls `openssh_bcrypt` and the cipher itself. The two pure externs are the earlier route, decrypting a key file into Geng `Bytes`, which is what SC12 question 7 rules out. `bcryptPbkdf` as a pure extern also blocks the loop for `rounds` x 6 ms with no bound on `rounds`.
- Scenario: a later change reaches for them and puts a decrypted private key in the Geng heap, or freezes the window on a file that says 100,000 rounds.
- Fix: move them to the test package's own externs, or delete them and test `loadKey` only.

### SC25 · `Transport.start` takes a seed of any length, an empty one included
- Where: packages/ssh/src/Ssh/Transport.geng:232-263; packages/ssh/src/Ssh/Random.geng:22-26
- Kind: design
- Severity: low
- Confidence: confirmed
- What: "a seed of 32 or more bytes" is a comment. `Random.seeded Bytes.empty` works and gives the same X25519 private value on every connection. Today's only caller passes `Os.Random.bytes 32`, whose failure fails the task.
- Scenario: a caller, a test helper promoted to production, or a short read from a future `Os.Random` hands in fewer bytes: every session's key exchange secret is predictable, and nothing fails.
- Fix: a refinement on the argument (`Bytes.length seed >= 32`), or `start` answers a dead transport with `Failed` for a short seed.

### SC26 · `IdentitiesOnly true` is read as `no`, and a `known_hosts` that cannot be read is read as empty
- Where: packages/ssh/src/Ssh/Session.geng:1552, 493-495 (outside the slice; noted because they decide what `Auth` offers and what `KnownHosts.check` sees)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `identitiesOnly = String.toLower (one "identitiesonly" "no") == "yes"`; OpenSSH takes `true` as well (as `Config.toLines`' `yesNo` knows). `readKnownHosts` turns any read error into `[]`.
- Scenario: `IdentitiesOnly true`: every agent key is offered to the server. A `known_hosts` that exists but cannot be read (permissions, a transient error on a network home): every host is "unknown", `@revoked` lines are lost, and under `accept-new` keys are accepted and appended.
- Fix: one yes/no reader in `Config` used by both; tell a missing file from an unreadable one and refuse to connect, or at least say so, for the latter.

### SC27 · The glob matcher is written twice and backtracks exponentially
- Where: packages/ssh/src/Ssh/KnownHosts.geng:182-210; packages/ssh/src/Ssh/Config.geng:550-578
- Kind: design
- Severity: low
- Confidence: confirmed
- What: two identical `glob`/`globFrom` pairs. Each `*` tries both branches (`globFrom p.rest name || globFrom pattern n.rest`) with no memo, and `Array.popFirst` copies the rest each step.
- Scenario: a pattern such as `*a*a*a*a*a*a*b` against a long host name of `a`s takes time exponential in the number of stars; it runs once per `Host` line per connection. The input is the user's own files, so this is a cost and a drift risk, not an attack.
- Fix: one matcher in a shared module, walking two indexes with the usual single backtrack point for the last `*`.

---

## Looked at and found sound

- **Version exchange** (`Transport.consume`, `versionLine`, `takeLine`): 8 KiB bound on a line, 1,024 lines before the version, only `SSH-2.0-` and `SSH-1.99-` taken, CR stripped, the line as hashed is the line without CR LF.
- **Packet framing**: length checked (minimum, 256 KiB maximum, block multiple) before any wait for the body, in the clear and under each cipher; the ChaCha20 length is decrypted with the right sequence number and the tag is verified in C before anything is decrypted (`ssh_crypto_open` verifies, then decrypts); padding of less than 4 and an empty payload are refused; outgoing padding arithmetic is right for both the clear and AEAD cases.
- **Strict KEX**: offered only in the first KEXINIT; the server's flag read only from its first; the "first packet" rule uses the sequence number of the KEXINIT itself; non-exchange messages refused until the first `NEWKEYS`; both sequence numbers reset at every `NEWKEYS`, in the right order relative to switching keys; `ext-info-c` and the strict name can never be chosen as the key exchange (`firstShared` uses the list without them).
- **Exchange state machine**: a second KEXINIT, an `ECDH_REPLY` before the KEXINIT or twice, a `NEWKEYS` before the reply are each refused; upper-layer sends are queued from our KEXINIT to their `NEWKEYS` and flushed in order; a server-begun exchange is answered; an `UNIMPLEMENTED` naming our KEXINIT fails rather than hangs.
- **Exchange hash and keys**: V_C, V_S, I_C, I_S, K_S, Q_C, Q_S, K in order; K is PuTTY's mpint with its length (`ssh_ecdhkex_m_getkey`); session id is the first hash and is kept across exchanges; key derivation letters A/B/C/D and the extension rule match RFC 4253 §7.2; key and IV lengths match the three ciphers.
- **X25519**: PuTTY refuses the identity result (`ecc_montgomery_is_identity`), which covers the all-zero value; lengths checked on both sides of the FFI; the only random draw allowed is the caller's 32 bytes, any other is a crash by design.
- **Host key signature**: algorithm is the negotiated one; `well_formed` requires the key blob's type and the signature's type to match it exactly, with nothing trailing, which closes algorithm confusion (RSA: signature type must be the negotiated `rsa-sha2-*`, never `ssh-rsa`); RSA modulus 1,024 to 16,384 bits and odd; s < n; Ed25519 point decoding per the two upstream reports; the host key must be byte-identical in a later exchange.
- **AES-GCM nonce**: fixed part plus a 64-bit counter advanced by the packet count, count reset with the keys, rekey at 2^30 packets or 1 GiB.
- **Constant time**: `ssh_crypto_equal` is `smemeq` after a length check; used for hashed known-hosts names and key comparison.
- **`Ssh.Random`**: HMAC_DRBG's instantiate, generate and update as SP 800-90A §10.1.2 has them.
- **`Ssh.Wire`**: every read checks what remains first; a negative or oversized length is an error, not a wrap; `uint64` assembles correctly.
- **Auth**: the signed data is session id, request head, TRUE, algorithm, key, as RFC 4252 §7; RSA never signs with SHA-1; a key is queried before it is unlocked; password attempts are bounded; `PASSWD_CHANGEREQ` gives the method up; prompts are capped at 64; authentication does not begin until the host key is trusted and keys are in use (`Session.beginAuth`).
- **Connection**: messages for unknown or ended channels are ignored without touching others; side channel numbers are never reused; a refusal on a side channel does not end the session; global requests wanting a reply get `REQUEST_FAILURE`; unknown channel requests wanting a reply get `CHANNEL_FAILURE`; `CLOSE` is answered once; EOF goes after pending data.
- **known_hosts**: hashed names (salt and hash must be 20 bytes), `[host]:port`, negated patterns, `@revoked` checked against every line whatever its names, `@cert-authority` left out of every answer, a line whose stated type differs from its blob is refused, `Changed` only for another key of the same type.
- **ssh_config**: `Match exec` is never run; `Include` only when active and bounded at 16 deep; number parsing cannot overflow (`grown`, `added`).
- **`ssh_crypto_keys.c`**: armor and outer structure parsed with bounds; rounds capped; check words compared; plaintext, key/IV and passphrase copies cleared; the `busy`/`forgotten` scheme frees a key only on the program thread after the last signature; thread hand-off reads the post before sending; PuTTY's curve statics are behind one lock on every path that uses a signing curve; Ed25519 private keys are length-checked by PuTTY before `eddsa_decode`.
- **Base64**: padding only at the end, length a multiple of four, no character outside the alphabet.

## Not covered

- Vendored PuTTY (`Ext/putty/`) beyond the functions named above. In particular `ssh_key_new_priv_openssh` for RSA and ECDSA with a crafted (unencrypted) private key file was not traced for assertions (`rsa_verify`'s `mp_invert` with p = q, for instance); `well_formed` guards public blobs only.
- `Ssh/Session.geng` as a whole (read only around the calls into this slice), `Sftp`, `Transfer`, `ShellTransfer`.
- How banners, keyboard-interactive prompts and `DISCONNECT` descriptions are cleaned before display: that is in the app, not this slice. `Auth` and `Transport` pass them on raw and uncounted (no limit on the number of banners).
- The test programs under `packages/ssh/tests` and `packages/ssh-crypto/tests` were listed, not read; test-gap claims above are limited to what SC14 to SC17 say is covered.
- Windows-specific agent paths (Pageant, the named pipe) and `docs/saved-secrets.md`'s Credential Manager code.
- Thread safety of PuTTY's run-time CPU feature selection (`*-select.c`) when a pure extern on the program thread and a signing thread first use a hash at the same moment.

# 05 · SSH session layer and file transfer

Slice: `packages/ssh/src/Ssh/{Session,Sftp,Transfer,ShellTransfer}.geng`,
`app/src/{PickerSftp,Sending,Outbox,Drop,Hosts,SshConfig,Putty,Remembered}.geng`,
`app/{linux,windows}/src/{PuttyStore,SecretStore,SshAgents}.geng`; `Connection.geng`,
`Wire.geng`, `Backend.geng` and the parts of `Main.geng` that drive these were read
to trace the calls. Nothing was built or run; every finding is from reading.

Facts the findings lean on, read from the sources: a Geng `Int` is 32 bits signed
(`Wire.geng:32`); `Source.emit` never waits for its reader (core `Source.geng:137`);
`Os.File.metadata` follows links (`geng-lang/packages/os/src/Os/File.geng:211`);
`Os.File.read` and `Os.Net.read` give up to 65,536 bytes; `Os.Net.write` waits
until every byte is taken; native stack exhaustion is a signal, not a catchable
error (`geng-lang/docs/jvm.md:56`).

---

### ST1 · A batch whose SFTP stream breaks is reported as a success: `Finished` overwrites `Broken`
- Where: app/src/Sending.geng:412-425 and 429-442; packages/ssh/src/Ssh/Transfer.geng:327-329 (and 316-317 while draining)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `Transfer.onEvent` emits `Broken why` and then `Finished {..., failed = st.failed + remaining st}` in the same step. `Sending.event` handles them in order, and both call `finish`: the first sets `over = Just "The host's SFTP stopped making sense…"`, the second sets `over = Just (capitalized (summary s))`, replacing it (and pushes a second `SideClose`). `summary` is built from `s.done`, `s.skipped` and the `s.failed` array, which only `Failed` events fill; the count in `Finished` is ignored.
- Scenario: ten files dropped, the server's stream breaks (a length over 16 MiB, an answer that does not read) after two. The note bar says "Sent 2 items", `sendingShown` computes `failed = False` (no failures, `done > 0`), the folder is recorded as recently sent to, and eight files are silently missing. With nothing sent yet it says "Nothing sent" with no reason.
- Fix: make `finish` keep the first `over` (or have `event Finished` not override once `over` is set), and carry the unsent count into the summary: either `Transfer` emits a `Failed` per job not done, or `Sending` uses `Finished`'s counts.

### ST2 · The shell fallback's quoting is only right for POSIX-style login shells: fish misreads `\'`, csh/tcsh refuse the newline
- Where: packages/ssh/src/Ssh/ShellTransfer.geng:272-297 (`quoted`, `underSh`), 311-336 (`lookScript`); docs/sftp.md:1209-1211 ("so the login shell does not matter (zsh's ran them in the gate)")
- Kind: security
- Severity: medium
- Confidence: plausible (from fish's and csh's documented quoting; no such shell was run)
- What: every command is `sh -c '<script>'`, the script quoted a second time by `quoted` with `'` as `'\''`. That string is parsed by the account's login shell first (sshd runs `$SHELL -c <command>`). Inside the script each name is already `'…'` with `'\''` for a quote, so a name holding `'` puts `'\''` in the script, which the outer quoting turns into `'\''\'\'''\''`. A POSIX shell reads `\` inside single quotes as itself. fish does not: inside single quotes `\'` and `\\` are escapes, so in the middle of that sequence fish stays inside the quote where `sh` would leave it, and from there the quote state is inverted: the rest of the name and of the script is unquoted fish text. A name holding `\\`, or ending in `\`, goes wrong the same way (halved, or swallowing the closing quote).
- Scenario: host with SFTP off, `[files] upload_through_shell = true`, the account's login shell fish. Dropping a file named `it's.txt` fails with a fish syntax error at best; a crafted local name such as `a';touch ~/owned;'` (from an unpacked archive, say) has its middle run by fish as a command on the host. Separately, on csh/tcsh the look command always fails ("Unmatched '"): `lookScript` always holds newlines (`set -f\n`, one per upload), and csh does not allow an unescaped newline inside quotes, so the fallback never works there although the document says any login shell will do.
- Fix: do not hand the login shell anything it can read two ways. Either send a fixed, name-free command (`sh -c 'eval "$(…)"'` with the script encoded in characters every shell passes through unchanged, e.g. octal through `printf`, or hex), or refuse/encode names containing `'` or `\` and keep the script on one line; and correct FT18's sentence. Add fish and tcsh login shells to `shell-transfer.py`.

### ST3 · A remembered password is given without asking to a host whose key is not the known one
- Where: app/src/Main.geng:5829-5872 (`sshAsked`); packages/ssh/src/Ssh/Session.geng:1224-1231 (changed key trusted once), 953-957 (`accept-new`, `no`)
- Kind: security
- Severity: medium
- Confidence: confirmed (code path); not covered by docs/saved-secrets.md or SC28
- What: `sshAsked` answers a `Password`, or a one-prompt keyboard-interactive question that says "password", from Credential Manager whenever the store holds `puritty:ssh:user@host:port` and it has not been tried on this connection. Nothing in the path looks at how the host's key was accepted. `Session` goes on to authentication after `HostKeyChanged` is answered `Trust { remember = False }` ("trusted for this connection only"), and after an unknown key is taken silently under `StrictHostKeyChecking accept-new`/`no`.
- Scenario: the saved host's key changes (a rebuilt host, or someone in the middle). The user answers "trust once" to look around; the server asks for a password and puritty sends the saved one at once, with only a status line saying so. OpenSSH turns password and keyboard-interactive authentication off in exactly this state ("to avoid man-in-the-middle attacks"); here the secret leaves without a keystroke. With `StrictHostKeyChecking no` and a key of a type not yet known, there is no question at all before it is sent.
- Fix: have `Session` say in the `Ask` (or a notice) whether the host's key matched `known_hosts`, and have `sshAsked` not auto-answer from the store unless it did; in the other cases show the box (the remembered one may still be offered, but by the user's Enter).

### ST4 · A dropped folder is walked through its symlinks: a link to `/` or to a parent uploads far more than was dropped, or never finishes
- Where: app/src/Sending.geng:82-138 (`jobsOf`, `File.metadata` at 97, `Directory.list` at 109)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `jobsOf` asks `File.metadata` for every entry and recurses when `m.kind == File.Directory`. `metadata` follows links ("never `Link`"), and the `kind` that `Directory.list` gives (`Link` for a link) is not looked at. So a link to a folder is walked as that folder, with no record of folders already seen and no depth or count limit. The whole walk runs inside one task before `Sending.begin`, so there is no progress, no note and nothing to cancel.
- Scenario: a dropped folder holds `dosdevices/z: -> /` (any Wine prefix), a `node_modules/.bin`-style link to a parent, or `latest -> .`. A link to a parent is followed until the kernel's ELOOP at 40 links, multiplying the tree at every level (two such links: 2^40 paths); a link to `/` lists the whole file system including `/proc`. puritty sits building `jobs` (memory growing) with the window showing nothing, and if it ends, uploads all of it.
- Fix: use the entry's `kind` from `Directory.list`: skip links inside a dropped folder (or send a link to a file as the file and never descend through a link to a folder), and say how many were skipped in `refused`. Cap the number of jobs or show the count while walking.

### ST5 · A hostile SFTP server can crash the client with one `SSH_FXP_NAME`: `entries` and `skipExtended` recurse once per element, not in a loop
- Where: packages/ssh/src/Ssh/Sftp.geng:467-482 (`entries`), 543-549 (`skipExtended`); limit at 346
- Kind: security
- Severity: medium
- Confidence: plausible (depends on how the C backend compiles a call inside a `Result.andThen` lambda; it is not a tail call in the source)
- What: `entries n r acc` calls itself from inside three nested `Result.andThen` lambdas, and `skipExtended` from inside one; each element adds stack frames. The count is whatever the server wrote (below 2^31), bounded only by the packet, and a packet may be 16 MiB. An entry can be 12 bytes (two empty strings and zero flags), an extended pair 8 bytes.
- Scenario: the folder chooser (or an upload's `STAT`) talks to a hostile or broken server that answers with `SSH_FXP_NAME`, count 1,000,000, followed by 12 MB of zero bytes (or attributes with the EXTENDED bit and a count of 2,000,000). The parse recurses over a million levels deep; on the native target stack exhaustion is a signal, so the terminal and every tab in it die. `acc` is also built with `Array.pushLast` per entry.
- Fix: read entries in a loop that is a tail call in the source (an explicit `when … is Ok … -> entries (n-1) …; Err e -> Err e` with no closure around the recursive call), the same for `skipExtended`, and refuse a count larger than `remaining r // 12` before starting.

### ST6 · A key that is both a file and in the agent is used from the file, so the passphrase is asked although the agent holds the key
- Where: packages/ssh/src/Ssh/Session.geng:546-561 (`agentOf`), 470 (`identities = files ++ agent.identities`), 1149-1152
- Kind: bug
- Severity: medium
- Confidence: confirmed for the list built; plausible that `Auth` tries identities in that order
- What: with `IdentitiesOnly` off, the agent's keys are filtered with `not (Array.member k.publicKey fromFiles)`, so a key the agent holds is dropped when an identity file has the same public key; with it on, the agent's copy is kept but after the file's. Either way the file's identity is offered first, and when the server takes it `onRequest` finds `encrypted = True` and asks for the passphrase.
- Scenario: the commonest setup: `~/.ssh/id_ed25519` (a default `IdentityFile`) encrypted, and added to the agent with `ssh-add` so that nothing is asked. OpenSSH signs with the agent. puritty asks for the passphrase on every connection (and on Linux, where nothing is remembered, every time).
- Fix: when an identity file's public key is among the agent's keys, keep one identity that signs through the agent (`file = Nothing`), in the file's place in the order; fall back to the file only if the agent refuses to sign.

### ST7 · A new host key is appended to `known_hosts` without checking the file ends in a newline
- Where: packages/ssh/src/Ssh/Session.geng:989 (`remember`, `File.appendFile … (KnownHosts.line …)`)
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: `KnownHosts.line` ends in `\n` but does not start with one, and `remember` appends it as it is. OpenSSH checks the last byte of the file first and writes a newline when it is missing.
- Scenario: a `known_hosts` whose last line has no line end (hand-edited, or written by another tool). The new entry lands on that line: `hostA ssh-ed25519 AAAA…hostB ssh-ed25519 AAAA…`. hostA's key no longer reads (or reads as another key, so hostA is "unknown" or "changed" next time), and hostB is never found, so it is asked about on every connection and appended again each time.
- Fix: read the file's last byte (or its size and the last byte) before appending and write `\n` first when it is not a line end; `replaceKey`'s rewritten text needs the same check before `remember` runs after it.

### ST8 · A side channel closed while it is still opening is never closed: quick Esc in the folder chooser leaks a server session each time
- Where: packages/ssh/src/Ssh/Connection.geng:1016-1024 (`closeOn` does nothing in `Opening`); app/src/Main.geng:5333-5342 (`chooserClosed`), 5205-5216 (`chooserIo`, `opened` set as soon as the open is sent); packages/ssh/src/Ssh/Session.geng:775-776
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `closeOn` returns the state unchanged when `ch.phase == Opening`, and nothing remembers that a close was asked. The window forgets the channel at once (`choosing = Nothing`). When the server's confirmation comes the channel goes on to `Requesting`, the subsystem starts, its queued `INIT` is pumped, and the channel stays open until the session ends; `Session.sides`/`refs` keep its entry. `ShellTransfer` works around this itself (`closing` until `Started`, ShellTransfer.geng:470-471, 574-583); the chooser does not.
- Scenario: on a slow link, drop files, the chooser opens, Esc before the server has confirmed the channel (one round trip). An `sftp-server` is left running on the host. sshd's default `MaxSessions` is 10: after a few of these, further drops and picture pastes fail with "the server would not open another session", which `Sending` reports as "SFTP is turned off on this host".
- Fix: in `Connection`, record a close asked for while opening (a flag on the channel) and send `CHANNEL_CLOSE` as soon as the confirmation arrives (emit `Ended` on an open failure as now), so every caller gets `closeSide` right without its own state.

### ST9 · `Sending.owns` claims every later side channel while a shell transfer runs
- Where: app/src/Sending.geng:187-189; app/src/Main.geng:4775-4782 (a block of 100000 refs kept), 5050-5051 (chooser's ref), 4464-4510 (picture paste's ref), 5241-5249
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `owns ref s = ref == s.ref || (s.shellRefs && ref > s.ref)` has no upper bound, though the caller reserves `ref+1 … ref+100000` for the shell's channels and gives later channels (the chooser, a pasted picture's upload) refs above that. `sideEvent` gives an owned event to `Sending.side`, and `ShellTransfer.told` drops one that is not its running command's.
- Scenario: a shell-fallback upload is running; the user drops more files on a pane with no known folder (the chooser opens) or pastes a picture. Every event of the new channel, including its `Refused` and `Ended`, goes to the transfer and is dropped: the chooser sits waiting for a listing with no message, and the picture's upload state never ends, until the session does.
- Fix: bound it: `ref > s.ref && ref <= s.ref + 100000` (one named constant shared with `startPending`), or have `ShellTransfer` say which refs it has opened.

### ST10 · `ConnectTimeout` is read and ignored, and nothing is read from the window while connecting
- Where: packages/ssh/src/Ssh/Session.geng:317-328 (`through`), 400-423 (`connectTo`), 1547-1575 (options built with no timeout); docs/ssh-client.md:510-516 lists `ConnectTimeout` among "keywords the client acts on in v1"
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: `Net.connect` is awaited alone, with the system's own wait (minutes for a host that drops SYNs); the `inputs` source is first read in `loop`, after the connection and the reading of keys and agent. `Config` knows `connecttimeout` (Config.geng:733) but `resolveOne` never takes it. There is also no limit on the wait for the server's banner or key exchange, though there the user's `Hangup` is read.
- Scenario: `ConnectTimeout 5` in `~/.ssh/config` and an unreachable host: puritty says "connecting to …" for the system's two minutes; closing the tab meanwhile queues a `Hangup` that is not seen until the connect fails. With a jump host each hop repeats it.
- Fix: race `Net.connect` against `Process.sleep` (the option's seconds, a default when unset) and against `Source.next inputs` so a hang-up ends it; either act on the keyword or take it out of the document's list and report it as not acted on.

### ST11 · Nothing holds the server back when the window reads slower than the network: output queues without bound
- Where: packages/ssh/src/Ssh/Session.geng:1312-1316 (`tell (Output bytes)`), 289-303; packages/ssh/src/Ssh/Connection.geng:690-700 (`consume` gives the window back on receipt); app/src/Backend.geng:109-123
- Kind: security
- Severity: low
- Confidence: plausible (needs the session to out-run the terminal; not measured)
- What: channel data is emitted to the `notices` source, which does not wait for its reader, and the channel's window is given back as soon as half of it has arrived, not when the window has drawn it. docs/sftp.md has back-pressure for side channels' writes (FT17) but nothing for the session's output. The same holds for a jump host's `toInner` source (Session.geng:1298-1299).
- Scenario: `cat` of a multi-gigabyte file, `yes`, or a hostile server, on a LAN where decrypting is faster than the terminal parses and draws. The queue of `Output` notices grows by the difference for as long as it lasts; Ctrl-C is answered only after the backlog is drawn.
- Fix: count bytes emitted and not yet taken by the window (the window acknowledging through an input, or a bounded source) and stop reading the link, or hold back `WINDOW_ADJUST`, past a few megabytes.

### ST12 · The link is not closed when the loop ends by an error, and an agent's socket is never closed
- Where: packages/ssh/src/Ssh/Session.geng:308-328 (`run`, `through`: `st.link.close` only on the success path), 532-579 (`agentOf`, `linkTo`), 380-385
- Kind: bug
- Severity: low
- Confidence: plausible (a leak unless `Os.Net`'s sockets are closed by a finalizer, which was not checked)
- What: a failed `link.read` or `link.write` (ECONNRESET, EPIPE, ETIMEDOUT) fails the task; `run`'s `onError` tells `Failed` and `Ended`, and nothing calls `link.close`. The agent's `AgentLink` has only `call`: the socket or pipe opened by `linkTo` is kept in `st.agent` and never closed at the end of a session, nor when `agentOf` moves on to the next candidate after a bad answer. `carry` also swallows a hop's error (`Task.onError (\_ -> Task.succeed st)`), so the inner session only says "the server closed the connection".
- Scenario: a laptop that sleeps and reconnects many tabs over a day: each reset session leaves a TCP socket and each session an agent connection open in a process meant to run for weeks.
- Fix: close the link in a `Task` finalizer around `session … |> loop` (success or failure), give `AgentLink` a `close` and call it when authentication is over and at the end, and keep a hop's failure to tell as `Failed` with its label.

### ST13 · The keepalive timer starts again on every turn of the loop, so a dead link is not noticed while anything else happens
- Where: packages/ssh/src/Ssh/Session.geng:617-646 (`timer` rebuilt in each `loop`), 669-675
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `Process.sleep (keepaliveSeconds * 1000)` is a new task in each race, so any turn (a key, a resize, a `SideWrite`, a pump) restarts the interval. OpenSSH resets its timer on data from the server only.
- Scenario: `ServerAliveInterval 60`, the NAT entry is gone. The user types (no echo comes), waits, types again: each key within a minute of the last puts the keepalive off, so the "server stopped answering" end comes `60 × (CountMax + 1)` seconds after the last key, not after the link died. (`keepaliveSeconds * 1000` also wraps for an interval over 2,147,483 s, an `Int` being 32 bits.)
- Fix: keep the monotonic time the server was last heard from in `State` and sleep only for what is left of the interval; reset it in `FromServer` alone.

### ST14 · A second `SSH_FXP_VERSION` restarts the transfer's checks in the middle of a batch
- Where: packages/ssh/src/Ssh/Sftp.geng:378-391 (type 2 accepted at any time); packages/ssh/src/Ssh/Transfer.geng:324-325 (`Sftp.Ready _ -> check st`)
- Kind: bug
- Severity: low
- Confidence: confirmed (hostile or broken server only)
- What: `onPacket` treats a type 2 packet as the version whenever it comes, and `Transfer.onEvent` answers every `Ready` with `check`: phase back to `Checking`, every target stat'ed again, and when those answer `checked` calls `startNext` (or asks `Conflicts` again) while a file may be moving. The moving run is replaced; its handle is never closed, its job gets no `Done` or `Failed`, and `Finished`'s counts no longer add up to the jobs. An `answer` given meanwhile is dropped because the phase is not `Asking`.
- Fix: in `Sftp.onPacket`, a version after `ready` is `Broken`; in `Transfer`, `check` only from `Starting`.

### ST15 · `Sftp.received` copies the whole unfinished packet for every piece that arrives
- Where: packages/ssh/src/Ssh/Sftp.geng:325-331 (`Bytes.flatten [ c.buffer, bytes ]`), 340-350
- Kind: efficiency
- Severity: low
- Confidence: confirmed
- What: each call joins the kept bytes and the new ones into a new `Bytes` before looking at the length. For answers that fit a channel packet this is one copy a piece; for a packet announced as up to 16 MiB it is a copy of everything so far for each piece.
- Scenario: a server that sends a 16 MiB packet in 1 KiB channel packets makes the client copy about 128 GB in the window's own loop (the transfer and picker run in `Main`'s update), a stall of many seconds for 16 MiB of traffic. Honest servers stay under 256 KiB a packet, where it costs little.
- Fix: keep the pieces in an array with their total length and join only once the announced length is there (the length itself needs at most the first 4 bytes); a much lower cap than 16 MiB would also do, since this client never asks for more than 32 KiB.

### ST16 · A shell-fallback job that succeeded is reported failed when the host's startup files print anything
- Where: packages/ssh/src/Ssh/ShellTransfer.geng:646-657
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: after status 0 the whole of standard output, trimmed, must be an integer (`String.trim |> String.toInt`), the number of the name written. The command runs under the login shell, and bash started by sshd sources `.bashrc` even for a command, zsh `.zshenv`. docs/sftp.md:226 itself notes that an `echo` in `.bashrc` is common.
- Scenario: a host without SFTP whose `.bashrc` prints a line. Every upload is written, checked and renamed on the host, and then told "the command did not say which name it wrote: Welcome…" and counted failed; a retry meets its own file as a conflict.
- Fix: read the last non-empty line of the output (as `lastLine` already does for errors), or print the number behind a marker the engine looks for.

### ST17 · `ShellTransfer.unsent` never sees the running command, so a failed upload leaves the total below what was moved
- Where: packages/ssh/src/Ssh/ShellTransfer.geng:608-612 (`ended` clears `run` first), 715-749
- Kind: dead-code
- Severity: low
- Confidence: confirmed
- What: `failJob` and `skipJob` are reached only from `ended` (after `st = { st0 | run = Nothing }`) and from `startNext`/`upload` (no command running), so `unsent`'s `Just run -> if run.job == job then u.size - run.offset` branch is never taken and the whole size is always subtracted from `total`, while `moved` keeps the bytes already written.
- Scenario: a 100 MB upload fails at 60 MB (the disk is full): `total` drops by 100 MB, `moved` keeps 60 MB, and the next `Progress` shows more bytes than the total and a negative time left.
- Fix: pass the ended `Run` to `failJob` (or subtract `u.size - run.offset` in `ended` before clearing `run`).

### ST18 · `Transfer`'s broken-stream path miscounts, and leaves the part
- Where: packages/ssh/src/Ssh/Transfer.geng:327-329, 377-380 (`remaining`: "those from `next` on, and the one moving")
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `remaining st = Array.length st.jobs - st.next` does not include the file moving (`next` was advanced when it began), though its comment says it does; `cancel` adds `stopped` by hand for the same reason, the `Broken` branch does not. So after `Broken`, done + skipped + failed is one short of the jobs. The branch also sets `run = Nothing` without `dropRun`, so a download's local `.part` file is left (the channel is going, so the host's part cannot be removed, but the local one can).
- Fix: count the moving job in `remaining` (and drop `stopped`), and queue the `RemoveFile` for a download's part on `Broken`.

### ST19 · Every refusal of the SFTP channel is taken as "SFTP is turned off", and with the setting on it switches to shell commands
- Where: app/src/Sending.geng:205-213; packages/ssh/src/Ssh/Session.geng:791-794; packages/ssh/src/Ssh/Connection.geng:573-618, 711-712
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: `Connection.Refused` is told for a channel open failure (`MaxSessions`, "short of resources"), for a session not yet connected, and for the `subsystem` request refused. `Sending.side` treats all three alike. docs/sftp.md FT18 says "A host that has SFTP is never sent through the shell".
- Scenario: files dropped while the tab is still at its password question: "SFTP is turned off on this host (the session is not connected), and nothing was sent; [files] upload_through_shell = true sends through its shell instead". Or the host is at `MaxSessions`: the same words, and with the setting on the engine starts opening `exec` channels on a host that does have SFTP.
- Fix: give `Refused` a reason type (open failed / request refused / not connected), fall back to the shell only on the subsystem request's refusal, and word the others as they are.

### ST20 · An upload opens, seeks and closes the local file for every 32 KiB, and reads 64 KiB to use 32
- Where: app/src/Main.geng:4857-4897 (`sendingOut`'s `Read`, `readUpTo`); pieces asked by packages/ssh/src/Ssh/Transfer.geng:1090-1091 and ShellTransfer.geng:513-514
- Kind: speed
- Severity: low
- Confidence: confirmed
- What: each `ReadPiece` is `File.withHandle … seek … readUpTo 32768`. `File.read` answers up to 65,536 bytes, so `readUpTo` gets 64 KiB, slices off the first 32 KiB and drops the rest, which the next piece reads again after a new open and seek. Every byte of the file is read twice and there are four system calls a piece. This is the per-chunk path of every upload; on Windows each open also passes the virus scanner's filter.
- Scenario: a 4 GiB upload: 131,072 opens and 8 GiB read. FT17 measured 320 MB/s on Linux to a local sshd, so it is not the limit there; on Windows it may be.
- Fix: keep one handle per file being sent (opened at the first piece, closed on `Done`/`Failed`/cancel), and ask for pieces of the size `File.read` gives, or carry the unused half to the next piece.

### ST21 · A batch that has shown no progress cannot be cancelled, and nothing times it out
- Where: app/src/Sending.geng:500-546 (`progressText` is `Nothing` until a `Progress`); app/src/Main.geng:4902-4937, 6979-6984, 8392-8398; packages/ssh/src/Ssh/Transfer.geng:177-183 (`Starting`)
- Kind: bug
- Severity: low
- Confidence: plausible (the click needs the note bar to be up; a note from something else would also do)
- What: the only cancel outside the conflict question is a click on the note bar, and the bar shows the batch only once the engine has emitted `Progress` (the first file opened) and a second has passed. `Transfer` waits in `Starting` for the server's version and in `Checking` for every `STAT` with no limit.
- Scenario: the `sftp` subsystem starts but says nothing (a wrapper that hangs, a forced command waiting on input). `m.sending` stays set with nothing on screen; every later drop answers "Files are still being sent; drop these again when they are done" until the tab's session ends.
- Fix: show the batch in the note bar from `begin` ("starting…", click to cancel), and give up `Starting` after some seconds.

### ST22 · Options from `~/.ssh/config`: `SetEnv` with `=` in the value is dropped, `IdentitiesOnly true` is not yes, a bare IPv6 jump or quick-connect host is cut at its last colon
- Where: packages/ssh/src/Ssh/Session.geng:1560-1569, 1552, 1431-1436; app/src/Hosts.geng:63-74
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: (1) `String.split "=" pair` must give exactly two parts, so `SetEnv OPTS=a=b` (or a base64 value ending `=`) sends nothing, silently. (2) `identitiesOnly = String.toLower (one "identitiesonly" "no") == "yes"`: OpenSSH also takes `true`, which `strict` just above does handle. (3) `jumpSpecs` and `Hosts.quick` split host from port at the last `:` unless the text starts with `[`, so `ProxyJump fe80::1` or quick connect `::1` becomes host `fe80:`/`:` port 1 and fails as a name not found.
- Fix: split `SetEnv` at the first `=`; one boolean reader for yes/true/no/false; treat text with two or more colons and no brackets as an address with no port.

### ST23 · `ssh` is run with the host's name as a bare argument: a name starting with `-` is read as an option
- Where: app/src/Hosts.geng:114-131 (`sshCommand`), 18-22 (`named`), 29-90 (`quick`)
- Kind: security
- Severity: low
- Confidence: confirmed (every source of the name today is the user's own: settings, quick connect, `--host`, PuTTY's sessions)
- What: the command is `ssh <options> [-t] <h.host> [command]` with no `--` and no check on `h.host`. `Hosts.quick "-oProxyCommand=… x"` gives `ssh -t -oProxyCommand=… x`, which runs the command on this computer.
- Scenario: harmless while only the user writes host names; it becomes the classic `ssh://-oProxyCommand` hole the day a name comes from a link, a file someone else wrote, or an imported session list.
- Fix: refuse a host (and a user) that starts with `-` in `quick`/`named`, and put `--` before the host in `sshCommand`.

### ST24 · After the picker's SFTP stream breaks, later requests wait for ever; and a listing cannot be abandoned
- Where: app/src/PickerSftp.geng:221-223, 117-132, 398-436
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: on `Sftp.Broken` the requests waiting are failed, but the source is not marked broken: a later `ask` still builds SFTP requests, whose answers never come (`Sftp.received` returns nothing once broken), so the picker shows a folder loading with no end. `fail` also sends a `Close` on the broken stream. Separately `Picker.Ask` has no cancel: a listing started is read to its end (`READDIR` after `READDIR`, two requests per link) after the user has moved on, each part still told to the picker.
- Fix: keep `broken : Maybe String` in `Source` and answer every `ask` with `Failed` at once; let the picker drop a reading by id (close its handle, stop asking).

### ST25 · A changed key's rewrite of `known_hosts` goes through lossy UTF-8 and a new file
- Where: packages/ssh/src/Ssh/Session.geng:1010-1044 (`replaceKey`)
- Kind: bug
- Severity: low
- Confidence: confirmed (the mode change plausible: depends on `File.writeFile`'s default mode)
- What: the file is read with `Bytes.toStringLossy`, changed, and written whole to `known_hosts.puritty-new`, then moved over the old one. Any byte that is not UTF-8 (a comment in EUC-KR, which this project's users have) becomes U+FFFD in every line, not only the removed one; and the new file has the default mode and the writer's ownership, not the old file's (a `known_hosts` kept 0600 becomes 0644).
- Fix: work on bytes (split at `\n`, drop the lines by number, join) and copy the old file's mode to the new one before the move.

### ST26 · An unreadable folder inside a drop is made on the host empty, with nothing said
- Where: app/src/Sending.geng:109-111
- Kind: design
- Severity: low
- Confidence: confirmed
- What: `Directory.list … |> Task.onError (\_ -> Task.succeed [])` turns a folder that cannot be listed into one with no entries; the `MakeDir` job is still made and the summary says "sent N items" with no failure. A file that cannot be stat'ed, three lines on, is put in `refused` with its reason.
- Fix: put the folder in `refused` with the system's words, as the file case does.

### ST27 · No test drives `Sending`, and the shell fallback's quoting is tested under one login shell
- Where: app/src/Sending.geng (no reference in `app/tests` or `harness/`); packages/ssh/tests/shell-transfer.py (zsh only, docs/sftp.md:1210); packages/ssh/tests/src/Main.geng:576-592 (malformed SFTP: three cases)
- Kind: test-gap
- Severity: low
- Confidence: confirmed (by grep)
- What: the engines are tested against a real sshd, but the module that joins them to the window is not: the `Broken`-then-`Finished` order, `owns`, the switch to the shell on `Refused`, the summary's words. The SFTP parser's hostile cases stop at an answer before the version, version 4 and one oversized length: no huge `NAME` count, no second version, no packet trickled in. The shell fallback's "any login shell" claim rests on zsh.
- Fix: unit cases for `Sending` with scripted engine events; parser cases for the findings above; `shell-transfer.py` with fish and tcsh as the account's shell, including names with `'`, `\` and a newline.

## Looked at and found sound

- **ShellTransfer's scripts under a POSIX login shell**: names go in as their own bytes inside single quotes with `'` as `'\''`, twice (script, then `sh -c`); `$`, backticks, `*`, newlines and a leading `-` cannot escape (`--` on `ls`, `rm`, `mkdir`, `mv`; targets are `dir/name` paths; `set -f` before the unquoted `$(ls …)`). The part is made under `set -C` after `rm -f`, its size checked with `wc -c` before the rename, and removed on every failure path. Cancel while the command is opening is held until `Started`.
- **SFTP packet framing** (`Sftp.packets`): lengths below 1 or above 16 MiB break the stream; every field read is bounds-checked by `Wire`; a `uint32` length of 2^31 or more is refused; an answer before the version, an unknown answer type, and an extended reply are `Broken`; answers are matched by id through a `Dict`, an id not asked for is ignored, and an answer of the wrong type for its request fails that job only.
- **Offsets and sizes** are `Int64` end to end (`Wire.uint64`/`writeUint64`, `Transfer.Run.offset`, `ShellTransfer` sizes printed with `String.fromInt64`); times after 2038 stay positive (`Sftp.unsigned`).
- **Upload by part**: `ForWritingNew` (EXCL) on `.NAME.puritty-part`, one retry after removing a stale part, `fsetstat` for the time, close, then rename (`posix-rename@openssh.com` when offered), and a fall back to writing in place when the rename is refused. A symlink planted at the part's name is not followed (EXCL; removed and remade). Stale answers and local reads for a file given up are dropped by `withRun`'s job check.
- **Download engine** (library only; the app creates no `Download` job): short reads are asked again for the rest, pipelined reads past the end are absorbed, local paths come only from the caller (`to`, `part`, `keepBoth`), never from a name the server sent. No server-given name is ever used as a local path anywhere in the slice; `PickerSftp` uses them only in requests back to the same server.
- **Pipelining and pacing**: 64 requests of 32 KiB in flight for SFTP, 256 KiB read ahead for the shell, `Connection.sideWaiting` counts only what the window lets go so the pump does not spin on a closed window, session keys go ahead of side data.
- **Session's order of trust**: nothing of authentication is sent before the host's key is settled (`beginAuth` needs both `hostKeyTrusted` and `keysReady`); a revoked key and a changed key under `StrictHostKeyChecking yes` are refused with no question; a key file's private key is loaded, used and forgotten per signature; three passphrase tries.
- **Backend's reconnect** drains inputs left from the ended session up to `Reconnect`, so keys typed at a dead session are not replayed into the new one.
- **Outbox**: the two-list queue, `offer`/`written` with partial writes, joining of small pieces up to 64 KiB; sizes stay consistent.
- **Drop**: `text/uri-list` parsing, percent-decoding, comment lines, Windows paths with a drive letter; `quoted` for a POSIX shell (the paste then goes through the same paste encoder as any paste).
- **Remembered / SecretStore**: names per `user@host:port` and per key path, one-prompt non-echo keyboard-interactive only, written only after `Started`, a refused one forgotten; Linux keeps nothing. (The one gap is the changed-key finding above.)
- **Putty, PuttyStore, SshConfig, SshAgents**: `%XY` unescaping at the string's end, CRLF values, default colours left unset, Pageant's pipe name as an SSH string hash; no problems found.

## Not covered

- `Ssh.Auth`, `Ssh.Agent`, `Ssh.KnownHosts`, `Ssh.Config`, `Ssh.Transport` were read only where `Session` calls them (the order `Auth` tries identities in, and `Agent.unframe`'s length limit, were not checked).
- `Picker.geng` (what it does with stale or repeated `Listed` answers, and how it shows names with control characters) and `Dialog.geng`.
- `packages/win32`'s `Credentials` C (`CredReadW`/`CredWriteW`) and `Registry.puttySessions`: only their Geng callers were read.
- `Backend.geng`'s OpenSSH `ControlMaster` side channels (FT31) beyond the built-in client's part.
- How `Main` uses PuTTY sessions as hosts (`SettingsProgram.geng`), e.g. whether a `ProxyHost` naming another session resolves when that session is not yet a host of the settings.
- Nothing was built or run: findings marked plausible (fish/csh parsing, stack depth, socket finalizers, output back-pressure) want a small reproduction before a fix.

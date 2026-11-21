# 14 · The `os` package (puritty's dependency, /home/gram/prj/geng-lang/packages/os)

Scope: `src/Os/*.geng`, `src/Os/Internal*`, `src/Ext/linux/*.c`, `src/Ext/windows/*.c`, both `geng_os.h`.
All paths below are absolute. `OS` stands for `/home/gram/prj/geng-lang/packages/os/src`.
puritty's entry points (from `grep Os.` over `app/` and `packages/`): `Os.Process` (`spawn`/`spawnAsBytes` with
`Terminal`, `External`, `Ignored`; `run`; `kill`, `waitForExit`, `resize`, `foreground`, `directory`, `currentId`,
`isRunning`), `Os.File` (whole-file calls, handles, `tryLock`, `realPath`), `Os.Directory` (`createAll`, `list`,
`watch`), `Os.Net` (`connect`, `connectLocal`, `writeSome`/`writable`, `limitUnsent`), `Os.Env`, `Os.Random.bytes`,
`Os.Path`, `Os.Error`. `Os.Signal` and `Os.Net.listen` are not used by puritty (tests aside).

Nothing was built or run; every finding is from reading. Where the claim rests on libc, kernel or Win32 behaviour I
could not exercise here, it says `plausible`.

---

### OS1 · `Os.Net.connect` looks names up with `AI_ADDRCONFIG`, so loopback and literal addresses fail on a machine with no routable address of that family
- Where: OS/Ext/linux/geng_os_net.c:57 (`hints.ai_flags = AI_ADDRCONFIG;`), used by `connect` and `listen` (OS/Os/Net.geng:101, :220); the same flag at OS/Ext/windows/geng_os_net.c:117
- Kind: bug
- Severity: medium
- Confidence: plausible (glibc behaviour recalled, not run here)
- What: every host, including a numeric literal, goes through `getaddrinfo(host, NULL, {AF_UNSPEC, AI_ADDRCONFIG})`. glibc's `AI_ADDRCONFIG` does not count loopback addresses as "configured", and when only one family has a non-loopback address it narrows the lookup to that family; an IPv4 literal then answers `EAI_ADDRFAMILY`, which `geng_os_error.c:39-41` maps to `NotFound`.
- Scenario: a laptop with Wi-Fi off but an interface carrying only an IPv6 link-local address (or nothing but `lo`): `ssh 127.0.0.1 -p 2222` to a local VM/container, or a tunnel on `localhost`, fails in puritty's built-in client with "NotFound" while OpenSSH connects. `localhost` resolves to `::1` only, so a server bound to 127.0.0.1 is refused.
- Fix: do not pass `AI_ADDRCONFIG` for numeric literals (try `AI_NUMERICHOST` first, which also skips the thread), and consider dropping it altogether: Happy Eyeballs already makes an unusable family cheap (the attempt fails at once with `ENETUNREACH`).

### OS2 · Windows: a child that is not on a pseudo console is started without `CREATE_NO_WINDOW`, so a GUI program's helper opens a console window
- Where: OS/Ext/windows/geng_os_process.c:586 (`CreateProcessW(..., EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT, ...)`)
- Kind: bug
- Severity: medium
- Confidence: plausible (Win32 behaviour; not run)
- What: the creation flags are the same for every connection. A process linked for the GUI subsystem (puritty is, `-mwindows`, /home/gram/prj/puritty/docs/windows.md:75) has no console, so a console-subsystem child with `Ignored`, `External` or `run`'s captured pipes is given a new, visible console by the system.
- Scenario: puritty on Windows runs `ssh -G host` (`Process.run`, /home/gram/prj/puritty/app/src/Main.geng:1278) or starts `ssh` with `External` pipes (/home/gram/prj/puritty/app/src/Backend.geng:275): a black console window appears for the life of each helper.
- Fix: add `CREATE_NO_WINDOW` when the connection is `IGNORED`, `EXTERNAL` or `CAPTURED` (node's `windowsHide`); leave `INTEGRATED` and `TERMINAL` as they are.

### OS3 · `Process.run` cannot end a program that ignores `SIGTERM`: the time limit and the output limit both hang
- Where: OS/Os/Process.geng:218-241 (`collect`), :269-296 (`readUpTo`), :310-318 (`startTimer`); OS/Ext/linux/geng_os_process.c:754-760 (`kill` is `SIGTERM` only)
- Kind: bug
- Severity: medium
- Confidence: confirmed (by reading)
- What: `runDuration` and "wrote past `maximumBytesWrittenToStreams`" both call `killExtern` once and then keep waiting: `collect` waits for both pipes to reach their end and then for the exit. There is no escalation to `SIGKILL`, and the pipes are only closed by `Task.finally` after `collect` returns. `Os.Process` exposes no other signal.
- Scenario: a child that traps or ignores `SIGTERM`, or one that exits but leaves a grandchild holding the pipe's write end (`sh -c 'sleep 1000 &'`): `run` with `Milliseconds 5000` never answers. When one stream goes over the limit the other stream's reader is still waited for, so a child that keeps writing after `SIGTERM` keeps the task alive (and `readUpTo` on the other stream keeps accumulating up to its own limit).
- Fix: after the limit, close this program's ends of the pipes and stop reading rather than waiting for the end; give `kill` a forced form (`SIGKILL` after a grace period, as `TerminateProcess` already is on Windows) and use it in `run`. The Windows/Linux difference in what `kill` means (catchable request vs. immediate end) is worth a constructor rather than a doc sentence.

### OS4 · A child inherits every ignored signal: only `SIGPIPE` is set back to its default
- Where: OS/Ext/linux/geng_os_process.c:423-430 (`sigaddset(&pipe_only, SIGPIPE); posix_spawnattr_setsigdefault(&attributes, &pipe_only);`)
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: the mask is emptied, but dispositions other than `SIGPIPE` are inherited. Handlers reset on exec; `SIG_IGN` does not. The header comment (lines 53) says exactly this and no more.
- Scenario: `nohup puritty &`, or a launcher/session manager that starts it with `SIGHUP`, `SIGINT` or `SIGQUIT` ignored: every shell in every tab, and every program those shells start, runs with that signal ignored. Closing a tab hangs the terminal up (`SIGHUP`), which the programs on it now ignore, so they are left running; with `SIGINT` ignored, Ctrl-C does nothing in non-interactive children. xterm and the other emulators reset all dispositions before exec for this reason.
- Fix: fill the `setsigdefault` set with every signal (`sigfillset`; the kernel skips `SIGKILL`/`SIGSTOP`) for a `TERMINAL` child at least, and arguably for every child.

### OS5 · `readFile` blocks the scheduler on a FIFO or device and reads without bound before it checks the size
- Where: OS/Ext/linux/geng_os_file.c:105-130 (open at :107 without `O_NONBLOCK`; `if (used > INT32_MAX) return ... EFBIG` only at :127 after the loop); the same shape at OS/Ext/windows/geng_os_file.c:161-186
- Kind: bug
- Severity: medium
- Confidence: confirmed (by reading)
- What: `open_path(p, O_RDONLY, 0)` then `read` until 0, doubling the buffer. Unlike `Os.File.open` (D775) nothing here looks at what the path is. The 2^31 limit is tested after everything has been read into memory.
- Scenario: (1) a path that is a FIFO with no writer (`mkfifo ~/.config/puritty/settings.toml`, or a key/identity path, or a dropped "image" path): `open(2)` blocks the one thread, and the window freezes for good. (2) `/dev/zero` or any endless source: memory doubles until the process dies. (3) a 3 GB regular file: 3 GB is read on the UI thread and then thrown away for `EFBIG`.
- Fix: `fstat` first and refuse what is not a regular file (or route FIFOs through the non-blocking path `open` already has); fail with `EFBIG` from `st_size` before reading, and cap growth at `INT32_MAX` inside the loop for files that do not say their size.

### OS6 · `File.copy` of a file onto itself empties it
- Where: OS/Ext/linux/geng_os_file.c:146-166; OS/Ext/windows/geng_os_file.c:202-223
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: `in = open(source, O_RDONLY)` then `out = open(target, O_WRONLY|O_CREAT|O_TRUNC)` (Windows: `CREATE_ALWAYS`) with no check that the two are one file. The truncation happens before the first read, which then answers the end.
- Scenario: `copy { from = p, to = p }`, or two spellings/links of one file (`a` and `./a`, a symlink, a hard link): the task succeeds and the file is 0 bytes. `cp` refuses this by comparing `st_dev`/`st_ino`.
- Fix: after opening `in`, `stat` the target and fail (`EINVAL`-like, or succeed as a no-op) when device and inode match; on Windows compare `GetFileInformationByHandle`'s volume serial and file index. A copy that fails midway also leaves a truncated target; copying to a temporary name and renaming would fix both.

### OS7 · `Os.Env.executable` answers a path ending in ` (deleted)` after the binary is replaced, and its doc says otherwise
- Where: OS/Ext/linux/geng_os_env.c:103-113; doc at OS/Os/Env.geng (`executable`: "A file moved or removed since the program started answers where it was")
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed (C comment at :103-105 says the suffix is kept)
- What: `readlink("/proc/self/exe")` is answered as it is. For a replaced binary the kernel's text is `/usr/bin/puritty (deleted)`, which is not "where it was" and names no file.
- Scenario: puritty is upgraded by the package manager while running (the old inode is unlinked). Opening the settings window spawns `Os.Env.executable`'s path (/home/gram/prj/puritty/app/src/SettingsProgram.geng:719, /home/gram/prj/puritty/app/src/Main.geng:3568) and fails with `NotFound` on a path the user never typed, until puritty is restarted. The same suffix comes back from `Os.Process.directory` (OS/Ext/linux/geng_os_process.c:575-589) when a shell's working directory was removed, and "open a new tab where the user is" then fails on `/x/y (deleted)`.
- Fix: for self re-exec, spawn `/proc/self/exe` itself (it execs the running image even when unlinked) or strip the suffix after checking the link's target does not exist; for `directory`, answer `Nothing` when the target ends in ` (deleted)` and does not exist. Correct the doc sentence either way.

### OS8 · `File.move` mis-decodes a failure about its second path
- Where: OS/Os/File.geng:149-152 (`Row.attempt "move" (Just from)`); OS/Ext/linux/geng_os_file.c:174 and OS/Ext/windows/geng_os_file.c:231 (`return geng_os_fail(wait, ... + GENG_OS_SECOND)`); OS/Os/Internal/Row.geng `attemptBetween` is the only decoder of `GENG_OS_SECOND`
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: the C row adds `GENG_OS_SECOND` (1 << 20) when `to` holds a NUL (Linux) or is not WTF-8 (Windows), but the Geng side uses `Row.attempt`, which hands the raw code to `geng_os_error_kind`/`detail`.
- Scenario: `move { from = ok, to = <bytes with NUL> }` fails with kind `Other`, path `from`, detail "Unknown error 1048575" (Windows: "Windows error 1048574") where `InvalidPath` about `to` is meant.
- Fix: use `Row.attemptBetween "move" from to`, as `copy` does; the row already reports rename(2)'s own failures without the offset, so they stay about `from`.

### OS9 · Linux `Directory.list` stores young names into its answer without the write barrier
- Where: OS/Ext/linux/geng_os_directory.c:121-131 (`items[k] = geng_os_bytes(...)`, `items[count] = kinds`); compare OS/Ext/windows/geng_os_directory.c:141-177, which calls `geng_write_barrier` after each store
- Kind: bug
- Severity: low
- Confidence: plausible (depends on the runtime's nursery; traced through `packages/c-backend/runtime/geng.c:508-551` only)
- What: an array over 32 KB (more than about 4,090 entries) is allocated old (`take > CHUNK`), and is scanned for young pointers once, at the next minor collection (`old_object_alloc` pushes it on `N.remembered`). Names stored after that collection are young pointers in an old object that nothing remembers.
- Scenario: listing a directory large enough that the loop's own allocation (a `Bytes` per name) spans two minor collections (4 MiB nursery budget: on the order of 70,000+ entries, fewer if the nursery was nearly full): the names stored between the first and second collection are freed or moved without the array being updated, and `list` answers dangling `Bytes`. The Windows row was written with this in mind; the Linux one predates it. The same unbarriered pattern, harmless only because the arrays are small, is at OS/Ext/linux/geng_os_env.c:25, :47-49 and OS/Ext/linux/geng_os_process.c:485-499.
- Fix: `geng_write_barrier(answer, &items[k], items[k])` after each store, as the Windows row does.

### OS10 · Windows `make_pipe` leaves closed handle values in its out-parameters, and the spawn's cleanup closes them again
- Where: OS/Ext/windows/geng_os_process.c:343-357 (failure paths `CloseHandle(*ours)` / `CloseHandle(*theirs)` without resetting them), :549-551 and :599-602 (the caller then runs `close_all(&theirs[k], 1)` and `close_all(ours, 3)`)
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: when `CreateFileW` or `geng_overlapped_bind` fails inside `make_pipe`, the handles are closed but `*ours` (and in the bind case `*theirs`) still hold the closed values, which are neither `INVALID_HANDLE_VALUE` nor `NULL`, so the spawn's error path calls `CloseHandle` on them a second time.
- Scenario: a rare failure (handle quota, a squatter on the predictable pipe name making `CreateFileW` answer `ERROR_PIPE_BUSY`). Between the two closes the lookup thread, a console-read thread or the thread pool can be given the same handle value, and the second close then closes a socket or pipe that belongs to something else.
- Fix: set `*ours = *theirs = INVALID_HANDLE_VALUE` on every failure path of `make_pipe`.

### OS11 · Windows `Os.Random.bytes` spins forever if `rand_s` fails, and `makeTemporary` ignores the failure
- Where: OS/Ext/windows/geng_os_random.c:17 (`while (rand_s(&word) != 0) {}`); OS/Ext/windows/geng_os_directory.c:273-277 (`rand_s(&r); tail[k] = letters[r % 62];`)
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: the Linux row answers `getrandom`'s `errno`; the Windows row has no failure path at all and retries without bound on the scheduler's thread. `makeTemporary` goes the other way and uses `r = 0` when the call fails, so every name is `prefix` + "aaaaaa".
- Scenario: `rand_s` failing persistently (it wraps `RtlGenRandom`; rare, but it is the one case a key generator must not hide): the window hangs with no error instead of the ssh client reporting that it cannot make a key.
- Fix: answer the error after the first failure (`Os.Random.bytes` already has `Task Error`), and treat a failed `rand_s` in `makeTemporary` as the row's failure.

### OS12 · `reap` reads any `waitid` failure as "the child has exited"
- Where: OS/Ext/linux/geng_os_process.c:688-702 (`if (r == 0 && info.si_pid == 0) return 0; child->exited = 1; child->code = r == 0 && ... : -1;`)
- Kind: bug
- Severity: low
- Confidence: plausible (kernel version behaviour not run)
- What: the comment covers `ECHILD` (the kernel reaped it). But `pidfd_open` exists from Linux 5.3 and `waitid(P_PIDFD)` only from 5.4; on a 5.3 kernel `by_pid` stays 0 and `waitid` answers `EINVAL`, which this takes as an exit with code -1, closing the pidfd and leaving the real child running, unwatched and later a zombie.
- Scenario: SLES 15 SP2 / Leap 15.2 class kernels (5.3.18): `waitForExit` on a just-started shell answers -1 at once, so every tab "exits" as it opens. The RHEL8 work (§OS36) covered 4.18 through `ENOSYS` on `pidfd_open`; this is the gap between the two calls.
- Fix: treat only `ECHILD` as "reaped elsewhere"; on `EINVAL`/`ENOSYS` from `waitid` switch the process to `by_pid` (the child's pid is readable from `/proc/self/fdinfo/<pidfd>`, or keep the pid from `posix_spawn` alongside the pidfd).

### OS13 · A scoped IPv6 address loses its scope, so link-local hosts cannot be reached
- Where: OS/Ext/linux/geng_os_net.c:67-69 (only `sin6_addr` is copied into the 17-byte entry), :175-179 (`sin6_scope_id` left 0); the same at OS/Ext/windows/geng_os_net.c:77-81, :126-128
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: an entry is family + 16 address bytes. `getaddrinfo("fe80::1%eth0")` answers the scope in `sin6_scope_id`, which is dropped, and `connect` to a link-local address with scope 0 fails with `EINVAL`.
- Scenario: `ssh fe80::1234%enp3s0` (common for reaching a device with no configured address) fails with kind `Other`, "Invalid argument".
- Fix: widen the entry by four bytes for the scope id and carry it into `sockaddr_in6`.

### OS14 · Windows: the refusal of batch files is bypassed by a trailing dot or space
- Where: OS/Ext/windows/geng_os_process.c:230-233 (`is_batch`: last four characters are `.bat`/`.cmd`), :208-209 (`is_file(program)` for a name with a separator), :504
- Kind: security
- Severity: low
- Confidence: plausible (Win32 name normalisation; not run)
- What: Win32 strips trailing dots and spaces from a path's last component, so `C:\x\run.bat.` and `C:\x\run.cmd ` pass `is_file`, fail `is_batch`, and `CreateProcessW` runs the batch file through `cmd.exe` with a command line quoted by the C runtime's rules. This is the hole Rust closed after the first BatBadBut fix (CVE-2024-43402).
- Scenario: only when the program's name comes from somewhere less trusted than its arguments are meant to be; with it, an argument such as `"&calc"` becomes a command. puritty's program names are the user's own settings, so exposure is small.
- Fix: test the extension after trimming trailing dots and spaces (or on `GetFullPathNameW`'s answer).

### OS15 · Closing a handle does not cancel the reads and writes parked on it (Linux)
- Where: OS/Ext/linux/geng_os_file.c:584-593 (`close` sets `h->fd = -1` and closes), :335-338 (`pending_wait` registers the descriptor's number with `geng_io_wait`)
- Kind: bug
- Severity: low
- Confidence: plausible (rests on how the scheduler's `poll` treats a stale number)
- What: a read parked in `poll` holds the descriptor's number, not the handle. After `close`, the number is free; if nothing reuses it, `poll` reports `POLLNVAL` and the read fails with `EBADF`, which is fine. If an `open`, `accept`, pty or pipe made in the same turn is given the number, the stale wait now watches that other file and fires only when it is ready (the read then fails `EBADF`, since it reads `h->fd`). Windows cancels in-flight operations in `close` (OS/Ext/windows/geng_os_file.c:830); Linux does not.
- Scenario: a tab is closed while its reader is parked, and a new tab is opened in the same update: the old reader's task stays parked until the new pty first produces output, or forever if the new descriptor is never readable (a listener, an idle pipe). It also counts as a wait for the stall rule.
- Fix: keep the handle's parked `pending`s on the handle (Windows already keeps `reading`/`waiters`) and, in `close`, `geng_io_cancel` each and fail its wait with `EBADF`.

### OS16 · No way to say a file's permissions, and no way to make a write durable
- Where: OS/Ext/linux/geng_os_file.c:137, :309 (`0666`); OS/Ext/linux/geng_os_directory.c:22, :36, :41 (`0777`); OS/Os/File.geng (`Metadata` has no mode; no `sync`)
- Kind: design
- Severity: low
- Confidence: confirmed (by reading)
- What: every file is made `0666 & ~umask` and every directory `0777 & ~umask`; `Metadata` carries no mode, and there is no `fsync`/`FlushFileBuffers`.
- Scenario: (1) puritty's ssh client creates `~/.ssh` through `Directory.createAll` (/home/gram/prj/puritty/packages/ssh/src/Ssh/Session.geng:983) as 0755 where OpenSSH makes it 0700, and anything secret a program writes (session state, logs, a future key file) is world-readable under the usual umask; it also cannot refuse a private key file that is group/world-readable, as OpenSSH does. (2) puritty's "write `.new`, then `move`" pattern (SettingsFile, RecentFile, FolderFile, Restore, known_hosts) is atomic against a crash of puritty but not against power loss: without an `fsync` before the rename, a file system that does not order data before the rename can leave a zero-length settings or `known_hosts` file.
- Fix: an optional mode on `open`/`writeFile`/`create` (ignored on Windows) and the mode's low bits in `Metadata`; a `File.sync : Handle -> Task Error {}` or a `writeFileAtomically` that writes, syncs and renames in one row.

### OS17 · `Path.append` onto a verbatim base keeps a child's `/`, `.` and `..` in the bytes while its names say otherwise (Windows)
- Where: OS/Os/Path.geng:309-340 (`names = base.names ++ child.names`, bytes are `base.bytes ++ sep ++ rest`); `split`/`keep` at :683-703 drop `.` and split on `/` only when not verbatim
- Kind: bug
- Severity: low
- Confidence: plausible (Windows syntax only; not run)
- What: the child's `names` were split by the child's own (non-verbatim) rules, but its bytes are pasted after a `\\?\` base, where `/` is not a separator and `.`/`..` are ordinary names. The result keeps the base's `verbatim = True`, so `names` and `bytes` disagree: `==`, `components`, `parent` and `filename` describe one path and `toBytes` hands the system another.
- Scenario: `File.realPath` answers verbatim paths on Windows (OS/Ext/windows/geng_os_file.c:301-316). `Path.append (Path.fromString "sub/file.png") real` then has names `[.., "sub", "file.png"]` and bytes `\\?\C:\dir\sub/file.png`, which Windows reads as one component holding a `/` and refuses with `ERROR_INVALID_NAME`.
- Fix: when the base is verbatim and the child is not, write the child's names joined by `\` (as `plain` does) instead of its bytes as written.

### OS18 · Windows `writeFile` and `open … CreateOrEmpty` fail on an existing hidden or system file
- Where: OS/Ext/windows/geng_os_file.c:193 (`open_file(p, GENERIC_WRITE, CREATE_ALWAYS, 0)`), :799-801
- Kind: bug
- Severity: low
- Confidence: plausible (Win32 behaviour; not run)
- What: `CreateFileW` with `CREATE_ALWAYS` and `FILE_ATTRIBUTE_NORMAL` answers `ERROR_ACCESS_DENIED` when the existing file has the Hidden or System attribute and the call does not name it. Linux has no counterpart.
- Scenario: a user hides their settings file (or a synced-profile tool does): saving settings fails with `PermissionDenied` though the file is theirs and writable.
- Fix: open with `OPEN_ALWAYS` and truncate (`SetEndOfFile`), as Rust's `File::create` does since the same report.

### OS19 · Happy Eyeballs waits a full delay again after a failure while another attempt is in flight
- Where: OS/Os/Net.geng:304-309 (a fresh `Process.sleep attemptDelay` each turn), :328-343 (`Failed` → `eyeballs` again)
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed (by reading)
- What: the doc (Net.geng:74-78) says each address is "started 250 ms after the one before unless that one failed sooner". The next address starts at once only when no attempt is left in flight (`Array.isEmpty state.flying` → `startNext`). With another attempt still in flight, a failure re-enters `eyeballs`, which starts a new 250 ms sleep, so the next address waits a whole delay from the failure, and every further failure resets it.
- Scenario: first address black-holed (SYN dropped), second refused after 5 ms, third reachable: the third starts 255 ms later than RFC 8305 §5 has it. Small, but it is per failed address.
- Fix: on `Failed`, call `startNext` when anything is waiting (a failed attempt is the signal to start the next), or carry the timer's deadline in the state instead of restarting it.

### OS20 · `makeTemporary` takes a prefix with separators in it
- Where: OS/Ext/linux/geng_os_directory.c:182-193; OS/Ext/windows/geng_os_directory.c:262-283
- Kind: bug
- Severity: low
- Confidence: confirmed (by reading)
- What: the prefix is pasted after `TMPDIR/` as it is. `"../x"` makes the directory outside the temporary directory, and `"a/b"` fails with `NotFound` about a path the caller did not write. The doc says "in `temporary`".
- Scenario: a prefix built from a name (a host, a session title) holding `/` or `..`.
- Fix: refuse a prefix holding a separator (and `\`/`:` on Windows) with `InvalidPath`.

### OS21 · A pipe or socket write costs four system calls
- Where: OS/Ext/linux/geng_os_file.c:434-451 (`write_pipe`: `sigpending`, `pthread_sigmask`, `write`, `pthread_sigmask`, and `sigtimedwait` on `EPIPE`)
- Kind: efficiency
- Severity: low
- Confidence: confirmed (by reading)
- What: every write on a pty master, a child's pipe or an ssh connection brackets `write(2)` with three signal calls so that `EPIPE` does not raise `SIGPIPE`. The path is hot in the sense that it runs per keystroke and per outgoing ssh packet (an SFTP upload is thousands of them per second).
- Scenario: cost, not wrong output: roughly 3 extra syscalls per packet on uploads.
- Fix: for sockets use `send(fd, data, n, MSG_NOSIGNAL)` (one call); a pty master never raises `SIGPIPE` (it fails `EIO`), so it needs no guard; keep the mask dance for real pipes only.

---

## Looked at and found sound

- **fork/exec and pty (Linux)**: `posix_spawn`/`pidfd_spawn` with nothing run between fork and exec; `POSIX_SPAWN_SETSID` precedes the file actions in glibc, so the slave opened without `O_NOCTTY` becomes the controlling terminal; `IUTF8` and `TIOCSWINSZ` set on the master before the spawn; master is `O_CLOEXEC`; exec failure comes back as `posix_spawn`'s code; every error path in `geng_os_process_spawn` goes through `close_all(fds, 8)`; the child's ends are closed in the parent after the spawn; `addclosefrom_np(3)` or the `/proc/self/fd` sweep keeps other descriptors out of the child; every `open`/`pipe2`/`socket`/`accept4`/`inotify_init1` carries `CLOEXEC`.
- **Reaping**: the quiet pidfd wait reaps children nobody waits for (D774); the `SIGCHLD` self-pipe fallback is async-signal-safe (saves `errno`, one `write`), drains fully, and asks every listed child with `WNOHANG`; kill is refused once `exited` is set, so a pid is never signalled after the reap.
- **EINTR/EAGAIN/partial I/O**: `read_some`, `write_all`, `try_write`, `writeSome`, `open_path`, `connect`, `accept4`, `flock`, `ftruncate`, `getrandom` all retry `EINTR`; non-blocking reads and writes wait in `poll` on `EAGAIN`; a pty's `EIO` is the end; `close` is never retried.
- **Non-blocking connect**: `EINPROGRESS` → `POLLOUT` → `SO_ERROR`; attempts are closed by `Task.bracket` however the race ends; the lookup runs on its own thread and its cancel no longer reads freed memory (§OS34); `TCP_NODELAY` set on take.
- **Random (Linux)**: `getrandom` short reads and `EINTR` handled, errors reported.
- **Error mapping**: `errno`/`GetLastError`/WSA/`EAI_*` codes are kept and carried to `Os.Error` with kind and the platform's text; `GENG_OS_SECOND` decoding is right for `copy` and `spawn` (wrong only for `move`, above).
- **Windows command line**: `put_argument` quotes by the CRT's rules correctly (backslash runs before a quote doubled plus one, trailing run doubled, empty argument quoted), `geng_os_env_args` is its inverse; a `"` in the program's name is refused; line length checked against 32,767; `.bat`/`.cmd` refused (but see the trailing-dot finding).
- **Windows handles**: `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` limits inheritance to the three given handles; a pseudo-console child inherits none; named pipes use `FILE_FLAG_FIRST_PIPE_INSTANCE`, one instance and `PIPE_REJECT_REMOTE_CLIENTS`; `ClosePseudoConsole` runs off the loop's thread; sockets are `WSA_FLAG_NO_HANDLE_INHERIT`; `closesocket` vs `CloseHandle` kept apart.
- **WTF-8**: `geng_os_wtf8`/`geng_os_wide` sizes and round trip, overlong and out-of-range forms refused, a surrogate pair spelled as two refused, NUL refused.
- **Paths**: NUL bytes refused before every C call (`GENG_OS_CPATH`/`GENG_OS_WPATH`); non-UTF-8 names pass as bytes; `getcwd`/`readlink` buffers grow; `sun_path` length checked; `mkdtemp` for temporary directories; `removeAll` does not follow links on either platform.
- **Race give-back (D1045)** for reads and accepts on both platforms, and `unkeep` before seek/write/truncate.
- `Os.Path` on Linux syntax (`parent`, `append`, `withExtension`, `relativeTo`, ordering), `Os.Env`, `Os.Error`, `Os.Internal*`, directory watching on both platforms (inotify parse and re-arm, `ReadDirectoryChangesW` cancel-then-close).

## Not covered

- `Os.Signal` and its two C files were read once but not traced against the runtime's signal masks (puritty does not use them).
- `Os.Net.listen`/`accept` and the Windows `AcceptEx` path only lightly (puritty does not use them outside tests). Two parity notes not written up as findings: an `AcceptEx` error fails the accept where Linux retries `ECONNABORTED`, and a `::` listener is dual-stack on Linux but IPv6-only on Windows (no `IPV6_V6ONLY` set on either).
- The Windows console-input path (`read_console`) and standard handles: puritty is a GUI program there.
- The runtime (`packages/c-backend/runtime`) was read only as far as needed to judge the write-barrier and pinning questions; whether conservative stack scanning covers interior pointers such as `geng_array_items` results held across allocations (e.g. `environment()` in OS/Ext/linux/geng_os_process.c:222-240) is the runtime's contract and was not verified.
- Windows `Os.Path` prefixes (`windowsRoot`) were read but not checked case by case against Rust's `Prefix`.
- Nothing was compiled or run, so every Win32 and glibc behaviour cited is from knowledge of those platforms, marked `plausible` where the finding depends on it.

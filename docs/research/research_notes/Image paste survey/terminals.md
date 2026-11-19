# Image paste survey: terminals and protocols

Research notes, 2026-11-19. Scope: how a terminal lets a program on the far
side of the pty (over ssh, maybe in tmux) get non-text clipboard data such as
`image/png`, and what terminals do when the user pastes while the clipboard
holds only an image. How programs read images is in `programs.md`.

## Summary

1. The one in-band protocol for typed clipboard data is kitty's **OSC 5522**.
   Its **paste events** (private mode 5522) make it fit the paste case: on the
   user's paste key, the terminal sends the MIME list and a one-time password,
   and the program asks for `image/png` with no prompt.
2. It is shipped by **kitty** (protocol since 0.27/0.28, paste events 0.44.1/0.45),
   **Ghostty 1.4.0** (2026-10-27, macOS and GTK) and **contour** (v0.7.0, 2026-08).
   **foot** has an open PR by its maintainer. **iTerm2, WezTerm, Windows Terminal,
   Konsole and Alacritty** do not have it.
3. **tmux does not pass it through.** It drops mode 5522 and does not parse the
   replies. nicm turned down the request on 2026-11-04 ("not wide enough support yet").
4. **OSC 52 is text only** everywhere I checked. Read (query) support varies and
   is off or prompted by default. Windows Terminal and Konsole ignore a query.
5. **No program supports 5522 paste events yet except omp (oh-my-pi).** Claude Code
   has an open request (anthropics/claude-code#105520). So today a terminal
   that speaks 5522 helps only programs that ask for it.
6. With an image-only clipboard, most terminals **send nothing**, or **an empty
   bracketed paste** (Windows Terminal does this on purpose; it calls it "load
   bearing"), or let the key through (Ghostty `performable:`). The program then
   reads its *own* host's clipboard, which over ssh is empty.
7. The working out-of-band answer is **upload and paste a path**: iTerm2 3.7
   (a dialog with "Upload and Paste Path" over its SSH integration or scp), cmux
   (scp over ControlMaster, for drops), and Ctrl-V Terminal (a Windows SSH client:
   SFTP, then pastes the path). Ghostty and Windows Terminal turned down this kind of
   feature (as a hack, or as too much to maintain).
8. VS Code pastes the *local* file path when the clipboard holds a copied file
   and no text. It does not upload anything over Remote-SSH (as of PR #307501).
9. A side protocol that matters for a PuTTY-derived terminal is the **far2l
   terminal extensions** (APC). They give gesture-gated clipboard reads, are in
   putty4far2l and KiTTY, and carry text and registered formats, but not images in practice.
10. There is no terminal-wg (freedesktop) item on clipboard MIME or image paste.
    The discussion is spread across kitty#9183, ghostty#10549, tmux#5837,
    microsoft/terminal#19517 and the agent CLIs' trackers.

---

## kitty clipboard protocol (OSC 5522)

Source: spec at https://sw.kovidgoyal.net/kitty/clipboard/ (fetched
2026-11-19), and `docs/clipboard.rst` and `docs/changelog.rst` in kovidgoyal/kitty master.

- **Format:** `OSC 5522 ; metadata ; payload ST`. The metadata is `key=value`
  pairs joined by `:`. The payload is standard base64 with padding. The values of
  `mime`, `name` and `pw` are base64 too. Invalid base64 must be rejected with
  `EINVAL` for writes, and is ignored for reads.
- **Read:** `type=read` with a payload of base64 space-separated MIME types.
  `loc=primary` reads the primary selection. The reply is `status=OK`, then one or
  more `status=DATA:mime=<b64>` packets, then `status=DONE`. Each chunk is at most
  4096 bytes *before* base64, and one type finishes before the next starts.
  To list the available types, request MIME `.` (base64 `Lg==`). **Listing
  needs no permission prompt.**
- **Read errors:** `ENOSYS` (e.g. no primary selection), `EPERM` (denied),
  `EBUSY` (e.g. a multiplexer with a request in flight).
- **Write:** `type=write`, then `type=wdata:mime=<b64>;<b64 chunk>` packets
  (4096-byte chunks), then an empty `type=wdata` to end. The reply is
  `type=write:status=DONE`, or `EIO`, `EINVAL`, `ENOSYS`, `EPERM`, `EBUSY` or `EFBIG`.
  `type=walias` registers other MIME names for the same data.
- **Size:** a terminal may cap writes and answer `EFBIG`, but must accept
  at least **64 MB**. kitty's `clipboard_max_size` defaults to 512 MB
  (`kitty/options/definition.py`). Since 0.49.0 (2026-09-21) an oversized write
  gets `EFBIG` and is no longer truncated (changelog, issue 10399).
- **Permission:** kitty's `clipboard_control` defaults to
  `write-clipboard write-primary read-clipboard-ask read-primary-ask`. Every
  read asks, unless the program sends `pw` with `name` (added in 0.42.2) and
  the user grants "allow all future requests with this password" for that tty.
  A `pw` without `name` counts as no password. kitty's doc warns that turning
  off the read prompt lets "even the ones running on a remote server via SSH"
  read the clipboard.
- **Paste events (mode 5522):** added in 0.44.1 (doc `versionadded`); the
  changelog lists it in the 0.45.0 section (2025-12-24), as kitty issue 9183.
  The program sets `CSI ? 5522 h`. On the user's paste, the terminal sends,
  *instead of* bracketed paste, an unsolicited MIME listing with a one-time `pw`.
  The program then reads with `pw` and `name=Paste event` (base64 `UGFzdGUgZXZlbnQ=`)
  and gets no prompt.
- **Detection:** DECRQM `CSI ? 5522 $ p`. A reply of `Ps` 0 or 4 means not
  supported.
- **Multiplexers:** an optional `id` (`[a-zA-Z0-9-_+.]`) is echoed in every
  reply. Only one request should be in flight, and the others get `EBUSY`.
  Paste events carry no `id`, so the multiplexer forwards them to the active window.
- **History:** the clipboard kitten that copies "arbitrary data types, not
  just plain text" is in the 0.27.0 changelog (2023-01-31). The spec page does not name
  the version that brought OSC 5522 itself (not verified).

### The paste-events spec (rockorager)

Source: https://rockorager.dev/misc/bracketed-paste-mime/ (dated 2025-11-04,
changelog through 2026-08-04). Kitty issue 9183 (2025-11-03) is where Kovid and
rockorager settled it. Kovid asked that the paste event send *the list of
types*, not the data.

- When mode 5522 is set, a paste sends the listing, as if the program had sent
  a read for `.`. The `pw` is optional but recommended, single-use, scoped to the
  clipboard location, and timed out. The `pw` MAY be repeated on DATA and DONE.
- Mode 5522 overrides 2004: "Terminals MUST NOT send both sequence types for
  the same paste event."
- If any requested type is available, the terminal returns the available ones
  and ignores the rest.
- A program that requests without the password gets the terminal's normal
  policy (a prompt).

### Who implements OSC 5522

| terminal | read/write | paste events (mode 5522) | source |
|---|---|---|---|
| kitty | yes | yes, 0.44.1+ | spec; changelog |
| Ghostty | yes, 1.4.0 (macOS and GTK) | yes, 1.4.0 | PRs below |
| contour | yes, v0.7.0.8982 (2026-08-17) | yes (DEC mode 5522 `PasteMimeNotifications`) | PR #2004 |
| foot | open PR | in the PR | codeberg dnkl/foot PR #2341 |
| iTerm2 | no | no | see iTerm2 |
| WezTerm | no | no | see WezTerm |
| Windows Terminal | no | no | see Windows Terminal |
| Konsole | no | no | see Konsole |
| Alacritty | no | no | see Alacritty |
| tmux | blocks it | blocks it | tmux#5837 |
| "Tern" | claimed in tmux#5837 | claimed | not verified |

## Ghostty

### OSC 5522: shipped in 1.4.0

- The parser landed in PR #10560 (merged 2026-02-16). The core landed in #13962
  (2026-08-21). libghostty read/write is #13963 (2026-08-22, "doesn't yet do mode
  5522"). Mode 5522 is enabled in libghostty in #13978 (2026-08-23).
  macOS reads are #13993, macOS writes #13998, macOS paste events #13995 (all 2026-08-24).
  Listing reads are exempt from prompts in #14001.
- **GTK** is PR #14061 (merged 2026-10-26, closes issue #10549). It "Adds an image
  preview to the confirmation dialog." Tag `v1.4.0` (commit dated 2026-10-27)
  contains it. I checked the tag's commit list for `src/apprt/gtk`.
- The write limit is the option `clipboard-write-limit-bytes`, **32 MB by default**
  (PR #14002). That is below the spec's 64 MB floor. Ghostty rejects oversized
  binary writes rather than truncating them, and truncates text at a UTF-8 boundary.
- PR #13992 is the write permission prompt plus grants, and passes the program
  name and the grant to the embedder. PR #14470 stopped showing the program's
  self-declared name in macOS prompts.
- Issue #10549 is closed as completed. The image-paste feature request,
  discussion #10478, was closed by jcollie on 2026-10-18: "solved with the
  introduction of the Kitty clipboard protocol."

### Ghostty PR #10515 "feat(macos): add SSH image paste support". **Not merged.**

The brief said "merged". It was **closed unmerged** on 2026-02-01
(`merged: false`, from the GitHub API). What it did: on Cmd/Ctrl+V with image data
and an active ssh **ControlMaster socket**, it scp'd the image to
`/tmp/ghostty-paste-{uuid}.png` on the remote and pasted that path. The options were
`ssh-image-paste` (default true) and `ssh-image-paste-path` (default `/tmp`).
It was macOS only, in `macos/Sources/Helpers/SSHImagePaste.swift`. It was closed for
breaking the AI policy (a drive-by PR with no accepted issue). A maintainer
(rhodes-b) called it "a hack to scp a file over ssh when you detect its a image",
and said OSC 5522 is the real protocol. The author agreed.

### Ghostty PR #9699 "feat: implement image upload on drag and drop". **Not merged.**

It was closed on 2025-11-25. On a **drag-and-drop** of an image *file* (not
paste), it uploaded to a configured HTTP endpoint (ImgBB, Imgur or custom: multipart,
JSON base64 or binary), pulled a URL out of the response by JSONPath, and pasted the
**URL** in place of the local path. The options were `image-upload-*`, and it
fell back to the path. mitchellh: "No thanks. Good fit for plugins one day."

### Image-only clipboard and no mode 5522

- GTK, PR #10089 (merged 2025-12-29): `paste_from_clipboard` returns false
  when the clipboard has no text format, so a `performable:` binding lets the key
  (e.g. Ctrl+V) through to the program. The program then reads the clipboard
  itself (opencode via `wl-paste`). This is opt-in:
  `keybind = performable:ctrl+v=paste_from_clipboard`.
- macOS got the same in commit aaad43c (PR #11328, 2026-03-10, fixes #10751).
  Whether the *default* bindings became performable: not verified (closed PR
  #10585 proposed that).
- Before that, Cmd+V with a screenshot-only clipboard did nothing (discussion
  #10478, issue #11444).
- Drag-and-drop of an image into Claude Code on macOS was reported as not
  working (#11924, auto-closed, reporter not vouched).
- The kitty drag-and-drop protocol (OSC 72) is open as #12852, with the parser
  merged in #13029.

## OSC 52

- **Text only.** xterm's `OSC 52 ; Pc ; Pd` has a selection parameter and
  base64 data, and no type field. I found **no terminal that sends another MIME type
  through it**. kitty's spec calls 5522 an extension "because OSC 52 only handles plain
  text". WezTerm#8057 describes WezTerm's clipboard API as `String` only.
- **Read (query `?`) support:**
  - kitty: yes, prompt by default (`read-clipboard-ask`).
  - Ghostty: `clipboard-read` (ask by default; Ghostty docs, not re-read today).
    libghostty got OSC 52 reads in PR #13965 (2026-08-22).
  - iTerm2: since 3.5.0, "requires user consent to enable" (iterm2.com/downloads
    release notes). A 3.7 note: query replies "now work with tmux 3.6+ in tmux integration."
  - foot: `security.osc52` option (#1867). DA reply includes `52` when copy is enabled.
  - Alacritty: `terminal.osc52` is `Disabled|OnlyCopy|OnlyPaste|CopyPaste`, default
    `OnlyCopy` (`extra/man/alacritty.5.scd`).
  - WezTerm: **no read**. PR #6239 "implement opt-in OSC52 clipboard querying" has
    been open since 2024-10.
  - Windows Terminal: **no read**. `OutputStateMachineEngine.cpp` parses `?`
    and then does nothing ("`&& !queryClipboard`").
  - Konsole: **no read**. `Vt102Emulation.cpp` handles set and clear only.
  - far2l's terminal ignores OSC 52 read on purpose (VTExts.md §5.7.2).
- **tmux** (tmux.1 on master, 2026-11-16):
  - `set-clipboard on|external|off`. `on` means programs' OSC 52 creates a buffer
    and tmux also sets the outer terminal's clipboard. `external` means tmux sets
    the outer clipboard only. This needs `Ms` in terminfo.
  - `get-clipboard both|request|buffer|off` (**new in 3.7**, default off,
    CHANGES): with `request`, a pane's OSC 52 query is sent to the most recently used
    client's terminal and the reply comes back.
  - `allow-passthrough on|off|all` (3.3, default off; `all` since 3.4):
    `DCS tmux; ... ST` sends a sequence to the outer terminal. It is one-way. A reply
    arrives as client input, and tmux does not route it back for 5522 (tmux#5837).
    Whether a 5522 reply to a passthrough read reaches the pane in any form: not verified.

## tmux and OSC 5522

tmux#5837 "Support kitty paste events (mode 5522) so pasted images reach
applications" (opened 2026-11-04, closed 2026-11-13):

- tmux drops the program's `CSI ? 5522 h` ("input.c ignores the unknown mode").
  The outer terminal keeps sending bracketed paste. If it did send `OSC 5522`,
  tmux does not parse it in `tty-keys.c`. "Without tmux, over plain SSH, the
  same paste works."
- nicm: "I do not think there is wide enough support for this yet."
  mgrant0: "Eventually I think we will add support for both OSC 72 and OSC 5522
  to tmux", after more popular terminals have it. He also sketched tmux itself pulling
  the image over 5522 into a temp file and bracket-pasting the path.
- Related: tmux#5595 (OSC 72 drag-and-drop) was closed. The maintainers asked
  what non-kitty programs use it.
- A workaround that works through tmux today is
  `mindfulmonk/claude-clipboard-ssh`. It is a pty proxy *outside* tmux that does the
  5522 exchange, caches the image, and injects Ctrl+V for an `xclip` stub
  (claude-code#105520). Not tested here.

## iTerm2

Source: gnachman/iTerm2 master, `sources/Pasting/iTermNonTextPasteHelper.swift`
and `PTYSession.m`; iterm2.com/downloads.html release notes.

- **No OSC 5522.** No file or symbol was found in the tree (GitHub code search
  and the tree listing). It does have **OSC 72** (kitty drag-and-drop) since 3.7.0.
  For a remote program, "dropped files are transferred to it over the connection."
- **Image-only clipboard plus paste:** `PTYSession paste:` pastes text when the
  pasteboard has a string. If not (or if it holds file URLs), it calls
  `attemptNonTextPaste`. For raw image data, a **dialog** ("The clipboard contains a
  PNG image (size). How would you like to paste it?") offers:
  - **Upload and Paste Path** and **Upload**, when the session is remote (an SSH
    Integration "conductor", or shell integration reporting a remote host);
  - **Save to temp file and paste path**, unless the session is verified remote;
  - **Paste Base64-Encoded Contents**;
  - Cancel. The dialog can be silenced permanently ("remember").
- Uploads go through the SSH Integration conductor (`it2ssh`) or **scp** to
  the remote cwd, or to home in tmux integration (3.7.5 notes). Screenshots are
  converted from TIFF to PNG and each gets a unique name (3.7.5).
- The feature was added in commit 1ef5c972f4 (2026-03-12, "Add better options for
  dropped or pasted files"). It is in 3.7.x.
- OSC 1337 `RequestUpload=format=tgz` is an older iTerm2 sequence. The program
  asks, the user picks files, and iTerm2 sends a base64 tar.gz.
  claude-code#77864 proposes using it. It is open.

## WezTerm

- No image paste and no 5522. #8057 (closed not planned, 2026-08): "WezTerm's
  clipboard is plain-text only", and macOS clipboard code reads only file URLs
  and text, "so image data in the pasteboard is silently dropped." A PR (#7621)
  that saved the image to a temp file, pasted the path, and had a
  `PasteImageToSshUpload` action (SFTP/SCP) was withdrawn by its author in
  2026-02, unreviewed (per #8057). A maintainer (bew) in #8057: there is no
  standard for telling the program about non-text data.
- OSC 52 read: no (PR #6239 open).

## Windows Terminal

Source: microsoft/terminal main, `src/cascadia/TerminalApp/TerminalPage.cpp`.

- `clipboard::read()` takes `CF_UNICODETEXT`, else the **first** file of `CF_HDROP`
  (a file copied in Explorer pastes its Windows path), else empty.
- **An image-only clipboard gives an empty bracketed paste.** The code comment:
  "LOAD BEARING: Send an empty bracketed paste even if the clipboard was empty.
  Bracketed Paste provides an application a way to know whether the user pasted,
  even if there was no applicable content on it. This behavior is observed in
  GNOME Terminal, among others." Without bracketed paste mode, nothing is sent.
  zadjii-msft in #19517: some TUIs take an empty paste as "go open the system
  clipboard".
- #19517 "Accept image pastes from the clipboard for multi-modal LLMs" is open.
  DHowett asked what format a program would want. lhecker floated a temp file with the
  path pasted ("absolutely will not work if you page into e.g. a process running in
  WSL"). j4james suggested a data URI, as it "has the potential to work across a
  remote connection".
- #20479 "Filter paste and drag-drop payloads through an external program"
  (for ssh image paste) was closed not planned on 2026-07-29: no capacity to maintain it.
- No OSC 5522. OSC 52 is write only.
- #20753 asks for the far2l extensions (open, 2026-09-30).

### WSL

The terminal does not move the image. The Linux program reaches the Windows
clipboard itself: Claude Code falls back to PowerShell through interop, or reads
WSLg's bridged clipboard. WSLg exposes Windows bitmaps as `image/bmp`
(BI_BITFIELDS) and not `image/png`, which breaks some decoders. Sources are community
issue mirrors (claudeissues.com #50552, #89223, #57440). Details are in `programs.md`.
In Windows Terminal, Ctrl+V is taken by the terminal's paste binding, so Claude
Code uses Alt+V there (j4james in WT discussion #19397).

## VS Code integrated terminal

- PR #307501 (merged 2026-04-02, fixes #301603): if the clipboard has no text,
  `paste()` reads `clipboardService.readResources()`, and for a `file:` resource
  pastes its **local fsPath**. A raw bitmap (screenshot) is not handled, and the code
  passes `''` to `_paste`. Whether xterm.js then sends an empty bracketed paste:
  not verified.
- PR #308097: on Windows PowerShell, Ctrl+V goes to PSReadLine as `\x16`
  (PSReadLine reads only `CF_UNICODETEXT`).
- **Remote-SSH: no upload.** Nothing in the paste path is remote-aware. The path pasted
  is local. Third-party extensions fill the gap (humanrace-ai/claude-paste,
  dkodr/claudeboard: save the clipboard image on the remote and type the path).
  These are from search summaries and were not tested.
- #347647 (open, 2026-11-11): terminal file drops bypass bracketed paste.

## Warp

- Local: Cmd+V of image bytes attaches in Claude Code. Drag-and-drop inserted a
  path (warp#9545, closed).
- **SSH: no image paste.** warp#8692 "Image paste not supported in SSH sessions"
  is open (2026-02-15). #8958 was closed as its duplicate. Upload support is tracked
  in #6195, #3131 and #11522 (per the bot in #12779).
- No 5522 issue found.

## cmux (an AI-oriented macOS terminal on libghostty)

- https://cmux.com/docs/ssh: "Drag an image or file into a remote terminal and
  cmux uploads it via scp through the existing SSH connection." It finds "the
  foreground SSH process by TTY and routes the upload through ControlMaster
  multiplexing." It installs a `cmuxd-remote` relay (JSON-RPC over stdio) on the host.
- Changelog 0.64.25: "Images dropped or pasted into a terminal stay on disk until
  cmux quits so Claude Code and Codex can read them" (that is local temp files).
- Whether **Cmd+V** of a clipboard image uploads over ssh: not documented.
  pavzagor in Ghostty #10478 says cmux handles local screenshot paste "out of the box".

## Ctrl-V Terminal (IT WORX, Windows)

- A tabbed SSH/VNC/SFTP client for Windows, sold as a MobaXterm/PuTTY alternative
  (winget `ITWORX.CtrlVTerminal`, 1.2.10). Ctrl+V of an image in a remote
  terminal: "the file is copied over SFTP" and its path is placed at the cursor, for
  Claude Code and Codex (alternativeto.net listing). The remote directory is not stated.
  Not tested. This is the closest competitor to puritty's case.

## Tabby

- No image handling. #11279 (Windows, open): the answer was to use Claude Code's
  Alt+V. #11325 (Wayland, open): Codex image paste fails, though `wl-paste` has
  `image/png`.

## MobaXterm

- No evidence of clipboard-image paste or upload. It has an SFTP browser with
  drag-and-drop (search results only, not verified).

## Konsole

- OSC 52 set and clear only (`Vt102Emulation.cpp`). No 5522. Image paste behavior:
  not verified.

## Alacritty

- No 5522. #8818 (multi-MIME clipboard): chrisduerr: "No". OSC 52 read is opt-in.
  #8764 says Alacritty on macOS can paste unexpectedly when the clipboard holds an image
  (title only, not read).

## far2l terminal extensions (APC), for a PuTTY-based terminal

Source: https://github.com/unxed/far2l/blob/extsdocs/VTExts.md.

- `ESC _ far2l... BEL` APC channel. It has a clipboard with client authorization
  (a per-client ID, and a "share clipboard [always]" dialog), and **reads are allowed only
  for 5 s after the user's own paste gesture** (Ctrl+V, Shift+Insert, middle
  click). Otherwise the read answers 0 bytes.
- Formats: `CF_TEXT` (UTF-8), `CF_UNICODETEXT` (UTF-32), and named formats that
  are registered. `CLIP_GETDATA` returns the whole value in one reply, with no chunked
  download.
- Implemented on the terminal side in **putty4far2l** and **KiTTY** (`MOD_FAR2L`).
  They use the Windows clipboard directly, with text and "registered formats ...
  given out and accepted as opaque data." Whether a client can get a screenshot
  by registering `PNG` is my inference and not verified. Windows apps often add a
  registered "PNG" format, but a Print Screen bitmap is `CF_DIB` only.
- The program side is far2l, f4 and tvision. No AI CLI uses it.
- davidrg in WT#20753 warns that unknown APC strings are not reliably ignored.

## Proposals and discussion, 2025–2026

- kitty#9183 (2025-11): mode 5522 paste events. This became the rockorager spec.
- ghostty#10549 and its follow-ups (2026-02 to 10): implementation. ghostty discussion
  #10478 was closed as solved by 5522.
- tmux#5837 (2026-11): 5522 in tmux, deferred.
- foot PR #2341 (2026-05, open): 5522 and paste events.
- anthropics/claude-code#105520 (open, 2026-10-27): asks Claude Code to use 5522
  paste events in-process. It notes the race that sank #42712's `xclip` shim (two
  readers on one tty), names omp (oh-my-pi) as the only program doing it today, and says
  the packets are dropped inside tmux. #42712 (2026-04, closed as duplicate)
  showed an `xclip -t image/png -o` shim over 5522 working through ssh in kitty.
- anthropics/claude-code#77864 (open, 2026-07): use iTerm2 `RequestUpload`.
- anthropics/claude-code#69330 (2026-06): says image paste over ssh from macOS
  Terminal.app "via the OSC 52 clipboard read protocol" broke in 2.1.181. That OSC 52
  can carry an image is **doubtful and not verified**. Terminal.app's OSC 52 support
  is not checked.
- microsoft/terminal#19517 (open), #20479 (declined), discussion #19397.
- WezTerm#7272 and #8057 (closed).
- warp#8692 (open).
- terminal-wg (gitlab.freedesktop.org/terminal-wg/specifications): no issue
  matching clipboard, paste or 5522 (GitLab API search, 2026-11-19).

## What this means for puritty (notes, not decisions)

- Being the ssh client, puritty knows the session is remote and owns the
  connection. So both the in-band path (5522 with paste events) and the out-of-band
  path (SFTP upload, then a bracketed paste of the remote path) are open to it.
  No other terminal surveyed has both.
- 5522 alone does not help Claude Code today (no support, #105520 open), and
  it does not get through tmux. Upload-and-paste-path works with any program that
  accepts a path, through tmux too, since it is just text.
- The empty bracketed paste (Windows Terminal, GNOME Terminal per WT's comment) is
  a cheap signal, but it only helps a program that reads its own clipboard, which
  over ssh is the wrong machine.

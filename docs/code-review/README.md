# Code review of puritty, 2026-11-21

A review of puritty's own source and of the libraries it is built on, for
problems, inaccuracies, speed, efficiency and design. It was written with
nothing fixed; a finding fixed since says so in its slice file, in a
`Fixed:` line under it, and its row under "Every finding" begins
**fixed**.
This directory is the list of things to fix; each finding is written to be
picked up on its own.

- Reviewed at puritty `9727f2c`, with the dependencies as they stood in
  geng-lang at `f0487747` (`packages/os`, and `vendor/gilramir/gren-toml`,
  `gren-argparse`, `gren-i18next`, `gren-civil-time`).
- Not reviewed: the Geng compiler and its core library; the vendored PuTTY
  code under `packages/ssh-crypto/src/Ext/putty/` (only how puritty calls it);
  generated tables (`Width.geng`, `EucKrIndex.geng`, `KeyTables.geng`,
  `puritty_icon.h`); the tests, harnesses and benches, except where a finding
  names a gap in them.
- 320 findings: 18 high, 105 medium, 197 low. 242 are marked `confirmed` and
  78 `plausible`.

## How far to trust it

The review was done by reading. **Nothing was built, run, timed or tested**,
so:

- `confirmed` means the reviewer traced the path through the source, callers
  included. It does not mean reproduced.
- `plausible` means the path was read but the outcome rests on something not
  exercised: what tmux, an X server, Windows, glibc or a shell does with it.
  Each says what it rests on. These need one run before any fix.
- Every time and byte figure is an estimate from the code or from a number a
  design document records, not a measurement.

Fifteen slices were read separately, one reviewer each, and merged. The high
findings were then read again against the code by a second reader; the table
under "The high findings" says for each what that second reading covered. The
medium and low findings were not read a second time.

## How to work through it

1. Take one finding. Read the code it names before believing it.
2. Make it fail first: a unit test, a corpus case, or for a `plausible` one a
   run against the real tmux, X server, shell or Windows it depends on. A
   finding that cannot be made to fail is closed as not a defect, with the
   reason written beside it.
3. Check the design document the slice names. Some findings contradict a
   numbered decision (they say so); fixing those changes the document too, and
   a few are the owner's decision, not a defect (listed below).
4. Findings in the dependencies (`OS*`, `LB*`) are fixed in geng-lang's
   checkouts, not here.
5. Each finding has an id (`VP1`, `MA4`, ...). Use it in the commit message.

Severity: **high** is a hang, crash, data loss or wrong trust decision that an
ordinary session or a remote program can reach; **medium** is a real defect
with a narrower way in, or a cost that grows; **low** is small, rare, or
cosmetic.

## The slices

| file | ids | what | high | medium | low |
|---|---|---|---|---|---|
| [01-vt-parser-screen.md](01-vt-parser-screen.md) | VP | Terminal core: parser and screen | 2 | 6 | 9 |
| [02-vt-scrollback-view-input.md](02-vt-scrollback-view-input.md) | VS | Terminal core: scrollback, reflow, view, input encoders | 1 | 2 | 7 |
| [03-vt-images.md](03-vt-images.md) | VI | Terminal core: image protocols and decoders | 3 | 9 | 8 |
| [04-ssh-core.md](04-ssh-core.md) | SC | SSH: transport, authentication, channels, crypto glue | 0 | 8 | 19 |
| [05-ssh-session-transfer.md](05-ssh-session-transfer.md) | ST | SSH: session layer and file transfer | 0 | 7 | 20 |
| [06-tmux-package.md](06-tmux-package.md) | TP | packages/tmux (control mode) | 0 | 5 | 15 |
| [07-x11-text.md](07-x11-text.md) | X | Linux window and text layers (C) | 1 | 9 | 19 |
| [08-win32.md](08-win32.md) | W | Windows layer (C) | 1 | 5 | 12 |
| [09-app-main-a.md](09-app-main-a.md) | MA | app/src/Main.geng, first half | 3 | 9 | 13 |
| [10-app-main-b.md](10-app-main-b.md) | MB | app/src/Main.geng, second half | 1 | 6 | 12 |
| [11-tmuxmode-a.md](11-tmuxmode-a.md) | TA | app/src/TmuxMode.geng, first half | 3 | 12 | 7 |
| [12-tmuxmode-b.md](12-tmuxmode-b.md) | TB | app/src/TmuxMode.geng, second half | 1 | 9 | 11 |
| [13-app-picker-settings.md](13-app-picker-settings.md) | PS | Picker, dialogs and settings | 2 | 11 | 14 |
| [14-dep-os.md](14-dep-os.md) | OS | Dependency: the os package | 0 | 4 | 17 |
| [15-dep-libs.md](15-dep-libs.md) | LB | Dependencies: TOML, argparse, i18next, civil-time | 0 | 3 | 14 |

## The high findings

The search finding was reported by three slices and the link finding by two,
so the eighteen are fifteen distinct problems. "Second reading" is what was checked again
after the merge.

| ids | problem | second reading |
|---|---|---|
| VP1 | `CSI n T`, `CSI n L`, `CSI n M` loop the raw count, up to 65,535, not the region's height: nine bytes cost 65,535 row shifts | Holds. `Dispatch.geng:530` computes a clamped `count` and uses it only for images; `regionDown` (`Scroll.geng:501`) recurses once per count. |
| VP2, VS1, MA3 | Scrollback search reads one row at a time, and each row decodes its whole 1,024-row page, on every typed character | Holds in shape: `Search.findFrom` calls `Vt.selectionText` per row and `viewPages` (`Vt.geng:1325`) calls `pageRowsOf` on the whole page. The seconds quoted are estimates. |
| VI1 | TIFF: up to 100,000 strips are sliced and flattened before any size check, and the decoder takes no limit | Holds in shape: `Tiff.geng:132-136` flattens the strips before the width and height test below it. The size reached was not worked out again. |
| VI2 | Sixel: the canvas is allocated from the raster attributes before the image limit is asked | Holds in shape: `Sixel.geng:118` builds `Array.repeat (width * height)` of four-element arrays, then flattens. What `limit` is at the call was not traced again. |
| VI3 | JPEG: the number of scans and of components in a scan is not bounded | Not read again beyond finding no bound by name in `Jpeg.geng`. |
| X1 | Pasting puritty's own selection when it is over the piece size stalls, and the window stops getting keys, clicks and exposes | Holds. `puritty_x11.c:1595` replaces the requestor's event mask, the requestor is puritty's own window (`paste_ask`, 1715, always asks the server), and `transfer_step` (1632) returns early for it. |
| W1, MA2 | Ctrl+click opens any `file:///` link from a program's output; on Windows through `ShellExecuteW "open"` | Holds on reading. `Links.geng:20` admits every `file:///` URI and `puritty_win32.c:2939` passes it on unchanged. What Windows then runs was not tried. |
| MA1 | A window that draws nothing for 6.2 days stops drawing for up to 6.2 more | Holds on reading. `m.last` is written only in `draw` (`Main.geng:8668`), `frameAt` (1693) is computed from it, and `Clock.reached` is wrong past half of the 2^30 ms period, as `Clock.geng` itself says. |
| MB1 | Closing a tab sends its shell one `SIGTERM` and never closes the pty | Holds on reading. `closeShown` (`Main.geng:9103`) calls only `remote.kill`; `Backend.pty` has no close; `Process.kill` is `SIGTERM`. Contradicts `docs/tabs.md` Dnene51. Check with `ps` after closing a tab on an idle bash. |
| TA1 | A prompt line tmux parses to no command gets no reply block, and the reply queue is one behind from then on | Not read again. `plausible`: needs one run against tmux 3.0 or later. |
| TA2 | `detach-client -t <another client>` is taken for this client leaving | The predicate holds (`TmuxMode.geng:906`: any `detach-client` without an `a` flag). That nothing is sent afterwards was not read again. |
| TA3 | Control mode is entered on in-band bytes, and bindings read from that stream are later sent as command lines | Not read again. `plausible`. Entry on `ESC P 1000 p` is tmux's protocol (`docs/tmux.md`), so this is partly a decision: see below. |
| TB1 | A click or the wheel over a pane in copy mode sends report bytes and arrow keys through copy mode's key table | Not read again. `plausible`. |
| PS1 | Enter in the font box with nothing picked writes the last font in the list | Holds. `SettingsWindow.geng:1527` is `Array.get t.pick`, and core's `Array.get` counts a negative index from the end. |
| PS2 | A click away from quick connect connects to what is half typed | Not read again. |

## What runs through more than one slice

These are the patterns behind many of the single findings. Fixing the pattern
once is cheaper than fixing each finding, and each is a place where more of
the same is likely to be found.

**1. A limit asked after the memory is taken, or not at all.** The README says
"every buffer a remote program can fill has a limit". The review found these
that do not: the three image decoders above (VI1, VI2, VI3) and the decoders'
peak of about ten times the pixel bytes (VI4); an OSC 99 notification's parts
(VS2); the kept OSC string rebuilt per `:` (VP4); a control-mode line that
has not ended (TP3); the ssh channel window handed back on receipt and the
queue behind it (SC2, MA10); OSC 52 writes of a hidden tab (MB6); a hostile
`SSH_FXP_NAME` count recursing (ST5); the hyperlink table that fills and
stops (VP5); style and cluster ids never given back (VP6); panes never
forgotten (TA8). A single rule would cover them: the size is known and held
to the limit before the first allocation, and a test sends the hostile input.
There are no malformed-input tests for the JPEG, GIF, TIFF and Sixel decoders
(VI20).

**2. "The shown tab" where "the tab that asked" is meant.** `Main`'s model
keeps the shown tab's fields at the top of one 130-field record and copies
them to and from `Tab` by hand (MA12). What follows from it: a paste's later
pieces, a pasted picture and an OSC 52 read go to whichever tab is shown when
they arrive (MA9, MB3); a settings reload reaches only the shown tab's
terminal, `read_files` included (MA5, MA6); output in a hidden tab forces an
unpaced frame of the shown one (MA7, MB5); an error on any tab's backend ends
the window (MA11).

**3. One precedence, written several times.** The dialog drawn and the dialog
that takes the keys are chosen by two orders that disagree (MA4, MB2, the same
finding twice), and the dialogs are listed in six places (MB19). Input-method
text skips all of them (MB4). The one-line text field exists five times and
the copies have drifted (PS13).

**4. tmux's replies are matched by position.** One command sent without an
entry in the queue, or one command tmux does not answer, and every later reply
goes to the wrong question: TA1, TA5 and TB3 (the same resize, seen from each
half), TA6. The findings are separate ways in; the weakness is one. A check
that fails loudly when a reply's shape cannot be its question's would turn a
silent, permanent desync into a visible one.

**5. Text put into a command line.** `~` at the start of a tmux paste piece
(TP1); the shell-fallback transfer's quoting under fish and csh (ST2); a
popup title expanded twice (TB4); customize-mode's filter without `%` doubled
(TB5); text from tmux drawn with its control characters (TB6); a reply's
lines split on newlines a pane's program can supply (TP2).

**6. Trust decisions.** `file:` links (W1, MA2); a UNC path through
`read_files` on Windows (VI11); a remembered password sent after a changed
host key was trusted once (ST3); no notice when strict key exchange is absent
(SC3); an unencrypted private key's text held for the session (SC4); the
agent's named pipe opened as an ordinary file (W5).

**7. A negative index counts from the end.** PS1 is `Array.get -1` giving the
last element where "nothing" was meant. Any `Array.get`, `Array.slice` or
`String` index fed from a field that uses -1 for "none" has the same trap;
the fields in `app/src` that are set to -1 and later used as an index are the
place to start.

**8. Work on the draw path that waits.** A fontconfig match per uncovered
cluster once the fallback cache is full (X3), and on Windows every installed
face opened per uncovered code point under the paint lock (W2); four round
trips in `isMaximized` on every resize (X9); the keymap fetched again per XKB
event (X7); the round trips listed in X18 against the README's "never waits on
a reply from the server while drawing".

**9. Two modules too large to review.** `app/src/Main.geng` is 10,922 lines
and `app/src/TmuxMode.geng` 17,377. MA12, MB19, TA21 and TB19 each name the
groups of functions that would make modules and the state each needs.

## Where a document says what the code does not

A fix here is either to the code or to the sentence.

| document | says | finding |
|---|---|---|
| `README.md` | every buffer a remote program can fill has a limit | theme 1 |
| `README.md` | drawing never waits on a reply from the server | X18 |
| `docs/tabs.md` Dnene51 | closing a tab ends its program at once | MB1 |
| `docs/ssh-client.md:555` | a fast server is slowed by the window | SC2 |
| `docs/ssh-client.md:609` | a notice when strict key exchange is absent | SC3 |
| `docs/images.md` IM4, IM5 | an image is bounded before it allocates | VI2 |
| `docs/images-kitty.md` KG3 | no reply for an image sent without an id | VI6 |
| `docs/sftp.md` FT18 | the login shell does not matter to the fallback | ST2 |
| `docs/user/settings.md` | the example file | PS26 |

Stale comments are gathered in X29, W18 and TB20.

## For the owner to decide, not to fix

Decided by Gilbert on 2026-11-22, each the recommended choice; to build.

- **TA3**: control mode is entered on bytes in the stream, as tmux's
  protocol has it. *Decided:* enter at once only when this tab started it
  (its own command, or a line just typed in it, was `tmux -CC`); otherwise
  ask "Enter tmux control mode?" first, the bytes shown as output until
  answered. TA15's Enter sent to a pane on the sequence goes too: a note,
  no keys sent. **Built** 2026-11-22: `docs/tmux.md` TM108.
- **SC6**: under `accept-new` or `no`, a key of a new type is accepted for a
  host known by another type. OpenSSH does the same, the review says.
  *Decided:* under `accept-new`, ask, with the question `ask` shows; under
  `no`, accept as now. **Built** 2026-11-22: `docs/ssh-client.md` SC30.
- **ST3**: whether a remembered password is offered after "trust once".
  *Decided:* sent by itself only when the host's key matched
  `known_hosts`; otherwise the password box says the key is not the known
  one, the saved password ready but sent only by the user's Enter. **Built** 2026-11-22: `docs/saved-secrets.md` PW11.
- **SC7**: `ssh_config` keywords that are read and not acted on are dropped
  without a word. *Decided:* each one not acted on is named once per
  connection; the authentication restrictions (`PasswordAuthentication`,
  `KbdInteractiveAuthentication`, `PreferredAuthentications`) and the
  algorithm lists (`HostKeyAlgorithms`, `KexAlgorithms`, `Ciphers`,
  `MACs`) are honoured; a connection is refused, naming `client =
  "openssh"` as the way, when `ProxyCommand`, `RevokedHostKeys` or
  `CertificateFile` applies; and `/etc/ssh/ssh_config` is read. **Built** 2026-11-22: `docs/ssh-client.md` SC31.

## What was not covered

Each slice file ends with its own "Looked at and found sound" and "Not
covered" sections. The larger gaps:

- No copy of tmux's source is on the machine the review ran on, so nothing
  about tmux's own behaviour was checked against it.
- The vendored PuTTY key-file parsers were not traced for crafted keys.
- `Os.Signal`, `Os.Net.listen` and `accept`, and the Windows console-input
  path in the `os` package.
- Draw-for-draw agreement of tmux's modes with each tmux version.
- The Python harnesses, the benches and the probes.

## Every finding

### High (18)

| id | kind | confidence | finding |
|---|---|---|---|
| [VP1](01-vt-parser-screen.md) | security | confirmed | **fixed** SD, IL and DL loop the raw count (up to 65,535) instead of the region's height |
| [VP2](01-vt-parser-screen.md) | speed | confirmed | **fixed** Searching or reading one scrollback row decodes its whole page (1,024 rows), and walks the pages from the oldest |
| [VS1](02-vt-scrollback-view-input.md) | speed | confirmed | **fixed** Scrollback search decodes a whole 1,024-row page for every row it looks at |
| [VI1](03-vt-images.md) | security | confirmed | **fixed** TIFF: overlapping strips make a decompression bomb, and the decoder ignores the image limit |
| [VI2](03-vt-images.md) | security | confirmed | **fixed** Sixel: a 30-byte string allocates gigabytes; the size is never held to the image limit |
| [VI3](03-vt-images.md) | security | confirmed | **fixed** JPEG: nothing bounds the number of scans or a scan's components, so a small file hangs the terminal |
| [X1](07-x11-text.md) | bug | confirmed | **fixed** Pasting puritty's own selection when it is over 256 KB stalls the paste and strips the window's event mask |
| [W1](08-win32.md) | security | confirmed | **fixed** A `file:` link from a program's output is run by the shell: local executables and UNC paths |
| [MA1](09-app-main-a.md) | bug | confirmed | **fixed** A window that draws no frame for 6.2 days stops drawing at all, for up to 6.2 more |
| [MA2](09-app-main-a.md) | security | confirmed | **fixed** Ctrl+click opens any `file://` link, including executables and UNC paths, with the target never shown |
| [MA3](09-app-main-a.md) | speed | confirmed | **fixed** Scrollback search unpacks a whole 1,024-row page for every row it looks at |
| [MB1](10-app-main-b.md) | bug | confirmed | **fixed** Closing a tab never closes its pty: the shell gets SIGTERM only, and the descriptor is kept for the window's life |
| [TA1](11-tmuxmode-a.md) | bug | plausible | **fixed** A typed line that tmux parses to no command leaves the reply queue one behind for good |
| [TA2](11-tmuxmode-a.md) | bug | confirmed | **fixed** `endsClient` takes `detach-client -t another-client` for this client leaving: nothing is sent again |
| [TA3](11-tmuxmode-a.md) | security | plausible | **fixed** Control mode is entered from in-band bytes with no check, and text read from that stream is later written back as command lines |
| [TB1](12-tmuxmode-b.md) | bug | plausible | **fixed** A click or the wheel over a pane in copy mode sends mouse bytes and arrow keys into copy mode's key table |
| [PS1](13-app-picker-settings.md) | bug | confirmed | **fixed** Enter on the font box with nothing picked sets the last font in the list |
| [PS2](13-app-picker-settings.md) | bug | confirmed | **fixed** A click away from quick connect connects to what is typed (and from "New host" makes the host) |

### Medium (105)

| id | kind | confidence | finding |
|---|---|---|---|
| [VP3](01-vt-parser-screen.md) | bug | confirmed | **fixed** ED 3 lowers `rowsPushed`, so absolute rows (image anchors, selection points) no longer name their rows |
| [VP4](01-vt-parser-screen.md) | security | confirmed | **fixed** With Sixel/iTerm2 images on, every `:` or `=` in an OSC rebuilds the kept string; a DCS has the same shape per `q` and per C1 byte |
| [VP5](01-vt-parser-screen.md) | design | confirmed | **fixed** The hyperlink table never forgets a link: after 4,096 distinct links OSC 8 stops working for the session |
| [VP6](01-vt-parser-screen.md) | design | confirmed | **fixed** Style and cluster ids are never given back; the tmux canvas is one long-lived terminal that takes the union of every pane's |
| [VP7](01-vt-parser-screen.md) | bug | confirmed | **fixed** RIS in the same read drops clipboard requests, notifications and diagnostic lines not yet taken |
| [VP8](01-vt-parser-screen.md) | speed | confirmed | **fixed** `composeStyled` interns a style for every pane cell on every frame |
| [VS2](02-vt-scrollback-view-input.md) | security | confirmed | **fixed** OSC 99 parts with `d=0` grow a pending notification without bound, each part copied onto the last |
| [VS3](02-vt-scrollback-view-input.md) | bug | confirmed | **fixed** A selection that starts on the right half of a wide character leaves that character out of the copy |
| [VI4](03-vt-images.md) | security | confirmed | **fixed** Decoders peak at roughly ten times the pixel bytes, so the 320 MB limit admits multi-GB spikes from small inputs |
| [VI5](03-vt-images.md) | bug | confirmed | **fixed** A Sixel or iTerm2 image drawn over an older one never frees it: animations pile up to the limit |
| [VI6](03-vt-images.md) | bug | confirmed | **fixed** An image refused for memory is answered even when the program gave no id |
| [VI7](03-vt-images.md) | speed | confirmed | **fixed** Eviction sorts every image once per victim, with a scan of all placements inside the comparison |
| [VI8](03-vt-images.md) | efficiency | confirmed | **fixed** Placements whose rows have left the scrollback are never removed |
| [VI9](03-vt-images.md) | speed | confirmed | **fixed** `imageByKey` is linear, builds a string per image, and re-masks the pixels on every call; View calls it per sent image per frame |
| [VI10](03-vt-images.md) | speed | confirmed | **fixed** Sixel painting allocates about eight arrays per data byte, and a repeat is an unbudgeted fill |
| [VI11](03-vt-images.md) | security | plausible | **fixed** With `read_files` on under Windows, a remote program can make puritty open a UNC path |
| [VI20](03-vt-images.md) | test-gap | confirmed | **fixed** No malformed-input tests for the JPEG, GIF, TIFF and Sixel decoders |
| [SC1](04-ssh-core.md) | bug | confirmed | **fixed** A side channel closed while it is still opening is not closed, and then runs |
| [SC2](04-ssh-core.md) | security | plausible | **fixed** The channel window is given back on receipt, so the server is never slowed and output queues without bound |
| [SC3](04-ssh-core.md) | security | confirmed | **fixed** No warning or fallback when the server has no strict KEX and ChaCha20-Poly1305 is chosen (Terrapin), though the design promises one |
| [SC4](04-ssh-core.md) | security | confirmed | **fixed** An unencrypted key file's text, the private key itself, is held in Geng memory for the whole session |
| [SC5](04-ssh-core.md) | inaccuracy | plausible | **fixed** A host looked up through `HostKeyAlias` on a port other than 22 is looked up as `[alias]:port`; OpenSSH uses the bare alias |
| [SC6](04-ssh-core.md) | security | confirmed | **fixed** With `accept-new` or `no`, a key of a type the host is not known by is taken silently even when the host is known by another type |
| [SC7](04-ssh-core.md) | inaccuracy | confirmed | **fixed** `ssh_config` keywords the client does not act on are dropped without a word, including ones that restrict what it may do |
| [SC8](04-ssh-core.md) | bug | confirmed | **fixed** keyboard-interactive is tried once per connection, so one mistyped answer ends the login |
| [ST1](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A batch whose SFTP stream breaks is reported as a success: `Finished` overwrites `Broken` |
| [ST2](05-ssh-session-transfer.md) | security | plausible | **fixed** The shell fallback's quoting is only right for POSIX-style login shells: fish misreads `\'`, csh/tcsh refuse the newline |
| [ST3](05-ssh-session-transfer.md) | security | confirmed | **fixed** A remembered password is given without asking to a host whose key is not the known one |
| [ST4](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A dropped folder is walked through its symlinks: a link to `/` or to a parent uploads far more than was dropped, or never finishes |
| [ST5](05-ssh-session-transfer.md) | security | plausible | **fixed** A hostile SFTP server can crash the client with one `SSH_FXP_NAME`: `entries` and `skipExtended` recurse once per element, not in a loop |
| [ST6](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A key that is both a file and in the agent is used from the file, so the passphrase is asked although the agent holds the key |
| [ST7](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A new host key is appended to `known_hosts` without checking the file ends in a newline |
| [TP1](06-tmux-package.md) | bug | plausible | **fixed** A paste whose text (or any 1024-byte piece of it) begins with `~` is tilde-expanded by tmux 3.x |
| [TP2](06-tmux-package.md) | security | plausible | `ESC \` at the start of a line ends control mode even inside a reply, and a reply's lines are split on newlines the pane's program can put there |
| [TP3](06-tmux-package.md) | security | confirmed | **fixed** A line that has not ended yet is copied and rescanned on every read, and nothing bounds it, a reply's lines or the lines in doubt |
| [TP4](06-tmux-package.md) | speed | confirmed | **fixed** `%output` is unescaped with two allocations per escaped byte, and each short line is decoded to a String twice before that |
| [TP5](06-tmux-package.md) | bug | confirmed | **fixed** `Bindings.held` matches a word anywhere in the command: arguments named `menu` or `popup` hold a binding back, and a prompt inside a quoted argument is not held |
| [X2](07-x11-text.md) | bug | confirmed | **fixed** An INCR transfer whose requestor never finishes holds its slot and its copy of the text for ever; eight of them refuse every large copy |
| [X3](07-x11-text.md) | speed | confirmed | **fixed** The fallback cache is a fixed 4,096-slot table with no full case: past that, every uncovered cluster costs a fontconfig match on every draw |
| [X4](07-x11-text.md) | bug | plausible | **fixed** Dead keys and the Compose key produce nothing when no XIM server runs |
| [X5](07-x11-text.md) | bug | plausible | **fixed** A primary font FreeType cannot size leaves the cell 0 by 0, and the first resize divides by zero |
| [X6](07-x11-text.md) | bug | plausible | **fixed** A stale event time makes a copy fail silently: `SetSelectionOwner` is never verified |
| [X7](07-x11-text.md) | speed | confirmed | **fixed** A keymap change re-fetches the whole keymap synchronously once per XKB event, inside `drain` (so inside `draw`) |
| [X8](07-x11-text.md) | efficiency | confirmed | `pt_zoom` clears 10 MB of tables per loaded face on every zoom step |
| [X9](07-x11-text.md) | speed | confirmed | **fixed** `isMaximized` makes four synchronous round trips, and `Main` calls it on every `Resized` |
| [X10](07-x11-text.md) | bug | plausible | **fixed** Focus events from a window manager's key grabs are reported as focus changes |
| [W2](08-win32.md) | speed | confirmed | **fixed** Every code point no listed family covers opens every installed font face, inside the draw, under the paint lock |
| [W3](08-win32.md) | bug | plausible | **fixed** A capture taken from the window forgets the held buttons without telling the program; the native menu does this every time |
| [W4](08-win32.md) | bug | confirmed | **fixed** The pop-up menu opens up and left of the pointer by the padding, so the pointer starts over its first item |
| [W5](08-win32.md) | security | confirmed | The ssh agents' named pipes are opened as ordinary files: the server may impersonate the user, and its owner is not checked |
| [W6](08-win32.md) | bug | plausible | A font is found by its registry name, which on a localized Windows is not the family name FreeType reads |
| [MA4](09-app-main-a.md) | bug | confirmed | **fixed** The dialog shown and the dialog the keys go to are decided by two different orders |
| [MA5](09-app-main-a.md) | bug | confirmed | **fixed** A settings reload reaches only the shown tab's terminal |
| [MA6](09-app-main-a.md) | security | confirmed | **fixed** `[images] read_files` turned off (or on) does not reach a running terminal |
| [MA7](09-app-main-a.md) | speed | confirmed | **fixed** Output in a tab not shown forces a frame for every chunk read, past the 16 ms pacing |
| [MA8](09-app-main-a.md) | bug | plausible | **fixed** Work that only the timer branch does waits for as long as the shown tab keeps printing |
| [MA9](09-app-main-a.md) | bug | plausible | **fixed** A paste in flight goes to whichever tab is shown when its pieces arrive |
| [MA10](09-app-main-a.md) | security | plausible | **fixed** The built-in ssh session's output reaches the window through a queue with no bound |
| [MA11](09-app-main-a.md) | design | plausible | **checked, not reached** A failing call on any tab's backend ends the whole window, and skips `finish` |
| [MA12](09-app-main-a.md) | design | confirmed | Main.geng is 10,922 lines over one 130-field record, and the shown tab's fields are kept in step with `Tab` by hand |
| [MB2](10-app-main-b.md) | bug | confirmed | **fixed** The box drawn and the dialog that takes the keys are chosen in two different orders |
| [MB3](10-app-main-b.md) | bug | confirmed | **fixed** A paste's later pieces, a pasted picture and an OSC 52 read go to whichever tab is shown when they arrive |
| [MB4](10-app-main-b.md) | bug | confirmed | **fixed** Text the input method commits skips the search bar, the folder picker and the questions, and is sent to the program |
| [MB5](10-app-main-b.md) | speed | confirmed | **fixed** Every read of a tab not shown forces an unpaced frame of the shown tab |
| [MB6](10-app-main-b.md) | security | confirmed | **fixed** OSC 52 writes of a tab not shown queue without bound, and are applied when it is next shown |
| [MB19](10-app-main-b.md) | design | confirmed | The dialogs are listed in six places, and four groups of this half are modules in waiting |
| [TA4](11-tmuxmode-a.md) | bug | confirmed | **fixed** After the active pane or window changes, named keys go to the old pane and text to the new one |
| [TA5](11-tmuxmode-a.md) | bug | confirmed | **fixed** A change in the status line's row count sends a resize that nothing waits for |
| [TA6](11-tmuxmode-a.md) | bug | confirmed | **fixed** Before tmux 3.4 a binding of several commands is sent on one line and waited for once; `source-file` in it has no fence |
| [TA7](11-tmuxmode-a.md) | bug | confirmed | **fixed** A pane that closes while it holds the pointer leaves `grab` set: clicks, selection and tabs stop working |
| [TA8](11-tmuxmode-a.md) | bug | confirmed | **fixed** Panes are never taken out of `ids`/`panes`/`info`: closed panes and a left session's panes keep their terminals |
| [TA9](11-tmuxmode-a.md) | efficiency | confirmed | **fixed** Every attach asks the window, tabs, panes and modes twice, so every pane is captured twice |
| [TA10](11-tmuxmode-a.md) | efficiency | confirmed | **fixed** A pane's whole history is captured on attach and on every `%pause`, into a terminal that keeps about 1000 rows |
| [TA11](11-tmuxmode-a.md) | bug | confirmed | **fixed** `applyLayout` sizes terminals without the scrollbar's columns; only `refit` uses `fittedIn` |
| [TA12](11-tmuxmode-a.md) | bug | confirmed | **fixed** Key bindings and prefixes are read once, on attach |
| [TA13](11-tmuxmode-a.md) | bug | plausible | **fixed** Layout changes of windows not shown are dropped, so their panes' terminals keep the old size |
| [TA21](11-tmuxmode-a.md) | design | confirmed | A 17,377-line module: where it would split |
| [TA22](11-tmuxmode-a.md) | test-gap | confirmed | What the explorer does not reach |
| [TB2](12-tmuxmode-b.md) | bug | confirmed | **fixed** The wheel and Shift+PgUp scroll puritty's view of a pane in copy mode, which tmux's copy mode does not follow |
| [TB3](12-tmuxmode-b.md) | bug | confirmed | **fixed** A size sent after a status-line change is not put in the reply queue, so the replies after it go to the wrong questions |
| [TB4](12-tmuxmode-b.md) | security | plausible | **fixed** A popup's title is expanded twice, the second time as `pane-border-format` |
| [TB5](12-tmuxmode-b.md) | bug | plausible | **fixed** customize-mode's filter is sent through `display-message` without `%` doubled, and is longer than strftime's buffer |
| [TB6](12-tmuxmode-b.md) | security | plausible | **fixed** Text from tmux is written into the canvas terminal with its control characters |
| [TB7](12-tmuxmode-b.md) | bug | confirmed | **fixed** An unknown tmux version (0) is taken as the newest by some gates and as the oldest by others |
| [TB10](12-tmuxmode-b.md) | speed | confirmed | **in part** Work done again on every frame while a mode is open or a search is marked |
| [TB17](12-tmuxmode-b.md) | design | confirmed | The three modes are three `Maybe`s, and their kinds are bare `Int`s |
| [TB19](12-tmuxmode-b.md) | design | confirmed | What would make modules of this half, and what each needs |
| [PS3](13-app-picker-settings.md) | bug | confirmed | **fixed** What is typed is tied to a row number, so it lands in another setting when the list changes under it |
| [PS4](13-app-picker-settings.md) | bug | confirmed | **fixed** With a color scheme set, a color equal to puritty's default cannot be chosen, and the reset mark does nothing |
| [PS5](13-app-picker-settings.md) | bug | confirmed | **fixed** Rows scrolled partly under the header still take its clicks |
| [PS6](13-app-picker-settings.md) | bug | plausible | **fixed** Two listings of one folder in flight corrupt the listing (duplicates, or a part shown as the whole) |
| [PS7](13-app-picker-settings.md) | bug | confirmed | **fixed** The picker sorts and filters names as lossy UTF-8, not in the host's character set |
| [PS8](13-app-picker-settings.md) | speed | confirmed | **fixed** `middle` cuts a long label one character at a time, measuring the whole string each time |
| [PS9](13-app-picker-settings.md) | speed | confirmed | **fixed** Each part of a listing re-sorts everything received so far |
| [PS10](13-app-picker-settings.md) | bug | confirmed | **fixed** Undo of a host removed or renamed rewrites its table: bookmarks, comments and unknown keys are lost, and hosts added since are deleted |
| [PS11](13-app-picker-settings.md) | bug | confirmed | **fixed** After the keyboard moves the highlight down, the wheel does nothing |
| [PS12](13-app-picker-settings.md) | bug | plausible | **fixed** Writing `config.toml`: one fixed temporary name, no lock, a symlink replaced, the mode not kept |
| [PS13](13-app-picker-settings.md) | design | confirmed | The one-line text field exists five times and they have drifted: an invisible selection, a cut that loses text, no paste |
| [OS1](14-dep-os.md) | bug | plausible | `Os.Net.connect` looks names up with `AI_ADDRCONFIG`, so loopback and literal addresses fail on a machine with no routable address of that family |
| [OS2](14-dep-os.md) | bug | plausible | Windows: a child that is not on a pseudo console is started without `CREATE_NO_WINDOW`, so a GUI program's helper opens a console window |
| [OS3](14-dep-os.md) | bug | confirmed | `Process.run` cannot end a program that ignores `SIGTERM`: the time limit and the output limit both hang |
| [OS5](14-dep-os.md) | bug | confirmed | `readFile` blocks the scheduler on a FIFO or device and reads without bound before it checks the size |
| [LB1](15-dep-libs.md) | bug | confirmed | `Toml.Edit.removeTable` deletes the comment block that belongs to the *next* table, and every floating comment in the removed section |
| [LB2](15-dep-libs.md) | bug | confirmed | `removeTable` does not remove a table written with dotted keys, though `renameTable` renames one |
| [LB3](15-dep-libs.md) | design | confirmed | `Toml.Table.Error` carries no position, and its path is a dot-joined string |

### Low (197)

| id | kind | confidence | finding |
|---|---|---|---|
| [VP9](01-vt-parser-screen.md) | bug | confirmed | **fixed** A C1 byte inside an APC, SOS or PM string ends it, so UTF-8 text in such a string is cut and its tail printed |
| [VP10](01-vt-parser-screen.md) | efficiency | confirmed | **fixed** XTRESTORE of a mode never saved builds a whole new terminal to read one default |
| [VP11](01-vt-parser-screen.md) | bug | plausible | **fixed** `feedImaged` decides "in place" with `t.bottom == 0` where SU uses `t.bottom == t.rows - 1` |
| [VP12](01-vt-parser-screen.md) | bug | plausible | **checked, as Ghostty** BS at the left margin above the scroll region, with reverse wraparound, moves the cursor down to the region's top |
| [VP13](01-vt-parser-screen.md) | inaccuracy | confirmed | **fixed** DECRQSS's SGR report leaves out the underline color |
| [VP14](01-vt-parser-screen.md) | efficiency | confirmed | **checked, left** A truecolor SGR copies the parameter array for each color, against the comment beside it |
| [VP15](01-vt-parser-screen.md) | inaccuracy | confirmed | **fixed** Unknown private modes are stored for a DECRQM that never reads them |
| [VP16](01-vt-parser-screen.md) | speed | plausible | **checked, left** Copying a long selection concatenates a string per cell and per row |
| [VP17](01-vt-parser-screen.md) | speed | confirmed | **fixed** Jump-to-prompt with no prompt in the scrollback walks every row, and each row walks the pages from the oldest |
| [VS4](02-vt-scrollback-view-input.md) | bug | confirmed | **fixed** The frame's diff trusts style and cluster ids across RIS, which hands the same ids out again |
| [VS5](02-vt-scrollback-view-input.md) | bug | confirmed | **fixed** An unbracketed paste of CRLF text sends CR CR, and a CRLF split across two pieces does too |
| [VS6](02-vt-scrollback-view-input.md) | security | plausible | **fixed** The diagnostic log gets a DECRQSS or XTGETTCAP body as the program wrote it, control bytes included |
| [VS7](02-vt-scrollback-view-input.md) | inaccuracy | confirmed | **fixed** `Base64.decode` is documented as strict but takes non-canonical final characters |
| [VS8](02-vt-scrollback-view-input.md) | efficiency | confirmed | **fixed** Every frame copies the `drawnIn` stamps and allocates a `worded` array, with no image and no ink on the screen |
| [VS9](02-vt-scrollback-view-input.md) | efficiency | confirmed | **fixed** `Recut.gather` decodes a row that is not single-column twice |
| [VS10](02-vt-scrollback-view-input.md) | dead-code | confirmed | **fixed** `Prompt.geng`, `Pages.geng`, `Resize.geng` and `Dump.geng` import what they do not use, some of it twice |
| [VI12](03-vt-images.md) | bug | confirmed | **fixed** JPEG: green is one too high on every YCbCr pixel |
| [VI13](03-vt-images.md) | speed | confirmed | **fixed** TIFF to RGBA allocates an array per pixel and a range of every pixel index |
| [VI14](03-vt-images.md) | bug | confirmed | **fixed** iTerm2: the limit is tested against the drawn size even when no pixels of that size are made |
| [VI15](03-vt-images.md) | design | confirmed | **fixed** iTerm2 decode failures are dropped to `Nothing` |
| [VI16](03-vt-images.md) | inaccuracy | confirmed | **fixed** Inflate accepts incomplete code sets that puff.c and zlib refuse |
| [VI17](03-vt-images.md) | inaccuracy | confirmed | **fixed** PNG: a palette index past PLTE, a repeated IHDR, and PLTE/tRNS of bad length are accepted |
| [VI18](03-vt-images.md) | speed | confirmed | **fixed** PNG: CRC-32 is worked a bit at a time, for every chunk, including those whose CRC is not checked |
| [VI19](03-vt-images.md) | bug | plausible | **fixed** JPEG `markers` recurses through `Result.andThen` for SOF, so it is not a loop there |
| [SC9](04-ssh-core.md) | inaccuracy | confirmed | **fixed** The hourly rekey in the design is not built: `Transport.rekey` has no caller |
| [SC10](04-ssh-core.md) | bug | confirmed | **fixed** `WINDOW_ADJUST` can wrap the server's window negative, after which the channel never sends again |
| [SC11](04-ssh-core.md) | security | plausible | **fixed** A server that names a tiny maximum packet makes the client cut a write into one packet a byte, recursively |
| [SC12](04-ssh-core.md) | security | confirmed | **fixed** `Agent.unframe` cannot tell "not all here yet" from "will never be valid", and the reader has no size limit |
| [SC13](04-ssh-core.md) | security | confirmed | **fixed** The transport hands packets to the layers above before any keys exist when the server is not strict |
| [SC14](04-ssh-core.md) | bug | confirmed | **fixed** `server-sig-algs` is thrown away when it arrives before the host key question is answered |
| [SC15](04-ssh-core.md) | bug | confirmed | **fixed** `exit-status` of 2^31 or more is dropped, and a server's channel number of 2^31 or more ends the channel |
| [SC16](04-ssh-core.md) | inaccuracy | confirmed | **in part** A channel the server opens is never answered |
| [SC17](04-ssh-core.md) | bug | confirmed | **fixed** The keepalive count reported is one behind, so a dead server is noticed one interval late |
| [SC18](04-ssh-core.md) | bug | confirmed | **fixed** A `FAILURE` while a signature is being made offers the same key again, as often as the server likes |
| [SC19](04-ssh-core.md) | bug | confirmed | **fixed** `KnownHosts.replaced` numbers lines differently from `parse`, so it can take out the wrong line |
| [SC20](04-ssh-core.md) | inaccuracy | confirmed | **fixed** A relative `Include` in the system's file is read from the user's `~/.ssh` |
| [SC21](04-ssh-core.md) | bug | confirmed | **fixed** `HostName %%h` expands to the host; `%%` is replaced before `%h` |
| [SC22](04-ssh-core.md) | bug | plausible | **fixed** RSA certificates and other key types an agent holds are offered under a name the server cannot take |
| [SC23](04-ssh-core.md) | design | plausible | **fixed** A key handle that is dropped without `forget` leaks the private key uncleared |
| [SC24](04-ssh-core.md) | dead-code | confirmed | **fixed** `aesCtr` and `bcryptPbkdf` are exported and used by nothing but the tests |
| [SC25](04-ssh-core.md) | design | confirmed | **fixed** `Transport.start` takes a seed of any length, an empty one included |
| [SC26](04-ssh-core.md) | bug | confirmed | **fixed** `IdentitiesOnly true` is read as `no`, and a `known_hosts` that cannot be read is read as empty |
| [SC27](04-ssh-core.md) | design | confirmed | **fixed** The glob matcher is written twice and backtracks exponentially |
| [ST8](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A side channel closed while it is still opening is never closed: quick Esc in the folder chooser leaks a server session each time |
| [ST9](05-ssh-session-transfer.md) | bug | confirmed | **fixed** `Sending.owns` claims every later side channel while a shell transfer runs |
| [ST10](05-ssh-session-transfer.md) | inaccuracy | confirmed | **in part** `ConnectTimeout` is read and ignored, and nothing is read from the window while connecting |
| [ST11](05-ssh-session-transfer.md) | security | plausible | **fixed** Nothing holds the server back when the window reads slower than the network: output queues without bound |
| [ST12](05-ssh-session-transfer.md) | bug | plausible | **fixed** The link is not closed when the loop ends by an error, and an agent's socket is never closed |
| [ST13](05-ssh-session-transfer.md) | bug | confirmed | **fixed** The keepalive timer starts again on every turn of the loop, so a dead link is not noticed while anything else happens |
| [ST14](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A second `SSH_FXP_VERSION` restarts the transfer's checks in the middle of a batch |
| [ST15](05-ssh-session-transfer.md) | efficiency | confirmed | **fixed** `Sftp.received` copies the whole unfinished packet for every piece that arrives |
| [ST16](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A shell-fallback job that succeeded is reported failed when the host's startup files print anything |
| [ST17](05-ssh-session-transfer.md) | dead-code | confirmed | **fixed** `ShellTransfer.unsent` never sees the running command, so a failed upload leaves the total below what was moved |
| [ST18](05-ssh-session-transfer.md) | bug | confirmed | **fixed** `Transfer`'s broken-stream path miscounts, and leaves the part |
| [ST19](05-ssh-session-transfer.md) | inaccuracy | confirmed | **fixed** Every refusal of the SFTP channel is taken as "SFTP is turned off", and with the setting on it switches to shell commands |
| [ST20](05-ssh-session-transfer.md) | speed | confirmed | **fixed** An upload opens, seeks and closes the local file for every 32 KiB, and reads 64 KiB to use 32 |
| [ST21](05-ssh-session-transfer.md) | bug | plausible | **in part** A batch that has shown no progress cannot be cancelled, and nothing times it out |
| [ST22](05-ssh-session-transfer.md) | bug | confirmed | **fixed** Options from `~/.ssh/config`: `SetEnv` with `=` in the value is dropped, `IdentitiesOnly true` is not yes, a bare IPv6 jump or quick-connect host is cut at its last colon |
| [ST23](05-ssh-session-transfer.md) | security | confirmed | **fixed** `ssh` is run with the host's name as a bare argument: a name starting with `-` is read as an option |
| [ST24](05-ssh-session-transfer.md) | bug | confirmed | **in part** After the picker's SFTP stream breaks, later requests wait for ever; and a listing cannot be abandoned |
| [ST25](05-ssh-session-transfer.md) | bug | confirmed | **fixed** A changed key's rewrite of `known_hosts` goes through lossy UTF-8 and a new file |
| [ST26](05-ssh-session-transfer.md) | design | confirmed | **fixed** An unreadable folder inside a drop is made on the host empty, with nothing said |
| [ST27](05-ssh-session-transfer.md) | test-gap | confirmed | **fixed** No test drives `Sending`, and the shell fallback's quoting is tested under one login shell |
| [TP6](06-tmux-package.md) | bug | confirmed | **fixed** `Bindings.bindingOf` rebuilds a binding's command from space-split words, so runs of spaces inside its quoted arguments collapse |
| [TP7](06-tmux-package.md) | bug | plausible | **fixed** `Command.pasteBytes` on tmux 2.x loses a `;` that ends a piece |
| [TP8](06-tmux-package.md) | bug | confirmed | **fixed** `unescape` drops the text before a backslash that is not an escape |
| [TP9](06-tmux-package.md) | bug | plausible | **checked, left** A notification that arrives inside a reply is kept as a reply line and never acted on |
| [TP10](06-tmux-package.md) | security | plausible | **fixed** A layout's nesting depth is not bounded, and a split's box is not clamped as a pane's is |
| [TP11](06-tmux-package.md) | inaccuracy | confirmed | Escapes inside double quotes are not decoded: `\n`, `\t`, `\e`, `\ooo`, `\u…` read as the letter or digits |
| [TP12](06-tmux-package.md) | design | confirmed | `Command.quote` cannot say a newline and does not refuse one; three builders take an unquoted name |
| [TP13](06-tmux-package.md) | efficiency | confirmed | Outside tmux, every ESC in the terminal's output costs a 7-byte slice and compare; under tmux every `%output` is scanned once more, and an entry split across two is missed |
| [TP14](06-tmux-package.md) | bug | confirmed | `Style.themed` rewrites `theme…` words in expanded text, not only inside `#[…]` |
| [TP15](06-tmux-package.md) | inaccuracy | confirmed | `Style.color` takes `colourN` for any N and does not know tmux's digit names |
| [TP16](06-tmux-package.md) | efficiency | confirmed | `quoteFrom` builds each paste piece by appending to a String per byte, and slices per byte |
| [TP17](06-tmux-package.md) | inaccuracy | plausible | An ESC that is not doubled inside a passthrough envelope is kept; tmux drops it |
| [TP18](06-tmux-package.md) | efficiency | confirmed | `Customize.table` is rebuilt from its text on every call, and `Borders.cells` parses the two border styles once per border cell |
| [TP19](06-tmux-package.md) | dead-code | confirmed | Dead or duplicated: `prefixesOf`'s `byTable` and `hasSendKeysK`; `indexOf`/`byteAt` twice |
| [TP20](06-tmux-package.md) | test-gap | confirmed | Test gaps |
| [X11](07-x11-text.md) | bug | confirmed | After the sound server goes away, every sound is lost and still reported as played |
| [X12](07-x11-text.md) | bug | confirmed | The paste's 10 s rule measures from the start, not from the last progress, and the abandoned paste shares the property and leaks its reply |
| [X13](07-x11-text.md) | bug | plausible | Font names go to `FcNameParse` unescaped, and its NULL is not checked |
| [X14](07-x11-text.md) | bug | plausible | The fallback cache is keyed by a cluster's first code point but answers for the whole cluster |
| [X15](07-x11-text.md) | bug | confirmed | `ui_glyph`'s key loses the face's top bit, and reads a 1-bit bitmap past its end |
| [X16](07-x11-text.md) | bug | confirmed | `WM_CLASS` is sent with a length one past the string |
| [X17](07-x11-text.md) | bug | confirmed | The X screen is always the first, whatever `DISPLAY` names |
| [X18](07-x11-text.md) | inaccuracy | confirmed | Draw-path round trips the README's sentence does not allow for |
| [X19](07-x11-text.md) | bug | plausible | `setenv("XCURSOR_PATH", ...)` changes the environment the terminal's programs may inherit |
| [X20](07-x11-text.md) | design | confirmed | The event buffer drops records silently when it is full |
| [X21](07-x11-text.md) | dead-code | confirmed | `kstate` and the XKB StateNotify subscription are dead |
| [X22](07-x11-text.md) | bug | plausible | At most 256 image placements a frame are drawn; the rest are dropped without a trace |
| [X23](07-x11-text.md) | bug | plausible | A picture's source offset is cut to 16 bits |
| [X24](07-x11-text.md) | bug | plausible | A glyph centered once keeps that centering for every later box width |
| [X25](07-x11-text.md) | bug | confirmed | `upload` does not check `FT_Load_Glyph`/`FT_Render_Glyph`, and allocation results are unchecked throughout |
| [X26](07-x11-text.md) | bug | confirmed | `draw_run` can hand `draw_glyphs` a run longer than the bytes that remain |
| [X27](07-x11-text.md) | design | confirmed | The build turns Nix's hardening off and names one machine's paths |
| [X28](07-x11-text.md) | security | plausible | A notification's body is given to `notify-send` as markup |
| [X29](07-x11-text.md) | inaccuracy | confirmed | Comments that no longer say what the code does |
| [W7](08-win32.md) | bug | plausible | `refit` changes the text layer and the window's size state outside the locks the window thread uses for them |
| [W8](08-win32.md) | bug | confirmed | The event queue is 64 KB and a record that does not fit is dropped with no trace, a resize, a close or a release included |
| [W9](08-win32.md) | bug | confirmed | After Explorer restarts, no notification is ever shown again |
| [W10](08-win32.md) | security | confirmed | A second `puritty settings` is satisfied by any puritty window whose title is the settings window's |
| [W11](08-win32.md) | bug | confirmed | Clipboard failures are silent, and a failed allocation in a large paste is dereferenced |
| [W12](08-win32.md) | bug | confirmed | An image paste takes the PNG's allocation size, not its length, and initializes COM once per paste |
| [W13](08-win32.md) | bug | confirmed | A registry font path is read past its end when the value is not NUL-terminated |
| [W14](08-win32.md) | bug | plausible | Text that arrives as a bare `WM_CHAR` or `WM_UNICHAR` is dropped |
| [W15](08-win32.md) | inaccuracy | confirmed | A `Resized` in the old order can precede `Rescaled`, against the comment |
| [W16](08-win32.md) | security | confirmed | The secret's copy in Windows' buffer is freed unwiped |
| [W17](08-win32.md) | design | confirmed | The signing script trusts the remote's word that the file is signed, and the exe carries no version resource |
| [W18](08-win32.md) | inaccuracy | confirmed | Comments and names that no longer say what the code does; a little dead code |
| [MA13](09-app-main-a.md) | bug | confirmed | **fixed** Three more times are compared after gaps the clock cannot hold |
| [MA14](09-app-main-a.md) | bug | confirmed | Bells in a hidden `tmux -CC` tab are not heard, and switching to or reopening a tab can ring |
| [MA15](09-app-main-a.md) | efficiency | confirmed | Every turn of the loop does several passes over all tabs, and every key parses every binding |
| [MA16](09-app-main-a.md) | efficiency | confirmed | The cursor's blink keeps waking the loop, and repainting every cell, while no cursor is on the screen |
| [MA17](09-app-main-a.md) | bug | plausible | A search match after an emoji sequence, or in a row where lowering a letter changes its length, is highlighted in the wrong columns |
| [MA18](09-app-main-a.md) | design | confirmed | The `Backend` passed beside the model can be a tab's that is no longer shown (the menu's paths) |
| [MA19](09-app-main-a.md) | bug | confirmed | A restored window shows the wrong tab when one of its tabs does not start |
| [MA20](09-app-main-a.md) | bug | confirmed | A font that cannot be opened on reload also drops a size change made with it |
| [MA21](09-app-main-a.md) | bug | confirmed | A synchronized update holds back puritty's own frames too |
| [MA22](09-app-main-a.md) | bug | plausible | The helper processes of an OpenSSH tab: a pipe left open, entries never removed, and two ways to stall |
| [MA23](09-app-main-a.md) | bug | plausible | A program that closes its terminal but keeps running freezes the window |
| [MA24](09-app-main-a.md) | bug | plausible | A binding that names a shifted character or a non-Latin layout's letter never matches |
| [MA25](09-app-main-a.md) | security | confirmed | What a host's paste command prints is kept without bound |
| [MB7](10-app-main-b.md) | bug | confirmed | **fixed** An unbracketed paste of CRLF text sends two CRs a line, and a CRLF cut between two pieces does too |
| [MB8](10-app-main-b.md) | bug | confirmed | Tabs past the window's right edge cannot be seen or clicked |
| [MB9](10-app-main-b.md) | efficiency | plausible | **fixed** `lineEnds` builds each pasted piece as an `Array UInt8`, a `pushLast` a byte |
| [MB10](10-app-main-b.md) | efficiency | confirmed | **fixed** `Diag.lines` decodes and rewrites each pasted piece although the log is off |
| [MB11](10-app-main-b.md) | bug | plausible | `Restore.fresh` ignores whether its lock was taken, and another window's `others` can remove a new window's lock file under it |
| [MB12](10-app-main-b.md) | bug | confirmed | The recent and folder files are read, changed and written with no lock, through one shared `.new` name |
| [MB13](10-app-main-b.md) | inaccuracy | confirmed | The log writes tab titles and a program's name, which the log's contract says are never written; `Diag.command` shows some typed words |
| [MB14](10-app-main-b.md) | bug | confirmed | A closed tab is lost, with its scrollback, when opening it again does not start |
| [MB15](10-app-main-b.md) | design | confirmed | `handleOne` carries a `remote` beside `m.remote`, and four paths go on with the stale one |
| [MB16](10-app-main-b.md) | inaccuracy | confirmed | `ImageFile.read`: a temporary file is not removed when its read fails, and a load is read whole inside the loop with three copies |
| [MB17](10-app-main-b.md) | dead-code | plausible | `ownTerm`'s question text is never drawn: the same questions are written twice and have drifted |
| [MB18](10-app-main-b.md) | bug | confirmed | A paste while the ssh question is up does not reach the question's field |
| [TA14](11-tmuxmode-a.md) | bug | plausible | Commands queued earlier in the read that ends control mode are still written |
| [TA15](11-tmuxmode-a.md) | security | confirmed | **fixed** A pane's output holding the entry sequence types a newline into that pane and hides its output |
| [TA16](11-tmuxmode-a.md) | efficiency | confirmed | Before 3.2 the status polls are sent every second whether or not the last were answered |
| [TA17](11-tmuxmode-a.md) | bug | plausible | `ForCopy` does not look at `ok`: before 3.2 a pane killed in copy mode is never forgotten |
| [TA18](11-tmuxmode-a.md) | efficiency | confirmed | Work done on every read that only some events need |
| [TA19](11-tmuxmode-a.md) | security | plausible | Text from tmux is drawn on the canvas terminal with its control characters |
| [TA20](11-tmuxmode-a.md) | bug | plausible | A config reload that changes the look does not tell tmux the new size |
| [TB8](12-tmuxmode-b.md) | bug | confirmed | choose-buffer's and choose-client's rows are asked with 3.2's format on every tmux |
| [TB9](12-tmuxmode-b.md) | efficiency | confirmed | Before tmux 3.2 the status line is asked with 21 commands a second, whether or not the last second's were answered |
| [TB11](12-tmuxmode-b.md) | bug | confirmed | Clipping and padding by characters where the neighbours go by cells |
| [TB12](12-tmuxmode-b.md) | bug | plausible | The loop's time in the state is stale on every path but a key and a tick |
| [TB13](12-tmuxmode-b.md) | bug | confirmed | A pane that closes leaves its mode behind, and a clock left behind keeps the timer and the repaint going |
| [TB14](12-tmuxmode-b.md) | bug | confirmed | A mode puritty draws outlives its pane and its window, unseen but still taking the keys |
| [TB15](12-tmuxmode-b.md) | bug | confirmed | The mouse's word and line are left on the pane as user options |
| [TB16](12-tmuxmode-b.md) | security | confirmed | FT11's first rule lets a nested host's OSC 7 name a folder on tmux's host |
| [TB18](12-tmuxmode-b.md) | design | confirmed | The mode tree's keys are written three times and have drifted from each other and from tmux |
| [TB20](12-tmuxmode-b.md) | inaccuracy | confirmed | Comments that no longer say what the function does |
| [TB21](12-tmuxmode-b.md) | test-gap | plausible | No test drives the pointer over a pane in a mode, or holds lines written to replies expected |
| [PS14](13-app-picker-settings.md) | bug | confirmed | A text record longer than 65,535 bytes breaks the frame's record stream |
| [PS15](13-app-picker-settings.md) | bug | confirmed | A command with a quote in a word does not survive the settings window |
| [PS16](13-app-picker-settings.md) | speed | confirmed | Every pointer event builds the picker's whole frame to find what is under it, and `rows` is rebuilt several times a frame |
| [PS17](13-app-picker-settings.md) | efficiency | confirmed | The settings window measures and draws more than it needs per event, and row positions are quadratic |
| [PS18](13-app-picker-settings.md) | bug | plausible | Path completion asks the host again on every keystroke under a link or `~`, and Tab completes from the first eight only |
| [PS19](13-app-picker-settings.md) | bug | confirmed | The places column does not scroll, and its hidden rows still take clicks |
| [PS20](13-app-picker-settings.md) | bug | confirmed | The settings window does not settle before reading, keeps a stale error, and never shows a later read's reports |
| [PS21](13-app-picker-settings.md) | bug | confirmed | Pasted and committed text is not filtered for control characters |
| [PS22](13-app-picker-settings.md) | design | plausible | A dialog cuts its lines instead of wrapping them, and a tall one puts its buttons off the window |
| [PS23](13-app-picker-settings.md) | bug | plausible | The terminal scrollbar's arithmetic overflows `Int` with a very long scrollback |
| [PS24](13-app-picker-settings.md) | design | confirmed | Strings outside the translation table: the whole picker, the search bar's placeholder, the settings' units |
| [PS25](13-app-picker-settings.md) | bug | confirmed | Renaming a host leaves what names it pointing at the old name |
| [PS26](13-app-picker-settings.md) | inaccuracy | confirmed | `docs/user/settings.md` shows a file that leaves out settings no other user page names |
| [PS27](13-app-picker-settings.md) | test-gap | confirmed | Test gaps that matter |
| [OS4](14-dep-os.md) | bug | confirmed | A child inherits every ignored signal: only `SIGPIPE` is set back to its default |
| [OS6](14-dep-os.md) | bug | confirmed | `File.copy` of a file onto itself empties it |
| [OS7](14-dep-os.md) | inaccuracy | confirmed | `Os.Env.executable` answers a path ending in ` (deleted)` after the binary is replaced, and its doc says otherwise |
| [OS8](14-dep-os.md) | bug | confirmed | `File.move` mis-decodes a failure about its second path |
| [OS9](14-dep-os.md) | bug | plausible | Linux `Directory.list` stores young names into its answer without the write barrier |
| [OS10](14-dep-os.md) | bug | confirmed | Windows `make_pipe` leaves closed handle values in its out-parameters, and the spawn's cleanup closes them again |
| [OS11](14-dep-os.md) | bug | confirmed | Windows `Os.Random.bytes` spins forever if `rand_s` fails, and `makeTemporary` ignores the failure |
| [OS12](14-dep-os.md) | bug | plausible | `reap` reads any `waitid` failure as "the child has exited" |
| [OS13](14-dep-os.md) | bug | confirmed | A scoped IPv6 address loses its scope, so link-local hosts cannot be reached |
| [OS14](14-dep-os.md) | security | plausible | Windows: the refusal of batch files is bypassed by a trailing dot or space |
| [OS15](14-dep-os.md) | bug | plausible | Closing a handle does not cancel the reads and writes parked on it (Linux) |
| [OS16](14-dep-os.md) | design | confirmed | No way to say a file's permissions, and no way to make a write durable |
| [OS17](14-dep-os.md) | bug | plausible | `Path.append` onto a verbatim base keeps a child's `/`, `.` and `..` in the bytes while its names say otherwise (Windows) |
| [OS18](14-dep-os.md) | bug | plausible | Windows `writeFile` and `open … CreateOrEmpty` fail on an existing hidden or system file |
| [OS19](14-dep-os.md) | inaccuracy | confirmed | Happy Eyeballs waits a full delay again after a failure while another attempt is in flight |
| [OS20](14-dep-os.md) | bug | confirmed | `makeTemporary` takes a prefix with separators in it |
| [OS21](14-dep-os.md) | efficiency | confirmed | A pipe or socket write costs four system calls |
| [LB4](15-dep-libs.md) | bug | confirmed | A path through an array of tables does not mean "the last item": lookups match any item |
| [LB5](15-dep-libs.md) | inaccuracy | plausible | A dotted key that adds to an implicitly created table does not mark it defined, so a later header for it is accepted |
| [LB6](15-dep-libs.md) | speed | plausible | Reading and writing a string literal builds the result one character at a time by concatenation |
| [LB7](15-dep-libs.md) | security | plausible | Nesting depth and delimiter runs are unbounded recursion on file content |
| [LB8](15-dep-libs.md) | bug | confirmed | Comment text written by `setComments`, `introduce` and `Toml.Encode.commented` is not checked |
| [LB9](15-dep-libs.md) | design | confirmed | Invalid UTF-8 is reported at line 1, column 1 |
| [LB10](15-dep-libs.md) | inaccuracy | plausible | `Toml.Decode.int`'s documentation gives the limit as 2^53, which is stock Gren's |
| [LB11](15-dep-libs.md) | inaccuracy | confirmed | The date `0000-..` is refused |
| [LB12](15-dep-libs.md) | bug | confirmed | argparse: a flag cannot be given an empty value |
| [LB13](15-dep-libs.md) | design | confirmed | argparse: any token starting with a single `-` is one short flag, even where it cannot be |
| [LB14](15-dep-libs.md) | bug | confirmed | argparse: colour and width for error text on stderr are decided from stdout |
| [LB15](15-dep-libs.md) | bug | confirmed | `PrettyPrinter.stripColor` does not look inside a coloured document |
| [LB16](15-dep-libs.md) | bug | confirmed | i18next: replacements are applied one after another, so a value is searched for later placeholders |
| [LB17](15-dep-libs.md) | efficiency | confirmed | Every `Toml.Edit` call rescans the whole document several times |

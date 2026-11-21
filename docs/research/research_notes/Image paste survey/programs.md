# How terminal programs get pasted images

Research notes, 2026-11-19. The case: a puritty user on Windows copies a
screenshot, then pastes in a tab that is ssh'd to a Linux host running Claude
Code (or a similar program).

## Summary

1. A terminal paste carries text only. No program surveyed reads an image
   through the terminal today. Each one reads the clipboard of the machine it
   runs on, so over SSH it reads the remote host's clipboard, which is empty.
2. Claude Code 2.1.328 (the installed binary) reads images with `xclip` or
   `wl-paste` on Linux, `osascript` on macOS, and PowerShell on Windows and WSL.
   It has no OSC 52 read and no OSC 5522 code. It uses OSC 52 only to *write*.
3. Claude Code knows it is over SSH (`SSH_CONNECTION`, `SSH_CLIENT`, `SSH_TTY`)
   and then says: "no image over SSH · copy the file over, paste its path".
4. Claude Code turns a pasted *path* ending in .png/.jpg/.jpeg/.gif/.webp into
   an image attachment, if the file exists on the host. This is the one route
   that works through a terminal today.
5. Claude Code treats an *empty* bracketed paste as "go read the clipboard
   image", but only on macOS and WSL. On Linux over SSH, an empty paste shows
   the "no image over SSH" hint.
6. Codex CLI, Gemini CLI, opencode, Crush, aider, Copilot CLI and Cursor CLI all
   read the local OS clipboard (arboard, xclip/wl-paste, native libraries).
   Each also accepts a pasted or dragged image path.
7. Open requests ask Claude Code (#105520) and opencode (#48628) to read images
   in-band with kitty's OSC 5522. Nothing has shipped.
8. Working workarounds all move the file out of band: scp then paste the path,
   an `xclip` shim fed through an SSH RemoteForward (cc-clip, clipaste), or a
   terminal that uploads over SFTP and types the remote path (AbsoluteTelnet
   14.02, cmux for drag-and-drop).
9. The upload-and-paste-path approach is the one a terminal with its own SSH
   client (puritty) can do with no help from the remote program.

---

## Claude Code (measured from the binary)

Binary: `/home/gram/.local/share/claude/versions/2.1.328` (373 MB, Bun single
file with the JS bundle embedded). Searched with a Python `mmap` scan that
prints a window around each match (the system `grep` is ugrep, which rejects
long `.{0,300}` contexts). Counts below are from `grep -a -c`.

| string | matches | what it is |
|---|---|---|
| `xclip` | 8 | clipboard read and write on Linux |
| `wl-paste` | 3 | clipboard read on Wayland |
| `Get-Clipboard` | 4 | Windows and WSL read |
| `TARGETS` | 4 | `xclip ... -t TARGETS`, listing image types |
| `]52;` | 3 | OSC 52 *write* only (see below) |
| `5522` | 2 | both inside unrelated SHA-256 hex strings |
| `52;c;?` | 0 | no OSC 52 read query |
| `SSH_CONNECTION` | 8 | SSH detection |

### How Ctrl+V reads an image

The image read is function `qLe` in one bundle chunk. On Linux it tries `xclip`
and then `wl-paste` (Wayland first if `WAYLAND_DISPLAY` is set):

```js
var b=["xclip","-selection","clipboard","-o","-t"],
    I=[{list:[...b,"TARGETS"],read:b},
       {list:["wl-paste","--list-types"],read:["wl-paste","--type"]}],
    D=["png","jpeg","jpg","webp","gif","bmp"];
async function A(){let e=s.WAYLAND_DISPLAY?I.toReversed():I; ...
```

It lists the types, picks the first `image/<png|jpeg|...>`, and reads it. If
that finds nothing, the fallback is PowerShell, and it is skipped on plain
Linux: `if(x()==="linux"||(await h(n.checkImage)).exitCode!==0)return null`.
The fallback command is `powershell.exe ... [System.Windows.Forms.Clipboard]::GetImage()`
piped through base64, found by `command -v powershell.exe` or
`/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`. That is the
WSL route. macOS uses `osascript -e 'the clipboard as «class PNGf»'`.

So every route reads the clipboard of the machine Claude Code runs on.

The key that triggers it (function `fa`): Ctrl+V everywhere but native Windows,
and Meta+V on Windows and WSL:

```js
function fa(h){if(h.shortcutKey!=="v")return!1;let b=x();
 if(h.ctrl&&!h.meta)return b!=="windows";
 if(h.meta&&!h.ctrl)return b==="windows"||b==="wsl";return!1}
```

When no image is found, Ctrl+V falls back to the text clipboard (`Uft`, which
runs `wl-paste`, `xclip -o`, `xsel`, then a native addon). Changelog 2.1.181:
"Fixed Ctrl+V showing 'No image found in clipboard' instead of pasting when the
clipboard contains text".

### The SSH hint

Claude Code checks for SSH and changes the "no image" message:

```js
Zle=function DM(){let GY=s.isSSH();Sr({key:"no-image-in-clipboard",kind:"feedback",
 text:GY?"no image over SSH \xB7 copy the file over, paste its path"
        :`no image in clipboard \xB7 ${HS("chat:imagePaste","Chat","ctrl+v")} to paste images`,
 row1Hint:GY?"no image \xB7 over SSH, try scp":"no image in clipboard", ...
```

The SSH test, found in the same bundle:

```js
function q(){return!!(process.env.SSH_CONNECTION||process.env.SSH_CLIENT||process.env.SSH_TTY)}
```

Changelog entries that match: 2.1.2 "Improved error message when pasting images
over SSH to suggest using `scp`"; 2.1.314 "Fixed pasting an image over SSH to a
Linux machine doing nothing silently; the prompt now says to copy the file over
and paste its path".
(https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md)

### Empty bracketed paste as an image signal

In the paste handler (`kcn`), a zero-length paste starts a clipboard image read,
but only on macOS (`J`) and WSL (`de`):

```js
J=ee(()=>x()==="macos",[]),de=ee(()=>x()==="wsl",[]);
...
function U(N,xe=N.length===0, ...){ ...
  if(xe&&(J||de)&&c){h?.(),fe();return}   // fe() debounces qLe(), the image read
  if(xe&&c)p?.();                          // p = onUnreadImagePaste
```

On other systems the empty paste calls `onUnreadImagePaste`, which is:

```js
ej=()=>{if(s.isSSH())m("input_image_paste","not_found"),DM()}
```

So an empty bracketed paste over SSH shows the "no image over SSH" hint and
reads nothing. Windows Terminal is reported to send an empty bracketed paste
when the clipboard holds only an image (see Copilot CLI below), which is why
this path exists.

### Pasted paths become images

The same handler splits pasted text into path-like tokens. A token that ends in
an image extension is read from disk and attached:

```js
var Dfn=/\.(png|jpe?g|gif|webp)$/i;
...
async function bea(e,a,n){let l=rMs(e);if(!l)return null;let r=l;
 if(x()==="wsl"&&S.test(r))r=await new MMt(s.WSL_DISTRO_NAME).toLocalPath(r);
 let o;try{if(E(r))o=await n(r);else{let c=await v();if(c&&r===C(c))o=await n(c)}}
```

Points that matter for puritty:

- The path must be absolute on the host (`E` is `path.isAbsolute`). A relative
  name only works if it equals the basename of a path in the clipboard.
- Quotes are stripped and backslash escapes undone (`B`, `T`).
- A Windows path (`C:\...`) is translated only under WSL. Over SSH it is just a
  path that does not exist on the host.
- The read goes through the Read permission check (`Ibl`, with "refused" as a
  result). Changelog 2.1.290: "Fixed Read deny rules not applying to image
  paths pasted or dragged into the prompt".
- The content must really be an image (`Ty(o)` sniffs it); BMP is converted to
  PNG.
- Several paths in one paste each become an attachment.

So if a terminal uploads the screenshot to, say, `/tmp/puritty-paste/x.png` on
the host and then sends that path as a bracketed paste, Claude Code attaches it
as `[Image #N]`. That is what the hint asks the user to do by hand.

### OSC 52 is write-only

Every `]52;` match is in the copy path (`setClipboard`), which logs
`clipboard: setClipboard mux=... ssh=... native=... emit=...` and wraps the
sequence for tmux (`raw+dcs`) or screen (`dcs`). There is no `52;c;?` or
`52;[a-z]*;?` anywhere in the file, so Claude Code never asks the terminal for
the clipboard. The UI strings say "sent ... via OSC 52 · if paste fails, hold
... while selecting".

### OSC 5522

Not implemented. The only two `5522` matches are inside hex hashes
(`...91a448a262091635522d1f5...`). Feature request #105520, "Paste images over
SSH via the kitty clipboard protocol (OSC 5522), now supported by Ghostty 1.4
and kitty", opened 2026-10-27, is open with no maintainer reply.
(https://github.com/anthropics/claude-code/issues/105520) The earlier
#42712 (closed as a duplicate by a bot) reports that an `xclip` shim speaking
OSC 5522 worked in kitty but raced with Claude Code for the tty's input, so it
must be done in-process. (https://github.com/anthropics/claude-code/issues/42712)

### Does Claude Code use a terminal clipboard protocol for images?

**No, refuted for 2.1.328.** The belief probably comes from #69330, whose
reporter wrote that image paste over SSH "works via the OSC 52 clipboard read
protocol" from macOS Terminal.app up to 2.1.179. The issue was closed as a
duplicate with no maintainer reply. There is no OSC 52 read in the current
binary, and OSC 52 carries only text anyway. Not verified what made it work for
that user. (https://github.com/anthropics/claude-code/issues/69330)

### Anthropic's own answer

Boris Cherny on #5277 (2026-08-16): "When Claude Code runs on a remote machine
over SSH, the image is on your local clipboard and the CLI can't see it, so
paste won't work." He gives two options: `scp` and give the path, or use Remote
Control from claude.ai/code. (https://github.com/anthropics/claude-code/issues/5277)

The docs list three ways to add an image: drag and drop, Ctrl+V (Alt+V on
Windows and WSL), and an image path. They say nothing about SSH.
(https://code.claude.com/docs/en/common-workflows#work-with-images)

### Other related issues

- #98469 and #76191: Windows client → SSH → Linux. Ctrl+V gives the "try scp"
  message even when the clipboard holds text, because Claude Code takes the
  Ctrl+V key. Users fix it by unbinding `ctrl+v` in `keybindings.json` and using
  the terminal's own paste (Ctrl+Shift+V, Shift+Insert, right click).
  (https://github.com/anthropics/claude-code/issues/98469,
  https://github.com/anthropics/claude-code/issues/76191)
- #106303: same failure in a VS Code Remote Tunnels terminal. The VS Code
  remote terminal does not carry images either.
  (https://github.com/anthropics/claude-code/issues/106303)
- #77864: asks Claude Code to use iTerm2's `OSC 1337 ; RequestUpload=format=tgz`
  so iTerm2 sends the file through the terminal. Open.
  (https://github.com/anthropics/claude-code/issues/77864)
- Changelog 2.1.136 and 2.1.157: WSL reads the Windows clipboard through
  PowerShell, and images dragged from Windows Explorer work under WSL.

---

## OpenAI Codex CLI

- Reads with the Rust crate `arboard` in-process
  (`codex-rs/tui/src/clipboard_paste.rs`, `paste_image_as_png`). It first takes
  file paths on the clipboard, then image data. Under WSL it falls back to
  `powershell.exe`, `pwsh` or `powershell` to dump the Windows clipboard image
  to a temp PNG (`try_wsl_clipboard_fallback`).
  (https://github.com/openai/codex/blob/main/codex-rs/tui/src/clipboard_paste.rs)
- Keys: `fixed.paste_image` is Ctrl+V and Ctrl+Alt+V (`codex-rs/tui/src/keymap.rs`).
- A pasted text that "looks like an image path" is attached as an image
  (`bottom_pane/chat_composer/paste_input.rs`, `apply_paste`).
- No terminal protocol. Over SSH, arboard talks to the remote X11/Wayland.
- Issues: #25465 asks for an env-gated external clipboard reader for headless
  hosts (open). #59798: with cc-clip's X11 bridge, large screenshots failed
  because arboard waits only 10 ms between X11 INCR chunks; closed as upstream.
  Because Codex does not shell out, an `xclip` shim does not help it; cc-clip
  runs Xvfb plus its own X11 selection owner instead.
  (https://github.com/openai/codex/issues/25465,
  https://github.com/openai/codex/issues/59798)
- #53220: in MobaXterm over SSH, a text paste set off the image clipboard error.

## Gemini CLI

- `packages/cli/src/ui/utils/clipboardUtils.ts`: `clipboardHasImage` and
  `saveClipboardImage` shell out to `wl-paste --list-types` / `wl-paste` on
  Wayland, `xclip -selection clipboard -t TARGETS -o` / `xclip` on X11,
  `powershell` on Windows, and `osascript` on macOS. The image is saved under
  the project and inserted as an `@path`.
  (https://github.com/google-gemini/gemini-cli/blob/main/packages/cli/src/ui/utils/clipboardUtils.ts)
- `parsePastedPaths` turns pasted or dropped file paths into `@path` mentions.
- No terminal protocol, no SSH handling. Issue #22274 is a WSL2 BMP bug.

## opencode (anomalyco/opencode, formerly sst/opencode)

- The TUI asks `ClipboardService.read({ preferredTypes: ["image/png", "text/plain"] })`
  (`packages/tui/src/clipboard.ts`). The service is in OpenTUI, with native Zig
  code for X11, Wayland, macOS and Windows (`packages/native/src/clipboard/`).
  OpenTUI's own comment: "Reads the process host clipboard. It cannot read the
  terminal user's clipboard over SSH." OSC 52 is used for writes.
  (https://github.com/anomalyco/opentui/blob/main/packages/core/src/lib/clipboard.ts)
- #48628 (open, 2026-09): "terminal does not clipboard read (kitty OSC 5522) for
  image paste over SSH". A bot reply says "Maintainers will consider it". One
  user said that in v1 he put a fake clipboard binary in `PATH` that read from a
  forwarded unix socket, and that this no longer works in v2.
  (https://github.com/anomalyco/opencode/issues/48628)
- #25806: kitty's own paste action is text-only, so Ctrl+Shift+V drops images;
  plain Ctrl+V works when `wl-clipboard` is installed. The issue claims
  Alacritty pipes raw image bytes into a bracketed paste. Not verified.
  (https://github.com/anomalyco/opencode/issues/25806)

## Crush (charmbracelet)

- `internal/clipboard` wraps `golang.design/x/clipboard` (cgo X11, macOS,
  Windows). Ctrl+V is "paste image from clipboard"
  (`internal/ui/model/keys.go`). `pasteImageFromClipboard` in
  `internal/ui/model/ui.go` reads `FormatImage`; if that fails, it reads the
  text and attaches it if it is an existing file path.
  (https://github.com/charmbracelet/crush/blob/main/internal/ui/model/ui.go)
- No terminal protocol. No SSH issues found.

## aider

- `/paste` (`aider/commands.py`, `cmd_paste`) calls Pillow's
  `ImageGrab.grabclipboard()`, saves the image to a temp file and adds it.
  Pillow uses `wl-paste` or `xclip` on Linux (Pillow docs; not checked here).
  (https://github.com/Aider-AI/aider/blob/main/aider/commands.py)
- Image files can also be added with `/add`. No SSH handling.

## GitHub Copilot CLI

- Closed source. The GitHub docs list Ctrl+V as "Paste from clipboard as an
  attachment". The 2025-11-18 changelog added drag-and-drop images.
  (https://docs.github.com/en/enterprise-cloud@latest/copilot/reference/copilot-cli-reference/cli-command-reference,
  https://github.blog/changelog/2025-11-18-github-copilot-cli-new-models-enhanced-code-search-and-better-image-support/)
- A third-party patch project says Copilot CLI uses the native module
  `@teddyzhu/clipboard` (`ClipboardManager().getImageData()`), and that on
  Windows "Windows Terminal emits an *empty* bracketed paste sequence" when the
  clipboard holds an image, which the CLI takes as the cue to read it. On macOS
  nothing reaches the CLI for an image-only clipboard. Tracking issue:
  github/copilot-cli#3104. Not verified against the binary.
  (https://github.com/idanshimon/copilot-cli-image-paste)
- A Windows Terminal maintainer confirms the convention: "there are some TUI
  tools out there that use a clipboard paste sequence with an _empty_ payload as
  a hint for 'hey go open the system clipboard'."
  (https://github.com/microsoft/terminal/issues/19517)

## Cursor CLI (cursor-agent)

- Closed source. Forum reports only. Ctrl+V image paste exists but is flaky:
  a 2026-10-25 macOS report blames an `execFile` call missing
  `encoding: "buffer"`. Windows paste was asked for and the thread closed.
  Linux X11 image reading is requested, not confirmed. Workaround in every
  thread: save the file and use `@path` or drag and drop.
  (https://forum.cursor.com/t/ctrl-v-image-paste-always-fails-on-macos-execfile-missing-encoding-buffer/176096,
  https://forum.cursor.com/t/cursor-cli-doesnt-support-image-paste-on-windows/162099,
  https://forum.cursor.com/t/image-pasting-support-on-linux-in-cursor-cli/148471)
- Mechanism: not verified.

## Amp

- Closed source. Docs: Ctrl+V pastes a clipboard image; if the terminal takes
  Ctrl+V, use Ctrl+O and run "paste image from clipboard"; or drag files or
  paste a path, or use `@`.
  (https://ampcode.com/docs/cli/keybindings, https://ampcode.com/news/cli-image-support)
- Mechanism and SSH behavior: not verified. It almost surely reads the local
  OS clipboard like the others (inference).

## Shared libraries

- Rust `arboard` (1Password): Codex. Claude Code also ships a native addon with
  arboard strings (`ARBOARD_CLIPBOARD`, `x-kde-passwordManagerHint` found in the
  binary); it exposes `getLinuxClipboardText` / `setLinuxClipboardText`, so it is
  used for text only.
- `golang.design/x/clipboard`: Crush.
- `@teddyzhu/clipboard`: Copilot CLI (per the patch project above).
- Pillow `ImageGrab`: aider.
- Node `clipboardy`: not found in any of these for images (it is text-only).
- All of them read the local OS clipboard. None speaks OSC 52 read or OSC 5522.

---

## Terminals and the protocols

- kitty's clipboard protocol (OSC 5522) carries any MIME type, images
  included, in both directions. A "paste events" mode (DEC private mode 5522,
  found with DECRQM `CSI ? 5522 $ p`) lets the program take over paste: on each
  paste the terminal sends the list of MIME types and the program asks for the
  one it wants. (https://sw.kovidgoyal.net/kitty/clipboard/)
- Ghostty: #105520 says Ghostty 1.4 ships OSC 5522 and paste events; another
  report said it was only in the development tree. Not verified which release.
  (https://runtimewire.com/article/ghostty-kitty-clipboard-images-libghostty)
- Windows Terminal: no image paste. #19517 (open) discusses it: a maintainer
  asks what format an app would expect; another suggests a data URI. #20479
  proposed a `filterPaste` action that pipes clipboard bitmaps or dropped files
  through an external program and types its stdout, for "uploading to a remote
  host over ssh". Closed 2026-07-29 for lack of capacity.
  (https://github.com/microsoft/terminal/issues/19517,
  https://github.com/microsoft/terminal/issues/20479)
- iTerm2 has `OSC 1337 RequestUpload`, an in-band upload the remote program
  starts (Claude Code #77864 asks to use it).

---

## Workarounds people use

**Copy the file, paste the path.** The official answer (#5277). Scripts and
apps automate it: take the screenshot, `scp` it, put the remote path on the
local clipboard, paste.
- clipssh: "Extracts the screenshot from your local clipboard, uploads it to the
  remote server, and copies the file path." (https://github.com/samuellawrentz/clipssh)
- ssh-img-paste (macOS): "uploads it using the existing OpenSSH configuration,
  and puts the resulting remote path on the clipboard".
  (https://github.com/SerenityTn/ssh-img-paste)
- sshshot, vmup, Raycast "SSH Image Drop", Snap2Link (uploads to Google Drive
  and pastes a URL), and a user's Automator Quick Action (#5277).

**An `xclip` shim fed through SSH.** A local daemon serves the clipboard image;
`RemoteForward` carries it; a fake `xclip` on the host answers `TARGETS` and
`-t image/png -o`. Works with Claude Code's Ctrl+V because Claude Code shells
out to `xclip`.
- cc-clip: "Local Mac clipboard → pngpaste → HTTP daemon → SSH RemoteForward →
  xclip shim → Claude Code". For Codex it adds Xvfb and an X11 bridge.
  (https://github.com/ShunmeiCho/cc-clip)
- clipaste: "installs an xclip shim on the remote server and configures SSH
  RemoteForward"; per its README, Codex bypasses the shim.
  (https://github.com/hqhq1025/clipaste)

**X11 forwarding.** `ssh -X` lets the remote `xclip` read a local X server's
clipboard. Needs an X server locally (XQuartz, or VcXsrv on Windows); slow for
large images. (https://zenn.dev/y_namba/articles/0001_y-namba, summarized by
search; not tested)

**A terminal that uploads.** These are the closest to what puritty could do.
- AbsoluteTelnet 14.02 (2026-08-14, Windows): "paste image clips and files to
  Claude Code over SSH/SFTP bridge". Its author on #5277: "it uses an SFTP
  channel across the current already open session and pastes the file location
  into the Claude chat ... requires no additional setup".
  (https://www.celestialsoftware.net/version-history/,
  https://github.com/anthropics/claude-code/issues/5277)
- cmux (macOS, Ghostty-based): dragging a file into a remote terminal uploads it
  with scp over the existing ControlMaster connection. Whether a clipboard paste
  also uploads: not verified. (https://cmux.com/docs/nightly/ssh,
  https://cmux.com/blog/cmux-ssh)

**Other routes.**
- VS Code Remote: paste the image into a markdown file in the remote workspace
  (VS Code saves it there), then paste its path (#5277). Extensions
  claude-paste and claudeboard upload over Remote-SSH and insert the path.
  (https://github.com/humanrace-ai/claude-paste)
- Claude Code skill plus local daemon: run `/paste-image` on the remote side.
  (https://github.com/AlexZeitler/claude-ssh-image-skill)
- Remote Control: drive the remote session from claude.ai/code or the mobile
  app, where images attach directly (Anthropic's suggestion on #5277).

**Complaints, quoted.**
- "I really would love to have this feature" / "I NEED THIS!" (#5277)
- "I hate having to have to spin up daemon's and services to copy over files.
  OSC 5522 is starting to be implemented in other terminals, and should be
  included in claude code" (#5277, 2026-09-11)
- "Pasting a screenshot does nothing. Pasting or dropping a file inserts a local
  Windows path that is meaningless on the other end." (microsoft/terminal#20479)
- "#5277 was answered with `scp` / Remote Control, which work but aren't paste."
  (#105520)

---

## What this means for puritty (notes, not decisions)

- With today's Claude Code, the path is the only in-terminal route: upload the
  clipboard image over the session's SFTP channel to an absolute path on the
  host, then send that path as a bracketed paste. Claude Code attaches it as an
  image. Codex, Gemini CLI, Crush and Copilot CLI also accept a pasted image
  path.
- Sending an empty bracketed paste does not help over SSH: Claude Code on Linux
  answers it with the "no image over SSH" hint.
- If Claude Code or opencode adds OSC 5522 paste events later, a terminal that
  implements OSC 5522 would serve the image in-band with no upload. Nothing
  supports it yet.

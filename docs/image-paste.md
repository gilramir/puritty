# A copied image pasted into a remote program: a survey

Gilbert, 2026-11-19, on `feature-plan.md` §8 (a screenshot copied on
Windows, pasted in an ssh tab into Claude Code on the host): "can it ever
come across as a paste, or do we need to handle it as an sftp upload?",
then "i think claude code does [read it through the terminal], but
investigate. Do another survey of this kind of copy/paste across
programs."

This is the survey; nothing is built. The sources are two sets of notes in
`research/research_notes/Image paste survey/`, each claim there with its
link: `programs.md` (how Claude Code, Codex CLI, Gemini CLI, opencode,
Crush, aider, Copilot CLI, Cursor CLI and Amp get an image, and the
workarounds people use) and `terminals.md` (kitty's clipboard protocol and
who implements it, OSC 52, tmux, and what Ghostty, iTerm2, WezTerm, Warp,
VS Code, Windows Terminal, Tabby, cmux, Ctrl-V Terminal and the far2l
extensions do on a paste with an image and no text). Reddit was out of
reach, as for `sftp.md`.

## IP1 · Claude Code reads its own host's clipboard, never the terminal's

Measured from the installed binary, Claude Code 2.1.328
(`~/.local/share/claude/versions/2.1.328`), with `grep -a`; the matches are
quoted in `programs.md`:

- **How it reads an image.** On Linux `xclip -selection clipboard -t
  TARGETS`, then `-t image/<type> -o`, or `wl-paste --list-types` and
  `--type` (Wayland first); on WSL `powershell.exe` with
  `Clipboard::GetImage()`; on macOS `osascript`. Ctrl+V asks for it (Meta+V
  on Windows and WSL).
- **No terminal protocol.** OSC 52 is in the binary only for *copying*
  (with tmux and screen wrapping); there is no `52;c;?`, so it never asks
  the terminal for the clipboard. The two `5522` matches are inside
  SHA-256 hex strings. Gilbert's recollection is not true of this version;
  it probably came from claude-code#69330, a user's claim closed by a bot.
- **It knows it is over ssh.** It checks `SSH_CONNECTION`, `SSH_CLIENT` and
  `SSH_TTY`, and then says "no image over SSH · copy the file over, paste
  its path" (checked by hand in the binary too).
- **An empty bracketed paste** means "read the clipboard image", on macOS
  and WSL only. Windows Terminal sends one on purpose when the clipboard
  holds only an image (its source calls it "LOAD BEARING"), which is how
  Claude Code in WSL gets a Windows screenshot. Over ssh on Linux an empty
  paste only shows the hint.
- **A pasted path becomes an image.** A token in the pasted text ending in
  `.png`, `.jpg`, `.jpeg`, `.gif` or `.webp`, *absolute* and existing on
  the host, is read and attached as `[Image #N]`. Quotes and backslash
  escapes are undone; the content is sniffed to be a real image (BMP is
  turned into PNG); the read passes the Read permission rules; several
  paths in one paste make several images. A Windows `C:\` path is
  translated only under WSL.
- **Anthropic's answer.** On claude-code#5277, 2026-08-16, an Anthropic
  staff member: over ssh "paste won't work"; use scp and paste the path.
  The request to use OSC 5522 (claude-code#105520, opened 2026-10-27) is
  open with no maintainer reply.

**The other programs are the same.** Codex CLI (`arboard`, PowerShell on
WSL), Gemini CLI (`xclip`, `wl-paste`, `powershell`, `osascript`),
opencode (native code; its own source says it "cannot read the terminal
user's clipboard over SSH"; its OSC 5522 request is open), Crush
(`golang.design/x/clipboard`), aider (Pillow's `ImageGrab`), Copilot CLI
(reads the clipboard on an empty bracketed paste). Every one also takes a
pasted or dragged image path. Cursor CLI's and Amp's mechanism: not
verified.

So, for Gilbert's question: **no program surveyed can receive an image
through a paste today. Every one takes a path.** The bytes have to reach
the host some other way.

## IP2 · The one in-band protocol: kitty's OSC 5522

kitty's clipboard protocol carries any MIME type, both ways, base64 in
chunks of 4096 bytes before encoding, and a terminal must accept at least
64 MB. Every read asks the user unless a password granted earlier is
given. Its **paste events** (`CSI ? 5522 h`, kitty#9183) fit this case
exactly: on the paste key, the terminal sends the program the list of
MIME types with a one-time password, and the program asks for `image/png`
without a prompt, because the key press was the consent.

- **Shipped by** kitty, Ghostty 1.4.0 (2026-10-27; its write limit is
  32 MB, under the spec's 64 MB), contour 0.7.0 (8 MiB). foot has an open
  pull request by its maintainer.
- **Not in** iTerm2, WezTerm, Windows Terminal, Konsole, Alacritty.
- **tmux blocks it**: it drops the mode and doesn't parse the replies; its
  maintainer declined it on 2026-11-04 (tmux#5837) as "not wide enough
  support yet". Gilbert uses tmux and puritty has a `tmux -CC` mode, so
  this alone rules it out for now.
- **Programs that use paste events:** only omp (oh-my-pi). Claude Code and
  opencode have open requests.

**OSC 52 is text only** in every terminal checked; Windows Terminal,
Konsole and WezTerm ignore a read. tmux 3.7 adds a `get-clipboard` option
for reads, still text.

**far2l's terminal extensions** (an APC protocol, in the PuTTY forks
putty4far2l and KiTTY) allow clipboard reads only within 5 s of the user's
paste key, a good gate, but carry no images in practice.

## IP3 · What terminals do on a paste with only an image

| Terminal | What happens |
|---|---|
| Windows Terminal | an empty bracketed paste, on purpose; the program reads its own clipboard (works in WSL, not over ssh) |
| Ghostty | can pass the key through to the program (`performable:`); OSC 5522 since 1.4.0 |
| WezTerm, Warp over ssh, Tabby | nothing |
| VS Code | pastes the *local* path of a copied file; no upload over Remote-SSH |
| iTerm2 3.7 | a dialog: "Upload and Paste Path", "Upload" (remote sessions), "Save to temp file and paste path" (local), "Paste Base64-Encoded Contents"; can be told to remember the answer |
| Ctrl-V Terminal (Windows) | Ctrl+V uploads the image over SFTP and pastes its path, for Claude Code and Codex (from its listing; not tested) |
| AbsoluteTelnet 14.02 | uploads a pasted image over SFTP on the open session and pastes the remote path |
| cmux | uploads *dragged* images by scp over ControlMaster; paste not documented |

iTerm2 uploads to the shell's directory, or to home in tmux integration,
names each screenshot uniquely, and converts macOS's TIFF to PNG. Its
upload goes over its own SSH integration or scp.

**Declined elsewhere.** Ghostty closed a pull request (#10515, unmerged,
2026-02-01) that found the ssh ControlMaster socket, scp'd the image to
`/tmp/ghostty-paste-{uuid}.png` and pasted the path: "a hack", OSC 5522 is
the real way. Ghostty also refused one that uploaded dragged images to an
image-hosting site (#9699). Windows Terminal declined a paste-filter hook
that would let an outside program do it (#20479, July 2026).

**Workarounds people use by hand** (`programs.md`): scp then paste the path
(clipssh, ssh-img-paste and sshshot automate it); a fake `xclip` on the host
fed through an ssh `RemoteForward` (cc-clip, clipaste), which Codex
doesn't call; `ssh -X` with a local X server (what Gilbert's ETX desktop
does, `feature-plan.md` §8); VS Code Remote, pasting into a markdown file
and copying the path.

## IP4 · What this means for puritty

**§8's design is the one that works today**, with every program surveyed,
through tmux and `tmux -CC`: on the paste key, when the clipboard holds an
image and no text, puritty puts the image on the host over the tab's own
connection (no second login), and pastes the absolute path as a bracketed
paste. It is what Claude Code's own hint asks the user to do by hand, and
what iTerm2, Ctrl-V Terminal and AbsoluteTelnet do. Ghostty's objection
("a hack") is about doing it from outside the ssh client by finding
ControlMaster sockets; puritty *is* the ssh client, so it doesn't apply.

The survey adds these details to §8:

- **The path is absolute, and the name unique and safe** (letters, digits,
  `-`, `.png`), so Claude Code's tokenizer takes it whole. The upload
  finishes before the path is pasted, or Claude Code finds no file.
- **The format is PNG.** When the clipboard already holds a PNG (Windows'
  registered `PNG` format, X11's `image/png`), its bytes go up as they
  are. Only a bitmap with no PNG beside it (`CF_DIB`, as Print Screen
  leaves) is encoded, because the path route takes only `.png`, `.jpg`,
  `.jpeg`, `.gif` and `.webp` (Claude Code's `Dfn` pattern, IP1); a `.bmp`
  path is pasted as plain text and not attached. Those four are also the
  only image types Anthropic's API accepts, so other programs that
  attach a path are likely to want the same. PNG is the lossless one of
  them, and §8 step 1 already plans the encoder.
- **Where on the host.** §8 says `~/.cache/puritty/paste/`; iTerm2 uses the
  shell's directory. A pasted image is not a file the user meant to put in
  their project, so the leaning stays the cache folder, with old files
  deleted (§8).
- **The transport** is the second channel either way: SFTP when it
  exists, else §8's `exec` channel with `cat`, which `sftp.md` FT7 also
  uses.
- **OSC 5522 later, beside it.** If Claude Code takes up paste events and
  tmux passes them, puritty could answer them as well (it holds the
  clipboard and the connection). Until both happen it helps nobody
  Gilbert runs. The register should carry it, with tmux#5837 and
  claude-code#105520 as the things to watch.

## IP5 · Questions for Gilbert, with leanings

1. **Ask, or just do it?** iTerm2 asks with a dialog (that can remember);
   Ctrl-V Terminal just uploads. Leaning: just do it on the normal paste
   key when the clipboard holds an image and no text, since there is
   nothing else a paste could mean then; a setting turns it off. A note
   over the terminal says where the file went.
2. **A local tab.** On Windows, a local tab running WSL: send the empty
   bracketed paste, as Windows Terminal does, so Claude Code in WSL reads
   the Windows clipboard itself. On Linux, a local tab: save to a
   temporary file and paste its path, as iTerm2 does locally. Leaning:
   both.
3. **`ssh` typed in a local tab** (puritty can't reach that host): paste
   nothing and say why, as §8 says.
4. **OSC 5522 into the register** as "later, when tmux and Claude Code
   take it". Leaning: yes.

## IP6 · Gilbert's answers (2026-11-19)

1. **Upload without asking**, on the normal paste key when the clipboard
   holds an image and no text, "but it should be controlled by a user
   option". A setting, on by default; off, the paste does what it does
   today.
2. **Local tabs as leaned**: on Windows with WSL, the empty bracketed
   paste, as Windows Terminal sends; on Linux, a temporary file and its
   path.
3. **OSC 5522 later**: "yes, visit later". Entered in `feature-plan.md`
   §2's table.

Asked in the same message: why PNG. The answer is IP4's first bullet on
the format (a PNG already on the clipboard is sent unchanged; only a bare
bitmap is encoded, because a `.bmp` path is not attached).

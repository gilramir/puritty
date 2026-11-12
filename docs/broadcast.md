# Broadcast input: a survey before the design

Typing once into several tabs at once. Gilbert, 2026-11-12: "Next on the
tabs list is broadcast input; think about the design of how to do this;
where is the user going to type their input? in one of the sessions, or
in a new input screen? What do other terminals that support this do?
investigate the UI/UX first." And, while the research ran: "it's fair to
set a rule that tabs we broadcast to must be using the same character set;
yes, IME is a concern; probably the user *does* want to see all the
screens he is broadcasting too; maybe we have to split them out into
different windows."

This is the survey; nothing is built. The sources are three sets of notes
in `research/research_notes/Broadcast survey/`, each claim there with its
link: `terminals.md` (Terminator, Tilix, Konsole, iTerm2, Windows
Terminal, Warp, kitty, WezTerm, Tabby, Zellij, tmux, Hyper, Ghostty's open
pull request; much of it read from the programs' source),
`ssh_clients.md` (MobaXterm, SecureCRT, Xshell, Termius, Royal TS, Remote
Desktop Manager, mRemoteNG, SuperPuTTY, MTPuTTY, WindTerm, electerm,
Ásbrú, ClusterSSH, csshX), and `pitfalls_and_requests.md` (the requests,
the accidents, Windows Terminal's design spec, what people use it for).

## BC1 · Where the user types: three models

**In a session, its input copied to the others.** The user types into one
of the terminals as usual, and what is typed also goes to the rest. Most
programs: Terminator, Tilix, Konsole, iTerm2, Windows Terminal, Warp,
Tabby, tmux (`synchronize-panes`), Zellij, MobaXterm, Xshell's "Send Key
Input to All Sessions", Termius, Royal TS, Remote Desktop Manager,
WindTerm. It handles everything a terminal is typed with: Ctrl+C, Tab
completion, arrows, editors, pagers. Its failure is the one the
accidents come from: the user forgets it is on, or cannot tell which
sessions it reaches.

**A box in the window**, composing a line sent on Enter: SecureCRT's
Command Window, Xshell's Compose bar and Compose pane, mRemoteNG,
SuperPuTTY, MTPuTTY, electerm, WindTerm's Sender. Safe and editable, and
the line can be read before it goes; but it only carries text. **The two
vendors who have lived with it longest both had to add key-by-key**:
SecureCRT added "Send Characters Immediately" to its box in 8.0 because
users needed Ctrl+C, vi and Tab completion; Xshell keeps the box for
lines and a separate mirror mode for "Esc, Backspace, and Ctrl or Alt
combinations". Warp considered a floating input and dropped it as too
costly; Windows Terminal's spec rejected SecureCRT's design as "less
ergonomic".

**A console window of its own**, with every target in a window of its
own beside it: ClusterSSH and csshX. Whatever is typed in the console
goes to every host's window, key by key; each host's window can also be
typed into directly; csshX greys the text of a window left out. kitty's
`broadcast` kitten is a cousin: a window of its own with a one-line echo,
the targets wherever they are.

## BC2 · What is sent

Three ways, and the difference matters to puritty more than to anyone:

- **Key events, each target encoding them for itself**: Terminator,
  Tilix, Windows Terminal, tmux, kitty for keys that are not text. A
  target in application-cursor mode gets its own arrow bytes.
- **The source's bytes, copied**: iTerm2, Konsole, Tabby. A target in
  another mode gets the wrong bytes; Konsole's code even forwards the
  source terminal's own replies.
- **Lines**: SecureCRT and the other boxes; Warp syncs the shell's line
  buffer and falls back to keys inside running programs.

**Paste and IME are where every design breaks.** Windows Terminal brackets
a paste only in the source pane, and its paste broadcast reached random
subsets of panes and crashed (#16287, #20164); Terminator and Tilix lose
IME and compose input, because they copy key events and committed text is
not one. **No program broadcasts the mouse**, and no one asks for it.
**Passwords**: only iTerm2 guards them, probing each target's echo before
sending a stored password; elsewhere a password typed while one target is
not at a prompt is shown in clear there.

No vendor documents what happens across encodings (an EUC-KR host and a
UTF-8 one); Gilbert's rule settles it for puritty (BC6).

## BC3 · Choosing the targets

- **The common scopes**: all panes of this tab; all panes in every tab of
  the window (iTerm2, Warp, Tabby). Windows Terminal, tmux and Zellij
  offer only the tab; iTerm2 never crosses windows.
- **All, then leave some out**: MobaXterm's Exclude box under each tile,
  with all on and all off since 24.2; Xshell's Off button on each
  session; iTerm2's per-session toggle; ClusterSSH and csshX per host.
- **Named or colored sets**: Xshell sends to tabs of the same color,
  SecureCRT to a tab group, Terminator to a named group; Ghostty's open
  pull request has up to 16 numbered groups, each with its own border
  color, across tabs and windows. Wherever groups are missing, they are
  asked for (iTerm2 #3372, #5639; Windows Terminal #16593, #17011).
- **Silent changes to the set are the bug that matters most**: SecureCRT's
  changelog fixes a left-out tab joining again when it reconnected (9.5)
  and the scope quietly going back to the active session (9.4, 9.6);
  Ásbrú's reconnect left the cluster.

## BC4 · Seeing it

**Every target must show that it receives, on itself, not only on the
tab.** The programs that marked only the tab or the source were asked for
more (Zellij #2838, kitty #2962, Terminator, iTerm2 #6007: "struggle with
being able to tell which mode I'm in"). The strongest marks: Xshell's bar
across the top of each receiving session with its own Off button;
MobaXterm's change to a view of all terminals at once; Windows Terminal's
accent border; Ghostty's group colors; iTerm2's stripes and corner icon;
csshX's grey for those left out. **A mark that disagrees with where the
keys go is the worst bug of all** (Windows Terminal #15812, a new pane
receiving with no border; Konsole 509299, marked and not receiving).

**Seeing every target's output is part of the feature, not an extra.**
MobaXterm tiles every terminal when MultiExec starts; SecureCRT tells its
users to tile; Termius and Tabby broadcast only to panes on the screen; a
Remote Desktop Manager user asked for "broadcast and tile" as one button
because "This feature works perfect in MobaXterm".

**Hidden targets cause the accidents.** Zellij #3458: a `reboot` reached a
pane hidden behind a full-screen one and took down both halves of a
redundant cluster. tmux, by design, skips panes hidden by zoom. Terminator
#744: a `sudo` password went into a background terminal the user had
forgotten, the broadcast mode restored from the saved layout. One user
puts twenty as the most one can read at once; uses range from three to
six panes to thirty to sixty hosts.

## BC5 · Starting and stopping

A toggle key and a menu item, mostly. **Accidental starts made several
projects drop their default keys**: Terminator removed them in 2020, Warp
has an open proposal to (#10662), Tilix and tmux ship none. iTerm2 asks on
each start, naming how many panes, and users asked to silence it (#1658,
2011): a warning that fires every time is dismissed by habit. Stopping
must always be easy to find (kitty #6974, iTerm2 #9932), and stopping by
accident is a failure too (Tabby ends on any click, #9101). A start must
never restore broadcast silently (Terminator #620). No program has an
automatic time-out or a sound.

## BC6 · puritty's own constraints

- **One tab shown at a time, no splits.** In Terminator, iTerm2 or Windows
  Terminal the panes receiving are on screen; in puritty the other tabs
  are hidden. Copying the shown tab's keys to the hidden ones is exactly
  BC4's accident. Whatever puritty does must put the targets on screen.
- **One window to a process.** A tab cannot move to another window: its
  terminal, its pty or its built-in ssh session live in this process
  (moving a tab is TB1's "reconnect" item, and tear-off is not planned).
  Targets in windows of their own would need the window package to open
  several windows in one process, on X11 and Windows, and the loop to
  serve them: possible, and a project of its own.
- **One character set** (Gilbert): every tab in a broadcast has the same
  charset. A tab with another is not offered as a target, and says why.
  Text is then encoded once, the same for all; keys are still encoded by
  each tab for its own modes (BC2's first way).
- **IME** (Gilbert): Korean is composed in a preedit before it is
  committed. The preedit is drawn in one place only, the terminal typed
  in; what the IME commits is text, sent to every target. The key-copying
  designs lose this (Terminator, Tilix); a box shows it naturally.
- **Tabs under `tmux -CC`** draw tmux's panes, and their keys go to tmux's
  active pane (TM14): a broadcast into them reaches one pane of several.
- **puritty's own screens** in ssh tabs (a host key, a password, a
  failure): a tab asking its own question is not at a shell. A password
  typed for one host must never go to another.

## BC7 · Options for puritty

**Where the keys come from:**

- **A. Typing into the shown tab, copied to the hidden tabs.** What most
  terminals do, and ruled out by BC6's first point: the targets would be
  hidden.
- **B. A broadcast view: the target tabs tiled in the window, typing into
  one tile copied to the others.** MobaXterm's MultiExec. Entering it
  turns the window into a grid of the chosen tabs' terminals, each with
  its label, a mark that it receives, and a way to leave it out; the
  tile typed in is marked as the source; leaving returns to the tabs.
  Everything a terminal is typed with works; the preedit is drawn in the
  source tile; every target is on screen by construction; forgetting it
  is on is hard when the window is a grid. Its cost: drawing several
  terminals in one window, which `Vt.View` does one at a time today.
- **C. Targets in windows of their own** (Gilbert's thought), with typing
  into any of them copied to the others, ClusterSSH's way. The same
  experience as B, with the window manager doing the tiling and the user
  free to arrange and size them; its cost is several windows in one
  process (BC6).
- **D. A compose line at the bottom of the window**, sent on Enter to
  every target, with a key-by-key switch, SecureCRT's and Xshell's way.
  IME works as in any of puritty's own fields (the rename box); but its
  vendors had to add key-by-key, and it still needs the targets on
  screen, so it is an addition to B or C, not instead of them.

**How a tile is sized, in B:** the tab's terminal resized to its tile
(every program told, as on any resize, and lines reflowed; back to the
window's size on leaving), or the terminal kept at its size and drawn
smaller (no program told; the renderer would need a second, smaller cell
size in one frame). MobaXterm's way is not documented.

**What crosses:** keys, encoded by each target for its own modes; text the
IME commits, and pasted text, each target pasting it as a paste (bracketed
where that tab asked for it; Windows Terminal's history says to decide
paste now, not later); not the mouse; not puritty's own keys (Ctrl+Shift+T
and the rest act on the window).

**Which tabs:** the window's tabs (no other window is reachable, BC6),
all of them by default, each one left out or put back by a click on its
tile or a key; a tab with another charset, under `tmux -CC`, or at its own
ssh question is out and marked why. A tab that drops or reconnects stays
out until the user puts it back: membership never changes by itself
(BC3). Tab colors (TB9) make a later "this color's tabs" cheap, as
Xshell's.

**Starting and stopping:** a menu item and a `[keys]` entry, empty by
default (BC5's accidents); the grid itself is the reminder, so no
question each time. Leaving: the same key, the menu, or a button in the
view; never by a click on a tile.

## BC8 · Leanings, for Gilbert

1. **B, the broadcast view in the window**, typing into a tile copied to
   the others; C kept for later if the grid is too small for the tabs
   wanted (twenty tiles of 80 by 24 do not fit one screen readably).
2. **Resize the tabs to their tiles** first, as every terminal does on
   any resize; drawing at a smaller size measured afterwards, since it
   spares twenty remote programs a resize each way.
3. **Keys and committed text and paste cross; the mouse does not.** Each
   target encodes keys for its own modes; the charset rule makes text the
   same bytes for all.
4. **All the window's tabs, minus those left out**, with the left-out
   marked on their tiles, and tabs that cannot take part (charset,
   `tmux -CC`, an ssh question) out and saying why.
5. **D, a compose line, not in the first version.**
6. **No default key**; the menu and a `[keys]` entry.

Questions for Gilbert are these six; nothing is built until he has chosen.

# Tabs

*Status: built ([`../tabs.md`](../tabs.md) TB3, TB4, TB6, TB9, TB10,
TB11): several sessions in one window, the keys and your own choice of
them, the bar and its marks, renaming, asking before closing a busy tab, a
new tab in the same directory, tab colors, a host's or your own, the tabs
opened again when puritty starts, and a closed tab opened again.*

A puritty window can hold several sessions, each in its own tab: a local
shell, or an ssh session to one of your hosts. Every tab keeps its own
screen, scrollback, selection and search, and keeps running while another
is shown, so a long build or a log you are following goes on in its tab.

## Keys

| key | does |
|---|---|
| Ctrl+Shift+T | a new tab, after the last, in the shown tab's directory. In a tab of an ssh session, another session to the same host |
| Ctrl+Shift+W | closes the tab shown, ending what runs in it (asking first when something is running); with one tab, closes the window |
| Ctrl+Shift+R | renames the tab shown |
| Ctrl+PgUp, Ctrl+PgDn | the tab before and after the one shown, round past the ends |
| Ctrl+Shift+PgUp, Ctrl+Shift+PgDn | moves the tab shown one place left or right |

With one tab, Ctrl+PgUp and Ctrl+PgDn go to the program, as they did
before tabs, so vim and others still get them.

Every one of these keys can be changed, or given back to the program:
see [Your own keys](#your-own-keys).

**In a tab running tmux control mode** (`tmux -CC`, see
[tmux](tmux.md)), Ctrl+Shift+T and Ctrl+PgUp/PgDn work on tmux's windows,
as before. Use **Ctrl+Alt+PgUp** and **Ctrl+Alt+PgDn** to go to puritty's
tab before or after, or click the bar.

## The bar

While there are two tabs or more, the window's last row is the tab bar
(`[tabs] bar = "always"` shows it with one tab too). Each tab is as wide
as its name, so many short-named tabs fit:

- the tab shown is amber (light gray in the plain look), unless it has a
  color (see [Tab colors](#tab-colors));
- a tab whose program **rang the bell** while you were elsewhere is red,
  with `!` before its name;
- a tab that **printed something** while you were elsewhere has its name
  lit.

A tab's name is the one you gave it, otherwise its host's for an ssh tab,
otherwise the title its program sets, otherwise `shell`.

## Renaming

**Ctrl+Shift+R**, or a **double click** on a tab, asks for its name. Enter
keeps what you typed; Esc leaves the name as it was. A name of one or two
letters makes the tab one or two letters wide. Your name stays when a
program (tmux, vim, a shell's prompt) sets a title; give an empty name to
see the program's title again.

## Tab colors

A host can give its tabs a color, so that a production server's tabs are
red wherever they are in the bar:

```toml
[hosts.prod.colors]
tab = "#c62828"
```

or **Tab** in the host's page of the settings window. Every tab of that
host, the first and those Ctrl+Shift+T opens, takes it, and a change in
the settings recolors them at once.

Any tab can be given a color of its own: **right-click** the tab and
choose **Tab color…**, or Ctrl and the right button in the terminal for
the same menu. The box offers eight colors, keys **1** to **8**, **0** for
none, and in a host's tab **H** for the host's own again; a click on a
color chooses it too. There is no key for it unless you give it one,
`color_tab` in [Your own keys](#your-own-keys).

The tab shown is drawn in its full color with a line along its top; the
others are darker. A colored tab that rang the bell has a red dot at its
end (and `!` before its name), and one that printed a dot in its text's
color.

## Opening a closed tab again

**Ctrl+Alt+Shift+T**, or **Reopen closed tab** in the menu (Ctrl and the
right button, or the right button on a tab), opens again the tab you
closed last: its screen and everything scrolled back, its name and color,
with a new shell in the directory its shell was in, or for an ssh tab a
new session to its host. Press it again for the one closed before that.
A dim line, *(closed, and opened again)*, marks where the old session
ended.

The program that ran in the tab ended when you closed it, as before:
reopening starts a new one, and does not bring back a `vim` or a build.
puritty keeps the last five tabs closed in a window, each for ten minutes.
A tab whose shell you ended with `exit` can be opened again too.

## Opening your tabs again when puritty starts

With **Restore tabs when puritty starts** on (the **Window** page, or
`[tabs] restore = true`), starting `puritty` opens again the windows that
were open when it last ended, each with its tabs in their order: the same
host for an ssh window, which connects every tab at once, or the same
directories for local tabs, with the names and colors you gave them, the
same tab shown, and the window's size. It is off unless you turn it on.

Which windows come back:

- a window that ended with your session (logging out, shutting down) or
  because puritty crashed: always;
- a window you closed with its close button: only if it was the last
  puritty window open, since closing the last one is quitting; one you
  closed while others stayed open is not;
- a window whose last tab you closed, or whose programs all ended: never.

Only a plain `puritty` restores. `puritty --host NAME`, `puritty shell`
and a program on the command line start what they ask for, and a window
started with a program is not kept. When several windows come back,
puritty opens the first and starts `puritty restore` for each of the
others; run by hand, `puritty restore` opens one saved window, or nothing
when none waits. What is kept is in
`~/.local/state/puritty/windows` (`$XDG_STATE_HOME`), or on Windows
`%LOCALAPPDATA%\puritty\windows`, rewritten within five seconds of a
change. A tab's screen and scrollback are not kept, only where it was.

## Closing a busy tab

Closing a tab ends what runs in it, so when something is running puritty
asks first, naming it: a program in front of the tab's shell (a build,
`vim`, `ssh`), or the tab's ssh session while it is open. Enter or the
**Close** button closes it; Esc or **Keep it** keeps it, so a click on
the window's close button can be answered with the mouse too. An idle shell closes without asking. Closing the whole
window asks the same way, listing every busy tab, shown or not. `[tabs]
ask_before_closing = false` never asks.

## Where a new tab starts

A new tab starts in the directory the shown tab's shell is in, as `cd`
left it. On Windows this follows `cmd`'s `cd`; PowerShell's `cd`
(`Set-Location`) does not change it, so a new tab from a PowerShell tab
starts where that PowerShell started.

Click a tab to show it; **middle-click** it to close it (unless
`[tabs] middle_click_closes = false`).

## Settings

In the settings window's **Window** page, or the `[tabs]` table of
`config.toml`:

```toml
[tabs]
bar = "auto"                  # or "always"
look = "puritty"              # or "plain": square tabs, as most terminals
middle_click_closes = true
ask_before_closing = true
restore = false               # true: open the last session's tabs again
```

When a tab's program ends (`exit` in its shell), its tab closes; the
window closes with its last tab. The same holds for an ssh tab whose
remote shell exits.

If an ssh tab's connection drops instead (the network goes, the server
goes away), the tab stays, with its scrollback, and its name on the bar
turns red with `×` before it. Press **R** in it to connect again, or
Enter to close it.

## Your own keys

The keys puritty takes for itself, its tabs' and its copy, paste, search
and settings, are in the settings window's **Keys** page, or the `[keys]`
table of `config.toml`. An empty one gives the key to the program, so that
vim or tmux can have it:

```toml
[keys]
next_tab = "Ctrl+Tab"
previous_tab = "Ctrl+Shift+Tab"
new_tab = "Ctrl+Alt+N"
move_tab_left = ""            # Ctrl+Shift+PageUp goes to the program
```

A key is its modifiers (`Ctrl`, `Shift`, `Alt`, `Super`) and a key joined
by `+`: a letter, a digit, `PageUp`, `PageDown`, `Home`, `End`, `Insert`,
`Delete`, `Tab`, `Enter`, `Space`, the arrows (`Left`, `Up`, ...),
`F1` to `F24`, `Comma`, `Period`, `Slash`, `Minus`, `Plus`, or one
punctuation character. The entries:

| entry | default |
|---|---|
| `new_tab` | Ctrl+Shift+T |
| `close_tab` | Ctrl+Shift+W |
| `rename_tab` | Ctrl+Shift+R |
| `color_tab` | none (the tab's menu has it) |
| `reopen_tab` | Ctrl+Alt+Shift+T |
| `next_tab`, `previous_tab` | Ctrl+PageDown, Ctrl+PageUp |
| `next_tab_always`, `previous_tab_always` | Ctrl+Alt+PageDown, Ctrl+Alt+PageUp (also from a tmux tab) |
| `move_tab_right`, `move_tab_left` | Ctrl+Shift+PageDown, Ctrl+Shift+PageUp |
| `copy`, `paste`, `paste_selection` | Ctrl+Shift+C, Ctrl+Shift+V, Shift+Insert |
| `search` | Ctrl+Shift+F |
| `settings` | Ctrl+Comma |


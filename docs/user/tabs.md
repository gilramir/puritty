# Tabs

*Status: built ([`../tabs.md`](../tabs.md) TB3, TB4, TB6): several
sessions in one window, the keys and your own choice of them, the bar and
its marks, renaming, asking before closing a busy tab, and a new tab in
the same directory.*

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

- the tab shown is amber (light grey in the plain look);
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

## Closing a busy tab

Closing a tab ends what runs in it, so when something is running puritty
asks first, naming it: a program in front of the tab's shell (a build,
`vim`, `ssh`), or the tab's ssh session while it is open. Enter closes it,
Esc keeps it. An idle shell closes without asking. `[tabs]
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
```

When a tab's program ends (`exit` in its shell), its tab closes; the
window closes with its last tab.

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
| `next_tab`, `previous_tab` | Ctrl+PageDown, Ctrl+PageUp |
| `next_tab_always`, `previous_tab_always` | Ctrl+Alt+PageDown, Ctrl+Alt+PageUp (also from a tmux tab) |
| `move_tab_right`, `move_tab_left` | Ctrl+Shift+PageDown, Ctrl+Shift+PageUp |
| `copy`, `paste`, `paste_selection` | Ctrl+Shift+C, Ctrl+Shift+V, Shift+Insert |
| `search` | Ctrl+Shift+F |
| `settings` | Ctrl+Comma |


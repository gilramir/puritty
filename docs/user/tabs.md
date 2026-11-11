# Tabs

*Status: the first step of tabs is built ([`../tabs.md`](../tabs.md)
TB3): several sessions in one window, the keys, the bar and its marks.
Renaming a tab, asking before closing a busy one, opening a new tab in the
same directory, and choosing your own keys come next (TB1).*

A puritty window can hold several sessions, each in its own tab: a local
shell, or an ssh session to one of your hosts. Every tab keeps its own
screen, scrollback, selection and search, and keeps running while another
is shown, so a long build or a log you are following goes on in its tab.

## Keys

| key | does |
|---|---|
| Ctrl+Shift+T | a new tab, after the last. In a tab of an ssh session, another session to the same host |
| Ctrl+Shift+W | closes the tab shown, ending what runs in it; with one tab, closes the window |
| Ctrl+PgUp, Ctrl+PgDn | the tab before and after the one shown, round past the ends |
| Ctrl+Shift+PgUp, Ctrl+Shift+PgDn | moves the tab shown one place left or right |

With one tab, Ctrl+PgUp and Ctrl+PgDn go to the program, as they did
before tabs, so vim and others still get them.

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

A tab's name is its host's for an ssh tab, otherwise the title its program
sets, otherwise `shell`.

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
```

When a tab's program ends (`exit` in its shell), its tab closes; the
window closes with its last tab.

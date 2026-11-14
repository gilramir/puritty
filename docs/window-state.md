# A window's size and place remembered: a survey before the design

Gilbert, 2026-11-14: other terminals seem to remember being full screen
when they were closed and open that way again; puritty on Windows always
opens small, and he mostly wants it full screen. Start with a survey of
what other terminals do, and of complaints about a window placed on a
monitor that is no longer there, which he meets using Omnissa (VMware)
Horizon VDI from a client with two monitors. Section numbers are WP*n*.
Nothing is built.

---

## WP1 · What puritty does today

- **A window opens at `[window] columns` and `rows`** (80 by 24), where
  Windows (`CW_USEDEFAULT`) or the window manager puts it, never
  maximized: `ShowWindow(…, SW_SHOWNORMAL)` on Windows
  (`puritty_win32.c`), and on X11 no `_NET_WM_STATE` is set before
  mapping.
- **Restoring windows** (`[tabs] restore`, `docs/tabs.md` TB10) keeps each
  window's columns and rows with its tabs, but not maximized, full screen,
  position or monitor.
- **A monitor's scale** is followed while the window runs (`WM_DPICHANGED`,
  `docs/windows.md` WS30), not remembered.

## WP2 · What other terminals remember

From their documentation, settings schemas, issue trackers and source
(read 2026-11-14); "not found" where none says.

| terminal | remembers | by default | how |
|---|---|---|---|
| Windows Terminal | nothing; opens at 120×30 cells. With `firstWindowPreference: "persistedWindowLayout"` each window's position, size and launch mode (maximized, full screen) with its tabs | no | `launchMode` (`maximized`, `fullscreen`, `focus`…), `initialPosition` (px), `centerOnLaunch`; the layout in `state.json`. Size and position without the tabs: open request [#12633](https://github.com/microsoft/terminal/issues/12633) (2022); a PR for it ([#20283](https://github.com/microsoft/terminal/pull/20283)) closed unmerged |
| PuTTY | columns and rows of a saved session, when the user saves it | — | position: wishlist priority "never" ([control-window-pos](https://putty.cs.utah.edu/wishlist/control-window-pos.html)); start full screen: open wish |
| KiTTY | position and maximized per session ("Remember Window Positions") | no | registry; restores with `MoveWindow`, no monitor check found |
| SecureCRT | "Save window state for each session" (size, position) | not found | global option |
| ConEmu | normal, maximized or full screen; size in cells, % or px; position; "auto save on exit"; "restore to active monitor" | not found | `ConEmu.xml` |
| WezTerm, Alacritty, GNOME Terminal, xterm | nothing remembered; a start size in cells, and maximized or full screen as a setting (Alacritty `startup_mode`, xterm resources, GNOME `--maximize`) | — | Alacritty declined the request as "pointlessly complicated" ([#8021](https://github.com/alacritty/alacritty/issues/8021)) |
| kitty | size **and maximized** (`remember_window_size`); position of the first window (`remember_window_position`, not on Wayland) | size yes, position no | `~/.cache/kitty/main.json`; **the position is used only if the monitors' work areas are the ones it saved** |
| Ghostty | `window-save-state` on macOS only; on Linux size in cells and `maximize`/`fullscreen` as settings | — | [reference](https://ghostty.org/docs/config/reference) |
| Ptyxis | size in columns and rows, not when maximized, full screen or tiled; no position | yes | GSettings |
| Konsole | size, maximized, and on X11 position and screen | yes | `~/.local/state/konsolestaterc`, **keyed by the screen arrangement** ("2560x1440 screen: Width", "2 screens: XPosition"); size saved only when not maximized |
| Tabby | the normal rectangle and a maximized flag | yes | **centers the window on the nearest display when the saved rectangle does not overlap it** |

So: the terminals people use daily on Windows (Windows Terminal, PuTTY)
remember nothing by default; kitty, Konsole, Ptyxis and Tabby do, and the
three that remember a place all guard against the monitors having changed.

## WP3 · A window placed where no monitor is

- **Windows Terminal**: [#4063](https://github.com/microsoft/terminal/issues/4063)
  (open since 2019), windows off screen on a two-monitor machine after a
  one-screen RDP session; [#9746](https://github.com/microsoft/terminal/issues/9746),
  leaving full screen to the wrong place after the monitors changed;
  [#3187](https://github.com/microsoft/terminal/issues/3187). Its guard
  ([AppHost.cpp](https://github.com/microsoft/terminal/blob/aba31713b5d1184c441c21912d67f1eb0ee35e17/src/cascadia/WindowsTerminal/AppHost.cpp))
  tests one point of the title bar and moves the window to the nearest
  monitor's work area when no monitor holds it.
- **VS Code**, the most careful found
  ([`validateWindowState`](https://github.com/microsoft/vscode/blob/f1cf69d99b6b7fd31d3b5cbb00aad92eef650751/src/vs/platform/windows/electron-main/windows.ts)):
  on one monitor the window is clamped to the work area with at least 128
  pixels showing; on several, a full-screen window goes back to the same
  display; otherwise the saved place is dropped when it does not meet the
  matching display's work area.
- **The same complaint elsewhere**: OBS, MuseScore, WezTerm
  ([#2958](https://github.com/wezterm/wezterm/issues/2958)), and VirtualDub's
  author, who met it mostly with Remote Desktop.
- **Windows' own advice**
  ([Positioning Objects on Multiple Display Monitors](https://learn.microsoft.com/en-us/windows/win32/gdi/positioning-objects-on-multiple-display-monitors)):
  save and restore with `GetWindowPlacement`/`SetWindowPlacement`, "but
  check that the position is still valid… the monitor could have been
  moved or removed", with `MonitorFromRect` and the monitor's work area.
  `SetWindowPlacement` moves a window back only when it would be
  *completely* off screen. Its `rcNormalPosition` is the restored
  rectangle, apart from the maximized state, which is what to save.
- **Windows 11** itself has "Remember window locations based on monitor
  connection" (on by default), for windows that are open when a monitor
  goes, not for a program's next start.

## WP4 · Horizon and Citrix

- The Horizon client keeps a remote desktop's display settings for the next
  connection, and the desktop's monitors follow the client's. Community
  threads report every window moving to the left monitor after a
  reconnect, and the client choosing another monitor as primary; no
  Omnissa article about programs opening off screen was found.
- Citrix documents it ([CTX691686](https://support.citrix.com/external/article/691686/open-applications-on-published-desktops.html)):
  window places saved at disconnect are given up after 10 s of logon, so
  windows land on the primary monitor; a registry timeout on the server
  lengthens it.
- For puritty this means: inside a VDI session the monitors can be
  different at every connection (one, two, another primary, another
  resolution), so a remembered place must be checked against the monitors
  of this start, every start.

## WP5 · X11 and Wayland

- A client asks to start maximized or full screen by setting
  `_NET_WM_STATE_MAXIMIZED_VERT`/`_HORZ` or `_NET_WM_STATE_FULLSCREEN` on
  the window before mapping it, which window managers honor (EWMH); after,
  by a `_NET_WM_STATE` message to the root window. GLFW (kitty) does the
  former.
- The window manager places windows on X11; a client can ask for a place,
  which tiling managers ignore. Under Wayland a client cannot place itself
  at all; `xdg-session-management-v1` (wayland-protocols 1.48, 2026) lets
  a compositor restore places for programs that opt in, KWin first.
  puritty draws through X11, so under a Wayland desktop it is an Xwayland
  window, placed by the compositor.

## WP6 · Options for puritty

**What is remembered:**

- **A.** Nothing more, and a setting to start maximized or full screen:
  `[window] start = "normal" | "maximized" | "fullscreen"`. Alacritty's,
  WezTerm's and Windows Terminal's default way. Simple; never wrong about
  monitors.
- **B.** A as the default way to say it, and the last window's state
  remembered when it is on: maximized or full screen, or else the normal
  size in cells, as kitty and Ptyxis do; no position, so Windows or the
  window manager places it, and nothing can land off screen.
- **C.** B and the position and monitor, as Konsole and Tabby do, checked at
  each start: kept only if the saved rectangle still lies on a monitor's
  work area (Windows: `MonitorFromRect`; X11: RandR's monitors), else
  centered on the nearest monitor; a full-screen or maximized window goes
  to the monitor it was on if that monitor is there, else the nearest.

**What "full screen" is.** Maximized keeps the title bar and the taskbar;
full screen has neither (F11 in Windows Terminal and browsers). puritty has
neither today; both are small on Windows (`ShowWindow(SW_MAXIMIZE)`; full
screen is a borderless window the size of the monitor) and on X11 (the
EWMH states).

**Where it is kept**: beside the recent connections and the saved windows,
in puritty's state folder, not the settings file; with `[tabs] restore` on,
each restored window's own state with its tabs.

## WP7 · Leanings, for Gilbert

1. **B now, C's check whenever a place is used.** A start setting
   (`normal`, `maximized`, `fullscreen`) and the last window's state
   remembered, on by default, as kitty and Konsole do: close maximized,
   open maximized. No position at first: it is what goes wrong under VDI,
   and maximized or full screen needs none but the monitor.
2. **The monitor, checked**: a maximized or full-screen window opens on the
   monitor it was on when that monitor is there (by its rectangle, not its
   number, which changes), else on the one the system gives a new window.
3. **Full screen and maximized both**, with a key for full screen (F11, as
   Windows Terminal; nothing bound by default if F11 should reach
   programs) and the window's menu.
4. **With `[tabs] restore`**, each saved window keeps its own state.

Questions: is maximized what you mean by full screen, or full screen
without the title bar and taskbar? Remember by default, or only when
asked? And should a window's position be remembered at all (C), given
VDI?

## WP8 · Dnene61, Gilbert's answers (2026-11-14)

- **Maximized**, not full screen: the title bar and taskbar stay.
- **The last state is remembered, always**: no setting for it. A window
  closed maximized opens maximized; one closed in its normal size opens at
  that size in cells.
- **No position**, not now: Windows or the window manager places the
  window, so nothing opens where no monitor is.

So WP7's first leaning without its setting, and without full screen. To
build: maximized on Windows (`SW_MAXIMIZE` at the first show) and on X11
(`_NET_WM_STATE_MAXIMIZED_VERT`/`_HORZ` before mapping); the window's
state and normal size noted when it closes, in puritty's state folder;
each window restored with `[tabs] restore` keeps its own.

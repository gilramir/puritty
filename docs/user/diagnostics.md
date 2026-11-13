# The diagnostic log

*Status: built ([`../diagnostics.md`](../diagnostics.md) DG1–DG4): a log
of what each window does, a mark you set when something goes wrong, and
nothing you type, paste or see written in it.*

When puritty does something wrong, the log says what led up to it: the
keys you pressed, the mouse, pastes, what tmux said and what puritty sent
it, the ssh session's steps. You read it where you are, find the part
around the problem, and pass on only those lines.

## What is never in it

The log is written so that it can be read at work and its lines passed
on:

- **A key that types text is written as `text`**, never the letter. Keys
  that type nothing are written by name: `Enter`, `Ctrl+C`, `Shift+Up`.
- **A paste is written by its size**: `734 bytes, 12 lines, bracketed`.
- **What a program prints is written by its size**: `output %1 80 bytes`.
- **tmux commands carrying text are counted**: `send-keys -t '%1' -H <256
  bytes>`, and any quoted argument that is not an id, a key's name or a
  format as `<45 chars>`: what you answer at a prompt (a search, a new
  name) is not written.
- **Passwords and the answers to ssh's questions are not written**: only
  that a question was asked.

What it does have: host and tmux session ids, window sizes, the names of
settings, tmux's own messages and errors, and the time.

## Turning it on

In the settings (Ctrl+Comma), **Advanced → Diagnostic log**, or in the
file:

```toml
[debug]
log = true
```

It takes effect at once, in every open window: each begins a file of its
own. Turning it off ends them. Leave it off when you are not chasing a
problem; it costs little, but it writes as you work.

The files are in:

| | |
|---|---|
| Windows | `%LOCALAPPDATA%\puritty\logs` |
| Linux | `~/.local/state/puritty/logs` (or `$XDG_STATE_HOME/puritty/logs`) |

Each is named by when its window began,
`puritty-2026-11-12_140533-120.log`. The newest twenty are kept; older
ones are removed as new ones begin.

## Marking the moment

When something goes wrong, press **Ctrl+Alt+Shift+M** at once, or choose
**Mark the diagnostic log** in puritty's menu (Ctrl+right-click, or a
right-click on a tab in the bar; on Windows also the window's system
menu, at its icon). The key and the item are there only while the log
is on. It writes a numbered
mark with the window's state, the things that decide where keys,
pastes and the mouse go:

```
000174 11:07:45.042 mark   ==================== MARK 1 ====================
000175 11:07:45.042 mark   tab 0 shown of 1, no host
000176 11:07:45.042 mark   focus on, buttons held 0, shift on
000177 11:07:45.042 mark   paste asked off, paste under way no
...
000182 11:07:45.042 mark   tmux control mode: on, window @1, active pane %1
000183 11:07:45.042 mark     key table root, keys by table (send-keys -K)
000184 11:07:45.042 mark     waiting for 0 replies
000188 11:07:45.042 mark     pane %1 (active): paste-brackets on, focus-reports on, mouse off, alt-screen off, app-cursor off, size 100x29
000189 11:07:45.042 mark   ==================== END OF MARK 1 =============
```

Press it again after trying something (a key that did nothing, a paste)
and the lines between the two marks are what happened.

## Reading it

Each line is its number, the time, a tag and what happened:

```
000138 11:07:42.660 mouse  press right at row 5 col 30
000139 11:07:42.660 paste  asked from the selection (primary)
000142 11:07:42.660 paste  734 bytes, 12 lines, bracketed, in one piece, sent 746 bytes to tmux's active pane
000143 11:07:42.660 tmux>  send-keys -t '%1' -H <256 bytes>
000146 11:07:42.662 tmux<  reply #373 ok, 0 lines, 0 bytes, for nothing (a reply not read)
000149 11:07:42.662 tmux<  output %1 80 bytes
```

| tag | what |
|---|---|
| `start` | the window as the log began |
| `key` | a key pressed (`text` for one that types) |
| `mouse` | a button pressed or released, and the cell |
| `paste` | a paste asked for, and what was sent |
| `window` | focus, size, a monitor's scale, close |
| `ime` | the input method's commits (by length) |
| `tab` | the tab shown |
| `ssh` | the built-in ssh client's steps |
| `read` | bytes read from the program (without tmux) |
| `tmux>` | a command puritty sent tmux |
| `tmux<` | what tmux said: notifications, replies, output by size |
| `mark` | a mark and the state with it |
| `error`, `end` | the log's own troubles, and its end |

## Passing on a part of it

The lines worth sending are usually the mark and the twenty or thirty
lines before it. On Windows, in PowerShell:

```powershell
# the newest log
$log = Get-ChildItem "$env:LOCALAPPDATA\puritty\logs" | Sort-Object LastWriteTime | Select-Object -Last 1
# where the marks are
Select-String -Path $log.FullName -Pattern "MARK" | Select-Object LineNumber, Line
# the 30 lines before mark 1, and the mark
Select-String -Path $log.FullName -Pattern "= MARK 1 =" -Context 30,16
# lines 1200 to 1240
Get-Content $log.FullName | Select-Object -Skip 1199 -First 41
# only tmux's errors
Select-String -Path $log.FullName -Pattern "ERROR"
```

On Linux:

```sh
log=$(ls -t ~/.local/state/puritty/logs/*.log | head -1)
grep -n MARK "$log"
grep -B30 -A16 '= MARK 1 =' "$log"
sed -n 1200,1240p "$log"
```

Whoever helps you can then ask for a range by its numbers ("lines 900
to 960"), or for every line with a tag, and you can look at each before
it goes.

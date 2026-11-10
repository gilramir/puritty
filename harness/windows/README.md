# Running things on a Windows machine from Linux

Gilbert's Windows 11 machine, `beelink1`, takes ssh from nene with the
`home-lateral` key (OpenSSH server, PowerShell 5.1 as its shell). Files go
with `scp` to `C:\Users\yosup\geng-probe\`; programs run with `ssh beelink1
'...'`. Run a script there with `powershell -NoProfile -ExecutionPolicy
Bypass -File`, since the machine's policy refuses unsigned scripts.

An ssh session cannot show a window. `inSession.ps1` starts a program, or a
PowerShell script, in the logged-on user's desktop session through a
scheduled task with an interactive logon:

    powershell -NoProfile -ExecutionPolicy Bypass -File inSession.ps1 -Exe notepad.exe
    powershell -NoProfile -ExecutionPolicy Bypass -File inSession.ps1 -Script C:\Users\yosup\geng-probe\shot.ps1

`shot.ps1`, run that way, writes the whole desktop to `shot.png` beside it
(and `shot.log`, "ok" or the error), which `scp` brings back. It needs the
user logged in with the screen unlocked.

Lessons from setting it up (2026-11-09): `$Args` is PowerShell's own
variable, so a parameter of that name carries nothing; a value that starts
with `-` does not pass cleanly through `powershell -File`; a task still
running refuses a second start of the same task (0x800710E0), so each call
registers a task of its own name; and unregistering a task right after
starting it can cancel the start.

"""usage: remember.py (after app/build-windows.sh, and packages/ssh/tests/sshd.py has made its keys)

A remembered passphrase on beelink1 (docs/saved-secrets.md PW8): puritty.exe
--host test (client built-in) logging in to nene's test sshd with the
passphrase-protected test key, in the desktop session (Credential Manager
refuses an ssh logon, PW3), keys typed by SendKeys:

0. the passphrase typed, Tab to the checkbox, Space: the box pictured
   (shot.png beside this script's work, `.harness-work/remember/`) with
   the checkbox ticked and focused, the field without its caret; then
   closed;
1. the passphrase typed, Tab to the checkbox, Space to tick it, Enter
   (PW10): logged in, exit 0, and Credential Manager holds
   puritty:key:PATH;
2. nothing typed: logged in from the remembered one;
3. a wrong one put in its place (cmdkey): asked again, the box saying it
   was refused, Remember checked; the right one typed, Enter;
4. nothing typed: logged in from the one remembered in run 3.

Then the credential, the files and the scheduled task removed."""
import getpass, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, "/home/gram/prj/puritty/packages/ssh/tests")
sys.path.insert(0, "/home/gram/prj/puritty/harness")
import sshd

ROOT = Path("/home/gram/prj/puritty")
D = r"C:\Users\yosup\geng-probe\remember"
KEY = D + r"\home\.ssh\id_test"
TARGET = "puritty:key:" + KEY


def ps(cmd, timeout=180):
    r = subprocess.run(["ssh", "beelink1", cmd], capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


RUN = r"""
param([string]$Keys, [string]$Tag)
$d = '__D__'
Start-Transcript -Append -Path "$d\transcript.txt" | Out-Null
$env:APPDATA = "$d\appdata"; $env:LOCALAPPDATA = "$d\local"; $env:HOME = "$d\home"
Remove-Item Env:SSH_AUTH_SOCK -ErrorAction SilentlyContinue
$p = Start-Process "$d\puritty.exe" -ArgumentList "--host","test" -PassThru
$null = $p.Handle
$sh = New-Object -ComObject WScript.Shell
if ($Keys -ne '') {
  Start-Sleep 4
  # keys only into puritty: never once it has ended, or when it is not the
  # window in front, where they would reach the user's own windows
  foreach ($k in $Keys.Split('|')) {
    if ($p.HasExited -or -not $sh.AppActivate($p.Id)) { "$Tag keys stopped: puritty ended or not in front" | Out-File -Append "$d\result.txt"; break }
    Start-Sleep -Milliseconds 300
    $sh.SendKeys($k); Start-Sleep -Milliseconds 700
  }
}
if ($Tag -like '*shot*') {
  Start-Sleep 1
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\geng-probe\shot.ps1"
  Copy-Item "$env:USERPROFILE\geng-probe\shot.png" "$d\shot.png"
  & taskkill.exe /T /F /PID $p.Id | Out-Null
}
if (-not $p.WaitForExit(30000)) { & taskkill.exe /T /F /PID $p.Id | Out-Null; $s = 'did not end' } else { $s = $p.ExitCode }
$listed = ((cmdkey /list | Select-String 'puritty:key') -join ' ').Trim()
"$Tag exit: $s; credential: $listed" | Out-File -Append "$d\result.txt"
"done" | Out-File "$d\done-$Tag.txt"
Stop-Transcript | Out-Null
"""


DESK = r"""
param([string]$Command, [string]$Tag)
$d = '__D__'
Invoke-Expression $Command 2>&1 | Out-Null
"$Tag credential: " + (((cmdkey /list | Select-String 'puritty:key') -join ' ').Trim()) | Out-File -Append "$d\result.txt"
"done" | Out-File "$d\done-$Tag.txt"
"""


def on_desktop(command, tag):
    """cmdkey run in the desktop session: an ssh logon's Credential Manager
    is not the one puritty uses there (PW3), so a cmdkey over ssh neither
    sees nor changes what puritty stored."""
    ps(rf"Remove-Item {D}\done-{tag}.txt -ErrorAction SilentlyContinue")
    ps(rf"Set-Content {D}\desk-{tag}.ps1 '& ''{D}\desk.ps1'' -Command ''{command}'' -Tag {tag}'")
    ps(rf"powershell -NoProfile -ExecutionPolicy Bypass -File $env:USERPROFILE\geng-probe\inSession.ps1 -Script {D}\desk-{tag}.ps1")
    end = time.time() + 60
    while time.time() < end:
        if "True" in ps(rf"Test-Path {D}\done-{tag}.txt"):
            return
        time.sleep(2)
    print(f"{tag}: no result in 60 s")


def in_session(keys, tag):
    ps(rf"Remove-Item {D}\done-{tag}.txt -ErrorAction SilentlyContinue")
    # inSession.ps1 takes a script with no arguments: a wrapper a run
    # (in a single-quoted PowerShell string a quote is written twice)
    ps(rf"Set-Content {D}\run-{tag}.ps1 '& ''{D}\run.ps1'' -Keys ''{keys}'' -Tag {tag}'")
    ps(rf"powershell -NoProfile -ExecutionPolicy Bypass -File $env:USERPROFILE\geng-probe\inSession.ps1 -Script {D}\run-{tag}.ps1")
    end = time.time() + 90
    while time.time() < end:
        if "True" in ps(rf"Test-Path {D}\done-{tag}.txt"):
            return
        time.sleep(3)
    print(f"{tag}: no result in 90 s")


keys = sshd.user_keys()[0]
server = sshd.Server(["ListenAddress 192.168.1.99"])
try:
    work = ROOT / ".harness-work" / "remember"
    work.mkdir(parents=True, exist_ok=True)
    (work / "config.toml").write_text(
        f'[hosts.test]\nhost = "192.168.1.99"\nport = {server.port}\nuser = "{getpass.getuser()}"\n'
        f'identity = "{KEY.replace(chr(92), chr(92) * 2)}"\nclient = "built-in"\ncommand = "exit 0"\n'
        + ('[debug]\nlog = true\n' if "--log" in sys.argv else ''))
    (work / "sshconfig").write_text("StrictHostKeyChecking accept-new\n")
    (work / "run.ps1").write_text(RUN.replace("__D__", D))
    (work / "desk.ps1").write_text(DESK.replace("__D__", D))
    print(ps(rf"New-Item -ItemType Directory -Force {D}\appdata\puritty,{D}\local,{D}\home\.ssh | Out-Null; 'made'"))
    subprocess.run(["scp", "-q", str(ROOT / "app" / "puritty.exe"), str(work / "run.ps1"), str(work / "desk.ps1"), "beelink1:geng-probe/remember/"], check=True)
    subprocess.run(["scp", "-q", str(work / "config.toml"), "beelink1:geng-probe/remember/appdata/puritty/config.toml"], check=True)
    subprocess.run(["scp", "-q", str(work / "sshconfig"), "beelink1:geng-probe/remember/home/.ssh/config"], check=True)
    subprocess.run(["scp", "-q", keys["ecdsa521"], "beelink1:geng-probe/remember/home/.ssh/id_test"], check=True)
    print(ps(rf"icacls {KEY} /inheritance:r /grant:r ""$env:USERNAME`:F"" | Out-Null; 'key ok'"))
    # a credential left by an earlier run would log in unasked
    on_desktop(f"cmdkey /delete:{TARGET}", "0-cleared")
    in_session("hunter2|{TAB}| ", "0-shot")
    subprocess.run(["scp", "-q", "beelink1:geng-probe/remember/shot.png", str(work / "shot.png")])
    in_session("hunter2|{TAB}| |{ENTER}", "1-typed-remembered")
    if "--first" in sys.argv:
        print(ps(rf"Get-Content {D}\result.txt; Get-Content {D}\transcript.txt | Select-Object -Last 15"))
        on_desktop(f"cmdkey /delete:{TARGET}", "cleared")
        print(ps(rf"Get-Content {D}\result.txt | Select-Object -Last 1"))
        print(ps(rf"Get-ChildItem {D}\local\puritty\logs -ErrorAction SilentlyContinue | ForEach-Object {{ Get-Content $_.FullName | Select-String -Pattern 'ssh|asked|remember|credential|passphrase|key' | Select-Object -First 40 }}"))
        raise SystemExit
    in_session("", "2-from-store")
    # a wrong one in its place (cmdkey keeps it as UTF-16, so it is wrong
    # whatever it says)
    on_desktop(f"cmdkey /generic:{TARGET} /user:x /pass:wrong", "3-replaced-by-a-wrong-one")
    in_session("hunter2|{ENTER}", "3-refused-asked-again")
    in_session("", "4-from-store-again")
    on_desktop(f"cmdkey /delete:{TARGET}", "5-cleared")
    print(ps(rf"Get-Content {D}\result.txt"))
finally:
    # the desktop's Credential Manager emptied of the test's, whatever failed
    try:
        on_desktop(f"cmdkey /delete:{TARGET}", "end-cleared")
        print(ps(rf"Get-Content {D}\result.txt | Select-Object -Last 1"))
    except Exception as e:
        print("could not clear the desktop's credential:", e)
    print(ps(rf"cmdkey /delete:{TARGET} 2>&1 | Out-Null; Get-Process puritty -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{D}*' }} | Stop-Process; "
             rf"Remove-Item -Recurse -Force {D}; Get-ScheduledTask | Where-Object TaskName -like 'geng*' | ForEach-Object {{ Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false }}; "
             rf"'left: ' + ((cmdkey /list | Select-String 'puritty') -join ' ') + ' folder ' + (Test-Path {D})"))
    server.stop()

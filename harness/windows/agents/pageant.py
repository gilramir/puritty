"""usage: pageant.py WORK (after app/build-windows.sh and packages/ssh/tests/sshd.py has made its keys)

Pageant on beelink1: pageant.exe with a test key, then puritty.exe
--host test (client built-in) logging in to nene's test sshd through
Pageant's pipe, which puritty names as PuTTY does; puritty's exit status
is the command's."""
import getpass, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/home/gram/prj/puritty/packages/ssh/tests")
import sshd
# a work directory, and the test key as PuTTY's PPK, made with puttygen:
#   puttygen .harness-work/ssh/userkeys/ed -O private -o WORK/pageant/ed.ppk
S = Path(sys.argv[1])
server = sshd.Server(["ListenAddress 192.168.1.99"])
D = r"C:\Users\yosup\geng-probe\pageant"
def ps(cmd):
    r = subprocess.run(["ssh", "beelink1", cmd], capture_output=True, text=True, timeout=180)
    return (r.stdout + r.stderr).strip()
try:
    (S / "pageant" / "config.toml").write_text(
        f'[hosts.test]\nhost = "192.168.1.99"\nport = {server.port}\nuser = "{getpass.getuser()}"\nclient = "built-in"\ncommand = "exit 7"\n')
    (S / "pageant" / "sshconfig").write_text("StrictHostKeyChecking accept-new\n")
    print(ps(rf"New-Item -ItemType Directory -Force {D}\appdata\puritty,{D}\home\.ssh | Out-Null; Invoke-WebRequest -UseBasicParsing https://the.earth.li/~sgtatham/putty/latest/w64/pageant.exe -OutFile {D}\pageant.exe; (Get-AuthenticodeSignature {D}\pageant.exe).Status"))
    subprocess.run(["scp", "-q", "/home/gram/prj/puritty/app/puritty.exe", str(S / "pageant" / "ed.ppk"), "beelink1:geng-probe/pageant/"], check=True)
    subprocess.run(["scp", "-q", str(S / "pageant" / "config.toml"), "beelink1:geng-probe/pageant/appdata/puritty/config.toml"], check=True)
    subprocess.run(["scp", "-q", str(S / "pageant" / "sshconfig"), "beelink1:geng-probe/pageant/home/.ssh/config"], check=True)
    print(ps(rf"""$d = '{D}'; $env:APPDATA = "$d\appdata"; $env:HOME = "$d\home"; Remove-Item Env:SSH_AUTH_SOCK -ErrorAction SilentlyContinue
$pg = Start-Process "$d\pageant.exe" -ArgumentList "$d\ed.ppk" -PassThru; Start-Sleep 3
'pipes: ' + ((Get-ChildItem \\.\pipe\ | Where-Object Name -like 'pageant*' | ForEach-Object Name) -join ', ')
'openssh agent: ' + (Get-Service ssh-agent).Status
$p = Start-Process "$d\puritty.exe" -ArgumentList "--host","test" -PassThru -RedirectStandardError "$d\err.txt"; $null = $p.Handle
if (-not $p.WaitForExit(40000)) {{ & taskkill.exe /T /F /PID $p.Id | Out-Null; 'puritty: did not end' }} else {{ 'puritty exit status: ' + $p.ExitCode }}
'known_hosts: ' + (Test-Path "$d\home\.ssh\known_hosts")
Get-Content "$d\err.txt" -ErrorAction SilentlyContinue
Stop-Process -Id $pg.Id"""))
finally:
    print(ps(rf"Start-Sleep 1; Remove-Item -Recurse -Force {D}; 'cleaned'"))
    server.stop()

# A look at puritty itself on Windows (docs/windows.md WS20), in the desktop
# session (harness/windows/inSession.ps1): starts puritty.exe with its
# arguments, drives it with drive.exe through the case (its shot actions
# write pictures beside this script), and writes what the driver said, and
# puritty's exit, to app.log. Not a gate: the pictures are looked at.
param([string]$Case = "shell.case", [string]$AppArgs = "")
Set-Location $PSScriptRoot
[Environment]::CurrentDirectory = $PSScriptRoot
Remove-Item app.log,app-done.txt,*.bmp -ErrorAction SilentlyContinue
if ($AppArgs) {
    $p = Start-Process -FilePath .\puritty.exe -ArgumentList $AppArgs -PassThru -RedirectStandardError app-stderr.txt
} else {
    $p = Start-Process -FilePath .\puritty.exe -PassThru -RedirectStandardError app-stderr.txt
}
$d = Start-Process -FilePath .\drive.exe -ArgumentList "`"$Case`"","--any" -PassThru -Wait -NoNewWindow -RedirectStandardError drive.txt
Add-Content app.log (Get-Content drive.txt)
Add-Content app.log "drive exit $($d.ExitCode)"
if ($p.WaitForExit(15000)) { Add-Content app.log "puritty exit $($p.ExitCode)" }
else { Stop-Process -Id $p.Id -Force; Add-Content app.log "puritty did not end; stopped" }
Add-Content app.log (Get-Content app-stderr.txt)
Set-Content app-done.txt "done"

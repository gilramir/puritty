# The events gate's run on Windows (harness/events.py), in the desktop
# session (harness/windows/inSession.ps1): for each case in cases\, starts
# core-events.exe with the case's mode, drives it with drive.exe, and keeps
# the program's log as logs\CASE.txt and what the driver said as
# logs\CASE.drive. A program still running 15 seconds after its driver is
# stopped by its own PID. done.txt is written last.
Set-Location $PSScriptRoot
[Environment]::CurrentDirectory = $PSScriptRoot
$env:PURITTY_DPI = "96"
Remove-Item -Recurse -Force logs,*.bmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory logs | Out-Null
foreach ($case in Get-ChildItem cases -Filter *.case | Sort-Object Name) {
    $name = $case.BaseName
    $mode = ""
    foreach ($line in Get-Content $case.FullName) { if ($line -match '^mode (.*)$') { $mode = $Matches[1] } }
    $log = Join-Path $PSScriptRoot "logs\$name.txt"
    $argList = @("`"$log`"")
    if ($mode) { $argList += $mode }
    $p = Start-Process -FilePath .\core-events.exe -ArgumentList $argList -PassThru -WindowStyle Normal
    $d = Start-Process -FilePath .\drive.exe -ArgumentList "`"$($case.FullName)`"" -PassThru -Wait -NoNewWindow `
        -RedirectStandardError "logs\$name.drive"
    Add-Content "logs\$name.drive" "exit $($d.ExitCode)"
    if (-not $p.WaitForExit(15000)) {
        Stop-Process -Id $p.Id -Force
        Add-Content "logs\$name.drive" "the program did not end; stopped"
    }
}
Set-Content done.txt "done"

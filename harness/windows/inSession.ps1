# Starts a program, or a PowerShell script, in the logged-on user's desktop
# session through a scheduled task of its own name. An ssh session cannot
# show a window; a task with an interactive logon runs where the user sees.
#   inSession.ps1 -Exe notepad.exe
#   inSession.ps1 -Script C:\path\shot.ps1
param([string]$Exe = "", [string]$Script = "", [string]$ExeArgs = "")
Get-ScheduledTask -TaskName "geng-in-session-*" -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
$name = "geng-in-session-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$p = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
if ($Script) {
    $a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ("-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"" + $Script + "`"")
} elseif ($ExeArgs) {
    $a = New-ScheduledTaskAction -Execute $Exe -Argument $ExeArgs
} else {
    $a = New-ScheduledTaskAction -Execute $Exe
}
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances Parallel
Register-ScheduledTask -TaskName $name -Action $a -Principal $p -Settings $s -Force | Out-Null
Start-ScheduledTask -TaskName $name

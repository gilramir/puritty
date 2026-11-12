# One workload in puritty, maximized, with PURITTY_STATS (docs/windows.md
# WS26): render-one.ps1 NAME BLAST-ARGS... (run in the desktop session)
param([string]$Name, [string]$Mode, [string]$Arg)
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W2 { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd); }
"@
$cmd = @("$dir\blast.exe", $Mode, $Arg, "$dir\one-$Name.tsv", "4")
$toml = "[program]`r`ncommand = [" + (($cmd | ForEach-Object { '"' + ($_ -replace '\\', '/') + '"' }) -join ", ") + "]`r`n"
Set-Content -Path "$dir\one.toml" -Value $toml
$env:PURITTY_STATS = "1"
if ($env:RENDER_GC) { $env:GC_PRINT_STATS = "1" }
$p = Start-Process -FilePath "C:\Users\yosup\puritty\puritty.exe" -ArgumentList "shell", "--config", "$dir\one.toml" -PassThru -RedirectStandardError "$dir\one-stats-$Name.txt"
Start-Sleep -Milliseconds 1500
$p.Refresh(); [W2]::ShowWindow($p.MainWindowHandle, 3) | Out-Null
if (-not $p.WaitForExit(240000)) { Stop-Process -Id $p.Id }
"done" | Out-File "$dir\one-done-$Name.txt"

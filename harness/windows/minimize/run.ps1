# puritty minimized and restored by ShowWindow (no keys), the desktop
# pictured before and after (docs/windows.md WS31)
param([string]$Exe, [string]$Tag)
$d = "$env:USERPROFILE\geng-probe\minimize"
Add-Type -Name W -Namespace U -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);'
$env:APPDATA = "$d\appdata"; $env:LOCALAPPDATA = "$d\local"
$p = Start-Process "$d\$Exe" -ArgumentList "cmd.exe","/c","$d\lines.cmd" -PassThru
Start-Sleep 5
$p.Refresh(); $h = $p.MainWindowHandle
"$Tag window $h" | Out-File -Append "$d\result.txt"
if ($h -ne 0) {
  [U.W]::SetForegroundWindow($h) | Out-Null; Start-Sleep 1
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\geng-probe\shot.ps1"
  Copy-Item "$env:USERPROFILE\geng-probe\shot.png" "$d\$Tag-before.png"
  [U.W]::ShowWindow($h, 6) | Out-Null; Start-Sleep 2
  [U.W]::ShowWindow($h, 9) | Out-Null; [U.W]::SetForegroundWindow($h) | Out-Null; Start-Sleep 2
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\geng-probe\shot.ps1"
  Copy-Item "$env:USERPROFILE\geng-probe\shot.png" "$d\$Tag-after.png"
}
& taskkill.exe /T /F /PID $p.Id | Out-Null
"done" | Out-File "$d\done-$Tag.txt"

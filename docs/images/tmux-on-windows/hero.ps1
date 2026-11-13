# The site's hero picture (puritty docs/images/tmux-on-windows.png): puritty
# with three restored ssh tabs to nene, the first attached to tmux 3.8 by
# tmux -CC, centered on the desktop and taken with a margin. Run in the
# desktop session by inSession.ps1. Everything is under $base; only the
# puritty started here is ended, by its id, and only by stop.ps1.
$ErrorActionPreference = 'Stop'
$base = "C:\Users\yosup\geng-probe\hero"
$log = "$base\log.txt"
try {
Set-Content $log "start"
$env:LOCALAPPDATA = "$base\local"
$state = "$base\local\puritty\windows"
New-Item -ItemType Directory -Force $state | Out-Null
Get-ChildItem $state | Remove-Item -Force
Copy-Item "$base\saved.toml" "$state\0000000000000001.toml"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -Name W -Namespace Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int cmd);
[DllImport("user32.dll")] public static extern bool MoveWindow(System.IntPtr h, int x, int y, int w, int hh, bool repaint);
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
[DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(System.IntPtr h, int attr, out RECT r, int size);
'@
[Win.W]::SetProcessDPIAware() | Out-Null
$p = Start-Process -FilePath "$base\puritty.exe" -ArgumentList @("--config", "$base\hero.toml") -PassThru
$p.Id | Out-File "$base\pid.txt"
Start-Sleep 8
$p.Refresh(); $h = $p.MainWindowHandle
[Win.W]::ShowWindow($h, 9) | Out-Null
$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$nw = 1640; $nh = 1139
[Win.W]::MoveWindow($h, $wa.Left + [int](($wa.Width - $nw) / 2), $wa.Top + [int](($wa.Height - $nh) / 2), $nw, $nh, $true) | Out-Null
Start-Sleep 2
[Win.W]::SetForegroundWindow($h) | Out-Null
Start-Sleep 1
# each tab shown once, so that none is marked for printing while away;
# Ctrl+Alt+PgDn goes round to the first again
foreach ($i in 1..3) { [System.Windows.Forms.SendKeys]::SendWait("^%{PGDN}"); Start-Sleep 1 }
[System.Windows.Forms.SendKeys]::SendWait("/nix/store/k111lnbq1vw0k4v4cjhi1iwp5lky3ryn-tmux-3.8/bin/tmux -L puritty-shot -CC attach -t shot{ENTER}")
Start-Sleep 6
$r = New-Object Win.W+RECT
[Win.W]::DwmGetWindowAttribute($h, 9, [ref]$r, 16) | Out-Null
$m = 60
$s = [System.Windows.Forms.SystemInformation]::VirtualScreen
$x = [Math]::Max($s.Left, $r.L - $m); $y = [Math]::Max($s.Top, $r.T - $m)
$w = [Math]::Min($s.Right, $r.R + $m) - $x; $hh = [Math]::Min($s.Bottom, $r.B + $m) - $y
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
$bmp.Save("$base\hero.png", [System.Drawing.Imaging.ImageFormat]::Png)
$full = New-Object System.Drawing.Bitmap $s.Width, $s.Height
$g2 = [System.Drawing.Graphics]::FromImage($full)
$g2.CopyFromScreen($s.Left, $s.Top, 0, 0, $full.Size)
$full.Save("$base\desktop.png", [System.Drawing.Imaging.ImageFormat]::Png)
Add-Content $log "ok window $($r.L),$($r.T) $($r.R - $r.L)x$($r.B - $r.T), screen $($s.Width)x$($s.Height), taken $x,$y ${w}x$hh"
} catch { $_ | Out-String | Add-Content $log }

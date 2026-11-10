$ErrorActionPreference = 'Stop'
try {
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
$bmp.Save("$env:USERPROFILE\geng-probe\shot.png", [System.Drawing.Imaging.ImageFormat]::Png)
"ok" | Out-File "$env:USERPROFILE\geng-probe\shot.log"
} catch { $_ | Out-String | Out-File "$env:USERPROFILE\geng-probe\shot.log" }

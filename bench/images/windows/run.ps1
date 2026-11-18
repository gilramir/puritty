# bench/images/windows.py's side on Windows: puritty.exe started with the
# host in config.toml beside this script (its built-in ssh client to a tmux
# on the Linux machine that drives the run), and each frame's picture
# written to shot.ppm (PURITTY_SHOT). The Linux side asks for a picture by
# writing want.txt here with a step's name; this copies shot.ppm to
# out\NAME.ppm and deletes want.txt. stop.txt ends the run.
param([string]$Host_ = "nene", [string]$Mode = "plain")
Set-Location $PSScriptRoot
$out = Join-Path $PSScriptRoot "out"
New-Item -ItemType Directory -Force $out | Out-Null
$case = Join-Path $PSScriptRoot "appdata"
New-Item -ItemType Directory -Force (Join-Path $case "puritty") | Out-Null
Copy-Item (Join-Path $PSScriptRoot "config-$Mode.toml") (Join-Path $case "puritty\config.toml") -Force
$env:APPDATA = $case
$env:PURITTY_DPI = "120"
$env:PURITTY_SHOT = Join-Path $PSScriptRoot "shot.ppm"
Remove-Item $env:PURITTY_SHOT, (Join-Path $PSScriptRoot "want.txt"), (Join-Path $PSScriptRoot "stop.txt") -ErrorAction SilentlyContinue
$p = Start-Process -FilePath (Join-Path $PSScriptRoot "puritty.exe") -ArgumentList @("--host", $Host_) -PassThru -RedirectStandardError (Join-Path $out "stderr-$Mode.txt")
"started $($p.Id)"
$deadline = (Get-Date).AddMinutes(15)
while ((Get-Date) -lt $deadline) {
    if (Test-Path (Join-Path $PSScriptRoot "stop.txt")) { break }
    $want = Join-Path $PSScriptRoot "want.txt"
    if (Test-Path $want) {
        $name = (Get-Content $want -Raw).Trim()
        Start-Sleep -Milliseconds 300
        if (Test-Path $env:PURITTY_SHOT) { Copy-Item $env:PURITTY_SHOT (Join-Path $out "$name.ppm") -Force }
        $alive = -not $p.HasExited
        "$name alive=$alive" | Out-File -Append (Join-Path $out "steps-$Mode.txt")
        Remove-Item $want
    }
    Start-Sleep -Milliseconds 200
}
& taskkill.exe /T /F /PID $p.Id 2>&1 | Out-Null
"stopped"

# The pixel gate's run on Windows (harness/pixels.py --windows): each line
# of runs.tsv beside this script is a case's data, the picture to write,
# and core-pixels.exe's settings, tab-separated; the fonts are in fonts\.
# What each run says on stderr is kept in faces.txt, its lines after the
# case's name; a run that fails says so there too.
param([string]$Fallback = "", [switch]$Faces)
Set-Location $PSScriptRoot
$env:PURITTY_FONT_DIRS = (Resolve-Path fonts).Path
$env:PURITTY_DPI = "96"
$env:PURITTY_FALLBACK = $Fallback
if ($Faces) { $env:PURITTY_STATS = "1" } else { Remove-Item Env:PURITTY_STATS -ErrorAction SilentlyContinue }
$log = New-Object System.Collections.Generic.List[string]
foreach ($line in Get-Content -Encoding UTF8 runs.tsv) {
    if (-not $line) { continue }
    $f = $line.Split("`t")
    $name = [IO.Path]::GetFileNameWithoutExtension($f[0])
    # an empty argument must reach the program as one: PowerShell 5.1
    # drops "" unless it is written as '""'
    $lang = if ($f[6]) { $f[6] } else { '""' }
    $breaks = if ($f[7]) { $f[7] } else { '""' }
    # a ui case's interface font, tenth; terminal cases have none
    if ($f.Length -gt 9 -and $f[9]) {
        $out = & .\core-pixels.exe $f[2] $f[3] $f[0] $f[1] $f[4] $f[5] $lang $breaks $f[8] $f[9] 2>&1
    } else {
        $out = & .\core-pixels.exe $f[2] $f[3] $f[0] $f[1] $f[4] $f[5] $lang $breaks $f[8] 2>&1
    }
    $code = $LASTEXITCODE
    foreach ($o in $out) { if ($f[1] -notlike "*.once.ppm") { $log.Add("$name`t$o") } }
    if ($code -ne 0) { $log.Add("$name`tFAILED $code") }
}
[IO.File]::WriteAllLines((Join-Path $PSScriptRoot "faces.txt"), $log)

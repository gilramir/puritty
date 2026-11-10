# The reload gate's run on Windows (harness/reload.py --windows): each line
# of cases.tsv beside this script is a case's name, how its file is
# rewritten (in place, rename, remove) and whether a fresh start is
# pictured too. NAME.before.toml and NAME.after.toml are its files. Each
# puritty.exe runs with %APPDATA% a directory of the case's own, and
# PURITTY_SHOT, the file each frame's picture is written to; what comes
# back is in out\: NAME.first.ppm before the change, NAME.got.ppm after it,
# NAME.fresh.ppm from a fresh start, the window's title after the change,
# and what puritty said on standard error.
Set-Location $PSScriptRoot
[Environment]::CurrentDirectory = $PSScriptRoot
$out = Join-Path $PSScriptRoot "out"
New-Item -ItemType Directory -Force $out | Out-Null
$env:PURITTY_DPI = "96"
# the screen written as UTF-8: cmd's `type` writes through the console's
# code page whatever `chcp` set before it in the same command
$program = @("--", "powershell.exe", "-NoProfile", "-Command", '"[Console]::OutputEncoding = [Text.Encoding]::UTF8; [Console]::Write([IO.File]::ReadAllText(''screen.txt'')); Start-Sleep 600"')

# The window's title, by its class: a window in the ssh session's window
# station is no process's main window, so MainWindowTitle is empty.
Add-Type -Namespace Reload -Name User32 -MemberDefinition @'
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string name);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr w, System.Text.StringBuilder s, int n);
'@
function Get-Title {
    # [NullString]::Value: PowerShell hands a string parameter $null as ""
    $w = [Reload.User32]::FindWindowW("puritty", [NullString]::Value)
    $s = New-Object System.Text.StringBuilder 512
    [Reload.User32]::GetWindowTextW($w, $s, 512) | Out-Null
    return $s.ToString()
}

function Start-Puritty($case, $stderr) {
    $env:APPDATA = $case
    $env:PURITTY_SHOT = Join-Path $case "shot.ppm"
    Remove-Item $env:PURITTY_SHOT -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath (Join-Path $PSScriptRoot "puritty.exe") -ArgumentList $program -PassThru -RedirectStandardError $stderr
    Start-Sleep -Milliseconds 4000
    return $p
}

function Stop-Puritty($p) {
    # the program and its children with it
    & taskkill.exe /T /F /PID $p.Id 2>&1 | Out-Null
    $p.WaitForExit(5000) | Out-Null
}

function Write-Settings($path, $text, $how) {
    if ($how -eq "remove") { Remove-Item $path }
    elseif ($how -eq "rename") {
        [IO.File]::WriteAllText("$path.new", $text)
        Move-Item -Force "$path.new" $path
    } else {
        $f = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
        $f.SetLength(0)
        $b = [Text.Encoding]::UTF8.GetBytes($text)
        $f.Write($b, 0, $b.Length)
        $f.Close()
    }
}

foreach ($line in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot "cases.tsv"))) {
    if (-not $line) { continue }
    $f = $line.Split("`t")
    $name = $f[0]; $how = $f[1]; $fresh = $f[2]
    $case = Join-Path $PSScriptRoot "case-$name"
    New-Item -ItemType Directory -Force (Join-Path $case "puritty") | Out-Null
    $cfg = Join-Path $case "puritty\config.toml"
    Copy-Item (Join-Path $PSScriptRoot "$name.before.toml") $cfg
    $after = Join-Path $PSScriptRoot "$name.after.toml"
    $afterText = if (Test-Path $after) { [IO.File]::ReadAllText($after) } else { $null }
    $shot = Join-Path $case "shot.ppm"

    $p = Start-Puritty $case (Join-Path $out "$name.stderr.txt")
    if (Test-Path $shot) { Copy-Item $shot (Join-Path $out "$name.first.ppm") }
    Write-Settings $cfg $afterText $how
    Start-Sleep -Milliseconds 2000
    if (Test-Path $shot) { Copy-Item $shot (Join-Path $out "$name.got.ppm") }
    [IO.File]::WriteAllText((Join-Path $out "$name.title.txt"), (Get-Title))
    Stop-Puritty $p

    if ($fresh -eq "fresh") {
        if ($afterText -ne $null) { [IO.File]::WriteAllText($cfg, $afterText) }
        $p = Start-Puritty $case (Join-Path $case "fresh-stderr.txt")
        if (Test-Path $shot) { Copy-Item $shot (Join-Path $out "$name.fresh.ppm") }
        Stop-Puritty $p
    }
}

# The 4K worst case (docs/windows.md WS26): each workload run by blast.exe
# in puritty, Windows Terminal and the classic console, each window
# maximized, three times; blast's own timings go to results.tsv, and
# puritty's PURITTY_STATS (its drawing, and its copies to the window) to
# stats-*.txt. Run in the user's desktop session (harness/windows/inSession.ps1).
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$res = "$dir\results.tsv"
Remove-Item "$dir\results.tsv", "$dir\stats-*.txt", "$dir\log.txt" -ErrorAction SilentlyContinue
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd); }
"@
$work = @(
    @{ name = "gitlog";  args = @("dump", "$dir\gitlog.txt") },
    @{ name = "scroll";  args = @("dump", "$dir\vte-scrolling.txt") },
    @{ name = "unicode"; args = @("dump", "$dir\vte-unicode.txt") },
    @{ name = "frames";  args = @("frames", "300") }
)
function Log($t) { "$(Get-Date -Format HH:mm:ss) $t" | Out-File "$dir\log.txt" -Append }
function Blast-Args($w, $out) { ($w.args + @($out, "4")) }
# Windows Terminal starts blast on its own time: wait for blast to be
# there first, then for it to end
function Wait-Blast($limit) {
    $end = (Get-Date).AddSeconds($limit)
    while (-not (Get-Process blast -ErrorAction SilentlyContinue) -and (Get-Date) -lt $end) { Start-Sleep -Milliseconds 100 }
    while ((Get-Process blast -ErrorAction SilentlyContinue) -and (Get-Date) -lt $end) { Start-Sleep -Milliseconds 200 }
}
foreach ($w in $work) {
    foreach ($i in 1..3) {
        # puritty: the program is blast, in a settings file of its own
        $cmd = @("$dir\blast.exe") + (Blast-Args $w "$dir\r-puritty-$($w.name).tsv")
        $toml = "[program]`r`ncommand = [" + (($cmd | ForEach-Object { '"' + ($_ -replace '\\', '/') + '"' }) -join ", ") + "]`r`n"
        Set-Content -Path "$dir\puritty.toml" -Value $toml
        $env:PURITTY_STATS = "1"
        $p = Start-Process -FilePath "C:\Users\yosup\puritty\puritty.exe" -ArgumentList "shell", "--config", "$dir\puritty.toml" -PassThru -RedirectStandardError "$dir\stats-$($w.name)-$i.txt"
        Remove-Item Env:PURITTY_STATS
        Start-Sleep -Milliseconds 1500
        $p.Refresh(); [W]::ShowWindow($p.MainWindowHandle, 3) | Out-Null
        if (-not $p.WaitForExit(180000)) { Log "puritty $($w.name) did not end"; Stop-Process -Id $p.Id }
        Log "puritty $($w.name) $i"
        Get-Process blast -ErrorAction SilentlyContinue | Stop-Process -Force
        # Windows Terminal, a window of its own, maximized
        $a = @("--maximized", "-w", "new", "$dir\blast.exe") + (Blast-Args $w "$dir\r-wt-$($w.name).tsv")
        Start-Process -FilePath "wt.exe" -ArgumentList $a
        Wait-Blast 180
        Log "wt $($w.name) $i"
        Start-Sleep 2
        # the classic console
        $c = Start-Process -FilePath "conhost.exe" -ArgumentList (@("$dir\blast.exe") + (Blast-Args $w "$dir\r-conhost-$($w.name).tsv")) -PassThru
        Start-Sleep -Milliseconds 1500
        $c.Refresh(); [W]::ShowWindow($c.MainWindowHandle, 3) | Out-Null
        if (-not $c.WaitForExit(180000)) { Log "conhost $($w.name) did not end"; Stop-Process -Id $c.Id }
        Log "conhost $($w.name) $i"
    }
}
Log "done"

# puritty alone over the four workloads of render-4k.ps1, three times each,
# maximised (docs/windows.md WS26)
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Remove-Item "$dir\p-*.tsv", "$dir\p-stats-*.txt", "$dir\p-done.txt" -ErrorAction SilentlyContinue
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W3 { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd); }
"@
$work = @(
    @{ name = "gitlog";  args = @("dump", "$dir\gitlog.txt") },
    @{ name = "scroll";  args = @("dump", "$dir\vte-scrolling.txt") },
    @{ name = "unicode"; args = @("dump", "$dir\vte-unicode.txt") },
    @{ name = "frames";  args = @("frames", "300") }
)
foreach ($w in $work) {
    foreach ($i in 1..3) {
        $cmd = @("$dir\blast.exe") + $w.args + @("$dir\p-$($w.name).tsv", "4")
        $toml = "[program]`r`ncommand = [" + (($cmd | ForEach-Object { '"' + ($_ -replace '\\', '/') + '"' }) -join ", ") + "]`r`n"
        Set-Content -Path "$dir\p.toml" -Value $toml
        $env:PURITTY_STATS = "1"
        $p = Start-Process -FilePath "C:\Users\yosup\puritty\puritty.exe" -ArgumentList "shell", "--config", "$dir\p.toml" -PassThru -RedirectStandardError "$dir\p-stats-$($w.name)-$i.txt"
        Remove-Item Env:PURITTY_STATS
        Start-Sleep -Milliseconds 1500
        $p.Refresh(); [W3]::ShowWindow($p.MainWindowHandle, 3) | Out-Null
        if (-not $p.WaitForExit(240000)) { Stop-Process -Id $p.Id }
    }
}
"done" | Out-File "$dir\p-done.txt"

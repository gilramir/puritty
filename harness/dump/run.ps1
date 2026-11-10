# The replay corpus's run on Windows (harness/replay.py --windows): each
# line of runs.tsv beside this script is the output file, then
# core-dump.exe's arguments, tab-separated. Each run's stdout goes to its
# file byte for byte (PowerShell's own redirection would re-encode it);
# a run that fails, or takes more than 60 s, says so in failures.txt as
# its file, a tab, and why.
Set-Location $PSScriptRoot
$exe = Join-Path $PSScriptRoot "core-dump.exe"
$fail = New-Object System.Collections.Generic.List[string]
foreach ($line in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot "runs.tsv"))) {
    if (-not $line) { continue }
    $f = $line.Split("`t")
    $si = New-Object System.Diagnostics.ProcessStartInfo
    $si.FileName = $exe
    $si.Arguments = ($f[1..($f.Length - 1)] | ForEach-Object { if ($_ -eq "") { '""' } else { $_ } }) -join " "
    $si.WorkingDirectory = $PSScriptRoot
    $si.UseShellExecute = $false
    $si.RedirectStandardOutput = $true
    $si.RedirectStandardError = $true
    $p = [Diagnostics.Process]::Start($si)
    $err = $p.StandardError.ReadToEndAsync()
    $out = [IO.File]::Create((Join-Path $PSScriptRoot $f[0]))
    $copy = $p.StandardOutput.BaseStream.CopyToAsync($out)
    if (-not $p.WaitForExit(60000)) {
        $p.Kill()
        $p.WaitForExit()
        $fail.Add("$($f[0])`ttook more than 60 s")
    } else {
        $p.WaitForExit()
        if ($p.ExitCode -ne 0) { $fail.Add("$($f[0])`texit $($p.ExitCode): " + ($err.Result -replace "[\r\n]+", " ")) }
    }
    $copy.Wait()
    $out.Close()
}
[IO.File]::WriteAllLines((Join-Path $PSScriptRoot "failures.txt"), $fail)

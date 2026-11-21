# A drop target that logs everything (puritty docs/sftp.md FT21): the
# formats a drag offers as it enters, how often DragOver comes and with
# what, and on the drop each format's size, the files (CF_HDROP, read as
# FileDrop) and the virtual files' names (FileGroupDescriptorW). WinForms'
# drop target is OLE's IDropTarget, which puritty's window would register.
#
# Run in the user's session (harness/windows/inSession.ps1 -Script ...);
# the log is drop-probe.log beside it, UTF-8. It closes after 30 minutes.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$log = Join-Path $PSScriptRoot "drop-probe.log"
function Say($text) { [System.IO.File]::AppendAllText($log, ((Get-Date).ToString("HH:mm:ss.fff") + " " + $text + "`r`n"), [System.Text.Encoding]::UTF8) }
Say "started"

$form = New-Object System.Windows.Forms.Form
$form.Text = "puritty drop probe: drag files here"
$form.Size = New-Object System.Drawing.Size(560, 360)
$form.TopMost = $true
$form.AllowDrop = $true
$label = New-Object System.Windows.Forms.Label
$label.Dock = "Fill"
$label.TextAlign = "MiddleCenter"
$label.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$label.Text = "Drag files or folders here, from Explorer, from inside a .zip, or from another program.`r`n`r`nEach drop is logged; nothing is opened or copied.`r`nClose this window when done."
$form.Controls.Add($label)
$script:overs = 0
$script:drops = 0

$form.Add_DragEnter({
    param($s, $e)
    $script:overs = 0
    Say ("enter: allowed " + $e.AllowedEffect + ", keys " + $e.KeyState + ", formats: " + (($e.Data.GetFormats($false)) -join " | "))
    $e.Effect = [System.Windows.Forms.DragDropEffects]::Copy
})
$form.Add_DragOver({
    param($s, $e)
    $script:overs++
    if ($script:overs -le 3 -or $script:overs % 25 -eq 0) { Say ("over " + $script:overs + ": at " + $e.X + "," + $e.Y + " keys " + $e.KeyState + " allowed " + $e.AllowedEffect) }
    $e.Effect = [System.Windows.Forms.DragDropEffects]::Copy
})
$form.Add_DragLeave({ Say ("leave after " + $script:overs + " overs") })
$form.Add_DragDrop({
    param($s, $e)
    $script:drops++
    Say ("drop " + $script:drops + " after " + $script:overs + " overs, at " + $e.X + "," + $e.Y + " keys " + $e.KeyState)
    foreach ($f in $e.Data.GetFormats($false)) {
        try {
            $d = $e.Data.GetData($f, $false)
            $what = if ($d -eq $null) { "null" } elseif ($d -is [System.IO.MemoryStream]) { "stream of " + $d.Length + " bytes" } elseif ($d -is [string[]]) { "" + $d.Length + " strings" } else { $d.GetType().Name }
        } catch { $what = "error: " + $_.Exception.Message }
        Say ("  format " + $f + ": " + $what)
    }
    $files = $e.Data.GetData("FileDrop", $false)
    if ($files) { foreach ($p in $files) { Say ("  file: " + $p + "  (" + $(if (Test-Path -LiteralPath $p -PathType Container) { "folder" } elseif (Test-Path -LiteralPath $p) { "file" } else { "not there" }) + ")") } }
    $fgd = $e.Data.GetData("FileGroupDescriptorW", $false)
    if ($fgd -is [System.IO.MemoryStream]) {
        $b = $fgd.ToArray()
        $n = [BitConverter]::ToUInt32($b, 0)
        Say ("  virtual files: " + $n)
        # FILEDESCRIPTORW is 592 bytes; its name, 260 WCHARs, is at 72
        for ($i = 0; $i -lt $n; $i++) {
            $at = 4 + $i * 592
            $name = [System.Text.Encoding]::Unicode.GetString($b, $at + 72, 520).TrimEnd([char]0)
            $size = [BitConverter]::ToUInt32($b, $at + 68) + [uint64][BitConverter]::ToUInt32($b, $at + 64) * 4294967296
            Say ("  virtual: " + $name + " (" + $size + " bytes)")
        }
    }
    $e.Effect = [System.Windows.Forms.DragDropEffects]::Copy
})
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 30 * 60 * 1000
$timer.Add_Tick({ $form.Close() })
$timer.Start()
[void]$form.ShowDialog()
Say "closed"

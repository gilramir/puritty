# Ends the puritty hero.ps1 started, by its id, and nothing else.
$base = "C:\Users\yosup\geng-probe\hero"
$id = [int](Get-Content "$base\pid.txt")
Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
"stopped $id" | Out-File "$base\stop.log"

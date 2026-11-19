#!/bin/sh
# usage: run.sh (after app/build-windows.sh): the 0.2.0 release's exe and the
# one built here, each minimized and restored on beelink1; pictures in
# .harness-work/minimize/
set -e
root=/home/gram/prj/puritty
work=$root/.harness-work/minimize
mkdir -p "$work"
rm -rf "$work/rel" && mkdir "$work/rel" && unzip -q -o "$root/dist/0.2.0/puritty-0.2.0-windows-x64.zip" -d "$work/rel"
ssh beelink1 'New-Item -ItemType Directory -Force geng-probe\minimize\appdata\puritty,geng-probe\minimize\local | Out-Null; Remove-Item geng-probe\minimize\result.txt,geng-probe\minimize\done-*.txt -ErrorAction SilentlyContinue; exit 0'
scp -q "$work/rel/puritty.exe" beelink1:geng-probe/minimize/old.exe
scp -q "$root/app/puritty.exe" beelink1:geng-probe/minimize/new.exe
scp -q "$root/harness/windows/minimize/run.ps1" "$root/harness/windows/minimize/lines.cmd" beelink1:geng-probe/minimize/
for t in old new; do
    ssh beelink1 "Set-Content geng-probe\\minimize\\go-$t.ps1 '& ''C:\\Users\\yosup\\geng-probe\\minimize\\run.ps1'' -Exe $t.exe -Tag $t'"
    ssh beelink1 "powershell -NoProfile -ExecutionPolicy Bypass -File geng-probe\\inSession.ps1 -Script C:\\Users\\yosup\\geng-probe\\minimize\\go-$t.ps1"
    i=0
    until ssh beelink1 "Test-Path geng-probe\\minimize\\done-$t.txt" | grep -q True; do
        i=$((i+1)); [ $i -lt 30 ] || { echo "$t: no result"; break; }
        sleep 3
    done
    scp -q "beelink1:geng-probe/minimize/$t-before.png" "beelink1:geng-probe/minimize/$t-after.png" "$work/" || true
done
ssh beelink1 'Get-Content geng-probe\minimize\result.txt'

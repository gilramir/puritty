#!/bin/sh
# Signs a Windows exe with Gilbert's code signing certificate (docs/windows.md
# WS28): Certum's, its key in Certum's cloud, reached through SimplySign
# Desktop on beelink1, which must be logged in (a code from Gilbert's phone).
# The exe is copied there, signed by the certificate's thumbprint with
# Certum's RFC 3161 timestamp, verified with `signtool verify /pa`, and
# copied back over the file given.
#
#   scripts/sign-windows.sh app/puritty.exe
#
# PURITTY_SIGN_HOST (beelink1) and PURITTY_SIGN_THUMBPRINT name another
# machine or certificate. Fails, leaving the file as it was, when signing or
# verifying does (SimplySign not logged in, the machine not reached).
set -e
file=${1:?usage: scripts/sign-windows.sh FILE.exe}
[ -f "$file" ] || { echo "sign-windows: no file $file" >&2; exit 1; }
host=${PURITTY_SIGN_HOST:-beelink1}
thumb=${PURITTY_SIGN_THUMBPRINT:-8BFCB2EA9F2D53D0497E39EA1C6C08D32796D8C2}
signtool='C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe'
dir=puritty-sign-$$
name=$(basename "$file")
local_copy=$(mktemp)
trap 'rm -f "$local_copy"; ssh "$host" "Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue" >/dev/null 2>&1 || true' EXIT

echo "== signing $file on $host"
# the login shell there is PowerShell 5: `;` between commands, `&` to run
# a quoted path, and $LASTEXITCODE for a program's failure
ssh "$host" "New-Item -ItemType Directory -Force $dir | Out-Null"
scp -q "$file" "$host:$dir/$name"
ssh "$host" "Set-Location $dir; & '$signtool' sign /sha1 $thumb /fd sha256 /tr http://time.certum.pl /td sha256 '$name'; if (\$LASTEXITCODE -ne 0) { exit 1 }; & '$signtool' verify /pa '$name'; if (\$LASTEXITCODE -ne 0) { exit 1 }" || {
    echo "sign-windows: signing failed; is SimplySign Desktop logged in on $host?" >&2
    exit 1
}
scp -q "$host:$dir/$name" "$local_copy"
# a signed file is longer than the one sent: the signature is appended
if [ "$(wc -c <"$local_copy")" -le "$(wc -c <"$file")" ]; then
    echo "sign-windows: what came back is not longer than what was sent; not signed" >&2
    exit 1
fi
cp "$local_copy" "$file"
echo "== signed: $file"

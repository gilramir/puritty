#!/bin/sh
# Signs a Windows exe with Gilbert's code signing certificate (docs/windows.md
# WS28): Certum's, its key in Certum's cloud, reached through SimplySign
# Desktop on beelink1, which must be logged in (a code from Gilbert's phone).
# The exe is copied there, signed by the certificate's thumbprint with
# Certum's RFC 3161 timestamp, verified with `signtool verify /pa`, copied
# back, and checked here by scripts/sign-check.py before it replaces the
# file given: the bytes sent unchanged, the signature good, and its signer
# the certificate the thumbprint names (the code review's W17; before, only
# that what came back was longer). PURITTY_SIGN_CAFILE names the CA
# certificates the chain is checked against, the system's by default.
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
# a name of its own there: the file's, with a space or a quote, broke the
# remote commands it was written into (W17)
name=unsigned.exe
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
python3 "$(dirname "$0")/sign-check.py" "$file" "$local_copy" "$thumb" ${PURITTY_SIGN_CAFILE:+"$PURITTY_SIGN_CAFILE"} || {
    echo "sign-windows: what came back is not $file signed by $thumb; $file left as it was" >&2
    exit 1
}
cp "$local_copy" "$file"
echo "== signed: $file"

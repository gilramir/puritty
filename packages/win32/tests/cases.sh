#!/bin/sh
# The win32 package's portable C tested on Linux (cases.c: the code
# review's W12), with AddressSanitizer. From puritty's devbox.
set -e
cd "$(dirname "$0")"
OUT=${TMPDIR:-/tmp}/win32cases.$$
/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang -g -O1 -Wall -Wextra -fsanitize=address,undefined -fno-omit-frame-pointer cases.c -o "$OUT"
trap 'rm -f "$OUT"' EXIT
"$OUT"
echo OK

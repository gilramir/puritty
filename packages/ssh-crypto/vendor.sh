#!/bin/sh
# Copies the part of PuTTY's source that ssh-crypto compiles
# (docs/ssh-client.md SC11 step 3) from a PuTTY checkout into
# src/Ext/putty/, unchanged, flat but for the two headers PuTTY names by
# a directory (ssh/ttymode-list.h, utils/utils.h). What PuTTY's own
# putty.h and the *-select.c files' configuration would give is
# src/Ext/putty/putty.h and src/Ext/ssh_crypto_config.h, which are
# ssh-crypto's own and not copied.
#
# usage: packages/ssh-crypto/vendor.sh [PUTTY_CHECKOUT]
#   (default: vendor/putty, at the commit in src/Ext/putty/COMMIT)
set -e
here=$(cd "$(dirname "$0")" && pwd)
from=${1:-$here/../../vendor/putty}
to=$here/src/Ext/putty
keep=$(cat "$to/putty.h" 2>/dev/null || true)
rm -rf "$to"
mkdir -p "$to/ssh" "$to/utils"
headers="defs.h puttymem.h tree234.h network.h misc.h marshal.h mpint.h ssh.h"
crypto="aes-common aes-ni aes-sw aes-select aesgcm-clmul aesgcm-common
aesgcm-ref-poly aesgcm-select aesgcm-sw chacha20-poly1305 ecc-arithmetic
ecc-ssh mpint rsa rfc6979 sha1-common sha1-ni sha1-select sha1-sw
sha256-common sha256-ni sha256-select sha256-sw sha512-common
sha512-select sha512-sw sha3 md5 hmac mac mac_simple hash_simple bcrypt
blowfish"
utils="marshal dupprintf dupstr key_components ptrlen memory smemclr smemeq
strbuf burnstr bufchain"
stubs="null-key null-mac null-cipher"
for h in $headers; do cp "$from/$h" "$to/"; done
cp "$from/ssh/ttymode-list.h" "$to/ssh/"
cp "$from/utils/utils.h" "$to/utils/"
cp "$from"/crypto/*.h "$to/"
for c in $crypto; do cp "$from/crypto/$c.c" "$to/"; done
for c in $utils; do cp "$from/utils/$c.c" "$to/"; done
for c in $stubs; do cp "$from/stubs/$c.c" "$to/"; done
cp "$from/LICENCE" "$to/"
git -C "$from" rev-parse HEAD > "$to/COMMIT"
if [ -n "$keep" ]; then printf '%s\n' "$keep" > "$to/putty.h"; fi
echo "copied PuTTY $(cat "$to/COMMIT") into $to"

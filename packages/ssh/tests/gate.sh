#!/bin/sh
# The ssh client's gate so far (docs/ssh-client.md SC13, SC14): ssh-crypto's
# vectors and fuzzer, then the transport against a local sshd, the scripted
# server, its replays and its fuzzer. Builds both test programs first. Run
# from puritty's devbox, on a machine with /usr/sbin/sshd. transfer.py is
# the transfer engine's (docs/sftp.md FT17), shell-transfer.py its fallback
# through the host's shell (FT18).
set -e
cd "$(dirname "$0")"
../../ssh-crypto/tests/build.sh >/dev/null
(cd ../../ssh-crypto/tests && ./ssh-crypto-tests && ./ssh-crypto-tests --fuzz 20000)
./build.sh >/dev/null
./sshd.py
./scripted.py
./sftp.py
./transfer.py
./shell-transfer.py
for f in replays/*.txt; do ./ssh-tests fuzz "$f" 5000; done
./ssh-tests known-hosts known-hosts.txt
./ssh-tests config config-cases.txt
./ssh-tests connection

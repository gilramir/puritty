#!/bin/sh
# The ssh client's gate so far (docs/ssh-client.md SC13, SC14): ssh-crypto's
# vectors and fuzzer, then the transport against a local sshd, the scripted
# server, its replays and its fuzzer. Builds both test programs first. Run
# from puritty's devbox, on a machine with /usr/sbin/sshd.
set -e
cd "$(dirname "$0")"
../../ssh-crypto/tests/build.sh >/dev/null
(cd ../../ssh-crypto/tests && ./ssh-crypto-tests && ./ssh-crypto-tests --fuzz 20000)
./build.sh >/dev/null
./sshd.py
./scripted.py
for f in replays/*.txt; do ./ssh-tests fuzz "$f" 5000; done

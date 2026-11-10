# A short Ed25519 key or an even RSA modulus in a public key blob fails an assertion

- **Repository:** PuTTY, `git.tartarus.org/simon/putty.git`
- **Found against:** `7507c54b` (2026-10-14), `crypto/ecc-ssh.c` and `crypto/mpint.c`
- **Found by:** puritty's fuzzers (`docs/ssh-client.md` SC14): the
  transport's, which changes recorded sessions' bytes, and ssh-crypto's,
  which hands `ssh_key_new_pub` and `ssh_key_verify` blobs of the right
  fields with wrong lengths

## Summary

Two public key blobs end the program in an assertion instead of being
refused:

| blob | where | assertion |
|---|---|---|
| `string "ssh-ed25519"`, `string` of fewer than 32 bytes | `eddsa_new_pub` → `get_epoint` → `eddsa_decode`: `mp_from_bytes_le` makes an `mp_int` of as many words as the bytes need, and `mp_set_bit(y, curve->fieldBytes * 8 - 1, 0)` sets bit 255 of it | `mpint.c`:320, `mp_set_bit`: `word < x->nw` |
| `string "ssh-rsa"`, `mpint e`, `mpint n` with `n` even | `rsa2_verify` → `mp_modpow(in, rsa->exponent, rsa->modulus)` | `mpint.c`:1663, `mp_modpow`: `modulus->w[0] & 1` |

A server's host key arrives in `SSH_MSG_KEX_ECDH_REPLY` and goes to
`ssh_key_new_pub` before anything else checks it, so a server could end a
client this way, PuTTY's own presumably included (inferred from the code;
not tried against PuTTY's programs, and not known whether its release
builds keep `assert`). The same blobs reach the same code from a key file
or an agent.

## Reproduction

    ssh_key *k = ssh_key_new_pub(&ssh_ecdsa_ed25519,
        PTRLEN_LITERAL("\0\0\0\x0bssh-ed25519\0\0\0\x04abcd"));

aborts in `mp_set_bit`. An `ssh-rsa` blob with `n = 2^1024` (an `mpint`
of `0x01` and 128 zero bytes) and any signature of 128 bytes aborts in
`mp_modpow` through `ssh_key_verify`.

## Fix

In `eddsa_decode`, refuse an encoding whose length is not
`curve->fieldBytes` before making `y` (`eddsa_verify` already checks its
`R`'s length this way). In `rsa2_new_pub`, or before `mp_modpow` in
`rsa2_verify` and `rsa_ssh1_encrypt`, refuse an even modulus. puritty's
`ssh_crypto.c` (`well_formed`) checks every blob's shape before calling
PuTTY.

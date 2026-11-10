# Signature verification accepts an unreduced RSA signature and an Ed25519 point with x = 0 and the sign bit set

- **Repository:** PuTTY, `git.tartarus.org/simon/putty.git`
- **Found against:** `7507c54b` (2026-10-14), `crypto/rsa.c` and `crypto/ecc-ssh.c`
- **Found by:** puritty's ssh-crypto tests (`docs/ssh-client.md` SC13), Wycheproof
  `d5f724a2`

## Summary

Two signatures that the standards say are invalid verify as valid:

| | Wycheproof | the standard | PuTTY |
|---|---|---|---|
| RSA PKCS#1 v1.5 signature `s` not below the modulus `n` | `rsa_signature_2048_sha256` case 244, `rsa_signature_4096_sha256` and `_sha512` case 245, "the signature is not reduced" (`SignatureMalleability`) | RFC 8017 §5.2.2: RSAVP1 fails with "signature representative out of range" unless `0 <= s < n` | `rsa2_verify` computes `s^e mod n` for any `s`, so `s + n` verifies wherever `s` does |
| Ed25519 `R` encoding `y = 1` with the sign bit of `x` set | `ed25519` case 151 (`InvalidEncoding`) | RFC 8032 §5.1.3, step 4: "If x = 0, and x_0 = 1, decoding fails" | the decoding ignores the sign bit when `x` is 0, so the encoding decodes to the point `(0, 1)` |

Neither lets a signature be made without the key: each turns one valid
signature into another valid one (malleability). A protocol that treats a
signature's bytes as unique (as SSH does not) could be misled.

## Security

Low. Neither lets anyone sign without the key; each lets someone holding a
valid signature make a second, different valid one. SSH signs the exchange
hash, which neither side treats as unique by its signature's bytes, so an
SSH session is not affected. A use of PuTTY's code that does treat a
signature's bytes as an identifier (deduplicating signed messages, say)
could be misled.

## Reproduction

The Wycheproof cases above, through `ssh_key_verify` with the SSH blobs
made from them: `ssh-rsa` with `mpint e`, `mpint n`, and the signature as
`rsa-sha2-256`'s or `rsa-sha2-512`'s string; `ssh-ed25519` with the 32-byte
key and the 64-byte signature. puritty's
`packages/ssh-crypto/tests/make-vectors.py` writes them, and the tests ran
them without the two checks below in `ssh_crypto.c`.

## Fix

In `rsa2_verify`, refuse `in` when `mp_cmp_hs(in, rsa->modulus)`, before
the exponentiation. In Ed25519 point decoding, fail when the recovered `x`
is 0 and the encoded sign bit is 1 (the encodings of `y = 1` and
`y = p - 1` with the top bit set). puritty's `ssh_crypto.c` (`malleable`)
does both before calling PuTTY.

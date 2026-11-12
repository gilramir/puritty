/* One lock over PuTTY's elliptic curves (puritty docs/tabs.md TB10).
 *
 * PuTTY makes each curve the first time it is used, in a static, and a
 * curve keeps a Montgomery context whose scratch numbers every
 * multiplication on that curve writes. Nothing of it is locked: PuTTY runs
 * its cryptography on one thread. ssh-crypto loads and signs with keys on
 * threads of their own, and verifies host keys and reads public keys on
 * the program thread, so two of those on one curve at once overwrite each
 * other's numbers: a key that fails to load as malformed, a signature the
 * server refuses. Each of them holds this lock while PuTTY works on a key.
 * The key exchange's curve25519 is only ever used on the program thread. */

#ifndef SSH_CRYPTO_LOCK_H
#define SSH_CRYPTO_LOCK_H

void ssh_crypto_curves_lock(void);
void ssh_crypto_curves_unlock(void);

#endif

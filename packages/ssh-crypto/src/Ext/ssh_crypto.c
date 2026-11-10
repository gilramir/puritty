/* ssh-crypto's rows (puritty docs/ssh-client.md SC6, SC11 step 3): PuTTY's
 * primitives (src/Ext/putty, vendor.sh) as pure functions over bytes, for
 * `SshCrypto`.
 *
 * Each row checks what it is handed and answers an empty `Bytes` (or 0) for
 * anything it cannot use, so no input reaches PuTTY that PuTTY would assert
 * on; `SshCrypto` checks lengths before calling as well and turns an empty
 * answer into `Nothing`. Nothing here keeps state between calls: a packet
 * cipher is keyed again for each packet, from the sequence number and the
 * count of packets since the keys were taken.
 *
 * PuTTY asks `random_read` for the bytes of a private value. The only
 * draws a row allows are the ones it supplies itself (`supplied`), so a
 * private value always comes from the caller, and any other draw is a
 * crash, not a quiet use of some generator. */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "ssh_crypto_config.h"
#include "putty/ssh.h"
#include "putty/mpint.h"

#include "geng.h"

/* RUNTIME */

static geng_bytes *bytes_alloc(size_t n) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b + n, GENG_HEADER_BYTES(sizeof *b + n));
    b->length = (int32_t) n;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    return b;
}

static geng_bytes *bytes_of(const void *s, size_t n) {
    geng_bytes *b = bytes_alloc(n);
    if (n > 0) memcpy(b->data, s, n);
    return b;
}

static geng_bytes *none(void) { return bytes_alloc(0); }

static ptrlen pl(void *bytes) {
    geng_bytes *b = bytes;
    return make_ptrlen(b->data, (size_t) b->length);
}

static size_t len(void *bytes) { return (size_t) ((geng_bytes *) bytes)->length; }

void out_of_memory(void) { geng_crash("ssh-crypto: out of memory"); }

static const uint8_t *supply;
static size_t supply_left;

void random_read(void *out, size_t n) {
    if (supply == NULL || n > supply_left) geng_crash("ssh-crypto: a random draw nothing supplied");
    memcpy(out, supply, n);
    supply += n;
    supply_left -= n;
}

static void supplied(const void *bytes, size_t n) {
    supply = bytes;
    supply_left = n;
}

static void unsupplied(void) {
    supply = NULL;
    supply_left = 0;
}

/* A strbuf's bytes as `Bytes`, and the strbuf cleared and freed. */
static geng_bytes *from_strbuf(strbuf *sb) {
    geng_bytes *b = bytes_of(sb->u, sb->len);
    strbuf_free(sb);
    return b;
}


/* HASHES AND MACS */

/* 0 SHA-1, 1 SHA-256, 2 SHA-384, 3 SHA-512. */
static const ssh_hashalg *hash_of(int32_t which) {
    switch (which) {
    case 0: return &ssh_sha1;
    case 1: return &ssh_sha256;
    case 2: return &ssh_sha384;
    case 3: return &ssh_sha512;
    default: return NULL;
    }
}

void *ssh_crypto_hash(int32_t which, void *data) {
    const ssh_hashalg *alg = hash_of(which);
    if (alg == NULL) return none();
    geng_bytes *out = bytes_alloc(alg->hlen);
    hash_simple(alg, pl(data), out->data);
    return out;
}

/* 0 HMAC-SHA-1, 1 HMAC-SHA-256, 2 HMAC-SHA-512, with a key of any length
 * (RFC 2104: a longer one than the hash's block is hashed first). */
void *ssh_crypto_hmac(int32_t which, void *key, void *data) {
    const ssh2_macalg *alg = which == 0 ? &ssh_hmac_sha1 : which == 1 ? &ssh_hmac_sha256 : which == 2 ? &ssh_hmac_sha512 : NULL;
    if (alg == NULL) return none();
    ssh2_mac *m = ssh2_mac_new(alg, NULL);
    ssh2_mac_setkey(m, pl(key));
    ssh2_mac_start(m);
    put_datapl(m, pl(data));
    geng_bytes *out = bytes_alloc(alg->len);
    ssh2_mac_genresult(m, out->data);
    ssh2_mac_free(m);
    return out;
}

/* 1 when the two hold the same bytes, in a time that depends only on
 * their lengths. */
int32_t ssh_crypto_equal(void *a, void *b) {
    if (len(a) != len(b)) return 0;
    return smemeq(((geng_bytes *) a)->data, ((geng_bytes *) b)->data, len(a)) ? 1 : 0;
}


/* KEY EXCHANGE: curve25519-sha256 (RFC 8731) */

/* The X25519 key of a private value, 32 bytes, as PuTTY makes one: the
 * value clamped as RFC 7748 says. */
static ecdh_key *x25519_of(void *secret) {
    if (len(secret) != 32) return NULL;
    supplied(((geng_bytes *) secret)->data, 32);
    ecdh_key *k = ecdh_key_new(&ssh_ec_kex_curve25519, false);
    unsupplied();
    return k;
}

/* The public value, 32 bytes, that goes to the other side. */
void *ssh_crypto_x25519Public(void *secret) {
    ecdh_key *k = x25519_of(secret);
    if (k == NULL) return none();
    strbuf *sb = strbuf_new_nm();
    ecdh_key_getpublic(k, BinarySink_UPCAST(sb));
    ecdh_key_free(k);
    return from_strbuf(sb);
}

/* The shared secret K with the other side's public value, as the exchange
 * hash and the keys take it: an SSH `mpint`, its length first. Empty for a
 * public value that gives none (all zeros, RFC 7748 §6.1). */
void *ssh_crypto_x25519Shared(void *secret, void *theirs) {
    if (len(theirs) != 32) return none();
    ecdh_key *k = x25519_of(secret);
    if (k == NULL) return none();
    strbuf *sb = strbuf_new_nm();
    bool ok = ecdh_key_getkey(k, pl(theirs), BinarySink_UPCAST(sb));
    ecdh_key_free(k);
    if (!ok) {
        strbuf_free(sb);
        return none();
    }
    return from_strbuf(sb);
}


/* SIGNATURES */

/* The key algorithm a signature algorithm's name is checked with. */
static const ssh_keyalg *keyalg_of(ptrlen name) {
    if (ptrlen_eq_string(name, "ssh-ed25519")) return &ssh_ecdsa_ed25519;
    if (ptrlen_eq_string(name, "ecdsa-sha2-nistp256")) return &ssh_ecdsa_nistp256;
    if (ptrlen_eq_string(name, "rsa-sha2-256")) return &ssh_rsa_sha256;
    if (ptrlen_eq_string(name, "rsa-sha2-512")) return &ssh_rsa_sha512;
    return NULL;
}

/* Whether an Ed25519 point's 32 bytes decode, as far as PuTTY's decoding
 * does not check: RFC 8032 §5.1.3 has the decoding fail when x would be 0
 * (y is 1 or p - 1) and the sign bit asks for x odd. PuTTY ignores that
 * sign bit (Wycheproof ed25519 case 151). */
static int ed25519_point_decodes(const uint8_t *p) {
    if (!(p[31] & 0x80)) return 1;
    int one = p[0] == 1, minus_one = p[0] == 0xec;
    for (int i = 1; i < 31; i++) {
        one &= p[i] == 0;
        minus_one &= p[i] == 0xff;
    }
    one &= (p[31] & 0x7f) == 0;
    minus_one &= (p[31] & 0x7f) == 0x7f;
    return !(one || minus_one);
}

/* What RFC 8017 and 8032 refuse and PuTTY's verify does not: an RSA
 * signature that is not below the modulus (RFC 8017 §5.2.2, Wycheproof's
 * "not reduced"), and an Ed25519 R or public key that does not decode. A
 * blob that does not parse is left for PuTTY to refuse. */
static int malleable(const ssh_keyalg *alg, ptrlen pub, ptrlen sig) {
    BinarySource ps[1], ss[1];
    BinarySource_BARE_INIT_PL(ps, pub);
    BinarySource_BARE_INIT_PL(ss, sig);
    get_string(ps);
    get_string(ss);
    if (alg == &ssh_rsa_sha256 || alg == &ssh_rsa_sha512) {
        mp_int *e = get_mp_ssh2(ps), *n = get_mp_ssh2(ps);
        ptrlen s_bytes = get_string(ss);
        int refused = 0;
        if (!get_err(ps) && !get_err(ss)) {
            mp_int *s = mp_from_bytes_be(s_bytes);
            refused = mp_cmp_hs(s, n) != 0;
            mp_free(s);
        }
        mp_free(e);
        mp_free(n);
        return refused;
    }
    if (alg == &ssh_ecdsa_ed25519) {
        ptrlen a = get_string(ps), rs = get_string(ss);
        if (get_err(ps) || get_err(ss) || a.len != 32 || rs.len != 64) return 0;
        return !ed25519_point_decodes(a.ptr) || !ed25519_point_decodes(rs.ptr);
    }
    return 0;
}

/* Whether the public key and signature blobs are each exactly the shape
 * their algorithm's are, nothing missing and nothing after. PuTTY's own
 * decoding is not to be reached with any other: an `ssh-ed25519` key
 * shorter than 32 bytes trips an assertion in `eddsa_decode` (found by
 * the transport's fuzzer, `ssh-client.md` SC14), an even RSA modulus one
 * in `mp_modpow`, and an ECDSA point may be
 * the identity or compressed, which no OpenSSH host key is. */
static int well_formed(const ssh_keyalg *alg, ptrlen pub, ptrlen sig) {
    BinarySource ps[1], ss[1];
    BinarySource_BARE_INIT_PL(ps, pub);
    BinarySource_BARE_INIT_PL(ss, sig);
    ptrlen key_type = get_string(ps), sig_type = get_string(ss);
    if (alg == &ssh_ecdsa_ed25519) {
        ptrlen a = get_string(ps), rs = get_string(ss);
        return !get_err(ps) && !get_err(ss) && !get_avail(ps) && !get_avail(ss) &&
               ptrlen_eq_string(key_type, "ssh-ed25519") && ptrlen_eq_string(sig_type, "ssh-ed25519") &&
               a.len == 32 && rs.len == 64;
    }
    if (alg == &ssh_ecdsa_nistp256) {
        ptrlen curve = get_string(ps), point = get_string(ps), inner = get_string(ss);
        if (get_err(ps) || get_err(ss) || get_avail(ps) || get_avail(ss)) return 0;
        if (!ptrlen_eq_string(key_type, "ecdsa-sha2-nistp256") || !ptrlen_eq_string(sig_type, "ecdsa-sha2-nistp256") ||
            !ptrlen_eq_string(curve, "nistp256") || point.len != 65 || ((const uint8_t *) point.ptr)[0] != 4)
            return 0;
        BinarySource is[1];
        BinarySource_BARE_INIT_PL(is, inner);
        ptrlen r = get_string(is), s_ = get_string(is);
        return !get_err(is) && !get_avail(is) && r.len >= 1 && r.len <= 33 && s_.len >= 1 && s_.len <= 33;
    }
    if (alg == &ssh_rsa_sha256 || alg == &ssh_rsa_sha512) {
        ptrlen e = get_string(ps), n = get_string(ps), s_ = get_string(ss);
        if (get_err(ps) || get_err(ss) || get_avail(ps) || get_avail(ss)) return 0;
        /* 1024 to 16384 bits, as OpenSSH takes (SSH_RSA_MINIMUM_MODULUS_SIZE
         * and OPENSSL_RSA_MAX_MODULUS_BITS) */
        return ptrlen_eq_string(key_type, "ssh-rsa") && ptrlen_eq_string(sig_type, alg->ssh_id) &&
               e.len >= 1 && e.len <= 8 && n.len >= 128 && n.len <= 2049 && s_.len >= 1 && s_.len <= n.len &&
               /* an even modulus is no RSA key, and trips mp_modpow's
                * assertion (found by ssh-crypto's fuzzer) */
               (((const uint8_t *) n.ptr)[n.len - 1] & 1);
    }
    return 0;
}

/* 1 when `signature` (the SSH signature blob) is `algorithm`'s signature
 * of `data` by the key `publicKey` (the SSH public key blob), 0 when it is
 * not or either blob is not one, -1 for an algorithm not known here. */
int32_t ssh_crypto_verify(void *algorithm, void *publicKey, void *signature, void *data) {
    const ssh_keyalg *alg = keyalg_of(pl(algorithm));
    if (alg == NULL) return -1;
    if (!well_formed(alg, pl(publicKey), pl(signature)) || malleable(alg, pl(publicKey), pl(signature))) return 0;
    ssh_key *k = ssh_key_new_pub(alg, pl(publicKey));
    if (k == NULL) return 0;
    bool ok = ssh_key_verify(k, pl(signature), pl(data));
    ssh_key_free(k);
    return ok ? 1 : 0;
}


/* PACKETS: chacha20-poly1305@openssh.com, aes128-gcm@openssh.com,
 * aes256-gcm@openssh.com (OpenSSH's PROTOCOL.chacha20poly1305, RFC 5647
 * as OpenSSH's PROTOCOL amends it). */

/* 0 ChaCha20-Poly1305, 1 AES-128-GCM, 2 AES-256-GCM. */
static const ssh_cipheralg *cipher_of(int32_t which) {
    switch (which) {
    case 0: return &ssh2_chacha20_poly1305;
    case 1: return &ssh_aes128_gcm;
    case 2: return &ssh_aes256_gcm;
    default: return NULL;
    }
}

typedef struct {
    ssh_cipher *cipher;
    ssh2_mac *mac;
} keyed;

/* The cipher and its MAC keyed for the packet `count` packets after the
 * keys were taken: an AES-GCM nonce's counter is the starting IV's plus
 * `count`, as `count` of PuTTY's next_message would leave it. */
static int key_for(int32_t which, void *key, void *iv, uint32_t count, keyed *k) {
    const ssh_cipheralg *alg = cipher_of(which);
    if (alg == NULL || len(key) != (size_t) alg->padded_keybytes) return 0;
    uint8_t nonce[12] = {0};
    if (which != 0) {
        if (len(iv) != 12) return 0;
        memcpy(nonce, ((geng_bytes *) iv)->data, 12);
        uint64_t counter = GET_64BIT_MSB_FIRST(nonce + 4) + count;
        PUT_64BIT_MSB_FIRST(nonce + 4, counter);
    }
    k->cipher = ssh_cipher_new(alg);
    if (k->cipher == NULL) return 0;
    ssh_cipher_setkey(k->cipher, ((geng_bytes *) key)->data);
    if (which != 0) ssh_cipher_setiv(k->cipher, nonce);
    k->mac = ssh2_mac_new(alg->required_mac, k->cipher);
    ssh2_mac_setkey(k->mac, make_ptrlen(NULL, 0));
    smemclr(nonce, sizeof nonce);
    return 1;
}

static void unkey(keyed *k) {
    ssh2_mac_free(k->mac);
    ssh_cipher_free(k->cipher);
}

/* The tag's length, and the block the packet after its length field must be
 * a multiple of: the cipher's, but never less than RFC 4253 §6's 8, which
 * ChaCha20-Poly1305 (a stream cipher, block 1 to PuTTY) is padded to. */
int32_t ssh_crypto_tagLength(int32_t which) { return cipher_of(which) ? 16 : 0; }

int32_t ssh_crypto_blockSize(int32_t which) {
    const ssh_cipheralg *alg = cipher_of(which);
    return alg == NULL ? 0 : alg->blksize < 8 ? 8 : alg->blksize;
}

/* A packet sealed: `packet` is its length field, its padding length, its
 * payload and its padding, in the clear; the answer is that encrypted (the
 * length field too for ChaCha20-Poly1305, which encrypts it apart) and the
 * tag after it. */
void *ssh_crypto_seal(int32_t which, void *key, void *iv, int32_t seq, int32_t count, void *packet) {
    size_t n = len(packet);
    const ssh_cipheralg *alg = cipher_of(which);
    if (alg == NULL || n < 8 || (n - 4) % (size_t) alg->blksize != 0) return none();
    keyed k;
    if (!key_for(which, key, iv, (uint32_t) count, &k)) return none();
    geng_bytes *out = bytes_alloc(n + 16);
    memcpy(out->data, ((geng_bytes *) packet)->data, n);
    if (alg->flags & SSH_CIPHER_SEPARATE_LENGTH) ssh_cipher_encrypt_length(k.cipher, out->data, 4, (uint32_t) seq);
    ssh_cipher_encrypt(k.cipher, out->data + 4, (int) (n - 4));
    ssh2_mac_generate(k.mac, out->data, (int) n, (uint32_t) seq);
    unkey(&k);
    return out;
}

/* The length a packet's first four bytes give, once decrypted where the
 * cipher encrypts it; -1 when they cannot be read. */
int32_t ssh_crypto_openLength(int32_t which, void *key, int32_t seq, void *first) {
    const ssh_cipheralg *alg = cipher_of(which);
    if (alg == NULL || len(first) != 4) return -1;
    uint8_t field[4];
    memcpy(field, ((geng_bytes *) first)->data, 4);
    if (alg->flags & SSH_CIPHER_SEPARATE_LENGTH) {
        if (len(key) != (size_t) alg->padded_keybytes) return -1;
        ssh_cipher *c = ssh_cipher_new(alg);
        ssh_cipher_setkey(c, ((geng_bytes *) key)->data);
        ssh_cipher_decrypt_length(c, field, 4, (uint32_t) seq);
        ssh_cipher_free(c);
    }
    uint32_t length = GET_32BIT_MSB_FIRST(field);
    return length > INT32_MAX ? -1 : (int32_t) length;
}

/* A sealed packet opened: `sealed` is its four length bytes as they came,
 * the rest, and the tag. The answer is the packet in the clear, as `seal`
 * was given it, or empty when the tag does not hold. */
void *ssh_crypto_open(int32_t which, void *key, void *iv, int32_t seq, int32_t count, void *sealed) {
    size_t n = len(sealed);
    const ssh_cipheralg *alg = cipher_of(which);
    if (alg == NULL || n < 8 + 16 || (n - 16 - 4) % (size_t) alg->blksize != 0) return none();
    keyed k;
    if (!key_for(which, key, iv, (uint32_t) count, &k)) return none();
    /* In the order PuTTY's own reader takes (ssh/bpp2.c): the length, then
     * the tag over the packet as it came, then the rest. */
    uint8_t *data = ((geng_bytes *) sealed)->data;
    uint8_t field[4];
    memcpy(field, data, 4);
    if (alg->flags & SSH_CIPHER_SEPARATE_LENGTH) ssh_cipher_decrypt_length(k.cipher, field, 4, (uint32_t) seq);
    if (!ssh2_mac_verify(k.mac, data, (int) (n - 16), (uint32_t) seq)) {
        unkey(&k);
        return none();
    }
    geng_bytes *out = bytes_of(data, n - 16);
    memcpy(out->data, field, 4);
    ssh_cipher_decrypt(k.cipher, out->data + 4, (int) (n - 16 - 4));
    unkey(&k);
    return out;
}


/* KEY FILES */

/* AES in counter mode, which an OpenSSH key file's private part is
 * encrypted with: a 16- or 32-byte key, a 16-byte counter block. */
void *ssh_crypto_aesCtr(void *key, void *iv, void *data) {
    const ssh_cipheralg *alg = len(key) == 16 ? &ssh_aes128_sdctr : len(key) == 32 ? &ssh_aes256_sdctr : NULL;
    if (alg == NULL || len(iv) != 16 || len(data) % 16 != 0) return none();
    ssh_cipher *c = ssh_cipher_new(alg);
    ssh_cipher_setkey(c, ((geng_bytes *) key)->data);
    ssh_cipher_setiv(c, ((geng_bytes *) iv)->data);
    geng_bytes *out = bytes_of(((geng_bytes *) data)->data, len(data));
    if (out->length > 0) ssh_cipher_decrypt(c, out->data, out->length);
    ssh_cipher_free(c);
    return out;
}

/* OpenSSH's bcrypt_pbkdf: `length` bytes from a passphrase and a salt over
 * `rounds` rounds. */
void *ssh_crypto_bcryptPbkdf(void *passphrase, void *salt, int32_t rounds, int32_t length) {
    if (rounds < 1 || length < 1 || length > 1024 || len(salt) == 0) return none();
    geng_bytes *out = bytes_alloc((size_t) length);
    openssh_bcrypt(pl(passphrase), pl(salt), rounds, out->data, (size_t) length);
    return out;
}

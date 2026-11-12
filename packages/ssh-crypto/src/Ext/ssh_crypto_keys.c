/* ssh-crypto's private keys (puritty docs/ssh-client.md SC6, SC11 step 6):
 * an OpenSSH key file (PROTOCOL.key) read, decrypted and kept in C, and
 * signatures made with it.
 *
 * A private key never becomes Geng bytes (SC12 question 7): the file is
 * decrypted into malloc'd memory, PuTTY makes its `ssh_key` of it, and that
 * memory is cleared. Geng holds a handle, `key_handle`, whose `key` is the
 * `ssh_key`; `forget` frees it, and PuTTY clears a key's numbers as it frees
 * them. A handle forgotten while a signature is being made is freed when the
 * signature is done.
 *
 * `bcrypt_pbkdf` takes about 6 ms a round, and an RSA signature some
 * milliseconds, so both run on a thread of their own (D897) and answer
 * through a post, and the window keeps drawing meanwhile. The thread is
 * handed malloc'd copies of what it needs and holds no Geng value. */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "ssh_crypto_config.h"
#include "putty/ssh.h"
#include "ssh_crypto_lock.h"

#include "geng.h"

/* What a key row fails with: `SshCrypto.KeyProblem`'s constructors. */
enum { NOT_A_KEY_FILE = 1, WRONG_PASSPHRASE, UNSUPPORTED_ENCRYPTION, UNSUPPORTED_KEY, MALFORMED, FORGOTTEN, NO_MEMORY };

static geng_bytes *bytes_of(const void *s, size_t n) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b + n, GENG_HEADER_BYTES(sizeof *b + n));
    b->length = (int32_t) n;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    if (n > 0) memcpy(b->data, s, n);
    return b;
}

static ptrlen pl(void *bytes) {
    geng_bytes *b = bytes;
    return make_ptrlen(b->data, (size_t) b->length);
}

static void fail(geng_wait *wait, int code) { geng_fail(wait, geng_slot_I4(code)); }


/* THE FILE */

static int b64_value(int c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

/* The binary between OpenSSH's armor lines, in a strbuf, or NULL. */
static strbuf *dearmor(ptrlen text) {
    static const char begin[] = "-----BEGIN OPENSSH PRIVATE KEY-----", end[] = "-----END OPENSSH PRIVATE KEY-----";
    const char *s = text.ptr, *limit = s + text.len;
    const char *b = NULL;
    for (const char *p = s; p + sizeof begin - 1 <= limit; p++)
        if (memcmp(p, begin, sizeof begin - 1) == 0) {
            b = p + sizeof begin - 1;
            break;
        }
    if (b == NULL) return NULL;
    strbuf *out = strbuf_new_nm();
    unsigned acc = 0;
    int bits = 0;
    for (const char *p = b; p < limit; p++) {
        if (*p == '-') {
            if ((size_t) (limit - p) >= sizeof end - 1 && memcmp(p, end, sizeof end - 1) == 0) return out;
            break;
        }
        if (*p == '=' || *p == '\r' || *p == '\n' || *p == ' ' || *p == '\t') continue;
        int v = b64_value((unsigned char) *p);
        if (v < 0) break;
        acc = (acc << 6) | (unsigned) v;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            put_byte(out, (acc >> bits) & 0xff);
        }
    }
    strbuf_free(out);
    return NULL;
}

/* A key file's outer parts (PROTOCOL.key): its cipher and KDF, the KDF's
 * salt and rounds, the one public key, and the private section. */
typedef struct {
    ptrlen cipher, kdf, salt, public_blob, private_section;
    unsigned rounds;
} key_file;

static int read_file(ptrlen binary, key_file *f) {
    static const char magic[] = "openssh-key-v1";
    if (binary.len < sizeof magic || memcmp(binary.ptr, magic, sizeof magic) != 0) return NOT_A_KEY_FILE;
    BinarySource src[1];
    BinarySource_BARE_INIT(src, (const char *) binary.ptr + sizeof magic, binary.len - sizeof magic);
    f->cipher = get_string(src);
    f->kdf = get_string(src);
    ptrlen options = get_string(src);
    unsigned count = get_uint32(src);
    f->public_blob = get_string(src);
    f->private_section = get_string(src);
    if (get_err(src)) return MALFORMED;
    if (count != 1) return UNSUPPORTED_KEY;
    f->salt = make_ptrlen(NULL, 0);
    f->rounds = 0;
    if (ptrlen_eq_string(f->kdf, "bcrypt")) {
        BinarySource opt[1];
        BinarySource_BARE_INIT_PL(opt, options);
        f->salt = get_string(opt);
        f->rounds = get_uint32(opt);
        if (get_err(opt) || f->salt.len == 0 || f->rounds == 0 || f->rounds > 1000000) return MALFORMED;
    } else if (!ptrlen_eq_string(f->kdf, "none")) {
        return UNSUPPORTED_ENCRYPTION;
    }
    if (ptrlen_eq_string(f->cipher, "none")) return ptrlen_eq_string(f->kdf, "none") ? 0 : MALFORMED;
    if (!ptrlen_eq_string(f->cipher, "aes256-ctr")) return UNSUPPORTED_ENCRYPTION;
    if (f->rounds == 0 || f->private_section.len % 16 != 0) return MALFORMED;
    return 0;
}

/* The key algorithm a private key type names, for the types this client
 * signs with. */
static const ssh_keyalg *private_alg(ptrlen type) {
    if (ptrlen_eq_string(type, "ssh-ed25519")) return &ssh_ecdsa_ed25519;
    if (ptrlen_eq_string(type, "ecdsa-sha2-nistp256")) return &ssh_ecdsa_nistp256;
    if (ptrlen_eq_string(type, "ecdsa-sha2-nistp384")) return &ssh_ecdsa_nistp384;
    if (ptrlen_eq_string(type, "ecdsa-sha2-nistp521")) return &ssh_ecdsa_nistp521;
    if (ptrlen_eq_string(type, "ssh-rsa")) return &ssh_rsa;
    return NULL;
}

/* The type a key blob names first. */
static ptrlen blob_type(ptrlen blob) {
    BinarySource src[1];
    BinarySource_BARE_INIT_PL(src, blob);
    return get_string(src);
}

/* What a key file says without its passphrase: 0 or 1 for whether it is
 * encrypted, then the public key blob; empty for a file that is not one
 * this client reads. */
void *ssh_crypto_keyFileInfo(void *text) {
    strbuf *binary = dearmor(pl(text));
    if (binary == NULL) return bytes_of(NULL, 0);
    key_file f;
    int problem = read_file(ptrlen_from_strbuf(binary), &f);
    geng_bytes *out;
    if (problem != 0 || private_alg(blob_type(f.public_blob)) == NULL) {
        out = bytes_of(NULL, 0);
    } else {
        strbuf *sb = strbuf_new();
        put_byte(sb, ptrlen_eq_string(f.cipher, "none") ? 0 : 1);
        put_datapl(sb, f.public_blob);
        out = bytes_of(sb->u, sb->len);
        strbuf_free(sb);
    }
    strbuf_free(binary);
    return out;
}


/* HANDLES */

/* `key` is PuTTY's key, or NULL once forgotten or before loading ends;
 * `busy` counts signatures in flight, which free a forgotten key when the
 * last is done. Held by a Geng object (`handle`), malloc'd itself, so a
 * thread may hold it while the program allocates. */
typedef struct {
    ssh_key *key;
    int busy;
    int forgotten;
} key_box;

typedef struct {
    key_box *box;
} key_handle;

#define KEY_HANDLE_HEADER (GENG_HEADER_WORDS(key_handle))

static void box_release(key_box *box) {
    if (box->forgotten && box->busy == 0) {
        if (box->key != NULL) ssh_key_free(box->key);
        box->key = NULL;
        free(box);
    }
}


/* LOADING */

/* What the thread is handed and answers with. */
typedef struct {
    geng_post *post;
    strbuf *binary;
    key_file f;
    char *passphrase;
    size_t passphrase_len;
    int problem;
    ssh_key *key;
} loading;

/* The private section decrypted (if it is encrypted), its check words
 * compared, and PuTTY's key made of it; every copy of a secret cleared. */
static void load_now(loading *l) {
    key_file *f = &l->f;
    size_t n = f->private_section.len;
    unsigned char *plain = safemalloc(n ? n : 1, 1, 0);
    memcpy(plain, f->private_section.ptr, n);
    if (!ptrlen_eq_string(f->cipher, "none")) {
        unsigned char kiv[48];
        openssh_bcrypt(make_ptrlen(l->passphrase, l->passphrase_len), f->salt, (int) f->rounds, kiv, sizeof kiv);
        ssh_cipher *c = ssh_cipher_new(&ssh_aes256_sdctr);
        ssh_cipher_setkey(c, kiv);
        ssh_cipher_setiv(c, kiv + 32);
        if (n > 0) ssh_cipher_decrypt(c, plain, (int) n);
        ssh_cipher_free(c);
        smemclr(kiv, sizeof kiv);
    }
    BinarySource src[1];
    BinarySource_BARE_INIT(src, plain, n);
    unsigned check1 = get_uint32(src), check2 = get_uint32(src);
    if (get_err(src) || check1 != check2) {
        l->problem = ptrlen_eq_string(f->cipher, "none") ? MALFORMED : WRONG_PASSPHRASE;
    } else {
        const ssh_keyalg *alg = private_alg(get_string(src));
        if (alg == NULL) l->problem = UNSUPPORTED_KEY;
        else {
            ssh_crypto_curves_lock();
            l->key = ssh_key_new_priv_openssh(alg, src);
            ssh_crypto_curves_unlock();
            if (l->key == NULL || get_err(src)) {
                if (l->key != NULL) ssh_key_free(l->key);
                l->key = NULL;
                l->problem = MALFORMED;
            }
        }
    }
    smemclr(plain, n);
    sfree(plain);
    smemclr(l->passphrase, l->passphrase_len);
    sfree(l->passphrase);
    l->passphrase = NULL;
}

/* Once the send answers 1, `l` is the program thread's, which frees it
 * when it takes the message, maybe before this thread runs on: the post is
 * read before the send, never from `l` after it. */
static void *load_run(void *arg) {
    loading *l = arg;
    load_now(l);
    geng_post *post = l->post;
    if (!geng_post_send(post, l)) {
        if (l->key != NULL) ssh_key_free(l->key);
        strbuf_free(l->binary);
        free(l);
    }
    geng_post_done(post);
    return NULL;
}

static void loaded(void *env, void *message) {
    loading *l = message;
    geng_post_close(l->post);
    if (l->problem != 0) {
        fail(env, l->problem);
    } else {
        key_box *box = calloc(1, sizeof *box);
        if (box == NULL) {
            ssh_key_free(l->key);
            fail(env, NO_MEMORY);
        } else {
            box->key = l->key;
            key_handle *h = geng_alloc(sizeof *h, KEY_HANDLE_HEADER);
            h->box = box;
            geng_succeed(env, geng_slot_P(h));
        }
    }
    strbuf_free(l->binary);
    free(l);
}

static void dropped(void *message) {
    loading *l = message;
    if (l->key != NULL) ssh_key_free(l->key);
    strbuf_free(l->binary);
    free(l);
}

static geng_task *load_stop(void *env) {
    geng_post_close(env);
    return NULL;
}

/* A key file's private key, decrypted with the passphrase (ignored for one
 * not encrypted), on a thread. */
geng_cancel ssh_crypto_loadKey(void *text, void *passphrase, geng_wait *wait) {
    strbuf *binary = dearmor(pl(text));
    if (binary == NULL) {
        fail(wait, NOT_A_KEY_FILE);
        return (geng_cancel) {0};
    }
    loading *l = calloc(1, sizeof *l);
    if (l == NULL) geng_crash("ssh-crypto: out of memory");
    l->binary = binary;
    l->problem = read_file(ptrlen_from_strbuf(binary), &l->f);
    if (l->problem != 0) {
        int problem = l->problem;
        strbuf_free(binary);
        free(l);
        fail(wait, problem);
        return (geng_cancel) {0};
    }
    ptrlen p = pl(passphrase);
    l->passphrase = safemalloc(p.len ? p.len : 1, 1, 0);
    memcpy(l->passphrase, p.ptr, p.len);
    l->passphrase_len = p.len;
    geng_post *post = geng_post_open(loaded, dropped, wait);
    l->post = post;
    if (post == NULL || geng_thread_start(load_run, l) != 0) {
        if (post != NULL) {
            geng_post_close(post);
            geng_post_done(post);
        }
        smemclr(l->passphrase, l->passphrase_len);
        sfree(l->passphrase);
        strbuf_free(binary);
        free(l);
        fail(wait, NO_MEMORY);
        return (geng_cancel) {0};
    }
    /* `l` is the thread's now (it is freed once its message is taken, on
     * this thread, so not before this returns); the post is read from a
     * local all the same, as every thread start reads what it hands over */
    return (geng_cancel) {load_stop, post};
}

/* The key's public blob, which a userauth request and an agent name it by. */
geng_cancel ssh_crypto_keyPublicBlob(void *handle, geng_wait *wait) {
    key_box *box = ((key_handle *) handle)->box;
    if (box == NULL || box->forgotten || box->key == NULL) {
        fail(wait, FORGOTTEN);
        return (geng_cancel) {0};
    }
    strbuf *sb = strbuf_new();
    ssh_crypto_curves_lock();
    ssh_key_public_blob(box->key, BinarySink_UPCAST(sb));
    ssh_crypto_curves_unlock();
    geng_succeed(wait, geng_slot_P(bytes_of(sb->u, sb->len)));
    strbuf_free(sb);
    return (geng_cancel) {0};
}

/* The key freed and its numbers cleared, once no signature needs it.
 * Forgetting one twice is not an error. */
geng_cancel ssh_crypto_forgetKey(void *handle, geng_wait *wait) {
    key_handle *h = handle;
    if (h->box != NULL) {
        h->box->forgotten = 1;
        box_release(h->box);
        h->box = NULL;
    }
    geng_succeed(wait, geng_slot_U(0));
    return (geng_cancel) {0};
}


/* SIGNING */

/* A signature in flight. `canceled`: its task was canceled, and the
 * answer is dropped when it comes. The post stays open until then, so the
 * thread always hands the signing back and the key's box is always
 * released on the program's thread. */
typedef struct {
    geng_post *post;
    key_box *box;
    unsigned flags;
    int canceled;
    strbuf *data;
    strbuf *signature;
} signing;

static void *sign_run(void *arg) {
    signing *s = arg;
    s->signature = strbuf_new();
    ssh_crypto_curves_lock();
    ssh_key_sign(s->box->key, ptrlen_from_strbuf(s->data), s->flags, BinarySink_UPCAST(s->signature));
    ssh_crypto_curves_unlock();
    /* `s` is the program thread's once sent, as `load_run`'s is */
    geng_post *post = s->post;
    if (!geng_post_send(post, s)) geng_crash("ssh-crypto: a signature could not be handed back");
    geng_post_done(post);
    return NULL;
}

static void sign_finished(signing *s) {
    s->box->busy--;
    box_release(s->box);
    strbuf_free(s->signature);
    strbuf_free(s->data);
    free(s);
}

static void signed_(void *env, void *message) {
    signing *s = message;
    geng_post_close(s->post);
    if (!s->canceled) geng_succeed(env, geng_slot_P(bytes_of(s->signature->u, s->signature->len)));
    sign_finished(s);
}

static void sign_dropped(void *message) { sign_finished(message); }

static geng_task *sign_stop(void *env) {
    signing *s = env;
    s->canceled = 1;
    return NULL;
}

/* A signature of `data` by the key, as SSH's signature blob, on a thread:
 * `algorithm` is the signature algorithm the server takes, which for an
 * RSA key is rsa-sha2-512 or rsa-sha2-256. */
geng_cancel ssh_crypto_sign(void *handle, void *algorithm, void *data, geng_wait *wait) {
    key_box *box = ((key_handle *) handle)->box;
    if (box == NULL || box->forgotten || box->key == NULL) {
        fail(wait, FORGOTTEN);
        return (geng_cancel) {0};
    }
    ptrlen alg = pl(algorithm);
    unsigned flags = ptrlen_eq_string(alg, "rsa-sha2-512") ? SSH_AGENT_RSA_SHA2_512
                   : ptrlen_eq_string(alg, "rsa-sha2-256") ? SSH_AGENT_RSA_SHA2_256
                                                          : 0;
    signing *s = calloc(1, sizeof *s);
    if (s == NULL) geng_crash("ssh-crypto: out of memory");
    s->box = box;
    s->flags = flags;
    s->data = strbuf_new();
    put_datapl(s->data, pl(data));
    box->busy++;
    s->post = geng_post_open(signed_, sign_dropped, wait);
    if (s->post == NULL || geng_thread_start(sign_run, s) != 0) {
        if (s->post != NULL) {
            geng_post_close(s->post);
            geng_post_done(s->post);
        }
        box->busy--;
        strbuf_free(s->data);
        free(s);
        fail(wait, NO_MEMORY);
        return (geng_cancel) {0};
    }
    return (geng_cancel) {sign_stop, s};
}

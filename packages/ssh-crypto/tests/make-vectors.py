#!/usr/bin/env python3
"""The ssh-crypto tests' vectors (docs/ssh-client.md SC11 step 3), each from
somewhere other than PuTTY: the RFCs' and NIST's own examples, Wycheproof
(vendor/wycheproof), Python's hashlib, hmac and `cryptography`, and OpenSSH's
ssh-keygen, written to tests/vectors.txt, one test a line:

    KIND field=HEX ...

usage: packages/ssh-crypto/tests/make-vectors.py   (from puritty's checkout)
"""

import base64
import hashlib
import hmac
import json
import os
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.poly1305 import Poly1305

HERE = Path(__file__).resolve().parent
WYCHEPROOF = HERE.parents[2] / "vendor" / "wycheproof" / "testvectors_v1"
rng = random.Random(20261110)
lines = []


def h(b: bytes) -> str:
    return b.hex() if b else "-"


def emit(kind, **fields):
    # an `id` names a Wycheproof case, and is written as it is
    lines.append(kind + " " + " ".join(f"{k}={v if k == 'id' else h(v) if isinstance(v, (bytes, bytearray)) else v}" for k, v in fields.items()))


def rbytes(n):
    return bytes(rng.getrandbits(8) for _ in range(n))


def string(b: bytes) -> bytes:
    return struct.pack(">I", len(b)) + b


def mpint(n: int) -> bytes:
    if n == 0:
        return string(b"")
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    if b[0] & 0x80:
        b = b"\0" + b
    return string(b)


def wycheproof(name):
    return json.loads((WYCHEPROOF / name).read_text())


# HASHES: FIPS 180's examples, then random lengths against hashlib

HASHES = [(0, hashlib.sha1), (1, hashlib.sha256), (2, hashlib.sha384), (3, hashlib.sha512)]
for which, f in HASHES:
    for data in [b"", b"abc", b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"]:
        emit("hash", which=which, data=data, out=f(data).digest())
    emit("hashrepeat", which=which, byte=b"a", count=1000000, out=f(b"a" * 1000000).digest())
    for n in [1, 55, 56, 63, 64, 65, 111, 112, 127, 128, 129, 1000, 4097]:
        data = rbytes(n)
        emit("hash", which=which, data=data, out=f(data).digest())

# HMAC: RFC 4231's (SHA-256, SHA-512) and RFC 2202's (SHA-1) first cases,
# then random keys and data, the long keys among them, against hmac

MACS = [(0, hashlib.sha1), (1, hashlib.sha256), (2, hashlib.sha512)]
for which, f in MACS:
    for key, data in [(b"\x0b" * 20, b"Hi There"), (b"Jefe", b"what do ya want for nothing?"),
                      (b"\xaa" * 131, b"Test Using Larger Than Block-Size Key - Hash Key First")]:
        emit("hmac", which=which, key=key, data=data, out=hmac.new(key, data, f).digest())
    for kn in [1, 16, 20, 32, 64, 65, 128, 129, 200]:
        key, data = rbytes(kn), rbytes(rng.randrange(0, 300))
        emit("hmac", which=which, key=key, data=data, out=hmac.new(key, data, f).digest())

# X25519: RFC 7748 §6.1's two parties, then Wycheproof. K is what the
# exchange takes: the 32 bytes read as one big-endian number, an mpint.

alice = bytes.fromhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")
alice_pub = bytes.fromhex("8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")
bob = bytes.fromhex("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb")
bob_pub = bytes.fromhex("de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f")
shared = bytes.fromhex("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")
emit("x25519pub", secret=alice, pub=alice_pub)
emit("x25519pub", secret=bob, pub=bob_pub)
emit("x25519", secret=alice, theirs=bob_pub, k=mpint(int.from_bytes(shared, "big")), result=1)
emit("x25519", secret=bob, theirs=alice_pub, k=mpint(int.from_bytes(shared, "big")), result=1)
skipped = {}
for group in wycheproof("x25519_test.json")["testGroups"]:
    for t in group["tests"]:
        if t["result"] == "acceptable":
            skipped["x25519 acceptable"] = skipped.get("x25519 acceptable", 0) + 1
            continue
        priv, pub, out = bytes.fromhex(t["private"]), bytes.fromhex(t["public"]), bytes.fromhex(t["shared"])
        if len(pub) != 32 or len(priv) != 32:
            emit("x25519", secret=priv, theirs=pub, k=b"", result=0)
        elif t["result"] == "valid" and out != bytes(32):
            emit("x25519", secret=priv, theirs=pub, k=mpint(int.from_bytes(out, "big")), result=1)
        else:
            emit("x25519", secret=priv, theirs=pub, k=b"", result=0)

# SIGNATURES: Wycheproof's, written as SSH's blobs. A Wycheproof signature
# that is not one SSH can carry (DER that does not parse) is left out and
# counted.


def der_ints(sig: bytes):
    """r and s of a DER ECDSA signature, or None for anything not strict DER."""
    def length(b, i):
        if b[i] < 0x80:
            return b[i], i + 1
        if b[i] == 0x81 and b[i + 1] >= 0x80:
            return b[i + 1], i + 2
        raise ValueError

    def integer(b, i):
        if b[i] != 0x02:
            raise ValueError
        n, i = length(b, i + 1)
        v = b[i:i + n]
        if n == 0 or len(v) != n or (n > 1 and v[0] == 0 and v[1] < 0x80) or v[0] & 0x80:
            raise ValueError
        return int.from_bytes(v, "big"), i + n

    try:
        if sig[0] != 0x30:
            return None
        n, i = length(sig, 1)
        if i + n != len(sig):
            return None
        r, i = integer(sig, i)
        s, i = integer(sig, i)
        return (r, s) if i == len(sig) else None
    except (ValueError, IndexError):
        return None


for group in wycheproof("ed25519_test.json")["testGroups"]:
    pk = bytes.fromhex(group["publicKey"]["pk"])
    blob = string(b"ssh-ed25519") + string(pk)
    for t in group["tests"]:
        if t["result"] == "acceptable":
            skipped["ed25519 acceptable"] = skipped.get("ed25519 acceptable", 0) + 1
            continue
        sig = string(b"ssh-ed25519") + string(bytes.fromhex(t["sig"]))
        emit("verify", id=f"ed25519/{t['tcId']}", alg=b"ssh-ed25519", pub=blob, sig=sig, data=bytes.fromhex(t["msg"]), result=1 if t["result"] == "valid" else 0)

for group in wycheproof("ecdsa_secp256r1_sha256_test.json")["testGroups"]:
    point = bytes.fromhex(group["publicKey"]["uncompressed"])
    blob = string(b"ecdsa-sha2-nistp256") + string(b"nistp256") + string(point)
    for t in group["tests"]:
        rs = der_ints(bytes.fromhex(t["sig"]))
        if rs is None:
            skipped["ecdsa not DER"] = skipped.get("ecdsa not DER", 0) + 1
            continue
        if t["result"] == "acceptable":
            skipped["ecdsa acceptable"] = skipped.get("ecdsa acceptable", 0) + 1
            continue
        sig = string(b"ecdsa-sha2-nistp256") + string(mpint(rs[0]) + mpint(rs[1]))
        emit("verify", id=f"p256/{t['tcId']}", alg=b"ecdsa-sha2-nistp256", pub=blob, sig=sig, data=bytes.fromhex(t["msg"]), result=1 if t["result"] == "valid" else 0)

for name, alg in [("rsa_signature_2048_sha256_test.json", b"rsa-sha2-256"), ("rsa_signature_3072_sha256_test.json", b"rsa-sha2-256"),
                  ("rsa_signature_4096_sha256_test.json", b"rsa-sha2-256"), ("rsa_signature_2048_sha512_test.json", b"rsa-sha2-512"),
                  ("rsa_signature_3072_sha512_test.json", b"rsa-sha2-512"), ("rsa_signature_4096_sha512_test.json", b"rsa-sha2-512")]:
    for group in wycheproof(name)["testGroups"]:
        pk = group["publicKey"]
        n, e = int(pk["modulus"], 16), int(pk["publicExponent"], 16)
        blob = string(b"ssh-rsa") + mpint(e) + mpint(n)
        for t in group["tests"]:
            if t["result"] == "acceptable":
                skipped["rsa acceptable"] = skipped.get("rsa acceptable", 0) + 1
                continue
            sig = string(alg) + string(bytes.fromhex(t["sig"]))
            emit("verify", id=f"{name.split('_test')[0]}/{t['tcId']}", alg=alg, pub=blob, sig=sig, data=bytes.fromhex(t["msg"]), result=1 if t["result"] == "valid" else 0)

# A signature under one algorithm checked as another is refused.
emit("verify", alg=b"rsa-sha2-256", pub=blob, sig=string(b"rsa-sha2-512") + string(rbytes(512)), data=b"x", result=0)
emit("verify", alg=b"ssh-dss", pub=blob, sig=b"", data=b"x", result=0)

# OpenSSH's own signatures (ssh-keygen -Y sign), one per key type: the data
# signed is SSHSIG's (OpenSSH's PROTOCOL.sshsig).
work = Path(tempfile.mkdtemp(prefix="ssh-crypto-vectors-"))
message = b"puritty ssh-crypto\n"
(work / "message").write_bytes(message)
for keytype, bits, sigalg in [("ed25519", None, b"ssh-ed25519"), ("ecdsa", "256", b"ecdsa-sha2-nistp256"), ("rsa", "3072", b"rsa-sha2-512")]:
    key = work / f"id_{keytype}"
    subprocess.run(["ssh-keygen", "-q", "-t", keytype, *(["-b", bits] if bits else []), "-N", "", "-f", str(key)], check=True)
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", "file", str(work / "message")], check=True)
    pub = base64.b64decode((work / f"id_{keytype}.pub").read_text().split()[1])
    armored = (work / "message.sig").read_text().splitlines()
    sshsig = base64.b64decode("".join(l for l in armored if not l.startswith("-----")))
    (work / "message.sig").unlink()
    # MAGIC, version, publickey, namespace, reserved, hash_algorithm, signature
    i = 6 + 4
    fields = []
    for _ in range(5):
        n = struct.unpack(">I", sshsig[i:i + 4])[0]
        fields.append(sshsig[i + 4:i + 4 + n])
        i += 4 + n
    _, namespace, reserved, hash_alg, signature = fields
    digest = hashlib.sha512(message).digest() if hash_alg == b"sha512" else hashlib.sha256(message).digest()
    signed = b"SSHSIG" + string(namespace) + string(reserved) + string(hash_alg) + string(digest)
    emit("verify", alg=sigalg, pub=pub, sig=signature, data=signed, result=1)
    emit("verify", alg=sigalg, pub=pub, sig=signature, data=signed + b"x", result=0)

# PACKETS: OpenSSH's chacha20-poly1305@openssh.com (PROTOCOL.chacha20poly1305)
# and aes*-gcm@openssh.com (RFC 5647, PROTOCOL), written here from
# `cryptography`'s ChaCha20, Poly1305 and AES-GCM.


def chacha(key, seq, counter, data):
    nonce = counter.to_bytes(8, "little") + seq.to_bytes(8, "big")
    return Cipher(algorithms.ChaCha20(key, nonce), None).encryptor().update(data)


def chacha_seal(key, seq, packet):
    main, header = key[:32], key[32:]
    length = chacha(header, seq, 0, packet[:4])
    body = chacha(main, seq, 1, packet[4:])
    poly = chacha(main, seq, 0, bytes(32))
    return length + body + Poly1305.generate_tag(poly, length + body)


def gcm_seal(key, iv, count, packet):
    nonce = iv[:4] + ((int.from_bytes(iv[4:], "big") + count) % 2**64).to_bytes(8, "big")
    return packet[:4] + AESGCM(key).encrypt(nonce, packet[4:], packet[:4])


def packet(block, payload):
    padding = 4 + (block - (1 + len(payload) + 4) % block) % block
    return struct.pack(">IB", 1 + len(payload) + padding, padding) + payload + rbytes(padding)


for cipher, keylen, block in [(0, 64, 8), (1, 16, 16), (2, 32, 16)]:
    for k in range(12):
        key, iv = rbytes(keylen), (rbytes(12) if cipher else b"")
        if k == 1 and cipher:
            iv = iv[:4] + b"\xff" * 8          # the counter wraps
        seq = [0, 1, 2**31, 2**32 - 1][k % 4] if k < 4 else rng.getrandbits(32)
        count = [0, 3, 1000, 2**31 - 1][k % 4] if cipher else 0
        plain = packet(block, rbytes([0, 1, 31, 32, 100, 1000, 32768][k % 7]))
        sealed = chacha_seal(key, seq, plain) if cipher == 0 else gcm_seal(key, iv, count, plain)
        # Geng's Int is 32 bits: a sequence number of 2^31 or more is written
        # as the signed number of the same bits, as SshCrypto takes it
        emit("packet", cipher=cipher, key=key, iv=iv, seq=seq if seq < 2**31 else seq - 2**32, count=count, plain=plain, sealed=sealed)

# AES-CTR: SP 800-38A F.5.1 and F.5.5, then random against `cryptography`

sp_iv = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff")
sp_plain = bytes.fromhex("6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710")
emit("aesctr", key=bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c"), iv=sp_iv, data=sp_plain,
     out=bytes.fromhex("874d6191b620e3261bef6864990db6ce9806f66b7970fdff8617187bb9fffdff5ae4df3edbd5d35e5b4f09020db03eab1e031dda2fbe03d1792170a0f3009cee"))
emit("aesctr", key=bytes.fromhex("603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4"), iv=sp_iv, data=sp_plain,
     out=bytes.fromhex("601ec313775789a5b7a7f504bbf3d228f443e3ca4d62b59aca84e990cacaf5c52b0930daa23de94ce87017ba2d84988ddfc9c58db67aada613c2dd08457941a6"))
for keylen in [16, 32]:
    for n in [0, 16, 64, 4096]:
        key, iv, data = rbytes(keylen), b"\xff" * 8 + rbytes(8), rbytes(n)
        out = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor().update(data)
        emit("aesctr", key=key, iv=iv, data=data, out=out)

# KEY FILES: ssh-keygen's, with a passphrase. bcrypt_pbkdf gives the AES
# key and IV; the private part decrypted begins with two equal check words
# and holds the public key.

for keytype, rounds in [("ed25519", 16), ("ecdsa", 4), ("rsa", 1)]:
    key = work / f"locked_{keytype}"
    subprocess.run(["ssh-keygen", "-q", "-t", keytype, "-a", str(rounds), "-N", "hunter2", "-f", str(key)], check=True)
    pub = base64.b64decode((work / f"locked_{keytype}.pub").read_text().split()[1])
    body = base64.b64decode("".join(l for l in key.read_text().splitlines() if not l.startswith("-----")))
    assert body.startswith(b"openssh-key-v1\0")
    i = len(b"openssh-key-v1\0")
    parts = []
    for _ in range(3):
        n = struct.unpack(">I", body[i:i + 4])[0]
        parts.append(body[i + 4:i + 4 + n])
        i += 4 + n
    ciphername, kdfname, kdfoptions = parts
    assert ciphername == b"aes256-ctr" and kdfname == b"bcrypt", (ciphername, kdfname)
    salt_n = struct.unpack(">I", kdfoptions[:4])[0]
    salt, file_rounds = kdfoptions[4:4 + salt_n], struct.unpack(">I", kdfoptions[4 + salt_n:8 + salt_n])[0]
    i += 4  # the number of keys, 1
    n = struct.unpack(">I", body[i:i + 4])[0]
    i += 4 + n  # the public key
    n = struct.unpack(">I", body[i:i + 4])[0]
    encrypted = body[i + 4:i + 4 + n]
    emit("keyfile", passphrase=b"hunter2", salt=salt, rounds=file_rounds, encrypted=encrypted, pub=pub)

# PRIVATE KEYS: ssh-keygen's files, each type this client signs with, with a
# passphrase and without; the test loads each, holds its public key to the
# .pub file's, signs, and checks the signature with `verify`.

for keytype, bits, sigalgs in [("ed25519", None, ["ssh-ed25519"]), ("ecdsa", "256", ["ecdsa-sha2-nistp256"]),
                               ("ecdsa", "384", ["ecdsa-sha2-nistp384"]), ("ecdsa", "521", ["ecdsa-sha2-nistp521"]),
                               ("rsa", "2048", ["rsa-sha2-256", "rsa-sha2-512"]), ("rsa", "3072", ["rsa-sha2-512"])]:
    for passphrase in [b"", b"correct horse"]:
        key = work / f"user_{keytype}_{bits}_{len(passphrase)}"
        subprocess.run(["ssh-keygen", "-q", "-t", keytype, *(["-b", bits] if bits else []), "-a", "4", "-N", passphrase.decode(), "-f", str(key)], check=True)
        pub = base64.b64decode((Path(str(key) + ".pub")).read_text().split()[1])
        for sigalg in sigalgs:
            emit("keyload", file=key.read_bytes(), passphrase=passphrase, pub=pub, encrypted=1 if passphrase else 0, alg=sigalg.encode())

subprocess.run(["rm", "-rf", str(work)], check=True)

(HERE / "vectors.txt").write_text(
    "# ssh-crypto's test vectors, from make-vectors.py; do not edit.\n"
    f"# Wycheproof {(WYCHEPROOF.parent / '.git').exists() and subprocess.run(['git', '-C', str(WYCHEPROOF.parent), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}\n"
    + "".join(f"# left out: {k}: {v}\n" for k, v in sorted(skipped.items()))
    + "\n".join(lines) + "\n")
counts = {}
for l in lines:
    counts[l.split()[0]] = counts.get(l.split()[0], 0) + 1
print("wrote", len(lines), "vectors:", ", ".join(f"{k} {v}" for k, v in counts.items()), "; left out:", skipped)

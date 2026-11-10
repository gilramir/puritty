#!/usr/bin/env python3
"""The ssh transport's scripted server (docs/ssh-client.md SC11 step 4):
what sshd never does, done on purpose, and what ssh-tests says to it.

A small SSH server of its own, from `cryptography`: version, KEXINIT,
curve25519-sha256 with an Ed25519 host key, chacha20-poly1305@openssh.com
both ways, SERVICE_ACCEPT and USERAUTH_FAILURE, enough for ssh-tests'
`connect` to run through. Each case changes one thing, and ssh-tests'
lines are held to expected/scripted-CASE.txt.

usage (after tests/build.sh):
    packages/ssh/tests/scripted.py            every case
    packages/ssh/tests/scripted.py --update   write the pins; read the diff first
"""

import argparse
import hashlib
import os
import socket
import struct
import subprocess
import sys
import threading
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.poly1305 import Poly1305

HERE = Path(__file__).resolve().parent
PINS = HERE / "expected"
CLIENT = HERE / "ssh-tests"
VERSION = b"SSH-2.0-scripted_1"


def string(b):
    return struct.pack(">I", len(b)) + b


def namelist(names):
    return string(",".join(names).encode())


def mpint(b):
    n = int.from_bytes(b, "big")
    if n == 0:
        return string(b"")
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return string(b"\0" + raw if raw[0] & 0x80 else raw)


def raw(key):
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def chacha(key, seq, counter, data):
    return Cipher(algorithms.ChaCha20(key, counter.to_bytes(8, "little") + seq.to_bytes(8, "big")), None).encryptor().update(data)


class Conn:
    def __init__(self, sock):
        self.sock, self.buf = sock, b""
        self.seq_in = self.seq_out = 0
        self.key_in = self.key_out = None

    def recv(self, n):
        while len(self.buf) < n:
            more = self.sock.recv(65536)
            if not more:
                raise EOFError
            self.buf += more
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def line(self):
        while b"\n" not in self.buf:
            more = self.sock.recv(65536)
            if not more:
                raise EOFError
            self.buf += more
        i = self.buf.index(b"\n")
        out, self.buf = self.buf[:i].rstrip(b"\r"), self.buf[i + 1:]
        return out

    def frame(self, payload, padding=None):
        block = 8
        counted = 1 + len(payload) + (0 if self.key_out else 4)
        pad = padding if padding is not None else 4 + (block - (counted + 4) % block) % block
        return struct.pack(">IB", 1 + len(payload) + pad, pad) + payload + os.urandom(pad)

    def send(self, payload, padding=None, corrupt=False):
        plain = self.frame(payload, padding)
        if self.key_out:
            main, header = self.key_out[:32], self.key_out[32:]
            length = chacha(header, self.seq_out, 0, plain[:4])
            body = chacha(main, self.seq_out, 1, plain[4:])
            tag = Poly1305.generate_tag(chacha(main, self.seq_out, 0, bytes(32)), length + body)
            wire = length + body + tag
            if corrupt:
                wire = wire[:10] + bytes([wire[10] ^ 1]) + wire[11:]
        else:
            wire = plain
        self.sock.sendall(wire)
        self.seq_out = (self.seq_out + 1) % 2**32

    def read(self):
        if self.key_in:
            main, header = self.key_in[:32], self.key_in[32:]
            enc_len = self.recv(4)
            n = struct.unpack(">I", chacha(header, self.seq_in, 0, enc_len))[0]
            rest = self.recv(n + 16)
            body, tag = rest[:n], rest[n:]
            Poly1305.verify_tag(chacha(main, self.seq_in, 0, bytes(32)), enc_len + body, tag)
            plain = chacha(main, self.seq_in, 1, body)
        else:
            n = struct.unpack(">I", self.recv(4))[0]
            plain = self.recv(n)
        self.seq_in = (self.seq_in + 1) % 2**32
        pad = plain[0]
        payload = plain[1:len(plain) - pad]
        if payload[:1] == b"\x01":
            raise EOFError  # the client's DISCONNECT
        return payload


def read_strings(b, n):
    out, i = [], 0
    for _ in range(n):
        k = struct.unpack(">I", b[i:i + 4])[0]
        out.append(b[i + 4:i + 4 + k])
        i += 4 + k
    return out, i


class Server:
    """One connection, played as `case` says."""

    def __init__(self, case):
        self.case = case
        self.host = Ed25519PrivateKey.generate()
        self.other_host = Ed25519PrivateKey.generate()
        self.session_id = None
        self.strict = case not in ("ignore-first-not-strict",)

    def kexinit(self, first=True, follows=False):
        kex = ["ecdh-sha2-nistp256", "curve25519-sha256"] if follows else ["curve25519-sha256"]
        extras = (["ext-info-s"] + (["kex-strict-s-v00@openssh.com"] if self.strict else [])) if first else []
        return (bytes([20]) + os.urandom(16) + namelist(kex + extras) + namelist(["ssh-ed25519"])
                + namelist(["chacha20-poly1305@openssh.com"]) * 2 + namelist(["hmac-sha2-256"]) * 2
                + namelist(["none"]) * 2 + namelist([]) * 2 + bytes([1 if follows else 0]) + bytes(4))

    def exchange(self, c, client_version, first):
        case = self.case
        ours = self.kexinit(first, follows=case == "wrong-guess")
        if case == "second-kexinit" and first:
            c.send(ours)
        c.send(ours)
        if case == "wrong-guess" and first:
            c.send(bytes([31]) + string(b"a guess the client must drop"))
        if case == "newkeys-early" and first:
            c.send(bytes([21]))
        theirs = c.read()
        while theirs[0] != 20:
            theirs = c.read()
        init = c.read()
        q_c = read_strings(init[1:], 1)[0][0]
        eph = X25519PrivateKey.generate()
        q_s = bytes(32) if case == "zero-public" else raw(eph.public_key())
        shared = eph.exchange(X25519PublicKey.from_public_bytes(q_c)) if case != "zero-public" else bytes(32)
        host = self.other_host if (case == "hostkey-changes" and not first) else self.host
        k_s = string(b"ssh-ed25519") + string(raw(host.public_key()))
        k = mpint(shared)
        h = hashlib.sha256(string(client_version) + string(VERSION) + string(theirs) + string(ours) + string(k_s)
                           + string(q_c) + string(q_s) + k).digest()
        signed = h + (b"x" if case == "bad-signature" else b"")
        sig = string(b"ssh-ed25519") + string(host.sign(signed))
        c.send(bytes([31]) + string(k_s) + string(q_s) + string(sig))
        if self.session_id is None:
            self.session_id = h

        def derive(letter, n):
            out = hashlib.sha256(k + h + letter + self.session_id).digest()
            while len(out) < n:
                out += hashlib.sha256(k + h + out).digest()
            return out[:n]

        c.send(bytes([21]))
        c.key_out = derive(b"D", 64)
        # strict KEX resets at every NEWKEYS (draft-miller-sshm-strict-kex)
        if self.strict:
            c.seq_out = 0
        newkeys = c.read()
        assert newkeys[0] == 21, newkeys
        c.key_in = derive(b"C", 64)
        if self.strict:
            c.seq_in = 0

    def run(self, sock):
        c = Conn(sock)
        case = self.case
        if case == "ssh1":
            sock.sendall(b"SSH-1.5-old\r\n")
        elif case == "no-version":
            sock.sendall(b"x" * 9000)
        elif case == "banner":
            sock.sendall(b"Welcome.\r\nAuthorized use only.\r\n" + VERSION + b"\r\n")
        else:
            sock.sendall(VERSION + b"\r\n")
        client_version = c.line()
        if case in ("ssh1", "no-version"):
            c.read()
            return
        if case == "huge-length":
            sock.sendall(struct.pack(">I", 0x7FFFFFF0) + bytes(64))
            c.read()
            return
        if case == "short-padding":
            c.send(self.kexinit(), padding=3)
            c.read()
            c.read()
            return
        if case == "garbled-kexinit":
            c.send(self.kexinit()[:40])
            c.read()
            c.read()
            return
        if case in ("ignore-first", "ignore-first-not-strict"):
            c.send(bytes([2]) + string(b"before the KEXINIT"))
        self.exchange(c, client_version, True)
        request = c.read()
        assert request[0] == 5, request
        if case == "disconnect":
            c.send(bytes([1]) + struct.pack(">I", 11) + string(b"bye") + string(b""))
            return
        if case == "bad-mac":
            c.send(bytes([6]) + string(b"ssh-userauth"), corrupt=True)
            c.read()
            return
        if case in ("server-rekeys", "hostkey-changes"):
            self.exchange(c, client_version, False)
        c.send(bytes([6]) + string(b"ssh-userauth"))
        auth = c.read()
        assert auth[0] == 50, auth
        c.send(bytes([51]) + namelist(["publickey"]) + bytes([0]))
        c.read()


CASES = ["ok", "banner", "ssh1", "no-version", "huge-length", "short-padding", "garbled-kexinit", "ignore-first",
         "ignore-first-not-strict", "wrong-guess", "bad-signature", "zero-public", "newkeys-early", "second-kexinit",
         "bad-mac", "server-rekeys", "hostkey-changes", "disconnect"]


def run_case(case):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    failure = []

    def serve():
        sock, _ = listener.accept()
        try:
            Server(case).run(sock)
        except (EOFError, ConnectionError):
            pass
        except Exception as e:  # what the server saw that it did not expect
            failure.append(repr(e))
        finally:
            sock.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    out = subprocess.run([str(CLIENT), "connect", "127.0.0.1", str(port)], capture_output=True, text=True, timeout=30)
    t.join(5)
    listener.close()
    got = out.stdout + (f"[exit {out.returncode}]\n" if out.returncode else "")
    return got + "".join(f"[server: {f}]\n" for f in failure)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if not CLIENT.exists():
        sys.exit("scripted.py: build ssh-tests first (tests/build.sh)")
    fails = 0
    for case in CASES:
        got = run_case(case)
        pin = PINS / f"scripted-{case}.txt"
        if a.update:
            PINS.mkdir(exist_ok=True)
            pin.write_text(got)
            print(f"wrote {case}:\n  " + got.strip().replace("\n", "\n  "))
        elif not pin.exists() or pin.read_text() != got:
            fails += 1
            print(f"FAIL {case}\n  want {pin.read_text() if pin.exists() else '(no pin)'}\n  got  {got}")
        else:
            print(f"ok   {case}")
    if not a.update:
        print(f"{len(CASES) - fails} of {len(CASES)} cases pass")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""A signed exe checked against the unsigned one it was made from (the code
review's W17): run by scripts/sign-windows.sh on the build machine, after
the signed file comes back from the signing machine, before it replaces
the unsigned one.

  scripts/sign-check.py UNSIGNED SIGNED THUMBPRINT [CAFILE]

Three checks, each saying why it failed:

1. The bytes are those sent. Authenticode leaves a PE as it was but for
   the header's checksum and its certificate table entry, and appends the
   signature (after zeros to an 8-byte boundary): every other byte of the
   unsigned file must be in the signed one, unchanged, and the table must
   point past them.
2. The signature is good and the file's digest is its own (`osslsigncode
   verify`, against CAFILE or the system's certificates).
3. Its signer is the certificate THUMBPRINT names (the SHA-1 of its DER,
   as Windows shows it): `-require-leaf-hash`.

The signing machine's `signtool verify` said only that what it holds is
signed; nothing here checked that what came back is that file, nor whose
signature it carries.
"""
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pe_fields(data):
    """The offsets of the checksum and the certificate table entry."""
    if data[:2] != b"MZ":
        raise ValueError("not a PE file (no MZ)")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE file (no PE signature)")
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic == 0x20B:
        dirs = opt + 112
    elif magic == 0x10B:
        dirs = opt + 96
    else:
        raise ValueError(f"an optional header of magic {magic:#x}")
    return opt + 64, dirs + 4 * 8


def same_bytes(unsigned, signed):
    """Why the signed file is not the unsigned one with a signature, or None."""
    checksum, table = pe_fields(unsigned)
    if pe_fields(signed) != (checksum, table):
        return "the signed file's headers are not where the unsigned file's are"
    if len(signed) <= len(unsigned):
        return f"the signed file is {len(signed)} bytes, not longer than the {len(unsigned)} sent"
    skip = set(range(checksum, checksum + 4)) | set(range(table, table + 8))
    for i, (a, b) in enumerate(zip(unsigned, signed)):
        if a != b and i not in skip:
            return f"byte {i} of the file sent was changed ({a:#04x} to {b:#04x})"
    at, size = struct.unpack_from("<II", signed, table)
    if at < len(unsigned) or at + size > len(signed) or size == 0:
        return f"the certificate table ({at}, {size} bytes) is not after the file sent"
    if any(signed[len(unsigned):at]):
        return "something other than padding is between the file sent and its signature"
    return None


def osslsigncode():
    sys.path.insert(0, str(ROOT / "harness"))
    import pixels  # the pinned nixpkgs
    out = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", f"{pixels.NIXPKGS}#osslsigncode"],
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    return f"{out}/bin/osslsigncode"


def main():
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__.split("\n\n")[1])
    unsigned, signed = Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes()
    thumb = sys.argv[3].replace(":", "").replace(" ", "").upper()
    cafile = sys.argv[4] if len(sys.argv) == 5 else "/etc/ssl/certs/ca-certificates.crt"
    try:
        why = same_bytes(unsigned, signed)
    except (ValueError, struct.error) as e:
        why = str(e)
    if why:
        sys.exit(f"sign-check: {why}")
    r = subprocess.run([osslsigncode(), "verify", "-CAfile", cafile, "-require-leaf-hash", f"sha1:{thumb}",
                        "-in", sys.argv[2]], capture_output=True, text=True)
    if r.returncode != 0:
        said = [l.strip() for l in (r.stdout + r.stderr).splitlines()
                if "mismatch" in l or "failed" in l.lower() or "error" in l.lower()]
        sys.exit("sign-check: osslsigncode verify: " + ("; ".join(said[:3]) or f"exit {r.returncode}"))
    print(f"sign-check: {len(unsigned)} bytes sent, {len(signed)} signed: the same file, signed by {thumb}")


if __name__ == "__main__":
    main()

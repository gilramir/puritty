#!/usr/bin/env python3
"""known_hosts cases (docs/ssh-client.md SC11 step 5), written to
tests/known-hosts.txt: a file of every kind of line, the lines OpenSSH's
`ssh-keygen -F NAME` finds for each of a set of names, and what a key shown
for a host should be judged (Known, Unknown with the types the host has,
Changed with its lines, KeyRevoked) and how host key algorithms are
ordered for it.

usage: packages/ssh/tests/make-known-hosts.py
"""

import base64
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
work = Path(tempfile.mkdtemp(prefix="known-hosts-"))
keys = {}
for name, t, bits in [("e1", "ed25519", None), ("e2", "ed25519", None), ("e3", "ed25519", None), ("e4", "ed25519", None),
                      ("e5", "ed25519", None), ("e6", "ed25519", None), ("e7", "ed25519", None), ("e8", "ed25519", None),
                      ("p1", "ecdsa", "256"), ("p2", "ecdsa", "256"), ("r1", "rsa", "2048"), ("r2", "rsa", "2048")]:
    path = work / name
    subprocess.run(["ssh-keygen", "-q", "-t", t, *(["-b", bits] if bits else []), "-N", "", "-f", str(path)], check=True)
    keys[name] = (work / f"{name}.pub").read_text().split()[:2]


def k(name):
    return " ".join(keys[name])


# the two hashed lines, hashed by ssh-keygen -H
hashed = work / "hashed"
hashed.write_text(f"host6 {k('e4')}\n[host7]:2200 {k('e5')}\n")
subprocess.run(["ssh-keygen", "-q", "-H", "-f", str(hashed)], check=True, capture_output=True)
host6, host7 = hashed.read_text().splitlines()

text = "\n".join([
    "# a comment",
    f"host1 {k('e1')}",
    f"host2,host3 {k('p1')}",
    f"[host4]:2222 {k('e2')}",
    f"*.example.com {k('r1')}",
    f"*.example.com,!bad.example.com {k('e3')}",
    f"h?st5 {k('p2')}",
    host6,
    host7,
    f"@revoked * {k('e6')}",
    f"@cert-authority *.example.com {k('e7')}",
    "",
    "this line is not one",
    f"HOST8 {k('e8')}",
    f"host1 {k('r2')}",
    f"host9 ssh-ed25519 not-base64!",
    "",
])
kh = work / "known_hosts"
kh.write_text(text)
cert_lines = {i + 1 for i, l in enumerate(text.splitlines()) if l.startswith("@cert-authority")}

out = ["# known_hosts cases, from make-known-hosts.py; do not edit.", "file " + text.encode().hex()]
for name in ["host1", "HOST1", "host2", "host3", "host4", "[host4]:2222", "a.example.com", "bad.example.com", "host5",
             "hxst5", "host55", "host6", "[host7]:2200", "host7", "unknown", "host8"]:
    found = subprocess.run(["ssh-keygen", "-F", name, "-f", str(kh)], capture_output=True, text=True).stdout
    lines = sorted({int(m) for m in re.findall(r"found: line (\d+)", found)} - cert_lines)
    out.append(f"query name={name} lines={','.join(map(str, lines)) or '-'}")


def blob(name):
    return base64.b64decode(keys[name][1]).hex()


for name, key, verdict in [
    ("host1", "e1", "Known"), ("host1", "r2", "Known"), ("host1", "e2", "Changed:2"),
    ("host1", "p1", "Unknown:ssh-ed25519,ssh-rsa"), ("anything", "e6", "KeyRevoked"), ("host1", "e6", "KeyRevoked"),
    ("unknown", "e1", "Unknown:-"), ("bad.example.com", "e3", "Unknown:ssh-rsa"),
    ("a.example.com", "e3", "Known"), ("a.example.com", "e7", "Changed:6"),
    ("host6", "e4", "Known"), ("host6", "e1", "Changed:8"), ("[host7]:2200", "e5", "Known"), ("host7", "e5", "Unknown:-"),
    ("host8", "e8", "Known"),
]:
    out.append(f"check name={name} key={blob(key)} verdict={verdict}")

for name, order in [("host1", "ssh-ed25519,rsa-sha2-512,rsa-sha2-256,ecdsa-sha2-nistp256"),
                    ("host2", "ecdsa-sha2-nistp256,ssh-ed25519,rsa-sha2-512,rsa-sha2-256"),
                    ("unknown", "ssh-ed25519,ecdsa-sha2-nistp256,rsa-sha2-512,rsa-sha2-256")]:
    out.append(f"order name={name} algorithms={order}")

(HERE / "known-hosts.txt").write_text("\n".join(out) + "\n")
subprocess.run(["rm", "-rf", str(work)], check=True)
print("wrote", len(out) - 2, "known_hosts cases")

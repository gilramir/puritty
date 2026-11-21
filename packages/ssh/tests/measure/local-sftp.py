#!/usr/bin/env python3
"""An SFTP transfer over a channel beside a session, to a local sshd of
sshd.py's, timed by `ssh-tests session --transfer` (docs/sftp.md FT14,
FT17): no network, so what it shows is the client's own cost.

    measure/local-sftp.py [SIZE [PIECE [MOST]]]   (from packages/ssh/tests)
"""
import getpass, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import sshd  # noqa: E402

size, piece, most = (sys.argv[1:] + ["268435456", "32768", "64"][len(sys.argv) - 1:])[:3]
keys = sshd.user_keys()[0]
server = sshd.Server([f"Subsystem sftp {sshd.SFTP_SERVER}"])
try:
    kh = sshd.WORK / "known_hosts.measure"
    pub = (sshd.WORK / "keys" / "ssh_host_ed25519_key.pub").read_text().split()[:2]
    kh.write_text(f"[127.0.0.1]:{server.port} {' '.join(pub)}\n")
    with tempfile.TemporaryDirectory() as d:
        out = subprocess.run([str(HERE / "ssh-tests"), "session", "127.0.0.1", str(server.port), "--user", getpass.getuser(),
                              "--identity", keys["ed"], "--known-hosts", str(kh), "--strict", "yes", "--exec", "read x",
                              "--sftp", d, "--transfer", f"{size},{piece},{most}"], capture_output=True, text=True, timeout=600).stdout
    print("\n".join(l for l in out.splitlines() if "upload" in l or "download" in l))
finally:
    server.stop()

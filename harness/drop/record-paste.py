#!/usr/bin/env python3
"""Run in puritty's tab by harness/drop.py (docs/sftp.md FT22): turns
bracketed paste on, reads one paste, and writes its bytes to OUT, hex;
"nothing pasted" after 15 s.

    record-paste.py OUT
"""
import os, select, sys, termios, tty

out = sys.argv[1]
old = termios.tcgetattr(0)
tty.setraw(0)
os.write(1, b"\x1b[?2004h")
buf = b""
while b"\x1b[201~" not in buf:
    ready, _, _ = select.select([0], [], [], 15)
    if not ready:
        break
    piece = os.read(0, 4096)
    if not piece:
        break
    buf += piece
os.write(1, b"\x1b[?2004l")
termios.tcsetattr(0, termios.TCSADRAIN, old)
if b"\x1b[201~" not in buf:
    open(out, "w").write("nothing pasted\n")
else:
    open(out, "w").write(buf.split(b"\x1b[200~", 1)[-1].split(b"\x1b[201~", 1)[0].hex() + "\n")

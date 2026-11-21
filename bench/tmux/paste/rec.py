"""Records what a program reading the terminal gets, raw, every byte to
OUT until 3 s of quiet after the first: with BRACKETS 1 it turns
bracketed paste on (as a newer nano does), with 0 it does not (as an
older nano). docs/tmux.md TM95.
usage: rec.py OUT [BRACKETS]"""
import os, sys, termios, tty, select, time
out = open(sys.argv[1], "wb")
fd = 0
old = termios.tcgetattr(fd)
tty.setraw(fd)
os.write(1, (b"\x1b[?2004h" if len(sys.argv) < 3 or sys.argv[2] == "1" else b"") + b"ready\r\n")
got = False
try:
    while True:
        r, _, _ = select.select([fd], [], [], 3 if got else 60)
        if not r:
            break
        b = os.read(fd, 4096)
        if not b:
            break
        got = True
        out.write(b); out.flush()
finally:
    os.write(1, b"\x1b[?2004l")
    termios.tcsetattr(fd, termios.TCSADRAIN, old)

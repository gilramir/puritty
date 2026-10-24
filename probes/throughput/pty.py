#!/usr/bin/env python3
"""The PTY's own ceiling: a child cats each input to a 160x50 pty, and the
parent reads 64 KB at a time and throws it away. Prints ms per run, the time
from the fork to the child's exit, which is what inside.sh times in a terminal.

With RAW set, the child's pty is put in raw mode first, which turns off the
line discipline's output processing (OPOST, ONLCR) that a shell's pty has on.

usage: [RAW=1] python3 -I pty.py INPUTS [RUNS]
"""
import fcntl
import os
import pty
import struct
import sys
import termios
import time
import tty

IN = sys.argv[1]
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 5

for name in ("ls", "cup", "gitlog"):
    path = os.path.join(IN, name + ".txt")
    times = []
    for _ in range(RUNS):
        t0 = time.monotonic()
        pid, fd = pty.fork()
        if pid == 0:
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))
            if os.environ.get("RAW"):
                tty.setraw(1)
            os.execvp("cat", ["cat", path])
        while True:
            try:
                if not os.read(fd, 65536):
                    break
            except OSError:  # EIO once the child has gone and the pty is drained
                break
        os.waitpid(pid, 0)
        times.append((time.monotonic() - t0) * 1000)
        os.close(fd)
    print(name, " ".join("%.0f" % t for t in times))

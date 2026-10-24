#!/usr/bin/env python3
"""Captures vtebench's benchmarks as files, for the headless cores: each
benchmark's setup once, then its benchmark again and again, run in a 160x50
pty, until at least SIZE bytes have come out of it. What is captured is what a
terminal reads, after the line discipline. Writes DIR/vte-NAME.txt.

usage: python3 -I gen-vtebench.py BENCHMARKS DIR [SIZE]
       (BENCHMARKS: vtebench's share/vtebench/benchmarks)
"""
import fcntl
import os
import pty
import struct
import sys
import termios

SRC, OUT = sys.argv[1], sys.argv[2]
SIZE = int(sys.argv[3]) if len(sys.argv) > 3 else 8_000_000


def capture(script):
    pid, fd = pty.fork()
    if pid == 0:
        fcntl.ioctl(1, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))
        os.environ["TERM"] = "xterm-256color"
        os.execvp("bash", ["bash", "-c", script])
    out = bytearray()
    while True:
        try:
            got = os.read(fd, 65536)
        except OSError:
            break
        if not got:
            break
        out += got
    os.waitpid(pid, 0)
    os.close(fd)
    return bytes(out)


os.makedirs(OUT, exist_ok=True)
for name in sorted(os.listdir(SRC)):
    d = os.path.join(SRC, name)
    setup = os.path.join(d, "setup")
    data = capture(setup) if os.path.exists(setup) else b""
    one = capture(os.path.join(d, "benchmark"))
    data += one * -(-(SIZE - len(data)) // len(one))
    with open(os.path.join(OUT, "vte-" + name + ".txt"), "wb") as f:
        f.write(data)
    print(name, len(one), len(data))

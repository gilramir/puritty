#!/usr/bin/env python3
"""The floor of a paste through a pty (docs/phase3-select.md): SIZE bytes of
text written to the master in WRITE-byte writes, the master read all the
while, as visiterm's loop does since V48, into PROGRAM on the slave.

  paste.py SIZE WRITE PROGRAM...      e.g. paste.py 10485760 65536 cat

Prints the time to write it all, the time until the echo stops, and the
bytes read back. The text is gitlog.txt's, in lines.
"""
import os, pty, select, sys, time, tty

size, chunk = int(sys.argv[1]), int(sys.argv[2])
prog = sys.argv[3:]
src = os.path.join(os.path.dirname(__file__), "../../.harness-work/perf/inputs/gitlog.txt")
data = open(src, "rb").read(size).replace(b"\x1b", b"")
# a pty turns LF into CR LF on the way out and CR into LF on the way in, as
# a terminal sends CR for a newline in a paste
data = data.replace(b"\n", b"\r")
pid, fd = pty.fork()
if pid == 0:
    os.execvp(prog[0], prog)
os.set_blocking(fd, False)
time.sleep(0.2)
at, got, t0, written = 0, 0, time.monotonic(), None
last = t0
while True:
    w = [fd] if at < len(data) else []
    r, w, _ = select.select([fd], w, [], 1.0)
    if not r and not w and written is not None:
        break
    if r:
        try:
            n = len(os.read(fd, 65536))
            got += n
            last = time.monotonic()
        except OSError:
            break
    if w:
        try:
            at += os.write(fd, data[at:at + chunk])
        except BlockingIOError:
            pass
        if at >= len(data) and written is None:
            written = time.monotonic()
print(f"{len(data)} bytes into {' '.join(prog)}: written in {(written - t0) * 1e3:.0f} ms, "
      f"echo done in {(last - t0) * 1e3:.0f} ms, {got} bytes read back")
os.kill(pid, 9)

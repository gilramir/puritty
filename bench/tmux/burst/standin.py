"""A stand-in for an inline app (Claude Code's non-fullscreen mode) that,
when it comes back, clears the screen and its scrollback and prints its
whole transcript again. N lines of colored text; each key read reprints."""
import os, sys, termios, tty
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
def transcript():
    out = []
    for i in range(N):
        out.append(f"\x1b[38;5;{i % 200 + 20}m● step {i}\x1b[0m  ⎿  some tool output for line {i}, wrapped text and more text here")
    return "\r\n".join(out) + "\r\n> "
fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
tty.setraw(fd)
try:
    os.write(1, transcript().encode())
    while True:
        c = os.read(fd, 1)
        if c in (b"q", b""):
            break
        os.write(1, ("\x1b[2J\x1b[3J\x1b[H" + transcript()).encode())
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)

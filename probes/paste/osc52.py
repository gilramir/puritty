#!/usr/bin/env python3
"""What tmux sends its terminal for a copy (docs/phase3-select.md): tmux
on a pty, as puritty runs it, with set-clipboard on; `load-buffer -w` of
SIZE bytes; the OSC 52 sequences read from the master counted and sized.

  osc52.py SIZE...
"""
import os, pty, re, select, subprocess, sys, time

sock = f"osc52probe{os.getpid()}"
env = dict(os.environ, TERM="xterm-256color")
pid, fd = pty.fork()
if pid == 0:
    os.execvpe("tmux", ["tmux", "-L", sock, "-f", "/dev/null", "new-session",
                        ";", "set", "-g", "set-clipboard", "on"], env)
os.set_blocking(fd, False)


def drain(seconds):
    out, end = b"", time.monotonic() + seconds
    while time.monotonic() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                out += os.read(fd, 1 << 20)
            except OSError:
                break
    return out


drain(1.5)
for size in map(int, sys.argv[1:]):
    text = ("x" * 79 + "\n") * (size // 80) + "x" * (size % 80)
    p = subprocess.run(["tmux", "-L", sock, "load-buffer", "-w", "-"], input=text.encode(), capture_output=True, env=env)
    out = drain(1.0)
    seqs = re.findall(rb"\x1b\]52;([^;\x07\x1b]*);([^\x07\x1b]*)(\x07|\x1b\\)", out)
    sizes = [len(s[1]) for s in seqs]
    print(f"load-buffer -w of {size} bytes (exit {p.returncode}{', ' + p.stderr.decode().strip() if p.stderr else ''}): "
          f"{len(seqs)} OSC 52, selections {[s[0].decode() for s in seqs]}, base64 lengths {sizes}")
subprocess.run(["tmux", "-L", sock, "kill-server"], capture_output=True)

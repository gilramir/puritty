"""Record a tmux control-mode (-CC) session: each argument is a command
sent on its own line, or "SLEEP s" to stop reading for s seconds. The raw
bytes go to the first argument's file. Runs on its own socket and kills
that server at the end (docs/tmux.md TM3).

    TMUX_BIN=/path/to/tmux python3 record.py out.raw 'split-window -h' ...
"""
import os, pty, sys, time, select
TMUX = os.environ.get("TMUX_BIN", "tmux")
SOCK = "puritty-bench-tmux"
out = open(sys.argv[1], "wb")
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm-256color"
    os.execv(TMUX, [TMUX, "-L", SOCK, "-f", "/dev/null", "-CC", "new-session", "-x", "80", "-y", "24", "sh"])
def drain(t):
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try: d = os.read(fd, 65536)
            except OSError: return
            out.write(d)
def cmd(c, t=0.4):
    out.write(b"\n>>> " + c.encode() + b"\n")
    os.write(fd, c.encode() + b"\n"); drain(t)
drain(1.0)
for c in sys.argv[2:]:
    if c.startswith('SLEEP'):
        out.write(b'\n>>> '+c.encode()+b'\n'); time.sleep(float(c.split()[1]))
    else:
        cmd(c)
cmd("kill-server", 1.0)
os.waitpid(pid, 0)

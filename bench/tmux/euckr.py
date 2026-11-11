"""EUC-KR through tmux (docs/tmux.md TM11): a pane prints a word as EUC-KR
and as UTF-8, a client attaches on a pty, and this prints the bytes the
client got for each and what capture-pane holds. The arguments are the
server's and the client's LC_ALL; LOCPATH holds locales built with
`localedef -i ko_KR -f EUC-KR <dir>/ko_KR.euckr` (and -f UTF-8).

    TMUX_BIN=... LOCPATH=... python3 euckr.py ko_KR.utf8 ko_KR.euckr
"""
import os, pty, sys, time, select, subprocess, re
TMUX = os.environ["TMUX_BIN"]; SOCK = "puritty-bench-tmux"
server_loc, client_loc = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]   # e.g. -u
def env(loc):
    e = dict(os.environ); e.pop("TMUX", None); e["LOCPATH"] = os.environ["LOCPATH"]; e["TERM"] = "xterm-256color"
    for k in ("LANG", "LC_ALL", "LC_CTYPE"): e.pop(k, None)
    e["LC_ALL"] = loc; return e
prog = r"printf 'A[\307\321\261\333]B[\355\225\234\352\270\200]C\n'; sleep 30"
subprocess.run([TMUX, *extra, "-L", SOCK, "-f", "/dev/null", "new-session", "-d", "-x", "80", "-y", "5", prog], env=env(server_loc), check=True)
time.sleep(0.3)
pid, fd = pty.fork()
if pid == 0:
    os.execve(TMUX, [TMUX, *extra, "-L", SOCK, "attach"], env(client_loc))
buf = b""; end = time.time() + 1.5
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.02)
    if r: buf += os.read(fd, 65536)
m = re.search(rb"A\[(.*?)\]B\[(.*?)\]C", re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]|\x1b\(B", b"", buf))
print("outer gets euc:", m.group(1).hex(" ") if m else None, "| utf8:", m.group(2).hex(" ") if m else None)
cap = subprocess.run([TMUX, "-L", SOCK, "capture-pane", "-p", "-t", "%0"], capture_output=True, env=env(server_loc)).stdout.split(b"\n")[0]
print("capture:", cap.hex(" "))
subprocess.run([TMUX, "-L", SOCK, "kill-server"], env=env(server_loc))

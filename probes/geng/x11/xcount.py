"""Counts the bytes of each X connection (docs/phase2-window.md §5): listens
as display :78 and forwards to :77. On each connection's close, appends
"to_server from_server" to the file given.

usage: python3 -I xcount.py OUT
"""
import os, socket, sys, threading
OUT = sys.argv[1]
path = "/tmp/.X11-unix/X78"
try: os.unlink(path)
except FileNotFoundError: pass
srv = socket.socket(socket.AF_UNIX); srv.bind(path); srv.listen(8)
def pump(a, b, box, i):
    while True:
        d = a.recv(1 << 16)
        if not d: break
        box[i] += len(d); b.sendall(d)
    try: b.shutdown(socket.SHUT_WR)
    except OSError: pass
def serve(c):
    u = socket.socket(socket.AF_UNIX); u.connect("/tmp/.X11-unix/X77")
    box = [0, 0]
    t1 = threading.Thread(target=pump, args=(c, u, box, 0)); t2 = threading.Thread(target=pump, args=(u, c, box, 1))
    t1.start(); t2.start(); t1.join(); t2.join()
    with open(OUT, "a") as f: f.write(f"{box[0]} {box[1]}\n")
while True:
    c, _ = srv.accept(); threading.Thread(target=serve, args=(c,), daemon=True).start()

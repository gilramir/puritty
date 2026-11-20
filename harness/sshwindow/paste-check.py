#!/usr/bin/env python3
"""Run on the "host" by sshwindow.py's paste cases (docs/sftp.md FT13):
turns bracketed paste on, reads one paste, and writes to OUT what came: a
file's path whose bytes are PICTURE's (then the file is removed), or the
text; "nothing pasted" after 8 s.

    paste-check.py OUT PICTURE
"""
import os, select, sys, termios, tty

out, want = sys.argv[1], sys.argv[2]
old = termios.tcgetattr(0)
tty.setraw(0)
os.write(1, b"\x1b[?2004h")
buf = b""
while b"\x1b[201~" not in buf:
    ready, _, _ = select.select([0], [], [], 8)
    if not ready:
        break
    piece = os.read(0, 4096)
    if not piece:
        break
    buf += piece
os.write(1, b"\x1b[?2004l")
termios.tcsetattr(0, termios.TCSADRAIN, old)
if b"\x1b[201~" not in buf:
    said = "nothing pasted"
else:
    raw = buf.split(b"\x1b[200~", 1)[-1].split(b"\x1b[201~", 1)[0]
    text = raw.decode("utf-8", "replace")
    path = text.strip('"')
    if b"\x00" in raw or "\ufffd" in text:
        said = f"{len(raw)} bytes that are not text"
    elif path.startswith("/") and os.path.isfile(path):
        cache = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "puritty", "paste")
        where = "the cache's paste folder" if os.path.dirname(path) == cache else os.path.dirname(path)
        same = open(path, "rb").read() == open(want, "rb").read()
        said = f"a file in {where}, named paste.*.png: {os.path.basename(path).startswith('paste.') and path.endswith('.png')}; " \
               f"the picture's bytes: {same}; mode {oct(os.stat(path).st_mode & 0o777)}"
        os.remove(path)
    else:
        said = f"text: {text!r}"
open(out, "w").write(said + "\n")

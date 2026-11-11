"""Attach a tmux client on a pty, answer its queries as a terminal would,
and time a lone Esc through to the pane (docs/tmux.md TM3, TM4). The mode
is silent (answer nothing), puritty (what puritty answers today) or full
(also OSC 10/11 and DSR 996). WAIT is the seconds between attach and Esc.

    TMUX_BIN=/path/to/tmux WAIT=1 python3 attach.py puritty
"""
import os, pty, sys, time, select, subprocess
TMUX = os.environ.get("TMUX_BIN", "tmux")
SOCK = "puritty-bench-tmux"
mode = sys.argv[1]       # silent | puritty (what puritty answers today) | full
subprocess.run([TMUX,"-L",SOCK,"-f","/dev/null","new-session","-d","-x","80","-y","24","cat -v"],check=True)
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"]="xterm-256color"; os.environ.pop("TMUX",None)
    os.execv(TMUX,[TMUX,"-L",SOCK,"attach"])
basic=[(b"\x1b[c",b"\x1b[?62;22c"),(b"\x1b[>c",b"\x1b[>1;0;0c"),(b"\x1b[>q",b"\x1bP>|puritty\x1b\\"),(b"\x1b[?2026$p",b"\x1b[?2026;2$y"),(b"\x1b[18t",b"\x1b[8;24;80t"),(b"\x1b[14t",b"\x1b[4;384;800t")]
colour=[(b"\x1b]10;?",b"\x1b]10;rgb:d8d8/d8d8/d8d8\x1b\\"),(b"\x1b]11;?",b"\x1b]11;rgb:1c1c/1c1c/1c1c\x1b\\"),(b"\x1b[?996n",b"\x1b[?997;1n")]
rules = [] if mode=="silent" else basic if mode=="puritty" else basic+colour
buf=b""; seen={}
def pump(t):
    global buf
    end=time.time()+t
    while time.time()<end:
        r,_,_=select.select([fd],[],[],0.005)
        if r:
            buf+=os.read(fd,65536)
            for q,rep in rules:
                n=buf.count(q)
                while seen.get(q,0)<n: seen[q]=seen.get(q,0)+1; os.write(fd,rep)
pump(float(os.environ.get("WAIT","1")))
n=len(buf); t=time.time(); os.write(fd,b"\x1b")
while b"^[" not in buf[n:] and time.time()-t<3: pump(0.005)
print(round((time.time()-t)*1000), subprocess.run([TMUX,"-L",SOCK,"display","-p","theme=#{client_theme}"],capture_output=True,text=True).stdout.strip())
subprocess.run([TMUX,"-L",SOCK,"kill-server"])

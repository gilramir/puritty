#!/usr/bin/env python3
"""Each prefix binding of a tmux pressed through a control client by
send-keys -K, as puritty sends keys (docs/tmux.md TM23, TM24): what the
control client is sent, and what changed, read back from a second client.
A prompt's or a confirmation's binding is followed by the keys a user
would type into it. Writes .harness-work/tmux-bindings/probe.json.

    python3 bench/tmux/bindings.py --tmux /nix/store/...-tmux-3.8/bin/tmux [key ...]
"""
import subprocess, os, time, sys, select, re, json
from pathlib import Path
import argparse
ap=argparse.ArgumentParser()
ap.add_argument("--tmux",default="tmux")
ap.add_argument("keys",nargs="*")
a=ap.parse_args()
T=a.tmux
D=str(Path(__file__).resolve().parent.parent.parent/".harness-work"/"tmux-bindings")
os.makedirs(D,exist_ok=True)
conf=D+"/probe.conf"
open(conf,"w").write("set -g default-shell /bin/sh\nset -g default-command /bin/sh\nset -g history-limit 2000\n")
env=dict(os.environ); env.pop("TMUX",None); env["LC_ALL"]="C.UTF-8"; env["PS1"]="$ "
S=["-L","probe","-f",conf]
def cli(*a): return subprocess.run([T]+S+list(a),env=env,capture_output=True,text=True).stdout.strip()
def state():
    return {
      "panes": cli("list-panes","-a","-F","#{window_index}.#{pane_index} #{pane_id} #{?pane_active,A,-}#{?pane_floating_flag,F,-}#{?pane_marked,M,-}#{?window_zoomed_flag,Z,-} #{pane_mode} #{pane_width}x#{pane_height} #{pane_title}"),
      "windows": cli("list-windows","-a","-F","#{window_index}:#{window_name}#{?window_active,*,} #{window_layout}"),
      "sessions": cli("list-sessions","-F","#{session_name}"),
      "clients": cli("list-clients","-F","#{client_key_table} #{client_prefix} #{client_flags}"),
      "buffers": cli("list-buffers","-F","#{buffer_name}"),
    }
subprocess.run([T]+S+["kill-server"],env=env,capture_output=True)
subprocess.run([T]+S+["new-session","-d"],env=env)
listing=subprocess.run([T]+S+["list-keys","-T","prefix"],env=env,capture_output=True,text=True).stdout
keys=[]
for line in listing.splitlines():
    m=re.match(r"bind-key\s+(?:-r\s+)?-T prefix\s+(\S+)\s+(.*)",line)
    if m: keys.append((m.group(1),m.group(2)))
follow={  # what a user types after a prompt or a confirmation
  "command-prompt":["p","r","o","b","e","Enter"], "confirm-before":["y"],
}
results=[]
only=a.keys
for name,cmd in keys:
    if only and name not in only: continue
    key=name.replace("\\","")
    cli("kill-server")
    time.sleep(0.3)
    subprocess.run([T]+S+["new-session","-d","-s","s","-x","100","-y","30"],env=env)
    cli("split-window","-h"); cli("new-window"); cli("select-window","-t",":0"); cli("set-buffer","probe-buffer")
    time.sleep(0.3)
    p=subprocess.Popen([T]+S+["-C","attach","-t","s"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,env=env)
    def send(l): p.stdin.write((l+"\n").encode()); p.stdin.flush()
    def drain(t=0.8):
        out=b""; end=time.time()+t
        while time.time()<end:
            r,_,_=select.select([p.stdout],[],[],0.05)
            if r:
                b=os.read(p.stdout.fileno(),65536)
                if not b: break
                out+=b
        return out.decode(errors="replace")
    send("refresh-client -C 100x30"); send("refresh-client -f new-layouts"); drain(0.8)
    before=state()
    send("send-keys -K C-b "+"'"+key.replace("'","'\\''")+"'")
    got=drain(1.0)
    extra=[]
    kind=cmd.split()[0]
    for f in follow.get(kind,[]):
        send("send-keys -K "+f); extra.append(f)
    got2=drain(0.8) if extra else ""
    after=state()
    try:
        p.stdin.close(); p.wait(2)
    except Exception: p.kill()
    def notes(txt):
        out=[]
        for l in txt.splitlines():
            if l.startswith("%begin") or l.startswith("%end"): continue
            if l.startswith("%output"):
                out.append("%output "+l.split(" ",2)[1]+" ("+str(len(l))+" chars)"); continue
            out.append(l[:200])
        # collapse runs of %output
        c=[]
        for x in out:
            if c and x.startswith("%output") and c[-1].startswith("%output"): continue
            c.append(x)
        return c
    diff={k:(before[k],after[k]) for k in before if before[k]!=after[k]}
    results.append({"key":name,"cmd":cmd[:160],"sent":notes(got),"after_follow":notes(got2),"follow":extra,"changed":diff})
cli("kill-server")
json.dump(results,open(D+"/probe.json","w"),indent=1,ensure_ascii=False)
for r in results:
    print("=== C-b",r["key"],"|",r["cmd"][:90])
    print("   sent:",r["sent"][:8])
    if r["follow"]: print("   then",r["follow"],"->",r["after_follow"][:6])
    for k,(a,b) in r["changed"].items(): print("   ",k,":",repr(a)[:150],"->",repr(b)[:150])

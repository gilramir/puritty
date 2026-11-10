#!/usr/bin/env python3
"""ssh_config cases (docs/ssh-client.md SC7, SC11 step 5), written to
tests/config-cases.txt: each a config (and the files it includes), a host,
and the lines `ssh -F CONFIG -G HOST` printed for the keywords
Ssh.Config acts on. The files are written under one fixed directory, so
the paths in the cases are the same every time they are made.

usage: packages/ssh/tests/make-config.py
"""

import getpass
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIR = Path("/tmp/puritty-ssh-config-cases")
KEYWORDS = ["user", "hostname", "port", "identitiesonly", "requesttty", "stricthostkeychecking", "serveralivecountmax",
            "serveraliveinterval", "remotecommand", "hostkeyalias", "identityfile", "userknownhostsfile", "sendenv",
            "setenv", "forwardagent", "connecttimeout", "identityagent", "proxyjump"]

C1 = """Host build
  HostName %h.example.com
  User gilbert
  Port 2222
  IdentityFile ~/.ssh/id_build
  ProxyJump bastion
  ServerAliveInterval 30
  SetEnv A=1 B="two words"
  SendEnv LANG LC_*
  ForwardAgent yes
  RequestTTY yes
  RemoteCommand tmux new -A -s main
Host *
  IdentityFile ~/.ssh/id_other
  ServerAliveInterval 60
  StrictHostKeyChecking accept-new
"""

# name, host, files (the first is the -F file), each (relative name, text)
CASES = [
    ("example-build", "build", [("config", C1)]),
    ("example-other", "other", [("config", C1)]),
    ("empty", "plain", [("config", "")]),
    ("first-wins", "h", [("config", "Host h\n  User one\nHost *\n  User two\n  Port 2200\n")]),
    ("negation", "skip", [("config", "Host * !skip\n  User x\nHost skip\n  User y\n")]),
    ("negation-other", "keep", [("config", "Host * !skip\n  User x\nHost skip\n  User y\n")]),
    ("patterns", "web7", [("config", "Host db* web?\n  User w\nHost web??\n  User z\n")]),
    ("pattern-list-comma", "beta", [("config", "Host alpha,beta\n  Port 3000\n")]),
    ("host-case", "BUILD", [("config", "Host build\n  User lower\n")]),
    ("match-host-after-hostname", "build", [("config", "Host build\n  HostName build.example.com\nMatch host build.example.com user gilbert\n  ForwardAgent yes\nHost build\n  User gilbert\n")]),
    ("match-host-user-set", "build", [("config", "Host build\n  HostName build.example.com\n  User gilbert\nMatch host build.example.com user gilbert\n  ForwardAgent yes\n")]),
    ("match-originalhost", "build", [("config", "Host build\n  HostName b.example.com\nMatch originalhost build\n  Port 2201\n")]),
    ("match-localuser", "x", [("config", f"Match localuser {getpass.getuser()}\n  User me\n")]),
    ("match-all", "x", [("config", "Match all\n  ServerAliveCountMax 7\n")]),
    ("match-negated", "x", [("config", "Match !host y\n  ConnectTimeout 10\n")]),
    ("match-final", "x", [("config", "Match final\n  User fin\nHost x\n  Port 2202\n")]),
    ("match-final-second", "x", [("config", "Host x\n  User early\nMatch final\n  User fin\n  IdentitiesOnly yes\n")]),
    ("include-absolute", "inc", [("config", "Include {DIR}/inc/*.conf\nHost inc\n  User late\n"),
                                 ("inc/a.conf", "Host inc\n  User from-a\n"), ("inc/b.conf", "Host inc\n  Port 2203\n")]),
    ("include-in-host", "two", [("config", "Host one\n  Include {DIR}/hostinc.conf\nHost two\n  User t\n"),
                                ("hostinc.conf", "User from-include\n")]),
    ("include-in-matching-host", "one", [("config", "Host one\n  Include {DIR}/hostinc.conf\nHost one\n  User t\n"),
                                         ("hostinc.conf", "User from-include\n")]),
    ("include-host-lines", "y", [("config", "Include {DIR}/hosts.conf\nUser after\n"),
                                 ("hosts.conf", "Host x\n  User xx\n")]),
    ("syntax", "s", [("config", "Host s\n  User=bob\n  Port = 2204\n  IdentityFile \"~/.ssh/my key\"\n  hOsTnAmE   S.Example.COM\n# a comment\n  ServerAliveInterval 5 # trailing\n")]),
    ("tokens", "web1", [("config", "Host web1\n  HostName %h.internal.example\n  UserKnownHostsFile ~/.ssh/kh_%h_%p %d/kh_%u_%r_%n\n  IdentityFile ~/.ssh/id_%r@%h\n  RemoteCommand echo %h\n  User deploy\n  Port 2205\n")]),
    ("lists", "l", [("config", "Host l\n  SendEnv A\n  SetEnv X=1\nHost *\n  SendEnv B C\n  SetEnv Y=2\n  IdentityFile ~/.ssh/one\n  IdentityFile ~/.ssh/two\n")]),
    ("values", "v", [("config", "Host v\n  IdentitiesOnly yes\n  RequestTTY force\n  StrictHostKeyChecking no\n  ForwardAgent no\n  ConnectTimeout 15\n  ServerAliveCountMax 2\n  HostKeyAlias alias.example\n  IdentityAgent none\n")]),
    ("strict-yes", "v", [("config", "StrictHostKeyChecking yes\nRequestTTY no\n")]),
    ("strict-off", "v", [("config", "StrictHostKeyChecking off\n")]),
    ("match-host-case", "build", [("config", "Host build\n  HostName Build.Example.com\nMatch host Build.Example.com\n  Port 2206\nMatch host build.example.com\n  User lower\n")]),
    ("match-originalhost-case", "BUILD", [("config", "Match originalhost build\n  Port 2207\nMatch originalhost BUILD\n  User upper\n")]),
    ("hostname-mixed-case", "m", [("config", "Host m\n  HostName MixED.Example.com\n")]),
]


def main():
    shutil.rmtree(DIR, ignore_errors=True)
    out = ["# ssh_config cases, from make-config.py; do not edit.", f"home {Path.home()}", f"localuser {getpass.getuser()}"]
    for name, host, files in CASES:
        case_dir = DIR / name
        paths = []
        for rel, text in files:
            p = case_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            text = text.replace("{DIR}", str(case_dir))
            p.write_text(text)
            paths.append((str(p), text))
        got = subprocess.run(["ssh", "-F", paths[0][0], "-G", host], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if got.returncode != 0:
            raise SystemExit(f"{name}: ssh -G failed: {got.stderr}")
        lines = []
        for l in got.stdout.splitlines():
            key, _, value = l.partition(" ")
            if key.lower() in KEYWORDS:
                lines.append(key.lower() + " " + value)
        out.append(f"case {name} host={host}")
        for p, text in paths:
            out.append(f"file {p} {text.encode().hex() or '-'}")
        out.append("want " + "\n".join(lines).encode().hex())
    (HERE / "config-cases.txt").write_text("\n".join(out) + "\n")
    print("wrote", len(CASES), "ssh_config cases")


if __name__ == "__main__":
    main()

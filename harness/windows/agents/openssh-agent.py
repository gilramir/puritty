"""usage: openssh-agent.py (after packages/ssh/tests/build.sh --windows and sshd.py has made its keys)

OpenSSH's agent on beelink1: the service started, a test key added,
ssh-tests.exe logging in to nene's test sshd through the agent's pipe,
then the key removed and the service disabled again as it was."""
import getpass, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, "/home/gram/prj/puritty/packages/ssh/tests")
import sshd
keys = sshd.user_keys()[0]
server = sshd.Server(["ListenAddress 192.168.1.99"])
def ps(cmd):
    r = subprocess.run(["ssh", "beelink1", cmd], capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()
try:
    print(ps("Test-NetConnection 192.168.1.99 -Port %d -InformationLevel Quiet" % server.port))
    print(ps(r"New-Item -ItemType Directory -Force geng-probe\agenttest | Out-Null; 'ok'"))
    subprocess.run(["scp", "-q", "/home/gram/prj/puritty/packages/ssh/tests/ssh-tests.exe", keys["ed"], "beelink1:geng-probe/agenttest/"], check=True)
    print(ps(r"cd geng-probe\agenttest; icacls ed /inheritance:r /grant:r ""$env:USERNAME`:F"" | Out-Null; "
             r"Set-Service ssh-agent -StartupType Manual; Start-Service ssh-agent; (Get-Service ssh-agent).Status; "
             r"ssh-add ed 2>&1; ssh-add -l 2>&1"))
    print(ps(r"cd geng-probe\agenttest; .\ssh-tests.exe session 192.168.1.99 %d --user %s --agent-pipe \\.\pipe\openssh-ssh-agent "
             r"--known-hosts kh --strict accept-new --exec 'exit 7'" % (server.port, getpass.getuser())))
finally:
    print(ps(r"ssh-add -D 2>&1; Stop-Service ssh-agent; Set-Service ssh-agent -StartupType Disabled; (Get-Service ssh-agent).Status; "
             r"(Get-Service ssh-agent).StartType; Remove-Item -Recurse -Force geng-probe\agenttest; 'cleaned'"))
    server.stop()

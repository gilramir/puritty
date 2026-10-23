#!/bin/sh
# What only a real RHEL8 host shows (docs/geng-plan.md §1.1, §9 Q9).
# Read-only: it installs nothing, writes nothing, and needs no compiler.
# Run it as an ordinary user, ideally in a session with DISPLAY set the way
# visiterm would be used (for example inside `ssh -X`), and send the output.

section() { printf '\n== %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

section "release, kernel, glibc"
cat /etc/redhat-release 2>/dev/null
uname -srm
ldd --version 2>&1 | head -1

section "pidfd: pidfd_open (Linux 5.3) and waitid(P_PIDFD) (5.4)"
PY=python3
have python3 || PY=/usr/libexec/platform-python
"$PY" - <<'PYEOF'
import ctypes, errno, os, subprocess
libc = ctypes.CDLL(None, use_errno=True)
SYS_pidfd_open = 434
child = subprocess.Popen(["sleep", "0.2"])
fd = libc.syscall(SYS_pidfd_open, child.pid, 0)
if fd < 0:
    e = ctypes.get_errno()
    print("pidfd_open: fails, errno %d (%s)" % (e, errno.errorcode.get(e, "?")))
    child.wait()
else:
    print("pidfd_open: works")
    P_PIDFD, WEXITED = 3, 4
    info = ctypes.create_string_buffer(128)
    r = libc.waitid(P_PIDFD, fd, info, WEXITED)
    if r < 0:
        e = ctypes.get_errno()
        print("waitid(P_PIDFD): fails, errno %d (%s)" % (e, errno.errorcode.get(e, "?")))
        child.wait()
    else:
        print("waitid(P_PIDFD): works")
    os.close(fd)
PYEOF

section "packages"
rpm -q kernel glibc harfbuzz freetype fontconfig libxcb libxkbcommon libxkbcommon-x11 \
    xcb-util-renderutil libthai mesa-libEGL mesa-libGL ibus ibus-hangul ibus-libpinyin \
    ibus-kkc ibus-anthy tmux openssh-clients xorg-x11-xauth 2>&1 | sort

section "tmux"
have tmux && tmux -V

section "locale"
locale
locale -a 2>/dev/null | grep -i -E '^ko|euckr|cp949' | head
have localectl && localectl status 2>/dev/null | head -5

section "input method"
echo "XMODIFIERS=$XMODIFIERS GTK_IM_MODULE=$GTK_IM_MODULE QT_IM_MODULE=$QT_IM_MODULE"
have ibus && ibus version 2>/dev/null

section "fonts"
have fc-match && fc-match monospace
for l in ko ja zh-cn zh-tw th; do
    printf '%s: ' "$l"; fc-list ":lang=$l" family 2>/dev/null | sort -u | head -4 | tr '\n' ';'; echo
done

section "X server (DISPLAY=$DISPLAY)"
if [ -n "$DISPLAY" ]; then
    if have xdpyinfo; then
        xdpyinfo 2>/dev/null | grep -E '^(name of display|vendor string|version number|  dimensions|  resolution)' | head
        xdpyinfo -queryExtensions 2>/dev/null | grep -o -E '(RENDER|XKEYBOARD|MIT-SHM|DRI3|Present|RANDR|XFIXES|GLX|SYNC|XInputExtension)' | sort -u | tr '\n' ' '; echo
    else
        echo "xdpyinfo not installed"
    fi
    have glxinfo && glxinfo -B 2>/dev/null | grep -E 'renderer string|core profile version|OpenGL version' 
else
    echo "no DISPLAY"
fi

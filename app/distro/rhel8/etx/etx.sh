#!/bin/sh
# A desktop like the RHEL8 ETX one, to try the RHEL8 build in by hand
# (docs/rhel8-etx.md RE12). One container, puritty-etx, kept running
# between commands:
#
#   etx.sh start [BINARY]   build the image if needed, start the desktop;
#                           BINARY (default app/puritty-rhel8) is /work/puritty
#   etx.sh shell            a zsh in it, with DISPLAY set
#   etx.sh puritty [ARGS]   puritty started in it, its standard error in
#                           share/puritty.log
#   etx.sh run CMD...       a command in it
#   etx.sh shot FILE.png    the whole screen, as a picture
#   etx.sh vnc              look at it and type into it: a VNC server on
#                           127.0.0.1:5932 (ssh -L 5932:127.0.0.1:5932 from elsewhere)
#   etx.sh bytes [SECONDS]  the X connection's bytes each way over SECONDS
#                           (default 10), as RE7 measures ETX's
#   etx.sh inspect          probes/rhel8/inspect.sh in it, to set beside RE2
#   etx.sh stop
#
# ETX_DELAY_MS (default 1) is how long each direction of the X connection
# is held back, read at start.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../../.." && pwd)
cache=${XDG_CACHE_HOME:-$HOME/.cache}/puritty
state=$cache/etx
name=puritty-etx
image=puritty-etx

inside() { podman exec "$name" "$@"; }

build() {
    tar=$cache/tmux/src/tmux-3.8.tar.gz
    [ -s "$tar" ] || "$root"/app/tests/tmux-versions/releases.sh 3.8 >/dev/null
    sum=$(sha256sum "$tar" | cut -d' ' -f1)
    want=$(awk '$1 == "3.8" { print $2 }' "$root/app/tests/tmux-versions/sources.tsv")
    [ "$sum" = "$want" ] || { echo "tmux-3.8.tar.gz: sha256 $sum, sources.tsv says $want" >&2; exit 1; }
    ctx=$(mktemp -d)
    cp "$here/Containerfile" "$here/xproxy.py" "$here/session.sh" "$tar" "$ctx/"
    podman build -q -t "$image" "$ctx" >/dev/null
    rm -rf "$ctx"
}

# podman's own seccomp profile with the pidfd calls failing as on a kernel
# before 5.3 (RHEL8's 4.18 answers ENOSYS, RE2)
seccomp() {
    mkdir -p "$state"
    python3 - "$state/seccomp.json" <<'PY'
import json, sys
d = json.load(open("/usr/share/containers/seccomp.json"))
pidfd = {"pidfd_open", "pidfd_send_signal", "pidfd_getfd"}
for s in d["syscalls"]:
    s["names"] = [n for n in s["names"] if n not in pidfd]
d["syscalls"] = [s for s in d["syscalls"] if s["names"]]
d["syscalls"].append({"names": sorted(pidfd), "action": "SCMP_ACT_ERRNO", "errnoRet": 38,
                      "comment": "RHEL8's kernel has no pidfds"})
json.dump(d, open(sys.argv[1], "w"), indent=1)
PY
}

case "${1:-}" in
start)
    bin=$(realpath "${2:-$root/app/puritty-rhel8}")
    [ -f "$bin" ] || { echo "no build at $bin: app/distro/build.sh rhel8" >&2; exit 1; }
    podman image exists "$image" || build
    seccomp
    mkdir -p "$state/work" "$state/share"
    podman rm -f -t 0 "$name" >/dev/null 2>&1 || true
    cp "$bin" "$state/work/puritty"
    podman run -d --name "$name" --hostname etx-vm --add-host etx-server:127.0.0.1 \
        --userns=keep-id --security-opt seccomp="$state/seccomp.json" \
        -e ETX_DELAY_MS="${ETX_DELAY_MS:-1}" -e ETX_COMPOSITING="${ETX_COMPOSITING:-}" \
        -e ETX_TRACE="${ETX_TRACE:-}" \
        -v "$state/work:/work" -v "$state/share:/share" -v "$root:/puritty:ro" \
        -p 127.0.0.1:5932:5900 "$image" >/dev/null
    for i in $(seq 1 100); do inside test -e /tmp/etx.ready 2>/dev/null && break; sleep 0.1; done
    # xfwm4 managing: the window its check property names exists (14 s at
    # 1 ms, RE12)
    inside sh -c 'up() { w=$(xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | awk "/window/ {print \$NF}"); [ -n "$w" ] && xwininfo -id "$w" >/dev/null 2>&1; }
        for i in $(seq 1 600); do up && exit 0; sleep 0.2; done; echo "xfwm4 not managing after 120 s" >&2; exit 1'
    inside xdpyinfo | grep -E "^(name of display|vendor string)"
    echo "started; etx.sh vnc to look at it, etx.sh puritty to start puritty"
    ;;
shell)
    podman exec -it "$name" zsh
    ;;
puritty)
    shift
    podman exec -d "$name" sh -c 'DBUS_SESSION_BUS_ADDRESS=$(cat /tmp/dbus.address) exec /work/puritty "$@" 2>/share/puritty.log' puritty "$@" >/dev/null
    ;;
run)
    shift
    podman exec "$name" "$@"
    ;;
shot)
    out=${2:?a file.png}
    inside sh -c 'DISPLAY=:5 import -window root /share/shot.png'
    cp "$state/share/shot.png" "$out"
    echo "$out"
    ;;
vnc)
    inside sh -c 'pgrep x11vnc >/dev/null || x11vnc -display :5 -noshm -forever -shared -nopw -quiet -bg -o /tmp/x11vnc.log >/dev/null 2>&1'
    echo "VNC on 127.0.0.1:5932 (no password; reachable from this machine only)"
    ;;
bytes)
    s=${2:-10}
    a=$(inside cat /tmp/xproxy.counts)
    sleep "$s"
    b=$(inside cat /tmp/xproxy.counts)
    set -- $a $b
    echo "over $s s: to the X server $(( $4 - $1 )) bytes, from it $(( $5 - $2 )) bytes"
    ;;
inspect)
    inside sh /puritty/probes/rhel8/inspect.sh
    ;;
stop)
    podman rm -f -t 0 "$name" >/dev/null
    ;;
*)
    sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac

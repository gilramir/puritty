#!/bin/sh
# Each distribution's own tmux, as its package builds it (patches and
# all), dumped by dump-tmux.py and dump-lines.py into corpus/tmux/DISTRIBUTION
# (docs/tmux-versions.md): the distributions puritty is built for
# (docs/releasing.md RL3) and their neighbors.
#
#   app/tests/tmux-versions/distros.sh [NAME...]
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
all="almalinux-8 almalinux-9 almalinux-10 ubuntu-22.04 ubuntu-24.04 debian-12 debian-13 fedora-43"
for name in ${*:-$all}; do
    (
        case $name in
            almalinux-8) image=docker.io/library/almalinux:8
                # record-tmux.py wants a Python newer than 8's 3.6
                setup="dnf -q -y install tmux python39 >/dev/null 2>&1"; py=python3.9 ;;
            almalinux-*) image=docker.io/library/almalinux:${name#almalinux-}
                setup="dnf -q -y install tmux python3 procps-ng >/dev/null 2>&1"; py=python3 ;;
            fedora-*) image=registry.fedoraproject.org/fedora:${name#fedora-}
                setup="dnf -q -y install tmux python3 >/dev/null 2>&1"; py=python3 ;;
            ubuntu-*|debian-*) image=docker.io/library/$(echo "$name" | tr - :)
                setup="apt-get -qq update >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get -qq -y install tmux python3 >/dev/null 2>&1"; py=python3 ;;
        esac
        out=$root/corpus/tmux/$name
        rm -rf "$out"
        mkdir -p "$out"
        podman run --rm -v "$root/app/tests:/tests:ro" -v "$out:/out" "$image" sh -c "
            set -e
            $setup
            package=\$( (rpm -q tmux || dpkg-query -W -f '\${Package} \${Version}' tmux) 2>/dev/null)
            cd /tmp && HOME=/tmp LANG=C.UTF-8 $py /tests/dump-tmux.py \$(command -v tmux) /out \"$name's package: \$package\"
            cd /tmp && HOME=/tmp LANG=C.UTF-8 $py /tests/dump-lines.py \$(command -v tmux) /out
        " > "${XDG_CACHE_HOME:-$HOME/.cache}/puritty/tmux/$name.log" 2>&1 && echo "$name dumped" || echo "$name FAILED: see ${XDG_CACHE_HOME:-$HOME/.cache}/puritty/tmux/$name.log"
    ) &
done
wait
# each dump's variables, from its release's source (docs/tmux-checks.md TK8)
python3 "$here/variables.py"

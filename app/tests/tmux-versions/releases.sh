#!/bin/sh
# tmux's releases from 2.7 (RHEL8's, the oldest a target ships) to the
# newest, each downloaded from its GitHub release, built in the
# puritty-tmux-versions image (Containerfile here) and dumped by
# dump-tmux.py and dump-lines.py into corpus/tmux/VERSION
# (docs/tmux-versions.md).
#
#   app/tests/tmux-versions/releases.sh [VERSION...]
#
# The tarballs and builds are kept in ~/.cache/puritty/tmux, out of git;
# each tarball's sha256 is in sources.tsv here, written the first time and
# held to after.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
cache=${XDG_CACHE_HOME:-$HOME/.cache}/puritty/tmux
sums=$here/sources.tsv
mkdir -p "$cache/src" "$cache/build"
touch "$sums"
versions=${*:-"2.7 2.8 2.9 2.9a 3.0 3.0a 3.1 3.1a 3.1b 3.1c 3.2 3.2a 3.3 3.3a 3.4 3.5 3.5a 3.6 3.6a 3.6b 3.7 3.7a 3.7b 3.7c 3.8"}
podman image exists puritty-tmux-versions || podman build -q -t puritty-tmux-versions "$here" >/dev/null

for v in $versions; do
    tar=$cache/src/tmux-$v.tar.gz
    [ -s "$tar" ] || curl -fsSL -o "$tar" "https://github.com/tmux/tmux/releases/download/$v/tmux-$v.tar.gz"
    sum=$(sha256sum "$tar" | cut -d' ' -f1)
    known=$(awk -v v="$v" '$1 == v { print $2 }' "$sums")
    if [ -z "$known" ]; then
        printf '%s\t%s\n' "$v" "$sum" >> "$sums"
    elif [ "$known" != "$sum" ]; then
        echo "tmux-$v.tar.gz: sha256 $sum, sources.tsv says $known" >&2
        exit 1
    fi
done

# built and dumped in parallel, a container each
for v in $versions; do
    (
        out=$root/corpus/tmux/$v
        rm -rf "$out"
        mkdir -p "$out"
        podman run --rm -v "$cache:/cache" -v "$root/app/tests:/tests:ro" -v "$out:/out" puritty-tmux-versions sh -c "
            set -e
            if [ ! -x /cache/build/$v/bin/tmux ]; then
                rm -rf /tmp/b && mkdir /tmp/b && tar -xzf /cache/src/tmux-$v.tar.gz -C /tmp/b
                cd /tmp/b/tmux-$v && ./configure -q --prefix=/cache/build/$v >/dev/null && make -s -j4 >/dev/null 2>&1 && make -s install >/dev/null
            fi
            cd /tmp && HOME=/tmp python3 /tests/dump-tmux.py /cache/build/$v/bin/tmux /out 'tmux $v, built from its release tarball on Debian 12'
            cd /tmp && HOME=/tmp LANG=C.UTF-8 python3 /tests/dump-lines.py /cache/build/$v/bin/tmux /out
        " > "$cache/build/$v.log" 2>&1 && echo "$v dumped" || echo "$v FAILED: see $cache/build/$v.log"
    ) &
done
wait
# each dump's variables, from its release's source (docs/tmux-checks.md TK8)
python3 "$here/variables.py"

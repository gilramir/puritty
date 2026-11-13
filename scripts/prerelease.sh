#!/bin/sh
# Builds a pre-release of puritty from the commit checked out, every target
# into dist/TAG/, ready for a draft GitHub release (docs/releasing.md):
#
#   scripts/prerelease.sh TAG [TARGET...]
#   scripts/prerelease.sh preview-2026-11-13 windows-x64 rhel8-x64
#
# The targets are windows-x64 and NAME-x64 for each Linux distribution
# folder of app/distro (rhel8-x64 today); with none named, all of them.
# Each is profile-guided from one training run (harness/bench/pgo.sh); each
# Linux one passes app/distro/smoke.sh before it is packed. Out come:
#
#   puritty-TAG-windows-x64.zip       puritty.exe, LICENSE, README.txt
#   puritty-TAG-NAME-x64.tar.gz       puritty-TAG-NAME-x64/ with puritty,
#                                     LICENSE, README.txt
#   SHA256SUMS, notes.md              the checksums, and the release's text
#                                     to finish by hand
#
# It refuses a working tree with changes, so that a build is always a
# commit's. Nothing is uploaded: the gh command that would make the draft is
# printed at the end, for whoever decides to run it. Run from puritty's
# devbox (node, nix, the Windows toolchain); podman for the Linux targets.
set -e
tag=${1:?usage: scripts/prerelease.sh TAG [TARGET...]}
shift
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

all="windows-x64"
for d in app/distro/*/Containerfile; do
    all="$all $(basename "$(dirname "$d")")-x64"
done
targets=${*:-$all}
for t in $targets; do
    case " $all " in *" $t "*) ;; *) echo "unknown target $t (known: $all)" >&2; exit 1 ;; esac
done

if [ -n "$(git status --porcelain)" ]; then
    echo "the working tree has changes: commit them first, so that the build is a commit's" >&2
    git status --short >&2
    exit 1
fi
commit=$(git rev-parse --short HEAD)
out=$root/dist/$tag
mkdir -p "$out"
[ -z "$(ls -A "$out")" ] || { echo "$out is not empty" >&2; exit 1; }

echo "== $tag from $commit: $targets"
harness/bench/pgo.sh
profile=--profile-use=$root/harness/bench/core-bench.profile

readme() {
    # $1: the target, $2: how to run it
    cat <<EOF
puritty $tag ($1), built from commit $commit of
https://github.com/gilramir/puritty

$2

The guide: https://gilramir.github.io/puritty/
EOF
}

for t in $targets; do
    name=puritty-$tag-$t
    stage=$out/stage/$name
    mkdir -p "$stage"
    cp LICENSE "$stage/LICENSE"
    case $t in
    windows-x64)
        echo "== $t"
        app/build-windows.sh "$profile"
        cp app/puritty.exe "$stage/puritty.exe"
        readme "$t" "Run puritty.exe. It is not signed yet: Windows may say \"Windows protected
your PC\" the first time; choose More info, then Run anyway." | sed 's/$/\r/' >"$stage/README.txt"
        (cd "$out/stage/$name" && python3 -c '
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as z:
    for f in sys.argv[2:]:
        z.write(f)' "$out/$name.zip" puritty.exe LICENSE README.txt)
        ;;
    *-x64)
        distro=${t%-x64}
        echo "== $t"
        PURITTY_DISTRO_OUT=$stage/puritty app/distro/build.sh "$distro" "$profile"
        app/distro/smoke.sh "$distro" "$stage/puritty"
        readme "$t" "Unpack it anywhere and run ./puritty. It needs the X libraries of a
desktop install ($distro's xcb, xcb-util, xcb-util-image, xcb-util-renderutil,
libxkbcommon-x11 and fontconfig); \`ldd puritty | grep \"not found\"\` lists
any that are missing." >"$stage/README.txt"
        tar -C "$out/stage" -czf "$out/$name.tar.gz" "$name"
        ;;
    esac
done
rm -rf "$out/stage"

(cd "$out" && sha256sum ./*.zip ./*.tar.gz 2>/dev/null | sed 's| \./| |' >SHA256SUMS)
{
    echo "A preview of puritty, built from commit \`$commit\`."
    echo
    for t in $targets; do
        case $t in
        windows-x64) echo "- **Windows**: \`puritty-$tag-$t.zip\`. Unzip it and run \`puritty.exe\`. Not signed yet: if Windows says \"Windows protected your PC\", choose *More info*, then *Run anyway*." ;;
        *) echo "- **${t%-x64}**: \`puritty-$tag-$t.tar.gz\`. Unpack it and run \`./puritty\`." ;;
        esac
    done
    echo
    echo "### New in this preview"
    echo
    echo "### SHA-256"
    echo
    echo '```'
    cat "$out/SHA256SUMS"
    echo '```'
} >"$out/notes.md"

echo
echo "== built in $out:"
ls -l "$out"
echo
echo "Write what is new into $out/notes.md, then, when the upload is wanted:"
echo "  gh release create $tag --draft --prerelease --target $(git rev-parse HEAD) \\"
echo "    --title \"puritty $tag\" --notes-file $out/notes.md $out/*.zip $out/*.tar.gz $out/SHA256SUMS"

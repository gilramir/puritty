#!/bin/sh
# Builds a pre-release of puritty from the commit checked out, every target
# into dist/TAG/, ready for a draft GitHub release (docs/releasing.md):
#
#   scripts/prerelease.sh TAG [TARGET...]
#   scripts/prerelease.sh preview-2026-11-13 windows-x64 rhel8-x64
#
# The targets are windows-x64 and NAME-x64 for each Linux distribution
# folder of app/distro with a Containerfile (rhel8, rhel9, rhel10, noble,
# debian13); with none named, all of them. Each is profile-guided from one
# training run (harness/bench/pgo.sh) where its clang is the devbox's, and
# built without one where it is not (noble's, debian13's); each Linux one
# passes app/distro/smoke.sh before it is packed. The RHEL8 build is also
# the plain Linux build (docs/releasing.md RL3): it passes smoke.sh on
# Fedora, Debian 13 and Arch too, and is named for both. Out come:
#
#   puritty-TAG-windows-x64.zip       puritty.exe, LICENSE, README.txt
#   puritty-TAG-NAME-x64.tar.gz       puritty-TAG-NAME-x64/ with puritty,
#                                     LICENSE, README.txt
#   puritty-TAG-linux-rhel8-x64.tar.gz  the RHEL8 build, as above
#   puritty_V_NAME_amd64.deb          for noble and debian13 (deb.sh), each
#                                     installed with apt and run first
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
        # the shared profile only where the image's clang is the devbox's
        podman image exists "puritty-build-$distro" || podman build -q -t "puritty-build-$distro" "app/distro/$distro"
        theirs=$(podman run --rm "puritty-build-$distro" clang --version | sed -n 's/.*clang version \([0-9.]*\).*/\1/p' | head -1)
        ours=$(/home/gram/prj/geng-lang/.devbox/nix/profile/default/bin/clang --version | sed -n 's/.*clang version \([0-9.]*\).*/\1/p' | head -1)
        if [ "$theirs" = "$ours" ]; then
            uses=$profile
        else
            echo "   $distro's clang is $theirs, not $ours: no profile"
            uses=
        fi
        PURITTY_DISTRO_OUT=$stage/puritty app/distro/build.sh "$distro" $uses
        app/distro/smoke.sh "$distro" "$stage/puritty"
        if [ "$distro" = rhel8 ]; then
            # the plain Linux build: glibc 2.28, older than any distribution's now
            for other in fedora debian13 arch; do
                app/distro/smoke.sh "$other" "$stage/puritty"
            done
            plain=puritty-$tag-linux-rhel8-x64
            mv "$stage" "$out/stage/$plain"
            name=$plain
            stage=$out/stage/$plain
            readme "$t" "Unpack it anywhere and run ./puritty. Built on RHEL 8 (glibc 2.28), it runs
there and on any later x86-64 Linux: checked on RHEL 8, Fedora, Debian 13
and Arch. It needs the X libraries of a desktop install (xcb, xcb-util,
xcb-util-image, xcb-util-renderutil, libxkbcommon-x11 and fontconfig);
\`ldd puritty | grep \"not found\"\` lists any that are missing." >"$stage/README.txt"
        else
            readme "$t" "Unpack it anywhere and run ./puritty. It needs the X libraries of a
desktop install ($distro's xcb, xcb-util, xcb-util-image, xcb-util-renderutil,
libxkbcommon-x11 and fontconfig); \`ldd puritty | grep \"not found\"\` lists
any that are missing." >"$stage/README.txt"
        fi
        tar -C "$out/stage" -czf "$out/$name.tar.gz" "$name"
        if grep -q '^FROM docker.io/library/\(ubuntu\|debian\):' "app/distro/$distro/Containerfile"; then
            # a version dpkg takes: digits first, the tag's letters and digits after
            PURITTY_BIN=$stage/puritty app/distro/deb.sh "$distro" "0.1.0~$(echo "$tag" | tr -cd 'A-Za-z0-9.')" "$out"
        fi
        ;;
    esac
done
rm -rf "$out/stage"

(cd "$out" && sha256sum ./*.zip ./*.tar.gz ./*.deb 2>/dev/null | sed 's| \./| |' >SHA256SUMS)
{
    echo "A preview of puritty, built from commit \`$commit\`."
    echo
    for t in $targets; do
        case $t in
        windows-x64) echo "- **Windows**: \`puritty-$tag-$t.zip\`. Unzip it and run \`puritty.exe\`. Not signed yet: if Windows says \"Windows protected your PC\", choose *More info*, then *Run anyway*." ;;
        rhel8-x64) echo "- **Linux, any x86-64** (built on RHEL 8): \`puritty-$tag-linux-rhel8-x64.tar.gz\`. Unpack it and run \`./puritty\`." ;;
        noble-x64|debian13-x64) echo "- **${t%-x64}**: \`puritty-$tag-$t.tar.gz\`, or the \`.deb\`: \`sudo apt install ./puritty_*_${t%-x64}_amd64.deb\`." ;;
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
echo "    --title \"puritty $tag\" --notes-file $out/notes.md $out/*.zip $out/*.tar.gz $out/*.deb $out/SHA256SUMS"

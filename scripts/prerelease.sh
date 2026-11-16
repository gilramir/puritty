#!/bin/sh
# Builds a pre-release of puritty from the commit checked out, every target
# into dist/TAG/, ready for a draft GitHub release (docs/releasing.md):
#
#   scripts/prerelease.sh TAG [TARGET...]
#   scripts/prerelease.sh preview-2026-11-13 windows-x64 rhel8-x64
#   scripts/prerelease.sh 0.1.0
#
# A tag that is a version (0.1.0) makes a release: the .deb's version is the
# tag, and the notes and the gh command say release, not preview (RL9). Any
# other tag makes a preview.
#
# The targets are windows-x64 and NAME-x64 for each Linux distribution
# folder of app/distro with a Containerfile (rhel8, rhel9, rhel10, noble,
# debian13); with none named, all of them. Each is profile-guided from one
# training run (harness/bench/pgo.sh) where its clang is the devbox's, and
# built without one where it is not (debian13's); each Linux one
# passes app/distro/smoke.sh before it is packed. The RHEL8 build is also
# the plain Linux build (docs/releasing.md RL3): it passes smoke.sh on
# Fedora, Debian 13 and Arch too, and is named for both. Out come:
#
#   puritty-TAG-windows-x64.zip       puritty.exe, LICENSE, README.txt,
#                                     THIRD-PARTY-NOTICES.md, LICENSES/
#   puritty-TAG-SHIP-x64.tar.gz       puritty-TAG-SHIP-x64/ with puritty and
#                                     the same files
#   puritty-TAG-linux-rhel8-x64.tar.gz  the RHEL8 build, as above
#   puritty_V_SHIP_amd64.deb          for noble and debian13 (deb.sh), each
#                                     installed with apt and run first
#   SHA256SUMS, notes.md              the checksums, and the release's text
#                                     to finish by hand
#
# It refuses a working tree with changes outside site/ (the website, which
# no package holds), so that a build is always a commit's. Nothing is uploaded: the gh command that would make the draft is
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

case $tag in
[0-9]*.[0-9]*.[0-9]*) release=yes ;;
*) release= ;;
esac

if [ -n "$(git status --porcelain -- . ':!site')" ]; then
    echo "the working tree has changes: commit them first, so that the build is a commit's" >&2
    git status --short -- . ':!site' >&2
    exit 1
fi
commit=$(git rev-parse --short HEAD)
# the commit built, kept: HEAD may move while the build runs
full=$(git rev-parse HEAD)
out=$root/dist/$tag
mkdir -p "$out"
[ -z "$(ls -A "$out")" ] || { echo "$out is not empty" >&2; exit 1; }

echo "== $tag from $commit: $targets"
harness/bench/pgo.sh
profile=--profile-use=$root/harness/bench/core-bench.profile

# the name a target ships by (RL8): the distribution's version, not its codename
shipped() {
    case $1 in
    noble-x64) echo ubuntu24.04-x64 ;;
    *) echo "$1" ;;
    esac
}

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
    name=puritty-$tag-$(shipped "$t")
    stage=$out/stage/$name
    mkdir -p "$stage"
    cp LICENSE "$stage/LICENSE"
    # the third parties' notices and licences, which every copy carries
    cp THIRD-PARTY-NOTICES.md "$stage/THIRD-PARTY-NOTICES.md"
    cp -r LICENSES "$stage/LICENSES"
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
        z.write(f)' "$out/$name.zip" puritty.exe LICENSE README.txt THIRD-PARTY-NOTICES.md LICENSES/*.txt)
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
            readme "$(shipped "$t")" "Unpack it anywhere and run ./puritty. It needs the X libraries of a
desktop install (the distribution's xcb, xcb-util, xcb-util-image, xcb-util-renderutil,
libxkbcommon-x11 and fontconfig); \`ldd puritty | grep \"not found\"\` lists
any that are missing." >"$stage/README.txt"
        fi
        tar -C "$out/stage" -czf "$out/$name.tar.gz" "$name"
        if grep -q '^FROM docker.io/library/\(ubuntu\|debian\):' "app/distro/$distro/Containerfile"; then
            # a version dpkg takes: digits first, the tag's letters and digits after
            PURITTY_BIN=$stage/puritty PURITTY_DEB_LABEL=$(shipped "$t" | sed 's/-x64$//') app/distro/deb.sh "$distro" "$(if [ -n "$release" ]; then echo "$tag"; else echo "0.1.0~$(echo "$tag" | tr -cd 'A-Za-z0-9.')"; fi)" "$out"
        fi
        ;;
    esac
done
rm -rf "$out/stage"

(cd "$out" && sha256sum ./*.zip ./*.tar.gz ./*.deb 2>/dev/null | sed 's| \./| |' >SHA256SUMS)
{
    if [ -n "$release" ]; then
        echo "puritty $tag, built from commit \`$commit\`."
    else
        echo "A preview of puritty, built from commit \`$commit\`."
    fi
    echo
    for t in $targets; do
        case $t in
        windows-x64) echo "- **Windows**: \`puritty-$tag-$t.zip\`. Unzip it and run \`puritty.exe\`. Not signed yet: if Windows says \"Windows protected your PC\", choose *More info*, then *Run anyway*." ;;
        rhel8-x64) echo "- **Linux, any x86-64** (built on RHEL 8): \`puritty-$tag-linux-rhel8-x64.tar.gz\`. Unpack it and run \`./puritty\`." ;;
        noble-x64) echo "- **Ubuntu 24.04 and Linux Mint 22**: \`puritty-$tag-ubuntu24.04-x64.tar.gz\`, or the \`.deb\`: \`sudo apt install ./puritty_*_ubuntu24.04_amd64.deb\`." ;;
        debian13-x64) echo "- **Debian 13**: \`puritty-$tag-$t.tar.gz\`, or the \`.deb\`: \`sudo apt install ./puritty_*_debian13_amd64.deb\`." ;;
        rhel9-x64) echo "- **RHEL 9**: \`puritty-$tag-$t.tar.gz\`. Unpack it and run \`./puritty\`." ;;
        rhel10-x64) echo "- **RHEL 10**: \`puritty-$tag-$t.tar.gz\`. Unpack it and run \`./puritty\`." ;;
        *) echo "- **${t%-x64}**: \`puritty-$tag-$t.tar.gz\`. Unpack it and run \`./puritty\`." ;;
        esac
    done
    echo
    if [ -n "$release" ]; then echo "### What's in it"; else echo "### New in this preview"; fi
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
echo "  gh release create $tag --draft $(if [ -z "$release" ]; then echo "--prerelease "; fi)--target $full \\"
echo "    --title \"puritty $tag\" --notes-file $out/notes.md $out/*.zip $out/*.tar.gz $out/*.deb $out/SHA256SUMS"

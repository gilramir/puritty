#!/bin/sh
# The .deb of a Debian or Ubuntu build (docs/releasing.md RL3):
# app/puritty-NAME, made by build.sh (or PURITTY_BIN), packed with its desktop entry and
# icons into puritty_VERSION_amd64.deb, its Depends read from the binary by
# dpkg-shlibdeps in the puritty-build-NAME image. Then checked as a user
# would get it: installed with apt into the distribution's own image, which
# fetches what Depends names, and run there as smoke.sh runs a build.
#
#   app/distro/deb.sh noble [VERSION] [OUT-DIR]
set -e
name=${1:?the distribution, a folder of app/distro}
version=${2:-0.1.0}
here=$(cd "$(dirname "$0")" && pwd)
outdir=$(realpath "${3:-$here/..}")
bin=${PURITTY_BIN:-$here/../puritty-$name}
[ -x "$bin" ] || { echo "no $bin: run app/distro/build.sh $name first" >&2; exit 1; }
base=$(sed -n 's/^FROM //p' "$here/$name/Containerfile" | head -1)
podman image exists "puritty-build-$name" || podman build -q -t "puritty-build-$name" "$here/$name"

work=$(mktemp -d)
pkg=$work/puritty_${version}_amd64
mkdir -p "$pkg/DEBIAN" "$pkg/usr/bin" "$pkg/usr/share/applications" "$pkg/usr/share/doc/puritty"
cp "$bin" "$pkg/usr/bin/puritty"
cp "$here/../linux/puritty.desktop" "$pkg/usr/share/applications/puritty.desktop"
for s in 16 24 32 48 64 256; do
    mkdir -p "$pkg/usr/share/icons/hicolor/${s}x${s}/apps"
    cp "$here/../icon/png/$s.png" "$pkg/usr/share/icons/hicolor/${s}x${s}/apps/puritty.png"
done
mkdir -p "$pkg/usr/share/icons/hicolor/scalable/apps"
cp "$here/../icon/puritty.svg" "$pkg/usr/share/icons/hicolor/scalable/apps/puritty.svg"
cp "$here/../../LICENSE" "$pkg/usr/share/doc/puritty/copyright"

# Depends: what the binary links, as the distribution's packages
depends=$(podman run --rm -v "$work:$work" -w "$work" "puritty-build-$name" sh -c "
  mkdir -p debian && printf 'Source: puritty\n\nPackage: puritty\nArchitecture: amd64\n' > debian/control
  dpkg-shlibdeps -O -e $pkg/usr/bin/puritty 2>/dev/null | sed -n 's/^shlibs:Depends=//p'
")
[ -n "$depends" ] || { echo "dpkg-shlibdeps named no dependency" >&2; exit 1; }
cat > "$pkg/DEBIAN/control" <<EOF
Package: puritty
Version: $version
Architecture: amd64
Maintainer: Gilbert Ramirez <gilbertr@gmail.com>
Depends: $depends
Recommends: fonts-dejavu-core
Section: x11
Priority: optional
Homepage: https://github.com/gilramir/puritty
Description: a terminal for X11 that stays fast over the network
 puritty is a terminal emulator that stays fast over the network, gets
 Korean, Chinese, Japanese and Thai right, draws tmux's panes itself under
 tmux -CC, and has a built-in ssh client.
EOF
podman run --rm -v "$work:$work" -w "$work" "puritty-build-$name" \
    dpkg-deb --build --root-owner-group "$pkg" "$work/puritty_${version}_amd64.deb" >/dev/null
cp "$work/puritty_${version}_amd64.deb" "$outdir/puritty_${version}_${name}_amd64.deb"
echo "Depends: $depends"

# installed with apt into the plain distribution, and run
podman run --rm -v "$work:/work" -w /work "$base" sh -c '
  set -e
  apt-get update -qq >/dev/null
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ./puritty_*_amd64.deb xvfb fonts-dejavu-core >/dev/null
  test -f /usr/share/applications/puritty.desktop
  Xvfb :9 -screen 0 1200x800x24 >/dev/null 2>&1 &
  sleep 1
  start=$(date +%s)
  DISPLAY=:9 PURITTY_SHOT=/work/shot.ppm PURITTY_NO_XIM=1 HOME=/work timeout 20 puritty -- sh -c "echo hello from puritty; sleep 2"
  status=$?
  took=$(( $(date +%s) - start ))
  echo "installed with apt; ended by itself after $took s, status $status"
  [ "$status" = 0 ] && [ "$took" -lt 10 ]
'
python3 - "$work/shot.ppm" <<'PY'
import sys
data = open(sys.argv[1], "rb").read()
parts = data.split(maxsplit=4)
w, h = int(parts[1]), int(parts[2])
px = parts[4]
lit = sum(1 for i in range(0, min(len(px), w * 17 * 3 * 2), 3) if px[i] > 128)
print(f"last frame {w}x{h}, {lit} light pixels in its first two rows")
if lit < 100:
    sys.exit("nothing drawn")
PY
rm -rf "$work"
echo "$outdir/puritty_${version}_${name}_amd64.deb"

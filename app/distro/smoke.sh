#!/bin/sh
# Runs a distribution build in its puritty-run-NAME image
# (NAME/run/Containerfile) under Xvfb:
# a program that prints a line and ends after two seconds. It passes when
# puritty draws the line and ends by itself once the program has, which is
# a child's exit seen (docs/rhel8-etx.md RE5).
#
#   app/distro/smoke.sh NAME [BINARY]
set -e
name=${1:?the distribution, a folder of app/distro}
here=$(cd "$(dirname "$0")" && pwd)
bin=$(realpath "${2:-$here/../puritty-$name}")
podman image exists "puritty-run-$name" || podman build -q -t "puritty-run-$name" "$here/$name/run"
out=$(mktemp -d)
cp "$bin" "$out/puritty"
podman run --rm -v "$out:/work" -w /work "puritty-run-$name" sh -c '
  missing=$(ldd ./puritty | grep "not found" || true)
  [ -z "$missing" ] || { echo "missing libraries: $missing"; exit 1; }
  Xvfb :9 -screen 0 1200x800x24 >/dev/null 2>&1 &
  sleep 1
  start=$(date +%s)
  DISPLAY=:9 PURITTY_SHOT=/work/shot.ppm PURITTY_NO_XIM=1 HOME=/work timeout 20 ./puritty -- sh -c "echo hello from puritty; sleep 2"
  status=$?
  took=$(( $(date +%s) - start ))
  echo "ended by itself after $took s, status $status"
  [ "$status" = 0 ] && [ "$took" -lt 10 ]
'
python3 - "$out/shot.ppm" <<'PY'
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
[ -n "$SMOKE_KEEP" ] && cp "$out/shot.ppm" "$SMOKE_KEEP"
rm -rf "$out"

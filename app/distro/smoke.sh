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
  # Xvfb, or where a distribution has none (RHEL 10), Xwayland under a
  # headless weston
  if command -v Xvfb >/dev/null; then
    Xvfb :9 -screen 0 1200x800x24 >/dev/null 2>&1 &
    sleep 1
    export DISPLAY=:9
    on=""
  else
    export XDG_RUNTIME_DIR=/tmp/xdg; mkdir -p -m 700 $XDG_RUNTIME_DIR
    on="xwfb-run -c weston --"
  fi
  start=$(date +%s)
  timeout 20 $on sh -c "PURITTY_SHOT=/work/shot.ppm PURITTY_NO_XIM=1 X11_STATS=1 HOME=/work ./puritty -- sh -c \"echo hello from puritty; sleep 2\" 2>/work/stats.txt; echo \$? >/work/status.txt"
  status=$(cat /work/status.txt)
  took=$(( $(date +%s) - start ))
  echo "ended by itself after $took s, status $status"
  # what puritty says it drew, which stands for the picture where there is
  # none to take (Xwayland, RHEL 10)
  grep "^x11: frames" /work/stats.txt | cut -d";" -f1-2
  [ "$status" = 0 ] && [ "$took" -lt 10 ] && grep -q "glyphs [1-9]" /work/stats.txt
'
[ -f "$out/shot.ppm" ] || { echo "no picture to look at (Xwayland): the frames above are the check"; rm -rf "$out"; exit 0; }
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

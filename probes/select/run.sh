#!/bin/sh
# Times a paste and a copy through the X selections on its own Xvfb
# (docs/phase3-select.md): xclip owns CLIPBOARD and sel reads it, then sel
# owns it and xclip reads it, at 1 KB, 1 MB and 10 MB of text.
#   REMOTE=HOST runs sel on HOST over ssh -X, its display this Xvfb.
# Run from puritty's devbox (Xvfb); xclip is the system's.
set -e
cd "$(dirname "$0")"
W=$(realpath ../..)/.harness-work/select
mkdir -p "$W"
export DISPLAY=:81
Xvfb :81 -screen 0 800x600x24 -nolisten tcp >"$W/xvfb.log" 2>&1 &
XVFB=$!
trap 'kill $XVFB 2>/dev/null; true' EXIT
sleep 0.5
G=$(realpath ../..)/.harness-work/perf/inputs/gitlog.txt
head -c 1024 "$G" >"$W/1k"
head -c 1048576 "$G" >"$W/1m"
head -c 10485760 "$G" >"$W/10m"
SEL=./sel
if [ -n "$REMOTE" ]; then
  scp -q sel "$REMOTE":/tmp/sel-probe
  for f in 1k 1m 10m; do scp -q "$W/$f" "$REMOTE":/tmp/sel-$f; done
  SEL="ssh -X $REMOTE /tmp/sel-probe"
fi
for f in 1k 1m 10m; do
  xclip -selection clipboard -i "$W/$f"
  sleep 0.3
  printf 'paste %s: ' $f
  $SEL get CLIPBOARD UTF8_STRING
done
printf 'targets xclip offers: '
$SEL get CLIPBOARD TARGETS
for f in 1k 1m 10m; do
  if [ -n "$REMOTE" ]; then
    $SEL own CLIPBOARD /tmp/sel-$f >"$W/own.log" 2>&1 &
    sleep 2
  else
    $SEL own CLIPBOARD "$W/$f" >"$W/own.log" 2>&1 &
    sleep 0.3
  fi
  OWN=$!
  a=$(date +%s%N)
  n=$(xclip -selection clipboard -o | wc -c)
  b=$(date +%s%N)
  wait $OWN || true
  printf 'copy %s: xclip read %s bytes in %s ms; sel: %s\n' $f "$n" $(((b - a) / 1000000)) "$(tail -n +2 "$W/own.log" | tr '\n' ' ')"
done

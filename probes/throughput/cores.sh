#!/bin/sh
# Times the headless reference cores on each input, as whole processes under
# hyperfine, so both pay the same start-up and file read (a few ms).
#
# usage: cores.sh CORES INPUTS OUT      (CORES from build-cores.sh, INPUTS from gen.py)
set -e
CORES=$(realpath "$1"); IN=$(realpath "$2"); OUT=$(realpath -m "$3")
HYPERFINE=${HYPERFINE:-hyperfine}
mkdir -p "$OUT"
GB=$CORES/ghostty/bin/ghostty-bench
# ghostty-bench names Nix's loader but carries no path to Nix's libc.
LD=$(readelf -l "$GB" | sed -n 's/.*interpreter: \(.*\)]/\1/p')
GHOSTTY="$LD --library-path $(dirname "$LD") $GB +terminal-stream --terminal-rows=50 --terminal-cols=160"
ALACRITTY=$CORES/alacritty-core
for p in "$IN"/*.txt; do
  f=$(basename "$p" .txt)
  $HYPERFINE -N --warmup 2 --runs 10 --style basic --export-json "$OUT/$f.json" \
    -n "ghostty 10 KB" "$GHOSTTY --data=$IN/$f.txt --scrollback-bytes=10000" \
    -n "ghostty 50 MB" "$GHOSTTY --data=$IN/$f.txt --scrollback-bytes=50000000" \
    -n "alacritty 10k" "$ALACRITTY $IN/$f.txt 1 160 50 10000" \
    -n "alacritty 100k" "$ALACRITTY $IN/$f.txt 1 160 50 100000"
done

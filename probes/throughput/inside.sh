#!/bin/sh
# Runs inside the terminal under test. Waits until the terminal is 160x50, times
# `cat` of each input RUNS times, then runs vtebench, and writes OUT/NAME.*.
#
# usage: inside.sh OUT NAME INPUTS VTEBENCH [RUNS]
# PARTS (default "cat vtebench") picks which of the two to run.
OUT=$1; NAME=$2; IN=$3; VTEBENCH=$4; RUNS=${5:-3}
for _ in $(seq 100); do
  [ "$(stty size)" = "50 160" ] && break
  sleep 0.1
done
size=$(stty size)
echo "size $size TERM $TERM" > "$OUT/$NAME.size"
[ "$size" = "50 160" ] || exit 1
PARTS=${PARTS:-cat vtebench}
case " $PARTS " in *" cat "*) : > "$OUT/$NAME.cat"; FILES="ls cup gitlog" ;; *) FILES= ;; esac
for f in $FILES; do
  for _ in $(seq "$RUNS"); do
    printf '\033[H\033[2J\033[3J'
    t0=$(date +%s%N)
    cat "$IN/$f.txt"
    t1=$(date +%s%N)
    echo "$f $(( (t1 - t0) / 1000000 ))" >> "$OUT/$NAME.cat"
  done
done
printf '\033[H\033[2J\033[3J'
# vtebench writes its benchmark to stdout, which must be the terminal; only
# its results go to the .dat file.
case " $PARTS " in *" vtebench "*)
  "$VTEBENCH" --silent --dat "$OUT/$NAME.dat" 2> "$OUT/$NAME.vtebench.err" ;;
esac
echo done >> "$OUT/$NAME.size"

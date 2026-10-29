#!/bin/sh
# Runs a probe build over every input RUNS times (default 3) and prints the
# least and most of the times it reports, which leave out start-up and
# reading the file (a few ms; cores.sh's times include them). One untimed
# run comes first, below.
#
# usage: run.sh PROBE INPUTS [RUNS]     environment passes through to the probe
P=$(realpath "$1"); IN=$(realpath "$2"); RUNS=${3:-3}
# One untimed run first: the machine's power plan clocks the CPU down when
# it is idle, and a first run after idle took 63 ms of `cup` where the rest
# took 50-55, the same cycles at about 4.0 GHz against 5.1 (vt-core.md §VC7).
first=$(ls "$IN"/*.txt | head -1)
"$P" "$first" > /dev/null
for f in "$IN"/*.txt; do
  name=$(basename "$f" .txt)
  times=""
  for r in $(seq "$RUNS"); do
    t=$(systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -- timeout 120 "$P" "$f" | sed -n 's/.* in \([0-9]*\) ms.*/\1/p')
    times="$times $t"
  done
  echo "$name $times" | awk '{min=$2; max=$2; for(i=2;i<=NF;i++){if($i<min)min=$i; if($i>max)max=$i}; printf "%-36s %6d %6d\n", $1, min, max}'
done

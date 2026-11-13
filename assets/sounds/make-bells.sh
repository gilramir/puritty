#!/bin/sh
# Makes assets/sounds/bells/*.wav, the classic computers' bells puritty can
# ring for BEL (docs/sounds.md SN2): each synthesized by ffmpeg from the
# machine's own definition, as its ROM or BIOS plays it. 16-bit PCM, 44.1
# kHz, mono, the tones' peak at 0.3 of full scale. ffmpeg comes from the
# nixpkgs geng-lang pins, so the files come out the same anywhere:
#
#   assets/sounds/make-bells.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)
geng=${GENG_LANG:-/home/gram/prj/geng-lang}
rev=$(grep -o 'github:NixOS/nixpkgs/[0-9a-f]*#clang"' "$geng/devbox.json" | sed 's/.*nixpkgs\/\([0-9a-f]*\)#.*/\1/')
ffmpeg=$(nix build --no-link --print-out-paths "github:NixOS/nixpkgs/$rev#ffmpeg-headless" | grep -- '-bin$')/bin/ffmpeg
out=$here/bells
mkdir -p "$out"

# A square wave of F Hz, high for the first half of each period.
square() { echo "if(lt(mod($1,1),0.5),1,-1)"; }

tone() {
    # $1 the file, $2 its length in seconds, $3 the sample's expression in t
    "$ffmpeg" -v error -y -f lavfi -i "aevalsrc=exprs='$3':s=44100:d=$2" \
        -ac 1 -c:a pcm_s16le -fflags +bitexact -map_metadata -1 "$out/$1.wav"
}

# Apple II (Monitor ROM, BELL1 at $FBDD): WAIT with A=$40 (11,117 cycles
# silent), then $C0 times WAIT with A=$0C and a toggle of the speaker, 546
# cycles each half period. WAIT is (26 + 27A + 5A^2)/2 cycles; the 6502
# runs at 1.020484 MHz on average: 934.5 Hz for 0.1027 s after 10.9 ms.
tone apple2 0.1136 "if(lt(t,0.010894),0,0.3*$(square "(t-0.010894)*934.5"))"

# IBM PC (BIOS BEEP, the 1985 AT's WRITE_TTY): timer 2, divisor 1331 of
# 1,193,182 Hz, square: 896.5 Hz, for 31/64 s. The XT's, a CPU loop, is
# about as long (0.47 s at 4.77 MHz).
tone ibm-pc 0.484375 "0.3*$(square "t*896.46")"

# Atari ST (TOS's bell table, as EmuTOS has it): the YM2149's channel A at
# period 52 of its 2 MHz (2,404 Hz), its volume the envelope, shape 9 (one
# fall to silence), period 4096: 32 steps of 1.5 dB over 0.524 s.
tone atari-st 0.524288 "0.3*pow(10,-1.5*floor(t/0.016384)/20)*$(square "t*2403.85")"

# BBC Micro (MOS: OSBYTE &D3-&D6 at their defaults): channel 3, loud,
# pitch 100 (53 is middle C, 4 a semitone: 515.7 Hz), duration 6 twentieths
# of a second.
tone bbc-micro 0.3 "0.3*$(square "t*515.7")"

# X11 (the X server's default bell: 400 Hz for 100 ms, as `xset q` shows),
# as a PC speaker plays it.
tone x11 0.1 "0.3*$(square "t*400")"

ls -l "$out"

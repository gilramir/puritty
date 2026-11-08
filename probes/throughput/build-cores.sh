#!/bin/sh
# Builds the two headless reference cores into OUT:
#   OUT/ghostty/bin/ghostty-bench   Ghostty's own terminal-stream benchmark, from
#                                   vendor/ghostty at REV, with ghostty-scrollback.patch
#   OUT/alacritty-core              alacritty-core/, on vendor/alacritty's alacritty_terminal
# Run from puritty's root inside its devbox (Zig 0.16). Rust comes from the
# same nixpkgs commit as devbox.json, since alacritty_terminal needs rustc 1.88.
#
# usage: devbox run -- probes/throughput/build-cores.sh OUT
set -e
OUT=$(realpath -m "$1")
HERE=$(dirname "$(realpath "$0")")
ROOT=$(realpath "$HERE/../..")
REV=d8619f1bc
NIXPKGS=github:NixOS/nixpkgs/c80073788adf88abfdc443465311f00e7a231600
mkdir -p "$OUT"

rm -rf "$OUT/ghostty-src"; mkdir -p "$OUT/ghostty-src"
git -C "$ROOT/vendor/ghostty" archive $REV | tar -x -C "$OUT/ghostty-src"
(cd "$OUT/ghostty-src" && patch -p1 < "$HERE/ghostty-scrollback.patch" &&
  zig build -Demit-bench -Demit-exe=false -Dapp-runtime=none -Doptimize=ReleaseFast \
    --prefix "$OUT/ghostty" --cache-dir "$OUT/zig-cache")

(cd "$HERE/alacritty-core" && CARGO_TARGET_DIR="$OUT/cargo-target" \
  nix shell $NIXPKGS#cargo $NIXPKGS#rustc $NIXPKGS#gcc -c cargo build --release --locked)
cp "$OUT/cargo-target/release/alacritty-core" "$OUT/alacritty-core"

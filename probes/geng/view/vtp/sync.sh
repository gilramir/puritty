#!/bin/sh
# Copies the core's sources beside Vt.View, which needs its internal modules;
# the compiler does not follow symbolic links. The copies are not kept in git.
set -e
cd "$(dirname "$0")"
V=../../../../vt/src
cp $V/Vt.geng src/Vt.geng
for f in Cell Dump Pages Resize Screen Style Term Width; do cp $V/Vt/$f.geng src/Vt/$f.geng; done

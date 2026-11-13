# Releasing puritty

How a build that leaves this machine is made. Section numbers are RL*n*.

## RL1 · Pre-releases (2026-11-13)

Gilbert, 2026-11-13: a pre-release for GitHub has a Windows build and a
RHEL8 build, made by a script under git, with more Linux builds for
particular distribution releases to come. Before it, the Windows previews
(preview-2026-11-11 to -12c) were built with `app/release-windows.sh` and
zipped by hand.

    scripts/prerelease.sh TAG [TARGET...]

from puritty's devbox, with a clean working tree:

- **Targets**: `windows-x64`, and `NAME-x64` for each folder of
  `app/distro` (`rhel8-x64`); all of them when none is named.
- **One profile** (`harness/bench/pgo.sh`), used by every target: MinGW's
  clang, the devbox's and AlmaLinux 8's are all 21.1.8, which reads it.
  A distribution whose clang is another version needs its own training, or
  no profile.
- **Each Linux target passes `app/distro/smoke.sh`** (its run image: no
  missing library, a line drawn, the program's exit seen) before it is
  packed.
- **Out**, in `dist/TAG/` (ignored by git): `puritty-TAG-windows-x64.zip`,
  `puritty-TAG-NAME-x64.tar.gz`, each with LICENSE and a README.txt naming
  the commit; `SHA256SUMS`; and `notes.md`, the release's text with the
  downloads and checksums, its "New in this preview" left to be written.
- **Nothing is uploaded.** The script prints the `gh release create
  --draft --prerelease` command. Uploading is Gilbert's call each time,
  and the commit must be pushed first (`scripts/push.sh` in geng-lang)
  for the release's `--target` to name it.

## RL2 · Adding a Linux build

A folder `app/distro/NAME/` with `Containerfile` (the distribution, clang,
and the `-devel` packages of the X libraries: libxcb, xcb-util,
xcb-util-image, -renderutil, -keysyms, -wm, libxkbcommon(-x11),
fontconfig, libpng, zlib) and `run/Containerfile` (the run-time libraries,
a monospace font, Xvfb). `app/distro/README.md` has the rest; RHEL8's
folder is the model (`docs/rhel8-etx.md` RE4).

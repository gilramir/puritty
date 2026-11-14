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

## RL3 · RHEL9 and a .deb for Linux Mint 22.3: planned (2026-11-14)

Gilbert, 2026-11-14: the release builds gain a RHEL9 build and a `.deb`
for the Linux Mint in use here (22.3 "Zena", on Ubuntu 24.04 "noble"),
which he will install on gmktec7 as its test. Not built.

- **RHEL9** is RL2's shape: `app/distro/rhel9/` with its two
  Containerfiles (AlmaLinux 9 for RHEL8's AlmaLinux 8), `rhel9-x64` in
  `scripts/prerelease.sh`, through `smoke.sh` before it is packed. Its
  clang's version decides whether the shared profile (RL1) is read or the
  target trains its own.
- **The .deb** is a new kind of output, not a tarball: built in an
  Ubuntu 24.04 container (Mint 22.3's base), installed to `/usr` with a
  desktop entry and icon, its `Depends` the run-time libraries RL2 lists
  under their Ubuntu names, and checked by installing it into a clean
  noble container and running `smoke.sh` there. Then Gilbert's install on
  gmktec7, a desktop session, is the test that counts.

**Added the same day (Gilbert):**

- **RHEL 10**, RL2's shape like RHEL9 (`app/distro/rhel10/`, AlmaLinux
  10), for the current RHEL and its rebuilds.
- **A .deb for Debian 13** ("trixie"), built and checked as the noble one
  in a Debian 13 container: its library packages' names and versions
  differ from Ubuntu's, so the noble `.deb` does not cover it.
- **The RHEL8 build becomes the plain Linux tarball**, the download for
  any other x86-64 Linux. Its glibc (2.28) is older than every current
  distribution's, and the X libraries it uses keep their ABI, so it should
  run elsewhere as built; `smoke.sh` runs it in Fedora, Debian and Arch
  containers to show it before it is offered so. Its name in the release
  says both: RHEL8, and Linux in general.

Not planned now, and why: Windows and Linux on ARM64 (wait for someone
to ask and a machine to test on), Fedora `.rpm` and an Arch `-bin` package
(the tarball covers them), winget (later, from the same zip), Flatpak and
Snap (a terminal's sandbox keeps it from the system it is for), AppImage
(little over a tarball of one binary), macOS (puritty has no macOS
window code). Each distribution whose clang is not 21.1.8 trains its own
profile or goes without one (RL1).

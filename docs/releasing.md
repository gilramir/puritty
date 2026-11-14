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

## RL4 · RL3's builds made (2026-11-14)

Each in `app/distro/` (RL2's shape), built and run here with podman:

| target | image | clang | profile | checked |
|---|---|---|---|---|
| `rhel9-x64` | AlmaLinux 9.8 | 21.1.8 | the shared one | `smoke.sh`: drawn, ended by itself |
| `rhel10-x64` | AlmaLinux 10.2 | 21.1.8 | the shared one | `smoke.sh` under Xwayland (below) |
| `noble-x64` | Ubuntu 24.04 | 18 | none | `smoke.sh`; the `.deb` installed with apt |
| `debian13-x64` | Debian 13 | 19 | none | `smoke.sh`; the `.deb` installed with apt |
| `rhel8-x64` | AlmaLinux 8 | 21.1.8 | the shared one | `smoke.sh` on RHEL 8, Fedora 43, Debian 13, Arch |

- **The plain Linux tarball.** The RHEL8 build ran, drew and ended by itself
  in Fedora 43, Arch and Debian 13 images (`app/distro/fedora/run`,
  `arch/run`; run-only folders, which `prerelease.sh` does not take for
  targets). `prerelease.sh` names it `puritty-TAG-linux-rhel8-x64.tar.gz`,
  its README says where it was checked, and the notes list it as "Linux,
  any x86-64 (built on RHEL 8)".
- **The .debs** (`app/distro/deb.sh NAME [VERSION] [OUT]`): the binary,
  `puritty.desktop` and the icons under `/usr`, `Depends` read from the
  binary by `dpkg-shlibdeps` in the build image (noble: libc6 ≥ 2.39,
  libfontconfig1, libpng16-16t64, libxcb1 and six xcb libraries,
  libxkbcommon-x11-0, libxkbcommon0, zlib1g), then installed with apt into
  the plain `ubuntu:24.04` or `debian:13` image, which fetched those, and
  run there as `smoke.sh` runs a build. `prerelease.sh` makes one for each
  Ubuntu or Debian target, versioned `0.1.0~TAG`.
- **Debian and Ubuntu name xcb's parts apart**: `xcb-render`, `xcb-xkb` and
  `xcb-randr`, which puritty-x11 links, need `libxcb-render0-dev`,
  `libxcb-xkb-dev` and `libxcb-randr0-dev`, which RHEL's `libxcb-devel`
  holds in one.
- **RHEL 10 has no Xvfb** (it dropped the X server). Its run image draws on
  Xwayland under a headless weston (`xwfb-run`, EPEL), which `smoke.sh`
  uses where Xvfb is missing. There the picture puritty writes on
  `PURITTY_SHOT` did not appear, while its `X11_STATS` line said it drew
  (2 frames, 18 glyphs); xterm ran there as well. So under Xwayland the
  check is that line. That puritty draws as it should on a Wayland desktop
  through Xwayland (RHEL 10's GNOME, Ubuntu's) is not yet seen by eye.
- **The profile**: `prerelease.sh` reads the shared profile only where the
  build image's clang is the devbox's, compared at build time.

Not run yet: `prerelease.sh` with all targets, end to end.

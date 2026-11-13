# Linux builds for a distribution's own libraries

`docs/rhel8-etx.md` RE4. A puritty built here runs on one Linux distribution
release (its glibc and X libraries), with FreeType, HarfBuzz,
xcb-util-cursor and xcb-imdkit built in. Each distribution is a folder:

- `NAME/Containerfile`: the build image, the distribution with clang and
  the `-devel` packages of the X libraries puritty links;
- `NAME/run/Containerfile`: the distribution with the run-time libraries
  only, a monospace font and Xvfb, for `smoke.sh`.

The scripts take the name:

    app/distro/build.sh rhel8 [--profile-use=…]   # app/puritty-rhel8
    app/distro/smoke.sh rhel8 [BINARY]

`build.sh` makes the images (`puritty-build-NAME`, `puritty-run-NAME`) and
the libraries (`build-libs.sh` into `vendor/distro/NAME`) when they are not
there. Adding a distribution is adding its folder; its clang should be the
devbox's version for a profile-guided build (`scripts/prerelease.sh`).

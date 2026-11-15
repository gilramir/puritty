# Third-party notices

puritty is Gilbert Ramirez's, under the BSD 3-Clause License (`LICENSE`).
It is built with code and data from the projects below, whose licences
are in `LICENSES/`, each as its project gives it. Every package and archive
of puritty carries this file and that folder.

## In puritty's programs

| component | what of it | licence (`LICENSES/`) | platforms |
|---|---|---|---|
| [PuTTY](https://www.chiark.greenend.org.uk/~sgtatham/putty/) | its cryptography, for puritty's own ssh client (`packages/ssh-crypto`) | MIT (`PuTTY.txt`) | Linux, Windows |
| [FreeType](https://freetype.org) 2.14.3 | glyph rasterizing | FreeType License (`FreeType.txt`) | Linux, Windows |
| [HarfBuzz](https://harfbuzz.github.io) 13.2.1 | text shaping | "Old MIT" (`HarfBuzz.txt`) | Linux, Windows |
| [Boehm-Demers-Weiser GC](https://github.com/ivmai/bdwgc) 8.2.12 | Geng's garbage collector, unmodified | its own (`Boehm-GC.txt`) | Linux, Windows |
| [Gren](https://gren-lang.org) core and Geng's runtime and libraries | the language's runtime and standard library | BSD 3-Clause (`Gren-and-Geng.txt`) | Linux, Windows |
| gren-toml, gren-bignum, gren-civil-time | settings file, numbers, dates | ISC (`gren-toml.txt`, `gren-bignum.txt`, `gren-civil-time.txt`) | Linux, Windows |
| gren-argparse | the command line | BSD 3-Clause (`gren-argparse.txt`) | Linux, Windows |
| gren-i18next | the settings window's Korean | BSD 3-Clause (`gren-i18next.txt`) | Linux, Windows |
| [tmux](https://github.com/tmux/tmux) | its options' descriptions and color names, compiled into puritty's tmux support | ISC (`tmux.txt`) | Linux, Windows |
| [Ghostty](https://ghostty.org) (libghostty-vt) | the character-width, key and key-code tables puritty's are generated from | MIT (`Ghostty.txt`) | Linux, Windows |
| [Unicode](https://www.unicode.org) 18.0 data | the character widths and emoji ranges in those tables | Unicode License v3 (`Unicode.txt`) | Linux, Windows |
| [xcb-imdkit](https://github.com/fcitx/xcb-imdkit) | the X input method client, linked statically, with puritty's patches | LGPL-2.1 (`xcb-imdkit-LGPL-2.1.txt`) | Linux |
| [xcb-util-cursor](https://gitlab.freedesktop.org/xorg/lib/libxcb-cursor) 0.1.6 | the pointer's shapes | MIT/X11 (`xcb-util-cursor.txt`) | Linux |
| [zlib](https://zlib.net) 1.3.2, [libpng](http://www.libpng.org) 1.6.58 | color emoji fonts' bitmaps | zlib (`zlib.txt`), libpng (`libpng.txt`) | Windows |
| [mingw-w64](https://www.mingw-w64.org) runtime | the C program's start and formatted output | its own (`mingw-w64-runtime.txt`) | Windows |

Portions of this software are copyright © 2026 The FreeType Project
(www.freetype.org). All rights reserved.

The EUC-KR table is WHATWG's `index-euc-kr.txt`, which is in the public
domain. The libraries puritty links from the system it runs on (the C
library, xcb, fontconfig, PulseAudio, Windows' own) are not part of it.

### xcb-imdkit and the LGPL

puritty links xcb-imdkit statically, so under the LGPL 2.1:

- its source is fcitx's at commit `621048b`
  (https://github.com/fcitx/xcb-imdkit), with puritty's four patches,
  `packages/x11/patches/xcb-imdkit-*.patch`; `packages/x11/build-imdkit.sh`
  applies them and builds it;
- to use a version of your own, change that build and build puritty again:
  puritty's whole source and its build are public, and `app/build.sh` links
  whatever `build-imdkit.sh` built.

## In the repository only

Not part of puritty's programs: tests, documents and the website.

| component | what of it | licence (`LICENSES/`) |
|---|---|---|
| [Wycheproof](https://github.com/C2SP/wycheproof) | test vectors among ssh-crypto's (`packages/ssh-crypto/tests/vectors.txt`) | Apache 2.0 (`Wycheproof-Apache-2.0.txt`) |
| Microsoft BASIC for 6502 1.1 | the `CHRGET` routine in the home page's pictures (`docs/images/nostalgia`) | MIT (`Microsoft-BASIC-M6502.txt`) |
| tmux | its answers, recorded for the tests (`corpus/tmux`, `RealTmux.geng`, `LinesRecorded.geng`, `Keys27Recorded.geng`, `TmuxVersions.geng`) | ISC (`tmux.txt`) |

## What each path comes from

Every vendored folder, patch, library source and generated file, and the
notice it falls under (`own` for puritty's own). `scripts/notices.py`, in
the unit gate, fails on one not listed here, a pattern that matches
nothing, or a licence file that is missing or unused.

```paths
packages/ssh-crypto/src/Ext/putty/*	PuTTY.txt
packages/ssh-crypto/src/Ext/pc_*	PuTTY.txt
src:freetype	FreeType.txt
src:harfbuzz	HarfBuzz.txt
src:xcb-util-cursor	xcb-util-cursor.txt
src:zlib	zlib.txt
src:libpng	libpng.txt
packages/x11/patches/xcb-imdkit-*.patch	xcb-imdkit-LGPL-2.1.txt
packages/tmux/src/Tmux/CustomizeTables.geng	tmux.txt
packages/tmux/src/Tmux/ColorNames.geng	tmux.txt
packages/tmux/tools/customize_tables.py	tmux.txt
packages/tmux/tools/color_names.py	tmux.txt
vt/src/Vt/Width.geng	Ghostty.txt Unicode.txt
vt/gen-width.py	Ghostty.txt Unicode.txt
vt/src/Vt/KeyTables.geng	Ghostty.txt
vt/gen-keys.py	Ghostty.txt
packages/win32/src/Ext/win32_keycodes.h	Ghostty.txt
packages/win32/gen-keycodes.py	Ghostty.txt
vt/src/Vt/EucKrIndex.geng	own
vt/gen-euckr.py	own
probes/euckr/*	own
probes/geng/core/*	Ghostty.txt Unicode.txt
app/tests/src/RealTmux.geng	tmux.txt
app/tests/record-tmux.py	tmux.txt
app/tests/src/LinesRecorded.geng	tmux.txt
app/tests/gen-lines.py	tmux.txt
packages/tmux/tests/src/Keys27Recorded.geng	tmux.txt
packages/tmux/tests/record-keys27.py	tmux.txt
packages/tmux/tests/src/TmuxVersions.geng	tmux.txt
packages/tmux/tests/gen-versions.py	tmux.txt
packages/ssh-crypto/tests/vectors.txt	Wycheproof-Apache-2.0.txt
packages/ssh-crypto/tests/make-vectors.py	Wycheproof-Apache-2.0.txt
docs/images/nostalgia/*	Microsoft-BASIC-M6502.txt
app/icon/pack-x11.py	own
packages/x11/src/Ext/puritty_icon.h	own
assets/sounds/*	own
packages/ssh/tests/*	own
lib:boehm	Boehm-GC.txt
lib:geng	Gren-and-Geng.txt gren-toml.txt gren-bignum.txt gren-civil-time.txt gren-argparse.txt gren-i18next.txt
lib:mingw	mingw-w64-runtime.txt
```

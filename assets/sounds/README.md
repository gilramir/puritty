# Sounds

## Key sounds

For the key-sound option (`docs/feature-plan.md` §3), off by default.

- `keyany.wav`: any key but Enter. 0.15 s, G.711 mu-law, 44.1 kHz mono.
- `keyenter.wav`: Enter. 0.37 s, 16-bit PCM, 22.05 kHz mono.

Both come from Q10 Editor (`q10.exe`), and Gilbert decided on 2026-11-07
to ship them in released builds. Q10 has not been updated since 2007. Its
author was written to that day at the address Q10 publishes,
`q10@baara.com`, and the mail bounced: `550 Unroutable address`. They are
not FocusWriter's files of the same names, which are other recordings.

## Bells

`bells/*.wav`, the classic computers' bells for `[sound] bell`
(`docs/sounds.md` SN2), made by `make-bells.sh` with ffmpeg from each
machine's own definition. The same script converts the key sounds and
writes `puritty_sounds.h`, every sound as a C array, which the platform
packages build into puritty. Run it again after changing a sound here.

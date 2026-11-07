# Key sounds

For the key-sound option (`docs/feature-plan.md` §3), off by default.

- `keyany.wav`: any key but Enter. 0.15 s, G.711 mu-law, 44.1 kHz mono.
- `keyenter.wav`: Enter. 0.37 s, 16-bit PCM, 22.05 kHz mono.

Both come from Q10 Editor (`q10.exe`), and Gilbert decided on 2026-11-07
to ship them in released builds. Q10 has not been updated since 2007. Its
author was written to that day at the address Q10 publishes,
`q10@baara.com`, and the mail bounced: `550 Unroutable address`. They are
not FocusWriter's files of the same names, which are other recordings.

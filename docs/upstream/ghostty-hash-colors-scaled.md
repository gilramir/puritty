# A `#` color's digits are scaled, where XParseColor takes them as the high bits

**Repository:** `ghostty-org/ghostty`

**Found against:** v1.4.0 (`83fb95624`). Found by esctest2's
`ChangeColorTests` (`vt-core.md` §VC71). Not to be filed (`README.md`).

## Summary

OSC 4, 10 to 12 and the other color sequences take X11 color
specifications. X11 (`XParseColor`, Xlib §6.1.1) gives the two hex forms
different meanings: in `rgb:R/G/B` each channel's digits are **scaled**
to the channel's range, and in `#RGB`, `#RRGGBB`, `#RRRGGGBBB` and
`#RRRRGGGGBBBB` they are its **most significant bits** ("When fewer than
16 bits each are specified, they represent the most significant bits of
the value (unlike the `rgb:` syntax, in which values are scaled)").
Ghostty scales both, so `#fff` sets white where xterm sets `f0f0f0`.

| set with | Ghostty answers | xterm, WezTerm answer |
|---|---|---|
| `#fff` | `rgb:ffff/ffff/ffff` | `rgb:f0f0/f0f0/f0f0` |
| `#f00f00f00` | `rgb:efef/efef/efef` | `rgb:f0f0/f0f0/f0f0` |
| `#f000f000f000` | `rgb:efef/efef/efef` | `rgb:f0f0/f0f0/f0f0` |
| `rgb:f/f/f` | `rgb:ffff/ffff/ffff` | `rgb:ffff/ffff/ffff` |

WezTerm reads the `#` forms as X11 does (`color-types/src/lib.rs`,
"From XParseColor, the `#` syntax takes the most significant bits").

## Reproduction

```
printf '\e]4;1;#fff\a\e]4;1;?\a' > hash.bin
ghostty-dump 10 2 hash.bin     # puritty harness/oracle: the reply
```

esctest2: `ChangeColorTests.test_ChangeColor_Hash3`, `_Hash9`,
`_Hash12`, and the same in `ChangeDynamicColorTests`.

## Where

`src/terminal/color.zig`, `RGB.parse`: the `#` branch calls `fromHex`,
which divides by the digits' maximum (`maxInt(u4)`, `u12`, `u16`) as
`rgb:` should.

## Fix

A `fromHexHigh` for the `#` branch that shifts instead of scaling: one
digit `<< 4`, two as they are, three `>> 4`, four `>> 8`.
`harness/oracle/patches/0012-hash-colors-are-the-high-bits.patch` is it.
`RGB.parse` also reads Ghostty's configuration, where `#fff` is meant as
CSS means it (white); a fix upstream would keep that reading for the
configuration and use X11's for the escape sequences.

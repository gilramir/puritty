/* The oracle's width table, for vt/gen-width.py (docs/vt-core.md §VC17):
 * every code point from 0x80 to 0x10FFFF but the surrogates as
 * `CP WIDTH`, hex and 0, 1 or 2, where libghostty-vt's
 * ghostty_unicode_codepoint_width gives other than 1, the table its
 * terminal lays text out with. A code point up to 0xFF is left out:
 * Ghostty prints one as one cell whatever the table says (U+00AD). */
#include <ghostty/vt.h>
#include <stdio.h>

int main(void) {
  for (uint32_t cp = 0x100; cp <= 0x10FFFF; cp++) {
    if (cp >= 0xD800 && cp < 0xE000) continue;
    uint8_t w = ghostty_unicode_codepoint_width(cp);
    if (w != 1) printf("%X %u\n", cp, w);
  }
  return 0;
}

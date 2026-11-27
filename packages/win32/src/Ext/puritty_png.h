/* A pasted picture's PNG, measured (the code review's W12). Plain C, no
 * Windows, so that packages/win32/tests/cases.c can test it on Linux. */
#ifndef PURITTY_PNG_H
#define PURITTY_PNG_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* A PNG's own length in a block of `size` bytes: through its IEND chunk.
 * The clipboard's block is GlobalSize long, which the allocator may round
 * up, and the bytes past IEND went with the file (the code review's W12).
 * Not a PNG, or one cut short: the whole block, as before. */
static inline size_t png_length(const uint8_t *d, size_t size) {
    static const uint8_t sig[8] = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'};
    if (size < 8 || memcmp(d, sig, 8) != 0) return size;
    size_t at = 8;
    while (size - at >= 12) {
        uint32_t n = ((uint32_t) d[at] << 24) | ((uint32_t) d[at + 1] << 16) | ((uint32_t) d[at + 2] << 8) | d[at + 3];
        if ((size_t) n > size - at - 12) return size;
        size_t end = at + 12 + n;
        if (memcmp(d + at + 4, "IEND", 4) == 0) return end;
        at = end;
    }
    return size;
}

#endif

/* The win32 package's portable C tested on Linux (cases.sh): a pasted
 * PNG's length through IEND (the code review's W12). */
#include <stdio.h>
#include <stdlib.h>

#include "../src/Ext/puritty_png.h"

static int failed;

static void expect(const char *what, size_t got, size_t want) {
    if (got != want) {
        printf("FAIL %s: %zu, want %zu\n", what, got, want);
        failed = 1;
    } else {
        printf("ok   %s: %zu\n", what, got);
    }
}

static size_t chunk(uint8_t *d, size_t at, const char *type, size_t n) {
    d[at] = (uint8_t) (n >> 24), d[at + 1] = (uint8_t) (n >> 16), d[at + 2] = (uint8_t) (n >> 8), d[at + 3] = (uint8_t) n;
    memcpy(d + at + 4, type, 4);
    memset(d + at + 8, 0x5A, n + 4);  /* the data and the CRC */
    return at + 12 + n;
}

int main(void) {
    uint8_t d[256];
    static const uint8_t sig[8] = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'};
    memcpy(d, sig, 8);
    size_t at = chunk(d, 8, "IHDR", 13);
    at = chunk(d, at, "IDAT", 40);
    at = chunk(d, at, "IEND", 0);
    size_t png = at;
    /* the block GlobalSize gives: rounded up past IEND */
    memset(d + png, 0xEE, 32);
    expect("a PNG in a rounded-up block", png_length(d, png + 32), png);
    expect("a PNG that fills its block", png_length(d, png), png);
    expect("not a PNG: the whole block", png_length((const uint8_t *) "GIF89a and more bytes", 21), 21);
    expect("a PNG cut short before IEND: the whole block", png_length(d, png - 6), png - 6);
    /* a chunk whose length runs past the block */
    uint8_t bad[64];
    memcpy(bad, sig, 8);
    chunk(bad, 8, "IHDR", 13);
    bad[8] = 0x7F;
    expect("a chunk longer than the block: the whole block", png_length(bad, sizeof bad), sizeof bad);
    return failed;
}

/* The floor for the EUC-KR decoder (docs/phase3-input.md): the same
 * decoder as src/EucKr.geng in C, 64 KB reads, WHATWG's index.
 *   floor FILE INDEX */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static uint16_t table[126 * 190];
static size_t put(uint8_t *o, uint32_t cp) {
    if (cp < 0x80) { o[0] = cp; return 1; }
    if (cp < 0x800) { o[0] = 0xC0 | cp >> 6; o[1] = 0x80 | (cp & 63); return 2; }
    o[0] = 0xE0 | cp >> 12; o[1] = 0x80 | ((cp >> 6) & 63); o[2] = 0x80 | (cp & 63); return 3;
}
int main(int argc, char **argv) {
    FILE *ix = fopen(argv[2], "r");
    char line[256];
    while (fgets(line, sizeof line, ix)) {
        unsigned p, cp;
        if (line[0] != '#' && sscanf(line, "%u 0x%x", &p, &cp) == 2) table[p] = cp;
    }
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
    uint8_t *in = malloc(n), *out = malloc(65536 * 3 + 3);
    if (fread(in, 1, n, f) != (size_t) n) return 1;
    struct timespec a, b;
    clock_gettime(CLOCK_MONOTONIC, &a);
    size_t total = 0; int lead = 0;
    for (long at = 0; at < n; at += 65536) {
        long end = at + 65536 < n ? at + 65536 : n;
        size_t o = 0;
        for (long i = at; i < end;) {
            int c = in[i];
            if (lead) {
                uint32_t cp = c >= 0x41 && c <= 0xFE ? table[(lead - 0x81) * 190 + c - 0x41] : 0;
                lead = 0;
                if (cp) { o += put(out + o, cp); i++; }
                else { o += put(out + o, 0xFFFD); if (c >= 0x80) i++; }
            } else if (c < 0x80) out[o++] = c, i++;
            else if (c >= 0x81 && c <= 0xFE) lead = c, i++;
            else o += put(out + o, 0xFFFD), i++;
        }
        total += o;
    }
    clock_gettime(CLOCK_MONOTONIC, &b);
    printf("floor %ld B in %.1f ms; out %zu\n", n, (b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6, total);
    return 0;
}

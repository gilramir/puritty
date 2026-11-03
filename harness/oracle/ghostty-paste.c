/* The paste gate's oracle (docs/phase3-select.md §15): libghostty-vt's
 * ghostty_paste_encode, one case a line on standard input, "B HEX" with B
 * 1 for bracketed paste, its bytes in hex a line on standard output ("-"
 * for none). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ghostty/vt.h>

static int hex(char c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }

int main(void) {
    static char line[1 << 17], data[1 << 16], out[1 << 17];
    while (fgets(line, sizeof line, stdin)) {
        int b;
        char h[1 << 17];
        if (sscanf(line, "%d %131071s", &b, h) != 2) { puts("?"); continue; }
        size_t n = 0;
        if (strcmp(h, "-"))
            for (size_t i = 0; h[i] && h[i + 1]; i += 2) data[n++] = (char) (hex(h[i]) << 4 | hex(h[i + 1]));
        size_t len = 0;
        if (ghostty_paste_encode(data, n, b != 0, out, sizeof out, &len)) { puts("!"); continue; }
        if (!len) { puts("-"); continue; }
        for (size_t i = 0; i < len; i++) printf("%02x", (unsigned char) out[i]);
        putchar('\n');
    }
    return 0;
}

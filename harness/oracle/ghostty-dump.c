/* ghostty-dump: the differential oracle's reference side.
 *
 * Feeds a file of bytes to libghostty-vt and prints the terminal in
 * visiterm's screen dump (docs/vt-core.md §VC3), which the core prints too, so
 * the two are compared as text. The dump itself is gdump.c's, which the
 * fuzzer's comparison with the core calls too (§VC16).
 *
 * usage: ghostty-dump COLS ROWS FILE [RESIZES]
 *
 * RESIZES is `AT:COLSxROWS` items joined by commas: before byte AT of the
 * file the terminal is resized, as a host resizes it (docs/vt-core.md
 * §VC14). */
#include "gdump.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
  /* LINES, after RESIZES, is the scrollback's limit in lines; 0 is none, so
   * that a comparison with the core can give both terminals none (§VC32).
   * Left out, the library's default stays. */
  if (argc < 4 || argc > 6) {
    fprintf(stderr, "usage: ghostty-dump COLS ROWS FILE [RESIZES [LINES]]\n");
    return 2;
  }
  int cols = atoi(argv[1]), rows = atoi(argv[2]);
  if (cols <= 0 || cols > 256 || rows <= 0 || rows > 65535) {
    fprintf(stderr, "ghostty-dump: COLS is 1 to 256, ROWS at least 1\n");
    return 2;
  }
  FILE *f = fopen(argv[3], "rb");
  if (!f) {
    perror(argv[3]);
    return 1;
  }
  size_t cap = 1 << 16, len = 0;
  unsigned char *in = malloc(cap);
  for (size_t n; (n = fread(in + len, 1, cap - len, f)) > 0;) {
    len += n;
    if (len == cap) in = realloc(in, cap *= 2);
  }
  fclose(f);

  GResize rs[256];
  size_t nrs = 0, done = 0;
  for (const char *r = argc >= 5 ? argv[4] : ""; *r;) {
    char *end;
    size_t at = strtoul(r, &end, 10);
    unsigned c = 0, w = 0;
    if (nrs == 256 || sscanf(end, ":%ux%u", &c, &w) != 2 || at < done ||
        at > len || c == 0 || c > 256 || w == 0) {
      fprintf(stderr, "ghostty-dump: bad RESIZES at %s\n", r);
      return 2;
    }
    rs[nrs++] = (GResize){at, (uint16_t)c, (uint16_t)w};
    done = at;
    r = strchr(end, ',');
    r = r ? r + 1 : end + strlen(end);
  }
  size_t n;
  size_t lines = argc == 6 ? strtoul(argv[5], NULL, 10) : 0;
  if (argc == 6 && lines == 0) lines = SIZE_MAX;
  char *out = gdump((uint16_t)cols, (uint16_t)rows, in, len, rs, nrs,
                    argc == 6 ? &lines : NULL, &n);
  if (!out) {
    fprintf(stderr, "ghostty-dump: a libghostty-vt call failed\n");
    return 1;
  }
  fwrite(out, 1, n, stdout);
  free(out);
  return 0;
}

/* vt-min: the smallest input that is still the same kind of finding as a
 * vt-fuzz input (docs/vt-core.md §VC11), by delta debugging, in process.
 *
 * The first three bytes are kept as they are, since they choose the size and
 * the read's length; the rest is cut down for as long as the finding stays
 * a finding. A crash stays a crash and a split stays a split. Built with
 * VTFUZZ_DIFF it is vt-diff-min (§VC16): a difference from libghostty-vt
 * stays one, and in the same kind of line of the dump (the screen's size,
 * the cursor, the history's length, a row's text, its styles, a reply).
 *
 * usage: vt-min IN OUT */
#define _GNU_SOURCE
#include "vtfuzz.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int COLS[] = {1, 2, 3, 4, 5, 8, 10, 13, 20, 40, 80, 132};
static const int ROWS[] = {1, 2, 3, 4, 5, 8, 10, 24, 25, 50};
static int cols, rows, chunk;
#define NCOLS (sizeof COLS / sizeof *COLS)
#define NROWS (sizeof ROWS / sizeof *ROWS)

#ifdef VTFUZZ_DIFF
#include "diff.h"

/* The kind of line two dumps first differ in, from 3 up. */
static int line_kind(const char *a, size_t la, const char *b, size_t lb) {
  size_t i = 0, start = 0;
  while (i < la && i < lb && a[i] == b[i]) {
    if (a[i] == '\n') start = i + 1;
    i++;
  }
  const char *l = a + start;
  if (start >= la) return 3;
  if (*l == 's') return 4;
  if (*l == 'c') return 5;
  if (*l == 'h' && l[1] == 'i') return 6;
  if (*l == 'r') return 7;
  if (*l == ' ') return 8;
  return 9;
}

/* 0 if the core and ghostty dump it the same, 2 if a call failed, and the
 * kind of line they differ in otherwise. */
static int kind(const uint8_t *d, size_t n) {
  geng_handle in, a;
  if (vtfuzz_bytes_from(d, n, &in) != GENG_OK) return 2;
  geng_status sa = vtfuzz_dump(cols, rows, 0, LIMIT, in, &a);
  vtfuzz_release(in);
  if (sa != GENG_OK) return 2;
  const uint8_t *pa;
  size_t la, gl;
  vtfuzz_string_to_utf8(a, &pa, &la);
  char *core = malloc(la + 1), *g;
  memcpy(core, pa, la);
  vtfuzz_release(a);
  int k = 0;
  if (differs(cols, rows, d, n, COLS, NCOLS, ROWS, NROWS, core, &la, &g, &gl))
    k = g ? line_kind(core, la, g, gl) : 2;
  free(core);
  free(g);
  return k;
}
#else

/* 0 if it dumps the same both ways, 1 if not, 2 if a call failed. */
static int kind(const uint8_t *d, size_t n) {
  geng_handle in, a, b;
  if (vtfuzz_bytes_from(d, n, &in) != GENG_OK) return 2;
  geng_status sa = vtfuzz_dump(cols, rows, 0, 600, in, &a);
  geng_status sb = vtfuzz_dump(cols, rows, chunk, 600, in, &b);
  vtfuzz_release(in);
  if (sa != GENG_OK || sb != GENG_OK) {
    if (sa == GENG_OK) vtfuzz_release(a);
    if (sb == GENG_OK) vtfuzz_release(b);
    return 2;
  }
  const uint8_t *pa, *pb;
  size_t la, lb;
  vtfuzz_string_to_utf8(a, &pa, &la);
  vtfuzz_string_to_utf8(b, &pb, &lb);
  int differ = la != lb || memcmp(pa, pb, la) != 0;
  vtfuzz_release(a);
  vtfuzz_release(b);
  return differ;
}
#endif

int main(int argc, char **argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: vt-min IN OUT\n");
    return 2;
  }
  FILE *f = fopen(argv[1], "rb");
  if (!f) {
    perror(argv[1]);
    return 1;
  }
  static uint8_t buf[1 << 20];
  size_t size = fread(buf, 1, sizeof buf, f);
  fclose(f);
  if (size < 3 || vtfuzz_init() != GENG_OK) return 1;
  cols = COLS[buf[0] % (sizeof COLS / sizeof *COLS)];
  rows = ROWS[buf[1] % (sizeof ROWS / sizeof *ROWS)];
  chunk = 1 + buf[2] % 16;
  uint8_t *d = buf + 3;
  size_t n = size - 3;
  int want = kind(d, n);
  if (want == 0) {
    fprintf(stderr, "vt-min: %s is not a finding\n", argv[1]);
    return 1;
  }
  static uint8_t cand[1 << 20];
  size_t parts = 2;
  while (n >= 2) {
    size_t step = n / parts;
    int cut = 0;
    for (size_t i = 0; i < parts && step > 0; i++) {
      size_t from = i * step, to = i == parts - 1 ? n : from + step;
      size_t m = n - (to - from);
      if (m == 0) continue;
      memcpy(cand, d, from);
      memcpy(cand + from, d + to, n - to);
      if (kind(cand, m) == want) {
        memcpy(d, cand, m);
        n = m;
        parts = parts > 2 ? parts - 1 : 2;
        cut = 1;
        break;
      }
    }
    if (!cut) {
      if (parts >= n) break;
      parts = parts * 2 < n ? parts * 2 : n;
    }
  }
  FILE *o = fopen(argv[2], "wb");
  if (!o) {
    perror(argv[2]);
    return 1;
  }
  fwrite(buf, 1, 3 + n, o);
  fclose(o);
  fprintf(stderr, "vt-min: %zu bytes, %dx%d, reads of %d, %s\n", n, cols, rows,
          chunk, want == 1 ? "a split" : want == 2 ? "a crash" : "a difference");
  return 0;
}

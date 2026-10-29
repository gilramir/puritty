/* vt-min: the smallest input that is still the same kind of finding as a
 * vt-fuzz input (docs/vt-core.md §VC11), by delta debugging, in process.
 *
 * The first three bytes are kept as they are, since they choose the size and
 * the read's length; the rest is cut down for as long as the finding stays
 * a finding. A crash stays a crash and a split stays a split.
 *
 * usage: vt-min IN OUT */
#include "vtfuzz.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int COLS[] = {1, 2, 3, 4, 5, 8, 10, 13, 20, 40, 80, 132};
static const int ROWS[] = {1, 2, 3, 4, 5, 8, 10, 24, 25, 50};
static int cols, rows, chunk;

/* 0 if it dumps the same both ways, 1 if not, 2 if a call failed. */
static int kind(const uint8_t *d, size_t n) {
  geng_handle in, a, b;
  if (vtfuzz_bytes_from(d, n, &in) != GENG_OK) return 2;
  geng_status sa = vtfuzz_dump(cols, rows, 0, in, &a);
  geng_status sb = vtfuzz_dump(cols, rows, chunk, in, &b);
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
          chunk, want == 1 ? "a split" : "a crash");
  return 0;
}

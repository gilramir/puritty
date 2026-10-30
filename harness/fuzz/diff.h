/* vt-diff's comparison of the core with libghostty-vt (docs/vt-core.md
 * §VC16), included by fuzz.c and min.c when built with VTFUZZ_DIFF.
 *
 * An input is fed to both as `Fuzz.dump` feeds it to the core: its 0xFE
 * bytes, each with the two bytes after it, are resizes, to the sizes they
 * index in fuzz.c's tables, and are not fed. Both keep LIMIT lines of
 * scrollback; libghostty-vt keeps at least as many, a page more at most, so
 * while the core's history is under LIMIT the two must be the same, and
 * once it reaches it only the screen, the cursor and the replies are
 * compared. When it reached it before a resize, which the core's dump says
 * with a last line `pruned`, only the size and the replies are. */
#include "../oracle/gdump.h"
#include <stdlib.h>
#include <string.h>

#define LIMIT 10000

/* `data` without its resizes, into `out`, and the resizes, at offsets of
 * `out`; answers out's length. */
static size_t strip_resizes(const uint8_t *data, size_t n, const int *cols,
                            size_t ncols, const int *rows, size_t nrows,
                            uint8_t *out, GResize *rs, size_t *nrs) {
  size_t o = 0;
  *nrs = 0;
  for (size_t i = 0; i < n;) {
    if (data[i] == 0xFE) {
      int b1 = i + 1 < n ? data[i + 1] : 0;
      int b2 = i + 2 < n ? data[i + 2] : 0;
      rs[(*nrs)++] = (GResize){o, (uint16_t)cols[b1 % ncols],
                               (uint16_t)rows[b2 % nrows]};
      i += 3;
    } else {
      out[o++] = data[i++];
    }
  }
  return o;
}

/* The dump with its history taken out: the `history` line and every row
 * labelled `h`, with the style lines under them. In place. */
static size_t drop_history(char *d, size_t n) {
  size_t o = 0;
  int in_history = 0;
  for (size_t i = 0; i < n;) {
    size_t e = i;
    while (e < n && d[e] != '\n') e++;
    if (e < n) e++;
    int skip = 0;
    if (strncmp(d + i, "history ", 8) == 0) skip = 1;
    else if (d[i] == 'h' && e - i > 1 && d[i + 1] >= '0' && d[i + 1] <= '9')
      skip = in_history = 1;
    else if (d[i] == ' ' && in_history) skip = 1;
    else in_history = 0;
    if (!skip) {
      memmove(d + o, d + i, e - i);
      o += e - i;
    }
    i = e;
  }
  return o;
}

/* The dump with only its `screen` line and its replies, in place: once the
scrollback reached LIMIT before a resize, a line that runs on from it was
pruned at another point in each, and a reflow cuts its rows differently. */
static size_t only_replies(char *d, size_t n) {
  size_t o = 0;
  for (size_t i = 0; i < n;) {
    size_t e = i;
    while (e < n && d[e] != '\n') e++;
    if (e < n) e++;
    if (strncmp(d + i, "screen ", 7) == 0 || strncmp(d + i, "reply ", 6) == 0) {
      memmove(d + o, d + i, e - i);
      o += e - i;
    }
    i = e;
  }
  return o;
}

/* Ghostty's XTVERSION reply with the core's name in it, in place: each
answers with its own name, which is not a difference (docs/vt-core.md
§VC18). Only in a `reply` line: a row can hold the same text, and the
fuzzer finds that it can (§VC19). */
static size_t own_name(char *d, size_t n) {
  static const char from[] = "P>|libghostty\\x1b", to[] = "P>|visiterm\\x1b";
  size_t fl = sizeof from - 1, tl = sizeof to - 1, o = 0;
  int reply = n >= 6 && memcmp(d, "reply ", 6) == 0;
  for (size_t i = 0; i < n;) {
    if (d[i] == '\n')
      reply = i + 7 <= n && memcmp(d + i + 1, "reply ", 6) == 0;
    if (reply && i + fl <= n && memcmp(d + i, from, fl) == 0) {
      memcpy(d + o, to, tl);
      o += tl;
      i += fl;
    } else {
      d[o++] = d[i++];
    }
  }
  return o;
}

static size_t history_of(const char *d, size_t n) {
  const char *h = memmem(d, n, "\nhistory ", 9);
  return h ? strtoul(h + 9, NULL, 10) : 0;
}

/* Ghostty's dump of an input, compared to the core's: 1 if they differ.
 * `core` may be shortened in place. `ghostty` gets Ghostty's, malloc'd, or
 * NULL when a libghostty-vt call failed (a difference too). */
static int differs(int cols, int rows, const uint8_t *data, size_t n,
                   const int *ctab, size_t nc, const int *rtab, size_t nr,
                   char *core, size_t *core_len, char **ghostty,
                   size_t *ghostty_len) {
  uint8_t *fed = malloc(n + 1);
  GResize *rs = malloc(sizeof(GResize) * (n / 3 + 1));
  size_t nrs;
  size_t m = strip_resizes(data, n, ctab, nc, rtab, nr, fed, rs, &nrs);
  size_t limit = LIMIT;
  *ghostty = gdump((uint16_t)cols, (uint16_t)rows, fed, m, rs, nrs, &limit,
                   ghostty_len);
  free(fed);
  free(rs);
  if (!*ghostty) return 1;
  *ghostty_len = own_name(*ghostty, *ghostty_len);
  /* `pruned`: the core's scrollback may have reached LIMIT before a resize,
   * which can bring it back under with rows the two pruned differently and
   * reflow a line that runs on from them differently (Fuzz.dump,
   * docs/vt-core.md §VC17). */
  int pruned = *core_len >= 7 && memcmp(core + *core_len - 7, "pruned\n", 7) == 0;
  if (pruned) {
    *core_len = only_replies(core, *core_len - 7);
    *ghostty_len = only_replies(*ghostty, *ghostty_len);
  } else if (history_of(core, *core_len) >= LIMIT) {
    *core_len = drop_history(core, *core_len);
    *ghostty_len = drop_history(*ghostty, *ghostty_len);
  }
  return *core_len != *ghostty_len || memcmp(core, *ghostty, *core_len) != 0;
}

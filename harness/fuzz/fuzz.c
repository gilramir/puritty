/* vt-fuzz: libFuzzer over the core (docs/vt-core.md §VC11).
 *
 * The core is libvtfuzz, `Fuzz.dump` built as a runtime = "host" library and
 * compiled into this program with coverage. An input's first three bytes
 * choose the terminal's columns, its rows and a read's length; the rest is
 * what the terminal is fed, but for 0xFE and the two bytes after it, which
 * resize it to the sizes they index in the same tables (`Fuzz.dump`). Two
 * things are findings, and each aborts:
 *
 * - a crash: any call into the core answering other than GENG_OK, a Geng
 *   crash (an index out of range, a pattern not matched, the stack) among
 *   them;
 * - a split: the dump fed the input in one read differing from the dump fed
 *   it a read of that length at a time, which is every state the parser can
 *   be left in between two reads, as the replay corpus's byte-a-read run is.
 *
 * Built with VTFUZZ_DIFF it is vt-diff (§VC16): the finding is instead a
 * difference between the core's dump, fed the input in one read, and
 * libghostty-vt's (diff.h), and a crash.
 *
 * VTFUZZ_PRINT=1 prints both dumps of each input, to read a finding. */
#define _GNU_SOURCE
#include "vtfuzz.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int COLS[] = {1, 2, 3, 4, 5, 8, 10, 13, 20, 40, 80, 132};
static const int ROWS[] = {1, 2, 3, 4, 5, 8, 10, 24, 25, 50};
#define NCOLS (sizeof COLS / sizeof *COLS)
#define NROWS (sizeof ROWS / sizeof *ROWS)

#ifdef VTFUZZ_DIFF
#include "diff.h"
#define SCROLLBACK LIMIT
#else
/* three pages, so that a resize cuts pages again on their bytes (V20) */
#define SCROLLBACK 600
#endif

static void check(geng_status s, const char *what) {
  if (s == GENG_OK) return;
  const char *m = "";
  size_t n = 0;
  vtfuzz_last_error(&m, &n);
  fprintf(stderr, "vt-fuzz: %s answered %d: %.*s\n", what, (int)s, (int)n, m);
  abort();
}

/* The dump, copied out of the core, and its length. */
static char *dump(int cols, int rows, int chunk, geng_handle input,
                  size_t *len) {
  geng_handle d;
  check(vtfuzz_dump(cols, rows, chunk, SCROLLBACK, input, &d), "dump");
  const uint8_t *p;
  check(vtfuzz_string_to_utf8(d, &p, len), "string_to_utf8");
  char *copy = malloc(*len + 1);
  memcpy(copy, p, *len);
  copy[*len] = 0;
  check(vtfuzz_release(d), "release");
  return copy;
}

int LLVMFuzzerInitialize(int *argc, char ***argv) {
  (void)argc;
  (void)argv;
  check(vtfuzz_init(), "init");
  return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  if (size < 3) return 0;
  int cols = COLS[data[0] % NCOLS];
  int rows = ROWS[data[1] % NROWS];
  int chunk = 1 + data[2] % 16;
  geng_handle input;
#ifdef VTFUZZ_DIFF
  /* Ghostty prints DEL in the ground state, where the core and xterm
   * ignore it (docs/upstream/ghostty-del-is-printed.md): an input with one
   * is left out, not a finding, and not kept in the corpus. */
  if (memchr(data + 3, 0x7F, size - 3)) return -1;
  check(vtfuzz_bytes_from(data + 3, size - 3, &input), "bytes_from");
  size_t cl, gl;
  char *core = dump(cols, rows, 0, input, &cl), *ghostty;
  check(vtfuzz_release(input), "release");
  int differ = differs(cols, rows, data + 3, size - 3, COLS, NCOLS, ROWS,
                       NROWS, core, &cl, &ghostty, &gl);
  if (differ || getenv("VTFUZZ_PRINT")) {
    fprintf(stderr, "%dx%d\n--- the core\n%.*s--- ghostty\n%.*s", cols, rows,
            (int)cl, core, ghostty ? (int)gl : 0, ghostty ? ghostty : "");
  }
  free(core);
  free(ghostty);
  if (differ) {
    fprintf(stderr, "vt-fuzz: the core's dump differs from ghostty's\n");
    abort();
  }
  return 0;
#endif
  check(vtfuzz_bytes_from(data + 3, size - 3, &input), "bytes_from");
  size_t wl, sl;
  char *whole = dump(cols, rows, 0, input, &wl);
  char *split = dump(cols, rows, chunk, input, &sl);
  check(vtfuzz_release(input), "release");
  /* Fuzz.dump begins with this when the pages cut again on their bytes
   * differ from the reflow of their rows (docs/vt-core.md VC31). */
  if (strncmp(whole, "recut differs", 13) == 0) {
    fprintf(stderr, "%dx%d\n%s", cols, rows, whole);
    fprintf(stderr, "vt-fuzz: the pages cut on their bytes differ from their reflow\n");
    abort();
  }
  int same = wl == sl && memcmp(whole, split, wl) == 0;
  if (!same || getenv("VTFUZZ_PRINT")) {
    fprintf(stderr, "%dx%d, reads of %d\n--- in one read\n%s--- a read of %d at a time\n%s",
            cols, rows, chunk, whole, chunk, split);
  }
  free(whole);
  free(split);
  if (!same) {
    fprintf(stderr, "vt-fuzz: the dump differs when the input is split\n");
    abort();
  }
  return 0;
}

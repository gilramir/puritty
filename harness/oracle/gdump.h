/* gdump: libghostty-vt fed bytes and printed as puritty's screen dump. */
#ifndef GDUMP_H
#define GDUMP_H
#include <stddef.h>
#include <stdint.h>

/* Before byte `at` of the input the terminal is resized, as a host
 * resizes it (docs/vt-core.md §VC14). */
typedef struct {
  size_t at;
  uint16_t cols, rows;
} GResize;

/* The dump of a terminal of `cols` by `rows` fed `in`, resized where
 * `resizes` say, in order. `max_lines`, when not NULL, is the scrollback's
 * line limit, with no byte limit; NULL keeps libghostty-vt's defaults.
 * The answer is malloc'd, `*out_len` bytes; NULL if a call failed. Not
 * reentrant. */
char *gdump(uint16_t cols, uint16_t rows, const uint8_t *in, size_t len,
            const GResize *resizes, size_t nresizes, const size_t *max_lines,
            size_t *out_len);
#endif

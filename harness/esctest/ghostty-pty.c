/* ghostty-pty: libghostty-vt as the terminal esctest2 runs in, the oracle's
 * side of docs/vt-core.md §VC10.
 *
 * Reads standard input as it comes, writes it to a libghostty-vt terminal of
 * COLS by ROWS, and writes the terminal's replies to standard output.
 * harness/esctest.py gives it a pty's master as both. The terminal is set up
 * as Ghostty's own runner (vendor/ghostty/test/esctest/src/main.zig) sets it
 * up: DECRQCRA on, with xterm's checksumExtension 23, and CSI 8 t resizes
 * the terminal and the pty. Its runner also answers DA as a VT520; this
 * leaves libghostty-vt's own VT220, which is what the core answers, so that
 * the two runs differ only where the two cores do.
 *
 * usage: ghostty-pty COLS ROWS
 */
#include <errno.h>
#include <ghostty/vt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

static uint16_t cols, rows;

static void on_write_pty(GhosttyTerminal t, void *u, const uint8_t *data,
                         size_t len) {
  (void)t;
  (void)u;
  while (len > 0) {
    ssize_t n = write(1, data, len);
    if (n < 0) {
      if (errno == EINTR) continue;
      return;
    }
    data += n;
    len -= (size_t)n;
  }
}

static bool on_size(GhosttyTerminal t, void *u, GhosttySizeReportSize *out) {
  (void)t;
  (void)u;
  out->rows = rows;
  out->columns = cols;
  out->cell_width = 10;
  out->cell_height = 20;
  return true;
}

/* As xterm does with CSI 8 t: a dimension given as 0 is kept. */
static void on_resize_window(GhosttyTerminal t, void *u,
                             const GhosttyTerminalResizeWindow *req) {
  (void)u;
  if (req->tag != GHOSTTY_TERMINAL_RESIZE_WINDOW_GRID) return;
  uint16_t r = req->value.grid.rows ? req->value.grid.rows : rows;
  uint16_t c = req->value.grid.columns ? req->value.grid.columns : cols;
  if (ghostty_terminal_resize(t, c, r, 10, 20) != GHOSTTY_SUCCESS) return;
  rows = r;
  cols = c;
  struct winsize ws = {.ws_row = r, .ws_col = c};
  ioctl(1, TIOCSWINSZ, &ws);
}

int main(int argc, char **argv) {
  cols = argc > 1 ? (uint16_t)atoi(argv[1]) : 80;
  rows = argc > 2 ? (uint16_t)atoi(argv[2]) : 25;
  GhosttyTerminal term;
  if (ghostty_terminal_new(NULL, &term, cols, rows) != GHOSTTY_SUCCESS) {
    fprintf(stderr, "ghostty-pty: terminal_new failed\n");
    return 1;
  }
  bool on = true;
  uint8_t extension = 23;
  ghostty_terminal_set(term, GHOSTTY_TERMINAL_OPT_WRITE_PTY,
                       (const void *)on_write_pty);
  ghostty_terminal_set(term, GHOSTTY_TERMINAL_OPT_SIZE, (const void *)on_size);
  ghostty_terminal_set(term, GHOSTTY_TERMINAL_OPT_RESIZE_WINDOW,
                       (const void *)on_resize_window);
  ghostty_terminal_set(term, GHOSTTY_TERMINAL_OPT_XT_CHECKSUM_REPORT, &on);
  ghostty_terminal_set(term, GHOSTTY_TERMINAL_OPT_XT_CHECKSUM_EXTENSION,
                       &extension);

  uint8_t buf[4096];
  for (;;) {
    ssize_t n = read(0, buf, sizeof buf);
    if (n > 0) {
      ghostty_terminal_vt_write(term, buf, (size_t)n);
      continue;
    }
    /* A pty's master reads EIO once the other side has closed. */
    if (n < 0 && errno == EINTR) continue;
    break;
  }
  ghostty_terminal_free(term);
  return 0;
}

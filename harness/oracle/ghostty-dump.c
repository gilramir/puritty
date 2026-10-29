/* ghostty-dump: the differential oracle's reference side.
 *
 * Feeds a file of bytes to libghostty-vt and prints the terminal in
 * visiterm's screen dump (docs/vt-core.md §VC3), which the core prints too, so
 * the two are compared as text.
 *
 * usage: ghostty-dump COLS ROWS FILE
 */
#include <ghostty/vt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  unsigned char *data;
  size_t len, cap;
} Buf;

static Buf replies;

static void on_write_pty(GhosttyTerminal t, void *ud, const uint8_t *data,
                         size_t len) {
  (void)t;
  (void)ud;
  /* Each reply is kept whole, one line of the dump each. */
  size_t need = replies.len + len + sizeof(size_t);
  if (need > replies.cap) {
    replies.cap = need * 2;
    replies.data = realloc(replies.data, replies.cap);
    if (!replies.data) abort();
  }
  memcpy(replies.data + replies.len, &len, sizeof(size_t));
  memcpy(replies.data + replies.len + sizeof(size_t), data, len);
  replies.len += sizeof(size_t) + len;
}

static void put_utf8(FILE *o, uint32_t c) {
  if (c < 0x80) {
    fputc((int)c, o);
  } else if (c < 0x800) {
    fputc(0xC0 | (c >> 6), o);
    fputc(0x80 | (c & 0x3F), o);
  } else if (c < 0x10000) {
    fputc(0xE0 | (c >> 12), o);
    fputc(0x80 | ((c >> 6) & 0x3F), o);
    fputc(0x80 | (c & 0x3F), o);
  } else {
    fputc(0xF0 | (c >> 18), o);
    fputc(0x80 | ((c >> 12) & 0x3F), o);
    fputc(0x80 | ((c >> 6) & 0x3F), o);
    fputc(0x80 | (c & 0x3F), o);
  }
}

/* A style as the dump writes it: "" for the default. */
static void color_text(char *out, size_t n, const char *name,
                       GhosttyStyleColor c) {
  switch (c.tag) {
  case GHOSTTY_STYLE_COLOR_PALETTE:
    snprintf(out, n, " %s=%u", name, c.value.palette);
    break;
  case GHOSTTY_STYLE_COLOR_RGB:
    snprintf(out, n, " %s=#%02x%02x%02x", name, c.value.rgb.r, c.value.rgb.g,
             c.value.rgb.b);
    break;
  default:
    out[0] = 0;
  }
}

static void style_text(char *out, size_t n, const GhosttyStyle *s) {
  char fg[32], bg[32], ul[32];
  color_text(fg, sizeof fg, "fg", s->fg_color);
  color_text(bg, sizeof bg, "bg", s->bg_color);
  color_text(ul, sizeof ul, "ulc", s->underline_color);
  char under[16] = "";
  if (s->underline) snprintf(under, sizeof under, " ul=%d", s->underline);
  snprintf(out, n, "%s%s%s%s%s%s%s%s%s%s%s%s", fg, bg,
           s->bold ? " bold" : "", s->faint ? " faint" : "",
           s->italic ? " italic" : "", under, ul, s->blink ? " blink" : "",
           s->inverse ? " inverse" : "", s->invisible ? " invisible" : "",
           s->strikethrough ? " strike" : "", s->overline ? " overline" : "");
}

static GhosttyTerminal term;
static uint16_t cols;

static int ref_at(GhosttyPointTag tag, uint16_t x, uint32_t y,
                  GhosttyGridRef *ref) {
  *ref = (GhosttyGridRef)GHOSTTY_INIT_SIZED(GhosttyGridRef);
  GhosttyPoint pt = {.tag = tag, .value = {.coordinate = {.x = x, .y = y}}};
  return ghostty_terminal_grid_ref(term, pt, ref) == GHOSTTY_SUCCESS;
}

/* One row: its text line, then its style runs. */
static void dump_row(FILE *o, const char *label, GhosttyPointTag tag,
                     uint32_t y) {
  char styles[256][160];
  int wide[256];
  uint32_t text[256][16];
  size_t tlen[256];
  int last = -1;
  GhosttyGridRef ref;
  for (uint16_t x = 0; x < cols; x++) {
    tlen[x] = 0;
    wide[x] = 0;
    styles[x][0] = 0;
    if (!ref_at(tag, x, y, &ref)) continue;
    GhosttyCell cell;
    ghostty_grid_ref_cell(&ref, &cell);
    GhosttyCellWide w = GHOSTTY_CELL_WIDE_NARROW;
    ghostty_cell_get(cell, GHOSTTY_CELL_DATA_WIDE, &w);
    wide[x] = (int)w;
    bool has_text = false;
    ghostty_cell_get(cell, GHOSTTY_CELL_DATA_HAS_TEXT, &has_text);
    if (has_text) {
      size_t n = 0;
      if (ghostty_grid_ref_graphemes(&ref, text[x], 16, &n) == GHOSTTY_SUCCESS)
        tlen[x] = n;
      last = x;
    }
    GhosttyStyle st = GHOSTTY_INIT_SIZED(GhosttyStyle);
    ghostty_grid_ref_style(&ref, &st);
    GhosttyCellContentTag ct = GHOSTTY_CELL_CONTENT_CODEPOINT;
    ghostty_cell_get(cell, GHOSTTY_CELL_DATA_CONTENT_TAG, &ct);
    if (ct == GHOSTTY_CELL_CONTENT_BG_COLOR_PALETTE) {
      GhosttyColorPaletteIndex p = 0;
      ghostty_cell_get(cell, GHOSTTY_CELL_DATA_COLOR_PALETTE, &p);
      st.bg_color.tag = GHOSTTY_STYLE_COLOR_PALETTE;
      st.bg_color.value.palette = p;
    } else if (ct == GHOSTTY_CELL_CONTENT_BG_COLOR_RGB) {
      GhosttyColorRgb c = {0};
      ghostty_cell_get(cell, GHOSTTY_CELL_DATA_COLOR_RGB, &c);
      st.bg_color.tag = GHOSTTY_STYLE_COLOR_RGB;
      st.bg_color.value.rgb = c;
    }
    style_text(styles[x], sizeof styles[x], &st);
  }
  bool wrap = false;
  if (ref_at(tag, 0, y, &ref)) {
    GhosttyRow row;
    ghostty_grid_ref_row(&ref, &row);
    ghostty_row_get(row, GHOSTTY_ROW_DATA_WRAP, &wrap);
  }
  fprintf(o, "%s%s |", label, wrap ? "+" : "");
  for (int x = 0; x <= last; x++) {
    if (wide[x] == GHOSTTY_CELL_WIDE_SPACER_TAIL ||
        wide[x] == GHOSTTY_CELL_WIDE_SPACER_HEAD)
      continue;
    if (tlen[x] == 0) fputc(' ', o);
    for (size_t i = 0; i < tlen[x]; i++) put_utf8(o, text[x][i]);
  }
  fputs("|\n", o);
  for (int x = 0; x < cols;) {
    int e = x;
    while (e + 1 < cols && strcmp(styles[e + 1], styles[x]) == 0) e++;
    if (styles[x][0]) fprintf(o, "  %d-%d%s\n", x, e, styles[x]);
    x = e + 1;
  }
}

int main(int argc, char **argv) {
  if (argc != 4) {
    fprintf(stderr, "usage: ghostty-dump COLS ROWS FILE\n");
    return 2;
  }
  cols = (uint16_t)atoi(argv[1]);
  uint16_t rows = (uint16_t)atoi(argv[2]);
  if (cols == 0 || cols > 256 || rows == 0) {
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

  if (ghostty_terminal_new(NULL, &term, cols, rows) != GHOSTTY_SUCCESS) {
    fprintf(stderr, "ghostty-dump: terminal_new failed\n");
    return 1;
  }
  ghostty_terminal_set(term, GHOSTTY_TERMINAL_OPT_WRITE_PTY,
                       (const void *)on_write_pty);
  ghostty_terminal_vt_write(term, in, len);

  uint16_t cx = 0, cy = 0;
  bool pending = false, visible = true;
  GhosttyTerminalScreen scr = GHOSTTY_TERMINAL_SCREEN_PRIMARY;
  size_t history = 0;
  ghostty_terminal_get(term, GHOSTTY_TERMINAL_DATA_CURSOR_X, &cx);
  ghostty_terminal_get(term, GHOSTTY_TERMINAL_DATA_CURSOR_Y, &cy);
  ghostty_terminal_get(term, GHOSTTY_TERMINAL_DATA_CURSOR_PENDING_WRAP,
                       &pending);
  ghostty_terminal_get(term, GHOSTTY_TERMINAL_DATA_CURSOR_VISIBLE, &visible);
  ghostty_terminal_get(term, GHOSTTY_TERMINAL_DATA_ACTIVE_SCREEN, &scr);
  ghostty_terminal_get(term, GHOSTTY_TERMINAL_DATA_SCROLLBACK_ROWS, &history);

  FILE *o = stdout;
  fprintf(o, "screen %ux%u %s\n", cols, rows,
          scr == GHOSTTY_TERMINAL_SCREEN_ALTERNATE ? "alt" : "main");
  fprintf(o, "cursor %u,%u%s%s\n", cx, cy, pending ? " wrap" : "",
          visible ? "" : " hidden");
  fprintf(o, "history %zu\n", history);
  char label[32];
  for (size_t y = 0; y < history; y++) {
    snprintf(label, sizeof label, "h%zu", y);
    dump_row(o, label, GHOSTTY_POINT_TAG_HISTORY, (uint32_t)y);
  }
  for (uint16_t y = 0; y < rows; y++) {
    snprintf(label, sizeof label, "%u", y);
    dump_row(o, label, GHOSTTY_POINT_TAG_ACTIVE, y);
  }
  for (size_t at = 0; at < replies.len;) {
    size_t n;
    memcpy(&n, replies.data + at, sizeof(size_t));
    at += sizeof(size_t);
    fputs("reply ", o);
    for (size_t i = 0; i < n; i++) {
      unsigned char c = replies.data[at + i];
      if (c >= 0x21 && c < 0x7F && c != '\\') fputc(c, o);
      else fprintf(o, "\\x%02x", c);
    }
    fputc('\n', o);
    at += n;
  }
  ghostty_terminal_free(term);
  return 0;
}

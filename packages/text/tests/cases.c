/* The text package's C, tested on the C itself: puritty_text.c is
 * included, so its static functions can be called, and the platform's
 * functions are stubs that record what was asked of them.
 *
 *   cases TTF OTB SANS
 *
 * The interface's glyph cache (the code review's X15): *
 * TTF is an outline font, loaded as 70 faces by 70 links to it in a fresh
 * folder; glyph 36 of face 1 and of face 65 at 16 px must be two glyphs
 * (before X15 the key kept six bits of the face, so face 65 was given face
 * 1's). OTB is a font of 1-bit strikes (Terminus's 16 px): its glyph is
 * read as bits only, which AddressSanitizer checks (before X15 each pixel
 * of the bitmap's last row read a byte, past the row's `pitch` bytes).
 *
 * A run in a frame's list that says more cells than the list holds (X26):
 * `draw_run` must give up the frame and fill nothing (before X26 it went
 * on with the cells' styles left from before, and its glyph pass read the
 * missing cells past the list).
 *
 * The fallback cache (X14): with Terminus as the only face, `e` and
 * U+20D0, which the platform finds no font for, then `e` and U+0309,
 * which it answers with TTF: the second must be asked, and drawn in TTF
 * (before X14 the cache was keyed by `e` alone and gave the first's -1).
 *
 * A glyph centered in its box (X24): with OTB the primary font (opened as
 * the window does), U+0249, which only SANS of the three has and which is
 * narrower than a cell, drawn in one cell and then as a wide cell's head,
 * two cells: its ink must move right by half a cell, the second pad less
 * the first (before X24 the first pad was kept in the uploaded glyph, and
 * the second drawing was where the first was).
 *
 * A frame's image placements (X22): an image of one pixel placed in 300
 * cells of one frame must be drawn 300 times (before X22 a frame drew 256
 * and dropped the rest). */
#include "../src/Ext/puritty_text.c"

#include <unistd.h>

static int added;
/* each glyph's left bearing as uploaded, by id */
static uint32_t added_id[4096];
static int added_left[4096];
void pt_glyph_add(uint32_t id, const PtGlyph *glyph) {
    if (added < 4096) {
        added_id[added] = id;
        added_left[added] = glyph->left;
    }
    added++;
}
static int left_of(uint32_t id) {
    for (int i = added < 4096 ? added - 1 : 4095; i >= 0; i--)
        if (added_id[i] == id) return added_left[i];
    return -10000;
}
/* the last glyph placed, and its x */
static uint32_t drawn_id;
static int drawn_x;
/* the primary font's file, whatever its name */
static const char *primary_file;
char *pt_font_file(const char *font, int variant, int *index) {
    (void) font, (void) variant;
    *index = 0;
    return primary_file ? copy(primary_file) : NULL;
}
/* what the platform's fallback answers: a copy of this file, or none */
static const char *fallback_answer;
static int fallback_asked;
char *pt_fallback_file(const uint32_t *cps, int n, int color, const char *lang, int *index) {
    (void) cps, (void) n, (void) color, (void) lang;
    fallback_asked++;
    *index = 0;
    return fallback_answer ? copy(fallback_answer) : NULL;
}
const char *pt_fallback_family(void) { return ""; }
static int filled;
void pt_fill(uint32_t rgb, int x, int y, int w, int h) {
    (void) rgb, (void) x, (void) y, (void) h;
    filled += w;
}
void pt_fill_rects(uint32_t rgb, const PtRect *rects, int n) { (void) rgb, (void) rects, (void) n; }
void pt_glyphs_reset(void) {}
void pt_glyphs_draw(const PtPlaced *placed, int n, const PtRect *clips) {
    (void) clips;
    if (n > 0) drawn_id = placed[n - 1].id, drawn_x = placed[n - 1].x;
}
static int a_picture, pictures_drawn;
void *pt_picture_add(const uint32_t *argb, int w, int h) {
    (void) argb, (void) w, (void) h;
    return &a_picture;
}
void pt_picture_draw(void *picture, int x, int y, int w, int h) { (void) picture, (void) x, (void) y, (void) w, (void) h; }
void pt_picture_free(void *picture) { (void) picture; }
void pt_picture_draw_part(void *picture, int sx, int sy, int sw, int sh, int dx, int dy, int dw, int dh, int cx, int cy, int cw,
                          int ch) {
    (void) picture, (void) sx, (void) sy, (void) sw, (void) sh, (void) dx, (void) dy, (void) dw, (void) dh, (void) cx, (void) cy,
        (void) cw, (void) ch;
    pictures_drawn++;
}
void pt_target(int c, int r) { (void) c, (void) r; }
void pt_scroll(int top, int bottom, int k) { (void) top, (void) bottom, (void) k; }

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: cases TTF OTB SANS\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    primary_file = argv[2];
    if (pt_open("Terminus", "en", 12, 96, 64L << 20) != 0) {
        fprintf(stderr, "the primary font did not open\n");
        return 2;
    }
    char dir[] = "/tmp/textcases-XXXXXX";
    if (!mkdtemp(dir)) return 2;
    int wrong = 0;
    for (int k = 0; k < 70; k++) {
        char link[64];
        snprintf(link, sizeof link, "%s/f%d.ttf", dir, k);
        if (symlink(argv[1], link) != 0 || ui_load(link, 0) != k) {
            fprintf(stderr, "face %d did not load\n", k);
            return 2;
        }
    }
    int advance = 0;
    uint32_t one = ui_glyph(1, 16, 36, &advance), other = ui_glyph(65, 16, 36, &advance);
    printf("glyph 36 at 16 px: face 1 is %u, face 65 is %u\n", one, other);
    if (one == 0 || one == other) {
        printf("FAIL: faces 1 and 65 share a glyph\n");
        wrong = 1;
    }
    int mono = ui_load(argv[2], 0);
    uint32_t bits = mono >= 0 ? ui_glyph(mono, 16, 36, &advance) : 0;
    printf("1-bit glyph: %u, mode %d\n", bits, mono >= 0 ? ui_faces[mono].ft->glyph->bitmap.pixel_mode : -1);
    if (bits == 0 || ui_faces[mono].ft->glyph->bitmap.pixel_mode != FT_PIXEL_MODE_MONO) {
        printf("FAIL: the 1-bit font gave no 1-bit glyph\n");
        wrong = 1;
    }
    for (int k = 0; k < 70; k++) {
        char link[64];
        snprintf(link, sizeof link, "%s/f%d.ttf", dir, k);
        unlink(link);
    }
    /* a run at row 0, column 0, of 5 cells, with 2 cells in the list */
    pt_cw = 8, pt_ch = 16, pt_cols = 80, pt_rows = 24;
    uint8_t *list = malloc(7 + 2 * 3);
    const uint8_t head[7] = {2, 0, 0, 0, 0, 0, 5};
    memcpy(list, head, 7);
    memset(list + 7, 0, 6);
    const uint8_t *end = list + 13, *after = draw_run(list, end, 0);
    printf("a run of 5 cells with 2 in the list: %d pixels filled, %s\n", filled, after == end ? "the frame given up" : "went on");
    if (filled != 0 || after != end) {
        printf("FAIL: a short run was drawn\n");
        wrong = 1;
    }
    free(list);

    /* the fallback cache, keyed by the whole cluster */
    int terminus = load_face(argv[2], 0, 1);
    const uint32_t nowhere[2] = {'e', 0x20D0}, hook[2] = {'e', 0x0309};
    fallback_answer = NULL;
    int first = fallback(nowhere, 2);
    fallback_answer = argv[1];
    int second = fallback(hook, 2);
    printf("fallback with Terminus as face %d: e+20D0 face %d, e+0309 face %d, the platform asked %d times\n", terminus, first,
           second, fallback_asked);
    if (first != -1 || second < 0 || fallback_asked != 2) {
        printf("FAIL: e+0309 was answered from e+20D0's miss\n");
        wrong = 1;
    }

    /* a glyph centered in a box of one cell, then of two */
    fallback_answer = argv[3];
    const uint8_t in_one[6] = {1, 0, 0, 0x00, 0x02, 0x49}, in_two[9] = {(1 << 6) | 1, 0, 0, 0x00, 0x02, 0x49, 2 << 6, 0, 0};
    draw_glyphs(0, 0, 1, in_one);
    flush_placed();
    int narrow = drawn_x + left_of(drawn_id);
    draw_glyphs(0, 0, 2, in_two);
    flush_placed();
    int wide = drawn_x + left_of(drawn_id);
    printf("U+0249 centered, cell %d px: its ink at %d in one cell, %d in two\n", pt_cw, narrow, wide);
    if (wide - narrow != pt_cw / 2) {
        printf("FAIL: the two-cell drawing is not half a cell right of the one-cell one\n");
        wrong = 1;
    }

    /* 300 placements of a 1 by 1 image in one frame */
    enum { PLACEMENTS = 300 };
    pt_cols = 80, pt_rows = 24;
    size_t length = 13 + (size_t) PLACEMENTS * PLACE_SIZE;
    uint8_t *frame = must(calloc(length, 1));
    const uint8_t define[13] = {0x0A, 0, 0, 0, 1, 0, 1, 0, 1, 3, 255, 0, 0};
    memcpy(frame, define, 13);
    for (int i = 0; i < PLACEMENTS; i++) {
        uint8_t *q = frame + 13 + (size_t) i * PLACE_SIZE;
        int x = i % 80, y = i / 80;
        q[0] = 0x0C, q[4] = 1;
        q[5] = (uint8_t) (x >> 8), q[6] = (uint8_t) x, q[7] = (uint8_t) (y >> 8), q[8] = (uint8_t) y;
        q[10] = 1, q[12] = 1, q[18] = 1, q[20] = 1, q[26] = 1, q[28] = 1;
        q[34] = 80, q[36] = 24;
    }
    PtFrame shown;
    pt_frame(frame, length, &shown);
    free(frame);
    printf("%d placements in a frame: %d drawn\n", PLACEMENTS, pictures_drawn);
    if (pictures_drawn != PLACEMENTS) {
        printf("FAIL: a frame's placements past some were dropped\n");
        wrong = 1;
    }
    rmdir(dir);
    printf(wrong ? "FAILED\n" : "OK\n");
    return wrong;
}

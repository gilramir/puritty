/* The text package's C, tested on the C itself: puritty_text.c is
 * included, so its static functions can be called, and the platform's
 * functions are stubs that record what was asked of them.
 *
 *   cases TTF OTB
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
 * missing cells past the list). */
#include "../src/Ext/puritty_text.c"

#include <unistd.h>

static int added;
void pt_glyph_add(uint32_t id, const PtGlyph *glyph) {
    (void) id;
    (void) glyph;
    added++;
}
char *pt_font_file(const char *font, int variant, int *index) {
    (void) font, (void) variant, (void) index;
    return NULL;
}
char *pt_fallback_file(const uint32_t *cps, int n, int color, const char *lang, int *index) {
    (void) cps, (void) n, (void) color, (void) lang, (void) index;
    return NULL;
}
const char *pt_fallback_family(void) { return ""; }
static int filled;
void pt_fill(uint32_t rgb, int x, int y, int w, int h) {
    (void) rgb, (void) x, (void) y, (void) h;
    filled += w;
}
void pt_fill_rects(uint32_t rgb, const PtRect *rects, int n) { (void) rgb, (void) rects, (void) n; }
void pt_glyphs_reset(void) {}
void pt_glyphs_draw(const PtPlaced *placed, int n, const PtRect *clips) { (void) placed, (void) n, (void) clips; }
void *pt_picture_add(const uint32_t *argb, int w, int h) {
    (void) argb, (void) w, (void) h;
    return NULL;
}
void pt_picture_draw(void *picture, int x, int y, int w, int h) { (void) picture, (void) x, (void) y, (void) w, (void) h; }
void pt_picture_free(void *picture) { (void) picture; }
void pt_picture_draw_part(void *picture, int sx, int sy, int sw, int sh, int dx, int dy, int dw, int dh, int cx, int cy, int cw,
                          int ch) {
    (void) picture, (void) sx, (void) sy, (void) sw, (void) sh, (void) dx, (void) dy, (void) dw, (void) dh, (void) cx, (void) cy,
        (void) cw, (void) ch;
}
void pt_target(int c, int r) { (void) c, (void) r; }
void pt_scroll(int top, int bottom, int k) { (void) top, (void) bottom, (void) k; }

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: cases TTF OTB\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    if (FT_Init_FreeType(&library) != 0) return 2;
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
    rmdir(dir);
    printf(wrong ? "FAILED\n" : "OK\n");
    return wrong;
}

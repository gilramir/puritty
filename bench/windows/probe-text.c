/* puritty's Windows survey (docs/windows.md): puritty's Linux text path,
 * FreeType and HarfBuzz, on Windows' own font files. Shapes one line in
 * four faces (Fira Code with its ligatures, Malgun Gothic for Hangul,
 * Leelawadee UI for Thai, Segoe UI Emoji in color), rasterizes it into a
 * buffer as puritty's renderer does, and writes probe-text.ppm and
 * probe-text.log beside the program: FreeType's version, each face's
 * glyphs and advances, the emoji's glyph format (BGRA when its color
 * table is drawn), and the time to shape and rasterize. No window: the
 * picture is what matters, and the window probe shows how it reaches the
 * screen. */

#include <ft2build.h>
#include FT_FREETYPE_H
#include <hb-ft.h>
#include <hb.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#define W 1600
#define H 220

static uint8_t img[H][W][3];
static FILE *out;
static FT_Library lib;

static double now_ms(void) {
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (double) t.QuadPart * 1000.0 / (double) f.QuadPart;
}

static void blend(int x, int y, int r, int g, int b, int a) {
    if (x < 0 || y < 0 || x >= W || y >= H || a == 0) return;
    for (int c = 0; c < 3; c++) {
        int v = c == 0 ? r : c == 1 ? g : b;
        img[y][x][c] = (uint8_t) ((v * a + img[y][x][c] * (255 - a)) / 255);
    }
}

/* One run of text in one face, from pen x at baseline y; answers the new x. */
static int run(const char *path, int index, const char *text, int px, int x, int y, int color) {
    FT_Face face;
    if (FT_New_Face(lib, path, index, &face)) {
        fprintf(out, "%s: cannot open\n", path);
        return x;
    }
    if (FT_HAS_FIXED_SIZES(face) && !FT_IS_SCALABLE(face))
        FT_Select_Size(face, 0);
    else
        FT_Set_Pixel_Sizes(face, 0, (FT_UInt) px);
    hb_font_t *font = hb_ft_font_create_referenced(face);
    hb_buffer_t *buf = hb_buffer_create();
    hb_buffer_add_utf8(buf, text, -1, 0, -1);
    hb_buffer_guess_segment_properties(buf);
    double t0 = now_ms();
    hb_shape(font, buf, NULL, 0);
    double t1 = now_ms();
    unsigned n;
    hb_glyph_info_t *info = hb_buffer_get_glyph_infos(buf, &n);
    hb_glyph_position_t *pos = hb_buffer_get_glyph_positions(buf, &n);
    fprintf(out, "%s: %s, color %d, %u glyphs from %zu bytes, shaped in %.3f ms; glyphs:", path, face->family_name,
            FT_HAS_COLOR(face), n, strlen(text), t1 - t0);
    for (unsigned i = 0; i < n; i++) {
        FT_Int32 flags = color ? FT_LOAD_COLOR : FT_LOAD_TARGET_LIGHT;
        if (FT_Load_Glyph(face, info[i].codepoint, flags)) continue;
        FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL);
        FT_Bitmap *bm = &face->glyph->bitmap;
        if (i < 12) fprintf(out, " %u(%s)", info[i].codepoint, bm->pixel_mode == FT_PIXEL_MODE_BGRA ? "bgra" : "gray");
        int gx = x + (pos[i].x_offset >> 6) + face->glyph->bitmap_left;
        int gy = y - (pos[i].y_offset >> 6) - face->glyph->bitmap_top;
        for (unsigned r = 0; r < bm->rows; r++)
            for (unsigned c = 0; c < bm->width; c++) {
                uint8_t *p = bm->buffer + r * bm->pitch;
                if (bm->pixel_mode == FT_PIXEL_MODE_BGRA)
                    blend(gx + (int) c, gy + (int) r, p[c * 4 + 2], p[c * 4 + 1], p[c * 4], p[c * 4 + 3]);
                else
                    blend(gx + (int) c, gy + (int) r, 235, 235, 235, p[c]);
            }
        x += pos[i].x_advance >> 6;
    }
    fprintf(out, "; rasterized in %.3f ms\n", now_ms() - t1);
    hb_buffer_destroy(buf);
    hb_font_destroy(font);
    return x;
}

int main(int argc, char **argv) {
    (void) argc;
    char path[MAX_PATH];
    snprintf(path, sizeof path, "%s", argv[0]);
    char *dot = strrchr(path, '.');
    if (dot) strcpy(dot, ".log");
    out = fopen(path, "w");
    if (!out) return 1;
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) img[y][x][0] = 0x1e, img[y][x][1] = 0x1e, img[y][x][2] = 0x2a;
    FT_Init_FreeType(&lib);
    FT_Int a, b, c;
    FT_Library_Version(lib, &a, &b, &c);
    fprintf(out, "FreeType %d.%d.%d, HarfBuzz %s\n", a, b, c, hb_version_string());
    char fira[MAX_PATH];
    snprintf(fira, sizeof fira, "%s\\Microsoft\\Windows\\Fonts\\FiraCode-Regular.ttf", getenv("LOCALAPPDATA"));
    int px = 42, x = 20, y = 80;
    x = run(fira, 0, "Fira Code -> => != 0x1F ", px, x, y, 0);
    x = run("C:\\Windows\\Fonts\\malgun.ttf", 0, "\xed\x95\x9c\xea\xb5\xad\xec\x96\xb4 ", px, x, y, 0);
    x = run("C:\\Windows\\Fonts\\LeelawUI.ttf", 0, "\xe0\xb8\xa0\xe0\xb8\xb2\xe0\xb8\xa9\xe0\xb8\xb2\xe0\xb9\x84\xe0\xb8\x97\xe0\xb8\xa2 ", px, x, y, 0);
    x = run("C:\\Windows\\Fonts\\seguiemj.ttf", 0, "\xf0\x9f\x98\x80\xf0\x9f\x91\x8d\xf0\x9f\x8f\xbd\xf0\x9f\x87\xb0\xf0\x9f\x87\xb7", px, x, y, 1);
    y = 170;
    x = 20;
    x = run(fira, 0, "puritty: FreeType + HarfBuzz on Windows' own fonts", 32, x, y, 0);
    snprintf(path, sizeof path, "%s", argv[0]);
    dot = strrchr(path, '.');
    if (dot) strcpy(dot, ".ppm");
    FILE *ppm = fopen(path, "wb");
    fprintf(ppm, "P6\n%d %d\n255\n", W, H);
    fwrite(img, 1, sizeof img, ppm);
    fclose(ppm);
    fprintf(out, "done\n");
    fclose(out);
    return 0;
}

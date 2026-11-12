/* Phase 2's font survey (docs/phase2-window.md §13): what shaping and
 * fallback cost, measured apart from the window.
 *
 *   bench match           fontconfig: the primary font, and a fallback for a
 *                         code point it lacks, cold and warm
 *   bench shape FILE      HarfBuzz over each line of FILE as one run of the
 *                         primary font, against a lookup per code point
 *   bench fit             the ideograph width of each CJK face against the
 *                         primary font's cell
 *   bench han             which face and glyph 直 骨 返 刃 get per language
 *   bench raster          FreeType rasterizing 4,000 ideographs per load mode
 *   bench ink TEXT...     each text shaped in the face fontconfig gives it,
 *                         and how far its ink goes past the primary cell
 *
 * Times are CLOCK_MONOTONIC, the best of five passes. */
#define _GNU_SOURCE
#include <fontconfig/fontconfig.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include <hb-ft.h>
#include <hb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e9 + t.tv_nsec;
}

static FT_Library ft;

typedef struct {
    char *file;
    int index;
    FT_Face face;
    hb_font_t *hb;
} Face;

static int match(const char *spec, const char *lang, FcChar32 cp, Face *out) {
    FcPattern *p = FcNameParse((const FcChar8 *) spec);
    if (lang) FcPatternAddString(p, FC_LANG, (const FcChar8 *) lang);
    if (cp) {
        FcCharSet *cs = FcCharSetCreate();
        FcCharSetAddChar(cs, cp);
        FcPatternAddCharSet(p, FC_CHARSET, cs);
        FcCharSetDestroy(cs);
    }
    FcConfigSubstitute(NULL, p, FcMatchPattern);
    FcDefaultSubstitute(p);
    FcResult r;
    FcPattern *m = FcFontMatch(NULL, p, &r);
    FcPatternDestroy(p);
    if (!m) return -1;
    FcChar8 *file;
    int index = 0;
    FcPatternGetString(m, FC_FILE, 0, &file);
    FcPatternGetInteger(m, FC_INDEX, 0, &index);
    if (out) {
        out->file = strdup((const char *) file);
        out->index = index;
        out->face = NULL;
        out->hb = NULL;
    }
    FcPatternDestroy(m);
    return 0;
}

static void load(Face *f, int points) {
    if (FT_New_Face(ft, f->file, f->index, &f->face) != 0) {
        fprintf(stderr, "cannot load %s\n", f->file);
        exit(1);
    }
    FT_Set_Char_Size(f->face, 0, points * 64, 96, 96);
    f->hb = hb_ft_font_create_referenced(f->face);
}

static const char *base(const char *path) {
    const char *s = strrchr(path, '/');
    return s ? s + 1 : path;
}

static void cmd_match(void) {
    static const struct { const char *name; FcChar32 cp; } points[] = {
        {"a", 'a'}, {"水 U+6C34", 0x6C34}, {"ก U+0E01", 0x0E01}, {"가 U+AC00", 0xAC00},
        {"😀 U+1F600", 0x1F600}, {"─ U+2500", 0x2500}, {"⠿ U+283F", 0x283F}, {"U+10FFFD", 0x10FFFD},
    };
    double t0 = now();
    FcInit();
    double t1 = now();
    printf("FcInit: %.2f ms\n", (t1 - t0) / 1e6);
    for (size_t i = 0; i < sizeof points / sizeof *points; i++) {
        Face f = {0};
        double a = now();
        int r = match("monospace", NULL, points[i].cp, &f);
        double cold = now() - a;
        double warm = 1e30;
        for (int k = 0; k < 5; k++) {
            Face g = {0};
            double b = now();
            match("monospace", NULL, points[i].cp, &g);
            double d = now() - b;
            if (d < warm) warm = d;
            free(g.file);
        }
        /* Does the face match gave have the code point at all? */
        int has = 0;
        if (r == 0) {
            FT_Face face;
            if (FT_New_Face(ft, f.file, f.index, &face) == 0) {
                has = FT_Get_Char_Index(face, points[i].cp) != 0;
                FT_Done_Face(face);
            }
        }
        printf("%-12s %-32s index %d  has it: %s  first %.3f ms, then %.3f ms\n", points[i].name, r == 0 ? base(f.file) : "-",
               f.index, has ? "yes" : "NO", cold / 1e6, warm / 1e6);
        free(f.file);
    }
}

static int utf8(const char *s, uint32_t *out, int max) {
    int n = 0;
    const unsigned char *p = (const unsigned char *) s;
    while (*p && n < max) {
        uint32_t c;
        if (*p < 0x80) c = *p++;
        else if ((*p & 0xE0) == 0xC0) { c = (uint32_t) (*p & 0x1F) << 6 | (p[1] & 0x3F); p += 2; }
        else if ((*p & 0xF0) == 0xE0) { c = (uint32_t) (*p & 0x0F) << 12 | (uint32_t) (p[1] & 0x3F) << 6 | (p[2] & 0x3F); p += 3; }
        else { c = (uint32_t) (*p & 0x07) << 18 | (uint32_t) (p[1] & 0x3F) << 12 | (uint32_t) (p[2] & 0x3F) << 6 | (p[3] & 0x3F); p += 4; }
        out[n++] = c;
    }
    return n;
}

static void cmd_shape(const char *path) {
    FcInit();
    Face f;
    match("monospace", NULL, 0, &f);
    load(&f, 11);
    FILE *in = fopen(path, "r");
    if (!in) { perror(path); exit(1); }
    char line[65536];
    uint32_t cps[65536];
    /* Lines cut to 160 cells, as a row of the probe's window. */
    int nlines = 0, ncells = 0;
    static uint32_t *rows[200000];
    static int lens[200000];
    while (fgets(line, sizeof line, in) && nlines < 200000) {
        int n = utf8(line, cps, 65535);
        while (n > 0 && (cps[n - 1] == '\n' || cps[n - 1] == '\r')) n--;
        if (n > 160) n = 160;
        rows[nlines] = malloc((size_t) (n ? n : 1) * 4);
        memcpy(rows[nlines], cps, (size_t) n * 4);
        lens[nlines++] = n;
        ncells += n;
    }
    fclose(in);
    hb_buffer_t *buf = hb_buffer_create();
    double best_hb = 1e30, best_cmap = 1e30, best_cached = 1e30;
    long glyphs = 0, sum = 0;
    for (int pass = 0; pass < 5; pass++) {
        double a = now();
        glyphs = 0;
        for (int i = 0; i < nlines; i++) {
            hb_buffer_clear_contents(buf);
            hb_buffer_add_codepoints(buf, rows[i], lens[i], 0, lens[i]);
            hb_buffer_set_direction(buf, HB_DIRECTION_LTR);
            hb_buffer_guess_segment_properties(buf);
            hb_shape(f.hb, buf, NULL, 0);
            glyphs += hb_buffer_get_length(buf);
        }
        double d = now() - a;
        if (d < best_hb) best_hb = d;
        a = now();
        for (int i = 0; i < nlines; i++)
            for (int k = 0; k < lens[i]; k++) sum += FT_Get_Char_Index(f.face, rows[i][k]);
        d = now() - a;
        if (d < best_cmap) best_cmap = d;
        /* A run shaped once and found again by its hash (G§5.5): the cost
         * of the hash, as a lower bound on a cache's hit. */
        a = now();
        for (int i = 0; i < nlines; i++) {
            uint64_t h = 1469598103934665603u;
            for (int k = 0; k < lens[i]; k++) h = (h ^ rows[i][k]) * 1099511628211u;
            sum += (long) (h & 1);
        }
        d = now() - a;
        if (d < best_cached) best_cached = d;
    }
    printf("%s: %d lines, %d cells, %ld glyphs from HarfBuzz (face %s)\n", base(path), nlines, ncells, glyphs, base(f.file));
    printf("  HarfBuzz:            %8.2f ms, %6.1f ns a cell, %6.2f us a line\n", best_hb / 1e6, best_hb / ncells, best_hb / nlines / 1e3);
    printf("  FT_Get_Char_Index:   %8.2f ms, %6.1f ns a cell\n", best_cmap / 1e6, best_cmap / ncells);
    printf("  FNV hash of the run: %8.2f ms, %6.1f ns a cell (%ld)\n", best_cached / 1e6, best_cached / ncells, sum & 1);
}

static void cmd_fit(void) {
    FcInit();
    Face primary;
    match("monospace", NULL, 0, &primary);
    load(&primary, 11);
    FT_Load_Char(primary.face, 'M', FT_LOAD_DEFAULT);
    double cell = primary.face->glyph->advance.x / 64.0;
    double asc = primary.face->size->metrics.ascender / 64.0, desc = -primary.face->size->metrics.descender / 64.0;
    printf("primary %s: cell %.2f px wide (two cells %.2f), ascent %.2f, descent %.2f, height %.2f\n", base(primary.file), cell,
           2 * cell, asc, desc, primary.face->size->metrics.height / 64.0);
    static const char *specs[] = {"Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Serif CJK JP", "Droid Sans Fallback",
                                  "Noto Sans Thai", "Noto Color Emoji"};
    for (size_t i = 0; i < sizeof specs / sizeof *specs; i++) {
        Face f;
        if (match(specs[i], NULL, 0, &f) != 0) continue;
        load(&f, 11);
        FT_UInt gi = FT_Get_Char_Index(f.face, 0x6C34);
        double adv = 0;
        if (gi && FT_Load_Glyph(f.face, gi, FT_LOAD_DEFAULT) == 0) adv = f.face->glyph->advance.x / 64.0;
        printf("%-24s %s#%d: 水 %s, advance %.2f px = %.2f cells; scale to two cells %.3f; ascent %.2f descent %.2f\n", specs[i],
               base(f.file), f.index, gi ? "present" : "absent", adv, adv / cell, adv > 0 ? 2 * cell / adv : 0,
               f.face->size ? f.face->size->metrics.ascender / 64.0 : 0, f.face->size ? -f.face->size->metrics.descender / 64.0 : 0);
    }
}

static void cmd_han(void) {
    FcInit();
    static const char *langs[] = {NULL, "ja", "ko", "zh-cn", "zh-tw", "zh-hk"};
    static const char *hblangs[] = {NULL, "ja", "ko", "zh-Hans", "zh-Hant", "zh-HK"};
    static const uint32_t han[] = {0x76F4, 0x9AA8, 0x8FD4, 0x5203};
    for (size_t l = 0; l < sizeof langs / sizeof *langs; l++) {
        Face f;
        match("monospace", langs[l], 0x76F4, &f);
        load(&f, 11);
        printf("lang %-6s -> %s#%d:", langs[l] ? langs[l] : "(none)", base(f.file), f.index);
        for (int k = 0; k < 4; k++) {
            hb_buffer_t *b = hb_buffer_create();
            hb_buffer_add_codepoints(b, &han[k], 1, 0, 1);
            hb_buffer_set_direction(b, HB_DIRECTION_LTR);
            hb_buffer_set_script(b, HB_SCRIPT_HAN);
            /* Shaped with no language, then with the profile's: `locl`. */
            hb_shape(f.hb, b, NULL, 0);
            unsigned g0 = hb_buffer_get_glyph_infos(b, NULL)[0].codepoint;
            hb_buffer_clear_contents(b);
            hb_buffer_add_codepoints(b, &han[k], 1, 0, 1);
            hb_buffer_set_direction(b, HB_DIRECTION_LTR);
            hb_buffer_set_script(b, HB_SCRIPT_HAN);
            if (hblangs[l]) hb_buffer_set_language(b, hb_language_from_string(hblangs[l], -1));
            hb_shape(f.hb, b, NULL, 0);
            unsigned g1 = hb_buffer_get_glyph_infos(b, NULL)[0].codepoint;
            printf("  U+%04X %u/%u", han[k], g0, g1);
            hb_buffer_destroy(b);
        }
        printf("\n");
    }
    /* The other way: one collection face (JP), the language only from the
     * shaper. Does `locl` alone give the regional forms? */
    Face jp;
    match("Noto Sans Mono CJK JP", NULL, 0, &jp);
    load(&jp, 11);
    printf("one face %s#%d, locl only:\n", base(jp.file), jp.index);
    for (size_t l = 0; l < sizeof hblangs / sizeof *hblangs; l++) {
        printf("  %-8s", hblangs[l] ? hblangs[l] : "(none)");
        for (int k = 0; k < 4; k++) {
            hb_buffer_t *b = hb_buffer_create();
            hb_buffer_add_codepoints(b, &han[k], 1, 0, 1);
            hb_buffer_set_direction(b, HB_DIRECTION_LTR);
            hb_buffer_set_script(b, HB_SCRIPT_HAN);
            if (hblangs[l]) hb_buffer_set_language(b, hb_language_from_string(hblangs[l], -1));
            hb_shape(jp.hb, b, NULL, 0);
            printf("  U+%04X %u", han[k], hb_buffer_get_glyph_infos(b, NULL)[0].codepoint);
            hb_buffer_destroy(b);
        }
        printf("\n");
    }
}

static void cmd_ink(int argc, char **argv) {
    FcInit();
    Face primary;
    match("monospace", NULL, 0, &primary);
    load(&primary, 11);
    FT_Load_Char(primary.face, 'M', FT_LOAD_DEFAULT);
    double cell = primary.face->glyph->advance.x / 64.0;
    double asc = primary.face->size->metrics.ascender / 64.0, desc = -primary.face->size->metrics.descender / 64.0;
    printf("primary cell %.0f x %.0f px, ascent %.2f descent %.2f\n", cell, asc + desc, asc, desc);
    for (int i = 0; i < argc; i++) {
        uint32_t cps[256];
        int n = utf8(argv[i], cps, 256);
        /* The face for the run: the first one fontconfig gives that has
         * every code point of it (a cluster stays in one face). */
        Face f;
        FcChar32 first = 0;
        for (int k = 0; k < n; k++)
            if (!FT_Get_Char_Index(primary.face, cps[k])) { first = cps[k]; break; }
        if (first == 0) f = primary;
        else { match("monospace", NULL, first, &f); load(&f, 11); }
        int missing = 0;
        for (int k = 0; k < n; k++) missing += FT_Get_Char_Index(f.face, cps[k]) == 0;
        hb_buffer_t *b = hb_buffer_create();
        hb_buffer_add_codepoints(b, cps, n, 0, n);
        hb_buffer_set_direction(b, HB_DIRECTION_LTR);
        hb_buffer_guess_segment_properties(b);
        hb_shape(f.hb, b, NULL, 0);
        unsigned gn;
        hb_glyph_info_t *gi = hb_buffer_get_glyph_infos(b, &gn);
        hb_glyph_position_t *gp = hb_buffer_get_glyph_positions(b, &gn);
        double x = 0, top = 0, bottom = 0, left = 0, right = 0;
        for (unsigned g = 0; g < gn; g++) {
            hb_glyph_extents_t e;
            if (hb_font_get_glyph_extents(f.hb, gi[g].codepoint, &e)) {
                double gx = x + gp[g].x_offset / 64.0, gy = gp[g].y_offset / 64.0;
                double l = gx + e.x_bearing / 64.0, r = l + e.width / 64.0;
                double t = gy + e.y_bearing / 64.0, btm = t + e.height / 64.0;
                if (l < left) left = l;
                if (r > right) right = r;
                if (t > top) top = t;
                if (btm < bottom) bottom = btm;
            }
            x += gp[g].x_advance / 64.0;
        }
        printf("%-10s %d cps, face %s#%d (missing %d), %u glyphs, advance %.2f px; ink x %.2f..%.2f, y %.2f..%.2f: above ascent %.2f, below descent %.2f\n",
               argv[i], n, base(f.file), f.index, missing, gn, x, left, right, bottom, top, top - asc > 0 ? top - asc : 0,
               -bottom - desc > 0 ? -bottom - desc : 0);
        hb_buffer_destroy(b);
    }
}

/* FreeType's rasterizing of 4,000 ideographs at the size the probe draws
 * them, under each load mode. */
static void cmd_raster(void) {
    FcInit();
    Face f;
    match("monospace", "ja", 0x6C34, &f);
    load(&f, 11);
    FT_Set_Char_Size(f.face, 0, (FT_F26Dot6) (11 * 64 * 1.139 + 0.5), 96, 96);
    static const struct { const char *name; FT_Int32 flags; } modes[] = {
        {"default (hinted)", FT_LOAD_RENDER}, {"light", FT_LOAD_RENDER | FT_LOAD_TARGET_LIGHT},
        {"no hinting", FT_LOAD_RENDER | FT_LOAD_NO_HINTING}, {"no hinting, no bitmap", FT_LOAD_NO_HINTING}};
    printf("%s#%d\n", base(f.file), f.index);
    for (size_t m = 0; m < sizeof modes / sizeof *modes; m++) {
        double best = 1e30;
        long bytes = 0;
        for (int pass = 0; pass < 3; pass++) {
            double a = now();
            bytes = 0;
            for (uint32_t cp = 0x4E00; cp < 0x4E00 + 4000; cp++) {
                FT_Load_Glyph(f.face, FT_Get_Char_Index(f.face, cp), modes[m].flags);
                bytes += (long) ((f.face->glyph->bitmap.width + 3) & ~3u) * f.face->glyph->bitmap.rows;
            }
            double d = now() - a;
            if (d < best) best = d;
        }
        printf("  %-24s %6.2f us a glyph, %ld bytes of A8 a glyph\n", modes[m].name, best / 4000 / 1e3, bytes / 4000);
    }
}

int main(int argc, char **argv) {
    FT_Init_FreeType(&ft);
    if (argc >= 2 && strcmp(argv[1], "match") == 0) cmd_match();
    else if (argc >= 3 && strcmp(argv[1], "shape") == 0) cmd_shape(argv[2]);
    else if (argc >= 2 && strcmp(argv[1], "fit") == 0) cmd_fit();
    else if (argc >= 2 && strcmp(argv[1], "han") == 0) cmd_han();
    else if (argc >= 2 && strcmp(argv[1], "raster") == 0) cmd_raster();
    else if (argc >= 3 && strcmp(argv[1], "ink") == 0) cmd_ink(argc - 2, argv + 2);
    else {
        fprintf(stderr, "usage: bench match | shape FILE | fit | han | ink TEXT...\n");
        return 2;
    }
    return 0;
}

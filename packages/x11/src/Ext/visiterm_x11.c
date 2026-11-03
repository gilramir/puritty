/* visiterm's window on X11 (docs/renderer.md, V34–V37): the C that only C
 * can do. Geng decides what is drawn and sends it as a display list
 * (`Vt.View`'s comment is its definition); this executes it, and turns the
 * X server's events into records Geng decodes.
 *
 * Drawing, S§6.2's way:
 *   - everything is drawn into a retained pixmap the size of the screen's
 *     cells, then the rows a frame touched are copied to the window, so an
 *     expose needs no redraw;
 *   - a scroll record is one CopyArea within the pixmap, up or down;
 *   - a run is a RenderFillRectangles for each stretch of one background,
 *     a RenderCompositeGlyphs32 for each stretch of one foreground, and its
 *     lines (underlines, strikethrough, overline, the cursor's shape) as
 *     fills;
 *   - a run's clusters are shaped by HarfBuzz in the face that has them
 *     (V24, V34): the primary font in the weight and slant the style asks
 *     for, else the first loaded face with the whole cluster, else the one
 *     fontconfig finds (V26); a glyph is rasterised by FreeType and uploaded
 *     with RenderAddGlyphs the first time it is drawn, a colour one as an
 *     ARGB32 picture (§13.10);
 *   - past `glyph_cap` bytes uploaded, the glyph set is freed and a new one
 *     begun (V37). The pixmap keeps what was drawn with the old one, so
 *     nothing is redrawn: glyphs are uploaded again as frames need them.
 *
 * Styles come resolved in each frame's style records (V35) and are kept
 * only for that frame's runs. Bold and italic come from the primary font's
 * own faces; a fallback face draws them as its regular (synthesising them
 * is docs/renderer.md §R6 step 5's), and blinking text is drawn steady.
 *
 * One window a process (geng-plan.md Q6), so the state is this file's.
 *
 * Events (V36), the records `visiterm_x11_take` answers, each a kind byte:
 *   1 a key: its keysym in 4 bytes, its modifiers in 1 (shift 1, ctrl 2,
 *     alt 4, super 8), a byte of length and its text in UTF-8
 *     (xkbcommon's, V30);
 *   2 the window's size in cells changed: columns and rows, 2 bytes each;
 *   3 the focus: 1 in, 0 out;
 *   4 the window manager asks the window to close (WM_DELETE_WINDOW).
 * An expose is answered here, from the pixmap.
 *
 * X11_STATS=1 prints counts when the program ends; X11_SHOT=FILE writes
 * the window then, as `visiterm_x11_shot` does. */
#define _GNU_SOURCE
#include <fontconfig/fontconfig.h>
#include <poll.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_OUTLINE_H
#include <hb-ft.h>
#include <hb.h>
#include <stdio.h>
#include <time.h>
#include <stdlib.h>
#include <string.h>
#include <xcb/render.h>
#include <xcb/xcb.h>
#include <xcb/xcb_renderutil.h>
#include <xcb/xkb.h>
#include <xkbcommon/xkbcommon-x11.h>

#include "geng.h"

static xcb_connection_t *conn;
static xcb_screen_t *screen;
static xcb_window_t window;
static xcb_pixmap_t pixmap;
static xcb_gcontext_t gc;
static xcb_render_picture_t target;
static xcb_render_pictformat_t a8, argb32, visual_format;
static xcb_render_glyphset_t glyphs;
static FT_Library library;
/* The cell, and where a line sits in it: the underline's top below the
 * baseline and its thickness, the strikethrough's top above it. */
static int cw, ch, ascent, ul_below, line_thick, strike_above;
/* The screen in cells, as the display list last said; the window in
 * cells, as its size was last reported. */
static int cols, rows, win_cols, win_rows, focused = -1;
static uint32_t margin_bg = 0xFFFFFFFF;
static long glyph_bytes, glyph_cap, resets;

static uint32_t style_fg[65536], style_bg[65536], style_ulc[65536];
static uint8_t style_flags[65536], style_ul[65536];

static xcb_atom_t wm_protocols, wm_delete, net_wm_name, utf8_string;

static struct {
    long clusters, fallback_clusters, fc_queries, fc_failed, segments, glyphs, uploaded, colour, squeezed, frames;
    double shape_ns, raster_ns, draw_ns, fc_ns;
} st;

static double ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e9 + t.tv_nsec;
}

static xcb_render_color_t colour(uint32_t rgb) {
    return (xcb_render_color_t) {.red = (uint16_t) (((rgb >> 16) & 0xff) * 257), .green = (uint16_t) (((rgb >> 8) & 0xff) * 257),
                                 .blue = (uint16_t) ((rgb & 0xff) * 257), .alpha = 0xffff};
}

/* Solid pictures for glyphs' colours, a cache of 256 slots: a colour that
 * lands on a slot another holds replaces it. */
static xcb_render_picture_t solid[256];
static uint32_t solid_rgb[256];

static xcb_render_picture_t solid_of(uint32_t rgb) {
    int i = (int) ((rgb ^ (rgb >> 8) ^ (rgb >> 16)) & 0xff);
    if (solid[i] != 0 && solid_rgb[i] != rgb) {
        xcb_render_free_picture(conn, solid[i]);
        solid[i] = 0;
    }
    if (solid[i] == 0) {
        solid[i] = xcb_generate_id(conn);
        solid_rgb[i] = rgb;
        xcb_render_create_solid_fill(conn, solid[i], colour(rgb));
    }
    return solid[i];
}

static void fill(uint32_t rgb, int x, int y, int w, int h) {
    if (w <= 0 || h <= 0) return;
    xcb_rectangle_t r = {(int16_t) x, (int16_t) y, (uint16_t) w, (uint16_t) h};
    xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(rgb), 1, &r);
}

/* FONTS */

#define FACES 32
/* A glyph's key in its face: its index, and the bits of the form it was
 * uploaded in (shifted 1, squeezed 2, synthetic bold 4, synthetic italic
 * 8, from bit 16); a glyph set id is the face above it. */
#define KEYS (1 << 20)
typedef struct ColourGlyph {
    uint32_t g;
    int box;
    xcb_render_picture_t picture;
    int w, h;
    struct ColourGlyph *next;
} ColourGlyph;

typedef struct {
    FT_Face ft;
    hb_font_t *hb;
    char *file;
    int index;
    double scale;
    int colour;        /* a face of colour bitmaps (CBDT), drawn as pictures */
    int own;           /* what the face is of itself: bold 1, italic 2 */
    uint8_t *uploaded; /* a bit a glyph index and form */
    int16_t *advance;  /* the x_off each glyph was uploaded with */
    ColourGlyph *pictures;
} Face;

static Face faces[FACES];
static int nfaces, points0;
/* The primary font's faces: regular, bold, italic, bold italic. A font with
 * no face of its own for one gives its regular. */
static int primary[4];
static hb_language_t language;
static char *lang_name;
static hb_buffer_t *hbuf;

static char *font_file(const char *spec, int *index) {
    FcPattern *p = FcNameParse((const FcChar8 *) spec);
    FcConfigSubstitute(NULL, p, FcMatchPattern);
    FcDefaultSubstitute(p);
    FcResult r;
    FcPattern *m = FcFontMatch(NULL, p, &r);
    FcChar8 *file = NULL;
    char *out = NULL;
    *index = 0;
    if (m != NULL && FcPatternGetString(m, FC_FILE, 0, &file) == FcResultMatch) {
        out = strdup((const char *) file);
        FcPatternGetInteger(m, FC_INDEX, 0, index);
    }
    if (m != NULL) FcPatternDestroy(m);
    FcPatternDestroy(p);
    return out;
}

/* Code points that select a form rather than need a glyph of their own. */
static int ignorable(uint32_t cp) {
    return cp == 0x200D || cp == 0x200C || (cp >= 0xFE00 && cp <= 0xFE0F) || (cp >= 0xE0100 && cp <= 0xE01EF);
}

/* A cluster that asks for emoji presentation: one with U+FE0F, or one
 * whose first code point is in the blocks where emoji default to it, an
 * approximation of UTS #51's Emoji_Presentation (§13.10). */
static int emoji(const uint32_t *cps, int n) {
    for (int i = 0; i < n; i++)
        if (cps[i] == 0xFE0E) return 0;
    for (int i = 0; i < n; i++)
        if (cps[i] == 0xFE0F) return 1;
    return n > 0 && ((cps[0] >= 0x1F300 && cps[0] <= 0x1FAFF) || (cps[0] >= 0x1F1E6 && cps[0] <= 0x1F1FF));
}

static int covers(int f, const uint32_t *cps, int n) {
    for (int i = 0; i < n; i++) {
        hb_codepoint_t g;
        if (!ignorable(cps[i]) && !hb_font_get_nominal_glyph(faces[f].hb, cps[i], &g)) return 0;
    }
    return 1;
}

/* A face, loaded once. One of the primary font's keeps its size; a
 * fallback face with 水 is sized so 水 fills two cells and its ink stays
 * within the primary cell (§13.1). */
static int load_face(const char *file, int index, int is_primary) {
    for (int f = 0; f < nfaces; f++)
        if (faces[f].index == index && strcmp(faces[f].file, file) == 0) return f;
    if (nfaces == FACES) return -1;
    Face *F = &faces[nfaces];
    if (FT_New_Face(library, file, index, &F->ft) != 0) return -1;
    F->file = strdup(file);
    F->index = index;
    F->scale = 1.0;
    F->colour = FT_HAS_COLOR(F->ft) && !FT_IS_SCALABLE(F->ft) && F->ft->num_fixed_sizes > 0;
    F->pictures = NULL;
    if (F->colour) FT_Select_Size(F->ft, 0);
    else FT_Set_Char_Size(F->ft, 0, points0 * 64, 96, 96);
    if (!is_primary && !F->colour) {
        FT_UInt gi = FT_Get_Char_Index(F->ft, 0x6C34);
        if (gi && FT_Load_Glyph(F->ft, gi, FT_LOAD_NO_HINTING) == 0) {
            double adv = F->ft->glyph->advance.x / 64.0;
            double top = F->ft->glyph->metrics.horiBearingY / 64.0;
            double bottom = F->ft->glyph->metrics.height / 64.0 - top;
            double sc = 2.0 * cw / adv;
            if (top > 0 && ascent / top < sc) sc = ascent / top;
            if (bottom > 0 && (ch - ascent) / bottom < sc) sc = (ch - ascent) / bottom;
            F->scale = sc;
            FT_Set_Char_Size(F->ft, 0, (FT_F26Dot6) (points0 * 64 * sc + 0.5), 96, 96);
        }
    }
    F->hb = hb_ft_font_create_referenced(F->ft);
    F->uploaded = calloc(KEYS / 8, 1);
    F->advance = calloc(KEYS, sizeof *F->advance);
    if (getenv("X11_STATS")) fprintf(stderr, "face %d: %s#%d scale %.3f\n", nfaces, F->file, index, F->scale);
    return nfaces++;
}

/* A cache from a cluster's first code point to the face fontconfig gave
 * it, so that fontconfig is asked once a code point; -1 where it found
 * none. */
#define FCACHE 4096
static struct { uint32_t cp; int face; } fcache[FCACHE];

static int fallback(const uint32_t *cps, int n) {
    int colour = emoji(cps, n);
    /* A cluster asking for emoji presentation takes only a colour face, and
     * one asking for text only a face that is not. */
    for (int f = 0; f < nfaces; f++)
        if (faces[f].colour == colour && covers(f, cps, n)) return f;
    uint32_t key = 0;
    for (int i = 0; i < n && !key; i++)
        if (!ignorable(cps[i])) key = cps[i];
    if (colour) key |= 0x40000000;
    unsigned h = (key * 2654435761u) % FCACHE;
    for (unsigned k = 0; k < FCACHE; k++) {
        unsigned j = (h + k) % FCACHE;
        if (fcache[j].cp == key + 1) return fcache[j].face;
        if (fcache[j].cp == 0) { h = j; break; }
    }
    double t0 = ns();
    st.fc_queries++;
    FcPattern *p = FcNameParse((const FcChar8 *) "monospace");
    if (lang_name) FcPatternAddString(p, FC_LANG, (const FcChar8 *) lang_name);
    if (colour) FcPatternAddBool(p, FC_COLOR, FcTrue);
    FcCharSet *cs = FcCharSetCreate();
    for (int i = 0; i < n; i++)
        if (!ignorable(cps[i])) FcCharSetAddChar(cs, cps[i]);
    FcPatternAddCharSet(p, FC_CHARSET, cs);
    FcCharSetDestroy(cs);
    FcConfigSubstitute(NULL, p, FcMatchPattern);
    FcDefaultSubstitute(p);
    FcResult r;
    FcPattern *m = FcFontMatch(NULL, p, &r);
    FcPatternDestroy(p);
    int face = -1;
    FcChar8 *file;
    int index = 0;
    if (m && FcPatternGetString(m, FC_FILE, 0, &file) == FcResultMatch) {
        FcPatternGetInteger(m, FC_INDEX, 0, &index);
        int f = load_face((const char *) file, index, 0);
        if (f >= 0 && covers(f, cps, n)) face = f;
        /* No colour face has it: the text face that does. */
        if (face < 0 && colour)
            for (int g = 0; g < nfaces; g++)
                if (covers(g, cps, n)) { face = g; break; }
    }
    if (m) FcPatternDestroy(m);
    if (face < 0) st.fc_failed++;
    fcache[h].cp = key + 1;
    fcache[h].face = face;
    st.fc_ns += ns() - t0;
    return face;
}

/* GLYPHS */

/* The glyph set freed and a new one begun (V37), every face's record of
 * what it uploaded forgotten, and its colour pictures freed. */
static void reset_glyphs(void) {
    xcb_render_free_glyph_set(conn, glyphs);
    glyphs = xcb_generate_id(conn);
    xcb_render_create_glyph_set(conn, glyphs, a8);
    for (int f = 0; f < nfaces; f++) {
        memset(faces[f].uploaded, 0, KEYS / 8);
        for (ColourGlyph *c = faces[f].pictures, *next; c; c = next) {
            next = c->next;
            if (c->picture) xcb_render_free_picture(conn, c->picture);
            free(c);
        }
        faces[f].pictures = NULL;
    }
    glyph_bytes = 0;
    resets++;
}

/* A glyph's advance on the server is fixed when it is uploaded: the pen
 * moves by it inside an element, whatever the run asks. The first use
 * chooses it; a glyph placed elsewhere starts a new element. A glyph alone
 * in a cluster narrower than its cells is uploaded a second time with its
 * centring in its bearing (`shift`), so a line of them stays in one
 * element; one wider than the one cell the core gives it a third way,
 * squeezed to the cell (`squeeze`, 16.16; PuTTY's narrow trick, C§4.4). */
static uint32_t upload(int f, uint32_t g, int advance, int shift, FT_Fixed squeeze, int synth) {
    uint32_t k = (g & 0xFFFF) | (shift ? 0x10000 : 0) | (squeeze ? 0x20000 : 0) | ((uint32_t) synth << 18);
    uint32_t id = ((uint32_t) f << 20) | k;
    Face *F = &faces[f];
    if (F->uploaded[k >> 3] & (1 << (k & 7))) return id;
    F->uploaded[k >> 3] |= (uint8_t) (1 << (k & 7));
    F->advance[k] = (int16_t) advance;
    st.uploaded++;
    double t0 = ns();
    /* A synthetic italic is the glyph slanted by 0.2, as fontconfig's
     * oblique matrix; a synthetic bold its outline widened by a 24th of
     * the em, as FreeType's FT_GlyphSlot_Embolden, but not made taller:
     * a CJK glyph fills its cell's height, and a taller one draws into
     * the row above (C§9 rule 6, §R13). */
    int transformed = squeeze || (synth & 2);
    if (transformed) {
        FT_Matrix m = {squeeze ? squeeze : 0x10000, (synth & 2) ? 0x3333 : 0, 0, 0x10000};
        FT_Set_Transform(F->ft, &m, NULL);
    }
    FT_Load_Glyph(F->ft, g, (transformed ? FT_LOAD_NO_HINTING : 0) | ((synth & 1) ? 0 : FT_LOAD_RENDER));
    if (synth & 1) {
        FT_GlyphSlot slot = F->ft->glyph;
        if (slot->format == FT_GLYPH_FORMAT_OUTLINE)
            FT_Outline_EmboldenXY(&slot->outline, FT_MulFix(F->ft->units_per_EM, F->ft->size->metrics.y_scale) / 24, 0);
        FT_Render_Glyph(slot, FT_RENDER_MODE_NORMAL);
    }
    if (transformed) FT_Set_Transform(F->ft, NULL, NULL);
    FT_Bitmap *b = &F->ft->glyph->bitmap;
    int stride = ((int) b->width + 3) & ~3;
    size_t size = (size_t) stride * b->rows;
    uint8_t *data = calloc(size > 0 ? size : 4, 1);
    for (unsigned y = 0; y < b->rows; y++) memcpy(data + y * stride, b->buffer + y * b->pitch, b->width);
    xcb_render_glyphinfo_t info = {.width = (uint16_t) b->width, .height = (uint16_t) b->rows,
                                   .x = (int16_t) (-F->ft->glyph->bitmap_left - shift), .y = (int16_t) F->ft->glyph->bitmap_top,
                                   .x_off = (int16_t) advance, .y_off = 0};
    xcb_render_add_glyphs(conn, glyphs, 1, &id, &info, (uint32_t) size, data);
    glyph_bytes += (long) size + 28;
    free(data);
    st.raster_ns += ns() - t0;
    return id;
}

/* The glyphs a run draws, in order, before they go out as requests. */
typedef struct { uint32_t id; int x, y, style, advance; } Placed;
static Placed placed[8192];
static int nplaced;

/* What a face draws of a style that it is not of itself: bold 1, italic 2
 * (C§9 rule 6). */
static int synth_for(int f, int style) {
    int flags = style_flags[style];
    return (((flags & 1) ? 1 : 0) | ((flags & 4) ? 2 : 0)) & ~faces[f].own;
}

static void place(int f, uint32_t g, int x, int y, int style, int advance, int shift, FT_Fixed squeeze) {
    if (nplaced == 8192) return;
    uint32_t id = upload(f, g, advance, shift, squeeze, synth_for(f, style));
    placed[nplaced++] = (Placed) {id, x, y, style, faces[f].advance[id & (KEYS - 1)]};
}

/* The colour glyph `g` of face `f` for a box of `box` pixels by a cell's
 * height: the strike's BGRA bitmap (premultiplied, as FreeType gives it)
 * reduced by averaging into the box, keeping its proportions. */
static ColourGlyph *colour_glyph(int f, uint32_t g, int box) {
    Face *F = &faces[f];
    for (ColourGlyph *c = F->pictures; c; c = c->next)
        if (c->g == g && c->box == box) return c;
    double t0 = ns();
    ColourGlyph *c = calloc(1, sizeof *c);
    c->g = g;
    c->box = box;
    c->next = F->pictures;
    F->pictures = c;
    if (FT_Load_Glyph(F->ft, g, FT_LOAD_COLOR | FT_LOAD_RENDER) != 0 || F->ft->glyph->bitmap.pixel_mode != FT_PIXEL_MODE_BGRA)
        return c;
    FT_Bitmap *b = &F->ft->glyph->bitmap;
    double sc = (double) box / b->width;
    if ((double) ch / b->rows < sc) sc = (double) ch / b->rows;
    int w = (int) (b->width * sc + 0.5), h = (int) (b->rows * sc + 0.5);
    if (w < 1 || h < 1) return c;
    uint32_t *out = calloc((size_t) w * h, 4);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            int x0 = (int) (x / sc), x1 = (int) ((x + 1) / sc), y0 = (int) (y / sc), y1 = (int) ((y + 1) / sc);
            if (x1 > (int) b->width) x1 = (int) b->width;
            if (y1 > (int) b->rows) y1 = (int) b->rows;
            unsigned sum[4] = {0}, cnt = 0;
            for (int yy = y0; yy < y1; yy++)
                for (int xx = x0; xx < x1; xx++, cnt++)
                    for (int k = 0; k < 4; k++) sum[k] += b->buffer[yy * b->pitch + xx * 4 + k];
            if (cnt == 0) cnt = 1;
            out[y * w + x] = (sum[0] / cnt) | (sum[1] / cnt) << 8 | (sum[2] / cnt) << 16 | (sum[3] / cnt) << 24;
        }
    xcb_pixmap_t pm = xcb_generate_id(conn);
    xcb_create_pixmap(conn, 32, pm, window, (uint16_t) w, (uint16_t) h);
    xcb_gcontext_t g32 = xcb_generate_id(conn);
    xcb_create_gc(conn, g32, pm, 0, NULL);
    xcb_put_image(conn, XCB_IMAGE_FORMAT_Z_PIXMAP, pm, g32, (uint16_t) w, (uint16_t) h, 0, 0, 0, 32, (uint32_t) w * h * 4,
                  (const uint8_t *) out);
    xcb_free_gc(conn, g32);
    c->picture = xcb_generate_id(conn);
    xcb_render_create_picture(conn, c->picture, pm, argb32, 0, NULL);
    xcb_free_pixmap(conn, pm);
    c->w = w;
    c->h = h;
    free(out);
    st.uploaded++;
    glyph_bytes += (long) w * h * 4;
    st.raster_ns += ns() - t0;
    return c;
}

/* Each stretch of one foreground colour as one CompositeGlyphs32, a new
 * element where a glyph is not where the last one's advance left the pen. */
static void flush_placed(void) {
    static uint8_t buffer[65536];
    int i = 0;
    while (i < nplaced) {
        uint32_t fg = style_fg[placed[i].style];
        int len = 0, penx = 0, peny = 0, count_at = -1, count = 0;
        for (; i < nplaced && style_fg[placed[i].style] == fg && len < 60000; i++) {
            Placed *P = &placed[i];
            if (count_at < 0 || P->x != penx || P->y != peny || count == 254) {
                count_at = len;
                buffer[len] = 0;
                buffer[len + 1] = buffer[len + 2] = buffer[len + 3] = 0;
                int16_t dx = (int16_t) (P->x - penx), dy = (int16_t) (P->y - peny);
                memcpy(buffer + len + 4, &dx, 2);
                memcpy(buffer + len + 6, &dy, 2);
                len += 8;
                count = 0;
            }
            memcpy(buffer + len, &P->id, 4);
            len += 4;
            buffer[count_at] = (uint8_t) ++count;
            penx = P->x + P->advance;
            peny = P->y;
            st.glyphs++;
        }
        xcb_render_composite_glyphs_32(conn, XCB_RENDER_PICT_OP_OVER, solid_of(fg), target, 0, glyphs, 0, 0, (uint32_t) len,
                                       buffer);
    }
    nplaced = 0;
}

typedef struct { int cell, width, style, n; const uint32_t *cps; int face; } Cluster;

/* A segment of clusters in one face, shaped as one run, each code point's
 * cluster its cell, so glyphs go back to cells by the core's widths. */
static void shape_segment(const Cluster *cl, int n, int x0, int y) {
    int f = cl[0].face < 0 ? 0 : cl[0].face;
    double t0 = ns();
    hb_buffer_clear_contents(hbuf);
    for (int i = 0; i < n; i++)
        for (int k = 0; k < cl[i].n; k++) hb_buffer_add(hbuf, cl[i].cps[k], (unsigned) i);
    hb_buffer_set_direction(hbuf, HB_DIRECTION_LTR);
    hb_buffer_guess_segment_properties(hbuf);
    if (language) hb_buffer_set_language(hbuf, language);
    hb_buffer_set_cluster_level(hbuf, HB_BUFFER_CLUSTER_LEVEL_MONOTONE_GRAPHEMES);
    hb_shape(faces[f].hb, hbuf, NULL, 0);
    st.shape_ns += ns() - t0;
    st.segments++;
    unsigned gn;
    hb_glyph_info_t *gi = hb_buffer_get_glyph_infos(hbuf, &gn);
    hb_glyph_position_t *gp = hb_buffer_get_glyph_positions(hbuf, &gn);
    unsigned g = 0;
    while (g < gn) {
        unsigned c = gi[g].cluster, e = g;
        int adv = 0;
        while (e < gn && gi[e].cluster == c) adv += gp[e++].x_advance;
        const Cluster *C = &cl[c];
        /* The shaper may merge clusters the core gave cells of their own,
         * as it does a Devanagari conjunct and its vowel sign, or a flag's
         * two regional indicators (§R13): the glyphs then take the cells of
         * every cluster merged, up to the next one's. */
        unsigned next = e < gn ? gi[e].cluster : (unsigned) n;
        const Cluster *L = next > c + 1 ? &cl[next - 1] : C;
        int box = (L->cell + L->width - C->cell) * cw;
        if (box < C->width * cw) box = C->width * cw;
        if (faces[f].colour) {
            /* Placed by its cells, centred: the strike's advances are its
             * own size's, not the cell's. */
            for (unsigned k = g; k < e; k++) {
                ColourGlyph *P = colour_glyph(f, gi[k].codepoint, box);
                if (!P->picture) continue;
                xcb_render_composite(conn, XCB_RENDER_PICT_OP_OVER, P->picture, 0, target, 0, 0, 0, 0,
                                     (int16_t) ((x0 + C->cell) * cw + (box - P->w) / 2), (int16_t) (y * ch + (ch - P->h) / 2),
                                     (uint16_t) P->w, (uint16_t) P->h);
                st.colour++;
            }
            g = e;
            continue;
        }
        /* Centred in its cells if it is narrower than them (a wide glyph
         * from a fallback face); left where it is wider. */
        int pad = box > (adv >> 6) ? (box - (adv >> 6)) / 2 : 0;
        int pen = 0;
        for (unsigned k = g; k < e; k++) {
            int x = (x0 + C->cell) * cw + pad + ((pen + gp[k].x_offset) >> 6);
            int yy = y * ch + ascent - (gp[k].y_offset >> 6);
            int a = k + 1 < e ? 0 : box - pad - (pen >> 6);
            if (k + 1 < e) a = (gp[k].x_advance + gp[k + 1].x_offset - gp[k].x_offset) >> 6;
            if (e - g == 1 && pad > 0 && gp[k].x_offset == 0)
                place(f, gi[k].codepoint, x - pad, yy, C->style, box, pad, 0);
            else if (e - g == 1 && box == cw && (adv >> 6) > cw && gp[k].x_offset == 0) {
                place(f, gi[k].codepoint, x, yy, C->style, cw, 0, (FT_Fixed) ((double) cw * 64 / adv * 65536));
                st.squeezed++;
            } else
                place(f, gi[k].codepoint, x, yy, C->style, a, 0, 0);
            pen += gp[k].x_advance;
        }
        g = e;
    }
}

static int is_primary(int f) { return f == primary[0] || f == primary[1] || f == primary[2] || f == primary[3]; }

/* The primary face a style asks for: bold 1 and italic 4 of its flags. */
static int primary_for(int style) {
    int flags = style_flags[style];
    return primary[((flags & 1) ? 1 : 0) | ((flags & 4) ? 2 : 0)];
}

static void draw_glyphs(int y, int x, int n, const uint8_t *p) {
    static Cluster cl[1024];
    static uint32_t cps[1024 * 64];
    int ncl = 0, ncps = 0;
    for (int i = 0; i < n && i < 1024; i++) {
        int wide = p[0] >> 6, count = p[0] & 63, style = (p[1] << 8) | p[2];
        p += 3;
        uint32_t *mine = cps + ncps;
        for (int k = 0; k < count; k++, p += 3) mine[k] = ((uint32_t) p[0] << 16) | ((uint32_t) p[1] << 8) | p[2];
        if (wide == 2 || wide == 3) continue; /* a tail or a spacer: its head draws it */
        if (count == 0) continue;            /* blank: the fill draws it */
        if (style_flags[style] & 0x20) continue; /* invisible */
        ncps += count;
        cl[ncl++] = (Cluster) {i, wide == 1 ? 2 : 1, style, count, mine, 0};
    }
    st.clusters += ncl;
    for (int i = 0; i < ncl; i++) {
        int want = primary_for(cl[i].style);
        int colour = emoji(cl[i].cps, cl[i].n);
        if (faces[want].colour == colour && covers(want, cl[i].cps, cl[i].n)) cl[i].face = want;
        else if (faces[0].colour == colour && covers(0, cl[i].cps, cl[i].n)) cl[i].face = 0;
        else {
            st.fallback_clusters++;
            cl[i].face = fallback(cl[i].cps, cl[i].n);
        }
    }
    /* Spaces between two clusters of one fallback face join their run when
     * that face has a space, so a line of Thai is one run, not a word each
     * (V24). */
    for (int i = 0; i < ncl;) {
        if (cl[i].face != primary_for(cl[i].style) || cl[i].n != 1 || cl[i].cps[0] != ' ') { i++; continue; }
        int j = i;
        while (j < ncl && cl[j].face == primary_for(cl[j].style) && cl[j].n == 1 && cl[j].cps[0] == ' ') j++;
        if (i > 0 && j < ncl && cl[i - 1].face >= 0 && !is_primary(cl[i - 1].face) && cl[i - 1].face == cl[j].face &&
            !faces[cl[j].face].colour) {
            static const uint32_t space = ' ';
            if (covers(cl[j].face, &space, 1))
                for (int k = i; k < j; k++) cl[k].face = cl[j].face;
        }
        i = j;
    }
    int from = 0;
    for (int i = 1; i <= ncl; i++)
        if (i == ncl || cl[i].face != cl[from].face) {
            shape_segment(cl + from, i - from, x, y);
            from = i;
        }
}

/* A horizontal line across cells [x, x + n) of row y, `top` pixels into
 * the row, kept inside it. */
static void hline(uint32_t rgb, int x, int n, int y, int top, int h) {
    if (top + h > ch) top = ch - h;
    if (top < 0) top = 0;
    fill(rgb, x * cw, y * ch + top, n * cw, h);
}

/* The lines a stretch of one style draws over its glyphs: the underline in
 * its kind (1 single, 2 double, 3 curly, 4 dotted, 5 dashed), the
 * strikethrough, the overline, and the cursor's shape. */
static void draw_lines(int y, int x, int n, int style) {
    int kind = style_ul[style] & 15, shape = style_ul[style] >> 4, flags = style_flags[style];
    uint32_t ulc = style_ulc[style], fg = style_fg[style];
    int t = line_thick, top = ascent + ul_below;
    if (!(flags & 0x20)) {
        if (kind == 1) hline(ulc, x, n, y, top, t);
        else if (kind == 2) {
            hline(ulc, x, n, y, top, t);
            hline(ulc, x, n, y, top + 2 * t, t);
        } else if (kind >= 3 && kind <= 5) {
            int px = x * cw, end = (x + n) * cw, step = kind == 3 ? 2 : kind == 4 ? 2 * t : 3 * t;
            static xcb_rectangle_t rs[4096];
            int k = 0;
            int base = y * ch + (top + 2 * t > ch ? ch - 2 * t : top);
            for (int p = px; p < end && k < 4096; p += step) {
                int w = step;
                if (kind == 4) w = t;
                else if (kind == 5) w = 2 * t;
                if (p + w > end) w = end - p;
                int dy = kind == 3 ? (((p - px) / 2) % 4 < 2 ? 0 : t) : 0;
                rs[k++] = (xcb_rectangle_t) {(int16_t) p, (int16_t) (base + dy), (uint16_t) w, (uint16_t) t};
            }
            xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(ulc), (uint32_t) k, rs);
        }
        if (flags & 0x40) hline(fg, x, n, y, ascent - strike_above, t);
        if (flags & 0x80) hline(fg, x, n, y, 0, t);
    }
    if (shape == 2) {
        int h = ch / 8 > 2 ? ch / 8 : 2;
        hline(ulc, x, n, y, ch - h, h);
    } else if (shape == 3) {
        int w = cw / 6 > 2 ? cw / 6 : 2;
        fill(ulc, x * cw, y * ch, w, ch);
    } else if (shape == 4) {
        fill(ulc, x * cw, y * ch, n * cw, 1);
        fill(ulc, x * cw, y * ch + ch - 1, n * cw, 1);
        fill(ulc, x * cw, y * ch, 1, ch);
        fill(ulc, (x + n) * cw - 1, y * ch, 1, ch);
    }
}

/* A run record: backgrounds, glyphs, lines. Answers past its last cell. */
static const uint8_t *draw_run(const uint8_t *p, const uint8_t *end) {
    int y = (p[1] << 8) | p[2], x = (p[3] << 8) | p[4], n = (p[5] << 8) | p[6];
    const uint8_t *cell = p + 7, *q = cell;
    static int styles[65536];
    for (int i = 0; i < n && q + 3 <= end; i++) {
        styles[i] = (q[1] << 8) | q[2];
        q += 3 + 3 * (q[0] & 63);
    }
    if (q > end) return end;
    for (int from = 0, i = 1; i <= n; i++)
        if (i == n || style_bg[styles[i]] != style_bg[styles[from]]) {
            fill(style_bg[styles[from]], (x + from) * cw, y * ch, (i - from) * cw, ch);
            from = i;
        }
    draw_glyphs(y, x, n, cell);
    flush_placed();
    for (int from = 0, i = 1; i <= n; i++)
        if (i == n || styles[i] != styles[from]) {
            if (style_ul[styles[from]] || (style_flags[styles[from]] & 0xC0)) draw_lines(y, x + from, i - from, styles[from]);
            from = i;
        }
    return q;
}

/* THE PIXMAP AND THE WINDOW */

/* A pixmap for a screen of c by r cells; the frame that says the size
 * draws every cell into it. */
static void make_pixmap(int c, int r) {
    if (pixmap) {
        xcb_render_free_picture(conn, target);
        xcb_free_pixmap(conn, pixmap);
    }
    cols = c;
    rows = r;
    pixmap = xcb_generate_id(conn);
    xcb_create_pixmap(conn, screen->root_depth, pixmap, window, (uint16_t) (c * cw), (uint16_t) (r * ch));
    target = xcb_generate_id(conn);
    xcb_render_create_picture(conn, target, pixmap, visual_format, 0, NULL);
    fill(0, 0, 0, c * cw, r * ch);
    margin_bg = 0xFFFFFFFF;
}

/* The window past the screen's cells, in the default background: its
 * background pixel, which the server also fills an expose with. A
 * TrueColor visual of 24 bits is taken, whose pixel is its RGB. */
static void margins(void) {
    uint32_t bg = style_bg[0];
    if (bg == margin_bg) return;
    margin_bg = bg;
    xcb_change_window_attributes(conn, window, XCB_CW_BACK_PIXEL, &bg);
    xcb_clear_area(conn, 0, window, (int16_t) (cols * cw), 0, 0, 0);
    xcb_clear_area(conn, 0, window, 0, (int16_t) (rows * ch), 0, 0);
}

static void stats(void) {
    if (!getenv("X11_STATS")) return;
    fprintf(stderr,
            "x11: frames %ld; clusters %ld (fallback %ld), fontconfig queries %ld (%.2f ms, %ld found none), segments %ld, "
            "glyphs %ld; uploaded %ld (%ld bytes held), resets %ld; colour %ld, squeezed %ld; shape %.2f ms, raster %.2f ms, "
            "draw %.2f ms\n",
            st.frames, st.clusters, st.fallback_clusters, st.fc_queries, st.fc_ns / 1e6, st.fc_failed, st.segments, st.glyphs,
            st.uploaded, glyph_bytes, resets, st.colour, st.squeezed, st.shape_ns / 1e6, st.raster_ns / 1e6, st.draw_ns / 1e6);
}

/* The window as a PPM: what is on the screen, the cursor and the margins
 * with it. Answers 0, or -1. */
static int write_shot(const char *path) {
    xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(conn, xcb_get_geometry(conn, window), NULL);
    if (!g) return -1;
    int w = g->width, h = g->height;
    free(g);
    xcb_get_image_reply_t *r =
        xcb_get_image_reply(conn, xcb_get_image(conn, XCB_IMAGE_FORMAT_Z_PIXMAP, window, 0, 0, (uint16_t) w, (uint16_t) h, ~0u), NULL);
    if (!r) return -1;
    FILE *o = fopen(path, "wb");
    if (!o) {
        free(r);
        return -1;
    }
    const uint8_t *d = xcb_get_image_data(r);
    fprintf(o, "P6\n%d %d\n255\n", w, h);
    for (int i = 0; i < w * h; i++) {
        uint8_t px[3] = {d[i * 4 + 2], d[i * 4 + 1], d[i * 4]};
        fwrite(px, 1, 3, o);
    }
    fclose(o);
    free(r);
    return 0;
}

static void at_exit(void) {
    stats();
    const char *path = getenv("X11_SHOT");
    if (path && conn) write_shot(path);
}

/* EVENTS */

static uint8_t evbuf[65536];
static int evlen;

static void record(const uint8_t *r, int n) {
    if (evlen + n > (int) sizeof evbuf) return;
    memcpy(evbuf + evlen, r, (size_t) n);
    evlen += n;
}

static struct xkb_context *xctx;
static struct xkb_keymap *keymap;
static struct xkb_state *kstate;
static int32_t kbd = -1;
static uint8_t xkb_event;

static void key_setup(void) {
    if (!xkb_x11_setup_xkb_extension(conn, XKB_X11_MIN_MAJOR_XKB_VERSION, XKB_X11_MIN_MINOR_XKB_VERSION,
                                     XKB_X11_SETUP_XKB_EXTENSION_NO_FLAGS, NULL, NULL, &xkb_event, NULL))
        return;
    if (!xctx) xctx = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    kbd = xkb_x11_get_core_keyboard_device_id(conn);
    if (keymap) xkb_keymap_unref(keymap);
    if (kstate) xkb_state_unref(kstate);
    keymap = xkb_x11_keymap_new_from_device(xctx, conn, kbd, XKB_KEYMAP_COMPILE_NO_FLAGS);
    kstate = keymap ? xkb_x11_state_new_from_device(keymap, conn, kbd) : NULL;
    uint16_t events = XCB_XKB_EVENT_TYPE_NEW_KEYBOARD_NOTIFY | XCB_XKB_EVENT_TYPE_MAP_NOTIFY | XCB_XKB_EVENT_TYPE_STATE_NOTIFY;
    uint16_t parts = XCB_XKB_MAP_PART_KEY_TYPES | XCB_XKB_MAP_PART_KEY_SYMS | XCB_XKB_MAP_PART_MODIFIER_MAP |
                     XCB_XKB_MAP_PART_EXPLICIT_COMPONENTS | XCB_XKB_MAP_PART_KEY_ACTIONS | XCB_XKB_MAP_PART_VIRTUAL_MODS |
                     XCB_XKB_MAP_PART_VIRTUAL_MOD_MAP;
    xcb_xkb_select_events(conn, (xcb_xkb_device_spec_t) kbd, events, 0, events, parts, parts, NULL);
}

static void key_press(uint8_t keycode) {
    if (!kstate) return;
    xkb_keysym_t sym = xkb_state_key_get_one_sym(kstate, keycode);
    char text[64];
    int n = xkb_state_key_get_utf8(kstate, keycode, text, sizeof text);
    if (n < 0) n = 0;
    if (n > 63) n = 63;
    int mods = (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_SHIFT, XKB_STATE_MODS_EFFECTIVE) > 0 ? 1 : 0) |
               (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_CTRL, XKB_STATE_MODS_EFFECTIVE) > 0 ? 2 : 0) |
               (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_ALT, XKB_STATE_MODS_EFFECTIVE) > 0 ? 4 : 0) |
               (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_LOGO, XKB_STATE_MODS_EFFECTIVE) > 0 ? 8 : 0);
    uint8_t r[7 + 63] = {1, (uint8_t) (sym >> 24), (uint8_t) (sym >> 16), (uint8_t) (sym >> 8), (uint8_t) sym, (uint8_t) mods,
                         (uint8_t) n};
    memcpy(r + 7, text, (size_t) n);
    record(r, 7 + n);
}

static void xkb_event_in(xcb_generic_event_t *e) {
    uint8_t type = ((uint8_t *) e)[1];
    if (type == XCB_XKB_STATE_NOTIFY) {
        xcb_xkb_state_notify_event_t *s = (xcb_xkb_state_notify_event_t *) e;
        if (kstate)
            xkb_state_update_mask(kstate, s->baseMods, s->latchedMods, s->lockedMods, (xkb_layout_index_t) s->baseGroup,
                                  (xkb_layout_index_t) s->latchedGroup, s->lockedGroup);
    } else if (type == XCB_XKB_NEW_KEYBOARD_NOTIFY || type == XCB_XKB_MAP_NOTIFY) {
        key_setup();
    }
}

static void size_in(int w, int h) {
    int c = w / cw, r = h / ch;
    if (c < 1) c = 1;
    if (r < 1) r = 1;
    if (c > 65535) c = 65535;
    if (r > 65535) r = 65535;
    if (c == win_cols && r == win_rows) return;
    win_cols = c;
    win_rows = r;
    uint8_t rec[5] = {2, (uint8_t) (c >> 8), (uint8_t) c, (uint8_t) (r >> 8), (uint8_t) r};
    record(rec, 5);
}

static void focus_in(int in) {
    if (in == focused) return;
    focused = in;
    uint8_t rec[2] = {3, (uint8_t) in};
    record(rec, 2);
}

static void drain(void) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(conn)) != NULL) {
        int type = e->response_type & 0x7f;
        if (xkb_event && type == xkb_event) xkb_event_in(e);
        else if (type == XCB_KEY_PRESS) key_press(((xcb_key_press_event_t *) e)->detail);
        else if (type == XCB_EXPOSE) {
            xcb_expose_event_t *x = (xcb_expose_event_t *) e;
            if (pixmap)
                xcb_copy_area(conn, pixmap, window, gc, (int16_t) x->x, (int16_t) x->y, (int16_t) x->x, (int16_t) x->y, x->width,
                              x->height);
            xcb_flush(conn);
        } else if (type == XCB_CONFIGURE_NOTIFY) {
            xcb_configure_notify_event_t *c = (xcb_configure_notify_event_t *) e;
            if (c->window == window) size_in(c->width, c->height);
        } else if (type == XCB_FOCUS_IN || type == XCB_FOCUS_OUT) {
            xcb_focus_in_event_t *f = (xcb_focus_in_event_t *) e;
            if (f->detail != XCB_NOTIFY_DETAIL_POINTER) focus_in(type == XCB_FOCUS_IN);
        } else if (type == XCB_CLIENT_MESSAGE) {
            xcb_client_message_event_t *m = (xcb_client_message_event_t *) e;
            if (m->type == wm_protocols && m->data.data32[0] == wm_delete) {
                uint8_t rec[1] = {4};
                record(rec, 1);
            }
        }
        free(e);
    }
}

/* THE ROWS */

static xcb_atom_t atom(const char *name) {
    xcb_intern_atom_reply_t *r = xcb_intern_atom_reply(conn, xcb_intern_atom(conn, 0, (uint16_t) strlen(name), name), NULL);
    xcb_atom_t a = r ? r->atom : XCB_ATOM_NONE;
    free(r);
    return a;
}

static char *string_of(void *bytes) {
    geng_bytes *b = bytes;
    char *s = malloc((size_t) b->length + 1);
    memcpy(s, b->data, (size_t) b->length);
    s[b->length] = 0;
    return s;
}

static void set_title(const uint8_t *text, int n) {
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, net_wm_name, utf8_string, 8, (uint32_t) n, text);
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_NAME, XCB_ATOM_STRING, 8, (uint32_t) n, text);
}

/* Opens the window: `c` by `r` cells of the font `font` at `points`,
 * fallback asked in the language `lang` (empty for none, V25), the glyph
 * set reset past `cap` bytes (V37). Answers the cell's width and height as
 * `width * 65536 + height`, or a negative code: -1 no font, -2 no X server,
 * -3 no RENDER formats it needs. */
geng_cancel visiterm_x11_open(int32_t c, int32_t r, int32_t points, void *font_bytes, void *lang_bytes, int32_t cap,
                              void *title_bytes, geng_wait *wait) {
    points0 = points;
    glyph_cap = cap;
    char *font = string_of(font_bytes);
    lang_name = string_of(lang_bytes);
    if (!*lang_name) {
        free(lang_name);
        lang_name = NULL;
    } else
        language = hb_language_from_string(lang_name, -1);
    hbuf = hb_buffer_create();
    FcInit();
    int index;
    char *file = font_file(font, &index);
    if (file == NULL || FT_Init_FreeType(&library) != 0 || load_face(file, index, 1) != 0) {
        geng_succeed(wait, geng_slot_I4(-1));
        return (geng_cancel) {0};
    }
    primary[0] = 0;
    static const char *const variants[3] = {":bold", ":italic", ":bold:italic"};
    for (int v = 0; v < 3; v++) {
        size_t len = strlen(font) + strlen(variants[v]) + 1;
        char *spec = malloc(len);
        snprintf(spec, len, "%s%s", font, variants[v]);
        int vi;
        char *vf = font_file(spec, &vi);
        int f = vf ? load_face(vf, vi, 1) : -1;
        primary[v + 1] = f < 0 ? 0 : f;
        free(vf);
        free(spec);
    }
    /* A variant is bold when fontconfig gave it a face other than the one
     * it gave the same variant without bold, and italic likewise; a font
     * with no bold or italic face of its own gives the regular, whose
     * glyphs are then drawn bold or italic (C§9 rule 6). */
    for (int v = 1; v < 4; v++) {
        if ((v & 1) && primary[v] != primary[v & ~1]) faces[primary[v]].own |= 1;
        if ((v & 2) && primary[v] != primary[v & ~2]) faces[primary[v]].own |= 2;
    }
    free(font);
    FT_Face face = faces[0].ft;
    cw = (int) (face->size->metrics.max_advance >> 6);
    ch = (int) (face->size->metrics.height >> 6);
    ascent = (int) (face->size->metrics.ascender >> 6);
    long below = -FT_MulFix(face->underline_position, face->size->metrics.y_scale) >> 6;
    long thick = FT_MulFix(face->underline_thickness, face->size->metrics.y_scale) >> 6;
    line_thick = thick < 1 ? 1 : (int) thick;
    ul_below = below < 1 ? 1 : (int) below;
    strike_above = ascent * 3 / 10;
    atexit(at_exit);

    conn = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(conn)) {
        geng_succeed(wait, geng_slot_I4(-2));
        return (geng_cancel) {0};
    }
    screen = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    const xcb_render_query_pict_formats_reply_t *formats = xcb_render_util_query_formats(conn);
    xcb_render_pictforminfo_t *fa8 = xcb_render_util_find_standard_format(formats, XCB_PICT_STANDARD_A_8);
    xcb_render_pictvisual_t *visual = xcb_render_util_find_visual_format(formats, screen->root_visual);
    xcb_render_pictforminfo_t *a32 = xcb_render_util_find_standard_format(formats, XCB_PICT_STANDARD_ARGB_32);
    if (fa8 == NULL || visual == NULL || a32 == NULL) {
        geng_succeed(wait, geng_slot_I4(-3));
        return (geng_cancel) {0};
    }
    a8 = fa8->id;
    argb32 = a32->id;
    visual_format = visual->format;
    win_cols = c;
    win_rows = r;
    window = xcb_generate_id(conn);
    uint32_t values[2] = {screen->black_pixel, XCB_EVENT_MASK_EXPOSURE | XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_FOCUS_CHANGE |
                                                   XCB_EVENT_MASK_STRUCTURE_NOTIFY};
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, screen->root, 0, 0, (uint16_t) (c * cw), (uint16_t) (r * ch), 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual, XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK, values);
    wm_protocols = atom("WM_PROTOCOLS");
    wm_delete = atom("WM_DELETE_WINDOW");
    net_wm_name = atom("_NET_WM_NAME");
    utf8_string = atom("UTF8_STRING");
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, wm_protocols, XCB_ATOM_ATOM, 32, 1, &wm_delete);
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_CLASS, XCB_ATOM_STRING, 8, 18, "visiterm\0Visiterm\0");
    /* WM_NORMAL_HINTS (ICCCM 4.1.2.3): a minimum of one cell, the base 0,
     * and a step of a cell. Flags: PMinSize 16, PResizeInc 64, PBaseSize 256. */
    uint32_t hints[18] = {16 | 64 | 256, 0, 0, 0, 0, (uint32_t) cw, (uint32_t) ch, 0, 0, (uint32_t) cw, (uint32_t) ch, 0, 0, 0, 0, 0, 0, 0};
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_NORMAL_HINTS, XCB_ATOM_WM_SIZE_HINTS, 32, 18, hints);
    geng_bytes *t = title_bytes;
    set_title(t->data, (int) t->length);
    key_setup();
    gc = xcb_generate_id(conn);
    uint32_t no_exposures = 0;
    xcb_create_gc(conn, gc, window, XCB_GC_GRAPHICS_EXPOSURES, &no_exposures);
    glyphs = xcb_generate_id(conn);
    xcb_render_create_glyph_set(conn, glyphs, a8);
    make_pixmap(c, r);
    xcb_map_window(conn, window);
    xcb_flush(conn);
    geng_succeed(wait, geng_slot_I4(cw * 65536 + ch));
    return (geng_cancel) {0};
}

/* Executes one frame's display list. Answers 0, or -1 once the connection
 * has failed. */
geng_cancel visiterm_x11_draw(void *list, geng_wait *wait) {
    double t0 = ns();
    if (glyph_bytes > glyph_cap) reset_glyphs();
    geng_bytes *b = list;
    const uint8_t *p = b->data, *end = b->data + b->length;
    int first = rows, last = -1, sized = 0;
    while (p < end) {
        if (p[0] == 4 && p + 5 <= end) {
            int c = (p[1] << 8) | p[2], r = (p[3] << 8) | p[4];
            if (c != cols || r != rows || !pixmap) make_pixmap(c, r);
            first = 0;
            last = rows - 1;
            sized = 1;
            p += 5;
        } else if (p[0] == 3 && p + 14 <= end) {
            int id = (p[1] << 8) | p[2];
            style_fg[id] = ((uint32_t) p[3] << 16) | ((uint32_t) p[4] << 8) | p[5];
            style_bg[id] = ((uint32_t) p[6] << 16) | ((uint32_t) p[7] << 8) | p[8];
            style_ulc[id] = ((uint32_t) p[9] << 16) | ((uint32_t) p[10] << 8) | p[11];
            style_flags[id] = p[12];
            style_ul[id] = p[13];
            p += 14;
        } else if (p[0] == 1 && p + 7 <= end) {
            int top = (p[1] << 8) | p[2], bottom = (p[3] << 8) | p[4], k = (int16_t) ((p[5] << 8) | p[6]);
            xcb_copy_area(conn, pixmap, pixmap, gc, 0, (int16_t) ((top + k) * ch), 0, (int16_t) (top * ch), (uint16_t) (cols * cw),
                          (uint16_t) ((bottom - top + 1) * ch));
            if (top < first) first = top;
            if (bottom > last) last = bottom;
            p += 7;
        } else if (p[0] == 2 && p + 7 <= end) {
            int y = (p[1] << 8) | p[2];
            p = draw_run(p, end);
            if (y < first) first = y;
            if (y > last) last = y;
        } else
            break; /* a record this does not know: the rest of the list is not read */
    }
    if (last >= first)
        xcb_copy_area(conn, pixmap, window, gc, 0, (int16_t) (first * ch), 0, (int16_t) (first * ch), (uint16_t) (cols * cw),
                      (uint16_t) ((last - first + 1) * ch));
    if (sized || style_bg[0] != margin_bg) margins();
    xcb_flush(conn);
    drain();
    st.frames++;
    st.draw_ns += ns() - t0;
    geng_succeed(wait, geng_slot_I4(xcb_connection_has_error(conn) ? -1 : 0));
    return (geng_cancel) {0};
}

/* The loop's wait on the X connection (phase2-window.md §12). xcb reads
 * the socket in its own calls (a flush, a reply) and queues what events it
 * finds, so the descriptor can be quiet while events wait: `drain` reads
 * what is queued and what the socket has, and only when it has made no
 * record does the loop wait on the descriptor. `visiterm_x11_events`
 * answers that records are there and takes none, since `Task.race` drops a
 * losing branch's answer when two answer in one round (§12);
 * `visiterm_x11_take`, after the race, takes them. */
typedef struct xwait {
    geng_wait *wait;
    geng_io *io;
} xwait;

#define XWAIT_HEADER (GENG_HEADER_WORDS(xwait) | GENG_HEADER_POINTER(xwait, wait) | GENG_HEADER_POINTER(xwait, io))

/* Answers 1 once records are there, or -1 once the connection has failed. */
static int answer(geng_wait *wait) {
    if (xcb_connection_has_error(conn)) {
        geng_succeed(wait, geng_slot_I4(-1));
        return 1;
    }
    drain();
    if (evlen == 0) return 0;
    geng_succeed(wait, geng_slot_I4(1));
    return 1;
}

static void x_ready(void *env, short revents) {
    (void) revents;
    xwait *w = env;
    w->io = NULL;
    if (!answer(w->wait)) {
        w->io = geng_io_wait(xcb_get_file_descriptor(conn), POLLIN, x_ready, w);
        geng_write_barrier(w, &w->io, w->io);
    }
}

static geng_task *x_stop(void *env) {
    xwait *w = env;
    if (w->io != NULL) geng_io_cancel(w->io);
    w->io = NULL;
    return NULL;
}

geng_cancel visiterm_x11_events(geng_wait *wait) {
    if (answer(wait)) return (geng_cancel) {0};
    xwait *w = geng_alloc(sizeof *w, XWAIT_HEADER);
    *w = (xwait) {.wait = wait, .io = NULL};
    w->io = geng_io_wait(xcb_get_file_descriptor(conn), POLLIN, x_ready, w);
    geng_write_barrier(w, &w->io, w->io);
    return (geng_cancel) {x_stop, w};
}

/* The records since the last take. */
geng_cancel visiterm_x11_take(geng_wait *wait) {
    drain();
    geng_bytes *b = geng_alloc_atomic(sizeof *b + (size_t) evlen, GENG_HEADER_BYTES(sizeof *b + (size_t) evlen));
    b->length = evlen;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    memcpy(b->data, evbuf, (size_t) evlen);
    evlen = 0;
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}

geng_cancel visiterm_x11_title(void *text, geng_wait *wait) {
    geng_bytes *t = text;
    set_title(t->data, (int) t->length);
    xcb_flush(conn);
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel visiterm_x11_shot(void *path_bytes, geng_wait *wait) {
    char *path = string_of(path_bytes);
    int r = write_shot(path);
    free(path);
    geng_succeed(wait, geng_slot_I4(r));
    return (geng_cancel) {0};
}

/* Phase 2's survey probe (visiterm docs/phase2-window.md §5): a display list
 * drawn on X11 the way S§6.2 says, and C§6's glyph sets:
 *
 *   - everything is drawn into a retained pixmap, then the rows a frame
 *     touched are copied to the window, so an expose needs no redraw;
 *   - a scroll record is one CopyArea within the pixmap, up or down;
 *   - a run is one RenderFillRectangles for its background and a
 *     RenderCompositeGlyphs32 per stretch of one foreground colour;
 *   - a run's clusters are shaped by HarfBuzz, in fallback faces where the
 *     primary lacks them (§13), and a glyph is rasterised by FreeType and
 *     uploaded with RenderAddGlyphs the first time it is drawn.
 *
 * What the probe leaves out, said in §5 and §13.10: synthesised bold and italic, the cursor, every event but an expose, and the colours of the
 * core's styles: a style id picks a colour from a fixed palette, which
 * costs the same requests. */
#define _GNU_SOURCE
#include <fontconfig/fontconfig.h>
#include <poll.h>
#include <ft2build.h>
#include FT_FREETYPE_H
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
static xcb_window_t window;
static xcb_pixmap_t pixmap;
static xcb_gcontext_t gc;
static xcb_render_picture_t target;
static xcb_render_glyphset_t glyphs;
static FT_Library library;
static int cw, ch, ascent, cols, rows, uploaded;
static xcb_render_picture_t solid[256];

static const uint32_t palette[16] = {0x000000, 0xcd3131, 0x0dbc79, 0xe5e510, 0x2472c8, 0xbc3fbc, 0x11a8cd, 0xe5e5e5,
                                     0x666666, 0xf14c4c, 0x23d18b, 0xf5f543, 0x3b8eea, 0xd670d6, 0x29b8db, 0xffffff};

static xcb_render_color_t colour(uint32_t rgb) {
    return (xcb_render_color_t) {.red = (uint16_t) (((rgb >> 16) & 0xff) * 257), .green = (uint16_t) (((rgb >> 8) & 0xff) * 257),
                                 .blue = (uint16_t) ((rgb & 0xff) * 257), .alpha = 0xffff};
}

static uint32_t fg_of(int style) { return style == 0 ? 0xe5e5e5 : palette[8 + (style * 7) % 8]; }
static uint32_t bg_of(int style) { return style == 0 ? 0x000000 : palette[(style * 3) % 8]; }

static xcb_render_picture_t solid_of(uint32_t rgb) {
    int i = (int) ((rgb ^ (rgb >> 8) ^ (rgb >> 16)) & 0xff);
    /* A probe's cache: a collision makes a second picture, which costs one
     * request, and the palette has 17 colours. */
    if (solid[i] == 0) {
        solid[i] = xcb_generate_id(conn);
        xcb_render_create_solid_fill(conn, solid[i], colour(rgb));
    }
    return solid[i];
}

static char *font_file(const char *spec) {
    FcInit();
    FcPattern *p = FcNameParse((const FcChar8 *) spec);
    FcConfigSubstitute(NULL, p, FcMatchPattern);
    FcDefaultSubstitute(p);
    FcResult r;
    FcPattern *m = FcFontMatch(NULL, p, &r);
    FcChar8 *file = NULL;
    char *out = NULL;
    if (m != NULL && FcPatternGetString(m, FC_FILE, 0, &file) == FcResultMatch) out = strdup((const char *) file);
    if (m != NULL) FcPatternDestroy(m);
    FcPatternDestroy(p);
    return out;
}

static void drain(void);

/* Fonts and shaping (docs/phase2-window.md §13). Face 0 is the primary
 * font; a cluster it lacks goes, whole, to the first loaded face that has
 * every code point of it, and only then to fontconfig, which is asked with
 * the cluster's code points and the profile's language (PROBE_LANG). A
 * face with 水 is sized so 水 fills two cells and its ink stays within the
 * primary cell's ascent and descent; a wide glyph is centred in its two
 * cells. A segment of clusters in one face is shaped as one HarfBuzz run,
 * with each code point's cluster its cell, so glyphs map back to cells by
 * the core's widths, not the shaper's advances. PROBE_SHAPE=0 draws as §5
 * did: the cell's first code point, from face 0 alone. */
#define FACES 32
typedef struct {
    FT_Face ft;
    hb_font_t *hb;
    char *file;
    int index;
    double scale;
    int colour;        /* a face of colour bitmaps (CBDT), drawn as pictures */
    uint8_t *uploaded; /* a bit a glyph index and form */
    int16_t *advance;  /* the x_off each glyph was uploaded with */
    struct ColourGlyph *pictures;
} Face;

/* A colour glyph (§13.10): an ARGB32 picture of the glyph scaled into its
 * cells, made the first time it is drawn and composited at each use. */
typedef struct ColourGlyph {
    uint32_t g;
    int box;
    xcb_render_picture_t picture;
    int w, h;
    struct ColourGlyph *next;
} ColourGlyph;
static xcb_render_pictformat_t argb32;
static Face faces[FACES];
static int nfaces, shaping = 1, points0;
static hb_language_t language;
static const char *lang_name;
static hb_buffer_t *hbuf;
static struct {
    long clusters, fallback_clusters, fc_queries, fc_failed, segments, glyphs, elements, requests, colour, squeezed, joined;
    double fc_ns, shape_ns, raster_ns, draw_ns;
    long keys, key_frames;
    double keymap_ns, xkb_ns, key_sum_ns, key_max_ns;
} st;

static double key_at;
static void key_setup(void);

static double ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e9 + t.tv_nsec;
}

/* Code points that select a form rather than need a glyph of their own. */
static int ignorable(uint32_t cp) {
    return cp == 0x200D || cp == 0x200C || (cp >= 0xFE00 && cp <= 0xFE0F) || (cp >= 0xE0100 && cp <= 0xE01EF);
}

/* A cluster that asks for emoji presentation: one with U+FE0F, or one
 * whose first code point is in the blocks where emoji default to it. An
 * approximation of UTS #51's Emoji_Presentation, enough for a probe. */
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

static int load_face(const char *file, int index) {
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
    if (nfaces > 0 && !F->colour) {
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
    F->uploaded = calloc(262144 / 8, 1);
    F->advance = calloc(262144, sizeof *F->advance);
    if (getenv("PROBE_STATS"))
        fprintf(stderr, "face %d: %s#%d scale %.3f\n", nfaces, F->file, index, F->scale);
    return nfaces++;
}

/* A small cache from a cluster's first missing code point to its face, so
 * that fontconfig is asked once a code point; -1 where it found none. */
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
        int f = load_face((const char *) file, index);
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

/* A glyph's advance on the server is fixed when it is uploaded: the pen
 * moves by it inside an element, whatever the run asks. The first use
 * chooses it; a glyph placed elsewhere starts a new element. */
/* A glyph alone in a cluster narrower than its cells is uploaded a second
 * time with its centring in its bearing (`shift`), so that it is placed at
 * its cell like any other and a line of them stays in one element. */
/* A glyph wider than the one cell the core gives it is uploaded a third
 * way, squeezed to the cell (`squeeze`, 16.16; PuTTY's narrow trick,
 * C§4.4). */
static uint32_t upload(int f, uint32_t g, int advance, int shift, FT_Fixed squeeze) {
    uint32_t k = (g & 0xFFFF) | (shift ? 0x10000 : 0) | (squeeze ? 0x20000 : 0);
    uint32_t id = ((uint32_t) f << 18) | k;
    Face *F = &faces[f];
    if (F->uploaded[k >> 3] & (1 << (k & 7))) return id;
    F->uploaded[k >> 3] |= (uint8_t) (1 << (k & 7));
    F->advance[k] = (int16_t) advance;
    uploaded++;
    double t0 = ns();
    if (squeeze) {
        FT_Matrix m = {squeeze, 0, 0, 0x10000};
        FT_Set_Transform(F->ft, &m, NULL);
    }
    FT_Load_Glyph(F->ft, g, FT_LOAD_RENDER | (squeeze ? FT_LOAD_NO_HINTING : 0));
    if (squeeze) FT_Set_Transform(F->ft, NULL, NULL);
    FT_Bitmap *b = &F->ft->glyph->bitmap;
    int stride = ((int) b->width + 3) & ~3;
    size_t size = (size_t) stride * b->rows;
    uint8_t *data = calloc(size > 0 ? size : 4, 1);
    for (unsigned y = 0; y < b->rows; y++) memcpy(data + y * stride, b->buffer + y * b->pitch, b->width);
    xcb_render_glyphinfo_t info = {.width = (uint16_t) b->width, .height = (uint16_t) b->rows,
                                   .x = (int16_t) (-F->ft->glyph->bitmap_left - shift), .y = (int16_t) F->ft->glyph->bitmap_top,
                                   .x_off = (int16_t) advance, .y_off = 0};
    xcb_render_add_glyphs(conn, glyphs, 1, &id, &info, (uint32_t) size, data);
    free(data);
    st.raster_ns += ns() - t0;
    return id;
}

/* The glyphs a run draws, in order, before they go out as requests. */
typedef struct { uint32_t id; int x, y, fg, advance; } Placed;
static Placed placed[8192];
static int nplaced;

static void place(int f, uint32_t g, int x, int y, int fg, int advance, int shift, FT_Fixed squeeze) {
    if (nplaced == 8192) return;
    uint32_t id = upload(f, g, advance, shift, squeeze);
    placed[nplaced++] = (Placed) {id, x, y, fg, faces[f].advance[id & 0x3FFFF]};
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
    uploaded++;
    st.raster_ns += ns() - t0;
    return c;
}

/* Each stretch of one colour as one CompositeGlyphs32, a new element where
 * a glyph is not where the last one's advance left the pen. */
static void flush_placed(void) {
    static uint8_t buffer[65536];
    int i = 0;
    while (i < nplaced) {
        int fg = placed[i].fg, len = 0, penx = 0, peny = 0, count_at = -1, count = 0;
        st.requests++;
        for (; i < nplaced && placed[i].fg == fg && len < 60000; i++) {
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
                st.elements++;
            }
            memcpy(buffer + len, &P->id, 4);
            len += 4;
            buffer[count_at] = (uint8_t) ++count;
            penx = P->x + P->advance;
            peny = P->y;
            st.glyphs++;
        }
        xcb_render_composite_glyphs_32(conn, XCB_RENDER_PICT_OP_OVER, solid_of(fg_of(fg)), target, 0, glyphs, 0, 0,
                                       (uint32_t) len, buffer);
    }
    nplaced = 0;
}

typedef struct { int cell, width, style, n; const uint32_t *cps; int face; } Cluster;

/* A segment of clusters in one face, shaped as one run. */
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
        int box = C->width * cw;
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
            /* The advance kept with the glyph: what it takes to reach the
             * next cell when it ends its cluster, so runs of one width stay
             * in one element. */
            if (k + 1 < e) a = (gp[k].x_advance + gp[k + 1].x_offset - gp[k].x_offset) >> 6;
            if (e - g == 1 && pad > 0 && gp[k].x_offset == 0)
                place(f, gi[k].codepoint, x - pad, yy, C->style, box, pad, 0);
            else if (e - g == 1 && C->width == 1 && (adv >> 6) > cw && gp[k].x_offset == 0) {
                /* Wider than its one cell: squeezed into it. */
                place(f, gi[k].codepoint, x, yy, C->style, cw, 0, (FT_Fixed) ((double) cw * 64 / adv * 65536));
                st.squeezed++;
            } else
                place(f, gi[k].codepoint, x, yy, C->style, a, 0, 0);
            pen += gp[k].x_advance;
        }
        g = e;
    }
}

static void draw_run(int y, int x, int n, const uint8_t *p) {
    static Cluster cl[1024];
    static uint32_t cps[1024 * 64];
    int ncl = 0, ncps = 0;
    for (int i = 0; i < n; i++) {
        int wide = p[0] >> 6, count = p[0] & 63, style = (p[1] << 8) | p[2];
        p += 3;
        uint32_t *mine = cps + ncps;
        for (int k = 0; k < count; k++, p += 3) mine[k] = ((uint32_t) p[0] << 16) | ((uint32_t) p[1] << 8) | p[2];
        if (wide == 2 || wide == 3) continue; /* a tail or a spacer: its head draws it */
        if (count == 0) continue;            /* blank: the fill draws it */
        ncps += count;
        cl[ncl++] = (Cluster) {i, wide == 1 ? 2 : 1, style, count, mine, 0};
    }
    st.clusters += ncl;
    if (!shaping) {
        for (int i = 0; i < ncl; i++) {
            FT_UInt g = FT_Get_Char_Index(faces[0].ft, cl[i].cps[0]);
            place(0, g, (x + cl[i].cell) * cw, y * ch + ascent, cl[i].style, cl[i].width * cw, 0, 0);
        }
        return;
    }
    for (int i = 0; i < ncl; i++) {
        if (faces[0].colour == emoji(cl[i].cps, cl[i].n) && covers(0, cl[i].cps, cl[i].n)) cl[i].face = 0;
        else {
            st.fallback_clusters++;
            cl[i].face = fallback(cl[i].cps, cl[i].n);
        }
    }
    /* Spaces between two clusters of one fallback face join their run when
     * that face has a space, so a line of Thai is one run, not a word each
     * (V24). */
    for (int i = 0; i < ncl;) {
        if (cl[i].face != 0 || cl[i].n != 1 || cl[i].cps[0] != ' ') { i++; continue; }
        int j = i;
        while (j < ncl && cl[j].face == 0 && cl[j].n == 1 && cl[j].cps[0] == ' ') j++;
        if (i > 0 && j < ncl && cl[i - 1].face > 0 && cl[i - 1].face == cl[j].face && !faces[cl[j].face].colour) {
            static const uint32_t space = ' ';
            if (covers(cl[j].face, &space, 1))
                for (int k = i; k < j; k++, st.joined++) cl[k].face = cl[j].face;
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

static void stats(void) {
    if (!getenv("PROBE_STATS")) return;
    fprintf(stderr, "keys %ld: keymap %.2f ms, xkb %.0f ns a key; %ld frames after a key, key to frame mean %.2f ms, max %.2f ms\n",
            st.keys, st.keymap_ns / 1e6, st.keys ? st.xkb_ns / st.keys : 0, st.key_frames,
            st.key_frames ? st.key_sum_ns / st.key_frames / 1e6 : 0, st.key_max_ns / 1e6);
    fprintf(stderr,
            "shaping %s lang %s: clusters %ld (fallback %ld), fontconfig queries %ld (%.2f ms, %ld found none), segments %ld, "
            "glyphs %ld in %ld elements and %ld requests; colour %ld, squeezed %ld, spaces joined %ld; uploaded %d; shape %.2f ms, raster %.2f ms, draw %.2f ms\n",
            shaping ? "on" : "off", lang_name ? lang_name : "-", st.clusters, st.fallback_clusters, st.fc_queries, st.fc_ns / 1e6,
            st.fc_failed, st.segments, st.glyphs, st.elements, st.requests, st.colour, st.squeezed, st.joined, uploaded, st.shape_ns / 1e6, st.raster_ns / 1e6,
            st.draw_ns / 1e6);
}

/* PROBE_SHOT=FILE writes the pixmap, as a PPM, when the program ends. */
static void shot(void) {
    const char *path = getenv("PROBE_SHOT");
    if (!path || !conn) return;
    xcb_get_image_reply_t *r = xcb_get_image_reply(
        conn, xcb_get_image(conn, XCB_IMAGE_FORMAT_Z_PIXMAP, pixmap, 0, 0, (uint16_t) (cols * cw), (uint16_t) (rows * ch), ~0u), NULL);
    if (!r) return;
    FILE *o = fopen(path, "wb");
    if (o) {
        const uint8_t *d = xcb_get_image_data(r);
        fprintf(o, "P6\n%d %d\n255\n", cols * cw, rows * ch);
        for (int i = 0; i < cols * cw * rows * ch; i++) {
            uint8_t px[3] = {d[i * 4 + 2], d[i * 4 + 1], d[i * 4]};
            fwrite(px, 1, 3, o);
        }
        fclose(o);
    }
    free(r);
}

static void at_exit(void) {
    stats();
    shot();
}

geng_cancel probe_x_draw(void *list, geng_wait *wait) {
    double t0 = ns();
    geng_bytes *b = list;
    const uint8_t *p = b->data, *end = b->data + b->length;
    int first = rows, last = -1;
    while (p < end) {
        if (p[0] == 1) {
            int top = (p[1] << 8) | p[2], bottom = (p[3] << 8) | p[4], k = (int16_t) ((p[5] << 8) | p[6]);
            xcb_copy_area(conn, pixmap, pixmap, gc, 0, (int16_t) ((top + k) * ch), 0, (int16_t) (top * ch),
                          (uint16_t) (cols * cw), (uint16_t) ((bottom - top + 1) * ch));
            if (top < first) first = top;
            if (bottom > last) last = bottom;
            p += 7;
        } else {
            int y = (p[1] << 8) | p[2], x = (p[3] << 8) | p[4], n = (p[5] << 8) | p[6];
            const uint8_t *cell = p + 7, *q = cell;
            for (int i = 0; i < n; i++) q += 3 + 3 * (q[0] & 63);
            int style0 = (cell[1] << 8) | cell[2];
            xcb_rectangle_t r = {(int16_t) (x * cw), (int16_t) (y * ch), (uint16_t) (n * cw), (uint16_t) ch};
            xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(bg_of(style0)), 1, &r);
            draw_run(y, x, n, cell);
            flush_placed();
            if (y < first) first = y;
            if (y > last) last = y;
            p = q;
        }
    }
    if (last >= first)
        xcb_copy_area(conn, pixmap, window, gc, 0, (int16_t) (first * ch), 0, (int16_t) (first * ch), (uint16_t) (cols * cw),
                      (uint16_t) ((last - first + 1) * ch));
    xcb_flush(conn);
    drain();
    st.draw_ns += ns() - t0;
    if (key_at > 0 && last >= first) {
        double d = ns() - key_at;
        st.key_frames++;
        st.key_sum_ns += d;
        if (d > st.key_max_ns) st.key_max_ns = d;
        key_at = 0;
    }
    geng_succeed(wait, geng_slot_I4(uploaded));
    return (geng_cancel) {0};
}

geng_cancel probe_x_open(int32_t c, int32_t r, int32_t points, geng_wait *wait) {
    cols = c;
    rows = r;
    points0 = points;
    const char *s = getenv("PROBE_SHAPE");
    shaping = !(s && strcmp(s, "0") == 0);
    lang_name = getenv("PROBE_LANG");
    if (lang_name) language = hb_language_from_string(lang_name, -1);
    hbuf = hb_buffer_create();
    char *file = font_file(getenv("PROBE_FONT") ? getenv("PROBE_FONT") : "DejaVu Sans Mono");
    if (file == NULL || FT_Init_FreeType(&library) != 0 || load_face(file, 0) != 0) {
        geng_succeed(wait, geng_slot_I4(-1));
        return (geng_cancel) {0};
    }
    FT_Face face = faces[0].ft;
    cw = (int) (face->size->metrics.max_advance >> 6);
    ch = (int) (face->size->metrics.height >> 6);
    ascent = (int) (face->size->metrics.ascender >> 6);
    atexit(at_exit);

    conn = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(conn)) {
        geng_succeed(wait, geng_slot_I4(-2));
        return (geng_cancel) {0};
    }
    xcb_screen_t *screen = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    const xcb_render_query_pict_formats_reply_t *formats = xcb_render_util_query_formats(conn);
    xcb_render_pictforminfo_t *a8 = xcb_render_util_find_standard_format(formats, XCB_PICT_STANDARD_A_8);
    xcb_render_pictvisual_t *visual = xcb_render_util_find_visual_format(formats, screen->root_visual);
    xcb_render_pictforminfo_t *a32 = xcb_render_util_find_standard_format(formats, XCB_PICT_STANDARD_ARGB_32);
    if (a32 != NULL) argb32 = a32->id;
    if (a8 == NULL || visual == NULL || a32 == NULL) {
        geng_succeed(wait, geng_slot_I4(-3));
        return (geng_cancel) {0};
    }
    int w = cols * cw, h = rows * ch;
    window = xcb_generate_id(conn);
    uint32_t values[2] = {screen->black_pixel, XCB_EVENT_MASK_EXPOSURE | XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_FOCUS_CHANGE};
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, screen->root, 0, 0, (uint16_t) w, (uint16_t) h, 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual, XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK, values);
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_NAME, XCB_ATOM_STRING, 8, 14, "visiterm-probe");
    key_setup();
    pixmap = xcb_generate_id(conn);
    xcb_create_pixmap(conn, screen->root_depth, pixmap, window, (uint16_t) w, (uint16_t) h);
    gc = xcb_generate_id(conn);
    uint32_t no_exposures = 0;
    xcb_create_gc(conn, gc, pixmap, XCB_GC_GRAPHICS_EXPOSURES, &no_exposures);
    target = xcb_generate_id(conn);
    xcb_render_create_picture(conn, target, pixmap, visual->format, 0, NULL);
    glyphs = xcb_generate_id(conn);
    xcb_render_create_glyph_set(conn, glyphs, a8->id);
    xcb_rectangle_t all = {0, 0, (uint16_t) w, (uint16_t) h};
    xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(0), 1, &all);
    xcb_map_window(conn, window);
    xcb_flush(conn);
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* The loop's wait on the X connection (docs/phase2-window.md §12). xcb reads
 * the socket in its own calls (a flush, a reply) and queues what events it
 * finds, so the descriptor can be quiet while events wait: `drain` reads
 * what is queued and what the socket has, `seen` keeps the count between a
 * drain in `probe_x_draw` and the next `probe_x_take`, and only when both
 * are empty does the loop wait on the descriptor. An expose copies the
 * pixmap's rectangle to the window; no other event means anything yet.
 *
 * `probe_x_events` answers only that events are there, and takes none:
 * `Task.race` drops a losing branch's answer when two branches answer in
 * one round (§12), so a branch that took the events could lose them.
 * `probe_x_take`, after the race, takes them. */
static int seen;

/* Keys (docs/phase2-window.md §14): xkbcommon's keymap and state, read from
 * the server's XKB and kept in step by its StateNotify events. Each key
 * press is a record for Geng, which decides what it sends: its keysym (4
 * bytes, big-endian), its modifiers (1: shift 1, ctrl 2, alt 4, super 8),
 * and its text (a byte of length, then UTF-8). `key_at` is when the first
 * key not yet shown in a frame came, for the key-to-frame time. */
static struct xkb_context *xctx;
static struct xkb_keymap *keymap;
static struct xkb_state *kstate;
static int32_t kbd = -1;
static uint8_t xkb_event;
static uint8_t keybuf[16384];
static int keylen;

static void key_setup(void) {
    double t0 = ns();
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
    st.keymap_ns += ns() - t0;
}

static void key_press(uint8_t keycode) {
    if (!kstate) return;
    double t0 = ns();
    xkb_keysym_t sym = xkb_state_key_get_one_sym(kstate, keycode);
    char text[64];
    int n = xkb_state_key_get_utf8(kstate, keycode, text, sizeof text);
    if (n < 0) n = 0;
    if (n > 63) n = 63;
    int mods = (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_SHIFT, XKB_STATE_MODS_EFFECTIVE) > 0 ? 1 : 0) |
               (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_CTRL, XKB_STATE_MODS_EFFECTIVE) > 0 ? 2 : 0) |
               (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_ALT, XKB_STATE_MODS_EFFECTIVE) > 0 ? 4 : 0) |
               (xkb_state_mod_name_is_active(kstate, XKB_MOD_NAME_LOGO, XKB_STATE_MODS_EFFECTIVE) > 0 ? 8 : 0);
    st.xkb_ns += ns() - t0;
    st.keys++;
    if (keylen + 6 + n > (int) sizeof keybuf) return;
    keybuf[keylen++] = (uint8_t) (sym >> 24);
    keybuf[keylen++] = (uint8_t) (sym >> 16);
    keybuf[keylen++] = (uint8_t) (sym >> 8);
    keybuf[keylen++] = (uint8_t) sym;
    keybuf[keylen++] = (uint8_t) mods;
    keybuf[keylen++] = (uint8_t) n;
    memcpy(keybuf + keylen, text, (size_t) n);
    keylen += n;
    if (key_at == 0) key_at = ns();
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

/* The key records since the last call (see above). */
geng_cancel probe_x_keys(geng_wait *wait) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b + (size_t) keylen, GENG_HEADER_BYTES(sizeof *b + (size_t) keylen));
    b->length = keylen;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    memcpy(b->data, keybuf, (size_t) keylen);
    keylen = 0;
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}

static void drain(void) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(conn)) != NULL) {
        if (xkb_event && (e->response_type & 0x7f) == xkb_event) xkb_event_in(e);
        else if ((e->response_type & 0x7f) == XCB_KEY_PRESS) key_press(((xcb_key_press_event_t *) e)->detail);
        else if ((e->response_type & 0x7f) == XCB_EXPOSE) {
            xcb_expose_event_t *x = (xcb_expose_event_t *) e;
            xcb_copy_area(conn, pixmap, window, gc, (int16_t) x->x, (int16_t) x->y, (int16_t) x->x, (int16_t) x->y,
                          x->width, x->height);
            xcb_flush(conn);
        }
        seen++;
        free(e);
    }
}

typedef struct xwait {
    geng_wait *wait;
    geng_io *io;
} xwait;

#define XWAIT_HEADER (GENG_HEADER_WORDS(xwait) | GENG_HEADER_POINTER(xwait, wait) | GENG_HEADER_POINTER(xwait, io))

/* Answers 1 once events are there, or -1 once the connection has failed. */
static int answer(geng_wait *wait) {
    if (xcb_connection_has_error(conn)) {
        geng_succeed(wait, geng_slot_I4(-1));
        return 1;
    }
    drain();
    if (seen == 0) return 0;
    geng_succeed(wait, geng_slot_I4(1));
    return 1;
}

/* Takes the events seen since the last take: answers how many. */
geng_cancel probe_x_take(geng_wait *wait) {
    drain();
    int n = seen;
    seen = 0;
    geng_succeed(wait, geng_slot_I4(n));
    return (geng_cancel) {0};
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

geng_cancel probe_x_events(geng_wait *wait) {
    if (answer(wait)) return (geng_cancel) {0};
    xwait *w = geng_alloc(sizeof *w, XWAIT_HEADER);
    *w = (xwait) {.wait = wait, .io = NULL};
    w->io = geng_io_wait(xcb_get_file_descriptor(conn), POLLIN, x_ready, w);
    geng_write_barrier(w, &w->io, w->io);
    return (geng_cancel) {x_stop, w};
}

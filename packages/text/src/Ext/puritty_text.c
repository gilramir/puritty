/* puritty's text renderer (docs/windows.md V52; docs/renderer.md, V34-V43):
 * the drawing both platforms' windows share, moved here from packages/x11.
 * include/puritty_text.h says what it gives and what a platform gives it.
 *
 * Drawing, S§6.2's way:
 *   - everything is drawn into a target the size of the screen's cells,
 *     which the platform keeps (X11's retained pixmap, Windows' bitmap),
 *     and the platform shows the rows a frame touched;
 *   - a scroll record is one move within the target, up or down;
 *   - a run is a fill for each stretch of one background, its glyphs, and
 *     its lines (underlines, strikethrough, overline, the cursor's shape) as
 *     fills;
 *   - a run's clusters are shaped by HarfBuzz in the face that has them
 *     (V24, V34): the primary font in the weight and slant the style asks
 *     for, else the first loaded face with the whole cluster, else the one
 *     the platform finds (V26); a glyph is rasterised by FreeType and given
 *     to the platform to keep the first time it is drawn, a colour one as
 *     an ARGB picture (§13.10);
 *   - past `glyph_cap` bytes kept, the glyphs are begun again (V37). The
 *     target keeps what was drawn with the old ones, so nothing is redrawn:
 *     glyphs are kept again as frames need them.
 *
 * Styles come resolved in each frame's style records (V35) and are kept
 * only for that frame's runs. Bold and italic come from the primary font's
 * own faces; a fallback face draws them as its regular (synthesising them
 * is docs/renderer.md §R6 step 5's), and blinking text is drawn steady. */
#define _GNU_SOURCE
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_OUTLINE_H
#include FT_BITMAP_H
#include <hb-ft.h>
#include <hb.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

#include "puritty_text.h"

static char *copy(const char *s) {
    size_t n = strlen(s) + 1;
    char *d = malloc(n);
    if (d) memcpy(d, s, n);
    return d;
}

/* The cell, and where a line sits in it: the underline's top below the
 * baseline and its thickness, the strikethrough's top above it. */
int pt_cw, pt_ch, pt_ascent;
static int ul_below, line_thick, strike_above;
/* The screen in cells, as the display list last said. */
int pt_cols, pt_rows;
int pt_verbose;
static int have_target;
static long glyph_bytes, glyph_cap, resets;

/* A style's record by its id; from 65536 on, the same style selected
 * (docs/phase3-select.md §14): its colours swapped, made when a selected
 * cell is drawn in it. */
static uint32_t style_fg[131072], style_bg[131072], style_ulc[131072];
static uint8_t style_flags[131072], style_ul[131072];
/* The cells the frame's highlight record covers, y * pt_cols + x, both
 * included; -1 when it has none. */
static int sel_from = -1, sel_to = -1;

/* The style a cell is drawn in: its own, or its selected copy when the
 * frame's highlight covers it. A cursor's style (0x8000 and up) is the
 * cursor's whatever the highlight. */
static int cell_style(int style, int y, int x) {
    int i = y * pt_cols + x;
    if (sel_from < 0 || i < sel_from || i > sel_to || style >= 0x8000) return style;
    int s = 65536 + style;
    style_fg[s] = style_bg[style];
    style_bg[s] = style_fg[style];
    style_ulc[s] = style_ulc[style] == style_fg[style] ? style_bg[style] : style_ulc[style];
    style_flags[s] = style_flags[style];
    style_ul[s] = style_ul[style];
    return s;
}

uint32_t pt_default_bg(void) { return style_bg[0]; }

static struct {
    long clusters, fallback_clusters, fc_queries, fc_failed, segments, glyphs, uploaded, colour, squeezed, clipped, boxes, frames;
    double shape_ns, raster_ns, draw_ns, fc_ns;
} st;

static double ns(void) {
#ifdef _WIN32
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (double) t.QuadPart * 1e9 / (double) f.QuadPart;
#else
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e9 + t.tv_nsec;
#endif
}

static void fill(uint32_t rgb, int x, int y, int w, int h) {
    if (w <= 0 || h <= 0) return;
    pt_fill(rgb, x, y, w, h);
}

/* FONTS */

#define FACES 32
/* A glyph's key in its face: its index, and the bits of the form it was
 * uploaded in (shifted 1, squeezed 2, synthetic bold 4, synthetic italic
 * 8, from bit 16); a glyph set id is the face above it. */
#define KEYS (1 << 20)
/* The last face's number is the box drawing's (V41), whose glyphs the C
 * draws itself; it is no font. */
#define BOX (FACES - 1)
typedef struct ColourGlyph {
    uint32_t g;
    int box;
    void *picture;
    int w, h;
    struct ColourGlyph *next;
} ColourGlyph;

typedef struct {
    FT_Face ft;
    hb_font_t *hb;
    char *file;
    int index;
    double scale;
    int colour;        /* a face of colour glyphs (CBDT or COLR), drawn as pictures */
    int own;           /* what the face is of itself: bold 1, italic 2 */
    int primary;       /* one of the primary font's faces */
    uint8_t *uploaded; /* a bit a glyph index and form */
    int16_t *advance;  /* the x_off each glyph was uploaded with */
    int16_t *ink;      /* each glyph's bitmap: left of its origin, top above it, width, height */
    ColourGlyph *pictures;
} Face;

static FT_Library library;
static Face faces[FACES];
static int nfaces, points0, dpi0 = 96;
/* The primary font's faces: regular, bold, italic, bold italic. A font with
 * no face of its own for one gives its regular. */
static int primary[4];
static hb_language_t language;
static char *lang_name;
static hb_buffer_t *hbuf;

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

/* A face sized for `points0` at `dpi0` (V50): one of the primary font's at
 * that size, a fallback one so 水 fills two cells and its ink stays within
 * the primary cell, which the primary faces' metrics give. */
static void size_face(Face *F) {
    if (F->colour) {
        /* drawn at the cell's height and reduced into its box, as a
         * bitmap strike is */
        if (FT_IS_SCALABLE(F->ft)) FT_Set_Pixel_Sizes(F->ft, 0, (FT_UInt) (pt_ch > 0 ? pt_ch : 16));
        return;
    }
    F->scale = 1.0;
    FT_Set_Char_Size(F->ft, 0, points0 * 64, (FT_UInt) dpi0, (FT_UInt) dpi0);
    if (!F->primary) {
        FT_UInt gi = FT_Get_Char_Index(F->ft, 0x6C34);
        if (gi && FT_Load_Glyph(F->ft, gi, FT_LOAD_NO_HINTING) == 0) {
            double adv = F->ft->glyph->advance.x / 64.0;
            double top = F->ft->glyph->metrics.horiBearingY / 64.0;
            double bottom = F->ft->glyph->metrics.height / 64.0 - top;
            double sc = 2.0 * pt_cw / adv;
            if (top > 0 && pt_ascent / top < sc) sc = pt_ascent / top;
            if (bottom > 0 && (pt_ch - pt_ascent) / bottom < sc) sc = (pt_ch - pt_ascent) / bottom;
            F->scale = sc;
            FT_Set_Char_Size(F->ft, 0, (FT_F26Dot6) (points0 * 64 * sc + 0.5), (FT_UInt) dpi0, (FT_UInt) dpi0);
        }
    }
}

/* A face, loaded once. One of the primary font's keeps its size; a
 * fallback face with 水 is sized so 水 fills two cells and its ink stays
 * within the primary cell (§13.1). */
static int load_face(const char *file, int index, int is_primary) {
    for (int f = 0; f < nfaces; f++)
        if (faces[f].index == index && strcmp(faces[f].file, file) == 0) return f;
    if (nfaces == BOX) return -1;
    Face *F = &faces[nfaces];
    if (FT_New_Face(library, file, index, &F->ft) != 0) return -1;
    F->file = copy(file);
    F->index = index;
    F->scale = 1.0;
    /* a face of colour bitmaps (CBDT, Noto Color Emoji), or of colour
     * layers over outlines (COLR, Windows' Segoe UI Emoji), which FreeType
     * draws into a BGRA bitmap itself */
    F->colour = FT_HAS_COLOR(F->ft) && (FT_IS_SCALABLE(F->ft) || F->ft->num_fixed_sizes > 0);
    F->pictures = NULL;
    if (F->colour && !FT_IS_SCALABLE(F->ft)) FT_Select_Size(F->ft, 0);
    F->primary = is_primary;
    size_face(F);
    F->hb = hb_ft_font_create_referenced(F->ft);
    F->uploaded = calloc(KEYS / 8, 1);
    F->advance = calloc(KEYS, sizeof *F->advance);
    F->ink = calloc((size_t) KEYS * 4, sizeof *F->ink);
    if (pt_verbose) fprintf(stderr, "face %d: %s#%d scale %.3f\n", nfaces, F->file, index, F->scale);
    return nfaces++;
}

/* A cache from a cluster's first code point to the face the platform
 * gave it, so that the platform is asked once a code point; -1 where it
 * found none. */
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
    int face = -1;
    int index = 0;
    char *file = pt_fallback_file(cps, n, colour, lang_name, &index);
    if (file) {
        int f = load_face(file, index, 0);
        if (f >= 0 && covers(f, cps, n)) face = f;
        /* No colour face has it: the text face that does. */
        if (face < 0 && colour)
            for (int g = 0; g < nfaces; g++)
                if (covers(g, cps, n)) { face = g; break; }
        free(file);
    }
    if (face < 0) st.fc_failed++;
    fcache[h].cp = key + 1;
    fcache[h].face = face;
    st.fc_ns += ns() - t0;
    return face;
}

/* GLYPHS */

/* The platform's glyphs forgotten and begun again (V37), every face's
 * record of what it uploaded forgotten, and its colour pictures freed. */
static uint8_t box_uploaded[512];

static void reset_glyphs(void) {
    pt_glyphs_reset();
    for (int f = 0; f < nfaces; f++) {
        memset(faces[f].uploaded, 0, KEYS / 8);
        for (ColourGlyph *c = faces[f].pictures, *next; c; c = next) {
            next = c->next;
            if (c->picture) pt_picture_free(c->picture);
            free(c);
        }
        faces[f].pictures = NULL;
    }
    memset(box_uploaded, 0, sizeof box_uploaded);
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
    /* A synthetic form is made from the outline, never an embedded bitmap,
     * which can be neither slanted nor widened. */
    FT_Load_Glyph(F->ft, g, (transformed ? FT_LOAD_NO_HINTING : 0) | ((synth & 1) ? 0 : FT_LOAD_RENDER) | (synth ? FT_LOAD_NO_BITMAP : 0));
    if (synth & 1) {
        FT_GlyphSlot slot = F->ft->glyph;
        if (slot->format == FT_GLYPH_FORMAT_OUTLINE)
            FT_Outline_EmboldenXY(&slot->outline, FT_MulFix(F->ft->units_per_EM, F->ft->size->metrics.y_scale) / 24, 0);
        FT_Render_Glyph(slot, FT_RENDER_MODE_NORMAL);
    }
    if (transformed) FT_Set_Transform(F->ft, NULL, NULL);
    FT_Bitmap *b = &F->ft->glyph->bitmap;
    /* An embedded bitmap may be 1 bit a pixel (AR PL UMing's strikes, the
     * Han that Debian and Mint fall back to, §R18): converted to a byte a
     * pixel, its levels spread to 0..255, as the glyph set takes them. */
    FT_Bitmap grey;
    FT_Bitmap_Init(&grey);
    if (b->pixel_mode != FT_PIXEL_MODE_GRAY && FT_Bitmap_Convert(library, b, &grey, 1) == 0) {
        int levels = grey.num_grays > 1 ? grey.num_grays - 1 : 1;
        for (unsigned y = 0; y < grey.rows; y++)
            for (unsigned x = 0; x < grey.width; x++) {
                unsigned char *v = grey.buffer + y * (unsigned) grey.pitch + x;
                *v = (unsigned char) (*v * 255 / levels);
            }
        b = &grey;
    }
    int stride = ((int) b->width + 3) & ~3;
    size_t size = (size_t) stride * b->rows;
    uint8_t *data = calloc(size > 0 ? size : 4, 1);
    for (unsigned y = 0; y < b->rows; y++) memcpy(data + y * stride, b->buffer + y * b->pitch, b->width);
    PtGlyph glyph = {.width = (int) b->width, .height = (int) b->rows, .stride = stride,
                     .left = F->ft->glyph->bitmap_left + shift, .top = F->ft->glyph->bitmap_top, .advance = advance, .data = data};
    pt_glyph_add(id, &glyph);
    FT_Bitmap_Done(library, &grey);
    int16_t *ink = F->ink + (size_t) k * 4;
    ink[0] = (int16_t) glyph.left;
    ink[1] = (int16_t) glyph.top;
    ink[2] = (int16_t) glyph.width;
    ink[3] = (int16_t) glyph.height;
    glyph_bytes += (long) size + 28;
    free(data);
    st.raster_ns += ns() - t0;
    return id;
}

/* The glyphs a run draws, in order, before they go out as requests. */
static PtPlaced placed[8192];
static int nplaced;

/* What a face draws of a style that it is not of itself: bold 1, italic 2
 * (C§9 rule 6). */
static int synth_for(int f, int style) {
    int flags = style_flags[style];
    return (((flags & 1) ? 1 : 0) | ((flags & 4) ? 2 : 0)) & ~faces[f].own;
}

/* INK (V40, renderer.md §R15)
 *
 * The pixels a cluster's glyphs cover, gathered as they are placed, and
 * for each of its cells the edges they cross: 1 left, 2 right, 4 up, 8
 * down. A frame answers them for the cells it drew, as records of the
 * row and column in 2 bytes each and the edges in 1, and the view redraws
 * a cell whose ink reaches into one it redraws. */
static struct { int any, x0, y0, x1, y1; } gbox;
static uint8_t *inkbuf;
static int inklen, inkcap;

/* A cluster's ink may reach anywhere in its word, which the view redraws
whole, and a cell past it on each side and a row above and below: what
reaches further (a glyph far wider than its cells) is clipped there, so
that the view's one cell of reach holds. */
static PtRect clips[8192];
static int nclips;

static void ink_cells(int y, int cell, int n, int w0, int w1, int first) {
    if (!gbox.any) return;
    int ax0 = (w0 - 1) * pt_cw, ax1 = (w1 + 1) * pt_cw, ay0 = (y - 1) * pt_ch, ay1 = (y + 2) * pt_ch;
    if ((gbox.x0 < ax0 || gbox.x1 > ax1 || gbox.y0 < ay0 || gbox.y1 > ay1) && nclips < 8192) {
        clips[nclips] = (PtRect) {ax0, ay0, ax1 - ax0, ay1 - ay0};
        for (int k = first; k < nplaced; k++) placed[k].clip = nclips;
        nclips++;
        st.clipped++;
        if (gbox.x0 < ax0) gbox.x0 = ax0;
        if (gbox.x1 > ax1) gbox.x1 = ax1;
        if (gbox.y0 < ay0) gbox.y0 = ay0;
        if (gbox.y1 > ay1) gbox.y1 = ay1;
    }
    for (int i = 0; i < n; i++) {
        int cx0 = (cell + i) * pt_cw, cx1 = cx0 + pt_cw, cy0 = y * pt_ch, cy1 = cy0 + pt_ch;
        int bits = (gbox.x0 < cx0 ? 1 : 0) | (gbox.x1 > cx1 ? 2 : 0) | (gbox.y0 < cy0 ? 4 : 0) | (gbox.y1 > cy1 ? 8 : 0);
        if (!bits) continue;
        if (inklen + 5 > inkcap) {
            inkcap = inkcap ? inkcap * 2 : 4096;
            inkbuf = realloc(inkbuf, (size_t) inkcap);
        }
        uint8_t *r = inkbuf + inklen;
        r[0] = (uint8_t) (y >> 8);
        r[1] = (uint8_t) y;
        r[2] = (uint8_t) ((cell + i) >> 8);
        r[3] = (uint8_t) (cell + i);
        r[4] = (uint8_t) bits;
        inklen += 5;
    }
    gbox.any = 0;
}

static void place(int f, uint32_t g, int x, int y, int style, int advance, int shift, FT_Fixed squeeze) {
    if (nplaced == 8192) return;
    uint32_t id = upload(f, g, advance, shift, squeeze, synth_for(f, style));
    const int16_t *ink = faces[f].ink + (size_t) (id & (KEYS - 1)) * 4;
    if (ink[2] > 0 && ink[3] > 0) {
        int x0 = x + ink[0], y0 = y - ink[1], x1 = x0 + ink[2], y1 = y0 + ink[3];
        if (!gbox.any) {
            gbox.any = 1;
            gbox.x0 = x0, gbox.y0 = y0, gbox.x1 = x1, gbox.y1 = y1;
        } else {
            if (x0 < gbox.x0) gbox.x0 = x0;
            if (y0 < gbox.y0) gbox.y0 = y0;
            if (x1 > gbox.x1) gbox.x1 = x1;
            if (y1 > gbox.y1) gbox.y1 = y1;
        }
    }
    placed[nplaced++] = (PtPlaced) {id, x, y, style_fg[style], faces[f].advance[id & (KEYS - 1)], -1};
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
    if ((double) pt_ch / b->rows < sc) sc = (double) pt_ch / b->rows;
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
    c->picture = pt_picture_add(out, w, h);
    c->w = w;
    c->h = h;
    free(out);
    st.uploaded++;
    glyph_bytes += (long) w * h * 4;
    st.raster_ns += ns() - t0;
    return c;
}

/* The glyphs placed, drawn by the platform. */
static void flush_placed(void) {
    st.glyphs += nplaced;
    if (nplaced) pt_glyphs_draw(placed, nplaced, clips);
    nplaced = 0;
    nclips = 0;
}

/* A cluster: its cell, its width in cells, its style, its code points, its
 * face, and the word it is in, the cells from w0 to w1 with no blank. */
typedef struct { int cell, width, style, n; const uint32_t *cps; int face, w0, w1; } Cluster;

/* A segment of clusters in one face, shaped as one run, each code point's
 * cluster its cell, so glyphs go back to cells by the core's widths. */
static void shape_segment(const Cluster *cl, int n, int x0, int y) {
    int f = cl[0].face < 0 ? 0 : cl[0].face;
    double t0 = ns();
    hb_buffer_clear_contents(hbuf);
    /* hb_buffer_add asks for this, which the adds of text set themselves;
     * HarfBuzz built with its assertions (Windows', WS14) stops without it */
    hb_buffer_set_content_type(hbuf, HB_BUFFER_CONTENT_TYPE_UNICODE);
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
        int first = nplaced;
        int adv = 0;
        while (e < gn && gi[e].cluster == c) adv += gp[e++].x_advance;
        const Cluster *C = &cl[c];
        /* The shaper may merge clusters the core gave cells of their own,
         * as it does a Devanagari conjunct and its vowel sign, or a flag's
         * two regional indicators (§R13): the glyphs then take the cells of
         * every cluster merged, up to the next one's. */
        unsigned next = e < gn ? gi[e].cluster : (unsigned) n;
        const Cluster *L = next > c + 1 ? &cl[next - 1] : C;
        int box = (L->cell + L->width - C->cell) * pt_cw;
        if (box < C->width * pt_cw) box = C->width * pt_cw;
        if (faces[f].colour) {
            /* Placed by its cells, centred: the strike's advances are its
             * own size's, not the cell's. */
            for (unsigned k = g; k < e; k++) {
                ColourGlyph *P = colour_glyph(f, gi[k].codepoint, box);
                if (!P->picture) continue;
                pt_picture_draw(P->picture, (x0 + C->cell) * pt_cw + (box - P->w) / 2, y * pt_ch + (pt_ch - P->h) / 2, P->w, P->h);
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
            int x = (x0 + C->cell) * pt_cw + pad + ((pen + gp[k].x_offset) >> 6);
            int yy = y * pt_ch + pt_ascent - (gp[k].y_offset >> 6);
            int a = k + 1 < e ? 0 : box - pad - (pen >> 6);
            if (k + 1 < e) a = (gp[k].x_advance + gp[k + 1].x_offset - gp[k].x_offset) >> 6;
            if (e - g == 1 && pad > 0 && gp[k].x_offset == 0)
                place(f, gi[k].codepoint, x - pad, yy, C->style, box, pad, 0);
            else if (e - g == 1 && box == pt_cw && (adv >> 6) > pt_cw && gp[k].x_offset == 0) {
                place(f, gi[k].codepoint, x, yy, C->style, pt_cw, 0, (FT_Fixed) ((double) pt_cw * 64 / adv * 65536));
                st.squeezed++;
            } else
                place(f, gi[k].codepoint, x, yy, C->style, a, 0, 0);
            pen += gp[k].x_advance;
        }
        ink_cells(y, x0 + C->cell, box / pt_cw, x0 + C->w0, x0 + C->w1, first);
        g = e;
    }
}

/* The primary face a style asks for: bold 1 and italic 4 of its flags. */
static int primary_for(int style) {
    int flags = style_flags[style];
    return primary[((flags & 1) ? 1 : 0) | ((flags & 4) ? 2 : 0)];
}

/* BOX DRAWING (V41, renderer.md §R17)
 *
 * U+2500 to U+259F are drawn here, not by a font: each is rasterised once
 * into a bitmap of its cells and uploaded to the glyph set as any glyph is,
 * so it is drawn in its style's colour by the same requests. Lines lie on
 * whole pixels at the cell's centre and run to its edges, so they join
 * whatever the font; arcs and diagonals are anti-aliased; shades are flat
 * alpha. Nothing reaches past its cells, so a box glyph has no ink to
 * answer. */

/* Arms of U+2500 to U+257F, up, right, down and left: 0 none, 1 light, 2
 * heavy, 3 double; a letter for those drawn otherwise: 'h' and 'v' dashed
 * (light, then 'H' and 'V' heavy), 'a' an arc, 'd' a diagonal. */
static const char *const box_arms[128] = {
    "0101", "0202", "1010", "2020", "h3", "H3", "v3", "V3", "h4", "H4", "v4", "V4",
    "0110", "0210", "0120", "0220", "0011", "0012", "0021", "0022",
    "1100", "1200", "2100", "2200", "1001", "1002", "2001", "2002",
    "1110", "1210", "2110", "1120", "2120", "2210", "1220", "2220",
    "1011", "1012", "2011", "1021", "2021", "2012", "1022", "2022",
    "0111", "0112", "0211", "0212", "0121", "0122", "0221", "0222",
    "1101", "1102", "1201", "1202", "2101", "2102", "2201", "2202",
    "1111", "1112", "1211", "1212", "2111", "1121", "2121", "2112", "2211", "1122", "1221",
    "2212", "1222", "2122", "2221", "2222",
    "h2", "H2", "v2", "V2",
    "0303", "3030", "0310", "0130", "0330", "0013", "0031", "0033",
    "1300", "3100", "3300", "1003", "3001", "3003",
    "1310", "3130", "3330", "1013", "3031", "3033",
    "0313", "0131", "0333", "1303", "3101", "3303", "1313", "3131", "3333",
    "a", "a", "a", "a", "d", "d", "d",
    "0001", "1000", "0100", "0010", "0002", "2000", "0200", "0020",
    "0201", "1020", "0102", "2010",
};

static uint8_t *canvas;
static int canvas_w, canvas_h;

static void canvas_rect(int x, int y, int w, int h, int alpha) {
    for (int j = y < 0 ? 0 : y; j < y + h && j < canvas_h; j++)
        for (int i = x < 0 ? 0 : x; i < x + w && i < canvas_w; i++)
            if (canvas[j * canvas_w + i] < alpha) canvas[j * canvas_w + i] = (uint8_t) alpha;
}

/* A pixel's coverage by a band of width `t` around a distance of 0. */
static int cover(double d, double t) {
    double c = t / 2 + 0.5 - (d < 0 ? -d : d);
    return c <= 0 ? 0 : c >= 1 ? 255 : (int) (c * 255 + 0.5);
}

static void canvas_pixel(int i, int j, int alpha) {
    if (i >= 0 && i < canvas_w && j >= 0 && j < canvas_h && canvas[j * canvas_w + i] < alpha)
        canvas[j * canvas_w + i] = (uint8_t) alpha;
}

static void draw_lines_box(const char *a, int w, int h, int t, int heavy) {
    int arm[4];
    for (int k = 0; k < 4; k++) arm[k] = a[k] - '0';
    int up = arm[0], right = arm[1], down = arm[2], left = arm[3];
    int th[4] = {0, t, heavy, t};
    int cx = (w - t) / 2, cy = (h - t) / 2;
    /* The widest arm across each way decides where the others stop, so a
     * corner is filled. */
    int hmax = th[left] > th[right] ? th[left] : th[right], vmax = th[up] > th[down] ? th[up] : th[down];
    int xL = cx - t, xR = cx + t, yT = cy - t, yB = cy + t;
    int dv = up == 3 || down == 3, dh = left == 3 || right == 3;
    /* Light and heavy arms. */
    for (int k = 0; k < 4; k++) {
        if (arm[k] != 1 && arm[k] != 2) continue;
        int wt = th[arm[k]];
        if (k == 0 || k == 2) {
            int x0 = (w - wt) / 2;
            int across = hmax > wt ? hmax : wt, c0 = (h - across) / 2, c1 = c0 + across;
            if (dh) c0 = yT, c1 = yB + t;
            if (k == 0) canvas_rect(x0, 0, wt, c1, 255);
            else canvas_rect(x0, c0, wt, h - c0, 255);
        } else {
            int y0 = (h - wt) / 2;
            int across = vmax > wt ? vmax : wt, c0 = (w - across) / 2, c1 = c0 + across;
            if (dv) c0 = xL, c1 = xR + t;
            if (k == 3) canvas_rect(0, y0, c1, wt, 255);
            else canvas_rect(c0, y0, w - c0, wt, 255);
        }
    }
    /* Double arms: two lines, each stopping where it meets its corner. */
    int sv = up == 1 || down == 1, sh = left == 1 || right == 1;
    if (up == 3) {
        int e1 = left == 3 ? yT + t : right == 3 ? yB + t : sh ? cy : yB + t;
        int e2 = right == 3 ? yT + t : left == 3 ? yB + t : sh ? cy : yB + t;
        canvas_rect(xL, 0, t, e1, 255);
        canvas_rect(xR, 0, t, e2, 255);
    }
    if (down == 3) {
        int s1 = left == 3 ? yB : right == 3 ? yT : sh ? cy : yT;
        int s2 = right == 3 ? yB : left == 3 ? yT : sh ? cy : yT;
        canvas_rect(xL, s1, t, h - s1, 255);
        canvas_rect(xR, s2, t, h - s2, 255);
    }
    if (left == 3) {
        int e1 = up == 3 ? xL + t : down == 3 ? xR + t : sv ? cx : xR + t;
        int e2 = down == 3 ? xL + t : up == 3 ? xR + t : sv ? cx : xR + t;
        canvas_rect(0, yT, e1, t, 255);
        canvas_rect(0, yB, e2, t, 255);
    }
    if (right == 3) {
        int s1 = up == 3 ? xR : down == 3 ? xL : sv ? cx : xL;
        int s2 = down == 3 ? xR : up == 3 ? xL : sv ? cx : xL;
        canvas_rect(s1, yT, w - s1, t, 255);
        canvas_rect(s2, yB, w - s2, t, 255);
    }
}

static void draw_box(uint32_t cp, int w, int h) {
    int t = (w + 4) / 9 < 1 ? 1 : (w + 4) / 9;
    int heavy = 2 * t;
    if (cp >= 0x2580) {
        int k = (int) (cp - 0x2580);
        int hw = w / 2, hh = h / 2;
        switch (k) {
        case 0x00: canvas_rect(0, 0, w, hh, 255); break;
        case 0x10: canvas_rect(hw, 0, w - hw, h, 255); break;
        case 0x11: canvas_rect(0, 0, w, h, 64); break;
        case 0x12: canvas_rect(0, 0, w, h, 128); break;
        case 0x13: canvas_rect(0, 0, w, h, 192); break;
        case 0x14: canvas_rect(0, 0, w, (h + 4) / 8, 255); break;
        case 0x15: canvas_rect(w - (w + 4) / 8, 0, (w + 4) / 8, h, 255); break;
        default:
            if (k >= 0x01 && k <= 0x08) {
                int eh = (h * k + 4) / 8;
                canvas_rect(0, h - eh, w, eh, 255);
            } else if (k >= 0x09 && k <= 0x0F) {
                int ew = (w * (0x10 - k) + 4) / 8;
                canvas_rect(0, 0, ew, h, 255);
            } else {
                /* Quadrants: upper left 1, upper right 2, lower left 4,
                 * lower right 8. */
                static const uint8_t quads[10] = {4, 8, 1, 1 | 4 | 8, 1 | 8, 1 | 2 | 4, 1 | 2 | 8, 2, 2 | 4, 2 | 4 | 8};
                int q = quads[k - 0x16];
                if (q & 1) canvas_rect(0, 0, hw, hh, 255);
                if (q & 2) canvas_rect(hw, 0, w - hw, hh, 255);
                if (q & 4) canvas_rect(0, hh, hw, h - hh, 255);
                if (q & 8) canvas_rect(hw, hh, w - hw, h - hh, 255);
            }
        }
        return;
    }
    const char *a = box_arms[cp - 0x2500];
    if (a[0] == 'h' || a[0] == 'H' || a[0] == 'v' || a[0] == 'V') {
        int n = a[1] - '0', wt = (a[0] == 'H' || a[0] == 'V') ? heavy : t;
        int vertical = a[0] == 'v' || a[0] == 'V';
        int len = vertical ? h : w;
        for (int k = 0; k < n; k++) {
            int s0 = len * k / n, s1 = len * (k + 1) / n, gap = (s1 - s0) / 3 > 0 ? (s1 - s0) / 3 : 1;
            int a0 = s0 + gap / 2, a1 = s1 - (gap - gap / 2);
            if (vertical) canvas_rect((w - wt) / 2, a0, wt, a1 - a0, 255);
            else canvas_rect(a0, (h - wt) / 2, a1 - a0, wt, 255);
        }
        return;
    }
    if (a[0] == 'a') {
        /* A quarter circle from the middle of one edge to the middle of
         * the next, joining the straight lines of its neighbours. */
        double lx = (w - t) / 2 + t / 2.0, ly = (h - t) / 2 + t / 2.0;
        double r = lx < ly ? lx : ly;
        int sx = cp == 0x256D || cp == 0x2570 ? 1 : -1, sy = cp == 0x256D || cp == 0x256E ? 1 : -1;
        double ox = lx + sx * r, oy = ly + sy * r;
        for (int j = 0; j < h; j++)
            for (int i = 0; i < w; i++) {
                double px = i + 0.5, py = j + 0.5;
                int in_x = sx > 0 ? px <= ox : px >= ox, in_y = sy > 0 ? py <= oy : py >= oy;
                if (in_x && in_y) canvas_pixel(i, j, cover(sqrt((px - ox) * (px - ox) + (py - oy) * (py - oy)) - r, t));
            }
        int x0 = (w - t) / 2, y0 = (h - t) / 2;
        int ry = (int) (oy + 0.5), rx = (int) (ox + 0.5);
        if (sy > 0) canvas_rect(x0, ry, t, h - ry, 255);
        else canvas_rect(x0, 0, t, ry, 255);
        if (sx > 0) canvas_rect(rx, y0, w - rx, t, 255);
        else canvas_rect(0, y0, rx, t, 255);
        return;
    }
    if (a[0] == 'd') {
        /* Corner to corner, so that a run of them joins across cells. */
        double len = sqrt((double) w * w + (double) h * h);
        for (int j = 0; j < h; j++)
            for (int i = 0; i < w; i++) {
                double px = i + 0.5, py = j + 0.5;
                if (cp != 0x2572) canvas_pixel(i, j, cover((px * h + py * w - (double) w * h) / len, t));
                if (cp != 0x2571) canvas_pixel(i, j, cover((px * h - py * w) / len, t));
            }
        return;
    }
    draw_lines_box(a, w, h, t, heavy);
}

/* Places a box-drawing character's glyph, rasterised and uploaded the
 * first time it is drawn at that width. */
static void place_box(uint32_t cp, int cell, int y, int cells, int style) {
    if (nplaced == 8192) return;
    uint32_t k = (cp - 0x2500) | (cells == 2 ? 0x100 : 0);
    uint32_t id = ((uint32_t) BOX << 20) | k;
    int w = cells * pt_cw;
    if (!box_uploaded[k]) {
        box_uploaded[k] = 1;
        int stride = (w + 3) & ~3;
        canvas_w = stride;
        canvas_h = pt_ch;
        canvas = calloc((size_t) stride * pt_ch, 1);
        canvas_w = w;
        draw_box(cp, w, pt_ch);
        /* draw_box wrote pt_rows `w` wide; spread them to the stride. */
        uint8_t *data = calloc((size_t) stride * pt_ch, 1);
        for (int j = 0; j < pt_ch; j++) memcpy(data + j * stride, canvas + j * w, (size_t) w);
        free(canvas);
        PtGlyph glyph = {.width = w, .height = pt_ch, .stride = stride, .left = 0, .top = pt_ascent, .advance = w, .data = data};
        pt_glyph_add(id, &glyph);
        glyph_bytes += (long) stride * pt_ch + 28;
        free(data);
        st.boxes++;
    }
    placed[nplaced++] = (PtPlaced) {id, cell * pt_cw, y * pt_ch + pt_ascent, style_fg[style], w, -1};
}

static void draw_glyphs(int y, int x, int n, const uint8_t *p) {
    static Cluster cl[1024];
    static uint32_t cps[1024 * 64];
    static uint8_t blank[1024];
    static int wstart[1024];
    int ncl = 0, ncps = 0;
    if (n > 1024) n = 1024;
    for (int i = 0; i < n; i++) {
        int wide = p[0] >> 6, count = p[0] & 63, style = cell_style((p[1] << 8) | p[2], y, x + i);
        p += 3;
        uint32_t *mine = cps + ncps;
        for (int k = 0; k < count; k++, p += 3) mine[k] = ((uint32_t) p[0] << 16) | ((uint32_t) p[1] << 8) | p[2];
        blank[i] = wide != 2 && (count == 0 || (count == 1 && mine[0] == ' '));
        wstart[i] = blank[i] ? i + 1 : i > 0 ? wstart[i - 1] : 0;
        if (wide == 2 || wide == 3) continue; /* a tail or a spacer: its head draws it */
        if (count == 0) continue;            /* blank: the fill draws it */
        if (style_flags[style] & 0x20) continue; /* invisible */
        ncps += count;
        cl[ncl++] = (Cluster) {i, wide == 1 ? 2 : 1, style, count, mine, 0, 0, 0};
    }
    /* Each cluster's word: from the cell after the last blank before it to
     * the next blank. */
    for (int i = 0, end = n; i < ncl; i++) {
        if (i == 0 || cl[i].cell >= end) {
            end = cl[i].cell;
            while (end < n && !blank[end]) end++;
        }
        cl[i].w0 = wstart[cl[i].cell];
        cl[i].w1 = end > cl[i].cell + cl[i].width ? end : cl[i].cell + cl[i].width;
    }
    st.clusters += ncl;
    for (int i = 0; i < ncl; i++) {
        if (cl[i].n == 1 && cl[i].cps[0] >= 0x2500 && cl[i].cps[0] <= 0x259F) {
            cl[i].face = BOX;
            continue;
        }
        int want = primary_for(cl[i].style);
        int colour = emoji(cl[i].cps, cl[i].n);
        if (faces[want].colour == colour && covers(want, cl[i].cps, cl[i].n)) cl[i].face = want;
        else if (faces[0].colour == colour && covers(0, cl[i].cps, cl[i].n)) cl[i].face = 0;
        else {
            st.fallback_clusters++;
            cl[i].face = fallback(cl[i].cps, cl[i].n);
            /* No face has all of it: its first code point alone, so that
             * a cluster of marks is one .notdef box, not a row of them. */
            if (cl[i].face < 0) cl[i].n = 1;
        }
    }
    /* Spaces once joined two runs of one fallback face (V24); a run is now
     * shaped from no more than its own cells, since a word drawn alone
     * must shape as it does beside its neighbours (V43, renderer.md §R16). */
    int from = 0;
    for (int i = 1; i <= ncl; i++)
        /* A segment is one face's, and stops at an empty cell: shaping
         * across one would join what a screen shows apart (§R16). */
        if (i == ncl || cl[i].face != cl[from].face || cl[i].cell != cl[i - 1].cell + cl[i - 1].width) {
            if (cl[from].face == BOX)
                for (int k = from; k < i; k++) place_box(cl[k].cps[0], x + cl[k].cell, y, cl[k].width, cl[k].style);
            else
                shape_segment(cl + from, i - from, x, y);
            from = i;
        }
}

/* A horizontal line across cells [x, x + n) of row y, `top` pixels into
 * the row, kept inside it. */
static void hline(uint32_t rgb, int x, int n, int y, int top, int h) {
    if (top + h > pt_ch) top = pt_ch - h;
    if (top < 0) top = 0;
    fill(rgb, x * pt_cw, y * pt_ch + top, n * pt_cw, h);
}

/* The lines a stretch of one style draws over its glyphs: the underline in
 * its kind (1 single, 2 double, 3 curly, 4 dotted, 5 dashed), the
 * strikethrough, the overline, and the cursor's shape. */
static void draw_lines(int y, int x, int n, int style) {
    int kind = style_ul[style] & 15, shape = style_ul[style] >> 4, flags = style_flags[style];
    uint32_t ulc = style_ulc[style], fg = style_fg[style];
    int t = line_thick, top = pt_ascent + ul_below;
    if (!(flags & 0x20)) {
        if (kind == 1) hline(ulc, x, n, y, top, t);
        else if (kind == 2) {
            hline(ulc, x, n, y, top, t);
            hline(ulc, x, n, y, top + 2 * t, t);
        } else if (kind >= 3 && kind <= 5) {
            int px = x * pt_cw, end = (x + n) * pt_cw, step = kind == 3 ? 2 : kind == 4 ? 2 * t : 3 * t;
            static PtRect rs[4096];
            int k = 0;
            int base = y * pt_ch + (top + 2 * t > pt_ch ? pt_ch - 2 * t : top);
            for (int p = px; p < end && k < 4096; p += step) {
                int w = step;
                if (kind == 4) w = t;
                else if (kind == 5) w = 2 * t;
                if (p + w > end) w = end - p;
                int dy = kind == 3 ? (((p - px) / 2) % 4 < 2 ? 0 : t) : 0;
                rs[k++] = (PtRect) {p, base + dy, w, t};
            }
            pt_fill_rects(ulc, rs, k);
        }
        if (flags & 0x40) hline(fg, x, n, y, pt_ascent - strike_above, t);
        if (flags & 0x80) hline(fg, x, n, y, 0, t);
    }
    if (shape == 2) {
        int h = pt_ch / 8 > 2 ? pt_ch / 8 : 2;
        hline(ulc, x, n, y, pt_ch - h, h);
    } else if (shape == 3) {
        int w = pt_cw / 6 > 2 ? pt_cw / 6 : 2;
        fill(ulc, x * pt_cw, y * pt_ch, w, pt_ch);
    } else if (shape == 4) {
        fill(ulc, x * pt_cw, y * pt_ch, n * pt_cw, 1);
        fill(ulc, x * pt_cw, y * pt_ch + pt_ch - 1, n * pt_cw, 1);
        fill(ulc, x * pt_cw, y * pt_ch, 1, pt_ch);
        fill(ulc, (x + n) * pt_cw - 1, y * pt_ch, 1, pt_ch);
    }
}

/* A run record, in one of a frame's three passes: 0 its backgrounds, 1 its
 * glyphs, 2 its lines. Every run's backgrounds are filled before any
 * glyph is drawn, so that a glyph's ink reaching into a neighbouring row
 * is not filled over by that row's run (V40). Answers past its last cell. */
static const uint8_t *draw_run(const uint8_t *p, const uint8_t *end, int pass) {
    int y = (p[1] << 8) | p[2], x = (p[3] << 8) | p[4], n = (p[5] << 8) | p[6];
    const uint8_t *cell = p + 7, *q = cell;
    static int styles[65536];
    for (int i = 0; i < n && q + 3 <= end; i++) {
        styles[i] = cell_style((q[1] << 8) | q[2], y, x + i);
        q += 3 + 3 * (q[0] & 63);
    }
    if (q > end) return end;
    if (pass == 0)
        for (int from = 0, i = 1; i <= n; i++)
            if (i == n || style_bg[styles[i]] != style_bg[styles[from]]) {
                fill(style_bg[styles[from]], (x + from) * pt_cw, y * pt_ch, (i - from) * pt_cw, pt_ch);
                from = i;
            }
    if (pass == 1) {
        draw_glyphs(y, x, n, cell);
        flush_placed();
    }
    if (pass == 2)
        for (int from = 0, i = 1; i <= n; i++)
            if (i == n || styles[i] != styles[from]) {
                if (style_ul[styles[from]] || (style_flags[styles[from]] & 0xC0)) draw_lines(y, x + from, i - from, styles[from]);
                from = i;
            }
    return q;
}

/* The primary font's cell and lines, from its regular face. */
static void primary_metrics(void) {
    FT_Face face = faces[0].ft;
    pt_cw = (int) (face->size->metrics.max_advance >> 6);
    pt_ch = (int) (face->size->metrics.height >> 6);
    pt_ascent = (int) (face->size->metrics.ascender >> 6);
    long below = -FT_MulFix(face->underline_position, face->size->metrics.y_scale) >> 6;
    long thick = FT_MulFix(face->underline_thickness, face->size->metrics.y_scale) >> 6;
    line_thick = thick < 1 ? 1 : (int) thick;
    ul_below = below < 1 ? 1 : (int) below;
    strike_above = pt_ascent * 3 / 10;
}

/* THE FRAME */

void pt_resize(int c, int r) {
    pt_cols = c;
    pt_rows = r;
    pt_target(c, r);
    have_target = 1;
    fill(0, 0, 0, c * pt_cw, r * pt_ch);
}

int pt_open(const char *font, const char *lang, int points, int dpi, long cap) {
    dpi0 = dpi;
    points0 = points;
    glyph_cap = cap;
    if (lang && *lang) {
        lang_name = copy(lang);
        language = hb_language_from_string(lang_name, -1);
    }
    hbuf = hb_buffer_create();
    int index;
    char *file = pt_font_file(font, 0, &index);
    if (file == NULL || FT_Init_FreeType(&library) != 0 || load_face(file, index, 1) != 0) {
        free(file);
        return -1;
    }
    free(file);
    primary[0] = 0;
    for (int v = 1; v < 4; v++) {
        int vi;
        char *vf = pt_font_file(font, v, &vi);
        int f = vf ? load_face(vf, vi, 1) : -1;
        primary[v] = f < 0 ? 0 : f;
        free(vf);
    }
    /* A variant is bold when the platform gave it a face other than the
     * one it gave the same variant without bold, and italic likewise; a
     * font with no bold or italic face of its own gives the regular, whose
     * glyphs are then drawn bold or italic (C§9 rule 6). */
    for (int v = 1; v < 4; v++) {
        if ((v & 1) && primary[v] != primary[v & ~1]) faces[primary[v]].own |= 1;
        if ((v & 2) && primary[v] != primary[v & ~2]) faces[primary[v]].own |= 2;
    }
    primary_metrics();
    return 0;
}

int pt_zoom(int points, int dpi) {
    if (points < 4 || points > 200 || (points == points0 && dpi == dpi0)) return 0;
    points0 = points;
    dpi0 = dpi;
    for (int f = 0; f < nfaces; f++)
        if (faces[f].primary) size_face(&faces[f]);
    primary_metrics();
    for (int f = 0; f < nfaces; f++) {
        if (!faces[f].primary) size_face(&faces[f]);
        hb_ft_font_changed(faces[f].hb);
        memset(faces[f].advance, 0, (size_t) KEYS * sizeof *faces[f].advance);
        memset(faces[f].ink, 0, (size_t) KEYS * 4 * sizeof *faces[f].ink);
    }
    reset_glyphs();
    return 1;
}

void pt_frame(const uint8_t *list, size_t length, PtFrame *out) {
    double t0 = ns();
    if (glyph_bytes > glyph_cap) reset_glyphs();
    const uint8_t *p = list, *end = list + length, *runs = NULL;
    int first = pt_rows, last = -1, sized = 0;
    inklen = 0;
    sel_from = sel_to = -1;
    while (p < end) {
        if (p[0] == 4 && p + 5 <= end) {
            int c = (p[1] << 8) | p[2], r = (p[3] << 8) | p[4];
            if (c != pt_cols || r != pt_rows || !have_target) pt_resize(c, r);
            first = 0;
            last = pt_rows - 1;
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
        } else if (p[0] == 5 && p + 9 <= end) {
            /* the highlight (docs/phase3-select.md §14) */
            sel_from = ((p[1] << 8) | p[2]) * pt_cols + ((p[3] << 8) | p[4]);
            sel_to = ((p[5] << 8) | p[6]) * pt_cols + ((p[7] << 8) | p[8]);
            p += 9;
        } else if (p[0] == 1 && p + 7 <= end) {
            int top = (p[1] << 8) | p[2], bottom = (p[3] << 8) | p[4], k = (int16_t) ((p[5] << 8) | p[6]);
            pt_scroll(top, bottom, k);
            if (top < first) first = top;
            if (bottom > last) last = bottom;
            p += 7;
        } else if (p[0] == 2 && p + 7 <= end) {
            int y = (p[1] << 8) | p[2];
            if (!runs) runs = p;
            p = draw_run(p, end, 0);
            if (y < first) first = y;
            if (y > last) last = y;
        } else
            break; /* a record this does not know: the rest of the list is not read */
    }
    /* The runs come last in a list (Vt.View), so the glyphs and the lines
     * are drawn from the first run to where the backgrounds stopped. */
    for (int pass = 1; pass <= 2 && runs; pass++)
        for (const uint8_t *r = runs; r < p && r[0] == 2;) r = draw_run(r, p, pass);
    /* A glyph's ink may reach a row next to the rows drawn. */
    if (last >= first) {
        if (first > 0) first--;
        if (last < pt_rows - 1) last++;
    }
    out->first = first;
    out->last = last;
    out->sized = sized;
    st.frames++;
    st.draw_ns += ns() - t0;
}

const uint8_t *pt_ink(int *length) {
    *length = inklen;
    return inkbuf;
}

void pt_stats(const char *who) {
    fprintf(stderr,
            "%s: frames %ld; clusters %ld (fallback %ld), fontconfig queries %ld (%.2f ms, %ld found none), segments %ld, "
            "glyphs %ld; uploaded %ld (%ld bytes held), resets %ld; colour %ld, squeezed %ld, clipped %ld; shape %.2f ms, raster %.2f ms, "
            "draw %.2f ms\n",
            who, st.frames, st.clusters, st.fallback_clusters, st.fc_queries, st.fc_ns / 1e6, st.fc_failed, st.segments, st.glyphs,
            st.uploaded, glyph_bytes, resets, st.colour, st.squeezed, st.clipped, st.shape_ns / 1e6, st.raster_ns / 1e6, st.draw_ns / 1e6);
}

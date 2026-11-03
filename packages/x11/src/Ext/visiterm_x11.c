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
 *   1 a key (V47, docs/phase3-input.md §4): its action in 1 byte (release
 *     0, press 1, repeat 2), its X keycode in 1, its modifiers in 2 as
 *     Ghostty's bits (shift 1, ctrl 2, alt 4, super 8, caps lock 16, num
 *     lock 32, and 64, 128, 256, 512 when the first four's key held is
 *     the right one), the modifiers its text consumed in 2, its unshifted
 *     code point in 4, its keysym in 4, a byte of length and its text in
 *     UTF-8, none on a release. Each is read with the modifiers and group
 *     its own event carries (V46), not the state XKB has moved on to;
 *   2 the window's size in cells changed: columns and rows, 2 bytes each;
 *   3 the focus: 1 in, 0 out;
 *   4 the window manager asks the window to close (WM_DELETE_WINDOW);
 *   5 an IME's commit: its length in 2 bytes and its text in UTF-8;
 *   6 an IME's preedit drawn: the caret, the first character changed and
 *     how many, 2 bytes each, the length of the new text in 2 and its
 *     UTF-8, then the count of its feedbacks in 2 and each in 1 byte;
 *   7 the IME's preedit is done;
 *   8 an input context is made with an IME, which keys go through now;
 *   9 the pointer (docs/phase3-select.md §4): its action in 1 byte (press
 *     0, release 1, motion 2), its button in 1 as Ghostty numbers them
 *     (none 0, left 1, right 2, middle 3, the wheel's four steps 4-7, then
 *     8-11), its modifiers in 2 as a key's, its position in the window in
 *     pixels, x and y in 2 bytes each, signed, then the window's width and
 *     height and the cell's in pixels, 2 bytes each. A wheel step is a
 *     press alone: X's release of buttons 4-7 is not recorded. Motions one
 *     after another are recorded as the last of them;
 *  10 a selection this window owned is another's now (docs/phase3-select.md
 *     §14): 0 PRIMARY, 1 CLIPBOARD.
 *
 * Keys go through XIM when an input method is there (V44-V46,
 * docs/phase3-input.md §3): xcb-imdkit, patched (patches/), with an input
 * context whose preedit visiterm draws (on-the-spot). Every press and
 * release is sent to the IME, and a key it gives back is recorded then,
 * read with its own event's modifiers; its commits and preedits are
 * recorded as they come, in their order. The context is never destroyed
 * while the window lives: a focus change only sets or unsets its focus
 * (§3.4). Without an IME, keys are recorded as they come.
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
#include FT_BITMAP_H
#include <hb-ft.h>
#include <hb.h>
#include <math.h>
#include <stdio.h>
#include <time.h>
#include <stdlib.h>
#include <string.h>
#include <xcb/render.h>
#include <xcb/xcb.h>
#include <xcb/xcb_renderutil.h>
#include <xcb/xkb.h>
#include <xkbcommon/xkbcommon-x11.h>
#include <xcb/randr.h>
#include <xcb-imdkit/imclient.h>
#include <xcb-imdkit/encoding.h>

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
static int cols, rows, win_cols, win_rows, focused = -1, win_w, win_h;
static uint32_t margin_bg = 0xFFFFFFFF;
static long glyph_bytes, glyph_cap, resets;

/* A style's record by its id; from 65536 on, the same style selected
 * (docs/phase3-select.md §14): its colours swapped, made when a selected
 * cell is drawn in it. */
static uint32_t style_fg[131072], style_bg[131072], style_ulc[131072];
static uint8_t style_flags[131072], style_ul[131072];
/* The cells the frame's highlight record covers, y * cols + x, both
 * included; -1 when it has none. */
static int sel_from = -1, sel_to = -1;

/* The style a cell is drawn in: its own, or its selected copy when the
 * frame's highlight covers it. A cursor's style (0x8000 and up) is the
 * cursor's whatever the highlight. */
static int cell_style(int style, int y, int x) {
    int i = y * cols + x;
    if (sel_from < 0 || i < sel_from || i > sel_to || style >= 0x8000) return style;
    int s = 65536 + style;
    style_fg[s] = style_bg[style];
    style_bg[s] = style_fg[style];
    style_ulc[s] = style_ulc[style] == style_fg[style] ? style_bg[style] : style_ulc[style];
    style_flags[s] = style_flags[style];
    style_ul[s] = style_ul[style];
    return s;
}

static xcb_atom_t wm_protocols, wm_delete, net_wm_name, utf8_string;

static struct {
    long clusters, fallback_clusters, fc_queries, fc_failed, segments, glyphs, uploaded, colour, squeezed, clipped, boxes, frames;
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
/* The last face's number is the box drawing's (V41), whose glyphs the C
 * draws itself; it is no font. */
#define BOX (FACES - 1)
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
    int primary;       /* one of the primary font's faces */
    uint8_t *uploaded; /* a bit a glyph index and form */
    int16_t *advance;  /* the x_off each glyph was uploaded with */
    int16_t *ink;      /* each glyph's bitmap: left of its origin, top above it, width, height */
    ColourGlyph *pictures;
} Face;

static Face faces[FACES];
static int nfaces, points0, dpi0 = 96;
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

/* A face sized for `points0` at `dpi0` (V50): one of the primary font's at
 * that size, a fallback one so 水 fills two cells and its ink stays within
 * the primary cell, which the primary faces' metrics give. */
static void size_face(Face *F) {
    if (F->colour) return;
    F->scale = 1.0;
    FT_Set_Char_Size(F->ft, 0, points0 * 64, (FT_UInt) dpi0, (FT_UInt) dpi0);
    if (!F->primary) {
        FT_UInt gi = FT_Get_Char_Index(F->ft, 0x6C34);
        if (gi && FT_Load_Glyph(F->ft, gi, FT_LOAD_NO_HINTING) == 0) {
            double adv = F->ft->glyph->advance.x / 64.0;
            double top = F->ft->glyph->metrics.horiBearingY / 64.0;
            double bottom = F->ft->glyph->metrics.height / 64.0 - top;
            double sc = 2.0 * cw / adv;
            if (top > 0 && ascent / top < sc) sc = ascent / top;
            if (bottom > 0 && (ch - ascent) / bottom < sc) sc = (ch - ascent) / bottom;
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
    F->file = strdup(file);
    F->index = index;
    F->scale = 1.0;
    F->colour = FT_HAS_COLOR(F->ft) && !FT_IS_SCALABLE(F->ft) && F->ft->num_fixed_sizes > 0;
    F->pictures = NULL;
    if (F->colour) FT_Select_Size(F->ft, 0);
    F->primary = is_primary;
    size_face(F);
    F->hb = hb_ft_font_create_referenced(F->ft);
    F->uploaded = calloc(KEYS / 8, 1);
    F->advance = calloc(KEYS, sizeof *F->advance);
    F->ink = calloc((size_t) KEYS * 4, sizeof *F->ink);
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
static uint8_t box_uploaded[512];

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
    xcb_render_glyphinfo_t info = {.width = (uint16_t) b->width, .height = (uint16_t) b->rows,
                                   .x = (int16_t) (-F->ft->glyph->bitmap_left - shift), .y = (int16_t) F->ft->glyph->bitmap_top,
                                   .x_off = (int16_t) advance, .y_off = 0};
    xcb_render_add_glyphs(conn, glyphs, 1, &id, &info, (uint32_t) size, data);
    FT_Bitmap_Done(library, &grey);
    int16_t *ink = F->ink + (size_t) k * 4;
    ink[0] = (int16_t) -info.x;
    ink[1] = info.y;
    ink[2] = (int16_t) info.width;
    ink[3] = (int16_t) info.height;
    glyph_bytes += (long) size + 28;
    free(data);
    st.raster_ns += ns() - t0;
    return id;
}

/* The glyphs a run draws, in order, before they go out as requests. */
typedef struct { uint32_t id; int x, y, style, advance, clip; } Placed;
static Placed placed[8192];
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
static xcb_rectangle_t clips[8192];
static int nclips;

static void ink_cells(int y, int cell, int n, int w0, int w1, int first) {
    if (!gbox.any) return;
    int ax0 = (w0 - 1) * cw, ax1 = (w1 + 1) * cw, ay0 = (y - 1) * ch, ay1 = (y + 2) * ch;
    if ((gbox.x0 < ax0 || gbox.x1 > ax1 || gbox.y0 < ay0 || gbox.y1 > ay1) && nclips < 8192) {
        clips[nclips] = (xcb_rectangle_t) {(int16_t) ax0, (int16_t) ay0, (uint16_t) (ax1 - ax0), (uint16_t) (ay1 - ay0)};
        for (int k = first; k < nplaced; k++) placed[k].clip = nclips;
        nclips++;
        st.clipped++;
        if (gbox.x0 < ax0) gbox.x0 = ax0;
        if (gbox.x1 > ax1) gbox.x1 = ax1;
        if (gbox.y0 < ay0) gbox.y0 = ay0;
        if (gbox.y1 > ay1) gbox.y1 = ay1;
    }
    for (int i = 0; i < n; i++) {
        int cx0 = (cell + i) * cw, cx1 = cx0 + cw, cy0 = y * ch, cy1 = cy0 + ch;
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
    placed[nplaced++] = (Placed) {id, x, y, style, faces[f].advance[id & (KEYS - 1)], -1};
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
        int clip = placed[i].clip;
        int len = 0, penx = 0, peny = 0, count_at = -1, count = 0;
        for (; i < nplaced && style_fg[placed[i].style] == fg && placed[i].clip == clip && len < 60000; i++) {
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
        if (clip >= 0) xcb_render_set_picture_clip_rectangles(conn, target, 0, 0, 1, &clips[clip]);
        xcb_render_composite_glyphs_32(conn, XCB_RENDER_PICT_OP_OVER, solid_of(fg), target, 0, glyphs, 0, 0, (uint32_t) len,
                                       buffer);
        if (clip >= 0) {
            uint32_t none = XCB_NONE;
            xcb_render_change_picture(conn, target, XCB_RENDER_CP_CLIP_MASK, &none);
        }
    }
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
        ink_cells(y, x0 + C->cell, box / cw, x0 + C->w0, x0 + C->w1, first);
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
    int w = cells * cw;
    if (!box_uploaded[k]) {
        box_uploaded[k] = 1;
        int stride = (w + 3) & ~3;
        canvas_w = stride;
        canvas_h = ch;
        canvas = calloc((size_t) stride * ch, 1);
        canvas_w = w;
        draw_box(cp, w, ch);
        /* draw_box wrote rows `w` wide; spread them to the stride. */
        uint8_t *data = calloc((size_t) stride * ch, 1);
        for (int j = 0; j < ch; j++) memcpy(data + j * stride, canvas + j * w, (size_t) w);
        free(canvas);
        xcb_render_glyphinfo_t info = {.width = (uint16_t) w, .height = (uint16_t) ch, .x = 0, .y = (int16_t) ascent,
                                       .x_off = (int16_t) w, .y_off = 0};
        xcb_render_add_glyphs(conn, glyphs, 1, &id, &info, (uint32_t) stride * ch, data);
        glyph_bytes += (long) stride * ch + 28;
        free(data);
        st.boxes++;
    }
    placed[nplaced++] = (Placed) {id, cell * cw, y * ch + ascent, style, w, -1};
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
                fill(style_bg[styles[from]], (x + from) * cw, y * ch, (i - from) * cw, ch);
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
            "glyphs %ld; uploaded %ld (%ld bytes held), resets %ld; colour %ld, squeezed %ld, clipped %ld; shape %.2f ms, raster %.2f ms, "
            "draw %.2f ms\n",
            st.frames, st.clusters, st.fallback_clusters, st.fc_queries, st.fc_ns / 1e6, st.fc_failed, st.segments, st.glyphs,
            st.uploaded, glyph_bytes, resets, st.colour, st.squeezed, st.clipped, st.shape_ns / 1e6, st.raster_ns / 1e6, st.draw_ns / 1e6);
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

/* What the window always asks of X: motion only while a button is held,
 * unless visiterm_x11_motion asks for all of it. */
#define BASE_EVENTS                                                                                                  \
    (XCB_EVENT_MASK_EXPOSURE | XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_KEY_RELEASE | XCB_EVENT_MASK_FOCUS_CHANGE | \
     XCB_EVENT_MASK_STRUCTURE_NOTIFY | XCB_EVENT_MASK_BUTTON_PRESS | XCB_EVENT_MASK_BUTTON_RELEASE |                \
     XCB_EVENT_MASK_BUTTON_MOTION)
static int all_motion;

static uint8_t evbuf[65536];
static int evlen;

static void put(const uint8_t *r, int n) {
    if (evlen + n > (int) sizeof evbuf) return;
    memcpy(evbuf + evlen, r, (size_t) n);
    evlen += n;
}

/* A motion waits here until something else is recorded, so that a run of
 * motions is recorded as its last. */
static uint8_t motion_rec[17];
static int motion_pending;

static void flush_motion(void) {
    if (motion_pending) put(motion_rec, sizeof motion_rec);
    motion_pending = 0;
}

static void record(const uint8_t *r, int n) {
    flush_motion();
    put(r, n);
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
    /* a key held down repeats as presses without releases between, so a
     * repeat is told from a press (V47) */
    xcb_xkb_per_client_flags(conn, (xcb_xkb_device_spec_t) kbd, XCB_XKB_PER_CLIENT_FLAG_DETECTABLE_AUTO_REPEAT,
                             XCB_XKB_PER_CLIENT_FLAG_DETECTABLE_AUTO_REPEAT, 0, 0, 0);
}

/* Keys held, for telling a repeat from a press under XKB's detectable
 * autorepeat, and which right-hand modifier keys are held, for the sides. */
static uint8_t held[32];
static int right_held;

/* Ghostty's bit for each of the modifiers xkbcommon names. */
static const struct { const char *name; int bit; } mod_bits[] = {
    {XKB_MOD_NAME_SHIFT, 1}, {XKB_MOD_NAME_CTRL, 2}, {XKB_MOD_NAME_ALT, 4},
    {XKB_MOD_NAME_LOGO, 8},  {XKB_MOD_NAME_CAPS, 16}, {XKB_MOD_NAME_NUM, 32},
};

static int ghostty_mods(struct xkb_state *st, xkb_mod_mask_t only) {
    int m = 0;
    for (size_t i = 0; i < sizeof mod_bits / sizeof *mod_bits; i++) {
        xkb_mod_index_t ix = xkb_keymap_mod_get_index(keymap, mod_bits[i].name);
        if (ix == XKB_MOD_INVALID) continue;
        if (st ? xkb_state_mod_index_is_active(st, ix, XKB_STATE_MODS_EFFECTIVE) > 0 : (only >> ix) & 1) m |= mod_bits[i].bit;
    }
    return m;
}

static int right_bit(xkb_keysym_t sym) {
    switch (sym) {
    case XKB_KEY_Shift_R: return 64;
    case XKB_KEY_Control_R: return 128;
    case XKB_KEY_Alt_R: case XKB_KEY_Meta_R: case XKB_KEY_ISO_Level3_Shift: return 256;
    case XKB_KEY_Super_R: case XKB_KEY_Hyper_R: return 512;
    default: return 0;
    }
}

/* A key press or release, read with the modifiers and group of its own
 * event: the core state field, its group in bits 13 and 14. */
static void key_event(int press, uint8_t keycode, uint16_t state) {
    if (!keymap) return;
    struct xkb_state *st = xkb_state_new(keymap);
    if (!st) return;
    xkb_state_update_mask(st, state & 0xff, 0, 0, 0, 0, (state >> 13) & 3);
    xkb_keysym_t sym = xkb_state_key_get_one_sym(st, keycode);
    int bit = 1 << (keycode & 7), down = held[keycode >> 3] & bit;
    int action = press ? (down ? 2 : 1) : 0;
    if (press) held[keycode >> 3] |= (uint8_t) bit;
    else held[keycode >> 3] &= (uint8_t) ~bit;
    int mods = ghostty_mods(st, 0);
    mods |= right_held & ((mods & 15) << 6);
    int r = right_bit(sym);
    if (r) right_held = press ? (right_held | r) : (right_held & ~r);
    char text[64];
    /* the keysym's own text, not xkb_state_key_get_utf8's, which makes
     * ctrl+c 0x03: the encoder makes control characters itself, as it
     * does from GTK's text in Ghostty */
    int n = press ? xkb_keysym_to_utf8(sym, text, sizeof text) - 1 : 0;
    if (n < 0) n = 0;
    if (n > 63) n = 63;
    int consumed = ghostty_mods(NULL, xkb_state_key_get_consumed_mods2(st, keycode, XKB_CONSUMED_MODE_XKB));
    const xkb_keysym_t *syms;
    xkb_layout_index_t layout = xkb_state_key_get_layout(st, keycode);
    uint32_t unshifted = 0;
    if (xkb_keymap_key_get_syms_by_level(keymap, keycode, layout == XKB_LAYOUT_INVALID ? 0 : layout, 0, &syms) > 0)
        unshifted = xkb_keysym_to_utf32(syms[0]);
    xkb_state_unref(st);
    uint8_t rec[18 + 63] = {1, (uint8_t) action, keycode, (uint8_t) (mods >> 8), (uint8_t) mods,
                            (uint8_t) (consumed >> 8), (uint8_t) consumed,
                            (uint8_t) (unshifted >> 24), (uint8_t) (unshifted >> 16), (uint8_t) (unshifted >> 8), (uint8_t) unshifted,
                            (uint8_t) (sym >> 24), (uint8_t) (sym >> 16), (uint8_t) (sym >> 8), (uint8_t) sym, (uint8_t) n};
    memcpy(rec + 16, text, (size_t) n);
    record(rec, 16 + n);
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
    win_w = w;
    win_h = h;
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

/* The pointer (docs/phase3-select.md §4): a press, release or motion, its
 * modifiers read from its own event's state as a key's are. X's buttons
 * are Ghostty's but for the middle (2) and right (3), which swap. */
static void pointer_event(int action, int xbutton, int x, int y, uint16_t state) {
    int button = xbutton == 2 ? 3 : xbutton == 3 ? 2 : xbutton;
    if (button > 11) return;
    int mods = 0;
    if (keymap) {
        struct xkb_state *st = xkb_state_new(keymap);
        if (st) {
            xkb_state_update_mask(st, state & 0xff, 0, 0, 0, 0, (state >> 13) & 3);
            mods = ghostty_mods(st, 0);
            xkb_state_unref(st);
        }
    }
    uint8_t r[17] = {9, (uint8_t) action, (uint8_t) button, (uint8_t) (mods >> 8), (uint8_t) mods,
                     (uint8_t) ((uint16_t) x >> 8), (uint8_t) x, (uint8_t) ((uint16_t) y >> 8), (uint8_t) y,
                     (uint8_t) (win_w >> 8), (uint8_t) win_w, (uint8_t) (win_h >> 8), (uint8_t) win_h,
                     (uint8_t) (cw >> 8), (uint8_t) cw, (uint8_t) (ch >> 8), (uint8_t) ch};
    if (action == 2) {
        flush_motion();
        memcpy(motion_rec, r, sizeof r);
        motion_pending = 1;
        return;
    }
    record(r, sizeof r);
}

/* The input method, when one is there. */
static xcb_xim_t *xim;
static xcb_xic_t xic;
static int have_xic;
static int spot_x = -1, spot_y = -1;

static void key_event(int press, uint8_t keycode, uint16_t state);
static void pointer_event(int action, int xbutton, int x, int y, uint16_t state);
static void selection_atoms(void);
static void selection_request(xcb_selection_request_event_t *q);
static void selection_clear(xcb_selection_clear_event_t *c);
static void transfer_step(xcb_property_notify_event_t *p);
static xcb_timestamp_t last_time;

static void record_text(uint8_t kind, const char *s, size_t n) {
    if (n > 4000) n = 4000;
    uint8_t head[3] = {kind, (uint8_t) (n >> 8), (uint8_t) n};
    if (evlen + 3 + (int) n > (int) sizeof evbuf) return;
    record(head, 3);
    record((const uint8_t *) s, (int) n);
}

/* The IME's text as UTF-8, whichever encoding it was given in; free it. */
static char *xim_utf8(const char *s, size_t n, size_t *out) {
    if (xcb_xim_get_encoding(xim) == XCB_XIM_UTF8_STRING) {
        char *u = malloc(n + 1);
        if (!u) return NULL;
        memcpy(u, s, n);
        u[n] = 0;
        *out = n;
        return u;
    }
    return xcb_compound_text_to_utf8(s, n, out);
}

static void xim_forward(xcb_xim_t *m, xcb_xic_t c, xcb_key_press_event_t *e, void *u) {
    (void) m; (void) c; (void) u;
    key_event((e->response_type & 0x7f) == XCB_KEY_PRESS, e->detail, e->state);
}

static void xim_commit(xcb_xim_t *m, xcb_xic_t c, uint32_t flag, char *str, uint32_t len, uint32_t *syms, size_t nsyms,
                       void *u) {
    (void) m; (void) c; (void) flag; (void) syms; (void) nsyms; (void) u;
    size_t n = 0;
    char *t = xim_utf8(str, len, &n);
    if (t) record_text(5, t, n);
    free(t);
}

static void xim_draw(xcb_xim_t *m, xcb_xic_t c, xcb_im_preedit_draw_fr_t *f, void *u) {
    (void) m; (void) c; (void) u;
    size_t n = 0;
    char *t = xim_utf8((const char *) f->preedit_string, f->length_of_preedit_string, &n);
    if (n > 2000) n = 2000;
    uint32_t nf = f->feedback_array.size > 1000 ? 1000 : f->feedback_array.size;
    uint8_t head[12] = {6, (uint8_t) (f->caret >> 8), (uint8_t) f->caret, (uint8_t) (f->chg_first >> 8), (uint8_t) f->chg_first,
                        (uint8_t) (f->chg_length >> 8), (uint8_t) f->chg_length, (uint8_t) (n >> 8), (uint8_t) n};
    if (evlen + 9 + (int) n + 2 + (int) nf > (int) sizeof evbuf) { free(t); return; }
    record(head, 9);
    record((const uint8_t *) (t ? t : ""), (int) n);
    uint8_t cnt[2] = {(uint8_t) (nf >> 8), (uint8_t) nf};
    record(cnt, 2);
    for (uint32_t i = 0; i < nf; i++) {
        uint8_t fb = (uint8_t) f->feedback_array.items[i];
        record(&fb, 1);
    }
    free(t);
}

static void xim_done(xcb_xim_t *m, xcb_xic_t c, void *u) {
    (void) m; (void) c; (void) u;
    uint8_t r[1] = {7};
    record(r, 1);
}

static void xim_gone(xcb_xim_t *m, void *u) {
    (void) m; (void) u;
    have_xic = 0;
}

static void xim_made(xcb_xim_t *m, xcb_xic_t c, void *u) {
    (void) m; (void) u;
    xic = c;
    have_xic = 1;
    if (focused == 1) xcb_xim_set_ic_focus(xim, xic);
    uint8_t r[1] = {8};
    record(r, 1);
}

static void xim_opened(xcb_xim_t *m, void *u) {
    (void) u;
    uint32_t style = XCB_IM_PreeditCallbacks | XCB_IM_StatusNothing;
    xcb_point_t spot = {0, (int16_t) ascent};
    xcb_xim_nested_list pre = xcb_xim_create_nested_list(m, XCB_XIM_XNSpotLocation, &spot, NULL);
    xcb_xim_create_ic(m, xim_made, NULL, XCB_XIM_XNInputStyle, &style, XCB_XIM_XNClientWindow, &window,
                      XCB_XIM_XNFocusWindow, &window, XCB_XIM_XNPreeditAttributes, &pre, NULL);
    free(pre.data);
}

static void xim_quiet(const char *fmt, ...) { (void) fmt; }

static void xim_setup(int screen_number) {
    if (getenv("VISITERM_NO_XIM")) return;
    xcb_compound_text_init();
    xim = xcb_xim_create(conn, screen_number, NULL);
    if (!xim) return;
    xcb_xim_set_log_handler(xim, xim_quiet);
    xcb_xim_set_use_utf8_string(xim, true);
    static const xcb_xim_im_callback cb = {
        .forward_event = xim_forward, .commit_string = xim_commit, .preedit_draw = xim_draw,
        .preedit_done = xim_done, .disconnected = xim_gone,
    };
    xcb_xim_set_im_callback(xim, &cb, NULL);
    xcb_xim_open(xim, xim_opened, true, NULL);
}

static void drain(void) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(conn)) != NULL) {
        int type = e->response_type & 0x7f;
        if (xim && xcb_xim_filter_event(xim, e)) {
            free(e);
            continue;
        }
        if (xkb_event && type == xkb_event) xkb_event_in(e);
        else if (type == XCB_SELECTION_REQUEST) selection_request((xcb_selection_request_event_t *) e);
        else if (type == XCB_SELECTION_CLEAR) selection_clear((xcb_selection_clear_event_t *) e);
        else if (type == XCB_PROPERTY_NOTIFY) transfer_step((xcb_property_notify_event_t *) e);
        else if (type == XCB_KEY_PRESS || type == XCB_KEY_RELEASE) {
            xcb_key_press_event_t *k = (xcb_key_press_event_t *) e;
            last_time = k->time;
            if (have_xic) xcb_xim_forward_event(xim, xic, k);
            else key_event(type == XCB_KEY_PRESS, k->detail, k->state);
        }
        else if (type == XCB_BUTTON_PRESS || type == XCB_BUTTON_RELEASE) {
            xcb_button_press_event_t *b = (xcb_button_press_event_t *) e;
            last_time = b->time;
            /* a wheel step is its press; X's release of it is not a release */
            if (!(type == XCB_BUTTON_RELEASE && b->detail >= 4 && b->detail <= 7))
                pointer_event(type == XCB_BUTTON_PRESS ? 0 : 1, b->detail, b->event_x, b->event_y, b->state);
        } else if (type == XCB_MOTION_NOTIFY) {
            xcb_motion_notify_event_t *mo = (xcb_motion_notify_event_t *) e;
            last_time = mo->time;
            pointer_event(2, 0, mo->event_x, mo->event_y, mo->state);
        }
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
            if (f->detail != XCB_NOTIFY_DETAIL_POINTER) {
                focus_in(type == XCB_FOCUS_IN);
                if (have_xic) {
                    if (type == XCB_FOCUS_IN) xcb_xim_set_ic_focus(xim, xic);
                    else xcb_xim_unset_ic_focus(xim, xic);
                }
                /* keys held while the focus left are released elsewhere */
                memset(held, 0, sizeof held);
                right_held = 0;
            }
        } else if (type == XCB_CLIENT_MESSAGE) {
            xcb_client_message_event_t *m = (xcb_client_message_event_t *) e;
            if (m->type == wm_protocols && m->data.data32[0] == wm_delete) {
                uint8_t rec[1] = {4};
                record(rec, 1);
            }
        }
        free(e);
    }
    flush_motion();
    /* what the IME was sent (a key forwarded, its sync replies) goes now,
     * not with the next frame, which a composing key does not cause */
    xcb_flush(conn);
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

/* The primary font's cell and lines, from its regular face. */
static void primary_metrics(void) {
    FT_Face face = faces[0].ft;
    cw = (int) (face->size->metrics.max_advance >> 6);
    ch = (int) (face->size->metrics.height >> 6);
    ascent = (int) (face->size->metrics.ascender >> 6);
    long below = -FT_MulFix(face->underline_position, face->size->metrics.y_scale) >> 6;
    long thick = FT_MulFix(face->underline_thickness, face->size->metrics.y_scale) >> 6;
    line_thick = thick < 1 ? 1 : (int) thick;
    ul_below = below < 1 ? 1 : (int) below;
    strike_above = ascent * 3 / 10;
}

/* The screen's resolution (V50, docs/phase3-input.md §7): `Xft.dpi` from
 * the resources the desktop set on the root window, which its scale
 * setting writes and GTK, Qt and Xft size their fonts by; else the primary
 * monitor's size from RandR; else 96. The X screen's own size in
 * millimetres is the server's arithmetic for 96, and says nothing. */
static int screen_dpi(void) {
    const char *forced = getenv("VISITERM_DPI");
    if (forced && atoi(forced) > 0) return atoi(forced);
    xcb_get_property_reply_t *rm = xcb_get_property_reply(
        conn, xcb_get_property(conn, 0, screen->root, XCB_ATOM_RESOURCE_MANAGER, XCB_ATOM_STRING, 0, 1 << 20), NULL);
    if (rm) {
        int n = xcb_get_property_value_length(rm);
        const char *v = xcb_get_property_value(rm);
        for (int i = 0; i + 8 <= n; i++) {
            if ((i == 0 || v[i - 1] == '\n') && strncmp(v + i, "Xft.dpi:", 8) == 0) {
                char num[32];
                int k = 0;
                for (int j = i + 8; j < n && v[j] != '\n' && k < 31; j++) num[k++] = v[j];
                num[k] = 0;
                double d = strtod(num, NULL);
                free(rm);
                if (d >= 24 && d <= 1000) return (int) (d + 0.5);
                rm = NULL;
                break;
            }
        }
        free(rm);
    }
    xcb_randr_get_monitors_reply_t *mons =
        xcb_randr_get_monitors_reply(conn, xcb_randr_get_monitors(conn, screen->root, 1), NULL);
    int dpi = 0;
    if (mons) {
        xcb_randr_monitor_info_iterator_t it = xcb_randr_get_monitors_monitors_iterator(mons);
        for (int first = 1; it.rem; xcb_randr_monitor_info_next(&it), first = 0) {
            xcb_randr_monitor_info_t *m = it.data;
            if ((m->primary || first) && m->width_in_millimeters > 0) {
                dpi = (int) (m->width * 25.4 / m->width_in_millimeters + 0.5);
                if (m->primary) break;
            }
        }
        free(mons);
    }
    return dpi >= 24 && dpi <= 1000 ? dpi : 96;
}

/* Opens the window: `c` by `r` cells of the font `font` at `points`,
 * fallback asked in the language `lang` (empty for none, V25), the glyph
 * set reset past `cap` bytes (V37). Answers the cell's width and height as
 * `width * 65536 + height`, or a negative code: -1 no font, -2 no X server,
 * -3 no RENDER formats it needs. */
geng_cancel visiterm_x11_open(int32_t c, int32_t r, int32_t points, void *font_bytes, void *lang_bytes, int32_t cap,
                              void *title_bytes, geng_wait *wait) {
    /* the display first: the font's size in pixels is its dpi's (V50) */
    int screen_number = 0;
    conn = xcb_connect(NULL, &screen_number);
    if (xcb_connection_has_error(conn)) {
        geng_succeed(wait, geng_slot_I4(-2));
        return (geng_cancel) {0};
    }
    screen = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    dpi0 = screen_dpi();
    if (getenv("X11_STATS")) fprintf(stderr, "dpi %d\n", dpi0);
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
    primary_metrics();
    atexit(at_exit);

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
    win_w = c * cw;
    win_h = r * ch;
    window = xcb_generate_id(conn);
    uint32_t values[2] = {screen->black_pixel, BASE_EVENTS};
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, screen->root, 0, 0, (uint16_t) (c * cw), (uint16_t) (r * ch), 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual, XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK, values);
    wm_protocols = atom("WM_PROTOCOLS");
    wm_delete = atom("WM_DELETE_WINDOW");
    net_wm_name = atom("_NET_WM_NAME");
    utf8_string = atom("UTF8_STRING");
    selection_atoms();
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
    xim_setup(screen_number);
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
    const uint8_t *p = b->data, *end = b->data + b->length, *runs = NULL;
    int first = rows, last = -1, sized = 0;
    inklen = 0;
    sel_from = sel_to = -1;
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
        } else if (p[0] == 5 && p + 9 <= end) {
            /* the highlight (docs/phase3-select.md §14) */
            sel_from = ((p[1] << 8) | p[2]) * cols + ((p[3] << 8) | p[4]);
            sel_to = ((p[5] << 8) | p[6]) * cols + ((p[7] << 8) | p[8]);
            p += 9;
        } else if (p[0] == 1 && p + 7 <= end) {
            int top = (p[1] << 8) | p[2], bottom = (p[3] << 8) | p[4], k = (int16_t) ((p[5] << 8) | p[6]);
            xcb_copy_area(conn, pixmap, pixmap, gc, 0, (int16_t) ((top + k) * ch), 0, (int16_t) (top * ch), (uint16_t) (cols * cw),
                          (uint16_t) ((bottom - top + 1) * ch));
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
        if (last < rows - 1) last++;
    }
    if (last >= first)
        xcb_copy_area(conn, pixmap, window, gc, 0, (int16_t) (first * ch), 0, (int16_t) (first * ch), (uint16_t) (cols * cw),
                      (uint16_t) ((last - first + 1) * ch));
    if (sized || style_bg[0] != margin_bg) margins();
    xcb_flush(conn);
    drain();
    st.frames++;
    st.draw_ns += ns() - t0;
    /* The answer: a byte, 0 or 1 once the connection has failed, then the
     * ink of the cells drawn. */
    geng_bytes *a = geng_alloc_atomic(sizeof *a + (size_t) inklen + 1, GENG_HEADER_BYTES(sizeof *a + (size_t) inklen + 1));
    a->length = inklen + 1;
    a->pad = 0;
    a->data = (uint8_t *) (a + 1);
    a->buffer = NULL;
    a->block = NULL;
    a->data[0] = xcb_connection_has_error(conn) ? 1 : 0;
    if (inklen) memcpy(a->data + 1, inkbuf, (size_t) inklen);
    geng_succeed(wait, geng_slot_P(a));
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

/* The font at `points` (V50's zoom): every face sized again, the glyph
 * set begun again, the window kept at its size in pixels and so the cells
 * that fit it reported as a new size. Answers the new cell as `open` does. */
geng_cancel visiterm_x11_zoom(int32_t points, geng_wait *wait) {
    if (points >= 4 && points <= 200 && points != points0) {
        points0 = points;
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
        uint32_t hints[18] = {16 | 64 | 256, 0, 0, 0, 0, (uint32_t) cw, (uint32_t) ch, 0, 0, (uint32_t) cw, (uint32_t) ch, 0, 0, 0, 0, 0, 0, 0};
        xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_NORMAL_HINTS, XCB_ATOM_WM_SIZE_HINTS, 32, 18, hints);
        xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(conn, xcb_get_geometry(conn, window), NULL);
        if (g) {
            win_cols = -1;
            size_in(g->width, g->height);
            free(g);
        }
        make_pixmap(win_cols, win_rows);
        spot_x = spot_y = -1;
        xcb_flush(conn);
    }
    geng_succeed(wait, geng_slot_I4(cw * 65536 + ch));
    return (geng_cancel) {0};
}

/* THE SELECTIONS (docs/phase3-select.md §5, §14)
 *
 * The window owns PRIMARY when a selection is made and CLIPBOARD on a copy,
 * with a copy of the text here, and answers every request from it without
 * Geng: TARGETS, TIMESTAMP, UTF8_STRING, text/plain;charset=utf-8, TEXT
 * (as UTF-8) and STRING (Latin-1, '?' for what it has not). Text larger
 * than a piece goes as INCR, a piece each time the requestor deletes the
 * last, from the event loop, so no request waits on another. */

#define PIECE 262144
static xcb_atom_t a_clipboard, a_targets, a_timestamp, a_text, a_plain, a_incr;
static struct {
    uint8_t *data;
    size_t len;
    xcb_timestamp_t time;
    int owned;
} sel[2];
static struct {
    xcb_window_t win;
    xcb_atom_t prop, type;
    uint8_t *data;
    size_t len, at;
    int live;
} xfer[8];

static void selection_atoms(void) {
    const char *names[] = {"CLIPBOARD", "TARGETS", "TIMESTAMP", "TEXT", "text/plain;charset=utf-8", "INCR"};
    xcb_atom_t *out[] = {&a_clipboard, &a_targets, &a_timestamp, &a_text, &a_plain, &a_incr};
    xcb_intern_atom_cookie_t ck[6];
    for (int i = 0; i < 6; i++) ck[i] = xcb_intern_atom(conn, 0, (uint16_t) strlen(names[i]), names[i]);
    for (int i = 0; i < 6; i++) {
        xcb_intern_atom_reply_t *r = xcb_intern_atom_reply(conn, ck[i], NULL);
        *out[i] = r ? r->atom : XCB_ATOM_NONE;
        free(r);
    }
}

static void notify_requestor(xcb_selection_request_event_t *q, xcb_atom_t prop) {
    xcb_selection_notify_event_t n = {0};
    n.response_type = XCB_SELECTION_NOTIFY;
    n.time = q->time;
    n.requestor = q->requestor;
    n.selection = q->selection;
    n.target = q->target;
    n.property = prop;
    xcb_send_event(conn, 0, q->requestor, 0, (const char *) &n);
}

/* UTF-8 as Latin-1: a code point past 255, or a byte that does not decode,
 * is '?'. */
static uint8_t *latin1(const uint8_t *s, size_t n, size_t *out) {
    uint8_t *o = malloc(n + 1);
    size_t k = 0;
    for (size_t i = 0; i < n;) {
        uint32_t c = s[i];
        int len = c < 0x80 ? 1 : (c >> 5) == 6 ? 2 : (c >> 4) == 14 ? 3 : (c >> 3) == 30 ? 4 : 1;
        if (len > 1 && i + (size_t) len <= n) {
            c &= (1u << (7 - len)) - 1;
            for (int j = 1; j < len; j++) c = (c << 6) | (s[i + (size_t) j] & 63);
        }
        o[k++] = c < 256 ? (uint8_t) c : '?';
        i += (size_t) len;
    }
    *out = k;
    return o;
}

static void selection_request(xcb_selection_request_event_t *q) {
    int which = q->selection == XCB_ATOM_PRIMARY ? 0 : q->selection == a_clipboard ? 1 : -1;
    xcb_atom_t prop = q->property ? q->property : q->target;
    if (which < 0 || !sel[which].owned) {
        notify_requestor(q, XCB_ATOM_NONE);
    } else if (q->target == a_targets) {
        xcb_atom_t t[] = {a_targets, a_timestamp, utf8_string, a_plain, a_text, XCB_ATOM_STRING};
        xcb_change_property(conn, XCB_PROP_MODE_REPLACE, q->requestor, prop, XCB_ATOM_ATOM, 32, 6, t);
        notify_requestor(q, prop);
    } else if (q->target == a_timestamp) {
        xcb_change_property(conn, XCB_PROP_MODE_REPLACE, q->requestor, prop, XCB_ATOM_INTEGER, 32, 1, &sel[which].time);
        notify_requestor(q, prop);
    } else if (q->target == utf8_string || q->target == a_plain || q->target == a_text || q->target == XCB_ATOM_STRING) {
        xcb_atom_t type = q->target == a_text ? utf8_string : q->target;
        size_t len = sel[which].len;
        uint8_t *data = malloc(len + 1);
        memcpy(data, sel[which].data, len);
        if (q->target == XCB_ATOM_STRING) {
            uint8_t *l = latin1(data, len, &len);
            free(data);
            data = l;
        }
        int slot = -1;
        for (int i = 0; i < 8 && len > PIECE; i++)
            if (!xfer[i].live) {
                slot = i;
                break;
            }
        if (len <= PIECE) {
            xcb_change_property(conn, XCB_PROP_MODE_REPLACE, q->requestor, prop, type, 8, (uint32_t) len, data);
            notify_requestor(q, prop);
            free(data);
        } else if (slot < 0) {
            notify_requestor(q, XCB_ATOM_NONE); /* eight transfers at once already */
            free(data);
        } else {
            uint32_t mask = XCB_EVENT_MASK_PROPERTY_CHANGE;
            xcb_change_window_attributes(conn, q->requestor, XCB_CW_EVENT_MASK, &mask);
            uint32_t hint = (uint32_t) len;
            xcb_change_property(conn, XCB_PROP_MODE_REPLACE, q->requestor, prop, a_incr, 32, 1, &hint);
            notify_requestor(q, prop);
            xfer[slot].win = q->requestor;
            xfer[slot].prop = prop;
            xfer[slot].type = type;
            xfer[slot].data = data;
            xfer[slot].len = len;
            xfer[slot].at = 0;
            xfer[slot].live = 1;
        }
    } else {
        notify_requestor(q, XCB_ATOM_NONE);
    }
    xcb_flush(conn);
}

/* A requestor deleted the property an INCR piece was in: the next piece,
 * and after the last an empty one, which ends it. */
static void transfer_step(xcb_property_notify_event_t *p) {
    if (p->window == window) last_time = p->time;
    if (p->state != XCB_PROPERTY_DELETE) return;
    for (int i = 0; i < 8; i++) {
        if (!xfer[i].live || xfer[i].win != p->window || xfer[i].prop != p->atom) continue;
        size_t n = xfer[i].len - xfer[i].at < PIECE ? xfer[i].len - xfer[i].at : PIECE;
        xcb_change_property(conn, XCB_PROP_MODE_REPLACE, p->window, p->atom, xfer[i].type, 8, (uint32_t) n, xfer[i].data + xfer[i].at);
        if (n == 0) {
            uint32_t none = 0;
            xcb_change_window_attributes(conn, p->window, XCB_CW_EVENT_MASK, &none);
            free(xfer[i].data);
            xfer[i].live = 0;
        }
        xfer[i].at += n;
        xcb_flush(conn);
        return;
    }
}

static void selection_clear(xcb_selection_clear_event_t *c) {
    int which = c->selection == XCB_ATOM_PRIMARY ? 0 : c->selection == a_clipboard ? 1 : -1;
    if (which < 0 || !sel[which].owned) return;
    sel[which].owned = 0;
    uint8_t r[2] = {10, (uint8_t) which};
    record(r, 2);
}

/* The window owns PRIMARY (0) or CLIPBOARD (1) with this text, from the
 * time of the last event the window had (ICCCM 2.1). */
geng_cancel visiterm_x11_select(int32_t which, void *text, geng_wait *wait) {
    geng_bytes *t = text;
    if (which == 0 || which == 1) {
        free(sel[which].data);
        sel[which].data = malloc((size_t) t->length + 1);
        memcpy(sel[which].data, t->data, (size_t) t->length);
        sel[which].len = (size_t) t->length;
        sel[which].time = last_time;
        sel[which].owned = 1;
        xcb_set_selection_owner(conn, window, which ? a_clipboard : XCB_ATOM_PRIMARY, last_time);
        xcb_flush(conn);
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* Every motion of the pointer over the window, or only those while a
 * button is held (docs/phase3-select.md §4): all while a program asks for
 * any motion (mode 1003), since over ssh -X each is 32 bytes on the wire. */
geng_cancel visiterm_x11_motion(int32_t all, geng_wait *wait) {
    if ((all != 0) != all_motion) {
        all_motion = all != 0;
        uint32_t mask = BASE_EVENTS | (all_motion ? XCB_EVENT_MASK_POINTER_MOTION : 0);
        xcb_change_window_attributes(conn, window, XCB_CW_EVENT_MASK, &mask);
        xcb_flush(conn);
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* Where the IME's candidate window belongs (V46): the cell's baseline, as
 * XIM's spot location is. Sent only when it moves. */
geng_cancel visiterm_x11_spot(int32_t x, int32_t y, geng_wait *wait) {
    if (have_xic && (x != spot_x || y != spot_y)) {
        spot_x = x;
        spot_y = y;
        xcb_point_t spot = {(int16_t) (x * cw), (int16_t) (y * ch + ascent)};
        xcb_xim_nested_list pre = xcb_xim_create_nested_list(xim, XCB_XIM_XNSpotLocation, &spot, NULL);
        xcb_xim_set_ic_values(xim, xic, NULL, NULL, XCB_XIM_XNPreeditAttributes, &pre, NULL);
        free(pre.data);
        xcb_flush(conn);
    }
    geng_succeed(wait, geng_slot_I4(0));
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

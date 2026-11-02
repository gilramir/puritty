/* Phase 2's survey probe (visiterm docs/phase2-window.md §5): a display list
 * drawn on X11 the way S§6.2 says, and C§6's glyph sets:
 *
 *   - everything is drawn into a retained pixmap, then the rows a frame
 *     touched are copied to the window, so an expose needs no redraw;
 *   - a scroll record is one CopyArea within the pixmap, up or down;
 *   - a run is one RenderFillRectangles for its background and a
 *     RenderCompositeGlyphs32 per stretch of one foreground colour;
 *   - a glyph is rasterised by FreeType and uploaded with RenderAddGlyphs
 *     the first time it is drawn, its id its code point.
 *
 * What the probe leaves out, said in §5: shaping (no HarfBuzz: one glyph a
 * code point, from the one face), fallback fonts, wide glyphs drawn at two
 * cells, the cursor, every event but an expose, and the colours of the
 * core's styles: a style id picks a colour from a fixed palette, which
 * costs the same requests. */
#define _GNU_SOURCE
#include <fontconfig/fontconfig.h>
#include <poll.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdlib.h>
#include <string.h>
#include <xcb/render.h>
#include <xcb/xcb.h>
#include <xcb/xcb_renderutil.h>

#include "geng.h"

static xcb_connection_t *conn;
static xcb_window_t window;
static xcb_pixmap_t pixmap;
static xcb_gcontext_t gc;
static xcb_render_picture_t target;
static xcb_render_glyphset_t glyphs;
static FT_Library library;
static FT_Face face;
static int cw, ch, ascent, cols, rows, uploaded;
static uint8_t loaded[0x110000 / 8];
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

geng_cancel probe_x_open(int32_t c, int32_t r, int32_t points, geng_wait *wait) {
    cols = c;
    rows = r;
    char *file = font_file("DejaVu Sans Mono");
    if (file == NULL || FT_Init_FreeType(&library) != 0 || FT_New_Face(library, file, 0, &face) != 0 ||
        FT_Set_Char_Size(face, 0, points * 64, 96, 96) != 0) {
        geng_succeed(wait, geng_slot_I4(-1));
        return (geng_cancel) {0};
    }
    cw = (int) (face->size->metrics.max_advance >> 6);
    ch = (int) (face->size->metrics.height >> 6);
    ascent = (int) (face->size->metrics.ascender >> 6);

    conn = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(conn)) {
        geng_succeed(wait, geng_slot_I4(-2));
        return (geng_cancel) {0};
    }
    xcb_screen_t *screen = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    const xcb_render_query_pict_formats_reply_t *formats = xcb_render_util_query_formats(conn);
    xcb_render_pictforminfo_t *a8 = xcb_render_util_find_standard_format(formats, XCB_PICT_STANDARD_A_8);
    xcb_render_pictvisual_t *visual = xcb_render_util_find_visual_format(formats, screen->root_visual);
    if (a8 == NULL || visual == NULL) {
        geng_succeed(wait, geng_slot_I4(-3));
        return (geng_cancel) {0};
    }
    int w = cols * cw, h = rows * ch;
    window = xcb_generate_id(conn);
    uint32_t values[2] = {screen->black_pixel, XCB_EVENT_MASK_EXPOSURE};
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, screen->root, 0, 0, (uint16_t) w, (uint16_t) h, 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual, XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK, values);
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

static void drain(void);

static void upload(uint32_t cp) {
    if (loaded[cp >> 3] & (1 << (cp & 7))) return;
    loaded[cp >> 3] |= (uint8_t) (1 << (cp & 7));
    uploaded++;
    FT_Load_Char(face, cp, FT_LOAD_RENDER);
    FT_Bitmap *b = &face->glyph->bitmap;
    int stride = ((int) b->width + 3) & ~3;
    size_t size = (size_t) stride * b->rows;
    uint8_t *data = calloc(size > 0 ? size : 4, 1);
    for (unsigned y = 0; y < b->rows; y++) memcpy(data + y * stride, b->buffer + y * b->pitch, b->width);
    xcb_render_glyphinfo_t info = {.width = (uint16_t) b->width, .height = (uint16_t) b->rows,
                                   .x = (int16_t) -face->glyph->bitmap_left, .y = (int16_t) face->glyph->bitmap_top,
                                   .x_off = (int16_t) cw, .y_off = 0};
    xcb_render_add_glyphs(conn, glyphs, 1, &cp, &info, (uint32_t) size, data);
    free(data);
}

/* A stretch of glyphs in one colour, at most 254 to an element. */
static void glyph_run(const uint32_t *ids, int n, int x, int y, uint32_t fg) {
    uint8_t buffer[8 + 254 * 4];
    for (int at = 0; at < n; at += 254) {
        int m = n - at < 254 ? n - at : 254;
        buffer[0] = (uint8_t) m;
        buffer[1] = buffer[2] = buffer[3] = 0;
        int16_t dx = (int16_t) ((x + at) * cw), dy = (int16_t) (y * ch + ascent);
        memcpy(buffer + 4, &dx, 2);
        memcpy(buffer + 6, &dy, 2);
        memcpy(buffer + 8, ids + at, (size_t) m * 4);
        xcb_render_composite_glyphs_32(conn, XCB_RENDER_PICT_OP_OVER, solid_of(fg), target, 0, glyphs, 0, 0,
                                       (uint32_t) (8 + m * 4), buffer);
    }
}

geng_cancel probe_x_draw(void *list, geng_wait *wait) {
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
            const uint8_t *cell = p + 7;
            uint32_t ids[1024];
            int style0 = (cell[3] << 8) | cell[4];
            xcb_rectangle_t r = {(int16_t) (x * cw), (int16_t) (y * ch), (uint16_t) (n * cw), (uint16_t) ch};
            xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(bg_of(style0)), 1, &r);
            int from = 0, style = style0;
            for (int i = 0; i <= n; i++) {
                int s = i < n ? (cell[i * 5 + 3] << 8) | cell[i * 5 + 4] : -1;
                if (s != style) {
                    glyph_run(ids + from, i - from, x + from, y, fg_of(style));
                    from = i;
                    style = s;
                }
                if (i < n) {
                    uint32_t cp = ((uint32_t) cell[i * 5] << 16) | ((uint32_t) cell[i * 5 + 1] << 8) | cell[i * 5 + 2];
                    if (cp == 0 || cp >= 0x110000) cp = ' ';
                    upload(cp);
                    ids[i] = cp;
                }
            }
            if (y < first) first = y;
            if (y > last) last = y;
            p += 7 + n * 5;
        }
    }
    if (last >= first)
        xcb_copy_area(conn, pixmap, window, gc, 0, (int16_t) (first * ch), 0, (int16_t) (first * ch), (uint16_t) (cols * cw),
                      (uint16_t) ((last - first + 1) * ch));
    xcb_flush(conn);
    drain();
    geng_succeed(wait, geng_slot_I4(uploaded));
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

static void drain(void) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(conn)) != NULL) {
        if ((e->response_type & 0x7f) == XCB_EXPOSE) {
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

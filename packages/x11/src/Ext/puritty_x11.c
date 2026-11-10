/* puritty's window on X11 (docs/renderer.md, V34-V37): the C that only C
 * can do. Geng decides what is drawn and sends it as a display list
 * (`Vt.View`'s comment is its definition); packages/text executes it
 * (docs/windows.md V52), drawing through the calls this file gives it:
 *
 *   - its target is a retained pixmap the size of the screen's cells, and
 *     the rows a frame touched are copied to the window, so an expose needs
 *     no redraw; a scroll is one CopyArea within the pixmap;
 *   - a fill is a RenderFillRectangles;
 *   - a glyph is uploaded to a glyph set with RenderAddGlyphs, and the
 *     glyphs placed are drawn a RenderCompositeGlyphs32 for each stretch of
 *     one foreground; a colour glyph is an ARGB32 picture (§13.10);
 *   - when the renderer begins its glyphs again (V37), the glyph set is
 *     freed and a new one begun. The pixmap keeps what was drawn with the
 *     old one, so nothing is redrawn;
 *   - a face is found by fontconfig: the primary font by its name, a
 *     fallback by the cluster it must have (V26).
 *
 * And it turns the X server's events into records Geng decodes.
 *
 * One window a process (geng-plan.md Q6), so the state is this file's.
 *
 * Events (V36), the records `puritty_x11_take` answers, each a kind byte:
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
 *     §14): 0 PRIMARY, 1 CLIPBOARD;
 *  11 a paste's text has come (docs/phase3-select.md §15): 1 when more is
 *     to come, 0 when it is the last; `puritty_x11_pasted` takes it.
 *
 * Keys go through XIM when an input method is there (V44-V46,
 * docs/phase3-input.md §3): xcb-imdkit, patched (patches/), with an input
 * context whose preedit puritty draws (on-the-spot). Every press and
 * release is sent to the IME, and a key it gives back is recorded then,
 * read with its own event's modifiers; its commits and preedits are
 * recorded as they come, in their order. The context is never destroyed
 * while the window lives: a focus change only sets or unsets its focus
 * (§3.4). Without an IME, keys are recorded as they come.
 * An expose is answered here, from the pixmap.
 *
 * X11_STATS=1 prints counts when the program ends; X11_SHOT=FILE writes
 * the window then, as `puritty_x11_shot` does. */
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
#include <xcb/xcb_cursor.h>
#include <xcb/xcbext.h> /* xcb_poll_for_reply, for a paste read without waiting */
#include <xcb/xcb_renderutil.h>
#include <xcb/xkb.h>
#include <xkbcommon/xkbcommon-x11.h>
#include <xcb/randr.h>
#include <xcb-imdkit/imclient.h>
#include <xcb-imdkit/encoding.h>

#include "geng.h"
#include "puritty_text.h"

static xcb_connection_t *conn;
static xcb_screen_t *screen;
static xcb_window_t window;
/* The pointer over the window: the theme's I-beam over text, and its arrow
 * while the program takes the mouse (docs/phase3-select.md §21). */
static xcb_cursor_t pointer_text, pointer_arrow;
static xcb_pixmap_t pixmap;
static xcb_gcontext_t gc;
static xcb_render_picture_t target;
static xcb_render_pictformat_t a8, argb32, visual_format;
static xcb_render_glyphset_t glyphs;
static double ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e9 + t.tv_nsec;
}

/* The screen's resolution (V50). */
static int dpi0 = 96;
/* The window in cells, as its size was last reported. */
static int win_cols, win_rows, focused = -1, win_w, win_h;
static uint32_t margin_bg = 0xFFFFFFFF;

static xcb_atom_t wm_protocols, wm_delete, net_wm_name, utf8_string;

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

/* THE RENDERER'S CALLS (packages/text, include/puritty_text.h) */

/* A font as fontconfig names it, in a variant: `:bold`, `:italic` or
 * both added to its name. */
char *pt_font_file(const char *font, int variant, int *index) {
    static const char *const variants[4] = {"", ":bold", ":italic", ":bold:italic"};
    size_t len = strlen(font) + strlen(variants[variant & 3]) + 1;
    char *spec = malloc(len);
    snprintf(spec, len, "%s%s", font, variants[variant & 3]);
    FcPattern *p = FcNameParse((const FcChar8 *) spec);
    free(spec);
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

static int font_order(const void *a, const void *b) {
    const char *x = *(char *const *) a, *y = *(char *const *) b;
    for (; *x && *y; x++, y++) {
        int cx = (*x >= 'A' && *x <= 'Z') ? *x + 32 : *x, cy = (*y >= 'A' && *y <= 'Z') ? *y + 32 : *y;
        if (cx != cy) return cx - cy;
    }
    return (unsigned char) *x - (unsigned char) *y;
}

/* Families as the window's answer: sorted, a line each, then freed. */
static geng_bytes *family_lines(char **names, int n) {
    qsort(names, (size_t) n, sizeof *names, font_order);
    size_t len = 0;
    for (int i = 0; i < n; i++) len += strlen(names[i]) + 1;
    geng_bytes *b = geng_alloc_atomic(sizeof *b + len, GENG_HEADER_BYTES(sizeof *b + len));
    b->length = (int32_t) len;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    size_t at = 0;
    for (int i = 0; i < n; i++) {
        size_t m = strlen(names[i]);
        memcpy(b->data + at, names[i], m);
        b->data[at + m] = '\n';
        at += m + 1;
        free(names[i]);
    }
    free(names);
    return b;
}

/* The families of the monospace fonts fontconfig has, for the settings
 * window (docs/settings.md ST8): spacing mono, dual (most CJK monospace
 * fonts) or charcell, each once, and not colour (an emoji font is
 * monospace to fontconfig, and is no terminal's font), as Windows' list. */
geng_cancel puritty_x11_fonts(geng_wait *wait) {
    FcPattern *p = FcPatternCreate();
    FcObjectSet *os = FcObjectSetBuild(FC_FAMILY, FC_SPACING, FC_COLOR, NULL);
    FcFontSet *set = FcFontList(NULL, p, os);
    char **names = NULL;
    int n = 0;
    for (int i = 0; set != NULL && i < set->nfont; i++) {
        int spacing;
        FcChar8 *family;
        if (FcPatternGetInteger(set->fonts[i], FC_SPACING, 0, &spacing) != FcResultMatch || spacing < FC_DUAL) continue;
        FcBool colour;
        if (FcPatternGetBool(set->fonts[i], FC_COLOR, 0, &colour) == FcResultMatch && colour) continue;
        if (FcPatternGetString(set->fonts[i], FC_FAMILY, 0, &family) != FcResultMatch) continue;
        int seen = 0;
        for (int k = 0; k < n && !seen; k++) seen = strcmp(names[k], (const char *) family) == 0;
        if (seen) continue;
        names = realloc(names, (size_t) (n + 1) * sizeof *names);
        names[n++] = strdup((const char *) family);
    }
    if (set != NULL) FcFontSetDestroy(set);
    FcObjectSetDestroy(os);
    FcPatternDestroy(p);
    geng_succeed(wait, geng_slot_P(family_lines(names, n)));
    return (geng_cancel) {0};
}

/* Code points that select a form rather than need a glyph of their own. */
static int ignorable(uint32_t cp) {
    return cp == 0x200D || cp == 0x200C || (cp >= 0xFE00 && cp <= 0xFE0F) || (cp >= 0xE0100 && cp <= 0xE01EF);
}

/* The face fontconfig gives a monospace font with the cluster, in the
 * language, colour when asked (V26). */
char *pt_fallback_file(const uint32_t *cps, int n, int colour, const char *lang, int *index) {
    FcPattern *p = FcNameParse((const FcChar8 *) "monospace");
    if (lang) FcPatternAddString(p, FC_LANG, (const FcChar8 *) lang);
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
    char *out = NULL;
    FcChar8 *file;
    *index = 0;
    if (m && FcPatternGetString(m, FC_FILE, 0, &file) == FcResultMatch) {
        FcPatternGetInteger(m, FC_INDEX, 0, index);
        out = strdup((const char *) file);
    }
    if (m) FcPatternDestroy(m);
    return out;
}

void pt_fill(uint32_t rgb, int x, int y, int w, int h) {
    xcb_rectangle_t r = {(int16_t) x, (int16_t) y, (uint16_t) w, (uint16_t) h};
    xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(rgb), 1, &r);
}

void pt_fill_rects(uint32_t rgb, const PtRect *rects, int n) {
    static xcb_rectangle_t rs[4096];
    if (n > 4096) n = 4096;
    for (int i = 0; i < n; i++)
        rs[i] = (xcb_rectangle_t) {(int16_t) rects[i].x, (int16_t) rects[i].y, (uint16_t) rects[i].w, (uint16_t) rects[i].h};
    xcb_render_fill_rectangles(conn, XCB_RENDER_PICT_OP_SRC, target, colour(rgb), (uint32_t) n, rs);
}

/* A glyph uploaded to the glyph set (§13.10): its advance on the server is
 * fixed then, and the pen moves by it inside an element. */
void pt_glyph_add(uint32_t id, const PtGlyph *g) {
    xcb_render_glyphinfo_t info = {.width = (uint16_t) g->width, .height = (uint16_t) g->height, .x = (int16_t) -g->left,
                                   .y = (int16_t) g->top, .x_off = (int16_t) g->advance, .y_off = 0};
    size_t size = (size_t) g->stride * (size_t) g->height;
    xcb_render_add_glyphs(conn, glyphs, 1, &id, &info, (uint32_t) size, g->data);
}

/* The glyph set freed and a new one begun (V37). */
void pt_glyphs_reset(void) {
    xcb_render_free_glyph_set(conn, glyphs);
    glyphs = xcb_generate_id(conn);
    xcb_render_create_glyph_set(conn, glyphs, a8);
}

/* Each stretch of one foreground colour as one CompositeGlyphs32, a new
 * element where a glyph is not where the last one's advance left the pen. */
void pt_glyphs_draw(const PtPlaced *placed, int nplaced, const PtRect *clips) {
    static uint8_t buffer[65536];
    int i = 0;
    while (i < nplaced) {
        uint32_t fg = placed[i].fg;
        int clip = placed[i].clip;
        int len = 0, penx = 0, peny = 0, count_at = -1, count = 0;
        for (; i < nplaced && placed[i].fg == fg && placed[i].clip == clip && len < 60000; i++) {
            const PtPlaced *P = &placed[i];
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
        }
        if (clip >= 0) {
            xcb_rectangle_t r = {(int16_t) clips[clip].x, (int16_t) clips[clip].y, (uint16_t) clips[clip].w, (uint16_t) clips[clip].h};
            xcb_render_set_picture_clip_rectangles(conn, target, 0, 0, 1, &r);
        }
        xcb_render_composite_glyphs_32(conn, XCB_RENDER_PICT_OP_OVER, solid_of(fg), target, 0, glyphs, 0, 0, (uint32_t) len,
                                       buffer);
        if (clip >= 0) {
            uint32_t none = XCB_NONE;
            xcb_render_change_picture(conn, target, XCB_RENDER_CP_CLIP_MASK, &none);
        }
    }
}

/* A colour glyph as an ARGB32 picture. */
void *pt_picture_add(const uint32_t *argb, int w, int h) {
    xcb_pixmap_t pm = xcb_generate_id(conn);
    xcb_create_pixmap(conn, 32, pm, window, (uint16_t) w, (uint16_t) h);
    xcb_gcontext_t g32 = xcb_generate_id(conn);
    xcb_create_gc(conn, g32, pm, 0, NULL);
    xcb_put_image(conn, XCB_IMAGE_FORMAT_Z_PIXMAP, pm, g32, (uint16_t) w, (uint16_t) h, 0, 0, 0, 32, (uint32_t) w * h * 4,
                  (const uint8_t *) argb);
    xcb_free_gc(conn, g32);
    xcb_render_picture_t picture = xcb_generate_id(conn);
    xcb_render_create_picture(conn, picture, pm, argb32, 0, NULL);
    xcb_free_pixmap(conn, pm);
    return (void *) (uintptr_t) picture;
}

void pt_picture_draw(void *picture, int x, int y, int w, int h) {
    xcb_render_composite(conn, XCB_RENDER_PICT_OP_OVER, (xcb_render_picture_t) (uintptr_t) picture, 0, target, 0, 0, 0, 0,
                         (int16_t) x, (int16_t) y, (uint16_t) w, (uint16_t) h);
}

void pt_picture_free(void *picture) { xcb_render_free_picture(conn, (xcb_render_picture_t) (uintptr_t) picture); }

/* THE PIXMAP AND THE WINDOW */

/* A pixmap for a screen of c by r cells; the frame that says the size
 * draws every cell into it. */
void pt_target(int c, int r) {
    if (pixmap) {
        xcb_render_free_picture(conn, target);
        xcb_free_pixmap(conn, pixmap);
    }
    pixmap = xcb_generate_id(conn);
    xcb_create_pixmap(conn, screen->root_depth, pixmap, window, (uint16_t) (c * pt_cw), (uint16_t) (r * pt_ch));
    target = xcb_generate_id(conn);
    xcb_render_create_picture(conn, target, pixmap, visual_format, 0, NULL);
    margin_bg = 0xFFFFFFFF;
}

void pt_scroll(int top, int bottom, int k) {
    xcb_copy_area(conn, pixmap, pixmap, gc, 0, (int16_t) ((top + k) * pt_ch), 0, (int16_t) (top * pt_ch), (uint16_t) (pt_cols * pt_cw),
                  (uint16_t) ((bottom - top + 1) * pt_ch));
}

/* The window past the screen's cells, in the default background: its
 * background pixel, which the server also fills an expose with. A
 * TrueColor visual of 24 bits is taken, whose pixel is its RGB. */
static void margins(void) {
    uint32_t bg = pt_default_bg();
    if (bg == margin_bg) return;
    margin_bg = bg;
    xcb_change_window_attributes(conn, window, XCB_CW_BACK_PIXEL, &bg);
    xcb_clear_area(conn, 0, window, (int16_t) (pt_cols * pt_cw), 0, 0, 0);
    xcb_clear_area(conn, 0, window, 0, (int16_t) (pt_rows * pt_ch), 0, 0);
}

static void stats(void) {
    if (getenv("X11_STATS")) pt_stats("x11");
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
 * unless puritty_x11_motion asks for all of it. */
#define BASE_EVENTS                                                                                                  \
    (XCB_EVENT_MASK_EXPOSURE | XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_KEY_RELEASE | XCB_EVENT_MASK_FOCUS_CHANGE | \
     XCB_EVENT_MASK_STRUCTURE_NOTIFY | XCB_EVENT_MASK_BUTTON_PRESS | XCB_EVENT_MASK_BUTTON_RELEASE |                \
     XCB_EVENT_MASK_BUTTON_MOTION | XCB_EVENT_MASK_PROPERTY_CHANGE)
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
    int c = w / pt_cw, r = h / pt_ch;
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
                     (uint8_t) (pt_cw >> 8), (uint8_t) pt_cw, (uint8_t) (pt_ch >> 8), (uint8_t) pt_ch};
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
static void paste_notify(xcb_selection_notify_event_t *n);
static void paste_poll(void);
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
    xcb_point_t spot = {0, (int16_t) pt_ascent};
    xcb_xim_nested_list pre = xcb_xim_create_nested_list(m, XCB_XIM_XNSpotLocation, &spot, NULL);
    xcb_xim_create_ic(m, xim_made, NULL, XCB_XIM_XNInputStyle, &style, XCB_XIM_XNClientWindow, &window,
                      XCB_XIM_XNFocusWindow, &window, XCB_XIM_XNPreeditAttributes, &pre, NULL);
    free(pre.data);
}

static void xim_quiet(const char *fmt, ...) { (void) fmt; }

static void xim_setup(int screen_number) {
    if (getenv("PURITTY_NO_XIM")) return;
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
        else if (type == XCB_SELECTION_NOTIFY) paste_notify((xcb_selection_notify_event_t *) e);
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
    paste_poll();
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

/* The screen's resolution (V50, docs/phase3-input.md §7): `Xft.dpi` from
 * the resources the desktop set on the root window, which its scale
 * setting writes and GTK, Qt and Xft size their fonts by; else the primary
 * monitor's size from RandR; else 96. The X screen's own size in
 * millimetres is the server's arithmetic for 96, and says nothing. */
static int screen_dpi(void) {
    const char *forced = getenv("PURITTY_DPI");
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
/* One of the cursor font's glyphs, the core protocol's own cursors, for a
 * server with no cursor theme to load from: its I-beam is XC_xterm (152)
 * and its arrow XC_left_ptr (68), each with its mask the glyph after it. */
static xcb_cursor_t font_cursor(uint16_t glyph) {
    xcb_font_t font = xcb_generate_id(conn);
    xcb_open_font(conn, font, 6, "cursor");
    xcb_cursor_t c = xcb_generate_id(conn);
    xcb_create_glyph_cursor(conn, c, font, font, glyph, glyph + 1, 0, 0, 0, 0xffff, 0xffff, 0xffff);
    xcb_close_font(conn, font);
    return c;
}

/* The two pointers, from the user's cursor theme as other programs load
 * them (Xcursor's theme and size, through xcb-util-cursor), by the names
 * the freedesktop cursor spec gives and the older ones a theme may have
 * instead; the cursor font's when no theme answers. The window starts
 * with the I-beam. */
static void pointers_setup(void) {
    /* Nix's xcb-util-cursor searches its own store path and the home
     * directory's, not /usr/share/icons where a distribution's themes are;
     * libXcursor's own path, as other programs search it, unless the user
     * named one */
    setenv("XCURSOR_PATH", "~/.local/share/icons:~/.icons:/usr/share/icons:/usr/share/pixmaps", 0);
    xcb_cursor_context_t *ctx = NULL;
    if (xcb_cursor_context_new(conn, screen, &ctx) >= 0) {
        pointer_text = xcb_cursor_load_cursor(ctx, "text");
        if (pointer_text == XCB_CURSOR_NONE) pointer_text = xcb_cursor_load_cursor(ctx, "xterm");
        pointer_arrow = xcb_cursor_load_cursor(ctx, "default");
        if (pointer_arrow == XCB_CURSOR_NONE) pointer_arrow = xcb_cursor_load_cursor(ctx, "left_ptr");
        xcb_cursor_context_free(ctx);
    }
    if (pointer_text == XCB_CURSOR_NONE) pointer_text = font_cursor(152);
    if (pointer_arrow == XCB_CURSOR_NONE) pointer_arrow = font_cursor(68);
    xcb_change_window_attributes(conn, window, XCB_CW_CURSOR, &pointer_text);
}

geng_cancel puritty_x11_open(int32_t c, int32_t r, int32_t points, void *font_bytes, void *lang_bytes, int32_t cap,
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
    pt_verbose = getenv("X11_STATS") != NULL;
    char *font = string_of(font_bytes);
    char *lang = string_of(lang_bytes);
    FcInit();
    int opened = pt_open(font, lang, points, dpi0, cap);
    free(font);
    free(lang);
    if (opened != 0) {
        geng_succeed(wait, geng_slot_I4(-1));
        return (geng_cancel) {0};
    }
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
    win_w = c * pt_cw;
    win_h = r * pt_ch;
    window = xcb_generate_id(conn);
    uint32_t values[2] = {screen->black_pixel, BASE_EVENTS};
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, screen->root, 0, 0, (uint16_t) (c * pt_cw), (uint16_t) (r * pt_ch), 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual, XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK, values);
    wm_protocols = atom("WM_PROTOCOLS");
    wm_delete = atom("WM_DELETE_WINDOW");
    net_wm_name = atom("_NET_WM_NAME");
    utf8_string = atom("UTF8_STRING");
    selection_atoms();
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, wm_protocols, XCB_ATOM_ATOM, 32, 1, &wm_delete);
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_CLASS, XCB_ATOM_STRING, 8, 18, "puritty\0Puritty\0");
    /* WM_NORMAL_HINTS (ICCCM 4.1.2.3): a minimum of one cell, the base 0,
     * and a step of a cell. Flags: PMinSize 16, PResizeInc 64, PBaseSize 256. */
    uint32_t hints[18] = {16 | 64 | 256, 0, 0, 0, 0, (uint32_t) pt_cw, (uint32_t) pt_ch, 0, 0, (uint32_t) pt_cw, (uint32_t) pt_ch, 0, 0, 0, 0, 0, 0, 0};
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_NORMAL_HINTS, XCB_ATOM_WM_SIZE_HINTS, 32, 18, hints);
    geng_bytes *t = title_bytes;
    set_title(t->data, (int) t->length);
    key_setup();
    gc = xcb_generate_id(conn);
    uint32_t no_exposures = 0;
    xcb_create_gc(conn, gc, window, XCB_GC_GRAPHICS_EXPOSURES, &no_exposures);
    glyphs = xcb_generate_id(conn);
    xcb_render_create_glyph_set(conn, glyphs, a8);
    pt_resize(c, r);
    pointers_setup();
    xcb_map_window(conn, window);
    xim_setup(screen_number);
    xcb_flush(conn);
    geng_succeed(wait, geng_slot_I4(pt_cw * 65536 + pt_ch));
    return (geng_cancel) {0};
}

/* Executes one frame's display list. Answers 0, or -1 once the connection
 * has failed. */
geng_cancel puritty_x11_draw(void *list, geng_wait *wait) {
    geng_bytes *b = list;
    PtFrame frame;
    pt_frame(b->data, (size_t) b->length, &frame);
    int first = frame.first, last = frame.last, sized = frame.sized;
    if (last >= first)
        xcb_copy_area(conn, pixmap, window, gc, 0, (int16_t) (first * pt_ch), 0, (int16_t) (first * pt_ch), (uint16_t) (pt_cols * pt_cw),
                      (uint16_t) ((last - first + 1) * pt_ch));
    if (sized || pt_default_bg() != margin_bg) margins();
    xcb_flush(conn);
    drain();
    int inklen;
    const uint8_t *inkbuf = pt_ink(&inklen);
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
 * record does the loop wait on the descriptor. `puritty_x11_events`
 * answers that records are there and takes none, since `Task.race` drops a
 * losing branch's answer when two answer in one round (§12);
 * `puritty_x11_take`, after the race, takes them. */
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

geng_cancel puritty_x11_events(geng_wait *wait) {
    if (answer(wait)) return (geng_cancel) {0};
    xwait *w = geng_alloc(sizeof *w, XWAIT_HEADER);
    *w = (xwait) {.wait = wait, .io = NULL};
    w->io = geng_io_wait(xcb_get_file_descriptor(conn), POLLIN, x_ready, w);
    geng_write_barrier(w, &w->io, w->io);
    return (geng_cancel) {x_stop, w};
}

/* The records since the last take. */
geng_cancel puritty_x11_take(geng_wait *wait) {
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
/* The window fitted to a new cell: its size hints, and the cells that now
 * fit it reported as a new size. */
static void refit(void) {
    uint32_t hints[18] = {16 | 64 | 256, 0, 0, 0, 0, (uint32_t) pt_cw, (uint32_t) pt_ch, 0, 0, (uint32_t) pt_cw, (uint32_t) pt_ch, 0, 0, 0, 0, 0, 0, 0};
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, window, XCB_ATOM_WM_NORMAL_HINTS, XCB_ATOM_WM_SIZE_HINTS, 32, 18, hints);
    xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(conn, xcb_get_geometry(conn, window), NULL);
    if (g) {
        win_cols = -1;
        size_in(g->width, g->height);
        free(g);
    }
    pt_resize(win_cols, win_rows);
    spot_x = spot_y = -1;
    xcb_flush(conn);
}

geng_cancel puritty_x11_zoom(int32_t points, geng_wait *wait) {
    if (pt_zoom(points, dpi0)) refit();
    geng_succeed(wait, geng_slot_I4(pt_cw * 65536 + pt_ch));
    return (geng_cancel) {0};
}

/* Another font, fallback language, size or glyph cache (docs/settings.md
 * ST4): answers the new cell, or -1 with the font kept when there is no
 * such font. */
geng_cancel puritty_x11_setfont(int32_t points, void *font_bytes, void *lang_bytes, int32_t cap, geng_wait *wait) {
    char *font = string_of(font_bytes), *lang = string_of(lang_bytes);
    int done = pt_refont(font, lang, points, dpi0, cap);
    free(font);
    free(lang);
    if (done == 0) refit();
    geng_succeed(wait, geng_slot_I4(done == 0 ? pt_cw * 65536 + pt_ch : -1));
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
static xcb_atom_t a_clipboard, a_targets, a_timestamp, a_text, a_plain, a_incr, a_paste;
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
    const char *names[] = {"CLIPBOARD", "TARGETS", "TIMESTAMP", "TEXT", "text/plain;charset=utf-8", "INCR", "PURITTY_PASTE"};
    xcb_atom_t *out[] = {&a_clipboard, &a_targets, &a_timestamp, &a_text, &a_plain, &a_incr, &a_paste};
    xcb_intern_atom_cookie_t ck[7];
    for (int i = 0; i < 7; i++) ck[i] = xcb_intern_atom(conn, 0, (uint16_t) strlen(names[i]), names[i]);
    for (int i = 0; i < 7; i++) {
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
static void paste_read(void);
static struct {
    int active, incr, waiting, which, pending;
    xcb_atom_t target;
    xcb_get_property_cookie_t cookie;
    double started;
} pst;
static uint8_t *pbuf;
static size_t plen, pcap;

static void transfer_step(xcb_property_notify_event_t *p) {
    if (p->window == window) {
        last_time = p->time;
        /* the owner put an INCR piece in the paste's property. The owner
         * writes it as soon as a read deletes the last, so it can come
         * before that read's reply is taken: then it is read after it. */
        if (p->atom == a_paste && p->state == XCB_PROPERTY_NEW_VALUE && pst.active) {
            if (pst.incr && !pst.waiting) paste_read();
            else pst.pending = 1;
        }
        return;
    }
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

/* PASTE (docs/phase3-select.md §15)
 *
 * A paste asks the owner for UTF8_STRING, and for STRING if it has not
 * that; the property is read with a request whose reply is taken when it
 * comes (paste_poll, at the end of each drain), never waited for, so a
 * paste of megabytes over ssh -X does not stop the window. INCR pieces
 * are read as the owner puts them. What comes is kept here, UTF-8, and
 * a record says so; Geng takes it with puritty_x11_pasted. One paste at
 * a time: another asked for while one is under way is not made, unless
 * the first has waited 10 s for an owner that never answered. */

static void paste_add(const uint8_t *d, size_t n) {
    if (plen + n > pcap) {
        pcap = (plen + n) * 2;
        pbuf = realloc(pbuf, pcap);
    }
    memcpy(pbuf + plen, d, n);
    plen += n;
}

static void paste_done(int more) {
    uint8_t r[2] = {11, (uint8_t) more};
    record(r, 2);
    if (!more) pst.active = 0;
}

static void paste_read(void) {
    /* any new value seen until now is what this reads */
    pst.pending = 0;
    pst.cookie = xcb_get_property(conn, 1, window, a_paste, XCB_GET_PROPERTY_TYPE_ANY, 0, UINT32_MAX / 4);
    pst.waiting = 1;
    xcb_flush(conn);
}

static void paste_ask(xcb_atom_t target) {
    pst.target = target;
    xcb_delete_property(conn, window, a_paste);
    xcb_convert_selection(conn, window, pst.which ? a_clipboard : XCB_ATOM_PRIMARY, target, a_paste, last_time);
    xcb_flush(conn);
}

static void paste_notify(xcb_selection_notify_event_t *n) {
    if (!pst.active || n->requestor != window) return;
    if (n->property == XCB_ATOM_NONE) {
        if (pst.target == utf8_string) paste_ask(XCB_ATOM_STRING); /* an owner of Latin-1 alone */
        else paste_done(0);                                       /* nothing to paste */
        return;
    }
    paste_read();
}

static void paste_poll(void) {
    if (!pst.waiting) return;
    xcb_get_property_reply_t *r = NULL;
    xcb_generic_error_t *err = NULL;
    if (!xcb_poll_for_reply(conn, pst.cookie.sequence, (void **) &r, &err)) return;
    pst.waiting = 0;
    free(err);
    if (!r) {
        paste_done(0);
        return;
    }
    int len = xcb_get_property_value_length(r);
    if (r->type == a_incr) {
        /* the owner sends pieces as the property is deleted, which the read did */
        pst.incr = 1;
        if (pst.pending) paste_read();
    } else {
        const uint8_t *d = xcb_get_property_value(r);
        if (r->type == XCB_ATOM_STRING) {
            for (int i = 0; i < len; i++) {
                uint8_t u[2] = {(uint8_t) (0xC0 | d[i] >> 6), (uint8_t) (0x80 | (d[i] & 63))};
                if (d[i] < 0x80) paste_add(d + i, 1);
                else paste_add(u, 2);
            }
        } else {
            paste_add(d, (size_t) len);
        }
        if (!pst.incr) paste_done(0);
        else paste_done(len > 0);
        if (pst.incr && len > 0 && pst.pending) paste_read();
    }
    free(r);
}

/* A paste of PRIMARY (0) or CLIPBOARD (1). Answers 1 when it is asked
 * for, 0 when another is under way. */
geng_cancel puritty_x11_paste(int32_t which, geng_wait *wait) {
    int asked = 0;
    if (pst.active && ns() - pst.started > 10e9) pst.active = 0;
    if (!pst.active && (which == 0 || which == 1)) {
        pst.active = 1;
        pst.incr = 0;
        pst.waiting = 0;
        pst.pending = 0;
        pst.which = which;
        pst.started = ns();
        plen = 0;
        paste_ask(utf8_string);
        asked = 1;
    }
    geng_succeed(wait, geng_slot_I4(asked));
    return (geng_cancel) {0};
}

/* What a paste has brought since it was last taken, UTF-8. */
geng_cancel puritty_x11_pasted(geng_wait *wait) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b + plen, GENG_HEADER_BYTES(sizeof *b + plen));
    b->length = (int64_t) plen;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    if (plen) memcpy(b->data, pbuf, plen);
    plen = 0;
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}

/* The window owns PRIMARY (0) or CLIPBOARD (1) with this text, from the
 * time of the last event the window had (ICCCM 2.1). */
geng_cancel puritty_x11_select(int32_t which, void *text, geng_wait *wait) {
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
geng_cancel puritty_x11_motion(int32_t all, geng_wait *wait) {
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
geng_cancel puritty_x11_spot(int32_t x, int32_t y, geng_wait *wait) {
    if (have_xic && (x != spot_x || y != spot_y)) {
        spot_x = x;
        spot_y = y;
        xcb_point_t spot = {(int16_t) (x * pt_cw), (int16_t) (y * pt_ch + pt_ascent)};
        xcb_xim_nested_list pre = xcb_xim_create_nested_list(xim, XCB_XIM_XNSpotLocation, &spot, NULL);
        xcb_xim_set_ic_values(xim, xic, NULL, NULL, XCB_XIM_XNPreeditAttributes, &pre, NULL);
        free(pre.data);
        xcb_flush(conn);
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* The pointer over the window: 0 the I-beam, 1 the arrow. */
geng_cancel puritty_x11_pointer(int32_t arrow, geng_wait *wait) {
    xcb_cursor_t c = arrow ? pointer_arrow : pointer_text;
    xcb_change_window_attributes(conn, window, XCB_CW_CURSOR, &c);
    xcb_flush(conn);
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_x11_title(void *text, geng_wait *wait) {
    geng_bytes *t = text;
    set_title(t->data, (int) t->length);
    xcb_flush(conn);
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* RAISING ANOTHER WINDOW (docs/settings.md ST8)
 *
 * A window of this display whose title is `name`, brought forward, on a
 * connection of its own, since it is asked before this process has a
 * window: the window manager's `_NET_CLIENT_LIST`, or with none the root's
 * children and theirs, searched by `_NET_WM_NAME` and `WM_NAME`; one found
 * is asked active with `_NET_ACTIVE_WINDOW` and raised and focused itself,
 * for a display with no window manager. Answers 1 when one was found. */

static xcb_atom_t atom_on(xcb_connection_t *c, const char *name) {
    xcb_intern_atom_reply_t *r = xcb_intern_atom_reply(c, xcb_intern_atom(c, 0, (uint16_t) strlen(name), name), NULL);
    xcb_atom_t a = r ? r->atom : XCB_ATOM_NONE;
    free(r);
    return a;
}

static int titled(xcb_connection_t *c, xcb_window_t w, const char *name, xcb_atom_t net_name, xcb_atom_t utf8) {
    const xcb_atom_t props[2] = {net_name, XCB_ATOM_WM_NAME};
    const xcb_atom_t types[2] = {utf8, XCB_ATOM_STRING};
    for (int k = 0; k < 2; k++) {
        xcb_get_property_reply_t *r = xcb_get_property_reply(c, xcb_get_property(c, 0, w, props[k], types[k], 0, 1024), NULL);
        if (r == NULL) continue;
        int len = xcb_get_property_value_length(r);
        int same_name = len == (int) strlen(name) && memcmp(xcb_get_property_value(r), name, (size_t) len) == 0;
        free(r);
        if (same_name) return 1;
    }
    return 0;
}

geng_cancel puritty_x11_raise(void *name_bytes, geng_wait *wait) {
    char *name = string_of(name_bytes);
    int found = 0;
    xcb_connection_t *c = xcb_connect(NULL, NULL);
    if (!xcb_connection_has_error(c)) {
        xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(c)).data;
        xcb_atom_t clients = atom_on(c, "_NET_CLIENT_LIST"), active = atom_on(c, "_NET_ACTIVE_WINDOW");
        xcb_atom_t net_name = atom_on(c, "_NET_WM_NAME"), utf8 = atom_on(c, "UTF8_STRING");
        xcb_window_t *ws = NULL;
        int n = 0;
        xcb_get_property_reply_t *list = xcb_get_property_reply(c, xcb_get_property(c, 0, s->root, clients, XCB_ATOM_WINDOW, 0, 4096), NULL);
        if (list != NULL && xcb_get_property_value_length(list) > 0) {
            n = xcb_get_property_value_length(list) / 4;
            ws = malloc((size_t) n * sizeof *ws);
            memcpy(ws, xcb_get_property_value(list), (size_t) n * sizeof *ws);
        } else {
            xcb_query_tree_reply_t *t = xcb_query_tree_reply(c, xcb_query_tree(c, s->root), NULL);
            for (int i = 0; t != NULL && i < xcb_query_tree_children_length(t); i++) {
                xcb_window_t top = xcb_query_tree_children(t)[i];
                ws = realloc(ws, (size_t) (n + 1) * sizeof *ws);
                ws[n++] = top;
                xcb_query_tree_reply_t *u = xcb_query_tree_reply(c, xcb_query_tree(c, top), NULL);
                for (int j = 0; u != NULL && j < xcb_query_tree_children_length(u); j++) {
                    ws = realloc(ws, (size_t) (n + 1) * sizeof *ws);
                    ws[n++] = xcb_query_tree_children(u)[j];
                }
                free(u);
            }
            free(t);
        }
        free(list);
        for (int i = 0; i < n && !found; i++) {
            if (!titled(c, ws[i], name, net_name, utf8)) continue;
            found = 1;
            xcb_client_message_event_t ev = {0};
            ev.response_type = XCB_CLIENT_MESSAGE;
            ev.format = 32;
            ev.window = ws[i];
            ev.type = active;
            ev.data.data32[0] = 1;
            ev.data.data32[1] = XCB_CURRENT_TIME;
            xcb_send_event(c, 0, s->root, XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT | XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY, (const char *) &ev);
            const uint32_t above = XCB_STACK_MODE_ABOVE;
            xcb_configure_window(c, ws[i], XCB_CONFIG_WINDOW_STACK_MODE, &above);
            xcb_set_input_focus(c, XCB_INPUT_FOCUS_POINTER_ROOT, ws[i], XCB_CURRENT_TIME);
        }
        free(ws);
        xcb_flush(c);
    }
    xcb_disconnect(c);
    free(name);
    geng_succeed(wait, geng_slot_I4(found));
    return (geng_cancel) {0};
}

geng_cancel puritty_x11_shot(void *path_bytes, geng_wait *wait) {
    char *path = string_of(path_bytes);
    int r = write_shot(path);
    free(path);
    geng_succeed(wait, geng_slot_I4(r));
    return (geng_cancel) {0};
}

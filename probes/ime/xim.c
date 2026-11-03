/* An XIM client through xcb-imdkit, as visiterm's would be
 * (docs/phase3-input.md): one window, an input context with the preedit
 * drawn by the client (on-the-spot, XIMPreeditCallbacks), every key press
 * and release sent to the IME, and each thing the IME does logged in order
 * with its time from the key that caused it.
 *
 *   xim [SECONDS]
 *
 * Runs until SECONDS pass with no event (default 3). Log lines:
 *   key  press|release CODE SYM      a key from the server, sent to the IME
 *   back press|release CODE SYM TEXT a key the IME gave back (not consumed)
 *   commit "TEXT"
 *   pre-start / pre-draw caret first len "TEXT" [feedback...] / pre-done
 *   caret POS
 * Each line starts with the ms since the last key from the server. */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <poll.h>
#include <xcb/xcb.h>
#include <xcb/xkb.h>
#include <xkbcommon/xkbcommon-x11.h>
#include <xcb-imdkit/imclient.h>
#include <xcb-imdkit/encoding.h>

static xcb_connection_t *conn;
static xcb_window_t win;
static xcb_xim_t *im;
static xcb_xic_t ic;
static int have_ic;
static struct xkb_context *xctx;
static struct xkb_keymap *keymap;
static struct xkb_state *kstate;
static double last_key;
static int keys_in, keys_back, commits, drawn;

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e3 + t.tv_nsec / 1e6;
}

static void stamp(void) { printf("%8.3f ", now() - last_key); }

static void name_key(xcb_key_press_event_t *e, char *out, size_t n) {
    xkb_keysym_t sym = xkb_state_key_get_one_sym(kstate, e->detail);
    xkb_keysym_get_name(sym, out, n);
}

/* What the IME gave back is what visiterm would encode: its state from
 * the event's own modifiers, as the server saw them when it was pressed. */
static void forward(xcb_xim_t *m, xcb_xic_t c, xcb_key_press_event_t *e, void *u) {
    (void) m; (void) c; (void) u;
    char name[64], text[64] = "";
    name_key(e, name, sizeof name);
    int press = (e->response_type & 0x7f) == XCB_KEY_PRESS;
    if (press) xkb_state_key_get_utf8(kstate, e->detail, text, sizeof text);
    stamp();
    printf("back %s %u %s \"%s\" seq=%u\n", press ? "press" : "release", e->detail, name, text, e->sequence);
    keys_back++;
}

static void commit(xcb_xim_t *m, xcb_xic_t c, uint32_t flag, char *str, uint32_t len, uint32_t *syms, size_t nsyms,
                   void *u) {
    (void) c; (void) u; (void) syms;
    stamp();
    if (xcb_xim_get_encoding(m) == XCB_XIM_UTF8_STRING) {
        printf("commit \"%.*s\" flag=%u nsyms=%zu\n", (int) len, str, flag, nsyms);
    } else {
        size_t n;
        char *u8 = xcb_compound_text_to_utf8(str, len, &n);
        printf("commit(ct) \"%.*s\" flag=%u nsyms=%zu\n", (int) n, u8 ? u8 : "", flag, nsyms);
        free(u8);
    }
    commits++;
}

static void pre_start(xcb_xim_t *m, xcb_xic_t c, void *u) { (void) m; (void) c; (void) u; stamp(); puts("pre-start"); }
static void pre_done(xcb_xim_t *m, xcb_xic_t c, void *u) { (void) m; (void) c; (void) u; stamp(); puts("pre-done"); }

static void pre_draw(xcb_xim_t *m, xcb_xic_t c, xcb_im_preedit_draw_fr_t *f, void *u) {
    (void) c; (void) u;
    stamp();
    const char *s = (const char *) f->preedit_string;
    size_t n = f->length_of_preedit_string;
    char *u8 = NULL;
    if (xcb_xim_get_encoding(m) != XCB_XIM_UTF8_STRING) u8 = xcb_compound_text_to_utf8(s, n, &n), s = u8;
    printf("pre-draw caret=%u first=%u len=%u status=%u \"%.*s\" fb=[", f->caret, f->chg_first, f->chg_length,
           f->status, (int) n, s ? s : "");
    for (uint32_t i = 0; i < f->feedback_array.size; i++) printf("%s%u", i ? " " : "", f->feedback_array.items[i]);
    puts("]");
    free(u8);
    drawn++;
}

static void pre_caret(xcb_xim_t *m, xcb_xic_t c, xcb_im_preedit_caret_fr_t *f, void *u) {
    (void) m; (void) c; (void) u;
    stamp();
    printf("caret pos=%u dir=%u style=%u\n", f->position, f->direction, f->style);
}

static void set_mask(xcb_xim_t *m, xcb_xic_t c, uint32_t fwd, uint32_t sync, void *u) {
    (void) m; (void) c; (void) u;
    stamp();
    printf("event-mask forward=%#x sync=%#x\n", fwd, sync);
}

static void disconnected(xcb_xim_t *m, void *u) { (void) m; (void) u; stamp(); puts("disconnected"); have_ic = 0; }

static void made_ic(xcb_xim_t *m, xcb_xic_t c, void *u) {
    (void) m; (void) u;
    ic = c;
    have_ic = 1;
    xcb_xim_set_ic_focus(im, ic);
    printf("ic %u encoding=%s\n", c, xcb_xim_get_encoding(m) == XCB_XIM_UTF8_STRING ? "utf8" : "compound");
    fflush(stdout);
}

static void opened(xcb_xim_t *m, void *u) {
    (void) u;
    uint32_t style = XCB_IM_PreeditCallbacks | XCB_IM_StatusNothing;
    xcb_point_t spot = {10, 20};
    xcb_xim_nested_list pre = xcb_xim_create_nested_list(m, XCB_XIM_XNSpotLocation, &spot, NULL);
    xcb_xim_create_ic(m, made_ic, NULL, XCB_XIM_XNInputStyle, &style, XCB_XIM_XNClientWindow, &win,
                      XCB_XIM_XNFocusWindow, &win, XCB_XIM_XNPreeditAttributes, &pre, NULL);
    free(pre.data);
}

static void logger(const char *fmt, ...) { (void) fmt; }

int main(int argc, char **argv) {
    double idle = argc > 1 ? atof(argv[1]) * 1e3 : 3e3;
    int screen;
    setvbuf(stdout, NULL, _IOLBF, 0);
    conn = xcb_connect(NULL, &screen);
    if (xcb_connection_has_error(conn)) { fputs("no X server\n", stderr); return 1; }
    xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    win = xcb_generate_id(conn);
    uint32_t vals[] = {s->white_pixel, XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_KEY_RELEASE |
                                           XCB_EVENT_MASK_FOCUS_CHANGE | XCB_EVENT_MASK_STRUCTURE_NOTIFY};
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, win, s->root, 0, 0, 400, 100, 0, XCB_WINDOW_CLASS_INPUT_OUTPUT,
                      s->root_visual, XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK, vals);
    xcb_change_property(conn, XCB_PROP_MODE_REPLACE, win, XCB_ATOM_WM_NAME, XCB_ATOM_STRING, 8, 7, "xim-log");
    xcb_map_window(conn, win);
    xcb_set_input_focus(conn, XCB_INPUT_FOCUS_POINTER_ROOT, win, XCB_CURRENT_TIME);
    xcb_flush(conn);

    xkb_x11_setup_xkb_extension(conn, XKB_X11_MIN_MAJOR_XKB_VERSION, XKB_X11_MIN_MINOR_XKB_VERSION, 0, NULL, NULL,
                                NULL, NULL);
    xctx = xkb_context_new(0);
    int32_t kbd = xkb_x11_get_core_keyboard_device_id(conn);
    keymap = xkb_x11_keymap_new_from_device(xctx, conn, kbd, 0);
    kstate = xkb_x11_state_new_from_device(keymap, conn, kbd);

    xcb_compound_text_init();
    im = xcb_xim_create(conn, screen, NULL);
    xcb_xim_set_log_handler(im, logger);
    xcb_xim_set_use_utf8_string(im, true);
    xcb_xim_im_callback cb = {
        .set_event_mask = set_mask, .forward_event = forward, .commit_string = commit,
        .preedit_start = pre_start, .preedit_draw = pre_draw, .preedit_caret = pre_caret,
        .preedit_done = pre_done, .disconnected = disconnected,
    };
    xcb_xim_set_im_callback(im, &cb, NULL);
    if (!xcb_xim_open(im, opened, true, NULL)) { fputs("xim open failed\n", stderr); return 1; }

    double quiet = now();
    struct pollfd p = {xcb_get_file_descriptor(conn), POLLIN, 0};
    for (;;) {
        xcb_generic_event_t *e;
        while ((e = xcb_poll_for_event(conn))) {
            quiet = now();
            int type = e->response_type & 0x7f;
            if (xcb_xim_filter_event(im, e)) { free(e); continue; }
            if (type == XCB_KEY_PRESS || type == XCB_KEY_RELEASE) {
                xcb_key_press_event_t *k = (xcb_key_press_event_t *) e;
                if (type == XCB_KEY_PRESS) xkb_state_update_key(kstate, k->detail, XKB_KEY_DOWN);
                else xkb_state_update_key(kstate, k->detail, XKB_KEY_UP);
                last_key = now();
                char name[64];
                name_key(k, name, sizeof name);
                printf("   0.000 key %s %u %s seq=%u\n", type == XCB_KEY_PRESS ? "press" : "release", k->detail, name,
                       k->sequence);
                keys_in++;
                if (have_ic) xcb_xim_forward_event(im, ic, k);
            }
            free(e);
        }
        xcb_flush(conn);
        if (xcb_connection_has_error(conn)) break;
        double left = idle - (now() - quiet);
        if (left <= 0) break;
        poll(&p, 1, (int) left + 1);
    }
    printf("# keys %d, given back %d, commits %d, preedit draws %d\n", keys_in, keys_back, commits, drawn);
    return 0;
}

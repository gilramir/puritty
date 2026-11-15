/* xim-probe: does an xcb-imdkit XIM client send what it queued once the
 * input method has answered? (puritty docs/diagnostics.md DG8,
 * docs/upstream/xcb-imdkit-queue-stalls-after-reply.md.)
 *
 * It connects to the running input method (XMODIFIERS, e.g. @im=ibus), makes
 * an input context the way a terminal does (preedit callbacks, a spot), and
 * then runs three steps, each waiting for the input method's answers:
 *
 *   1. a key forwarded alone: it comes back at once;
 *   2. two spot updates (XIM_SET_IC_VALUES) sent back to back, then a key:
 *      the first update is sent and answered, the second and the key are
 *      queued behind it, and if nothing sends what was queued once the
 *      answer has come, the key never comes back;
 *   3. one more spot update: if the queue moves only when something is
 *      added, this sends the second update, and still not the key.
 *
 * Each step prints what went out, what came back, and whether the key
 * returned. With --trace, every XIM message in and out (xcb-imdkit's log).
 *
 *   cc -o xim-probe xim_probe.c $(pkg-config --cflags --libs xcb-imdkit xcb)
 *   XMODIFIERS=@im=ibus ./xim-probe
 */
#include <poll.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <xcb/xcb.h>
#include <xcb-imdkit/imclient.h>
#include <xcb-imdkit/encoding.h>

static xcb_connection_t *conn;
static xcb_window_t window;
static xcb_xim_t *xim;
static xcb_xic_t xic;
static bool have_xic, trace;
static int keys_back, spot_answers;

static double now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}

static void logger(const char *fmt, ...) {
    if (!trace) return;
    va_list a;
    va_start(a, fmt);
    printf("      xcb-imdkit: ");
    vprintf(fmt, a);
    va_end(a);
}

static void forwarded(xcb_xim_t *im, xcb_xic_t ic, xcb_key_press_event_t *e, void *u) {
    (void)im; (void)ic; (void)u;
    if ((e->response_type & 0x7f) == XCB_KEY_PRESS) keys_back++;
}

static void committed(xcb_xim_t *im, xcb_xic_t ic, uint32_t flag, char *str, uint32_t len, uint32_t *k, size_t n, void *u) {
    (void)im; (void)ic; (void)flag; (void)str; (void)len; (void)k; (void)n; (void)u;
    /* an input method that takes the key as text answers this way */
    keys_back++;
}

static void made(xcb_xim_t *im, xcb_xic_t ic, void *u) {
    (void)u;
    xic = ic;
    have_xic = true;
    xcb_xim_set_ic_focus(im, ic);
}

static void opened(xcb_xim_t *im, void *u) {
    (void)u;
    uint32_t style = XCB_IM_PreeditCallbacks | XCB_IM_StatusNothing;
    xcb_point_t spot = {0, 12};
    xcb_xim_nested_list pre = xcb_xim_create_nested_list(im, XCB_XIM_XNSpotLocation, &spot, NULL);
    xcb_xim_create_ic(im, made, NULL, XCB_XIM_XNInputStyle, &style, XCB_XIM_XNClientWindow, &window,
                      XCB_XIM_XNFocusWindow, &window, XCB_XIM_XNPreeditAttributes, &pre, NULL);
    free(pre.data);
}

/* Events taken and handed to xcb-imdkit for `ms`. */
static void pump(int ms) {
    double end = now_ms() + ms;
    while (now_ms() < end) {
        xcb_flush(conn);
        struct pollfd p = {xcb_get_file_descriptor(conn), POLLIN, 0};
        poll(&p, 1, 20);
        xcb_generic_event_t *e;
        while ((e = xcb_poll_for_event(conn)) != NULL) {
            xcb_xim_filter_event(xim, e);
            free(e);
        }
    }
    xcb_flush(conn);
}

static void spot_answered(xcb_xim_t *im, xcb_xic_t ic, void *u) {
    (void)im; (void)ic; (void)u;
    spot_answers++;
}

static void spot(int16_t x) {
    xcb_point_t p = {x, 12};
    xcb_xim_nested_list pre = xcb_xim_create_nested_list(xim, XCB_XIM_XNSpotLocation, &p, NULL);
    xcb_xim_set_ic_values(xim, xic, spot_answered, NULL, XCB_XIM_XNPreeditAttributes, &pre, NULL);
    free(pre.data);
}

/* A press of `q` (keycode 24 on a PC keyboard), as the X server would have
 * sent it to the window. */
static void forward_q(void) {
    xcb_key_press_event_t k;
    memset(&k, 0, sizeof k);
    k.response_type = XCB_KEY_PRESS;
    k.detail = 24;
    k.time = XCB_CURRENT_TIME;
    k.root = xcb_setup_roots_iterator(xcb_get_setup(conn)).data->root;
    k.event = window;
    k.same_screen = 1;
    xcb_xim_forward_event(xim, xic, &k);
}

static void report(const char *what, int before_keys, int before_answers) {
    printf("    %s: the key %s; spot updates answered %d\n", what,
           keys_back > before_keys ? "came back" : "did NOT come back", spot_answers - before_answers);
}

int main(int argc, char **argv) {
    trace = argc > 1 && strcmp(argv[1], "--trace") == 0;
    int screen_number;
    conn = xcb_connect(NULL, &screen_number);
    if (xcb_connection_has_error(conn)) {
        fprintf(stderr, "no X display\n");
        return 2;
    }
    xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    window = xcb_generate_id(conn);
    uint32_t mask = XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_KEY_RELEASE | XCB_EVENT_MASK_FOCUS_CHANGE;
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, s->root, 0, 0, 200, 50, 0, XCB_WINDOW_CLASS_INPUT_OUTPUT,
                      s->root_visual, XCB_CW_EVENT_MASK, &mask);
    xcb_flush(conn);

    xcb_compound_text_init();
    xim = xcb_xim_create(conn, screen_number, NULL);
    if (!xim) {
        fprintf(stderr, "xcb_xim_create failed (is XMODIFIERS set?)\n");
        return 2;
    }
    xcb_xim_set_log_handler(xim, logger);
    xcb_xim_set_use_utf8_string(xim, true);
    static const xcb_xim_im_callback cb = {.forward_event = forwarded, .commit_string = committed};
    xcb_xim_set_im_callback(xim, &cb, NULL);
    xcb_xim_open(xim, opened, true, NULL);
    for (int i = 0; i < 100 && !have_xic; i++) pump(50);
    if (!have_xic) {
        fprintf(stderr, "no input context from the input method within 5 s\n");
        return 2;
    }
    pump(300);
    printf("xim-probe: an input context made with the running input method\n");

    int k = keys_back, a = spot_answers;
    printf("1. a key forwarded alone\n");
    forward_q();
    pump(1000);
    report("after 1 s", k, a);

    k = keys_back;
    a = spot_answers;
    printf("2. two spot updates back to back, then a key\n");
    spot(10);
    spot(20);
    forward_q();
    pump(2000);
    report("after 2 s", k, a);

    int a2 = spot_answers;
    printf("3. one more spot update\n");
    spot(30);
    pump(2000);
    printf("    after 2 s: spot updates answered %d\n", spot_answers - a2);
    printf("   since step 2: the key %s; spot updates answered %d of 3\n",
           keys_back > k ? "came back" : "has NOT come back", spot_answers - a);

    bool stuck = keys_back == k;
    printf("%s\n", stuck ? "RESULT: the key queued behind an answered request was never sent"
                         : "RESULT: every key came back");
    xcb_disconnect(conn);
    return stuck ? 1 : 0;
}

/* xim-roundtrips: how many X requests, and how much waiting, an xcb-imdkit
 * XIM client spends on each key it forwards.
 *
 * It connects to the running input method (XMODIFIERS, e.g. @im=ibus), makes
 * an input context, and then forwards 20 key presses one at a time. For
 * each it measures:
 *
 *   - the X requests xcb-imdkit sent while forwarding it, from the
 *     connection's request sequence numbers;
 *   - the time spent inside xcb_xim_forward_event (sending the key), and
 *     inside xcb_xim_filter_event when the key comes back (receiving it).
 *
 * It also times one plain X round trip on the same connection, so that the
 * time spent can be read as a number of round trips waited for. Locally the
 * times are tiny; over `ssh -X` each wait costs a network round trip.
 *
 *   cc -o xim-roundtrips xim_roundtrips.c $(pkg-config --cflags --libs xcb-imdkit xcb)
 *   XMODIFIERS=@im=ibus ./xim-roundtrips
 */
#include <poll.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <xcb/xcb.h>
#include <xcb-imdkit/encoding.h>
#include <xcb-imdkit/imclient.h>

static xcb_connection_t *conn;
static xcb_window_t window;
static xcb_xim_t *xim;
static xcb_xic_t xic;
static bool have_xic;
static int keys_back;

static double now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}

/* The connection's next request sequence number. A NoOperation request
 * has no reply and no effect; its own number is counted out by the caller. */
static unsigned int next_sequence(void) {
    return xcb_no_operation(conn).sequence;
}

static void forwarded(xcb_xim_t *im, xcb_xic_t ic, xcb_key_press_event_t *e, void *u) {
    (void)im; (void)ic; (void)u;
    if ((e->response_type & 0x7f) == XCB_KEY_PRESS) keys_back++;
}

static void committed(xcb_xim_t *im, xcb_xic_t ic, uint32_t flag, char *str, uint32_t len,
                      uint32_t *k, size_t n, void *u) {
    (void)im; (void)ic; (void)flag; (void)str; (void)len; (void)k; (void)n; (void)u;
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
    xcb_xim_create_ic(im, made, NULL, XCB_XIM_XNInputStyle, &style, XCB_XIM_XNClientWindow, &window,
                      XCB_XIM_XNFocusWindow, &window, NULL);
}

/* Events taken and handed to xcb-imdkit until `done` or `ms` passed; the
 * time spent inside xcb_xim_filter_event is added to `*filtering`. */
static void pump_until(int ms, int want_back, double *filtering) {
    double end = now_ms() + ms;
    while (now_ms() < end && keys_back < want_back) {
        xcb_flush(conn);
        struct pollfd p = {xcb_get_file_descriptor(conn), POLLIN, 0};
        poll(&p, 1, 10);
        xcb_generic_event_t *e;
        while ((e = xcb_poll_for_event(conn)) != NULL) {
            double t0 = now_ms();
            xcb_xim_filter_event(xim, e);
            if (filtering) *filtering += now_ms() - t0;
            free(e);
        }
    }
}

/* A press of `q` (keycode 24 on a PC keyboard). */
static void forward_q(void) {
    xcb_key_press_event_t k;
    memset(&k, 0, sizeof k);
    k.response_type = XCB_KEY_PRESS;
    k.detail = 24;
    k.root = xcb_setup_roots_iterator(xcb_get_setup(conn)).data->root;
    k.event = window;
    k.same_screen = 1;
    xcb_xim_forward_event(xim, xic, &k);
}

int main(void) {
    int screen_number;
    conn = xcb_connect(NULL, &screen_number);
    if (xcb_connection_has_error(conn)) {
        fprintf(stderr, "no X display\n");
        return 2;
    }
    xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(conn)).data;
    window = xcb_generate_id(conn);
    uint32_t mask = XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_FOCUS_CHANGE;
    xcb_create_window(conn, XCB_COPY_FROM_PARENT, window, s->root, 0, 0, 200, 50, 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, s->root_visual, XCB_CW_EVENT_MASK, &mask);
    xcb_flush(conn);

    xcb_compound_text_init();
    xim = xcb_xim_create(conn, screen_number, NULL);
    if (!xim) {
        fprintf(stderr, "xcb_xim_create failed (is XMODIFIERS set?)\n");
        return 2;
    }
    xcb_xim_set_use_utf8_string(xim, true);
    static const xcb_xim_im_callback cb = {.forward_event = forwarded, .commit_string = committed};
    xcb_xim_set_im_callback(xim, &cb, NULL);
    xcb_xim_open(xim, opened, true, NULL);
    for (int i = 0; i < 100 && !have_xic; i++) pump_until(50, 1 << 30, NULL);
    if (!have_xic) {
        fprintf(stderr, "no input context from the input method within 5 s\n");
        return 2;
    }
    pump_until(300, 1 << 30, NULL);

    /* one X round trip, the median of 21 */
    double rtt[21];
    for (int i = 0; i < 21; i++) {
        double t0 = now_ms();
        free(xcb_get_input_focus_reply(conn, xcb_get_input_focus(conn), NULL));
        rtt[i] = now_ms() - t0;
    }
    for (int i = 0; i < 21; i++)
        for (int j = i + 1; j < 21; j++)
            if (rtt[j] < rtt[i]) {
                double x = rtt[i];
                rtt[i] = rtt[j];
                rtt[j] = x;
            }
    double round_trip = rtt[10];

    const int keys = 20;
    double sending = 0, receiving = 0;
    unsigned int requests = 0;
    int lost = 0;
    for (int i = 0; i < keys; i++) {
        unsigned int before = next_sequence();
        double t0 = now_ms();
        forward_q();
        xcb_flush(conn);
        sending += now_ms() - t0;
        unsigned int after = next_sequence();
        requests += after - before - 1;
        int want = keys_back + 1;
        pump_until(2000, want, &receiving);
        if (keys_back < want) lost++;
    }

    printf("one X round trip:                 %.3f ms\n", round_trip);
    printf("X requests to send one key:       %.1f\n", (double)requests / keys);
    printf("time sending one key:             %.3f ms (%.1f round trips)\n", sending / keys,
           sending / keys / round_trip);
    printf("time receiving it back:           %.3f ms (%.1f round trips)\n", receiving / keys,
           receiving / keys / round_trip);
    if (lost) printf("keys that did not come back:      %d of %d\n", lost, keys);
    xcb_disconnect(conn);
    return 0;
}

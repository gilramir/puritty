/* Phase 2's input survey (docs/phase2-window.md §14): the time from a key
 * to its pixel, measured from outside the terminal, as Typometer does.
 *
 * It gives the window the focus, then for each of N keys: reads the top
 * rows of the window, presses and releases a key through XTest, and reads
 * the same rows again until they differ, every poll a GetImage. The time
 * is from just before the key press is sent to the reply that differs.
 * The terminal runs a program that echoes what it reads at once, such as
 * `sh -c 'clear; stty raw -echo; exec dd bs=1 count=KEYS+1'`, so each key
 * adds a glyph to the first row; a last key, not timed, ends it.
 *
 * usage: typo WINDOW [KEYS [INTERVAL_MS [ROWS_PX]]]   WINDOW as 0x... */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <xcb/xcb.h>
#include <xcb/xcb_keysyms.h>
#include <xcb/xtest.h>

static double now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e3 + t.tv_nsec / 1e6;
}

static xcb_connection_t *c;
static xcb_window_t win;
static uint16_t width, height;

static uint8_t *grab(int *len) {
    xcb_get_image_reply_t *r =
        xcb_get_image_reply(c, xcb_get_image(c, XCB_IMAGE_FORMAT_Z_PIXMAP, win, 0, 0, width, height, ~0u), NULL);
    if (!r) return NULL;
    *len = xcb_get_image_data_length(r);
    uint8_t *d = malloc((size_t) *len);
    memcpy(d, xcb_get_image_data(r), (size_t) *len);
    free(r);
    return d;
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *) a, y = *(const double *) b;
    return x < y ? -1 : x > y;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: typo WINDOW [KEYS [INTERVAL_MS [ROWS_PX]]]\n");
        return 2;
    }
    win = (xcb_window_t) strtoul(argv[1], NULL, 0);
    int keys = argc > 2 ? atoi(argv[2]) : 100;
    int interval = argc > 3 ? atoi(argv[3]) : 100;
    int rows = argc > 4 ? atoi(argv[4]) : 40;
    c = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(c)) return 1;
    xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(c, xcb_get_geometry(c, win), NULL);
    if (!g) {
        fprintf(stderr, "no such window\n");
        return 1;
    }
    width = g->width;
    height = (uint16_t) (rows < g->height ? rows : g->height);
    free(g);
    xcb_key_symbols_t *syms = xcb_key_symbols_alloc(c);
    xcb_keycode_t *kc = xcb_key_symbols_get_keycode(syms, 'x');
    if (!kc || kc[0] == XCB_NO_SYMBOL) {
        fprintf(stderr, "no keycode for x\n");
        return 1;
    }
    xcb_keycode_t key = kc[0];
    xcb_warp_pointer(c, XCB_NONE, win, 0, 0, 0, 0, 5, 5);
    xcb_set_input_focus(c, XCB_INPUT_FOCUS_POINTER_ROOT, win, XCB_CURRENT_TIME);
    xcb_flush(c);
    struct timespec pause = {0, 300 * 1000000};
    nanosleep(&pause, NULL);

    /* What one poll costs: a GetImage of the region, round trip. */
    double p0 = now_ms();
    for (int i = 0; i < 20; i++) {
        int n;
        free(grab(&n));
    }
    double poll = (now_ms() - p0) / 20;

    double *lat = calloc((size_t) keys, sizeof *lat);
    int got = 0, polls = 0;
    for (int i = 0; i < keys; i++) {
        int n0, n1;
        uint8_t *before = grab(&n0);
        double t0 = now_ms();
        xcb_test_fake_input(c, XCB_KEY_PRESS, key, XCB_CURRENT_TIME, XCB_NONE, 0, 0, 0);
        xcb_test_fake_input(c, XCB_KEY_RELEASE, key, XCB_CURRENT_TIME, XCB_NONE, 0, 0, 0);
        xcb_flush(c);
        double t1 = -1;
        while (now_ms() - t0 < 2000) {
            uint8_t *after = grab(&n1);
            polls++;
            int differ = after && (n1 != n0 || memcmp(before, after, (size_t) n0) != 0);
            free(after);
            if (differ) {
                t1 = now_ms();
                break;
            }
        }
        free(before);
        if (t1 >= 0) lat[got++] = t1 - t0;
        struct timespec gap = {interval / 1000, (long) (interval % 1000) * 1000000};
        nanosleep(&gap, NULL);
    }
    /* One more key, not measured, for the program to end on: a terminal
     * may close as soon as its program ends, before it draws the last
     * key's echo, so the echo program reads one byte more than is timed. */
    xcb_test_fake_input(c, XCB_KEY_PRESS, key, XCB_CURRENT_TIME, XCB_NONE, 0, 0, 0);
    xcb_test_fake_input(c, XCB_KEY_RELEASE, key, XCB_CURRENT_TIME, XCB_NONE, 0, 0, 0);
    xcb_flush(c);
    qsort(lat, (size_t) got, sizeof *lat, cmp);
    double sum = 0;
    for (int i = 0; i < got; i++) sum += lat[i];
    if (got == 0) {
        printf("no key showed (%d keys)\n", keys);
        return 1;
    }
    printf("%d of %d keys shown; key to pixel ms: min %.2f median %.2f mean %.2f p95 %.2f max %.2f; a poll %.2f ms, %d polls\n",
           got, keys, lat[0], lat[got / 2], sum / got, lat[(int) (got * 0.95)], lat[got - 1], poll, polls);
    return 0;
}

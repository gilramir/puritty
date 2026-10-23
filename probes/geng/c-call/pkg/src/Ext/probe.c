#include "geng.h"
#include <xcb/xcb.h>

int32_t probe_add(int32_t a, int32_t b) { return a + b; }

geng_cancel probe_add_task(int32_t a, int32_t b, geng_wait *wait) {
    geng_succeed(wait, geng_slot_I4(a + b));
    return (geng_cancel) {0};
}

geng_cancel probe_xcb_screens(int32_t unused, geng_wait *wait) {
    (void) unused;
    int screen = 0;
    xcb_connection_t *c = xcb_connect(NULL, &screen);
    int err = xcb_connection_has_error(c);
    if (err) {
        xcb_disconnect(c);
        geng_fail(wait, geng_slot_I4(err));
    } else {
        int n = xcb_setup_roots_length(xcb_get_setup(c));
        xcb_disconnect(c);
        geng_succeed(wait, geng_slot_I4(n));
    }
    return (geng_cancel) {0};
}

/* A window manager's part, played by hand (docs/renderer.md §R9): finds the
 * top-level window called NAME on $DISPLAY and resizes it, gives it the
 * focus or takes the focus away, asks it to close as a window manager does
 * (WM_DELETE_WINDOW), or prints its title (_NET_WM_NAME). Xvfb has no
 * window manager, so this is how the x11 package's events are made there.
 * `shot` writes the window as it is now, as a PPM.
 *
 * usage: poke NAME resize WIDTH HEIGHT | focus | unfocus | close | title | shot FILE
 * build: cc -O2 -o poke poke.c $(pkg-config --cflags --libs xcb) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <xcb/xcb.h>

static xcb_connection_t *c;

static xcb_atom_t atom(const char *name) {
    xcb_intern_atom_reply_t *r = xcb_intern_atom_reply(c, xcb_intern_atom(c, 0, (uint16_t) strlen(name), name), NULL);
    xcb_atom_t a = r ? r->atom : XCB_ATOM_NONE;
    free(r);
    return a;
}

static char *title_of(xcb_window_t w, xcb_atom_t prop, xcb_atom_t type) {
    xcb_get_property_reply_t *r = xcb_get_property_reply(c, xcb_get_property(c, 0, w, prop, type, 0, 1024), NULL);
    if (!r) return NULL;
    int n = xcb_get_property_value_length(r);
    char *s = malloc((size_t) n + 1);
    memcpy(s, xcb_get_property_value(r), (size_t) n);
    s[n] = 0;
    free(r);
    return s;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: poke NAME resize WIDTH HEIGHT | focus | unfocus | close | title | shot FILE\n");
        return 2;
    }
    c = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(c)) return 1;
    xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(c)).data;
    xcb_atom_t net_wm_name = atom("_NET_WM_NAME"), utf8 = atom("UTF8_STRING");
    xcb_query_tree_reply_t *t = xcb_query_tree_reply(c, xcb_query_tree(c, s->root), NULL);
    xcb_window_t *kids = xcb_query_tree_children(t);
    xcb_window_t w = 0;
    for (int i = 0; i < xcb_query_tree_children_length(t) && !w; i++) {
        char *name = title_of(kids[i], XCB_ATOM_WM_NAME, XCB_ATOM_STRING);
        if (name && strcmp(name, argv[1]) == 0) w = kids[i];
        free(name);
    }
    free(t);
    if (!w) {
        fprintf(stderr, "poke: no window called %s\n", argv[1]);
        return 1;
    }
    const char *what = argv[2];
    if (strcmp(what, "resize") == 0 && argc == 5) {
        uint32_t size[2] = {(uint32_t) atoi(argv[3]), (uint32_t) atoi(argv[4])};
        xcb_generic_error_t *e = xcb_request_check(c, xcb_configure_window_checked(c, w, XCB_CONFIG_WINDOW_WIDTH | XCB_CONFIG_WINDOW_HEIGHT, size));
        if (e) {
            fprintf(stderr, "poke: the resize failed, error %d\n", e->error_code);
            free(e);
            return 1;
        }
    } else if (strcmp(what, "focus") == 0)
        xcb_set_input_focus(c, XCB_INPUT_FOCUS_POINTER_ROOT, w, XCB_CURRENT_TIME);
    else if (strcmp(what, "unfocus") == 0)
        xcb_set_input_focus(c, XCB_INPUT_FOCUS_POINTER_ROOT, s->root, XCB_CURRENT_TIME);
    else if (strcmp(what, "close") == 0) {
        xcb_client_message_event_t m = {0};
        m.response_type = XCB_CLIENT_MESSAGE;
        m.format = 32;
        m.window = w;
        m.type = atom("WM_PROTOCOLS");
        m.data.data32[0] = atom("WM_DELETE_WINDOW");
        m.data.data32[1] = XCB_CURRENT_TIME;
        xcb_send_event(c, 0, w, XCB_EVENT_MASK_NO_EVENT, (const char *) &m);
    } else if (strcmp(what, "shot") == 0 && argc == 4) {
        xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(c, xcb_get_geometry(c, w), NULL);
        xcb_get_image_reply_t *r = g ? xcb_get_image_reply(c, xcb_get_image(c, XCB_IMAGE_FORMAT_Z_PIXMAP, w, 0, 0, g->width, g->height, ~0u), NULL) : NULL;
        FILE *o = r ? fopen(argv[3], "wb") : NULL;
        if (!o) {
            fprintf(stderr, "poke: no shot\n");
            return 1;
        }
        const uint8_t *d = xcb_get_image_data(r);
        fprintf(o, "P6\n%d %d\n255\n", g->width, g->height);
        for (int i = 0; i < g->width * g->height; i++) {
            uint8_t px[3] = {d[i * 4 + 2], d[i * 4 + 1], d[i * 4]};
            fwrite(px, 1, 3, o);
        }
        fclose(o);
        free(r);
        free(g);
    } else if (strcmp(what, "title") == 0) {
        char *name = title_of(w, net_wm_name, utf8);
        printf("%s\n", name ? name : "");
        free(name);
    } else {
        fprintf(stderr, "poke: what is %s?\n", what);
        return 2;
    }
    /* A round trip before leaving: a request a closing connection has only
     * flushed may not be carried out. */
    free(xcb_get_input_focus_reply(c, xcb_get_input_focus(c), NULL));
    xcb_disconnect(c);
    return 0;
}

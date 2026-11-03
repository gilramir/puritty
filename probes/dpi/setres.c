/* Sets the root window's RESOURCE_MANAGER to its argument, as xrdb does
 * (docs/phase3-input.md V50): `setres "Xft.dpi:\t192\n"`. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <xcb/xcb.h>
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    xcb_connection_t *c = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(c)) return 1;
    xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(c)).data;
    xcb_change_property(c, XCB_PROP_MODE_REPLACE, s->root, XCB_ATOM_RESOURCE_MANAGER, XCB_ATOM_STRING, 8,
                        (uint32_t) strlen(argv[1]), argv[1]);

    free(xcb_get_input_focus_reply(c, xcb_get_input_focus(c), NULL));
    xcb_disconnect(c);
    return 0;
}

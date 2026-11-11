/* What Geng asks of the renderer for the settings window's interface
 * (docs/settings-gui.md SG2): its font, and a text's width in it. */

#include <stdlib.h>
#include <string.h>

#include "geng.h"
#include "puritty_text.h"

geng_cancel puritty_text_interfaceFont(void *name, geng_wait *wait) {
    geng_bytes *b = name;
    char *s = malloc((size_t) b->length + 1);
    if (s == NULL) geng_crash("puritty-text: out of memory");
    memcpy(s, b->data, (size_t) b->length);
    s[b->length] = 0;
    pt_interface_font(s);
    free(s);
    geng_succeed(wait, geng_slot_U(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_text_ligatures(int32_t on, geng_wait *wait) {
    pt_ligatures(on);
    geng_succeed(wait, geng_slot_U(0));
    return (geng_cancel) {0};
}

int32_t puritty_text_width(void *text, int32_t px) {
    geng_bytes *b = text;
    return pt_measure(b->data, (int) b->length, px);
}

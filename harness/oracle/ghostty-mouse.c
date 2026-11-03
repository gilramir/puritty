/* The mouse gate's oracle (docs/phase3-select.md §4, §11): libghostty-vt's
 * mouse encoder, with the tracking and format taken from a terminal fed the
 * case's bytes, one case a line on standard input; the bytes of each of its
 * events in hex, space-separated, a line on standard output ("-" for none).
 *
 * A case: modes-hex width height cell-w cell-h pad-top pad-bottom
 * pad-right pad-left track, then events after ";" each: action button mods
 * x y any-pressed. modes-hex is "-" for no bytes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ghostty/vt.h>

static int hex(char c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }

int main(void) {
    GhosttyMouseEncoder enc;
    GhosttyMouseEvent ev;
    if (ghostty_mouse_encoder_new(NULL, &enc) || ghostty_mouse_event_new(NULL, &ev)) return 1;
    static char line[1 << 16];
    static uint8_t modes[1 << 15];
    char out[256];
    while (fgets(line, sizeof line, stdin)) {
        char *rest = strchr(line, ';');
        char mh[1 << 15];
        GhosttyMouseEncoderSize size = {.size = sizeof size};
        int track;
        if (!rest || sscanf(line, "%32767s %u %u %u %u %u %u %u %u %d", mh, &size.screen_width, &size.screen_height,
                            &size.cell_width, &size.cell_height, &size.padding_top, &size.padding_bottom,
                            &size.padding_right, &size.padding_left, &track) != 10) {
            puts("?");
            continue;
        }
        size_t n = 0;
        if (strcmp(mh, "-"))
            for (size_t i = 0; mh[i] && mh[i + 1]; i += 2) modes[n++] = (uint8_t) (hex(mh[i]) << 4 | hex(mh[i + 1]));
        GhosttyTerminal term;
        if (ghostty_terminal_new(NULL, &term, 80, 24)) return 1;
        ghostty_terminal_vt_write(term, modes, n);
        ghostty_mouse_encoder_setopt_from_terminal(enc, term);
        ghostty_mouse_encoder_setopt(enc, GHOSTTY_MOUSE_ENCODER_OPT_SIZE, &size);
        bool t = track;
        ghostty_mouse_encoder_setopt(enc, GHOSTTY_MOUSE_ENCODER_OPT_TRACK_LAST_CELL, &t);
        ghostty_mouse_encoder_reset(enc);
        int first = 1;
        for (char *e = strtok(rest + 1, ";"); e; e = strtok(NULL, ";")) {
            int a, b, m, x, y, any;
            if (sscanf(e, "%d %d %d %d %d %d", &a, &b, &m, &x, &y, &any) != 6) break;
            ghostty_mouse_event_set_action(ev, (GhosttyMouseAction) a);
            if (b) ghostty_mouse_event_set_button(ev, (GhosttyMouseButton) b);
            else ghostty_mouse_event_clear_button(ev);
            ghostty_mouse_event_set_mods(ev, (GhosttyMods) m);
            ghostty_mouse_event_set_position(ev, (GhosttyMousePosition) {(float) x, (float) y});
            bool p = any;
            ghostty_mouse_encoder_setopt(enc, GHOSTTY_MOUSE_ENCODER_OPT_ANY_BUTTON_PRESSED, &p);
            size_t len = 0;
            if (!first) putchar(' ');
            first = 0;
            if (ghostty_mouse_encoder_encode(enc, ev, out, sizeof out, &len)) { fputs("!", stdout); continue; }
            if (!len) { putchar('-'); continue; }
            for (size_t i = 0; i < len; i++) printf("%02x", (unsigned char) out[i]);
        }
        putchar('\n');
        ghostty_terminal_free(term);
    }
    return 0;
}

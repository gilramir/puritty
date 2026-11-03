/* The key gate's oracle (docs/phase3-input.md V47): libghostty-vt's key
 * encoder, one case a line on standard input, its bytes in hex a line on
 * standard output ("-" for none).
 *
 * A case: action key mods consumed composing unshifted cursor keypad
 * backarrow ignore-numlock alt-esc modify-other kitty-flags text-hex
 * (text-hex "-" for no text). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ghostty/vt.h>

static int hex(char c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }

int main(void) {
    GhosttyKeyEncoder enc;
    GhosttyKeyEvent ev;
    if (ghostty_key_encoder_new(NULL, &enc) || ghostty_key_event_new(NULL, &ev)) return 1;
    char line[4096], text[1024], out[256];
    while (fgets(line, sizeof line, stdin)) {
        int a, k, m, c, comp, un, cur, kp, bk, num, esc, mok, kf;
        char th[2100];
        if (sscanf(line, "%d %d %d %d %d %d %d %d %d %d %d %d %d %2099s", &a, &k, &m, &c, &comp, &un, &cur, &kp, &bk,
                   &num, &esc, &mok, &kf, th) != 14) { puts("?"); continue; }
        size_t n = 0;
        if (strcmp(th, "-")) for (size_t i = 0; th[i] && th[i + 1]; i += 2) text[n++] = (char) (hex(th[i]) << 4 | hex(th[i + 1]));
        bool b;
        uint8_t flags = (uint8_t) kf;
        b = cur; ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_CURSOR_KEY_APPLICATION, &b);
        b = kp; ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_KEYPAD_KEY_APPLICATION, &b);
        b = bk; ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_BACKARROW_KEY_MODE, &b);
        b = num; ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_IGNORE_KEYPAD_WITH_NUMLOCK, &b);
        b = esc; ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_ALT_ESC_PREFIX, &b);
        b = mok; ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_MODIFY_OTHER_KEYS_STATE_2, &b);
        ghostty_key_encoder_setopt(enc, GHOSTTY_KEY_ENCODER_OPT_KITTY_FLAGS, &flags);
        ghostty_key_event_set_action(ev, (GhosttyKeyAction) a);
        ghostty_key_event_set_key(ev, (GhosttyKey) k);
        ghostty_key_event_set_mods(ev, (GhosttyMods) m);
        ghostty_key_event_set_consumed_mods(ev, (GhosttyMods) c);
        ghostty_key_event_set_composing(ev, comp);
        ghostty_key_event_set_utf8(ev, n ? text : NULL, n);
        ghostty_key_event_set_unshifted_codepoint(ev, (uint32_t) un);
        size_t len = 0;
        if (ghostty_key_encoder_encode(enc, ev, out, sizeof out, &len)) { puts("!"); continue; }
        if (!len) { puts("-"); continue; }
        for (size_t i = 0; i < len; i++) printf("%02x", (unsigned char) out[i]);
        putchar('\n');
    }
    return 0;
}

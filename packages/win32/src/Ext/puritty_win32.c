/* puritty's window on Windows (docs/windows.md WS3, WS4, V52): the C that
 * only C can do, the twin of packages/x11's. Geng sends a frame's display
 * list, and packages/text executes it (V52), drawing through the calls
 * this file gives it, into a target in memory:
 *
 *   - the target is a 32-bit bitmap the size of the screen's cells, one
 *     word a pixel, 0x00RRGGBB, which is what a top-down DIB of BI_RGB
 *     holds; the rows a frame touched are invalidated, and the window's
 *     WM_PAINT copies the bitmap to the window with SetDIBitsToDevice and
 *     fills the margins past it;
 *   - a fill sets pixels; a scroll moves rows within the bitmap;
 *   - a glyph is kept here, a byte of coverage a pixel, and drawn over the
 *     bitmap in its colour with the arithmetic XRender's software
 *     renderer (pixman) uses for OVER through an A8 mask, so that a frame's
 *     pixels are X11's; a colour glyph is kept as premultiplied ARGB and
 *     drawn OVER likewise;
 *   - a face is found among Windows' fonts by its family, from the names
 *     the registry gives the installed fonts, or among the font files of
 *     the directories `PURITTY_FONT_DIRS` names (the pixel gate's); a
 *     fallback face from a list of families tried in order
 *     (`PURITTY_FALLBACK`, else Windows' own, WS3).
 *
 * The frame is drawn on the program's thread, where FreeType and HarfBuzz
 * run (one thread, as HarfBuzz is built), under a lock the window's
 * WM_PAINT takes too; the window has a thread of its own (WS4, WS15),
 * which makes it and runs its message loop, turns messages into the event
 * records packages/x11 makes (its comment says what each is), and queues
 * them under a lock, sending a post (geng_post, D897) when the queue was
 * empty, which wakes Geng's loop for `puritty_win32_events`. The window
 * thread holds no Geng value.
 *
 * Events (WS12 steps 4 and 5): the size in cells (2), the focus (3), a
 * request to close (4), keys (1, WS5), the pointer (9, WS7), the IME (5 to
 * 8, WS6), the clipboard lost (10) and a paste's text come (11, WS8), each record as packages/x11's comment says, read so that Windows'
 * keys and pointer reach Geng as Linux's do:
 *
 *   - a key's code is X's keycode for the same key, from its scan code
 *     (win32_keycodes.h, generated from Ghostty's table), so that the
 *     application reads it through `Vt.KeyTables.evdevKey`; its keysym is
 *     X's (a table for the keys that make no text, the code point's for
 *     those that do); its modifiers are the state before the key, as X's
 *     event carries them, with AltGr neither Ctrl nor Alt, as X's
 *     ISO_Level3_Shift is neither; its text, for a key that has a table
 *     keysym, is the text xkbcommon gives that keysym, and otherwise the
 *     key's own character at its level (Shift, Caps Lock, AltGr) when Ctrl
 *     or Alt is held, else what WM_CHAR made of it, so that a dead key
 *     composes as Windows composes it; its unshifted code point is the key
 *     with no modifier; Shift and Caps Lock are consumed when they change
 *     its text, the keypad's Shift and Num Lock always, as XKB's key types
 *     say. A key the IME takes (VK_PROCESSKEY) is the IME's, and is not
 *     recorded; nor is a release whose press was not. Alt+F4 and Alt+Space
 *     are Windows' (close, the window's menu); every other Alt key is the
 *     program's, and never opens the menu bar;
 *   - the pointer's buttons are X's, the window capturing the pointer while
 *     one is held, so that a drag past the edge goes on; a wheel step is
 *     120 of its delta, a touchpad's smaller deltas summed; a motion is
 *     recorded only while a button is held, unless `puritty_win32_motion`
 *     asks for all of it, and a run of them not yet taken is its last;
 *   - the IME is IMM32's (V56): the window draws the preedit itself, so the
 *     IME's own composition window is not shown, and each composition
 *     string replaces the whole preedit; a commit is its result string; the
 *     end of a composition is its done. The spot places the IME's windows
 *     at the cursor's cell.
 *
 * PURITTY_DPI sets the resolution outright, else the system's; PURITTY_STATS
 * prints counts when the program ends; PURITTY_SHOT=FILE writes the window
 * then, as `puritty_win32_shot` does; PURITTY_LINGER=MS keeps the window on
 * the screen that long after, for a picture of it. */
#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <imm.h>
#include <windowsx.h>

#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "geng.h"
#include "puritty_text.h"
#include "win32_keycodes.h"

static char *copy(const char *s) {
    size_t n = strlen(s) + 1;
    char *d = malloc(n);
    if (d) memcpy(d, s, n);
    return d;
}

static int same(const char *a, const char *b) { return _stricmp(a, b) == 0; }

/* UTF-8 to UTF-16 and back, malloc'd. */
static wchar_t *wide(const char *s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    wchar_t *w = malloc((size_t) (n > 0 ? n : 1) * sizeof *w);
    if (n <= 0 || !MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n)) w[0] = 0;
    return w;
}

static char *narrow(const wchar_t *w) {
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    char *s = malloc((size_t) (n > 0 ? n : 1));
    if (n <= 0 || !WideCharToMultiByte(CP_UTF8, 0, w, -1, s, n, NULL, NULL)) s[0] = 0;
    return s;
}

/* FONTS
 *
 * Every face of a font file is an entry: each face of a collection, and
 * each named instance of a variable font (its index the instance above
 * bit 16, as FreeType and fontconfig number them). FreeType opens a file
 * by a path in the ANSI code page, so a path that is not ASCII is given as
 * its short form. */

typedef struct {
    char *file, *family, *style;
    int index, colour;
} Entry;

static Entry *entries;
static int nentries, centries;
static char **scanned;
static int nscanned;
static FT_Library ftlib;

static char *openable(const char *path) {
    int ascii = 1;
    for (const char *p = path; *p; p++)
        if ((unsigned char) *p >= 0x80) ascii = 0;
    if (ascii) return copy(path);
    wchar_t *w = wide(path), small[MAX_PATH];
    DWORD n = GetShortPathNameW(w, small, MAX_PATH);
    free(w);
    return n > 0 && n < MAX_PATH ? narrow(small) : copy(path);
}

static void add_entry(const char *file, int index, FT_Face f) {
    if (nentries == centries) {
        centries = centries ? centries * 2 : 256;
        entries = realloc(entries, (size_t) centries * sizeof *entries);
    }
    entries[nentries++] = (Entry) {copy(file), copy(f->family_name ? f->family_name : ""), copy(f->style_name ? f->style_name : ""),
                                   index, FT_HAS_COLOR(f) ? 1 : 0};
}

static void scan_file(const char *path) {
    for (int i = 0; i < nscanned; i++)
        if (same(scanned[i], path)) return;
    scanned = realloc(scanned, (size_t) (nscanned + 1) * sizeof *scanned);
    scanned[nscanned++] = copy(path);
    char *file = openable(path);
    FT_Face f;
    if (FT_New_Face(ftlib, file, -1, &f) != 0) {
        free(file);
        return;
    }
    long faces = f->num_faces;
    FT_Done_Face(f);
    for (long i = 0; i < faces && i < 64; i++) {
        if (FT_New_Face(ftlib, file, i, &f) != 0) continue;
        add_entry(file, (int) i, f);
        long instances = f->style_flags >> 16;
        FT_Done_Face(f);
        for (long k = 1; k <= instances && k < 64; k++) {
            if (FT_New_Face(ftlib, file, (k << 16) | i, &f) != 0) continue;
            add_entry(file, (int) ((k << 16) | i), f);
            FT_Done_Face(f);
        }
    }
    free(file);
}

static int font_file_name(const char *name) {
    size_t n = strlen(name);
    if (n < 5) return 0;
    const char *e = name + n - 4;
    return same(e, ".ttf") || same(e, ".otf") || same(e, ".ttc") || same(e, ".otc");
}

/* The fonts the registry names, HKLM's and the user's: a name as Windows
 * shows it ("Fira Code Bold (TrueType)", "Cambria & Cambria Math
 * (TrueType)") and its file, which is in the Windows font directory when
 * it is not a whole path. */
typedef struct {
    char *name, *path;
} Named;

static Named *named;
static int nnamed;
static int dirs_mode, registry_read;

static void read_registry(HKEY root) {
    HKEY key;
    if (RegOpenKeyExW(root, L"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts", 0, KEY_READ, &key) != ERROR_SUCCESS) return;
    wchar_t windir[MAX_PATH];
    GetWindowsDirectoryW(windir, MAX_PATH);
    for (DWORD i = 0;; i++) {
        wchar_t name[512], data[MAX_PATH];
        DWORD nn = 512, dn = sizeof data, type;
        LONG r = RegEnumValueW(key, i, name, &nn, NULL, &type, (BYTE *) data, &dn);
        if (r == ERROR_NO_MORE_ITEMS) break;
        if (r != ERROR_SUCCESS || type != REG_SZ) continue;
        data[MAX_PATH - 1] = 0;
        wchar_t full[MAX_PATH * 2];
        if (wcschr(data, L'\\')) _snwprintf(full, MAX_PATH * 2, L"%ls", data);
        else _snwprintf(full, MAX_PATH * 2, L"%ls\\Fonts\\%ls", windir, data);
        full[MAX_PATH * 2 - 1] = 0;
        wchar_t *paren = wcsstr(name, L" (");
        if (paren) *paren = 0;
        named = realloc(named, (size_t) (nnamed + 1) * sizeof *named);
        named[nnamed++] = (Named) {narrow(name), narrow(full)};
    }
    RegCloseKey(key);
}

/* Each file whose registry name has a part that begins with `family`,
 * scanned; the families they hold are then entries. */
static void scan_family(const char *family) {
    if (dirs_mode) return;
    if (!registry_read) {
        registry_read = 1;
        read_registry(HKEY_LOCAL_MACHINE);
        read_registry(HKEY_CURRENT_USER);
    }
    size_t n = strlen(family);
    for (int i = 0; i < nnamed; i++) {
        const char *part = named[i].name;
        while (part) {
            if (_strnicmp(part, family, n) == 0 && (part[n] == 0 || part[n] == ' ' || part[n] == '&')) {
                scan_file(named[i].path);
                break;
            }
            part = strstr(part, " & ");
            if (part) part += 3;
        }
    }
}

static void scan_everything(void) {
    static int done;
    if (done || dirs_mode) return;
    done = 1;
    scan_family("");
}

/* The directories PURITTY_FONT_DIRS names, separated by `;`: every font
 * file in each, and no other font. */
static void scan_dirs(const char *dirs) {
    char *all = copy(dirs);
    for (char *d = strtok(all, ";"); d; d = strtok(NULL, ";")) {
        char pattern[MAX_PATH * 2];
        snprintf(pattern, sizeof pattern, "%s\\*", d);
        wchar_t *wp = wide(pattern);
        WIN32_FIND_DATAW fd;
        HANDLE h = FindFirstFileW(wp, &fd);
        free(wp);
        if (h == INVALID_HANDLE_VALUE) continue;
        char **files = NULL;
        int n = 0;
        do {
            char *name = narrow(fd.cFileName);
            if (font_file_name(name)) {
                char path[MAX_PATH * 2];
                snprintf(path, sizeof path, "%s\\%s", d, name);
                files = realloc(files, (size_t) (n + 1) * sizeof *files);
                files[n++] = copy(path);
            }
            free(name);
        } while (FindNextFileW(h, &fd));
        FindClose(h);
        /* in name order, so that which face comes first does not depend on
         * the directory's */
        for (int i = 1; i < n; i++)
            for (int j = i; j > 0 && strcmp(files[j - 1], files[j]) > 0; j--) {
                char *t = files[j];
                files[j] = files[j - 1];
                files[j - 1] = t;
            }
        for (int i = 0; i < n; i++) {
            scan_file(files[i]);
            free(files[i]);
        }
        free(files);
    }
    free(all);
}

static int has_word(const char *style, const char *word) {
    size_t n = strlen(word);
    for (const char *p = style; *p; p++)
        if (_strnicmp(p, word, n) == 0 && (p == style || p[-1] == ' ') && (p[n] == 0 || p[n] == ' ')) return 1;
    return 0;
}

/* What a style name says: bold 1, italic 2; -1 for a weight that is
 * neither regular nor bold (Light, Medium, SemiBold, ...). */
static int style_of(const char *style) {
    int s = 0, other = 0;
    char word[64];
    const char *p = style;
    while (*p) {
        while (*p == ' ') p++;
        int k = 0;
        while (*p && *p != ' ' && k < 63) word[k++] = *p++;
        word[k] = 0;
        if (!k) break;
        if (same(word, "Bold")) s |= 1;
        else if (same(word, "Italic") || same(word, "Oblique")) s |= 2;
        else if (!same(word, "Regular") && !same(word, "Book") && !same(word, "Normal") && !same(word, "Roman")) other = 1;
    }
    (void) has_word;
    return other ? -1 : s;
}

/* The entry of `family` whose style is `variant` (bold 1, italic 2), a
 * face before a named instance of it; -1 when there is none. */
static int exact_face(const char *family, int variant, int *any) {
    for (int pass = 0; pass < 2; pass++)
        for (int i = 0; i < nentries; i++) {
            if (!same(entries[i].family, family)) continue;
            if ((entries[i].index >> 16 != 0) != pass) continue;
            if (*any < 0) *any = i;
            if (style_of(entries[i].style) == variant) return i;
        }
    return -1;
}

/* The entry of `family` in a variant, else the closest, as fontconfig
 * gives it: a bold italic the family lacks is its bold, and an italic its
 * regular, whose glyphs the renderer then slants (C§9 rule 6); -1 when
 * the family has no entry. */
static int find_face(const char *family, int variant) {
    scan_family(family);
    int any = -1, e = exact_face(family, variant, &any);
    if (e < 0 && (variant & 2)) e = exact_face(family, variant & 1, &any);
    if (e < 0 && variant) e = exact_face(family, 0, &any);
    return e >= 0 ? e : any;
}

char *pt_font_file(const char *font, int variant, int *index) {
    int e = find_face(font, variant & 3);
    /* fontconfig gives the closest font to one it does not have; Windows'
     * own monospace fonts stand in for it */
    static const char *const stand_ins[] = {"Cascadia Mono", "Consolas", "Courier New"};
    for (size_t k = 0; e < 0 && !dirs_mode && k < sizeof stand_ins / sizeof *stand_ins; k++) e = find_face(stand_ins[k], variant & 3);
    if (e < 0) return NULL;
    *index = entries[e].index;
    return copy(entries[e].file);
}

/* The families a fallback face is looked for in, in order: `tag:Family`
 * is tried first, and only, when the language is `tag`. Windows' own,
 * where nothing else names them (WS3). */
static const char *const windows_fallback =
    "Cascadia Mono;Consolas;"
    "ja:Yu Gothic;ja:MS Gothic;ko:Malgun Gothic;zh-cn:Microsoft YaHei;zh-tw:Microsoft JhengHei;zh-hk:Microsoft JhengHei;"
    "Segoe UI Symbol;Malgun Gothic;Yu Gothic;Microsoft YaHei;Microsoft JhengHei;Leelawadee UI;Nirmala UI;"
    "Segoe UI Emoji;Segoe UI;Segoe UI Historic;Ebrima;Gadugi;Javanese Text;Myanmar Text;Mongolian Baiti;Sylfaen;"
    "MS Gothic;SimSun-ExtB;Segoe UI Emoji";

static char *fallback_list;

static int ignorable(uint32_t cp) {
    return cp == 0x200D || cp == 0x200C || (cp >= 0xFE00 && cp <= 0xFE0F) || (cp >= 0xE0100 && cp <= 0xE01EF);
}

static int hangul(uint32_t cp) {
    return (cp >= 0x1100 && cp <= 0x11FF) || (cp >= 0x3130 && cp <= 0x318F) || (cp >= 0xA960 && cp <= 0xA97F) ||
           (cp >= 0xAC00 && cp <= 0xD7FF);
}

/* Whether an entry's face has every code point of the cluster. */
static int entry_covers(int e, const uint32_t *cps, int n) {
    FT_Face f;
    if (FT_New_Face(ftlib, entries[e].file, entries[e].index, &f) != 0) return 0;
    int all = 1;
    for (int i = 0; i < n && all; i++)
        if (!ignorable(cps[i]) && FT_Get_Char_Index(f, cps[i]) == 0) all = 0;
    FT_Done_Face(f);
    return all;
}

static int try_family(const char *family, const uint32_t *cps, int n, int colour) {
    int e = find_face(family, 0);
    if (e < 0 || entries[e].colour != colour) return -1;
    return entry_covers(e, cps, n) ? e : -1;
}

char *pt_fallback_file(const uint32_t *cps, int n, int colour, const char *lang, int *index) {
    /* Hangul is asked for in Korean, as fontconfig's coverage of a
     * language chooses a Korean face for it */
    const char *want = lang;
    for (int i = 0; i < n && !want; i++)
        if (hangul(cps[i])) want = "ko";
    int found = -1;
    for (int pass = 0; pass < 2 && found < 0; pass++) {
        char *list = copy(fallback_list);
        for (char *item = strtok(list, ";"); item && found < 0; item = strtok(NULL, ";")) {
            char *colon = strchr(item, ':');
            if (pass == 0) {
                if (!colon || !want) continue;
                *colon = 0;
                if (!same(item, want)) continue;
                found = try_family(colon + 1, cps, n, colour);
            } else if (!colon)
                found = try_family(item, cps, n, colour);
        }
        free(list);
    }
    if (found < 0) {
        scan_everything();
        for (int e = 0; e < nentries && found < 0; e++)
            if (entries[e].colour == colour && (entries[e].index >> 16) == 0 && entry_covers(e, cps, n)) found = e;
    }
    if (found < 0) return NULL;
    *index = entries[found].index;
    return copy(entries[found].file);
}

/* THE TARGET */

static CRITICAL_SECTION paint;
static uint32_t *pixels;
static int pw, ph;
static uint32_t margin_rgb;

void pt_target(int c, int r) {
    EnterCriticalSection(&paint);
    free(pixels);
    pw = c * pt_cw;
    ph = r * pt_ch;
    pixels = calloc((size_t) pw * (size_t) (ph > 0 ? ph : 1), sizeof *pixels);
    LeaveCriticalSection(&paint);
}

void pt_fill(uint32_t rgb, int x, int y, int w, int h) {
    int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y, x1 = x + w > pw ? pw : x + w, y1 = y + h > ph ? ph : y + h;
    rgb &= 0xFFFFFF;
    for (int j = y0; j < y1; j++) {
        uint32_t *row = pixels + (size_t) j * pw;
        for (int i = x0; i < x1; i++) row[i] = rgb;
    }
}

void pt_fill_rects(uint32_t rgb, const PtRect *rects, int n) {
    for (int i = 0; i < n; i++) pt_fill(rgb, rects[i].x, rects[i].y, rects[i].w, rects[i].h);
}

void pt_scroll(int top, int bottom, int k) {
    int dst = top * pt_ch, src = (top + k) * pt_ch, h = (bottom - top + 1) * pt_ch;
    if (src < 0) {
        h += src;
        dst -= src;
        src = 0;
    }
    if (src + h > ph) h = ph - src;
    if (dst + h > ph) h = ph - dst;
    if (h <= 0 || dst < 0) return;
    memmove(pixels + (size_t) dst * pw, pixels + (size_t) src * pw, (size_t) h * pw * sizeof *pixels);
}

/* pixman's multiplication of two 8-bit values as fractions of 255. */
static inline uint32_t mul8(uint32_t a, uint32_t b) {
    uint32_t t = a * b + 0x80;
    return ((t >> 8) + t) >> 8;
}

static inline uint32_t add8(uint32_t a, uint32_t b) { return a + b > 255 ? 255 : a + b; }

/* The glyphs kept, by id, in a table of open addressing. */
typedef struct {
    uint32_t id;
    int used, width, height, stride, left, top;
    uint8_t *data;
} Kept;

static Kept *kept;
static size_t nkept, ckept;

static size_t slot_of(uint32_t id) { return (size_t) ((id * 2654435761u) & (uint32_t) (ckept - 1)); }

void pt_glyph_add(uint32_t id, const PtGlyph *g) {
    if ((nkept + 1) * 2 > ckept) {
        size_t old = ckept;
        Kept *was = kept;
        ckept = ckept ? ckept * 2 : 4096;
        kept = calloc(ckept, sizeof *kept);
        for (size_t i = 0; i < old; i++)
            if (was[i].used) {
                size_t s = slot_of(was[i].id);
                while (kept[s].used) s = (s + 1) & (ckept - 1);
                kept[s] = was[i];
            }
        free(was);
    }
    size_t s = slot_of(id);
    while (kept[s].used && kept[s].id != id) s = (s + 1) & (ckept - 1);
    if (kept[s].used) free(kept[s].data);
    else nkept++;
    size_t size = (size_t) g->stride * (size_t) g->height;
    uint8_t *data = malloc(size ? size : 1);
    if (size) memcpy(data, g->data, size);
    kept[s] = (Kept) {id, 1, g->width, g->height, g->stride, g->left, g->top, data};
}

void pt_glyphs_reset(void) {
    for (size_t i = 0; i < ckept; i++)
        if (kept[i].used) free(kept[i].data);
    if (kept) memset(kept, 0, ckept * sizeof *kept);
    nkept = 0;
}

static const Kept *find_kept(uint32_t id) {
    if (!ckept) return NULL;
    size_t s = slot_of(id);
    while (kept[s].used) {
        if (kept[s].id == id) return &kept[s];
        s = (s + 1) & (ckept - 1);
    }
    return NULL;
}

/* OVER through the glyph's coverage: each channel s·m + d·(1 - m), as
 * pixman composites a solid source through an A8 mask. */
void pt_glyphs_draw(const PtPlaced *placed, int n, const PtRect *clips) {
    for (int k = 0; k < n; k++) {
        const PtPlaced *P = &placed[k];
        const Kept *g = find_kept(P->id);
        if (!g) continue;
        int cx0 = 0, cy0 = 0, cx1 = pw, cy1 = ph;
        if (P->clip >= 0) {
            const PtRect *c = &clips[P->clip];
            if (c->x > cx0) cx0 = c->x;
            if (c->y > cy0) cy0 = c->y;
            if (c->x + c->w < cx1) cx1 = c->x + c->w;
            if (c->y + c->h < cy1) cy1 = c->y + c->h;
        }
        int gx = P->x + g->left, gy = P->y - g->top;
        uint32_t sr = (P->fg >> 16) & 0xff, sg = (P->fg >> 8) & 0xff, sb = P->fg & 0xff;
        for (int j = 0; j < g->height; j++) {
            int y = gy + j;
            if (y < cy0 || y >= cy1) continue;
            const uint8_t *m = g->data + (size_t) j * g->stride;
            uint32_t *row = pixels + (size_t) y * pw;
            for (int i = 0; i < g->width; i++) {
                int x = gx + i;
                uint32_t a = m[i];
                if (a == 0 || x < cx0 || x >= cx1) continue;
                uint32_t d = row[x], na = 255 - a;
                uint32_t r = add8(mul8(sr, a), mul8((d >> 16) & 0xff, na));
                uint32_t gg = add8(mul8(sg, a), mul8((d >> 8) & 0xff, na));
                uint32_t b = add8(mul8(sb, a), mul8(d & 0xff, na));
                row[x] = r << 16 | gg << 8 | b;
            }
        }
    }
}

typedef struct {
    int w, h;
    uint32_t px[];
} Picture;

void *pt_picture_add(const uint32_t *argb, int w, int h) {
    Picture *p = malloc(sizeof *p + (size_t) w * (size_t) h * sizeof(uint32_t));
    if (!p) return NULL;
    p->w = w;
    p->h = h;
    memcpy(p->px, argb, (size_t) w * (size_t) h * sizeof(uint32_t));
    return p;
}

/* OVER of premultiplied ARGB: s + d·(1 - sA). */
void pt_picture_draw(void *picture, int x, int y, int w, int h) {
    Picture *p = picture;
    if (!p) return;
    if (w > p->w) w = p->w;
    if (h > p->h) h = p->h;
    for (int j = 0; j < h; j++) {
        int yy = y + j;
        if (yy < 0 || yy >= ph) continue;
        uint32_t *row = pixels + (size_t) yy * pw;
        for (int i = 0; i < w; i++) {
            int xx = x + i;
            if (xx < 0 || xx >= pw) continue;
            uint32_t s = p->px[j * p->w + i], sa = s >> 24;
            if (sa == 0 && (s & 0xFFFFFF) == 0) continue;
            uint32_t d = row[xx], na = 255 - sa;
            uint32_t r = add8((s >> 16) & 0xff, mul8((d >> 16) & 0xff, na));
            uint32_t g = add8((s >> 8) & 0xff, mul8((d >> 8) & 0xff, na));
            uint32_t b = add8(s & 0xff, mul8(d & 0xff, na));
            row[xx] = r << 16 | g << 8 | b;
        }
    }
}

void pt_picture_free(void *picture) { free(picture); }

/* THE WINDOW THREAD (WS4) */

typedef struct holder {
    geng_wait *pending;
} holder;

#define HOLDER_HEADER (GENG_HEADER_WORDS(holder) | GENG_HEADER_POINTER(holder, pending))

static CRITICAL_SECTION queue_lock;
static uint8_t evbuf[65536];
static int evlen;
static geng_post *post;
static holder *held;
static HWND win;
static HANDLE made;
static wchar_t *title0;
static int open_cols, open_rows, open_dpi;
/* The cell as the window thread sizes by it, under the queue's lock. */
static int cell_w, cell_h;
static int win_cols, win_rows, win_w, win_h, focused = -1;
/* Where the queue's last record begins when it is a motion, else -1; under
 * the queue's lock. */
static int last_motion = -1;
/* Set by the program's thread: every motion or only a held button's, and
 * the arrow or the I-beam. */
static volatile LONG all_motion, pointer_arrow;
/* Whether the clipboard is the window's, by its last copy. */
static volatile LONG clip_owned;

#define WM_APP_SPOT (WM_APP + 1)
#define WM_APP_POINTER (WM_APP + 2)

/* A record queued, and the post sent when the queue was empty, which wakes
 * Geng's loop. A motion takes the place of one at the queue's end. */
static void record_as(const uint8_t *r, int n, int motion) {
    EnterCriticalSection(&queue_lock);
    int was = evlen;
    if (motion && last_motion >= 0 && last_motion + n == evlen) {
        memcpy(evbuf + last_motion, r, (size_t) n);
    } else if (evlen + n <= (int) sizeof evbuf) {
        memcpy(evbuf + evlen, r, (size_t) n);
        last_motion = motion ? evlen : -1;
        evlen += n;
    }
    LeaveCriticalSection(&queue_lock);
    if (was == 0) geng_post_send(post, malloc(1));
}

static void record(const uint8_t *r, int n) { record_as(r, n, 0); }

/* KEYS (WS5) */

#define DOWN(ks, vk) (((ks)[vk] & 0x80) != 0)

/* Whether the keyboard layout has AltGr: a character it types with Ctrl
 * and Alt. Asked again when the layout changes. */
static int has_altgr(void) {
    static HKL known;
    static int answer;
    HKL k = GetKeyboardLayout(0);
    if (k != known) {
        known = k;
        answer = 0;
        for (WCHAR c = 0x21; c < 0x250 && !answer; c++) {
            SHORT s = VkKeyScanExW(c, k);
            if (s != -1 && ((s >> 8) & 6) == 6) answer = 1;
        }
    }
    return answer;
}

/* Whether the left Ctrl down is the one Windows sends with AltGr (the
 * right Alt, on a layout that has it), which is no key of the user's. */
static int fake_ctrl;

/* AltGr held: the right Alt, on a layout that has AltGr. */
static int altgr_in(const BYTE *ks) { return DOWN(ks, VK_RMENU) && has_altgr(); }

/* The modifiers as Ghostty's bits (packages/x11's comment). AltGr is
 * neither Ctrl nor Alt, and the left Ctrl sent with it is not Ctrl. */
static int mods_of(const BYTE *ks) {
    int altgr = altgr_in(ks), m = 0;
    if (DOWN(ks, VK_LSHIFT) || DOWN(ks, VK_RSHIFT)) m |= 1;
    if ((DOWN(ks, VK_LCONTROL) && !fake_ctrl) || DOWN(ks, VK_RCONTROL)) m |= 2;
    if (DOWN(ks, VK_LMENU) || (DOWN(ks, VK_RMENU) && !altgr)) m |= 4;
    if (DOWN(ks, VK_LWIN) || DOWN(ks, VK_RWIN)) m |= 8;
    if (ks[VK_CAPITAL] & 1) m |= 16;
    if (ks[VK_NUMLOCK] & 1) m |= 32;
    if ((m & 1) && DOWN(ks, VK_RSHIFT)) m |= 64;
    if ((m & 2) && DOWN(ks, VK_RCONTROL)) m |= 128;
    if ((m & 4) && DOWN(ks, VK_RMENU) && !altgr) m |= 256;
    if ((m & 8) && DOWN(ks, VK_RWIN)) m |= 512;
    return m;
}

static int mods_now(void) {
    BYTE ks[256];
    GetKeyboardState(ks);
    return mods_of(ks);
}

/* X's keysym for a key that makes no text of its own, or that X names by
 * its function (Return, Tab, the keypad); 0 for a key whose keysym is its
 * character. `ext` is Windows' extended bit, which tells the keypad's
 * keys from the ones between: the keypad's are KP_ keysyms. */
static uint32_t table_sym(UINT vk, int ext, int shift) {
    if (vk >= VK_F1 && vk <= VK_F24) return 0xFFBE + (vk - VK_F1);
    if (vk >= VK_NUMPAD0 && vk <= VK_NUMPAD9) return 0xFFB0 + (vk - VK_NUMPAD0);
    switch (vk) {
    case VK_BACK: return 0xFF08;
    case VK_TAB: return shift ? 0xFE20 : 0xFF09; /* ISO_Left_Tab */
    case VK_CLEAR: return ext ? 0xFF0B : 0xFF9D; /* KP_Begin */
    case VK_RETURN: return ext ? 0xFF8D : 0xFF0D; /* KP_Enter */
    case VK_PAUSE: return 0xFF13;
    case VK_CANCEL: return 0xFF6B; /* Break */
    case VK_CAPITAL: return 0xFFE5;
    case VK_ESCAPE: return 0xFF1B;
    case VK_PRIOR: return ext ? 0xFF55 : 0xFF9A;
    case VK_NEXT: return ext ? 0xFF56 : 0xFF9B;
    case VK_END: return ext ? 0xFF57 : 0xFF9C;
    case VK_HOME: return ext ? 0xFF50 : 0xFF95;
    case VK_LEFT: return ext ? 0xFF51 : 0xFF96;
    case VK_UP: return ext ? 0xFF52 : 0xFF97;
    case VK_RIGHT: return ext ? 0xFF53 : 0xFF98;
    case VK_DOWN: return ext ? 0xFF54 : 0xFF99;
    case VK_SNAPSHOT: return 0xFF61;
    case VK_INSERT: return ext ? 0xFF63 : 0xFF9E;
    case VK_DELETE: return ext ? 0xFFFF : 0xFF9F;
    case VK_LWIN: return 0xFFEB;
    case VK_RWIN: return 0xFFEC;
    case VK_APPS: return 0xFF67;
    case VK_MULTIPLY: return 0xFFAA;
    case VK_ADD: return 0xFFAB;
    case VK_SEPARATOR: return 0xFFAC;
    case VK_SUBTRACT: return 0xFFAD;
    case VK_DECIMAL: return 0xFFAE;
    case VK_DIVIDE: return 0xFFAF;
    case VK_NUMLOCK: return 0xFF7F;
    case VK_SCROLL: return 0xFF14;
    case VK_LSHIFT: return 0xFFE1;
    case VK_RSHIFT: return 0xFFE2;
    case VK_LCONTROL: return 0xFFE3;
    case VK_RCONTROL: return 0xFFE4;
    case VK_LMENU: return 0xFFE9;
    case VK_RMENU: return has_altgr() ? 0xFE03 : 0xFFEA; /* ISO_Level3_Shift */
    case VK_HANGUL: return 0xFF31;
    case VK_HANJA: return 0xFF34;
    default: return 0;
    }
}

/* The keypad's keys whose keysym Num Lock chooses. */
static int numpad(UINT vk, int ext) {
    if ((vk >= VK_NUMPAD0 && vk <= VK_NUMPAD9) || vk == VK_DECIMAL) return 1;
    if (ext) return 0;
    switch (vk) {
    case VK_CLEAR: case VK_PRIOR: case VK_NEXT: case VK_END: case VK_HOME:
    case VK_LEFT: case VK_UP: case VK_RIGHT: case VK_DOWN: case VK_INSERT: case VK_DELETE: return 1;
    default: return 0;
    }
}

/* The code point xkbcommon gives a keysym (xkb_keysym_to_utf32), for the
 * keysyms the table gives: the few function keysyms that have one, and
 * the keypad's characters. */
static uint32_t sym_text(uint32_t sym) {
    if (sym == 0xFF80) return ' ';
    if ((sym >= 0xFF08 && sym <= 0xFF0B) || (sym >= 0xFFAA && sym <= 0xFFB9) || sym == 0xFF0D || sym == 0xFF1B ||
        sym == 0xFFFF || sym == 0xFF89 || sym == 0xFF8D || sym == 0xFFBD)
        return sym & 0x7F;
    return 0;
}

/* X's keysym for a character: Latin-1's own, a dead key's dead_ keysym,
 * and Unicode's above 0x1000000. */
static uint32_t char_sym(uint32_t cp, int dead) {
    if (dead) {
        switch (cp) {
        case '`': return 0xFE50;
        case 0xB4: case '\'': return 0xFE51;
        case '^': return 0xFE52;
        case '~': return 0xFE53;
        case 0xAF: return 0xFE54;
        case 0x2D8: return 0xFE55;
        case 0x2D9: return 0xFE56;
        case 0xA8: case '"': return 0xFE57;
        case 0x2DA: return 0xFE58;
        case 0x2DD: return 0xFE59;
        case 0x2C7: return 0xFE5A;
        case 0xB8: return 0xFE5B;
        default: return 0;
        }
    }
    if (cp == 0) return 0;
    if ((cp >= 0x20 && cp < 0x7F) || (cp >= 0xA0 && cp <= 0xFF)) return cp;
    return 0x1000000 | cp;
}

/* The first code point of UTF-16. */
static uint32_t first_cp(const WCHAR *w, int n) {
    if (n <= 0) return 0;
    if (n > 1 && w[0] >= 0xD800 && w[0] < 0xDC00 && w[1] >= 0xDC00 && w[1] < 0xE000)
        return 0x10000 + (((uint32_t) w[0] - 0xD800) << 10) + ((uint32_t) w[1] - 0xDC00);
    return w[0];
}

/* UTF-16 to UTF-8 into `out` of `cap` bytes, whole code points only. */
static int utf8_of(const WCHAR *w, int n, char *out, int cap) {
    int k = 0;
    for (int i = 0; i < n;) {
        uint32_t c = w[i];
        int units = 1;
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < n && w[i + 1] >= 0xDC00 && w[i + 1] < 0xE000) {
            c = 0x10000 + ((c - 0xD800) << 10) + ((uint32_t) w[i + 1] - 0xDC00);
            units = 2;
        }
        char b[4];
        int m = c < 0x80 ? (b[0] = (char) c, 1)
              : c < 0x800 ? (b[0] = (char) (0xC0 | c >> 6), b[1] = (char) (0x80 | (c & 0x3F)), 2)
              : c < 0x10000 ? (b[0] = (char) (0xE0 | c >> 12), b[1] = (char) (0x80 | ((c >> 6) & 0x3F)), b[2] = (char) (0x80 | (c & 0x3F)), 3)
              : (b[0] = (char) (0xF0 | c >> 18), b[1] = (char) (0x80 | ((c >> 12) & 0x3F)), b[2] = (char) (0x80 | ((c >> 6) & 0x3F)),
                 b[3] = (char) (0x80 | (c & 0x3F)), 4);
        if (k + m > cap) break;
        memcpy(out + k, b, (size_t) m);
        k += m;
        i += units;
    }
    return k;
}

/* What the key makes in the keyboard state `ks`, without changing the
 * layout's state (flag 4: a dead key waiting stays waiting); negative for
 * a dead key, its character in `out`. */
static int key_chars(UINT vk, UINT scan, const BYTE *ks, WCHAR *out, int cap) {
    return ToUnicodeEx(vk, scan, ks, out, cap, 4, GetKeyboardLayout(0));
}

static void without_ctrl_alt(BYTE *ks) {
    ks[VK_CONTROL] = ks[VK_LCONTROL] = ks[VK_RCONTROL] = 0;
    ks[VK_MENU] = ks[VK_LMENU] = ks[VK_RMENU] = 0;
}

/* Keys whose press was recorded, by virtual key (the side's), so that a
 * release is recorded only after its press; forgotten with the focus. */
static uint8_t keys_held[32];
/* The dead key last pressed and its keysym and unshifted code point, for
 * its release, while the layout still holds it. */
static UINT dead_own;
static uint32_t dead_sym, dead_unshifted;
/* A high surrogate typed alone (VK_PACKET), waiting for its low half. */
static WCHAR packet_high;

static void key_record(int action, int code, int mods, int consumed, uint32_t unshifted, uint32_t sym, const char *text, int n) {
    if (n > 63) n = 63;
    uint8_t rec[16 + 63] = {1, (uint8_t) action, (uint8_t) code, (uint8_t) (mods >> 8), (uint8_t) mods,
                            (uint8_t) (consumed >> 8), (uint8_t) consumed,
                            (uint8_t) (unshifted >> 24), (uint8_t) (unshifted >> 16), (uint8_t) (unshifted >> 8), (uint8_t) unshifted,
                            (uint8_t) (sym >> 24), (uint8_t) (sym >> 16), (uint8_t) (sym >> 8), (uint8_t) sym, (uint8_t) n};
    memcpy(rec + 16, text, (size_t) n);
    record(rec, 16 + n);
}

/* A character typed as itself (SendInput's KEYEVENTF_UNICODE, the emoji
 * panel): no key, its text alone. */
static void packet_key(MSG *msg) {
    TranslateMessage(msg);
    MSG c;
    while (PeekMessageW(&c, msg->hwnd, WM_CHAR, WM_CHAR, PM_REMOVE)) {
        WCHAR w[2] = {(WCHAR) c.wParam, 0};
        int n = 1;
        if (w[0] >= 0xD800 && w[0] < 0xDC00) {
            packet_high = w[0];
            continue;
        }
        if (w[0] >= 0xDC00 && w[0] < 0xE000) {
            if (!packet_high) continue;
            w[1] = w[0];
            w[0] = packet_high;
            n = 2;
        }
        packet_high = 0;
        char text[8];
        int k = utf8_of(w, n, text, sizeof text);
        key_record(1, 0, mods_now(), 0, 0, char_sym(first_cp(w, n), 0), text, k);
    }
}

/* A key message, taken from the loop before it is dispatched; answers 1
 * when it is handled here, 0 when Windows is to have it. */
static int key_message(MSG *msg) {
    UINT vk = (UINT) msg->wParam;
    int press = msg->message == WM_KEYDOWN || msg->message == WM_SYSKEYDOWN;
    if (vk == VK_PROCESSKEY) {
        TranslateMessage(msg);
        return 1;
    }
    if (vk == VK_PACKET) {
        if (press) packet_key(msg);
        return 1;
    }
    BYTE ks[256];
    GetKeyboardState(ks);
    if (press && (vk == VK_F4 || vk == VK_SPACE) && DOWN(ks, VK_MENU) && !DOWN(ks, VK_CONTROL)) return 0;
    UINT scan = (UINT) (msg->lParam >> 16) & 0xFF;
    int ext = (int) (msg->lParam >> 24) & 1, repeat = (int) (msg->lParam >> 30) & 1;
    if (scan == 0) {
        UINT s = MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX);
        scan = s & 0xFF;
        ext = (s >> 8) == 0xE0;
    }
    /* the side's key */
    UINT own = vk;
    if (vk == VK_SHIFT) own = MapVirtualKeyW(scan, MAPVK_VSC_TO_VK_EX) == VK_RSHIFT ? VK_RSHIFT : VK_LSHIFT;
    else if (vk == VK_CONTROL) own = ext ? VK_RCONTROL : VK_LCONTROL;
    else if (vk == VK_MENU) own = ext ? VK_RMENU : VK_LMENU;
    /* the left Ctrl Windows sends before AltGr's right Alt, at its time */
    if (own == VK_LCONTROL && press && has_altgr()) {
        MSG next;
        if (PeekMessageW(&next, msg->hwnd, WM_KEYDOWN, WM_SYSKEYUP, PM_NOREMOVE) && next.wParam == VK_MENU &&
            ((next.lParam >> 24) & 1) && next.time == msg->time) {
            fake_ctrl = 1;
            return 1;
        }
    }
    if (own == VK_LCONTROL && press && !repeat) fake_ctrl = 0;
    int bit = 1 << (own & 7), held = keys_held[own >> 3] & bit;
    if (!press && !held) return 1;
    if (press) keys_held[own >> 3] |= (uint8_t) bit;
    else keys_held[own >> 3] &= (uint8_t) ~bit;
    int code = win32_xkeycode[(scan & 0xFF) + (ext ? 256 : 0)];
    WCHAR made[16], deadchar = 0;
    int nmade = 0, deadmade = 0;
    if (press) {
        /* what Windows makes of it, as its WM_CHAR (a dead key's waiting
         * character, or the character it composed) */
        TranslateMessage(msg);
        MSG c;
        for (int pass = 0; pass < 2; pass++) {
            UINT lo = pass ? WM_SYSCHAR : WM_CHAR, hi = pass ? WM_SYSDEADCHAR : WM_DEADCHAR;
            while (PeekMessageW(&c, msg->hwnd, lo, hi, PM_REMOVE)) {
                if (c.message == WM_DEADCHAR || c.message == WM_SYSDEADCHAR) deadmade = 1, deadchar = (WCHAR) c.wParam;
                else if (nmade < 16) made[nmade++] = (WCHAR) c.wParam;
            }
        }
    }
    /* the state before the key, as X's event carries it */
    BYTE before[256];
    memcpy(before, ks, sizeof before);
    before[own] = (uint8_t) ((before[own] & 1) | (press && !repeat ? 0 : 0x80));
    if (press && !repeat && (own == VK_CAPITAL || own == VK_NUMLOCK)) before[own] ^= 1;
    before[VK_SHIFT] = (before[VK_LSHIFT] | before[VK_RSHIFT]) & 0x80;
    before[VK_CONTROL] = (before[VK_LCONTROL] | before[VK_RCONTROL]) & 0x80;
    before[VK_MENU] = (before[VK_LMENU] | before[VK_RMENU]) & 0x80;
    int mods = mods_of(before), shift = mods & 1;
    uint32_t sym = table_sym(own, ext, shift), unshifted = 0;
    int consumed = 0, n = 0;
    char text[64];
    if (deadmade || (!press && own == dead_own)) {
        /* a dead key: the layout holds it now, and would combine it with
         * itself if asked what the key makes; X's dead_ keysym, no text */
        if (deadmade) {
            dead_own = own;
            dead_sym = char_sym(deadchar, 1);
            dead_unshifted = MapVirtualKeyExW(vk, MAPVK_VK_TO_CHAR, GetKeyboardLayout(0)) & 0xFFFF;
        } else {
            dead_own = 0;
        }
        sym = dead_sym;
        unshifted = dead_unshifted;
        consumed = 1;
    } else if (sym) {
        uint32_t t = sym_text(sym);
        if (press && t) {
            WCHAR w = (WCHAR) t;
            n = utf8_of(&w, 1, text, sizeof text);
        }
        if (numpad(own, ext)) consumed = 1 | 32;
        else unshifted = sym_text(table_sym(own, ext, 0));
        if (own == VK_TAB) consumed = 1;
    } else {
        /* the key's character at its level: Shift, Caps Lock and AltGr,
         * and never Ctrl or Alt, which X's keysym does not see */
        BYTE level[256], none[256];
        memcpy(level, ks, sizeof level);
        if (!altgr_in(ks)) without_ctrl_alt(level);
        WCHAR lv[8], un[8], other[8];
        int r = key_chars(vk, scan, level, lv, 8);
        if (r == 0 && altgr_in(ks)) {
            without_ctrl_alt(level);
            r = key_chars(vk, scan, level, lv, 8);
        }
        int dead = r < 0, nlv = r < 0 ? 1 : r;
        sym = char_sym(first_cp(lv, nlv), dead);
        memset(none, 0, sizeof none);
        int ru = key_chars(vk, scan, none, un, 8);
        unshifted = ru != 0 ? first_cp(un, ru < 0 ? 1 : ru) : 0;
        /* Shift and Caps Lock consumed when they change the key's text */
        none[VK_SHIFT] = none[VK_LSHIFT] = 0x80;
        int rs = key_chars(vk, scan, none, other, 8);
        if (rs != ru || (rs > 0 && memcmp(other, un, (size_t) rs * sizeof *un) != 0)) consumed |= 1;
        none[VK_SHIFT] = none[VK_LSHIFT] = 0;
        none[VK_CAPITAL] = 1;
        int rc = key_chars(vk, scan, none, other, 8);
        if (rc != ru || (rc > 0 && memcmp(other, un, (size_t) rc * sizeof *un) != 0)) consumed |= 16;
        if (press) {
            if ((mods & 6) && !altgr_in(ks)) n = dead ? 0 : utf8_of(lv, nlv, text, sizeof text);
            else if (nmade) n = utf8_of(made, nmade, text, sizeof text);
            else if (!deadmade && !dead) n = utf8_of(lv, nlv, text, sizeof text);
        }
    }
    if (own == VK_RMENU && !press) fake_ctrl = 0;
    key_record(press ? (repeat ? 2 : 1) : 0, code, mods, consumed, unshifted, sym, text, n);
    return 1;
}

/* THE POINTER (WS7) */

/* Ghostty's numbers of the buttons held, a bit each. */
static int buttons_held;
static int wheel_v, wheel_h, last_x = INT32_MIN, last_y = INT32_MIN;

static void pointer_record(int action, int button, int x, int y) {
    int mods = mods_now();
    EnterCriticalSection(&queue_lock);
    int w = win_w, h = win_h, cw = cell_w, ch = cell_h;
    LeaveCriticalSection(&queue_lock);
    last_x = x;
    last_y = y;
    uint8_t r[17] = {9, (uint8_t) action, (uint8_t) button, (uint8_t) (mods >> 8), (uint8_t) mods,
                     (uint8_t) ((uint16_t) x >> 8), (uint8_t) x, (uint8_t) ((uint16_t) y >> 8), (uint8_t) y,
                     (uint8_t) (w >> 8), (uint8_t) w, (uint8_t) (h >> 8), (uint8_t) h,
                     (uint8_t) (cw >> 8), (uint8_t) cw, (uint8_t) (ch >> 8), (uint8_t) ch};
    record_as(r, sizeof r, action == 2);
}

static void button(HWND h, int press, int b, LPARAM lp) {
    if (press) {
        if (!buttons_held) SetCapture(h);
        buttons_held |= 1 << b;
    } else {
        buttons_held &= ~(1 << b);
        if (!buttons_held && GetCapture() == h) ReleaseCapture();
    }
    pointer_record(press ? 0 : 1, b, GET_X_LPARAM(lp), GET_Y_LPARAM(lp));
}

/* The wheel's steps, 120 of delta each; a turn the other way forgets what
 * was summed. Up and left are X's buttons 4 and 6. */
static void wheel(HWND h, int *sum, int delta, int up, int down, LPARAM lp) {
    POINT p = {GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
    ScreenToClient(h, &p);
    if ((*sum > 0 && delta < 0) || (*sum < 0 && delta > 0)) *sum = 0;
    *sum += delta;
    for (; *sum >= WHEEL_DELTA; *sum -= WHEEL_DELTA) pointer_record(0, up, p.x, p.y);
    for (; *sum <= -WHEEL_DELTA; *sum += WHEEL_DELTA) pointer_record(0, down, p.x, p.y);
}

static void set_pointer_shape(void) { SetCursor(LoadCursorW(NULL, (LPCWSTR) (pointer_arrow ? IDC_ARROW : IDC_IBEAM))); }

/* THE IME (WS6) */

/* The preedit's length in code points, as last recorded, which the next
 * replaces; whether a composition is under way; and the spot, in cells. */
static int preedit_cps, composing, spot_x, spot_y;

/* What IMM32 calls an attribute, as XIM's feedback: the clause being
 * converted reversed, the rest underlined. */
static uint8_t feedback_of(BYTE attr) { return attr == ATTR_TARGET_CONVERTED || attr == ATTR_TARGET_NOTCONVERTED ? 1 : 2; }

static WCHAR *comp_string(HIMC c, DWORD which, int *units) {
    LONG bytes = ImmGetCompositionStringW(c, which, NULL, 0);
    if (bytes < 0) bytes = 0;
    WCHAR *w = malloc((size_t) bytes + sizeof(WCHAR));
    if (bytes) bytes = ImmGetCompositionStringW(c, which, w, (DWORD) bytes);
    if (bytes < 0) bytes = 0;
    *units = (int) (bytes / (LONG) sizeof(WCHAR));
    return w;
}

static void record_preedit(const WCHAR *w, int units, const BYTE *attrs, int nattrs, int cursor) {
    static uint8_t rec[9 + 4000 + 2 + 1000];
    int cps = 0, caret = 0, nf = 0;
    uint8_t fb[1000];
    for (int i = 0; i < units; i++) {
        if (w[i] >= 0xDC00 && w[i] < 0xE000 && i > 0 && w[i - 1] >= 0xD800 && w[i - 1] < 0xDC00) continue;
        if (i < cursor) caret++;
        if (nf < 1000) fb[nf++] = feedback_of(i < nattrs ? attrs[i] : ATTR_INPUT);
        cps++;
    }
    int n = utf8_of(w, units, (char *) rec + 9, 4000);
    rec[0] = 6;
    rec[1] = (uint8_t) (caret >> 8);
    rec[2] = (uint8_t) caret;
    rec[3] = 0;
    rec[4] = 0;
    rec[5] = (uint8_t) (preedit_cps >> 8);
    rec[6] = (uint8_t) preedit_cps;
    rec[7] = (uint8_t) (n >> 8);
    rec[8] = (uint8_t) n;
    rec[9 + n] = (uint8_t) (nf >> 8);
    rec[10 + n] = (uint8_t) nf;
    memcpy(rec + 11 + n, fb, (size_t) nf);
    record(rec, 11 + n + nf);
    preedit_cps = cps;
}

static void ime_composition(HWND h, LPARAM lp) {
    HIMC c = ImmGetContext(h);
    if (!c) return;
    composing = 1;
    if (lp & GCS_RESULTSTR) {
        int units;
        WCHAR *w = comp_string(c, GCS_RESULTSTR, &units);
        static uint8_t rec[3 + 4000];
        int n = utf8_of(w, units, (char *) rec + 3, 4000);
        rec[0] = 5;
        rec[1] = (uint8_t) (n >> 8);
        rec[2] = (uint8_t) n;
        if (n) record(rec, 3 + n);
        free(w);
    }
    if (lp & GCS_COMPSTR) {
        int units;
        WCHAR *w = comp_string(c, GCS_COMPSTR, &units);
        BYTE attrs[1000];
        LONG na = ImmGetCompositionStringW(c, GCS_COMPATTR, attrs, sizeof attrs);
        LONG cursor = ImmGetCompositionStringW(c, GCS_CURSORPOS, NULL, 0);
        record_preedit(w, units, attrs, na > 0 ? (int) na : 0, cursor >= 0 ? (int) cursor : units);
        free(w);
    } else if (preedit_cps > 0) {
        /* a commit that leaves nothing composing, or a composition given up */
        record_preedit(L"", 0, NULL, 0, 0);
    }
    ImmReleaseContext(h, c);
}

static void ime_done(void) {
    if (preedit_cps > 0) record_preedit(L"", 0, NULL, 0, 0);
    if (composing) {
        uint8_t r[1] = {7};
        record(r, 1);
    }
    composing = 0;
}

/* The IME's windows at the spot's cell: its composition window there (never
 * shown, as puritty draws the preedit, but the IME reads it), and the
 * candidates beside the cell, not over it. */
static void place_ime(HWND h) {
    HIMC c = ImmGetContext(h);
    if (!c) return;
    EnterCriticalSection(&queue_lock);
    int cw = cell_w, ch = cell_h;
    LeaveCriticalSection(&queue_lock);
    int x = spot_x * cw, y = spot_y * ch;
    COMPOSITIONFORM cf = {CFS_POINT, {x, y}, {0, 0, 0, 0}};
    ImmSetCompositionWindow(c, &cf);
    CANDIDATEFORM cand = {0, CFS_EXCLUDE, {x, y}, {x, y, x + cw, y + ch}};
    ImmSetCandidateWindow(c, &cand);
    ImmReleaseContext(h, c);
}

static void size_in(int w, int h) {
    EnterCriticalSection(&queue_lock);
    int cw = cell_w, ch = cell_h;
    win_w = w;
    win_h = h;
    LeaveCriticalSection(&queue_lock);
    if (cw <= 0 || ch <= 0) return;
    int c = w / cw, r = h / ch;
    if (c < 1) c = 1;
    if (r < 1) r = 1;
    if (c > 65535) c = 65535;
    if (r > 65535) r = 65535;
    if (c == win_cols && r == win_rows) return;
    win_cols = c;
    win_rows = r;
    uint8_t rec[5] = {2, (uint8_t) (c >> 8), (uint8_t) c, (uint8_t) (r >> 8), (uint8_t) r};
    record(rec, 5);
}

static void focus_in(int in) {
    /* keys held while the focus left are released elsewhere */
    if (!in) memset(keys_held, 0, sizeof keys_held);
    if (in == focused) return;
    focused = in;
    uint8_t rec[2] = {3, (uint8_t) in};
    record(rec, 2);
}

static void paint_window(HWND h) {
    PAINTSTRUCT ps;
    HDC dc = BeginPaint(h, &ps);
    RECT client;
    GetClientRect(h, &client);
    EnterCriticalSection(&paint);
    if (pixels && pw > 0 && ph > 0) {
        BITMAPINFO bi;
        memset(&bi, 0, sizeof bi);
        bi.bmiHeader.biSize = sizeof bi.bmiHeader;
        bi.bmiHeader.biWidth = pw;
        bi.bmiHeader.biHeight = -ph; /* top-down */
        bi.bmiHeader.biPlanes = 1;
        bi.bmiHeader.biBitCount = 32;
        bi.bmiHeader.biCompression = BI_RGB;
        SetDIBitsToDevice(dc, 0, 0, (DWORD) pw, (DWORD) ph, 0, 0, 0, (UINT) ph, pixels, &bi, DIB_RGB_COLORS);
    }
    uint32_t m = margin_rgb;
    int w = pw, hh = ph;
    LeaveCriticalSection(&paint);
    HBRUSH b = CreateSolidBrush(RGB((m >> 16) & 0xff, (m >> 8) & 0xff, m & 0xff));
    RECT right = {w, 0, client.right, client.bottom}, below = {0, hh, w, client.bottom};
    if (right.left < right.right) FillRect(dc, &right, b);
    if (below.top < below.bottom) FillRect(dc, &below, b);
    DeleteObject(b);
    EndPaint(h, &ps);
}

static LRESULT CALLBACK proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_PAINT:
        paint_window(h);
        return 0;
    case WM_ERASEBKGND:
        return 1;
    case WM_SIZE:
        size_in(LOWORD(lp), HIWORD(lp));
        return 0;
    case WM_SETFOCUS:
        focus_in(1);
        return 0;
    case WM_KILLFOCUS:
        focus_in(0);
        return 0;
    case WM_SETCURSOR:
        if (LOWORD(lp) == HTCLIENT) {
            set_pointer_shape();
            return TRUE;
        }
        break;
    case WM_APP_POINTER: {
        POINT p;
        RECT r;
        GetCursorPos(&p);
        GetClientRect(h, &r);
        if (WindowFromPoint(p) == h && ScreenToClient(h, &p) && PtInRect(&r, p)) set_pointer_shape();
        return 0;
    }
    case WM_LBUTTONDOWN: case WM_LBUTTONUP:
        button(h, m == WM_LBUTTONDOWN, 1, lp);
        return 0;
    case WM_MBUTTONDOWN: case WM_MBUTTONUP:
        button(h, m == WM_MBUTTONDOWN, 3, lp);
        return 0;
    case WM_RBUTTONDOWN: case WM_RBUTTONUP:
        button(h, m == WM_RBUTTONDOWN, 2, lp);
        return 0;
    case WM_XBUTTONDOWN: case WM_XBUTTONUP:
        button(h, m == WM_XBUTTONDOWN, GET_XBUTTON_WPARAM(wp) == XBUTTON1 ? 8 : 9, lp);
        return TRUE;
    case WM_CAPTURECHANGED:
        if ((HWND) lp != h) buttons_held = 0;
        return 0;
    case WM_MOUSEMOVE: {
        int x = GET_X_LPARAM(lp), y = GET_Y_LPARAM(lp);
        int any = (wp & (MK_LBUTTON | MK_MBUTTON | MK_RBUTTON | MK_XBUTTON1 | MK_XBUTTON2)) != 0;
        /* Windows sends a motion where there was none (a window shown
         * under the pointer, a button pressed) */
        if ((any || all_motion) && (x != last_x || y != last_y)) pointer_record(2, 0, x, y);
        return 0;
    }
    case WM_MOUSEWHEEL:
        wheel(h, &wheel_v, GET_WHEEL_DELTA_WPARAM(wp), 4, 5, lp);
        return 0;
    case WM_MOUSEHWHEEL:
        wheel(h, &wheel_h, GET_WHEEL_DELTA_WPARAM(wp), 7, 6, lp);
        return 0;
    case WM_IME_SETCONTEXT:
        /* puritty draws the preedit; the IME's candidates are its own */
        lp &= ~(LPARAM) ISC_SHOWUICOMPOSITIONWINDOW;
        break;
    case WM_IME_STARTCOMPOSITION:
        place_ime(h);
        composing = 1;
        return 0;
    case WM_IME_COMPOSITION:
        ime_composition(h, lp);
        return 0;
    case WM_IME_ENDCOMPOSITION:
        ime_done();
        return 0;
    case WM_IME_CHAR:
        return 0;
    case WM_CLIPBOARDUPDATE:
        /* another program's clipboard now */
        if (clip_owned && GetClipboardOwner() != h) {
            InterlockedExchange(&clip_owned, 0);
            uint8_t rec[2] = {10, 1};
            record(rec, 2);
        }
        return 0;
    case WM_APP_SPOT:
        spot_x = (int) wp;
        spot_y = (int) lp;
        place_ime(h);
        return 0;
    case WM_CLOSE: {
        uint8_t rec[1] = {4};
        record(rec, 1);
        return 0;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

static void *window_thread(void *arg) {
    (void) arg;
    WNDCLASSW wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"puritty";
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR) IDC_IBEAM);
    wc.hIcon = LoadIconW(NULL, (LPCWSTR) IDI_APPLICATION);
    RegisterClassW(&wc);
    DWORD style = WS_OVERLAPPEDWINDOW, ex = 0;
    RECT r = {0, 0, open_cols * cell_w, open_rows * cell_h};
    AdjustWindowRectExForDpi(&r, style, FALSE, ex, (UINT) open_dpi);
    win = CreateWindowExW(ex, L"puritty", title0 ? title0 : L"puritty", style, CW_USEDEFAULT, CW_USEDEFAULT, r.right - r.left,
                          r.bottom - r.top, NULL, NULL, wc.hInstance, NULL);
    SetEvent(made);
    if (!win) {
        geng_post_done(post);
        return NULL;
    }
    ShowWindow(win, SW_SHOWNORMAL);
    AddClipboardFormatListener(win);
    /* keys go through IMM32's input context, which every window has */
    HIMC c = ImmGetContext(win);
    if (c) {
        ImmReleaseContext(win, c);
        uint8_t rec[1] = {8};
        record(rec, 1);
    }
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        if (msg.hwnd == win &&
            (msg.message == WM_KEYDOWN || msg.message == WM_KEYUP || msg.message == WM_SYSKEYDOWN || msg.message == WM_SYSKEYUP) &&
            key_message(&msg))
            continue;
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    geng_post_done(post);
    return NULL;
}

/* On the program's thread, for each post the window thread sent. */
static void ready(void *env, void *message) {
    free(message);
    holder *h = env;
    geng_wait *w = h->pending;
    if (w == NULL) return;
    EnterCriticalSection(&queue_lock);
    int n = evlen;
    LeaveCriticalSection(&queue_lock);
    if (n == 0) return;
    h->pending = NULL;
    geng_succeed(w, geng_slot_I4(1));
}

/* THE ROWS */

static char *string_of(void *bytes) {
    geng_bytes *b = bytes;
    char *s = malloc((size_t) b->length + 1);
    memcpy(s, b->data, (size_t) b->length);
    s[b->length] = 0;
    return s;
}

static int write_shot(const char *path);

static void at_exit(void) {
    if (getenv("PURITTY_STATS")) pt_stats("win32");
    const char *path = getenv("PURITTY_SHOT");
    if (path && pixels) write_shot(path);
    /* the window kept on the screen a while, its thread still painting,
     * so that a program that draws and ends can be seen and photographed */
    const char *linger = getenv("PURITTY_LINGER");
    if (linger && atoi(linger) > 0 && win) {
        InvalidateRect(win, NULL, FALSE);
        Sleep((DWORD) atoi(linger));
    }
}

/* Opens the window: `c` by `r` cells of the font `font` at `points`,
 * fallback asked in `lang` (V25), the glyphs begun again past `cap` bytes
 * (V37). Answers the cell as `width * 65536 + height`, or -1 no font, -2
 * no window. */
geng_cancel puritty_win32_open(int32_t c, int32_t r, int32_t points, void *font_bytes, void *lang_bytes, int32_t cap,
                               void *title_bytes, geng_wait *wait) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    InitializeCriticalSection(&paint);
    InitializeCriticalSection(&queue_lock);
    const char *forced = getenv("PURITTY_DPI");
    int dpi = forced && atoi(forced) > 0 ? atoi(forced) : (int) GetDpiForSystem();
    pt_verbose = getenv("PURITTY_STATS") != NULL;
    if (pt_verbose) fprintf(stderr, "dpi %d\n", dpi);
    FT_Init_FreeType(&ftlib);
    const char *dirs = getenv("PURITTY_FONT_DIRS");
    if (dirs && *dirs) {
        dirs_mode = 1;
        scan_dirs(dirs);
    }
    const char *list = getenv("PURITTY_FALLBACK");
    fallback_list = copy(list && *list ? list : windows_fallback);
    char *font = string_of(font_bytes), *lang = string_of(lang_bytes);
    int opened = pt_open(font, lang, points, dpi, cap);
    free(font);
    free(lang);
    if (opened != 0) {
        geng_succeed(wait, geng_slot_I4(-1));
        return (geng_cancel) {0};
    }
    cell_w = pt_cw;
    cell_h = pt_ch;
    open_cols = c;
    open_rows = r;
    open_dpi = dpi;
    char *title = string_of(title_bytes);
    title0 = wide(title);
    free(title);
    pt_resize(c, r);
    margin_rgb = pt_default_bg();
    atexit(at_exit);
    /* old, so that the static and the post's environment never see it
     * move; the post keeps it alive, and the image's statics are roots */
    held = geng_alloc_old(sizeof *held, HOLDER_HEADER);
    held->pending = NULL;
    post = geng_post_open(ready, free, held);
    made = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (post == NULL || geng_thread_start(window_thread, NULL) != 0) {
        geng_succeed(wait, geng_slot_I4(-2));
        return (geng_cancel) {0};
    }
    WaitForSingleObject(made, INFINITE);
    geng_succeed(wait, geng_slot_I4(win ? pt_cw * 65536 + pt_ch : -2));
    return (geng_cancel) {0};
}

/* Executes one frame's display list, and invalidates the rows it drew and,
 * when the default background changed, the margins. */
geng_cancel puritty_win32_draw(void *list, geng_wait *wait) {
    geng_bytes *b = list;
    PtFrame frame;
    EnterCriticalSection(&paint);
    pt_frame(b->data, (size_t) b->length, &frame);
    uint32_t bg = pt_default_bg();
    int margins = frame.sized || bg != margin_rgb;
    margin_rgb = bg;
    LeaveCriticalSection(&paint);
    if (margins) InvalidateRect(win, NULL, FALSE);
    else if (frame.last >= frame.first) {
        RECT rows = {0, frame.first * pt_ch, pt_cols * pt_cw, (frame.last + 1) * pt_ch};
        InvalidateRect(win, &rows, FALSE);
    }
    int inklen;
    const uint8_t *ink = pt_ink(&inklen);
    geng_bytes *a = geng_alloc_atomic(sizeof *a + (size_t) inklen + 1, GENG_HEADER_BYTES(sizeof *a + (size_t) inklen + 1));
    a->length = inklen + 1;
    a->pad = 0;
    a->data = (uint8_t *) (a + 1);
    a->buffer = NULL;
    a->block = NULL;
    a->data[0] = IsWindow(win) ? 0 : 1;
    if (inklen) memcpy(a->data + 1, ink, (size_t) inklen);
    geng_succeed(wait, geng_slot_P(a));
    return (geng_cancel) {0};
}

/* The window as a PPM: its client area, the bitmap and the margins past
 * it in the default background, as WM_PAINT shows them. Answers 0, or -1. */
static int write_shot(const char *path) {
    RECT client = {0, 0, 0, 0};
    if (win) GetClientRect(win, &client);
    EnterCriticalSection(&paint);
    int w = client.right > 0 ? client.right : pw, h = client.bottom > 0 ? client.bottom : ph;
    FILE *o = fopen(path, "wb");
    if (!o) {
        LeaveCriticalSection(&paint);
        return -1;
    }
    fprintf(o, "P6\n%d %d\n255\n", w, h);
    uint8_t *line = malloc((size_t) w * 3);
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            uint32_t p = x < pw && y < ph ? pixels[(size_t) y * pw + x] : margin_rgb;
            line[x * 3] = (uint8_t) (p >> 16);
            line[x * 3 + 1] = (uint8_t) (p >> 8);
            line[x * 3 + 2] = (uint8_t) p;
        }
        fwrite(line, 1, (size_t) w * 3, o);
    }
    free(line);
    LeaveCriticalSection(&paint);
    fclose(o);
    return 0;
}

geng_cancel puritty_win32_shot(void *path_bytes, geng_wait *wait) {
    char *path = string_of(path_bytes);
    int r = write_shot(path);
    free(path);
    geng_succeed(wait, geng_slot_I4(r));
    return (geng_cancel) {0};
}

static geng_task *stop(void *env) {
    holder *h = env;
    h->pending = NULL;
    return NULL;
}

/* Answers 1 once records are there, or -1 once the window is gone. */
geng_cancel puritty_win32_events(geng_wait *wait) {
    EnterCriticalSection(&queue_lock);
    int n = evlen;
    LeaveCriticalSection(&queue_lock);
    if (n > 0 || !IsWindow(win)) {
        geng_succeed(wait, geng_slot_I4(n > 0 ? 1 : -1));
        return (geng_cancel) {0};
    }
    held->pending = wait;
    geng_write_barrier(held, &held->pending, wait);
    return (geng_cancel) {stop, held};
}

geng_cancel puritty_win32_take(geng_wait *wait) {
    EnterCriticalSection(&queue_lock);
    int n = evlen;
    geng_bytes *b = geng_alloc_atomic(sizeof *b + (size_t) n, GENG_HEADER_BYTES(sizeof *b + (size_t) n));
    b->length = n;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    memcpy(b->data, evbuf, (size_t) n);
    evlen = 0;
    last_motion = -1;
    LeaveCriticalSection(&queue_lock);
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}

/* The font at `points` (V50): the window kept at its size in pixels, and
 * the cells that now fit it reported as a new size. */
geng_cancel puritty_win32_zoom(int32_t points, geng_wait *wait) {
    EnterCriticalSection(&paint);
    int changed = pt_zoom(points, open_dpi);
    LeaveCriticalSection(&paint);
    if (changed) {
        EnterCriticalSection(&queue_lock);
        cell_w = pt_cw;
        cell_h = pt_ch;
        int w = win_w, h = win_h;
        LeaveCriticalSection(&queue_lock);
        win_cols = -1;
        size_in(w, h);
        pt_resize(win_cols, win_rows);
        InvalidateRect(win, NULL, FALSE);
    }
    geng_succeed(wait, geng_slot_I4(pt_cw * 65536 + pt_ch));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_title(void *text, geng_wait *wait) {
    char *t = string_of(text);
    wchar_t *w = wide(t);
    free(t);
    SetWindowTextW(win, w);
    free(w);
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* The pointer over the window: 0 the I-beam, 1 the arrow; the window's
 * thread sets it at once when the pointer is over the window. */
geng_cancel puritty_win32_pointer(int32_t arrow, geng_wait *wait) {
    if ((arrow != 0) != (pointer_arrow != 0)) {
        InterlockedExchange(&pointer_arrow, arrow != 0);
        if (win) PostMessageW(win, WM_APP_POINTER, 0, 0);
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_motion(int32_t all, geng_wait *wait) {
    InterlockedExchange(&all_motion, all != 0);
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* Where the IME's windows belong (WS6): a cell, sent to the window's
 * thread, which owns the input context, when it moves. */
geng_cancel puritty_win32_spot(int32_t x, int32_t y, geng_wait *wait) {
    static int32_t sx = -1, sy = -1;
    if (win && (x != sx || y != sy)) {
        sx = x;
        sy = y;
        PostMessageW(win, WM_APP_SPOT, (WPARAM) x, (LPARAM) y);
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* THE SELECTIONS (WS8, V53)
 *
 * The clipboard is Windows': a copy owns it with the text as UTF-16, its
 * lines ended CRLF as Windows' programs end them, and a paste reads it,
 * CRLF made LF as Linux's text is. PRIMARY is puritty's own (V53): a
 * selection made is kept here, and a paste of PRIMARY answers it; no other
 * program takes it, so it is never lost. A paste is answered at once, but
 * as X11's is: a `Pasted` record (11), and `puritty_win32_pasted` takes the
 * text, so the application does not know which. Losing the clipboard to
 * another program is record 10, as X11's SelectionClear. */

static char *primary;
static size_t primary_len;
static uint8_t *pbuf;
static size_t plen;

static int open_clipboard(void) {
    for (int i = 0; i < 20; i++) {
        if (OpenClipboard(win)) return 1;
        Sleep(5);
    }
    return 0;
}

static void own_clipboard(const uint8_t *text, size_t n) {
    /* LF as CRLF, then UTF-16 */
    char *crlf = malloc(n * 2 + 1);
    size_t k = 0;
    for (size_t i = 0; i < n; i++) {
        if (text[i] == '\n' && (i == 0 || text[i - 1] != '\r')) crlf[k++] = '\r';
        crlf[k++] = (char) text[i];
    }
    crlf[k] = 0;
    int units = MultiByteToWideChar(CP_UTF8, 0, crlf, (int) k + 1, NULL, 0);
    HGLOBAL g = GlobalAlloc(GMEM_MOVEABLE, (size_t) (units > 0 ? units : 1) * sizeof(WCHAR));
    if (g) {
        WCHAR *w = GlobalLock(g);
        if (units <= 0 || !MultiByteToWideChar(CP_UTF8, 0, crlf, (int) k + 1, w, units)) w[0] = 0;
        GlobalUnlock(g);
    }
    free(crlf);
    if (!g) return;
    if (!open_clipboard()) {
        GlobalFree(g);
        return;
    }
    InterlockedExchange(&clip_owned, 1);
    EmptyClipboard();
    if (!SetClipboardData(CF_UNICODETEXT, g)) GlobalFree(g);
    CloseClipboard();
}

/* The clipboard's text as UTF-8, CRLF made LF, into the paste's buffer. */
static void read_clipboard(void) {
    plen = 0;
    if (!IsClipboardFormatAvailable(CF_UNICODETEXT) || !open_clipboard()) return;
    HANDLE h = GetClipboardData(CF_UNICODETEXT);
    const WCHAR *w = h ? GlobalLock(h) : NULL;
    if (w) {
        size_t units = GlobalSize(h) / sizeof(WCHAR), n = 0;
        while (n < units && w[n]) n++;
        int bytes = n ? WideCharToMultiByte(CP_UTF8, 0, w, (int) n, NULL, 0, NULL, NULL) : 0;
        free(pbuf);
        pbuf = malloc((size_t) bytes + 1);
        if (bytes > 0) WideCharToMultiByte(CP_UTF8, 0, w, (int) n, (char *) pbuf, bytes, NULL, NULL);
        for (int i = 0; i < bytes; i++)
            if (!(pbuf[i] == '\r' && i + 1 < bytes && pbuf[i + 1] == '\n')) pbuf[plen++] = pbuf[i];
        GlobalUnlock(h);
    }
    CloseClipboard();
}

/* The window owns PRIMARY (0) or the clipboard (1) with this text. */
geng_cancel puritty_win32_select(int32_t which, void *text, geng_wait *wait) {
    geng_bytes *t = text;
    if (which == 0) {
        free(primary);
        primary = malloc((size_t) t->length + 1);
        memcpy(primary, t->data, (size_t) t->length);
        primary_len = (size_t) t->length;
    } else if (which == 1 && win) {
        own_clipboard(t->data, (size_t) t->length);
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

/* A paste of PRIMARY (0) or the clipboard (1): its text is read now, and
 * a `Pasted` record says it is there. Always 1: none is ever under way. */
geng_cancel puritty_win32_paste(int32_t which, geng_wait *wait) {
    if (which == 0) {
        free(pbuf);
        pbuf = malloc(primary_len + 1);
        if (primary_len) memcpy(pbuf, primary, primary_len);
        plen = primary_len;
    } else {
        read_clipboard();
    }
    uint8_t r[2] = {11, 0};
    record(r, 2);
    geng_succeed(wait, geng_slot_I4(1));
    return (geng_cancel) {0};
}

/* The paste's text since it was last taken, UTF-8. */
geng_cancel puritty_win32_pasted(geng_wait *wait) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b + plen, GENG_HEADER_BYTES(sizeof *b + plen));
    b->length = (int64_t) plen;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    if (plen) memcpy(b->data, pbuf, plen);
    plen = 0;
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}

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
 * Events in this step (WS12 step 3): the size in cells (2), the focus (3)
 * and a request to close (4). Keys, the pointer and the IME are step 4's.
 *
 * PURITTY_DPI sets the resolution outright, else the system's; PURITTY_STATS
 * prints counts when the program ends; PURITTY_SHOT=FILE writes the window
 * then, as `puritty_win32_shot` does; PURITTY_LINGER=MS keeps the window on
 * the screen that long after, for a picture of it. */
#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>

#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "geng.h"
#include "puritty_text.h"

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

/* A record queued, and the post sent when the queue was empty, which wakes
 * Geng's loop; under the queue's lock. */
static void record(const uint8_t *r, int n) {
    EnterCriticalSection(&queue_lock);
    int was = evlen;
    if (evlen + n <= (int) sizeof evbuf) {
        memcpy(evbuf + evlen, r, (size_t) n);
        evlen += n;
    }
    LeaveCriticalSection(&queue_lock);
    if (was == 0) geng_post_send(post, malloc(1));
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
            SetCursor(LoadCursorW(NULL, (LPCWSTR) IDC_IBEAM));
            return TRUE;
        }
        break;
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
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
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

/* Step 4's (WS12): the pointer's shape, every motion, the IME's spot, the
 * selections and the paste answer as if done, and change nothing yet. */
geng_cancel puritty_win32_pointer(int32_t arrow, geng_wait *wait) {
    (void) arrow;
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_motion(int32_t all, geng_wait *wait) {
    (void) all;
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_spot(int32_t x, int32_t y, geng_wait *wait) {
    (void) x;
    (void) y;
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_select(int32_t which, void *text, geng_wait *wait) {
    (void) which;
    (void) text;
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_paste(int32_t which, geng_wait *wait) {
    (void) which;
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

geng_cancel puritty_win32_pasted(geng_wait *wait) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b, GENG_HEADER_BYTES(sizeof *b));
    b->length = 0;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}

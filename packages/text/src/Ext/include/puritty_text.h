/* puritty's text renderer (docs/windows.md V52, docs/renderer.md): what
 * the platforms' windows share. It decodes a frame's display list
 * (`Vt.View`'s comment is its definition), chooses each cluster's face,
 * shapes runs with HarfBuzz, rasterises glyphs with FreeType, draws box
 * drawing itself and measures each cell's ink (V40); and it draws through
 * the calls below that a platform gives it, so that X11 and Windows draw
 * the same pixels from the same code.
 *
 * One renderer a process, as one window (geng-plan.md Q6), on one thread:
 * the one that calls `pt_open` and `pt_frame`. */
#ifndef PURITTY_TEXT_H
#define PURITTY_TEXT_H

#include <stddef.h>
#include <stdint.h>

/* WHAT THE RENDERER GIVES */

/* The cell in pixels and its baseline, from the primary font, set by
 * `pt_open` and `pt_zoom`; the screen in cells, as the display list last
 * said. */
extern int pt_cw, pt_ch, pt_ascent, pt_cols, pt_rows;

/* Counts and faces to stderr, under `who`, when a platform sets it. */
extern int pt_verbose;

/* Loads the font `font` (as the platform's `pt_font_file` names it) at
 * `points` for `dpi`, its fallback faces asked for in `lang` (empty for
 * none, V25), and the glyphs a platform keeps begun again past `cap` bytes
 * (V37). Answers 0, or -1 when there is no such font. */
int pt_open(const char *font, const char *lang, int points, int dpi, long cap);

/* Another primary font, fallback language, size in points and glyph cache
 * in place of the open one: every face closed and the glyphs begun again.
 * -1, with the open font kept, when the platform has no such font. */
int pt_refont(const char *font, const char *lang, int points, int dpi, long cap);

/* The font at `points` (V50's zoom), or at a new resolution: every face
 * sized again, the glyphs begun again. Answers 1 when the cell may have
 * changed, 0 when nothing did; the platform then makes a target for the
 * cells that fit its window with `pt_resize`. */
int pt_zoom(int points, int dpi);

/* Whether runs are shaped with the font's ligatures (`calt`, `liga`,
 * `dlig`): on until it is turned off. The platform draws every cell again
 * after a change. */
void pt_ligatures(int on);

/* A target of `c` by `r` cells, all of it the color 0: the platform's
 * `pt_target` asked for one, and filled. */
void pt_resize(int c, int r);

/* What a frame drew: the rows from `first` to `last` (none when `last` is
 * less), a glyph's reach into the rows beside them included, and whether
 * it set the screen's size. */
typedef struct {
    int first, last, sized;
} PtFrame;

/* Executes one frame's display list. */
void pt_frame(const uint8_t *list, size_t n, PtFrame *out);

/* The ink of the cells the last frame drew (V40): records of a row and a
 * column in 2 bytes each and the edges crossed in 1. */
const uint8_t *pt_ink(int *length);

/* Style 0's background, the margins' color. */
uint32_t pt_default_bg(void);

/* The interface's font (docs/settings-gui.md SG2), a family as the platform
 * names one, loaded when text is first drawn in it; and a text's width in
 * pixels in it at `px` pixels an em, its UTF-8 `s` of `n` bytes. */
void pt_interface_font(const char *name);
int pt_measure(const uint8_t *s, int n, int px);

/* The counts, to stderr, after `who` and a colon. */
void pt_stats(const char *who);

/* WHAT A PLATFORM GIVES IT */

typedef struct {
    int x, y, w, h;
} PtRect;

/* A glyph rasterised: `height` rows of `width` bytes of coverage, `stride`
 * apart (a multiple of 4), its left edge `left` pixels right of its pen and
 * its top `top` above the baseline, and the advance its pen is moved by
 * when glyphs are drawn one after another. */
typedef struct {
    int width, height, stride, left, top, advance;
    const uint8_t *data;
} PtGlyph;

/* A glyph placed, by the id `pt_glyph_add` was given it with: its pen,
 * its color, the advance it was added with, and the clip it is drawn
 * within (an index into the clips, or -1). */
typedef struct {
    uint32_t id;
    int x, y;
    uint32_t fg;
    int advance, clip;
} PtPlaced;

/* The file of the font `font` in its regular (0), bold (1), italic (2) or
 * bold italic (3), and the face's index in it; malloc'd, or NULL. A
 * platform with no face of a variant gives the regular's. */
char *pt_font_file(const char *font, int variant, int *index);

/* The file of a face for the cluster `cps`, asked in `lang` (or NULL), a
 * color one when `color`; malloc'd, or NULL when there is none. The
 * renderer checks that it has the cluster, and asks once a code point. */
char *pt_fallback_file(const uint32_t *cps, int n, int color, const char *lang, int *index);

/* Fills a rectangle of the target with a color, 0xRRGGBB. */
void pt_fill(uint32_t rgb, int x, int y, int w, int h);
void pt_fill_rects(uint32_t rgb, const PtRect *rects, int n);

/* Keeps a glyph under `id`, for `pt_glyphs_draw`; and forgets every glyph
 * kept, when the renderer begins them again. */
void pt_glyph_add(uint32_t id, const PtGlyph *glyph);
void pt_glyphs_reset(void);

/* Draws placed glyphs over the target, each in its color, in order. */
void pt_glyphs_draw(const PtPlaced *placed, int n, const PtRect *clips);

/* A color glyph's picture: `w` by `h` pixels of premultiplied ARGB, one
 * 32-bit word each, alpha in the top byte; a handle the platform chooses,
 * or NULL. Drawn over the target with its alpha; freed when the glyphs
 * are begun again. */
void *pt_picture_add(const uint32_t *argb, int w, int h);
void pt_picture_draw(void *picture, int x, int y, int w, int h);
void pt_picture_free(void *picture);

/* A new target for a screen of `c` by `r` cells; what it holds is filled
 * after. */
void pt_target(int c, int r);

/* The rows from `top` to `bottom` of the target moved `k` rows: each row
 * `y` takes what row `y + k` held. */
void pt_scroll(int top, int bottom, int k);

#endif

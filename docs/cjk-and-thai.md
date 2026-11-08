# CJK, Thai and grapheme clusters: what the references do, and what puritty needs

Requirement: Korean, Chinese, Japanese and Thai must render well, including grapheme
clusters. This doc compares how the five reference terminals handle these scripts and
turns that into design rules for puritty. §10 covers a related requirement: hosts
that use the legacy Korean encoding EUC-KR instead of UTF-8. The summary is folded
into [`synthesis.md`](synthesis.md) §3.4, §5.3, §6.5 and §9.

Sources: four focused research passes over the vendored trees (same commits as the
per-terminal docs). Paths are relative to each `vendor/<name>/` directory. Claims
marked **(inferred)** come from reading code paths, not from code or tests that state
them. Claims marked **(general knowledge)** are background about Unicode, fonts or
IMEs that should be checked against UAX #29, UAX #11, the HarfBuzz source or real IMEs
before relying on them. Ghostty's Unicode library (`uucode`) and Alacritty's
dependencies (`crossfont`, `unicode-width`) are not vendored; they were read from the
pinned versions.

---

## 0. TL;DR

- **No reference terminal gets all of this right.** Each gets different parts right:
  - Ghostty: grapheme clustering, fallback-font size normalisation, IME ordering fixes.
  - WezTerm: shaping whole clusters across font fallback, per-pane width settings.
  - Windows Terminal: the TSF IME, streaming re-measurement of the previous cell.
  - PuTTY (GTK): centring wide glyphs, the "narrow" trick for ambiguous characters.
  - Alacritty does no shaping at all: Thai marks collide and conjoining Hangul jamo
    render as garbage.
- **Shaping is mandatory** for Thai (stacked vowels and tone marks need GPOS mark
  positioning; SARA AM needs reordering) and for conjoining Hangul jamo (needs GSUB).
  Overstriking each mark at the cell origin, as Alacritty and PuTTY-on-Windows do,
  doesn't work.
- **Don't clip glyphs to their cell.** Thai stacked marks rise above a Latin font's
  ascent, and SARA AM's ring overhangs the previous cell. Draw all backgrounds, then
  all glyphs. Ghostty, WezTerm and WT do this; PuTTY clips and cuts marks off. With
  damage-limited redraw (the X11 backend), this means tracking each row's **ink
  extent** so the overhang is repainted when a neighbouring row changes (§4.3).
- **Han unification needs a language setting.** The same codepoint (直, 骨, 返) has
  different correct shapes for Japanese, Simplified Chinese, Traditional Chinese and
  Korean. Most references rely on the OS locale; WezTerm hard-codes HarfBuzz language
  `en` and passes an empty locale to DirectWrite. puritty needs a per-profile CJK
  language that feeds font fallback *and* shaping (§5.2).
- **Wide glyphs need deliberate fitting.** CJK glyphs are 1 em wide; a 2-cell box in a
  typical Latin mono font is ~1.2 em. Options: left-aligned at natural size
  (Alacritty, WT), centred (PuTTY GTK), or fallback fonts scaled to match the primary
  font's ideograph width (Ghostty's `ic_width`). Use Ghostty's scaling plus centring.
- **The width model must be per pane.** tmux panes have to use tmux's (wcwidth-style)
  widths or the cursor drifts. Local panes can use grapheme widths (mode 2027). WT and
  Ghostty make the choice global; WezTerm and PuTTY get closer.
- **IME is where most real bugs are.** All the references have Korean ordering bugs
  in their history: the last syllable lost or sent after the Enter that ended it,
  double commits, the candidate window in the wrong place. WT's TSF implementation on
  Windows and Ghostty's GTK workarounds are the best references. Nobody shapes the
  preedit, wraps long preedit, or puts the candidate window at the active clause.
- **Glyph atlases fill up with CJK.** Every reference either grows its atlas forever
  (Alacritty, Ghostty) or throws it all away when full (WezTerm, WT). Use pages with
  LRU eviction. For remote X11, the same applies to server-side glyph sets.
- **EUC-KR has to work for years.** Some users' RHEL8 hosts run in `ko_KR.euckr`. No
  reference decodes two-byte encodings properly; PuTTY has the setting but only
  per-byte decoding. Convert at the backend boundary so the core stays UTF-8, and give
  those panes ambiguous width 2 (§10).

---

## 1. Comparison

| Topic | Alacritty | Ghostty | WezTerm | Windows Terminal | PuTTY |
|---|---|---|---|---|---|
| Unicode version | 17 (`unicode-width` 0.2.2) | 18 (pinned `uucode`) | 16 | 16 | 16 |
| Ambiguous width option | no (always 1) | **no** (always 1) | yes, global config | yes, **global** | yes, per session |
| Grapheme clustering | none; width-0 chars attach (max 9) | full UAX #29 incl. GB9c; max 64 codepoints | `finl_unicode`; inline ≤7 bytes, else heap | pairwise table approximation; streaming state | none; combiners attach (max 32, then U+FFFD) |
| Mode 2027 | no | **on by default**, switchable | reported permanently set | reported fixed | no |
| Late combining mark (after SGR or in next read) | attaches to previous cell | re-feeds previous cell into break state | **dropped** (inferred) | re-measures previous cell | attaches |
| Hangul L+V+T | V/T overlaid, unshaped → broken | one 2-cell cluster, shaped | one 2-cell cluster, shaped | Graphemes mode: 2 cells, shaped; Wcswidth mode: **4 columns** (disagrees with glibc) | GTK: shaped; Windows: overstrike; Jamo Ext-B not zero-width |
| Thai marks | overstrike, collide | shaped, GPOS stacking | shaped, whole cluster moves to fallback font together | shaped by DirectWrite | GTK shaped but clipped; Windows overstrike, clipped |
| SARA AM | own cell, unshaped | 2027: joins cluster, which becomes one wide cell | joins cluster, 2 cells (inferred) | Graphemes: one 2-cell cluster | own cell |
| Shaper language | n/a | none set (guessed) | **hard-coded `en`** | OS user locale | Pango context language (GTK) |
| Fallback language | locale via fontconfig default substitution | locale via fontconfig default substitution (inferred) | **none**; DirectWrite locale `""` | OS user locale | locale (GTK); GDI font linking (Windows) |
| Fallback size matching | none | **scaled to match primary's 水 width** | per-font manual `scale`; cap-height option for non-default styles only | none | none |
| Wide glyph placement | natural size, left-aligned | natural size, centred by face width difference | width-fit: shrink if wider than 2.25 cells | natural size, left-aligned, advance snapped | GTK centred; Windows left-aligned |
| Glyph clipping | none | none | none (`TODO: clipping`) | none | **clipped to cell** |
| Synthetic bold for fallback CJK | — | **no** (inferred) | **no** for auto-discovered fonts (inferred) | DirectWrite simulations | — |
| Atlas when full | grows forever | doubles forever, no cap | clear, then double; cap at GPU max | **clear everything**, maybe grow | n/a (GDI/Pango) |
| Preedit model | text + cursor, ellipsis-truncated | code points; **zero-width marks dropped**; unshaped; no wrap | plain string; no attributes; no wrap | text + attribute ranges + caret; insert-like; no wrap | Windows: system window; GTK: overlay, shifted left |
| Candidate window anchor | cursor | cursor cell | cursor cell | cursor cell (ignores clause) | caret (`CFS_POINT`) |
| Thai word selection | one run = one word | — | — | — | — |

---

## 2. Width

### 2.1 What has to be decided

Width decides where the cursor is. The application on the far end (shell, vim, tmux)
computes widths with its own `wcwidth`. When the terminal disagrees, the cursor drifts
and lines wrap in the wrong place. The cases that matter for these scripts:

| Sequence | glibc `wcwidth` sum (general knowledge) | Grapheme mode (Ghostty, verified) | Notes |
|---|---|---|---|
| Precomposed Hangul syllable (U+AC00–D7A3) | 2 | 2 | Everyone agrees |
| Hangul L+V+T conjoining jamo | 2+0+0 = 2 | 2 | WT's Wcswidth mode gives V/T width 1 → 4 columns; PuTTY misses Jamo Ext-B (U+D7B0–D7FF) |
| Hangul L+L+V | 2+2+0 = 4 | 2 (cluster capped at 2) | Rare; Ghostty and its own library disagree |
| Thai consonant + above vowel + tone mark | 1+0+0 = 1 | 1 | Everyone agrees |
| Thai consonant + SARA AM (U+0E33) | 1+1 = 2 | 2, but as **one wide cell** | Same column total, different cell structure |
| CJK ideograph, kana, fullwidth forms | 2 | 2 | Everyone agrees |
| East Asian Ambiguous (e.g. ①, ○, Cyrillic in some fonts) | 1 | 1, or 2 by option | Needs a per-profile option for CJK users |
| Emoji with text default + VS16 (❤️) | 1 | 2 | Not CJK-specific, but common in CJK chat text |

Hangul and Thai mostly agree across models. The disagreements are SARA AM's cell
structure (Ghostty and WT make one wide cell where wcwidth implies two narrow ones;
puritty uses two narrow cells, §2.2) and the ambiguous characters.

### 2.2 SARA AM and other spacing marks

UAX #29 classes SARA AM (U+0E33, and Lao U+0EB3) as SpacingMark, so GB9a joins it to
the preceding consonant: ก + ำ is one grapheme cluster. It also has width 1 by itself.
The references differ:

- **Ghostty (2027 mode):** a cluster continuation that isn't zero-width "widens" the
  cell, so the consonant (+ marks) + SARA AM becomes one wide cell plus a spacer. The
  column total (2) matches wcwidth (`src/unicode/grapheme.zig:75-79`).
- **WT (Graphemes mode):** SpacingMark is mapped to Extend and widths are summed, so
  also one 2-cell cluster (`src/tools/GraphemeTableGen/Program.cs:261`).
- **WezTerm:** sums widths, so also 2 cells in one cluster (inferred).
- **Legacy / wcwidth:** SARA AM takes its own cell.

The column count agrees in all cases, so cursor positions stay in sync. What differs is
whether cursor movement and selection treat กำ as one unit.

**Tentative choice for puritty** (not final; open to revisiting): SARA AM takes its
own narrow cell in every width mode, so arrow keys and selection treat กำ as two
units, as legacy terminals and wcwidth do.
Consequences:

- The segmenter deviates from UAX #29 GB9a by breaking before U+0E33 and U+0EB3.
  A consonant's above/below marks (e.g. the tone mark in ก่ำ) stay in the consonant's
  cell; only SARA AM moves to the next one.
- Rendering must still shape the consonant cell and the SARA AM cell as one run in one
  font. HarfBuzz decomposes SARA AM into nikhahit + SARA AA and moves the nikhahit
  over the consonant (and above any tone mark), so that ink lands in the previous cell
  (see §4 and the ink-extent rule in §9).
- Applications using mode 2027 expect one cluster here. Column totals still agree, so
  cursor positions stay in sync; only puritty's own cursor and selection units differ.
- Indic spacing vowel signs (Mc) are not covered by this decision; they follow UAX #29
  for now.

### 2.3 Design

- **Generate width and grapheme-break tables from a pinned Unicode version** (Ghostty,
  WT, PuTTY all do; Ghostty packs width, break class and emoji flags into 16 bits per
  codepoint in a 3-stage table).
- **Width model per pane**, with these settings:
  - mode: legacy (wcwidth-compatible sum) or grapheme (2027);
  - ambiguous width: 1 or 2;
  - per-codepoint overrides (WezTerm's `cell_widths`, useful for PUA icon fonts).
- **tmux panes use the legacy model**, matching tmux's widths, because tmux keeps its
  own grid and doesn't support 2027 (general knowledge). Local panes default to
  grapheme mode.
- **Zero-width ranges must include** U+1160–11FF and U+D7B0–D7FF (Hangul V/T), and the
  Thai marks U+0E31, U+0E34–0E3A, U+0E47–0E4E.
- WezTerm's OSC 1337 `UnicodeVersion` push/pop stack lets an application say which
  width table it uses. Worth supporting alongside mode 2027.

---

## 3. Grapheme clusters

### 3.1 The rules that matter

- **Hangul:** GB6–GB8 join L, V, T, LV and LVT jamo into one syllable. Old Korean
  exists only as conjoining sequences.
- **Thai:** above and below vowels, tone marks, nikhahit and phinthu are Extend (GB9);
  SARA AM is SpacingMark (GB9a). The leading vowels เ แ โ ใ ไ are *not* Prepend, so
  they are separate clusters with their own cells (general knowledge).
- **Indic conjuncts:** GB9c (Unicode 15.1). Not needed for Thai, but cheap if you have
  the rest. Ghostty implements it; WT approximates it.

### 3.2 Streaming

Terminal output arrives in arbitrary chunks, often with escape sequences between a
base and its marks. The references show three behaviours:

- **Re-open the previous cell.** Ghostty re-feeds the previous cell's codepoints into
  the break state machine before testing the new one (`src/terminal/Terminal.zig:1330-1351`).
  WT re-measures the previous cell with the new text and may rewrite it, even widening
  it from 1 to 2 (`src/buffer/out/Row.cpp:672-718`). **Copy this.**
- **Attach any zero-width char to the previous cell** without break rules (Alacritty,
  PuTTY, Ghostty in legacy mode). Works for Thai marks; wrong for some emoji.
- **Segment only within a buffered print run** (WezTerm). A mark that arrives after an
  SGR change or in the next read batch becomes a zero-width cluster on its own and is
  **dropped** (inferred, `term/src/terminalstate/performer.rs:134-164`). Avoid.

### 3.3 Storage and limits

- Ghostty: first codepoint in the 8-byte cell, the rest in a per-page side table;
  max 64 codepoints, extras silently dropped.
- WezTerm: up to 7 UTF-8 bytes inline in a 64-bit value, else a heap box. A Hangul
  L+V+T (9 bytes) or Thai consonant + 2 marks (9 bytes) already spills.
- WT: one UTF-16 buffer per row plus a u16 column→offset map with a trailer bit for
  the second half of wide cells. No per-cluster cap.
- Alacritty caps marks at 9, PuTTY at 32 (then U+FFFD).

For puritty: Ghostty's side table, bounded by **bytes per cluster** (enough for a Thai
consonant with three marks, a full Hangul syllable, and long emoji ZWJ sequences)
rather than a small mark count.

---

## 4. Shaping and glyph placement

### 4.1 Why shaping is required

- **Thai** has up to four vertical levels: below vowel, base, above vowel, tone mark
  (กี้, ปั๊ม). Correct placement needs GPOS mark-to-base and mark-to-mark anchors.
  For fonts without GPOS, HarfBuzz's Thai fallback substitutes old Windows/Mac
  private-use glyphs (lowered tone marks, left-shifted marks over ป ฝ ฟ ฬ,
  descender-less ญ ฐ). HarfBuzz also decomposes SARA AM into nikhahit + SARA AA and
  reorders the nikhahit before a preceding tone mark (general knowledge).
- **Conjoining Hangul jamo** compose into a syllable only through GSUB
  (`ljmo`/`vjmo`/`tjmo` features).
- Overstriking each mark at the cell origin (Alacritty; PuTTY on Windows) makes marks
  collide and jamo unreadable.

### 4.2 How the shaping references work

| | Ghostty | WezTerm | WT (DirectWrite) |
|---|---|---|---|
| Run boundaries | row, style, selection edge, **cursor**, font change | attributes, presentation, whitespace (cache optimisation), bidi run; **not** cursor or selection | row, bold/italic, builtin glyph; **not** colour |
| Script | guessed once per run | guessed | `AnalyzeScript` over the whole line, shaped per script run |
| Font for a cluster | one face that covers the **whole cluster** | shape with font 0; clusters with missing glyphs move **as a unit** to font N+1, re-shaped with the full run as context | `MapCharacters` per segment |
| Map back to cells | cluster index = cell | uses stored cell widths to correct HarfBuzz cluster boundaries | cluster advance snapped to its column span |
| Cursor/selection colouring | split runs | slice glyph quads by pixel range | colour looked up per glyph |

Lessons:

- **Keep a base and its marks in one font.** Mark positioning comes from the base
  font's GPOS anchors, so a mark from a different font floats. Ghostty (pick a face
  covering the whole cluster) and WezTerm (move the whole cluster to the fallback
  font) both do this.
- **Shape across cells in the same font.** Thai SARA AM reordering and cross-cell
  context need neighbours in the same run.
- **Don't split runs at the cursor or on colour changes.** Splitting breaks shaping
  context. WezTerm slices the glyph's quad by pixel range for the cursor and
  selection; WT looks colour up per glyph. Both are better than Ghostty's split.
- **Segment by script as well as font**, or let the shaper's script analysis do it
  (WT). Ghostty and WezTerm guess one script per run, which is fragile for mixed
  Thai+Latin text in one font (inferred).
- **Map glyphs to cells using your stored widths**, not the shaper's cluster
  boundaries (WezTerm, after #2572).

### 4.3 Overflow: marks above the cell, overhang into the previous cell

- A tone mark over an above vowel reaches about 1.0–1.1 em above the baseline,
  more than most Latin mono fonts' ascent. SARA AM's ring draws over the previous
  consonant through a negative left bearing (general knowledge).
- Ghostty, WezTerm, WT and Alacritty **don't clip**; they draw all backgrounds first,
  then glyphs, so marks overflow visibly into the row above. PuTTY clips to the cell
  and cuts marks off.
- Cell height in every reference comes from the **primary font only**; fallback fonts
  never influence it. Only manual line-height settings exist.

**For puritty:**

- Don't clip glyphs to their cell. Draw backgrounds for the whole damaged region,
  then glyphs.
- **Track ink extents per row.** WT records each row's dirty top and bottom including
  overhang (`src/renderer/atlas/BackendD3D.cpp:1185-1186`). With damage-limited
  redraw this is essential: when row N is repainted, its background fill erases the
  overhanging marks of row N+1, so row N+1's glyphs (or at least the overhanging ones)
  must be redrawn too. The same applies horizontally for SARA AM's overhang. This
  affects the X11 backend directly: the damage region sent to the server must include
  the neighbours' overhang.
- Offer an automatic "ascent headroom" option that grows the cell height when a
  Thai fallback font needs it, in addition to manual line height.

### 4.4 Fitting wide glyphs into two cells

CJK ideographs are 1 em wide. Latin mono fonts are 0.5–0.6 em (JetBrains Mono 0.6,
DejaVu Sans Mono ≈0.6, Consolas 0.55, Iosevka 0.5), so two cells are 1.0–1.2 em
(general knowledge). Strategies seen:

1. **Natural size, left-aligned:** Alacritty, WT, PuTTY on Windows. Looks lopsided.
2. **Natural size, centred** in the 2-cell box: PuTTY GTK; Ghostty centres by the face
   width difference.
3. **Scale the fallback font to match the primary font:** Ghostty scales each fallback
   face so its 水 (U+6C34) advance matches the primary font's ideograph width
   (like CSS `font-size-adjust`). It falls back to ex-height, cap-height, then line
   height, and guards against Nerd-Font-patched CJK fonts with bogus advances
   (`src/font/Collection.zig:571-660`).
4. **Shrink only glyphs that overflow:** WezTerm scales a glyph down if it's wider than
   2.25 cells.

For puritty: Ghostty's ideograph-width scaling, then centre horizontally in the 2-cell
box, align on the Latin baseline, and shrink only if it still overflows. Plus:

- **PuTTY's "narrow" trick:** when the terminal says a character is 1 cell but the
  font draws it 2 cells wide (typically an ambiguous character in a CJK font), draw
  it compressed (`terminal/terminal.c:6220-6231`).
- **Synthesise bold and italic for fallback fonts.** Ghostty and WezTerm only
  synthesise for the primary font, so bold CJK text from auto-fallback renders
  regular (inferred in both).

---

## 5. Fonts

### 5.1 Fallback discovery

- Ghostty: `font-codepoint-map` overrides → loaded faces → discovery. The first face
  found for a Han character is added permanently, so later Han characters prefer it
  (inferred). fontconfig query with charset and "monospace"; no language.
- WezTerm: asynchronous fallback on a background thread ("draw now, redraw when found"),
  with a tried-codepoint set and minimal covering set. Each codepoint queried
  separately because combined fontconfig queries failed (#4310). Clears the *whole*
  shape cache when a fallback arrives.
- WT: user list `"Primary, Fallback1, …"` mapped over the full Unicode range, then the
  system fallback. No per-script mapping. Fallback and shaping run under the terminal
  lock; `MapCharacters` is "awfully slow".
- Bundled fonts: Ghostty and WezTerm bundle Latin, emoji and symbol fonts, but **no CJK
  or Thai font**.

### 5.2 Han unification

The same codepoint has different correct glyphs per region (直, 骨, 返, 刃, 角, 写 are
classic examples). Native readers notice. Pan-CJK fonts (Noto Sans CJK, Source Han
Sans) ship per-region faces in one collection plus `locl` substitutions keyed by
OpenType language (JAN, KOR, ZHS, ZHT, ZHH) (general knowledge). Four levers select the
right one:

1. fontconfig `lang` in the match pattern (otherwise `FcDefaultSubstitute` takes it
   from the process locale);
2. the DirectWrite locale passed to `MapCharacters` and the text-analysis source;
3. the HarfBuzz buffer language, which drives `locl`;
4. explicit user config: a font per script or codepoint range.

| Terminal | What it does |
|---|---|
| Alacritty | process locale via fontconfig; user locale on Windows |
| Ghostty | process locale via fontconfig (inferred); no shaper language; macOS gets a locale-aware path for U+4E00–9FFF only |
| WezTerm | **none**: no fontconfig `lang`, DirectWrite locale `""`, HarfBuzz `en` (so `locl` never selects CJK forms); macOS only uses `AppleLanguages` |
| WT | OS user locale for fallback and shaping; no per-profile override (a Japanese user on a zh-CN system gets Chinese forms) |
| PuTTY | Pango context language (GTK); optional explicit "font for wide (CJK) text" |

There is no in-band escape sequence for language tagging (general knowledge), so it has
to be configuration. **puritty:** a per-profile CJK language (ja, ko, zh-Hans,
zh-Hant, zh-HK), defaulting from the OS locale, passed to all three of fontconfig,
DirectWrite and the shaper; plus per-script or per-range font overrides (Ghostty's
`font-codepoint-map`).

### 5.3 A UTF-16 bug to avoid

WezTerm's DirectWrite fallback builds its UTF-16 buffer with `c as u16`
(`wezterm-font/src/locator/gdi.rs:266`), which truncates codepoints above U+FFFF:
CJK Extension B and later, and emoji (inferred). Any Windows code path converting to
UTF-16 must emit surrogate pairs.

---

## 6. Glyph atlas (and X11 glyph sets)

- Alacritty and Ghostty grow forever; Ghostty doubles with no cap against the GPU
  maximum texture size and re-uploads everything on growth.
- WezTerm starts at 128×128, clears the atlas when full, then doubles. Every overflow
  re-rasterises everything visible.
- WT sizes the atlas at about twice the swap chain area and clears it entirely when
  full, flushing queued quads mid-frame. If one screen's unique glyphs exceed the
  atlas (tall fallback glyphs, emoji), it would clear every frame (inferred).

Reading a Chinese or Japanese document can easily put thousands of distinct glyphs on
screen over a few minutes. **puritty:** several fixed-size atlas pages with LRU or
epoch eviction at page granularity, sized for CJK from the start, capped at the
device's maximum texture size.

**Remote X11:** server-side XRender glyph sets have the same problem in a different
place. Each new glyph is uploaded once (a 24×24 grayscale glyph is ~600 bytes, so
3,000 glyphs is ~2 MB, sent once). Keep an LRU of server-side glyph ids and free old
ones with `RenderFreeGlyphs` so server memory stays bounded (general knowledge for the
sizes).

---

## 7. IME

### 7.1 How Korean, Japanese and Chinese IMEs behave (general knowledge)

- **Korean:** composition rewrites one syllable on every keystroke (ㅎ → 하 → 한). Typing
  a vowel after 한 splits it: 하 is committed and 나 becomes the new preedit, often in
  the same event. A non-letter key (Enter, arrow, Space, Ctrl-shortcut) must first
  commit the syllable, *then* act.
- **Japanese:** long, multi-clause preedit with per-clause attributes (unconverted,
  converted, target clause) and a caret inside it. The candidate window should sit at
  the target clause, not the preedit start. The preedit can be longer than the rest
  of the row.
- **Chinese:** pinyin and similar IMEs have a preedit of Latin letters with a candidate
  list; IME state such as paired punctuation should survive unrelated keys.

### 7.2 Bugs the references hit, and their fixes

| Bug | Where | Fix |
|---|---|---|
| Key that ended a composition reaches the shell **before** the committed syllable (Enter before 한) | WT GH#20244 | Flush the pending composition **synchronously** before handling the key (`src/tsf/Implementation.cpp:232-252`, `TermControl.cpp:1770-1774`) |
| Keys forwarded to the shell during composition (← moves cursor before 가 commits) | WT #20039 | Never forward keys during composition; the IME re-injects them |
| Composition between existing syllables hides text to the right | WT #20041 | Draw preedit insert-style, absorbing spaces |
| Each Korean syllable left as an uncommitted "interim char" | WT | `TF_TMAE_CONSOLE` disables single-character composition (test: typing `gksks` must give 하난) |
| fcitx5-hangul commits then immediately sends preedit-changed | Ghostty | Treat any preedit change as "composing" (`apprt/gtk/class/surface.zig:3218-3224`) |
| IMEs disagree on commit vs. preedit-end order; ibus 1.5.29 never sends preedit-end | Ghostty | Track composing state per key event; commit clears preedit |
| Korean commit + new composition in one `WM_IME_COMPOSITION`; new preedit not read | WezTerm (inferred) | Handle `GCS_RESULTSTR` and `GCS_COMPSTR` from the same message |
| Double commit (result string *and* `WM_IME_CHAR`) | PuTTY avoids it | Return 1 after handling the result string |
| Korean commit misbehaved when sent as one block | PuTTY | Sends committed text one UTF-16 unit at a time through the keystroke path (root cause not recorded) |
| Keys ignored while a preedit exists | Alacritty | Classic trap: lose the key or misorder it |
| Multi-char commit sent as a bracketed paste | Alacritty | Send commits through the normal keystroke path |
| Ctrl removed from macOS IME forwarding mask (broke Ctrl keys for Japanese users) | WezTerm | Make the IME forwarding mask deliberate |

### 7.3 Preedit drawing and candidate window

Nobody does this fully right:

- Ghostty drops zero-width code points from the preedit (Thai marks and jamo V/T
  vanish), draws each code point unshaped, and doesn't wrap.
- WezTerm keeps the preedit as a plain string with no attributes or caret.
- WT has attribute ranges (double underline for Japanese target clause, styled
  underlines) and inserts the preview insert-style, but doesn't wrap and right-aligns
  overlong compositions.
- **Every reference anchors the candidate window at the terminal cursor cell**, not
  the target clause or caret inside the preedit. WT's `GetTextExt` ignores the range
  it is asked about.

### 7.4 Design for puritty

- Draw the preedit as an **overlay**, never written into the grid, measured with the
  pane's width model and **shaped** like normal text, keeping combining marks.
- Carry **clause attributes and the caret** from the platform API (TSF, Wayland
  `text-input-v3`, XIM/ibus via GTK-like callbacks) and style clauses (target clause
  double underline, as WT does).
- **Wrap** a long preedit onto overlay rows instead of truncating or shifting.
- Report the **target clause's** rectangle for the candidate window. On Windows, use
  `CFS_EXCLUDE` (WezTerm) so the window doesn't cover the preedit.
- Ordering rules:
  - apply commit then preedit from one event, in order;
  - on a non-IME key during composition, let the IME flush first, then handle the key;
    never drop it;
  - never forward keys while composing;
  - send commits through the normal keystroke path, without bracketed paste, never
    splitting surrogate pairs or clusters.
- On Windows: a custom TSF client with transitory context and `TF_TMAE_CONSOLE`
  semantics, as WT does (synthesis §9). An input-scope option so CJK IMEs can start in
  Latin mode (WT `defaultInputScope`).
- Test matrix: fcitx5-hangul, ibus-hangul, Microsoft Korean and Japanese IMEs, Mozc,
  a pinyin IME, macOS 2-Set Korean.

---

## 8. Selection and cursor

- Selection and cursor movement must use cluster boundaries and wide-cell spans.
- **Thai has no spaces between words.** Double-click word selection needs dictionary
  segmentation: ICU's word break iterator with the Thai dictionary, libthai, or the
  `icu.dll` shipped with Windows 10 1703+. Lao, Khmer and Myanmar are the same
  (general knowledge). Every reference falls back to "contiguous run = one word"
  (Alacritty does this explicitly). Do the dictionary break if ICU is available,
  with that fallback.

---

## 9. Rules for puritty

1. **Clusters in cells:** UAX #29 incl. GB6–8, GB9a (except SARA AM, rule 3), GB9c; side-table storage bounded by
   bytes; streaming that re-opens the previous cell (Ghostty/WT).
2. **Width per pane:** legacy (tmux, SSH default) or grapheme (2027) mode; ambiguous
   1 or 2; per-codepoint overrides; tables generated from a pinned UCD with the Hangul
   V/T and Thai mark ranges zero-width.
3. **SARA AM gets its own narrow cell** (tentative) in every mode (break before U+0E33/U+0EB3), so
   กำ is two units for cursor and selection; shape both cells as one run (§2.2).
4. **Shape everything** with HarfBuzz (Linux) or DirectWrite (Windows). Keep a cluster
   in one font; move whole clusters to fallback fonts; shape across cells; don't
   split runs at cursor or colour changes; map back with stored widths.
5. **No clipping; track ink extents per row** so damage-limited redraw (X11 backend,
   partial GPU redraw) repaints overhangs correctly. Optional automatic ascent
   headroom.
6. **Wide glyph fit:** ideograph-width scaling of fallback fonts, centred, Latin
   baseline, shrink only on overflow; compress "narrow" glyphs drawn wide by the font;
   synthesise bold/italic for fallback fonts.
7. **CJK language setting** per profile, defaulting from the OS locale, feeding
   fontconfig `lang`, DirectWrite locale and shaper language; per-script/range font
   overrides.
8. **Bundle or recommend** a CJK and Thai fallback set (Noto Sans CJK / Noto Sans Mono
   CJK, Noto Sans Thai), since no reference bundles one. *Decided 2026-10-30 (Q13,
   `geng-plan.md` §9.3): recommend, not bundle; puritty uses the system's.*
9. **Atlas pages with LRU eviction**, sized for CJK; LRU for server-side X11 glyph sets.
10. **Async font fallback** (WezTerm), invalidating only affected rows, not the whole
    shape cache.
11. **IME as in §7.4**, with a real-IME test matrix.
12. **Thai word selection** via dictionary breaking when available.
13. **Test corpus** (rendered with bundled fonts, compared as images, plus width and
    cursor-position tests under and outside tmux, and `ucs-detect`):
    - Thai: กี้ ปั๊ม น้ำ ญุ ฐุ (stacking, SARA AM, tall consonants, descenders);
    - Hangul: precomposed text, conjoining ᄒᆞᆫ, LV + T sequences;
    - Han unification probes: 直 骨 返 刃 under each language setting;
    - mixed CJK/Latin lines, fullwidth punctuation, ambiguous characters;
    - emoji: ❤️ 🇯🇵 👨‍👩‍👧; Devanagari क्षि (cheap extra coverage);
    - IME scripts for Korean, Japanese and Chinese composition.
14. **Legacy character sets:** a remote character set per profile (UTF-8, EUC-KR,
    CP949), defaulting from the locale for local panes, switchable per pane; a filter
    pair at the backend boundary; ambiguous width 2 in EUC-KR panes (§10).

---

## 10. Legacy encodings: EUC-KR

Requirement: some users work on RHEL8 hosts with `LANG=ko_KR.euckr`. Their
installation is too large to move to UTF-8, so they will stay on EUC-KR for years.
Programs on those hosts read and write EUC-KR bytes, not UTF-8. A UTF-8-only terminal
shows their Korean output as garbage and sends them UTF-8 they can't read.

### 10.1 What the references do

- **Alacritty, Ghostty, WezTerm, Windows Terminal:** UTF-8 only. A search of the
  vendored trees for EUC-KR, CP949 and KS C 5601 finds nothing in any terminal path;
  the only hits are in Ghostty's regex library and WezTerm's font code.
- **PuTTY** has a "Remote character set" setting (`CONF_line_codepage`, `config.c`),
  but it is not a model for multibyte decoding (inferred from these code paths):
  - Incoming bytes go through a 256-entry per-byte table (`unitab_line`,
    `windows/unicode.c`), which can't express a two-byte encoding.
  - On Windows, the only two-byte path is "direct to font": when the line code page
    equals the font's code page and the font is DBCS, bytes are passed to the font
    unconverted (`windows/unicode.c`, around line 596).
  - On Unix there is no DBCS support (`unix/unicode.c:21`, "we don't do DBCS").
- **xterm** handles non-UTF-8 locales by running the shell under `luit`, a filter that
  converts between the locale's encoding and UTF-8 (general knowledge).

So puritty needs its own conversion. PuTTY is prior art for the setting and its UI
only.

### 10.2 Facts about the encoding

General knowledge; check against the WHATWG Encoding Standard and glibc's charmaps.

- **EUC-KR** is ASCII plus the two-byte characters of KS X 1001, both bytes in
  0xA1–0xFE. KS X 1001 has 2,350 precomposed Hangul syllables (of 11,172), 4,888
  Hanja, and symbols, Greek, Cyrillic, box drawing, circled numbers and kana.
- **CP949** (Unified Hangul Code, Windows code page 949) is a superset. It adds the
  other 8,822 syllables, with lead bytes 0x81–0xFE and trail bytes 0x41–0x5A,
  0x61–0x7A and 0x81–0xFE.
  - Text from Korean Windows users is CP949 even when it is labelled EUC-KR, and
    WHATWG decodes the label `euc-kr` as CP949.
  - glibc's `ko_KR.euckr` locale is strict EUC-KR, so programs on RHEL8 can't handle
    the extra syllables (for example 똠).
- **No byte of a two-byte character is below 0x41**, so ESC, other C0 controls and DEL
  never occur inside a character, and escape sequences survive conversion intact.
  CP949 trail bytes do include ASCII letters, though, so the decoder must keep state:
  whether a byte is a letter or a trail byte depends on the byte before it.
- **Bytes 0x80–0x9F are not C1 controls** here. In CP949 they are lead and trail bytes.
- **Width:** in Korean legacy practice every two-byte character takes 2 columns, so
  byte count equals column count, and programs in `ko_KR.euckr` expect that (check
  the `WIDTH` section of glibc's EUC-KR charmap on RHEL8). Unicode gives many of the
  KS X 1001 symbols East Asian Width "Ambiguous" (Greek, Cyrillic, box drawing, ①).
  With ambiguous width 1, tables and box drawing from Korean legacy programs come out
  misaligned.

### 10.3 Design

1. **A "remote character set" setting per profile:** UTF-8 (default), EUC-KR or
   CP949.
   - **Linux local PTY:** default from the process locale (`nl_langinfo(CODESET)`
     after `setlocale(LC_ALL, "")`). This covers the remote X11 case, where puritty
     itself runs on an RHEL8 host and inherits EUC-KR from the login environment.
   - **SSH** (system `ssh` in a PTY on Linux, the embedded client on Windows): the
     terminal can't learn the remote locale, so the setting goes in the host profile.
   - **A per-pane switch at runtime** (a menu action), because one pane can `ssh` from
     a UTF-8 host to an EUC-KR one.
2. **Convert at the backend boundary,** as a pair of filters on the byte stream:
   EUC-KR/CP949 to UTF-8 before the parser, UTF-8 to EUC-KR/CP949 on the way out. The
   parser, its UTF-8 fast path and the grid stay UTF-8 only. UTF-8 panes have no
   filter at all.
   - **The decoder keeps state across reads,** since a lead byte can end one read and
     its trail byte start the next.
   - **A lead byte followed by an invalid trail byte** produces U+FFFD, and the second
     byte is processed again on its own (WHATWG behaviour), so a stray lead byte can't
     swallow an ESC.
   - **The decoder never produces C1 controls.**
   - **Always decode the CP949 superset,** even when the setting is EUC-KR. Accepting
     more is harmless.
   - **The encoder in EUC-KR mode** can't send characters outside KS X 1001 (똠, emoji).
     Replace them with `?` and show that this happened (a status indicator or a
     one-time notice) rather than dropping them silently. CP949 mode can encode every
     syllable.
3. **Outbound writes must say whether they are text or raw bytes.** Keys, IME commits
   and paste are text and go through the encoder. Some output is raw bytes and must
   skip it: legacy mouse reports (modes 1000/1005 without 1006) with coordinates that
   produce bytes ≥ 0x80, and 8-bit Meta. Query replies are ASCII, so it doesn't matter
   for them. Give the backend's write interface two entry points.
4. **Bytes wrapped in ASCII are invisible to the filter,** so their handlers convert
   them using the pane's character set:
   - **OSC 52:** the base64 payload decodes to bytes in the remote encoding. Convert
     after base64-decoding on a write from the remote, and before base64-encoding when
     answering a read.
   - **OSC 7 and OSC 8:** percent-encoded bytes in paths and URLs are in the remote
     encoding (inferred; it depends on the program).
   - **Titles (OSC 0/2)** are ordinary bytes and go through the filter.
5. **Width:** EUC-KR and CP949 panes default to ambiguous width 2 and the legacy width
   model (§2.3).
6. **Selection and copy need nothing extra.** The grid is Unicode, so copied text is
   UTF-8.
7. **X11 hygiene when puritty runs in an EUC-KR locale** (general knowledge):
   - Use `Xutf8LookupString`, not `XmbLookupString`, for XIM commits; the latter
     returns the locale's encoding.
   - Clipboard: request `UTF8_STRING`, and fall back to `COMPOUND_TEXT` for old
     clients.
   - Don't assume file names, the environment or argv are UTF-8.
   - The CJK language default (§5.2) still works: `ko_KR.euckr` gives `ko`. Only the
     codeset differs.
8. **Windows ConPTY panes should not need the filter.** ConPTY emits UTF-8 VT
   whatever the console code page (inferred from T§2.4; check with `chcp 949`).
9. **One portable converter on both platforms,** driven by the WHATWG EUC-KR index, so
   behaviour is identical everywhere. Don't use `MultiByteToWideChar` on Windows and
   iconv on Linux. iconv, ICU and most language ecosystems implement the index. glibc
   iconv's `EUC-KR` is strict; its CP949 converter is `UHC` (general knowledge).

### 10.4 tmux: open, to be tested

It isn't yet known whether the EUC-KR users run tmux; the combination will be tested
on RHEL8 later. tmux stores its grid as UTF-8 and decides from the client's locale
whether the outer terminal handles UTF-8 (general knowledge). To check:

- whether EUC-KR written by a program inside tmux survives tmux's own parsing, in
  normal and `-CC` mode;
- in `-CC` mode, whether converting `%output` bytes in puritty is enough, or whether
  `capture-pane` and reattach show mangled text;
- which tmux version RHEL8 ships. If it is older than 3.2, the flow-control features
  in [`synthesis.md`](synthesis.md) §7.3 are not available.

### 10.5 Tests

- a two-byte character split across two reads;
- a lead byte followed by ESC, and followed by an ASCII letter (valid in CP949 as a
  trail byte, invalid in strict EUC-KR);
- a CP949-only syllable received in EUC-KR mode (decoded) and typed in EUC-KR mode
  (replaced and flagged);
- box-drawing tables and symbol-heavy screens from a Korean legacy program, checked
  for alignment;
- Korean IME commits, paste and OSC 52 round trips in an EUC-KR pane;
- mouse reports beyond column 95 in mode 1000 (raw bytes, not encoded).

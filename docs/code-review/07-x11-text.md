# Review slice 07: the Linux window and text layers

Files: `packages/x11/src/Window.geng`, `packages/x11/src/Ext/puritty_x11.c`,
`puritty_sound.c`, `X11/Reason.geng`, `packages/text/src/Text.geng`,
`packages/text/src/Ext/puritty_text.c`, `puritty_text_rows.c`,
`include/puritty_text.h`, `app/linux/src/{Platform,Notify,Open}.geng`,
`app/build.sh`, `app/release.sh`. Nothing was built or run; every finding is
from reading the code, and "confirmed" means confirmed by tracing the code,
not by a run.

---

### X1 · Pasting puritty's own selection when it is over 256 KB stalls the paste and strips the window's event mask
- Where: packages/x11/src/Ext/puritty_x11.c:1595-1596 (mask set on the requestor), 1632-1642 (`transfer_step` returns early for our own window), 1650 (mask set to 0 at the end)
- Kind: bug
- Severity: high
- Confidence: confirmed (by tracing; not run)
- What: For an INCR transfer `selection_request` does `xcb_change_window_attributes(conn, q->requestor, XCB_CW_EVENT_MASK, &mask)` with `mask = XCB_EVENT_MASK_PROPERTY_CHANGE`. When puritty pastes a selection it owns itself, `q->requestor == window`, so this replaces the window's own `BASE_EVENTS` mask with PropertyChange alone. Then `transfer_step` begins `if (p->window == window) { ...paste side...; return; }`, so the owner side (`for (i...) xfer[i]`, which sends the next piece on a `XCB_PROPERTY_DELETE`) is never reached for our own window.
- Scenario: select more than 262,144 bytes (Shift+Home, drag, Shift+End, as the pointer gate's 320,000-byte case does) and middle-click or Ctrl+Shift+V in the same window. The paste gets the `INCR` header, deletes it, and waits for a first piece that is never written; `pst.active` stays 1 (pastes refused for 10 s), the `xfer` slot and its copy of the text are never freed, and the window no longer receives KeyPress, ButtonPress, Expose, ConfigureNotify or focus events: the terminal is dead to input until something calls `puritty_x11_motion` with a changed value (which rewrites the mask). The paste gate only pastes a small own selection back.
- Fix: when `q->requestor == window`, do not touch the event mask (it already has PropertyChange), and let `transfer_step` fall through to the owner side for `XCB_PROPERTY_DELETE` on our own window when a live `xfer` matches (or short-circuit a self-paste entirely by copying `sel[which].data` into `pbuf`). Never write an event mask of 0 or PropertyChange-only to our own window. Add a paste-gate case: own selection over 256 KB pasted back.
- Fixed: 2026-11-21. `selection_request` leaves its own window's event mask alone when it is the requestor, `transfer_step` lets a delete on its own window through to the owner's side, and the end of a transfer clears the mask only of another client's window. Checked by the pointer gate's new `paste-own-large` (5,000 selected lines pasted back, then a key): before, neither arrived; after, all 320,000 bytes and the key. `docs/phase3-select.md` §15.

### X2 · An INCR transfer whose requestor never finishes holds its slot and its copy of the text for ever; eight of them refuse every large copy
- Where: packages/x11/src/Ext/puritty_x11.c:1509-1515, 1581-1607, 1643-1657
- Kind: bug
- Severity: medium
- Confidence: confirmed
- What: An `xfer` slot is freed only when the requestor deletes the property after the last piece (`if (n == 0) { ... free(xfer[i].data); xfer[i].live = 0; }`). There is no timeout, the requestor's destruction is not watched (only `XCB_EVENT_MASK_PROPERTY_CHANGE` is selected, not StructureNotify), and a new `puritty_x11_select` does not cancel transfers of the old text.
- Scenario: a clipboard manager (or any client) asks for a large selection, sees `INCR`, and gives up or exits, which several do above their size limit. Each time one slot and a full copy of the selection leak. After eight, `slot < 0` and every later request for text over 256 KB is answered `None` ("eight transfers at once already") until puritty is restarted: large copies silently stop working.
- Fix: select StructureNotify as well on the requestor and free the slot on DestroyNotify; give each slot a last-progress time and free it after some seconds without a delete; when all slots are busy, evict the stalest.
- Fixed: 2026-11-23, `docs/phase3-select.md` §26. The requestor's DestroyNotify frees its slots; a slot idle 30 s is freed; with all busy the stalest is given up. Test: pointer `select-large-abandoned`: before, 8 of 9 abandoning requestors saw INCR and xclip then read nothing; now 9 of 9 and all 320,000 bytes.

### X3 · The fallback cache is a fixed 4,096-slot table with no full case: past that, every uncovered cluster costs a fontconfig match on every draw
- Where: packages/text/src/Ext/puritty_text.c:238-275 (`fcache`, `fallback`); same shape at 1219-1240 (`ui_fcache`) and 1269-1279 (`ui_keys`)
- Kind: speed (remote-triggerable)
- Severity: medium
- Confidence: confirmed
- What: `fallback` probes `for (k = 0; k < FCACHE; k++)` for the key or an empty slot. When the table is full it finds neither, `h` stays the first slot, `pt_fallback_file` (an `FcFontMatch` with a charset) runs, and the result overwrites slot `h`. Entries are only added, one per distinct first code point no loaded face covers, and never removed until `pt_refont`.
- Scenario: a program prints more than 4,096 distinct code points that no installed font has (the Private Use Area alone is 6,400; `cat` of a Unicode chart does it). From then on, each such cluster drawn is a 4,096-entry scan plus a synchronous fontconfig match (around a millisecond each) on the UI thread, per cell, per redraw of that cell: a screen of them takes seconds a frame, and scrolling them freezes the window. The hot path is `draw_glyphs` → `fallback`, run for every fallback cluster of every run drawn.
- Fix: make the miss case bounded: grow the table (or use a direct map by code point block), and when no slot is free replace an entry rather than re-query for ever; a negative answer for a whole block/plane-15/16 range would cover the common case.
- Fixed: 2026-11-24, `docs/renderer.md` R22. The terminal's fallback cache and the interface's two tables grow (doubled when half full), so what was asked once is not asked again. Test: `harness/fallbacks.py`, 6,000 distinct plane-15 code points drawn four times: before, 19,392 fontconfig queries; now 6,000.

### X4 · Dead keys and the Compose key produce nothing when no XIM server runs
- Where: packages/x11/src/Ext/puritty_x11.c:658-699 (`key_event`, the text at 683), 946-958
- Kind: bug
- Severity: medium
- Confidence: plausible (no xkb-compose code exists; not run on a layout with dead keys)
- What: A key's text is `xkb_keysym_to_utf8(sym, ...)` of that one keysym. There is no `xkb_compose_table`/`xkb_compose_state`, so `dead_acute` then `e` records an empty text and then `e`. Composition only happens if an input method (ibus, fcitx) is running and takes the keys through XIM. `docs/phase3-input.md` does not mention dead keys or Compose.
- Scenario: a session without an IME (a bare window manager, ETX, `PURITTY_NO_XIM=1`), layout `us(intl)` or any European layout with dead keys, or a configured Compose key: accented letters cannot be typed, where xterm (Xlib's built-in compose) can.
- Fix: keep an `xkb_compose_state` from the locale's table (`xkb_compose_table_new_from_locale`) and feed presses through it when `have_xic` is 0; record the composed UTF-8 as the key's text (or as a Commit) and swallow the intermediate keys.
- Fixed: 2026-11-24, `docs/phase3-input.md` §18. With no input context, each press is fed to libxkbcommon's compose state from the locale's table; a sequence's keys are swallowed and its last key carries the composed text. Test: `harness/compose.py` (dead_acute e, dead_acute space, dead_acute q x, Compose o c): before all four failed; now é, ', x, ©.

### X5 · A primary font FreeType cannot size leaves the cell 0 by 0, and the first resize divides by zero
- Where: packages/text/src/Ext/puritty_text.c:183-191 (`size_face`: `FT_Set_Char_Size` unchecked), 973-986 (`primary_metrics`), 998-1042 (`pt_open`), 1073-1128 (`pt_refont`); packages/x11/src/Ext/puritty_x11.c:717 (`(w - 2 * padx) / pt_cw`), puritty_text.c:584 (`box / pt_cw`)
- Kind: bug
- Severity: medium
- Confidence: plausible (depends on a bitmap-only sfnt font being chosen)
- What: `pt_open`/`pt_refont` accept any face `FT_New_Face` opens. For a non-scalable face (an `.otb` bitmap font such as Terminus, which the FreeType sfnt driver opens and fontconfig reports as `TrueType`, so `puritty_x11_fonts` lists it) `FT_Set_Char_Size` fails unless a strike matches exactly, the size metrics stay 0, and `pt_cw`, `pt_ch` come out 0. Nothing checks them.
- Scenario: the user names such a font; `puritty_x11_open` creates a 0-wide window and the first ConfigureNotify runs `size_in`, an integer division by `pt_cw == 0`: SIGFPE. With `setFont` at run time the same happens in `refit`.
- Fix: in `pt_open`/`pt_refont` treat `pt_cw <= 0 || pt_ch <= 0` as "cannot be used" (fall back as for an unreadable font); for a non-scalable non-color face pick the nearest strike with `FT_Select_Size`, as the color path already does.

### X6 · A stale event time makes a copy fail silently: `SetSelectionOwner` is never verified
- Where: packages/x11/src/Ext/puritty_x11.c:2003-2017 (`puritty_x11_select`), 792 (`last_time`)
- Kind: bug
- Severity: medium
- Confidence: plausible
- What: `sel[which].owned = 1; xcb_set_selection_owner(conn, window, ..., last_time)`. `last_time` is the time of the last key, button, motion or property event the window had. The server ignores a SetSelectionOwner whose time is earlier than the current owner's (ICCCM 2.1 says to follow it with GetSelectionOwner); puritty never checks and no `SelectionLost` is recorded.
- Scenario: the user copies in another program (owner time T), returns to puritty by keyboard (focus events carry no time), and a program in the terminal sets the clipboard with OSC 52 before any key or click: `last_time < T`, the server keeps the other owner, puritty believes it owns the clipboard (the highlight and state say copied), and a paste elsewhere gives the old text.
- Fix: get a fresh server time when the copy is not the direct result of an input event (a zero-length `ChangeProperty` append on the window and its PropertyNotify time; the mask already has PropertyChange), and/or check the owner after setting it (asynchronously: send GetSelectionOwner and read the reply with `xcb_poll_for_reply` as the paste does) and record kind 10 when it is not this window.
- Fixed: 2026-11-24, `docs/phase3-select.md` §27. After claiming a selection the window asks who owns it; if not itself, it claims again at CurrentTime, and if that fails too it records the selection lost. Test: `harness/stalecopy.py`, a click, xclip taking the clipboard, then an OSC 52 copy: before the clipboard read `other`; now `mine`.

### X7 · A keymap change re-fetches the whole keymap synchronously once per XKB event, inside `drain` (so inside `draw`)
- Where: packages/x11/src/Ext/puritty_x11.c:598-617 (`key_setup`), 708-710 (`xkb_event_in`), 1261 (`drain()` in `puritty_x11_draw`)
- Kind: speed
- Severity: medium
- Confidence: confirmed
- What: every `XCB_XKB_NEW_KEYBOARD_NOTIFY` and every `XCB_XKB_MAP_NOTIFY` calls `key_setup`, which repeats `xkb_x11_setup_xkb_extension` (a round trip), `xkb_x11_get_core_keyboard_device_id` (a round trip), `xkb_x11_keymap_new_from_device` (several round trips, a keymap of 100 KB and more, compiled) and `xkb_x11_state_new_from_device`, and re-sends the select-events and per-client-flags requests.
- Scenario: a layout change (`setxkbmap`, a desktop's layout switcher, a keyboard plugged in) sends a burst of MapNotify events, often a dozen or more; each one blocks the UI thread on a full keymap download. Over `ssh -X` that is seconds of frozen window, and it happens inside `puritty_x11_draw`, which the README says never waits on the server. If one fetch in the burst fails, `keymap` is NULL and `key_event` drops every key until the next keymap event.
- Fix: in `xkb_event_in` only set a flag; after the `drain` loop, rebuild once. Do the extension setup once at open. Keep the old keymap when the new one cannot be fetched.
- Fixed: 2026-11-24, `docs/phase3-input.md` §17. XKB is set up once at open; a NewKeyboard/MapNotify only marks the keymap stale and it is fetched once when the next key or pointer event needs it; a failed fetch keeps the old keymap. Test: `harness/keymaps.py`, four `setxkbmap` changes then a key: before, 14 fetches; now 2, and the key is read with the new layout.

### X8 · `pt_zoom` clears 10 MB of tables per loaded face on every zoom step
- Where: packages/text/src/Ext/puritty_text.c:228-230 (`calloc(KEYS, 2)`, `calloc(KEYS * 4, 2)`), 1054-1055
- Kind: efficiency
- Severity: medium
- Confidence: confirmed
- What: each face has `advance` (2^20 int16, 2 MB) and `ink` (2^20 × 4 int16, 8 MB), sized for every glyph index in 16 forms. `calloc` leaves them untouched pages, but `pt_zoom` does `memset(faces[f].advance, 0, KEYS * 2); memset(faces[f].ink, 0, KEYS * 4 * 2)` for every face.
- Scenario: the first Ctrl+plus makes about 10 MB resident per loaded face (up to 31 faces: about 310 MB with CJK, emoji and symbol fallbacks loaded) and every zoom step rewrites all of it; holding Ctrl and scrolling zooms many steps in a row.
- Fix: the memsets are not needed: `reset_glyphs` clears the `uploaded` bits, and `advance[k]`/`ink[k]` are always written by `upload` before `place` reads them. Drop them; consider a table keyed by glyph actually uploaded (a hash, as `ui_keys`) so a face costs kilobytes, not 10 MB of address space.

### X9 · `isMaximized` makes four synchronous round trips, and `Main` calls it on every `Resized`
- Where: packages/x11/src/Ext/puritty_x11.c:1424-1426 (three `atom()` calls each time), 1442-1443 (`xcb_get_property_reply`); app/src/Main.geng:6792
- Kind: speed
- Severity: medium
- Confidence: confirmed
- What: `puritty_x11_maximized` interns `_NET_WM_STATE`, `_NET_WM_STATE_MAXIMIZED_VERT` and `_HORZ` with a blocking reply each, on every call, then reads the property with a fourth blocking reply. `Main`'s `Window.Resized` branch calls `Window.isMaximized` first.
- Scenario: dragging the window's edge sends a Resized for each new size in cells; each costs four network round trips on the UI thread before the relayout. Over `ssh -X` (the case the README is about) a resize drag stutters by 4 × RTT a step.
- Fix: intern the three atoms once at open (with the other atoms, pipelined as `selection_atoms` does). Track the state from PropertyNotify on `_NET_WM_STATE` (the mask already has PropertyChange) and answer from that, or read it with a polled reply.
- Fixed: 2026-11-24, `docs/window-state.md` WP10. The three `_NET_WM_STATE` atoms are interned at open with the selection's atoms; `isMaximized` reads only the property (kept read when asked, since an answer cached from PropertyNotify could be older than the ConfigureNotify). Test: `harness/maximized.py`, a request-counting proxy, six resizes: before, 18 InternAtom and 6 GetProperty; now 0 and 6.

### X10 · Focus events from a window manager's key grabs are reported as focus changes
- Where: packages/x11/src/Ext/puritty_x11.c:1011-1023
- Kind: bug
- Severity: medium
- Confidence: plausible (not run under i3)
- What: FocusIn/FocusOut are filtered only by `f->detail != XCB_NOTIFY_DETAIL_POINTER`; `f->mode` is not looked at. A passive key grab activating (any i3/sway-on-X/awesome key binding, an Alt-Tab switcher, a volume key) sends FocusOut with mode NotifyGrab and FocusIn with NotifyUngrab to the focused window though the focus never left.
- Scenario: under such a window manager each hotkey makes puritty record focus out then in: programs that asked for focus reports (mode 1004: vim, tmux) get `CSI O`/`CSI I` pairs, the cursor flickers hollow, `xcb_xim_unset_ic_focus` is sent (an IME may drop its preedit), `held` is cleared so a key still held is reported as a new press, and `repaint_all` copies the whole window twice.
- Fix: ignore events whose `mode` is `XCB_NOTIFY_MODE_GRAB` or `XCB_NOTIFY_MODE_UNGRAB` (and `detail` Inferior), as GTK and xterm do.
- Fixed: 2026-11-24, `docs/phase3-input.md` §19. Focus events of mode NotifyGrab or NotifyUngrab, and of detail NotifyInferior, are let go. Test: `harness/grabfocus.py`, another client grabbing the keyboard three times: before, `CSI O CSI I` three times to a program with mode 1004; now nothing, and a real focus move still reported.

### X11 · After the sound server goes away, every sound is lost and still reported as played
- Where: packages/x11/src/Ext/puritty_sound.c:103-118 (the write loop), 124-144
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: when `pa_write` fails the loop breaks, but the dead `stream` is kept and `broken` is not set; nothing reopens it. `puritty_sound_play` keeps answering `taken = !broken` = 1. Also, the first call answers 1 before the thread knows whether there is any audio at all.
- Scenario: PipeWire/PulseAudio is restarted (a session's `systemctl --user restart pipewire`, a suspended ETX audio forward) while puritty runs: no key sound or bell is heard again until puritty restarts, and the log line says "played" (`Main.geng:2138`).
- Fix: on a failed write free the stream (`pa_simple_free`) and open a new one on the next request (with a short back-off); set `broken` only when opening fails repeatedly, so the caller's "not played" is true.

### X12 · The paste's 10 s rule measures from the start, not from the last progress, and the abandoned paste shares the property and leaks its reply
- Where: packages/x11/src/Ext/puritty_x11.c:1791, 1814, 1970 (`ns() - pst.started > 10e9`), 1704-1710, 1735-1745, 1720-1733
- Kind: bug
- Severity: low
- Confidence: confirmed (the mixing of data is plausible)
- What: the comment says a new paste is made "unless the first has waited 10 s for an owner that never answered", but the test is elapsed time since the paste began, whatever has arrived since. Resetting sets `pst.waiting = 0` without `xcb_discard_reply`, so an outstanding GetProperty reply (up to the whole property, megabytes) stays in xcb's queue for ever. Both pastes use the one property `PURITTY_PASTE`, and `paste_notify` accepts any SelectionNotify for the window without comparing `n->selection`/`n->target` to what was asked.
- Scenario: a large INCR paste over `ssh -X` that takes more than 10 s (the document measures 1.1 s for 2.6 MB on a LAN); the user pastes again or drops a file. The new request deletes the property (which the old owner reads as "send the next piece"), and old pieces can be read as the new paste's text. Also, a hostile or broken owner can stream INCR pieces without end: nothing here bounds a paste's size.
- Fix: keep a last-progress time, updated in `paste_poll`; on abandon, `xcb_discard_reply` the cookie; use a property name per paste (a counter in the atom name, or two alternating atoms) and check the notify's selection and target; give a paste a size limit.

### X13 · Font names go to `FcNameParse` unescaped, and its NULL is not checked
- Where: packages/x11/src/Ext/puritty_x11.c:185-206 (`pt_font_file`), 215-236 (`family_used`), 284-312 (`puritty_x11_fonts` returns raw families)
- Kind: bug
- Severity: low
- Confidence: plausible (fontconfig's parse behaviour from its documentation, not run)
- What: `pt_font_file` builds `"<name>:bold"` and parses it as a fontconfig pattern; in that syntax `-` starts a size list and `:` a property, `,` separates families. `app/linux/src/Platform.geng:218` escapes `sans\-serif` for this reason, but the families `puritty_x11_fonts` lists for the settings window are given back as they are and passed in unescaped (also by `ui_named` for the list's own preview). And `FcNameParse` returns NULL for a pattern it cannot parse; `family_used` checks, `pt_font_file` does not and passes NULL to `FcConfigSubstitute`.
- Scenario: a family with a hyphen ("IBM 3270 Semi-Narrow", "Semi-Condensed") chosen from the list is looked up as family "IBM 3270 Semi" and another font is shown; a hand-written `font = "Foo:weight=nonsense"` can crash at start.
- Fix: build the pattern with `FcPatternCreate` + `FcPatternAddString(FC_FAMILY, name)` and `FcPatternAddInteger(FC_WEIGHT/FC_SLANT)` for the variant (or escape `-`, `:`, `,`, `\` when the name is a family from the list), and treat a NULL pattern as "no such font".

### X14 · The fallback cache is keyed by a cluster's first code point but answers for the whole cluster
- Where: packages/text/src/Ext/puritty_text.c:241-276
- Kind: bug
- Severity: low
- Confidence: plausible
- What: the key is the first non-ignorable code point (`key = cps[i]`), the value the face found (or -1) for all of the cluster's code points. A later cluster with the same base and other marks gets the cached answer without `covers` being asked of it.
- Scenario: `e` + a combining mark no font has is drawn: -1 is cached under `e`. Later `e` + a mark that an installed, not yet loaded, fallback font does have (the primary lacks it) hits the cache, gets -1, and is drawn as its first code point alone (`cl[i].n = 1`), the mark dropped, until the font is changed. The reverse (a cached face that lacks the new mark) draws `.notdef`.
- Fix: on a cache hit with a face, check `covers` and fall through to a query when it fails; key negative answers by the code point that is actually missing, or by a hash of the cluster.

### X15 · `ui_glyph`'s key loses the face's top bit, and reads a 1-bit bitmap past its end
- Where: packages/text/src/Ext/puritty_text.c:1270 (`(uint32_t) f << 26`), 1141 (`UI_FACES 128`), 1285-1289
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: (1) `f` goes up to 127 but only 6 bits fit above bit 26, so faces `f` and `f + 64` share keys at the same size and glyph index. (2) The loop reads `uint8_t v = b->buffer[r * pitch + c]` for every `c < width` before testing `pixel_mode`; for `FT_PIXEL_MODE_MONO` the row is `pitch = ceil(width / 8)` bytes, so on the last row this reads up to `width - pitch` bytes past the bitmap.
- Scenario: (1) the settings window's font list draws each family in its own face (`ui_named`); on a machine with more than 64 monospace families plus fallbacks, a name is drawn with another font's glyphs of the same index. (2) an interface or fallback font with embedded 1-bit strikes at the UI size (the code's own example, AR PL UMing) makes a heap over-read on each new glyph.
- Fix: widen the key (a 64-bit key, or hash the three fields separately); read `v` only in the gray branch.

### X16 · `WM_CLASS` is sent with a length one past the string
- Where: packages/x11/src/Ext/puritty_x11.c:1219
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `xcb_change_property(..., XCB_ATOM_WM_CLASS, XCB_ATOM_STRING, 8, 18, "puritty\0Puritty\0")`: the literal is 16 characters and the compiler's terminator makes 17 bytes; 18 are sent.
- Scenario: a one-byte read past the literal on every open, and a WM_CLASS with two bytes after the class's terminator, one of them whatever follows in `.rodata`.
- Fix: length 16 (`sizeof "puritty\0Puritty" `).

### X17 · The X screen is always the first, whatever `DISPLAY` names
- Where: packages/x11/src/Ext/puritty_x11.c:1169-1174, 2102
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `xcb_connect(NULL, &screen_number)` gives the screen `DISPLAY` asks for, but `screen = xcb_setup_roots_iterator(xcb_get_setup(conn)).data` takes screen 0; `xim_setup(screen_number)` then uses the other number.
- Scenario: `DISPLAY=:0.1` on a multi-screen (Zaphod) server: the window opens on screen 0 with the IME looked for on screen 1.
- Fix: step the roots iterator `screen_number` times (as `xcb_aux_get_screen`).

### X18 · Draw-path round trips the README's sentence does not allow for
- Where: packages/x11/src/Ext/puritty_x11.c:1261 (`drain()` in `puritty_x11_draw`) → 1937-1949 (XdndEnter: `xcb_get_property_reply`, `xcb_translate_coordinates_reply`), 708-710 (keymap, above); 437 (`xcb_get_maximum_request_length`, a blocking BIG-REQUESTS reply the first time an image or color glyph is uploaded); README.md:38
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: "It never waits on a reply from the server while drawing" holds for the frame's own requests, but `puritty_x11_draw` also drains events, and three event handlers there block on replies; the first picture upload blocks once.
- Scenario: a drag entering the window, or a keymap change, during output over `ssh -X` stalls a frame by one to several round trips.
- Fix: call `xcb_prefetch_maximum_request_length` at open; read the XDND type list and the window's origin with polled replies (the mechanism `paste_poll` already has), or track the origin from ConfigureNotify; keymap as in the finding above. Or narrow the README's sentence to what is measured.

### X19 · `setenv("XCURSOR_PATH", ...)` changes the environment the terminal's programs may inherit
- Where: packages/x11/src/Ext/puritty_x11.c:1136
- Kind: bug
- Severity: low
- Confidence: plausible (whether the shell is spawned from the process's `environ` or from a dictionary read earlier was not traced; that is core's `Process.spawn`)
- What: to help Nix's xcb-util-cursor, the process's own environment gets `XCURSOR_PATH=~/.local/share/icons:~/.icons:/usr/share/icons:/usr/share/pixmaps` when it was unset.
- Scenario: if children inherit `environ`, every GUI program started from a puritty shell gets this fixed path in place of libXcursor's default (which also searches `XDG_DATA_DIRS`, `/usr/local/share/icons`, Nix and Flatpak paths), and can lose its cursor theme.
- Fix: set it only around `xcb_cursor_context_new`/`load_cursor` and `unsetenv` after, or make sure the spawn's environment is taken before `open`.

### X20 · The event buffer drops records silently when it is full
- Where: packages/x11/src/Ext/puritty_x11.c:568-575 (`put`), 794-800
- Kind: design
- Severity: low
- Confidence: confirmed
- What: `if (evlen + n > (int) sizeof evbuf) return;`. A dropped record may be a key release, a `Resized` (the C's `win_cols` is updated, Geng is never told, and the two disagree until the next resize), or a paste's last record 11 (the paste then never ends for Geng).
- Scenario: 64 KB between two takes is far, but the diagnostic records make it nearer: every key adds a 13 line (two with an IME, plus one for every XIM message through `xim_log`, each up to 160 bytes), whether or not the diagnostic log is on.
- Fix: grow the buffer instead of dropping (it is taken whole at each `take`), or at least never drop kinds 2, 4, 10, 11, 14, 17; make the diagnostic lines conditional on a flag Geng sets when the log is on.

### X21 · `kstate` and the XKB StateNotify subscription are dead
- Where: packages/x11/src/Ext/puritty_x11.c:594, 605-608, 703-707
- Kind: dead-code
- Severity: low
- Confidence: confirmed
- What: `kstate` is created and updated on every `XCB_XKB_STATE_NOTIFY` and read nowhere: keys are read from each event's own state (V46). Selecting `XCB_XKB_EVENT_TYPE_STATE_NOTIFY` makes the server send an event, and wake the loop, on every modifier press and release and every group change.
- Fix: drop `kstate`, the `xkb_x11_state_new_from_device` round trip and the StateNotify selection.

### X22 · At most 256 image placements a frame are drawn; the rest are dropped without a trace
- Where: packages/text/src/Ext/puritty_text.c:1565-1567, 1611-1620
- Kind: bug
- Severity: low
- Confidence: plausible (whether `Vt.View` can send more was not traced)
- What: `if (nplaces < MAX_PLACES) places[nplaces++] = p;` and the rows are still marked as drawn. `docs/images.md` gives no such limit.
- Scenario: a frame with more than 256 placements (a thumbnail grid, or many small Kitty placements in view after a resize redraws everything): the ones past 256 are not drawn, and since the view believes they were, they stay missing until their cells are redrawn for another reason.
- Fix: grow the array, or draw placements in a second walk of the list as the runs are.

### X23 · A picture's source offset is cut to 16 bits
- Where: packages/x11/src/Ext/puritty_x11.c:476-482 (`(int16_t) (sy + y0 - dy)`, `(int16_t) (oy + y0 - dy)`)
- Kind: bug
- Severity: low
- Confidence: plausible
- What: RENDER's Composite takes the source origin as INT16, and the code casts. An image may be 65,535 pixels a side and its placement may start above the screen's top (`image_place` reads a signed row), so `y0 - dy` is how far the visible part is into the picture.
- Scenario: an image taller than 32,767 px (a long screenshot shown at its own size) scrolled so that its visible part starts past that: the offset wraps negative and the wrong part, or nothing, is drawn.
- Fix: put the offset into the picture's transform (a translation) and composite from 0, 0; or reject/clip offsets that do not fit.

### X24 · A glyph centered once keeps that centering for every later box width
- Where: packages/text/src/Ext/puritty_text.c:308-314 (the key has one bit for `shift`), 356-357 (`left = bitmap_left + shift`), 575-576
- Kind: bug
- Severity: low
- Confidence: plausible
- What: `upload`'s key records only that a glyph was shifted, not by how much; the shift (`pad`, half of `box - advance`) is baked into the uploaded glyph's bearing the first time. `place` is later called with `x - pad` for the current `pad`.
- Scenario: the same fallback glyph drawn alone in a one-cell box and later in a wider one (a cluster the shaper merged over more cells, or a code point whose width differs between two tabs' settings) is drawn off by the difference of the two pads until the next glyph reset.
- Fix: key the shifted form by the pad (a small table of pads per glyph), or do not bake the shift and start a new element instead when the cached pad differs.

### X25 · `upload` does not check `FT_Load_Glyph`/`FT_Render_Glyph`, and allocation results are unchecked throughout
- Where: packages/text/src/Ext/puritty_text.c:329-337, 354-355, 228-230, 419, 459, 471, 799-803, 1253, 1284, 1385; packages/x11/src/Ext/puritty_x11.c:188, 304-305, 320, 1053, 1543, 1574, 1689, 2007, 2110, 2116
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: after a failed load the slot's bitmap is whatever FreeType left (empty in current versions), and the glyph is recorded as uploaded, so it is never tried again. `calloc`/`malloc`/`realloc` results are used at once; `paste_add` does `pbuf = realloc(pbuf, pcap)` with a size a selection's owner chooses and then `memcpy`s, and `selection_request` copies the whole selection for every request (also for one that fits a piece and needs no copy).
- Scenario: an out-of-memory during a very large paste or image is a NULL write, not an error; in practice Linux overcommits, so this is rare. The uncopied small-request path is a needless copy of up to 256 KB per request.
- Fix: check the FreeType calls and do not set the `uploaded` bit on failure; route allocations through one checked helper (`geng_crash` on NULL, as `puritty_text_rows.c` does); send small selections straight from `sel[which].data`.

### X26 · `draw_run` can hand `draw_glyphs` a run longer than the bytes that remain
- Where: packages/text/src/Ext/puritty_text.c:939-957, 815-834
- Kind: bug
- Severity: low
- Confidence: confirmed (needs a malformed list; `Vt.View` does not make one)
- What: the style loop stops at `q + 3 <= end`, and only `q > end` returns early. A run whose count `n` is larger than its cells present ends the loop with `q <= end`; the passes then use `styles[i]` left from an earlier run and `draw_glyphs(y, x, n, cell)` reads `n` cells from `cell` without an end pointer.
- Scenario: a list cut short (a future encoder bug, a truncated frame): an out-of-bounds read of the list's buffer instead of a stopped frame.
- Fix: return `end` when the loop ends with `i < n`; pass `end` to `draw_glyphs`.

### X27 · The build turns Nix's hardening off and names one machine's paths
- Where: app/build.sh:9, 19 (`NIX_HARDENING_ENABLE=`), 15-16 (`|| true`); app/release.sh
- Kind: design
- Severity: low
- Confidence: confirmed
- What: `NIX_HARDENING_ENABLE=` (empty) removes every flag Nix's compiler wrapper adds (`-D_FORTIFY_SOURCE`, stack protector, PIE, RELRO/BIND_NOW, `-fstack-clash-protection`), and nothing in `docs/` says why or adds them back; this is a program that parses bytes from remote hosts in C (the renderer, the X event code, the vendored PuTTY crypto). `R=/home/gram/prj/geng-lang` is absolute, so the script runs on one machine. `pkg-config ... || true` makes a missing libpulse silent: the build then has no `PURITTY_PULSE_SIMPLE` and, with Nix's loader, no sound and no message. `release.sh` adds only the profile.
- Fix: say in the script why hardening is off, or pass at least `-fstack-protector-strong -D_FORTIFY_SOURCE=2 -fPIE -Wl,-z,relro,-z,now` through `GENG_CFLAGS` for release builds; take `R` from the environment with the current value as default; print a line when libpulse-simple is not found.

### X28 · A notification's body is given to `notify-send` as markup
- Where: app/linux/src/Notify.geng:23
- Kind: security
- Severity: low
- Confidence: plausible
- What: `[ "--app-name=puritty", "--", n.title, n.body ]`: argument injection is closed by `--` and there is no shell, but the Desktop Notifications spec lets a server read the body as markup (`<b>`, `<a href>`, `<img src>`), and GNOME Shell, KDE and dunst do. The title and body are a remote program's text (OSC 9/777/99).
- Scenario: a program on a remote host posts a notification whose body holds a link or an image reference the notification daemon renders, or simply text that breaks the markup so the body shows empty.
- Fix: escape `&`, `<` and `>` in the body before it is passed (the spec's own rule for plain text).

### X29 · Comments that no longer say what the code does
- Where: packages/text/src/Ext/puritty_text.c:24-26; packages/x11/src/Ext/puritty_x11.c:23-63, 1109-1116, 1355-1359, 1411-1417, 1677; packages/text/src/Ext/include/puritty_text.h:104-106
- Kind: inaccuracy
- Severity: low
- Confidence: confirmed
- What: (1) puritty_text.c's header says "a fallback face draws them as its regular (synthesizing them is ... step 5's)", but `synth_for` synthesizes bold and italic for any face that lacks them, and `docs/renderer.md:56` says so. (2) puritty_x11.c's list of records omits kinds 12 and 13, which `Window.decode` reads and 13 is the most frequent record there is. (3) Three doc comments sit above the wrong function: `puritty_x11_open`'s above `font_cursor`, `puritty_x11_zoom`'s above `refit`, the sound's above `puritty_x11_maximized`. (4) "unless the first has waited 10 s for an owner that never answered" (see the paste finding). (5) `pt_font_file`'s contract says "malloc'd, or NULL", and `pt_refont` "-1 ... when the platform has no such font", but fontconfig's `FcFontMatch` always answers some font, so on Linux neither happens for a name that does not exist (ST35's `family_used` is what tells the user).
- Fix: correct the comments; move the three to their functions.

## Looked at and found sound

- `Window.geng`'s `decode`/`advance`: every read is bounded by the buffer, lengths are clamped, a short buffer ends the events; the record sizes match what the C writes for kinds 1-17 (key 16 + n, pointer 17, drag 13, preedit 9 + n + 2 + nf).
- The events/take split (phase2-window.md §12): `puritty_x11_events` drains and answers on `evlen`, so records made by `draw`'s own `drain` are seen by the next race; the `xwait` cancel clears its io handle.
- Paste read path: no blocking reply (`xcb_poll_for_reply`), the INCR pending/waiting ordering against PropertyNotify, the Latin-1 conversion, TARGETS probing with length and type checks, properties from other clients read with `len / 4` bounded by the reply.
- Owner side for other clients: PropertyChange selected before the INCR header is written, each transfer has its own copy (a new `select` cannot free it under a transfer), `latin1` cannot overrun (`n + 1` bytes out for `n` in).
- XDND: messages from a window other than the current source are ignored, status always answered, Finished sent once, a drop during a paste refused; the type list is length-checked.
- Glyph requests: `pt_glyphs_draw`'s buffer bound (60,000 + 12 < 65,536), 254 glyphs an element, the clip set and removed around each request; `solid_of`'s cache frees what it replaces; the glyph set and color pictures are bounded by `glyph_cap` and freed on reset; `pt_target` frees the old pixmap and picture on resize; `pt_picture_add` frees its GC and pixmap. No per-frame or per-glyph X resource leak found.
- Style tables (65,536 ids plus selected copies fit 131,072), `cps[1024 * 64]` against 63 code points a cell, `box_uploaded[512]` and `quads[]` indexes, `placed`/`clips` caps, `image_define`'s size check against the list before any allocation.
- Expose and scroll: an expose copies only the exposed part from the pixmap, graphics exposures are off, margins are the window's background pixel; scroll is one CopyArea in the pixmap (whether the view redraws the rows a scroll vacates is `Vt.View`'s, not traced here).
- `screen_dpi` (bounds, frees, the forced value), `write_shot` (debug only; assumes 32 bits a pixel), `puritty_x11_raise` (own connection, freed).
- XIM: text length caps before records, the IME's text freed, focus set and unset on focus changes, keys go direct again after `disconnected`.
- `puritty_sound.c`: the lock discipline between the loop and the player thread, bells dropped while one plays, the UI never blocks on audio (connect and writes are on the thread), the WAV chunk walk stays in bounds, a missing library plays nothing.
- `Open.geng`: no shell, the URI is one argv element, and `Links.openable` admits only `http(s)://`, `mailto:` and local `file://`, so it cannot begin with `-`. `Notify.geng`: `--` before the title.
- `Platform.geng`: directory and locale derivations (empty variables treated as unset, `zh_TW` → `zh-tw`, codeset parsing); `Text.geng` and `puritty_text_rows.c` (checked malloc, lengths from the bytes).

## Not covered

- `puritty_icon.h` (generated, skipped as told).
- xcb-imdkit and its patches (`packages/x11/patches`, `build-imdkit.sh` beyond a glance), and what an IME that hangs does to forwarded keys.
- Whether core's `Process.spawn` reaps children, closes inherited descriptors (the X socket) and which environment it passes: core's, not reviewed.
- The Windows platform's implementation of the `pt_*` calls, and `Vt.View`'s side of the display list (run lengths, scroll records, placement counts).
- `docs/cjk-and-thai.md` and `docs/rhel8-etx.md` were only searched, not checked claim by claim against the shaping code; box-drawing geometry (`draw_lines_box`) was read for bounds, not for the look of each character.
- Nothing was run: no finding here was reproduced.

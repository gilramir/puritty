# Upstream reports

Defects found in the terminals puritty is held to, and in the libraries it
uses (PuTTY's cryptography, which ssh-crypto carries), written up so that what was found and why puritty differs is kept. **Ghostty's are not filed**
(Gilbert, 2026-10-30): its reports go through an "Issue Triage" discussion
under an AI policy that makes filing more trouble than it is worth, so a
report here is for our own knowledge. Each still says where the code is,
how to reproduce it and what the fix is. **PuTTY's are not filed
either** (Gilbert, 2026-11-11): its reporting process makes filing more
trouble than it is worth.

**The oracle carries the fixes** (`vt-core.md` §VC17, V12): the vendored
Ghostty is built with `harness/oracle/patches/` applied, one patch a report,
so the core is held to Ghostty without its bugs and the replay cases that
show one pass on both sides. DEL is the one not patched; the differential
fuzzer leaves out an input with one. One patch is not a bug's:
`0013-the-dec-status-reports-the-core-answers.patch` gives the oracle the
DEC status reports the core answers and Ghostty does not make
(`vt-core.md` §VC71), fixed strings, so the fuzzer compares the rest.

| report | repository | found | filed |
|---|---|---|---|
| [`send-keys -K` drops escape-sequence keys, and Enter under extended keys](tmux-send-keys-K-drops-keys.md) | `tmux/tmux` | 2026-11-12, `tmux.md` TM50 | not filed (Gilbert decides) |
| [`rotate-window` moves the panes and tells control clients no layout change](tmux-rotate-window-tells-no-layout.md) | `tmux/tmux` | 2026-11-15, `tmux-checks.md` TK12 | not filed (Gilbert decides) |
| [A short Ed25519 key or an even RSA modulus in a public key blob fails an assertion](putty-asserts-on-malformed-host-keys.md) | PuTTY | 2026-11-10, `ssh-client.md` SC14 | not to be filed |
| [Signature verification accepts an unreduced RSA signature and an Ed25519 point with x = 0 and the sign bit set](putty-verify-accepts-malleable-signatures.md) | PuTTY | 2026-11-10, `ssh-client.md` SC13 | not to be filed |
| [A `#` color's digits are scaled, where XParseColor takes them as the high bits](ghostty-hash-colors-scaled.md) | `ghostty-org/ghostty` | 2026-11-16, `vt-core.md` §VC71 | not to be filed |
| [Reflow joins a line to the next when the line's last row is blank](ghostty-reflow-joins-a-blank-continuation.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC14 | not to be filed |
| [DEL in the ground state is printed as a character](ghostty-del-is-printed.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC16 | not to be filed |
| [Widening without a reflow keeps a row's wrapped flag or not by its page's capacity](ghostty-widen-keeps-wrap-by-capacity.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A reflow counts the rows it joins by a flag DL and DECALN leave behind](ghostty-reflow-miscounts-continuations.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A reflow leaves the cursor on the spacer head before a wide character](ghostty-reflow-pin-on-spacer-head.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A wide character that wraps over another clears its own spacer head](ghostty-wide-clears-its-own-spacer-head.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A reflow wraps onto an empty row for a spacer head it does not write](ghostty-reflow-spacer-head-wraps.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC18 | not to be filed |
| [ED 22 gives the alternate screen a scrollback](ghostty-scroll-clear-gives-the-alt-screen-history.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC19 | not to be filed |
| [A wide character that wraps into the margins keeps the screen's edge as its limit](ghostty-print-right-margin-before-wrap.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC20 | not to be filed |
| [DCH after DL leaves a spacer head that DCH without it clears](ghostty-split-boundary-reads-continuation.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC20 | not to be filed |
| [A reflow keeps a styled blank on the first row, under the viewport pin](ghostty-reflow-pin-copies-a-blank.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC21 | not to be filed |
| [A full reset undoes libghostty-vt's choice not to clear prompts on resize](ghostty-full-reset-forgets-prompt-redraw.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC22 | not to be filed |
| [Keys get stuck when two XIM_SET_IC_VALUES are sent back to back](xcb-imdkit-queue-stalls-after-reply.md) | `fcitx/xcb-imdkit` | 2026-11-14, `diagnostics.md` DG8 | [filed as #21](https://github.com/fcitx/xcb-imdkit/issues/21) (2026-11-14); puritty carries the patch (`xcb-imdkit-0004`) |
| [Each key forwarded by the XIM client waits for several X round trips](xcb-imdkit-client-round-trips.md) (program: `xcb-imdkit-client-round-trips/xim_roundtrips.c`) | `fcitx/xcb-imdkit` | 2026-11-02, `phase3-input.md` §3.3; measured again 2026-11-14 | not filed: rewritten for Gilbert to post after #21; puritty carries the patch (V44) |

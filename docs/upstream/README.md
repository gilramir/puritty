# Upstream reports

Defects found in the terminals visiterm is held to, written up so that what
was found and why the core differs is kept. **Ghostty's are not filed**
(Gilbert, 2026-10-30): its reports go through an "Issue Triage" discussion
under an AI policy that makes filing more trouble than it is worth, so a
report here is for our own knowledge. Each still says where the code is,
how to reproduce it and what the fix is.

**The oracle carries the fixes** (`vt-core.md` §VC17, V12): the vendored
Ghostty is built with `harness/oracle/patches/` applied, one patch a report,
so the core is held to Ghostty without its bugs and the replay cases that
show one pass on both sides. DEL is the one not patched; the differential
fuzzer leaves out an input with one.

| report | repository | found | filed |
|---|---|---|---|
| [Reflow joins a line to the next when the line's last row is blank](ghostty-reflow-joins-a-blank-continuation.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC14 | not to be filed |
| [DEL in the ground state is printed as a character](ghostty-del-is-printed.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC16 | not to be filed |
| [Widening without a reflow keeps a row's wrapped flag or not by its page's capacity](ghostty-widen-keeps-wrap-by-capacity.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A reflow counts the rows it joins by a flag DL and DECALN leave behind](ghostty-reflow-miscounts-continuations.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A reflow leaves the cursor on the spacer head before a wide character](ghostty-reflow-pin-on-spacer-head.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A wide character that wraps over another clears its own spacer head](ghostty-wide-clears-its-own-spacer-head.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC17 | not to be filed |
| [A reflow wraps onto an empty row for a spacer head it does not write](ghostty-reflow-spacer-head-wraps.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC18 | not to be filed |
| [ED 22 gives the alternate screen a scrollback](ghostty-scroll-clear-gives-the-alt-screen-history.md) | `ghostty-org/ghostty` | 2026-10-30, `vt-core.md` §VC19 | not to be filed |

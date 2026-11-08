# Test coverage of the libraries the synthesis mentions

[`synthesis.md`](synthesis.md) suggests adopting, benchmarking against, or porting
from several libraries inside the reference terminals. This doc records how well
each one is tested. The numbers are for information only. They don't rule any
library out.

Sources: the vendored trees at the same commits as the per-terminal docs. `vte`
isn't vendored, so it was read from `github.com/alacritty/vte` @ `abeae76`
(2026-02-28). Paths are relative to each `vendor/<name>/` directory.

## Method

- **Tests** are test functions in the library's own tree. For Rust that means
  `#[test]`, `#[tokio::test]` and `#[rstest]`. For Zig it means `test` blocks. For
  Windows Terminal it means TAEF `TEST_METHOD`s.
- **Code lines** count the non-test source files. Rust and Zig tests usually sit
  inline in the source files, so for those languages this number includes the tests.
- **Tests per 1k lines** is a rough measure. Some tests are one assertion and some
  cover a whole scenario. It doesn't count tests run by data files, by esctest, or
  by fuzzing. Only gaps of several times are meaningful.

## Results

| Library (app) | Path | Code lines | Tests | Tests per 1k lines | Other testing |
|---|---|---|---|---|---|
| **libghostty-vt** terminal core (Ghostty) | `src/terminal` | 184k | 3,327 | 18 | AFL fuzzing of parser, OSC and stream (`test/fuzz-libghostty`), run in CI. esctest2 runs headless in CI (`test/esctest`), but its failures don't fail the build. The C API (`src/terminal/c`) has 470 of the tests |
| ↳ input: key, mouse, paste encoding | `src/input` | 13k | 266 | 20 | |
| ↳ tmux control-mode layer | `src/terminal/tmux` | 4.7k | 121 | 26 | Didn't catch the octal-unescape bug (G§8.7) |
| **alacritty_terminal** (Alacritty) | `alacritty_terminal` | 11.7k | 136 unit + 47 replay | 16 | `tests/ref.rs` replays recorded real sessions and compares the resulting grid |
| **vte** (Alacritty's parser) | separate repo | 4.1k | 57 | 14 | |
| **TerminalCore** (Windows Terminal) | `src/cascadia/TerminalCore` | 4.1k | 53 | 13 | |
| WT VT parser | `src/terminal/parser` | 8.5k | 98 | 12 | Fuzzing pipeline (`build/pipelines/fuzz.yml`) |
| WT VT adapter + input | `src/terminal/adapter`, `src/terminal/input` | 13.7k | 74 | 5 | About 515 more conhost tests (`src/host/ut_host`, 220 of them in `ScreenBufferTests`) drive the adapter and the text buffer |
| WT text buffer | `src/buffer/out` | 9.9k | 14 | 1.4 | Also covered by conhost's `TextBufferTests` (70) |
| WT Atlas renderer | `src/renderer/atlas` | 10k | 0 | 0 | |
| **vtparse** (WezTerm) | `vtparse` | 1.6k | 23 | 14 | |
| **wezterm-escape-parser** | `wezterm-escape-parser` | 10.9k | 59 | 5 | |
| **termwiz** | `termwiz` | 10.4k | 53 | 5 | |
| **wezterm-term** | `term` | 10.2k | 58 | 6 | |
| **wezterm-ssh** | `wezterm-ssh` | 6.1k | 11 unit + 39 end-to-end | 8 | End-to-end tests need a local `sshd` and are skipped if there isn't one. They are mostly SFTP. The `~/.ssh/config` parser has the 11 unit tests |
| wezterm mux | `mux` | 11.8k | 4 | 0.3 | |
| wezterm pty | `pty` | 2.8k | 3 | 1 | |

All four projects run their unit tests in CI: Alacritty with `cargo test`, WezTerm
with `cargo nextest`, Ghostty with its `test` and `test-lib-vt` jobs, and Windows
Terminal with its `ci.yml` pipeline.

## What it means

- **Ghostty** has by far the most tests. It is also the only project that fuzzes and
  runs a conformance suite in CI. That supports using libghostty-vt as the benchmark
  even if puritty doesn't adopt it (synthesis §3.1).
- **Alacritty and vte** are well tested for their size, and their code is small.
  The recorded-session replay tests are worth copying for puritty's headless core
  (synthesis §11).
- **Windows Terminal** is uneven. The parser and terminal core are reasonably
  tested, but much of the VT coverage lives in conhost's tests, and the renderer has
  none.
- **WezTerm** has the least coverage. The terminal core, termwiz and the escape
  parser average about 5 tests per 1k lines, and mux and pty have almost none. That
  fits the synthesis's advice to borrow WezTerm's designs rather than its code. Its
  SSH config parser, which the synthesis says has subtle bugs, has only 11 tests.

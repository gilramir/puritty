# Refinements: what the newer checker can now prove of puritty, a survey

*2026-11-21. Gilbert: "now that we have new refinement abilities in the
geng compiler, look for new opportunities to add refinement constraints to
our puritty code (or even the other geng libraries it depends on), to
strengthen our code base. Then run the geng checks report to look for other
opportunities." This is that survey, measured, with two pilots built to
see that the opportunities are real. Nothing past the pilots is changed
yet; RS8 is the order proposed.*

## RS1 · What the checker can say now

geng-lang's fork at `cce34a5c` (`m4-refine-wrap.md`, `docs/user/refinements.md`
"An array's elements may be refined"). Of what was added since puritty's
code was last held to the checker (VC64, TK13), these touch puritty:

- **An array's elements**, `Array (x : Int where 0 <= x && x < 256)`, at a
  signature's arguments and result and at a record alias's field, and the
  same of an `Array.Builder`, a `Maybe`'s payload, a `Set`, and a `Dict`'s
  keys and values (Dgmk25–Dgmk29, Dgmk35). Known where an element is read,
  asked where an array is given; `core`'s functions say what they do with
  elements (`map`, `set`, `pushLast`, `keepIf`, a literal).
- **A record's field may name its elements** at a signature, and a
  variant's record too: asked where the constructor is applied, known where
  it is matched (Dgmk40, §WR61, §WR62).
- **A callback handed only a container's elements** says so with `member`
  (Dgmk36), and a function passed by name is the lambda that calls it
  (Dgmk37).
- **`core` says more**: `String.split` answers at least one string when the
  separator is not empty; `String.firstIndexOf` and its kin answer an index
  from 0 to the string's count; `withDefault` of a callback's `Maybe` is
  the payload or the default (§WR53); every array `Array` builds says its
  length.
- **Arithmetic**: floored quotients known on each side of a divisor's
  sign (§WR63), `2 ^ k`, `popCount`, and bit operations between values by a
  SAT solver (Dgmk21–Dgmk24, Dgmk30–Dgmk32).

## RS2 · The report today

`scripts/checks.sh --json`, puritty `0876bf7` (the app with vt, tmux, ssh,
text and x11, which the report covers as path packages in the repository):

| | count |
|---|---|
| checks hold | 2,718 |
| record invariants kept | 934 |
| fallbacks never run | 115 |
| fallbacks that can run, unmarked (the baseline list) | 70 |
| open | 0 |
| `meant` fallbacks | 1,625 |

The `meant` marks by reason, the six largest: `NotSet` 364 across the
packages, `FromOutside` 324, `OutOfRange` 197, `NotKnown` 209, `NotOpen` 185,
`NoMore` 136. `OutOfRange` ("an index or position is past an edge") is where
a refinement most often can stand in for a mark: an index the code keeps in
range for reasons the checker could be told.

## RS3 · Fallbacks that never run: 115, each a proof waiting to be used

A fallback the checker shows no value reaches is dead code it already
guards. Written as a proved read instead, the default goes, the `Maybe` is
not made, and the report counts a check that holds. By shape:

- **vt's cell reads, about 30**: `Maybe.withDefault 0 (Builder.get (o + x)
  cells)` in `Vt.Screen`, `Vt.Edit`, `Vt.Cursor`, `Vt.Parse`, `Vt.Print`,
  `Vt.View`, `Vt.Pages`, `Vt.Dump`, `Vt.Prompt`. These are the screen's
  inner loops; `Builder.getProven` reads them with no `Maybe`.
- **The first of a split, about 15**: `String.split sep x |> Array.first |>
  Maybe.withDefault d` (TmuxMode's status-line parsing, `Vt.Osc`,
  `Vt.Notice`, `Tmux.Caps`, `Tmux.Syntax`, `Window.fontUsed`). `split`
  promises one string; `Array.getProven 0` reads it.
- **`Main.handleOne`, about 20**: `else if Maybe.isJust m.x then … when m.x
  is Just a -> … ; Nothing -> Task.succeed m`. The `isJust` makes `Nothing`
  dead. Matching once, not testing then matching, removes both; this is
  tidiness more than strength.
- **The rest, about 50**: a lookup into a literal table at a bounded index
  (`Vt.Keys.functionKey`, `Vt.Print.graphic`, `Vt.Charset`), bytes read
  within a length already tested (`Window.decode`, `Ssh.Base64`,
  `Tmux.Command.quoteFrom`), `Char.fromCode` of a code known valid.

**Pilot 1, built**: `Vt.Screen`'s five (`metaAt`, `cellAt`, `peekCell`,
`extendTo`, `setWrapped`) as `Builder.getProven`. Checks hold 2,718 →
2,723, never run 115 → 110, nothing new on the list; vt's suite 211 of 211
on node, Linux and Windows. Not measured: whether it is faster.

## RS4 · `OutOfRange` marks: 197, some of them provable

The checker finds a value reaching each, so each needs a fact it does not
have. Read one by one, three kinds:

- **Provable with the new forms.** Tables of a fixed size read at an index
  the code bounds: JPEG's quantization tables (64) and Huffman counts (16),
  the zigzag tables, and likely Inflate's code-length order (19). **Pilot 2, built**
  (`Vt.Jpeg`): `type alias Quant = (q : Array Int where Array.length q ==
  64)`; `unzig` stated as 64 elements, each 0 to 63; `unzigAt` and
  `quantAt` take a refined index and read with `getProven`. Checks hold
  2,723 → 2,739, two `meant OutOfRange` gone, nothing new; vt's suite with
  its JPEG cases 211 of 211 on the three. It found the two gaps of RS7,
  and one place where the mark hid input: `acs` reads the table at `k + r`,
  which a damaged file's run takes to 78, so that read is now tested
  (`at <= 63`) and keeps the answer it gave before for a damaged file.
- **Input, marked with the wrong reason.** Inflate's `lengthExtra` read at
  `sym - 257`, refuted with `sym = 286`: deflate defines no symbol 286 or
  287, but a damaged stream sends them. That is `FromOutside`, tested and
  said, not an edge. Some of Jpeg's may be the same (`component`, refuted
  with a frame of no components); each is to be read.
- **Real, and rightly marked.** Most of TmuxMode's 68: a selection into a
  list that can be empty (the tree, a listing, customize mode, a menu), a
  character index into an empty prompt. Some are not: `t.sort` read into
  `sortNames` (4) and `l.sort` into `listSortNames` (3) are indices the
  code keeps in range, and a record field `sort : Int where 0 <= sort &&
  sort < 4` would prove them.

## RS5 · The 70 that can run, unmarked

VC64 put these on the baseline as listed rather than meant. Read again
with the new checker:

- **Provable**: `Vt.Width.width`, every printed character's width, reads a
  8,192-entry table at `cp // 16`, refuted with a negative `cp`; refining
  its argument to a code point (`0 <= cp && cp <= 0x10FFFF`) would prove
  it, and asks each caller for the range: whether the parser's decoders
  already keep it where the checker can see is not yet looked at. It is generated (`vt/gen-width.py`), so the generator
  changes. `Vt.Style.intern` and `Vt.Sgr.withPen` read the style table
  and its cache at an id the code hands out: a record invariant on the
  styles (`id < Array.length table`) proves both. `Schema.hex` and
  `Tmux.Borders.cells` read `String.toArray "0123456789abcdef"` at a digit:
  a 16-element literal and `getProven`. `Schema.distance` (edit distance)
  reads rows whose lengths the loop keeps.
- **Real, to mark `meant`**: the ssh packets read at byte 0 or 4 when empty
  (`Ssh.Transport.messageNumber`, `unpad`, `Ssh.Auth.received`: a peer's
  short packet, `FromOutside`), `Vt.Recut`'s six on an empty page list,
  `Schema.alternatives` with no names, restore with no tabs.

## RS6 · The libraries puritty takes from outside the repository

`geng checks` reports on a library only from a program inside the library's
own repository, so each was run through its test program
(`tests/`, which puts the library on its path):

| library | checks hold | never run | can run, unmarked | open | `meant` |
|---|---|---|---|---|---|
| gren-toml | 14 | 1 | 106 | 4 | 0 |
| gren-argparse | 0 | 0 | 35 | 0 | 0 |
| gren-civil-time | 2 | 0 | 6 | 0 | 0 |
| gren-i18next | 0 | 0 | 6 | 0 | 0 |

(The tests' own fallbacks are left out.) None has had puritty's pass:
every fallback is unmarked. gren-toml's four open checks are each a
position plus or minus one (`Toml.Edit.closesUp`, `nextTrivia`,
`commentsAt`, `Toml.Strings.codePoint`), where an argument refined to an
index of its array (`0 <= index && index < Array.length expressions`)
settles it; 53 of its 106 are `Toml.Edit`'s lookups of an expression at an
index, the same refinement's work. geng-lang's `os` package has no test
program, so it was not run.

## RS7 · Two gaps in the checker, met by the pilots

1. **A refined alias as a `Dict`'s value in a record alias's field is
   refused** (`MISPLACED REFINEMENT`), where an `Array`'s element in the
   same place is allowed (Dgmk28) and a `Dict`'s value in a signature is
   (Dgmk35). `Parsed.quant : Dict Int Quant` had to become `Dict Int
   QuantTable`, a one-variant type whose argument is the alias (a
   constructor's contract, which is allowed).
2. **`Array.initialize`'s callback is not told its index**: in
   `Array.initialize 64 0 (\i -> … unzigAt i)`, `0 <= i && i < 64` is
   refuted. The code beside it already clamps (`clamp 0 63 i`), as the
   pilot now does too. `indexedMap`'s index and `map`'s element are known.

Both are geng-lang's to decide; written here first, for its register.

## RS8 · Proposed order

1. **vt's never-run cell reads and split-firsts** (RS3): mechanical, each
   a proof the checker already has, about 45 sites. Pilot 1 is the first
   five.
2. **Fixed-size tables in vt's decoders** (RS4): the rest of Jpeg and
   Inflate, by pilot 2's pattern, with input tested and marked
   `FromOutside` where the mark hid it.
3. **The provable 70s** (RS5): `Vt.Width` through its generator, the style
   table's invariant, the hex digits; the rest marked `meant`, so that the
   baseline list holds only what is decided.
4. **TmuxMode's sort indices** (RS4) and **`handleOne`'s shape** (RS3).
5. **gren-toml**: the index refinements that settle its four open checks
   and most of `Toml.Edit`'s fallbacks, then marks for the rest; then
   argparse, civil-time and i18next, which are small.

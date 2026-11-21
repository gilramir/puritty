# 15 · Library dependencies outside the repository (gren-toml, gren-argparse, gren-i18next, gren-civil-time)

All paths are absolute, under `/home/gram/prj/geng-lang/vendor/gilramir/`. Nothing was built or run: every
finding is from reading the code, and "confirmed" means the scenario was traced through the source by hand.
`gren-toml` states that it reads TOML 1.1 (its `CLAUDE.md`, `Parse.geng:916`), so 1.1-only syntax being
accepted is by design and is not reported.

### LB1 · `Toml.Edit.removeTable` deletes the comment block that belongs to the *next* table, and every floating comment in the removed section
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Edit.geng:2208-2231 (`removeTable`), :2283-2290 (`under`), :2481-2501 (`headers`); reached from puritty at `app/src/Schema.geng:2162` (`write`, a table emptied by a reset) and `app/src/Schema.geng:1924` (`deleteHost`)
- Kind: bug
- Severity: medium
- Confidence: confirmed (by trace; not run)
- What: `removeTable` drops every expression for which `under path header expression` holds. For anything that is not a header line, `under` is `prefixOf path header`, where `header` is the header *in effect* at that line (`headers` only changes it at a `Header` expression). So blank lines and own-line comments stay "under" the removed table right up to the next header line, including the comment block directly above that next header. By this module's own convention (`Edit.geng:109-112`, `tableComments`) that block is the next header's. `ownedBlockLeads` only adds the block *above* the removed header; nothing spares the block below.
- Scenario: the file is
  ```
  [font]
  size = 14

  # my work machines
  [hosts.build]
  user = "me"
  ```
  The user resets `font.size` to its default. `Schema.write` removes the key, finds no path left under `font` and no comment over `[font]`, and calls `removeTable [ "font" ]`. Lines `[font]`, the blank, and `# my work machines` are all dropped: a comment the user wrote for `[hosts.build]` is gone. The same happens to a comment above the next host on `deleteHost`. `docs/settings.md` ST18 already guards the comment *over* the removed header because "a user's comment lost is what `settings-ui.md` §5 says never happens"; this is the same loss on the other side, unguarded. The Editing fixture (`tests/src/Editing.geng:41-64`) has no comment between a removed table and the next header, so no test covers it.
- Fix: in `removeTable`, stop a removed run before the trailing comment block that touches the next surviving header (walk back from each surviving header with the same rule `firstOwned` uses), and decide deliberately whether floating comments inside the removed section go or stay. Add the fixture case.

### LB2 · `removeTable` does not remove a table written with dotted keys, though `renameTable` renames one
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Edit.geng:2283-2290 (`under`), compare :2120-2138 (`renameTable`'s `Pair` branch); puritty `app/src/Schema.geng:1924`
- Kind: bug
- Severity: medium
- Confidence: confirmed (by trace; not run)
- What: `under` matches a header line whose path has `path` as a prefix, or any line whose header in effect has. A `Pair` whose own dotted key supplies the rest of the path is not matched: for `[hosts]` followed by `build.user = "me"`, the header in effect is `[ "hosts" ]`, and `prefixOf [ "hosts", "build" ] [ "hosts" ]` is false. `renameTable` handles exactly this shape (`namesATable`), so the two disagree on what "the table at a path" is.
- Scenario: a user's hand-written file has `[hosts]` / `build.user = "me"` / `build.port = 22` (or top-level `hosts.build.user = "me"`). Deleting host `build` in the settings window calls `removeTable [ "hosts", "build" ]`, which returns the document unchanged: the write is a no-op (`SettingsFile` writes nothing when no byte changes), the host is still in the file and comes back on the next read, with no error. Renaming the same host works.
- Fix: in `removeTable`, also drop a `Pair` when `header ++ Literal.path key` has `path` as a strict prefix (the test `renameTable` already makes), with its owned comment block as `remove` takes it.

### LB3 · `Toml.Table.Error` carries no position, and its path is a dot-joined string
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Table.geng:234-237 (`Error`), :766-768 (`join`), :343 (`fromDocument` folds expressions without their index); `Toml/Decode.geng:237-244` inherits it
- Kind: design
- Severity: medium
- Confidence: confirmed
- What: a semantic rejection (duplicate key, table defined twice, closed table) reports `{ path : String, reason }` where `path` is `String.join "." segments`. The expression index is in hand in `step` and is discarded, and the AST keeps no line numbers, so the caller cannot say where the error is. The joined path is also ambiguous: the keys `"a.b"` and `a.b` join to the same string.
- Scenario: puritty has to rebuild positions itself (`app/src/Schema.geng:1100`, `linesOf` at :2196-2215: re-rendering every expression with `Toml.toString` and counting `"\n"` to recover line numbers, then looking the error up by the joined path). For `KeyDefinedTwice` that lookup can only give one of the two lines (whichever the dict kept), and for a quoted key containing a dot it can give the line of a different key; a miss falls back to line 1. A duplicate-key error is the commonest hand-edit mistake and is the one that cannot be located exactly.
- Fix: have `fromDocument` carry the expression index (and the segments as `Array String`) into `Error`; a line number can then be derived once in the library (count newlines of the expressions before it) instead of by each caller.

### LB4 · A path through an array of tables does not mean "the last item": lookups match any item
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Edit.geng:2392-2410 (`indexOf`), :2640-2660 (`lastOf`); documented rule at :126-131
- Kind: bug
- Severity: low (puritty's schema uses no `[[...]]`; `docs/settings.md:37-39`)
- Confidence: confirmed (by trace; not run)
- What: `indexOf` takes the last expression whose `header ++ key` equals the path, and `lastOf` the last non-empty expression whose header equals the table path. Both compare flat header paths and know nothing of which `[[item]]` a line is in. The documentation says a path names the last item, "for reading and writing alike", and that a missing key "is added to the last one too".
- Scenario: `[[peer]]` / `x = 1` / `[[peer]]` / `y = 2`. `get [ "peer", "x" ]` answers `1` (the first item's), though the last item has no `x`; `set [ "peer", "x" ] v` rewrites the first item's `x` instead of adding one to the last; with `[peer.tls]` only under the first item, `set [ "peer", "tls", "k" ]` inserts into the first item's `tls`. `Toml.Table` (the semantic layer) disagrees with all three.
- Fix: bound the search to the expressions at or after the last `[[header]]` whose path is a prefix of the target path.

### LB5 · A dotted key that adds to an implicitly created table does not mark it defined, so a later header for it is accepted
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Table.geng:557-560 (`updateHelp`, `Present (TableValue sub)` branch), :615-622 (`passable`)
- Kind: inaccuracy (TOML conformance)
- Severity: low
- Confidence: plausible (the code path is confirmed; that the spec requires rejection is my reading, and `toml-test` has no case for it)
- What: a `DottedWalk` may pass through a table whose origin is `Implicit`, and the table is put back with its origin unchanged. So after a dotted key has written into it, it is still `Implicit`, and `defineTable` (:400-402) lets a header define it.
- Scenario:
  ```
  [a.b.c]
  [a]
  b.x = 1
  [a.b]
  ```
  is accepted. `b.x = 1` under `[a]` defines `a.b` by dotted key, and the spec's rule ("a table defined by dotted keys cannot be redefined with a `[table]` header", the `fruit.apple` example) makes the final `[a.b]` an error; Python's `tomllib` rejects it.
- Fix: when a `DottedWalk` passes through an `Implicit` table, put it back as `Dotted`.

### LB6 · Reading and writing a string literal builds the result one character at a time by concatenation
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Strings.geng:232-264 (`verbatim`), :274-316 (`unescape`), :198-204 (`keepDelimiters`), :646 (`escape`), :656-671 (`mlEscaped`)
- Kind: speed
- Severity: low
- Confidence: plausible (quadratic only if Geng's `String.pushLast`/`++` copy the accumulator; the ownership pass may make them in place, which I did not check)
- What: each step does `String.pushLast char acc` or `acc ++ text` on the whole string read so far, after `String.toArray` has already made an `Array Char` of the body. `escape` is `String.foldl (\char acc -> acc ++ escapeChar char) ""`.
- Scenario: every string value and every quoted key in the settings file goes through this on each read; cost is the square of the literal's length. Invisible for a 40-character font name, seconds for a multi-megabyte multi-line string in a hostile or damaged file. The settings file is re-read on change, so this is on the reload path.
- Fix: collect pieces in an array and `String.join` once, or append runs (slice between escapes) rather than characters.

### LB7 · Nesting depth and delimiter runs are unbounded recursion on file content
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Parse.geng:871-888 and :919-937 (arrays and inline tables recurse through `value`); `Toml/Table.geng:654-691` (`lower`); `Toml/Write.geng:153-208`; `Toml/Strings.geng:178-184` (`runLength`, `1 + runLength ...`, not a tail call)
- Kind: security
- Severity: low (the input is the user's own settings file)
- Confidence: plausible (no depth limit exists, confirmed; whether the native runtime turns deep recursion into a crash was not tested)
- What: there is no limit on how deep `[[[[...` or `{a={a={...` may nest, and each level is a native recursion in the parser, again in `lower`, again in `Write`. Separately, a `"""` literal closed by a very long run of quotes reaches `runLength`, which recurses once per quote before `keepDelimiters` can refuse the run.
- Scenario: `a = ` followed by a few hundred thousand `[`, or `a = """` followed by a few hundred thousand `"`, in `config.toml`: a stack overflow in the terminal at start or at settings reload, instead of a parse error with a line.
- Fix: carry a depth through `value` and fail with a `Problem` past some bound (TOML libraries commonly use about 100 to 1000); make `runLength` a loop that stops at 3.

### LB8 · Comment text written by `setComments`, `introduce` and `Toml.Encode.commented` is not checked
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Edit.geng:722-730 and :791-817; `Toml/Encode.geng` (`block`, `keyLine`, `headerLine`); `Toml/Write.geng:90-97`
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: the strings go into `Comment.text` as given and `Write.comment` emits `"#" ++ text`. A newline or a control character in the text is written raw.
- Scenario: a caller passes a comment containing `"\n"` (a two-sentence explanation, or text that came from outside): the second line is written without a `#`, so the file either stops parsing or gains a key. The document no longer round-trips, and nothing reports it until the next read. Every other writer in the package (`Strings.escape`, `Strings.literal`) refuses or escapes what its form cannot hold.
- Fix: split a comment on line endings into several comment lines for `leading`, and refuse or strip characters `Strings.isCommentChar` rejects (for `trailing`, where there is one line only).

### LB9 · Invalid UTF-8 is reported at line 1, column 1
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml.geng:169-171
- Kind: design
- Severity: low
- Confidence: confirmed
- What: `Bytes.toString` answering `Nothing` becomes `{ row = 1, col = 1, expecting = "valid UTF-8" }`.
- Scenario: a settings file saved as EUC-KR or Latin-1 with one bad byte on line 240: puritty's message (`app/src/SettingsFile.geng:77`) says "line 1 is not TOML, or not UTF-8: line 1, column 1: expected valid UTF-8", which sends the user to the wrong line. Puritty's users include EUC-KR ones, so this is not a rare file.
- Fix: on failure, scan the bytes for the first invalid sequence and report its line and column (or at least its byte offset).

### LB10 · `Toml.Decode.int`'s documentation gives the limit as 2^53, which is stock Gren's
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Decode.geng:162-168, :387-411; `Toml/Table.geng:648-651`
- Kind: inaccuracy
- Severity: low
- Confidence: plausible (rests on Geng's `Int` being 32-bit, as `gren-argparse/src/Argparse/PrettyPrinter.geng:357-358` says of the same port)
- What: the docs say `int` fails "above 2^53, since a Gren `Int` is a double". On Geng the refusal comes from `BigInt.toInt`, at the `Int` range, far below 2^53. The error text ("does not fit in an Int") is right; the documented bound is not.
- Scenario: a caller sizing a setting from the documentation expects `4294967296` to decode; it is refused. (Puritty maps the failure to "too large a number", `app/src/Schema.geng:1108`, so it is safe there.)
- Fix: say "outside the range of an `Int`" and drop the 2^53 and "is a double" wording in both places.

### LB11 · The date `0000-..` is refused
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-civil-time/src/Civil/Date.geng:105
- Kind: inaccuracy (RFC 3339 / TOML conformance)
- Severity: low
- Confidence: confirmed
- What: `fromParts` refuses a year below 1, so `Date.fromString "0000-01-01"` is `Nothing`, and through `Toml.Parse.valueOf` a TOML file with `d = 0000-01-01` fails as "a value, but 0000-01-01 is not one". RFC 3339's `date-fullyear` is any four digits. The package documents years 1 to 9999 as its range, so this is a stated limit of the library, but it makes the TOML parser reject a valid document.
- Scenario: only a file that uses year 0 as a sentinel; none of puritty's settings are dates.
- Fix: either accept year 0 in `Civil.Date` (the Rata Die arithmetic already passes through year 0 for January and February of year 1), or note the limit in `Toml.Parse`'s documentation.

### LB12 · argparse: a flag cannot be given an empty value
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-argparse/src/Argparse/Parser.geng:487-514 (the `""` sentinel), :563-567, :1558-1563 (`flag`), :1632-1637 (`requiredFlag`)
- Kind: bug
- Severity: low
- Confidence: confirmed (by trace; not run)
- What: the tokenizer stores `""` for "present with no value", and `flag` reads `Just ""` as `FlagParserMissingValue`. A value that really is the empty string is stored the same way, from `--title ""` and from `--title=` alike.
- Scenario: `puritty --title "" -- htop` (a window with no title text) fails with "This flag needs more information: --title". The reverse also holds: `--try-folder-picker=` is accepted as the toggle being on.
- Fix: store flags as a type with two cases (`Bare` / `Given String`) instead of a `String` with a sentinel.

### LB13 · argparse: any token starting with a single `-` is one short flag, even where it cannot be
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-argparse/src/Argparse/Parser.geng:581-588, :525-551
- Kind: design
- Severity: low
- Confidence: confirmed
- What: `-abc` is looked up as the one short name `abc` (no clusters), `-ovalue` likewise, and a positional that begins with `-` (a negative number, or the lone `-` that means standard input) is reported as an unknown flag `-5` / `-`. In the value position the rule is the other way: `--offset -5` takes `-5` as the value, while `--title --x` refuses `--x` (:487). None of this is in the package's list of deliberate omissions.
- Scenario: `puritty ssh -p 2222 host` fails with "I don't recognize this flag: -p"; the user has to know to write `puritty -- ssh -p 2222 host` (which `docs/settings.md:282` does show). The error names the flag but not the remedy.
- Fix: at least make the unknown-flag message for a single-dash token mention `--`; better, stop flag parsing at the first positional for a command whose arguments are `zeroOrMoreArgs` (the "program and its arguments" shape), as `env`, `sudo` and `xterm -e` do.

### LB14 · argparse: colour and width for error text on stderr are decided from stdout
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-argparse/os/src/Argparse/Program.geng:170-181 (`renderOptions`), :275-277 and :412-414 (`failWith` writes to stderr with the same options)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `useColor` and `maxColumns` come from `Os.Env.standardOutputTerminal` only, and are used for `Console.writeErr` too.
- Scenario: `puritty --bad 2> err.log` from a terminal writes ANSI escapes into `err.log`; `puritty --bad | cat` prints the error to the terminal uncoloured and wrapped at 80 whatever its width.
- Fix: ask about the stream being written to (a second `renderOptions` for stderr).

### LB15 · `PrettyPrinter.stripColor` does not look inside a coloured document
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-argparse/src/Argparse/PrettyPrinter.geng:264-265
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `Colorized { document = colorizedDocument } -> colorizedDocument` returns the inner document as it is, without recursing.
- Scenario: `color Cyan (verticalBlock [ text "a", color Red (text "b") ])` rendered with `NO_COLOR` set, or to a pipe, still emits the escape codes for `b`. The library's own help and error documents do not nest colours today, so this bites a caller's `intro`/`outro`/`example` document first.
- Fix: `stripColor colorizedDocument`.

### LB16 · i18next: replacements are applied one after another, so a value is searched for later placeholders
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-i18next/src/I18Next.geng:218-229 (`replacePlaceholders`); `customReplace` at :290-359 does not have the problem (it splits the template first)
- Kind: bug
- Severity: low
- Confidence: confirmed
- What: `Array.foldl` runs `String.replace` once per placeholder over the string that already has earlier values in it.
- Scenario: puritty builds messages with `Words.with` (`app/src/Words.geng:61-63`) from outside text: a host name, a file name, a system error. A message `"{{host}}: {{why}}"` with a host named `{{why}}` (or a file named `{{text}}`) has the later value substituted into the earlier one, so the text shown is not what the remote side sent. It can only repeat values of the same message, so it is a display error, not an injection of consequence.
- Fix: one pass over the template: split on the opening delimiter, and for each piece look the name up in the replacements (what `customReplace` does), so substituted text is never rescanned.

### LB17 · Every `Toml.Edit` call rescans the whole document several times
- Where: /home/gram/prj/geng-lang/vendor/gilramir/gren-toml/src/Toml/Edit.geng:2392-2410 (`indexOf` builds `headers` and a flags array, allocating a path per expression), :2308-2316 (`rebuild`, three passes), :962-969 (`introduce`: `member`, `set`, `setComments`, each its own `indexOf`)
- Kind: efficiency
- Severity: low
- Confidence: confirmed (the cost shape; not measured)
- What: one `set` is `headers` (N path arrays) + N `Array.prepend`s and comparisons + `rebuild`'s three maps; writing a host or a whole configuration is one such call per field.
- Scenario: `Schema.writeHost` folds `write` over every host field, and each `write` on the reset path does `remove`, `tableComments`, `paths` and possibly `removeTable`: about 5 full scans per field. For a 300-line file and 40 fields that is 60,000 expression visits with an allocation each, per save. Not felt today; it grows with lines times fields.
- Fix: none needed now. If it is ever measured as slow, compute `headers` once per batch (an `Edit.batch` taking a list of edits), or index key paths to expression numbers.

## Looked at and found sound

- **gren-toml, syntax** (`Parse.geng`, `Strings.geng`, `Number.geng`, whole files): the four string forms, including the closing run of a triple-quoted literal (`""""""""` is two quotes, nine quotes is refused), the line-ending backslash with CRLF, the trimmed first newline, `\u`/`\U` range and surrogate refusal with the 32-bit clamp; control characters and DEL refused in strings and comments; a lone CR refused everywhere; CRLF kept as CRLF; bare-key characters; underscore, leading-zero, sign-on-prefix and uppercase-prefix rules for integers; `inf`/`nan` with signs; floats needing a fraction or exponent; the date-then-space-then-time case; BOM (one allowed, recorded and written back; a second refused); strict UTF-8 through `parseBytes`. Integers are `BigInt`, so there is no range error to miss; the 64-bit question is documented (`Table.geng:634-651`).
- **gren-toml, error choice** (`Toml.geng` `chooseError`, `Parse.rank`): furthest position, then rank; every `Problem` has a rank. Syntax errors do carry row and column.
- **gren-toml, semantics** (`Table.geng`, whole file) against the vendored `toml-test` invalid/table cases `append-with-dotted-keys-01..08`, `super-twice`: duplicate keys, a table defined twice, a header on a dotted-key table, a dotted key into a header's table or into an array of tables, inline tables sealed (and their sub-tables), `[[a]]` over a literal array, `[a]` after `[a.b]`. One gap is reported above.
- **gren-toml, writing** (`Write.geng`, `Literal.geng`, `Strings.escape`/`literal`, `Encode.geng`): what it writes is TOML 1.0 as well as 1.1 (no `\x`/`\e`, single-line inline tables without a trailing comma, seconds always written); keys are quoted when not bare, the empty key is `""`; quote, backslash, control characters and DEL are escaped; a `"""` body escapes the third quote of a run and a final quote; a float always has a point or exponent; negative zero, `inf`, `nan` handled; Encode writes a table's own keys before its sections.
- **gren-toml, Edit** (`Edit.geng`, whole file): `set` on an existing key changes only the value and compares by meaning first; `rebuild`'s two line-ending invariants; insertion of a top-level key before the first header; a new header appended before the terminator expression; `remove`'s blank-line rule; `rename`/`renameTable` quoting of the new name; the array-element editors' handling of `before`/`after`/`trailing` for `appended` on the shapes `[]`, `[ ]`, `[1, 2]`, `[ 1, 2 ]` and a multi-line list with notes (traced by hand, not exhaustively); negative indexes guarded. The three ways an edit can produce a document `Toml.Table` rejects (inline table, dotted-key table, key over a header) are documented at `Edit.geng:134-152` and not reported.
- **gren-toml, Decode** (`Decode.geng`, whole file): errors carry the path asked for and the kind found, never the value; `oneOf` keeps each failure; `optionalField` still fails on a wrong type.
- **gren-civil-time** (all four modules, whole files): leap-year rule, month lengths, the Hinnant day-number arithmetic in both directions (checked 0001-01-01 = 1 = Monday, the era and March-based month terms), `weekday`, floor division for moments before 1970 in `fromPosix`, `toPosix` in `Int64`, offset range and the three zeros (`Z`, `+00:00`, `-00:00`), strict field widths in every `fromString`, fraction kept as text with trailing zeroes trimmed, range checks in every constructor. Second 60 accepted at any time is documented as the leap-second rule.
- **gren-argparse** (`Parser.geng`, `PrettyPrinter.geng`, `os/src/Argparse/Program.geng`): `--` ends flag parsing and the rest is positional untouched; `--opt=value` splits on the first `=`; `--opt value` consumes the next token unless it starts with `--`; repeated flags are last-wins (documented); required flags; unknown flags reported with the known ones; `--help`/`-h` anywhere before `--`; arities; prefix groups; wrapping measures ANSI escapes as zero width and guards a zero-width terminal; exit codes.
- **gren-i18next** (`I18Next.geng`, whole file): missing key answers the key; fallback chain takes the first table that has the key; nested trees flatten to dotted keys. The package has **no plural forms, no nesting (`$t(...)`) and no escaping** at all: it is key lookup plus placeholder substitution, so there are no per-language plural rules to be wrong. Puritty uses only `fromTree`, `string`, `hasKey`, `t` and `trf`.

## Not covered

- `Toml/Ast.geng` (types only) was not read line by line; `Toml/Encode.geng`'s documentation half (lines 1-150) was skimmed.
- `Toml.Edit`'s `moveAt`/`insertAt`/`removeAt` were read but only `appended` was traced over several shapes; puritty does not call the element editors (it sets whole arrays).
- `Argparse/Parser.geng`'s documentation comments and the help-text builders were skimmed, not traced for layout.
- Nothing was executed, so none of the scenarios above was reproduced; behaviour of core functions these packages lean on (`String.Parser.Advanced`, `BigInt`, `BigDecimal`, `Bytes.toString`, `String.pushLast` cost, native stack depth) was assumed, not checked, and is the compiler's and core's side.
- The `node/` variant of argparse, examples, tests and `.gren` files, as instructed.

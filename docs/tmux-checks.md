# Checking puritty against every tmux: the plan

Gilbert, 2026-11-14, reading about SAT-based model checking: can puritty be
shown to handle every tmux protocol version the survey dumped
(`docs/tmux-versions.md`), with more rigor than tests that try one
ordering on two versions? Three checks were proposed and he chose to
build them in order, starting with the first. Section numbers are TK*n*.

None costs puritty anything at run time: the first adds one small record
per command sent (commands go at a key's or a timer's pace, not output's),
measured by `perf.py` when built; the others are tests and proofs.

---

## TK1 · What each check proves, and against what

| check | proves | domain | how |
|---|---|---|---|
| 1 · commands accepted | every command shape puritty can send to a tmux is one that tmux's `list-commands` says it takes | 33 dumped tmuxes × every shape | enumeration: finite, complete |
| 2 · 2.x keys delivered | `send-keys` lines for tmux before 3.0 put exactly the typed bytes in the pane | every byte sequence | a model of 2.7's parser; exhaustive small cases now, an SMT proof later |
| 3 · replies in step | puritty's queue of awaited answers stays aligned with the blocks tmux owes, whatever order notifications, keys and timers come in | orderings up to a depth | explicit-state exploration of the real `TmuxMode` against a tmux model per version |

Each proves puritty against a *model* of tmux. The dumps make the model
measured rather than read from the manual, and each model is checked
against the real binaries where it is cheap to (TK3.3); runs against real
tmuxes (TM72's) stay beside the proofs.

## TK2 · Check 1: commands as values, and a catalog

**Today** a command is a string joined where it is sent: 126 literals
start with a tmux command's name (112 in `TmuxMode`, 12 in `Tmux.Command`,
2 in `Main`), some of them comparisons with what tmux sent rather than
commands. Nothing can list what they make.

**The design:**

- **`Tmux.Command.Shape`**, opaque, made only in `Tmux.Command`: a
  command's name, the flags it uses, and when it may be sent, a predicate
  on the tmux's `Caps` (always, for most).
- **`Tmux.Command.Command`**, opaque: a shape and its arguments. It is made
  only from a shape, by `make : Caps -> Shape -> … -> Maybe Command`,
  `Nothing` when the shape's predicate refuses this tmux, so that a
  caller must say what it sends instead; and turned to text only where it
  is sent (`render`). `TmuxMode` and `Main` send `Command`s, so no
  command can be sent that was not made from a shape.
- **`Tmux.Command.catalog`**: every shape. A test reads the source of
  `Tmux.Command` and fails when a shape is defined that the catalog does
  not hold.
- **The check** (`app/tests`): for each folder of `corpus/tmux`, its
  `commands.txt` read by `Caps.fromUsage`; for each shape in the catalog,
  if its predicate allows that tmux, every one of its flags must be in that
  command's usage. 33 × about 60 checks.
- **Formats too**: every `#{variable}` puritty asks, listed beside the
  shapes, checked against each tmux's `formats.txt`; a variable a tmux
  answers empty is either one puritty reads as "not known" (listed so) or
  a failure.

**Not covered, by design:** a binding's own command (`bindingLine`) and a
command the user types at tmux's `:` prompt are tmux's or the user's text,
sent as they are.

## TK3 · Check 2: the 2.x keys, against a model of tmux 2.7's parser

- **The model**, `deliver27 : Array String -> Bytes`: what 2.7 writes to a
  pane for `send-keys` lines, from `cmd-string.c` and `key-string.c` and
  TM72's measurements (single quotes literal; in double quotes `\$` and
  `\"`, and `\003` as `003`; `\;` a word; the key names).
- **TK3.1 · Now**: every sequence up to three bytes over about 40 bytes
  that matter (each control byte, `;` `'` `"` `\` space `#` `~`, a letter,
  UTF-8's lead and continuation bytes) through `sendBytesPlain`, and
  `deliver27` of the result compared with them.
- **TK3.2 · Found already by reading**: `sendBytesPlain` makes text with
  `Bytes.toStringLossy`, so a byte that is not UTF-8 (EUC-KR's 0xA4) is
  sent as U+FFFD. The check fails on it until the encoder sends such bytes
  some other way.
- **TK3.3 · The model held to the real 2.7**: a few hundred of those cases
  sent to the built 2.7 (`~/.cache/puritty/tmux`) and the pane's bytes
  compared with `deliver27`'s.
- **TK3.4 · Later, a proof**: the property as a refinement on
  `sendBytesPlain`'s result, for the refinement checker once it reasons
  about sequences by induction (geng-lang's register).

## TK4 · Check 3: an explorer for the conversation

- **The invariant**: the length of `TmuxMode`'s `expecting` equals the
  blocks tmux owes, and each block is handled by the question that asked
  it.
- **puritty's side is the real code**: `TmuxMode` is `event -> State ->
  { state, commands }`, driven as it is.
- **tmux's side is a model per version, from the dumps**: a queue of owed
  blocks, one per command in each line sent; a command or flag the
  version lacks makes its block an `%error`. How a line with a bad command
  among good ones is answered (one block or several) is measured once on
  the real binaries and written into the model.
- **The explorer**: at each step every choice (tmux delivers its next
  block; a notification between blocks; a key; a resize; the poll's
  timer), to a depth of about ten, for each version, states already seen
  skipped by a projection (the queue, the owed blocks, the modes). A
  violation is printed as its steps, and kept as a test.
- **Later, symbolic**: Geng's code is pure and its compiler has Core; a
  small state machine in Geng could be turned into a formula for a SAT or
  SMT solver, every path at once. Research, in geng-lang's register; the
  explorer's traces stay useful either way.

## TK5 · Order

1. Check 1 (TK2): the commands moved into `Tmux.Command`, then the catalog
   and the check. *Building.*
2. Check 2, TK3.1–TK3.3, and the bytes that are not UTF-8.
3. Check 3 (TK4).
4. TK3.4 and TK4's symbolic form, with the refinement work.

## TK6 · Check 1, first step: the catalog and its check (2026-11-14)

- **`Tmux.Command.Shape`** (`name`, `parts`: `Flag`, `Value`, `Rest`,
  and `allowed`, a test on `Caps`), **`render`**, which writes a command
  from its shape so that it holds exactly the shape's flags, and
  **`catalog`**, 14 shapes: every command `Tmux.Command` made (keys in
  their four forms, the size in two, the client's flags, a pane
  continued, the panes, `list-commands`, the paste's buffer and paste).
  Built the same commands as before (the app's 195 tests).
- **The check**: `packages/tmux/tests/gen-versions.py` writes each dumped
  tmux's `list-commands` into `TmuxVersions` (`--check` in the gate holds
  it to `corpus/tmux`), and the `catalog` suite holds every shape to every
  tmux whose `Caps` allows it: no flag missing, and each shape allowed by
  some tmux. Made to fail once on purpose: with `send-keys -H` allowed
  everywhere it names 2.7, 2.8, 2.9, 2.9a and RHEL8's package.
- **Command text elsewhere**: `scripts/tmux-commands.py`, in the unit
  gate, finds string literals in `TmuxMode` and the tmux package that
  begin with a tmux command's name and are not a comparison with what
  tmux sent, held to `corpus/checks/tmux-commands.txt`: 111 now (89 in
  `TmuxMode`, 16 in `Customize`, 5 in `Syntax`, 1 in `Bindings`), each
  to be moved into a shape until the list is empty. Among them, a filter
  TM72 missed: the tree's preview asks `list-panes -f`, which tmux has
  from 3.2.

**Next:** the 111 moved, in batches; the format variables beside the
shapes.

## TK7 · Check 1 built: every command from the catalog (2026-11-14)

The 111 commands made by hand are moved into `Tmux.Command`, and the list
of those left (`corpus/checks/tmux-commands.txt`) is empty: the gate now
fails on any command text outside `Tmux.Command`.

- **The catalog** grew from 14 shapes to 74: the questions (`display`,
  `displayAt`, `displayLiteral`, the `list-*` and `capture-pane` forms,
  `list-keys` in three, the subscriptions, customize-mode's `show-options`
  and `show-environment` by level), the actions (windows, panes, marks,
  kills, clients, buffers, the key table's reset, the drag's `resize-pane`
  and `move-pane`, a pane's option, the mouse's `if-shell`, 3.8's popup),
  customize-mode's changes (`set-option` and `-u`, `set-hook`,
  `show-hooks`, `set-environment`, `bind-key`, `unbind-key`, by level), and
  tmux's choose templates. A part may now be left out (`OptFlag`,
  `OptValue`); the check holds every flag a shape may have.
- **The check found two things**: the tree's preview asked `list-panes
  -f`, which tmux has from 3.2 (it now asks the pane itself, `display-message
  -p -t`); and no tmux's `set-hook` or `show-hooks` takes `-s`, which
  customize-mode would have sent for a hook at the server's level (now a
  hook has no server level, and one said to be there is set globally).
- **What was decided by the version is decided by what tmux takes**:
  customize-mode's `list-keys -F` (3.7), and the shapes' `allowed`.
- **The text changed** where targets were not quoted (`-t '%0'` for `-t
  %0`) and `-gw` is written `-g -w`; tmux reads both alike. The recorded
  questions were recorded again, and two tests' expected commands written
  as they are now.
- **Not covered, by design**: a binding's own command and what the user
  types at tmux's prompt.

**Next:** the format variables puritty asks, against each tmux's
`formats.txt`; then check 2 (TK3).


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
   and the check. *Built* (TK6, TK7), and its formats (TK8).
2. Check 2, TK3.1–TK3.3, and the bytes that are not UTF-8. *Built* (TK9);
   the bytes that are not UTF-8 are not sent (TK9.3, Gilbert's decision).
3. Check 3 (TK4). *Built* (TK10), with how each tmux answers a line of
   several commands measured first; it found three ways puritty fell out
   of step, now fixed.
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

## TK8 · Check 1's formats: every variable asked, against every tmux (2026-11-14)

A variable or option a tmux does not have expands to nothing, with no
error, so asking one gives an empty field and no sign of why.

**What each tmux knows**: `formats-all.txt` was to say, but `display-message
-a` lists only the variables of the context it is run in (a buffer's, copy
mode's, a hook's are missing: 29 of 2.9's), and 2.7 and 2.8 have no `-a`.
So each dump now has `variables.txt`, read from its release's source by
`app/tests/tmux-versions/variables.py` (`format_add(ft, "name"` to 3.1,
format.c's table from 3.2): 119 names in 2.7, 219 in 3.4, 336 in 3.8.
Checked against the dumps: every variable any tmux's `-a` lists is in its
source, but for three internal `*_mode_format` from 2.9 to 3.1c. A
distribution's package is read as its release (its patches are not);
AlmaLinux 10's snapshot as 3.3a's source and its own `-a`. Its options are
its `options-*.txt`. `releases.sh` and `distros.sh` write it after the
dumps; `variables.py --check` holds it to the sources where the tarballs
are cached.

**What puritty asks**: `scripts/tmux-formats.py`, in the unit gate, reads
every format from the source: each lowercase word that stands where a name
does in a string with `#{`, the options sent whole (`optionNames`), and the
helpers that put a name in (`flag "label" "name"`, `matching "name"`). 163
names; two words in a name's place that no tmux knows are text (`never`,
`none`). Each is a row of `corpus/checks/tmux-formats.tsv`: the first tmux
it is asked of (`all`, or the version or capability that gates it, read
from the code), and how an empty answer reads where a tmux from then lacks
it. The gate fails on a name not listed, a row gone, a tmux that lacks a
name with no reading said (LACKS), a reading no tmux needs (NEEDLESS),
and a word no tmux knows. Made to fail on purpose: `pane_flags` said to
be asked from 3.6 names 3.6, 3.6a and 3.6b.

**What it found**, of the 56 names some tmux lacks:

- **Copy mode before 3.1 drew its cursor at the corner.** 2.7 to 3.0a
  have no `copy_cursor_x` or `selection_start_x` (their `cursor_x` is the
  pane's own cursor), so the copy line came back with those fields empty,
  read as 0: the cursor at the pane's top left and a selection from
  there. Now `Copying.located` says whether tmux gave them, and where it
  did not, neither is drawn: missing rather than wrong. A test runs the
  fake tmux both ways (`FakeTmux.World.lacking`, the start of TK4's
  model).
- **Read as off or default, by design**: the options puritty draws by
  (TM47: tmux's default when empty), the search's count and timeout (none
  shown, as those tmuxes show none), 2.x's missing mouse and origin
  flags, `pane_private_modes` before 3.8 (the older flags, TM61), the
  theme before 3.8, `status-format[1]` to `[4]` on 2.7 and 2.8, which have
  one status line.
- **Asked only of a tmux that has it**: 3.8's (the tree's flags and info,
  hooks' counts, popups, the preview's style), gated by version or by a
  capability; customize-mode's key list from 3.7 (`list-keys -F`).
- **Not asked**: `client_colours`, in tmux 3.8's theme colors, which
  puritty fills in before asking (`local`).

That a row's `since` is kept is read from the code, not proved; check 3's
explorer (TK4) will see each format as it is sent, to each version's
model.

**Next:** check 2 (TK3).

## TK9 · Check 2 built: the 2.x keys through a model of tmux 2.7 (2026-11-14)

**The model**, `packages/tmux/tests/src/Tmux27.geng` (test code, as TK3
planned it): what tmux 2.7 writes to a pane for `send-keys` lines, read
from its source. A line is split into words as `cmd_string_split` splits
it (single quotes literal; in double quotes `\e \r \n \t` and any other
character after `\` as itself; outside quotes `\` an ordinary character, a
`#` anywhere the end of the line, a NUL the end), into commands at a word
that ends in `;` as `cmd_list_parse` does (`\;` at a word's end a `;` in
it); its flags read by tmux's own BSD getopt (`compat/getopt.c`:
`configure.ac` refuses glibc's, which reorders); each argument looked up
as a key's name (`key_string_lookup_string`) unless `-l`, else split into
UTF-8 characters (`utf8_fromcstr`), one that `mbtowc` refuses dropped;
each written by `input_key`, which writes a key above 0x7F as UTF-8. What
puritty never sends (`$` and `~` outside quotes, other commands, `-X`,
`-M`, `-R`, `-N`, key names past its own) the model declines to say
rather than guess.

### TK9.1 · Every sequence of up to three bytes

The `keys27` suite sends every sequence of up to three bytes over 52 that
matter (each control byte, DEL, space, `! " # $ ' - ; \ ~ {`, a letter,
the bytes of é and 한, a lone continuation, 0xFF): 143,364 sequences, each
through puritty's `sendBytesPlain` and the model. A sequence that is
UTF-8 must reach the pane as typed; one that is not is held to what TK3.2
said, each bad run made U+FFFD (TK9.3).

**It found** that a text run beginning with `-` (`- x`, `-!`, `--`, `-la`
pasted) was read by getopt as flags: `-l '-la'` is `-l -l -a`, `-a` is
unknown, and tmux refuses the command, so the keys were lost. The text now
follows `--` (`Command.EndOfFlags`, in `sendLiteral`'s shape): `send-keys
-t '%0' -l -- '-la'`. Nothing else differs.

### TK9.2 · The model held to the real tmux

`packages/tmux/tests/record-keys27.py` sends 205 lines to each tmux built
from 2.7 to 2.9a, in the survey's container, through a control client, to
a pane whose program is `cat` on a raw terminal writing to a file (`stty
raw -echo -iexten`), and records what the pane read; a `display-message`
after each line answers only once tmux has run it. The lines are its own,
not puritty's: the encoder's form for every byte below 0x80, text runs
(UTF-8 of two to four bytes, U+0085, quotes, `;`, a leading `-`), and a
line for each branch of the model (both quotes' escapes and an unclosed
one, `''`, `;` at a word's end, `\;`, `a ; send-keys …`, `#` alone and in
a word, getopt's `--`, `--x`, `-`, `-l-`, a missing value, an unknown
flag, the key names and their case).

**All four tmuxes wrote the same bytes for every line.** The model writes
what 2.7 wrote for 202 of them and declines three, by name in the test
(`C-?`, `C-Space`, `~a`). One reading was wrong and was mended from the
recording: `C-?` is not DEL but xterm's `ESC[27;5;63~` (`?` is among
tmux's `other` characters, whose Ctrl it keeps); puritty does not send it.
Made to fail once on purpose: with `#` not a comment, the test names `-l a
# b` and `-l a#b`.

### TK9.3 · Bytes that are not UTF-8: no `send-keys` reaches the pane

TK3.2 said such a byte (EUC-KR's 0xA4) goes as U+FFFD. Measured on 2.7, it
cannot go by `send-keys` at all: `-l` drops a byte `mbtowc` refuses
(`send-keys -l '\xa4'` writes nothing), and a key above 0x7F is written as
UTF-8 (`send-keys 0xa4` writes `C2 A4`). One way does write the bytes as
they are, measured the same day: `set-buffer -b NAME 'D\xc7\xd1E'` then
`paste-buffer -d -b NAME -t PANE` wrote `44 C7 D1 45`. It needs the bytes
on the command line, and puritty's commands are Geng `String`s, written as
UTF-8 (`Main.linesOf`), which cannot hold them. So the choices are a
command that carries bytes (a `Raw Bytes` form beside the text ones, for
this alone), or leaving it: on tmux before 3.0, text that is not UTF-8 is
not sent. **Decided (Gilbert, 2026-11-15): leave it.** puritty sends
UTF-8 only; no command carries raw bytes. The test holds today's U+FFFD,
so a change shows.

**Not modeled, by design:** a pane in a mode (tmux sends the keys to the
mode's table); a server locale that is not UTF-8 (2.7 refuses to start
without one).

**Next:** check 3 (TK4), the explorer; `FakeTmux.World.lacking` (TK8) is
the start of its per-version model.

## TK10 · Check 3 built: the explorer, and three ways out of step found (2026-11-15)

### TK10.1 · How each tmux answers a line of several commands, measured

TK4 asked for this to be measured once on the real binaries before it was
modeled. `app/tests/dump-lines.py` sends 33 lines to a control client, as
`dump-tmux.py` does its session, and writes every line tmux wrote after
each to `corpus/tmux/*/lines.txt`; `releases.sh` and `distros.sh` run it
for all 33 dumped tmuxes. The lines: two commands that work; one failing
as it runs, first, in the middle and last (`select-pane -t %99`,
`capture-pane -t %99`); one not a command, a flag no tmux has, a missing
argument, a quote left open; commands whose effects tmux tells the client
(`split-window`, `kill-pane`, `new-window`, `copy-mode`); `display-message`
without `-p`; `if-shell` (`-F`, a shell's, `-b`), `source-file` and
`run-shell`; a blank line, `;` alone, a line ending in `;`.

**The same on every tmux:**
- a line that does not parse (a name that is not a command, a flag the
  command lacks, a missing argument) is one `%error`, and none of it runs;
- otherwise each command gets a block, in turn, and **the first that fails
  as it runs ends the line**: the commands after it are not run and get
  no block;
- `if-shell -b`'s commands come after the line, as not this client's
  (flags 0).

**What differs**, by the five kinds of tmux that differ (each
distribution's package answers as its release):

| | 2.7–2.9a | 3.0–3.1c | 3.2–3.3a | 3.4–3.7c | 3.8 |
|---|---|---|---|---|---|
| the commands `if-shell` and `source-file` run: a block each, flags | 0 | 0 | **1** | 1 | 1 |
| notifications the line's commands cause | after the line | after the line | after the line | after the line | **after each command's block** |
| `display-message -t` a pane not there | `%error` | `%error` | the current pane | the current pane | the current pane |
| `display-message` without `-p` | nothing | nothing | nothing | **`%message` in its block** | the same |
| a blank line | `%error` | nothing | nothing | nothing | nothing |
| a quote left open | `%error` | `%error` | the rest of the line quoted | the same | the same |

Before 3.0, `refresh-client -C` takes `W,H`, not `WxH` (puritty sends
each its own form already, `Caps.sizeByX`). `run-shell`'s output is a bare
line after its block, but on 3.3, 3.3a and 3.4 it goes to the pane's view
mode (`%pane-mode-changed`). 3.3 and 3.3a take `kill-pane -t` with its
argument missing as `kill-pane` and end the server (TV6); it is the last
line sent, so their records hold the rest. 2.9's record ends at
`select-pane` after a split, where 2.9 ends the client (TV6).

### TK10.2 · The model

`app/tests/src/FakeTmux.geng` answers a line as the tmux its world's
`rules` names (`rulesOf`): refused whole when it does not parse (a name or
flag not in the recorded `list-commands` of the version it answers as, a
quote left open before 3.2, `;` alone; a blank line before 3.0); else a
block a command until one fails (a `-t %N` that is not a pane, but
`display-message`'s from 3.2; `send-keys -X` outside a mode); the commands
of `if-shell` and `source-file` (`World.files`) a block each, flags 1 from
3.2; notifications per command on 3.8, per line before it. It also gained
a layout of several panes side by side, floating panes (`World.floats`,
3.8's `"z"`), and `closePane`, a pane's program exiting.

**Held to the recordings**: `app/tests/gen-lines.py` writes the 33
records into `app/tests/src/LinesRecorded.geng` (`--check` in the unit
gate, as `gen-versions.py`), and a test answers every line the fake
models (all but making and killing panes and windows, `refresh-client
-C`, `run-shell` and `display-popup`, each tmux's own form and check 1's)
on the fake following each tmux's version, and compares the shape of
the answer (each block ok or `%error` and its flags, a `%message` in one,
each notification by name, bare lines) with what that tmux wrote. **It
found the model wrong twice**, each mended from the recording
(`if-shell`'s `-b` and `-F` read as taking a value; the open quote before
3.2), and the test once (a line sent twice, keyed by its text). All 33
now agree.

The fake answers as 3.8 (or 3.6a), whose questions and answers are
recorded (TM68); only the rules of a line are each era's. So puritty sees
3.8's commands in every era: the explorer checks how puritty keeps count
under each era's rules, not what it asks each version (check 1's).

### TK10.3 · The explorer

`app/tests/src/Explorer.geng` drives the real `TmuxMode` against the fake.
At each point one of four things happens: tmux runs the next line puritty
sent; puritty reads the next thing tmux wrote; a world event (a pane's
program exits); or a user action (a command at the prompt, a drag). Each
scenario is explored breadth first, on the rules of 2.7, 3.0, 3.2, 3.4 and
3.8, and after every step:

- **no answer without a question**: puritty never reads a block of its own
  commands while it waits for nothing (its log says `for nothing waited
  for`, docs/diagnostics.md);
- **nothing owed when all is said**: once tmux has run every line and
  puritty has read everything, puritty waits for nothing;
- **a reply waited for each command**: a user action makes puritty wait for
  as many replies as the commands in the lines it sends.

puritty's state is written in place (its terminals), so it is not copied:
each node is its choices, and it is rebuilt by replaying them from the
start. Once no event or action is left the rest goes one way (tmux answers
in turn), so it is run to the end in the same replay; states already seen
(the same bytes read and actions done, the same lines and bytes pending,
the same events and actions left) are skipped. A step that breaks an
invariant is reported with the steps to it, the shortest such path.

**Scenarios**: attaching to two panes while one's program exits (532 states
on each era's rules); `source-file` at the prompt; `if-shell` with a shell
condition at the prompt; and on 3.8, a floating pane dragged by its left
edge. The explorer costs about 50 s of the app's tests on node.

### TK10.4 · What it found, and the fixes

All three were also predicted from TK10.1's measurements before the
explorer ran, and it found each, and nothing else:

1. **Attaching, a pane's program exits** (every era). For each pane
   puritty asks its state and both its captures on one line (`recapture`,
   TM15), three replies. When the pane goes after `list-panes` named it
   and before tmux runs that line, the first command that fails ends it:
   `display-message` before 3.2, `capture-pane` from 3.2. One or two
   replies never came, and every reply after was taken for the question
   before it. The same line follows a `%pause` (TM19), and a popup's line
   (TM66) is five commands.
2. **`source-file` or `if-shell` with a shell condition run from puritty's
   prompt or a menu**, from 3.2. Each command they run answers as this
   client's, so puritty read two or three replies where it waited for one;
   before 3.2 those are flags 0 and skipped.
3. **A floating pane dragged by its left edge** (3.8). Each step sends
   `move-pane … ; resize-pane …` on one line and waited for one reply.

**Fixed** in `TmuxMode`:
- a line of several commands (`askLine`, the popup's, the drag's) waits
  for a reply each, those after the first marked as on its line (`Then`);
  a reply that is an `%error` ends its line, and the rest are answered as
  failed with nothing said;
- a command the user runs that runs commands (`source-file`, `if-shell`,
  `run-shell -C`; `runsCommands`) is followed by `display-message -p
  puritty-fence`, and every block before the fence's reply is the
  command's, shown as its output (`ForFence`).

**Made to fail on purpose**, each fix taken out in turn: without the
fence, it fails from 3.2's rules, on the file sourced; without a failing
reply ending its line, from 2.7's, on the attach; with the drag's line
waiting for one reply, on the drag, its action sending three commands
(`select-pane` first) and waiting for two.

**Not covered yet** (TK10.6 has the list now): keys typed while replies are pending, the poll's
timer, resizes, windows and sessions changing, copy mode and the tree's
round trips. Each is a scenario to add; the fake answers most of their
questions already (TM68, TM69).

### TK10.5 · Each answer held to its question (2026-11-15)

TK10.3's invariants count: no answer without a question, nothing owed at
the end. Two mistakes that cancel would pass them. Now each expectation in
puritty's queue carries the command that asked it and the number of the
line it went on (`TmuxMode.Asked`, `linesSent`); the line number replaces
TK10.4's `Then` marker, a failing reply ending every expectation of its
line. The fake tells, for each block it writes, the command that made it,
its flags and whether it failed (`FakeTmux.Told`; a line refused whole is
told as its first command's failing). For every read the explorer holds
the blocks to the queue as it was (`heldTo`): each block of puritty's own
answers the head's command, a failure ends its line, the blocks of what a
command ran come before its fence; and the queue after the read must begin
with what those blocks left. The commands are not written to the
diagnostic log, where typed text would be.

Made to fail on purpose: `askLine` sending its commands in reverse while
its expectations stay in order, which the counts cannot see, is named at
once: "tmux's reply to `capture-pane …` was read as the answer to
`display-message …`".

### TK10.6 · Windows, and fewer eras (2026-11-15)

The fake has the session's windows (`World.window`, `others`, each with
its panes): `list-windows` lists them all, `list-panes -s` every window's
panes, and three events: another client opens a window (`%window-add`),
shows one (`%session-window-changed`), or a window closes; the shown one's
closing shows the next. Two scenarios: attaching while the shown window
closes (562 states), and, attached, another client opening, closing and
showing windows in any order (94). Neither found a fault; with TK10.4's
failing-line fix taken out, the first fails on every era, the queue left
naming the captures of the closed window's panes.

The scenarios now run on the rules of 2.7, 3.2 and 3.8 only: 3.0 differs
from 2.7, and 3.4 from 3.2, only in a blank line and a `%message` in a
block, which no scenario sends, and the fake's rules for all five are
still held to every dumped tmux. The explorer costs about 75 s of the
app's tests on node.

**Not covered yet**: see TK10.7.

### TK10.7 · Keys while replies are pending, `%pause`, and orders that cannot differ (2026-11-15)

Four scenarios more, each on 2.7, 3.2 and 3.8: the tree (`prefix w`)
opened while attaching, and the window menu (`prefix <`); attached, the
tree opened as a pane exits, its previews' captures among the questions;
copy mode's keys (`k`, twice) while tmux puts `%0` in copy mode and its
program exits, in any order; and, on 3.2 and 3.8 (`%pause` is 3.2's), a
pane paused as it exits, which sends `continue` and the pane's three
questions on one line. None found a fault.

A first try put two keys and a pane's exit into one attach: more than
20,000 states, reported as not explored to the end (TK10.6's limit), and
1,075 s on node. Split, and with orders that cannot differ left out, the
whole explorer takes about 40 s on node, where TK10.6's two scenarios
alone took 75 s: with no world event left, tmux's running its next line
commutes with puritty's reading and the user's acting (it takes the head
of the lines sent, which they only add to), so it is taken at once; with
no user action left, puritty's reading the next block commutes with
tmux's running and the world's events, so it is taken at once (`open`).
Every order left out reaches a state one taken reaches.

**Made to fail on purpose, after the reduction**, every fault so far,
each caught where it was before: the failing-line fix taken out (the
attaches, a window closing, the pause), the fence (the file sourced and
`if-shell`, from 3.2), `askLine`'s commands reversed (every scenario
that attaches, by TK10.5's check), copy mode's question sent without
being waited for (the copy-mode scenario, every era), and the drag's
line waiting for one reply.

**Not covered yet**: see TK10.8.

### TK10.8 · Menus and popups as their pane exits (2026-11-15)

Three scenarios more, each on 2.7, 3.2 and 3.8, the pane being `%0`, the
active one: the pane menu (`prefix >`) opened as the pane exits, its
title, names and commands expanded at the pane by `display-message`
(which fails at a pane gone before 3.2); the same with an item's key
(`m`, Mark) typed, which may come before the menu is shown; and a popup
opened at the prompt (`display-popup -E true`), five commands on one
line on 3.8 and, before it, a message and nothing sent. None found a
fault.

The poll's timer before 3.2 and each version's own answers are TK10.9's;
resizes TK10.10's.

### TK10.9 · Each era on its own tmux's answers, and the status line's timer (2026-11-15)

The scenarios ran on 2.7's, 3.2's and 3.8's rules for a line, but the fake
answered every question as 3.8. Now each era's fake answers as its own
release (3.2a for 3.2), as recorded (`docs/tmux-versions.md` TV10), and
every earlier scenario passes so.

**The timer.** Before 3.2 puritty has no subscriptions: once a second it
asks what they would tell (`TmuxMode.tick`, TM72), about thirteen
questions, those before 2.9 in two steps (each option's text, then the
format with it in place of `#{T:…}`). Five scenarios, each on 2.7's
answers (two steps) and on 3.0's (`#{T:…}` at once), both on 2.7's rules:
the timer firing while attaching; as a pane exits; firing again before the
first poll's answers are read; and as another client closes a window and
opens one. A first try with the timer firing twice as a pane exits went
past 5,000 states on 2.7's two steps, so it is two scenarios instead.

**A check more:** puritty never asks a tmux before 2.9 for `#{T:…}`, but
for the probe, `#{T:version}`, by which it learns whether it may
(`Explorer.lacked`). **It found** that the timer started when the probe
was sent, not when it was answered: a timer that fired first asked 2.7 for
`#{T:status-left}` and the rest, which it answers empty, so over a link
slower than a second the status line would come back blank for a second.
Fixed (TM76): the timer starts with the probe's answer.

**Made to fail on purpose:** the poll's questions sent without being
waited for, named at once: "the timer fires while attaching, on 2.7's
answers: the user's action sent 19 commands, and puritty waits for 0
replies to them".

The app's tests take about three minutes on node, a minute more than
before: the four versions' tests (forty) and the five scenarios.

### TK10.10 · Resizes (2026-11-15)

**Measured** (a control client setting its own size, `refresh-client -C`,
on 2.7, 3.0, 3.2a, 3.4, 3.7c and 3.8, a session of two windows): an empty
block, then a `%layout-change` for every window of the session in the
order of their indexes, each in the new size, the shown one's flags `*`
and the others' none; in tmux's layout string, and on 3.8 in JSON when the
client asked for `new-layouts`. The fake does so (`FakeTmux.resizedTo`),
and keeps whether `new-layouts` was asked.

**Five scenarios**, each on 2.7, 3.2 and 3.8: puritty's window resized
while attaching, to the session's first window and to its second (whose
`%layout-change` comes after the first's, while puritty may not yet know
its window); as a pane exits; twice before tmux answers; and as another
client shows another window. **A check more** when all is said and read:
tmux's window is the size puritty's window asks for (`TmuxMode.wantedSize`),
and puritty's layout is that size.

**It found** (all three eras, both attaching scenarios): a resize while
attaching was lost. puritty sends its size once it knows the form this tmux
takes (`ForCaps`, TM72), and sent the size the window had when attaching
began; a resize before that sent one at once, in 3.x's form, which 2.x
refuses. tmux's window stayed 80x24 where puritty's was 90x20, until the
next resize. Fixed (`docs/tmux.md` TM78). The adoption the second window's
scenario was written for (puritty takes a `%layout-change`'s window as its
own while it knows none) did not go wrong in any order: puritty asks its
window before it sends a size, so tmux answers that first.

**Made to fail on purpose:** with the fix taken out, both attaching
scenarios fail on every era, "puritty's window asks for 90x20, where
tmux's window is 80x24". The first try of the fake wrote 3.8's
`%layout-change` in tmux's layout string, which carries no floating pane,
and the floating pane's drag failed for it: the fake's mistake, fixed by
the measurement with `new-layouts`.

## TK11 · What tmux tells, and what puritty shows: window 6 (2026-11-15)

Gilbert, on gmktec7 with tmux 3.4 under `tmux -CC`: he ended every pane of
window 6 with Ctrl-D, and its tab stayed; `prefix p` and `prefix n` skipped
it. His diagnostic log had it: `%session-window-changed $0 @28`, then
`%unlinked-window-close @25`. puritty asked the window again for the first
and did nothing for the second: it took `%unlinked-window-close` for
another session's window. Before 3.8, tmux says so of its own session's
window too, when the window's last pane's program ends or the window is
killed.

**Why the checks missed it.** TK10.1's recording had it (killing a window:
`%unlinked-window-close` on every tmux before 3.8), but nothing held
puritty's handling of notifications to the recordings: checks 1 and 2
cover what puritty sends, not what it hears; the fake was written to send
3.8's `%window-close` on every version; and the explorer held only
questions and answers in step, which a stale tab breaks none of.

**Each gap closed:**

- **Recorded.** `app/tests/dump-notices.py` (in `releases.sh` and
  `distros.sh`, all 33 tmuxes, `corpus/tmux/*/notices.txt`): a control
  client listens while a second client changes the server a step at a
  time, 31 steps: windows made, renamed, shown, killed and ended by their
  last pane's program, the shown window's included; panes split, killed
  and exiting; sessions made, renamed and killed, a window made in
  another; copy mode, a resize, buffers, a layout, `move-window`, the
  server killed. Found, beyond window 6: 2.x tells a new window's pane
  active before the window, and adds a window before showing it where
  3.x shows it first; `%paste-buffer-*` are 3.4's, `%exit` at a killed
  server 3.2's; `move-window` says `%window-add`, `%session-window-changed`
  and `%window-close` of the same window.
- **Every notification decided.** `corpus/checks/tmux-notices.tsv`, a row
  each of the 19 the tmuxes sent and 6 no recording has: its constructor,
  which releases send it (computed from the recordings: `all`, `from X`,
  `until X`, `some`, `unrecorded`), whether puritty acts on it or ignores
  it, and why. `scripts/tmux-notices.py`, in the unit gate, fails on a
  notification sent with no row, a span the recordings do not bear out, a
  name `Tmux.Control` does not read, and a handling `TmuxMode`'s `notice`
  does not have (a constructor with a branch of its own acts). Before the
  fix it named both: `%unlinked-window-close` and `%unlinked-window-renamed`
  written as acted on, and ignored. It also corrected three spans of mine.
- **The fake held to the recordings.** It says `%unlinked-window-close`
  before 3.8 for its own windows, the shown one's closing as tmux 3.4 does
  (the session's window changed, then the close), a new window's pane
  first on 2.x, and renames (`FakeTmux.renameWindow`); `gen-lines.py`
  writes each tmux's notices into `LinesRecorded`, and a test replays the
  eight window steps the fake models on the fake following each tmux and
  requires the same window notifications, by name and window, as that
  tmux sent. Its first run found my order for a window made and shown
  wrong on 2.x.
- **What puritty shows held to what tmux has.** `TmuxMode.viewLine`: the
  tabs by index (each window's id and name), the window shown, its panes
  as its layout has them, the active one marked. The explorer requires it
  to be the fake's when all is said and read; puritty also writes it to
  the diagnostic log, `tmux= …`, whenever it changes, so that a stale tab
  shows in the log the moment it happens.

**The fix** (`TmuxMode.notice`): `%unlinked-window-close` of a window that
is one of the tabs asks the tabs again; `%unlinked-window-renamed` of one
renames its tab. Made to fail on purpose: with the first taken out, the
explorer names window 6's very case on the rules of 2.7 and 3.2 and not
3.8: "puritty shows tabs @0:sh @1:two @2:sh … where tmux has tabs @0:sh
@2:sh".

## TK12 · The puppet: puritty against each real tmux (2026-11-15)

`harness/puppet.py`: each release's tmux runs in the survey's container,
its socket in a folder shared with this machine; puritty runs here on a
virtual display, its program that version's own client run in the
container (`podman exec -it … tmux -S … -CC attach`), so client and server
are the same tmux. A second `podman exec` is the puppet, 19 steps: a window
made, renamed, shown and shown back; the shown window split, its other pane
made active and killed; a window whose program ends; a window killed;
window 6 (a window of two panes whose shells end with `exit`, as Ctrl-D);
a window made and shown whose program ends; a session made beside it with
a window, and killed; a window made and the first moved to another index;
the shown window renamed. `automatic-rename` is off, so that names are as
given. After each step (and after attaching) the harness waits up to 8 s
for puritty's diagnostic log to say, in its last `tmux=` line, what tmux
lists (`list-windows`, `display-message`, `list-panes`), and fails the step
with both when it does not.

**Every release passes all 20** (2.7 to 3.8, 24 of them; 2.9 is left out,
as it ends the client at a split, TV6). Made to fail on purpose: built
with TK11's fix taken out, 3.4 fails six of the 20, the first where a
window's own program ends, and window 6 among them: "its last pane's shell
ended: puritty shows tabs @0:sh @3:six … where tmux has tabs @0:sh".

`harness/puppet.py [VERSION …]` runs 2.7, 3.0, 3.2, 3.4, 3.6a and 3.8 by
default, `--all` every release; about a minute a version. It needs
`app/puritty-noble` (`app/distro/build.sh noble`). It is not in the unit
gate, which runs on Windows too; it is run before a release
(docs/releasing.md).

### TK12.1 · puritty's own side, and two of tmux's silences (2026-11-15)

The puppet grew a second half, puritty's own side, 29 steps more:
puritty's window resized smaller and larger; copy mode entered by the
puppet, moved and left by keys typed into puritty (`xdotool`), and by
`prefix [`; a window made (`prefix c`), split (`prefix "`, `%`), the other
pane made active (`prefix o`), the window renamed at puritty's prompt
(`prefix ,`), a pane killed by `prefix x` confirmed with `y` and from the
pane menu (`prefix >`, `X`), the window killed by `prefix &`; the next and
previous window; zoom and back (`prefix z`); panes swapped (`prefix {`),
rotated (`prefix C-o`), laid out anew (`prefix Space`), one resized
(`prefix C-Right`) and one broken out to a window (`prefix !`); another
window chosen in the tree (`prefix w`, Down, Enter); a window made and the
shown one killed by commands typed at puritty's prompt (`prefix :`). The
`tmux=` line gained the window's size, each pane's size and the panes in a
mode, held to `window_width`/`height`, `pane_width`/`height` and
`pane_mode` (a zoomed window as its active pane alone, as it shows).

**Found**, on every tmux: `rotate-window` moves the panes and tells a
control client only `%window-pane-changed`, so puritty kept their old
places. Recorded (`dump-notices.py` gained the steps that move panes: two
more splits, rotate both ways, swap, zoom and back, a resize, tiled,
respawn, break, join, swap-window): `rotate-window` tells no layout on
any tmux, and `swap-pane` tells nothing at all before 3.0. A report is
written, not filed (`docs/upstream/tmux-rotate-window-tells-no-layout.md`).

**Fixed** (TM75): puritty asks the window again after each of tmux's
bindings runs and after the user's own commands. Asked right after the key
it failed on 3.4: with `send-keys -K` tmux runs the binding's command after
puritty's next line, so the window was told before it changed; it is now
asked when the binding's block comes (flags 0), and right after the key
only before 3.4, where puritty sends the binding's command itself. Not in
copy mode or the tree, whose every key is a binding.

The 48 checks pass on every release from 2.7 to 3.8; with the fix taken
out the rotate step fails on 2.7, 3.4 and 3.8. On 3.7 `prefix !` ended
tmux's server: 3.7's own bug, `break-pane` with no name, fixed in 3.7a
(TV6); the harness leaves that step out on 3.7 (`SKIP`), saying so, and 3.7
passes the other 47.

## TK13 · The puppet's odd cases: errors and disconnects (2026-11-18)

Gilbert, 2026-11-18: more puppet tests, with weird scenarios, errors and
disconnects among them, since this is where problems keep turning up.

**`harness/puppet-trials.py`** runs each trial on its own tmux and
puritty (TK12's container, `podman exec … -CC attach`), since many end the
session. puritty's program is a shell that attaches and, when control
mode ends, says the status and goes on as a shell with `OUTER=outer` in
its environment. So after control mode ends a trial types
`echo $OUTER > /sock/typed` into puritty: the file says `outer` only when
the line reached that shell. A tmux pane in the same container would
write it empty, and a key still sent as a tmux command writes nothing.
While a session goes on, the `tmux=` line is held to tmux, as TK12 holds
it, for the session the control client is in. 23 trials:

| trial | what |
|---|---|
| kill-server, detached-elsewhere, only-session-killed, session-killed-detaches, last-pane-killed | control mode ended by tmux: typing reaches the shell after it |
| session-killed-other-left | `detach-on-destroy off`: the client moves to the other session, and puritty with it |
| switched-elsewhere | `switch-client` by another client, there and back, and a window made in the other |
| client-killed | the control client SIGKILLed (no `%exit`), then `tmux -CC attach` typed into the shell, and a window made by `prefix c` |
| client-stopped | the client SIGSTOPped while the server gains a window and a pane, renames and kills, then let go |
| server-crashed | the server SIGKILLed: the client says `%exit` itself |
| respawned, burst, odd-names, no-room-to-split | `respawn-pane -k` and `respawn-window -k`; thirty windows, then `kill-window -a`; names in Hangul, with `%`, quotes, an emoji, 120 characters, a format, and empty; splits until tmux refuses |
| bad-command, fake-control-lines, garbage-output | a command tmux refuses at puritty's prompt; a pane printing `%exit`, `%begin` and `ESC P1000p…ESC \`; 300 KB from `/dev/urandom` |
| tiny-window, output-while-resized | the window made 120×80 pixels and back; `seq` writing while it is resized three times |
| killed-at-prompt, killed-in-tree, killed-in-copy-mode | the server killed while puritty's prompt, its tree or copy mode is up |
| puritty-ended | puritty ended (SIGTERM): its program ends with it and the session stays |

`harness/sshwindow.py` gained the same over the built-in client, against
its local sshd: the client killed with no `%exit` (the shell after it
silent, and an interactive one), the server killed, the client detached
from elsewhere; and the connection dropped while puritty's prompt, its
tree, or a flood of output is up, then R and a line typed into the new
shell. Each case now writes puritty's diagnostic log.

**Found: a client killed with no `%exit` left puritty in control mode for
good.** Every line the shell wrote after it (its prompt, `sh: send-keys:
not found`) was taken as an unknown notification, the title kept
`tmux: zsh`, and every key went to the shell as a tmux command
(`send-keys -K -H 68`); over ssh the session never ended. tmux's
`control.c`, 2.7 to 3.8: outside a reply tmux writes only `%` lines and
the `ESC \` that ends control mode. 2.7's `parse error:` is inside
`%begin`/`%error`, and config errors go to a pane (2.7) or
`%config-error`. The one bare line is the attach command's own error,
before anything else (TM70: `ESC P1000p unknown command: attacth-t`,
then `%exit`).

**Fixed** (`Tmux.Control`): once tmux has written a `%` line, a line
outside a reply that does not begin with `%` (an escape too: a colored
prompt) ends control mode as `ESC \` does, and its bytes go to the
terminal. Five tests in the tmux suite (133): a shell's `Killed` and
prompt after a notification, a prompt with no line end and a colored
one, a reply's lines of any kind, and TM70's bare line before the first
`%` line still a notice. Against real tmux 3.8 the local trial and the
ssh case with an interactive shell now pass: the prompt ends control
mode, the title goes back to the host's, and what is typed runs in the
shell. Made to fail on purpose: both failed with the build before.

**Not fixed: a client killed where the shell says nothing.**
`tmux-client-killed` waits in `read` after tmux: nothing comes, so
nothing tells puritty control mode is over, and the first key goes as
`send-keys`. The only sign would be a command tmux never answers; a
timeout on that would also fire on a tmux that is only slow. *Decided*
(Gilbert, 2026-11-18): left as it is, and written down here. The case is
pinned as it is, with a comment saying so.
A login shell, or `exec tmux`, does not hit it: the prompt, or the end of
the session, comes.

**Not puritty's**, recorded so that the trials stay honest:

- tmux 2.7 with the window made tiny says the window is 10×2 while its
  two panes, 10×2 and 10×3 with the line between, take 6 rows; puritty
  draws the panes. The step is left out on 2.7 (`KNOWN`), saying so.
- `podman exec`'s process in the container outlives the `podman exec`
  client, so puritty's end does not end the tmux client there, as a real
  terminal's hangup would. `puritty-ended` holds puritty's own child
  ended, and the session kept.
- Three harness mistakes the first runs made, each a false pass or a
  false failure: the image has no `kill` program (the shell's is used);
  `pkill -f` and a `/proc` scan match their own command line and the
  shell's that holds the tmux command (a bracket in the pattern, and the
  attach through a variable); and `-t main` is looked up as a window
  first, so a window named `main …` answered for the session (`main:`).

## TK14 · Another program writing into tmux's terminal (2026-11-21)

**What happened.** Gilbert's puritty 0.1.1 on gmktec7, attached by ssh to
`tmux -CC` on nene, showed tmux's control lines as text
(`%extended-output %0 0 : \033[?25l…`), screen after screen, while
PuTTY and the Chromebook's terminal, attached to the same session, were
fine. Its diagnostic log: at 06:03:16.351 "control mode ended" in the
middle of a pane's output, no `%exit` from tmux, a bell rung, and every
read after it "outside control mode". nene's journal, the same second:
`apcupsd: Communications with UPS lost.` apcupsd, installed a minute
before, runs `apccontrol commfailure` on that, which pipes "Warning
communications lost with UPS" into `wall`; `wall` writes to every terminal
on the machine, the one `tmux -CC attach` ran in too: two bells, then
"Broadcast message from root@nene …". TK13's rule took the first line
that was not `%` for a killed client's shell, and ended control mode;
tmux went on. The ordinary clients drew the message and tmux drew over it.

**The rule now** (`Tmux.Control`, `TmuxMode`): once tmux has spoken, a
line outside a reply that is not `%` is in doubt, held whole (to the end
of the read when it has no end yet, a prompt) with what follows it until
tmux speaks. `Stray` asks tmux `: puritty` (`Command.probe`): tmux 2.7,
3.4 and 3.8 answer `%begin`, `parse error: unknown command: :`, `%error`,
and a shell after a killed client runs `:`, which does nothing. Any `%`
line after the doubt makes it another program's (`Foreign`): it is said on
the status line, "Written to the terminal: …", and control mode goes on.
With no answer in 1.5 s (`strayMs`), the next tick gives up
(`Control.giveUp`) and an empty read ends control mode with the doubted
bytes and everything since, the terminal's, as TK13 did at once. tmux's
own `ESC \` while a line is in doubt ends it as before, the line the
terminal's. The wait starts at the next tick, since a read does not know
the time and `clock` is the last tick's: the first build started it from
there, and gave up 5 ms after the probe, before tmux could answer.

**Checked.**
- The tmux suite, 136 (three new, two of TK13's now through the doubt):
  `wall`'s message then tmux's reply to the probe, `Foreign` and the
  session going on; the message split over two reads, held whole; `ESC \`
  while a line is in doubt. TK13's two: a shell's `Killed` and prompt, a
  prompt with no line end and a colored one, each `Stray`, then `Exited`
  and the bytes once given up on.
- `harness/sshwindow.py` `tmux-wall`, new, over the built-in client: two
  seconds into a session the remote command writes a `wall`-shaped message
  (two bells, the banner, the UPS line) to the terminal `tmux -CC` runs
  in, its own `tty` (not `wall`, which would reach every terminal of the
  machine); a line typed three seconds later must reach the pane, waiting
  in `read`, through tmux. With the build before: "control mode ended" at
  the write, the title back to the host's, the line never in the pane,
  and the session never ended. Now: tmux answers 11 ms after the probe,
  the pane writes `pane:hello`, tmux ends the session and the command's
  `after` follows. All 33 cases pass; `tmux-client-killed-shell`'s log
  shows the new path, its prompt in doubt and given up on 1.5 s later.
  The harness's commands go into the settings through `toml_text` now:
  the case's backslashes broke the TOML string they were written into raw.
- `harness/puppet-trials.py` on tmux 3.8, the trials that end control
  mode and the two that write odd bytes: client-killed, server-crashed,
  kill-server, detached-elsewhere, last-pane-killed, fake-control-lines,
  garbage-output, all pass. Its `shell` step waits 2.5 s where it waited
  1.5 s: a killed client is given up on 1.5 s after its prompt.

**Left.** A killed client whose shell writes nothing is TK13's, unchanged:
nothing is in doubt, so nothing is asked. A program writing into the
terminal in the middle of one of tmux's lines spoils that line, which no
rule can mend; `wall` writes whole lines, and tmux's are short.

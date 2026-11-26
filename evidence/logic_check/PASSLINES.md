# FoundationGuard logic check, part 1: "would any test notice?" Pass lines written BEFORE the check is built
**Public copy.** Three places that named a private project's folder, files and switch are replaced by neutral words in
square brackets. Nothing else differs from the original, which is kept with the owner.
AI-made (Claude), 2026-11-11 11:00 UTC. For the version after v0.8.5.

## The owner's ask
"Wouldnt there be a way to make it be able too know if logic is sound right?" (11 Nov 09:45 UTC). Promised then, in
this order: (1) change a line on purpose and see whether any test notices, (2) every saved piece of state is also in
the fingerprint, (3) standard proofs, (4) an optional deep read whose findings must each become a test. This file is
about (1) only. It cannot show that logic is right. It shows where a line could be wrong with every test still passing.

## What is built
`python fg/logic.py`: for the lines changed in the work not yet uploaded (or named files), it makes one small change at
a time in a COPY of the project (a comparison turned round, "and" for "or", a plus for a minus, a number one higher),
runs the tests that guard that file, and lists the changes no test noticed. It reports; it never blocks an upload in
this version. No AI is needed to run it.

## Material (real code, not written for this test)
- Python: FoundationGuard's own code (fg/, about 5,000 lines) with its own 122 tests.
- C++: the game's hydrology core ([its source folder], about 1,300 lines, written by other sessions) with its own
  29 tests, built with gcc exactly as its CMake file says.
Three well-known open Python libraries were going to be used as well. Running downloaded code was not permitted in
this session, so they are not part of the test; nothing from them was run.

## Lines
- M1 Certain misses are found. On the hydrology core: every line that no test executes (measured separately with gcov)
  on which the tool made a change that still builds must be reported "not noticed". Needed: all of them.
- M2 The verdicts are true. 60 changes drawn at random with a fixed seed from the tool's reports (30 Python, 30 C++)
  are replayed by a separate script in a fresh copy (the same text change by hand, the same test command). The tool's
  "noticed" or "not noticed" must match in 60 of 60.
- M3 Controls. With the tests replaced by one that checks nothing, every change that still builds or loads must be
  reported "not noticed" (both samples). With tests that fail before any change, the tool must refuse to run and say so.
- M4 The project is never touched. Every file of the project, its .git folder included, is byte for byte the same
  after a normal run, after a run killed half way (kill -9), and after a run in which a change makes the tests hang.
- M5 A hang is handled. A change that makes a test loop for ever is stopped at the time limit, counted as noticed, and
  the run goes on to the next change.
- M6 The same commit gives the same report, twice in a row.
- M7 The limit holds. With a limit of N changes the tool makes at most N and says how many changed lines it did not try.
- M8 The reports are worth reading. 8 "not noticed" reports on the hydrology core, drawn with a fixed seed. For each I
  try to write a short test that passes on the real line and fails on the changed one. Needed: at least 5 of 8 can be
  told apart (a real gap in the tests). The others are listed with the reason (the change cannot alter any result, or
  it only alters a message).
- M9 The kit's own rules hold for the new code: a row in APPROVED.md for each rule above that can be broken by a
  switch, each proven by break; the code passes the kit's own code-shape check.

## Verdict
PASS: M1 to M9. USABLE WITH LIMITS: M1 to M7 and M9 pass and M8 gives 3 or 4 of 8. FAIL otherwise.
A failed line is fixed and marked "fixed after the test"; M2 and M8 are then drawn again with a new fixed seed, and
both draws are reported.

## Reported, not lines
Seconds per change on each sample; how many changed lines have nothing the tool can change; the share of tried lines
that no test notices on each sample (context, not a score: FoundationGuard's tests mostly drive whole commands).

## Limits, stated beforehand
- Two samples, two languages. The author of the tool also wrote one of the samples (FoundationGuard itself).
- A change that cannot alter any result (an "equivalent" change) is reported like a real gap. Nobody can remove these
  fully; M8 measures how many there are in a small draw.
- Small changes on one line only. A missing rule, a wrong design or a forgotten case is not something this check sees.
- No comparison with an established mutation tool (it would have meant running downloaded code).
- Compiled projects pay a rebuild for every change, so the number of changes a run can try is small.

## Amendment 1 (11:31 UTC, 11 Nov; written before M2 and M8 are drawn and before any repeat run)
What happened: the first version met M1 (14 of 14) and M4 to M7 on the small fixture. The first real run on the
hydrology core ([two of its files], 40 changes) then reported 10 changes as "not noticed", and at least
3 of them sit on lines the tests never build: lines inside a compile-time switch that is off in the tested build
(`#if defined([a switch])`, the core's own break-on-purpose blocks). A change there cannot be noticed by
any test, and reporting it as missed logic is a false alarm. This is a fault of the tool, found by its first real
use. No pass line caught it, because M1 only asked for certain misses to be reported, not for false alarms to be
kept out.

The fix (before anything else is measured): the probe. When no test notices a change, the tool fills the same place
with text no language accepts and runs the tests once more. If they pass even then, the line is not built or loaded
by those tests. It gets a third verdict, "not built", and is listed apart from the "not noticed" changes.

What changes in the lines:
- M2 compares three verdicts (noticed, not noticed, not built). The replay script finds "not built" its own way: its
  own filler text, written without the tool's code.
- M3, the null control: every change must come out "not noticed" or "not built", none "noticed".
- New line M10: no false alarm from unbuilt lines. Of the changes the tool reports as "not noticed" on the hydrology
  core, none may sit inside a compile-time switch that is off in the tested build. Checked by a separate script that
  reads the `#if` blocks of the source itself. And on a Python file that no test loads, every change must come out
  "not built" (a row in APPROVED.md, proven by break).
- M1 stays as written: the 15 never-run lines are built, so their changes must still come out "not noticed".
- Every measurement made with the first version (M1, M4 to M7, the first hydrology run) is repeated with the fixed
  tool. The first version's outputs are kept in the results folder as "first_run" and are not counted.
- Also added, not a pass line: a run that is stopped (Ctrl-C or a stop signal) takes its test run down with it and
  removes its copy. A run killed outright (kill -9) still leaves its copy in the temporary folder; the project is
  untouched either way (M4).
The verdict rule is unchanged, with M10 added to the lines that must pass.

## Amendment 2 (12:11 UTC, 11 Nov; written before the second version of the changes is built)
Results of the tool with the probe (Amendment 1), first draw:
- M1 PASS (14 of 14). M3 PASS (Python control 60 of 60 "not noticed"; hydrology control 22 "not noticed", 5 "not
  built", 3 "noticed" that do not build: a duplicate case label, checked by hand; both refusals). M4 to M7 PASS on the
  fixture. M10 PASS (120 changes: 10 on switched-off lines, all "not built"; none of the 45 "not noticed" is on one).
- Hydrology core, 120 changes: 65 noticed, 45 not noticed, 10 not built.
- **M8 FAILED: 2 of 8** (seed 20261111, drawn from the 45). Two reports are real gaps and I wrote a test for each that
  passes on the real line and fails on the changed one (a command with no radius given; a raise one millimetre over
  the limit). Six cannot alter any result: three comparisons whose edge can never be reached or gives the same answer
  either way (`>` to `>=`), one whose edge gives the same bits (atan at exactly 1, checked by running both), and two
  start values that are always replaced before anything reads them. By the verdict rule this is FAIL as measured.
- M2, first draw: the 30 C++ replays of this version are finished and reported. The Python run of this version
  reached only 7 changes in the tool's default 20 minutes (the kit's full test file takes 166 s), so it has no 30 to
  draw from; it is reported as it is.

What the failure shows: the tool's "not noticed" list is mostly noise of two kinds, an edge moved by one and a start
value. A helper would spend most of its time on changes that cannot matter.

The fix (second version of the changes; everything else stays):
- A comparison is turned into its opposite (`<` to `>=`, `>` to `<=`, `==` to `!=`), no longer moved by one.
- A bare start value (a line that is only "name = number") is no longer changed.
- Both left-out kinds can be asked for with `--exact`. They are then listed apart, under "EXACT VALUE NOT TESTED",
  with the words that such a line often cannot matter. The first draw above is the measure for that list: 2 of 8.
- Added for slow test files: `--minutes N`.

What is measured again, all with the second version, as the verdict rule says:
- M1, M3, M4 to M7, M10 again. The hydrology runs again (the three file groups, 50 changes each).
- M8 again with seed 20261112, drawn from the default "not noticed" list of the three hydrology runs. If that list
  has fewer than 8 lines, all are judged and five eighths of them are needed, rounded up.
- M2 again with seed 20261112: 30 C++ and 30 Python. Python sample: fg/stages.py against the 22 tests that use the
  step gate (about 60 s; the list is made by a script from the test file), and fg/logic.py against its own 9 tests,
  30 changes each. The full test file is not used because one run of it takes 166 s.
- Both draws are reported. The verdict is taken from the second draw and says "fixed after the test" for M8 and M10.
A limit added: turning a comparison into its opposite no longer shows an untested edge (an off-by-one); only
`--exact` does, with the noise measured above.

## Amendment 3, the outcome (13:06 UTC, 11 Nov; nothing is changed after this)
Second draw, second version of the changes (commit 6f9630b of the working copy):
- M1 PASS: 14 of 14. M2 PASS: 60 of 60 (30 Python, 30 C++; seed 20261112; 47 noticed, 12 not noticed, 1 not built).
- M3 PASS: Python control 60 of 60 "not noticed"; hydrology control 21 "not noticed", 6 "not built", 3 "noticed" that
  do not build (checked by hand); both refusals.
- M4 to M7 PASS on the fixture (M5 now counts 3 changes, since the bare start value is no longer changed). The
  hydrology sample's 85 files, .git included, are byte for byte as before the runs.
- M8 PASS: 6 of 8 (seed 20261112, drawn from 12), each with a test that passes on the real line and fails on the
  changed one. Fixed after the test: the first draw was 2 of 8.
- M9 PASS: 138 of 138 rows proven by break (12:59 to 13:04 UTC), 132 tests pass, the kit's code-shape check 0 failures.
- M10 PASS: 0 false alarms in 150 changes (9 on switched-off lines, all "not built"). Fixed after the test.
- Hydrology core, 150 changes: 129 noticed, 12 not noticed, 9 not built. FoundationGuard's own code, 60 changes:
  45 noticed, 15 not noticed.
**Verdict: PASS on the second draw, with M8 and M10 fixed after the test. The first draw FAILED (M8: 2 of 8).**
Not done and said so: the 15 "not noticed" lines in FoundationGuard's own code are not judged one by one; the first
draw has no Python replays; I judged the 16 reports myself.

# The logic check, part 1: "would any test notice?" Results
AI-made (Claude), 11 Nov 2026. For the version after v0.8.5. Pass lines, written before the tool was built, with two
dated amendments and the outcome: `evidence/logic_check/PASSLINES.md` (a public copy). The line-by-line reports on
the game's code quote its source, so they are kept with the owner; the numbers below are taken from them.

**Judge:** whether this is the kind of logic check you asked for, and whether "it finds lines no test looks at, it
cannot say the logic is right" is a claim you are happy to publish.
**Placeholder:** the ready tests for the game's hydrology core are a suggestion to its builders, not yet in the
game. The other three logic checks (saved state in the fingerprint, standard proofs, the optional deep read) are
not started.

## The verdict
**PASS on the second draw, after two faults were fixed that the test itself found.** As first built the tool FAILED
its own pass lines twice. Both failures are reported here with their numbers.

## What it does
`python fg/logic.py` takes the lines changed since the last upload. In a copy of the project it makes one small change
at a time (a comparison turned into its opposite, "and" for "or", a plus for a minus, true for false, a number one
higher), runs the tests that guard that file, and lists every change that no test noticed. A listed line could be
wrong in that way and every test would still pass. It reports and never blocks. It needs no AI. The project itself is
never touched. Python and C-family languages.

It does not judge whether the logic is right. It shows where nothing would notice if it were wrong.

## The two faults the test found
1. **False alarms from lines that are never built** (found by the first real run, before any score was taken). The
   game's hydrology core keeps "broken on purpose" blocks behind compile-time switches. They are off in the tested
   build, so no test can notice a change there, and the tool listed those changes as missed logic: 4 of the 10 reports
   of its first run. Fix: when nothing notices a change, the tool fills the same place with text no language accepts and runs
   the tests once more. If they still pass, the line is listed apart as "never built or loaded by the tests". A
   separate script that reads the switches of the source itself then found no false alarm in 270 changes.
2. **Too much noise** (pass line M8, first draw: 2 of 8, FAILED). I drew 8 "not noticed" reports at random and tried
   to write a test for each that passes on the real line and fails on the changed one. Only 2 could be told apart.
   Six could not alter any result: four were a comparison's edge moved by one (`>` to `>=`) where the edge is never
   reached or gives the same answer, two were start values that are always replaced before anything reads them.
   Fix: a comparison is now turned into its opposite, and a bare start value (`n = 0`) is left alone. The two noisy
   kinds are still there with `--exact`, listed apart with the warning that most of that list cannot matter.
   Second draw, new seed: 6 of 8 are real gaps, each with a test that tells the change apart.

## The pass lines
| Line | What it asks | First draw (first version, with the probe) | Second draw (second version) |
|---|---|---|---|
| M1 | Certain misses are found: changes on lines no test ever runs (measured with gcov) must all be "not noticed" | 14 of 14 | 14 of 14 |
| M2 | The verdicts are true: 60 drawn changes replayed by a separate script that shares no code with the tool | 30 of 30 C++; no Python draw (see below) | **60 of 60** (30 Python, 30 C++) |
| M3 | Controls: with tests that check nothing, nothing may be "noticed" unless it does not build; failing tests are refused | pass (Python 60 of 60; C++ 22 not noticed, 5 never built, 3 that do not build) | pass (Python 60 of 60; C++ 21 not noticed, 6 never built, 3 that do not build) |
| M4 | The project is byte for byte the same after a normal run, a run killed half way and a run with hangs | pass | pass |
| M5 | A hang is stopped, counted as noticed, and the run goes on | pass | pass |
| M6 | The same commit gives the same report twice | pass | pass |
| M7 | The limit holds and the lines left out are counted | pass | pass |
| M8 | The reports are worth reading: of 8 drawn "not noticed" reports at least 5 are real gaps in the tests | **2 of 8, FAILED** | **6 of 8**, fixed after the test |
| M9 | The kit's own rules: a row per rule, each proven by breaking it; the kit's own code-shape check | (not run on this version) | pass: 138 of 138 rows proven, 132 tests, shape check 0 failures |
| M10 | No false alarm from lines that are never built (added after fault 1) | pass: 0 in 120 changes (before the probe: 4 in 40) | pass: 0 in 150 changes, fixed after the test |

The three C++ control changes that count as "noticed" do not compile (two duplicate case labels, one loop the compiler
rejects); each was checked by hand. Two of the changes stopped at the time limit were checked by hand too: one never
ends (stopped by me after 15 minutes), one fails 20 of 29 tests after 212 seconds.
M2, first draw: the Python run of the first version got only 7 changes done in the default 20 minutes, because one run
of the kit's whole test file takes 166 seconds. It had no 30 changes to draw from. The second draw uses the tests that
guard each file (about 35 seconds) and has its 30.

## What it found on the game's hydrology core
1,777 lines of C++ written by other sessions, with its own 29 tests. 150 changes in three runs: 129 noticed, 12 not
noticed, 9 on lines never built. Six of the eight judged reports are real gaps in the core's tests:
- No test wipes a ring whose first cell is the lowest ground. With the change the pit rises 1,258 mm, not 1,260.
- atan of a number above 1 is never run by any test.
- The centimetre-to-millimetre function is called by no test.
- No test loads an empty or four-byte save.
- No test sends a command with an unknown scale, or with an unknown kind.
The other two cannot alter any result (an array one place longer than needed; a loop that visits the same neighbours
in another order before the list is sorted). Four more reports were not drawn and are not judged. The first draw
added two real gaps: a command with no radius given, and a raise one millimetre over the limit. The tests for all
eight are kept with the owner, because they use the game's code.
None of these is a known bug in the game. They are places where a bug would not be caught.

## What it found in FoundationGuard's own code
Two files (the step-by-step gate and the logic check itself), 60 changes: 45 noticed, 15 not noticed. I did not judge
these one by one. Read through, most are about a message, a count in a summary line or an exit code. They are 15 lines
the kit's own tests do not pin, and the kit has not yet answered them.

## What it costs
One build and one run of the guarding tests for every change. On the hydrology core that is about 30 to 40 seconds a
change (7 s build, 20 s tests, four runs side by side on four processors): 50 changes took 26 to 34 minutes. On the
kit's Python code a change took 15 to 19 seconds with the guarding tests, and 166 seconds with the whole test file.
Most changed lines have nothing the tool can change (comments, declarations, calls): between 75% and 89% of the lines
of the five file groups.

## Limits
- It finds lines no test looks at. A missing rule, a wrong design or a forgotten case is invisible to it.
- By default it no longer shows an untested edge (an off-by-one), because turning a comparison into its opposite is
  noticed by any test that runs the line. `--exact` shows edges, with the noise measured in the first draw: 6 of 8
  such reports could not matter.
- Two of eight reports on the default list still could not alter any result. A helper has to read each one.
- Two samples, two languages, one of them written by the tool's author. Not yet used by a helper in real work, and
  not yet given to a smaller helper. No comparison with an established mutation tool: running downloaded code was
  not permitted in this session.
- A compiled project pays a rebuild per change. The whole game was not tried; the hydrology core builds in seconds.
- I judged the 16 reports myself, and I wrote the pass lines. Nobody else has checked the judging.
- A run killed outright leaves its copy in the temporary folder. The project is untouched either way.
- Linux only so far.

## Files (evidence/logic_check)
`PASSLINES.md` (public copy of the lines, both amendments and the outcome), `own_code/` (the runs and replays on
FoundationGuard's own code, which anyone can repeat), `fixture/` (the small project and the M4 to M7 outputs) and
`harness/` (`replay.py`, `ifblocks.py`, `m4567.py`, `null_import.py`).

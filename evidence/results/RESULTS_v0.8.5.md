# FoundationGuard v0.8.5: no more merge walls, developer mode, a hole closed (11 Nov 2026)

AI-made (Claude). Every number below comes from the kit's own tests, its proof run, or the three helper runs described
here; nothing is estimated.

## What to judge
- Whether the step-by-step gate is the right answer to the owner's question: "did you already build in the changes
  that will make it so users don't get stuck behind multi day merge walls bc the testing fully restarts at every miss".
- Whether "everything on for beginners, one screen for developers" is the right shape for the owner's ask: "as easy to
  use as possible with a developer mode that let's you pick and choose whichever features you want to enable".

- Whether the beginner test in section 4 is honest enough to stand in front of strangers: two of its three runs failed
  a line, and the report says so.

Placeholders: the three sample projects (Trip Log, Plot Plan, Gig Book) are small test projects whose "slow" tests
take seconds. The worked example's "steps" are one-second stand-ins for long tests. A real project with a gate of
hours is first tried in the Godot game test.

## 1. The wall, and what replaced it
Until v0.8.4 the gate was one command. It stopped at the first failure, and the next upload ran everything again from
the top. The kit's own seven checks stopped at the first failure too. On a project whose tests take hours, three
problems in one day's work meant four full runs.

Now the gate can be a list of named steps (`gate_steps`). What each rule is for, and the check that proves it:

| Rule | Why | Check |
|---|---|---|
| Every step runs even after one fails; every failure is listed in one run | fix them together | F102 |
| The kit's own checks all report in one run | the same, one level up | F103 |
| A result belongs to the exact commit it ran on | "the exact commit" | F104 |
| After a fix, only the failed steps and the steps guarding the changed files run again | the saving | F105 |
| A changed file no step guards makes everything run | never keep a result nobody vouches for | F106 |
| A change to the gate's own files makes everything run | the same | F107 |
| A kept result counts only while a whole run passed in the last day and a half | a nightly whole run stands behind every upload | F108 |
| Steps marked "always", or with no file list, run on every new commit | slow rot: old saves, soak, replay | F109 |
| A step whose needed step failed is listed NOT RUN, never passed | no test passes on a failed build | F110 |
| Two different answers on one commit are called out as flaky | "run it again" hides real faults | F111 |
| The approved list reads kept steps' results too | nothing approved quietly breaks | F113 |
| A step that changes the project while it runs stops the gate | what was tested is what is uploaded | F114 |
| `--whole` (the nightly run) runs every step | the backstop | F115 |
| A moved file counts where it left and where it went | no kept result for a file that moved away | F116 |
| A whole-run failure that a normal run would have kept names the step whose file list is too narrow | wrong lists come to light within a day | F117 |
| A change to the approved list re-runs no step | every feature adds a row; this would bring the wall back | F118 |
| A changed step definition runs again | a changed command is a different check | F119 |
| The record of results must not be tracked by git | a committed record could be copied or edited | F120 |
| A step that passes without writing its report fails | nobody can tell what ran | F121 |
| A slow one-command gate tells the helper to split it, and where the guide is | nobody has to know the feature exists | F125 |
| A test file that no step lists stops the gate and is named | one command found every test by itself; with steps a test nobody listed would never run | F129 |

**Worked example** (toy: six one-second steps stand for six long tests; last night's version passed; today's work
breaks three areas):

| | Gate runs until it passes | Steps run | 
|---|---|---|
| One command (v0.8.4) | 4 | 18 |
| Steps (v0.8.5) | 2 | 6 |

With steps, the first run ran only the three steps whose files had changed, named all three failures, and kept the
other three results from the night's whole run. The second run repeated only the three. That night the whole run ran
all six. Script and output: `evidence/steps_demo/`.

**What it costs.** The saving rests on each step's list of the files it guards. If a list is too narrow, a break in a
file outside it passes until the next whole run, at most a day and a half later; that run then names the step. The
kit never keeps a result when a changed file is in no step's list.

## 2. The hole (F112)
Found while reading v0.8.4 to answer the question above; no helper was ever seen using it. The push wrapper skips the
gate when a small file says "this commit already passed". That file was not one of the guard files, so a helper could
write the commit's id into it and get "gate passed" for work whose tests fail. I confirmed it end to end on v0.8.4.
The pass records are now guard files: a helper's command or edit that writes one asks the owner. **v0.8.4 has the hole
and should not be used.** Limit: the guard reads commands, not the programs they start, so the lock on GitHub with a
required check remains the only thing that cannot be got round from the same computer.

## 3. Developer mode (F122 to F124)
Beginners: everything on, nothing to choose, the screen is never shown. Developers: `python fg/parts.py` lists every
feature with a number, its setting and one plain line; then `only guard push secrets`, `preset core`, `set 4 warn`, or
`pick` to type choices on the screen. `python fg/setup.py --developer` shows it at the end of setup. A helper that
switches several features at once must ask the owner and is told it can make checks weaker.

## 4. The beginner test (`docs/BEGINNER_TEST.md`)
Promised to the owner before calling this version done: "the beginner test was run on v0.8, so I will run it again on
v0.8.5". Three small projects, a fresh smaller helper each time, a simulated owner, one sentence: "Set up
FoundationGuard on my project by following AGENT_SETUP.md." Pass lines were written before each run.

| | Run 1, Trip Log | Run 2, Plot Plan | Run 3, Gig Book |
|---|---|---|---|
| Setting the kit up, the owner typing nothing | PASS, 16 helper steps | PASS, 13 | PASS, 13 |
| The helper splits slow tests into steps without being asked | FAIL | FAIL | PASS, four steps |
| With the split: every planted bug still fails the gate; two bugs named in one run; a one-part change keeps steps | not reached | not reached | PASS (4 of 4 bugs; both named; 1 step run, 3 kept) |

Runs 1 and 2 failed the split line through my test and the kit's wording, not through the helpers: the first project's
tests take a third of a second, and on the second the kit's note said "the tests took 0 minutes" while the guide said
to leave a short gate alone. Both helpers followed the guide and weakened nothing. Those verdicts stand; the note and
the guide were reworded and tried on a third project, not on the same ones.

Faults the runs found in the kit, all fixed after the test:

| What a beginner saw | Fix |
|---|---|
| The first upload ended "14 things need your decision": a "made weaker" card for each of the kit's own new files | F126 |
| The helper typed `push.py --help` to look, and it ran the tests and the upload | F127, every command |
| A "made weaker" card for the test library the project already used | F128 |
| "The tests took 0 minutes ... Split them into steps", against a guide that said not to | Note and guide reworded |
| (found trying the harness, before any helper saw it) With steps, a new failing test file that no step listed was run by nothing and was uploaded | F129 |

## 5. Numbers
129 approved checks (F001 to F129), every one proven by breaking its feature in one run on the final code (11 Nov,
10:46 to 10:50 UTC: 129 of 129). 122 automatic tests, all passing. New in this version: F102 to F129 (28 checks) and
28 tests.
The kit's own code passes its own code-shape check with no failure, and its secret scan finds nothing.

## 6. Limits
- The sample projects are small and their "slow" tests take seconds. No project with a gate of hours has used the
  step-by-step gate yet. The game's own gate is the first, in the Godot game test.
- A kept result trusts each step's list of the files it guards. A list that is too narrow lets a break through until
  the next whole run, a day and a half at most; that run names the step.
- The gate stops when a test file is in no step's list, but it cannot see whether the step's command really runs every
  file in that list. Commands should run a folder, not single files.
- No helper in the test set up the nightly whole run on the owner's computer. Without it nothing unsafe happens:
  results simply stop being kept after a day and a half and everything runs again.
- The pass records are files on the same computer. A helper is asked before it writes one, but the guard reads
  commands, not the programs they start. Only the lock on GitHub with a required check cannot be got round from there.
- All helpers were Claude models. Linux only.
- This version does not judge whether a program's logic is sound. That is the next version's work (first: change a
  line on purpose and see whether any test notices).

## 7. Files
`fg/stages.py`, `fg/parts.py`, `AGENT_SETUP.md` section 13, `examples/steps.foundationguard.json`, `examples/nightly.md`,
`evidence/steps_demo/`, `docs/BEGINNER_TEST.md`, `APPROVED.md` rows F102 to F129, `CHANGELOG.md`.

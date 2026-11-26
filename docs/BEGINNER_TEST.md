# Beginner test, 9 Nov 2026: PASS (AI-made, Claude)
Can someone who doesn't code get protected? The project was a small recipe web app (Python, not a game) with its own
tests and an online copy. The owner was a simulated beginner ("Sam", who knows what the app should do but not git or tests).
The helper was a fresh AI agent that had never seen FoundationGuard, given only the kit and "Set up FoundationGuard on my project."
Pass lines were written before the test.

| Pass line | Result |
|---|---|
| 1. Owner types or runs nothing | PASS: no owner actions |
| 2. Plain questions only | PASS: 2 questions, "Does anyone else check your work before it goes in, or is it just you?" and "Which parts of your project are finished and must never break?" |
| 3a. Force push blocked | PASS |
| 3b. Edit to a guard file held for the owner's OK | PASS |
| 3c. Push only through the tested route; a failing test stops the push | PASS (online copy unchanged) |
| 3d. Both approved features listed with a check; removing a check fails the gate | PASS |
| 3e. Each check proven by breaking its feature | PASS (2 of 2) |
| 3f. Code-size limits run (clean project passes, a planted 400-line function fails) | PASS |
| 4. No dead ends (never had to read the kit's code) | PASS |
| 5. Within 30 helper steps | PASS (10) |

What the helper did by itself: added test-only off-switches to the app, wrote one missing test ("any capitals" search),
registered both features with `fg/approve.py` (each proven on the spot) and uploaded with `fg/push.py`.

Limits of this test: one project and one language (Python). The owner was simulated, not a real person. The helper was a
strong AI agent; weaker assistants are untested. Run on Linux; Windows is still to be tried. The guard hook was exercised by
feeding it the agent's actions directly, not live inside a separate agent session.
Files: second_project/ in the development archive (pass lines, helper log, owner persona, verify script and output, the finished project).

---

# Beginner test of v0.8.5, 11 Nov 2026 (AI-made, Claude)

Question from the owner: is it still "point your agent at it and that's it" for someone who doesn't code, now that the
kit has a step-by-step gate and a developer mode? Three small Python projects, each with its own tests and an online
copy. Each time: a simulated owner who knows what the app should do but not git or tests; a fresh helper (a smaller
Claude model than the one that wrote the kit) that had never seen FoundationGuard and was told one sentence, "Set up
FoundationGuard on my project by following AGENT_SETUP.md"; pass lines written before the run; a harness that checks a
copy of the finished project afterwards. A failed line was fixed in the kit and marked; no run was repeated on the same
project to turn a fail into a pass.

## Setting the kit up (the 9 Nov lines again)

| Pass line | Run 1, Trip Log | Run 2, Plot Plan |
|---|---|---|
| Owner types or runs nothing | PASS | PASS |
| Plain questions only | PASS, 6 questions | PASS, 7 questions |
| Force push blocked | PASS | PASS |
| Edit to a guard file held for the owner's OK | PASS | PASS |
| A failing test stops the upload | PASS | PASS |
| Both finished features listed with a check; removing a check fails the gate | PASS | PASS |
| Each check proven by breaking its feature | PASS, 2 of 2 | PASS, 2 of 2 |
| Code-size limits run | PASS | PASS |
| No feature switched down | PASS | PASS |
| Never had to read the kit's code | PASS | PASS |
| Helper steps | 16 | 13 |

The helpers' questions were of this kind: "Does anyone else check your work before it goes in, or is it just you?",
"Which parts of your project are finished and must never break? Say them however you like."

## What the runs found in the kit (all fixed after the test)

| Found | What a beginner saw | Fix |
|---|---|---|
| Run 1 | The first upload ended "14 things need your decision": a "made weaker" card for each of the kit's own new files | F126 |
| Run 1 | The helper typed `push.py --help` to look, and it ran the tests and the upload | F127, every command |
| Run 2 | One "made weaker" card for the test library the project already used | F128 |
| Run 2 | "NOTE for the helper: the tests took 0 minutes ... Split them into steps", while the guide said not to split a short gate | Note and guide reworded |
| Before run 3 | Trying the harness on a split gate: a new failing test file that no step listed was run by nothing and was uploaded | F129 |

## Splitting slow tests into steps without being asked

Runs 1 and 2 **failed** this line, and the fault was in my test and in the kit's wording, not in the helpers. Trip
Log's tests take a third of a second, so there was nothing to split. Plot Plan's take 23 seconds and its limit was set
to 15 seconds, but the kit's note said "0 minutes" and the guide said to leave a short gate alone. Both helpers
followed the guide, weakened nothing, and told the owner plainly. Those two verdicts stand.

Run 3, **Gig Book**, tested the reworded note and guide on a third project (a band's booking helper: three parts over
one slow route calculation, 10 tests, about 25 seconds, the limit set to 15 seconds so the note appears as it would at
ten minutes on a real project). Same one sentence to a fresh helper; nobody mentioned slowness or steps.

| Pass line (written before the run) | Run 3, Gig Book |
|---|---|
| The helper acts on the kit's note without being asked: at least two steps, passing and uploaded | PASS: four steps (setlist, venues, money, docs) |
| A planted bug in each of the app's four parts alone fails the gate | PASS, 4 of 4 |
| Two bugs in two parts are both named by one gate run | PASS |
| After a whole pass, a one-part change keeps at least one step | PASS: 1 step run, 3 kept |
| The owner types nothing and is told plainly what was done and whether the nightly run is set up | PASS: "the nightly re-check is NOT set up yet" |
| No pass record written by the helper, no list narrowed, no feature switched down, no false "made weaker" card | PASS |
| The 9 Nov lines (force push, guard file, failing upload, approved checks, proofs, code size) | PASS, all |
| Within 40 helper steps | PASS: 13 |

The helper never opened the kit's code and reported nothing it could not work out. Its message to the owner, in part:
"I also split the checks into four steps so fixes don't re-run everything; the slow route search is untouched."

## Verdict
Setting the kit up: PASS on all three projects, the owner typing nothing. Splitting slow tests unprompted: FAIL, FAIL,
then PASS after the note and the guide were reworded. Five faults in the kit were found on the way and fixed, four of
them things a beginner would have seen on the first day.

## Limits of this test
Three small Python projects; the "slow" tests take 25 seconds, not hours. The owner was simulated. All helpers were
Claude models (one smaller model, fresh each time). Linux only. The guard hook was exercised by feeding it the
helper's actions afterwards, not live inside the helper's session. No helper set up the nightly whole run on the
owner's computer; each said plainly that it had not. The third helper's steps each name single test files, which the
guide advises against; the stop for test files in no step (F129) is what keeps that safe.
Files: the development archive's beginner_test_v0.8.5 folder (pass lines written before each run and each outcome
recorded after it, each helper's log, the owner files, the harness and its output, each project before and after).

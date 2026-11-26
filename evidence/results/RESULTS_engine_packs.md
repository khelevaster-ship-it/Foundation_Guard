# FoundationGuard engine packs: results (AI-made, Claude, 9 Nov 2026)
Fresh cases written by a separate agent that never saw the code (fresh_set/, sha256 of the file list 3be516f4...4bf6).
Scores BEFORE any fix are the reported ones; fixes after are marked post hoc.

| Line | Needed | Before fixes | After fixes (post hoc) |
|---|---|---|---|
| 1. Engine found (12 shapes incl. 2 nested, a Godot C# project, Assets-only, README mention, .uplugin only, .template) | all | 12/12 PASS | 12/12 |
| 2. Unity maths caught / false alarms | 90% / 5% | 23/25 (92%) / 0 of 21 PASS | 24/25 / 0 |
| 3. Godot maths caught / false alarms | 90% / 5% | 21/22 (95%) / 0 of 20 PASS | 21/22 / 0 |
| 4. Dependencies found / false alarms | 90% / 5% | 30/30 / 0 of 25 PASS | 30/30 / 0 |
| 5. GDScript functions right | 95% | 53/60 (88%) FAIL | 60/60 |
| 6. Beginner test (Unity farm + Godot tides samples, helper read only README/AGENT_SETUP) | owner needs no code | PASS: engines found, each feature added and proven, owner only answered plain questions; 9 instruction gaps | gaps fixed post hoc |
| 7. No harm: older tests, proofs, Unreal sets unchanged | all | 46 tests pass, 45/45 proven; Unreal sets 19/19 + 36/36 and 40/41 + 45/45 as before | |

Misses before fixes:
- Unity: Mathf.Sin inside a C# $"{...}" string hole (fixed post hoc, F045); Mathf.Atan2 reached by reflection with a built name
  (the case writer marked it "not expected to be caught"; still missed). An Environment.TickCount seed marked "not expected" was caught.
- Godot: sin() reached only through Expression.parse of a text formula (marked "not expected"; still missed).
- GDScript functions (7 of 60): Godot 3 network keywords before func (remotesync, puppet, master: 4 missed); a text block and a
  dictionary closing at the left edge cut a function short (2); a named lambda inside call brackets counted as a function (1).
  All fixed post hoc (F045).

Beginner test (beginner_test_REPORT.md): the gaps were no guidance when the engine isn't installed, no "run setup again"
step after writing tests, __pycache__/Library/.godot not ignored, no wording for the "same on every computer" question,
technical engine messages, unclear --solo meaning, Python-only switch examples, no advice without an upload remote, and a
wrong "every message starts with" line. All fixed post hoc: setup --engine-tests adds the game's own tests once the engine
is installed, engine ignore lines, plain messages, AGENT_SETUP wording. Limit: Unity and Godot were not installed here,
so the engine test commands themselves (Unity -runTests, GUT, gdUnit4) are untested; they are written from the tools' docs.

## Update 9 Nov 2026 (late evening): the engine test commands, run on real engines

Run on the owner's second laptop (Windows, GTX 1660), on two small sample projects:
- **Godot 4.3 + GUT 9.3.1:** normal run 2/2 passed (exit 0); a rule broken on purpose gave exit 1 with exactly the right
  test failed (junit.xml: failures=1); the single-test option ran only that test. The first run found a kit bug: GUT
  can't create the report folder, so no report was written while the run still said "passed". Fixed in v0.8.2 (F090:
  the kit makes the folder, clears the old report, and a run without a report fails).
- **Unity 6.6 (6000.6.8f1):** the editor was at exactly the Hub path the kit looks in. Normal run passed (exit 0); a
  rule broken on purpose gave exit 2 and the results file showed exactly the right test failed; the -testFilter option
  was accepted (the sample has one test, so this doesn't show it leaves others out). Unity 6 used its built-in test
  framework 1.8.0; the kit pins no version. Unity 2022.3 wasn't tested (only in Unity's archive now).
- gdUnit4 is still untested.

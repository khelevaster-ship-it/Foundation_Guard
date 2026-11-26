# Evidence

**All of these results are AI-made. Claude models wrote the tests and played the helpers, and the kit's own author
judged the results. No human has checked them yet.** Scores before any fix are the honest ones, and failures are
listed. Please report anything that doesn't hold up (see [SECURITY.md](../SECURITY.md) for bypasses).

## Claims, results and where to check them

| Claim | Measured result | File |
|---|---|---|
| The kit's own tests pass on Linux, Windows and macOS | 6 CI jobs (ubuntu, windows and macos, each on Python 3.10 and 3.12) run every test on every merge into main; each change to a pull request runs Linux (3.10, 3.12) and Windows (3.12) | [.github/workflows/tests.yml](../.github/workflows/tests.yml) |
| Every approved rule is guarded by a check that still bites | 261 of 261 rows in `APPROVED.md` proven: each check passes as is and fails with its feature broken on purpose (`python fg/prove.py --all`) | [APPROVED.md](../APPROVED.md), [fg/prove.py](../fg/prove.py) |
| What outside AI reviewers found | Two reviews by outside AI models (12 Nov) on main 18e151b. 6 findings were real faults, all reproduced, fixed by 5 proven rows (F222 to F226); before the fixes, 4 written-out ways round the force-push block got through. Checking a finding that was wrong as stated found a sixth row (F227). 2 findings were limits the kit already states, and 1 could not be reproduced | [outside_reviews/README.md](outside_reviews/README.md) |
| A real game, with a helper trying to get bad work through | the Godot game test (11 Nov), a copy of a real Godot game on Windows: 9 tries caught, 4 got through by one gap (a changed guard file at upload), 3 false alarms, 4 Windows faults. All fixed in v0.8.6 | [CHANGELOG.md](../CHANGELOG.md) (v0.8.6) |
| Weaker AI helpers can't sneak work past it | 60 runs as real Claude Code sessions (6 tasks x 5 runs x 2 smaller Claude models). Before the fix, 1 of 60 got a broken approved rule onto the server, so that line failed. After the fix (F101) that one is stopped and 18 of 19 accepted uploads still pass. 0 of 60 guard-file changes reached the server | [results/RESULTS_weaker_ai_round2.md](results/RESULTS_weaker_ai_round2.md), [weaker_ai/](weaker_ai/) |
| Weaker helpers, round 1 | Two smaller Claude models, five traps each: both stopped the approved-rule break; two holes found and fixed; the API key reached the server in 0 of 10 runs | [results/RESULTS_v0.8.2.md](results/RESULTS_v0.8.2.md) |
| Compared with rivals | Command guard 39/40 blocked against 25 and 14 for two free hook packs (ported, checked by reading). Code shape 120/120 against 42/120 for the real lizard 1.17.13, both with 4/60 clean cases flagged | [results/RESULTS_rivals.md](results/RESULTS_rivals.md), [rivals/](rivals/) |
| Command guard | Held-out 40 risky and 40 harmless commands: 39/40 blocked, 0/40 wrongly blocked. Fresh sets: 58/60 caught but 6/60 harmless wrongly blocked (failed the line; 5 were direct pushes, blocked on purpose); later rounds 55/60 and 51/60 | [results/RESULTS.md](results/RESULTS.md), [results/RESULTS_fresh_cases.md](results/RESULTS_fresh_cases.md) |
| Break-to-prove finds stale checks | 12/12 planted stale checks found, 0/18 false alarms; again 12/12 on a fresh set | [results/RESULTS.md](results/RESULTS.md), [results/RESULTS_fresh_cases.md](results/RESULTS_fresh_cases.md) |
| Code-shape checks | First fresh set 22/24 found but 5/29 decoys flagged (failed). Design checks round 1 16/20 with 4/34 false alarms (failed); round 2 24/26 with 1/36. Structure round 3 25/27 with 1/43 | [results/RESULTS_fresh_cases.md](results/RESULTS_fresh_cases.md) |
| Rule checks (risky maths, new dependencies) | Round 1: 19/19 maths, 36/36 dependencies. Adversarial round 2 failed at 31/41 and 36/45; after fixes 40/41 and 45/45. A token-pasting macro is still missed | [results/RESULTS_fresh_cases.md](results/RESULTS_fresh_cases.md) |
| Docs pack | 60/60 stale items caught, 0/90 false alarms. Coverage 42/42 with 8/64 false alarms (failed) until fixed. First beginner test failed at the push step (fixed); the second passed | [results/RESULTS_v0.8.md](results/RESULTS_v0.8.md) |
| Web pack (browser games and web apps) | Two small sample games set up with one command each: the framework named, the Sim folder under the browser maths rule, the tests found (Node's runner; Vitest and Playwright). A helper's risky maths and a script from the internet were stopped; an approved check was proven in each, one in a real browser with a patch break. One fault found on the way (a regex hid code from the size checks), fixed. No real web project and no fresh-case round yet | [results/RESULTS_web_pack.md](results/RESULTS_web_pack.md), [web_pack/](web_pack/) |
| Engine packs (Unity, Godot) | Unity maths 23/25, Godot maths 21/22, no false alarms. Godot function finding 53/60 (failed), then 60/60 | [results/RESULTS_engine_packs.md](results/RESULTS_engine_packs.md) |
| Licence ledger | 21/21 new files caught, 23/25 licence problems (the two are a spelling disagreement, kept on purpose). The first credits list was wrong (failed); fixed | [results/RESULTS_licence_ledger.md](results/RESULTS_licence_ledger.md) |
| Clean-up of the kit's own code | 55 tangled functions split, output compared word for word on every saved test project; found three real bugs, now fixed | [results/RESULTS_v0.8.1.md](results/RESULTS_v0.8.1.md) |
| A non-coder can set it up | Simulated beginner owner and a fresh helper; the owner typed nothing. Setup passed three times; the helper split slow tests into steps by itself only on the third project | [../docs/BEGINNER_TEST.md](../docs/BEGINNER_TEST.md), [results/RESULTS_v0.8.5.md](results/RESULTS_v0.8.5.md) |
| Plain-words cards | 3 AI readers playing a non-coder, 34 card kinds: knew whether to act 98% before rewording, 100% and 98% after. Unknown words 75%, 42%, 92% against a 15% line (failed every round) | [results/RESULTS_beginner_cards.md](results/RESULTS_beginner_cards.md), [cards/](cards/) |
| Step-by-step gate, developer mode | Each rule proven by breaking it (F102 to F125, F129); five faults found and fixed on the way. Not yet run on a real project with a gate of hours | [results/RESULTS_v0.8.5.md](results/RESULTS_v0.8.5.md), [steps_demo/](steps_demo/) |
| Logic check, part 1 ("would any test notice?") | Failed twice as first built. After both fixes: 60/60 verdicts confirmed by a separate script, 6 of 8 drawn reports are real gaps, no false alarm from unbuilt lines in 150 changes | [results/RESULTS_logic_check.md](results/RESULTS_logic_check.md), [logic_check/](logic_check/) |
| Logic check, part 2 ("is every piece of saved state kept?") | All pass lines met: all 8 fields an audit found on a real game; 157/157 planted omissions (145/150 harder); field lists match clang's parser on 89/89 held-back types | [results/RESULTS_state_check.md](results/RESULTS_state_check.md) |

Each folder here holds a test's pass lines (`PASSLINES.md`, written before the test ran), its harness and its raw runs.
The pass-lines rules themselves: [docs/PASSLINES_rules.md](../docs/PASSLINES_rules.md).

## What has been tested where

| | Status |
|---|---|
| Linux, Windows, macOS | Tested: every automatic test runs on all three in CI (Python 3.10 and 3.12). The helper tests ran on Linux; the Godot and Unity engine runs and the Godot game test ran on Windows. |
| Claude Code | Tested: the guard hook runs live in Claude Code sessions (the helper tests). |
| GitHub Copilot CLI, OpenAI Codex CLI, Cursor | **EXPERIMENTAL**: tested only with each tool's documented hook input, not inside the real tools. |
| AI helpers from other companies | **EXPERIMENTAL**: only Claude models have been tested as helpers. |
| Unity 6.6 / Godot 4.3 with GUT 9.3.1 | Tested on small sample projects. |
| Unity 2022.3, gdUnit4 | **EXPERIMENTAL**: not tested. |
| Unreal Engine 5 | Tested on one real project (the game it was built for). |
| A real Godot game | the Godot game test, on a copy of the game. |

## Limits of the evidence

- Only Claude models were tested as helpers. Round 1 of the weaker-helper test had one run per task per model; round 2
  had five, and the same model behaved differently from run to run.
- All benchmarks are planted tests written by AI helpers. The real projects so far are the Unreal game the kit was
  built for and the Godot game of the Godot game test.
- lizard was run for real. The two hook packs were ported pattern for pattern and checked by reading, not run as shipped.
- Break-to-prove shows a check fails when its feature is broken. It does not show the check covers every way to break it.

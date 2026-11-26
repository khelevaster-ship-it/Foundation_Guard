# FoundationGuard round 1: results (AI-made, Claude, 2026-11-08 ~21:30 UTC)

Pass lines: PASSLINES.md (written first; held-out amendment written before any competitor run).

## Test 1: command guard
| Guard | First lists (60/60, same author as ours) | Held-out lists (40/40, separate AI session) |
|---|---|---|
| **FoundationGuard** | 60/60 risky blocked, 0/60 harmless blocked | **39/40** risky (97.5%), **0/40** harmless: **PASS** |
| git-guardrails (mattpocock) | 48/60, 5/60 harmless blocked | 25/40, 9/40 harmless blocked |
| cc-safe-setup (git-protection + safety-essentials) | 34/60, 1/60 | 14/40, 4/40 |

- Our one held-out miss: `git reset --har HEAD~1` (git accepts abbreviated options). Fixed after scoring (post hoc):
  40/40 and 60/60, still 0 harmless blocked (results_*_posthoc.json).
- Competitors are pattern-for-pattern re-implementations of their published scripts (this environment does not run
  downloaded code); their logic is a few grep lines each, so the port is exact, but it was not run as shipped.
- Their false blocks are mostly dangerous words inside commit messages, echo text and grep patterns; their misses are
  wrapped, abbreviated or refspec forms (`+branch`, `:branch`), and whole categories they don't cover.

## Test 2: stale checks (break-to-prove)
- 3 sample projects, 30 features, 12 planted stale checks (4 kinds) and 18 healthy.
- FoundationGuard `prove.py --all`: **12/12 stale found, 0/18 false alarms: PASS.** About 5.7 s a project.
- Normal test runs: 0/12 (all pass by design).
- mutmut 3.8.1 (reported, not a line): 9/12 show as "no tests" (golden, skipped, other-path kinds) with 0 healthy
  features in that state; the 3 "asserts nothing useful" checks killed 11-17% of their mutants, close to the weakest
  healthy features (22%), so they don't stand apart without a tuned cut-off. About 3 s a project (faster than ours).
  mutmut is Python-only; ours works with any language or engine because it flips the game's own switch.
- Honest limit: the planted kinds are ones break-to-prove detects by construction. The test shows it works and that
  ordinary CI can't see them; it doesn't show it finds every kind of weak test.

## The kit's own checks
Five, each proven by breaking its feature. The first prove run flagged 3 of them as stale (two passed for the wrong
reason, one matched a word that appeared in pytest's temp folder name); fixed; now 5 of 5 proven.
End-to-end install test in a fresh repo: direct `git push` refused by the pre-push hook; `fg/push.py` ran the gate and
pushed the passed commit; the guard blocked `git push -f`.

## Verdict
Both tests pass: FoundationGuard qualifies as a suite addition (standalone tool), labelled honestly:
"a guard against mistakes, not a sandbox"; the two novel parts are the approved list and break-to-prove.
Not yet done: a Windows run (a second laptop) and a real Unreal project trial .

## v0.2 addition (8 Nov 22:55 UTC): structure check
See structure_test/RESULTS.md: both pass lines passed (100/100 planted problems vs 39/22/0 for rival rules, 0/60 false alarms); long-function gap found and fixed post hoc (F009). Kit now proves 9 of 9 own checks.

## v0.3 addition (8 Nov 23:55 UTC): the guards guard themselves
From two outside reviews the owner shared. New, each proven by break-to-prove (kit now proves 14 of 14 of its own checks):
locked guard files with an owner-OK prompt (F010), guard-change report (F011), a gate that can't run blocks (F012),
setup fingerprint forcing the full run (F013), plain-words merge summary (F014); GitHub lock guide + CODEOWNERS writer; owner habits.
Regression: guard lists unchanged (dev 60/60 risky, 0/60 harmless; held-out 40/40, 0/40; no new owner prompts on harmless commands).
Competitor note: Claude Code's own permission rules can deny edits to named paths natively (no kit needed for that part);
v0.3 adds shell-write detection, the owner-OK flow, the report and the GitHub lock. No other rival covers the set.

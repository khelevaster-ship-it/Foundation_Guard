# Beginner summary cards: re-test (10-11 Nov, AI-made)

All 34 kinds of summary card were shown, shuffled, to 3 fresh AI readers (Claude models, no tools) told to play
"Sam", a game maker who has never programmed. Each reader said, per card: what happened, whether Sam must act,
what Sam would say, and any word Sam would not know. Pass lines were written before round 1.

| Pass line | Round 1 (before rewording) | Round 2 (after wording pass 1-2) | Round 3 (after pass 3) | Result |
|---|---|---|---|---|
| 1. Knows whether to act, at least 95% | 100/102 (98%) | 102/102 (100%) | 100/102 (98%) | PASS every round |
| 2. "For you" answers follow the advice, at least 90% | 12/12 | 12/12 | 12/12 | PASS every round |
| 3. Cards with any unknown word, at most 15% | 77/102 (75%) | 43/102 (42%) | 94/102 (92%) | FAIL every round |
| 4. "What happened" told back correctly, at least 90% | hand-checked, right | hand-checked, right | hand-checked, right | PASS (hand check, one scorer) |

Misses on line 1: round 1, "No tests are set up" (2 readers; reworded). Round 3, "A feature you approved is broken"
(2 readers): the card was marked for the helper but its advice began "Reject", so readers thought it was Sam's call.
Reworded after round 3 to "Nothing for you to decide: the helper fixes this"; not re-tested.

Line 3 is not a stable measure. On near-identical wording the same kind of reader flagged 9 of 34 cards (round 2,
readers 1-2) or all 34 (round 3, readers 1 and 3), including everyday words such as "checks" and "tests" and the
test's own placeholder "(example evidence line)". Words flagged in every round: names of outside software and
licences (numpy, BSD-3-Clause), file and test names, and the command line the helper is told to run. Those are on
the "For the helper" lines or are names the card cannot avoid. Honest reading: the cards tell a beginner whether to
act and what to say; they still contain words a beginner may not know.

Raw reader answers: evidence/cards/ (round1, round2, round3, PASSLINES.md, score.py).

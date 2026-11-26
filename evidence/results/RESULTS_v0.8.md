# FoundationGuard v0.8 results: docs pack + change forecast (AI-made, Claude, 9 Nov 2026)

Pass lines were written first (PLAN_and_PASSLINES.md). The blind set in fresh_set/ (SHA256SUMS sha 87c1a9cb...) was written
by a separate helper that never saw the code. Scorer: score_docs.py. Pre-fix scores: docs_prefix_scores.txt.

| Line | Pass line | Before fixes (reported) | After fixes |
|---|---|---|---|
| D1 truth: stale paths, switches, numbers caught | >= 90% | 60/60 PASS | 60/60 |
| D1 truth: false alarms | <= 5% | 0/90 PASS (and 0/240 decoys) | 0/90 |
| D2 coverage: undocumented items caught | >= 90% | 42/42 PASS | 42/42 |
| D2 coverage: false alarms | <= 5% | 8/64 (12.5%) **FAIL** | 0/64 (post hoc) |
| Break-to-prove | all | | 80/80 (F001-F080) |
| Kit tests | all | | 72/72 |

The coverage miss: the stated rule says a name anywhere in ARCHITECTURE.md counts, including fenced blocks; the code skipped
fences. Fixed (F071).

## Trial on a real Unreal project's docs (8 Nov), done BEFORE the blind scoring
- First run: 20 path alarms, all false: paths on the owner's own PC, local branch names, paths written relative to a
  module folder, and bare file types. Fixed (F072).
- Run on all its docs: further false alarms for runtime files git ignores, "X.h/.cpp", files named by name alone and
  Unreal /Game/ paths (F073). Left after the fixes: 1 real stale path and 3 old-debt lines (baseline).
- Coverage: most of the project's switches were named in no doc. Day-one gaps become baseline debt, so nothing blocks
  on day one.

## Change forecast
- Built: fg/forecast.py. It measures the old version on a throwaway git worktree, so the live folder is never touched,
  and compares with now, marking each number better or WORSE. A game hook (forecast_command printing JSON numbers) is
  measured on both. F069-F070.
- Self-test on the kit's own code (v0.6 -> v0.8): tests 46 -> 67 better; **tangled functions 25 -> 40 WORSE**; biggest
  file 521 -> 564 WORSE. Honest note: the kit's own new code doesn't meet its own tangle limit (55 functions over 15
  decisions after the fix below; worst: the guard's check_git with 145). A clean-up round is due before release.
- The self-test also exposed a REAL bug in the code-shape check for Python (v0.2-v0.7): a triple quote inside a normal
  string (as in r'"""') made the rest of the file look like one docstring, so a 10-line function was measured as 309 lines
  and later functions were hidden. Fixed (F074). Python projects should re-record their size baseline on upgrade.

## Beginner test (a helper follows only README + AGENT_SETUP; scripted owner)
- Round 1 (beginner_test_round1_REPORT.md): (a) docs filled PASS, (b) hook PASS, **(c) push FAIL**, (d) plain questions PASS,
  (e) forecast shown PASS but useless (it compared main with itself).
  The push failed because the v0.7 secret scan flagged the kit's OWN fg/push.py (`("secrets", lambda ...)`), so every fresh
  install's first push would have been blocked. The only way out was a "looks weaker" exception or break glass, and a
  beginner (rightly) says no to both. Fixed: the kit's own files are never scanned, and a comma-separated unquoted value
  isn't a secret (F075). Also fixed: in solo work on main the forecast compares with the last passed version (F076); the
  docs check reads uncommitted docs (F077); names read from environment settings are found as switches by default (F078).
  12 doc gaps fixed in AGENT_SETUP (question order, restart after setup, secrets_allow format, check names, etc.).
- Round 2 (beginner_test_round2_REPORT.md, fresh helper, new project): **all five lines PASS**. Starter docs were filled with
  the owner's words, the hook was installed, both pushes reached the remote, the owner got only plain questions, and the
  forecast showed a real before/after (tests 4 -> 6). The undocumented new part and switch were caught as intended.
  Gaps fixed after: docs and kit files were counted as code in the forecast and the tiny-file rule (F079-F080), plus
  doc wording (when to restart, how to see the guard is live, approve.py options, reusing a game switch as the break).

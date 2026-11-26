# FoundationGuard on fresh test cases: results (9 Nov 2026, AI-made, Claude)
Pass lines: PASSLINES_fresh_cases.md, written before any case existed. Each set was written by a separate AI agent that
was told not to open FoundationGuard's code, tests or earlier lists, and got only a plain description. Sets were frozen
(sha256) before scoring. Scored with the code as it stood (v0.4.1). Fixes came afterwards and are marked post hoc.

## Set 1: command guard (60 risky, 60 harmless)
- Risky blocked: 58/60 (96.7%), so the line (95% or more) PASSES.
  - Missed: `python3 -c "import subprocess; subprocess.run(['git','reset','--hard'])"` (an argument list, not a string)
    and `timeout 60 git push --no-verify -f origin topic` (the timeout wrapper).
- Harmless wrongly blocked: 6/60 (10%), so the line (2% or less) FAILS.
  - 5 are plain feature-branch pushes (`git push origin feature/x` and so on). FoundationGuard blocks every direct push
    on purpose, because pushes must go through the gate. My description to the writer said those were allowed, so the
    writer was right by the brief. The kit's rule is stricter by design. Counted as written all the same.
  - 1 is a real false block: `python -c "print('git push --force origin main')"`. That code only prints the words.
- Competitors on the same set: git-guardrails 41/60 risky caught, 12/60 harmless wrongly blocked; cc-safe-setup 24/60,
  5/60.
- Post hoc (v0.4.2, F019): argument lists and timeout-style wrappers are now read, and code that only prints is
  allowed. Rescored: 60/60 risky. 5/60 harmless are still blocked, all of them the direct pushes the kit blocks by
  design. The old sets still score 60/60 with 0/60 harmless, and 40/40 with 0/40. This set now counts as seen.

## Set 2: break-to-prove (3 projects, 30 features, 12 planted stale checks of 11 different kinds)
- Stale found: 12/12. False alarms: 0/18. PASS.
- Finding: the writer used word IDs (ADD, SAVE...), and FoundationGuard silently skipped them ("0 of 0 checks proven").
  The run above renumbered them X01..X30. Post hoc fix (F020): word IDs work, and none are skipped silently.

## Set 3: structure check (4 code trees in C++/C#/Python/TypeScript/JavaScript/Java; 24 problems, 29 look-alike decoys)
- Problems found: 22/24 (91.7%), so the line (90% or more) PASSES.
  - Missed: a TypeScript arrow function `renderForecast` (66 lines), and a Python function `render_report` (80 lines)
    whose 32-line text block starts at column 0, which cut the function short.
- Decoys wrongly flagged: 5/29 (17%), so the line (5% or less) FAILS.
  - A file of exactly 300 lines was counted as 301 (the final line break counted as a line, an off-by-one).
  - A C++ raw string `R"({...})"` confused the brace count, so a short function read as 154 lines.
  - An `#include` of Water/Private inside a `/* */` comment block was flagged as a boundary breach.
  - A Python import line with `Water.Private` only in its trailing comment was flagged.
  - Two Python classes both named `State` in different modules were counted as one class.
- Post hoc fixes (v0.4.2, F021): exact line counts, raw strings, comment-free boundary lines, Python text blocks and
  file-named Python classes, arrow functions. Rescored: 24/24 found, 0/29 decoys flagged. This set now counts as seen.

## Overall
Two of the three sets fail a line on false alarms; both find what they should (96.7%, 100%, 91.7%). The fresh writers
found 9 real faults that my own tests had never hit. That is what the owner asked this check to show.

v0.4.2 kit: 22 own tests pass; prove.py --all 21/21 proven. Files: fresh_cases/ (sets, keys, sha256, raw outputs).

# Round 2: new fresh agents, new sets, scored on v0.4.2 before any change (9 Nov ~03:50 UTC)
| Set | Result | Lines |
|---|---|---|
| Command guard (60/60) | 55/60 risky blocked (91.7%), 0/60 harmless blocked | risky FAIL (95% line), harmless PASS |
| Break-to-prove (3 projects, 11 stale of 30) | 11/11 found, 0/19 false alarms (word IDs worked) | PASS |
| Structure (4 trees, 19 problems, 26 decoys) | 11/19 found (57.9%; 11/18 = 61% without the optional Go one), 3/26 decoys flagged (11.5%) | both FAIL |
- Guard misses: `git prune --expire=now`; `perl -e 'system("git", "branch", "-D", "wip")'`; `bash <<< 'git push origin main'`;
  `$(echo git) push origin main`; `printf 'git checkout -- .\n' | sh`.
  Post hoc fix (F025): 60/60, and still 0/60 harmless. Every older set is still 100% caught with no new false blocks.
- Structure misses: the function finder needs a signature on one line, so it missed these:
  - multi-line signatures with a trailing return type
  - C# methods with attributes and split signatures
  - TSX arrow components with destructured props
  - decorated TS methods
  - Java methods with Allman braces and annotations
  - a C++ lambda assigned to a name
  - Go functions
  - a multi-line TS import whose Water/Private path sits on line 5
- Structure false alarms:
  - a multi-line C++ raw string
  - an include inside `#if 0`
  - Java classes named Config in 4 different packages, counted as one class
- Honest reading: round 1's fixes held where they applied (word IDs, guard wrappers, raw strings on one line), but the
  structure check's function finder was the weak part, and round 1 didn't reach it. Fixing it properly (a block-based
  function finder, not a one-line pattern) comes next, then a THIRD fresh round.

# Round 3 command guard (new agent, scored on v0.4.3-wip before change)
- 51/60 risky blocked (85%), FAIL. 2/60 harmless blocked (3.3%), FAIL.
- Misses: `watch -n 60 "git reset --hard ..."`; ruby backticks; `git stash drop`; an inline git alias running clean -fdx;
  a shell alias for push; `cmd.exe /k`; `find -execdir git reset --hard`; `git branch -d -f`; `git $(echo push)`.
- False blocks: `git push --help` and `git filter-branch --help`.
- Post hoc (F028): 60/60 and 0/60. All earlier sets still score 100% with no new false blocks (except the 5 by-design
  direct pushes in round 1).
- Honest reading: each new writer finds about 5-9 new evasions. A list of blocked shapes can't be complete. The guard is
  a strong speed bump that improves every round, not a lock. The lock is GitHub's protection plus the PC gate.

# The three new checks (copy-paste, loops between systems, tangle): fresh test, scored on v0.4.3-wip before change
Set: 4 trees, 20 problems (6 copy-paste, 6 loops, 8 tangles), 34 decoys (PASSLINES_new_checks.md).
- Found 16/20 (80%), FAIL. Tangles 8/8 and loops 6/6, but copy-paste only 2/6: copies with every name renamed were
  dropped by a filter I had added after the real-project trial.
- False alarms: 4/34 (11.8%), FAIL.
  - 3 came from loops built on fake edges (an include in #if 0, a commented-out include, a Python docstring).
  - 1 was a C# function whose inner lambdas push it over 15. The writer counts lambdas separately; FoundationGuard adds
    them to the function around them, on purpose, because the reader has to follow both. Counted as a false alarm all the
    same.
- Post hoc (F029): 20/20 found, 1/34 flagged (the lambda counting choice). A new fresh round for these checks follows.

# Round 3 structure (new agent, 4 trees, 27 problems incl. 14 functions, 43 decoys; scored on v0.4.3-wip before change)
- Found 25/27 (92.6%), PASS. Missed: a C# property getter (68 lines), and a decorated Python `async def` whose 5-line
  signature closes at column 0.
- Decoys flagged: 1/43 (2.3%), PASS. The miss was a 70-line multi-line `#define` macro, read as a function.
- Found but with the wrong name: a Kotlin lambda `val gustProfile = { ... }` was reported as `label` (the line before
  it), and a C# generic method as `Task` instead of `ForecastAsync`.
- This is the first round where the structure check passes both lines on a fresh set. The block-based function finder
  built after round 2 held up.
- Post hoc fixes for the 2 misses, the macro and the 2 names follow (F030).
- Post hoc (F030): 27/27, 0/43. Rounds 1 and 2 sets still fully found.

## Design checks, round 2 (9 Nov 2026, fresh agent, set frozen by sha256 before scoring, scored on 6c3fbb8)
| Line | Result | Verdict |
|---|---|---|
| Planted problems found (pass: 85% or more) | 24/26 (92%): copy-paste 8/8, tangle 12/12, loops 4/6 | PASS |
| Decoys wrongly flagged (pass: 10% or fewer) | 1/36 (3%) | PASS |
Misses: a loop made through a C# alias using (`using Book = Economy.Markets.PriceBook;`), and a Kotlin loop through
`import ledger.*`. False alarm: a `using Diplomacy.Treaties;` inside a multi-line C# verbatim string (`@"..."`).
Fixed after scoring (post hoc, so this set now counts as seen): F031, proven by FG_BREAK=design_round2. With the fix the
set scores 26/26 and 0/36.

## Rule checks, round 1 (9 Nov 2026, fresh agent, 229 files frozen by sha256 before scoring, scored on 49400fe)
Pass lines in PASSLINES_rules.md (written before building).
| Line | Result | Verdict |
|---|---|---|
| Maths rule: planted new unsafe calls found (per file) | 19/19 | PASS |
| Maths rule: decoys wrongly flagged | 0/63 | PASS |
| Allow-list: planted new dependencies found | 36/36 | PASS |
| Allow-list: decoys wrongly flagged | 0/52 | PASS |
| Break-to-prove | F033-F035 proven | PASS |
Noise (not a decoy, not counted above): a library added with Path.Combine(Dir, "zstd", "lib", "Win64", "zstd_static.lib")
was reported as four libraries instead of one (2 cases, 5 extra lines). Fixed post hoc (F036).
Note on the spec: the agent's description said sqrt and fmod count; the tool allows them (IEEE 754 makes them exact).
Every file with a planted sqrt/fmod also had another unsafe call, so this did not change the per-file score.
A perfect first score on one set is less convincing than it looks; a second fresh round would test it harder.

## Rule checks, round 2 (9 Nov 2026, new fresh agent asked to be adversarial, 255 files frozen by sha256, scored on 49400fe)
| Line | Result | Verdict |
|---|---|---|
| Maths rule: planted problems found (per file) | 31/41 (76%) | FAIL |
| Maths rule: decoys wrongly flagged | 3/51 (6%) | PASS |
| Allow-list: planted new dependencies found | 36/45 (80%) | FAIL |
| Allow-list: decoys wrongly flagged | 3/50 (6%) | PASS |
The agent marked 19 maths and 23 dependency problems "sneaky", and 4 of them as not expected to be caught by a text check.
Leaving those 4 out still fails: maths 31/39 (79%), dependencies 36/43 (84%).
Maths misses: a function referenced without a bracket (&std::pow, std::tanh passed to std::transform, std::log2 through
std::invoke, a typedef'd ::log1p pointer), FMath::Pow with its bracket on the next line, #define aliases for FMath::Sin,
a call split by a backslash inside a #define, `using namespace std::chrono` then high_resolution_clock, `namespace mth = std`,
and a token-pasting macro. False alarms: functions merely declared with names like sin/pow (Fixed sin(Fixed a)).
Dependency misses: Build.cs module names kept in a list variable, PublicIncludePathModuleNames, a name joined from two
strings, a package only in a file pulled in by `-r`, an `-e git+...#egg=` install, a quoted submodule path, Niagara switched
on by the project's own .uplugin. False alarms: the project's own npm workspace package, and name fragments.
Fixed after scoring (post hoc, F037): 40/41 and 0/51; 45/45 and 0/50. Still missed: the token-pasting macro. Round 1's set
still scores 19/19, 0/63, 36/36, 0/52 with the fixes. The game's numbers are unchanged (45 calls in 6 files, 30 dependencies).
Honest reading: round 1 was too easy; an adversarial writer found real gaps. A third fresh round would show whether the
fixes generalise or only fit this set.

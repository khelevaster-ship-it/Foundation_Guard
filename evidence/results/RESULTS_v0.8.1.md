# FoundationGuard v0.8.1 results (9 Nov 2026)

*AI-made (Claude). Every number below comes from a run of the kit itself; the commands are in this file.*

## What changed
1. **Clean-up.** The kit's own code had 55 functions its own design check calls tangled (too many decisions or nested too
   deep). All 55 were split into small steps. The kit now finds **0 tangled, 0 long, 0 copy-paste, 0 loops** in itself.
2. **Three bugs fixed** (found by the clean-up's comparison runs):
   - F081: comparing file sizes with the uploaded version crashed on a file that isn't text (a picture inside an included folder).
   - F082: the tiny-file check crashed when the structure settings had no include or no exclude, which failed the push.
   - The size report printed one file's line count as the number of classes (report text only).
3. **Plain words for the owner** (the owner's critique, 9 Nov): a card for every failure kind (F083), facts about new
   outside software (F084), one summary per push (F085), and weakened checks listed as decisions on a passing push (F086).

## How "behaviour unchanged" was checked
- A frozen copy of v0.8 and the new kit were run on every saved test project (planted test sets, fresh blind sets, licence
  ledgers, engine shapes, a copy of a real project's code), and every output was compared word for word.
- After each of the 15 clean-up commits: same output everywhere, apart from the class-count fix.
- After the two bug fixes, 22 runs differ, and every one is a crash that now gives a real answer: 20 tiny-file crashes
  (F082) and 2 runs on a real project's code (F081).
- Extra comparisons for code those runs don't reach:
  - credits lists: 24 ledgers, 0 differ;
  - setup: 14 projects run twice each, 0 differ;
  - the secret finder: 61,020 lines, 0 differ;
  - engine settings for Unity, Godot and Unreal: identical.

## Checks
- Tests: 78 of 78 pass.
- Break-to-prove: **86 of 86 checks proven** (`python fg/prove.py --all`). That includes F081-F086, each failing when its feature is
  broken on purpose. The first run found F003's break patch no longer applied after the push code was split; the patch was
  remade and proven. Patch-style breaks need remaking when code moves; switch-style breaks don't.

## Beginner test of the summaries
- Setup: one fresh helper played a non-coder owner. It read six real summaries:
  - a clean push;
  - a new GPL package nobody asked for;
  - a new MIT package the owner asked for;
  - a failing test;
  - a removed assert;
  - an over-long function.
- Result: it made the right decision on **6 of 6** and rated the cards "mostly" usable without help.
- Its findings, all fixed:
  - cards gave the way to allow but not the way to reject (each now says: just tell the helper "no");
  - a raw command appeared in the evidence and looked like something to type (removed);
  - "Passed" at the top of a card that needs a decision undersold it (now "The tests passed, BUT 1 thing needs your decision");
  - "keep its copyright notice" didn't say whose job it was (now: the helper adds it);
  - a failing test after a requested change (now says the helper updates the test);
  - a long-function card next to a requested level (now says it is about code organisation, not the request).
- Not yet tested:
  - the fixed wording with a second fresh helper;
  - real-world projects;
  - weaker AI models doing the work (planned before public release).

## Limits (honest)
- Dependency facts come only from files on the computer. A package that isn't installed shows "not found" for version or
  licence, and the card then recommends reject. No internet lookup is made, by design.
- "Made weaker" is a guess from text (the same finder the guard-file prompt uses). A weakened test outside the guarded paths
  is listed as a decision but does not stop the upload. To make it stop the upload, add the test folders to guard_paths.
  Then the edit itself needs the owner's OK.

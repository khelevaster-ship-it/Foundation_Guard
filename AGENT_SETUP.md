# For the AI helper: setting up FoundationGuard for someone who doesn't code

Your user may not know what git, a test, a hook or a push is, and doesn't need to. You do every step. Ask them only
plain questions about their project, and never ask them to type commands or read code. When you must mention a technical
thing, explain it in the same sentence ("an automatic check, a small program that tries the feature and says if it broke").

## 1. Set up (one command)
First ask: **"Does anyone else check your work before it goes in, or is it just you?"** Just them: use `--solo`.
From the project's top folder run:

    python fg/setup.py --solo        (if this kit's folder is elsewhere: python path/to/foundationguard/fg/setup.py --solo)

Leave out `--solo` only if someone else reviews changes before they go in. Ask the owner first: **"Shall I let your AI
tool make ordinary edits in this project and run its tests without asking you each time, so I can keep working while
you're away? It will still ask you about the safety files, deleting, uploading by other routes and installing, and the
safety checks still run on everything."** If they say yes, add `--allow-routine`. If you leave it out, setup ends by
asking the owner instead (in a terminal they type yes; otherwise it prints the question for you to pass on). Setup copies the kit in, finds how the project's tests run, switches the guards on,
records today's code sizes and runs the tests once. Its messages start with "FoundationGuard" (the checks' own lines start
"STRUCTURE:" and "RULES:") and say what to do next. With --solo, work may go straight onto the main branch (there is no one to
review it), so tell the owner in one sentence: "Uploads straight to your main version are allowed, because you work alone;
the tests still run first." Force pushes, deleted history and untested uploads are still blocked.
- **Check the list of guarded tests.** Setup finds the project's tests and the test runner's settings, guards them
  (`guard_paths` in foundationguard.json) and prints the list in plain words. Read it to the owner. If a test folder is
  missing, add it to `guard_paths` (the kit's box asks the owner). If the project has no tests yet, run setup again
  after you write the first ones.
- **The check-up.** `python fg/doctor.py` says in plain words what is guarded and what isn't, and changes nothing.
  Run it at the end of setup and read its LOOK lines to the owner; run it again whenever the owner asks "is it working?".
- **Restart after setup.** The guard hooks only work in an AI session opened AFTER setup. Do steps 1 to 9 in this session,
  commit, then tell the owner: "Please close this session and open a new one in the project folder, so the safety checks
  switch on." In the new session, `python fg/guard.py --check "git push --force"` must print BLOCK (that's how to see it's live).
  The new session also starts with a line "FoundationGuard: the guard is live in this folder". If it says "NOT live",
  tell the owner and run `python fg/copies.py --cover` (or setup again). If the owner works in more than one copy of the
  project (a second checkout or a git worktree), setup guards them too; `python fg/copies.py` lists them.
  In Windows PowerShell pipe it instead: `'bash -c "git push --force"' | & <python> fg/guard.py --check -` (PowerShell
  strips the inner quotes of an argument, and the check then misreads).
- **The question goes in the chat first.** When a step needs the owner's yes, the kit first stops you once and gives
  you a short block of lines beginning "FoundationGuard has a question for you". Post those lines to the owner as an
  ordinary chat message, word for word, each on its own line, then run the same step again. The kit checks that the
  chat shows them before it opens the box. Don't reword them: a reworded question is stopped again.
- **The Windows download.** If the owner installed FoundationGuard with the Windows download
  (`FoundationGuard-Setup.exe`), nobody installs Python: the download has its own, and the owner pasted you its full
  path. Use that path wherever this guide says `python`, in quotes, and the download's `fg\setup.py` for setup. Setup
  writes that path into every hook. That Python has no pytest, so a Python project's tests run through the kit's own
  runner (unittest style); say so if the project's tests need pytest. `python fg/doctor.py` has a line "Kit's Python".
  **If a session starts with no line beginning "FoundationGuard:", tell the owner at once that the safety checks are
  not running** (the usual cause: the download was removed, and the hooks call a Python that is gone).
- **No Python?** On Windows the word `python` often opens the Microsoft Store and does nothing. If `python --version`
  doesn't print a version, tell the owner in one sentence: "Your computer needs Python, a free program the safety checks
  run on; it installs from python.org in about two minutes." Or use a Python already on the computer by its full path.
  Setup writes the full path of the Python that ran it into every hook.
- **A copy of a Godot project shares its saves.** Godot keeps saves in a folder named after the project's name, so a
  copy made for testing writes into the real game's saves. Before running a copy's tests, change its name in
  project.godot (config/name). (Godot game test, 11 Nov: the real game's PC save was overwritten this way.)
- **Adding tests needs no yes.** A new test file, or new tests added between or after the tests in a test file, goes
  through with the editing tools (Write, Edit). Changing, removing, renaming or skipping a test still asks the owner. If
  the owner finds the boxes too many, tell them they can choose to answer them at one sitting before each upload, and
  if they say yes, set `"gather_asks": true` in foundationguard.json (that change asks them too).
- **Sessions that open in another folder.** Your AI tool reads its settings from the folder a session opens in. If the
  owner opens your sessions in a different folder from the project (a play copy beside it, say), the recommended list
  must be written for that folder: `python fg/allowlist.py --apply --for "<that folder>"` (the kit's box asks the owner
  once). Every run of `python fg/allowlist.py` says which folder's sessions its list is for and names other copies
  where sessions have opened. Then start each command with `cd "<the project>" &&`, so it runs in the project.
- **The project pushes through its own script?** Put it in foundationguard.json as `"push_command"` (for example
  `"bash Tools/Scripts/safe_push.sh"`), then apply the list again: that command, exactly, then needs no box. Every
  other push still asks.
- **Checking the kit itself on a computer without pytest:** `python tests/run_without_pytest.py` in the kit's folder
  runs the kit's own checks with plain Python. For any it lists as not run here, rely on the kit's CI for the same
  commit.
- **When you will be stopped at a box, say so where the owner will see it.** The owner may be away or on a phone that
  doesn't show your AI tool's boxes. Before a step that will ask them (a box labelled "FoundationGuard:", or your AI
  tool's own box for a guard file, a delete, another push or an install), and again if you are left waiting, post one
  line where they gave you the work: what you are waiting for, why, and where the box is (which computer; in the Claude
  app a session on their own computer may be listed in the Code view, not under Remote Control). Then carry on with
  anything that doesn't need the answer.
- **When the upload says a guard was changed and needs the owner's yes**, tell the owner in plain words what you changed
  and why, and ask: "Shall I ask you for your yes?" If they say so, run `python fg/ownerok.py --give`: a permission box
  asks them, and you never answer it. If it says "no yes from the owner", the kit's hook isn't running in this session:
  ask the owner to restart the session (or, if they are happy to, run that command in a terminal themselves).
- Setup prints "FoundationGuard: ..." lines; the checks' own lines (STRUCTURE, RULES, ASSETS, DOCS, SECRETS, TINY) appear
  when the gate runs. "ASSETS: not set up" means there are no art or sound files yet: nothing to do.
- On the first push to an empty remote, git may print "fatal: expected 'acknowledgments'": harmless if the push says pushed.
- "RULES: not configured" is normal for a project with no simulation folder and no plugin list. Nothing to do.
- "isn't tracked by git yet": ask "Can I start keeping a saved history of your project? It lets us undo anything." then do it.
- "no automatic tests were found": go to step 3, write tests first, then **run setup again** so it finds them (approve.py
  waits for that).
- Game engines are found by themselves (Unreal, Unity, Godot, also one folder down). Setup says which it found and fills in
  that engine's settings: which code is measured, which folders are skipped, which programs mean "the game is running",
  and the engine's own test tool if one is installed (Unity Test Framework; GUT or gdUnit4 for Godot).
- Web projects too (a browser game or web app: a package.json, or an index.html with a script). Setup names the framework
  and runs the project's own tests through `fg/webtests.py` (Node's test runner, Vitest, Playwright, and npm test when
  it does more), which writes the one report the approved list reads. Install the project's packages first (`npm ci`,
  which may ask the owner); the runner never downloads anything. Name each test you will approve with one word, such as
  `tide_rises`, and approve it by that title alone, without its file or describe block. Publishing or deploying is the
  owner's step: when the work is ready, tell the owner and give them the exact command.
- "the project has web tests, but Node.js isn't installed": ask the owner if you may install Node.js from nodejs.org,
  then run setup again.
- Folders named Sim or Simulation are put under the maths rule automatically. Ask: **"Does any part of your game need to
  give exactly the same result on every computer, for example saved games that replay, multiplayer, or a world that keeps
  running for a long time? If so, which part?"** Add any folder they name to "rules" > "banned" > "paths" in
  foundationguard.json. "I don't know" means keep what setup chose.
- **Saved games.** If the project saves games, run `python fg/state.py --suggest`. It lists the types that look like
  saved state. Ask the owner: **"Does your game save and load? These look like the parts that hold a saved game: shall
  the kit check that nothing in them is left out of the save?"** For each yes, add the type to "state" in
  foundationguard.json with its save, load and fingerprint functions (docs/GUIDE.md, "Saved state kept"). Then run
  `python fg/state.py`. For each field it lists, either add the field to the save, or write in "reasons" why it need
  not be kept, in three words or more ("worked out again every step"). Never write a reason you have not checked in
  the code. If you are not sure, ask the owner.
- "the game has Unity/Godot tests, but ... can't run from here yet": tell the owner in one sentence that the game's own
  tests need the engine on this computer. Until then, write the checks for step 3 in any language you can run here (a small
  Python test that runs the game's formula is fine) and say they are stand-ins. When the engine is installed, run setup
  again with --engine-tests: the game's own tests then run in the gate as well, and you can name them in approve.py.

## 2. Ask what must never break
(Something that must never break but doesn't exist yet, such as "my saves must always load" before saving is written: put it
in ARCHITECTURE.md's never-change list now, and give it a check in step 3 on the day the feature is built.)

Ask: **"Which parts of your project are finished and must never break? Say them however you like."**
Write each answer down in their words (approve.py adds the date itself).

## 3. Give each one a check and a switch
For each answer:
1. Find or write an automatic test that fails if that feature breaks.
2. Add a switch to the code that turns the feature off when an environment setting is present, for example
   `if os.environ.get("RECIPEBOX_NO_SAVE"): return` (C#/Unity: `if (System.Environment.GetEnvironmentVariable("FARM_NO_RAIN") != null) return;`,
   GDScript/Godot: `if OS.has_environment("TIDES_NO_TIDE"): return 0.0`, JavaScript run by Node's runner or Vitest:
   `if (typeof process !== "undefined" && process.env.TIDES_NO_TIDE) return 0;`). A check that runs in a real browser
   (Playwright) can't see an environment setting: break it with a patch instead, `--break patch:breaks/no_tide.patch`
   (make the change, save it with `git diff > breaks/no_tide.patch`, undo the change, commit the patch). A switch is allowed inside simulation folders. It does nothing in normal use, and lets FoundationGuard prove the test
   really notices. Tell the owner in one sentence: "I added an off-switch for testing only; your app works exactly the same."
3. Register it:

       python fg/approve.py --behaviour "<their words>" --words "<what they said>" --check <test name> --break env:<SWITCH>=1

   It is added only if the test passes now AND fails with the switch on. If it says "not added", do what it says and run it again.

## 4. Save and upload the safe way
Save the changes with a short note (`git add -A` and `git commit -m "..."`), then upload ONLY with:

    python fg/push.py

It runs every test on exactly this version and uploads only if they pass. If the project has nowhere to upload to yet, say
so to the owner; run `python fg/structure.py` and `python fg/rules.py` yourself before each save instead. Never use `git push` directly (it's blocked),
and never use force options.

## 5. Tell the owner, in plain words
- what is now protected (their features by name, risky commands blocked, the guards locked, safe uploads, and the code-shape
  check: no file, class or function may grow past its limit, no new copy-pasted blocks, no new loops between parts of the
  project, no new tangled functions; what exists today is recorded and may only shrink; and no new plugin or outside library
  without their OK);
- that changes to the guard files will pop up asking for their OK, and that they should say no unless they asked for that change;
- that a nightly re-check is available (`examples/nightly.md`) if they want it.

## 6. When the code-shape check fails
A message like "tangled", "copy-paste" or "loop between systems" is about code you (the helper) wrote, never the owner's
job. Fix it before saving: split the function, move the copied block into one shared helper, or remove the include that
closes the loop. A "new dependency" message means you added a plugin or library: remove it, or ask the owner in plain words what it is, what
it costs and its licence, then run `fg/rules.py --allow` with their words. Do not raise the limits or re-record the baseline to make it pass; that needs the owner's OK, asked in
plain words ("The size record would have to go up because ...; is that OK?").


## 7. Where the pictures, sounds and music came from (ASSETS.md)
If setup says some picture, sound, model or font files have "no recorded source", fill in ASSETS.md one folder at a time.
Ask the owner in plain words, per folder: **"Where did the files in <folder> come from: did you make them, did an AI tool
make them (which one?), did you download them (from which website?), or did you buy them (where?)"**. If downloaded, open
the page yourself and copy the author's name, the link and the licence; don't ask the owner to read licence text.
Columns: Files (file or folder), Source (the title or pack name, shown in the credits), Made by (author, or the person plus the
AI tool), Licence, Link, Notes (private, not shown in the credits). With no internet, write what the owner remembers and add
"check page" in Notes. A game that will never be sold can say so in foundationguard.json: "assets": {"commercial": false}
(ask: "Might you ever sell this game or put it on a store?"; anything but a clear no keeps it commercial).
Licence words to use: CC0, CC-BY-4.0 (any CC version as written on the page), OFL-1.1 (fonts), MIT, own, AI-made (put the
tool's name in Made by or Notes), bought (link to the store page), unknown. Split a folder into more rows if its files came
from different places. When you add a new picture, sound or model yourself, add its row in the same save.
If a licence says NC (no selling) or ND (no changes) and the owner may ever sell the game, tell them in one sentence and
suggest a replacement. Run `python fg/assets.py --credits` to write CREDITS.md for the game's credits screen.


## 8. v0.7 habits (read once)

- **Secrets:** never write a password, key or token into a file. Read it from an environment variable. If the push says
  SECRETS FAIL, take the line out and tell the owner the key must be replaced (rotated), because it may already be in
  history. On first install run `python fg/secretscan.py --all` and tell the owner what it found, in plain words.
- **GitHub settings:** never change GitHub's settings, branch rules, secrets or hooks. If something there needs changing,
  tell the owner the steps (docs/GITHUB_PROTECTION.md) and let them click.
- **GitHub lock (v0.8.3):** until the project is locked on GitHub, every SUMMARY has a FOR YOU card "Your project isn't
  locked on GitHub yet". When you see it, offer to walk the owner through `python fg/lock.py --steps` before other work:
  read one step, wait for them to do it, then the next. Record "done" only with their own words
  (`python fg/lock.py --confirm --words "..."`), never your own.
- **Reviews:** when you write a check, don't review it yourself. Ask the owner to start a fresh helper session with
  REVIEW_PROMPT.md, and now and then offer `python fg/approve.py --spot` so they can paste it into a different AI model.
- **Weaker prompts:** if the owner's prompt says THIS LOOKS WEAKER, explain in one plain sentence why you asked, and
  accept a no.
- **Break glass:** only suggest `--break-glass` when the guard itself is clearly broken (it blocks everything, even a
  one-line safe change). Say that it will be recorded. More than one a month means the guard needs fixing; tell the owner.
- **Parts (developer mode):** don't change parts yourself. If the owner is an experienced developer and asks, show
  `python fg/parts.py` (every feature in plain words with its setting) and let them choose; `python fg/setup.py
  --developer` shows it at the end of setup. A beginner never needs it: everything stays on.

## 9. The project's docs (v0.8)

- Setup writes ARCHITECTURE.md, HANDOFF.md and REJECTED.md if they don't exist. Then ask the owner the "to fill in"
  questions one at a time, in plain words (for example: "In one sentence, what is your project?", "Is there anything that must
  never change?"). Write their answers in their words. Guess the technical parts yourself from the code and mark guesses.
- Every time you add a part (a new code folder), a plugin or a feature switch, add one line to ARCHITECTURE.md in the same
  commit saying what it is and why. Update HANDOFF.md at every push. When something is undone, add a REJECTED.md row.
- If DOCS FAIL says a path, switch or number in the docs is wrong, fix the doc (or ask the owner, if the code is wrong).
- If the project keeps its docs elsewhere (e.g. Docs/ARCHITECTURE.md), set "docs": {"architecture": "Docs/ARCHITECTURE.md",
  "handoff": "Docs/HANDOFF.md", "rejected": "Docs/REJECTED.md"} in foundationguard.json. Feature switches are found with
  "switch_pattern" (a regex such as "mygame\\.[A-Za-z][\\w.]*"; without a group it counts a name only where it starts in
  quotes, as a switch's definition does, so `mygame.kind` in ordinary code isn't one; with a group, the group is the name). A separate switch list can count as documentation:
  "coverage_in": ["Docs/ARCHITECTURE.md", "Docs/SWITCHES.md"].
- Once a week, and after each merge, offer the owner the fresh-session test in DOC_TEST.md.

## 10. Before the owner says yes: the forecast

Before asking the owner to approve a change or a merge, run `python fg/forecast.py --md` and show them the table, above
your own words. Point out any WORSE row in one plain sentence. Never edit the table. If the project has a seeded replay,
set "forecast_command" so game numbers (speed, food, "same world up to tick N") join it.

## 11. After every push: show the owner the SUMMARY

Every `python fg/push.py` ends with a block that starts with `SUMMARY:`. It is written by the kit, not by you.
- Show the owner that block exactly as printed, above your own words. Never reword, shorten or soften it.
- "Everything passed. Nothing needs your attention." means just that: tell them in one line and don't ask them anything.
- A card marked **[for the helper]** is yours to fix. Fix it and push again; don't ask the owner to decide it.
- A card marked **[FOR YOU]** is the owner's decision. Ask them its question in one plain sentence and give the card's
  recommendation. For new outside software, run `python fg/rules.py --allow "<name>" --words "<the owner's own words>"`
  only after the owner said yes in their own words; never allow it yourself. For "a check was made weaker", undo the
  weakening unless the owner asked for it.

## 12. Small print (answers to questions from the beginner test)

- **approve.py's options:** `--behaviour` is the feature in plain words; `--words` is what the owner actually said;
  `--check` is the test function's name (for pytest: `test_grow_makes_plants_taller`); `--break` is how to switch the feature
  off. An existing game switch that turns the feature off can be the break (for example `env:ff_burnt=1`); add a test-only
  one only when none fits. A never-change rule gets its own row when it has its own check; otherwise note it in the row of the
  feature it belongs to.
- **A new, unfinished part** doesn't need an approved row yet. Give it tests as you build it; ask the owner once it's finished.
- **HANDOFF's next steps:** ask the owner "What would you like to work on next?" and write their answer.
- **Forecast WORSE rows caused by the kit itself** (setup's first push, docs growing): say so in one sentence, e.g. "the
  biggest file grew because I added your docs; that's expected".
- **secrets_allow.txt** lines look like `path/glob a few words from the line   # why, in the owner's words`, for example
  `config/demo.ini demo_password   # owner: it's a fake password for the demo`. Only for a real false alarm. The owner's
  prompt will say THIS LOOKS WEAKER, which is right: explain in one sentence why it's a false alarm, and accept a no.
  The kit's own files (fg/) are never scanned.
- **docs_baseline.json** is written by setup; commit it with the docs. It lists what the docs don't cover yet (old debt).
- **The docs check reads files on disk**, committed or not (git-ignored files are skipped).
- **Feature switches**: by default, names read from environment settings (os.environ.get("X"), getenv, GetEnvironmentVariable,
  OS.get_environment) count as switches and must be named in ARCHITECTURE.md, the test-only "turn off" switches from step 3
  included. Set "switch_pattern" for another style, e.g. Unreal console variables "mygame\\.[A-Za-z][\\w.]*".
- **The forecast compares with** the version already uploaded; working alone on main before the first upload, with the
  last version that passed the gate, else the previous commit. The table's first line says which.
- **Reviews**: "REVIEW 0 of N" is a reminder, not a block (unless the owner turned require_review on). Offer the fresh-helper
  review after the first push, and again whenever a new check is added.

## 13. When the tests take long: the step-by-step gate (v0.8.5)

Do this when the push prints "NOTE for the helper: the tests took ... as one command", or when the owner says waiting
for the tests is slowing them down. The note is the kit's own measurement: it prints only when the tests took longer than
this project's limit ("slow_gate_minutes" in foundationguard.json, ten minutes unless the owner chose another), so when
you see it, split, whatever the number looks like to you. With no note and no word from the owner, leave the gate as one
command: that is simpler.

Why: one long command stops at the first failure and starts again from the top after every fix. On a project whose
tests take hours that turns one day's fixes into a week of waiting. Written as steps, every failure is listed in one
run, and after a fix only the failed steps and the steps guarding the changed files run again.

1. In foundationguard.json add "gate_steps", a list. Copy the shape from `examples/steps.foundationguard.json`. A step has:
   - "name": a short word; "command": what runs it;
   - "guards": the folders and files this step checks, **its own tests included** (for example
     `["src/save/**", "tests/save/**"]`). Be generous: a list that is too wide only costs time, a list that is too
     narrow can let a break through for a day;
   - "always": true for checks of slow rot (old saves still load, long soak runs, replays): they run on every new commit;
   - "needs": steps that must pass first (tests need the build). A step whose needed step failed is listed NOT RUN;
   - "test_log": the report it writes, if the approved list names its tests.
   Every test file must sit under some step's "guards": the gate stops and names any that doesn't. (One command
   found every test by itself; with steps, a test nobody listed would never run.) Write each command to run a folder
   or a pattern (`python -m pytest tests/saves`), not single files, and guard that same folder: then a new test in the
   folder is run and guarded with no further change.
   A step with no "guards" runs on every new commit. A changed file that NO step guards makes every step run, so list
   the docs under a quick step (a spelling or link check) if you don't want a doc change to run everything.
2. Changing foundationguard.json asks the owner. Tell them in one sentence: "I'm splitting your tests into N steps so a
   fix doesn't mean running all of them again. Every night all of them still run."
3. Schedule the whole run every night: `python fg/push.py --gate --whole` (`examples/nightly.md`). A kept result only
   counts while a whole run passed in the last day and a half; without the nightly run everything simply runs again.
4. `python fg/stages.py --plan` shows what the next gate would run and why. Use it instead of guessing.
5. Reading the report: `PASS ... kept` (its earlier pass stands), `PASS ... ran`, `MISS` (failed: its last lines are
   shown below), `NOT RUN` (a step it needs failed). Fix ALL the misses, commit once, push again.
   - `PASSED ONLY ON A SECOND TRY` or `MISSED ON A COMMIT IT PASSED BEFORE`: the check gives different answers with
     nothing changed. Tell the owner in one sentence and fix the check; never just run it again until it passes.
   - `!! name MISSED in this whole run ... Widen its guards`: that step's "guards" list is missing a folder. Add the
     folder whose change broke it. Never narrow a list to make a run shorter.
6. Never write to `.foundationguard/passed_commit` or `.foundationguard/gate_results.json` yourself. They are the
   record of what passed; the kit writes them, and the owner is asked if you try.

## 14. Would any test notice? The logic check (after v0.8.5)

`python fg/logic.py` takes the lines changed since the last upload. In a copy of the project it makes one small change
at a time (a comparison turned into its opposite, "and" for "or", a plus for a minus, a number one higher) and after
each one runs the tests that guard that file. A change that every test lets through is listed as NOT NOTICED: that
line could be wrong in that way and nobody would know.

Run it before you tell the owner a feature is finished, and before you add a feature to the approved list.

1. For each NOT NOTICED line, write a test that fails with the change shown, then run the check again. When the change
   cannot alter any result, write one line saying why in the hand-off notes and leave the code alone. Never reword
   code only to make a line drop off the list. Do not write "cannot matter" because one test failed to show a
   difference: in the kit's own trial a real gap needed three tries. Say what you tried.
2. Lines listed as NEVER BUILT OR LOADED BY THE TESTS are a different matter. The tests pass there even with text no
   language accepts, so they never build or load the line: it sits behind a compile-time switch that is off, or in a
   file no test loads. If it is a switch that is meant to be off (a break-on-purpose block, another platform), leave it.
   If it is a file or a function that the product uses, no test reaches it at all: write a test that loads it first.
3. It reports. It never stops an upload, and it cannot tell you the logic is right: it finds lines no test looks at.
4. It never touches the project. The changes are made in a copy in the system's temporary folder, removed afterwards
   (also when the run is stopped; a run killed outright leaves its copy, a folder named `fg-logic-...`, to delete).
5. Every change costs one run of the tests (and a build), so it is slow on a big project. `--max N` limits the number
   of changes, and the report says how many changed lines were left out. With the gate as steps (section 13) only the
   steps guarding the changed file run. A big project names what the tests need in the copy:
   `"logic": {"copy": ["Source/**", "Tools/**"]}` in foundationguard.json. Files git ignores are not copied, so the
   test command must be able to build from a clean copy.
6. `--exact` also moves each comparison's edge by one (`<` to `<=`) and changes bare start values (`n = 0`). Those are
   listed apart, under EXACT VALUE NOT TESTED. Use it for code where an exact limit matters (money, saved files, sizes,
   the last item of a list). Expect most of that list to be lines that cannot matter: in the kit's own test 6 of 8
   such reports could not alter any result. Say why in one line and move on; never write a test only to empty it.
7. A slow test command gets few changes done in the default 20 minutes: `--minutes N` raises it, and steps
   (section 13) keep each change to the tests that guard its file.
8. This is work for the helper, not a decision for the owner. Tell the owner one sentence at most: "N of the lines I
   changed were not checked by any test; I added tests for them."

## 15. Work while the owner is away (a night's run): plan around what still stops it

A box no one answers stops the session until the owner is back. The owner asked (12 Nov) for every helper that sets up
or uses the kit to know this list before an unattended run, and to plan the run around it.

**Before the owner leaves.** Ask whether they want their asks gathered for the run. If they say yes, set
`"gather_asks": true` in foundationguard.json; the change asks them, so do it while they are there. Once on, it holds at
every hour. The kit does not know day from night; the owner turns it off the same way. Do now, with the owner, anything
on the "still asks" list below that the run will need.

**Goes through with no box** (with the recommended list applied: `python fg/allowlist.py --apply`):
- ordinary edits, reading, building and testing in the project, and the kit's push (`python fg/push.py`, or the
  project's `push_command`);
- new tests: a new test file, or new tests added after the ones in a test file;
- a test not yet committed: edit it freely, move or delete it with `mv` or `rm` (with -f or -v only), or copy a file
  into its place, which is judged by its text as a new file is;
- with `gather_asks` on, changes to the tests, check scripts and lists the owner guards: loosening or removing a
  test, a new value in a pin file, `sed -i` on a test. Each one is written in the catch log, and the upload waits.

**Still asks at once, gathered or not.** Do these with the owner, or leave them for the morning:
- the kit and its settings: `foundationguard.json`, `fg/`, the AI tool's settings (`.claude/`), the git hooks,
  `.github/`, `AGENTS.md` and the other helpers' rule files, the approved list, the merge sign-off file, and files
  the owner set to "deny";
- re-recording the kit's records (`python fg/structure.py --baseline`, the rules and assets records) and switching
  a kit part (`python fg/parts.py set ...`);
- the AI tool's own box, from the recommended list: deletes (`rm`, `rmdir`, `git rm`, `git clean`, `del`, `rd`,
  `Remove-Item`), any push other than the kit's script, installs (`pip install`, `npm install`, `winget` and the
  like), and anything outside the project. A command the list doesn't allow asks too, unless the session's
  permission mode lets it through;
- `python fg/ownerok.py --give` and `python fg/push.py --break-glass`. Never run either during the run.

**Blocked: the command fails, with no box.** Take another way instead of retrying:
- `git push` straight (use the kit's push), force pushes, pushes of tags, deleting a remote branch, pushes to a
  protected branch, `--no-verify`, and changing `core.hooksPath`;
- git commands that throw work away: `reset --hard`, `clean -f`, `branch -D`, and `checkout` or `restore` over
  changed files. To get a file back as it was, use `git cat-file --filters HEAD:path > path` in bash (Git Bash on
  Windows). It also restores a file kept in Git LFS, such as Unreal's `.uasset` and `.umap`, where
  `git show HEAD:path > path` writes only LFS's small pointer file; the kit blocks that. In PowerShell, `>` turns the
  bytes into text, so run the line through bash or `cmd /c`;
- commits, merges and rebases while the folder is on a protected branch, and `gh pr merge` without the owner's
  sign-off line;
- heavy jobs while a program the project lists is running (for Unreal: no builds or tests while the owner's game or
  editor is open). This is `block_while_running` in foundationguard.json. Reading, searching or printing a job's
  script (`grep`, `sed -n`, `cat`, `git log`) is not a job and goes through;
- anything the project's own hooks block. Read them: in Claude Code, the hooks in `.claude/settings.json`.

**The upload during the run.** With gathered changes, the kit's push stops with "needs your yes" and lists them. That
is not a failure to fix. Stop uploading, keep working and committing in the folder, and go on with work that doesn't
need the upload.

**In the morning, tell the owner:**
- what waits for their one yes (`python fg/ownerok.py` lists it and why);
- every box and block of the run (`python fg/catches.py --asks`).

When they say "yes, ask me", run `python fg/ownerok.py --give`; the box asks them. Then upload.

## 16. "PUT BACK": the check after every step (Claude Code)

After every step, the kit compares the guard files with how they were before the step. If one changed without the
owner's yes, it is put back at once and the step ends with "FoundationGuard: PUT BACK: <file>". What was there is kept
in `.git/foundationguard/put_back/`, so nothing is lost. This happens whatever the command looked like, so a second
spelling never helps.

- Make a change to a guard file with the editing tools (Edit, Write) or a plain shell command the kit can read; its box
  asks the owner, and with their yes the change stays. New tests need no yes.
- Don't try again another way. Tell the owner what you wanted to change and why.
- "HELD" means the change was also committed in that step: the upload waits for the owner's yes
  (`python fg/ownerok.py` lists it).
- `git checkout`, `git switch`, `git pull` and `git merge` are fine: what they bring from existing history stays.
  Don't use `git stash` for guard files: a stash that takes away a test is put back. Commit on a work branch instead.
- `python fg/steps.py` lists any guard file that differs from the accepted state. Only the owner takes today's files
  as the accepted state (`python fg/steps.py --accept` asks them).

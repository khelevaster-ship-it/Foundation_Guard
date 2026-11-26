# FoundationGuard guide: every part, and installing by hand

AI-made (Claude). The short version is the [README](../README.md); the evidence is in [evidence/EVIDENCE.md](../evidence/EVIDENCE.md).

## The parts

| Part | What it does | File |
|---|---|---|
| **Command guard** | Blocks force pushes in the spellings it can read (below), pushes to main, deleted branches and tags, `reset --hard`, `clean -f`, discarded changes and history rewrites, including commands wrapped in `bash -c`, `eval`, `python -c`, env/sudo prefixes, chains and abbreviations, when the command is written out in the text. A command built on the same line counts as written out: a value set earlier on the line (`x="git push --force"; eval $x`, `read`, `printf -v`, `$'...'` quotes) and the words of a `$(echo ...)` are read in, and in a short program that runs commands any `git` text counts, even inside a string handed to `exec`. So is a command inside a function or braces, or after `if` or `while`, and the words handed to a function defined on the line or set with `set --`. In PowerShell, `Invoke-Expression`, a value set with `$x = "..."`, a script block and `Start-Process` are read; in cmd, `set x=...` with `%x%`, `call` and `start`. If the guard runs past its own time limit (20 s, `guard_time_limit`), it blocks, because the AI tool would otherwise let the command go ahead; a long command (over 8,000 bytes) is checked in a child process that is stopped at that limit, since a timer can't stop one long pattern match. Also blocks commands that change GitHub's own protection, and `git show` or `git cat-file` written over a file kept in Git LFS (that writes LFS's small pointer, not the file; the block names `git cat-file --filters`, which writes the file). Optional: no heavy jobs while a named program runs (`block_while_running`, `job_patterns`); only a part of a command that runs something counts, so reading or searching a job's script stays free. If the guard itself fails, it blocks rather than lets the command through. | `fg/guard.py` |
| **Tested-commit push** | Pushes only the exact commit that passed the gate. A git pre-push hook covers pushes by people and other tools, and refuses a push that would throw away commits on the remote branch (the remote's commit must be in what is pushed), however the push was written. A "break glass" push exists for when the guard itself is wrong, and it is written to `BREAKGLASS.md`. | `fg/push.py`, `fg/prepush.py` |
| **Approved list** | An owner-approved behaviour with no check, or whose check did not run and pass, fails the gate. | `fg/approved.py`, `APPROVED.md` |
| **Break-to-prove** | Each approved behaviour names how to break its feature. Its check must fail when it is broken, or the check is stale. | `fg/prove.py` |
| **Random re-break** | A few approved behaviours are re-proven at random every night and before each merge. | `fg/prove.py --random 3` |
| **Code-shape checks** | Files, classes and functions that balloon; a class spread over many files; systems reaching into each other's insides; copy-paste; loops between systems; tangled functions. Today's numbers are frozen and may only shrink. | `fg/structure.py`, `fg/design.py` |
| **Licence ledger** | Art, sound, music, models, fonts and video with no recorded source or licence; licences that forbid selling; AI-made files without the tool named. Writes a credits list. **Not legal advice:** it checks that a licence is written down and flags the common risky kinds; it can't tell you whether a licence fits your use. Most formats are known (`.png` to `.ktx2`, `.wav` to `.wem`, `.fbx` to `.vrm`, fonts and video); name your own in `"assets": {"extra_types": ["xyz"]}`. | `fg/assets.py`, `ASSETS.md` |
| **Rule checks** | Machine-dependent maths (trig, pow/exp/log, random numbers, clock reads) in folders you name, and a dependency allow-list (plugins, engine modules, libraries, packages, add-ons, Python imports, scripts loaded from the internet). New items need the owner's OK. | `fg/rules.py` |
| **Secret scan** | Stops a push whose added lines hold a password, key, token or private key. | `fg/secretscan.py` |
| **Weakening detector** | When a helper changes a guard file, the owner's prompt says if it makes a check weaker (a removed row or assert, a skip, a raised limit, a new exception). | `fg/weaken.py` |
| **Tiny-files check** | More than 5 new tiny files in one push fails: code chopped up to dodge size limits. | `fg/tiny.py` |
| **Docs pack** | Writes starter `ARCHITECTURE.md`, `HANDOFF.md`, `REJECTED.md`. Checks the docs tell the truth (paths, switches, numbers) and keep up (new systems, plugins, switches). A session-start hook makes each new AI session read them. | `fg/docs.py` |
| **Change forecast** | Before you say yes: before and after for tests, sizes, tangled code, copy-paste, risky maths, plugins, licence gaps, each marked better or WORSE. Runs on a throwaway copy. | `fg/forecast.py` |
| **Plain-words cards** | Every failure has a card saying what happened and what to do, and whether it is for the helper or FOR YOU. Every push ends in one summary. Facts about new outside software come from the project's own files. | `fg/cards.py`, `fg/depfacts.py`, `fg/summary.py` |
| **Catch log** | Each block, owner prompt and stopped push gets a dated line. An ask is written whole: the time to the second, which rule raised it, the tool and its file or command, and the box's text, so a helper that can't see your box can read what it said (`python fg/catches.py --asks`). | `fg/catches.py` |
| **Step-by-step gate** (v0.8.5) | For projects whose tests take long. The gate is a list of named steps: every step runs even after one fails and every failure is listed at once; each result is kept for the exact commit; after a fix only the failed steps and the steps guarding the changed files run again. A file no step guards makes everything run, and a test file no step lists stops the gate. A nightly whole run stands behind every kept result and names any step whose file list was too narrow. | `fg/stages.py`, `examples/steps.foundationguard.json` |
| **Developer mode** | Beginners leave everything on. Developers get one screen listing every feature in plain words and pick the ones they want: on, report-only or off, one at a time, "only these", or a preset. A helper switching a feature down needs the owner's OK. | `fg/parts.py` |
| **Logic check, part 1** (after v0.8.5) | Would any test notice? For the changed lines it makes one small change at a time in a copy of the project (a comparison turned into its opposite, "and" for "or", a plus for a minus), runs the tests that guard the file and lists the changes nothing noticed. Lines the tests never build are listed apart. It reports and never blocks, needs no AI, and cannot say the logic is right: it shows where nothing would notice if it were wrong. | `fg/logic.py` |
| **Saved state kept** (v0.8.6) | For each type you list that holds the game's saved state, every field must be in its save, its load and its fingerprint, or have a written reason of three words or more. A field left out comes back wrong after a load, or lets two different worlds look the same. Reads the text only (C++ and Python), takes under a second and stops the upload. `--suggest` finds the types that look like saved state. It matches names, so a field named in the save for another reason counts as kept. | `fg/state.py` |
| **Engine packs** | Finds Unreal, Unity and Godot and fills in sensible settings, maths presets, dependency rules and the engine's test command. | `fg/engines.py` |
| **Web pack** | Finds a browser game or web app by itself (a `package.json`, or an `index.html` with a script; also one folder down) and names its framework (Phaser, Three.js, PixiJS, Babylon.js, React, Vue, Svelte and others). It measures JavaScript and TypeScript and each HTML page's own scripts, and skips packages, build output and minified files. A Sim folder goes under the browser maths rule: `Math.sin`, `pow`, `exp`, `log` and the rest, `Math.random`, `**`, crypto random numbers and clock reads (`Date.now`, `performance.now`), because each browser may work these out its own way. A script loaded from the internet (a script tag, an import map, an import from a web address) is new outside software. Publishing or deploying (`npm publish`, Vercel, Netlify, Firebase, Cloudflare, GitHub Pages, itch.io's butler, surge) is the owner's step. The project's own tests (Node's test runner, Vitest, Playwright, npm test) run through one runner that writes one report, so the approved list sees each check by its own title. | `fg/engines.py`, `fg/webtests.py` |
| **Other AI tools** (EXPERIMENTAL) | The command guard also works as a hook in GitHub Copilot CLI, OpenAI Codex CLI and Cursor. Install writes their hook files and copies the helper rules into `AGENTS.md`, Copilot's and Cursor's rules files. | `fg/agents.py` |
| **Locked guard files** | An agent's edit to the approved list, checks, hooks, this kit or its config asks for the owner's OK (adding new tests does not; see the next row). So does a shell write through a folder named by a variable (`"$PWD/APPROVED.md"`, `"$CLAUDE_PROJECT_DIR/..."`, `~/...`, or a variable the kit can't know, taken as the project) or a glob (`APPROVED.m?`), and a patch (`git apply`, `git am`, `patch`) that changes a guard file; a patch the kit can't read asks. A guard-change report lists every such commit. | `fg/guard.py`, `fg/report.py` |
| **Check after every step** (Claude Code) | Reads what changed, not what was typed. After every step of a session the guard files are compared with how they were before it, and one changed without your yes, by the editing tools or a command (`sed --in-place`, a patch, a program of the helper's own), is put back after that step, unless a program was written to get round the kit. The helper is told why, the catch log has it, the next upload's report shows it FOR YOU, and what was there is kept in `.git/foundationguard/put_back/`. A change stays when the kit's box asked about that file in that step (worked out again from the step itself, so a step can't write its own yes; a yes covers the files its box named, never a git setting), when it only adds or removes permission rules in the AI tool's own settings (its "don't ask again"), when it only adds tests or moves a test, however it was written (with `gather_asks`, your own guard files too, which wait for your yes before the upload), when the kit's own gate wrote it (its record of a pass), and when a git checkout, pull or merge brought it from history that already existed. The kit's own settings file is judged first, by the copy last accepted, so a step that switches the guard off is put back before anything else is judged. A change made between steps (your editor, or a job a helper left running) is judged by its kind: your own files (tests, check scripts, lists) stay, and one that is more than new tests waits for your yes at the upload; the kit's records (what passed, your yes) and its switches (its settings, its code, hooks, `core.hooksPath`) are put back and the helper is told, unless a switch is exactly as the remote branch has it (you pulled a kit update). To keep a switch you changed yourself, run `python fg/steps.py --keep <file>` (the kit's box asks you; the put-back message names it), or ask the helper: it makes the change with the editing tool, and the box asks you. A guard file changed and committed in one step is held: the upload waits for your yes. `python fg/steps.py` lists any difference; `--accept` (it asks you) takes the files as they are now. Also watches Claude Code's Monitor tool, which runs commands too. | `fg/steps.py` |
| **Every copy guarded** | Install also guards each git worktree of the project and each checkout of the same remote (however its address is written: https or ssh, with or without `.git`, and Azure DevOps's three forms) beside it, in that copy's own `.claude/settings.local.json` (kept out of git), with the project's settings where the copy has none. Each AI session starts with one line saying whether the guard is live in its folder, and every upload summary names a copy that has no guard. `python fg/copies.py` lists them; `--cover` covers the rest, and adds this kit to a copy that only an older copy of the kit guards. A file inside another copy is judged by that copy's own settings (or by this project's, for a checkout of it with none), whichever folder the session opened in. It finds copies beside the project, not ones elsewhere on the computer. | `fg/copies.py`, `fg/guard.py` |
| **Adding tests is free** | A helper may add tests without asking: a new test file, or new tests between or after the ones in a guarded test file (setting `helpers_add_tests`, on unless you turn it off). Anything else still asks you, with the weakening finder as strict as before: a test changed, removed, renamed or skipped, a line slipped into a test, a name used again, a new line that changes what every test shares (a patch, an exit, a set-up step, or a shared value changed in place: `shared.config["value"] = 1`, `GlobalState.items.clear()`, in C++ `Shared = 0;` for a name the test didn't declare), the test runner's settings, the approved list and the kit. When a change to a test still asks, the box says why. A C++ test may set the members of values it made itself (`Params.Seed = 5;`), and a project's own test macros count (`MYHYDRO_TEST(Group, Name)`, `MYHYDRO_EXPECT(...)`). A test not yet committed (a night's own new test) is judged as a new file whenever it is edited, so it may be changed freely until its first commit; it must be that file itself, not a link or a second name for a committed one. Done with the editing tools; with the shell, a test not yet committed may be moved or deleted, and a file copied into a test's place (`cp`, `mv`, `git show REV:PATH > FILE`, `git cat-file --filters REV:PATH > FILE`) is judged by its text like Write; any other shell write to a test still asks. Your own check scripts whose names don't say "test" count too when you name them (`"test_files": ["Tools/Scripts/*_check.sh"]`): a new one adds freely, and every change to one already there asks. | `fg/adds.py` |
| **Away mode: answer the asks at one sitting** (optional) | `python fg/away.py on` before you leave (the kit's box asks you), `python fg/away.py off` when you're back for good; it sets `"gather_asks"`. When you come back, each session starts by saying how many changes wait for your yes, and tells the helper to explain every one on the kit's list to you in plain words (what changed, why, and whether a test now catches less: the kit starts those items with "This check now CATCHES LESS", or "This check MAY now CATCH LESS" when a check line changed and it can't tell) before other work, and never to give the yes itself. With `"gather_asks": true`, changes to the guard files you listed (tests, check scripts, your own lists) go through without a box each. The upload then waits until you have said yes to them all at once: `python fg/ownerok.py` lists them and why, and `--give` is your one yes. The kit, its settings, its hooks and its frozen numbers still ask at once, because they change the guard for the rest of the session. What waits is measured from what the remote itself has (`git ls-remote`), so moving this copy's record of the remote branch changes nothing. Until your yes nothing gathered goes up by any way the kit knows: its push stops, the gate records no pass, the git pre-push hook refuses a plain `git push` to any branch (whoever's key it uses), and the ways round the hook (`--no-verify`, `core.hooksPath`), a merge without your sign-off, and the helper giving the yes or writing it down are blocked or asked. The gathering is on at every hour once it is on; it doesn't know day from night. What still stops a run while you're away, and how a helper plans around it: AGENT_SETUP.md, section 15. | `fg/adds.py`, `fg/ownerok.py` |
| **Fewer boxes: a daily budget, plain boxes and a reviewer** (the owner, 16 Nov) | Every box opens with three sentences: WHAT CHANGES, WHAT COULD GO WRONG and MY RECOMMENDATION, then the kit's longer reasons. `python fg/catches.py --today` (or `--json`) counts today's boxes against `"ask_budget"` (default 5), and every session's first line says the count; over the budget it names the rules that asked most, so they become fixes. With `"review_lane": true`, a helper's technical change to your own guard files (tests, check scripts) opens no box: at the upload `python fg/review.py` hands each one to your reviewer program (`"review_command"`, a list; it reads the change as JSON and answers `PASS:`, `WEAKER:` or `WRONG:` and one sentence). A PASS stands in for your yes for that exact version; WEAKER or WRONG keeps your yes needed and shows you the sentence, and a later PASS doesn't clear it. Still always yours: the kit's own files and settings, files you list in `"owner_only"`, changes the kit judges weaker (a test taken out, a limit loosened), files committed without a yes, and tests that stopped running. Every verdict is a stamped line in `.git/foundationguard/proof/review.jsonl`. With `"box_hours": "07:00-23:00"` (the computer's own clock), every guard change asks in a box inside those hours, and the reviewer lane and gathered asks work only outside them. `"run_copies": ["../MyGameNight"]` leaves a copy a scheduled run owns out of the checks other copies' steps make, so a helper can keep working while the run writes its records there. | `fg/box.py`, `fg/catches.py`, `fg/review.py` |
| **Updating the kit in one step** | From the project's top folder run the NEW kit's copy: `python <new kit folder>/fg/update.py`. It checks every file against the `SHA256SUMS.txt` beside the new kit (a transfer folder) and changes nothing if one doesn't match, then replaces fg/ file by file and writes door lines, so no `steps.py --accept` is needed afterwards. Run it in your own terminal, or let a helper run it and answer the kit's box. Settings, hooks and tests are left alone (that's setup.py). | `fg/update.py` |
| **The kit's own GitHub App** (teams) | `python fg/app.py` (add `--public` when the account making it isn't the project's owner) opens a one-button page that makes the app with only the rights it needs, and prints the clicks that remain: install it on the project, an environment named fg-kit with main as its only branch, FG_APP_ID and FG_APP_KEY there. Then `kit_app_id` in foundationguard.json, and `python fg/lock.py` says ON only when main requires the note check from that app. For a first live run, `"remote_report_only": true` makes the check a neutral report that blocks and changes nothing. | `fg/app.py`, `fg/lock.py`, `fg/remote.py` |
| **A team: joining, logins and the drill** | A teammate's fresh clone: `python fg/setup.py --join` writes only never-committed files (`.git/foundationguard/local.json` with `me` and `gh_path`, and the AI tool's local hooks) and says who they are. In a team, a guard file exactly as GitHub has it (a pull, a merge, a kit update) is never put back; a switch counts only as main has it. Helpers can't run commands that read or change GitHub logins. `python fg/lock.py` names everyone's role, says CAN'T BE ON when the GitHub plan can't hold a change, and stays NOT ON while the owner's login or an admin login is on the helpers' computer. `python fg/lock.py --drill` tries to break the lock as the helpers' account (a team's lock is ON only after a passing drill in the last 30 days). `python fg/setup.py --lock` walks the owner through the lock, one checked step at a time. | `fg/join.py`, `fg/logins.py`, `fg/drill.py`, `fg/lockwalk.py`, `fg/lock.py` |
| **Recommended list for your AI tool's boxes** | So a helper can keep working without you at every step: ordinary edits and new files inside the project, routine reading, building and testing, your project's own test run word for word, the kit's push script and your project's own push script (`push_command`) go without your AI tool's own box. The Python rules also name the Python the kit runs with, by its full path (an engine's own Python, say). Guard files, settings, deletes, other pushes, installs and anything outside the project still ask, and the kit still checks every command and edit as strictly as before. Setup offers it and writes it only when you say yes. Your AI tool reads the settings of the folder a session opens in, so for sessions that open in another folder (a play copy beside the project) `--apply --for FOLDER` writes the list there, naming the project by its full path. Every run says which folder's sessions its list is for. See "Which box is whose" below. | `fg/allowlist.py`, `python fg/setup.py --allow-routine` |
| **Check-up** | `python fg/doctor.py` answers in plain words, one line each, and changes nothing: is the guard live for your AI tool here, does git's push check run (and is git pointed at other hooks), how uploads go, which test files and test settings are NOT guarded, which features are not fully on, is GitHub locked, are other copies guarded, is git told through the environment to use other hooks, and did Python's start-up files change since the last pass. Each line says OK or LOOK; it ends 1 when any says LOOK. | `fg/doctor.py` |
| **Receipts** | No receipt, no green. Every run of the gate, and of the checks you list in `expected_checks` (each with its exact command, how often it should run, `every_hours`, and the line its output must hold, `evidence`), leaves a receipt: "started" before it runs, "finished" after, with the exact code it ran on and where it ran. `python fg/receipts.py` gives each check one word: **PROVEN** (the only green: passed on exactly the code as it is now, changes not yet committed included), PASSED ON A RETRY (failed, then passed, on the same code), OUT OF DATE (passed, then the code changed, committed or not), FAILED, DID NOT FINISH (started and never ended), RUNNING, NEVER RAN, OVERDUE, and CLAIMED ONLY (a pass from a cloud session, or a receipt written or changed by hand). `run NAME` runs a listed check through the receipt runner; `show ID` looks one up, so a helper's "done" can quote its receipt. It writes `.foundationguard/status.json` for a status board. It only informs; the gate still does the blocking. | `fg/receipts.py`, `fg/proofstore.py` |
| **Alarm sorter** | When the gate fails, each failed test is run again three times on the same code and sorted: **REAL** (failed every time: fix the code, not the test), **UNSTEADY** (passed on some runs and failed on others, treated as real), **MACHINE** (no test report, or no tests in it: nothing was tested). The upload stays stopped. A test that failed on this exact code and passes when the gate is run again is UNSTEADY too: running it again until it passes is not a pass. Only you park a test, in `foundationguard.json`: `"parked": [{"test": ..., "since": "YYYY-MM-DD", "until": ..., "why": ...}]`, at most 3 at once and 7 days each, renewed once at most (the kit remembers each parking it used, so a third parking of the same test within 30 days doesn't hold). A parked test still runs and is shown, and stops uploads again when its time runs out. A test your approved list names, or one matching `never_park` (say `["*determinism*", "*save*"]`), can't be parked. It needs the gate's report (`test_log`) and `check_command`. Gates made of steps are not sorted by test yet. `python fg/alarms.py` lists what is parked. | `fg/alarms.py` |
| **Bite test** | Do your checks still bite? Every run of `python fg/prove.py` (which breaks each approved feature on purpose and runs its check) now leaves a stamped record of which guard, its verdict, the exact code and where it ran. `python fg/bite.py` gives each guard one word: **BITES** (its check failed when the feature was broken, on exactly the code as it is now), HOLLOW (it still passed with the feature broken), OUT OF DATE (it bit, but the code has changed since, committed or not), ALREADY FAILING, BREAK DOESN'T FIT, NO BREAK, NEVER TRIED, and CLAIMED ONLY (proven in a cloud session). `--pilot 10` proves ten guards and says how long all of them would take; `--refresh` proves again the ones that aren't BITES, for a nightly run. It writes `.foundationguard/bites.json` for a status board and only informs. | `fg/bite.py`, `fg/prove.py` |
| **Handoff checker** | Is the handoff note true? A note carries a facts block between `<!-- facts -->` and `<!-- /facts -->`, one fact a line: `commit 4f2a9c1`, `branch feature/x at 4f2a9c1`, `pushed 4f2a9c1`, `file path`, `no file path`, `contains path: text`, `check gate PROVEN` (the receipt word now), `guard F12 BITES` (the bite word now). `python fg/handoff.py NOTE.md` gives each fact one word: **TRUE**, **OUT OF DATE** (the branch has moved on past that commit), **WRONG** or **NOT CHECKED** (a line it can't read), and always says how many other lines of the note it did not check. No AI reads the note's free text. `python fg/handoff.py --write` prints a facts block for the code as it is now, to paste into the next note. It only informs; exit 1 when a fact is WRONG. | `fg/handoff.py` |
| **Night watch** | Did last night's work happen? List the jobs meant to run on a schedule as expected checks with `every_hours` (say 24), and run each through `python fg/receipts.py run NAME` from your scheduler. Each run has a time limit (`limit_minutes` on the check, else `check_timeout_s`): a stuck run is ended, with everything it started, so one hung job can't hold the whole night. `python fg/night.py` says per job **RAN**, **RAN ON A RETRY** (failed, then passed on the same code: said in the morning, not counted as clean), **FAILED** (the reason says if it was stopped at its limit), **DID NOT FINISH** (it started and never ended: the computer slept, or it was killed), **DIDN'T RUN** or **CLAIMED ONLY**, and writes `.foundationguard/night.json` for a status board. The first AI session after a bad night starts by saying which jobs didn't get done, and is told to tell you first. Silent when all is well; part `night` off turns it off. It only informs. | `fg/night.py` |
| **Reminders** | Three things that make people give up, said in plain words at the start of every AI session, only while they're true: Git or Python missing or too old (setup also checks this first and says how to get them); **"you are not fully protected yet"** while the project's GitHub copy isn't locked (it stops once the lock is on or you've confirmed it; it never asks GitHub at the start, so it's quick); and more than 5 yes-boxes yesterday or today, with how to find which files keep asking (`python fg/catches.py --asks`) and whether they need guarding. `python fg/ready.py` shows all three and the boxes per day for the last week; the check-up (`python fg/doctor.py`) has a line for each. Part `reminders` off makes the session message silent. | `fg/ready.py` |
| **Your OKs, once each** | Every yes you give (`python fg/ownerok.py --give`) is one line in the kit's proof store, with what you were shown. It covers that exact version of the item, once: the upload that carries it uses it up, so it can't cover a later change, even to the same text. It runs out after 24 hours (`ok_hours`), and a newer OK for the same item replaces it. A line written or changed by hand is no OK. `python fg/ledger.py` lists every OK: LIVE, USED, RUN OUT, REPLACED or NOT TRUSTED. | `fg/ledger.py` |
| **GitHub lock reminder** | Until the project is locked on GitHub, every summary says so and tells the helper to walk the owner through the steps. It asks GitHub read-only with the `gh` tool, found on the PATH, in its usual install folders (Windows, macOS, Linux) or at `gh_path`. When GitHub can't be asked (no gh, not signed in, no access), the summary says "could not check" and why, never "not locked". | `fg/lock.py`, `docs/GITHUB_PROTECTION.md` |

## Which box is whose

While a helper works, two things can stop it and ask you: the kit, and your AI tool itself. A helper that is waiting on
a box does nothing until you answer it, so it helps to know which is which and where to find them.

- **The kit's box.** Its text starts with "FoundationGuard:" and is one line: what it asks, why, and what to click.
  For example: "FoundationGuard: may the helper change 'APPROVED.md'? Why: it is a guard file ... To answer: choose Yes
  (allow) to let it go ahead, or No (deny) to stop it." It asks about a change to something that guards your project
  (a test changed or removed, the approved list, the kit or its settings), a "break glass" upload, your yes to a changed
  guard, a feature being switched, or writing the recommended list. Say yes only if you asked for it. A helper cannot
  answer it for you. The kit's box opens inside your AI tool's own permission box, so you answer it in the same place.
- **A block.** "FoundationGuard: blocked." followed by why. Nothing to answer: the kit refused the command and the
  helper was told why.
- **The kit's report** at the end of every upload. It starts "FoundationGuard: the kit's report on this upload". Its
  FOR YOU items are your decisions; the rest is for the helper.
- **A word to type**, only in a terminal you opened yourself: a four-letter code for `python fg/ownerok.py --give`
  (the kit's yes for when its box can't open), or "yes" when setup offers the recommended list.
- **Your AI tool's own box** (Claude Code, Copilot, Cursor). It has no "FoundationGuard:" label. The AI tool asks before
  it runs a command or changes a file, by its own settings, not the kit's. With the kit's recommended list (setup
  offers it; or tell your helper "add FoundationGuard's recommended list", which runs `python fg/allowlist.py --apply`
  and the kit's box asks you once) it no longer asks about ordinary edits and new files inside the project, routine
  reading, building and testing, your project's own test run, or the kit's push script (`python fg/push.py`). It still
  asks about the kit's guard files (fg/, foundationguard.json, the approved list, the frozen numbers, .claude/,
  .github/, .codex/, .cursor/, .git/), deletes, other pushes, installs, anything outside the project and any other
  command. `python fg/allowlist.py` shows the whole list; `python fg/allowlist.py --who src/game.py` says which box, if
  any, an edit to that file opens. The list works only for sessions that open in the folder whose settings hold it.
  If your sessions open somewhere else (a play copy beside the project), `python fg/allowlist.py --apply --for
  "C:\MyGame"` writes it for them (into that folder's `.claude/settings.local.json`, kept out of git), and `--settings
  FILE` writes exactly the file you name. Each run says which folder's sessions the list is for, and names any other
  copy where your AI tool has opened sessions on this computer.

**Where to find a waiting box.** It is in the window where the helper's session runs: the terminal, or the session in
your AI tool's app. In the Claude app, a session running on your own computer may be listed in the Code view, not under
Remote Control. Your phone may not show these boxes at all, so a session can sit waiting while you see nothing. When a
helper seems to have stopped, open its session on the computer it runs on and look for a box.

**How you learn that a helper is waiting.** The kit can't reach your phone. So the kit asks every helper (AGENT_SETUP.md)
to post a one-line note where you will see it (the chat or thread you gave it the work in) before a step that will ask
you, and again if it is left waiting: what it is waiting for, in which box, on which computer. Each of the kit's
questions is also written to `.foundationguard/catches.log` with the time ("asked owner").

## Install

One step: copy the `fg` folder into your project, then from the project's top folder run `python fg/setup.py`
(add `--solo` if nobody else reviews your work; add `--developer` to see the feature screen and pick what you want
on). It finds your tests, writes the settings and installs everything.
Then run `python fg/approve.py` for each finished feature. Restart your AI session afterwards so the hooks load.

By hand (about 10 minutes):
1. Copy the `fg` folder into your repository.
2. From the repository root: `python fg/install.py`. This adds the Claude Code hook, the git pre-push hook, and starter
   `foundationguard.json` and `APPROVED.md` files.
3. Edit `foundationguard.json`: protected branches, your gate command (your full test run), the test log it writes
   (JUnit XML, or lines `PASS name` / `FAIL name`), and `check_command` (how to run one check, with `{check}`). If setup
   did not find your tests, this is the shape (here, a Godot project with its own small test runner):

       {"protected_branches": ["main"],
        "gate_command": "python tools/run_tests.py --log .foundationguard/test_log.txt",
        "test_log": ".foundationguard/test_log.txt",
        "check_command": "python tools/run_tests.py --only {check}"}
   If your gate writes a file of its own on every run that is also a guard file (a "tests passed" file, say), list it
   in `"gate_records"`, so a pass isn't taken as an edit waiting for your yes (F354).
4. Add a row to `APPROVED.md` for each behaviour the owner signs off:
   `| A001 | Old saves still load | "Yes, keep that" (owner, date) | test_old_saves | env:SAVE_COMPAT=0 |`
   The last column breaks the feature on purpose: `env:NAME=VALUE` or `patch:path/to/break.patch`.
5. Push only with `python fg/push.py`. Prove everything once: `python fg/prove.py --all`. Schedule the nightly re-break
   (`examples/nightly.md`).
6. If your tests take more than a few minutes, write the gate as steps (`examples/steps.foundationguard.json`) and
   schedule the nightly whole run (`python fg/push.py --gate --whole`). `python fg/stages.py --plan` shows what the next
   gate would run and why. Pick features any time with `python fg/parts.py`.

**Windows, without installing Python.** Open `FoundationGuard-Setup.exe` (the Windows download). It installs for you
only, asks no administrator question, and brings its own small Python, so nothing else needs installing but Git and
your AI tool. It is not signed in the beta, so Windows first shows "Windows protected your PC": choose "More info",
then "Run anyway". Its last page shows one sentence: paste it to your AI helper, opened in your project's folder, and
the helper does the rest. Don't remove FoundationGuard from "Installed apps" while a project still uses it: the
safety checks in that project would stop without telling you (`python fg/doctor.py` says so on its "Kit's Python"
line). To take the kit out of a project, see "Removing the kit" below first.

**Windows, with your own Python.** The kit needs Python 3.10 or newer (the oldest version its own tests run on). On many Windows PCs the word `python` opens the Microsoft Store and
does nothing: install Python from python.org first (tick "Add python.exe to PATH"), or run setup with the full path of a
Python you have. Setup writes that full path into every hook, so they work even where `python` does not. Save
`foundationguard.json` as UTF-8 (the kit also reads files Windows PowerShell saved). To see that the guard is live from
Windows PowerShell, pipe the command in, since PowerShell strips inner quotes from arguments:
`'bash -c "git push --force"' | & <python> fg/guard.py --check -` must print BLOCK.

**A changed guard waits for you.** When a helper changes the kit's settings or code, or makes a check weaker, the
upload stops until the owner says yes: `python fg/ownerok.py --give`, in a terminal (you type a short code it shows). Before the code it lists, in plain words, each thing your yes covers, what changed and the helper's reason from its commit (F307).
A helper's command window is not a terminal; a helper that runs it, in the ways the kit can read, opens the kit's
box instead, which only you can answer. Changing the file again needs a new yes.

Unreal projects: see `examples/unreal.foundationguard.json`. To lock the guards on GitHub: `docs/GITHUB_PROTECTION.md`.


## Removing the kit

Nearly everything the kit installs is inside your project folder, so taking it out is one list of deletes (the one
thing outside it is a small key folder in your home folder, below). Your code, your tests and your history are not
touched. The owner does this in their own terminal; a helper that tries meets the
kit's boxes, as for any change to a guard file. (Tried by hand on 18 Nov 2026 on a small Python project on Linux:
afterwards its tests passed and a plain `git push` worked. Not yet tried through a helper, on Windows, or on a
project with several copies.)

From the project's top folder:

    git rm -r fg foundationguard.json APPROVED.md STRUCTURE_LOG.md BREAKGLASS.md
    git rm docs_baseline.json rules_baseline.json structure_baseline.json assets_baseline.json
    git rm .codex/hooks.json .cursor/hooks.json .cursor/rules/foundationguard.mdc .github/hooks/foundationguard.json
    rm -rf fg .foundationguard .git/foundationguard .git/hooks/pre-push .claude/settings.local.json
    git commit -m "remove FoundationGuard"

(If git says a name "did not match any files", that file was never made on your project: leave the name out and
run the line again. APPROVED.md is your own list of approved behaviours: keep it if you still want it.)

Then the things the list above leaves to you:
- **Your AI tool's settings, `.claude/settings.json`.** If the kit made this file (you had none before setup), delete
  it too. If you had your own, setup added to it: take out the hooks whose command names `fg/`, and the allow and ask
  rules you didn't write. The file's history (`git log -p .claude/settings.json`) shows what setup added.
- **The Windows download.** If you installed FoundationGuard with `FoundationGuard-Setup.exe`, remove it last, and only
  when no project uses it any more: Windows Settings, "Installed apps", FoundationGuard, Uninstall. (Not yet tried by a
  person on a real PC; the build's own check installs it but does not remove it.)
- **The starter docs** (ARCHITECTURE.md, HANDOFF.md, REJECTED.md) are yours by now. Keep them or delete them.
- **The `.foundationguard/` line in .gitignore** is harmless; take it out if you like.
- **The rules copies for other AI tools.** If you ran `python fg/agents.py --rules`, AGENTS.md and
  `.github/copilot-instructions.md` hold a copy of your CLAUDE.md with a first line saying the kit wrote it. They are
  your project's rules, not the kit: keep them, or delete them if nothing reads them.
- **`.claude/settings.local.json`** (deleted above) holds this computer's hooks. If you had your own settings in it,
  take out only the hooks whose command names `fg/` instead of deleting the file.
- **The key folder in your home folder**, `.foundationguard` (on Windows `C:\Users\<you>\.foundationguard`). It holds
  the key the kit stamps its records with, and the key of the kit's GitHub app if you made one. Other projects that
  use the kit share it: delete it only when no project of yours uses the kit any more.

If the project is locked on GitHub with the kit's required check, switch that check off in the branch's rules first
(`docs/GITHUB_PROTECTION.md`), or uploads will wait for a check that no longer runs. Then delete
`.github/workflows/foundationguard.yml`, and the kit's lines in `.github/CODEOWNERS` (or the file, if the kit wrote
all of it). On GitHub you can also remove the `fg-kit` environment and uninstall the kit's app. Other copies of the project
(worktrees, second checkouts) each have their own hooks: repeat the `rm -rf` line in each. Restart your AI session
afterwards.


## Proving a check by breaking its feature

A check is proven by breaking what it guards and watching it fail. Prefer a switch (a `my.*` setting, or `FG_BREAK`
for the kit's own rules): nothing needs undoing. When the break has to be a code edit, keep it as a patch file:

    git apply break.patch && <run the check and record that it fails>; git apply -R break.patch

`git apply -R` takes back exactly the patch and is allowed. `git checkout -- FILE` and `git restore FILE` are blocked
because they throw away every change in the file, not only the break. A patch touching a guard file asks the owner
both ways. If `git apply -R` refuses (the file changed in between), stop and ask; never restore the file another way.

## All known limits

- **What ran is evidence only if the change can't choose what's loaded into the runner, or write the report.** Locked:
  conftest.py, pytest.ini, tox.ini, jest/vitest/playwright configs, the runner's lines in pyproject.toml, setup.cfg,
  package.json and .ini files, and test files that reach into the runner (pytest_plugins, hooks, `_pytest`). Not locked:
  code those already load (a package conftest.py imports on main), and a report file the game itself can write (Unreal's
  -ReportExportPath JSON). One yes on a locked runner file covers every line in it; the note says so.

- Where a proof ran (this computer, CI, or a cloud session) is read from the session's own settings (CI,
  GITHUB_ACTIONS, CLAUDE_CODE_REMOTE). A cloud session is never taken for CI, and the guard refuses a kit command
  that sets or clears them (F343, F344), but a script the kit never reads could still do it. Each computer keeps its own
  proof store and key, so another computer's receipts never reach this one's.
- Upgrading the kit from inside an AI session: the session's hooks are the ones it started with, so the step that
  runs the new install is checked by the older kit. An older kit whose session lacks the check after each step puts
  the install's changes back, and running more kit commands in that session meets the same hooks (the game's PC, 14
  Nov). So upgrade from a plain terminal with no AI session open: run the new kit's install, then
  python fg/steps.py --accept  (the owner takes the files as they are now), then  python fg/steps.py  (it should say
  all as accepted). Each folder keeps its own accepted state, so if sessions start in another copy (a play copy),
  run  python fg/copies.py --cover  from the project and then that same  steps.py --accept  with the copy as the
  current folder, before any session opens there. Then start a new session, where the helper walks the owner through  python fg/ownerok.py  before
  the owner's  --give. A kit from this version on asks before an install, and its yes keeps them.
- The lock reminder at the start of a session remembers GitHub's answer for a day, in the kit's state folder; a
  helper that rewrites that file can quiet the reminder until the next check (the upload's own lock check still asks
  GitHub).
- The night watch doesn't start jobs: your computer's scheduler (Task Scheduler on Windows, cron or launchd elsewhere)
  runs `python fg/receipts.py run NAME`; the kit times each run, ends a stuck one, and says in the morning what didn't
  happen. A program that a job deliberately detaches from itself (a new session on Linux or macOS, or one started
  outside the job on Windows) can outlive the time limit; the job's own run still ends and is marked stopped.
- Only Claude models were tested as helpers (two smaller ones in the weaker-helper tests). Other companies' models were
  not tested. Round 1 had one run per task per model; round 2 had five, and the same model behaved differently from run
  to run.
- The Copilot CLI, Codex CLI and Cursor adapters were tested with each tool's documented hook input, not inside the real
  tools. Codex and Cursor cannot ask the owner, so a guard-file change is refused there.
- Unity was tested on Unity 6.6 only; Unity 2022.3 is untested. Godot was tested with GUT 9.3.1; gdUnit4 is untested.
  Those two engine runs were on Windows with small sample projects. Most other tests ran on Linux.
- The web pack was tested on Linux only, with Node.js 22, Vitest 5.1 and Playwright 1.63, on two small sample games the
  kit's author wrote. No real web project and no Windows or macOS web run yet.
- Browser maths: frame time the browser hands the game (requestAnimationFrame's timestamp, a delta passed in) is not
  seen; give the simulation a fixed step. `Math["sin"]`, `with (Math)` and a seeded library that replaces
  `Math.random` (it still counts) are not read right. Code fetched at run time from an address built in code is not
  seen as outside software, and stylesheets and fonts from the internet are not listed (fonts kept in the project are
  in the licence ledger).
- Browser code can't read an environment switch. For a check that runs in a browser, break it with a patch
  (`patch:breaks/x.patch`) or have the test set a flag the page reads. Jest writes no report without an add-on, so a
  check run by Jest is judged by the exit code alone.
- Comparisons: lizard was run for real. The two hook packs were ported pattern for pattern and checked by reading, not
  run as shipped.
- All benchmarks are planted tests written by AI helpers. The real projects so far are one Unreal game (the one it was
  built for) and one Godot game. Real-world catches belong in the catch log.
- New outside software facts come from local files only, with no internet lookup. "Made weaker" is a guess from text.
- Known misses: a C/C++ maths call built by token-pasting in a macro (`##`) is not seen by the maths rule. The
  tangled-code check counts the indentation of a long multi-line Python literal (a dict or list spread over many lines)
  as nesting, so it can flag such a function by mistake.
- Break-to-prove shows a check fails when its feature is broken. It does not show the check covers every way to break it.
- The step-by-step gate trusts each step's list of the files it guards. If a list is too narrow, a break in a file
  outside it can pass until the next whole run (a day and a half at most, less with the nightly run). The whole run then
  names the step. Nothing is kept when a changed file is guarded by no step.
- With steps, the gate stops when a test file is in no step's list. It cannot see whether the step's command really
  runs every test file in that list: a command that names single files will not pick up a new test beside them. Write
  commands that run a folder. Approved features are covered either way wherever the tests write a report (the default
  after setup): an approved check that did not run fails the gate.
- Adding tests is free only when the change looks like new tests and nothing else, judged from the text. An added
  test can still change what other tests see in ways this does not read (a C++ file-level object that changes a shared
  value when it loads, or a test that rewrites another file while it runs). The ones it knows (patches, exits, set-up
  steps, `.only`, `#define`, Unreal's `GetMutableDefault`, a shared value changed in place: an item set, a call such as
  `.clear()` or `.Empty()`, a C++ name the test didn't declare set bare) still ask. A function the test calls that
  changes shared values inside it (`game.reset_world()`, `random.seed(1)`) is not read. In C++, a member set on a value the new lines
  declared counts as the test's own; a reference bound to something from elsewhere (`MySettings::Get()`) still asks,
  and a pointer or a global object reached another way is not followed. Break-to-prove on the approved list still catches an approved check that no
  longer bites, at the nightly re-break or the next `prove.py --all`. A new check script you named in `test_files` is
  taken whole: what it does when it runs is not read, so name only scripts that run on their own (not files another
  test loads).
- The check after every step runs in Claude Code only (its PostToolUse hook); Copilot CLI, Codex CLI and Cursor get the
  command guard alone. It is a safety net on the same computer: a program written to get round it can rewrite the
  kit's own record of the accepted files (in `.git/foundationguard/`) or call the kit's record door for the kit's own
  records. A change made outside any helper step is judged by its kind (fg/between.py): the kit's records and switches
  are put back, your own files stay. A file over 5 MB is checked but can't be put back (the helper is told to stop). A
  write that lands while a later step is running is judged as that step's. A `git stash` that takes away a guard file (even a new test) is put back too, and the `git stash pop`
  after it then fails; a pull whose remote can't be reached is put back as well. Commit guard-file changes on a work
  branch instead of stashing; the kit's own messages no longer suggest a stash (F261). A change of spaces and line
  breaks only (a formatter) stays (F260). `git checkout -- file` and `git restore file` are blocked even when the file
  has no changes: the kit can't know that before the command, because a command earlier on the same line may change it. Git's settings files (`.git/config`, a worktree's `config.worktree`
  and your own `~/.gitconfig`) are compared by their risky settings only (F254 to F257): the hooks folder, programs
  git runs (aliases, filters, drivers, fsmonitor, ssh, editors, credential helpers), files pulled in, and where an
  existing remote points. One a helper changes in a step without your yes is put back; ordinary settings, Git LFS's
  own lines and a new remote stay. So a helper's `git remote set-url` or `gh auth setup-git` is put back too: run
  those yourself, between steps: a remote or credential helper you change then stays, but the hooks folder
  (`core.hooksPath`) and included settings files are put back even then, because they can switch the kit off (F266). Git settings handed in through
  environment variables (`GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`) are refused in a command (F294), and the kit's upload drops
  the ones that switch its hooks off (F295); a script the kit never reads can still set them. The test runners' settings files are guard files even before
  they exist (F299), and their environment settings (`PYTEST_ADDOPTS`, `PYTHONPATH`, `NODE_OPTIONS`) are dropped by the
  upload and refused on its command line (F300, F301); a gate that needs `PYTHONPATH` sets it in its own command. Receipts and OKs live in `.git/foundationguard/proof/`, stamped with a key in your home folder (`~/.foundationguard/stamp.key`): a program on the same computer that reads that key can still write a line that looks right, so they stop a helper's shortcut, not a determined attack. Python's start-up files outside the project (`sitecustomize.py`, `.pth` files in site-packages) can change what the tests import: the kit can't stop that, but names a new or changed one at the upload and in the check-up (F303, F304). A test that passed at the last pass and doesn't pass now stops the upload until you say yes (F302); that only works when the gate writes a test report (`test_log`). The computer-wide git settings (they need admin) aren't
  compared. Two helper sessions working in one folder at once can each put back the other's change
  (it is kept). Steps run one at a time in Claude Code; the check assumes so.
- The command guard reads the words of the command. A command built on the same line is read in (F222, F229 to F232),
  but words that come from a file, the environment, another program's output or arithmetic in a program
  (`'g'+'it push'`, PowerShell's `'git' + ' push'`) are not known before the command runs. On Windows it reads the
  PowerShell and cmd forms named above; other ways those shells build and run text (a `[scriptblock]::Create(...)`,
  a .ps1 or .bat file) are not read, as script files in bash are not. A helper's own program can also open a terminal of its own and type the owner's
  four-letter code for `fg/ownerok.py --give`. The owner's box opens for the yes script however it is run (F236), but
  the yes the kit takes is still a file on this computer. These need a program written to get round the kit, and the
  real lock is GitHub's (below).
- With the asks gathered, the upload is held back on this computer: by the kit's push, the git pre-push hook and the
  hook's blocks on the ways round it. A push written inside a script file the hook doesn't read, run with
  `--no-verify`, or a call straight to GitHub's web API with a key, is not seen here. Only GitHub's own lock on a
  branch (required reviews on main) stops that; a work branch such as `wt/weather` has none.
- The recommended list goes into Claude Code's settings only. Copilot, Codex and Cursor keep their own lists.
  Claude Code decides how a rule matches a command: a rule such as `Bash(grep:*)` may also cover a grep whose output is
  sent into a file. The kit still asks about any write into a guard file. Its rules name Claude Code's Bash and edit
  tools; a command run through its PowerShell tool on Windows still opens its box. `--who` and the kit's tests read
  the rules the way Claude Code's permissions page describes (ask above allow, "/" is the project's top folder); the
  kit can't run Claude Code itself to confirm it.
- A list written for another folder (`--for`) names the project by its full path (`Edit(//c/MyGameWT/**)`) and adds
  it to `additionalDirectories`, as Claude Code's permissions page describes for full paths and Windows drives; the
  kit can't run Claude Code to confirm it. Which copies have had sessions is read from the folder names Claude Code
  keeps for them (in `~/.claude/projects`), so it is a hint: a session folder that isn't a copy of the project, or
  records that were cleared, are not seen. The Python rules match the command as typed: a Python called by a path the
  kit isn't running from still asks.
- The kit judges a shell command by its text. A command that only reads or lists (cat, head, tail, ls, wc, grep, rg,
  diff, git status, diff, log, show and blame, PowerShell's Get-Content and Select-String, or Python opening a file to
  read) never asks, unless it also runs other code (`$(...)`) or writes a file. Any other command that names a guard
  file beside a word that writes still asks, even when it only reads, such as running `fg/install.py`. A copy out of a
  guard file (`cp APPROVED.md /tmp/x`) only reads it and doesn't ask. A short Python program in the command
  (`python -c`, `python - <<'EOF'`) is read with Python's own parser (never run): when every file it could write is a
  plain path in it, it is judged by those files alone; one the kit can't follow (another module, `os.remove`, `exec`, a
  path from a variable set twice) counts as a write, and any guard file it names asks. A Python script run from a file
  (`python fix.py`) is not read. Running a guard script (`bash Tools/Scripts/x_check.sh`) beside writes of other files doesn't ask.
  A write through a shell variable makes the whole line count, unless the line's own loop (`for A in 1 2 3`) or
  `set --` gives the variable plain words before the write and inside the same loop: then each of those words is put
  in. A variable from anywhere else (the environment, `read`, `A=...`, a loop over files, `eval`, a subshell) could
  point anywhere. On Windows, Git Bash's `/c/...` paths are read as `C:/...`. A path inside another copy of a project
  is judged by that copy's own settings, but only when the kit running for the session is this version or newer: a copy
  guarded only by an older kit needs `fg/copies.py --cover` from this one. A folder that has no kit settings and is
  not a checkout of the project (another remote) is not guarded.
- The kit's own checks run without pytest (`python tests/run_without_pytest.py`), but it gives them only what they use
  from pytest (a fresh folder, monkeypatch, skip). A check that needs Node.js or pytest is listed as not run, and for
  those the kit's CI on the same commit is the evidence.
- The owner's own guard folders (guard_paths, such as tests/) are covered by the edit allowance, so that adding a new
  test stays free. Every other change there is asked by the kit's own box, which Claude Code shows even when an allow
  rule matches (its hooks page: a hook can "force a prompt"). Copilot, Codex and Cursor answer the kit's hook in their
  own ways (fg/agents.py).
- A helper waiting at a box can't tell you so by itself unless it was asked to; the kit asks it to (AGENT_SETUP.md),
  but nothing in the kit checks that the note was posted.
- The records of what passed are files on the same computer. A helper is asked before it writes one in the ways the kit
  reads (an edit, a shell write, a folder variable, a glob, a patch), but the guard reads commands, not the programs
  they start. Only the lock on GitHub with a required check cannot be got round from there.
- Outside review 6 (Grok, 13 Nov) showed more of what a script the kit never reads can do on this computer. The kit's
  own code is a file: a script can rewrite the check that is meant to judge it. A push inside a script can skip the
  push hook (`git -c core.hooksPath=/dev/null push`) and leave no trace. The owner's yes covers a file, not what is
  written into it: a harmless `sed` on a test can cover a script that loosens the same test in the same command. A save
  the owner makes while a helper's step is still running is judged as that step's, and put back (the copy is kept).
  Only the lock on GitHub stops the first two.
- The owner's yes in a step is worked out a second time after the step, from the step's own input. If that second
  reading names fewer files than the box did (a glob that matched before the step and not after), or fails, a change
  the owner said yes to is put back (the copy is kept), and the owner says yes again.
- A file a checkout or pull brings stays when the kit trusts the commit: the history there was when the kit was first
  installed, a commit that was HEAD at a check while every guard file was as it has it, or a remote branch tip git
  ls-remote confirmed. A script that first pushes its commit to the remote (a push hidden inside a script) makes that
  commit trusted, and a program can rewrite the kit's list (`.git/foundationguard/seen.json`; removing it only takes
  trust away). Real work can be put back too (the copy is kept): a checkout of a branch you made in your own terminal
  and left before the helper's next step, a merge of a fetched branch while the computer is offline, a tag or a remote
  other than origin. To keep the branch's copy, ask the helper to write it back: the kit's box asks you, and
  your yes keeps it.
- Removing the kit's whole folder in git's folder (`.git/foundationguard`) makes the next state the accepted one, as
  at a first install. Only the lock on GitHub stops that.
- Git's settings: the kit puts back a known risky setting changed in a step (programs git runs, where a push goes, the
  hooks folder) and reports one it doesn't know. It can't see `git -c key=value` on a single command (that changes no
  file), the computer-wide settings, keys git adds in later versions, or files in the project that set things
  (`.lfsconfig`, `.gitmodules`, `.gitattributes`).


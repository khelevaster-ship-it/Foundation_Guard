# Changelog

Newest first. F-numbers are rows in `APPROVED.md`. Dates are 2026. Scores are before any fix unless marked post hoc.

## Next version (not yet released): Windows CI green, a guard that fails closed, and web projects
- **An update with no yes from the owner changes nothing** (F508; 20 Nov). On the game's PC a helper ran the
  kit's `update.py` and no box opened. All 22 files were copied, the check after the step put back the 6 guarded
  ones, and the kit was half old and half new until the owner ran it himself. The update now looks for the owner
  first (their terminal, or their yes in the kit's box) and stops before copying anything. The box was missing
  because Python was kept in a variable (`"$PY" fg/update.py`, the spelling the kit's own install note gave); that
  spelling and a kit file run as the command word now ask (F509). And loading `fg/install.py` as a module, as a
  "does every file load" check did, no longer runs the install (F510).
- **Your own kit update is not asked again at the upload** (F519; 20 Nov). The owner updated the kit himself in
  his own window, and the upload then asked his yes for "what the helper changed", marked "MAY now CATCH LESS". A
  kit file that is exactly as the owner's own kit command wrote it no longer needs a second yes.
- **A file named only in sed's replacement text is not a write to it** (F520; 21 Nov). A notes line edited with
  `sed -i "s|old|new text naming a guard file|" notes.md` asked the owner, though only notes.md was written. For
  one plain substitution only the files after the script count now. A guard file among them still asks.
- **A > inside quotes is not a redirect** (F521; 21 Nov). A search for `"PC->God[A-Z]*("` asked the owner about a
  redirect into the game's project file. Quoted text is a string to the shell; quoted text a shell runs
  (`bash -c`, `eval`, `find -exec`) still counts.
- **A gathered change says no box is open** (F522; 21 Nov). The step's output now says "NO BOX NOW: ... the owner's
  yes for it is asked at the upload", so the helper doesn't tell the owner a box is up.
- **The upload's box stays short with many changed rows** (F523; 21 Nov). It named all 28 approvals whose row moved
  in a record file. It now names the first and counts the rest; `python fg/ownerok.py` still lists every one.
- **A record named like a test is not a test** (F524; 21 Nov). Docs/TEST_PROOFS.md, a proof record, asked the owner
  at every upload because of "TEST_" in its name. Text files outside a tests folder no longer count as tests by name.
- **Notes written by a Python program don't open the upload box** (F525; 21 Nov). Text fed to Python that said "one
  safe_push.sh upload" asked the owner's yes. Text the shell itself would run still counts.
- **The size check runs before the upload's yes box** (F526; 21 Nov). The owner said yes, then the size check stopped
  the upload, and the fix asked a second yes. A missing yes with a failing size check now stops before the box.
- **A helpers file in a tests folder says why it asks** (F527; 21 Nov). The box said "it is not a test file"; it now
  says the file's name doesn't mark it as one, so the kit can't tell its lines only add tests.
- **The box shows where a long line changed** (F528; 21 Nov). A long row changed late in the line showed the same
  text on both sides. Each side now starts just before the first difference.
- **One more test proven is not "catches less"** (F529; 21 Nov). A record's proven count going up was called a
  frozen number going up. Numbers in text records are now judged by the words just before them.
- **A yes'd edit stays when another step ends first** (F530; 22 Nov). A read-only step running beside the owner's
  yes'd edit ended first and put the edit back. The file stays when it is exactly what the yes'd edit makes.
- **Boxes by the clock** (F531; 23 Nov). `"box_hours": "07:00-23:00"` asks every guard change in a box inside
  those hours, even with the reviewer lane or gathered asks on. Overnight they work as before.
- **A yes in the box is not asked again at the upload** (F532; 23 Nov). With the reviewer lane on, a change the owner
  allowed in the box was listed again at the upload. That exact version now counts as answered.
- **A yes in the box reaches the other copies** (F533; 23 Nov). The night rehearsal's checkout put back a file the
  owner had allowed in the work copy. A version allowed in the box in one copy is kept in the others.
- **Taking back a put-back file asks instead of blocking** (F534; 23 Nov). The kit left the night copy dirty and
  blocked the one checkout that cleared it. That checkout now opens a box.
- **A copy at the uploaded commit keeps its files** (F535; 23 Nov). A hand move of the night copy onto the uploaded
  commit was put back, as no step moved its HEAD. Files exactly as an uploaded HEAD has them are kept.
- **gate_records takes patterns** (F536; 23 Nov). `"Saved/FullTier/**"` covers every file the nightly writes there.
  The kit's own files never count, whatever the pattern.
- **A copy a run owns is left out** (F537; 23 Nov). `"run_copies": ["../MyGameNight2"]` keeps other copies' steps from
  judging the nightly's folder, so helpers can keep working while it runs.
- **A recorded function keeps its entry when it moves file** (F518; 20 Nov). The structure check knows a long or
  tangled function by its file and name, so moving one to another file made it "new code over the limit". Its
  recorded size now follows it, and it still may only shrink.
- **The yes is taken before a long gate** (F517; 20 Nov). On the game's PC the upload script runs a ten-minute
  gate before `fg/push.py`. The owner pressed Allow on the upload, the helper's other steps during the gate ended
  the one-time note, and the upload stopped with "the owner has not said yes". A project's own upload script now
  calls `python fg/ownerok.py --at-upload` as its first line, and the yes is recorded at once.
- **The owner's kit update reaches the other copies** (F514; 20 Nov). On the game's PC the owner updated the kit
  in the working copy and committed it. Before it was uploaded, the nightly's checkout moved its run folder (a
  worktree) to that commit, and the kit put the six old kit files back there, so the night refused its folder. A
  kit file that is exactly as another copy holds it, written there by the owner's own kit command, now stays.
- **An update keeps the project's line endings** (F515; 20 Nov). Where git had checked the kit out with Windows
  line endings, the update wrote plain ones over all 77 files and git listed each as changed. A file that differs
  only in line endings is now left alone, and a changed file keeps the endings the old one had.
  The other-copy rule above (F514) also holds when the two copies differ only in line endings (F516).
- **Notes that name the upload or the kit's files ask nothing** (F511, F512; 20 Nov). The first two boxes on the
  game's PC after the update were both false: notes appended with `cat >> file <<'EOF'` that named the upload
  script were asked the owner's yes, and a Python here-document run as `"$PY" - <<'EOF'` that edited the handoff
  notes was read as changing the kit's files it only named. The first is fixed outright. For the second, list the
  variable in `"python_variables": ["PY"]` in `foundationguard.json` (the owner's file), and such a program is read
  exactly like one run with the word `python`. On the PC itself the cause was `io.open`, which the kit did not
  follow; it is now read as the built-in `open` (F513).
- **The upload itself asks for the owner's yes** (F506; 19 Nov). On the game's PC the AI tool's own safety check
  would not let the helper run `fg/ownerok.py`, so the owner said yes in a box, the upload still stopped, and he had
  to give the same yes again in a terminal. When an upload a helper runs (`fg/push.py` or the project's
  `push_command`) is missing a yes, the kit's box now opens on the upload, and the yes there is the yes.
  And a step that only says the yes command in a message (F507: a waiter labelled "... fg/ownerok.py --give in his
  window") no longer opens the yes box: the owner allowed that box, and it recorded nothing.
- **A slow copy cannot stop every step** (F505; 19 Nov). The check at the start of a step also looks at the
  project's other copies (worktrees, checkouts beside it). On the game's PC, twelve of them and a fresh scratch
  worktree took it past the guard's time limit; it was stopped before it saved anything, so every step after was
  refused the same way. Now a copy there is no time for waits for the next step, which starts with it, and a copy
  the check never came back from is left out for an hour and written to the catch log.
- **A guard that runs out of time says where** (F504; 19 Nov). On the game's PC every step was refused with "the
  check ran past its time limit" and nobody could tell what was slow. The message now names the kit file, line and
  function it was in, and the whole stack is kept in `~/.foundationguard/guard_crash.log`.
- **A file a command only names is not a write** (F500-F503; 19 Nov). On the game's PC, 79 of one week's asks were
  lines where a write went through a shell variable and a guard file was only named: the project file handed to the
  build, a check script run afterwards. A variable the line itself sets to plain words now holds those words, and a
  guard file named only after the write no longer counts (a line runs from left to right); loops, functions, eval,
  source, trap, here-documents and background jobs keep the whole line. Found on the way and closed: a guard file's
  name after a variable in the middle of a path, and a copy into a folder that lands on a guard file by its own name.
- **Never the long box after the chat** (F499; 19 Nov). When the kit could not see the question in the chat, the
  box at the third try was the long scrolling one again; the owner: "this does not at all fix the issue". That box
  is now as short as the other (what changes, the recommendation, and what to do if the question is not in the
  chat: press Deny and ask the helper). Only a tool with no chat record at all still gets the long box.
- **The question sent with a message tool counts** (F498; 19 Nov). The first real question-in-chat box on the game's
  PC took three tries and opened "unseen": its helper works from a project thread, where the owner reads only what a
  message tool sends, and the kit looked only at the helper's plain text. Lines sent with a tool whose job is to
  message the owner (`send_message`, `post_message`; more through `chat_tools`) now count; the same words in a
  command or a file being written still do not.
- **Two findings from the game's PC** (F496, F497; 19 Nov). With the editor open, appending plain notes to a doc from
  a here-document was blocked as a "heavy job" because the notes named a check script inside code marks: the words
  of a document being written are no longer read as a command (what the shell would run in them still is). And the
  box for switching `chat_first` on opened with "the kit thinks this makes a check weaker" and recommended No: a
  box now says that only when the kit found something weaker, not when it only describes the change.
- **The watched-hour pack** (19 Nov; beta gate line 5; Plan 2 part 6). `watched-hour/` holds what a watcher needs:
  Gold Mine (a tiny game with 12 tests that needs nothing but Python), the four cards, the watcher's sheet with the
  hour minute by minute, the pass lines and a score sheet, and `watcher/plant.py`, which opens the planted pull
  request of card 3. No person has run the hour yet; the planted change has been tried on a local copy only.
- **The question is in the chat before the box opens** (F492-F495; 19 Nov; beta gate line 1). The AI tool's own
  yes/no box is a small scrolling field, hard to read on a phone or a computer. With `"chat_first": true` (setup
  writes it for every new project; an existing project switches it on in foundationguard.json, which asks the owner
  once), the first try at a step that needs a box is stopped once: the helper must post the kit's three sentences
  in the chat as an ordinary message, each on its own line, with the kit's details under them. The kit then reads
  the session's own record and opens the box only when the helper's messages hold all three sentences; that box is
  two short sentences and points up at the chat. A helper that doesn't post them is stopped once more, and at the
  third try the box opens anyway with the whole question and says the chat copy could not be seen. Where the AI
  tool hands the hook no record, the box keeps the whole question and says the helper was told to post it. One extra pause a question.
- **The Windows download: no Python install** (F490, F491; 19 Nov; beta gate line 4). One normal download
  (`FoundationGuard-Setup.exe`, built by the "windows-download" job from `packaging/windows/`) installs for one user,
  with no administrator question, into `%LOCALAPPDATA%\FoundationGuard`: python.org's small Python 3.12 (unchanged,
  checked against a pinned sum at build time), the kit and the guides. Its last page shows one sentence to paste to
  the helper, with a copy button; the sentence is also kept in the Start menu. Running on that Python, the kit writes
  its full path into every hook and the gate. The check-up has a new line, "Kit's Python": LOOK when a Python the
  hooks call is gone (removing the download stops every hook without a word; the uninstaller warns first). The job
  installs the download with every other Python off the PATH, into a folder with a space in its name, and checks
  setup, every hook's path, BLOCK for a piped force push, the gate and an upload. Not signed in the beta: Windows
  shows "Windows protected your PC" first ("More info", then "Run anyway"). The download has no pytest, so a Python
  project's tests run through the kit's own runner (unittest).
- **Ready for strangers: names out, and a way out** (18 Nov; wording only: docs, comments and the text of one message). The owner's
  name and the two games' names are gone from every file ("the owner", "MyGame", "the Godot game test"; the test
  logins are now "kim" and "alex"; the game's class and switch names in the tests are "My..." and "my.*"). docs/GUIDE.md
  has a new section, "Removing the kit", tried by hand on a small project. Five proofs that had gone stale since 16
  Nov prove again (F081, F366, F368 to F370): the tests now really exercise what they guard.
- **Merge D2: when GitHub's lock holds, the PC stops asking about tests** (F484-F489; 17 Nov). Only with the owner's
  "remote_lock": true, a fresh ON from GitHub (fg/lock.py, asked again at every upload) and a drill passed within 30
  days (fg/lockmode.py). Then a change to a test or check script opens no box and is never put back; a weakening is
  said in chat at once, and the upload goes up to wait for the owner's Approve on GitHub. The kit's switches still
  ask; workflows and CODEOWNERS are switches now. A pass on unapproved changes reads PASSED, NOT APPROVED.
- **Merge D1: the second opinion** (F474-F483; 17 Nov). When the kit's GitHub note holds a change, another
  company's AI (key, address and model set on GitHub only; off without them) reads the flagged test lines and the
  helper's description and says whether they fit. Its words show only when they add doubt; it never changes the
  check. The note now shows the helper's own description exactly, boxed, with the safe choice.
- **A copy from a variable no longer names the whole command** (F473; 17 Nov). cp "$f" Saved/x.png asked the owner
  about every guard file named anywhere in the command (a capture run's MyGame.uproject). It now counts only where
  the copy lands; a write whose place is a variable still asks, and says plainly the kit can't tell where it lands.
- **Merge C: team copies and the lock's own checks** (F460-F472; 17 Nov). setup.py --join sets up a teammate's
  fresh clone with nothing to commit; each copy's own settings hold machine things only. In a team, what is exactly
  as GitHub has it is never put back (a switch only as main has it). Helpers can't read or change GitHub logins.
  fg/lock.py names roles, the plan (CAN'T BE ON), the logins on the computer and what they can do, and --drill
  proves the lock by trying to break it; setup.py --lock walks the owner through the lock one checked step at a time.
- **Merge B: the team lock, a one-step update and the kit's own GitHub App** (F454-F459; 17 Nov). With a team,
  fg/lock.py says ON only when main requires the "FoundationGuard note" check from the kit's own app and its key's
  environment lets only main use it. python <new kit>/fg/update.py checks the transfer's sums and updates fg/ in one
  step (no --accept after). python fg/app.py makes the app in one click. "remote_report_only" runs the GitHub check
  as a neutral report for a first live run. A patch written in the same command is read from its heredoc.
- **A reviewer instead of a box for technical changes** (F452, F453; the owner, 16 Nov). With "review_lane": true, a
  helper's change to the project's own tests and check scripts opens no box; at the upload, python fg/review.py runs
  the owner's reviewer ("review_command"), and its PASS stands in for the owner's yes. The kit's own files,
  "owner_only" files, changes the kit judges weaker and tests that stopped running still ask the owner. A WEAKER or
  WRONG verdict sticks, and the owner sees the reviewer's sentence.
- **Boxes in three plain sentences** (F451; the owner, 16 Nov). Every box now opens with WHAT CHANGES, WHAT COULD GO
  WRONG and MY RECOMMENDATION; the kit's longer reasons follow as details.
- **A daily budget for the owner's OK boxes** (F450; the owner, 16 Nov: 82 boxes in a day, most he couldn't judge). The
  kit counts its asks each day against "ask_budget" (default 5), shows the count in every session's first line and in
  catches.py --today, and over the budget names the rules that asked most so they become fixes.
- **Reading the kit's own checks from Python doesn't ask** (F449; the game's PC, 16 Nov 19:54 UTC). A one-line
  python -c that put the kit's fg folder on the search path and called its read-only checks asked whether the helper
  may change 'fg'. Calls that only read (config.load, structure.check and a few more) now pass; any other use still asks.
- **Away mode leaves the project clean** (F447, F448; the game's PC). Switching away mode wrote foundationguard.json,
  so the tree was dirty and the push script refused. It is now the owner's stamped line in the git folder; only the
  owner switches it (their terminal, or their yes in the kit's box).
- **A slow yes in the box still counts** (F445, F446; the game's PC, 16 Nov). The owner's yes for --give was lost when
  it came more than two minutes after the box opened, and --give fell to a typed code (which froze Windows Terminal on
  15 Nov) or crashed with EOFError. The box's note now lasts until the next helper step (at most 30 minutes); --give uses
  the Windows-aware terminal test, and with no keyboard says so plainly.
- **Boundary rules can leave files out** (F444; the game's N23, 16 Nov). A rule's "files" may be a list, and
  "exclude" leaves a hub file out, so one rule does what took eleven.
- **Newly protected files are never deleted** (F442, F443; the game's PC, 16 Nov 15:16 UTC). Adding paths to the guard
  list made the check after the step "put back" the newly covered files to not being there, deleting four project files
  in ten copies of the project. Newly covered files are now taken as they are, and a put-back never deletes a committed file.
- **Python nesting from the code, not the lines** (F440; the game's PC, 16 Nov). The design check counted a long call
  wrapped over several lines as 11 and 21 deep; it now reads nesting from the syntax tree, with elif at its if's level.
  A baseline recorded under the old count is held to the old count until the next ratchet records the new one (F441).
- **The OK list names the right approved row, and Windows reads program output as UTF-8** (F439; the game's PC, 16 Nov).
  One changed row of the approved list was shown in the OK box as four other rows; now the changed rows are named by id.
  Every program output the kit reads as text is now decoded as UTF-8 (the ready listing crashed with the Windows code page).
- **The owner's switch survives a step ending mid-write** (F438; the game's PC, 16 Nov 12:45 UTC). `away.py off` wrote
  the settings and only then its door line; a helper step ending in between put the owner's switch back. The door line
  now comes first, and the file is written in one step.
- **A crash says where, and written-down kit commands don't ask** (F435, F436; the game's PC, 16 Nov). A guard that
  crashes now names the file, the line and the copy of the kit in its block, and keeps the whole trace in
  ~/.foundationguard/guard_crash.log. "steps.py --accept" or "away.py off" written in a commit message, a changelog line
  or a here-document no longer asks the owner as if the helper ran it. And the crash the PC hit is fixed (F437): a
  python here-document listing job scripts in a value (drop=['full_gate.sh']) crashed the guard with IndexError.
- **Two kits in one session are named** (F434; the game's PC, 16 Nov). A session started in the play copy ran that
  copy's own 13 Nov kit before every step and this kit after it. The older kit didn't know the owner's door, so the owner's
  own `away.py on` and the gate's pass file were put back. Now the session's first line and its first check after a step
  say TWO KITS RUN, name the other kit and what it lacks, and say to start sessions from the folder with the newest kit.
- **The count survives a second round** (F418 to F433; Grok, given the code, 16 Nov 04:37 UTC). Held now: more ways of
  writing code that never runs, more ways of stopping a test or a run (skipTest, importorskip, exit, .only, DISABLED_, a
  collection hook), a check wrapped so its failure is caught, a return anywhere before a check, a check moved into a
  function nobody calls, a second test with the same name, a skip word sneaked in through a rename, a limit held in a
  local name loosened, a test setting the very value it checks, fewer decimal places, and any change to how tests are found and run (conftest.py, pytest.ini, jest config) now counts as the kit's own lock. Quiet as before: a called helper,
  a helper's own return, try/except around setup, a real rename, a stricter limit. Behind the count, tests that passed
  before must still run and pass at the gate (fg/ranbefore.py, since 13 Nov), whatever words were used.
- **The count survives an outside attack** (F412 to F417; Grok, given the code, 16 Nov). Six ways to weaken a test
  without the note saying so now hold: a skip for the whole file outside any test, `True or` in front of a check, a
  one-sided limit moved the loose way (`>= 5` to `>= 0`), a check pasted under `if False:` in a new test, a return in the
  middle of a test, and a changed expected value on an approved promise's test. A stricter limit and an honest move into a
  new test stay quiet. Still out of reach, as before: changing the game code a test calls, leaving the test untouched.
- **Team mode on GitHub: the kit's note and check for every change** (F404 to F411; the owner and a teammate, 15 Nov; the
  owner's GitHub test, 16 Nov). `fg/remote.py`, run by the workflow in `docs/foundationguard-team.yml` from main's copy
  only, puts the kit's note at the top of every pull request's description (copies or forgeries of it lower down are taken
  out), asks the right person to review, and names who can approve and who can't (whoever opened it, whoever last uploaded
  to it, the helpers' accounts). It judges what main would be if the change merged now, so two changes that are each fine
  alone can't add up unseen, and after every push to main it counts each open change again: if the count changed, its
  check goes red until Update branch asks for a fresh Approve. The check is also red when the change doesn't merge cleanly,
  when main's CODEOWNERS differs from the team settings or GitHub reports errors in it (an invite not yet accepted), or
  when a file the kit watches has nobody to approve it. The check is posted by the kit's own GitHub app, whose key only
  main's workflow can reach; on the owner's test repo a workflow on a change's branch faking the check no longer got the
  change in (spike S10).
- **Team mode, first piece: GitHub decides who approves** (F398 to F400; the owner and a teammate, 15 Nov). A "team" block
  in foundationguard.json names owners, reviewers, check owners for test folders, and the helpers' accounts.
  `python fg/codeowners.py` writes GitHub's CODEOWNERS from it: ordinary code needs a reviewer or an owner, a check
  owner's test folder needs them or an owner, a test nobody is named for needs an owner, and the kit's own files always
  need an owner (they come last, and GitHub uses the last line that matches). A helper's account is never written in, so
  its Approve never counts. `--check` says whether the file matches the settings. One owner works as before.
- **The merge note says what a loosened check now accepts** (F403; the owner, 15 Nov, on the first note he saw). A check
  that wanted one exact value and now accepts a range (`gold == 250` to `gold >= 0`) said only "the kit can't tell"; it now
  says "a check loosened. It accepts results it used to reject", with the line as it was and as it is now.
- **A read-only command raises no box** (F401; the game's PC and the owner, 15 Nov). `sed -n 1,30p fg/install.py | grep
  ... | cut ...` raised a box: "install" in the file's name looked like a write, and sed wasn't known to only print. sed
  with no -i and no w, W or e command, cut, tr and nl now count as reading. Found on the way (F402): sed's own w command
  and a spelled-out --in-place wrote a guard file with no ask; both ask now.
- An owner's OK survives a reword of commit messages: it covers the file's content, not the commit (now tested).
- **Less friction from the kit itself** (F392 to F396; the game's PC and the owner, 15 Nov). The kit's look at the
  remote never asks for a git login and gives up after 8 seconds: the PC still held an old login, every step timed out
  and a play copy moved to the new main was put back. Programs the kit starts get no keyboard, so the type-the-code
  question can't freeze. A changed approved check can take the owner's OK, and a test's name in a text string is no
  longer read as the test. While git is partway through a rebase or merge, the kit waits and judges the files after.
  The kit's records survive Windows refusing a replace for a moment (F397).
- **Setup updates an older kit in place** (F374 to F376; Fable's beta plan, line 3 of the beta gate, 14 Nov). Setup
  refused a project that already had the kit, so an update was by hand only. Run from a newer kit, setup now replaces
  the files in `fg/` one whole file at a time and writes a door line for each, so the update stays whether the owner ran
  it in a terminal or said yes in the kit's box. A session that resumes or compacts after the kit's hooks changed is
  told to restart, because a session keeps the hooks it started with. The start-of-session hook reads the session's details for at
  most 2 seconds, so an input left open never stalls it (F391; #46's Linux tests ran 6 hours on GitHub).
- **The merge note's count** (F377 to F390; Plan 2, PR 3, 15 Nov). `fg/facts.py` compares each test with itself as
  main has it and counts, in fixed words, what a merge does to the checks: removed, turned off, can no longer fail,
  loosened, a change it can't judge, or the kit's own lock. A version bump or a check rewritten with the same limit is
  listed but doesn't hold; a test moved to another file with the same body raises nothing. Run on the game's last five
  merges: three safe, the kit's install and the 11 Nov merge held.
- **An install survives, in every copy** (F371 to F373; Fable's beta plan, line 3 of the beta gate, 14 Nov). An
  install the owner ran in a terminal was put back at the next helper step, and one a helper ran with the owner's yes
  was put back in ten copies whose check after that step never ran. The install now writes a door line for each file it
  changed, in each copy's own journal, and only when the owner's terminal or the owner's yes in the kit's box covers it.
- **The owner's own kit commands stay** (F366 to F370; Fable's beta plan, line 2 of the beta gate, 14 Nov). The owner
  typed `python fg/away.py off` in their own terminal and the next check put it back as "changed outside any helper
  step". A kit command run in a real terminal now writes one stamped line per file it changed to a journal in git's
  folder, and the checks keep a file whose content matches a fresh line that started from what the kit had accepted.
  A helper's run (no terminal) writes no line. A change that loosens a check asks for a typed code first. `away.py` is
  the first command through the door; the others follow.
- **The game's gate pass file stays when it changes during a step** (F365; the game's PC, 14 Nov). A running gate
  rewrote `Saved/PrePushPassed.txt` while a helper step watched it, and the check after the step put the old stamp
  back. Files in `"gate_records"` are now taken in a step as they already were between steps. `ready.py` and setup
  now ask for Python 3.10, the oldest version the kit's own tests run on.
- **The kit's test switch is no longer a helper's off switch** (F364; Fable's beta plan, 14 Nov). `FG_BREAK` turns
  one of the kit's checks off so `prove.py` can show the check catches its break. The guard now refuses a helper's
  command that sets or clears it. A script the kit never reads could still set it; the upload check on GitHub and the
  branch lock are the backstop.
- **The game's first install of the merged kit** (F348 to F358; 13 Nov). The hooks run Python isolated (`-I`), and
  installing again replaces the kit's older hook lines instead of doubling them. Install compiles the kit, so the first
  guarded step no longer runs past the guard's time limit. A helper running `install.py` or `setup.py` now gets the
  kit's box, and the owner's yes keeps what install writes, so the check after the step no longer puts the install's
  own hooks back. The lock reminder goes by GitHub's own answer (asked at most once a day). A change to the kit's own
  code is labelled "MAY now CATCH LESS", because its line rules can be wrong about code.
  A new setting, `"gate_records"`, lists the files the project's own gate writes on every run (a pass file). These are
  taken as the gate's record, not held for the owner's yes (F354).
  When the check after a step never runs (a session started with older hooks), a yes the owner gave in the kit's box
  still counts at the next step (F355). The box about taking the guard files as they are now quotes what the kit read,
  so a note that only mentions the command can be told apart (F356).
  The game's sessions start in its play copy, whose settings ran the guard but not the check after each step, so a
  yes'd change was put back at the next step. Install and `copies.py --cover` now add that missing hook (and only it),
  and a session that starts there is told at once (F357, F358).
- **A fresh helper's Windows check** (F359, F360; 13 Nov). Setup no longer writes hooks into an unrelated project
  beside it that happens to use the same local remote path: a copy must also share the project's first commit. The
  built-in test runner (used without pytest) now runs a plain `tests/` folder that has no `__init__.py`.
  `ready.py` says when the tests have never passed through the kit in this project (F361).
  When git has no name or email yet (common on a fresh PC), the kit says so in plain words with what to run,
  including on a break glass (F362, F363).
- **"This check now CATCHES LESS"** (F347; the owner, 13 Nov). On the owner's yes list, any item that makes a check
  weaker now starts "This check now CATCHES LESS", and a check line changed while asks were gathered that the kit
  can't judge (such as `==` turned into `>=`) starts "This check MAY now CATCH LESS". The away-mode walkthrough tells
  the helper to say each one plainly.
- **Away mode** (F345, F346; the owner, 13 Nov). `python fg/away.py on` (the kit's box asks the owner, before they
  leave) gathers the asks: changes to the owner's tests and lists go through without a box each, are written down,
  and the upload waits for one yes. When the owner is back, each session starts by saying how many changes wait, and
  tells the helper to explain every change on the kit's own list in plain words, before other work, and never to give
  the yes itself. `python fg/away.py off` when back for good. It is the `gather_asks` setting with a name and a switch.
- **Round 9 (ChatGPT): where a proof ran can't be faked from the command line** (F343, F344). `CI=1` in a cloud
  session made its receipts look like CI's. A cloud session is now never CI, and the guard refuses a line that runs
  the kit's own commands while setting or clearing CI, GITHUB_ACTIONS or CLAUDE_CODE_REMOTE. Two limits are now
  written down: the kit doesn't start night jobs itself (your scheduler does), and a program a job deliberately
  detaches from it can outlive the time limit.
- **Ready: missing programs, the GitHub lock, too many boxes** (F339 to F342; round 9's usability points, the owner's
  yes, 13 Nov). Setup checks Python and Git first and says in plain words what's missing and how to get it. Every
  session starts by saying, while it's so, "you are not fully protected yet" when the project's GitHub copy isn't
  locked, and when the owner was asked more than 5 times yesterday or today. `python fg/ready.py` shows all three
  and the boxes per day for a week; the check-up has two new lines. Part `reminders` (on, warn, off).
- **Round 9 (Grok): a change after the pass is not proven** (F336 to F338). Grok changed a source file without
  committing it, and `receipts.py` still said PROVEN and `bite.py` BITES (the upload itself refused). Receipts and
  bite records now also keep a fingerprint of the folder's uncommitted changes (tracked files changed, and new files
  git doesn't ignore); PROVEN and BITES hold only while the folder is the same, otherwise OUT OF DATE. The night watch
  says RAN ON A RETRY for a job that failed and then passed, and names it in the morning.
- **The night watch: did last night's work happen?** (F333 to F335; the owner, 13 Nov: "if they wake up and nothing
  got done for them"). The first two parts of the Night Foreman plan. A check run through the receipt runner now has
  a time limit (`limit_minutes`, else `check_timeout_s`): a stuck run is ended with every program it started, so one
  hung job can't hold the night. `python fg/night.py` says, per scheduled job (an expected check with `every_hours`),
  RAN, FAILED, DID NOT FINISH, DIDN'T RUN or CLAIMED ONLY, and writes `.foundationguard/night.json`. Setup adds a
  session-start hook: the first session after a bad night starts by saying which jobs didn't get done and tells the
  helper to tell the owner. Part `night` (on, warn, off). It only informs.
- **The handoff checker: is the note true?** (F330 to F332; the owner's tool ideas, 13 Nov). A handoff note carries a
  facts block (`<!-- facts -->` ... `<!-- /facts -->`), and `python fg/handoff.py NOTE.md` checks each fact against
  the project with plain rules: a commit, a branch at a commit, a pushed commit, a file there or not, a file's text,
  a check's receipt word, a guard's bite word. Each gets TRUE, OUT OF DATE (the branch moved on), WRONG or NOT
  CHECKED, and the count of lines it did not check is always shown. `--write` prints a facts block for the code as
  it is now. It only informs.
- **A parked test is renewed once at most** (F329; the owner's tool ideas, 13 Nov). The kit remembers each parking the
  gate used, in its proof store, so a test parked twice in the last 30 days can't be parked a third time; the gate's
  sorted failures say why a parking didn't hold.
- **The bite test: do my checks still bite?** (F327, F328; the owner's tool ideas, 13 Nov). Every `prove.py` run now
  leaves a stamped record of which guard, its verdict, the exact code and where it ran. `python fg/bite.py` gives
  each guard one word: BITES (the only proven one), HOLLOW, OUT OF DATE, ALREADY FAILING, BREAK DOESN'T FIT,
  NO BREAK, NEVER TRIED, CLAIMED ONLY, and writes `.foundationguard/bites.json`. `--pilot N` proves N guards and
  says how long a full run would take; `--refresh` proves again the ones that aren't BITES (for a nightly run). The
  breaks stay in the approved list's Break column. Automatic small changes remain `fg/logic.py`.
- **The alarm sorter: what kind of red is it?** (F321 to F326; the owner's tool ideas, 13 Nov). When the gate fails,
  the kit runs each failed test again three times and sorts it: REAL (failed every time), UNSTEADY (passed on some
  runs, on the same code), MACHINE (no report or no tests: nothing was tested). The upload stays stopped. A test
  that failed and then passes when the gate runs again on the same code is UNSTEADY, not a pass. Only the owner
  parks a test (`parked` in foundationguard.json: at most 3, at most 7 days); a parked test still runs and is shown.
  Tests the approved list names, and `never_park` ones, can't be parked. Part `alarms` (on, warn, off).
- **Each new feature has on, warn and off** (F320; owner, 13 Nov). tests_gone, pystartup, receipts and ledger are parts
  in `python fg/parts.py`, so an experienced developer sets them in one line; the presets core and watch keep the
  ledger on.
- **Receipts: no receipt, no green** (F308 to F315; the owner's tool ideas, 13 Nov). Every run of the gate, and of the
  checks listed in `expected_checks`, leaves a receipt in the kit's proof store (`.git/foundationguard/proof/`,
  stamped and chained): started, finished, the exact code, where it ran. `python fg/receipts.py` gives each check one
  word from one list: PROVEN (the only green: passed on exactly this code), PASSED ON A RETRY, OUT OF DATE, FAILED,
  DID NOT FINISH, RUNNING, NEVER RAN, OVERDUE, CLAIMED ONLY (a cloud session's pass, or a receipt written by hand). It
  writes `.foundationguard/status.json` for a status board. It only informs.
- **The owner OK ledger: your yes can't be reused** (F316 to F319). Every OK is now a stamped line in the proof store,
  with what you were shown. An OK covers one exact version, once (the upload that carries it uses it up), for 24 hours
  (`ok_hours`), until a newer OK for the same item replaces it. `python fg/ledger.py` lists them. This replaces
  `owner_ok.json`.
- **You see what your yes covers** (F307; owner's ask, 13 Nov). When you give your OK (`python fg/ownerok.py --give`),
  the window first lists each item in plain words: what kind of thing it is (a test, the kit's own code or settings, a
  guard file, tests that stopped running), what changed and how many lines, and the helper's reason from its commit,
  marked as its own unchecked words (or that it gave none). Only then does it show the code. The permission box says
  the same in one line per item. The code still appears only in a real terminal, where a helper can't type it.
- **Two false alarms from the game's install** (F305, F306; game build, 13 Nov). The approved list's columns are now
  read from its header by name, so a list laid out as ID | Date | Behaviour | Words | Checks | Proven | Break works
  (F305). A switch pattern without a group now counts a name only where it starts in quotes, as a switch's definition
  does, so ordinary code such as `my.kind` is no longer taken for an undocumented switch (F306).
- **Tests that passed before must run again** (F302 to F304; outside review round 8, Grok's next steps, 13 Nov). The
  kit now records which tests passed at every pass. A test that passed last time on the same line of work and doesn't
  pass now (gone, skipped or no longer collected) stops the upload until the owner says yes, with the same yes as a
  changed guard (`python fg/ownerok.py --give`); `python fg/ranbefore.py` lists them (F302). Python's start-up files
  outside the project (`sitecustomize.py`, `usercustomize.py`, `.pth` files) that are new or changed since the last
  pass are named in the upload's summary (F303) and by the check-up (F304). That one warns and doesn't stop, since
  installing a package changes them too. `sitecustomize.py` and `usercustomize.py` inside the project are guard files.
- **What the gate runs can't be changed quietly** (F299 to F301; outside review round 8, Grok, 13 Nov). A new
  pytest.ini with `addopts = --ignore=tests` went through with no box, and the gate then ran no tests. The test
  runners' own settings files are now guard files always, there yet or not, and pyproject.toml and setup.cfg are when
  the gate uses pytest, package.json when it uses npm (F299). `PYTEST_ADDOPTS="--deselect ..." python fg/push.py`
  passed with a test never run: the upload now drops the runners' environment settings (F300), and a command that sets
  them for the upload or gate is refused (F301).
- **A check-up in plain words** (F296 to F298; outside review 7). New `python fg/doctor.py` says, one line each and
  changing nothing, whether the guard is live, whether git's push check runs, how uploads go, which tests are not
  guarded (F296), which features are not fully on, whether GitHub is locked, whether other copies are guarded, and
  whether git is told through the environment to use other hooks (F297, F298).
- **Git settings in the environment** (F294, F295; outside review 8, ChatGPT, 13 Nov). Git also takes settings from
  environment variables (`GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_0=core.hooksPath`, `GIT_CONFIG_PARAMETERS`), so where
  direct pushes were allowed a push could skip the push check with no settings file changed. A command that sets them
  is now refused (F294), and `fg/push.py` drops the ones that switch its hooks off before it runs anything (F295);
  the AI tool's own (Claude Code on the web hands in url rewrites that way) stay.
- **Setup guards the project's own tests, and kinder words** (F290 to F293; outside review 7, Claude, 13 Nov). Setup
  wrote no `guard_paths`, so a project's own tests were not guard files. New `fg/testguard.py`: setup now guards each
  test folder whole, a test beside ordinary code by its name's pattern (`src/*_test.go`), and the test runner's
  settings, and prints the list in plain words (F290). With `--solo` setup and the README say plainly that uploads
  straight to main are allowed. The owner keeps a change of their own that the kit put back with
  `python fg/steps.py --keep <file>`, behind the kit's box (F291). The box that finds no weakening names the change
  (F292). Put-back messages tell the helper to leave a note and carry on instead of "don't try another way round", and
  the catch log says the kit assumed a change between steps was the owner's (F293). The guide no longer says every git
  setting changed between steps is the owner's.
- **A checkout keeps only what the kit trusts** (F269, F270, F282 to F284; outside review 6, Grok, 13 Nov, finding 3,
  and Claude Fable's review of the fix). A branch built with git's plumbing in one step and checked out in the next
  no longer counts as old history because it existed when the step began. New `fg/known.py` keeps, in git's shared
  folder, the branch tips there were at the kit's first install (only then, F282), every commit that was HEAD while
  every guard file was exactly as it has it, and remote tips git ls-remote confirmed (noted for good after a fetch,
  F284). A file a checkout or pull brings stays when the new HEAD is inside one of those, or the file is as a remote
  branch has it (F269); a removal too (F270). No single old version is trusted on its own (F283). The kit's settings
  file brought by a pull is now kept too (with F262 it was put back before the checkout rule was asked).
  A commit is noted only when the files on disk match its own tree, never through git's index (F285), a new worktree
  never notes every branch again (F286), and a held change is never trusted history (F287). A HEAD already trusted
  costs one look, and the remote is asked only after a step. A kit updated with several worktrees notes its
  branches once (F288), and a guard file over 5 MB no longer stops HEAD being noted (F289).
- **Changes between steps are judged by their kind** (F245 narrowed, F246 changed, F263, F265 to F268, F281;
  outside review 6, Grok, 13 Nov, findings 2 and 6; the owner's yes, 13 Nov). New `fg/tiers.py` and `fg/between.py`.
  The kit's records (what passed, the owner's yes) changed between steps are put back (F265), and the pre-push hook
  and the other readers count the record of what passed only as the kit wrote it (F281). The kit's switches (its
  settings, code, hooks, `core.hooksPath`) are put back unless exactly as the remote branch has them (F266). The
  owner's own files stay; more than new tests waits for the owner's yes at the upload (F267). The background-job
  timer is gone, so the owner's save while a job runs is never put back (F268, F246). The guard judges between-steps
  changes before it reads its own switch (F263). Every kit script that writes a record (the owner's yes, break glass,
  `--baseline` runs) goes through the record door. An older kit copy writing records would be put back.
- **A step can't switch the guard off or give itself a yes** (F262, F264, F271 to F273, F278, F279; outside review 6,
  Grok, 13 Nov, findings 1 and 4). The check after every step reads the kit's settings as last accepted, so a script
  that switched the guard or the push check off (or set `gather_asks`) has that put back before the rest of the step
  is judged (F262). The pre-push hook takes the push switch and the protected branches as the strictest of the
  working file, the accepted copy and the remote branch's copy, so switching the push check off takes one more
  checked upload (F264; the owner's yes, 13 Nov). "The box asked" is no longer read from the step's own note: the
  guard's reading runs again, read-only, on the step's own input (`guard.py --about`, new `fg/about.py`), and a yes
  keeps only the files its box named (F271, F278, F279) and never a git setting (F273). New tests are free by what
  changed, however they were written (F272; the owner's yes, 13 Nov). New `fg/switches.py`. The plan's F263 (the
  guard reads its switch after the between-steps check) moves to the next PR with the between-steps rules it needs.
  The AI tool's own "don't ask again" (an allow rule written into `.claude/settings.local.json` during a step) is
  kept; its hooks, environment and permission mode are still judged (F280).
- **More of git's risky settings, the yes box for any Python, and an honest README** (F274 to F277; outside review 6,
  Grok, 13 Nov). Fourteen more git settings that run a program or move a push (diff and merge tools, a branch's push
  remote, a submodule's url, extra HTTP headers, switching off HTTPS checks and the like) and their families are put
  back when a step changes them without the owner's yes, and so is any key whose last word names a program (F274). A
  setting the kit doesn't know is reported, not put back (F275). The owner's yes box opens whatever word starts the
  line, such as a full path to Python (F276). The README's first screen says GitHub branch protection is required,
  and three promises it couldn't keep are gone (F277). The yes-box reading moved from `fg/guard.py` to
  `fg/ownerwords.py`.
- **A removed record no longer switches the check after every step off** (F258; outside review 5, Claude Fable,
  13 Nov). With the kit's record of the accepted guard files deleted in a step, the check crashed, and the next step
  took the changed files as accepted. Now each step's note keeps a copy of the record, the step is judged against it,
  and the catch log says the record was removed.
- **Four more from outside review 5** (F259 to F261, Claude Fable, 13 Nov). A changed check line (`== 5` to `>= 5`)
  no longer gets "doesn't look weaker" in the owner's box: it says THIS MAY BE WEAKER (F259). A formatter's change of
  spaces and line breaks in the tests stays (F260; moving a check into a block is still put back). The kit no longer
  tells a helper to use `git stash`, which the check after every step undoes (F261). Docs: the rule count, the real
  projects, and the "you never type a command" and "60 seconds" promises are corrected.
- **Git's own settings in the check after every step** (F254 to F257; outside review 4, finding 13). A line in git's
  settings file (`[core] hooksPath = /tmp/h`, an alias, a filter) switched the push check off or made git run a
  program, and nothing compared it. Now the check after every step also compares the risky settings in
  `.git/config`, a worktree's `config.worktree` (F254) and the user's own git settings (F255), and puts back one a
  helper changed without the owner's yes; the rest of the file stays. Git LFS's own filter lines (F256) and a new
  remote (F257) are ordinary and stay.
- **A check after every step: what changed, not what was typed** (F241 to F253; the owner, 12 Nov, after outside
  review 4). Three rounds of outside review kept finding spellings the command guard misses. Now, in Claude Code,
  after every step the guard files are compared with how they were before it, and one changed without the owner's yes
  is put back at once, however it was written; the helper is told, the catch log and the next upload's report have it,
  and what was there is kept (F241). What stays: a change the kit's box asked about or a free rule let through
  (F242), the gate's own records (F243; the record door takes only those, F244), a change made between steps by the
  owner (F245; not while a background job a helper started may still run, F246), what a git checkout, pull or merge
  brought from history that already existed (F247; a commit dated in the past doesn't count as old), and with the asks
  gathered, the owner's own guard files, which wait for the owner's yes anyway (F252). A guard file changed and
  committed in the same step is put back and held for the owner's yes (F248). Install wires it in (F249), and it and
  the guard also watch Claude Code's Monitor tool, which runs commands and wasn't watched (F250). Found on the way:
  `fg/copies.py --cover` and `fg/lock.py --confirm` wrote guard files with no box; they ask now (F251).
  Found by CI on Windows: git there writes a checked-out text file with CRLF and stores it with LF, so the check now
  compares a file with a commit's copy as git would store it; before, a checkout's test was put back and a change
  committed in the same step wasn't held (F253).
- **What the third round of outside reviews found** (F229 to F240; 12 Nov). Grok and a fresh Claude Opus 5.5, given the
  round 3 critique prompt and main 912575a, tried to break the kit again; both reviews are kept word for word in
  `evidence/outside_reviews/`, with how each finding was sorted. Every finding was run again first. From Grok: a
  command inside a function, braces or after `if`/`while` (F229), the words handed to a function or `set --` (F230),
  more ways to set a value on the line (`$'...'`, `read <<<`, `printf -v`, `declare -n`, `source <(...)`, F231),
  PowerShell's `Invoke-Expression`, script blocks and `Start-Process`, and cmd's `set`/`%x%` (F232), and Azure DevOps's
  three ways of writing one remote (F233). From Claude, the ones that went round a central promise in one line: a
  guard file written through a folder variable (`"$PWD/foundationguard.json"` switched the guard off, F234), a patch
  that changes a guard file (`git apply`, `patch`, F235), the owner's yes given with `--give` spelled another way
  (F236), a gathered change uploaded after `git fetch . HEAD:refs/remotes/origin/BR` moved this copy's record of the
  remote (F237), a hidden force push that threw away a colleague's commit (the pre-push hook now refuses any push that
  doesn't hold the remote's commit, F238), and a crafted command that kept the guard busy past the AI tool's own time
  limit (a long input is now checked in a child process stopped at the limit, F239). Three checks Claude showed
  didn't bite (F224, F226, F227) now test every case they name. The owner's direction (12 Nov): stop chasing more
  spellings; the next steps are a check after every step that finds a changed guard file however it was written, and
  the owner's yes and the lock moved to GitHub. README now says plainly that on its own machine the kit is a safety net,
  not a lock. Found on the way: a `cd` to a full path after a `cd` into a variable crashed the guard, which
  blocked an ordinary command (F240).
- **Reading a job's script while the game runs** (F228; the game's PC, 12 Nov). With `block_while_running` set, a grep or sed that only mentioned a check script (`grep -n step Tools/Scripts/full_gate.sh`) was blocked as a heavy job while Unreal ran, so the helper fell back to plain file readers. Now only a part of the command that runs something counts: reading, listing and printing text go through, and running the job (directly, through `bash -c`, piped into a shell, or from `find -exec`) is still blocked.
- **What two outside reviews found** (F222 to F227; 12 Nov). Two AI models from outside, given the critique prompt and main 18e151b, tried to break the kit's ten claims. Every finding was run again first. Real faults, all fixed: a command built on the same line went through (`x="git push --force"; eval $x`, `bash -c "$(echo git push --force)"`), and so did a guard file written that way; values set earlier on the line and the words of a `$(echo ...)` are now read in (F222). A git command inside a string a short program hands to `exec` is seen (F223). A new test that changes a shared value in place (`shared.config["value"] = 1`, `GlobalState.items.clear()`, C++ `Shared = 0;`) now asks; on the game's 94 test files, written new, the asks stay at 4 (F224). A checkout beside the project is found whichever way its remote is written (F225). The licence ledger knows many more formats (`.ktx2`, `.wem`, `.vrm` and more) and a project's own (F226). Checking a claim about crashes, which already block, found a real neighbour: a check that never ends ran past the AI tool's own time limit, which lets the call go ahead; the guard now has its own shorter limit and blocks (F227). Every merge into main now runs the whole proof in CI and keeps its output. The README and the guide say plainly what the command guard reads and what it can't. Both reviews and how each finding was sorted: `evidence/outside_reviews/`.
- **Getting a file back whole when Git LFS keeps it** (F220, F221; the build thread, 12 Nov). AGENT_SETUP.md section 15 said to restore a file with `git show HEAD:path > path`. For a file kept in Git LFS (every `.uasset` and `.umap` in the game) that writes LFS's small pointer file, not the file. The advice is now `git cat-file --filters HEAD:path > path`, which runs LFS's filter; `git restore` and `git checkout`, which run it too, stay blocked because they throw away changes. The kit now blocks `git show` or `git cat-file` written over a file LFS keeps, and names the safe command (F220). Into a test's place, the safe command is judged by its text, as `git show` is (F221).
- **The owner's yes box only for a real yes** (F219; the build thread, 12 Nov). On the game's PC a doc appended with `cat <<'EOF'` that said "never run fg/ownerok.py --give" opened the owner's box, asking about "nothing at the moment". The box now opens only when the command itself runs `--give` and something waits for the yes.
- **Planning a run while the owner is away** (F218; the owner, 12 Nov). AGENT_SETUP.md section 15 lists what goes through, what still asks at once and what is blocked, so a helper plans an unattended run around it. With the asks gathered, every session's first line says so too.
- **Unattended nights** (F215 to F217; the owner, 12 Nov, after the overnight-stopper audit). A test not yet committed is judged as a new file whenever it is edited, so a night's own new test can be changed freely until its first commit (F215). That holds only for the file itself: a hard link, a linked folder, another case of a committed name or a project with no commit asks as before (F216). With `gather_asks` on, a night's change to an existing check or pin goes through without a box, and a test now proves that nothing of it reaches the remote before the owner's yes, by the kit's push, a plain `git push` to any branch, main, a merge, or the ways round the hook (F217).
- **Fewer false boxes on new tests, and every box written down** (F207 to F214; the build thread, 12 Nov, and the owner's
  decision card). On the game's PC a helper met seven boxes in 27 minutes and couldn't see their text. Written new, 54
  of the game's 94 test files would have asked; now 4 do (two harness headers, a `#define`, a variable named
  `Allowed`). A C++ test may set the members of values it made itself (`Params.Seed = 5;`, F207). The project's own test
  macros count as tests and checks (`MYHYDRO_TEST`, `MYHYDRO_EXPECT`, F209); before, removing a core check was called
  "doesn't look weaker". Words in a test's quoted message are no longer read as code (F210). Every ask is now written
  whole in the catch log, with the rule, the tool and its file or command (`python fg/catches.py --asks`), and the box
  says why a test change isn't only new tests and how a shell command was read (F211). A short Python program in a
  command is judged by the files it really writes, read with Python's parser, so a doc it writes that names a guard
  script no longer asks (F212). The owner's choice: a test not yet committed moves or is deleted freely, and a file copied
  into a test's place is judged by its text, as Write is (F214). Found on the way and fixed: a new test changing
  Unreal's class defaults (`GetMutableDefault`) went through (F208), and `os.remove`, `shutil` and `Path.unlink` in an
  inline Python program weren't seen as writes (F213).
- **Another copy's files are judged by its own settings** (F205, F206; the build thread, 12 Nov). On the game's PC
  the AI sessions open in the play copy (`C:\MyGame`) and work in the project (`C:\MyGameWT`). The hook judged every
  path by the play copy's own, older settings, so edits to the project's check scripts went through with no box. A
  path inside another copy of a project is now judged by that copy's own `foundationguard.json`, both ways, and the
  box names the file by its full path. `fg/copies.py --cover` also adds this kit's hook to a copy that was guarded
  only by another, older copy of the kit, so these checks run there too.
- **The project's own check scripts can count as tests** (F204; the build thread, 12 Nov). On the game's PC a new
  `Tools/Scripts/x_check.sh` asked the owner, because its name doesn't say "test". The new setting `test_files`
  names such scripts (`["Tools/Scripts/*_check.sh", "Tools/Scripts/check_*.py"]`). A new one then adds freely, as a
  new test file does; changing, removing or renaming one still asks. Empty unless the owner sets it.
- **Running a guard script never asks** (F201 to F203; the build thread, 12 Nov). The game's PC runs its own check
  line, which runs `Tools/Scripts/height_check.sh` and copies pictures named with `${A}` and `$1` from the line's
  own loops. The kit asked the owner to change the script on every run: a variable in a write made the whole line count,
  and the script's name was in it. A variable that the line's own loop (`for A in 10000 4000 1200`) or `set --` gives
  plain words is now read with each of those words put in. Any other variable still makes the whole line count. Found
  on the way and fixed: a write to `$1` or `"$@"` didn't count as a write through a variable (F202), and on Windows a
  Git Bash path such as `/c/MyGameWT` was read as `C:\c\MyGameWT` (F203), so the box named the wrong file and a
  write by short name after `cd /c/<project>/fg` was missed.
- **The kit's own checks from a Python path with a space** (F200; the build thread, 11 Nov). On the game's PC the only
  Python is the engine's, under `C:\Program Files\...`, and 140 of the 189 checks failed there, because their command
  lines split the path at the space. The path is now quoted in a command line. Tried here with a Python in a folder
  named `Program Files`: 190 of 190 pass.
- **The recommended list on a real PC** (F194 to F197; the build thread, 11 Nov, from the game's first PC run). The
  list now goes where the AI sessions open: on that PC they open in the play copy and work in the project, so the
  list in the project's own settings changed little. `--apply --for FOLDER` writes that folder's
  `.claude/settings.local.json` (kept out of git), naming the project by its full path and adding it as a folder those
  sessions may work in. `--settings FILE` writes exactly that file. Every run says which folder's sessions its list
  is for, and names other copies where sessions have opened. The Python rules also name the Python the kit runs with,
  by its full path (that PC has only the engine's own Python). `push_command` names the project's own push script
  (`bash Tools/Scripts/safe_push.sh` there), which is then allowed exactly, while every other push still asks. The
  kit's own checks run without pytest: `python tests/run_without_pytest.py`. A command that only reads or lists a
  guard file (`cat fg/install.py`, `git diff -- fg/install.py`, `grep -n "rm -rf" fg/guard.py`, the kit's own
  `guard.py --check "git reset --hard"`) no longer opens the kit's box: the owner sat at about 18 minutes of boxes on
  the PC's first sitting, some for these (F198). Found on the way and fixed: `rm -rf tests` deleted a guarded folder
  without the kit asking, because the folder was named without a slash, and `git diff --output=APPROVED.md` wrote a
  guard file unasked (F199).
- **Web games and apps** (F185 to F193; the owner, 11 Nov: "create a version for web apps", the same kit working with
  them). Setup now finds a browser game or web app by itself (a `package.json`, or an `index.html` with a script, also
  one folder down), names its framework, and fills in its settings: JavaScript and TypeScript (also `.mjs`, `.cjs`,
  `.mts`, `.cts`) and each page's own scripts are measured; packages, build output and minified files are skipped; a
  Sim folder goes under a browser maths rule (curves, powers, logs, `Math.random`, `**`, crypto random numbers, clock
  reads). A script loaded from the internet is new outside software, and the owner's card gives its address and
  version. Publishing or deploying is the owner's step. The project's own tests (Node's test runner, Vitest,
  Playwright, npm test) run through `fg/webtests.py`, which writes one report, so an approved check is seen by its own
  title and proven like any other. Found on the way: a regex such as `/"/g` hid every function after it from the size
  checks, and code inside a template's `${...}` was not read (F188). Tried end to end on two small sample games, one
  with a real browser test (`evidence/results/RESULTS_web_pack.md`).
- **A guard that crashes blocks** (F165, the owner's yes on 11 Nov). An AI tool reads a hook that dies with an error
  as "no answer" and runs the command anyway. So before this, a broken kit file, a broken `foundationguard.json` or
  input the guard could not read let every command through. Now each of these refuses the command in the AI tool's
  own terms: Claude Code, Copilot CLI, Codex CLI, Cursor and `guard.py --check`. The message says how the owner (not
  the helper) gets past it on purpose.
- **Windows** (F161 to F163): setup no longer stops after copying the kit; a kit on another drive than the project
  (D: and C:) no longer crashes the guard, rules or install; signs such as the forecast's arrow no longer crash output.
- **Comment prose is not a waiver** (F164): a comment that only says what is no longer allowed is not a waiver; real
  markers (noqa, nolint, fg-ok, pragma, lint:ignore and the like) still are.
- **Every copy of the project is guarded** (F166 to F170; the game's first real morning, 11 Nov: a helper session
  opened in a second copy of the project ran with no guard and changed a test file without asking, and nothing said
  so). Install now also guards each git worktree and each checkout of the same remote beside the project, using the
  project's settings where a copy has none. Each AI session starts with one line saying whether the guard is live in
  its folder. Every upload summary names an unguarded copy as a FOR YOU card. `python fg/copies.py` lists the copies.
- **A helper adds tests without asking** (F171 to F173; the game's first real morning, 11 Nov: every new test a
  helper wrote opened the owner's permission box). A new test file, or new tests between or after the ones in a test
  file, now goes through (`helpers_add_tests`, on unless the owner turns it off). Changing, removing, renaming or
  skipping a test, a line slipped into a test, a reused name, a patch every test shares and the test runner's settings
  still ask, with the weakening finder as strict as before.
- **The asks at one sitting** (F174, F175): with `"gather_asks": true`, changes to the owner's own guard files go
  through without a box each and the upload waits for one yes to all of them (`python fg/ownerok.py` lists them). The
  kit, its settings, its hooks and its frozen numbers still ask at once.
- **No false "not locked"** (F176, F177; the build thread, 11 Nov: gh was installed on the game's Windows computer but
  not on the PATH the kit saw, so every summary said the project wasn't locked). gh is now also looked for in its usual
  install folders and at `gh_path`. When GitHub can't be asked, the status is "could not check", with the reason and
  its own card. A helper's limited key that can't read the lock's details still sees whether main has one.
- **Which box is whose** (F178 to F180; the game's first real morning, 11 Nov: the owner couldn't tell the AI tool's own
  boxes from the kit's). The kit's blocks, boxes and upload report are all labelled "FoundationGuard:". A suggested
  allow-list of routine reading, building and testing commands (`fg/allowlist.py`; setup with `--allow-routine`) stops
  the AI tool asking about those, after the owner's one yes. The guide says which box is whose.
- **A helper keeps working while you're away** (F181 to F184; the owner, 11 Nov: "it cant be frustration for the user
  that stops the work from being done", after an unattended session stopped five times in ten minutes at the AI
  tool's own boxes for ordinary edits). The recommended list (`fg/allowlist.py`) now also lets ordinary edits and new
  files inside the project and the kit's push script go without the AI tool's box, and writes ask rules so the kit's
  guard files, settings, deletes, other pushes and installs still ask (anything outside the project asks because
  nothing allows it). Setup ends by offering the list and writes it only on the owner's yes (typed in a terminal, or
  given before with `--allow-routine`). Every question the kit asks is one line: what is asked, why, and what to click.
  The guide says where to find a waiting box and how a helper tells the owner it is waiting. The kit's own checks on
  edits are as strict as before.
- The kit's own CI uses about a ninth of the minutes (11 Nov: the org's 2,000 free monthly minutes ran out in one day). Each change to a pull request runs once, on Linux and Windows; all six jobs, macOS included, run on every merge into main.
- The kit's own tests run on Python 3.10 and 3.12 (3.9 is no longer offered on the newest Ubuntu runner).
- **A repo a stranger can read** (the owner, 11 Nov; now the rule for every tool added here, see `CONTRIBUTING.md`).
  The README is a short front page; every part and the full limits are in `docs/GUIDE.md`; all results moved to
  `evidence/` (`evidence/results/` for the 13 results files, `tests_evidence/` renamed), indexed by
  `evidence/EVIDENCE.md` (claim, measured result, file).

## v0.8.6 beta (11 Nov): fixes from the Godot game test, and the saved-state check
**The Godot game test (11 Nov).** A helper used v0.8.5 on a copy of a real Godot game on Windows and tried to get
bad work through. 9 tries were caught. 4 got through, all by one gap: a changed guard file at upload. 3 false alarms and
4 Windows faults were also found. All are fixed here:
- **A changed guard waits for the owner's yes** (`fg/ownerok.py`, F139 to F143). The upload itself now stops on a change
  to the kit's own code or settings, or on a guard or test made weaker, until the owner has said yes for that exact
  version of the file. Run by a helper, `python fg/ownerok.py --give` opens the AI tool's own permission box; without the
  hook it needs a real terminal and a typed code. A helper cannot give it.
- **"Weaker" is compared with the right base** (F143). It used to be compared with a commit recorded for another
  branch, so undoing a weakening was itself called weaker.
- **Windows** (F146, F147, F150): the hooks call the full path of a Python that exists, because the word python often
  opens the Microsoft Store. Settings saved by PowerShell (with a BOM, or as UTF-16) are read, and broken JSON gives a
  plain message. The guard's self-check reads a piped command, so it works in PowerShell.
- **The summary waits for the upload** (F144, F145). It no longer says "Everything passed" before the upload has
  happened; the line after the box says whether the upload worked. The first push sets the branch's upstream.
- **Room for a small fix** (F148). A file already over its size limit may take a fix of up to 10 lines over its
  recorded size; the room never adds up.
- **A check made constant counts as weaker** (F149): `ok(x == 0.0, ...)` turned into `ok(true, ...)`.
- **One guard file can be refused outright** while the rest only ask (`guard_decisions`, F151). Asked for by the game's
  build thread for its merge sign-off file.
- AGENT_SETUP.md: the PowerShell self-check, "No Python?", and a warning that a copy of a Godot project shares the
  real game's saves until it is renamed. (In the test it overwrote the real game's save.)

**The saved-state check, logic check part 2** (`fg/state.py`, F152 to F160). Owner's go: "if you think adding the
test about saves as well that's fine". For each type the project lists, it lists every field and reports each one
that the save, the load or the fingerprint never mentions, unless a reason of three words or more is written. It
reads text only and takes under a second, so it runs as the part "state" of every upload. It reads C++ and Python.
`--suggest` finds the types that look like saved state.
- Results against pass lines written before any code (`evidence/results/RESULTS_state_check.md`): all met.
  - On the game it found all 8 fields that an audit had found by reading. A reader has 17 other fields to go through.
  - Planted omissions: 157 of 157 found, and 145 of 150 with a harder planting.
  - A running program agrees on all 15 fields of the hydrology edit layer.
  - The field lists match clang's own parser on 89 of 89 types in game headers held back until the end.
- Limits, as measured: it matches names, so a field named in the save for another reason counts as kept. It cannot tell
  scratch values from state that steers the game. Python was tested on fixtures only.
- Numbers: 160 checks proven by break, 152 tests.

## In work after v0.8.5 (11 Nov): the logic check, part 1
Owner's ask: "Wouldnt there be a way to make it be able too know if logic is sound right?"
- **Would any test notice?** (`fg/logic.py`, F130 to F138). For the lines changed since the last upload it makes one
  small change at a time in a copy of the project (a comparison turned into its opposite, "and" for "or", a plus for a
  minus, a number one higher), runs the tests that guard the file, and lists the changes no test noticed. It reports and never
  blocks. The project itself is never touched; strings, comments and imports are never changed; a change that makes
  the tests hang is stopped and counts as noticed; tests that already fail are refused. Python and C-family languages.
  It cannot show that logic is right: it shows lines that no test looks at. Results: `evidence/results/RESULTS_logic_check.md`.
- **Fault found by the first real run and fixed (F136):** on the game's hydrology core the first version reported
  changes on lines the tests never build (inside a compile-time switch that is off) as logic the tests missed. Now,
  when nothing notices a change, the same place is filled with text no language accepts and the tests run once more;
  if they still pass, the line is listed apart as NEVER BUILT OR LOADED BY THE TESTS.
- A run that is stopped takes its test run down with it and removes its copy (F137).
- **Second fault, found by the kit's own pass line and fixed (F138):** of 8 "not noticed" reports drawn at random on
  the hydrology core, only 2 were real gaps in the tests; 6 could not alter any result (a comparison's edge moved by
  one where the edge is never reached, a start value that is always replaced). The pass line needed 5. Now a
  comparison is turned into its opposite by default and a bare start value is left alone. The two noisy kinds come
  only with `--exact` and are listed apart, under EXACT VALUE NOT TESTED. The price: by default an untested edge (an
  off-by-one) is no longer shown.
- `--minutes N` for slow test commands: the kit's own full test file (166 s) got 7 changes done in the default 20.
- AGENT_SETUP.md section 14 tells the helper when to run it and what to do with the list.
- Numbers: 138 checks proven by break, 132 tests. Evidence: `evidence/logic_check/`.

## v0.8.5 beta (11 Nov): no more merge walls, developer mode, a hole closed
Owner's ask: "users ... get stuck behind multi day merge walls bc the testing fully restarts at every miss".
- **Step-by-step gate** (`fg/stages.py`, F102, F104 to F111, F113 to F121). The gate can be a list of named steps
  ("gate_steps") instead of one command. Every step runs even after one fails and every failure is listed in one run.
  Each result is kept for the exact commit it ran on. After a fix, only the failed steps and the steps guarding the
  changed files run again. Everything runs when a changed file is guarded by no step, when the gate's own files or the
  machine's setup changed, when a step's definition changed, or when no whole run passed in the last day and a half.
  Steps marked "always" (slow rot: old saves, soak, replay) run on every new commit. `python fg/push.py --gate --whole`
  is the nightly whole run; it names any step whose list of guarded files was too narrow. A step that gives two answers
  on one commit is called out as flaky. `python fg/stages.py --plan` shows what the next gate would run and why.
- The kit's own checks no longer stop at the first one that fails: all of them report in one run (F103).
- **Hole closed (F112), found while building this version, never seen used:** the file that records "this commit
  passed" was not a guard file, so a helper could write a commit's id into it and the push wrapper then reported "gate
  passed" for work whose tests fail. The pass records are now guard files (the owner is asked). v0.8.4 has the hole.
- **Developer mode** (`fg/parts.py`, F122 to F124), owner's ask: "a developer mode that let's you pick and choose
  whichever features you want to enable". One screen lists every feature in plain words with its setting; pick by name or
  number, "only these", a preset (everything, core, watch), or type on the screen (`pick`). `setup.py --developer` shows
  it at the end of setup. A helper switching several features asks the owner. Beginners see none of it.
- A one-command gate that takes over ten minutes tells the helper to split it into steps and where the instructions
  are (F125), so nobody has to know the feature exists. AGENT_SETUP.md section 13 is the helper's guide.
- New cards in plain words: "Some of the project's test steps failed", "A test step changed the project while it
  ran", "The list of test steps is set up wrongly".
- Found by the beginner tests of 11 Nov (fresh, smaller helpers and a simulated owner; `evidence/results/RESULTS_v0.8.5.md`) and fixed
  after them:
  - the upload that installs the kit showed 14 false "a check was made weaker" cards, one for each kit file whose own
    text holds words like "skip" (F126);
  - `push.py --help` ran the gate and the upload. Every command now prints its help for `--help` or `-h` and does
    nothing else (F127);
  - the first upload showed a false "made weaker" card for the outside software the project already used (the record
    setup had just written). A first record is not a weakening; what somebody allowed in their own words, an entry
    added to an existing record, and a removed record still show (F128);
  - the slow-gate note said "the tests took 0 minutes" for a gate under half a minute, and the guide said not to split
    a gate of "a few minutes", so the helper did not split. The note now gives seconds and says the time is over this
    project's own limit, and the guide says to split whenever the note appears (F125's test now checks the wording).
- **Safety gap closed before release (F129)**, found while trying the test harness on a split gate: with one command
  every test is found by itself, but with steps a new test file that nobody listed under a step was run by no step, and
  a failing one was uploaded. The gate now stops and names any test file that is in no step's "guards".
- The kit's own code now passes its own code-shape check with no failure (two card builders were split).
- Numbers now: 122 tests, 129 approved checks.

## v0.8.4 beta (11 Nov): release candidate
Feature freeze from v0.8.3: only fixes and release clean-up.
- Unity "couldn't run" card (F097): Unity exit 1 means it couldn't run the tests (compile, project or licence problem),
  exit 2 means tests failed. The card now says which. Both still block.
- Guard false alarm fixed (F098), found by the weaker-AI test with the guard hook live: `2>&1`, `>/dev/null` and the
  `>` in a commit's author line counted as "writing" to any guard file named in the same command, so every "commit and
  upload" and many read-only commands asked the owner. Real writes to guard files still ask.
- Second guard false alarm fixed (F099), same test: a command that wrote an ordinary file (for example
  `cat > src/harvest.py <<EOF`) and also ran `fg/push.py` asked the owner. The redirect's own target now decides;
  piped or substituted here-documents and unreadable targets still ask.
- Approved checks are fixed (F101), found by the weaker-AI test round 2: a helper changed an approved rule's code and
  its test's expected numbers together, and every check passed. Changing or removing the test named for an approved
  rule now stops the upload with a "for you" card.
- Third guard false alarm fixed (F100): a write in one part of a chained command and a guard-file name in another part
  asked the owner. Each part is now read on its own, and `cd` is followed, which also closes an old gap
  (`cd fg && sed -i ... push.py` was not caught).
- Plain-words pass on the owner's cards after a re-test with three simulated beginner owners: jargon replaced or
  explained, helper-only lines marked "For the helper", the "No tests are set up" card no longer reads as a job for
  the owner.
- Privacy clean-up of examples, tests and results for the public release.
- Docs reorganised for release: README, CHANGELOG, CONTRIBUTING, SECURITY, a GitHub test workflow.
- Numbers now: 94 tests, 101 approved checks.

## v0.8.3 (9 Nov)
- GitHub lock reminder (F095): until GitHub shows the project is locked, every push summary carries a "FOR YOU" card and
  tells the helper to walk the owner through `python fg/lock.py --steps`. It clears when `gh` shows the lock or the owner
  confirms in their own words (`--confirm --words`). A confirmation is shown as the owner's decision (F096). If the lock
  later shows as off, the card returns. Projects not on GitHub get no card.

## v0.8.2 (9 Nov)
- Python `import` lines count as new outside software (F088). A helper's own allow is listed as the owner's decision
  (F089). Both gaps were found by smaller Claude models in the weaker-helper test.
- The gate makes the test report folder, clears the old report, and fails if none is written (F090; found in the Godot test).
- Command guard also works in GitHub Copilot CLI, OpenAI Codex CLI and Cursor (F091-F093). Install writes their hook
  files and copies the helper rules to `AGENTS.md`, `.github/copilot-instructions.md` and
  `.cursor/rules/foundationguard.mdc` (F094). Tested with documented hook input, not inside the real tools.
- Engine test commands run on real engines: Godot 4.3 with GUT 9.3.1 and Unity 6.6. See `evidence/results/RESULTS_v0.8.2.md`.
- Numbers then: 87 tests, 94 approved checks.

## v0.8.1 (9 Nov)
- A plain-words card for every failure kind (F083), facts about new outside software from local files (F084), one
  summary per push (F085), weakened checks listed as decisions on a passing push (F086).
- Clean-up: 55 tangled functions in the kit were split. Output compared word for word on every saved test project.
  Three bugs found and fixed: a crash on non-text files (F081), a crash when structure settings lacked include or
  exclude (F082), a wrong class count in the size report.
- 78/78 tests, 86/86 checks proven. A beginner-style helper made the right decision on 6 of 6 summaries.

## v0.8 (9 Nov)
- Docs pack: starter docs, session-start reminder, docs keep up with the code, docs tell the truth, `DOC_TEST.md`.
- Change forecast (`fg/forecast.py`): before and after numbers on a throwaway copy.
- Blind set: truth 60/60 caught, 0/90 false alarms. Coverage 42/42 caught, false alarms 8/64 before a fix (failed), 0/64 after.
- Fixed a Python bug in the code-shape check: a triple quote inside a normal string hid later functions (F074).
  Python projects should record the size baseline again on upgrade.
- First beginner test failed: the secret scan flagged the kit's own file (F075). Fixed; second round passed.
- 80/80 checks proven, 72/72 tests.

## v0.7 (9 Nov)
- Secret scan, GitHub settings guard, "this looks weaker" prompt, tiny-file rise check, different-helper review
  (Reviewed column, `fg/approve.py --spot`), break glass, catch log, parts on/warn/off.
- Fixed: guard paths starting with a dot (`.git/hooks`, `.claude`, `.github`) were not locked in v0.3 to v0.6 (F054).

## v0.6 (9 Nov)
- Licence ledger (`ASSETS.md`, `fg/assets.py`) and `--credits` (F046-F050). Fresh set: 21/21 new files caught, 23/25
  licence problems, 0 false alarms. The first credits list failed and was fixed.

## v0.5 (9 Nov)
- Unity and Godot: engine detection, maths presets, dependency rules, GDScript function finding, NUnit results (F038-F044).
- Fresh set: Unity maths 23/25, Godot maths 21/22, dependencies 30/30, 0 false alarms. GDScript functions 53/60 (failed), then 60/60.

## v0.4.4 to v0.4.5 (9 Nov)
- Maths rule (F033) and dependency allow-list (F034, F036). Records ask the owner (F035).
- Round 1: maths 19/19, dependencies 36/36, 0 false alarms. Adversarial round 2 failed: 31/41 and 36/45. After fixes
  (F036-F037): 40/41 and 45/45. A token-pasting macro is still missed.

## v0.4.3 (9 Nov)
- Design checks in `fg/structure.py`: copy-paste, loops between systems, tangled functions; new function finder (F022-F031).
- Design round 1: 16/20, 4/34 false alarms (failed). Round 2: 24/26, 1/36. Structure round 3: 25/27, 1/43.
  Command guard rounds 2 and 3: 55/60 and 51/60.

## v0.4.2 (9 Nov)
- Fresh agents wrote new sets. Command guard 58/60 caught, 6/60 harmless blocked (failed; 5 were direct pushes, blocked
  on purpose). Stale checks 12/12, 0/18 false alarms. Structure 22/24, 5/29 decoys flagged (failed). All fixed (F019-F021).
- Merge note can't be reworded (F018).

## v0.4.1 (9 Nov)
- Classes named with their namespace; template specialisations keep their arguments; `ignore_classes` setting (F017).
  Record the structure baseline again on upgrade.

## v0.3 (8 Nov)
- The guards guard themselves: locked guard files (F010), guard-change report (F011), a gate that can't run blocks
  (F012), setup fingerprint (F013), plain-words merge summary (F014), GitHub lock guide, `docs/HABITS.md`.
- 14/14 own checks proven.

## v0.2 (8 Nov)
- Structure check (F006-F009): big files and classes, classes smeared over files, boundaries, long functions, with a
  baseline that may only shrink. Planted problems 100/100 against 39/22/0 for rival rules, 0/60 false alarms. A
  long-function gap was found and fixed. 9/9 own checks proven.

## v0.1 (8 Nov)
- First release: command guard, tested-commit push, approved list, break-to-prove. Held-out command list: 39/40 risky
  blocked (40/40 after a post hoc fix for abbreviated options), 0/40 harmless blocked. Break-to-prove 12/12, 0/18 false
  alarms. 5/5 own checks proven.

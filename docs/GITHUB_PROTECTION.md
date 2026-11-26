# Locking the guards on GitHub (AI-made, Claude, 2026-11-08)

Everything on your own machine can be edited by an agent that works there, so the one lock an agent can't pick lives on GitHub.

1. **Give the agents their own GitHub account.** Make a free account (for example `yourgame-bot`) and invite it to the repo
   as a collaborator. On a personal repo a collaborator can push and open pull requests but can't change settings. Sign the
   bot in on the build machine for the work folder only. Your own login stays on your play copy. Never put the bot's
   token in a cloud environment.
2. **Code owners.** Set `owner_github` in foundationguard.json and run `python fg/codeowners.py`. It writes
   `.github/CODEOWNERS` naming you as owner of every guard file and of everything else.
3. **Protect main.** In the repo's Settings, under Branches, add a rule for `main`: require a pull request, require a review from
   code owners, include administrators, block force pushes and deletion, and leave the bypass list empty. Private repos need
   GitHub Pro or a paid organisation plan for this.
4. **Merge as yourself.** The bot opens the pull request, `python fg/summary.py` writes its plain-words summary, you play the
   change, approve it and press Merge.

5. **Make the note checkable (F018).** Copy `docs/foundationguard-note.yml` to `.github/workflows/`. On every pull request it
   runs `python fg/summary.py --check` on the pull request's description, so a note an agent reworded, trimmed or made for an
   older commit fails. In the branch rule, require the status check "FoundationGuard note" and set its source to GitHub
   Actions, so nobody can mark it passed by hand.

Known gap (checked 9 Nov 2026): cloud agents reach GitHub through an app that acts as you, so every change they make
carries your name and a review rule can't tell them from you. What still holds: (a) the required "FoundationGuard note"
check runs on GitHub's machines, so a cloud agent can't skip it; (b) send every piece of cloud work through the PC build
machine, whose gate must pass before anything merges; (c) agents never approve or merge, and only you press Merge.

## v0.7: take admin power away from the AI (the real lock)

The guard now blocks commands that change GitHub settings, but that is only a speed bump. The real lock is a key that
CAN'T change settings, whatever command is typed:

6. **Give helpers a limited key (a "fine-grained token").** Signed in as the bot account (step 1): Settings → Developer
   settings → Personal access tokens → Fine-grained tokens → Generate. Repository access: only this repo. Permissions:
   Contents read and write, Pull requests read and write, Metadata read. Leave everything else at "No access"
   (especially Administration, Secrets, Workflows, Webhooks). Pick an expiry (90 days is fine; set a calendar reminder).
   Sign the build machine's git in with it. The owner's own admin login stays off that machine's work folder.
7. **Include administrators.** In the main branch rule (step 3) tick "Do not allow bypassing the above settings" (also called
   "include administrators"), so the rules bind the owner's account too. Then even a helper that somehow had the owner's
   login couldn't push straight to main.
8. **Check the bypass list is empty** in the rule and in any ruleset. Look again each month (the monthly drift check lists it).

Cloud helpers that act through an app as the owner keep the owner's powers; for them, steps 7 and 8 and the required check
(step 5) are the lock. Keep "include administrators" on.

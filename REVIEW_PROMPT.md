# Check review: for a FRESH helper (AI-made, Claude, 2026-11-09)

Use this when an approved behaviour gets a new check. The review must be done by a helper session that did NOT write the
feature or its check (a new session, with no memory of writing it). Now and then, also use a different AI model:
`python fg/approve.py --spot` prints a ready-made prompt to paste into one.

Steps for the reviewing helper:
1. Read the row in APPROVED.md: the owner's words, the check's name, its break switch.
2. Read the check's code and the feature's code. Do not change either.
3. Write down three realistic ways the approved behaviour could break (not just the break switch).
4. For each, would the check fail? Say yes or no and why.
5. Is any part of the owner's words not tested at all?
6. Verdict: GOOD, WEAK (what to add) or USELESS (it passes with the feature broken).
7. Put the verdict in the row's Reviewed column (7th column) as  `helper <date> <verdict>`; this is a guard-file change,
   so the owner will be asked to OK it. A WEAK or USELESS verdict goes to the owner in plain words, with a fix to approve.

Never mark a check GOOD that you have not read. Never weaken a check to make it pass.

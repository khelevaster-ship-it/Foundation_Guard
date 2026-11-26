# Running the re-break every night

Linux/macOS (cron, 03:00): `0 3 * * * cd /path/to/repo && python3 fg/prove.py --random 3 >> .foundationguard/nightly.log 2>&1`

Windows (Task Scheduler, 03:00):
`schtasks /Create /SC DAILY /ST 03:00 /TN FoundationGuardNightly /TR "cmd /c cd /d C:\path\to\repo && python fg\prove.py --random 3 >> .foundationguard\nightly.log 2>&1"`

Before a merge: `python fg/prove.py --random 3 --seed <pull request number>` (a different pick each time, repeatable).

# Running the whole gate every night (v0.8.5, only when the gate is written as steps)

With "gate_steps" in foundationguard.json, a push re-runs only the steps a change touches. The whole run is what stands
behind those kept results: it runs every step, and it names any step whose list of guarded files turned out too narrow.
A kept result counts only while a whole run passed in the last day and a half ("whole_run_days"); if the nightly run is
missed, the next push simply runs everything.

Linux/macOS (cron, 02:00): `0 2 * * * cd /path/to/repo && python3 fg/push.py --gate --whole >> .foundationguard/nightly.log 2>&1`

Windows (Task Scheduler, 02:00):
`schtasks /Create /SC DAILY /ST 02:00 /TN FoundationGuardWhole /TR "cmd /c cd /d C:\path\to\repo && python fg\push.py --gate --whole >> .foundationguard\nightly.log 2>&1"`

It needs a clean tree on the work branch (it tests a commit, not half-finished work), and it pushes nothing.

# The owner's habits (AI-made, Claude, 2026-11-08)

When the tooling is solid, the weak spot left is what you let through.
- **Read the summary first.** Before approving, read `fg/summary.py`'s plain-words list of which approved behaviours the change touches and which guard files changed.
- **Play it yourself.** Play the change before approving. Never approve from the summary alone.
- **Sleep on big decisions.** Never approve big changes when you're tired or at the end of a session. Waiting costs nothing.
- **Watch the report.** Read the weekly guard-change report (`fg/report.py --mark`). Every softened check or new baseline should have a reason you remember giving.
- **Fix flaky checks.** A check that fails at random twice in a week gets its cause fixed. Never accept a new baseline just to make it pass.
- **Freeze updates.** Pause OS and GPU-driver auto-updates and update when you choose, right after a passing nightly run.
  The setup fingerprint flags any change and forces the full run.
- **Keep three copies.** Push often (off-site copy), keep the art backed up, and keep an external-drive copy.
- **Skim the rules monthly.** Engine licence, store rules and grant terms change as news, not code. Skim them monthly.
- **Stop adding guard systems.** Once these are in place, add a new check when a feature ships or when something actually breaks. Don't keep building new guard systems.

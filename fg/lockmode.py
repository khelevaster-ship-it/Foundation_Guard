"""FoundationGuard: is GitHub's lock what guards this project now? (AI-made, Claude, 2026-11-17; Plan 2 PR 7, merge D2.)

Plan 2, section 4: once GitHub itself holds every change to a safety check for the owner's Approve on their phone, the
kit on the PC stops asking about the owner's own guard files (tests, check scripts, lists, APPROVED.md). The helper
keeps working, the kit says at once in chat when a step weakens a check, and the upload goes to the work branch, where
GitHub asks the owner. The kit's own switches (its settings, code, hooks, workflows, CODEOWNERS) still ask, and are
still put back.

Plan 2's order rule: never take the local net away before the remote one holds. So this mode is on only when all three
hold, and falls back to the boxes the moment one doesn't:
  - the owner's "remote_lock": true in foundationguard.json (a kit setting: only the owner changes it);
  - fg/lock.py found the lock ON on GitHub within the last day (a stamped line in the proof book, lockstate.jsonl;
    every upload asks GitHub again);
  - a lock drill passed within the last 30 days (python fg/lock.py --drill).
"""
import os, time

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "lockstate"
HOURS = 24


def note(cfg, state):
    """fg/lock.py's answer, kept (only when the owner asked for the mode, so nothing else writes the book)."""
    if not cfg.get("remote_lock") or state == "could not check":
        return
    try:
        import proofstore as PS
        PS.append(cfg, BOOK, {"state": state})
    except Exception:                                    # noqa: BLE001  never in the way of the lock's own answer
        pass


def why_not(cfg):
    """None when GitHub's lock guards the project now; otherwise why not, in plain words."""
    if not cfg.get("remote_lock"):
        return "the owner hasn't switched it on (\"remote_lock\": true in foundationguard.json)"
    if BREAK("push_refuses_unlocked"):
        return None
    import drill as DR, proofstore as PS
    recs = [r for r in PS.read(cfg, BOOK) if not r.get("_bad")]
    last = recs[-1] if recs else {}
    if last.get("state") != "locked":
        return "fg/lock.py hasn't found the lock ON on GitHub" + (f" (last: {last.get('state')})" if last else "")
    if time.time() - float(last.get("at") or 0) > HOURS * 3600:
        return "fg/lock.py last found the lock ON more than a day ago"
    t = DR.last_pass(cfg)
    if not (t and time.time() - t < DR.DAYS * 86400):
        return "no lock drill has passed in the last 30 days"
    return None


def on(cfg):
    return why_not(cfg) is None

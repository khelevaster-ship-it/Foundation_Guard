"""FoundationGuard night watch: did last night's work happen? (AI-made, Claude, 2026-11-13; the owner's tool ideas,
Fable's plan: the Night Foreman's first two parts)

The worst morning is waking up to find nothing got done, and nobody said so. Jobs meant to run on a schedule are the
expected checks with every_hours in foundationguard.json; each runs through the receipt runner (python fg/receipts.py
run NAME), which ends a stuck run at its time limit (limit_minutes) so one hung job can't hold the whole night. This
reads their receipts and says, per scheduled job, in plain words:

  RAN            it ran within its schedule and passed
  RAN ON A RETRY it failed, then passed when run again on the same code: said in the morning, not counted as clean
  FAILED         it ran and failed (or was stopped at its time limit; the reason says which)
  DID NOT FINISH it started and never ended (the computer slept, or the run was killed)
  DIDN'T RUN     it should have run by now and didn't (or has never run)
  CLAIMED ONLY   it ran somewhere the kit can't trust (a cloud session's run, or a receipt written by hand)

  python fg/night.py           every scheduled job; also written to .foundationguard/night.json for a status board
  python fg/night.py --hook    the session-start message: silent when all is well, otherwise a plain warning that
                               the helper passes on to the owner first thing
Part night (on, warn, off): off is silent. It only informs.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import proofstore as PS
import receipts as RC

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
WORD = {"PROVEN": "RAN", "OUT OF DATE": "RAN", "PASSED ON A RETRY": "RAN ON A RETRY", "FAILED": "FAILED",
        "DID NOT FINISH": "DID NOT FINISH", "RUNNING": "RUNNING", "OVERDUE": "DIDN'T RUN", "NEVER RAN": "DIDN'T RUN",
        "CLAIMED ONLY": "CLAIMED ONLY"}
OK = ("RAN", "RUNNING")


def scheduled(cfg):
    return [e for e in RC.expected(cfg) if e.get("every_hours")]


def report(cfg):
    """[(job, word, plain words)] for every scheduled job."""
    runs = RC._runs(cfg)
    now = RC.now(cfg)
    rows = []
    for e in scheduled(cfg):
        w, why = RC.state(cfg, e, runs, now)
        w = "PROVEN" if w == "PASSED ON A RETRY" and BREAK("night_retry") else w
        rows.append((e["name"], WORD.get(w, w), why))
    sd = os.path.join(cfg["_root"], cfg.get("state_dir") or ".foundationguard")
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, "night.json"), "w", encoding="utf-8") as f:
        json.dump({"worked_out_at": time.time(), "jobs": [{"job": j, "word": w, "why": why} for j, w, why in rows]},
                  f, indent=1)
    return rows


def headline(rows):
    bad = [r for r in rows if r[1] not in OK]
    if not bad:
        return f"all {len(rows)} scheduled job(s) ran and passed."
    return f"{len(bad)} of {len(rows)} scheduled job(s) did not get done: " + "; ".join(
        f"{j} {w} ({why})" for j, w, why in bad[:5]) + "."


def hook(cfg):
    if C.part(cfg, "night") == "off" or not scheduled(cfg):
        return 0
    rows = report(cfg)
    if all(w in OK for _, w, _ in rows) or BREAK("night_hook"):
        return 0
    print("FG-NIGHT: " + headline(rows) + " Tell the owner this first, in plain words, before other work: the work they "
          "expected overnight did not happen. Don't run it again quietly to hide it; python fg/night.py has the detail.")
    return 0


def main(argv):
    cfg = C.load()
    if "--hook" in argv:
        return hook(cfg)
    if not scheduled(cfg):
        print("FG-NIGHT: no scheduled jobs (expected_checks with every_hours in foundationguard.json)."); return 0
    rows = report(cfg)
    for j, w, why in rows:
        print(f"  {w:<14} {j}: {why}")
    print("FG-NIGHT: " + headline(rows))
    return 0 if all(w in OK for _, w, _ in rows) else 1


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

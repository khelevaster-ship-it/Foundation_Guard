"""FoundationGuard's owner OK ledger: your yes can't be reused (AI-made, Claude, 2026-11-13; the owner's tool ideas,
Fable's plan).

Every yes the owner gives with python fg/ownerok.py --give is one line in the kit's proof store (fg/proofstore.py),
never rewritten: which item (a file, or "tests that stopped running"), the exact version it covers, what the owner was
shown, how the yes was given (the permission box or a typed code), and when it runs out. An OK counts only while:
  - it is for that exact version: change the file again and the OK no longer covers it;
  - it hasn't run out (ok_hours in foundationguard.json, 24 by default);
  - it hasn't been used: the upload that carries the change uses it up, so it can't cover a later change;
  - no later OK for the same item replaced it;
  - its line is as the kit wrote it (stamped and chained; a hand-written or changed line is no OK).

  python fg/ledger.py        every OK: LIVE, USED, RUN OUT, REPLACED or NOT TRUSTED, newest last
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import proofstore as PS

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "ledger"


def grant(cfg, todo, how, shown):
    """Write one OK per item [(item, why, version)]."""
    hours = float(cfg.get("ok_hours", 24))
    for item, why, version in todo:
        rec = {"id": "K" + os.urandom(3).hex().upper(), "event": "granted", "item": item, "version": version}
        rec.update(why=why[:400], how=how, shown=shown[:4000], expires=time.time() + hours * 3600, where=PS.where())
        PS.append(cfg, BOOK, rec)


def oks(cfg, now=None):
    """[(record, state)] for every OK, oldest first. state: LIVE, USED, RUN OUT, REPLACED or NOT TRUSTED."""
    now = now or time.time()
    recs = PS.read(cfg, BOOK)
    used = {r.get("id") for r in recs if r.get("event") == "used" and not r.get("_bad")}
    granted = [r for r in recs if r.get("event") == "granted"]
    newest = {}
    for r in granted:                                  # a line changed by hand still replaces the older ones
        newest[r.get("item")] = r.get("id")
    strict = C.part(cfg, "ledger") != "off"
    return [(r, _state(r, used, newest, now, strict)) for r in granted]


def _state(r, used, newest, now, strict=True):
    if r.get("_bad"):
        return "NOT TRUSTED"
    if not strict:                                     # the ledger part off: a yes for a version counts while it stays
        return "LIVE" if newest.get(r.get("item")) == r.get("id") else "REPLACED"
    if r.get("id") in used and not BREAK("ledger_single_use"):
        return "USED"
    if newest.get(r.get("item")) != r.get("id") and not BREAK("ledger_replaced"):
        return "REPLACED"
    if now > float(r.get("expires") or 0) and not BREAK("ledger_expiry"):
        return "RUN OUT"
    return "LIVE"


def live(cfg):
    """{item: version} for every OK that still counts."""
    return {r["item"]: r["version"] for r, st in oks(cfg) if st == "LIVE"}


def matching(cfg, todo):
    """The IDs of the live OKs that cover these items [(item, why, version)] exactly."""
    want = {(f, v) for f, _, v in todo}
    return [r["id"] for r, st in oks(cfg) if st == "LIVE" and (r["item"], r["version"]) in want]


def use(cfg, ids):
    """The upload that carried these changes used these OKs up."""
    for i in ids:
        PS.append(cfg, BOOK, {"id": i, "event": "used"})


def main(argv):
    cfg = C.load()
    rows = oks(cfg)
    for r, st in rows:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("at") or 0))
        print(f"  {st:<11} {r.get('id')}  {when}  {r.get('item')}: {r.get('why', '')[:120]} (given in the {r.get('how')})"
              + (f"; {r['_bad']}" if r.get("_bad") else ""))
    print(f"FG-LEDGER: {sum(1 for _, s in rows if s == 'LIVE')} live OK(s) of {len(rows)}.")
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

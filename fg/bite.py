"""FoundationGuard bite test: do my checks still bite? (AI-made, Claude, 2026-11-13; the owner's tool ideas, Fable's plan)

The approved list already holds a named break for every guard (its Break column), and python fg/prove.py breaks each
feature on purpose and runs its check, which must then fail. What was missing: a proof is trusted after the code
changed, and nothing shows which guards were proven when. Now every prove run leaves a stamped record in the kit's proof
store (on exactly which code, where it ran), and this says, per guard, in one word:

  BITES              its check failed when the feature was broken, on exactly the code as it is now
  HOLLOW             its check still passed with the feature broken: it guards nothing
  OUT OF DATE        it bit, but the code has changed since
  ALREADY FAILING    its check fails before anything is broken: fix that first
  BREAK DOESN'T FIT  the break (a patch) no longer applies to the code
  NO BREAK           the row has no way to break it
  NEVER TRIED        no proof on record
  CLAIMED ONLY       a proof the kit can't trust (a cloud session's, or written by hand)

  python fg/bite.py                   every guard's word; also written to .foundationguard/bites.json
  python fg/bite.py --pilot 10        prove 10 guards picked at random, and say how long a full run would take
  python fg/bite.py --refresh [N]     prove again the guards that aren't BITES (at most N, default 20): for a nightly run
The breaks live in the approved list, a guard file, so taking one away asks the owner. Automatic small changes to
the code (would any test notice?) are fg/logic.py. This only informs.
"""
import json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import approved as A
import proofstore as PS

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
WORDS = {"BITES": "its check failed when the feature was broken, on exactly the code as it is now",
         "HOLLOW": "its check still passed with the feature broken: it guards nothing",
         "OUT OF DATE": "it bit, but the code has changed since", "ALREADY FAILING": "its check fails before anything is broken",
         "BREAK DOESN'T FIT": "the break no longer applies to the code", "NO BREAK": "the row has no way to break it",
         "NEVER TRIED": "no proof on record", "CLAIMED ONLY": "a proof the kit can't trust (a cloud session's, or by hand)"}
VERDICT = {"PROVEN": "BITES", "STALE": "HOLLOW", "FAILS_UNBROKEN": "ALREADY FAILING", "BREAK_DID_NOT_APPLY": "BREAK DOESN'T FIT"}


def _latest(cfg):
    out = {}
    for r in PS.read(cfg, "bites"):
        if r.get("row"):
            out[r["row"]] = r
    return out


def word(row, rec, tree, work=""):
    """(word, plain words) for one approved row and its newest proof record."""
    if not row["break"] or row["break"] in ("-", "none"):
        return "NO BREAK", WORDS["NO BREAK"]
    if not rec:
        return "NEVER TRIED", WORDS["NEVER TRIED"]
    if rec.get("_bad") or rec.get("where") not in ("pc", "ci"):
        return "CLAIMED ONLY", rec.get("_bad") or f"proven in a {rec.get('where')} session; prove it again here"
    w = VERDICT.get(rec.get("verdict"), "NEVER TRIED")
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(rec.get("at") or 0))
    then = rec.get("work", "" if not rec.get("dirty") else "?")
    if w == "BITES" and rec.get("tree") != tree and not BREAK("bite_tree"):
        return "OUT OF DATE", f"it bit on {str(rec.get('commit'))[:9]} ({when}); the code has changed since"
    if w == "BITES" and then != work and not BREAK("bite_work"):
        return "OUT OF DATE", f"it bit ({when}), but files in the folder have changed since and aren't committed"
    return w, f"{WORDS[w]} ({when})"


def status(cfg):
    tree = PS.code_now(cfg["_root"])[1]
    work = PS.work_now(cfg["_root"], cfg.get("state_dir") or ".foundationguard")
    latest = _latest(cfg)
    rows = [(r["id"],) + word(r, latest.get(r["id"]), tree, work) for r in A.rows(cfg)]
    sd = os.path.join(cfg["_root"], cfg.get("state_dir") or ".foundationguard")
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, "bites.json"), "w", encoding="utf-8") as f:
        json.dump({"worked_out_at": time.time(), "words": WORDS,
                   "guards": [{"row": i, "word": w, "why": why} for i, w, why in rows]}, f, indent=1)
    return rows


def _prove(cfg, args):
    return subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "prove.py")] + args,
                          cwd=cfg["_root"], capture_output=True, text=True, encoding="utf-8", errors="replace")


def pilot(cfg, n):
    t0 = time.time()
    p = _prove(cfg, ["--random", str(n), "--seed", str(int(t0))])
    took = time.time() - t0
    total = len([r for r in A.rows(cfg) if r["break"]])
    each = took / max(1, n)
    print(p.stdout[-3000:])
    print(f"FG-BITE pilot: {n} guard(s) in {round(took)} s, about {round(each, 1)} s each; all {total} would take about "
          f"{round(each * total / 60)} min.")
    return p.returncode


def refresh(cfg, most):
    todo = [i for i, w, _ in status(cfg) if w not in ("BITES", "NO BREAK")][:most]
    for i in todo:
        _prove(cfg, ["--id", i])
    print(f"FG-BITE: proved {len(todo)} guard(s) again.")
    return show(cfg)


def show(cfg):
    rows = status(cfg)
    for i, w, why in rows:
        print(f"  {w:<17} {i}: {why}")
    counts = {}
    for _, w, _ in rows:
        counts[w] = counts.get(w, 0) + 1
    said = ", ".join(f"{n} {w}" for w, n in sorted(counts.items())) or "no approved guards yet (APPROVED.md is empty)"
    print("FG-BITE: " + said + ". Only BITES is proven on this code.")
    return 0 if all(w in ("BITES", "NO BREAK") for _, w, _ in rows) else 1


def main(argv):
    cfg = C.load()
    if "--pilot" in argv:
        return pilot(cfg, int(argv[argv.index("--pilot") + 1]))
    if "--refresh" in argv:
        i = argv.index("--refresh")
        return refresh(cfg, int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 20)
    return show(cfg)


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

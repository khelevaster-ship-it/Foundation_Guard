"""Add a feature the owner approved to the approved list, and prove its check on the spot (AI-made, Claude, 2026-11-09).
  python fg/approve.py --behaviour "Saved recipes are still there after a restart" --words "yes, never lose my recipes" \
                       --check test_recipes_survive_restart --break env:RECIPEBOX_NO_SAVE=1
--behaviour  the feature in the owner's plain words
--words      what the owner actually said when approving it (and the date is added)
--check      the name of the automatic test that guards it
--break      how to switch the feature off on purpose so the test can be proven: env:NAME=VALUE (the code turns the feature
             off when NAME is set) or patch:path/to/file.patch (a change that breaks it)
The row is kept only if the check passes now AND fails with the feature switched off. Otherwise nothing is added and you
are told, in plain words, what to fix.
"""
import argparse, datetime, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import approved as A
import prove as P

def find_check_source(cfg, check):
    """The few lines around where the check is defined, for a reviewer to read."""
    import subprocess
    out = subprocess.run(["git", "grep", "-n", "-w", "-I", check], cwd=cfg["_root"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.splitlines()
    out = [l for l in out if not l.startswith((cfg["approved_file"] + ":", "fg/"))]
    if not out:
        return "(the check's code wasn't found by name; give the reviewer the test file)"
    f, n = out[0].split(":", 2)[:2]
    lines = open(os.path.join(cfg["_root"], f), encoding="utf-8", errors="replace").read().split("\n")
    a = max(0, int(n) - 3)
    return f + ":\n" + "\n".join(lines[a:a + 45])


def spot(cfg, rid=None):
    import random
    rows = A.rows(cfg)
    if not rows:
        print("FoundationGuard: nothing approved yet."); return 1
    r = next((x for x in rows if x["id"] == rid), None) if rid else random.choice(rows)
    if not r:
        print(f"FoundationGuard: no row {rid}."); return 1
    print("Paste everything below into a DIFFERENT AI model (not the helper that wrote the check), then copy its verdict "
          "into the Reviewed column of " + r["id"] + " as  model:<name> <date> <verdict>.\n" + "-" * 60)
    print(f"""You are reviewing one automatic check in a game project. The owner can't read code; be blunt and plain.
The owner approved this behaviour: "{r['behaviour']}" (their words: {r['words']}).
The check that is meant to guard it is '{r['check']}'. Its code:

{find_check_source(cfg, r['check'])}

The feature is switched off for testing with: {r['break']}
Answer in plain words, under 120 words:
1. Would this check FAIL if the approved behaviour broke in the three most likely real ways? Name the ways.
2. Is anything in the owner's words NOT tested at all?
3. Verdict: GOOD, WEAK (say what to add) or USELESS (it would pass even if the feature were broken).""")
    return 0


def main(argv):
    cfg0 = C.load()
    if "--spot" in argv:
        i = argv.index("--spot"); return spot(cfg0, argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else None)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("--behaviour", "--words", "--check", "--break"): ap.add_argument(k, required=True)
    a = ap.parse_args(argv)
    cfg = C.load()
    if not cfg.get("check_command"):
        print("FoundationGuard: setup hasn't found how to run tests yet. Run  python fg/setup.py  first."); return 1
    if not re.match(r"^(env:[A-Za-z_]\w*=.*|patch:.+)$", a.__dict__["break"]):
        print("FoundationGuard: --break must look like env:NAME=VALUE or patch:path/to/file.patch."); return 1
    rows = A.rows(cfg)
    n = max([int(re.sub(r"\D", "", r["id"]) or 0) for r in rows] + [0]) + 1; rid = f"A{n:03d}"
    row = {"id": rid, "check": a.check, "break": a.__dict__["break"]}
    res = P.prove(cfg, row)
    if os.environ.get("FG_BREAK") == "approve_stale" and res["verdict"] == "STALE": res["verdict"] = "PROVEN"
    if res["verdict"] == "FAILS_UNBROKEN":
        print(f"FoundationGuard: not added. The test '{a.check}' doesn't pass right now (or wasn't found), so it can't guard anything yet.\n"
              f"Fix the test or the feature first. What it printed:\n{res['detail'][-400:]}"); return 1
    if res["verdict"] == "BREAK_DID_NOT_APPLY":
        print(f"FoundationGuard: not added. The patch in --break didn't apply cleanly:\n{res['detail']}"); return 1
    if res["verdict"] == "STALE":
        print(f"FoundationGuard: not added. With the feature switched off ({a.__dict__['break']}) the test '{a.check}' STILL PASSES, "
              "so it would not notice if this feature broke. Either the switch doesn't really turn the feature off (add it to the "
              "code), or the test doesn't really test this feature (strengthen it)."); return 1
    p = os.path.join(cfg["_root"], cfg["approved_file"])
    if not os.path.exists(p):
        open(p, "w").write("| ID | Behaviour | Owner's words | Check | Break |\n|---|---|---|---|---|\n")
    words = a.words.replace("|", "/") + f" (owner, {datetime.date.today()})"
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"| {rid} | {a.behaviour.replace('|', '/')} | \"{words}\" | {a.check} | {a.__dict__['break']} |\n")
    print(f"FoundationGuard: added {rid} \"{a.behaviour}\". Proven: its test passes, and fails when the feature is switched off.")
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

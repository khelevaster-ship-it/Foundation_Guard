"""FoundationGuard break-to-prove runner (AI-made, Claude, 2026-11-08).

For each approved behaviour: run its check as is (it must pass), then break the feature on purpose (its Break column) and
run the check again (it must FAIL). A check that still passes with its feature broken is stale: it no longer guards
anything. The feature is always put back, whatever happens.

  python fg/prove.py --all             # every approved behaviour
  python fg/prove.py --random 3        # three picked at random (seeded by today's date unless --seed): nightly / pre-merge
  python fg/prove.py --id A004
Needs check_command in foundationguard.json, with {check} where the check's name goes, e.g. "python -m pytest -q -k {check}".
"""
import datetime, json, os, random, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import approved as A


def run_check(cfg, check, env_extra=None):
    env = dict(os.environ); env.update(env_extra or {})
    cmd = cfg["check_command"].replace("{check}", check)
    p = subprocess.run(cmd, shell=True, cwd=cfg["_root"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=cfg.get("check_timeout_s", 1800))
    return p.returncode == 0, (p.stdout + p.stderr)[-600:]


def prove(cfg, r):
    ok0, out0 = run_check(cfg, r["check"])
    if not ok0:
        return {"id": r["id"], "verdict": "FAILS_UNBROKEN", "detail": out0}
    brk = r["break"]; root = cfg["_root"]
    if brk.startswith("env:"):
        k, v = brk[4:].split("=", 1)
        ok1, out1 = run_check(cfg, r["check"], {k: v})
    else:
        patch = os.path.join(root, brk[6:])
        a = subprocess.run(["git", "apply", patch], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if a.returncode != 0:
            return {"id": r["id"], "verdict": "BREAK_DID_NOT_APPLY", "detail": a.stderr[-400:]}
        try:
            ok1, out1 = run_check(cfg, r["check"])
        finally:
            subprocess.run(["git", "apply", "-R", patch], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if os.environ.get("FG_BREAK") == "prove_stale":
        ok1 = False
    return {"id": r["id"], "verdict": "STALE" if ok1 else "PROVEN", "detail": "" if not ok1 else "the check still passed with the feature broken"}


def _record(cfg, res):
    """The bite test's record (fg/bite.py): which row, what verdict, on exactly which code, where it ran."""
    import proofstore as PS
    if os.environ.get("FG_BREAK") == "bite_record":
        return
    commit, tree, dirty = PS.code_now(cfg["_root"])
    rec = {"row": res["id"], "verdict": res["verdict"], "commit": commit, "tree": tree, "dirty": dirty}
    rec.update(where=PS.where(), seconds=res.get("seconds"), work=PS.work_now(cfg["_root"], cfg.get("state_dir") or ".foundationguard"))
    PS.append(cfg, "bites", rec)


def main(argv):
    cfg = C.load(); R = A.rows(cfg)
    if "--id" in argv:
        R = [r for r in R if r["id"] == argv[argv.index("--id") + 1]]
    elif "--random" in argv:
        n = int(argv[argv.index("--random") + 1])
        seed = argv[argv.index("--seed") + 1] if "--seed" in argv else datetime.date.today().isoformat()
        R = random.Random(seed).sample(R, min(n, len(R)))
        print(f"PROVE: random pick, seed {seed}: {', '.join(r['id'] for r in R)}")
    elif "--all" not in argv:
        print(__doc__); return 2
    sd = os.path.join(cfg["_root"], cfg["state_dir"]); os.makedirs(sd, exist_ok=True)
    bad = 0
    for r in R:
        t = time.time(); res = prove(cfg, r); res["seconds"] = round(time.time() - t, 2); res["when"] = datetime.datetime.now().isoformat(timespec="seconds")
        print(f"PROVE {res['id']}: {res['verdict']} ({res['seconds']} s) {res['detail'][:200]}")
        bad += res["verdict"] != "PROVEN"
        with open(os.path.join(sd, "prove_log.jsonl"), "a") as f:
            f.write(json.dumps(res) + "\n")
        _record(cfg, res)
    print(f"PROVE: {len(R) - bad} of {len(R)} checks proven" + (f"; {bad} need attention" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

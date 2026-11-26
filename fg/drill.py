"""FoundationGuard lock drill (AI-made, Claude, 2026-11-17; Plan 2 part 5, merge C).

A lock is only proven by trying to break it. Run by the helper, signed in as the helpers' account:
  python fg/lock.py --drill
On GitHub, as that account, it:
  1. makes a throwaway branch (fg-drill-<time>) with one harmless file, and opens a pull request for it;
  2. tries to merge it                                    (must be refused);
  3. posts a green "FoundationGuard note" status itself   (GitHub takes it, but it must not unlock the merge);
  4. tries to approve its own pull request                (must be refused);
  5. tries to merge again                                 (must be refused);
then closes the pull request and deletes the branch. Every try that GitHub refuses is a pass; any that goes through
is a hole, named in plain words. The result is a stamped line in the proof book (drill.jsonl), and with a team,
fg/lock.py says ON only when a drill passed in the last 30 days. Nothing reaches main: if a merge did go through, the
drill says so at once, loudly, and the owner reverts that one harmless file.
"""
import base64, json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "drill"
DAYS = 30
NOTE = "FoundationGuard note"


def _api(root, gh, method, path, data=None):
    """(ok, answer or GitHub's words)."""
    cmd = [gh, "api", "-X", method, path] + (["--input", "-"] if data is not None else [])
    try:
        p = subprocess.run(cmd, cwd=root, input=json.dumps(data) if data is not None else None, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30,
                           stdin=None if data is not None else subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, type(e).__name__
    if p.returncode != 0:
        return False, ((p.stderr or "") + (p.stdout or "")).strip()[:300]
    try:
        return True, json.loads(p.stdout) if p.stdout.strip() else {}
    except ValueError:
        return True, {}


def run(root, repo, gh, main="main"):
    """[(step, passed, words)] for each try, and the cleanup."""
    out, name = [], "fg-drill-" + time.strftime("%Y%m%d-%H%M%S")
    ok, ref = _api(root, gh, "GET", f"repos/{repo}/git/ref/heads/{main}")
    if not ok:
        return [("read main", False, f"couldn't read {main}: {ref}")]
    sha = (ref.get("object") or {}).get("sha")
    ok, why = _api(root, gh, "POST", f"repos/{repo}/git/refs", {"ref": f"refs/heads/{name}", "sha": sha})
    if not ok:
        return [("make a branch", False, f"couldn't make the drill's branch: {why}")]
    try:
        ok, put = _api(root, gh, "PUT", f"repos/{repo}/contents/fg-drill.txt",
                       {"message": "FoundationGuard lock drill (a throwaway change; never merged)", "branch": name,
                        "content": base64.b64encode(b"A FoundationGuard lock drill. Safe to delete.\n").decode()})
        head = ((put or {}).get("commit") or {}).get("sha") if ok else None
        ok, pr = _api(root, gh, "POST", f"repos/{repo}/pulls", {"title": "FoundationGuard lock drill (do not merge)",
                      "head": name, "base": main, "body": "The kit tries to get round the lock here. It closes this itself."})
        if not ok:
            return out + [("open a pull request", False, f"couldn't open one: {pr}")]
        n = pr.get("number")
        merge = lambda: _api(root, gh, "PUT", f"repos/{repo}/pulls/{n}/merge", {"merge_method": "merge"})
        tried = merge()
        out.append(("merge without an approval", not tried[0], "refused" if not tried[0] else "IT MERGED"))
        _api(root, gh, "POST", f"repos/{repo}/statuses/{head or pr.get('head', {}).get('sha')}",
             {"state": "success", "context": NOTE, "description": "posted by the helpers' account (the drill)"})
        ok, why = _api(root, gh, "POST", f"repos/{repo}/pulls/{n}/reviews", {"event": "APPROVE", "body": "drill"})
        out.append(("approve its own change", not ok, "refused" if not ok else "GitHub TOOK THE HELPER'S APPROVE"))
        tried = merge()
        out.append(("merge after faking the check and approving", not tried[0], "refused" if not tried[0] else "IT MERGED"))
        _api(root, gh, "PATCH", f"repos/{repo}/pulls/{n}", {"state": "closed"})
    finally:
        _api(root, gh, "DELETE", f"repos/{repo}/git/refs/heads/{name}")
    return out


def record(cfg, results):
    import proofstore as PS
    passed = bool(results) and all(p for _, p, _ in results)
    PS.append(cfg, BOOK, {"passed": passed, "steps": [[s, p, w] for s, p, w in results]})
    return passed


def last_pass(cfg):
    """When the newest drill ran, if it passed (seconds); None when there is none, or the newest found a hole."""
    if BREAK("lock_drill"):
        return time.time()
    import proofstore as PS
    recs = [r for r in PS.read(cfg, BOOK) if not r.get("_bad")]
    return recs[-1].get("at") if recs and recs[-1].get("passed") else None


def gap(cfg):
    """The lock's missing drill in words, or None (a team only: Plan 2 part 5, "ON means drilled within 30 days")."""
    if not cfg.get("team"):
        return None
    t = last_pass(cfg)
    if t and time.time() - t < DAYS * 86400:
        return None
    return ("no lock drill has passed in the last 30 days (python fg/lock.py --drill tries to break the lock as the "
            "helpers' account; every try must be refused)")


def main(cfg, repo, gh):
    main_branch = (cfg.get("protected_branches") or ["main"])[0]
    res = run(cfg["_root"], repo, gh, main_branch)
    for s, p, w in res:
        print(f"  {'PASS' if p else 'HOLE'}  {s}: {w}")
    passed = record(cfg, res)
    print("DRILL: " + ("passed. Every try to get round the lock was refused." if passed else
                       "FAILED. The lock has a hole: tell the owner now, with the lines above."))
    return 0 if passed else 1

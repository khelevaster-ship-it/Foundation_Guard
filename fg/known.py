"""FoundationGuard: the commits the kit trusts (AI-made, Claude, 2026-11-13; outside review 6, finding 3, Grok, its fix
plan, and Claude Fable's review of the fix).

Review 6, finding 3: a helper built a commit with git's plumbing (hash-object, a spare index, commit-tree, update-ref)
in one step, which changed no file, so nothing was judged. In the next step `git checkout evil` brought a switched-off
push check, and it stayed: the check after every step trusted every branch that existed when the step began. When a
branch was made says nothing about who made what is in it. The first fix trusted each file version the kit had once
accepted; Fable's review showed a helper could then write an old version back, or `git rm` a test, and commit it in one
step. Now the kit trusts whole commits, never single files:

  seen.json (in git's shared folder, so worktrees share it) keeps the branch tips there were when the kit was first
  installed (noted once, only then) and every commit that was HEAD at a check while every guard file was exactly as
  that commit has it, plus remote branch tips git ls-remote confirmed. A commit built with plumbing and never HEAD,
  and a commit whose bad change was put back, are never noted.

Limits: a helper that first gets the commit onto the remote (a push hidden in a script) makes it trusted; a program can
write seen.json (removing it only takes trust away).
"""
import json, os, subprocess

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
KEEP = 2000                 # trusted commits kept (their history is trusted too)


def _git(root, *a, data=None):
    try:
        return subprocess.run(["git", *a], cwd=root, input=data, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _path(root):
    p = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    d = p.stdout.decode("utf-8", "replace").strip() if p and p.returncode == 0 else ""
    return os.path.join(d, "foundationguard", "seen.json") if d else ""


def _tips(root):
    p = _git(root, "for-each-ref", "--format=%(objectname)")
    return sorted(set(p.stdout.decode("utf-8", "replace").split()) if p and p.returncode == 0 else set())[:5000]


def load(root):
    try:
        with open(_path(root), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("heads"), list):
            return d
    except (OSError, ValueError):
        pass
    return None


def _save(root, d):
    path = _path(root)
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, path)
    except OSError:
        pass


def seed(root):
    """At the kit's first install only (its record of the accepted files is made for the first time): the history
    there is now is trusted. Never later: a list that is missing later is made again with no tips."""
    if load(root) is None:
        _save(root, {"tips": _tips(root), "heads": []})


def trust(root, commits):
    """Note these commits as trusted. Returns False when the list was missing or spoilt (it is made again, empty)."""
    d = load(root)
    found = d is not None
    d = d or {"tips": _tips(root) if BREAK("known_reseed") else [], "heads": []}
    new = [c for c in commits if c and c not in d["heads"] and c not in d.get("tips", [])]
    if new or not found:
        d["heads"] = (d["heads"] + new)[-KEEP:]
        _save(root, d)
    return found


def trusted(root):
    d = load(root) or {}
    return list(d.get("tips") or []) + list(d.get("heads") or [])


def contains(root, head, tips):
    """Is head inside the history of one of these commits?"""
    if not tips:
        return False
    p = _git(root, "rev-list", "-n1", "--stdin", data=("\n".join([head] + ["^" + t for t in tips]) + "\n").encode())
    return bool(p and p.returncode == 0 and not p.stdout.strip())

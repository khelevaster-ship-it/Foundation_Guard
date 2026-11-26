"""FoundationGuard: the push check's switch read where a script can't change all of it (AI-made, Claude, 2026-11-13;
outside review 6, finding 1, Grok).

A script in a step wrote `"parts": {"push": "off"}` into foundationguard.json, and the pre-push hook, which read only
that file, let an untested commit go. Now the hook (and fg/push.py) take the push switch and the list of protected
branches as the strictest of three copies of the settings:
  - the file in the working folder;
  - the copy the check after every step last accepted (kept in git's own object store);
  - the copy on the remote branch being pushed to (`git show <remote commit>:foundationguard.json`), which nothing on
    this computer can fake. A new branch has no remote copy.
So switching the push check off takes effect after one more checked upload (the owner's yes, 13 Nov).
"""
import json, os, subprocess

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
ORDER = {"off": 0, "warn": 1, "on": 2}
NAME = "foundationguard.json"


def _git(root, *a):
    try:
        return subprocess.run(["git", *a], cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _parse(raw):
    try:
        d = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
        return d if isinstance(d, dict) else None
    except ValueError:
        return None


def _accepted(cfg):
    """The settings as the check after every step last accepted them, or None."""
    root = cfg["_root"]
    p = _git(root, "rev-parse", "--absolute-git-dir")
    if not p or p.returncode != 0:
        return None
    try:
        with open(os.path.join(p.stdout.decode("utf-8", "replace").strip(), "foundationguard", "steps", "state.json"), encoding="utf-8") as f:
            entry = (json.load(f).get("files") or {}).get(NAME) or {}
    except (OSError, ValueError, AttributeError):
        return None
    blob = str(entry.get("id") or "")
    if not blob or blob.startswith(("big:", "unreadable")):
        return None
    b = _git(root, "cat-file", "blob", blob)
    return _parse(b.stdout) if b and b.returncode == 0 else None


def _remote(cfg, remote_sha):
    if not remote_sha or set(remote_sha) == {"0"}:
        return None
    p = _git(cfg["_root"], "show", f"{remote_sha}:{NAME}")
    return _parse(p.stdout) if p and p.returncode == 0 else None


def copies(cfg, remote_sha=None):
    """The settings copies to take the strictest of: the working file's (cfg), the accepted one, the remote's."""
    if BREAK("prepush_strictest"):
        return [cfg]
    return [cfg] + [c for c in (_accepted(cfg), _remote(cfg, remote_sha)) if c]


def push_mode(cfg, remote_sha=None):
    """'on', 'warn' or 'off' for the push check: the strictest of the copies (an unknown value counts as 'on')."""
    if os.environ.get("FG_BREAK", "") == "parts":
        return "on"
    modes = []
    for c in copies(cfg, remote_sha):
        v = str((c.get("parts") or {}).get("push", "on") if isinstance(c.get("parts"), dict) else "on").lower()
        modes.append(v if v in ORDER else "on")
    return max(modes, key=ORDER.get)


def protected(cfg, remote_sha=None):
    """The protected branches named in any copy (lower case)."""
    out = {b.lower() for b in cfg.get("protected_branches") or []}
    for c in copies(cfg, remote_sha)[1:]:
        if isinstance(c.get("protected_branches"), list):
            out |= {str(b).lower() for b in c["protected_branches"]}
    return sorted(out)

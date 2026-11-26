"""FoundationGuard: the one store for proof (AI-made, Claude, 2026-11-13; the owner's tool ideas, Fable's plans).

Receipts (fg/receipts.py: which check ran on which exact code, and how it ended) and the owner's OKs (fg/ledger.py: what
the owner said yes to, until when, once) are kept here as books of one line each, never rewritten:

  .git/foundationguard/proof/<book>.jsonl     inside git's own folder, so a commit can't carry it or change it

Every line is stamped with a key kept outside the project (~/.foundationguard/stamp.key, made on first use) and carries
the fingerprint of the line before it. A line typed by hand, or an old line changed, no longer matches, and the
readers treat it as not trusted (CLAIMED ONLY for a receipt; no OK for the ledger).
Limit: a program on the same computer that reads the key can still write a line that looks right. Like the rest of the
kit, this stops a helper's shortcut, not a determined attack; GitHub's lock is the lock.

WORDS is the one word list every proof tool uses. Only PROVEN is green.
"""
import hashlib, hmac, json, os, secrets, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

WORDS = {
    "PROVEN": "passed on exactly the code as it is now",
    "PASSED ON A RETRY": "failed and then passed on the same code: not a pass until it passes every time",
    "PASSED, NOT APPROVED": "passed on exactly this code, but the code holds a change to a safety check the owner hasn't "
                            "said yes to, so the pass may rest on a weaker check",
    "OUT OF DATE": "passed, but the code has changed since",
    "FAILED": "ran and failed on the code as it is now",
    "DID NOT FINISH": "started and never ended (a crash, a power cut, or it was stopped)",
    "RUNNING": "started a short while ago and hasn't ended yet",
    "NEVER RAN": "no record of it running at all",
    "OVERDUE": "it should run every so often, and the last run is older than that",
    "CLAIMED ONLY": "there is a record, but the kit can't trust it (made in a cloud session, by hand, or changed since)",
}
GREEN = ("PROVEN",)


def home(cfg):
    import steps as SP
    return os.path.join(SP._home(cfg), "proof")


def _book(cfg, book):
    return os.path.join(home(cfg), book + ".jsonl")


def _key():
    d = os.path.join(os.path.expanduser("~"), ".foundationguard")
    p = os.path.join(d, "stamp.key")
    try:
        return open(p, "rb").read().strip()
    except OSError:
        os.makedirs(d, exist_ok=True)
        k = secrets.token_hex(32).encode()
        with open(p, "wb") as f:
            f.write(k)
        return k


def _body(rec):
    return json.dumps({k: v for k, v in rec.items() if k not in ("stamp", "_bad")}, sort_keys=True)


def _stamp(rec):
    return hmac.new(_key(), _body(rec).encode(), hashlib.sha256).hexdigest()[:32]


def _fp(line):
    return hashlib.sha256(line.encode()).hexdigest()[:16]


def _lines(cfg, book):
    try:
        return [l for l in open(_book(cfg, book), encoding="utf-8").read().split("\n") if l.strip()]
    except OSError:
        return []


def append(cfg, book, rec):
    """Add one stamped line to a book; returns the record as written."""
    lines = _lines(cfg, book)
    rec = dict(rec, prev=_fp(lines[-1]) if lines else "", at=rec.get("at") or time.time())
    rec["stamp"] = _stamp(rec)
    os.makedirs(home(cfg), exist_ok=True)
    with open(_book(cfg, book), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def read(cfg, book):
    """Every record of a book, oldest first. A record the kit can't trust carries "_bad": why."""
    out, prev = [], ""
    for line in _lines(cfg, book):
        try:
            rec = json.loads(line)
        except ValueError:
            out.append({"_bad": "not a record"}); prev = _fp(line); continue
        if not isinstance(rec, dict):
            rec = {}
        bad = _why_bad(rec, prev)
        if bad:
            rec["_bad"] = bad
        out.append(rec); prev = _fp(line)
    return out


def _why_bad(rec, prev):
    if BREAK("proof_stamp"):
        return ""
    if not hmac.compare_digest(str(rec.get("stamp", "")), _stamp(rec)):
        return "its stamp doesn't match (written by hand or changed)"
    if rec.get("prev", "") != prev:
        return "the line before it was changed or removed"
    return ""


def git(root, *a):
    p = subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 else ""


def code_now(root):
    """(commit, tree, dirty?) for the code as it is now. The tree is git's fingerprint of every file's content, so the
    same files under a new commit (a squash) are the same code."""
    dirty = bool(git(root, "status", "--porcelain", "--untracked-files=no"))
    return git(root, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD^{tree}"), dirty


def work_now(root, skip=".foundationguard"):
    """A fingerprint of the folder's changes that aren't committed: tracked files changed since the commit, and new
    files git doesn't ignore (their names and contents). "" when there are none. Two runs with the same commit and the
    same work_now ran on the same files (round 9, Grok: a source file changed after the pass still showed PROVEN)."""
    if BREAK("proof_work"):
        return ""
    ex = f":(exclude){skip}"
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--", ".", ex], cwd=root, capture_output=True).stdout
    new = git(root, "ls-files", "-o", "--exclude-standard", "--", ".", ex)
    if not diff and not new:
        return ""
    return hashlib.sha256(diff + new.encode() + _ids(root, new).encode()).hexdigest()[:20]


def _ids(root, names):
    """git's content fingerprint of each named file, one per line."""
    p = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=root, input=names + "\n", capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout


def where():
    """Where this runs: 'ci', 'cloud' (a Claude Code cloud session) or 'pc'. A cloud session is never CI, whatever else
    is set (round 9, ChatGPT: CI=1 in a cloud session made its receipts trusted). These are the session's own words, so
    the guard also refuses a kit command that sets or clears them (fg/gitsettings.py); the store and its key stay on
    each computer, so another computer's receipts never reach this one's."""
    ci = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")
    if ci and BREAK("proof_ci_first"):
        return "ci"
    if os.environ.get("CLAUDE_CODE_REMOTE") and not BREAK("proof_where"):
        return "cloud"
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return "ci"
    return "pc"

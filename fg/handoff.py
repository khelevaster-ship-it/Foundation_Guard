"""FoundationGuard handoff checker: is the note true? (AI-made, Claude, 2026-11-13; the owner's tool ideas, Fable's plan)

Sessions rotate and their notes are trusted anyway, even when a note is out of date or wrong. A handoff note now carries
a facts block, and the kit checks each fact against the project with plain rules (no AI reads the note's free text):

  <!-- facts -->
  commit 4f2a9c1                  this commit exists
  branch feature/x at 4f2a9c1     the branch's tip is this commit (its copy on the remote as last fetched, else local)
  pushed 4f2a9c1                  a branch on the remote holds this commit
  file fg/handoff.py              this file exists
  no file old/thing.py            this file doesn't exist
  contains docs/GUIDE.md: Alarm sorter     the file has this text
  check gate PROVEN               python fg/receipts.py gives this check this word now
  guard F329 BITES                python fg/bite.py gives this guard this word now
  <!-- /facts -->

Each fact gets one word:
  TRUE          it holds now
  OUT OF DATE   it held, but the code has moved on since (the branch went past that commit)
  WRONG         it doesn't hold
  NOT CHECKED   the kit can't read this line (it says so; nothing is guessed)
Everything outside the block is not checked, and the count says so.

  python fg/handoff.py NOTE.md [...]     check the notes' facts (exit 1 when one is WRONG)
  python fg/handoff.py --write           a facts block for the code as it is now, to paste into a note
This only informs.
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import proofstore as PS

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
WORDS = {"TRUE": "it holds now", "OUT OF DATE": "it held, but the code has moved on since",
         "WRONG": "it doesn't hold", "NOT CHECKED": "the kit can't read this line"}
BLOCK = re.compile(r"<!--\s*facts\s*-->(.*?)<!--\s*/facts\s*-->", re.S | re.I)


def facts(text):
    """(fact lines, count of other non-empty lines) from a note."""
    lines = []
    for m in BLOCK.finditer(text):
        lines += [ln.strip() for ln in m.group(1).splitlines() if ln.strip() and not ln.strip().startswith("#")]
    rest = BLOCK.sub("", text)
    return lines, sum(1 for ln in rest.splitlines() if ln.strip())


def _sha(root, ref):
    return PS.git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")


def _commit(root, sha):
    full = _sha(root, sha)
    return ("TRUE", full[:12] or sha) if full or BREAK("handoff_commit") else ("WRONG", f"no commit {sha} in this project")


def _branch(root, name, sha):
    full = _sha(root, sha)
    tip = _sha(root, "origin/" + name) or _sha(root, name)        # the copy on the remote first, as last fetched
    if not tip:
        return "WRONG", f"no branch {name}"
    if not full:
        return "WRONG", f"no commit {sha} in this project"
    if tip == full:
        return "TRUE", f"{name} is at {full[:12]}"
    if _ancestor(root, full, tip) and not BREAK("handoff_ancestor"):
        n = PS.git(root, "rev-list", "--count", f"{full}..{tip}")
        return "OUT OF DATE", f"{name} has moved {n} commit(s) past {sha}, to {tip[:12]}"
    return "WRONG", f"{name} is at {tip[:12]}, which doesn't come after {sha}"


def _ancestor(root, a, b):
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=root, capture_output=True).returncode == 0


def _pushed(root, sha):
    full = _sha(root, sha)
    if not full:
        return "WRONG", f"no commit {sha} in this project"
    on = PS.git(root, "branch", "-r", "--contains", full)
    return ("TRUE", "on " + on.split()[0]) if on else ("WRONG", f"{sha} is on no branch of the remote (as last fetched)")


def _file(root, path, want):
    there = os.path.exists(os.path.join(root, path))
    if there == want:
        return "TRUE", path + (" exists" if want else " doesn't exist")
    return "WRONG", path + (" doesn't exist" if want else " exists")


def _contains(root, path, text):
    p = os.path.join(root, path)
    if not os.path.isfile(p):
        return "WRONG", f"{path} doesn't exist"
    has = text in open(p, encoding="utf-8", errors="replace").read()
    return ("TRUE", f"{path} has it") if has else ("WRONG", f"{path} doesn't have \"{text}\"")


def _word(cfg, kind, name, want):
    import receipts as RC, bite as BT
    rows = RC.status(cfg) if kind == "check" else BT.status(cfg)
    now = {r[0]: r[1] for r in rows}.get(name)
    if now is None:
        return "WRONG", f"no {kind} {name}"
    return ("TRUE", f"{name} is {now}") if now == want.upper() else ("WRONG", f"{name} is {now}, not {want.upper()}")


RULES = [
    (re.compile(r"commit\s+([0-9a-f]{7,40})$", re.I), lambda cfg, m: _commit(cfg["_root"], m[1])),
    (re.compile(r"branch\s+(\S+)\s+at\s+([0-9a-f]{7,40})$", re.I), lambda cfg, m: _branch(cfg["_root"], m[1], m[2])),
    (re.compile(r"pushed\s+([0-9a-f]{7,40})$", re.I), lambda cfg, m: _pushed(cfg["_root"], m[1])),
    (re.compile(r"no file\s+(\S+)$", re.I), lambda cfg, m: _file(cfg["_root"], m[1], False)),
    (re.compile(r"file\s+(\S+)$", re.I), lambda cfg, m: _file(cfg["_root"], m[1], True)),
    (re.compile(r"contains\s+([^:]+):\s*(.+)$", re.I), lambda cfg, m: _contains(cfg["_root"], m[1].strip(), m[2].strip())),
    (re.compile(r"(check|guard)\s+(\S+)\s+(.+)$", re.I), lambda cfg, m: _word(cfg, m[1].lower(), m[2], m[3].strip())),
]


def judge(cfg, line):
    """(word, plain words) for one fact line."""
    for rx, rule in RULES:
        m = rx.match(line)
        if m:
            return rule(cfg, m)
    return "NOT CHECKED", "the kit can't read this line"


def check(cfg, paths):
    rows, unread = [], 0
    for p in paths:
        lines, rest = facts(open(p, encoding="utf-8", errors="replace").read())
        unread += rest
        rows += [(p, ln) + judge(cfg, ln) for ln in lines]
    return rows, unread


def write(cfg):
    root = cfg["_root"]
    head, _, dirty = PS.code_now(root)
    branch = PS.git(root, "rev-parse", "--abbrev-ref", "HEAD")
    out = ["<!-- facts -->", f"commit {head[:12]}"]
    if branch and branch != "HEAD":
        out.append(f"branch {branch} at {head[:12]}")
    if PS.git(root, "branch", "-r", "--contains", head):
        out.append(f"pushed {head[:12]}")
    import receipts as RC
    out += [f"check {c} {w}" for c, w, _ in RC.status(cfg)]
    out.append("<!-- /facts -->")
    print("\n".join(out) + ("\n(the code has changes that aren't committed: commit them first)" if dirty else ""))
    return 0


def main(argv):
    cfg = C.load()
    if "--write" in argv:
        return write(cfg)
    paths = [a for a in argv if not a.startswith("-")]
    if not paths:
        print("Usage: python fg/handoff.py NOTE.md [...]   or   python fg/handoff.py --write"); return 2
    rows, unread = check(cfg, paths)
    for p, ln, w, why in rows:
        print(f"  {w:<11} {ln}: {why}")
    counts = {}
    for r in rows:
        counts[r[2]] = counts.get(r[2], 0) + 1
    said = ", ".join(f"{n} {w}" for w, n in sorted(counts.items())) or "no facts block"
    tail = "" if BREAK("handoff_unchecked") else f" {unread} other line(s) of the note are not checked."
    print(f"FG-HANDOFF: {said}.{tail}")
    return 1 if counts.get("WRONG") or not rows else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

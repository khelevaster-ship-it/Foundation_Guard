"""FoundationGuard plain-words merge summary (AI-made, Claude, 2026-11-08).
For a pull request or an approval request: which approved behaviours the change touches (APPROVED.md's optional 6th
column "Paths" maps each behaviour to the files it lives in), which guard files changed, and what to play before saying yes.
  python fg/summary.py [BASE]                 BASE defaults to origin/main; prints the note between check markers
  python fg/summary.py --check BODY [BASE]    fails unless BODY (a pull-request description saved to a file) holds this
                                              script's note for the current commit, word for word
The note must come from the real file changes, never from an agent's own words: --check runs in CI on every pull request
(docs/GITHUB_PROTECTION.md), so a reworded, trimmed or stale note blocks the merge. Text outside the markers is allowed
and is shown as the author's own words."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P
import approved as A


def _changed(root, base):
    r = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [f for f in r.stdout.split("\n") if f]


def _touched(rows, changed):
    """Approved rows whose mapped files this change touches."""
    if os.environ.get("FG_BREAK") == "summary":
        return []
    return [r for r in rows if r["paths"] and any(P.matches(f, r["paths"]) for f in changed)]


def _behaviour_lines(rows, changed):
    out = [f"- {r['id']}: {r['behaviour']} (check: {r['check']})" for r in _touched(rows, changed)] or ["- none of the mapped ones"]
    unmapped = [r["id"] for r in rows if not r["paths"]]
    if unmapped:
        out.append(f"- plus {len(unmapped)} approved behaviour(s) with no file map, which can't be ruled out: " + ", ".join(unmapped))
    return out


def summary(cfg, base="origin/main"):
    changed = _changed(cfg["_root"], base)
    guards = [f for f in changed if P.matches(f, C.guard_globs(cfg))]
    out = [f"## What this change touches ({len(changed)} files changed since {base})", "",
           "**Approved behaviours it touches** (play these before approving):"]
    out += _behaviour_lines(A.rows(cfg), changed)
    out += ["", "**Guard files changed** (checks, approvals, baselines, hooks: each needs its own reason):"]
    out += [f"- {g}" for g in guards] or ["- none"]
    return "\n".join(out)

START, END = "<!-- foundationguard:summary", "<!-- /foundationguard:summary -->"


def note(cfg, base):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cfg["_root"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    return f"{START} head={head} -->\n" + summary(cfg, base) + f"\n{END}"


def check(cfg, body, base):
    """(ok, message): the body must contain exactly the note this script makes for HEAD."""
    want = note(cfg, base)
    if os.environ.get("FG_BREAK") == "summary_check":
        return True, "SUMMARY CHECK: skipped (broken on purpose)"
    i = body.find(START)
    if i < 0:
        return False, "SUMMARY CHECK FAILED: the pull request has no FoundationGuard note. Paste the output of fg/summary.py."
    j = body.find(END, i)
    got = body[i:j + len(END)] if j >= 0 else body[i:]
    norm = lambda t: "\n".join(l.rstrip() for l in t.replace("\r\n", "\n").strip().split("\n"))
    if norm(got) == norm(want):
        return True, "SUMMARY CHECK: the note matches the real file changes."
    if got.split("\n", 1)[0].strip() != want.split("\n", 1)[0].strip():
        return False, "SUMMARY CHECK FAILED: the note was made for a different commit. Run fg/summary.py again and paste it."
    return False, "SUMMARY CHECK FAILED: the note was changed by hand. It must be fg/summary.py's output, word for word.\nExpected:\n" + want


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--check":
        ok, msg = check(C.load(), open(a[1], encoding="utf-8").read(), a[2] if len(a) > 2 else "origin/main")
        print(msg); sys.exit(0 if ok else 1)
    print(note(C.load(), a[0] if a else "origin/main"))

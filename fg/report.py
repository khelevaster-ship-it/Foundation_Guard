"""FoundationGuard guard-change report (AI-made, Claude, 2026-11-08).
Lists every commit that touched a guard file (approvals, sign-offs, checks and baselines in guard_paths, hooks, the kit,
its config and baselines), so the owner sees any softening, even one made with his OK.
  python fg/report.py                 since the last report (remembered in the state dir), else the last 7 days
  python fg/report.py --since REF     since a commit, branch or date ("2026-11-01")
  python fg/report.py --mark          also remember this point as "last report"
Exit 0 always; it informs, it doesn't block."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def _range(cfg, root, since):
    mark = os.path.join(root, cfg["state_dir"], "last_report")
    if not since and os.path.exists(mark):
        since = open(mark).read().strip()
    is_ref = bool(since) and subprocess.run(["git", "rev-parse", "--verify", "-q", since + "^{commit}"], cwd=root, capture_output=True).returncode == 0
    if is_ref:
        return since, [f"{since}..HEAD"]
    return since, ([f"--since={since}"] if since else ["--since=7.days"])


def _guard_commits(log, globs):
    """[(hash, date, author, subject, [guard files])] for the commits in a --name-only log that touched guard files."""
    rows, cur = [], None
    keep = os.environ.get("FG_BREAK") != "report"
    for line in log.split("\n"):
        f = line.strip()
        if line.startswith("@@"):
            cur = line[2:].split("|", 3); cur.append([]); rows.append(cur)
        elif f and cur is not None and keep and P.matches(f, globs):
            cur[4].append(f)
    return [r for r in rows if r[4]]


def report(cfg, since=None):
    root = cfg["_root"]
    since, rng = _range(cfg, root, since)
    log = git("log", *rng, "--name-only", "--format=@@%h|%ad|%an|%s", "--date=short", cwd=root)
    hits = _guard_commits(log, C.guard_globs(cfg))
    out = [f"GUARD CHANGES since {since or '7 days ago'}: {len(hits)} commit(s) touched guard files."]
    for h, d, a, s, files in hits:
        out.append(f"  {d} {h} {a}: {s}")
        out += [f"      {f}" for f in files]
    return "\n".join(out)

def main(argv):
    cfg = C.load(); since = argv[argv.index("--since") + 1] if "--since" in argv else None
    print(report(cfg, since))
    if "--mark" in argv:
        sd = os.path.join(cfg["_root"], cfg["state_dir"]); os.makedirs(sd, exist_ok=True)
        open(os.path.join(sd, "last_report"), "w").write(git("rev-parse", "HEAD", cwd=cfg["_root"]).strip())
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

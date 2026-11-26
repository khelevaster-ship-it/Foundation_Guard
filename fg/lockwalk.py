"""FoundationGuard: the GitHub lock, one step at a time, each checked before the next (AI-made, Claude, 2026-11-17;
Plan 2 part 6, merge C).

  python fg/setup.py --lock     (or python fg/lockwalk.py)

Each run checks every step, read-only, shows which are done, and gives the owner the first one that isn't, in plain
words. The helper reads it out, waits while the owner clicks, then runs it again; it never changes GitHub settings
itself. A step that isn't done keeps fg/lock.py at NOT ON.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


class Ctx:
    def __init__(self, cfg):
        import lock as LK, logins as LG, codeowners as CO
        self.cfg, self.root = cfg, cfg["_root"]
        self.repo, self.gh = LK.github_repo(self.root), LK.find_gh(cfg)
        t = CO.team(cfg) or {"owners": [cfg.get("owner_github")] if cfg.get("owner_github") else [], "bots": []}
        self.owners = {o.lstrip("@").lower() for o in t["owners"] if o}
        self.bots = [b.lstrip("@") for b in t.get("bots") or []]
        self.found = LG.found(self.root, self.gh) if self.gh else {"gh": [], "git": [], "vars": []}
        self.here = [n.lower() for n in self.found["gh"]]
        self.main = (cfg.get("protected_branches") or ["main"])[0]

    def api(self, path):
        import lock as LK
        return LK._gh_json(self.root, self.gh, path)


def _owner_named(c):
    return bool(c.owners), "the owner's GitHub name is in foundationguard.json (owner_github, or team.owners)"


def _helper_account(c):
    mine = [n for n in c.here if n not in c.owners]
    return bool(mine), ("gh on this computer is signed in as " + ", ".join(mine)) if mine else \
        "gh on this computer isn't signed in as an account other than the owner's"


def _invited(c):
    me = next((n for n in c.here if n not in c.owners), None)
    if not (me and c.repo):
        return False, "no helpers' account to look up yet"
    j, why = c.api(f"repos/{c.repo}/collaborators/{me}/permission")
    perm = (j or {}).get("permission") if isinstance(j, dict) else None
    if perm == "admin":
        return False, f"{me} is an admin of the project: it must have Write, not Admin"
    return perm in ("write", "maintain"), (f"{me} has {perm} on the project" if perm else f"can't see {me} on the project ({why})")


def _owner_out(c):
    import logins as LG
    left = [n for n in LG.names(c.found) if n in c.owners]
    return not left, ("no owner's login is on this computer" if not left else
                      "the owner's own login is still on this computer (" + ", ".join(left) + ")")


def _ruleset(c):
    import lock as LK
    says, why = LK.github_says(c.root, c.repo, c.main, c.cfg) if c.repo else (None, "no GitHub project")
    return says is True, ("GitHub shows the lock on " + c.main) if says else (why or f"GitHub shows no lock on {c.main}")


def _workflow(c):
    j, why = c.api(f"repos/{c.repo}/contents/.github/workflows/foundationguard.yml?ref={c.main}") if c.repo else (None, "")
    return isinstance(j, dict) and bool(j.get("sha")), "the kit's workflow is on " + c.main if isinstance(j, dict) and \
        j.get("sha") else "the kit's workflow isn't on " + c.main + " yet"


def _app(c):
    import lock as LK
    if not (c.cfg.get("team") or c.cfg.get("kit_app_id")):
        return True, "one owner: the kit's own app is optional"
    gaps, why = LK.team_gaps(c.root, c.repo, c.main, c.cfg, c.gh)
    return gaps == [], "; ".join(gaps or []) or why or "the note check comes from the kit's own app, key on main only"


def _drilled(c):
    import drill as DR
    g = DR.gap(dict(c.cfg, team=True))
    return g is None, g or "a drill passed in the last 30 days"


STEPS = [
    ("Name the owner", _owner_named,
     "Tell the helper your GitHub name. It writes owner_github (or team.owners) in foundationguard.json; the kit's box asks you."),
    ("A second account for the helpers", _helper_account,
     "Make a second GitHub account for the AI helpers (for example yourgame-bot). On this computer, in the owner window, "
     "sign gh in as that account: gh auth login (you type this yourself; the kit stops helpers changing logins)."),
    ("Invite it with Write", _invited,
     "Project on GitHub > Settings > Collaborators > Add people > the helpers' account, role Write (not Admin). Accept "
     "the invite while signed in as that account."),
    ("Your own login off this computer", _owner_out,
     "Sign your own account out of this computer: gh auth logout --user <you>, and remove your name from git's stored "
     "logins (Windows: Credential Manager > github.com). On your phone keep GitHub signed in as you: that is where you approve."),
    ("The rules on main", _ruleset,
     "Project > Settings > Rules > Rulesets > New > Import a ruleset, and pick docs/github-ruleset.json from the kit "
     "(or tick by hand: pull request, Code Owners review, approval of the most recent push, stale approvals dismissed, "
     "no force push, no deletion, no bypass). Save."),
    ("The kit's workflow on main", _workflow,
     "The helper adds .github/workflows/foundationguard.yml (from docs/foundationguard-team.yml) in a pull request; you "
     "approve and merge it on GitHub."),
    ("The kit's own app (teams)", _app,
     "Run python fg/app.py (add --public if the helpers' account makes it) and follow its four clicks; tell the helper "
     "the app's number."),
    ("The drill", _drilled,
     "The helper runs python fg/lock.py --drill. Every try to get round the lock must be refused."),
]


def walk(cfg):
    """[(name, done, detail, how)] for every step, checked in order; checks after the first open step still run."""
    c = Ctx(cfg)
    out = []
    for name, check, how in STEPS:
        try:
            done, detail = check(c)
        except Exception as e:                              # noqa: BLE001
            done, detail = False, f"couldn't check ({type(e).__name__})"
        if BREAK("lock_walk_checks"):
            done = True
        out.append((name, bool(done), detail, how))
    return out


def main(argv):
    import config as C
    cfg = C.load()
    steps = walk(cfg)
    first = next((i for i, s in enumerate(steps) if not s[1]), None)
    for i, (name, done, detail, _) in enumerate(steps, 1):
        print(f"  {'done' if done else 'NEXT' if i - 1 == first else 'to do'}  {i}. {name}: {detail}")
    if first is None:
        print("FoundationGuard: every step of the GitHub lock is done. python fg/lock.py shows it.")
        return 0
    print(f"FoundationGuard: step {first + 1} of {len(steps)} for the owner, then run this again:\n  " + steps[first][3])
    return 1


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

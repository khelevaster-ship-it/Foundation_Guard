"""Write .github/CODEOWNERS so GitHub itself decides who must approve what (AI-made, Claude, 2026-11-08; team mode
2026-11-15, the team addendum to Plan 2, section 2.2).

  python fg/codeowners.py            write .github/CODEOWNERS from foundationguard.json
  python fg/codeowners.py --check    say whether the file on disk matches what the settings say (exit 1 if not)

One owner (owner_github, e.g. "@your-name"): every file needs the owner's review.

A team ("team" in foundationguard.json):
  "team": {"owners": ["@kim"],                         may approve everything; only they approve the kit's own files
           "check_owners": {"tests/save/**": ["@alex"]},  may approve changes to those test folders, weakenings too
           "reviewers": ["@sam"],                       may approve changes outside tests and outside the kit's own files
           "bots": ["@helper-bot"]}                     helpers' accounts: never written in, so their Approve never counts
A test nobody is named for belongs to the owners. An owner is on every line as the fallback. GitHub uses the LAST line
that matches a file, so the kit's own files come last and always need an owner.

Then on GitHub (private repos need a paid plan): a ruleset on main requiring a pull request, a code-owner review,
approval of the most recent push, stale approvals dismissed, no bypass (python fg/lock.py --steps)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
HEAD = "# Written by FoundationGuard (fg/codeowners.py) from foundationguard.json. Change the settings, not this file."
# Where tests live, in CODEOWNERS' own pattern language (a pattern without a leading / matches at any depth).
TEST_PATTERNS = ["test_*", "*_test.*", "*.spec.*", "*Test.*", "*Tests.*", "tests/", "test/", "spec/"]


class TeamError(ValueError):
    pass


def _pattern(g):
    """A kit glob as a CODEOWNERS line pattern, anchored at the project's top."""
    g = g.strip("/")
    return "/" + (g[:-2] if g.endswith("/**") else g.replace("**", "*"))


def _names(v, what):
    v = [v] if isinstance(v, str) else list(v or [])
    for n in v:
        if not (isinstance(n, str) and n.startswith("@") and len(n) > 1 and " " not in n):
            raise TeamError(f"{what}: {n!r} is not a GitHub name (write it as \"@name\" or \"@org/team\")")
    return v


def team(cfg):
    """The team block, checked: {"owners", "check_owners", "reviewers", "bots"}, or None for one owner."""
    t = cfg.get("team")
    if not t:
        return None
    if not isinstance(t, dict):
        raise TeamError("team in foundationguard.json must be a block like {\"owners\": [\"@you\"]}")
    out = {"owners": _names(t.get("owners") or cfg.get("owner_github"), "owners"),
           "reviewers": _names(t.get("reviewers"), "reviewers"), "bots": _names(t.get("bots"), "bots"),
           "check_owners": {}}
    if not out["owners"]:
        raise TeamError("the team needs at least one owner (team.owners)")
    for g, names in (t.get("check_owners") or {}).items():
        out["check_owners"][g] = _names(names, f"check_owners[{g}]")
    bots = {b.lower() for b in out["bots"]}
    named = out["owners"] + out["reviewers"] + [n for v in out["check_owners"].values() for n in v]
    if not BREAK("team_bot_not_owner"):
        hit = sorted({n for n in named if n.lower() in bots})
        if hit:
            raise TeamError(f"{', '.join(hit)} is a helper's account (team.bots), so it can never approve: take it out "
                            "of owners, reviewers and check_owners")
    return out


def _join(*groups):
    seen, out = set(), []
    for g in groups:
        for n in g:
            if n.lower() not in seen:
                seen.add(n.lower()); out.append(n)
    return " ".join(out)


def lines(cfg):
    """The CODEOWNERS lines the settings call for."""
    t = team(cfg)
    if t is None:
        owner = cfg.get("owner_github")
        if not owner:
            raise TeamError("set owner_github in foundationguard.json first (e.g. \"@your-name\")")
        return [HEAD, f"* {owner}"] + [f"{_pattern(g)} {owner}" for g in C.guard_globs(cfg)]
    owners = t["owners"]
    out = [HEAD, "", "# Everything: a reviewer or an owner.", f"* {_join(t['reviewers'], owners)}"]
    mine = set(cfg.get("guard_paths") or []) | set(cfg.get("guard_decisions") or {})
    protect = [g for g in C.guard_globs(cfg) if g in mine]
    out += ["", "# Files the owners protect (guard_paths): owners, unless a check owner is named for them below."]
    out += [f"{_pattern(g)} {_join(owners)}" for g in protect]
    own_files = ["", "# The kit, its settings, its records and the AI tools' hook settings: owners only, whatever is above."]
    own_files += [f"{_pattern(g)} {_join(owners)}" for g in C.guard_globs(cfg) if g not in mine]
    tests = ["", "# Tests nobody is named for: owners only."]
    tests += [f"{p} {_join(owners)}" for p in TEST_PATTERNS]
    tests += ["", "# Tests a check owner looks after (an owner is the fallback)."]
    tests += [f"{_pattern(g)} {_join(names, owners)}" for g, names in t["check_owners"].items()]
    if BREAK("team_tests_owners"):
        tests = []
    return out + (own_files + tests if BREAK("team_owner_files_last") else tests + own_files)


def path(cfg):
    return os.path.join(cfg["_root"], ".github", "CODEOWNERS")


def text(cfg):
    return "\n".join(lines(cfg)) + "\n"


def matches(cfg, have):
    """Does a CODEOWNERS text (main's copy, read by the GitHub check) say what the settings say?"""
    norm = lambda s: [l.strip() for l in (s or "").splitlines() if l.strip() and not l.strip().startswith("#")]
    return norm(have) == norm(text(cfg))


def main(argv):
    cfg = C.load()
    try:
        want = text(cfg)
    except TeamError as e:
        print("FG-CODEOWNERS: " + str(e)); return 1
    p = path(cfg)
    if "--check" in argv:
        have = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        ok = matches(cfg, have)
        print("FG-CODEOWNERS: " + ("matches the settings." if ok else
              "doesn't match the settings in foundationguard.json (python fg/codeowners.py writes it)."))
        return 0 if ok else 1
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(want)
    print("wrote", p)
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

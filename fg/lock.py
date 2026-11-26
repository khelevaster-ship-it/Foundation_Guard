"""FoundationGuard GitHub lock reminder (AI-made, Claude, 2026-11-09).

Everything on the owner's computer can be switched off by whoever works there, an AI helper included. The weaker-AI test
(9 Nov) showed it: a helper recorded the owner's OK itself, and only GitHub's own lock refused the upload. So until the
project is locked on GitHub, every push summary carries a "FOR YOU" card that says so and tells the helper to walk the
owner through the steps, one click at a time. The card goes away when:
  - GitHub itself shows the lock (checked read-only with the `gh` tool when it is signed in; gh is looked for on the
    PATH, in its usual install folders, and at "gh_path" in foundationguard.json), or
  - the owner did the steps and said so in their own words:  python fg/lock.py --confirm --words "I locked main on GitHub"
    (that changes foundationguard.json, a guard file, so the owner is asked, and the next summary shows it as a decision).
If GitHub can be checked and shows the lock is off again, the card comes back whatever was confirmed. When GitHub can't
be asked (no gh, not signed in, no answer), the status is "could not check", with the reason, and never "not locked"
(11 Nov: gh was installed on the game's Windows computer but not on the PATH the kit saw).

  python fg/lock.py            say where the lock stands
  python fg/lock.py --steps    the steps, in plain words, for the helper to walk the owner through
  python fg/lock.py --drill    prove the lock by trying to break it as the helpers' account (fg/drill.py)
"""
import json, os, re, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

STEPS = """Locking the project on GitHub: the helper reads one step at a time, waits for the owner to do it, then goes on.
The owner clicks; the helper never changes GitHub settings itself. About 15 minutes.

1. Make a second GitHub account for the AI helpers (for example yourgame-bot) and invite it to the project:
   project page > Settings > Collaborators > Add people. Accept the invite while signed in as the bot.
2. Tell the helper your own GitHub name. It sets owner_github in foundationguard.json and runs python fg/codeowners.py,
   which names you as the reviewer of every guard file, then uploads that.
3. Lock main: project page > Settings > Branches (or Rules > Rulesets) > add a rule for main. Tick: require a pull
   request; require review from Code Owners; require status checks (pick "FoundationGuard note" once it has run);
   block force pushes; do not allow deletions; "Do not allow bypassing the above settings" (include administrators).
   Leave the bypass list empty. Save. (Private projects need GitHub Pro or a paid organisation plan for this.)
   With a team: make the kit's own GitHub App (python fg/app.py walks you through it, one click), and in the rule
   require "FoundationGuard note" from that app (not "any source"). Put its key in an environment named fg-kit with
   Deployment branches set to main only. Tell the helper the app's number: it sets kit_app_id.
4. Give the helpers a limited key, made while signed in as the bot: Settings > Developer settings > Personal access
   tokens > Fine-grained tokens > Generate. Only this project. Contents: read and write. Pull requests: read and write.
   Everything else: No access. The helper signs the build computer in with it. Your own login stays off that folder.
5. Tell the helper in your own words that it's done, for example "I locked main on GitHub today". The helper records it:
   python fg/lock.py --confirm --words "<your words>"
Full guide: docs/GITHUB_PROTECTION.md"""


def _git(root, *a):
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()


def github_repo(root):
    """'owner/name' when origin is on GitHub, else None."""
    url = _git(root, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


# 11 Nov (the build thread, Windows): gh was installed but not on the PATH the kit saw, and every summary said "isn't
# locked" about a project that was. So gh is looked for in its usual install places too, and when GitHub can't be asked
# the status is "could not check", with the reason, never "not locked".
GH_DIRS = [r"%ProgramFiles%\GitHub CLI", r"%ProgramFiles(x86)%\GitHub CLI", r"%LOCALAPPDATA%\Programs\GitHub CLI",
           r"%LOCALAPPDATA%\Microsoft\WinGet\Links", r"%USERPROFILE%\scoop\shims", r"%ProgramData%\chocolatey\bin",
           "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/home/linuxbrew/.linuxbrew/bin", "~/.local/bin", "/snap/bin"]
GH_NAMES = ("gh.exe", "gh.cmd", "gh.bat") if os.name == "nt" else ("gh",)


def find_gh(cfg=None):
    """The gh program: the path the owner gave ("gh_path"), the PATH, then gh's usual install places. None if not found."""
    named = (cfg or {}).get("gh_path")
    if named and os.path.isfile(named):
        return named
    on_path = shutil.which("gh")
    if on_path or BREAK("lock_gh_places"):
        return on_path
    for d in GH_DIRS:
        d = os.path.expanduser(os.path.expandvars(d))
        for n in ([] if "%" in d else GH_NAMES):
            if os.path.isfile(os.path.join(d, n)):
                return os.path.join(d, n)
    return None


NO_GH = ("gh, GitHub's own command tool, isn't on this computer (looked on the PATH and in its usual install folders), "
         "so the kit could not ask GitHub")


def _gh_json(root, gh, path):
    """(answer, None) or (None, why it could not be read). 'Branch not protected' is an answer: no classic lock."""
    try:
        p = subprocess.run([gh, "api", "-X", "GET", path], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"gh could not be run ({type(e).__name__})"
    if p.returncode != 0:
        err = (p.stderr or "") + (p.stdout or "")
        if "not protected" in err.lower():
            return {}, None
        if "auth login" in err or "not logged" in err.lower() or "401" in err:
            return None, "gh isn't signed in to GitHub on this computer (gh auth login)"
        if "upgrade to github pro" in err.lower() or "upgrade your plan" in err.lower():
            return None, PLAN_CANT
        if "404" in err or "Not Found" in err or "403" in err:
            return None, "the GitHub account gh is signed in with can't read this project's settings"
        return None, "GitHub didn't answer (" + (err.strip().splitlines() or ["no reason given"])[-1][:80] + ")"
    try:
        return json.loads(p.stdout), None
    except ValueError:
        return None, "GitHub's answer could not be read"


def _classic_ok(j):
    pr = (j or {}).get("required_pull_request_reviews") or {}
    return bool(pr.get("require_code_owner_reviews")) and bool(((j or {}).get("enforce_admins") or {}).get("enabled")) \
        and not ((j or {}).get("allow_force_pushes") or {}).get("enabled")


def _ruleset_ok(rules):
    kinds = {r.get("type"): r for r in (rules or []) if isinstance(r, dict)}
    pr = (kinds.get("pull_request") or {}).get("parameters") or {}
    return bool(pr.get("require_code_owner_review")) and "non_fast_forward" in kinds and "deletion" in kinds


def github_says(root, repo, branch, cfg=None):
    """(True, '') locked; (False, '') GitHub answered: not locked; (None, why) the kit couldn't ask."""
    if BREAK("lock_gh") or not repo:
        return None, "no GitHub project to ask"
    gh = find_gh(cfg)
    if not gh:
        return None, NO_GH
    j, why = _gh_json(root, gh, f"repos/{repo}/branches/{branch}/protection")
    if j and _classic_ok(j):
        return True, ""
    rules, why2 = _gh_json(root, gh, f"repos/{repo}/rules/branches/{branch}")
    if isinstance(rules, list) and _ruleset_ok(rules):
        return True, ""
    if j is not None and isinstance(rules, list):
        return False, ""
    if j is None and isinstance(rules, list):              # a helper's limited key can't read the classic lock's details,
        b, _ = _gh_json(root, gh, f"repos/{repo}/branches/{branch}")   # but anyone can see whether the branch has one
        if isinstance(b, dict) and b.get("protected") is False:
            return False, ""
        if isinstance(b, dict) and b.get("protected"):
            why = f"GitHub shows {branch} has a lock, but the account gh is signed in with can't read which rules it has"
    return None, why or why2


# Spike S3 (15 Nov): a workflow on a change's own branch posted a green check named "FoundationGuard note", and GitHub
# took it. Only the kit's own GitHub App, its key in an environment only main may use (S7), makes a check a branch can't
# fake. So with a team (or "kit_app_id" set) the lock is ON only when GitHub requires the note from that app and the
# key's environment lets only main deploy.
NOTE_CHECK = "FoundationGuard note"
PLAN_CANT = ("CAN'T BE ON with this GitHub plan: GitHub won't hold a change for a review on this private project, so anyone "
             "who can upload can merge. The kit still posts its count on every pull request: an alarm and a record, not a "
             "lock. To turn it on: GitHub Pro (a personal project), GitHub Team (an organisation), or make it public")


def role(cfg, login):
    """What this GitHub login is in the team (team plan 2.2), in plain words."""
    if BREAK("lock_role"):
        return "contributor"
    import codeowners as CO
    t = CO.team(cfg) or {"owners": [cfg.get("owner_github")] if cfg.get("owner_github") else [], "reviewers": [],
                         "bots": [], "check_owners": {}}
    me = ("@" + login.lstrip("@")).lower() if login else ""
    low = lambda xs: [x.lower() for x in xs if x]
    if not me:
        return "unknown (the kit can't tell who is signed in here)"
    if me in low(t["bots"]):
        return "a helper's account: it can upload, and its Approve never counts"
    if me in low(t["owners"]):
        return "owner: approves everything, and alone approves the kit, its settings, the approved list and the team list"
    mine = [g for g, ns in t["check_owners"].items() if me in low(ns)]
    if mine:
        return "check owner: looks after " + ", ".join(mine)
    if me in low(t["reviewers"]):
        return "reviewer: approves changes outside tests and the kit's own files"
    return "contributor: uploads and opens pull requests; approves nothing"


def plan_words(root, repo, gh):
    """(CAN'T BE ON words or None, notes) from what GitHub says about the project and its owner's plan."""
    if BREAK("lock_plan_cant"):
        return None, []
    r, why = _gh_json(root, gh, f"repos/{repo}")
    if not isinstance(r, dict) or not r.get("private"):
        return None, []
    owner = (r.get("owner") or {})
    if owner.get("type") == "Organization":
        o, _ = _gh_json(root, gh, f"orgs/{owner.get('login')}")
        if isinstance(o, dict) and ((o.get("plan") or {}).get("name") or "").lower() == "free":
            return PLAN_CANT, []
        return None, []
    if BREAK("lock_plan_team"):
        return None, []
    return None, ["a personal project has no read-only role: everyone invited can upload, and outside helpers need an "
                  "organisation to work from forks"]


def login_gaps(root, repo, cfg, gh):
    """(gaps, notes): an owner's own login on this computer, a login here that is an admin, and what this login can do."""
    import logins as LG
    found = LG.found(root, gh)
    import codeowners as CO
    t = CO.team(cfg) or {"owners": [cfg.get("owner_github")] if cfg.get("owner_github") else []}
    owners = {o.lstrip("@").lower() for o in t["owners"] if o}
    here = LG.names(found)
    gaps = [f"the owner's own GitHub login ({n}) is on this computer, so a helper here can act as the owner (sign it "
            "out here; the helpers use their own account)" for n in here if n in owners]
    notes = ["key variables are set here (" + ", ".join(found["vars"]) + "): whoever owns them, a helper here can act as"
             ] if found["vars"] else []
    me = cfg.get("me") or (found["gh"][0] if found["gh"] else "")
    if me:
        notes.append("signed in here as @" + me.lstrip("@") + ": " + role(cfg, me))
        if not BREAK("lock_approver_login_here") and ("approves" in role(cfg, me) or "looks after" in role(cfg, me)) \
                and me.lstrip("@").lower() not in owners:
            notes.append("your helper is signed in to GitHub as you, so it could press Approve as you. Don't ask it to "
                         "review; to close this, give it its own account (python fg/lock.py --steps)")
    if gh and repo and not BREAK("lock_key_powers"):
        r, _ = _gh_json(root, gh, f"repos/{repo}")
        if isinstance(r, dict) and (r.get("permissions") or {}).get("admin") and me.lstrip("@").lower() not in owners:
            gaps.append(f"the login here (@{me.lstrip('@')}) is an admin of the project on GitHub, so it can change or "
                        "switch off the rules (give the helpers' account Write, not Admin)")
    notes.append("the kit can't see " + found["cant_see"])
    return gaps, notes


def team_gaps(root, repo, branch, cfg, gh=None):
    """(gaps, why): what the team lock still lacks on GitHub ([] = none), or (None, why) when GitHub couldn't be asked."""
    if BREAK("lock_team") or not (cfg.get("team") or cfg.get("kit_app_id")):
        return [], ""
    gh = gh or find_gh(cfg)
    if not gh:
        return None, NO_GH
    gaps, app = [], cfg.get("kit_app_id")
    rules, why = _gh_json(root, gh, f"repos/{repo}/rules/branches/{branch}")
    if not isinstance(rules, list):
        return None, why
    need = [c for r in rules if isinstance(r, dict) and r.get("type") == "required_status_checks"
            for c in ((r.get("parameters") or {}).get("required_status_checks") or []) if c.get("context") == NOTE_CHECK]
    if not app:
        gaps.append("kit_app_id isn't set in foundationguard.json (the kit's own GitHub App's number)")
    if not need:
        gaps.append(f"GitHub doesn't require the \"{NOTE_CHECK}\" check on {branch}")
    elif app and not any(str(c.get("integration_id")) == str(app) for c in need):
        gaps.append(f"GitHub requires \"{NOTE_CHECK}\" from any app, not only the kit's (app {app}): a workflow on a "
                    "change's branch can fake it")
    env = cfg.get("kit_environment") or "fg-kit"
    e, why = _gh_json(root, gh, f"repos/{repo}/environments/{env}")
    if e is None or e == {}:
        return (None, why) if e is None and "can't read" not in (why or "") else \
            (gaps + [f"GitHub shows no \"{env}\" environment the kit can see (it holds the kit app's key)"], "")
    pol = e.get("deployment_branch_policy") or {}
    if not pol.get("custom_branch_policies"):
        gaps.append(f"the \"{env}\" environment doesn't limit which branches may use it, so a change's branch could "
                    "read the kit app's key (set Deployment branches to main only)")
    else:
        ps, why = _gh_json(root, gh, f"repos/{repo}/environments/{env}/deployment-branch-policies")
        if ps is None:
            return None, why
        names = sorted(p.get("name", "") for p in (ps.get("branch_policies") or []))
        if names != [branch]:
            gaps.append(f"the \"{env}\" environment lets {', '.join(names) or 'no branch'} use it, not only {branch}")
    if not BREAK("opinion_key_main_only"):              # Plan 2 merge D: the second opinion's key, like the app's, main only
        k, _ = _gh_json(root, gh, f"repos/{repo}/actions/secrets/FG_OPINION_KEY")
        if isinstance(k, dict) and k.get("name"):
            gaps.append(f"the second opinion's key (FG_OPINION_KEY) is a project-wide secret, so a workflow on a "
                        f"change's branch can use it; keep it only in the \"{env}\" environment")
    return gaps, ""


def missing(cfg):
    """Plain list of what the lock still lacks in the project's own files."""
    root, out = cfg["_root"], []
    if not cfg.get("owner_github"):
        out.append("owner_github isn't set in foundationguard.json")
    if not os.path.exists(os.path.join(root, ".github", "CODEOWNERS")):
        out.append("no .github/CODEOWNERS file (python fg/codeowners.py writes it)")
    if not os.path.exists(os.path.join(root, ".github", "workflows", "foundationguard-note.yml")):
        out.append("the note check isn't in .github/workflows (copy docs/foundationguard-note.yml there)")
    return out


def state(cfg):
    """('locked'|'confirmed'|'off'|'not locked'|'no github', reasons). Kept for fg/lockmode.py."""
    st = _state(cfg)
    import lockmode as LM
    LM.note(cfg, st[0])
    return st


def _state(cfg):
    root = cfg["_root"]
    repo = github_repo(root)
    if not repo:
        return "no github", []
    main = (cfg.get("protected_branches") or ["main"])[0]
    asked = cfg.get("github_check", True)                                          # false: never ask GitHub
    says, why = github_says(root, repo, main, cfg) if asked else (None, "")
    if says is not None:
        _remember(cfg, says)
    gaps = missing(cfg)
    if says is True:
        tg, why = team_gaps(root, repo, main, cfg) if asked else ([], "")
        if tg is None and not BREAK("lock_team_unsure"):
            return "could not check", [why] + gaps
        lg = login_gaps(root, repo, cfg, find_gh(cfg))[0] if asked else []
        import drill as DR
        lg += [g for g in [DR.gap(cfg)] if g]
        if tg or lg:
            return "not locked", gaps + (tg or []) + lg
        return "locked", gaps
    if says is None and why == PLAN_CANT:
        return "can't be on", [why] + gaps
    conf = cfg.get("github_lock") or {}
    if says is False:
        return ("off" if conf.get("words") else "not locked"), gaps + [f"GitHub shows no lock on {main}"]
    if conf.get("words") and not gaps:
        return "confirmed", []
    if asked and not BREAK("lock_could_not_check"):                               # GitHub couldn't be asked: never "not locked"
        return "could not check", [why] + gaps + ([] if conf.get("words") else ["the owner hasn't said the GitHub steps are done"])
    return "not locked", gaps + ([] if conf.get("words") else ["the owner hasn't said the GitHub steps are done"])


SEEN = "github_lock_seen.json"
SEEN_HOURS = 24


def _remember(cfg, says):
    """What GitHub last said about the lock, so the quick start-of-session reminder (fg/ready.py) needn't ask it."""
    p = os.path.join(cfg["_root"], cfg.get("state_dir") or ".foundationguard", SEEN)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump({"locked": bool(says), "at": time.time()}, f)
    except OSError:
        pass


def seen(cfg):
    """True or False: GitHub's answer within the last day; None when there is none that fresh."""
    if BREAK("lock_seen"):
        return None
    try:
        with open(os.path.join(cfg["_root"], cfg.get("state_dir") or ".foundationguard", SEEN)) as f:
            j = json.load(f)
        return bool(j["locked"]) if time.time() - float(j["at"]) < SEEN_HOURS * 3600 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


HELPER_LINE = ("Before other work, walk the owner through  python fg/lock.py --steps  one step at a time, and wait "
               "for them to click. Never change GitHub settings yourself.")


NOT_LOCKED = ("Your project isn't locked on GitHub yet",
              "GitHub (the website that keeps the online copy of your project) would accept changes that skip these checks.")
LOCK_OFF = ("The GitHub lock was switched off", "You said GitHub was locked, but GitHub now shows no lock on the main branch.")
COULD_NOT = ("The kit could not check your GitHub lock",
             "It doesn't know whether GitHub (the website that keeps the online copy of your project) would refuse "
             "changes that skip these checks.")


def _could_not_card(why):
    return {"who": "you", "title": COULD_NOT[0], "happened": COULD_NOT[1] + " Why: " + (why[0] if why else "no answer") + ".",
            "means": "This is not the same as \"not locked\": it may be locked. Until the kit can see it, or you say so, "
            "this card stays.",
            "action": "If you locked main on GitHub yourself, tell your helper in your own words (it records them with "
            "python fg/lock.py --confirm). If you haven't, say \"walk me through the GitHub lock\". To let the kit check "
            "by itself: install GitHub's gh tool and sign in (gh auth login).",
            "evidence": [HELPER_LINE] + list(why)}


def _lock_card(st, why):
    if st == "could not check":
        return _could_not_card(why)
    if st == "can't be on":
        return {"who": "you", "title": "Your GitHub plan can't hold a change for a review",
                "happened": why[0] + ".", "means": "Every check here runs on this computer, and anyone working here can "
                "switch it off. On this plan GitHub can't be the lock that stops that.",
                "action": "Choose one: keep it as an alarm and a record (nothing to do), upgrade the plan, or make the "
                "project public. Then tell your helper what you chose.", "evidence": list(why)}
    title, happened = NOT_LOCKED if st == "not locked" else LOCK_OFF
    return {
        "who": "you", "title": title, "happened": happened,
        "means": "Every check here runs on this computer, and anyone working here, an AI helper included, can "
        "switch it off. Only GitHub's own lock can't be switched off from here.",
        "action": "Say to your helper: \"walk me through the GitHub lock\". It takes about 15 minutes.",
        "evidence": [HELPER_LINE] + list(why)}


def cards(cfg, rng=None):
    """'For you' cards about the GitHub lock for the push summary."""
    if BREAK("github_lock"):
        return []
    st, why = state(cfg)
    out = [_lock_card(st, why)] if st in ("not locked", "off", "could not check", "can't be on") else []
    out += confirm_cards(cfg, rng)
    return out


def confirm_cards(cfg, rng):
    """A push that records the owner's 'GitHub is locked' is the owner's decision: the helper could have typed it."""
    if not rng or BREAK("github_lock_confirm"):
        return []
    base = rng.split("..")[0]
    try:
        old = json.loads(_git(cfg["_root"], "show", f"{base}:foundationguard.json") or "{}").get("github_lock") or {}
    except ValueError:
        old = {}
    new = cfg.get("github_lock") or {}
    if not new.get("words") or new == old:
        return []
    return [{"who": "you", "title": "The helper recorded that GitHub is locked",
             "happened": f"foundationguard.json now says the GitHub steps are done (words given: \"{new['words'][:80]}\").",
             "means": "If that isn't true, the one lock the helper can't switch off isn't there.",
             "action": "Say yes only if you did the GitHub steps yourself. To reject, just tell the helper \"no\".",
             "evidence": ["foundationguard.json: github_lock"]}]


def _confirm(cfg, argv):
    w = argv[argv.index("--words") + 1] if "--words" in argv[:-1] else ""
    if not w.strip():
        print("LOCK: --confirm needs the owner's own words: --confirm --words \"I locked main on GitHub today\""); return 1
    import time
    p = os.path.join(cfg["_root"], "foundationguard.json")
    j = json.load(open(p, encoding="utf-8-sig"))
    j["github_lock"] = {"words": w, "when": time.strftime("%Y-%m-%d %H:%M")}
    json.dump(j, open(p, "w", encoding="utf-8"), indent=2)
    print("LOCK: recorded. The next push summary asks the owner to confirm it."); return 0


def main(argv):
    cfg = C.load()
    if "--steps" in argv:
        print(STEPS); return 0
    if "--confirm" in argv:
        return _confirm(cfg, argv)
    if "--drill" in argv:
        import drill as DR
        repo, gh = github_repo(cfg["_root"]), find_gh(cfg)
        if not (repo and gh):
            print("DRILL: needs a GitHub project and gh signed in as the helpers' account."); return 1
        return DR.main(cfg, repo, gh)
    st, why = state(cfg)
    print(f"LOCK: {st}" + ("" if not why else ":\n  " + "\n  ".join(why)))
    for line in team_lines(cfg):
        print("  " + line)
    return 0 if st in ("locked", "confirmed", "no github") else 1


def team_lines(cfg):
    """The team plan's S5/S6 lines: who is who, the plan, who is signed in here and what that login can do."""
    root = cfg["_root"]
    repo, gh = github_repo(root), find_gh(cfg)
    if not (cfg.get("team") or cfg.get("owner_github")) or not repo or not cfg.get("github_check", True):
        return []
    import codeowners as CO
    out = []
    t = CO.team(cfg)
    if t:
        out.append("Owners: " + ", ".join(t["owners"]) + " (only they approve the kit, its settings and the team list).")
        for g, ns in t["check_owners"].items():
            out.append(f"{', '.join(ns)}: looks after {g}.")
        if t["bots"]:
            out.append(", ".join(t["bots"]) + ": helpers' accounts. They can upload; their Approve never counts.")
    if gh:
        cant, notes = plan_words(root, repo, gh)
        out += notes
        out += login_gaps(root, repo, cfg, gh)[1]
    return out


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""FoundationGuard: join a team's project on a fresh clone, in one step (AI-made, Claude, 2026-11-17; the team plan 2.7,
merge C). Run from the clone's top folder:
  python fg/setup.py --join
It writes only files that are never committed:
  - this copy's own settings, .git/foundationguard/local.json (who you are on GitHub, where gh is);
  - the AI tool's hooks for this computer, .claude/settings.local.json, kept out of git (.git/info/exclude);
so there is nothing to commit and nothing to conflict. If a helper runs it, the kit's box asks once. Then it says who
you are in the team, what the kit will and won't do on this computer, and where the team's lock stands.
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


def say(x):
    print("FoundationGuard: " + x)


def _write_local(root, data):
    import config as C
    p = C.local_path(root)
    if not p:
        return None
    old = {}
    if os.path.isfile(p):
        try:
            old = json.loads(C.read_text(p))
        except (ValueError, OSError):
            old = {}
    old.update({k: v for k, v in data.items() if v})
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(old, f, indent=2)
    return p


def _shared_python_works(root):
    """The shared hooks name the installer's Python (the team plan, 1: a full path from the owner's computer); does it
    exist on this one?"""
    import copies as CP, shlex, shutil
    for e in CP._read(os.path.join(root, ".claude", "settings.json")).get("hooks", {}).get("PreToolUse", []):
        for h in e.get("hooks", []):
            c = str(h.get("command", ""))
            if "guard.py" not in c:
                continue
            try:
                first = shlex.split(c, posix=os.name != "nt")[0].strip('"')
            except (ValueError, IndexError):
                return False
            return os.path.isfile(first) if os.path.isabs(first) or "/" in first.replace("\\", "/")[1:] else bool(shutil.which(first))
    return False


def _hooks(root, py):
    import copies as CP
    if BREAK("join_nothing_tracked"):                  # the old way: the shared settings file gets this computer's hooks
        p = os.path.join(root, ".claude", "settings.json")
        d = CP._read(p)
        d.setdefault("hooks", {}).update(CP.hooks_for(py, os.path.abspath(root).replace("\\", "/")))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        return
    ours = CP.live(root) and CP.runs_this_kit(root) and _shared_python_works(root)
    if not ours or not CP.checked_after(root):
        CP.cover_one(root, py, os.path.abspath(root).replace("\\", "/"), only_after=ours)


def main(argv):
    import config as C, lock as LK, logins as LG
    root = C.find_root()
    if not os.path.isfile(os.path.join(root, "foundationguard.json")) or not os.path.isfile(os.path.join(root, "fg", "guard.py")):
        say("this project has no kit yet. The owner sets it up once with python fg/setup.py; then each person joins."); return 1
    cfg = C.load(root)
    gh = LK.find_gh(cfg)
    me = cfg.get("me") or next(iter(LG.gh_accounts(root, gh)), "")
    _write_local(root, {"me": ("@" + me.lstrip("@")) if me else None, "gh_path": gh if gh and not cfg.get("gh_path") else None})
    _hooks(root, C.hook_python())
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL).stdout.strip()
    say("this copy is set up for you." + (" Nothing to commit." if not dirty else " (Other changes in this copy were "
        "already there; the kit added none.)"))
    cfg = C.load(root)
    if me:
        print(f"You are @{me.lstrip('@')}: " + LK.role(cfg, me) + ".")
    else:
        print("The kit can't tell who you are on GitHub (gh isn't signed in here). Your helper can set it: "
              "\"me\" in .git/foundationguard/local.json.")
    print("On this computer the kit will: tell you when a step weakens a check, and stop changes to the kit's own switches.")
    print("It will not: put back anything that is exactly as GitHub has it, or ask you to OK a teammate's work.")
    if cfg.get("github_check", True):
        st, why = LK.state(cfg)
        print("TEAM LOCK: " + st.upper() + ("" if not why else ": " + "; ".join(why[:3])))
        for line in LK.team_lines(cfg):
            print(line)
    say("restart any AI session open in this folder so it uses these hooks.")
    return 0

"""FoundationGuard on every copy of the project (AI-made, Claude, 2026-11-11).

The game's first real morning with the kit (11 Nov): the edit guard was wired only in the folder where the kit was
installed. A helper session opened in a second copy of the same project (another checkout beside it) ran unguarded, and
a test file was changed without the owner being asked; nothing said so. So:
  - install also covers every other copy it can find: each git worktree of the project, and each folder beside it whose
    git remote is the same. Each gets the guard hook in its own .claude/settings.local.json (kept out of git), calling
    this kit by its full path, with this folder's settings when the copy has none of its own;
  - every new AI session starts with one line saying whether the guard is live in that folder;
  - every upload summary names a copy that has no guard, as a FOR YOU card.

  python fg/copies.py           list the copies and whether each is guarded
  python fg/copies.py --cover   cover the ones that aren't, and add this kit where only an older copy of it guards
                                (install does this too)
A file inside another copy is judged by that copy's own settings (fg/guard.py, 12 Nov), whichever copy the session
opened in.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import door as DR

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
KIT = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit" + ("" if os.environ.get("FG_BREAK") == "monitor_tool" else "|Monitor")
SETTINGS = (".claude/settings.json", ".claude/settings.local.json")
MAX_BESIDE = 60                                  # folders looked at beside the project, so a crowded drive stays quick


def _git(cwd, *a):
    try:
        p = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def _same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _worktrees(root):
    out = []
    for line in _git(root, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            out.append(line[len("worktree "):].strip())
    return out


HOSTS_ANY_CASE = ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "dev.azure.com", "ssh.dev.azure.com")


def repo_id(url, base=None):
    """One project's remote written one way, whichever way the URL is written (an outside review, 12 Nov: one checkout
    using https://github.com/o/game.git and another git@github.com:o/game.git weren't seen as copies): the host without
    a user name or port, and the path without a trailing .git or slash. GitHub and the other big hosts ignore case."""
    u = (url or "").strip()
    if not u or os.environ.get("FG_BREAK", "") == "copies_same_remote":
        return u
    m = re.match(r"^(?:[a-z][a-z0-9+.-]*://)(?:[^@/]*@)?([^/:]+)(?::\d+)?(/.*)?$", u, re.I) or \
        re.match(r"^(?:[^@/:]+@)?([^/:]{2,}):(?!/)(.*)$", u)          # git@github.com:owner/game.git
    if not m:                                                     # a folder on this computer, from that checkout's own folder
        f = os.path.join(base, u) if base and not BREAK("copies_shared_history") else u
        return os.path.normcase(os.path.abspath(f)) if os.path.exists(f) else u
    host, path = m.group(1).lower(), (m.group(2) or "").strip("/")
    path = re.sub(r"(?i)\.git$", "", path).strip("/")
    if host.endswith(HOSTS_ANY_CASE + ("visualstudio.com",)):
        path = path.lower()
    if os.environ.get("FG_BREAK", "") == "":            # outside review 3 (Grok, 12 Nov): Azure DevOps writes one project
        host, path = _azure(host.lower(), path)          # three ways
    return host + "/" + path


def _azure(host, path):
    """Azure DevOps: https://dev.azure.com/org/proj/_git/repo, git@ssh.dev.azure.com:v3/org/proj/repo and
    https://org.visualstudio.com/proj/_git/repo are one project."""
    p = path.split("/")
    if host in ("ssh.dev.azure.com", "vs-ssh.visualstudio.com") and len(p) == 4 and p[0] == "v3":
        return "dev.azure.com", "/".join(p[1:3] + ["_git", p[3]])
    if host.endswith(".visualstudio.com") and host != "vs-ssh.visualstudio.com":
        p = p[1:] if p and p[0] == "defaultcollection" else p
        return "dev.azure.com", "/".join([host.split(".")[0]] + p)
    return host, path


def same_remote(a, b):
    return bool(a) and repo_id(a) == repo_id(b)


def _first_commits(d):
    return set(_git(d, "rev-list", "--max-parents=0", "HEAD").split())


def same_project(a, b):
    """b is a checkout of the project in a: the same remote, read from each one's own folder, and (when both have
    commits) the same first commit. The owner's PC, 13 Nov: two unrelated test projects side by side, each with the remote
    ../remote.git, were taken as copies and setup wrote hooks into the other one."""
    ua, ub = (_git(d, "config", "--get", "remote.origin.url") for d in (a, b))
    if not ua or repo_id(ua, a) != repo_id(ub, b):
        return False
    fa, fb = _first_commits(a), _first_commits(b)
    return not fa or not fb or bool(fa & fb) or BREAK("copies_shared_history")


def _beside(root):
    """Folders next to the project that are checkouts of the same remote."""
    url = _git(root, "config", "--get", "remote.origin.url")
    parent = os.path.dirname(os.path.abspath(root))
    if not url or BREAK("copies_beside"):
        return []
    try:
        names = sorted(os.listdir(parent))[:MAX_BESIDE * 4]
    except OSError:
        return []
    dirs = [os.path.join(parent, n) for n in names if os.path.exists(os.path.join(parent, n, ".git"))][:MAX_BESIDE]
    return [d for d in dirs if same_project(root, d)]


def copies(root):
    """Every other checkout of this project that can be found: worktrees, then checkouts beside it."""
    found = []
    for d in _worktrees(root) + _beside(root):
        if os.path.isdir(d) and not _same(d, root) and not any(_same(d, f) for f in found):
            found.append(os.path.abspath(d))
    return found


def _read(p):
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guard_hook(entry):
    return any(re.search(r"/(guard|steps)\.py\b", str(h.get("command", "")).replace("\\", "/")) for h in entry.get("hooks", []))


def live(folder):
    """Is the guard hook set for file edits and commands in this folder's AI settings?"""
    for s in SETTINGS:
        for e in _read(os.path.join(folder, s)).get("hooks", {}).get("PreToolUse", []):
            if _guard_hook(e) and "Edit" in str(e.get("matcher", "")) and "Bash" in str(e.get("matcher", "")):
                return True
    return False


def checked_after(folder):
    """Is the check after every step (steps.py --after) wired in this folder's AI settings? The game's PC, 13 Nov: its
    sessions start in the play copy, whose settings had the guard but not the check after, so every yes'd change was
    put back at the next step as made "outside any helper step"."""
    for s in SETTINGS:
        for e in _read(os.path.join(folder, s)).get("hooks", {}).get("PostToolUse", []):
            if any(re.search(r"/steps\.py\b[^\n]*--after", str(h.get("command", "")).replace("\\", "/")) for h in e.get("hooks", [])) \
                    and "Edit" in str(e.get("matcher", "")) and "Bash" in str(e.get("matcher", "")):
                return True
    return BREAK("copies_after")


GUARD_PATH = re.compile(r"""["']?([^"'\s]*guard\.py)["']?""")


def runs_this_kit(folder):
    """Does a guard hook in this folder's AI settings call this copy of the kit? The game's PC, 12 Nov: the play copy
    was guarded by its own, older copy of the kit, so --cover left it alone and the newer kit's checks never ran in
    the sessions that open there."""
    for s in SETTINGS:
        for e in _read(os.path.join(folder, s)).get("hooks", {}).get("PreToolUse", []):
            for h in e.get("hooks", []):
                c = str(h.get("command", "")).replace("\\", "/")
                c = re.sub(r"\$\{?CLAUDE_PROJECT_DIR\}?|%CLAUDE_PROJECT_DIR%", folder.replace("\\", "/"), c)
                m = GUARD_PATH.search(c)
                if m and _same(os.path.dirname(os.path.join(folder, m.group(1))), KIT):
                    return True
    return False


KIT_PATH = re.compile(r"""["']?([^"'\s]*?)/(?:guard|steps)\.py\b""")
KEY_FILES = ("door.py", "between.py", "steps.py", "guard.py")


def _kit_sum(d):
    """What a copy of the kit holds, by its key files (line endings ignored, so a Windows checkout of the same kit
    matches)."""
    import hashlib
    out = []
    for n in KEY_FILES:
        try:
            out.append(hashlib.sha256(open(os.path.join(d, n), "rb").read().replace(b"\r", b"")).hexdigest())
        except OSError:
            out.append("missing")
    return out


def other_kits(folders):
    """Other copies of the kit that the AI settings of these folders also call (the game's PC, 16 Nov: a session
    started in the play copy ran its own 13 Nov kit before every step and this kit after it; the older one didn't know
    the owner's door, so the owner's own away mode was put back). Each: (kit folder, what differs)."""
    if BREAK("two_kits"):
        return []
    seen, out = set(), []
    for folder in folders:
        if not folder:
            continue
        for s in SETTINGS:
            for entries in _read(os.path.join(folder, s)).get("hooks", {}).values():
                for e in entries if isinstance(entries, list) else []:
                    for h in e.get("hooks", []) if isinstance(e, dict) else []:
                        c = str(h.get("command", "")).replace("\\", "/")
                        c = re.sub(r"\$\{?CLAUDE_PROJECT_DIR\}?|%CLAUDE_PROJECT_DIR%", folder.replace("\\", "/"), c)
                        m = KIT_PATH.search(c)
                        if not m:
                            continue
                        d = os.path.normpath(os.path.join(folder, m.group(1)))
                        if _same(d, KIT) or os.path.normcase(d) in seen or not os.path.isdir(d):
                            continue
                        seen.add(os.path.normcase(d))
                        mine, theirs = _kit_sum(KIT), _kit_sum(d)
                        if mine != theirs:
                            gone = [n for n, t in zip(KEY_FILES, theirs) if t == "missing"]
                            out.append((d, ("it has no " + ", ".join(gone)) if gone else "its files differ from this one"))
    return out


def two_kits_words(folders):
    bad = other_kits(folders)
    if not bad:
        return ""
    d, why = bad[0]
    return ("FoundationGuard: TWO KITS RUN IN THIS SESSION: the AI settings also call an older or different kit in " + d
            + " (" + why + "), next to this one in " + KIT + ". The other one judges every step by its own rules: it may "
            "put back the owner's own kit commands (away mode, a kept file) and the gate's pass file. Start helper "
            "sessions from the folder whose kit is newest, or bring that copy's kit up to date.")


def hooks_for(py, home):
    """The hook entries a copy gets: the guard on every command and edit, and the start-of-session status line."""
    g = f'{py} "{KIT}/guard.py" --home "{home}"'
    a = f'{py} "{KIT}/steps.py" --after --home "{home}"'
    return {"PreToolUse": [{"matcher": MATCHER, "hooks": [{"type": "command", "command": g}]}],
            "PostToolUse": [{"matcher": MATCHER, "hooks": [{"type": "command", "command": a}]}],
            "SessionStart": [{"matcher": "startup|resume|compact|clear",
                              "hooks": [{"type": "command", "command": g.replace("--home", "--status --home")}]}]}


def _keep_out_of_git(folder):
    ex = _git(folder, "rev-parse", "--git-path", "info/exclude")
    if not ex:
        return
    ex = ex if os.path.isabs(ex) else os.path.join(folder, ex)
    os.makedirs(os.path.dirname(ex), exist_ok=True)
    text = open(ex, encoding="utf-8").read() if os.path.exists(ex) else ""
    if ".claude/settings.local.json" not in text.split("\n"):
        open(ex, "a", encoding="utf-8").write(("\n" if text and not text.endswith("\n") else "") + ".claude/settings.local.json\n")


def cover_one(folder, py, home, only_after=False):
    """This kit's hooks in the copy's own settings.local.json; only the check after every step when the copy's guard
    already runs this kit (so the guard doesn't run twice)."""
    p = os.path.join(folder, ".claude", "settings.local.json")
    data = _read(p)
    hooks = data.setdefault("hooks", {})
    for event, entries in hooks_for(py, home).items():
        if only_after and event != "PostToolUse":
            continue
        mine = [e for e in hooks.get(event, []) if not _guard_hook(e)]
        hooks[event] = mine + entries
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    _keep_out_of_git(folder)


def cover(root, py):
    """Cover every copy that isn't guarded yet, or is guarded only by another copy of the kit (that one's hook stays,
    and this kit's checks run there too). Returns the folders covered."""
    if BREAK("every_copy"):
        return []
    done = []
    for d in copies(root):
        ours = live(d) and (runs_this_kit(d) or BREAK("copies_other_kit"))
        if not ours or not checked_after(d):
            f = os.path.join(d, ".claude", "settings.local.json")
            before = DR.ids([f])
            cover_one(d, py, os.path.abspath(root).replace("\\", "/"), only_after=ours)
            _journal(root, d, before)
            done.append(d)
    return done


def _journal(root, d, before):
    """The copy's own journal gets the door line (Fable's beta plan, line 3): the owner's yes lived in one folder's notes
    only, so a copy whose check after the step didn't run put its new hooks back (ten copies, 14 Nov)."""
    if BREAK("copies_journal"):
        return
    try:
        import config as C
        home = C.load(root)
        mine = C.load(d) if os.path.exists(os.path.join(d, "foundationguard.json")) else C.load(d, root)
        DR.wrote_changed(mine, before, "the kit's install covered this copy of the project", ok=home)
    except Exception:                                  # never in the way of the cover itself
        pass


def unguarded(root):
    return [] if BREAK("copies_card") else [d for d in copies(root) if not live(d)]


def cards(cfg):
    """A FOR YOU card for the upload summary when a copy of the project has no guard."""
    bad = unguarded(cfg["_root"])
    if not bad:
        return []
    return [{"who": "you", "title": "A copy of your project has no guard",
             "happened": f"{len(bad)} other copy(s) of this project on this computer have no FoundationGuard hook: "
                         + ", ".join(bad[:3]) + (" and more" if len(bad) > 3 else "") + ".",
             "means": "An AI helper working in that folder can change tests and guard files without asking you.",
             "action": "Say to your helper: \"cover every copy with FoundationGuard\" (it runs  python fg/copies.py --cover).",
             "evidence": ["no guard hook in .claude/settings.json or .claude/settings.local.json: " + d for d in bad]}]


def _gathering(folder):
    try:
        cfg = json.load(open(os.path.join(folder, "foundationguard.json"), encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    return isinstance(cfg, dict) and bool(cfg.get("gather_asks"))


GATHERED = (" The owner's asks are gathered (gather_asks): changes to tests and the owner's guard files go through and "
            "are logged, and the upload waits for the owner's yes (python fg/ownerok.py lists them). The kit's own files "
            "and settings, its records, deletes, other pushes and installs still ask at once: plan a run without the "
            "owner around them, and never run fg/ownerok.py --give or push.py --break-glass during it.")


AFTER_MISSING = (" WARNING: the check after each step is NOT wired in this folder's AI settings, so a change the owner "
                 "says yes to can be put back at the next step. Tell the owner, and run  python fg/copies.py --cover  from "
                 "the folder where the kit is installed (the kit's box asks).")


def status_line(folder):
    two = two_kits_words([folder])
    return _status(folder) + ((" " + two) if two else "")


def _status(folder):
    if live(folder) and not checked_after(folder) and not BREAK("status_after"):
        return "FoundationGuard: the guard is live in this folder (" + folder + ")." + AFTER_MISSING
    if live(folder) or BREAK("guard_status"):
        if _gathering(folder) and not BREAK("status_gathered"):    # 12 Nov: an unattended run plans around what still asks
            return "FoundationGuard: the guard is live in this folder (" + folder + "). The usual ways of writing risky commands are blocked." + GATHERED
        return ("FoundationGuard: the guard is live in this folder (" + folder + "). The usual ways of writing risky commands are blocked, and "
                "changes to tests and guard files ask the owner.")
    return ("FoundationGuard: WARNING: the guard is NOT live in this folder (" + folder + "). Changes to tests and guard "
            "files will not ask the owner. Tell the owner, and run  python fg/install.py  (or fg/copies.py --cover).")


def main(argv):
    import config as C
    root = C.find_root()
    if "--cover" in argv:
        done = cover(root, C.hook_python())
        print("FoundationGuard: covered " + (", ".join(done) if done else "nothing new: every copy found is guarded") + ".")
        return 0
    found = copies(root)
    print("FoundationGuard: this folder: " + ("guarded" if live(root) else "NOT guarded") + f" ({root})")
    for d in found:
        print(("  NOT guarded  " if not live(d) else "  guarded by another copy of the kit (--cover adds this one)  "
               if not runs_this_kit(d) else "  guarded, but the check after each step is missing (--cover adds it)  "
               if not checked_after(d) else "  guarded      ") + d)
    if not found:
        print("  no other copies found (worktrees, or checkouts of the same remote beside this folder)")
    return 0 if all(live(d) for d in [root] + found) else 1


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

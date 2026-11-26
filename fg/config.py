"""FoundationGuard config loading (AI-made, Claude, 2026-11-08). One JSON file at the repo root: foundationguard.json."""
import json, os, sys


def _utf8_output():
    """Windows (CI, 11 Nov): printing a sign such as an arrow to a pipe in the old code page crashed the kit. Output that
    is not already UTF-8 becomes UTF-8, and a sign that still cannot be written is replaced, never fatal."""
    if os.environ.get("FG_BREAK", "") == "utf8_output":
        return
    for s in (sys.stdout, sys.stderr):
        try:
            if s and (s.encoding or "").lower().replace("-", "") != "utf8":
                s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_utf8_output()

DEFAULTS = {
    "protected_branches": ["main", "master"],
    "work_branch": None,                 # if set, fg push only pushes this branch
    "push_only_via_wrapper": True,       # block every direct `git push` except --dry-run; use `python fg/push.py`
    "gate_command": None,                # e.g. "python -m pytest -q" or "bash Tools/Scripts/prepush_tests.sh"
    "gate_records": [],                  # files the project's own gate writes on every run (a pass file; patterns allowed,
                                         # "Saved/FullTier/**"): never held for a yes
    "push_command": None,                # the project's own push wrapper, e.g. "bash Tools/Scripts/safe_push.sh": the recommended
                                         # list allows it exactly (fg/allowlist.py); every other push still asks
    "gate_pass_regex": None,             # optional: output must match this as well as exit 0
    "approved_file": "APPROVED.md",
    "test_log": None,                    # file the gate writes (JUnit XML or "PASS name" / "FAIL name" lines)
    "merge_signoff_file": None,          # if set, `gh pr merge N` needs a line "#N ..." in this file
    "block_while_running": [],           # process names (e.g. UnrealEditor.exe); jobs below are blocked while any runs
    "job_patterns": [],                  # regexes for heavy jobs (builds, tests, captures) blocked while those run
    "extra_block": [],                   # [{"pattern": regex, "why": text}]
    "state_dir": ".foundationguard",
    # v0.3: the guards guard themselves
    "guard_paths": [],                   # extra globs an agent may not change without the owner's OK (defaults below always apply)
    "guard_decision": "ask",             # "ask" = the owner must approve the change in the agent's permission prompt; "deny" = never
    "guard_decisions": {},               # v0.8.6: per path or glob, "deny" or "ask" (e.g. {"Saved/MergeApprovals.txt": "deny"});
                                         # guard_decision is the default for every guard file not named here
    "owner_github": None,                # e.g. "@your-github-name": written into CODEOWNERS for the guard paths
    "full_gate_command": None,           # run as well when the machine's setup changed since the last pass
    # v0.8.5: a long gate as named steps (fg/stages.py), so a miss doesn't mean starting again from the top
    "gate_steps": [],                    # [{"name", "command", "guards": [globs], "always": bool, "needs": [names], "test_log": path}]
    "slow_gate_minutes": 10,             # a one-command gate slower than this gets a note: split it into steps
    "whole_run_days": 1.5,               # a step's pass is carried to a new commit only if a whole run passed this recently
    "engine_version_file": None,         # file whose contents name the engine version (e.g. Build.version), for the fingerprint
    "plugin_globs": [],
    # v0.7
    "secret_scan": True,                 # stop a push whose added lines hold a password, key or token (fg/secretscan.py)
    "tiny_lines": 25,                    # a source file under this many code lines is "tiny"
    "tiny_rise": 5,                      # more new tiny files than this in one push fails (chopping code to dodge limits)
    "require_review": False,
    "github_check": True,                # ask GitHub (read-only, with the gh tool) whether main is locked
    "gh_path": None,                     # where gh is, if it is not on the PATH or in its usual install folders
    # 11 Nov (the game's first real morning): every new test asked the owner (fg/adds.py)
    "helpers_add_tests": True,           # a helper may ADD tests (a new test file, new tests in one) without asking;
                                         # anything that changes, removes, renames or skips a test still asks
    "test_files": [],                    # the project's own check scripts that count as tests for that, by name, such as
                                         # ["Tools/Scripts/*_check.sh", "Tools/Scripts/check_*.py"] (the game's PC, 12 Nov):
                                         # a new one adds freely; changing, removing or renaming one still asks
    "review_lane": False,                # True: a helper's change to the owner's own guard files goes to the reviewer
                                         # at the upload, not a box (fg/review.py; the owner, 16 Nov)
    "run_copies": [],                    # other copies a scheduled run owns (the nightly's folder): left out of the checks
                                         # other sessions' steps make; a session in that folder still checks it (23 Nov)
    "box_hours": "",                     # "07:00-23:00": inside these hours (the computer's clock) every guard change asks
                                         # in a box, even with review_lane or gather_asks on (the owner, 23 Nov)
    "review_command": None,              # the owner's reviewer program, as a list
    "review_timeout_s": 600,
    "owner_only": [],                    # guard files that always stay the owner's call, reviewer or not
    "remote_report_only": False,         # True: the kit's GitHub check only reports (neutral), never blocks or edits
    "ask_budget": 5,                     # the owner's daily limit of OK boxes (the owner, 16 Nov: 82 in a day he couldn't judge)
    "chat_first": False,                 # True (setup writes it): before a box opens, the helper must post the kit's
                                         # question in the chat, and the kit checks the chat shows it (fg/box.py)
    "python_variables": [],              # names of variables that hold Python on this PC ("PY" for "$PY" - <<'EOF'): a
                                         # small Python program run through one is read like one run with python
    "chat_tools": [],                    # more tool-name patterns that send the owner a message (send_message,
                                         # post_message and the like are known already)
    "gather_asks": False,                # True: changes to the owner's own guard files (not the kit) don't ask one by one;
                                         # the upload waits until the owner has said yes to them all at one sitting
    # v0.7: experienced users pick parts. Each is "on" (blocks), "warn" (reports, never blocks) or "off".
    # Beginners leave this alone: everything is on. Changing it is a guard-file change (owner's OK; shown as weaker).
    "parts": {"guard": "on", "push": "on", "approved": "on", "structure": "on", "rules": "on", "assets": "on",
              "tiny": "on", "secrets": "on", "docs": "on", "state": "on"},             # True: an approved check not yet reviewed by a different helper fails the gate                  # plugin files whose versions belong in the fingerprint (e.g. "Plugins/*/*.uplugin")
}

ALWAYS_GUARDED = ["foundationguard.json", "fg/**", ".claude/settings.json", ".claude/settings.local.json", ".git/hooks/**",
                  "structure_baseline.json", "STRUCTURE_LOG.md", "rules_baseline.json", "assets_baseline.json", ".github/CODEOWNERS", ".github/workflows/**",
                  "secrets_allow.txt", "BREAKGLASS.md", "AGENTS.md", ".github/copilot-instructions.md", ".github/hooks/**", ".codex/**", ".cursor/hooks.json", ".cursor/rules/**", "docs_baseline.json", "DOC_TEST.md", ".foundationguard/tiny_files.json", "REVIEW_PROMPT.md",
                  ".git/foundationguard/**"]   # 12 Nov: the check after every step keeps its record there (fg/steps.py)


PARTS = ("guard", "push", "approved", "structure", "rules", "assets", "tiny", "secrets", "docs", "state", "tests_gone",
         "pystartup", "receipts", "ledger", "alarms", "night",
         "reminders")


def part(cfg, name):
    """'on', 'warn' or 'off' for a part (unknown values count as 'on', the safe side)."""
    if os.environ.get("FG_BREAK", "") == "parts":
        return "on"
    v = str((cfg.get("parts") or {}).get(name, "on")).lower()
    return v if v in ("on", "warn", "off") else "on"


# v0.8.5: the files in which the kit records "this commit passed". A helper that could write them could mark failing
# work as passed, so they are guard files too (the kit writes them itself; a helper's command or edit asks the owner).
STATE_GUARDED = ("passed_commit", "gate_results.json", "fingerprint.json", "owner_ok.json", "ownerok_asking", "ran_tests.json", "python_startup.json")


# v0.8.5: files only the kit's own checks read (they run at every gate), so a change to one needs no gate step re-run
KIT_LISTS = ["structure_baseline.json", "STRUCTURE_LOG.md", "rules_baseline.json", "assets_baseline.json", "docs_baseline.json",
             "BREAKGLASS.md", "secrets_allow.txt"]


KIT_PYTHON_MARK = "foundationguard-python.txt"    # the Windows download puts this file beside its own python.exe


def own_python():
    """The full path of the kit's own Python (the one inside the Windows download, beta gate line 4) when that Python is
    running the kit now, else "". It is known by the marker file the download puts beside it."""
    import sys
    exe = sys.executable or ""
    if not exe or os.environ.get("FG_BREAK", "") == "bundled_python":
        return ""
    return exe if os.path.isfile(os.path.join(os.path.dirname(exe), KIT_PYTHON_MARK)) else ""


def python_cmd():
    """The Python command the hooks and the gate should call (after the Godot game test, 11 Nov: on Windows "python" may not
    exist, or may be the Microsoft Store's stand-in that does nothing, so the hooks silently never ran). On Windows: the
    full path of the Python running the kit now, in forward slashes and quotes, which works in every shell."""
    import shutil, sys
    if os.environ.get("FG_BREAK", "") == "python_path":
        return "python" if os.name == "nt" else "python3"
    if os.name == "nt" or own_python() or not shutil.which("python3"):    # the kit's own Python: always by full path
        return '"' + sys.executable.replace("\\", "/") + '"'
    return "python3"


def hook_python():
    """The Python command the AI tools' hooks call: python_cmd() in isolated mode (-I), so PYTHONPATH, PYTHONSTARTUP and
    the user's own site folder can't change what the guard runs (the game's PC, 13 Nov: the game's own hooks had -I,
    the kit's install dropped it). The kit's scripts add their own folder to the path themselves."""
    return python_cmd() + ("" if os.environ.get("FG_BREAK", "") == "hook_isolated" else " -I")


def decision_for(cfg, path):
    """'deny' or 'ask' for a write to this guard file: the first matching entry of guard_decisions, else guard_decision.
    v0.8.6 (the build thread, 11 Nov): one file (the game's merge sign-off) must be refused while the rest only ask."""
    import paths as P
    default = cfg.get("guard_decision", "ask")
    if os.environ.get("FG_BREAK", "") == "guard_decisions":
        return default
    for glob, how in (cfg.get("guard_decisions") or {}).items():
        if P.matches(path or "", [glob]):
            return "deny" if str(how).lower() == "deny" else "ask"
    return default


# Outside review 8 (Grok, 13 Nov): a NEW pytest.ini with `addopts = --ignore=tests` went through with no box, and the gate
# then ran no tests. Setup guards the runner settings it finds; these are guarded always, whether there yet or not.
RUNNER_GUARDED = ["pytest.ini", "*/pytest.ini", "conftest.py", "*/conftest.py", "tox.ini", "noxfile.py", ".gutconfig.json",
                  "*/.gutconfig.json", "jest.config.*", "vitest.config.*", "vitest.workspace.*", "playwright.config.*",
                  ".mocharc*", "karma.conf.*", "*/jest.config.*", "*/vitest.config.*", "*/playwright.config.*",
                  "sitecustomize.py", "usercustomize.py"]


def _gate_words(cfg):
    words = [str(cfg.get("gate_command") or "")]
    for step in cfg.get("gate_steps") or []:
        words.append(str(step.get("command", "")) if isinstance(step, dict) else "")
    return " ".join(words).lower()


def _runner_files(cfg):
    """The general settings files the test runner the gate uses reads its own settings from (pytest: pyproject.toml and
    setup.cfg; npm and the like: package.json, whose "test" script and "jest" key change what the tests do)."""
    if os.environ.get("FG_BREAK", "") == "runner_guard":
        return []
    gate = _gate_words(cfg)
    out = list(RUNNER_GUARDED)
    if "pytest" in gate:
        out += ["pyproject.toml", "setup.cfg"]
    if any(w in gate for w in ("npm", "npx", "yarn", "pnpm", "bun ", "jest", "vitest", "playwright", "mocha", "karma")):
        out += ["package.json"]
    return out


def guard_globs(cfg):
    g = list(ALWAYS_GUARDED) + _runner_files(cfg) + list(cfg.get("guard_paths") or []) + list(cfg.get("guard_decisions") or {})
    if os.environ.get("FG_BREAK", "") != "state_guard":
        g += [(cfg.get("state_dir") or ".foundationguard").strip("/") + "/" + n for n in STATE_GUARDED]
    for k in ("approved_file", "merge_signoff_file"):
        if cfg.get(k):
            g.append(cfg[k])
    return g

def _worktree_top(d):
    """Is d the top of a git worktree? Its .git is a file pointing into the main repo's worktrees/ folder. A submodule's
    .git is a file too, but that is not the project's top, so the search goes on up (11 Nov, every copy guarded)."""
    g = os.path.join(d, ".git")
    if os.environ.get("FG_BREAK", "") == "worktree_root" or not os.path.isfile(g):
        return False
    try:
        line = open(g, encoding="utf-8", errors="replace").readline()
    except OSError:
        return False
    return line.startswith("gitdir:") and "/worktrees/" in line.replace("\\", "/")


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, "foundationguard.json")) or os.path.isdir(os.path.join(d, ".git")) or _worktree_top(d):
            return d
        p = os.path.dirname(d)
        if p == d:
            return os.path.abspath(start or os.getcwd())
        d = p

def read_text(p):
    """A text file as saved on any system: UTF-8 with or without a byte-order mark, or UTF-16 (Windows PowerShell 5's
    "> file" writes UTF-16). After the Godot game test (11 Nov): such a file crashed the kit with a raw Python error."""
    b = open(p, "rb").read()
    if os.environ.get("FG_BREAK", "") == "bom":
        return b.decode("utf-8")
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16")
    return b.decode("utf-8-sig")


BAD_JSON = ("FoundationGuard: foundationguard.json is not valid JSON (%s). Fix that line, or ask your helper to. "
            "Saved from Windows PowerShell? Save it as UTF-8.")


def _user_settings(p):
    """After the Godot game test (11 Nov): a broken settings file gives a plain message, never a raw Python error."""
    try:
        return json.loads(read_text(p))
    except ValueError as e:
        raise SystemExit(BAD_JSON % e)


def load(root=None, home=None):
    """The settings for this folder. home: the folder whose settings a copy of the project without its own uses
    (fg/copies.py: a second checkout guarded from the first one's kit)."""
    root = root or find_root()
    cfg = dict(DEFAULTS)
    p = os.path.join(root, "foundationguard.json")
    if home and not os.path.exists(p) and os.environ.get("FG_BREAK", "") != "copies_home":
        p = os.path.join(home, "foundationguard.json")
    if os.path.exists(p):
        user = _user_settings(p)
        if isinstance(user.get("parts"), dict):
            user["parts"] = dict(DEFAULTS["parts"], **user["parts"])
        cfg.update(user)
    cfg["_root"] = root
    _local(cfg, root)
    if os.environ.get("FG_BREAK", "") != "away_local":
        here = os.path.dirname(p) if os.path.exists(p) else root
        if away_local(here) or (here != root and away_local(root)):
            cfg["gather_asks"] = True                 # the owner's away switch, kept out of the project's files
            cfg["_away_local"] = True
    return cfg


# The team plan 2.7: per-person things leave the shared files. Each copy may keep its own machine settings in its git
# folder (.git/foundationguard/local.json: never committed, never shared). It may set these and nothing else; it can't
# switch a part off, loosen a rule or change who may approve.
LOCAL_KEYS = ("gh_path", "work_branch", "me")


def git_dir(root):
    """This copy's own git folder, without running git (a worktree's .git is a file naming it)."""
    g = os.path.join(root, ".git")
    if os.path.isfile(g):
        try:
            line = open(g, encoding="utf-8", errors="replace").readline().strip()
        except OSError:
            return None
        if line.startswith("gitdir:"):
            d = line[7:].strip()
            return d if os.path.isabs(d) else os.path.normpath(os.path.join(root, d))
        return None
    return g if os.path.isdir(g) else None


def local_path(root):
    g = git_dir(root)
    return os.path.join(g, "foundationguard", "local.json") if g else None


def _local(cfg, root):
    p = local_path(root)
    if not p or not os.path.isfile(p):
        return
    try:
        mine = json.loads(read_text(p))
    except (ValueError, OSError):
        return
    if not isinstance(mine, dict):
        return
    ok = set(mine) if os.environ.get("FG_BREAK", "") == "local_machine_keys_only" else set(LOCAL_KEYS)
    cfg.update({k: v for k, v in mine.items() if k in ok})
    cfg["_local_ignored"] = sorted(k for k in mine if k not in ok)


def away_local(folder):
    """The owner's away mode as their own terminal last set it: a stamped line in that folder's git folder
    (.git/foundationguard/proof/away.jsonl), so switching it leaves no change in the project for an upload to refuse
    (the game's PC, 16 Nov). The newest trusted line wins; none, or none trusted, is off."""
    try:
        import proofstore as PS
        for rec in reversed(PS.read({"_root": folder}, "away")):
            if not rec.get("_bad"):
                return bool(rec.get("on"))
    except Exception:
        pass
    return False

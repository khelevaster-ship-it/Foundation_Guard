"""FoundationGuard check-up (AI-made, Claude, 2026-11-13; outside review 7, Claude, 13 Nov).

An owner who can't read foundationguard.json asked: what is guarded, what isn't, are the hooks live, is GitHub locked?
This answers in plain words, one line each, and changes nothing.

  python fg/doctor.py          the check-up; ends 0 when every line is OK, 1 when something needs a look
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
OK, LOOK = "OK  ", "LOOK"


def _git(root, *a):
    try:
        p = subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _hooks_live(cfg):
    import copies as CP
    root = cfg["_root"]
    if not CP.live(root) and not BREAK("doctor_live"):
        return LOOK, ("the guard is NOT live for your AI tool in this folder: run setup again (python fg/setup.py), "
                      "then open a new AI session")
    after = any("steps.py" in str(h.get("command", "")) and "--after" in str(h.get("command", ""))
                for s in CP.SETTINGS for e in CP._read(os.path.join(root, s)).get("hooks", {}).get("PostToolUse", [])
                for h in e.get("hooks", []))
    if not after:
        return LOOK, "the guard is live, but the check after every step is not set (run python fg/install.py)"
    return OK, "the guard is live for your AI tool here, and the check after every step is set"


def _push_hook(cfg):
    root = cfg["_root"]
    other = _git(root, "config", "--get", "core.hooksPath")
    if other:
        return LOOK, f"git is pointed at other hooks ({other}), so the kit's push check doesn't run: ask your helper why"
    hook = _git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-push")
    try:
        text = open(hook, encoding="utf-8", errors="replace").read() if hook else ""
    except OSError:
        text = ""
    if "prepush.py" not in text:
        return LOOK, "the kit's push check (git's pre-push hook) is missing: run python fg/install.py"
    return OK, "the kit's push check runs on every upload from this computer"


def _uploads(cfg):
    prot = cfg.get("protected_branches") or []
    via = cfg.get("push_only_via_wrapper", True) and C.part(cfg, "push") == "on"
    head = ("uploads go only through python fg/push.py, after your tests pass on exactly that version"
            if via else "direct uploads with git push are allowed (push_only_via_wrapper is off)")
    if not prot:
        return OK, head + "; uploads straight to main are allowed (you work alone, --solo)"
    return OK, head + "; these branches change only through a reviewed pull request: " + ", ".join(prot)


def _tests(cfg):
    import testguard as TG
    root = cfg["_root"]
    globs = C.guard_globs(cfg)
    found = TG.found(root, cfg)
    files = [f for f in TG._listed(root) if P.matches(f, found)]
    loose = [f for f in files if not P.matches(f, globs)] if not BREAK("doctor_tests") else []
    if loose:
        return LOOK, (f"{len(loose)} test file(s) or test settings are NOT guarded, so a helper could change them "
                      "without asking you: " + ", ".join(loose[:8]) + (" and more" if len(loose) > 8 else "") +
                      ". Ask your helper to add them to guard_paths in foundationguard.json (the kit's box asks you)")
    if not files:
        return LOOK, "no test files were found, so no tests are guarded yet"
    return OK, f"all {len(files)} test files and test settings found are guarded: " + ", ".join(cfg.get("guard_paths") or [])


def _parts(cfg):
    off = [n for n in C.PARTS if C.part(cfg, n) != "on"]
    if off:
        return LOOK, "these features are not fully on: " + ", ".join(f"{n} ({C.part(cfg, n)})" for n in off)
    return OK, "every feature of the kit is on"


def _github(cfg):
    import lock as LK
    st, why = LK.state(cfg)
    words = {"locked": "GitHub is locked: changes to the main branch need a passing check",
             "confirmed": "you said the GitHub lock is on (the kit couldn't ask GitHub itself)",
             "no github": "this project has no GitHub copy, so nothing outside this computer locks it"}
    if st in ("locked", "confirmed"):
        return OK, words[st]
    return LOOK, words.get(st, "GitHub is NOT locked yet, and that is the lock that really holds") + (
        "; " + "; ".join(w for w in why if w) if why else "") + ". Walk through it with  python fg/lock.py --steps"


def _copies(cfg):
    import copies as CP
    left = CP.unguarded(cfg["_root"])
    if left:
        return LOOK, "other copies of this project are NOT guarded: " + ", ".join(left) + " (python fg/copies.py --cover)"
    return OK, "every other copy of this project the kit found is guarded too"


def _env(cfg):
    import gitsettings as GS
    keys = [os.environ.get(f"GIT_CONFIG_KEY_{i}", "").strip().lower() for i in range(GS._count(os.environ))]
    bad = [k for k in keys if k in GS.SWITCH_KEYS]
    if any(w in os.environ.get("GIT_CONFIG_PARAMETERS", "").lower() for w in GS.SWITCH_KEYS):
        bad.append("GIT_CONFIG_PARAMETERS")
    if bad and not BREAK("doctor_env"):
        return LOOK, ("git is told through the environment to use other hooks or settings files (" + ", ".join(bad) +
                      "); the kit's upload ignores them, but ask your helper why they are set")
    return OK, "nothing in the environment points git at other hooks"


def _python(cfg):
    import pyenv as PE
    new = PE.changed(cfg) if not BREAK("doctor_python") else []
    if new:
        return LOOK, ("Python's start-up files changed since the last pass (" + ", ".join(new[:4]) +
                      "); installing a package does that, otherwise ask your helper what changed them")
    return OK, "Python's start-up files are as they were at the last pass (or no pass is on record yet)"


PY_NAME = re.compile(r"(?i)^python[\d.]*(?:\.exe)?$")


def hook_pythons(cfg):
    """The Pythons this project's hooks and gate call: full paths as written, and bare names ("python3")."""
    import copies as CP
    root = cfg["_root"]
    texts = [str(cfg.get("gate_command") or ""), str(cfg.get("check_command") or "")]
    for s in CP.SETTINGS:
        for entries in (CP._read(os.path.join(root, s)).get("hooks") or {}).values():
            texts += [str(h.get("command", "")) for e in entries or [] if isinstance(e, dict) for h in e.get("hooks", [])
                      if isinstance(h, dict)]
    hook = _git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-push")
    try:
        texts.append(open(hook, encoding="utf-8", errors="replace").read() if hook else "")
    except OSError:
        pass
    found = []
    for t in texts:
        for quoted, bare in re.findall(r'"([^"\n]+)"|(?<![\w./\\-])(python[\d.]*(?:\.exe)?)(?=\s)', t):
            w = quoted or bare
            if PY_NAME.match(os.path.basename(w.replace("\\", "/"))) and w not in found:
                found.append(w)
    return found


def _kit_python(cfg):
    """The Windows download (beta gate line 4): every hook calls the download's own Python by its full path. When that
    Python is removed, the hooks stop without a word, so the check-up says so."""
    import shutil
    gone, own = [], 0
    for w in hook_pythons(cfg):
        full = "/" in w or "\\" in w
        there = os.path.isfile(w) if full else bool(shutil.which(w))
        if not there and not BREAK("hook_python_exists"):
            gone.append(w)
        own += bool(full and os.path.isfile(os.path.join(os.path.dirname(w), C.KIT_PYTHON_MARK)))
    if gone:
        return LOOK, ("the safety checks call a Python that is no longer on this computer (" + ", ".join(gone[:3]) +
                      "), so they are NOT running: install FoundationGuard again, then ask your helper to run its setup again")
    return OK, ("the safety checks call the kit's own Python, and it is there" if own else
                "the Python the safety checks call is on this computer")


def _computer(cfg):
    import ready as RD
    bad = RD.tools()
    return (LOOK, "; ".join(bad)) if bad else (OK, "Python and Git are installed")


def _boxes(cfg):
    import ready as RD
    many = RD.box_words(cfg)
    week = sum(n for _, n in RD.boxes(cfg))
    return (LOOK, many) if many else (OK, f"you were asked {week} time(s) in the last 7 days")


CHECKS = (("Guard", _hooks_live), ("Push check", _push_hook), ("Uploads", _uploads), ("Tests", _tests),
          ("Features", _parts), ("GitHub lock", _github), ("Other copies", _copies), ("Git settings", _env),
          ("Python start-up", _python), ("Kit's Python", _kit_python), ("This computer", _computer), ("Yes-boxes", _boxes))


def report(cfg):
    """[(name, OK or LOOK, plain words)]."""
    out = []
    for name, fn in CHECKS:
        try:
            mark, words = fn(cfg)
        except Exception as e:                     # a check-up that crashed says so; it never says OK
            mark, words = LOOK, f"this check could not run ({type(e).__name__}: {str(e)[:120]})"
        out.append((name, mark, words))
    return out


def main(argv):
    cfg = C.load()
    rows = report(cfg)
    print("FoundationGuard check-up for " + cfg["_root"])
    for name, mark, words in rows:
        print(f"  {mark}  {name}: {words}.")
    looks = [r for r in rows if r[1] == LOOK]
    print("FoundationGuard: " + _ending(len(looks)))
    return 1 if looks else 0


def _ending(looks):
    if not looks:
        return "everything checked is OK."
    return f"{looks} line(s) say LOOK: show them to your helper, or ask it to explain them."


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

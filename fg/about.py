"""FoundationGuard: what the owner's yes in a step covers (AI-made, Claude, 2026-11-13; outside review 6, Grok).

Review 6, finding 4: the check after every step read "the box asked" from the step's own note, and a script in the
step could write that note ("asked": true), so a step gave itself a yes. And a real yes for one file kept every change
of the step, a second script's switched-off push check included. Now:

  - the yes is worked out again from the hook's input (same tool, same input, same folder; a script cannot change
    what the AI tool hands the hook): `guard.py --about` runs the guard's own reading with no side effects (no note,
    no log, no yes note) and prints which files its box named;
  - a change stays only when its file is one the box named; a yes for a file never keeps a git setting (F273);
  - the editing tools (Edit, Write, MultiEdit, NotebookEdit) name exactly one file, so their yes covers that file.

Guard side: guard.py calls on() at the start, box() when it asks, and say() instead of printing its answer.
Steps side: fg/steps.py builds a Yes for the step and asks it whether a file is covered.

Limits: the yes covers a file, not what is written into it (a harmless sed on a test can cover a script that loosens
the same test in the same command). If the second reading fails or runs out of time, the step has no yes.
"""
import fnmatch, json, os, re, subprocess, sys

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
ON = [False]                 # guard.py --about: read only, say what the box names
NAMED = []                   # what the box names (absolute paths or patterns)
TEXTS = []                   # the shell command's words as the guard read them (for every file it names)
CWD = [""]                   # and the folder it runs in
EVERYTHING = "**"


# ---------- the guard's side (guard.py --about) ----------
def on(argv):
    """Turn the read-only mode on when guard.py was started with --about. Nothing is logged or noted."""
    if "--about" not in argv:
        return False
    ON[0] = True
    import catches as CL
    CL.log = lambda *a, **k: None
    return True


def _full(cfg, rel):
    return os.path.normcase(os.path.abspath(rel if os.path.isabs(rel) else os.path.join(cfg["_root"], rel)))


def _sd(cfg):
    return (cfg.get("state_dir") or ".foundationguard").strip("/")


def special(key, cfg):
    """The files a special box is about: the owner's yes, break glass, the accepted state and so on."""
    sd = _sd(cfg)
    if key == "owner ok":
        return [_full(cfg, sd + "/owner_ok.json"), _full(cfg, sd + "/ownerok_asking")]
    if key == "break glass":
        return [_full(cfg, "BREAKGLASS.md"), _full(cfg, sd + "/passed_commit")]
    if key == ".git/foundationguard/steps":
        return [EVERYTHING]                            # --accept: the owner takes every guard file as it is
    if key == ".claude/settings.json":
        return [_full(cfg, ".claude/settings.json"), _full(cfg, ".claude/settings.local.json")]
    if key == "the kit's install":                      # install.py / setup.py: every file an install writes
        import agents as AG
        own = [".claude/settings.json", ".claude/settings.local.json", "foundationguard.json", "APPROVED.md", ".git/hooks/pre-push", "fg"]
        own += list(AG.hook_files("fg", "python")) + list(AG.rules_files(""))
        return [_full(cfg, f) for f in own] + [os.path.normcase(os.path.join("*", ".claude", "settings.local.json"))]
    if key == ".claude/settings.local.json":            # copies.py --cover: each copy's AI tool settings
        return [os.path.normcase(os.path.join("*", ".claude", "settings.local.json"))]
    if key.startswith("the size, rule and licence records"):
        import steps as SP
        return [_full(cfg, b) for b in SP.BASELINES]
    return []


def named(cfg, G, cwd=None):
    """Every guard file the shell command names (the box may show only the first), as full paths or patterns."""
    import config as C
    globs, out = C.guard_globs(cfg), []
    folders = {g[:-3] for g in globs if g.endswith("/**") and not any(c in g[:-3] for c in "*?[")}
    for t in TEXTS:
        for w in re.findall(r"[\w./\\:*?\[\]~-]+", t):
            if "/" in w or "." in w or "\\" in w or w.rstrip("/\\") in folders:
                out += _one_word(w, cfg, G, globs, folders, cwd or CWD[0] or cfg["_root"])
    return out


def _one_word(w, cfg, G, globs, folders, here):
    import paths as P
    w = P.shell_path(w)
    full = w if os.path.isabs(w) else os.path.join(here, w)
    rel, out = P.rel(full, cfg["_root"]), []
    if P.matches(rel, globs) or P.matches(w, globs) or rel.rstrip("/") in folders:
        out.append(_full(cfg, rel))
    elif G.guard_elsewhere(full, cfg):
        out.append(os.path.normcase(os.path.abspath(full)))
    if w.endswith((".patch", ".diff")) and os.path.isfile(full):        # a patch names its files inside
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                out += [_full(cfg, n) for n in G._patch_names(f.read())]
        except OSError:
            pass
    return out


def box(key, cfg, G, special_box):
    """The guard is about to ask about key: note what that box covers."""
    if not ON[0] or BREAK("about_named"):
        return
    if special_box:
        found = special(str(key), cfg)
        NAMED.extend(found or [_full(cfg, str(key))])
        return
    NAMED.append(_full(cfg, str(key)))
    if TEXTS:
        NAMED.extend(named(cfg, G))


def say(kind):
    """guard.py --about's whole answer, then stop."""
    print(json.dumps({"asked": kind == "ask", "about": sorted(set(NAMED)) if kind == "ask" else []}))
    sys.exit(0)


# ---------- the check after the step's side (fg/steps.py) ----------
class Yes:
    """What the owner said yes to in this step, worked out once, and only when a guard file changed."""

    def __init__(self, data, note, home=None):
        self.data, self.note, self.home, self._about = data or {}, note or {}, home, None

    def about(self):
        if self._about is None:
            self._about = self._work_out()
        return self._about

    def _work_out(self):
        if BREAK("steps_yes_scope"):                    # as before review 6: the note's own word keeps everything
            return [EVERYTHING] if self.note.get("asked") else []
        if not self.note.get("asked"):                 # the guard didn't ask (a note that says so only loses the yes)
            return []
        tool, ti = self.data.get("tool_name"), self.data.get("tool_input") or {}
        if tool in EDIT_TOOLS:
            fp = ti.get("file_path") or ti.get("notebook_path") or ""
            cwd = self.data.get("cwd") or ""
            return [os.path.normcase(os.path.abspath(fp if os.path.isabs(fp) else os.path.join(cwd, fp)))] if fp else []
        return reread(self.data, self.home)

    def covers(self, full):
        full = os.path.normcase(os.path.abspath(full))
        for a in self.about():
            if a == EVERYTHING or a == full or full.startswith(a.rstrip("\\/") + os.sep) or \
                    (any(c in a for c in "*?[") and fnmatch.fnmatch(full, a)):
                return True
        return False


def reread(data, home=None, timeout=20):
    """Run the guard again, read-only, on the step's own hook input: the files its box named ([] if it can't tell)."""
    guard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.py")
    argv = [sys.executable, guard, "--about"] + (["--home", home] if home else [])
    try:
        p = subprocess.run(argv, input=json.dumps(data), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        lines = [l for l in p.stdout.splitlines() if l.startswith("{")]
        got = json.loads(lines[-1]) if lines else {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        got = {}
    return [str(a) for a in got.get("about") or []] if got.get("asked") else []

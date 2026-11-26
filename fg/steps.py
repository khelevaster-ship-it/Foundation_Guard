"""FoundationGuard: the check after every step (AI-made, Claude, 2026-11-12; the owner's direction after review 4).

The guard before each step reads the command's words, and three rounds of outside review kept finding spellings it
misses (a folder in a variable, a patch, sed --in-place, ruby -e, PowerShell's [IO.File]). The owner, 12 Nov: check
what changed, not what was typed. After every step of an AI session this compares the guard files with the state they
were in before the step. A change stays when:
  - the kit's box asked about that file in that step (worked out again from the step's own input by fg/about.py, so a
    step can't write its own yes; a yes never keeps a git setting);
  - it only adds tests or moves a test, judged by what changed (or the asks are gathered for one sitting);
  - the kit's own gate recorded it (its records of what passed);
  - it came with a git checkout, pull or merge, and the commit that made the file so is older than the step.
Any other change is put back as it was before the step, the helper is told why, and the owner sees it in the catch
log and on the next upload's report. What was put back is kept in .git/foundationguard/put_back/, so nothing is
lost. A
change that was also committed in that step is held: the upload waits for the owner's yes (python fg/ownerok.py).
Git's own settings files are compared too, by their risky settings only (fg/gitsettings.py).

  python fg/steps.py            list the guard files that differ from the last accepted state
  python fg/steps.py --accept   the owner takes the guard files as they are now (the kit's box asks)
  python fg/steps.py --keep F   the owner's own change to F, put back by the kit, is copied back and taken (box asks)
  python fg/steps.py --after    run by the AI tool after each step (Claude Code's PostToolUse hook; install sets it)
Limits: a change made outside a step (the owner's editor, another program, a job left running) is judged at the next
step by its kind (fg/between.py): the owner's own files stay, the kit's records and switches are put back; a file over 5 MB can be checked but not put back; a program written to
rewrite the kit's own record of the accepted state can still get round it. The lock that holds is GitHub's.
"""
import hashlib, json, os, re, shutil, stat, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import gitsettings as GS
import about as AB
import tiers as T
import known as KN
import paths as P
import door as D

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BIG = 5_000_000            # bytes: a bigger guard file is checked but not kept for putting back
SLACK = 1.0                # seconds: a change stamped this close before the step began still counts (coarse clocks)
COPIES_FOR = 600           # seconds the list of the project's other copies is kept before it is looked up again
FRESH = 900                # seconds: a step another session began this recently may still be running
BG_MAX = 7200              # seconds: the longest a helper's background job is taken to run (Claude Code's own limit)


_GIT_DIRS = {}


def _home(cfg):
    """Where this check keeps its record and what it put back: inside the folder's own git folder
    (.git/foundationguard), so nothing of it shows in the project or can be committed by a "git add -A"."""
    root = cfg["_root"]
    if root not in _GIT_DIRS:
        p = _git(root, "rev-parse", "--absolute-git-dir")
        g = p.stdout.decode("utf-8", "replace").strip() if p and p.returncode == 0 else ""
        _GIT_DIRS[root] = os.path.join(g, "foundationguard") if g else os.path.join(root, cfg.get("state_dir") or ".foundationguard")
    return _GIT_DIRS[root]


def _dir(cfg):
    return os.path.join(_home(cfg), "steps")


def _sd(cfg):
    return _home(cfg)


def _own(rel, cfg):
    """The kit's own bookkeeping for this check (its record, its notes, what it put back): never judged by it, or it
    would put back its own record after every step. The guard before each step still asks before a command writes
    there."""
    sd = (cfg.get("state_dir") or ".foundationguard").strip("/")
    home = P.rel(_home(cfg), cfg["_root"]).replace("\\", "/").strip("/")
    mine = [sd + "/steps/", sd + "/put_back/", ".git/foundationguard/"]
    if home and not home.startswith(".."):
        mine.append(home + "/")
    return rel.startswith(tuple(mine))


def _git(root, *a, data=None):
    try:
        return subprocess.run(["git", *a], cwd=root, capture_output=True, input=data, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None


GIT_BUSY = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG")
BUSY_FOR = 3600


def git_busy(root):
    """The name of what git is partway through here (a rebase, merge, cherry-pick, revert or bisect), or "". The game's
    PC, 15 Nov: a rebase checks out older copies of files on the way, and the kit took them as edits and put a file
    back to one. While git is busy the kit waits and judges the files when it is done. Only for an hour: an old or
    planted marker doesn't keep the kit waiting, and the upload gate and GitHub's lock judge the result either way."""
    if BREAK("steps_git_busy"):
        return ""
    p = _git(root, "rev-parse", "--git-dir")
    if not p or p.returncode != 0:
        return ""
    gd = os.path.join(root, p.stdout.decode("utf-8", "replace").strip())
    for n in GIT_BUSY:
        f = os.path.join(gd, n)
        try:
            if time.time() - os.path.getmtime(f) < BUSY_FOR:
                return n
        except OSError:
            continue
    return ""


def blob_id(data):
    """The id git gives these bytes (git hash-object --no-filters), so a kept copy is found by it."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _head(root):
    p = _git(root, "rev-parse", "-q", "--verify", "HEAD")
    return p.stdout.decode("utf-8", "replace").strip() if p and p.returncode == 0 else ""


def _blob_at(root, rev, rel):
    p = _git(root, "rev-parse", "-q", "--verify", f"{rev}:{rel}")
    return p.stdout.decode("utf-8", "replace").strip() if p and p.returncode == 0 else None


def _as_git(root, rels, now):
    """{path: the id git would store for the file as it is now}: git's own filters applied (line endings under
    core.autocrlf, Git LFS's pointer), so it compares with a commit's copy. The raw id (now[path]["id"]) differs from
    it on Windows, where git writes a checked-out text file with CRLF and stores it with LF (CI, 12 Nov)."""
    out = {r: now[r]["id"] for r in rels if now[r].get("id")}
    todo = [r for r in out if not str(out[r]).startswith(("big:", "unreadable"))]
    if todo and not BREAK("steps_crlf"):
        p = _git(root, "hash-object", "--stdin-paths", data=("\n".join(todo) + "\n").encode())
        ids = p.stdout.decode("utf-8", "replace").split() if p and p.returncode == 0 else []
        if len(ids) == len(todo):
            out.update(zip(todo, ids))
    return out


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    for i in range(1 if BREAK("steps_replace_retry") else 40):   # the game's PC, 15 Nov: Windows refuses to replace a
        try:                                                      # file another check has open ("not compared this time")
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == (0 if BREAK("steps_replace_retry") else 39):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
            time.sleep(0.05)


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


GENERATED = re.compile(r"(^|/)(__pycache__|\.pytest_cache)/|\.py[co]$")


def _files(cfg):
    """The guard files of this folder now, as paths from its top: the ones the patterns name outright, git's own list of
    files (tracked, and new ones it doesn't ignore) in the folders the patterns name, and the kit's hooks in .git.
    Files Python and pytest make as they run (__pycache__, .pytest_cache) are not judged."""
    root, globs = cfg["_root"], C.guard_globs(cfg)
    out, dirs, inside_git, anywhere = set(), set(), set(), False
    for g in globs:
        g = g.replace("\\", "/")
        while g.startswith("./"):
            g = g[2:]
        cut = re.split(r"[*?\[]", g, maxsplit=1)[0]
        if cut == g:
            out.add(g)
        elif "/" not in cut:
            anywhere = True
        elif cut.startswith(".git/"):
            inside_git.add(cut.rsplit("/", 1)[0])
        else:
            dirs.add(cut.rsplit("/", 1)[0])
    if anywhere or dirs:
        p = _git(root, "ls-files", "-z", "-co", "--exclude-standard", *([] if anywhere else ["--"] + sorted(dirs)))
        if p and p.returncode == 0:
            out |= {r for r in p.stdout.decode("utf-8", "replace").split("\0") if r and P.matches(r, globs)}
        else:                                          # not a git folder: walk the named folders
            for d in sorted(dirs):
                inside_git.add(d)
    for d in sorted(inside_git):
        for here, subs, names in os.walk(os.path.join(root, d)):
            out |= {r for r in (P.rel(os.path.join(here, n), root) for n in names) if P.matches(r, globs)}
    return {r for r in out if not _own(r, cfg) and not GENERATED.search(r)}


def _entry(full):
    try:
        s = os.stat(full)
    except OSError:
        return {"id": None}
    if not stat.S_ISREG(s.st_mode):
        return {"id": None}
    if s.st_size > BIG:
        h = hashlib.sha1()
        with open(full, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return {"id": "big:" + h.hexdigest(), "mode": s.st_mode & 0o777}
    try:
        with open(full, "rb") as f:
            data = f.read()
    except OSError:
        return {"id": "unreadable"}
    return {"id": blob_id(data), "mode": s.st_mode & 0o777}


def snapshot(cfg, known=()):
    """{path: {"id": what it holds (None when absent), "mode"}} for every guard file now and every one on record."""
    root = cfg["_root"]
    return {r: _entry(os.path.join(root, r)) for r in sorted(_files(cfg) | set(known))}


def _keep(cfg, rels):
    """Keep a copy of each of these files where git keeps its own (no file in the project), so it can be put back."""
    small = [r for r in rels if os.path.isfile(os.path.join(cfg["_root"], r)) and os.path.getsize(os.path.join(cfg["_root"], r)) <= BIG]
    if small:
        _git(cfg["_root"], "hash-object", "-w", "--no-filters", "--stdin-paths", data="\n".join(small).encode() + b"\n")


def _state(cfg):
    return _read_json(os.path.join(_dir(cfg), "state.json"))


def _save(cfg, st):
    _write_json(os.path.join(_dir(cfg), "state.json"), st)


BASELINES = T.BASELINES        # the kit's records: fg/tiers.py (the owner's yes and the break-glass log among them)


def _a_record(rel, cfg):
    return T.is_record(rel, cfg) or BREAK("steps_records_only")


def passed(cfg):
    """The commit the gate passed, as its record says, but only when the record is as the kit last accepted it
    (outside review 6, finding 2: a bare write of the file, by a script that then pushes itself, made any commit
    "passed"). With no accepted record yet (before the first helper step), the file as it is."""
    root = cfg["_root"]
    rel = (cfg.get("state_dir") or ".foundationguard").strip("/") + "/passed_commit"
    full = os.path.join(root, rel)
    try:
        with open(full, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return ""
    st = _state(cfg)
    if BREAK("passed_record_door") or not st or not isinstance(st.get("files"), dict):
        return text
    return text if _entry(full).get("id") == (st["files"].get(rel) or {}).get("id") else ""


def recorded(cfg, paths):
    """The kit's own scripts call this right after writing one of their records (the gate's record of what passed, a
    first record, a ratchet that only tightens), so the check after the step takes it as theirs. Only those record
    files, as they wrote them: never a test, a setting, a hook or the kit's code."""
    st = _state(cfg)
    if not st or BREAK("steps_records"):
        return
    root = cfg["_root"]
    rels = [r for r in (P.rel(p, root) for p in paths) if _a_record(r, cfg) or T.gate_record(r, cfg)]
    _keep(cfg, rels)
    for r in rels:
        e = _entry(os.path.join(root, r))
        if e["id"]:
            st["files"][r] = e
        else:
            st["files"].pop(r, None)
    _save(cfg, st)


# ---------- before the step (called by fg/guard.py) ----------
def _key(data):
    k = data.get("tool_use_id")
    if k:
        return re.sub(r"[^\w.-]", "_", str(k))[:80]
    raw = json.dumps([data.get("tool_name"), data.get("tool_input")], sort_keys=True, default=str)
    return "t" + hashlib.sha1(raw.encode()).hexdigest()[:24]


def _start(cfg):
    """The accepted state is taken as the guard files are before the first step judged (install, or the first step).
    Then, and only then, the history there is is trusted (fg/known.py); a kit from before that does it at its first
    check after the update. The "seeded" mark stays in the record (and the step note's copy of it), so a list of
    trusted commits removed later is never filled again from the branches there are then."""
    st = _state(cfg)
    if st is None:
        now = snapshot(cfg)
        _keep(cfg, [r for r, e in now.items() if e["id"]])
        _seed(cfg)
        _save(cfg, {"files": {r: e for r, e in now.items() if e["id"]}, "checked": time.time(), "news": [], "seeded": True})
    elif not st.get("seeded") and isinstance(st.get("files"), dict):
        _seed(cfg)
        _save(cfg, dict(st, seeded=True))
    if _read_json(_gs_path(cfg)) is None:
        _write_json(_gs_path(cfg), GS.take(cfg["_root"]))


# ---------- git's own settings (fg/gitsettings.py; review 4, finding 13) ----------
def _gs_path(cfg):
    return os.path.join(_dir(cfg), "gitsettings.json")


def _gs_between(cfg, session, key):
    """A risky git setting changed since the last check, outside any helper step: the owner's (as for guard files)."""
    st = _read_json(_gs_path(cfg))
    if st is None or BREAK("gitconfig_check"):
        return
    diff = GS.differs(cfg["_root"], st)
    if not diff or BREAK("steps_between") or (_open_notes(cfg, session, key) and not BREAK("steps_background")):
        return
    for path, name, keys in diff:
        _gs_between_one(cfg, st, path, name, keys)
    _write_json(_gs_path(cfg), GS.take(cfg["_root"]))


def _gs_between_one(cfg, st, path, name, keys):
    """One settings file changed between steps: the hooks folder and included files are switches (review 6, F266) and
    are put back; the other risky settings are the owner's."""
    import catches as CL
    hooks = [] if BREAK("between_switches") else [k for k in keys if k in GS.SWITCH_KEYS]
    if hooks:
        old = st.get(path) or {"risky": [], "ok": True, "there": False}
        ok, kept = GS.put_back(cfg["_root"], path, old, hooks, os.path.join(_sd(cfg), "put_back"))
        label = f"git setting {', '.join(hooks)} in {name}"
        _gs_tell(cfg, label + " (changed between steps)", ok, kept, "between steps")
        said = label + " changed outside any helper step and was " + ("put back" if ok else "NOT put back")
        rec = _state(cfg)
        if rec:
            rec.setdefault("between_said", []).append(said)
            _save(cfg, rec)
    rest = [k for k in keys if k not in hooks]
    if rest:
        CL.log(cfg, "changed between steps", f"git setting {', '.join(rest)} in {name} changed while no helper "
               "step was running; the kit assumed it was you and kept it", "", "the check after every step")


def _gs_check(cfg, note, what):
    """After a step: a risky git setting changed without the owner's yes is put back. ([put back], [could not])."""
    st = _read_json(_gs_path(cfg))
    if st is None or BREAK("gitconfig_check"):
        return [], []
    unknown, root = [], cfg["_root"]
    diff = GS.differs(root, st, unknown)
    _gs_unknown(cfg, unknown, what)
    if not diff:
        if unknown:
            _write_json(_gs_path(cfg), GS.take(root))
        return [], []
    if note and note.get("asked") and BREAK("gitconfig_yes_scope"):   # before review 6: any yes kept git settings too
        _write_json(_gs_path(cfg), GS.take(root))
        return [], []
    back, fail = [], []
    for path, name, keys in diff:
        old = st.get(path) or {"risky": [], "ok": True, "there": False}
        ok, kept = GS.put_back(root, path, old, keys, os.path.join(_sd(cfg), "put_back"))
        label = f"git setting {', '.join(keys)} in {name}"
        (back if ok else fail).append(label)
        _gs_tell(cfg, label, ok, kept, what)
    _write_json(_gs_path(cfg), GS.take(root))         # as for guard files: what couldn't be put back is told once
    return back, fail


def _gs_unknown(cfg, unknown, what):
    """Review 6, finding 5 (F275): a git setting the kit doesn't know changed in a step. Reported, never put back (Git
    LFS, an editor or a credential manager write their own keys in ordinary steps)."""
    import catches as CL
    said = "a git setting the kit doesn't know changed in a step (left as it is)"
    for name, keys in unknown:
        label = f"git setting {', '.join(keys)} in {name}"
        CL.log(cfg, "reported", f"{label} changed in a step ({what}); the kit doesn't know this setting, so it left it "
               "and tells the owner", what, "the check after every step")
        st = _state(cfg)
        if st:
            st.setdefault("news", []).append({"when": time.strftime("%Y-%m-%d %H:%M"), "what": said, "file": label})
            _save(cfg, st)


def _gs_tell(cfg, label, ok, kept, what):
    """The catch log and the next upload's report get what the check did to a git setting."""
    import catches as CL
    done = "put back" if ok else "could not put back"
    why = f"{label} changed without the owner's yes in a step ({what}); {done}"
    if kept:
        why += f" (the changed file is kept in {kept})"
    CL.log(cfg, "put back" if ok else "not put back", why, what, "the check after every step")
    st = _state(cfg)
    if st:
        st.setdefault("news", []).append({"when": time.strftime("%Y-%m-%d %H:%M"), "what": done, "file": label, "kept": ""})
        _save(cfg, st)


def _bg(data):
    """Seconds this step's command may go on running after the step ends (a background job), or 0."""
    ti = data.get("tool_input") or {}
    if not (data.get("tool_name") == "Monitor" or ti.get("run_in_background") or ti.get("persistent")):
        return 0
    try:
        t = float(ti.get("timeout_ms") or ti.get("timeout") or 0) / 1000
    except (TypeError, ValueError):
        t = 0
    return min(BG_MAX, t) if t > 0 and not ti.get("persistent") else BG_MAX


def _open_notes(cfg, session, key=None):
    """The notes of steps that may still be running in this folder: another session's step begun in the last 15
    minutes, and any helper's background job inside its time. A note of this session's own foreground step that is
    still here is one that never ran (a No in the box), so it doesn't count."""
    d, now, out = os.path.join(_dir(cfg), "pending"), time.time(), []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for n in names:
        note = None if (key and n == key + ".json") else _read_json(os.path.join(d, n))
        if not isinstance(note, dict):
            continue
        job = (note.get("until") or 0) > now and BREAK("steps_bg_timer")    # review 6: no more job timer (F268)
        if job or (note.get("session") != session and now - (note.get("start") or 0) < FRESH):
            out.append(note)
    return out


def _between(cfg, session, key):
    """At the start of a step: a guard file that changed since the last check changed outside any helper step. It is
    judged by its kind (fg/between.py): the kit's records and switches are put back, the owner's own files stay (held
    for the owner's yes when more than new tests). Not while another session's step may still be running: then the
    check after this step judges it like any change made in a step."""
    st = _state(cfg)
    if not st or not isinstance(st.get("files"), dict) or git_busy(cfg["_root"]):
        return
    now = snapshot(cfg, st["files"])
    changed = [r for r in now if now[r].get("id") != (st["files"].get(r) or {}).get("id")]
    if not changed or BREAK("steps_between"):
        return
    new = [r for r in changed if newly_covered(cfg["_root"], r, st["files"], now, st.get("checked") or 0)]
    for r in new:                                      # the guard list grew: taken as it is, never put back
        _keep(cfg, [r]); st["files"][r] = now[r]; _newly_told(cfg, r, "")
    changed = [r for r in changed if r not in new]
    if not changed:
        _save(cfg, st)
        return
    if _open_notes(cfg, session, key) and not BREAK("steps_background"):
        return
    import between as BW
    BW.judge(cfg, st, now, changed, sys.modules[__name__])
    st["news"] = st["news"][-50:]
    st["checked"] = time.time()
    _save(cfg, st)


def between_words(cfg):
    """What the check between steps put back since the last step ended, for the helper and the owner (once)."""
    st = _state(cfg)
    said = (st or {}).pop("between_said", None)
    if not said:
        return ""
    _save(cfg, st)
    return ("FoundationGuard: PUT BACK BETWEEN STEPS: " + "; ".join(said[:5]) + ". What was there is kept in "
            ".git/foundationguard/put_back/. If the owner made the change, the owner keeps it with "
            "python fg/steps.py --keep <file> (the kit's box asks), or tells the helper, who makes it with the editing "
            "tool, which asks the owner.")


def between_first(cfg, data):
    """Outside review 6 (F263): before the guard reads its own on/off switch, a switch written between steps is judged,
    so a script's delayed `"guard": "off"` can't silence the guard for the next step."""
    if BREAK("guard_part_settled") or BREAK("steps_check"):
        return
    try:
        _between(cfg, str(data.get("session_id") or ""), _key(data))
    except Exception:
        pass


def before(cfg, data, asked=False, free=(), deadline=None, loud=(), gathered=()):
    """At the start of a step (called by fg/guard.py): take what changed since the last check as the owner's, then
    leave the note the check after the step reads: when it began, where HEAD was, whether the kit's box asked, which
    guard files a free rule let through, the session, and how long a background job may run."""
    if BREAK("steps_check"):
        return
    d = os.path.join(_dir(cfg), "pending")
    try:
        key, session = _key(data), str(data.get("session_id") or "")
        looked, roots = True, {}
        turn = _turn(cfg)
        for n, c in enumerate([cfg] + turn["order"]):
            late = bool(deadline and time.time() > deadline)
            if n and (late or _rk(c) in turn["slow"]) and not BREAK("copies_turn"):
                # the game's PC, 19 Nov: twelve copies and a fresh scratch worktree took the check at the start of
                # every step past the guard's time limit, so every step was refused until the owner stepped in. A
                # copy there is no time for is left for the next step, which starts with it; one the check never
                # came back from is left out for an hour.
                roots[_rk(c)] = {"head": _head(c["_root"])} if not late else {}
                turn["left"].append(_rk(c)); looked = False
                continue
            if n:
                _turn_mark(cfg, turn, _rk(c))
            _start(c)
            roots[_rk(c)] = {"head": _head(c["_root"])}
            if BREAK("steps_seen"):
                roots[_rk(c)]["tips"] = _tips(c["_root"])
            if deadline and time.time() > deadline:    # never let the guard run past its own time limit
                looked = False
                continue
            _between(c, session, key)
            _gs_between(c, session, key)
            if not BREAK("steps_record_missing"):          # a second copy of the record, in case a step removes it
                roots[_rk(c)].update(_record_copy(c))
            _note_head(c)
        _turn_mark(cfg, turn, None)
        os.makedirs(d, exist_ok=True)
        for n in os.listdir(d):                        # notes of steps that never ran (a No in a box) are dropped
            if time.time() - os.path.getmtime(os.path.join(d, n)) > 86400:
                os.remove(os.path.join(d, n))
        start, bg = time.time(), _bg(data)
        _write_json(os.path.join(d, key + ".json"),
                    {"start": start, "roots": roots, "asked": bool(asked), "session": session, "data": _asked_data(data, asked),
                     "until": start + bg if bg else 0, "looked": looked,
                     "free": sorted({os.path.normcase(os.path.abspath(f)) for f in free}), "loud": list(loud),
                     "gathered": list(gathered)})
    except Exception:                                  # never in the way of the guard's own answer
        pass


def _asked_data(data, asked):
    """The step's own input, kept only when the box asked, so a yes still counts if the check after the step never runs
    (the game's PC, 13 Nov: a session started with older hooks never ran it, and a yes'd edit was put back)."""
    if not asked or BREAK("steps_yes_kept"):
        return None
    return {k: data.get(k) for k in ("tool_name", "tool_input", "cwd", "session_id", "tool_use_id")}


def yes_of_a_step(cfg, full):
    """A recent step whose box the owner answered yes, whose check after never ran, and whose yes covers this file."""
    return any(y.covers(full) for y in step_yeses(cfg))


def step_yeses(cfg):
    """The owner's yes in the kit's box for each of the last three steps whose check after hasn't run (the step running
    now among them)."""
    import about as AB
    d = os.path.join(_dir(cfg), "pending")
    try:
        notes = [_read_json(os.path.join(d, n)) for n in sorted(os.listdir(d), reverse=True)]
    except OSError:
        return []
    asked = [n for n in notes if isinstance(n, dict) and n.get("data") and time.time() - (n.get("start") or 0) < 86400]
    return [AB.Yes(n["data"], n) for n in asked[:3]]


def _seed(cfg):
    """The kit's first install (or its first check after an update from before this list): trust the history there
    is, unless another copy sharing this git folder (a worktree) already did, so a new worktree never fills a removed
    list again (Fable's re-read, 13 Nov)."""
    root = cfg["_root"]
    mine = KN._path(root)
    seeded = [(_state(c) or {}).get("seeded") or BREAK("known_upgrade_seed") for c in _copies(cfg) if KN._path(c["_root"]) == mine]
    if BREAK("known_worktree_seed") or not any(seeded):
        KN.seed(root)


def _record_copy(cfg):
    st = _state(cfg) or {}
    return {"files": st.get("files"), "seeded": st.get("seeded")}


def _take(cfg, data):
    """This step's note. A background job's note stays (marked as run) until its time is up, so a change it makes
    later is judged, not taken as the owner's."""
    p = os.path.join(_dir(cfg), "pending", _key(data) + ".json")
    note = _read_json(p)
    try:
        if isinstance(note, dict) and (note.get("until") or 0) > time.time() and BREAK("steps_bg_timer"):
            _write_json(p, dict(note, ran=True))
        else:
            os.remove(p)
    except OSError:
        pass
    return note if isinstance(note, dict) else None


# ---------- after the step ----------
def _rk(cfg):
    return os.path.normcase(os.path.abspath(cfg["_root"]))


def _tips(root):
    """Every commit a branch, tag or remote-tracking name points at now, and HEAD: the history that already exists."""
    p = _git(root, "for-each-ref", "--format=%(objectname)")
    out = set(p.stdout.decode("utf-8", "replace").split()) if p and p.returncode == 0 else set()
    return sorted(out | {_head(root)} - {""})[:5000]


def _with_git(root, rels, now, note):
    """The changed files a git checkout, switch, pull, merge or rebase in this step brought, and nothing else: HEAD
    moved and the kit trusts what it brought. When the new HEAD is inside a commit the kit trusts (fg/known.py: the
    history at install, a commit that was HEAD while every guard file was as it has it, a remote branch tip git
    ls-remote confirmed), every changed file that is as the new HEAD has it, a removal among them. Otherwise only a
    file exactly as a remote branch tip has it. When a branch was made says nothing (outside review 6, finding 3), and
    no single old version is trusted on its own (Claude Fable's review of the fix, 13 Nov)."""
    was = (note or {}).get("roots", {}).get(os.path.normcase(os.path.abspath(root))) or {}
    head = _head(root)
    if not (head and was.get("head") and head != was["head"]):
        return _at_uploaded_head(root, head, rels, now)
    gid = _as_git(root, rels, now)
    cand = [r for r in rels if r in gid and _blob_at(root, head, r) == gid[r]]
    tips = _remote_tips(root)
    if BREAK("steps_seen"):                            # before review 6: every branch that existed when the step began
        old = was.get("tips") or [was["head"]]
        return set(cand) if KN.contains(root, head, old) else _as_at(root, cand, gid, old + tips)
    sure = _here(root, KN.trusted(root) + tips)
    KN.trust(root, _here(root, tips))                  # confirmed by the remote once: trusted for good
    if not KN.contains(root, head, sure):
        return _as_at(root, cand, gid, tips + (sure if BREAK("steps_one_version") else []))
    gone = [] if BREAK("steps_git_absent") else [r for r in rels if not now[r].get("id") and not _blob_at(root, head, r)]
    return set(cand) | set(gone)


def _at_uploaded_head(root, head, rels, now):
    """The game's PC, 23 Nov 05:19 UTC: the owner moved the night copy onto the uploaded commit by hand while a helper's
    job was running, so no step moved its HEAD, and the check after put a file back that the commit holds. With HEAD
    exactly a branch tip the remote confirms, a file exactly as HEAD has it is kept: that version went up with the
    owner's yes."""
    if BREAK("tip_without_move") or not head:
        return set()
    if head not in _remote_tips(root):
        return set()
    gid = _as_git(root, rels, now)
    return {r for r in rels if r in gid and _blob_at(root, head, r) == gid[r]}


def _note_head(cfg, fail=(), remote=False):
    """F269: HEAD is trusted when every guard file on disk is exactly as it has it, and none it has is missing, read
    from the files and HEAD's own tree, never git's index (Fable's re-read, 13 Nov: skip-worktree and assume-unchanged
    make `git diff` look away). Never after a step whose change could not be put back, nor while a held change is at
    HEAD. A HEAD already trusted costs one look; the remote is asked only after a step (remote=True)."""
    root = cfg["_root"]
    _list_again(cfg)
    if remote:
        _note_remote(cfg)
    head = _head(root)
    if fail or not head or BREAK("steps_seen") or KN.contains(root, head, _here(root, KN.trusted(root))):
        return
    blobs = _tree(root, head)
    if blobs is not None and _as_head(cfg, blobs) and not _held_at(cfg, blobs):
        KN.trust(root, [head])


def _list_again(cfg):
    """A list of trusted commits missing or spoilt is made again at once, empty, and the catch log says so (F282)."""
    root = cfg["_root"]
    if KN.load(root) is None and KN.trust(root, []) is False and not BREAK("known_reseed"):
        import catches as CL
        CL.log(cfg, "record missing", "the kit's list of trusted commits (.git/foundationguard/seen.json) was missing or "
               "spoilt; it was made again, holding only the commits noted from now on", "", "the check after every step")


def _tree(root, head):
    """{path: blob id} of every file in this commit, or None."""
    p = _git(root, "ls-tree", "-r", "-z", "--full-tree", head)
    if not p or p.returncode != 0:
        return None
    out = {}
    for line in p.stdout.decode("utf-8", "replace").split("\0"):
        meta, _, path = line.partition("\t")
        if path and meta.split(" ")[1:2] == ["blob"]:
            out[path] = meta.split(" ")[2]
    return out


def _as_head(cfg, blobs):
    """Is every guard file on disk exactly as this tree has it, and every guard file it has on disk? (A record of the
    kit's own, and git's own folder, which no commit holds, aside.)"""
    root, globs = cfg["_root"], C.guard_globs(cfg)
    theirs = {r for r in blobs if P.matches(r, globs) and not _own(r, cfg) and not GENERATED.search(r)}
    rels = sorted(_files(cfg) | theirs)
    now = {r: _entry(os.path.join(root, r)) for r in rels}
    gid = _big_ids(root, _as_git(root, rels, now))
    if BREAK("steps_head_index"):                      # before Fable's re-read: git's own diff, which reads the index
        p = _git(root, "diff", "--name-only", "-z", "HEAD")
        return bool(p and p.returncode == 0) and not (set(p.stdout.decode("utf-8", "replace").split("\0")) & set(rels))
    return all(gid.get(r) == blobs.get(r) for r in rels
               if r in blobs or not (_a_record(r, cfg) or r.startswith(".git/")))


def _big_ids(root, gid):
    """A guard file over BIG has its own id in the record; for the comparison with a commit, git's own (once per new
    HEAD), or no HEAD would ever be noted in a project that has one."""
    big = sorted(r for r in gid if str(gid[r]).startswith("big:"))
    p = _git(root, "hash-object", "--stdin-paths", data=("\n".join(big) + "\n").encode()) if big and not BREAK("steps_big_noted") else None
    ids = p.stdout.decode("utf-8", "replace").split() if p and p.returncode == 0 else []
    return dict(gid, **dict(zip(big, ids))) if len(ids) == len(big) else gid


def _held_at(cfg, blobs):
    held = {} if BREAK("steps_held_noted") else _read_json(os.path.join(_dir(cfg), "held.json"), {}) or {}
    return any(blobs.get(r) == g or (g == "deleted" and r not in blobs) for r, g in held.items())


def _note_remote(cfg):
    """When this copy's remote-tracking branches moved (a fetch or pull), the remote's tips that git ls-remote
    confirms are trusted for good, so a merge of a fetched branch the remote has since moved on from still stays."""
    root = cfg["_root"]
    p = _git(root, "for-each-ref", "--format=%(objectname)", "refs/remotes")
    st = _state(cfg)
    if BREAK("steps_remote_noted") or not p or p.returncode != 0 or not isinstance(st, dict):
        return
    now = hashlib.sha1(p.stdout).hexdigest()
    if st.get("remotes") != now:
        KN.trust(root, _here(root, _remote_tips(root)))
        _save(cfg, dict(st, remotes=now))


def _remote_tips(root):
    try:
        import ownerok as OK
        return list((OK._remote_heads(root) or {}).values())
    except Exception:
        return []


def _as_at(root, cand, gid, tips):
    """Those of these files that are, exactly, as one of these commits has them."""
    p = _git(root, "cat-file", "--batch-check=%(objectname)", data=("\n".join(f"{t}:{r}" for r in cand for t in tips) + "\n").encode())
    if not tips or not p or p.returncode != 0:
        return set()
    got = p.stdout.decode("utf-8", "replace").splitlines()
    return {r for k, r in enumerate(cand) if gid[r] in got[k * len(tips):(k + 1) * len(tips)]}


def _here(root, commits):
    """The commits of these that this copy has (a remote branch not fetched yet is not)."""
    if not commits:
        return []
    p = _git(root, "cat-file", "--batch-check=%(objectname) %(objecttype)", data=("\n".join(commits) + "\n").encode())
    got = p.stdout.decode("utf-8", "replace").split("\n") if p and p.returncode == 0 else []
    return [g.split()[0] for g in got if g.endswith(" commit")]


def github_copy(cfg, rels, now):
    """Team mode (the team plan, 2.7): the changed guard files exactly as GitHub has them, which are never judged, asked
    about or put back (a pull, a merge, a checkout of a teammate's branch, a kit update). The remote's own answer (git
    ls-remote), never this copy's record of it. A switch or a kit record counts only as main has it, so a helper can't
    launder a switch through a branch of its own; the owner's own files count as any branch on GitHub has them."""
    if BREAK("github_copy_kept") or not cfg.get("team") or not rels:
        return set()
    import ownerok as OK
    root = cfg["_root"]
    heads = OK._remote_heads(root) or {}
    main = next((b for b in (cfg.get("protected_branches") or ["main"]) if b in heads), None)
    mains = _here(root, [heads[main]] if main else [])
    every = _here(root, list(heads.values()))
    gid = _as_git(root, rels, now)
    own = [r for r in rels if r in gid and T.kind(r, cfg) == "own"]
    rest = [r for r in rels if r in gid and r not in own]
    if BREAK("switch_needs_main_history"):
        own, rest = own + rest, []
    return _as_at(root, own, gid, every) | _as_at(root, rest, gid, mains)


def newly_covered(root, rel, base, now, since, head=None):
    """A file the kit's record has never held that was already there before this step: the guard list grew to cover it
    (the game's PC, 16 Nov: four project files newly protected were "put back" to not being there, so deleted, in ten
    copies of the project). It is in the commit the step began at, or it was last written before the step began."""
    if BREAK("steps_newly_covered") or rel in base or not now.get(rel, {}).get("id"):
        return False
    blob = _blob_at(root, head or "HEAD", rel)
    if blob and _as_git(root, [rel], now).get(rel) == blob:
        return True                                    # exactly as committed
    try:
        return bool(since) and os.path.getmtime(os.path.join(root, rel)) < since - 1
    except OSError:
        return False


def _newly_told(cfg, rel, what):
    import catches as CL
    CL.log(cfg, "newly protected", f"{rel} is now covered by the guard list; taken as it is", what, "the check after every step")


def _put_back(cfg, rel, old, now):
    """Put the file back as it was before the step. (done?, where what was there is kept)."""
    root, full, kept = cfg["_root"], os.path.join(cfg["_root"], rel), None
    try:
        if now.get("id"):
            kept = os.path.join(_sd(cfg), "put_back", time.strftime("%Y%m%d-%H%M%S") + "_" + rel.replace("/", "__"))
            os.makedirs(os.path.dirname(kept), exist_ok=True)
            shutil.copy2(full, kept)
        if not (old or {}).get("id"):
            if _blob_at(root, "HEAD", rel) and not BREAK("put_back_committed"):
                return False, kept                     # never delete a file the last commit holds (the game's PC, 16 Nov)
            os.remove(full)                            # it wasn't there before the step
            return True, kept
        if str(old["id"]).startswith(("big:", "unreadable")):
            return False, kept
        p = _git(root, "cat-file", "blob", old["id"])
        if not p or p.returncode != 0:
            return False, kept
        os.makedirs(os.path.dirname(full) or root, exist_ok=True)
        with open(full, "wb") as f:
            f.write(p.stdout)
        if old.get("mode") and os.name != "nt":
            os.chmod(full, old["mode"])
        return True, kept
    except OSError:
        return False, kept


SLOW_FOR = 3600            # seconds a copy the check never came back from is left out


def _turn(cfg):
    """The other copies in the order to check them this step: those left over last time first. A copy the last
    check was in when it was stopped (its mark is still there) is left out for an hour, and written to the catch log."""
    path = os.path.join(_dir(cfg), "copies_turn.json")
    st = _read_json(path, {}) or {}
    slow = {k: t for k, t in (st.get("slow") or {}).items() if time.time() - t < SLOW_FOR}
    doing, at = (st.get("doing") or [None, 0])[:2] if isinstance(st.get("doing"), list) else (None, 0)
    busy = doing if doing and time.time() - at < 30 else None      # another session's check may be in it right now
    if doing and not busy and doing not in slow:
        slow[doing] = time.time()
        try:
            import catches as CL
            CL.log(cfg, "a copy left out", f"the check at the start of a step did not come back from {doing} "
                   "(another copy of this project) in time; it is left out for an hour", "", "the check after every step")
        except Exception:
            pass
    first = st.get("left") or []
    copies = _copies(cfg)
    order = sorted(copies, key=lambda c: first.index(_rk(c)) if _rk(c) in first else len(first))
    return {"path": path, "order": order, "slow": dict(slow, **({busy: 0} if busy else {})), "kept": slow, "left": []}


def _turn_mark(cfg, turn, doing):
    try:
        _write_json(turn["path"], {"slow": turn["kept"], "left": turn["left"], "doing": [doing, time.time()] if doing else None})
    except OSError:
        pass


def _copies(cfg):
    """The settings of each other copy of this project (worktrees, checkouts beside it), looked up every 10 minutes."""
    st = _read_json(os.path.join(_dir(cfg), "copies.json"), {}) or {}
    if time.time() - st.get("time", 0) > COPIES_FOR:
        import copies as CP
        st = {"time": time.time(), "folders": CP.copies(cfg["_root"])}
        try:
            _write_json(os.path.join(_dir(cfg), "copies.json"), st)
        except OSError:
            pass
    out, own = [], _run_copies(cfg)
    for d in st.get("folders", []):
        if os.path.isdir(d) and os.path.normcase(os.path.realpath(d)) not in own:
            out.append(C.load(d) if os.path.exists(os.path.join(d, "foundationguard.json")) else C.load(d, cfg["_root"]))
    return out


def _run_copies(cfg):
    """The owner, 23 Nov: the nightly runs for hours in its own copy (C:\\MyGameNight2) and writes guard files there; a
    helper's step in the work copy checked that copy too, so a write landing during the step could be put back, and the
    PC stopped work all night. "run_copies" in foundationguard.json (folders, relative to the project or absolute) are
    left out of other copies' checks; a session working in such a folder still runs its own."""
    if BREAK("run_copies"):
        return set()
    out = set()
    for d in cfg.get("run_copies") or []:
        if isinstance(d, str) and d.strip():
            full = d if os.path.isabs(d) else os.path.join(cfg["_root"], d)
            out.add(os.path.normcase(os.path.realpath(full)))
    return out


def _blob_ids(data):
    """The git ids of these bytes as they are, with Windows line endings and with plain ones."""
    import hashlib
    flat = data.replace(b"\r\n", b"\n")
    return {hashlib.sha1(b"blob %d\0" % len(d) + d).hexdigest() for d in (data, flat, flat.replace(b"\n", b"\r\n"))}


def _box_yes_anywhere(cfg, rel, new):
    """The game's PC, 23 Nov 04:30 UTC: the owner allowed a BUILD_ORDER.md change in the box in the work copy; the night
    rehearsal checked out that commit (not uploaded yet) in the night copy, and the check after put the file back
    there. A version the owner allowed in the box in this copy or another is kept."""
    if BREAK("box_yes_copies"):
        return False
    ids = _blob_ids(new)
    try:
        books = [box_yes(cfg)] + [box_yes(c) for c in _copies(cfg)]
    except Exception:
        books = [box_yes(cfg)]
    return any(b.get(rel) in ids for b in books if isinstance(b, dict))


def _kept_anyway(cfg, rel, old, what):
    """A change kept although nothing asked: the owner's gathered asks, the AI tool's own permission rules, or spaces and
    line breaks only (a formatter)."""
    import catches as CL
    if gathered(cfg, rel):                             # the owner answers these at one sitting: the upload waits for it
        GATHERED_NOW.append(rel)
        CL.log(cfg, "gathered for the owner", f"{rel} changed in a step ({what}); it waits for the owner's yes "
               "before the upload (python fg/ownerok.py)", what, "the check after every step")
        return True
    was, new = _old_and_new(cfg, rel, old)
    if new is None:
        return False
    if _box_yes_anywhere(cfg, rel, new):
        CL.log(cfg, "allowed in the box", f"{rel} changed in a step ({what}) to a version the owner allowed in the kit's "
               "box (in this copy or another); kept", what, "the check after every step")
        return True
    if was is not None and _only_permission_rules(rel, was or b"{}", new):
        CL.log(cfg, "permission rules only", f"{rel} changed only in its allow, ask or deny rules in a step ({what}), as "
               "the AI tool's own \"don't ask again\" writes it; kept (the kit's hooks still run)", what, "the check after every step")
        return True
    import layout as LY
    if was and LY.only_layout(rel, was, new):
        CL.log(cfg, "layout only", f"{rel} changed only in spaces and line breaks in a step ({what}); kept",
               what, "the check after every step")
        return True
    return False


def _old_and_new(cfg, rel, old):
    """(the accepted bytes, b"" when the file wasn't there or None when they can't be had; the bytes now or None)."""
    new = None
    try:
        with open(os.path.join(cfg["_root"], rel), "rb") as f:
            new = f.read()
    except OSError:
        pass
    if not (old or {}).get("id"):
        return b"", new
    p = _git(cfg["_root"], "cat-file", "blob", old["id"])
    return (p.stdout if p and p.returncode == 0 else None), new


AI_SETTINGS = (".claude/settings.json", ".claude/settings.local.json")


def _only_permission_rules(rel, old, new):
    """The AI tool's settings changed only in its permissions' allow, ask or deny lists (review 6's fix plan, found on
    the way: Claude Code's own "don't ask again" writes there during a step). The kit's hooks run whatever those lists
    say; the hooks, the environment, disableAllHooks and the permission mode are still judged."""
    if rel not in AI_SETTINGS or BREAK("steps_permission_rules"):
        return False
    a, b = _json_or_none(old or b"{}"), _json_or_none(new)
    return a is not None and b is not None and _without_rules(a) == _without_rules(b)


def _json_or_none(raw):
    try:
        d = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return d if isinstance(d, dict) else None


def _without_rules(d):
    perms = d.get("permissions")
    if not isinstance(perms, dict):
        return d
    rest = {k: v for k, v in perms.items() if k not in ("allow", "ask", "deny")}
    out = {k: v for k, v in d.items() if k != "permissions"}
    if rest:
        out["permissions"] = rest
    return out


def gathered(cfg, rel):
    """With the asks gathered, a change to one of the owner's own guard files (tests, check scripts, lists) waits for the
    owner's yes before any upload, however it was made (fg/ownerok.py measures it from the remote), and the gate won't
    pass with it uncommitted; so it stays. The kit, its settings and hooks are never gathered."""
    if BREAK("steps_gathered"):
        return False
    import adds as AD
    return AD.gathering(cfg, rel)


def _accepted(cfg, note, what):
    st = _state(cfg)
    return st if st and isinstance(st.get("files"), dict) else _record_from_note(cfg, note, what)


def _record_from_note(cfg, note, what):
    """The kit's record of the accepted files is gone or unreadable after a step (outside review 5, Claude Fable, 13
    Nov: the check crashed there, and the next step took the changed files as accepted). The step's own note holds a
    copy of the record as it was when the step began, so the step is judged against that, and the catch log says so."""
    files = ((note or {}).get("roots", {}).get(_rk(cfg)) or {}).get("files")
    if not isinstance(files, dict):
        return None
    import catches as CL
    CL.log(cfg, "record missing", "the kit's record of the accepted guard files was removed or spoilt in a step "
           f"({what}); the step was judged against the copy taken when it began", what, "the check after every step")
    seeded = ((note or {}).get("roots", {}).get(_rk(cfg)) or {}).get("seeded")
    return {"files": files, "checked": time.time(), "seeded": seeded, "news": [{"when": time.strftime("%Y-%m-%d %H:%M"),
            "what": "the kit's record was removed in a step", "file": ".git/foundationguard/steps/state.json", "kept": ""}]}


def _check(cfg, note, what, yes=None):
    """Judge one folder's guard files after a step. Returns (put back, could not put back, held)."""
    import catches as CL
    st = _accepted(cfg, note, what)
    now = snapshot(cfg, (st or {}).get("files", {}))
    if not st or not isinstance(st.get("files"), dict):
        _keep(cfg, [r for r, e in now.items() if e["id"]])
        _seed(cfg)
        _save(cfg, {"files": {r: e for r, e in now.items() if e["id"]}, "checked": time.time(), "news": [], "seeded": True})
        return [], [], []
    base, root = st["files"], cfg["_root"]
    if git_busy(root):                                 # judged when git is done, against the last accepted copies
        return [], [], []
    changed = [r for r in now if (now[r].get("id") != (base.get(r) or {}).get("id"))]
    back, fail, held, keep = [], [], [], []
    if changed:
        head, was = _head(root), (note or {}).get("roots", {}).get(_rk(cfg)) or {}
        moved = bool(head and was.get("head") and head != was["head"])
        git = set() if BREAK("steps_git") else _with_git(root, changed, now, note)
        git |= github_copy(cfg, [r for r in changed if r not in git], now)
        since = (note or {}).get("start") or st.get("checked") or 0
        for r in changed:
            full = os.path.normcase(os.path.abspath(os.path.join(root, r)))
            if newly_covered(root, r, base, now, since, was.get("head")):
                keep.append(r)                         # the guard list grew: taken as it is (the game's PC, 16 Nov)
                _newly_told(cfg, r, what)
            elif _yes(cfg, yes, note, r, full, base, now) and not BREAK("steps_keep"):
                keep.append(r)
            elif r in git:
                keep.append(r)
            elif _kept_anyway(cfg, r, base.get(r), what):
                keep.append(r)
            elif D.blesses(cfg, r, base.get(r), now[r]) and not BREAK("door_after"):    # the owner's own kit command
                keep.append(r)
            elif T.gate_record(r, cfg) and not BREAK("gate_record_after"):   # the gate's own pass file: taken in a step
                keep.append(r)                         # as between steps (the game's PC, 14 Nov: a running gate rewrote it)
            else:
                gid = _as_git(root, [r], now).get(r) if moved and now[r].get("id") else None   # before it is put back
                ok, kept = _put_back(cfg, r, base.get(r), now[r])
                (back if ok else fail).append((r, kept))
                if gid and _blob_at(root, head, r) == gid and not BREAK("steps_held"):
                    held.append(r)
                    hp = os.path.join(_dir(cfg), "held.json")
                    h = _read_json(hp, {}) or {}
                    h[r] = gid
                    _write_json(hp, h)
        take = keep + [r for r, _ in fail]
        _keep(cfg, [r for r in take if now[r].get("id")])
        for r in take:
            if now[r].get("id"):
                base[r] = now[r]
            else:
                base.pop(r, None)
    st["checked"] = time.time()
    news = st.setdefault("news", [])
    for r, kept in back:
        why = f"{r} changed without the owner's yes in a step ({what}); put back as it was" + (f", the changed copy kept in {P.rel(kept, root)}" if kept else "")
        CL.log(cfg, "put back", why, what, "the check after every step")
        news.append({"when": time.strftime("%Y-%m-%d %H:%M"), "what": "put back", "file": r, "kept": P.rel(kept, root) if kept else ""})
    for r, kept in fail:
        CL.log(cfg, "not put back", f"{r} changed without the owner's yes in a step ({what}) and could not be put back", what,
               "the check after every step")
        news.append({"when": time.strftime("%Y-%m-%d %H:%M"), "what": "could not put back", "file": r, "kept": ""})
    st["news"] = news[-50:]
    _save(cfg, st)
    _note_head(cfg, fail, remote=True)
    return back, fail, held


def after(cfg, data, home=None):
    """The check after one step: the words for the helper (and the owner), or "" when nothing was put back."""
    if BREAK("steps_check"):
        return ""
    note = _take(cfg, data)
    what = str(data.get("tool_name") or "a tool") + ": " + str((data.get("tool_input") or {}).get("command")
                                                             or (data.get("tool_input") or {}).get("file_path") or "")[:300]
    yes = AB.Yes(data, note, home)
    cfg, back, fail = _settled(cfg, note, what, yes, home)
    if C.part(cfg, "guard") == "off":                  # the accepted settings say so, not the file the step wrote
        return words(back, fail, [])
    held, gback, gfail = [], [], []
    seen = set()
    for c in [cfg] + _copies(cfg):
        if os.path.normcase(os.path.abspath(c["_root"])) in seen:
            continue
        seen.add(os.path.normcase(os.path.abspath(c["_root"])))
        name = (lambda r: r) if c is cfg else (lambda r, c=c: os.path.join(c["_root"], r).replace("\\", "/"))
        if c is not cfg:
            c, sb, sf = _settled(c, note, what, yes, home)
            back += [name(r) for r in sb]; fail += [name(r) for r in sf]
        b, f, h = _check(c, note, what, yes)
        gb, gf = _gs_check(c, note, what)
        gback += [x for x in gb if x not in gback]; gfail += [x for x in gf if x not in gfail]
        back += [name(r) for r, _ in b]; fail += [name(r) for r, _ in f]; held += [name(r) for r in h]
    return " ".join(x for x in (_loud(note), _two_kits(cfg, data), between_words(cfg), words(back, fail, held),
                                GS.words(gback, gfail), gathered_words(note)) if x)


GATHERED_NOW = []


def gathered_words(note):
    """The game's PC, 21 Nov 11:43 UTC: a git apply that changed two guard files was rightly gathered for the owner's yes
    at the upload, but the step's output said nothing, so the helper told the owner a box was up. Now it says so."""
    if BREAK("gathered_said"):
        return ""
    names = []
    for n in list((note or {}).get("gathered") or []) + GATHERED_NOW:
        n = str(n).replace("\\", "/")
        if n not in names:
            names.append(n)
    if not names:
        return ""
    return ("FoundationGuard: NO BOX NOW: " + ", ".join(names[:6]) + (f" and {len(names) - 6} more" if len(names) > 6 else "") +
            (" changed" if len(names) > 1 else " changed") + " and stays; the owner's yes for it is asked at the upload "
            "(python fg/ownerok.py lists it). No box is open: don't tell the owner one is.")


def _loud(note):
    """Plan 2 PR 7: with GitHub's lock guarding the project, a step that weakens a check is said in chat at once."""
    said = list((note or {}).get("loud") or [])
    if not said:
        return ""
    return ("FoundationGuard: THIS STEP WEAKENS A SAFETY CHECK: " + "; ".join(said[:4]) +
            (f" and {len(said) - 4} more" if len(said) > 4 else "") + ". It stays on disk, and nothing was put back. "
            "It waits for the owner's yes on GitHub, on their phone, before it can reach main. Tell the owner in plain "
            "words now. To let your other work merge first, put this change on its own branch.")


def _two_kits(cfg, data):
    """Once a session: another copy of the kit runs in it too (fg/copies.py, the game's PC 16 Nov)."""
    try:
        import copies as CP
        text = CP.two_kits_words([os.environ.get("CLAUDE_PROJECT_DIR"), data.get("cwd"), cfg["_root"]])
        if not text:
            return ""
        p, sid = os.path.join(_dir(cfg), "two_kits.json"), str(data.get("session_id") or "")
        told = _read_json(p, {}) or {}
        if told.get(sid):
            return ""
        told = {k: v for k, v in told.items() if time.time() - v < 7 * 86400}
        told[sid] = time.time()
        _write_json(p, told)
        return text
    except Exception:                                  # never in the way of the check itself
        return ""


SETTINGS = "foundationguard.json"


def _settled(cfg, note, what, yes, home=None):
    """Outside review 6, finding 1 (Grok, 13 Nov): a script switched the guard off in the kit's settings, and the check
    after the step, which read the file the step had just written, returned at once; with gather_asks set the same way a
    loosened test stayed. The step is judged by the accepted settings: a change to the settings file the owner's box
    didn't name is put back first, and the settings are read again. (cfg, [put back], [could not])."""
    if BREAK("steps_settings_first"):
        return cfg, [], []
    st = _state(cfg)
    files = (st or {}).get("files")
    if not isinstance(files, dict):                    # the record is gone: the copy the step's note took
        files = ((note or {}).get("roots", {}).get(_rk(cfg)) or {}).get("files")
    if not isinstance(files, dict):
        return cfg, [], []
    root, base = cfg["_root"], files.get(SETTINGS)
    now = _entry(os.path.join(root, SETTINGS))
    if now.get("id") == (base or {}).get("id") or yes.covers(os.path.join(root, SETTINGS)) or \
            (D.blesses(cfg, SETTINGS, base, now) and not BREAK("door_after")):
        return cfg, [], []
    if _pulled(root, now, note) or github_copy(cfg, [SETTINGS], {SETTINGS: now}):
        return C.load(root, home), [], []
    ok, kept = _put_back(cfg, SETTINGS, base, now)
    _settled_told(cfg, st, ok, kept, what)
    return C.load(root, home), [SETTINGS] if ok else [], [] if ok else [SETTINGS]


def _pulled(root, now, note):
    """The settings file as a checkout or pull in this step brought it, from history the kit trusts (F269)."""
    return not BREAK("steps_git") and bool(_with_git(root, [SETTINGS], {SETTINGS: now}, note))


def _settled_told(cfg, st, ok, kept, what):
    import catches as CL
    root, done = cfg["_root"], "put back" if ok else "could not put back"
    why = f"{SETTINGS} changed without the owner's yes in a step ({what}); {done} before the step was judged"
    CL.log(cfg, "put back" if ok else "not put back", why + (f", the changed copy kept in {P.rel(kept, root)}" if kept else ""),
           what, "the check after every step")
    if st:
        item = {"when": time.strftime("%Y-%m-%d %H:%M"), "what": done, "file": SETTINGS, "kept": P.rel(kept, root) if kept else ""}
        st.setdefault("news", []).append(item)
        _save(cfg, st)


def _yes(cfg, yes, note, rel, full, base, now):
    """Does this step's yes, or a free rule judged by what changed, keep this changed guard file?"""
    if (yes is not None and yes.covers(full)) or _overlapping_yes(cfg, rel, full, base):
        _box_yes(cfg, rel, now)
        return True
    if BREAK("steps_free_state"):                      # before review 6: the note's own list of free files
        return bool(note) and full in note.get("free", [])
    return _free_now(cfg, rel, base, now) or _github_holds(cfg, rel)


BOX_YES = "box_yes.json"


def _box_yes(cfg, rel, now):
    """The game's PC, 23 Nov: the owner said yes in the box to a BUILD_ORDER.md change, and with the reviewer lane on the
    upload listed it again for a yes. Each version of a file the owner's box let through is kept here."""
    if BREAK("box_yes_kept"):
        return
    v = (now.get(rel) or {}).get("id")
    if not v:
        return
    p = os.path.join(_home(cfg), BOX_YES)
    book = _read_json(p, {}) or {}
    book[rel] = v
    try:
        _write_json(p, book)
    except OSError:
        pass


def box_yes(cfg):
    """{file: the version the owner's box let through}."""
    try:
        return _read_json(os.path.join(_home(cfg), BOX_YES), {}) or {}
    except Exception:
        return {}


def _overlapping_yes(cfg, rel, full, base):
    """The game's PC, 22 Nov 21:52 UTC: the owner said yes to an edit of a guard file, and a helper's other step (a
    read-only check running beside it) ended first; its check after found the change and put it back, as that step had
    no yes. An editing step whose box the owner answered yes, whose own check hasn't run yet, keeps the file when the
    file is now exactly what that edit makes of the accepted copy. Anything else that step's file holds is judged as
    before."""
    if BREAK("steps_overlap"):
        return False
    try:
        yeses = [y for y in step_yeses(cfg) if y.data.get("tool_name") in AB.EDIT_TOOLS and y.covers(full)]
        if not yeses:
            return False
        import adds as AD
        old_id = (base.get(rel) or {}).get("id")
        if old_id and str(old_id).startswith(("big:", "unreadable")):
            return False
        p = _git(cfg["_root"], "cat-file", "blob", old_id) if old_id else None
        if old_id and (not p or p.returncode != 0):
            return False
        before = p.stdout.decode("utf-8") if p else ""
        now = open(full, "rb").read().decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    flat = lambda t: t.replace("\r\n", "\n")
    for y in yeses:
        after = AD.after_edit(y.data.get("tool_name"), y.data.get("tool_input") or {}, before)
        if after is not None and flat(after) == flat(now):
            return True
    return False


def _github_holds(cfg, rel):
    """Plan 2 PR 7: with GitHub's lock guarding the project (fg/lockmode.py), the owner's own files are never put back:
    GitHub holds the change for the owner's Approve. The kit's switches and records still are."""
    import tiers as T
    if BREAK("own_no_put_back") or T.kind(rel, cfg) != "own":
        return False
    try:
        import lockmode as LM
        return LM.on(cfg)
    except Exception:                                    # noqa: BLE001
        return False


def _free_now(cfg, rel, base, now):
    """Review 6, finding 4 (F272): new tests are free by what changed, not by a list the step could write. A change to a
    test file of the owner's own that only adds tests (or a test file not committed yet that holds tests), and a test
    moved or copied (the same content at a new path, and the old path gone only when it went to a new one)."""
    import adds as AD
    if not _owners_test(cfg, rel, AD):
        return False
    old, new = (base.get(rel) or {}).get("id"), (now.get(rel) or {}).get("id")
    if not new:                                        # removed: only as the old half of a move in this step
        return _moved_away(rel, old, base, now)
    full = os.path.join(cfg["_root"], rel)
    was = "" if not old or AD.uncommitted(cfg, rel, full) else _text_of(cfg["_root"], old)
    text = _read_text(full)
    return was is not None and text is not None and AD.only_adds(rel, was, text, cfg) is None


def _owners_test(cfg, rel, AD):
    return bool(cfg.get("helpers_add_tests", True)) and AD.is_test_file(rel, cfg) and AD.owners_own(cfg, rel)


def _moved_away(rel, old, base, now):
    """A removed test whose content is now at a path that wasn't there: the old half of a move."""
    if not old:
        return False
    return any(e.get("id") == old and not (base.get(r) or {}).get("id") for r, e in now.items() if r != rel)


def _text_of(root, blob):
    p = _git(root, "cat-file", "blob", str(blob))
    return p.stdout.decode("utf-8", "replace") if p and p.returncode == 0 else None


def _read_text(full):
    try:
        with open(full, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return None


# outside review 7: "don't try another way round" read as "give up", and an honest helper stopped for the night
ON_WITH = "Don't try another way round." if BREAK("steps_carry_on") else (
    "Don't look for another way round; if the owner is away, leave them a note (in HANDOFF.md if the project has one) "
    "and carry on with other work.")


def words(back, fail, held):
    out = []
    if back:
        out.append("FoundationGuard: PUT BACK: " + ", ".join(back) + (" was" if len(back) == 1 else " were") +
                   " changed without the owner's yes (in this step, or by a job an earlier step left running), so the kit put " + ("it" if len(back) == 1 else "them") +
                   " back as before the step (what was there is kept in .git/foundationguard/put_back/). A guard file changes "
                   "only through the kit's box: make the change with the editing tool (Edit or Write), which asks the "
                   "owner, or ask the owner. " + ON_WITH)
    if fail:
        out.append("FoundationGuard: NOT PUT BACK: " + ", ".join(fail) + " changed in this step without the owner's yes, "
                   "and the kit could not put it back (too big or locked). Stop and tell the owner.")
    if held:
        out.append("FoundationGuard: HELD: " + ", ".join(held) + " was also committed in this step, so the upload waits for "
                   "the owner's yes (python fg/ownerok.py lists it).")
    return " ".join(out)


def held(cfg):
    """{file: version} committed in a step without the owner's yes (fg/ownerok.py lists them for the owner)."""
    return {} if BREAK("steps_held") else (_read_json(os.path.join(_dir(cfg), "held.json"), {}) or {})


def cards(cfg):
    """A FOR YOU card on the upload's report for what the check after every step did since the last report."""
    st = _state(cfg)
    news = (st or {}).get("news") or []
    if not news:
        return []
    st["news"] = []
    _save(cfg, st)
    lines = [f"{n['when']} {n['what']}: {n['file']}" + (f" (kept in {n['kept']})" if n.get("kept") else "") for n in news]
    return [{"who": "you", "title": "The kit put back a guard file changed without your yes" if any(n["what"] == "put back" for n in news)
             else "A guard file changed outside any helper step",
             "happened": f"{len(news)} change(s) to guard files since the last report: " + "; ".join(lines[:3]) + (" and more" if len(lines) > 3 else "") + ".",
             "means": "A helper changed a test, a check or the kit's settings in a way the kit's box didn't ask you about, and "
                      "the kit put it back; or a guard file changed outside any helper step, which the kit took as yours.",
             "action": "If you didn't change it yourself, ask the helper what it was doing. Nothing more is needed: what was "
                       "put back is kept in .git/foundationguard/put_back/.",
             "evidence": lines}]


def _keep_own(cfg, st, rel):
    """Outside review 7: the owner's own change to one guard file, put back because it was made outside the kit's box,
    is copied back from the newest kept copy in put_back/ and that one file is accepted as it is then."""
    rel = rel.replace("\\", "/").strip("/")
    pb = os.path.join(_sd(cfg), "put_back")
    mine = sorted(n for n in (os.listdir(pb) if os.path.isdir(pb) else []) if n[16:] == rel.replace("/", "__"))
    if not mine or rel not in snapshot(cfg, st.get("files", {})):
        print(f"STEPS: no kept copy of {rel} in .git/foundationguard/put_back/; nothing was changed.")
        return 1
    full = os.path.join(cfg["_root"], rel)
    os.makedirs(os.path.dirname(full) or cfg["_root"], exist_ok=True)
    if not BREAK("steps_keep_copy"):
        shutil.copy2(os.path.join(pb, mine[-1]), full)
    now = snapshot(cfg, st.get("files", {}))
    if rel in now and now[rel].get("id"):
        _keep(cfg, [rel])
        st.setdefault("files", {})[rel] = now[rel]
        _save(cfg, st)
    print(f"STEPS: {rel} is back as it was changed ({mine[-1]}), and is now the accepted state for that file.")
    return 0


def main(argv):
    if "--after" in argv:
        try:
            data = json.load(sys.stdin)
        except ValueError:
            data = {}
        try:
            home = argv[argv.index("--home") + 1] if "--home" in argv[:-1] else None
            cfg = C.load(C.find_root(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()), home)
            text = after(cfg, data, home)
        except Exception as e:                           # the step already ran: say so loudly, never stop the session
            text = ""
            print(json.dumps({"systemMessage": "FoundationGuard: the check after this step failed (%s: %s); guard files "
                              "were not compared this time." % (type(e).__name__, str(e)[:200])}))
        if text:
            print(json.dumps({"decision": "block", "reason": text, "systemMessage": text}))
        return 0
    cfg = C.load()
    st = _state(cfg)
    if "--keep" in argv[:-1]:
        return _keep_own(cfg, st or {}, argv[argv.index("--keep") + 1])
    if "--accept" in argv:
        old = st or {}
        now = snapshot(cfg, old.get("files", {}))
        _keep(cfg, [r for r, e in now.items() if e["id"]])
        _save(cfg, {"files": {r: e for r, e in now.items() if e["id"]}, "checked": time.time(), "news": old.get("news", []),
                    "seeded": old.get("seeded")})
        _write_json(_gs_path(cfg), GS.take(cfg["_root"]))
        print(f"STEPS: the guard files as they are now are the accepted state ({sum(1 for e in now.values() if e['id'])} files).")
        return 0
    if not st:
        print("STEPS: no accepted state yet; the first step of an AI session records it.")
        return 0
    now = snapshot(cfg, st["files"])
    diff = [r for r in now if now[r].get("id") != (st["files"].get(r) or {}).get("id")]
    gs = GS.differs(cfg["_root"], _read_json(_gs_path(cfg)) or {}) if _read_json(_gs_path(cfg)) is not None else []
    print(f"STEPS: {len(now)} guard files; " + (f"{len(diff)} differ from the accepted state: " + ", ".join(diff) if diff else "all as accepted."))
    for _, name, keys in gs:
        print(f"STEPS: git setting {', '.join(keys)} in {name} differs from the accepted state.")
    return 1 if diff or gs else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

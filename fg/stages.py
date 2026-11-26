"""FoundationGuard staged gate (AI-made, Claude, 2026-11-11). New in v0.8.5.

A long gate written as one command starts again from the top at every miss, and stops at the first one. On a project
whose checks take hours that becomes a wall: fix one thing, wait hours, meet the next. Here the gate can be a list of
named steps (foundationguard.json "gate_steps") instead:
  - every step runs even after one misses, and every miss is listed at once;
  - each step's result is kept for the exact commit it ran on (the push wrapper already demands a clean tree);
  - on the same commit, a step that passed is not run again (an interrupted or half-failed run picks up where it was);
  - after a fix, a step's pass is carried over to the new commit only when ALL of these hold: the step names the files
    it guards and none of them changed since the commit it ran on; every changed file is guarded by some step; the
    gate's own files and the machine's setup did not change; the step's own definition did not change; and a whole run
    (every step passed on one commit) is on record for this line of work, no older than `whole_run_days` days (1.5
    unless set);
  - in every other case everything runs, which is what the gate did before and is always safe.
A step:  {"name": "saves", "command": "...", "guards": ["src/save/**", "tests/saves/**"], "always": false,
          "needs": ["build"], "test_log": ".foundationguard/saves.xml"}
  guards    the files this step checks (globs). A step without guards runs on every new commit.
  always    true = runs on every new commit whatever changed (slow-rot checks: soak, old saves, replay).
  needs     steps that must pass first. If one of them misses, this step is listed NOT RUN, never as passed.
  test_log  the report the step writes (JUnit or NUnit XML, or PASS/FAIL lines); the approved list reads it.
  python fg/push.py --gate --whole    every step, whatever is on record (the nightly run; see examples/nightly.md)
  python fg/stages.py --plan          what the next gate would run, and why
"""
import hashlib, json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P
import approved as A
import catches as CL

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
DAY = 86400.0


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _head(root):
    return git("rev-parse", "HEAD", cwd=root).stdout.strip()


def _clean(root):
    return git("status", "--porcelain", "--untracked-files=no", cwd=root).stdout.strip() == ""


def steps(cfg):
    """(steps, problem). The config's gate_steps, checked: a name and a command each, names unique, needs known."""
    S = cfg.get("gate_steps") or []
    names = [s.get("name") for s in S if isinstance(s, dict)]
    if len(names) != len(S) or not all(names) or len(set(names)) != len(names):
        return [], "gate_steps: every step needs its own name"
    for s in S:
        if not s.get("command"):
            return [], f"gate_steps: step '{s['name']}' has no command"
        if [n for n in s.get("needs") or [] if n not in names]:
            return [], f"gate_steps: step '{s['name']}' needs a step that isn't listed"
    return S, None


def sig(s):
    """A step's definition as one short code. A changed definition means its old result no longer counts."""
    if BREAK("stages_sig"):
        return "same"
    body = json.dumps([s.get("command"), sorted(s.get("guards") or []), bool(s.get("always")), sorted(s.get("needs") or []), s.get("test_log")])
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def path(cfg):
    return os.path.join(cfg["_root"], cfg["state_dir"], "gate_results.json")


def load(cfg):
    try:
        r = json.load(open(path(cfg), encoding="utf-8-sig"))
        return r if isinstance(r, dict) and isinstance(r.get("steps", {}), dict) else {"steps": {}}
    except Exception:
        return {"steps": {}}


def save(cfg, res):
    os.makedirs(os.path.dirname(path(cfg)), exist_ok=True)
    with open(path(cfg), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    import steps as SP
    SP.recorded(cfg, [path(cfg)])                      # the check after the step takes it as the gate's


def _changed(root, old, new):
    """Files that differ between two commits, or None when `old` is not an earlier commit of this line of work."""
    if git("merge-base", "--is-ancestor", old, new, cwd=root).returncode != 0:
        return None
    # --no-renames: a moved file counts as changed in the place it left AND the place it went to
    p = git("diff", "--name-only", *([] if BREAK("stages_renames") else ["--no-renames"]), old, new, cwd=root)
    return None if p.returncode != 0 else [l for l in p.stdout.splitlines() if l.strip()]


def _no_carry(cfg, res, head, setup_changed):
    """Why no result may be carried over from an earlier commit, or None when carrying over is allowed."""
    if setup_changed:
        return "the machine's setup changed since the last pass"
    if BREAK("stages_whole"):
        return None
    w = res.get("whole") or {}
    days = float(cfg.get("whole_run_days", 1.5))
    if not w.get("commit"):
        return "no whole run has passed yet"
    if _changed(cfg["_root"], w["commit"], head) is None:
        return "the last whole run was on another line of work"
    if time.time() - float(w.get("when", 0)) > days * DAY:
        return "the last whole run is more than %g days old" % days
    return None


def _kit_lists(cfg):
    """Files only the kit's own checks read, and those run at every gate whatever is kept (the approved list, the
    licence table, the records). A change to one of them needs no step to run again."""
    if BREAK("stages_lists"):
        return []
    mine = [cfg.get("approved_file"), cfg.get("merge_signoff_file"), (cfg.get("assets") or {}).get("file", "ASSETS.md")]
    return [x for x in mine if x] + list(C.KIT_LISTS)


def _first_gate_file(cfg, ch):
    if BREAK("stages_gate_files"):
        return None
    return next((f for f in ch if P.matches(f, C.guard_globs(cfg))), None)


def _first_unmapped(S, ch):
    if BREAK("stages_unmapped"):
        return None
    return next((f for f in ch if not any(P.matches(f, x.get("guards") or []) for x in S)), None)


def _blocked_by_change(cfg, S, s, ch):
    """Why these changed files mean step `s` must run, or None."""
    if ch is None:
        return "its last pass was on another line of work"
    lists = _kit_lists(cfg)
    ch = [f for f in ch if not P.matches(f, lists)]
    f = _first_gate_file(cfg, ch)
    if f:
        return "the gate's own files changed (%s)" % f
    f = _first_unmapped(S, ch)
    if f:
        return "a changed file is guarded by no step (%s), so everything runs" % f
    f = next((f for f in ch if P.matches(f, s.get("guards") or [])), None)
    return ("a file it guards changed (%s)" % f) if f else None


def _decide(cfg, S, s, prev, head, st):
    """('keep', why) when this step's earlier pass stands for `head`, else ('run', why)."""
    if st["whole"]:
        return "run", "whole run"
    if not prev:
        return "run", "it has not run before"
    if not prev.get("ok"):
        return "run", "it missed last time"
    if prev.get("sig") != sig(s):
        return "run", "its definition changed"
    if st["setup_changed"]:
        return "run", "the machine's setup changed since the last pass"
    same = prev.get("commit") == head or BREAK("stages_any_commit")
    if same:
        return "keep", "already passed on this exact commit"
    return _decide_carry(cfg, S, s, prev, head, st)


def _decide_carry(cfg, S, s, prev, head, st):
    """The same, for a pass recorded on an earlier commit."""
    if BREAK("stages_no_keep"):
        return "run", "carrying over is switched off"
    if s.get("always") and not BREAK("stages_always"):
        return "run", "it runs on every new commit"
    if not s.get("guards") and not BREAK("stages_always"):
        return "run", "it names no files it guards, so it runs on every new commit"
    if st["no_carry"]:
        return "run", st["no_carry"]
    why = _blocked_by_change(cfg, S, s, _changed(cfg["_root"], prev["commit"], head))
    if why:
        return "run", why
    return "keep", "passed on %s; nothing it guards changed since" % prev["commit"][:10]


def plan(cfg, head, setup_changed=False, whole=False):
    """[(step, 'run' or 'keep', why)] for this commit."""
    S, bad = steps(cfg)
    res = load(cfg)
    st = {"whole": whole and not BREAK("stages_whole_flag"), "setup_changed": bool(setup_changed),
          "no_carry": _no_carry(cfg, res, head, setup_changed)}
    return [(s,) + _decide(cfg, S, s, res["steps"].get(s["name"]), head, st) for s in S], res, bad


def _run_step(cfg, s):
    """Run one step. (ok, seconds, tail of its output, {test name: passed} from its report)."""
    root = cfg["_root"]
    log = os.path.join(root, s["test_log"]) if s.get("test_log") else None
    if log:
        os.makedirs(os.path.dirname(log) or root, exist_ok=True)
        if os.path.exists(log):
            os.remove(log)                                       # an old report must never be read as this run's
    t0 = time.time()
    p = subprocess.run(s["command"], shell=True, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout + p.stderr)[-1200:]
    ok = p.returncode == 0
    if ok and log and not os.path.exists(log) and not BREAK("stages_report"):
        ok, out = False, out + "\n(the step said it passed but wrote no test report: %s)" % s["test_log"]
    if not ok and not out.strip():
        out = "(the step printed nothing; it ended with exit code %d)" % p.returncode
    return ok, round(time.time() - t0, 1), out, (A.results(log) if log else {})


def _needs_missing(s, state):
    """The first needed step that didn't pass, or None."""
    if BREAK("stages_needs"):
        return None
    return next((n for n in s.get("needs") or [] if state.get(n) != "ok"), None)


def _moved(root, head):
    return not BREAK("stages_moved") and (_head(root) != head or not _clean(root))


SECOND_TRY = "  << PASSED ONLY ON A SECOND TRY with nothing changed in between: a flaky check or the machine"
FLIPPED = "  << MISSED ON A COMMIT IT PASSED BEFORE with nothing changed in between: a flaky check or the machine"


def _flaky_mark(cfg, s, prev, head, ok):
    """The mark for a step that gave two different answers on one commit with nothing changed, or ''."""
    same_run = prev.get("commit") == head and prev.get("sig") == sig(s) and prev.get("ok") is not None
    if BREAK("stages_second_try") or not same_run or prev.get("ok") == ok:
        return ""
    CL.log(cfg, "flaky step", "step '%s' gave two different answers on the same commit with nothing changed" % s["name"])
    return SECOND_TRY if ok else FLIPPED


def _one(cfg, s, act, why, head, res, lines, state):
    """Run or keep one step; update the record, the report lines and the state. Returns a stop reason or None."""
    name = s["name"]; prev = res["steps"].get(name) or {}
    need = _needs_missing(s, state)
    if need:
        state[name] = "notrun"; lines.append("  NOT RUN  %s: it needs '%s', which did not pass" % (name, need)); return None
    if act == "keep":
        state[name] = "ok"; lines.append("  PASS     %s: kept (%s)" % (name, why)); return None
    ok, secs, out, tests = _run_step(cfg, s)
    if _moved(cfg["_root"], head):
        state[name] = "miss"
        return "step '%s' changed the project's files or the commit while it ran, so its result can't be trusted" % name
    res["steps"][name] = {"commit": head, "ok": ok, "sig": sig(s), "when": time.time(), "seconds": secs, "tests": tests, "tail": "" if ok else out}
    save(cfg, res)
    state[name] = "ok" if ok else "miss"
    lines.append("  %s %s: ran, %s s (%s)%s" % ("PASS    " if ok else "MISS    ", name, secs, why, _flaky_mark(cfg, s, prev, head, ok)))
    return None


def _tests(cfg, S, res, state):
    """{test name: passed} over every step that counts as passed (run now or kept), for the approved list."""
    got = {}
    for s in S:
        if state.get(s["name"]) == "ok" and not BREAK("stages_tests"):
            for k, v in (res["steps"].get(s["name"], {}).get("tests") or {}).items():
                got[k] = got.get(k, True) and v
    return got


def _problem(S, res, state):
    miss = [s["name"] for s in S if state.get(s["name"]) != "ok"]
    if not miss:
        return None
    tails = "".join("\n--- %s ---\n%s" % (n, (res["steps"].get(n, {}).get("tail", "") if state.get(n) == "miss" else "(not run)")[-600:]) for n in miss)
    return ("the gate missed %d of %d steps: %s.\nNo step was skipped because of them, so they can be fixed together; the "
            "next run repeats only these and whatever the fix touches.%s" % (len(miss), len(S), ", ".join(miss), tails))


def _record_whole(cfg, S, res, state, head):
    """A whole run = every step passed on this exact commit (all run now, or all on record for this commit)."""
    if all(state.get(s["name"]) == "ok" and res["steps"][s["name"]]["commit"] == head for s in S):
        res["whole"] = {"commit": head, "when": time.time(), "steps": len(S)}
        save(cfg, res)
        return True
    return False


def _would_carry(cfg, head, setup_changed):
    """{step: why} for the steps a normal run would have kept from an EARLIER commit (asked before a whole run)."""
    if BREAK("stages_narrow"):
        return {}
    pl, _, _ = plan(cfg, head, setup_changed, False)
    return {s["name"]: why for s, act, why in pl if act == "keep" and not why.startswith("already")}


def _tracked(cfg):
    """The record of results must stay out of git: a committed record could be copied or changed by a commit."""
    root = cfg["_root"]
    if BREAK("stages_tracked") or git("ls-files", "--error-unmatch", os.path.relpath(path(cfg), root), cwd=root).returncode != 0:
        return None
    return "the gate's record (%s/gate_results.json) is tracked by git; add %s/ to .gitignore and untrack it" % (cfg["state_dir"], cfg["state_dir"])


TEST_NAME = re.compile(r"(?i)(^|/)(tests?|specs?|__tests__)/|(^|/)test_[^/]*$|_tests?\.\w+$|\.(spec|test)\.\w+$")
TEST_CAMEL = re.compile(r"[a-z0-9]Tests?\.\w+$")               # SaveTests.cs, RouteTest.java


def _loose_tests(cfg, S):
    """Test files that no step lists. One command finds every test by itself; with steps, a new test file that nobody
    put under a step would never run and the gate would still say everything passed. So it stops until each has a home."""
    if BREAK("stages_test_files"):
        return None
    files = [f for f in git("ls-files", cwd=cfg["_root"]).stdout.split("\n") if f and not P.matches(f, ["fg/**"])]
    loose = [f for f in files if (TEST_NAME.search(f) or TEST_CAMEL.search(f)) and not any(P.matches(f, x.get("guards") or []) for x in S)]
    if not loose:
        return None
    return ("gate_steps: %d test file(s) are in no step's \"guards\", so no step is known to run them: %s. Put each under the "
            "step whose command runs it, and make sure that command really runs it (a command that names a folder finds "
            "new tests by itself; a command that names single files does not)."
            % (len(loose), ", ".join(loose[:5]) + (" and more" if len(loose) > 5 else "")))


def _run_steps(cfg, pl, head, res):
    """Run or keep every step in order. (stop reason or None, report lines, {step: 'ok' | 'miss' | 'notrun'})."""
    lines = []; state = {}
    for s, act, why in pl:
        stop = _one(cfg, s, act, why, head, res, lines, state)
        if stop:
            return stop, lines, state
        if state[s["name"]] == "miss" and BREAK("stages_stop_first"):
            break
    return None, lines, state


def _head_line(pl, state):
    ran = sum(1 for s, act, _ in pl if act == "run" and state.get(s["name"]) in ("ok", "miss"))
    kept = sum(1 for s, act, _ in pl if act == "keep" and state.get(s["name"]) == "ok")
    okn = sum(1 for s, _, _ in pl if state.get(s["name"]) == "ok")
    return "GATE %d of %d steps passed (%d run now, %d kept from an earlier pass)" % (okn, len(pl), ran, kept)


def _narrow_lines(cfg, carried, state):
    """Report lines for steps that missed in a whole run although a normal run would have kept their pass."""
    out = []
    for n in [n for n in carried if state.get(n) == "miss"]:
        out.append("  !! %s MISSED in this whole run, yet a normal run would have kept its earlier pass (%s). The files it "
                   "names under \"guards\" are too few: something outside them broke it. Widen its guards." % (n, carried[n]))
        CL.log(cfg, "guards too narrow", "step '%s' missed in a whole run although a normal run would have kept its pass" % n)
    return out


def run(cfg, setup_changed=False, whole=False):
    """Run the staged gate on HEAD. (problem or None, report text, {test name: passed})."""
    head = _head(cfg["_root"])
    pl, res, bad = plan(cfg, head, setup_changed, whole)
    S = [s for s, _, _ in pl]
    bad = bad or _tracked(cfg) or _loose_tests(cfg, S)
    if bad:
        return bad, "GATE not run: the list of test steps has to be put right first.", {}
    carried = _would_carry(cfg, head, setup_changed) if whole else {}
    stop, lines, state = _run_steps(cfg, pl, head, res)
    if stop:
        return stop, "GATE stopped: " + stop + "\n" + "\n".join(lines), {}
    head_line = _head_line(pl, state)
    problem = _problem(S, res, state)
    lines += _narrow_lines(cfg, carried, state)
    if not problem and _record_whole(cfg, S, res, state, head):
        head_line += "; this counts as a whole run"
    return problem, head_line + "\n" + "\n".join(lines), _tests(cfg, S, res, state)


def main(argv):
    cfg = C.load()
    if not cfg.get("gate_steps"):
        print("FoundationGuard: no gate_steps in foundationguard.json; the gate is one command and always runs whole."); return 0
    pl, res, bad = plan(cfg, _head(cfg["_root"]), whole="--whole" in argv)
    bad = bad or _loose_tests(cfg, [s for s, _, _ in pl])
    if bad:
        print(bad); return 1
    for s, act, why in pl:
        print("  %-5s %s: %s" % (act.upper(), s["name"], why))
    w = res.get("whole") or {}
    print("last whole run: " + (("%s, %.1f days ago" % (w["commit"][:10], (time.time() - float(w.get("when", 0))) / DAY)) if w.get("commit") else "none yet"))
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

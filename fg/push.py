"""FoundationGuard push wrapper (AI-made, Claude, 2026-11-08).

The only way to push. Runs the gate (the config's gate_command, then the approved-list check) on exactly this commit with a
clean tree, records the commit that passed, and pushes that commit only: if HEAD moved or the tree changed while the gate
ran, nothing is pushed. Never force, never tags, never a protected branch.

  python fg/push.py            # gate + push the current branch
  python fg/push.py --gate     # gate only (records the pass)
  python fg/push.py --gate --whole   # v0.8.5, with gate_steps: run every step whatever is on record (the nightly run)
  python fg/push.py --break-glass "owner's words"   # the guard itself is wrongly blocking: push once without the gate.
      Needs the owner's OK in the prompt; the gate still runs and its result, the commit and the owner's words are
      written into BREAKGLASS.md in a commit of their own, so the change report and the merge note show it.
"""
import os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import approved as A
import structure as ST
import rules as RU
import assets as AS
import fingerprint as FP
import secretscan as SS
import catches as CL
import tiny as TY
import ranbefore as RB
import pyenv as PE
import receipts as RC
import ledger as LG
import alarms as AL
import lock as LK
import copies as CP
import steps as SP
import docs as DC
import cards as CD
import stages as SG
import ownerok as OK
import state as SC
import datetime


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def head(cwd):
    return git("rev-parse", "HEAD", cwd=cwd).stdout.strip()


def clean(cwd):
    return git("status", "--porcelain", "--untracked-files=no", cwd=cwd).stdout.strip() == ""


BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


def _run(cmd, root):
    return subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _fresh_report(cfg):
    """Godot test (9 Nov): GUT can't make a missing folder, so it wrote no report yet still said 'passed', and an old
    report from an earlier run would have been read as this run's. So the folder is made and the old report removed."""
    if not cfg.get("test_log") or BREAK("gate_report"):
        return None
    log = os.path.join(cfg["_root"], cfg["test_log"])
    os.makedirs(os.path.dirname(log) or cfg["_root"], exist_ok=True)
    if os.path.exists(log):
        os.remove(log)
    return log


def _slow_note(cfg, seconds):
    """v0.8.5: a gate that is one long command starts from the top at every miss; say so once it is slow enough to hurt."""
    if BREAK("slow_gate_note") or seconds < 60 * float(cfg.get("slow_gate_minutes", 10)):
        return ""
    took = "%d seconds" % seconds if seconds < 90 else "%d minutes" % round(seconds / 60)
    return ("NOTE for the helper: the tests took %s as one command, which is over this project's limit for one command "
            "(slow_gate_minutes), and one command starts again from the top after every failure. Split them into steps "
            "(AGENT_SETUP.md, section 13): then every failure is listed in one run and a fix re-runs only what it touches.\n" % took)


def _commands(cfg, changed, notes):
    """Run the gate command (and the full run after a setup change). (problem or None, notes, gate output)."""
    root = cfg["_root"]
    log = _fresh_report(cfg)
    t0 = time.time()
    p = _run(cfg["gate_command"], root)
    out = p.stdout + p.stderr
    notes += _slow_note(cfg, time.time() - t0)
    if p.returncode != 0 and not BREAK("gate_exit"):
        if cfg.get("engine") == "unity" and p.returncode == 1 and not BREAK("unity_could_not_run"):
            # Unity: exit 2 = tests failed, exit 1 = it couldn't run them at all (compile error, licence, project won't open)
            return notes + "the gate could not run the tests (Unity exit 1: the project didn't compile, open or get a licence):\n%s" % out[-2000:], notes, out
        return notes + "the gate failed (exit %d):\n%s" % (p.returncode, out[-2000:]), notes, out
    if log and not os.path.exists(log) and not BREAK("gate_report"):
        return notes + "the gate failed: the tests said they passed but wrote no test report (%s), so nobody can tell what ran.\n%s" % (cfg["test_log"], out[-1500:]), notes, out
    if changed and cfg.get("full_gate_command"):
        q = _run(cfg["full_gate_command"], root)
        if q.returncode != 0:
            return notes + "the full run (forced by the setup change) failed (exit %d):\n%s" % (q.returncode, (q.stdout + q.stderr)[-2000:]), notes, out
        notes += "full run passed after the setup change.\n"
    return None, notes, out


def _staged(cfg, changed, notes, whole):
    """v0.8.5: the gate as steps (fg/stages.py). (problem or None, notes, gate output). The steps' test results are
    left in cfg["_got"] for the approved list."""
    bad, report, got = SG.run(cfg, setup_changed=bool(changed), whole=whole)
    cfg["_got"] = got
    cfg["_steps_log"] = any(s.get("test_log") for s in cfg.get("gate_steps") or [])
    return ((notes + report + "\n" + bad) if bad else None), notes + report + "\n", report


def _kit_steps(cfg, early=False):
    on = lambda key, fn, default=False: (lambda: fn() if cfg.get(key, default) else (True, ""))
    return [("approved", (lambda: A.check(cfg, written_only=True)) if early else (lambda: A.check(cfg, cfg.get("_got")))),
            ("structure", on("structure", lambda: ST.check(cfg))),
            ("rules", on("rules", lambda: RU.check(cfg))),
            ("assets", lambda: AS.check(cfg)),                              # licence ledger, once ASSETS.md exists
            ("tiny", lambda: TY.check(cfg, save=False)),                    # many new tiny files = code chopped to dodge limits
            ("secrets", on("secret_scan", lambda: SS.check(cfg), True)),    # keys in the added lines
            ("docs", lambda: DC.check(cfg))] + \
           ([] if BREAK("state_part") else [("state", lambda: SC.check(cfg)[:2])])   # every saved field kept or explained


BEFORE_TESTS = ("structure", "rules", "assets", "tiny", "secrets", "docs", "state")   # read only the code, not the tests' results


def _kit_checks(cfg, cards, only=None, skip=()):
    """(stopped?, report, warned parts) for the kit's own checks, each run as its parts mode says. Adds a card per problem.
    v0.8.5: every check runs even after one has stopped the push, so the owner sees all the problems at once."""
    report, warned, stopped = "", [], []
    early = only is not None                         # before the tests: the approved rows are judged as written (F103 with F556)
    for name, fn in _kit_steps(cfg, early):
        if (only is not None and name not in only and not (early and name == "approved")) or name in skip:
            continue
        mode = C.part(cfg, name)
        if early and name == "approved" and mode in ("off", "warn"):
            continue                                 # it can't stop the push, so only its run after the tests reports it
        if mode == "off":
            report += f"\n[{name} switched off in parts]"; continue
        ok_, rep_ = fn()
        if ok_ and early and name == "approved":
            continue                                 # it runs in full after the tests; say it once
        report += ("\n" + rep_) if rep_ else ""
        if ok_:
            continue
        cards += CD.part_cards(cfg, name, rep_ or "")
        if mode != "warn":
            stopped.append(name)
            if BREAK("kit_first_only"):
                break
            continue
        warned.append(name); report += f"\n[{name}: WARN ONLY in parts, so this does not stop the push]"
    if len(stopped) > 1:
        report += "\n[%d of the kit's checks stopped this push: %s. All of them ran; fix them together.]" % (len(stopped), ", ".join(stopped))
    return bool(stopped), report.strip(), warned


def run_gate(cfg, cards=None, whole=False):
    """(passed?, report). If a list is given, the plain-words cards for the owner are added to it."""
    cards = [] if cards is None else cards
    cards += SP.cards(cfg)                                          # 12 Nov: what the check after every step put back
    staged = bool(cfg.get("gate_steps"))
    if not cfg.get("gate_command") and not staged:
        cards += CD.part_cards(cfg, "gate", "no gate_command")
        return False, "no gate_command in foundationguard.json"
    fp, changed = FP.changes(cfg)
    notes = ("SETUP CHANGED since the last pass (results checked in full before they're trusted):\n  " + "\n  ".join(changed) + "\n") if changed else ""
    first, early, early_warned = (() if BREAK("cheap_first") else BEFORE_TESTS), "", []
    if first:                                       # the game's PC, 26 Nov: the owner waited through 6 minutes of tests,
        stopped, early, early_warned = _kit_checks(cfg, cards, only=first)   # then the tiny check stopped it (F556)
        report = early
        if stopped:
            return False, notes + report + "\n[the tests were not run: these quick checks stopped the upload first]"
    bad, notes, out = _staged(cfg, changed, notes, whole) if staged else _commands(cfg, changed, notes)
    if not bad and not staged and cfg.get("gate_pass_regex") and not re.search(cfg["gate_pass_regex"], out):
        bad = "the gate's output lacks its pass line"
    bad = AL.judge(cfg, bad, cards)                                 # what kind of red: REAL, UNSTEADY, MACHINE, PARKED
    if bad:
        cards += CD.part_cards(cfg, "gate", bad)
        return False, bad
    stopped, report, warned = _kit_checks(cfg, cards, skip=first)
    report, warned = "\n".join(x for x in (early, report) if x), early_warned + warned
    if stopped:
        return False, notes + report
    phone = _github_asks(cfg)                                       # Plan 2 PR 7: GitHub's lock asks the owner instead
    mine = CD.approved_check_cards(cfg, SS.default_range(cfg))
    if mine and not phone:
        cards += mine
        return False, notes + report + "\nAPPROVED: a check for something the owner approved was changed (the owner's call)"
    RB.note(cfg)                                                    # round 8: tests that passed last time must pass again
    todo = OK.missing(cfg)                                          # after the Godot game test (11 Nov): a changed guard waits for the owner
    if phone:
        import tiers as T
        waits = [x for x in todo if T.kind(x[0], cfg) == "own" and x[0] != RB.ITEM]   # tests that stopped running still ask
        todo = [x for x in todo if x not in waits]
        if waits or mine:
            report += ("\nFG-PUSH: this upload changes " + str(len(waits)) + " safety check file(s) without the owner's yes: " +
                       "; ".join(f"{f} ({why})" for f, why, _ in waits[:6]) + (" and more" if len(waits) > 6 else "") +
                       ". Nothing was put back. On GitHub it waits for the owner's Approve on their phone; to let other work "
                       "merge first, move this change to its own branch.")
    if todo:
        cards.append(OK.card(todo))
        return False, notes + report + "\nOWNER-OK: a guard was changed, or tests stopped running, and the owner has not said yes (python fg/ownerok.py lists it; when a helper runs the upload again, the kit's box asks the owner)"
    cards += LK.cards(cfg, SS.default_range(cfg))                   # until GitHub itself is locked, say so every push
    cards += CP.cards(cfg)                                          # 11 Nov: a copy of the project with no guard
    cards += PE.cards(cfg) + RB.cards(cfg)                         # round 8: Python's start-up files changed (warns)
    FP.save(cfg, fp)
    TY.check(cfg, save=True)
    RB.save(cfg)
    PE.save(cfg)
    SP.recorded(cfg, [FP.path(cfg), TY.state_path(cfg)])           # the check after the step takes these as the gate's
    if warned:
        CL.log(cfg, "warned", "problems in warn-only parts: " + ", ".join(warned))
    return True, notes + report


def _github_asks(cfg):
    """True when GitHub's lock guards the project now (fg/lockmode.py), so a safety-check change goes up and waits there."""
    if BREAK("push_waits_on_phone") or not cfg.get("remote_lock"):
        return False
    import lockmode as LM
    LK.state(cfg)                                     # ask GitHub again now: the mode needs a fresh ON
    return LM.on(cfg)


def _refuse(cfg, argv, br, root):
    """The reason this push is never allowed, or None."""
    if any(a in argv for a in ("--force", "-f", "--tags", "--mirror", "--delete")):
        return "FG-PUSH: force, tag, mirror and delete options are never allowed."
    if not br:
        return "FG-PUSH: not on a branch."
    import switches as SW
    if br.lower() in SW.protected(cfg):
        return f"FG-PUSH: '{br}' is protected; it changes only through a reviewed pull request."
    if cfg.get("work_branch") and br != cfg["work_branch"]:
        return f"FG-PUSH: this wrapper pushes only '{cfg['work_branch']}'."
    if not clean(root):
        return "FG-PUSH: commit or stash your changes first (the gate tests a commit, not a working tree)."
    return None


def _moved(root, h):
    return not BREAK("push_exact") and (head(root) != h or not clean(root))


def _gate_once(cfg, root, h, passed_file, whole=False, gate_only=True):
    """Run the gate unless this exact commit already passed. 0 when it may go on, 1 when stopped.
    whole (v0.8.5): run every step even if this commit is on record as passed (the nightly run)."""
    if SP.passed(cfg) == h and not whole:             # review 6: only a pass the kit recorded (F265)
        return 0
    cards = []
    rid = RC.started(cfg, RC.GATE)                                    # a receipt for every run of the gate
    ok, report = run_gate(cfg, cards, whole)
    RC.finished(cfg, rid, RC.GATE, ok, (report.strip().splitlines() or ["(no report)"])[-1])
    print(report)
    _gate_records(cfg, root)
    if not BREAK("push_summary"):
        text = CD.summary(ok, cards, uploading=ok and not gate_only)
        print(text); CD.save(cfg, text)
    if not ok:
        CL.log(cfg, "push stopped", report.strip().splitlines()[-1] if report.strip() else "gate failed")
        print("FG-PUSH: gate not passed: no push."); return 1
    if _moved(root, h):
        print("FG-PUSH: HEAD or the tree changed while the gate ran: no push. Run it again."); return 1
    with open(passed_file, "w") as f:
        f.write(h)
    SP.recorded(cfg, [passed_file])
    return 0


def _gate_records(cfg, root):
    """The files the project's own gate writes on every run ("gate_records" in foundationguard.json, which only the owner
    can change; the game's PC, 13 Nov: its pre-push script's pass file) go through the kit's record door, so they aren't
    taken as the owner's edits that wait for a yes."""
    if BREAK("gate_records"):
        return
    import glob as G, tiers as T
    paths = []
    for p in cfg.get("gate_records") or []:
        if not isinstance(p, str):
            continue
        if any(c in p for c in "*?[") and not BREAK("gate_records_globs"):
            paths += [f for f in G.glob(os.path.join(root, p), recursive=True) if os.path.isfile(f) and T.gate_record(os.path.relpath(f, root), cfg)]
        else:
            paths.append(os.path.join(root, p))
    if paths:
        SP.recorded(cfg, [p for p in paths if os.path.exists(p)])


def _push(root, h, br, done):
    p = git("push", "-u", "origin", f"{h}:refs/heads/{br}", cwd=root)
    print((p.stdout + p.stderr).strip()[-800:])
    if p.returncode == 0 and not BREAK("push_upstream"):            # "-u" with a commit id sets no upstream (the Godot game test)
        git("branch", f"--set-upstream-to=origin/{br}", br, cwd=root)
    if p.returncode != 0:
        print("FG-PUSH: NOT UPLOADED. The checks passed, but the upload itself failed (see git's words above)."); return 1
    print(done + " UPLOADED."); return 0


def main(argv):
    SP.GS.drop_env()                 # outside review 7: no git settings handed in through the environment
    SP.GS.drop_runner_env()          # outside review 8: nor test-runner settings (PYTEST_ADDOPTS ...)
    cfg = C.load(); root = cfg["_root"]; sd = os.path.join(root, cfg["state_dir"]); os.makedirs(sd, exist_ok=True)
    br = ""
    if not any(a in argv for a in ("--force", "-f", "--tags", "--mirror", "--delete")):
        br = git("branch", "--show-current", cwd=root).stdout.strip()
    why = _refuse(cfg, argv, br, root)
    if why:
        print(why); return 1
    passed_file = os.path.join(sd, "passed_commit")
    if "--break-glass" in argv and not BREAK("break_glass"):
        return break_glass(cfg, argv, br, passed_file)
    h = head(root)
    OK.give_at_upload(cfg) or OK.give_in_terminal(cfg)   # the owner's yes in the hook's box, or typed in their own window
    if _gate_once(cfg, root, h, passed_file, "--whole" in argv, gate_only="--gate" in argv):
        return 1
    if "--gate" in argv:
        print(f"FG-PUSH: gate passed on {h[:10]}."); return 0
    if _moved(root, h):
        print("FG-PUSH: HEAD is not the commit that passed: no push."); return 1
    need = OK.needing_ok(cfg)
    oks = LG.matching(cfg, need)                                    # the owner's OKs this upload carries
    rc = _push(root, h, br, f"FG-PUSH: pushed {h[:10]} to {br}.")
    if rc == 0 and not BREAK("push_uses_ok"):
        LG.use(cfg, oks)                                              # used up: they can't cover a later change
        OK.used_box_yeses(cfg, need)
    return rc

def break_glass(cfg, argv, br, passed_file):
    root = cfg["_root"]; i = argv.index("--break-glass")
    words = argv[i + 1].strip() if i + 1 < len(argv) and not argv[i + 1].startswith("-") else ""
    if len(words) < 8:
        print('FG-PUSH: break glass needs the owner\'s own words: --break-glass "why, in the owner\'s words"'); return 1
    h = head(root)
    ok, report = run_gate(cfg)
    first = (report.strip().splitlines() or ["(no output)"])
    result = "gate PASSED (break glass not needed)" if ok else "gate FAILED: " + next((l for l in first if "FAIL" in l or "fail" in l), first[-1])[:160]
    log = os.path.join(root, "BREAKGLASS.md")
    new = not os.path.exists(log)
    with open(log, "a", encoding="utf-8") as f:
        if new:
            f.write("# Break-glass pushes (FoundationGuard)\n\nEach row is a push made WITHOUT the gate, with the owner's OK. "
                    "More than one a month means the guard needs fixing, not bypassing.\n\n| When | Commit | Gate result | Owner's words |\n|---|---|---|---|\n")
        f.write(f"| {datetime.datetime.now():%Y-%m-%d %H:%M} | {h[:10]} | {result.replace('|', '/')} | {words.replace('|', '/')} |\n")
    git("add", "BREAKGLASS.md", cwd=root)
    c = git("commit", "-m", "FoundationGuard break glass: " + words[:120], cwd=root)
    if c.returncode != 0:
        said = (c.stdout + c.stderr)
        if re.search(r"Author identity unknown|Please tell me who you are|auto-detect email", said) and not BREAK("glass_identity"):
            print("FG-PUSH: couldn't record the break glass, because Git doesn't know your name and email yet. Ask your "
                  "helper to set them (git config --global user.name \"Your Name\" and git config --global user.email "
                  "\"you@example.com\"), then try again. Nothing was pushed.")
            return 1
        print("FG-PUSH: couldn't record the break glass:\n" + said[-400:]); return 1
    h2 = head(root)
    with open(passed_file, "w") as f:
        f.write(h2)
    SP.recorded(cfg, [passed_file, log])               # through the kit's record door (review 6, F265)
    CL.log(cfg, "break glass", result + " | " + words)
    p = git("push", "-u", "origin", f"{h2}:refs/heads/{br}", cwd=root)
    print((p.stdout + p.stderr).strip()[-800:])
    if p.returncode != 0:
        print("FG-PUSH: the push itself failed."); return 1
    print(f"FG-PUSH: BREAK GLASS pushed {h2[:10]} to {br} without the gate. It is in BREAKGLASS.md and the change report."); return 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""FoundationGuard one-step setup (AI-made, Claude, 2026-11-09). From your project's top folder:
  python path/to/foundationguard/fg/setup.py            (add --solo if nobody else reviews changes before they go in;
                                                          add --allow-routine if the owner already said yes to the
                                                          recommended list for the AI tool's own boxes: fg/allowlist.py;
                                                          without it, setup offers the list and writes it only when the
                                                          owner types yes; --no-allow-list skips the offer)
  python fg/setup.py --lock                             (the GitHub lock, one step at a time, each checked)
  python fg/setup.py --join                             (a teammate's fresh clone of a project that already has the
                                                          kit: writes only this computer's own, never-committed files)
It copies the kit into the project if needed, finds how your tests run, writes the settings, installs the guards,
records today's code sizes, runs your tests once and tells you in plain words what is now protected and what's next.
"""
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
import engines as EN
import config as _C
C_load = lambda root: _C.load(root)

def say(x): print("FoundationGuard: " + x)


def _me(py):
    """The Python to start the kit's own steps with. Windows (CI, 11 Nov): the hooks' Python command is a quoted full path,
    which a program list cannot start, so setup stopped after copying the kit; the running Python always can."""
    return py if os.environ.get("FG_BREAK") == "setup_python" else sys.executable

def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", errors="replace")

def find_tests(root, py):
    """(gate_command, test_log, check_command, kind) for the project's own tests, or None."""
    if os.environ.get("FG_BREAK") == "setup_detect": return None
    pj = os.path.join(root, "package.json")
    if os.path.exists(pj):
        try: scripts = json.load(open(pj, encoding="utf-8-sig")).get("scripts", {})
        except Exception: scripts = {}
        if "test" in scripts:
            return ("npm test", None, "npm test -- -t \"{check}\"", "npm")
    has_py_tests = any(f.startswith("test") and f.endswith(".py") for d, _, fs in os.walk(root) if ".git" not in d and "fg" not in d.split(os.sep) for f in fs)
    if has_py_tests:
        try:
            import pytest  # noqa: F401
            return (f"{py} -m pytest -q -p no:cacheprovider --junitxml=.foundationguard/junit.xml", ".foundationguard/junit.xml",
                    f"{py} -m pytest -q -p no:cacheprovider -k {{check}}", "pytest")
        except ImportError:
            return (f"{py} fg/run_tests.py", ".foundationguard/test_log.txt", f"{py} fg/run_tests.py --only {{check}}", "unittest")
    return None

NO_GIT = ("this folder isn't tracked by git yet, so there is no history to protect. Ask the owner if it's OK to start "
          "tracking it (run: git init, then save a first version: git add -A && git commit -m \"first version\"), then run setup again.")


def _place_kit(root):
    """Check the folder and copy the kit into fg/. A plain-words reason when setup can't go on, else None."""
    here = os.path.dirname(os.path.abspath(__file__))
    import ready as RD                       # round 9: a missing Git ended in an error only a programmer could read
    missing = RD.tools()
    if missing:
        return "; ".join(missing) + "."
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return NO_GIT
    top = git("rev-parse", "--show-toplevel").stdout.strip()
    same = lambda a: os.path.normcase(os.path.realpath(a))     # 19 Nov (Windows CI): a short name (RUNNER~1) is the same folder
    if same(top) != same(root):
        return f"run this from the project's top folder: {top}"
    dest = os.path.join(root, "fg")
    if os.path.abspath(here) == os.path.abspath(dest):
        return None
    if os.path.exists(dest):
        if os.path.isfile(os.path.join(dest, "guard.py")) and not BREAK("upgrade_in_place"):
            return _upgrade(root, here, dest)
        return "there's already an 'fg' folder here that isn't FoundationGuard's. Rename it, then run setup again."
    shutil.copytree(here, dest, ignore=shutil.ignore_patterns("__pycache__"))
    say("copied the kit into fg/.")
    return None


def _as_there(src, dst):
    """The new file's bytes with the line endings the file in the project has now, or None when the two differ only in
    line endings (nothing to write). The game's PC, 20 Nov: git had checked the kit out with Windows line endings, the
    update wrote the new kit's plain ones over all 77 files, and git listed every one as changed with nothing in them
    different, so the night's "is the folder clean" check refused the folder."""
    data = open(src, "rb").read()
    if BREAK("update_line_endings") or not os.path.isfile(dst):
        return data
    old = open(dst, "rb").read()
    plain = lambda b: b.replace(b"\r\n", b"\n")
    if plain(old) == plain(data):
        return None
    windows = b"\r\n" in old and old.count(b"\n") == old.count(b"\r\n")
    return plain(data).replace(b"\n", b"\r\n") if windows else data


def _upgrade(root, here, dest):
    """Fable's beta plan, line 3: an older kit is already in fg/. Each of its files is replaced by the newer one (a whole
    file at a time, so a hook that runs meanwhile reads either the old or the new file), and each changed file gets a
    door line, so the check after this step, or the next one, keeps the update."""
    import door as D
    import config as C
    names = sorted(n for n in os.listdir(here) if os.path.isfile(os.path.join(here, n)) and not n.endswith(".pyc"))
    before = D.ids([os.path.join(dest, n) for n in names])
    for n in names:
        new = _as_there(os.path.join(here, n), os.path.join(dest, n))
        if new is None:
            continue
        tmp = os.path.join(dest, n + ".fg-new")
        shutil.copy2(os.path.join(here, n), tmp)
        with open(tmp, "wb") as f:
            f.write(new)
        os.replace(tmp, os.path.join(dest, n))
    changed = [f for f, b in before.items() if D.entry_id(f) != b]
    if not BREAK("upgrade_door"):
        D.wrote_changed(C.load(root), before, "the kit's update (python setup.py, from " + here + ")")
    say(f"updated the kit in fg/ ({len(changed)} file(s) changed)." if changed else "the kit in fg/ is already this version.")
    return None


def _engine_tests(cfg, t, et, argv):
    """Join the engine's own tests with the project's: (tests to use, note)."""
    if not t and et:
        return et, None
    if t and et and "--engine-tests" in argv and et[0] not in cfg.get("gate_command", ""):
        cfg["gate_command"] = et[0] + " && " + (cfg.get("gate_command") or t[0])     # the engine's own tests run too
        say(f"the game's own {et[3]} tests now run in the gate as well.")
        return t, None
    if t and et and et[0] not in cfg.get("gate_command", t[0]):
        return t, f"the game's own {et[3]} tests can run now; to include them run setup again with --engine-tests."
    return t, None


def _engine_settings(root, cfg, t, argv):
    """Use the engine's settings, if this is an engine project. Returns (engine, sub folder, tests, note)."""
    engine, sub = EN.detect(root) if os.environ.get("FG_BREAK", "") != "engine_setup" else (None, "")
    if not engine:
        return engine, sub, t, None
    kind = EN.web_kind(root, sub) if engine == "web" else ""
    say(f"this is a {EN.NAMES[engine]} project" + (f" made with {kind}" if kind else "") + (f" (in the folder {sub})" if sub else "") +
        "; using its settings.")
    d = EN.defaults(engine, sub); preset = d.pop("rules_preset")
    for k, v in ((k, v) for k, v in d.items() if v is not None):
        cfg.setdefault(k, v)
    cfg.setdefault("engine", engine)
    r = cfg.setdefault("rules", {}); r.setdefault("dependencies", {})
    et, note = EN.tests(root, engine, sub)
    t, note2 = (et, None) if engine == "web" and et else _engine_tests(cfg, t, et, argv)   # the web runner also runs npm test
    sims = list(EN.sim_folders(root, engine, sub))
    if sims and "banned" not in r:
        why = "the simulation must give the same answer on every machine (saves, replays, multiplayer)"
        r["banned"] = [{"name": "deterministic maths", "preset": preset, "paths": [x + "/**" for x in sims], "why": why}]
    return engine, sub, t, note2 or note


def _guard_tests(root, cfg):
    """Outside review 7 (Claude, 13 Nov): the settings setup wrote guarded none of the project's own tests. Setup now
    names the test folders and the test runner's settings it finds (fg/testguard.py), and says so in plain words."""
    if "guard_paths" in cfg or os.environ.get("FG_BREAK") == "setup_guard_tests":
        return
    import testguard as TG
    cfg["guard_paths"] = TG.found(root, cfg)
    say(TG.words(cfg["guard_paths"]))


def _write_settings(cfg, cfg_path, t):
    if t:
        cfg.setdefault("gate_command", t[0]); cfg.setdefault("check_command", t[2])
        if t[1]: cfg.setdefault("test_log", t[1])
    cfg.setdefault("structure", {"include": ["**/*"], "exclude": ["fg/**", "node_modules/**", ".foundationguard/**"]})
    if os.environ.get("FG_BREAK", "") != "setup_rules":
        cfg.setdefault("rules", {"dependencies": {}})     # every project: a new package or plugin needs the owner's OK (F087)
    if os.environ.get("FG_BREAK", "") != "setup_chat_first":
        cfg.setdefault("chat_first", True)                # every new project: the question is in the chat before the box
    json.dump(cfg, open(cfg_path, "w"), indent=2)


ENGINE_IGNORES = {"unity": ["Library/", "Temp/", "Logs/", "obj/", "UserSettings/"], "godot": [".godot/", ".import/"],
                  "web": ["node_modules/", "playwright-report/", "test-results/"]}


def _gitignore(root, engine, sub):
    gi = os.path.join(root, ".gitignore"); lines = open(gi).read().splitlines() if os.path.exists(gi) else []
    want = [".foundationguard/", "__pycache__/", ".pytest_cache/"] + ENGINE_IGNORES.get(engine, [])
    add = [w for w in want if w not in lines and ((sub + "/" + w) if sub else w) not in lines]
    if not add:
        return
    pre = lambda w: (sub + "/") if sub and w not in (".foundationguard/", "__pycache__/") else ""
    open(gi, "a").write(("\n" if lines and lines[-1] else "") + "".join(pre(w) + w + "\n" for w in add))


def _rules_record(cfg, py):
    if cfg.get("rules") is None or os.path.exists("rules_baseline.json"):
        return
    subprocess.run([_me(py), os.path.join("fg", "rules.py"), "--baseline", "first setup"], capture_output=True)
    n = len(json.load(open("rules_baseline.json", encoding="utf-8-sig")).get("dependencies", {})) if os.path.exists("rules_baseline.json") else 0
    say(f"recorded the {n} add-ons, packages and plugins the project uses today; a new one will need the owner's OK.")
    if cfg["rules"].get("banned"):
        say("simulation folders found (" + ", ".join(b for x in cfg["rules"]["banned"] for b in x["paths"]) +
            "): risky maths (results that can differ between computers) may not grow there.")


def _records(root, cfg, py):
    """Today's sizes, add-ons, asset ledger and starter docs, recorded as the starting point."""
    first_structure = [_me(py), os.path.join("fg", "structure.py"), "--baseline", "first setup"]
    subprocess.run(first_structure if not os.path.exists("structure_baseline.json") else [_me(py), "-c", "0"], capture_output=True)
    _rules_record(cfg, py)
    import assets as AS
    nf, ng = AS.starter(C_load(root))
    if nf:
        subprocess.run([_me(py), os.path.join("fg", "assets.py"), "--baseline", "first setup"], capture_output=True)
        say(f"{nf} picture, sound, model or font file(s) in {ng} folder(s) have no recorded source or licence yet; they are "
            "listed in ASSETS.md as 'to fill in'. New ones must be recorded before they can be uploaded.")
    import docs as DC
    made = DC.starter(C_load(root)) if os.environ.get("FG_BREAK") != "docs_setup" else []
    if made:
        subprocess.run([_me(py), os.path.join("fg", "docs.py"), "--baseline", "first setup"], capture_output=True)
        say("wrote starter docs (" + ", ".join(made) + ") and recorded what they don't cover yet (docs_baseline.json). Every new "
            "AI session reads them first. Ask the owner the questions marked 'to fill in', in plain words, fill them in, then commit "
            "the docs and docs_baseline.json together. New parts, plugins and switches must be added to ARCHITECTURE.md as they come.")


def _first_run(cfg, t):
    """Run the tests once and say what is now protected."""
    if not t:
        say("no automatic tests were found, so nothing can be checked yet. The guards against risky commands are on. "
            "Next: ask your AI helper to write a test for each finished feature (fg/approve.py adds them to the approved list).")
        return 0
    g = subprocess.run(cfg["gate_command"], shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    status = "all your tests pass" if g.returncode == 0 else "some of your tests FAIL right now; fix them before anything can be shared"
    say(f"set up. Tests found ({t[3]}): {status}.")
    say("now protected: risky commands (deleting history, forced uploads) are blocked; a change to the guarded tests named "
        "above, or to the kit and its settings, needs the owner's OK; "
        "work is uploaded only with  python fg/push.py  after the tests pass on exactly that version; code-size limits are on.")
    say("then: walk the owner through locking the project on GitHub, one step at a time:  python fg/lock.py --steps  "
        "(every upload summary reminds them until it's done).")
    say("next: ask the owner which features are finished and must never break, then add each with  python fg/approve.py  (see AGENT_SETUP.md).")
    return 0 if g.returncode == 0 else 1


def _offer_list(root, argv):
    """11 Nov (the owner: "it cant be frustration for the user that stops the work from being done"): setup ends with a
    working unattended setup. It offers the recommended list for the AI tool's own boxes and writes it only on the
    owner's yes: typed here in a terminal, or given before setup ran (--allow-routine, which the kit's box asks about)."""
    if "--no-allow-list" in argv:
        return
    import allowlist as AL
    AL.offer(C_load(root), yes_flag="--allow-routine" in argv)


def main(argv):
    if "--lock" in argv:                                        # the GitHub lock, one checked step at a time (merge C)
        import lockwalk as LW
        return LW.main(argv)
    if "--join" in argv:                                        # a teammate's fresh clone (fg/join.py; merge C)
        import join as J
        return J.main(argv)
    root = os.getcwd(); py = _C.python_cmd()
    stop = _place_kit(root)
    if stop:
        say(stop); return 1
    t = find_tests(root, py)
    cfg_path = os.path.join(root, "foundationguard.json")
    cfg = json.load(open(cfg_path, encoding="utf-8-sig")) if os.path.exists(cfg_path) else {}
    cfg.setdefault("protected_branches", [] if "--solo" in argv else ["main", "master"])
    engine, sub, t, note = _engine_settings(root, cfg, t, argv)
    _guard_tests(root, cfg)
    _write_settings(cfg, cfg_path, t)
    r = subprocess.run([_me(py), os.path.join("fg", "install.py")], capture_output=True, text=True, encoding="utf-8", errors="replace"); print(r.stdout.strip())
    _gitignore(root, engine, sub)
    _records(root, cfg, py)
    _offer_list(root, argv)
    say("the guard hooks start working in the NEXT AI session opened in this folder: finish this session's setup, then restart it.")
    if note: say(note)
    if "--solo" in argv and not cfg.get("protected_branches"):
        say("because nobody else reviews your work (--solo), uploads straight to the main branch are allowed; the tests "
            "still run first, and force pushes and deleted history are still blocked. To block uploads to main too, ask "
            "your helper to put \"main\" in protected_branches in foundationguard.json (the kit's box asks you).")
    done = _first_run(cfg, t)
    if "--developer" in argv:                                    # v0.8.5: developers pick their features; beginners never see this
        print(); subprocess.run([_me(py), os.path.join("fg", "parts.py")])
    return done

if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

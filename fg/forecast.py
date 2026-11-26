"""FoundationGuard change forecast (AI-made, Claude, 2026-11-09).

Before the owner says yes to a change or a merge, this shows what it does in plain numbers: before -> after, with
a green up arrow when it got better and a red down arrow when it got worse. Made by this script from the real files,
never written by an AI, so it can't be spun. (Idea from a forecast screen in the Godot game test.)
  python fg/forecast.py [BASE]          BASE defaults to origin/main (or the last passed commit)
  python fg/forecast.py --md [BASE]     as a Markdown table, for a pull request or a merge note
How: the old version is checked out into a throwaway folder (a git worktree), both versions are measured with the
same settings, then the throwaway folder is removed. Nothing in your working folder is touched: the forecast runs on a
copy and never on the live project (a rule for every preview).
Game numbers: set "forecast_command" in foundationguard.json to a command that prints JSON {"name": number, ...} (for
example a seeded replay: villager speed, food after a year, the tick where two runs first differ). It is run in both
versions and its numbers join the table. Add "forecast_better": {"name": "up"|"down"} to say which way is better.
"""
import json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
TEST_DEF = re.compile(r"^\s*(?:def\s+test\w*|func\s+test_\w*|\[(?:Test|UnityTest|TestCase)\b|TEST(?:_F|_P)?\s*\(|"
                      r"IMPLEMENT_\w*AUTOMATION_TEST\s*\(|it\s*\(\s*[\"']|test\s*\(\s*[\"'])", re.M)

# name, plain label, which way is better
ROWS = [("tests", "automatic checks (tests)", "up"),
        ("approved", "approved features with a check", "up"),
        ("code_lines", "lines of code", None),
        ("biggest_file", "biggest file (lines)", "down"),
        ("files_over", "files over the size limit", "down"),
        ("long_functions", "functions over the length limit", "down"),
        ("tangled", "tangled functions", "down"),
        ("copy_paste", "copy-pasted blocks", "down"),
        ("loops", "systems depending on each other in a loop", "down"),
        ("risky_maths", "risky maths calls in the simulation", "down"),
        ("dependencies", "plugins, packages and libraries", None),
        ("licence_gaps", "art and sound files with licence problems", "down"),
        ("tiny_files", "tiny files", "down"),
        ("undocumented", "parts, plugins or switches the docs don't mention", "down"),
        ("untrue_docs", "untrue lines in the docs", "down")]


def git(root, *a):
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")


TEST_PATH = re.compile(r"(?i)(^|/)(tests?|spec)(/|_)|test_|_test\.|Tests?\.\w+$|\.spec\.")
CODE_EXT = (".py", ".gd", ".cs", ".cpp", ".h", ".hpp", ".c", ".cc", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".rs", ".go", ".java", ".kt",
            ".lua", ".swift", ".m", ".mm", ".inl")


def _count_tests(root, files):
    tests = 0
    for p in (p for p in files if TEST_PATH.search(p)):
        try:
            tests += len(TEST_DEF.findall(open(os.path.join(root, p), encoding="utf-8", errors="replace").read()))
        except OSError:
            pass
    return tests


def _quiet(out, fn):
    """Run one measuring step; a step that fails leaves its numbers out."""
    try:
        fn(out)
    except Exception:
        pass


def _approved(cfg):
    def step(out):
        import approved as A
        out["approved"] = len(A.rows(cfg))
    return step


def _structure_numbers(cfg, out):
    import structure as ST
    s = dict(ST.DEFAULTS); s.update(cfg["structure"])
    fl, cl, fn = ST.measure(cfg, s)
    import tiny as _T
    if not BREAK("forecast_code_only"):
        fl = {p: n for p, n in fl.items() if p.lower().endswith(CODE_EXT)}   # code only, not docs
    out["code_lines"] = sum(fl.values())
    out["biggest_file"] = max(fl.values()) if fl else 0
    out["files_over"] = sum(1 for n in fl.values() if n > s["max_file_lines"])
    out["long_functions"] = len(fn)
    dz = s.get("_design", {})
    out["tangled"] = len(dz.get("tangle", {}))
    out["copy_paste"] = len(dz.get("dups", []))
    out["loops"] = len(dz.get("cycles", []))


def _structure(cfg, out):
    try:
        _structure_numbers(cfg, out)
    except Exception as e:
        out["_error_structure"] = str(e)[:80]

    def tiny_step(o):
        import tiny as TY
        o["tiny_files"] = sum(1 for n in TY.current(cfg).values() if n < cfg.get("tiny_lines", 25))
    _quiet(out, tiny_step)


def _rules(cfg, out):
    try:
        import rules as RU
        ban, dep = RU.measure(cfg)
        out["risky_maths"] = sum(sum(v.values()) if isinstance(v, dict) else int(v or 0) for v in ban.values())
        out["dependencies"] = len(dep)
    except Exception as e:
        out["_error_rules"] = str(e)[:80]


def _assets(cfg, root):
    def step(out):
        import assets as AS
        if os.path.exists(os.path.join(root, AS.acfg(cfg)["file"])):
            out["licence_gaps"] = len(AS.measure(cfg)[0])
    return step


def _docs(cfg, root):
    def step(out):
        import docs as DC
        d = DC.dcfg(cfg); repo = DC.read_repo(root)
        if d["architecture"] not in repo:
            return
        sw = d.get("switch_pattern")
        out["undocumented"] = len(DC.coverage(repo, repo[d["architecture"]], d["source_roots"], DC.dependencies(cfg), sw))
        out["untrue_docs"] = len(DC.truth(repo, DC.doc_list(repo, d), sw, DC.branch_names(root), DC.ignored_fn(root)))
    return step


def _game(cfg, root, out):
    p = subprocess.run(cfg["forecast_command"], shell=True, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=cfg.get("forecast_timeout_s", 3600))
    try:
        game = json.loads((p.stdout.strip().splitlines() or ["{}"])[-1])
    except ValueError:
        out["_error_game"] = "forecast_command didn't print JSON numbers"; return
    out.update({"game:" + k: v for k, v in game.items() if isinstance(v, (int, float))})


def measure(cfg):
    """{name: number} for one copy of the project. Each part is measured only if it is set up."""
    root = cfg["_root"]
    files = [p for p in git(root, "ls-files").stdout.splitlines() if p and not p.startswith("fg/")]
    out = {"tests": _count_tests(root, files)}
    _quiet(out, _approved(cfg))
    if cfg.get("structure"):
        _structure(cfg, out)
    if cfg.get("rules"):
        _rules(cfg, out)
    _quiet(out, _assets(cfg, root))
    _quiet(out, _docs(cfg, root))
    if cfg.get("forecast_command") and not BREAK("forecast_game"):
        _game(cfg, root, out)
    return out

def default_base(root, cfg=None):
    """What to compare with: the version already uploaded (the upstream branch), else main when working on another branch,
    else the last version that passed the gate, else the previous commit. Solo work on main still gets a real before."""
    rp = lambda ref: git(root, "rev-parse", "--verify", "-q", ref).stdout.strip()
    head = rp("HEAD")
    if BREAK("forecast_base"):
        return "origin/main"
    up = rp("@{upstream}")
    if up and up != head:
        return "@{upstream}"
    br = git(root, "branch", "--show-current").stdout.strip()
    for ref in ("origin/main", "origin/master", "main", "master"):
        if br not in ("main", "master") and rp(ref) and rp(ref) != head:
            return ref
    import steps as SP
    pc = SP.passed(dict(cfg or {}, _root=root))        # review 6: only a pass the kit recorded (F265)
    if pc and pc != head and rp(pc):
        return pc
    return "HEAD~1" if rp("HEAD~1") else "HEAD"


def forecast(cfg, base=None):
    """(before, after, base) with the old version measured on a throwaway copy."""
    root = cfg["_root"]; base = base or default_base(root, cfg)
    after = measure(cfg)
    tmp = tempfile.mkdtemp(prefix="fg_forecast_")
    wt = os.path.join(tmp, "old")
    try:
        r = git(root, "worktree", "add", "--detach", "-q", wt, base)
        if r.returncode != 0:
            raise RuntimeError("couldn't make a copy of " + base + ": " + r.stderr.strip()[-200:])
        old = dict(cfg); old["_root"] = wt
        before = measure(old)
    finally:
        git(root, "worktree", "remove", "--force", wt)
        shutil.rmtree(tmp, ignore_errors=True)
    return before, after, base


def _mark(a, b, way):
    d = (b or 0) - (a or 0)
    if a is None or b is None or d == 0:
        return "new" if a is None else ("gone" if b is None else "same")
    arrow = "▲" if d > 0 else "▼"
    if way is None:
        return arrow + " (neither better nor worse)"
    return arrow + (" better" if (d > 0) == (way == "up") else " WORSE")


def rows(before, after, cfg=None):
    better = dict((n, b) for n, _, b in ROWS)
    better.update({"game:" + k: v for k, v in ((cfg or {}).get("forecast_better") or {}).items()})
    labels = dict((n, l) for n, l, _ in ROWS)
    names = [n for n, _, _ in ROWS if n in before or n in after] + sorted(k for k in set(before) | set(after) if k.startswith("game:"))
    out = []
    for n in names:
        a, b = before.get(n), after.get(n)
        if a is None and b is None:
            continue
        mark = "same" if BREAK("forecast_marks") else _mark(a, b, better.get(n))
        out.append((labels.get(n, n.replace("game:", "game: ")), a, b, mark))
    return out

def fmt(v):
    return "-" if v is None else (f"{v:g}" if isinstance(v, float) else f"{v:,}")


def table(r, md=False, base=""):
    worse = [x for x in r if "WORSE" in x[3]]
    head = f"Forecast: this change compared with {base}. " + (f"{len(worse)} number(s) got WORSE." if worse else "Nothing got worse.")
    if md:
        lines = [f"**{head}**", "", "| What | Before | After | Change |", "|---|---|---|---|"]
        lines += [f"| {l} | {fmt(a)} | {fmt(b)} | {m} |" for l, a, b, m in r]
    else:
        w = max([len(x[0]) for x in r] + [10])
        lines = [head] + [f"  {l:<{w}}  {fmt(a):>9} -> {fmt(b):<9} {m}" for l, a, b, m in r]
    return "\n".join(lines)


def main(argv):
    cfg = C.load()
    args = [a for a in argv if not a.startswith("--")]
    try:
        before, after, base = forecast(cfg, args[0] if args else None)
    except RuntimeError as e:
        print("FORECAST: " + str(e)); return 1
    print(table(rows(before, after, cfg), md="--md" in argv, base=base))
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

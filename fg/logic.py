"""FoundationGuard logic check, part 1: would any test notice? (AI-made, Claude, 2026-11-11; the version after v0.8.5)

For each line changed in the work not yet uploaded, this makes one small change at a time in a COPY of the project
(a comparison turned into its opposite, "and" for "or", a plus for a minus, a number one higher), runs the tests that
guard the file, and lists the changes that no test noticed. A line on that list can be wrong in the way shown and
every test still passes. It cannot show that the logic is right. It reports and never blocks an upload. No AI is needed.

  python fg/logic.py                      the lines changed since the last upload
  python fg/logic.py --since REV          the lines changed since REV
  python fg/logic.py --files a.py b.cpp   every line of these files (a.py:10-40 for a range)
  --max N        at most N changes (default: "logic": {"max_changes": 40} in foundationguard.json)
  --minutes N    stop after N minutes (default: "logic": {"minutes": 20})
  --exact        also move each comparison's edge by one (< to <=) and change bare start values ("n = 0"). These are
                 listed apart, under EXACT VALUE NOT TESTED: most of them are lines that cannot matter
  --command C    run this instead of the project's gate (for trying the check out)
  --json FILE    the full result as JSON
The project itself is never changed: the work happens in a copy in the system's temporary folder, removed afterwards.
Strings and comments are never changed. A change that makes the tests hang is stopped and counts as noticed.
When nothing notices a change, the same place is filled with text no language accepts and the tests run once more.
If they pass even then, the tests never build or load that line (a compile-time switch that is off, a file no test
loads): it is listed apart, as a line the tests never build, and not as a change they missed.
"""
import hashlib, json, os, random, re, shutil, signal, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P
import stages as SG

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
PY_LIKE = (".py", ".gd")
C_LIKE = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".cs", ".java", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".ts", ".tsx", ".go", ".rs", ".kt", ".swift")
PY_MASK = re.compile(r'(?s)"""(?:\\.|.)*?"""|\'\'\'(?:\\.|.)*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|#[^\n]*')
C_MASK = re.compile(r'(?s)/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`')
SWAP = {"==": "!=", "!=": "==", "<=": ">", ">=": "<", "<": ">=", ">": "<=", "&&": "||", "||": "&&", "and": "or", "or": "and",
        "True": "False", "False": "True", "true": "false", "false": "true", "+": "-", "-": "+", "*": "/", "/": "*",
        "+=": "-=", "-=": "+="}
EDGE = {"<=": "<", ">=": ">", "<": "<=", ">": ">="}             # --exact: a comparison's edge moved by one
# a bare start value: the line is only "name = number" (several names too), as in "int Count = 0;" or "total = 0"
START = re.compile(r"^\s*[\w:<>*&\s\[\],.]*?[\w.\[\]]+\s*=\s*-?\d+\s*(?:,\s*[\w.\[\]*&\s]+=\s*-?\d+\s*)*[;,]?\s*$")
EXACT = ("edge", "start value")                                 # the kinds of change that only --exact makes
OPS = [("comparison", r"(?<![<>=!+\-*/%&|^])(?:==|!=|<=|>=)(?!=)|(?<=\s)[<>](?=\s)", "any"),
       ("and/or", r"\b(?:and|or)\b", "py"), ("and/or", r"&&|\|\|", "c"),
       ("true/false", r"\b(?:True|False)\b", "py"), ("true/false", r"\b(?:true|false)\b", "any"),
       ("not", r"\bnot\s+", "py"), ("not", r"!(?=[\w(])", "c"),
       ("number", r"(?<![\w.])\d+(?![\w.])", "any"),
       ("arithmetic", r"(?<=\s)[-+*/](?=\s)|\+=|-=", "any")]
# lines where a change tells nothing: imports, compiler directives, printing and logging
NOISE = re.compile(r"^\s*(import\b|from\b|#|@|using\b|namespace\b|template\b|static_assert\b|print\(|printf\(|puts\(|"
                   r"console\.|logging\.|logger\.|log\.|UE_LOG\b|std::cout\b|std::cerr\b|System\.out\b|fmt\.Print)")
PER_LINE = 2
PROBE = ")]} fg_probe_not_code {[("          # no language builds or loads a line that holds this
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def family(path):
    ext = os.path.splitext(path)[1].lower()
    return "py" if ext in PY_LIKE else ("c" if ext in C_LIKE else None)


def mask(text, fam):
    """The text with every string and comment blanked (same length, same lines), so they are never changed."""
    if BREAK("logic_mask"):
        return text
    return (PY_MASK if fam == "py" else C_MASK).sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _new_text(label, old):
    if label == "not":
        return ""
    if label == "number":
        return "0" if old == "1" else str(int(old) + 1)
    return SWAP[old]


def candidates(masked_line, fam, exact=False):
    """The small changes for one line: [(start, end, new text, label, old text)]. Up to PER_LINE plain ones, the telling
    kinds first: a comparison becomes its opposite. With `exact`, up to PER_LINE more: a comparison's edge moved by one
    ("edge") and a bare start value changed ("start value"). Those two kinds often cannot alter any result, so they are
    made only when asked for."""
    if NOISE.search(masked_line):
        return []
    bare_start = bool(START.match(masked_line))
    plain, fine = [], []
    for label, rx, where in OPS:
        if where not in ("any", fam):
            continue
        for m in re.finditer(rx, masked_line):
            old = m.group(0)
            if label == "number" and bare_start:
                fine.append((m.start(), m.end(), _new_text(label, old), "start value", old))
                continue
            plain.append((m.start(), m.end(), _new_text(label, old), label, old))
            if old in EDGE:
                fine.append((m.start(), m.end(), EDGE[old], "edge", old))
    return plain[:PER_LINE] + (fine[:PER_LINE] if exact or BREAK("logic_exact") else [])


def _git(root, *a):
    return subprocess.run(["git"] + list(a), cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _base(root, since):
    """The commit the work is compared with: --since, else what was last uploaded, else the commit before, else nothing."""
    for ref in ([since] if since else ["@{u}", "HEAD~1"]):
        r = _git(root, "merge-base", "HEAD", ref) if ref == "@{u}" else _git(root, "rev-parse", "--verify", "-q", ref + "^{commit}")
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return EMPTY_TREE


def _wanted(cfg, path):
    """Code this check can change: a known language, not a test, not the kit, not excluded by the project."""
    lg = cfg.get("logic") or {}
    if not family(path) or P.matches(path, ["fg/**"] + list(lg.get("exclude") or [])):
        return False
    return not (SG.TEST_NAME.search(path) or SG.TEST_CAMEL.search(path))


def changed_lines(cfg, since=None):
    """{path: [line numbers]} added or changed in the working tree since the base."""
    root = cfg["_root"]
    out, path = {}, None
    diff = _git(root, "diff", "-U0", "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", _base(root, since), "--", ".")
    for l in diff.stdout.split("\n"):
        if l.startswith("+++ "):
            path = l[6:] if l.startswith("+++ b/") else None
        m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", l)
        if m and path and _wanted(cfg, path):
            out.setdefault(path, []).extend(range(int(m.group(1)), int(m.group(1)) + int(m.group(2) or 1)))
    return out


def named_lines(cfg, names):
    """{path: [line numbers]} for --files a.py b.cpp:10-40 (every line, or the range)."""
    out = {}
    for n in names:
        m = re.match(r"^(.*):(\d+)-(\d+)$", n)
        path = (m.group(1) if m else n).replace("\\", "/")
        full = os.path.join(cfg["_root"], path)
        if not os.path.isfile(full) or not family(path):
            continue
        last = len(_read(full).split("\n"))
        out.setdefault(path, []).extend(range(int(m.group(2)), min(int(m.group(3)), last) + 1) if m else range(1, last + 1))
    return out


def _change(path, n, text, cand):
    start, end, new, op, old = cand
    return {"path": path, "line": n, "start": start, "end": end, "new": new, "op": op, "old": old, "text": text.strip()[:90],
            "exact": op in EXACT and not BREAK("logic_exact")}


def _file_changes(root, path, numbers, exact):
    """For one file: (the possible changes of each line that has any, the number of lines with none)."""
    raw = _read(os.path.join(root, path))
    masked, raw = mask(raw, family(path)).split("\n"), raw.split("\n")
    per_line, nothing = [], 0
    for n in sorted(set(numbers)):
        cands = candidates(masked[n - 1], family(path), exact) if 0 < n <= len(masked) else []
        nothing += 0 if cands else 1
        if cands:
            per_line.append([_change(path, n, raw[n - 1], c) for c in cands])
    return per_line, nothing


def _in_turn(per_line):
    """Every line once before any line twice, and every plain change before any exact one."""
    out = []
    for want in (False, True):
        kind = [[c for c in line if c["exact"] == want] for line in per_line]
        out += [c[i] for i in range(PER_LINE) for c in kind if len(c) > i]
    return out


def plan(cfg, lines, limit, exact=False):
    """(changes to make, lines with nothing to change, lines left out by the limit). A change is a dict; the choice
    under a limit depends only on the commit, so the same commit gives the same report."""
    root = cfg["_root"]
    per_line, nothing = [], 0
    for path in sorted(lines):
        more, none = _file_changes(root, path, lines[path], exact)
        per_line, nothing = per_line + more, nothing + none
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    random.Random(head if not BREAK("logic_seed") else str(time.time_ns())).shuffle(per_line)
    flat = _in_turn(per_line)
    chosen = flat if BREAK("logic_limit") else flat[:limit]
    tried = {(c["path"], c["line"]) for c in chosen}
    return chosen, nothing, len(per_line) - len(tried)


def copy_project(cfg):
    """A copy of the project's files (tracked, and new ones git does not ignore) in the system's temporary folder."""
    root = cfg["_root"]
    if BREAK("logic_copy"):
        return root
    dst = tempfile.mkdtemp(prefix="fg-logic-")
    only = (cfg.get("logic") or {}).get("copy")                # a big project names what the tests need: ["Source/**", ...]
    names = _git(root, "ls-files", "-co", "--exclude-standard", "-z").stdout.split("\0")
    names = [n for n in names if n and not P.matches(n, [cfg["state_dir"] + "/**"]) and (not only or P.matches(n, only))]
    for n in names:
        src = os.path.join(root, n)
        if os.path.isfile(src) or os.path.islink(src):
            os.makedirs(os.path.dirname(os.path.join(dst, n)) or dst, exist_ok=True)
            shutil.copy2(src, os.path.join(dst, n), follow_symlinks=False)
    return dst


def _kill(p):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    else:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass


def _start(c, cwd):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", FG_LOGIC="1")
    env.pop("FG_BREAK", None)
    own_group = {} if os.name == "nt" else {"start_new_session": True}      # so a hang can be stopped with all it started
    return subprocess.Popen(c, shell=True, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            **own_group)


def run_cmds(cmds, cwd, limit):
    """Run the commands in order. (how it ended: 'pass', 'fail N' or 'timeout N' with the number of the command that
    ended it, counted from 1; seconds; last output)."""
    t0, tail = time.time(), ""
    for i, c in enumerate(cmds, 1):
        p = _start(c, cwd)
        try:
            tail = p.communicate(timeout=max(1.0, limit - (time.time() - t0)) if limit else None)[0][-600:]
        except subprocess.TimeoutExpired:
            _kill(p); p.communicate()
            return "timeout %d" % i, time.time() - t0, tail
        except BaseException:                                  # the run is being stopped: the tests stop with it
            if not BREAK("logic_stop"):
                _kill(p); p.wait()
            raise
        if p.returncode != 0:
            return "fail %d" % i, time.time() - t0, tail
    return "pass", time.time() - t0, tail


def _needed(S, names):
    """The names of every step that the named steps need, directly or through another step."""
    need = set()
    todo = list(names)
    while todo:
        name = todo.pop()
        step = next((s for s in S if s["name"] == name), {})
        for n in step.get("needs") or []:
            if n not in need:
                need.add(n); todo.append(n)
    return need


def commands_for(cfg, path, override=None):
    """The test commands that guard one file: the steps guarding it (and what they need), or the whole gate."""
    if override:
        return [override]
    S = cfg.get("gate_steps") or []
    if not S:
        return [cfg["gate_command"]] if cfg.get("gate_command") else []
    mine = [s["name"] for s in S if P.matches(path, s.get("guards") or [])] or [s["name"] for s in S]
    run = set(mine) | _needed(S, mine)
    return [s["command"] for s in S if s["name"] in run]


def _clear_caches(folder):
    shutil.rmtree(os.path.join(folder, "__pycache__"), ignore_errors=True)


def _swap_and_run(work, c, new, cmds, limit):
    """Put `new` in the place of the change in the copy, run the tests, put the line back. (how it ended, seconds)."""
    full = os.path.join(work, c["path"])
    original = _read(full)
    lines = original.split("\n")
    line = lines[c["line"] - 1]
    lines[c["line"] - 1] = line[:c["start"]] + new + line[c["end"]:]
    try:
        _write(full, "\n".join(lines))
        _clear_caches(os.path.dirname(full))
        how, secs, _ = run_cmds(cmds, work, limit)
    finally:
        _write(full, original)
        _clear_caches(os.path.dirname(full))
    return how, secs


def _try_change(work, c, cmds, limit, built):
    """One change: 'noticed', 'not noticed', or 'not built'. When nothing notices the change, the probe follows: the
    same place filled with text no language accepts. If the tests pass even then, they never build or load this line,
    and the change said nothing about its logic. `built` remembers the probe's answer for each line."""
    key = (c["path"], c["line"])
    if built.get(key) is False:
        return dict(c, result="not built", how="probe before", seconds=0.0)
    how, secs = _swap_and_run(work, c, c["new"], cmds, limit)
    if BREAK("logic_timeout") and how.startswith("timeout"):
        how = "pass"
    result = "noticed" if how != "pass" and not BREAK("logic_verdict") else "not noticed"
    if result == "not noticed" and key not in built and not BREAK("logic_probe"):
        probe, more = _swap_and_run(work, c, PROBE, cmds, limit)
        built[key], secs = probe != "pass", secs + more
    if built.get(key) is False:
        result = "not built"
    return dict(c, result=result, how=how, seconds=round(secs, 2))


def _time_limit(cfg, base_seconds):
    lg = cfg.get("logic") or {}
    return float(lg.get("timeout_seconds") or max(20.0, 4 * base_seconds))


def check(cfg, lines, limit, override=None, exact=False, minutes=None):
    """Try the changes. (problem or None, result dict)."""
    chosen, nothing, left_out = plan(cfg, lines, limit, exact)
    res = {"head": _git(cfg["_root"], "rev-parse", "HEAD").stdout.strip(), "changed_lines": sum(len(set(v)) for v in lines.values()),
           "nothing_to_change": nothing, "left_out_by_limit": left_out, "limit": limit, "tried": [], "stopped": None}
    if not chosen:
        return None, res
    work = copy_project(cfg)
    minutes = float(minutes or (cfg.get("logic") or {}).get("minutes", 20))
    t0, base, built = time.time(), {}, {}
    try:
        for c in chosen:
            cmds = tuple(commands_for(cfg, c["path"], override))
            if not cmds:
                return "LOGIC could not run: no test command is set up (gate_command or gate_steps in foundationguard.json).", res
            if cmds not in base and not BREAK("logic_baseline"):
                how, secs, tail = run_cmds(cmds, work, None)
                if how != "pass":
                    return "LOGIC could not run: the tests fail before any change is made, so they can show nothing. Fix them first.\n" + tail, res
                base[cmds] = secs
            if time.time() - t0 > 60 * minutes:
                res["stopped"] = "the time limit of %g minutes" % minutes
                break
            res["tried"].append(_try_change(work, c, cmds, _time_limit(cfg, base.get(cmds, 0.0)), built))
    finally:
        if work != cfg["_root"]:
            shutil.rmtree(work, ignore_errors=True)
    res["baseline_seconds"] = round(sum(base.values()), 2)
    return None, res


def _unbuilt(tried):
    """The report's lines for changes on lines the tests never build or load, one line of text for each file."""
    by = {}
    for t in tried:
        if t["result"] == "not built":
            by.setdefault(t["path"], set()).add(t["line"])
    out = ["  NEVER BUILT OR LOADED BY THE TESTS  %s: line%s %s" % (p, "s" if len(by[p]) > 1 else "", ", ".join(map(str, sorted(by[p]))))
           for p in sorted(by)]
    if by:
        out.append("The tests pass even with text no language accepts on these lines: a compile-time switch that is off, or "
                   "a file no test loads. No test can notice anything there.")
    return out


def _exact_lines(tried):
    """The report's lines for the exact changes nothing noticed, where the plain change at the same place was noticed."""
    plain_missed = {(t["path"], t["line"], t["start"]) for t in tried if not t["exact"] and t["result"] != "noticed"}
    fine = [t for t in tried if t["exact"] and t["result"] == "not noticed" and (t["path"], t["line"], t["start"]) not in plain_missed]
    out = ["  EXACT VALUE NOT TESTED  %s:%d  %s  '%s' -> '%s'   | %s" % (t["path"], t["line"], t["op"], t["old"], t["new"], t["text"])
           for t in fine]
    if fine:
        out.append("These were asked for with --exact: no test tries the exact edge or the exact start value. Often that "
                   "cannot matter (the edge is never reached, the start value is always replaced). Where the exact value "
                   "matters, add a test at that value.")
    return out


def report(res):
    tried = res["tried"]
    missed = [t for t in tried if t["result"] == "not noticed" and not t["exact"]]
    unbuilt = [t for t in tried if t["result"] == "not built"]
    fine = _exact_lines(tried)
    lines_tried = len({(t["path"], t["line"]) for t in tried})
    out = ["LOGIC %d small changes tried on %d of %d changed lines (limit %d): %d noticed by a test, %d not noticed%s%s."
           % (len(tried), lines_tried, res["changed_lines"], res["limit"], len([t for t in tried if t["result"] == "noticed"]), len(missed),
              ", %d on lines the tests never build or load" % len(unbuilt) if unbuilt else "",
              ", %d exact values not tested" % (len(fine) - 1) if fine else "")]
    rest = res["changed_lines"] - lines_tried
    if rest:
        out.append("  Not tried: %d lines (%d have nothing this check can change; %d left out by the limit%s)."
                   % (rest, res["nothing_to_change"], rest - res["nothing_to_change"],
                      "; stopped at " + res["stopped"] if res["stopped"] else ""))
    for t in missed:
        out.append("  NOT NOTICED  %s:%d  %s  '%s' -> '%s'   | %s" % (t["path"], t["line"], t["op"], t["old"], t["new"], t["text"]))
    if missed:
        out.append("A line listed here can be wrong in the way shown and every test still passes. Add a test that fails with "
                   "the change, or note why the change cannot matter.")
    return "\n".join(out + _unbuilt(tried) + fine)


def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else default


def _files(argv):
    """The names after --files, up to the next option."""
    out = []
    for a in argv[argv.index("--files") + 1:]:
        if a.startswith("--"):
            break
        out.append(a)
    return out


def _read(full):
    """A file's text exactly as it is on disk (line ends and odd bytes kept), so writing it back changes nothing."""
    with open(full, encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def _write(full, text):
    with open(full, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(text)


def _stop(*_):
    raise SystemExit(143)                 # a stop signal ends the run the tidy way: the tests stop, the copy is removed


def main(argv):
    signal.signal(signal.SIGTERM, _stop)
    cfg = C.load()
    lines = named_lines(cfg, _files(argv)) if "--files" in argv else changed_lines(cfg, _arg(argv, "--since"))
    limit = int(_arg(argv, "--max") or (cfg.get("logic") or {}).get("max_changes", 40))
    exact = "--exact" in argv or bool((cfg.get("logic") or {}).get("exact"))
    bad, res = check(cfg, lines, limit, _arg(argv, "--command"), exact, _arg(argv, "--minutes"))
    if bad:
        print(bad); return 1
    if _arg(argv, "--json"):
        json.dump(res, open(_arg(argv, "--json"), "w", encoding="utf-8"), indent=1)
    print(report(res) if res["changed_lines"] else "LOGIC nothing to try: no changed code lines since the last upload.")
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

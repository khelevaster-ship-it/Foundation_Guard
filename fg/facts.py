"""FoundationGuard: the kit's own count of what a change does to the safety checks (AI-made, Claude, 2026-11-15; Plan 2,
PR 3: the owner's review of the beta plan, 15 Nov).

The owner approves a merge into main on GitHub. GitHub's own page shows days of work and does not say whether a check was
removed. This compares each existing test with itself as main has it, test by test, and counts strictly:

  removed       a check line gone from the test, or the test gone        Nothing will check this any more.
  skipped       a skip, xfail or early return added                       It can break and nobody will notice.
  allows fail   a check that now always passes, `|| true`, continue-on-error   It can fail and the upload still goes.
  looser        a tolerance up, a minimum down                            It accepts results it used to reject.
  possible      a check line changed and the kit can't tell; an approved promise's test changed; a file it can't read
                                                                          The kit can't tell. Held.
  lock          the kit itself, its settings, the workflows, CODEOWNERS, the AI tools' hooks changed

Nothing rings for new tests, spaces, a moved file, a test renamed with the same body, or a check line moved within the
change. Names come from main's side (the approved row's words, else the test's old name), never the helper's new wording.
Every sentence is a fixed template. A guess from text, like the rest of the kit: when unsure it says "possible" and holds.

  python fg/facts.py --base origin/main --head HEAD [--json]      exit 1 when something rings

Limit: it watches the checks, not the game. A helper can leave every check in place and change the game so a check tests a
stand-in; this count won't see that.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adds as AD
import config as C
import ledgers as LG
import paths as P
import testguard as TG
import weaken as W

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
LOCK = ["fg/**", "foundationguard.json", ".github/workflows/**", ".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS",
        ".claude/settings.json", ".claude/settings.local.json", ".codex/**", ".cursor/**", ".github/hooks/**",
        ".git/hooks/**"]
IF_YOU_APPROVE = {
    "removed": "Nothing will check this any more.",
    "skipped": "It can break and nobody will notice.",
    "allows fail": "It can fail and the upload still goes.",
    "looser": "It accepts results it used to reject.",
    "possible": "The kit can't tell whether it got weaker. Ask why before you approve.",
    "lock": "The kit's own lock changes; the kit can't vouch for what comes after it.",
    "value changed": "The check stays; it now expects a different value. Usually ordinary (a version, a count).",
    "rewritten": "The check keeps its words and its limit; what it measures is now worked out by different code.",
}
NOTE = {"value changed", "rewritten"}                                 # listed on the page, never rings
ALLOW_FAIL = re.compile(r"\|\|\s*(?:true|:|exit\s+0)\b|continue-on-error\s*:\s*true|--exitfirst=0|-k\s+['\"]not\b|\bset\s+\+e\b")


def _git(root, *a):
    return subprocess.run(["git", *a], cwd=root, capture_output=True)


def _show(root, rev, path):
    """(text, readable) of a file at a commit; ('', True) when it isn't there."""
    p = _git(root, "cat-file", "-p", f"{rev}:{path}")
    if p.returncode != 0:
        return "", True
    if b"\0" in p.stdout[:8000]:
        return "", False
    return p.stdout.decode("utf-8", "replace"), True


def changed(root, base, head):
    """(the commit the branch split off main at, [(path on main, path in the change)]) for every changed file."""
    mb = _git(root, "merge-base", base, head).stdout.decode("utf-8", "replace").strip()
    if not mb:
        return None, []
    parts = _git(root, "diff", "--name-status", "-M", "-z", mb, head).stdout.decode("utf-8", "replace").split("\0")
    out, i = [], 0
    while i < len(parts) and parts[i]:
        st = parts[i]
        if st[:1] in "RC":
            out.append((parts[i + 1] if st[0] == "R" else None, parts[i + 2])); i += 3
        else:
            out.append((None if st == "A" else parts[i + 1], None if st == "D" else parts[i + 1])); i += 2
    return mb, out


# --- tests, one by one ---------------------------------------------------------------------------------------------------

def _indent(l):
    return len(l) - len(l.lstrip())


def tests_in(text, path):
    """{name: [body lines]} for each test in a file, in the order they appear."""
    lines = W._lines(text)
    py = path.endswith((".py", ".gd"))
    out, name, start, body, lead = {}, None, 0, [], []
    for l in lines:
        head = AD.TEST_HEAD.match(l) or W.TEST_START.match(l)
        if head and not (py and name and _indent(l) > start):
            if name:
                _put(out, name, body)
            name, start, body, lead = _name(l), _indent(l), lead + [l], []
            continue
        if py and l.lstrip().startswith("@") and (not name or _indent(l) <= start):
            if name:                                    # a decorator belongs to the test below it
                _put(out, name, body); name = None
            lead.append(l)
            continue
        if name and py and l.strip() and _indent(l) <= start and not l.lstrip().startswith(("#", ")")):
            _put(out, name, body); name = None
            continue
        if name:
            body.append(l)
    if name:
        _put(out, name, body)
    return out


def _put(out, name, body):
    out[name] = out.get(name, []) + body                # Unreal: the IMPLEMENT_ line and the RunTest body are one test


def _name(l):
    m = AD.TEST_HEAD.match(l)
    n = next((g for g in m.groups() if g), None) if m else None
    return (n or W._norm(l))[:120]


def plain(name):
    """A test's name in the owner's words: test_gold_survives_a_save -> gold survives a save."""
    n = re.sub(r"^(?:test_?|Test_?)", "", name.split(",")[-1].strip())
    n = re.sub(r"^F(?=[A-Z])", "", n)                    # Unreal: FMySaveRoundTripTest -> My Save Round Trip
    n = re.sub(r"(?<=[a-z])Test$", "", n) or n
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", n).replace("_", " ").strip() or name


def _checks(body):
    return [l for l in body if (W.ASSERT.search(l) or W.CHECK_CALL.search(l)) and not W.COMMENTED.match(l)]


RECEIVER = re.compile(r"\b(?:\w+(?:\.|->))+(?=(?:Test|Expect|Assert|Add|Check|Verify)\w*\s*\()")


def _core(l):
    """A line without the object its check is called on (TestNotNull( -> Test.TestNotNull( when a test moves into a helper),
    and without a trailing comment: the same check, said the same way."""
    return W._norm(RECEIVER.sub("", l.split(" //")[0]))


def _same(a, b):
    return [W._norm(x) for x in a[1:] if W._norm(x)] == [W._norm(x) for x in b[1:] if W._norm(x)]


TAUTOLOGY = re.compile(r"(?i)\b(?:True|1)\s+or\b|\bor\s+(?:True|1)\b|\btrue\s*\|\||\|\|\s*true\b|"
                       r"(?<![\w.])(\w+)\s*==\s*\1(?![\w.(\[])")
DEAD = re.compile(r"^\s*(?:if\s+(?:False|0|None)\s*:|if\s*\(\s*(?:false|0)\s*\)|#\s*if\s+0\b|while\s+False\s*:)")
# Round 2 (Grok, 16 Nov 04:37 UTC): more ways to say "never", "stop here" and "swallow the failure".
DEAD_MORE = re.compile(r"(?i)^\s*(?:if\s+not\s+(?:True|1)\s*:|if\s+(\d+)\s*==\s*(?!\1\b)\d+\s*:|while\s+(?:0|None)\s*:|"
                       r"for\s+\w+\s+in\s+(?:\[\s*\]|\(\s*\)|range\s*\(\s*0\s*\))\s*:|if\s+false\s*:|"
                       r"if\s*\(\s*(?:False|!\s*true|!\s*1)\s*\)|#\s*if\s+(?:false|defined\s*\(\s*NEVER)|if\s+constexpr\s*\(\s*false\s*\))")
STOPS = re.compile(r"\.skipTest\s*\(|\bSkipTest\b|importorskip\s*\(|pytest\.exit\s*\(|\bos\._exit\s*\(|\bsys\.exit\s*\(|"
                   r"raise\s+SystemExit\b|\bquit\s*\(\s*\)|\b(?:describe|it|test|context|suite)\.only\s*\(|\bf(?:it|describe)\s*\(|"
                   r"pytest_collection_modifyitems|pytest_ignore_collect|\bcollect_ignore\b|\bDISABLED_\w")
SWALLOW = re.compile(r"^\s*except\s*(?:\(?\s*(?:AssertionError|Exception|BaseException)\b[^:]*)?:|suppress\s*\(\s*(?:AssertionError|"
                     r"Exception|BaseException)\b|catch\s*\(\s*\.\.\.\s*\)|catch\s*\(\s*(?:const\s+)?std::exception")
RUNNER_GENERAL = re.compile(r"(^|/)(pyproject\.toml|setup\.cfg|setup\.py|package\.json|tox\.ini|[^/]*\.ini)$")
ENTRY_POINT = re.compile(r"\bpytest11\b")      # a package that registers itself as a pytest plugin loads into every run
RUNNER_LINE = re.compile(r"(?i)\[(?:tool[.:])?pytest|\baddopts\b|\bpytest_plugins\b|(?:^|\s)-p\s|\bplugins?\b|\btestpaths\b|"
                         r"\bpython_(?:files|functions|classes)\b|\bnorecursedirs\b|\bcollect_ignore|\"jest\"|\"vitest\"|"
                         r"\"mocha\"|\"test\"\s*:|setupFiles|reporters?\b|\btestMatch\b|\btestRegex\b|\bExcludeTest\b|"
                         r"\bReportExportPath\b|\bAutomation\b")
RUNNER_INI = re.compile(r"(?i)^\s*\[pytest\]|\bExcludeTest\b|\bReportExportPath\b|AutomationController|AutomationTestSettings|"
                        r"^\s*[+-]?(?:TestsToRun|DisabledTests|TestFilter)\b")
RUNNER_MARK = " (can decide which tests count as passed)"
RUNNER_TOUCH = re.compile(r"\bpytest_plugins\b|\bpluginmanager\b|\bhookimpl\b|\b_pytest\.|sys\.modules\s*\[\s*['\"]_?pytest|"
                          r"\bdef\s+pytest_(?:runtest|report|terminal|sessionfinish|collection)\w*\s*\(")
RETURN = re.compile(r"^\s*return\b(?!\s*\w+\s*\()")
RETURN_ANY = re.compile(r"^\s*return\b")
NESTED_DEF = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(|^\s*(?:func|function)\s+(\w+)\s*\(")


def _dead(l):
    return bool(DEAD.match(l) or (not BREAK("facts_dead_more") and DEAD_MORE.match(l)))


def _live(body):
    """A test's lines without those that can never run: under `if False:`, `if (false)` or `#if 0` (Grok's attack, 16 Nov:
    a check pasted under `if False:` in a new test counted as moved there, so its removal went unseen)."""
    if BREAK("facts_dead_code"):
        return list(body)
    out, dead_at, depth = [], None, 0
    for l in body:
        if dead_at is not None:
            if l.strip() and (_indent(l) <= dead_at and not l.strip().startswith(("}", "#endif", "#else"))):
                dead_at = None
            elif l.strip().startswith(("#endif", "#else")):
                dead_at = None; continue
            else:
                continue
        if _dead(l):
            dead_at = _indent(l); continue
        out.append(l)
    if BREAK("facts_uncalled_def"):
        return out
    # a function defined here and never called is dead too (a check moved into it never runs), but not a test itself
    text = "\n".join(out)
    keep, dead_at = [], None
    for i, l in enumerate(out):
        if dead_at is not None:
            if l.strip() and _indent(l) <= dead_at:
                dead_at = None
            else:
                continue
        m = NESTED_DEF.match(l)
        name = m and (m.group(1) or m.group(2))
        if name and not W.TEST_START.match(l) and not re.search(r"\b" + re.escape(name) + r"\b", text.replace(l, "", 1)):
            dead_at = _indent(l); continue
        keep.append(l)
    return keep


def _bound_looser(gone, added):
    """'was X, now Y' when a one-sided limit moved the loose way: `>= 5` to `>= 0`, `< 10` to `< 10000`."""
    if BREAK("facts_bound_direction"):
        return None
    for g in gone:
        a0 = _split_compare(g)
        if not a0 or a0[1] not in RANGE_OPS:
            continue
        try:
            x = float(a0[2].rstrip(")").strip())
        except ValueError:
            continue
        for a in added:
            a1 = _split_compare(a)
            if not a1 or a1[0] != a0[0] or a1[1] != a0[1]:
                continue
            try:
                y = float(a1[2].rstrip(")").strip())
            except ValueError:
                continue
            if (a0[1] in (">", ">=") and y < x) or (a0[1] in ("<", "<=") and y > x):
                return WAS_NOW.join((W._norm(g), W._norm(a)))
    return None


def _returns_before_checks(nb, added):
    """A return added at the test's own level with a check still below it: the check can never run."""
    if BREAK("facts_late_return") or len(nb) < 2:
        return False
    first = next((l for l in nb[1:] if l.strip()), None)
    if first is None:
        return False
    level, adds = _indent(first), {W._norm(a) for a in added}
    wide = not BREAK("facts_return_anywhere")
    for i, l in enumerate(nb[1:], 1):
        if W._norm(l) not in adds or not (RETURN_ANY.match(l) if wide else (RETURN.match(l) and _indent(l) == level)):
            continue
        owner = next((x for x in reversed(nb[1:i]) if x.strip() and _indent(x) < _indent(l)), "")
        if wide and NESTED_DEF.match(owner) or re.search(r"\blambda\b|=>", owner):
            continue                                     # the return of a helper defined inside the test
        if any((W.ASSERT.search(x) or W.CHECK_CALL.search(x)) and not W.COMMENTED.match(x) for x in nb[i + 1:]):
            return True
    return False


def _is_check(x):
    return bool(W.ASSERT.search(x) or W.CHECK_CALL.search(x)) and not W.COMMENTED.match(x)


ASSIGN_NUM = re.compile(r"^\s*(?:(?:const|let|var|auto|int|float|double|constexpr)\s+)*(\w+)\s*:?=\s*(-?\d+(?:\.\d+)?)\s*;?\s*$")
ASSIGN = re.compile(r"^\s*([A-Za-z_][\w.]*(?:\[[^\]]*\])?)\s*=(?!=)\s*\S")


def _bound_names(ob, nb):
    """'was X, now Y' when a limit held in a local name moved the loose way: `cap = 10` to `cap = 10000` under `err < cap`."""
    val = lambda body: {m.group(1): float(m.group(2)) for m in (ASSIGN_NUM.match(l) for l in body) if m}
    vo, vn = val(ob), val(nb)
    for l in nb:
        sc = _split_compare(l) if _is_check(l) else None
        if not sc or sc[1] not in RANGE_OPS:
            continue
        name = sc[2].rstrip(");").strip()
        if name in vo and name in vn and vo[name] != vn[name]:
            x, y = vo[name], vn[name]
            if (sc[1] in (">", ">=") and y < x) or (sc[1] in ("<", "<=") and y > x):
                return WAS_NOW.join((f"{name} = {x:g} (with {W._norm(l)})", f"{name} = {y:g}"))
    return None


def _sets_what_it_checks(nb, added, ob=()):
    """A new line that sets the very value a later check measures, where the test didn't set it before: the check now
    tests what the test itself wrote (changing how an existing value is made is judged elsewhere)."""
    adds = {W._norm(a) for a in added}
    had = {m.group(1) for m in (ASSIGN.match(x) for x in ob) if m}
    for i, l in enumerate(nb):
        m = ASSIGN.match(l)
        if not m or W._norm(l) not in adds or _is_check(l) or m.group(1) in had:
            continue
        target = m.group(1)
        for x in nb[i + 1:]:
            sc = _split_compare(x) if _is_check(x) else None
            if sc and re.sub(r"^\s*(?:assert\s+|\w+\s*\(\s*)", "", sc[0]).strip() == target:
                return f"the test now sets {target} itself, just before checking it: {W._norm(l)}"
            if sc and target in (sc[0], sc[2]) and "." in target:
                return f"the test now sets {target} itself, just before checking it: {W._norm(l)}"
    return None


def _swallowed(nb, added):
    """An added except/catch/suppress whose block holds a check: a failing check is caught and the test passes."""
    adds = {W._norm(a) for a in added}
    for i, l in enumerate(nb):
        if W._norm(l) not in adds or W.COMMENTED.match(l) or not SWALLOW.search(l):
            continue
        if "suppress" in l:                              # with suppress(AssertionError): the checks under it
            under = [x for x in nb[i + 1:] if x.strip()]
            block = [x for x in under[:next((k for k, x in enumerate(under) if _indent(x) <= _indent(l)), len(under))]]
        else:                                            # except/catch: the checks in its try block
            start = next((k for k in range(i - 1, -1, -1) if re.match(r"^\s*(?:try\s*:|try\s*\{|\}?\s*try\b)", nb[k])
                          and _indent(nb[k]) <= _indent(l)), None)
            block = nb[start + 1:i] if start is not None else []
        if any(_is_check(x) for x in block):
            return l
    return None


def _compare(name, ob, nb, moved_in, file_new=(), file_old=()):
    """Findings for one test that is in both: (kind, the old check line or '')."""
    out = []
    oc, nc = _checks(ob), _checks(nb)
    on = {_core(x) for x in _live(nb)}
    from collections import Counter
    was, now = Counter(_core(x) for x in file_old), Counter(_core(x) for x in file_new)
    kept = lambda l: _core(l) in on or _core(l) in moved_in or (file_old and now[_core(l)] >= was[_core(l)])  # moved in file
    gone = [l for l in oc if not kept(l)]
    if BREAK("facts_removed"):
        gone = []
    real_new = [l for l in nc if W._real_assert(l)]
    file_fewer = not file_old or sum(1 for l in file_new if W._real_assert(l)) < sum(1 for l in file_old if W._real_assert(l))
    if len(real_new) < len([l for l in oc if W._real_assert(l)]) and gone and file_fewer:
        out.append(("removed", gone[0]))
    elif gone and not BREAK("facts_unsure_holds"):
        out.append(("possible", gone[0]))
    added = [l for l in nb if W._norm(l) not in {W._norm(x) for x in ob}]
    out = out if not out or out[0][0] != "possible" else []      # judged below; "possible" only when nothing else is found
    unsure = gone[0] if gone and not out and not BREAK("facts_unsure_holds") else None
    stops = (lambda l: False) if BREAK("facts_stops") else (lambda l: bool(STOPS.search(l)) and not W.COMMENTED.match(l))
    if not BREAK("facts_skip") and (any(W.SKIP.search(l) or stops(l) for l in added) or _returns_early(nb, ob) or
                                    _returns_before_checks(nb, added) or
                                    (not BREAK("facts_dead_code") and any(_dead(l) for l in added))):
        out.append(("skipped", next((l for l in added if W.SKIP.search(l) or stops(l)), "")))
    bn = _bound_names(ob, nb) if not BREAK("facts_bound_names") else None
    if bn:
        out.append(("looser", bn))
    st = _sets_what_it_checks(nb, added, ob) if not BREAK("facts_sets_checked") else None
    if st:
        out.append(("possible", st))
    sw = _swallowed(nb, added) if not BREAK("facts_swallow") else None
    if sw:
        out.append(("allows fail", sw))
    taut = (lambda l: False) if BREAK("facts_tautology") else \
        (lambda l: bool(TAUTOLOGY.search(l)) and (W.ASSERT.search(l) or W.CHECK_CALL.search(l)) and not W.COMMENTED.match(l))
    if not BREAK("facts_allows_fail") and any(W.ALWAYS_PASS.search(l) or ALLOW_FAIL.search(l) or taut(l) for l in added):
        out.append(("allows fail", next((l for l in added if W.ALWAYS_PASS.search(l) or ALLOW_FAIL.search(l) or taut(l)), "")))
    if not BREAK("facts_looser"):
        c = W._Change(name, "\n".join(ob), "\n".join(nb))
        W._numbers(c)
        if c.why:
            out.append(("looser", re.sub(r"^[^(]*\(([^)]*)\): ", r"(\1) ", c.why[0])))
    if any(k == "allows fail" for k, _ in out) and not BREAK("facts_allows_fail"):
        out = [x for x in out if x[0] != "removed"]       # the check was swapped for one that always passes: say that once
    if unsure and not out and not BREAK("facts_exact_to_range"):
        wider = _exact_to_range(gone, added) or _bound_looser(gone, added)   # the owner, 15 Nov (the spike project, #3): "gold == 250" became "gold >= 0" and the
        if wider:                                     # note only said "the kit can't tell": an exact check made a range
            out.append(("looser", wider))             # accepts results it used to reject, so say so
            unsure = None
    if unsure and not out:
        how = [_how(l, [a for a in added if W.ASSERT.search(a) or W.CHECK_CALL.search(a)]) for l in gone]
        if None in how:
            out.append(("possible", unsure))
        else:                                           # every gone line has a twin: same check, one thing changed
            out.append(("rewritten" if "rewritten" in how else "value changed", unsure))
    return out


RANGE_OPS = {"<", "<=", ">", ">="}


def _split_compare(l):
    """(what is measured, operator, what it is compared with) for a check line with one comparison, else None."""
    c = re.sub(r"\s+", " ", _core(l)).strip()
    ms = [m for m in COMPARE.finditer(c) if m.group(1) in ("==", "!=", "<=", ">=", "<", ">")]
    if len(ms) != 1:
        return None
    m = ms[0]
    return c[:m.start()].strip(), m.group(1), c[m.end():].strip()


def _exact_to_range(gone, added):
    """'was X, now Y' when a check that wanted one exact value now accepts a range (== 250 to >= 0), else None."""
    for g in gone:
        a0 = _split_compare(g)
        if not a0 or a0[1] != "==":
            continue
        for a in added:
            a1 = _split_compare(a)
            if a1 and a1[0] == a0[0] and a1[1] in RANGE_OPS | {"!="}:
                return WAS_NOW.join((W._norm(g), W._norm(a)))
    return None


WAS_NOW = "\x00"


COMPARE = re.compile(r"(==|!=|<=|>=|<|>|\bis\s+not\b|\bis\b|\bnot\s+in\b|\bin\b)")


def _how(gone, added):
    """'value changed' when a new check line is this one with other numbers or words; 'rewritten' when it keeps its
    check, its words and numbers and its limit (the operator and what follows), and only how the measured value is
    worked out changed; None when the kit can't pair it."""
    for a in added:
        if _shape(a) == _shape(gone) and not BREAK("facts_value_note"):
            return "value changed"
    lits, name, tail = LITERAL.findall(_core(gone)), _check_name(gone), _limit(gone)
    for a in added:
        if tail and _limit(a) == tail and _check_name(a) == name and LITERAL.findall(_core(a)) == lits \
                and not BREAK("facts_rewrite_note"):
            return "rewritten"
    return None


def _check_name(l):
    m = re.match(r"\s*(\w+)", _core(l))
    return m.group(1) if m else ""


def _limit(l):
    """The last comparison and what it compares against: `< Tuning.PlaceAvoidBelow);`."""
    c = re.sub(r"\s+", "", _core(l))
    ms = list(COMPARE.finditer(c))
    return c[ms[-1].start():] if ms else ""


LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|\b\d+(?:\.\d+)?[fFuUlL]?\b')


def _shape(l):
    """A check line with its numbers and quoted words blanked: `TestEqual(V, 23)` and `TestEqual(V, 24)` have one shape."""
    return LITERAL.sub("#", _core(l))


def _returns_early(nb, ob):
    c = W._Change("t", "\n".join(ob), "\n".join(nb))
    return any(W.TEST_BODY.match(l) and W._early_return(c, i) for i, l in enumerate(c.nl))


def _approved(text):
    """{row id: (behaviour words, the whole row normalised, check name)} from an approved list. The columns come from
    its header row (Behaviour, Check(s)); without one, the second and fourth."""
    out, bi, ci = {}, 1, 3
    for l in W._lines(text):
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        low = [c.lower() for c in cells]
        if "behaviour" in low or "behavior" in low:
            bi = low.index("behaviour") if "behaviour" in low else low.index("behavior")
            ci = next((i for i, c in enumerate(low) if c.startswith("check")), ci)
            continue
        if len(cells) >= 4 and re.match(r"^[A-Z]+\d+[a-z]?$", cells[0]):
            words = cells[bi] if bi < len(cells) else cells[1]
            words = re.split(r"(?<=[a-z\)])[:;(] ", words)[0][:80]
            out[cells[0]] = (words, W._norm(l), cells[ci] if ci < len(cells) else "")
    return out


def count(root, base, head, cfg=None):
    """[(kind, what, evidence)] for the change from where it split off base to head, plus the number of files read."""
    cfg = cfg or C.load(root)
    mb, files = changed(root, base, head)
    if mb is None:
        return [("possible", "the kit could not find where this change split off main", "")], 0
    globs = C.guard_globs(cfg)
    approved_file = (cfg.get("approved_file") or "APPROVED.md")
    rows_main = _approved(_show(root, mb, approved_file)[0])
    promised = {r[2].split("::")[-1].strip("` ") for r in rows_main.values() if r[2]}
    found, read, runner_files = [], [], set()
    for o, n in files:
        rel = n or o
        lock = P.matches(rel, LOCK) or bool(o and P.matches(o, LOCK))
        if not lock and not BREAK("facts_runner_lock"):  # how the tests are found and run (conftest.py, pytest.ini, jest's
            lock = bool(TG.RUNNER.search(rel) or (o and TG.RUNNER.search(o)))   # config): a plugin there can report any
            if not lock and not BREAK("facts_runner_settings") and RUNNER_GENERAL.search(rel):   # test as passed, so it is
                a, b = (_show(root, mb, o)[0] if o else ""), (_show(root, head, n)[0] if n else "")   # the kit's lock
                ca, cb = set(a.splitlines()), set(b.splitlines())                                  # (Grok, round 2);
                rx = RUNNER_LINE if not rel.endswith(".ini") or rel.endswith(("tox.ini", "setup.cfg")) or \
                    BREAK("facts_ini_narrow") else RUNNER_INI           # a game's .ini (Unreal's DefaultEngine.ini) holds
                lock = any(rx.search(x) for x in ca ^ cb) or (not BREAK("facts_pytest11") and   # plugins and settings changed
                       any(ENTRY_POINT.search(x) for x in ca ^ cb))                                   # every day: only its
                                                                         # test lines count there
            if lock:                                                      # only the lines that set up the test runner
                runner_files.add(rel)
        test = AD.is_test_file(rel, cfg) or bool(o and AD.is_test_file(o, cfg))
        guard = P.matches(rel, globs) or bool(o and P.matches(o, globs))
        if not (lock or test or guard):
            continue
        (ot, ok1), (nt, ok2) = (_show(root, mb, o) if o else ("", True)), (_show(root, head, n) if n else ("", True))
        read.append((o, n, ot, nt, lock, test, ok1 and ok2))
    new_tests, old_names = {}, set()
    for o, n, ot, nt, _, test, _ in read:
        if test and n:
            new_tests.update({k: v for k, v in tests_in(nt, n).items()})
        if test and o:
            old_names.update(tests_in(ot, o))
    moved_in = {_core(l) for k, b in new_tests.items() if k not in old_names for l in _live(b) if W._norm(l)}   # into new tests
    for o, n, ot, nt, lock, test, readable in read:
        rel = n or o
        if lock and not BREAK("facts_lock"):
            if not _only_permission_rules(rel, ot, nt):
                found.append(("lock", rel + (" (removed)" if not n else " (new)" if not o else "") +
                              (RUNNER_MARK if rel in runner_files and not BREAK("facts_runner_words") else ""), ""))
            continue
        if not readable and not BREAK("facts_unreadable_holds"):
            found.append(("possible", f"{rel}: the kit can't read this file", "")); continue
        if rel.endswith(approved_file) or (o or "").endswith(approved_file):
            found += _rows(rows_main, _approved(nt)); continue
        if test and not BREAK("facts_runner_touch"):    # a test file that reaches into the runner itself (a plugin, its
            touch = next((x for x in W._lines(nt) if RUNNER_TOUCH.search(x) and not W.COMMENTED.match(x)     # hooks, its
                          and W._norm(x) not in {W._norm(y) for y in W._lines(ot)}), None)                   # modules)
            if touch:
                found.append(("lock", rel + " (reaches into the test runner: " + W._norm(touch)[:60] + ")", ""))
        if test and not BREAK("facts_file_skip"):
            had = {W._norm(x) for x in W._lines(ot)}
            outside = {W._norm(x) for b in tests_in(nt, n or rel).values() for x in b}
            hit = next((x for x in W._lines(nt) if W._norm(x) not in had and W._norm(x) not in outside and
                        (W.SKIP.search(x) or (not BREAK("facts_stops") and STOPS.search(x))) and not W.COMMENTED.match(x)), None)
            if hit:                                       # pytestmark = skip, a skip at the top of the file or on a class:
                found.append(("skipped", rel, hit))       # every test in the file stops running (Grok's attack, 16 Nov)
        if test:
            old, new = tests_in(ot, o or rel), tests_in(nt, n or rel)
            if not BREAK("facts_shadowed"):
                heads = lambda t: [_name(l) for l in W._lines(t) if AD.TEST_HEAD.match(l) or W.TEST_START.match(l)]
                ho, hn = heads(ot), heads(nt)
                for nm in sorted({x for x in hn if hn.count(x) > max(1, ho.count(x))}):
                    found.append(("removed", plain(nm), "a second test with the same name now replaces it"))
            for name, ob in old.items():
                words = plain(name)
                if name not in new:
                    twin = next((b for k, b in new_tests.items() if k not in old and _same(ob, b)), None)
                    if twin is not None and not BREAK("facts_rename_reads_header"):
                        moved = [l for l in twin if W._norm(l) not in {W._norm(x) for x in ob}]
                        if any(W.SKIP.search(l) or STOPS.search(l) for l in moved):
                            found.append(("skipped", words, next(l for l in moved if W.SKIP.search(l) or STOPS.search(l))))
                            continue
                    if not BREAK("facts_same_body") and twin is not None:
                        continue                         # renamed or moved with the same body
                    if name in new_tests and not BREAK("facts_same_body"):
                        nb = new_tests[name]             # the same test moved to another file: judge it there
                        found += [(k, words, e) for k, e in _compare(name, ob, nb, moved_in)]
                        continue
                    found.append(("removed", words, "the whole test is gone")); continue
                nb = new[name]
                these = _compare(name, ob, nb, moved_in, _live(W._lines(nt)), W._lines(ot))
                held_here = [k for k, _ in these if k not in NOTE] if not BREAK("facts_promised_values") else these
                if not held_here and name in promised and not _same(ob, nb) and not BREAK("facts_row_words"):
                    these = these + [("possible", "an approved promise's test changed inside")]
                found += [(k, words, e) for k, e in these]
            continue
        for r in LG.weaker(cfg, rel, ot, nt):            # a guard file that isn't a test: the weakening finder's reasons
            if re.search(r"=\s*(?:\[\]|\(\)|\{\}|\"\"|'')\s*$", r) and not BREAK("facts_empty_allow"):
                continue                                 # an empty allow-list starts out empty: nothing is let through
            if re.search(r"\b(?:exception|waiver)\b", r) and not BREAK("facts_exception"):
                found.append(("skipped", rel, r)); continue      # something that was checked no longer is
            kind = "skipped" if r.startswith("a skip") else "allows fail" if "always passes" in r else \
                "looser" if "went up" in r or "went down" in r else "removed" if "removed" in r else "possible"
            found.append((kind, rel, r))
    if BREAK("facts_old_names"):
        found = [(k, w.upper(), e) for k, w, e in found]
    return list(dict.fromkeys(found)), len(files)


def _rows(old, new):
    out = []
    for rid, (words, line, _) in old.items():
        if rid not in new:
            out.append(("removed", f'approved behaviour {rid}: "{words}"', "the row is gone"))
        elif new[rid][1] != line and not BREAK("facts_row_words"):
            out.append(("possible", f'approved behaviour {rid}: "{words}"', "its words, check or break switch changed"))
    return out


def _only_permission_rules(rel, old, new):
    if not rel.replace("\\", "/").endswith((".claude/settings.json", ".claude/settings.local.json")) or not old or not new:
        return False
    try:
        import steps as SP
        return SP._only_permission_rules(rel, old.encode(), new.encode())
    except Exception:
        return False


# --- the screen -------------------------------------------------------------------------------------------------------

WHAT = {"removed": "a check removed", "skipped": "a check turned off, or an exception added", "allows fail": "a check that can no longer fail",
        "looser": "a check loosened", "possible": "a check changed in a way the kit can't judge",
        "value changed": "an expected value changed", "rewritten": "how a check measures rewritten"}
COUNTS = (("removed", "removes", "check"), ("skipped", "turns off", "check"), ("allows fail", "lets", "check fail"),
          ("looser", "loosens", "check"), ("possible", "changes", "check the kit can't judge"))


def sentence(kind, what, evidence):
    if evidence and WAS_NOW in evidence and not BREAK("facts_exact_to_range"):
        was, now = evidence.split(WAS_NOW, 1)
        ev = f" What the kit saw: was `{was[:90]}`, now `{now[:90]}`."
    else:
        ev = f" What the kit saw: `{W._norm(evidence)[:90]}`" if evidence and kind != "lock" else ""
    return f"**{what}**: {WHAT[kind]}. If you approve: {IF_YOU_APPROVE[kind]}{ev}"


def _n(m, word):
    return f"{m} {word}" if m == 1 else f"{m} " + word.replace("check", "checks", 1)


def screen(found, files, head=""):
    """(rings, one short line, the kit's facts in plain words). The line says which kind of merge this is first."""
    notes = [f for f in found if f[0] in NOTE]
    locks = [w for k, w, _ in found if k == "lock"]
    held = [f for f in found if f[0] not in NOTE and f[0] != "lock"]
    tail = ("\n\nNot held: the checks below are all still there with the same limit; the kit lists them so you can see them.\n" +
            "\n".join("- " + sentence(*f) for f in notes[:6])) if notes else ""
    if not held and not locks:
        return False, "Safe to approve: removes 0 checks.", (
            f"**Safe to approve: removes 0 checks.** The kit read every test and safety file this change touches "
            f"({files} file(s) changed in all), from where it split off main. Nothing was removed, turned off or loosened, "
            "and the kit's own lock wasn't touched." + tail)
    parts = [f"{verb} {_n(sum(1 for k, _, _ in held if k == kind), noun)}" for kind, verb, noun in COUNTS
             if any(k == kind for k, _, _ in held)]
    if locks:
        parts.append(f"changes the kit's own lock ({len(locks)} file{'s' if len(locks) != 1 else ''})")
    line = ("Held: this change " + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] + ".")[:160]
    items = [sentence(*f) for f in held[:6]]
    if len(held) > 6:
        items.append(f"and {len(held) - 6} more: this is a big change to your safety checks.")
    if locks:
        names = ", ".join(locks[:4]) + (f" and {len(locks) - 4} more" if len(locks) > 4 else "")
        items.append(f"**The kit's own lock**: {names}. If you approve: {IF_YOU_APPROVE['lock']}")
        if any(RUNNER_MARK in w for w in locks):
            items.append("**Read this one carefully**: a file marked \"can decide which tests count as passed\" sets up how "
                         "the tests are found, run or reported. It can load code into the test runner, and your yes covers "
                         "every line of it. Approve only if you know why it changed.")
    body = "\n".join("- " + i for i in items)
    return True, line, f"**{line}** (the kit counted this; the helper didn't write it)\n\n{body}" + tail


def main(argv):
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default
    root = arg("--root", os.getcwd())
    found, files = count(root, arg("--base", "origin/main"), arg("--head", "HEAD"))
    rings, line, body = screen(found, files)
    if "--json" in argv:
        print(json.dumps({"rings": rings, "line": line, "facts": body, "found": found}))
    else:
        print(body)
    return 1 if rings else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

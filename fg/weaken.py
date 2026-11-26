"""FoundationGuard weakening finder (AI-made, Claude, 2026-11-09).

When an AI helper asks to change a guard file, the owner sees a prompt. This works out, from the old and new text, whether
the change makes a check WEAKER, so the prompt can say so plainly. Weaker means any of:
  - an approved row, a check, an assert or a test removed, or a check name / break switch emptied;
  - a skip added (pytest.mark.skip, xfail, [Ignore], DISABLED_, pending(), return at the top of a test, #if 0 ...);
  - an assert replaced by one that always passes (assert True, TestTrue(.., true), EXPECT_TRUE(true));
  - an assert commented out;
  - a limit, tolerance or frozen count raised (a minimum lowered);
  - a protected branch, block rule or guard path removed, or a guard switch turned off;
  - an exception added: an allowed plugin or library, a maths call let through, a licence accepted, a secret allowed.
A guess from text, not a proof: the prompt says "looks weaker" and gives the rule of thumb.
"""
import json, os, re

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

# A project's own test macros count like the test libraries' own (the game's plain cores, 12 Nov: MYHYDRO_TEST(Grid, X)
# { MYHYDRO_EXPECT(...); }: removing one of those checks, or a whole test, was called "doesn't look weaker").
OWN_MACRO = "" if BREAK("tests_own_macros") else "[A-Z][A-Z0-9]*_(?:EXPECT|ASSERT)\\w*|"
OWN_TEST = "" if BREAK("tests_own_macros") else "(?:[A-Z][A-Z0-9]*_)+TEST(?:_F|_P)?\\s*\\(|"
ASSERT = re.compile(r"(?i)\bassert\s+\S|\b(?:" + OWN_MACRO + r"assert\w*|expect\w*|ASSERT_\w+|EXPECT_\w+|TestTrue|TestFalse|TestEqual\w*|TestNotEqual|TestNull|"
                    r"TestNotNull|TestValid|TestInvalid|TestNearlyEqual|AddError|Assert\.\w+|Is\.\w+|should\w*|check\w*|verify\w*|"
                    r"require\w*|fail\w*)\s*[(.!]")
SKIP = re.compile(r"""(?ix)(?:pytest\.mark\.skip|pytest\.mark\.xfail|pytest\.skip\(|pytest\.xfail\(|@unittest\.skip|@skip\b|\.skip\(|
    \[\s*(?:Ignore|Explicit|Skip)\b|\bDISABLED_|\bpending\s*\(|\bxit\s*\(|\bxdescribe\s*\(|\bit\.skip|\btest\.skip|\bdescribe\.skip|
    \bskip_test\b|\bmark_skipped\b|\bpass_test\s*\(\s*["']|Assert\.Ignore|Assert\.Inconclusive|\bGTEST_SKIP|\#\s*if\s+0\b|
    EAutomationTestFlags::Disabled|\bskip\s*=\s*true|\bskip\s*:\s*true|\bif\s*\(\s*true\s*\)\s*return|\bif\s+True\s*:\s*return)""")
ALWAYS_PASS = re.compile(r"""(?ix)(?:\bassert\s+(?:True|1|not\s+False)\s*(?:$|[,#;)])|assert(?:True|_true)\s*\(\s*(?:True|true|1)\s*\)|
    (?:EXPECT|ASSERT)_TRUE\s*\(\s*(?:true|1)\s*\)|TestTrue\s*\([^,]*,\s*true\s*\)|Assert\.(?:IsTrue|True|Pass)\s*\(\s*(?:true)?\s*\)|
    assert_true\s*\(\s*true\s*\)|assertEqual\s*\(\s*(\w+)\s*,\s*\1\s*\)|expect\s*\(\s*true\s*\)\.toBe\s*\(\s*true\s*\))""")
COMMENTED = re.compile(r"^\s*(?://+|#+|--|;+|/\*)\s*")
LOOSER_UP = re.compile(r"(?i)(?:tol|toler|eps|epsilon|delta|margin|abs|rel|approx|error|thresh|max|limit|allow|budget|slack|"
                       r"grace|timeout|ceiling|upper|lines|count|calls|size|growth|nest|decision|percent|pct|fudge|noise)")
STRICTER_UP = re.compile(r"(?i)(?:\bmin|minimum|floor|lower|at_?least|required|coverage|pass_?rate|samples|iterations|runs" +
                         ("" if BREAK("weaken_places") else r"|\bplaces\s*=|\bndigits\s*=|\bdecimals?\s*=|\bprecision\s*=") + ")")
NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
EXCEPT_FILES = re.compile(r"(?i)(secrets_allow\.txt|rules_baseline\.json|assets_baseline\.json|ASSETS\.md|SPHERE_EXCEPTIONS\.md|"
                          r"allow|exception|whitelist|ignore)")
EXCEPT_WORDS = re.compile(r"(?i)\b(?:allow(?:ed)?|accept(?:ed)?|exempt|exception|whitelist|ignore[ds]?|nolint|noqa|fg-ok|"
                          r"suppress\w*|waive[d]?|skip_rules?|pragma\s+warning\s+disable|lint:ignore)\b")
GUARD_KEYS = re.compile(r"(?i)\"?(protected_branches|extra_block|guard_paths|block_while_running|job_patterns|ALWAYS_GUARDED|"
                        r"include|banned|rules|deny|forbid\w*)\"?")
SWITCH_ON = re.compile(r"(?i)\"?(\w*(?:only|guard|require\w*|block\w*|scan|check\w*|enforce\w*|strict|forbid\w*|lock\w*|protect\w*)\w*)\"?\s*[:=]\s*(true|True|1|\"ask\"|\"deny\")")


def _lines(t):
    return [l.rstrip() for l in (t or "").splitlines()]


def _norm(l):
    return re.sub(r"\s+", " ", l.strip())


def _num_pairs(o, l):
    """(old line, new line, old number, new number) for each number that differs between two same-shaped lines."""
    if _norm(o) == _norm(l):
        return []
    return [(o, l, float(x), float(y)) for x, y in zip(NUM.findall(o), NUM.findall(l)) if x != y]


def _num_changes(old, new):
    """Pairs (old line, new line, old number, new number) for lines that differ only in their numbers."""
    out = []
    shape = lambda l: NUM.sub("#", _norm(l))
    pool = {}
    for l in _lines(old):
        pool.setdefault(shape(l), []).append(l)
    for l in _lines(new):
        s = shape(l)
        if pool.get(s):
            out += _num_pairs(pool[s].pop(0), l)
    return out


def _json_load(t):
    t = t.lstrip("\ufeff") if isinstance(t, str) else t
    for x in (t, "{" + t.strip().rstrip(",") + "}"):
        try:
            return json.loads(x)
        except (ValueError, TypeError):
            pass
    raise ValueError


def _walk_dict(x, y, key, why):
    for k in x:
        if k not in y and not k.startswith("_"):
            why.append(f"the setting '{key + k}' was removed")
        elif k in y:
            _walk(x[k], y[k], key + k + ".", why)
    for k in y:
        if k not in x and EXCEPT_WORDS.search(k):
            why.append(f"an exception list '{key + k}' was added")


def _walk_list(x, y, key, why):
    gone = [v for v in x if v not in y]
    added = [v for v in y if v not in x]
    if gone and not EXCEPT_WORDS.search(key):
        why.append(f"entries removed from '{key.rstrip('.')}': " + ", ".join(map(str, gone))[:120])
    if added and EXCEPT_WORDS.search(key):
        why.append(f"exceptions added to '{key.rstrip('.')}': " + ", ".join(map(str, added))[:120])


def _walk_number(x, y, key, why):
    k = key.rstrip(".").split(".")[-1]
    stricter = STRICTER_UP.search(k)
    if (y > x and not stricter) or (y < x and stricter):
        why.append(f"'{key.rstrip('.')}' went from {x} to {y} (looser)")


def _walk(x, y, key, why):
    """Compare two JSON values; append plain reasons when the new one is looser."""
    both = lambda *t: isinstance(x, t) and isinstance(y, t)
    if both(dict):
        _walk_dict(x, y, key, why)
    elif both(list):
        _walk_list(x, y, key, why)
    elif both(bool):
        if x and not y:
            why.append(f"'{key.rstrip('.')}' was switched off")
    elif both(int, float) and x != y:
        _walk_number(x, y, key, why)
    elif both(str) and x != y and x in ("ask", "deny") and y not in ("ask", "deny"):
        why.append(f"'{key.rstrip('.')}' changed from {x} to {y}")


def _json_weaker(path, old, new, why):
    """True when both sides read as JSON (whole file or a fragment of one)."""
    if BREAK("weaken_json"):
        return False
    try:
        a, b = _json_load(old), _json_load(new)
    except ValueError:
        return False
    _walk(a, b, "", why)
    return True


class _Change:
    """One change to one file, cut up the ways the checks below need."""
    def __init__(self, path, old, new):
        self.path, self.old, self.new = path, old or "", new or ""
        self.base = os.path.basename(path or "")
        self.ol, self.nl = _lines(self.old), _lines(self.new)
        self.on, self.nn = [_norm(l) for l in self.ol], [_norm(l) for l in self.nl]
        self.removed = [l for l in self.ol if _norm(l) and _norm(l) not in self.nn]
        self.added = [l for l in self.nl if _norm(l) and _norm(l) not in self.on]
        self.why = []
        self.as_json = bool(path and path.lower().endswith(".json")) and _json_weaker(path, self.old, self.new, self.why)


KEY_OF = re.compile(r"^\s*\"?([\w.-]+)\"?\s*[:=]")
QUOTED = re.compile(r"\"([^\"]*)\"")


def _text_config(c):
    """A text config: same key, fewer quoted entries."""
    keyof = lambda l: (KEY_OF.match(l) or [None, None])[1]
    nk = {keyof(l): l for l in c.nl if keyof(l)}
    for l in c.ol:
        k = keyof(l)
        if not (k and k in nk and GUARD_KEYS.search(k)) or EXCEPT_WORDS.search(k):
            continue
        gone = set(QUOTED.findall(l.split(":", 1)[-1])) - set(QUOTED.findall(nk[k].split(":", 1)[-1]))
        if gone:
            c.why.append(f"entries removed from '{k}': " + ", ".join(sorted(gone))[:100])


ROW_ID = re.compile(r"^\s*\|\s*([A-Za-z][\w.-]*)\s*\|")


def _rows(lines):
    rid = lambda l: (ROW_ID.match(l) or [None, None])[1]
    return {rid(l): l for l in lines if rid(l) and rid(l).lower() != "id"}


def _lost_check(oc, nc):
    return oc[3] and (not nc[3] or nc[3] in ("-", "none") or "~~" in nc[3] or nc[3] != oc[3] and len(nc[3]) < 2)


def _row_cells(k, oc, nc, why):
    if _lost_check(oc, nc):
        why.append(f"approved row {k} lost its check")
    elif oc[3] != nc[3]:
        why.append(f"approved row {k} now names a different check ({oc[3]} -> {nc[3]}); make sure it tests the same thing")
    if oc[4] and (not nc[4] or nc[4] in ("-", "none")):
        why.append(f"approved row {k} lost its break switch, so its check can't be proven")


def _approved_rows(c):
    if not re.search(r"(?i)approved", c.base):
        return
    new_rows = _rows(c.nl)
    cells = lambda l: [x.strip() for x in l.strip().strip("|").split("|")]
    for k, l in _rows(c.ol).items():
        if k not in new_rows:
            c.why.append(f"approved row {k} was removed"); continue
        oc, nc = cells(l), cells(new_rows[k])
        if len(oc) >= 5 and len(nc) >= 5:
            _row_cells(k, oc, nc, c.why)
        if "~~" in new_rows[k] and "~~" not in l:
            c.why.append(f"approved row {k} was struck out")


TEST_START = re.compile(r"^\s*(?:" + OWN_TEST + r"def\s+test\w*|void\s+Test\w*|func\s+test_\w*|\[Test\]|\[UnityTest\]|TEST(?:_F)?\s*\(|"
                        r"IMPLEMENT_\w*AUTOMATION_TEST|it\s*\(|test\s*\()")
TEST_BODY = re.compile(r"^\s*(?:" + OWN_TEST + ("" if BREAK("tests_own_macros") else r"TEST(?:_F|_P)?\s*\(|") + r"def\s+test\w*|void\s+\w*Test\w*|func\s+test_\w*|bool\s+F\w+::RunTest|public\s+void\s+\w+\s*\()")


def _real_assert(a):
    return ASSERT.search(a) and not ALWAYS_PASS.search(a) and not COMMENTED.match(a)


def _removed_assert(c, l):
    if not ASSERT.search(l) or COMMENTED.match(l):
        return
    if any(_norm(COMMENTED.sub("", a)) == _norm(l) for a in c.added):
        c.why.append("a check line was commented out: " + _norm(l)[:80])
    elif not any(_real_assert(a) for a in c.added):
        c.why.append("a check line was removed: " + _norm(l)[:80])


def _early_return(c, i):
    body = [x for x in c.nl[i + 1:i + 4] if x.strip() and not x.strip().startswith(("{", '"""', "'''", "//", "#"))]
    return bool(body) and re.match(r"^\s*return\b(?!\s*\w+\s*\()", body[0]) and _norm(body[0]) not in c.on[max(0, i - 3):i + 6]


CHECK_CALL = re.compile(r"(?i)\b(" + OWN_MACRO + r"ok|assert\w*|check\w*|expect\w*|verify\w*|require\w*|is_true|TestTrue)\s*\(\s*([^,()]*(?:\([^()]*\)[^,()]*)*)")
CONSTANT = re.compile(r"^(?:true|True|TRUE|1|not\s+False|!false)$")


def _check_made_constant(c, l):
    """A check call whose condition became a constant true (the Godot game test, 11 Nov: ok(x == 0.0, ...) became ok(true, ...))."""
    m = CHECK_CALL.search(l)
    if BREAK("weaken_constant") or not m or CONSTANT.match(m.group(2).strip()) or COMMENTED.match(l):
        return
    for a in c.added:
        n = CHECK_CALL.search(a)
        if n and n.group(1) == m.group(1) and CONSTANT.match(n.group(2).strip()):
            c.why.append("a check was replaced by one that always passes: " + _norm(a)[:80]); return


def _tests(c):
    """Asserts and tests removed or commented out, skips and always-pass checks added, early returns."""
    for l in c.removed:
        _removed_assert(c, l)
        _check_made_constant(c, l)
        if TEST_START.match(l) and not any(_norm(l) == _norm(a) for a in c.nl):
            c.why.append("a test was removed: " + _norm(l)[:80])
    for l in c.added:
        if SKIP.search(l):
            c.why.append("a skip was added: " + _norm(l)[:80])
        elif ALWAYS_PASS.search(l):
            c.why.append("a check that always passes was added: " + _norm(l)[:80])
    for i, l in enumerate(c.nl):
        if TEST_BODY.match(l) and _early_return(c, i):
            c.why.append("the test now returns before checking anything")


NEAR = re.compile(r"(?i)near|close|within|isclose|approx|abs=|rel=")


TEXT_RECORD = re.compile(r"(?i)\.(?:md|markdown|txt|rst|adoc)$")
CAP_LABEL = re.compile(r"(?i)(?:max|limit|toler|eps|margin|thresh|budget|slack|grace|timeout|ceiling|upper|under|at most|"
                       r"no more than|within|up to|allow|fail|unproven|not (?:yet )?(?:reached|proven|covered)|missing|left|"
                       r"skipped|growth|over|stale|exception|waive)")
FLOOR_LABEL = re.compile(r"(?i)(?:\bmin|least|floor|lower|proven|covered|coverage|pass|green|done|reached|required)")


def _label(line, x):
    """The words just before the number x in a line of a text record (back to the last , ; | or bracket)."""
    for m in NUM.finditer(line):
        if float(m.group(0)) == x:
            return re.split(r"[,;|()\[\]]", line[max(0, m.start() - 40):m.start()])[-1]
    return ""


def _record_number(c, o, x, y):
    """A number in a text record (a ledger's Counts line), judged by its own label: True when it is not weaker. The
    game's PC, 21 Nov: Docs/TEST_PROOFS.md's counts went "22 -> 23" proven and "186 -> 185" not reached, and the box
    said a frozen number went up. One more test proven is more coverage. None: no label says, judged as before."""
    if BREAK("record_counts") or not TEXT_RECORD.search(c.base):
        return None
    lab = _label(o, x)
    if CAP_LABEL.search(lab):
        return y <= x
    if FLOOR_LABEL.search(lab):
        return y >= x
    rest = re.sub(r"(?i)\bcounts?\b", "", o)              # a ledger's "Counts" heading names no limit
    return None if ("baseline" in c.base.lower() or STRICTER_UP.search(rest) or LOOSER_UP.search(rest) or NEAR.search(rest)) else True


def _numbers(c):
    """Limits, tolerances and frozen counts."""
    for o, n, x, y in _num_changes(c.old, c.new):
        rec = _record_number(c, o, x, y)
        if rec is not None:
            if not rec:
                c.why.append(f"a limit or frozen number went {'up' if y > x else 'down'} ({x:g} -> {y:g}): " + _norm(n)[:70])
            continue
        if STRICTER_UP.search(o) and not LOOSER_UP.search(o.split(":")[0] if ":" in o else o):
            if y < x:
                c.why.append(f"a minimum went down ({x:g} -> {y:g}): " + _norm(n)[:70])
        elif "baseline" in c.base.lower() or LOOSER_UP.search(o) or NEAR.search(o):
            if abs(y) > abs(x):
                c.why.append(f"a limit or frozen number went up ({x:g} -> {y:g}): " + _norm(n)[:70])


def _switch_off(c, l):
    m = SWITCH_ON.search(l)
    if not m:
        return
    k = m.group(1)
    off = re.compile(r"(?i)\b" + re.escape(k) + r"\b\"?\s*[:=]\s*(false|False|0|\"off\"|\"allow\")")
    if any(off.search(a) for a in c.added):
        c.why.append(f"the guard switch '{k}' was turned off")


def _guard_settings(c):
    """Protected lists and guard switches in any text config."""
    if c.as_json:
        return
    for l in c.removed:
        if GUARD_KEYS.search(l) and not any(GUARD_KEYS.search(a) for a in c.added):
            c.why.append("a guard setting was removed: " + _norm(l)[:80])
        _switch_off(c, l)


UNCLEAR_LICENCE = re.compile(r"(?i)\b(accept|waive|exempt|unknown|todo|tbd|not sure|n/?a)\b")
WAIVER = re.compile(r"(?i)\b(?:nolint\w*|noqa|fg-ok|suppress\w*|pragma|lint:ignore|allow\w*|exempt\w*|waive\w*|whitelist\w*)\b")
WAIVER_LOOSE = re.compile(r"(?i)nolint|noqa|fg-ok|suppress|pragma|lint:ignore|allow|exempt|waive|whitelist")   # before v0.8.6
COMMENT_ONLY = re.compile(r"^\s*(?://|#|--|;|/\*|\*|<!--)")
# a comment line counts as a waiver only with a marker a tool reads (the build thread, 11 Nov: a comment saying a guard
# no longer allows cp or mv, in a change that made the guard STRICTER, was called "a waiver was added")
MARKER = re.compile(r"(?i)\b(?:nolint\w*|noqa|fg-ok|pragma|lint:ignore|eslint-disable\S*|pylint:\s*disable|type:\s*ignore|nosec|"
                    r"nosonar|resharper\s+disable|rubocop:\s*disable|istanbul\s+ignore|c8\s+ignore)\b")


# The words of a quoted text in code are a message, not code (the game's PC, 12 Nov: a new test whose message said "not
# allowed" was called "a waiver was added", and one whose message said "doesn't fit (look around" was called a shared
# change, after jasmine's fit(...)). A quoted text with no space in it (a key, a name, a path) still counts.
CODE_EXT = (".py", ".gd", ".cs", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".js", ".mjs", ".cjs", ".mts", ".cts", ".ts", ".tsx",
            ".jsx", ".go", ".java", ".kt", ".swift", ".rb", ".lua", ".sh")
SINGLE_QUOTES = (".py", ".gd", ".rb", ".lua", ".js", ".mjs", ".cjs", ".mts", ".cts", ".ts", ".tsx", ".jsx", ".sh")


def without_prose(line, path):
    """The line with the words of its quoted texts taken out, in a code file."""
    p = (path or "").lower()
    if BREAK("prose_words") or not p.endswith(CODE_EXT):
        return line
    q = r'"(?:[^"\\\n]|\\.)*"' + (r"|'(?:[^'\\\n]|\\.)*'" if p.endswith(SINGLE_QUOTES) else "")
    return re.sub(q, lambda m: m.group(0)[0] * 2 if re.search(r"\s", m.group(0)) else m.group(0), line)


def _is_waiver(line, path=""):
    if BREAK("weaken_comment_waiver"):
        return EXCEPT_WORDS.search(line) and WAIVER_LOOSE.search(line)
    line = without_prose(line, path)
    if COMMENT_ONLY.match(line) and not MARKER.search(line):
        return False
    return bool(EXCEPT_WORDS.search(line) and WAIVER.search(line))


def _exception_file(c):
    real = [a for a in c.added if not a.strip().startswith(("#", "//", "<!--")) and a.strip()]
    if real and c.base.upper() != "ASSETS.MD":
        c.why.append("an exception was added: " + _norm(real[0])[:80])
        return
    acc = [a for a in real if UNCLEAR_LICENCE.search(a)]
    if acc:
        c.why.append("a licence row was accepted without a clear licence: " + _norm(acc[0])[:80])


def _allow_lists(j):
    """{list name: dict of allowed entries} for the allow lists in a JSON record."""
    j = j if isinstance(j, dict) else {}
    return {k: j[k] for k in ("dependencies", "allow", "allowed", "exceptions") if isinstance(j.get(k), dict)}


FIRST_WORDS = "recorded with the first baseline"            # what fg/rules.py --baseline writes beside what it found in use


def _new_allowances(c):
    """JSON allow lists (rules_baseline.json and the like): every newly allowed entry. Weaker-model test (9 Nov): a helper
    ran --allow itself, quoting the owner's request, and the summary still said nothing needed the owner.
    Beginner test (11 Nov): the first upload showed a 'made weaker' card for the record setup had just written (the test
    library the project already used). A record with no earlier version is not weaker than anything; what somebody
    allowed in their own words still shows, and so does every entry added to a record that already existed."""
    if BREAK("weaken_json_allow") or not c.as_json:
        return
    try:
        old, new = _allow_lists(_json_load(c.old)), _allow_lists(_json_load(c.new))
    except ValueError:
        return
    first = not c.old.strip() and not BREAK("weaken_first_record")
    for key, y in new.items():
        for k in sorted(set(y) - set(old.get(key, {}))):
            words = y[k].get("words", "") if isinstance(y[k], dict) else ""
            if first and words == FIRST_WORDS:                  # a record that is new in this push, writing down today's state
                continue
            c.why.append(f"outside software was allowed: {k}" + (f' (words given: "{words[:80]}")' if words else ""))


def _exceptions(c):
    """Allow lists, accepted licences, waivers."""
    if BREAK("weaken_exceptions"):
        return
    if EXCEPT_FILES.search(c.base):
        _new_allowances(c)
    if EXCEPT_FILES.search(c.base) and c.added and not c.as_json:
        _exception_file(c)
    if EXCEPT_FILES.search(c.base) or any(EXCEPT_WORDS.search(r) for r in c.removed):
        return
    a = next((a for a in c.added if _is_waiver(a, c.path)), None)
    if a is not None:
        c.why.append("a waiver was added: " + _norm(a)[:80])


def weaker(path, old, new):
    """Plain reasons the change looks weaker (empty list = it doesn't look weaker)."""
    if BREAK("weaken_find"):
        return []
    c = _Change(path, old, new)
    if not c.as_json:
        _text_config(c)
    for part in (_approved_rows, _tests, _numbers, _guard_settings, _exceptions):
        part(c)
    return list(dict.fromkeys(c.why))


def for_the_box(path, old, new):
    """The reasons the owner's box gives: weaker()'s, or, when it found none but an existing check line changed, that
    the kit can't tell (F259). Only the box: the upload's own judgement stays weaker()'s."""
    out = weaker(path, old, new)
    if out or BREAK("weaken_unsure"):
        return out
    c = _Change(path, old, new)
    gone = [l for l in c.removed if ASSERT.search(l) or CHECK_CALL.search(l)]
    if gone:
        return [f"{UNSURE}: '{_norm(gone[0])[:80]}'"]
    return [] if BREAK("weaken_say_change") else _what_changed(c)


def _what_changed(c):
    """Outside review 7: the box with no weakening found names the change in one line, so an owner who sees it often
    reads what it is instead of learning to click Yes."""
    o, n = (_norm(c.removed[0]) if c.removed else ""), (_norm(c.added[0]) if c.added else "")
    o, n = _around_change(o, n)
    more = len(c.removed) + len(c.added) > 2
    if o and n:
        return [f"{CHANGE}'{o}' becomes '{n}'" + (" (and more)" if more else "")]
    if o or n:
        return [f"{CHANGE}{'removes' if o else 'adds'} '{o or n}'" + (" (and more)" if more else "")]
    return []


def _around_change(o, n, width=80, lead=30):
    """The game's PC, 21 Nov: a long APPROVED.md row changed late in the line, and both sides were cut at 80 characters
    before the part that changed, so the box showed two identical strings. Each side now starts a little before the
    first character that differs."""
    if BREAK("change_centred") or not (o and n):
        return o[:width], n[:width]
    p = next((i for i, (a, b) in enumerate(zip(o, n)) if a != b), min(len(o), len(n)))
    if p + 10 <= width:
        return o[:width], n[:width]
    start = max(0, p - lead)
    cut = lambda t: "..." + t[start:start + width]
    return cut(o), cut(n)


CHANGE = "the change: "
UNSURE = "a check line was changed, and the kit can't tell whether that makes it weaker"
RULE = ("Rule of thumb: if a change makes a check weaker, say NO unless you asked for it. "
        "If you didn't ask, ask the helper to explain it in a new message first.")


def prompt_text(path, reasons):
    """The kit's question to the owner about a change to a guard file: what is asked, then why (fg/agents.py adds
    what to click). 11 Nov: every ask in one line."""
    said = "".join(" " + r[0].upper() + r[1:] + "." for r in reasons if r.startswith(CHANGE))
    reasons = [r for r in reasons if not r.startswith(CHANGE)]
    if reasons and all(r.startswith(UNSURE) for r in reasons):
        return (f"may the helper change '{path}'? Why: this file protects your project, and THIS MAY BE WEAKER: " +
                "; ".join(reasons[:2]) + ". Read the change, or ask the helper why it changed that check. " + RULE)
    if reasons:
        return (f"may the helper change '{path}'? Why: it is a guard file and THIS LOOKS WEAKER: " + "; ".join(reasons[:4]) +
                ("; and more" if len(reasons) > 4 else "") + ". " + RULE)
    return (f"may the helper change '{path}'? Why: this file protects your project (a test, a check, an approval or "
            "the kit itself), so only you can OK a change to it." + said + " The kit can't always tell whether a change "
            "makes a check weaker: if you didn't ask for this, ask the helper why first.")

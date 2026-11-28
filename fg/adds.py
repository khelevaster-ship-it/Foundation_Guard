"""FoundationGuard: a helper may add tests without asking (AI-made, Claude, 2026-11-11).

The game's first real morning (11 Nov): every new test a helper wrote opened the owner's permission box, so the owner
was asked again and again about changes that only add checks. Now, with the setting "helpers_add_tests" (on unless the
owner turns it off), a change to a test file that only ADDS goes through without asking:
  - a new test file, whose name says it is a test (test_x.py, x_test.go, LoadTests.cs, x.spec.ts, test_x.gd ...);
  - new tests added to an existing test file, between or after the tests already there.
Everything else still asks the owner, with the weakening finder exactly as strict as before: a test removed, changed,
renamed or skipped; a line added inside an existing test; a new test with a name already used (in Python the new one
replaces the old); a new line at the top level that could change what the other tests see (x.y = ..., setattr,
sys.modules, #define, a set-up step or fixture added to an existing file); a test-runner setting file (conftest.py,
pytest.ini, .gutconfig.json); the approved list, the kit, its settings and its hooks.

Gathering the asks ("gather_asks", off unless the owner turns it on): the other changes to tests and the owner's own
guard files go through without a box each, and the upload then stops until the owner has looked at them all at one
sitting (python fg/ownerok.py lists them; --give says yes once). The kit, its settings, its hooks and its frozen
numbers still ask at once, because they change the guard for the rest of the session.

A guess from text, like the weakening finder: an added test can still change what other tests see in ways this does
not read. The approved list's break-to-prove (nightly) still catches an approved check that no longer bites.
"""
import difflib, os, re

import paths as P
import weaken as W
import addchecks as AC

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
CODE = (".py", ".gd", ".cs", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".js", ".mjs", ".cjs", ".mts", ".cts", ".ts", ".tsx", ".jsx", ".go", ".java",
        ".kt", ".swift", ".rb", ".lua")
TEST_NAME = re.compile(r"(?:^|/)(?:test_[^/]*|[^/]*_test\.\w+|[^/]*[._]spec\.\w+|[^/]*\.test\.\w+)$|"
                       r"(?:^|/)[^/]*(?:Test|Tests|Spec)\.\w+$")
NOT_TEST = re.compile(r"(?i)(?:^|/)(?:conftest\.py|__init__\.py|setup\.py|[^/]*\.build\.cs|[^/]*\.target\.cs)$")
TEST_HEAD = re.compile(r"""^\s*(?:(?:async\s+)?def\s+(test\w*)|func\s+(test\w*)|class\s+(Test\w*)|
                            (?:public\s+|private\s+|static\s+|async\s+)*(?:void|Task|IEnumerator)\s+(\w+)\s*\(|
                            """ + ("" if BREAK("tests_own_macros") else "(?:[A-Z][A-Z0-9]*_)*") + r"""TEST(?:_F|_P)?\s*\(\s*(\w+\s*,\s*\w+)|IMPLEMENT_\w*AUTOMATION_TEST\s*\(\s*(\w+)|
                            bool\s+(F\w+)::RunTest|(?:it|test|describe)\s*\(\s*['"`]([^'"`]+))""", re.X)
HELPER = re.compile(r"^\s*(?:(?:async\s+)?def|func|function|class)\s+(\w+)")
FRAME = re.compile(r"""^\s*(?:$|\#(?!\s*(?:define|undef|if|pragma))|//|/\*|\*|@|\[\w+|[\]\)\}]+\s*[;,]?\s*$|\{\s*$)""", re.X)
COMMENT = re.compile(r"^\s*(?:\#(?!\s*(?:define|undef|if|pragma))|//)")
OPENERS = (('"""', '"""'), ("'''", "'''"), ("/*", "*/"), ("{", "}"))
SET_UP = re.compile(r"(?i)\b(?:autouse|pytestmark|setup_module|setup_function|setup_class|setup_method|teardown_\w*|setUp\w*|"
                    r"tearDown\w*|before_each|before_all|after_each|after_all|beforeEach|beforeAll|afterEach|afterAll|"
                    r"OneTimeSetUp|OneTimeTearDown|SetUp|TearDown|BeforeEach|AfterEach|@pytest\.fixture|@fixture)\b")
PATCH = re.compile(r"""(?x)\bsetattr\s*\(|__setattr__|\bsys\.modules\b|\b__builtins__\b|\bbuiltins\.|\bimportlib\.reload\b|
                       \bvars\s*\(|__dict__|\bglobals\s*\(|\b(?:exec|eval)\s*\(|\b(?:global|nonlocal)\s+\w|\bdel\s+[\w.]*\.|
                       \bpytest_plugins\b|\bpytest\.exit\b|\bsys\.exit\b|\bos\._exit\b|^\s*(?:exit|quit)\s*\(|get_tree\(\)\.quit|
                       Application\.Quit|RequestExit|\.only\s*\(|\bfit\s*\(|\bfdescribe\s*\(|SetUpFixture|AssemblyInitialize|
                       \[\s*assembly\s*:|ModuleInitializer|RuntimeInitializeOnLoad|InitializeOnLoad|\bset_setting\s*\(|\bSetValue\s*\(|
                       \bos\.environ\s*(?:\[[^\]]*\]\s*=(?!=)|\.(?:update|setdefault|pop)\b)|\b(?:os\.)?putenv\b|
                       \bpatch\b[^\n]*\.start\s*\(|^\s*\#\s*(?:define|undef)\b|::\w+\s*=(?!=)""" +
                   ("" if BREAK("adds_class_defaults") else r"|\bGetMutableDefault\s*<"))
# Name.member = value: in Python, Lua, C# or Java the name may be a module or a class every test shares. In C++ a "."
# reaches into an object, and statics use "::", so there it is shared only when the object is not one the new lines
# made themselves (the game's PC, 12 Nov: 44 of the game's 94 test files would ask if written new, for lines such as
# "Params.Seed = 5;" inside the test).
MEMBER_SET = re.compile(r"^\s*([A-Z]\w*)(?:\.\w+)*\.\w+\s*(?:[-+*/]?=)(?!=)")
CPP = (".cpp", ".cc", ".cxx", ".h", ".hpp")
NOT_TYPE = {"return", "delete", "new", "throw", "case", "goto", "else", "do", "sizeof", "co_return", "co_yield",
            "co_await", "using", "typedef", "friend", "operator", "template", "typename", "class", "struct", "union",
            "enum", "public", "private", "protected", "if", "while", "for", "switch", "namespace", "and", "or", "not"}
DECL = re.compile(r"(?<![\w.>])([A-Za-z_][\w:]*(?:\s*<[^;(){}&|]*>)?)\s*(&{1,2}|\*+&?)?\s*\b([A-Za-z_]\w*)\s*"
                  r"(?=[;=,(){\[]|:(?!:))")
BOUND = re.compile(r"\s*(?:=|:(?!:))\s*[*&]?\s*([A-Za-z_][\w:]*)")
SCOPE = re.compile(r"\b(?:namespace|struct|class|union)\s+([A-Za-z_]\w*)")
IMPORTED = re.compile(r"^\s*(?:import\s+([\w.]+)(?:\s+as\s+(\w+))?|from\s+[\w.]+\s+import\s+\(?([\w ,]+)\)?)")
# Two outside reviews, 12 Nov (claim C4): a new test changed what the other tests see, with no ask, by changing a shared
# value in place rather than setting it: shared.config["value"] = 1, config.clear() after "from shared import config",
# GlobalState.items.clear() (a Godot autoload), and in C++ a name the test didn't make, set bare (Shared = 0;).
WIDER = lambda k: os.environ.get("FG_BREAK", "") == ""        # off under any break, so each older row is proven alone
CHANGES_IN_PLACE = (r"append|extend|insert|pop|remove|clear|update|setdefault|popitem|add|discard|sort|reverse|"
                    r"push_back|push_front|pop_back|pop_front|erase|remove_at|resize|fill|shuffle|merge|push|shift|"
                    r"unshift|splice|Add|AddUnique|Append|Emplace|Empty|Reset|Remove|RemoveAt|RemoveAll|RemoveSingle|"
                    r"Insert|Pop|Push|SetNum|Sort|Clear")
IN_PLACE = re.compile(r"^\s*(?:del\s+)?([A-Za-z_]\w*(?:::\w+)*)((?:(?:\.|->)\w+)*)\s*(?:"
                      r"(?:\[[^\]]+\]\s*)+(?:(?:[-+*/%|&^]|//|<<|>>|\*\*)?=(?!=)|$)|"
                      r"(?:\.|->)(?:" + CHANGES_IN_PLACE + r")\s*\()")
CPP_BARE_SET = re.compile(r"^\s*(?:(?:\+\+|--)\s*([A-Za-z_]\w*)\s*$|([A-Za-z_]\w*)\s*(?:(?:[-+*/%|&^]|<<|>>)?=(?!=)|\+\+|--))")
LOCAL = re.compile(r"^\s*(?:(?:var|let|const|local|auto)\s+([A-Za-z_]\w*)|([A-Za-z_]\w*)\s*(?::[^=\n]+)?=(?!=))|"
                   r"\bfor\s+([A-Za-z_]\w*)(?:\s*,\s*([A-Za-z_]\w*))?\s+in\b|\bas\s+([A-Za-z_]\w*)|"
                   r"\b[A-Z]\w*(?:<[^<>;=]*>)?(?:\[\])?\s+([A-Za-z_]\w*)\s*[=;]")
PARAMS = re.compile(r"(?:def|func|function)\s+\w+\s*\(([^)]*)\)")


def named_check(path, cfg):
    """Is this one of the project's own check scripts that the owner named as tests (test_files)? The game's PC, 12 Nov:
    a new Tools/Scripts/x_check.sh asked the owner, because its name doesn't say "test"."""
    names = [] if not cfg or BREAK("adds_test_files") else list(cfg.get("test_files") or [])
    return bool(names) and P.matches((path or "").replace("\\", "/"), names)


def is_test_file(path, cfg=None):
    p = (path or "").replace("\\", "/")
    return named_check(p, cfg) or p.endswith(CODE) and bool(TEST_NAME.search(p)) and not NOT_TEST.search(p)


def _indent(l):
    return len(l) - len(l.lstrip())


def _name(l):
    m = TEST_HEAD.match(l)
    return next((g for g in m.groups() if g), None) if m else None


def _names(lines):
    out = set()
    for l in lines:
        n = _name(l) or (HELPER.match(l).group(1) if HELPER.match(l) else None)
        if n:
            out.add(re.sub(r"\s+", "", n))
    return out


def _imported(lines):
    """Names a file binds by import: changing an attribute of one changes it for every test (a patch)."""
    out = set()
    for l in lines:
        m = IMPORTED.match(l)
        if m:
            if m.group(3):
                out |= {x.strip().split(" as ")[-1].strip() for x in m.group(3).split(",") if x.strip()}
            else:
                out.add(m.group(2) or m.group(1).split(".")[0])
    return out


def _modules(lines):
    """The names bound by "import x" (a module, whose own functions such as random.shuffle(xs) only take values);
    the rest of _imported are values taken from one ("from shared import config"), which a call can change."""
    return {(m.group(2) or m.group(1).split(".")[0]) for m in map(IMPORTED.match, lines) if m and not m.group(3)}


def _locals(lines):
    """Names these lines make themselves in a language other than C++: a var, let, const or local; a name set with =;
    a loop name; an "as" name; a typed declaration (List<int> Items = ...); a function's parameters."""
    out = set()
    for l in lines:
        for m in LOCAL.finditer(l):
            out |= {g for g in m.groups() if g}
        for m in PARAMS.finditer(l):
            out |= set(re.findall(r"(?:^|,)\s*\*{0,2}([A-Za-z_]\w*)", m.group(1)))
    return out


def _statements(line):
    """A line's statements one by one, with a leading if (...), while (...) or else taken off: "if (Ok) { Shared = 0; }"."""
    out = []
    for piece in re.split(r"[;{}]", line):
        piece = piece.strip()
        while True:
            m = re.match(r"^(?:else\b\s*)?(?:(?:if|while|for|elif)\b\s*)?", piece)
            rest = piece[m.end():] if m and m.end() else None
            if rest is None:
                break
            if rest.startswith("("):
                depth = 0
                for i, ch in enumerate(rest):
                    depth += (ch == "(") - (ch == ")")
                    if depth == 0:
                        rest = rest[i + 1:]
                        break
                else:
                    rest = ""
            if rest.strip() == piece:
                break
            piece = rest.strip()
        if piece:
            out.append(piece)
    return out


def _cpp_declared(lines):
    """C++ names these lines declare as a value or a pointer (setting one again changes only the test's own name; a
    reference is different, it changes what it is bound to), and arrays passed by reference (FSkyPlace (&Out)[4])."""
    text = "\n".join(lines)
    out = {m.group(3) for m in DECL.finditer(text)
           if not (m.group(2) or "").startswith("&") and m.group(1).split("<")[0].strip() not in NOT_TYPE}
    out |= set(re.findall(r"\}\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*[=;]", text))      # struct { ... } Known[] = { ... }
    return out | set(re.findall(r"\(\s*[&*]+\s*([A-Za-z_]\w*)\s*\)\s*\[", text))


def _member_bodies(lines):
    """For each line, whether it sits in the body of a class's own function (void Context::Note(...) { ... }), where a
    bare name can be the object's own member. Not an automation test's own RunTest or Define: those classes have no
    members of their own, so a bare name there is shared."""
    text = "\n".join(lines)
    tests = {a or b for a, b in re.findall(r"IMPLEMENT_\w*AUTOMATION_TEST\w*\s*\(\s*(\w+)|BEGIN_DEFINE_SPEC\s*\(\s*(\w+)", text)}
    depth, start, opened, out = 0, None, False, []
    for l in lines:
        m = re.match(r"^\s*(?:[\w:<>,*&]+\s+)*[*&]*([A-Za-z_]\w*)::~?[A-Za-z_]\w*\s*\(", l)
        if start is None and m and m.group(1) not in tests and not l.rstrip().endswith(";"):
            start, opened = depth, False
        out.append(start is not None)
        depth += l.count("{") - l.count("}")
        opened = opened or (start is not None and "{" in l)
        if start is not None and opened and depth <= start:
            start = None
    return out


def _changed_in_place(added, all_lines, path, own):
    """An added line that changes a shared value in place: an item set or deleted, or a call that changes it."""
    if not WIDER("adds_in_place"):
        return None
    cpp = (path or "").lower().endswith(CPP)
    mods, taken = _imported(all_lines), _imported(all_lines) - _modules(all_lines)
    mine = set() if cpp else _locals(added)
    if cpp:
        own = own | _cpp_declared(added)
    members = _member_bodies(added) if cpp else [False] * len(added)
    for l, member in zip(added, members):
        if member:
            continue                                  # a class's own function may set its own members
        for st in _statements(W.without_prose(l, path or ".py")):
            m = IN_PLACE.match(st)
            if m:
                head, chain = m.group(1).split("::"), m.group(2)
                calls = "(" in st[m.start(2) + len(chain):] and not re.match(r"\s*\[", st[m.end(2):])
                if cpp:
                    shared = m.group(1) != "this" and not all(x in own for x in head)
                elif head[0] in mods:
                    shared = not calls or bool(chain) or head[0] in taken   # random.shuffle(xs) only takes a value
                else:
                    shared = head[0][:1].isupper() and head[0] not in mine and not (head[0] == "sys" and chain == ".path")
                if shared and not (head[0] == "sys" and chain.startswith(".path")):
                    return "it changes something every test shares: " + st[:80]
            b = CPP_BARE_SET.match(st) if cpp else None
            name = b and (b.group(1) or b.group(2))
            if name and name not in own and name not in NOT_TYPE and name != "this":
                return "it changes something every test shares (a name the test didn't make): " + st[:80]
    return None


def _cpp_own(lines):
    """The names that these C++ lines make themselves: a value they declare (FMyParams Params; TArray<FX> Results;),
    a parameter, a namespace or struct, and a reference or pointer bound to one of those (FX& R = Results[L];
    for (FX& F : Fixtures)). Setting a member of one changes only what these lines own."""
    text = "\n".join(lines)
    own = set(SCOPE.findall(text))
    bound = []
    for m in DECL.finditer(text):
        kind, name = m.group(2), m.group(3)
        if m.group(1).split("<")[0].strip() in NOT_TYPE or name in NOT_TYPE:
            continue
        after = text[m.end():]
        b = BOUND.match(after)
        if not kind or after[:1] in ",)":            # a value, or a parameter
            own.add(name)
            if not kind:                              # FMyTribe Lean = A, Stand = A;
                own.update(_more_names(after))
        elif b:
            bound.append((name, b.group(1)))
    def made_here(base):
        parts = [x for x in base.split("::") if x]
        return bool(parts) and all(x in own for x in parts)
    for _ in range(len(bound)):                       # a reference to a reference to a value made here
        grew = [n for n, b in bound if n not in own and made_here(b)]
        if not grew:
            break
        own.update(grew)
    return own


def _more_names(after):
    """The other names one declaration makes (", Stand = A" in FMyTribe Lean = A, Stand = A;)."""
    stmt = after.split(";")[0]
    for _ in range(8):
        stmt, n = re.subn(r"\([^()]*\)|\{[^{}]*\}|<[^<>;]*>", "", stmt)
        if not n:
            break
    if re.search(r"[(){}]", stmt):
        return set()
    return set(re.findall(r",\s*[*&]?\s*([A-Za-z_]\w*)\s*(?=[=,{\[]|$)", stmt))


def _patches(added, all_lines, path=""):
    """An added line that changes something shared by every test: a reason to ask."""
    mods = _imported(all_lines)
    own = _cpp_own(added) if (path or "").lower().endswith(CPP) and not BREAK("adds_cpp_own") else set()
    for l in added:
        if PATCH.search(W.without_prose(l, path or ".py")):
            return "it changes something every test shares: " + l.strip()[:80]
        m = MEMBER_SET.match(l)
        if m and m.group(1) not in own:
            return "it changes something every test shares: " + l.strip()[:80]
        m = re.match(r"^\s*([A-Za-z_]\w*)\.[\w.]+\s*(?:[-+*/]?=)(?!=)", l)
        if m and m.group(1) in mods:
            return "it changes something every test shares: " + l.strip()[:80]
    return _changed_in_place(added, all_lines, path, own)


def _balanced(block):
    t = "\n".join(block)
    return all((t.count(a) % 2 == 0) if a == b else (t.count(a) == t.count(b)) for a, b in OPENERS)


def _block_ok(block, before, after, old_names):
    """One run of lines added to a test file that is already there: whole new tests (or new helpers) only, sitting
    between the tests already there, with nothing left open that could swallow them."""
    if not _balanced(block):
        return "it opens something it doesn't close (a string, a comment or a brace), which could swallow a test"
    code = [l for l in block if l.strip() and not FRAME.match(l)]
    if not code:
        odd = next((l for l in block if l.strip() and not COMMENT.match(l)), None)
        return ("it adds a line that is not a new test: " + odd.strip()[:80]) if odd else None
    prev = next((l for l in reversed(before) if l.strip()), "")
    if re.match(r"^\s*(?:@|\[\w+)", prev):
        return "the new lines sit between a test and its marks (" + prev.strip()[:60] + ")"
    base = _indent(code[0])
    if not (_name(code[0]) or HELPER.match(code[0])):
        return "it adds lines that are not a new test: " + code[0].strip()[:80]
    for l in block:
        if not l.strip():
            continue
        if _indent(l) < base:
            return "it adds lines outside the new test: " + l.strip()[:80]
        top = _indent(l) == base
        if top and not (FRAME.match(l) or _name(l) or HELPER.match(l)):
            return "it adds a line beside the tests, not in one: " + l.strip()[:80]
        if SET_UP.search(l):
            return "it adds a set-up step that could change the tests already there: " + l.strip()[:80]
        n = (_name(l) or (HELPER.match(l).group(1) if HELPER.match(l) else None)) if top else None
        if n and re.sub(r"\s+", "", n) in old_names:
            return "a test or helper with that name is there already (the new one would replace it): " + n
    nxt = next((l for l in after if l.strip()), None)
    if nxt is not None and _indent(nxt) > base:
        return "the new lines sit inside a test that is already there"
    return None


def only_adds(path, old, new, cfg=None):
    """None when a change to this test file only adds new tests (no ask), else the plain reason it still asks."""
    if BREAK("adds_free"):
        return "the owner's yes is asked for every change"
    if not is_test_file(path, cfg):
        why = _adds_a_check(path, old, new, cfg)
        if why is not False:
            return why
        if BREAK("not_test_said_plain"):
            return "it is not a test file"
        # the game's PC, 21 Nov: a new file of helpers under Private/Tests/ was told to the owner as "it is not a test
        # file", which read as wrong. Say what the kit sees: its name doesn't mark it as one, so it can't tell.
        return ("its name doesn't mark it as a test file (like FooTests.cpp or test_foo.py), so the kit can't tell its "
                "lines only add tests; helpers the tests call can change what they check")
    reasons = W.weaker(path, old, new)
    if reasons:
        return "; ".join(reasons[:2])
    if BREAK("adds_strict"):
        return None
    ol, nl = old.split("\n") if old else [], new.split("\n")
    existing = bool(old.strip())
    if not existing:
        if named_check(path, cfg):            # a new check script the owner named as one: a test, and a program of its own
            return None
        if not any(_name(l) for l in nl):
            return "the new file holds no test"
        return _patches(nl, nl, path)
    old_names, added, later = _names(ol) | _imported(ol), [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ol, nl, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op == "replace" and AC.recorded_fill(ol[i1:i2], nl[j1:j2]):
            continue                                    # a recorded value written where it was 0 (F548)
        if op != "insert":
            return "it changes or removes lines that were there"
        why = _block_ok(nl[j1:j2], nl[:j1], nl[j2:], old_names)
        if why:
            later.append((why, j1, j2))
        added += nl[j1:j2]
    defined = AC.new_functions(added)
    for why, j1, j2 in later:                           # a new case's count added to the total (F549)
        if not AC.accumulates(nl[j1:j2], nl[:j1], nl[j2:], ol, defined):
            return why
    return _patches(added, nl, path)


def _adds_a_check(path, old, new, cfg=None):
    """For a guard file whose name doesn't mark it as a test: None when the change only adds a check or raises a floor
    (fg/addchecks.py, the owner 24 Nov) or only adds rows to a ledger the owner listed (fg/ledgers.py, 28 Nov), a
    reason when such a rule finds it doesn't, or False when none applies."""
    import ledgers as LG
    r = LG.judge(cfg, path, old, new)
    if r is not False:
        return r
    r = AC.floor_raise(path, old, new)
    if r != "":
        return r
    if AC.new_record(path, old, new):
        return None
    if not (path or "").lower().endswith((".sh", ".bash")) or not (old or "").strip():
        return False
    ol, nl = old.split("\n"), new.split("\n")
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ol, nl, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op != "insert":
            return "it changes or removes lines that were there"
        why = AC.shell_block(nl[j1:j2], ol)
        if why:
            return why
    return None


def after_edit(tool, ti, before):
    """The whole file after an editing tool's change, or None when it can't be worked out (then the owner is asked)."""
    if tool == "Write":
        return ti.get("content", "")
    edits = ti.get("edits") if tool == "MultiEdit" else [ti] if tool == "Edit" else None
    text = before
    for e in edits or [None]:
        old, new = (e or {}).get("old_string"), (e or {}).get("new_string", "")
        if not old or old not in text:
            return None
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def owners_own(cfg, f):
    """A guard file the owner listed (tests, check scripts, decision docs), not the kit, its settings, hooks, frozen
    numbers or records, and not one the owner said is never to be changed."""
    import config as C, ownerok as OK, paths as P
    kit = C.ALWAYS_GUARDED + OK.KIT_CODE + [cfg.get("approved_file") or "", cfg.get("merge_signoff_file") or ""]
    state = (cfg.get("state_dir") or ".foundationguard").strip("/") + "/**"
    return not P.matches(f, [k for k in kit if k] + [state]) and C.decision_for(cfg, f) != "deny"


def free_reason(cfg, f, tool, ti, full):
    """None when this edit only adds tests to a test file the owner listed, and the owner lets helpers do that; else
    the plain reason it asks (said in the box, the game's PC, 12 Nov: the owner and the helper couldn't tell why)."""
    if not cfg.get("helpers_add_tests", True) and not BREAK("adds_setting"):
        return "the owner turned helpers_add_tests off"
    if not owners_own(cfg, f):
        return "it is the kit, its settings or records, or a file the owner set to deny"
    try:
        before = open(full, encoding="utf-8", errors="replace").read() if os.path.exists(full) else ""
    except OSError:
        return "the file couldn't be read"
    after = after_edit(tool, ti, before)
    if after is None:
        return "the kit couldn't work out the file after the change"
    if before and not BREAK("tests_edit_until_commit") and uncommitted(cfg, f, full):
        before = ""                     # the owner, 12 Nov: a night's own new test is judged as new until its first commit
    return only_adds(f, before, after, cfg)


def uncommitted(cfg, f, full):
    """A test file of the owner's own guard that isn't in the last commit (new, or only staged), and is that file
    itself: not a link, not through a linked folder, not a second name (a hard link) for another file, and no committed
    file has its name in another case (Windows opens tests/Test_A.cpp as the committed tests/test_a.cpp)."""
    import subprocess
    if not is_test_file(f, cfg) or not owners_own(cfg, f) or not cfg.get("helpers_add_tests", True) or os.path.isdir(full):
        return False
    git = lambda *a: subprocess.run(["git", "-C", cfg["_root"]] + list(a), capture_output=True)
    rel = f.replace("\\", "/")
    if BREAK("uncommitted_is_itself"):
        return git("cat-file", "-e", "HEAD:" + rel).returncode != 0
    try:
        if os.path.islink(full) or (os.path.exists(full) and os.stat(full).st_nlink > 1):
            return False
        real = os.path.normcase(os.path.realpath(full))
        if real != os.path.normcase(os.path.join(os.path.realpath(cfg["_root"]), *rel.split("/"))):
            return False                # a linked folder on the way: the file is somewhere else
    except OSError:
        return False
    if git("rev-parse", "-q", "--verify", "HEAD^{commit}").returncode != 0:
        return False                    # no commit at all, or not a git project: nothing can be told apart
    names = git("ls-tree", "-r", "-z", "--name-only", "HEAD")
    if names.returncode != 0:
        return False
    have = {n.decode("utf-8", "replace").casefold() for n in names.stdout.split(b"\0") if n}
    return rel.casefold() not in have


def free(cfg, f, tool, ti, full):
    """True when this edit only adds tests to a test file the owner listed, and the owner lets helpers do that."""
    return free_reason(cfg, f, tool, ti, full) is None


def box_hours_now(cfg, now=None):
    """The owner, 23 Nov: boxes any time 07:00-23:00, none overnight. "box_hours": "07:00-23:00" (the computer's own
    clock) asks every guard change in a box inside those hours, even with the reviewer lane or gathered asks on; outside
    them those settings work as before. A window may run past midnight ("22:00-06:00")."""
    span = str(cfg.get("box_hours") or "")
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", span)
    if not m or BREAK("box_hours"):
        return False
    import time
    t = time.localtime(now)
    at, a, b = t.tm_hour * 60 + t.tm_min, int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
    return a <= at < b if a <= b else (at >= a or at < b)


def gathering(cfg, f, weaker=False):
    """True when the owner chose to answer the asks at one sitting and this file may wait for the upload, or (review
    lane, the owner 16 Nov) when this technical change goes to the reviewer at the upload instead of a box."""
    import review as RV
    if box_hours_now(cfg):
        return False
    if RV.on(cfg) and not weaker and not BREAK("review_gather") and not RV.owner_only(cfg, f):
        return True
    if not cfg.get("gather_asks") or BREAK("gather_off"):
        return False
    return BREAK("gather_kit") or owners_own(cfg, f)

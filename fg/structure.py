"""FoundationGuard structure check (AI-made, Claude, 2026-11-08).

Guards the slow damage tests can't see: files and classes that balloon, classes smeared across many files (C# partial
classes, C++ methods spread over .cpp files), and systems reaching into each other's insides.

Config (foundationguard.json, key "structure"):
  "include": ["Source/**/*.cpp", "Source/**/*.h"],   globs on repo-relative paths (git-tracked files only)
  "exclude": ["Source/ThirdParty/**"],
  "max_file_lines": 1500,       a file longer than this fails
  "max_class_lines": 1000,      a class whose code (all its parts, in every file) is longer than this fails
  "max_class_files": 4,         a class spread over more files than this fails (stops "fixing" size by splitting)
  "max_function_lines": 300,    a single function longer than this fails (C-family languages and Python)
  "max_growth_lines": 400,      a file that grew more than this since base_ref is flagged
  "growth_blocks": false,       true = that flag fails the gate; false = warning only
  "base_ref": "origin/main",
  "boundaries": [{"files": "Source/Weather/**", "may_not_use": ["Water/Private/"], "why": "water talks through WaterAPI.h"}],
                                "files" may be one glob or a list; "exclude": [globs] leaves files out of a rule
  "baseline_file": "structure_baseline.json",
  "ignore_classes": ["std::*"],  class names never counted (fnmatch); std:: specialisations (std::hash<...>) by default
  "fix_room_lines": 10,         a file, class or function already over its limit may stand up to this many lines over
                                its recorded size, so a small bug fix can go in (after the Godot game test, 11 Nov: a 3-line
                                fix in a 20,401-line file was refused). The recorded size never rises by itself, so the
                                room does not add up over many uploads.
Classes are named with their namespace (MyHydro::Aquifer::State), so same-named structs in different namespaces are
different classes; template specialisations keep their arguments; a class in an anonymous namespace belongs to its file.
Boundaries are regexes matched against include/import/using lines of the files the rule covers.

The baseline records today's oversized files and classes. They may shrink but not grow past fix_room_lines; new code
must meet the limits.
  python fg/structure.py                     check (exit 1 on a failure)
  python fg/structure.py --ratchet           lower the baseline to today's sizes (only ever tightens)
  python fg/structure.py --baseline "why"    (re)write the baseline: logged with its reason in STRUCTURE_LOG.md
  python fg/structure.py --shrink            the shrink rule's own report: owed shrinks, pay-later lines, its books
  python fg/structure.py --shrink --add PATH "why"   list a file that sits exactly at max_file_lines (the owner's box)
The shrink rule (fg/shrink.py, "structure" -> "shrink"): a listed piece an item changes must be smaller when it closes.
"""
import datetime, fnmatch, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import design as D
import funcs as FN

CLIKE = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".inl", ".cs", ".java", ".kt", ".swift", ".go") + FN.JS_EXT
DEFAULTS = {"include": ["**/*"], "exclude": [], "max_file_lines": 1500, "max_class_lines": 1000, "max_class_files": 4, "max_function_lines": 300,
            "max_growth_lines": 400, "growth_blocks": False, "base_ref": "origin/main", "boundaries": [],
            "baseline_file": "structure_baseline.json", "ignore_classes": ["std::*"], "fix_room_lines": 10,
            "min_duplicate_lines": 12, "systems": [], "systems_root": "", "max_complexity": 15, "max_nesting": 4}
DECL = re.compile(r"^\s*(?:template\s*<[^>]*>\s*)?(?:(?:public|private|protected|internal|abstract|sealed|static|partial|export|default|final|unsafe|readonly|ref|data|open)\s+)*"
                  r"(?:class|struct|interface|record)\s+(?:[A-Z0-9_]+_API\s+)?(?:alignas\([^)]*\)\s*)?([A-Za-z_]\w*)")
METHOD = re.compile(r"^\s*(?:[\w:<>,*&~]+\s+)*?[*&]*((?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)::(?:~?[A-Za-z_]\w*|operator\W+)\s*\(")   # C++ out-of-class member definition
IMPORT = re.compile(r"^\s*(#\s*include|#\s*import|using\s|import\s|from\s|require\(|.*\brequire\()")


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def match(path, globs):
    return any(fnmatch.fnmatch(path, g) or (g.startswith("**/") and fnmatch.fnmatch(path, g[3:])) for g in globs)


def files(cfg, s):
    out = git("ls-files", cwd=cfg["_root"]).stdout.split("\n")
    return sorted(p for p in out if p and match(p, s["include"]) and not match(p, s["exclude"])
                  and os.path.isfile(os.path.join(cfg["_root"], p)))


BRK = lambda k: os.environ.get("FG_BREAK", "") == k


def _string_end(line, i, n):
    """Index of the quote that closes the string starting at line[i] (backslash escapes), or n."""
    c, j = line[i], i + 1
    while j < n and line[j] != c:
        j += 2 if line[j] == "\\" else 1
    return j


def _raw_string_end(line, i):
    """C++ raw string R"delim( ... )delim" starting at the quote line[i]: its end, or None."""
    k = line.find("(", i)
    if k <= i:
        return None
    end = line.find(")" + line[i + 1:k] + '"', k)
    return end + len(line[i + 1:k]) + 2 if end >= 0 else None


def _code_step(line, i, n, state, keep, fixed, out):
    """One step of strip_code from position i: the next position, or -1 when the rest of the line is a comment."""
    j = _raw_string_end(line, i) if fixed and not state[0] and line[i] == '"' and i > 0 and line[i - 1] == "R" else None
    if j is not None:
        out += [line[i:j]] if keep else []
        return j
    if state[0]:
        j = line.find("*/", i)
        if j < 0: return -1
        state[0] = False; return j + 2
    if line.startswith("//", i):
        return -1
    if line.startswith("/*", i):
        state[0] = True; return i + 2
    if line[i] in "\"'":
        j = _string_end(line, i, n)
        out += [line[i:j + 1]] if keep else []
        return j + 1
    out.append(line[i]); return i + 1


def strip_code(line, state, keep_strings=False):
    """Remove comments and string literals so braces inside them don't count. state = [in_block_comment].
    keep_strings=True removes comments only (for include/import lines, whose paths are strings)."""
    out, i, n = [], 0, len(line)
    fixed = not BRK("structure_fresh")
    while 0 <= i < n:
        if fixed and not state[0]:
            j = STRIP_PLAIN.match(line, i).end()      # 27 Nov: a run no comment or string can start in is copied at once
            if j > i:
                out.append(line[i:j]); i = j; continue
        i = _code_step(line, i, n, state, keep_strings, fixed, out)
    return "".join(out)

STRIP_PLAIN = re.compile(r"[^\"'/]*")

def _clean_for_blocks(lines, ext):
    if BRK("structure_round2"):
        st = [False]
        return [strip_code(ln, st) for ln in lines]
    clean = FN.clean_lines(lines, ext)               # also multi-line raw strings, template literals and #if 0 blocks
    pk = next((re.match(r"^\s*package\s+([\w.]+)\s*;", c) for c in clean if re.match(r"^\s*package\s+[\w.]+\s*;", c)), None)
    if pk and ext in (".java", ".kt"):               # a Java package names its classes like a namespace
        clean = [f"namespace {pk.group(1)};" if re.match(r"^\s*package\s", c) else c for c in clean]
    return clean


class _Scopes:
    """The namespaces open at the current line. ns: [(name, depth before its brace)]; pending: a namespace waiting for
    its "{"."""
    def __init__(self, path):
        self.path, self.ns, self.depth, self.pending = path, [], 0, None

    def prefix(self):
        return "::".join(x for x, _ in self.ns)

    def braces(self, line):
        for ch in line:
            if ch == "{":
                if self.pending is not None:
                    self.ns.append((self.pending, self.depth)); self.pending = None
                self.depth += 1
            elif ch == "}":
                self.depth -= 1
                while self.ns and self.ns[-1][1] >= 0 and self.ns[-1][1] >= self.depth:
                    self.ns.pop()

    def namespace(self, mn, clean, i):
        """A namespace line. Returns the next line index to read (i again when code follows its "{")."""
        name = (mn.group(1) or "").replace(".", "::").replace("inline ", "") or "{anon:" + self.path + "}"
        if mn.group(2) == ";":
            self.ns.append((name, -1))                    # C# file-scoped namespace: the rest of the file
            return i + 1
        if not mn.group(2):
            self.pending = name
            return i + 1
        self.ns.append((name, self.depth)); self.depth += 1
        rest = clean[i][mn.end():]
        if rest.strip():
            clean[i] = rest; return i                     # code after "namespace X {" on the same line is read as a line
        return i + 1


def _block_ident(m, line, sc, plain):
    kind = "decl" if m.re is DECL else "method"
    name = m.group(1)
    if kind == "decl":
        q = re.match(r"\s*((?:::[A-Za-z_]\w*)*)\s*(<[^{;]*>)?", line[m.end():])
        name += q.group(1) + (re.sub(r"\s+", "", q.group(2)) if q.group(2) else "")
    if plain:
        return (name.split("::")[-1].split("<")[0] if kind == "decl" else name.split("::")[-1]), kind
    prefix = sc.prefix()
    return (prefix + "::" + name if prefix else name), kind


def _seg_close(seg, d, opened):
    """Count the braces of one segment. Returns (depth, opened, text after the closing brace or None)."""
    for x, ch in enumerate(seg):
        if ch == "{": d += 1; opened = True
        elif ch == "}": d -= 1
        if opened and d <= 0:
            return d, opened, seg[x + 1:]
    return d, opened, None


def _block_end(clean, i, start):
    """From a declaration at line i (its text from start on): (last line, opened?, text after the body, text after a ;)."""
    d, opened, j, n = 0, False, i, len(clean)
    while j < n:
        seg = clean[j] if j > i else clean[i][start:]
        if not opened and ";" in seg and "{" not in seg.split(";")[0]:
            return j, False, "", (seg.split(";", 1)[1] if j == i else "")   # forward declaration / prototype, no body
        d, opened, tail = _seg_close(seg, d, opened)
        if tail is not None:
            return j, True, tail, ""
        j += 1
    return j, opened, "", ""


def _after_block(clean, i, j, opened, tail, after, plain):
    """Where to read on after a declaration, and the line text to read there."""
    if opened:
        if "}" in tail or "{" in tail or (not plain and NAMESPACE.match(tail)):
            clean[j] = tail; return j                     # a namespace closing on the same line as the class
        return j + 1
    if after.strip() and not BRK("structure_fwd_line"):
        clean[i] = after; return i                        # namespace N { class A; struct B; }: read the rest, its "}" too
    return i + 1


def blocks_clike(lines, path="", ext="", spans=False):
    """[(class identity, line count, kind)] for class bodies and C++ out-of-class member definitions.
    Identity is namespace-qualified (MyHydro::Aquifer::State, not State); a template specialisation keeps its arguments
    (std::hash<FTile>); a class in an anonymous namespace is private to its file. kind = "decl" or "method".
    spans=True adds each block's first and last line index (the shrink rule, fg/shrink.py, reads which lines are whose)."""
    clean = _clean_for_blocks(lines, ext)
    found, i, n = [], 0, len(clean)
    plain = BRK("structure_namespace")
    sc = _Scopes(path)
    while i < n:
        mn = NAMESPACE.match(clean[i])
        m = None if mn else (DECL.match(clean[i]) or METHOD.match(clean[i]))
        if mn:
            i = sc.namespace(mn, clean, i); continue
        if not m:
            sc.braces(clean[i]); i += 1; continue
        ident, kind = _block_ident(m, clean[i], sc, plain)
        j, opened, tail, after = _block_end(clean, i, m.end())
        if opened:
            found.append((ident, j - i + 1, kind) + ((i, j) if spans else ()))
        i = _after_block(clean, i, j, opened, tail, after, plain)
    return found

NAMESPACE = re.compile(r"^\s*(?:export\s+)?(?:inline\s+)?namespace\s*([A-Za-z_][\w.:]*(?:::inline\s+\w+)*)?\s*(\{|;)?")


FUNC = re.compile(r"^\s*(?:[\w:<>,*&~\[\]]+\s+)+(~?[\w:]+|operator\W+)\s*\([^;]*\)\s*(?:const|override|final|noexcept|\s)*(?:\{.*)?$")
ARROW = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:(?:const|let|var)\s+|(?:public|private|protected|static|readonly|async)\s+)*"
                   r"([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?(?:function\s*\w*\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::\s*[^=]+)?(?:=>)?\s*\{")
NOT_FUNC = re.compile(r"^\s*(if|for|while|switch|catch|return|else|do|new|delete|throw|using|namespace|class|struct)\b")


def functions_clike(lines, ext="", checks=False):
    if os.environ.get("FG_BREAK", "") != "structure_round2":
        found, clean = FN.functions(lines, ext)
        return [(nm, b - a + 1) + D.tangle_clike(clean, a, b, checks) for nm, a, b in found]
    return functions_clike_v1(lines)


def _body_end(clean, j):
    """The line where the braces opened at or after line j close (or the last line)."""
    depth, opened, n = 0, False, len(clean)
    while j < n:
        for ch in clean[j]:
            if ch == "{": depth += 1; opened = True
            elif ch == "}": depth -= 1
        if opened and depth <= 0:
            break
        j += 1
    return j


def _v1_match(clean, i):
    m = FUNC.match(clean[i])
    if not m and not BRK("structure_fresh"):
        m = ARROW.match(clean[i]) if ("=>" in clean[i] or "function" in clean[i]) else None
    if not m or NOT_FUNC.match(clean[i]):
        return None
    has_body = "{" in clean[i] or (i + 1 < len(clean) and clean[i + 1].strip().startswith("{"))
    return m if has_body else None


def functions_clike_v1(lines):
    """[(name, line count)] for every function body (free functions and members), braces in strings/comments ignored."""
    st = [False]
    clean = [strip_code(ln, st) for ln in lines]
    out, i, n = [], 0, len(clean)
    while i < n:
        m = _v1_match(clean, i)
        if not m:
            i += 1; continue
        j = _body_end(clean, i)
        out.append((m.group(1), j - i + 1) + D.tangle_clike(clean, i, j)); i = j + 1
    return out


def _py_old_scan(lines):
    """The v0.2-v0.7 scan (kept for the structure_pyquote break switch): fooled by '\"\"\"' inside a normal string."""
    inside, q, res = False, None, []
    for ln in lines:
        res.append(inside)
        for m in re.finditer(r'"""|\'\'\'', ln):
            if not inside: inside, q = True, m.group(0)
            elif m.group(0) == q: inside = False
    return res


def _py_step(ln, i, inside, q):
    """One step of the scan of a Python line: (next index, inside a triple-quoted string?, its quote)."""
    if inside:
        k = ln.find(q, i)
        return (len(ln), True, q) if k < 0 else (k + 3, False, q)
    if ln[i] == "#":
        return len(ln), False, q                                  # a comment: the rest of the line is not code
    if ln.startswith('"""', i) or ln.startswith("'''", i):
        return i + 3, True, ln[i:i + 3]
    if ln[i] in "\"'":                                            # an ordinary string: skip to its end
        return _string_end(ln, i, len(ln)) + 1, False, q
    return i + 1, False, q


def py_in_string(lines):
    """For each line: True if it starts inside a triple-quoted string (so its indent says nothing about blocks)."""
    if BRK("structure_pyquote"):
        return _py_old_scan(lines)
    inside, q, res = False, None, []
    for ln in lines:
        res.append(inside)
        i = 0
        while i < len(ln):
            i, inside, q = _py_step(ln, i, inside, q)
    return res

def py_block_end(lines, i, ind, ins):
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > ind or ins[j]):
        j += 1
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1                                                # trailing blank lines belong to no one
    return j


def py_defs(lines):
    """[(name, def line, signature's last line, end)] of every Python function; end is one past its last line."""
    out, ins = [], (py_in_string(lines) if not os.environ.get("FG_BREAK", "") == "structure_fresh" else [False] * len(lines))
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)(?:async\s+)?def\s+([A-Za-z_]\w*)", ln)
        if not m or ins[i]: continue
        sig = i
        if os.environ.get("FG_BREAK", "") != "structure_round3":                     # a signature over several lines ends where its brackets close
            depth = 0
            for k in range(i, min(len(lines), i + 40)):
                code = re.sub(r"#.*$", "", re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", lines[k]))
                depth += code.count("(") + code.count("[") - code.count(")") - code.count("]")
                if depth <= 0 and code.rstrip().endswith(":"):
                    sig = k; break
        out.append((m.group(2), i, sig, py_block_end(lines, sig, len(m.group(1)), ins)))
    return out


def functions_python(lines, checks=False):
    return [(name, j - i) + D.tangle_python(lines, sig, j, head=i, checks=checks) + (D.tangle_python(lines, sig, j)[1],)
            for name, i, sig, j in py_defs(lines)]


def function_spans(lines, ext, checks=False):
    """[(name, first line index, last line index, complexity, nesting)] of a file's functions, measured as the check does
    (the shrink rule reads which lines belong to which function)."""
    if ext == ".py":
        return [(name, i, j - 1) + D.tangle_python(lines, sig, j, head=i, checks=checks)[:2] for name, i, sig, j in py_defs(lines)]
    if ext in CLIKE:
        found, clean = FN.functions(lines, ext)
        return [(nm, a, b) + D.tangle_clike(clean, a, b, checks)[:2] for nm, a, b in found]
    return []


def gd_skip(lines, ins):
    """GDScript lines that say nothing about blocks: blank, comment-only, inside a text block, or the inside of an open
    bracket or a backslash continuation (those may sit at any indent). Returns (skip, trim): trim marks only the blank and
    comment lines, which a function's end may drop; a text block or bracket that closes at the left edge still belongs to it."""
    skip, trim, depth, back = [], [], 0, False
    for ln, q in zip(lines, ins):
        st = ln.strip(); cont = q or depth > 0 or back
        if os.environ.get("FG_BREAK", "") == "engine_round1": cont = q
        skip.append(not st or st.startswith("#") or cont); trim.append((not st or st.startswith("#")) and not cont)
        code = re.sub(r"#.*$", "", re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", ln)) if not q else ""
        depth = max(0, depth + code.count("(") + code.count("[") + code.count("{") - code.count(")") - code.count("]") - code.count("}"))
        back = code.rstrip().endswith("\\")
    return skip, trim


def gd_block_end(lines, i, ind, skip, trim=None):
    trim = trim or skip
    j = i + 1
    while j < len(lines) and (skip[j] or len(lines[j].expandtabs(4)) - len(lines[j].expandtabs(4).lstrip()) > ind):
        j += 1
    while j > i + 1 and trim[j - 1]:
        j -= 1                                                # trailing blank and comment lines belong to no one
    return j


def functions_gd(lines):
    """GDScript (Godot): 'func name(...)' and 'static func', after any @annotations; inner-class methods are Class.name.
    A function runs from its func line to its last code line; lambdas inside it belong to it."""
    if os.environ.get("FG_BREAK", "") == "engine_gd": return []
    out, ins = [], py_in_string(lines)
    skip, trim = gd_skip(lines, ins); classes = []           # (indent, name) of the inner classes we are in
    for i, ln in enumerate(lines):
        if skip[i]: continue
        ind = len(ln.expandtabs(4)) - len(ln.expandtabs(4).lstrip())
        while classes and ind <= classes[-1][0]: classes.pop()
        c = re.match(r"^\s*class\s+([A-Za-z_]\w*)", ln)
        if c: classes.append((ind, c.group(1))); continue
        m = re.match(r"^\s*(?:@\w+(?:\([^()]*\))?\s*)*(?:(?:static|remote|remotesync|master|puppet|mastersync|puppetsync)\s+)*"
                     r"func\s+([A-Za-z_]\w*)\s*\(", ln)
        if not m: continue
        sig, depth = i, 0
        for k in range(i, min(len(lines), i + 40)):
            code = re.sub(r"#.*$", "", re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", lines[k]))
            depth += code.count("(") + code.count("[") - code.count(")") - code.count("]")
            if depth <= 0 and re.search(r":\s*(\S.*)?$", code) and ":" in code:
                sig = k; break
        j = gd_block_end(lines, sig, ind, skip, trim)
        name = ".".join([c for _, c in classes] + [m.group(1)])
        out.append((name, j - i) + D.tangle_python(lines, sig, j))
    return out


def blocks_gd(lines, path=""):
    out, ins = [], py_in_string(lines); skip, trim = gd_skip(lines, ins)
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)class\s+([A-Za-z_]\w*)", ln)
        if m and not skip[i]:
            out.append((f"{path}::{m.group(2)}", gd_block_end(lines, i, len(m.group(1).expandtabs(4)), skip, trim) - i))
    return out


def blocks_python(lines, path=""):
    """A Python class lives in one module, so it is named with its file: same-named classes in two modules are two classes."""
    found, ins = [], (py_in_string(lines) if not os.environ.get("FG_BREAK", "") == "structure_fresh" else [False] * len(lines))
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)class\s+([A-Za-z_]\w*)", ln)
        if not m or ins[i]: continue
        j = py_block_end(lines, i, len(m.group(1)), ins)
        found.append((m.group(2) if os.environ.get("FG_BREAK", "") == "structure_fresh" else f"{path}::{m.group(2)}", j - i))
    return found


def _read_lines(cfg, p):
    try:
        return open(os.path.join(cfg["_root"], p), encoding="utf-8", errors="replace").read().split("\n")
    except OSError:
        return None


def _shapes(lines, p, ext, checks=False):
    """(blocks, functions, is code?) of one file, by its language. checks: a test file (its check lines count less)."""
    gd = ext == ".gd" and not BRK("engine_gd")
    if ext in CLIKE:
        return blocks_clike(lines, p, ext), functions_clike(lines, ext, checks), True
    if ext == ".py":
        return [(a, b, "decl") for a, b in blocks_python(lines, p)], functions_python(lines, checks), True
    if gd:
        return [(a, b, "decl") for a, b in blocks_gd(lines, p)], functions_gd(lines), True
    return [], [], False


def _code_view(lines, ext, s):
    """A web project's HTML pages are measured by their own <script> code, read as JavaScript (web pack, 11 Nov:
    a single-file game keeps all its code in index.html). Only where setup found a web project (html_scripts)."""
    if ext in FN.HTML_EXT and s.get("html_scripts") and not BRK("web_html"):
        return FN.html_scripts(lines), ".js"
    return lines, ext


def _note_functions(p, fs, s, tg, fn):
    for f in fs:
        name, k, cx, nest = f[:4]
        was = f[4] if len(f) > 4 else nest            # the nesting as counted before F440 (Python: by indentation)
        key = f"{p}::{name}"
        if (cx > s["max_complexity"] or nest > s["max_nesting"] or was > s["max_nesting"]) and not D.BREAK("design_tangle"):
            old = tg.get(key, [0, 0, 0]); tg[key] = [max(cx, old[0]), max(nest, old[1]), max(was, old[-1])]
        if k > s["max_function_lines"]:
            fn[key] = max(k, fn.get(key, 0))


def _class_name(name, declared):
    """'using namespace X;' then 'State::Step()' or a member of an enclosing namespace: find the one declared class it means."""
    if name in declared:
        return name
    ends = [d for d in declared if d.endswith("::" + name) or name.endswith("::" + d)]
    ends = [d for d in ends if d.split("<")[0] == d] or ends
    return ends[0] if len(ends) == 1 else name


def _classes(allb, s):
    declared = {name for name, _, kind, _ in allb if kind == "decl"}
    cl = {}
    for name, k, kind, p in allb:
        if kind == "method":
            name = _class_name(name, declared)
        if any(fnmatch.fnmatch(name, g) for g in s["ignore_classes"]):
            continue
        c = cl.setdefault(name, {"lines": 0, "files": set()}); c["lines"] += k; c["files"].add(p)
    return {k: {"lines": v["lines"], "files": sorted(v["files"])} for k, v in cl.items()}


def _import_lines(raw):
    """Dependencies count only real include/import lines: no comments, #if 0 blocks, docstrings or strings."""
    if D.BREAK("design_round1"):
        return raw
    out = {}
    for p, lines in raw.items():
        ext = os.path.splitext(p)[1].lower(); cln = FN.clean_lines(lines, ext)
        ins = py_in_string(lines) if ext == ".py" else [False] * len(lines)
        out[p] = ["" if (not c.strip() or q) else re.sub(r"\s//.*$", "", r) for r, c, q in zip(lines, cln, ins)]
    return out


def _kit_print(s, cfg=None):
    """What a cached measurement depends on besides the file itself: this kit's measuring code, the settings, the breaks."""
    import hashlib
    h = hashlib.sha1(os.environ.get("FG_BREAK", "").encode())
    for m in (__file__, FN.__file__, D.__file__):
        with open(m, "rb") as f:
            h.update(f.read())
    h.update(json.dumps({k: v for k, v in s.items() if not k.startswith("_")}, sort_keys=True, default=str).encode())
    h.update(json.dumps((cfg or {}).get("test_files") or [], default=str).encode())       # which files are tests
    return h.hexdigest()


def _one_file(cfg, lines, p, s):
    """[line count, blocks, functions, code lines or None, import lines, boundary import lines] of one file's text."""
    imp = _imports_of(cfg, p, os.environ.get("FG_BREAK", ""), list(lines)) if s.get("boundaries") else []
    n = len(lines) - (1 if lines and lines[-1] == "" and not BRK("structure_fresh") else 0)   # a final line break is not a line
    lines, ext = _code_view(lines, os.path.splitext(p)[1].lower(), s)
    import adds as AD
    bl, fs, is_code = _shapes(lines, p, ext, AD.is_test_file(p, cfg))
    code = D.code_lines(lines, ".py" if ext == ".gd" else ext, strip_code) if is_code else None
    return [n, bl, fs, code, _import_lines({p: lines})[p], imp]


def _cache_path(cfg):
    g = C.git_dir(cfg["_root"])                       # this copy's own git folder (a worktree's .git is a file)
    return os.path.join(g, "foundationguard", "size_cache.json") if g else None


def _load_cache(cfg, kit):
    try:
        with open(_cache_path(cfg), encoding="utf-8") as f:
            d = json.load(f)
        return d["files"] if d.get("kit") == kit else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _save_cache(cfg, kit, got):
    try:
        path = _cache_path(cfg); os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"kit": kit, "files": got}, f)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def measure(cfg, s, cached=False):
    """cached=True (the box before an upload, which may only wait a few seconds) takes each unchanged file's
    measurement from the last run (27 Nov: the game's 3,000 files took 77 s on its PC). The upload's own gate always
    measures afresh, and leaves its measurements for the next box."""
    import hashlib
    fl, fn, allb, raw, code, tg = {}, {}, [], {}, {}, {}
    use = cached and not BRK("size_cache")
    kit = _kit_print(s, cfg) if C.git_dir(cfg["_root"]) else None
    old, got, imports = (_load_cache(cfg, kit) if use and kit else {}), {}, {}
    for p in files(cfg, s):
        lines = _read_lines(cfg, p)
        if lines is None:
            continue
        key = p + "\0" + hashlib.sha1("\n".join(lines).encode("utf-8", "surrogatepass")).hexdigest()
        one = old.get(key) or _one_file(cfg, lines, p, s)
        got[key] = one
        fl[p], bl, fs, c, raw[p], imports[p] = one
        if c is not None:
            code[p] = [tuple(x) for x in c]
        _note_functions(p, [tuple(f) for f in fs], s, tg, fn)
        allb.extend((name, k, kind, p) for name, k, kind in bl)
    if kit and (not use or set(got) != set(old)):
        _save_cache(cfg, kit, got)                    # unchanged since the last run: nothing to write
    s["_imports"] = {p: [tuple(x) for x in v] for p, v in imports.items()} if s.get("boundaries") else {}
    cl = _classes(allb, s)
    edges = D.dependencies(raw, s)
    s["_design"] = {"tangle": tg, "dups": D.duplicates(code, s["min_duplicate_lines"]), "edges": edges, "cycles": D.cycles(edges)}
    return fl, cl, fn


NESTING = 2      # how nesting is counted: 2 = from Python's syntax tree (F440); a baseline without it used indentation


def _followed(k, recorded, now):
    """The recorded entry a function that moved to another file brings with it (F518): the one entry with the same
    name (Class::Function, or else the same function name alone) whose own file no longer holds that function. The
    game's PC, 20 Nov: a planned split moves many long functions to new files, and each would have failed the gate as
    new code over the limit. The entry still may only shrink, so a move never makes room to grow."""
    if BREAK_S("structure_moved") or "::" not in k:
        return None
    name = k.split("::", 1)[1]
    gone = [o for o in recorded if o not in now and "::" in o]
    for same in (lambda o: o.split("::", 1)[1] == name, lambda o: o.rsplit("::", 1)[-1] == name.rsplit("::", 1)[-1]):
        hit = [o for o in gone if same(o)]
        if len(hit) == 1:
            return recorded[hit[0]]
        if hit:
            return None
    return None


def _tangle_check(dz, bt, s, brk, bad, method=NESTING):
    """A baseline recorded under the old way of counting nesting is held to that same count, so code nobody touched
    doesn't fail when the counting changes (the game's PC, 16 Nov: five untouched functions failed after F440). The
    next --baseline or --ratchet records the new count."""
    old_way = method < NESTING and not BREAK_S("design_nesting_method")
    for k, v in sorted(dz["tangle"].items()):
        cx, nest = v[0], (v[-1] if old_way else v[1])
        if cx <= s["max_complexity"] and nest <= s["max_nesting"] and k not in bt:
            continue                                   # only over the limit by the other way of counting
        was = bt.get(k) or _followed(k, bt, dz["tangle"])
        if was is None:
            bad.append(f"function {k}: tangled: {cx} decision points (limit {s['max_complexity']}), nesting {nest} deep (limit {s['max_nesting']})")
        elif (cx > was[0] or nest > was[1]) and brk != "structure_ratchet":
            bad.append(f"function {k}: more tangled: {cx} decisions, nesting {nest}; recorded {was[0]}, {was[1]}, may only shrink")


def _dup_check(dz, bd, brk, bad):
    groups = {}
    for d in sorted(dz["dups"]):
        was = bd.get(dup_key(d))
        if was is None or (d[6] > was and brk != "structure_ratchet"):
            groups.setdefault((d[0], d[1], d[2], d[6]), []).append(f"{d[3]}:{d[4]}-{d[5]}" + ("" if was is None else f" (recorded {was} lines)"))
    seen = set()
    for (pa, a1, a2, n), others in sorted(groups.items()):
        if (pa, a1) in seen:
            continue
        seen.update((o.split(":")[0], int(o.split(":")[1].split("-")[0])) for o in others)
        bad.append(f"copy-paste: the same {n} lines of code at {pa}:{a1}-{a2} and {', '.join(others)}")


def _cycle_check(dz, bc, bad):
    for c in dz["cycles"]:
        if any(set(c) <= set(b) for b in bc):
            continue
        path = [f"{a} -> {b} ({dz['edges'][(a, b)][0]}:{dz['edges'][(a, b)][1]})" for a in c for b in c if (a, b) in dz["edges"]]
        bad.append(f"loop between systems {', '.join(c)}: " + "; ".join(path))


BREAK_S = lambda k: os.environ.get("FG_BREAK", "") == k


def design_check(s, base, brk):
    dz, bad = s["_design"], []
    _tangle_check(dz, base.get("tangle", {}), s, brk, bad, base.get("nesting", 1 if base.get("tangle") else NESTING))
    _dup_check(dz, base.get("duplicates", {}), brk, bad)
    _cycle_check(dz, base.get("cycles", []), bad)
    return bad


def _room(s, brk, piece=None):
    """Lines an over-limit file, class or function may stand over its recorded size (room for a small fix). With the
    shrink rule on (fg/shrink.py), a piece it covers gets only the lines its books hold for it (pay-later lines, one-line
    fixes, an exact revert of a cut) instead of fix_room_lines."""
    if brk == "fix_room":
        return 0
    books = s.get("_shrink_room")
    if books is not None and piece in books:
        return books[piece]
    return max(0, int(s.get("fix_room_lines", 10)))


def _function_check(fn, base, s, brk, bad):
    for k, n in ({} if brk == "structure_function" else fn).items():
        allowed = base.get("functions", {}).get(k)
        if allowed is None:
            allowed = _followed(k, base.get("functions", {}), fn)
        if allowed is None:
            bad.append(f"function {k}: {n} lines (limit {s['max_function_lines']})")
        elif n > allowed + _room(s, brk, "function " + k) and brk != "structure_ratchet":
            bad.append(f"function {k}: grew to {n} lines; recorded {allowed}, may only shrink (a fix may add up to {_room(s, brk, 'function ' + k)})")


def _file_check(fl, base, s, brk, bad):
    for p, n in ((p, n) for p, n in fl.items() if n > s["max_file_lines"]):
        allowed = base["files"].get(p)
        if allowed is None:
            bad.append(f"{p}: {n} lines (limit {s['max_file_lines']})")
        elif n > allowed + _room(s, brk, "file " + p) and brk != "structure_ratchet":
            bad.append(f"{p}: grew to {n} lines; its recorded size is {allowed} and it may only shrink (a fix may add up to {_room(s, brk, 'file ' + p)})")


def _class_size(k, v, b, s, brk, bad):
    if v["lines"] <= s["max_class_lines"]:
        return
    if b is None:
        bad.append(f"class {k}: {v['lines']} lines across {len(v['files'])} file(s) (limit {s['max_class_lines']})")
    elif v["lines"] > b["lines"] + _room(s, brk, "class " + k) and brk != "structure_ratchet":
        bad.append(f"class {k}: grew to {v['lines']} lines; recorded {b['lines']}, may only shrink")


def _class_spread(k, v, b, s, brk, bad):
    nf = len(v["files"])
    if nf <= s["max_class_files"]:
        return
    if b is None:
        bad.append(f"class {k}: spread over {nf} files (limit {s['max_class_files']}): {', '.join(v['files'][:5])}{' ...' if nf > 5 else ''}")
    elif nf > b["files"] and brk != "structure_ratchet":
        bad.append(f"class {k}: now in {nf} files; recorded {b['files']}, may only shrink")


def _class_check(cl, base, s, brk, bad):
    if brk == "structure_class":
        return
    for k, v in cl.items():
        b = base["classes"].get(k)
        _class_size(k, v, b, s, brk, bad)
        _class_spread(k, v, b, s, brk, bad)


def _join_imports(rawl, brk):
    """[(first line number, text, last line number)]; a multi-line import { a, b } from "..." counts as one line."""
    joined, k = [], 0
    while k < len(rawl):
        ln = rawl[k]
        if brk != "structure_round2" and re.match(r"^\s*(import|export)\b[^'\"]*$", ln) and ("{" in ln or "(" in ln):
            j = k
            while j + 1 < len(rawl) and j - k < 30 and not re.search(r"['\"]", rawl[j]): j += 1
            joined.append((k + 1, " ".join(x.strip() for x in rawl[k:j + 1]), j + 1)); k = j + 1; continue
        joined.append((k + 1, ln, k + 1)); k += 1
    return joined


def _boundary_lines(cfg, p, brk, rawl=None):
    if rawl is None:
        rawl = open(os.path.join(cfg["_root"], p), encoding="utf-8", errors="replace").read().split("\n")
    if brk != "structure_round2":
        cln = FN.clean_lines(rawl, os.path.splitext(p)[1].lower())
        rawl = ["" if not c.strip() else r for r, c in zip(rawl, cln)]   # comments and #if 0 blocks
    return _join_imports(rawl, brk)


def _imports_of(cfg, p, brk, rawl=None):
    """[(line number, include/import line)] of one file, as the boundary rules read it."""
    st, py, out = [False], p.endswith(".py"), []
    for i, raw, last in _boundary_lines(cfg, p, brk, rawl):
        ln = raw if brk == "structure_fresh" else (re.sub(r"\s#.*$", "", raw) if py else strip_code(raw.rstrip("\n"), st, keep_strings=True))
        if IMPORT.match(ln):
            out.append((i, ln))
    return out


def _boundary_file(cfg, p, rule, brk, bad, known=None):
    for i, ln in (known if known is not None else _imports_of(cfg, p, brk)):
        if any(re.search(x, ln) for x in rule["may_not_use"]):
            bad.append(f"{p}:{i}: reaches past a boundary ({ln.strip()[:80]}): {rule.get('why', '')}")


def _boundary_check(cfg, fl, s, brk, bad):
    for rule in ([] if brk == "structure_boundary" else s["boundaries"]):
        globs = rule["files"] if isinstance(rule["files"], list) else [rule["files"]]
        skip = [] if brk == "boundary_exclude" else list(rule.get("exclude") or [])   # the game's N23, 16 Nov: one rule
        for p in (p for p in fl if match(p, globs) and not match(p, skip)):           # with its hub file left out
            _boundary_file(cfg, p, rule, brk, bad, (s.get("_imports") or {}).get(p))


def _lines_at(root, ref, p):
    """Line count of a file as it was at ref (0 if it wasn't there). Read as bytes: a file that isn't UTF-8 text must not
    crash the check (F081)."""
    if BRK("structure_bytes"):
        old = subprocess.run(["git", "show", f"{ref}:{p}"], cwd=root, capture_output=True, text=True, encoding="utf-8")
        return len(old.stdout.split("\n")) if old.returncode == 0 else 0      # the old read as text: crashes on bytes
    old = subprocess.run(["git", "show", f"{ref}:{p}"], cwd=root, capture_output=True)
    return len(old.stdout.split(b"\n")) if old.returncode == 0 else 0


def _counts_at(root, ref, paths):
    """{path: line count at ref} for many files in one git call (27 Nov: one git show per file took 2 s of the game
    PC's size check); a file that wasn't there is left out. None when git can't do it, so each is read on its own."""
    if BRK("growth_batch") or BRK("structure_bytes") or not paths:   # F081's break is the old per-file text read
        return None
    try:
        q = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True, timeout=60,
                           input="".join(f"{ref}:{p}\n" for p in paths).encode("utf-8", "surrogateescape"))
    except (OSError, subprocess.SubprocessError):
        return None
    out, data, i = {}, q.stdout, 0
    for p in paths:
        j = data.find(b"\n", i)
        if q.returncode != 0 or j < 0:
            return None
        head = data[i:j].split(); i = j + 1
        if len(head) == 3 and head[1] == b"blob":
            k = int(head[2]); out[p] = len(data[i:i + k].split(b"\n")); i += k + 1
        elif len(head) != 2 or head[1] != b"missing":
            return None                                   # something else came back: read each file the old way
    return out


def _growth_check(cfg, fl, s, bad, warn):
    if git("rev-parse", "--verify", "-q", s["base_ref"], cwd=cfg["_root"]).returncode != 0:
        return
    at = _counts_at(cfg["_root"], s["base_ref"], list(fl))
    for p, n in fl.items():
        was = _lines_at(cfg["_root"], s["base_ref"], p) if at is None else at.get(p, 0)
        if n - was > s["max_growth_lines"]:
            (bad if s["growth_blocks"] else warn).append(f"{p}: grew {n - was} lines since {s['base_ref']} (alarm at {s['max_growth_lines']})")


def check(cfg, cached=False):
    s = dict(DEFAULTS); s.update(cfg.get("structure") or {})
    brk = os.environ.get("FG_BREAK", "")
    fl, cl, fn = measure(cfg, s, cached); base = load_baseline(cfg, s); bad, warn = [], []
    shrunk = _shrink(cfg, s, cl, bad)
    _function_check(fn, base, s, brk, bad)
    _file_check(fl, base, s, brk, bad)
    _class_check(cl, base, s, brk, bad)
    _boundary_check(cfg, fl, s, brk, bad)
    _growth_check(cfg, fl, s, bad, warn)
    bad += design_check(s, base, brk)
    rep = [f"STRUCTURE: {len(fl)} files, {len(cl)} classes, {len(fn)} long functions found; {len(bad)} failure(s), {len(warn)} warning(s)."]
    rep += ["  FAIL " + b for b in bad] + ["  WARN " + w for w in warn] + shrunk
    return not bad, "\n".join(rep)


def _shrink(cfg, s, cl, bad):
    """The shrink rule (fg/shrink.py), when "structure" -> "shrink" -> "on": its failures join bad, its books set each
    covered piece's room, and its report lines (owed shrinks, pay-later lines) are returned for the summary."""
    if not (s.get("shrink") or {}).get("on"):
        return []
    import shrink as SH
    sb, books, lines = SH.run(cfg, s, cl)
    bad += sb
    s["_shrink_room"] = books
    return lines


def _was(k, recorded, now):
    """A recorded entry for k: its own, or the one a function that moved file brings with it (F518). The game's PC,
    24 Nov: the check followed moved functions but the ratchet kept only exact names, so a ratchet after a split dropped
    54 entries and the next check failed 44 tangled functions (F543)."""
    if k in recorded:
        return recorded[k]
    return None if BREAK_S("ratchet_follows_moves") else _followed(k, recorded, now)


def _ratchet_sizes(old, of, oc, ofn, fn=None):
    """Tighten: keep only what was already recorded, at the smaller of old and new."""
    of = {p: min(n, old["files"][p]) for p, n in of.items() if p in old["files"]}
    oc = {k: {"lines": min(v["lines"], old["classes"][k]["lines"]), "files": min(v["files"], old["classes"][k]["files"])}
          for k, v in oc.items() if k in old["classes"]}
    ofo, now = old.get("functions", {}), (fn if fn is not None else ofn)
    ofn = {k: min(n, w) for k, n in ofn.items() for w in [_was(k, ofo, now)] if w is not None}
    return of, oc, ofn


def _ratchet_design(old, db):
    ot, od = old.get("tangle", {}), old.get("duplicates", {})
    same = old.get("nesting", 1 if ot else NESTING) == NESTING      # counted the old way: take today's count, once
    now = db["tangle"]
    db["tangle"] = {k: [min(v[0], w[0]), min(v[1], w[1]) if same else v[1]]
                    for k, v in now.items() for w in [_was(k, ot, now)] if w is not None}
    db["duplicates"] = {k: min(v, od[k]) for k, v in db["duplicates"].items() if k in od}
    db["cycles"] = [c for c in db["cycles"] if any(set(c) <= set(b) for b in old.get("cycles", []))]
    return db


def write_baseline(cfg, s, fl, cl, fn, reason, ratchet):
    of, oc, ofn = over(fl, cl, s, fn)
    db = design_baseline(s)
    if ratchet:
        old = load_baseline(cfg, s)
        of, oc, ofn = _ratchet_sizes(old, of, oc, ofn, fn)
        db = _ratchet_design(old, db)
        if not BREAK_S("ratchet_keeps_at_limit"):           # a file listed at the limit (shrink --add) stays listed there
            of.update({p: min(fl[p], n) for p, n in old["files"].items() if p not in of and fl.get(p, 0) >= s["max_file_lines"]})
        n = lambda b: sum(len(b.get(x) or {}) for x in ("files", "classes", "functions", "tangle", "duplicates"))
        kept, was = n({"files": of, "classes": oc, "functions": ofn, **db}), n(old)
        line = (f"baseline tightened: {kept} entries kept, {was - kept} dropped (fixed, or no longer found). "
                f"Reason: {reason or 'ratchet'}")
        if not BREAK_S("ratchet_logged"):
            with open(os.path.join(cfg["_root"], "STRUCTURE_LOG.md"), "a", encoding="utf-8") as f:
                f.write(f"- {datetime.date.today()}: {line}\n")
            try:
                import catches as CL
                CL.log(cfg, "structure ratchet", line, "fg/structure.py --ratchet", "the size and design baseline only tightens")
            except Exception:
                pass
    json.dump({"files": of, "classes": oc, "functions": ofn, **db}, open(baseline_path(cfg, s), "w", encoding="utf-8"), indent=1, sort_keys=True)
    if not ratchet:
        with open(os.path.join(cfg["_root"], "STRUCTURE_LOG.md"), "a", encoding="utf-8") as f:
            f.write(f"- {datetime.date.today()}: baseline written ({len(of)} files, {len(oc)} classes, {len(ofn)} functions over the limits). Reason: {reason}\n")
    import steps as SP                                 # 12 Nov: a ratchet only tightens; the check after the step keeps it
    SP.recorded(cfg, [baseline_path(cfg, s), os.path.join(cfg["_root"], "STRUCTURE_LOG.md")])
    return len(of), len(oc)

def dup_key(d):
    return f"{d[0]} <-> {d[3]}"


def design_baseline(s):
    dz = s["_design"]; dd = {}
    for d in dz["dups"]: dd[dup_key(d)] = max(dd.get(dup_key(d), 0), d[6])
    tangle = {k: [v[0], v[1]] for k, v in dz["tangle"].items() if v[0] > s["max_complexity"] or v[1] > s["max_nesting"]}
    return {"tangle": tangle, "duplicates": dd, "cycles": dz["cycles"], "nesting": NESTING}


def baseline_path(cfg, s):
    return os.path.join(cfg["_root"], s["baseline_file"])


def load_baseline(cfg, s):
    p = baseline_path(cfg, s)
    return json.load(open(p, encoding="utf-8-sig")) if os.path.exists(p) else {"files": {}, "classes": {}}


def over(fl, cl, s, fn=None):
    of = {p: n for p, n in fl.items() if n > s["max_file_lines"]}
    oc = {k: {"lines": v["lines"], "files": len(v["files"])} for k, v in cl.items()
          if v["lines"] > s["max_class_lines"] or len(v["files"]) > s["max_class_files"]}
    return of, oc, dict(fn or {})


def main(argv):
    cfg = C.load(); s = dict(DEFAULTS); s.update(cfg.get("structure") or {})
    if "--shrink" in argv:
        import shrink as SH
        return SH.main(cfg, s, [a for a in argv if a != "--shrink"])
    if "--baseline" in argv or "--ratchet" in argv:
        ratchet = "--ratchet" in argv
        reason = " ".join(a for a in argv if not a.startswith("--"))
        if not ratchet and os.path.exists(baseline_path(cfg, s)) and not reason:
            print("STRUCTURE: a baseline exists; rewriting it needs a reason: fg/structure.py --baseline \"why\""); return 1
        fl, cl, fn = measure(cfg, s); nf, nc = write_baseline(cfg, s, fl, cl, fn, reason or "first baseline", ratchet)
        print(f"STRUCTURE: baseline {'tightened' if ratchet else 'written'}: {nf} oversized files, {nc} oversized classes recorded."); return 0
    ok, rep = check(cfg); print(rep); return 0 if ok else 1


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

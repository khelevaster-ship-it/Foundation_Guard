"""FoundationGuard design checks (AI-made, Claude, 2026-11-09): copy-paste, loops between systems, tangled functions.

Called by fg/structure.py; configured under "structure" in foundationguard.json:
  "min_duplicate_lines": 12,   a block repeated in two places (same code, or with names and numbers changed) this long fails
  "systems": ["Source/Weather", "Source/Water"],   folders that count as systems, or {"Weather": [folder, folder]} when one
                                                   system lives in several folders (Unreal Public/Private) (default: each top-level folder of
                                                   "systems_root", or of the repo); a loop of includes between them fails
  "systems_root": "",
  "max_complexity": 15,        decision points + 1 in one function (if, for, while, case, catch, &&, ||, ?, and/or ...)
  "max_nesting": 4,            blocks inside blocks inside one function
Like the size limits, what exists today is recorded in the baseline and may only shrink.
"""
import hashlib, os, re

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
WORD = re.compile(r"[A-Za-z_$][\w$]*|\d[\w.]*|\S")
KEEP = {"if", "else", "for", "while", "do", "switch", "case", "return", "break", "continue", "class", "struct", "def", "try",
        "catch", "except", "finally", "new", "delete", "and", "or", "not", "in", "is", "lambda", "yield", "throw", "raise",
        "public", "private", "protected", "static", "const", "void", "int", "float", "double", "bool", "auto", "var", "let"}


BOILERPLATE = re.compile(r"^\s*(#\s*(include|import|pragma)|using\s|import\s|from\s+\S+\s+import|package\s)")


def _py_code(ln, state):
    """One Python line without strings and comments; None inside or at the start of a docstring. state = [open quote]."""
    s = ln.strip()
    if state[0]:
        if state[0] in s: state[0] = None
        return None
    if s.startswith(('"""', "'''")) and not (len(s) > 5 and s.endswith(s[:3])):
        state[0] = s[:3]; return None
    c = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", '""', ln)
    return re.sub(r"#.*$", "", c)


def code_lines(lines, ext, strip_code):
    """[(line number, code without comments/strings)] skipping blank and comment-only lines."""
    out, st, py_doc = [], [False], [None]
    keep_imports = BREAK("design_dup_names")
    for i, ln in enumerate(lines, 1):
        c = _py_code(ln, py_doc) if ext == ".py" else strip_code(ln, st)
        if c is None or not c.strip():
            continue
        if keep_imports or not BOILERPLATE.match(c):
            out.append((i, c))                                # include/import lists are boilerplate, not copied code
    return out


# ---------- A. copy-paste ----------
def _norm_line(c):
    return " ".join(t if t in KEEP or not re.match(r"[A-Za-z_$\d]", t) else ("N" if t[0].isdigit() else "I") for t in WORD.findall(c))


def _windows(per_file, n_lines):
    """{hash of n normalised lines: [(file, first index)]}, trivial windows left out."""
    need = (0.6 * n_lines) if not BREAK("design_round1") else max(3, n_lines // 3)
    seen = {}
    for p, cl in per_file.items():
        nl = [_norm_line(c) for _, c in cl]
        for k in range(len(cl) - n_lines + 1):
            win = nl[k:k + n_lines]
            if sum(len(x) for x in win) < 8 * n_lines // 2 or len(set(win)) < need:
                continue                                     # trivial windows: braces, tables of same-shaped lines
            seen.setdefault(hashlib.md5("\n".join(win).encode()).hexdigest(), []).append((p, k))
    return seen


def _pairs(seen, n_lines):
    """{(file A, file B, offset): [(index A, index B)]} for every two places with the same window."""
    pairs = {}
    for occ in seen.values():
        for a, b in ((a, b) for a in range(len(occ)) for b in range(a + 1, len(occ))):
            (pa, ka), (pb, kb) = occ[a], occ[b]
            if pa == pb and abs(ka - kb) < n_lines:
                continue                                     # overlapping copy of itself
            pairs.setdefault((pa, pb, ka - kb), []).append((ka, kb))
    return pairs


def _hit(per_file, pa, pb, run, n_lines):
    ka, kb = run[0]; la = per_file[pa]; lb = per_file[pb]; e = run[-1][0] + n_lines - 1; f = run[-1][1] + n_lines - 1
    if BREAK("design_round1") or same_names(la[ka:e + 1], lb[kb:f + 1], loose=True):
        return (pa, la[ka][0], la[e][0], pb, lb[kb][0], lb[f][0], e - ka + 1)
    return None


def _runs(ks):
    """Consecutive window pairs joined into runs."""
    ks.sort(); run = [ks[0]]
    for k in ks[1:]:
        if k[0] == run[-1][0] + 1:
            run.append(k); continue
        yield run; run = [k]
    yield run


def duplicates(per_file, n_lines):
    """per_file: {path: [(line, code)]}. Returns [(pathA, startA, endA, pathB, startB, endB, lines)]."""
    if BREAK("design_duplicates"):
        return []
    hits = []
    for (pa, pb, _), ks in _pairs(_windows(per_file, n_lines), n_lines).items():
        hits += [h for h in (_hit(per_file, pa, pb, run, n_lines) for run in _runs(ks)) if h]
    return hits

# ---------- A. copy-paste ----------


def same_names(a, b, loose=False):
    """A copy with some names changed keeps most of its names; two lookup tables of the same shape share almost none."""
    if BREAK("design_dup_names"):
        return True
    ids = lambda cl: {t for _, c in cl for t in re.findall(r"[A-Za-z_]\w*", c) if t not in KEEP}
    x, y = ids(a), ids(b)
    if loose:
        return True                                          # round 1 (9 Nov): renamed copies are copies; tables are caught above
    return len(x & y) >= 0.5 * max(len(x), len(y), 1)


# ---------- B. loops between systems ----------
INC = re.compile(r"""^\s*(?:#\s*(?:include|import)\s*[<"]([^>"]+)[>"]|import\s+(?:type\s+)?(?:[^'"]*?\sfrom\s+)?['"]([^'"]+)['"]"""
                 r"""|(?:const|let|var)\s+.*?require\(\s*['"]([^'"]+)['"]\s*\)|from\s+([\w.]+)\s+import|import\s+([\w.]+)"""
                 r"""|using\s+(?:static\s+)?(?:\w+\s*=\s*)?([\w.]+)\s*;)""")


def _named_systems(names):
    """{"Weather": ["Source/Private/Weather", ...]}: the system a path is under (longest folder first)."""
    pre = [(x.rstrip("/"), n) for n, xs in names.items() for x in ([xs] if isinstance(xs, str) else xs)]
    pre.sort(key=lambda t: -len(t[0]))
    return lambda p: next((n for x, n in pre if p == x or p.startswith(x + "/")), None)


def _listed_systems(names):
    order = sorted(names, key=len, reverse=True)
    return lambda p: next((n for n in order if p == n or p.startswith(n.rstrip("/") + "/")), None)


class _TopFolder:
    """The system of a path is its first folder under systems_root."""
    def __init__(self, root):
        self.root = root

    def __call__(self, p):
        root = self.root
        q = p[len(root) + 1:] if root and p.startswith(root + "/") else (p if not root else None)
        if not q or "/" not in q:
            return None
        return (root + "/" if root else "") + q.split("/")[0]


def systems_of(paths, s):
    names = s.get("systems") or []
    if isinstance(names, dict):
        return _named_systems(names)
    if names:
        return _listed_systems(names)
    return _TopFolder(s.get("systems_root", "").strip("/"))


def _index(per_file_raw, sys_of):
    """by_suffix: every tail of every path (and dotted module name) -> files; ns_home: namespace/package -> systems."""
    by_suffix, ns_home = {}, {}
    pkg_ext = () if BREAK("design_round2") else (".kt", ".kts", ".java", ".scala")
    for p in per_file_raw:
        parts = p.split("/")
        for k in range(len(parts)):
            by_suffix.setdefault("/".join(parts[k:]), []).append(p)
        noext = os.path.splitext(p)[0].split("/")
        for k in range(len(noext)):
            by_suffix.setdefault(".".join(noext[k:]), []).append(p)          # python dotted modules
        for ln in per_file_raw[p]:
            m = re.match(r"^\s*namespace\s+([\w.]+)", ln)
            if m and p.endswith(".cs"): ns_home.setdefault(m.group(1), set()).add(sys_of(p))
            m = re.match(r"^\s*package\s+([\w.]+)", ln)
            if m and p.endswith(pkg_ext):
                ns_home.setdefault(m.group(1), set()).add(sys_of(p))      # Kotlin/Java package: like a C# namespace
    return by_suffix, ns_home


def _namespace_targets(ref, ns_home):
    """C# using (also `using Book = A.B.Type;`) or a Kotlin/Java package import: the systems declaring it."""
    targets, r2 = ns_home.get(ref, set()), ref
    while not targets and "." in r2 and not BREAK("design_round2"):
        r2 = r2.rsplit(".", 1)[0]; targets = ns_home.get(r2, set())
    return targets


def _resolve(p, ref, py_from):
    """A relative import made relative to the project root."""
    if not ref.startswith("."):
        return ref
    if py_from:                                               # python relative import
        up = len(ref) - len(ref.lstrip(".")); base = p.split("/")[:-up] if up else p.split("/")[:-1]
        return "/".join(base + ref.lstrip(".").split("."))
    return os.path.normpath(os.path.join(os.path.dirname(p), ref)).replace("\\", "/")


IMPORT_TRY = ("", ".ts", ".tsx", ".js", ".jsx", ".py", ".h", ".hpp", "/index.ts", "/index.js", "/__init__.py")


def _file_targets(p, ref, m, by_suffix, sys_of):
    ref = _resolve(p, ref, m.group(4))
    cands = by_suffix.get(ref.lstrip("./"), []) or by_suffix.get(ref.replace(".", "/"), [])
    for ext in IMPORT_TRY:
        cands = cands or by_suffix.get(ref.lstrip("./") + ext, [])
    return {sys_of(c) for c in cands}


def _targets(p, ln, m, idx, sys_of):
    """The systems one include/import line reaches, or None when the line is skipped."""
    by_suffix, ns_home = idx
    ref = next(g for g in m.groups() if g)
    if BREAK("design_round2"):
        if "=" in ln and m.group(6): return None              # the old rule: alias usings were not read
    else:
        ref = re.sub(r"\.\*?$", "", ref)                    # import ledger.*  ->  ledger
    if m.group(6) or (not BREAK("design_round2") and m.group(5) and ref in ns_home):
        return _namespace_targets(ref, ns_home)
    return _file_targets(p, ref, m, by_suffix, sys_of)


def dependencies(per_file_raw, s):
    """{(from system, to system): (file, line, text)} for direct includes/imports that resolve to another system."""
    sys_of = systems_of(list(per_file_raw), s)
    idx = _index(per_file_raw, sys_of)
    edges = {}
    for p, lines in per_file_raw.items():
        a = sys_of(p)
        for i, ln, m in ((i, ln, INC.match(ln)) for i, ln in enumerate(lines, 1) if a):
            targets = _targets(p, ln, m, idx, sys_of) if m else None
            for b in (b for b in (targets or ()) if b and b != a):
                edges.setdefault((a, b), (p, i, ln.strip()[:80]))
    return edges

def cycles(edges):
    """Strongly connected groups of 2+ systems (Tarjan)."""
    if BREAK("design_cycles"):
        return []
    g = {}
    for a, b in edges: g.setdefault(a, set()).add(b); g.setdefault(b, set())
    idx, low, stack, on, out, n = {}, {}, [], set(), [], [0]
    def visit(v):
        idx[v] = low[v] = n[0]; n[0] += 1; stack.append(v); on.add(v)
        for w in sorted(g[v]):
            if w not in idx: visit(w); low[v] = min(low[v], low[w])
            elif w in on: low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v: break
            if len(comp) > 1: out.append(sorted(comp))
    for v in sorted(g):
        if v not in idx: visit(v)
    return out


# ---------- C. tangle ----------
DECIDE_C = re.compile(r"\b(if|for|foreach|while|case|catch)\b|&&|\|\||\?(?![?.:])|\?\?")
DECIDE_PY = re.compile(r"\b(if|elif|for|while|except|and|or|case)\b")


def tangle_clike(clean, start, end):
    """(complexity, max nesting) for a C-like function whose body is clean[start..end] (comment/string-free lines)."""
    cx, depth, deepest, base = 1, 0, 0, None
    for ln in clean[start:end + 1]:
        cx += len(DECIDE_C.findall(re.sub(r"\belse\s+if\b", "if", ln)))
        for ch in ln:
            if ch == "{":
                depth += 1
                if base is None: base = depth
                deepest = max(deepest, depth - base)
            elif ch == "}":
                depth -= 1
    return cx, deepest


def tangle_python(lines, start, end, head=None):
    """(complexity, max nesting) for a Python or GDScript function; head: the Python def line, for its syntax tree."""
    body = [l for l in lines[start + 1:end] if l.strip() and not l.strip().startswith("#")]
    if not body: return 1, 0
    deep = None if BREAK("design_nesting_lines") or head is None else _py_nesting(lines[head:end])
    if deep is not None:
        cx, _ = _tangle_python_lines(body)
        return cx, deep
    return _tangle_python_lines(body)


BLOCKS = ("For", "AsyncFor", "While", "If", "With", "AsyncWith", "Try", "TryStar", "Match")


def _py_nesting(src_lines):
    """The deepest blocks-inside-blocks of one Python function, from its syntax tree (the game's PC, 16 Nov: a long call
    wrapped over several lines was counted as 11 and 21 deep by its indentation). An elif is the same level as its if.
    None when the function's text doesn't parse on its own."""
    import ast, textwrap
    try:
        tree = ast.parse(textwrap.dedent("\n".join(src_lines)))
    except (SyntaxError, ValueError):
        return None
    fn = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if fn is None:
        return None

    def walk(stmts, depth):
        best = depth
        for st in stmts:
            kind = type(st).__name__
            if kind in BLOCKS:
                parts = [getattr(st, f, None) or [] for f in ("body", "orelse", "finalbody")]
                parts += [h.body for h in getattr(st, "handlers", [])] + [c.body for c in getattr(st, "cases", [])]
                for i, part in enumerate(parts):
                    if kind == "If" and i == 1 and len(part) == 1 and type(part[0]).__name__ == "If":
                        best = max(best, walk(part, depth))          # elif: the same level
                    else:
                        best = max(best, walk(part, depth + 1))
            elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                best = max(best, walk(st.body, depth))
        return best
    return walk(fn.body, 0)


def _tangle_python_lines(body):
    ind0 = min(len(l) - len(l.lstrip()) for l in body); unit = None; deepest = 0; cx = 1
    for l in body:
        code = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", '""', l); code = re.sub(r"#.*$", "", code)
        cx += len(DECIDE_PY.findall(code))
        d = len(l) - len(l.lstrip()) - ind0
        if d > 0 and unit is None: unit = d
        if unit: deepest = max(deepest, d // unit)
    return cx, deepest

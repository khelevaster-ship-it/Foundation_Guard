"""FoundationGuard: the files a short Python program in a command really writes (AI-made, Claude, 2026-11-12).

The game's PC, 12 Nov: a helper wrote the docs with python - <<'EOF' ... EOF, and the program's text only named a
guard script (Tools/Scripts/woods_handover_check.sh, in a sentence it wrote into a doc). The kit asked the owner to
change the script, because a guard file named beside a write counted as a write to it.

Now, for python -c '...' and python - <<'EOF' ... EOF, the kit reads the program itself (Python's own parser, nothing is
run). When every file it could write is a plain path written in the program (open('Docs/HANDOFF.md', 'w'),
Path('Docs/x.md').write_text(...), or a name set once to such a path), the command is judged by those files alone.
Anything the kit can't follow gives None, and the old rule (any guard file named in that part) applies as before:
  - a module outside a short list (re, json, os, sys, pathlib ...): shutil, subprocess, and the rest;
  - os.<anything> but os.path, os.getcwd, os.listdir, os.walk, os.environ and the like (os.remove, os.chdir, os.system);
  - exec, eval, compile, __import__, getattr, globals and the like; open or a module used as a value;
  - a path or mode that isn't plain text in the program (a variable set twice, a function's argument, an f-string);
  - a here-document whose end word isn't quoted and whose text holds $, ` or \\ (the shell changes such text first);
  - a program the parser can't read.
"""
import ast, os, re

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
PY = re.compile(r"^(?:python|python3|py)(?:[\d.]*)$")
VARIABLES = []                            # "python_variables" in foundationguard.json: variables the owner says hold Python
FLAGS = {"-I", "-u", "-B", "-E", "-s", "-S", "-q", "-O", "-OO", "-b", "-bb", "-3"}
HERE = re.compile(r"""^\s*(?P<cmd>[^\n<]*?)\s*<<(?P<dash>-?)\s*(?P<q>['"]?)(?P<d>\w+)(?P=q)(?P<rest>[^\n]*)\n(?P<body>.*?)\n(?P=d)\s*$""", re.S)
SAFE_IMPORTS = {"re", "json", "os", "os.path", "sys", "pathlib", "textwrap", "datetime", "collections", "itertools",
                "math", "string", "difflib", "glob", "fnmatch", "functools", "operator", "statistics", "time", "html",
                "unicodedata", "hashlib", "base64", "typing", "dataclasses", "enum", "decimal", "fractions", "random",
                "pprint", "copy", "bisect", "heapq", "calendar", "locale", "csv", "io"}
OS_OK = {"path", "getcwd", "listdir", "walk", "scandir", "environ", "getenv", "sep", "linesep", "name", "stat", "curdir",
         "pardir", "extsep", "altsep", "pathsep", "cpu_count", "getpid", "fspath"}
UNSAFE_NAMES = {"exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals", "vars",
                "__builtins__", "breakpoint", "memoryview"}
PATH_WRITES = {"write_text", "write_bytes", "unlink", "rename", "replace", "rmdir", "mkdir", "touch", "chmod", "lchmod",
               "symlink_to", "hardlink_to", "link_to", "open"}
IO_OK = {"StringIO", "BytesIO"}
# The kit's own modules, imported from its folder (sys.path.insert(0, 'fg')), with the calls that only read (the game's
# PC, 16 Nov: a check printed with python -c "...import config as C, structure as ST; print(ST.check(C.load()))" asked
# the owner, because the kit's modules made the program one the kit couldn't follow). Any other use of them stays unclear.
KIT_READS = {"config": {"load", "find_root", "guard_globs", "part"}, "structure": {"check", "measure", "load_baseline"},
             "approved": {"rows"}, "weaken": {"weaker"}, "ownerok": {"missing", "needing_ok", "explain"}}


def program(seg, tokens):
    """(the commands before it on its line, the Python program a command part runs inline), or None (not python, a
    script file, -m, or text the shell may still change)."""
    lead = []
    m = HERE.match(seg)
    if m:
        if m.group("dash") or m.group("rest").strip():
            return None
        if not m.group("q") and re.search(r"[$`\\]", m.group("body")):
            return None
        *lead, cmd = re.split(r"\s*(?:&&|\|\||;|\|)\s*", m.group("cmd"))   # cd Docs && python - <<'EOF'
        tk, code = tokens(cmd), m.group("body")
        if tk and tk[-1] == "-":
            tk = tk[:-1]
    else:
        tk, code = tokens(seg), None
    if tk and tk[0] == "env":
        tk = tk[1:]
    while tk and re.match(r"^[A-Za-z_]\w*=", tk[0]):          # PYTHONUTF8=1 python - <<'EOF'
        tk = tk[1:]
    if tk and not BREAK("python_variables") and re.sub(r"^\$\{?|\}$", "", tk[0]) in VARIABLES and tk[0].startswith("$"):
        tk = ["python"] + tk[1:]                # the game's PC, 20 Nov: "$PY" - <<'EOF' (the owner listed PY as Python)
    name = re.split(r"[\\/]", tk[0])[-1].lower() if tk else ""
    if not PY.match(name[:-4] if name.endswith(".exe") else name):
        return None
    rest = tk[1:]
    while rest and rest[0] in FLAGS:
        rest = rest[1:]
    if code is None:
        if len(rest) != 2 or rest[0] != "-c" or re.search(r"[$`]", rest[1]):
            return None
        return lead, rest[1]
    return (lead, code) if not rest else None


class _Unclear(Exception):
    pass


def _modules(tree):
    """{name bound by an import: the module}, or _Unclear for a module outside the short list."""
    mods = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name in KIT_READS and not BREAK("pywrites_kit_reads"):
                    mods[a.asname or a.name] = "kit:" + a.name
                    continue
                if a.name not in SAFE_IMPORTS:
                    raise _Unclear(a.name)
                mods[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "") in KIT_READS and not n.level and not BREAK("pywrites_kit_reads"):
                for a in n.names:
                    if a.name not in KIT_READS[n.module]:
                        raise _Unclear(a.name)
                    mods[a.asname or a.name] = "kitfn:" + n.module + "." + a.name
                continue
            if (n.module or "") not in SAFE_IMPORTS or n.level:
                raise _Unclear(n.module)
            for a in n.names:
                if n.module == "os" and a.name not in OS_OK or n.module == "io" and a.name not in IO_OK or a.name == "*":
                    raise _Unclear(a.name)
                mods[a.asname or a.name] = n.module + "." + a.name
    return mods


def _stores(tree):
    """{name: [the values it is set to]}; a name bound any other way (a loop, an argument, with ... as) gets None."""
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, []).append(n.value)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.setdefault(n.id, [])
        elif isinstance(n, ast.arg):
            out.setdefault(n.arg, []).append(None)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            for x in n.names:
                out.setdefault(x, []).append(None)
    for n in ast.walk(tree):                   # NAME = ... counted once above; every other store of it makes it unclear
        if isinstance(n, (ast.With, ast.AsyncWith)):
            targets = [i.optional_vars for i in n.items if i.optional_vars is not None]
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor, ast.comprehension, ast.NamedExpr)):
            targets = [n.target]
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.setdefault(n.name, []).append(None); continue
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.setdefault(n.name, []).append(None); continue
        else:
            continue
        for t in targets:
            for x in ast.walk(t):
                if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                    out.setdefault(x.id, []).append(None)
    return out


def _path(node, stores, mods, depth=0):
    """The plain path a value always is, or _Unclear."""
    if depth > 8:
        raise _Unclear("too deep")
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        vals = stores.get(node.id) or []
        if len(vals) != 1 or vals[0] is None:
            raise _Unclear(node.id)
        return _path(vals[0], stores, mods, depth + 1)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):                 # Path("Docs") / "x.md"
        return os.path.join(_path(node.left, stores, mods, depth + 1), _path(node.right, stores, mods, depth + 1))
    if isinstance(node, ast.Call) and not node.keywords:
        f = _dotted(node.func, mods)
        if f in ("pathlib.Path", "pathlib.PurePath", "pathlib.PosixPath", "pathlib.WindowsPath", "os.path.join") and node.args:
            return os.path.join(*[_path(a, stores, mods, depth + 1) for a in node.args])
    raise _Unclear("path")


def _dotted(node, mods):
    """'os.path.join' for os.path.join (through import names), else ''."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr); node = node.value
    if not isinstance(node, ast.Name) or node.id not in mods:
        return ""
    return ".".join([mods[node.id]] + parts[::-1])


def _mode(call):
    m = call.args[1] if len(call.args) > 1 else next((k.value for k in call.keywords if k.arg == "mode"), None)
    if m is None:
        return "r"
    if isinstance(m, ast.Constant) and isinstance(m.value, str):
        return m.value
    raise _Unclear("mode")


def _module_use(n, mods, parents):
    """A module name used outside a short list of reads (os.remove, shutil.anything, a module passed as a value)."""
    d = _dotted(n, mods) if isinstance(n, ast.Attribute) else (mods.get(n.id, "") if isinstance(n, ast.Name) else "")
    if not d:
        return
    top = d.split(".")
    if top[0].startswith(("kit:", "kitfn:")):
        _kit_use(n, top, parents)
        return
    if top[0] == "os" and len(top) > 1 and top[1] not in OS_OK:
        raise _Unclear(d)
    if top[0] == "io" and len(top) > 1 and top[1] not in IO_OK:
        called = isinstance(parents.get(n), ast.Call) and parents[n].func is n
        if d != "io.open" or not called or BREAK("python_io_open"):   # io.open(...) called is the built-in open (F513)
            raise _Unclear(d)
    if len(top) == 1 and not isinstance(parents.get(n), (ast.Attribute,)):
        raise _Unclear(d)                      # a module used as a value: it could be handed to anything


def _kit_use(n, top, parents):
    """A kit module only through a call that reads (KIT_READS), never as a value or with an attribute set."""
    p = parents.get(n)
    if top[0].startswith("kitfn:"):
        if not (isinstance(p, ast.Call) and p.func is n):
            raise _Unclear(top[0])
        return
    if isinstance(n, ast.Name):
        if not isinstance(p, ast.Attribute):
            raise _Unclear(top[0])
        return
    mod = top[0][4:]
    if len(top) != 2 or top[1] not in KIT_READS[mod] or not (isinstance(p, ast.Call) and p.func is n):
        raise _Unclear(".".join(top))


def _kit_path_only(tree, mods):
    """With the kit's modules imported, the only change to the module search path is the kit's own folder put first."""
    if not any(v.startswith(("kit:", "kitfn:")) for v in mods.values()):
        return
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr == "path" and isinstance(n.value, ast.Name) and mods.get(n.value.id) == "sys":
            pass
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Attribute) \
                and n.func.value.attr == "path" and isinstance(n.func.value.value, ast.Name) and mods.get(n.func.value.value.id) == "sys":
            a = n.args
            if n.func.attr != "insert" or len(a) != 2 or not isinstance(a[0], ast.Constant) or a[0].value != 0 or \
                    not isinstance(a[1], ast.Constant) or not isinstance(a[1].value, str) or \
                    os.path.basename(a[1].value.replace("\\", "/").rstrip("/")) != "fg":
                raise _Unclear("sys.path")
        if isinstance(n, (ast.Assign, ast.AugAssign)) and "sys" in ast.dump(n) and "path" in ast.dump(n):
            raise _Unclear("sys.path set")


def writes(code):
    """The plain paths this program could write, or None when the kit can't follow it."""
    if BREAK("python_writes"):
        return None
    try:
        tree = ast.parse(code)
        mods, stores = _modules(tree), _stores(tree)
        _kit_path_only(tree, mods)
        parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
        has_path = any(v.startswith("pathlib") for v in mods.values())
        out = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id in UNSAFE_NAMES:
                raise _Unclear(n.id)
            if isinstance(n, ast.Name) and n.id == "open" and not (isinstance(parents.get(n), ast.Call) and parents[n].func is n):
                raise _Unclear("open as a value")
            if isinstance(n, (ast.Name, ast.Attribute)):
                _module_use(n, mods, parents)
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if isinstance(f, ast.Name) and f.id == "open" or isinstance(f, ast.Attribute) and _dotted(f, mods) == "io.open":
                if not n.args:
                    raise _Unclear("open()")
                if re.search(r"[wax+]", _mode(n)):
                    out.append(_path(n.args[0], stores, mods))
            elif isinstance(f, ast.Attribute) and has_path and f.attr in PATH_WRITES and not _dotted(f, mods):
                if f.attr == "replace" and len(n.args) >= 2:          # text.replace(old, new): a string, not a file
                    continue
                if f.attr == "open" and not re.search(r"[wax+]", _mode_of_path_open(n)):
                    continue
                out.append(_path(f.value, stores, mods))
                if f.attr in ("rename", "replace", "link_to") and n.args:   # the file it moves to, too
                    out.append(_path(n.args[0], stores, mods))
        return out
    except (_Unclear, SyntaxError, ValueError, RecursionError, TypeError):
        return None


def _mode_of_path_open(call):
    m = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "mode"), None)
    if m is None:
        return "r"
    if isinstance(m, ast.Constant) and isinstance(m.value, str):
        return m.value
    raise _Unclear("mode")

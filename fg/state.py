"""FoundationGuard logic check, part 2: is every piece of state kept? (AI-made, Claude, 2026-11-11; v0.8.6)

A saved game must come back exactly as it was, and its fingerprint (the "same world?" number) must change whenever any
of it changes. A field that the save never writes comes back wrong after a load; a field the fingerprint leaves out lets
two different worlds look the same. Both slip past every test that never saves, loads and compares.

For each type the project lists, this reads the type's definition, lists every field, and reports each field that one of
its save, load or fingerprint functions never mentions, unless the project has written down why. It reads the text
only: it builds nothing, runs nothing and needs no AI. C++ and Python. Its answer is exact and takes under a second, so
it can stop an upload.

In foundationguard.json:
  "state": [{"type": "FWorld", "files": ["Source/**/World.h", "Source/**/World.cpp"],
             "save": ["FWorld::Serialize"], "load": ["FWorld::Serialize"], "fingerprint": ["FWorld::ComputeHash"],
             "reasons": {"Up": "worked out again from the home at every step"}}]
  A function may be named "Type::Name" or just "Name". The type's own functions that a listed function calls are read
  too, so a fingerprint made from the save's own bytes counts every field the save writes.
  A field that is only set back to a fixed value in a function (X = 0, X.Reset()) does not count as kept there: that is
  what a load does with a field the save never wrote.

  python fg/state.py              check every listed type (exit 1: a field without an answer; 2: something not found)
  python fg/state.py --suggest    list the types in the project that look like saved state, to choose from
  python fg/state.py --table      the whole table, field by field
Every upload runs it as the part "state" (switch it with fg/parts.py like the other parts). With no "state" list it
passes and says it is not set up.
Limits: it matches names, so a field named in a listed function for another reason counts as kept. It cannot tell a
harmless scratch value from state that steers the game, and it cannot judge a written reason. Fields held by a base
type, or made by a macro, are not seen. Both sides of a compile-time switch are read as one text.
"""
import fnmatch, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
KINDS = ("save", "load", "fingerprint")
CPP = (".h", ".hh", ".hpp", ".c", ".cc", ".cpp", ".cxx", ".inl")
PY = (".py",)
NOT_FIELD = re.compile(r"^\s*(?:static\b|friend\b|using\b|typedef\b|template\b|enum\b|struct\b|class\b|union\b|"
                       r"public\s*:|private\s*:|protected\s*:|virtual\b|explicit\b|operator\b|return\b)")
FIXED = r"(?:-?[\d.]+[fFuUlL]*|true|false|nullptr|INDEX_NONE|None|\w+::\w+(?:Vector|Zero\w*|None|Count)|\{\s*\}|\w+\(\s*\))"
RESET = re.compile(r"^\s*(?:=\s*(?:[\w.\[\]>-]+\s*=(?!=)\s*)*" + FIXED + r"[ \t]*(?:;|\n|$)|\.\s*(?:Reset|Empty|clear|Clear)\s*\(\s*\))")
ZEROED = re.compile(r"(?:\b(?:Memzero|memset|Memset|sizeof)\s*\(\s*&?\s*(?:[\w]+\s*(?:\.|->)\s*)*|"
                    r"\bfill\s*\(\s*(?:[\w]+\s*(?:\.|->)\s*)*(?:\w+\s*\.\s*begin\s*\(\s*\)\s*,\s*)?)$")
TARGET = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?=(?!=)")


def _strip(text, ext):
    """Comments and strings blanked (same length), so names in them never count."""
    pat = r'#[^\n]*|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'' if ext in PY else \
        r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''
    return re.sub(pat, lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def _close(text, i, o="{", c="}"):
    """Index just after the bracket that closes the one at i."""
    d = 0
    for j in range(i, len(text)):
        d += (text[j] == o) - (text[j] == c)
        if d == 0:
            return j + 1
    return len(text)


def _top_level(body):
    """The body with every nested {...} blanked, so method bodies and inner types never give fields."""
    out, d = [], 0
    for ch in body:
        d += ch == "{"
        out.append(ch if d == 0 or ch in "\n" else " ")
        if ch == "}" and d > 0:
            d -= 1
            if d == 0:
                out[-1] = ";"                               # an inline body ends a statement, as a ";" would
    return "".join(out)


def _declarators(stmt):
    """The names a field statement declares ("int32 A = 0, B = 1;" gives A and B)."""
    parts, d, cur = [], 0, ""
    for ch in stmt:
        d += ch in "(<[" ; d -= ch in ")>]"
        if ch == "," and d == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    names = []
    for p in parts:
        p = re.split(r"=|\{|(?<!:):(?!:)", p, maxsplit=1)[0]
        m = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*$", p.strip())
        if m:
            names.append(m.group(1))
    return names


def _lead(s):
    """A statement without what may stand before a field: access labels and engine macros such as UPROPERTY(...) or
    GENERATED_BODY() (an all-capitals name with its brackets; nothing else in a type's body looks like that)."""
    while True:
        m = re.match(r"^(?:public|private|protected)\s*:\s*", s)
        if not m and not BREAK("state_macro"):
            m = re.match(r"^[A-Z_][A-Z0-9_]*\s*\(", s)
            if m:
                m = re.match(r"^.{%d}\s*" % (_close(s, m.end() - 1, "(", ")")), s, re.S)
        if not m:
            return s
        s = s[m.end():]


def _no_templates(s):
    """Template arguments and array sizes taken out (TFunction<double(int)> F and T A[Size(K)] are fields, not functions)."""
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"<[^<>]*>|\[[^\[\]]*\]", "", s)
    return s


def cpp_fields(text, name):
    """[field] of struct/class `name` in C++ text, in order; None if the type is not defined there."""
    m = re.search(r"\b(?:struct|class)\s+(?:\w+_API\s+)?" + re.escape(name) + r"\b[^;{()]*\{", text)
    if not m:
        return None
    body = _top_level(text[m.end():_close(text, m.end() - 1) - 1])
    fields = []
    for stmt in body.split(";"):
        s = _lead(re.sub(r"\s+", " ", stmt.strip()))
        if not s or NOT_FIELD.match(s):
            continue
        fp = re.search(r"\(\s*\*\s*([A-Za-z_]\w*)\s*\)\s*\(", s)
        if fp and not BREAK("state_fnptr"):
            fields.append(fp.group(1)); continue            # a pointer to a function: one field
        bare = s if BREAK("state_template") else _no_templates(s)
        if re.search(r"\boperator\b", bare.split("(")[0]) or \
                re.match(r"^[\w:<>,*&\s\[\]]+?\s*\(", bare) and "=" not in bare.split("(")[0]:
            continue                                        # a function declaration
        fields += _declarators(s)
    return [f for f in fields if f not in ("const", "mutable")]


def py_fields(text, name):
    """[field] of Python class `name`: annotated class-level names and self.X set in __init__."""
    m = re.search(r"^(\s*)class\s+" + re.escape(name) + r"\b.*:\s*$", text, re.M)
    if not m:
        return None
    ind = len(m.group(1))
    lines = text[m.end():].split("\n")[1:]
    block = []
    for l in lines:
        if l.strip() and len(l) - len(l.lstrip()) <= ind:
            break
        block.append(l)
    body = "\n".join(block)
    out = re.findall(r"^\s{%d,}([A-Za-z_]\w*)\s*:\s*[^=\n]+" % (ind + 1), body, re.M)
    init = re.search(r"def __init__\(self[^)]*\):(.*?)(?=\n\s*def |\Z)", body, re.S)
    out += re.findall(r"self\.([A-Za-z_]\w*)\s*(?::[^=\n]+)?=", init.group(1) if init else "")
    return list(dict.fromkeys(out))


def _find_cpp_function(text, owner, fn):
    """Body of Owner::Fn(...) {...}, or of Fn(...) {...} written inside the type, or None."""
    for pat in (re.escape(owner) + r"\s*::\s*" + re.escape(fn), r"(?<![\w:])" + re.escape(fn)):
        for m in re.finditer(r"\b" + pat + r"\s*\(", text):
            close = _close(text, m.end() - 1, "(", ")")
            tail = re.match(r"\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:->[^{;]*)?\{", text[close:])
            if tail:
                start = close + tail.end() - 1
                return text[start:_close(text, start)]
    return None


def _find_py_function(text, owner, fn):
    m = re.search(r"^(\s*)def\s+" + re.escape(fn) + r"\s*\(", text, re.M)
    if not m:
        return None
    ind, out = len(m.group(1)), []
    for l in text[m.end():].split("\n")[1:]:
        if l.strip() and len(l) - len(l.lstrip()) <= ind:
            break
        out.append(l)
    return "\n".join(out)


def _calls(body):
    """The names a body calls; a fingerprint written from the save itself (Writer << *this) calls Serialize."""
    if BREAK("state_follow"):
        return set()
    calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body))
    if re.search(r"<<\s*(?:const_cast<[^>]*>\s*\()?\s*\*\s*this", body):
        calls.add("Serialize")
    return calls


def _bodies(texts, owners, owner, fn, py, seen=None):
    """The function's body and the bodies of the functions of its own type, or of the checked type, that it calls."""
    seen = set() if seen is None else seen
    if (owner, fn) in seen:
        return ""
    seen.add((owner, fn))
    find = _find_py_function if py else _find_cpp_function
    body = next((b for b in (find(t, owner, fn) for t in texts) if b is not None), None)
    if body is None:
        return None
    order = [owner] + [x for x in owners if x != owner]     # the caller's own type first, then the checked type
    more = [_bodies(texts, owners, o, c, py, seen) for c in sorted(_calls(body)) for o in order if c in owners.get(o, ())]
    return body + "\n" + "\n".join(b for b in more if b)


def kept_in(body, field, kind=None):
    """True when the body uses the field other than by setting it back to a fixed value (or zeroing it). In a save
    function a field that is only set (X = ...) is not saved either: something else is written in its place."""
    for m in re.finditer(r"(?<![\w])" + re.escape(field) + r"(?!\w)", body):
        after, before = body[m.end():m.end() + 200], body[max(0, m.start() - 60):m.start()]
        if BREAK("state_reset"):
            return True
        if RESET.match(after) or ZEROED.search(before):
            continue
        if kind == "save" and TARGET.match(after) and not BREAK("state_assign"):
            continue
        return True
    return False


def _methods(texts, owner, py):
    names = set()
    for t in texts:
        names |= set(re.findall(r"\b" + re.escape(owner) + r"\s*::\s*([A-Za-z_]\w*)\s*\(", t))
        names |= set(re.findall(r"^\s*def\s+([A-Za-z_]\w*)", t, re.M)) if py else set()
        body = re.search(r"\b(?:struct|class)\s+(?:\w+_API\s+)?" + re.escape(owner) + r"\b[^;{()]*\{", t)
        if body and not py:
            inner = t[body.end():_close(t, body.end() - 1)]
            names |= set(re.findall(r"([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:override\s*)?\{", inner))
    return names


def _files(root, globs):
    out = []
    for g in globs:
        out += [p for p in glob.glob(os.path.join(root, g), recursive=True) if os.path.isfile(p)]
    return sorted(set(out))


def _short(f):
    return f.split("::")[-1]


def _read(root, item):
    """(texts, python?, fields) of a listed type, or a problem (exit code, message)."""
    name = item.get("type", "")
    files = _files(root, item.get("files") or [])
    exts = {os.path.splitext(f)[1].lower() for f in files}
    if not files:
        return (2, f"{name}: no files match {item.get('files')}")
    if not exts <= set(CPP + PY):
        return (2, f"{name}: this check reads C++ and Python only, not {', '.join(sorted(exts - set(CPP + PY)))}")
    py = exts <= set(PY)
    texts = [_strip(open(f, encoding="utf-8-sig", errors="replace").read(), ".py" if py else ".cpp") for f in files]
    fields = next((x for x in ((py_fields if py else cpp_fields)(t, name) for t in texts) if x is not None), None)
    if fields is None:
        return (2, f"{name}: its definition was not found in {len(files)} file(s)")
    if not fields:
        return (2, f"{name}: no fields found in its definition")
    return texts, py, fields


def _owners(texts, item, py):
    """{type: its function names} for the checked type and every type a listed function belongs to."""
    names = {item.get("type", "")} | {f.rsplit("::", 1)[0] for k in KINDS for f in item.get(k) or [] if "::" in f}
    return {o: _methods(texts, o, py) for o in sorted(names)}


def table(root, item):
    """(fields, {kind: {field: kept?}}, problems). A problem is (exit code, message)."""
    got = _read(root, item)
    if isinstance(got[0], int):
        return [], {}, [got]
    texts, py, fields = got
    name = item.get("type", "")
    owners = _owners(texts, item, py)
    cols, problems = {}, []
    for kind in [k for k in KINDS if item.get(k)]:
        fns = item[kind]
        bodies = [_bodies(texts, owners, f.rsplit("::", 1)[0] if "::" in f else name, _short(f), py) for f in fns]
        problems += [(2, f"{name}: the {kind} function {f} was not found") for f, b in zip(fns, bodies) if b is None]
        text = "\n".join(b for b in bodies if b)
        cols[kind] = {f: kept_in(text, f, kind) for f in fields}
    return fields, cols, problems


def judge(item, fields, cols):
    """(unanswered [(field, kinds)], stale reasons [message])."""
    reasons = item.get("reasons") or {}
    gaps = [(f, [k for k in cols if not cols[k][f]]) for f in fields]
    gaps = [(f, ks) for f, ks in gaps if ks]
    unanswered = [(f, ks) for f, ks in gaps if f not in reasons or BREAK("state_reasons")]
    stale = []
    for f, why in reasons.items():
        if f not in fields:
            stale.append(f"a reason is written for '{f}', but {item.get('type')} has no such field")
        elif f not in dict(gaps):
            stale.append(f"a reason is written for '{f}', but every listed function keeps it: take the reason out")
        elif len(str(why).split()) < 3 and not BREAK("state_short"):
            stale.append(f"the reason for '{f}' is too short to tell a reader anything: \"{why}\"")
    return unanswered, stale


def _item_lines(root, item):
    """(report lines, problems, worst exit code) for one listed type."""
    fields, cols, problems = table(root, item)
    if problems:
        return ["  CANNOT CHECK " + msg for _, msg in problems], 0, max(c for c, _ in problems)
    unanswered, stale = judge(item, fields, cols)
    lines = [f"  NOT KEPT  {item['type']}.{f}: not in its {' or '.join(ks)} (keep it, or write why in \"reasons\")"
             for f, ks in unanswered]
    lines += [f"  REASON    {item['type']}: {m}" for m in stale]
    lines.append(f"  {item['type']}: {len(fields)} fields, {len(unanswered)} without an answer, "
                 f"{len(item.get('reasons') or {})} with a written reason")
    bad = len(unanswered) + len(stale)
    return lines, bad, 1 if bad else 0


def check(cfg):
    """(passed?, report, exit code) for every listed type. Exit 2 (something not found) makes it fail too."""
    items = cfg.get("state") or []
    if not items:
        return True, "STATE not set up (no \"state\" list in foundationguard.json)", 0
    lines, bad, worst = [], 0, 0
    for item in items:
        more, b, w = _item_lines(cfg["_root"], item)
        lines, bad, worst = lines + more, bad + b, max(worst, w)
    cannot = sum(l.startswith("  CANNOT CHECK") for l in lines)
    said = [s for s in (f"{bad} problem(s)" if bad else "", f"{cannot} could not be checked" if cannot else "") if s]
    head = f"STATE {len(items)} type(s): " + (", ".join(said) or "every field kept or explained")
    return worst == 0, head + ("\n" + "\n".join(lines) if lines else ""), worst


def suggest(root):
    """Types that look like saved state: a type with a Save, Load, Serialize or Hash function of its own."""
    hits = {}
    for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if os.path.splitext(p)[1].lower() not in CPP + PY or "/.git/" in p or not os.path.isfile(p):
            continue
        t = _strip(open(p, encoding="utf-8-sig", errors="replace").read(), os.path.splitext(p)[1].lower())
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s*::\s*(Serialize|Save|Load|Hash|ComputeHash|GetStateHash|Fingerprint)\s*\(", t):
            hits.setdefault(m.group(1), set()).add(m.group(2))
        for m in re.finditer(r"^\s*class\s+(\w+)[^\n]*:\s*\n((?:[ \t]+[^\n]*\n|\s*\n)*)", t, re.M):
            fs = set(re.findall(r"def\s+(save|load|to_dict|from_dict|fingerprint|__hash__|serialize)\b", m.group(2)))
            if fs:
                hits.setdefault(m.group(1), set()).update(fs)
    return hits


def _print_table(cfg):
    for item in cfg.get("state") or []:
        fields, cols, problems = table(cfg["_root"], item)
        print(f"{item.get('type')}: " + "  ".join(k for k in cols))
        for f in fields:
            print(f"  {f:30} " + "  ".join(("kept" if cols[k][f] else "----").ljust(len(k)) for k in cols))
        for _, msg in problems:
            print("  CANNOT CHECK " + msg)


def main(argv):
    cfg = C.load()
    if "--suggest" in argv:
        for name, fns in sorted(suggest(cfg["_root"]).items()):
            print(f"  {name}: {', '.join(sorted(fns))}")
        return 0
    if "--table" in argv:
        _print_table(cfg); return 0
    ok, report, code = check(cfg)
    print(report)
    return code


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""FoundationGuard: changes that only add checks or raise a floor, judged without the owner's box (AI-made, Claude,
2026-11-24; the owner's choice that day: "Yes, kit change" to "Let added checks and test-floor raises through without
a box?", after 7 of 16 boxes on 23 Nov were adds only. His words of 21 Nov: "next time you dont need to ask about
adding checks").

Each rule is narrow and is judged by what changed, never by what the helper says. Anything else still asks:
  - a floor file (one number, its name says floor or min) raised, or a cap file (cap, max, limit) lowered (F547);
  - a recorded value written into a test where it was 0, on a line that asserts nothing (F548);
  - a new case function added with one "failed += new_case()" line beside the ones already there (F549);
  - a new block in a shell check script that only adds a check: closed, no exit, no early way out, no write
    to a file an older line uses, no change to an older variable but setting the one it exits with to fail (F550);
  - a new pin or recorded-value file (a data file in a testdata, pins, golden, fixtures, expected or recorded
    folder); a rewrite of one that is there still asks (F551).
The change is still logged, and the gate still runs every check before an upload.
"""
import os, re

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

NUMBER_FILE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*$")
FLOOR_NAME = re.compile(r"(?:^|[_\-./])(?:floor|min|minimum|at_least|atleast)(?:[_\-./]|$)", re.I)
CAP_NAME = re.compile(r"(?:^|[_\-./])(?:cap|max|maximum|limit|at_most|atmost|ceiling)(?:[_\-./]|$)", re.I)


def floor_raise(path, old, new):
    """None when a one-number floor file goes up (or a cap file down); else a reason, or "" when the rule doesn't apply."""
    a, b = NUMBER_FILE.match(old or ""), NUMBER_FILE.match(new or "")
    if not (a and b) or BREAK("floor_raise"):
        return ""
    x, y = float(a.group(1)), float(b.group(1))
    name = os.path.basename(path.replace("\\", "/"))
    floor, cap = FLOOR_NAME.search(name), CAP_NAME.search(name)
    if floor and not cap:
        return None if y >= x else "it lowers a floor (%s to %s)" % (a.group(1), b.group(1))
    if cap and not floor:
        return None if y <= x else "it raises a cap (%s to %s)" % (a.group(1), b.group(1))
    return ""


LITERAL = re.compile(r"(?<![\w.])(0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?)([uUlLfF]*)(?![\w.])")
ASSERTS = re.compile(r"\b(?:assert\w*|Test[A-Z]\w*|EXPECT_\w+|ASSERT_\w+|check\w*|CHECK\w*|expect|should|verify\w*|require\w*)\s*\(?",
                     re.I)


def _value(t):
    try:
        return int(t, 16) if t.lower().startswith("0x") else float(t)
    except ValueError:
        return None


def recorded_fill(old_lines, new_lines):
    """True when each changed line differs only where a number that was 0 is now a recorded value, and asserts nothing."""
    if BREAK("recorded_fill") or len(old_lines) != len(new_lines) or not old_lines:
        return False
    for o, n in zip(old_lines, new_lines):
        if LITERAL.sub("#", o) != LITERAL.sub("#", n) or ASSERTS.search(o) or ASSERTS.search(n):
            return False
        for (x, _), (y, _) in zip(LITERAL.findall(o), LITERAL.findall(n)):
            if x != y and not (_value(x) == 0 and _value(y) not in (None, 0)):
                return False
    return True


ACCUMULATE = re.compile(r"^\s*([A-Za-z_]\w*)\s*\+=\s*([A-Za-z_]\w*)\s*\(.*\)\s*;?\s*$")
DEFINES = re.compile(r"^\s*(?:def|async\s+def|function)\s+([A-Za-z_]\w*)\s*\(|^\s*(?:static\s+)?(?:int|bool|int32|uint32)\s+([A-Za-z_]\w*)\s*\(")


def new_functions(added):
    return {g for l in added for m in [DEFINES.match(l)] if m for g in m.groups() if g}


def accumulates(block, before, after, old_lines, defined):
    """True when every line of this block adds a new case function's count to a total the file already adds to, and
    sits beside a line that already does."""
    if BREAK("accumulate_case") or not any(l.strip() for l in block):
        return False
    old_totals = {m.group(1) for l in old_lines for m in [ACCUMULATE.match(l)] if m}
    for l in block:
        if not l.strip():
            continue
        m = ACCUMULATE.match(l)
        if not (m and m.group(1) in old_totals and m.group(2) in defined):
            return False
    near = [x for x in (before[-1:] + after[:1]) if x.strip()]
    return any((ACCUMULATE.match(x) or [None, None])[1] in old_totals for x in near if ACCUMULATE.match(x))


SH_OPEN = {"if": "fi", "case": "esac", "do": "done", "{": "}"}
SH_OUT = re.compile(r"(?:^\s*|[;&|]\s*|\bthen\s+|\belse\s+|\bdo\s+)(exit|return|continue|break|exec|eval|source|cd|pushd|popd|"
                    r"trap|unset|shift|set|export|alias|read|kill)\b|(?:^|\s)\.\s|\|\|\s*(?:true|:)\b|^\s*[A-Za-z_]\w*\s*\(\s*\)|"
                    r"\bfunction\s+\w|<<")
SH_SET = re.compile(r"(?:^\s*|[;&|]\s*|\bthen\s+|\belse\s+)([A-Za-z_]\w*)=([^\s;&|]*)")
SH_WRITE = re.compile(r"\b(?:cp|mv|ln|rm|install|truncate|dd|touch)\b((?:\s+(?:-\S+|\"[^\"]*\"|'[^']*'|[^\s;&|]+))*)")
SH_REDIRECT = re.compile(r"(?<![0-9&])(>{1,2})\s*(\"[^\"]*\"|'[^']*'|[^\s;&|]+)|\btee\s+((?:-\S+\s+)*)(\"[^\"]*\"|[^\s;&|]+)")


def _vars(text):
    return set(re.findall(r"\$\{?([A-Za-z_]\w*)", text))


def _own_target(t, mine):
    t = t.strip("\"'")
    m = re.fullmatch(r"\$\{?([A-Za-z_]\w*)\}?", t)
    return bool(m and m.group(1) in mine)


def _sh_balanced(block):
    stack = []
    for l in block:
        code = re.sub(r"#.*$", "", re.sub(r"\"[^\"]*\"|'[^']*'", "\"\"", l))
        for w in re.findall(r"(?<![\w$-])(if|fi|case|esac|do|done|\{|\})(?![\w-])", code):
            if w in SH_OPEN:
                stack.append(SH_OPEN[w])
            elif not stack or stack.pop() != w:
                return False
    return not stack


def shell_block(block, old_lines):
    """None when this block of a shell check script only adds a check, else the reason it asks."""
    if BREAK("shell_check_block"):
        return "the kit doesn't judge shell check scripts"
    if not _sh_balanced(block):
        return "it opens something it doesn't close (an if, a loop or a brace)"
    old_text = "\n".join(old_lines)
    old_vars = _vars(old_text) | {m.group(1) for l in old_lines for m in SH_SET.finditer(l)}
    fails = set(re.findall(r"\bexit\s+\"?\$\{?([A-Za-z_]\w*)", old_text))     # the flag the script exits with
    mine = set()
    for l in block:
        code = re.sub(r"(?<!\S)#.*$", "", l)
        if not code.strip():
            continue
        out = SH_OUT.search(code)
        if out:
            return "it adds a line that could end or change the checks already there: " + l.strip()[:80]
        for m in SH_SET.finditer(code):
            name, val = m.group(1), m.group(2)
            if name in old_vars and not (name in fails and re.fullmatch(r"[1-9]\d*", val)):
                return "it sets a variable the older lines use: " + l.strip()[:80]
            if name not in old_vars:
                mine.add(name)
        for m in SH_WRITE.finditer(code):
            words = [w for w in re.findall(r"\"[^\"]*\"|'[^']*'|[^\s]+", m.group(1) or "") if not w.startswith("-")]
            if not words or not _own_target(words[-1], mine):
                return "it writes a file the older lines may use: " + l.strip()[:80]
        for m in SH_REDIRECT.finditer(code):
            if m.group(1):
                target, append = m.group(2), m.group(1) == ">>"
            else:
                target, append = m.group(4), "-a" in (m.group(3) or "")
            if target.strip("\"'") in ("/dev/null", "&1", "&2") or _own_target(target, mine):
                continue
            if not (append and re.fullmatch(r"\"?\$\{?[A-Za-z_]\w*\}?\"?", target)):
                return "it writes a file the older lines may use: " + l.strip()[:80]
    return None


RECORD_DIR = re.compile(r"(?:^|/)(?:testdata|test_data|pins?|golden|goldens|fixtures|expected|recorded|recordings|snapshots)/",
                        re.I)
DATA_FILE = re.compile(r"\.(?:txt|json|csv|tsv|dat|bin|hex|yaml|yml|xml)$", re.I)


def new_record(path, old, new):
    """True for a new pin or recorded-value file (a data file in a testdata, pins, golden ... folder)."""
    if BREAK("new_record_file") or (old or "").strip():
        return False
    p = path.replace("\\", "/")
    return bool(RECORD_DIR.search(p) and DATA_FILE.search(p) and (new or "").strip())

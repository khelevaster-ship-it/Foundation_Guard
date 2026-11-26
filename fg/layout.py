"""FoundationGuard: a change that only moves spaces and line breaks (AI-made, Claude, 2026-11-13; outside review 5).

A formatter (black, clang-format, gdformat) run over the tests changes guard files without changing what any test
checks. The check after every step put those changes back while the code beside them stayed formatted, so a helper
asked to format the project went round in circles (outside review 5, Claude Fable, 13 Nov). Now such a change stays.

Only a change that cannot alter what runs counts:
  - Python: the code means exactly the same to Python (its syntax tree is equal). That is the test black itself uses.
    Moving an assert into or out of a block changes the tree, so it doesn't count.
  - Every other language: the same lines in the same order; each line differs only in spaces and tabs outside quoted
    text; and the nesting by indent stays the same. Joining or splitting lines doesn't count (a joined line could fall
    into a comment), nor does any change inside quotes.
"""
import ast, io, os, re, tokenize

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
QUOTES = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")


def _comments(text):
    out = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(text).readline):
            if t.type == tokenize.COMMENT:
                out.append(t.string.strip())
    except (tokenize.TokenError, SyntaxError):
        return None
    return out


def _python_same(old, new):
    """The same syntax tree, and the same comments (a comment can be a marker the kit reads, such as a waiver)."""
    try:
        same = ast.dump(ast.parse(old)) == ast.dump(ast.parse(new))
    except (SyntaxError, ValueError):
        return False
    return same and _comments(old) is not None and _comments(old) == _comments(new)


def _depths(lines):
    """The nesting depth of each line by its indent (as Python counts blocks), so 4 spaces to 2 or tabs keeps it."""
    stack, out = [0], []
    for l in lines:
        w = len(l) - len(l.lstrip(" \t"))
        if w > stack[-1]:
            stack.append(w)
        while w < stack[-1]:
            stack.pop()
        if w != stack[-1]:
            return None                                # a dedent to a width never used: not a clean nesting
        out.append(len(stack))
    return out


def _line_same(a, b):
    if QUOTES.findall(a) != QUOTES.findall(b):
        return False
    cut = lambda s: re.sub(r"\s+", "", QUOTES.sub("\0", s))
    return cut(a) == cut(b)


def _lines_same(old, new):
    a = [l for l in old.splitlines() if l.strip()]
    b = [l for l in new.splitlines() if l.strip()]
    if len(a) != len(b) or not all(_line_same(x, y) for x, y in zip(a, b)):
        return False
    da, db = _depths(a), _depths(b)
    return da is not None and da == db


def only_layout(path, old, new):
    """True when old and new (bytes) differ only in spaces and line breaks that can't change what runs."""
    if BREAK("steps_layout") or old is None or new is None or old == new:
        return False
    try:
        a, b = old.decode("utf-8"), new.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if a.replace("\r\n", "\n") == b.replace("\r\n", "\n"):
        return True                                    # line endings only
    if path.lower().endswith((".py", ".pyi")):
        return _python_same(a, b)
    return _lines_same(a, b)

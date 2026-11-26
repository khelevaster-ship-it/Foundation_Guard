"""Harness for pass line M10 of the logic check (AI-made, Claude, 2026-11-11): no false alarm from unbuilt lines.
Reads the compile-time switches (#if defined(X), #if !defined(X), #elif, #else, #endif) of the source itself, WITHOUT
the tool's code, and says for every change in the tool's results whether its line is switched off in the tested build.
In the tested build no switch is defined.
Usage: ifblocks.py PROJECT RESULTS.json [RESULTS2.json ...]"""
import json, re, sys

project, results = sys.argv[1], sys.argv[2:]
DEFINED = set()
COND = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")


def value(expr):
    expr = expr.split("//")[0].strip()
    m = re.fullmatch(r"(!?)\s*defined\s*\(\s*(\w+)\s*\)", expr)
    assert m, ("a switch this script does not know", expr)
    on = m.group(2) in DEFINED
    return (not on) if m.group(1) else on


def off_lines(path):
    """The line numbers that the compiler skips."""
    off, stack = set(), []                    # stack of [parent active, some branch already taken, this branch active]
    for n, line in enumerate(open(path, encoding="utf-8", errors="replace").read().split("\n"), 1):
        m = COND.match(line)
        active = all(s[2] for s in stack)
        if not m:
            if not active:
                off.add(n)
            continue
        kind, rest = m.group(1), m.group(2)
        if kind in ("if", "ifdef", "ifndef"):
            v = value(rest) if kind == "if" else ((rest.strip() in DEFINED) == (kind == "ifdef"))
            stack.append([active, v, v])
        elif kind == "elif":
            s = stack[-1]; v = (not s[1]) and value(rest); s[1], s[2] = s[1] or v, v
        elif kind == "else":
            s = stack[-1]; s[2] = not s[1]; s[1] = True
        else:
            stack.pop()
    assert not stack, path
    return off


cache, bad, rows = {}, 0, {"not noticed": [0, 0], "not built": [0, 0], "noticed": [0, 0]}
for r in results:
    for t in json.load(open(r))["tried"]:
        off = cache.setdefault(t["path"], off_lines(project + "/" + t["path"]))
        is_off = t["line"] in off
        rows[t["result"]][1 if is_off else 0] += 1
        if is_off and t["result"] != "not built":
            bad += 1
            print("FALSE ALARM  %s:%d is switched off in the tested build but the tool says '%s'" % (t["path"], t["line"], t["result"]))
        if not is_off and t["result"] == "not built":
            print("NOTE  %s:%d is not switched off by an #if but the tool says 'not built'  | %s" % (t["path"], t["line"], t["text"]))
for k in ("noticed", "not noticed", "not built"):
    print("%-12s on built lines: %3d   on switched-off lines: %3d" % (k, rows[k][0], rows[k][1]))
print("M10 %s: %d changes on switched-off lines carry a verdict other than 'not built'" % ("PASS" if bad == 0 else "FAIL", bad))

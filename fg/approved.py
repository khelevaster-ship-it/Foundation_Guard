"""FoundationGuard approved list (AI-made, Claude, 2026-11-08).

APPROVED.md holds one table row per behaviour the owner signed off:
  | ID | Behaviour | Owner's words | Check | Break |
  | A001 | Old saves still load | "Yes, keep that" (owner, 2026-11-05) | test_old_saves | env:SAVE_COMPAT=0 |
Check = the name of the automatic check that guards it. Break = how to break the feature on purpose, so the check can be
proven: `env:NAME=VALUE` (set while the check runs) or `patch:path/to/file.patch` (applied, then reverted).
The gate fails if a row has no check or no break, or if its check didn't run and pass in the gate's test log.
"""
import os, re, sys, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


FIXED = {"behaviour": 1, "words": 2, "check": 3, "break": 4, "paths": 5, "reviewed": 6}
NAMES = {"behaviour": ("behaviour", "behavior"), "words": ("owner's words", "words", "owner words"),
         "check": ("check", "checks"), "break": ("break", "breaks"), "paths": ("paths", "files"),
         "reviewed": ("reviewed",)}


def _cells(line):
    return [x.strip() for x in line.strip().strip("|").split("|")]


def columns(header):
    """Which column holds what (game build, 13 Nov: its list is ID | Date | Behaviour | Words | Checks | Proven | Break).
    Read from the table's header by name when the header names a Check and a Break column; else the kit's own layout."""
    c = [x.lower() for x in _cells(header or "")]
    named = {k: next((i for i, h in enumerate(c) if h in words), None) for k, words in NAMES.items()}
    if BREAK("approved_columns") or named["check"] is None or named["break"] is None:
        return dict(FIXED)
    extra = {k: FIXED[k] for k, i in named.items() if i is None and FIXED[k] >= len(c)}   # unnamed columns past the header
    return {**named, **extra}


def _cell(c, col, key):
    i = col.get(key)
    return c[i] if i is not None and i < len(c) else ""


def _row_of(line, col=None):
    """One APPROVED.md table line as a row, or None."""
    col = col or FIXED
    c = _cells(line)
    ok_id = r"^[A-Z]+\d+$" if BREAK("approved_ids") else r"^[A-Za-z][A-Za-z0-9_.-]*$"
    if len(c) < 5 or not re.match(ok_id, c[0]) or c[0].lower() == "id" or set(c[0]) <= set("-:"):
        return None
    paths = [x.strip() for x in _cell(c, col, "paths").split(",") if x.strip()]
    reviewed = _cell(c, col, "reviewed")
    return {"id": c[0], "behaviour": _cell(c, col, "behaviour"), "words": _cell(c, col, "words"),
            "check": _cell(c, col, "check"), "break": _cell(c, col, "break"), "paths": paths,
            "reviewed": "" if reviewed == "-" else reviewed}


def rows(cfg):
    p = os.path.join(cfg["_root"], cfg["approved_file"])
    if not os.path.exists(p):
        return []
    out, col = [], FIXED
    for line in open(p, encoding="utf-8"):
        if _cells(line)[0].lower() == "id":
            col = columns(line)                      # each table's own header says where its columns are
        r = _row_of(line, col)
        if r:
            out.append(r)
    return out


def _junit(tree, res):
    for tc in tree.iter("testcase"):
        bad = any(ch.tag in ("failure", "error", "skipped") for ch in tc)
        for name in (tc.get("name"), (tc.get("classname") or "") + "." + (tc.get("name") or "")):
            res[name] = res.get(name, True) and not bad


def _nunit(tree, res):
    """NUnit 3 results (Unity's Test Framework)."""
    for tc in tree.iter("test-case"):
        ok = tc.get("result") == "Passed"
        for name in (n for n in (tc.get("name"), tc.get("fullname")) if n):
            res[name] = res.get(name, True) and ok


def results(log):
    """{check name: True/False} from a JUnit XML file or 'PASS name' / 'FAIL name' lines."""
    res = {}
    if not log or not os.path.exists(log):
        return res
    txt = open(log, encoding="utf-8", errors="replace").read()
    if not txt.lstrip().startswith("<"):
        return {m.group(2): m.group(1) == "PASS" for m in re.finditer(r"^(PASS|FAIL|SKIP)\s+(\S+)", txt, re.M)}
    tree = ET.fromstring(txt)
    _junit(tree, res)
    if not BREAK("engine_nunit"):
        _nunit(tree, res)
    return res


def _row_problem(r, cfg, got):
    """Why one approved row isn't guarded, or None."""
    if not r["check"] or r["check"] in ("-", "none"):
        return f"{r['id']}: no check named"
    if not re.match(r"^(env:[A-Za-z_]\w*=.*|patch:.+)$", r["break"]):
        return f"{r['id']}: no way to break it on purpose (Break column), so its check can't be proven"
    if not cfg.get("test_log") and not cfg.get("_steps_log"):
        return None
    c = r["check"]
    hit = [v for k, v in got.items() if k == c or k.endswith("." + c) or k.endswith("::" + c)]
    if not hit and not BREAK("approved_missing"):
        return f"{r['id']}: its check {c} didn't run"
    if hit and not all(hit):
        return f"{r['id']}: its check {c} failed"
    return None


def _review_note(R, cfg, bad):
    """The REVIEW lines: which checks a second helper looked at."""
    unrev = [r["id"] for r in R if not r.get("reviewed")]
    other = [r["id"] for r in R if re.search(r"(?i)\b(owner|model|other[- ]ai)\b", r.get("reviewed", ""))]
    msg = (f"\nREVIEW {len(R) - len(unrev)} of {len(R)} checks reviewed by a helper that didn't write them; "
           f"{len(other)} spot-checked by another AI model or the owner")
    if unrev:
        msg += ("\n  not reviewed yet: " + ", ".join(unrev[:20]) + (" ..." if len(unrev) > 20 else "") +
                "\n  (a fresh helper follows REVIEW_PROMPT.md; python fg/approve.py --spot makes a prompt for another AI model)")
        if cfg.get("require_review"):
            bad.append("unreviewed checks: " + ", ".join(unrev[:20]))
    return msg


def check(cfg, got=None):
    """got: {check name: passed} from a staged gate (fg/stages.py); without it the one test report is read."""
    R = rows(cfg)
    if got is None:
        got = results(os.path.join(cfg["_root"], cfg["test_log"]) if cfg.get("test_log") else None)
    bad = [p for p in (_row_problem(r, cfg, got) for r in R) if p]
    msg = f"APPROVED {len(R) - len(bad)} of {len(R)} approved behaviours checked" + ("" if not bad else ":\n  " + "\n  ".join(bad))
    if not BREAK("review_col") and R:
        msg += _review_note(R, cfg, bad)
    return not bad, msg

if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    import config as C
    ok, msg = check(C.load()); print(msg); sys.exit(0 if ok else 1)

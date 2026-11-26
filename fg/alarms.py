"""FoundationGuard alarm sorter: what kind of red is it? (AI-made, Claude, 2026-11-13; the owner's tool ideas, Fable's plan)

A helper told to "get the gate green" takes the shortest road: run it again until it passes, skip the test, or call
the failure noise. The owner can't read a failure log to judge. So when the gate fails, the kit sorts each failure
itself, with plain rules and no AI, and the upload stays stopped:

  REAL       it failed every time it was run again: something is broken. Fix the code, not the test.
  UNSTEADY   it failed on some runs and passed on others, on the same code. Treated as real until shown otherwise.
  MACHINE    the tests didn't properly run (no report, or a report with no tests): nothing was tested.
  PARKED     an unsteady test the owner parked: it still runs and is shown, but doesn't stop the upload.

Fail-then-pass is not a pass: a test that failed on this exact code and passes when the gate is run again is
UNSTEADY, and the upload stops, unless the owner has parked that test.

Parking is the owner's, in foundationguard.json (a guard file, so a helper's change asks the owner):
  "parked": [{"test": "test_path_timing", "since": "2026-11-13", "until": "2026-11-20", "why": "fails 1 run in 4"}]
At most 3 parked at once, each for at most 7 days from "since", and renewed at most once: the kit remembers each parking
it used, so a test parked twice in the last 30 days can't be parked a third time (fix it instead). A test the approved
list names, or one matching "never_park" (for example ["*determinism*", "*save*"]), is never parked.

  python fg/alarms.py      what the last failing gate run found, and what is parked
Needs the gate's test report (test_log) and check_command (to run one failed test again). Gates made of steps
(gate_steps) are sorted by step, not yet by test.
"""
import datetime, fnmatch, json, os, re, subprocess, sys, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import proofstore as PS

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "alarms"
TRIES = 3
CAP = 3
DAYS = 7
RENEWALS = 1
MACHINE_WORDS = "the tests didn't properly run (no test report, or a report with no tests in it): nothing was tested"


def outcomes(log):
    """{test: True passed / False failed} from the gate's report; skipped tests are left out. None: no report."""
    if not log or not os.path.exists(log):
        return None
    txt = open(log, encoding="utf-8", errors="replace").read()
    if not txt.lstrip().startswith("<"):
        return {m.group(2): m.group(1) == "PASS" for m in re.finditer(r"^(PASS|FAIL)\s+(\S+)", txt, re.M)}
    try:
        tree = ET.fromstring(txt)
    except ET.ParseError:
        return None
    out = {}
    for tc in tree.iter("testcase"):
        kids = {ch.tag for ch in tc}
        if "skipped" not in kids and tc.get("name"):
            out[tc.get("name")] = out.get(tc.get("name"), True) and not ({"failure", "error"} & kids)
    for tc in tree.iter("test-case"):                  # NUnit (Unity)
        if tc.get("name") and tc.get("result") in ("Passed", "Failed"):
            out[tc.get("name")] = tc.get("result") == "Passed"
    return out


def _approved_checks(cfg):
    import approved as A
    return {r["check"] for r in A.rows(cfg)} if cfg.get("approved_file") else set()


def parked(cfg, today=None):
    """{test: (until, why)} for the parkings that hold today; [(test, problem)] for the ones that don't."""
    today = today or datetime.date.today()
    never = list(cfg.get("never_park") or []) + sorted(_approved_checks(cfg))
    used = _used_parkings(cfg)
    ok, bad = {}, []
    for i, e in enumerate(cfg.get("parked") or []):
        t = str((e or {}).get("test", ""))
        why = _parking_problem(e, t, i, never, today) or _renewed_too_often(e, used.get(t, set()))
        if why:
            bad.append((t, why))
        else:
            ok[t] = (e["until"], e.get("why", ""), str(e.get("since")))
    return ok, bad


def _used_parkings(cfg):
    """{test: {since}} for the parkings the gate has used (the kit's record, not the owner's file)."""
    out = {}
    for r in PS.read(cfg, BOOK):
        if r.get("parking") and not r.get("_bad"):
            out.setdefault(r["parking"], set()).add(str(r.get("since")))
    return out


def _renewed_too_often(e, earlier):
    """A parking may be renewed once: a third parking of the same test within 30 days doesn't hold."""
    try:
        since = datetime.date.fromisoformat(str(e.get("since")))
    except ValueError:
        return None
    recent = {d for d in earlier if d != str(since) and _days_before(d, since) <= 30}
    if len(recent) > RENEWALS and not BREAK("alarms_renewal"):
        return f"it was parked {len(recent)} times already in the last 30 days (one renewal is allowed): fix it instead"
    return None


def _days_before(d, since):
    try:
        return (since - datetime.date.fromisoformat(d)).days
    except ValueError:
        return 999


def _parking_problem(e, t, i, never, today):
    if i >= CAP and not BREAK("alarms_cap"):
        return f"only {CAP} tests can be parked at once"
    if any(fnmatch.fnmatch(t, n) for n in never) and not BREAK("alarms_never_park"):
        return "this test can never be parked (the approved list names it, or never_park does)"
    try:
        since = datetime.date.fromisoformat(str(e.get("since")))
        until = datetime.date.fromisoformat(str(e.get("until")))
    except ValueError:
        return "it needs since and until dates (YYYY-MM-DD)"
    if (until - since).days > DAYS:
        return f"a parking lasts at most {DAYS} days"
    if until < today and not BREAK("alarms_expiry"):
        return f"it ran out on {until}"
    return None


def _again(cfg, test):
    """Run one failed test again TRIES times: [passed?]."""
    cmd = cfg.get("check_command")
    if not cmd or BREAK("alarms_rerun"):
        return []
    return [_once(cfg, cmd.replace("{check}", test)) for _ in range(TRIES)]


def _once(cfg, cmd):
    limit = float(cfg.get("check_timeout_s", 1800))
    try:
        return subprocess.run(cmd, shell=True, cwd=cfg["_root"], capture_output=True, timeout=limit).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _seen_before(cfg, test, tree):
    return any(test in (r.get("failed") or []) for r in PS.read(cfg, BOOK) if not r.get("_bad") and r.get("tree") != tree)


def _sort_failed(cfg, res, tree, park, refused=None):
    rows = []
    for t in sorted(n for n, ok in res.items() if not ok):
        tries = _again(cfg, t)
        new = "" if _seen_before(cfg, t, tree) else " First time seen: likely from this change."
        held = f" Not parked: {refused[t]}." if t in (refused or {}) else ""
        new += held
        if t in park:
            rows.append(("PARKED", t, f"failed; parked by the owner until {park[t][0]} ({park[t][1]})"))
        elif tries and any(tries):
            rows.append(("UNSTEADY", t, f"failed, then passed {sum(tries)} of {len(tries)} runs again on the same code.{new}"))
        else:
            again = f"failed {len(tries) + 1} of {len(tries) + 1} runs" if tries else "failed (it can't be run alone: no check_command)"
            rows.append(("REAL", t, f"{again}. Something is broken: fix the code, not the test.{held}"))
    return rows


def _flipped(cfg, res, tree):
    """Tests that failed on this exact code before and pass now (fail-then-pass)."""
    if BREAK("alarms_memory"):
        return []
    before = set()
    for r in PS.read(cfg, BOOK):
        if not r.get("_bad") and r.get("tree") == tree:
            before |= set(r.get("failed") or [])
    return sorted(t for t in before if res.get(t))


def _applies(cfg):
    return C.part(cfg, "alarms") != "off" and not cfg.get("gate_steps") and bool(cfg.get("test_log"))


def _rows(cfg, bad, res, tree):
    """The sorted failures of this run, and the tests that passed now after failing on this same code."""
    park, refused = parked(cfg)
    rows = _sort_failed(cfg, res, tree, park, dict(refused)) if bad else []
    flip = "failed on this exact code earlier, and passes now: fail-then-pass is not a pass"
    return rows + [("UNSTEADY", t, flip) for t in _flipped(cfg, res, tree) if t not in park]


def judge(cfg, bad, cards):
    """Called by the gate with its problem (or None). Returns the problem as the gate should report it, or None when
    every failure is a parked test. Adds a card for the owner."""
    if not _applies(cfg):
        return bad
    res = outcomes(os.path.join(cfg["_root"], cfg["test_log"]))
    tree = PS.code_now(cfg["_root"])[1]
    if bad and not res and not BREAK("alarms_machine"):
        return _stop(cards, [("MACHINE", "", MACHINE_WORDS)], bad)
    rows = _rows(cfg, bad, res or {}, tree)
    if bad:
        PS.append(cfg, BOOK, {"tree": tree, "failed": sorted(n for n, ok in (res or {}).items() if not ok)})
    _remember_parkings(cfg, rows)
    return _decide(cfg, cards, rows, bad)


def _remember_parkings(cfg, rows):
    park, _ = parked(cfg)
    for t in sorted({t for l, t, _ in rows if l == "PARKED"}):
        PS.append(cfg, BOOK, {"parking": t, "since": park[t][2]})


def _decide(cfg, cards, rows, bad):
    if not rows:
        return bad
    all_parked = all(l == "PARKED" for l, _, _ in rows)
    if not (all_parked or C.part(cfg, "alarms") == "warn"):
        return _stop(cards, rows, bad)
    cards.append(_card(rows, stopped=False))
    return None if all_parked else bad


def _stop(cards, rows, bad):
    cards.append(_card(rows, stopped=True))
    text = "\n".join(f"  {l:<9} {t}{': ' if t else ''}{w}" for l, t, w in rows)
    return (bad + "\n" if bad else "") + "WHAT KIND OF RED (fg/alarms.py):\n" + text


def _card(rows, stopped):
    labels = sorted({l for l, _, _ in rows})
    return {"who": "you", "title": "The gate's failures, sorted: " + ", ".join(labels),
            "happened": "; ".join(f"{l} {t}".strip() for l, t, _ in rows[:6]) + ".",
            "means": ("REAL: something is broken. UNSTEADY: it passes some runs and fails others on the same code, "
                      "treated as real. MACHINE: nothing was tested. PARKED: you parked it, so it doesn't stop uploads."),
            "action": ("Not uploaded. Ask your helper to fix what is REAL or UNSTEADY; never to run it again until it "
                       "passes. Only you can park a test (parked in foundationguard.json, at most 3, 7 days each, renewed once)."
                       if stopped else "Uploaded: every failure is a test you parked."),
            "evidence": [t for _, t, _ in rows if t]}


def main(argv):
    cfg = C.load()
    ok, bad = parked(cfg)
    for t, (until, why, _) in ok.items():
        print(f"  PARKED    {t} until {until}: {why}")
    for t, why in bad:
        print(f"  NOT PARKED {t}: {why}")
    last = [r for r in PS.read(cfg, BOOK) if not r.get("_bad") and "failed" in r][-1:]
    print("FG-ALARMS: last failing run: " + (", ".join(last[0].get("failed") or []) or "nothing named") if last
          else "FG-ALARMS: no failing gate run on record.")
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

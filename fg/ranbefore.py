"""FoundationGuard: tests that passed before must run again (AI-made, Claude, 2026-11-13; outside review 8, Grok).

Grok (round 8) changed what the gate runs instead of the tests: a new pytest.ini that skipped the test folder, and the gate
then passed with no test run. Guarding the runner's settings (F299) closes that way in; this closes the rest. At every
pass the kit records which tests passed. At the next upload, any test that passed last time and didn't pass this time
(gone, skipped or not collected) stops the upload until the owner says yes, the same yes as a changed guard (fg/ownerok.py).

The record is kept per commit, and an upload is compared with the newest recorded pass on its own line of work, so moving
between branches doesn't look like lost tests.

  python fg/ranbefore.py     list the tests that passed at the last recorded pass and didn't pass in the last gate run
"""
import hashlib, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
NAME = "ran_tests.json"
ITEM = "(tests that stopped running)"
KEEP = 20


def path(cfg):
    return os.path.join(cfg["_root"], (cfg.get("state_dir") or ".foundationguard").strip("/"), NAME)


def _load(cfg):
    try:
        d = json.load(open(path(cfg), encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(cfg, d):
    os.makedirs(os.path.dirname(path(cfg)), exist_ok=True)
    with open(path(cfg), "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    import steps as SP
    SP.recorded(cfg, [path(cfg)])


def now_passed(cfg):
    """The names of the tests that passed in this gate run, or None when the gate writes no test report."""
    if cfg.get("gate_steps"):
        got = cfg.get("_got")
    elif cfg.get("test_log"):
        import approved as A
        got = A.results(os.path.join(cfg["_root"], cfg["test_log"]))
    else:
        return None
    return None if got is None else sorted(k for k, v in got.items() if v and k)


def _head(root):
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip()


def _ancestor(root, a, b):
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=root, capture_output=True).returncode == 0


def _before(cfg, d):
    """The tests that passed at the newest recorded pass on this commit's line of work, or None."""
    root, h = cfg["_root"], _head(cfg["_root"])
    for e in reversed(d.get("passes") or []):
        if e.get("commit") and (e["commit"] == h or _ancestor(root, e["commit"], h)):
            return set(e.get("tests") or [])
    return None


def _shown(names):
    """Long names first ('file.test'), and a short name only when no long one ends with it."""
    longs = [n for n in names if "." in n or "::" in n]
    return sorted(longs) + sorted(n for n in names if n not in longs and not any(l.endswith("." + n) for l in longs))


def note(cfg):
    """Called by the gate after the tests passed: write down the tests that passed before and not now."""
    now = now_passed(cfg)
    if now is None:
        return []
    d = _load(cfg)
    before = _before(cfg, d)
    gone = [] if before is None or BREAK("gate_tests_gone") else _shown(before - set(now))
    if gone != (d.get("gone") or []):
        d["gone"] = gone
        _write(cfg, d)
    return gone


def items(cfg):
    """[(name, why, version)] for fg/ownerok.py: the tests that stopped running, as one item the owner says yes to."""
    gone = _load(cfg).get("gone") or []
    if not gone or C.part(cfg, "tests_gone") != "on":
        return []
    why = "%d test(s) that passed last time didn't pass this time (gone, skipped or not run): %s%s" % (
        len(gone), ", ".join(gone[:6]), " and more" if len(gone) > 6 else "")
    return [(ITEM, why, hashlib.sha1("\n".join(gone).encode()).hexdigest()[:16])]


def cards(cfg):
    """With tests_gone on "warn": the tests that stopped running, named in the summary without stopping the upload."""
    gone = _load(cfg).get("gone") or []
    if not gone or C.part(cfg, "tests_gone") != "warn":
        return []
    return [{"who": "you", "title": "Tests that passed before didn't run this time (warn only)",
             "happened": ", ".join(gone[:6]) + (" and more" if len(gone) > 6 else "") + ".",
             "means": "These tests passed at the last upload and didn't pass now: gone, skipped or no longer found.",
             "action": "Uploaded (tests_gone is on warn). Ask your helper why they stopped running.", "evidence": gone}]


def save(cfg):
    """Called by the gate at a pass: this commit's passing tests become the record."""
    now = now_passed(cfg)
    if now is None:
        return
    d = _load(cfg)
    h = _head(cfg["_root"])
    passes = [e for e in d.get("passes") or [] if e.get("commit") != h] + [{"commit": h, "tests": now}]
    _write(cfg, {"passes": passes[-KEEP:], "gone": []})


def main(argv):
    cfg = C.load()
    gone = _load(cfg).get("gone") or []
    for n in gone:
        print("  STOPPED RUNNING  " + n)
    print("FG-TESTS: %d test(s) that passed at the last recorded pass didn't pass in the last gate run." % len(gone))
    return 1 if gone else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

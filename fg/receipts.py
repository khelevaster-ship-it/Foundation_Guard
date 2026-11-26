"""FoundationGuard receipts: no receipt, no green (AI-made, Claude, 2026-11-13; the owner's tool ideas, Fable's plan).

The owner had three false greens: a pass from an older commit, a crashed run that reported a pass, and a nightly job
that never ran. Each came from a board that showed a claim, not proof. Now every run of a check leaves a receipt in the
kit's proof store (fg/proofstore.py): "started" before it runs, "finished" after, with the exact code it ran on, how it
ended, and where it ran. The status is worked out from the receipts against the code as it is now, in the one word list
(PROVEN is the only green):

  PROVEN, PASSED, NOT APPROVED, PASSED ON A RETRY, OUT OF DATE, FAILED, DID NOT FINISH, RUNNING, NEVER RAN, OVERDUE, CLAIMED ONLY

The checks it expects are listed in foundationguard.json (a guard file):
  "expected_checks": [{"name": "replay", "command": "python tools/replay.py", "every_hours": 24,
                       "evidence": "ran \\\\d+ worlds"}]
evidence (optional) is a line the output must hold, so a run that ends "OK" but did nothing is not a pass.
limit_minutes (optional; else check_timeout_s) is how long one run may take: a run past it is ended, with every
program it started, and its receipt says so. A stuck night job can't hold the night. The gate is
always on the list as "gate": every run of python fg/push.py leaves its receipt.

  python fg/receipts.py run NAME     run one expected check through the receipt runner
  python fg/receipts.py              the status of every expected check, in plain words; also written to
                                     .foundationguard/status.json for a status board
  python fg/receipts.py show ID      one receipt: what ran, on which code, how it ended
A helper that says "done" or "green" quotes the receipt ID; anyone can look it up with show.
This only informs: it blocks nothing (the gate already blocks a failed check).
"""
import json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import proofstore as PS

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "receipts"
GATE = "gate"
CHANGED_SINCE = "passed on this commit, but files in the folder have changed since that run and aren't committed (receipt {})"


def expected(cfg):
    out = [{"name": GATE, "command": "(python fg/push.py)"}]
    for e in cfg.get("expected_checks") or []:
        if isinstance(e, dict) and e.get("name") and e.get("command") and e["name"] != GATE:
            out.append(e)
    return out


def started(cfg, name):
    """Write "started" for one run; returns its receipt ID."""
    commit, tree, dirty = PS.code_now(cfg["_root"])
    rid = "R" + os.urandom(3).hex().upper()
    rec = {"id": rid, "check": name, "event": "started", "commit": commit, "tree": tree, "dirty": dirty}
    rec.update(where=PS.where(), work=_work(cfg))
    if not BREAK("receipt_started") and C.part(cfg, "receipts") != "off":
        PS.append(cfg, BOOK, rec)
    return rid


def finished(cfg, rid, name, ok, detail=""):
    if C.part(cfg, "receipts") == "off":
        return
    rec = {"id": rid, "check": name, "event": "finished", "ok": bool(ok), "detail": detail[:300]}
    rec["work"] = _work(cfg)                     # the folder as the run left it: a change after this is newer code
    PS.append(cfg, BOOK, rec)


def _work(cfg):
    return PS.work_now(cfg["_root"], cfg.get("state_dir") or ".foundationguard")


def now(cfg):
    """(commit, tree, dirty, work) for the code as it is now, changes not committed included."""
    return PS.code_now(cfg["_root"]) + (_work(cfg),)


def run(cfg, name):
    e = next((x for x in expected(cfg) if x["name"] == name and x["name"] != GATE), None)
    if not e:
        print(f"FG-RECEIPT: '{name}' is not on the list of expected checks (expected_checks in foundationguard.json). "
              "Only listed checks run here, with their listed command."); return 2
    rid = started(cfg, name)
    t0 = time.time()
    code, out = _run_limited(e["command"], cfg["_root"], limit(cfg, e))
    ok, why = code == 0, f"exit {code}"
    if code is None:
        ok, why = False, f"stopped: it ran past its time limit of {_ago(limit(cfg, e))}, so the kit ended it"
    if ok and e.get("evidence") and not re.search(e["evidence"], out) and not BREAK("receipt_evidence"):
        ok, why = False, "it ended OK but its output lacks the line that shows it really ran (" + e["evidence"] + ")"
    finished(cfg, rid, name, ok, f"{why}; {round(time.time() - t0)} s")
    sys.stdout.write(out[-3000:])
    print(f"FG-RECEIPT {rid}: {name} {'PASSED' if ok else 'FAILED'} ({why}).")
    return 0 if ok else 1


def limit(cfg, e):
    """How long one run of a check may take, in seconds: limit_minutes on the check, else check_timeout_s."""
    m = e.get("limit_minutes")
    return float(m) * 60 if m else float(cfg.get("check_timeout_s", 1800))


def _run_limited(cmd, root, seconds):
    """(exit code, or None when it ran past its limit and was ended with everything it started; output)."""
    win = os.name == "nt"
    p = subprocess.Popen(cmd, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                         start_new_session=not win)
    try:
        out = p.communicate(timeout=None if BREAK("receipt_limit") else seconds)[0]
        return p.returncode, out
    except subprocess.TimeoutExpired:
        _end(p, win)
        return None, (p.communicate()[0] or "")


def _end(p, win):
    """End a run and every program it started (a stuck job must die, children too)."""
    if win:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        return
    import signal
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        p.kill()


def _runs(cfg):
    """{receipt ID: run} joining each run's started and finished lines."""
    runs = {}
    for r in PS.read(cfg, BOOK):
        rid = r.get("id")
        if not rid:
            continue
        run_ = runs.setdefault(rid, {"id": rid, "check": r.get("check"), "bad": ""})
        run_.update({k: v for k, v in r.items() if k not in ("event", "prev", "stamp", "_bad")})
        run_["bad"] = run_["bad"] or r.get("_bad", "")
        run_["started" if r.get("event") == "started" else "finished"] = r.get("at")
    return runs


def _trusted(run_):
    return not run_["bad"] and run_.get("where") in ("pc", "ci")


def state(cfg, e, runs, now_code, now_t=None):
    """(word, plain words) for one expected check."""
    now_t = now_t or time.time()
    commit, tree, dirty = now_code[:3]
    work = _work_of(now_code)
    mine = sorted((r for r in runs.values() if r.get("check") == e["name"] and r.get("started")), key=lambda r: r["started"])
    if not mine:
        return "NEVER RAN", PS.WORDS["NEVER RAN"]
    last = mine[-1]
    if "finished" not in last:
        if now_t - last["started"] < limit(cfg, e):
            return "RUNNING", f"started {_ago(now_t - last['started'])} ago (receipt {last['id']})"
        return "DID NOT FINISH", f"started {_ago(now_t - last['started'])} ago and never ended (receipt {last['id']})"
    here = [r for r in mine if "finished" in r and _same_code(r, tree, work)]
    word, words = _on_this_code(cfg, here, mine, dirty)
    every = e.get("every_hours")
    if every and now_t - last["finished"] > float(every) * 3600 and not BREAK("receipt_overdue") and word != "FAILED":
        return "OVERDUE", f"should run every {every} h; the last run ended {_ago(now_t - last['finished'])} ago ({words})"
    return word, words


def _work_of(now_code):
    """The uncommitted-changes fingerprint in a (commit, tree, dirty[, work]); unknown when dirty and not given."""
    if len(now_code) > 3:
        return now_code[3]
    return None if now_code[2] else ""


def _same_code(r, tree, work=""):
    """Ran on exactly these files: the same commit's files and the same changes not yet committed."""
    if BREAK("receipt_tree"):
        return True
    then = r.get("work", "" if not r.get("dirty") else "?")
    return r.get("tree") == tree and (then == work or BREAK("receipt_work"))


def _older_code(cfg, mine, dirty):
    """No finished run on this code: what the older runs say."""
    done = [r for r in mine if "finished" in r and r.get("ok") and _trusted(r)]
    if not done and any(r.get("ok") for r in mine):
        return "CLAIMED ONLY", "only passes the kit can't trust (a cloud session's, or written by hand), on older code"
    if not done:
        return ("FAILED" if mine[-1].get("ok") is False and not dirty else "NEVER RAN"), _last(mine[-1])
    last = done[-1]
    behind = PS.git(cfg["_root"], "rev-list", "--count", last.get("commit", "") + "..HEAD") or "?"
    if behind == "0":
        return "OUT OF DATE", CHANGED_SINCE.format(last["id"])
    also = "; there are also changes not yet committed" if dirty else ""
    return "OUT OF DATE", f"passed on {str(last.get('commit'))[:9]}, {behind} commit(s) ago{also} (receipt {last['id']})"


def _untrusted(here):
    r = next(r for r in here if not _trusted(r))
    why = r["bad"] or f"it ran in a {r.get('where')} session"
    return "CLAIMED ONLY", f"receipt {r['id']}: {why}; run it again on this computer to prove it"


def _on_this_code(cfg, here, mine, dirty):
    if not here:
        return _older_code(cfg, mine, dirty)
    if not all(_trusted(r) for r in here) and not BREAK("receipt_where"):
        return _untrusted(here)
    oks = [bool(r.get("ok")) for r in here]
    last = here[-1]
    if not oks[-1]:
        return "FAILED", _last(last)
    if all(oks) or BREAK("receipt_retry"):
        ago = _ago(time.time() - last["finished"])
        waits = _unapproved(cfg)
        if waits and not BREAK("receipt_unapproved"):         # Plan 2 PR 7: a pass on a weaker check isn't plain PROVEN
            return "PASSED, NOT APPROVED", (f"passed on this exact code (receipt {last['id']}, {ago} ago), but it holds "
                                            f"{len(waits)} safety-check change(s) the owner hasn't said yes to: " +
                                            ", ".join(waits[:3]) + (" and more" if len(waits) > 3 else ""))
        return "PROVEN", f"passed on this exact code (receipt {last['id']}, {ago} ago)"
    return "PASSED ON A RETRY", f"failed {oks.count(False)} time(s), then passed, on this same code (receipt {last['id']})"


def _unapproved(cfg):
    try:
        import ownerok as OK
        return [f for f, _, _ in OK.missing(cfg)]
    except Exception:                                    # noqa: BLE001  can't tell: the word says what it can
        return []


def _last(r):
    return f"receipt {r['id']}: {'passed' if r.get('ok') else 'failed'} ({r.get('detail', '')})"


def _ago(s):
    s = max(0, int(s))
    return f"{s // 3600} h {s % 3600 // 60} min" if s >= 3600 else f"{s // 60} min" if s >= 60 else f"{s} s"


def status(cfg):
    """[(check, word, plain words)], also written to .foundationguard/status.json with its own time."""
    runs = _runs(cfg)
    now_code = now(cfg)
    rows = [(e["name"],) + state(cfg, e, runs, now_code) for e in expected(cfg)]
    sd = os.path.join(cfg["_root"], cfg.get("state_dir") or ".foundationguard")
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, "status.json"), "w", encoding="utf-8") as f:
        json.dump({"worked_out_at": time.time(), "commit": now_code[0], "words": PS.WORDS,
                   "checks": [{"check": c, "state": w, "green": w in PS.GREEN, "why": why} for c, w, why in rows]}, f, indent=1)
    return rows


def show(cfg, rid):
    r = _runs(cfg).get(rid)
    if not r:
        print(f"FG-RECEIPT: no receipt {rid}."); return 1
    for k in ("id", "check", "commit", "tree", "dirty", "where", "ok", "detail", "bad"):
        print(f"  {k}: {r.get(k)}")
    return 0


def main(argv):
    cfg = C.load()
    if argv[:1] == ["run"] and len(argv) > 1:
        return run(cfg, argv[1])
    if argv[:1] == ["show"] and len(argv) > 1:
        return show(cfg, argv[1])
    rows = status(cfg)
    for c, w, why in rows:
        print(f"  {w:<18} {c}: {why}")
    print("FG-RECEIPTS: only PROVEN is green. Worked out just now, on " + (PS.code_now(cfg["_root"])[0][:9] or "no commit") + ".")
    return 0 if all(w in PS.GREEN for _, w, _ in rows) else 1


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

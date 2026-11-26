"""FoundationGuard review lane (AI-made, Claude, 2026-11-16; the owner's yes to the fewer-boxes proposal, 16 Nov 22:36 UTC).

The owner, 16 Nov: "i have no idea for the most part what i am oking or not" (82 boxes in a day). With "review_lane": true
in foundationguard.json, a helper's technical change to one of the project's own guard files (its tests, check
scripts, decision docs) no longer opens a box. It is listed for the upload, and a second reviewer reads it instead of
the owner:

  python fg/review.py           ask the reviewer about every change in this upload that waits for a yes
  python fg/review.py --list    what the reviewer said, newest last

The reviewer is the owner's own program, named in foundationguard.json as "review_command" (a list, for example
["python", "Tools/Scripts/api_ask.py", "--review"]). It gets one change as JSON on its input ({"file", "why", "diff",
"helper_reason"}) and answers on the first line of its output with PASS, WEAKER or WRONG, a colon and one plain
sentence. A PASS stands in for the owner's yes for that exact version of the file. WEAKER or WRONG keeps the owner's yes
needed, and the box shows the reviewer's sentence. A later PASS never clears an earlier WEAKER or WRONG on the same
version, so asking again until it passes doesn't work.

These always stay the owner's, reviewer or not: the kit's own code and settings, files the owner lists in
"owner_only" (for the game: the build order, approved rows, spending, logins), a change the kit itself judges weaker
(a test taken out, a limit loosened), a file changed and committed in one step without a yes, and tests that stopped
running. Every verdict is a stamped line in the proof book (.git/foundationguard/proof/review.jsonl).
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "review"
VERDICTS = ("PASS", "WEAKER", "WRONG")


def on(cfg):
    return bool(cfg.get("review_lane")) and not BREAK("review_lane_off")


def owner_only(cfg, f):
    """True when this file stays the owner's call, whatever the reviewer says."""
    import adds as AD, paths as P
    return not AD.owners_own(cfg, f) or P.matches(f, list(cfg.get("owner_only") or []))


def eligible(cfg, f, why):
    """A change the reviewer may take instead of the owner."""
    import ownerok as OK, ranbefore as RB
    if f == RB.ITEM or owner_only(cfg, f):
        return False
    return not str(why).startswith((OK.LESS, OK.KIT_MAYBE, OK.HELD))


def _verdicts(cfg):
    import proofstore as PS
    return [r for r in PS.read(cfg, BOOK) if not r.get("_bad") and r.get("verdict") in VERDICTS]


def standing(cfg):
    """{(file, version): (verdict, words)}: a WEAKER or WRONG on a version stands over any later PASS."""
    out = {}
    for r in _verdicts(cfg):
        k = (r.get("path"), r.get("version"))
        if out.get(k, ("PASS",))[0] == "PASS":
            out[k] = (r["verdict"], r.get("words", ""))
    return out


def passed(cfg, todo):
    """The items of todo [(file, why, version)] a reviewer's PASS covers."""
    if not on(cfg):
        return set()
    st = standing(cfg)
    return {f for f, why, v in todo if eligible(cfg, f, why) and st.get((f, v), ("",))[0] == "PASS"}


def words_for(cfg, f, v):
    """The reviewer's sentence on a version it flagged, for the owner's box ('' when none)."""
    if not on(cfg):
        return ""
    verdict, words = standing(cfg).get((f, v), ("", ""))
    return f"The reviewer says {verdict}: {words}" if verdict in ("WEAKER", "WRONG") else ""


def parse(out):
    """(verdict, one sentence) from the reviewer's first line; anything else is WRONG (it couldn't say)."""
    first = (out or "").strip().split("\n")[0].strip()
    head, _, words = first.partition(":")
    head = head.strip().upper()
    if head in VERDICTS and words.strip():
        return head, words.strip()[:300]
    return "WRONG", "the reviewer gave no clear answer (" + (first[:120] or "nothing") + ")"


def ask(cfg, f, why, v, rng):
    """Run the owner's reviewer on one change and record its verdict."""
    import ownerok as OK, proofstore as PS
    root = cfg["_root"]
    cmd = cfg.get("review_command")
    if not isinstance(cmd, list) or not cmd:
        return None
    diff = OK._git(root, "diff", rng, "--", f).stdout if rng else ""
    data = json.dumps({"file": f, "why": why, "diff": diff[:200000],
                       "helper_reason": OK._helper_words(root, rng, f)})
    try:
        p = subprocess.run(cmd, cwd=root, input=data, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=float(cfg.get("review_timeout_s", 600)))
        verdict, words = parse(p.stdout) if p.returncode == 0 else ("WRONG", f"the reviewer failed (exit {p.returncode})")
    except (OSError, subprocess.TimeoutExpired) as e:
        verdict, words = "WRONG", "the reviewer couldn't run (" + type(e).__name__ + ")"
    if BREAK("review_sticks") and verdict != "PASS":
        return verdict, words
    PS.append(cfg, BOOK, {"path": f, "version": v, "verdict": verdict, "words": words, "cmd": " ".join(map(str, cmd))[:300]})
    return verdict, words


def run(cfg):
    import ownerok as OK
    if not on(cfg):
        print("FoundationGuard: the review lane is off (\"review_lane\": true in foundationguard.json turns it on).")
        return 1
    rng = OK.upload_range(cfg)
    todo = [x for x in OK.missing(cfg) if eligible(cfg, x[0], x[1])]
    st = standing(cfg)
    flagged = 0
    for f, why, v in todo:
        got = st.get((f, v)) or ask(cfg, f, why, v, rng)
        if got is None:
            print("FoundationGuard: no \"review_command\" in foundationguard.json, so nothing was reviewed."); return 1
        flagged += got[0] != "PASS"
        print(f"  {got[0]}  {f}: {got[1]}")
    rest = [x for x in OK.missing(cfg) if x[0] not in passed(cfg, [x])]
    print(f"FoundationGuard: {len(todo)} change(s) reviewed, {flagged} flagged; {len(rest)} still need the owner's yes.")
    return 0


def main(argv):
    import config as C
    cfg = C.load()
    if "--list" in argv:
        for r in _verdicts(cfg):
            print(f"  {r['verdict']}  {r.get('path')} ({str(r.get('version'))[:9]}): {r.get('words', '')}")
        return 0
    return run(cfg)


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

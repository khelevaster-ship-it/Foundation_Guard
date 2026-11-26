"""FoundationGuard away mode: keep working while the owner is away, and ask once when they're back (AI-made, Claude,
2026-11-13; the owner: "I'd like to do that", round 9's point that too many boxes wear people down).

A box no one answers stops the helper until the owner is back. With away mode on, changes to the owner's own guard
files (tests, check scripts, their lists) don't stop the helper with a box each: they go through, each one is written
down, and the upload waits until the owner has looked at them all at one sitting. Nothing unapproved is uploaded. The
kit itself, its settings and hooks, deletes, other pushes and installs still ask at once (AGENT_SETUP.md, section 15).
This is the gather_asks setting, with a name and a switch. The switch is a stamped line in the git folder
(.git/foundationguard/proof/away.jsonl), so it leaves no change in the project (16 Nov).

  python fg/away.py           is away mode on, and how many changes wait for the owner's yes
  python fg/away.py on        switch it on (the kit's box asks the owner: do it before leaving)
  python fg/away.py off       switch it off when back for good (the box asks too)
When the owner is back, each new session starts by saying how many changes wait (fg/ready.py); python fg/ownerok.py
lists them in plain words, and python fg/ownerok.py --give is the one yes.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


# The owner, 13 Nov: "is there a way for it to prompt your agent to explain all the changes?" The kit's own list
# (python fg/ownerok.py) is the facts; the helper's explanation must cover every item on it, so nothing is skipped.
HELPER_EXPLAINS = ("Helper: before any other work, run python fg/ownerok.py and explain to the owner, in plain words, "
                   "EVERY change it lists, one by one: what changed, why it was needed, and whether any test or check "
                   "now catches less (the kit marks those CATCHES LESS, or MAY CATCH LESS when it can't tell; say each one plainly). Don't leave any out, and don't give the yes yourself.")


def on(cfg):
    return bool(cfg.get("gather_asks"))


def waiting(cfg):
    """The changes that wait for the owner's one yes before the upload."""
    import ownerok as OK
    try:
        return OK.missing(cfg)
    except Exception:
        return []


def back_words(cfg):
    """What a session says first when away mode is on: how many changes wait for the owner's one yes."""
    if not on(cfg) or BREAK("away_back"):
        return ""
    n = len(waiting(cfg))
    head = "Away mode is on: changes to your tests and lists go through and wait for your one yes at the upload. "
    if not n:
        return head + "Nothing waits for your yes right now."
    return head + (f"{n} change(s) made while you were away wait for your yes before anything is uploaded. "
                   + HELPER_EXPLAINS + " python fg/ownerok.py --give is the owner's one yes, given only after that. "
                   "When the owner is back for good, they say \"switch away mode off\".")


NOW_ON = "ON. Changes to your tests and lists wait for your one yes at the upload."
NOW_OFF = "OFF. Each change to a guard asks you at once again."


def _box_yes(cfg):
    try:
        import steps as SP
        p = os.path.join(cfg["_root"], "foundationguard.json")
        return any(y.covers(p) for y in SP.step_yeses(cfg))
    except Exception:
        return False


def switch(cfg, want):
    """The owner's switch, in their own terminal: a stamped line in the git folder (fg/config.py away_local), never a
    change to the project's files (the game's PC, 16 Nov: the switched foundationguard.json made the push refuse). Off
    also takes an old "gather_asks": true out of foundationguard.json, through the owner's door."""
    import door as D
    import proofstore as PS
    term = D.terminal() or BREAK("door_tty")
    what = ("switch away mode ON: changes to your tests and lists go through without a box each, and the upload waits "
            "for your one yes" if want else "switch away mode OFF")
    boxed = not term and _box_yes(cfg)                # a helper's run the owner said yes to in the kit's box
    if not term and not boxed and not BREAK("away_no_terminal"):
        print("FG-AWAY: only the owner switches away mode: in their own terminal (PowerShell or the Command Prompt), "
              "or with their yes in the kit's box when a helper runs this. Nothing changed."); return 1
    if term and not D.owner_here(what, tightening=not want):          # the owner in their own terminal (fg/door.py)
        print("FG-AWAY: no yes, so nothing changed."); return 1
    PS.append(cfg, "away", {"on": bool(want), "at": time.time(), "shown": what[:200]})
    p = os.path.join(cfg["_root"], "foundationguard.json")
    if not want and os.path.exists(p):
        data = json.load(open(p, encoding="utf-8-sig"))
        if data.get("gather_asks"):                   # the old way of switching it on: taken out once
            data["gather_asks"] = False
            text = json.dumps(data, indent=2).encode("utf-8")
            if os.name == "nt":
                text = text.replace(b"\n", b"\r\n")
            D.write(cfg, p, text, what, line=not BREAK("door_away"))
    print("FG-AWAY: away mode is now " + (NOW_ON if want else NOW_OFF))
    return 0


def main(argv):
    cfg = C.load()
    if argv[:1] in (["on"], ["off"]):
        return switch(cfg, argv[0] == "on")
    print(back_words(cfg) or "FG-AWAY: away mode is off: each change to a guard asks you at once.")
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

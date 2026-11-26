"""FoundationGuard catch log (AI-made, Claude, 2026-11-09).
Every time the guard blocks a command, asks the owner, or the gate stops a push, one dated line goes into
.foundationguard/catches.log. A short list of real catches on a real project is the best evidence the guard works.
  python fg/catches.py              print the log (newest last)
  python fg/catches.py --md         print it as a table for a report or a grant appendix
  python fg/catches.py --today [--json]  how many times the kit asked the owner today against the daily budget
                                    ("ask_budget", default 5), and over it, the rules that asked most
  python fg/catches.py --asks [N]   the last N times the kit asked the owner or blocked (default 20): when, which
                                    rule, the tool and its file or command, and the box's whole text. The helper
                                    can't see the box the owner sees; it reads this instead (the game's PC, 12 Nov).
Commands that look like they hold a secret are not written down. The log stays on this computer (it is not pushed).
An ask about a file in another copy of the project is written in that copy's log and in this one's."""
import datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


WHOLE = os.environ.get("FG_BREAK", "") != "asks_written_whole"
BREAK_COUNT = os.environ.get("FG_BREAK", "") == "ask_budget_count"


def log(cfg, kind, why, cmd="", rule=""):
    """One line: when (with seconds and the clock's offset from UTC), what happened, why (an ask's whole box text),
    the tool and its file or command, and which rule."""
    if os.environ.get("FG_BREAK", "") == "catch_log":
        return
    try:
        import secretscan as SS
        if cmd and SS.find(cmd):
            cmd = "(command not kept: it looked like it held a secret)"
        d = os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard")); os.makedirs(d, exist_ok=True)
        flat = lambda x, n: str(x).replace("\t", " ").replace("\r", " ").replace("\n", " ")[:n]
        if WHOLE:
            t = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
            line = "\t".join([t, kind, flat(why, 4000), flat(cmd, 2000), flat(rule, 200)])
        else:
            t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            line = "\t".join([t, kind, flat(why, 300), flat(cmd, 200)])
        with open(os.path.join(d, "catches.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass                       # the log must never stop the guard itself


def read(cfg):
    p = os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"), "catches.log")
    return [l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def asks_on(rows, day):
    """The owner's boxes on one day (YYYY-MM-DD, the computer's own date), by rule, most first."""
    if BREAK_COUNT:
        return 0, []
    by = {}
    for r in rows:
        if len(r) > 1 and r[1] == "asked owner" and r[0][:10] == day:
            k = (r[4] if len(r) > 4 and r[4] else "no rule named")
            by[k] = by.get(k, 0) + 1
    return sum(by.values()), sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))


def today(cfg, day=None):
    """{"day", "asks", "budget", "over", "top"}: today's count of owner boxes against the budget (the owner, 16 Nov)."""
    day = day or datetime.datetime.now().strftime("%Y-%m-%d")
    n, top = asks_on(read(cfg), day)
    b = int(cfg.get("ask_budget", 5))
    return {"day": day, "asks": n, "budget": b, "over": n > b, "top": top[:5]}


def today_words(cfg, day=None):
    t = today(cfg, day)
    w = f"Owner asks today: {t['asks']} of {t['budget']}."
    if t["over"]:
        w += (" Over the budget: gather what's left for one sitting, and send the top reasons to the kit's friction list ("
              + ", ".join(f"{k}: {v}" for k, v in t["top"][:3]) + ").")
    return w


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    import config as C
    cfg = C.load()
    rows = read(cfg)
    if "--md" in sys.argv:
        print("| When | What happened | Why | Command |\n|---|---|---|---|")
        for r in rows:
            r = (r + ["", "", "", ""])[:4]; print("| " + " | ".join(x.replace("|", "/") for x in r) + " |")
    elif "--today" in sys.argv:
        if "--json" in sys.argv:
            import json; print(json.dumps(today(cfg)))
        else:
            print(today_words(cfg))
    elif "--asks" in sys.argv:
        i = sys.argv.index("--asks")
        n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 and sys.argv[i + 1].isdigit() else 20
        asks = [r + [""] * (5 - len(r)) for r in rows if len(r) > 1 and r[1] in ("asked owner", "blocked")][-n:]
        for t, kind, why, cmd, rule in asks:
            print(f"{t}  {kind}" + (f"  [{rule}]" if rule else ""))
            if cmd:
                print("  " + cmd)
            print("  " + why + "\n")
        print(f"{len(asks)} ask(s) and block(s) shown, newest last. The log: "
              + os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"), "catches.log"))
    else:
        for r in rows: print("  ".join(r))
        print(f"{len(rows)} catch(es) logged.")

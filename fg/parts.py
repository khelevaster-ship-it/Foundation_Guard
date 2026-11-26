"""FoundationGuard developer mode (AI-made, Claude, 2026-11-09; the screen and the picker added 2026-11-11, v0.8.5).

Beginners: leave everything on and never open this. Developers: pick the features you want.
  python fg/parts.py                           the screen: every feature in plain words, and whether it is on
  python fg/parts.py pick                      choose on that screen: type "4 off", "structure warn", "only 1 2 8", "done"
  python fg/parts.py set structure warn        one feature (by name or number): on, warn or off
  python fg/parts.py only guard push secrets   these on, every other feature off
  python fg/parts.py preset core               everything (all on) | core (guard, push, approved, secrets) |
                                               watch (guard, push, secrets on; the rest report without blocking)
  python fg/parts.py set review on             extra: every approved check must have been reviewed by a second helper
"on" blocks, "warn" reports but never blocks, "off" skips.
Run by you in your own terminal, these just do it. Run by an AI helper, each one asks you first, and a feature going
down is shown as making a check weaker. Every check also runs without any AI tool, for your own CI:  python fg/push.py --gate
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
WHAT = {"guard": "command guard for AI helpers", "push": "push only the tested commit", "approved": "approved list",
        "structure": "code-shape check", "rules": "maths rule and plugin list", "assets": "licence ledger",
        "tiny": "tiny-file rise", "secrets": "secret scan", "docs": "docs pack (truth + keeping up)",
        "state": "saved state kept (save, load, fingerprint)", "tests_gone": "tests that passed must run again",
        "pystartup": "Python start-up files watched", "receipts": "receipts (no receipt, no green)",
        "ledger": "your OKs: one version, once, for a day", "alarms": "failures sorted; fail-then-pass stops",
        "night": "a missed night job is said first thing",
        "reminders": "missing programs, the GitHub lock, too many boxes"}
PLAIN = {
    "guard": "Command guard. Stops an AI helper's destructive commands (force pushes, deleted branches, thrown-away work, "
             "changed GitHub settings) and asks you before it changes a check or this kit.",
    "push": "Tested-commit push. Only the exact commit that passed your tests can be pushed.",
    "approved": "Approved list. Every feature you signed off must have a check that ran and passed.",
    "structure": "Code-shape check. Files, classes and functions that balloon, copy-paste, tangled functions, loops between systems.",
    "rules": "Rule checks. Machine-dependent maths in the folders you name; new plugins, libraries and packages need your OK.",
    "assets": "Licence ledger. Art, sound, models and fonts with no recorded source or licence.",
    "tiny": "Tiny-files check. Code chopped into many tiny files to get under the size limits.",
    "secrets": "Secret scan. Passwords, keys and tokens in what you push.",
    "docs": "Docs pack. The project's docs must tell the truth (paths, switches, numbers) and keep up with the code.",
    "state": "Saved state. Every field of the types you list is in their save, load and fingerprint, or has a written reason.",
    "tests_gone": "Tests that stop running. A test that passed at the last upload and doesn't pass now stops the upload "
                  "until you say yes (warn: it is only named in the summary).",
    "pystartup": "Python's start-up files. Ones outside the project that changed since the last pass are named in the "
                 "summary (it never blocks).",
    "receipts": "Receipts. Every run of the gate and your listed checks leaves a receipt; python fg/receipts.py says "
                "which checks are proven on the code as it is now (it never blocks).",
    "ledger": "Your OKs. Each yes covers one exact version, once, for a day (off: a yes for a version counts for as long "
              "as that version stays).",
    "alarms": "Alarm sorter. A failing gate's tests are sorted REAL, UNSTEADY or MACHINE, and a test that failed and "
              "then passed on the same code stops the upload unless you parked it (warn: sorted and named only).",
    "night": "Night watch. A scheduled job (an expected check with every_hours) that didn't run, failed, or never "
             "finished is said at the start of the next session, so nobody wakes to find nothing got done (it never "
             "blocks).",
    "reminders": "Reminders. Each session starts by saying, only when it's so, that Git or Python is missing, that "
                 "the GitHub lock isn't on yet, or that you were asked more than 5 times a day (it never blocks)."}
PRESETS = {"everything": {n: "on" for n in C.PARTS},
           "core": {n: ("on" if n in ("guard", "push", "approved", "secrets", "tests_gone", "ledger", "alarms", "night", "reminders") else "off")
                    for n in C.PARTS},
           "watch": {n: ("on" if n in ("guard", "push", "secrets", "ledger", "night", "reminders") else "warn") for n in C.PARTS}}
MODES = ("on", "warn", "off")
USE = ("Change:  set <name or number> <on|warn|off>   only <names or numbers>   preset <everything|core|watch>   "
       "set review <on|off>")


def _name(x):
    """A feature's name from its name or its number on the screen, or None."""
    if x in C.PARTS:
        return x
    return C.PARTS[int(x) - 1] if x.isdigit() and 1 <= int(x) <= len(C.PARTS) else None


def _path(cfg):
    return os.path.join(cfg["_root"], "foundationguard.json")


def _steps_line(cfg):
    n = len(cfg.get("gate_steps") or [])
    return ("%d steps, kept per commit (python fg/stages.py --plan)" % n) if n else \
        "not set up: the gate is one command and always runs whole (examples/steps.foundationguard.json)"


def screen(cfg):
    """The developer-mode screen as text."""
    if BREAK("parts_screen"):
        return "\n".join(f"  {n:10} {C.part(cfg, n):5} {WHAT[n]}" for n in C.PARTS)
    out = ["FoundationGuard features (developer mode).  on = blocks   warn = reports, never blocks   off = skipped", ""]
    for i, n in enumerate(C.PARTS, 1):
        out.append(f"  {i}  {C.part(cfg, n).upper():5} {n:10} {PLAIN[n]}")
    out += ["", "Extras",
            f"     {'ON' if cfg.get('require_review') else 'off':5} {'review':10} A second helper must have reviewed each approved check before it counts.",
            f"     {'':5} {'steps':10} Step-by-step gate: {_steps_line(cfg)}",
            "", USE, "Or choose on this screen:  python fg/parts.py pick"]
    return "\n".join(out)


def _write(cfg, parts=None, review=None):
    """Write the changes into foundationguard.json and say what changed. Returns the lines printed."""
    p = _path(cfg); data = json.load(open(p, encoding="utf-8-sig")) if os.path.exists(p) else {}
    said = []
    for n, mode in (parts or {}).items():
        was = C.part(cfg, n)
        if was != mode:
            data.setdefault("parts", {})[n] = mode
            down = MODES.index(mode) > MODES.index(was)
            said.append(f"parts: {n} ({WHAT[n]}) is now {mode}." + ("  (was %s: this check now catches less)" % was if down else ""))
    if review is not None and bool(cfg.get("require_review")) != review:
        data["require_review"] = review
        said.append("parts: review is now %s." % ("on" if review else "off"))
    if said:
        json.dump(data, open(p, "w", encoding="utf-8"), indent=2)
    print("\n".join(said) if said else "parts: nothing to change.")
    return said


def _set(cfg, args):
    if len(args) == 2 and args[0] == "review" and args[1].lower() in ("on", "off") and not BREAK("parts_pick"):
        _write(cfg, review=args[1].lower() == "on"); return 0
    name = _name(args[0]) if args and not (BREAK("parts_pick") and args[0].isdigit()) else None
    if len(args) != 2 or not name or args[1].lower() not in MODES:
        print("parts: use  set <" + "|".join(C.PARTS) + "> <on|warn|off>"); return 1
    _write(cfg, {name: args[1].lower()}); return 0


def _only(cfg, args):
    names = [_name(a) for a in args]
    if not names or None in names:
        print("parts: use  only <names or numbers>, for example: only guard push secrets"); return 1
    _write(cfg, {n: ("on" if n in names else "off") for n in C.PARTS}); return 0


def _preset(cfg, args):
    if len(args) != 1 or args[0] not in PRESETS:
        print("parts: use  preset <" + "|".join(PRESETS) + ">"); return 1
    _write(cfg, PRESETS[args[0]]); return 0


def _do(cfg, words):
    """One instruction (from the command line or typed on the pick screen). 0 done, 1 not understood."""
    if not words:
        return 1
    if words[0] == "set":
        return _set(cfg, words[1:])
    if BREAK("parts_pick"):
        return 1
    if words[0] == "only":
        return _only(cfg, words[1:])
    if words[0] == "preset":
        return _preset(cfg, words[1:])
    if len(words) == 2 and (_name(words[0]) or words[0] == "review"):      # the short form on the pick screen: "4 off"
        return _set(cfg, words)
    return 1


def pick():
    """Choose on the screen: one instruction a line until 'done'."""
    print(screen(C.load()))
    while True:
        try:
            line = input("\nfeature and setting (for example: 4 off), or done > ").strip()
        except EOFError:
            break
        if line.lower() in ("done", "q", "quit", "exit", ""):
            break
        if _do(C.load(), line.split()):
            print("Not understood. Examples:  4 off    structure warn    only 1 2 8    preset core    review on    done")
    print("\n" + screen(C.load()))
    return 0


def main(argv):
    cfg = C.load()
    if argv and argv[0] == "pick" and not BREAK("parts_pick"):
        return pick()
    if argv:
        return _do(cfg, argv) and (print(__doc__) or 1)
    print(screen(cfg))
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

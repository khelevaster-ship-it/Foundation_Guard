"""FoundationGuard: the owner's door (AI-made, Claude, 2026-11-14; Fable's beta plan, line 2 of the beta gate).

The owner typed `python fg/away.py off` in their own terminal while a helper session ran, and the session's next check
put it back as "changed outside any helper step": the kit's own commands wrote a switch and told nobody. Now a kit
command that the owner runs in a real terminal writes one stamped line per file it changed to a journal in that
folder's git folder (proof book "door": path, what it held before, what it holds after, when, what the owner was shown).
The checks before and after each step, and between steps, keep such a file when:
  - what it holds now is the "after" of a door line, and
  - the "before" of that line is what the kit had accepted (so a file tampered with first is never blessed).

Who may use it: a real terminal (stdin is a terminal). A change that loosens a check also asks for a typed code, after
saying what will change; one that only tightens (away mode off) needs no code. A helper's run (no terminal) writes a
line only for a file the owner's yes in the kit's box covers (an install: the box names what it writes, and the line
lets each copy of the project keep it even when the check after that step never runs there).
Limits: a program that fakes a terminal, or reads the stamp key, can use the door (as for the ledger). The upload
check and GitHub's lock bound the damage.
"""
import os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
BOOK = "door"
FRESH = 24 * 3600                       # a door line counts for a day; after that the normal judging applies


def terminal():
    """stdin is a real terminal. On Windows the NUL device also says it is one (a helper's run, CI), so a console is
    asked for too: a Git Bash window (mintty) is not one, and there the owner uses PowerShell or the Command Prompt."""
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return False
        if os.name != "nt":
            return True
        import ctypes, msvcrt
        mode = ctypes.c_ulong()
        return bool(ctypes.windll.kernel32.GetConsoleMode(msvcrt.get_osfhandle(sys.stdin.fileno()), ctypes.byref(mode)))
    except Exception:
        return False


def owner_here(what, tightening=False):
    """True when the owner runs this in a real terminal, and (unless it only tightens) types the code shown."""
    if BREAK("door_tty"):
        return True
    if not terminal():
        return False
    if tightening:
        return True
    print("FoundationGuard: " + what)
    code = "".join(random.choice("ABCDEFGHJKMNPQRSTUVWXYZ") for _ in range(4))
    try:
        return input(f"To say yes, type {code} and press Enter (anything else says no): ").strip().upper() == code
    except EOFError:
        return False


def allowed(cfg, fulls):
    """The files of fulls a kit command may write a door line for: all of them in the owner's terminal; in a helper's
    step, those the owner's yes in the kit's box covers (the box for an install names every file it writes)."""
    if BREAK("install_door"):
        return set()
    if terminal() or BREAK("door_tty"):
        return set(fulls)
    import steps as SP
    yeses = SP.step_yeses(cfg)
    return {f for f in fulls if any(y.covers(f) for y in yeses)}


def ids(fulls):
    return {f: entry_id(f) for f in fulls}


def wrote_changed(cfg, before, shown, ok=None):
    """A door line for each file in before (its id before the write) that the command changed and may write one for
    (ok: the folder whose box or terminal says so, when the file is in another copy). Returns the files written for."""
    changed = [f for f, b in before.items() if entry_id(f) != b]
    mine = allowed(ok or cfg, changed)
    for f in changed:
        if f in mine:
            wrote(cfg, f, before[f], shown)
    return [f for f in changed if f in mine]


def entry_id(full):
    import steps as SP
    return SP._entry(full).get("id")


def wrote(cfg, full, before, shown):
    """Write the door line for one file the owner's command changed (before: its id before the write)."""
    import proofstore as PS
    import paths as P
    rel = P.rel(full, cfg["_root"]).replace("\\", "/")
    PS.append(cfg, BOOK, {"path": rel, "before": before, "after": entry_id(full), "at": time.time(), "shown": shown[:300]})


def write(cfg, full, data, shown, line=True):
    """The owner's kit command writes a file: the door line FIRST, naming what the file will hold, then the file in one
    step (a new file moved over the old). The game's PC, 16 Nov 12:45 UTC: away.py wrote the settings and only then its
    door line, and a helper step ending in between put the owner's switch back as unexplained. line: False when no door
    line may be written (not the owner's terminal); the file is still written in one step."""
    import steps as SP
    import tempfile
    before = entry_id(full)
    if line and not BREAK("door_line_first"):
        _line(cfg, full, before, SP.blob_id(data), shown)
    d = os.path.dirname(full) or "."
    fd, tmp = tempfile.mkstemp(prefix=".fg-", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if os.path.exists(full):
            os.chmod(tmp, os.stat(full).st_mode & 0o777)
        os.replace(tmp, full)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    if line and BREAK("door_line_first"):
        wrote(cfg, full, before, shown)


def _line(cfg, full, before, after, shown):
    import proofstore as PS
    import paths as P
    rel = P.rel(full, cfg["_root"]).replace("\\", "/")
    PS.append(cfg, BOOK, {"path": rel, "before": before, "after": after, "at": time.time(), "shown": shown[:300]})


def blesses(cfg, rel, base, now):
    """True when a fresh, trusted door line took this file from what the kit accepted (base) to what it holds now."""
    if BREAK("door_between") or not (now or {}).get("id"):
        return False
    import proofstore as PS
    rel = rel.replace("\\", "/")
    want_before = (base or {}).get("id")
    for r in reversed(PS.read(cfg, BOOK)):
        if r.get("_bad") or r.get("path") != rel or time.time() - float(r.get("at") or 0) > FRESH:
            continue
        if r.get("after") == now["id"]:
            return r.get("before") == want_before or BREAK("door_from_accepted")
    return False

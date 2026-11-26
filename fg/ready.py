"""FoundationGuard: is this computer ready, is the project locked, and how often are you asked? (AI-made, Claude,
2026-11-13; round 9's usability points, the owner's yes the same day)

Three things that make an owner who doesn't code give up:
  - a missing program (Git, or a Python too old) that ends in an error only a programmer can read;
  - not knowing they aren't fully protected until GitHub is locked;
  - so many yes-boxes that they stop reading them.

  python fg/ready.py           Python and Git on this computer, the GitHub lock, the yes-boxes of the last 7 days, and
                               whether the tests have ever passed through the kit here
  python fg/ready.py --hook    the session-start message: silent when all is well; otherwise plain words the helper
                               passes on to the owner first (a missing program, the GitHub lock not on yet, too many
                               boxes yesterday)
setup.py checks Python and Git first, in the same words. The yes-boxes are counted from the kit's catch log (every
time it asked the owner). Part reminders (on, warn, off): off makes the hook silent. It only informs.
"""
import datetime, os, platform, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
PY_MIN = (3, 10)                     # the oldest Python the kit's own tests run on (CI, GUIDE)
BOXES_A_DAY = 5                     # the owner OK ledger plan: more than five a day wears people down
GET_GIT = {"Windows": "ask your helper to install Git for you (it runs: winget install Git.Git), or download it from "
                      "git-scm.com, then open a new terminal",
           "Darwin": "ask your helper to install Git for you (it runs: xcode-select --install), then open a new terminal",
           "Linux": "ask your helper to install Git for you (for example: sudo apt install git)"}


def tools():
    """Plain-words problems with the programs the kit needs on this computer; [] when all is well."""
    out = []
    if sys.version_info[:2] < PY_MIN or BREAK("ready_python"):
        have = ".".join(map(str, sys.version_info[:3]))
        out.append(f"this Python is {have}, and FoundationGuard needs {PY_MIN[0]}.{PY_MIN[1]} or newer: ask your helper "
                   "to install a newer Python from python.org, then run setup again")
    if not _git_works() and not BREAK("ready_git"):
        out.append("Git isn't installed on this computer (or can't be found), and FoundationGuard needs it to keep your "
                   "project's history: " + GET_GIT.get(platform.system(), GET_GIT["Linux"]) + ", then run setup again")
    if out == [] and not _git_knows_you() and not BREAK("ready_identity"):
        out.append("Git doesn't know your name and email yet, so it can't save versions of your project (the owner's PC, 13 "
                   "Nov): ask your helper to set them (it runs: git config --global user.name \"Your Name\" and git "
                   "config --global user.email \"you@example.com\"; any email works), then run setup again")
    return out


def _git_knows_you():
    """Git can name who saves a version here. A CI machine (no person) is left alone."""
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return True
    try:
        return subprocess.run(["git", "var", "GIT_COMMITTER_IDENT"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return True


def _git_works():
    if not shutil.which("git"):
        return False
    try:
        return subprocess.run(["git", "--version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def lock_words(cfg):
    """Plain words when the project has a GitHub copy that isn't locked yet. GitHub's own answer counts (the game's PC,
    13 Nov: main was locked, and this said it wasn't because it never asked); it is asked at most once a day."""
    import lock as LK
    known = LK.seen(cfg)
    st, why = LK.state(cfg) if known is None else ("locked" if known else "not locked", [])
    if st in ("locked", "confirmed", "no github") or BREAK("ready_lock"):
        return ""
    if st == "could not check":
        return ("The kit couldn't check your GitHub lock (" + (why[0] if why else "no answer") + "). If main is locked "
                "on GitHub, tell your helper so in your own words; if not: " + LK.HELPER_LINE)
    return ("YOU ARE NOT FULLY PROTECTED YET: the GitHub lock isn't on, and it is the lock that really holds (on this "
            "computer the kit is a safety net, not a lock). " + LK.HELPER_LINE)


def boxes(cfg, days=7, today=None):
    """[(date, how many times the kit asked the owner)] for the last days, oldest first."""
    import catches as CL
    today = today or datetime.date.today()
    count = {}
    for r in CL.read(cfg):
        if len(r) > 1 and r[1] == "asked owner":
            count[r[0][:10]] = count.get(r[0][:10], 0) + 1
    return [((today - datetime.timedelta(days=n)).isoformat(), count.get((today - datetime.timedelta(days=n)).isoformat(), 0))
            for n in range(days - 1, -1, -1)]


def box_words(cfg):
    """Plain words when yesterday or today had more boxes than people keep reading."""
    many = [(d, n) for d, n in boxes(cfg, 2) if n > BOXES_A_DAY]
    if not many or BREAK("ready_boxes"):
        return ""
    d, n = many[-1]
    return (f"you were asked {n} times on {d}. Past about {BOXES_A_DAY} a day, people stop reading them. Ask your helper "
            "which files keep asking (python fg/catches.py --asks) and whether they should be guarded at all, or set "
            "to allow in foundationguard.json (guard_decisions), so the boxes you do get are the ones that matter.")


def gate_words(cfg):
    """Plain words when the project's tests have never passed through the kit here, else "" (the owner's PC, 13 Nov: ready
    said all OK on a project whose gate had never passed, so nothing could be uploaded)."""
    import config as C
    import receipts as RC
    if C.part(cfg, "receipts") == "off" or BREAK("ready_gate"):
        return ""
    if any(r.get("check") == RC.GATE and r.get("ok") and RC._trusted(r) for r in RC._runs(cfg).values()):
        return ""
    return ("Your tests have never passed through the kit in this project, so nothing can be uploaded yet. Ask your "
            "helper to run: python fg/push.py --gate, and to explain anything it says.")


STALE = ("The kit's hooks in this folder changed after this session started (an install or an update), and a session "
         "keeps the hooks it started with, so some checks may not run in it. Restart this session when you can: close "
         "it and open a new one in this folder.")


def stale_words(cfg, data):
    """Fable's beta plan, line 3: the hooks a session runs are fixed when it starts. Remember each session's hook wiring
    at its start; when it resumes, compacts or clears with different wiring on disk, say so."""
    if BREAK("session_stale") or not isinstance(data, dict) or not data.get("session_id"):
        return ""
    import hashlib, json
    import steps as SP
    h = hashlib.sha256()
    for f in (".claude/settings.json", ".claude/settings.local.json"):
        try:
            j = json.load(open(os.path.join(cfg["_root"], f), encoding="utf-8-sig"))
            h.update(json.dumps(j.get("hooks") if isinstance(j, dict) else None, sort_keys=True).encode())
        except (OSError, ValueError):
            h.update(b"-")
    now, sid = h.hexdigest()[:16], str(data["session_id"])
    p = os.path.join(SP._dir(cfg), "sessions.json")
    seen = SP._read_json(p, {}) or {}
    was = (seen.get(sid) or {}).get("hooks")
    if data.get("source") == "startup" or not was:
        seen[sid] = {"hooks": now, "at": time.time()}
        SP._write_json(p, dict(sorted(seen.items(), key=lambda kv: (kv[1] or {}).get("at", 0))[-50:]))
        return ""
    return "" if was == now else STALE


def _hook_input(wait=2.0):
    """The session's start details, which the AI tool writes on this hook's input and then closes. Read in a helper
    thread that gives up after a moment: a hook run by hand or by a program that leaves its input open (GitHub's Linux
    runners do) must not wait for ever (15 Nov: #46's tests ran 6 hours)."""
    import json, threading
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return None
    except (OSError, ValueError):
        return None
    got, fd = [], sys.stdin.fileno()
    if os.name == "nt" and not BREAK("hook_input_waits"):
        return _peek_windows(fd, wait)

    def read():                                    # the bare file, not sys.stdin: a thread still waiting in sys.stdin
        chunks = []                                # holds its lock, and Python on Windows then never exits
        while True:
            b = os.read(fd, 65536)
            if not b:
                break
            chunks.append(b)
        got.append(b"".join(chunks).decode("utf-8", "replace"))
    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(None if BREAK("hook_input_waits") else wait)        # the break: wait until the input closes
    _READER.append(t)
    if not got:
        return None
    try:
        return json.loads(got[0] or "null")
    except ValueError:
        return None


_READER = []


def _peek_windows(fd, wait):
    """Windows: a read left waiting on a pipe keeps the process from ending, so the pipe is only peeked at, and read
    when bytes are there, until it closes or nothing more comes for `wait` seconds. A file (not a pipe) is just read."""
    import ctypes, json, msvcrt
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    h = msvcrt.get_osfhandle(fd)
    if k32.GetFileType(h) != 3:                    # FILE_TYPE_PIPE; anything else can't wait for ever
        try:
            return json.loads(os.read(fd, 1 << 20).decode("utf-8", "replace") or "null")
        except (OSError, ValueError):
            return None
    k32.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    chunks, end = [], time.time() + wait
    while time.time() < end:
        n = wintypes.DWORD(0)
        if not k32.PeekNamedPipe(h, None, 0, None, ctypes.byref(n), None):
            break                                  # the writer closed it: all there is has been read
        if n.value:
            chunks.append(os.read(fd, n.value)); end = time.time() + wait
        else:
            time.sleep(0.02)
    try:
        return json.loads(b"".join(chunks).decode("utf-8", "replace") or "null")
    except ValueError:
        return None


def _leave(code):
    """Exit; when the input reader is still waiting, at once (Windows waits for it otherwise)."""
    if any(t.is_alive() for t in _READER):
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(code if isinstance(code, int) else 0)
    return code


def hook(cfg, data=None):
    import config as C
    if C.part(cfg, "reminders") == "off":
        return 0
    import away as AW
    said = [w for w in tools() + [stale_words(cfg, data), lock_words(cfg), box_words(cfg), AW.back_words(cfg)] if w]
    if said:
        print("FG-READY: " + " ".join(said) + " Tell the owner this first, in plain words.")
    return 0


def main(argv):
    problems = tools()
    if "--hook" not in argv:
        for p in problems:
            print("  LOOK  " + p)
        if not problems:
            print("  OK    Python and Git are installed")
    try:
        import config as C
        cfg = C.load()
    except Exception:
        return 1 if problems else 0
    if "--hook" in argv:
        return _leave(hook(cfg, _hook_input()))
    lock = lock_words(cfg)
    print(("  LOOK  " + lock) if lock else "  OK    GitHub: locked, confirmed, or no GitHub copy")
    print("  Yes-boxes, last 7 days: " + ", ".join(f"{d[5:]} {n}" for d, n in boxes(cfg)))
    many = box_words(cfg)
    if many:
        print("  LOOK  " + many)
    gate = gate_words(cfg)
    print(("  LOOK  " + gate) if gate else "  OK    Your tests have passed through the kit here")
    return 1 if problems or lock or many or gate else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

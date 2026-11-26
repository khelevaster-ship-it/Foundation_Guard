"""FoundationGuard: Python's start-up files (AI-made, Claude, 2026-11-13; outside review 8, Grok).

Python runs `sitecustomize.py`, `usercustomize.py` and the `.pth` files in its package folders every time it starts,
before any test. Those live outside the project, where the kit's guard doesn't reach, so a helper could put one there
that changes what the tests see. The kit can't stop that, but it notices: at every pass of the gate it keeps a
fingerprint of those files, and when one is new or changed since the last pass the upload says so in plain words
(and fg/doctor.py says LOOK). Installing a Python package changes them too, so this warns and doesn't stop the upload.

  python fg/pyenv.py      list the start-up files that are new or changed since the last pass
"""
import glob, hashlib, json, os, site, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
NAME = "python_startup.json"
STARTUP = ("sitecustomize.py", "usercustomize.py")


def path(cfg):
    return os.path.join(cfg["_root"], (cfg.get("state_dir") or ".foundationguard").strip("/"), NAME)


def _dirs():
    out = []
    try:
        out += site.getsitepackages()
    except AttributeError:
        pass
    try:
        out.append(site.getusersitepackages())
    except AttributeError:
        pass
    return [d for d in dict.fromkeys(out + [p for p in sys.path if p]) if os.path.isdir(d)]


def files(root):
    """{path: fingerprint} for Python's start-up files outside the project."""
    root = os.path.realpath(root)
    out = {}
    for d in _dirs():
        if os.path.realpath(d).startswith(root + os.sep) or os.path.realpath(d) == root:
            continue
        for f in [os.path.join(d, n) for n in STARTUP] + glob.glob(os.path.join(d, "*.pth")):
            try:
                out[f] = hashlib.sha1(open(f, "rb").read()).hexdigest()[:16]
            except OSError:
                pass
    return out


def _load(cfg):
    try:
        d = json.load(open(path(cfg), encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def changed(cfg):
    """The start-up files new or changed since the last pass (none before the first record)."""
    before = _load(cfg)
    if before is None or BREAK("python_startup"):
        return []
    return sorted(f for f, v in files(cfg["_root"]).items() if before.get(f) != v)


MEANS = ("Installing a Python package changes them, and that is fine. If nobody installed anything, one of them could "
         "change what your tests see.")
ACTION = "Uploaded. Ask your helper what changed them. If it can't say, ask it to show you the file."


def cards(cfg):
    """[a plain-words card for the upload summary] when a start-up file is new or changed, else []."""
    new = changed(cfg) if C.part(cfg, "pystartup") != "off" else []
    if not new:
        return []
    named = ", ".join(new[:4]) + (" and more" if len(new) > 4 else "")
    happened = "These files outside your project, which Python runs before any test, are new or changed: " + named + "."
    return [{"who": "you", "title": "Python's start-up files changed since the last pass", "happened": happened,
             "means": MEANS, "action": ACTION, "evidence": new}]


def save(cfg):
    os.makedirs(os.path.dirname(path(cfg)), exist_ok=True)
    with open(path(cfg), "w", encoding="utf-8") as f:
        json.dump(files(cfg["_root"]), f, indent=1)
    import steps as SP
    SP.recorded(cfg, [path(cfg)])


def main(argv):
    cfg = C.load()
    new = changed(cfg)
    for f in new:
        print("  NEW OR CHANGED  " + f)
    print("FG-PYTHON: %d of Python's start-up files are new or changed since the last pass." % len(new))
    return 1 if new else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

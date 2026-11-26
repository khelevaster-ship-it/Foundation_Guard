"""Matching repo paths against FoundationGuard's guard globs (AI-made, Claude, 2026-11-08)."""
import fnmatch, os, re

import quiet  # noqa: F401  (every program the kit starts gets no keyboard: fg/quiet.py)


def rel(path, root):
    p = os.path.abspath(os.path.join(root, path)) if not os.path.isabs(path) else os.path.abspath(path)
    try:
        r = os.path.relpath(p, root)
    except ValueError:                 # Windows: another drive (D: vs C:) is never inside the project; keep the full path
        if os.environ.get("FG_BREAK", "") == "cross_drive":
            raise
        r = p
    return r.replace("\\", "/")


def shell_path(p, windows=None):
    """A path as Git Bash writes it on Windows (/c/MyGameWT) in the form Python reads (C:/MyGameWT); elsewhere, and any
    other path, unchanged (the game's PC, 12 Nov: "cd /c/MyGameWT" was read as C:\\c\\MyGameWT, so a later write into a
    guard folder by its short name could be missed)."""
    m = re.match(r"^/([A-Za-z])(/.*)?$", p)
    if not m or not (os.name == "nt" if windows is None else windows) or os.environ.get("FG_BREAK", "") == "git_bash_paths":
        return p
    return m.group(1).upper() + ":" + (m.group(2) or "/")


def kit_dir(root):
    """The kit's folder as the hooks should name it: relative to the project, or in full when it is on another drive."""
    return rel(os.path.dirname(os.path.abspath(__file__)), root)


def from_top(top, fg):
    """'<top>/<fg>' for a kit inside the project; the kit's full path when it lives elsewhere (another drive)."""
    return fg if os.path.isabs(fg) or re.match(r"^[A-Za-z]:/", fg) else top + "/" + fg


def matches(path, globs):
    path = path.replace("\\", "/")
    if os.environ.get("FG_BREAK", "") == "paths_dot":
        path = path.lstrip("./") if not path.startswith("..") else path       # the v0.3-v0.6 bug: ".git/..." became "git/..."
    else:
        while path.startswith("./"):
            path = path[2:]                                                    # only a leading "./", never the dot of ".git"
        path = path.lstrip("/")
    for g in globs:
        if fnmatch.fnmatch(path, g) or (g.endswith("/**") and (path == g[:-3] or path.startswith(g[:-2]))) \
                or (g.startswith("**/") and fnmatch.fnmatch(path, g[3:])):
            return True
    return False

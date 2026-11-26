"""FoundationGuard: who is signed in to GitHub on this computer, and what that login may do (AI-made, Claude,
2026-11-17; Plan 2 part 5 and the team plan, merge C).

The lock only holds if the helper's login can't do what the owner can. So the kit looks, read-only, in the places a
helper's commands would find a GitHub login:
  - every account gh is signed in with (gh auth status, never the key itself);
  - git's own settings for logins (credential.helper, credential.<url>.username);
  - ~/.git-credentials (the names only; the keys in it are never read out or kept);
  - the GH_TOKEN, GITHUB_TOKEN and GH_ENTERPRISE_TOKEN variables (whether one is set, never its value).
It can't see: logins kept by browsers, by other apps, by the operating system's own key store (unless git names it),
or by cloud helpers that act as you. It says so every time.

  python fg/logins.py        what it found, with the names only
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
CANT_SEE = ("logins kept by browsers, other apps or the system's key store, and cloud helpers that act as you")
TOKEN_VARS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")


def _run(cmd, root, timeout=10):
    try:
        p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=timeout,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never"))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def gh_accounts(root, gh):
    """The GitHub logins gh is signed in with ([] when none, or no gh)."""
    if not gh:
        return []
    code, out = _run([gh, "auth", "status"], root)
    names = re.findall(r"\b(?:account|as)\s+@?([A-Za-z0-9-]+)", out or "")
    return list(dict.fromkeys(names))


def git_logins(root):
    """Names git would offer GitHub: credential.<url>.username and the users in ~/.git-credentials (never the keys)."""
    names = []
    code, out = _run(["git", "config", "--get-regexp", r"^credential\..*username$"], root)
    for line in (out or "").splitlines():
        if "github" in line.lower():
            names.append(line.split()[-1])
    p = os.path.expanduser("~/.git-credentials")
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            m = re.match(r"\s*https?://([^:@/\s]+)(?::[^@\s]*)?@([^/\s]*github[^/\s]*)", line)
            if m:
                names.append(m.group(1))
    except OSError:
        pass
    return list(dict.fromkeys(names))


def helpers(root):
    """The credential helpers git uses (each could hand a helper's git a login without asking)."""
    code, out = _run(["git", "config", "--get-all", "credential.helper"], root)
    return [l.strip() for l in (out or "").splitlines() if l.strip()]


def token_vars():
    return [v for v in TOKEN_VARS if os.environ.get(v)]


def found(root, gh):
    """{"gh", "git", "helpers", "vars", "cant_see"}: names only, never a key."""
    if BREAK("lock_owner_key_here"):
        return {"gh": [], "git": [], "helpers": [], "vars": [], "cant_see": CANT_SEE}
    return {"gh": gh_accounts(root, gh), "git": git_logins(root), "helpers": helpers(root), "vars": token_vars(),
            "cant_see": CANT_SEE}


def names(f):
    return list(dict.fromkeys(n.lower() for n in f["gh"] + f["git"]))


def main(argv):
    import config as C, lock as LK
    cfg = C.load()
    f = found(cfg["_root"], LK.find_gh(cfg))
    print("FoundationGuard: GitHub logins this computer's commands could use (names only):")
    print("  gh: " + (", ".join(f["gh"]) or "none"))
    print("  git: " + (", ".join(f["git"]) or "none") + ("  (helpers: " + ", ".join(f["helpers"]) + ")" if f["helpers"] else ""))
    print("  key variables set: " + (", ".join(f["vars"]) or "none"))
    print("  can't see: " + f["cant_see"])
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

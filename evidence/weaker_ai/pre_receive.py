#!/usr/bin/env python3
"""Test 'server' (stands in for GitHub branch protection): refuses guard-file changes without the owner's review and
runs the FoundationGuard gate on exactly the pushed commit. Logs every attempt to SERVER_LOG (outside the helper's project)."""
import fnmatch, json, os, shutil, subprocess, sys, tempfile, time
LOG = os.environ.get("SERVER_LOG") or os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "..", "..", "server_log.jsonl")
Z = "0" * 40

def git(*a, cwd=None, inp=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=inp is None, input=inp)

def extract(sha, dest):
    os.makedirs(dest, exist_ok=True)
    tar = subprocess.run(["git", "archive", sha], capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", dest], input=tar)

def guard_globs(tree_dir):
    sys.path.insert(0, os.path.join(tree_dir, "fg"))
    import config as C
    cfg = json.load(open(os.path.join(tree_dir, "foundationguard.json")))
    return C.guard_globs(cfg)

def log(rec):
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")

def check(old, new, ref):
    files = git("diff", "--name-only", old, new).stdout.split() if old != Z else []
    tmp = tempfile.mkdtemp()
    try:
        base = os.path.join(tmp, "base"); extract(old, base)
        globs = guard_globs(base)
        g = [f for f in files if any(fnmatch.fnmatch(f, p) or fnmatch.fnmatch(f, p.rstrip("*").rstrip("/") + "/*") for p in globs)]
        if g:
            return False, "guard files changed without the owner's review: " + ", ".join(g), files
        up = os.path.join(tmp, "up.git"); work = os.path.join(tmp, "work")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        r = lambda *a, cwd=work: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, env=env)
        subprocess.run(["git", "init", "-q", "--bare", up], env=env)
        shutil.copytree(base, work)
        r("init", "-q", "-b", "main"); r("add", "-A"); r("-c", "user.email=s@x", "-c", "user.name=s", "commit", "-qm", "base")
        r("remote", "add", "origin", up); r("push", "-q", "origin", "main"); r("branch", "-u", "origin/main")
        for n in os.listdir(work):
            if n != ".git":
                p = os.path.join(work, n); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        extract(new, work)
        r("add", "-A"); r("-c", "user.email=s@x", "-c", "user.name=s", "commit", "-qm", "pushed")
        p = subprocess.run([sys.executable, "fg/push.py", "--gate"], cwd=work, capture_output=True, text=True, env={**env, "FG_SERVER": "1"}, timeout=600)
        ok = p.returncode == 0
        return ok, (p.stdout + p.stderr)[-1500:], files
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

bad = False
for line in sys.stdin:
    old, new, ref = line.split()
    if new == Z:
        ok, why, files = False, "deleting a branch is refused", []
    else:
        ok, why, files = check(old, new, ref)
    log({"t": time.time(), "ref": ref, "old": old, "new": new, "accepted": ok, "why": why[-600:], "files": files})
    if not ok:
        bad = True
        print("SERVER REFUSED: " + why[-800:])
sys.exit(1 if bad else 0)

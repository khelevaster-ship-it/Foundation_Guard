"""FoundationGuard git pre-push hook (AI-made, Claude, 2026-11-08). Installed by fg/install.py as .git/hooks/pre-push.
Covers pushes made by people and other tools too: every pushed commit must be the one the gate passed, and nothing may
be pushed to a protected branch or deleted. (A person can still skip it with --no-verify; GitHub-side branch protection
is the only thing that can't be skipped.)"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import secretscan as SS
import switches as SW

def _ref_problem(local_sha, remote_ref, prot):
    if set(local_sha) == {"0"}:
        return "FG pre-push: deleting a remote branch or tag is not allowed."
    if remote_ref.replace("refs/heads/", "").lower() in prot:
        return f"FG pre-push: '{remote_ref}' is protected."
    if remote_ref.startswith("refs/tags/"):
        return "FG pre-push: pushing tags is not allowed."
    return None


def _secrets_stop(cfg, local_sha, remote_sha):
    """True if a secret in what is pushed stops it (secrets part 'on'); found secrets are printed either way."""
    if not cfg.get("secret_scan", True) or C.part(cfg, "secrets") == "off" or os.environ.get("FG_BREAK") == "secrets_prepush":
        return False
    root = cfg["_root"]
    rng = SS.push_range(root, local_sha, remote_sha)
    hits = SS.scan(root, SS.added_lines(root, rng) if rng else SS.tracked_lines(root))
    if not hits:
        return False
    print("FG pre-push: " + SS.report(hits))
    return C.part(cfg, "secrets") == "on"


def _overwrites(root, local_sha, remote_sha):
    """Why this push would throw away commits on the remote branch, or None. Outside review 3 (Claude, 12 Nov, finding 5):
    a force push written so the guard couldn't read it ({ git push --force origin HEAD:feature-x; }) went through this
    hook, which only checked the pushed commit, and a colleague's commit was gone from the remote. The remote's commit
    must be in what is pushed: an ordinary push, never one that replaces history."""
    if set(remote_sha) == {"0"} or os.environ.get("FG_BREAK") == "prepush_fast_forward":
        return None                                  # a new branch: nothing on the remote to lose
    run = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run("cat-file", "-e", remote_sha + "^{commit}").returncode != 0:
        return (f"FG pre-push: the remote branch has a commit this copy hasn't got ({remote_sha[:10]}). Pushing over it "
                "would throw it away. Fetch and merge it first (git pull), then push with `python fg/push.py`.")
    if run("merge-base", "--is-ancestor", remote_sha, local_sha).returncode != 0:
        return (f"FG pre-push: this push would replace the remote branch's history (its commit {remote_sha[:10]} is not in "
                "what is pushed), throwing work away. Merge the remote branch first (git pull), then push again.")
    return None


def _one_ref(cfg, p, prot, passed):
    """0 if this pushed ref may go, 1 if it stops the push."""
    local_ref, local_sha, remote_ref, remote_sha = p[:4]
    why = _ref_problem(local_sha, remote_ref, sorted(set(prot) | set(SW.protected(cfg, remote_sha))))
    if why:
        print(why); return 1
    if _secrets_stop(cfg, local_sha, remote_sha):
        return 1
    lost = _overwrites(cfg["_root"], local_sha, remote_sha)
    if lost:
        print(lost); return 1
    if local_sha == passed:
        return 0
    mode = SW.push_mode(cfg, remote_sha)              # review 6: the strictest of this file, the accepted copy, the remote's
    if mode != "on":
        print(f"FG pre-push: {local_sha[:10]} didn't pass the gate (push check is {mode} in parts, so it goes ahead).")
        return 0
    print(f"FG pre-push: {local_sha[:10]} is not the commit that passed the gate. Push with `python fg/push.py`."); return 1


def main():
    cfg = C.load(); prot = [b.lower() for b in cfg["protected_branches"]]
    import steps as SP
    passed = SP.passed(cfg)                            # review 6: only a pass the kit recorded (F265)
    for p in (line.split() for line in sys.stdin):
        if len(p) >= 4 and _one_ref(cfg, p, prot, passed):
            return 1
    return 0

if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main())

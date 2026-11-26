"""Proves the Windows download on the computer it was just installed on (AI-made, Claude, 2026-11-19; beta gate line 4).

Run BY the installed Python, with every other Python off the PATH:

    "<install folder>\\python\\python.exe" check_download.py

It sets up a small project in a folder with a space in its name, as a helper would for an owner who has never
installed Python, and checks: every hook calls the download's own Python by its full path; a piped force push prints
BLOCK; the AI tool's own hook refuses it; the tests pass through the kit's gate; an upload goes through git's pre-push
hook; and the check-up says the kit's own Python is there. Ends 0 only when every line says ok.
"""
import json, os, shutil, subprocess, sys, tempfile

EXE = sys.executable
APP = os.path.dirname(os.path.dirname(EXE))
FWD = '"' + EXE.replace("\\", "/") + '"'
FAILS = []


def ok(cond, what, more=""):
    print(("ok    " if cond else "FAIL  ") + what + ("" if cond or not more else "\n      " + str(more)[-1500:].replace("\n", "\n      ")))
    if not cond:
        FAILS.append(what)
    return cond


def run(args, cwd, text_in=None, shell=False, env=None):
    e = dict(os.environ); e.update(env or {})
    p = subprocess.run(args, cwd=cwd, input=text_in, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       shell=shell, env=e, stdin=None if text_in is not None else subprocess.DEVNULL)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def bash():
    """Git's own bash, as the AI tool uses on Windows (never the Windows stand-in of the same name)."""
    git = shutil.which("git") or ""
    mine = os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe")
    return mine if os.name == "nt" and os.path.isfile(mine) else "bash"


def project(top):
    r = os.path.join(top, "My Game"); os.makedirs(os.path.join(r, "tests"))
    open(os.path.join(r, "game.py"), "w").write("def gold(x):\n    return x + 1\n")
    open(os.path.join(r, "tests", "test_game.py"), "w").write(
        "import unittest\nfrom game import gold\nclass T(unittest.TestCase):\n    def test_gold(self): self.assertEqual(gold(1), 2)\n")
    run(["git", "init", "-q", "--bare", os.path.join(top, "remote.git")], top)
    for a in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "first version"],
              ["remote", "add", "origin", os.path.join(top, "remote.git").replace("\\", "/")]):
        run(["git", *a], r)
    return r


def hook_commands(r):
    j = json.load(open(os.path.join(r, ".claude", "settings.json"), encoding="utf-8-sig"))
    return [(ev, h.get("command", "")) for ev, entries in j.get("hooks", {}).items() for e in entries for h in e.get("hooks", [])]


def main():
    print("FoundationGuard download check: " + APP)
    ok(os.path.isfile(os.path.join(os.path.dirname(EXE), "foundationguard-python.txt")), "this Python is the download's own (the marker file is beside it)")
    ok(os.path.isfile(os.path.join(APP, "fg", "setup.py")) and os.path.isfile(os.path.join(APP, "AGENT_SETUP.md")), "the kit and the helper's guide were installed beside it")
    if os.name == "nt":
        ok(" " in APP, "the install folder has a space in its name (as a user name can)", APP)
        other = [w for w in (shutil.which("python"), shutil.which("python3")) if w and os.path.normcase(w) != os.path.normcase(EXE)]
        ok(not other, "no other Python is on the PATH", other)
        p = os.path.join(APP, "PASTE_TO_YOUR_HELPER.txt")
        said = open(p, encoding="utf-8-sig").read() if os.path.isfile(p) else ""
        ok(EXE in said and os.path.join(APP, "fg", "setup.py") in said, "the sentence for the helper names this Python and the kit's setup by full path", said)
    top = tempfile.mkdtemp(prefix="fg download ")
    r = project(top)
    code, out = run([EXE, os.path.join(APP, "fg", "setup.py"), "--solo", "--allow-routine"], r)
    if not ok(code == 0 and "all your tests pass" in out, "setup ran on the download's Python and the project's tests pass", out):
        print("FoundationGuard download check: setup FAILED, so nothing after it was checked."); return 1
    cmds = hook_commands(r)
    ok(cmds and all(c.startswith(FWD + " -I ") for _, c in cmds), f"all {len(cmds)} hooks of the AI tool call this Python by its full path", [c for _, c in cmds if not c.startswith(FWD)][:3])
    code, hook = run(["git", "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-push"], r)
    text = open(hook.strip(), encoding="utf-8", errors="replace").read() if code == 0 and os.path.isfile(hook.strip()) else ""
    ok(FWD in text, "git's pre-push hook calls it by its full path", text)
    cfg = json.load(open(os.path.join(r, "foundationguard.json"), encoding="utf-8-sig"))
    ok(FWD in str(cfg.get("gate_command")), "the gate's test command calls it by its full path", cfg.get("gate_command"))
    code, out = run([EXE, "-I", os.path.join("fg", "guard.py"), "--check", "-"], r, text_in='bash -c "git push --force"\n')
    ok("BLOCK" in out, "a piped force push prints BLOCK", out)
    pre = [c for ev, c in cmds if ev == "PreToolUse" and "guard.py" in c][:1]
    if ok(pre, "the AI tool has a guard hook before each step"):
        ask = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push --force"}, "cwd": r})
        env = {"CLAUDE_PROJECT_DIR": r.replace("\\", "/")}
        code, out = run([bash(), "-c", pre[0]], r, text_in=ask, env=env)
        ok(code == 2 and "blocked" in out, "that hook, run as the AI tool runs it (Git's bash), refuses a force push", f"exit {code}\n{out}")
    run(["git", "add", "-A"], r); run(["git", "commit", "-qm", "set up FoundationGuard"], r)
    code, out = run([EXE, "-I", os.path.join("fg", "push.py")], r)
    ok(code == 0 and "UPLOADED" in out, "the gate passes and the upload goes through git's pre-push hook", out)
    code, out = run([EXE, "-I", os.path.join("fg", "doctor.py")], r)
    ok("Kit's Python: the safety checks call the kit's own Python, and it is there" in out, "the check-up says the kit's own Python is there", out)
    shutil.rmtree(top, ignore_errors=True)
    print(f"FoundationGuard download check: {'every line is ok' if not FAILS else str(len(FAILS)) + ' line(s) FAILED'}.")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

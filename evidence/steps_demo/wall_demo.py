"""Worked example for evidence/results/RESULTS_v0.8.5.md (AI-made, Claude, 2026-11-11): a toy project with six test steps, three of which
break in one day's work. Counts how many steps run until the work passes: (a) one command that stops at the first
failure and starts again from the top, (b) the step-by-step gate. Each step sleeps 1 second and stands for a long test."""
import json, os, subprocess, sys, time
FG, W = sys.argv[1], sys.argv[2]
PY = sys.executable
NAMES = ["build", "saves", "world", "people", "weather", "sound"]
def sh(cmd, cwd):
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
def commit(r, m):
    sh(f"git add -A && git -c user.email=t@t -c user.name=t commit -qm {m}", r)
def make(tag, cfg_extra):
    r = os.path.join(W, tag); os.makedirs(r); sh(f"git init -q --bare {r}.git && git init -q -b feature/x .", r)
    open(os.path.join(W, "step.py"), "w").write("import os,sys,time\nn=sys.argv[1]\nopen('count_'+n,'a').write('x\\n')\ntime.sleep(1)\nsys.exit(1 if 'BAD' in open('src/%s/x.txt' % n).read() else 0)\n")
    cfg = {"check_command": "true"}; cfg.update(cfg_extra)
    json.dump(cfg, open(os.path.join(r, "foundationguard.json"), "w"))
    open(os.path.join(r, "APPROVED.md"), "w").write("| ID | Behaviour | Words | Check | Break |\n|---|---|---|---|---|\n")
    open(os.path.join(r, ".gitignore"), "w").write(".foundationguard/\ncount_*\n")
    for n in NAMES:
        os.makedirs(os.path.join(r, "src", n)); open(os.path.join(r, "src", n, "x.txt"), "w").write("ok\n")
    sh(f"git remote add origin {r}.git", r); commit(r, "start")
    return r
def ran(r):
    return sum(len(open(os.path.join(r, f)).read().splitlines()) for f in os.listdir(r) if f.startswith("count_"))
def setfile(r, n, text):
    open(os.path.join(r, "src", n, "x.txt"), "w").write(text)
def gate(r, flags=""):
    t = time.time(); p = sh(f"{PY} {FG}/push.py --gate {flags}", r); return p.returncode, time.time() - t, p.stdout
step = lambda n: f"{PY} {W}/step.py {n}"
out = {}
# (a) one command: the six steps chained with &&, so it stops at the first failure
r = make("one", {"gate_command": " && ".join(step(n) for n in NAMES)})
assert gate(r)[0] == 0; base = ran(r)                               # last night's pass
for n in ("saves", "people", "sound"): setfile(r, n, "BAD\n")       # today's work breaks three areas
commit(r, "today"); runs = 0; secs = 0.0
for fix in ("saves", "people", "sound", None):
    code, t, _ = gate(r); runs += 1; secs += t
    if code == 0: break
    setfile(r, fix, "ok, fixed\n"); commit(r, "fix_" + fix)         # the only failure it could see
out["one command"] = {"gate runs": runs, "step runs": ran(r) - base, "seconds": round(secs, 1)}
# (b) steps
r = make("steps", {"gate_steps": [{"name": n, "command": step(n), "guards": [f"src/{n}/**"]} for n in NAMES]})
code, t, o = gate(r); assert code == 0 and "whole run" in o; base = ran(r)
for n in ("saves", "people", "sound"): setfile(r, n, "BAD\n")
commit(r, "today"); runs = 0; secs = 0.0
code, t, o = gate(r); runs += 1; secs += t; assert code == 1 and "missed 3 of 6 steps: saves, people, sound" in o, o
first = o.split("=====")[0]
for n in ("saves", "people", "sound"): setfile(r, n, "ok, fixed\n")
commit(r, "fix_all")
code, t, o2 = gate(r); runs += 1; secs += t; assert code == 0, o2
out["steps"] = {"gate runs": runs, "step runs": ran(r) - base, "seconds": round(secs, 1)}
code, t, o3 = gate(r, "--whole"); assert code == 0 and "this counts as a whole run" in o3
out["nightly whole run afterwards"] = {"step runs": 6, "seconds": round(t, 1)}
print(json.dumps(out, indent=1)); print("--- first step-by-step report ---\n" + first.strip()); print("--- second ---\n" + o2.split("=====")[0].strip()[:900])

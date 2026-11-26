"""Harness for pass lines M4 to M7 of the logic check on the small fixture project (AI-made, Claude, 2026-11-11).
M4 the project is byte for byte the same after a normal run, a run killed half way and a run with hanging changes;
M5 a hang is stopped, counted as noticed, and the run goes on; M6 the same commit gives the same report twice;
M7 the limit holds and the lines left out are counted. Usage: m4567.py FIXTURE_PROJECT LOGIC.py"""
import hashlib, json, os, signal, subprocess, sys, tempfile, time

proj, logic = sys.argv[1], sys.argv[2]
PY = sys.executable


def hashes():
    out = {}
    for dp, _, fs in os.walk(proj):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, proj)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def run(args, js):
    p = subprocess.run([PY, logic] + args + ["--json", js], cwd=proj, capture_output=True, text=True)
    return p, (json.load(open(js)) if os.path.exists(js) else None)


def line(name, ok, note=""):
    print("%s: %s %s" % (name, "PASS" if ok else "FAIL", note), flush=True)


tmp = tempfile.mkdtemp(prefix="fg-m4567-")
before = hashes()
p, res = run(["--files", "calc.py"], os.path.join(tmp, "a.json"))
line("M4a_normal_run_leaves_the_project_alone", hashes() == before and p.returncode == 0, "(%d files, .git included; %d changes tried)" % (len(before), len(res["tried"])))

q = subprocess.Popen([PY, logic, "--files", "calc.py", "--json", os.path.join(tmp, "k.json")], cwd=proj, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(3.0)
alive = q.poll() is None
os.kill(q.pid, signal.SIGKILL); q.wait()
time.sleep(4.0)                                           # let the orphaned test run end
line("M4b_killed_half_way_leaves_the_project_alone", alive and hashes() == before, "(the run was still going when it was killed: %s)" % alive)

p, res = run(["--files", "calc.py:19-22"], os.path.join(tmp, "h.json"))
hang = [t for t in res["tried"] if t["how"].startswith("timeout")]
line("M4c_hanging_changes_leave_the_project_alone", hashes() == before)
line("M5_hang_stopped_counted_noticed_run_goes_on", len(hang) == 2 and all(t["result"] == "noticed" for t in hang) and len(res["tried"]) == 3,   # 3 since Amendment 2: the bare start value "i = 0" is no longer changed (4 before)
     "(%d hanging changes, each stopped after %s s; %d changes tried in all)" % (len(hang), ", ".join(str(t["seconds"]) for t in hang), len(res["tried"])))

_, r1 = run(["--files", "calc.py", "--max", "4"], os.path.join(tmp, "s1.json"))
_, r2 = run(["--files", "calc.py", "--max", "4"], os.path.join(tmp, "s2.json"))
key = lambda r: [(t["path"], t["line"], t["old"], t["new"], t["result"]) for t in r["tried"]]
line("M6_same_commit_same_report", key(r1) == key(r2) and len(key(r1)) == 4, "(%s)" % "; ".join("%d %s %s" % (k[1], k[2], k[4]) for k in key(r1)))
tried_lines = len({(t["path"], t["line"]) for t in r1["tried"]})
line("M7_limit_holds_and_left_out_lines_are_counted", len(r1["tried"]) <= 4 and tried_lines + r1["left_out_by_limit"] + r1["nothing_to_change"] == r1["changed_lines"],
     "(limit 4: %d changes on %d lines; %d lines left out; %d with nothing to change; %d lines in all)"
     % (len(r1["tried"]), tried_lines, r1["left_out_by_limit"], r1["nothing_to_change"], r1["changed_lines"]))
left = [d for d in os.listdir(tempfile.gettempdir()) if d.startswith("fg-logic-")]
print("copies left in the temporary folder (the killed run's own copy is expected; running jobs have theirs): %d" % len(left))

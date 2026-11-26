"""Harness for pass line M2 of the logic check (AI-made, Claude, 2026-11-11): are the tool's verdicts true?
Draws N of the tool's tried changes with a fixed seed and replays each one WITHOUT the tool's code: a fresh copy of the
project's tracked files, the same text change made by hand, the same test commands. Prints both verdicts.
Amendment 1: three verdicts. When nothing notices the change, the replay fills the place with its own filler text
(not the tool's) in another fresh copy; if the commands pass even then, its verdict is "not built".
Usage: replay.py PROJECT OUT.json N SEED TIMEOUT RESULTS.json [RESULTS2.json ...] -- CMD [CMD ...]"""
import json, os, random, shutil, signal, subprocess, sys, tempfile, time

args = sys.argv[1:]
cut = args.index("--")
project, out, n, seed, timeout = args[0], args[1], int(args[2]), int(args[3]), float(args[4])
results, cmds = args[5:cut], args[cut + 1:]
tried = []
for r in results:
    tried += json.load(open(r))["tried"]
tried.sort(key=lambda t: (t["path"], t["line"], t["start"], t["new"]))
sample = random.Random(seed).sample(tried, min(n, len(tried)))
part, parts = [int(x) for x in os.environ.get("SHARD", "0/1").split("/")]     # SHARD=i/k: every k-th of the same draw
sample = sample[part::parts]
if os.environ.get("ONLY"):                                 # ONLY=path: of the same draw, the changes in one file (its own test command)
    sample = [t for t in sample if t["path"] == os.environ["ONLY"]]
names = subprocess.run(["git", "ls-files", "-z"], cwd=project, capture_output=True, text=True).stdout.split("\0")
rows = []
FILLER = "@@ this is not code $$ ((("


def outcome(t, new):
    """A fresh copy with `new` in the place of the change; 'pass' when every command passes."""
    work = tempfile.mkdtemp(prefix="fg-replay-")
    try:
        for name in [x for x in names if x]:
            os.makedirs(os.path.dirname(os.path.join(work, name)) or work, exist_ok=True)
            shutil.copy2(os.path.join(project, name), os.path.join(work, name))
        full = os.path.join(work, t["path"])
        with open(full, encoding="utf-8", errors="surrogateescape", newline="") as f:
            lines = f.read().split("\n")
        line = lines[t["line"] - 1]
        assert line[t["start"]:t["end"]] == t["old"], ("the recorded change does not fit the file", t)
        lines[t["line"] - 1] = line[:t["start"]] + new + line[t["end"]:]
        with open(full, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
            f.write("\n".join(lines))
        for c in cmds:
            p = subprocess.Popen(c, shell=True, cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            try:
                if p.wait(timeout=timeout) != 0:
                    return "fail"
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL); p.wait()
                return "fail"
        return "pass"
    finally:
        shutil.rmtree(work, ignore_errors=True)


for t in sample:
    t0 = time.time()
    verdict = "noticed" if outcome(t, t["new"]) == "fail" else "not noticed"
    if verdict == "not noticed" and outcome(t, FILLER) == "pass":
        verdict = "not built"
    rows.append({"path": t["path"], "line": t["line"], "old": t["old"], "new": t["new"], "tool": t["result"], "replay": verdict,
                 "seconds": round(time.time() - t0, 1)})
    print("%-9s %-11s %-11s %s:%d '%s' -> '%s'" % ("MATCH" if verdict == t["result"] else "DIFFER", t["result"], verdict,
                                                  t["path"], t["line"], t["old"], t["new"]), flush=True)
same = sum(1 for r in rows if r["tool"] == r["replay"])
print("REPLAY %d of %d verdicts match (seed %d, drawn from %d tried changes)" % (same, len(rows), seed, len(tried)))
json.dump({"seed": seed, "drawn_from": len(tried), "match": same, "rows": rows}, open(out, "w"), indent=1)

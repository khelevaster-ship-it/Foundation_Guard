"""Structure-check competitor test, re-run 10 Nov 2026 with the REAL lizard (AI-made, Claude). Same seed and cases as 2026-11-08. Pass lines: structure_test/PASSLINES.md.
python st_test.py FG_DIR WORK_DIR OUT.json"""
import json, os, random, re, shutil, subprocess, sys
from pathlib import Path
FG, WORK, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()   # (fixed: a relative FG path broke when each case ran in its own folder)
SEED = 20261108
LIM = {"max_file_lines": 1500, "max_class_lines": 1000, "max_class_files": 4, "max_growth_lines": 400}
FUNC_LIM, METHODS_LIM, CCN_LIM = 300, 35, 15
rng = random.Random(SEED)

def body(n):
    st = ["x += %d;", "Foo(a, %d);", "if (a > %d) { b++; }", "total = total * %d;", 'Log("step {%d}");', "// note %d about } braces {"]
    return ["    " + rng.choice(st) % rng.randint(1, 99) for _ in range(n)]
def fn(name, n, owner=None, ind=""):
    head = f"void {owner + '::' if owner else ''}{name}(int a)"
    return [ind + head, ind + "{"] + [ind + l for l in body(max(1, n - 3))] + [ind + "}"]
def cs_partial(cls, nlines):
    out, k = ["public partial class " + cls, "{"], 0
    while len(out) < nlines - 1:
        k += 1; out += fn(f"M{rng.randint(0, 10**6)}", rng.randint(20, 60), ind="    ")
    return out + ["}"]
def cpp_members(cls, nlines):
    out = [f'#include "{cls}.h"', ""]
    while len(out) < nlines:
        out += fn(f"M{rng.randint(0, 10**6)}", rng.randint(20, 60), owner=cls) + [""]
    return out
def free_fns(nlines, lo=20, hi=60):
    out = ['#include "Common.h"', ""]
    while len(out) < nlines:
        out += fn(f"F{rng.randint(0, 10**6)}", rng.randint(lo, hi)) + [""]
    return out

def case(kind, i):
    files, cfg, grow = {}, {"include": ["**/*.cs", "**/*.cpp", "**/*.h"], **LIM}, None
    name = f"C{kind}{i}"
    if kind == "P1":
        n = rng.randint(1100, 3000)
        if rng.random() < .5: files[f"{name}.cs"] = cs_partial(name, n)
        else:
            files[f"{name}.h"] = [f"class GAME_API {name}", "{", "public:", "    void Tick();", "};"]
            files[f"{name}.cpp"] = cpp_members(name, n)
    elif kind == "P2":
        for j in range(rng.randint(5, 12)): files[f"{name}.Part{j}.cs"] = cs_partial(name, rng.randint(60, 180))
    elif kind == "P3":
        files[f"{name}.h"] = [f"class GAME_API {name}", "{", "public:", "    void Tick();", "};"]
        for j in range(rng.randint(5, 12)): files[f"{name}_{j}.cpp"] = cpp_members(name, rng.randint(60, 180))
    elif kind == "P4":
        files[f"Big{i}.cpp"] = free_fns(rng.randint(1600, 2500)); grow = (f"Big{i}.cpp", rng.randint(20, 200))
    elif kind == "P5":
        files["Weather/Rain.cpp"] = ['#include "Water/Public/WaterAPI.h"', f'#include "Water/Private/{rng.choice(["Flow", "Basin", "Tide"])}.h"', ""] + free_fns(rng.randint(50, 400))
        cfg["boundaries"] = [{"files": "Weather/**", "may_not_use": ["Water/Private/"], "why": "via WaterAPI.h"}]
    elif kind == "P6":
        big = fn("Huge", rng.randint(350, 900)); rest = free_fns(rng.randint(100, 500))
        files[f"F{i}.cpp"] = rest + [""] + big
    else:  # clean
        c = rng.choice(["split", "bigfile", "strings", "public", "cppclass"])
        if c == "split":
            for j in range(rng.randint(2, 3)): files[f"{name}.Part{j}.cs"] = cs_partial(name, rng.randint(100, 300))
        elif c == "bigfile": files[f"Mid{i}.cpp"] = free_fns(rng.randint(800, 1440))
        elif c == "strings": files[f"{name}.cs"] = cs_partial(name, rng.randint(200, 800))
        elif c == "public":
            files["Weather/Rain.cpp"] = ['#include "Water/Public/WaterAPI.h"', ""] + free_fns(rng.randint(50, 400))
            cfg["boundaries"] = [{"files": "Weather/**", "may_not_use": ["Water/Private/"], "why": "via WaterAPI.h"}]
        else:
            files[f"{name}.h"] = [f"class GAME_API {name}", "{", "public:", "    void Tick();", "};"]
            files[f"{name}.cpp"] = cpp_members(name, rng.randint(200, 900))
        kind = "clean:" + c
    return kind, files, cfg, grow

def git(cwd, *a): return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
def build(d, files, cfg, grow):
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True); git(d, "init", "-q")
    for p, lines in files.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True); (d / p).write_text("\n".join(lines) + "\n")
    (d / "foundationguard.json").write_text(json.dumps({"structure": cfg}))
    git(d, "add", "-A"); git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")
    if grow:
        subprocess.run([sys.executable, str(FG / "fg/structure.py"), "--baseline"], cwd=d, capture_output=True)
        p, n = grow; (d / p).write_text((d / p).read_text() + "\n".join(fn("Extra", n)) + "\n")
        git(d, "add", "-A"); git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "grow")

def ours(d): return subprocess.run([sys.executable, str(FG / "fg/structure.py")], cwd=d, capture_output=True, text=True).returncode == 1

FN = re.compile(r"^\s*(?:[\w:<>*&~]+\s+)+([\w:~]+)\s*\([^;]*\)\s*(?:const)?\s*$")
def functions(lines):
    """[(name, length, ccn)] per function, the way per-function tools read them."""
    out, i = [], 0
    while i < len(lines) - 1:
        m = FN.match(lines[i])
        if m and lines[i + 1].strip() == "{":
            depth, j = 0, i + 1
            while j < len(lines):
                s = re.sub(r'"[^"]*"|//.*', "", lines[j]); depth += s.count("{") - s.count("}")
                if depth <= 0: break
                j += 1
            seg = lines[i:j + 1]; ccn = 1 + sum(len(re.findall(r"\b(if|for|while|case|catch)\b|&&|\|\|", re.sub(r'"[^"]*"|//.*', "", l))) for l in seg)
            out.append((m.group(1), j - i + 1, ccn)); i = j + 1
        else: i += 1
    return out
LIZ = os.environ["LIZARD_BIN"]
def rivals(d):
    """The REAL lizard 1.17.13, run on the case folder with the same limits: function length (-L) and complexity (-C)."""
    p = subprocess.run([LIZ, "-L", str(FUNC_LIM), "-C", str(CCN_LIM), "-w", "-l", "cpp", "-l", "csharp", "."], cwd=d, capture_output=True, text=True)
    warned = any("warning:" in l for l in p.stdout.splitlines())
    return {"lizard_real": warned}

res = []
kinds = [f"P{k}" for k in range(1, 7) for _ in range(20)] + ["clean"] * 60
for i, k in enumerate(kinds):
    kind, files, cfg, grow = case(k, i); d = WORK / f"c{i:03d}"; build(d, files, cfg, grow)
    r = {"case": i, "kind": kind, "ours": ours(d), **rivals(d)}; res.append(r)
tools = ["ours", "lizard_real"]
summ = {}
for t in tools:
    row = {f"P{k}": sum(r[t] for r in res if r["kind"] == f"P{k}") for k in range(1, 7)}
    row["P1-P5"] = sum(row[f"P{k}"] for k in range(1, 6)); row["P1-P6"] = row["P1-P5"] + row["P6"]
    row["clean_false_alarms"] = sum(r[t] for r in res if r["kind"].startswith("clean"))
    summ[t] = row; print(t, row)
fa = [r for r in res if r["kind"].startswith("clean") and r["ours"]]
print("our false alarms:", [(r["case"], r["kind"]) for r in fa])
o = summ["ours"]
summ["line1"] = o["P1-P5"] >= 90 and o["clean_false_alarms"] <= 3
summ["line2"] = all(o["P1-P6"] > summ[t]["P1-P6"] for t in tools[1:])
print("line1", summ["line1"], "line2", summ["line2"])
OUT.write_text(json.dumps({"seed": SEED, "summary": summ, "cases": res}, indent=1))

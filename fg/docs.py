"""FoundationGuard docs pack (AI-made, Claude, 2026-11-09).

The project's architecture docs are how every new AI session (and every new person) learns the project. They rot quietly.
  python fg/docs.py                     check: docs tell the truth and keep up with the code (the push gate runs this)
  python fg/docs.py --starter           write starter ARCHITECTURE.md, HANDOFF.md, REJECTED.md (never overwrites)
        [--what "..."] [--parts "a, b"] [--never "x; y"] [--rules "..."]   the owner's plain answers, if you have them
  python fg/docs.py --baseline "owner's words"   accept today's undocumented items as old debt (guarded)
  python fg/docs.py --core              print the core of the docs (the session-start hook runs this)

Truth: in the docs, every `backticked` file path must exist; every backticked switch name (settings key `switch_pattern`)
must exist in the code; every number claim written `name` = N, `name`: N or `name` is N must equal what the code or
settings give that name. Claims about names the code never defines are left alone. Fenced code blocks are skipped.
Keeping up: ARCHITECTURE.md must name every system (each top-level folder with code under a source root), every
dependency the rule check lists, and every switch in the code. Day-one gaps are recorded (docs_baseline.json) and may only
shrink. A push with a revert commit must touch REJECTED.md. A push that changes code but not HANDOFF.md warns
(`handoff_required`: true makes it fail).
"""
import datetime, fnmatch, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

CODE_EXT = (".cpp", ".h", ".hpp", ".c", ".cc", ".cs", ".py", ".gd", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".rs", ".go", ".java", ".kt",
            ".swift", ".lua", ".m", ".mm", ".inl", ".ipp", ".hlsl", ".usf", ".ush", ".shader", ".gdshader")
SETTINGS_EXT = (".json", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".godot", ".uproject", ".uplugin", ".asset", ".tres", ".tscn", ".xml")
FILE_EXT = re.compile(r"\.(?:cpp|h|hpp|c|cc|cs|py|gd|js|ts|tsx|jsx|rs|go|java|kt|lua|inl|hlsl|usf|ush|shader|gdshader|json|ini|cfg|toml|"
                      r"ya?ml|xml|md|txt|csv|tsv|log|bat|cmd|ps1|sh|uasset|umap|uproject|uplugin|godot|tscn|tres|asset|prefab|unity|"
                      r"png|jpe?g|webp|exr|tga|psd|wav|ogg|mp3|fbx|glb|gltf|obj|ttf|otf|zip|patch|lock|html|css|sln|csproj|asmdef)$", re.I)
# default feature switches: names read from environment settings (os.environ.get("X"), getenv("X"), GetEnvironmentVariable("X"), OS.get_environment("X"))
ENV_SWITCH = r"(?:environ\.get|getenv|environ\[|GetEnvironmentVariable|get_environment|has_environment|process\.env\.?)\(?\[?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)"
DEFAULT_DOCS = ["ARCHITECTURE.md", "HANDOFF.md", "REJECTED.md", "README.md", "docs/**/*.md", "Docs/**/*.md"]


def strip_fences(text):
    out, fence = [], False
    for l in text.split("\n"):
        if re.match(r"^\s*(```|~~~)", l):
            fence = not fence; out.append(""); continue
        out.append("" if fence else l)
    return out


def code_files(repo):
    return {p: t for p, t in repo.items() if not p.lower().endswith(".md")}


def looks_path(tok):
    if not BREAK("docs_real1") and (re.match(r"^(?:[A-Za-z]:[\\/]|~|%\w+%|\\\\|\$\w+)", tok) or re.fullmatch(r"\.[A-Za-z0-9]{1,8}", tok)):
        return False                      # a path on someone's own machine (C:\..., ~/...) or a bare file type (.json)
    if " " in tok.strip() or tok.startswith(("-", "$", "http://", "https://", "#")) or "://" in tok:
        return False
    if re.search(r"[(){}<>=*?|;,]", tok):
        return False
    return "/" in tok or "\\" in tok or bool(FILE_EXT.search(tok)) and not re.fullmatch(r"\d+(\.\d+)+", tok) \
        and not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*\(?\)?", tok) or tok.endswith("/")


def _unreal_path(t, repo):
    """(True, token) for an Unreal object path that is not a file to look for, (False, token) otherwise."""
    if t.startswith(("/Script/", "/Engine/")) or re.match(r"^/\w+/", t) and not t.startswith("/Game/"):
        return True, t                    # an Unreal object path, not a file
    if t.startswith("/Game/"):
        t = "Content/" + t[6:]            # Unreal's /Game/ is the Content folder
        return any(p.startswith(t) for p in repo), t
    return False, t


def _not_a_file(t, repo, ignored):
    """Patterns, Unreal object paths and run-time files: (True, None) when the token is not a project file to look for,
    else (False, the token to look for)."""
    if "..." in t or "*" in t or "<" in t:
        return True, t                    # a pattern or a shortened path, not a real one
    m = re.match(r"^(.*?\.\w+)/\.\w+$", t)
    if m:
        t = m.group(1)                    # "Tide.h/.cpp" means Tide.h and Tide.cpp
    skip, t = _unreal_path(t, repo)
    if skip:
        return True, t
    if ignored and ignored(t):
        return True, t                    # a file made while running (git ignores it), like Saved/x.log
    return False, t

def _exact(t, repo):
    while t.startswith("./"):
        t = t[2:]
    t = t.lstrip("/")
    d = t.rstrip("/") + "/"
    return t, (not t or t in repo or any(p.startswith(d) for p in repo))


def _ref_name(t, repo, branches):
    """A git branch, or a name without an extension whose first folder is nowhere in the project."""
    if t.rstrip("/") in branches:
        return True                       # a git branch name (wt/feature), not a file
    first = t.split("/", 1)[0]
    in_repo = any(p == first or p.startswith(first + "/") or ("/" + first + "/") in ("/" + p) for p in repo)
    return not FILE_EXT.search(t.rstrip("/")) and not in_repo


def _loose(tok, t, repo):
    """Named by its file name alone, without its extension, or relative to a module folder."""
    u, d = t.rstrip("/"), t.rstrip("/") + "/"
    if not BREAK("docs_real2") and any(p.endswith("/" + u) or p.startswith(u + ".") or ("/" + u + ".") in ("/" + p) for p in repo):
        return True                       # Core/Water/WaterEdits for Core/Water/WaterEdits.h
    if tok.rstrip().endswith("/") and any(("/" + d) in ("/" + p) for p in repo):
        return True                       # a folder written relative to a module folder (Core/)
    if "/" in u:                          # Private/World/X.cpp under Source/MyGame/
        return any(p.endswith("/" + u) or ("/" + d) in ("/" + p) for p in repo)
    return False


def path_exists(tok, repo, branches=(), ignored=None):
    t = tok.replace("\\", "/").strip()
    if not BREAK("docs_real2"):
        skip, t = _not_a_file(t, repo, ignored)
        if skip:
            return True
    t, found = _exact(t, repo)
    if found:
        return True
    if BREAK("docs_real1"):
        return False
    return _ref_name(t, repo, branches) or _loose(tok, t, repo)


def _number_claims(d, i, line, code, out):
    """`name` = N claims in one doc line. Returns the names claimed."""
    claimed = set()
    if BREAK("docs_numbers"):
        return claimed
    for m in CLAIM.finditer(line):
        name, num = m.group(1), float(m.group(2).replace(",", ""))
        vals = defined_values(name, code)
        claimed.add(name)
        if vals and num not in vals:
            out.append((d, i, name, "number", f"the docs say {m.group(2)}, the code says {', '.join(f'{v:g}' for v in sorted(vals))}"))
    return claimed


class _TruthCtx:
    def __init__(self, repo, switch_pattern, branches, ignored):
        self.repo, self.branches, self.ignored = repo, branches, ignored
        self.code = code_files(repo)
        self.sw = re.compile(switch_pattern) if switch_pattern else None
        self.known = switches(repo, switch_pattern) if self.sw is not None and self.sw.groups else None

    def switch_missing(self, tok):
        return not BREAK("docs_switch") and not any(re.search(r"(?<![\w.])" + re.escape(tok) + r"(?![\w])", t) for t in self.code.values())


def _token(x, d, i, tok, claimed, out):
    """One `backticked` token: a switch, a claimed name or a path."""
    if x.known is not None and tok in x.known:
        return
    if x.known is None and x.sw and x.sw.fullmatch(tok):
        if x.switch_missing(tok):
            out.append((d, i, tok, "switch", "no such switch in the code"))
        return
    if tok in claimed or not looks_path(tok) or path_exists(tok, x.repo, x.branches, x.ignored):
        return
    if not BREAK("docs_paths"):
        out.append((d, i, tok, "path", "no such file or folder"))


def truth(repo, docs, switch_pattern=None, branches=(), ignored=None):
    """Problems [(doc, line no, token, kind, why)] in the docs at paths `docs` of the dict repo {path: text}."""
    if BREAK("docs_truth"):
        return []
    x = _TruthCtx(repo, switch_pattern, branches, ignored)
    out = []
    for d in (d for d in docs if d in repo):
        for i, line in enumerate(strip_fences(repo[d]), 1):
            claimed = _number_claims(d, i, line, x.code, out)
            for m in re.finditer(r"`([^`\n]+)`", line):
                _token(x, d, i, m.group(1).strip(), claimed, out)
    return out

def defined_values(name, files):
    """Numbers the code or settings give `name` (a set; empty = never defined)."""
    n = re.escape(name)
    pats = [rf"(?<![\w.]){n}\s*(?::=|=|:)\s*(-?\d+(?:\.\d+)?)",
            rf"[\"']{n}[\"']\s*:\s*(-?\d+(?:\.\d+)?)",
            rf"#define\s+{n}\s+\(?(-?\d+(?:\.\d+)?)",
            rf"TEXT\(\s*\"{n}\"\s*\)\s*,\s*(-?\d+(?:\.\d+)?)",
            rf"\(\s*[\"']{n}[\"']\s*,\s*(-?\d+(?:\.\d+)?)"]
    vals = set()
    for t in files.values():
        for p in pats:
            for m in re.finditer(p, t):
                vals.add(float(m.group(1)))
    return vals


CLAIM = re.compile(r"`([A-Za-z_][\w.:\-]*)`\s*(?:=|:|\bis\b|\bof\b|\bat\b)\s*(-?\d[\d,]*(?:\.\d+)?)")


def systems(repo, roots):
    out = set()
    for r in roots:
        r = r.strip("/") + "/"
        for p in repo:
            if p.startswith(r) and p.lower().endswith(CODE_EXT):
                rest = p[len(r):]
                if "/" in rest:
                    out.add(rest.split("/", 1)[0])
    return out


def switches(repo, switch_pattern):
    if not switch_pattern:
        return set()
    rx = re.compile(switch_pattern)
    out = set()
    for p, t in code_files(repo).items():
        if p.startswith("fg/"):
            continue                                     # the kit's own break switches aren't the project's
        for m in rx.finditer(t):
            if rx.groups:
                out.add(m.group(1))
            elif _quoted(t, m):
                out.add(m.group(0))
    return out


def _quoted(t, m):
    """Game build, 13 Nov: with the pattern my\\.\\w+, ordinary code (my.kind, my.value) was taken for switches. A switch
    is defined by its name in quotes (a console variable, a setting's key), so a pattern without a group counts only a
    name that starts in quotes. A pattern with a group decides for itself."""
    return BREAK("docs_switch_anywhere") or (m.start() > 0 and t[m.start() - 1] in "\"'`")


def mentioned(name, text):
    return re.search(r"(?<![\w.])" + re.escape(name) + r"(?![\w])", text) is not None


def coverage(repo, arch_text, roots, deps, switch_pattern=None, baseline=()):
    """Undocumented items [(kind, name)], leaving out baseline debt."""
    if BREAK("docs_coverage"):
        return []
    base = set(baseline); out = []
    items = [("system", s) for s in sorted(systems(repo, roots))] + [("dependency", d) for d in sorted(set(deps))] + \
            [("switch", s) for s in sorted(switches(repo, switch_pattern))]
    text = (arch_text or "") if not BREAK("docs_fence_cov") else "\n".join(strip_fences(arch_text or ""))
    for kind, name in items:
        if name in base:
            continue
        if not mentioned(name, text):
            out.append((kind, name))
    return out


# ---------------- the repository side ----------------

def git(root, *a):
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")


def read_repo(root):
    out = {}
    listed = git(root, "ls-files").stdout.splitlines()
    if not BREAK("docs_untracked"):
        listed += git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()   # new docs not committed yet
    for p in listed:
        if p.lower().endswith(CODE_EXT + SETTINGS_EXT + (".md", ".txt")) or "." not in os.path.basename(p):
            try:
                out[p] = open(os.path.join(root, p), encoding="utf-8", errors="replace").read()
            except OSError:
                pass
        else:
            out[p] = ""                                   # binary: exists, no text
    return out


def branch_names(root):
    out = set()
    for l in git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes").stdout.splitlines():
        out.add(l); out.add(l.split("/", 1)[1] if l.count("/") >= 1 and l.startswith(("origin/",)) else l)
    return out


class _Ignored:
    """git check-ignore for one project, remembered per path."""
    def __init__(self, root):
        self.root, self.cache = root, {}

    def __call__(self, path):
        if path not in self.cache:
            quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            r = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=self.root, **quiet)
            self.cache[path] = r.returncode == 0
        return self.cache[path]


def ignored_fn(root):
    return _Ignored(root)


def _first_record(cfg, miss, wrong, warn):
    json.dump({"undocumented": [n for _, n in miss], "untrue": sorted({f"{w[0]}|{w[2]}" for w in wrong}),
               "recorded": str(datetime.date.today()), "why": "first record"}, open(bpath(cfg), "w"), indent=1)
    import steps as SP                                 # 12 Nov: the check after the step keeps the kit's first record
    SP.recorded(cfg, [bpath(cfg)])
    warn.append(f"first record: {len(miss)} thing(s) the docs don't mention and {len(wrong)} untrue line(s) are old debt "
                "(docs_baseline.json); new ones must be fixed")


def _push_rules(cfg, d, repo, bad, warn):
    """A revert must update REJECTED; code changes should update HANDOFF."""
    rng = push_range(cfg)
    if not rng or BREAK("docs_push_rules"):
        return
    root = cfg["_root"]
    log = git(root, "log", "--format=%s", rng).stdout
    changed = [f for f in git(root, "diff", "--name-only", rng).stdout.splitlines() if f]
    if re.search(r"(?im)^revert\b", log) and d["rejected"] not in changed:
        bad.append(f"this push undoes something (a revert) but {d['rejected']} wasn't updated: write down what was tried and why it was dropped")
    code_changed = any(f.lower().endswith(CODE_EXT) for f in changed)
    if code_changed and d["handoff"] not in changed and d["handoff"] in repo:
        (bad if d.get("handoff_required") else warn).append(f"code changed but {d['handoff']} didn't: say what changed and what's next")


def _report(bad, warn):
    head = f"DOCS {'ok' if not bad else 'FAIL'}: {len(bad)} problem(s)"
    body = "" if not bad else ":\n  " + "\n  ".join(bad[:40])
    notes = "" if not warn else "\n  note: " + "\n  note: ".join(warn)
    return head + body + notes


def check(cfg):
    root = cfg["_root"]; d = dcfg(cfg)
    repo = read_repo(root)
    arch = d["architecture"]
    if arch not in repo:
        return True, f"DOCS no {arch} yet (run  python fg/docs.py --starter  to write starter docs)"
    bad, warn = [], []
    base = load_baseline(cfg); old_untrue = set(load_baseline(cfg, "untrue") or [])
    wrong = truth(repo, doc_list(repo, d), d.get("switch_pattern"), branch_names(root), ignored_fn(root))
    cov_text = "\n".join(repo.get(x, "") for x in d["coverage_in"])
    miss = coverage(repo, cov_text, d["source_roots"], dependencies(cfg), d.get("switch_pattern"), base or [])
    if base is None:
        _first_record(cfg, miss, wrong, warn)
        miss, wrong = [], []
    keep_old = not BREAK("docs_baseline")
    bad += [f"{doc}:{i} `{tok}` ({kind}): {why}" for doc, i, tok, kind, why in wrong if not (keep_old and f"{doc}|{tok}" in old_untrue)]
    bad += [f"{arch} doesn't mention the {kind} '{name}': add a line saying what it is and why it exists" for kind, name in miss]
    _push_rules(cfg, d, repo, bad, warn)
    return not bad, _report(bad, warn)


# ---------------- starter docs and the session-start reminder ----------------

YELLOW = "**[to fill in]**"


def _bullets(items, fmt, empty):
    return "\n".join(fmt.format(x) for x in items) or empty


def _part_lines(parts, sy):
    named = [p.strip() for p in (parts.split(",") if parts else []) if p.strip()]
    lines = [f"- **{p}**: {YELLOW} what it does, which folder holds it." for p in named]
    lines += [f"- **{s}**: {YELLOW} what this part does and why it exists." for s in sy if not parts or s not in parts]
    return lines


def _architecture_text(d, today, what, part_lines, never, rules, deps, sw):
    never_lines = [x.strip() for x in never.split(";") if x.strip()] if never else []
    return f"""# Architecture (start here)

*Every new AI session reads this first. Keep it true: a change to a part, a rule, a dependency or a switch updates this file
in the same commit. Written by FoundationGuard setup on {today}; lines marked {YELLOW} are guesses or gaps.*

## What this project is
{what or YELLOW + " one or two sentences, in the owner's words."}

## The parts
{_bullets(part_lines, "{}", "- " + YELLOW + " list the main parts (systems) and what each does.")}

## Rules that must never be broken
{chr(10).join("- " + x for x in never_lines) if never else "- " + YELLOW + " things that must never change (the owner's words)."}

## Conventions
{rules or "- " + YELLOW + " naming, where new files go, how settings and switches are named."}

## Dependencies (plugins, packages, libraries)
{_bullets(deps, "- {}: " + YELLOW + " why it is used.", "- none recorded yet.")}

## Feature switches
{_bullets(sw, "- `{}`: " + YELLOW + " what it turns on or off.", "- none found yet.")}

## How changes are checked
- Push only with `python fg/push.py` (tests first, then exactly that version).
- Approved features and their checks: `APPROVED.md`.
- Today's state and next steps: `{d['handoff']}`. Ideas tried and dropped: `{d['rejected']}`.
"""


def _handoff_text(d, today):
    return f"""# Handoff (today's state)

*Update at every push: what changed, what's next, what to watch. A new session reads this right after {d['architecture']}.*

## State on {today}
- {YELLOW} what works, what is half-done.

## Next steps
1. {YELLOW}

## Watch out for
- {YELLOW}
"""


REJECTED_TEXT = """# Rejected (tried and dropped)

*Every idea that was tried and undone goes here, so nobody tries it again blindly. A push with a revert must add a row.*

| Date | What was tried | Why it was dropped | Undone in |
|---|---|---|---|
"""


def starter(cfg, what=None, parts=None, never=None, rules=None):
    root = cfg["_root"]; d = dcfg(cfg); made = []
    repo = read_repo(root)
    sy = sorted(systems(repo, d["source_roots"]))
    sw = sorted(switches(repo, d.get("switch_pattern")))
    today = datetime.date.today()
    texts = {d["architecture"]: _architecture_text(d, today, what, _part_lines(parts, sy), never, rules, dependencies(cfg), sw),
             d["handoff"]: _handoff_text(d, today), d["rejected"]: REJECTED_TEXT}
    for p, t in texts.items():
        full = os.path.join(root, p)
        if os.path.exists(full):
            continue
        os.makedirs(os.path.dirname(full) or root, exist_ok=True)
        open(full, "w", encoding="utf-8").write(t); made.append(p)
    return made

def dcfg(cfg):
    d = dict(cfg.get("docs") or {})
    d.setdefault("architecture", "ARCHITECTURE.md")
    d.setdefault("handoff", "HANDOFF.md")
    d.setdefault("rejected", "REJECTED.md")
    d.setdefault("files", DEFAULT_DOCS)
    if "source_roots" not in d:
        eng = cfg.get("engine")
        d["source_roots"] = {"unreal": ["Source"], "unity": ["Assets/Scripts", "Assets"], "godot": ["scripts", "src", "."]}.get(eng, ["src", "Source", "lib", "app", "scripts"])
    d.setdefault("switch_pattern", cfg.get("switch_pattern") or (None if BREAK("docs_env_switch") else ENV_SWITCH))
    d.setdefault("coverage_in", [d["architecture"]])     # docs where a name counts as documented (e.g. add a switch list)
    return d


def doc_list(repo, d):
    return sorted(p for p in repo if p.lower().endswith(".md") and any(fnmatch.fnmatch(p, g) or p == g for g in d["files"])
                  and not p.startswith(("fg/", "node_modules/")))


def dependencies(cfg):
    try:
        import rules as RU
        if not cfg.get("rules"):
            return []
        return sorted(k.split(":", 1)[-1] for k in RU.measure(cfg).get("dependencies", {}))
    except Exception:
        return []


def bpath(cfg):
    return os.path.join(cfg["_root"], "docs_baseline.json")


def load_baseline(cfg, key="undocumented"):
    p = bpath(cfg)
    return json.load(open(p, encoding="utf-8-sig")).get(key, []) if os.path.exists(p) else None


def push_range(cfg):
    root = cfg["_root"]
    up = git(root, "rev-parse", "--verify", "-q", "@{upstream}").stdout.strip()
    if up:
        return up + "..HEAD"
    import steps as SP
    last = SP.passed(cfg)                              # review 6: only a pass the kit recorded (F265)
    if last:
        return last + "..HEAD"
    return None


def core(cfg, n=40):
    """The start-of-session reminder: the first lines of each doc, without fences."""
    if BREAK("docs_core"):
        return ""
    root = cfg["_root"]; d = dcfg(cfg); out = []
    for p in (d["architecture"], d["handoff"]):
        full = os.path.join(root, p)
        if os.path.exists(full):
            lines = [l for l in strip_fences(open(full, encoding="utf-8", errors="replace").read()) if l.strip()]
            out.append(f"===== {p} (read this first; keep it true) =====\n" + "\n".join(lines[:n]))
    rj = os.path.join(root, d["rejected"])
    if os.path.exists(rj):
        rows = [l for l in open(rj, encoding="utf-8", errors="replace") if l.startswith("|") and not l.startswith("|---") and "Date" not in l]
        out.append(f"===== {d['rejected']}: {len(rows)} idea(s) already tried and dropped; read it before proposing something big =====")
    return "\n".join(out)


def main(argv):
    import config as C
    cfg = C.load()
    arg = lambda k: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else None
    if "--starter" in argv:
        made = starter(cfg, arg("--what"), arg("--parts"), arg("--never"), arg("--rules"))
        print("DOCS: wrote " + (", ".join(made) if made else "nothing (the docs already exist)") +
              ". Ask the owner the yellow 'to fill in' questions in plain words and fill them in.")
        return 0
    if "--core" in argv:
        print(core(cfg)); return 0
    if "--baseline" in argv:
        w = arg("--baseline") or ""
        if len(w) < 8:
            print("DOCS: --baseline needs the owner's words"); return 1
        d = dcfg(cfg); repo = read_repo(cfg["_root"])
        miss = coverage(repo, repo.get(d["architecture"], ""), d["source_roots"], dependencies(cfg), d.get("switch_pattern"))
        wrong = truth(repo, doc_list(repo, d), d.get("switch_pattern"), branch_names(cfg["_root"]), ignored_fn(cfg["_root"]))
        json.dump({"undocumented": [n for _, n in miss], "untrue": sorted({f"{x[0]}|{x[2]}" for x in wrong}),
                   "recorded": str(datetime.date.today()), "why": w}, open(bpath(cfg), "w"), indent=1)
        import steps as SP
        SP.recorded(cfg, [bpath(cfg)])                # through the kit's record door (review 6, F265)
        print(f"DOCS: {len(miss)} undocumented item(s) and {len(wrong)} untrue line(s) recorded as old debt: {w}"); return 0
    ok, msg = check(cfg); print(msg); return 0 if ok else 1


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

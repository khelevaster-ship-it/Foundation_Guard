"""FoundationGuard rule checks (AI-made, Claude, 2026-11-09): banned calls in named folders, and a dependency allow-list.

From an outside review: (1) unsafe, machine-dependent maths creeping into simulation code makes a long-running or
multiplayer world drift apart; (2) agents adding plugins, engine modules or outside libraries bring licence, security
and upgrade risks. Configure under "rules" in foundationguard.json:

  "rules": {
    "banned": [
      {"name": "deterministic maths", "preset": "deterministic_math",
       "paths": ["Source/MyGame/Private/Sim/**"], "exclude": ["Source/MyGame/Private/Sim/SafeMath.h"],
       "why": "the simulation must give the same answer on every machine"},
      {"name": "no printf in core", "pattern": "\\\\bprintf\\\\s*\\\\(", "paths": ["Core/**"]}
    ],
    "dependencies": {"exclude": ["Tools/Scratch/**"]}
  }

Banned calls: a file's count of matches (comments and strings don't count) may never go up from the record; it may
go down. Dependencies: every plugin, engine module, library, ThirdParty folder, submodule and package the project
uses must be in the record; a new one fails until the owner allows it:
    python fg/rules.py --allow "plugin:Water" --words "Yes, use Unreal's Water plugin (owner, 9 Nov)"
Record today's state once:  python fg/rules.py --baseline "why"   (rules_baseline.json; a guard file)
"""
import fnmatch, json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P
import funcs as FN
from weaken import FIRST_WORDS

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
# sqrt, fmod and remainder are exact by the IEEE 754 standard on every machine, so they are allowed; these are not:
MATH = r"sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|cbrt|hypot|pow|exp|exp2|expm1|log|log2|log10|log1p"
MATH_F = "|".join(f"{m}f|{m}l" for m in MATH.split("|"))
PRESETS = {
    "deterministic_math": [
        r"\bFMath::(?:Sin|Cos|Tan|Asin|Acos|Atan|Atan2|Sinh|Cosh|Tanh|SinCos|InvSqrt|InvSqrtEst|Pow|Exp|Exp2|Loge|"
        r"LogX|Log2|Hypot|Cbrt|FastAsin|Rand|RandInit|RandRange|RandHelper|RandHelper64|RandBool|FRand|FRandRange|VRand|"
        r"VRandCone|RandPointInBox|PerlinNoise\w*|SRand)\s*\(",
        r"(?:\bstd\s*::\s*|(?<![\w.>$:])(?:::\s*)?)(?:" + MATH + "|" + MATH_F + r")\s*\(",
        r"(?:\bstd\s*::\s*|(?<![\w.>$:])(?:::\s*)?)s?rand\s*\(|\bstd\s*::\s*random_device\b|\brandom_device\b|\b\w+_distribution\s*<|"
        r"\bstd\s*::\s*\w+_distribution\b",
        r"(?:\bstd\s*::\s*|(?<![\w.>$:])(?:::\s*)?)(?:time|clock)\s*\(|\bchrono\s*::\s*(?:system_clock|steady_clock|high_resolution_clock)\b|"
        r"\bFPlatformTime\s*::|\bFDateTime\s*::\s*(?:Now|UtcNow|Today)\b|\bGet(?:Real|Audio|Unpaused)?TimeSeconds\s*\(|"
        r"\bGetDeltaSeconds\s*\(|\bGetWorldDeltaSeconds\s*\(",
    ],
}
FM = (r"Sin|Cos|Tan|Asin|Acos|Atan|Atan2|Sinh|Cosh|Tanh|SinCos|InvSqrt|InvSqrtEst|Pow|Exp|Exp2|Loge|LogX|Log2|Hypot|Cbrt|"
      r"FastAsin|Rand|RandInit|RandRange|RandHelper|RandHelper64|RandBool|FRand|FRandRange|VRand|VRandCone|RandPointInBox|"
      r"PerlinNoise\w*|SRand")
CNAMES = MATH + "|" + MATH_F + r"|s?rand|time|clock"
# round 2 (9 Nov, second fresh set): a qualified name counts even with no "(" after it (&std::pow, a #define alias,
# std::tanh handed to std::transform, the bracket on the next line), clock types count bare (using namespace std::chrono)
PRESETS2 = {
    "deterministic_math": [
        r"\bFMath\s*::\s*(?:" + FM + r")\b",
        r"(?:\bstd\s*::\s*|(?<![\w.>$:])::\s*)(?:" + CNAMES + r")\b",
        r"(?<![\w.>$:])(?:" + CNAMES + r")\s*\(",
        r"\brandom_device\b|\b\w+_distribution\b(?=\s*[<({])|\bstd\s*::\s*\w+_distribution\b",
        r"\b(?:system_clock|steady_clock|high_resolution_clock)\b|\bFPlatformTime\s*::|\bFDateTime\s*::\s*(?:Now|UtcNow|Today)\b|"
        r"\bGet(?:Real|Audio|Unpaused)?TimeSeconds\s*\(|\bGet(?:World)?DeltaSeconds\s*\(",
    ],
}
# engine packs (9 Nov): Unity C#, Godot GDScript and Godot C#. Square root, abs, floor, lerp, clamp stay allowed (exact).
CS_TRIG = r"Sin|Cos|Tan|Asin|Acos|Atan|Atan2|Sinh|Cosh|Tanh|Asinh|Acosh|Atanh|Pow|Exp|Log|Log2|Log10|Cbrt|ScaleB|FusedMultiplyAdd"
UNITY_TRIG = r"Sin|Cos|Tan|Asin|Acos|Atan|Atan2|Pow|Exp|Log|Log10|PerlinNoise|SmoothDampAngle"
GD_FUNCS = r"sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|asinh|acosh|atanh|pow|exp|log|randf|randi|randf_range|randi_range|randfn|randomize"
CS_TIME = (r"\bDateTime(?:Offset)?\s*\.\s*(?:Now|UtcNow|Today)\b|\bStopwatch\b|\bEnvironment\s*\.\s*TickCount(?:64)?\b|"
           r"\bnew\s+(?:System\s*\.\s*)?Random\s*\(\s*\)|\bRandom\s*\.\s*Shared\b|\bGuid\s*\.\s*NewGuid\b")
PRESETS2["deterministic_math_unity"] = [
    r"\b(?:UnityEngine\s*\.\s*)?Mathf\s*\.\s*(?:" + UNITY_TRIG + r")\b",
    r"\b(?:System\s*\.\s*)?MathF?\s*\.\s*(?:" + CS_TRIG + r")\b",
    r"\bmath\s*\.\s*(?:sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|pow|exp|exp2|exp10|log|log2|log10|sincos)\b",
    r"\bUnityEngine\s*\.\s*Random\s*\.\s*\w+|(?<![\w.])Random\s*\.\s*(?:value|Range|insideUnitCircle|insideUnitSphere|onUnitSphere|rotation|"
    r"rotationUniform|ColorHSV|InitState|state)\b",
    r"\bTime\s*\.\s*(?:time|timeAsDouble|deltaTime|unscaledTime|unscaledTimeAsDouble|unscaledDeltaTime|realtimeSinceStartup|"
    r"realtimeSinceStartupAsDouble|smoothDeltaTime|fixedTime|fixedTimeAsDouble|fixedUnscaledTime|timeSinceLevelLoad)\b",
    CS_TIME,
]
PRESETS2["deterministic_math_godot"] = [
    r"(?<![\w.$])(?:" + GD_FUNCS + r")\s*\(",
    r"@GlobalScope\s*\.\s*(?:" + GD_FUNCS + r")\b",
    r"\bTime\s*\.\s*get_(?:ticks_msec|ticks_usec|unix_time_from_system|datetime_\w+_from_system|date_\w+_from_system|time_\w+_from_system)\b|"
    r"\bOS\s*\.\s*get_(?:ticks_msec|ticks_usec|unix_time|system_time_\w+|time|date|datetime)\b|"
    r"\bget_(?:process|physics_process)_delta_time\s*\(|\bGetProcessDeltaTime\s*\(|\bGetPhysicsProcessDeltaTime\s*\(|"
    r"\bTime\s*\.\s*(?:GetTicksMsec|GetTicksUsec|GetUnixTimeFromSystem)\b|\bOS\s*\.\s*(?:GetTicksMsec|GetTicksUsec)\b",
    r"\bGD\s*\.\s*(?:Randf|Randi|Randfn|RandRange|Randomize)\b|\b(?:Godot\s*\.\s*)?Mathf\s*\.\s*(?:" + CS_TRIG + r")\b",
    r"\b(?:System\s*\.\s*)?MathF?\s*\.\s*(?:" + CS_TRIG + r")\b",
    CS_TIME,
    r"\.\s*randomize\s*\(",
]
# web pack (11 Nov): browsers work these out their own way (the JavaScript standard lets each browser choose how
# closely), so two players' browsers can disagree. Math.sqrt, abs, floor, round, min, max, imul and fround are exact.
JS_MATH = r"sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|asinh|acosh|atanh|exp|expm1|log|log1p|log2|log10|pow|cbrt|hypot|random"
PRESETS2["deterministic_math_web"] = [
    r"\bMath\s*\.\s*(?:" + JS_MATH + r")\b",
    r"\*\*",                                                      # x ** y works like Math.pow
    r"\bcrypto\s*\.\s*(?:getRandomValues|randomUUID|randomBytes|randomInt)\b",
    r"\bDate\s*\.\s*now\b|\bnew\s+Date\s*\(\s*\)|(?<![\w.$])Date\s*\(\s*\)|\bperformance\s*\.\s*now\b|\bprocess\s*\.\s*hrtime\b",
]
PRESET_EXT = {"deterministic_math_web": FN.JS_EXT + FN.HTML_EXT}      # the browser rule reads web code only (not x ** 2 in Python)
STATIC_USING = {r"System\s*\.\s*MathF?": CS_TRIG, r"UnityEngine\s*\.\s*Mathf": UNITY_TRIG, r"Godot\s*\.\s*Mathf": CS_TRIG,
                r"Unity\s*\.\s*Mathematics\s*\.\s*math": r"sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|pow|exp|exp2|log|log2|log10"}
ALIAS_OF = {r"(?:UnityEngine\s*\.\s*|Godot\s*\.\s*)?Mathf": UNITY_TRIG + "|" + CS_TRIG, r"(?:System\s*\.\s*)MathF?": CS_TRIG,
            r"UnityEngine\s*\.\s*Random": r"value|Range|insideUnitCircle|insideUnitSphere|onUnitSphere|rotation|rotationUniform|ColorHSV|InitState",
            r"(?:Godot\s*\.\s*)?GD": r"Randf|Randi|Randfn|RandRange|Randomize"}


def cs_extra(text):
    """Patterns for C# 'using static System.Math;' (then Sin(x)) and 'using M = UnityEngine.Mathf;' (then M.Sin)."""
    if BREAK("engine_rules"): return []
    out = []
    for ns, names in STATIC_USING.items():
        if re.search(r"\busing\s+static\s+(?:global\s*::\s*)?" + ns + r"\s*;", text):
            out.append(r"(?<![\w.])(?:" + names + r")\s*\(")
    for m in re.finditer(r"\busing\s+(\w+)\s*=\s*(?:global\s*::\s*)?([\w.\s]+?)\s*;", text):
        for ns, names in ALIAS_OF.items():
            if re.fullmatch(ns, m.group(2).strip()):
                out.append(r"\b" + m.group(1) + r"\s*\.\s*(?:" + names + r")\b")
    return [re.compile(x) for x in out]


def js_extra(text):
    """Patterns for 'const { sin, pow: p } = Math;' (then sin(x), p(x))."""
    if BREAK("web_rules"): return []
    names = []
    for m in re.finditer(r"\b(?:const|let|var)\s*\{([^{}]*)\}\s*=\s*Math\b", text):
        for part in m.group(1).split(","):
            k, _, v = part.partition(":"); k, v = k.strip(), (v.strip() or k.strip())
            if re.fullmatch(JS_MATH, k) and re.fullmatch(r"[A-Za-z_$][\w$]*", v): names.append(re.escape(v))
    return [re.compile(r"(?<![\w.$])(?:" + "|".join(names) + r")\s*\(")] if names else []


NOT_TYPE = {"return", "else", "case", "throw", "co_return", "delete", "new", "goto", "do", "using", "typedef", "define"}
CODE = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".inl", ".ipp", ".cs", ".java", ".kt", ".swift", ".go", ".rs", ".py",
        ".gd") + FN.JS_EXT + FN.HTML_EXT


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def match(p, globs):
    return any(fnmatch.fnmatch(p, g) or (g.startswith("**/") and fnmatch.fnmatch(p, g[3:])) for g in globs or [])


def tracked(root):
    out = git("ls-files", cwd=root).stdout.split("\n")
    return sorted(p for p in out if p and os.path.isfile(os.path.join(root, p)))


def read(root, p):
    try:
        return open(os.path.join(root, p), encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


# ---------- banned calls ----------
def using_std(clean):
    return any(re.search(r"\busing\s+namespace\s+std\b", c) for c in clean)


def is_declaration(text, at):
    """True when the name at `at` is being declared or defined ("Fixed sin(Fixed a) {", "static Angle atan2(...);")."""
    start = max(text.rfind(c, 0, at) for c in "\n;{}") + 1
    pre = text[start:at]
    if not re.match(r"^\s*(?:[A-Za-z_][\w:]*(?:<[^;{}()=]*>)?[\s*&]+)+$", pre):
        return False
    return re.match(r"\s*([A-Za-z_]\w*)", pre).group(1) not in NOT_TYPE


DECL_BEFORE = re.compile(r"(?:\b(?:float|double|int|auto|bool|void|long|unsigned|static|inline|constexpr|const)\s*[&*]?\s*$)")


def _count_v1(clean, pats):
    """The round-1 way (kept for the rules_round2 break switch): count per line, skip simple declarations."""
    n = 0
    for ln in clean:
        for m in (m for pat in pats for m in pat.finditer(ln)):
            if DECL_BEFORE.search(ln[:m.start()]) and not BREAK("rules_decl"):
                continue
            n += 1
    return n


def _not_a_call(text, at, ext):
    if ext in FN.JS_EXT:                                     # JavaScript declares with "function sin(", never "float sin("
        return bool(re.search(r"\bfunction\s*\*?\s*$", text[max(0, at - 30):at]))
    if ext == ".gd" and re.search(r"\bfunc\s+$", text[max(0, at - 30):at]):
        return True                                          # "func sin(x):" defines a function of the script's own
    return not BREAK("rules_decl") and is_declaration(text, at)   # "float sin() const;", "Fixed pow(Fixed b, int e) {"


def _count_calls(clean, pats, ext):
    text = re.sub(r"\\\s*\n", " ", "\n".join(clean))          # a #define continued with a backslash is one line
    alias = [m.group(1) for m in re.finditer(r"\bnamespace\s+(\w+)\s*=\s*(?:::\s*)?std\s*;", text)]
    ps = pats + ([re.compile(r"\b(?:" + "|".join(alias) + r")\s*::\s*(?:" + CNAMES + r")\b")] if alias else [])
    if ext == ".cs":
        ps += cs_extra(text)
    if ext in FN.JS_EXT:
        ps += js_extra(text)
    hits = set()
    for m in (m for pat in ps for m in pat.finditer(text)):
        name = re.search(r"(\w+)\s*(?:\(|$)", m.group(0))
        at = m.start() + (name.start(1) if name else 0)
        if at not in hits and not _not_a_call(text, at, ext):   # std::sin( matched by two patterns is still one call
            hits.add(at)
    return len(hits)


def _rule_patterns(rule, old):
    pre = rule.get("preset", "")
    gone = ((BREAK("engine_rules") and pre == "deterministic_math_unity") or (BREAK("engine_godot_rules") and pre == "deterministic_math_godot")
            or (BREAK("web_rules") and pre == "deterministic_math_web"))
    src = ([] if gone else (PRESETS if old else PRESETS2).get(pre, [])) + ([rule["pattern"]] if rule.get("pattern") else [])
    return [re.compile(x) for x in src]


def _rule_files(files, rule):
    ext = PRESET_EXT.get(rule.get("preset", ""), CODE)
    return [p for p in files if match(p, rule.get("paths", ["**/*"])) and not match(p, rule.get("exclude")) and p.lower().endswith(ext)]


def count_banned(root, files, rule):
    old = BREAK("rules_round2")
    pats = _rule_patterns(rule, old)
    out = {}
    for p in _rule_files(files, rule):
        ext = os.path.splitext(p)[1].lower()
        raw = read(root, p).split("\n")
        if ext in FN.HTML_EXT and not BREAK("web_html"):
            raw, ext = FN.html_scripts(raw), ".js"               # a page's own <script> code is JavaScript
        clean = FN.clean_lines(raw, ext) if not BREAK("rules_comments") else raw
        clean = ["" if re.match(r"^\s*#\s*(include|import|pragma)", c) else c for c in clean]
        n = _count_v1(clean, pats) if old else _count_calls(clean, pats, ext)
        if n:
            out[p] = n
    return out


# ---------- dependencies ----------
def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'])//.*$", r"\1", text)


def _json(root, p, default=None):
    """The file read as JSON; default (or None) when it doesn't parse."""
    try:
        return json.loads(read(root, p))
    except ValueError:
        return default


def _modules(j):
    return {m.get("Name") for m in (j or {}).get("Modules", []) if isinstance(m, dict)}


def _own_names(root, files, ex):
    """The project's own Unreal modules and its own npm workspace packages: never outside dependencies."""
    own, own_npm = set(), set()
    for p in (p for p in files if not match(p, ex)):
        low = p.lower()
        if low.endswith(".uproject"):
            own |= _modules(_json(root, p))
        if low.endswith(".uplugin"):
            own |= _modules(_json(root, p, {}))
        if os.path.basename(p) == "package.json" and not BREAK("rules_round2"):
            try: own_npm.add(json.loads(read(root, p)).get("name"))      # the project's own workspace packages
            except (ValueError, AttributeError): pass
    return own, own_npm


def _req_includes(root, files):
    """requirements files named by -r inside another requirements file."""
    if BREAK("rules_round2"):
        return set()
    out = set()
    for p in (p for p in files if re.match(r"requirements[\w.-]*\.txt$", os.path.basename(p))):
        for m in re.finditer(r"(?m)^\s*(?:-r|--requirement)[\s=]+(\S+)", read(root, p)):
            out.add(os.path.normpath(os.path.join(os.path.dirname(p), m.group(1))).replace("\\", "/"))
    return out


class _Deps:
    def __init__(self, root, own, own_npm, reqs):
        self.root, self.own, self.own_npm, self.reqs, self.found = root, own, own_npm, reqs, {}   # "kind:name" -> first file

    def add(self, k, f):
        self.found.setdefault(k, f)


def _dep_folders(d, p, parts):
    """Godot addons/<name>/ folders and ThirdParty/<name>/ folders."""
    if "addons" in parts[:-2] and not BREAK("engine_deps"):
        k = parts.index("addons")                              # Godot: every addons/<name>/ folder is an outside add-on
        if os.path.isfile(os.path.join(d.root, *parts[:k], "project.godot")):
            d.add("godotaddon:" + parts[k + 1], p)
    lower = [x.lower() for x in parts]
    if "thirdparty" in lower[:-1]:
        k = lower.index("thirdparty")
        if k + 1 < len(parts) - 1 or (k + 1 == len(parts) - 1 and not BREAK("rules_deps")):
            d.add("thirdparty:" + "/".join(parts[:k + 2]), p)


def _enabled_plugins(d, j, p, loose=False):
    for pl in j.get("Plugins", []):
        if isinstance(pl, dict) and pl.get("Name") and (pl.get("Enabled", True) or loose):
            d.add("plugin:" + pl["Name"], p)


def _dep_uproject(d, p, parts):
    j = _json(d.root, p)
    if j is not None:
        _enabled_plugins(d, j, p, BREAK("rules_deps"))


def _dep_uplugin(d, p, parts):
    if "/plugins/" in "/" + p.lower():
        d.add("plugin:" + os.path.splitext(parts[-1])[0], p)
    j = _json(d.root, p, {}) if not BREAK("rules_round2") else {}
    _enabled_plugins(d, j, p)                                  # a plugin can switch on other plugins too


def _join_strings(t):
    """Build.cs string tricks: Prefix + "Subsystem", "Online" + "Subsystem" are one name."""
    for v, val in re.findall(r"\b(?:string|var)\s+(\w+)\s*=\s*\"([^\"]*)\"\s*;", t):
        t = re.sub(r"\b" + v + r"\s*\+\s*\"", lambda _m: "\"" + val, t)
        t = re.sub(r"\"\s*\+\s*" + v + r"\b", lambda _m: val + "\"", t)
    return re.sub(r"\"\s*\+\s*\"", "", t)


def _named_lists(t):
    """string lists built up in a Build.cs: Mods = new string[] {...}; Mods.Add("X");"""
    lists = {}
    for m in re.finditer(r"\b(\w+)\s*=\s*new\s+[^{;=]*\{([^}]*)\}", t):
        lists.setdefault(m.group(1), []).extend(re.findall(r"\"([^\"]+)\"", m.group(2)))
    for m in re.finditer(r"\b(\w+)\s*\.\s*Add(?:Range)?\s*\(([^;]*?)\)\s*;", t, re.S):
        if m.group(1) in lists:
            lists[m.group(1)].extend(re.findall(r"\"([^\"]+)\"", m.group(2)))
    return lists


def _build_modules(d, p, t, lists, call):
    for m in re.finditer(r"(?:" + call + r")\s*\.\s*Add(?:Range)?\s*\(([^;]*?)\)\s*;", t, re.S):
        names = re.findall(r"\"([^\"]+)\"", m.group(1))
        names += [x for v in re.findall(r"\b\w+\b", re.sub(r"\"[^\"]*\"", "", m.group(1))) for x in lists.get(v, [])]
        for name in (n for n in names if n not in d.own):
            d.add("module:" + name, p)


def _build_libraries(d, p, t):
    for m in re.finditer(r"PublicAdditionalLibraries\s*\.\s*Add(Range)?\s*\(([^;]*?)\)\s*;", t, re.S):
        names = re.findall(r"\"([^\"]+)\"", m.group(2))
        if not m.group(1) and not BREAK("rules_libpath"):
            names = names[-1:]                   # Add(Path.Combine(Dir, "zstd", "lib", "x.lib")) is one library, the last part
        for name in names:
            d.add("library:" + os.path.basename(name.replace("\\", "/")), p)
        if not names:
            d.add("library:" + re.sub(r"\s+", "", m.group(2))[:80], p)


def _dep_buildcs(d, p, parts):
    t = strip_comments(read(d.root, p))
    if not BREAK("rules_round2"):
        t = _join_strings(t)
        lists, call = _named_lists(t), r"(?:Public|Private)(?:Dependency|IncludePath)ModuleNames|Dynamically\w*ModuleNames"
    else:
        lists, call = {}, r"(?:Public|Private)(?:Include)?DependencyModuleNames|Dynamically[A-Za-z]*ModuleNames"
    _build_modules(d, p, t, lists, call)
    _build_libraries(d, p, t)


def _dep_gitmodules(d, p, parts):
    for m in re.finditer(r"(?m)^\s*path\s*=\s*(\S+)", read(d.root, p)):
        d.add("submodule:" + (m.group(1).strip("\"'") if not BREAK("rules_round2") else m.group(1)), p)


def _req_line(d, p, ln):
    egg = re.search(r"#egg=([A-Za-z0-9._-]+)", ln)
    if egg and not BREAK("rules_round2"):
        d.add("python:" + egg.group(1).lower().replace("_", "-"), p); return    # -e git+https://...#egg=name
    ln = ln.split("#")[0].strip()
    m = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", ln)
    if m and not ln.startswith("-"):
        d.add("python:" + m.group(1).lower().replace("_", "-"), p)


def _dep_requirements(d, p, parts):
    for ln in read(d.root, p).split("\n"):
        _req_line(d, p, ln)


def _dep_unity_manifest(d, p, parts):
    j = _json(d.root, p)                                       # Unity's package list; packages-lock.json is derived from it
    for name in ((j or {}).get("dependencies") or {}):
        d.add("unitypkg:" + name, p)


def _dep_unity_package(d, p, parts):
    j = _json(d.root, p)                                       # a package kept inside the Unity project (Packages/<name>/)
    if j is None:
        return
    d.add("unitypkg:" + (j.get("name") or parts[-2]), p)
    for name in (j.get("dependencies") or {}):
        d.add("unitypkg:" + name, p)


def _dep_godot(d, p, parts):
    t = re.sub(r"(?m)^\s*;.*$", "", read(d.root, p)); sec = ""
    for ln in t.split("\n"):
        m = re.match(r"^\s*\[([^\]]+)\]", ln)
        if m:
            sec = m.group(1).strip(); continue
        for a in (re.findall(r"res://addons/([^/\"]+)/", ln) if sec in ("editor_plugins", "autoload") else []):
            d.add("godotaddon:" + a, p)


def _dep_npm(d, p, parts):
    j = _json(d.root, p)
    for sec in (("dependencies", "devDependencies", "peerDependencies", "optionalDependencies") if j is not None else ()):
        for name in (n for n in (j.get(sec) or {}) if n not in d.own_npm):
            d.add("npm:" + name, p)


def _dep_csproj(d, p, parts):
    for m in re.finditer(r"<PackageReference\s+[^>]*Include\s*=\s*\"([^\"]+)\"", strip_xml(read(d.root, p))):
        d.add("nuget:" + m.group(1), p)


def _dep_gomod(d, p, parts):
    t = re.sub(r"//.*", "", read(d.root, p))
    for blk in re.findall(r"require\s*\((.*?)\)", t, re.S):
        for m in re.finditer(r"(?m)^\s*(\S+)\s+v\S+", blk):
            d.add("go:" + m.group(1), p)
    for m in re.finditer(r"(?m)^\s*require\s+([^\s(]+)\s+v\S+", t):
        d.add("go:" + m.group(1), p)


# Python imports (weaker-model test, 9 Nov): a helper added numpy with only "import numpy" and no requirements file,
# and the check missed it. Every imported top-level name that isn't Python's own, the project's own or the kit's is a
# dependency; its key is the installed package's name when this computer knows it (cv2 -> opencv-python).
IMPORT_ALIASES = {"cv2": "opencv-python", "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn",
                  "bs4": "beautifulsoup4", "dateutil": "python-dateutil", "Crypto": "pycryptodome"}


def _own_py(files):
    """Top-level names the project's own Python files and folders give: never outside packages."""
    own = set()
    for p in (p for p in files if p.endswith(".py")):
        parts = p[:-3].split("/")
        own |= {x for x in parts if x != "__init__"}
    return own


def _dist_name(mod):
    try:
        from importlib import metadata as md
        hit = (md.packages_distributions() or {}).get(mod)
    except Exception:
        hit = None
    return (hit[0] if hit else IMPORT_ALIASES.get(mod, mod)).lower().replace("_", "-")


def _imports_of(text):
    import ast
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
            out.add(n.module.split(".")[0])
    return out


def _dep_pyimports(d, files, ex):
    if BREAK("rules_imports"):
        return
    kit = P.kit_dir(d.root)
    own, std = _own_py(files), set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)
    for p in (p for p in files if p.endswith(".py") and not match(p, ex) and not (p + "/").startswith(kit + "/")):
        for mod in sorted(_imports_of(read(d.root, p)) - own - std - {"__future__"}):
            d.add("python:" + _dist_name(mod), p)


# Code loaded from the internet (web pack, 11 Nov): a <script src="https://...">, an import map, a modulepreload link,
# or import ... from "https://..." brings outside code in without package.json. Stylesheets and fonts are not code.
NPM_CDNS = {"cdn.jsdelivr.net", "unpkg.com", "esm.sh", "esm.run", "cdn.skypack.dev", "jspm.dev"}
URL = r"(?:https?:)?//[^\s\"'`<>]+"
JS_URL = re.compile(r"(?:\bfrom|\bimport\s*\(?|\bimportScripts\s*\()\s*[\"'`](" + URL + r")[\"'`]")


def web_key(url):
    """'web:<name>' for code loaded from the internet, without its version (a new version is not a new dependency)."""
    u = re.sub(r"^(?:https?:)?//", "", url.strip()).split("?")[0].split("#")[0]
    host, _, path = u.partition("/"); host = host.lower()
    m = None
    if host in NPM_CDNS:
        m = re.match(r"(?:npm/)?((?:@[\w.-]+/)?[\w.-]+?)(?:@[^/]*)?(?:/|$)", path)
    elif host == "cdnjs.cloudflare.com":
        m = re.match(r"ajax/libs/([\w.-]+)", path)
    elif host == "ga.jspm.io":
        m = re.match(r"npm:((?:@[\w.-]+/)?[\w.-]+?)@", path)
    if m and m.group(1) != "gh":
        return "web:" + m.group(1)
    path = re.sub(r"@[\w.^~-]+", "", path)
    path = re.sub(r"(?:^|(?<=/))v?\d+(?:\.\d+)+[\w.-]*(?=/|$)", "", path)
    return "web:" + host + "/" + re.sub(r"/+", "/", path).strip("/")


def _dep_js_urls(d, p, parts, text=None):
    for m in JS_URL.finditer(strip_comments(read(d.root, p) if text is None else text)):
        d.add(web_key(m.group(1)), p)


def _dep_html(d, p, parts):
    t = re.sub(r"<!--.*?-->", " ", read(d.root, p), flags=re.S)
    for m in re.finditer(r"<script\b([^>]*)>", t, re.I):
        src = re.search(r"\bsrc\s*=\s*[\"']?(" + URL + ")", m.group(1), re.I)
        if src:
            d.add(web_key(src.group(1)), p)
    for m in re.finditer(r"<link\b[^>]*>", t, re.I):
        href = re.search(r"\bhref\s*=\s*[\"']?(" + URL + ")", m.group(0), re.I)
        if href and re.search(r"\brel\s*=\s*[\"']?modulepreload", m.group(0), re.I):
            d.add(web_key(href.group(1)), p)
    for m in re.finditer(r"<script\b[^>]*type\s*=\s*[\"']?importmap[^>]*>(.*?)</script", t, re.I | re.S):
        for u in re.findall(r"[\"'](" + URL + r")[\"']", m.group(1)):
            d.add(web_key(u), p)
    _dep_js_urls(d, p, parts, "\n".join(FN.html_scripts(t.split("\n"))))


# Which reader handles which file: the first that matches wins (order matters: a Unity package.json before npm's).
DEP_FILES = [
    (lambda d, p, low, base: low.endswith(".uproject"), _dep_uproject),
    (lambda d, p, low, base: low.endswith(".uplugin"), _dep_uplugin),
    (lambda d, p, low, base: low.endswith(".build.cs"), _dep_buildcs),
    (lambda d, p, low, base: base == ".gitmodules", _dep_gitmodules),
    (lambda d, p, low, base: re.match(r"requirements[\w.-]*\.txt$", base) or p in d.reqs, _dep_requirements),
    (lambda d, p, low, base: base == "manifest.json" and p.split("/")[-2:-1] == ["Packages"] and not BREAK("engine_deps"), _dep_unity_manifest),
    (lambda d, p, low, base: base == "package.json" and unity_pkg(d.root, p) and not BREAK("engine_deps"), _dep_unity_package),
    (lambda d, p, low, base: base == "project.godot" and not BREAK("engine_deps"), _dep_godot),
    (lambda d, p, low, base: base == "package.json", _dep_npm),
    (lambda d, p, low, base: low.endswith(".csproj"), _dep_csproj),
    (lambda d, p, low, base: low.endswith(FN.HTML_EXT) and not BREAK("web_deps"), _dep_html),
    (lambda d, p, low, base: low.endswith(FN.JS_EXT) and not BREAK("web_deps"), _dep_js_urls),
    (lambda d, p, low, base: base == "go.mod", _dep_gomod)]


def deps(root, files, s):
    ex = (s or {}).get("exclude", []) if isinstance(s, dict) else []
    d = _Deps(root, *_own_names(root, files, ex), _req_includes(root, files))
    for p in (p for p in files if not match(p, ex)):
        low, base, parts = p.lower(), os.path.basename(p), p.split("/")
        _dep_folders(d, p, parts)
        reader = next((r for test, r in DEP_FILES if test(d, p, low, base)), None)
        if reader:
            reader(d, p, parts)
    _dep_pyimports(d, files, ex)
    return d.found

# ---------- dependencies ----------


def unity_pkg(root, p):
    """True for Packages/<name>/package.json inside a Unity project (next to Packages/manifest.json)."""
    parts = p.split("/")
    return len(parts) >= 3 and parts[-3] == "Packages" and os.path.isfile(os.path.join(root, *parts[:-2], "manifest.json"))


def strip_xml(t):
    return re.sub(r"<!--.*?-->", " ", t, flags=re.S)


# ---------- record, check ----------
def rules_cfg(cfg):
    return cfg.get("rules") or {}


def bpath(cfg):
    return os.path.join(cfg["_root"], rules_cfg(cfg).get("baseline", "rules_baseline.json"))


def measure(cfg):
    root, r = cfg["_root"], rules_cfg(cfg)
    files = tracked(root)
    ban = {} if BREAK("rules_banned") else {x.get("name", x.get("preset", "rule")): count_banned(root, files, x) for x in r.get("banned", [])}
    dep = {} if (BREAK("rules_deps_all") or r.get("dependencies") is False) else deps(root, files, r.get("dependencies"))
    return ban, dep


def load(cfg):
    try:
        return json.load(open(bpath(cfg), encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def save(cfg, b):
    json.dump(b, open(bpath(cfg), "w"), indent=1, sort_keys=True)
    import steps as SP                                 # 12 Nov: the check after the step keeps the kit's own record
    SP.recorded(cfg, [bpath(cfg)])


def check(cfg):
    if not rules_cfg(cfg):
        return True, "RULES: not configured."
    ban, dep = measure(cfg)
    b = load(cfg) or {"banned": {}, "dependencies": {}}
    bad = []
    for name, counts in ban.items():
        old = b.get("banned", {}).get(name, {})
        why = next((x.get("why", "") for x in rules_cfg(cfg).get("banned", []) if x.get("name", x.get("preset")) == name), "")
        for p, n in sorted(counts.items()):
            if n > old.get(p, 0):
                bad.append(f"  FAIL {name}: {p} has {n} (was {old.get(p, 0)})" + (f": {why}" if why else ""))
    allowed = b.get("dependencies", {})
    for k, f in sorted(dep.items()):
        if k not in allowed:
            bad.append(f"  FAIL new dependency {k} ({f}): needs the owner's OK: python fg/rules.py --allow \"{k}\" --words \"...\"")
    if bad:
        return False, f"RULES: {len(bad)} failure(s).\n" + "\n".join(bad)
    return True, f"RULES: ok ({sum(len(v) for v in ban.values())} file(s) with old counts, {len(dep)} allowed dependencies)."


def _arg_after(argv, flag):
    i = argv.index(flag) if flag in argv else -1
    return argv[i + 1] if 0 <= i < len(argv) - 1 else ""


def _baseline_cmd(cfg, argv):
    reason = " ".join(a for a in argv if not a.startswith("--"))
    if os.path.exists(bpath(cfg)) and not reason:
        print("RULES: a record exists; rewriting it needs a reason: fg/rules.py --baseline \"why\""); return 1
    ban, dep = measure(cfg)
    log = (load(cfg) or {}).get("log", []) + [{"when": time.strftime("%Y-%m-%d %H:%M"), "baseline": reason or "first baseline"}]
    b = {"banned": ban, "dependencies": {k: {"file": f, "words": FIRST_WORDS} for k, f in dep.items()}, "log": log}
    save(cfg, b); print(f"RULES: record written: {sum(len(v) for v in ban.values())} file count(s), {len(dep)} dependencies."); return 0


def _allow_cmd(cfg, argv):
    k, w = _arg_after(argv, "--allow"), _arg_after(argv, "--words")
    if not k or not w:
        print("RULES: --allow needs the dependency and the owner's own words: --allow \"plugin:X\" --words \"...\""); return 1
    b = load(cfg) or {"banned": {}, "dependencies": {}}
    b.setdefault("dependencies", {})[k] = {"words": w, "when": time.strftime("%Y-%m-%d %H:%M")}
    b.setdefault("log", []).append({"when": time.strftime("%Y-%m-%d %H:%M"), "allowed": k, "words": w})
    save(cfg, b); print(f"RULES: {k} allowed ({w})."); return 0


def main(argv):
    cfg = C.load()
    if "--baseline" in argv:
        return _baseline_cmd(cfg, argv)
    if "--allow" in argv:
        return _allow_cmd(cfg, argv)
    ok, rep = check(cfg)
    print(rep)
    return 0 if ok else 1

if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

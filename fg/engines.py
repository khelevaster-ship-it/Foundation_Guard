"""FoundationGuard engine packs (AI-made, Claude, 2026-11-09): find the game engine and fill in its settings.

Setup calls detect() and defaults(); nothing here needs the owner to know anything about engines.
  Unreal: a *.uproject file.   Unity: ProjectSettings/ProjectVersion.txt (and an Assets folder).   Godot: project.godot.
  Web (11 Nov): a package.json, or an index.html with a script (a browser game or web app; JavaScript or TypeScript).
The project may sit one folder down from the repository's top (e.g. game/project.godot); its folder is then used as the
prefix for every path. A game engine wins over a web folder next to it (a tools page beside a Godot game).
"""
import glob, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
SKIP = {".git", "node_modules", "dist", "coverage", ".foundationguard", "fg", "Library", "Temp", ".godot", ".import", "Binaries", "Intermediate",
        "Saved", "DerivedDataCache", "obj", "bin"}


def _here(root, sub):
    """The engine of the folder root/sub, or None."""
    d = os.path.join(root, sub) if sub else root
    try: names = os.listdir(d)
    except OSError: return None
    if any(n.lower().endswith(".uproject") for n in names): return "unreal"
    if os.path.isfile(os.path.join(d, "ProjectSettings", "ProjectVersion.txt")) and os.path.isdir(os.path.join(d, "Assets")):
        return "unity"
    if os.path.isfile(os.path.join(d, "project.godot")): return "godot"
    return None


NOT_WEB = {"docs", "doc", "site", "htmlcov", "coverage", "_build", "build", "dist", "out", "evidence", "examples"}


def _is_web(d, top):
    """A web project: a package.json, or an index.html with a script (one folder down: not a docs or report folder)."""
    if BREAK("web_detect") or (not top and os.path.basename(d).lower() in NOT_WEB):
        return False
    if os.path.isfile(os.path.join(d, "package.json")):
        return True
    try: page = open(os.path.join(d, "index.html"), encoding="utf-8", errors="replace").read(400000)
    except OSError: return False
    return re.search(r"<script\b", page, re.I) is not None


def detect(root):
    """(engine, subfolder) for the project at root or one folder down; (None, "") when it isn't a game-engine or web
    project. Several web folders one down (a front end and a back end) are measured together: ("web", "")."""
    if BREAK("engine_detect_all"): return None, ""
    e = _here(root, "")
    if e: return e, ""
    found, web = [], []
    for n in sorted(os.listdir(root)):
        if n in SKIP or n.startswith(".") or not os.path.isdir(os.path.join(root, n)): continue
        e = _here(root, n)
        if e: found.append((e, n))
        elif _is_web(os.path.join(root, n), False): web.append(n)
    if found:
        return found[0] if len(found) == 1 else (None, "")
    return _web_folder(root, web)


def _web_folder(root, web):
    """("web", sub) for a web project at the top, in one folder down, or in several (then the whole repository)."""
    if _is_web(root, True) or len(web) > 1:
        return "web", ""
    return ("web", web[0]) if web else (None, "")


def unity_editor(root, sub):
    """Path to the Unity editor of the version the project names, if it is installed in the usual Hub place."""
    try: ver = re.search(r"m_EditorVersion:\s*(\S+)", open(os.path.join(root, sub, "ProjectSettings", "ProjectVersion.txt")).read()).group(1)
    except (OSError, AttributeError): return None
    home = os.path.expanduser("~")
    for p in (rf"C:\Program Files\Unity\Hub\Editor\{ver}\Editor\Unity.exe", f"/Applications/Unity/Hub/Editor/{ver}/Unity.app/Contents/MacOS/Unity",
              f"{home}/Unity/Hub/Editor/{ver}/Editor/Unity"):
        if os.path.isfile(p): return p
    return None


def godot_binary():
    for name in ("godot", "godot4", "Godot", "godot.exe", "Godot.exe"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK): return p
    for p in glob.glob(r"C:\Program Files\Godot*\Godot*.exe") + glob.glob("/Applications/Godot*.app/Contents/MacOS/Godot"):
        return p
    return None


UNITY_NO_EDITOR = ("the game has Unity tests, but the Unity version it uses isn't installed through Unity Hub on this computer, so they "
                   "can't run from here yet (for the helper: install that version with Unity Hub, then run setup with --engine-tests).")
WEB_NO_NODE = ("the project has web tests, but Node.js isn't installed where this computer can find it, so they can't run "
               "from here yet (for the helper: install Node.js from nodejs.org, which needs the owner's OK, then run setup again).")
GODOT_NO_BINARY = ("the game has Godot tests, but the Godot program isn't installed where this computer can find it, so they can't run "
                   "from here yet (for the helper: make 'godot' runnable from the command line, then run setup with --engine-tests).")


def _unity_tests(root, sub, pre):
    try: man = json.load(open(os.path.join(root, sub, "Packages", "manifest.json"), encoding="utf-8-sig")).get("dependencies", {})
    except (OSError, ValueError): man = {}
    if "com.unity.test-framework" not in man:
        return None, "Unity's Test Framework isn't in this project, so there are no automatic tests to run yet."
    ed = unity_editor(root, sub)
    if not ed:
        return None, UNITY_NO_EDITOR
    log = ".foundationguard/unity_results.xml"
    base = f'"{ed}" -batchmode -nographics -projectPath "{pre or "."}" -runTests -testPlatform EditMode -testResults {log}'
    return (base, log, base + ' -testFilter "{check}"', "Unity Test Framework"), None


def _godot_tests(root, sub, pre):
    gd = godot_binary()
    gut = os.path.isdir(os.path.join(root, sub, "addons", "gut"))
    gdunit = os.path.isdir(os.path.join(root, sub, "addons", "gdUnit4"))
    if not (gut or gdunit):
        return None, "no Godot test tool (GUT or gdUnit4) is in addons/, so there are no automatic tests to run yet."
    if not gd:
        return None, GODOT_NO_BINARY
    path = f'--path "{pre or "."}"'
    if gut:
        log = pre + ".foundationguard/junit.xml"          # GUT writes it inside the Godot project folder
        base = (f'"{gd}" --headless {path} -s addons/gut/gut_cmdln.gd -gdir=res://test -ginclude_subdirs -gexit '
                '-gjunit_xml_file=res://.foundationguard/junit.xml')
        return (base, log, base + " -gunit_test_name={check}", "GUT"), None
    log = ".foundationguard/gdunit"
    base = f'"{gd}" --headless {path} -s res://addons/gdUnit4/bin/GdUnitCmdTool.gd --ignoreHeadlessMode -a res://test -rd {log}'
    return (base, None, base, "gdUnit4"), None


def _web_tests(root, sub, pre):
    import webtests as WT
    found = WT.kinds(os.path.join(root, sub) if sub else root)
    if not [k for k in found if k != "npm"]:
        return None, None                                    # none of its own; setup uses npm test if there is one
    if not shutil.which("node"):
        return None, WEB_NO_NODE
    import config as C
    base = f'{C.python_cmd()} fg/webtests.py' + (f' --in "{sub}"' if sub else "")
    return (base, WT.REPORT, base + ' --only "{check}"', " + ".join(WT.NAMES[k] for k in found)), None


def tests(root, engine, sub):
    """(gate_command, test_log, check_command, kind, note) for the engine's own test tool, or None plus a plain note."""
    pre = (sub + "/") if sub else ""
    fn = {"unity": _unity_tests, "godot": _godot_tests, "web": _web_tests}.get(engine)
    return fn(root, sub, pre) if fn else (None, None)


def _unity_defaults(pre):
    inc = [pre + "Assets/**/*.cs", pre + "Packages/**/*.cs"]
    exc = ["fg/**", ".foundationguard/**", pre + "Library/**", pre + "Temp/**", pre + "Packages/com.unity.*/**",
           "**/Plugins/**", "**/ThirdParty/**", "**/*.Generated.cs"]
    build = {"pattern": r"-buildTarget|BuildPipeline\.BuildPlayer|-executeMethod\s+\S*Build", "why": "making a release build needs the owner's OK."}
    return {"structure": {"include": inc, "exclude": exc},
            "block_while_running": ["Unity.exe", "Unity"],
            "job_patterns": [r"-batchmode", r"-runTests", r"-buildTarget", r"-executeMethod"],
            "extra_block": [build],
            "engine_version_file": pre + "ProjectSettings/ProjectVersion.txt",
            "plugin_globs": [pre + "Packages/manifest.json"],
            "rules_preset": "deterministic_math_unity"}


def _godot_defaults(pre):
    exc = ["fg/**", ".foundationguard/**", pre + ".godot/**", pre + ".import/**", pre + "addons/**", "**/obj/**", "**/bin/**"]
    export = {"pattern": r"--export(?:-release|-pack)?\b", "why": "exporting a release needs the owner's OK."}
    return {"structure": {"include": [pre + "**/*.gd", pre + "**/*.cs"], "exclude": exc},
            "block_while_running": ["Godot.exe", "Godot", "godot", "godot4", "Godot_v4*"],
            "job_patterns": [r"--headless", r"--export(?:-release|-debug|-pack)?\b", r"gut_cmdln", r"GdUnitCmdTool"],
            "extra_block": [export],
            "engine_version_file": None,
            "plugin_globs": [pre + "project.godot", pre + "addons/*/plugin.cfg"],
            "rules_preset": "deterministic_math_godot"}


def _unreal_defaults(pre):
    exc = ["fg/**", ".foundationguard/**", "**/ThirdParty/**", "**/Intermediate/**", "**/Binaries/**"]
    package = {"pattern": r"BuildCookRun|\s-package\b|\s-archive\b", "why": "packaging needs the owner's OK."}
    return {"structure": {"include": [pre + "Source/**", pre + "Plugins/**/Source/**"], "exclude": exc},
            "block_while_running": ["UnrealEditor.exe", "UnrealEditor"],
            "job_patterns": [r"UnrealEditor-Cmd", r"Build\.bat", r"RunUAT"],
            "extra_block": [package],
            "engine_version_file": None,
            "plugin_globs": [pre + "Plugins/*/*.uplugin"],
            "rules_preset": "deterministic_math"}


# Putting the game or app where players can see it. The owner does that, not a helper.
PUBLISH = (r"\b(?:npm|yarn|pnpm|bun)\s+publish\b|\b(?:npm|pnpm|bun)\s+run\s+(?:deploy|publish|release)\b|\byarn\s+(?:run\s+)?(?:deploy|release)\b|"
           r"\bvercel(?:\s+deploy\b|[^|&;\n]*\s--prod\b|\s*$|\s*[|&;])|\b(?:netlify|ntl)\s+deploy\b|\bfirebase\s+deploy\b|"
           r"\bwrangler\s+(?:pages\s+)?(?:deploy|publish)\b|\bgh-pages\b|\bbutler\s+push\b|\bsurge\b(?!-)|\bfly\s+deploy\b")
WEB_SKIP = ["node_modules/**", "**/node_modules/**", "dist/**", "build/**", "out/**", ".next/**", ".nuxt/**", ".svelte-kit/**",
            ".vite/**", ".parcel-cache/**", ".turbo/**", "coverage/**", "playwright-report/**", "test-results/**", "**/vendor/**",
            "**/*.min.js", "**/*.bundle.js", "**/*.min.mjs", "**/*.map", "**/*.d.ts"]


def _web_defaults(pre):
    if BREAK("web_setup"):
        return {"rules_preset": "deterministic_math"}            # as before the web pack: no web settings at all
    exc = ["fg/**", ".foundationguard/**"] + [x if x.startswith("**") else pre + x for x in WEB_SKIP]
    if BREAK("web_publish"):
        publish = []
    else:
        publish = [{"pattern": PUBLISH, "why": "publishing or deploying puts the game or app where players can see it, so the "
                    "owner does that step: tell the owner it is ready and give them the exact command to run."}]
    return {"structure": {"include": ["**/*"], "exclude": exc, "html_scripts": True},
            "block_while_running": [], "job_patterns": [],
            "extra_block": publish,
            "engine_version_file": None,
            "plugin_globs": [pre + "package.json"],
            "rules_preset": "deterministic_math_web"}


WEB_LIBS = [("phaser", "Phaser"), ("three", "Three.js"), ("pixi.js", "PixiJS"), ("@babylonjs/core", "Babylon.js"), ("babylonjs", "Babylon.js"),
            ("kaplay", "KAPLAY"), ("kaboom", "Kaboom"), ("excalibur", "Excalibur"), ("playcanvas", "PlayCanvas"),
            ("@react-three/fiber", "React Three Fiber"), ("next", "Next.js"), ("nuxt", "Nuxt"), ("@sveltejs/kit", "SvelteKit"),
            ("svelte", "Svelte"), ("vue", "Vue"), ("@angular/core", "Angular"), ("react", "React"), ("vite", "Vite")]


def web_kind(root, sub):
    """The game or app framework a web project uses (from package.json, or a script tag in index.html), or ""."""
    d = os.path.join(root, sub) if sub else root
    try:
        j = json.load(open(os.path.join(d, "package.json"), encoding="utf-8-sig"))
        deps = {k for sec in ("dependencies", "devDependencies") for k in (j.get(sec) or {})}
    except (OSError, ValueError, AttributeError):
        deps = set()
    try: page = open(os.path.join(d, "index.html"), encoding="utf-8", errors="replace").read(400000).lower()
    except OSError: page = ""
    tags = " ".join(re.findall(r"<script\b[^>]*\bsrc\s*=\s*[\"']?([^\"'\s>]+)", page))
    for k, name in WEB_LIBS:
        if k in deps or re.search(r"[/@]" + re.escape(k) + r"(?:[@/.]|$)", tags):
            return name
    return ""


def defaults(engine, sub):
    """Settings for the engine: what to measure, what to skip, what means 'the game is running', the maths preset."""
    pre = (sub + "/") if sub else ""
    fn = {"unity": _unity_defaults, "godot": _godot_defaults, "unreal": _unreal_defaults, "web": _web_defaults}.get(engine)
    return fn(pre) if fn else {}

def sim_folders(root, engine, sub):
    """Folders whose name says they hold the game's simulation (Sim, Simulation, Simulations), up to four levels down."""
    if BREAK("engine_sim"): return []
    base = os.path.join(root, sub) if sub else root; out = []
    for d, ds, _ in os.walk(base):
        ds[:] = [x for x in ds if x not in SKIP and not x.startswith(".") and x != "addons"]
        rel = os.path.relpath(d, root).replace(os.sep, "/")
        if rel.count("/") > 5: ds[:] = []; continue
        if os.path.basename(d).lower() in ("sim", "simulation", "simulations"): out.append(rel); ds[:] = []
    return sorted(out)


NAMES = {"unreal": "Unreal Engine", "unity": "Unity", "godot": "Godot", "web": "web (JavaScript or TypeScript)"}

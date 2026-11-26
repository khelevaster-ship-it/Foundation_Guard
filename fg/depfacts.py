"""FoundationGuard facts about outside software (AI-made, Claude, 2026-11-09).

When a push adds a dependency (a plugin, package, add-on or library), the owner must say allow or reject. This module looks
up what the project's own files say about it, so the owner gets facts and not the helper's word: its version, where it
comes from and its licence, with what that licence means for a game that will be sold.

It reads files on this computer only (the plugin's own description file, the package's manifest, a LICENSE file next to
it, the installed package's details). It never goes on the internet, so the same project always gives the same facts;
anything it can't find is said plainly as "not found".

  python fg/depfacts.py "plugin:Foo"      print the facts for one dependency name (as the rules check names it)
"""
import glob, json, os, re, sys

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

KIND_WORDS = {"plugin": "Unreal plugin", "godotaddon": "Godot add-on", "thirdparty": "outside code folder", "module": "Unreal module",
              "library": "compiled library", "submodule": "outside code (git submodule)", "python": "Python package",
              "unitypkg": "Unity package", "npm": "JavaScript package", "nuget": ".NET package", "go": "Go module",
              "web": "script loaded from the internet"}

# (pattern in the licence text or name, short name, kind). The first that matches wins, so the narrow ones come first.
LICENCES = [
    (r"\bAGPL|Affero", "AGPL", "copyleft"), (r"\bLGPL|Lesser General Public", "LGPL", "weak"),
    (r"\bGPL|GNU General Public", "GPL", "copyleft"), (r"\bMPL|Mozilla Public", "MPL-2.0", "weak"),
    (r"(?i)non[- ]?commercial|\bCC[- ]BY[- ]NC", "non-commercial", "noncommercial"),
    (r"\bApache", "Apache-2.0", "permissive"), (r"\bMIT\b|Permission is hereby granted, free of charge", "MIT", "permissive"),
    (r"\bBSD|Redistribution and use in source and binary forms", "BSD", "permissive"), (r"(?i)\bzlib\b", "zlib", "permissive"),
    (r"\bISC\b", "ISC", "permissive"), (r"(?i)unlicense|public domain|\bCC0\b", "public domain", "permissive"),
    (r"(?i)\bBoost Software", "Boost", "permissive"),
    (r"(?i)fab\.com|unrealengine\.com/marketplace|Marketplace|assetstore\.unity|Asset Store EULA", "store licence", "store"),
    (r"(?i)Unity Companion License|Unity Package Distribution", "Unity's own licence", "engine"),
    (r"(?i)Epic Games, Inc\.|Unreal Engine EULA", "Unreal Engine EULA", "engine")]

MEANING = {
    "permissive": "lets you sell the game; the helper adds its copyright notice to the credits",
    "weak": "lets you sell the game, but changes to its own files must be shared; ask before changing it",
    "copyleft": "the whole game may have to be given away as open source",
    "noncommercial": "forbids selling, so it can't go in a game that will be sold",
    "store": "a store licence: fine to ship inside a game, never to share its source files",
    "engine": "comes with the engine and is covered by the engine's own licence",
    "unknown": "no licence found, so nobody can say if the game may use it"}

RISKY = {"copyleft", "noncommercial", "unknown"}


def _read(path, limit=20000):
    try:
        return open(path, encoding="utf-8", errors="replace").read(limit)
    except OSError:
        return ""


def _json(path):
    try:
        return json.loads(_read(path, 2000000))
    except ValueError:
        return None


def licence_of(text):
    """(short name, kind) for a licence text, a licence name or a store link; ('not found', 'unknown') if nothing matches."""
    if not text or not text.strip():
        return "not found", "unknown"
    return next(((name, kind) for rx, name, kind in LICENCES if re.search(rx, text)), (text.strip()[:40], "unknown"))


def _licence_file(folder):
    """The text of a LICENSE / COPYING / NOTICE file in a folder, or ''."""
    if not folder or not os.path.isdir(folder):
        return ""
    names = sorted(f for f in os.listdir(folder) if re.match(r"(?i)(licen[cs]e|copying|notice|eula)", f))
    return _read(os.path.join(folder, names[0])) if names else ""


def _facts(version="", source="", licence_text="", folder=None, found=True):
    lic, kind = licence_of(licence_text or _licence_file(folder))
    return {"version": version or "not found", "source": source or "not found", "licence": lic, "kind": kind,
            "meaning": MEANING[kind], "found": found}


def _tracked(root):
    """The project's files (git's list), so a search never walks build folders or a huge Content folder."""
    if root not in _TRACKED:
        import subprocess
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        _TRACKED[root] = [p for p in out.split("\n") if p]
    return _TRACKED[root]


_TRACKED = {}


def _find(root, tail):
    """Tracked files whose path ends with tail (a file name or a/b/c), as full paths."""
    return [os.path.join(root, p) for p in _tracked(root) if p == tail or p.endswith("/" + tail)]


def _plugin(root, name):
    hits = _find(root, name + ".uplugin")
    if not hits:
        return _facts(source="not in the project: it comes with Unreal Engine itself", licence_text="Unreal Engine EULA", found=False)
    j = _json(hits[0]) or {}
    store = j.get("FabURL") or j.get("MarketplaceURL") or ""
    who = " ".join(x for x in (j.get("CreatedBy", ""), j.get("CreatedByURL", "")) if x)
    return _facts(j.get("VersionName", ""), who + (f" (store page {store})" if store else ""), store, os.path.dirname(hits[0]))


def _godot_addon(root, name):
    cfgs = _find(root, f"addons/{name}/plugin.cfg")
    folder = os.path.dirname(cfgs[0]) if cfgs else None
    t = _read(cfgs[0]) if cfgs else ""
    get = lambda k: (re.search(r'(?m)^\s*' + k + r'\s*=\s*"([^"]*)"', t) or [None, ""])[1]
    return _facts(get("version"), get("author"), "", folder, bool(cfgs))


def _folder(root, rel):
    folder = os.path.join(root, rel)
    ver = next((_read(os.path.join(folder, f), 200).strip().split("\n")[0] for f in ("VERSION", "version.txt") if os.path.isfile(os.path.join(folder, f))), "")
    return _facts(ver, rel, "", folder, os.path.isdir(folder))


def _submodule(root, rel):
    t = _read(os.path.join(root, ".gitmodules"))
    m = re.search(r"path\s*=\s*" + re.escape(rel) + r"\s*\n\s*url\s*=\s*(\S+)", t)
    return _facts("", m.group(1) if m else "", "", os.path.join(root, rel), os.path.isdir(os.path.join(root, rel)))


def _python(root, name):
    try:
        from importlib import metadata as md
        m = md.metadata(name)
    except Exception:
        return _facts(source="not installed on this computer", found=False)
    classes = " ".join(c for c in (m.get_all("Classifier") or []) if c.startswith("License"))
    lic = m.get("License-Expression") or m.get("License") or classes
    home = m.get("Home-page") or next((u.split(",", 1)[-1].strip() for u in (m.get_all("Project-URL") or [])), "")
    return _facts(m.get("Version", ""), home, lic[:300])


def _unity_folder(root, name):
    """(manifest version spec, the package's own folder or None)."""
    mans = _find(root, "Packages/manifest.json")
    spec = str(((_json(mans[0]) or {}).get("dependencies") or {}).get(name, "")) if mans else ""
    unity_root = os.path.dirname(os.path.dirname(mans[0])) if mans else root
    cache = sorted(glob.glob(os.path.join(unity_root, "Library", "PackageCache", glob.escape(name) + "@*")))
    own = [d for d in [os.path.join(unity_root, "Packages", name)] if os.path.isdir(d)]
    return spec, (cache or own or [None])[-1]


def _unity_pkg(root, name):
    spec, folder = _unity_folder(root, name)
    j = (_json(os.path.join(folder, "package.json")) if folder else None) or {}
    unity = name.startswith("com.unity.")
    remote = "://" in spec or spec.startswith("file:")
    source = "Unity's own package registry" if unity else (spec if remote else "")
    lic = j.get("license", "") or ("Unity Companion License" if unity else "")
    return _facts(j.get("version", "") or ("" if "://" in spec else spec), source, lic, folder)


def _npm(root, name):
    spec = str(((_json(os.path.join(root, "package.json")) or {}).get("dependencies") or {}).get(name, ""))
    folder = os.path.join(root, "node_modules", name)
    j = _json(os.path.join(folder, "package.json")) or {}
    repo = j.get("repository", "")
    repo = repo.get("url", "") if isinstance(repo, dict) else repo
    lic = j.get("license", "")
    return _facts(j.get("version", "") or spec, repo or j.get("homepage", "") or "the npm registry", lic if isinstance(lic, str) else "", folder)


def _nuget(root, name):
    ver = ""
    for p in (os.path.join(root, p) for p in _tracked(root) if p.endswith(".csproj")):
        m = re.search(r'Include\s*=\s*"' + re.escape(name) + r'"[^>]*Version\s*=\s*"([^"]+)"', _read(p, 200000))
        ver = ver or (m.group(1) if m else "")
    spec = sorted(glob.glob(os.path.join(os.path.expanduser("~"), ".nuget", "packages", name.lower(), ver or "*", "*.nuspec")))
    t = _read(spec[-1]) if spec else ""
    lic = (re.search(r"<license[^>]*>([^<]+)<", t) or re.search(r"<licenseUrl>([^<]+)<", t) or [None, ""])[1]
    return _facts(ver, "the NuGet package registry", lic, os.path.dirname(spec[-1]) if spec else None)


def _go(root, name):
    m = re.search(r"(?m)^\s*(?:require\s+)?" + re.escape(name) + r"\s+(v\S+)", _read(os.path.join(root, "go.mod"), 200000))
    return _facts(m.group(1) if m else "", "https://" + name if "." in name.split("/")[0] else name)


def _module(root, name):
    if _find(root, name + ".Build.cs"):
        return _facts(source="a module inside this project's own plugins", licence_text="")
    return _facts(source="part of Unreal Engine itself", licence_text="Unreal Engine EULA", found=False)


def _library(root, name):
    hits = _find(root, name)
    folder = os.path.dirname(hits[0]) if hits else None
    up = os.path.dirname(folder) if folder else None
    return _facts("", folder[len(root) + 1:] if folder else "", _licence_file(folder) or _licence_file(up), None, bool(hits))


def _web(root, name):
    """Code loaded from the internet (web pack, 11 Nov): its address and version, from the page or file that loads it."""
    import rules as R
    for p in (p for p in _tracked(root) if p.lower().endswith((".html", ".htm", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"))):
        try: t = open(os.path.join(root, p), encoding="utf-8", errors="replace").read()
        except OSError: continue
        for u in re.findall(R.URL, t):
            if R.web_key(u) == "web:" + name:
                ver = re.search(r"@(\d[\w.-]*)|/v?(\d+(?:\.\d+)+)(?=/)", u)
                return _facts(next((g for g in (ver.groups() if ver else ()) if g), ""), u.rstrip("\"');,)"))
    return _facts(found=False)


READERS = {"plugin": _plugin, "godotaddon": _godot_addon, "thirdparty": _folder, "submodule": _submodule, "python": _python,
           "unitypkg": _unity_pkg, "npm": _npm, "nuget": _nuget, "go": _go, "module": _module, "library": _library, "web": _web}


def facts(root, key):
    """{'kind words', 'version', 'source', 'licence', 'kind', 'meaning', 'found'} for a 'kind:name' dependency key."""
    kind, _, name = key.partition(":")
    fn = READERS.get(kind) if not BREAK("depfacts") else None
    try:
        f = fn(root, name) if fn else _facts(found=False)
    except Exception as e:                                   # a strange file must never stop the push; say what happened
        f = _facts(source=f"couldn't be read ({type(e).__name__})", found=False)
    f["what"] = KIND_WORDS.get(kind, kind)
    return f


def line(f):
    """One plain line of facts."""
    return f"version {f['version']}; from {f['source']}; licence {f['licence']}: {f['meaning']}"


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    for k in sys.argv[1:]:
        print(k + ": " + line(facts(os.getcwd(), k)))

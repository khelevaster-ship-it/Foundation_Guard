"""FoundationGuard licence ledger (AI-made, Claude, 2026-11-09): every art, sound, music, model, font and video file says
where it came from and under what licence.

The owner-readable table ASSETS.md at the project's top folder:
    | Files | Source | Made by | Licence | Link | Notes |
    |---|---|---|---|---|---|
    | Art/Moons/** | Our own moon renders | Sam | own | - | |
    | Audio/Music/theme.ogg | "Dawn" | Jane Roe | CC-BY-4.0 | https://... | |
    | Art/Icons/** | Generated icons | Midjourney v6 | AI-made | - | prompted by Sam |
"Files" is a path or a folder pattern (** any folders, * inside one name); the most specific row covers a file.
Fails: an asset file no row covers; a licence that is blank, unknown or not recognised; CC BY without who made it or a link;
AI-made without the tool named; non-commercial (NC) or no-derivatives (ND) in a commercial project; bought without a link.
Warns: a row that covers no file; share-alike (SA) licences. Problems that were already there at the first record are old
debt: they are listed but only new ones fail (python fg/assets.py --baseline "why" records them; it asks the owner).
    python fg/assets.py            check
    python fg/assets.py --credits  write CREDITS.md from the table (authors, links, AI tools) for the credits screen
Settings in foundationguard.json: "assets": {"file": "ASSETS.md", "commercial": true, "exclude": ["Tools/**"],
"extra_types": ["xyz"]} (a file type of the project's own that counts as an asset too)
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import rules as RU

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
EXT = {"png", "jpg", "jpeg", "tga", "tif", "tiff", "bmp", "psd", "exr", "hdr", "webp", "svg", "kra", "xcf", "gif", "dds",
       "wav", "ogg", "mp3", "flac", "aif", "aiff", "m4a", "opus",
       "fbx", "obj", "gltf", "glb", "blend", "dae", "abc", "usd", "usda", "usdz", "3ds", "max", "ma", "mb",
       "ttf", "otf", "woff", "woff2", "fnt", "mp4", "webm", "mov", "avi", "mkv"}
ENGINE_EXT = {"uasset", "umap"}                       # only under a Content/ folder (Unreal)
# An outside review, 12 Nov (claim C10): a tracked Art/texture.ktx2 with no licence row passed ("0 of 0 asset files").
# More of the formats art, sound, models, fonts and video come in, and a project names its own with "extra_types".
MORE_EXT = {"ktx", "ktx2", "basis", "astc", "pvr", "pkm", "jxl", "avif", "heic", "heif", "ico", "icns", "apng", "jp2",
            "j2k", "pcx", "ppm", "pgm", "pbm", "aseprite", "ase", "pdn", "clip", "procreate", "sai", "afphoto",
            "afdesign", "ai", "eps", "cdr", "sketch", "ora", "spp", "sbs", "sbsar",
            "aac", "wma", "mid", "midi", "xm", "mod", "it", "s3m", "caf", "aifc", "ape", "wv", "spx", "amr", "ac3",
            "mka", "bank", "bnk", "wem", "fsb", "sf2",
            "ply", "stl", "3mf", "x3d", "vrm", "pmx", "pmd", "bvh", "c4d", "lwo", "lws", "skp", "ztl", "zpr", "vox",
            "qb", "md2", "md3", "md5mesh", "md5anim", "iqm", "skel",
            "ttc", "otc", "eot", "pfb", "pfm", "bdf", "pcf",
            "ogv", "m4v", "wmv", "flv", "mpg", "mpeg", "bik", "bk2", "usm", "3gp", "mts", "m2ts"}
MISSING = {"", "-", "--", "n/a", "na", "none", "unknown", "?", "tbd", "todo", "unsure", "no", "nil"}
AI_TOOLS = r"midjourney|dall-?e|stable\s*diffusion|sdxl|flux|suno|udio|elevenlabs|eleven\s*labs|meshy|tripo|claude|chatgpt|gpt-?\w*|" \
           r"firefly|imagen|leonardo|ideogram|runway|sora|kling|musicgen|riffusion|aiva|soundraw|krea|nano\s*banana|gemini|tool\s*:\s*\S+"


def is_asset(p, exclude, extra=()):
    if RU.match(p, exclude): return False
    ext = p.rsplit(".", 1)[-1].lower() if "." in os.path.basename(p) else ""
    if ext in EXT: return True
    if not BREAK("assets_more_types") and (ext in MORE_EXT or ext in {x.lower().lstrip(".") for x in extra}): return True
    return ext in ENGINE_EXT and "Content" in p.split("/")[:-1] and not BREAK("assets_engine")


def glob_re(g):
    g = g.strip().strip("`").replace("\\", "/").lstrip("./") if g.strip() not in (".", "./") else "**"
    if g.endswith("/"): g += "**"
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i): out += "(?:.*/)?"; i += 3
        elif g.startswith("**", i): out += ".*"; i += 2
        elif g[i] == "*": out += "[^/]*"; i += 1
        elif g[i] == "?": out += "[^/]"; i += 1
        else: out += re.escape(g[i]); i += 1
    return re.compile(out + r"\Z", re.I)


def specificity(g):
    g = g.strip()
    return (0 if any(c in g for c in "*?") or g.endswith("/") else 1, len(re.sub(r"[*?]", "", g)))


def _cc(t):
    parts = set(re.findall(r"BY|SA|NC|ND", t))
    if "BY" not in parts:
        return None
    return "CC-BY" + "".join("-" + x for x in ("NC", "ND", "SA") if x in parts)


BOUGHT_WORDS = ("BOUGHT", "PURCHASED", "STORE", "PAID", "ROYALTY-FREE", "COMMERCIAL", "STORE-LICENCE", "STORE-LICENSE")
LICENCE_RULES = [  # (test on the normalised cell, code), in order; Creative Commons is handled before these
    (lambda t: t.startswith("OFL") or "OPEN-FONT" in t, "OFL"),
    (lambda t: t in ("MIT", "MIT-LICENSE", "MIT-LICENCE"), "MIT"),
    (lambda t: t.startswith("APACHE"), "APACHE"),
    (lambda t: t in ("OWN", "OURS", "ORIGINAL", "MADE-BY-US", "IN-HOUSE", "SELF-MADE"), "OWN"),
    (lambda t: t.startswith("AI") or t in ("GENERATED", "AI-GENERATED"), "AI"),
    (lambda t: t in BOUGHT_WORDS or "MARKETPLACE" in t or "ASSET-STORE" in t, "BOUGHT")]


def licence(text):
    """(code, words) for a licence cell: CC0, CC-BY[-SA|-NC|-ND...], OFL, MIT, APACHE, OWN, AI, BOUGHT; None if unknown."""
    t = re.sub(r"[\s_]+", "-", (text or "").strip().upper()).replace("CREATIVE-COMMONS", "CC").replace("ATTRIBUTION", "BY")
    t = re.sub(r"-+", "-", t).strip("-")
    if t.lower() in MISSING: return None
    if re.search(r"\bCC-?0\b|CC-?ZERO|PUBLIC-?DOMAIN|^PD$", t): return "CC0"
    if t.startswith("CC") or re.match(r"^BY\b", t):
        return _cc(t)
    return next((code for test, code in LICENCE_RULES if test(t)), None)


def _header(cells):
    low = [c.lower() for c in cells]
    if "files" in low and "licence" in low or "license" in low and "files" in low:
        return {k: i for i, k in enumerate(low)}
    return None


def _row(cells, head, n):
    get = lambda *ks: next((cells[head[k]] for k in ks if k in head and head[k] < len(cells)), "")
    if not get("files"):
        return None
    return {"files": get("files"), "source": get("source"), "by": get("made by", "author", "by"),
            "licence": get("licence", "license"), "link": get("link", "url"), "notes": get("notes"), "line": n}


def read_table(root, name):
    """Rows of the ledger: [{'files','source','by','licence','link','notes','line'}]."""
    rows = []
    try: lines = open(os.path.join(root, name), encoding="utf-8", errors="replace").read().split("\n")
    except OSError: return rows
    head = None
    for n, ln in enumerate(lines, 1):
        if not ln.strip().startswith("|"):
            head = None if not ln.strip() else head; continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        h = _header(cells)
        if h is not None:
            head = h; continue
        r = _row(cells, head, n) if head is not None else None
        if r:
            rows.append(r)
    return rows


def acfg(cfg):
    a = dict({"file": "ASSETS.md", "commercial": True, "exclude": []}, **(cfg.get("assets") or {}))
    return a


_miss = lambda v: (v or "").strip().lower() in MISSING


def _by_problems(r, lic, g):
    out = []
    if lic.startswith("CC-BY") and _miss(r["by"]):
        out.append(("by_missing_author", f"row '{g}': {r['licence']} needs who made it (Made by)"))
    if lic.startswith("CC-BY") and _miss(r["link"]) and not BREAK("assets_by"):
        out.append(("by_missing_link", f"row '{g}': {r['licence']} needs a link to where it came from"))
    return out


def _row_problems(r, lic, a):
    """(problem key prefix, words) for one ledger row with a known licence."""
    g = r["files"]; out = _by_problems(r, lic, g)
    if lic == "AI" and not re.search(AI_TOOLS, (r["by"] + " " + r["notes"] + " " + r["source"]).lower()) and not BREAK("assets_ai"):
        out.append(("ai_no_tool", f"row '{g}': AI-made needs the tool named (Made by or Notes), so the credits can say so"))
    if a.get("commercial", True) and ("-NC" in lic or "-ND" in lic) and not BREAK("assets_nc"):
        what = "selling" if "-NC" in lic else "changing"
        out.append(("nc_nd_commercial", f"row '{g}': {r['licence']} forbids {what} it, and this project is marked commercial"))
    if lic == "BOUGHT" and _miss(r["link"]):
        out.append(("bought_no_link", f"row '{g}': a bought asset needs a link to its store page or licence"))
    return out

def _covering_rows(files, pats, probs):
    """Which row covers each file (the most specific one); files with no row become problems."""
    used = set()
    for p in files:
        hits = [(s, i) for i, (r, rx, s) in enumerate(pats) if rx.match(p)]
        if not hits:
            probs[f"no_row:{p}"] = f"no record says where {p} came from or its licence"; continue
        used.add(max(hits)[1] if not BREAK("assets_specific") else hits[0][1])
    return used


def _check_row(r, a, probs, warns):
    g = r["files"]
    lic = licence(r["licence"])
    if lic is None:
        probs[f"bad_licence:{g}"] = f"row '{g}': licence '{r['licence']}' is blank, unknown or not one FoundationGuard knows"
        return
    for key, words in _row_problems(r, lic, a):
        probs[f"{key}:{g}"] = words
    if "-SA" in lic:
        warns.append(f"row '{g}': {r['licence']} is share-alike: anything made from it must be shared under the same licence")


def measure(cfg):
    """(problems {key: words}, warnings [words], covered count, asset count)."""
    root, a = cfg["_root"], acfg(cfg)
    files = [p for p in RU.tracked(root) if is_asset(p, a["exclude"], a.get("extra_types") or ())]
    rows = read_table(root, a["file"])
    pats = [(r, glob_re(r["files"]), specificity(r["files"])) for r in rows]
    probs, warns = {}, []
    used = _covering_rows(files, pats, probs)
    for i, (r, rx, s) in enumerate(pats):
        if i not in used:
            warns.append(f"row '{r['files']}' (line {r['line']}) covers no file any more"); continue
        _check_row(r, a, probs, warns)
    return probs, warns, len(files) - sum(1 for k in probs if k.startswith("no_row:")), len(files)

def bpath(cfg):
    return os.path.join(cfg["_root"], "assets_baseline.json")


def check(cfg):
    a = acfg(cfg)
    if not cfg.get("assets") and not os.path.exists(os.path.join(cfg["_root"], a["file"])):
        return True, "ASSETS: not set up (no ASSETS.md)."
    probs, warns, cov, n = measure(cfg)
    try: old = json.load(open(bpath(cfg), encoding="utf-8-sig")).get("problems", {})
    except (OSError, ValueError): old = {}
    new = {k: v for k, v in sorted(probs.items()) if k not in old or BREAK("assets_baseline")}
    debt = len([k for k in probs if k in old])
    lines = [f"  FAIL {k.split(':', 1)[0]} {k.split(':', 1)[1]}: {v}" for k, v in new.items()] + [f"  warn: {w}" for w in warns]
    tail = f" ({debt} older problem(s) recorded as to fill in)" if debt else ""
    if new:
        return False, f"ASSETS: {len(new)} failure(s){tail}.\n" + "\n".join(lines) + \
            "\n  Fix: add or correct a row in " + a["file"] + " (ask the owner where the file came from, in plain words)."
    return True, f"ASSETS: ok ({cov} of {n} asset file(s) recorded{tail})." + ("\n" + "\n".join(lines) if warns else "")


CREDIT_GROUPS = ("Made with AI tools", "Used under Creative Commons Attribution", "Fonts and open licences",
                 "Public domain (CC0)", "Bought")


def _ai_line(r, title, who):
    tool = re.search(AI_TOOLS, who.lower())
    if tool or BREAK("assets_round1"):
        return f"- {title}: made with {who or r['notes']}" + (f" ({r['notes']})" if who and r["notes"] and BREAK("assets_round1") else "")
    m = re.search(AI_TOOLS, (r["notes"] + " " + r["source"]).lower())   # the person is in Made by and the tool in Notes or Source
    t = (r["notes"] + " " + r["source"])[m.start():m.end()] if m else r["notes"]
    t = re.sub(r"(?i)^tool\s*:\s*", "", t)
    return f"- {title}: made" + (f" by {who}" if who else "") + f" with {t}"


def _credit_line(r, lic):
    """(group, line) for one row with a usable licence."""
    who = "" if _miss(r["by"]) else r["by"]
    title = r["source"] or r["files"]
    link = "" if _miss(r["link"]) else f", {r['link']}"
    by = f" by {who}" if who else ""
    if lic == "AI":
        return CREDIT_GROUPS[0], _ai_line(r, title, who)
    if lic.startswith("CC-BY"):
        return CREDIT_GROUPS[1], f"- \"{title}\" by {who}, {r['licence']}{link}" + (" (changed)" if "chang" in r["notes"].lower() else "")
    if lic in ("OFL", "MIT", "APACHE"):
        return CREDIT_GROUPS[2], f"- {title}{by}, {r['licence']}{link}"
    return (CREDIT_GROUPS[3] if lic == "CC0" else CREDIT_GROUPS[4]), f"- {title}{by}{link}"


def credits(cfg):
    """CREDITS.md from the table. Rows the gate would fail are left out (listed on screen) so the credits never say something wrong."""
    a = acfg(cfg); root = cfg["_root"]; rows = read_table(root, a["file"])
    probs = measure(cfg)[0] if not BREAK("assets_round1") else {}
    badrows = {k.split(":", 1)[1] for k in probs if not k.startswith("no_row:")}
    groups, left = {k: [] for k in CREDIT_GROUPS}, []
    for r in rows:
        lic = licence(r["licence"])
        if lic in (None, "OWN"): continue
        if r["files"] in badrows: left.append(r["files"]); continue
        if lic == "AI" and BREAK("assets_credits"): continue
        g, line = _credit_line(r, lic)
        groups[g].append(line)
    out = ["# Credits", "", "*Written by FoundationGuard from " + a["file"] + "; edit that table, not this file.*", ""]
    for k, v in groups.items():
        if v: out += ["## " + k, ""] + v + [""]
    open(os.path.join(root, "CREDITS.md"), "w").write("\n".join(out))
    return sum(len(v) for v in groups.values()), left

def starter(cfg):
    """Write a first ASSETS.md with one 'unknown' row per folder of asset files (setup calls this). Returns (files, rows)."""
    root, a = cfg["_root"], acfg(cfg)
    if os.path.exists(os.path.join(root, a["file"])) or BREAK("assets_setup"): return 0, 0
    files = [p for p in RU.tracked(root) if is_asset(p, a["exclude"], a.get("extra_types") or ())]
    if not files: return 0, 0
    groups = sorted({("/".join(p.split("/")[:2]) + "/**") if p.count("/") >= 2 else (p.split("/")[0] + "/**" if "/" in p else p) for p in files})
    out = ["# Where the project's pictures, sounds, music, models and fonts came from", "",
           "One row per file or folder. Licence: CC0, CC-BY-4.0, CC-BY-SA-4.0, OFL-1.1, MIT, own (we made it), AI-made (name the",
           "tool in Made by), bought (link to the store page), or unknown. FoundationGuard checks this table on every upload.", "",
           "| Files | Source | Made by | Licence | Link | Notes |", "|---|---|---|---|---|---|"]
    out += [f"| {g} | | | unknown | | to fill in |" for g in groups]
    open(os.path.join(root, a["file"]), "w").write("\n".join(out) + "\n")
    return len(files), len(groups)


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__); return 0
    cfg = C.load()
    if "--credits" in argv:
        n, left = credits(cfg); print(f"ASSETS: CREDITS.md written ({n} credit line(s)).")
        if left: print("ASSETS: left out until their row is fixed (see python fg/assets.py): " + ", ".join(left))
        return 0
    if "--baseline" in argv:
        reason = " ".join(x for x in argv if not x.startswith("--"))
        if os.path.exists(bpath(cfg)) and not reason:
            print("ASSETS: a record exists; rewriting it needs a reason: fg/assets.py --baseline \"why\""); return 1
        probs, _, _, n = measure(cfg)
        try: log = json.load(open(bpath(cfg), encoding="utf-8-sig")).get("log", [])
        except (OSError, ValueError): log = []
        json.dump({"problems": probs, "log": log + [{"when": time.strftime("%Y-%m-%d %H:%M"), "baseline": reason or "first record"}]},
                  open(bpath(cfg), "w"), indent=1, sort_keys=True)
        import steps as SP
        SP.recorded(cfg, [bpath(cfg)])                # through the kit's record door (review 6, F265)
        print(f"ASSETS: record written: {len(probs)} older problem(s) of {n} asset file(s) to fill in over time."); return 0
    ok, rep = check(cfg); print(rep)
    return 0 if ok else 1


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

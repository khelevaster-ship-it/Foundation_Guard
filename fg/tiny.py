"""FoundationGuard tiny-file check (AI-made, Claude, 2026-11-09).
Size limits can be dodged by chopping messy code into many small, pointless files. This stops a push that adds more than
`tiny_rise` (default 5) new tiny source files (under `tiny_lines`, default 25 code lines) since the last passed push.
A real split into a few medium files is fine; so is adding a handful of small files.
  python fg/tiny.py                 check (the push gate runs this)
  python fg/tiny.py --baseline "owner's words"   accept today's tiny files (guarded: needs the owner's OK)
The list of tiny files at the last pass lives in .foundationguard/tiny_files.json (a guard file)."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

COMMENT = re.compile(r"^\s*(?://|#|/\*|\*|--|;)")


def code_lines(text):
    return sum(1 for l in text.split("\n") if l.strip() and not COMMENT.match(l) and l.strip() not in ("{", "}", "};", "pass"))


def new_tiny(before, after, tiny_lines=25):
    """before: set of files that were tiny (or {path: lines}); after: {path: code lines}. -> sorted new tiny files."""
    was = set(p for p, n in before.items() if n < tiny_lines) if isinstance(before, dict) else set(before)
    return sorted(p for p, n in after.items() if n < tiny_lines and p not in was)


def decide(before, after, tiny_lines=25, rise=5):
    if os.environ.get("FG_BREAK", "") == "tiny_rise":
        return False, []
    nt = new_tiny(before, after, tiny_lines)
    return len(nt) > rise, nt


def current(cfg):
    import structure as ST
    s = dict(ST.DEFAULTS)
    s.update(cfg.get("structure") or {})          # a structure section without include or exclude uses the defaults (F082)
    if os.environ.get("FG_BREAK", "") == "tiny_defaults":
        s = cfg.get("structure") or {}
    out = {}
    code_ext = (".py", ".gd", ".cs", ".cpp", ".h", ".hpp", ".c", ".cc", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".rs", ".go", ".java", ".kt",
                ".lua", ".swift", ".m", ".mm", ".inl")
    for p in ST.files(cfg, s):
        if not p.lower().endswith(code_ext) and os.environ.get("FG_BREAK", "") != "tiny_code_only":
            continue                                       # docs, settings and data files aren't code
        try:
            out[p] = code_lines(open(os.path.join(cfg["_root"], p), encoding="utf-8", errors="replace").read())
        except OSError:
            pass
    return out


def state_path(cfg):
    return os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"), "tiny_files.json")


def check(cfg, save=False):
    if not cfg.get("structure"):
        return True, "TINY skipped (no structure settings)"
    now = current(cfg); sp = state_path(cfg); tl = cfg.get("tiny_lines", 25); rise = cfg.get("tiny_rise", 5)
    if not os.path.exists(sp):
        if save: json.dump(sorted(p for p, n in now.items() if n < tl), open(sp, "w"), indent=0)
        return True, f"TINY first record: {sum(1 for n in now.values() if n < tl)} tiny files"
    before = set(json.load(open(sp, encoding="utf-8-sig")))
    bad, nt = decide(before, now, tl, rise)
    if bad:
        return False, (f"TINY FAIL: {len(nt)} new tiny files (under {tl} code lines) in one push; more than {rise} looks like code "
                       "chopped up to dodge the size limits. Merge them into files that each do one real job. New tiny files:\n  " +
                       "\n  ".join(nt[:30]))
    if save:
        json.dump(sorted(p for p, n in now.items() if n < tl), open(sp, "w"), indent=0)
    return True, f"TINY ok: {len(nt)} new tiny file(s)"


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    import config as C
    cfg = C.load()
    if "--baseline" in sys.argv:
        i = sys.argv.index("--baseline"); w = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        if len(w) < 8: print('TINY: --baseline needs the owner\'s words'); sys.exit(1)
        os.makedirs(os.path.dirname(state_path(cfg)), exist_ok=True)
        tl = cfg.get("tiny_lines", 25)
        json.dump(sorted(p for p, n in current(cfg).items() if n < tl), open(state_path(cfg), "w"), indent=0)
        import steps as SP
        SP.recorded(cfg, [state_path(cfg)])           # through the kit's record door (review 6, F265)
        print("TINY: today's tiny files accepted: " + w); sys.exit(0)
    ok, msg = check(cfg); print(msg); sys.exit(0 if ok else 1)

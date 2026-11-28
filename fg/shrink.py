"""FoundationGuard shrink rule (AI-made, Claude, 2026-11-28).

The size check (fg/structure.py) stops a listed oversized piece from growing. The shrink rule goes one step further: a
listed piece that an item changes must be smaller by the time that item closes, so every item pays down the pieces it
works in. Run by the upload's size check when it is on, and on its own with: python fg/structure.py --shrink

The pieces are the size check's own list (structure_baseline.json): oversized files, classes and long functions,
tangled functions and repeated blocks. Lines are counted with the copy-paste check's code_lines (fg/design.py), so the two
never disagree about what a code line is.

  Touched       a commit changes a code line inside the piece (comment and blank lines don't count; code that only moves
                between the piece's own files is not a change).
  Item          each commit names its item with a trailer line: "<work_trailer>: <id>" (work on it) or
                "<fix_trailer>: <id>" (a fix). A commit that names none is its own item and closes at once.
  Close         a commit with "<close trailer>: <id>" (done, or waiting on the owner) closes the item. Every piece the
                item touched must then be smaller than when the item first touched it:
                files and classes by shrink_pct of the recorded size or shrink_min_lines, whichever is larger;
                long functions by function_pct; a tangled function ends under the complexity and nesting limits; a
                repeated block is gone. The measure is all lines, but code lines must fall by as much (deleting comments
                earns nothing), and code moved into another listed piece makes that piece owe its own shrink.
  One-line fix  a fix commit that changes one line of a piece (added, removed or replaced) owes nothing.
  Bigger fix    a fix commit must bring a test (it changes a test file). It uploads at once; the growth becomes a
                pay-later line, owed by the piece's own planned cut (the "Owed-by:" line of its map), not by the item.
                Cap: cap_entries open lines or cap_lines owed lines on one piece; at the cap fixes still upload, and
                work on that piece waits for the owner's answer (structure.shrink.cap_answered).
  Books         the room each covered piece has over its recorded size is only what its books hold for it (pay-later
                and one-line lines, and an exact revert of a recorded cut), never fix_room_lines. The books are worked
                out from the history since "since" every run, so nobody can write them by hand; the readable record
                (<git folder>/foundationguard/<record>) is written only by this tool, and a change to it by any other
                hand fails the check. A raised or added number in structure_baseline.json fails unless the same commit
                logged it in STRUCTURE_LOG.md (--baseline or --add, the owner's box) or exactly reverts a recorded cut.
  Kinds         tests, check scripts and off-line tools ("checks" globs, and every test file) stay as before: no growth
                past fix_room_lines, no shrink asked. A piece listed under "retiring" owes nothing until its retiring
                item closes; then, if it is still there, that item owes its shrink.
  Maps          every other listed file, class and long function needs a map in maps_dir: a short Markdown page with
                "Piece: <file|class|function> <name>", "Owed-by: <item>" and "Goes-to: <globs>" lines (where its code
                goes when it is cut), so a forced cut never makes arbitrary helper files.

Config (foundationguard.json, "structure" -> "shrink"):
  "on": false, "since": "<commit>"   the switch and the commit it was switched on at (history before it is not read;
                                     a piece over its recorded size there opens with that excess as a pay-later line)
  "work_trailer": "Item", "fix_trailer": "Fix-for", "close_trailers": ["Item-done", "Item-waits"]
  "close_rows": {"file": "docs/PLAN.md", "row": "<regex with (?P<id>) and (?P<status>)>", "closed": "<regex>"}
                                     optional: a commit that turns an item's row in a plan table to a closed status
                                     (done, or waiting on the owner) closes that item, as a close trailer would
  "shrink_pct": 2, "shrink_min_lines": 25, "function_pct": 10
  "checks": [globs], "not_checks": [globs]    (not_checks wins: a code builder kept with the tools)
  "retiring": [{"pieces": ["function path::Name"], "until": "<item>"}]
  "maps_dir": "docs/maps", "cap_entries": 3, "cap_lines": 40, "cap_answered": [pieces]
  python fg/structure.py --shrink                       the report and the books
  python fg/structure.py --shrink --add PATH "why"      list a file at the line limit, so a fix has room (logged)
"""
import collections, datetime, fnmatch, hashlib, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import design as D
import structure as ST

DEFAULTS = {"on": False, "since": "", "work_trailer": "Item", "fix_trailer": "Fix-for", "close_trailers": ["Item-done", "Item-waits"],
            "shrink_pct": 2, "shrink_min_lines": 25, "function_pct": 10, "checks": [], "not_checks": [], "retiring": [],
            "maps_dir": "docs/maps", "cap_entries": 3, "cap_lines": 40, "cap_answered": [], "record": "shrink_owed.json",
            "close_rows": None}
BOOKS = ("structure_baseline.json", "STRUCTURE_LOG.md")
SIZED = ("file", "class", "function")
BRK = lambda k: os.environ.get("FG_BREAK", "") == k
REVERT = re.compile(r"This reverts commit ([0-9a-f]{7,40})")


def settings(s):
    sh = dict(DEFAULTS); sh.update(s.get("shrink") or {})
    return sh


# ---------- reading the history ----------
class Repo:
    """The project's git history, read once per run (files at a commit are kept, so each is read once)."""

    def __init__(self, root, s):
        self.root, self.s, self.blobs = root, s, {}

    def lines(self, rev, path):
        if (rev, path) not in self.blobs:
            p = ST.git("show", f"{rev}:{path}", cwd=self.root)
            self.blobs[(rev, path)] = p.stdout.split("\n") if p.returncode == 0 else None
        return self.blobs[(rev, path)]

    def baseline(self, rev):
        got = self.lines(rev, self.s["baseline_file"])
        try:
            b = json.loads("\n".join(got)) if got else {}
        except ValueError:
            b = {}
        return {"files": b.get("files") or {}, "classes": b.get("classes") or {}, "functions": b.get("functions") or {},
                "tangle": b.get("tangle") or {}, "duplicates": b.get("duplicates") or {}}

    def commits(self, since):
        """[(sha, parent, message, changed paths)] on the first-parent line from since (not included) to HEAD, oldest first."""
        p = ST.git("log", "--first-parent", "--reverse", "-m", "--name-only", "--format=%x01%H %P%x02%B%x02",
                   f"{since}..HEAD", cwd=self.root)
        out = []
        for rec in p.stdout.split("\x01")[1:]:
            head, msg, names = (rec.split("\x02") + ["", ""])[:3]
            ids = head.split()
            out.append((ids[0], ids[1] if len(ids) > 1 else None, msg, sorted({n for n in names.split("\n") if n.strip()})))
        return out

    def patch_id(self, a, b):
        p = ST.git("diff", a, b, "--", ".", *[f":(exclude){x}" for x in BOOKS], cwd=self.root)
        q = __import__("subprocess").run(["git", "patch-id", "--stable"], cwd=self.root, input=p.stdout, capture_output=True,
                                         text=True, encoding="utf-8", errors="replace")
        return (q.stdout.split() or [None])[0]


def closed_rows(ctx, parent, sha):
    """Items whose row in the plan table this commit turned to a closed status (close_rows)."""
    cr = ctx.sh.get("close_rows")
    if not cr or not parent or BRK("shrink_close_rows"):
        return []
    rx, shut = re.compile(cr["row"]), re.compile(cr["closed"], re.I)
    def table(rev):
        got = {}
        for ln in ctx.repo.lines(rev, cr["file"]) or []:
            m = rx.match(ln)
            if m:
                got[m.group("id").strip()] = bool(shut.match(m.group("status").strip()))
        return got
    old, new = table(parent), table(sha)
    return [x for x, c in new.items() if c and old.get(x) is False]


def trailers(msg, name):
    """The ids named by "<name>: <id>" lines (an id runs to the line's end or the first ": ")."""
    if not name:
        return []
    rx = re.compile(r"^" + re.escape(name) + r":[ \t]*(\S[^\n]*?)[ \t]*$", re.M)
    return [m.group(1).split(": ")[0].strip() for m in rx.finditer(msg)]


# ---------- the pieces ----------
def pieces(base):
    """Every listed piece of a baseline, as "kind name" labels."""
    out = ["file " + p for p in base["files"]] + ["class " + k for k in base["classes"]]
    out += ["function " + k for k in base["functions"]] + ["tangle " + k for k in base["tangle"]]
    return out + ["dup " + k for k in base["duplicates"]]


def recorded(base, label):
    kind, name = label.split(" ", 1)
    v = {"file": base["files"], "class": base["classes"], "function": base["functions"]}.get(kind, {}).get(name)
    return v["lines"] if isinstance(v, dict) else v


def paths_of(label, class_files, followed=None):
    kind, name = label.split(" ", 1)
    if kind == "file":
        return [name]
    if kind == "class":
        return list(class_files.get(name) or [])
    if kind == "dup":
        return sorted(set(name.split(" <-> ")))
    return [(followed or {}).get(label) or name.split("::", 1)[0]]


def _ext(p):
    e = os.path.splitext(p)[1].lower()
    return ".py" if e == ".gd" else e


def _code(lines, p):
    """{line number (1-based): code} of a file, comments, blanks and strings stripped as the copy-paste check does."""
    return dict(D.code_lines(lines, _ext(p), ST.strip_code)) if lines is not None else {}


def _n(lines):
    return len(lines) - (1 if lines and lines[-1] == "" else 0)


EMPTY = {"present": False, "lines": 0, "code": [], "all": [], "cx": 0, "nest": 0}


def _view_file(repo, rev, p):
    lines = repo.lines(rev, p)
    if lines is None:
        return dict(EMPTY)
    n = _n(lines)
    return {"present": True, "lines": n, "code": list(_code(lines, p).values()), "all": lines[:n], "cx": 0, "nest": 0}


def _in_spans(lines, p, spans):
    code = _code(lines, p)
    rows = [k for a, b in spans for k in range(a, b + 1)]
    return [code[k + 1] for k in rows if k + 1 in code], [lines[k] for k in rows if k < len(lines)]


def _view_class(repo, rev, name, files):
    got = dict(EMPTY, code=[], all=[])
    for p in files:
        lines = repo.lines(rev, p)
        if lines is None or _ext(p) not in ST.CLIKE:
            continue
        spans = [(b[3], b[4]) for b in ST.blocks_clike(lines, p, _ext(p), spans=True)
                 if (b[0] == name or ST._class_name(b[0], {name}) == name) and not (b[2] == "method" and BRK("shrink_class_methods"))]
        if spans:
            code, alll = _in_spans(lines, p, spans)
            got = dict(got, present=True, lines=got["lines"] + sum(b - a + 1 for a, b in spans),
                       code=got["code"] + code, all=got["all"] + alll)
    return got


def _function_in(repo, rev, p, name, cfg):
    lines = repo.lines(rev, p)
    if lines is None:
        return None
    import adds as AD
    found = [f for f in ST.function_spans(lines, _ext(p), AD.is_test_file(p, cfg)) if f[0] == name]
    if not found:
        return None
    nm, a, b, cx, nest = max(found, key=lambda f: f[2] - f[1])
    code, alll = _in_spans(lines, p, [(a, b)])
    return {"present": True, "lines": b - a + 1, "code": code, "all": alll, "cx": cx, "nest": nest, "path": p}


def _view_function(repo, rev, label, cfg, where, look):
    """A long or tangled function, at its recorded file or, when it moved, the one other file (of look) that holds a
    function of the same name (the size check follows moved functions the same way, F518)."""
    p, name = where.split("::", 1) if "::" in where else (where, "")
    name = label.split(" ", 1)[1].split("::", 1)[1]
    v = _function_in(repo, rev, p, name, cfg)
    if v or BRK("shrink_follow"):
        return v or dict(EMPTY)
    hits = [x for x in (_function_in(repo, rev, q, name, cfg) for q in look if q != p) if x]
    return hits[0] if len(hits) == 1 else dict(EMPTY)


def _view_dup(repo, rev, name, s):
    a, b = name.split(" <-> ")
    per = {q: D.code_lines(repo.lines(rev, q) or [], _ext(q), ST.strip_code) for q in {a, b}}
    for d in D.duplicates(per, s["min_duplicate_lines"]):
        if ST.dup_key(d) == name:
            code = [c for q, x, y in ((d[0], d[1], d[2]), (d[3], d[4], d[5])) for k, c in per[q] if x <= k <= y]
            return {"present": True, "lines": d[6], "code": code, "all": code, "cx": 0, "nest": 0}
    return dict(EMPTY)


def view(ctx, rev, label, look=()):
    """What a piece is at a commit: present?, its lines, its code lines' text, its complexity."""
    kind, name = label.split(" ", 1)
    if kind == "file":
        return _view_file(ctx.repo, rev, name)
    if kind == "class":
        return _view_class(ctx.repo, rev, name, ctx.class_files.get(name) or [])
    if kind == "dup":
        return _view_dup(ctx.repo, rev, name, ctx.s)
    where = ctx.followed.get(label, name.split("::", 1)[0]) + "::" + name.split("::", 1)[1]
    v = _view_function(ctx.repo, rev, label, ctx.cfg, where, look)
    if v.get("path"):
        ctx.followed[label] = v["path"]
    return v


def summary(v):
    return {"present": v["present"], "lines": v["lines"], "code": len(v["code"]), "cx": v["cx"], "nest": v["nest"]}


def _h(lines):
    return [hashlib.sha1(x.strip().encode("utf-8", "surrogatepass")).hexdigest()[:12] for x in lines]


# ---------- kinds and maps ----------
def kind_of(ctx, label):
    """("checks"|"retiring"|"code", retiring item or None)."""
    if BRK("shrink_kinds"):
        return "code", None
    for r in ctx.sh["retiring"]:
        if label in (r.get("pieces") or []):
            return "retiring", r.get("until")
    import adds as AD
    ps = paths_of(label, ctx.class_files, ctx.followed)
    chk = lambda p: (AD.is_test_file(p, ctx.cfg) or ST.match(p, ctx.sh["checks"])) and not ST.match(p, ctx.sh["not_checks"])
    return ("checks", None) if ps and all(chk(p) for p in ps) else ("code", None)


def load_maps(root, sh):
    """{piece label: {"owed_by", "goes_to", "map"}} from the maps folder's "Piece:", "Owed-by:" and "Goes-to:" lines."""
    d, out = os.path.join(root, sh["maps_dir"]), {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".md"):
            continue
        text = open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        field = lambda k: [m.group(1).strip() for m in re.finditer(r"^" + k + r":[ \t]*(.+)$", text, re.M)]
        owed, goes = (field("Owed-by") or [None])[0], [g.strip() for x in field("Goes-to") for g in x.split(",") if g.strip()]
        for piece in field("Piece"):
            out[piece] = {"owed_by": owed, "goes_to": goes, "map": sh["maps_dir"].rstrip("/") + "/" + f}
    return out


def owed_by(ctx, label):
    k, until = kind_of(ctx, label)
    if k == "retiring":
        return until
    return (ctx.maps.get(label) or {}).get("owed_by")


# ---------- one commit ----------
def _baseline_raises(ctx, before, after):
    """[(label, old, new)] for every number raised and every entry added in the size list by a commit."""
    out = []
    for label in pieces(after):
        kind = label.split(" ", 1)[0]
        if kind in SIZED:
            old, new = recorded(before, label), recorded(after, label)
        elif kind == "tangle":
            old, new = before["tangle"].get(label[7:]), after["tangle"].get(label[7:])
        else:
            old, new = before["duplicates"].get(label[4:]), after["duplicates"].get(label[4:])
        if old is None or _above(new, old):
            out.append((label, old, new))
    return out


def _above(new, old):
    """A recorded number (or a tangled function's [branches, nesting]) raised in any part."""
    if isinstance(new, list):
        return any(n > o for n, o in zip(new, old if isinstance(old, list) else [old] * len(new)))
    return new > old


def _moved_entry(before, label, new):
    """A function entry that only followed its function to another file (the ratchet's F543): same name, gone key."""
    kind, name = label.split(" ", 1)
    if kind not in ("function", "tangle") or "::" not in name:
        return False
    table = before["functions" if kind == "function" else "tangle"]
    fn = name.split("::", 1)[1]
    olds = [v for k, v in table.items() if k.split("::", 1)[1] == fn and k != name]
    return any(not _above(new, v) for v in olds)


def _touches(ctx, sha, parent, changed, base):
    """{label: what the commit did to it} for every listed piece whose code lines it changed."""
    out = {}
    for label in pieces(base):
        if not set(paths_of(label, ctx.class_files, ctx.followed)) & set(changed):
            continue
        b, a = view(ctx, parent, label, changed), view(ctx, sha, label, changed)
        cb, ca = collections.Counter(b["code"]), collections.Counter(a["code"])
        if cb == ca:
            continue
        ab, aa = collections.Counter(b["all"]), collections.Counter(a["all"])
        out[label] = {"before": summary(b), "after": summary(a), "a_all": sum((aa - ab).values()), "r_all": sum((ab - aa).values()),
                      "add": _h(list((ca - cb).elements())), "rem": _h(list((cb - ca).elements()))}
    return out


def event(ctx, sha, parent, msg, changed):
    """Everything the rule needs from one commit (kept in the cache by its id)."""
    sh = ctx.sh
    before, after = ctx.repo.baseline(parent), ctx.repo.baseline(sha)
    ev = {"sha": sha, "parent": parent, "work": trailers(msg, sh["work_trailer"]), "fix": trailers(msg, sh["fix_trailer"]),
          "closes": [x for t in sh["close_trailers"] for x in trailers(msg, t)] + closed_rows(ctx, parent, sha), "touch": {}, "raised": [],
          "logged": False, "revert_of": None, "restore": {}}
    import adds as AD
    ev["test"] = any(AD.is_test_file(p, ctx.cfg) for p in changed)
    log = ST.git("diff", parent, sha, "--", "STRUCTURE_LOG.md", cwd=ctx.root).stdout if parent else ""
    ev["logged"] = bool(re.search(r"^\+.*baseline (written|entry added)", log, re.M))
    ev["raised"] = [r for r in _baseline_raises(ctx, before, after) if not _moved_entry(before, r[0], r[2])]
    m = REVERT.search(msg)
    if m and parent:
        cut = ST.git("rev-parse", "--verify", "-q", m.group(1), cwd=ctx.root).stdout.strip()
        if cut and ctx.repo.patch_id(cut, cut + "^") == ctx.repo.patch_id(parent, sha):
            ev["revert_of"] = cut
            pre = ctx.repo.baseline(cut + "^")
            ev["restore"] = {lb: recorded(pre, lb) for lb in pieces(pre) if lb.split(" ", 1)[0] in SIZED}
    if parent:
        ev["touch"] = _touches(ctx, sha, parent, changed, before)
    ev["followed"] = dict(ctx.followed)
    return ev


# ---------- the books ----------
class Books:
    def __init__(self):
        self.items, self.ledger, self.closed, self.restored, self.bad, self.fixes, self.cards = {}, [], set(), {}, [], 0, []

    def owed_lines(self, label, by=None):
        return sum(e["lines"] for e in self.ledger if e["piece"] == label and (by is None or e["owed_by"] == by))

    def open_lines(self, label):
        return [e for e in self.ledger if e["piece"] == label and e["kind"] != "one-line"]


def _need(label, rec, sh):
    if label.startswith("function "):
        return max(1, int(rec * sh["function_pct"] / 100 + 0.5))
    return max(int(sh["shrink_min_lines"]), int(rec * sh["shrink_pct"] / 100 + 0.5))


def _target(label, st, owed, sh):
    """(lines at most, code lines at most) a sized piece must reach by its item's close."""
    rec = st["recorded"] or st["start"]["lines"]
    base = min(st["start"]["lines"], rec) if owed else st["start"]["lines"]
    top = base - _need(label, rec, sh)
    return top, st["start"]["code"] - (st["start"]["lines"] - top)


def _moved_in(item, label):
    """Code lines added to this piece in the item that another listed piece lost in the same item."""
    mine = collections.Counter(item["pieces"][label]["add"])
    gone = collections.Counter(h for lb, st in item["pieces"].items() if lb != label for h in st["rem"])
    return sum((mine & gone).values())


def paid(ctx, books, x, label, st, end):
    """None when the piece is paid at its item's close, else why not."""
    kind = label.split(" ", 1)[0]
    if not end["present"]:
        return None
    if kind == "tangle":
        ok = BRK("shrink_tangle") or end["cx"] <= ctx.s["max_complexity"] and end["nest"] <= ctx.s["max_nesting"]
        return None if ok else f"still tangled ({end['cx']} branches, nested {end['nest']}; limits {ctx.s['max_complexity']} and {ctx.s['max_nesting']})"
    if kind == "dup":
        return "the two copies are still there: make them one"
    owed = books.owed_lines(label, x)
    top, code_top = _target(label, st, owed, ctx.sh)
    moved, lines, code = _moved_in(books.items[x], label), end["lines"], end["code"]
    if BRK("shrink_move"):
        lines, code = lines - moved, code - moved          # the break: code moved in from another listed piece is not counted
    if lines <= top and (code <= code_top or BRK("shrink_code_lines")):
        return None
    why = f"{end['lines']} lines ({end['code']} code lines); it needs at most {top} ({code_top} code lines)"
    if lines <= top:
        why += ": the lines fell but the code lines did not (deleting comments or blank lines earns nothing)"
    if moved:
        why += (f"; {moved} of its new code lines came out of another listed piece: cut code goes where the piece's "
                f"map says, never into another listed piece")
    return why + (f", {owed} of them pay-later lines it owes" if owed else "")


def _start(ctx, books, x, label, rev):
    it = books.items[x]
    if label not in it["pieces"]:
        it["pieces"][label] = {"start": summary(view(ctx, rev, label)), "recorded": recorded(ctx.repo.baseline(rev), label),
                               "add": [], "rem": []}
    return it["pieces"][label]


def close(ctx, books, x, sha):
    it = books.items.setdefault(x, {"first": sha + "^", "pieces": {}})
    for e in [e for e in books.ledger if e["owed_by"] == x]:
        _start(ctx, books, x, e["piece"], it["first"])
    for label, st in sorted(it["pieces"].items()):
        why = paid(ctx, books, x, label, st, summary(view(ctx, sha, label)))
        if why and not BRK("shrink_close"):
            books.bad.append(f"{sha[:10]}: item {x} closed with a shrink owed on {label}: {why}")
        elif not why:
            books.ledger = [e for e in books.ledger if not (e["piece"] == label and e["owed_by"] == x)]
    books.closed.add(x)
    for r in ctx.sh["retiring"]:
        if r.get("until") == x:
            for label in r.get("pieces") or []:
                ctx.retired.add(label)


def _fix_touch(ctx, books, ev, label, t):
    if kind_of(ctx, label)[0] == "checks":
        return                                            # tests and tools keep the size check's own fix room
    one = (t["a_all"] - t["r_all"] <= 1) if BRK("shrink_one_line_net") else (t["a_all"] <= 1 and t["r_all"] <= 1)
    one = one and not BRK("shrink_one_line")
    if not one and not ev["test"] and not BRK("shrink_fix_test"):
        books.bad.append(f"{ev['sha'][:10]}: a fix that changes {max(t['a_all'], t['r_all'])} lines of {label} (not one line) "
                         f"must bring a test: a fix commit that changes no test file is refused")
        return
    grew = t["after"]["lines"] - t["before"]["lines"]
    if grew > 0 and label.split(" ", 1)[0] in SIZED and not BRK("shrink_paylater"):
        books.ledger.append({"piece": label, "lines": grew, "kind": "one-line" if one else "pay-later", "sha": ev["sha"][:10],
                             "item": ev["fix"][0], "owed_by": owed_by(ctx, label)})


def _work_touch(ctx, books, ev, x, label, t):
    kind, until = kind_of(ctx, label)
    if kind == "checks" or (kind == "retiring" and label not in ctx.retired):
        return
    at_cap = len(books.open_lines(label)) >= ctx.sh["cap_entries"] or books.owed_lines(label) >= ctx.sh["cap_lines"]
    if at_cap and label not in ctx.sh["cap_answered"] and not BRK("shrink_cap"):
        books.bad.append(f"{ev['sha'][:10]}: work on {label} waits: its pay-later lines are at the cap "
                         f"({len(books.open_lines(label))} open, {books.owed_lines(label)} lines); the owner's card: "
                         f"pull its cut forward, yes or no (answer in structure.shrink.cap_answered)")
    st = _start(ctx, books, x, label, ev["parent"])
    st["add"] += t["add"]; st["rem"] += t["rem"]


def _raises(ctx, books, ev):
    if BRK("shrink_raise") or ev["logged"]:
        return
    for label, old, new in ev["raised"]:
        back = ev["revert_of"] and not BRK("shrink_revert") and not _above(new, ev["restore"].get(label) or 0)
        if not back:
            books.bad.append(f"{ev['sha'][:10]}: {label}: its recorded number was {'added' if old is None else 'raised'} "
                             f"({old} -> {new}) by hand; only --baseline or --add (the owner's box, logged in STRUCTURE_LOG.md) "
                             f"or an exact revert of a recorded cut may raise one")


def _restore_room(ctx, books, ev):
    """An exact revert of a recorded cut gives the piece back the room the cut's tightening took."""
    for label, was in ev["restore"].items():
        now = recorded(ctx.repo.baseline(ev["sha"]), label)
        if was and now is not None and was > now:
            books.restored[label] = max(books.restored.get(label, 0), was - now)


def _apply_touches(ctx, books, ev, x):
    """Each touched piece: a fix's books, or the work item's owed shrink. Returns the item the work went to."""
    fix_only = bool(ev["fix"]) and not ev["work"]
    if fix_only and ev["touch"]:
        books.fixes += 1
    for label, t in sorted(ev["touch"].items()):
        if fix_only:
            _fix_touch(ctx, books, ev, label, t)
            continue
        x = x or "commit " + ev["sha"][:10]
        books.items.setdefault(x, {"first": ev["parent"], "pieces": {}})
        _work_touch(ctx, books, ev, x, label, t)
    if x and x not in books.items and not ev["fix"]:
        books.items[x] = {"first": ev["parent"], "pieces": {}}
    return x


def _retiring_owed(ctx, books, ev, x):
    """The item a retiring piece waits for owes that piece's shrink from its first commit on."""
    if x not in books.items or not ev["parent"]:
        return
    for label in [lb for r in ctx.sh["retiring"] if r.get("until") == x for lb in r.get("pieces") or []]:
        _start(ctx, books, x, label, books.items[x]["first"])


def replay(ctx, books, ev):
    """Apply one commit to the books."""
    ctx.followed.update(ev.get("followed") or {})
    _raises(ctx, books, ev)
    if ev["revert_of"] and not BRK("shrink_revert"):
        _restore_room(ctx, books, ev)
        return
    x = _apply_touches(ctx, books, ev, (ev["work"] or ev["fix"] or [None])[0])
    _retiring_owed(ctx, books, ev, x)
    for c in ev["closes"] + ([x] if x and x.startswith("commit ") else []):
        close(ctx, books, c, ev["sha"])


def opening(ctx, books, since):
    """At switch-on, each piece over its recorded size opens a pay-later line for the excess, owed by its planned cut."""
    base = ctx.repo.baseline(since)
    for label in ([] if BRK("shrink_opening") else pieces(base)):
        if label.split(" ", 1)[0] not in SIZED or kind_of(ctx, label)[0] == "checks":
            continue
        over = view(ctx, since, label)["lines"] - recorded(base, label)
        if over > 0:
            books.ledger.append({"piece": label, "lines": over, "kind": "opening", "sha": since[:10], "item": None,
                                 "owed_by": owed_by(ctx, label)})


# ---------- the run ----------
class Ctx:
    def __init__(self, cfg, s, cl):
        self.cfg, self.s, self.root, self.sh = cfg, s, cfg["_root"], settings(s)
        self.repo, self.followed, self.retired = Repo(self.root, s), {}, set()
        self.class_files = {k: v["files"] for k, v in (cl or {}).items()}
        self.maps = load_maps(self.root, self.sh)


def _state(ctx):
    g = C.git_dir(ctx.root)
    return os.path.join(g, "foundationguard") if g else None


def _load_cache(ctx, kit):
    try:
        with open(os.path.join(_state(ctx), "shrink_cache.json"), encoding="utf-8") as f:
            d = json.load(f)
        return d if d.get("kit") == kit else {"record_sha": d.get("record_sha")}
    except (OSError, ValueError, TypeError):
        return {}


def _kit(ctx):
    h = hashlib.sha1(ST._kit_print(ctx.s, ctx.cfg).encode())
    with open(__file__, "rb") as f:
        h.update(f.read())
    h.update(json.dumps(ctx.class_files, sort_keys=True).encode())
    return h.hexdigest()


def _record_text(ctx, books, since):
    owed = {x: {lb: _target(lb, st, books.owed_lines(lb, x), ctx.sh) if lb.split(" ", 1)[0] in SIZED else "under the limits / gone"
                for lb, st in it["pieces"].items()} for x, it in books.items.items() if x not in books.closed}
    return json.dumps({"written_by": "fg/structure.py --shrink (only; any other hand fails the check)", "since": since,
                       "pay_later": books.ledger, "restored": books.restored, "owed": owed}, indent=1, sort_keys=True)


def _keep_record(ctx, books, cache, since):
    """Write the readable record; a record changed since this tool last wrote it fails the check."""
    d = _state(ctx)
    if not d:
        return
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, ctx.sh["record"])
    if os.path.exists(path) and cache.get("record_sha") and not BRK("shrink_record"):
        with open(path, "rb") as f:
            if hashlib.sha1(f.read()).hexdigest() != cache["record_sha"]:
                books.bad.append(f"the pay-later record ({path}) was changed by another hand; only this tool writes it "
                                 f"(it is worked out from the history, and has been written again)")
    text = _record_text(ctx, books, since).encode("utf-8")
    with open(path, "wb") as f:
        f.write(text)
    cache["record_sha"] = hashlib.sha1(text).hexdigest()


def _save_cache(ctx, cache):
    try:
        with open(os.path.join(_state(ctx), "shrink_cache.json"), "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except (OSError, TypeError):
        pass


def _maps_missing(ctx, base):
    if BRK("shrink_maps"):
        return []
    return [f"{lb}: it has no map in {ctx.sh['maps_dir']} (\"Piece: {lb}\", \"Owed-by:\", \"Goes-to:\"): the map comes before "
            f"the rule can force a cut" for lb in pieces(base) if lb.split(" ", 1)[0] in SIZED
            and kind_of(ctx, lb)[0] == "code" and lb not in ctx.maps]


def books_for(cfg, s, cl):
    """(Books, ctx, since) worked out from the history since the switch-on commit."""
    ctx = Ctx(cfg, s, cl); books = Books()
    since = ST.git("rev-parse", "--verify", "-q", (ctx.sh["since"] or "") + "^{commit}", cwd=ctx.root).stdout.strip()
    if not since:
        books.bad.append("the shrink rule is on but structure.shrink.since names no commit (set it to the switch-on commit)")
        return books, ctx, since
    kit = _kit(ctx); cache = _load_cache(ctx, kit); evs = cache.get("events") or {}
    opening(ctx, books, since)
    for sha, parent, msg, changed in ctx.repo.commits(since):
        ev = evs.get(sha) or event(ctx, sha, parent, msg, changed)
        evs[sha] = ev
        replay(ctx, books, ev)
    cache.update(kit=kit, events=evs)
    _keep_record(ctx, books, cache, since)
    _save_cache(ctx, cache)
    return books, ctx, since


def run(cfg, s, cl):
    """([failures], {piece label: room over its recorded size}, [report lines]) for the size check."""
    books, ctx, since = books_for(cfg, s, cl)
    head = ctx.repo.baseline("HEAD") if since else {"files": {}, "classes": {}, "functions": {}, "tangle": {}, "duplicates": {}}
    bad = books.bad + _maps_missing(ctx, head)
    room = {}
    if not BRK("shrink_room"):
        for lb in pieces(head):
            if lb.split(" ", 1)[0] in SIZED and kind_of(ctx, lb)[0] != "checks":
                room[lb] = books.owed_lines(lb) + books.restored.get(lb, 0)
                fol = ctx.followed.get(lb)
                if fol:
                    room["function " + fol + "::" + lb.split("::", 1)[1]] = room[lb]
    return bad, room, report(ctx, books, since)


def report(ctx, books, since):
    open_items = {x: it for x, it in books.items.items() if x not in books.closed and it["pieces"]}
    out = [f"  SHRINK: on since {since[:10]}: {sum(len(i['pieces']) for i in open_items.values())} shrink(s) owed by "
           f"{len(open_items)} open item(s); {len(books.ledger)} pay-later line(s) ({sum(e['lines'] for e in books.ledger)} lines); "
           f"{books.fixes} fix commit(s) touched listed pieces"] if since else []
    for x, it in sorted(open_items.items()):
        for lb, st in sorted(it["pieces"].items()):
            if lb.split(" ", 1)[0] in SIZED:
                top, ct = _target(lb, st, books.owed_lines(lb, x), ctx.sh)
                out.append(f"  OWED by {x}'s close: {lb}: from {st['start']['lines']} lines to at most {top} ({ct} code lines)")
            else:
                out.append(f"  OWED by {x}'s close: {lb}: " + ("under the limits" if lb.startswith("tangle") else "the copies made one"))
    for e in books.ledger:
        out.append(f"  PAY-LATER {e['piece']}: +{e['lines']} line(s) ({e['kind']}, {e['sha']}), owed by "
                   f"{e['owed_by'] or 'its planned cut (no map names it)'}")
    for lb in sorted({e["piece"] for e in books.ledger}):
        if len(books.open_lines(lb)) >= ctx.sh["cap_entries"] or books.owed_lines(lb) >= ctx.sh["cap_lines"]:
            out.append(f"  CARD {lb}: at the cap ({len(books.open_lines(lb))} open, {books.owed_lines(lb)} lines): "
                       f"pull its cut forward, yes or no?" + (" (answered)" if lb in ctx.sh["cap_answered"] else ""))
    return out


# ---------- commands ----------
def add(cfg, s, path, why):
    """List a file that sits at the line limit, so a fix in it has room (the owner's box: the baseline is guarded)."""
    if not why:
        print("SHRINK: adding a file to the list needs a reason: fg/structure.py --shrink --add PATH \"why\""); return 1
    lines = ST._read_lines(cfg, path)
    n = _n(lines) if lines is not None else None
    if n is None or not (s["max_file_lines"] - int(s.get("fix_room_lines", 10)) <= n <= s["max_file_lines"]):
        print(f"SHRINK: {path} is {n} lines; only a file at or just under the limit ({s['max_file_lines']}) is added"); return 1
    bp = ST.baseline_path(cfg, s); base = ST.load_baseline(cfg, s)
    base.setdefault("files", {})[path] = n
    with open(bp, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=1, sort_keys=True)
    with open(os.path.join(cfg["_root"], "STRUCTURE_LOG.md"), "a", encoding="utf-8") as f:
        f.write(f"- {datetime.date.today()}: baseline entry added: {path} at {n} lines. Reason: {why}\n")
    import steps as SP
    SP.recorded(cfg, [bp, os.path.join(cfg["_root"], "STRUCTURE_LOG.md")])
    print(f"SHRINK: {path} listed at {n} lines."); return 0


def main(cfg, s, argv):
    if "--add" in argv:
        i = argv.index("--add"); rest = argv[i + 1:]
        return add(cfg, s, rest[0] if rest else "", " ".join(rest[1:]))
    if not settings(s)["on"]:
        print("SHRINK: off (structure.shrink.on is false)."); return 0
    fl, cl, fn = ST.measure(cfg, s, cached=True)
    bad, room, rep = run(cfg, s, cl)
    print("\n".join([f"SHRINK: {len(bad)} failure(s)."] + ["  FAIL " + b for b in bad] + rep))
    return 1 if bad else 0

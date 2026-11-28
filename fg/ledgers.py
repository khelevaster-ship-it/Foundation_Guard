"""FoundationGuard: a row added to a ledger the owner listed, judged without the owner's box (AI-made, Claude,
2026-11-28; the owner's choice that day: "Yes, after the package" to letting append-only ledger edits through).

The owner lists each ledger and its kind in foundationguard.json:
    "ledgers": {"Docs/TEST_PROOFS.md": "table", "Docs/BREAK_PROOFS.md": "newest_on_top", "Data/Pins/names.json": "pins"}
Each kind passes only an edit that adds and changes nothing that was there (F567):
  - table: new rows in a table already there, each with as many cells as its table and a first cell no row has yet.
    Count lines may change only by the rows added: a "Counts:" line by the added rows of each state (the table's State
    column), a heading's "(N)" by the rows added under it, and a running total (": N" in a prose line, only added to)
    by all the rows added. Every other old line stays the same, byte for byte.
  - newest_on_top: one new section ("## ..." and its lines) put above the first section; nothing else changes.
  - pins: a JSON object whose lists only gain new entries (every old entry the same and in its order, no new name the
    same as an old one); "frozen_at" may change only with an entry added; every other key stays the same.
Anything else still asks, with the plain reason. The gate still runs every check before an upload.
"""
import json, os, re

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

KINDS = ("table", "newest_on_top", "pins")
ROW = re.compile(r"^\s*\|.*\|\s*$")
RULE_ROW = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
HEAD = re.compile(r"^(#+\s.*?)\((\d+)\)\s*$")
COUNTS = re.compile(r"^(\s*Counts?:\s*)(.*?)(\.?\s*)$")
PAIR = re.compile(r"^\s*(.*?)\s+(\d+)\s*$")
TOTAL = re.compile(r": (\d+)\b")


def kind_of(cfg, path):
    """The kind the owner gave this ledger, or None when it isn't listed."""
    import paths as P
    for glob, kind in ((cfg or {}).get("ledgers") or {}).items():
        if P.matches(path, [glob]):
            return kind
    return None


def judge(cfg, path, old, new):
    """None when this edit only adds to a ledger the owner listed; a plain reason when it doesn't; False when the file
    isn't a listed ledger (the other rules judge it then)."""
    kind = kind_of(cfg, path)
    if kind is None or BREAK("ledger_adds"):
        return False
    if not (old or "").strip():
        return "it is a new ledger file; only rows added to one that is there pass without a box"
    if old == new:
        return None
    if kind == "table":
        return _table(old, new)
    if kind == "newest_on_top":
        return _newest_on_top(old, new)
    if kind == "pins":
        return _pins(old, new)
    return "its ledger kind '%s' isn't one the kit knows (%s)" % (kind, ", ".join(KINDS))


def weaker(cfg, path, old, new):
    """The weakening finder's reasons, or none for a change this rule passes: a row added in "not reached" moves its
    count up, which reads as a limit raised to the finder (the box and the upload's yes use this, not the finder)."""
    import weaken as W
    if judge(cfg, path, old, new) is None and not BREAK("ledger_upload"):
        return []
    return W.weaker(path, old, new)


def _cells(l):
    return [c.strip() for c in l.strip().strip("|").split("|")]


def _tables(lines):
    """For each line, its table's header cells (or None) and the heading above it (its index, or None)."""
    out, header, head, prev_row = [], None, None, False
    for i, l in enumerate(lines):
        if l.startswith("#"):
            head = i
        row = bool(ROW.match(l))
        header = (_cells(l) if not prev_row else header) if row else None
        out.append((header, head))
        prev_row = row
    return out


def _table(old, new):
    import difflib
    ol, nl = old.split("\n"), new.split("\n")
    where = _tables(nl)
    added, changed, kept = [], [], []
    firsts = {_cells(l)[0] for l in ol if ROW.match(l) and not RULE_ROW.match(l)}
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ol, nl, autojunk=False).get_opcodes():
        if op == "equal":
            kept += [(nl[j], nl[j], j) for j in range(j1, j2)]
        elif op == "delete" or (op == "replace" and i2 - i1 != j2 - j1):
            return "it changes or removes lines that were there: " + ol[i1].strip()[:80]
        elif op == "replace":
            changed += [(ol[i1 + k], nl[j1 + k], j1 + k) for k in range(i2 - i1)]
        else:
            for j in range(j1, j2):
                why = _new_row(nl, j, where, firsts)
                if why:
                    return why
                firsts.add(_cells(nl[j])[0])
                added.append(j)
    if not added:
        return "it changes lines that were there and adds no row"
    for a, b, j in changed + [k for k in kept if HEAD.match(k[0]) or COUNTS.match(k[0])]:
        why = _count_line(a, b, j, added, nl, where)
        if why:
            return why
    return None


def _new_row(nl, j, where, firsts):
    l, header = nl[j], where[j][0]
    if not ROW.match(l) or RULE_ROW.match(l):
        return "it adds a line that is not a table row: " + l.strip()[:80]
    start = j
    while start > 0 and ROW.match(nl[start - 1]):
        start -= 1
    if start == j:
        return "it adds a row outside a table that is there: " + l.strip()[:80]
    if j <= start + 1 and not BREAK("ledger_strict"):
        return "it adds a row above the table's own first rows: " + l.strip()[:80]
    if len(_cells(l)) != len(header):
        return "a new row has %d cells and its table %d: %s" % (len(_cells(l)), len(header), l.strip()[:80])
    if _cells(l)[0] in firsts and not BREAK("ledger_strict"):
        return "a row for '%s' is there already (a second one could stand in for it)" % _cells(l)[0][:60]
    return None


def _state(nl, j, where):
    header = [h.lower() for h in where[j][0]]
    return _cells(nl[j])[header.index("state")].lower() if "state" in header else None


def _count_line(a, b, j, added, nl, where):
    """None when a count line moved by exactly the rows added (or stayed, with none added for it); else the reason."""
    ha, hb = HEAD.match(a), HEAD.match(b)
    if ha and hb and ha.group(1) == hb.group(1):
        under = sum(1 for k in added if where[k][1] == j)
        return None if int(hb.group(2)) - int(ha.group(2)) == under or BREAK("ledger_counts") else \
            "'%s' goes from %s to %s, but %d rows were added under it" % (ha.group(1).strip(), ha.group(2), hb.group(2), under)
    ca, cb = COUNTS.match(a), COUNTS.match(b)
    if ca and cb:
        return _counts(ca, cb, [_state(nl, k, where) for k in added])
    return _total(a, b, len(added))


def _counts(ca, cb, states):
    if ca.group(1) != cb.group(1) or ca.group(3) != cb.group(3) or None in states:
        return "its counts line changed in a way the kit can't match with the rows added"
    pa = [PAIR.match(p) for p in ca.group(2).split(",")]
    pb = [PAIR.match(p) for p in cb.group(2).split(",")]
    if None in pa or None in pb or [m.group(1) for m in pa] != [m.group(1) for m in pb][:len(pa)]:
        return "its counts line changed in a way the kit can't match with the rows added"
    was = {m.group(1).lower(): int(m.group(2)) for m in pa}
    for m in pb:
        name, n = m.group(1).lower(), int(m.group(2))
        if n - was.get(name, 0) != states.count(name) and not BREAK("ledger_counts"):
            return "the count of '%s' goes from %d to %d, but %d rows were added in that state" % (
                m.group(1), was.get(name, 0), n, states.count(name))
    missing = set(states) - {m.group(1).lower() for m in pb}
    return ("rows were added in a state the counts line doesn't show: " + ", ".join(sorted(missing))) if missing else None


def _total(a, b, n):
    """A prose line may only gain text, and the text it gains must end at the old running total plus the rows added."""
    import difflib
    ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
    if len(ops) != 1 or ops[0][0] != "insert":
        return "it changes a line that was there: " + a.strip()[:80]
    totals, got = TOTAL.findall(a), TOTAL.findall(b[ops[0][3]:ops[0][4]])
    if not totals or len(got) != 1:
        return "it adds words to a line that was there: " + b[ops[0][3]:ops[0][4]].strip()[:80]
    want = max(int(t) for t in totals) + n
    return None if int(got[0]) == want or BREAK("ledger_counts") else \
        "its running total goes to %s, but the old total %s plus the %d rows added is %d" % (got[0], max(totals, key=int), n, want)


def _newest_on_top(old, new):
    ol = old.split("\n")
    first = next((i for i, l in enumerate(ol) if l.startswith("## ")), len(ol))
    top, rest = "\n".join(ol[:first]), "\n".join(ol[first:])
    if not new.startswith(top + "\n" if first else "") or not new.endswith(rest):
        return "it changes or removes lines that were there; only a new section on top passes without a box"
    mid = new[len(top) + 1 if first else 0:len(new) - len(rest)]
    if not mid.strip():
        return "it changes the lines above the first section"
    if not mid.startswith("## ") and not BREAK("ledger_strict"):
        return "the new lines on top don't start a section ('## ...')"
    if not mid.endswith("\n") and rest:
        return "the new section runs into the one below it"
    return None


def _pins(old, new):
    try:
        a, b = json.loads(old), json.loads(new)
    except ValueError:
        return "the kit couldn't read it as JSON"
    if not (isinstance(a, dict) and isinstance(b, dict)) or set(a) != set(b):
        return "it adds or removes a key that was there"
    grew = False
    for k in a:
        if a[k] == b[k] or k == "frozen_at":
            continue
        if not (isinstance(a[k], list) and isinstance(b[k], list)):
            return "it changes '%s'" % k
        why = _grows(k, a[k], b[k])
        if why:
            return why
        grew = True
    if a.get("frozen_at") != b.get("frozen_at") and not grew and not BREAK("ledger_strict"):
        return "it changes 'frozen_at' with no entry added"
    return None if grew else "it changes nothing the kit can count as an add"


def _name(e):
    return json.dumps(e.get("name") if isinstance(e, dict) and "name" in e else e, sort_keys=True)


def _grows(k, a, b):
    """None when list b is list a with new entries put in, every old one the same and in its order."""
    i, new = 0, []
    for x in b:
        if i < len(a) and x == a[i]:
            i += 1
        else:
            new.append(x)
    if i < len(a):
        return "it changes, removes or moves an entry of '%s' that was there: %s" % (k, json.dumps(a[i])[:80])
    names = [_name(e) for e in a]
    for e in new:
        if _name(e) in names and not BREAK("ledger_strict"):
            return "a new entry of '%s' has the name of one that is there: %s" % (k, _name(e)[:60])
        names.append(_name(e))
    return None

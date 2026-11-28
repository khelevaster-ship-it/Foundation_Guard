"""FoundationGuard plain-words cards and the one summary per push (AI-made, Claude, 2026-11-09).

The owner's job is to approve, not to investigate. So every failure the kit can find has a card written by the kit itself
(never by the AI helper): what happened, what it means, and what to do. Most cards say "for the helper": the helper fixes
it and the owner has nothing to decide. Only a few need the owner: new outside software, a licence that forbids selling,
and a change that makes a check weaker. Those say "for you" and recommend an answer.

Every push ends with one summary: "Everything passed. Nothing needs your attention." when that is true, otherwise a short
list with the decisions first. The summary is also written to .foundationguard/last_summary.txt.
"""
import os, re, subprocess

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

HELPER = "Nothing for you to decide: the helper fixes this. Nothing is uploaded until it is fixed."
REJECT = "Reject unless you asked for exactly this. To reject, just tell the helper \"no\"."

# part -> [(pattern on one report line, title, what happened, what it means, recommended, who)]
# "{n}" in a text is the number of report lines of that kind. The first pattern that matches a line wins.
CARDS = {
    "gate": [
        (r"full run .*failed", "The full test run failed after a setup change",
         "Something on this computer changed (for example a Windows update, or a new version of the program the game is built in), so every test ran, and some failed.",
         "That change may have broken something that worked before.", HELPER, "helper"),
        (r"wrote no test report", "The tests left no report",
         "The tests said they passed, but they wrote no report of which tests ran.",
         "Nobody can tell what was tested; an old report must never stand in for this run.", HELPER, "helper"),
        (r"could not run the tests", "The tests couldn't run at all",
         "The game engine (the program the game is built in) couldn't run the tests: the code had a mistake that stopped it from starting, the project didn't open, or the program wasn't signed in to its account.",
         "Nothing was tested, so nobody knows whether anything is broken.", HELPER, "helper"),
        (r"the gate missed \d+ of \d+ steps", "Some of the project's test steps failed",
         "The project's tests run as a list of steps. Every step was run, and the ones listed below failed or could not run.",
         "Something that used to work may be broken now. All the failures are listed at once, so the helper can fix them "
         "together; the next run repeats only these steps and whatever the fix touches.", HELPER, "helper"),
        (r"while it ran, so its result", "A test step changed the project while it ran",
         "One of the test steps changed the project's files, or made a new version, while it was running.",
         "What was tested is no longer what would be uploaded, so the result can't be trusted.", HELPER, "helper"),
        (r"gate_steps:|is tracked by git", "The list of test steps is set up wrongly",
         "The safety tool's list of test steps, or the record it keeps of their results, is not set up properly.",
         "The tests can't be run in a way that can be trusted.", HELPER, "helper"),
        (r"gate failed", "The project's own tests failed",
         "Some of the automatic tests failed on this version.",
         "Something that used to work may be broken now. If you asked for a change in how something works, the helper updates the test; "
         "you still have nothing to do.", HELPER, "helper"),
        (r"lacks its pass line", "The tests didn't say they passed",
         "The test run finished but never printed its 'passed' line.", "The tests may not have run at all.", HELPER, "helper"),
        (r"no gate_command", "No tests are set up", "The safety tool doesn't know how to run the project's automatic tests.",
         "Nothing can be checked, so nothing can be uploaded.", "Nothing for you to decide: the helper runs the safety tool's setup again. Nothing is uploaded until it is fixed.", "helper")],
    "approved": [
        (r": no check named", "An approved feature has no check", "{n} approved feature(s) have no automatic check named.",
         "A feature you approved could break and nobody would notice.", HELPER, "helper"),
        (r": no way to break it", "An approved feature's check can't be proven",
         "{n} approved feature(s) can't be switched off on purpose for a moment, so nobody can prove that their check would notice if they broke.",
         "The check might pass even when the feature is broken.", HELPER, "helper"),
        (r"didn't run", "An approved feature's check didn't run", "{n} check(s) for features you approved didn't run.",
         "The feature might be broken and nobody would know.", HELPER, "helper"),
        (r"failed$", "A feature you approved is broken", "{n} check(s) for features you approved failed.",
         "Something you signed off no longer works.",
         "Nothing for you to decide: the helper fixes this. If the helper says the change was on purpose, say yes only if you asked for it.", "helper"),
        (r"unreviewed checks", "Checks not yet reviewed", "Some checks haven't been looked at by a second helper.",
         "A check written by one helper alone may test the wrong thing.", HELPER, "helper")],
    "structure": [
        (r"tangled", "Code that is too tangled", "{n} piece(s) of code make too many choices, or have choices inside choices inside choices.",
         "Tangled code is where bugs hide; it gets harder to change without breaking something.", HELPER, "helper"),
        (r"^function .*lines", "Pieces of code that are too long", "{n} piece(s) of code are longer than the limit, or grew past the size they had when the limit was set.",
         "This is about how the code is organised, not about what you asked for: long pieces of code are hard to check and easy to break.",
         HELPER, "helper"),
        (r"^class ", "Parts of the code that are too big or too spread out", "{n} part(s) of the code are too big, or spread over too many files.",
         "One part of the code is doing too many jobs, which makes every change riskier.", HELPER, "helper"),
        (r"reaches past a boundary", "One part reaches into another it shouldn't",
         "{n} line(s) in one part of the game use another part's inside workings instead of the agreed way in.",
         "Parts that reach into each other break each other when either changes.", HELPER, "helper"),
        (r"^copy-paste", "Copy-pasted code", "{n} block(s) of code appear in more than one place.",
         "A fix made in one copy is easily missed in the other.", HELPER, "helper"),
        (r"^loop between systems", "Parts that depend on each other in a loop", "{n} loop(s) between parts of the game.",
         "Parts in a loop can't be changed or tested on their own.", HELPER, "helper"),
        (r"lines", "Files that are too big", "{n} file(s) are over the size limit, or grew past the size they had when the limit was set.",
         "Very big files are hard to check and easy to break.", HELPER, "helper")],
    "rules": [
        (r"new dependency", "New outside software", "", "", "", "you"),     # filled in from the dependency's own files
        (r"has \d+ \(was", "More risky maths in the part that must match on every computer",
         "{n} file(s) in the part of the game that must work out the same on every computer now use more maths that can give slightly different answers on different computers.",
         "Saves, replays and multiplayer could drift apart between computers.", HELPER, "helper")],
    "assets": [
        (r"^no_row", "Pictures, sounds or models with no recorded source", "{n} file(s) have no record of where they came from.",
         "Nobody can show the game is allowed to use them.", HELPER, "helper"),
        (r"^bad_licence", "Unknown licence", "{n} entries in the list of the game's pictures, sounds and other files have no licence (the permission to use them) written down, or one the tool doesn't know.",
         "Nobody can say whether the game may use those files.", HELPER, "helper"),
        (r"^by_missing", "Credit details missing", "{n} entries need the maker's name or a web link, which their licence (the permission to use them) requires.",
         "The game would break the licence by not crediting them properly.", HELPER, "helper"),
        (r"^ai_no_tool", "AI-made files without the tool named", "{n} AI-made file(s) don't say which AI tool made them.",
         "The credits must say which tool made them.", HELPER, "helper"),
        (r"^nc_nd_commercial", "A licence that forbids selling or changing", "{n} file(s) have a licence (the permission to use them) that forbids selling them or changing them.",
         "The game is marked as one that will be sold, so these files can't stay in it.",
         "Reject. The helper must replace these files with ones the game may sell.", "you"),
        (r"^bought_no_link", "Bought files without their store page", "{n} bought file(s) have no web link to the shop page or the licence (the permission to use them).",
         "Nobody could show the purchase if asked.", HELPER, "helper")],
    "tiny": [
        (r"TINY FAIL", "Code chopped into many tiny files", "One upload added many very small code files.",
         "This can be a way of getting around the size limits instead of tidying the code.", HELPER, "helper")],
    "secrets": [
        (r"SECRETS FAIL", "A password or key is about to be uploaded", "Some new lines look like a password or a secret key.",
         "Anyone who can see the project could use it.",
         "Nothing is uploaded. The helper takes it out. If it was ever uploaded before, it must also be replaced with a new one.", "helper")],
    "docs": [
        (r"a revert", "Something was undone without a note", "This upload undoes earlier work, but the list of ideas that were tried and dropped wasn't updated.",
         "The next helper may try the same idea again.", HELPER, "helper"),
        (r"code changed but", "Today's notes weren't updated", "The code changed, but the notes the helper leaves for the next helper didn't.",
         "The next helper won't know what changed or what's next.", HELPER, "helper"),
        (r"doesn't mention", "Parts the docs don't mention", "{n} part(s) of the project aren't described in the project's notes.",
         "A new helper won't know they exist or why.", HELPER, "helper"),
        (r"`", "Docs that are no longer true", "{n} line(s) in the project's notes name files, settings or numbers that aren't true any more.",
         "A new helper reading the notes would be misled.", HELPER, "helper")],
    "state": [
        (r"^NOT KEPT", "Saved-game data that is never saved", "{n} piece(s) of the game's state are left out of its save, its load or its fingerprint.",
         "After a load the game may not carry on as it was, or two different worlds may look the same.",
         "Not uploaded. The helper adds them to the save, or writes in foundationguard.json why each one need not be kept.", "helper"),
        (r"^REASON", "A written reason that no longer fits", "{n} reason(s) for leaving state out of the save are stale or too short.",
         "A reason that is out of date hides nothing now, but it tells the next reader something untrue.", HELPER, "helper"),
        (r"^CANNOT CHECK", "The saved-state check could not read a type", "{n} listed type(s) or function(s) were not found.",
         "That type's save is not being checked at all.", HELPER, "helper")],
}

PART_HEAD = {"docs": r"^\s+\S", "state": r"^\s+(?:NOT KEPT|REASON|CANNOT CHECK)\b"}                       # the other parts mark each failure line with FAIL


GATE_LINE = re.compile(r"gate failed|could not run the tests|full run|lacks its pass|no gate_command|the gate missed \d+ of|while it ran, so its result|gate_steps:|is tracked by git")


def _gate_evidence(report):
    lines = [l for l in report.strip().split("\n") if l.strip()]
    if not lines:
        return []
    failing = [l.strip() for l in lines if re.search(r"\bFAILED\b|^FAIL\b|\bError\b|^MISS\b|^NOT RUN\b|^!! ", l.strip())][:8]
    return [next((l for l in lines if GATE_LINE.search(l)), lines[0])] + failing


def _approved_evidence(cfg, report):
    body = report.split("\nREVIEW")[0]
    ev = [l.strip() for l in body.split("\n")[1:] if l.strip()]
    if cfg.get("require_review") and "not reviewed yet" in report:
        ev.append("unreviewed checks: " + report.split("not reviewed yet:")[1].split("\n")[0].strip())
    return ev


def _evidence(cfg, part, report):
    """The kit's own failure lines for one part (the machine evidence a card stands on)."""
    if part == "approved":
        return _approved_evidence(cfg, report)
    if part in ("tiny", "secrets"):
        return [report.strip().split("\n")[0]] if report.strip() else []
    head = PART_HEAD.get(part, r"^\s+FAIL ")
    lines = [l for l in report.split("\n") if re.match(head, l) and not l.strip().startswith(("WARN", "warn", "note:"))]
    return [re.sub(r"^\s+(?:FAIL\s+)?", "", l) for l in lines]


def _card(spec, ev):
    title, happened, means, action, who = spec[1:]
    return {"who": who, "title": title, "happened": happened.format(n=len(ev)), "means": means, "action": action, "evidence": ev}


def _dep_card(cfg, line):
    import depfacts as DF
    m = re.search(r"new dependency (\S+) \(([^)]*)\)", line)
    key, where = (m.group(1), m.group(2)) if m else (line, "")
    f = DF.facts(cfg["_root"], key)
    name = key.partition(":")[2] or key
    risky = f["kind"] in DF.RISKY
    action = (REJECT + " Its licence or source is a risk for the game (see above)." if risky else
              "Allow only if you asked for it. To allow, tell the helper \"allow " + name + "\" in your own words; to reject, just say \"no\".")
    return {"who": "you", "title": f"New outside software: {name}",
            "happened": f"A piece of outside software called '{name}' was added (a {f['what']}, named in {where}).",
            "means": "Facts from the files on this computer (no internet lookup): " + DF.line(f) + ".",
            "action": action, "evidence": [line.split(": needs the owner's OK")[0]]}


def part_cards(cfg, part, report):
    """Cards for one part's failure report, grouped so one kind of problem is one card."""
    if BREAK("cards"):
        return []
    groups, out = {}, []
    if part == "gate":                                      # one card; the failing test names are its evidence
        ev = _gate_evidence(report)
        spec = next((s for s in CARDS["gate"] if ev and re.search(s[0], ev[0])), CARDS["gate"][1])
        return [_card(spec, ev)]
    for ev in _evidence(cfg, part, report):
        spec = next((s for s in CARDS.get(part, []) if re.search(s[0], ev)), None)
        if spec and spec[0] == r"new dependency":
            out.append(_dep_card(cfg, ev)); continue
        groups.setdefault(spec or ("", f"A '{part}' check failed", "{n} problem(s) found.", "See the evidence.", HELPER, "helper"), []).append(ev)
    return out + [_card(s, ev) for s, ev in groups.items()]


def _changed(cfg, rng):
    r = subprocess.run(["git", "diff", "--name-only", rng], cwd=cfg["_root"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [f for f in r.stdout.split("\n") if f]


def _old_new(cfg, rng, path):
    base = rng.split("..")[0]
    old = subprocess.run(["git", "show", f"{base}:{path}"], cwd=cfg["_root"], capture_output=True)
    full = os.path.join(cfg["_root"], path)
    new = open(full, encoding="utf-8", errors="replace").read() if os.path.isfile(full) else ""
    return (old.stdout.decode("utf-8", "replace") if old.returncode == 0 else ""), new


# The game's PC, 21 Nov 13:2x UTC: Docs/TEST_PROOFS.md, a proof record the project's own tools write, was read as "a
# test" because of "TEST_" in its name, so every upload that added a record line asked the owner. A text record outside
# a tests folder is not a test by its name; inside tests/ (golden files, expected values) it still is, and a guard file
# listed in guard_paths still counts, whatever its kind.
TEST_FILE = re.compile((r"(?i)" if os.environ.get("FG_BREAK") == "records_are_tests" else
                        r"(?i)^(?:(?=(?:.*/)?(?:tests?|spec)/)|(?!.*\.(?:md|markdown|txt|rst|adoc|csv|tsv|log|html?)$))(?:.*?)") +
                       r"(?:(?:^|/)(?:tests?|spec)(?:/|_)|test_|_test\.|Tests?\.\w+$|\.spec\.)")


def _weaker_card(f, why):
    more = "; and more" if len(why) > 4 else ""
    return {"who": "you", "title": f"A check was made weaker: {f}", "happened": "; ".join(why[:4]) + more + ".",
            "means": "Something that protects the game will now catch less.", "action": REJECT, "evidence": [f]}


def _kit_is_new(cfg, rng):
    """True when this push is the one that puts the kit into the project. Beginner test (11 Nov): the first upload showed
    14 'a check was made weaker' cards, one for each kit file whose text holds words like 'skip' or 'allowed'."""
    if BREAK("cards_first_install"):
        return False
    base = rng.split("..")[0]
    return subprocess.run(["git", "cat-file", "-e", f"{base}:fg/guard.py"], cwd=cfg["_root"], capture_output=True).returncode != 0


def weaker_cards(cfg, rng):
    """'For you' cards for guard files or tests this push made weaker (a removed check, a raised limit, a skip added)."""
    import config as C, ledgers as LG, paths as P
    if not rng or BREAK("cards_weaker"):
        return []
    globs = C.guard_globs(cfg)
    files = [f for f in _changed(cfg, rng) if P.matches(f, globs) or TEST_FILE.search(f)]
    if _kit_is_new(cfg, rng):                                   # the push that installs the kit: its files have no "before"
        files = [f for f in files if not P.matches(f, ["fg/**"])]
    found = ((f, LG.weaker(cfg, f, *_old_new(cfg, rng, f))) for f in files)
    return [_weaker_card(f, why) for f, why in found if why]


def _approved_check_card(f, why):
    return {
        "who": "you", "title": f"A check for something you approved was changed: {f}",
        "happened": "; ".join(why[:3]) + ".",
        "means": "The helper changed the test that protects a feature you signed off, so it may no longer protect it.",
        "action": "Not uploaded. Say yes only if you asked for this exact change to what you approved; otherwise "
        "tell the helper \"no, put the check back\".", "evidence": [f]}


def approved_check_cards(cfg, rng):
    """A stop, with a 'for you' card, when this push changed or removed the test that guards something the owner approved."""
    if not rng or BREAK("cards_approved_check"):
        return []
    out = []
    import ownerok as OK
    ok = {} if BREAK("approved_check_ok") else OK.given(cfg)
    for f in [f for f in _changed(cfg, rng) if approved_check_file(f)]:
        why = _approved_check_changed(cfg, f, *_old_new(cfg, rng, f))
        if why and not (f in ok and ok[f] == OK._version(cfg["_root"], f)):   # the owner's OK for this very version
            out.append(_approved_check_card(f, why))
    return out


def approved_check_file(f):
    return bool(TEST_FILE.search(f)) or f.endswith((".py", ".cs", ".cpp", ".h", ".gd", ".js", ".ts"))


STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')


def _check_body(text, name):
    """The lines of the test called `name` (an indented block, or up to its closing brace), or None if it isn't there."""
    lines = text.split("\n")
    word = re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])")
    code = (lambda l: l) if BREAK("cards_name_in_string") else (lambda l: STRING.sub('""', l))   # the game, 15 Nov:
    i = next((k for k, l in enumerate(lines) if word.search(code(l)) and not l.lstrip().startswith(("#", "//"))), None)
    # a test's name in a switch's description string was read as the test, and every line after it as its body
    if i is None:
        return None
    head, body = lines[i], [lines[i].strip()]
    if head.rstrip().endswith(":"):                                     # Python-style block
        ind = len(head) - len(head.lstrip())
        for l in lines[i + 1:i + 300]:
            if l.strip() and len(l) - len(l.lstrip()) <= ind:
                break
            body.append(l.strip())
    else:                                                              # braces
        depth, seen = head.count("{") - head.count("}"), "{" in head
        for l in lines[i + 1:i + 300]:
            if seen and depth <= 0:
                break
            body.append(l.strip())
            depth += l.count("{") - l.count("}")
            seen = seen or "{" in l
    return "\n".join(x for x in body if x)


def _is_approved_list(cfg, f):
    a = (cfg.get("approved_file") or "APPROVED.md").replace("\\", "/")
    return f.replace("\\", "/") == a


def _rows_changed(old, new):
    """The rows of the approved list that changed, by id: "approved row A005 was changed (...)"."""
    import approved as A
    def by_id(text):
        out, col = {}, A.FIXED
        for line in (text or "").split("\n"):
            if A._cells(line)[0].lower() == "id":
                col = A.columns(line)
            r = A._row_of(line, col)
            if r:
                out[r["id"]] = r
        return out
    o, n = by_id(old), by_id(new)
    return [f"approved row {k} was changed (\"{n[k]['behaviour'][:60]}\")" for k in o if k in n and o[k] != n[k]]


def _approved_check_changed(cfg, f, old, new):
    """Owner-approved checks are fixed: changing what one tests is the owner's call (weaker-AI test, 11 Nov: a helper
    rewrote both the approved rule's code and its test's expected numbers, and the push went through)."""
    import approved as A
    why = []
    if _is_approved_list(cfg, f) and not BREAK("approved_list_rows"):
        return _rows_changed(old, new)               # the list itself: its rows, by id (the game's PC, 16 Nov: one changed
    if not approved_check_file(f) and not BREAK("approved_list_rows"):    # row was shown as A001-A004, read as checks)
        return []
    for r in A.rows(cfg):
        name = r["check"].split("::")[-1].split(".")[-1].strip("` ")
        if not name or not re.match(r"^[A-Za-z_]\w*$", name):
            continue
        before = _check_body(old, name)
        if before is None:
            continue
        after = _check_body(new, name)
        if after is None:
            why.append(f"the check for something you approved was removed ({r['id']}, {name})")
        elif after != before:
            why.append(f"the check for something you approved was changed ({r['id']}, {name}: \"{r['behaviour'][:60]}\")")
    return why


def _render(c, i):
    who = "FOR YOU" if c["who"] == "you" else "for the helper"
    ev = c["evidence"][:3] + ([f"... and {len(c['evidence']) - 3} more"] if len(c["evidence"]) > 3 else [])
    return "\n".join([f"  {i}. [{who}] {c['title']}", f"     What happened: {c['happened']}", f"     What it means: {c['means']}",
                      f"     Recommended: {c['action']}"] + [f"     For the helper: {e}" for e in ev])


def _n(k, word):
    return f"{k} {word}" + ("" if k == 1 else "s")


def _head(ok, cards):
    mine = sum(1 for c in cards if c["who"] == "you")
    helper = len(cards) - mine
    if not ok:
        return f"NOT UPLOADED. {_n(mine, 'decision')} for you, {_n(helper, 'thing')} for the helper to fix."
    if not cards:
        return "Everything passed. Nothing needs your attention."
    head = (f"The tests passed, BUT {_n(mine, 'thing')} {'needs' if mine == 1 else 'need'} your decision before you say yes."
            if mine else "Passed. Nothing needs your decision.")
    return head + (f" {helper} warning(s) from warn-only parts for the helper; they don't stop uploads." if helper else "")


def summary(ok, cards, uploading=False):
    """The one summary at the end of a push: decisions for the owner first, then the helper's list. uploading (after Four
    @ the Gate, 11 Nov): the upload has not happened yet, so it must not say "Everything passed" before it has."""
    if not ok and not cards:                                 # never "0 things to fix" on a stopped push
        cards = [{"who": "helper", "title": "The upload was stopped", "happened": "A check stopped the upload (see the lines above).",
                  "means": "Something isn't right yet.", "action": HELPER, "evidence": []}]
    cards = sorted(cards, key=lambda c: c["who"] != "you")
    head = _head(ok, cards)
    if ok and uploading and not BREAK("summary_early"):
        head = "The checks passed. Uploading now: the line after this box says whether the upload worked. " + head.replace("Everything passed. ", "")
    label = [] if BREAK("kit_label") else ["FoundationGuard: the kit's report on this upload (not a box from your AI tool)"]
    return "\n".join(["", "=" * 70] + label + ["SUMMARY: " + head] + [_render(c, i) for i, c in enumerate(cards, 1)] + ["=" * 70])


def save(cfg, text):
    sd = os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"))
    try:
        os.makedirs(sd, exist_ok=True)
        open(os.path.join(sd, "last_summary.txt"), "w", encoding="utf-8").write(text.strip() + "\n")
    except OSError:
        pass

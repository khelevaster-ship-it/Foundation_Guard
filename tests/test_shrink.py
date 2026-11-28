"""The shrink rule's own checks (AI-made, Claude, 2026-11-28): fg/shrink.py, run by fg/structure.py.

The twelve planted cases of the rule's plan, and a few more (maps, switch-on, the cap, the tangled and retiring kinds,
--add). Each fails with a "PROOF:" message when its own FG_BREAK key undoes the rule it guards."""
import json, os, subprocess
from test_kit import PY, FG, repo, sh, _commit

LIMITS = {"include": ["**/*.cpp", "**/*.py"], "max_file_lines": 50, "max_class_lines": 10**6, "max_function_lines": 10**6,
          "min_duplicate_lines": 10**6, "base_ref": "none"}


def code(name, n, start=0):
    return "".join(f"int {name}{i} = {i};\n" for i in range(start, start + n))


def comments(n):
    return "".join(f"// note {i}\n" for i in range(n))


def shrink_repo(tmp, files, limits=None, extra=None, maps=None):
    """A project with files listed as oversized, the rule switched on at the commit that listed them, and a map each."""
    tmp.mkdir(parents=True, exist_ok=True)
    cfg = {"structure": dict(LIMITS, **(limits or {}))}
    r = repo(tmp, extra=cfg)
    for p, text in files.items():
        os.makedirs(os.path.dirname(str(r / p)) or ".", exist_ok=True); (r / p).write_text(text)
    for label, owed in (maps if maps is not None else {f"file {p}": "CUT" for p in files}).items():
        (r / "docs" / "maps").mkdir(parents=True, exist_ok=True)
        (r / "docs" / "maps" / (label.split(" ", 1)[1].replace("/", "_").replace(":", "_") + ".md")).write_text(
            f"# Where things go\n\nPiece: {label}\nOwed-by: {owed}\nGoes-to: src/new/**\n")
    _commit(r, "the files")
    assert sh(f'{PY} {FG}/structure.py --baseline "listed"', r).returncode == 0
    _commit(r, "listed")
    since = sh("git rev-parse HEAD", r).stdout.strip()
    cfg["structure"]["shrink"] = dict({"on": True, "since": since}, **(extra or {}))
    (r / "foundationguard.json").write_text(json.dumps(dict(json.loads((r / "foundationguard.json").read_text()), **cfg)))
    _commit(r, "the shrink rule on")
    return r


def check(r):
    return sh(f"{PY} {FG}/structure.py", r)


def put(r, path, text, msg):
    (r / path).write_text(text); _commit(r, msg)


BIG = code("a", 100)


# 1. growth in a touched piece
def test_shrink_growth_in_a_touched_piece_fails_at_once(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    put(r, "A.cpp", BIG + code("x", 1), "work\n\nItem: T1")
    p = check(r)
    assert p.returncode == 1 and "grew to 101" in p.stdout, "PROOF: a listed piece grew a line in an item's work: " + p.stdout


# 2. an item closed with a shrink owed (and one that paid closes)
def test_shrink_an_item_cannot_close_with_a_shrink_owed(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;"), "work\n\nItem: T1")
    p = check(r)
    assert p.returncode == 0 and "OWED by T1's close: file A.cpp: from 100 lines to at most 75" in p.stdout, p.stdout
    _commit(r, "allow empty"); sh('git commit -q --allow-empty -m "done\n\nItem-done: T1"', r)
    p = check(r)
    assert p.returncode == 1 and "item T1 closed with a shrink owed on file A.cpp" in p.stdout, "PROOF: an item closed owing: " + p.stdout
    r2 = shrink_repo(tmp_path / "paid", {"A.cpp": BIG})
    put(r2, "A.cpp", code("a", 75), "cut\n\nItem: T1\nItem-done: T1")
    assert check(r2).returncode == 0, check(r2).stdout


# 3. a comment-only shrink
def test_shrink_deleting_comments_earns_nothing(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG + comments(40)})
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;") + comments(10), "work\n\nItem: T1\nItem-done: T1")
    p = check(r)
    assert p.returncode == 1 and "deleting comments" in p.stdout, "PROOF: a shrink of comments only paid: " + p.stdout


# 4. a move into another listed piece
def test_shrink_code_moved_into_another_listed_piece_is_owed_there(tmp_path):
    b = code("b", 100)
    r = shrink_repo(tmp_path, {"A.cpp": BIG, "B.cpp": b})
    (r / "N.cpp").write_text(code("b", 40)); put(r, "B.cpp", code("b", 60, 40), "B's cut to a new file\n\nItem: T1")
    put(r, "A.cpp", code("a", 70, 30), "A's code moved\n\nItem: T1")
    put(r, "B.cpp", code("b", 60, 40) + code("a", 30), "into B\n\nItem: T1\nItem-done: T1")
    p = check(r)
    assert p.returncode == 1 and "item T1 closed with a shrink owed on file B.cpp" in p.stdout and "another listed piece" in p.stdout, \
        "PROOF: code moved into another listed piece was not owed there: " + p.stdout


# 5. a number raised by hand
def test_shrink_a_recorded_number_raised_by_hand_fails(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    b = json.loads((r / "structure_baseline.json").read_text()); b["files"]["A.cpp"] = 120
    put(r, "structure_baseline.json", json.dumps(b), "more room")
    p = check(r)
    assert p.returncode == 1 and "raised (100 -> 120) by hand" in p.stdout, "PROOF: a raised number passed: " + p.stdout


# 6. an exact revert of a recorded cut (passes)
def test_shrink_an_exact_revert_of_a_recorded_cut_restores_its_number(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    put(r, "A.cpp", code("a", 70, 30), "cut\n\nItem: T1")
    cut = sh("git rev-parse HEAD", r).stdout.strip()
    assert sh(f'{PY} {FG}/structure.py --ratchet "T1 closed"', r).returncode == 0
    _commit(r, "close\n\nItem-done: T1")
    assert json.loads((r / "structure_baseline.json").read_text())["files"]["A.cpp"] == 70
    assert sh(f"git revert --no-edit {cut}", r).returncode == 0
    p = check(r)
    assert p.returncode == 0, "PROOF: the exact revert of a recorded cut was refused: " + p.stdout


# 7. a moved function (no new entry), still owed at its new place
def test_shrink_a_moved_function_is_followed_not_counted_as_a_shrink(tmp_path):
    body = "void Big() {\n" + "".join(f"    int b{i} = {i};\n" for i in range(30)) + "}\n"
    r = shrink_repo(tmp_path, {"A.cpp": body}, limits={"max_file_lines": 10**6, "max_function_lines": 20},
                    maps={"function A.cpp::Big": "CUT"})
    (r / "M.cpp").write_text(body); put(r, "A.cpp", "", "moved\n\nItem: T1")
    p = check(r)
    assert p.returncode == 0, "a moved function failed: " + p.stdout
    put(r, "M.cpp", body.replace("int b3 = 3;", "int b3 = 4;"), "work\n\nItem: T1\nItem-done: T1")
    p = check(r)
    assert p.returncode == 1 and "shrink owed on function A.cpp::Big" in p.stdout, \
        "PROOF: a function that moved file and was changed closed as if it were gone: " + p.stdout
    assert "M.cpp::Big" not in (r / "structure_baseline.json").read_text()


# 8. a one-line fix (passes)
def test_shrink_a_one_line_fix_owes_nothing(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;"), "fix\n\nFix-for: T1")
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;") + code("x", 1), "fix 2\n\nFix-for: T1")
    sh('git commit -q --allow-empty -m "done\n\nItem-done: T1"', r)
    p = check(r)
    assert p.returncode == 0 and "one-line" in p.stdout, "PROOF: a one-line fix was refused or made its item owe: " + p.stdout


# 9. a two-line "one-line" fix (refused)
def test_shrink_a_two_line_fix_is_not_a_one_line_fix(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;").replace("int a6 = 6;", "int a6 = 7;"), "fix\n\nFix-for: T1")
    p = check(r)
    assert p.returncode == 1 and "changes 2 lines of file A.cpp (not one line)" in p.stdout, \
        "PROOF: a two-line fix passed as a one-line fix: " + p.stdout


# 10. a pay-later fix (passes, then shows as owed by the cut, which pays it)
def test_shrink_a_bigger_fix_uploads_with_a_pay_later_line_owed_by_the_cut(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    (r / "tests").mkdir(); (r / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    put(r, "A.cpp", BIG + code("x", 12), "urgent fix\n\nFix-for: T1")
    p = check(r)
    assert p.returncode == 0 and "PAY-LATER file A.cpp: +12 line(s) (pay-later" in p.stdout and "owed by CUT" in p.stdout, \
        "PROOF: a bigger fix with a test was refused or left no pay-later line: " + p.stdout
    put(r, "A.cpp", code("a", 80), "a short cut\n\nItem: CUT\nItem-done: CUT")
    p = check(r)
    assert p.returncode == 1 and "pay-later lines it owes" in p.stdout, p.stdout
    r2 = shrink_repo(tmp_path / "paid", {"A.cpp": BIG})
    (r2 / "test_a.py").write_text("def test_a():\n    assert True\n")
    put(r2, "A.cpp", BIG + code("x", 12), "urgent fix\n\nFix-for: T1")
    put(r2, "A.cpp", code("a", 75), "the cut\n\nItem: CUT\nItem-done: CUT")
    p = check(r2)
    assert p.returncode == 0 and "PAY-LATER" not in p.stdout, p.stdout


# 11. a Fix-for with no test (refused)
def test_shrink_a_bigger_fix_with_no_test_is_refused(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    put(r, "A.cpp", BIG + code("x", 12), "urgent fix\n\nFix-for: T1")
    p = check(r)
    assert p.returncode == 1 and "must bring a test" in p.stdout, "PROOF: a bigger fix with no test passed: " + p.stdout


# 12. a hand edit of the pay-later record (refused)
def test_shrink_a_hand_edit_of_the_pay_later_record_fails(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    assert check(r).returncode == 0
    rec = r / ".git" / "foundationguard" / "shrink_owed.json"
    d = json.loads(rec.read_text()); d["pay_later"] = [{"piece": "file A.cpp", "lines": 400}]; rec.write_text(json.dumps(d))
    p = check(r)
    assert p.returncode == 1 and "changed by another hand" in p.stdout, "PROOF: a hand-written pay-later record passed: " + p.stdout
    assert check(r).returncode == 0                                   # written again from the history


# more: the map comes first
def test_shrink_needs_a_map_for_every_listed_code_piece(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG}, maps={})
    p = check(r)
    assert p.returncode == 1 and "file A.cpp: it has no map" in p.stdout, "PROOF: a piece with no map passed: " + p.stdout


# more: switch-on day, a piece over its record opens a pay-later line
def test_shrink_switch_on_opens_a_pay_later_line_for_each_piece_over_its_record(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    b = json.loads((r / "structure_baseline.json").read_text()); b["files"]["A.cpp"] = 94
    (r / "structure_baseline.json").write_text(json.dumps(b))
    (r / "STRUCTURE_LOG.md").write_text("- baseline written for the test. Reason: x\n"); _commit(r, "re-listed")
    cfg = json.loads((r / "foundationguard.json").read_text())
    cfg["structure"]["shrink"]["since"] = sh("git rev-parse HEAD", r).stdout.strip()
    (r / "foundationguard.json").write_text(json.dumps(cfg)); _commit(r, "on again")
    p = check(r)
    assert p.returncode == 0 and "PAY-LATER file A.cpp: +6 line(s) (opening" in p.stdout, \
        "PROOF: a piece over its record at switch-on failed or opened no pay-later line: " + p.stdout


# more: the cap
def test_shrink_at_the_cap_fixes_upload_and_work_on_that_piece_waits(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG})
    text = BIG
    for k in range(3):
        (r / "test_a.py").write_text(f"def test_a{k}():\n    assert True\n")
        text += code(f"f{k}_", 3); put(r, "A.cpp", text, f"fix {k}\n\nFix-for: T1")
    p = check(r)
    assert p.returncode == 0 and "CARD file A.cpp: at the cap" in p.stdout, p.stdout
    put(r, "A.cpp", text.replace("int a5 = 5;", "int a5 = 6;"), "work\n\nItem: T2")
    p = check(r)
    assert p.returncode == 1 and "work on file A.cpp waits" in p.stdout, "PROOF: work went on at the cap: " + p.stdout


# more: tests and tools are not asked to shrink; a retiring piece owes nothing until its item closes
def test_shrink_kinds_tests_and_retiring_pieces(tmp_path):
    t = code("t", 100)
    r = shrink_repo(tmp_path, {"A.cpp": BIG, "FooTests.cpp": t}, maps={},
                    extra={"retiring": [{"pieces": ["file A.cpp"], "until": "R1"}]})
    put(r, "FooTests.cpp", t.replace("int t5 = 5;", "int t5 = 6;"), "work\n\nItem: T1\nItem-done: T1")
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;"), "work\n\nItem: T2\nItem-done: T2")
    p = check(r)
    assert p.returncode == 0, "PROOF: a test file or a retiring piece was asked to shrink: " + p.stdout
    sh('git commit -q --allow-empty -m "retired?\n\nItem: R1\nItem-done: R1"', r)
    p = check(r)
    assert p.returncode == 1 and "item R1 closed with a shrink owed on file A.cpp" in p.stdout, p.stdout


# more: a tangled function, touched, must end under the limits
def test_shrink_a_touched_tangled_function_ends_under_the_limits(tmp_path):
    body = "int T(int x) {\n" + "".join(f"    if (x == {i}) return {i};\n" for i in range(8)) + "    return 0;\n}\n"
    r = shrink_repo(tmp_path, {"A.cpp": body}, limits={"max_file_lines": 10**6, "max_complexity": 5}, maps={})
    put(r, "A.cpp", body.replace("return 3;", "return 33;"), "work\n\nItem: T1\nItem-done: T1")
    p = check(r)
    assert p.returncode == 1 and "still tangled" in p.stdout, "PROOF: a touched tangled function closed tangled: " + p.stdout


# more: --add lists a file at the limit (logged), so a fix has room
def test_shrink_add_lists_a_file_at_the_limit_with_its_reason(tmp_path):
    r = shrink_repo(tmp_path, {"A.cpp": BIG, "F.cpp": code("f", 50)})
    assert sh(f"{PY} {FG}/structure.py --shrink --add F.cpp", r).returncode == 1          # a reason is needed
    assert sh(f'{PY} {FG}/structure.py --shrink --add F.cpp "a fix needs room"', r).returncode == 0
    assert "baseline entry added: F.cpp at 50 lines" in (r / "STRUCTURE_LOG.md").read_text()
    (r / "docs" / "maps" / "F.md").write_text("Piece: file F.cpp\nOwed-by: CUT\n"); _commit(r, "F listed")
    assert check(r).returncode == 0, check(r).stdout
    assert sh(f'{PY} {FG}/structure.py --ratchet "an item closed"', r).returncode == 0
    assert json.loads((r / "structure_baseline.json").read_text())["files"].get("F.cpp") == 50, \
        "PROOF: the ratchet dropped a file listed at the limit"


# more: a class spread over a header and a .cpp is one piece; a change in either file is a touch
def test_shrink_a_class_is_measured_across_its_files(tmp_path):
    h = "class FBig {\npublic:\n" + "".join(f"    int m{i} = {i};\n" for i in range(40)) + "    void Go();\n};\n"
    c = '#include "Big.h"\nvoid FBig::Go() {\n' + "".join(f"    int g{i} = {i};\n" for i in range(40)) + "}\n"
    r = shrink_repo(tmp_path, {"Big.h": h, "Big.cpp": c}, limits={"include": ["**/*.cpp", "**/*.h"], "max_file_lines": 10**6,
                    "max_class_lines": 50}, maps={"class FBig": "CUT"})
    assert "FBig" in (r / "structure_baseline.json").read_text()
    put(r, "Big.cpp", c.replace("int g7 = 7;", "int g7 = 8;"), "work\n\nItem: T1")
    p = check(r)
    assert p.returncode == 0 and "OWED by T1's close: class FBig: from 86 lines to at most 61" in p.stdout, \
        "PROOF: a change in a class's .cpp was not a touch of the class: " + p.stdout


# more: an item closes when its row in the plan table turns to done (close_rows), with no close trailer
def test_shrink_an_item_closes_when_its_plan_row_turns_done(tmp_path):
    rows = {"file": "PLAN.md", "row": r"^\| (?P<id>[^|]+?) \|.*\| (?P<status>[^|]*?) \|\s*$", "closed": r"(done|waiting)"}
    r = shrink_repo(tmp_path, {"A.cpp": BIG}, extra={"close_rows": rows})
    put(r, "PLAN.md", "| T1 | the work | todo |\n", "plan")
    put(r, "A.cpp", BIG.replace("int a5 = 5;", "int a5 = 6;"), "work\n\nItem: T1")
    assert check(r).returncode == 0
    put(r, "PLAN.md", "| T1 | the work | done 28 Nov |\n", "T1 done")
    p = check(r)
    assert p.returncode == 1 and "item T1 closed with a shrink owed on file A.cpp" in p.stdout, \
        "PROOF: an item marked done in the plan closed without its shrink: " + p.stdout

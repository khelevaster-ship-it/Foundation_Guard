"""FoundationGuard: the project's own tests as guard files, found at setup (AI-made, Claude, 2026-11-13; outside
review 7, Claude, 13 Nov).

Review 7 ran setup the way a new owner does and found that the settings it wrote had no `guard_paths`: the project's
own tests were not guard files at all, so a helper could loosen one with no box and nothing put back. Every earlier
review, and the kit's own tests, had added the test folders by hand. Setup now writes them from what it finds:

  - a folder that holds test files (and nothing but tests and their helpers) is guarded whole: `tests/**`;
  - a test file in a folder of ordinary code is guarded by its name's pattern there (`src/*_test.go`), so editing the
    code beside it doesn't ask;
  - the test runner's own settings, which change what every test does: `conftest.py`, `pytest.ini`, `tox.ini`,
    Godot's `.gutconfig.json`, the Jest, Vitest, Playwright, Mocha and Karma settings, and `pyproject.toml` or
    `setup.cfg` when they hold pytest's own section.

The list is printed in plain words at setup, so the owner can check it.
"""
import os, re, subprocess

import adds as AD

RUNNER = re.compile(r"(^|/)(conftest\.py|pytest\.ini|tox\.ini|\.gutconfig\.json|(jest|vitest|playwright)\.config\.\w+"
                    r"|\.mocharc(\.\w+)?|karma\.conf\.\w+)$")
TESTDIR = re.compile(r"(^|/)(tests?|__tests__|specs?|testing)(/|$)", re.I)
SECTIONS = {"pyproject.toml": "[tool.pytest", "setup.cfg": "[tool:pytest]"}
NAME_FORMS = [(re.compile(r"^test_.*(\.\w+)$"), "test_*{}"), (re.compile(r"^.*_test(\.\w+)$"), "*_test{}"),
              (re.compile(r"^.*\.(test|spec)\.\w+$"), None), (re.compile(r"^.*(Tests?\.\w+)$"), "*{}")]


def _listed(root):
    p = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard"], cwd=root, capture_output=True)
    if p.returncode != 0:
        return []
    return [f for f in p.stdout.decode("utf-8", "replace").split("\0") if f and not f.startswith("fg/")]


def _form(name):
    """The name pattern a test file's name follows (test_*.py, *_test.go, *.test.js ...), or None."""
    for rx, form in NAME_FORMS:
        m = rx.match(name)
        if m:
            if form is None:
                kind = m.group(1)
                return "*." + kind + ".*"
            return form.format(m.group(1))
    return None


def found(root, cfg=None):
    """The guard paths for the tests and the test runner's settings this project has now."""
    files = _listed(root)
    tests = [f for f in files if AD.is_test_file(f, cfg)]
    by_dir = {}
    for f in tests:
        by_dir.setdefault(os.path.dirname(f), []).append(f)
    code = {os.path.dirname(f) for f in files if f.endswith(AD.CODE) and f not in tests and not RUNNER.search(f)}
    out = []
    for d in sorted(by_dir):
        _add_dir(out, d, by_dir[d], code)
    out += [f for f in files if RUNNER.search(f) and not _covered(f, out)]
    out += [n for n, sec in SECTIONS.items() if n in files and sec in _read(os.path.join(root, n))]
    return out


def _add_dir(out, d, tests, code):
    """One folder's tests: the whole test folder, or each test's name pattern where ordinary code lives beside it."""
    if _covered(d + "/", out):
        return                                         # inside a folder already guarded whole
    top = _test_top(d)
    if top or (d and d not in code):
        out.append((top or d) + "/**")
        return
    for f in sorted(tests):
        form = _form(os.path.basename(f))
        g = (d + "/" if d else "") + form if form else f
        if g not in out:
            out.append(g)


def _test_top(d):
    """The folder a test folder starts at (tests/unit -> tests; Source/Game/Tests/Foo -> Source/Game/Tests), so a test
    folder added beside later is guarded too; "" when the path has no test folder in it."""
    m = TESTDIR.search(d)
    return d[:m.end(2)] if m else ""


def _covered(f, out):
    return any(f.startswith(o[:-2]) for o in out if o.endswith("/**"))


def _read(full):
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def words(paths):
    """The list in plain words for the owner."""
    if not paths:
        return ("no test files were found, so no tests are guarded yet. When your helper writes tests, run setup again "
                "(or ask the helper to add their folder to guard_paths in foundationguard.json; the kit's box asks you).")
    return ("these files are now guarded: changing or removing them waits for your OK (adding new tests is free): "
            + ", ".join(paths) + ". If a test folder is missing, ask your helper to add it to guard_paths in "
            "foundationguard.json (the kit's box asks you).")

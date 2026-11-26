"""FoundationGuard test runner for projects using Python's built-in unittest (AI-made, Claude, 2026-11-09).
Runs every test and writes one 'PASS name' / 'FAIL name' line per test to .foundationguard/test_log.txt, so the approved
list can see which checks ran.
  python fg/run_tests.py               all tests (the gate)
  python fg/run_tests.py --only NAME   just the tests whose name ends with NAME (one check)
"""
import os, sys, unittest

def names(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite): yield from names(t)
        else: yield t

def main(argv):
    root = os.getcwd(); sys.path.insert(0, root)
    start = 'tests' if os.path.isdir(os.path.join(root, 'tests')) else '.'
    plain = start == 'tests' and not os.path.exists(os.path.join(root, 'tests', '__init__.py'))   # a plain tests/ folder
    top = os.path.join(root, 'tests') if plain and os.environ.get('FG_BREAK') != 'run_tests_plain' else root  # (the owner's PC, 13 Nov)
    suite = unittest.defaultTestLoader.discover(start, top_level_dir=top)
    tests = list(names(suite))
    broken = [t for t in tests if type(t).__name__ == '_FailedTest']
    if '--only' in argv:
        want = argv[argv.index('--only') + 1]
        tests = [t for t in tests if t.id() == want or t.id().endswith('.' + want)]
        if not tests:
            print(f"FoundationGuard: no test called '{want}' was found. Check the name in APPROVED.md matches a test."); return 1
    res = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
    bad = {t.id() for t, _ in res.failures + res.errors}
    os.makedirs('.foundationguard', exist_ok=True)
    with open(os.path.join('.foundationguard', 'test_log.txt'), 'w') as f:
        for t in tests: f.write(f"{'FAIL' if t.id() in bad else 'PASS'} {t.id()}\n")
    if broken: print("FoundationGuard: some test files couldn't even load (see above). Fix those first.")
    return 0 if res.wasSuccessful() else 1

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))

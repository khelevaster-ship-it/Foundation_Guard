"""The kit's own checks without pytest (AI-made, Claude, 2026-11-11).

The game's PC, 11 Nov: its only Python is the one that comes with the engine, with no pytest, so the kit's own checks
could not run there before the kit was copied into the game. This runs the same checks (tests/test_kit.py) with plain
Python. Each check gets what pytest would give it (a fresh folder as tmp_path, and monkeypatch, undone afterwards). A
check that can't run on this computer (it needs Node.js, or pytest itself) is listed apart, with the commit whose CI
on GitHub to rely on for it.

  python tests/run_without_pytest.py              every check
  python tests/run_without_pytest.py -k NAME      only the checks whose name holds NAME ("A or B": either)
  python tests/run_without_pytest.py -x           stop at the first failure
  python tests/run_without_pytest.py --file PATH  another file of checks
"""
import importlib.util, inspect, os, shutil, subprocess, sys, tempfile, time, traceback, types
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
NEEDS_PYTEST = ("No module named pytest", "No module named 'pytest'")
_GONE = object()


class Skipped(Exception):
    """pytest.skip() inside a check: it can't run on this computer."""


class MonkeyPatch:
    """The part of pytest's monkeypatch the kit's checks use, undone after each check."""

    def __init__(self):
        self._undo = []

    def setattr(self, obj, name, value):
        old = getattr(obj, name, _GONE)
        self._undo.append(lambda: delattr(obj, name) if old is _GONE else setattr(obj, name, old))
        setattr(obj, name, value)

    def setenv(self, name, value):
        old = os.environ.get(name)
        self._undo.append(lambda: _put_env(name, old))
        os.environ[name] = str(value)

    def delenv(self, name, raising=True):
        if name not in os.environ and raising:
            raise KeyError(name)
        old = os.environ.pop(name, None)
        self._undo.append(lambda: _put_env(name, old))

    def undo(self):
        for f in reversed(self._undo):
            f()
        self._undo = []


def _put_env(name, value):
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class _Mark:
    """pytest.mark.skipif(cond, reason=...) and pytest.mark.skip(reason=...) as decorators."""

    @staticmethod
    def skipif(cond, reason=""):
        def put(fn):
            if cond:
                fn.not_here = reason or "skipped"
            return fn
        return put

    def skip(self, reason=""):
        return self.skipif(True, reason)


def _stand_in_pytest():
    """What the checks take from pytest itself: skip, mark.skipif and raises."""
    m = types.ModuleType("pytest")

    def skip(reason=""):
        raise Skipped(reason)

    class raises:
        def __init__(self, kind):
            self.kind = kind

        def __enter__(self):
            return self

        def __exit__(self, kind, value, tb):
            if kind is None:
                raise AssertionError(f"did not raise {self.kind.__name__}")
            return issubclass(kind, self.kind)

    m.skip, m.raises, m.mark = skip, raises, _Mark()
    sys.modules["pytest"] = m


def _checks(path, word):
    spec = importlib.util.spec_from_file_location("kit_checks", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec.loader.exec_module(mod)
    return [(n, f) for n, f in vars(mod).items()
            if n.startswith("test_") and inspect.isfunction(f) and f.__module__ == mod.__name__
            and (not word or any(w.strip() in n for w in word.split(" or ")))]


def _given(fn, folder, mp):
    """What the check asks for by name: tmp_path, monkeypatch."""
    if BREAK("plain_run"):
        return {}
    if getattr(fn, "not_here", None):
        raise Skipped(fn.not_here)
    have = {"tmp_path": folder, "monkeypatch": mp}
    want = list(inspect.signature(fn).parameters)
    missing = [w for w in want if w not in have]
    if missing:
        raise Skipped(f"needs pytest's {', '.join(missing)}")
    return {w: have[w] for w in want}


class _Quiet:
    """What a check prints, and what the programs it runs print, is kept and shown only if it fails, as pytest does."""

    def __enter__(self):
        sys.stdout.flush(); sys.stderr.flush()
        self.f, self.saved, self.text = tempfile.TemporaryFile(), [os.dup(1), os.dup(2)], ""
        os.dup2(self.f.fileno(), 1); os.dup2(self.f.fileno(), 2)
        return self

    def __exit__(self, *exc):
        sys.stdout.flush(); sys.stderr.flush()
        os.dup2(self.saved[0], 1); os.dup2(self.saved[1], 2)
        for fd in self.saved:
            os.close(fd)
        self.f.seek(0)
        self.text = self.f.read().decode("utf-8", "replace")
        self.f.close()


def _outcome(fn, folder, mp):
    try:
        fn(**_given(fn, folder, mp))
        return "ok", ""
    except Skipped as e:
        return "skip", str(e) or "skipped"
    except KeyboardInterrupt:
        raise
    except BaseException as e:                             # a check's failure, whatever it raised
        text = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        if any(n in text for n in NEEDS_PYTEST):
            return "skip", "needs pytest on this computer"
        return "FAIL", text


def run_one(name, fn):
    """('ok' | 'skip' | 'FAIL', what to say)."""
    folder = Path(tempfile.mkdtemp(prefix=name[:40] + "_")).resolve()
    mp, cwd, q = MonkeyPatch(), os.getcwd(), _Quiet()
    try:
        with q:
            state, said = _outcome(fn, folder, mp)
    finally:
        mp.undo()
        os.chdir(cwd)
        shutil.rmtree(folder, ignore_errors=True)
    if state == "FAIL" and q.text.strip():
        said += "--- what it printed ---\n" + q.text[-4000:]
    return state, said


def _commit():
    try:
        p = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=TOP, capture_output=True, text=True)
        return p.stdout.strip() or "this copy's commit"
    except OSError:
        return "this copy's commit"


def summary(done):
    ok = sum(1 for _, s, _ in done if s == "ok")
    bad = [n for n, s, _ in done if s == "FAIL"]
    skip = [(n, why) for n, s, why in done if s == "skip"]
    lines = [f"FoundationGuard: {ok} of {len(done)} kit checks passed here, {len(bad)} failed, {len(skip)} could not run "
             "on this computer."]
    lines += ["  FAILED   " + n for n in bad]
    lines += [f"  not run  {n}: {why}" for n, why in skip]
    if skip:
        lines.append(f"For the checks not run here, rely on the kit's CI for this same commit ({_commit()}): its green "
                     "ticks on GitHub, from computers that have pytest and Node.js.")
    return "\n".join(lines)


def main(argv):
    word = argv[argv.index("-k") + 1] if "-k" in argv[:-1] else None
    path = argv[argv.index("--file") + 1] if "--file" in argv[:-1] else os.path.join(HERE, "test_kit.py")
    _stand_in_pytest()
    os.chdir(TOP)
    done = []
    for name, fn in _checks(path, word):
        t = time.time()
        state, said = run_one(name, fn)
        done.append((name, state, said))
        print(f"  {state:4}  {name} ({time.time() - t:.1f} s)" + (f": {said}" if state == "skip" else ""), flush=True)
        if state == "FAIL":
            print(said, flush=True)
            if "-x" in argv:
                break
    print(summary(done))
    return 1 if any(s == "FAIL" for _, s, _ in done) or not done else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""FoundationGuard web test runner (AI-made, Claude, 2026-11-11). Runs a web project's own tests and writes one JUnit
report, so the approved list can see which checks ran and passed. Setup puts it in the gate for a web project.
  python fg/webtests.py                 every test (the gate)
  python fg/webtests.py --only NAME     just the test called NAME (one check); passes only if it ran and passed
  python fg/webtests.py --in FOLDER     the web project sits in FOLDER, one down from the top
What it runs, as the project has them:
  Node's own test runner   test files that import "node:test" (comes with Node.js, nothing to install)
  Vitest                   when package.json lists vitest
  Playwright               when there is a playwright.config file (tests in a real browser)
  npm test                 when package.json's test script also runs something else (Jest, a linter); it gives no report
A test is known by its own title, without its file or describe blocks around it ("tide rises", not "sim > tide rises").
Tools are started with npx --no-install, so nothing is downloaded: install the project's packages first (npm ci).
"""
import json, os, re, subprocess, sys, xml.etree.ElementTree as ET

REPORT = ".foundationguard/junit.xml"
NAMES = {"node": "Node's test runner", "vitest": "Vitest", "playwright": "Playwright", "npm": "npm test"}
BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
NODE_TEST = re.compile(r"""(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*\(?\s*)["']node:test["']""")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "coverage", ".foundationguard", "fg", "playwright-report", "test-results"}
PLACEHOLDER = "no test specified"                     # npm init's test script, which only fails
TOOL = {"node": r"node\s+(?:--\S+\s+)*--test\b", "vitest": r"vitest\b", "playwright": r"playwright\s+test\b"}


def say(x): print("FoundationGuard: " + x)


def _pkg(d):
    try: j = json.load(open(os.path.join(d, "package.json"), encoding="utf-8-sig"))
    except (OSError, ValueError): return set(), {}
    if not isinstance(j, dict): return set(), {}
    deps = {k for sec in ("dependencies", "devDependencies") for k in (j.get(sec) or {})}
    return deps, (j.get("scripts") or {})


def node_files(d):
    """Test files that use Node's own test runner (they import "node:test")."""
    out = []
    for top, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        for f in sorted(x for x in files if x.endswith((".js", ".mjs", ".cjs"))):
            try: t = open(os.path.join(top, f), encoding="utf-8", errors="replace").read(200000)
            except OSError: continue
            if NODE_TEST.search(t): out.append(os.path.relpath(os.path.join(top, f), d).replace(os.sep, "/"))
    return out


def _covered(script, found):
    """True when npm's test script only runs tools already found (running it as well would run the tests twice)."""
    parts = [x.strip() for x in re.split(r"&&|;|\|\|", script) if x.strip()]
    return bool(found) and all(any(re.match(r"(?:npx\s+)?" + TOOL[k], x) for k in found) for x in parts)


def kinds(d):
    """Which of the test tools the project at d has, in the order they run."""
    if BREAK("web_tests"):
        return []
    deps, scripts = _pkg(d)
    found = (["node"] if node_files(d) else []) + (["vitest"] if "vitest" in deps else [])
    if any(os.path.isfile(os.path.join(d, "playwright.config." + e)) for e in ("ts", "js", "mjs", "cjs", "mts", "cts")):
        found.append("playwright")
    test = scripts.get("test", "")
    if test and PLACEHOLDER not in test and not _covered(test, found):
        found.append("npm")
    return found


def _q(s):
    return '"' + s.replace('"', '\\"') + '"'


def _js_re(name):
    return re.sub(r"([.*+?^${}()|\[\]\\/])", r"\\\1", name)


def _step(k, d, out, only):
    """(command, extra environment, report file or None) for one tool."""
    if k == "node":
        pat = f" --test-name-pattern={_q('^' + _js_re(only) + '$')}" if only else ""
        return ("node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit "
                f"--test-reporter-destination={_q(out)}{pat} " + " ".join(_q(f) for f in node_files(d)), {}, out)
    if k == "vitest":
        pat = f" -t {_q(_js_re(only))}" if only else ""
        return (f"npx --no-install vitest run --reporter=default --reporter=junit --outputFile.junit={_q(out)}{pat}", {}, out)
    if k == "playwright":
        pat = f" -g {_q(_js_re(only))}" if only else ""
        return ("npx --no-install playwright test --reporter=list,junit" + pat,
                {"PLAYWRIGHT_JUNIT_OUTPUT_FILE": out, "PLAYWRIGHT_JUNIT_OUTPUT_NAME": out}, out)
    return ("npm test" + (f" -- -t {_q(only)}" if only else ""), {}, None)


TITLE_SPLIT = re.compile(r"\s+(?:>|›|»)\s+")


def _own_titles(suite):
    """Each test by its own title; the file and describe blocks go in classname."""
    for tc in suite.iter("testcase"):
        full = tc.get("name") or ""
        parts = TITLE_SPLIT.split(full)
        if len(parts) > 1 and not BREAK("web_report"):
            tc.set("name", parts[-1]); tc.set("classname", ((tc.get("classname") or "") + " " + " > ".join(parts[:-1])).strip())


def _join(reports, dest):
    top = ET.Element("testsuites")
    for f in reports:
        try: t = ET.parse(f).getroot()
        except (OSError, ET.ParseError): continue
        for s in ([t] if t.tag == "testsuite" else list(t)):
            _own_titles(s); top.append(s)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    ET.ElementTree(top).write(dest, encoding="utf-8", xml_declaration=True)


def _ran(dest, only):
    """[passed?] for each test called only in the joined report."""
    got = []
    for tc in ET.parse(dest).getroot().iter("testcase"):
        if tc.get("name") == only:
            got.append(not any(ch.tag in ("failure", "error", "skipped") for ch in tc))
    return got


def _run_tools(found, d, rep, only):
    """Run each tool: (all exited 0?, the reports written, the tools that should have written one and didn't)."""
    ok, reports, quiet = True, [], []
    for k in found:
        out = os.path.join(rep, k + ".xml")
        if os.path.exists(out): os.remove(out)                 # an old report never stands in for this run's
        cmd, env, report = _step(k, d, out, only)
        print(f"FoundationGuard: running {NAMES[k]}: {cmd}", flush=True)
        ok = subprocess.run(cmd, shell=True, cwd=d, env={**os.environ, **env}).returncode == 0 and ok
        if report and os.path.exists(report): reports.append(report)
        elif report: quiet.append(NAMES[k])
    return ok, reports, quiet


def _one_check(dest, only, ok, found):
    """The verdict on one check: it ran (by its own title) and every run of it passed."""
    got = _ran(dest, only)
    if not got and "npm" in found:
        return 0 if ok else 1                                  # npm test gives no report: its exit code is all there is
    if not got:
        say(f"no test called '{only}' ran. Check the name in APPROVED.md matches the test's own title.")
    return 0 if got and all(got) else 1


def run(root, sub, only=None):
    d = os.path.join(root, sub) if sub else root
    rep = os.path.join(root, ".foundationguard", "web"); os.makedirs(rep, exist_ok=True)
    found = kinds(d)
    if not found:
        say("no web tests were found (Node's test runner, Vitest, Playwright or an npm test script)."); return 1
    if not os.path.isdir(os.path.join(d, "node_modules")) and set(found) & {"vitest", "playwright", "npm"}:
        say("the project's packages aren't installed here yet, so its test tools can't start (for the helper: npm ci).")
    ok, reports, quiet = _run_tools(found, d, rep, only)
    dest = os.path.join(root, REPORT); _join(reports, dest)
    if BREAK("web_report"):
        return 0 if ok else 1                                  # as a plain runner would: the exit code alone
    if only:
        return _one_check(dest, only, ok, found)
    if quiet:
        say(", ".join(quiet) + " wrote no test report, so nobody can tell what ran."); return 1
    return 0 if ok else 1


def _arg(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(run(os.getcwd(), _arg(sys.argv, "--in") or "", _arg(sys.argv, "--only")))

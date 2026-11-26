"""The watcher's planted change for card 3 of the watched hour (AI-made, Claude, 2026-11-19; Plan 2 part 6).

Run on the WATCHER's computer at about minute 35, signed in to gh as the watcher's helper account (an account the
tester invited to their project with Write before the clock). It opens a pull request on the tester's project that
removes the test "a save keeps the gold" and says: "Tidying the save tests. Nothing is weakened." That sentence is
false on purpose: the tester passes card 3 by not approving it.

  python plant.py OWNER/PROJECT            push the branch and open the pull request
  python plant.py --url GIT_URL --no-pr    for trying the script: any git address, no pull request

It changes nothing else, and never touches main.
"""
import os, re, subprocess, sys, tempfile

BRANCH = "tidy-save-tests"
SAYS = "Tidying the save tests. Nothing is weakened."
TEST = "test_a_save_keeps_the_gold"
FILE = os.path.join("tests", "test_game.py")


def run(*a, cwd=None):
    p = subprocess.run(a, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit(f"plant: {' '.join(a[:3])} failed:\n{(p.stderr or p.stdout).strip()[-600:]}")
    return p.stdout


def without_the_gold_check(text):
    """The test file without the one test that checks a save keeps the gold. Unchanged text means it wasn't found."""
    return re.sub(r"\n    def " + TEST + r"\(self\):\n(?:        .*\n)+", "\n", text, count=1).replace("\n\n\n    def ", "\n\n    def ")


def main(argv):
    url = argv[argv.index("--url") + 1] if "--url" in argv else None
    repo = next((a for a in argv if "/" in a and not a.startswith("-") and a != url), None)
    if not (url or repo):
        print(__doc__.strip()); return 1
    work = tempfile.mkdtemp(prefix="plant-")
    if url:
        run("git", "clone", "-q", url, work)
    else:
        run("gh", "repo", "clone", repo, work, "--", "-q")
    path = os.path.join(work, FILE)
    old = open(path, encoding="utf-8").read()
    new = without_the_gold_check(old)
    if new == old:
        raise SystemExit(f"plant: {TEST} isn't in {FILE} any more; nothing was pushed")
    open(path, "w", encoding="utf-8", newline="\n").write(new)
    run("git", "checkout", "-q", "-b", BRANCH, cwd=work)
    run("git", "-c", "user.name=helper", "-c", "user.email=helper@example.invalid", "commit", "-qam", SAYS, cwd=work)
    run("git", "push", "-q", "origin", BRANCH, cwd=work)
    if "--no-pr" in argv:
        print(f"plant: pushed {BRANCH} (no pull request asked for)"); return 0
    out = run("gh", "pr", "create", "--repo", repo, "--head", BRANCH, "--title", SAYS, "--body", SAYS, cwd=work)
    print("plant: the pull request is open: " + out.strip().splitlines()[-1])
    print("plant: write down the time. The tester's phone should ring within a minute or two.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

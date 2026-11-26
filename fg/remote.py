"""FoundationGuard on GitHub: the kit's note and check for every pull request, run from main's copy (AI-made, Claude,
2026-11-16; team addendum to Plan 2, merge B; spike rounds 1-3 on a throwaway repo).

The kit's workflow (docs/foundationguard-team.yml) runs this on pull_request_target and on every push to main. main's copy
of the kit runs; the change's commits are fetched and READ AS DATA (git cat-file), never checked out or run.

  python fg/remote.py pr NUMBER        judge one pull request: put the note at the top of its description, ask the
                                       right people to review, post the "FoundationGuard note" check
  python fg/remote.py main-moved       after a push to main: re-count every open pull request; any whose count changed
                                       goes red ("main changed under this") until Update branch asks for a fresh Approve
  python fg/remote.py judge --base SHA --head SHA [--author LOGIN] [--pusher LOGIN] [--previous FILE]
                                       [--codeowners-errors FILE]
                                       the same judgement offline, printed as JSON (for tests and for the owner)

What it judges is the MERGE RESULT: what main would be if this merged now (git merge-tree), so two changes that are each
fine alone can't add up to a weakening unseen. The note says who can approve (from main's CODEOWNERS) and who can't (the
helpers' accounts, whoever opened it, whoever last uploaded to it).

The check goes red only when the kit can't stand behind a green one: the change doesn't merge cleanly, main's CODEOWNERS
isn't what the settings say, GitHub reports errors in it (an invite not yet accepted), a file the kit watches
has nobody to approve it, or main moved and the count changed.
A held change stays green here: GitHub itself withholds the merge until the right person approves (CODEOWNERS + the
ruleset). The token: the kit's own GitHub app (FG_APP_TOKEN) when set up; with only GITHUB_TOKEN the check says it can be
faked by a workflow on the change's branch (spike S3), and fg/lock.py doesn't say ON.
"""
import hashlib, json, os, re, subprocess, sys, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adds as AD
import codeowners as CO
import config as C
import facts as F
import paths as P

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
CHECK = "FoundationGuard note"
START, END = "<!-- foundationguard:note:start -->", "<!-- foundationguard:note:end -->"
COUNT_TAG = re.compile(r"<!-- foundationguard:count (.*?) -->")
MAIN_MOVED = "Main changed under this"
SCREEN = "<!-- foundationguard:screen -->"


# --- what main would be ----------------------------------------------------------------------------------------------
def _git(root, *a, env=None):
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def merge_result(root, base, head):
    """The commit main would have if head merged into base now, or None when the two don't merge cleanly."""
    if BREAK("team_merge_result"):
        return head
    t = _git(root, "merge-tree", "--write-tree", "--no-messages", base, head)
    if t.returncode != 0:
        return None
    tree = t.stdout.split("\n", 1)[0].strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="FoundationGuard", GIT_AUTHOR_EMAIL="fg@example.invalid",
               GIT_COMMITTER_NAME="FoundationGuard", GIT_COMMITTER_EMAIL="fg@example.invalid",
               GIT_AUTHOR_DATE="2000-01-01T00:00:00Z", GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")
    c = _git(root, "commit-tree", tree, "-p", base, "-p", head, "-m", "FoundationGuard: what main would be", env=env)
    return c.stdout.strip() or None


# --- who GitHub asks (main's CODEOWNERS) -----------------------------------------------------------------------------
def _co_regex(pat):
    """A CODEOWNERS pattern as a regex over a path from the project's top (gitignore rules, as GitHub reads them)."""
    anchored = pat.startswith("/") or "/" in pat.rstrip("/")
    p = pat.strip("/")
    out, i = "", 0
    while i < len(p):
        if p.startswith("**", i):
            out += ".*"; i += 2
            if i < len(p) and p[i] == "/":
                out = out[:-2] + "(?:.*/)?"; i += 1
        elif p[i] == "*":
            out += "[^/]*"; i += 1
        elif p[i] == "?":
            out += "[^/]"; i += 1
        else:
            out += re.escape(p[i]); i += 1
    return re.compile(("^" if anchored else "^(?:.*/)?") + out + "(?:/.*)?$")


def owner_lines(text):
    out = []
    for line in (text or "").splitlines():
        line = line.split(" #")[0].strip()
        if not line or line.startswith("#"):
            continue
        pat, *names = line.split()
        out.append((_co_regex(pat) if pat != "*" else re.compile(".*"), names))
    return out


def owners_for(lines, path):
    """The names GitHub asks for this file: the LAST matching line wins; [] when no line, or an empty line, matches."""
    who = []
    for rx, names in lines:
        if rx.match(path):
            who = names
    return who


def who(cfg, co_text, paths, author="", pusher=""):
    """{"groups": [(names, [paths])], "can": [names who could approve it all alone], "cant": [(name, why)],
        "unowned": [watched paths nobody can approve]}"""
    lines = owner_lines(co_text)
    team = CO.team(cfg) or {"bots": []}
    bots = {b.lower() for b in team.get("bots") or []}
    globs = C.guard_globs(cfg)
    groups, unowned = {}, []
    for p in paths:
        names = owners_for(lines, p)
        if not names:
            watched = P.matches(p, globs) or P.matches(p, F.LOCK) or AD.is_test_file(p, cfg)
            if watched and not BREAK("team_unowned_holds"):
                unowned.append(p)
            continue
        groups.setdefault(tuple(names), []).append(p)
    cant = []
    if not BREAK("team_who_from_login"):
        for login, why in ((author, "opened this change"), (pusher, "uploaded the last commit")):
            if login and ("@" + login).lower() not in {n.lower() for n, _ in cant}:
                cant.append(("@" + login, why))
    cant += [(b, "a helper's account") for b in team.get("bots") or [] if b.lower() not in {n.lower() for n, _ in cant}]
    blocked = {n.lower() for n, _ in cant} | bots
    sets = [{n.lower() for n in g} for g in groups]
    every = [n for n in (groups and next(iter(groups)) or ()) if all(n.lower() in s for s in sets)]
    return {"groups": [(list(k), v) for k, v in groups.items()], "can": [n for n in every if n.lower() not in blocked],
            "cant": cant, "unowned": unowned}


# --- the judgement ---------------------------------------------------------------------------------------------------
def previous_count(summary):
    m = COUNT_TAG.search(summary or "")
    return m.group(1) if m else None


def judge(root, base, head, cfg=None, co_text=None, author="", pusher="", previous=None, signed=True, co_errors=()):
    """{"conclusion", "title", "note", "summary", "reviewers", "count"} for a change, against main as it is now."""
    cfg = cfg or C.load(root)
    if co_text is None:
        co_text = F._show(root, base, ".github/CODEOWNERS")[0] or F._show(root, base, "CODEOWNERS")[0]
    red = []
    merged = merge_result(root, base, head)
    if merged is None:
        found, files, paths = [("possible", "this change doesn't merge cleanly into main", "")], 0, []
        red.append("It doesn't merge cleanly into main as it is now. Update the branch, then the kit counts again.")
    else:
        found, files = F.count(root, base, merged, cfg)
        paths = [n or o for o, n in F.changed(root, base, merged)[1]]
    rings, line, facts = F.screen(found, files)
    if CO.team(cfg) is not None and not BREAK("team_codeowners_match"):
        try:
            if not CO.matches(cfg, co_text):
                red.append("main's CODEOWNERS doesn't say what foundationguard.json says, so GitHub may ask the wrong "
                           "people. The owner runs `python fg/codeowners.py` and merges the result.")
        except CO.TeamError as e:
            red.append(f"The team settings on main are wrong: {e}")
    if co_errors and not BREAK("team_codeowners_errors"):
        red.append("GitHub can't use part of CODEOWNERS, so it may not ask the right person: " + "; ".join(
            f"line {e.get('line', '?')}: {(e.get('message') or e.get('kind') or '').splitlines()[0][:140]}" for e in co_errors[:3]) +
            ". Often an invite that hasn't been accepted yet, or someone who no longer has access.")
    w = who(cfg, co_text, paths, author, pusher)
    if w["unowned"]:
        red.append("Nobody is named to approve " + ", ".join(f"`{p}`" for p in w["unowned"][:5]) +
                   (f" and {len(w['unowned']) - 5} more" if len(w["unowned"]) > 5 else "") +
                   ". Name an owner for them in CODEOWNERS (python fg/codeowners.py).")
    # The count kept on the check: the line plus a fingerprint of everything found, so two different weakenings with the
    # same line ("removes 1 check") still differ.
    count = line + " #" + hashlib.sha256(json.dumps(sorted(map(list, found))).encode()).hexdigest()[:12]
    same = (lambda a, b: a.split(" #")[0] == b.split(" #")[0]) if BREAK("team_count_whole") else (lambda a, b: a == b)
    if previous and not same(previous, count) and not BREAK("team_main_moved"):
        red.insert(0, f"{MAIN_MOVED}: when this was last counted the kit said \"{previous.split(' #')[0]}\"; against main "
                      f"now it says \"{line}\" (what it found changed). Press Update branch on the change: that asks for a "
                      "fresh Approve.")
        count = previous                                  # stays red until the branch is updated (a new head)
    lines = [START, "## FoundationGuard", "", facts, ""] + ([SCREEN, ""] if rings else [])
    if red:
        lines += ["**The kit's check is red:**", ""] + [f"- {r}" for r in red] + [""]
    if w["groups"]:
        if w["can"]:
            lines.append("**Who can approve:** " + ", ".join(w["can"]) + " (GitHub asks them; any one of them is enough).")
        else:
            lines.append("**Who can approve:** one person from each group: " +
                         "; ".join(" or ".join(n) + " for " + ", ".join(f"`{p}`" for p in ps[:3]) +
                                   (f" and {len(ps) - 3} more" if len(ps) > 3 else "") for n, ps in w["groups"]) + ".")
    if w["cant"]:
        lines.append("**Who can't:** " + ", ".join(f"{n} ({why})" for n, why in w["cant"]) + ".")
    lines += ["", "_Counted by the kit from main's copy, on what main would be if this merged now. The helper didn't write "
              "this, and edits to it are put back._" + ("" if signed else
              " **Posted without the kit's own app, so a workflow on the change's branch could fake this check.**"), END]
    cant = {n.lower() for n, _ in w["cant"]}
    pick = w["can"][:1] or [next((n for n in names if n.lower() not in cant), "") for names, _ in w["groups"]]
    reviewers = list(dict.fromkeys(n.lstrip("@") for n in pick if n and "/" not in n))[:5]
    summary = facts + "\n\n" + "\n".join(f"- {r}" for r in red) + f"\n\n<!-- foundationguard:count {count} -->"
    title = (red[0].split(":")[0] if red and red[0].startswith(MAIN_MOVED) else
             "Red: " + red[0][:120] if red else line)[:140]
    return {"conclusion": "failure" if red else "success", "title": title, "note": "\n".join(lines),
            "summary": summary[:60000], "reviewers": reviewers, "count": count, "rings": rings, "merged": merged, "base": base,
            "kit": "possible" if {k for k, _, _ in found if k not in F.NOTE} <= {"possible"} else "weakened"}


def screen(j, body, api=None, root=None, cfg=None, last=None, post=None):
    """The held change's note gains the helper's own words, boxed, and the second opinion's line (Plan 2 3.2, 3.3).
    Nothing here changes the check's conclusion: the second opinion can't unlock anything."""
    import opinion as OP
    if not j.get("rings") or SCREEN not in j["note"]:
        return j
    helper = OP.helper_words(body, START, END)
    if BREAK("helper_words_exact"):
        helper = helper.replace("Nothing is weakened", "")
    box = "~~~~"
    shown = helper.replace(box, "~ ~ ~ ~") if not BREAK("helper_words_boxed") else helper
    said = ("**What the helper wrote on this change** (its own words, copied exactly, not checked):\n\n" +
            (f"{box}\n{shown}\n{box}" if shown else "_(nothing)_") +
            "\n\nIf the helper told you something different in chat, that is a reason for Not now.")
    line, keep = OP.OFF, ""
    if OP.on():
        try:
            summaries = () if OP.reuse(last, j["count"]) or api is None else _today_summaries(api)
            lines = OP.material(root, j["base"], j["merged"], cfg or {}) if j.get("merged") else ""
            line, keep = OP.ask(j["kit"], j["count"], j["title"], helper, lines, summaries, last, cfg, post=post)
        except Exception:                                # noqa: BLE001  never in the way of the kit's own count
            line, keep = OP.DOWN, ""
    screen_text = said + "\n\n" + line + "\n\n**Safe choice if unsure: Not now.** Do nothing. The work stays saved; it just waits."
    out = dict(j, note=j["note"].replace(SCREEN, screen_text), summary=j["summary"] + ("\n" + keep if keep else ""))
    if BREAK("opinion_never_unlocks") and line == OP.NO_PROBLEM:
        out.update(title="Safe to approve: removes 0 checks.", reviewers=[])
    return out


def _today_summaries(api, n=20):
    """The kit's last check on the most recently updated pull requests (to count today's second-opinion calls)."""
    out = []
    for pr in api("GET", f"/repos/{{repo}}/pulls?state=all&sort=updated&direction=desc&per_page={n}"):
        try:
            out.append(_last_kit_check(api, pr["head"]["sha"]) or "")
        except RuntimeError:
            pass
    return out


def put_note(body, note):
    """The description with the kit's note at the top. Any old or forged note blocks anywhere in it are taken out first."""
    body = body or ""
    if not BREAK("team_note_replaced"):
        body = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n*", "", body, flags=re.S)
        body = body.replace(START, "").replace(END, "")
    return note + "\n\n" + body.lstrip()


# --- GitHub ----------------------------------------------------------------------------------------------------------
class Api:
    def __init__(self, repo, token, url="https://api.github.com"):
        self.repo, self.token, self.url = repo, token, url

    def __call__(self, method, path, data=None):
        req = urllib.request.Request(self.url + path.replace("{repo}", self.repo), method=method,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "foundationguard"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                t = r.read()
                return json.loads(t) if t else {}
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub said {e.code} to {method} {path}: {e.read()[:300]!r}")


def _fetch(root, number):
    ref = f"refs/foundationguard/pr/{number}"
    r = _git(root, "fetch", "--no-tags", "--quiet", "origin", f"+refs/pull/{number}/head:{ref}")
    return r.returncode == 0


def _last_kit_check(api, sha):
    got = api("GET", f"/repos/{{repo}}/commits/{sha}/check-runs?check_name={CHECK.replace(' ', '%20')}")
    runs = got.get("check_runs", []) if isinstance(got, dict) else []
    mine = [r for r in runs if os.environ.get("FG_APP_ID") and str(r.get("app", {}).get("id")) == os.environ["FG_APP_ID"]] \
        or ([] if os.environ.get("FG_APP_ID") else runs)
    return (mine[0].get("output") or {}).get("summary") if mine else None


def report_only(root):
    """"remote_report_only": true in main's foundationguard.json: the check is always neutral (never blocks), its text
    carries the note, and the description and reviewers are left alone."""
    if BREAK("remote_report_only"):
        return False
    try:
        return bool(C.load(root).get("remote_report_only"))
    except Exception:                                    # noqa: BLE001
        return False


def run_pr(root, api, number, recount=False, signed=True):
    pr = api("GET", f"/repos/{{repo}}/pulls/{number}")
    if pr.get("state") != "open":
        return None
    base = _git(root, "rev-parse", "HEAD").stdout.strip()          # main's copy, checked out by the workflow
    head = pr["head"]["sha"]
    if not _fetch(root, number):
        raise RuntimeError(f"couldn't fetch pull request {number}")
    commits = api("GET", f"/repos/{{repo}}/pulls/{number}/commits?per_page=100")
    last = commits[-1] if commits else {}
    pusher = ((last.get("committer") or {}).get("login") or (last.get("author") or {}).get("login") or "")
    last = _last_kit_check(api, head)
    previous = previous_count(last) if recount else None
    try:
        errs = api("GET", f"/repos/{{repo}}/codeowners/errors?ref={pr['base']['ref']}").get("errors", [])
    except RuntimeError:
        errs = []                                        # no CODEOWNERS at all: the unowned-file rule speaks instead
    j = judge(root, base, head, author=pr["user"]["login"], pusher=pusher, previous=previous, signed=signed, co_errors=errs)
    j = screen(j, pr.get("body"), api, root, C.load(root), last)
    if report_only(root):                       # a first live run (17 Nov): the note is shown, nothing is blocked or changed
        api("POST", "/repos/{repo}/check-runs", {"name": CHECK, "head_sha": head, "status": "completed",
                                                 "conclusion": "neutral",
                                                 "output": {"title": ("Report only. Would be: " + j["conclusion"] + ". "
                                                                      + j["title"])[:140],
                                                            "summary": (j["note"] + "\n\n" + j["summary"])[:60000]}})
        return dict(j, conclusion="neutral")
    body = put_note(pr.get("body"), j["note"])
    if body != (pr.get("body") or ""):
        api("PATCH", f"/repos/{{repo}}/pulls/{number}", {"body": body})
    asked = {u["login"].lower() for u in pr.get("requested_reviewers") or []}
    ask = [r for r in j["reviewers"] if r.lower() not in asked and r.lower() != pr["user"]["login"].lower()]
    if ask and not recount:
        try:
            api("POST", f"/repos/{{repo}}/pulls/{number}/requested_reviewers", {"reviewers": ask})
        except RuntimeError as e:
            print("FG-REMOTE: couldn't ask for a review:", e)
    api("POST", "/repos/{repo}/check-runs", {"name": CHECK, "head_sha": head, "status": "completed",
                                             "conclusion": j["conclusion"],
                                             "output": {"title": j["title"], "summary": j["summary"]}})
    return j


def main(argv):
    root = os.getcwd()
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default
    if argv[:1] == ["judge"]:
        prev = arg("--previous")
        errs = arg("--codeowners-errors")
        j = judge(root, arg("--base", "origin/main"), arg("--head", "HEAD"), author=arg("--author", ""),
                  pusher=arg("--pusher", ""), previous=open(prev).read().strip() if prev else None,
                  co_errors=json.load(open(errs)).get("errors", []) if errs else ())
        print(json.dumps(j, indent=1)); return 0 if j["conclusion"] == "success" else 1
    token = os.environ.get("FG_APP_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        print("FG-REMOTE: runs in the kit's GitHub workflow (needs GITHUB_REPOSITORY and a token)."); return 2
    signed = bool(os.environ.get("FG_APP_TOKEN"))
    api = Api(repo, token)
    if argv[:1] == ["pr"] and len(argv) > 1:
        j = run_pr(root, api, int(argv[1]), signed=signed)
        print(json.dumps({k: j[k] for k in ("conclusion", "title")} if j else {"skipped": "not open"}))
        return 0
    if argv[:1] == ["main-moved"]:
        for pr in api("GET", "/repos/{repo}/pulls?state=open&per_page=100"):
            try:
                j = run_pr(root, api, pr["number"], recount=True, signed=signed)
                print(pr["number"], j and j["conclusion"], j and j["title"])
            except RuntimeError as e:
                print(pr["number"], "FG-REMOTE:", e)
        return 0
    print(__doc__.strip()); return 2


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

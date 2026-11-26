"""FoundationGuard: git's own settings in the check after every step (AI-made, Claude, 2026-11-12; outside review 4,
finding 13).

A helper can switch the push check off, or make git run a program of its own, without touching a single guard file:
a line in git's settings file is enough (`[core] hooksPath = /tmp/h` written into .git/config with the Write tool, or
by any program). The command guard reads only the words of a command, so the owner's rule applies here too: check
what changed, not what was typed. Before each step the kit notes the risky settings (below) in the project's git
settings, its worktree settings and the user's own git settings; after the step, a risky setting a helper added,
changed or removed without the owner's yes is put back, and the helper is told. Ordinary settings (a branch's
upstream, user.name, a new remote, Git LFS's own filter lines) are never judged.

Risky settings: the hooks folder (core.hooksPath), programs git runs (aliases, filters, diff and merge drivers,
fsmonitor, ssh, pager, editors, askpass, gpg, credential helpers), files pulled in (include, includeIf), where an
existing remote points (its url, pushurl and push lines, url.*.insteadOf) and the worktree's place (core.worktree).

Limits: the system-wide git settings (they need the computer's admin) aren't compared; a settings file git can't read
is put back whole from the copy kept at the last check.
"""
import fnmatch, hashlib, os, posixpath, re, shutil, subprocess, time

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

RISKY = ("core.hookspath", "core.fsmonitor", "core.sshcommand", "core.gitproxy", "core.pager", "core.editor",
         "core.askpass", "core.worktree", "sequence.editor", "pager.*", "alias.*", "filter.*", "diff.external",
         "diff.*.textconv", "diff.*.command", "merge.*.driver", "include.path", "includeif.*", "credential.*",
         "gpg.program", "gpg.*.program", "remote.*.url", "remote.*.pushurl", "remote.*.push", "remote.*.receivepack",
         "remote.*.uploadpack", "url.*.insteadof", "url.*.pushinsteadof", "submodule.*.update", "uploadpack.*",
         "http.proxy", "http.*.proxy", "protocol.*.allow", "extensions.worktreeconfig")
# Outside review 6 (Grok, 13 Nov, finding 5): more keys that run a program or move a push, and the same families
WIDE = ("difftool.*.cmd", "difftool.*.path", "mergetool.*.cmd", "mergetool.*.path", "diff.tool", "diff.guitool",
        "merge.tool", "merge.guitool", "core.alternaterefscommand", "interactive.difffilter", "gui.editor",
        "browser.*.cmd", "browser.*.path", "web.browser", "man.*.cmd", "branch.*.pushremote", "remote.pushdefault",
        "remote.*.proxy", "remote.*.vcs", "submodule.*.url", "http.extraheader", "http.*.extraheader", "http.sslverify",
        "http.*.sslverify", "http.curloptresolve", "trailer.*.command", "trailer.*.cmd", "sendemail.*cmd",
        "sendemail.smtpserver", "init.templatedir", "core.attributesfile", "lfs.url", "lfs.pushurl",
        "lfs.customtransfer.*", "lfs.extension.*")
# ...and any key whose last word says it names a program, whatever its section
RUNS = re.compile(r"\.(?:cmd|program|helper|driver|textconv|editor|pager|askpass|[a-z0-9-]*command|[a-z0-9-]*hook)$")
# Keys no step needs judging: never reported when they change (F275)
HARMLESS = ("user.*", "author.*", "committer.*", "branch.*.remote", "branch.*.merge", "branch.*.rebase",
            "branch.*.description", "branch.*.vscode-merge-base", "branch.*.github-pr-*", "remote.*.fetch",
            "remote.*.tagopt", "remote.*.prune", "remote.*.mirror", "init.defaultbranch", "safe.directory",
            "lfs.*.access", "lfs.*.locksverify", "lfs.repositoryformatversion", "core.repositoryformatversion",
            "core.filemode", "core.bare", "core.logallrefupdates", "core.ignorecase", "core.precomposeunicode",
            "core.symlinks", "core.autocrlf", "core.eol", "core.safecrlf", "core.longpaths", "core.quotepath",
            "color.*", "gui.*", "pull.rebase", "pull.ff", "push.default", "push.autosetupremote", "fetch.prune",
            "rerere.enabled", "merge.conflictstyle", "diff.algorithm", "diff.colormoved", "maintenance.*",
            "gc.*", "pack.*", "index.*", "feature.*", "commit.gpgsign", "tag.gpgsign", "gpg.format",
            "credential.*.username", "extensions.objectformat", "submodule.active", "submodule.*.active")
# Outside review 7 (ChatGPT, 13 Nov): git also takes settings from the environment, GIT_CONFIG_COUNT with
# GIT_CONFIG_KEY_0 = core.hooksPath and GIT_CONFIG_VALUE_0 = /dev/null, or GIT_CONFIG_PARAMETERS, so a push skipped the
# push check with no settings file changed. A command that sets them (VAR=, export, env, $env:, set, os.environ) is
# refused, and the kit's own upload drops the ones that switch its hooks off before it runs anything.
ENV_NAMES = r"GIT_CONFIG(?:_COUNT|_KEY_\w*|_VALUE_\w*|_PARAMETERS|_GLOBAL|_SYSTEM|_NOSYSTEM)?"
ENV_SET = re.compile(r"(?<![\w$])(?:\$env:)?" + ENV_NAMES + r"(?![\w])['\"]?\]?\s*(?:[:,]|=(?!=))", re.I)


# Outside review 8 (Grok's round, 13 Nov): PYTEST_ADDOPTS="--deselect ..." python fg/push.py --gate passed with the test
# behind it never run. Settings the test runners read from the environment are refused on a line that runs the kit's
# upload or gate, and fg/push.py drops them before the gate runs.
RUNNER_ENV = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "NODE_OPTIONS", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME",
              "JEST_CONFIG", "VITEST_CONFIG")
RUNNER_SET = re.compile(r"(?<![\w$])(?:\$env:)?(?:" + "|".join(RUNNER_ENV) + r")(?![\w])['\"]?\]?\s*(?:[:,]|=(?!=))", re.I)
UPLOAD = re.compile(r"\b(?:push|prepush|stages|ownerok)\.py\b")
# Round 9 (ChatGPT, 13 Nov): where a proof ran is read from the environment (CI, GITHUB_ACTIONS, CLAUDE_CODE_REMOTE).
# A line that runs the kit's proof or upload commands may not set or clear them.
PROOF_ENV = ("CI", "GITHUB_ACTIONS", "CLAUDE_CODE_REMOTE")
PROOF_KIT = re.compile(r"\b(?:push|prepush|stages|ownerok|receipts|prove|bite|night|alarms|ledger|handoff)\.py\b")
PROOF_SET = re.compile(r"(?<![\w$])(?:\$env:)?(?:" + "|".join(PROOF_ENV) + r")(?![\w])['\"]?\]?\s*(?:[:,]|=(?!=))"
                       r"|(?:\bunset\b|\benv\b[^;&|\n]*?\s-(?:u\s*|-unset[= ]))\s*['\"]?(?:" + "|".join(PROOF_ENV) + r")\b"
                       r"|\benv\b[^;&|\n]*?\s-(?:i|-ignore-environment)\b", re.I)


# Fable's beta plan (14 Nov): FG_BREAK is the kit's own test switch; each value turns one of its checks off. A helper's
# command may not set or clear it (any shell, PowerShell's $env:, env, export, unset, set), whatever the command runs.
BREAK_SET = re.compile(r"(?<![\w$])(?:\$env:)?FG_BREAK(?![\w])['\"]?\]?\s*(?:[:,]|=(?!=))"
                       r"|(?:\bunset\b|\benv\b[^;&|\n]*?\s-(?:u\s*|-unset[= ]))\s*['\"]?FG_BREAK\b"
                       r"|\b(?:export|set|setx|declare|typeset|local)\b[^;&|\n]*\bFG_BREAK\b", re.I)
BREAK_WORDS = ("FG_BREAK is the kit's own test switch: each value turns one of its checks off, so a helper may not "
               "set it; not allowed. Run the command without it.")


PROOF_WORDS = ("setting or clearing CI, GITHUB_ACTIONS or CLAUDE_CODE_REMOTE for the kit's own commands changes where the "
               "kit thinks a proof ran; not allowed. Run the kit's command on its own.")


def _proof_line(cmd):
    return not BREAK("proof_env") and bool(PROOF_KIT.search(cmd)) and bool(PROOF_SET.search(cmd))


def env_settings(cmd):
    """A reason to refuse a command that hands git settings through the environment, or test-runner settings to the
    kit's upload or gate, or None."""
    if BREAK_SET.search(cmd or "") and not BREAK("break_switch_open"):
        return BREAK_WORDS
    if not BREAK("git_env_settings") and ENV_SET.search(cmd or ""):
        return ("setting git's settings through the environment (GIT_CONFIG_...) can switch the push check off; not "
                "allowed. Change a git setting with the owner's yes instead.")
    if _proof_line(cmd or ""):
        return PROOF_WORDS
    if not BREAK("runner_env") and UPLOAD.search(cmd or "") and RUNNER_SET.search(cmd or ""):
        return ("setting the test runner's settings through the environment (PYTEST_ADDOPTS, PYTHONPATH, NODE_OPTIONS "
                "...) for the kit's upload can change which tests the gate runs; not allowed. Run python fg/push.py "
                "on its own.")
    return None


def drop_runner_env(env=None):
    """Remove the test runners' settings from this environment before the gate runs (fg/push.py)."""
    env = os.environ if env is None else env
    for k in [k for k in env if k.upper() in RUNNER_ENV and not BREAK("push_runner_env_kept")]:
        del env[k]
    return env


def drop_env(env=None):
    """Remove the git settings handed in through this environment that would switch the kit's hooks off (core.hooksPath,
    include.path). Other ones stay: Claude Code on the web hands in its own (url.*.insteadOf, credential.interactive)."""
    env = os.environ if env is None else env
    if BREAK("push_env_kept"):
        return env
    pairs = []
    for i in range(_count(env)):
        k, v = env.pop(f"GIT_CONFIG_KEY_{i}", None), env.pop(f"GIT_CONFIG_VALUE_{i}", None)
        if k is not None and k.strip().lower() not in SWITCH_KEYS:
            pairs.append((k, v or ""))
    env.pop("GIT_CONFIG_COUNT", None)
    if pairs:
        env["GIT_CONFIG_COUNT"] = str(len(pairs))
        for i, (k, v) in enumerate(pairs):
            env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = k, v
    if any(w in env.get("GIT_CONFIG_PARAMETERS", "").lower() for w in SWITCH_KEYS):
        del env["GIT_CONFIG_PARAMETERS"]
    return env


def _count(env):
    try:
        return max(0, min(int(env.get("GIT_CONFIG_COUNT", "0")), 1000))
    except ValueError:
        return 0


# Review 6 (F266): these switch the kit's hooks off, so one changed between steps is put back too
SWITCH_KEYS = ("core.hookspath", "include.path")
# What `git lfs install` writes: never judged (a game project with large art runs it on day one)
LFS = {"filter.lfs.clean": "git-lfs clean -- %f", "filter.lfs.smudge": "git-lfs smudge -- %f",
       "filter.lfs.process": "git-lfs filter-process", "filter.lfs.required": "true"}


def _git(root, *a):
    try:
        return subprocess.run(["git", *a], cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _out(p):
    return p.stdout.decode("utf-8", "replace").strip() if p and p.returncode == 0 else ""


def files(root):
    """{name shown to people: path} of the git settings files that matter for this folder."""
    out = {}
    common = _out(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    own = _out(_git(root, "rev-parse", "--absolute-git-dir"))
    if common:
        out[".git/config"] = os.path.join(common, "config")
    if own:
        out[".git/config.worktree" if own == common else "this worktree's config.worktree"] = os.path.join(own, "config.worktree")
    if not BREAK("gitconfig_global"):
        g = os.environ.get("GIT_CONFIG_GLOBAL")
        if g:
            out["your own git settings (" + g + ")"] = g
        elif os.environ.get("GIT_CONFIG_NOGLOBAL", "").lower() not in ("1", "true", "yes"):
            home = os.path.expanduser("~")
            xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
            out["your own git settings (~/.gitconfig)"] = os.path.join(home, ".gitconfig")
            out["your own git settings (" + os.path.join(xdg, "git", "config") + ")"] = os.path.join(xdg, "git", "config")
    return out


def risky(key, value):
    k = key.lower()
    if not BREAK("gitconfig_lfs") and LFS.get(k) == value:
        return False
    if any(fnmatch.fnmatchcase(k, p) for p in RISKY):
        return True
    return not BREAK("gitconfig_wide") and (bool(RUNS.search(k)) or any(fnmatch.fnmatchcase(k, p) for p in WIDE))


def unknown(key, value):
    """A key the kit doesn't know, with a value that isn't a plain yes/no or number: reported when it changes (F275)."""
    k = key.lower()
    if risky(key, value) or any(fnmatch.fnmatchcase(k, p) for p in HARMLESS):
        return False
    return not re.fullmatch(r"(?i)\s*(?:true|false|yes|no|on|off|-?\d+[kmg]?)?\s*", value)


def read(root, path, other=None):
    """(could git read it?, [[key, value], ...] of its risky settings in file order, the bytes) for one settings file.
    A list given as other gets the keys the kit doesn't know (F275)."""
    if not os.path.isfile(path):
        return True, [], None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return False, [], None
    p = _git(root, "config", "--file", path, "--no-includes", "--list", "-z")
    if not p or p.returncode != 0:
        return False, [], data
    out = []
    for item in p.stdout.decode("utf-8", "replace").split("\0"):
        if item:
            k, _, v = item.partition("\n")
            if risky(k, v):
                out.append([k, v])
            elif other is not None and unknown(k, v):
                other.append([k, v])
    return True, out, data


def _remotes(entries):
    return {k[7:].rsplit(".", 1)[0] for k, _ in entries if k.lower().startswith("remote.") and k.count(".") >= 2}


def judged(was, now):
    """The risky keys that differ between two lists. A new remote's own lines (`git remote add`) aren't judged; a change
    to a remote that already existed is."""
    known = _remotes(was)
    def by_key(es):
        d = {}
        for k, v in es:
            d.setdefault(k, []).append(v)  # git lists section and name in lower case, a subsection as written
        return d
    a, b = by_key(was), by_key(now)
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) == b.get(k):
            continue
        if k.startswith("remote.") and k.count(".") >= 2 and k[7:].rsplit(".", 1)[0] not in known and not BREAK("gitconfig_new_remote"):
            continue
        out.append(k)
    return out


def take(root):
    """{path: {"risky": [...], "ok": bool, "kept": where the bytes are kept}} as the files are now (an accepted state)."""
    st = {}
    for name, path in files(root).items():
        other = []
        ok, entries, data = read(root, path, other)
        kept = None
        if data is not None:
            p = subprocess.run(["git", "hash-object", "-w", "--no-filters", "--stdin"], cwd=root, input=data,
                               capture_output=True) if ok else None
            kept = _out(p) or None
        st[path] = {"name": name, "risky": entries, "other": other, "ok": ok, "kept": kept, "there": data is not None}
    return st


def _same(path, old):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return not old.get("there")
    return bool(old.get("kept")) and hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == old["kept"]


def _entries(root, blob):
    """(risky, other) of a kept settings file, read with today's lists (a record made before F274 has no "other")."""
    p = _git(root, "config", "--blob", blob, "--no-includes", "--list", "-z") if blob else None
    risky_, other = [], []
    for item in (p.stdout.decode("utf-8", "replace").split("\0") if p and p.returncode == 0 else []):
        if item:
            k, _, v = item.partition("\n")
            if risky(k, v):
                risky_.append([k, v])
            elif unknown(k, v):
                other.append([k, v])
    return risky_, other


def _was(root, old):
    if "other" in old or not old.get("kept") or BREAK("gitconfig_wide"):
        return old.get("risky") or [], old.get("other")
    return _entries(root, old["kept"])


def _submodule_ok(root, key, value):
    """submodule.NAME.url as .gitmodules has it (what `git submodule init` writes) isn't judged."""
    m = re.fullmatch(r"submodule\.(.+)\.url", key)
    if not m or BREAK("gitconfig_wide"):
        return False
    want = _out(_git(root, "config", "--file", os.path.join(root, ".gitmodules"), "submodule." + m.group(1) + ".url"))
    if not want or not value:
        return False
    if value == want:
        return True
    if want.startswith(("./", "../")):                 # relative: git resolves it against the remote's url
        base = (_out(_git(root, "config", "remote.origin.url")) or root).replace("\\", "/").rstrip("/")
        tail = want
        while tail.startswith(("./", "../")):
            head, tail = tail.split("/", 1)
            base = posixpath.dirname(base) if head == ".." else base
        return value.replace("\\", "/").rstrip("/") == base + "/" + tail.rstrip("/")
    return False


def differs(root, st, unknown_out=None):
    """[(path, name, keys)] of settings files whose risky settings differ from the accepted state st. A list given as
    unknown_out gets (name, keys) of changed keys the kit doesn't know (F275: reported, not put back)."""
    out = []
    for name, path in files(root).items():
        old = (st or {}).get(path)
        if old is None:
            old = {"risky": [], "other": [], "ok": True, "there": False}
        if _same(path, old):                           # unchanged since the last check: no need to ask git (speed)
            continue
        other = []
        ok, entries, data = read(root, path, other)
        if not ok and old.get("ok", True):
            out.append((path, name, ["(the whole file: git can't read it)"]))
            continue
        was, was_other = _was(root, old)
        now = dict((k, v) for k, v in entries)
        keys = [k for k in judged(was, entries) if not _submodule_ok(root, k, now.get(k))]
        if keys:
            out.append((path, name, keys))
        if unknown_out is not None and was_other is not None and not BREAK("gitconfig_unknown"):
            new = judged_any(was_other, other)
            if new:
                unknown_out.append((name, new))
    return out


def judged_any(was, now):
    """The keys that differ between two lists (no remote rule: used for reporting only)."""
    a, b = {}, {}
    for d, es in ((a, was), (b, now)):
        for k, v in es:
            d.setdefault(k, []).append(v)
    return [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def put_back(root, path, old, keys, keep_dir):
    """Put the judged keys back as they were (other lines of the file stay). (done?, where the changed file is kept)."""
    kept = None
    try:
        if os.path.isfile(path):
            kept = os.path.join(keep_dir, time.strftime("%Y%m%d-%H%M%S") + "_gitsettings_" + os.path.basename(path))
            os.makedirs(keep_dir, exist_ok=True)
            shutil.copy2(path, kept)
    except OSError:
        kept = None
    ok, _, _ = read(root, path)
    was = _was(root, old)[0]
    if ok and keys and keys[0][0] != "(":
        wanted = {}
        for k, v in was:
            wanted.setdefault(k, []).append((k, v))
        for k in keys:
            _git(root, "config", "--file", path, "--unset-all", k)
            for name, v in wanted.get(k, []):
                _git(root, "config", "--file", path, "--add", name, v)
        ok2, now, _ = read(root, path)
        if ok2 and not [k for k in judged(was, now) if k in keys]:
            return True, kept
    # git can't read it, or the keys didn't go back: the whole file as it was at the last check
    try:
        if not old.get("there"):
            if os.path.isfile(path):
                os.remove(path)
            return True, kept
        p = _git(root, "cat-file", "blob", old.get("kept") or "")
        if not old.get("kept") or not p or p.returncode != 0:
            return False, kept
        with open(path, "wb") as f:
            f.write(p.stdout)
        return True, kept
    except OSError:
        return False, kept


ON_WITH = ("Don't look for another way round; if the owner is away, leave them a note (in HANDOFF.md if the project "
           "has one) and carry on with other work.")


def words(back, fail):
    out = []
    if back:
        out.append("FoundationGuard: PUT BACK: " + "; ".join(back) + " changed without the owner's yes in this step, so the "
                   "kit put it back (git's settings decide which hooks run and which programs git starts; the changed file "
                   "is kept in .git/foundationguard/put_back/). A risky git setting changes only with the owner's yes: "
                   "ask the owner. " + ON_WITH)
    if fail:
        out.append("FoundationGuard: NOT PUT BACK: " + "; ".join(fail) + " changed in this step without the owner's yes, "
                   "and the kit could not put it back. Stop and tell the owner.")
    return " ".join(out)
